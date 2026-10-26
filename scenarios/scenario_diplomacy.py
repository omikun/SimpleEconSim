"""Separate French, British, and Ottoman decisions in the Egypt crisis."""

from __future__ import annotations


OFFERS = {
    'request_french_mediation': 'mediation',
    'offer_joint_guarantee': 'joint_guarantee',
    'seek_french_opposition': 'oppose_unilateral',
}


def _nation(world, name):
    return next((nation for nation in world['nations'] if nation.name == name), None)


def _energy(world, name):
    report = next((item for item in world['scenario_state'].get('foreign_reports', [])
                   if item['nation'] == name), None)
    return float(report['energy']) if report else 0.0


def _trace_region(world):
    return next((tile for tile in world.get('tiles', [])
                 if getattr(tile, '_run_trace', None) is not None), None)


def _trace_decision(world, *, actor, decision, policy, inputs,
                    cause_event_ids=None, formula_id=None):
    region = _trace_region(world)
    if region is None:
        return None
    from run_trace import emit
    return emit(
        region, kind='scenario_diplomacy_ai_decision',
        record_class='decision', phase='scenario_diplomacy',
        subject={'type': 'scenario/nation', 'id': actor},
        metric_id='scenario.foreign_diplomacy_ai',
        formula_id=formula_id,
        inputs={'turn': int(world.get('turn', 0)), 'decision': decision,
                'policy': policy, **inputs},
        cause_event_ids=cause_event_ids)


def initialize(world):
    world['scenario_state']['diplomatic_crisis'] = {
        'egyptian_proposal': None, 'proposal_due_turn': None,
        'french_policy': 'abstain', 'french_commitment': 'none',
        'french_authorization': {'demonstrate': False, 'blockade': False, 'bombard': False},
        'british_policy': 'observe', 'ottoman_offer': None,
        'treaty': None, 'reasons': {}, 'history': [],
        'policy_lock': None,
    }


def ensure(world):
    if not world['scenario_state'].get('diplomatic_crisis'):
        initialize(world)
    return world['scenario_state']['diplomatic_crisis']


def _record(world, actor, decision, reason):
    state = ensure(world)
    entry = {'turn': int(world['turn']), 'actor': actor, 'decision': decision, 'reason': reason}
    state['history'].append(entry)
    state['reasons'][actor] = reason
    world['scenario_state'].setdefault('creditor_news', []).append({
        'turn': int(world['turn']), 'headline': f'{actor}: {decision}', 'body': reason})
    return entry


def make_offer(world, action_id):
    if action_id not in OFFERS:
        return False, 'Unknown diplomatic offer.'
    state = world['scenario_state']
    crisis = ensure(world)
    if crisis.get('egyptian_proposal'):
        return False, 'A diplomatic offer is already awaiting a reply.'
    if state['payment_status'] not in ('defaulted', 'deferred', 'unpaid'):
        return False, 'A live creditor dispute is needed for this offer.'
    if state['naval_crisis'].get('stage') not in ('none', 'mobilizing', 'ultimatum', 'blockaded'):
        return False, 'The current military phase cannot accept this offer.'
    if int(world['turn']) >= int(world['scenario']['horizon_turns']):
        return False, 'No turn remains for Paris to answer this offer.'
    crisis['egyptian_proposal'] = OFFERS[action_id]
    crisis['proposal_due_turn'] = int(world['turn']) + 1
    _record(world, 'Egypt', OFFERS[action_id], 'Cairo requested a decision from Paris before the next escalation.')
    return True, f'Cairo offered {OFFERS[action_id].replace("_", " ")}; France answers next turn.'


