import unittest
from types import SimpleNamespace
from unittest.mock import patch

from government import Government
from macro.imperialism.manager import ImperialismManager
from macro.imperialism.models import CustomsReceivership


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(with_trace=True):
    debtor_government = Government('Colony Treasury', 1, initial_cash=100.0)
    creditor_government = Government('Empire Treasury', 2, initial_cash=50.0)
    port_government = Government('Port Treasury', 3, initial_cash=10.0)
    debtor_government.currency = 'COL'
    creditor_government.currency = 'GBP'
    port_government.currency = 'COL'
    trace = MemoryTrace()
    region = SimpleNamespace(
        name='Port', home_currency='COL', gov=port_government,
        _collective_trace_clock={'turn': 4, 'phase': 'government', 'next': 1})
    if with_trace:
        region._run_trace = trace
    debtor = SimpleNamespace(name='Colony', currency='COL',
                             government=debtor_government, tiles=[region])
    region.owner_nation = debtor
    creditor = SimpleNamespace(name='Empire', currency='GBP',
                               government=creditor_government, tiles=[])
    receiver = CustomsReceivership(
        receivership_id='rec_test', creditor_nation='Empire',
        debtor_nation='Colony', intercept_share=0.4, remaining_debt=100.0,
        total_collected=0.0, creditor_obj=creditor)
    manager = ImperialismManager()
    manager.receiverships.append(receiver)
    return region, debtor, creditor, receiver, manager, trace


class ImperialRevenueTraceTests(unittest.TestCase):
    def test_tariff_interception_links_credit_debt_reduction_and_net_receipts(self):
        region, debtor, creditor, receiver, manager, trace = _fixture()
        creditor_before = creditor.government.agent.cash
        debtor_before = debtor.government.agent.cash
        local_before = region.gov.agent.cash

        with patch('imperialism.get_imperialism_manager', return_value=manager):
            region.gov.receive_tariff(4, 100.0, region)

        self.assertAlmostEqual(creditor.government.agent.cash, creditor_before + 40.0)
        self.assertAlmostEqual(debtor.government.agent.cash, debtor_before + 48.0)
        self.assertAlmostEqual(region.gov.agent.cash, local_before + 12.0)
        self.assertAlmostEqual(receiver.remaining_debt, 60.0)
        self.assertAlmostEqual(receiver.total_collected, 40.0)

        interception = next(row for row in trace.rows
                            if row.get('kind') == 'customs_receivership_revenue_interception')
        contract = interception['inputs']['transfer_contract']
        self.assertEqual(contract['payer_account']['balance_status'],
                         'aggregate_source_not_identified')
        self.assertEqual(contract['payee_account']['balance_before'], creditor_before)
        self.assertEqual(contract['payee_account']['balance_after'], creditor_before + 40.0)
        self.assertTrue(contract['counterparty_currency_mismatch'])
        self.assertTrue(contract['unconverted_currency_mismatch'])

        debt = next(row for row in trace.rows
                    if row.get('metric_id') == 'finance.receivership_balance')
        self.assertEqual((debt['before'], debt['after']), (100.0, 60.0))
        self.assertEqual(debt['cause_event_ids'], [interception['event_id']])
        receipt_rows = [row for row in trace.rows
                        if row.get('kind') == 'tariff_collected']
        self.assertEqual([row['after'] for row in receipt_rows], [48.0, 12.0])
        for receipt in receipt_rows:
            self.assertEqual(set(receipt['cause_event_ids']),
                             {interception['event_id'], debt['event_id']})
            self.assertEqual(receipt['inputs']['gross_tariff'], 100.0)
            self.assertEqual(receipt['inputs']['intercepted_tariff'], 40.0)

    def test_tariff_reception_state_matches_with_tracing_disabled(self):
        traced = _fixture(True)
        untraced = _fixture(False)
        for region, _, _, _, manager, _ in (traced, untraced):
            with patch('imperialism.get_imperialism_manager', return_value=manager):
                region.gov.receive_tariff(4, 100.0, region)

        def state(fixture):
            region, debtor, creditor, receiver, _, _ = fixture
            return (debtor.government.agent.cash, creditor.government.agent.cash,
                    region.gov.agent.cash, receiver.remaining_debt,
                    receiver.total_collected,
                    dict(debtor.government._income_pending),
                    dict(creditor.government._income_pending),
                    dict(region.gov._income_pending))

        self.assertEqual(state(traced), state(untraced))

    def test_missing_creditor_is_visible_without_fabricating_a_treasury_leg(self):
        region, _, _, receiver, manager, trace = _fixture()
        receiver.creditor_nation = 'missing-creditor-for-trace-test'
        receiver.creditor_obj = None

        net, intercepted, creditor_name = manager.intercept_revenue(
            'Colony', 50.0, 4, trace_region=region)

        self.assertEqual((net, intercepted, creditor_name),
                         (30.0, 20.0, receiver.creditor_nation))
        self.assertFalse(any(row.get('kind') ==
                             'customs_receivership_revenue_interception'
                             for row in trace.rows))
        balance = next(row for row in trace.rows
                       if row.get('metric_id') == 'finance.receivership_balance')
        self.assertFalse(balance['inputs']['creditor_cash_credited'])
        self.assertFalse(balance.get('cause_event_ids'))


if __name__ == '__main__':
    unittest.main()
