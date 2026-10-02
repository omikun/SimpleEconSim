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


def initialize(world):
    world['scenario_state']['diplomatic_crisis'] = {
        'egyptian_proposal': None, 'proposal_due_turn': None,
        'french_policy': 'abstain', 'french_commitment': 'none',
        'french_authorization': {'demonstrate': False, 'blockade': False, 'bombard': False},
        'british_policy': 'observe', 'ottoman_offer': None,
        'treaty': None, 'reasons': {}, 'history': [],
        'policy_lock': None,
    }


def _record(world, actor, decision, reason):
    state = world['scenario_state']['diplomatic_crisis']
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
    crisis = state['diplomatic_crisis']
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


def french_policy(world):
    from scenario_debt import bonds, outstanding
    state = world['scenario_state']
    crisis = state['diplomatic_crisis']
    france = _nation(world, 'France')
    if france is None or outstanding(world) <= .01:
        return 'abstain', 'France has no unsettled claim to enforce.'
    exposure = sum(bond.principal for bond in bonds(world) if bond.holder_nation == 'France')
    cash = float(france.government.agent.cash)
    unrest = _energy(world, 'France')
    locked = crisis.get('policy_lock')
    if locked and unrest < 6 and (locked != 'join_enforcement' or cash >= 8):
        return locked, 'France maintains its recorded commitment for this crisis.'
    proposal = crisis.get('egyptian_proposal')
    if proposal == 'mediation' and cash >= 20 and unrest < 6:
        return 'mediate', f'France holds {exposure:,.0f} in claims and sees a funded settlement as less costly than force.'
    if proposal == 'oppose_unilateral' and (unrest >= 2.5 or state['geography']['canal_open']):
        return 'oppose', 'Paris opposes exclusive British control while its own claims remain at risk.'
    if proposal == 'joint_guarantee' and cash >= 20 and unrest < 5:
        return 'joint_guarantor', 'France accepts a shared collection guarantee if Britain and Egypt sign it.'
    if unrest >= 6:
        return 'oppose', f'French domestic protest ({unrest:.1f}/10) makes armed enforcement untenable.'
    if unrest >= 4 or cash < 40:
        return 'abstain', f'French protest ({unrest:.1f}/10) or treasury cash limits its commitment.'
    if not state['geography']['canal_open'] and cash >= 60 and unrest < 2.5:
        return 'join_enforcement', 'Canal denial threatens French access and its creditor claim; Paris funds a squadron.'
    return 'endorse', 'France supports collection of its claim but has not authorized military force.'


def british_policy(world, french_stance):
    from scenario_debt import outstanding
    state = world['scenario_state']
    britain = _nation(world, 'Britain')
    if britain is None or outstanding(world) <= .01:
        return 'withdraw', 'No collectible British claim remains.'
    cash = float(britain.government.agent.cash)
    unrest = _energy(world, 'Britain')
    from scenario_situation import situation_template
    extra_cost = mobilization_cost(french_stance) - float(situation_template()['naval_crisis']['mobilization_cost'])
    protest_limit = 5.5 if french_stance == 'oppose' else 6.5
    if cash < float(situation_template()['naval_crisis']['mobilization_cost']) + extra_cost or unrest >= protest_limit:
        return 'withdraw', f'Britain lacks a funded, politically viable expedition (cash {cash:.0f}; protest {unrest:.1f}).'
    return 'intervene', f'Britain can fund its claim; French {french_stance.replace("_", " ")} changes the diplomatic cost.'


def mobilization_cost(french_stance):
    from scenario_situation import situation_template
    base = float(situation_template()['naval_crisis']['mobilization_cost'])
    return base + (20.0 if french_stance == 'oppose' else -5.0 if french_stance == 'endorse' else 0.0)


def british_reply_to_offer(world, offer, french_stance, military_policy):
    """Compare treaty receipts against bounded expedition receipts and cost."""
    from scenario_debt import outstanding
    claim = outstanding(world)
    remaining = max(0, int(world['scenario']['horizon_turns']) - int(world['turn']))
    protest = _energy(world, 'Britain')
    canal_value = 25.0 if world['scenario_state']['geography']['canal_open'] else 80.0
    military_value = (min(claim, 5.0 * remaining) + canal_value
                      - mobilization_cost(french_stance) - 16.0 - protest * 5.0)
    treaty_value = (claim * .5 if offer == 'mediation'
                    else min(claim, 5.0 * remaining) * .5)
    if military_policy == 'withdraw' or treaty_value >= military_value:
        return 'accept', (f'Expected treaty recovery {treaty_value:,.0f} exceeds the net '
                          f'expedition estimate {military_value:,.0f}.')
    return 'proceed_alone', (f'Expected expedition value {military_value:,.0f} exceeds '
                             f'treaty recovery {treaty_value:,.0f}.')


def evaluate(world):
    crisis = world['scenario_state']['diplomatic_crisis']
    policy, french_reason = french_policy(world)
    british, british_reason = british_policy(world, policy)
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
    return policy, british


def advance(world, turn, ticker_push):
    crisis = world['scenario_state']['diplomatic_crisis']
    if not crisis.get('egyptian_proposal') or turn < int(crisis['proposal_due_turn']):
        return
    french, british = evaluate(world)
    offer = crisis['egyptian_proposal']
    crisis['policy_lock'] = french
    if offer == 'oppose_unilateral':
        reply = 'proceed_alone' if british == 'intervene' else 'withdraw'
        reason = crisis['reasons'].get('Britain', 'London reassesses the cost of acting without France.')
    elif (offer == 'mediation' and french != 'mediate'
          or offer == 'joint_guarantee' and french != 'joint_guarantor'):
        reply = 'no_french_offer'
        reason = 'France declined the requested role, so London has no joint terms to accept.'
    else:
        reply, reason = british_reply_to_offer(world, offer, french, british)
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
    crisis = state['diplomatic_crisis']
    if response_id == 'reject':
        _record(world, 'Egypt', 'reject_terms', 'Cairo rejected the foreign proposal and retained its claim dispute.')
        return True, 'Egypt rejects the proposed terms; the creditor dispute continues.'
    if kind == 'french_terms':
        from scenario_debt import pay
        amount = round(float(state['scheduled_remittance']) * .5, 2)
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
