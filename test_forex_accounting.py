"""Actor statements for bilateral FX order-book matches."""
import unittest
from types import SimpleNamespace

from agent import Agent
from economy.actor_accounts import begin_turn, seal_turn
from forex import ForexDesk, fx_add
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


if __name__ == '__main__':
    unittest.main()
