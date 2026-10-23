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
    def test_public_creditor_and_debtor_writes_close_and_link_payment(self):
        from nation import Nation
        from pathlib import Path
        import tempfile
        from run_trace import RunTrace
        from trace_audit import audit
        for public_side in ('creditor','debtor','both'):
            with self.subTest(public_side=public_side),tempfile.TemporaryDirectory() as directory:
                nation=Nation('Obligation public','C',initial_cash=100,register=False)
                tile=Region('Parish',t=0,number_of_agents=0);nation.add_tile(tile)
                private=Agent(0);private.cash=12;private.home_currency='C';tile.agents.append(private)
                debtor=nation.government.agent if public_side in ('debtor','both') else private
                creditor=tile.gov.agent if public_side in ('creditor','both') else private
                for agent in (debtor,creditor):
                    if agent not in tile.agents:tile.agents.append(agent)
                trace=RunTrace(Path(directory)/'obligation.ctr','obligation-public')
                clock={'turn':0,'phase':'setup','next':1}
                for source in (tile,nation):source._run_trace=trace;source._collective_trace_clock=clock
                trace.treasury_book.register_nations([nation],clock)
                before={('finance.treasury',nation.name):(None,'C',nation.treasury()['total'])}
                clock['turn']=1
                assess_obligation(tile,debtor.id,creditor.id,'cash_tax',30,due_turn=1)
                settle_obligations(tile,1)
                trace.treasury_book.close([nation],clock,before)
                closures=trace.query(kind='treasury_account_closure')['events']
                self.assertTrue(all(row['formula_replay']['matches'] for row in closures))
                payment=trace.query(kind='cash_obligation_payment')['events'][0]
                writes=trace.query(kind='public_account_write')['events']
                self.assertEqual(2 if public_side=='both' else 1,len(writes))
                for row in writes:
                    self.assertIn(payment['event_id'],row['cause_event_ids'])
                    self.assertEqual(payment['inputs']['operation_id'],row['inputs']['semantic_operation_id'])
                trace.checkpoint(clock)
                self.assertTrue(audit(trace.path)['structural_and_supported_formula_checks_pass'])

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
