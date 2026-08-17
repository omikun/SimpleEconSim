#!/usr/bin/env python3
"""
REGNUM v3_wilderness — 10x8 headless world (M0.5-style driver).

Three Nations each randomly claim 2-3 tiles (100 agents / tile).  The rest of
the 80-tile grid is UNCLAIMED wilderness: ``Region(wilderness=True)`` with a
non-ticking ``wilderness_pop`` in 0..50, no bank/gov/charity/factions, and
no minted agents.  Homesteaders will arrive in a later milestone (migration).

Wiring:
  - Full grid adjacency: every tile is a neighbor (and has a Route) to its
    orthogonal neighbors — owned->owned and owned->adjacent-unclaimed both
    get structural routes (the trader settlement milestone uses them).
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
import ledger


GRID_COLS = 10
GRID_ROWS = 8


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


def build_world(seed=42):
    """Build the 10x8 world and return (tiles, nations, grid).

    grid: list of lists (rows x cols) of the same Region objects as *tiles*,
    so callers can address tiles by (row, col).
    """
    random.seed(seed)
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

    # ---- Nations claim 2-3 random tiles each (disjoint) ----
    claimed_by = {"Alpha": "AL", "Beta": "BE", "Gamma": "GA"}
    nations = []
    claimed_pool = list(tiles)
    random.shuffle(claimed_pool)
    cursor = 0
    for nname, cur in claimed_by.items():
        n = Nation(nname, currency=cur,
                   regime_type="autocracy" if nname != "Gamma" else "democracy")
        nations.append(n)
        n_tiles = random.randint(2, 3)
        for _ in range(n_tiles):
            tile = claimed_pool[cursor]
            cursor += 1
            # Rebuild this tile as a claimed tile (replacing wilderness).
            idx = tiles.index(tile)
            claimed = make_claimed(tile.name, profs)
            tiles[idx] = claimed
            grid[idx // GRID_COLS][idx % GRID_COLS] = claimed
            n.add_tile(claimed)

    # ---- Full grid adjacency (routes every edge) ----
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            tile = grid[r][c]
            for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS:
                    other = grid[nr][nc]
                    if other.name not in tile.neighbors:
                        tile.add_neighbor(other)

    # ---- ForexDesks only between claimed tiles ----
    seen = set()
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            a = grid[r][c]
            if getattr(a, 'owner_nation', None) is None:
                continue
            for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS):
                    continue
                b = grid[nr][nc]
                if getattr(b, 'owner_nation', None) is None:
                    continue
                key = tuple(sorted((a.name, b.name)))
                if key in seen:
                    continue
                seen.add(key)
                fx.connect_desks(a, b, t=0)

    for r in tiles:
        # trader_wealth reads region.bank.deposits — wilderness tiles have no
        # bank, so only claimed tiles get the baseline (unclaimed stay 0).
        if getattr(r, 'owner_nation', None) is not None:
            r._init_trader_wealth = trader_wealth(r)
        else:
            r._init_trader_wealth = 0.0
    return tiles, nations, grid


def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    logInit()
    random.seed(42)
    print(f"v3_wilderness: 10x8 world ({GRID_COLS}x{GRID_ROWS}), "
          f"{time_steps} turns\n")

    tiles, nations, _grid = build_world()
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

        for r in tiles:
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