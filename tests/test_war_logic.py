"""Deterministic decisions around war aims, supply, peace and political shocks."""

import unittest
from types import SimpleNamespace

from ai_nation import NationPolicyAI
from diplomacy import DiplomacySystem
from intents import MoveArmyIntent, ProposePeaceIntent, RespondPeaceIntent
from war_logic import (WarAim, aim_secured, apply_political_shocks,
                       attack_forecasts, update_wars)


class Tile:
    def __init__(self, name):
        self.name = name
        self.neighbors = {}
        self.owner_nation = None


class Nation:
    def __init__(self, name, tile, soldiers, cash=100, food=100):
        self.name = name
        self.tiles = [tile]
        tile.owner_nation = self
        self.military_units = [SimpleNamespace(
            unit_id=name, region_name=tile.name, soldiers=soldiers,
            strength=float(soldiers), wage_per_soldier=1.0,
            food_per_soldier=0.1, morale=1.0, is_garrison=False)]
        self.cash = cash
        self.government = SimpleNamespace(food_inventory=food)
        self.legitimacy = 0.6
        self.regime_type = 'autocracy'
        self.ruling_faction = name
        self.regime_log = []
        self.intents = []
        self.ai = NationPolicyAI(self)

    def treasury(self):
        return {'total': self.cash}

    def submit_intent(self, intent, t):
        self.intents.append(intent)


class WarLogicTest(unittest.TestCase):
    def setUp(self):
        a, b = Tile('A'), Tile('B')
        a.neighbors[b.name] = b
        b.neighbors[a.name] = a
        self.alpha = Nation('Alpha', a, 30)
        self.beta = Nation('Beta', b, 5)
        self.dip = DiplomacySystem()
        self.dip.declare_war('Alpha', 'Beta', t=1,
                             aim=WarAim('border_tile', 'B'),
                             nations={'Alpha': self.alpha, 'Beta': self.beta})
        self.war = self.dip.get_war('Alpha', 'Beta')

    def test_supplied_offensive_attacks_then_banks_limited_victory(self):
        side = self.war.sides['Alpha']
        self.assertGreater(attack_forecasts(self.alpha, self.beta, side)[0]['progress'],
                           attack_forecasts(self.alpha, self.beta, side)[0]['cost'])
        order = self.alpha.ai.choose_war_intent(self.war, self.beta, t=2)
        self.assertIsInstance(order, MoveArmyIntent)
        captured = self.beta.tiles.pop()
        captured.owner_nation = self.alpha
        self.alpha.tiles.append(captured)
        self.assertTrue(aim_secured(self.alpha, self.beta, side))
        self.assertIsInstance(self.alpha.ai.choose_war_intent(self.war, self.beta, t=3),
                              ProposePeaceIntent)

    def test_supply_failure_culminates_offensive(self):
        self.alpha.government.food_inventory = 0
        update_wars(self.dip, [self.alpha, self.beta], turn=1)
        self.assertEqual(self.war.sides['Alpha'].posture, 'culminated')
        self.assertIsInstance(self.alpha.ai.choose_war_intent(self.war, self.beta, t=2),
                              ProposePeaceIntent)

    def test_peace_needs_a_reply_on_later_turn(self):
        self.assertTrue(self.dip.propose_peace('Alpha', 'Beta', t=2)['success'])
        self.assertFalse(self.dip.respond_peace('Beta', 'Alpha', True, t=2)['success'])
        self.assertTrue(self.dip.are_at_war('Alpha', 'Beta'))
        self.assertTrue(self.dip.respond_peace('Beta', 'Alpha', True, t=3)['success'])
        self.assertFalse(self.dip.are_at_war('Alpha', 'Beta'))
        self.assertIsNone(self.dip.get_war('Alpha', 'Beta'))

    def test_regime_change_aim_reduces_early_peace_acceptance(self):
        self.alpha.government.food_inventory = 0
        self.war.sides['Alpha'].aims = [WarAim('regime_change')]
        self.assertFalse(self.alpha.ai.evaluate_peace_offer(self.war, self.beta))
        self.war.sides['Alpha'].aims = [WarAim('border_tile', 'B')]
        self.assertTrue(self.alpha.ai.evaluate_peace_offer(self.war, self.beta))

    def test_major_loss_can_trigger_one_political_shock(self):
        self.alpha.legitimacy = 0.25
        self.dip.record_battle('Beta', 'Alpha', 0, 20)
        update_wars(self.dip, [self.alpha, self.beta], turn=2)
        side = self.war.sides['Alpha']
        self.assertGreater(side.pending_political_shock, 0)
        before = self.alpha.legitimacy
        apply_political_shocks(self.dip, self.alpha, turn=3)
        self.assertLess(self.alpha.legitimacy, before)
        self.assertEqual(side.pending_political_shock, 0)
        apply_political_shocks(self.dip, self.alpha, turn=3)
        self.assertEqual(len(self.alpha.regime_log), 1)

    def test_shared_battle_secures_border_aim_and_changes_next_order(self):
        from army import recruit_unit
        from goods import Goods
        from nation import Nation as GameNation
        from region import Region
        import diplomacy

        diplomacy.diplomacy_instance = DiplomacySystem()
        dip = diplomacy.get_diplomacy()
        a = GameNation('BattleA', initial_cash=300, register=False)
        b = GameNation('BattleB', initial_cash=300, register=False)
        ta = Region('BattleA1', t=0, number_of_agents=40,
                    profession_distribution={Goods.food: 0.8, Goods.wood: 0.2})
        tb = Region('BattleB1', t=0, number_of_agents=40,
                    profession_distribution={Goods.food: 0.8, Goods.wood: 0.2})
        a.add_tile(ta)
        b.add_tile(tb)
        ta.add_neighbor(tb)
        tb.add_neighbor(ta)
        self.assertIsNotNone(recruit_unit(a, ta, 20, t=1))
        self.assertIsNotNone(recruit_unit(b, tb, 5, t=1))
        a.government.food_inventory = 100
        b.government.food_inventory = 100
        dip.declare_war(a.name, b.name, t=1, aim=WarAim('border_tile', tb.name),
                        nations={a.name: a, b.name: b})
        ai = NationPolicyAI(a)
        war = dip.get_war(a.name, b.name)
        order = ai.choose_war_intent(war, b, t=2)
        self.assertIsInstance(order, MoveArmyIntent)
        ok, _ = order.execute({ta.name: ta, tb.name: tb}, {a.name: a, b.name: b}, t=2)
        self.assertTrue(ok)
        self.assertIn(tb, a.tiles)
        update_wars(dip, [a, b], turn=2)
        self.assertIsInstance(ai.choose_war_intent(war, b, t=3), ProposePeaceIntent)


if __name__ == '__main__':
    unittest.main()
