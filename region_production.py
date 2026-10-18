"""
Production engine (firm and independent production) with Cython acceleration.
"""

from collections import defaultdict
from goods import Goods
from random_cache import rand
from labor_contract import calculate_shift_multiplier, calculate_work_effort, ensure_labor_agreement, record_surplus_value

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
        bonuses = getattr(b, 'production_bonuses', {})
        if good in bonuses:
            mult *= bonuses[good]

    if good in (Goods.food, Goods.cotton, Goods.sugar, Goods.tobacco):
        from supply_rights import water_yield_factor
        mult *= water_yield_factor(region, producer)

    # P3: Metabolic Rift & Soil Fertility for agricultural food crops
    if good == Goods.food:
        soil_fert = getattr(region, 'soil_fertility', 1.0)
        mult *= soil_fert

        # 10-Turn Yearly Biological Seasonality
        cur_t = t if t is not None else getattr(region, '_last_turn', None)
        if cur_t is not None:
            mult *= season_mult(cur_t)
            from secular_climate import get_secular_climate
            sec_clim = get_secular_climate(cur_t)
            mult *= sec_clim['yield_multiplier']

        # Hydrological Fishery Degradation (toxic river effluent destroys coastal/river fisheries)
        p_water = getattr(region, 'pollution_water', 0.0)
        is_aquatic = (getattr(region, 'is_coast', False) or getattr(region, 'is_water', False) or
                      'arable_silt' in getattr(region, 'terrain', {}))
        if is_aquatic and p_water > 10.0:
            fish_penalty = max(0.40, 1.0 - (p_water - 10.0) * 0.015)
            mult *= fish_penalty

        # Phase 1 Enclosure Vector: Pastoral conversion replaces food crops
        tenure = getattr(region, 'tenure', None)
        if tenure is not None:
            p_frac = getattr(tenure, 'pasture_fraction', 0.0)
            if p_frac > 0:
                mult *= max(0.20, 1.0 - (0.75 * p_frac))

        # Agro-Ecological Regimes: Four-Field Rotation vs Intensive Monoculture
        regime = getattr(region, 'farming_regime', 'rotation')
        use_fert = (regime == 'intensive' or getattr(region, 'use_fertilizer', False) or
                    getattr(region, 'mandate_fertilizer', False))
        use_pest = getattr(region, 'use_pesticides', False) or getattr(region, 'mandate_pesticides', False)

        if use_fert:
            # Intensive Monoculture: Physical fertilizer / nitrate stock consumption
            stock = getattr(region, 'fertilizer_stock', 0.0)
            farm_corps = sum(1 for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False) and getattr(a, 'output', None) == Goods.food)
            needed = 1.0 + 0.5 * farm_corps
            if getattr(region, 'fertilizer_rationing', False):
                needed *= 0.5
            if stock >= needed:
                region.fertilizer_stock -= needed
                region.fertilizer_consumed_last_turn = needed
                region.is_nitrate_depleted = False
                mult *= 1.75
            else:
                region.fertilizer_consumed_last_turn = 0.0
                # Nitrate shortage!
                if soil_fert < 0.65:
                    # Turnip Winter Harvest Shock on depleted soil
                    region.is_nitrate_depleted = True
                    mult *= 0.50
                else:
                    region.is_nitrate_depleted = False
        else:
            # Norfolk Four-Field Rotation: Zero chemical inputs, biological nitrogen fixation
            region.is_nitrate_depleted = False

        if use_pest:
            mult *= 1.40

        # Scenario-only low-Nile crop shock; ordinary worlds default to 1.0.
        scenario_yield = float(getattr(region, 'scenario_food_yield_modifier', 1.0))
        shock_end = getattr(region, 'scenario_food_yield_modifier_until', None)
        current_turn = t if t is not None else getattr(region, '_last_turn', None)
        if shock_end is None or current_turn is None or current_turn <= shock_end:
            mult *= scenario_yield
        if getattr(region, 'scenario_location', None) in ('Nile Delta', 'Upper Egypt'):
            world = getattr(getattr(region, 'gov', None), 'scenario_debt_world', None)
            if world is not None and world.get('scenario_id') == 'egypt_1877':
                from scenario_projects import effectiveness
                repair = effectiveness(world, 'nile_repair', region.scenario_location)
                if repair:
                    # Restored channels mitigate the low flood, then retain a
                    # smaller durable productivity benefit after the shock.
                    project_bonus = (0.8 if current_turn is not None and current_turn <= 12
                                     else 0.15) * repair
                    mult *= 1.0 + project_bonus
                    region.scenario_repair_applied_turn = current_turn
                    region.scenario_repair_yield_factor = 1.0 + project_bonus

    # P3: Clover / Turnip Pasture Synergy for Wool
    elif good == Goods.wool:
        regime = getattr(region, 'farming_regime', 'rotation')
        if regime == 'rotation':
            mult *= 1.35  # Clover forage boosts livestock health and fleece weight by +35%

    return base * mult


