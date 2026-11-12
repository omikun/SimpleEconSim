"""Canonical food phase boundaries shared by regional engine clients."""
from goods import Goods
from world_config import gameplay_flags_for


def prepare_region(region, turn):
    """Declare opening stocks and located institutions before auditing the turn."""
    from agriculture import initialize
    region._last_turn = turn
    if not hasattr(region, 'agricultural_area'):
        from households import human
        population = next((n for n in getattr(region, 'total_population', ()) if n > 0),
                          sum(human(a) for a in region.agents))
        region.agricultural_area = .6 * population
        if not hasattr(region, 'commons_capacity'):
            region.commons_capacity = .8 * population
        region.food_migration_assumptions = {
            'land_basis_population': population, 'area_per_person': .6,
            'standing_crops_created': False, 'food_created': False}
    from supply_rights import allocate_seasonal_water
    if getattr(region, 'water_allocation_turn', None) != turn:
        allocate_seasonal_water(region, turn)
    if getattr(region, 'gov', None) is not None:
        region.gov.bind_food_site(region)
    if getattr(region, 'charity', None) is not None:
        region.charity.bind_food_site(region)
    initialize(region, turn)
    from agriculture import ensure_operations
    ensure_operations(region, turn)


def begin_turn(region, turn):
    if getattr(region, '_food_prepared_turn', None) == turn:
        return
    prepare_region(region, turn)
    from households import rebuild
    from food_accounts import stocks, consume, balance, reserve
    region._food_prepared_turn = turn
    region._food_opening_stock = stocks(region)['total']
    rebuild(region, turn)
    spoilage_enabled = gameplay_flags_for(region).food_spoilage
    for person in region.agents:
        queued = max(0, getattr(person, 'emergency_food_units', 0))
        if queued:
            person.inv_add(Goods.food, queued)
            person.emergency_food_units = 0
        if spoilage_enabled:
            remainders = dict(getattr(person, 'food_loss_remainders', {}))
            for good, rate in ((Goods.food, .001), (Goods.prepared_food, .02)):
                exact = balance(person, good) * rate + remainders.get(good.name, 0)
                units = int(exact * 1000) / 1000
                remainders[good.name] = exact - units
                if units:
                    consume(region, person, units, kind='storage_loss', good=good)
            person.food_loss_remainders = remainders
    for farm in region.farms.values():
        if spoilage_enabled:
            exact = balance(farm) * .0005 + farm.get('loss_remainder', 0)
            units = int(exact * 1000) / 1000
            farm['loss_remainder'] = exact - units
            if units:
                consume(region, farm, units, kind='storage_loss')
        reserve(region, farm, 'seed', farm['area'] * 6)


def prepare_work(region, turn, *, production_enabled=True):
    if getattr(region, '_food_work_prepared_turn', None) == turn:
        return
    region._food_work_prepared_turn = turn
    if not hasattr(region, 'seasonal_work_orders'):
        region.seasonal_work_orders = []
    if production_enabled:
        from agriculture import begin_crops, commit_crop_inputs
        begin_crops(region, turn)
        commit_crop_inputs(region, turn)
    # Private farms purchase temporary work just as public programs do. Offers
    # share the same physical work ledger and are limited by owned cash.
    from agriculture import requirements
    actors = {a.id: a for a in region.agents if a.alive}
    programs = getattr(region, 'production_programs', ()) if production_enabled else ()
    for program in programs:
        if (program['kind'] == 'seasonal_hiring' and program['status'] == 'active'
                and program['starts_turn'] <= turn <= program['expires_turn']):
            left = max(0, program['quantity'] - program['delivered'])
            existing = {o['farm_id'] for o in region.seasonal_work_orders
                        if o['program_id'] == program['id'] and o['turn'] == turn}
            for key, requested in requirements(region, turn).items():
                if key not in existing and requested > 0 and left > 0:
                    quantity = min(left, requested)
                    region.seasonal_work_orders.append({'turn': turn, 'program_id': program['id'],
                        'farm_id': key, 'payer_id': program['escrow_id'],
                        'pay_rate': program['unit_ceiling'], 'quantity': quantity,
                        'delivered': 0.0, 'completed': False})
                    left -= quantity
    rate = (4 * region.recipes[Goods.food]['price'] + .5 * region.recipes[Goods.wood]['price']) * 10 / 4.5
    crop_needs = requirements(region, turn) if production_enabled else {}
    for key, requested in crop_needs.items():
        farm = region.farms[key]
        operator = actors.get(farm['operator_id'])
        company = operator if getattr(operator, 'is_corporation', False) else getattr(operator, 'company_owned', None)
        payer = company if company is not None and company.output == Goods.food and not getattr(company, 'business_closed', False) else operator
        payroll = sum(max(0, getattr(a, 'wage', 0)) for a in getattr(payer, 'employees', ()) if a.alive)
        cash = max(0, getattr(payer, 'cash', 0) - payroll)
        if payer is not None and requested > 0 and payer.cash > 0:
            region.seasonal_work_orders.append({'turn': turn, 'program_id': None,
                'farm_id': key, 'payer_id': payer.id, 'pay_rate': rate,
                'quantity': min(requested, cash / max(.01, rate)),
                'delivered': 0.0, 'completed': False})
    nation = getattr(region, 'owner_nation', None)
    if nation is not None:
        from innovation import get_innovation_system
        get_innovation_system().prepare_region_engineering(nation, region, turn)
    from work_allocation import begin, assign
    from engineering import production_work_share
    begin(region, turn)
    for person in region.agents:
        assign(region, person, 'engineering', production_work_share(person, turn))


def finish_turn(region, turn):
    from food_storage import enforce
    enforce(region)
    from food_outlook import close_turn
    close_turn(region, turn)
