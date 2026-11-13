"""Sector selection, company expansion and incorporation."""
from economy.actor_accounts import record
from goods import Goods
from run_trace import emit
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
from economy.elite_treasury_trace import _trace_government_company_equity


def local_input_supply(region, good, traced):
    inventory, producers, stocks = [], [], []
    producer_count = 0
    for supplier in getattr(region, 'agents', ()):
        if not getattr(supplier, 'alive', True):
            continue
        held = supplier.inv_get(good, 0)
        stocks.append(held)
        is_producer = getattr(supplier, 'output', None) == good
        producer_count += int(is_producer)
        if traced:
            inventory.append({'agent_id': str(getattr(supplier, 'id', 'unknown')), 'units': float(held)})
            if is_producer:
                producers.append(str(getattr(supplier, 'id', 'unknown')))
    return sum(stocks) + producer_count, inventory, producers


def scan_sectors(region, trace_enabled):
    recipes = getattr(region, 'recipes', {})
    best_sector = None
    best_profit_margin = 0.0
    sector_evaluations = []
    sector_exclusions = []

    for g, r in recipes.items():
        if g in (Goods.gov, Goods.none, Goods.foreign_luxuries):
            sector_exclusions.append({
                'good': getattr(g, 'name', str(g)),
                'reason': 'government_none_or_foreign_luxury_output'})
            continue
        if r.get('is_luxury') and r.get('numInput', 0) == 0:
            sector_exclusions.append({
                'good': getattr(g, 'name', str(g)),
                'reason': 'zero_input_luxury_output'})
            continue
        if r.get('import_only'):
            sector_exclusions.append({
                'good': getattr(g, 'name', str(g)),
                'reason': 'import_only_output'})
            continue
        p_out = float(r.get('price', 1.0))
        req_qty = float(r.get('numInput', 0))
        in_good = r.get('input')
        p_in = float(recipes.get(in_good, {}).get('price', 0.0)) if req_qty > 0 else 0.0
        production = float(r.get('production', 1.0))
        gross_output_value = p_out * production
        from abundance import enabled as abundance_enabled, funded_demand
        if abundance_enabled(region):
            gross_output_value = p_out * min(production, funded_demand(region, g))
        input_cost = p_in * req_qty
        raw_margin = gross_output_value - input_cost
        margin = raw_margin
        local_supply = None
        input_inventory = []
        input_producer_ids = []
        if req_qty > 0 and in_good is not None:
            local_supply, input_inventory, input_producer_ids = local_input_supply(
                region, in_good, trace_enabled)
            if local_supply < req_qty:
                margin *= 0.05
        selected_as_best = margin > best_profit_margin
        if trace_enabled:
            sector_evaluations.append({
                'good': getattr(g, 'name', str(g)),
                'output_price': p_out,
                'output_units_per_turn': production,
                'gross_output_value': gross_output_value,
                'input_good': getattr(in_good, 'name', str(in_good))
                if in_good is not None else None,
                'input_unit_price': p_in,
                'input_units': req_qty,
                'input_cost': input_cost,
                'raw_margin': raw_margin,
                'local_input_inventory': input_inventory,
                'local_input_producer_ids': input_producer_ids,
                'local_input_supply': local_supply,
                'input_shortage_penalty': (
                    0.05 if local_supply is not None and local_supply < req_qty
                    else 1.0 if local_supply is not None else None),
                'effective_margin': margin,
                'best_sector_threshold_before': best_profit_margin,
                'selected_as_best_sector': selected_as_best})
        if selected_as_best:
            best_profit_margin = margin
            best_sector = g
    return best_sector, best_profit_margin, sector_evaluations, sector_exclusions


