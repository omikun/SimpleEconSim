"""Turn opening and labor market decisions for a region."""
from goods import Goods
from random_cache import rand
import region_labor as _labor
import region_logistics as _logistics
import land_rent as _rent


def run(region, t, flags, legacy):
    from micro.region.stepper import _profession_population_members, record_start, audit_cash
    from food_economy import begin_turn as begin_food_turn
    begin_food_turn(region, t)
    if (getattr(region, '_run_trace', None) is not None
            and not hasattr(region, '_trace_profession_members')):
        region._trace_profession_members = _profession_population_members(region)
    from supply_rights import expire_land_leases
    expire_land_leases(region, t)
    for firm in getattr(region, 'agents', []):
        if getattr(firm, 'supply_pause_until', 0) and t >= firm.supply_pause_until:
            firm.max_employees = int(getattr(firm, '_supply_prior_max_employees',
                                             getattr(firm, 'max_employees', 0)))
            firm.supply_pause_until = 0

    from nutrition import update_dependent_need
    for person in region.agents:
        update_dependent_need(person, t)

    rand.reset()
    food_price = region.recipes[Goods.food]['price']
    wood_price = region.recipes[Goods.wood]['price']
    furn_price = region.recipes[Goods.furniture]['price']
    from secular_climate import get_secular_climate
    region.secular_climate = get_secular_climate(t)
    col_clim = region.secular_climate.get('col_modifier', 1.0)
    col_before = getattr(region, 'cost_of_living', None)
    region.cost_of_living = max(0.1, (4 * food_price + 1 * wood_price + 0.25 * furn_price)
                                * region.col_multiplier * col_clim)
    from run_trace import emit
    emit(region, kind='cost_of_living_calculation', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='living.cost_of_living', unit='local_currency_per_basket',
         before=col_before, after=region.cost_of_living,
         formula_id='living.basket_prices_climate.v1',
         inputs={'food_price': food_price, 'wood_price': wood_price,
                 'furniture_price': furn_price, 'basket_weights': [4, 1, 0.25],
                 'basket_component_goods': ['food', 'wood', 'furniture'],
                 'basket_component_prices': {
                     'food': food_price, 'wood': wood_price,
                     'furniture': furn_price},
                 'weighted_reference_price': (4 * food_price + wood_price
                                              + 0.25 * furn_price),
                 'component_coverage': ['food', 'wood', 'furniture'],
                 'price_basis': 'displayed_recipe_reference',
                 'currency': getattr(region, 'home_currency', None),
                 'regional_multiplier': region.col_multiplier,
                 'climate_multiplier': col_clim}, constraints={'floor': 0.1})
    region.food_price = food_price
    region.all_goods_price = food_price + wood_price + furn_price
    record_start(region)
    from economy.actor_accounts import begin_turn
    begin_turn(region, t)
    audit_cash(region, t, "step_start")

    # A labor-law petition takes effect only after its later decision window.
    from labor_laws import decide_labor_laws
    decide_labor_laws(region, t)
    from market_concessions import decide_concession_petitions
    decide_concession_petitions(region, t)
    from supply_proposals import decide as decide_supply_proposals
    decide_supply_proposals(region, t)

    # Named rent and fixed cash tax claims are assessed before workers compare offers.
    from livelihood_access import assess_obligation, settle_obligations
    if flags.land_rent:
        _rent.assess_rents(region, t)
    fixed_tax = (max(0.0, float(getattr(region, 'cash_tax_per_person', 0.0)))
                 if flags.taxation else 0.0)
    if fixed_tax and getattr(region, 'gov', None) is not None:
        for person in sorted(region.agents, key=lambda a: a.id):
            if (person.alive and not person.is_trader and not person.is_government
                    and not person.is_corporation and not getattr(person, 'is_lord', False)
                    and not getattr(person, 'military_unit_id', None)
                    and not (getattr(person, 'is_native_child', False) and person.age(t) < 14)):
                assess_obligation(region, person.id, region.gov.agent.id, 'cash_tax',
                                  fixed_tax, t)

    # Repoint traders to best-margin neighbor
    if flags.regional_trade:
        _logistics.repoint_traders(region)

    # Clear per-agent wealth caches and reset food source counters
    for a in region.agents:
        a.food_foraged = 0
        a.temporary_work_share = 0.0
        a.food_purchased = 0
        a.clear_wealth_cache()

    # Charity donations
    if legacy:
        region.charity.collect_donations(t, region.agents, region.bank,
                                         regions=(region,))
        audit_cash(region, t, "charity_done")

    # Freeze profession counts before any hiring or founder conversion.
    from career_transitions import begin_turn as begin_career_turn, step_careers
    begin_career_turn(region, t)
    new_companies = _labor.run_labour(
        region, t, defer_careers=True, market_enabled=flags.labor_market,
        wage_quotes_enabled=flags.wage_quotes)
    if new_companies:
        region.agents.extend(new_companies)

    # Sven Beckert Capitalist Propagation: Elite Multi-Step Planning & Labor Mobility
    if not hasattr(region, 'elite_planner'):
        from economy import EliteCapitalistPlanner
        region.elite_planner = EliteCapitalistPlanner()
    if not hasattr(region, 'labor_scheduler'):
        from economy import LaborMobilityScheduler
        region.labor_scheduler = LaborMobilityScheduler()

    planner_enabled = flags.elite_planning
    mobility_enabled = flags.career_mobility
    region.elite_planner.record_planning_phase_gate(region, t, planner_enabled)
    if planner_enabled:
        has_new_items = region.elite_planner.check_new_market_items(region)
        for a in list(region.agents):
            if region.elite_planner.should_run_planning(a, region, t, has_new_items):
                region.elite_planner.plan_and_execute_elite(a, region, t)
    step_careers(region, t, independent=mobility_enabled)
    audit_cash(region, t, "labour_done")
