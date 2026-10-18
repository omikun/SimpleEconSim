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


def _tile(name, bank_capital, municipal_cash, fertility=1.0):
    return SimpleNamespace(
        name=name, home_currency='EGP',
        bank=SimpleNamespace(capital=float(bank_capital)),
        gov=SimpleNamespace(agent=SimpleNamespace(id=f'gov-{name}',
                                                  cash=float(municipal_cash))),
        owner_nation=None, soil_fertility=float(fertility))


def _province_fixture(*, treasury_cash=300.0, fertility=(1.0, 1.47),
                      with_tiles=True, traced=True):
    tiles = [_tile('Poor District', 4.0, 5.0, fertility[0]),
             _tile('Rich District', 20.0, 30.0, fertility[1])] if with_tiles else []
    province = SimpleNamespace(
        name='Nile Province', currency='EGP', tiles=tiles,
        gov=SimpleNamespace(agent=SimpleNamespace(
            id='province-gov', cash=float(treasury_cash))))
    trace = MemoryTrace()
    world_tiles = list(tiles)
    if traced:
        if not world_tiles:
            world_tiles = [_tile('Trace Host', 0, 0)]
        world_tiles[0]._run_trace = trace
        world_tiles[0]._collective_trace_clock = {
            'turn': 3, 'phase': 'policy_action', 'next': 1}
    world = {'turn': 3, 'tiles': world_tiles, 'policy_feedback': None}
    return world, province, tiles, trace


def _state(fixture):
    world, province, tiles, _trace = fixture
    return (province.gov.agent.cash,
            tuple(tile.gov.agent.cash for tile in tiles),
            tuple(tile.soil_fertility for tile in tiles),
            world.get('policy_feedback'), tuple(world.get('ticker_events', ())))


class WorldviewProvincialPolicyTraceTests(unittest.TestCase):
    def test_desktop_policy_dispatch_uses_traced_provincial_actions(self):
        from client.desktop.panels.policies import _execute_policy_action as desktop_action
        grant = _province_fixture(treasury_cash=300.0)

        desktop_action(grant[0], 'prov_equalization_grant', grant[1])

        self.assertEqual(grant[1].gov.agent.cash, 100.0)
        self.assertTrue(any(row.get('kind') == 'provincial_equalization_grant_receipt'
                            for row in grant[3].rows))

        soil = _province_fixture(treasury_cash=200.0)
        desktop_action(soil[0], 'prov_soil_conservation', soil[1])

        self.assertEqual(soil[1].gov.agent.cash, 50.0)
        self.assertTrue(any(row.get('kind') == 'provincial_policy_expenditure'
                            for row in soil[3].rows))

    def test_equalization_pairs_exact_treasury_debit_and_selected_tile_receipt(self):
        plain = _province_fixture(traced=False)
        traced = _province_fixture(traced=True)

        _execute_policy_action(plain[0], 'prov_equalization_grant', plain[1])
        _execute_policy_action(traced[0], 'prov_equalization_grant', traced[1])

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[1].gov.agent.cash, 100.0)
        self.assertEqual([tile.gov.agent.cash for tile in traced[2]], [205.0, 30.0])
        decision = next(row for row in traced[3].rows
                        if row.get('kind') == 'provincial_policy_funding_decision')
        debit = next(row for row in traced[3].rows
                     if row.get('kind') == 'provincial_equalization_grant_debit')
        receipt = next(row for row in traced[3].rows
                       if row.get('kind') == 'provincial_equalization_grant_receipt')
        outcome = next(row for row in traced[3].rows
                       if row.get('kind') == 'provincial_policy_action_outcome')
        contract = debit['inputs']['transfer_contract']
        self.assertTrue(decision['inputs']['funded'])
        self.assertEqual(decision['inputs']['recipient_selection_rule'],
                         'minimum local bank capital plus municipal treasury cash')
        self.assertEqual(debit['after'], -200.0)
        self.assertEqual(contract['payer_account']['balance_before'], 300.0)
        self.assertEqual(contract['payer_account']['balance_after'], 100.0)
        self.assertEqual(receipt['subject']['id'], 'Poor District')
        self.assertEqual(receipt['inputs']['transfer_contract']['payee_account'][
            'balance_after'], 205.0)
        self.assertEqual(receipt['cause_event_ids'], [debit['event_id']])
        self.assertEqual(outcome['cause_event_ids'], [
            decision['event_id'], debit['event_id'], receipt['event_id']])
        self._assert_catalogued(traced[3].rows)

    def test_unaffordable_equalization_records_shortfall_without_transfer(self):
        fixture = _province_fixture(treasury_cash=50.0)

        _execute_policy_action(fixture[0], 'prov_equalization_grant', fixture[1])

        decision = next(row for row in fixture[3].rows
                        if row.get('kind') == 'provincial_policy_funding_decision')
        self.assertEqual(decision['inputs']['reason'], 'treasury_cash_below_cost')
        self.assertEqual(decision['inputs']['cash_shortfall'], 150.0)
        self.assertEqual(fixture[1].gov.agent.cash, 50.0)
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[3].rows))

    def test_soil_conservation_records_expenditure_and_each_fertility_change(self):
        plain = _province_fixture(treasury_cash=200.0, traced=False)
        traced = _province_fixture(treasury_cash=200.0, traced=True)

        _execute_policy_action(plain[0], 'prov_soil_conservation', plain[1])
        _execute_policy_action(traced[0], 'prov_soil_conservation', traced[1])

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[1].gov.agent.cash, 50.0)
        self.assertAlmostEqual(traced[2][0].soil_fertility, 1.1)
        self.assertEqual(traced[2][1].soil_fertility, 1.5)
        expenditure = next(row for row in traced[3].rows
                           if row.get('kind') == 'provincial_policy_expenditure')
        self.assertEqual(expenditure['after'], -150.0)
        contract = expenditure['inputs']['transfer_contract']
        self.assertEqual(contract['payer_account']['balance_before'], 200.0)
        self.assertEqual(contract['payer_account']['balance_after'], 50.0)
        self.assertEqual(contract['counterparty_leg_status'],
                         'policy_expenditure_no_cash_payee')
        fertility = [row for row in traced[3].rows
                     if row.get('kind') == 'provincial_soil_conservation_outcome']
        self.assertEqual({row['subject']['id'] for row in fertility},
                         {'Poor District', 'Rich District'})
        self.assertTrue(all(row['cause_event_ids'] == [expenditure['event_id']]
                            for row in fertility))
        self._assert_catalogued(traced[3].rows)

    def test_empty_soil_conservation_province_records_existing_spend_without_effect(self):
        fixture = _province_fixture(treasury_cash=200.0, with_tiles=False)

        _execute_policy_action(fixture[0], 'prov_soil_conservation', fixture[1])

        self.assertEqual(fixture[1].gov.agent.cash, 50.0)
        outcome = next(row for row in fixture[3].rows
                       if row.get('kind') == 'provincial_policy_action_outcome')
        self.assertTrue(outcome['inputs']['success'])
        self.assertEqual(outcome['inputs']['reason'],
                         'policy_cost_paid_without_province_tiles')
        self.assertEqual(outcome['inputs']['fertility_changes'], [])
        self.assertEqual(len([row for row in fixture[3].rows
                              if row.get('kind') == 'provincial_policy_expenditure']), 1)
        self.assertFalse(any(row.get('metric_id') == 'ecology.soil_fertility'
                             for row in fixture[3].rows))

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
