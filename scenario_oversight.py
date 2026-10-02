"""Conditional Caisse inspection rights after a reduced Egyptian payment."""

from __future__ import annotations


def _egypt(world):
    return next(n for n in world['nations'] if n.name == 'Egypt')


def _creditors(world):
    return [n for n in world['nations'] if n.name in ('Britain', 'France')]


def sign(world, written_down):
    state = world['scenario_state']
    state['oversight_agreement'] = {
        'status': 'active', 'scope': ['tax', 'tariff'],
        'signed_turn': int(world['turn']), 'expires_turn': int(world['scenario']['horizon_turns']),
        'review_turn': int(world['turn']) + 3,
        'conditional_write_down': round(float(written_down), 2),
        'reports': [], 'proposal': None,
    }


def action(world, action_id):
    state = world['scenario_state']
    agreement = state.get('oversight_agreement') or {}
    if agreement.get('status') != 'active':
        return False, 'No Caisse oversight agreement is in force.'
    egypt = _egypt(world)
    turn = int(world['turn'])
    if action_id == 'comply_oversight':
        cost = 2.0
        if egypt.government.agent.cash < cost:
            return False, 'The treasury needs 2 units to prepare the inspection.'
        from scenario_gunboat import _transfer_to_households
        if not _transfer_to_households(egypt, cost):
            return False, 'No Egyptian inspectors can be paid.'
        state['creditor_confidence'] = min(1.0, state['creditor_confidence'] + .03)
        agreement['review_turn'] = turn + 3
        return True, 'Egypt funded the next Caisse inspection and retained the conditional debt write-down.'
    if action_id == 'seek_narrower_oversight':
        if agreement.get('proposal') or agreement['scope'] == ['tax']:
            return False, 'The current inspection terms cannot be narrowed again.'
        cost = 20.0
        if egypt.government.agent.cash < cost:
            return False, 'The treasury needs 20 units to make a narrower guarantee.'
        egypt.government.agent.cash -= cost
        creditors = _creditors(world)
        for creditor in creditors:
            creditor.government.agent.cash += cost / len(creditors)
        state['debt_ledger'].append({'turn': turn, 'kind': 'oversight_negotiation',
                                     'amount': cost, 'creditors': [n.name for n in creditors]})
        agreement['proposal'] = {'due_turn': turn + 1, 'scope': ['tax']}
        return True, 'Egypt paid 20 units to propose tax-only Caisse inspection; creditors answer next turn.'
    if action_id == 'revoke_oversight':
        from scenario_debt import reinstate_claim
        claim = float(agreement['conditional_write_down'])
        reinstate_claim(world, claim, due_turn=min(turn + 2, int(world['scenario']['horizon_turns'])))
        agreement['status'] = 'revoked'
        state['payment_status'] = 'deferred'
        state['creditor_confidence'] = max(0.0, state['creditor_confidence'] - .25)
        state['fiscal_autonomy'] = min(1.0, state['fiscal_autonomy'] + .15)
        return True, f'Egypt revoked inspection; the conditional {claim:,.0f}-unit write-down is due again on turn {state["payment_window_turn"]}.'
    return False, 'Unknown Caisse oversight decision.'


def advance(world, turn, ticker_push):
    state = world['scenario_state']
    agreement = state.get('oversight_agreement') or {}
    if agreement.get('status') != 'active':
        return
    proposal = agreement.get('proposal')
    if proposal and turn >= int(proposal['due_turn']):
        reports = agreement['reports']
        receipts = reports[-1]['receipts'] if reports else 0.0
        accepted = state['creditor_confidence'] >= .60 and receipts >= 8.0
        if accepted:
            agreement['scope'] = list(proposal['scope'])
            state['fiscal_autonomy'] = min(1.0, state['fiscal_autonomy'] + .10)
            message = 'The Caisse accepts tax-only inspection after reviewing Egyptian receipts.'
        else:
            state['creditor_confidence'] = max(0.0, state['creditor_confidence'] - .05)
            message = 'The Caisse refuses narrower inspection because receipts or confidence are too weak.'
        agreement['proposal'] = None
        state.setdefault('creditor_news', []).append({'turn': turn, 'headline': 'Caisse inspection terms', 'body': message})
        ticker_push(world, turn, 'CREDITOR', message, (225, 178, 87))
    if turn < int(agreement['review_turn']):
        return
    governments = {_egypt(world).government}
    governments.update(tile.gov for tile in _egypt(world).tiles if getattr(tile, 'gov', None))
    receipts = sum(float(entry.get(source, 0.0))
                   for government in governments
                   for entry in getattr(government, 'income_log', [])[-3:]
                   for source in agreement['scope'])
    agreement['reports'].append({'turn': turn, 'scope': list(agreement['scope']),
                                 'receipts': round(receipts, 2)})
    agreement['review_turn'] = turn + 3
    state.setdefault('creditor_news', []).append({
        'turn': turn, 'headline': 'Caisse inspects assigned receipts',
        'body': f'Inspected {receipts:,.0f} units of {" and ".join(agreement["scope"])} receipts.'})
