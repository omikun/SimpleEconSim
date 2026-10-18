"""Causal trace for state-funded assassination plots and their outcomes."""

import json
import random
import unittest
from types import SimpleNamespace

from agent import Agent
from agents.resistance.manager import PopularResistanceManager
from agents.resistance.models import AssassinationPlot
from land_tenure import LandPlot, TenureStatus, TileTenure
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'assassination-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced, treasury=100.0, constable=True, charity=True):
    tile = Region('Parish', t=0, number_of_agents=0)
    tile.home_currency = 'GBP'
    tile.bank = None
    tile.agents.clear()
    tile.gov.agent.cash = float(treasury)
    tile.gov.agent.home_currency = 'GBP'

    leader = Agent(0)
    leader.id = 101
    leader.alive = True
    leader.cash = 50.0
    leader.charisma = 0.8
    leader.ambition = 0.8
    leader.social_class = 'proletarian'
    tile.agents.append(leader)

    officer = None
    if constable:
        officer = Agent(0)
        officer.id = 102
        officer.alive = True
        officer.cash = 5.0
        officer.is_police = True
        officer.social_class = 'constable'
        officer.home_currency = 'GBP'
        tile.agents.append(officer)

    charity_agent = Agent(0)
    charity_agent.id = 103
    charity_agent.cash = 0.0
    tile.charity = (SimpleNamespace(agent=charity_agent) if charity else None)

    manager = PopularResistanceManager()
    state = manager.get_state(tile.name)
    state.leader_id = leader.id
    state.leader_name = 'Parish Agitator'
    state.followers = [leader.id]

    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 10, 'phase': 'policy_action', 'next': 1}
    return tile, manager, state, leader, officer, charity_agent, trace


def _state(fixture):
    tile, _manager, state, leader, officer, charity_agent, _trace = fixture
    return {
        'treasury_cash': tile.gov.agent.cash,
        'officer_cash': officer.cash if officer else None,
        'charity_cash': charity_agent.cash if tile.charity else None,
        'leader_alive': leader.alive,
        'leader_cash': leader.cash,
        'leader_charisma': leader.charisma,
        'leader_id': state.leader_id,
        'followers': tuple(state.followers),
        'plot_status': getattr(state.active_plot, 'status', None),
        'deaths_this_turn': tile.deaths_this_turn,
        'death_causes': dict(tile.deaths_by_cause_this_turn),
    }


