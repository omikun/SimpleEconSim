"""One regional career market and a serializable, shared departure ledger.

Only fractional capacity survives a turn. Counts are frozen before hiring;
actual membership is checked again at commitment, after any forced losses.
"""
from __future__ import annotations

import math
from collections import Counter


def working_adult(person, turn):
    from labor_choice import career_lifecycle_age
    return (getattr(person, 'alive', True)
            and not any(getattr(person, flag, False) for flag in
                        ('is_corporation', 'is_government', 'is_trader', 'is_lord',
                         'in_workhouse', 'military_unit_id'))
            and getattr(person, 'social_class', None) != 'constable'
            and career_lifecycle_age(person, turn) >= 14)


def profession(person):
    from goods import Goods
    employer = getattr(person, 'employer', None)
    if employer is None and getattr(person, 'is_native_child', False) and getattr(person, 'primary_livelihood', None) is None:
        return None
    good = (getattr(employer, 'output', None) if employer is not None else
            getattr(person, 'output', None) or getattr(person, 'primary_livelihood', None))
    return good if good not in (None, Goods.none, Goods.gov) else None


def populations(region, turn):
    return Counter(good.name for person in region.agents
                   if working_adult(person, turn)
                   and (good := profession(person)) is not None)


def begin_turn(region, turn):
    state = getattr(region, 'career_transition_state', None)
    if state is not None and state['turn'] == turn:
        return state
    counts = populations(region, turn)
    floor = max(0, int(getattr(region, 'career_minimum_workers', 4)))
    carry = getattr(region, 'career_transition_carry', {})
    region.career_transition_carry = {
        key: value for key, value in carry.items() if counts.get(key, 0) > floor}
    state = {'turn': int(turn), 'minimum': floor, 'population': dict(counts),
             'budgets': {}, 'committed': [], 'blocked_ids': [], 'prepared': False}
    region.career_transition_state = state
    return state


def prepare_budgets(region, turn, gains):
    state = begin_turn(region, turn)
    if state['prepared']:
        return state
    state['prepared'] = True
    carry = region.career_transition_carry
    for key, count in state['population'].items():
        gain = max(0.0, gains.get(key, 0.0))
        surplus = max(0, count - state['minimum'])
        rate = min(max(0.0, float(getattr(region, 'career_max_transition_rate', .25))),
                   max(0.0, float(getattr(region, 'career_gain_sensitivity', .10))) * gain)
        allowance = surplus * rate + carry.get(key, 0.0) if gain > 0 and surplus else 0.0
        whole_allowance = math.floor(allowance + 1e-9)
        quota = min(surplus, whole_allowance)
        remainder = allowance - whole_allowance
        carry[key] = max(0.0, min(1.0 - 1e-12, remainder))
        state['budgets'][key] = {
            'population': count, 'minimum': state['minimum'], 'gain': gain,
            'rate': rate, 'quota': quota, 'used': 0, 'blocked': 0,
            'carry': carry[key]}
    return state


def voluntary(reason):
    return not any(word in str(reason).lower() for word in
                   ('forced', 'coerced', 'enclosure', 'workhouse', 'military',
                    'debt_bound', 'penal', 'displacement', 'deserter'))


def permit_change(region, person, good, turn, reason):
    """Consume a slot immediately before the authoritative occupation mutation."""
    old = profession(person)
    if region is None or old is None or old == good or not voluntary(reason):
        return True
    if not working_adult(person, turn):
        return False
    state = begin_turn(region, turn)
    # Noncanonical callers cannot create their own second allowance. They must
    # submit proposals to the common decision phase before attempting a move.
    budget = state['budgets'].get(old.name)
    allowed = (state['prepared'] and person.id not in state['committed'] and budget
               and budget['used'] < budget['quota']
               and populations(region, turn).get(old.name, 0) > state['minimum'])
    if not allowed:
        if budget and person.id not in state['blocked_ids']:
            budget['blocked'] += 1
            state['blocked_ids'].append(person.id)
        return False
    budget['used'] += 1
    state['committed'].append(person.id)
    return True


def _returns(region, person, good, counts, turn):
    from economy.labor_mobility import independent_return
    from goods import Goods
    if good == Goods.food:
        from agriculture import farm_return
        return farm_return(region, person, turn)
    value, reason = independent_return(region, person, good, counts.get(good.name, 0), turn)
    return value, reason


