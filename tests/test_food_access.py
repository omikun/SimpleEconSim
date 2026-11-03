"""Food must remain purchasable, owned, and conserved across meal access paths."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from goods import Goods
from region import Region
from food_access import household_demand, business_food_target, food_surplus
from region_market import (calculate_bid, calculate_bid_limit, calculate_ask,
                           clear_discriminatory, food_after_payroll)
from region_finance import redeem_company_scrip
from region_production import release_emergency_food


class FoodAccessTests(unittest.TestCase):
    def setUp(self):
        self.region = Region('Food access', 0, 0, number_of_traders=0)
        self.region.agents = []
        self.region._last_turn = 1

    def person(self, good=Goods.furniture, cash=197, food=0):
        actor = Agent(0)
        initialize_agent(actor, good, 0, 0, cash)
        actor.remainingCash = cash
        actor.inv_set(Goods.food, food)
        actor.region = self.region.name
        self.region.agents.append(actor)
        return actor

    def bid(self, buyer, price=8.62):
        if not buyer.is_corporation:
            from food_access import household_bid
            return household_bid(buyer, self.region, price, buyer.remainingCash)[0]
        return calculate_bid(self.region, buyer, Goods.food, price, 16,
                             self.region.recipes[buyer.output], buyer.employer is not None,
                             buyer.consumption_multiplier)

    def test_large_desired_basket_can_still_buy_affordable_meal(self):
        buyer = self.person()
        buyer.consumption_multiplier = 3
        seller = self.person(Goods.food, food=40)
        quantity = self.bid(buyer)
        limit = calculate_bid_limit(self.region, buyer, Goods.food, 8.62, 2, quantity)
        units, paid, _ = clear_discriminatory(
            self.region, Goods.food, 8.62, 10, quantity, [], self.region.agents, 1,
            local_orders={'buyers': [{'agent': buyer, 'quantity': quantity, 'limit_price': limit}],
                          'sellers': [{'agent': seller, 'quantity': 10, 'limit_price': 8.06}]})
        self.assertGreaterEqual(units, 4)
        self.assertLessEqual(paid, 197)
        self.assertEqual(buyer.inv_get(Goods.food, 0) + seller.inv_get(Goods.food, 0), 40)

    def test_household_target_is_independent_of_profession_and_queued_meals_count(self):
        buyer = self.person()
        target = household_demand(buyer, self.region)['target']
        bid = self.bid(buyer)
        buyer.output = Goods.food
        self.assertEqual(household_demand(buyer, self.region)['target'], target)
        self.assertEqual(self.bid(buyer), bid)
        buyer.emergency_food_units = target
        self.assertEqual(self.bid(buyer), 0)

    def test_partial_meal_and_actual_unaffordability(self):
        buyer = self.person(cash=12)
        self.assertGreaterEqual(self.bid(buyer, 8), 1)
        buyer.cash = buyer.remainingCash = 0
        self.assertEqual(self.bid(buyer), 0)

    def test_nonfood_firm_only_buys_for_real_commitments_and_resells(self):
        firm = self.person(food=54)
        firm.is_corporation = True
        worker = self.person()
        worker.employer = firm
        firm.employees = [worker]
        self.assertEqual(business_food_target(firm, self.region), 0)
        self.assertEqual(self.bid(firm), 0)
        self.assertEqual(calculate_ask(self.region, firm, Goods.food, 2, False), 54)
        firm.pay_mode = 'scrip'
        self.assertGreater(business_food_target(firm, self.region), 0)
        worker.alive = False
        self.assertEqual(business_food_target(firm, self.region), 0)

    def test_cash_worker_can_buy_company_food_and_conserve_cash(self):
        firm = self.person(cash=100, food=10)
        firm.is_corporation = True
        worker = self.person(cash=20)
        worker.employer = firm
        firm.employees = [worker]
        self.region.food_price = 2
        redeem_company_scrip(self.region, 1)
        self.assertEqual(worker.inv_get(Goods.food, 0), 4)
        self.assertEqual(firm.inv_get(Goods.food, 0), 6)
        self.assertAlmostEqual(worker.cash + firm.cash, 120)
        self.assertEqual(worker.company_debt, 0)

    def test_employed_household_can_sell_only_surplus(self):
        person = self.person(food=30)
        person.employer = self.person()
        self.assertEqual(calculate_ask(self.region, person, Goods.food, 2, True),
                         food_surplus(person, self.region))
        self.assertGreater(food_surplus(person, self.region), 0)

    def test_after_payday_meal_settles_once_and_publishes_one_price(self):
        buyer = self.person(cash=5)
        seller = self.person(Goods.food, cash=0, food=30)
        self.region._food_market_pending = {'turn': 1, 'reference': 1,
            'bids': 0, 'asks': 18, 'imported_asks': 0, 'cause_ids': [],
            'private_units': 0, 'realized': 1}
        self.region._trade_prices = {Goods.food: [1]}
        self.region._food_log_starts = {'_trade_prices': 0, 'sold_log': 0}
        self.region._auction_import_sales = {Goods.food: (2, 3)}
        self.region._auction_import_sales_by_source = {Goods.food: {'Neighbor': {'quantity': 2}}}
        total = buyer.cash + seller.cash
        with patch('region_market.update_price_ref', wraps=__import__('region_market').update_price_ref) as publish:
            units = food_after_payroll(self.region, 1)
            self.assertGreater(units, 0)
            self.assertEqual(food_after_payroll(self.region, 1), 0)
            self.assertEqual(publish.call_count, 1)
        self.assertAlmostEqual(buyer.cash + seller.cash, total)
        self.assertEqual(buyer.inv_get(Goods.food, 0) + seller.inv_get(Goods.food, 0), 30)
        self.assertEqual(self.region._auction_import_sales[Goods.food], (2, 3))
        self.assertEqual(len(self.region._trade_prices[Goods.food]), 1)

    def test_emergency_release_outside_season_is_bounded_and_conserved(self):
        people = [self.person(cash=0) for _ in range(4)]
        self.region.granary_stock = 20
        self.region.gov.food_inventory = 0
        self.region.gov.emergency_food_policy = True
        self.region.granary_handling_capacity = 9
        released = release_emergency_food(self.region, 5)
        self.assertEqual(released, 9)
        self.assertEqual(self.region.granary_stock + self.region.gov.food_inventory, 20)
        self.assertEqual(release_emergency_food(self.region, 5), 0)

    def test_policy_off_does_not_trigger_emergency_release(self):
        self.person(cash=0)
        self.region.granary_stock = 120
        self.region.gov.food_inventory = 0
        self.region.gov.emergency_food_policy = False
        self.assertEqual(release_emergency_food(self.region, 5), 0)
        self.assertEqual(self.region.granary_stock, 120)
        self.assertEqual(self.region.granary_release_status['reason'], 'Emergency release disabled')

    def test_new_payday_cash_is_not_blocked_by_an_earlier_empty_basket(self):
        buyer = self.person(cash=10)
        seller = self.person(Goods.food, cash=0, food=30)
        with patch('abundance.order', return_value={'quantity': 0, 'limit': 0}):
            self.assertEqual(calculate_bid_limit(self.region, buyer, Goods.food, 1, 2, 4), 0)
            self.assertGreater(food_after_payroll(self.region, 1), 0)
        self.assertGreater(buyer.inv_get(Goods.food, 0), 0)

    def test_wage_response_can_be_enabled_without_enabling_owner_strategies(self):
        from region_labor import adjust_wages
        firm = self.person(cash=1000)
        firm.is_corporation = True
        firm.wage = 2
        firm.max_employees = 4
        self.region.scenario_owner_policy = True
        with patch('region_labor.calculate_labor_market_tightness', return_value=2), patch(
                'region_labor.calculate_firm_wage_ceiling', return_value=10), patch(
                'region_labor.evaluate_worker_reservation_wage', return_value=8):
            adjust_wages(self.region, 1)
            self.assertEqual(firm.wage, 2)
            self.region.responsive_wages = True
            adjust_wages(self.region, 1)
            self.assertGreater(firm.wage, 2)
            self.assertLessEqual(firm.wage, 10)

    def test_food_fill_trace_replays_and_explains_an_unfilled_order(self):
        from tests.test_food_security_recovery import MemoryTrace
        from economic_replay import replay
        trace = MemoryTrace()
        self.region._run_trace = trace
        self.region._collective_trace_clock = {'next': 1, 'turn': 1, 'phase': 'trade'}
        buyer = self.person(cash=1)
        seller = self.person(Goods.food, food=30)
        clear_discriminatory(self.region, Goods.food, 2, 10, 4, [], self.region.agents, 1,
            local_orders={'buyers': [{'agent': buyer, 'quantity': 4, 'limit_price': 0.25}],
                          'sellers': [{'agent': seller, 'quantity': 10, 'limit_price': 2}]})
        event = next(row for row in trace.rows if row['kind'] == 'food_purchase_result')
        self.assertEqual(event['inputs']['reason'], 'below_seller_price')
        self.assertEqual(replay(event), event['after'])

    def test_last_grain_unit_is_available_in_emergency(self):
        self.person(cash=0)
        self.region.granary_stock = 1
        self.region.gov.food_inventory = 0
        self.region.gov.emergency_food_policy = True
        self.assertEqual(release_emergency_food(self.region, 5), 1)

    def test_parent_orders_child_meal_once_and_protects_it(self):
        parent = self.person(cash=100, food=4)
        child = self.person(cash=0)
        child.is_native_child = True
        child.parent = parent
        child.birth_turn = 0
        child.calorie_need_kcal = 1000
        self.assertTrue(household_demand(child, self.region)['dependent_order'])
        self.assertEqual(household_demand(child, self.region)['desired'], 0)
        self.assertGreater(household_demand(parent, self.region)['meal_gap'], 0)
        self.assertEqual(food_surplus(parent, self.region), 0)

    def test_charity_arrives_before_daily_intake_and_is_not_repeated(self):
        from micro.region.stepper import live
        import econsim_live
        person = self.person(cash=0, food=3)
        person.hungry_steps = 2
        self.region.charity.food_inventory = 1
        self.region.gov.food_inventory = 0
        with patch('econsim_live.handle_death', return_value=False), patch(
                'econsim_live.consume_daily_food', wraps=econsim_live.consume_daily_food) as meal:
            live(self.region, 1)
        call = next(c for c in meal.call_args_list if c.args[0] is person)
        self.assertEqual(person.last_calories_eaten, 2000)
        self.assertEqual(person.calorie_deficit_kcal, 0)
        self.region.charity.food_inventory = 1
        self.region.charity.distribute_food(1, self.region.agents, regions=(self.region,))
        self.assertEqual(self.region.charity.food_inventory, 1)

    def test_food_security_explains_stocks_and_policy(self):
        from food_security import diagnose_tile
        person = self.person(cash=0)
        person.calorie_deficit_kcal = 1000
        firm = self.person(food=40)
        firm.is_corporation = True
        self.region.granary_stock = 120
        status = diagnose_tile(self.region)
        self.assertEqual(status['company_food_units'], 40)
        self.assertEqual(status['granary_food_units'], 120)
        self.assertIn('Households cannot afford the next meal', status['access_reasons'])
        self.assertIn('Emergency release disabled', status['access_reasons'])


if __name__ == '__main__':
    unittest.main()
