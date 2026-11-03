"""Read-only crop-based supply, household access, and support capacity."""
from __future__ import annotations
from goods import Goods
from nutrition import basic_food_units
from households import human, food
from food_accounts import stocks


def snapshot(region):
    from agriculture import expected_harvest, phase, turns_until_harvest, SEED_PER_AREA
    from career_transitions import profession, working_adult
    from foraging import capacity, potential
    from food_access import food_surplus
    people = [a for a in region.agents if human(a)]
    civilians = [a for a in people if not getattr(a, 'military_unit_id', None)]
    turn = int(getattr(region, '_last_turn', 0))
    price = max(.01, region.recipes.get(Goods.food, {}).get('price', 1))
    need = sum(basic_food_units(a) for a in people)
    farmers = [a for a in people if working_adult(a, turn) and profession(a) == Goods.food]
    farm_need = sum(basic_food_units(a) for a in farmers)
    holdings = stocks(region)
    history = list(getattr(region, 'food_history', ()))
    window = history[-10:]
    harvest = sum(r['farm_production'] for r in window)
    seed = sum(r['seed_use'] for r in window)
    losses = sum(r['losses'] for r in window)
    ordinary = sum(r['ordinary_need'] for r in window)
    elapsed = len(window)
    net_farm = max(0, harvest - seed - losses)
    adult_capacity = net_farm / (4 * elapsed) if elapsed >= 10 else None
    bank = getattr(region, 'bank', None)
    def spendable(a):
        deposits = bank.deposits.get(a, 0) if bank and not getattr(bank, 'is_frozen', False) else 0
        return max(0, a.cash) + max(0, deposits)
    gaps = {a.id: max(0, basic_food_units(a) - food(a)) for a in civilians}
    affordable = {a.id: min(gaps[a.id], spendable(a) / price) for a in civilians}
    missing = sum(gaps.values())
    underfed = sum(getattr(a, 'food_consumed_turn', None) is not None
                   and a.last_calories_eaten + .5 < basic_food_units(a) * 500 for a in civilians)
    farms = getattr(region, 'farms', {})
    actors = {a.id: a for a in region.agents if a.alive}
    from agriculture import can_operate
    active = [f for f in farms.values() if f['operator_id'] in actors and
              (can_operate(region, f, actors[f['operator_id']]) or (f.get('crop') and not f['crop']['closed']))]
    expected = sum(expected_harvest(region, f, turn) for f in active)
    commons = sum(potential(a, region) for a in civilians)
    incoming = [s for p in getattr(getattr(region, 'owner_nation', None), 'provinces', ())
                for s in getattr(p, 'food_shipments', ()) if s.get('destination') == region.name]
    # Report a farm-only central path and the explicit potential commons path.
    # Potential gathering is never silently treated as grain already in storage.
    until = turns_until_harvest(region)
    horizon = until + 10
    central = holdings['total'] - holdings['cargo']
    with_commons = central
    series = []
    from agriculture import staff_capacity, work_productivity
    from food_inventory import milli
    schedules = {}
    for farm in active:
        crop = farm.get('crop')
        committed = bool(crop and not crop['closed'])
        # Keep this crop's receipts separate from a conditional future planting.
        # Each harvest window uses its feasible cumulative harvest work.
        labor = staff_capacity(region, farm, turn) * work_productivity(region, actors[farm['operator_id']], 'harvest')
        remaining = expected_harvest(region, farm, turn)
        area = crop['planted_area'] if committed else farm['area']
        done = crop['harvest_work'] if committed else 0
        harvested = crop['harvested'] if committed else 0
        upcoming = [dt for dt in range(1, horizon + 1) if phase(region, turn + dt) in (6, 7)]
        current_epoch = crop['epoch'] if committed else None
        for epoch in sorted({(turn + dt + int(getattr(region, 'seasonal_phase_offset', 0))) // 10 for dt in upcoming}):
            windows = [dt for dt in upcoming if (turn + dt + int(getattr(region, 'seasonal_phase_offset', 0))) // 10 == epoch]
            is_current = committed and epoch == current_epoch
            projected = remaining if is_current else expected_harvest(region, {**farm, 'crop': None}, turn)
            worked = done if is_current else 0
            prior = harvested if is_current else 0
            final_fraction = min(1, (worked + labor * len(windows)) / max(.001, area * 1.5))
            crop_potential = (projected + prior) / final_fraction if final_fraction > 0 else 0
            for dt in windows:
                worked += labor
                receipt = max(0, milli(crop_potential * min(1, worked / max(.001, area * 1.5)) - prior)) / 1000
                prior += receipt
                row = schedules.setdefault(dt, {'committed': 0.0, 'planned': 0.0})
                row['committed' if is_current else 'planned'] += receipt
    adverse = central
    for dt in range(1, horizon + 1):
        future = turn + dt
        arrivals = sum(s['units'] for s in incoming if s['arrival_turn'] == future)
        receipts = schedules.get(dt, {})
        committed_receipt, planned_receipt = receipts.get('committed', 0), receipts.get('planned', 0)
        receipt = committed_receipt + planned_receipt
        future_need = sum((2 if a.age(future) < 5 else 3 if a.age(future) < 14 else 4)
                          if getattr(a, 'is_native_child', False) else basic_food_units(a) for a in people)
        seed_use = sum(f['area'] * SEED_PER_AREA for f in active) if phase(region, future) == 0 else 0
        loss = max(0, central) * .001
        central += receipt + arrivals - future_need - seed_use - loss
        adverse += .7 * receipt + arrivals - future_need - seed_use - max(0, adverse) * .001
        with_commons += receipt + arrivals - future_need - seed_use - max(0, with_commons) * .001 + min(commons, future_need)
        series.append({'turn': future, 'phase': phase(region, future),
                       'harvest': round(receipt, 3), 'committed_harvest': round(committed_receipt, 3),
                       'conditional_planned_harvest': round(planned_receipt, 3), 'arrivals': arrivals,
                       'ordinary_need': future_need, 'seed_use': seed_use,
                       'closing_stock': round(central, 3), 'adverse_closing_stock': round(adverse, 3),
                       'with_potential_commons': round(with_commons, 3)})
    first_gap = next((r['turn'] for r in series if r['closing_stock'] < -.001), None)
    shortage = any(r['with_potential_commons'] < -.001 for r in series[:until])
    access = underfed > 0 or any(getattr(a, 'calorie_deficit_kcal', 0) > 0 for a in civilians) or any(gaps[a.id] > affordable[a.id] + potential(a, region) for a in civilians)
    diagnosis = 'shortage_and_access' if shortage and access else 'shortage' if shortage else 'access' if access else 'stable'
    offered = sum(food_surplus(a, region) for a in region.agents)
    reasons = []
    if any(gaps[a.id] > affordable[a.id] + potential(a, region) for a in civilians):
        reasons.append('Households cannot afford the next meal')
    if missing > offered + commons:
        reasons.append('Insufficient reachable offers for the next meal')
    if holdings['granary'] and not getattr(region.gov, 'emergency_food_policy', False):
        reasons.append('Emergency release disabled')
    if first_gap is not None:
        reasons.append(f'Projected reserve gap at turn {first_gap}')
    if not reasons:
        reasons.append('Current meals covered')
    current_work = getattr(region, 'work_allocations', {}).get('people', {})
    effective = sum(sum(value for key, value in row['activities'].items() if key in farms)
                    for row in current_work.values())
    latest = window[-1] if window else {}
    minimum_path = min((r['closing_stock'] for r in series), default=holdings['total'])
    return {
        'tile': region.name, 'residents': len(civilians), 'food_producers': len(farmers),
        'minimum_meal_units': need, 'household_food_units': sum(food(a) for a in civilians),
        'forecast_commons_food_units': commons, 'government_food_units': holdings['aid'],
        'missing_meal_units': missing, 'recent_food_production': latest.get('farm_production', 0),
        'crop_cycle_turns': 10, 'observed_crop_cycle_turns': elapsed,
        'crop_cycle_production': harvest, 'crop_cycle_meal_demand': ordinary,
        'accessible_food_buffer': sum(food(a) for a in civilians) + holdings['aid'],
        'projected_crop_cycle_margin': minimum_path,
        'forecast_commons_cycle_food': commons * 10,
        'projected_crop_cycle_margin_with_commons': min((r['with_potential_commons'] for r in series), default=0),
        'food_buffer_proven': elapsed >= 10 and minimum_path >= need and underfed == 0,
        'enclosure_risk': any(r['closing_stock'] < need for r in series),
        'projected_supply_gap': max(0, -minimum_path),
        'underfed_residents': underfed, 'underfed_share': underfed / max(1, len(civilians)),
        'diagnosis': diagnosis, 'emergency': underfed > 0 or shortage,
        'production_units_last_turn': latest.get('farm_production', 0),
        'foraged_units_last_turn': latest.get('commons_production', getattr(region, 'food_foraged_this_turn', 0)),
        'unmet_calorie_units_last_turn': sum(a.calorie_deficit_kcal for a in civilians) / 500,
        'company_food_units': sum(a.inv_get(Goods.food, 0) for a in region.agents if a.is_corporation),
        'food_available_for_sale': offered, 'granary_food_units': holdings['granary'],
        'food_in_transit': sum(s['units'] for s in incoming),
        'meal_reference_cost': 4 * price,
        'unaffordable_residents': sum(gaps[a.id] > affordable[a.id] + .001 for a in civilians),
        'relief_policy': 'emergency' if getattr(region.gov, 'emergency_food_policy', False) else 'ordinary',
        'access_reasons': reasons, 'granary_release': dict(getattr(region, 'granary_release_status', {})),
        'phase': phase(region), 'turns_until_harvest': until, 'expected_harvest': expected,
        'adverse_harvest': expected * .7, 'stock_path': series, 'first_projected_gap': first_gap,
        'stocks': holdings, 'latest_turn': latest, 'primary_farmers': len(farmers),
        'effective_farm_work': effective, 'farm_support_adult_equivalents': adult_capacity,
        'resident_adult_equivalents': need / 4,
        'farmer_adult_equivalents': farm_need / 4,
        'other_resident_adult_equivalents': (need - farm_need) / 4,
        'support_for_others': None if adult_capacity is None else max(0, adult_capacity - farm_need / 4),
        'farmers_own_support_gap': None if adult_capacity is None else max(0, farm_need / 4 - adult_capacity),
        'support_window_turns': elapsed, 'production_margin': None if not elapsed else (net_farm - ordinary) / elapsed,
        'initialization': getattr(region, 'food_initialization', None),
    }


def close_turn(region, turn):
    if getattr(region, '_food_closed_turn', None) == turn:
        return
    region._food_closed_turn = turn
    from food_accounts import state
    events = [r for r in state(region)['events'] if r['turn'] == turn]
    need = sum(basic_food_units(a) for a in region.agents if human(a))
    row = {'turn': turn, 'phase': __import__('agriculture').phase(region),
           'farm_production': sum(r['units'] for r in events if r['kind'] == 'harvest'),
           'commons_production': sum(r['units'] for r in events if r['kind'] == 'commons_gathering'),
           'seed_use': sum(r['units'] for r in events if r['kind'] == 'seed_use'),
           'losses': sum(r['units'] for r in events if r['kind'] == 'storage_loss'),
           'ordinary_need': getattr(region, 'food_turn_need', need),
           'meals_consumed': sum(r['units'] for r in events if r['kind'] == 'meal'),
           'closing_stock': stocks(region)['total']}
    history = getattr(region, 'food_history', [])
    row['stock_change'] = row['closing_stock'] - (history[-1]['closing_stock'] if history else
                                               getattr(region, '_food_opening_stock', row['closing_stock']))
    row['production_margin'] = row['farm_production'] + row['commons_production'] - need - row['seed_use'] - row['losses']
    history.append(row)
    region.food_history = history[-300:]
