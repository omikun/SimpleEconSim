#!/usr/bin/env python3
"""Verify the 9x9 hex world wiring + perf smoke (headless).

Checks:
  1. 81 tiles; every engine-wired edge is hex-adjacent on the true honeycomb
     (0 bad edges = "all hexes connect like Civilization").
  2. Every INTERIOR tile is edge-adjacent to exactly 6 neighbors.
  3. Pixel <-> axial round-trip for the full offset layout.
  4. Perf smoke: time N turns of the sim_world main-loop body, report
     turns/sec (81 Region.step() per turn).

Usage:
    python3 tmp/verify_hex_adj.py [turns]
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import logInit
import forex as fx
from goods import Goods
from world_trade import pending_imports, resolve_parked, settle_trade
from regime import step_regime
from migration import run_migrations
from trade_settle import settle_wilderness
from claims import check_and_apply_claims
from hexmap import (rectangular_hex_layout, pixel_to_axial, axial_to_pixel,
                    assert_edges_are_hex_adjacent, axial_neighbors,
                    axial_to_offset, offset_to_axial)
import ledger
from sim_world import build_world, GRID_ROWS, GRID_COLS

TURNS = int(sys.argv[1]) if len(sys.argv) > 1 else 10


def parse_rc(name):
    return int(name[1:name.index('c')]), int(name[name.index('c') + 1:])


def check_adjacency(tiles, layout):
    bad = assert_edges_are_hex_adjacent(tiles, layout=layout)
    print(f"[1] adjacency: {len(bad)} bad edges "
          f"({'PASS' if not bad else 'FAIL'})")
    for a, b in bad:
        print(f"  BAD EDGE: {a} <-> {b}")
    return not bad


def check_six_neighbors(grid):
    bad = []
    for r in range(1, GRID_ROWS - 1):
        for c in range(1, GRID_COLS - 1):
            n = len(grid[r][c].neighbors)
            if n != 6:
                bad.append((f"r{r}c{c}", n))
    print(f"[2] interior 6-neighbor: {len(bad)} non-6 tiles "
          f"({'PASS' if not bad else 'FAIL'})")
    for name, n in bad:
        print(f"  {name} has {n} neighbors")
    return not bad


def check_roundtrip(size=55):
    layout = rectangular_hex_layout(GRID_ROWS, GRID_COLS)
    ok = True
    for name, (q, r) in sorted(layout.items()):
        x, y = axial_to_pixel(q, r, size)
        q2, r2 = pixel_to_axial(x, y, size)
        if (q2, r2) != (q, r):
            print(f"  MISMATCH {name}: ({q},{r}) -> ({q2},{r2})")
            ok = False
    print(f"[3] pixel<->axial round-trip ({len(layout)} tiles) "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def perf_smoke(tiles, nations, turns):
    currencies = [n.currency for n in nations]
    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None
                   and not getattr(o, 'wilderness', False)]

    ledger.reset()
    t0 = time.time()
    shifts = []
    for t in range(1, turns + 1):
        curr_before = {c: fx.audit_currency_total(tiles, c)
                       for c in currencies}
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

        mig_events = run_migrations(t, tiles)
        claim_events = check_and_apply_claims(t, tiles, nations)
        if claim_events:
            pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                           and r.neighbors.get(o.name) is not None
                           and not getattr(o, 'wilderness', False)
                           and not getattr(r, 'wilderness', False)]

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
            recorded = ledger.cleared(t, c)
            unaccounted = delta + recorded
            if abs(unaccounted) > 5.0:
                shifts.append((t, c, unaccounted))
    dt = time.time() - t0
    print(f"[4] perf smoke: {turns} turns in {dt:.2f}s "
          f"({turns / max(dt, 1e-9):.2f} turns/sec)")
    if shifts:
        print(f"    {len(shifts)} SUPPLY SHIFT (reported, not a hard fail):")
        for t, c, u in shifts:
            print(f"      T={t} {c} {u:+.2f}")
    else:
        print("    0 SUPPLY SHIFT")
    return True


def main():
    logInit()
    tiles, nations, grid = build_world()
    layout = rectangular_hex_layout(GRID_ROWS, GRID_COLS)
    print(f"9x9 hex world: {len(tiles)} tiles, "
          f"{[n.name for n in nations]}, {TURNS} turns\n")
    ok = True
    ok &= check_adjacency(tiles, layout)
    ok &= check_six_neighbors(grid)
    ok &= check_roundtrip()
    perf_smoke(tiles, nations, TURNS)
    print("\n" + "=" * 60)
    print("HEX-WORLD VERIFY PASS" if ok else "HEX-WORLD VERIFY FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())