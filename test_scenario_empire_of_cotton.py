"""
test_scenario_empire_of_cotton.py — Unit & Integration Tests for JSON-Driven Empire of Cotton Scenario.
"""

from __future__ import annotations
import unittest
from pathlib import Path

from scenarios.schema import load_scenario_spec
from scenarios.interpreter import ScenarioInterpreter
from scenario_empire_of_cotton import (
    TEMPLATE_PATH,
    get_empire_of_cotton_interpreter,
    create_empire_of_cotton_world,
    step_empire_of_cotton_turn,
    run_headless_playthrough,
)
from goods import Goods


class TestScenarioEmpireOfCotton(unittest.TestCase):

    def test_01_spec_loading_and_validation(self):
        """Verify scenario JSON specification conforms to regnum.scenario.v2."""
        self.assertTrue(TEMPLATE_PATH.exists(), f"Template not found at {TEMPLATE_PATH}")
        spec = load_scenario_spec(TEMPLATE_PATH)

        self.assertEqual(spec.id, 'empire_of_cotton')
        self.assertEqual(spec.format, 'regnum.scenario.v2')
        self.assertEqual(spec.meta['year'], 1780)
        self.assertIn('capitalism', spec.modules)
        self.assertEqual(len(spec.pressures), 3)
        self.assertGreaterEqual(len(spec.actions), 6)
        self.assertGreaterEqual(len(spec.branches), 2)
        self.assertGreaterEqual(len(spec.outcomes), 3)

    def test_02_world_creation_and_initialization(self):
        """Verify world generation, role binding, and scenario state initialization."""
        world = create_empire_of_cotton_world(seed=42)
        self.assertEqual(world['player_nation_name'], 'Lancashire_Metropole')
        self.assertGreaterEqual(len(world['nations']), 2)
        self.assertGreaterEqual(len(world['wilderness_tiles']), 1)

        interpreter = get_empire_of_cotton_interpreter()
        interpreter.initialize_scenario(world)

        state = world['scenario_state']
        self.assertEqual(state['scenario_id'], 'empire_of_cotton')
        self.assertTrue(state.get('capitalism_enabled'))
        self.assertGreaterEqual(state.get('cotton_reserves', 0), 20)
        self.assertEqual(state.get('credit_leverage'), 1.00)

    def test_03_pressures_evaluation(self):
        """Verify the 3 headline pressures evaluate and format accurately."""
        world = create_empire_of_cotton_world(seed=42)
        interpreter = get_empire_of_cotton_interpreter()
        interpreter.initialize_scenario(world)

        pressures = interpreter.evaluate_pressures(world)
        self.assertEqual(len(pressures), 3)

        p_cotton = next(p for p in pressures if p['id'] == 'cotton_inventory')
        self.assertIn("reserve", p_cotton['display'])

        p_labor = next(p for p in pressures if p['id'] == 'labor_unrest')
        self.assertIn("%", p_labor['display'])

        p_credit = next(p for p in pressures if p['id'] == 'credit_leverage')
        self.assertIn("x", p_credit['display'])

    def test_04_action_execution_and_effects(self):
        """Verify actions: steam mill, enclosure, bills of exchange, and wage caps."""
        world = create_empire_of_cotton_world(seed=42)
        interpreter = get_empire_of_cotton_interpreter()
        interpreter.initialize_scenario(world)

        player = world['nations'][0]
        init_gov_cash = player.government.agent.cash

        # 1. Incorporate Steam Mill ($60 treasury cost)
        ok_mill, msg_mill = interpreter.apply_action(world, 'incorporate_steam_mill')
        self.assertTrue(ok_mill, f"Failed steam mill: {msg_mill}")
        self.assertEqual(player.government.agent.cash, init_gov_cash - 60.0)

        capital_tile = player.tiles[0]
        firms = [a for a in capital_tile.agents if getattr(a, 'is_corporation', False)]
        self.assertGreaterEqual(len(firms), 1)
        self.assertEqual(firms[0].output, Goods.cloth)
        self.assertEqual(firms[0].machinery_level, 1)

        # 2. Advance to turn 2
        world['turn'] = 2
        interpreter.advance_turn(world, 2)

        # 3. Issue Merchant Bills (0 cash cost, creates elastic credit)
        ok_bill, msg_bill = interpreter.apply_action(world, 'issue_merchant_bills')
        self.assertTrue(ok_bill, f"Failed bill issue: {msg_bill}")
        credit_mgr = world['scenario_state']['credit_manager_ref']
        self.assertGreaterEqual(len(credit_mgr.active_bills), 1)

        # 4. Advance to turn 3
        world['turn'] = 3
        interpreter.advance_turn(world, 3)

        # 5. Enact Statute of Laborers Wage Cap
        ok_wage, msg_wage = interpreter.apply_action(world, 'enforce_wage_suppression_decree')
        self.assertTrue(ok_wage, f"Failed wage cap: {msg_wage}")
        self.assertTrue(capital_tile.statute_of_laborers)
        self.assertLessEqual(firms[0].wage, 1.50)

    def test_05_branching_reactions_and_warning_modals(self):
        """Verify delayed reaction branching and warning modal resolution."""
        world = create_empire_of_cotton_world(seed=42)
        interpreter = get_empire_of_cotton_interpreter()
        interpreter.initialize_scenario(world)

        # Launch frontier expedition on turn 1
        ok_exp, _ = interpreter.apply_action(world, 'launch_frontier_expedition')
        self.assertTrue(ok_exp)

        # Step to turn 2 (1-turn delay for frontier reaction)
        world['turn'] = 2
        interpreter.advance_turn(world, 2)

        # Interactive modal should pause gameplay
        modal = world.get('scenario_warning_modal')
        self.assertIsNotNone(modal)
        self.assertIn("Colonial Frontier", modal.get('headline', ''))
        self.assertGreaterEqual(len(modal.get('responses', [])), 1)

        # Resolve modal
        resp_id = modal['responses'][0]['id']
        ok_resp, _ = interpreter.resolve_reaction_response(world, resp_id)
        self.assertTrue(ok_resp)
        self.assertIsNone(world.get('scenario_warning_modal'))

    def test_06_multi_turn_playthrough_and_outcome(self):
        """Verify full multi-turn headless playthrough and historical outcome achievement."""
        res = run_headless_playthrough(turns=6, seed=42)
        self.assertGreaterEqual(res['turns_run'], 4)
        self.assertIsNotNone(res['final_state'])

        final_state = res['final_state']
        self.assertTrue(final_state.get('capitalism_enabled'))
        self.assertGreaterEqual(final_state.get('active_mills_count', 0), 1)
        self.assertGreaterEqual(final_state.get('cotton_reserves', 0), 15)

        # Outcome check
        outcome = res.get('final_outcome')
        if outcome:
            self.assertIn(outcome['id'], ('industrial_hegemony', 'historical_status_quo'))


    def test_07_conditional_merchant_fiber_reaction(self):
        """Verify conditional merchant reaction: trade boom when abundant, bottleneck modal when scarce."""
        # 1. Case A: Abundant cotton (reserves >= 20) -> Fallback reaction (Trade boom, no blocking modal)
        world_a = create_empire_of_cotton_world(seed=101)
        interp_a = get_empire_of_cotton_interpreter()
        interp_a.initialize_scenario(world_a)
        
        ok_mill, _ = interp_a.apply_action(world_a, 'incorporate_steam_mill')
        self.assertTrue(ok_mill)
        self.assertGreaterEqual(world_a['scenario_state'].get('cotton_reserves', 0), 20)

        # Advance 2 turns to trigger reaction
        world_a['turn'] = 2
        interp_a.advance_turn(world_a, 2)
        world_a['turn'] = 3
        interp_a.advance_turn(world_a, 3)

        # Should NOT halt with a warning modal; merchants celebrate trade boom
        self.assertIsNone(world_a.get('scenario_warning_modal'))
        self.assertIn("Commercial Trade Boom", world_a.get('scenario_feedback', ''))

        # 2. Case B: Scarce cotton (reserves < 20) -> Condition met, triggers Fiber Bottleneck modal
        world_b = create_empire_of_cotton_world(seed=202)
        interp_b = get_empire_of_cotton_interpreter()
        interp_b.initialize_scenario(world_b)
        
        ok_mill_b, _ = interp_b.apply_action(world_b, 'incorporate_steam_mill')
        self.assertTrue(ok_mill_b)

        # Advance to turn 2
        world_b['turn'] = 2
        interp_b.advance_turn(world_b, 2)

        # Draw down raw fiber below threshold prior to reaction evaluation at turn 3
        for t in world_b['nations'][0].tiles:
            for a in t.agents:
                a.inv_set(Goods.cotton, 0)
        world_b['scenario_state']['cotton_reserves'] = 0

        # Advance to turn 3 (2-turn delay matured)
        world_b['turn'] = 3
        interp_b.advance_turn(world_b, 3)

        # Must halt with interactive warning modal
        modal_b = world_b.get('scenario_warning_modal')
        self.assertIsNotNone(modal_b)
        self.assertIn("Fiber Bottleneck", modal_b.get('headline', ''))

        # Resolve by underwriting transatlantic credit line ($15 cost -> +15 cotton)
        init_gov_cash = world_b['nations'][0].government.agent.cash
        ok_res, _ = interp_b.resolve_reaction_response(world_b, 'guarantee_transatlantic_credit')
        self.assertTrue(ok_res)
        self.assertIsNone(world_b.get('scenario_warning_modal'))
        self.assertEqual(world_b['nations'][0].government.agent.cash, init_gov_cash - 15.0)
        self.assertGreaterEqual(world_b['scenario_state'].get('cotton_reserves', 0), 15)


if __name__ == '__main__':
    unittest.main()
