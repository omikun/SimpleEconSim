"""Persistent plot operations and ten-phase crops. Inventories never stop growth."""
from __future__ import annotations
import math
from goods import Goods
from food_accounts import balance, transfer, create, consume, record, reserve, release

SOW = (0, 1)
TEND = (2, 3, 4, 5)
HARVEST = (6, 7)
WORK_PER_AREA = {'sow': .5, 'tend': .5, 'harvest': .75}
YIELD_PER_AREA = 120.0
SEED_PER_AREA = 6.0
WORK_TECHNOLOGIES = {'seed_drills': ('sow', 'tend'),
                     'mechanized_harvesting': ('sow', 'tend', 'harvest')}


def operating_producer(operator):
    company = getattr(operator, 'company_owned', None)
    return company if company is not None and company.output == Goods.food and not getattr(company, 'business_closed', False) else operator


def work_productivity(region, operator, label):
    from technology_adoption import applies_to_producer
    factor = 1.0
    for building in getattr(region, 'buildings', ()):
        tech = building.name.removesuffix('_prototype')
        if label in WORK_TECHNOLOGIES.get(tech, ()) and applies_to_producer(building, operating_producer(operator)):
            factor *= max(1, building.production_bonuses.get(Goods.food, 1))
    return factor


def phase(region, turn=None):
    return (int(getattr(region, '_last_turn', 0) if turn is None else turn)
            + int(getattr(region, 'seasonal_phase_offset', 0))) % 10


def stage(region, turn=None):
    p = phase(region, turn)
    return 'sow' if p in SOW else 'tend' if p in TEND else 'harvest' if p in HARVEST else 'fallow'


def turns_until_harvest(region, turn=None):
    p = phase(region, turn)
    if p == 6:
        return 1  # The second harvest window is still ahead.
    return (6 - p) % 10 or 10


def ensure_operations(region, turn):
    """Allocate finite land to existing lawful cultivators, once per plot/person."""
    from households import human
    from livelihood_access import effective_access
    from labor_choice import career_lifecycle_age
    farms = getattr(region, 'farms', {})
    plots = getattr(getattr(region, 'tenure', None), 'plots', ())
    total_area = float(getattr(region, 'agricultural_area', 0))
    present = {a.id: a for a in region.agents if human(a)}
    living = {a.id: a for a in region.agents if a.alive}
    for plot in plots:
        if getattr(plot, 'production_type', 'arable') not in ('arable', 'mixed'):
            continue
        candidates = [p for p in present.values() if not getattr(p, 'is_lord', False)
                      and getattr(plot.tenure, 'value', '') != 'enclosed'
                      and career_lifecycle_age(p, turn) >= 14
                      and (getattr(p, 'assigned_plot_id', None) == plot.plot_id or p.id in plot.tenant_ids)
                      and effective_access(p, region, 'field') > 0]
        existing = [f for f in farms.values() if f['plot_id'] == plot.plot_id]
        allocated = sum(f['area'] for f in existing)
        vacant = max(0, total_area * plot.fraction - allocated)
        known = {f['operator_id'] for f in existing}
        newcomers = [p for p in candidates if p.id not in known]
        # New entrants can use genuinely unallocated land, never shrink somebody
        # else's standing operation merely by entering the population.
        if newcomers and (vacant > .001 or getattr(plot.tenure, 'value', '') == 'commons'):
            each = vacant / len(newcomers)
            for person in sorted(newcomers, key=lambda a: a.id):
                key = f'farm:{plot.plot_id}:{person.id}'
                farms[key] = {'id': key, 'plot_id': plot.plot_id, 'operator_id': person.id,
                              'area': each, 'food_milli': 0, 'crop': None,
                              'created_turn': turn, 'loss_remainder': 0.0,
                              'storage_capacity': each * YIELD_PER_AREA * 1.5,
                              'work_history': {}, 'harvest_total': 0.0}
    region.farms = farms
    # Exclusive control can operate an estate through paid labor. Usufruct
    # cultivators retain their standing crops until harvest; new sowing uses
    # the lawful controller after that crop cycle ends.
    from land_tenure import TenureStatus
    for plot in plots:
        if plot.tenure != TenureStatus.ENCLOSED or plot.production_type not in ('arable', 'mixed'):
            continue
        control = getattr(plot, 'controlled_by_id', plot.lord_id)
        controller = next((a for a in region.agents if a.id == control and a.alive), None)
        if controller is not None and not any(f['plot_id'] == plot.plot_id and f['operator_id'] == control for f in farms.values()):
            key = f'farm:{plot.plot_id}:{control}'
            vacant = max(0, total_area * plot.fraction - sum(f['area'] for f in farms.values() if f['plot_id'] == plot.plot_id))
            farms[key] = {'id': key, 'plot_id': plot.plot_id, 'operator_id': control,
                          'area': vacant, 'food_milli': 0, 'crop': None, 'created_turn': turn,
                          'loss_remainder': 0.0, 'storage_capacity': vacant * YIELD_PER_AREA * 1.5,
                          'work_history': {}, 'harvest_total': 0.0, 'estate_operation': True}
    for farm in farms.values():
        operator = living.get(farm['operator_id'])
        company = operator if getattr(operator, 'is_corporation', False) else getattr(operator, 'company_owned', None)
        farm['employer_id'] = (company.id if company is not None and company.output == Goods.food
                               and not getattr(company, 'business_closed', False) else None)
    # Succession keeps both physical stock and the standing crop.
    for farm in farms.values():
        if farm['operator_id'] not in living:
            previous = next((a for a in region.agents if a.id == farm['operator_id']), None)
            if previous is None:  # A living absentee owner retains their property.
                continue
            heirs = [a for a in present.values() if getattr(a, 'parent', None) is previous] if previous else []
            plot = next((p for p in plots if p.plot_id == farm['plot_id']), None)
            successor = min(heirs, key=lambda a: a.id) if heirs else present.get(getattr(plot, 'lord_id', None))
            if successor is not None:
                farm['operator_id'] = successor.id
    allocate_seasonal_land(region, turn)
    return farms


