import json
import unittest
from types import SimpleNamespace

from agent import Agent
from goods import Goods
from metric_catalog import METRICS, TRACE_INSTRUMENTED
from client.desktop.panels.policies import _execute_policy_action as desktop_action
from worldview_policies import _execute_policy_action as web_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, homesteader_count=2, traced=True):
    agents = []
    for index in range(homesteader_count):
        pioneer = Agent(index + 1)
        pioneer.is_homesteader = True
        pioneer.inv_add(Goods.food, index)
        agents.append(pioneer)
    non_homesteader = Agent(99)
    non_homesteader.is_homesteader = False
    agents.append(non_homesteader)
    frontier = SimpleNamespace(name='Prairie', agents=agents)
    trace = MemoryTrace()
    if traced:
        frontier._run_trace = trace
        frontier._collective_trace_clock = {
            'turn': 4, 'phase': 'policy_action', 'next': 1}
    world = {'turn': 4, 'tiles': [], 'policy_feedback': None}
    return world, frontier, agents, trace


def _state(fixture):
    world, frontier, agents, _trace = fixture
    return (tuple(agent.inv_get(Goods.food, 0) for agent in agents),
            world.get('policy_feedback'))


class FrontierPioneerGrantTraceTests(unittest.TestCase):
    def test_web_and_desktop_paths_trace_created_food_without_cash_debit(self):
        for action in (web_action, desktop_action):
            with self.subTest(handler=action.__module__):
                plain = _fixture(traced=False)
                traced = _fixture(traced=True)

                action(plain[0], 'frontier_pioneer_grant', plain[1])
                action(traced[0], 'frontier_pioneer_grant', traced[1])

                self.assertEqual(_state(plain), _state(traced))
                self.assertEqual([agent.inv_get(Goods.food, 0)
                                  for agent in traced[2]], [2, 3, 0])
                decision = next(row for row in traced[3].rows
                                if row.get('kind') == 'frontier_pioneer_aid_decision')
                outcome = next(row for row in traced[3].rows
                               if row.get('kind') == 'frontier_pioneer_aid_outcome')
                recipients = [row for row in traced[3].rows
                              if row.get('kind') ==
                              'frontier_pioneer_food_recipient_outcome']
                self.assertEqual(decision['inputs']['recipient_count'], 2)
                self.assertEqual(decision['inputs']['displayed_policy_cost'], 40.0)
                self.assertEqual(decision['inputs']['cash_debited'], 0.0)
                self.assertFalse(decision['inputs']['stock_debit_recorded'])
                self.assertEqual(len(recipients), 2)
                self.assertEqual([row['after'] - row['before'] for row in recipients],
                                 [2.0, 2.0])
                self.assertEqual(outcome['inputs']['food_units_created'], 4.0)
                self.assertEqual(outcome['inputs']['recipient_ids'],
                                 [str(traced[2][0].id), str(traced[2][1].id)])
                self._assert_catalogued(traced[3].rows)

    def test_empty_frontier_logs_no_eligible_recipient_outcome(self):
        fixture = _fixture(homesteader_count=0)

        web_action(fixture[0], 'frontier_pioneer_grant', fixture[1])

        decision = next(row for row in fixture[3].rows
                        if row.get('kind') == 'frontier_pioneer_aid_decision')
        outcome = next(row for row in fixture[3].rows
                       if row.get('kind') == 'frontier_pioneer_aid_outcome')
        self.assertEqual(decision['inputs']['reason'], 'no_eligible_homesteaders')
        self.assertEqual(outcome['inputs']['recipient_count'], 0)
        self.assertEqual(outcome['inputs']['food_units_created'], 0.0)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