def expand_company(decision, company, investment_event_id):
    agent, region, t = decision.agent, decision.region, decision.turn
    result = decision.result
    injection = min(agent.cash * 0.4, 50.0)
    owner_cash_before = float(agent.cash)
    company_cash_before = float(company.cash)
    wage_before = float(company.wage)
    employee_cap_before = int(company.max_employees)
    _trace_cash_write = _trace_public_begin(None, agent)
    agent.cash -= injection
    founder_cash_write_ids = _trace_public_finish(
        _trace_cash_write,
        'economy/capitalist_planner:EliteCapitalistPlanner._plan_and_execute_elite',
        inputs={"source_writer": 'economy/capitalist_planner.py:EliteCapitalistPlanner._plan_and_execute_elite:ebcb08d91ea10d4c:1'})
    _trace_cash_write = _trace_public_begin(None, company)
    company.cash += injection
    _trace_public_finish(
        _trace_cash_write,
        'economy/capitalist_planner:EliteCapitalistPlanner._plan_and_execute_elite',
        inputs={"source_writer": 'economy/capitalist_planner.py:EliteCapitalistPlanner._plan_and_execute_elite:0d2c439a4043addd:1'})
    record(region, 'owner_financing', turn=t, payer_id=agent.id,
           recipient_id=company.id, amount=injection, asset_id=company.id,
           detail={'funding_type': 'equity', 'investment_kind': 'company_expansion'})
    _trace_government_company_equity(
        region, founder=agent, company=company, turn=t,
        amount=injection,
        founder_cash_before=owner_cash_before,
        founder_cash_after=agent.cash,
        company_cash_before=company_cash_before,
        company_cash_after=company.cash,
        public_write_event_ids=founder_cash_write_ids,
        investment_event_id=investment_event_id,
        investment_kind='company_expansion')
    # Raise offered wage to attract more workers
    company.wage = round(max(company.wage * 1.10, company.wage + 0.5), 2)
    company.max_employees = min(50, company.max_employees + 5)
    result['action_taken'] = 'CAPITAL_EXPANSION'
    result['details'] = {
        'company_id': company.id, 'injection': injection,
        'new_wage': company.wage,
        'owner_cash_before': owner_cash_before,
        'owner_cash_after': float(agent.cash),
        'company_cash_before': company_cash_before,
        'company_cash_after': float(company.cash),
        'wage_before': wage_before,
        'wage_after': float(company.wage),
        'employee_cap_before': employee_cap_before,
        'employee_cap_after': int(company.max_employees)}
    return result


def incorporate_company(decision, best_sector, investment_event_id):
    agent, region, t = decision.agent, decision.region, decision.turn
    result = decision.result
    from agent import Agent, seed_traits
    comp = Agent(t)
    comp.is_corporation = True
    seed_traits(comp)
    comp.output = best_sector
    comp.owner = agent
    comp._bank_ref = getattr(region, 'bank', None)
    comp.home_currency = getattr(region, 'home_currency', None)
    comp.region = getattr(region, 'name', '')
    agent.company_owned = comp
    founder_cash_before = float(agent.cash)
    equity = min(agent.cash * 0.5, agent.cash - 60.0)
    company_cash_before = float(comp.cash)
    _trace_cash_write = _trace_public_begin(None, agent)
    agent.cash -= equity
    founder_cash_write_ids = _trace_public_finish(
        _trace_cash_write,
        'economy/capitalist_planner:EliteCapitalistPlanner._plan_and_execute_elite',
        inputs={"source_writer": 'economy/capitalist_planner.py:EliteCapitalistPlanner._plan_and_execute_elite:0da483c477d7a07e:1'})
    _trace_cash_write = _trace_public_begin(None, comp)
    comp.cash = equity
    _trace_public_finish(_trace_cash_write, 'economy/capitalist_planner:EliteCapitalistPlanner._plan_and_execute_elite',
                         inputs={"source_writer": 'economy/capitalist_planner.py:EliteCapitalistPlanner._plan_and_execute_elite:9ff287188158c1ce:1'})
    record(region, 'owner_financing', turn=t, payer_id=agent.id,
           recipient_id=comp.id, amount=equity, asset_id=comp.id,
           detail={'funding_type': 'equity', 'investment_kind': 'company_incorporation'})
    _trace_government_company_equity(
        region, founder=agent, company=comp, turn=t, amount=equity,
        founder_cash_before=founder_cash_before,
        founder_cash_after=agent.cash,
        company_cash_before=company_cash_before,
        company_cash_after=comp.cash,
        public_write_event_ids=founder_cash_write_ids,
        investment_event_id=investment_event_id,
        investment_kind='company_incorporation')
    # Attractive wage to stimulate profession adoption
    food_p = float(region.recipes.get(Goods.food, {}).get('price', 1.0))
    comp.wage = round(max(2.0, food_p * 2.0), 2)
    comp.max_employees = 15
    region.agents.append(comp)
    result['action_taken'] = 'INCORPORATE_FIRM'
    result['details'] = {
        'company_id': comp.id, 'sector': best_sector.name,
        'wage': comp.wage, 'owner_cash_before': founder_cash_before,
        'owner_cash_after': float(agent.cash),
        'company_equity': float(comp.cash),
        'initial_employee_cap': int(comp.max_employees)}
    return result


