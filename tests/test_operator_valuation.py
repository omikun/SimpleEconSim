"""Operator explanations use the same economic arithmetic as return estimates."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from goods import Goods
from economy.operator_valuation import generic_return, return_basis
from economy.transformation_graph import TransformationGraph, TransformationOperator


class OperatorValuationTests(unittest.TestCase):
    def test_funded_demand_and_prestige_explanations_replay_the_actual_return(self):
        actor = SimpleNamespace()
        region = SimpleNamespace(name='Valuation', agents=[], recipes={
            Goods.wood: {'price': 3.0}, Goods.fine_textiles: {'price': 50.0}})
        op = TransformationOperator('valued', 'Valued', 'artisan',
                                    input_goods={Goods.wood: 2.0},
                                    output_goods={Goods.fine_textiles: 10.0}, cash_cost=4.0)
        for commercial in (True, False):
            with self.subTest(commercial=commercial), \
                    patch('abundance.enabled', return_value=commercial), \
                    patch('abundance.funded_demand', return_value=.25):
                value = op.estimate_net_return(actor, region, 1.5)
                basis = return_basis(op, actor, region, 1.5)
                replay = (sum(row['value_contribution'] for row in basis['outputs'])
                          - basis['cash_cost_contribution']
                          - sum(row['cost_contribution'] for row in basis['inputs']))
                self.assertEqual(value, replay)
                self.assertEqual(basis['outputs'][0]['quantity'], .25 if commercial else 10.0)
                self.assertEqual(basis['outputs'][0]['value_basis'],
                                 'expected_price_times_shadow_cash' if commercial else 'prestige')
                self.assertEqual(generic_return(op, actor, region, 1.5), (value, basis))

    def test_registered_native_hooks_share_their_explanation_provider(self):
        actor = SimpleNamespace(frontier_estates=[{'primary_commodity': 'cotton', 'captive_labor': 5}])
        region = SimpleNamespace(agents=[], recipes={Goods.cotton: {'price': 4.0}})
        for op_id in ('construct_machinery', 'maintain_repair_machinery',
                      'chartered_frontier_conquest', 'procure_captive_labor',
                      'mandate_plantation_labor_gang'):
            with self.subTest(operator=op_id):
                op = TransformationGraph.get_operator(op_id)
                value, basis = op.estimate_return_hook.evaluation(actor, region, 1.25)
                self.assertEqual(op.estimate_net_return(actor, region, 1.25), value)
                self.assertEqual(return_basis(op, actor, region, 1.25), basis)
                self.assertIn('formula', basis)

    def test_custom_hook_replacement_does_not_keep_a_stale_native_explanation(self):
        from unittest.mock import patch
        op = TransformationGraph.get_operator('construct_machinery')
        actor, region = SimpleNamespace(), SimpleNamespace()
        with patch.object(op, 'estimate_return_hook', lambda *_: 123.0):
            self.assertEqual(op.estimate_net_return(actor, region, 1.0), 123.0)
            basis = return_basis(op, actor, region, 1.0)
            self.assertEqual(basis['formula'], 'specialized operator return hook')
            self.assertNotIn('fixed_return', basis)

    def test_native_operator_callbacks_and_valuations_survive_a_fresh_process(self):
        import io
        import json
        import os
        from pathlib import Path
        import subprocess
        import sys
        from simulation_checkpoint import CheckpointPickler
        buffer = io.BytesIO()
        CheckpointPickler(buffer).dump(TransformationGraph._operators)
        script = '''import json,pickle,sys
from types import SimpleNamespace
from goods import Goods
from economy.transformation_graph import TransformationGraph
from economy.operator_valuation import return_basis
operators=pickle.loads(sys.stdin.buffer.read())
actor=SimpleNamespace(frontier_estates=[{'primary_commodity':'cotton','captive_labor':5}])
region=SimpleNamespace(agents=[],recipes={Goods.cotton:{'price':4.0}})
rows={name:(operators[name].estimate_net_return(actor,region,1.25),return_basis(operators[name],actor,region,1.25)) for name in ('construct_machinery','maintain_repair_machinery','chartered_frontier_conquest','procure_captive_labor','mandate_plantation_labor_gang')}
print(json.dumps(rows,sort_keys=True))
'''
        completed = subprocess.run([sys.executable, '-c', script], input=buffer.getvalue(),
                                   capture_output=True, check=True,
                                   env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1])))
        rows = json.loads(completed.stdout)
        actor = SimpleNamespace(frontier_estates=[{'primary_commodity': 'cotton', 'captive_labor': 5}])
        region = SimpleNamespace(agents=[], recipes={Goods.cotton: {'price': 4.0}})
        for name, (value, basis) in rows.items():
            op = TransformationGraph.get_operator(name)
            self.assertEqual(value, op.estimate_net_return(actor, region, 1.25))
            self.assertEqual(basis, return_basis(op, actor, region, 1.25))

    def test_sector_ranking_is_trace_neutral_with_fractional_supplier_stocks(self):
        from economy.elite_investment import scan_sectors
        from tests.test_elite_planning_gate_trace import Actor
        suppliers = [Actor(i, lord=False, inventory={Goods.wood: units})
                     for i, units in enumerate((.1, .2, .3), start=1)]
        for supplier in suppliers:
            supplier.output = Goods.wood
        region = SimpleNamespace(agents=suppliers, recipes={
            Goods.wood: {'price': 2.0, 'production': 1.0, 'numInput': 0},
            Goods.furniture: {'price': 20.0, 'production': 1.0,
                              'input': Goods.wood, 'numInput': 3.6}})
        with patch('abundance.enabled', return_value=False):
            plain = scan_sectors(region, False)
            traced = scan_sectors(region, True)
        self.assertEqual(plain[:2], traced[:2])
        self.assertEqual(traced[0], Goods.furniture)