def can_operate(region, farm, operator):
    from career_transitions import profession
    from livelihood_access import effective_access
    if operator is None:
        return False
    plot = next((p for p in region.tenure.plots if p.plot_id == farm['plot_id']), None)
    controller = plot is not None and getattr(plot, 'controlled_by_id', plot.lord_id) == operator.id
    return (controller and getattr(plot.tenure, 'value', '') == 'enclosed') or (
        profession(operator) == Goods.food and effective_access(operator, region, 'field') > 0)


def seed_gap(region, person):
    if phase(region) not in (8, 9, 0, 1):
        return 0.0
    actors = {a.id: a for a in getattr(region, 'agents', ()) if a.alive}
    gap = 0.0
    for farm in getattr(region, 'farms', {}).values():
        operator = actors.get(farm['operator_id'])
        company = getattr(operator, 'company_owned', None)
        funder = company if company is not None and company.output == Goods.food and not getattr(company, 'business_closed', False) else operator
        if (funder is person and can_operate(region, farm, operator)
                and (not farm.get('crop') or farm['crop']['closed'])):
            gap += max(0, farm['area'] * SEED_PER_AREA - balance(farm))
    return gap


def yield_factor(region, operator, turn, *, farm=None):
    """Read-only productive inputs; chemical use is committed once per stage."""
    from technology_adoption import applies_to_producer
    from secular_climate import get_secular_climate
    from supply_rights import water_yield_factor
    terrain = max(0, float(getattr(region, 'terrain', {}).get(Goods.food, 1)))
    soil = max(0, float(getattr(region, 'soil_fertility', 1)))
    water = water_yield_factor(region, operator) if operator is not None else 1
    if farm is not None and any(p.plot_id == farm['plot_id'] for p in getattr(getattr(region, 'tenure', None), 'plots', ())):
        water = max(.25, min(1.25, float(getattr(region, 'water_allocations', {}).get(farm['plot_id'], 0))))
    tech = 1.0
    for building in getattr(region, 'buildings', ()):
        if (applies_to_producer(building, operating_producer(operator))
                and building.name.removesuffix('_prototype') not in WORK_TECHNOLOGIES):
            tech *= getattr(building, 'production_bonuses', {}).get(Goods.food, 1)
    shock = float(getattr(region, 'scenario_food_yield_modifier', 1))
    until = getattr(region, 'scenario_food_yield_modifier_until', None)
    if until is not None and turn > until:
        shock = 1.0
    climate = get_secular_climate(turn)['yield_multiplier']
    pollution = max(.4, 1 - max(0, getattr(region, 'pollution_water', 0) - 10) * .01)
    repair_factor = 1.0
    location = getattr(region, 'scenario_location', None)
    world = getattr(getattr(region, 'gov', None), 'scenario_debt_world', None)
    if location in ('Nile Delta', 'Upper Egypt') and world and world.get('scenario_id') == 'egypt_1877':
        from scenario_projects import effectiveness
        repair_factor += (.8 if turn <= 12 else .15) * effectiveness(world, 'nile_repair', location)
    committed = getattr(region, 'crop_inputs', {})
    chemical = committed.get('factor', 1) if committed.get('turn') == turn else 1
    return terrain * soil * water * tech * shock * climate * pollution * repair_factor * chemical


