#!/usr/bin/env python3
"""
REGNUM v3_wilderness — 9x9 hex headless world (M0.5-style driver).

Three Nations each claim a CONTIGUOUS hex cluster (Alpha=3, Beta=4, Gamma=5
tiles; 100 agents / tile).  The rest of the 81-tile honeycomb is UNCLAIMED
wilderness: ``Region(wilderness=True)`` with a non-ticking
``wilderness_pop`` in 0..50, no bank/gov/charity/factions, and no minted
agents.  Homesteaders will arrive in a later milestone (migration).

Wiring:
  - True hex adjacency: the 9x9 rectangular odd-r offset grid maps 1:1 onto a
    pointy-top honeycomb (see hexmap.rectangular_hex_layout), so every
    INTERIOR tile is edge-adjacent to exactly SIX neighbors.  Owned->owned
    and owned->adjacent-unclaimed both get structural routes (the trader
    settlement milestone uses them).
  - ForexDesks ONLY between claimed tiles (unclaimed tiles have no bank and
    no home currency, so no desks can exist there).

Every turn runs the same conserved pipeline as sim_nation (pending imports ->
step -> routes -> parked resolve -> settle -> interbank -> regime -> audits)
and flags any per-currency SUPPLY SHIFT above 5.0.

Usage:
    python3 sim_world.py [time_steps]
"""

import sys
import random

from goods import Goods
from region import Region
from nation import Nation
from logger import logInit
import forex as fx
from world_trade import (pending_imports, resolve_parked, settle_trade,
                         trader_wealth)
from regime import step_regime
from migration import run_migrations
from trade_settle import settle_wilderness

from claims import check_and_apply_claims
from hexmap import (rectangular_hex_layout, axial_neighbors, axial_to_offset)
from province import Province, partition_contiguous
import ledger
import sim_engine


GRID_COLS = 9
GRID_ROWS = 9
# ---- True hex adjacency: every interior tile edges SIX axial neighbors.
#      The 9x9 odd-r offset grid maps 1:1 onto the honeycomb; engines
#      (migration/claims/trade) are neighbor-agnostic, so they pick up the
#      six-way connectivity with no changes.
_LAYOUT = rectangular_hex_layout(GRID_ROWS, GRID_COLS)


def _professions():
    return {Goods.food: 0.60, Goods.wood: 0.25, Goods.furniture: 0.08}


def make_claimed(name, profs):
    """One claimed (owned) tile with 100 agents + 2 traders per good."""
    return Region(name, t=0, number_of_agents=100,
                  profession_distribution=profs,
                  number_of_traders=2)


def make_wilderness(name):
    """One unclaimed tile: currency-less, no institutions, scalar natives."""
    return Region(name, t=0, wilderness=True)


