"""Commercial deployment of learned designs, funded by firms and existing banks.

Decisions use settled sales rather than valuing unsold output as revenue. Physical
construction is delegated to the normal project pipeline; no treasury is charged.
"""
from __future__ import annotations

from copy import copy
import math

from goods import Goods

HISTORY_TURNS = 8
MIN_OBSERVATIONS = HISTORY_TURNS
DECISION_INTERVAL = 3
ACTIVE_PROJECT_STATUSES = ('in_progress', 'stalled')
REASON_LABELS = {
    'selected': 'Investment approved', 'no_realized_demand': 'Waiting for sales',
    'no_productivity_gain': 'Current equipment is sufficient',
    'operating_losses': 'Operating losses make investment unattractive',
    'credit_unavailable': 'Insufficient cash and available credit',
    'debt_service_too_high': 'Expected sales cannot cover new debt safely',
    'payback_too_long': 'Expected payback is too slow',
    'negative_net_present_value': 'Expected return is too low',
    'guild_blockade': 'Guild rules block deployment',
    'construction_supplies_unavailable': 'Waiting for construction supplies',
    'no_operating_workforce': 'Waiting for an operating workforce',
    'currency_mismatch': 'Local currency financing is unavailable',
    'construction_unavailable': 'Waiting for construction capacity',
    'better_investment_available': 'Another investment offers a better return',
}


def owns_installation(building, actor):
    owner = getattr(building, 'private_owner_id', None)
    return owner is not None and owner == getattr(actor, 'id', None)


def applies_to_producer(building, producer):
    owner = getattr(building, 'private_owner_id', None)
    return owner is None or (producer is not None and owner == producer.id)


def firm_reserve(firm, region):
    """Retain five payrolls, input purchases and scheduled debt payments."""
    staff = sum(getattr(a, 'alive', True) for a in getattr(firm, 'employees', ()))
    recipe = getattr(region, 'recipes', {}).get(firm.output, {})
    inputs = max(0.0, float(recipe.get('numInput', 0)))
    input_price = max(0.0, float(region.recipes.get(recipe.get('input'), {}).get('price', 0)))
    payroll = staff * max(0.0, float(getattr(firm, 'wage', 0)))
    debt = sum(max(0.0, float(loan.getPaymentAmount())) for loan in getattr(firm, 'loans', ())
               if not loan.isPaid())
    return 20.0 + 5 * (payroll + staff * inputs * input_price + debt)


def credit_terms(firm, region):
    bank = getattr(region, 'bank', None)
    capacity = 0.0
    if bank is not None and not getattr(bank, 'is_frozen', False):
        capacity = max(0.0, (bank.capital + bank.total_deposits)
                       * (1 - bank.reserve_fraction) - bank.total_liabilities)
    return {'capacity': capacity, 'interest_rate': max(0.0, float(getattr(bank, 'interest_rate', 0))),
            'repayment_turns': 100, 'frozen': bool(getattr(bank, 'is_frozen', False))}


def available_funding(firm, region, budget, reserve):
    """Use accessible savings before debt, including their lending-capacity effect."""
    bank = getattr(region, 'bank', None)
    terms = credit_terms(firm, region)
    deposits = (max(0.0, float(bank.deposits.get(firm, 0)))
                if bank is not None and not terms['frozen'] else 0.0)
    withdrawal = min(deposits, max(0.0, budget + reserve - firm.cash))
    capacity = max(0.0, terms['capacity'] - withdrawal * (1 - getattr(bank, 'reserve_fraction', 0)))
    return {'withdrawal': withdrawal, 'capacity': capacity,
            'borrowing': max(0.0, budget + reserve - firm.cash - withdrawal)}


