"""Public savings, freezes, loss resolution and loan service share one chain."""
from pathlib import Path
import tempfile
import unittest

from agent import Agent
from banking_policy import recapitalize_domestic_banks
from econsim_trade_money import PayLoans
from nation import Nation
from region import Region
from run_trace import RunTrace
from trace_audit import audit


class PublicBankLifecycleTraceTests(unittest.TestCase):
    def test_public_depositor_freeze_haircut_recapitalization_and_service_close(self):
        with tempfile.TemporaryDirectory() as directory:
            nation = Nation('Resolution', 'C', initial_cash=1000, register=False)
            tile = Region('Bank district', 0, number_of_agents=0)
            nation.add_tile(tile)
            government = tile.gov.agent
            government.cash = 1000
            person = Agent(0)
            person.cash = 100
            tile.agents = [government, person]
            bank = tile.bank
            trace = RunTrace(Path(directory)/'resolution.ctr', 'resolution')
            clock = {'turn': 0, 'phase': 'setup', 'next': 1}
            for source in (nation, tile):
                source._run_trace = trace
                source._collective_trace_clock = clock
            trace.bank_book.register_tiles([tile], clock)
            trace.treasury_book.register_nations([nation], clock)
            previous = {('finance.treasury', nation.name):
                        (None, 'C', nation.treasury()['total'])}
            clock['turn'] = 1
            bank.Borrow(1, government, 100, trace_region=tile)
            bank.Deposit(government, 200, trace_region=tile)
            bank.Deposit(person, 50, trace_region=tile)
            bank.is_frozen = True
            self.assertEqual(5, bank.Withdraw(government, 50, trace_region=tile, t=1))
            self.assertEqual(0, bank.Borrow(1, government, 100, trace_region=tile))
            bank.apply_bail_in_haircut(.25, 50, trace_region=tile)
            self.assertEqual(50, bank.deposits[person])
            self.assertEqual(158.75, bank.deposits[government])
            bank.write_down_bonds(bank.capital+5, trace_region=tile)
            self.assertTrue(bank.is_frozen)
            ok, _ = recapitalize_domestic_banks(nation, target_capital=500)
            self.assertTrue(ok)
            self.assertEqual(500, bank.capital)
            self.assertFalse(bank.is_frozen)
            self.assertGreater(bank.PayDepositInterest(tile.agents, trace_region=tile), 0)
            PayLoans(government, bank=bank, trace_region=tile, t=1)
            trace.bank_book.close([tile], clock, {})
            trace.treasury_book.close([nation], clock, previous)
            self.assertTrue(all(row['formula_replay']['matches'] for row in
                                trace.query(kind='bank_closing_balance')['events']))
            public = trace.query(kind='treasury_account_closure')['events']
            self.assertEqual(1, len(public))
            self.assertTrue(public[0]['formula_replay']['matches'])
            result = audit(trace.path)
            self.assertTrue(result['structural_and_supported_formula_checks_pass'], result['issues'])


if __name__ == '__main__':
    unittest.main()