def _french_policy_assessment(world):
    from scenario_debt import bonds, outstanding
    state = world['scenario_state']
    crisis = ensure(world)
    france = _nation(world, 'France')
    claim = outstanding(world)
    if france is None or claim <= .01:
        row = {'candidate': 'abstain_no_collectible_claim', 'priority': 1,
               'eligible': True, 'selected': True,
               'reason': 'france_missing' if france is None else
               'claim_at_or_below_minimum',
               'gates': {'france_available': france is not None,
                         'claim_above_0_01': claim > .01}}
        return ('abstain', 'France has no unsettled claim to enforce.',
                {'claim': claim, 'candidates': [row],
                 'selected_candidate': row['candidate']})
    exposure = sum(bond.principal for bond in bonds(world) if bond.holder_nation == 'France')
    cash = float(france.government.agent.cash)
    unrest = _energy(world, 'France')
    locked = crisis.get('policy_lock')
    proposal = crisis.get('egyptian_proposal')
    canal_open = bool(state['geography']['canal_open'])
    gates = [
        ('maintain_locked_commitment', bool(locked) and unrest < 6
         and (locked != 'join_enforcement' or cash >= 8),
         {'policy_lock_present': bool(locked), 'protest_below_6': unrest < 6,
          'enforcement_cash_gate': locked != 'join_enforcement' or cash >= 8}),
        ('mediation_offer', proposal == 'mediation' and cash >= 20 and unrest < 6,
         {'proposal_is_mediation': proposal == 'mediation',
          'cash_at_least_20': cash >= 20, 'protest_below_6': unrest < 6}),
        ('oppose_unilateral_control', proposal == 'oppose_unilateral'
         and (unrest >= 2.5 or canal_open),
         {'proposal_is_unilateral_opposition': proposal == 'oppose_unilateral',
          'protest_at_least_2_5': unrest >= 2.5,
          'canal_open': canal_open}),
        ('joint_guarantee_offer', proposal == 'joint_guarantee'
         and cash >= 20 and unrest < 5,
         {'proposal_is_joint_guarantee': proposal == 'joint_guarantee',
          'cash_at_least_20': cash >= 20, 'protest_below_5': unrest < 5}),
        ('domestic_protest_forces_opposition', unrest >= 6,
         {'protest_at_least_6': unrest >= 6}),
        ('protest_or_treasury_limits_commitment', unrest >= 4 or cash < 40,
         {'protest_at_least_4': unrest >= 4, 'cash_below_40': cash < 40}),
        ('canal_denial_funds_enforcement', not canal_open and cash >= 60
         and unrest < 2.5,
         {'canal_closed': not canal_open, 'cash_at_least_60': cash >= 60,
          'protest_below_2_5': unrest < 2.5}),
        ('endorse_without_military_authorization', True, {}),
    ]
    selected_rule = next(rule for rule, eligible, _ in gates if eligible)
    if selected_rule == 'maintain_locked_commitment':
        policy, reason = locked, 'France maintains its recorded commitment for this crisis.'
    elif selected_rule == 'mediation_offer':
        policy = 'mediate'
        reason = (f'France holds {exposure:,.0f} in claims and sees a funded settlement '
                  'as less costly than force.')
    elif selected_rule == 'oppose_unilateral_control':
        policy = 'oppose'
        reason = 'Paris opposes exclusive British control while its own claims remain at risk.'
    elif selected_rule == 'joint_guarantee_offer':
        policy = 'joint_guarantor'
        reason = 'France accepts a shared collection guarantee if Britain and Egypt sign it.'
    elif selected_rule == 'domestic_protest_forces_opposition':
        policy = 'oppose'
        reason = f'French domestic protest ({unrest:.1f}/10) makes armed enforcement untenable.'
    elif selected_rule == 'protest_or_treasury_limits_commitment':
        policy = 'abstain'
        reason = f'French protest ({unrest:.1f}/10) or treasury cash limits its commitment.'
    elif selected_rule == 'canal_denial_funds_enforcement':
        policy = 'join_enforcement'
        reason = 'Canal denial threatens French access and its creditor claim; Paris funds a squadron.'
    else:
        policy = 'endorse'
        reason = 'France supports collection of its claim but has not authorized military force.'

    candidates = []
    earlier_selected = False
    for priority, (rule, eligible, rule_gates) in enumerate(gates, 1):
        selected = rule == selected_rule
        candidates.append({
            'candidate': rule, 'priority': priority, 'eligible': eligible,
            'selected': selected, 'gates': rule_gates,
            'reason': ('selected_by_policy_priority' if selected else
                       'higher_priority_rule_selected' if eligible and earlier_selected else
                       'fallback_rule' if rule == 'endorse_without_military_authorization' else
                       'required_gates_not_met')})
        earlier_selected = earlier_selected or selected
    return policy, reason, {
        'claim': claim, 'french_claim_exposure': exposure,
        'treasury_cash': cash, 'domestic_protest': unrest,
        'proposal': proposal, 'policy_lock': locked,
        'canal_open': canal_open, 'candidates': candidates,
        'selected_candidate': selected_rule}


def french_policy(world):
    policy, reason, _assessment = _french_policy_assessment(world)
    return policy, reason


