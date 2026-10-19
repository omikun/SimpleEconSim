"""Causal tracing for Nile repair harvest and grain-access outcomes."""

import tempfile
import unittest
from pathlib import Path

from goods import Goods
from region_production import produce
from run_trace import RunTrace, verify
from scenario_projects import advance, get_project, record_food_results, start_project
from worldview_engine import build_world_view


class NileRepairFoodResultTraceTests(unittest.TestCase):
    def test_realized_harvest_and_owner_purchase_resolve_to_source_events(self):
        world = build_world_view(scenario_id='egypt_1877')
        world['turn'] = 1
        tile = next(tile for tile in world['tiles']
                    if getattr(tile, 'scenario_location', None) == 'Nile Delta')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'nile-food-outcome.ctr'
            trace = RunTrace(path, 'nile-food-outcome-test')
            clock = {'next': 1, 'turn': 1, 'phase': 'scenario_projects'}
            for region in world['tiles']:
                region._run_trace = trace
                region._collective_trace_clock = clock

            self.assertTrue(start_project(world, 'nile_repair', 'Nile Delta')[0])
            for turn in (2, 3):
                world['turn'] = turn
                clock['turn'] = turn
                advance(world)
            project = get_project(world, 'nile_repair', 'Nile Delta')
            self.assertEqual(project['status'], 'operating')

            economy = world['scenario_state']['political_economy']
            owner_id = economy['warehouse_by_tile'][tile.name]
            owner = next(agent for agent in tile.agents if agent.id == owner_id)
            producer = next(agent for agent in tile.agents
                            if agent.id != owner_id and agent.output == Goods.food
                            and not getattr(agent, 'is_trader', False))
            owner.cash = 10000.0
            producer.inv_set(Goods.food, 100)

            world['turn'] = 4
            clock['turn'] = 4
            advance(world)
            produce(tile, 4)
            record_food_results(world)

            outcomes = trace.query(metric_id='scenario.nile_repair_outcome')
            self.assertEqual(outcomes['total'], 1)
            outcome = outcomes['events'][0]
            inputs = outcome['inputs']
            self.assertTrue(inputs['yield_applied_this_turn'])
            self.assertEqual(inputs['project_status'], 'operating')
            self.assertEqual(inputs['realized_yield_factor'], 1.8)
            self.assertEqual(inputs['food_produced'],
                             tile.production_log[Goods.food][-1])
            self.assertGreater(inputs['private_reserved_food'], 0)

            production = next(row for row in trace.recent
                              if row['event_id'] == inputs['production_event_id'])
            self.assertEqual(production['metric_id'], 'goods.production')
            self.assertEqual(production['kind'], 'tile_production_total')
            self.assertIn(production['event_id'], outcome['cause_event_ids'])
            self.assertIn(inputs['project_advance_event_id'],
                          outcome['cause_event_ids'])

            purchases = inputs['private_purchase_transactions']
            self.assertTrue(purchases)
            purchase_operation_ids = set(inputs['private_purchase_operation_ids'])
            transaction_events = [
                row for row in trace.recent
                if (row.get('inputs', {}).get('operation_id') in purchase_operation_ids
                    or (row.get('inputs', {}).get('transfer_contract') or {}).get(
                        'operation_id') in purchase_operation_ids)]
            self.assertTrue(transaction_events)
            self.assertTrue(all(row['event_id'] in outcome['cause_event_ids']
                                for row in transaction_events))
            self.assertEqual(inputs['unresolved_purchase_operation_ids'], [])

            owner_responses = trace.query(metric_id='scenario.nile_owner_response')
            self.assertEqual(owner_responses['total'], 1)
            self.assertEqual(owner_responses['events'][0]['value_after'],
                             purchases[0]['units'])
            self.assertTrue(owner_responses['events'][0]['cause_event_ids'])

            # Re-reading the same turn must not duplicate report or trace events.
            record_food_results(world)
            self.assertEqual(
                trace.query(metric_id='scenario.nile_repair_outcome')['total'], 1)
            self.assertEqual(
                trace.query(metric_id='scenario.nile_owner_response')['total'], 1)
            self.assertEqual(len(world['scenario_state']['strategic_projects']
                                 ['food_reports']), 1)
            self.assertGreater(verify(path)['rows'], 1)


if __name__ == '__main__':
    unittest.main()
