"""Conditional Caisse inspection rights after a reduced Egyptian payment."""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish


def _egypt(world):
    return next(n for n in world['nations'] if n.name == 'Egypt')


def _creditors(world):
    return [n for n in world['nations'] if n.name in ('Britain', 'France')]


def sign(world, written_down):
    state = world['scenario_state']
    existing = state.get('oversight_agreement') or {}
    if existing.get('status') == 'active':
        existing['conditional_write_down'] = round(
            float(existing['conditional_write_down']) + float(written_down), 2)
        existing['review_turn'] = int(world['turn']) + 3
        return
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
        from scenario_gunboat import _emit_naval_trace, _transfer_to_households
        payment_event_ids = []
        if not _transfer_to_households(
                world, egypt, cost, source='egypt_caisse_inspection_preparation',
                phase='creditor_reaction', trace_event_ids=payment_event_ids):
            if egypt.government.agent.cash < cost:
                return False, 'The treasury needs 2 units to prepare the inspection.'
            return False, 'No Egyptian inspectors can be paid.'
        confidence_before = float(state['creditor_confidence'])
        review_before = int(agreement['review_turn'])
        state['creditor_confidence'] = min(1.0, state['creditor_confidence'] + .03)
        agreement['review_turn'] = turn + 3
        _emit_naval_trace(
            world, egypt,
            kind='caisse_inspection_compliance_outcome', record_class='outcome',
            phase='creditor_reaction',
            subject={'type': 'scenario/nation', 'id': egypt.name},
            metric_id='scenario.creditor_confidence',
            before=confidence_before, after=float(state['creditor_confidence']),
            unit='ratio',
            inputs={'turn': turn, 'inspection_cost': cost,
                    'review_turn_before': review_before,
                    'review_turn_after': int(agreement['review_turn']),
                    'cause_payment_event_ids': payment_event_ids},
            cause_event_ids=payment_event_ids or None)
        return True, 'Egypt funded the next Caisse inspection and retained the conditional debt write-down.'
    if action_id == 'seek_narrower_oversight':
        if agreement.get('proposal') or agreement['scope'] == ['tax']:
            return False, 'The current inspection terms cannot be narrowed again.'
        cost = 20.0
        from scenario_situation import (_emit_situation_trace, _pay_creditors,
                                        _situation_operation_id,
                                        _trace_creditor_payment)
        source = 'narrower_oversight_terms'
        operation_id = _situation_operation_id(world, source)
        treasury_before = float(egypt.government.agent.cash)
        funding_event_id = _emit_situation_trace(
            world, kind='oversight_negotiation_funding_decision',
            record_class='decision', phase='creditor_reaction',
            subject={'type': 'scenario/nation', 'id': egypt.name},
            metric_id='scenario.creditor_response_funding',
            inputs={'operation_id': operation_id, 'source': source,
                    'treasury_cash_available': treasury_before,
                    'required_cash': cost,
                    'cash_shortfall': max(0.0, cost - treasury_before),
                    'affordable': treasury_before >= cost,
                    'decision': ('offer_narrower_terms' if treasury_before >= cost
                                 else 'reject_unaffordable_offer'),
                    'reason': ('treasury_funds_response' if treasury_before >= cost
                               else 'treasury_cash_below_response_cost')})
        if treasury_before < cost:
            _emit_situation_trace(
                world, kind='oversight_negotiation_payment_outcome',
                record_class='outcome', phase='creditor_reaction',
                subject={'type': 'scenario/nation', 'id': egypt.name},
                metric_id='scenario.creditor_effects', before=treasury_before,
                after=treasury_before,
                inputs={'operation_id': operation_id, 'source': source,
                        'success': False, 'reason': 'insufficient_treasury_cash',
                        'amount_requested': cost},
                cause_event_ids=[funding_event_id] if funding_event_id else None)
            return False, 'The treasury needs 20 units to make a narrower guarantee.'
        creditors = _creditors(world)
        amount_before = float(egypt.government.agent.cash)
        _trace_cash_write = _trace_public_begin(None, egypt.government.agent)
        egypt.government.agent.cash -= cost
        _trace_public_finish(_trace_cash_write, 'scenario_oversight:action',
                             inputs={"source_writer": 'scenario_oversight.py:action:9b66a2aa74720133:1'})
        payments = _pay_creditors(world, cost)
        payment_event_ids = _trace_creditor_payment(
            world, egypt, source, operation_id, cost, amount_before,
            float(egypt.government.agent.cash), payments,
            cause_event_ids=[funding_event_id] if funding_event_id else None)
        state['debt_ledger'].append({'turn': turn, 'kind': 'oversight_negotiation',
                                     'amount': cost, 'creditors': [n.name for n in creditors]})
        agreement['proposal'] = {'due_turn': turn + 1, 'scope': ['tax']}
        _emit_situation_trace(
            world, kind='oversight_negotiation_payment_outcome',
            record_class='outcome', phase='creditor_reaction',
            subject={'type': 'scenario/nation', 'id': egypt.name},
            metric_id='scenario.creditor_effects', before=amount_before,
            after=float(egypt.government.agent.cash),
            unit=getattr(egypt, 'currency', None) or 'local_currency',
            inputs={'operation_id': operation_id, 'source': source,
                    'success': True, 'reason': 'narrower_terms_proposed',
                    'amount_paid': cost,
                    'creditor_names': [n.name for n in creditors],
                    'proposal_due_turn': int(agreement['proposal']['due_turn']),
                    'payment_event_ids': payment_event_ids},
            cause_event_ids=[event_id for event_id in
                             ([funding_event_id] if funding_event_id else [])
                             + payment_event_ids] or None)
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
