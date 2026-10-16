"""Causal trace contract and live mutation probes."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from goods import Goods
from region_market import update_price_ref, price_decay
from run_trace import RunTrace, verify
from price_trace import replay_event
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
            self.assertTrue(replay_event(row)['matches'])
            self.assertEqual(terms['recent_sample_mean'], 2.3)
            self.assertEqual(row['sequence'], 1)
            self.assertIn('prior_reference', render(row))
            self.assertEqual(len(report(trace.path, turn=7, entity='tile:Delta',
                                        metric='goods.price')), 1)
            self.assertEqual(len(report(trace.path, turn=7, entity='tile:Delta',
                                        metric='goods.price', good='wood')), 0)

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

    def test_price_bridge_tracks_order_and_exposes_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'bridge.jsonl', 'bridge')
            clock = {'next': 1, 'turn': 1, 'phase': 'local'}
            subject = {'type': 'tile', 'id': 'Delta', 'good': 'food'}
            trace.emit(clock, kind='market_price_update', record_class='calculation',
                       subject=subject, metric_id='goods.price', before=2, after=3)
            trace.emit(clock, kind='market_price_decay', record_class='calculation',
                       subject=subject, metric_id='goods.price', before=3, after=2.5)
            trace.price_bridge(clock, subject=subject, before=2, after=2.5,
                               unit='local_currency_per_unit')
            bridge = trace.query(subject=subject, metric_id='goods.price')['events'][-1]
            self.assertEqual([step['difference'] for step in bridge['inputs']['steps']],
                             [1, -0.5])
            self.assertEqual(bridge['explanation_status'], 'ordered_writes_reconciled')
            trace.price_bridge(clock, subject=subject, before=1, after=2.5,
                               unit='local_currency_per_unit')
            gap = trace.query(subject=subject, metric_id='goods.price')['events'][-1]
            self.assertEqual(gap['explanation_status'], 'mutation_chain_incomplete')

    def test_no_order_decay_and_furniture_input_floor_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'floors.jsonl', 'floors')
            clock = {'next': 1, 'turn': 2, 'phase': 'local'}
            recipes = {Goods.food: {'price': 3.0, 'maxinv': 10},
                       Goods.furniture: {'price': 1.0, 'maxinv': 10,
                                         'input': Goods.food, 'numInput': 2,
                                         'production': 1}}
            producer = SimpleNamespace(output=Goods.furniture, is_trader=False,
                                       inv_get=lambda _good, _fallback: 10.0)
            region = SimpleNamespace(name='Delta', recipes=recipes,
                                     _price_ref={Goods.food: 3.0,
                                                 Goods.furniture: 1.0},
                                     _trade_prices={}, agents=[producer],
                                     _collective_trace_clock=clock, _run_trace=trace,
                                     home_currency='D')
            price_decay(region, Goods.food)
            self.assertAlmostEqual(recipes[Goods.food]['price'], 2.85)
            update_price_ref(region, Goods.furniture, 0.1,
                             local_asks=10, imported_asks=0, bids=1)
            self.assertAlmostEqual(recipes[Goods.furniture]['price'], 5.7)
            rows = trace.query(metric_id='goods.price')['events']
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(replay_event(row)['matches'] for row in rows))
            self.assertAlmostEqual(rows[1]['constraints']['active_floor'], 5.7)

    def test_food_rise_and_fall_replay_on_separate_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'food.jsonl', 'food')
            clock = {'next': 1, 'turn': 1, 'phase': 'local'}
            producer = SimpleNamespace(output=Goods.food, is_trader=False,
                                       inv_get=lambda _good, _fallback: 10.0)
            region = SimpleNamespace(name='Delta', recipes={Goods.food: {
                'price': 2.0, 'maxinv': 10}}, _price_ref={Goods.food: 2.0},
                _trade_prices={}, agents=[producer], _collective_trace_clock=clock,
                _run_trace=trace, home_currency='D')
            update_price_ref(region, Goods.food, 5.0,
                             local_asks=1, imported_asks=0, bids=5)
            rise = trace.query(turn=1, metric_id='goods.price')['events'][0]
            self.assertGreater(rise['value_after'], rise['value_before'])
            self.assertTrue(replay_event(rise)['matches'])
            clock['turn'] = 2
            update_price_ref(region, Goods.food, 0.0,
                             local_asks=1, imported_asks=0, bids=0)
            fall = trace.query(turn=2, metric_id='goods.price')['events'][0]
            self.assertLess(fall['value_after'], fall['value_before'])
            self.assertTrue(replay_event(fall)['matches'])

    def test_cloth_quote_change_is_queryable_at_each_turn(self):
        from labor_frontier_market import _cloth_ask
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'cloth.jsonl', 'cloth')
            clock = {'next': 1, 'turn': 1, 'phase': 'scenario_market'}
            region = SimpleNamespace(name='Mill', recipes={
                Goods.cloth: {'production': 3}, Goods.cotton: {'price': 3.0}},
                neighbors={}, home_currency='D', _collective_trace_clock=clock,
                _run_trace=trace)
            firm = SimpleNamespace(id='mill-1', wage=2.0, machinery_level=1,
                                   broken_machinery=0,
                                   cost_get=lambda _good, _fallback: 3.0)
            first = _cloth_ask(region, firm)
            clock['turn'] = 2
            firm.wage = 4.0
            second = _cloth_ask(region, firm)
            self.assertGreater(second, first)
            old_row = trace.query(turn=1, subject={'type': 'tile', 'id': 'Mill',
                                                    'good': 'cloth'},
                                  metric_id='goods.seller_ask')['events'][0]
            new_row = trace.query(turn=2, subject={'type': 'tile', 'id': 'Mill',
                                                    'good': 'cloth'},
                                  metric_id='goods.seller_ask')['events'][0]
            self.assertEqual((old_row['value_after'], new_row['value_after']),
                             (first, second))
            self.assertTrue(replay_event(old_row)['matches'])
            self.assertTrue(replay_event(new_row)['matches'])

    def test_dynamic_price_snapshot_and_read_only_death_sample(self):
        from trace_snapshots import sample
        tile = SimpleNamespace(name='Delta', recipes={Goods.cotton: {'price': 3.0}},
                               total_population=[4], deaths_this_turn=2,
                               deaths_by_cause_this_turn={'disease': 2},
                               protest_energy_log=[], unrest_log=[], agents=[],
                               construction_projects=[], cost_of_living=1.0)
        first = sample([tile], [])
        second = sample([tile], [])
        self.assertEqual(first, second)
        self.assertEqual(first[('goods.price', 'Delta', 'cotton')][2], 3.0)
        self.assertEqual(tile.deaths_this_turn, 2)

    def test_scenario_quote_replays_and_paid_price_is_separate(self):
        from sim_server.sim_server import SimServer
        server = SimServer(seed=613, terrain_seed=613, nation_seed=613,
                           scenario_id='labor_frontier_rivalry')
        server.step()
        asks = server.run_trace.query(turn=1, metric_id='goods.seller_ask',
                                      limit=10000)['events']
        self.assertTrue(any(row['subject']['good'] == 'cloth' for row in asks))
        self.assertTrue(any(row['subject']['good'] == 'cotton' for row in asks))
        self.assertTrue(all(replay_event(row)['matches'] for row in asks))
        delivered = server.run_trace.query(turn=1, metric_id='goods.delivered_quote',
                                           limit=10000)['events']
        self.assertTrue(all(replay_event(row)['matches'] for row in delivered))
        paid = server.run_trace.query(turn=1, metric_id='goods.transaction_price',
                                      limit=10000)['events']
        self.assertTrue(paid)
        self.assertTrue(all(row['value_after'] > 0 for row in paid))

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
        rows = server.run_trace.query(turn=1, limit=10000)['events']
        kinds = {row['kind'] for row in rows}
        self.assertIn('market_price_update', kinds)
        self.assertIn('unrest_roll', kinds)
        self.assertTrue(all(row['turn'] == 1 for row in rows))
        for _ in range(4):
            server.step()
        self.assertEqual(server.turn, 5)
        self.assertTrue(server.run_trace.query(turn=5, metric_id='goods.price')['events'])
        self.assertEqual(verify(server.run_trace.path)['checkpoints'], 5)
        price_rows = server.run_trace.query(metric_id='goods.price', limit=10000)['events']
        replayed = [replay_event(row) for row in price_rows]
        self.assertTrue(all(result['matches'] for result in replayed if result))
        self.assertTrue(any(row['kind'] == 'price_bridge' for row in price_rows))
        for metric in ('goods.seller_ask', 'goods.delivered_quote'):
            quotes = server.run_trace.query(metric_id=metric, limit=10000)['events']
            self.assertTrue(all(replay_event(row)['matches'] for row in quotes
                                if replay_event(row)))


if __name__ == '__main__':
    unittest.main()
