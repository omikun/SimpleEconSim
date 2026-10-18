import json
import unittest
from types import SimpleNamespace

from metric_catalog import METRICS, TRACE_INSTRUMENTED
from worldview_policies import _execute_policy_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _tile(name, *, coast=True, stock=12.0, depleted=False, agents=None):
    return SimpleNamespace(
        name=name, is_coast=coast, neighbors={}, agents=list(agents or []),
        fertilizer_stock=float(stock), is_nitrate_depleted=depleted)


def _agent(agent_id, *, cash=0.0, trader=False, currency='AGR'):
    return SimpleNamespace(id=agent_id, cash=float(cash), is_trader=trader,
                           home_currency=currency)


def _fixture(*, treasury_cash=250.0, tiles=None, traced=True):
    tiles = list(tiles or [_tile('Port', stock=0, depleted=True,
                                 agents=[_agent('merchant', cash=10, trader=True)])])
    government_agent = SimpleNamespace(id='national-gov', cash=float(treasury_cash))
    nation = SimpleNamespace(name='Agraria', currency='AGR', tiles=tiles,
                             government=SimpleNamespace(agent=government_agent))
    trace = MemoryTrace()
    if traced:
        host = tiles[0]
        host._run_trace = trace
        host._collective_trace_clock = {
            'turn': 10, 'phase': 'policy_action', 'next': 1}
    world = {'turn': 10, 'tiles': tiles, 'policy_feedback': None}
    return world, nation, tiles, trace


def _state(fixture):
    world, nation, tiles, _trace = fixture
    return (nation.government.agent.cash,
            tuple((tile.fertilizer_stock, tile.is_nitrate_depleted,
                   tuple((agent.id, agent.cash) for agent in tile.agents))
                  for tile in tiles),
            world.get('policy_feedback'), tuple(world.get('ticker_events', ())))


