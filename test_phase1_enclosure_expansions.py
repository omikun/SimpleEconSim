"""
test_phase1_enclosure_expansions.py — Test Suite for Phase 1: Primitive Accumulation & Feudal Land Tenure.

Verifies:
1. Real-world country-specific plot naming (50 names per country, authentic assignment).
2. Granular tenancy: agents bound to specific lots (assigned_plot_id & plot.tenant_ids).
3. Pastoral conversion ("sheep eat men"): 75% labor cut, evictions to dispossessed, food penalty, wool export yield.
4. Survey & tithe debt trap: statutory fee assessment, solvent payment, foreclosure auction to wealthiest agent.
5. Parish Workhouse & Settlement Laws: vagrancy arrests, gruel feeding, municipal labor revenue, fiscal drought bread riot, and foreign migration barriers.
6. Financial & inventory conservation invariants throughout all transfers.
"""

import unittest
from nation import Nation
from region import Region
from goods import Goods
from land_tenure import TenureStatus, TileTenure, LandPlot
from agent import Agent
from world_names import COUNTRY_PLOT_NAMES, get_plot_name, get_plot_names_for_country, assign_world_identities
from enclosure import execute_enclosure, step_enclosure_survey_debts, STATUTORY_SURVEY_FEE
from workhouse import has_workhouse, step_workhouse, get_workhouse_inmates
import land_rent as _rent
import region_production as _prod


