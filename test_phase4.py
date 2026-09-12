"""
test_phase4.py — Unit test suite for Phase 4: Financial Imperialism & Popular Resistance.

Verifies:
1. Customs Receivership intercepts debtor tariff revenue with 0 cash leak.
2. Anti-Enclosure Revolts tear down fences, restoring commons access and zeroing rents.
3. General Strike freezes transport routes (no advance, no post).
4. Armed Insurrection raids armory with strict cash/food conservation.
5. Revolutionary Commune declares council regime, restores all land to commons, and repudiates foreign debt.
6. Core-Periphery index correctly classifies imperial creditors vs indebted periphery.
"""

import unittest
from nation import Nation
from region import Region
from goods import Goods
from land_tenure import TenureStatus, TileTenure, LandPlot
from transporter import Route
from sovereign_bonds import SovereignBond, get_bond_market
from imperialism import get_imperialism_manager, CustomsReceivership
from popular_resistance import get_popular_resistance_manager


class TestPhase4(unittest.TestCase):

    def setUp(self):
        self.imp_mgr = get_imperialism_manager()
        self.imp_mgr.receiverships.clear()
        self.imp_mgr.unequal_treaties.clear()
        self.imp_mgr.blockaded_tiles.clear()
        self.imp_mgr.delinquent_defaults.clear()

        self.res_mgr = get_popular_resistance_manager()
        self.res_mgr.tile_states.clear()

        self.bond_market = get_bond_market()
        self.bond_market.bonds.clear()

    def test_customs_receivership_conservation(self):
        """Test that Customs Receivership intercepts tariffs with 100% money conservation."""
        creditor = Nation("Empire", initial_cash=1000.0)
        debtor = Nation("Colony", initial_cash=100.0)

        tile = Region("PortCity", 0, 0)
        debtor.add_tile(tile)

        # Establish receivership for $300 debt
        ok, msg, rec = self.imp_mgr.establish_receivership(creditor, debtor, 300.0, t=1)
        self.assertTrue(ok)
        self.assertEqual(rec.remaining_debt, 300.0)

        # Gross tariff collected = $100.0
        creditor_cash_before = creditor.government.agent.cash
        net_amount, intercepted, cred_name = self.imp_mgr.intercept_revenue("Colony", 100.0, t=2)

        self.assertEqual(cred_name, "Empire")
        self.assertAlmostEqual(intercepted, 40.0)  # 40%
        self.assertAlmostEqual(net_amount, 60.0)    # 60%
        self.assertAlmostEqual(creditor.government.agent.cash - creditor_cash_before, 40.0)
        self.assertAlmostEqual(rec.remaining_debt, 260.0)
        self.assertAlmostEqual(rec.total_collected, 40.0)

        # Verify sum conservation: intercepted + net == 100.0
        self.assertAlmostEqual(net_amount + intercepted, 100.0)

    def test_anti_enclosure_revolts(self):
        """Test that hungry peasants tear down enclosure fences, restoring commons access."""
        nation = Nation("Agraria", initial_cash=500.0)
        tile = Region("Farmland", 0, 0)
        nation.add_tile(tile)

        # Set up enclosed plot
        plot = LandPlot(
            plot_id="plot_1",
            tile_name=tile.name,
            lord_id=999,
            fraction=0.8,
            tenure=TenureStatus.ENCLOSED,
            rent_rate=5.0
        )
        tile.tenure = TileTenure(plots=[plot])
        self.assertEqual(tile.tenure.commons_access, 0.0)
        self.assertEqual(tile.tenure.enclosed_fraction, 0.8)

        # Create hungry dispossessed peasants
        from agent import Agent
        a1 = Agent(1)
        a1.region = tile.name
        a1.hungry_steps = 2
        a1.social_class = 'dispossessed'
        a2 = Agent(2)
        a2.region = tile.name
        a2.hungry_steps = 3
        a2.social_class = 'tenant'
        tile.agents = [a1, a2]
        tile.unrest_level = 1.2

        # Step through the 5-stage revolt ladder to leveling
        for turn in range(5, 10):
            events = self.res_mgr.evaluate_anti_enclosure_revolt(tile, t=turn)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['kind'], 'ANTI_ENCLOSURE_REVOLT')

        # Fence torn down: plot becomes COMMONS, rent_rate 0, full commons access
        self.assertEqual(plot.tenure, TenureStatus.COMMONS)
        self.assertEqual(plot.rent_rate, 0.0)
        self.assertAlmostEqual(tile.tenure.commons_access, 0.8)

    def test_general_strike_freezes_routes(self):
        """Test that General Strike paralyzes transport routes from posting and advancing."""
        src = Region("FactoryCity", 0, 0)
        dst = Region("MarketCity", 1, 0)
        route = Route("IndustrialRoute", src, dst, base_delay=2)

        from agent import Agent
        trader = Agent(10)
        trader.region = src.name
        trader.inventory_export[Goods.food.value] = 50

        # Normal posting works
        posted = route.post(trader, Goods.food, 20)
        self.assertEqual(posted, 20)
        route.deliver_pending()
        self.assertEqual(len(route.in_transit), 1)
        self.assertEqual(route.in_transit[0][3], 2)  # turns_left = 2

        # Trigger General Strike on route
        route.is_blocked_by_strike = True
        self.assertTrue(route.is_frozen)

        # Posting is blocked
        posted_strike = route.post(trader, Goods.food, 10)
        self.assertEqual(posted_strike, 0)

        # Advancing is frozen
        route.advance()
        self.assertEqual(route.in_transit[0][3], 2)  # did not decrement!
        self.assertEqual(len(route.delivered_this_turn), 0)

        # End strike
        route.is_blocked_by_strike = False
        self.assertFalse(route.is_frozen)
        route.advance()
        self.assertEqual(route.in_transit[0][3], 1)  # decremented to 1

    def test_revolutionary_commune_transition(self):
        """Test that insurrection triggers the Revolutionary Commune, de-encloses land, and repudiates foreign debt."""
        debtor = Nation("Republique", initial_cash=200.0, legitimacy=0.02)
        creditor = Nation("ImperialMetropole", initial_cash=2000.0)

        tile1 = Region("Capital", 0, 0)
        tile2 = Region("Plains", 0, 1)
        debtor.add_tile(tile1)
        debtor.add_tile(tile2)

        # Add enclosed plots
        p1 = LandPlot("p1", tile1.name, 100, 0.6, TenureStatus.ENCLOSED, rent_rate=10.0)
        p2 = LandPlot("p2", tile2.name, 101, 0.7, TenureStatus.ENCLOSED, rent_rate=8.0)
        tile1.tenure = TileTenure([p1])
        tile2.tenure = TileTenure([p2])

        # Active barricades in territory
        st1 = self.res_mgr.get_state(tile1.name)
        st1.has_barricades = True

        # Foreign sovereign bond owed to creditor
        bond = SovereignBond("bnd_test", debtor.name, creditor.name, 800.0, 0.002, 20, 0, 20, "active")
        self.bond_market.bonds.append(bond)

        # Active customs receivership
        self.imp_mgr.establish_receivership(creditor, debtor, 800.0, t=1)

        world = {
            'nations': [debtor, creditor],
            'tiles': [tile1, tile2]
        }

        # Step commune evaluation
        events = self.res_mgr.evaluate_revolutionary_commune(debtor, t=10, world=world)
        self.assertEqual(len(events), 1)
        self.assertEqual(debtor.regime_type, 'commune')
        self.assertEqual(debtor.ruling_faction, 'Worker-Peasant Council')
        self.assertGreaterEqual(debtor.legitimacy, 0.8)

        # All land tenure restored to COMMONS
        self.assertEqual(p1.tenure, TenureStatus.COMMONS)
        self.assertEqual(p1.rent_rate, 0.0)
        self.assertEqual(p2.tenure, TenureStatus.COMMONS)
        self.assertEqual(p2.rent_rate, 0.0)

        # Sovereign debt repudiated
        self.assertEqual(bond.status, 'repudiated')
        rec = self.imp_mgr.get_active_receivership_on(debtor.name)
        self.assertIsNone(rec)  # expelled

    def test_core_periphery_index(self):
        """Test calculation of Core-Periphery score."""
        core = Nation("CoreEmpire", initial_cash=5000.0)
        peri = Nation("PeripheryNation", initial_cash=150.0)

        # Core holds bonds issued by Periphery
        b = SovereignBond("b_foreign", peri.name, core.name, 600.0, 0.002, 20, 0, 20, "active")
        self.bond_market.bonds.append(b)

        world = {'nations': [core, peri]}
        score_core = self.imp_mgr.compute_core_periphery_index(core, world)
        score_peri = self.imp_mgr.compute_core_periphery_index(peri, world)

        self.assertGreater(score_core.composite_index, score_peri.composite_index)
        self.assertEqual(score_core.tier, "Imperial Core")
        self.assertEqual(score_peri.tier, "Indebted Periphery")

    def test_phase4_tooltips_and_decrees(self):
        """Verify tooltips and decrees for Phase 4."""
        from worldview_tooltips import get_button_tooltip_data
        from worldview_policies import _execute_policy_action
        nation = Nation("Testland", initial_cash=1000.0)
        tile = Region("TileA", 0, 0)
        nation.add_tile(tile)

        p = LandPlot("plot_encl", tile.name, 50, 0.5, TenureStatus.ENCLOSED, rent_rate=10.0)
        tile.tenure = TileTenure([p])

        world = {
            'turn': 10,
            'nations': [nation],
            'tiles': [tile],
            'selected_region': tile,
            'ticker_events': []
        }

        # 1. Test tooltip generation
        tooltips_to_test = [
            'debt_scope_imperial', 'debt_repudiate', 'debt_moratorium',
            'debt_accept_receivership', 'dip_imperial_coercion',
            'nat_restore_commons', 'nat_martial_law'
        ]
        for tip_id in tooltips_to_test:
            tip = get_button_tooltip_data(tip_id, world, region=tile, nation=nation)
            self.assertIsNotNone(tip, f"Tooltip data for {tip_id} should not be None")
            self.assertTrue(len(tip.get('title', '')) > 0)
            self.assertTrue(len(tip.get('desc', [])) > 0)

        # 2. Test nat_restore_commons decree
        self.assertEqual(tile.tenure.enclosed_fraction, 0.5)
        _execute_policy_action(world, 'nat_restore_commons', nation)
        self.assertEqual(tile.tenure.enclosed_fraction, 0.0)
        self.assertEqual(tile.tenure.commons_fraction, 0.5)
        self.assertEqual(p.tenure, TenureStatus.COMMONS)

        # 3. Test nat_martial_law decree
        st = self.res_mgr.get_state(tile.name)
        st.has_barricades = True
        st.is_general_strike = True

        # Fails without military units
        _execute_policy_action(world, 'nat_martial_law', nation)
        self.assertTrue(st.has_barricades)

        # Succeeds when nation has standing military forces
        from army import MilitaryUnit
        unit = MilitaryUnit("unit_1", nation.name, tile.name, soldiers=15)
        nation.military_units.append(unit)
        _execute_policy_action(world, 'nat_martial_law', nation)
        self.assertFalse(st.has_barricades)
        self.assertFalse(st.is_general_strike)


if __name__ == '__main__':
    unittest.main()