class WorldviewGuanoSubsidyTraceTests(unittest.TestCase):
    def test_funded_subsidy_traces_exact_allocations_delivery_and_storage_cap(self):
        trader_a = _agent('merchant-a', cash=10, trader=True)
        trader_b = _agent('merchant-b', cash=30, trader=True)
        local = _agent('resident', cash=5)
        tiles = [
            _tile('Depleted Port', stock=0, depleted=True,
                  agents=[trader_a, trader_b]),
            _tile('Nearly Full Port', stock=75, agents=[local]),
        ]
        plain = _fixture(treasury_cash=250, tiles=[
            _tile('Depleted Port', stock=0, depleted=True,
                  agents=[_agent('merchant-a', cash=10, trader=True),
                          _agent('merchant-b', cash=30, trader=True)]),
            _tile('Nearly Full Port', stock=75, agents=[_agent('resident', cash=5)]),
        ], traced=False)
        traced = _fixture(treasury_cash=250, tiles=tiles, traced=True)

        _execute_policy_action(plain[0], 'nat_subsidize_guano_import', plain[1])
        _execute_policy_action(traced[0], 'nat_subsidize_guano_import', traced[1])

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[1].government.agent.cash, 150.0)
        self.assertEqual(trader_a.cash, 60.0)
        self.assertEqual(trader_b.cash, 30.0)
        self.assertEqual(local.cash, 55.0)
        self.assertEqual([tile.fertilizer_stock for tile in tiles], [20.0, 80.0])
        self.assertFalse(tiles[0].is_nitrate_depleted)

        funding = self._row(traced, 'national_guano_funding_decision')
        ports = self._row(traced, 'national_guano_port_availability')
        debit = self._row(traced, 'national_guano_subsidy_treasury_debit')
        outcome = self._row(traced, 'national_guano_subsidy_outcome')
        receipts = [row for row in traced[3].rows
                    if row.get('kind') == 'national_guano_import_payment_receipt']
        stock_rows = [row for row in traced[3].rows
                      if row.get('kind') == 'national_guano_fertilizer_stock_outcome']
        delivery_rows = [row for row in traced[3].rows
                         if row.get('kind') == 'national_guano_import_delivery']
        depletion = self._row(traced, 'national_guano_nitrate_recovery')
        self.assertTrue(funding['inputs']['funded'])
        self.assertEqual(ports['inputs']['eligible_tile_ids'],
                         ['Depleted Port', 'Nearly Full Port'])
        self.assertEqual(debit['after'], -100.0)
        contract = debit['inputs']['transfer_contract']
        self.assertEqual(contract['payer_account']['balance_before'], 250.0)
        self.assertEqual(contract['payer_account']['balance_after'], 150.0)
        self.assertEqual({row['subject']['id'] for row in receipts},
                         {'merchant-a', 'resident'})
        self.assertEqual(len(receipts), 2)
        self.assertTrue(all(row['inputs']['transfer_contract']['counterparty_leg_status']
                            == 'allocated_from_aggregate_national_treasury_debit'
                            for row in receipts))
        self.assertEqual({row['subject']['id']: row['after'] for row in stock_rows},
                         {'Depleted Port': 20.0, 'Nearly Full Port': 80.0})
        self.assertEqual({row['after'] for row in delivery_rows}, {5.0, 20.0})
        self.assertEqual(depletion['before'], True)
        self.assertEqual(depletion['after'], False)
        self.assertEqual(outcome['inputs']['agent_receipt_total'], 100.0)
        self.assertEqual(outcome['inputs']['treasury_refund_total'], 0.0)
        self.assertTrue(outcome['inputs']['cash_shares_reconciled'])
        self.assertEqual(outcome['inputs']['fertilizer_units_added'], 25.0)
        self._assert_catalogued(traced[3].rows)

    def test_insufficient_treasury_stops_before_port_search_and_mutation(self):
        fixture = _fixture(treasury_cash=40)
        before = _state(fixture)

        _execute_policy_action(fixture[0], 'nat_subsidize_guano_import', fixture[1])

        self.assertEqual(_state(fixture)[:2], before[:2])
        funding = self._row(fixture, 'national_guano_funding_decision')
        self.assertFalse(funding['inputs']['funded'])
        self.assertEqual(funding['inputs']['cash_shortfall'], 60.0)
        self.assertFalse(funding['inputs']['coastal_port_search_performed'])
        self.assertFalse(any(row.get('kind') == 'national_guano_port_availability'
                             for row in fixture[3].rows))
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[3].rows))

    def test_no_coastal_ports_does_not_charge_funded_treasury(self):
        fixture = _fixture(treasury_cash=200,
                           tiles=[_tile('Inland', coast=False)])
        before = _state(fixture)

        _execute_policy_action(fixture[0], 'nat_subsidize_guano_import', fixture[1])

        self.assertEqual(_state(fixture)[:2], before[:2])
        funding = self._row(fixture, 'national_guano_funding_decision')
        ports = self._row(fixture, 'national_guano_port_availability')
        self.assertTrue(funding['inputs']['funded'])
        self.assertEqual(ports['after'], 0)
        self.assertEqual(ports['inputs']['reason'], 'no_coastal_port_tiles')
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[3].rows))

    def test_missing_tile_agent_receives_refund_and_cash_shares_reconcile(self):
        merchant = _agent('merchant', cash=0, trader=True)
        tiles = [_tile('Merchant Port', agents=[merchant]),
                 _tile('Empty Port', agents=[])]
        fixture = _fixture(treasury_cash=200, tiles=tiles)

        _execute_policy_action(fixture[0], 'nat_subsidize_guano_import', fixture[1])

        self.assertEqual(merchant.cash, 50.0)
        self.assertEqual(fixture[1].government.agent.cash, 150.0)
        refund = self._row(fixture, 'national_guano_import_treasury_refund')
        self.assertEqual(refund['after'], 50.0)
        self.assertEqual(refund['inputs']['cash_balance_after'], 150.0)
        outcome = self._row(fixture, 'national_guano_subsidy_outcome')
        self.assertEqual(outcome['inputs']['agent_receipt_total'], 50.0)
        self.assertEqual(outcome['inputs']['treasury_refund_total'], 50.0)
        self.assertTrue(outcome['inputs']['cash_shares_reconciled'])
        self.assertEqual(outcome['inputs']['treasury_after'], 150.0)

    def _row(self, fixture, kind):
        return next(row for row in fixture[3].rows if row.get('kind') == kind)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
