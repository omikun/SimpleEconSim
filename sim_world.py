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


def build_world(seed=None):
    """Build the 9x9 hex world and return (tiles, nations, grid).

    grid: list of lists (rows x cols) of the same Region objects as *tiles*,
    so callers can address tiles by (row, col).  ``seed=None`` seeds from
    system entropy (nondeterministic); pass an int for reproducible worlds.
    """
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()
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

    # ---- Nations claim contiguous hex clusters (disjoint) ----
    # Sizes are locked with the user: Alpha 3, Beta 4, Gamma 5 tiles.
    claimed_by = {"Alpha": ("AL", 3), "Beta": ("BE", 4), "Gamma": ("GA", 5)}
    nations = []

    def _unclaimed_cells():
        return {(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)
                if getattr(grid[r][c], 'owner_nation', None) is None}

    for nname, (cur, n_tiles) in claimed_by.items():
        n = Nation(nname, currency=cur,
                   regime_type="autocracy" if nname != "Gamma" else "democracy")
        nations.append(n)
        open_cells = _unclaimed_cells()
        # BFS cluster growth: seed at a random unclaimed cell, then keep
        # absorbing random unclaimed hex-adjacent cells until the target
        # size is reached.  This keeps every nation's starting tiles in ONE
        # connected component (the hex adjacency is computed via the same
        # odd-r layout used by the wiring pass below).
        seed_r, seed_c = random.choice(sorted(open_cells))
        cluster = [(seed_r, seed_c)]
        frontier = [(seed_r, seed_c)]
        seen = {(seed_r, seed_c)}
        while len(cluster) < n_tiles:
            grown = False
            random.shuffle(frontier)
            for pr, pc in frontier:
                q, axr = _LAYOUT[f"r{pr}c{pc}"]
                for nq, nar in axial_neighbors(q, axr):
                    nc, nr = axial_to_offset(nq, nar)
                    if not (0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS):
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
                # Full grid is an edge case; fall back to any unclaimed cell.
                rest = sorted(_unclaimed_cells() - seen)
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
        n_parts = 1 if len(cluster) < 3 else (2 if len(cluster) <= 4 else 3)
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

    # ---- True hex adjacency (routes every edge) ----
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            tile = grid[r][c]
            q, axr = _LAYOUT[tile.name]
            for nq, nar in axial_neighbors(q, axr):
                nc, nr = axial_to_offset(nq, nar)
                if 0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS:
                    other = grid[nr][nc]
                    if other.name not in tile.neighbors:
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
        curr_before = {c: fx.audit_currency_total(tiles, c) for c in currencies}

        for r in tiles:
            pending = {}
            for other in tiles:
                if other is r or other not in r.neighbors.values():
                    continue
                for g, entries in pending_imports(r, other).items():
                    pending.setdefault(g, []).extend(entries)
            r.pending_imports = pending
            r._auction_import_sales = {}

        # v3 provinces: provincial tiles run the ONCE-PER-PROVINCE flow
        # (shared charity/bank/gov); legacy / wilderness tiles keep the
        # per-tile r.step() path.  Province.step calls each member tile's
        # step_economy() (guarded so the shared institutionals don't double).
        _provinces = [p for n in nations for p in getattr(n, 'provinces', [])]
        _prov_tiles = {}
        for p in _provinces:
            for r in p.tiles:
                _prov_tiles[r.name] = r
        for p in _provinces:
            p.step(t)
        for r in tiles:
            if r.name in _prov_tiles:
                continue
            r.step(t)

        for r in tiles:
            for rt in r._all_routes():
                rt.advance()
                rt.deliver_pending()

        resolve_parked(tiles)

        for r, other in pair_orders:
            settle_trade(t, other, r)

        fx.cycle_all_markets(tiles, t)

        # v3: real conserved movement (claimed tiles under pressure push
        # residents toward wilderness / other nations).  Events feed the
        # world ticker archive.
        mig_events = run_migrations(t, tiles)
        world_events.extend(mig_events)
        if mig_events:
            for ev in mig_events:
                print(f"  T={t}: MIGRATE a{ev['agent_id']} "
                      f"{ev['from']} -> {ev['to']} ({ev['via']})")

        # v3: claims milestone — evaluate 50% majority claim rule on wilderness tiles
        claim_events = check_and_apply_claims(t, tiles, nations)
        world_events.extend(claim_events)
        if claim_events:
            for ev in claim_events:
                print(f"  T={t}: CLAIM {ev['nation']} claimed {ev['tile']} "
                      f"({ev['origin_count']}/{ev['pop']} {ev['share']*100:.1f}%)")
            pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                           and r.neighbors.get(o.name) is not None
                           and not getattr(o, 'wilderness', False)
                           and not getattr(r, 'wilderness', False)]

        # v3: trader wilderness settlement — every claimed tile's
        # traders service adjacent UNCLAIMED tiles with homesteaders
        # (no-interest loan of goods, collect outputs, half-diff payout).
        for r in tiles:
            if getattr(r, 'owner_nation', None) is None or not r.trader_agents:
                continue
            for other in r.neighbors.values():
                if not getattr(other, 'wilderness', False):
                    continue
                if not any(getattr(a, 'is_homesteader', False) for a in other.agents):
                    continue
                for trader in r.trader_agents:
                    settle_wilderness(trader, other, t)

        for n in nations:
            step_regime(n, t)

        for r, other in pair_orders:
            desk = r.forex_desks.get(other.name)
            if desk is not None:
                ppp = max(0.1, other.cost_of_living) / max(0.1, r.cost_of_living)
                desk.update(0, bank=r.bank, fx_regime='managed', ppp_target=ppp)
                if getattr(r, 'destination_region', None) is other:
                    desk.save_rate(r)

        for c in currencies:
            delta = fx.audit_currency_total(tiles, c) - curr_before[c]
            # v3: legitimate destruction (heirless estate on a state-less
            # wilderness tile, future lost-at-sea cargo) is RECORDED in the
            # ledger and exempt — the alarm fires only on unexplained losses.
            recorded = ledger.cleared(t, c)
            unaccounted = delta + recorded
            if abs(unaccounted) > 5.0:
                print(f"  T={t}: CURRENCY {c!r} SUPPLY SHIFT ${unaccounted:.2f}"
                      f" (raw {delta:+.2f}, destruction {recorded:.2f})")
        for ev in ledger.all_events():
            if ev['t'] != t:
                continue
            print(f"  T={t}: DESTROY {ev['currency'] or '-'} "
                  f"{ev['amount']:.2f} ({ev['reason']})")

        for r in tiles:
            for other in tiles:
                if other is r or other not in r.neighbors.values():
                    continue
                turn_export = sum(r.export_val[g][-1]
                                  for g in [Goods.food, Goods.wood, Goods.furniture]
                                  if r.export_val[g])
                turn_import = sum(r.import_val[g][-1]
                                  for g in [Goods.food, Goods.wood, Goods.furniture]
                                  if r.import_val[g])
                r.cumulative_trade_balance += (turn_export - turn_import)
                r.trade_flow_log.append(turn_export - turn_import)

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