def investment_economics(*, revenue, produced, sold, operating_cost, gain_fraction,
                         lost_fraction, capital_cost, downtime, cash, reserve,
                         credit_capacity, interest_rate, risk_tolerance=0.5):
    """Pure conservative comparison, replayed by the trace inspector and tests.

    The gain is extra output from unchanged productive work, so existing input
    costs and payroll do not grow. Sales uncertainty is discounted explicitly.
    Forgone output during a retrofit is charged as part of the investment.
    """
    risk = min(1.0, max(0.0, float(risk_tolerance)))
    sell_through = min(1.0, max(0.0, sold) / max(1.0, produced))
    confidence = 0.45 + 0.35 * risk
    extra_revenue = max(0.0, revenue) * max(0.0, gain_fraction) * sell_through * confidence
    baseline_profit = revenue - operating_cost
    lost_income = max(0.0, revenue) * max(0.0, lost_fraction) * max(0, downtime)
    liquid = max(0.0, cash - reserve)
    borrowing = max(0.0, capital_cost - liquid)
    interest = borrowing * max(0.0, interest_rate)
    debt_payment = borrowing * (max(0.0, interest_rate) + 0.01)
    net_gain = extra_revenue - interest
    investment = capital_cost + lost_income
    payback = investment / net_gain if net_gain > 0 else None
    horizon = 12.0 + 36.0 * risk
    discount = max(0.001, interest_rate + 0.002)
    annuity = (1 - (1 + discount) ** -horizon) / discount
    npv = net_gain * annuity - investment
    reason = ('no_realized_demand' if revenue <= 0 or sold <= 0 else
              'no_productivity_gain' if gain_fraction <= 0 else
              'operating_losses' if baseline_profit + extra_revenue <= 0 else
              'credit_unavailable' if borrowing > credit_capacity + 1e-8 else
              'debt_service_too_high' if borrowing > 0 and extra_revenue < 2 * debt_payment else
              'payback_too_long' if payback is None or payback > horizon else
              'negative_net_present_value' if npv <= 0 else 'profitable')
    return {'feasible': reason == 'profitable', 'reason': reason,
            'baseline_profit': baseline_profit, 'sell_through': sell_through,
            'confidence': confidence, 'extra_revenue': extra_revenue,
            'net_gain_per_turn': net_gain, 'downtime_loss': lost_income,
            'capital_cost': capital_cost, 'borrowing': borrowing,
            'interest_per_turn': interest, 'debt_payment': debt_payment,
            'reserve': reserve, 'payback_turns': payback, 'horizon': horizon, 'npv': npv}


def observe_firm_market(region, firm, turn):
    """One bounded observation per completed turn, from the settlement journal."""
    history = list(getattr(firm, 'technology_market_history', ()))
    if turn <= 0 or (history and history[-1]['turn'] >= turn):
        return history
    good_name = firm.output.name
    events = [e for e in getattr(region, 'economic_events', ()) if e['turn'] == turn
              and (e['payer_id'] == firm.id or e['recipient_id'] == firm.id)]
    sales = [e for e in events if e['recipient_id'] == firm.id and e.get('good') == good_name
             and e['kind'] in ('spot_sale', 'contract_delivery', 'market_sale_cash_receipt')
             and not (e['kind'] == 'spot_sale' and e.get('detail', {}).get('seller_account_tile', region.name) != region.name)]
    revenue = sum(float(e.get('detail', {}).get('cash_receipt', e.get('detail', {}).get('seller_receipt', e['amount']))) for e in sales)
    produced = sum(e['quantity'] for e in events if e['recipient_id'] == firm.id
                   and e['kind'] == 'production' and e.get('good') == good_name)
    spent = [e for e in events if e['payer_id'] == firm.id
             and not str(e.get('detail', {}).get('payment_kind', '')).startswith('engineering_')
             and e.get('detail', {}).get('purpose') != 'engineering']
    wages = sum(e['amount'] for e in spent if e['kind'] == 'wage')
    input_cost = sum(e['amount'] if e['amount'] > 0 else e['quantity'] * max(0.0, float(
        region.recipes.get(Goods.__members__.get(e.get('good')), {}).get('price', 0)))
        for e in spent if e['kind'] == 'input_consumed')
    fixed_cost = sum(e['amount'] for e in spent if e['kind'] in ('freight', 'rent', 'tax', 'cash_tax'))
    sample = {'turn': turn, 'revenue': revenue, 'produced': produced,
              'sold': sum(e['quantity'] for e in sales), 'operating_cost': wages + input_cost + fixed_cost,
              'wages': wages, 'input_cost': input_cost, 'output_stock': firm.inv_get(firm.output, 0),
              'journal_ids': [e['id'] for e in events]}
    from run_trace import emit
    ident = emit(region, kind='commercial_technology_market_observation', record_class='observation',
        phase='projects', subject={'type': 'agent', 'id': firm.id, 'tile': region.name},
        metric_id='innovation.adoption_market', unit='local_currency_per_turn', after=revenue,
        inputs=sample)
    sample['trace_event_id'] = ident
    history.append(sample)
    firm.technology_market_history = history[-HISTORY_TURNS:]
    return firm.technology_market_history


