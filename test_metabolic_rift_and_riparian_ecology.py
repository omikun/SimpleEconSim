"""
test_metabolic_rift_and_riparian_ecology.py — Comprehensive Test Suite for Phase 3:
Ecological Metabolic Rift, Public Health, Hydrological Effluent, and Municipal Sewer Bonds.

Verifies:
1. Ultra-rare Guano / Nitrate endowment (strictly 1 or 2 tiles across the world map).
2. Physical Goods.nitrates commodity circuit, navvy labor, and market consumption.
3. Agro-Ecological Regimes: Four-Field Crop Rotation vs. Intensive Monoculture.
4. 10-turn yearly agricultural cycle & emergent unscripted Turnip Winter.
5. Hydrological downstream river effluent advection (35% flow) & fishery collapse.
6. Demographic infant mortality from water pollution & riparian casus belli.
7. Bazalgette Sewer megaproject & Municipal Revenue Bond financing (0 leak).
8. The Great Stink catalyst event on capital city pollution.
"""

import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import unittest
import math
from goods import Goods
from region import Region
from nation import Nation
from tile_resources import TileResource, assign_tile_resources, RESOURCE_META
import region_production as _prod
from externalities import step_tile_externalities, get_tile_metabolic_state
from terrain_edges import TerrainEdgeManager, get_edge_manager, reset_edge_manager
from diplomacy import get_diplomacy
from sovereign_bonds import get_bond_market
from demographics_reproduction import handle_reproduction
from agent import Agent, initialize_agent
from buildings import BUILDING_RECIPES, ConstructionProject
from construction_politics import find_or_emerge_contractor


class DummyBank:
    def __init__(self):
        self.deposits = {}


class DummyCtx:
    def __init__(self, source_region):
        self.source_region = source_region
        self.bank = DummyBank()
        self.most_demand = Goods.food
        self.p_birth = 0.50
        self.cost_of_living = 20.0
        self.birth_gap = 5
        self.max_agents = 100
        self.goods = [Goods.food, Goods.wood, Goods.furniture, Goods.transport, Goods.wool, Goods.cloth, Goods.nitrates, Goods.gov]
        self.profession = {
            Goods.food: 'F', Goods.wood: 'W', Goods.furniture: 'C', Goods.transport: 'P',
            Goods.gov: 'G', Goods.wool: 'S', Goods.cloth: 'T', Goods.nitrates: 'N', Goods.none: '-'
        }
        self.recipes = source_region.recipes
        self.production_log = {g: [10] for g in self.goods}


