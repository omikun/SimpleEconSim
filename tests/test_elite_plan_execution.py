import unittest
from collections import defaultdict
from dataclasses import replace
from goods import Goods
from world_config import ElitePlanningConfig
from economy.capitalist_planner import EliteCapitalistPlanner
from economy.elite_plan_execution import review_plan
from economy.elite_plan_receipts import observe_receipt
from tests.elite_plan_fixture import firm_fixture


def start_plan():
    region, firm, worker, supplier, buyer = firm_fixture()
    region._elite_planning_config = ElitePlanningConfig(mode='active', horizon=1)
    region.elite_planner = planner = EliteCapitalistPlanner()
    result = review_plan(planner, firm, region, 1)
    if not result:
        raise AssertionError('Fixture did not select a useful production chain')
    return region, firm, worker, supplier, buyer


def auction(region, good, seller, buyer, quantity, turn):
    from region_market import calculate_bid, calculate_bid_limit, calculate_ask_price, clear_discriminatory
    from economy.elite_plan_orders import attach_order
    buyer.remainingCash = buyer.cash
    bid = calculate_bid(region, buyer, good, region.recipes[good]['price'], 2,
                        region.recipes[buyer.output], buyer.employer is not None, 1)
    bid = min(bid, quantity)
    limit = calculate_bid_limit(region, buyer, good, region.recipes[good]['price'], 2, bid)
    row = dict(agent=buyer, quantity=bid, limit_price=limit)
    attach_order(region, buyer, good, row, turn)
    ask = calculate_ask_price(region, seller, good, region.recipes[good]['price'])
    orders = dict(buyers=[row], sellers=[dict(agent=seller, quantity=quantity, limit_price=ask)])
    return clear_discriminatory(region, good, region.recipes[good]['price'], quantity, bid,
                                [], region.agents, turn, local_orders=orders)


def finish_chain(region, firm, worker, supplier, buyer):
    from region_production import produce_corporation
    from region_finance import pay_wages
    auction(region, Goods.wood, supplier, firm, 2, 1)
    produce_corporation(region, firm, region.recipes[firm.output], firm.output,
                       {firm.output: 1}, defaultdict(float), turn=1)
    pay_wages(region, 1)
    region._last_turn = 2
    review_plan(region.elite_planner, firm, region, 2)
    auction(region, Goods.furniture, firm, buyer, 1, 2)
    return region.elite_planner._active_plans[firm.id]


class PlanExecutionTests(unittest.TestCase):
    def test_actual_auctions_production_and_payroll_complete_once(self):
        r, firm, worker, supplier, buyer = start_plan()
        opening = sum(a.cash for a in r.agents)
        plan = finish_chain(r, firm, worker, supplier, buyer)
        self.assertEqual(plan['status'], 'completed', plan)
        self.assertEqual((plan['output_produced'], plan['output_sold'], plan['inputs_remaining']), (1, 1, 0))
        self.assertGreater(plan['input_cost'], 0)
        self.assertEqual(plan['wages_paid'], 4)
        self.assertGreater(plan['sale_receipts'], plan['input_cost'] + plan['wages_paid'])
        self.assertAlmostEqual(opening, sum(a.cash for a in r.agents))
        before = dict(plan)
        for event in r.economic_events[1:]: observe_receipt(r, event)
        self.assertEqual(before, plan)
        self.assertTrue(any(e.get('detail', {}).get('plan_id') == plan['plan_id'] for e in r.economic_events))

    def test_due_plan_wakes_before_five_turn_cadence(self):
        r, firm, *_ = start_plan()
        self.assertTrue(r.elite_planner.should_run_planning(firm, r, 2, False))

    def test_prestocked_second_batch_keeps_plan_open_until_its_sale(self):
        from tests.elite_economic_cases import economic_cases, build_case
        from tests.elite_economic_accounts import FirmAccounts
        from tests.elite_economic_turn import run_turn
        r, firm = build_case(economic_cases()[8])
        r._elite_planning_config = ElitePlanningConfig(mode='active', horizon=2)
        r.elite_planner = EliteCapitalistPlanner()
        accounts = FirmAccounts(firm)
        run_turn(r, firm, 1, accounts)
        plan = r.elite_planner._active_plans[firm.id]
        self.assertEqual(plan['purchase_quantity'], 8)
        run_turn(r, firm, 2, accounts)
        self.assertEqual((plan['output_produced'], plan['output_sold']), (4, 2))
        self.assertNotEqual(plan['status'], 'completed')
        run_turn(r, firm, 3, accounts)
        self.assertEqual(plan['status'], 'completed')
        self.assertEqual(plan['output_sold'], 4)

    def test_legacy_pending_supply_offer_keeps_its_single_owner(self):
        r, firm, *_ = firm_fixture()
        r._elite_planning_config = ElitePlanningConfig(mode='active')
        r.elite_planner = EliteCapitalistPlanner()
        legacy = {'proposal_id': 7, 'budget': 10, 'status': 'active'}
        r.elite_planner._active_plans[firm.id] = legacy
        r.supply_proposals = [{'id':7, 'status':'proposed'}]
        self.assertIsNone(review_plan(r.elite_planner, firm, r, 1))
        self.assertIs(r.elite_planner._active_plans[firm.id], legacy)
        self.assertFalse(hasattr(r.elite_planner, '_next_plan_id'))