def _british_policy_assessment(world, french_stance):
    from scenario_debt import outstanding
    state = world['scenario_state']
    britain = _nation(world, 'Britain')
    claim = outstanding(world)
    if britain is None or claim <= .01:
        row = {'candidate': 'withdraw_no_collectible_claim', 'priority': 1,
               'eligible': True, 'selected': True,
               'reason': 'britain_missing' if britain is None else
               'claim_at_or_below_minimum',
               'gates': {'britain_available': britain is not None,
                         'claim_above_0_01': claim > .01}}
        return ('withdraw', 'No collectible British claim remains.',
                {'claim': claim, 'french_stance': french_stance,
                 'candidates': [row], 'selected_candidate': row['candidate']})
    cash = float(britain.government.agent.cash)
    unrest = _energy(world, 'Britain')
    from scenario_situation import situation_template
    extra_cost = mobilization_cost(french_stance) - float(situation_template()['naval_crisis']['mobilization_cost'])
    from scenario_projects import effectiveness
    line = effectiveness(world, 'canal_line', 'Tel el Kebir')
    extra_cost += 12.0 * line
    protest_limit = 5.5 if french_stance == 'oppose' else 6.5
    base_cost = float(situation_template()['naval_crisis']['mobilization_cost'])
    required_cash = base_cost + extra_cost
    cash_gate = cash >= required_cash
    protest_gate = unrest < protest_limit
    eligible = cash_gate and protest_gate
    policy = 'intervene' if eligible else 'withdraw'
    reason = (f'Britain can fund its claim; French {french_stance.replace("_", " ")} '
              f'and the prepared canal line ({line:.0%}) change the expected cost.')
    if not eligible:
        reason = (f'Britain lacks a funded, politically viable expedition '
                  f'(cash {cash:.0f}; protest {unrest:.1f}; prepared canal line {line:.0%}).')
    candidates = [
        {'candidate': 'withdraw_unfunded_or_unpopular_expedition',
         'priority': 1, 'eligible': not eligible, 'selected': not eligible,
         'gates': {'cash_at_least_required': cash_gate,
                   'protest_below_limit': protest_gate,
                   'required_cash': required_cash,
                   'protest_limit': protest_limit},
         'reason': ('insufficient_cash' if not cash_gate else
                    'domestic_protest_at_or_above_limit' if not protest_gate else
                    'intervention_gates_passed')},
        {'candidate': 'intervene_to_collect_claim', 'priority': 2,
         'eligible': eligible, 'selected': eligible,
         'gates': {'cash_at_least_required': cash_gate,
                   'protest_below_limit': protest_gate},
         'reason': ('selected_by_funding_and_protest_gates' if eligible else
                    'expedition_not_funded_or_politically_viable')},
    ]
    return policy, reason, {
        'claim': claim, 'treasury_cash': cash, 'domestic_protest': unrest,
        'french_stance': french_stance, 'prepared_canal_line': line,
        'base_mobilization_cost': base_cost,
        'additional_mobilization_cost': extra_cost,
        'required_cash': required_cash, 'protest_limit': protest_limit,
        'candidates': candidates,
        'selected_candidate': candidates[0 if not eligible else 1]['candidate']}


def british_policy(world, french_stance):
    policy, reason, _assessment = _british_policy_assessment(world, french_stance)
    return policy, reason


def mobilization_cost(french_stance):
    from scenario_situation import situation_template
    base = float(situation_template()['naval_crisis']['mobilization_cost'])
    return base + (20.0 if french_stance == 'oppose' else -5.0 if french_stance == 'endorse' else 0.0)