def commit_crop_inputs(region, turn):
    """Consume physical chemicals once, outside read-only yield queries."""
    if getattr(region, 'crop_inputs', {}).get('turn') == turn:
        return
    factor = 1.0
    region.fertilizer_consumed_last_turn = 0.0
    region.is_nitrate_depleted = False
    if stage(region, turn) == 'tend':
        area = sum(f['crop']['planted_area'] for f in region.farms.values()
                   if f.get('crop') and not f['crop']['closed'])
        requested = area * .1
        use = getattr(region, 'farming_regime', 'rotation') == 'intensive' or getattr(region, 'use_fertilizer', False) or getattr(region, 'mandate_fertilizer', False)
        if use and requested > 0:
            before = max(0, getattr(region, 'fertilizer_stock', 0))
            used = min(before, requested * (.5 if getattr(region, 'fertilizer_rationing', False) else 1))
            region.fertilizer_stock = before - used
            region.fertilizer_consumed_last_turn = used
            factor *= 1 + .75 * used / requested
            region.is_nitrate_depleted = used < requested and getattr(region, 'soil_fertility', 1) < .65
            if region.is_nitrate_depleted:
                factor *= .5
            from run_trace import emit
            emit(region, kind='fertilizer_stock_use', record_class='outcome', phase='production',
                 subject={'type': 'tile', 'id': region.name, 'good': 'fertilizer'},
                 metric_id='ecology.fertilizer_stock', unit='fertilizer_units', before=before,
                 after=region.fertilizer_stock, formula_id='agriculture.fertilizer_area_use.v2',
                 inputs={'turn': turn, 'actual_use': used, 'requested_use': requested,
                         'planted_area': area, 'yield_factor': factor})
        # A mandate is permission, not a free material input.
        if requested > 0 and (getattr(region, 'use_pesticides', False) or getattr(region, 'mandate_pesticides', False)):
            used = min(max(0, getattr(region, 'pesticide_stock', 0)), requested)
            region.pesticide_stock = max(0, getattr(region, 'pesticide_stock', 0) - used)
            factor *= 1 + .4 * used / requested
    region.crop_inputs = {'turn': turn, 'factor': factor}


