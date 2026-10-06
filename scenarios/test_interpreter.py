"""Unit tests for the generic scenario framework, evaluator, and template interpreter."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from scenarios.effects import apply_declarative_effects
from scenarios.evaluator import evaluate_condition, evaluate_metric
from scenarios.interpreter import ScenarioInterpreter
from scenarios.schema import load_scenario_spec


class MockAgent:
    def __init__(self, cash=500.0):
        self.cash = float(cash)
        self.alive = True
        self.is_government = False
        self.is_corporation = False
        self.is_trader = False
        self.hungry_steps = 0
        self.inventory = {}

    def inv_add(self, item, qty):
        self.inventory[item] = self.inventory.get(item, 0) + qty


class MockGovernment:
    def __init__(self, cash=500.0, food=120):
        self.agent = MockAgent(cash=cash)
        self.agent.is_government = True
        self.food_inventory = food


class MockTile:
    def __init__(self, name="Tile1", agents=None):
        self.name = name
        self.agents = agents or []
        self.unrest_level = 0.0
        self.food_export_fraction = 1.0
        self.protest_energy_log = [1.5]
        self.gov = SimpleNamespace(tax_rate=0.20)


class MockNation:
    def __init__(self, name, cash=500.0, food=120):
        self.name = name
        self.government = MockGovernment(cash=cash, food=food)
        self.legitimacy = 0.50
        self.tiles = [MockTile(f"{name}_Tile", [MockAgent(cash=10.0), MockAgent(cash=5.0)])]


def create_test_world():
    player = MockNation("Egypt", cash=600.0, food=120)
    creditor1 = MockNation("Britain", cash=400.0)
    creditor2 = MockNation("France", cash=400.0)
    return {
        'turn': 1,
        'player_nation_name': 'Egypt',
        'nations': [player, creditor1, creditor2],
        'scenario_state': {},
    }


class ScenarioFrameworkTests(unittest.TestCase):

    def test_expression_evaluator(self):
        ctx = {
            'turn': 6,
            'cash': 250.0,
            'debt': {'status': 'unpaid', 'amount': 200.0},
            'legitimacy': 0.65,
        }
        self.assertTrue(evaluate_condition("turn >= 6 and debt.status == 'unpaid'", ctx))
        self.assertTrue(evaluate_condition("cash >= debt.amount", ctx))
        self.assertFalse(evaluate_condition("legitimacy < 0.50", ctx))
        self.assertEqual(evaluate_metric("cash - debt.amount", ctx), 50.0)

    def test_load_specs(self):
        templates_dir = Path(__file__).parent / 'templates'
        egypt_path = templates_dir / 'egypt_1877.scenario.json'
        venezuela_path = templates_dir / 'venezuela_1902.scenario.json'

        self.assertTrue(egypt_path.exists())
        self.assertTrue(venezuela_path.exists())

        egypt_spec = load_scenario_spec(egypt_path)
        self.assertEqual(egypt_spec.id, 'egypt_1877')
        self.assertIn('debt', egypt_spec.modules)
        self.assertGreater(len(egypt_spec.actions), 5)

        venezuela_spec = load_scenario_spec(venezuela_path)
        self.assertEqual(venezuela_spec.id, 'venezuela_1902')
        self.assertEqual(venezuela_spec.meta['year'], 1902)

    def test_effect_cash_conservation(self):
        world = create_test_world()
        player = world['nations'][0]
        creditor = world['nations'][1]
        context = {
            'player_nation': player,
            'creditor_nations': [creditor],
        }

        total_cash_before = player.government.agent.cash + creditor.government.agent.cash
        ok, msg = apply_declarative_effects(world, {'treasury_cost': 150.0}, context)
        self.assertTrue(ok)
        total_cash_after = player.government.agent.cash + creditor.government.agent.cash
        self.assertEqual(total_cash_before, total_cash_after)
        self.assertEqual(player.government.agent.cash, 450.0)
        self.assertEqual(creditor.government.agent.cash, 550.0)

    def test_interpreter_lifecycle_and_actions(self):
        templates_dir = Path(__file__).parent / 'templates'
        interpreter = ScenarioInterpreter.from_file(templates_dir / 'egypt_1877.scenario.json')

        world = create_test_world()
        interpreter.initialize_scenario(world)

        state = world['scenario_state']
        self.assertEqual(state['scenario_id'], 'egypt_1877')
        self.assertEqual(state['payment_status'], 'upcoming')

        # Test actions discovery
        actions = interpreter.get_available_actions(world)
        self.assertTrue(any(a['id'] == 'release_maize' and a['enabled'] for a in actions))

        # Apply maize release
        ok, feedback = interpreter.apply_action(world, 'release_maize')
        self.assertTrue(ok)
        self.assertEqual(state['last_action_turn'], 1)

        # Cannot apply second major action on same turn
        ok2, _ = interpreter.apply_action(world, 'reduce_fellahin_tax')
        self.assertFalse(ok2)

        # Advance turn to 2
        world['turn'] = 2
        news = []
        interpreter.advance_turn(world, 2, ticker_push=lambda w, t, k, text, c: news.append(text))
        # Delayed reaction for release_maize fires on turn 2
        self.assertTrue(any("emergency maize relief" in msg for msg in news))

        # Check pressures evaluation
        pressures = interpreter.evaluate_pressures(world)
        self.assertEqual(len(pressures), 3)
        self.assertIn("maize", pressures[0]['title'].lower())

    def test_branching_modal_reaction(self):
        templates_dir = Path(__file__).parent / 'templates'
        interpreter = ScenarioInterpreter.from_file(templates_dir / 'egypt_1877.scenario.json')

        world = create_test_world()
        interpreter.initialize_scenario(world)

        # Action with interactive reaction responses
        ok, _ = interpreter.apply_action(world, 'prioritize_domestic_grain')
        self.assertTrue(ok)

        # Step to turn 2 to trigger the delayed demand
        world['turn'] = 2
        interpreter.advance_turn(world, 2)

        # Game must pause with interactive modal
        self.assertFalse(world.get('playing', True))
        self.assertEqual(world.get('scenario_warning_modal', {}).get('kind'), 'creditor_reaction')

        # Player chooses response
        ok_resp, msg_resp = interpreter.resolve_reaction_response(world, 'defend_food_priority')
        self.assertTrue(ok_resp)
        self.assertIsNone(world.get('scenario_warning_modal'))

    def test_venezuela_playthrough_and_outcome(self):
        templates_dir = Path(__file__).parent / 'templates'
        interpreter = ScenarioInterpreter.from_file(templates_dir / 'venezuela_1902.scenario.json')

        venezuela = MockNation("Venezuela", cash=300.0)
        britain = MockNation("Britain", cash=500.0)
        germany = MockNation("Germany", cash=500.0)
        world = {
            'turn': 1,
            'player_nation_name': 'Venezuela',
            'nations': [venezuela, britain, germany],
            'scenario_state': {},
        }

        interpreter.initialize_scenario(world)
        state = world['scenario_state']
        self.assertEqual(state['scenario_id'], 'venezuela_1902')

        # Turn 1: Appeal US arbitration
        ok, feedback = interpreter.apply_action(world, 'appeal_us_arbitration')
        self.assertTrue(ok)

        # Turn 2: Advance turn, Washington Hague proposal arrives
        world['turn'] = 2
        interpreter.advance_turn(world, 2)
        self.assertEqual(world.get('scenario_warning_modal', {}).get('kind'), 'creditor_reaction')

        # Accept Hague arbitration
        ok_resp, _ = interpreter.resolve_reaction_response(world, 'accept_hague_terms')
        self.assertTrue(ok_resp)
        self.assertEqual(state['payment_status'], 'restructured')

        # Advance to check outcome
        interpreter.advance_turn(world, 2)
        self.assertEqual(state.get('ending'), 'hague_arbitration')
        self.assertIn('Hague', state.get('debrief', {}).get('title', ''))


if __name__ == '__main__':
    unittest.main()
