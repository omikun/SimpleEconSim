"""Accounting tests for funded frontier policy actions."""

import unittest
from types import SimpleNamespace

from agent import Agent
from client.desktop.panels.policies import _execute_policy_action as desktop_policy_action
from economy.actor_accounts import recorded_cash_delta
from goods import Goods
from worldview_policies import _execute_policy_action as web_policy_action


class Recorder:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        self.rows.append({'turn': clock['turn'], **row})


def expedition_fixture(treasury_cash=100.0):
    treasury = Agent(0)
    treasury.cash = treasury_cash
    capital = SimpleNamespace(
        name='Capital', agents=[treasury], home_currency='USD',
        economic_events=[])
    nation = SimpleNamespace(
        name='Sponsor', currency='USD',
        government=SimpleNamespace(agent=treasury), tiles=[capital])
    frontier = SimpleNamespace(
        name='Frontier', agents=[], is_ocean=False, elevation=0.1,
        home_currency=None,
        _collective_trace_clock={'turn': 4, 'next': 1, 'phase': 'policy'},
        _run_trace=Recorder())
    return {'nations': [nation], 'turn': 4}, nation, capital, frontier


class FrontierPolicyTests(unittest.TestCase):
    def test_web_and_desktop_expedition_fund_and_record_each_wallet_grant(self):
        for action in (web_policy_action, desktop_policy_action):
            with self.subTest(handler=action.__module__):
                world, nation, capital, frontier = expedition_fixture()
                action(world, 'frontier_expedition', frontier)

                pioneers = frontier.agents
                self.assertEqual(len(pioneers), 5)
                self.assertEqual(len({pioneer.id for pioneer in pioneers}), 5)
                self.assertTrue(all(pioneer.is_homesteader for pioneer in pioneers))
                self.assertTrue(all(pioneer.output == Goods.food for pioneer in pioneers))
                self.assertTrue(all(pioneer.wallets == {'USD': 20.0}
                                    for pioneer in pioneers))
                self.assertEqual(nation.government.agent.cash, 0.0)
                self.assertEqual(
                    nation.government.agent.cash
                    + sum(pioneer.wallets.get('USD', 0.0) for pioneer in pioneers),
                    100.0)

                spending = [event for event in capital.economic_events
                            if event['kind'] == 'frontier_expedition_spending']
                grants = [event for event in frontier.economic_events
                          if event['kind'] == 'foreign_wallet_grant']
                self.assertEqual(len(spending), 5)
                self.assertEqual(len(grants), 5)
                self.assertTrue(all(event['payer_id'] == nation.government.agent.id
                                    and event['amount'] == 20.0
                                    and event['currency'] == 'USD'
                                    for event in spending))
                self.assertEqual(
                    recorded_cash_delta(capital.economic_events,
                                       nation.government.agent.id), -100.0)
                self.assertEqual(
                    sum(recorded_cash_delta(frontier.economic_events, pioneer.id)
                        for pioneer in pioneers), 0.0)
                self.assertEqual(len(frontier._run_trace.rows), 5)
                self.assertEqual(frontier._run_trace.rows[-1]['kind'],
                                 'frontier_pioneer_grant')
                self.assertEqual(frontier._run_trace.rows[-1]['unit'], 'USD')
                self.assertIn('100 USD was spent', world['policy_feedback'][0])

    def test_expedition_refuses_insufficient_treasury_without_creating_pioneers(self):
        world, nation, capital, frontier = expedition_fixture(99.0)

        web_policy_action(world, 'frontier_expedition', frontier)

        self.assertEqual(nation.government.agent.cash, 99.0)
        self.assertEqual(frontier.agents, [])
        self.assertEqual(capital.economic_events, [])
        self.assertEqual(getattr(frontier, 'economic_events', []), [])
        self.assertEqual(frontier._run_trace.rows[0]['kind'],
                         'frontier_expedition_denied')
        self.assertIn('Insufficient Treasury', world['policy_feedback'][0])


if __name__ == '__main__':
    unittest.main()
