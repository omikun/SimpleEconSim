"""Actor statements for bilateral FX order-book matches."""
import unittest
from types import SimpleNamespace

from agent import Agent
from economy.actor_accounts import begin_turn, seal_turn
from econsim_trade_money import Bank
from forex import (ForexDesk, buy_fx_from_bank, flush_pending_trader_float_traces,
                   fx_add, seed_trader_wallet, sell_fx_to_bank)
from wilderness import enter_claimed, enter_wilderness


class Recorder:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        row['event_id'] = f"test:{clock['next']}"
        clock['next'] += 1
        self.rows.append(row)
        return row['event_id']


class ForexAccountingTests(unittest.TestCase):
    def test_bank_fx_conversions_trace_foreign_wallet_delta_in_both_directions(self):
        trader = Agent(0)
        trader.is_trader = True
        trader.home_currency = 'A'
        trader.cash = 2.0
        fx_add(trader, 'B', 5.0)
        bank = Bank()
        bank.fx_pool = 20.0
        bank.foreign_reserves['B'] = 0.0
        region = SimpleNamespace(
            name='FXHome', home_currency='A', agents=[trader],
            cash_obligations=[], economic_events=[], _last_turn=2)
        recorder = Recorder()
        region._collective_trace_clock = {
            'turn': 2, 'phase': 'trade', 'next': 1}
        region._run_trace = recorder

        self.assertAlmostEqual(sell_fx_to_bank(bank, trader, 'B', 4.0, 2.0,
                                               trace_region=region), 8.0)
        self.assertAlmostEqual(buy_fx_from_bank(bank, trader, 'B', 2.0, 2.0,
                                                trace_region=region), 2.0)

        events = [row for row in recorder.rows
                  if row['kind'] == 'fx_conversion_executed']
        self.assertEqual(len(events), 2)
        self.assertEqual([row['inputs']['direction'] for row in events],
                         ['sell_foreign', 'buy_foreign'])
        self.assertEqual(events[0]['metric_id'], 'trade.fx_conversion')
        self.assertEqual((events[0]['before'], events[0]['after']), (5.0, 1.0))
        self.assertEqual((events[1]['before'], events[1]['after']), (1.0, 3.0))
        self.assertEqual((events[0]['unit'], events[1]['unit']), ('B', 'B'))
        self.assertEqual(events[0]['inputs']['home_paid'], 8.0)
        self.assertEqual((events[0]['inputs']['bank_fx_pool_before'],
                          events[0]['inputs']['bank_fx_pool_after']), (20.0, 12.0))
        self.assertEqual((events[1]['inputs']['bank_fx_pool_before'],
                          events[1]['inputs']['bank_fx_pool_after']), (12.0, 16.0))
        self.assertEqual((bank.fx_pool, bank.foreign_reserves['B']), (16.0, 2.0))

    def test_matched_order_posts_cash_and_bilateral_wallet_legs(self):
        buyer = Agent(0)
        buyer.is_trader = True
        buyer.home_currency = 'A'
        buyer.cash = 100.0
        seller = Agent(0)
        seller.is_trader = True
        seller.home_currency = 'A'
        seller.cash = 0.0
        fx_add(seller, 'B', 10.0)
        region = SimpleNamespace(
            name='DeskHome', home_currency='A', agents=[buyer, seller],
            cash_obligations=[], tenure=None, recipes={}, bank=None,
            province=None, economic_events=[], _last_turn=4)
        recorder = Recorder()
        region._collective_trace_clock = {
            'turn': 4, 'phase': 'trade', 'next': 1}
        region._run_trace = recorder
        begin_turn(region, 4)
        desk = ForexDesk('A', 'B', mid=1.0, spread=0.0,
                         seed_reserves=False)
        desk.post_order('bid', buyer, 5.0, 1.2)
        desk.post_order('ask', seller, 5.0, 1.1)

        matched = desk.clear_book(region, t=4)

        accounts = {row['actor_id']: row for row in seal_turn(region, 4)}
        buyer_account = accounts[buyer.id]
        seller_account = accounts[seller.id]
        trace = next(row for row in recorder.rows
                     if row['kind'] == 'fx_order_match')
        events = region.economic_events
        cash_event = next(event for event in events
                          if event['kind'] == 'fx_order_cash_transfer')
        wallet_out = next(event for event in events
                          if event['kind'] == 'wallet_transfer_out')
        wallet_in = next(event for event in events
                         if event['kind'] == 'wallet_transfer_in')

        self.assertAlmostEqual(matched, 5.5)
        self.assertAlmostEqual(buyer.cash, 94.5)
        self.assertAlmostEqual(seller.cash, 5.5)
        self.assertAlmostEqual(buyer_account['posted_cash_change'], -5.5)
        self.assertAlmostEqual(seller_account['posted_cash_change'], 5.5)
        self.assertAlmostEqual(buyer_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(seller_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(buyer_account['wallet_change_by_currency']['B'], 5.0)
        self.assertAlmostEqual(seller_account['wallet_change_by_currency']['B'], -5.0)
        self.assertAlmostEqual(buyer_account['wallet_transfer_in_by_currency']['B'], 5.0)
        self.assertAlmostEqual(seller_account['wallet_transfer_out_by_currency']['B'], 5.0)
        self.assertEqual(cash_event['asset_id'], wallet_out['asset_id'])
        self.assertEqual(cash_event['asset_id'], wallet_in['asset_id'])
        self.assertEqual(trace['metric_id'], 'trade.fx_order_match')
        self.assertAlmostEqual(trace['inputs']['home_paid'], cash_event['amount'])
        self.assertEqual(trace['inputs']['wallet_in_event']['event_id'], wallet_in['id'])

    def test_wilderness_cash_wallet_transitions_post_linked_conversion_legs(self):
        agent = Agent(0)
        agent.home_currency = 'USD'
        agent.cash = 12.0
        wilderness = SimpleNamespace(
            name='Frontier', home_currency=None, wilderness=True,
            is_ocean=False, elevation=0.0, agents=[agent], cash_obligations=[],
            tenure=None, recipes={}, bank=None, province=None,
            economic_events=[], _last_turn=1)
        recorder = Recorder()
        wilderness._collective_trace_clock = {'turn': 1, 'phase': 'move', 'next': 1}
        wilderness._run_trace = recorder

        begin_turn(wilderness, 1)
        enter_wilderness(wilderness, agent, 1)

        frontier_account = {row['actor_id']: row for row in seal_turn(wilderness, 1)}[agent.id]
        cash_to_wallet = [event for event in wilderness.economic_events
                          if event['kind'] == 'fx_conversion']
        wallet_in = [event for event in wilderness.economic_events
                     if event['kind'] == 'wallet_transfer_in']
        self.assertEqual(agent.cash, 0.0)
        self.assertAlmostEqual(agent.wallets['USD'], 12.0)
        self.assertAlmostEqual(frontier_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(frontier_account['fx_converted_out'], 12.0)
        self.assertEqual(cash_to_wallet[0]['asset_id'], wallet_in[0]['asset_id'])
        self.assertEqual(recorder.rows[0]['metric_id'], 'finance.cash_wallet_conversion')

        claimed = SimpleNamespace(
            name='Claimed', home_currency='USD', wilderness=False,
            agents=[agent], cash_obligations=[], tenure=None, recipes={},
            bank=None, province=None, economic_events=[], _last_turn=2)
        claimed._collective_trace_clock = {'turn': 2, 'phase': 'move', 'next': 1}
        claimed._run_trace = recorder
        begin_turn(claimed, 2)
        enter_claimed(claimed, agent, 2)

        claimed_account = {row['actor_id']: row for row in seal_turn(claimed, 2)}[agent.id]
        cash_from_wallet = next(event for event in claimed.economic_events
                                if event['kind'] == 'fx_conversion')
        wallet_out = next(event for event in claimed.economic_events
                          if event['kind'] == 'wallet_transfer_out')
        self.assertAlmostEqual(agent.cash, 12.0)
        self.assertAlmostEqual(agent.wallets.get('USD', 0.0), 0.0)
        self.assertAlmostEqual(claimed_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(claimed_account['fx_converted_in'], 12.0)
        self.assertEqual(cash_from_wallet['asset_id'], wallet_out['asset_id'])

    def test_initial_trader_float_links_cash_deposit_and_foreign_reserve(self):
        trader = Agent(0)
        trader.is_trader = True
        trader.home_currency = 'A'
        trader.cash = 10.0
        bank = SimpleNamespace(
            deposits={trader: 50.0}, total_deposits=50.0,
            fx_pool=0.0, foreign_reserves={'B': 100.0}, loans=[])
        region = SimpleNamespace(
            name='FloatHome', home_currency='A', agents=[trader], bank=bank,
            cash_obligations=[], tenure=None, recipes={}, province=None,
            economic_events=[], _last_turn=0)
        begin_turn(region, 0)
        desk = ForexDesk('A', 'B', mid=1.0, spread=0.0,
                         seed_reserves=False)
        amount = seed_trader_wallet(
            region, SimpleNamespace(home_currency='B'), t=0, desk=desk)

        recorder = Recorder()
        region._collective_trace_clock = {'turn': 0, 'phase': 'setup', 'next': 1}
        region._run_trace = recorder
        self.assertEqual(flush_pending_trader_float_traces(region), 1)
        account = {row['actor_id']: row for row in seal_turn(region, 0)}[trader.id]
        events = {event['kind']: event for event in region.economic_events}
        trace = recorder.rows[0]

        self.assertAlmostEqual(amount, 60.0)
        self.assertAlmostEqual(trader.cash, 0.0)
        self.assertAlmostEqual(bank.deposits[trader], 0.0)
        self.assertAlmostEqual(trader.wallets['B'], 60.0)
        self.assertAlmostEqual(bank.fx_pool, 60.0)
        self.assertAlmostEqual(bank.foreign_reserves['B'], 40.0)
        self.assertAlmostEqual(account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(account['fx_converted_out'], 60.0)
        self.assertAlmostEqual(account['bank_deposit_fx_converted_out'], 50.0)
        self.assertAlmostEqual(account['wallet_transfer_in_by_currency']['B'], 60.0)
        self.assertEqual(events['fx_conversion']['amount'], 10.0)
        self.assertEqual(events['bank_fx_deposit_conversion']['amount'], 50.0)
        self.assertEqual(events['fx_conversion']['asset_id'],
                         events['wallet_transfer_in']['asset_id'])
        self.assertEqual(trace['metric_id'], 'trade.fx_trader_float')
        self.assertEqual(trace['inputs']['deposit_event']['event_id'],
                         events['bank_fx_deposit_conversion']['id'])


if __name__ == '__main__':
    unittest.main()
