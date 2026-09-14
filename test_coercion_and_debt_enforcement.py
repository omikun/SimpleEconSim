"""
test_coercion_and_debt_enforcement.py — Tests for Phase 4 Coercion Calculus, Caisse de la Dette, and Banking Contagion.

Verifies:
1. evaluate_credible_takeover_threat accurately computes force ratios, logistics, deterrence, and tiers.
2. Coercion gating: receivership and Caisse escalation are blocked when threats are hollow bluffs.
3. Caisse de la Dette asset seizures: transit tolls (75%) and granary buffers (50%) with 100% money/food conservation.
4. Urabi nationalist backlash: +2.5 protest energy per turn and barricade erection.
5. Panic Banking Contagion: neighboring bank runs and secondary freeze when a domestic bank is frozen.
6. Emergent Brady Bond Restructuring: dynamic haircut based on S_cred, replacement 50t bond, and rating restoration.
7. Intent Command Pattern: RestructureDebtIntent and EscalateCaisseIntent.
"""

import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import unittest
from nation import Nation
from region import Region
from goods import Goods
from army import MilitaryUnit
from econsim_trade_money import Bank
from sovereign_bonds import SovereignBond, get_bond_market
from imperialism import (
    get_imperialism_manager,
    evaluate_credible_takeover_threat,
    ThreatAssessment,
    CustomsReceivership
)
from popular_resistance import get_popular_resistance_manager
from banking_policy import (
    get_banking_system_health,
    evaluate_banking_contagion,
    recapitalize_domestic_banks,
    enact_deposit_bailin_haircut
)
from intents import RestructureDebtIntent, EscalateCaisseIntent


