"""
micro/region/stepper.py — Economy stepping, lifecycle simulation, and telemetry logging for regions.
"""

from __future__ import annotations
import math
from statistics import mean
from typing import TYPE_CHECKING, List, Dict, Any

from goods import Goods, profession
from econsim_states import (
    probability_birth, birth_gap, max_career_switches, starvation_limit,
)
from logger import loginfo, logwarning
from random_cache import rand
from micro.region.helpers import compute_gini, get_total_cash

# Subsystem modules
import region_labor as _labor
import region_production as _prod
import region_market as _market
import region_finance as _fin
import region_logistics as _logistics
import region_factions as _factions
import foraging as _forage
import feudal_tribute as _tribute
import land_rent as _rent
import social_class as _sclass


def step_economy(region: Any, t: int):
    """Per-tile economy and institutional flows."""
    legacy = getattr(region, 'province', None) is None

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
                 'regional_multiplier': region.col_multiplier,
                 'climate_multiplier': col_clim}, constraints={'floor': 0.1})
    region.food_price = food_price
    region.all_goods_price = food_price + wood_price + furn_price
    record_start(region)
    audit_cash(region, t, "step_start")

    # A labor-law petition takes effect only after its later decision window.
    from labor_laws import decide_labor_laws
    decide_labor_laws(region, t)

    # Named rent and fixed cash tax claims are assessed before workers compare offers.
    from livelihood_access import assess_obligation, settle_obligations
    _rent.assess_rents(region, t)
    fixed_tax = max(0.0, float(getattr(region, 'cash_tax_per_person', 0.0)))
    if fixed_tax and getattr(region, 'gov', None) is not None:
        for person in sorted(region.agents, key=lambda a: a.id):
            if (person.alive and not person.is_trader and not person.is_government
                    and not person.is_corporation and not getattr(person, 'is_lord', False)
                    and not getattr(person, 'military_unit_id', None)):
                assess_obligation(region, person.id, region.gov.agent.id, 'cash_tax',
                                  fixed_tax, t)

    # Repoint traders to best-margin neighbor
    _logistics.repoint_traders(region)

    # Clear per-agent wealth caches and reset food source counters
    for a in region.agents:
        a.food_foraged = 0
        a.food_purchased = 0
        a.clear_wealth_cache()

    # Charity donations
    if legacy:
        region.charity.collect_donations(t, region.agents, region.bank)
        audit_cash(region, t, "charity_done")

    # Labor market
    new_companies = _labor.run_labour(region, t)
    if new_companies:
        region.agents.extend(new_companies)

    # Sven Beckert Capitalist Propagation: Elite Multi-Step Planning & Labor Mobility
    if not hasattr(region, 'elite_planner'):
        from economy import EliteCapitalistPlanner
        region.elite_planner = EliteCapitalistPlanner()
    if not hasattr(region, 'labor_scheduler'):
        from economy import LaborMobilityScheduler
        region.labor_scheduler = LaborMobilityScheduler()

    if not getattr(region, 'scenario_owner_policy', False):
        has_new_items = region.elite_planner.check_new_market_items(region)
        for a in list(region.agents):
            if region.elite_planner.should_run_planning(a, region, t, has_new_items):
                region.elite_planner.plan_and_execute_elite(a, region, t)
        region.labor_scheduler.step_labor_cohort(region, t)
    audit_cash(region, t, "labour_done")

    # Workplace participation must be decided before food allocation and output.
    # Existing strike records are stored by firm ID and survive save/load.
    from labor_resistance import step_workplace_resistance
    res_info = step_workplace_resistance(region, t)
    region.strikers_log.append(res_info['strikers'])
    region.broken_machinery_log.append(res_info['broken_machinery'])
    region.sabotage_log.append(res_info['smashed_this_turn'])
    audit_cash(region, t, "resistance_done")

    # Workers allocate this turn to paid work or subsistence foraging, not both.
    _forage.forage_tile(region, t)

    # Capital goods machinery depreciation (operational wear-and-tear)
    from economy import apply_machinery_depreciation
    apply_machinery_depreciation(region, t)

    # Production
    from collective_action import record_production
    firm_inventory_before = {a.id: a.inv_get(a.output, 0) for a in region.agents
                             if a.alive and a.is_corporation}
    _prod.produce(region, t)
    record_production(region, t, firm_inventory_before)
    audit_cash(region, t, "produce_done")

    # Feudal tribute: lords collect in-kind share of harvest from serfs
    tribute_data = _tribute.collect_tribute(region, t)
    tribute_val = 0.0
    if tribute_data:
        for lord_id, goods_dict in tribute_data.items():
            for g, qty in goods_dict.items():
                price = region.food_price if g == Goods.food else region.recipes.get(g, {}).get('price', 2.0)
                tribute_val += qty * price
    region.tribute_collected_log.append(tribute_val)

    # Crop liens and share tenancy claim only this turn's independently produced harvest.
    from crop_credit import settle_crop_liens, settle_crop_shares
    settle_crop_liens(region, t)
    settle_crop_shares(region, t)

    # Trade & Route export posting
    _market.trade(region, t)
    _logistics.post_exports_to_route(region)
    audit_cash(region, t, "trade_done")

    # Wages & Profits
    from collective_action import record_payroll_and_review
    worker_cash_before = {a.id: a.cash for a in region.agents
                          if a.alive and not a.is_corporation}
    _fin.pay_wages(region, t)
    record_payroll_and_review(region, t, worker_cash_before)
    _fin.redeem_company_scrip(region, t)
    audit_cash(region, t, "wages_done")

    _fin.distribute_profits(region, t)
    audit_cash(region, t, "profits_done")

    # Settle named claims after wages; receipts move debtor cash to the named creditor.
    claim_events = settle_obligations(region, t)
    rent_coll = sum(e['paid'] for e in claim_events if e['origin'] == 'rent')
    rent_arr = sum(c.balance for c in getattr(region, 'cash_obligations', [])
                   if c.origin == 'rent' and c.status == 'active')
    region.rent_collected_log.append(rent_coll)
    region.rent_arrears_log.append(rent_arr)
    from run_trace import emit
    rent_settlements = [event for event in claim_events if event['origin'] == 'rent']
    emit(region, kind='rent_collection_summary', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='finance.rent_collected', unit='local_currency',
         after=rent_coll, formula_id='rent.obligation_settlement.v1',
         inputs={'paid_claims': rent_settlements,
                 'active_rent_arrears': rent_arr,
                 'active_rent_claim_count': sum(
                     1 for claim in getattr(region, 'cash_obligations', [])
                     if claim.origin == 'rent' and claim.status == 'active')})
    emit(region, kind='rent_arrears_summary', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='finance.rent_arrears', unit='local_currency',
         after=rent_arr, formula_id='rent.active_obligations.v1',
         inputs={'active_rent_claims': [
             {'obligation_id': claim.id, 'debtor_id': claim.debtor_id,
              'creditor_id': claim.creditor_id, 'balance': claim.balance,
              'due_turn': claim.due_turn}
             for claim in getattr(region, 'cash_obligations', [])
             if claim.origin == 'rent' and claim.status == 'active']})
    pasture_f = region.tenure.pasture_fraction if hasattr(region, 'tenure') and region.tenure else 0.0
    region.pasture_fraction_log.append(pasture_f)
    audit_cash(region, t, "rent_done")

    # Unpaid claims become named cases and cannot resolve until a later turn.
    from labor_cases import process_default_cases
    process_default_cases(region, t)

    # Migrate legacy survey claims; new claims are handled by the obligation ledger.
    from enclosure import step_enclosure_survey_debts
    survey_evs = step_enclosure_survey_debts(region, t)
    audit_cash(region, t, "survey_debts_done")

    # Tax
    record_delta(region)
    _fin.collect_tax(region, t)
    if len(region.tax_distribution_log) < len(region.rent_collected_log):
        region.tax_distribution_log.append({'total': 0.0, 'municipal': 0.0, 'provincial': 0.0, 'national': 0.0})
    audit_cash(region, t, "tax_done")

    log_gdp(region)

    # Surplus value & labor metrics (P2.1)
    from labor_contract import aggregate_tile_surplus
    surplus_stats = aggregate_tile_surplus(region)
    region.avg_shift_hours_log.append(surplus_stats['avg_shift_hours'])
    region.surplus_value_log.append(surplus_stats['total_surplus_value'])
    region.rate_of_exploitation_log.append(surplus_stats['avg_rate_of_exploitation'])

    if t > 0 and t % 10 == 0:
        _fin.recalculate_multipliers(region)

    # Demographics & Lifecycle
    prior_agents = list(region.agents)
    next_agents = live(region, t)
    surviving_ids = {a.id for a in next_agents}
    for firm in prior_agents:
        if not getattr(firm, 'is_corporation', False):
            continue
        retained = []
        for worker in getattr(firm, 'employees', []):
            if getattr(worker, 'alive', True) and worker.id in surviving_ids:
                retained.append(worker)
            else:
                if getattr(worker, 'employer', None) is firm:
                    worker.employer = None
                agreement = getattr(worker, 'labor_agreement', None)
                if agreement is not None:
                    agreement.active = False
        firm.employees[:] = retained
    from livelihood_access import remove_access
    for departed in prior_agents:
        if not getattr(departed, 'alive', True) and departed.id not in surviving_ids:
            remove_access(region, departed.id)
            for plot in getattr(getattr(region, 'tenure', None), 'plots', []):
                if departed.id in plot.tenant_ids:
                    plot.tenant_ids.remove(departed.id)
    region.agents = next_agents
    region.trader_agents = [a for a in region.agents if a.is_trader]
    from collective_action import record_essential_needs
    record_essential_needs(region, t)
    audit_cash(region, t, "live_done")

    # Dynamic social class evaluation (P1.4)
    class_dist = _sclass.update_tile_social_classes(region)
    region.social_class_log.append(class_dist)

    # Parish Workhouse & Vagrancy Enforcement (Phase 1)
    from workhouse import step_workhouse, get_workhouse_inmates
    workhouse_evs = step_workhouse(region, t)
    inmates_count = len(get_workhouse_inmates(region))
    region.workhouse_inmates_log.append(inmates_count)
    audit_cash(region, t, "workhouse_done")

    # Alienation, Health Attrition & Despair (P2.2)
    from alienation import step_tile_alienation
    step_tile_alienation(region, t)

    # Metabolic Rift & Externalities Engine (P3)
    from externalities import step_tile_externalities
    step_tile_externalities(region, t)

    # Epidemics & Medical Economics (P3)
    from disease import step_tile_diseases
    step_tile_diseases(region, t)

    # True Cost & Externalities Ledger Finalization
    try:
        from economy.true_cost_ledger import get_true_cost_ledger
        scen_id = getattr(getattr(region, 'gov', None), 'scenario_id', None)
        get_true_cost_ledger().seal_turn(t, scenario_id=scen_id)
    except Exception:
        pass

    # Charity food distribution
    if legacy:
        region.charity.distribute_food(t, region.agents)
        audit_cash(region, t, "charity_food_done")

    # Metrics, Factions & Unrest
    log_metrics(region, t)
    region.migration_intent_log.append(_logistics.migration_intent_score(region))
    _factions.step_factions(region, t)

    from unrest import step_unrest
    ev = step_unrest(region, t)
    region.unrest_flag = ev['stage'] != 'calm'
    if legacy:
        region.gov.seal_income(t)

    region.total_population.append(sum(v[-1] for v in region.population_log.values()))
    emit(region, kind='population_count_calculation', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='people.population', unit='people',
         before=region.total_population[-2] if len(region.total_population) > 1 else None,
         after=region.total_population[-1], formula_id='population.sum_professions.v1',
         inputs={'by_profession': {g.name if hasattr(g, 'name') else str(g): history[-1]
                                   for g, history in region.population_log.items() if history}})
    region.cost_of_living_log.append(region.cost_of_living)
    region.tenure_log.append(region.tenure.commons_access)
    region.food_foraged_log.append(sum(getattr(a, 'food_foraged', 0) for a in region.agents))
    region.food_purchased_log.append(sum(getattr(a, 'food_purchased', 0) for a in region.agents))
    region.bank_cash_log.append(region.bank.equity)
    if getattr(region.bank, 'is_frozen', False):
        region.bank.frozen_turns += 1
        for a, dep in list(getattr(region.bank, 'deposits', {}).items()):
            if dep > 0 and hasattr(a, 'despair'):
                a.despair = min(1.0, getattr(a, 'despair', 0.0) + 0.02)
    region.total_cash_log.append(total_cash(region))
    log_population_rate(region)

    for p in region.goods:
        for g in region.goods:
            region.bought_log[p][g].append(0)

    if len(region.total_cash_log) >= 2:
        difference = math.fabs(region.total_cash_log[-2] - region.total_cash_log[-1])
        if difference > 1e-8:
            logwarning(t, f"Region '{region.name}' cash: {region.total_cash_log[-2]:.2f}->{region.total_cash_log[-1]:.2f} (d={difference:.2f})")

    if t % 100 == 0:
        circulating_cash = sum(a.cash for a in region.agents)
        print(f"--- Region '{region.name}' T={t}: circ=${circulating_cash:.0f}, "
              f"dep=${region.bank.total_deposits:.0f}, "
              f"liab=${region.bank.total_liabilities:.0f}, "
              f"r={region.bank.total_deposits/max(1,circulating_cash):.1f}x")


