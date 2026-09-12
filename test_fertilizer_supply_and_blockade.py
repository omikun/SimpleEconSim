"""
test_fertilizer_supply_and_blockade.py — Tests for Physical Fertilizer Stocks,
Blockade Interception, Turnip Winter Harvest Shocks, Tech Tree, and Career Shifts.
"""

import unittest
from goods import Goods
from agent import Agent, initialize_agent
from region import Region
from nation import Nation
from army import MilitaryUnit
from innovation import TECH_CATALOG
import region_production as _prod
from externalities import step_tile_externalities, get_tile_metabolic_state
from imperialism import get_imperialism_manager
from demographics_career import learned_switch_choice


class DummyCtx:
    def __init__(self, source_region):
        self.source_region = source_region
        self.most_demand = Goods.food


class TestFertilizerSupplyAndBlockade(unittest.TestCase):

    def setUp(self):
        self.nation = Nation("Agraria")
        self.tile = Region("Pampa", 1)
        self.tile.owner_nation = self.nation
        self.nation.tiles = [self.tile]

    def test_tech_catalog_mineral_nitrates(self):
        self.assertIn('mineral_nitrates', TECH_CATALOG)
        tech = TECH_CATALOG['mineral_nitrates']
        self.assertEqual(tech.era, 3)
        self.assertIn('crop_rotation', tech.required_techs)

    def test_career_switch_famine_pressure(self):
        agent = Agent(1)
        initialize_agent(agent, Goods.wood, 0, 5, 20.0)

        # Baseline: not depleted
        self.tile.is_nitrate_depleted = False
        ctx = DummyCtx(self.tile)
        choices = [Goods.food, Goods.wood, Goods.furniture]
        weights = [1.0, 1.0, 1.0]

        # Depleted state: Turnip Winter famine
        self.tile.is_nitrate_depleted = True
        # Verify learned_switch_choice runs without error under famine pressure
        choice = learned_switch_choice(ctx, agent, choices, weights)
        self.assertIn(choice, choices)

    def test_fertilizer_consumption_and_harvest_bonus(self):
        self.tile.soil_fertility = 1.0
        self.tile.use_fertilizer = True
        self.tile.fertilizer_stock = 10.0

        # Calculate production multiplier for food
        mult = _prod.terrain_bonus(self.tile, Goods.food)

        # 1.0 (soil) * 1.75 (fertilizer) = 1.75
        self.assertAlmostEqual(mult, 1.75)
        # 1.0 consumed (no farm corporations)
        self.assertAlmostEqual(self.tile.fertilizer_stock, 9.0)
        self.assertAlmostEqual(self.tile.fertilizer_consumed_last_turn, 1.0)
        self.assertFalse(self.tile.is_nitrate_depleted)

    def test_turnip_winter_harvest_shock_on_depleted_soil(self):
        self.tile.soil_fertility = 0.50  # Depleted soil from monoculture
        self.tile.use_fertilizer = True
        self.tile.fertilizer_stock = 0.0  # Run out of fertilizer!

        mult = _prod.terrain_bonus(self.tile, Goods.food)

        # Harvest collapses by 50%: 0.50 (soil) * 0.50 (shock) = 0.25
        self.assertAlmostEqual(mult, 0.25)
        self.assertTrue(self.tile.is_nitrate_depleted)

    def test_naval_blockade_intercepts_maritime_nitrates(self):
        imp_mgr = get_imperialism_manager()
        self.tile.is_coast = True
        self.tile.fertilizer_stock = 10.0

        # Coastal tile with mineral nitrates tech receives +3.0 tons/turn
        self.nation.unlocked_techs = {'mineral_nitrates'}
        step_tile_externalities(self.tile, 1)
        self.assertAlmostEqual(self.tile.fertilizer_stock, 13.0)
        self.assertAlmostEqual(self.tile.fertilizer_inflow_last_turn, 3.0)

        # Now impose naval blockade
        enforcer = Nation("Britannia")
        unit = MilitaryUnit("u_brit_1", "Britannia", self.tile.name, soldiers=50)
        enforcer.military_units = [unit]
        world = {'turn': 2, 'tiles': [self.tile]}

        ok, msg = imp_mgr.impose_naval_blockade(enforcer, self.nation, self.tile, 2, world)
        self.assertTrue(ok)
        self.assertTrue(imp_mgr.is_tile_blockaded(self.tile.name))

        # Under blockade: maritime inflow drops to 0!
        prev_stock = self.tile.fertilizer_stock
        step_tile_externalities(self.tile, 3)
        self.assertAlmostEqual(self.tile.fertilizer_stock, prev_stock)
        self.assertAlmostEqual(self.tile.fertilizer_inflow_last_turn, 0.0)

        # Lift blockade
        imp_mgr.lift_blockade(self.tile.name, world, 4)

    def test_haber_bosch_synthesis_immunity(self):
        imp_mgr = get_imperialism_manager()
        self.tile.is_coast = True
        self.tile.fertilizer_stock = 5.0

        # Place tile under naval blockade
        imp_mgr.blockaded_tiles.add(self.tile.name)

        # Unlock Haber-Bosch synthetic_fertilizers and add industrial factory
        self.nation.unlocked_techs = {'synthetic_fertilizers'}
        ind_corp = Agent(10)
        ind_corp.is_corporation = True
        ind_corp.output = Goods.wood
        self.tile.agents = [ind_corp]

        step_tile_externalities(self.tile, 5)

        # Even under blockade, domestic synthesis generates +4.0 tons/turn!
        self.assertAlmostEqual(self.tile.fertilizer_inflow_last_turn, 4.0)
        self.assertAlmostEqual(self.tile.fertilizer_stock, 9.0)

        imp_mgr.blockaded_tiles.discard(self.tile.name)

    def test_blockade_runner_subsidy_and_conservation(self):
        from worldview_policies import _execute_policy_action

        self.tile.is_coast = True
        self.tile.fertilizer_stock = 0.0

        merchant = Agent(20)
        merchant.is_trader = True
        merchant.cash = 10.0
        self.tile.agents = [merchant]

        gov = self.nation.government.agent
        gov.cash = 250.0

        world = {'turn': 10, 'policy_feedback': None}
        _execute_policy_action(world, 'nat_subsidize_guano_import', self.nation)

        # $100 spent from treasury, transferred 1-for-1 to merchant
        self.assertAlmostEqual(gov.cash, 150.0)
        self.assertAlmostEqual(merchant.cash, 110.0)  # Conserved!
        # Coastal tile received +20.0 tons of emergency nitrates
        self.assertAlmostEqual(self.tile.fertilizer_stock, 20.0)


if __name__ == '__main__':
    unittest.main()
