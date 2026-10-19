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


def _profession_population_members(region: Any) -> dict:
    """Capture the agents included by the local profession headcount rule."""
    members = {getattr(group, 'name', str(group)): {} for group in region.goods}
    members['trader'] = {}
    for agent in getattr(region, 'agents', ()):
        if getattr(agent, 'is_trader', False):
            continue
        output = getattr(agent, 'output', None)
        if output == Goods.food:
            group_name = Goods.food.name
        elif output != Goods.gov and output in region.goods:
            group_name = getattr(output, 'name', str(output))
        else:
            continue
        members.setdefault(group_name, {})[getattr(agent, 'id', None)] = agent
    for agent in getattr(region, 'trader_agents', ()):
        members['trader'][getattr(agent, 'id', None)] = agent
    return members


def sample_effective_workday_cap(region: Any) -> float:
    """Record the workday cap that governed this tile's production turn."""
    cap = float(getattr(region, 'workday_cap',
                        getattr(region, 'max_workday_hours', 16.0)))
    history = getattr(region, 'workday_cap_log', None)
    if history is None:
        history = []
        region.workday_cap_log = history
    before = history[-1] if history else None
    history.append(cap)
    from run_trace import emit
    emit(region, kind='effective_workday_cap_sample',
         record_class='calculation', phase='local',
         subject={'type': 'tile', 'id': region.name},
         metric_id='labor.statutory_workday', unit='hours',
         before=before, after=cap,
         formula_id='labor.effective_workday_cap_sample.v1',
         inputs={'effective_workday_cap': cap,
                 'workday_cap_field': 'workday_cap',
                 'statute_display_value': float(getattr(
                     region, 'max_workday_hours', cap)),
                 'sample_point': 'effective cap state recorded for this turn'})
    return cap


