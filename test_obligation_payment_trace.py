"""Causal and account-balance evidence for named obligation settlements."""

import json
import unittest

from agent import Agent
from livelihood_access import assess_obligation, settle_obligations
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'obligation-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced):
    region = Region('Parish', t=0, number_of_agents=0)
    region.home_currency = 'GBP'
    debtor = Agent(0)
    debtor.id = 11
    debtor.cash = 12.0
    debtor.alive = True
    debtor.home_currency = 'GBP'
    creditor = Agent(0)
    creditor.id = 12
    creditor.cash = 4.0
    creditor.alive = True
    creditor.home_currency = 'GBP'
    region.agents.extend([debtor, creditor])
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 2, 'phase': 'livelihood', 'next': 1}
    claim = assess_obligation(
        region, debtor.id, creditor.id, 'survey', 30.0, due_turn=2,
        interest_rate=0.1, collateral_plot_id='plot-a')
    return region, debtor, creditor, claim, trace


def _state(fixture):
    _region, debtor, creditor, claim, _trace = fixture
    return {
        'debtor_cash': debtor.cash,
        'creditor_cash': creditor.cash,
        'claim_balance': claim.balance,
        'claim_status': claim.status,
        'last_settled_turn': claim.last_settled_turn,
    }


class ObligationPaymentTraceTests(unittest.TestCase):
    def test_partial_payment_records_both_wallets_and_links_claim_settlement(self):
        baseline = _fixture(traced=False)
        traced = _fixture(traced=True)

        plain_events = settle_obligations(baseline[0], 2)
        settlement_ids_by_origin = {}
        payment_ids_by_origin = {}
        traced_events = settle_obligations(
            traced[0], 2,
            settlement_trace_event_ids_by_origin=settlement_ids_by_origin,
            payment_trace_event_ids_by_origin=payment_ids_by_origin)

        self.assertEqual(traced_events, plain_events)
        self.assertEqual(_state(traced), _state(baseline))
        self.assertEqual((traced[1].cash, traced[2].cash), (0.0, 16.0))
        self.assertEqual(traced[3].balance, 21.0)

        rows = traced[4].rows
        settlement = next(row for row in rows
                          if row.get('kind') == 'obligation_settlement')
        self.assertEqual(settlement['inputs']['balance_after_accrual_before_payment'],
                         33.0)
        self.assertEqual(settlement['inputs']['paid'], 12.0)

        payment = next(row for row in rows
                       if row.get('kind') == 'cash_obligation_payment')
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(payment['metric_id'], 'finance.cash_transfer')
        self.assertEqual(contract['operation_type'], 'cash_obligation_payment')
        self.assertEqual(contract['amount'], 12.0)
        self.assertEqual(contract['amount_currency'], 'GBP')
        self.assertEqual(contract['payer_account']['balance_before'], 12.0)
        self.assertEqual(contract['payer_account']['balance_after'], 0.0)
        self.assertEqual(contract['payee_account']['balance_before'], 4.0)
        self.assertEqual(contract['payee_account']['balance_after'], 16.0)
        self.assertEqual(payment['cause_event_ids'], [settlement['event_id']])
        self.assertEqual(settlement_ids_by_origin['survey'],
                         [settlement['event_id']])
        self.assertEqual(payment_ids_by_origin['survey'], [payment['event_id']])

        journal_event = next(event for event in traced[0].economic_events
                             if event['source_id'] == contract['operation_id'])
        self.assertEqual(payment['inputs']['actor_account_event_id'],
                         journal_event['id'])
        summary = next(row for row in rows
                       if row.get('metric_id') == 'finance.obligation_payment')
        self.assertEqual(summary['cause_event_ids'], [payment['event_id']])
        self.assertEqual(summary['inputs']['operation_id'],
                         contract['operation_id'])


if __name__ == '__main__':
    unittest.main()