def settle_succession(region, prior_agents, survivors):
    """Resolve dead operators while their kinship and title links still exist."""
    living = {a.id: a for a in survivors if a.alive}
    dead = {a.id: a for a in prior_agents if not a.alive}
    for farm in getattr(region, 'farms', {}).values():
        former = dead.get(farm['operator_id'])
        if former is None:
            continue
        heirs = [a for a in living.values() if getattr(a, 'parent', None) is former
                 and not getattr(a, 'is_corporation', False)]
        plot = next((p for p in region.tenure.plots if p.plot_id == farm['plot_id']), None)
        heir = max(heirs, key=lambda a: (a.age(getattr(region, '_last_turn', 0)), -a.id)) if heirs else living.get(getattr(plot, 'lord_id', None))
        if heir is not None:
            farm['operator_id'] = heir.id
            farm['employer_id'] = None
            if getattr(heir, 'assigned_plot_id', None) is None:
                heir.assigned_plot_id = farm['plot_id']


def initialize(region, turn, *, mode=None):
    if getattr(region, 'food_economy_version', None) == 2:
        return getattr(region, 'food_initialization', {})
    from households import rebuild, human
    from career_transitions import profession
    mode = mode or getattr(region, 'food_opening_mode', 'authored')
    if mode not in ('balanced', 'authored'):
        raise ValueError('Food opening mode must be balanced or authored')
    region._last_turn = turn
    rebuild(region, turn)
    farms = ensure_operations(region, turn)
    if mode == 'balanced':
        allocate_seasonal_land(region, turn, opening=True)
    before = sum(a.inv_get(Goods.food, 0) for a in region.agents)
    seed = harvest = 0.0
    if mode == 'balanced':
        # Declared synthetic preceding harvest, never a paid transaction.
        for person in region.agents:
            if human(person):
                person.inv_set(Goods.food, 0)
        for farm in farms.values():
            operator = next((a for a in region.agents if a.id == farm['operator_id']), None)
            if not can_operate(region, farm, operator):
                continue
            gross = farm['area'] * float(getattr(region, 'crop_yield_per_area', YIELD_PER_AREA))
            gross *= yield_factor(region, operator, turn, farm=farm)
            harvest += create(region, farm, gross, kind='opening_harvest',
                              assumed_completed_work=farm['area'] * 4.5)
            kept = min(gross, farm['area'] * SEED_PER_AREA)
            seed += reserve(region, farm, 'seed', kept)
            transfer(region, farm, operator, max(0, gross - kept), kind='opening_household_withdrawal')
        # A declared carryover pantry for non-growers buys time to trade. It is
        # part of the opening endowment, never replenished by the turn loop.
        pantry = 0.0
        from nutrition import basic_food_units
        for person in region.agents:
            if human(person) and profession(person) != Goods.food:
                pantry += create(region, person, basic_food_units(person) * 2,
                                 kind='opening_pantry_carryover')
    else:
        pantry = 0.0
        # Legacy/authored stocks are preserved; move owned grain into seed,
        # without creating a retrospectively planted crop or free harvest.
        for farm in farms.values():
            operator = next((a for a in region.agents if a.id == farm['operator_id']), None)
            if operator is not None and profession(operator) == Goods.food:
                amount = transfer(region, operator, farm,
                                  min(operator.inv_get(Goods.food, 0) / 4, farm['area'] * SEED_PER_AREA),
                                  kind='opening_seed_reservation')
                seed += reserve(region, farm, 'seed', amount)
    region.food_economy_version = 2
    region.food_initialization = {'mode': mode, 'turn': turn, 'phase': phase(region, turn),
                                 'prior_private_stock': before, 'synthetic_prior_harvest': harvest,
                                 'declared_pantry_carryover': pantry, 'seed_reserved': seed,
                                 'area': sum(f['area'] for f in farms.values()),
                                 'migration_assumptions': getattr(region, 'food_migration_assumptions', None)}
    from nutrition import basic_food_units
    ordinary = sum(basic_food_units(a) for a in region.agents if human(a))
    private = sum(a.inv_get(Goods.food, 0) + a.inv_get(Goods.prepared_food, 0) for a in region.agents if human(a))
    cycle = sum(max(0, f['area'] * (getattr(region, 'crop_yield_per_area', YIELD_PER_AREA) - SEED_PER_AREA)) for f in farms.values())
    region.food_initialization['feasibility'] = {
        'basic_cycle_requirement': ordinary * 10,
        'land_yield_ceiling_before_work_and_shocks': cycle,
        'private_bridge_food': private,
        'bridge_requirement_before_first_harvest': ordinary * turns_until_harvest(region, turn),
        'private_bridge_sufficient': private >= ordinary * turns_until_harvest(region, turn),
        'land_ceiling_sufficient': cycle >= ordinary * 10,
        'balanced_mode_requires_postharvest_phase': mode != 'balanced' or phase(region, turn) in (7, 8, 9)}
    return region.food_initialization


