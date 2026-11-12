"""
Feudal tribute — lords collect a share of serf production in kind.

Under feudalism, serfs owe the lord a portion of their harvest
(tribute_rate, default 50%). This is NOT cash rent — it is grain,
wood, and goods transferred directly into the lord's inventory.
The lord does not need money to eat; tribute feeds the lord's household
and gives the lord surplus goods to sell at market.

New production accrues until late harvest (phase 7 of the ten-turn cycle).
Previously held reserves, purchases, and relief do not create a new tax base.
Estate owners also supply basic meals to hungry residents before consumption.
"""

from goods import Goods
from land_tenure import TenureStatus
from game_time import seasonal_cycle_phase


TRIBUTE_COLLECTION_PHASE = 7
TRIBUTE_GOODS = (Goods.food, Goods.wood, Goods.furniture)


def estate_residents(region, residents=None):
    """Resolve actual local residence; never allocate people by a shuffled slice.

    Explicit plot assignments take priority over legacy tenant lists. Children
    and unassigned descendants retain their local family residence. A move to
    another named plot overrides the family link.
    """
    plots = {p.plot_id: p for p in getattr(getattr(region, 'tenure', None), 'plots', ())
             if p.tenure != TenureStatus.COMMONS}
    present = list(getattr(region, 'agents', ()) if residents is None else residents)
    memberships = {}
    for plot_id in sorted(plots):
        for ident in plots[plot_id].tenant_ids:
            memberships.setdefault(ident, plot_id)
    result = {plot_id: [] for plot_id in plots}
    for person in sorted(present, key=lambda a: a.id):
        if (not person.alive or person.is_government or person.is_corporation
                or person.is_trader or getattr(person, 'is_lord', False)
                or getattr(person, 'military_unit_id', None)):
            continue
        owner = person
        seen = set()
        while owner is not None and id(owner) not in seen:
            seen.add(id(owner))
            if owner is not person and getattr(owner, 'region', None) != getattr(region, 'name', None):
                break
            explicit = getattr(owner, 'assigned_plot_id', None)
            plot_id = explicit if explicit is not None else memberships.get(owner.id)
            if plot_id is not None:
                if plot_id in result:
                    result[plot_id].append(person)
                break
            owner = getattr(owner, 'parent', None)
    return result


def _accrue_harvest(region, t, assignments):
    """Read completed production receipts once; never infer income from stock."""
    if getattr(region, '_feudal_harvest_observed_turn', None) == t:
        return
    region._feudal_harvest_observed_turn = t
    from harvest_claims import register
    register(region, t)
    book = getattr(region, 'feudal_harvest_accruals', {})
    plots = {p.plot_id: p for p in region.tenure.plots}
    for plot_id in list(book):
        if plot_id not in plots or plots[plot_id].tenure != TenureStatus.FEUDAL:
            del book[plot_id]
    home = {a.id: plot_id for plot_id, people in assignments.items()
            if plots[plot_id].tenure == TenureStatus.FEUDAL for a in people}
    for receipt in getattr(region, 'production_receipts', ()):
        if receipt.get('turn') != t or receipt.get('good') not in TRIBUTE_GOODS:
            continue
        plot_id = home.get(receipt['person_id'])
        units = max(0, int(receipt['quantity']))
        if plot_id is None or units == 0:
            continue
        account = book.setdefault(plot_id, {}).setdefault(str(receipt['person_id']), {})
        key = receipt['good'].name
        account[key] = account.get(key, 0) + units
    region.feudal_harvest_accruals = book


def _transfer_tribute(region, t, plot, serf, lord, good, quantity, *,
                      force_present, protest_energy, assessment):
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
                **assessment,
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
        formula_id='feudal_tribute.harvest_share_transfer.v2',
        inputs={'operation_id': operation_id, 'transfer_contract': contract,
                'tribute_rate': float(plot.tribute_rate),
                'plot_fraction': float(plot.fraction),
                'force_present': bool(force_present),
                'protest_energy': float(protest_energy),
                'serf_hungry_steps': int(getattr(serf, 'hungry_steps', 0)),
                **assessment})
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
    """Collect once per harvest cycle, based only on newly produced goods."""
    tenure = getattr(region, 'tenure', None)
    if tenure is None or not tenure.plots:
        return ({}, []) if return_trace else {}

    assignments = estate_residents(region)
    _accrue_harvest(region, t, assignments)
    if (seasonal_cycle_phase(t, region) != TRIBUTE_COLLECTION_PHASE
            or getattr(region, '_feudal_tribute_collection_turn', None) == t):
        return ({}, []) if return_trace else {}
    region._feudal_tribute_collection_turn = t
    # A settled assessment is closed, including any unaffordable share. It is
    # never turned into a second tax on reserves in the following cycle.
    assessments = region.feudal_harvest_accruals
    region.feudal_harvest_accruals = {}

    results = {}
    transfer_event_ids = []
    people = {a.id: a for a in region.agents if a.alive}

    for plot in tenure.plots:
        if plot.tenure != TenureStatus.FEUDAL or plot.tribute_rate <= 0:
            continue

        lord = people.get(plot.lord_id)
        if lord is None:
            continue

        harvests = assessments.get(plot.plot_id, {})
        assigned = [people[int(ident)] for ident in sorted(harvests, key=int)
                    if int(ident) in people]

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

            from food_access import protected_food
            from run_trace import emit
            for good in TRIBUTE_GOODS:
                new_harvest = int(harvests[str(serf.id)].get(good.name, 0))
                due = int(new_harvest * max(0, min(1, plot.tribute_rate)))
                reserve = int(protected_food(serf, region)) if good == Goods.food else 0
                held = int(serf.inv_get(good, 0))
                from harvest_claims import available as claimable_harvest
                tribute = int(min(due, claimable_harvest(region, serf, good, t), max(0, held - reserve)))
                assessment = {'new_harvest_units': new_harvest, 'assessed_units': due,
                              'unpaid_units': due-tribute, 'protected_food_reserve': reserve,
                              'collection_phase': TRIBUTE_COLLECTION_PHASE}
                if tribute > 0:
                    event_id = _transfer_tribute(
                        region, t, plot, serf, lord, good, tribute,
                        force_present=has_force, protest_energy=pe, assessment=assessment)
                    if event_id is not None:
                        transfer_event_ids.append(event_id)
                    collected[good] = collected.get(good, 0) + tribute
                if due > tribute:
                    emit(region, kind='feudal_tribute_unpaid', record_class='outcome', phase='economy',
                         subject={'type': 'tile', 'id': region.name, 'plot_id': plot.plot_id,
                                  'serf_id': serf.id, 'lord_id': lord.id, 'good': good.name},
                         metric_id='goods.feudal_tribute_unpaid', unit='units', after=due-tribute,
                         inputs={**assessment, 'available_inventory': held,
                                 'reason': 'household_reserve_or_insufficient_goods',
                                 'arrears_created': False})

        if collected:
            destination = results.setdefault(plot.lord_id, {})
            for good, units in collected.items():
                destination[good] = destination.get(good, 0) + units
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


