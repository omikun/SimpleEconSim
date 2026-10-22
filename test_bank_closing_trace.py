"""Bank closures must account for actual transitions, including shared banks."""
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest

from agent import Agent
from bank_trace import balances
from econsim_trade_money import Bank
from price_trace import replay_event
from run_trace import RunTrace


class BankClosingTraceTests(unittest.TestCase):
    def make_world(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        trace = RunTrace(Path(directory.name) / 'bank.ctr', 'bank', recent_limit=10000)
        clock = {'turn': 0, 'phase': 'setup', 'next': 1}
        bank = Bank()
        tiles = [SimpleNamespace(name=name, home_currency='C', bank=bank,
                                 _run_trace=trace, _collective_trace_clock=clock)
                 for name in ('A', 'B')]
        bank._attached_regions = tiles
        trace.bank_book.register_tiles(tiles, clock)
        clock['turn'] = 1
        person = Agent(0)
        person.cash = 1000
        person.loans = []
        for tile in tiles:
            tile.agents = [person]
        return trace, clock, bank, tiles, person

    def test_shared_bank_transactions_and_repeat_close(self):
        trace, clock, bank, tiles, person = self.make_world()
        bank.Deposit(person, 200, trace_region=tiles[0])
        bank.Withdraw(person, 50, trace_region=tiles[1])
        bank.Borrow(1, person, 100, trace_region=tiles[0])
        person.loans[-1].pay(10)
        bank.PayDepositInterest([person], trace_region=tiles[1])
        bank.write_down_bonds(2, trace_region=tiles[0])
        bank.recapitalize(3, trace_region=tiles[0])
        bank.apply_bail_in_haircut(trace_region=tiles[1])
        state = balances(bank)
        trace.bank_book.close(tiles, clock, {})
        trace.bank_book.close(tiles, clock, {})
        rows = list(trace.recent)
        self.assertEqual(1, sum(row['kind'] == 'bank_registered' for row in rows))
        self.assertEqual(8, sum(row['kind'] == 'bank_balance_operation' for row in rows))
        closings = [row for row in rows if row['kind'] == 'bank_closing_balance']
        self.assertEqual(6, len(closings))
        self.assertTrue(all(row['formula_replay']['matches'] for row in closings))
        aliases = [row for row in rows if row['kind'] == 'bank_tile_closing_alias']
        self.assertEqual(16, len(aliases))
        self.assertEqual(state, balances(bank))
        # Repeated close keeps the original opening provenance for this turn.
        self.assertEqual([r['inputs']['opening_source_event_id'] for r in closings[:3]],
                         [r['inputs']['opening_source_event_id'] for r in closings[3:]])

    def test_missing_write_is_not_explained(self):
        trace, clock, bank, tiles, _ = self.make_world()
        bank.capital += 5
        trace.bank_book.close(tiles, clock, {})
        rows = list(trace.recent)
        capital = next(row for row in rows if row['kind'] == 'bank_closing_balance'
                       and row['metric_id'] == 'finance.bank_capital')
        self.assertEqual('audit', capital['record_class'])
        self.assertFalse(capital['formula_replay']['matches'])
        self.assertEqual(5, capital['inputs']['unattributed_residual'])
        self.assertFalse(any(row['kind'] == 'bank_tile_closing_alias' and
                             row['metric_id'] in ('finance.bank_capital', 'finance.bank_equity')
                             for row in rows))

    def test_offsetting_missing_writes_fail_continuity(self):
        trace, clock, bank, tiles, person = self.make_world()
        bank.capital += 5
        bank.Deposit(person, 20, trace_region=tiles[0])
        bank.capital -= 5
        trace.bank_book.close(tiles, clock, {})
        capital = next(row for row in trace.recent if row['kind'] == 'bank_closing_balance'
                       and row['metric_id'] == 'finance.bank_capital')
        self.assertEqual(0, capital['inputs']['unattributed_residual'])
        self.assertEqual(2, len(capital['inputs']['chain_gaps']))
        self.assertFalse(replay_event(capital)['matches'])

    def test_next_turn_opens_at_previous_close(self):
        trace, clock, bank, tiles, person = self.make_world()
        bank.Deposit(person, 20, trace_region=tiles[0])
        trace.bank_book.close(tiles, clock, {})
        clock['turn'] = 2
        bank.Withdraw(person, 10, trace_region=tiles[0])
        trace.bank_book.close(tiles, clock, {})
        deposits = [row for row in trace.recent if row['kind'] == 'bank_closing_balance'
                    and row['metric_id'] == 'finance.bank_deposits']
        self.assertEqual((20, 10), (deposits[-1]['value_before'], deposits[-1]['value_after']))
        self.assertTrue(deposits[-1]['formula_replay']['matches'])

    def test_earlier_outcome_cannot_hide_missing_closing_write(self):
        trace, clock, bank, tiles, _ = self.make_world()
        bank.capital += 5
        trace.emit(clock, kind='earlier_capital_outcome', record_class='outcome',
                   subject={'type': 'tile', 'id': 'A'}, metric_id='finance.bank_capital',
                   after=bank.capital)
        trace.bank_book.close(tiles, clock, {})
        trace.snapshot(clock, subject={'type': 'tile', 'id': 'A'},
                       metric_id='finance.bank_capital', unit='C', before=2000,
                       after=bank.capital)
        snapshot = next(row for row in trace.recent if row['kind'] == 'metric_snapshot')
        self.assertEqual('source_missing', snapshot['explanation_status'])

    def test_distinct_banks_have_distinct_institution_ids(self):
        trace, clock, bank, tiles, _ = self.make_world()
        tiles[1].bank = Bank()
        trace.bank_book.register_tiles(tiles, clock)
        self.assertEqual(2, len(trace.bank_book.banks))
        self.assertEqual(2, len({info['id'] for info in trace.bank_book.banks.values()}))

    def test_estate_losses_and_treasury_recapitalization_close(self):
        from demographics_estate import forgive_bad_debt
        trace, clock, bank, tiles, person = self.make_world()
        # A loss larger than capital exercises deposits and treasury support.
        person.cash = 1000
        bank.Deposit(person, 100, trace_region=tiles[0])
        government = Agent(0)
        government.cash = 1000
        bank.gov = SimpleNamespace(agent=government)
        forgive_bad_debt(bank, 2200, 1, region=tiles[0], debtor=person)
        trace.bank_book.close(tiles, clock, {})
        closings = [row for row in trace.recent if row['kind'] == 'bank_closing_balance']
        self.assertTrue(all(row['formula_replay']['matches'] for row in closings))
        kinds = {row['inputs']['operation_kind'] for row in trace.recent
                 if row['kind'] == 'bank_balance_operation'}
        self.assertTrue({'estate_shareholder_loss', 'estate_depositor_loss',
                         'estate_treasury_recapitalization'} <= kinds)

    def test_trace_does_not_change_rules_or_rng(self):
        trace, clock, bank, tiles, person = self.make_world()
        other, agent = Bank(), Agent(0)
        agent.cash, agent.loans = 1000, []
        rng_before = random.getstate()
        for institution, actor, region in ((bank, person, tiles[0]), (other, agent, None)):
            institution.Deposit(actor, 200, trace_region=region)
            institution.Borrow(1, actor, 100, trace_region=region)
            actor.loans[-1].pay(10)
            institution.PayDepositInterest([actor], trace_region=region)
            institution.Withdraw(actor, 50, trace_region=region)
        self.assertEqual(balances(bank), balances(other))
        self.assertEqual(person.cash, agent.cash)
        self.assertEqual(rng_before, random.getstate())


if __name__ == '__main__':
    unittest.main()
