"""
Production engine (firm and independent production) with Cython acceleration.
"""

from economy import production_math
from collections import defaultdict
from goods import Goods
from random_cache import rand
from labor_contract import calculate_shift_multiplier, calculate_work_effort, ensure_labor_agreement, record_surplus_value
from engineering import record_operation, production_work_share
from soil_dynamics import SOIL_DEGRADATION_SCALE

try:
    import region_core as _c
except ImportError:
    _c = None


import math

def season_mult(t: int | None) -> float:
    """Ten-phase seasonal productivity curve, separate from agent age years."""
    if t is None:
        return 1.0
    from game_time import seasonal_cycle_phase
    year_turn = seasonal_cycle_phase(t)
    # Peak at autumn harvest (t%10 == 4-6), trough at winter (t%10 == 9, 0)
    return max(0.45, 1.0 + 0.45 * math.sin(2.0 * math.pi * (year_turn - 2) / 10.0))


def terrain_bonus(region, good, t: int | None = None, producer=None):
    """Production multiplier from terrain and installed buildings for *good* (default 1.0)."""
    base = region.terrain.get(good, 1.0)
    mult = 1.0
    for b in getattr(region, 'buildings', []):
        from technology_adoption import applies_to_producer
        if not applies_to_producer(b, producer):
            continue
        bonuses = getattr(b, 'production_bonuses', {})
        if good in bonuses:
            mult *= bonuses[good]

    if good in (Goods.food, Goods.cotton, Goods.sugar, Goods.tobacco):
        from supply_rights import water_yield_factor
        mult *= water_yield_factor(region, producer)

    if good == Goods.food:
        from agriculture import yield_factor
        return yield_factor(region, producer, t if t is not None else getattr(region, '_last_turn', 0))

    # P3: Clover / Turnip Pasture Synergy for Wool
    if good == Goods.wool:
        regime = getattr(region, 'farming_regime', 'rotation')
        if regime == 'rotation':
            mult *= 1.35  # Clover forage boosts livestock health and fleece weight by +35%

    return base * mult


def _record_zero_production(region, agent, output, *, kind, formula_id,
                            reason, inputs, receipt_ids=None,
                            cause_event_ids=None):
    from run_trace import emit

    event_id = emit(
        region, kind=kind, record_class='outcome',
        subject={'type': 'agent', 'id': agent.id, 'tile': region.name,
                 'good': output.name},
        metric_id='goods.production', unit='units', before=0, after=0,
        formula_id=formula_id, cause_event_ids=cause_event_ids,
        inputs={'reason': reason, 'agent_id': agent.id,
                'output_good': output.name, **inputs})
    if receipt_ids is not None and event_id is not None:
        receipt_ids.append(event_id)
    return event_id


def _food_conversion(region, agent, recipe, inputs_used, output, units):
    if recipe.get('input') in (Goods.food, Goods.prepared_food) and inputs_used:
        loss = inputs_used - (units if output in (Goods.food, Goods.prepared_food) else 0)
        if loss > 0:
            from food_accounts import record
            record(region, 'food_processing_loss', loss, source=agent, good=recipe['input'])


