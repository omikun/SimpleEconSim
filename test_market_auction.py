"""Focused behavior checks for the local commodity order book."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from price_trace import replay_event
from region_market import (
    calculate_ask,
    calculate_bid_limit,
    clear_discriminatory,
    food_reserve_units,
)
from run_trace import RunTrace


class MarketAuctionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trace = RunTrace(Path(self.tmp.name) / 'market.ctr', 'market-fixture')
        self.clock = {'next': 1, 'turn': 1, 'phase': 'market_test'}
        self.region = SimpleNamespace(
            name='Delta', home_currency='D',
            _collective_trace_clock=self.clock, _run_trace=self.trace,
            _auction_import_sales={}, _trade_price_event_ids={},
            recipes={Goods.wood: {'price': 5.0, 'maxinv': 10}},
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _wood_seller_and_buyer(self):
        seller = Agent(0)
        initialize_agent(seller, Goods.wood, 0, 0, 5.0)
        seller.inv_set(Goods.wood, 10)
        buyer = Agent(0)
        initialize_agent(buyer, Goods.furniture, 0, 0, 100.0)
        buyer.inv_set(Goods.wood, 0)
        return seller, buyer

    def test_clear_uses_exact_offers_and_settles_midpoint(self):
        seller, buyer = self._wood_seller_and_buyer()
        orders = {
            'sellers': [{'agent': seller, 'quantity': 2, 'limit_price': 4.0}],
            'buyers': [{'agent': buyer, 'quantity': 3, 'limit_price': 6.0}],
        }

        units, paid, vwap = clear_discriminatory(
            self.region, Goods.wood, 5.0, total_asks=2, total_bids=3,
            imp_pool=[], agents=[seller, buyer], t=1, local_orders=orders)

        self.assertEqual(units, 2)
        self.assertEqual(paid, 10.0)
        self.assertEqual(vwap, 5.0)
        self.assertEqual(seller.inv_get(Goods.wood, 0), 8)
        self.assertEqual(buyer.inv_get(Goods.wood, 0), 2)
        self.assertEqual(seller.cash, 15.0)
        self.assertEqual(buyer.cash, 90.0)

    def test_bid_below_ask_does_not_trade(self):
        seller, buyer = self._wood_seller_and_buyer()
        orders = {
            'sellers': [{'agent': seller, 'quantity': 4, 'limit_price': 4.0}],
            'buyers': [{'agent': buyer, 'quantity': 4, 'limit_price': 3.0}],
        }

        units, paid, _ = clear_discriminatory(
            self.region, Goods.wood, 5.0, total_asks=4, total_bids=4,
            imp_pool=[], agents=[seller, buyer], t=1, local_orders=orders)

        self.assertEqual((units, paid), (0, 0.0))
        self.assertEqual(seller.inv_get(Goods.wood, 0), 10)
        self.assertEqual(buyer.inv_get(Goods.wood, 0), 0)
        self.assertEqual(buyer.cash, 100.0)

    def test_food_offer_respects_household_reserve(self):
        farmer = Agent(0)
        initialize_agent(farmer, Goods.food, 0, 0, 20.0)
        farmer.inv_set(Goods.food, 10)
        reserve = food_reserve_units(farmer)
        self.assertEqual(calculate_ask(self.region, farmer, Goods.food, 2.0, False),
                         max(0, 10 - reserve))

    def test_excess_demand_raises_bid_and_trace_replays(self):
        household = SimpleNamespace(
            is_trader=False, is_corporation=False, hungry_steps=0,
            cash=100.0, output=Goods.food, wage=0.0, employees=[],
        )
        self.region.destination_region = None
        self.region.recipes[Goods.food] = {'price': 2.0, 'maxinv': 10}
        balanced = calculate_bid_limit(self.region, household, Goods.wood, 5.0, 1.0, 2)
        scarce = calculate_bid_limit(self.region, household, Goods.wood, 5.0, 2.0, 2)
        self.assertGreater(scarce, balanced)

        seller_a, buyer_a = self._wood_seller_and_buyer()
        _, _, balanced_vwap = clear_discriminatory(
            self.region, Goods.wood, 5.0, total_asks=2, total_bids=2,
            imp_pool=[], agents=[seller_a, buyer_a], t=1,
            local_orders={
                'sellers': [{'agent': seller_a, 'quantity': 2, 'limit_price': 4.0}],
                'buyers': [{'agent': buyer_a, 'quantity': 2, 'limit_price': balanced}],
            })

        seller_b, buyer_b = self._wood_seller_and_buyer()
        buyer_c = Agent(0)
        initialize_agent(buyer_c, Goods.furniture, 0, 0, 100.0)
        scarce_bids = [
            {'agent': buyer_b, 'quantity': 2,
             'limit_price': calculate_bid_limit(self.region, buyer_b, Goods.wood, 5.0, 2.0, 2)},
            {'agent': buyer_c, 'quantity': 2,
             'limit_price': calculate_bid_limit(self.region, buyer_c, Goods.wood, 5.0, 2.0, 2)},
        ]
        _, _, scarce_vwap = clear_discriminatory(
            self.region, Goods.wood, 5.0, total_asks=2, total_bids=4,
            imp_pool=[], agents=[seller_b, buyer_b, buyer_c], t=1,
            local_orders={
                'sellers': [{'agent': seller_b, 'quantity': 2, 'limit_price': 4.0}],
                'buyers': scarce_bids,
            })
        self.assertGreater(scarce_vwap, balanced_vwap)

        row = {
            'formula_id': 'market.local_bid.v1',
            'value_after': scarce,
            'inputs': {
                'reference': 5.0, 'demand_premium': 0.2, 'need_premium': 0.0,
                'quantity': 2, 'cash_limit': 50.0,
                'input_value_ceiling': None, 'trader_net_value': None,
            },
        }
        self.assertTrue(replay_event(row)['matches'])

    def test_corporation_cannot_bypass_auction_for_neighboring_inputs(self):
        from economy.capitalist_planner import EliteCapitalistPlanner

        grower = Agent(0)
        initialize_agent(grower, Goods.wood, 0, 0, 5.0)
        grower.inv_set(Goods.wood, 8)
        neighbor = SimpleNamespace(
            name='Upland', home_currency='D', agents=[grower], goods=[],
            recipes={Goods.wood: {'price': 5.0}},
        )
        firm = Agent(0)
        initialize_agent(firm, Goods.furniture, 2, 0, 100.0)
        firm.is_corporation = True
        firm.inv_set(Goods.wood, 0)
        owner = Agent(0)
        initialize_agent(owner, Goods.food, 0, 0, 100.0)
        owner.company_owned = firm
        region = SimpleNamespace(
            name='Lowland', home_currency='D', neighbors={'Upland': neighbor},
            destination_region=None, goods=[], agents=[owner, firm],
            recipes={Goods.furniture: {'input': Goods.wood, 'numInput': 2}},
        )

        result = EliteCapitalistPlanner().evaluate_spatial_trade(owner, region, t=1)

        self.assertIsNone(result)
        self.assertEqual(grower.inv_get(Goods.wood, 0), 8)
        self.assertEqual(firm.inv_get(Goods.wood, 0), 0)
        self.assertEqual(firm.cash, 100.0)


if __name__ == '__main__':
    unittest.main()