def audit_cash(region: Any, t: int, label: str):
    """Log all cash components when anomalies occur."""
    agent_cash = sum(a.cash for a in region.agents)
    deposits = region.bank.total_deposits
    liabilities = region.bank.total_liabilities
    bank_equity = region.bank.equity
    total = agent_cash + bank_equity
    if total < 0 or agent_cash < 0 or deposits < 0 or liabilities < 0:
        print(f"  CASH AUDIT [{label}] T={t}: "
              f"agents=${agent_cash:.0f} "
              f"deposits=${deposits:.0f} "
              f"liabilities=${liabilities:.0f} "
              f"bank_eq=${bank_equity:.0f} "
              f"TOTAL=${total:.0f}")


def record_start(region: Any):
    for a in region.agents:
        a._start_cash = a.cash
        a._start_deposits = region.bank.deposits.get(a, 0)


def record_delta(region: Any):
    for a in region.agents:
        a._delta_cash = a.cash - a._start_cash
        a._delta_deposits = region.bank.deposits.get(a, 0) - a._start_deposits


def total_cash(region: Any) -> float:
    """Total cash including agents, bank equity, and charity's hand cash."""
    return get_total_cash(region.agents, region.bank) + region.charity.agent.cash


def live(region: Any, t: int):
    """Run life-cycle using LiveContext."""
    import econsim_live as _lm
    from econsim_live import LiveContext

    ctx = LiveContext(
        recipes=region.recipes,
        goods=region.goods,
        governments=[region.gov],
        default_gov=region.gov,
        hungry_log=region.hungry_log,
        dead_pop=region.dead_pop,
        deadstarve_pop=region.dead_starved_population,
        production_log=region.production_log,
        starve_limit=starvation_limit,
        profession=profession,
        max_career_switches=max_career_switches,
        p_birth=probability_birth,
        birth_gap=birth_gap,
        bank=region.bank,
        most_demand=getattr(region, 'most_demand', None),
        charity=region.charity,
        max_agents=region.max_agents,
        carrying_capacity=region.max_agents,
        cost_of_living=region.cost_of_living,
        food_price=region.food_price,
        source_region=region,
    )
    result = _lm.Live(t, region.agents, context=ctx)

    # Post-processing: trader exit + inheritance + career switching
    _logistics.process_trader_exits(region, t, result)

    if (region.neighbors or region.destination_region is not None) and t > 0:
        has_arbitrage = any(
            region.recipes[g]['price'] < other.recipes[g]['price'] * 0.95
            for g in [Goods.wood, Goods.furniture]
            for other in (list(region.neighbors.values()) or [region.destination_region])
        )
        trader_count = sum(1 for a in result if a.is_trader)
        max_traders = int(len(result) * 0.2)
        for agent in result:
            if agent.is_corporation:
                continue
            parent = agent.parent
            if (parent is not None and parent.is_trader
                    and not agent.is_trader
                    and trader_count < max_traders
                    and rand.random() < 0.5):
                _logistics.make_trader_internal(region, agent)
                trader_count += 1
                loginfo(t, f"{agent.name()} inherited trader from parent {parent.name()}")
            elif (not agent.is_trader
                  and has_arbitrage
                  and (agent.cash < 20 or agent.hungry_steps > 0)
                  and trader_count < max_traders
                  and rand.random() < 0.003):
                _logistics.make_trader_internal(region, agent)
                trader_count += 1
                loginfo(t, f"{agent.name()} switched to trader (cash=${agent.cash:.0f})")

    return result


