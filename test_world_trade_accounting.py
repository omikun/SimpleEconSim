"""Journal checks for food purchases made by away traders."""
import unittest
from types import SimpleNamespace

from agent import Agent
from economy.actor_accounts import begin_turn, seal_turn
from forex import ForexDesk, fx_add
from goods import Goods
from world_trade import TRADE_GOODS, settle_trade


class Recorder:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        row['event_id'] = f"test:{clock['next']}"
        clock['next'] += 1
        self.rows.append(row)
        return row['event_id']


class AwayTraderAccountingTests(unittest.TestCase):
    def test_food_purchase_debits_foreign_wallet_and_pays_local_seller(self):
        source = SimpleNamespace(
            name='Upland', home_currency='EUR', agents=[], trader_agents=[],
            forex_desks={}, forex=None, recipes={}, bank=None, province=None,
            tenure=None, cash_obligations=[], economic_events=[], _last_turn=1,
            export_vol={good: [] for good in TRADE_GOODS},
            export_val={good: [] for good in TRADE_GOODS})
        destination = SimpleNamespace(
            name='Lowland', home_currency='USD', agents=[],
            recipes={Goods.food: {'price': 2.0}}, bank=None, province=None,
            tenure=None, cash_obligations=[], economic_events=[], _last_turn=1,
            import_vol={good: [] for good in TRADE_GOODS},
            import_val={good: [] for good in TRADE_GOODS},
            _auction_import_sales={good: (0, 0.0) for good in TRADE_GOODS})
        trader = Agent(0)
        trader.is_trader = True
        trader.home_region = source.name
        trader.home_currency = 'EUR'
        trader.destination_region = destination
        trader.cash = 30.0
        fx_add(trader, 'USD', 20.0)
        seller = Agent(0)
        seller.output = Goods.food
        seller.home_currency = 'USD'
        seller.cash = 5.0
        seller.inv_add(Goods.food, 10)
        source.agents = [trader]
        source.trader_agents = [trader]
        destination.agents = [seller]
        desk = ForexDesk('EUR', 'USD', mid=1.0, spread=0.0,
                         seed_reserves=False)
        source.forex = desk
        source.forex_desks[destination.name] = desk

        recorder = Recorder()
        clock = {'turn': 1, 'phase': 'trade', 'next': 1}
        for region in (source, destination):
            region._collective_trace_clock = clock
            region._run_trace = recorder
            begin_turn(region, 1)

        settle_trade(1, destination, source)

        source_account = next(row for row in seal_turn(source, 1)
                             if row['actor_id'] == trader.id)
        destination_account = next(row for row in seal_turn(destination, 1)
                                   if row['actor_id'] == seller.id)
        wallet_event = next(event for event in source.economic_events
                            if event['kind'] == 'wallet_transfer_out')
        sale_event = next(event for event in destination.economic_events
                          if event['kind'] == 'spot_sale')
        trace = next(row for row in recorder.rows
                     if row['kind'] == 'away_trader_food_purchase')

        self.assertEqual(trader.inv_get(Goods.food), 8)
        self.assertEqual(seller.inv_get(Goods.food), 2)
        self.assertAlmostEqual(trader.cash, 30.0)
        self.assertAlmostEqual(seller.cash, 21.0)
        self.assertAlmostEqual(source_account['wallet_change_by_currency']['USD'], -16.0)
        self.assertAlmostEqual(source_account['wallet_transfer_out_by_currency']['USD'],
                               16.0)
        self.assertAlmostEqual(source_account['posted_cash_change'], 0.0)
        self.assertAlmostEqual(source_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(destination_account['cash_change'], 16.0)
        self.assertAlmostEqual(destination_account['posted_cash_change'], 16.0)
        self.assertEqual(wallet_event['detail']['transfer_id'],
                         sale_event['detail']['transfer_id'])
        self.assertEqual(sale_event['payer_id'], None)
        self.assertEqual(sale_event['recipient_id'], seller.id)
        self.assertEqual(trace['inputs']['wallet_event']['tile'], 'Upland')
        self.assertEqual(trace['inputs']['sale_event']['tile'], 'Lowland')


if __name__ == '__main__':
    unittest.main()
