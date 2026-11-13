import unittest
from types import SimpleNamespace
from goods import Goods
from economy.transformation_graph import TransformationOperator
from economy.inventory_transform import execute_inventory_transform
from tests.test_elite_cash_accounting import person
from region import Region
from economy.actor_accounts import begin_turn, seal_turn


class InventoryTransformTests(unittest.TestCase):
    def test_consumption_aliases_yield_and_paired_fee(self):
        r = Region('Transform', 0, number_of_agents=0)
        a = person(Goods.wood, 20)
        r.agents = [a, r.gov.agent]
        a.inv_set(Goods.wood, 2.5)
        a.unclaimed_production = {'wood': 2.5}
        op = TransformationOperator('test', 'Test', 'artisan',
            input_goods={Goods.wood: 1.5, 'wood': 1}, output_goods={'furniture': 1.9}, cash_cost=3)
        begin_turn(r, 1)
        self.assertTrue(execute_inventory_transform(op, a, r, 1)['success'])
        self.assertEqual((a.inv_get(Goods.wood), a.inv_get(Goods.furniture), a.cash), (0, 1, 17))
        self.assertEqual(a.unclaimed_production['wood'], 0)
        self.assertFalse(execute_inventory_transform(op, a, r, 1)['success'])
        self.assertEqual(a.cash, 17)
        self.assertTrue(all(row['unposted_cash_change'] == 0 for row in seal_turn(r, 1)))

    def test_rejection_is_atomic_and_custom_inputs_are_consumed(self):
        r = Region('Transform', 0, number_of_agents=0)
        a = person(Goods.wood, 20)
        a.inv_set('custom', 1.25)
        op = TransformationOperator('test', 'Test', 'artisan', input_goods={'custom': 1.25},
                                    output_goods={Goods.wood: 2}, cash_cost=3)
        for failure in ('recipient', 'stock', 'cash', 'precision', 'nan'):
            with self.subTest(failure=failure):
                r.gov = None if failure == 'recipient' else SimpleNamespace(agent=person(Goods.food, 0))
                a.cash = 0 if failure == 'cash' else 20
                op.input_goods = {'missing': 1} if failure == 'stock' else {'custom': 1.25}
                if failure == 'precision': op.input_goods = {Goods.food: .0001}
                if failure == 'nan': op.output_goods = {Goods.wood: float('nan')}
                before = (a.cash, list(a.inventory), dict(a.custom_inventory or {}))
                self.assertFalse(execute_inventory_transform(op, a, r, 1)['success'])
                self.assertEqual(before, (a.cash, list(a.inventory), dict(a.custom_inventory or {})))
        op.input_goods, op.output_goods = {'custom': 1.25}, {Goods.wood: 2}
        self.assertTrue(execute_inventory_transform(op, a, r, 1)['success'])
        self.assertEqual(a.inv_get('custom'), 0)

    def test_self_loop_cannot_borrow_its_own_output(self):
        r = Region('Transform', 0, number_of_agents=0)
        a = person(Goods.wood, 20)
        a.inv_set(Goods.wood, 0)
        op = TransformationOperator('loop', 'Loop', 'artisan',
                                    input_goods={Goods.wood: 1}, output_goods={Goods.wood: 1})
        self.assertFalse(execute_inventory_transform(op, a, r, 1)['success'])
        a.inv_set(Goods.wood, 1)
        for _ in range(3): self.assertTrue(execute_inventory_transform(op, a, r, 1)['success'])
        self.assertEqual(a.inv_get(Goods.wood), 1)
