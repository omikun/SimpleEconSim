import unittest
from goods import Goods
from world_config import ElitePlanningConfig
from economy.capitalist_planner import EliteCapitalistPlanner
from economy.elite_plan_orders import current_signature, input_bid, attach_order, cap_limit, spendable_cash
from tests.elite_plan_fixture import firm_fixture


def ready_plan(region, firm):
    firm.remainingCash = firm.cash
    region._elite_planning_config = ElitePlanningConfig(mode='active')
    region.elite_planner = EliteCapitalistPlanner()
    plan = dict(kind='production_chain', plan_id='fixture:1', status='ready', reserve=4,
        deadline=4, input_good='wood', output_good='furniture', signature=current_signature(firm, region),
        target_stock=2, purchase_quantity=2, input_filled=0, limit_price=3,
        created_turn=1, output_produced=0, output_sold=0, opening_outputs=0, last_receipt=0)
    region.elite_planner._active_plans[firm.id] = plan
    return plan


class PlanOrderTests(unittest.TestCase):
    def test_single_bid_replaces_ordinary_buffer_and_has_stable_identity(self):
        from region_market import calculate_bid, calculate_bid_limit
        r, firm, *_ = firm_fixture()
        firm.remainingCash = firm.cash
        plan = ready_plan(r, firm)
        self.assertEqual(calculate_bid(r, firm, Goods.wood, 3, 10, r.recipes[firm.output], False, 1), 2)
        row = {'agent':firm, 'quantity':2}
        attach_order(r, firm, Goods.wood, row, 1)
        self.assertEqual(row['plan_id'], 'fixture:1')
        self.assertEqual(input_bid(r, firm, Goods.wood), 0)
        self.assertLessEqual(calculate_bid_limit(r, firm, Goods.wood, 3, 2, 2), 3)
        self.assertEqual(spendable_cash(r, firm), 16)
        self.assertEqual(cap_limit(r, firm, Goods.furniture, 2, 20), 8)
        r._elite_planning_config = ElitePlanningConfig()
        self.assertIsNone(input_bid(r, firm, Goods.wood))
        self.assertEqual(spendable_cash(r, firm), 20)

    def test_partial_input_and_changed_workforce_cannot_overbuy(self):
        r, firm, worker, *_ = firm_fixture()
        plan = ready_plan(r, firm)
        firm.inv_set(Goods.wood, 1)
        plan['input_filled'] = 1
        self.assertEqual(input_bid(r, firm, Goods.wood), 1)
        worker.is_striking = True
        self.assertEqual(input_bid(r, firm, Goods.wood), 0)