def produce_corporation(region, agent, recipe, output, num_agents_per_good,
                        local_total_production, receipt_ids=None, turn=None):
    """Run production logic for a corporate employer."""
    if output == Goods.food:
        raise ValueError('Food production requires the persistent crop phase')
    from abundance import enabled as workshops_enabled
    if workshops_enabled(region) and recipe.get('setup_good') and recipe.get('numInput', 0) > 0:
        from abundance import produce_workshop
        produce_workshop(region, agent, recipe, local_total_production,
                         receipt_ids if receipt_ids is not None else [],
                         turn if turn is not None else getattr(region, '_last_turn', 0))
        return
    # P2.3: Striking or revolting workers withhold living labor power
    working_employees = [e for e in agent.employees if not getattr(e, 'is_striking', False) and not getattr(e, 'in_revolt', False)
                         and e.id not in getattr(region, 'pollution_revolt_ids', set())]
    num_employees = len(working_employees)
    workforce_event_id = getattr(region, '_labor_workforce_event_ids', {}).get(agent.id)
    workforce_causes = ([workforce_event_id]
                        if workforce_event_id is not None else None)
    if num_employees == 0:
        _record_zero_production(
            region, agent, output, kind='firm_production_zero',
            formula_id='production.corporation_zero.v1',
            reason=('no_employees' if not agent.employees else
                    'all_employees_withheld_or_revolting'),
            receipt_ids=receipt_ids, cause_event_ids=workforce_causes,
            inputs={'employees': len(agent.employees), 'working_employees': 0,
                    'employee_ids': [employee.id for employee in agent.employees],
                    'striking_employee_ids': [employee.id for employee in agent.employees
                                              if getattr(employee, 'is_striking', False)],
                    'revolting_employee_ids': [employee.id for employee in agent.employees
                                               if (getattr(employee, 'in_revolt', False)
                                                               or employee.id in getattr(region, 'pollution_revolt_ids', set()))],
                    'workforce_event_id': workforce_event_id})
        return
    max_inventory = recipe['maxinv'] * (1 + len(agent.employees))
    if agent.inv_get(output, 0) / max_inventory >= 1:
        return
    active_slots = production_math.active_slots(num_employees,
        agent.inv_get(recipe.get('input'), 0) if recipe.get('numInput', 0) > 0 else 0,
        recipe.get('numInput', 0))
    if active_slots <= 0 or recipe.get('production', 0) <= 0:
        return
    synergy = 1.0 + (0.15 if num_employees < 4 else 0.20 if num_employees < 8 else 0.25 if num_employees < 12 else 0.30) * num_employees
    base_production = recipe['production']

    # P2.1: Shift length multiplier and machinery capacity
    effort_factors = []
    for employee in working_employees:
        agreement = ensure_labor_agreement(employee, agent, getattr(region, '_last_turn', 0))
        fatigue = float(getattr(employee, 'work_fatigue', 0.0))
        nutrition = 1.0  # health/nutrition are already in the shared work budget
        effort_factors.append(calculate_work_effort(agreement.hours, agreement.pace,
                                                    nutrition, fatigue))
        employee.work_fatigue = max(0.0, fatigue + max(0.0, agreement.hours - 8.0) * 0.025
                                    + max(0.0, agreement.pace - 1.0) * 0.20 - 0.05)
        employee.workplace_accident = agreement.hours >= 14.0 or agreement.pace >= 1.75
    from work_allocation import main_work
    effort_factors = [effort * main_work(region, person, turn, default=1)
                      for effort, person in zip(effort_factors, working_employees)]
    shift_mult = sum(effort_factors) / len(effort_factors) if effort_factors else calculate_shift_multiplier(getattr(agent, 'shift_hours', 8.0))
    terrain_mult = terrain_bonus(region, output, producer=agent)
    from abundance import enabled, proficiency, learn
    practice_mult = (sum(proficiency(e, output) for e in working_employees) / num_employees
                     if enabled(region) else 1.0)
    machinery = getattr(agent, 'machinery_level', 1)
    broken = getattr(agent, 'broken_machinery', 0)
    working_machinery = max(0, machinery - broken)
    production_per_slot = production_math.production_per_slot(
        base_production, num_employees, terrain_mult, shift_mult, practice_mult, working_machinery)
    resource_factor = (min(1.0, recipe['maxtotalprod'] / max(1, num_agents_per_good[output]) / base_production)
                       if output in (Goods.food, Goods.wood) else 1.0)
    chance = production_math.success_probability(agent.hungry_steps, agent.inv_get(output, 0),
                                                  max_inventory, resource_factor)
    vals = rand.random_n(active_slots)
    if _c is not None:
        successful_slots = _c.produce_corporation_slots(active_slots, chance, vals)
    else:
        successful_slots = sum(1 for v in vals if v < chance)
    if successful_slots:
        if production_math.output_units(successful_slots, production_per_slot) <= 0:
            return
        inputs_cost = 0.0
        inputs_used = 0
        input_price = 0.0
        recorded_basis = None
        input_inventory_before = (agent.inv_get(recipe['input'], 0)
                                  if recipe.get('numInput', 0) > 0 else None)
        if recipe.get('numInput', 0) > 0:
            inputs_used = successful_slots * recipe['numInput']
            recorded_basis = max(0.0, float(agent.cost_get(recipe['input'], 0)))
            agent.inv_add(recipe['input'], -inputs_used)
            input_price = region.recipes.get(recipe['input'], {}).get('price', 1.0)
            inputs_cost = inputs_used * input_price
            from economy.actor_accounts import record as record_economic_event
            record_economic_event(region, 'input_consumed', payer_id=agent.id,
                                  good=recipe['input'], quantity=inputs_used,
                                  amount=inputs_used * recorded_basis,
                                  detail={'cost_basis_known': recorded_basis > 0})
        num_output = production_math.output_units(successful_slots, production_per_slot)
        if output == Goods.prepared_food:
            num_output = min(num_output, inputs_used)
        _food_conversion(region, agent, recipe, inputs_used, output, num_output)
        inventory_before = agent.inv_get(output, 0)
        agent.inv_add(output, num_output)
        from economy.actor_accounts import record as record_economic_event
        record_economic_event(region, 'production', recipient_id=agent.id,
                              good=output, quantity=num_output)
        local_total_production[output] = local_total_production.get(output, 0) + num_output
        from run_trace import emit
        event_id = emit(region, kind='firm_production', record_class='outcome',
                        subject={'type': 'agent', 'id': agent.id, 'tile': region.name,
                                 'good': output.name},
                        metric_id='goods.production', unit='units', before=0,
                        after=num_output, formula_id='production.corporation.v1',
                        cause_event_ids=workforce_causes,
                        inputs={'employees': len(agent.employees),
                                'working_employees': num_employees,
                                'working_employee_ids': [employee.id
                                                         for employee in working_employees],
                                'striking_employee_ids': [employee.id
                                                          for employee in agent.employees
                                                          if getattr(employee, 'is_striking', False)],
                                'revolting_employee_ids': [employee.id
                                                           for employee in agent.employees
                                                           if (getattr(employee, 'in_revolt', False)
                                                               or employee.id in getattr(region, 'pollution_revolt_ids', set()))],
                                'active_slots': active_slots, 'successful_slots': successful_slots,
                                'slot_draws': list(vals), 'success_probability': chance,
                                'base_production': base_production, 'synergy': synergy,
                                'practice_multiplier': practice_mult,
                                'terrain_multiplier': terrain_mult,
                                'shift_multiplier': shift_mult,
                                'working_machinery': working_machinery,
                                'production_per_slot': production_per_slot,
                                'inputs_used': inputs_used,
                                'input_good': (recipe['input'].name
                                               if recipe.get('numInput', 0) > 0 else None),
                                'input_quantity_used': inputs_used,
                                'input_inventory_before': input_inventory_before,
                                'input_inventory_after': (
                                    agent.inv_get(recipe['input'], 0)
                                    if recipe.get('numInput', 0) > 0 else None),
                                'workforce_event_id': workforce_event_id,
                                'inventory_before': inventory_before,
                                'inventory_after': agent.inv_get(output, 0)})
        if receipt_ids is not None and event_id is not None:
            receipt_ids.append(event_id)

        record_operation(region, agent, output, successful_slots * shift_mult, 0,
                         turn if turn is not None else getattr(region, '_last_turn', 0), event_id)
        for employee, draw in zip(working_employees, vals):
            if draw < chance:
                learn(region, employee, output, max(0.0, shift_mult),
                      turn if turn is not None else getattr(region, '_last_turn', 0))

        # P2.1: Surplus value extraction accounting (s/v)
        wages_paid = len(agent.employees) * getattr(agent, 'wage', 1.0)
        record_surplus_value(agent, region, output, num_output, inputs_cost,
                             wages_paid, turn=turn,
                             input_good=(recipe.get('input')
                                         if inputs_used > 0 else None),
                             input_units=inputs_used,
                             input_reference_price=input_price,
                             input_inventory_unit_cost_basis=recorded_basis,
                             input_inventory_cost_basis_known=(
                                 recorded_basis > 0.0
                                 if recorded_basis is not None else None))
        compute_and_record_firm_footprint(agent, region, output, num_output,
                                          inputs_cost, wages_paid, cur_turn=turn)
    else:
        if workforce_event_id is not None:
            _record_zero_production(
                region, agent, output, kind='firm_production_zero',
                formula_id='production.corporation_zero.v1',
                reason='all_slots_failed_random_draw', receipt_ids=receipt_ids,
                cause_event_ids=workforce_causes,
                inputs={'employees': len(agent.employees),
                        'working_employees': num_employees,
                        'working_employee_ids': [employee.id
                                                 for employee in working_employees],
                        'active_slots': active_slots, 'slot_draws': list(vals),
                        'success_probability': chance,
                        'base_production': base_production, 'synergy': synergy,
                        'terrain_multiplier': terrain_mult,
                        'shift_multiplier': shift_mult,
                        'working_machinery': working_machinery,
                        'production_per_slot': production_per_slot,
                        'workforce_event_id': workforce_event_id,
                        'inventory_before': agent.inv_get(output, 0),
                        'maximum_inventory': max_inventory})