def requirements(region, turn):
    ensure_operations(region, turn)
    label = stage(region, turn)
    actors = {a.id: a for a in region.agents if a.alive}
    return {key: (farm.get('crop', {}).get('planted_area', farm['area']) * WORK_PER_AREA[label]
                  / work_productivity(region, actors.get(farm['operator_id']), label)
                  if label != 'fallow' and farm.get('crop') and not farm['crop']['closed'] else 0)
            for key, farm in region.farms.items()}


def allocate_seasonal_land(region, turn, *, opening=False):
    if phase(region, turn) not in SOW and not opening:
        return
    people = {a.id: a for a in region.agents if a.alive}
    growers = [f for f in region.farms.values() if f['operator_id'] in people
               and can_operate(region, f, people[f['operator_id']])]
    # Commons cultivation rights divide finite shared acreage at sowing. New
    # adults may join cultivation without duplicating land; private operations
    # retain their contracted areas. Standing crops are never repartitioned.
    epoch = (turn + int(getattr(region, 'seasonal_phase_offset', 0))) // 10
    if getattr(region, '_commons_allotment_epoch', None) != epoch:
        from land_tenure import TenureStatus
        for plot in region.tenure.plots:
            if plot.tenure not in (TenureStatus.COMMONS, TenureStatus.ENCLOSED):
                continue
            selected = [f for f in growers if f['plot_id'] == plot.plot_id]
            each = getattr(region, 'agricultural_area', 0) * plot.fraction / max(1, len(selected))
            storage = sum(f['storage_capacity'] for f in region.farms.values() if f['plot_id'] == plot.plot_id)
            for farm in region.farms.values():
                if farm['plot_id'] == plot.plot_id:
                    farm['area'] = each if farm in selected else 0.0
                    if selected:
                        farm['storage_capacity'] = storage / len(selected) if farm in selected else 0.0
        region._commons_allotment_epoch = epoch


def planting_area(region, farm, operator, turn):
    """The same replenishment plan is used for sowing and conditional forecasts."""
    from households import human
    from nutrition import basic_food_units
    actors = {a.id: a for a in region.agents if a.alive}
    active_area = sum(f['area'] for f in region.farms.values()
                      if can_operate(region, f, actors.get(f['operator_id'])))
    ordinary = sum(basic_food_units(p) for p in actors.values() if human(p))
    share = ordinary * farm['area'] / max(.001, active_area)
    until = turns_until_harvest(region, turn)
    company = getattr(operator, 'company_owned', None)
    business_stock = company.inv_get(Goods.food, 0) if company is not None and company.output == Goods.food and not getattr(company, 'business_closed', False) else 0
    stock_at_harvest = max(0, balance(farm) + operator.inv_get(Goods.food, 0) + business_stock - share * until)
    desired = max(0, share * 11 - stock_at_harvest)
    yield_per_area = getattr(region, 'crop_yield_per_area', YIELD_PER_AREA) * max(.001, yield_factor(region, operator, turn, farm=farm))
    return min(farm['area'], desired / max(.001, yield_per_area - SEED_PER_AREA)), share, stock_at_harvest


