"""
test_bond_announcements.py — Unit Tests for 1-Turn Bond Announcements & Autonomous AI Purchasing.

Verifies:
1. 1-Turn advance public announcement lifecycle (announced -> live -> filled).
2. Autonomous AI sovereign reserve purchasing on friendly relations (>= +0.10) & surplus cash (> $1,000).
3. AI refusal to purchase bonds from hostile/war rivals.
4. Fallback domestic commercial bank underwriting for unpurchased offerings after 2 turns.
5. Strict money conservation during cross-border autonomous settlement.
"""

import unittest
import pygame
from client.desktop.app import build_world_view
from sovereign_bonds import get_bond_market, BondOffering
from intents import IssueSovereignBondIntent, BuyForeignBondIntent
from diplomacy import get_diplomacy


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        sequence = clock['next']
        clock['next'] += 1
        self.rows.append({'event_id': f'test:{sequence}', **row})
        return self.rows[-1]['event_id']


class TestBondAnnouncements(unittest.TestCase):

    def setUp(self):
        pygame.init()
        pygame.font.init()

    def tearDown(self):
        market = get_bond_market()
        market.offerings.clear()
        market.bonds.clear()
        pygame.quit()

    def test_1_turn_announcement_lifecycle(self):
        """Verify that bond offerings are announced 1 turn before going live."""
        world = build_world_view(seed=42)
        nations = world['nations']
        issuer = nations[0]
        market = get_bond_market()
        market.offerings.clear()
        market.bonds.clear()

        # Turn 1: Announce $1,000 50t Bond
        ok, msg, off = market.announce_bond_offering(issuer, principal=1000.0, duration_turns=50, t=1, world=world)
        self.assertTrue(ok)
        self.assertIsNotNone(off)
        self.assertEqual(off.status, "announced")
        self.assertEqual(off.announced_turn, 1)
        self.assertEqual(off.live_turn, 2)

        # In Turn 1, offering is announced, not yet live
        self.assertEqual(len(market.get_announced_offerings()), 1)
        self.assertEqual(len(market.get_live_offerings()), 0)

        # Step to Turn 2: offering should go live
        market.step(world, t=2)
        self.assertEqual(off.status, "live")
        self.assertEqual(len(market.get_live_offerings()), 1)

    def test_autonomous_friendly_ai_bond_purchasing(self):
        """Verify friendly AI with surplus cash autonomously purchases a live bond offering."""
        world = build_world_view(seed=42)
        nations = world['nations']
        player_nation = nations[0]
        ai_nation = nations[1]
        world['player_nation_name'] = player_nation.name

        market = get_bond_market()
        market.offerings.clear()
        market.bonds.clear()
        diplomacy = get_diplomacy()

        # Set friendly diplomatic relations (+0.50)
        diplomacy.set_relation(ai_nation.name, player_nation.name, 0.50)

        # Fund AI nation with surplus cash
        ai_nation.government.agent.cash = 2500.0
        player_init_cash = player_nation.government.agent.cash

        # Player announces a $500 20t bond at Turn 1
        market.announce_bond_offering(player_nation, principal=500.0, duration_turns=20, t=1, world=world)

        # Step to Turn 2: Offering goes live and AI purchases it
        ai_cash_before = ai_nation.government.agent.cash
        market.step(world, t=2)

        # Verify offering was filled by AI
        offering = market.offerings[0]
        self.assertEqual(offering.status, "filled")

        # Verify money transfer and bond creation (including turn 2 coupon payment)
        held_by_ai = market.get_bonds_held_by(ai_nation.name)
        self.assertEqual(len(held_by_ai), 1)
        coupon = held_by_ai[0].per_turn_coupon
        self.assertAlmostEqual(ai_cash_before - ai_nation.government.agent.cash, 500.0 - coupon, places=2)
        self.assertAlmostEqual(player_nation.government.agent.cash - player_init_cash, 500.0 - coupon, places=2)
        self.assertEqual(held_by_ai[0].issuer_nation, player_nation.name)
        self.assertEqual(held_by_ai[0].holder_nation, ai_nation.name)

    def test_foreign_bond_cash_legs_share_an_auditable_operation(self):
        world = build_world_view(seed=42)
        issuer, buyer = world['nations'][0], world['nations'][1]
        market = get_bond_market()
        market.offerings.clear()
        market.bonds.clear()
        trace = MemoryTrace()
        clock = {'turn': 2, 'phase': 'finance', 'next': 1}
        for nation in world['nations']:
            for tile in nation.tiles:
                tile._run_trace = trace
                tile._collective_trace_clock = clock

        buyer.government.agent.cash = 2500.0
        buyer_before = buyer.government.agent.cash
        issuer_before = issuer.government.agent.cash
        ok, _, offering = market.announce_bond_offering(
            issuer, principal=500.0, duration_turns=20, t=1, world=world)
        self.assertTrue(ok)
        offering.status = 'live'
        ok, _, bond = market.purchase_live_offering(
            buyer, offering.offering_id, world, t=2)
        self.assertTrue(ok)

        flows = [row for row in trace.rows
                 if row.get('metric_id') == 'finance.treasury_flow']
        self.assertEqual(len(flows), 2)
        contracts = [row['inputs']['transfer_contract'] for row in flows]
        self.assertEqual({contract['operation_id'] for contract in contracts},
                         {f'bond:{bond.bond_id}:principal_issue:principal'})
        by_side = {contract['side']: contract for contract in contracts}
        self.assertEqual(set(by_side), {'payer', 'payee'})
        self.assertEqual(by_side['payer']['payer_account']['id'], buyer.name)
        self.assertEqual(by_side['payee']['payee_account']['id'], issuer.name)
        self.assertAlmostEqual(by_side['payer']['payer_account']['balance_before'],
                               buyer_before)
        self.assertAlmostEqual(by_side['payer']['payer_account']['balance_after'],
                               buyer_before - 500.0)
        self.assertAlmostEqual(by_side['payee']['payee_account']['balance_before'],
                               issuer_before)
        self.assertAlmostEqual(by_side['payee']['payee_account']['balance_after'],
                               issuer_before + 500.0)
        self.assertAlmostEqual(sum(row['after'] for row in flows), 0.0)

        market.step(world, t=3)
        coupon_flows = [row for row in trace.rows
                        if row.get('metric_id') == 'finance.treasury_flow'
                        and row.get('kind') in (
                            'sovereign_bond_coupon_paid',
                            'sovereign_bond_coupon_received')]
        self.assertEqual(len(coupon_flows), 2)
        coupon_contracts = [row['inputs']['transfer_contract']
                            for row in coupon_flows]
        self.assertEqual(len({row['operation_id'] for row in coupon_contracts}), 1)
        self.assertTrue(all(row['funding_components'] for row in coupon_contracts))

    def test_municipal_sewer_bond_names_unmatched_credit_source(self):
        world = build_world_view(seed=42)
        issuer = world['nations'][0]
        tile = issuer.tiles[0]
        market = get_bond_market()
        market.offerings.clear()
        market.bonds.clear()
        trace = MemoryTrace()
        clock = {'turn': 1, 'phase': 'finance', 'next': 1}
        tile._run_trace = trace
        tile._collective_trace_clock = clock

        ok, _, bond = market.issue_municipal_sewer_bond(issuer, tile, t=1,
                                                        world=world)
        self.assertTrue(ok)
        creation = next(row for row in trace.rows
                        if row.get('metric_id') == 'finance.cash_creation')
        bond_record = next(row for row in trace.rows
                           if row.get('kind') == 'municipal_sewer_bond_underwritten')
        self.assertEqual(creation['after'], bond.principal)
        self.assertEqual(creation['inputs']['bond_id'], bond.bond_id)
        self.assertEqual(creation['inputs']['reconciliation_status'],
                         'cash_credit_without_recorded_source_debit')
        self.assertEqual(creation['inputs']['operation_id'],
                         bond_record['inputs']['operation_id'])

    def test_unconverted_cross_currency_bond_leg_is_flagged(self):
        world = build_world_view(seed=42)
        issuer, buyer = world['nations'][0], world['nations'][1]
        issuer.currency = 'USD'
        buyer.currency = 'GBP'
        market = get_bond_market()
        market.offerings.clear()
        market.bonds.clear()
        trace = MemoryTrace()
        clock = {'turn': 2, 'phase': 'finance', 'next': 1}
        for nation in world['nations']:
            for tile in nation.tiles:
                tile._run_trace = trace
                tile._collective_trace_clock = clock
        buyer.government.agent.cash = 2500.0
        ok, _, offering = market.announce_bond_offering(
            issuer, principal=500.0, duration_turns=20, t=1, world=world)
        self.assertTrue(ok)
        offering.status = 'live'
        ok, _, _ = market.purchase_live_offering(
            buyer, offering.offering_id, world, t=2)
        self.assertTrue(ok)
        payer_flow = next(row for row in trace.rows
                          if row.get('metric_id') == 'finance.treasury_flow'
                          and row['inputs']['transfer_contract']['side'] == 'payer')
        contract = payer_flow['inputs']['transfer_contract']
        self.assertEqual(contract['local_cash_leg_currency'], 'GBP')
        self.assertEqual(contract['amount_currency'], 'USD')
        self.assertTrue(contract['unconverted_currency_mismatch'])
        self.assertFalse(contract['currency_conversion_applied'])

    def test_ai_refuses_to_buy_hostile_bonds(self):
        """Verify AI will NOT buy bonds from hostile rivals or during war."""
        world = build_world_view(seed=42)
        nations = world['nations']
        player_nation = nations[0]
        ai_nation = nations[1]
        world['player_nation_name'] = player_nation.name

        market = get_bond_market()
        market.offerings.clear()
        market.bonds.clear()
        diplomacy = get_diplomacy()

        # Set hostile relations (-0.60)
        diplomacy.set_relation(ai_nation.name, player_nation.name, -0.60)
        ai_nation.government.agent.cash = 3000.0

        market.announce_bond_offering(player_nation, principal=500.0, duration_turns=20, t=1, world=world)

        # Step to Turn 2
        market.step(world, t=2)

        # Offering should remain live and UNFILLED by the hostile AI
        offering = market.offerings[0]
        self.assertEqual(offering.status, "live")
        self.assertEqual(len(market.get_bonds_held_by(ai_nation.name)), 0)

    def test_domestic_commercial_bank_fallback_underwrite(self):
        """Verify that unsold live offerings are underwritten by domestic banks after 2 turns."""
        world = build_world_view(seed=42)
        nations = world['nations']
        player_nation = nations[0]
        ai_nation = nations[1]
        world['player_nation_name'] = player_nation.name

        market = get_bond_market()
        market.offerings.clear()
        market.bonds.clear()
        diplomacy = get_diplomacy()

        # Make AI too poor to buy
        ai_nation.government.agent.cash = 20.0
        player_cash_start = player_nation.government.agent.cash

        market.announce_bond_offering(player_nation, principal=500.0, duration_turns=20, t=1, world=world)

        # Turn 2: Goes live (unfilled)
        market.step(world, t=2)
        self.assertEqual(market.offerings[0].status, "live")

        # Turn 3: Still live
        market.step(world, t=3)

        # Turn 4: Reaches live_turn + 2 -> Domestic commercial banks underwrite
        market.step(world, t=4)
        self.assertEqual(market.offerings[0].status, "filled")

        owed = market.get_bonds_owed_by(player_nation.name)
        self.assertEqual(len(owed), 1)
        self.assertEqual(owed[0].holder_nation, "Domestic Commercial Banks")
        coupon = owed[0].per_turn_coupon
        self.assertAlmostEqual(player_nation.government.agent.cash - player_cash_start, 500.0 - coupon, places=2)


if __name__ == "__main__":
    unittest.main()
