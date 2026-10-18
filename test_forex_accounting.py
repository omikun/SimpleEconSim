"""Actor statements for bilateral FX order-book matches."""
import unittest
from types import SimpleNamespace

from agent import Agent
from economy.actor_accounts import begin_turn, seal_turn
from forex import ForexDesk, fx_add


class Recorder:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        row['event_id'] = f"test:{clock['next']}"
        clock['next'] += 1
        self.rows.append(row)
        return row['event_id']


class ForexAccountingTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
