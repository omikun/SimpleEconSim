import json
import unittest
from types import SimpleNamespace

from labor_politics import subsidize_mass_entertainment
from metric_catalog import METRICS, TRACE_INSTRUMENTED


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _tile(name, entertainment, unrest):
    return SimpleNamespace(name=name,
                           entertainment_level=float(entertainment),
                           unrest_level=float(unrest), gov=None)


def _fixture(*, treasury_cash=200.0, traced=True):
    tiles = [_tile('North', 0.1, 0.5), _tile('South', 0.9, 0.1)]
    treasury = SimpleNamespace(id='national-gov', cash=float(treasury_cash))
    tiles[0].gov = SimpleNamespace(agent=treasury)
    nation = SimpleNamespace(name='Agraria', currency='AGR', tiles=tiles,
                             government=SimpleNamespace(agent=treasury))
    trace = MemoryTrace()
    if traced:
        tiles[0]._run_trace = trace
        tiles[0]._collective_trace_clock = {
            'turn': 9, 'phase': 'policy_action', 'next': 1}
    return nation, tiles, trace


def _state(fixture):
    nation, tiles, _trace = fixture
    return (nation.government.agent.cash,
            tuple((tile.entertainment_level, tile.unrest_level) for tile in tiles))


class MassEntertainmentTraceTests(unittest.TestCase):
    def test_funded_subsidy_traces_treasury_expense_and_capped_tile_effects(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        result_plain = subsidize_mass_entertainment(plain[0], cost=50.0)
        result_traced = subsidize_mass_entertainment(traced[0], cost=50.0)

        self.assertEqual(result_plain, result_traced)
        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[0].government.agent.cash, 150.0)
        for tile, expected in zip(traced[1], [0.3, 1.0]):
            self.assertAlmostEqual(tile.entertainment_level, expected)
        for tile, expected in zip(traced[1], [0.35, 0.0]):
            self.assertAlmostEqual(tile.unrest_level, expected)
        funding = self._row(traced, 'mass_entertainment_funding_decision')
        expense = self._row(traced, 'mass_entertainment_policy_expenditure')
        effects = [row for row in traced[2].rows
                   if row.get('kind') == 'mass_entertainment_tile_effect']
        unrest = [row for row in traced[2].rows
                  if row.get('kind') == 'mass_entertainment_unrest_effect']
        outcome = self._row(traced, 'mass_entertainment_subsidy_outcome')
        self.assertTrue(funding['inputs']['funded'])
        self.assertEqual(expense['after'], -50.0)
        contract = expense['inputs']['transfer_contract']
        self.assertEqual(contract['payer_account']['balance_before'], 200.0)
        self.assertEqual(contract['payer_account']['balance_after'], 150.0)
        self.assertEqual(contract['counterparty_leg_status'],
                         'policy_expenditure_no_cash_payee')
        self.assertEqual({row['subject']['id'] for row in effects},
                         {'North', 'South'})
        self.assertEqual({row['subject']['id'] for row in unrest},
                         {'North', 'South'})
        self.assertAlmostEqual(outcome['inputs']['entertainment_increases'], 0.3)
        self.assertEqual(outcome['inputs']['unrest_change_total'], -0.25)
        self.assertIsNone(outcome['inputs']['cash_recipient'])
        self._assert_catalogued(traced[2].rows)

    def test_insufficient_treasury_records_gate_without_effects(self):
        fixture = _fixture(treasury_cash=20)
        before = _state(fixture)

        ok, _message = subsidize_mass_entertainment(fixture[0], cost=50.0)

        self.assertFalse(ok)
        self.assertEqual(_state(fixture), before)
        funding = self._row(fixture, 'mass_entertainment_funding_decision')
        self.assertFalse(funding['inputs']['funded'])
        self.assertEqual(funding['inputs']['cash_shortfall'], 30.0)
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[2].rows))

    def _row(self, fixture, kind):
        return next(row for row in fixture[2].rows if row.get('kind') == kind)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
