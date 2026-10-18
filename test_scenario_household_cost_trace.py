import json
import unittest
from types import SimpleNamespace

from scenario_oversight import action as oversight_action
from scenario_gunboat import _transfer_to_households


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, treasury_cash=80.0, recipient_cash=12.0, recipient_present=True,
             recipient_currency='EGP', traced=True):
    agent = SimpleNamespace(id=41, cash=float(recipient_cash), alive=True,
                            is_government=False, is_corporation=False,
                            home_currency=recipient_currency)
    tile = SimpleNamespace(name='Alexandria', home_currency='EGP', agents=[])
    if recipient_present:
        tile.agents.append(agent)
    government_agent = SimpleNamespace(id=900, cash=float(treasury_cash))
    nation = SimpleNamespace(
        name='Egypt', currency='EGP',
        government=SimpleNamespace(agent=government_agent), tiles=[tile])
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 4, 'phase': 'naval_crisis', 'next': 1}
    world = {'turn': 4, 'nations': [nation], 'tiles': [tile]}
    return world, nation, tile, agent, government_agent, trace


def _state(fixture):
    _world, nation, tile, recipient, treasury, _trace = fixture
    return (float(treasury.cash), float(recipient.cash),
            tuple(str(agent.id) for agent in tile.agents), nation.name)