def build_world(seed=None, terrain_seed=None, nation_seed=None):
    """Build the 9x9 hex world and return (tiles, nations, grid).

    grid: list of lists (rows x cols) of the same Region objects as *tiles*,
    so callers can address tiles by (row, col). Supports independent terrain_seed
    and nation_seed for procedural variations.
    """
    if terrain_seed is None:
        terrain_seed = seed if seed is not None else random.randint(1, 999999)
    if nation_seed is None:
        nation_seed = random.randint(1, 999999)

    rng_nation = random.Random(nation_seed)
    profs = _professions()

    tiles = []
    grid = []
    for r in range(GRID_ROWS):
        row = []
        for c in range(GRID_COLS):
            name = f"r{r}c{c}"
            tile = make_wilderness(name)
            row.append(tile)
            tiles.append(tile)
        grid.append(row)

    # ---- Apply realistic elevation heightmap and continuous landmass ----
    from heightmap import apply_heightmap_to_world
    apply_heightmap_to_world(tiles, seed=terrain_seed, grid_rows=GRID_ROWS, grid_cols=GRID_COLS)

    # Ensure ocean tiles have 0 natives and 0 agents
    for t in tiles:
        if getattr(t, 'is_ocean', False):
            t.wilderness_pop = 0
            t.agents = []

    # ---- Nations claim contiguous hex clusters (disjoint, strictly on land) ----
    # 3 Starting Global Powers from the 10-country database (sizes 3, 4, 5)
    from world_names import get_starting_nations_claimed_by
    claimed_by = get_starting_nations_claimed_by(seed=nation_seed)
    nations = []

    def _unclaimed_land_cells():
        return {(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)
                if getattr(grid[r][c], 'owner_nation', None) is None and not getattr(grid[r][c], 'is_ocean', False)}

    for nname, (cur, n_tiles) in claimed_by.items():
        regime = "democracy" if rng_nation.random() > 0.5 else "autocracy"
        n = Nation(nname, currency=cur, regime_type=regime)
        nations.append(n)
        open_cells = _unclaimed_land_cells()
        # BFS cluster growth strictly on land tiles in the central continent
        seed_r, seed_c = rng_nation.choice(sorted(open_cells))
        cluster = [(seed_r, seed_c)]
        frontier = [(seed_r, seed_c)]
        seen = {(seed_r, seed_c)}
        while len(cluster) < n_tiles:
            grown = False
            rng_nation.shuffle(frontier)
            for pr, pc in frontier:
                q, axr = _LAYOUT[f"r{pr}c{pc}"]
                for nq, nar in axial_neighbors(q, axr):
                    nc, nr = axial_to_offset(nq, nar)
                    if not (0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS):
                        continue
                    if getattr(grid[nr][nc], 'is_ocean', False):
                        continue
                    key = (nr, nc)
                    if key in seen or getattr(grid[nr][nc], 'owner_nation', None) is not None:
                        continue
                    seen.add(key)
                    cluster.append(key)
                    frontier.append(key)
                    grown = True
                    if len(cluster) >= n_tiles:
                        break
                if len(cluster) >= n_tiles:
                    break
            if not grown:
                rest = sorted(_unclaimed_land_cells() - seen)
                if not rest:
                    break
                extra = rest[0]
                seen.add(extra)
                cluster.append(extra)
                frontier.append(extra)

        # ---- v3 provinces: split each nation's contiguous cluster into
        #      1-3 contiguous sub-provinces, each sharing ONE bundle of
        #      bank/government/charity.  Member tiles are CONSTRUCTED with
        #      the shared bundle (``institutions=...``) so no per-tile bank
        #      capital is ever abandoned; the shared government agent is
        #      seated only on the province's first tile.  The per-currency
        #      audit dedupes shared banks/charities (id-seen set). ----
        # v3.1: balanced provinces — every STARTING province is 2-3 tiles (few
        # 1- or 5-tile provinces): Alpha(3)->1 part of 3, Beta(4)->[2,2],
        # Gamma(5)->[2,3].  partition_contiguous uses the farthest-pair seed
        # + smallest-part BFS growth to keep each part balanced AND contiguous.
        n_parts = 1 if len(cluster) < 4 else 2
        parts = partition_contiguous(cluster, _LAYOUT, n_parts)
        for part in parts:
            prov = Province(f"{nname}-{len(n.provinces)+1}", n, t=0)
            for i, (rr, cc) in enumerate(part):
                tile = grid[rr][cc]
                idx = tiles.index(tile)
                claimed = Region(tile.name, t=0, number_of_agents=100,
                                 profession_distribution=profs,
                                 number_of_traders=2,
                                 institutions=prov.institutions,
                                 seat_gov=(i == 0))
                tiles[idx] = claimed
                grid[rr][cc] = claimed
                prov.add_tile(claimed)
                n.add_tile(claimed)
            n.provinces.append(prov)

    # ---- True hex adjacency (routes every edge subject to geographic passability) ----
    from terrain_edges import reset_edge_manager
    edge_mgr = reset_edge_manager(tiles, _LAYOUT)
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            tile = grid[r][c]
            q, axr = _LAYOUT[tile.name]
            for nq, nar in axial_neighbors(q, axr):
                nc, nr = axial_to_offset(nq, nar)
                if 0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS:
                    other = grid[nr][nc]
                    if other.name not in tile.neighbors and edge_mgr.is_passable(tile.name, other.name):
                        tile.add_neighbor(other)

    # ---- ForexDesks only between claimed (neighbor) tiles ----
    seen = set()
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            a = grid[r][c]
            if getattr(a, 'owner_nation', None) is None:
                continue
            for other in a.neighbors.values():
                if getattr(other, 'owner_nation', None) is None:
                    continue
                key = tuple(sorted((a.name, other.name)))
                if key in seen:
                    continue
                seen.add(key)
                fx.connect_desks(a, other, t=0)

    for r in tiles:
        # trader_wealth reads region.bank.deposits — wilderness tiles have no
        # bank, so only claimed tiles get the baseline (unclaimed stay 0).
        if getattr(r, 'owner_nation', None) is not None:
            r._init_trader_wealth = trader_wealth(r)
        else:
            r._init_trader_wealth = 0.0

    return tiles, nations, grid