def british_reply_to_offer(world, offer, french_stance, military_policy,
                           *, cause_event_ids=None):
    """Compare treaty receipts against bounded expedition receipts and cost."""
    from scenario_debt import outstanding
    claim = outstanding(world)
    remaining = max(0, int(world['scenario']['horizon_turns']) - int(world['turn']))
    protest = _energy(world, 'Britain')
    canal_value = 25.0 if world['scenario_state']['geography']['canal_open'] else 80.0
    from scenario_projects import effectiveness
    line = effectiveness(world, 'canal_line', 'Tel el Kebir')
    military_value = (min(claim, 5.0 * remaining) + canal_value
                      - mobilization_cost(french_stance) - 16.0 - protest * 5.0
                      - 25.0 * line)
    treaty_value = (claim * .5 if offer == 'mediation'
                    else min(claim, 5.0 * remaining) * .5)
    if military_policy == 'withdraw' or treaty_value >= military_value:
        reply = 'accept'
        reason = (f'Expected treaty recovery {treaty_value:,.0f} exceeds the net '
                  f'expedition estimate {military_value:,.0f}.')
        selected_candidate = 'accept_treaty_terms'
    else:
        reply = 'proceed_alone'
        reason = (f'Expected expedition value {military_value:,.0f} exceeds '
                  f'treaty recovery {treaty_value:,.0f}.')
        selected_candidate = 'proceed_without_french_terms'
    _trace_decision(
        world, actor='Britain', decision='evaluate_diplomatic_offer',
        policy=reply, formula_id='scenario.british_offer_value.v1',
        cause_event_ids=cause_event_ids,
        inputs={
            'offer': offer, 'french_stance': french_stance,
            'military_policy': military_policy,
            'claim_outstanding': claim, 'turns_remaining': remaining,
            'canal_access_value': canal_value,
            'prepared_canal_line_effectiveness': line,
            'expected_military_recovery': min(claim, 5.0 * remaining),
            'mobilization_cost': mobilization_cost(french_stance),
            'fixed_expedition_cost': 16.0,
            'domestic_protest_cost': protest * 5.0,
            'prepared_line_cost': 25.0 * line,
            'military_value': military_value, 'treaty_value': treaty_value,
            'comparison': 'accept_if_withdraw_or_treaty_value_ge_military_value',
            'candidates': [
                {'candidate': 'accept_treaty_terms',
                 'eligible': military_policy == 'withdraw'
                 or treaty_value >= military_value,
                 'selected': selected_candidate == 'accept_treaty_terms',
                 'reason': ('military_policy_is_withdraw'
                            if military_policy == 'withdraw' else
                            'treaty_value_meets_or_exceeds_military_value'
                            if treaty_value >= military_value else
                            'treaty_value_below_military_value')},
                {'candidate': 'proceed_without_french_terms',
                 'eligible': military_policy != 'withdraw'
                 and treaty_value < military_value,
                 'selected': selected_candidate == 'proceed_without_french_terms',
                 'reason': ('military_value_exceeds_treaty_value'
                            if military_policy != 'withdraw'
                            and treaty_value < military_value else
                            'acceptance_rule_selected')},
            ],
            'selected_candidate': selected_candidate, 'reason': reason})
    return reply, reason


def _evaluate(world):
    crisis = ensure(world)
    policy, french_reason, french_assessment = _french_policy_assessment(world)
    british, british_reason, british_assessment = _british_policy_assessment(
        world, policy)
    french_event_id = _trace_decision(
        world, actor='France', decision='assess_creditor_crisis', policy=policy,
        inputs={**french_assessment, 'reason': french_reason})
    british_event_id = _trace_decision(
        world, actor='Britain', decision='assess_creditor_crisis', policy=british,
        inputs={**british_assessment, 'reason': british_reason},
        cause_event_ids=[french_event_id] if french_event_id else None)
    if (crisis['french_policy'], crisis['british_policy']) != (policy, british):
        _record(world, 'France', policy, french_reason)
        _record(world, 'Britain', british, british_reason)
    crisis['french_policy'] = policy
    crisis['british_policy'] = british
    crisis['french_commitment'] = {
        'endorse': 'endorsement', 'mediate': 'mediator',
        'joint_guarantor': 'joint_guarantor', 'join_enforcement': 'joint_enforcement',
    }.get(policy, 'none')
    crisis['french_authorization'] = {
        'demonstrate': policy == 'join_enforcement',
        'blockade': policy == 'join_enforcement',
        'bombard': policy == 'join_enforcement' and _energy(world, 'France') < 1.5,
    }
    return policy, british, french_event_id, british_event_id


def evaluate(world):
    policy, british, _french_event_id, _british_event_id = _evaluate(world)
    return policy, british


