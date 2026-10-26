"""Unit tests for the Centralized Shared-State Mutation Handler (state_handler.py)."""

import math
import unittest

from agent import Agent, initialize_agent
from goods import Goods
from state_handler import (
    STATE_HANDLER,
    StateInvariantError,
    StateMutationHandler,
    adjust_cash,
    adjust_good,
    recent_mutations,
    strict_mode,
    transfer_cash,
    transfer_deposit,
    transfer_good,
    unwatch_agent,
    unwatch_region,
    watch_agent,
    watch_all,
    watch_region,
)


class DummyBank:
    def __init__(self):
        self.capital = 1000.0
        self.deposits = {}
        self.loans = []
        self._attached_regions = ()

    @property
    def total_deposits(self):
        return sum(self.deposits.values())

    @property
    def total_liabilities(self):
        return sum(getattr(l, 'principle', 0.0) for l in self.loans)


class DummyRegion:
    def __init__(self, name='test-tile'):
        self.name = name
        self.agents = []
        self.home_currency = 'GBP'


class TestStateMutationHandler(unittest.TestCase):
    def setUp(self):
        STATE_HANDLER.reset()
        self.payer = Agent(101)
        initialize_agent(self.payer, Goods.food, 0, 0, 100.0)
        self.payer.inv_set(Goods.food, 25)

        self.payee = Agent(102)
        initialize_agent(self.payee, Goods.cloth, 0, 0, 40.0)
        self.payee.inv_set(Goods.food, 5)

        self.region = DummyRegion('lancashire')

    def tearDown(self):
        STATE_HANDLER.reset()

    def test_transfer_cash_conserves_money_and_notifies_watchpoints(self):
        events = []
        watch_agent(self.payer, events.append)
        STATE_HANDLER.history_enabled = True

        moved = transfer_cash(
            self.payer,
            self.payee,
            35.5,
            region=self.region,
            kind='test:wage_payment',
        )
        self.assertAlmostEqual(moved, 35.5)
        self.assertAlmostEqual(self.payer.cash, 64.5)
        self.assertAlmostEqual(self.payee.cash, 75.5)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['op'], 'transfer_cash')
        self.assertEqual(events[0]['payer_id'], self.payer.id)
        self.assertEqual(events[0]['payee_id'], self.payee.id)
        self.assertAlmostEqual(events[0]['amount'], 35.5)

        history = recent_mutations(agent_id=self.payee.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['kind'], 'test:wage_payment')
        unwatch_agent(self.payer)

    def test_transfer_cash_cap_at_payer_cash(self):
        moved = transfer_cash(
            self.payer,
            self.payee,
            250.0,
            region=self.region,
            kind='test:capped_transfer',
            cap_at_payer_cash=True,
        )
        self.assertAlmostEqual(moved, 100.0)
        self.assertAlmostEqual(self.payer.cash, 0.0)
        self.assertAlmostEqual(self.payee.cash, 140.0)

    def test_strict_mode_rejects_overdraft_nan_and_dead_agent_mutation(self):
        with strict_mode(allow_dead=False):
            with self.assertRaises(StateInvariantError):
                transfer_cash(self.payer, self.payee, 150.0, kind='test:overdraft')

            with self.assertRaises(StateInvariantError):
                adjust_cash(self.payer, float('nan'), kind='test:nan')

            with self.assertRaises(StateInvariantError):
                adjust_good(self.payer, Goods.food, -30, kind='test:negative_inventory')

            self.payee.alive = False
            with self.assertRaises(StateInvariantError):
                transfer_cash(self.payer, self.payee, 10.0, kind='test:dead_payee')

    def test_transfer_good_and_region_watchpoint(self):
        region_events = []
        watch_region(self.region, region_events.append)

        qty = transfer_good(
            self.payer,
            self.payee,
            Goods.food,
            12,
            region=self.region,
            kind='test:grain_relief',
        )
        self.assertEqual(qty, 12)
        self.assertEqual(self.payer.inv_get(Goods.food), 13)
        self.assertEqual(self.payee.inv_get(Goods.food), 17)
        self.assertEqual(len(region_events), 1)
        self.assertEqual(region_events[0]['good'], 'food')
        self.assertEqual(region_events[0]['qty'], 12)
        unwatch_region(self.region)

    def test_transfer_deposit_conserves_bank_deposits(self):
        bank = DummyBank()
        bank.deposits[self.payer] = 80.0
        bank.deposits[self.payee] = 20.0

        with strict_mode():
            moved = transfer_deposit(
                bank,
                self.payer,
                self.payee,
                50.0,
                region=self.region,
                kind='test:wire_transfer',
            )
            self.assertAlmostEqual(moved, 50.0)
            self.assertAlmostEqual(bank.deposits[self.payer], 30.0)
            self.assertAlmostEqual(bank.deposits[self.payee], 70.0)
            self.assertAlmostEqual(bank.total_deposits, 100.0)

            with self.assertRaises(StateInvariantError):
                transfer_deposit(bank, self.payer, self.payee, 50.0, kind='test:deposit_overdraft')


if __name__ == '__main__':
    unittest.main()