def _local_quote(region, recipe):
    """A bid covers materials and a full paid crew, even at unusual local prices."""
    result = copy(recipe)
    # Normal projects may overrun by two turns. Reserve the full crew payroll.
    duration = result.base_turns + 2
    materials = sum(q * max(0.01, float(region.recipes.get(g, {}).get('price', 1)))
                    for g, q in result.required_goods.items())
    result.cost = round(max(result.cost, materials + 1.5 * result.construction_workers * duration), 2)
    return result


def adoption_candidates(system, nation, region, firm, turn):
    from buildings import BUILDING_RECIPES, Building
    from engineering import quote_recipe
    from innovation import TECH_CATALOG
    history = [s for s in getattr(firm, 'technology_market_history', ())
               if turn - HISTORY_TURNS <= s['turn'] < turn]
    if len(history) < MIN_OBSERVATIONS:
        return []
    count = len(history)
    means = {key: sum(s[key] for s in history) / count
             for key in ('revenue', 'produced', 'sold', 'operating_cost')}
    reserve = firm_reserve(firm, region)
    terms = credit_terms(firm, region)
    candidates = []
    assets = list(getattr(region, 'buildings', ()))
    known = system.get_discovered_techs(nation.name)
    for tid in sorted(known):
        recipe = BUILDING_RECIPES.get(tid + '_prototype')
        if recipe is None or firm.output not in recipe.production_bonuses:
            continue
        tier = system.get_tech_tier(nation.name, tid)
        owned = [b for b in assets if owns_installation(b, firm)
                 and tid in getattr(b, 'technology_designs', {})]
        target = owned[0] if owned else None
        if target is not None and getattr(target, 'technology_designs', {}).get(tid, 0) >= tier:
            continue
        if target is not None and getattr(target, 'retrofit_project_id', None):
            continue
        quoted = _local_quote(region, quote_recipe(nation, recipe, system))
        new_asset = Building(quoted.name, quoted, turn, region.name)
        current_mult = target.production_bonuses.get(firm.output, 1) if target else 1
        replacement_mult = new_asset.production_bonuses.get(firm.output, 1)
        choices = [('install' if target is None else 'replace', quoted, replacement_mult)]
        if target is not None:
            gap = tier - target.technology_designs.get(tid, 0)
            retrofit = copy(quoted)
            retrofit.cost = round(quoted.cost * min(1.15, 0.4 + 0.25 * max(0, gap - 1)), 2)
            retrofit.required_goods = {g: max(1, math.ceil(q * min(1.0, 0.4 + 0.25 * max(0, gap - 1))))
                                       for g, q in quoted.required_goods.items()}
            retrofit.base_turns = 2 + max(0, gap - 1)
            retrofit = _local_quote(region, retrofit)
            upgraded = copy(target)
            upgraded.technology_designs = {**target.technology_designs, tid: tier}
            choices.append(('retrofit', retrofit, upgraded.production_bonuses.get(firm.output, 1)))
        for action, bid, after_mult in choices:
            funding = available_funding(firm, region, bid.cost, reserve)
            inputs = {**means, 'gain_fraction': max(0.0, after_mult / max(1, current_mult) - 1),
                      'lost_fraction': max(0.0, 1 - 1 / max(1, current_mult)),
                      'capital_cost': bid.cost, 'downtime': bid.base_turns + 2 if target else 0,
                      'cash': float(firm.cash) + funding['withdrawal'], 'reserve': reserve,
                      'credit_capacity': funding['capacity'], 'interest_rate': terms['interest_rate'],
                      'risk_tolerance': getattr(firm, 'risk_tolerance', 0.5)}
            economics = investment_economics(**inputs)
            blocked = system.get_guild_blockade(nation, tid)
            if blocked.get('active'):
                economics.update(feasible=False, reason='guild_blockade')
            stocks = {g: sum(int(a.inv_get(g, 0)) for a in getattr(region, 'agents', ())
                            if getattr(a, 'alive', True) and callable(getattr(a, 'inv_get', None))
                            and not getattr(a, 'is_government', False)) for g in bid.required_goods}
            if any(stocks[g] < quantity for g, quantity in bid.required_goods.items()):
                economics.update(feasible=False, reason='construction_supplies_unavailable')
            if not getattr(firm, 'employees', ()) or means['produced'] <= 0:
                economics.update(feasible=False, reason='no_operating_workforce')
            firm_currency = getattr(firm, 'home_currency', None)
            if firm_currency and firm_currency != getattr(region, 'home_currency', firm_currency):
                economics.update(feasible=False, reason='currency_mismatch')
            candidates.append({'tech_id': tid, 'generation': tier, 'action': action,
                               'recipe': bid, 'target': target, 'inputs': inputs, 'economics': economics,
                               'source_event_ids': [s['trace_event_id'] for s in history if s.get('trace_event_id')]})
    return candidates


