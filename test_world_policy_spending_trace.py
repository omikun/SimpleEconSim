"""Trace one-shot city, provincial, and national policy spending."""

import json
import unittest
from types import SimpleNamespace

from client.desktop.panels.gov_panel import _execute_gov_policy as desktop_gov_action
from metric_catalog import METRICS, TRACE_INSTRUMENTED
from worldview_gov_panel import _execute_gov_policy as web_gov_action
from worldview_policies import _execute_policy_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'world-policy-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, municipal_cash=500.0,
             add_residents=True):
    government = SimpleNamespace(id='city-government', cash=float(municipal_cash),
                                 is_government=True)
    household = SimpleNamespace(id='resident', cash=7.0, alive=True,
                                is_government=False, is_corporation=False,
                                home_currency='EGP')
    agents = [government]
    if add_residents:
        agents.append(household)
    city = SimpleNamespace(
        name='Ward', home_currency='EGP', gov=SimpleNamespace(
            agent=government, ubi_enabled=False, ubi_mandate_turns_left=0),
        agents=agents, owner_nation=None, police_officers=2,
        protest_energy_log=[1.4], economic_events=[],
        _next_economic_event_id=1)
    nation = SimpleNamespace(
        name='Republic', currency='EGP', tiles=[city],
        government=SimpleNamespace(agent=SimpleNamespace(
            id='national-government', cash=900.0)))
    city.owner_nation = nation
    trace = MemoryTrace()
    if traced:
        city._run_trace = trace
        city._collective_trace_clock = {
            'turn': 5, 'phase': 'policy_action', 'next': 1}
    world = {'turn': 5, 'tiles': [city], 'nations': [nation],
             'selected_region': city, 'policy_feedback': None}
    return world, city, nation, household, trace


def _province_fixture(*, traced=True, treasury_cash=400.0):
    world, city, nation, household, trace = _fixture(traced=traced)
    province_agent = SimpleNamespace(id='province-government',
                                     cash=float(treasury_cash))
    province = SimpleNamespace(name='Province', currency='EGP', tiles=[city],
                              gov=SimpleNamespace(agent=province_agent))
    city.province = province
    return world, province, city, household, trace


def _nation_fixture(*, traced=True, treasury_cash=400.0):
    world, city, _nation, household, trace = _fixture(traced=traced)
    nation = SimpleNamespace(
        name='Republic', currency='EGP', tiles=[city],
        government=SimpleNamespace(agent=SimpleNamespace(
            id='national-government', cash=float(treasury_cash))))
    city.owner_nation = nation
    return world, nation, city, household, trace