def begin_crops(region, turn):
    ensure_operations(region, turn)
    from career_transitions import profession
    current = phase(region, turn)
    if current not in SOW:
        return
    people = {a.id: a for a in region.agents if a.alive}
    from nutrition import basic_food_units
    from households import human
    growers = [f for f in region.farms.values() if f['operator_id'] in people
               and can_operate(region, f, people[f['operator_id']])]
    for farm in region.farms.values():
        operator = people.get(farm['operator_id'])
        epoch = (turn + int(getattr(region, 'seasonal_phase_offset', 0))) // 10
        crop = farm.get('crop')
        if crop and crop['epoch'] == epoch:
            continue
        if not can_operate(region, farm, operator):
            continue
        # Plan replenishment at the next harvest, not an inventory on/off gate.
        # Existing grain pays for meals/sales until then and is not all surplus.
        planned_area, share, stock_at_harvest = planting_area(region, farm, operator, turn)
        farm['planting_plan'] = {'turn': turn, 'area': planned_area,
                                 'expected_need_share': share, 'expected_stock_at_harvest': stock_at_harvest}
        seed_need = planned_area * SEED_PER_AREA
        release(region, farm, 'seed')
        missing = max(0, seed_need - balance(farm))
        company = getattr(operator, 'company_owned', None)
        seed_owner = company if company is not None and company.output == Goods.food and not getattr(company, 'business_closed', False) else operator
        transfer(region, seed_owner, farm, missing, kind='seed_purchase_from_owned_stock')
        if seed_owner is not operator:
            transfer(region, operator, farm, max(0, seed_need - balance(farm)), kind='owner_seed_contribution')
        planted = min(planned_area, balance(farm) / SEED_PER_AREA)
        if planted <= 0:
            continue
        used = consume(region, farm, planted * SEED_PER_AREA, kind='seed_use')
        farm['crop'] = {'epoch': epoch, 'planted_area': planted, 'seed_used': used,
                        'sow_work': 0.0, 'tend_work': 0.0, 'harvest_work': 0.0,
                        'growth_sum': 0.0, 'growth_count': 0, 'harvested': 0.0,
                        'potential': None, 'last_turn': None, 'closed': False}


def staff_capacity(region, farm, turn):
    """Feasible crop labor, shared across all operations of the same operator."""
    from work_allocation import available_work
    from households import food
    from nutrition import basic_food_units
    people = {a.id: a for a in region.agents if a.alive}
    operator = people.get(farm['operator_id'])
    company = operator if getattr(operator, 'is_corporation', False) else getattr(operator, 'company_owned', None)
    staff = ([operator] if operator is not None and not getattr(operator, 'is_corporation', False) else [])
    if company is not None and company.output == Goods.food and not getattr(company, 'business_closed', False):
        staff += [p for p in company.employees if p.alive]
    capacity = 0.0
    for person in staff:
        if person.is_striking or person.in_revolt or person.id in getattr(region, 'pollution_revolt_ids', ()):
            continue
        work = available_work(region, person, turn)
        # The same subsistence attempt used by the work planner has priority.
        from foraging import potential
        gathering = min(max(0, basic_food_units(person) - food(person)), potential(person, region)) / 8
        from engineering import production_work_share
        capacity += max(0, work - gathering - production_work_share(person, turn))
    all_area = sum(f['area'] for f in getattr(region, 'farms', {}).values()
                   if f['operator_id'] == farm['operator_id'])
    return capacity * farm['area'] / max(.001, all_area)


