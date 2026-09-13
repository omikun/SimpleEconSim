"""
test_canals_wool_construction.py — Unit & Integration Tests for:
1. First-class Wool & Cloth economy (Goods.wool, Goods.cloth, Shepherds, Weavers).
2. Infrastructure Technologies (turnpike_trusts, barge_canals, mechanized_textiles).
3. Emergent Construction Companies (zero start, organic agent transition).
4. Physical Resource & Navvy Labor Gating, Dynamic Progress & Stalling.
5. Emergency Contractor Overrun Subsidies (avert layoffs, conserved money).
6. Project Droughts, Mass Layoffs & Navvy Riots.
7. Operational Building Staffing & Efficiency Scaling.
8. Sovereign AI Market-Driven Enclosures & Infrastructure Procurement.
"""

import unittest
from goods import Goods, profession
from region import Region
from nation import Nation
from buildings import BUILDING_RECIPES, Building, ConstructionProject
from innovation import TECH_CATALOG, TechDomain
from intents import BuildIntent, SubsidizeContractorIntent, step_intents_and_construction
from construction_politics import (
    find_or_emerge_contractor,
    calculate_contractor_political_power,
    subsidize_contractor,
    step_construction_politics
)
from agent import Agent, initialize_agent, seed_traits
from land_tenure import TileTenure, LandPlot, TenureStatus
import region_production as _prod