def invest_capital(decision):
    agent, region, t = decision.agent, decision.region, decision.turn
    result = decision.result
    if agent.cash < 150.0 or getattr(agent, 'is_lord', False):
        return None
    best_sector, best_profit_margin, sector_evaluations, sector_exclusions = scan_sectors(
        region, decision.trace_enabled)
    company = getattr(agent, 'company_owned', None)
    company_can_expand = bool(
        company and getattr(company, 'is_corporation', False)
        and company.alive and company in region.agents
        and company.home_currency == region.home_currency)
    can_incorporate = bool(
        company is None and agent.cash >= 300.0
        and not getattr(agent, 'employer', None) and best_sector)
    investment_action = ('CAPITAL_EXPANSION' if company_can_expand else
                         'INCORPORATE_FIRM' if can_incorporate else 'continue')
    if company_can_expand:
        investment_reason = 'expand_existing_same_currency_company'
    elif can_incorporate:
        investment_reason = 'cash_gate_and_positive_best_sector_passed'
    elif company is not None:
        investment_reason = 'owned_company_not_expandable_in_this_currency_or_region'
    elif agent.cash < 300.0:
        investment_reason = 'incorporation_cash_below_300'
    elif getattr(agent, 'employer', None):
        investment_reason = 'owner_is_employed'
    else:
        investment_reason = 'no_sector_with_positive_effective_margin'
    from run_trace import emit
    investment_event_id = emit(
        region, kind='elite_capital_allocation_evaluation',
        record_class='decision', phase='local',
        subject={'type': 'agent', 'id': agent.id,
                 'tile': getattr(region, 'name', 'default')},
        metric_id='ai.elite_economic_decision', unit='candidate',
        after=investment_action,
        formula_id='elite.capital_allocation_gate.v1',
        inputs={'opening_cash': float(agent.cash),
                'investment_cash_threshold': 150.0,
                'incorporation_cash_threshold': 300.0,
                'eligible_sector_evaluations': sector_evaluations,
                'excluded_sectors': sector_exclusions,
                'best_sector': (getattr(best_sector, 'name', str(best_sector))
                                if best_sector is not None else None),
                'best_effective_margin': best_profit_margin,
                'owner_is_lord': bool(getattr(agent, 'is_lord', False)),
                'owner_has_employer': bool(getattr(agent, 'employer', None)),
                'owned_company_id': (str(company.id) if company else None),
                'company_can_expand': company_can_expand,
                'can_incorporate': can_incorporate,
                'selected_branch': investment_action,
                'reason': investment_reason})
    if investment_event_id is not None:
        result['evaluation_event_ids'].append(investment_event_id)

    if company_can_expand:
        return expand_company(decision, company, investment_event_id)
    if can_incorporate:
        return incorporate_company(decision, best_sector, investment_event_id)
    return None
