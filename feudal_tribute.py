"""
Feudal tribute — lords collect a share of serf production in kind.

Under feudalism, serfs owe the lord a portion of their harvest
(tribute_rate, default 50%). This is NOT cash rent — it is grain,
wood, and goods transferred directly into the lord's inventory.
The lord does not need money to eat; tribute feeds the lord's household
and gives the lord surplus goods to sell at market.

Serfs keep their subsistence food reserve (4 food) so the feudal
commons sustain the peasantry as intended by customary tenure.
"""

from goods import Goods
from land_tenure import TenureStatus


def _find_agent(region, agent_id: int):
    """Find agent by ID in region."""
    for a in region.agents:
        if a.id == agent_id:
            return a
    return None


def _transfer_tribute(region, t, plot, serf, lord, good, quantity, *,
                      force_present, protest_energy):
    from economy.actor_accounts import record as record_economic_event
    from run_trace import emit

    operation_id = (f'feudal-tribute:{region.name}:{int(t)}:{plot.plot_id}:'
                    f'{serf.id}:{good.name}')
    serf_before = int(serf.inv_get(good, 0))
    lord_before = int(lord.inv_get(good, 0))
    serf.inv_add(good, -quantity)
    lord.inv_add(good, quantity)
    serf_after = int(serf.inv_get(good, 0))
    lord_after = int(lord.inv_get(good, 0))
    record_economic_event(
        region, 'feudal_tribute', turn=t, payer_id=serf.id,
        recipient_id=lord.id, good=good, quantity=quantity,
        asset_id=plot.plot_id, source_id=operation_id,
        detail={'operation_id': operation_id, 'tribute_rate': float(plot.tribute_rate),
                'force_present': bool(force_present),
                'protest_energy': float(protest_energy)})
    contract = {
        'contract_version': 'goods_transfer.v1',
        'operation_id': operation_id,
        'operation_type': 'feudal_tribute',
        'good': good.name,
        'unit': 'units',
        'amount': int(quantity),
        'payer_account': {
            'type': 'agent_inventory', 'id': str(serf.id),
            'good': good.name, 'balance_before': serf_before,
            'balance_after': serf_after, 'balance_scope': 'inventory'},
        'payee_account': {
            'type': 'agent_inventory', 'id': str(lord.id),
            'good': good.name, 'balance_before': lord_before,
            'balance_after': lord_after, 'balance_scope': 'inventory'},
        'cash_transfer_status': 'in_kind_no_cash',
        'counterparty_leg_status': 'both_inventory_balances_captured',
    }
    event_id = emit(
        region, kind='feudal_tribute_transfer', record_class='transfer',
        phase='economy',
        subject={'type': 'tile', 'id': region.name, 'good': good.name,
                 'serf_id': serf.id, 'lord_id': lord.id,
                 'plot_id': plot.plot_id},
        metric_id='goods.feudal_tribute', unit='units', before=0,
        after=int(quantity),
        formula_id='feudal_tribute.inventory_share_transfer.v1',
        inputs={'operation_id': operation_id, 'transfer_contract': contract,
                'tribute_rate': float(plot.tribute_rate),
                'plot_fraction': float(plot.fraction),
                'force_present': bool(force_present),
                'protest_energy': float(protest_energy),
                'serf_hungry_steps': int(getattr(serf, 'hungry_steps', 0)),
                'protected_food_reserve': 4 if good == Goods.food else 0})
    return event_id


def _record_withheld_tribute(region, t, plot, lord, assigned, *, reason,
                             force_present, protest_energy, hungry_serfs=None):
    from run_trace import emit
    return emit(
        region, kind='feudal_tribute_withheld', record_class='outcome',
        phase='economy',
        subject={'type': 'tile', 'id': region.name, 'plot_id': plot.plot_id,
                 'lord_id': lord.id},
        metric_id='goods.feudal_tribute', unit='units', before=0, after=0,
        formula_id='feudal_tribute.collection_gate.v1',
        inputs={'turn': int(t), 'plot_fraction': float(plot.fraction),
                'tribute_rate': float(plot.tribute_rate),
                'assigned_serf_ids': [serf.id for serf in assigned],
                'hungry_serf_ids': list(hungry_serfs or []),
                'force_present': bool(force_present),
                'protest_energy': float(protest_energy), 'reason': reason})


