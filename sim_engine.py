"""
sim_engine.py — Canonical turn-stepping engine for Call of Capital simulations.

Coordinates the multi-layered turn pipeline across:
  1. World / Inter-tile Layer: pending imports, routes, parked goods, trade settlement,
     forex markets, migrations, claims, audits, and trade flow logs.
  2. National Layer: regime updates (elections/coups/legitimacy) and federal policies.
  3. Provincial & Local Layer: shared institutions (Province.step) and local tile
     economies (Region.step_economy or wilderness.step_wilderness).
"""

from goods import Goods
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade, desk_for
from regime import step_regime
from migration import run_migrations
from trade_settle import settle_wilderness
from claims import check_and_apply_claims
from intents import step_intents_and_construction
from army import step_armies
from diplomacy import get_diplomacy
from war_logic import apply_political_shocks, update_wars
import ledger


def step_turn(t: int, tiles: list, nations: list = None,
              pair_orders: list = None, currencies: list = None,
              on_event=None, ledger_exempt: bool = True, on_phase=None):
    """Run one canonical simulation turn across all hierarchical layers.

    Returns (violations, claim_events) where violations is a list of
    (t, currency, unaccounted_shift) tuples.
    """
    from collective_trace_clock import attach_clock
    trace_clock = attach_clock(tiles)
    if trace_clock is not None:
        trace_clock['turn'] = t
        trace_clock['phase'] = 'strategy'
    if nations is None:
        nations = []
    trace_recorder = next((getattr(tile, '_run_trace', None) for tile in tiles
                           if getattr(tile, '_run_trace', None) is not None), None)
    if trace_recorder is not None and trace_clock is not None:
        for nation in nations:
            nation._run_trace = trace_recorder
            nation._collective_trace_clock = trace_clock
        if getattr(trace_recorder, 'treasury_book', None) is not None:
            trace_recorder.treasury_book.register_nations(nations, trace_clock, basis='turn_boundary')
    # Per-turn counters belong to the simulation boundary. Snapshot/reporting
    # must remain read-only, including when invoked more than once.
    for tile in tiles:
        tile.births_this_turn = 0
        tile.deaths_this_turn = 0
        tile.deaths_by_cause_this_turn = {}
        tile.emergency_grain_levy_units = 0
        for agent in getattr(tile, 'agents', []):
            agent.food_levy_cap_this_turn = None
            agent.food_levied_this_turn = 0
    from trace_phase import treasury_boundary
    treasury_boundary(tiles, nations, 'turn_start')
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

    diplomacy = get_diplomacy()

    # 0a. AI Sovereign Decisions (submit intents)
    for n in nations:
        ai = getattr(n, 'ai', None)
        if ai is not None and hasattr(ai, 'decide_turn'):
            ai.decide_turn(t, tiles, nations, diplomacy)

    # 0b. Strategic Intents & Construction Projects
    if nations:
        step_intents_and_construction(t, tiles, nations, on_event=on_event)
    treasury_boundary(tiles, nations, 'projects')
    if on_phase:
        on_phase('projects')

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
        r._auction_import_sales_by_source = {}
        r._auction_import_sale_trace_ids = {}

    # 2. Stepping: Provinces first (shared institutions), then independent tiles
    if trace_clock is not None:
        trace_clock['phase'] = 'local'
    _provinces = [p for n in nations for p in getattr(n, 'provinces', [])]
    _prov_tiles = {r.name: r for p in _provinces for r in p.tiles}
    for p in _provinces:
        p.step(t)
    for r in tiles:
        if r.name in _prov_tiles:
            continue
        r.step(t)
    if on_phase:
        on_phase('local')
    treasury_boundary(tiles, nations, 'local')

    # 3. Advance routes and deliver in-transit cargo
    if trace_clock is not None:
        trace_clock['phase'] = 'trade'
    for r in tiles:
        for rt in r._all_routes():
            rt.advance()
            rt.deliver_pending()

    # 3b. Inter-regional trade epidemic transmission (The Great Pestilence)
    from disease import step_trade_epidemic_transmission
    step_trade_epidemic_transmission(tiles, t)

    # 4. Re-route parked goods
    resolve_parked(tiles)

    # 5. Settle bilateral trade between paired regions
    trade_exports_by_tile = {region.name: [] for region in tiles}
    for r, other in pair_orders:
        settle_trade(t, other, r)
        if r.name not in trade_exports_by_tile:
            continue
        partner_currency = getattr(other, 'home_currency', None)
        home_currency = getattr(r, 'home_currency', None)
        source_sales_by_good = getattr(
            other, '_auction_import_sales_by_source', {})
        pair_quantity = 0
        partner_value = 0.0
        source_sale_event_ids = []
        good_rows = []
        for good in (Goods.food, Goods.wood, Goods.furniture):
            source_rows = source_sales_by_good.get(good)
            if source_rows is None:
                quantity, value = getattr(other, '_auction_import_sales', {}).get(
                    good, (0, 0.0))
                source_event_ids = []
            else:
                source_row = source_rows.get(r.name, {})
                quantity = int(source_row.get('quantity', 0))
                value = float(source_row.get('value', 0.0))
                source_event_ids = list(source_row.get('event_ids', ()))
            pair_quantity += int(quantity)
            partner_value += float(value)
            source_sale_event_ids.extend(source_event_ids)
            good_rows.append({'good': good.name, 'quantity': int(quantity),
                              'value': float(value),
                              'sale_event_ids': source_event_ids})
        if home_currency == partner_currency:
            conversion_rate = 1.0
            conversion_basis = 'same_currency'
        elif home_currency is None or partner_currency is None:
            conversion_rate = 1.0
            conversion_basis = 'parity_assumed_missing_currency'
        else:
            desk = desk_for(r, other)
            if desk is None:
                conversion_rate = 1.0
                conversion_basis = 'parity_assumed_no_source_desk'
            else:
                conversion_rate = float(desk.buy_rate())
                conversion_basis = 'source_desk_current_buy_rate'
        trade_exports_by_tile[r.name].append({
            'partner_tile': other.name,
            'partner_currency': partner_currency,
            'home_currency': home_currency,
            'quantity': pair_quantity,
            'value_in_partner_currency': partner_value,
            'conversion_rate_to_home': conversion_rate,
            'conversion_basis': conversion_basis,
            'value_in_home_currency': partner_value * conversion_rate,
            'goods': good_rows,
            'source_sale_event_ids': source_sale_event_ids})

    # 6. Cycle all forex markets & convert non-trader foreign wallets
    fx.cycle_all_markets(tiles, t)
    for r in tiles:
        if getattr(r, 'owner_nation', None) is not None:
            fx.convert_non_trader_wallets(r.agents, r, t)

    # 7. Migrations
    mig_events = run_migrations(t, tiles)
    # Movement can invalidate an employer's cached worker list even when the
    # person's employment reference was already cleared. Keep both sides of
    # the contract consistent at the end of the migration phase.
    from region_labor import cleanup_labor
    for region in tiles:
        if getattr(region, 'agents', None):
            cleanup_labor(region)
    if on_event:
        for ev in mig_events:
            on_event(t, 'MIGRATE',
                     f"MIGRATE a{ev['agent_id']} {ev['from']} -> {ev['to']} ({ev['via']})")

    # 8. Claims check & application
    claim_events = check_and_apply_claims(t, tiles, nations) if nations else []
    if on_event:
        for ev in claim_events:
            if ev.get('event') == 'FRONTIER_CLAIM_REPELLED':
                on_event(t, 'FRONTIER_DEFENSE', ev.get('message', 'Claim repelled by customary inhabitants.'))
            else:
                on_event(t, 'CLAIM',
                         f"CLAIM {ev.get('nation', '')} claimed {ev.get('tile', '')} "
                         f"({ev.get('origin_count', 0)}/{ev.get('pop', 0)} {ev.get('share', 0.0)*100:.1f}%)")

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
                settle_wilderness(trader, other, t, source_region=r)
    if on_phase:
        on_phase('trade')
    treasury_boundary(tiles, nations, 'trade')

    # 10. National Regimes (elections, coups, legitimacy)
    if trace_clock is not None:
        trace_clock['phase'] = 'regime'
    for n in nations:
        apply_political_shocks(diplomacy, n, t)
        step_regime(n, t)
    if on_phase:
        on_phase('regime')
    treasury_boundary(tiles, nations, 'regime')

    # 10b. Military Upkeep & Supplies
    if nations:
        army_events = step_armies(tiles, nations, t)
        if on_event:
            for ev in army_events:
                kind = ev.get('event', 'MILITARY')
                if kind == 'ARMY_SUPPLY_SHORTAGE':
                    on_event(t, kind, f"Army unit {ev.get('unit_id')} in {ev.get('region', '?')} supply shortage (morale: {ev.get('morale', 0.0):.2f})")
                elif kind == 'DESERTER_HOMESTEAD':
                    on_event(t, kind, f"Deserter a{ev.get('agent_id')} from {ev.get('from_region', '?')} homesteaded on {ev.get('to_region', '?')} (xp: {ev.get('military_xp', 0.0):.2f})")
                elif kind == 'DESERTER_REABSORBED':
                    on_event(t, kind, f"Deserter a{ev.get('agent_id')} reabsorbed into {ev.get('region', '?')} labor pool (xp: {ev.get('military_xp', 0.0):.2f})")
                else:
                    on_event(t, kind, f"Military event on {ev.get('unit_id', '')}")
    if on_phase:
        on_phase('military')

    # The next AI turn reads a snapshot of completed battles, politics and
    # supplies; no side gets an advantage from nation iteration order.
    if nations:
        update_wars(diplomacy, nations, t)

    # 10c. Global Diplomacy & Relations Drift
    if nations:
        diplomacy.update_relations(tiles, nations, t)

    # 10d. Induced Innovation, Learning-by-Doing & Trade Diffusion
    if nations:
        from innovation import step_innovation
        inno_events = step_innovation(tiles, nations, pair_orders, t)
        if on_event:
            for ev in inno_events:
                on_event(t, ev.get('event', 'INNOVATION'), ev.get('message', ''))

    # 10e. Popular Resistance Escalation & Commune Formation
    world_ctx = {'tiles': tiles, 'nations': nations, 'pair_orders': pair_orders}
    try:
        from popular_resistance import get_popular_resistance_manager
        res_events = get_popular_resistance_manager().step_popular_resistance(world_ctx, t)
        if on_event and res_events:
            for ev in res_events:
                on_event(t, ev.get('kind', 'RESISTANCE'), ev.get('msg', ''))
    except Exception:
        pass
    if on_phase:
        on_phase('resistance')

    # 10f. Financial Imperialism & Core-Periphery Tracking
    try:
        from imperialism import get_imperialism_manager
        get_imperialism_manager().step_imperialism(world_ctx, t)
    except Exception:
        pass

    # 11. Forex desks update & PPP tracking
    if trace_clock is not None:
        trace_clock['phase'] = 'forex'
    for r, other in pair_orders:
        desk = r.forex_desks.get(other.name)
        if desk is not None:
            ppp = max(0.1, other.cost_of_living) / max(0.1, r.cost_of_living)
            desk.update(t, bank=r.bank, fx_regime='managed', ppp_target=ppp,
                        trace_region=r)
            if getattr(r, 'destination_region', None) is other:
                desk.save_rate(r)

    # 12. Currency Audits & Ledger Destruction Accounting
    treasury_boundary(tiles, nations, 'forex_and_diplomacy')
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

    # 13. Turn-level trade values, valued in each tile's home currency.
    if trace_clock is not None:
        trace_clock['phase'] = 'trade'
    from run_trace import emit
    for r in tiles:
        import_rows = []
        import_event_ids = []
        imports_by_source = getattr(r, '_auction_import_sales_by_source', {})
        import_trace_ids = getattr(r, '_auction_import_sale_trace_ids', {})
        import_total = 0.0
        for good in (Goods.food, Goods.wood, Goods.furniture):
            quantity, value = getattr(r, '_auction_import_sales', {}).get(
                good, (0, 0.0))
            quantity, value = int(quantity), float(value)
            source_rows = imports_by_source.get(good, {})
            breakdown = [
                {'source_tile': source,
                 'quantity': int(row.get('quantity', 0)),
                 'value': float(row.get('value', 0.0)),
                 'paid_sale_event_ids': list(row.get('event_ids', ()))}
                for source, row in sorted(source_rows.items())]
            summary_id = import_trace_ids.get(good)
            if summary_id is not None:
                import_event_ids.append(summary_id)
            import_rows.append({'good': good.name, 'quantity': quantity,
                                'value': value, 'currency': r.home_currency,
                                'source_breakdown': breakdown,
                                'market_summary_event_id': summary_id})
            import_total += value
        export_rows = trade_exports_by_tile.get(r.name, [])
        export_total = sum(row['value_in_home_currency'] for row in export_rows)
        net_total = export_total - import_total
        r.export_value_log.append(export_total)
        r.import_value_log.append(import_total)
        r.net_trade_value_log.append(net_total)
        r.cumulative_trade_balance += net_total
        r.trade_flow_log.append(net_total)
        currency = getattr(r, 'home_currency', None) or 'local_currency'
        export_event_id = emit(
            r, kind='trade_export_value_calculation',
            record_class='calculation', phase='trade',
            subject={'type': 'tile', 'id': r.name},
            metric_id='trade.export_value',
            unit=f'{currency}_per_turn',
            before=r.export_value_log[-2] if len(r.export_value_log) > 1 else None,
            after=export_total,
            formula_id='trade.sum_partner_values_in_home_currency.v1',
            inputs={'home_currency': currency,
                    'partner_settlements': export_rows,
                    'conversion_timing': 'trade_settlement_current_fx_quote',
                    'formula_result': export_total},
            cause_event_ids=[event_id for row in export_rows
                             for event_id in row['source_sale_event_ids']] or None)
        import_event_id = emit(
            r, kind='trade_import_value_calculation',
            record_class='calculation', phase='trade',
            subject={'type': 'tile', 'id': r.name},
            metric_id='trade.import_value',
            unit=f'{currency}_per_turn',
            before=r.import_value_log[-2] if len(r.import_value_log) > 1 else None,
            after=import_total,
            formula_id='trade.sum_market_import_values_in_home_currency.v1',
            inputs={'home_currency': currency, 'goods': import_rows,
                    'currency_conversion_applied': False,
                    'formula_result': import_total},
            cause_event_ids=import_event_ids or None)
        emit(r, kind='trade_net_value_calculation',
             record_class='calculation', phase='trade',
             subject={'type': 'tile', 'id': r.name},
             metric_id='trade.net_value', unit=f'{currency}_per_turn',
             before=r.net_trade_value_log[-2]
             if len(r.net_trade_value_log) > 1 else None,
             after=net_total,
             formula_id='trade.export_minus_import_value.v1',
             inputs={'export_value_home_currency': export_total,
                     'import_value_home_currency': import_total,
                     'formula_result': net_total},
             cause_event_ids=[event_id for event_id in
                              (export_event_id, import_event_id)
                              if event_id is not None])

    return violations, claim_events
