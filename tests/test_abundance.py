"""Behavior and accounting of abundance, independent of a UI or long campaign."""
import copy
import pickle
import unittest
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import patch

from abundance import (household_plan, prepare_household_orders, consume_uses,
                       consider_workshops, proficiency, produce_workshop)
from agent import Agent, initialize_agent
from demographics_consumption import consume_daily_food
from goods import Goods
from region import Region
from region_market import (calculate_bid, calculate_bid_limit, update_price_ref,
                           price_decay, clear_discriminatory)
from region_production import produce_independent
from economic_replay import replay
from price_trace import replay_reference, replay_decay


class Trace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def person(good=Goods.food, cash=100, food=8):
    a = Agent(0)
    initialize_agent(a, good, 0, food, cash)
    a.remainingCash = cash
    a.region = 'Test'
    return a


def fixture():
    r = Region('Test', 0, 0, number_of_traders=0)
    r._last_turn = 10
    return r


class AbundanceTests(unittest.TestCase):
    def test_one_budget_covers_all_limits_and_meals_come_first(self):
        r = fixture()
        a = person(Goods.wood, cash=20, food=0)
        plan = household_plan(r, a)
        self.assertEqual(plan[Goods.food]['quantity'], 8)
        self.assertLessEqual(sum(row['quantity'] * row['limit'] for row in plan.values()), 20)
        a.remainingCash = 3
        plan = household_plan(r, a)
        self.assertEqual(set(plan), {Goods.food})
        self.assertEqual(plan[Goods.food]['quantity'], 2)

    def test_cheaper_staples_release_spending_without_unbounded_calories(self):
        r = fixture()
        a = person(Goods.wood, cash=50, food=0)
        r.recipes[Goods.food]['price'] = 4
        expensive = household_plan(r, a)
        r.recipes[Goods.food]['price'] = 0.2
        cheap = household_plan(r, a)
        self.assertEqual(expensive[Goods.food]['quantity'], cheap[Goods.food]['quantity'])
        extra = lambda p: sum(row['quantity'] for g, row in p.items() if g != Goods.food)
        self.assertGreater(extra(cheap), extra(expensive))
        self.assertLessEqual(cheap.get(Goods.prepared_food, {}).get('quantity', 0), 8)

    def test_cheaper_cloth_and_saturation_use_the_same_demand_rule(self):
        r = fixture()
        a = person(cash=100)
        r.recipes[Goods.cloth]['price'] = 18
        expensive = household_plan(r, a).get(Goods.cloth, {}).get('quantity', 0)
        r.recipes[Goods.cloth]['price'] = 0.2
        cheap = household_plan(r, a).get(Goods.cloth, {}).get('quantity', 0)
        self.assertGreater(cheap, expensive)
        a.inv_set(Goods.cloth, 6)
        self.assertNotIn(Goods.cloth, household_plan(r, a))
        self.assertNotIn(Goods.iron_ore, household_plan(r, a))

    def test_auction_orders_remain_funded_when_demand_raises_limits(self):
        r = fixture()
        a = person(Goods.wood, cash=30, food=0)
        r.agents = [a]
        prepare_household_orders(r, 10)
        total = 0
        for good, row in r.household_orders[a.id].items():
            if good == Goods.food:
                from food_access import household_bid
                # Meals settle after payroll; the early auction buys only productive inputs.
                self.assertEqual(calculate_bid(r, a, good, r.recipes[good]['price'], 99,
                                               r.recipes[a.output], False, 1), 0)
                qty = household_bid(a, r, r.recipes[good]['price'], a.cash)[0]
            else:
                qty = calculate_bid(r, a, good, r.recipes[good]['price'], 99,
                                    r.recipes[a.output], False, 1)
            limit = calculate_bid_limit(r, a, good, r.recipes[good]['price'], 5, qty)
            self.assertEqual(qty, row['quantity'])
            total += qty * limit
        self.assertLessEqual(total, a.cash)

    def test_successful_work_learns_but_blocked_production_does_not(self):
        r = fixture()
        r.terrain = {Goods.wood: 1}
        a = person(Goods.wood, cash=0, food=4)
        recipe = {**r.recipes[Goods.wood], 'production': 10, 'maxinv': 100,
                  'maxtotalprod': 100000}
        totals = defaultdict(int)
        with patch('region_production.rand.random', return_value=0):
            produce_independent(r, a, recipe, Goods.wood, {Goods.wood: 1}, totals)
        first = totals[Goods.wood]
        for _ in range(50):
            a.inv_set(Goods.wood, 0)
            with patch('region_production.rand.random', return_value=0):
                produce_independent(r, a, recipe, Goods.wood, {Goods.wood: 1}, totals)
        self.assertGreater(a.inv_get(Goods.wood), first)
        self.assertLess(proficiency(a, Goods.wood), 1.6)
        xp = copy.deepcopy(a.productive_practice)
        a.inv_set(Goods.wood, 100)
        produce_independent(r, a, recipe, Goods.wood, {Goods.wood: 1}, totals)
        self.assertEqual(a.productive_practice, xp)

    def test_processing_requires_equipment_and_protects_meals(self):
        r = fixture()
        a = person(Goods.prepared_food, food=12)
        recipe = r.recipes[Goods.prepared_food]
        totals = {}
        produce_workshop(r, a, recipe, totals, [], 10)
        self.assertEqual(totals, {})
        a.inv_set(Goods.furniture, 1)
        produce_workshop(r, a, recipe, totals, [], 10)
        self.assertEqual(a.inv_get(Goods.prepared_food), 4)
        self.assertEqual(a.inv_get(Goods.food), 8)
        self.assertEqual(a.inv_get(Goods.furniture), 1)
        self.assertEqual(a.cash, 100)
        a.inv_set(Goods.food, 4)
        produce_workshop(r, a, recipe, totals, [], 11)
        self.assertEqual(totals[Goods.prepared_food], 4)

    def test_processing_and_eating_conserve_calories_and_equipment(self):
        r = fixture()
        a = person(Goods.prepared_food, food=20)
        a.inv_set(Goods.furniture, 1)
        a.productive_practice = {'prepared_food': 100}
        before = a.inv_get(Goods.food)
        produce_workshop(r, a, r.recipes[Goods.prepared_food], {}, [], 10)
        self.assertEqual(a.inv_get(Goods.food) + a.inv_get(Goods.prepared_food), before)
        consume_uses(r, a)
        self.assertEqual(a.inv_get(Goods.furniture), 1)
        eaten = consume_daily_food(a, region=r, turn=10)
        self.assertEqual(eaten, 4)
        self.assertEqual(a.inv_get(Goods.food) + a.inv_get(Goods.prepared_food), before-4)
        self.assertEqual(a.calorie_deficit_kcal, 0)

    def test_meals_count_for_food_relief_and_corporations_can_order_equipment(self):
        from food_access import meal_gap, household_demand
        r = fixture()
        a = person(Goods.wood, food=0)
        a.inv_set(Goods.prepared_food, 4)
        self.assertEqual(meal_gap(a), 0)
        self.assertEqual(household_demand(a, r, reserve_turns=0)['desired'], 0)
        firm = person(Goods.prepared_food, cash=100)
        firm.is_corporation = True
        recipe = r.recipes[Goods.prepared_food]
        bid = calculate_bid(r, firm, Goods.furniture, 25, 99, recipe, False, 1)
        self.assertEqual(bid, 1)
        firm.inv_set(Goods.furniture, 1)
        self.assertEqual(calculate_bid(r, firm, Goods.furniture, 25, 99, recipe, False, 1), 0)

    def test_the_same_workshop_engine_handles_nonfood_recipes(self):
        r = fixture()
        a = person(Goods.cloth, food=8)
        a.inv_set(Goods.wool, 10)
        a.inv_set(Goods.furniture, 1)
        recipe = {**r.recipes[Goods.cloth], 'setup_good': Goods.furniture, 'setup_units': 1}
        produce_workshop(r, a, recipe, {}, [], 10)
        self.assertEqual(a.inv_get(Goods.cloth), 1)
        self.assertEqual(a.inv_get(Goods.wool), 8)
        self.assertEqual(a.inv_get(Goods.food), 8)

    def test_posted_prices_alone_do_not_justify_converting_farmland(self):
        from economy.transformation_graph import TransformationOperator
        r = fixture()
        a = person()
        op = TransformationOperator(id='pasture_test', name='Pasture', category='enclosure',
                                    output_goods={Goods.wool: 12}, cash_cost=15)
        self.assertEqual(op.estimate_net_return(a, r, 1), -15)
        r.demand_log[Goods.wool] = [24]
        self.assertGreater(op.estimate_net_return(a, r, 1), 0)

    def test_savings_are_funded_once_and_post_payroll_orders_are_not_capped_by_old_plan(self):
        r = fixture()
        a = person(Goods.wood, cash=0, food=0)
        r.agents = [a]
        r.bank.deposits[a] = 10
        r.bank.total_deposits = 10
        r.bank.capital += 10
        prepare_household_orders(r, 10)
        budget = sum(row['quantity'] * row['limit'] for row in r.household_orders[a.id].values())
        self.assertLessEqual(budget, a.cash)
        self.assertGreater(r.household_orders[a.id][Goods.food]['quantity'], 0)
        self.assertAlmostEqual(a.cash+r.bank.deposits[a], 10)
        r.household_budget_active = False
        a.cash = 20
        self.assertGreater(calculate_bid_limit(r, a, Goods.food, 1, 2, 4), 0)

    def test_workshop_entry_needs_funded_orders_capital_and_departure_capacity(self):
        r = fixture()
        candidates = [person(Goods.wood, cash=100, food=8) for _ in range(8)]
        for candidate in candidates:
            candidate.productivity = .8
        buyer = person(Goods.food, cash=100, food=8)
        r.agents = [*candidates, buyer]
        r.recipes[Goods.food]['price'] = .2
        r.recipes[Goods.prepared_food]['price'] = 5
        consider_workshops(r, 10)
        self.assertTrue(all(c.output == Goods.wood for c in candidates))
        # The next turn has actual funded orders but no startup capital.
        r.household_orders = {buyer.id: {Goods.prepared_food: {'quantity': 4, 'limit': 5}}}
        for candidate in candidates:
            candidate.cash = 1
        consider_workshops(r, 11)
        self.assertTrue(all(c.output == Goods.wood for c in candidates))
        for candidate in candidates:
            candidate.cash = 100
        # A viable livelihood retains its workers; an actual meal failure triggers a search.
        candidates[0].calorie_deficit_kcal = 500
        consider_workshops(r, 12)
        entrants = [c for c in candidates if c.output == Goods.prepared_food]
        self.assertEqual(len(entrants), 1)
        self.assertEqual(entrants[0].cash, 100)  # no setup fee disappears
        self.assertEqual(entrants[0].inv_get(Goods.prepared_food), 0)
        # Reentering another subsystem cannot grant another decision this turn.
        consider_workshops(r, 12)
        self.assertEqual(sum(c.output == Goods.prepared_food for c in candidates), 1)

    def test_excess_supply_can_push_raw_and_processed_prices_below_old_floors(self):
        r = fixture()
        for good in (Goods.food, Goods.furniture):
            a = person(good)
            a.inv_set(good, r.recipes[good]['maxinv'])
            r.agents = [a]
            r._price_ref[good] = r.recipes[good]['price'] = .8
            r._trade_prices[good] = []
            for _ in range(30):
                update_price_ref(r, good, 0.1)
            self.assertLess(r.recipes[good]['price'], .8)
            self.assertGreaterEqual(r.recipes[good]['price'], .1)

    def test_trace_replays_new_prices_processing_practice_and_budget(self):
        r = fixture()
        r._run_trace = Trace()
        r._collective_trace_clock = {'turn': 10, 'phase': 'test', 'next': 1}
        a = person(Goods.prepared_food, food=20)
        a.inv_set(Goods.furniture, 1)
        r.agents = [a]
        prepare_household_orders(r, 10)
        produce_workshop(r, a, r.recipes[a.output], {}, [], 10)
        update_price_ref(r, Goods.wood, 0.1)
        price_decay(r, Goods.furniture)
        consume_daily_food(a, region=r, turn=10)
        for row in r._run_trace.rows:
            if row.get('formula_id') in ('market.reference.v1', 'market.reference.v2'):
                value = replay_reference(row['inputs'], dated=row['formula_id'].endswith('.v2'))['final']
            elif row.get('formula_id') == 'market.decay.v1':
                value = replay_decay(row['inputs'])
            elif row.get('formula_id') in ('production.practice.v1', 'demand.funded_basket.v1',
                                           'production.workshop.v1', 'nutrition.prepared_food.v1'):
                value = replay({**row, 'value_before': row.get('before')})
            else:
                continue
            self.assertAlmostEqual(value, row['after'])

    def test_save_reload_extends_old_wallets_and_keeps_practice(self):
        a = person()
        a.productive_practice = {'food': 12}
        for name in ('inventory', 'inventory_export', 'inventory_foreign', 'cost_basis'):
            setattr(a, name, getattr(a, name)[:Goods.prepared_food.value])
        restored = pickle.loads(pickle.dumps(a))
        restored.inv_add(Goods.prepared_food, 2)
        self.assertEqual(restored.inv_get(Goods.prepared_food), 2)
        self.assertEqual(restored.productive_practice, {'food': 12})
        r = fixture()
        r.goods.remove(Goods.prepared_food)
        del r.recipes[Goods.prepared_food]
        del r.abundance_enabled
        restored_region = pickle.loads(pickle.dumps(r))
        self.assertIn(Goods.prepared_food, restored_region.goods)
        self.assertIn(Goods.prepared_food, restored_region.recipes)


if __name__ == '__main__':
    unittest.main()