def log_gdp(region: Any):
    total = 0
    terms = {}
    for g in region.goods:
        if g != Goods.gov:
            value = region.production_log[g][-1] * region.recipes[g]['price']
            total += value
            region.gdp_by_profession_log[g].append(value)
            terms[g.name if hasattr(g, 'name') else str(g)] = {
                'units': region.production_log[g][-1],
                'reference_price': region.recipes[g]['price'], 'value': value}
    region.gdp_log.append(total)
    from run_trace import emit
    emit(region, kind='nominal_gdp_calculation', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='economy.gdp_nominal', unit='local_currency_per_turn',
         before=region.gdp_log[-2] if len(region.gdp_log) > 1 else None,
         after=total, formula_id='gdp.sum_output_times_reference_price.v1',
         inputs={'goods': terms})


def log_metrics(region: Any, t: int):
    agents = region.agents
    by_output = {g: [] for g in region.goods}
    by_output['trader'] = []
    food_agents = []
    total_cash_by_output = {g: 0.0 for g in region.goods}
    total_inv_by_output = {g: 0.0 for g in region.goods if g != Goods.gov}
    total_inv_trader = 0.0

    for a in agents:
        if a.is_trader:
            continue
        if a.output == Goods.food:
            food_agents.append(a)
            by_output[Goods.food].append(a)
            total_cash_by_output[Goods.food] += a.cash
            if Goods.food != Goods.gov:
                total_inv_by_output[Goods.food] += a.inv_get(Goods.food, 0)
        elif a.output != Goods.gov and a.output in by_output:
            o = a.output
            by_output[o].append(a)
            total_cash_by_output[o] += a.cash
            if o != Goods.gov:
                total_inv_by_output[o] += a.inv_get(o, 0)

    trader_agents = region.trader_agents
    by_output['trader'] = trader_agents
    for a in trader_agents:
        total_inv_trader += a.inv_get(Goods.food, 0) + a.inv_get(Goods.wood, 0) + a.inv_get(Goods.furniture, 0)

    compute_gini_this_turn = (t % 10 == 0)

    for g in region.goods:
        grp = by_output[g]
        pop = len(grp)
        region.population_log[g].append(pop)
        region.cash_log[g].append(total_cash_by_output.get(g, 0.0))
        if compute_gini_this_turn:
            region.gini_log[g].append(compute_gini(grp, g))
        else:
            region.gini_log[g].append(region.gini_log[g][-1] if region.gini_log[g] else 0)
        if g != Goods.gov:
            region.inventory_log[g].append(total_inv_by_output.get(g, 0.0))
            from run_trace import emit
            emit(region, kind='producer_inventory_total', record_class='calculation',
                 subject={'type': 'tile', 'id': region.name, 'good': g.name},
                 metric_id='goods.producer_inventory', unit='units',
                 after=region.inventory_log[g][-1],
                 formula_id='inventory.sum_producer_holdings.v1',
                 inputs={'holdings': [{'agent_id': a.id, 'units': a.inv_get(g, 0)}
                                     for a in grp]})
            non_prod = [a.inv_get(g, 0) for a in agents if a.output != g and not a.is_trader]
            region.per_capita_inventory[g].append(mean(non_prod) if non_prod else 0)
            region.price_log[g].append(region.recipes[g]['price'])

    tr_len = len(trader_agents)
    region.population_log['trader'].append(tr_len)
    region.cash_log['trader'].append(sum(a.cash for a in trader_agents))
    if compute_gini_this_turn:
        region.gini_log['trader'].append(compute_gini(trader_agents, Goods.food))
    else:
        region.gini_log['trader'].append(region.gini_log['trader'][-1] if region.gini_log['trader'] else 0)
    region.hungry_log['trader'].append(sum(1 for a in trader_agents if a.hungry_steps > 0))
    region.inventory_log['trader'].append(total_inv_trader)
    non_trader = [a.inv_get(Goods.food, 0) for a in trader_agents if a.output != Goods.food]
    region.per_capita_inventory['trader'].append(mean(non_trader) if non_trader else 0)
    region.production_log['trader'].append(0)
    region.gdp_by_profession_log['trader'].append(0)

    region.trader_cash_log.append(sum(a.cash for a in trader_agents))
    pipeline_qty = 0
    for rt in _logistics.all_routes(region):
        pipeline_qty += sum(
            rt.in_transit_total(g)
            for g in [Goods.food, Goods.wood, Goods.furniture]
        )
    region.pipeline_depth_log.append(pipeline_qty)
    infant_fatalities = getattr(region, 'infant_fatalities_this_turn', 0)
    region.infant_fatalities_log.append(infant_fatalities)
    from run_trace import emit
    emit(region, kind='infant_fatalities_turn_total', record_class='calculation',
         phase='demographics', subject={'type': 'tile', 'id': region.name},
         metric_id='health.infant_fatalities', unit='people_per_turn',
         before=0, after=infant_fatalities,
         formula_id='demographics.infant_fatalities_sum.v1',
         inputs={'deaths_recorded_during_turn': infant_fatalities})
    region.infant_fatalities_this_turn = 0


def log_population_rate(region: Any):
    if len(region.total_population) >= 10:
        pop_10_ago = region.total_population[-10]
        current_pop = region.total_population[-1]
        population_change_pct = ((current_pop - pop_10_ago) / pop_10_ago * 100) if pop_10_ago > 0 else 0
    else:
        population_change_pct = 0
    region.population_change_rate_log.append(population_change_pct)
