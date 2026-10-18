import tempfile
import unittest
from pathlib import Path

from agent import Agent, initialize_agent
from goods import Goods
from region import Region
from region_market import trade
from run_trace import RunTrace


class MarketAffordabilityTraceTests(unittest.TestCase):
    def test_market_zero_order_links_cash_affordability_and_bank_draw(self):
        with tempfile.TemporaryDirectory() as directory:
            region = Region('Cash Poor Parish', t=0, number_of_agents=0)
            buyer = Agent(0)
            initialize_agent(buyer, Goods.none, 0, 0, 0.0)
            buyer.alive = True
            buyer.is_trader = False
            buyer.is_corporation = False
            buyer.is_government = False
            buyer.remainingCash = 0.0
            region.agents.append(buyer)
            region.bank.deposits[buyer] = 5.0
            region.bank.total_deposits = 5.0
            region._run_trace = RunTrace(
                Path(directory) / 'affordability.ctr', 'affordability-fixture')
            region._collective_trace_clock = {
                'turn': 1, 'phase': 'trade', 'next': 1}

            trade(region, 1)

            rows = region._run_trace.query(turn=1, limit=10000)['events']
            withdrawal = next(row for row in rows
                              if row.get('kind') == 'bank_withdrawal_posted'
                              and row['inputs'].get('reason') == 'fund_market_bid')
            summary = next(row for row in rows
                           if row.get('kind') == 'market_zero_order_summary'
                           and row.get('subject', {}).get('good') == Goods.food.name)
            buyer_group = next(group for group in
                               summary['inputs']['buyers_by_reason']
                               if any(order.get('agent_id') == buyer.id
                                      for order in group['orders']))
            buyer_evidence = next(order for order in buyer_group['orders']
                                  if order.get('agent_id') == buyer.id)

            self.assertGreater(withdrawal['inputs']['settled_amount'], 0.0)
            self.assertIn(withdrawal['event_id'],
                          buyer_evidence['cash_funding_event_ids'])
            self.assertIn(withdrawal['event_id'], summary['cause_event_ids'])
            self.assertEqual(buyer_evidence['cash_affordable_units_at_bid'], 0)
            self.assertEqual(buyer_evidence['cash_affordability_basis'],
                             'remainingCash')
            self.assertEqual(buyer_evidence['cash_affordability_formula_id'],
                             'market.cash_affordability_ceiling.v1')
            self.assertEqual(buyer_group['reason'], 'cash_at_or_below_unit_price')

    def test_bank_draw_causes_a_positive_market_order(self):
        with tempfile.TemporaryDirectory() as directory:
            region = Region('Liquid Parish', t=0, number_of_agents=0)
            buyer = Agent(0)
            initialize_agent(buyer, Goods.wood, 0, 0, 5.0)
            buyer.alive = True
            buyer.is_trader = False
            buyer.is_corporation = False
            buyer.is_government = False
            buyer.remainingCash = 5.0
            region.agents.append(buyer)
            region.bank.deposits[buyer] = 2.0
            region.bank.total_deposits = 2.0
            region._run_trace = RunTrace(
                Path(directory) / 'funded-order.ctr', 'funded-order-fixture')
            region._collective_trace_clock = {
                'turn': 1, 'phase': 'trade', 'next': 1}

            trade(region, 1)

            rows = region._run_trace.query(turn=1, limit=10000)['events']
            order = next(row for row in rows
                         if row.get('kind') == 'market_buyer_order_submitted'
                         and row.get('subject', {}).get('buyer_id') == buyer.id
                         and row.get('subject', {}).get('good') == Goods.food.name)
            withdrawal_id = next(
                event_id for event_id in order['cause_event_ids']
                if next(candidate for candidate in rows
                        if candidate['event_id'] == event_id).get('kind')
                == 'bank_withdrawal_posted')
            withdrawal = next(row for row in rows
                              if row['event_id'] == withdrawal_id)

            self.assertGreater(order['value_after'], 0)
            self.assertEqual(order['inputs']['cash_funding_event_ids'],
                             [withdrawal_id])
            self.assertEqual(withdrawal['inputs']['reason'], 'fund_market_bid')
            self.assertGreater(withdrawal['inputs']['settled_amount'], 0.0)


if __name__ == '__main__':
    unittest.main()