def step_economy(region: Any, t: int):
    """Per-tile economy and institutional flows."""
    legacy = getattr(region, 'province', None) is None
    region._last_turn = t
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
    _rent.assess_rents(region, t)
    fixed_tax = max(0.0, float(getattr(region, 'cash_tax_per_person', 0.0)))
    if fixed_tax and getattr(region, 'gov', None) is not None:
        for person in sorted(region.agents, key=lambda a: a.id):
            if (person.alive and not person.is_trader and not person.is_government
                    and not person.is_corporation and not getattr(person, 'is_lord', False)
                    and not getattr(person, 'military_unit_id', None)
                    and not (getattr(person, 'is_native_child', False) and person.age(t) < 14)):
                assess_obligation(region, person.id, region.gov.agent.id, 'cash_tax',
                                  fixed_tax, t)

    # Repoint traders to best-margin neighbor
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

    planner_enabled = not getattr(region, 'scenario_owner_policy', False)
    region.elite_planner.record_planning_phase_gate(region, t, planner_enabled)
    if planner_enabled:
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
    from supply_rights import allocate_seasonal_water
    allocate_seasonal_water(region, t)
    firm_inventory_before = {a.id: a.inv_get(a.output, 0) for a in region.agents
                             if a.alive and a.is_corporation}
    _prod.produce(region, t)
    record_production(region, t, firm_inventory_before)
    audit_cash(region, t, "produce_done")

    # Feudal tribute: lords collect in-kind share of harvest from serfs
    tribute_data, tribute_event_ids = _tribute.collect_tribute(
        region, t, return_trace=True)
    tribute_val, _valuation_event_id = _tribute.record_tribute_value(
        region, t, tribute_data, cause_event_ids=tribute_event_ids)
    region.tribute_collected_log.append(tribute_val)

    # Crop liens and share tenancy claim only this turn's independently produced harvest.
    from crop_credit import settle_crop_liens, settle_crop_shares, settle_offtake_contracts
    settle_offtake_contracts(region, t)
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
    _fin.settle_wage_arrears(region, t)
    _fin.redeem_company_scrip(region, t)
    audit_cash(region, t, "wages_done")

    _fin.distribute_profits(region, t)
    audit_cash(region, t, "profits_done")

    # Settle named claims after wages; receipts move debtor cash to the named creditor.
    obligation_settlement_trace_ids = {}
    obligation_payment_trace_ids = {}
    claim_events = settle_obligations(
        region, t,
        settlement_trace_event_ids_by_origin=obligation_settlement_trace_ids,
        payment_trace_event_ids_by_origin=obligation_payment_trace_ids)
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
                     if claim.origin == 'rent' and claim.status == 'active')},
         cause_event_ids=obligation_payment_trace_ids.get('rent'))
    emit(region, kind='rent_arrears_summary', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='finance.rent_arrears', unit='local_currency',
         after=rent_arr, formula_id='rent.active_obligations.v1',
         inputs={'active_rent_claims': [
             {'obligation_id': claim.id, 'debtor_id': claim.debtor_id,
              'creditor_id': claim.creditor_id, 'balance': claim.balance,
              'due_turn': claim.due_turn}
             for claim in getattr(region, 'cash_obligations', [])
             if claim.origin == 'rent' and claim.status == 'active']},
         cause_event_ids=obligation_settlement_trace_ids.get('rent'))
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
    surplus_stats = aggregate_tile_surplus(region, turn=t)
    sample_effective_workday_cap(region)
    region.avg_shift_hours_log.append(surplus_stats['avg_shift_hours'])
    region.surplus_value_log.append(surplus_stats['total_surplus_value'])
    region.rate_of_exploitation_log.append(surplus_stats['avg_rate_of_exploitation'])
    from run_trace import emit
    for metric_id, history, value, unit, kind, formula_id, inputs in (
            ('labor.average_shift_hours', region.avg_shift_hours_log,
             surplus_stats['avg_shift_hours'], 'hours',
             'labor_shift_hours_calculation',
             'labor.weighted_average_shift_hours.v1',
             surplus_stats['avg_shift_hours_inputs']),
            ('labor.exploitation_rate', region.rate_of_exploitation_log,
             surplus_stats['avg_rate_of_exploitation'], 'ratio',
             'labor_exploitation_rate_calculation',
             'labor.surplus_over_variable_capital.v1',
             surplus_stats['exploitation_inputs'])):
        emit(region, kind=kind, record_class='calculation', phase='local',
             subject={'type': 'tile', 'id': region.name}, metric_id=metric_id,
             unit=unit,
             before=history[-2] if len(history) > 1 else None,
             after=float(value), formula_id=formula_id, inputs=inputs)

    surplus_inputs = surplus_stats['surplus_inputs']
    surplus_causes = [row['source_event_id']
                      for row in surplus_inputs['firms']
                      if row.get('included_in_current_turn')
                      and row.get('source_event_id') is not None]
    emit(region, kind='labor_surplus_value_calculation',
         record_class='calculation', phase='local',
         subject={'type': 'tile', 'id': region.name},
         metric_id='labor.surplus_value',
         unit=getattr(region, 'home_currency', None) or 'local_currency',
         before=(region.surplus_value_log[-2]
                 if len(region.surplus_value_log) > 1 else None),
         after=float(surplus_stats['total_surplus_value']),
         formula_id='labor.surplus_value_current_turn.v1',
         inputs=surplus_inputs,
         cause_event_ids=surplus_causes or None)

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
    from run_trace import emit
    class_groups = {
        'serf': ('serf',),
        'tenant': ('tenant',),
        'worker': ('proletarian',),
        'dispossessed': ('dispossessed',),
        'gentry': ('lord', 'landlord'),
        'artisan': ('petty_bourgeois', 'industrialist'),
    }
    previous_classes = (region.social_class_log[-2]
                        if len(region.social_class_log) > 1 else {})
    for group, members in class_groups.items():
        member_class_counts = {
            name: int(class_dist.get(name, 0)) for name in members}
        count = sum(member_class_counts.values())
        before = sum(int(previous_classes.get(name, 0)) for name in members)
        emit(region, kind='social_class_population_calculation',
             record_class='calculation', phase='local',
             subject={'type': 'tile', 'id': region.name,
                      'class_group': group},
             metric_id='society.class_population', unit='people',
             before=before, after=count,
             formula_id='social_class.group_population.v1',
             inputs={'class_group': group, 'member_classes': list(members),
                     'member_class_counts': member_class_counts,
                     'counting_rule': 'sum living agents assigned to member classes'})

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
    audit_cash(region, t, "disease_done")

    # True Cost & Externalities Ledger Finalization
    try:
        from economy.true_cost_ledger import get_true_cost_ledger
        scen_id = getattr(getattr(region, 'gov', None), 'scenario_id', None)
        get_true_cost_ledger().seal_turn(t, scenario_id=scen_id)
    except Exception:
        pass

    # Charity food distribution
    if legacy:
        region.charity.distribute_food(t, region.agents, regions=(region,))
        audit_cash(region, t, "charity_food_done")

    # Metrics, Factions & Unrest
    log_metrics(region, t)
    region.migration_intent_log.append(_logistics.migration_intent_score(region))
    _factions.step_factions(region, t)

    from unrest import step_unrest
    ev = step_unrest(region, t)
    region.unrest_flag = ev['stage'] != 'calm'
    if legacy:
        income_snapshot = region.gov.seal_income(t)
        from government import trace_income_snapshot
        trace_income_snapshot(region.gov, region, income_snapshot, t,
                              scope='tile', member_tiles=[region.name])

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
    plot_composition = [
        {'plot_id': str(plot.plot_id), 'fraction': float(plot.fraction),
         'tenure': getattr(plot.tenure, 'value', str(plot.tenure))}
        for plot in getattr(region.tenure, 'plots', [])]
    commons_access = float(region.tenure.commons_access)
    emit(region, kind='commons_access_calculation', record_class='calculation',
         phase='local', subject={'type': 'tile', 'id': region.name},
         metric_id='land.commons_access', unit='ratio',
         before=region.tenure_log[-2] if len(region.tenure_log) > 1 else None,
         after=commons_access, formula_id='tenure.commons_access_from_plots.v1',
         inputs={'plots': plot_composition, 'no_plot_default': 1.0,
                 'feudal_weight': 1.0, 'leasehold_weight': 0.5,
                 'commons_weight': 1.0, 'enclosed_weight': 0.0,
                 'upper_bound': 1.0})
    for history_name, attr_name, metric_id, kind in (
            ('food_foraged_log', 'food_foraged', 'food.foraged',
             'foraged_food_total'),
            ('food_purchased_log', 'food_purchased', 'food.purchased',
             'purchased_food_total')):
        agent_food_units = [
            {'agent_id': str(agent.id), 'food_units': int(
                getattr(agent, attr_name, 0))}
            for agent in region.agents
            if int(getattr(agent, attr_name, 0)) != 0]
        total_food = sum(row['food_units'] for row in agent_food_units)
        history = getattr(region, history_name)
        history.append(total_food)
        emit(region, kind=kind, record_class='calculation', phase='local',
             subject={'type': 'tile', 'id': region.name}, metric_id=metric_id,
             unit='food_units',
             before=history[-2] if len(history) > 1 else None,
             after=total_food, formula_id='food.source_total.v1',
             inputs={'agent_food_units': agent_food_units,
                     'agent_count': len(region.agents),
                     'contributor_count': len(agent_food_units)})
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

    if getattr(region, 'province', None) is None:
        from economy.actor_accounts import seal_turn
        seal_turn(region, t)

    if t % 100 == 0:
        circulating_cash = sum(a.cash for a in region.agents)
        print(f"--- Region '{region.name}' T={t}: circ=${circulating_cash:.0f}, "
              f"dep=${region.bank.total_deposits:.0f}, "
              f"liab=${region.bank.total_liabilities:.0f}, "
              f"r={region.bank.total_deposits/max(1,circulating_cash):.1f}x")