def commission_private_adoption(system, nation, region, firm, candidate, turn, decision_id=None):
    """Fund a real contractor; credit follows the existing bank's balance sheet."""
    from construction_politics import find_or_emerge_contractor
    from buildings import ConstructionProject
    from engineering import _pay
    from run_trace import emit
    if any(getattr(p, 'private_owner_id', None) == firm.id and p.status in ACTIVE_PROJECT_STATUSES
           for p in getattr(region, 'construction_projects', ())):
        return None
    recipe = candidate['recipe']
    budget = float(recipe.cost)
    reserve = firm_reserve(firm, region)
    funding = available_funding(firm, region, budget, reserve)
    shortfall = funding['borrowing']
    if shortfall > funding['capacity'] + 1e-8:
        return None
    contractor_args = dict(exclude_ids={firm.id, *(a.id for a in firm.employees)},
                           require_independent=True, allow_create=False)
    contractor = find_or_emerge_contractor(region, budget, turn, dry_run=True, **contractor_args)
    if contractor is None:
        firm.technology_adoption_blocked = 'No available independent contractor.'
        return None
    workers = [a for a in region.agents if a.id != contractor.id and a.id not in contractor_args['exclude_ids']
        and getattr(a, 'alive', True) and not any(getattr(a, flag, False) for flag in
            ('is_corporation', 'is_government', 'is_native_child', 'is_lord', 'is_trader', 'military_unit_id'))
        and getattr(a, 'employer', None) in (None, contractor)]
    if len(workers) < recipe.construction_workers:
        firm.technology_adoption_blocked = 'Construction workers are unavailable.'
        return None
    from engineering import _stockists
    if any(sum(int(a.inv_get(g, 0)) for a in _stockists(region, g, contractor))
           + max(0, int(contractor.inv_get(g, 0))) < q
           for g, q in recipe.required_goods.items()):
        firm.technology_adoption_blocked = 'Construction supplies are unavailable.'
        return None
    contractor = find_or_emerge_contractor(region, budget, turn, **contractor_args)
    if funding['withdrawal']:
        region.bank.Withdraw(firm, funding['withdrawal'], trace_region=region, t=turn,
                             reason='commercial_technology_investment')
    if shortfall > 1e-8:
        borrowed = region.bank.Borrow(turn, firm, shortfall, trace_region=region)
        if borrowed + 1e-8 < shortfall:
            return None
    payment_id = _pay(region, nation, firm, contractor, budget, turn, candidate['tech_id'],
                      'commercial_technology_construction', 'commission')
    ident = f'private-tech:{region.name}:{firm.id}:{turn}'
    project = ConstructionProject(ident, nation.name, region, recipe, contractor=contractor,
                                  started_turn=turn)
    project.private_owner_id = firm.id
    project.adoption_action = candidate['action']
    project.navvy_ids = [a.id for a in workers if getattr(a, 'employer', None) is contractor][:recipe.construction_workers]
    target = candidate['target']
    if target is not None:
        target.retrofit_project_id = ident
        if candidate['action'] == 'replace':
            project.replacement_target = target
        else:
            project.retrofit_target = target
    if not hasattr(region, 'construction_projects'):
        region.construction_projects = []
    region.construction_projects.append(project)
    firm.technology_adoption_spent = float(getattr(firm, 'technology_adoption_spent', 0)) + budget
    firm.technology_adoption_borrowed = float(getattr(firm, 'technology_adoption_borrowed', 0)) + shortfall
    firm.last_technology_investment = {'turn': turn, 'tech_id': candidate['tech_id'],
        'generation': candidate['generation'], 'action': candidate['action'], 'project_id': ident,
        'cost': budget, 'borrowed': shortfall, 'savings_withdrawn': funding['withdrawal'],
        'expected_gain_per_turn': candidate['economics']['net_gain_per_turn'],
        'expected_payback_turns': candidate['economics']['payback_turns']}
    firm.technology_adoption_blocked = ''
    emit(region, kind='commercial_technology_commissioned', record_class='outcome', phase='projects',
         subject={'type': 'agent', 'id': firm.id, 'tile': region.name, 'tech_id': candidate['tech_id']},
         metric_id='innovation.commercial_investment', unit='local_currency', after=budget,
         decision_id=decision_id, cause_event_ids=[e for e in (decision_id, payment_id) if e],
         inputs={**firm.last_technology_investment, 'contractor_id': contractor.id,
                 'cash_reserve': reserve, 'firm_cash_after': firm.cash})
    return project


