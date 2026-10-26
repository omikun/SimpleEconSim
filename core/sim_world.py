#!/usr/bin/env python3
"""
Call of Capital v3_wilderness — 9x9 hex headless world (M0.5-style driver).

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


def _starting_population_for_tile(tile) -> int:
    """Starting population scaled by geography and carrying capacity.
    - Mountains: ~45 agents (sparse highlands)
    - Hills/Highlands: ~75 agents
    - Lowlands/Plains: ~95 agents
    - Coasts: ~135 agents (flourishing maritime/delta hubs)
    """
    if getattr(tile, 'is_ocean', False):
        return 0
    elev = getattr(tile, 'elevation', 0.20)
    biome = getattr(tile, 'biome', 'plains')
    is_mountain = (elev >= 0.72) or (biome in ('mountains', 'snow_peaks'))
    is_coast = getattr(tile, 'is_coast', False) or (biome == 'coast')

    if is_mountain:
        return 45
    elif is_coast:
        return 135
    elif elev >= 0.40:
        return 75
    else:
        return 95


def _professions_for_tile(tile) -> dict:
    """Terrain-aware profession distribution.
    - Mountains: No trees -> 0 loggers, 0 carpenters, 100% food gatherers/miners.
    - Coasts: Maritime/delta food surplus -> 85% farmers/fishers, 10% wood, 5% furniture.
    - Lowlands/Plains: Standard agrarian-craftsman balance (60% food, 25% wood, 15% furniture).
    """
    elev = getattr(tile, 'elevation', 0.20)
    biome = getattr(tile, 'biome', 'plains')
    is_mountain = (elev >= 0.72) or (biome in ('mountains', 'snow_peaks'))
    is_coast = getattr(tile, 'is_coast', False) or (biome == 'coast')

    if is_mountain:
        # Strictly no trees in the mountains: 0 loggers, 0 carpenters
        return {Goods.food: 1.0, Goods.wood: 0.0, Goods.furniture: 0.0}
    elif is_coast:
        # More farmers/fishers on coastal tiles
        return {Goods.food: 0.85, Goods.wood: 0.10, Goods.furniture: 0.05}
    else:
        return {Goods.food: 0.60, Goods.wood: 0.25, Goods.furniture: 0.15}


def _professions():
    """Fallback default baseline professions."""
    return {Goods.food: 0.60, Goods.wood: 0.25, Goods.furniture: 0.15}


def make_claimed(name, profs):
    """One claimed (owned) tile with 100 agents + 2 traders per good."""
    return Region(name, t=0, number_of_agents=100,
                  profession_distribution=profs,
                  number_of_traders=2)


def make_wilderness(name):
    """One unclaimed tile: currency-less, no institutions, scalar natives."""
    return Region(name, t=0, wilderness=True)


def build_world_hex(seed=None, terrain_seed=None, nation_seed=None, scenario_id=None):
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

    # Ensure ocean tiles have 0 natives and 0 agents, and scale wilderness population by geography
    for t in tiles:
        if getattr(t, 'is_ocean', False):
            t.wilderness_pop = 0
            t.agents = []
        else:
            t.wilderness_pop = int(_starting_population_for_tile(t) * 0.8)

    # ---- Nations claim contiguous hex clusters (disjoint, strictly on land) ----
    # 3 Starting Global Powers from the 10-country database (sizes 3, 4, 5)
    from world_names import get_starting_nations_claimed_by
    claimed_by = get_starting_nations_claimed_by(seed=nation_seed, scenario_id=scenario_id)
    nations = []

    def _unclaimed_land_cells():
        return {(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)
                if getattr(grid[r][c], 'owner_nation', None) is None and not getattr(grid[r][c], 'is_ocean', False)}

    for nname, (cur, n_tiles) in claimed_by.items():
        regime = "democracy" if rng_nation.random() > 0.5 else "autocracy"
        n = Nation(nname, currency=cur, regime_type=regime, initial_cash=1000.0)
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
                init_pop = _starting_population_for_tile(tile)
                init_profs = _professions_for_tile(tile)
                claimed = Region(tile.name, t=0, number_of_agents=init_pop,
                                 profession_distribution=init_profs,
                                 number_of_traders=2,
                                 institutions=prov.institutions,
                                 seat_gov=(i == 0))
                # CRITICAL: Preserve all terrain, elevation, and biome attributes!
                claimed.elevation = tile.elevation
                claimed.elevation_meters = tile.elevation_meters
                claimed.biome = tile.biome
                claimed.terrain_color = tile.terrain_color
                claimed.hillshade = tile.hillshade
                claimed.is_ocean = getattr(tile, 'is_ocean', False)
                claimed.is_coast = getattr(tile, 'is_coast', False)
                claimed.is_river_corridor = getattr(tile, 'is_river_corridor', False)
                claimed.grid_r = getattr(tile, 'grid_r', rr)
                claimed.grid_c = getattr(tile, 'grid_c', cc)

                tiles[idx] = claimed
                grid[rr][cc] = claimed
                prov.add_tile(claimed)
                n.add_tile(claimed)
            n.provinces.append(prov)

    # ---- Geographic Passability & Trade Network Degree Capping ----
    # Mountains: strictly 1 or 2 neighbors it can trade with
    # Most tiles: no more than 3 trading partners
    from terrain_edges import reset_edge_manager
    edge_mgr = reset_edge_manager(tiles, _LAYOUT)

    def _is_hex_mountain(t) -> bool:
        elev = getattr(t, 'elevation', 0.20)
        biome = getattr(t, 'biome', 'plains')
        return (elev >= 0.72) or (biome in ('mountains', 'snow_peaks'))

    def _max_trade_partners(t) -> int:
        return 2 if _is_hex_mountain(t) else 3

    def _hex_adjacent(tile):
        q, axr = _LAYOUT[tile.name]
        for nq, nar in axial_neighbors(q, axr):
            nc, nr = axial_to_offset(nq, nar)
            if 0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS:
                yield grid[nr][nc]

    from world_topology import build_trade_network_topology, connect_claimed_forex_and_trader_wealth
    build_trade_network_topology(
        tiles,
        edge_mgr,
        _hex_adjacent,
        is_mountain_fn=_is_hex_mountain,
        max_trade_partners_fn=_max_trade_partners,
        river_bonus=150.0,
        strict_degree_cap_on_bridge=True,
        fallback_respects_cap=True,
    )
    connect_claimed_forex_and_trader_wealth(tiles, fx, trader_wealth)

    # ---- Assign Procedural Natural Resource Endowments ----
    from tile_resources import assign_tile_resources
    assign_tile_resources(tiles, seed=seed if seed is not None else 42)

    # ---- Assign Geological Climate Zoning & Capitalist Institutions ----
    from economy.map_generator import apply_geological_and_economic_distribution, setup_capitalism_institutions
    apply_geological_and_economic_distribution(tiles, grid, seed=seed if seed is not None else 42)
    for tile in tiles:
        setup_capitalism_institutions(tile, t=0)

    # ---- Assign Realistic Country Identities, Capitals & City Names ----
    from world_names import assign_world_identities
    assign_world_identities(tiles, nations, seed=nation_seed)

    return tiles, nations, grid


def build_world(seed=None, terrain_seed=None, nation_seed=None, scenario_id=None):
    """Polymorphic world builder respecting world_config.MAP_TOPOLOGY."""
    from world_config import is_voronoi_topology
    if is_voronoi_topology():
        from sim_world_voronoi import build_world_voronoi
        return build_world_voronoi(seed=seed, terrain_seed=terrain_seed, nation_seed=nation_seed,
                                   scenario_id=scenario_id)
    return build_world_hex(seed=seed, terrain_seed=terrain_seed, nation_seed=nation_seed,
                           scenario_id=scenario_id)



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