class ScenarioHouseholdCostTraceTests(unittest.TestCase):
    def test_paid_cost_records_exact_wallet_legs_and_trace_parity(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)
        plain_ids, traced_ids = [], []

        self.assertTrue(_transfer_to_households(
            plain[0], plain[1], 35.0, source='test_squadron',
            trace_event_ids=plain_ids))
        self.assertTrue(_transfer_to_households(
            traced[0], traced[1], 35.0, source='test_squadron',
            trace_event_ids=traced_ids))

        self.assertEqual(_state(traced), _state(plain))
        self.assertEqual((traced[4].cash, traced[3].cash), (45.0, 47.0))
        decision = next(row for row in traced[5].rows
                        if row.get('kind') == 'scenario_household_cost_funding_decision')
        payment = next(row for row in traced[5].rows
                       if row.get('kind') == 'scenario_household_cost_payment')
        outcome = next(row for row in traced[5].rows
                       if row.get('kind') == 'scenario_household_cost_outcome')
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(contract['amount'], 35.0)
        self.assertEqual(contract['payer_account']['balance_before'], 80.0)
        self.assertEqual(contract['payer_account']['balance_after'], 45.0)
        self.assertEqual(contract['payee_account']['balance_before'], 12.0)
        self.assertEqual(contract['payee_account']['balance_after'], 47.0)
        self.assertEqual(payment['cause_event_ids'], [decision['event_id']])
        self.assertEqual(outcome['cause_event_ids'],
                         [decision['event_id'], payment['event_id']])
        self.assertEqual(traced_ids, [decision['event_id'], payment['event_id'],
                                      outcome['event_id']])
        self.assertEqual(payment['inputs']['source'], 'test_squadron')

    def test_foreign_household_payment_flags_unconverted_currency_mismatch(self):
        fixture = _fixture(recipient_currency='FRF')
        self.assertTrue(_transfer_to_households(
            fixture[0], fixture[1], 35.0, source='test_foreign_recipient'))
        payment = next(row for row in fixture[5].rows
                       if row.get('kind') == 'scenario_household_cost_payment')
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(contract['payer_account']['currency'], 'EGP')
        self.assertEqual(contract['payee_account']['currency'], 'FRF')
        self.assertTrue(contract['counterparty_currency_mismatch'])
        self.assertTrue(contract['unconverted_currency_mismatch'])
        self.assertFalse(contract['currency_conversion_applied'])

    def test_insufficient_cash_and_missing_recipient_record_failure_without_transfer(self):
        poor = _fixture(treasury_cash=34.0)
        self.assertFalse(_transfer_to_households(
            poor[0], poor[1], 35.0, source='test_upkeep'))
        self.assertEqual((poor[4].cash, poor[3].cash), (34.0, 12.0))
        decision = next(row for row in poor[5].rows
                        if row.get('kind') == 'scenario_household_cost_funding_decision')
        outcome = next(row for row in poor[5].rows
                       if row.get('kind') == 'scenario_household_cost_outcome')
        self.assertEqual(decision['inputs']['reason'], 'treasury_cash_below_cost')
        self.assertEqual(decision['inputs']['cash_shortfall'], 1.0)
        self.assertEqual(outcome['inputs']['reason'], 'treasury_cash_below_cost')
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in poor[5].rows))

        no_recipient = _fixture(treasury_cash=80.0, recipient_present=False)
        event_ids = []
        self.assertFalse(_transfer_to_households(
            no_recipient[0], no_recipient[1], 35.0,
            source='test_unstaffed', trace_event_ids=event_ids))
        self.assertEqual(no_recipient[4].cash, 80.0)
        decision = next(row for row in no_recipient[5].rows
                        if row.get('kind') == 'scenario_household_cost_funding_decision')
        self.assertEqual(decision['inputs']['reason'],
                         'no_eligible_household_recipient')
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in no_recipient[5].rows))

    def test_narrower_oversight_offer_pairs_creditor_receipts(self):
        fixture = _fixture(treasury_cash=80.0)
        world, egypt, tile, _resident, _treasury, trace = fixture
        britain = SimpleNamespace(
            name='Britain', currency='GBP',
            government=SimpleNamespace(agent=SimpleNamespace(id=901, cash=25.0)))
        france = SimpleNamespace(
            name='France', currency='FRF',
            government=SimpleNamespace(agent=SimpleNamespace(id=902, cash=35.0)))
        world['nations'].extend([britain, france])
        world['scenario'] = {'horizon_turns': 20}
        world['scenario_state'] = {
            'creditor_confidence': 0.6,
            'debt_ledger': [],
            'oversight_agreement': {
                'status': 'active', 'scope': ['tax', 'tariff'],
                'proposal': None, 'conditional_write_down': 10.0,
            },
        }

        result = oversight_action(world, 'seek_narrower_oversight')

        self.assertTrue(result[0], result[1])
        self.assertEqual(egypt.government.agent.cash, 60.0)
        self.assertEqual(britain.government.agent.cash, 35.0)
        self.assertEqual(france.government.agent.cash, 45.0)
        payer = next(row for row in trace.rows
                     if row.get('kind') == 'creditor_situation_treasury_cost')
        receipts = [row for row in trace.rows
                    if row.get('kind') == 'creditor_situation_payment_receipt']
        self.assertEqual({row['subject']['id'] for row in receipts}, {'Britain', 'France'})
        self.assertEqual(payer['after'], -20.0)
        self.assertTrue(all(row['cause_event_ids'] == [payer['event_id']]
                            for row in receipts))
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'oversight_negotiation_payment_outcome')
        self.assertEqual(outcome['inputs']['reason'], 'narrower_terms_proposed')
        self.assertIn(payer['event_id'], outcome['cause_event_ids'])
        self.assertEqual(world['scenario_state']['oversight_agreement']['proposal'],
                         {'due_turn': 5, 'scope': ['tax']})

    def test_unaffordable_oversight_offer_records_gate_without_cash_change(self):
        fixture = _fixture(treasury_cash=19.0)
        world, egypt, _tile, _resident, treasury, trace = fixture
        world['nations'].extend([
            SimpleNamespace(name='Britain', government=SimpleNamespace(
                agent=SimpleNamespace(id=901, cash=25.0))),
            SimpleNamespace(name='France', government=SimpleNamespace(
                agent=SimpleNamespace(id=902, cash=35.0))),
        ])
        world['scenario'] = {'horizon_turns': 20}
        world['scenario_state'] = {
            'debt_ledger': [],
            'oversight_agreement': {
                'status': 'active', 'scope': ['tax', 'tariff'],
                'proposal': None, 'conditional_write_down': 10.0,
            },
        }

        result = oversight_action(world, 'seek_narrower_oversight')

        self.assertFalse(result[0])
        self.assertEqual(egypt.government.agent.cash, 19.0)
        self.assertEqual(treasury.cash, 19.0)
        self.assertEqual(world['scenario_state']['debt_ledger'], [])
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'oversight_negotiation_funding_decision')
        self.assertEqual(decision['inputs']['reason'],
                         'treasury_cash_below_response_cost')
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in trace.rows))


if __name__ == '__main__':
    unittest.main()