def produce_corporation(region, agent, recipe, output, num_agents_per_good,
                        local_total_production, receipt_ids=None):
    """Run production logic for a corporate employer."""
    # P2.3: Striking or revolting workers withhold living labor power
    working_employees = [e for e in agent.employees if not getattr(e, 'is_striking', False) and not getattr(e, 'in_revolt', False)]
    num_employees = len(working_employees)
    if num_employees == 0:
        return
    max_inventory = recipe['maxinv'] * (1 + len(agent.employees))
    if agent.inv_get(output, 0) / max_inventory >= 1:
        return
    num_slots = num_employees
    if recipe.get('numInput', 0) > 0:
        available = agent.inv_get(recipe['input'], 0)
        active_slots = int(min(num_slots, available // recipe['numInput']))
    else:
        active_slots = int(num_slots)
    if active_slots <= 0 or recipe.get('production', 0) <= 0:
        return
    synergy = 1.0 + (0.15 if num_employees < 4 else 0.20 if num_employees < 8 else 0.25 if num_employees < 12 else 0.30) * num_employees
    base_production = recipe['production']

    # P2.1: Shift length multiplier and machinery capacity
    effort_factors = []
    for employee in working_employees:
        agreement = ensure_labor_agreement(employee, agent, getattr(region, '_last_turn', 0))
        fatigue = float(getattr(employee, 'work_fatigue', 0.0))
        nutrition = 0.6 if getattr(employee, 'hungry_steps', 0) > 0 else 1.0
        effort_factors.append(calculate_work_effort(agreement.hours, agreement.pace,
                                                    nutrition, fatigue))
        employee.work_fatigue = max(0.0, fatigue + max(0.0, agreement.hours - 8.0) * 0.025
                                    + max(0.0, agreement.pace - 1.0) * 0.20 - 0.05)
        employee.workplace_accident = agreement.hours >= 14.0 or agreement.pace >= 1.75
    shift_mult = sum(effort_factors) / len(effort_factors) if effort_factors else calculate_shift_multiplier(getattr(agent, 'shift_hours', 8.0))
    terrain_mult = terrain_bonus(region, output, producer=agent)
    production_per_slot = base_production * synergy * terrain_mult * shift_mult

    machinery = getattr(agent, 'machinery_level', 1)
    broken = getattr(agent, 'broken_machinery', 0)
    working_machinery = max(0, machinery - broken)
    if working_machinery < 1:
        # If all machinery broken by sabotage, manual labor has 50% productivity penalty
        production_per_slot *= 0.5
    elif working_machinery > 1:
        production_per_slot *= 1.0 + 0.40 * min(3, working_machinery - 1)

    chance = 1.0
    if agent.hungry_steps > 0:
        chance *= 1 / (1 + agent.hungry_steps * 0.2)
    if output in (Goods.food, Goods.wood):
        chance *= min(1.0, recipe['maxtotalprod'] / max(1, num_agents_per_good[output]) / base_production)
    chance *= max(0, 1 - agent.inv_get(output, 0) / max_inventory)
    vals = rand.random_n(active_slots)
    if _c is not None:
        successful_slots = _c.produce_corporation_slots(active_slots, chance, vals)
    else:
        successful_slots = sum(1 for v in vals if v < chance)
    if successful_slots:
        inputs_cost = 0.0
        inputs_used = 0
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
        num_output = int(successful_slots * production_per_slot) or 1
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
                        inputs={'employees': len(agent.employees),
                                'working_employees': num_employees,
                                'active_slots': active_slots, 'successful_slots': successful_slots,
                                'slot_draws': list(vals), 'success_probability': chance,
                                'base_production': base_production, 'synergy': synergy,
                                'terrain_multiplier': terrain_mult,
                                'shift_multiplier': shift_mult,
                                'working_machinery': working_machinery,
                                'production_per_slot': production_per_slot,
                                'inputs_used': inputs_used,
                                'inventory_before': inventory_before,
                                'inventory_after': agent.inv_get(output, 0)})
        if receipt_ids is not None and event_id is not None:
            receipt_ids.append(event_id)

        # P2.1: Surplus value extraction accounting (s/v)
        wages_paid = len(agent.employees) * getattr(agent, 'wage', 1.0)
        record_surplus_value(agent, region, output, num_output, inputs_cost, wages_paid)
        compute_and_record_firm_footprint(agent, region, output, num_output, inputs_cost, wages_paid)


def compute_and_record_firm_footprint(agent, region, output, num_output, inputs_cost, wages_paid, cur_turn=None):
    """Attribute ecological, health, and sociological footprint directly to producing firm."""
    try:
        from economy.true_cost_ledger import get_true_cost_ledger
        ledger = get_true_cost_ledger()
        if cur_turn is None:
            cur_turn = getattr(region, '_last_turn', 0) or 0

        phys = {}
        b_names = [getattr(b, 'name', '') for b in getattr(region, 'buildings', [])]
        has_scrubber = 'smoke_scrubber' in b_names
        has_sewer = 'trunk_sewer' in b_names
        has_filtration = 'water_filtration_plant' in b_names

        regime = getattr(region, 'farming_regime', 'rotation')
        use_fert = (regime == 'intensive' or getattr(region, 'use_fertilizer', False) or
                    getattr(region, 'mandate_fertilizer', False))
        use_pest = getattr(region, 'use_pesticides', False) or getattr(region, 'mandate_pesticides', False)

        # 1. Agricultural emissions
        if output in (Goods.food, Goods.cotton, Goods.sugar, Goods.tobacco):
            if use_fert or regime == 'intensive':
                phys['soil_fertility_loss'] = 0.025
                phys['water_effluent_discharged'] = 3.5
            elif regime == 'rotation':
                phys['soil_fertility_loss'] = 0.005
            else:
                phys['soil_fertility_loss'] = 0.015

            if use_pest:
                phys['soil_toxins_generated'] = 4.0
                if getattr(agent, 'employees', []):
                    phys['labor_health_wear'] = len(agent.employees) * 0.040

        # 2. Industrial emissions
        else:
            raw_air = 1.8
            nation = getattr(region, 'owner_nation', None)
            unlocked = getattr(nation, 'unlocked_techs', set()) if nation else set()
            if 'coal_coking' in unlocked or 'steam_engines' in unlocked:
                raw_air *= 1.6
            if has_scrubber:
                phys['air_smog_emitted'] = raw_air * 0.30
                phys['soil_toxins_generated'] = raw_air * 0.35  # sludge
            else:
                phys['air_smog_emitted'] = raw_air

            raw_water = 1.2
            if has_sewer or has_filtration:
                raw_water *= 0.30
            phys['water_effluent_discharged'] = raw_water

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
    max_inventory = recipe['maxinv']
    if agent.inv_get(output, 0) / max_inventory >= 1:
        return
    has_inputs = True
    if recipe['numInput'] > 0 and agent.inv_get(recipe['input'], 0) < recipe['numInput']:
        has_inputs = False
    num_output = 0
    if has_inputs and recipe.get('production', 0) > 0:
        chance = 1.0
        chance *= max(0.0, 1.0 - float(getattr(agent, 'temporary_work_share', 0.0)))
        if agent.hungry_steps > 0:
            chance *= 1 / (1 + agent.hungry_steps * 0.2)
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
            if recipe['numInput'] > 0:
                agent.inv_add(recipe['input'], -recipe['numInput'])
                input_price = region.recipes.get(recipe['input'], {}).get('price', 1.0)
                inputs_cost = recipe['numInput'] * input_price
            terrain_mult = terrain_bonus(region, output, producer=agent)
            from labor_choice import occupational_tenure_multiplier
            cur_turn = int(getattr(region, '_last_turn', 0) or 0)
            tenure_mult = occupational_tenure_multiplier(agent, output, cur_turn)
            num_output = int(round(recipe['production'] * terrain_mult * tenure_mult))
            compute_and_record_firm_footprint(agent, region, output, num_output, inputs_cost, 0.0)
        if made:
            from run_trace import emit
            event_id = emit(region, kind='independent_production', record_class='outcome',
                            subject={'type': 'agent', 'id': agent.id, 'tile': region.name,
                                     'good': output.name},
                            metric_id='goods.production', unit='units', before=0,
                            after=num_output, formula_id='production.independent.v1',
                            inputs={'draw': rand_val, 'success_probability': chance,
                                    'base_production': recipe['production'],
                                    'terrain_multiplier': terrain_mult,
                                    'tenure_multiplier': round(tenure_mult, 4),
                                    'inputs_used': recipe['numInput'] if recipe['numInput'] > 0 else 0,
                                    'inventory_before': agent.inv_get(output, 0)})
            if receipt_ids is not None and event_id is not None:
                receipt_ids.append(event_id)
    agent.inv_add(output, num_output)
    local_total_production[output] = local_total_production.get(output, 0) + num_output
    if num_output > 0:
        from economy.actor_accounts import record as record_economic_event
        record_economic_event(region, 'production', recipient_id=agent.id,
                              good=output, quantity=num_output)
        region.production_receipts.append({'turn': getattr(region, '_last_turn', 0),
                                          'person_id': agent.id, 'good': output,
                                          'quantity': num_output})


def produce(region, t):
    """Run production phase for all active producers in region."""
    region._last_turn = t
    region.production_receipts = []
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
    for a in region.agents:
        if (a.employer or a.output == Goods.gov or a.is_trader or a.output == Goods.none
                or a.output not in region.recipes or getattr(a, 'military_unit_id', None)):
            continue
        if getattr(a, 'is_native_child', False) and a.age(t) < 14:
            continue
        if getattr(a, 'is_striking', False) or getattr(a, 'in_revolt', False):
            continue
        r = region.recipes[a.output]
        if r.get('import_only', False):
            continue
        if a.is_corporation and len(a.employees) > 0:
            produce_corporation(region, a, r, a.output, num_agents_per_good,
                                local_total_production, receipt_ids.setdefault(a.output, []))
        else:
            produce_independent(region, a, r, a.output, num_agents_per_good,
                                local_total_production, receipt_ids.setdefault(a.output, []))

    if getattr(region, 'scenario_grain_holder_id', None) is not None:
        from scenario_political_economy import hold_after_harvest
        hold_after_harvest(region, t)

    # Phase 1: Pastoral wool / fiber yield for landlords on pasture plots
    wool_yield_total = 0
    tenure = getattr(region, 'tenure', None)
    if tenure is not None:
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
    year_turn = seasonal_cycle_phase(t)
    food_made = local_total_production.get(Goods.food, 0)
    granary_release_units = 0
    if not hasattr(region, 'granary_stock'):
        region.granary_stock = 25.0

    if year_turn in (4, 5, 6, 7) and food_made > 2:
        # Peak harvest accumulation into granary
        buffer_in = max(1.0, food_made * 0.15)
        region.granary_stock = min(120.0, region.granary_stock + buffer_in)
    elif year_turn in (9, 0, 1) and region.granary_stock > 2.0:
        # Winter / early spring lean season: granary releases buffer food into local production
        buffer_out = min(4.0, region.granary_stock * 0.20)
        region.granary_stock = max(0.0, region.granary_stock - buffer_out)
        granary_release_units = int(buffer_out)
        local_total_production[Goods.food] += granary_release_units

    for g in region.goods:
        if g != Goods.gov:
            region.production_log[g].append(local_total_production[g])
            from run_trace import emit
            emit(region, kind='tile_production_total', record_class='calculation',
                 subject={'type': 'tile', 'id': region.name, 'good': g.name},
                 metric_id='goods.production', unit='units_per_turn',
                 after=local_total_production[g],
                 formula_id='production.sum_receipts.v1',
                 inputs={'producer_count': num_agents_per_good.get(g, 0),
                         'granary_stock': getattr(region, 'granary_stock', None),
                         'wool_from_pasture': wool_yield_total if g == Goods.wool else 0,
                         'granary_release_units': granary_release_units if g == Goods.food else 0},
                 cause_event_ids=receipt_ids.get(g, []))
