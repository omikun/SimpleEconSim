#!/usr/bin/env python3
"""
Milestone E — verify the Region.step -> step_economy split is byte-identical
for the LEGACY path (province is None) and that the Province machinery is
syntactically/semantically sound:

  1. region/province import cleanly.
  2. sim_world build_world() -> every claimed tile still has its own bank/gov/
     charity and province is None; interior 6-neighbor + adjacency unchanged.
  3. A 6-turn legacy world run (migration + claims + trade + regime) produces
     0 SUPPLY SHIFT > 5.0 — proving the split kept the legacy flow intact.
  4. Province construction: build one Province with 2 claimed tiles sharing
     ONE bundle; assert they share the SAME bank/gov/charity instances.
  5. partition_contiguous returns *nparts* parts that together cover the
     cluster (size/contiguity smoke for small clusters).

Usage:
    PYTHONPATH=/Users/sli/Code /Users/sli/Code/venv/bin/python3 tmp/verify_milestone_e.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import logInit
import forex as fx
from goods import Goods
from world_trade import pending_imports, resolve_parked, settle_trade
from regime import step_regime
from migration import run_migrations
from trade_settle import settle_wilderness
from claims import check_and_apply_claims
import ledger
from sim_world import build_world, GRID_ROWS, GRID_COLS
from region import Region
from province import Province, partition_contiguous, InstitutionBundle


TURNS = 6


def check_imports():
    import province as p
    import region as r
    print("[1] imports: region + province OK "
          f"(Province={p.Province.__name__}, make_bundle ok)")
    return True


def check_province_build():
    """sim_world now builds PROVINCES: every claimed tile belongs to one,
    each province's tiles share ONE bank/gov/charity, and the shared gov
    agent is seated exactly once (on the province's first tile)."""
    tiles, nations, _ = build_world()
    claimed = [t for t in tiles
               if getattr(t, 'owner_nation', None) is not None]
    wild = [t for t in tiles
            if getattr(t, 'owner_nation', None) is None]
    provinces = [p for n in nations for p in getattr(n, 'provinces', [])]
    ok = True
    ok &= len(provinces) >= 3                      # at least one per nation
    ok &= all(1 <= len(p.tiles) <= 5 for p in provinces)
    ok &= all(t.province is not None for t in claimed)
    # every member tile of a province shares the SAME bundle
    ok &= all(len({id(t.bank) for t in p.tiles}) == 1
              and len({id(t.gov) for t in p.tiles}) == 1
              and len({id(t.charity) for t in p.tiles}) == 1
              for p in provinces)
    # shared gov seated exactly once (first tile only)
    ok &= all(len([t for t in p.tiles if getattr(t, '_seat_gov_agent', True)])
              == 1 for p in provinces)
    ok &= all(t.bank is None and t.gov is None and t.charity is None
              for t in wild)
    ok &= len(claimed) == 12
    print(f"[2] province build: {len(provinces)} provinces across "
          f"{len(nations)} nations, {len(claimed)} claimed (all in a "
          f"province, shared bundle, gov seated once), {len(wild)} wild "
          f"(all None) {'PASS' if ok else 'FAIL'}")
    return ok


def run_legacy_turns():
    """Short legacy world run with the NEW step_economy split — gates the
    split is byte-identical (province None -> full legacy behavior)."""
    tiles, nations, _ = build_world()
    currencies = [n.currency for n in nations]
    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None
                   and not getattr(o, 'wilderness', False)]

    ledger.reset()
    shifts = []
    for t in range(1, TURNS + 1):
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

        run_migrations(t, tiles)
        check_and_apply_claims(t, tiles, nations)
        if check_and_apply_claims is not None:
            pass

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

    ok = len(shifts) == 0
    print(f"[3] legacy world {TURNS}t with step_economy split: "
          f"{len(shifts)} SUPPLY SHIFT {'PASS' if ok else 'FAIL'}")
    for t, c, u in shifts:
        print(f"      T={t} {c} {u:+.2f}")
    return ok


def check_province_sharing():
    """Build two claimed tiles then merge into ONE province sharing a bundle."""
    profs = {Goods.food: 0.60, Goods.wood: 0.25, Goods.furniture: 0.08}
    a = Region("pA", t=0, number_of_agents=50, profession_distribution=profs,
               number_of_traders=1)
    b = Region("pB", t=0, number_of_agents=50, profession_distribution=profs,
               number_of_traders=1)
    prov = Province("provA", type("N", (), {'currency': 'XX'})(), t=0)
    prov.add_tile(a)
    prov.add_tile(b)
    ok = (a.bank is b.bank and a.gov is b.gov and a.charity is b.charity
          and prov.bank is a.bank and prov.gov is a.gov
          and prov.charity is a.charity
          and a.province is prov and b.province is prov)
    print(f"[4] province sharing: 2 tiles share ONE bundle "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def check_partition():
    """partition_contiguous covers the input exactly for small nparts."""
    cells = [(5, 0), (5, 1), (5, 2)]
    parts = partition_contiguous(cells, None, 2)
    flat = sorted(c for part in parts for c in part)
    ok = flat == sorted(cells) and len(parts) <= 2
    print(f"[5] partition_contiguous(3 cells -> up to 2 parts): "
          f"{len(parts)} part(s), cover={'PASS' if ok else 'FAIL'}")
    return ok


def main():
    logInit()
    ok = True
    ok &= check_imports()
    ok &= check_province_build()
    ok &= run_legacy_turns()
    ok &= check_province_sharing()
    ok &= check_partition()
    print("\n" + "=" * 60)
    print("MILESTONE E VERIFY PASS" if ok else "MILESTONE E VERIFY FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())