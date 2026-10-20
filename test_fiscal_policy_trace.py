"""Fiscal policy evidence preserves financing behavior and explains its gates."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest

from region import Region
from region_finance import collect_tax
from run_trace import RunTrace
from trace_snapshots import sample


def _region(*, cash=0.0, rate=0.25, gaps=()):
    region = Region('District', t=0, number_of_agents=0)
    region.home_currency = 'D'
    region.owner_nation = SimpleNamespace(name='Nation', currency='D')
    region.food_price = 1.0
    region.gov.agent.cash = cash
    region.gov.food_inventory = 0
    region.gov.target_food_reserve = 10
    region.gov.tax_rate = rate
    region.gov.tax_adjust_interval = 2
    region.gov.borrow_log = list(gaps)
    return region


def _state(region):
    return (region.gov.agent.cash, region.gov.tax_rate,
            tuple(region.gov.borrow_log), tuple(region.gov.tax_rate_log),
            tuple(sorted(region.tax_distribution_log[-1].items())),
            region.bank.capital, region.bank.total_deposits,
            region.bank.total_liabilities,
            tuple((loan.principle, loan.principle_paid, loan.interest_paid)
                  for loan in region.gov.agent.loans))


class FiscalPolicyTraceTests(unittest.TestCase):
    def test_rate_reasons_bounds_and_hold_gates_replay(self):
        cases = (
            (0.0, 0.6, [20.0], 2, 0.75, 'persistent_financing_gap'),
            (100.0, 0.25, [0.0], 2, 0.175,
             'zero_gap_and_large_reserve_surplus'),
            (100.0, 0.06, [0.0], 2, 0.05,
             'zero_gap_and_large_reserve_surplus'),
            (20.0, 0.25, [0.0], 2, 0.25, 'within_fiscal_band'),
            (0.0, 0.25, [20.0], 1, 0.25, 'interval_not_due'),
            (20.0, 0.25, [], 2, 0.25, 'insufficient_gap_history'))
        with tempfile.TemporaryDirectory() as tmp:
            for index, (cash, rate, gaps, turn, expected, reason) in enumerate(cases):
                with self.subTest(reason=reason, rate=rate):
                    region = _region(cash=cash, rate=rate, gaps=gaps)
                    trace = RunTrace(Path(tmp) / f'policy-{index}.ctr', f'p-{index}')
                    region._run_trace = trace
                    region._collective_trace_clock = {
                        'turn': turn, 'phase': 'finance', 'next': 1}
                    with redirect_stdout(StringIO()):
                        collect_tax(region, turn)
                    rows = {row['metric_id']: row for row in trace.recent
                            if row.get('metric_id') in (
                                'finance.fiscal_deficit', 'finance.fiscal_gap',
                                'finance.tax_rate')}
                    self.assertEqual(len(rows), 3)
                    self.assertTrue(all(row['formula_replay']['matches']
                                        for row in rows.values()))
                    self.assertAlmostEqual(region.gov.tax_rate, expected)
                    self.assertEqual(rows['finance.tax_rate']['inputs']['reason'], reason)
                    self.assertIn(rows['finance.fiscal_deficit']['event_id'],
                                  rows['finance.fiscal_gap']['cause_event_ids'])
                    self.assertIn(rows['finance.fiscal_gap']['event_id'],
                                  rows['finance.tax_rate']['cause_event_ids'])
                    values = sample([region], [])
                    self.assertEqual(values[('finance.fiscal_gap', region.name)][2],
                                     region.gov.borrow_log[-1])
                    self.assertAlmostEqual(
                        values[('finance.tax_rate', region.name)][2], expected)
                    self.assertEqual(bool(region.gov.tax_rate_log),
                                     reason not in ('interval_not_due',
                                                    'insufficient_gap_history'))

    def test_trace_preserves_borrowing_debt_service_and_random_state(self):
        from random_cache import rand

        traced = _region(gaps=[20.0])
        plain = _region(gaps=[20.0])
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'debt.ctr', 'debt')
            traced._run_trace = trace
            clock = traced._collective_trace_clock = {
                'turn': 2, 'phase': 'finance', 'next': 1}
            for turn in (2, 3):
                clock['turn'] = turn
                random_before = random.getstate()
                cache_index = rand._idx
                with redirect_stdout(StringIO()):
                    collect_tax(traced, turn)
                    collect_tax(plain, turn)
                self.assertEqual(_state(traced), _state(plain))
                self.assertEqual(random.getstate(), random_before)
                self.assertEqual(rand._idx, cache_index)
            rows = list(trace.recent)
            budget = next(row for row in rows
                          if row.get('metric_id') == 'finance.fiscal_deficit'
                          and row['turn'] == 3)
            service = next(row for row in rows
                           if row['kind'] == 'government_loan_service')
            self.assertIn(service['event_id'], budget['cause_event_ids'])
            self.assertTrue(budget['formula_replay']['matches'])
            borrowing = [row for row in rows
                         if row['kind'] == 'government_bank_borrowing']
            self.assertTrue(borrowing)
            by_id = {row['event_id']: row for row in rows}
            for row in borrowing:
                self.assertEqual(by_id[row['cause_event_ids'][0]]['metric_id'],
                                 'finance.fiscal_gap')

    def test_requested_gap_remains_visible_when_bank_rejects_loan(self):
        region = _region(gaps=[20.0])
        region.bank.is_frozen = True
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'frozen.ctr', 'frozen')
            region._run_trace = trace
            region._collective_trace_clock = {
                'turn': 2, 'phase': 'finance', 'next': 1}
            with redirect_stdout(StringIO()):
                collect_tax(region, 2)
            gap = next(row for row in trace.recent
                       if row.get('metric_id') == 'finance.fiscal_gap')
            denied = next(row for row in trace.recent
                          if row['kind'] == 'bank_loan_denied')
            self.assertEqual(gap['value_after'], 20.0)
            self.assertEqual(region.gov.borrow_log[-1], 20.0)
            self.assertEqual(denied['value_after'], 0.0)
            self.assertEqual(region.gov.agent.cash, 0.0)

    def test_shared_government_nonseat_does_not_repeat_policy(self):
        region = _region()
        region.province = SimpleNamespace()
        region._seat_gov_agent = False
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'nonseat.ctr', 'nonseat')
            region._run_trace = trace
            region._collective_trace_clock = {
                'turn': 2, 'phase': 'finance', 'next': 1}
            collect_tax(region, 2)
            self.assertFalse(region.gov.borrow_log)
            self.assertFalse(region.gov.tax_rate_log)
            self.assertFalse(trace.recent)
            self.assertNotIn(('finance.tax_rate', region.name), sample([region], []))


if __name__ == '__main__':
    unittest.main()