def step_private_adoption(tiles, nations, turn, system=None):
    from innovation import get_innovation_system
    from run_trace import emit
    from world_config import gameplay_flags_for
    system = system or get_innovation_system()
    owners = {id(n): n for n in nations}
    events = []
    for region in sorted(tiles, key=lambda r: r.name):
        nation = owners.get(id(getattr(region, 'owner_nation', None)))
        if nation is None or not gameplay_flags_for(region).private_technology_adoption:
            continue
        known = system.get_discovered_techs(nation.name)
        if not known:
            continue
        for firm in sorted(list(getattr(region, 'agents', ())), key=lambda a: a.id):
            if (not getattr(firm, 'is_corporation', False) or not getattr(firm, 'alive', True)
                    or getattr(firm, 'is_construction_company', False)
                    or getattr(firm, 'is_government', False) or getattr(firm, 'is_trader', False)):
                continue
            observe_firm_market(region, firm, turn - 1)
            if (turn + firm.id) % DECISION_INTERVAL or getattr(firm, '_technology_adoption_turn', None) == turn:
                continue
            firm._technology_adoption_turn = turn
            if any(getattr(p, 'private_owner_id', None) == firm.id and p.status in ACTIVE_PROJECT_STATUSES
                   for p in getattr(region, 'construction_projects', ())):
                continue
            candidates = adoption_candidates(system, nation, region, firm, turn)
            feasible = [c for c in candidates if c['economics']['feasible']]
            winner = max(feasible, key=lambda c: c['economics']['npv'], default=None)
            summary = winner or max(candidates, key=lambda c: c['economics']['npv'], default=None)
            per_tech = {}
            for candidate in candidates:
                tid = candidate['tech_id']
                if tid not in per_tech or candidate['economics']['npv'] > per_tech[tid]['economics']['npv']:
                    per_tech[tid] = candidate
            for candidate in candidates:
                selected = candidate is winner
                economics = candidate['economics']
                reason = economics['reason'] if not economics['feasible'] else 'selected' if selected else 'better_investment_available'
                decision = {'turn': turn, 'tech_id': candidate['tech_id'], 'action': candidate['action'],
                            'selected': selected, 'reason': reason,
                            'expected_gain_per_turn': economics['net_gain_per_turn'],
                            'payback_turns': economics['payback_turns'], 'cost': economics['capital_cost']}
                if candidate is summary:
                    firm.last_technology_adoption_decision = decision
                if candidate is per_tech[candidate['tech_id']]:
                    if not hasattr(firm, 'technology_adoption_decisions'):
                        firm.technology_adoption_decisions = {}
                    firm.technology_adoption_decisions[candidate['tech_id']] = decision
                decision_id = emit(region, kind='commercial_technology_adoption_decision', record_class='decision',
                    phase='projects', subject={'type': 'agent', 'id': firm.id, 'tile': region.name,
                                              'tech_id': candidate['tech_id'], 'action': candidate['action']},
                    metric_id='innovation.adoption_decision', unit='boolean', after=int(selected),
                    inputs={**decision, 'estimate_inputs': candidate['inputs'], 'economics': economics,
                            'estimate_status': 'conditional_on_recent_sales_and_current_prices'},
                    cause_event_ids=candidate['source_event_ids'] or None)
                if not selected:
                    continue
                project = commission_private_adoption(system, nation, region, firm, candidate, turn, decision_id)
                if project is not None:
                    title = getattr(firm, 'company_name', None) or f'Firm {firm.id}'
                    events.append({'t': turn, 'event': 'ENGINEERING',
                        'message': f'{title} is funding a {candidate["action"]} of {candidate["tech_id"].replace("_", " ")}: {project.recipe.cost:.0f}, expected payback {economics["payback_turns"]:.0f} turns.'})
                else:
                    firm.last_technology_adoption_decision.update(selected=False,
                        reason='construction_unavailable',
                        constraint=getattr(firm, 'technology_adoption_blocked', 'Funding unavailable.'))
                    emit(region, kind='commercial_technology_commission_blocked', record_class='outcome',
                        phase='projects', subject={'type': 'agent', 'id': firm.id, 'tile': region.name,
                                                  'tech_id': candidate['tech_id']},
                        metric_id='innovation.commercial_investment', unit='local_currency', after=0,
                        cause_event_ids=[decision_id] if decision_id else None,
                        inputs=firm.last_technology_adoption_decision)
    return events
