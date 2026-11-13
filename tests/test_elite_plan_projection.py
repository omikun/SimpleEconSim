import pickle
import unittest
from collections import defaultdict
from dataclasses import replace
from goods import Goods
from economy.elite_planning_state import capture_planning_state
from economy.elite_planning_projection import purchase, finish_turn, score_terminal, baseline
from tests.elite_plan_fixture import firm_fixture
from tests.test_elite_plan_search import snapshot


class ProjectionTests(unittest.TestCase):
    def test_real_production_and_pure_snapshot_agree_without_mutating(self):
        from region_production import produce_corporation
        from random_cache import rand
        r, firm, worker, *_ = firm_fixture()
        before = pickle.dumps((firm, worker, rand))
        state = capture_planning_state(firm, r, 1)
        self.assertEqual(before, pickle.dumps((firm, worker, rand)))
        self.assertEqual(state.slots, 1)
        self.assertGreaterEqual(state.output_per_slot, 1)
        firm.inv_set(Goods.wood, 2)
        predicted = finish_turn(replace(state, inputs=2, phase='inputs'))
        produce_corporation(r, firm, r.recipes[Goods.furniture], Goods.furniture,
                            {Goods.furniture: 1}, defaultdict(float), turn=1)
        self.assertEqual(predicted.outputs, firm.inv_get(Goods.furniture))
        self.assertEqual(predicted.inputs, firm.inv_get(Goods.wood))

    def test_chain_cannot_sell_new_output_in_earlier_market(self):
        state = purchase(snapshot(supply=2), 2)
        self.assertEqual((state.cash, state.inputs, state.outputs), (14, 2, 0))
        produced = finish_turn(state)
        self.assertEqual((produced.cash, produced.inputs, produced.outputs), (10, 0, 1))
        sold = purchase(produced, 0)
        self.assertEqual((sold.cash, sold.outputs), (25, 0))
        self.assertEqual(score_terminal(sold), 25)
        self.assertIsNone(purchase(snapshot(cash=9), 2))
        self.assertIsNone(finish_turn(replace(state, cash=3)))

    def test_no_demand_does_not_create_sale_and_fractional_expectation_is_not_cash(self):
        state = finish_turn(purchase(snapshot(demand=0, chance=.5), 2))
        self.assertEqual(state.cash, 10)
        self.assertEqual(state.outputs, .5)
        self.assertEqual(purchase(state, 0).cash, 10)

    def test_baseline_includes_normal_production_and_does_not_spend_payroll_twice(self):
        self.assertIsNone(baseline(snapshot(), 1))  # Ordinary eight-unit buffer exhausts cash.
        state = snapshot(cash=100, supply=2)
        ordinary = baseline(state, 1)
        planned = finish_turn(purchase(state, 2))
        self.assertEqual(ordinary, planned)
        self.assertEqual(score_terminal(ordinary), 105)
        self.assertEqual(score_terminal(replace(ordinary, liabilities=7)), 98)

    def test_new_input_cannot_spend_later_output_auction_receipts(self):
        self.assertIsNone(purchase(snapshot(cash=4, outputs=1), 2))

    def test_recurring_demand_keeps_one_shared_buyer_cash_budget(self):
        state = snapshot(outputs=2, slots=0, demand_per_turn=1, buyer_budget=15)
        sold = purchase(state, 0)
        self.assertEqual((sold.cash, sold.buyer_budget), (35, 0))
        next_turn = finish_turn(sold)
        self.assertEqual(next_turn.demand, 0)
        self.assertEqual(purchase(next_turn, 0).cash, 31)

    def test_funded_recurring_demand_returns_next_turn(self):
        state = snapshot(outputs=1, demand_per_turn=1, buyer_budget=45)
        next_turn = finish_turn(purchase(state, 0))
        self.assertEqual((next_turn.demand, next_turn.buyer_budget), (1, 30))

    def test_future_obligation_remains_reserved_without_early_payment(self):
        state = snapshot(cash=30, liabilities=7, due_schedule=((2, 7),))
        next_turn = finish_turn(purchase(state, 2))
        self.assertEqual((next_turn.cash, next_turn.liabilities), (20, 7))
        next_turn = finish_turn(purchase(next_turn, 0))
        self.assertEqual(next_turn.liabilities, 7)
        due_turn = finish_turn(purchase(next_turn, 0))
        self.assertEqual(due_turn.liabilities, 0)

    def test_unrelated_crops_do_not_disable_nonfood_firm_projection(self):
        r, firm, *_ = firm_fixture()
        r.farms = {'unrelated': {'operator_id': -1, 'employer_id': -1}}
        self.assertEqual(capture_planning_state(firm, r, 1).slots, 1)
        r.farms['unrelated']['employer_id'] = firm.id
        with self.assertRaisesRegex(ValueError, 'crop_work'):
            capture_planning_state(firm, r, 1)

    def test_standard_production_uses_existing_abundance_proficiency(self):
        r, firm, worker, *_ = firm_fixture()
        ordinary = capture_planning_state(firm, r, 1)
        r._gameplay_flags = replace(r._gameplay_flags, abundance=True)
        r.recipes[firm.output].pop('setup_good', None)
        worker.productive_practice = {'furniture':30}
        self.assertGreater(capture_planning_state(firm, r, 1).output_per_slot, ordinary.output_per_slot)

    def test_pending_crop_delivery_is_not_treated_as_spot_inventory(self):
        r, firm, *_ = firm_fixture()
        r.offtake_contracts = [{'lender_id': firm.id, 'status':'active', 'remaining':2}]
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            capture_planning_state(firm, r, 1)
        self.assertEqual(firm.inv_get(Goods.wood), 0)
