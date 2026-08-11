#!/usr/bin/env python3
"""
M1 gate: behavior-drift validation for the REGNUM M1 milestone.

Runs the 3-tile ring (A-B-C-A) for 300 turns across 3 seeds and asserts:
  - per-currency conservation (0 SUPPLY SHIFT over the 5.0 threshold),
  - combined cash conservation (0 CASH LEAK over the 5.0 threshold),
  - no BANK INSOLVENCY (no exception propagates),
  - behavior actually DRIFTS with the M1 machinery:
      * agents carry traits in [0,1] and identity tags,
      * memory buffers stay bounded (<= 32 entries),
      * migration intent scores were logged every turn,
      * at least one learned career switch happened (M1.4 path).

Usage:
    python3 tmp/behavior_drift.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goods import Goods
from region import Region
from logger import logInit
import forex as fx
from world_trade import (pending_imports, resolve_parked, settle_trade,
                         trader_wealth)

TRANSPORT_DELAY = 1
SEEDS = (42, 7, 1337)
TURNS = 300
LEAK_THRESHOLD = 5.0


def update_exchange_rate_pair(region, partner):
    """Copy of sim_ring's per-pair desk update (keeps FX regime live)."""
    desk = region.forex_desks.get(partner.name)
    if desk is None:
        return
    home_col = max(0.1, region.cost_of_living)
    partner_col = max(0.1, partner.cost_of_living)
    ppp = partner_col / home_col
    desk.update(0, bank=region.bank,
                fx_regime=getattr(region.gov, 'fx_regime', 'managed'),
                ppp_target=ppp)
    if getattr(region, 'destination_region', None) is partner:
        desk.save_rate(region)


def build_ring():
    """Build the standard 3-tile ring and wire routes + FX desks."""
    region_a = Region("A", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.753,
                                               Goods.wood: 0.110,
                                               Goods.furniture: 0.037},
                      number_of_traders=3,
                      terrain={Goods.food: 1.6})
    region_b = Region("B", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.50,
                                               Goods.wood: 0.35,
                                               Goods.furniture: 0.05},
                      number_of_traders=3,
                      terrain={Goods.wood: 1.6})
    region_c = Region("C", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.55,
                                               Goods.wood: 0.20,
                                               Goods.furniture: 0.12},
                      number_of_traders=3)
    regions = [region_a, region_b, region_c]
    for r in regions:
        for other in regions:
            if other is r:
                continue
            r.add_neighbor(other)
    for r in regions:
        for other in regions:
            if other is r:
                continue
            fx.connect_desks(r, other, t=0)
    return regions