class TestCanalsWoolConstruction(unittest.TestCase):

    def setUp(self):
        self.nation = Nation("Commonwealth", initial_cash=1000.0)
        self.tile = Region("Oxfordshire", 0, 0)
        self.nation.add_tile(self.tile)

    def test_01_wool_and_cloth_supply_chain(self):
        """Verify Goods.wool and Goods.cloth definitions, recipes, and pasture yields."""
        self.assertIn(Goods.wool, Goods)
        self.assertIn(Goods.cloth, Goods)
        self.assertEqual(profession[Goods.wool], 'S')
        self.assertEqual(profession[Goods.cloth], 'T')

        # Check default recipes in region
        self.assertIn(Goods.wool, self.tile.recipes)
        self.assertIn(Goods.cloth, self.tile.recipes)
        self.assertEqual(self.tile.recipes[Goods.cloth]['input'], Goods.wool)

        # Pasture plot produces Goods.wool
        lord = self.tile.agents[0]
        plot = LandPlot(
            plot_id='p_pasture',
            tile_name=self.tile.name,
            lord_id=lord.id,
            fraction=0.5,
            tenure=TenureStatus.ENCLOSED,
            rent_rate=5.0,
            production_type='pasture',
            name='Cotswold Downs'
        )
        self.tile.tenure = TileTenure(plots=[plot])
        w_before = lord.inv_get(Goods.wool, 0)
        _prod.produce(self.tile, t=1)
        w_after = lord.inv_get(Goods.wool, 0)
        self.assertGreater(w_after, w_before, "Pasture plot must yield Goods.wool")

    def test_02_tech_catalog_and_building_recipes(self):
        """Verify Turnpike Trusts, Barge Canals, and Mechanized Textiles in TECH_CATALOG and BUILDING_RECIPES."""
        self.assertIn('turnpike_trusts', TECH_CATALOG)
        self.assertIn('barge_canals', TECH_CATALOG)
        self.assertIn('mechanized_textiles', TECH_CATALOG)

        self.assertIn('turnpike_road', BUILDING_RECIPES)
        self.assertIn('barge_canal', BUILDING_RECIPES)
        self.assertIn('textile_mill', BUILDING_RECIPES)

        r_road = BUILDING_RECIPES['turnpike_road']
        self.assertGreaterEqual(r_road.construction_workers, 3)
        self.assertIn(Goods.transport, r_road.staff_required)

        r_canal = BUILDING_RECIPES['barge_canal']
        self.assertGreaterEqual(r_canal.construction_workers, 4)
        self.assertIn(Goods.wood, r_canal.required_goods)

        r_mill = BUILDING_RECIPES['textile_mill']
        self.assertIn(Goods.cloth, r_mill.production_bonuses)
        self.assertIn(Goods.cloth, r_mill.staff_required)

    def test_03_zero_start_and_emergent_contractor_transition(self):
        """Verify game starts with zero contractors, and commissioning a project causes an agent to transition."""
        # 1. Verify zero initial contractors
        initial_contractors = [
            a for a in self.tile.agents
            if getattr(a, 'is_construction_company', False)
        ]
        self.assertEqual(len(initial_contractors), 0, "Must start with zero construction companies")

        # 2. Commission project
        intent = BuildIntent(self.nation.name, self.tile.name, 'turnpike_road', submitted_turn=1)
        tiles_by_name = {self.tile.name: self.tile}
        nations_by_name = {self.nation.name: self.nation}
        ok, msg = intent.execute(tiles_by_name, nations_by_name, t=1)
        self.assertTrue(ok)

        # 3. An existing living agent transitioned into contractor
        contractors = [
            a for a in self.tile.agents
            if getattr(a, 'is_construction_company', False)
        ]
        self.assertEqual(len(contractors), 1, "Exactly one contractor should have emerged")
        c = contractors[0]
        self.assertTrue(c.is_corporation)
        self.assertEqual(c.social_class, 'contractor')
        self.assertIn("Syndicate", c.company_name)
        self.assertGreaterEqual(c.cash, 300.0, "Contractor received the project funds")

    def test_04_dynamic_progress_and_resource_stalling(self):
        """Verify projects require physical resources and stall when resources are absent."""
        recipe = BUILDING_RECIPES['turnpike_road']
        contractor = find_or_emerge_contractor(self.tile, 300.0, t=1)
        contractor.cash = 0.0  # Zero cash -> cannot buy materials

        proj = ConstructionProject(
            project_id="test_stall_proj",
            nation_name=self.nation.name,
            region=self.tile,
            recipe=recipe,
            contractor=contractor,
            started_turn=1
        )
        self.tile.construction_projects = [proj]

        # Step project: materials cannot be bought -> project stalls
        proj.step(t=1)
        self.assertEqual(proj.status, 'stalled')
        self.assertEqual(proj.stall_reason, 'missing_materials')
        self.assertEqual(proj.progress_pct, 0.0)

        # Give contractor cash to buy materials
        contractor.cash = 200.0
        proj.step(t=2)
        # Contractor bought materials and hired navvies -> progress moves forward
        self.assertGreater(proj.progress_pct, 0.0)
        self.assertEqual(proj.status, 'in_progress')

    def test_05_emergency_overrun_subsidy_averts_layoffs(self):
        """Verify option to inject overrun grants transfers funds, resumes project, and preserves money invariant."""
        recipe = BUILDING_RECIPES['barge_canal']
        contractor = find_or_emerge_contractor(self.tile, 380.0, t=1)
        contractor.cash = 1.0  # Critically low cash

        proj = ConstructionProject(
            project_id="canal_distress_proj",
            nation_name=self.nation.name,
            region=self.tile,
            recipe=recipe,
            contractor=contractor,
            started_turn=1
        )
        proj.status = 'stalled'
        self.tile.construction_projects = [proj]

        treasury_before = self.nation.government.agent.cash
        contractor_before = contractor.cash

        # Issue subsidy of $100
        ok, msg = subsidize_contractor(proj, 100.0, self.nation)
        self.assertTrue(ok)
        self.assertEqual(proj.status, 'in_progress')

        # Money conservation check (0 LEAK)
        self.assertEqual(self.nation.government.agent.cash, treasury_before - 100.0)
        self.assertEqual(contractor.cash, contractor_before + 100.0)
        self.assertEqual(proj.emergency_subsidies_received, 100.0)

    def test_06_project_drought_mass_layoffs_and_navvy_riots(self):
        """Verify that idle contractors execute mass layoffs after >= 2 turns, spiking unrest and triggering navvy riots."""
        contractor = find_or_emerge_contractor(self.tile, 200.0, t=1)
        # Attach 4 navvies
        workers = self.tile.agents[1:5]
        for w in workers:
            w.employer = contractor
            contractor.employees.append(w)
        self.tile.construction_projects = []  # No active projects (drought)

        self.tile.protest_energy_log = [1.0]

        # Turn 1 idle: Corporate Lobbying
        step_construction_politics(self.tile, t=1)
        self.assertEqual(contractor.idle_turns, 1)
        self.assertEqual(len(contractor.employees), 4, "Should not lay off on turn 1")

        # Turn 2 idle: Project Drought -> Mass Layoffs!
        step_construction_politics(self.tile, t=2)
        self.assertEqual(contractor.idle_turns, 2)
        self.assertEqual(len(contractor.employees), 0, "Employees discharged into dispossessed")
        for w in workers:
            self.assertIsNone(w.employer)
            self.assertEqual(w.social_class, 'dispossessed')

        # Protest energy spiked!
        self.assertGreater(self.tile.protest_energy_log[-1], 2.5)

    def test_07_operational_building_staffing_and_efficiency(self):
        """Verify installed buildings require operational staff to maintain full production efficiency."""
        recipe = BUILDING_RECIPES['textile_mill']
        b = Building(
            name='textile_mill',
            recipe=recipe,
            built_turn=1,
            region_name=self.tile.name
        )
        self.tile.buildings = [b]

        # Initially unstaffed
        b.staff_ids = []
        b.operational_efficiency = 0.0

        # Step staffing
        b.step_operational_staffing(self.tile, t=1)
        self.assertGreater(b.operational_efficiency, 0.2)
        self.assertGreater(len(b.staff_ids), 0)

        # Bonuses scale with efficiency
        bonuses = b.production_bonuses
        self.assertIn(Goods.cloth, bonuses)
        self.assertGreater(bonuses[Goods.cloth], 1.0)

    def test_08_ai_enclosure_and_infrastructure_procurement(self):
        """Verify AI responds to grain/wool prices to enclose and orders turnpikes/canals."""
        from ai_nation import NationPolicyAI
        from diplomacy import DiplomacySystem
        ai = NationPolicyAI(self.nation)
        diplomacy = DiplomacySystem()

        # Set up a feudal plot
        lord = self.tile.agents[0]
        lord.cash = 200.0
        plot = LandPlot(
            plot_id='p_feudal_ai',
            tile_name=self.tile.name,
            lord_id=lord.id,
            fraction=0.5,
            tenure=TenureStatus.FEUDAL,
            rent_rate=0.0,
            production_type='arable',
            name='Abingdon Commons'
        )
        self.tile.tenure = TileTenure(plots=[plot])
        self.tile.recipes[Goods.wool]['price'] = 4.0  # High wool price trigger
        self.tile.recipes[Goods.food]['price'] = 1.0

        # Run AI turn
        submitted = ai.decide_turn(t=5, all_tiles=[self.tile], all_nations=[self.nation], diplomacy=diplomacy)
        self.assertGreater(len(submitted), 0)

        # Verify AI converted land use to pasture due to high wool/grain ratio
        self.assertEqual(plot.production_type, 'pasture')


if __name__ == '__main__':
    unittest.main()