def expected_harvest(region, farm, turn):
    """Central harvest conditional on observed crops and feasible remaining work."""
    from career_transitions import profession
    crop = farm.get('crop')
    operator = next((a for a in region.agents if a.id == farm['operator_id'] and a.alive), None)
    capacity = staff_capacity(region, farm, turn)
    current = phase(region, turn)
    area = crop['planted_area'] if crop and not crop['closed'] else farm['area']
    if area <= 0 or operator is None:
        return 0.0
    if crop and not crop['closed']:
        not_done = crop.get('last_turn') != turn
        future = lambda phases: sum(p > current or (p == current and not_done) for p in phases)
        sow = crop['sow_work'] + future(SOW) * capacity * work_productivity(region, operator, 'sow')
        tend = crop['tend_work'] + future(TEND) * capacity * work_productivity(region, operator, 'tend')
        harvest_work = crop['harvest_work'] + future(HARVEST) * capacity * work_productivity(region, operator, 'harvest')
        growth = crop['growth_sum']
        count = crop['growth_count']
        for p in TEND:
            if p > current or (p == current and not_done):
                growth += yield_factor(region, operator, turn, farm=farm) * max(.45, 1 + .45 * math.sin(2 * math.pi * (p - 2) / 10))
                count += 1
        factor = growth / max(1, count)
        potential = (crop['potential'] if crop['potential'] is not None else
                     area * getattr(region, 'crop_yield_per_area', YIELD_PER_AREA) * factor
                     * min(1, sow / max(.001, area)) * (.4 + .6 * min(1, tend / max(.001, area * 2))))
        return max(0, potential * min(1, harvest_work / max(.001, area * 1.5)) - crop['harvested'])
    if not can_operate(region, farm, operator):
        return 0.0
    area = planting_area(region, farm, operator, turn)[0]
    company = getattr(operator, 'company_owned', None)
    company_stock = company.inv_get(Goods.food, 0) if company is not None and company.output == Goods.food and not getattr(company, 'business_closed', False) else 0
    area = min(area, (balance(farm) + operator.inv_get(Goods.food, 0) + company_stock) / SEED_PER_AREA)
    seasonal = sum(max(.45, 1 + .45 * math.sin(2 * math.pi * (p - 2) / 10)) for p in TEND) / len(TEND)
    return (area * getattr(region, 'crop_yield_per_area', YIELD_PER_AREA)
            * yield_factor(region, operator, turn, farm=farm) * seasonal
            * min(1, capacity * 2 * work_productivity(region, operator, 'sow') / max(.001, area))
            * (.4 + .6 * min(1, capacity * 4 * work_productivity(region, operator, 'tend') / max(.001, area * 2)))
            * min(1, capacity * 2 * work_productivity(region, operator, 'harvest') / max(.001, area * 1.5)))