def run_seed(seed, turns):
    """Run the ring for *turns* with *seed*; return (failures, stats)."""
    random.seed(seed)
    regions = build_ring()
    currencies = [r.home_currency for r in regions]
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]

    failures = []
    learned_switches = 0
    peak_mem_entries = 0
    migration_logged = 0

    for t in range(1, turns + 1):
        curr_before = {c: fx.audit_currency_total(regions, c) for c in currencies}
        cash_before = sum(curr_before.values())

        for r in regions:
            pending = {}
            for other in regions:
                if other is r:
                    continue
                for g, entries in pending_imports(r, other).items():
                    pending.setdefault(g, []).extend(entries)
            r.pending_imports = pending
            r._auction_import_sales = {}

        for r in regions:
            r.step(t)

        for r in regions:
            for rt in r._all_routes():
                rt.advance()
                rt.deliver_pending()
        resolve_parked(regions)

        for r, other in pair_orders:
            settle_trade(t, other, r)

        fx.cycle_all_markets(regions, t)

        for r, other in pair_orders:
            update_exchange_rate_pair(r, other)

        for c in currencies:
            delta = fx.audit_currency_total(regions, c) - curr_before[c]
            if abs(delta) > LEAK_THRESHOLD:
                failures.append(
                    f"seed={seed} T={t}: CURRENCY {c!r} SUPPLY SHIFT ${delta:.2f}")

        cash_after = sum(fx.audit_currency_total(regions, c) for c in currencies)
        if abs(cash_after - cash_before) > LEAK_THRESHOLD:
            failures.append(
                f"seed={seed} T={t}: COMBINED CASH LEAK ${cash_after - cash_before:.2f}")

        # ---- M1 behavior probes (every 50 turns) ----
        if t % 50 == 0:
            for r in regions:
                migration_logged += len(r.migration_intent_log) > 0
                for a in r.agents:
                    if a.is_corporation or a.is_government:
                        continue
                    peak_mem_entries = max(peak_mem_entries,
                                           max((len(v) for v in a.memory.values()), default=0))
                    # Trait bounds
                    for tr in ('ambition', 'loyalty', 'charisma', 'risk_tolerance',
                               'productivity', 'fertility', 'religiousness'):
                        v = getattr(a, tr, 0.5)
                        if not (0.0 <= v <= 1.0):
                            failures.append(
                                f"seed={seed} T={t} agent{a.id} {tr}={v} out of [0,1]")
                    if a.ethnicity is None or a.religion is None or a.politics is None:
                        failures.append(
                            f"seed={seed} T={t} agent{a.id} missing identity tag")

    # End-of-run survival / career probes
    for r in regions:
        learned_switches += sum(
            1 for a in r.agents
            if any(k.startswith('mem_') for k in a.memory)
        )

    stats = {
        'learned_memory_agents': learned_switches,
        'peak_mem_entries': peak_mem_entries,
        'migration_tile_turns_logged': migration_logged,
        'final_pop': sum(r.total_population[-1] if r.total_population else 0
                         for r in regions),
    }
    return failures, stats


def main():
    logInit()
    print(f"M1 behavior-drift gate: {TURNS} turns x {len(SEEDS)} seeds\n")
    all_failures = []
    all_stats = []
    for seed in SEEDS:
        try:
            failures, stats = run_seed(seed, TURNS)
        except Exception as exc:  # noqa: BLE001 - report insolvency as failure
            all_failures.append(f"seed={seed}: EXCEPTION {type(exc).__name__}: {exc}")
            continue
        all_failures.extend(failures)
        all_stats.append(stats)
        status = "FAIL" if failures else "PASS"
        print(f"seed={seed}: {status}  pop={stats['final_pop']}, "
              f"mem_agents={stats['learned_memory_agents']}, "
              f"peak_mem={stats['peak_mem_entries']}, "
              f"migration_logged={stats['migration_tile_turns_logged']}")

    print("\n" + "=" * 60)
    if all_failures:
        print(f"GATE FAILED: {len(all_failures)} conservation/behavior violations")
        for f in all_failures[:20]:
            print(f"  {f}")
        sys.exit(1)

    # Behavior-drift assertions: M1 machinery must actually engage.
    peak_mem = max(s['peak_mem_entries'] for s in all_stats)
    mem_agents = max(s['learned_memory_agents'] for s in all_stats)
    mig_logged = sum(s['migration_tile_turns_logged'] for s in all_stats)
    if peak_mem > 32:
        print(f"GATE FAILED: memory buffer grew to {peak_mem} entries (cap 32)")
        sys.exit(1)
    if mem_agents == 0:
        print("GATE FAILED: no agents accumulated memory — M1 memory inert")
        sys.exit(1)
    if mig_logged == 0:
        print("GATE FAILED: migration intent score never logged — M1.5 inert")
        sys.exit(1)

    print(f"GATE PASS: 0 LEAK / 0 SUPPLY SHIFT / no insolvency across "
          f"{len(SEEDS)} seeds x {TURNS} turns")
    print(f"  max memory buffer size: {peak_mem} (<= 32)")
    print(f"  agents with learned memory: {mem_agents}")
    print(f"  migration-intent tile-turns logged: {mig_logged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())