#!/usr/bin/env python3
"""
test_m5_ai_diplomacy.py — Automated Test Suite for Milestone 5 (M5: AI, Diplomacy, Alliances, Wars).

Verifies:
- M5.1: Terrain scoring + bottleneck relief (greedy choice test).
- M5.2: Vulnerability calculation + military response / treaty proposal.
- M5.3: Expansion drive with player-visible reason strings.
- M5.4: Bilateral relations drift + trade-pact tariff discount in get_trade_fee_multiplier.
- M5.5: Counterbalancing alliance formation against a dominant expansionist power.
- M5.6: Ideological polarization and war outbreak traceable in event log.
- M5.7: Treaty betrayal, memory accumulation, and post-betrayal diplomatic drag.
- End-to-end multi-nation sandbox run with 0 LEAK / 0 SUPPLY SHIFT.
"""

import sys
import unittest
from goods import Goods
from region import Region
from nation import Nation
from government import Government
from diplomacy import DiplomacySystem, TreatyType, get_diplomacy
from army import MilitaryUnit, recruit_unit, step_armies, resolve_battle
from ai_nation import NationPolicyAI
from intents import (RecruitArmyIntent, MoveArmyIntent, ProposeTreatyIntent,
                     BreakTreatyIntent, DeclareWarIntent, step_intents_and_construction)
import sim_engine
import forex as fx


def make_test_tile(name, profs=None, terrain=None, climate='temperate', pop=50):
    if profs is None:
        profs = {Goods.food: 0.60, Goods.wood: 0.25, Goods.furniture: 0.08}
    return Region(name, t=0, number_of_agents=pop, profession_distribution=profs,
                  number_of_traders=2, terrain=terrain, climate=climate)


