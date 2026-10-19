"""Causal records for capitalist planner activation and cadence gates."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from economy.capitalist_planner import EliteCapitalistPlanner
from economy.transformation_graph import TransformationGraph
from goods import Goods
from metric_catalog import METRICS, TRACE_INSTRUMENTED


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'elite-gate-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Actor:
    def __init__(self, agent_id, *, lord=True, inventory=None):
        self.id = agent_id
        self.is_lord = lord
        self.is_corporation = False
        self.alive = True
        self.cash = 0.0
        self._inventory = inventory or {}
        self.company_owned = None
        self.employer = None

    def inv_get(self, good, default=0):
        return self._inventory.get(good, default)

    def inv_add(self, good, amount):
        self._inventory[good] = self._inventory.get(good, 0) + amount


class ElitePlanningGateTraceTests(unittest.TestCase):
    def make_region(self, *, turn=7, goods=(), actor=None, traced=True):
        actor = actor or Actor(17)
        region = SimpleNamespace(
            name='TraceMarket', goods=list(goods), agents=[actor],
            supply_proposal_events=[], concession_events=[])
        trace = MemoryTrace()
        if traced:
            region._run_trace = trace
            region._collective_trace_clock = {
                'turn': turn, 'phase': 'local', 'next': 1}
        return region, actor, trace

    def test_new_market_good_triggers_and_links_planning_gate(self):
        planner = EliteCapitalistPlanner()
        region, actor, trace = self.make_region(
            goods=['cotton'], actor=Actor(17, inventory={'cotton': 2}))

        self.assertTrue(planner.check_new_market_items(region))
        self.assertTrue(planner.should_run_planning(actor, region, 7, True))

        scan, gate = trace.rows
        self.assertEqual(scan['kind'], 'elite_market_novelty_scan')
        self.assertEqual(scan['metric_id'], 'market.elite_market_novelty')
        self.assertEqual(scan['after'], 1)
        self.assertEqual(scan['inputs']['new_goods'], ['cotton'])
        self.assertEqual(gate['kind'], 'elite_planning_gate')
        self.assertEqual(gate['metric_id'], 'market.elite_planning_gate')
        self.assertEqual(gate['after'], 1)
        self.assertEqual(gate['inputs']['reason'], 'new_market_item')
        self.assertEqual(gate['cause_event_ids'], [scan['event_id']])

        actor._inventory['cotton'] = 0
        self.assertFalse(planner.check_new_market_items(region))
        self.assertEqual(trace.rows[-1]['inputs']['removed_goods'], ['cotton'])
        actor._inventory['cotton'] = 2
        self.assertTrue(planner.check_new_market_items(region))
        self.assertEqual(trace.rows[-1]['inputs']['new_goods'], ['cotton'])

    def test_gate_records_each_existing_trigger_and_cadence_reason(self):
        cases = (
            (7, {'turn': 7, 'buyer_id': 17, 'proposal_id': 'p-1',
                 'kind': 'advance_offtake', 'status': 'settled'},
             None, False, True, 'same_turn_supply_proposal'),
            (7, None, {'turn': 7, 'sponsor_id': 17, 'petition_id': 'c-1',
                       'status': 'enacted'},
             False, True, 'same_turn_concession'),
            (10, None, None, False, True, 'five_turn_cadence'),
            (8, None, None, False, False, 'not_due'),
        )
        for turn, supply_event, concession_event, market_new, expected, reason in cases:
            with self.subTest(reason=reason):
                planner = EliteCapitalistPlanner()
                region, actor, trace = self.make_region(turn=turn, goods=())
                if supply_event:
                    region.supply_proposal_events.append(supply_event)
                if concession_event:
                    region.concession_events.append(concession_event)
                self.assertFalse(planner.check_new_market_items(region))

                self.assertEqual(
                    planner.should_run_planning(actor, region, turn, market_new), expected)
                gate = trace.rows[-1]
                self.assertEqual(gate['inputs']['reason'], reason)
                self.assertEqual(gate['after'], int(expected))
                if supply_event or concession_event:
                    self.assertEqual(gate['inputs']['matched_trigger']['status'],
                                     (supply_event or concession_event)['status'])

    def test_trace_does_not_change_novelty_or_cadence_results(self):
        results = []
        for traced in (False, True):
            planner = EliteCapitalistPlanner()
            region, actor, _ = self.make_region(
                goods=['grain'], actor=Actor(17, inventory={'grain': 1}),
                traced=traced)
            first_scan = planner.check_new_market_items(region)
            first_gate = planner.should_run_planning(actor, region, 1, first_scan)
            second_scan = planner.check_new_market_items(region)
            second_gate = planner.should_run_planning(actor, region, 1, second_scan)
            results.append((first_scan, first_gate, second_scan, second_gate))
        self.assertEqual(results, [(True, True, False, False)] * 2)

    def test_metric_catalog_covers_planner_gates_and_existing_strategy_events(self):
        for metric_id in ('market.supply_strategy', 'market.elite_market_novelty',
                          'market.elite_planning_gate',
                          'market.elite_planner_phase_gate'):
            with self.subTest(metric_id=metric_id):
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)

    def test_scenario_owner_policy_suppression_is_explicit(self):
        planner = EliteCapitalistPlanner()
        region, _, trace = self.make_region()
        region.scenario_owner_policy = True

        planner.record_planning_phase_gate(region, 7, planning_enabled=False)

        event = trace.rows[-1]
        self.assertEqual(event['metric_id'], 'market.elite_planner_phase_gate')
        self.assertEqual(event['after'], 0)
        self.assertEqual(event['inputs']['reason'], 'scenario_owner_policy')
        self.assertTrue(event['inputs']['scenario_owner_policy'])

    def test_corporate_plan_has_queryable_decision_and_linked_cash_outcome(self):
        planner = EliteCapitalistPlanner()
        region, actor, trace = self.make_region(actor=Actor(17))
        region.recipes = {}
        region.neighbors = {}
        region.economic_events = []
        region.home_currency = 'crown'

        with patch.object(planner, '_elite_candidate_snapshot',
                          return_value=[{'candidate': 'do_nothing'}]), \
                patch.object(planner, '_plan_and_execute_elite',
                             return_value={'action_taken': None, 'details': {}}):
            planner.plan_and_execute_elite(actor, region, 7)

        decision = next(row for row in trace.rows
                        if row.get('kind') == 'corporation_ai_decision')
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'corporation_ai_outcome')
        self.assertEqual(decision['metric_id'], 'ai.elite_economic_decision')
        self.assertEqual(decision['after'], 'do_nothing')
        self.assertEqual(outcome['decision_id'], decision['event_id'])
        self.assertEqual(decision['inputs']['preflight_candidate_snapshot'],
                         [{'candidate': 'do_nothing'}])
        self.assertIn('separate diagnostic pass',
                      decision['inputs']['preflight_snapshot_status'])
        self.assertNotIn('candidates', decision['inputs'])
        self.assertEqual(decision['inputs']['actual_consideration_order'][-2:],
                         ['inventory_liquidation', 'do_nothing'])

    def _liquidation_case(self, buyer_cash, traced):
        planner = EliteCapitalistPlanner()
        seller = Actor(17, lord=False, inventory={Goods.wood: 4})
        buyer = Actor(18, lord=False)
        seller.cash = 0.0
        buyer.cash = float(buyer_cash)
        region, _, trace = self.make_region(
            goods=[Goods.wood], actor=seller, traced=traced)
        region.agents = [seller, buyer]
        region.recipes = {Goods.wood: {'price': 5.0}}
        region.economic_events = []
        region.neighbors = {}
        region.trade_manager = None
        region.home_currency = 'crown'

        planner._elite_candidate_snapshot = lambda *_args: [
            {'candidate': 'diagnostic_only'}]
        planner.get_market_luxuries = lambda *_args: []
        planner.evaluate_triangular_trade_voyage = lambda *_args: None
        planner.evaluate_spatial_trade = lambda *_args: None
        planner.evaluate_class_legislation = lambda *_args: None
        planner._execute_input_control = lambda *_args: None
        with patch.object(TransformationGraph, 'get_operator', return_value=None), \
                patch('economy.actor_accounts.record', return_value=None):
            result = planner.plan_and_execute_elite(seller, region, 7)
        return result, seller, buyer, trace

    def test_liquidation_uses_actual_first_affordable_buyer_and_traces_cash(self):
        traced = self._liquidation_case(10.0, True)
        plain = self._liquidation_case(10.0, False)
        traced_result, seller, buyer, trace = traced
        plain_result, plain_seller, plain_buyer, _ = plain

        self.assertEqual(traced_result['action_taken'], 'LIQUIDATE_WOOD')
        self.assertEqual(plain_result['action_taken'], traced_result['action_taken'])
        self.assertEqual((seller.cash, buyer.cash, seller.inv_get(Goods.wood),
                          buyer.inv_get(Goods.wood)),
                         (plain_seller.cash, plain_buyer.cash,
                          plain_seller.inv_get(Goods.wood),
                          plain_buyer.inv_get(Goods.wood)))
        self.assertEqual((seller.cash, buyer.cash,
                          seller.inv_get(Goods.wood), buyer.inv_get(Goods.wood)),
                         (10.0, 0.0, 2, 2))

        evaluation = next(row for row in trace.rows
                          if row['kind'] == 'elite_inventory_liquidation_decision')
        candidate = evaluation['inputs']['evaluated_goods'][-1]
        self.assertEqual(candidate['reason'], 'liquidation_selected')
        self.assertEqual(candidate['selected_buyer_id'], '18')
        self.assertEqual(candidate['sale_quantity'], 2.0)
        self.assertEqual(candidate['cash_received'], 10.0)
        self.assertEqual(candidate['settlement_path'], 'direct_inventory_transfer')
        decision = next(row for row in trace.rows
                        if row['kind'] == 'corporation_ai_decision')
        self.assertEqual(decision['cause_event_ids'], [evaluation['event_id']])
        outcome = next(row for row in trace.rows
                       if row['kind'] == 'corporation_ai_outcome')
        self.assertEqual(outcome['decision_id'], decision['event_id'])
        details = outcome['inputs']['details']
        self.assertEqual(details['buyer_cash_before'], 10.0)
        self.assertEqual(details['buyer_cash_after'], 0.0)
        self.assertEqual(details['seller_inventory_before'], 4.0)
        self.assertEqual(details['seller_inventory_after'], 2.0)
        self.assertEqual(details['buyer_inventory_before'], 0.0)
        self.assertEqual(details['buyer_inventory_after'], 2.0)
        self.assertFalse(details['currency_conversion_applied'])

    def test_liquidation_records_no_affordable_buyer_as_a_rejection(self):
        result, seller, buyer, trace = self._liquidation_case(4.0, True)

        self.assertIsNone(result['action_taken'])
        self.assertEqual(seller.inv_get(Goods.wood), 4)
        self.assertEqual(buyer.inv_get(Goods.wood), 0)
        evaluation = next(row for row in trace.rows
                          if row['kind'] == 'elite_inventory_liquidation_decision')
        candidate = evaluation['inputs']['evaluated_goods'][0]
        self.assertEqual(candidate['reason'], 'no_live_buyer_can_afford_one_unit')
        self.assertEqual(candidate['buyer_checks'][0]['reason'],
                         'seller_cannot_buy_own_inventory')
        self.assertEqual(candidate['buyer_checks'][1]['reason'],
                         'buyer_cannot_afford_one_unit')
        decision = next(row for row in trace.rows
                        if row['kind'] == 'corporation_ai_decision')
        self.assertEqual(decision['cause_event_ids'], [evaluation['event_id']])

    def _investment_case(self, traced):
        planner = EliteCapitalistPlanner()
        owner = Actor(27, lord=False)
        owner.cash = 400.0
        company = Actor(28, lord=False)
        company.is_corporation = True
        company.home_currency = 'crown'
        company.cash = 100.0
        company.wage = 2.0
        company.max_employees = 10
        company.output = Goods.food
        owner.company_owned = company
        region, _, trace = self.make_region(
            goods=[Goods.food, Goods.wood, Goods.furniture],
            actor=owner, traced=traced)
        region.agents = [owner, company]
        region.recipes = {
            Goods.food: {'price': 10.0, 'production': 1.0, 'numInput': 0},
            Goods.wood: {'price': 3.0, 'production': 2.0, 'numInput': 0},
            Goods.furniture: {'price': 100.0, 'production': 1.0,
                              'input': Goods.wood, 'numInput': 5.0},
        }
        region.economic_events = []
        region.neighbors = {}
        region.trade_manager = None
        region.home_currency = 'crown'
        planner._elite_candidate_snapshot = lambda *_args: []
        planner.get_market_luxuries = lambda *_args: []
        planner.evaluate_triangular_trade_voyage = lambda *_args: None
        planner.evaluate_spatial_trade = lambda *_args: None
        planner.evaluate_class_legislation = lambda *_args: None
        planner._execute_input_control = lambda *_args: None
        with patch.object(TransformationGraph, 'get_operator', return_value=None), \
                patch('economy.actor_accounts.record', return_value=None):
            result = planner.plan_and_execute_elite(owner, region, 7)
        return result, owner, company, trace

    def test_capital_expansion_records_actual_sector_scan_and_balances(self):
        traced = self._investment_case(True)
        plain = self._investment_case(False)
        result, owner, company, trace = traced
        plain_result, plain_owner, plain_company, _ = plain

        self.assertEqual(result['action_taken'], 'CAPITAL_EXPANSION')
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual((owner.cash, company.cash, company.wage,
                          company.max_employees),
                         (plain_owner.cash, plain_company.cash,
                          plain_company.wage, plain_company.max_employees))
        self.assertEqual((owner.cash, company.cash, company.wage,
                          company.max_employees), (350.0, 150.0, 2.5, 15))

        evaluation = next(row for row in trace.rows
                          if row['kind'] == 'elite_capital_allocation_evaluation')
        inputs = evaluation['inputs']
        self.assertEqual(evaluation['after'], 'CAPITAL_EXPANSION')
        self.assertEqual(inputs['best_sector'], 'food')
        furniture = next(row for row in inputs['eligible_sector_evaluations']
                         if row['good'] == 'furniture')
        self.assertEqual(furniture['raw_margin'], 85.0)
        self.assertEqual(furniture['local_input_supply'], 0)
        self.assertEqual(furniture['input_shortage_penalty'], 0.05)
        self.assertEqual(furniture['effective_margin'], 4.25)
        decision = next(row for row in trace.rows
                        if row['kind'] == 'corporation_ai_decision')
        self.assertEqual(decision['cause_event_ids'], [evaluation['event_id']])
        outcome = next(row for row in trace.rows
                       if row['kind'] == 'corporation_ai_outcome')
        self.assertEqual(outcome['decision_id'], decision['event_id'])
        self.assertEqual(outcome['inputs']['details']['company_cash_after'], 150.0)


if __name__ == '__main__':
    unittest.main()