def audit_cash(region: Any, t: int, label: str):
    """Log all cash components when anomalies occur."""
    current_actor_cash = {a.id: float(a.cash) for a in region.agents}
    if getattr(region, '_actor_cash_phase_turn', None) != int(t):
        region._actor_cash_phase_turn = int(t)
        region._actor_cash_phase_snapshot = current_actor_cash
        region._actor_cash_phase_changes = {}
    else:
        previous_actor_cash = getattr(region, '_actor_cash_phase_snapshot', {})
        phase_changes = getattr(region, '_actor_cash_phase_changes', {})
        for actor_id in set(previous_actor_cash) | set(current_actor_cash):
            change = current_actor_cash.get(actor_id, 0.0) - previous_actor_cash.get(actor_id, 0.0)
            if abs(change) > 1e-9:
                rows = phase_changes.setdefault(actor_id, [])
                rows.append({'phase': label, 'cash_change': round(change, 4)})
        region._actor_cash_phase_changes = phase_changes
        region._actor_cash_phase_snapshot = current_actor_cash

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
                    and not (getattr(agent, 'is_native_child', False) and agent.age(t) < 14)
                    and trader_count < max_traders
                    and rand.random() < 0.5):
                _logistics.make_trader_internal(region, agent)
                trader_count += 1
                loginfo(t, f"{agent.name()} inherited trader from parent {parent.name()}")
            elif (not agent.is_trader
                  and not (getattr(agent, 'is_native_child', False) and agent.age(t) < 14)
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


def _trace_profession_population(region: Any, by_output: dict) -> None:
    """Record changing members of the legacy profession-population measure."""
    run_trace = getattr(region, '_run_trace', None)
    if run_trace is None:
        return
    previous = getattr(region, '_trace_profession_members', None)
    current = {
        getattr(group, 'name', str(group)): {
            getattr(agent, 'id', None): agent for agent in agents}
        for group, agents in by_output.items()
    }
    if previous is not None:
        old_profession = {agent_id: name for name, members in previous.items()
                          for agent_id in members}
        new_profession = {agent_id: name for name, members in current.items()
                          for agent_id in members}
        flow_events = {}
        flow_events.update(getattr(run_trace, '_previous_person_flow_events', {}))
        flow_events.update(getattr(run_trace, '_person_flow_events', {}))
        for group, members in by_output.items():
            name = getattr(group, 'name', str(group))
            old_members = previous.get(name, {})
            new_members = current.get(name, {})
            removed_ids = old_members.keys() - new_members.keys()
            added_ids = new_members.keys() - old_members.keys()
            if not removed_ids and not added_ids:
                continue

            changes = []
            cause_ids = set()
            for person_id in sorted(removed_ids | added_ids, key=str):
                agent = new_members.get(person_id) or old_members.get(person_id)
                changes.append({
                    'agent_id': str(person_id),
                    'from_profession': old_profession.get(person_id),
                    'to_profession': new_profession.get(person_id),
                    'role': ('corporation' if getattr(agent, 'is_corporation', False)
                             else 'government' if getattr(agent, 'is_government', False)
                             else 'trader' if getattr(agent, 'is_trader', False)
                             else 'person'),
                    'alive': bool(getattr(agent, 'alive', True)),
                    'death_cause': getattr(agent, 'death_cause', None),
                    'region': getattr(agent, 'region', None),
                    'last_migration_turn': getattr(agent, 'last_migration_turn', None),
                })
                for event_id in flow_events.get(str(person_id), ()):
                    cause_ids.add(event_id)

            history = getattr(region, 'population_log', {}).get(group, ())
            before = history[-1] if history else len(old_members)
            after = len(members)
            from run_trace import emit
            emit(region, kind='profession_population_count', record_class='calculation',
                 phase='local',
                 subject={'type': 'tile', 'id': region.name, 'profession': name},
                 metric_id='people.profession_population', unit='people',
                 before=int(before), after=int(after),
                 formula_id='population.profession_membership_count.v1',
                 inputs={'profession': name,
                         'counting_rule': ('all entries in trader_agents'
                                           if name == 'trader' else
                                           'non-trader agents whose output equals this '
                                           'profession; government output excluded'),
                         'added_agent_ids': sorted(map(str, added_ids)),
                         'removed_agent_ids': sorted(map(str, removed_ids)),
                         'membership_changes': changes,
                         'member_count': int(after),
                         'previous_membership_available': True},
                 cause_event_ids=sorted(cause_ids))
    region._trace_profession_members = current


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

    _trace_profession_population(region, by_output)

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
    hunger_groups = {}
    for good in (Goods.food, Goods.wood, Goods.furniture):
        history = region.hungry_log.get(good, ())
        hunger_groups[good.name] = int(history[-1]) if history else 0
    trader_hunger = region.hungry_log.get('trader', ())
    hunger_groups['trader'] = int(trader_hunger[-1]) if trader_hunger else 0
    from run_trace import emit
    emit(region, kind='population_hunger_count_calculation',
         record_class='calculation', phase='demographics',
         subject={'type': 'tile', 'id': region.name},
         metric_id='people.hungry', unit='people',
         after=sum(hunger_groups.values()),
         formula_id='population.sum_hungry_output_groups.v1',
         inputs={'group_counts': hunger_groups,
                 'included_groups': list(hunger_groups),
                 'counting_rule': 'sum disjoint producer-output and trader cohorts',
                 'source': 'Live hunger histories for this turn'})
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
