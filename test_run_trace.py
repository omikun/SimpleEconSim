"""Causal trace contract and live mutation probes."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from goods import Goods
from region_market import update_price_ref
from run_trace import RunTrace, verify
from trace_report import report, render, diff_snapshots


class RunTraceTests(unittest.TestCase):
    def test_price_formula_replays_from_recorded_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'run.jsonl', 'fixture', seed=1)
            clock = {'next': 1, 'turn': 7, 'phase': 'local'}
            producer = SimpleNamespace(output=Goods.food, is_trader=False,
                                       inv_get=lambda _good, _fallback: 2.0)
            region = SimpleNamespace(name='Delta', _price_ref={Goods.food: 2.0},
                                     _trade_prices={Goods.food: [2.2, 2.4]},
                                     agents=[producer], recipes={Goods.food: {'maxinv': 10, 'price': 2.0}},
                                     _collective_trace_clock=clock, _run_trace=trace)
            update_price_ref(region, Goods.food, 1.5,
                             local_asks=8, imported_asks=2, bids=15)
            rows = trace.query(turn=7, subject={'type': 'tile', 'id': 'Delta'},
                               metric_id='goods.price')['events']
            self.assertEqual(len(rows), 1)
            row = rows[0]
            terms = row['inputs']
            self.assertEqual((terms['local_asks'], terms['imported_asks'], terms['bids']),
                             (8, 2, 15))
            expected = min(50.0, max(0.1, terms['input_cost_floor'], terms['after_vwap']))
            self.assertAlmostEqual(row['value_after'], expected)
            self.assertAlmostEqual(region._price_ref[Goods.food], expected)
            self.assertEqual(row['sequence'], 1)
            self.assertIn('prior_reference', render(row))
            self.assertEqual(len(report(trace.path, turn=7, entity='tile:Delta',
                                        metric='goods.price')), 1)

    def test_pagination_and_typed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'run.jsonl', 'fixture')
            clock = {'next': 1, 'turn': 1, 'phase': 'test'}
            for value in range(3):
                trace.emit(clock, kind='snapshot', subject={'type': 'tile', 'id': 'A'},
                           metric_id='people.population', after=value)
            page = trace.query(metric_id='people.population', offset=1, limit=1)
            self.assertEqual(page['total'], 3)
            self.assertEqual(page['events'][0]['value_after'], 1)
            self.assertEqual(page['events'][0]['event_id'], 'fixture:2')
            trace.emit(clock, kind='tax', record_class='transfer',
                       subject={'type': 'nation', 'id': 'A'},
                       metric_id='finance.treasury_flow', after=5.0)
            self.assertEqual(trace._treasury_flows['A'][0]['amount'], 5.0)
            trace.checkpoint(clock)
            self.assertEqual(verify(trace.path)['checkpoints'], 1)
            left = [{'kind': 'metric_snapshot', 'turn': 1,
                     'subject': {'type': 'tile', 'id': 'A'},
                     'metric_id': 'goods.price', 'value_after': 2.0}]
            right = [{**left[0], 'value_after': 2.5}]
            self.assertEqual(diff_snapshots(left, right)[0]['difference'], 0.5)

    def test_fx_formula_records_reserves_and_ppp(self):
        from forex import ForexDesk
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'run.jsonl', 'fx-fixture')
            clock = {'next': 1, 'turn': 4, 'phase': 'forex'}
            region = SimpleNamespace(name='Delta', _collective_trace_clock=clock,
                                     _run_trace=trace)
            bank = SimpleNamespace(total_deposits=100.0, fx_pool=20.0,
                                   foreign_reserves={'B': 10.0})
            desk = ForexDesk('A', 'B', bank=bank, seed_reserves=False,
                             target_reserves=20.0)
            desk.update(4, bank=bank, ppp_target=1.1, trace_region=region)
            row = trace.query(metric_id='fx.bilateral_mid')['events'][0]
            self.assertEqual(row['inputs']['reserve_ratio'], 0.5)
            self.assertEqual(row['turn'], 4)
            self.assertAlmostEqual(row['value_after'], desk.mid)

    def test_live_server_records_price_and_unrest(self):
        from sim_server.sim_server import SimServer
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           scenario_id='labor_frontier_rivalry')
        from metric_catalog import inventory_region_histories
        inventory = {row['field']: row for row in inventory_region_histories(server.tiles[0])}
        self.assertEqual(inventory['gdp_log']['coverage'], 'instrumented')
        self.assertEqual(inventory['bank_cash_log']['coverage'], 'untraced')
        server.step()
        rows = server.run_trace.query(turn=1, limit=200)['events']
        kinds = {row['kind'] for row in rows}
        self.assertIn('market_price_update', kinds)
        self.assertIn('unrest_roll', kinds)
        self.assertTrue(all(row['turn'] == 1 for row in rows))
        for _ in range(4):
            server.step()
        self.assertEqual(server.turn, 5)
        self.assertTrue(server.run_trace.query(turn=5, metric_id='goods.price')['events'])
        self.assertEqual(verify(server.run_trace.path)['checkpoints'], 5)


if __name__ == '__main__':
    unittest.main()