class WorldPolicySpendingTraceTests(unittest.TestCase):
    def test_safety_patrol_is_exact_paid_transfer_in_both_gov_panels(self):
        plain = _fixture(traced=False)
        _execute_policy_action(plain[0], 'city_safety_patrol', plain[1])
        self.assertEqual(plain[1].gov.agent.cash, 440.0)
        self.assertEqual(plain[3].cash, 67.0)
        self.assertEqual(plain[1].police_officers, 5)
        self.assertAlmostEqual(plain[1].protest_energy_log[-1], 1.0)

        for dispatch in (web_gov_action, desktop_gov_action):
            fixture = _fixture(traced=True)
            dispatch(fixture[0], 'city_safety_patrol', fixture[1])
            self.assertEqual(fixture[1].gov.agent.cash, 440.0)
            self.assertEqual(fixture[3].cash, 67.0)
            self.assertEqual(fixture[1].police_officers, 5)
            self.assertAlmostEqual(fixture[1].protest_energy_log[-1], 1.0)

            payment = next(row for row in fixture[4].rows
                           if row.get('metric_id') == 'finance.cash_transfer')
            self.assertEqual(payment['kind'], 'world_policy_agent_payment')
            contract = payment['inputs']['transfer_contract']
            self.assertEqual(contract['operation_type'], 'city_safety_patrol')
            self.assertEqual(contract['payer_account']['balance_before'], 500.0)
            self.assertEqual(contract['payer_account']['balance_after'], 440.0)
            self.assertEqual(contract['payee_account']['id'], 'resident')
            self.assertEqual(contract['payee_account']['balance_before'], 7.0)
            self.assertEqual(contract['payee_account']['balance_after'], 67.0)
            funding = next(row for row in fixture[4].rows
                           if row.get('kind') == 'world_policy_funding_decision')
            self.assertEqual(payment['cause_event_ids'], [funding['event_id']])
            journal = next(event for event in fixture[1].economic_events
                           if event.get('source_id') == contract['operation_id'])
            self.assertEqual(payment['inputs']['actor_account_event_id'],
                             journal['id'])
            outcome = next(row for row in fixture[4].rows
                           if row.get('kind') == 'world_policy_action_outcome')
            self.assertEqual(outcome['cause_event_ids'],
                             [funding['event_id'], payment['event_id']])

    def test_safety_patrol_without_recipient_is_explicit_expense(self):
        fixture = _fixture(traced=True, add_residents=False)
        _execute_policy_action(fixture[0], 'city_safety_patrol', fixture[1])

        self.assertEqual(fixture[1].gov.agent.cash, 440.0)
        self.assertEqual(fixture[1].police_officers, 5)
        expense = next(row for row in fixture[4].rows
                       if row.get('kind') == 'world_policy_expenditure')
        self.assertEqual(expense['metric_id'], 'finance.policy_expenditure')
        self.assertEqual(expense['after'], -60.0)
        self.assertEqual(expense['inputs']['transfer_contract'][
            'counterparty_leg_status'], 'policy_expenditure_no_cash_payee')

    def test_city_ubi_funding_and_repeal_are_traced(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)
        for fixture, dispatch in ((plain, web_gov_action),
                                  (traced, desktop_gov_action)):
            dispatch(fixture[0], 'city_toggle_ubi', fixture[1])
        self.assertEqual(plain[1].gov.agent.cash, 450.0)
        self.assertEqual(traced[1].gov.agent.cash, plain[1].gov.agent.cash)
        self.assertTrue(traced[1].gov.ubi_enabled)
        self.assertEqual(traced[1].gov.ubi_mandate_turns_left, 10)
        expense = next(row for row in traced[4].rows
                       if row.get('kind') == 'world_policy_expenditure')
        self.assertEqual(expense['after'], -50.0)
        self.assertTrue(expense['inputs']['transfer_contract'][
            'payee_account']['cash_balance_captured'] is False)

        web_gov_action(traced[0], 'city_toggle_ubi', traced[1])
        self.assertFalse(traced[1].gov.ubi_enabled)
        self.assertEqual(traced[1].gov.ubi_mandate_turns_left, 0)
        self.assertEqual(len([row for row in traced[4].rows
                              if row.get('kind') == 'world_policy_expenditure']), 1)
        repeal = [row for row in traced[4].rows
                  if row.get('kind') == 'world_policy_action_outcome'][-1]
        self.assertEqual(repeal['inputs']['reason_code'],
                         'mandate_repeal_requires_no_payment')

    def test_affordability_failure_has_no_debit_and_shows_transfer_dialog(self):
        fixture = _fixture(traced=True, municipal_cash=20.0)
        _execute_policy_action(fixture[0], 'city_farm_subsidy', fixture[1])

        self.assertEqual(fixture[1].gov.agent.cash, 20.0)
        self.assertEqual(fixture[0]['transfer_dialog']['cost'], 100.0)
        decision = next(row for row in fixture[4].rows
                        if row.get('kind') == 'world_policy_funding_decision')
        self.assertFalse(decision['after'])
        self.assertEqual(decision['inputs']['reason_code'],
                         'insufficient_treasury_cash')
        self.assertFalse(any(row.get('metric_id') in
                             ('finance.cash_transfer', 'finance.policy_expenditure')
                             for row in fixture[4].rows))
        _execute_policy_action(fixture[0], 'city_farm_subsidy', fixture[1])
        decisions = [row for row in fixture[4].rows
                     if row.get('kind') == 'world_policy_funding_decision']
        self.assertEqual(len({row['inputs']['operation_id']
                              for row in decisions}), 2)

    def test_other_policy_spends_report_the_current_unmodeled_service_effects(self):
        cases = (
            ('city_farm_subsidy', _fixture, web_gov_action, 100.0,
             'production_or_farm_state_effect_modeled'),
            ('prov_pave_highway', _province_fixture, desktop_gov_action,
             120.0, 'road_or_route_state_effect_modeled'),
            ('prov_healthcare', _province_fixture, web_gov_action, 150.0,
             'health_or_service_state_effect_modeled'),
            ('nat_science_prize', _nation_fixture, desktop_gov_action,
             300.0, 'research_or_recipient_effect_modeled'),
        )
        for action_id, make_fixture, dispatch, cost, missing_effect in cases:
            with self.subTest(action_id=action_id):
                plain = make_fixture(traced=False)
                fixture = make_fixture(traced=True)
                plain_target = plain[1]
                target = fixture[1]
                initial_cash = (target.gov.agent.cash if hasattr(target, 'gov')
                                else target.government.agent.cash)
                dispatch(plain[0], action_id, plain_target)
                dispatch(fixture[0], action_id, target)
                plain_cash = (plain_target.gov.agent.cash
                              if hasattr(plain_target, 'gov')
                              else plain_target.government.agent.cash)
                final_cash = (target.gov.agent.cash if hasattr(target, 'gov')
                              else target.government.agent.cash)
                self.assertEqual(final_cash, plain_cash)
                self.assertEqual(fixture[0]['policy_feedback'],
                                 plain[0]['policy_feedback'])
                self.assertEqual(initial_cash - final_cash, cost)
                expense = next(row for row in fixture[4].rows
                               if row.get('kind') == 'world_policy_expenditure')
                self.assertEqual(expense['after'], -cost)
                outcome = next(row for row in fixture[4].rows
                               if row.get('kind') == 'world_policy_action_outcome')
                self.assertFalse(outcome['inputs'][missing_effect])

    def test_new_world_policy_metrics_are_catalogued(self):
        for metric_id in ('scenario.world_policy_funding',
                          'scenario.world_policy_action'):
            self.assertIn(metric_id, METRICS)
            self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
