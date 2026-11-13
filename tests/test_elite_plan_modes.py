import argparse
import pickle
import unittest
from dataclasses import replace
from world_config import ElitePlanningConfig, add_elite_planning_arguments, elite_planning_config_from_args
from economy.capitalist_planner import EliteCapitalistPlanner
from economy.elite_plan_execution import review_plan, prepare_turn
from tests.elite_plan_fixture import firm_fixture


class PlanningModeTests(unittest.TestCase):
    def test_config_validated_in_central_file_and_cli(self):
        for bad in ({'mode':'other'}, {'max_states':0}, {'horizon':True}):
            with self.assertRaises(ValueError): ElitePlanningConfig(**bad)
        parser = argparse.ArgumentParser()
        add_elite_planning_arguments(parser)
        self.assertEqual(elite_planning_config_from_args(parser.parse_args([])), ElitePlanningConfig())
        self.assertEqual(elite_planning_config_from_args(parser.parse_args(['--elite-planning-mode','shadow'])).mode, 'shadow')

    def test_shadow_is_read_only_and_parent_gate_wins(self):
        from random_cache import rand
        import abundance, game_time
        r, firm, *_ = firm_fixture()
        r._elite_planning_config = ElitePlanningConfig(mode='shadow')
        planner = EliteCapitalistPlanner()
        from simulation_semantics import canonical_state, graph_differences
        before = canonical_state([r], [], extra={'planner': planner})
        review_plan(planner, firm, r, 1)
        after = canonical_state([r], [], extra={'planner': planner})
        self.assertFalse(graph_differences(before['graph'], after['graph']))
        self.assertLessEqual(r._trace_elite_budget['expanded'], 200)
        r._gameplay_flags = replace(r._gameplay_flags, elite_planning=False)
        del r._trace_elite_budget
        review_plan(planner, firm, r, 2)
        self.assertFalse(hasattr(r, '_trace_elite_budget'))

    def test_world_budget_rotates_and_is_never_exceeded(self):
        regions = [firm_fixture()[0] for _ in range(4)]
        for i, r in enumerate(regions): r.name = str(i)
        settings = ElitePlanningConfig(mode='active', max_states=2, world_max_states=3)
        prepare_turn(regions, 1, settings)
        first = regions[0]._elite_planning_budget
        self.assertEqual(sum(first['allocations'].values()), 3)
        prepare_turn(regions, 2, settings)
        second = regions[0]._elite_planning_budget
        self.assertNotEqual(first['allocations'], second['allocations'])
