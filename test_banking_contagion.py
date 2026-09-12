"""
test_banking_contagion.py — Tests for Domestic Banking Contagion, Corralito Freezes, and Resolution Decrees.
"""

import unittest
from agent import Agent
from nation import Nation
from econsim_trade_money import Bank
from sovereign_bonds import SovereignBond, BondOffering, get_bond_market
from banking_policy import (
    get_banking_system_health,
    recapitalize_domestic_banks,
    enact_deposit_bailin_haircut,
)


class MockTile:
    def __init__(self, name="BankCity"):
        self.name = name
        self.bank = Bank()
        self.agents = []
        self.owner_nation = None


class TestBankingContagion(unittest.TestCase):

    def setUp(self):
        self.nation = Nation("Sovereignia")
        self.tile1 = MockTile("City1")
        self.tile2 = MockTile("City2")
        self.tile1.owner_nation = self.nation
        self.tile2.owner_nation = self.nation
        self.nation.tiles = [self.tile1, self.tile2]

    def test_domestic_underwriting_and_coupon_distribution(self):
        market = get_bond_market()
        world = {'nations': [self.nation], 'turn': 10}

        offering = BondOffering(
            offering_id="off_test_1",
            issuer_nation=self.nation.name,
            principal=1000.0,
            coupon_rate=0.002,
            duration_turns=20,
            announced_turn=7,
            live_turn=8,
            status="live"
        )
        market.offerings = [offering]
        market.bonds = []

        # Step at t=10 (live_turn + 2 = 10, triggers domestic bank underwrite)
        market.step(world, 10)

        # Bond should now be filled by Domestic Commercial Banks
        self.assertEqual(offering.status, "filled")
        self.assertEqual(len(market.bonds), 1)
        bond = market.bonds[0]
        self.assertEqual(bond.holder_nation, "Domestic Commercial Banks")

        # Each tile's bank should hold half the principal ($500)
        self.assertEqual(len(self.tile1.bank.sovereign_bonds_held), 1)
        self.assertEqual(len(self.tile2.bank.sovereign_bonds_held), 1)
        self.assertEqual(self.tile1.bank.sovereign_bonds_held[0]['principal'], 500.0)
        self.assertEqual(self.tile2.bank.sovereign_bonds_held[0]['principal'], 500.0)

        # Test coupon distribution to bank capital
        init_cap1 = self.tile1.bank.capital
        init_cap2 = self.tile2.bank.capital
        self.nation.government.agent.cash = 100.0

        # Step at t=11 (coupon servicing)
        market.step(world, 11)

        coupon = bond.per_turn_coupon  # 1000 * 0.002 = 2.0
        self.assertAlmostEqual(self.tile1.bank.capital, init_cap1 + coupon / 2)
        self.assertAlmostEqual(self.tile2.bank.capital, init_cap2 + coupon / 2)

    def test_sovereign_default_wipes_capital_and_triggers_corralito(self):
        market = get_bond_market()
        world = {'nations': [self.nation], 'turn': 20}

        # Domestic bank holds a $2,500 sovereign bond
        self.tile1.bank.capital = 1000.0
        self.tile1.bank.sovereign_bonds_held = [{
            'bond_id': 'bnd_crisis',
            'principal': 2500.0,
            'coupon': 5.0,
            'duration_turns': 20
        }]

        bond = SovereignBond(
            bond_id='bnd_crisis',
            issuer_nation=self.nation.name,
            holder_nation="Domestic Commercial Banks",
            principal=2500.0,
            coupon_rate=0.002,
            duration_turns=20,
            issued_turn=0,
            maturity_turn=20,
            status="active"
        )
        market.bonds = [bond]
        market.offerings = []

        # Government has 0 cash (will default on principal at maturity turn 20)
        self.nation.government.agent.cash = 0.0

        # Step at maturity
        market.step(world, 20)

        self.assertEqual(bond.status, "defaulted")
        # Bank takes loss: capital was 1000.0, loss is 2500 / 2 = 1250.0
        # Wait, tiles=[tile1, tile2], so loss per bank is 2500/2 = 1250.0
        # tile1 capital: 1000 - 1250 = -250.0
        self.assertLessEqual(self.tile1.bank.capital, 0.0)
        self.assertTrue(self.tile1.bank.is_frozen)

    def test_corralito_credit_crunch_and_withdrawal_clamp(self):
        bank = self.tile1.bank
        bank.capital = -100.0
        bank.is_frozen = True

        depositor = Agent(1)
        depositor.cash = 0.0
        bank.deposits[depositor] = 200.0
        bank.total_deposits = 200.0

        # 1. Borrowing must be completely blocked (credit crunch)
        borrowed = bank.Borrow(1, depositor, 50.0)
        self.assertEqual(borrowed, 0.0)
        self.assertEqual(depositor.cash, 0.0)

        # 2. Withdrawals must be clamped to subsistence cap ($5.0)
        bank.Withdraw(depositor, 50.0)
        self.assertEqual(depositor.cash, 5.0)  # Clamped to $5
        self.assertEqual(bank.deposits[depositor], 195.0)
        self.assertEqual(bank.total_deposits, 195.0)  # Conserved

    def test_bank_recapitalization_bailout_decree(self):
        bank1 = self.tile1.bank
        bank1.capital = -150.0
        bank1.is_frozen = True

        bank2 = self.tile2.bank
        bank2.capital = 100.0
        bank2.is_frozen = False

        # Target capital is 500.0
        # bank1 shortfall: 500 - (-150) = 650.0
        # bank2 shortfall: 500 - 100 = 400.0
        # Total needed: 1050.0

        gov = self.nation.government.agent
        gov.cash = 2000.0

        ok, msg = recapitalize_domestic_banks(self.nation, target_capital=500.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(gov.cash, 950.0)  # 2000 - 1050 = 950
        self.assertAlmostEqual(bank1.capital, 500.0)
        self.assertAlmostEqual(bank2.capital, 500.0)
        self.assertFalse(bank1.is_frozen)  # Corralito lifted!

    def test_deposit_bailin_haircut_decree(self):
        bank = self.tile1.bank
        bank.capital = -50.0
        bank.is_frozen = True

        rich_depositor = Agent(2)
        bank.deposits[rich_depositor] = 500.0
        bank.total_deposits = 500.0

        # Haircut 25% on balances > 50: excess = 450, 25% = 112.50
        # 112.50 moved from deposits to capital
        # Capital becomes -50.0 + 112.50 = +62.50 > 0
        # Freeze lifted!
        ok, msg = enact_deposit_bailin_haircut(self.nation, haircut_pct=0.25, exemption_floor=50.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(bank.deposits[rich_depositor], 387.50)
        self.assertAlmostEqual(bank.total_deposits, 387.50)
        self.assertAlmostEqual(bank.capital, 62.50)
        self.assertFalse(bank.is_frozen)  # Solvency restored!


if __name__ == '__main__':
    unittest.main()