class AssassinationTraceTests(unittest.TestCase):
    def test_commission_payment_and_decapitation_link_to_registered_death(self):
        baseline = _fixture(traced=False)
        traced = _fixture(traced=True)

        for fixture in (baseline, traced):
            ok, _message, _data = fixture[1].initiate_assassination_plot(
                fixture[0], 10, operative_funds=75.0, turns_delay=2)
            self.assertTrue(ok)
            result = fixture[1].resolve_assassination_strike(fixture[0], 12)
            self.assertTrue(result[0])
            self.assertEqual(result[2]['outcome'], 'decapitation')

        self.assertEqual(_state(traced), _state(baseline))
        self.assertEqual(_state(traced)['treasury_cash'], 25.0)
        self.assertEqual(_state(traced)['officer_cash'], 80.0)
        self.assertEqual(_state(traced)['charity_cash'], 50.0)

        rows = traced[6].rows
        decision = next(row for row in rows
                        if row.get('kind') == 'assassination_plot_funding_decision')
        self.assertEqual(decision['inputs']['reason_code'], 'funding_available')
        self.assertTrue(decision['after'])

        payment = next(row for row in rows
                       if row.get('kind') == 'assassination_contract_funding')
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(payment['metric_id'], 'finance.cash_transfer')
        self.assertEqual(contract['operation_type'],
                         'assassination_contract_funding')
        self.assertEqual(contract['amount'], 75.0)
        self.assertEqual(contract['payer_account']['balance_before'], 100.0)
        self.assertEqual(contract['payer_account']['balance_after'], 25.0)
        self.assertEqual(contract['payee_account']['type'], 'constable_wallet')
        self.assertEqual(contract['payee_account']['balance_before'], 5.0)
        self.assertEqual(contract['payee_account']['balance_after'], 80.0)
        self.assertEqual(payment['cause_event_ids'], [decision['event_id']])
        journal = next(event for event in traced[0].economic_events
                       if event['source_id'] == contract['operation_id'])
        self.assertEqual(payment['inputs']['actor_account_event_id'], journal['id'])

        commissioned = next(row for row in rows
                            if row.get('kind') == 'assassination_plot_commissioned')
        self.assertEqual(commissioned['inputs']['operation_id'],
                         contract['operation_id'])
        self.assertEqual(commissioned['cause_event_ids'],
                         [decision['event_id'], payment['event_id']])

        death = next(row for row in rows if row.get('kind') == 'person_died')
        self.assertEqual(death['inputs']['assassination_operation_id'],
                         contract['operation_id'])
        outcome = next(row for row in rows
                       if row.get('metric_id') == 'politics.assassination_outcome')
        self.assertEqual(outcome['inputs']['outcome'], 'decapitation')
        self.assertEqual(outcome['inputs']['death_recorded'], True)
        self.assertEqual(outcome['cause_event_ids'], [death['event_id']])

    def test_insufficient_cash_gate_records_no_payment(self):
        baseline = _fixture(traced=False, treasury=40.0)
        traced = _fixture(traced=True, treasury=40.0)

        plain = baseline[1].initiate_assassination_plot(
            baseline[0], 10, operative_funds=75.0, turns_delay=2)
        observed = traced[1].initiate_assassination_plot(
            traced[0], 10, operative_funds=75.0, turns_delay=2)

        self.assertEqual(observed, plain)
        self.assertFalse(observed[0])
        self.assertEqual(_state(traced), _state(baseline))
        decision = next(row for row in traced[6].rows
                        if row.get('kind') == 'assassination_plot_funding_decision')
        self.assertEqual(decision['inputs']['reason_code'],
                         'insufficient_municipal_treasury')
        self.assertFalse(decision['after'])
        self.assertFalse(any(row.get('metric_id') == 'finance.cash_transfer'
                             for row in traced[6].rows))

    def test_martyrdom_outcome_records_follower_surge_and_death_link(self):
        fixtures = [_fixture(traced=False), _fixture(traced=True)]
        results = []
        for fixture in fixtures:
            tile, manager, state, leader, _officer, _charity, _trace = fixture
            sympathizer_ids = []
            for agent_id in range(201, 206):
                sympathizer = Agent(0)
                sympathizer.id = agent_id
                sympathizer.alive = True
                sympathizer.social_class = 'proletarian'
                tile.agents.append(sympathizer)
                sympathizer_ids.append(agent_id)
            state.followers = [leader.id, *sympathizer_ids]
            state.active_plot = AssassinationPlot(
                target_leader_id=leader.id,
                target_leader_name=state.leader_name,
                tile_name=tile.name, turns_remaining=0, total_turns=2,
                funding_allocated=75.0,
                operation_id='assassination-plot:Parish:8:101:1')
            results.append(manager.resolve_assassination_strike(tile, 12))

        self.assertEqual(results[1], results[0])
        self.assertEqual(results[1][2]['outcome'], 'martyrdom')
        self.assertEqual(_state(fixtures[1]), _state(fixtures[0]))
        rows = fixtures[1][6].rows
        death = next(row for row in rows if row.get('kind') == 'person_died')
        outcome = next(row for row in rows
                       if row.get('metric_id') == 'politics.assassination_outcome')
        self.assertEqual(outcome['inputs']['outcome'], 'martyrdom')
        self.assertEqual(outcome['inputs']['followers_before'], 5)
        self.assertEqual(outcome['inputs']['followers_after'],
                         results[1][2]['followers_now'])
        self.assertEqual(outcome['cause_event_ids'], [death['event_id']])

    def test_missing_recipient_is_reported_as_uncredited_expenditure(self):
        fixture = _fixture(traced=True, constable=False, charity=False)

        ok, _message, _data = fixture[1].initiate_assassination_plot(
            fixture[0], 10, operative_funds=75.0, turns_delay=2)

        self.assertTrue(ok)
        self.assertEqual(fixture[0].gov.agent.cash, 25.0)
        self.assertFalse(any(row.get('metric_id') == 'finance.cash_transfer'
                             for row in fixture[6].rows))
        expense = next(row for row in fixture[6].rows
                       if row.get('kind') == 'assassination_contract_uncredited_expenditure')
        contract = expense['inputs']['transfer_contract']
        self.assertEqual(expense['metric_id'], 'finance.policy_expenditure')
        self.assertEqual(expense['after'], -75.0)
        self.assertEqual(contract['payer_account']['balance_before'], 100.0)
        self.assertEqual(contract['payer_account']['balance_after'], 25.0)
        self.assertEqual(contract['counterparty_leg_status'],
                         'policy_expenditure_no_cash_payee')
        commissioned = next(row for row in fixture[6].rows
                            if row.get('kind') == 'assassination_plot_commissioned')
        self.assertEqual(commissioned['inputs']['recipient_cash_credited'], False)
        self.assertIn(expense['event_id'], commissioned['cause_event_ids'])

    def test_detection_draw_and_blown_outcome_are_causal_and_trace_neutral(self):
        fixtures = [_fixture(traced=False), _fixture(traced=True)]
        for fixture in fixtures:
            tile, _manager, state, leader, _officer, _charity, _trace = fixture
            plot = LandPlot('enclosed', tile.name, leader.id, 1.0,
                            TenureStatus.ENCLOSED, rent_rate=3.0)
            tile.tenure = TileTenure(plots=[plot])
            state.enclosure_stage = 'protest'
            state.active_plot = AssassinationPlot(
                target_leader_id=leader.id,
                target_leader_name=state.leader_name,
                tile_name=tile.name, turns_remaining=2, total_turns=2,
                funding_allocated=75.0, detection_risk_per_turn=0.1,
                operation_id='assassination-plot:Parish:8:101')

        random.seed(31)
        result_plain = fixtures[0][1].step_rebellion_fermentation(
            fixtures[0][0], 9)
        plain_random_state = random.getstate()
        random.seed(31)
        result_traced = fixtures[1][1].step_rebellion_fermentation(
            fixtures[1][0], 9)
        traced_random_state = random.getstate()

        self.assertEqual(result_traced, result_plain)
        self.assertEqual(traced_random_state, plain_random_state)
        self.assertEqual(_state(fixtures[1]), _state(fixtures[0]))
        self.assertAlmostEqual(fixtures[1][3].charisma, 0.95)
        rows = fixtures[1][6].rows
        decision = next(row for row in rows
                        if row.get('kind') == 'assassination_detection_check')
        self.assertAlmostEqual(decision['inputs']['detection_draw'],
                               0.01227824739797545)
        self.assertEqual(decision['inputs']['reason_code'],
                         'plot_detected_before_strike')
        outcome = next(row for row in rows
                       if row.get('metric_id') == 'politics.assassination_outcome')
        self.assertEqual(outcome['inputs']['outcome'], 'plot_blown')
        self.assertEqual(outcome['cause_event_ids'], [decision['event_id']])


if __name__ == '__main__':
    unittest.main()