class TestPhase1EnclosureExpansions(unittest.TestCase):

    def setUp(self):
        # Reset counters / cache
        pass

    def test_01_country_plot_names_database(self):
        """Verify 50 authentic land plot names exist for all 18 countries."""
        all_countries = [
            "United States", "Britain", "France", "Germany", "Spain", "Italy",
            "China", "Japan", "India", "Indonesia", "Brazil", "Mexico",
            "Nigeria", "Pakistan", "Bangladesh", "Russia", "Korea", "Vietnam"
        ]
        for country in all_countries:
            self.assertIn(country, COUNTRY_PLOT_NAMES, f"{country} missing from COUNTRY_PLOT_NAMES")
            names = COUNTRY_PLOT_NAMES[country]
            self.assertEqual(len(names), 50, f"{country} does not have exactly 50 names (has {len(names)})")
            # Verify names are unique non-empty strings
            self.assertEqual(len(names), len(set(names)), f"{country} contains duplicate plot names")

        # Test helper functions
        us_name = get_plot_name("United States")
        self.assertIn(us_name, COUNTRY_PLOT_NAMES["United States"])
        
        # Test aliases
        self.assertEqual(len(get_plot_names_for_country("UK")), 50)
        self.assertEqual(len(get_plot_names_for_country("US")), 50)
        self.assertEqual(len(get_plot_names_for_country("South Korea")), 50)

    def test_02_assign_world_identities_plot_naming(self):
        """Verify assign_world_identities gives country-authentic plot names to tiles."""
        nation = Nation("Britain", initial_cash=1000.0)
        tile = Region("TileA", 0, number_of_agents=20)
        nation.add_tile(tile)

        self.assertGreater(len(tile.tenure.plots), 0)
        assign_world_identities([tile], [nation], seed=42)

        for plot in tile.tenure.plots:
            self.assertTrue(bool(plot.name), "Plot should have an authentic name")
            self.assertIn(plot.name, COUNTRY_PLOT_NAMES["Britain"], f"Plot {plot.name} should belong to British pool")

    def test_03_granular_tenancy_agent_binding(self):
        """Verify serfs are explicitly bound to plots (assigned_plot_id and plot.tenant_ids)."""
        tile = Region("TileManor", 0, number_of_agents=30)
        self.assertGreater(len(tile.tenure.plots), 0)
        
        total_bound = sum(len(p.tenant_ids) for p in tile.tenure.plots)
        self.assertGreater(total_bound, 0, "Tenants should be bound to plots")

        for plot in tile.tenure.plots:
            for tid in plot.tenant_ids:
                tenant = next((a for a in tile.agents if a.id == tid), None)
                self.assertIsNotNone(tenant)
                self.assertEqual(tenant.assigned_plot_id, plot.plot_id)

    def test_04_pasture_conversion_and_evictions(self):
        """Verify pasture conversion slashes tenant labor by 75%, evicting the rest to dispossessed."""
        tile = Region("EstateTile", 0, 0)
        lord = Agent(1)
        lord.cash = 200.0
        lord.is_lord = True
        tile.agents.append(lord)

        plot = LandPlot(
            plot_id="plot_pasture_test",
            tile_name=tile.name,
            lord_id=lord.id,
            fraction=1.0,
            tenure=TenureStatus.ENCLOSED,
            rent_rate=5.0,
            production_type='arable'
        )
        tile.tenure = TileTenure(plots=[plot])

        # Create 8 tenants bound to this plot
        tenants = []
        for i in range(8):
            a = Agent(10 + i)
            a.cash = 20.0
            a.assigned_plot_id = plot.plot_id
            plot.tenant_ids.append(a.id)
            tenants.append(a)
            tile.agents.append(a)

        self.assertEqual(len(plot.tenant_ids), 8)

        # Convert plot to pasture
        tile.tenure.convert_production_type(plot.plot_id, 'pasture', turn=1)
        self.assertEqual(plot.production_type, 'pasture')
        self.assertAlmostEqual(tile.tenure.pasture_fraction, 1.0)

        # Collect rents: triggers 75% labor cut
        collected, arrears, events = _rent.collect_rents(tile, t=1)

        # Keep count should be max(1, int(8 * 0.25)) = 2 shepherds
        self.assertEqual(len(plot.tenant_ids), 2)
        
        # 6 evicted tenants
        evicted = [a for a in tenants if a.id not in plot.tenant_ids]
        self.assertEqual(len(evicted), 6)
        for ex in evicted:
            self.assertIsNone(ex.assigned_plot_id)
            self.assertEqual(ex.social_class, 'dispossessed')
            self.assertIn('mem_eviction', ex.memory)

    def test_05_pasture_food_penalty_and_wool_yield(self):
        """Verify pasture fraction reduces food terrain bonus and yields wool for landlord."""
        tile = Region("WoolTile", 0, 0)
        lord = Agent(1)
        lord.is_lord = True
        lord.cash = 100.0
        tile.agents.append(lord)

        plot = LandPlot(
            plot_id="p_wool",
            tile_name=tile.name,
            lord_id=lord.id,
            fraction=0.8,
            tenure=TenureStatus.ENCLOSED,
            rent_rate=5.0,
            production_type='pasture'
        )
        tile.tenure = TileTenure(plots=[plot])

        # Food multiplier should be penalized by pasture fraction (0.8 * 0.75 = 0.60 reduction -> 0.40)
        food_mult = _prod.terrain_bonus(tile, Goods.food)
        self.assertLess(food_mult, 1.0)

        # Produce phase: landlord receives wool (Goods.wood)
        wood_before = lord.inv_get(Goods.wood, 0)
        _prod.produce(tile, t=1)
        wood_after = lord.inv_get(Goods.wood, 0)
        self.assertGreater(wood_after, wood_before, "Lord should receive wool/raw material yield from pasture")

    def test_06_survey_debt_trap_solvent_and_foreclosure(self):
        """Verify survey fee statutory assessment, solvent payment, and foreclosure auction on default."""
        nation = Nation("Kingdom", initial_cash=500.0)
        tile = Region("CourtTile", 0, 0)
        nation.add_tile(tile)

        lord = Agent(1)
        lord.cash = 600.0
        lord.is_lord = True
        tile.agents.append(lord)

        # Solvent tenant
        t_solvent = Agent(2)
        t_solvent.cash = 30.0  # > STATUTORY_SURVEY_FEE (15.0)
        tile.agents.append(t_solvent)

        # Insolvent tenant
        t_insolvent = Agent(3)
        t_insolvent.cash = 2.0   # < STATUTORY_SURVEY_FEE
        tile.agents.append(t_insolvent)

        # Wealthy merchant/gentry bidder
        merchant = Agent(4)
        merchant.cash = 50.0
        tile.agents = [lord, t_solvent, t_insolvent, merchant]

        plot = LandPlot(
            plot_id="feudal_strip",
            tile_name=tile.name,
            lord_id=lord.id,
            fraction=0.5,
            tenure=TenureStatus.FEUDAL,
            tenant_ids=[t_solvent.id, t_insolvent.id]
        )
        tile.tenure = TileTenure(plots=[plot])

        # Execute enclosure at t=1
        ok, msg, evs = execute_enclosure(tile, plot.plot_id, t=1)
        self.assertTrue(ok)
        self.assertEqual(plot.tenure, TenureStatus.ENCLOSED)

        # Verify survey debts assessed
        self.assertEqual(len(tile.enclosure_survey_debts), 2)

        # Turn 1: solvent tenant pays immediately
        gov_cash_before = tile.gov.agent.cash
        evs_debts1 = step_enclosure_survey_debts(tile, t=1)
        self.assertAlmostEqual(t_solvent.cash, 15.0) # 30 - 15
        self.assertAlmostEqual(tile.gov.agent.cash - gov_cash_before, 15.0) # conserved transfer
        self.assertEqual(len(tile.enclosure_survey_debts), 1) # only insolvent tenant left

        # Turn 2: insolvent tenant under pressure (deadline is t=4)
        evs_debts2 = step_enclosure_survey_debts(tile, t=2)
        self.assertEqual(len(tile.enclosure_survey_debts), 1)
        self.assertIn('mem_promises', t_insolvent.memory)

        # Turn 4: deadline reached! Foreclosure & auction
        gov_cash_before_auction = tile.gov.agent.cash
        merchant_cash_before = merchant.cash
        evs_debts4 = step_enclosure_survey_debts(tile, t=4)

        # Insolvent tenant foreclosed & evicted
        self.assertNotIn(t_insolvent.id, plot.tenant_ids)
        self.assertEqual(t_insolvent.social_class, 'dispossessed')
        self.assertIn('mem_debt_trap', t_insolvent.memory)
        self.assertIn('mem_eviction', t_insolvent.memory)

        # Wealthiest agent (Lord with $100 vs Merchant with $50) won auction
        auction_ev = next((e for e in evs_debts4 if e['event'] == 'SURVEY_DEBT_FORECLOSURE'), None)
        self.assertIsNotNone(auction_ev)
        self.assertEqual(auction_ev['winner_id'], lord.id)
        bid = auction_ev['clearing_bid']
        self.assertGreater(bid, 0.0)
        self.assertAlmostEqual(lord.cash, 100.0 - bid)
        self.assertAlmostEqual(tile.gov.agent.cash, gov_cash_before_auction + bid)

    def test_07_parish_workhouse_confinement_and_revenue(self):
        """Verify workhouse building recipe, vagrancy arrest, gruel feeding, and municipal labor revenue."""
        nation = Nation("ParishNation", initial_cash=500.0)
        tile = Region("ParishCity", 0, 0)
        nation.add_tile(tile)

        # Install completed workhouse building
        from buildings import BUILDING_RECIPES, Building
        recipe = BUILDING_RECIPES['workhouse']
        self.assertIsNotNone(recipe)
        b = Building(name='workhouse', recipe=recipe, built_turn=1, region_name=tile.name)
        tile.buildings.append(b)
        self.assertTrue(has_workhouse(tile))

        # Create 3 dispossessed paupers
        paupers = []
        for i in range(3):
            p = Agent(50 + i)
            p.cash = 1.0
            p.social_class = 'dispossessed'
            tile.agents.append(p)
            paupers.append(p)

        # Municipal treasury has food and cash
        tile.gov.agent.inv_add(Goods.food, 5)
        gov_cash_before = tile.gov.agent.cash

        # Step workhouse
        evs = step_workhouse(tile, t=1)

        # All 3 arrested and confined
        inmates = get_workhouse_inmates(tile)
        self.assertEqual(len(inmates), 3)
        for p in paupers:
            self.assertTrue(p.in_workhouse)
            self.assertIn('mem_workhouse', p.memory)
            self.assertEqual(p.hungry_steps, 0)

        # Municipal revenue earned from forced labor: 3 * 1.50 = 4.50
        self.assertAlmostEqual(tile.gov.agent.cash - gov_cash_before, 4.50)

    def test_08_workhouse_fiscal_drought_bread_riot(self):
        """Verify that if the municipality has no food and no cash, inmates starve and launch a Bread Riot."""
        nation = Nation("BankruptNation", initial_cash=0.0)
        tile = Region("BankruptCity", 0, 0)
        nation.add_tile(tile)

        from buildings import BUILDING_RECIPES, Building
        b = Building(name='workhouse', recipe=BUILDING_RECIPES['workhouse'], built_turn=1, region_name=tile.name)
        tile.buildings.append(b)

        # Bankrupt municipal gov
        tile.gov.agent.cash = 0.0
        tile.gov.agent.inventory[Goods.food.value] = 0

        pauper = Agent(70)
        pauper.cash = 0.0
        pauper.social_class = 'dispossessed'
        tile.agents.append(pauper)

        # Step 1: Inmate arrested but starved
        step_workhouse(tile, t=1)
        self.assertTrue(pauper.in_workhouse)
        self.assertEqual(pauper.hungry_steps, 1)
        self.assertIn('mem_starvation', pauper.memory)

        # Step 2: Still starved -> bread riot event
        evs2 = step_workhouse(tile, t=2)
        riot_ev = next((e for e in evs2 if e['event'] == 'WORKHOUSE_BREAD_RIOT'), None)
        self.assertIsNotNone(riot_ev, "Starving inmates must stage a Workhouse Bread Riot")

    def test_09_settlement_laws_migration_barrier(self):
        """Verify Settlement Laws prevent dispossessed paupers from migrating to foreign claimed parishes."""
        from migration import _pick_destination

        home_nation = Nation("HomeNation", initial_cash=100.0)
        foreign_nation = Nation("ForeignNation", initial_cash=100.0)

        home_tile = Region("HomeTile", 0, 0)
        foreign_tile = Region("ForeignTile", 1, 0)
        wild_tile = Region("WildFrontier", 0, 1)
        wild_tile.wilderness = True

        home_nation.add_tile(home_tile)
        foreign_nation.add_tile(foreign_tile)

        home_tile.add_neighbor(foreign_tile, 1)
        home_tile.add_neighbor(wild_tile, 1)

        # Pauper agent born in HomeNation
        pauper = Agent(99)
        pauper.origin_nation = "HomeNation"
        pauper.social_class = 'dispossessed'
        pauper.cash = 2.0

        # Destination choice: foreign tile is blocked by Settlement Laws, so pauper picks wilderness
        dest = _pick_destination(home_tile, pauper)
        self.assertEqual(dest, wild_tile, "Dispossessed pauper barred from foreign parish must homestead or stay")


if __name__ == '__main__':
    unittest.main()
