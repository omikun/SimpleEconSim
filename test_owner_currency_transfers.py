"""Owner financing and payout journal tests across cash and FX wallets."""

import unittest

from agent import Agent
from economy.actor_accounts import begin_turn, seal_turn
from region_finance import bailout_owner, pay_base_salary, repay_owner_loan


class Recorder:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        self.rows.append({'turn': clock['turn'], **row})


class Region:
    def __init__(self):
        self.name = 'Factory District'
        self.home_currency = 'USD'
        self.bank = None
        self.food_price = 2.0
        self.agents = []
        self.recipes = {}
        self.cash_obligations = []
        self.tenure = None
        self.economic_events = []
        self._collective_trace_clock = {'turn': 1, 'next': 1, 'phase': 'finance'}
        self._run_trace = Recorder()


class OwnerCurrencyTransferTests(unittest.TestCase):
    def setUp(self):
        self.region = Region()
        self.owner = Agent(0)
        self.owner.cash = 0.0
        self.owner.home_currency = 'GBP'
        self.owner.wallets = {'USD': 100.0}
        self.owner._bank_ref = object()
        self.firm = Agent(0)
        self.firm.is_corporation = True
        self.firm.cash = 0.0
        self.firm.wage = 5.0
        self.firm.owner = self.owner
        self.firm.owner_loan = 0.0
        self.firm.retained_earnings = 0.0
        self.firm.employees = []
        self.region.agents = [self.owner, self.firm]

    def test_wallet_bailout_salary_and_loan_repayment_post_the_right_legs(self):
        begin_turn(self.region, 1)
        bailout_owner(self.region, self.firm, self.owner, payroll=10.0, t=1)
        accounts = {row['actor_id']: row for row in seal_turn(self.region, 1)}

        self.assertEqual(self.owner.wallets['USD'], 90.0)
        self.assertEqual(self.firm.cash, 10.0)
        self.assertEqual(self.firm.owner_loan, 10.0)
        self.assertEqual(accounts[self.owner.id]['cash_change'], 0.0)
        self.assertEqual(accounts[self.owner.id]['posted_cash_change'], 0.0)
        self.assertEqual(accounts[self.owner.id]['unposted_cash_change'], 0.0)
        self.assertEqual(
            accounts[self.owner.id]['wallet_transfer_out_by_currency'],
            {'USD': 10.0})
        self.assertEqual(accounts[self.firm.id]['posted_cash_change'], 10.0)
        self.assertEqual(accounts[self.firm.id]['owner_financing_received'], 10.0)
        self.assertEqual(accounts[self.firm.id]['opening_owner_loan'], 0.0)
        self.assertEqual(accounts[self.firm.id]['closing_owner_loan'], 10.0)

        self.firm.cash = 100.0
        self.region._collective_trace_clock = {'turn': 2, 'next': 1, 'phase': 'finance'}
        begin_turn(self.region, 2)
        pay_base_salary(self.region, self.firm, self.owner, payroll=5.0, t=2)
        salary_accounts = {row['actor_id']: row
                           for row in seal_turn(self.region, 2)}

        self.assertEqual(self.firm.cash, 95.0)
        self.assertEqual(self.owner.wallets['USD'], 95.0)
        self.assertEqual(salary_accounts[self.firm.id]['posted_cash_change'], -5.0)
        self.assertEqual(salary_accounts[self.owner.id]['posted_cash_change'], 0.0)
        self.assertEqual(
            salary_accounts[self.owner.id]['wallet_transfer_in_by_currency'],
            {'USD': 5.0})
        self.assertEqual(salary_accounts[self.owner.id]['unposted_cash_change'], 0.0)

        self.firm.cash = 100.0
        self.firm.owner_loan = 10.0
        self.region._collective_trace_clock = {'turn': 3, 'next': 1, 'phase': 'finance'}
        begin_turn(self.region, 3)
        repay_owner_loan(self.region, self.firm, self.owner, payroll=5.0, t=3)
        repayment_accounts = {row['actor_id']: row
                              for row in seal_turn(self.region, 3)}

        self.assertEqual(self.firm.cash, 90.0)
        self.assertEqual(self.owner.wallets['USD'], 105.0)
        self.assertEqual(repayment_accounts[self.firm.id]['posted_cash_change'], -10.0)
        self.assertEqual(repayment_accounts[self.firm.id]['owner_loan_repaid'], 10.0)
        self.assertEqual(repayment_accounts[self.firm.id]['closing_owner_loan'], 0.0)
        self.assertEqual(
            repayment_accounts[self.owner.id]['wallet_transfer_in_by_currency'],
            {'USD': 10.0})
        self.assertEqual(
            repayment_accounts[self.owner.id]['owner_loan_repayment_received'],
            10.0)
        self.assertEqual(repayment_accounts[self.owner.id]['unposted_cash_change'], 0.0)

        self.assertEqual(len(self.region._run_trace.rows), 3)
        self.assertTrue(all(row['metric_id'] == 'finance.owner_transfer'
                            for row in self.region._run_trace.rows))


if __name__ == '__main__':
    unittest.main()
