"""Public stock closure needs ordered writes and stable account membership."""
from pathlib import Path
import random
import tempfile
import unittest

from nation import Nation
from region import Region
from run_trace import RunTrace, verify
from treasury_trace import begin_public_change, finish_public_change


class TreasuryClosingTraceTests(unittest.TestCase):
    def world(self, traced=True):
        nation = Nation('Public', 'C', initial_cash=1000, register=False)
        tile = Region('District', 0, 0)
        nation.add_tile(tile)
        before = {('finance.treasury', nation.name): (None, 'C', nation.treasury()['total'])}
        clock = {'turn': 0, 'phase': 'setup', 'next': 1}
        trace = None
        if traced:
            directory = tempfile.TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            trace = RunTrace(Path(directory.name) / 'public.ctr', 'public', recent_limit=10000)
            for source in (nation, tile):
                source._run_trace, source._collective_trace_clock = trace, clock
            trace.treasury_book.register_nations([nation], clock)
        clock['turn'] = 1
        return nation, tile, trace, clock, before

    def cash(self, source, actor, delta, kind='test_transfer'):
        change = begin_public_change(source, actor)
        actor.cash += delta
        finish_public_change(change, kind)

    def closes(self, trace):
        return [row for row in trace.recent if row['kind'] == 'treasury_account_closure']

    def test_ordered_cash_deposit_and_internal_transfer_closure(self):
        nation, tile, trace, clock, before = self.world()
        self.cash(tile, nation.government.agent, -50, 'grant_debit')
        self.cash(tile, tile.gov.agent, 50, 'grant_receipt')
        tile.bank.Deposit(tile.gov.agent, 100, trace_region=tile)
        tile.bank.Withdraw(tile.gov.agent, 20, trace_region=tile)
        tile.bank.Borrow(1, tile.gov.agent, 10, trace_region=tile)
        trace.treasury_book.close([nation], clock, before)
        closure = self.closes(trace)[-1]
        self.assertEqual('calculation', closure['record_class'])
        self.assertTrue(closure['formula_replay']['matches'])
        self.assertAlmostEqual(before[('finance.treasury', nation.name)][2] + 10,
                               closure['value_after'])
        self.assertTrue(all(row['complete'] for row in closure['inputs']['accounts']))
        for row in trace.recent:
            if row['kind'] == 'public_account_close':
                self.assertTrue(row['formula_replay']['matches'])
        trace.checkpoint(clock)
        self.assertEqual(1, verify(trace.path)['checkpoints'])
        from trace_coverage import coverage
        self.assertEqual({'nation_closes': 1, 'verified': 1, 'gaps': 0, 'membership_changes': 0},
                         coverage(trace.path)['_treasury_account_closure'])

    def test_offsetting_unrecorded_writes_fail_even_with_matching_nation_total(self):
        nation, tile, trace, clock, before = self.world()
        actor = tile.gov.agent
        actor.cash += 5
        tile.bank.Deposit(actor, 20, trace_region=tile)
        actor.cash -= 5
        trace.treasury_book.close([nation], clock, before)
        self.assertEqual(before[('finance.treasury', nation.name)][2], nation.treasury()['total'])
        closure = self.closes(trace)[-1]
        self.assertEqual('audit', closure['record_class'])
        self.assertFalse(closure['formula_replay']['matches'])
        broken = next(row for row in trace.recent if row['kind'] == 'public_account_close'
                      and row['inputs']['account_kind'] == 'cash'
                      and row['inputs']['government_id'] == actor.id)
        self.assertEqual(2, len(broken['inputs']['chain_gaps']))
        self.assertEqual(0, broken['inputs']['unattributed_residual'])

    def test_equal_and_opposite_missing_public_transfers_do_not_disappear(self):
        nation, tile, trace, clock, before = self.world()
        nation.government.agent.cash -= 30
        tile.gov.agent.cash += 30
        trace.treasury_book.close([nation], clock, before)
        closure = self.closes(trace)[-1]
        self.assertEqual(before[('finance.treasury', nation.name)][2], closure['value_after'])
        self.assertEqual('audit', closure['record_class'])
        self.assertEqual(2, sum(not row['complete'] for row in closure['inputs']['accounts']))
        from trace_coverage import coverage
        self.assertEqual(1, coverage(trace.path)['_treasury_account_closure']['gaps'])

    def test_repeated_close_and_next_turn_have_correct_openings(self):
        nation, tile, trace, clock, before = self.world()
        self.cash(tile, tile.gov.agent, 7)
        trace.treasury_book.close([nation], clock, before)
        trace.treasury_book.close([nation], clock, before)
        first, second = self.closes(trace)
        self.assertEqual(
            {key: value for key, value in first['inputs'].items() if key != 'accounts'},
            {key: value for key, value in second['inputs'].items() if key != 'accounts'})
        self.assertEqual(
            [{key: value for key, value in row.items() if key != 'source_event_id'}
             for row in first['inputs']['accounts']],
            [{key: value for key, value in row.items() if key != 'source_event_id'}
             for row in second['inputs']['accounts']])
        self.assertEqual('calculation', second['record_class'])
        previous = {('finance.treasury', nation.name): (None, 'C', nation.treasury()['total'])}
        clock['turn'] = 2
        self.cash(tile, tile.gov.agent, -3)
        trace.treasury_book.close([nation], clock, previous)
        last = self.closes(trace)[-1]
        self.assertEqual(previous[('finance.treasury', nation.name)][2], last['value_before'])
        self.assertEqual('calculation', last['record_class'])

    def test_new_bank_association_and_departed_accounts_are_visible(self):
        from econsim_trade_money import Bank
        nation, tile, trace, clock, before = self.world()
        tile._institutions.bank = Bank(tile.gov)
        tile.gov._bank_ref = None
        tile.gov.agent._bank_ref = None
        trace.treasury_book.close([nation], clock, before)
        closure = self.closes(trace)[-1]
        self.assertEqual('audit', closure['record_class'])
        self.assertTrue(closure['inputs']['entered_accounts'])
        self.assertTrue(closure['inputs']['departed_accounts'])
        self.assertFalse(closure['inputs']['membership_unchanged'])

    def test_territory_change_with_shared_accounts_stays_an_audit(self):
        nation, tile, trace, clock, before = self.world()
        other = Region('Annex', 0, 0, institutions=tile._institutions)
        # Deliberately bypass the instrumented ownership API.
        nation.tiles.append(other)
        other.owner_nation = nation
        trace.treasury_book.close([nation], clock, before)
        closure = self.closes(trace)[-1]
        self.assertEqual('audit', closure['record_class'])
        self.assertFalse(closure['inputs']['territory_unchanged'])
        self.assertFalse(closure['inputs']['entered_accounts'])

    def test_shared_tiles_register_each_physical_account_once(self):
        nation, tile, trace, clock, before = self.world()
        other = Region('Shared', 0, 0, institutions=tile._institutions)
        nation.add_tile(other)
        trace.treasury_book.close([nation], clock, before)
        self.assertEqual(4, len(trace.treasury_book.accounts))
        public_bank_ids = {info['bank_id'] for info in trace.treasury_book.accounts.values()
                           if info['bank_id'] is not None}
        self.assertLessEqual(public_bank_ids, {info['id'] for info in trace.bank_book.banks.values()})
        self.assertEqual('calculation', self.closes(trace)[-1]['record_class'])

    def test_public_deposit_bail_in_has_real_account_chain(self):
        nation, tile, trace, clock, before = self.world()
        tile.bank.Deposit(tile.gov.agent, 150, trace_region=tile)
        tile.bank.apply_bail_in_haircut(trace_region=tile)
        trace.treasury_book.close([nation], clock, before)
        closure = self.closes(trace)[-1]
        self.assertEqual('calculation', closure['record_class'])
        self.assertAlmostEqual(before[('finance.treasury', nation.name)][2] - 25,
                               closure['value_after'])

    def test_frozen_estate_probate_cash_and_deposits_close(self):
        from types import SimpleNamespace
        from agent import Agent
        from demographics_estate import handle_wealth_inheritance
        nation, tile, trace, clock, before = self.world()
        deceased = Agent(0)
        deceased.cash = 20
        deceased.home_currency = 'C'
        tile.bank.Deposit(deceased, 10, trace_region=tile)
        tile.bank.is_frozen = True
        tile.bank.subsistence_withdrawal_cap = 0
        ctx = SimpleNamespace(source_region=tile, bank=tile.bank,
                              default_gov=tile.gov, charity=tile.charity)
        handle_wealth_inheritance(ctx, 1, deceased, [])
        trace.treasury_book.close([nation], clock, before)
        closure = self.closes(trace)[-1]
        self.assertEqual('calculation', closure['record_class'])
        self.assertAlmostEqual(before[('finance.treasury', nation.name)][2] + 6,
                               closure['value_after'])

    def test_tracing_has_no_effect_on_state_or_rng(self):
        states = []
        for traced in (False, True):
            nation, tile, trace, clock, before = self.world(traced)
            rng = random.getstate()
            self.cash(tile, nation.government.agent, -50)
            self.cash(tile, tile.gov.agent, 50)
            tile.bank.Deposit(tile.gov.agent, 70, trace_region=tile)
            tile.bank.Withdraw(tile.gov.agent, 20, trace_region=tile)
            if trace:
                trace.treasury_book.close([nation], clock, before)
            self.assertEqual(rng, random.getstate())
            states.append((nation.treasury()['total'], tile.gov.agent.cash,
                           tile.bank.total_deposits, tile.bank.capital))
        self.assertEqual(*states)


if __name__ == '__main__':
    unittest.main()
