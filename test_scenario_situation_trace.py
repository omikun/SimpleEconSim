import json
import unittest

from nation import Nation
from region import Region
from scenario_situation import apply_effects


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=False, treasury_cash=50.0, creditor_names=('Britain', 'France')):
    nations = [Nation('Egypt', initial_cash=treasury_cash)]
    nations.extend(Nation(name, initial_cash=10.0 + i * 10.0)
                   for i, name in enumerate(creditor_names))
    tiles = []
    for nation in nations:
        tile = Region(f'{nation.name} Seat', 0, number_of_agents=0,
                      number_of_traders=0)
        nation.add_tile(tile)
        tiles.append(tile)
    trace = MemoryTrace()
    if traced:
        clock = {'turn': 4, 'phase': 'creditor_reaction', 'next': 1}
        for tile in tiles:
            tile._run_trace = trace
            tile._collective_trace_clock = clock
    world = {
        'turn': 4,
        'player_nation_name': 'Egypt',
        'nations': nations,
        'tiles': tiles,
        'scenario': {'horizon_turns': 20},
        'scenario_state': {
            'creditor_confidence': 0.60,
            'fiscal_autonomy': 0.40,
            'scheduled_remittance': 80.0,
            'payment_status': 'current',
            'deferral_count': 0,
            'politics': {'palace_authority': 0.50},
        },
    }
    return world, trace


def _money(world):
    return tuple((nation.name, float(nation.government.agent.cash))
                 for nation in world['nations'])


def _state(world):
    egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
    return (_money(world), world['scenario_state']['creditor_confidence'],
            world['scenario_state']['fiscal_autonomy'], egypt.legitimacy,
            world['scenario_state']['politics']['palace_authority'],
            tuple(tile.food_export_fraction for tile in egypt.tiles))


class ScenarioSituationTraceTests(unittest.TestCase):
    def test_cost_records_payer_split_receipts_effects_and_trace_parity(self):
        plain, _ = _fixture(treasury_cash=50.0)
        traced, trace = _fixture(treasury_cash=50.0, traced=True)
        effects = {
            'treasury_cost': 20.0,
            'confidence_delta': 0.1,
            'autonomy_delta': -0.1,
            'legitimacy_delta': 0.05,
            'palace_authority_delta': 0.1,
            'export_fraction': 0.5,
        }

        self.assertEqual(apply_effects(plain, effects, source='response:test'),
                         apply_effects(traced, effects, source='response:test'))
        self.assertEqual(_state(traced), _state(plain))
        self.assertEqual(_money(traced), (('Egypt', 30.0), ('Britain', 20.0),
                                           ('France', 30.0)))
        state = traced['scenario_state']
        self.assertAlmostEqual(state['creditor_confidence'], 0.7)
        self.assertAlmostEqual(state['fiscal_autonomy'], 0.3)
        self.assertAlmostEqual(traced['nations'][0].legitimacy, 0.65)
        self.assertAlmostEqual(state['politics']['palace_authority'], 0.6)
        self.assertEqual(traced['nations'][0].tiles[0].food_export_fraction, 0.5)

        decision = next(row for row in trace.rows
                        if row.get('kind') == 'creditor_effect_funding_decision')
        self.assertTrue(decision['inputs']['affordable'])
        payer = next(row for row in trace.rows
                     if row.get('kind') == 'creditor_situation_treasury_cost')
        self.assertEqual(payer['after'], -20.0)
        self.assertEqual(payer['inputs']['treasury_cash_before'], 50.0)
        self.assertEqual(payer['inputs']['treasury_cash_after'], 30.0)
        self.assertEqual(payer['inputs']['recipient_amounts'], [10.0, 10.0])
        receipts = [row for row in trace.rows
                    if row.get('kind') == 'creditor_situation_payment_receipt']
        self.assertEqual({row['subject']['id'] for row in receipts}, {'Britain', 'France'})
        for receipt in receipts:
            self.assertEqual(receipt['after'], 10.0)
            self.assertEqual(receipt['cause_event_ids'], [payer['event_id']])
            self.assertTrue(receipt['inputs']['transfer_contract'][
                'unconverted_currency_mismatch'])
        self.assertTrue(all(row['inputs']['transfer_contract']['operation_id']
                            == payer['inputs']['transfer_contract']['operation_id']
                            for row in receipts))
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'creditor_effect_application')
        self.assertEqual(outcome['inputs']['reason'], 'effects_applied')
        self.assertEqual(outcome['inputs']['state_before']['legitimacy'], 0.6)
        self.assertEqual(outcome['inputs']['state_after']['legitimacy'], 0.65)
        self.assertIn(payer['event_id'], outcome['cause_event_ids'])

    def test_insufficient_cash_records_rejection_without_partial_payment(self):
        world, trace = _fixture(traced=True, treasury_cash=19.0)
        before = _money(world)

        result = apply_effects(world, {'treasury_cost': 20.0,
                                       'confidence_delta': 0.2},
                               source='response:unaffordable')

        self.assertFalse(result[0])
        self.assertEqual(_money(world), before)
        self.assertEqual(world['scenario_state']['creditor_confidence'], 0.60)
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in trace.rows))
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'creditor_effect_funding_decision')
        self.assertEqual(decision['inputs']['reason'],
                         'treasury_cash_below_response_cost')
        self.assertEqual(decision['inputs']['cash_shortfall'], 1.0)
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'creditor_effect_application')
        self.assertEqual(outcome['inputs']['reason'], 'insufficient_treasury_cash')
        self.assertEqual(outcome['cause_event_ids'], [decision['event_id']])

    def test_missing_creditors_discloses_unmatched_treasury_debit(self):
        world, trace = _fixture(traced=True, treasury_cash=50.0,
                                creditor_names=())

        self.assertEqual(apply_effects(world, {'treasury_cost': 20.0},
                                       source='response:no-creditor'), (True, ''))

        self.assertEqual(_money(world), (('Egypt', 30.0),))
        debit = next(row for row in trace.rows
                     if row.get('kind') == 'creditor_situation_cost_without_recipient')
        contract = debit['inputs']['transfer_contract']
        self.assertEqual(debit['after'], -20.0)
        self.assertEqual(contract['counterparty_leg_status'],
                         'treasury_debit_only_no_eligible_creditor')
        self.assertEqual(contract['payee_account']['balance_status'],
                         'treasury_cash_debited_without_creditor_receipt')
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'creditor_effect_application')
        self.assertIn(debit['event_id'], outcome['cause_event_ids'])


if __name__ == '__main__':
    unittest.main()