def collect_tribute(region, t: int, *, return_trace=False) -> dict:
    """Lords collect in-kind tribute from serfs on their feudal plots.

    For each FEUDAL plot:
    - Identify serfs assigned to this lord based on plot fraction.
    - Transfer tribute_rate fraction of their output/surplus to the lord.
    - Strictly conserved: serf inventory -> lord inventory.

    Returns: {lord_id: {good: amount_collected}}
    """
    tenure = getattr(region, 'tenure', None)
    if tenure is None or not tenure.plots:
        return ({}, []) if return_trace else {}

    # Identify all active serfs/workers (not lords, traders, or government)
    serfs = [a for a in region.agents
             if not a.is_trader and not a.is_government
             and not getattr(a, 'is_lord', False)
             and a.alive]

    if not serfs:
        return ({}, []) if return_trace else {}

    results = {}
    transfer_event_ids = []
    serfs_count = len(serfs)
    current_idx = 0

    for plot in tenure.plots:
        if plot.tenure != TenureStatus.FEUDAL or plot.tribute_rate <= 0:
            continue

        lord = _find_agent(region, plot.lord_id)
        if lord is None or not lord.alive:
            continue

        # Each lord claims a proportional slice of serfs
        slice_size = max(1, int(serfs_count * plot.fraction))
        assigned = serfs[current_idx:current_idx + slice_size]
        current_idx = (current_idx + slice_size) % serfs_count

        # Coercive force check for in-kind tribute extraction:
        # If serfs are militant and landlord/crown lacks armed retainers or garrison, serfs withhold tribute
        pe = region.protest_energy_log[-1] if (hasattr(region, 'protest_energy_log') and region.protest_energy_log) else 0.0
        has_force = any(getattr(u, 'strength', 0) > 5.0 for u in getattr(region, 'military_units', [])) or \
                    getattr(region, 'police_employed', 0) > 0 or getattr(lord, 'cash', 0.0) >= 10.0

        if pe >= 4.5 and not has_force:
            # Serfs in open resistance withhold tribute!
            for serf in assigned:
                serf.mem_push('mem_promises', 0.5)
            _record_withheld_tribute(
                region, t, plot, lord, assigned,
                reason='open_resistance_without_armed_enforcement',
                force_present=has_force, protest_energy=pe)
            continue

        collected = {}
        hungry_withheld = []
        for serf in assigned:
            # Hungry serfs withhold food unless forced
            if serf.hungry_steps > 0 and not has_force:
                hungry_withheld.append(serf.id)
                continue

            # For food: protect 4 subsistence food from tribute
            food_held = serf.inv_get(Goods.food, 0)
            if food_held > 4:
                taxable_food = food_held - 4
                tribute_food = int(taxable_food * plot.tribute_rate)
                if tribute_food > 0:
                    event_id = _transfer_tribute(
                        region, t, plot, serf, lord, Goods.food, tribute_food,
                        force_present=has_force, protest_energy=pe)
                    if event_id is not None:
                        transfer_event_ids.append(event_id)
                    collected[Goods.food] = collected.get(Goods.food, 0) + tribute_food

            # For wood and furniture: collect tribute on total held
            for good in (Goods.wood, Goods.furniture):
                held = serf.inv_get(good, 0)
                if held > 0:
                    tribute = int(held * plot.tribute_rate)
                    if tribute > 0:
                        event_id = _transfer_tribute(
                            region, t, plot, serf, lord, good, tribute,
                            force_present=has_force, protest_energy=pe)
                        if event_id is not None:
                            transfer_event_ids.append(event_id)
                        collected[good] = collected.get(good, 0) + tribute

        if collected:
            results[plot.lord_id] = collected
        else:
            reason = ('subsistence_protected_or_no_surplus'
                      if not hungry_withheld else 'hungry_serfs_withheld')
            _record_withheld_tribute(
                region, t, plot, lord, assigned, reason=reason,
                force_present=has_force, protest_energy=pe,
                hungry_serfs=hungry_withheld)

    if return_trace:
        return results, transfer_event_ids
    return results


def record_tribute_value(region, t, tribute_data, cause_event_ids=None):
    """Value the in-kind tribute log using the same prices as the legacy series."""
    valuations = []
    total = 0.0
    for lord_id, goods_dict in tribute_data.items():
        for good, quantity in goods_dict.items():
            price = (region.food_price if good == Goods.food
                     else region.recipes.get(good, {}).get('price', 2.0))
            value = float(quantity) * float(price)
            total += value
            valuations.append({'lord_id': lord_id, 'good': good.name,
                               'quantity': int(quantity), 'reference_price': float(price),
                               'reference_value': value})
    from run_trace import emit
    currency = getattr(region, 'home_currency', None) or 'local_currency'
    event_id = emit(
        region, kind='feudal_tribute_reference_valuation',
        record_class='calculation', phase='economy',
        subject={'type': 'tile', 'id': region.name},
        metric_id='finance.tribute_value', unit=currency, before=0.0,
        after=float(total),
        formula_id='feudal_tribute.reference_valuation.v1',
        inputs={'turn': int(t), 'currency': currency,
                'valuation_basis': 'region.food_price for food; recipe price for other goods; 2.0 fallback',
                'valuations': valuations},
        cause_event_ids=cause_event_ids or None)
    return total, event_id
