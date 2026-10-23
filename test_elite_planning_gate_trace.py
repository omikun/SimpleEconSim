"""Causal records for capitalist planner activation and cadence gates."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from economy.capitalist_planner import EliteCapitalistPlanner
from economy.transformation_graph import TransformationGraph
from goods import Goods
from metric_catalog import METRICS, TRACE_INSTRUMENTED
from random_cache import rand


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
                from price_trace import replay_event
                replay_row = {**gate, 'value_after': gate['after']}
                self.assertTrue(replay_event(replay_row)['matches'])
                if supply_event or concession_event:
                    gate['inputs']['matched_trigger']['turn'] -= 1
                    self.assertFalse(replay_event(replay_row)['matches'])

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
                          side_effect=AssertionError('preflight must not run')), \
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
        self.assertNotIn('preflight_candidate_snapshot', decision['inputs'])
        self.assertEqual(decision['inputs']['preflight_snapshot_status'],
                         'omitted; live planner records its actual evaluations once')
        self.assertNotIn('candidates', decision['inputs'])
        self.assertEqual(decision['inputs']['actual_consideration_order'][-2:],
                         ['inventory_liquidation', 'do_nothing'])

    def test_actual_luxury_scan_links_candidate_ranking_and_purchase(self):
        results = []
        traces = []
        for traced in (False, True):
            planner = EliteCapitalistPlanner()
            buyer = Actor(17, lord=True, inventory={})
            buyer.cash = 100.0
            seller = Actor(18, lord=False, inventory={Goods.foreign_luxuries: 1})
            seller.cash = 3.0
            region, _, trace = self.make_region(actor=buyer, traced=traced)
            region.agents.append(seller)
            region.goods = [Goods.foreign_luxuries]
            region.recipes = {Goods.foreign_luxuries: {'price': 10.0}}
            region.economic_events = []
            with patch.object(planner, '_elite_candidate_snapshot',
                              side_effect=AssertionError('preflight must not run')), \
                    patch.object(planner, 'get_market_luxuries',
                                 return_value=[(Goods.foreign_luxuries, 10.0, 5.0, 1)]):
                result = planner._plan_and_execute_elite(buyer, region, 7)
            results.append((result['action_taken'], buyer.cash, seller.cash,
                            buyer.inv_get(Goods.foreign_luxuries),
                            seller.inv_get(Goods.foreign_luxuries)))
            traces.append(trace)

        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], ('PURCHASE_LUXURY', 90.0, 13.0, 1, 0))
        trace = traces[1]
        evaluation = next(row for row in trace.rows
                          if row.get('kind') == 'elite_luxury_purchase_evaluation')
        execution = next(row for row in trace.rows
                         if row.get('kind') == 'elite_luxury_purchase_execution')
        candidate = evaluation['inputs']['candidate_evaluations'][0]
        self.assertTrue(candidate['selected'])
        self.assertEqual(candidate['seller_id'], '18')
        self.assertIn(evaluation['event_id'], execution['cause_event_ids'])
        self.assertEqual(execution['inputs']['buyer_inventory_before'], 0.0)
        self.assertEqual(execution['inputs']['buyer_inventory_after'], 1.0)

    def test_actual_labor_legislation_scan_records_priority_and_petition_result(self):
        planner = EliteCapitalistPlanner()
        sponsor = Actor(27, lord=True)
        sponsor.cash = 50.0
        government = Actor(99, lord=False)
        government.cash = 1.0
        region, _, trace = self.make_region(actor=sponsor)
        region.gov = SimpleNamespace(agent=government)
        region.labor_law_petitions = []
        region.labor_laws = {}

        def operator(operator_id, feasible, reason, law, fee):
            def execute(agent, target, turn):
                agent.cash -= fee
                government.cash += fee
                petition = {'id': len(target.labor_law_petitions) + 1,
                            'law': law, 'sponsor_id': agent.id,
                            'fee': fee, 'requested_turn': turn,
                            'status': 'proposed'}
                target.labor_law_petitions.append(petition)
                return {'success': True, 'petition_id': petition['id'],
                        'fee_paid': fee}
            return SimpleNamespace(
                can_agent_execute=lambda _agent, _region: (feasible, reason),
                on_execute=execute)

        operators = {
            'petition_statute_of_laborers': operator(
                'statute', False, 'wage squeeze gate failed', 'wage_cap', 20.0),
            'enforce_vagrancy_decree': operator(
                'vagrancy', True, 'workhouse and cash gates passed', 'vagrancy', 10.0)}
        with patch.object(TransformationGraph, 'get_operator',
                          side_effect=lambda op_id: operators[op_id]):
            result = planner.evaluate_class_legislation(sponsor, region, 8)

        self.assertEqual(result['action_taken'], 'PETITION_VAGRANCY_DECREE')
        evaluation = next(row for row in trace.rows
                          if row.get('kind') == 'elite_labor_legislation_evaluation')
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'elite_labor_legislation_petition')
        rows = evaluation['inputs']['candidate_evaluations']
        self.assertEqual([row['operator_id'] for row in rows], [
            'petition_statute_of_laborers', 'enforce_vagrancy_decree'])
        self.assertFalse(rows[0]['can_execute'])
        self.assertTrue(rows[1]['selected_for_execution'])
        self.assertIn(evaluation['event_id'], outcome['cause_event_ids'])
        self.assertEqual(outcome['inputs']['state_before']['sponsor_cash'], 50.0)
        self.assertEqual(outcome['inputs']['state_after']['sponsor_cash'], 40.0)
        self.assertEqual(outcome['inputs']['state_after']['petition_count'], 1)

    def test_live_plan_does_not_run_mutating_preflight_or_consume_randomness(self):
        planner = EliteCapitalistPlanner()
        owner = Actor(37, lord=False)
        owner.is_corporation = True
        owner.output = Goods.furniture
        owner.employees = []
        owner.cash = 100.0
        grower = Actor(38, lord=False, inventory={})
        grower.output = Goods.wood
        grower.assigned_plot_id = 'plot-1'
        plot = SimpleNamespace(plot_id='plot-1', lord_id=grower.id,
                               controlled_by_id=grower.id, fraction=1.0)
        region, _, _ = self.make_region(actor=owner, traced=False)
        region.agents.append(grower)
        region.recipes = {
            Goods.furniture: {'price': 20.0, 'production': 2.0,
                              'input': Goods.wood, 'numInput': 1},
            Goods.wood: {'price': 5.0}}
        region.tenure = SimpleNamespace(plots=[plot])
        region.economic_events = []
        region.neighbors = {}
        region._last_turn = 7
        random_index_before = rand._idx

        with patch.object(planner, '_elite_candidate_snapshot',
                          side_effect=AssertionError('preflight must not run')), \
                patch.object(planner, '_plan_and_execute_elite',
                             return_value={'action_taken': None, 'details': {}}):
            planner.plan_and_execute_elite(owner, region, 7)

        self.assertFalse(getattr(region, 'water_rights_initialized', False))
        self.assertFalse(hasattr(region, 'water_rights'))
        self.assertEqual(rand._idx, random_index_before)

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
        self.assertIn(evaluation['event_id'], decision['cause_event_ids'])
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
        self.assertIn(evaluation['event_id'], decision['cause_event_ids'])

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
        self.assertIn(evaluation['event_id'], decision['cause_event_ids'])
        outcome = next(row for row in trace.rows
                       if row['kind'] == 'corporation_ai_outcome')
        self.assertEqual(outcome['decision_id'], decision['event_id'])
        self.assertEqual(outcome['inputs']['details']['company_cash_after'], 150.0)

    def _coercive_labor_case(self, captive_labor, traced, frontier=False):
        planner = EliteCapitalistPlanner()
        owner = Actor(37, lord=False, inventory={Goods.rum: 1})
        owner.is_trader = True
        owner.cash = 80.0
        owner.frontier_estates = ([] if frontier else [{
            'target_region': 'Overseas_Colony',
            'primary_commodity': 'cotton',
            'turn_acquired': 4,
            'displaced_population': 20,
            'captive_labor': captive_labor,
        }])
        commoner = Actor(38, lord=False)
        commoner.cash = 4.0
        region, _, trace = self.make_region(
            goods=[Goods.cotton], actor=owner, traced=traced)
        region.agents = [owner, commoner]
        region.recipes = {
            Goods.cotton: {'price': 8.0 if frontier else 4.0,
                           'production': 10.0, 'numInput': 0}}
        target = SimpleNamespace(name='Frontier', wilderness=True,
                                 wilderness_pop=15, climate='tropical', biome='plains')
        region.neighbors = {'Frontier': target} if frontier else {}
        region.economic_events = []
        region.home_currency = 'crown'
        planner._elite_candidate_snapshot = lambda *_args: []
        planner.get_market_luxuries = lambda *_args: []
        planner.evaluate_triangular_trade_voyage = lambda *_args: None
        planner.evaluate_spatial_trade = lambda *_args: None
        planner.evaluate_class_legislation = lambda *_args: None
        planner._execute_input_control = lambda *_args: None
        with patch('economy.actor_accounts.record', return_value=None):
            result = planner.plan_and_execute_elite(owner, region, 7)
        return result, owner, commoner, region, trace

    def test_actual_captive_labor_gates_and_execution_are_linked(self):
        gang_traced = self._coercive_labor_case(captive_labor=5, traced=True)
        gang_plain = self._coercive_labor_case(captive_labor=5, traced=False)
        result, owner, commoner, _region, trace = gang_traced
        plain_result, plain_owner, plain_commoner, _plain_region, _ = gang_plain
        self.assertEqual(result['action_taken'], 'MANDATE_PLANTATION_LABOR_GANG')
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual((owner.cash, commoner.cash,
                          owner.inv_get(Goods.cotton, 0),
                          owner.frontier_estates[0]['captive_labor']),
                         (plain_owner.cash, plain_commoner.cash,
                          plain_owner.inv_get(Goods.cotton, 0),
                          plain_owner.frontier_estates[0]['captive_labor']))
        self.assertEqual((owner.cash, commoner.cash,
                          owner.inv_get(Goods.cotton, 0),
                          owner.frontier_estates[0]['captive_labor']),
                         (70.0, 14.0, 15.0, 4))

        gang_gate = next(row for row in trace.rows
                         if row['kind'] == 'elite_operator_evaluation'
                         and row['inputs']['stage'] == 'plantation_labor_gang')
        self.assertTrue(gang_gate['inputs']['can_execute'])
        self.assertTrue(gang_gate['inputs']['return_gate_passed'])
        self.assertEqual(gang_gate['inputs']['strict_return_threshold'], 10.0)
        gang_execution = next(row for row in trace.rows
                              if row['kind'] == 'elite_operator_execution')
        self.assertEqual(gang_execution['inputs']['execution_result']['wage_cost_to_laborers'], 0.0)
        self.assertEqual(gang_execution['inputs']['state_after']['commoner_cash'][0]['cash'], 14.0)
        self.assertEqual(gang_execution['inputs']['state_after']['tracked_inventory']['cotton'], 15.0)

        procurement_traced = self._coercive_labor_case(captive_labor=0, traced=True)
        procurement_plain = self._coercive_labor_case(captive_labor=0, traced=False)
        result, owner, commoner, _region, trace = procurement_traced
        plain_result, plain_owner, plain_commoner, _plain_region, _ = procurement_plain
        self.assertEqual(result['action_taken'], 'PROCURE_CAPTIVE_LABOR')
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual((owner.cash, commoner.cash, owner.inv_get(Goods.rum, 0),
                          owner.frontier_estates[0]['captive_labor']),
                         (plain_owner.cash, plain_commoner.cash,
                          plain_owner.inv_get(Goods.rum, 0),
                          plain_owner.frontier_estates[0]['captive_labor']))
        self.assertEqual((owner.cash, commoner.cash, owner.inv_get(Goods.rum, 0),
                          owner.frontier_estates[0]['captive_labor']),
                         (80.0, 4.0, 0.0, 5))

        gates = [row for row in trace.rows
                 if row['kind'] == 'elite_operator_evaluation'
                 and row['inputs']['stage'] in ('plantation_labor_gang',
                                                'procure_captive_labor')]
        self.assertEqual([row['inputs']['stage'] for row in gates],
                         ['plantation_labor_gang', 'procure_captive_labor'])
        self.assertFalse(gates[0]['inputs']['can_execute'])
        self.assertEqual(gates[0]['inputs']['feasibility_reason'],
                         'Prerequisites hook failed')
        self.assertTrue(gates[1]['inputs']['return_gate_passed'])
        procurement_execution = next(row for row in trace.rows
                                     if row['kind'] == 'elite_operator_execution')
        self.assertEqual(procurement_execution['inputs']['execution_result']['cost_type'], 'rum')
        self.assertEqual(procurement_execution['inputs']['state_after']['tracked_inventory']['rum'], 0.0)
        decision = next(row for row in trace.rows
                        if row['kind'] == 'corporation_ai_decision')
        all_operator_gates = [row for row in trace.rows
                              if row['kind'] == 'elite_operator_evaluation']
        self.assertTrue({row['event_id'] for row in all_operator_gates}
                        <= set(decision['cause_event_ids']))
        outcome = next(row for row in trace.rows
                       if row['kind'] == 'corporation_ai_outcome')
        self.assertIn(procurement_execution['event_id'], outcome['cause_event_ids'])

        frontier_traced = self._coercive_labor_case(
            captive_labor=0, traced=True, frontier=True)
        frontier_plain = self._coercive_labor_case(
            captive_labor=0, traced=False, frontier=True)
        result, owner, commoner, region, trace = frontier_traced
        plain_result, plain_owner, plain_commoner, plain_region, _ = frontier_plain
        self.assertEqual(result['action_taken'], 'WAR_CAPITALISM_FRONTIER_CONQUEST')
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual((owner.cash, commoner.cash,
                          owner.frontier_estates, owner.inv_get(Goods.cotton, 0),
                          region.neighbors['Frontier'].wilderness_pop),
                         (plain_owner.cash, plain_commoner.cash,
                          plain_owner.frontier_estates, plain_owner.inv_get(Goods.cotton, 0),
                          plain_region.neighbors['Frontier'].wilderness_pop))
        self.assertEqual((owner.cash, commoner.cash, owner.inv_get(Goods.cotton, 0),
                          region.neighbors['Frontier'].wilderness_pop),
                         (45.0, 39.0, 10.0, 0))
        gates = [row for row in trace.rows
                 if row['kind'] == 'elite_operator_evaluation'
                 and row['inputs']['stage'] in ('plantation_labor_gang',
                                                'procure_captive_labor',
                                                'frontier_conquest')]
        self.assertEqual([row['inputs']['stage'] for row in gates],
                         ['plantation_labor_gang', 'procure_captive_labor',
                          'frontier_conquest'])
        conquest_gate = gates[-1]
        self.assertTrue(conquest_gate['inputs']['can_execute'])
        self.assertTrue(conquest_gate['inputs']['return_gate_passed'])
        self.assertEqual(conquest_gate['inputs']['return_basis']['expected_unit_price'], 8.0)
        self.assertEqual(conquest_gate['inputs']['estimated_net_return'], 50.0)
        conquest_execution = next(row for row in trace.rows
                                  if row['kind'] == 'elite_operator_execution')
        self.assertEqual(conquest_execution['inputs']['execution_result']['displaced_pop'], 15)
        self.assertEqual(conquest_execution['inputs']['state_after']['frontier_estates'][0]
                         ['primary_commodity'], 'cotton')

    def _machinery_case(self, *, repair, traced):
        planner = EliteCapitalistPlanner()
        owner_inventory = ({Goods.iron: 1} if repair else
                           {Goods.iron: 2, Goods.coal: 1})
        owner = Actor(47, lord=False, inventory=owner_inventory)
        owner.cash = 80.0
        company_inventory = ({Goods.iron: 1} if repair else
                             {Goods.iron: 2, Goods.coal: 1})
        company = Actor(48, lord=False, inventory=company_inventory)
        company.is_corporation = True
        company.cash = 100.0 if repair else 50.0
        company.output = Goods.furniture
        company.machinery_level = 0 if repair else 1
        company.broken_machinery = 1 if repair else 0
        company.max_employees = 10
        owner.company_owned = company
        artisan = Actor(49, lord=False)
        artisan.cash = 5.0
        artisan.output = Goods.iron if repair else Goods.wood
        region, _, trace = self.make_region(actor=owner, traced=traced)
        region.agents = [owner, company, artisan]
        region.recipes = {
            Goods.iron: {'price': 5.0, 'production': 1.0, 'numInput': 0},
            Goods.coal: {'price': 3.0, 'production': 1.0, 'numInput': 0}}
        region.neighbors = {}
        region.economic_events = []
        region.home_currency = 'crown'
        planner._elite_candidate_snapshot = lambda *_args: []
        planner.get_market_luxuries = lambda *_args: []
        planner.evaluate_triangular_trade_voyage = lambda *_args: None
        planner.evaluate_spatial_trade = lambda *_args: None
        planner.evaluate_class_legislation = lambda *_args: None
        planner._execute_input_control = lambda *_args: None
        with patch('economy.actor_accounts.record', return_value=None):
            result = planner.plan_and_execute_elite(owner, region, 7)
        return result, owner, company, artisan, trace

    def test_actual_machinery_gates_and_execution_state_are_linked(self):
        repair_traced = self._machinery_case(repair=True, traced=True)
        repair_plain = self._machinery_case(repair=True, traced=False)
        result, owner, company, artisan, trace = repair_traced
        plain_result, plain_owner, plain_company, plain_artisan, _ = repair_plain
        self.assertEqual(result['action_taken'], 'REPAIR_MACHINERY')
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual((owner.cash, company.cash, artisan.cash,
                          company.inv_get(Goods.iron, 0),
                          company.broken_machinery, company.machinery_level),
                         (plain_owner.cash, plain_company.cash, plain_artisan.cash,
                          plain_company.inv_get(Goods.iron, 0),
                          plain_company.broken_machinery, plain_company.machinery_level))
        self.assertEqual((company.cash, artisan.cash,
                          company.inv_get(Goods.iron, 0),
                          company.broken_machinery, company.machinery_level),
                         (90.0, 15.0, 0, 0, 1))
        repair_gate = next(row for row in trace.rows
                           if row['kind'] == 'elite_operator_evaluation'
                           and row['inputs']['stage'] == 'machinery_repair')
        self.assertTrue(repair_gate['inputs']['can_execute'])
        self.assertIsNone(repair_gate['inputs']['return_gate_passed'])
        self.assertEqual(repair_gate['inputs']['prerequisite_basis']
                         ['broken_machinery'], 1)
        repair_execution = next(row for row in trace.rows
                                if row['kind'] == 'elite_operator_execution')
        self.assertEqual(repair_execution['inputs']['state_before']['firm_state'][0]
                         ['broken_machinery'], 1)
        self.assertEqual(repair_execution['inputs']['state_after']['firm_state'][0]
                         ['broken_machinery'], 0)

        construction_traced = self._machinery_case(repair=False, traced=True)
        construction_plain = self._machinery_case(repair=False, traced=False)
        result, owner, company, artisan, trace = construction_traced
        plain_result, plain_owner, plain_company, plain_artisan, _ = construction_plain
        self.assertEqual(result['action_taken'], 'CONSTRUCT_MACHINERY')
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual((owner.cash, company.cash, artisan.cash,
                          company.inv_get(Goods.iron, 0), company.inv_get(Goods.coal, 0),
                          company.machinery_level, company.max_employees),
                         (plain_owner.cash, plain_company.cash, plain_artisan.cash,
                          plain_company.inv_get(Goods.iron, 0),
                          plain_company.inv_get(Goods.coal, 0),
                          plain_company.machinery_level, plain_company.max_employees))
        self.assertEqual((company.cash, artisan.cash,
                          company.inv_get(Goods.iron, 0), company.inv_get(Goods.coal, 0),
                          company.machinery_level, company.max_employees),
                         (25.0, 30.0, 0, 0, 2, 15))
        gates = [row for row in trace.rows
                 if row['kind'] == 'elite_operator_evaluation'
                 and row['inputs']['stage'] in ('machinery_repair',
                                                'machinery_construction')]
        self.assertEqual([row['inputs']['stage'] for row in gates],
                         ['machinery_repair', 'machinery_construction'])
        self.assertFalse(gates[0]['inputs']['can_execute'])
        self.assertTrue(gates[1]['inputs']['can_execute'])
        self.assertTrue(gates[1]['inputs']['planner_cash_gate_passed'])
        self.assertEqual(gates[1]['inputs']['prerequisite_basis']
                         ['required_cash_before_inventory_credit'], 38.0)
        self.assertEqual(gates[1]['inputs']['return_basis']['formula'],
                         '35 * shadow_price_cash')
        self.assertEqual(gates[1]['inputs']['estimated_net_return'], 35.0)
        construction_execution = next(row for row in trace.rows
                                      if row['kind'] == 'elite_operator_execution')
        self.assertEqual(construction_execution['inputs']['execution_result']
                         ['new_machinery_level'], 2)

    def test_construction_cash_gate_is_logged_when_not_met(self):
        def run_case(traced):
            planner = EliteCapitalistPlanner()
            owner = Actor(57, lord=False)
            owner.cash = 50.0
            region, _, trace = self.make_region(actor=owner, traced=traced)
            region.recipes = {}
            region.neighbors = {}
            region.economic_events = []
            region.home_currency = 'crown'
            planner._elite_candidate_snapshot = lambda *_args: []
            planner.get_market_luxuries = lambda *_args: []
            planner.evaluate_triangular_trade_voyage = lambda *_args: None
            planner.evaluate_spatial_trade = lambda *_args: None
            planner.evaluate_class_legislation = lambda *_args: None
            planner._execute_input_control = lambda *_args: None
            with patch('economy.actor_accounts.record', return_value=None):
                result = planner.plan_and_execute_elite(owner, region, 7)
            return result, owner, trace

        result, owner, trace = run_case(True)
        plain_result, plain_owner, _ = run_case(False)

        gate = next(row for row in trace.rows
                    if row['kind'] == 'elite_operator_evaluation'
                    and row['inputs']['stage'] == 'machinery_construction')
        self.assertIsNone(result['action_taken'])
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual(plain_owner.cash, owner.cash)
        self.assertFalse(gate['inputs']['planner_cash_gate_passed'])
        self.assertEqual(gate['inputs']['planner_cash_gate_threshold'], 60.0)
        self.assertEqual(gate['inputs']['feasibility_reason'],
                         'Planner cash threshold $60.0 not met')

    def _lord_transformation_case(self, traced, candidate_returns=(8.0, 94.0)):
        planner = EliteCapitalistPlanner()
        lord = Actor(67, lord=True, inventory={Goods.food: 2})
        lord.cash = 100.0
        commoner = Actor(68, lord=False)
        region, _, trace = self.make_region(
            goods=[Goods.cotton], actor=lord, traced=traced)
        region.agents = [lord, commoner]
        region.recipes = {
            Goods.cotton: {'price': 8.0, 'production': 10.0, 'numInput': 0}}
        region.neighbors = {}
        region.economic_events = []
        region.home_currency = 'crown'
        planner._elite_candidate_snapshot = lambda *_args: []
        planner.get_market_luxuries = lambda *_args: []
        planner.evaluate_triangular_trade_voyage = lambda *_args: None
        planner.evaluate_spatial_trade = lambda *_args: None
        planner.evaluate_class_legislation = lambda *_args: None

        def make_operator(op_id, category, feasible, reason, return_value,
                          *, output=None, execute=None, cash_cost=0.0):
            return SimpleNamespace(
                id=op_id, name=op_id.replace('_', ' ').title(), category=category,
                cash_cost=cash_cost, input_goods={}, output_goods=output or {},
                estimate_return_hook=None,
                can_agent_execute=lambda _agent, _region: (feasible, reason),
                estimate_net_return=lambda _agent, _region, _shadow: return_value,
                on_execute=execute)

        operators = [
            make_operator('enclose_candidate', 'enclosure', True,
                          'feudal plot available', candidate_returns[0]),
            make_operator('corvee_cotton_plantation', 'corvee', True,
                          'warm climate and lord status', candidate_returns[1],
                          output={Goods.cotton: 12.0},
                          cash_cost=2.0,
                          execute=lambda agent, _region, _turn: (
                              agent.inv_add(Goods.cotton, 12),
                              {'success': True, 'yield': 12})[1]),
            make_operator('excluded_candidate', 'political', True,
                          'eligible but not a conversion category', 999.0),
            make_operator('blocked_candidate', 'corvee', False,
                          'requires customary tenure', 1000.0),
        ]
        with patch.object(TransformationGraph, 'all_operators', return_value=operators), \
                patch('economy.actor_accounts.record', return_value=None):
            result = planner.plan_and_execute_elite(lord, region, 7)
        return result, lord, region, trace

    def test_lord_transformation_scan_records_actual_rank_and_selected_action(self):
        traced = self._lord_transformation_case(True)
        plain = self._lord_transformation_case(False)
        result, lord, _region, trace = traced
        plain_result, plain_lord, _plain_region, _ = plain
        self.assertEqual(result['action_taken'],
                         'OPERATOR_EXECUTED_CORVEE_COTTON_PLANTATION')
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual(lord.inv_get(Goods.cotton, 0), 12)
        self.assertEqual(plain_lord.inv_get(Goods.cotton, 0), 12)

        evaluation = next(row for row in trace.rows
                          if row['kind'] == 'elite_lord_transformation_evaluation')
        candidates = evaluation['inputs']['candidate_evaluations']
        self.assertEqual([row['operator_id'] for row in candidates], [
            'enclose_candidate', 'corvee_cotton_plantation',
            'excluded_candidate', 'blocked_candidate'])
        self.assertEqual(candidates[0]['best_return_before'], -999.0)
        self.assertTrue(candidates[0]['selected_as_best'])
        self.assertEqual(candidates[1]['best_return_before'], 8.0)
        self.assertTrue(candidates[1]['selected_as_best'])
        self.assertFalse(candidates[2]['category_eligible_for_lord_planning'])
        self.assertIsNone(candidates[2]['estimated_net_return'])
        self.assertFalse(candidates[3]['can_execute'])
        self.assertEqual(evaluation['inputs']['best_operator_id'],
                         'corvee_cotton_plantation')
        self.assertEqual(evaluation['inputs']['strict_execution_threshold'], 5.0)
        self.assertEqual(evaluation['inputs']['best_net_return'], 94.0)
        self.assertEqual(candidates[1]['return_basis']['outputs'][0]
                         ['value_contribution'], 96.0)
        self.assertEqual(candidates[1]['return_basis']['cash_cost_contribution'], 2.0)
        execution = next(row for row in trace.rows
                         if row['kind'] == 'elite_operator_execution')
        self.assertEqual(execution['inputs']['execution_result']['yield'], 12)
        self.assertEqual(execution['inputs']['state_after']['tracked_inventory']['cotton'], 12.0)
        decision = next(row for row in trace.rows
                        if row['kind'] == 'corporation_ai_decision')
        self.assertIn(evaluation['event_id'], decision['cause_event_ids'])

    def test_lord_transformation_return_equal_to_cutoff_does_not_execute(self):
        traced = self._lord_transformation_case(True, candidate_returns=(5.0, 4.0))
        plain = self._lord_transformation_case(False, candidate_returns=(5.0, 4.0))
        result, lord, _region, trace = traced
        plain_result, plain_lord, _plain_region, _ = plain
        self.assertIsNone(result['action_taken'])
        self.assertEqual(plain_result['action_taken'], result['action_taken'])
        self.assertEqual(lord.inv_get(Goods.cotton, 0), 0)
        self.assertEqual(plain_lord.inv_get(Goods.cotton, 0), 0)
        evaluation = next(row for row in trace.rows
                          if row['kind'] == 'elite_lord_transformation_evaluation')
        self.assertEqual(evaluation['inputs']['best_net_return'], 5.0)
        self.assertFalse(evaluation['inputs']['selected_for_execution'])
        self.assertEqual(evaluation['inputs']['selection_reason'],
                         'best_return_not_above_strict_threshold')


if __name__ == '__main__':
    unittest.main()