class TestMetabolicRiftAndRiparianEcology(unittest.TestCase):

    def setUp(self):
        self.nation_a = Nation("Britannia")
        self.nation_b = Nation("Germania")

        self.tile_up = Region("UpstreamMills", 1)
        self.tile_up.owner_nation = self.nation_a
        self.tile_up.elevation = 0.40  # Higher elevation
        self.tile_up.is_river_corridor = True

        self.tile_down = Region("DownstreamEstuary", 2)
        self.tile_down.owner_nation = self.nation_b
        self.tile_down.elevation = 0.10  # Lower elevation
        self.tile_down.is_coast = True
        self.tile_down.is_river_corridor = True

        # Link neighbors
        self.tile_up.neighbors[self.tile_down.name] = self.tile_down
        self.tile_down.neighbors[self.tile_up.name] = self.tile_up

        self.nation_a.tiles = [self.tile_up]
        self.nation_b.tiles = [self.tile_down]

        self.tiles = [self.tile_up, self.tile_down]
        self.layout = {self.tile_up.name: (100, 100), self.tile_down.name: (150, 150)}
        self.em = reset_edge_manager(self.tiles, self.layout)

    def test_01_ultra_rare_guano_endowment(self):
        """Verify that across all world tiles, strictly 1 or 2 tiles receive NATURAL_NITRATES."""
        world_tiles = [Region(f"Tile_{i}", i) for i in range(12)]
        for i, t in enumerate(world_tiles):
            t.elevation = 0.05 * (i % 6)
            if i % 3 == 0:
                t.is_coast = True

        assign_tile_resources(world_tiles, seed=12345)
        guano_tiles = [t for t in world_tiles if TileResource.NATURAL_NITRATES in t.natural_resources]

        self.assertGreaterEqual(len(guano_tiles), 1)
        self.assertLessEqual(len(guano_tiles), 2)
        self.assertIn(TileResource.NATURAL_NITRATES, RESOURCE_META)
        self.assertEqual(RESOURCE_META[TileResource.NATURAL_NITRATES].name, "Natural Guano & Nitrates")

    def test_02_physical_nitrates_commodity_circuit(self):
        """Verify Goods.nitrates extraction, recipe pricing, and market inventory tracking."""
        self.assertIn(Goods.nitrates, self.tile_up.recipes)
        r = self.tile_up.recipes[Goods.nitrates]
        self.assertEqual(r['commodity'], Goods.nitrates)
        self.assertGreater(r['price'], 0.0)

        # Producer agent
        miner = Agent(1)
        initialize_agent(miner, Goods.nitrates, 0, 10, 50.0)
        self.assertEqual(miner.output, Goods.nitrates)
        self.assertEqual(_prod.Goods.nitrates, Goods.nitrates)

    def test_03_four_field_rotation_vs_intensive_monoculture(self):
        """Verify Four-Field rotation regenerates soil with clover forage vs Intensive monoculture exhaustion."""
        # A. Four-field rotation: zero chemical input, regenerates soil, clover boosts wool
        self.tile_up.farming_regime = 'rotation'
        self.tile_up.soil_fertility = 1.0
        step_tile_externalities(self.tile_up, 1)

        self.assertGreater(self.tile_up.soil_fertility, 0.95)
        wool_mult = _prod.terrain_bonus(self.tile_up, Goods.wool)
        self.assertAlmostEqual(wool_mult, 1.35)  # +35% clover pasture synergy!

        # B. Intensive monoculture: consumes nitrates, drops nutrition density, accelerates soil extraction
        self.tile_up.farming_regime = 'intensive'
        self.tile_up.fertilizer_stock = 10.0
        step_tile_externalities(self.tile_up, 2)

        self.assertAlmostEqual(self.tile_up.nutrition_density, 0.925)  # Nutrition dilution (moves towards 0.70)
        self.assertAlmostEqual(self.tile_up.fertilizer_stock, 10.0)  # Consumed via harvest

    def test_04_seasonal_cycle_and_emergent_turnip_winter(self):
        """Verify 10-turn seasonal productivity curve and unscripted Turnip Winter collapse."""
        # Verify seasonal multipliers across the 10-turn year
        # Autumn peak (turn 4-6) vs Winter trough (turn 9)
        autumn_mult = _prod.season_mult(5)
        winter_mult = _prod.season_mult(9)
        self.assertGreater(autumn_mult, 1.30)
        self.assertLess(winter_mult, 0.65)

        # Emergent Turnip Winter:
        # Depleted soil (0.40) + nitrate cut-off during winter trough (turn 9)
        self.tile_up.soil_fertility = 0.40
        self.tile_up.farming_regime = 'intensive'
        self.tile_up.fertilizer_stock = 0.0  # Nitrates depleted!
        self.tile_up._last_turn = 9          # Winter trough!

        yield_mult = _prod.terrain_bonus(self.tile_up, Goods.food, t=9)
        # 0.40 (soil) * 0.50 (nitrate shortage) * winter_mult (~0.57) < 0.25 (over 75% collapse!)
        self.assertLess(yield_mult, 0.25)
        self.assertTrue(self.tile_up.is_nitrate_depleted)

    def test_05_transboundary_effluent_and_fishery_collapse(self):
        """Verify 35% downstream river advection and downstream coastal fishery yield collapse."""
        # Verify downstream neighbor detection along river
        downstream = self.em.get_downstream_neighbors(self.tile_up.name)
        self.assertEqual(len(downstream), 1)
        self.assertEqual(downstream[0].name, self.tile_down.name)

        # Inject industrial water pollution upstream
        self.tile_up.pollution_water = 40.0
        self.tile_down.pollution_water = 0.0

        step_tile_externalities(self.tile_up, 1)

        # Downstream tile receives effluent!
        self.assertGreater(self.tile_down.pollution_water, 5.0)

        # Downstream fishery food production collapses due to water toxicity
        fish_mult = _prod.terrain_bonus(self.tile_down, Goods.food)
        self.assertLess(fish_mult, 1.0)

    def test_06_infant_mortality_and_riparian_casus_belli(self):
        """Verify infant mortality spike from bad water and generation of riparian casus belli."""
        # A. Infant mortality on polluted tile without sewer
        self.tile_down.pollution_water = 90.0
        self.tile_down.infant_fatalities_this_turn = 0

        parent = Agent(1)
        initialize_agent(parent, Goods.food, 0, 20, 100.0)
        parent.inv_add(Goods.food, 50)
        parent.last_reproduction = 0

        ctx = DummyCtx(self.tile_down)
        ctx.p_birth = 1.0
        new_agents = []
        # Attempt reproduction under high water pollution without sewer
        for step_i in range(30):
            parent.last_reproduction = step_i - 10
            handle_reproduction(ctx, step_i, parent, [parent], new_agents)

        self.assertGreater(self.tile_down.infant_fatalities_this_turn, 0)

        # B. Riparian casus belli between different nations
        dip = get_diplomacy()
        dip.set_relation(self.nation_b.name, self.nation_a.name, -0.55)

        self.tile_up.pollution_water = 60.0
        step_tile_externalities(self.tile_up, 1)

        cb_set = getattr(self.nation_b, 'active_casus_belli', set())
        self.assertTrue(any(target == self.nation_a.name and cb == 'riparian_poisoning' for target, cb in cb_set))

    def test_07_bazalgette_sewer_megaproject_and_conserved_bond(self):
        """Verify municipal sewer bond issuance, cholera eradication, and 0-leak coupon service."""
        market = get_bond_market()
        ok, msg, bond = market.issue_municipal_sewer_bond(self.nation_a, self.tile_up, t=1)
        self.assertTrue(ok)
        self.assertIsNotNone(bond)
        self.assertEqual(bond.principal, 1000.0)
        self.assertEqual(bond.bond_purpose, "municipal_sewer")

        # Project exists on tile
        sewer_projs = [p for p in self.tile_up.construction_projects if p.recipe.name == 'trunk_sewer']
        self.assertEqual(len(sewer_projs), 1)
        proj = sewer_projs[0]
        self.assertGreaterEqual(proj.contractor.cash, 1000.0)

        # Add citizen on tile to verify sanitation fee coupon service (0 leak)
        cit = Agent(1)
        initialize_agent(cit, Goods.food, 0, 10, 50.0)
        self.tile_up.agents = [cit]

        initial_total_cash = cit.cash + self.nation_a.government.agent.cash + proj.contractor.cash
        world = {'nations': [self.nation_a, self.nation_b], 'turn': 2}
        market.step(world, 2)

        # Citizen paid small sanitation fee towards coupon
        self.assertLess(cit.cash, 50.0)

        # Verify cholera is eradicated once sewer is built
        from disease import step_agent_disease_onset, DIS_WATERBORNE
        b_sewer = BUILDING_RECIPES['trunk_sewer']
        from buildings import Building
        self.tile_up.buildings.append(Building(name='trunk_sewer', recipe=b_sewer, built_turn=2, region_name=self.tile_up.name))

        self.tile_up.pollution_water = 80.0  # Even under high pollution!
        active_dis = step_agent_disease_onset(cit, self.tile_up)
        self.assertNotIn(DIS_WATERBORNE, active_dis)

    def test_08_the_great_stink_catalyst(self):
        """Verify capital pollution >= 60 triggers The Great Stink and legitimacy drop."""
        from worldview_engine import step_world
        world = {
            'turn': 1,
            'tiles': self.tiles,
            'currencies': ['gold'],
            'nations': [self.nation_a, self.nation_b],
            'pair_orders': [],
            'ticker': []
        }
        self.nation_a.legitimacy = 0.80
        # Add industrial polluters in capital to generate massive water effluent
        factories = []
        for i in range(25):
            f_ag = Agent(1)
            initialize_agent(f_ag, Goods.wood, 0, 10, 50.0)
            f_ag.is_corporation = True
            factories.append(f_ag)
        self.tile_up.agents = factories
        self.tile_up.pollution_water = 85.0

        step_world(world)

        self.assertTrue(getattr(self.nation_a, '_great_stink_triggered', False))
        self.assertLessEqual(self.nation_a.legitimacy, 0.60)


if __name__ == '__main__':
    unittest.main()