def compute_and_record_firm_footprint(agent, region, output, num_output, inputs_cost, wages_paid, cur_turn=None):
    """Attribute ecological, health, and sociological footprint directly to producing firm."""
    try:
        from economy.true_cost_ledger import get_true_cost_ledger
        ledger = get_true_cost_ledger()
        if cur_turn is None:
            cur_turn = getattr(region, '_last_turn', 0) or 0

        phys = {}

        regime = getattr(region, 'farming_regime', 'rotation')
        use_fert = (regime == 'intensive' or getattr(region, 'use_fertilizer', False) or
                    getattr(region, 'mandate_fertilizer', False))
        use_pest = getattr(region, 'use_pesticides', False) or getattr(region, 'mandate_pesticides', False)

        # 1. Agricultural emissions
        if output in (Goods.food, Goods.cotton, Goods.sugar, Goods.tobacco):
            if use_fert or regime == 'intensive':
                phys['soil_fertility_loss'] = 0.025 * SOIL_DEGRADATION_SCALE
                phys['water_effluent_discharged'] = 3.5
            elif regime == 'rotation':
                phys['soil_fertility_loss'] = 0.005 * SOIL_DEGRADATION_SCALE
            else:
                phys['soil_fertility_loss'] = 0.015 * SOIL_DEGRADATION_SCALE

            if use_pest:
                phys['soil_toxins_generated'] = 4.0
                if getattr(agent, 'employees', []):
                    phys['labor_health_wear'] = len(agent.employees) * 0.040

        # Use the same output-based flows as regional ecology, for every producer.
        from production_emissions import output_emissions, pollution_controls
        flows = output_emissions(region, output, num_output)
        scrubber, water_factor = pollution_controls(region)
        phys['air_smog_emitted'] = flows['air'] * (0.3 if scrubber else 1.0)
        phys['water_effluent_discharged'] = (flows['industrial_water'] + flows['fertilizer_runoff']) * water_factor
        phys['soil_toxins_generated'] = flows['pesticide_soil'] + (flows['air'] * 0.35 if scrubber else 0.0)

        # 3. Labor contract conditions
        shift_h = getattr(agent, 'shift_hours', 8.0)
        safety_inv = getattr(agent, 'safety_investment', 0.0)
        num_w = len(getattr(agent, 'employees', []))

        if shift_h > 8.0:
            phys['labor_health_wear'] = phys.get('labor_health_wear', 0.0) + num_w * 0.005 * (shift_h - 8.0)
            phys['alienation_despair'] = phys.get('alienation_despair', 0.0) + 0.02 * (shift_h - 8.0)
        if safety_inv < 1.0 and num_w > 0:
            phys['labor_health_wear'] = phys.get('labor_health_wear', 0.0) + num_w * 0.010 * max(0.0, 1.0 - safety_inv)
        if shift_h >= 8.0:
            phys['alienation_despair'] = phys.get('alienation_despair', 0.0) + 0.05 * (shift_h / 8.0)

        c_cost = inputs_cost + (safety_inv * num_w)
        v_cost = wages_paid

        ledger.record_production(agent, region, cur_turn, c_cost, v_cost, phys)
        price = region.recipes.get(output, {}).get('price', 1.0)
        ledger.record_sales(agent, region, cur_turn, num_output * price)
    except Exception:
        pass