def feed_estate_residents(region, t, residents=None):
    """Owners protect their workforce with real grain before anyone eats.

    Relief covers basic calories, not luxury appetite. It is a physical gift,
    not a loan or a wage. Each owner keeps a basic meal for their own household.
    """
    if region is None or getattr(region, '_estate_food_relief_turn', None) == t:
        return 0
    region._estate_food_relief_turn = t
    from nutrition import basic_food_units
    from food_access import prepared_food_units
    from economy.actor_accounts import record
    from run_trace import emit

    present = list(getattr(region, 'agents', ()) if residents is None else residents)
    by_id = {a.id: a for a in present if a.alive}
    plots = {p.plot_id: p for p in getattr(getattr(region, 'tenure', None), 'plots', ())}
    assignments = estate_residents(region, present)

    def gap(person):
        return max(0, basic_food_units(person) - max(0, int(person.inv_get(Goods.food, 0)))
                   - prepared_food_units(person) - max(0, int(getattr(person, 'emergency_food_units', 0))))

    # One owner may hold several plots. Allocate their common stock to the
    # neediest actual residents across all of those plots, without duplication.
    estates = {}
    for plot_id, people in assignments.items():
        owner_id = plots[plot_id].lord_id
        estates.setdefault(owner_id, {}).update({a.id: (a, plot_id) for a in people})
    total = 0
    recipients = 0
    for owner_id in sorted(estates):
        lord = by_id.get(owner_id)
        if lord is None or lord.is_government or lord.is_corporation:
            continue
        own_meal = max(0, basic_food_units(lord) - prepared_food_units(lord)
                       - max(0, int(getattr(lord, 'emergency_food_units', 0))))
        dependents = [a for a in present if a.alive and getattr(a, 'parent', None) is lord
                      and getattr(a, 'is_native_child', False) and a.age(t) < 14]
        reserve = own_meal + sum(gap(child) for child in dependents)
        ordered = sorted(estates[owner_id].values(), key=lambda row: (
            float(getattr(row[0], 'energy_reserve_kcal', 40000))
            / max(1, float(getattr(row[0], 'calorie_need_kcal', 2000))),
            -float(getattr(row[0], 'hungry_steps', 0)), row[0].id))
        for person, plot_id in ordered:
            missing = gap(person)
            donor_before = int(lord.inv_get(Goods.food, 0))
            units = min(missing, max(0, donor_before - reserve))
            if units <= 0:
                continue
            before = int(person.inv_get(Goods.food, 0))
            lord.inv_add(Goods.food, -units)
            person.inv_add(Goods.food, units)
            operation_id = f'estate-food:{region.name}:{int(t)}:{owner_id}:{person.id}'
            contract = {
                'contract_version': 'goods_transfer.v1', 'operation_id': operation_id,
                'operation_type': 'estate_subsistence_relief', 'good': 'food', 'unit': 'food_units',
                'amount': units,
                'payer_account': {'type': 'agent_inventory', 'id': str(owner_id), 'good': 'food',
                                  'balance_before': donor_before, 'balance_after': donor_before-units,
                                  'balance_scope': 'inventory'},
                'payee_account': {'type': 'agent_inventory', 'id': str(person.id), 'good': 'food',
                                  'balance_before': before, 'balance_after': before+units,
                                  'balance_scope': 'inventory'},
                'cash_transfer_status': 'in_kind_no_cash',
                'counterparty_leg_status': 'both_inventory_balances_captured'}
            record(region, 'estate_food_relief', turn=t, payer_id=owner_id, recipient_id=person.id,
                   good=Goods.food, quantity=units, asset_id=plot_id, source_id=operation_id)
            emit(region, kind='estate_food_relief', record_class='transfer', phase='demographics',
                 subject={'type': 'tile', 'id': region.name, 'plot_id': plot_id,
                          'lord_id': owner_id, 'recipient_id': person.id, 'good': 'food'},
                 metric_id='goods.estate_food_relief', unit='food_units', before=0, after=units,
                 formula_id='feudal_tribute.estate_relief.v1',
                 inputs={'turn': int(t), 'operation_id': operation_id, 'basic_meal_gap': missing,
                         'donor_household_reserve': reserve, 'donor_inventory_before': donor_before,
                         'transfer_contract': contract})
            total += units
            recipients += 1
    region.estate_food_relief_units = total
    region.estate_food_relief_recipients = recipients
    return total


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
