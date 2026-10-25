"""Fiscal policy evidence preserves financing behavior and explains its gates."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest

from agent import Agent, initialize_agent
from goods import Goods
from government import Government
from nation import Nation
from region import Region
from region_finance import collect_tax
from run_trace import RunTrace
from trace_snapshots import sample


def _region(*, cash=0.0, rate=0.25, gaps=()):
    region = Region('District', t=0, number_of_agents=0)
    region.home_currency = 'D'
    nation = Nation('Nation', 'D', initial_cash=0, register=False)
    nation.add_tile(region)
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


def _income_region(tiers=3, *, limited_cash=False, deduction=0.0,
                   incomes=(100.0, 100.0), carry=0.0):
    region = _region()
    region.gov.tax_adjust_interval = 100
    region.agents = []
    for index in range(20):
        person = Agent(0)
        person.id = index + 1
        cash = ((1.0, 0.5) if limited_cash else (30.0, 20.0))
        initialize_agent(person, Goods.food, 0, 0,
                         cash[index] if index < 2 else 0.0)
        person._delta_cash = incomes[index] if index < 2 else 0.0
        person._delta_deposits = 0.0
        person.tax_loss_carryforward = carry if index == 0 else 0.0
        person._bank_ref = region.bank
        region.agents.append(person)
    if limited_cash:
        region.bank.deposits[region.agents[0]] = 1.0
        region.bank.total_deposits = 1.0
    if tiers >= 2:
        region.owner_nation.government = Government('National', 0, initial_cash=0)
    else:
        region.owner_nation.government = None
    if tiers == 3:
        region.province = SimpleNamespace(
            gov=Government('Provincial', 0, initial_cash=0))
        region._seat_gov_agent = True
    deduction_calls = []

    def child_deduction(person):
        deduction_calls.append(person.id)
        return deduction

    region.gov.compute_child_tax_deduction = child_deduction
    return region, deduction_calls


class FiscalPolicyTraceTests(unittest.TestCase):
    def test_government_taxpayer_debit_offsets_the_recorded_tax_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            region, _calls = _income_region(tiers=1)
            taxpayer = region.gov.agent
            taxpayer.cash = 10.0
            taxpayer._delta_cash = 1000.0
            taxpayer._delta_deposits = 0.0
            taxpayer.tax_loss_carryforward = 0.0
            taxpayer.id = 9999
            for agent in region.agents:
                agent.cash = 0.5
            region.agents.append(taxpayer)

            trace = RunTrace(Path(tmp) / 'government-taxpayer.ctr',
                             'government-taxpayer')
            region._run_trace = trace
            region._collective_trace_clock = {
                'turn': 1, 'phase': 'finance', 'next': 1}
            trace.treasury_book.register_nations(
                [region.owner_nation], region._collective_trace_clock)
            before = region.owner_nation.treasury()['total']

            collect_tax(region, 1)

            flows = [row for row in trace.recent
                     if row.get('metric_id') == 'finance.treasury_flow']
            assessment = next(row for row in trace.recent
                              if row.get('kind') ==
                              'income_tax_assessment_calculation')
            bill = next(row for row in assessment['inputs']['bills']
                        if row['agent_id'] == taxpayer.id)
            self.assertGreater(bill['amount_paid'], 0.0)
            taxpayer_flow = next(row for row in flows
                                 if row.get('kind') ==
                                 'government_income_tax_payment')
            self.assertAlmostEqual(taxpayer_flow['value_after'],
                                   -bill['amount_paid'])
            self.assertTrue(taxpayer_flow['cause_event_ids'])
            self.assertAlmostEqual(
                region.owner_nation.treasury()['total'] - before,
                sum(row['value_after'] for row in flows), places=7)

    def test_assessment_and_all_treasury_splits_match_untraced_outcomes(self):
        expected_splits = {
            1: {'total': 20.0, 'national': 0.0, 'provincial': 0.0, 'municipal': 20.0},
            2: {'total': 20.0, 'national': 10.0, 'provincial': 0.0, 'municipal': 10.0},
            3: {'total': 20.0, 'national': 10.0, 'provincial': 6.0, 'municipal': 4.0}}
        with tempfile.TemporaryDirectory() as tmp:
            for tiers in (1, 2, 3):
                traced, calls = _income_region(tiers)
                plain, plain_calls = _income_region(tiers)
                trace = RunTrace(Path(tmp) / f'split-{tiers}.ctr', f'split-{tiers}')
                traced._run_trace = trace
                traced._collective_trace_clock = {
                    'turn': 1, 'phase': 'finance', 'next': 1}
                trace.treasury_book.register_nations([traced.owner_nation],
                                                     traced._collective_trace_clock)
                collect_tax(traced, 1)
                collect_tax(plain, 1)
                self.assertEqual(_state(traced), _state(plain))
                self.assertEqual([(a.cash, a.tax_loss_carryforward)
                                  for a in traced.agents],
                                 [(a.cash, a.tax_loss_carryforward)
                                  for a in plain.agents])
                self.assertEqual(calls, plain_calls)
                self.assertEqual(calls, [1, 2])
                self.assertEqual(traced.tax_distribution_log[-1], expected_splits[tiers])
                assessment = next(row for row in trace.recent
                                  if row.get('metric_id') == 'finance.tax_assessment')
                self.assertTrue(assessment['formula_replay']['matches'])
                self.assertEqual(assessment['inputs']['effective_rate'], 0.1)
                self.assertEqual([bill['agent_id'] for bill in
                                  assessment['inputs']['bills']], [1, 2])
                self.assertEqual([row['agent_id'] for row in
                                  assessment['inputs']['wealth_ranking'][:2]], [1, 2])
                distributions = [row for row in trace.recent
                                 if row.get('metric_id') == 'finance.tax_distribution']
                self.assertEqual(len(distributions), 4)
                receipt_write_ids = {
                    event_id for receipt in distributions[0]['inputs']['receipts']
                    for event_id in receipt['public_write_event_ids']}
                expected_write_count = {1: 2, 2: 4, 3: 6}[tiers]
                self.assertEqual(len(receipt_write_ids), expected_write_count)
                rows_by_id = {row['event_id']: row for row in trace.recent}
                for event_id in receipt_write_ids:
                    self.assertEqual(rows_by_id[event_id]['kind'], 'public_account_write')
                for row in distributions:
                    tier = row['subject']['tax_tier']
                    self.assertEqual(row['value_after'], expected_splits[tiers][tier])
                    self.assertTrue(row['formula_replay']['matches'])
                    self.assertIn(assessment['event_id'], row['cause_event_ids'])
                    self.assertTrue(receipt_write_ids.issubset(set(row['cause_event_ids'])))
                snapshots = sample([traced], [])
                for tier, expected in expected_splits[tiers].items():
                    self.assertEqual(snapshots[(
                        'finance.tax_distribution', traced.name, tier)][2], expected)

    def test_tax_bases_capture_deductions_losses_and_liquidity_limits(self):
        cases = (
            ({'limited_cash': True}, 2.5, 'income_tax_assessed'),
            ({'deduction': 10.0, 'incomes': (50.0, -10.0), 'carry': -20.0},
             5.0, 'income_tax_assessed'),
            ({'incomes': (0.0, 0.0)}, 0.0, 'no_positive_tax_base'))
        with tempfile.TemporaryDirectory() as tmp:
            for index, (options, expected, reason) in enumerate(cases):
                region, calls = _income_region(1, **options)
                trace = RunTrace(Path(tmp) / f'bases-{index}.ctr', f'bases-{index}')
                region._run_trace = trace
                region._collective_trace_clock = {
                    'turn': 1, 'phase': 'finance', 'next': 1}
                collect_tax(region, 1)
                assessment = next(row for row in trace.recent
                                  if row.get('metric_id') == 'finance.tax_assessment')
                self.assertEqual(assessment['value_after'], expected)
                self.assertTrue(assessment['formula_replay']['matches'])
                self.assertEqual(assessment['inputs']['reason'], reason)
                self.assertEqual(calls, [1, 2])
                if options.get('limited_cash'):
                    first = assessment['inputs']['bills'][0]
                    self.assertEqual(first['payment_status'],
                                     'limited_by_cash_and_deposits')
                    self.assertEqual(first['deposit_before_payment'], 1.0)
                    self.assertEqual(first['deposit_after_debit'], 0.0)

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
            by_id = {row['event_id']: row for row in rows}
            self.assertTrue(service['cause_event_ids'])
            self.assertTrue(all(by_id[event_id]['kind'] == 'public_account_write'
                                for event_id in service['cause_event_ids']))
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
