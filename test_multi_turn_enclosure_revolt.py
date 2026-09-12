"""
test_multi_turn_enclosure_revolt.py — Verification of multi-turn stepped anti-enclosure revolts,
labor withholding, logistics/feeding, police capacity invariants, martyrdom backfire, and state terror chilling effect.
"""

import unittest
from region import Region
from nation import Nation
from land_tenure import TenureStatus, LandPlot
from popular_resistance import PopularResistanceManager, get_popular_resistance_manager
from goods import Goods
from agent import Agent


class TestMultiTurnEnclosureRevolt(unittest.TestCase):

    def setUp(self):
        self.mgr = PopularResistanceManager()

    def _setup_tile_with_enclosure(self, nation_name="Commonwealth", tile_name="Wessex"):
        nation = Nation(nation_name, initial_cash=200.0)
        tile = Region(tile_name, 0, 10)
        nation.add_tile(tile)

        # Create an enclosed plot held by a lord
        lord = Agent(0)
        lord.id = 999
        lord.is_lord = True
        lord.cash = 100.0
        tile.agents.append(lord)

        plot = LandPlot(
            plot_id=f"{tile_name}-plot-1",
            tile_name=tile_name,
            lord_id=lord.id,
            fraction=0.60,
            tenure=TenureStatus.ENCLOSED,
            rent_rate=5.0
        )
        tile.tenure.plots.clear()
        tile.tenure.add_plot(plot)

        # Add peasants (dispossessed, serfs, tenants)
        peasants = []
        for i in range(10):
            p = Agent(0)
            p.id = 100 + i
            p.social_class = "dispossessed"
            p.hungry_steps = 1
            p.cash = 10.0
            peasants.append(p)
            tile.agents.append(p)

        tile.unrest_level = 1.2

        world = {
            'turn': 1,
            'nations': [nation],
            'tiles': [tile],
            'ticker_events': []
        }
        return nation, tile, plot, peasants, world

    def test_natural_5_stage_progression_and_leveling(self):
        """Verify 5-turn escalation: Dormant -> Organizing -> Announced -> Marching -> Protest -> Leveling."""
        nation, tile, plot, peasants, world = self._setup_tile_with_enclosure()
        st = self.mgr.get_state(tile.name)
        self.assertEqual(st.enclosure_stage, "dormant")

        # Turn 1: Organizing triggered
        evs1 = self.mgr.evaluate_anti_enclosure_revolt(tile, t=1, world=world)
        self.assertEqual(len(evs1), 1)
        self.assertEqual(evs1[0]['kind'], 'ENCLOSURE_REVOLT_ORGANIZING')
        self.assertEqual(st.enclosure_stage, "organizing")
        self.assertTrue(len(st.revolt_participants) >= 2)
        # Check labor withholding
        for aid in st.revolt_participants:
            a = next(ag for ag in tile.agents if ag.id == aid)
            self.assertTrue(getattr(a, 'in_revolt', False))
            self.assertTrue(getattr(a, 'is_striking', False))

        # Turn 2: Announced
        evs2 = self.mgr.evaluate_anti_enclosure_revolt(tile, t=2, world=world)
        self.assertEqual(st.enclosure_stage, "announced")
        self.assertEqual(evs2[0]['kind'], 'ENCLOSURE_REVOLT_ANNOUNCED')

        # Turn 3: Marching (more peasants join column)
        count_before = len(st.revolt_participants)
        evs3 = self.mgr.evaluate_anti_enclosure_revolt(tile, t=3, world=world)
        self.assertEqual(st.enclosure_stage, "marching")
        self.assertEqual(evs3[0]['kind'], 'ENCLOSURE_REVOLT_MARCHING')
        self.assertTrue(len(st.revolt_participants) >= count_before)

        # Turn 4: Protest / Standoff at perimeter
        evs4 = self.mgr.evaluate_anti_enclosure_revolt(tile, t=4, world=world)
        self.assertEqual(st.enclosure_stage, "protest")
        self.assertEqual(evs4[0]['kind'], 'ENCLOSURE_REVOLT_PROTEST')

        # Turn 5: Leveling (violent fence tearing & restored commons)
        evs5 = self.mgr.evaluate_anti_enclosure_revolt(tile, t=5, world=world)
        self.assertEqual(evs5[0]['kind'], 'ANTI_ENCLOSURE_REVOLT')
        self.assertEqual(plot.tenure, TenureStatus.COMMONS, "Plot must revert to COMMONS")
        self.assertEqual(st.enclosure_stage, "dormant", "Revolt resets to dormant after leveling")
        self.assertEqual(len(st.revolt_participants), 0)

        # Labor withholding released
        for p in peasants:
            self.assertFalse(getattr(p, 'in_revolt', False))
            self.assertFalse(getattr(p, 'is_striking', False))

    def test_logistics_feeding_and_desperation_looting(self):
        """Verify marchers are fed by charity/sympathizers, or loot granary when starving."""
        nation, tile, plot, peasants, world = self._setup_tile_with_enclosure()
        st = self.mgr.get_state(tile.name)

        # Step into organizing
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=1, world=world)

        # Give tile charity some food
        tile.charity.food_inventory = 5
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=2, world=world)
        self.assertTrue(st.sympathizer_food_donated > 0, "Charity should disburse food to marchers")

        # Now starve marchers to trigger bread riot desperation looting
        tile.charity.food_inventory = 0
        tile.gov.food_inventory = 15  # Municipal granary
        for p in peasants:
            p.inventory[Goods.food.value] = 0
            p.hungry_steps = 2  # Acute starvation

        self.mgr.evaluate_anti_enclosure_revolt(tile, t=3, world=world)
        self.assertLess(tile.gov.food_inventory, 15, "Granary should be looted by starving marchers")

    def test_police_payroll_capacity_invariant(self):
        """Verify police cannot be mobilized if 0 constables on payroll and municipal treasury has no funds."""
        nation, tile, plot, peasants, world = self._setup_tile_with_enclosure()
        st = self.mgr.get_state(tile.name)

        # Step into marching
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=1, world=world)
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=2, world=world)
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=3, world=world)
        self.assertEqual(st.enclosure_stage, "marching")

        # City has 0 police and $0 cash in municipal treasury
        tile.police_officers = 0
        tile.gov.agent.cash = 0.0

        ok, msg, data = self.mgr.interdict_enclosure_revolt(tile, t=3, world=world)
        self.assertFalse(ok, "Police interdiction must fail without payroll capacity")
        self.assertIn("no constables on payroll", msg)

    def test_violent_clash_martyrdom_effect(self):
        """Verify moderate police clash kills marchers, pushes mem_casualties, and escalates future turnout."""
        nation, tile, plot, peasants, world = self._setup_tile_with_enclosure()
        st = self.mgr.get_state(tile.name)

        # Step into marching
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=1, world=world)
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=2, world=world)
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=3, world=world)

        # State funds constables
        tile.police_officers = 4
        tile.gov.agent.cash = 100.0

        multiplier_before = st.martyrdom_multiplier
        ok, msg, data = self.mgr.interdict_enclosure_revolt(tile, t=3, world=world)
        self.assertTrue(ok)
        self.assertEqual(data['outcome'], 'martyrdom')
        self.assertGreater(data['casualties'], 0)

        # Verify martyrdom multiplier increased
        self.assertGreater(st.martyrdom_multiplier, multiplier_before)
        self.assertEqual(st.enclosure_stage, "dormant")

        # Verify survivors received mem_casualties
        living_peasants = [p for p in peasants if p.alive]
        has_casualty_memory = any('mem_casualties' in p.memory for p in living_peasants)
        self.assertTrue(has_casualty_memory, "Survivors must store mem_casualties from police killings")

    def test_overwhelming_brutality_state_terror_chilling_effect(self):
        """Verify army intervention crushes revolt, imposes 10-turn terror cooldown, and damages legitimacy."""
        nation, tile, plot, peasants, world = self._setup_tile_with_enclosure()
        st = self.mgr.get_state(tile.name)

        # Step into marching
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=1, world=world)
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=2, world=world)
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=3, world=world)

        # Deploy 10 standing soldiers (military garrison)
        from army import MilitaryUnit
        unit = MilitaryUnit("ImperialInfantry", nation_name=nation.name, region_name=tile.name, soldiers=10)
        tile.military_units = [unit]
        nation.military_units = [unit]

        legitimacy_before = nation.legitimacy
        ok, msg, data = self.mgr.interdict_enclosure_revolt(tile, t=3, world=world)
        self.assertTrue(ok)
        self.assertEqual(data['outcome'], 'terror')
        self.assertEqual(st.terror_cooldown, 10, "10-turn terror cooldown must be active")
        self.assertLess(nation.legitimacy, legitimacy_before, "State legitimacy must drop from state terror")

        # During terror cooldown, new revolts cannot organize
        tile.unrest_level = 5.0
        evs_blocked = self.mgr.evaluate_anti_enclosure_revolt(tile, t=4, world=world)
        self.assertEqual(len(evs_blocked), 0, "No revolts can organize during terror cooldown")
        self.assertEqual(st.terror_cooldown, 9)

    def test_peaceful_dissolution_when_commons_restored(self):
        """Verify peasant march dissolves peacefully if the government legally restores the plot to commons."""
        nation, tile, plot, peasants, world = self._setup_tile_with_enclosure()
        st = self.mgr.get_state(tile.name)

        # Step into marching
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=1, world=world)
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=2, world=world)
        self.mgr.evaluate_anti_enclosure_revolt(tile, t=3, world=world)
        self.assertEqual(st.enclosure_stage, "marching")

        # Government peacefully restores plot to commons
        tile.tenure.revert_plot_to_commons(plot.plot_id, turn=3)

        # Next evaluation sees grievance resolved and peacefully dissolves
        evs = self.mgr.evaluate_anti_enclosure_revolt(tile, t=4, world=world)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]['kind'], 'ENCLOSURE_REVOLT_DISSOLVED_PEACEFUL')
        self.assertEqual(st.enclosure_stage, "dormant")


if __name__ == '__main__':
    unittest.main()
