"""
test_enforcement_and_tooltip_reasons.py — Test suite for:
1. Military enforcement for barricades and naval blockades.
2. Creditor military force vs hired agents for customs receiverships.
3. 100% money conservation for agent contracts and retainers.
4. Tooltips for greyed-out (disabled) buttons showing clear reason for disabled state.
"""

import unittest
from nation import Nation
from region import Region
from army import MilitaryUnit
from imperialism import get_imperialism_manager
from popular_resistance import get_popular_resistance_manager
from worldview_policies import _execute_policy_action
from worldview_tooltips import get_button_tooltip_data, draw_left_panel_tooltip
from worldview_tooltips_extra import build_debt_tooltip, build_diplomacy_tooltip, build_military_tooltip
import pygame


class TestEnforcementAndTooltipReasons(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    def setUp(self):
        self.imp_mgr = get_imperialism_manager()
        self.imp_mgr.receiverships.clear()
        self.imp_mgr.unequal_treaties.clear()
        self.imp_mgr.blockaded_tiles.clear()
        self.imp_mgr.blockade_enforcers.clear()
        self.imp_mgr.delinquent_defaults.clear()

        self.res_mgr = get_popular_resistance_manager()
        self.res_mgr.tile_states.clear()
        self.res_mgr.resistance_log.clear()

    # ------------------------------------------------------------------
    # 1. Barricade Military Enforcement
    # ------------------------------------------------------------------

    def test_barricade_military_suppression_and_martial_law(self):
        """Verify barricades require standing military units to suppress or clear."""
        nation = Nation("Rebelia", initial_cash=500.0)
        tile = Region("UrbanCore", 0, 0)
        nation.add_tile(tile)
        tile.unrest_level = 5.0

        world = {
            'turn': 1,
            'nations': [nation],
            'tiles': [tile],
            'selected_region': tile,
            'ticker_events': []
        }

        # Step 1: Erection of barricades
        events = self.res_mgr.evaluate_armed_insurrection(tile, t=1, world=world)
        st = self.res_mgr.get_state(tile.name)
        self.assertTrue(st.has_barricades)
        self.assertEqual(st.barricade_hp, 100.0)

        # Step 2: Attempt martial law without military units -> blocked
        self.assertEqual(len(nation.military_units), 0)
        _execute_policy_action(world, 'nat_martial_law', nation)
        self.assertTrue(st.has_barricades, "Barricades should resist removal without troops")
        self.assertIn("Cannot declare Martial Law", world.get('policy_feedback', ('', ''))[0])

        # Tooltip for nat_martial_law explains why it is greyed out
        tip = get_button_tooltip_data('nat_martial_law', world, region=tile, nation=nation)
        self.assertIsNotNone(tip)
        self.assertIn('disabled_reason', tip)
        self.assertIn("Military Force Required", tip['disabled_reason'])

        # Step 3: Military unit stationed on tile suppresses barricade
        unit = MilitaryUnit("garrison_1", nation.name, tile.name, soldiers=20)
        tile.military_units = [unit]
        nation.military_units = [unit]

        # First turn of suppression: dealing damage to barricade HP
        self.res_mgr.evaluate_armed_insurrection(tile, t=2, world=world)
        self.assertLess(st.barricade_hp, 100.0, "Military forces should degrade barricade HP")

        # Second turn: military completes breaching of barricades
        self.res_mgr.evaluate_armed_insurrection(tile, t=3, world=world)
        self.assertFalse(st.has_barricades, "Barricades should be breached after military suppression")
        self.assertEqual(st.barricade_hp, 0.0)

    # ------------------------------------------------------------------
    # 2. Blockade Military Enforcement
    # ------------------------------------------------------------------

    def test_blockade_military_enforcement(self):
        """Verify blockades cannot be imposed or sustained without military forces."""
        enforcer = Nation("SeaPower", initial_cash=500.0)
        debtor = Nation("IslandState", initial_cash=200.0)
        port_tile = Region("PortHarbor", 0, 0)
        port_tile.is_coast = True
        debtor.add_tile(port_tile)

        world = {
            'turn': 1,
            'nations': [enforcer, debtor],
            'tiles': [port_tile],
            'ticker_events': []
        }

        # Impose blockade without military units -> fails
        ok, msg = self.imp_mgr.impose_naval_blockade(enforcer, debtor, port_tile, t=1, world=world)
        self.assertFalse(ok)
        self.assertIn("Cannot impose naval blockade without active", msg)

        # Give enforcer a fleet/military unit -> succeeds
        fleet = MilitaryUnit("fleet_1", enforcer.name, "SeaTile", soldiers=30)
        enforcer.military_units.append(fleet)
        ok, msg = self.imp_mgr.impose_naval_blockade(enforcer, debtor, port_tile, t=1, world=world)
        self.assertTrue(ok)
        self.assertTrue(self.imp_mgr.is_tile_blockaded(port_tile.name))

        # Sustainment check: if enforcer units are destroyed/withdrawn, blockade collapses
        enforcer.military_units.clear()
        self.imp_mgr.step_imperialism(world, t=2)
        self.assertFalse(self.imp_mgr.is_tile_blockaded(port_tile.name), "Blockade should collapse without military forces")

    # ------------------------------------------------------------------
    # 3. Receivership Force vs Hired Agents & 100% Cash Conservation
    # ------------------------------------------------------------------

    def test_receivership_military_vs_hired_agents_conservation(self):
        """Verify receivership establishment with force, hired agents, and cash conservation."""
        creditor = Nation("ImperialBank", initial_cash=100.0)
        debtor = Nation("DebtorLand", initial_cash=50.0)
        tile = Region("Capital", 0, 0)
        debtor.add_tile(tile)

        # Setup living agents to guarantee conservation
        from agent import Agent
        bailiff_agent = Agent(1)
        bailiff_agent.region = tile.name
        tile.agents = [bailiff_agent]

        world = {
            'turn': 1,
            'nations': [creditor, debtor],
            'tiles': [tile],
            'ticker_events': []
        }

        # Case A: Creditor has no army and < $50 cash -> cannot establish receivership
        creditor.government.agent.cash = 30.0
        ok, msg, rec = self.imp_mgr.establish_receivership(creditor, debtor, 400.0, t=1, world=world)
        self.assertFalse(ok)
        self.assertIn("cannot afford $50 fee", msg)

        # Case B: Creditor has no army but has >= $50 cash -> contracts hired agents
        creditor.government.agent.cash = 100.0
        bailiff_cash_before = bailiff_agent.cash
        ok, msg, rec = self.imp_mgr.establish_receivership(creditor, debtor, 400.0, t=1, world=world)
        self.assertTrue(ok)
        self.assertEqual(rec.enforcement_mode, "hired_agents")
        self.assertEqual(creditor.government.agent.cash, 50.0)  # $100 - $50
        self.assertEqual(bailiff_agent.cash - bailiff_cash_before, 50.0, "100% money conserved: $50 transferred to agents")

        # Step turn in step_imperialism: pays $2.00 retainer fee to agents
        cred_cash_before_step = creditor.government.agent.cash
        bailiff_cash_before_step = bailiff_agent.cash
        self.imp_mgr.step_imperialism(world, t=2)
        self.assertEqual(rec.status, "active")
        self.assertEqual(cred_cash_before_step - creditor.government.agent.cash, 2.0)
        self.assertEqual(bailiff_agent.cash - bailiff_cash_before_step, 2.0, "Retainer fee strictly conserved")

        # If creditor cannot afford retainer: receivership is suspended
        creditor.government.agent.cash = 0.50
        self.imp_mgr.step_imperialism(world, t=3)
        self.assertEqual(rec.status, "suspended")

        # Intercept revenue while suspended returns full amount to debtor
        net, intercepted, cred_name = self.imp_mgr.intercept_revenue(debtor.name, 100.0, t=4, world=world)
        self.assertEqual(net, 100.0)
        self.assertEqual(intercepted, 0.0)

    # ------------------------------------------------------------------
    # 4. Tooltips for Greyed-Out Buttons
    # ------------------------------------------------------------------

    def test_tooltips_disabled_reason_display(self):
        """Verify all greyed-out buttons show accurate disabled_reason in tooltips."""
        nation = Nation("Republic", initial_cash=0.0)  # Broke nation
        tile = Region("Metropolis", 0, 0)
        tile.gov.agent.cash = 0.0  # Zero municipal treasury
        nation.add_tile(tile)
        tile.unrest_level = 0.20  # Peaceful, no unrest

        world = {
            'turn': 1,
            'nations': [nation],
            'tiles': [tile],
            'selected_region': tile,
            'ticker_events': []
        }

        # 1. City Emergency Food (Costs $50, treasury is $0)
        tip_food = get_button_tooltip_data('city_emergency_food', world, region=tile, nation=nation)
        self.assertIn('disabled_reason', tip_food)
        self.assertIn("Insufficient Municipal Treasury", tip_food['disabled_reason'])

        # 2. City Police Curfew (No civil unrest)
        tip_curfew = get_button_tooltip_data('city_police_curfew', world, region=tile, nation=nation)
        self.assertIn('disabled_reason', tip_curfew)
        self.assertIn("Civil Order Stable", tip_curfew['disabled_reason'])

        # 3. National Science Prize (Costs $300, treasury $0)
        tip_sci = get_button_tooltip_data('nat_science_prize', world, region=tile, nation=nation)
        self.assertIn('disabled_reason', tip_sci)
        self.assertIn("Insufficient Sovereign Treasury", tip_sci['disabled_reason'])

        # 4. Debt Panel: Lobby ISRB ($200 cost, $0 cash)
        tip_lobby = build_debt_tooltip('debt_lobby_isrb', world, nation=nation)
        self.assertIn('disabled_reason', tip_lobby)
        self.assertIn("Insufficient Sovereign Treasury", tip_lobby['disabled_reason'])

        # 5. Debt Panel: Board Seat ($600 cost, $0 cash)
        tip_seat = build_debt_tooltip('debt_board_seat', world, nation=nation)
        self.assertIn('disabled_reason', tip_seat)
        self.assertIn("Insufficient Sovereign Treasury", tip_seat['disabled_reason'])

        # 6. Military Panel: Recruit Unit ($15 cost, $0 cash)
        tip_mil = build_military_tooltip('mil_recruit_unit', world, region=tile, nation=nation)
        self.assertIn('disabled_reason', tip_mil)
        self.assertIn("Insufficient Sovereign Treasury", tip_mil['disabled_reason'])

        # 7. Rendering verification: draw_left_panel_tooltip renders without crash
        font = pygame.font.Font(None, 14)
        surf = pygame.Surface((1280, 720))
        world['_hovered_left_tooltip'] = tip_food
        draw_left_panel_tooltip(surf, world, font, mouse_pos=(100, 200))


if __name__ == '__main__':
    unittest.main()
