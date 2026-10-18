import json
import unittest
from types import SimpleNamespace

from agent import Agent
from nation import Nation
from popular_resistance import PopularResistanceManager
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, treasury_cash=100.0, traced=False, marcher_count=2):
    nation = Nation('Commonwealth', initial_cash=200.0)
    tile = Region('Wessex', 0)
    tile.agents.clear()
    nation.add_tile(tile)
    tile.gov.agent.cash = float(treasury_cash)
    tile.police_officers = 0
    tile.military_units = []

    marchers = []
    for agent_id in range(101, 101 + marcher_count):
        person = Agent(0)
        person.id = agent_id
        person.cash = 10.0
        person.memory = {}
        marchers.append(person)
        tile.agents.append(person)

    manager = PopularResistanceManager()
    state = manager.get_state(tile.name)
    state.enclosure_stage = 'marching'
    state.revolt_participants = {person.id for person in marchers}
    world = {'turn': 3, 'nations': [nation], 'tiles': [tile], 'ticker_events': []}
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {'turn': 3, 'phase': 'policy_action', 'next': 1}
    return nation, tile, marchers, manager, world, trace


def _state(fixture):
    nation, tile, marchers, manager, _world, _trace = fixture
    return (tile.gov.agent.cash, tuple(person.cash for person in marchers),
            tile.police_officers, manager.get_state(tile.name).enclosure_stage,
            tuple(person.alive for person in marchers), nation.legitimacy)


class EmergencyConstableTraceTests(unittest.TestCase):
    def test_funded_mobilization_records_exact_wallets_and_linked_outcome(self):
        baseline = _fixture(treasury_cash=100.0)
        traced = _fixture(treasury_cash=100.0, traced=True)

        plain_result = baseline[3].interdict_enclosure_revolt(
            baseline[1], t=3, world=baseline[4])
        traced_result = traced[3].interdict_enclosure_revolt(
            traced[1], t=3, world=traced[4])

        self.assertEqual(traced_result, plain_result)
        self.assertEqual(_state(traced), _state(baseline))
        self.assertEqual(_state(traced)[:3], (40.0, (70.0, 10.0), 5))

        decision = next(row for row in traced[5].rows
                        if row.get('kind') == 'emergency_constable_funding_decision')
        self.assertEqual(decision['inputs']['reason'], 'emergency_constables_affordable')
        self.assertEqual(decision['inputs']['municipal_treasury_cash_before'], 100.0)
        self.assertEqual(decision['inputs']['required_cash'], 60.0)

        payment = next(row for row in traced[5].rows
                       if row.get('kind') == 'emergency_constable_mobilization_payment')
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(contract['amount'], 60.0)
        self.assertEqual(contract['payer_account']['balance_before'], 100.0)
        self.assertEqual(contract['payer_account']['balance_after'], 40.0)
        self.assertEqual(contract['payee_account']['balance_before'], 10.0)
        self.assertEqual(contract['payee_account']['balance_after'], 70.0)
        self.assertEqual(payment['cause_event_ids'], [decision['event_id']])
        self.assertFalse(payment['inputs']['recipient_is_named_constable'])

        outcome = next(row for row in traced[5].rows
                       if row.get('kind') == 'enclosure_revolt_interdiction_outcome')
        self.assertEqual(outcome['inputs']['outcome'], 'peaceful_dispersal')
        self.assertEqual(outcome['inputs']['casualties'], 0)
        self.assertEqual(outcome['cause_event_ids'],
                         [decision['event_id'], payment['event_id']])

    def test_insufficient_treasury_records_gate_without_debit(self):
        baseline = _fixture(treasury_cash=59.0)
        traced = _fixture(treasury_cash=59.0, traced=True)

        plain_result = baseline[3].interdict_enclosure_revolt(
            baseline[1], t=3, world=baseline[4])
        traced_result = traced[3].interdict_enclosure_revolt(
            traced[1], t=3, world=traced[4])

        self.assertEqual(traced_result, plain_result)
        self.assertFalse(traced_result[0])
        self.assertEqual(_state(traced), _state(baseline))
        self.assertFalse(any(row.get('kind') == 'emergency_constable_mobilization_payment'
                             for row in traced[5].rows))

        decision = next(row for row in traced[5].rows
                        if row.get('kind') == 'emergency_constable_funding_decision')
        self.assertEqual(decision['inputs']['reason'], 'insufficient_municipal_treasury')
        self.assertEqual(decision['inputs']['cash_shortfall'], 1.0)
        outcome = next(row for row in traced[5].rows
                       if row.get('kind') == 'enclosure_revolt_interdiction_outcome')
        self.assertEqual(outcome['inputs']['outcome'], 'insufficient_municipal_treasury')
        self.assertIn(decision['event_id'], outcome['cause_event_ids'])

    def test_existing_force_is_used_without_emergency_fee(self):
        fixture = _fixture(treasury_cash=100.0, traced=True)
        fixture[1].police_officers = 5

        fixture[3].interdict_enclosure_revolt(fixture[1], t=3, world=fixture[4])

        self.assertEqual(fixture[1].gov.agent.cash, 100.0)
        self.assertFalse(any('emergency_constable' in row.get('kind', '')
                             for row in fixture[5].rows))
        capacity = next(row for row in fixture[5].rows
                        if row.get('kind') == 'enclosure_interdiction_capacity_decision')
        self.assertEqual(capacity['inputs']['reason'], 'standing_police_available')

    def test_garrison_terror_trace_names_casualties_and_legitimacy_effect(self):
        fixture = _fixture(treasury_cash=100.0, traced=True, marcher_count=10)
        fixture[1].military_units = [SimpleNamespace(soldiers=5)]
        legitimacy_before = fixture[0].legitimacy

        result = fixture[3].interdict_enclosure_revolt(
            fixture[1], t=3, world=fixture[4])

        self.assertEqual(result[2]['outcome'], 'terror')
        outcome = next(row for row in fixture[5].rows
                       if row.get('kind') == 'enclosure_revolt_interdiction_outcome')
        self.assertEqual(outcome['inputs']['outcome'], 'state_terror')
        self.assertEqual(outcome['inputs']['casualties'], 5)
        self.assertEqual(len(outcome['inputs']['casualty_agent_ids']), 5)
        self.assertEqual(outcome['inputs']['legitimacy_before'], legitimacy_before)
        self.assertAlmostEqual(outcome['inputs']['legitimacy_after'],
                               legitimacy_before - 0.2)
        self.assertEqual(outcome['inputs']['terror_cooldown_after'], 10)
        self.assertFalse(any('emergency_constable' in row.get('kind', '')
                             for row in fixture[5].rows))


if __name__ == '__main__':
    unittest.main()