def step_careers(region, turn, *, independent=True):
    """Compare all adults' feasible moves, rank gains, then commit once each.

    Posted prices alone never establish an income. Independent returns include
    reachable sales, inputs and food kept for the household; jobs need a funded
    vacancy. Failed commitments spend no departure capacity.
    """
    from world_config import gameplay_flags_for
    if not gameplay_flags_for(region).career_mobility:
        region.labor_scheduler_last_turn = turn
        return {'disabled': True, 'processed': 0, 'switched': 0, 'hired': 0}
    from goods import Goods
    from labor_choice import evaluate_offer, attach_worker, apply_career_switch
    from region_labor import calculate_labor_market_tightness, _record_labor_decision
    from run_trace import emit

    state = begin_turn(region, turn)
    if getattr(region, 'labor_scheduler_last_turn', None) == turn:
        return {'already_processed': True, 'processed': 0, 'switched': 0, 'hired': 0}
    region.labor_scheduler_last_turn = turn
    counts = state['population']
    staff = {aid for b in getattr(region, 'buildings', ()) for aid in getattr(b, 'staff_ids', ())}
    people = sorted((p for p in region.agents if working_adult(p, turn)
                     and p.id not in staff), key=lambda p: p.id)
    firms = sorted((f for f in region.agents if getattr(f, 'alive', True)
                    and getattr(f, 'is_corporation', False)
                    and not getattr(f, 'business_closed', False)), key=lambda f: f.id)
    tightness = calculate_labor_market_tightness(region)
    proposals, gains = [], {}
    meal_cost = max(.001, 4 * region.recipes.get(Goods.food, {}).get('price', 1.0))
    from food_access import food_surplus
    from households import human
    food_market = {'offered': sum(food_surplus(a, region) for a in region.agents),
                   'buyers': max(1, len(getattr(region, 'households', {})) or sum(human(a) for a in region.agents))}
    for person in people:
        old = profession(person)
        employer = getattr(person, 'employer', None)
        current = (float(getattr(employer, 'wage', 0.0)) if employer else
                   _returns(region, person, old, counts, turn)[0] if old else 0.0)
        from livelihood_viability import assess
        viability = assess(region, person, turn, current)
        if not viability['seeking']:
            record = {'turn': turn, 'person_id': person.id, 'current_return': current,
                      'current_profession': old.name if old else None, 'options': [],
                      'viability': viability}
            region.career_choice_log = [*getattr(region, 'career_choice_log', []), record][-500:]
            emit(region, kind='worker_livelihood_stay', record_class='decision', phase='labor',
                 subject={'type': 'agent', 'id': person.id, 'tile': region.name},
                 metric_id='labor.career_choice', unit='occupation', inputs=record)
            continue
        from livelihood_viability import secured_meals
        from households import demand as household_need
        normal_food = max(.001, household_need(person, region, reserve_turns=0)['ordinary'])
        current_food = secured_meals(region, person, old, current, employer, food_market)
        food_options = {}
        def improves(value, good, firm=None):
            food = secured_meals(region, person, good, value, firm, food_market)
            food_options[(good, getattr(firm, 'id', None))] = food
            return value > current + 1e-9 or food > current_food + .001
        # A legally assessed exit cost belongs in the comparison, not in a
        # second emergency quit path that skips choosing the next occupation.
        penalty = (float(getattr(employer, 'wage', 0.0)) * 2
                   if employer and getattr(region, 'labor_laws', {}).get('quit_penalty') == 'enacted' else 0.0)
        options = []
        assessed = []
        if independent:
            for good in region.recipes:
                if good == old and employer is None:
                    continue
                value, explanation = _returns(region, person, good, counts, turn)
                assessed.append({'profession': good.name, 'return': value - penalty,
                                 'feasibility': explanation})
                if improves(value - penalty, good):
                    options.append((value - penalty, good, None, None, explanation))
        for firm in firms:
            if firm is employer:
                continue
            decision = evaluate_offer(person, firm, region, turn, tightness=tightness, career_phase=True)
            if not decision.accepted:
                _record_labor_decision(region, decision)
            elif not improves(decision.offered_wage - penalty, firm.output, firm):
                from dataclasses import replace
                _record_labor_decision(region, replace(decision, accepted=False, reason='lower_feasible_return'))
            assessed.append({'profession': firm.output.name, 'firm_id': firm.id,
                             'return': decision.offered_wage - penalty,
                             'feasibility': decision.reason})
            if decision.accepted and improves(decision.offered_wage - penalty, firm.output, firm):
                options.append((decision.offered_wage - penalty, firm.output, firm, decision, 'funded wage'))
        # Select a viable low-disruption route before comparing gains across
        # seekers. A familiar trade beats a distant speculative high return.
        options.sort(key=lambda option: (
            food_options.get((option[1], getattr(option[2], 'id', None)), 0) + .001 < normal_food,
            option[0] < viability['necessities_cost'], option[1] != old,
            option[1] != getattr(person, 'primary_livelihood', None),
            option[2] is None and region.recipes.get(option[1], {}).get('setup_good') is not None,
            -option[0], option[1].value))
        for value, good, firm, decision, explanation in options[:1]:
            food_gain = (food_options[(good, getattr(firm, 'id', None))] - current_food) / normal_food
            gain = max((value - current) / max(abs(current), meal_cost, .001), food_gain)
            proposals.append((gain, value - current, person.id, good.value, person,
                              good, firm, decision, current, value, explanation, penalty))
            if old is not None and old != good:
                gains[old.name] = max(gains.get(old.name, 0.0), gain)
        record = {'turn': turn, 'person_id': person.id, 'current_return': current,
                  'current_profession': old.name if old else None, 'options': assessed,
                  'viability': viability, 'secured_meal_units': current_food}
        region.career_choice_log = [*getattr(region, 'career_choice_log', []), record][-500:]
        emit(region, kind='worker_livelihood_options', record_class='decision', phase='labor',
             subject={'type': 'agent', 'id': person.id, 'tile': region.name},
             metric_id='labor.career_options', unit='return', inputs=record)
    prepare_budgets(region, turn, gains)
    done, switched, hired, entered = set(), 0, 0, 0
    for gain, _, _, _, person, good, firm, decision, current, value, explanation, penalty in sorted(
            proposals, key=lambda row: (-row[0], -row[1], row[2], row[3], getattr(row[6], 'id', -1))):
        if person.id in done:
            continue
        old = profession(person)
        old_employer = getattr(person, 'employer', None)
        if firm is not None:
            # Vacancy, complete payroll and input funding can have changed.
            decision = evaluate_offer(person, firm, region, turn, career_phase=True)
            if not decision.accepted:
                continue
            success = attach_worker(person, firm, turn, decision, region=region)
            if success:
                _record_labor_decision(region, decision)
                hired += 1
        else:
            # Recheck physical capacity after earlier entrants took places.
            fresh, _ = _returns(region, person, good, populations(region, turn), turn)
            if (fresh - penalty <= current + 1e-9
                    and secured_meals(region, person, good, fresh - penalty, market=food_market) <=
                    secured_meals(region, person, old, current, old_employer, food_market) + .001):
                continue
            success = apply_career_switch(region, person, good, turn,
                reason='better_feasible_return', formula_id='labor.career_return.v1',
                inputs={'current_return': current, 'new_return': value, 'relative_gain': gain,
                        'feasibility': explanation})
            if old == good and old_employer is not None:
                success = True  # Leaving paid work for the same occupation.
            if success and old_employer is not None:
                from labor_contract import quit_job
                quit_job(person, region, turn, penalty=penalty)
        if success:
            done.add(person.id)
            entered += int(old is None)
            switched += int(old is not None and old != good)
            emit(region, kind='career_choice', record_class='decision', phase='labor',
                 subject={'type': 'agent', 'id': person.id, 'tile': region.name},
                 metric_id='labor.career_choice', unit='occupation', after=good.name,
                 inputs={'current_return': current, 'new_return': value,
                         'relative_gain': gain, 'feasibility': explanation})
    for key, row in state['budgets'].items():
        emit(region, kind='profession_departure_budget', record_class='calculation', phase='labor',
             subject={'type': 'tile', 'id': region.name, 'good': key},
             metric_id='labor.departure_budget', unit='workers', after=row['used'],
             formula_id='labor.profession_departure_budget.v1', inputs=dict(row))
    return {'processed': len(people), 'switched': switched, 'hired': hired, 'entered': entered,
            'n_groups': 1, 'active_group': 0, 'deferred': 0}