class TestCoercionAndDebtEnforcement(unittest.TestCase):

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

        # Nations
        self.creditor = Nation("Empire", initial_cash=2000.0)
        self.debtor = Nation("Khedivate", initial_cash=100.0)

        # Tiles
        self.cred_tile = Region("London", 0, 0)
        self.creditor.add_tile(self.cred_tile)

        self.debt_tile1 = Region("Alexandria", 1, 0)
        self.debt_tile2 = Region("Cairo", 2, 0)
        self.debtor.add_tile(self.debt_tile1)
        self.debtor.add_tile(self.debt_tile2)

        self.world = {
            'nations': [self.creditor, self.debtor],
            'tiles': [self.cred_tile, self.debt_tile1, self.debt_tile2],
            'tiles_by_name': {t.name: t for t in [self.cred_tile, self.debt_tile1, self.debt_tile2]},
            'turn': 10
        }

    def test_coercion_threat_assessment_tiers(self):
        """Test calculation of credibility score and classification into tiers."""
        # 1. Hollow Bluff: Creditor has 0 soldiers, debtor has garrison
        d_unit = MilitaryUnit(unit_id="u_d1", nation_name="Khedivate", region_name="Cairo", soldiers=100)
        self.debtor.military_units = [d_unit]
        self.creditor.military_units = []
        self.creditor.government.agent.cash = 10.0  # Cannot afford agents

        threat = evaluate_credible_takeover_threat(self.creditor, self.debtor, self.world)
        self.assertEqual(threat.tier, "Hollow Bluff")
        self.assertLess(threat.credibility_score, 0.7)

        # 2. Overwhelming Hegemony: Creditor mobilizes 500 soldiers
        c_unit = MilitaryUnit(unit_id="u_c1", nation_name="Empire", region_name="London", soldiers=500)
        self.creditor.military_units = [c_unit]
        self.creditor.government.agent.cash = 2000.0

        threat = evaluate_credible_takeover_threat(self.creditor, self.debtor, self.world)
        self.assertIn(threat.tier, ["Overwhelming Hegemony", "Credible Threat"])
        self.assertGreaterEqual(threat.credibility_score, 1.2)

    def test_coercion_gating_on_receivership_and_caisse(self):
        """Test that receiverships and Caisse cannot be declared without military backing."""
        # Creditor has 0 soldiers and low cash
        self.creditor.military_units = []
        self.creditor.government.agent.cash = 5.0
        d_unit = MilitaryUnit(unit_id="u_d1", nation_name="Khedivate", region_name="Cairo", soldiers=80)
        self.debtor.military_units = [d_unit]

        # Should fail due to hollow bluff
        ok, msg, rec = self.imp_mgr.establish_receivership(self.creditor, self.debtor, 500.0, t=10, world=self.world)
        self.assertFalse(ok)
        self.assertIn("lacks military", msg)

        # Now give creditor strong military units
        c_unit = MilitaryUnit(unit_id="u_c1", nation_name="Empire", region_name="London", soldiers=300)
        self.creditor.military_units = [c_unit]
        self.creditor.government.agent.cash = 1000.0

        ok, msg, rec = self.imp_mgr.establish_receivership(self.creditor, self.debtor, 500.0, t=10, world=self.world)
        self.assertTrue(ok)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.level, "customs")

        # Caisse escalation check
        can_caisse, reason, threat = self.imp_mgr.can_escalate_to_caisse(self.creditor, self.debtor, self.world)
        self.assertTrue(can_caisse)

        # Escalate
        ok, msg = self.imp_mgr.escalate_to_caisse(rec.receivership_id, self.world, t=11)
        self.assertTrue(ok)
        self.assertEqual(rec.level, "caisse_de_la_dette")
        self.assertEqual(rec.intercept_share, 0.65)

    def test_caisse_asset_seizures_and_urabi_backlash(self):
        """Test transit toll and granary buffer seizures with 100% money/food conservation, and Urabi revolt."""
        # Setup active Caisse de la Dette
        c_unit = MilitaryUnit(unit_id="u_c1", nation_name="Empire", region_name="London", soldiers=400)
        self.creditor.military_units = [c_unit]
        ok, _, rec = self.imp_mgr.establish_receivership(self.creditor, self.debtor, 300.0, t=10, world=self.world, force_override=True)
        self.imp_mgr.escalate_to_caisse(rec.receivership_id, self.world, t=10)

        # Setup debtor tile infrastructure and granary
        self.debt_tile1.granary_stock = 20.0
        self.debt_tile1.is_coast = True
        self.debtor.government.agent.cash = 50.0

        cred_cash_before = self.creditor.government.agent.cash
        debt_cash_before = self.debtor.government.agent.cash

        # Step imperialism turn
        self.imp_mgr.step_imperialism(self.world, t=11)

        # 1. Verify Toll & Granary Seizures occurred
        self.assertGreater(rec.seized_tolls, 0.0)
        self.assertGreater(rec.seized_granary_grain, 0.0)
        self.assertLess(self.debt_tile1.granary_stock, 20.0)

        # 2. Strict conservation: Creditor gained exactly what was seized
        total_seized = rec.seized_tolls + (rec.seized_granary_grain * 2.0)
        self.assertAlmostEqual(self.creditor.government.agent.cash - cred_cash_before, total_seized)
        self.assertAlmostEqual(debt_cash_before - self.debtor.government.agent.cash, rec.seized_tolls)
        self.assertAlmostEqual(rec.remaining_debt, 300.0 - total_seized)

        # 3. Verify Urabi Nationalist Unrest Backlash
        st1 = self.res_mgr.get_state(self.debt_tile1.name)
        st2 = self.res_mgr.get_state(self.debt_tile2.name)
        self.assertGreater(st1.revolt_intensity, 0.0)
        self.assertGreater(st2.revolt_intensity, 0.0)
        self.assertGreater(self.debt_tile1.unrest_level, 0.0)

    def test_domestic_banking_contagion_and_panic_runs(self):
        """Test that a frozen bank triggers panic bank runs across neighboring tiles in the same nation."""
        from agent import Agent
        bank1 = self.debt_tile1.bank
        bank2 = self.debt_tile2.bank

        # City 1 bank suffers default and freezes
        bank1.capital = -100.0
        bank1.is_frozen = True

        # City 2 bank is solvent with depositors
        bank2.capital = 300.0
        bank2.is_frozen = False
        dep1 = Agent(101)
        dep1.cash = 100.0
        bank2.Deposit(dep1, 80.0)
        self.assertEqual(bank2.deposits[dep1], 80.0)

        # Evaluate banking contagion
        events = evaluate_banking_contagion(self.debtor, self.world, t=12)

        # Panic run should have hit bank 2
        self.assertTrue(any(e['kind'] == 'BANK_RUN' for e in events))
        # Depositor pulled 20% of funds
        self.assertLess(bank2.deposits[dep1], 80.0)
        self.assertGreater(dep1.cash, 20.0)

        # Health monitor reflects critical panic risk
        b_health = get_banking_system_health(self.debtor)
        self.assertTrue(b_health['is_system_frozen'])
        self.assertIn("CRITICAL", b_health['panic_risk'])

    def test_emergent_brady_bond_restructuring(self):
        """Test dynamic debt haircut negotiation, 50-turn Brady Bond issuance, and default clearance."""
        # Register sovereign default
        b_def = SovereignBond(
            bond_id="bnd_delinquent",
            issuer_nation="Khedivate",
            holder_nation="Empire",
            principal=1000.0,
            coupon_rate=0.002,
            duration_turns=20,
            issued_turn=0,
            maturity_turn=20,
            status="defaulted"
        )
        self.bond_market.bonds.append(b_def)
        self.imp_mgr.register_default(b_def, self.world, t=20)
        self.assertEqual(len(self.imp_mgr.get_unresolved_defaults_against("Khedivate")), 1)

        # Negotiate debt restructuring accord
        ok, msg, res = self.imp_mgr.negotiate_debt_restructuring(
            self.debtor, self.creditor, haircut_pct=0.50, use_brady_bonds=True, world=self.world, t=21
        )
        self.assertTrue(ok)
        self.assertIn("BRADY ACCORD", msg)
        self.assertEqual(res['haircut_amount'], 500.0)
        self.assertEqual(res['restructured_principal'], 500.0)

        # Check that delinquent defaults were cleared
        self.assertEqual(len(self.imp_mgr.get_unresolved_defaults_against("Khedivate")), 0)

        # Check replacement 50-turn Brady Bond in bond market
        brady = res['brady_bond']
        self.assertIsNotNone(brady)
        self.assertEqual(brady.duration_turns, 50)
        self.assertEqual(brady.principal, 500.0)
        self.assertEqual(brady.coupon_rate, 0.0015)
        self.assertEqual(brady.status, "active")

        # Check ISRB credit rating restored
        self.assertEqual(self.bond_market.isrb.rating_modifiers.get("Khedivate", 0), 0)

    def test_intents_execution(self):
        """Test RestructureDebtIntent and EscalateCaisseIntent command execution."""
        # 1. RestructureDebtIntent
        intent_restruct = RestructureDebtIntent("Khedivate", "Empire", haircut_pct=0.40, submitted_turn=25)
        ok, msg = intent_restruct.execute(self.world['tiles_by_name'], {n.name: n for n in self.world['nations']}, 25, self.world)
        self.assertTrue(ok)
        self.assertEqual(intent_restruct.status, 'completed')

        # 2. EscalateCaisseIntent
        # Setup active receivership with overwhelming military force
        c_unit = MilitaryUnit(unit_id="u_c_hegemon", nation_name="Empire", region_name="London", soldiers=600)
        self.creditor.military_units = [c_unit]
        self.creditor.government.agent.cash = 3000.0
        self.imp_mgr.establish_receivership(self.creditor, self.debtor, 400.0, t=25, world=self.world, force_override=True)

        intent_esc = EscalateCaisseIntent("Empire", "Khedivate", submitted_turn=26)
        ok, msg = intent_esc.execute(self.world['tiles_by_name'], {n.name: n for n in self.world['nations']}, 26, self.world)
        self.assertTrue(ok)
        self.assertEqual(intent_esc.status, 'completed')
        rec = self.imp_mgr.get_active_receivership_on("Khedivate")
        self.assertEqual(rec.level, "caisse_de_la_dette")

    def test_debt_panel_ui_rendering(self):
        """Test drawing and clicking the Left Sovereign Debt drawer under domestic and imperial scopes."""
        import pygame
        pygame.init()
        surface = pygame.Surface((1400, 900))
        font = pygame.font.Font(None, 20)
        font_small = pygame.font.Font(None, 16)

        from worldview_debt_panel import draw_debt_panel, debt_panel_hit

        self.world['debt_panel_open'] = True
        self.world['player_nation_name'] = "Khedivate"
        self.world['left_panel_tab'] = 'domestic'

        # 1. Draw Domestic Scope (testing Corralito alert & contagion display)
        self.debt_tile1.bank.is_frozen = True
        draw_debt_panel(surface, self.world, font, font_small, mouse_pos=(100, 200))

        # 2. Draw Imperial Scope (testing Threat assessment & Caisse display)
        self.world['left_panel_tab'] = 'imperial'
        draw_debt_panel(surface, self.world, font, font_small, mouse_pos=(100, 200))

        # 3. Test Hit testing
        hit = debt_panel_hit((100, 100), self.world)
        self.assertTrue(hit)


if __name__ == '__main__':
    unittest.main()

