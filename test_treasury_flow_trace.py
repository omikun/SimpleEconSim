"""Settled public flows must explain changes without counting internal withdrawals."""
from pathlib import Path
import tempfile
import unittest

from agent import Agent
from econsim_trade_money import PayLoans
from nation import Nation
from region import Region
from run_trace import RunTrace


class TreasuryFlowTraceTests(unittest.TestCase):
    def world(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        trace = RunTrace(Path(directory.name) / 'public.ctr', 'public', recent_limit=10000)
        nation = Nation('Public', 'C', initial_cash=0, register=False)
        tile = Region('District', 0, 0)
        nation.add_tile(tile)
        clock = {'turn': 1, 'phase': 'finance', 'next': 1}
        tile._run_trace, tile._collective_trace_clock = trace, clock
        trace.bank_book.register_tiles([tile], clock)
        return nation, tile, trace, clock

    def flows(self, trace):
        return [row for row in trace.recent if row.get('metric_id') == 'finance.treasury_flow']

    def test_automatic_public_credit_interest_and_repayment(self):
        nation, tile, trace, _ = self.world()
        government = tile.gov.agent
        before = nation.treasury()['total']
        tile.bank.Borrow(1, government, 100, trace_region=tile)
        tile.bank.Deposit(government, 100, trace_region=tile)
        tile.bank.PayDepositInterest([government], trace_region=tile)
        PayLoans(government, bank=tile.bank, trace_region=tile, t=1)
        after = nation.treasury()['total']
        flows = self.flows(trace)
        self.assertEqual(3, len(flows))
        self.assertAlmostEqual(after - before, sum(row['value_after'] for row in flows))
        self.assertTrue(all(row['inputs']['government_id'] == government.id for row in flows))

    def test_fiscal_credit_has_one_flow_and_keeps_gap_link(self):
        from region_finance import collect_tax
        nation, tile, trace, _ = self.world()
        tile.gov.agent.cash = 0
        before = nation.treasury()['total']
        collect_tax(tile, 1)
        flows = self.flows(trace)
        self.assertAlmostEqual(nation.treasury()['total'] - before,
                               sum(row['value_after'] for row in flows))
        credits = [row for row in flows if row['kind'] == 'government_bank_borrowing']
        self.assertEqual(1, len(credits))
        self.assertTrue(credits[0]['cause_event_ids'])
        self.assertFalse(any(row['kind'] == 'government_automatic_bank_credit' for row in flows))

    def test_private_credit_is_not_public_revenue(self):
        nation, tile, trace, _ = self.world()
        person = Agent(0)
        before = nation.treasury()['total']
        tile.bank.Borrow(1, person, 100, trace_region=tile)
        self.assertEqual([], self.flows(trace))
        self.assertEqual(before, nation.treasury()['total'])

    def test_construction_debits_and_failed_rollback_match_observed_treasury(self):
        from test_build_intent_trace import _fixture
        for funding in ('cash', 'deposit', 'frozen_deposit', 'rollback'):
            with self.subTest(funding=funding):
                nation, _tile, _intent, _result, _state, trace = _fixture(funding=funding, traced=True)
                rows = trace.rows
                plan = next(row for row in rows if row['kind'] == 'construction_funding_plan')
                flows = [row for row in rows if row.get('metric_id') == 'finance.treasury_flow']
                self.assertAlmostEqual(nation.treasury()['total'] - plan['inputs']['treasury_total_before'],
                                       sum(row['after'] for row in flows))

    def test_enclosure_receipt_matches_public_balance_gain(self):
        from test_enclosure_payment_trace import _fixture
        from enclosure import execute_enclosure
        nation, tile, _lord, _recipient, plot, trace = _fixture(traced=True)
        before = nation.treasury()['total']
        self.assertTrue(execute_enclosure(tile, plot.plot_id, 10)[0])
        flows = [row for row in trace.rows if row.get('metric_id') == 'finance.treasury_flow']
        self.assertEqual(1, len(flows))
        self.assertEqual(nation.treasury()['total'] - before, flows[0]['after'])
        self.assertTrue(flows[0]['cause_event_ids'])

    def test_machinery_repair_receipt_to_treasury_is_attributed(self):
        from goods import Goods
        from labor_resistance import repair_and_replace_machinery

        nation, tile, trace, _clock = self.world()
        government = tile.gov.agent
        firm = Agent(900)
        firm.is_corporation = True
        firm.output = Goods.cloth
        firm.cash = 500.0
        firm.broken_machinery = 1
        firm.machinery_level = 0
        firm.employees = []
        tile.agents = [government, firm]
        tile.recipes.update({
            Goods.wood: {'price': 3.0, 'production': 1},
            Goods.furniture: {'price': 10.0, 'production': 1},
        })
        before = nation.treasury()['total']

        evidence = []
        repair_and_replace_machinery(firm, tile, 1, evidence)

        flows = self.flows(trace)
        receipt = next(row for row in flows
                       if row['kind'] == 'government_machinery_repair_received')
        self.assertAlmostEqual(nation.treasury()['total'] - before,
                               sum(row['value_after'] for row in flows))
        self.assertEqual(receipt['inputs']['payer_id'], firm.id)
        self.assertEqual(len(receipt['cause_event_ids']), 1)
        self.assertEqual(receipt['cause_event_ids'][0], next(
            row['event_id'] for row in trace.recent
            if row['kind'] == 'public_account_write'
            and row['inputs'].get('operation_kind') ==
            'labor_resistance:repair_and_replace_machinery'))
        self.assertEqual(evidence[-1]['reason'], 'repaired')

    def test_domestic_bond_coupon_and_maturity_close_bank(self):
        from sovereign_bonds import SovereignBond, SovereignBondMarket
        nation, tile, trace, clock = self.world()
        nation.government.agent.cash = 1000
        market = SovereignBondMarket()
        market.bonds = [SovereignBond('b1', nation.name, 'Domestic Commercial Banks',
                                     100, .01, 2, 0, 2, currency='C')]
        world = {'nations': [nation], 'tiles': [tile]}
        market.step(world, 1)
        trace.bank_book.close([tile], clock, {})
        clock['turn'] = 2
        market.step(world, 2)
        trace.bank_book.close([tile], clock, {})
        capital_closes = [row for row in trace.recent if row['kind'] == 'bank_closing_balance'
                          and row['metric_id'] == 'finance.bank_capital']
        self.assertTrue(all(row['formula_replay']['matches'] for row in capital_closes))
        operations = [row['inputs']['operation_kind'] for row in trace.recent
                      if row['kind'] == 'bank_balance_operation']
        self.assertEqual(['sovereign_bond_coupon', 'sovereign_bond_principal_redemption'], operations)


if __name__ == '__main__':
    unittest.main()
