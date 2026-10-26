"""Causal accounting for trader-to-homesteader frontier settlements."""
import unittest
from types import SimpleNamespace

from agent import Agent
from economy.actor_accounts import begin_turn, seal_turn
from goods import Goods
from trade_settle import settle_wilderness


class Recorder:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        row['event_id'] = f"test:{clock['next']}"
        clock['next'] += 1
        self.rows.append(row)
        return row['event_id']


class WildernessTradeAccountingTests(unittest.TestCase):
    def test_wallet_payments_and_goods_flows_reconcile_both_actor_accounts(self):
        source = SimpleNamespace(
            name='Home', home_currency='USD', agents=[], bank=None,
            province=None, tenure=None, cash_obligations=[], recipes={},
            economic_events=[], _last_turn=1)
        wilderness = SimpleNamespace(
            name='Frontier', home_currency=None, wilderness=True,
            is_ocean=False, elevation=0.0, agents=[], bank=None,
            province=None, tenure=None, cash_obligations=[],
            recipes={Goods.food: {'price': 2.0},
                     Goods.wood: {'price': 4.0},
                     Goods.transport: {'price': 1.0, 'capacity': 10}},
            economic_events=[], settlement_log=[], _last_turn=1)
        trader = Agent(0)
        trader.is_trader = True
        trader.home_currency = 'USD'
        trader.cash = 100.0
        trader.inv_add(Goods.food, 4)
        homesteader = Agent(0)
        homesteader.is_homesteader = True
        homesteader.home_currency = 'USD'
        homesteader.inv_add(Goods.wood, 10)
        source.agents = [trader]
        wilderness.agents = [homesteader]

        recorder = Recorder()
        clock = {'turn': 1, 'phase': 'trade', 'next': 1}
        for region in (source, wilderness):
            region._collective_trace_clock = clock
            region._run_trace = recorder
            begin_turn(region, 1)

        result = settle_wilderness(trader, wilderness, 1, source_region=source)

        source_accounts = {row['actor_id']: row for row in seal_turn(source, 1)}
        frontier_accounts = {row['actor_id']: row for row in seal_turn(wilderness, 1)}
        trader_account = source_accounts[trader.id]
        homesteader_account = frontier_accounts[homesteader.id]
        payment_events = [event for event in source.economic_events
                          if event['kind'] == 'wilderness_trade_payment']
        wallet_events = [event for event in wilderness.economic_events
                         if event['kind'] == 'wallet_transfer_in']
        goods_events = [event for event in wilderness.economic_events
                        if event['kind'] in {'wilderness_goods_advance',
                                             'wilderness_goods_collection'}]

        self.assertAlmostEqual(result['sold_value'], 10.08)
        self.assertAlmostEqual(result['collected_value'], 44.0)
        self.assertAlmostEqual(result['paid'], 16.96)
        self.assertAlmostEqual(trader.cash, 72.96)
        self.assertAlmostEqual(homesteader.wallets['USD'], 27.04)
        self.assertAlmostEqual(sum(event['amount'] for event in payment_events), 27.04)
        self.assertAlmostEqual(sum(event['amount'] for event in wallet_events), 27.04)
        self.assertEqual({event['asset_id'] for event in payment_events},
                         {event['asset_id'] for event in wallet_events})
        self.assertEqual(sorted((event['kind'], event['good'], event['quantity'])
                                for event in goods_events),
                         [('wilderness_goods_advance', 'food', 4.0),
                          ('wilderness_goods_collection', 'food', 2.0),
                          ('wilderness_goods_collection', 'wood', 10.0)])
        self.assertAlmostEqual(trader_account['posted_cash_change'], -27.04)
        self.assertAlmostEqual(trader_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(homesteader_account['wallet_change_by_currency']['USD'],
                               27.04)
        self.assertAlmostEqual(
            homesteader_account['wallet_transfer_in_by_currency']['USD'], 27.04)
        self.assertEqual({row['metric_id'] for row in recorder.rows},
                         {'trade.wilderness_settlement', 'trade.wilderness_goods'})
        for payment in payment_events:
            trace = next(row for row in recorder.rows
                         if row.get('kind') == 'wilderness_wallet_payment'
                         and row['inputs']['transfer_id'] == payment['asset_id'])
            self.assertEqual(trace['inputs']['cash_event']['tile'], 'Home')
            self.assertEqual(trace['inputs']['wallet_event']['tile'], 'Frontier')


if __name__ == '__main__':
    unittest.main()