def produce(region, turn, totals, receipts):
    if getattr(region, '_crop_production_turn', None) == turn:
        return
    region._crop_production_turn = turn
    if not hasattr(region, 'farms'):
        from food_economy import begin_turn, prepare_work
        begin_turn(region, turn)
        prepare_work(region, turn)
    begin_crops(region, turn)
    label = stage(region, turn)
    p = phase(region, turn)
    people = {a.id: a for a in region.agents if a.alive}
    work_rows = getattr(region, 'work_allocations', {}).get('people', {})
    for key, farm in region.farms.items():
        crop = farm.get('crop')
        if not crop or crop['closed'] or crop.get('last_turn') == turn:
            continue
        crop['last_turn'] = turn
        operator = people.get(farm['operator_id'])
        supplied = sum(row.get('activities', {}).get(key, 0) for row in work_rows.values())
        farm['work_history'][str(turn)] = supplied
        farm['work_history'] = dict(list(farm['work_history'].items())[-30:])
        if label in WORK_PER_AREA:
            crop[f'{label}_work'] += supplied * work_productivity(region, operator, label)
        if label == 'tend':
            location = getattr(region, 'scenario_location', None)
            world = getattr(getattr(region, 'gov', None), 'scenario_debt_world', None)
            if location in ('Nile Delta', 'Upper Egypt') and world:
                from scenario_projects import effectiveness
                repair = effectiveness(world, 'nile_repair', location)
                if repair:
                    region.scenario_repair_applied_turn = turn
                    region.scenario_repair_yield_factor = 1 + (.8 if turn <= 12 else .15) * repair
            # The seasonal curve affects growth once, not harvested grain again.
            seasonal = max(.45, 1 + .45 * math.sin(2 * math.pi * (p - 2) / 10))
            from abundance import enabled, proficiency
            workers = [(people[pid], row.get('activities', {}).get(key, 0))
                       for pid, row in work_rows.items() if pid in people]
            practice = (sum(proficiency(person, Goods.food) * work for person, work in workers)
                        / supplied if supplied > 0 and enabled(region) else 1.0)
            crop['growth_sum'] += yield_factor(region, operator, turn, farm=farm) * seasonal * practice
            crop['growth_count'] += 1
        if label == 'harvest':
            area = crop['planted_area']
            if crop['potential'] is None:
                factor = crop['growth_sum'] / max(1, crop['growth_count'])
                establishment = min(1, crop['sow_work'] / max(.001, area))
                tending = min(1, crop['tend_work'] / max(.001, area * 2))
                crop['potential'] = area * getattr(region, 'crop_yield_per_area', YIELD_PER_AREA) * factor * establishment * (.4 + .6 * tending)
            fraction = min(1, crop['harvest_work'] / max(.001, area * 1.5))
            units = max(0, crop['potential'] * fraction - crop['harvested'])
            if units > 0:
                units = create(region, farm, units, kind='harvest', farm_id=key,
                               actual_work=supplied, potential=crop['potential'])
                crop['harvested'] += units
                farm['harvest_total'] += units
                totals[Goods.food] += units
                seed_target = farm['area'] * SEED_PER_AREA
                reserve(region, farm, 'seed', seed_target)
                if operator is not None:
                    business = getattr(operator, 'company_owned', None)
                    recipient = business if business is not None and business.output == Goods.food and not getattr(business, 'business_closed', False) else operator
                    transferred = transfer(region, farm, recipient, balance(farm), kind='harvest_withdrawal')
                    region.production_receipts.append({'turn': turn, 'person_id': recipient.id,
                                                      'good': Goods.food, 'quantity': transferred,
                                                      'farm_id': key})
                    from economy.actor_accounts import record as economic
                    economic(region, 'production', recipient_id=recipient.id, good=Goods.food, quantity=units)
                from run_trace import emit
                eid = emit(region, kind='crop_harvest', record_class='outcome', phase='production',
                           subject={'type': 'agent', 'id': farm['operator_id'], 'tile': region.name, 'good': 'food'},
                           metric_id='goods.production', unit='units', before=0, after=units,
                           formula_id='agriculture.harvest.v2', inputs={'farm_id': key, **crop,
                               'harvested_before': crop['harvested'] - units,
                               'harvest_required_work': crop['planted_area'] * 1.5})
                if eid:
                    receipts.setdefault(Goods.food, []).append(eid)
            if p == 7:
                lost = max(0, crop['potential'] - crop['harvested'])
                record(region, 'unharvested_crop_loss', lost, farm_id=key, physical_stock_loss=False)
                crop['closed'] = True
        if operator is not None and supplied > 0:
            from engineering import record_operation
            record_operation(region, operating_producer(operator), Goods.food, supplied, farm['area'], turn)
            from abundance import learn
            for pid, row in work_rows.items():
                work = row.get('activities', {}).get(key, 0)
                if work > 0 and pid in people:
                    learn(region, people[pid], Goods.food, work, turn)


def farm_return(region, person, turn):
    farms = [f for f in getattr(region, 'farms', {}).values() if f['operator_id'] == person.id]
    if not farms:
        from livelihood_access import effective_access
        if effective_access(person, region, 'field') <= 0:
            return 0.0, 'no usable farm operation'
    value = sum(max(0, expected_harvest(region, f, turn) - f['area'] * SEED_PER_AREA) for f in farms)
    if value <= 0:
        from livelihood_access import effective_access
        from land_tenure import TenureStatus
        if effective_access(person, region, 'field') > 0:
            plots = [p for p in region.tenure.plots if p.tenure == TenureStatus.COMMONS
                     and (p.plot_id == getattr(person, 'assigned_plot_id', None) or person.id in p.tenant_ids)]
            other = sum(1 for a in region.agents if a.alive and a.output == Goods.food)
            area = sum(p.fraction for p in plots) * getattr(region, 'agricultural_area', 0) / max(1, other + 1)
            value = area * max(0, getattr(region, 'crop_yield_per_area', YIELD_PER_AREA) * yield_factor(region, person, turn) - SEED_PER_AREA)
    return value / 10 * region.recipes[Goods.food]['price'], 'seasonal crop return and retained food'
