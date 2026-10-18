"""
test_banking_contagion.py — Tests for Domestic Banking Contagion, Corralito Freezes, and Resolution Decrees.
"""

import unittest
from types import SimpleNamespace
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
        writeoff = next(event for event in self.tile1.economic_events
                        if event['kind'] == 'bank_bond_writeoff')
        self.assertEqual(writeoff['asset_id'], 'bnd_crisis')
        self.assertEqual(writeoff['turn'], 20)
        self.assertEqual(writeoff['detail']['issuer_nation'], self.nation.name)
        self.assertEqual(writeoff['detail']['default_kind'], 'principal_default')
        self.assertEqual(writeoff['amount'], 1250.0)

    def test_bond_write_down_records_auditable_financial_trace(self):
        class Recorder:
            def __init__(self):
                self.rows = []

            def emit(self, clock, **row):
                self.rows.append({'turn': clock['turn'], **row})

        tile = self.tile1
        tile._collective_trace_clock = {'turn': 12, 'next': 1, 'phase': 'finance'}
        tile._run_trace = Recorder()
        was_frozen = tile.bank.write_down_bonds(
            250.0, trace_region=tile, bond_id='bnd_audit',
            issuer_nation=self.nation.name, default_kind='coupon_default',
            defaulted_amount=5.0, turn=12)

        event = tile.economic_events[-1]
        self.assertFalse(was_frozen)
        self.assertEqual(event['kind'], 'bank_bond_writeoff')
        self.assertEqual(event['asset_id'], 'bnd_audit')
        self.assertEqual(event['amount'], 250.0)
        self.assertEqual(event['currency'], getattr(tile, 'home_currency', None))
        self.assertEqual(event['detail']['defaulted_amount'], 5.0)
        self.assertEqual(event['detail']['capital_before'], 2000.0)
        self.assertEqual(event['detail']['capital_after'], 1750.0)
        self.assertEqual(event['detail']['equity_before'], 2000.0)
        self.assertEqual(event['detail']['equity_after'], 1750.0)
        self.assertEqual([row['metric_id'] for row in tile._run_trace.rows],
                         ['finance.bank_capital', 'finance.bank_bond_writeoff'])
        writeoff_trace = tile._run_trace.rows[1]
        self.assertEqual(writeoff_trace['after'], 250.0)
        self.assertEqual(writeoff_trace['inputs']['bond_id'], 'bnd_audit')
        self.assertEqual(writeoff_trace['inputs']['default_kind'], 'coupon_default')

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

    def test_frozen_withdrawal_trace_records_cap_and_reason(self):
        class Recorder:
            def __init__(self):
                self.rows = []

            def emit(self, clock, **row):
                self.rows.append({'turn': clock['turn'], **row})

        tile = self.tile1
        tile.home_currency = 'USD'
        tile._collective_trace_clock = {'turn': 7, 'next': 1, 'phase': 'finance'}
        tile._run_trace = Recorder()
        bank = tile.bank
        bank.capital = -100.0
        bank.is_frozen = True
        depositor = Agent(1)
        depositor.cash = 0.0
        bank.deposits[depositor] = 200.0
        bank.total_deposits = 200.0

        settled = bank.Withdraw(depositor, 50.0, trace_region=tile, t=7,
                                reason='panic_bank_run')

        self.assertEqual(settled, 5.0)
        event = tile.economic_events[-1]
        self.assertEqual(event['kind'], 'bank_withdrawal')
        self.assertEqual(event['asset_id'], 'bank:City1')
        self.assertEqual(event['detail']['requested_amount'], 50.0)
        self.assertEqual(event['detail']['settled_amount'], 5.0)
        self.assertEqual(event['detail']['reason'], 'panic_bank_run')
        trace = tile._run_trace.rows[-1]
        self.assertEqual(trace['kind'], 'bank_withdrawal_posted')
        self.assertEqual(trace['inputs']['frozen_withdrawal_cap'], 5.0)
        self.assertEqual(trace['inputs']['requested_amount'], 50.0)
        self.assertEqual(trace['inputs']['settled_amount'], 5.0)
        self.assertEqual(trace['inputs']['reason'], 'panic_bank_run')

    def test_bank_recapitalization_bailout_decree(self):
        class MemoryTrace:
            def __init__(self):
                self.rows = []

            def emit(self, clock, **row):
                sequence = clock['next']
                clock['next'] += 1
                event_id = f'test:{sequence}'
                self.rows.append({'event_id': event_id, **row})
                return event_id

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
        trace = MemoryTrace()
        clock = {'turn': 8, 'phase': 'finance', 'next': 1}
        for tile in (self.tile1, self.tile2):
            tile._run_trace = trace
            tile._collective_trace_clock = clock

        ok, msg = recapitalize_domestic_banks(self.nation, target_capital=500.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(gov.cash, 950.0)  # 2000 - 1050 = 950
        self.assertAlmostEqual(bank1.capital, 500.0)
        self.assertAlmostEqual(bank2.capital, 500.0)
        self.assertFalse(bank1.is_frozen)  # Corralito lifted!
        flows = [row for row in trace.rows
                 if row.get('metric_id') == 'finance.treasury_flow'
                 and row.get('kind') == 'bank_recapitalization_funding']
        bank_changes = [row for row in trace.rows
                        if row.get('kind') == 'bank_recapitalization'
                        and row.get('metric_id') == 'finance.bank_capital']
        self.assertEqual(len(flows), 2)
        self.assertEqual(len(bank_changes), 2)
        self.assertAlmostEqual(sum(row['after'] for row in flows), -1050.0)
        by_operation = {row['inputs']['operation_id']: row for row in bank_changes}
        self.assertEqual(set(by_operation), {
            row['inputs']['transfer_contract']['operation_id'] for row in flows})
        for flow in flows:
            contract = flow['inputs']['transfer_contract']
            bank_change = by_operation[contract['operation_id']]
            amount = contract['amount']
            self.assertEqual(contract['contract_version'], 'treasury_transfer.v1')
            self.assertAlmostEqual(
                contract['payer_account']['balance_before']
                - contract['payer_account']['balance_after'], amount)
            self.assertAlmostEqual(
                contract['payee_account']['balance_after']
                - contract['payee_account']['balance_before'], amount)
            self.assertEqual(flow['cause_event_ids'], [bank_change['event_id']])
            self.assertEqual(bank_change['inputs']['operation_id'],
                             contract['operation_id'])

    def test_deposit_bailin_haircut_decree(self):
        class MemoryTrace:
            def __init__(self):
                self.rows = []

            def emit(self, clock, **row):
                sequence = clock['next']
                clock['next'] += 1
                event_id = f'test:{sequence}'
                self.rows.append({'event_id': event_id, **row})
                return event_id

        bank = self.tile1.bank
        bank.capital = -50.0
        bank.is_frozen = True

        rich_depositor = Agent(2)
        bank.deposits[rich_depositor] = 500.0
        bank.total_deposits = 500.0

        trace = MemoryTrace()
        clock = {'turn': 9, 'phase': 'banking_policy', 'next': 1}
        self.tile1.home_currency = 'USD'
        self.tile1._run_trace = trace
        self.tile1._collective_trace_clock = clock
        self.nation.legitimacy = 0.7
        bourgeoisie = SimpleNamespace(name='Bourgeoisie', loyalty=0.8)
        workers = SimpleNamespace(name='Labor', loyalty=0.6)
        self.nation.factions = [bourgeoisie, workers]

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
        transfer = next(row for row in trace.rows
                        if row.get('metric_id') == 'finance.bank_bailin_transfer')
        contract = transfer['inputs']['transfer_contract']
        aggregate = next(row for row in trace.rows
                         if row.get('kind') == 'bank_depositor_bail_in'
                         and row.get('metric_id') == 'finance.bank_capital')
        self.assertEqual(contract['contract_version'], 'bank_bailin.v1')
        self.assertFalse(contract['cash_movement'])
        self.assertEqual(contract['amount'], 112.5)
        self.assertEqual(contract['payer_account']['balance_before'], 500.0)
        self.assertEqual(contract['payer_account']['balance_after'], 387.5)
        self.assertEqual(contract['payee_account']['balance_before'], -50.0)
        self.assertEqual(contract['payee_account']['balance_after'], 62.5)
        self.assertEqual(aggregate['inputs']['deposit_transfer_event_ids'],
                         [transfer['event_id']])
        loyalty = {row['inputs']['faction']: row for row in trace.rows
                   if row.get('metric_id') == 'politics.faction_loyalty'}
        self.assertAlmostEqual(loyalty['Bourgeoisie']['after'], 0.55)
        self.assertAlmostEqual(loyalty['Labor']['after'], 0.55)
        self.assertEqual(loyalty['Bourgeoisie']['cause_event_ids'],
                         [aggregate['event_id']])
        legitimacy = next(row for row in trace.rows
                          if row.get('metric_id') == 'politics.legitimacy')
        self.assertAlmostEqual(legitimacy['before'], 0.7)
        self.assertAlmostEqual(legitimacy['after'], 0.55)
        self.assertEqual(legitimacy['cause_event_ids'], [aggregate['event_id']])


if __name__ == '__main__':
    unittest.main()