def produce_independent(region, agent, recipe, output, num_agents_per_good,
                        local_total_production, receipt_ids=None):
    """Run production logic for an independent sole craftsman."""
    if output == Goods.food:
        raise ValueError('Food production requires the persistent crop phase')
    from abundance import enabled as workshops_enabled
    if workshops_enabled(region) and recipe.get('setup_good') and recipe.get('numInput', 0) > 0:
        from abundance import produce_workshop
        produce_workshop(region, agent, recipe, local_total_production,
                         receipt_ids if receipt_ids is not None else [], getattr(region, '_last_turn', 0))
        return
    trace = getattr(region, '_run_trace', None)
    activity_event_id = (getattr(trace, '_turn_temporary_activity_events', {}).get(
        str(agent.id)) if trace is not None else None)
    activity_causes = ([activity_event_id] if activity_event_id is not None else None)
    engineering_share = production_work_share(agent, getattr(region, '_last_turn', 0))
    engineering_event_id = getattr(agent, 'engineering_work_event_id', None) if engineering_share else None
    if engineering_event_id is not None:
        activity_causes = list(activity_causes or ()) + [engineering_event_id]
    if agent.id in getattr(region, 'pollution_revolt_ids', set()):
        _record_zero_production(region, agent, output, kind='independent_production_zero',
                                formula_id='production.independent_zero.v1',
                                reason='pollution_illness_revolt', receipt_ids=receipt_ids,
                                inputs={'pollution_health_state': region.pollution_health_state})
        return
    max_inventory = recipe['maxinv']
    if agent.inv_get(output, 0) / max_inventory >= 1:
        return
    has_inputs = True
    if recipe['numInput'] > 0 and agent.inv_get(recipe['input'], 0) < recipe['numInput']:
        has_inputs = False
    num_output = 0
    inventory_before = agent.inv_get(output, 0)
    if has_inputs and recipe.get('production', 0) > 0:
        chance = 1.0
        from work_allocation import main_work
        work = main_work(region, agent, getattr(region, '_last_turn', 0))
        chance *= work if work is not None else 1.0
        if output in (Goods.food, Goods.wood):
            chance *= min(1.0, recipe['maxtotalprod'] / max(1, num_agents_per_good[output]) / recipe['production'])
        if (output == Goods.food and getattr(agent, 'assigned_plot_id', None) is None
                and getattr(agent, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0):
            # Evicted cultivators retain their skills but no longer have secure fields.
            chance *= 0.25
        chance *= max(0, 1 - agent.inv_get(output, 0) / max_inventory)
        rand_val = rand.random()
        if _c is not None:
            made = _c.produce_independent_check(chance, rand_val)
        else:
            made = 1 if rand_val < chance else 0
        if made:
            inputs_cost = 0.0
            input_inventory_before = (agent.inv_get(recipe['input'], 0)
                                      if recipe['numInput'] > 0 else None)
            if recipe['numInput'] > 0:
                agent.inv_add(recipe['input'], -recipe['numInput'])
                input_price = region.recipes.get(recipe['input'], {}).get('price', 1.0)
                inputs_cost = recipe['numInput'] * input_price
            terrain_mult = terrain_bonus(region, output, producer=agent)
            from labor_choice import occupational_tenure_multiplier
            cur_turn = int(getattr(region, '_last_turn', 0) or 0)
            tenure_mult = occupational_tenure_multiplier(agent, output, cur_turn)
            from abundance import enabled, proficiency, learn
            practice_mult = proficiency(agent, output) if enabled(region) else 1.0
            num_output = int(round(recipe['production'] * terrain_mult * tenure_mult * practice_mult))
            if output == Goods.prepared_food:
                num_output = min(num_output, recipe['numInput'])
            _food_conversion(region, agent, recipe, recipe['numInput'], output, num_output)
            compute_and_record_firm_footprint(agent, region, output, num_output, inputs_cost, 0.0)
        if made:
            from run_trace import emit
            event_id = emit(region, kind='independent_production', record_class='outcome',
                            subject={'type': 'agent', 'id': agent.id, 'tile': region.name,
                                     'good': output.name},
                            metric_id='goods.production', unit='units', before=0,
                            after=num_output, formula_id='production.independent.v1',
                            cause_event_ids=activity_causes,
                            inputs={'draw': rand_val, 'success_probability': chance,
                                    'temporary_work_share': float(getattr(
                                        agent, 'temporary_work_share', 0.0)),
                                    'engineering_work_share': engineering_share,
                                    'activity_event_id': activity_event_id,
                                    'base_production': recipe['production'],
                                    'terrain_multiplier': terrain_mult,
                                    'tenure_multiplier': tenure_mult,
                                    'practice_multiplier': practice_mult,
                                    'inputs_used': recipe['numInput'] if recipe['numInput'] > 0 else 0,
                                    'input_good': (recipe['input'].name
                                                   if recipe['numInput'] > 0 else None),
                                    'input_quantity_used': (recipe['numInput']
                                                            if recipe['numInput'] > 0 else 0),
                                    'input_inventory_before': input_inventory_before,
                                    'input_inventory_after': (
                                        agent.inv_get(recipe['input'], 0)
                                        if recipe['numInput'] > 0 else None),
                                    'inventory_before': agent.inv_get(output, 0)})
            if receipt_ids is not None and event_id is not None:
                receipt_ids.append(event_id)
            if num_output > 0:
                learn(region, agent, output, max(0.0, 1.0 - getattr(agent, 'temporary_work_share', 0.0)
                                                - engineering_share), cur_turn)
                record_operation(region, agent, output, 1, 0,
                                 getattr(region, '_last_turn', 0), event_id)
        else:
            temporary_work_share = float(getattr(agent, 'temporary_work_share', 0.0))
            if (activity_event_id is not None or engineering_event_id is not None) and (temporary_work_share + engineering_share) > 0:
                _record_zero_production(
                    region, agent, output, kind='independent_production_zero',
                    formula_id='production.independent_zero.v1',
                    reason='production_random_draw_failed', receipt_ids=receipt_ids,
                    cause_event_ids=activity_causes,
                    inputs={'draw': rand_val, 'success_probability': chance,
                            'temporary_work_share': temporary_work_share,
                            'engineering_work_share': engineering_share,
                            'activity_event_id': activity_event_id,
                            'base_production': recipe['production'],
                            'inputs_available': has_inputs,
                            'input_good': getattr(recipe.get('input'), 'name', None),
                            'input_quantity': recipe.get('numInput', 0),
                            'inventory_before': inventory_before,
                            'maximum_inventory': max_inventory})
    else:
        if activity_event_id is not None:
            _record_zero_production(
                region, agent, output, kind='independent_production_zero',
                formula_id='production.independent_zero.v1',
                reason=('input_material_unavailable' if not has_inputs else
                        'nonpositive_recipe_output'), receipt_ids=receipt_ids,
                cause_event_ids=activity_causes,
                inputs={'temporary_work_share': float(getattr(
                    agent, 'temporary_work_share', 0.0)),
                        'activity_event_id': activity_event_id,
                        'inputs_available': has_inputs,
                        'input_good': getattr(recipe.get('input'), 'name', None),
                        'input_quantity': recipe.get('numInput', 0),
                        'input_inventory': (agent.inv_get(recipe['input'], 0)
                                            if recipe.get('input') is not None else None),
                        'recipe_production': recipe.get('production', 0),
                        'inventory_before': inventory_before,
                        'maximum_inventory': max_inventory})
    agent.inv_add(output, num_output)
    local_total_production[output] = local_total_production.get(output, 0) + num_output
    if num_output > 0:
        from economy.actor_accounts import record as record_economic_event
        record_economic_event(region, 'production', recipient_id=agent.id,
                              good=output, quantity=num_output)
        region.production_receipts.append({'turn': getattr(region, '_last_turn', 0),
                                          'person_id': agent.id, 'good': output,
                                          'quantity': num_output})


def _record_granary_food_transfer(region, *, turn, direction, units,
                                  granary_before, granary_after,
                                  source_inventory_changes=(),
                                  public_food_account_id=None,
                                  public_food_before=None,
                                  public_food_after=None,
                                  cause_event_ids=None):
    """Trace an exact physical transfer between a granary and food stocks."""
    if units <= 0:
        return None
    from run_trace import emit

    operation_id = f"granary-food:{region.name}:{int(turn)}:{direction}"
    inventory_changes = [dict(row) for row in source_inventory_changes]
    if direction == "deposit":
        members = [{
            "id": str(row["agent_id"]),
            "currency": "food_units",
            "amount": int(row["units"]),
            "balance_before": int(row["inventory_before"]),
            "balance_after": int(row["inventory_after"]),
        } for row in inventory_changes]
        payer = {
            "type": "agent_inventory_group", "id": operation_id,
            "currency": "food_units", "member_count": len(members),
            "member_ids": [member["id"] for member in members],
            "members": members,
            "balance_before": sum(row["balance_before"] for row in members),
            "balance_after": sum(row["balance_after"] for row in members),
            "balance_scope": "member_food_inventories",
        }
        payee = {
            "type": "regional_granary_stock", "id": region.name,
            "currency": "food_units",
            "balance_before": float(granary_before),
            "balance_after": float(granary_after),
            "balance_scope": "granary_stock",
        }
        counterpart_status = "producer_inventory_debits_and_granary_credit_captured"
    else:
        payer = {
            "type": "regional_granary_stock", "id": region.name,
            "currency": "food_units",
            "balance_before": float(granary_before),
            "balance_after": float(granary_after),
            "balance_scope": "granary_stock",
        }
        payee = {
            "type": "government_food_inventory",
            "id": str(public_food_account_id or region.name),
            "currency": "food_units",
            "balance_before": float(public_food_before),
            "balance_after": float(public_food_after),
            "balance_scope": "government_food_inventory",
        }
        counterpart_status = "granary_debit_and_public_food_credit_captured"
    transfer_contract = {
        "contract_version": "goods_transfer.v1",
        "operation_id": operation_id,
        "operation_type": "seasonal_granary_deposit" if direction == "deposit"
        else "seasonal_granary_release",
        "good": "food", "unit": "food_units", "amount": int(units),
        "payer_account": payer, "payee_account": payee,
        "counterparty_leg_status": counterpart_status,
    }
    return emit(
        region, kind="granary_food_stock_transfer", record_class="transfer",
        phase="production",
        subject={"type": "tile/operation", "id": operation_id,
                 "tile": region.name, "good": "food"},
        metric_id="goods.granary_stock", unit="food_units",
        before=float(granary_before), after=float(granary_after),
        formula_id="production.granary_food_transfer.v1",
        cause_event_ids=cause_event_ids or None,
        inputs={"turn": int(turn), "operation_id": operation_id,
                "direction": direction, "units": int(units),
                "granary_stock_before": float(granary_before),
                "granary_stock_after": float(granary_after),
                "source_inventory_changes": inventory_changes,
                "public_food_inventory_before": public_food_before,
                "public_food_inventory_after": public_food_after,
                "transfer_contract": transfer_contract})


def _store_food_in_granary(region, *, turn, requested_units,
                           producer_outputs, cause_event_ids=None):
    """Move integer units of this turn's harvest from farms into the granary."""
    granary_before = float(getattr(region, "granary_stock", 0.0))
    from food_storage import granary_capacity
    room = max(0, math.floor(granary_capacity(region) - granary_before + 1e-9))
    target = min(max(0, int(requested_units)), room)
    remaining = target
    changes = []
    for agent, produced_units in sorted(
            producer_outputs, key=lambda row: str(getattr(row[0], "id", ""))):
        if remaining <= 0:
            break
        inventory_before = max(0, int(agent.inv_get(Goods.food, 0)))
        available = min(max(0, int(produced_units)), inventory_before)
        take = min(remaining, available)
        if take <= 0:
            continue
        agent.inv_add(Goods.food, -take)
        inventory_after = int(agent.inv_get(Goods.food, 0))
        changes.append({"agent_id": agent.id, "units": take,
                        "inventory_before": inventory_before,
                        "inventory_after": inventory_after})
        remaining -= take
    stored = target - remaining
    if stored <= 0:
        return 0
    region.granary_stock = granary_before + stored
    _record_granary_food_transfer(
        region, turn=turn, direction="deposit", units=stored,
        granary_before=granary_before,
        granary_after=float(region.granary_stock),
        source_inventory_changes=changes, cause_event_ids=cause_event_ids)
    return stored


def _release_granary_food(region, *, turn, requested_units=None):
    """Move whole released units into public food inventory, if available."""
    granary_before = float(getattr(region, "granary_stock", 0.0))
    government = (getattr(region, "gov", None)
                  or getattr(getattr(region, "owner_nation", None),
                             "government", None))
    if ((granary_before <= 2.0 if requested_units is None else granary_before <= 0) or government is None
            or not hasattr(government, "food_inventory")):
        return 0
    units = (min(4, int(granary_before * 0.20), int(granary_before))
             if requested_units is None else min(max(0, int(requested_units)), int(granary_before)))
    if units <= 0:
        return 0
    public_food_before = float(government.food_at(region))
    granary_after = granary_before - units
    government.receive_food(units, region)
    region.granary_stock = granary_after
    if getattr(region, '_granary_released_turn', None) != turn:
        region._granary_released_turn = turn
        region._granary_released_units = 0
    region._granary_released_units += units
    _record_granary_food_transfer(
        region, turn=turn, direction="release", units=units,
        granary_before=granary_before, granary_after=granary_after,
        public_food_before=public_food_before,
        public_food_account_id=getattr(government, "name", region.name),
        public_food_after=float(government.food_at(region)))
    return units


def release_emergency_food(region, t):
    """Authorized extra release after purchases, before the district eats."""
    if getattr(region, '_granary_emergency_turn', None) == t:
        return 0
    region._granary_emergency_turn = t
    from food_access import meal_gap
    residents = [a for a in region.agents if a.alive and not a.is_corporation
                 and not a.is_government and not getattr(a, 'military_unit_id', None)]
    government = region.gov
    gap = max(0, sum(meal_gap(a) for a in residents) - government.food_at(region))
    capacity = max(0, int(getattr(region, 'granary_handling_capacity',
                                  max(4, math.ceil(len(residents) * 0.5)))))
    stock = max(0, int(getattr(region, 'granary_stock', 0)))
    reserve = max(0, int(getattr(region, 'granary_emergency_reserve', 0)))
    enabled = bool(getattr(government, 'emergency_food_policy', False))
    already = (getattr(region, '_granary_released_units', 0)
               if getattr(region, '_granary_released_turn', None) == t else 0)
    requested = min(gap, max(0, capacity - already), max(0, stock - reserve)) if enabled else 0
    units = _release_granary_food(region, turn=t, requested_units=requested) if requested else 0
    reason = ('Emergency release disabled' if not enabled else
              'Meals covered' if gap <= 0 else 'Granary empty' if stock <= 0 else
              'Protected grain reserve' if stock <= reserve else
              'Granary handling capacity reached' if capacity < gap else 'Grain released for meals')
    region.granary_release_status = {'turn': t, 'gap': gap, 'capacity': capacity,
                                    'released': units, 'reason': reason}
    return units


def produce(region, t, *, enabled=True):
    """Run production phase for all active producers in region."""
    if getattr(region, '_production_turn', None) == t:
        return
    region._production_turn = t
    region._last_turn = t
    region.production_receipts = []
    nation = getattr(region, 'owner_nation', None)
    if nation is not None:
        from innovation import get_innovation_system
        get_innovation_system().prepare_region_engineering(nation, region, t)
    region._technology_usage_turn = t
    region.technology_usage = {}
    num_agents_per_good = {}
    for a in region.agents:
        if getattr(a, 'is_native_child', False) and a.age(t) < 14:
            continue
        if not a.is_trader and a.output != Goods.gov and a.output != Goods.none and a.output in region.recipes:
            num_agents_per_good[a.output] = num_agents_per_good.get(a.output, 0) + 1
    for g in region.goods:
        if g not in num_agents_per_good:
            num_agents_per_good[g] = 0
    local_total_production = defaultdict(int)
    receipt_ids = {}
    from agriculture import produce as produce_crops
    if enabled:
        produce_crops(region, t, local_total_production, receipt_ids)
    food_producer_outputs = [(a, sum(r['quantity'] for r in region.production_receipts
        if r['person_id'] == a.id and r['good'] == Goods.food)) for a in region.agents]
    for a in (region.agents if enabled else ()):
        if (not a.alive or getattr(a, "business_closed", False) or a.output == Goods.food
                or a.employer or a.output == Goods.gov or a.is_trader or a.output == Goods.none
                or a.output not in region.recipes or getattr(a, 'military_unit_id', None)):
            continue
        if getattr(a, 'is_native_child', False) and a.age(t) < 14:
            continue
        if getattr(a, 'is_striking', False) or getattr(a, 'in_revolt', False):
            source_event_ids = []
            for event in getattr(region, 'collective_log', ()):
                if event.get('turn') != t or event.get('trace_event_id') is None:
                    continue
                facts = event.get('facts', {})
                if (a.id in facts.get('participant_ids', ())
                        or facts.get('person_id') == a.id):
                    source_event_ids.append(event['trace_event_id'])
            _record_zero_production(
                region, a, a.output, kind='independent_production_zero',
                formula_id='production.independent_zero.v1',
                reason=('worker_strike_withheld_labor'
                        if getattr(a, 'is_striking', False) else
                        'worker_revolt_withheld_labor'),
                receipt_ids=receipt_ids.setdefault(a.output, []),
                cause_event_ids=source_event_ids or None,
                inputs={'temporary_work_share': float(getattr(
                    a, 'temporary_work_share', 0.0)),
                        'inventory_before': a.inv_get(a.output, 0),
                        'collective_event_ids': source_event_ids,
                        'is_striking': bool(getattr(a, 'is_striking', False)),
                        'in_revolt': bool(getattr(a, 'in_revolt', False))})
            continue
        record_operation(region, a, a.output, 0,
                         len(getattr(a, 'employees', ())) if getattr(a, 'is_corporation', False) else 1, t)
        r = region.recipes[a.output]
        if r.get('import_only', False):
            continue
        inventory_before = (int(a.inv_get(Goods.food, 0))
                            if a.output == Goods.food else 0)
        if r.get('setup_good'):
            from abundance import produce_workshop
            produce_workshop(region, a, r, local_total_production,
                             receipt_ids.setdefault(a.output, []), t)
        elif a.is_corporation:
            produce_corporation(region, a, r, a.output, num_agents_per_good,
                                local_total_production,
                                receipt_ids.setdefault(a.output, []), turn=t)
        else:
            produce_independent(region, a, r, a.output, num_agents_per_good,
                                local_total_production, receipt_ids.setdefault(a.output, []))
        if a.output == Goods.food:
            produced_units = max(0, int(a.inv_get(Goods.food, 0))
                                 - inventory_before)
            if produced_units:
                food_producer_outputs.append((a, produced_units))

    if enabled and getattr(region, 'scenario_grain_holder_id', None) is not None:
        from scenario_political_economy import hold_after_harvest
        hold_after_harvest(region, t)

    # Phase 1: Pastoral wool / fiber yield for landlords on pasture plots
    wool_yield_total = 0
    tenure = getattr(region, 'tenure', None)
    if enabled and tenure is not None:
        for plot in getattr(tenure, 'plots', []):
            if getattr(plot, 'production_type', 'arable') == 'pasture':
                lord = None
                for a in region.agents:
                    if a.id == plot.lord_id:
                        lord = a
                        break
                if lord and lord.alive:
                    wool_yield = max(1, int(4 * plot.fraction * terrain_bonus(region, Goods.wool)))
                    lord.inv_add(Goods.wool, wool_yield)
                    local_total_production[Goods.wool] += wool_yield
                    wool_yield_total += wool_yield

    # Phase 3: Granary buffer stock management across 10-turn agricultural year
    from game_time import seasonal_cycle_phase
    year_turn = seasonal_cycle_phase(t, region)
    from harvest_claims import register as register_harvest
    register_harvest(region, t)
    # Ecology consumes only this turn's completed production, before storage releases.
    region.emission_production_turn = t
    region.emission_production = dict(local_total_production)
    food_made = local_total_production.get(Goods.food, 0)
    granary_release_units = 0
    if not hasattr(region, 'granary_stock'):
        region.granary_stock = 25.0

    # Public reserves are purchased through funded programs or explicit tax
    # claims. There is no automatic unpaid confiscation of every harvest.
    if year_turn in (9, 0, 1) and region.granary_stock > 2.0:
        # Winter / early spring lean season: release stored food into public aid stock.
        granary_release_units = _release_granary_food(region, turn=t)

    for g in region.goods:
        if g != Goods.gov:
            region.production_log[g].append(local_total_production[g])
            from run_trace import emit
            emit(region, kind='tile_production_total', record_class='calculation',
                 subject={'type': 'tile', 'id': region.name, 'good': g.name},
                 metric_id='goods.production', unit='units_per_turn',
                 after=local_total_production[g],
                 formula_id='production.sum_receipts.v2',
                 inputs={'producer_count': num_agents_per_good.get(g, 0),
                         'producer_receipts': [
                             {'event_id': ident, 'units': region._run_trace._turn_production_receipts[ident]}
                             for ident in receipt_ids.get(g, [])]
                         if getattr(region, '_run_trace', None) is not None else [],
                         'granary_stock': getattr(region, 'granary_stock', None),
                         'wool_from_pasture': wool_yield_total if g == Goods.wool else 0,
                         'granary_release_units': granary_release_units if g == Goods.food else 0},
                 cause_event_ids=receipt_ids.get(g, []))
