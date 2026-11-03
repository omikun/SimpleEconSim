"""Paid price evidence ages by turns, rather than remaining a permanent anchor."""
import copy
import unittest

from goods import Goods
from region import Region
from region_market import record_paid_price, update_price_ref, trade, food_after_payroll
from price_trace import replay_reference


class DatedMarketPriceTests(unittest.TestCase):
    def fixture(self):
        r = Region('Prices', 0)
        r._price_ref[Goods.food] = 5
        r.recipes[Goods.food]['price'] = 5
        r._last_turn = 1
        return r

    def test_old_price_influence_decays_and_then_expires(self):
        original = self.fixture()
        record_paid_price(original, Goods.food, 1, 10, 10)
        prices = []
        for turn in (1, 4, 13):
            r = copy.deepcopy(original)
            r._last_turn = turn
            update_price_ref(r, Goods.food, 5, local_asks=0, bids=50)
            prices.append(r.recipes[Goods.food]['price'])
        self.assertLess(prices[0], prices[1])
        self.assertLess(prices[1], prices[2])
        self.assertGreater(prices[2], 5)

    def test_idle_quote_cannot_refresh_evidence(self):
        r = self.fixture()
        record_paid_price(r, Goods.food, 1, 10, 10)
        for turn in range(2, 20):
            r._last_turn = turn
            record_paid_price(r, Goods.food, turn, 0, 0)
            update_price_ref(r, Goods.food, 5, local_asks=0, bids=50)
        self.assertEqual(r._paid_price_observations[Goods.food][0]['turn'], 1)
        self.assertGreater(r.recipes[Goods.food]['price'], 5)

    def test_food_sessions_merge_only_paid_units(self):
        r = self.fixture()
        record_paid_price(r, Goods.food, 1, 2, 4)
        record_paid_price(r, Goods.food, 1, 3, 9)
        record_paid_price(r, Goods.food, 1, 0, 0)
        row, = r._paid_price_observations[Goods.food]
        self.assertEqual(row, {'turn': 1, 'quantity': 5, 'paid': 13})

    def test_legacy_undated_history_is_not_relabelled_fresh(self):
        r = self.fixture()
        r._trade_prices[Goods.food] = [1] * 12
        r._last_turn = 100
        update_price_ref(r, Goods.food, 5, local_asks=0, bids=50)
        self.assertGreater(r.recipes[Goods.food]['price'], 5)
        self.assertFalse(getattr(r, '_paid_price_observations', {}))

    def test_no_bids_and_no_offers_do_not_signal_scarcity(self):
        r = self.fixture()
        r.agents = []
        r.trader_agents = []
        r.all_goods_price = 7
        trade(r, 1, defer_food_price=True)
        food_after_payroll(r, 1)
        self.assertEqual(r.demand_ratio_log[Goods.food][-1], 1)
        self.assertLessEqual(r.recipes[Goods.food]['price'], 5)
        self.assertFalse(getattr(r, '_paid_price_observations', {}))

    def test_v1_replay_stays_unchanged_and_v2_uses_dated_evidence(self):
        inputs = {'prior_reference': 5, 'demand_ratio': 5,
                  'average_producer_inventory': 0, 'max_inventory': 10,
                  'recent_market_price_samples': [1], 'input_quantity': 0,
                  'paid_observations': [{'turn': 1, 'quantity': 10, 'paid': 10}],
                  'observation_turn': 13, 'observation_half_life': 3}
        legacy = replay_reference(inputs)['final']
        dated = replay_reference(inputs, dated=True)['final']
        self.assertLess(legacy, dated)
        self.assertAlmostEqual(replay_reference(inputs)['final'], legacy)


if __name__ == '__main__':
    unittest.main()