def advance(world, turn, ticker_push):
    crisis = ensure(world)
    if not crisis.get('egyptian_proposal') or turn < int(crisis['proposal_due_turn']):
        return
    french, british, french_event_id, british_event_id = _evaluate(world)
    offer = crisis['egyptian_proposal']
    crisis['policy_lock'] = french
    if offer == 'oppose_unilateral':
        reply = 'proceed_alone' if british == 'intervene' else 'withdraw'
        reason = crisis['reasons'].get('Britain', 'London reassesses the cost of acting without France.')
        _trace_decision(
            world, actor='Britain', decision='respond_to_unilateral_opposition',
            policy=reply,
            cause_event_ids=[british_event_id] if british_event_id else None,
            inputs={'offer': offer, 'french_policy': french,
                    'british_funding_policy': british, 'reason': reason,
                    'candidates': [
                        {'candidate': 'proceed_alone',
                         'eligible': british == 'intervene',
                         'selected': reply == 'proceed_alone',
                         'reason': ('funded_expedition_remains_viable'
                                    if british == 'intervene' else
                                    'expedition_not_viable')},
                        {'candidate': 'withdraw',
                         'eligible': british == 'withdraw',
                         'selected': reply == 'withdraw',
                         'reason': ('expedition_not_viable'
                                    if british == 'withdraw' else
                                    'funded_expedition_remains_viable')},
                    ]})
    elif (offer == 'mediation' and french != 'mediate'
          or offer == 'joint_guarantee' and french != 'joint_guarantor'):
        reply = 'no_french_offer'
        reason = 'France declined the requested role, so London has no joint terms to accept.'
        _trace_decision(
            world, actor='Britain', decision='respond_to_diplomatic_offer',
            policy=reply,
            cause_event_ids=[french_event_id] if french_event_id else None,
            inputs={'offer': offer, 'french_policy': french, 'reason': reason,
                    'candidates': [
                        {'candidate': 'accept_joint_terms', 'eligible': False,
                         'selected': False,
                         'reason': 'requested_french_role_not_offered'},
                        {'candidate': 'decline_without_french_terms',
                         'eligible': True, 'selected': True,
                         'reason': 'france_declined_requested_role'},
                    ]})
    else:
        reply, reason = british_reply_to_offer(
            world, offer, french, british,
            cause_event_ids=[british_event_id]
            if british_event_id else None)
    _record(world, 'Britain', reply, reason)
    if offer == 'mediation' and french == 'mediate' and reply == 'accept':
        crisis['ottoman_offer'] = None
        world['scenario_warning_modal'] = {'kind': 'french_terms'}
        world['playing'] = False
        _record(world, 'Britain', 'consider_french_terms', 'London will accept half the claim if Cairo signs a French-brokered settlement.')
    elif offer == 'joint_guarantee' and french == 'joint_guarantor' and reply == 'accept':
        world['scenario_warning_modal'] = {'kind': 'joint_guarantee_terms'}
        world['playing'] = False
        _record(world, 'Britain', 'consider_joint_guarantee', 'London will accept capped shared collection instead of an expedition.')
    else:
        ticker_push(world, turn, 'DIPLOMACY', f'France {french.replace("_", " ")}; Britain {british}.', (190, 180, 125))
    crisis['egyptian_proposal'] = None
    crisis['proposal_due_turn'] = None


def resolve_terms(world, response_id):
    warning = world.get('scenario_warning_modal') or {}
    kind = warning.get('kind')
    if kind not in ('french_terms', 'joint_guarantee_terms'):
        return False, 'No diplomatic terms await Egypt.'
    if response_id not in ('accept', 'reject'):
        return False, 'Unknown diplomatic response.'
    state = world['scenario_state']
    crisis = ensure(world)
    if response_id == 'reject':
        _record(world, 'Egypt', 'reject_terms', 'Cairo rejected the foreign proposal and retained its claim dispute.')
        return True, 'Egypt rejects the proposed terms; the creditor dispute continues.'
    if kind == 'french_terms':
        from scenario_debt import pay, outstanding
        amount = round(outstanding(world) * .5, 2)
        ok, reason = pay(world, amount, kind='french_mediation', forgive_remainder=True)
        if not ok:
            return False, reason
        state['payment_status'] = 'restructured'
        state['settlement_path'] = 'french_mediation'
        terms = {'kind': 'french_mediation', 'signatories': ['Egypt', 'Britain', 'France'],
                 'payment': amount, 'revenue_control': 'Egypt', 'status': 'active'}
        from scenario_gunboat import withdraw
        if state['naval_crisis'].get('stage') in ('mobilizing', 'ultimatum', 'blockaded'):
            withdraw(world, 'France brokers a paid settlement; Britain withdraws.', cause='settlement')
        message = f'Egypt pays {amount:,.0f} under French mediation; the claim is settled.'
    else:
        from scenario_debt import set_collection_assignment
        set_collection_assignment(world, 5, origin='joint_guarantee')
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - .10)
        terms = {'kind': 'joint_guarantee', 'signatories': ['Egypt', 'Britain', 'France'],
                 'revenue_control': 'Caisse', 'status': 'active'}
        from scenario_gunboat import withdraw
        if state['naval_crisis'].get('stage') in ('mobilizing', 'ultimatum', 'blockaded'):
            withdraw(world, 'Egypt, Britain, and France sign a shared collection guarantee.', cause='settlement')
        message = 'Egypt signs a capped joint Caisse assignment with Britain and France.'
    crisis['treaty'] = terms
    _record(world, 'Egypt', 'accept_terms', message)
    state.setdefault('actions_taken', []).append({'turn': int(world['turn']),
                                                   'action': response_id, 'message': message})
    return True, message