def main():
    time_steps = 30
    seed = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--seed' and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        elif args[i] == '-t' and i + 1 < len(args):
            time_steps = int(args[i + 1])
            i += 2
        elif args[i].isdigit():
            time_steps = int(args[i])
            i += 1
        else:
            i += 1
    logInit()
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()
    print(f"v3_wilderness: 9x9 hex world ({GRID_COLS}x{GRID_ROWS}), "
          f"{time_steps} turns\n")

    tiles, nations, _grid = build_world(seed=seed)
    currencies = [n.currency for n in nations]
    # Commerce pairs run through the priced-auction / FX machinery, which
    # requires a destination BANK + currency.  Wilderness tiles (no bank, no
    # currency) are serviced exclusively by trade_settle.settle_wilderness,
    # so pair only claimed tiles here.
    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None
                   and not getattr(o, 'wilderness', False)]

    n_claimed = sum(1 for t in tiles if getattr(t, 'owner_nation', None) is not None)
    n_wild = len(tiles) - n_claimed
    print(f"Nations: {', '.join(f'{n.name}({n.currency})' for n in nations)}")
    for n in nations:
        print(f"  {n.name}: tiles={[t.name for t in n.tiles]}, "
              f"legitimacy={n.legitimacy}")
    print(f"Terrain: {n_claimed} claimed / {n_wild} wilderness tiles\n")

    world_events = []
    ledger.reset()

    for t in range(1, time_steps + 1):
        def on_event(turn, kind, text):
            print(f"  T={turn}: {text}")

        violations, claim_events = sim_engine.step_turn(
            t, tiles, nations=nations, pair_orders=pair_orders,
            currencies=currencies, on_event=on_event, ledger_exempt=True
        )

        for v in violations:
            print(f"  T={v[0]}: CURRENCY {v[1]!r} SUPPLY SHIFT ${v[2]:.2f}")

        if claim_events:
            pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                           and r.neighbors.get(o.name) is not None
                           and not getattr(o, 'wilderness', False)
                           and not getattr(r, 'wilderness', False)]

        if t % 10 == 0:
            print(f"Progress: turn {t}/{time_steps}")

    print("\n" + "=" * 60)
    print("v3_WORLD FINAL SUMMARY")
    print("=" * 60)
    for n in nations:
        print(f"\n--- Nation {n.name} ({n.currency}) ---")
        gdp = 0.0
        pop = 0
        food_prices = []
        for r in n.tiles:
            gdp += r.gdp_log[-1] if r.gdp_log else 0
            pop += r.total_population[-1] if r.total_population else 0
            food_prices.append(r.recipes[Goods.food]['price'])
        print(f"  tiles={len(n.tiles)}, pop={pop}, GDP/turn=${gdp:.0f}, "
              f"food={', '.join(f'{p:.2f}' for p in food_prices)}")
        tr = n.treasury()
        print(f"  Treasury: ${tr['total']:.2f} ({tr['cash']:.2f} cash, "
              f"{tr['deposits']:.2f} deposits, {tr['food']} food)")
    homesteaders = sum(1 for r in tiles
                       if getattr(r, 'wilderness', False)
                       for a in r.agents if getattr(a, 'is_homesteader', False))
    print(f"\nWilderness: {n_wild} tiles, {homesteaders} homesteaders "
          f"(migration milestone pending)")
    print("Done.")


if __name__ == "__main__":
    main()