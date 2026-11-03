import tempfile
import unittest
from pathlib import Path

from agent import Agent, initialize_agent
from goods import Goods
from region import Region
from region_market import trade, food_after_payroll
from run_trace import RunTrace


class MarketAffordabilityTraceTests(unittest.TestCase):
    def test_shared_budget_funds_meal_order_from_household_savings(self):
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

            trade(region, 1, defer_food_price=True)
            food_after_payroll(region, 1)

            rows = region._run_trace.query(turn=1, limit=10000)['events']
            withdrawal = next(row for row in rows
                              if row.get('kind') == 'bank_withdrawal_posted'
                              and row['inputs'].get('reason') == 'fund_market_bid')
            order = next(row for row in rows
                         if row.get('kind') == 'market_buyer_order_submitted'
                         and row.get('subject', {}).get('buyer_id') == buyer.id
                         and row.get('subject', {}).get('good') == Goods.food.name)
            budget = next(row for row in rows
                          if row.get('kind') == 'household_budget_plan'
                          and row.get('subject', {}).get('id') == buyer.id)

            self.assertGreater(withdrawal['inputs']['settled_amount'], 0.0)
            self.assertIn(withdrawal['event_id'],
                          order['inputs']['cash_funding_event_ids'])
            self.assertIn(withdrawal['event_id'], budget['cause_event_ids'])
            self.assertGreater(order['value_after'], 0)
            self.assertLessEqual(budget['value_after'], budget['inputs']['cash_budget'])

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

            trade(region, 1, defer_food_price=True)
            food_after_payroll(region, 1)

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
            self.assertIn(withdrawal_id, order['inputs']['cash_funding_event_ids'])
            self.assertTrue(all(next(row for row in rows if row['event_id'] == ident)['kind'] == 'bank_withdrawal_posted'
                                for ident in order['inputs']['cash_funding_event_ids']))
            self.assertEqual(withdrawal['inputs']['reason'], 'fund_market_bid')
            self.assertGreater(withdrawal['inputs']['settled_amount'], 0.0)


if __name__ == '__main__':
    unittest.main()