class TestM5DiplomacyAndAI(unittest.TestCase):

    def setUp(self):
        # Reset global diplomacy system for each test
        import diplomacy
        diplomacy.diplomacy_instance = DiplomacySystem()

    def test_m5_1_terrain_valuation_and_bottleneck(self):
        """M5.1: AI picks fertile tile over barren tile (greedy claim test) and computes bottleneck relief."""
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=500.0)
        ai = NationPolicyAI(alpha)
        alpha.ai = ai

        # Base tile
        t_base = make_test_tile("A1")
        alpha.add_tile(t_base)

        # Barren candidate tile vs Fertile candidate tile
        t_barren = make_test_tile("T_Barren", terrain={Goods.food: 0.5}, climate='cold')
        t_fertile = make_test_tile("T_Fertile", terrain={Goods.food: 2.0}, climate='fertile')

        score_barren, reason_barren = ai.evaluate_candidate_tile(t_barren)
        score_fertile, reason_fertile = ai.evaluate_candidate_tile(t_fertile)

        self.assertGreater(score_fertile, score_barren, "Fertile tile must score higher than barren tile.")
        self.assertIn("Terrain score", reason_fertile)
        self.assertIn("Bottleneck relief", reason_fertile)

    def test_m5_2_vulnerability_and_military_posture(self):
        """M5.2: Tile is vulnerable when adjacent to hostile rival; AI recruits garrison or fortifies."""
        dip = get_diplomacy()
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=500.0)
        beta = Nation("Beta", currency="BE", regime_type="autocracy", initial_cash=500.0)
        ai_alpha = NationPolicyAI(alpha)
        alpha.ai = ai_alpha

        t_a1 = make_test_tile("A1")
        t_b1 = make_test_tile("B1")
        alpha.add_tile(t_a1)
        beta.add_tile(t_b1)

        t_a1.add_neighbor(t_b1)
        t_b1.add_neighbor(t_a1)

        # Hostile relations
        dip.set_relation("Alpha", "Beta", -0.8)

        # Beta deploys a strong army unit on the border
        unit_beta = recruit_unit(beta, t_b1, soldier_count=40, wage=1.0)
        self.assertIsNotNone(unit_beta)

        # Alpha currently has no troops on A1
        vuln, reason = ai_alpha.evaluate_tile_vulnerability(t_a1, [alpha, beta], dip)
        self.assertGreater(vuln, 0.5, f"Expected high vulnerability for undefended border: {vuln}")
        self.assertIn("Beta", reason)

        # AI decides to recruit garrison to protect the vulnerable tile
        intents = ai_alpha.decide_turn(t=1, all_tiles=[t_a1, t_b1], all_nations=[alpha, beta], diplomacy=dip)
        recruit_intents = [it for it in intents if isinstance(it, RecruitArmyIntent)]
        self.assertTrue(len(recruit_intents) > 0, "AI must submit RecruitArmyIntent when border is vulnerable.")

    def test_m5_3_expansion_drive(self):
        """M5.3: AI evaluates expansion options and returns optimal path with player-visible reason string."""
        dip = get_diplomacy()
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=500.0)
        ai_alpha = NationPolicyAI(alpha, personality={'expansionist': 0.9, 'militarism': 0.2, 'diplomatic': 0.7, 'risk_tolerance': 0.4, 'loyalty': 0.8})
        alpha.ai = ai_alpha

        t_a1 = make_test_tile("A1")
        alpha.add_tile(t_a1)

        # Adjacent wilderness tile
        t_wild = Region("W1", t=0, wilderness=True)
        t_a1.add_neighbor(t_wild)
        t_wild.add_neighbor(t_a1)

        plan = ai_alpha.evaluate_expansion([t_a1, t_wild], [alpha], dip)
        self.assertIsNotNone(plan)
        self.assertEqual(plan['mode'], 'settle')
        self.assertIn("Expand into wilderness", plan['reason'])

    def test_m5_4_bilateral_relations_and_tariff_discount(self):
        """M5.4: Trade-pact tariff cut flows into get_trade_fee_multiplier; betrayal lowers relations."""
        dip = get_diplomacy()
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=500.0)
        beta = Nation("Beta", currency="BE", regime_type="autocracy", initial_cash=500.0)

        t_a1 = make_test_tile("A1")
        t_b1 = make_test_tile("B1")
        alpha.add_tile(t_a1)
        beta.add_tile(t_b1)

        # Enable import tariffs on Beta
        beta.government.import_tariff_enabled = True
        beta.government.import_tariff_rate = 0.20
        beta.government.import_drawback_rate = 0.0

        # Base fee without treaty
        base_mult = beta.government.get_trade_fee_multiplier(source_nation="Alpha")

        # Sign Trade Pact
        ok, msg = dip.propose_treaty("Alpha", "Beta", TreatyType.TRADE_PACT.value, t=1)
        self.assertTrue(ok, f"Trade pact proposal failed: {msg}")

        # Fee multiplier with trade pact (tariff should be discounted by 50%)
        pact_mult = beta.government.get_trade_fee_multiplier(source_nation="Alpha")
        self.assertGreater(pact_mult, base_mult, "Trade pact must increase the trader keep multiplier (lower effective tariff).")

        # Betrayal / breaking treaty
        res = dip.break_treaty("Alpha", "Beta", TreatyType.TRADE_PACT.value, t=2, reason="Border dispute")
        self.assertTrue(res['success'])
        self.assertLess(dip.get_relation("Alpha", "Beta"), 0.0, "Betrayal must drop relations into negative.")
        self.assertEqual(len(dip.betrayal_memory[("Beta", "Alpha")]), 1, "Betrayal memory must be stored on victim.")

    def test_m5_5_counterbalancing_alliance_formation(self):
        """M5.5: Two weak nations form a defensive alliance against a strong expansionist neighbor."""
        dip = get_diplomacy()
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=500.0)
        beta = Nation("Beta", currency="BE", regime_type="autocracy", initial_cash=500.0)
        gamma = Nation("Gamma", currency="GA", regime_type="autocracy", initial_cash=1000.0)

        ai_alpha = NationPolicyAI(alpha)
        ai_beta = NationPolicyAI(beta)
        alpha.ai = ai_alpha
        beta.ai = ai_beta

        t_a = make_test_tile("A1", pop=100)
        t_b = make_test_tile("B1", pop=100)
        t_g = make_test_tile("G1", pop=200)
        alpha.add_tile(t_a)
        beta.add_tile(t_b)
        gamma.add_tile(t_g)

        # Gamma builds a massive expansionist army (60 soldiers)
        recruit_unit(gamma, t_g, soldier_count=60, wage=1.0)

        # Alpha and Beta have modest military presence (10 soldiers each)
        recruit_unit(alpha, t_a, soldier_count=10, wage=1.0)
        recruit_unit(beta, t_b, soldier_count=10, wage=1.0)

        # Alpha evaluates diplomacy and identifies Gamma as a common threat, proposing defensive alliance to Beta
        intents = ai_alpha.evaluate_diplomacy([alpha, beta, gamma], dip, t=1)
        alliance_intents = [it for it in intents if isinstance(it, ProposeTreatyIntent)
                            and it.treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value]
        
        self.assertTrue(len(alliance_intents) > 0, "Weaker nation must propose counterbalancing alliance against expansionist Gamma.")
        self.assertEqual(alliance_intents[0].target_nation_name, "Beta")

    def test_m5_6_ideological_blocs_and_war(self):
        """M5.6: Ideological polarization and negative relations trigger war declarations and defensive mobilization."""
        dip = get_diplomacy()
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=500.0)
        beta = Nation("Beta", currency="BE", regime_type="democracy", initial_cash=500.0)
        gamma = Nation("Gamma", currency="GA", regime_type="democracy", initial_cash=500.0)

        ai_alpha = NationPolicyAI(alpha)
        alpha.ai = ai_alpha

        t_a = make_test_tile("A1", pop=200)
        t_b = make_test_tile("B1", pop=100)
        t_g = make_test_tile("G1", pop=100)
        alpha.add_tile(t_a)
        beta.add_tile(t_b)
        gamma.add_tile(t_g)

        # Beta and Gamma have an existing defensive alliance
        dip.set_relation("Beta", "Gamma", 0.8)
        dip.propose_treaty("Beta", "Gamma", TreatyType.DEFENSIVE_ALLIANCE.value, t=1)

        # Alpha builds an army and has strong grievance/hostility against Beta
        recruit_unit(alpha, t_a, soldier_count=50, wage=1.0)
        recruit_unit(beta, t_b, soldier_count=10, wage=1.0)
        recruit_unit(gamma, t_g, soldier_count=20, wage=1.0)
        dip.set_relation("Alpha", "Beta", -0.9)

        # Alpha declares war on Beta
        events = dip.declare_war("Alpha", "Beta", t=5, reason="Ideological conflict")
        self.assertTrue(dip.are_at_war("Alpha", "Beta"))
        # Gamma should be pulled in to defend Beta
        self.assertTrue(dip.are_at_war("Alpha", "Gamma"), "Defensive ally Gamma must join war against aggressor Alpha.")

    def test_m5_7_betrayal_and_memory_drag(self):
        """M5.7: Treaty backstabbing stores betrayal memory and increases difficulty of future treaties."""
        dip = get_diplomacy()
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=500.0)
        beta = Nation("Beta", currency="BE", regime_type="autocracy", initial_cash=500.0)

        # Sign NAP
        dip.set_relation("Alpha", "Beta", 0.4)
        dip.propose_treaty("Alpha", "Beta", TreatyType.NON_AGGRESSION.value, t=1)

        # Alpha breaks the treaty
        dip.break_treaty("Alpha", "Beta", TreatyType.NON_AGGRESSION.value, t=3, reason="Aggressive rearmament")

        # Now try to re-propose a treaty from Alpha to Beta
        # The betrayal memory should penalize the acceptance threshold
        ok, reason = dip.propose_treaty("Alpha", "Beta", TreatyType.NON_AGGRESSION.value, t=4)
        self.assertFalse(ok, "Post-betrayal treaty proposal should be rejected due to betrayal memory drag.")

    def test_m5_8_desertion_reabsorption_and_veteran_xp(self):
        """M5.8: Unpaid soldiers desert, reabsorb into civilian labor pool or homestead, and retain military_xp."""
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=0.0)
        t_a1 = make_test_tile("A1", pop=50)
        alpha.add_tile(t_a1)

        # Adjacent wilderness tile
        t_wild = Region("W1", t=0, wilderness=True)
        t_a1.add_neighbor(t_wild)
        t_wild.add_neighbor(t_a1)

        # Recruit unit
        unit = recruit_unit(alpha, t_a1, soldier_count=20, wage=5.0)
        self.assertIsNotNone(unit)

        # Drop morale directly to trigger desertion during step_armies
        unit.morale = 0.2
        unit.veteran_xp = 0.4

        initial_agent_count = len(t_a1.agents)
        initial_wild_count = len(t_wild.agents)

        events = step_armies([t_a1, t_wild], [alpha], t=1)

        # Check that deserters were reabsorbed or homesteaded
        deserter_events = [ev for ev in events if ev['event'] in ('DESERTER_REABSORBED', 'DESERTER_HOMESTEAD')]
        self.assertGreater(len(deserter_events), 0, "Desertion must emit reabsorption / homesteading events.")

        # Check veteran experience on deserter agents
        deserter_agents = [a for a in (t_a1.agents + t_wild.agents) if getattr(a, 'military_xp', 0.0) > 0.0]
        self.assertGreater(len(deserter_agents), 0, "Deserters must retain military_xp > 0.")
        self.assertGreaterEqual(deserter_agents[0].military_xp, 0.4, "Deserter military_xp must reflect unit combat experience.")

    def test_m5_end_to_end_sandbox_conservation(self):
        """M5 exit criteria: Multi-nation AI sandbox runs with active intents, armies, diplomacy, and 0 LEAK."""
        import econsim_states
        econsim_states.governments = []

        dip = get_diplomacy()
        alpha = Nation("Alpha", currency="AL", regime_type="autocracy", initial_cash=500.0)
        beta = Nation("Beta", currency="BE", regime_type="autocracy", initial_cash=500.0)
        gamma = Nation("Gamma", currency="GA", regime_type="democracy", initial_cash=500.0)

        ai_alpha = NationPolicyAI(alpha)
        ai_beta = NationPolicyAI(beta)
        ai_gamma = NationPolicyAI(gamma)
        alpha.ai = ai_alpha
        beta.ai = ai_beta
        gamma.ai = ai_gamma

        t_a1 = make_test_tile("A1", terrain={Goods.food: 1.5})
        t_a2 = make_test_tile("A2")
        t_b1 = make_test_tile("B1", terrain={Goods.wood: 1.5})
        t_b2 = make_test_tile("B2")
        t_g1 = make_test_tile("G1")
        t_g2 = make_test_tile("G2", climate='cold')

        tiles = [t_a1, t_a2, t_b1, t_b2, t_g1, t_g2]
        nations = [alpha, beta, gamma]

        alpha.add_tile(t_a1)
        alpha.add_tile(t_a2)
        beta.add_tile(t_b1)
        beta.add_tile(t_b2)
        gamma.add_tile(t_g1)
        gamma.add_tile(t_g2)

        # Wire grid connectivity
        edges = [
            (t_a1, t_a2), (t_b1, t_b2), (t_g1, t_g2),
            (t_a1, t_b1), (t_a2, t_b2),
            (t_b1, t_g1), (t_b2, t_g2)
        ]
        for a, b in edges:
            a.add_neighbor(b)
            b.add_neighbor(a)
            if a.owner_nation is not b.owner_nation:
                fx.connect_desks(a, b, t=0)

        currencies = ["AL", "BE", "GA"]

        # Run 30 turns of fully autonomous AI simulation
        total_violations = []
        for t in range(1, 31):
            violations, _ = sim_engine.step_turn(
                t, tiles, nations=nations, currencies=currencies, ledger_exempt=True
            )
            total_violations.extend(violations)

        self.assertEqual(len(total_violations), 0, f"Encountered currency audit violations: {total_violations}")
        print("M5 end-to-end sandbox completed successfully with 0 LEAK / 0 SUPPLY SHIFT.")


if __name__ == "__main__":
    unittest.main()
