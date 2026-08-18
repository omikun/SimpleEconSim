"""
sim_engine.py — Canonical turn-stepping engine for REGNUM simulations.

Coordinates the multi-layered turn pipeline across:
  1. World / Inter-tile Layer: pending imports, routes, parked goods, trade settlement,
     forex markets, migrations, claims, audits, and trade flow logs.
  2. National Layer: regime updates (elections/coups/legitimacy) and federal policies.
  3. Provincial & Local Layer: shared institutions (Province.step) and local tile
     economies (Region.step_economy or wilderness.step_wilderness).
"""

from goods import Goods
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade
from regime import step_regime
from migration import run_migrations
from trade_settle import settle_wilderness
from claims import check_and_apply_claims
import ledger


def step_turn(t: int, tiles: list, nations: list = None,
              pair_orders: list = None, currencies: list = None,
              on_event=None, ledger_exempt: bool = True):
    """Run one canonical simulation turn across all hierarchical layers.

    Returns (violations, claim_events) where violations is a list of
    (t, currency, unaccounted_shift) tuples.
    """
    if nations is None:
        nations = []
    if currencies is None:
        currencies = [n.currency for n in nations if getattr(n, 'currency', None)]
        if not currencies:
            # Fall back to distinct tile currencies
            currencies = list({r.home_currency for r in tiles if getattr(r, 'home_currency', None)})
    if pair_orders is None:
        pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                       and r.neighbors.get(o.name) is not None
                       and not getattr(o, 'wilderness', False)
                       and not getattr(r, 'wilderness', False)]

    curr_before = {c: fx.audit_currency_total(tiles, c) for c in currencies}
    violations = []

    # 1. Gather pending cross-region imports
    for r in tiles:
        pending = {}
        for other in tiles:
            if other is r or other not in r.neighbors.values():
                continue
            for g, entries in pending_imports(r, other).items():
                pending.setdefault(g, []).extend(entries)
        r.pending_imports = pending
        r._auction_import_sales = {}

    # 2. Stepping: Provinces first (shared institutions), then independent tiles
    _provinces = [p for n in nations for p in getattr(n, 'provinces', [])]
    _prov_tiles = {r.name: r for p in _provinces for r in p.tiles}
    for p in _provinces:
        p.step(t)
    for r in tiles:
        if r.name in _prov_tiles:
            continue
        r.step(t)

    # 3. Advance routes and deliver in-transit cargo
    for r in tiles:
        for rt in r._all_routes():
            rt.advance()
            rt.deliver_pending()

    # 4. Re-route parked goods
    resolve_parked(tiles)

    # 5. Settle bilateral trade between paired regions
    for r, other in pair_orders:
        settle_trade(t, other, r)

    # 6. Cycle all forex markets
    fx.cycle_all_markets(tiles, t)

    # 7. Migrations
    mig_events = run_migrations(t, tiles)
    if on_event:
        for ev in mig_events:
            on_event(t, 'MIGRATE',
                     f"MIGRATE a{ev['agent_id']} {ev['from']} -> {ev['to']} ({ev['via']})")

    # 8. Claims check & application
    claim_events = check_and_apply_claims(t, tiles, nations) if nations else []
    if on_event:
        for ev in claim_events:
            on_event(t, 'CLAIM',
                     f"CLAIM {ev['nation']} claimed {ev['tile']} "
                     f"({ev['origin_count']}/{ev['pop']} {ev['share']*100:.1f}%)")

    # 9. Trader wilderness settlement
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

    # 10. National Regimes (elections, coups, legitimacy)
    for n in nations:
        step_regime(n, t)

    # 11. Forex desks update & PPP tracking
    for r, other in pair_orders:
        desk = r.forex_desks.get(other.name)
        if desk is not None:
            ppp = max(0.1, other.cost_of_living) / max(0.1, r.cost_of_living)
            desk.update(0, bank=r.bank, fx_regime='managed', ppp_target=ppp)
            if getattr(r, 'destination_region', None) is other:
                desk.save_rate(r)

    # 12. Currency Audits & Ledger Destruction Accounting
    for c in currencies:
        delta = fx.audit_currency_total(tiles, c) - curr_before[c]
        recorded = ledger.cleared(t, c) if ledger_exempt else 0.0
        unaccounted = delta + recorded
        if abs(unaccounted) > 5.0:
            violations.append((t, c, unaccounted))

    if ledger_exempt and on_event:
        for ev in ledger.all_events():
            if ev['t'] != t:
                continue
            on_event(t, 'DESTROY',
                     f"DESTROY {ev['currency'] or '-'} ${ev['amount']:.2f} ({ev['reason']})")

    # 13. Trade flow and balance logs
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

    return violations, claim_events
