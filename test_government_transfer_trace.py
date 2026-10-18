import unittest
from types import SimpleNamespace

from government import Government, _trace_public_transfer


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        sequence = clock['next']
        clock['next'] += 1
        self.rows.append({'event_id': f'test:{sequence}', **row})


class GovernmentTransferTraceTests(unittest.TestCase):
    def test_public_outflow_and_revenue_use_shared_transfer_contract(self):
        trace = MemoryTrace()
        clock = {'turn': 5, 'phase': 'government', 'next': 1}
        nation = SimpleNamespace(name='North', currency='NRC')
        region = SimpleNamespace(name='Delta', owner_nation=nation,
                                 home_currency='NRC', _run_trace=trace,
                                 _collective_trace_clock=clock, _last_turn=5)
        government = Government('North', 0)
        government.regions = [region]
        government.agent.cash = 90.0

        _trace_public_transfer(government, 'welfare_distributed', 10.0,
                               [101, 202], turn=5)
        government.agent.cash = 100.0
        _trace_public_transfer(government, 'legacy_tax_collected', 10.0, [],
                               outflow=False, tax_source='legacy_collect_tax',
                               turn=5)

        self.assertEqual(len(trace.rows), 2)
        welfare, tax = [row['inputs']['transfer_contract'] for row in trace.rows]
        self.assertEqual(welfare['contract_version'], 'treasury_transfer.v1')
        self.assertEqual(welfare['side'], 'payer')
        self.assertEqual(welfare['payer_account']['balance_before'], 100.0)
        self.assertEqual(welfare['payer_account']['balance_after'], 90.0)
        self.assertEqual(welfare['payee_account']['member_ids'], ['101', '202'])
        self.assertEqual(tax['side'], 'payee')
        self.assertEqual(tax['payee_account']['balance_before'], 90.0)
        self.assertEqual(tax['payee_account']['balance_after'], 100.0)
        self.assertEqual(tax['payee_account']['currency'], 'NRC')
        self.assertNotEqual(welfare['operation_id'], tax['operation_id'])


if __name__ == '__main__':
    unittest.main()
