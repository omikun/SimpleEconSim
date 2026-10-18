import json
import unittest
from types import SimpleNamespace

from metric_catalog import METRICS, TRACE_INSTRUMENTED
from scenario_politics import apply_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, treasury_cash=100.0, recipients=True, already_paid=False,
             traced=True):
    residents = [
        SimpleNamespace(id=11, cash=3.0, alive=True,
                        is_government=False, is_corporation=False,
                        home_currency='EGP'),
        SimpleNamespace(id=12, cash=7.0, alive=True,
                        is_government=False, is_corporation=False,
                        home_currency='EGP'),
    ] if recipients else []
    residents.extend([
        SimpleNamespace(id=13, cash=1.0, alive=True,
                        is_government=True, is_corporation=False),
        SimpleNamespace(id=14, cash=1.0, alive=True,
                        is_government=False, is_corporation=True),
    ])
    tile = SimpleNamespace(name='Alexandria', scenario_location='Alexandria',
                           home_currency='EGP', agents=residents)
    treasury = SimpleNamespace(id=900, cash=float(treasury_cash))
    unit = SimpleNamespace(unit_id='egypt_alexandria_garrison', morale=0.4)
    nation = SimpleNamespace(name='Egypt', currency='EGP', tiles=[tile],
                             government=SimpleNamespace(agent=treasury),
                             military_units=[unit])
    politics = {'officers_paid': already_paid, 'army_loyalty': 0.5,
                'garrison_id': unit.unit_id, 'events': []}
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {'turn': 4, 'phase': 'scenario_action',
                                        'next': 1}
    world = {'turn': 4, 'nations': [nation], 'tiles': [tile],
             'scenario_state': {'politics': politics}, 'ticker_events': []}
    return world, nation, tile, residents, treasury, unit, politics, trace


def _state(fixture):
    world, nation, tile, residents, treasury, unit, politics, _trace = fixture
    return (treasury.cash, tuple(agent.cash for agent in residents),
            politics['officers_paid'], politics['army_loyalty'], unit.morale,
            tuple(world['ticker_events']), tuple(politics['events']))


class ScenarioPoliticsTransferTraceTests(unittest.TestCase):
    def test_arrears_payment_records_treasury_and_each_household_receipt(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        self.assertTrue(apply_action(plain[0], 'pay_army_arrears')[0])
        self.assertTrue(apply_action(traced[0], 'pay_army_arrears')[0])

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[4].cash, 70.0)
        self.assertEqual([person.cash for person in traced[3]], [18.0, 22.0, 1.0, 1.0])
        funding = next(row for row in traced[7].rows
                       if row.get('kind') == 'officer_arrears_funding_decision')
        debit = next(row for row in traced[7].rows
                     if row.get('kind') == 'officer_arrears_treasury_debit')
        receipts = [row for row in traced[7].rows
                    if row.get('kind') == 'officer_arrears_household_receipt']
        outcome = next(row for row in traced[7].rows
                       if row.get('kind') == 'officer_arrears_payment_outcome')
        self.assertTrue(funding['inputs']['funded'])
        self.assertEqual(len(receipts), 2)
        self.assertEqual(debit['inputs']['transfer_contract']['amount'], 30.0)
        self.assertEqual(debit['inputs']['transfer_contract']['payer_account']['balance_before'],
                         100.0)
        self.assertEqual(debit['inputs']['transfer_contract']['payer_account']['balance_after'],
                         70.0)
        self.assertEqual([row['subject']['id'] for row in receipts], ['11', '12'])
        self.assertTrue(all(row['cause_event_ids'] == [debit['event_id']]
                            for row in receipts))
        self.assertEqual(outcome['before'], 0.5)
        self.assertEqual(outcome['after'], 0.72)
        self.assertEqual(outcome['cause_event_ids'],
                         [funding['event_id'], debit['event_id']]
                         + [row['event_id'] for row in receipts])
        morale = next(row for row in traced[7].rows
                      if row.get('kind') ==
                      'officer_arrears_garrison_morale_outcome')
        self.assertEqual(morale['before'], 0.4)
        self.assertAlmostEqual(morale['after'], 0.6)
        self.assertIn(outcome['event_id'], morale['cause_event_ids'])
        for row in traced[7].rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)

    def test_underfunded_arrears_records_gate_without_changing_cash_or_loyalty(self):
        fixture = _fixture(treasury_cash=29.0)
        self.assertFalse(apply_action(fixture[0], 'pay_army_arrears')[0])
        self.assertEqual(fixture[4].cash, 29.0)
        self.assertEqual([agent.cash for agent in fixture[3]], [3.0, 7.0, 1.0, 1.0])
        self.assertEqual(fixture[6]['army_loyalty'], 0.5)
        funding = next(row for row in fixture[7].rows
                       if row.get('kind') == 'officer_arrears_funding_decision')
        self.assertEqual(funding['inputs']['reason'], 'treasury_cash_below_cost')
        self.assertEqual(funding['inputs']['cash_shortfall'], 1.0)
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[7].rows))

    def test_missing_household_recipients_records_gate_without_payment(self):
        fixture = _fixture(recipients=False)
        self.assertFalse(apply_action(fixture[0], 'pay_army_arrears')[0])
        self.assertEqual(fixture[4].cash, 100.0)
        funding = next(row for row in fixture[7].rows
                       if row.get('kind') == 'officer_arrears_funding_decision')
        self.assertEqual(funding['inputs']['reason'], 'no_household_recipients')
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[7].rows))

    def test_already_paid_package_is_recorded_as_noop(self):
        fixture = _fixture(already_paid=True)
        self.assertFalse(apply_action(fixture[0], 'pay_army_arrears')[0])
        self.assertEqual(fixture[4].cash, 100.0)
        outcome = next(row for row in fixture[7].rows
                       if row.get('kind') == 'officer_arrears_payment_outcome')
        self.assertEqual(outcome['inputs']['reason'], 'arrears_package_already_funded')
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[7].rows))


if __name__ == '__main__':
    unittest.main()
