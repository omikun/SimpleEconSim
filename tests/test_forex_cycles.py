"""Settlement contracts for legacy and multi-neighbor FX entry points."""
import unittest
from types import SimpleNamespace

from agent import Agent
from econsim_trade_money import Bank
from forex import ForexDesk, cycle_all_markets, cycle_market, fx_add, fx_balance


def market_fixture(home_region):
    trader = Agent(0)
    trader.is_trader = True
    trader.home_region = home_region
    trader.home_currency = 'A'
    trader.cash = 0.0
    trader._trader_revenue = 0.0
    fx_add(trader, 'B', 5.0)
    bank = Bank()
    bank.fx_pool = 20.0
    desk = ForexDesk('A', 'B', bank=bank, mid=1.0, spread=0.0,
                     seed_reserves=False)
    partner = SimpleNamespace(name='Away', home_currency='B', forex=None)
    region = SimpleNamespace(
        name='Home', home_currency='A', agents=[trader], trader_agents=[trader],
        bank=bank, forex=desk, forex_desks={'Away': desk},
        neighbors={'Away': partner}, destination_region=partner, _last_turn=1)
    return region, partner, trader


class ForexCycleTests(unittest.TestCase):
    def check_result(self, region, trader, repatriated):
        self.assertEqual(trader.cash, 5.0 if repatriated else 0.0)
        self.assertEqual(trader._trader_revenue, trader.cash)
        # Both currencies are conserved across cash, wallets and bank reserves.
        self.assertEqual(trader.cash + region.bank.fx_pool, 20.0)
        self.assertEqual(fx_balance(trader, 'B')
                         + region.bank.foreign_reserves.get('B', 0.0), 5.0)
        self.assertEqual(fx_balance(trader, 'B'), 0.0 if repatriated else 5.0)

    def test_legacy_cycle_repatriates_local_and_visiting_traders(self):
        for home in ('Home', 'Elsewhere'):
            with self.subTest(home=home):
                region, partner, trader = market_fixture(home)
                self.assertEqual(cycle_market(region, partner, 1), {'Home': 0.0})
                self.check_result(region, trader, True)

    def test_neighbor_cycle_leaves_visiting_trader_wallet_untouched(self):
        for home in ('Home', 'Elsewhere'):
            with self.subTest(home=home):
                region, partner, trader = market_fixture(home)
                self.assertEqual(cycle_all_markets([region, partner], 1),
                                 {'Home->Away': 0.0})
                self.check_result(region, trader, home == 'Home')
