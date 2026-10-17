"""Causal trace contract and live mutation probes."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from goods import Goods
from region_market import update_price_ref, price_decay
from run_trace import RunTrace, verify
from price_trace import replay_event
from trace_report import report, render, diff_snapshots


class RunTraceTests(unittest.TestCase):
    def test_starvation_death_uses_region_trace_and_snapshot_counter(self):
        from demographics_estate import handle_death

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'deaths.ctr', 'deaths')
            clock = {'next': 1, 'turn': 7, 'phase': 'local'}
            region = SimpleNamespace(name='Delta', deaths_this_turn=0,
                                     deaths_by_cause_this_turn={},
                                     _collective_trace_clock=clock, _run_trace=trace)
            context = SimpleNamespace(source_region=region)
            person = Agent(0)
            initialize_agent(person, Goods.food, 0, 0, 0)
            person.calorie_deficit_kcal = 2000.0
            person.energy_reserve_kcal = 0.0
            with ExitStack() as patches:
                patches.enter_context(patch('demographics_estate.rand.random', return_value=0.0))
                for helper in ('cleanup_dead_agent_links', 'handle_company_inheritance',
                               'reclaim_dead_route_cargo', 'escheat_dead_parked_goods',
                               'handle_debt_inheritance', 'handle_wealth_inheritance',
                               'zero_out_dead_agent'):
                    patches.enter_context(patch(f'demographics_estate.{helper}'))
                patches.enter_context(patch('demographics_estate.living_descendants_recursive',
                                            return_value=[]))
                self.assertTrue(handle_death(context, 7, person, [person]))

            self.assertEqual(region.deaths_this_turn, 1)
            self.assertEqual(region.deaths_by_cause_this_turn, {'starvation': 1})
            rows = trace.query(turn=7)['events']
            self.assertEqual([row['kind'] for row in rows],
                             ['starvation_death_assessment', 'person_died'])
            self.assertEqual(rows[0]['subject']['id'], 'Delta')
            self.assertEqual(rows[1]['inputs']['tile'], 'Delta')
            self.assertEqual(rows[1]['inputs']['death_cause'], 'starvation')

    def test_price_formula_replays_from_recorded_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'run.ctr', 'fixture', seed=1)
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
            self.assertTrue(row['formula_replay']['matches'])
            self.assertEqual(terms['recent_sample_mean'], 2.3)
            self.assertEqual(row['sequence'], 1)
            self.assertIn('prior_reference', render(row))
            self.assertEqual(len(report(trace.path, turn=7, entity='tile:Delta',
                                        metric='goods.price')), 1)
            self.assertEqual(len(report(trace.path, turn=7, entity='tile:Delta',
                                        metric='goods.price', good='wood')), 0)

    def test_pagination_and_typed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'run.ctr', 'fixture')
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
            trace = RunTrace(Path(tmp) / 'bridge.ctr', 'bridge')
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

    def test_formula_mismatch_cannot_receive_exact_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'mismatch.ctr', 'mismatch')
            clock = {'next': 1, 'turn': 1, 'phase': 'local'}
            subject = {'type': 'tile', 'id': 'Delta', 'good': 'food'}
            trace.emit(clock, kind='market_price_decay', record_class='calculation',
                       subject=subject, metric_id='goods.price', before=2, after=9,
                       formula_id='market.decay.v1',
                       inputs={'prior_display_price': 2, 'input_cost_floor': 1,
                               'input_quantity': 0, 'production_quantity': 0})
            row = trace.query(metric_id='goods.price')['events'][0]
            self.assertFalse(row['formula_replay']['matches'])
            self.assertEqual(row['confidence'], 'unknown')
            trace.price_bridge(clock, subject=subject, before=2, after=9,
                               unit='local_currency_per_unit')
            bridge = trace.query(metric_id='goods.price')['events'][-1]
            self.assertEqual(bridge['explanation_status'], 'mutation_chain_incomplete')

    def test_no_order_decay_and_furniture_input_floor_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'floors.ctr', 'floors')
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
            self.assertTrue(all(row['formula_replay']['matches'] for row in rows))
            self.assertAlmostEqual(rows[1]['constraints']['active_floor'], 5.7)

    def test_food_rise_and_fall_replay_on_separate_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'food.ctr', 'food')
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
            trace = RunTrace(Path(tmp) / 'cloth.ctr', 'cloth')
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
            trace = RunTrace(Path(tmp) / 'run.ctr', 'fx-fixture')
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

    def test_career_switch_emits_typed_trace_event(self):
        import agent as agent_mod
        from labor_choice import apply_career_switch
        saved_id = agent_mod._agentid_counter[0]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                trace = RunTrace(Path(tmp) / 'career.ctr', 'career-fixture')
                clock = {'next': 1, 'turn': 12, 'phase': 'local'}
                region = SimpleNamespace(name='Delta', _collective_trace_clock=clock,
                                         _run_trace=trace)
                worker = Agent(42)
                initialize_agent(worker, Goods.food, 0, 0, 0)
                worker.birth_round = -10
                worker.last_career_switch = 4
                switched = apply_career_switch(
                    region, worker, Goods.wood, 12,
                    reason='INDEPENDENT_SWITCH',
                    formula_id='labor.career_switch.v2',
                    inputs={'current_income': 1.2, 'target_income': 2.5},
                    constraints={'min_cooldown_turns': 4},
                )
                self.assertTrue(switched)
                self.assertEqual(worker.output, Goods.wood)
                self.assertEqual(worker.last_career_switch, 12)
                self.assertEqual(worker.mem_last('mem_career_history'), 'food')
                rows = trace.query(turn=12, metric_id='labor.career_choice')['events']
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row['value_before'], 'food')
                self.assertEqual(row['value_after'], 'wood')
                self.assertEqual(row['inputs']['prior_tenure'], 8)
                self.assertEqual(row['inputs']['age'], 22)
                self.assertAlmostEqual(row['inputs']['age_mobility_factor'], 1.35)
                self.assertEqual(row['inputs']['reason'], 'INDEPENDENT_SWITCH')
                self.assertEqual(row['constraints']['min_cooldown_turns'], 4)
        finally:
            agent_mod._agentid_counter[0] = saved_id

    def test_lifecycle_age_curve_and_childhood_lock(self):
        import agent as agent_mod
        from labor_choice import (
            career_lifecycle_age,
            career_mobility_age_factor,
            career_switch_hurdle_and_cooldown,
        )
        saved_id = agent_mod._agentid_counter[0]
        try:
            child = Agent(5)
            initialize_agent(child, Goods.food, 0, 0, 0)
            child.last_career_switch = 5
            self.assertEqual(career_lifecycle_age(child, 12), 7)
            self.assertEqual(career_mobility_age_factor(child, 12), 0.0)
            hurdle_child, cooldown_child, _ = career_switch_hurdle_and_cooldown(child, 12)
            self.assertEqual(hurdle_child, float('inf'))
            self.assertEqual(cooldown_child, 7)

            # At age 15 (turn 20), child enters youth exploration window with zero initial cooldown
            hurdle_youth, cooldown_youth, factor_youth = career_switch_hurdle_and_cooldown(child, 20)
            self.assertAlmostEqual(factor_youth, 1.35)
            self.assertEqual(cooldown_youth, 0)

            # Senior founder (founding_age_offset=56) has much higher hurdle and cooldown than youth
            senior = Agent(0)
            initialize_agent(senior, Goods.wood, 0, 0, 0)
            senior.founding_age_offset = 56
            hurdle_senior, cooldown_senior, factor_senior = career_switch_hurdle_and_cooldown(senior, 4)
            self.assertAlmostEqual(factor_senior, 0.12)
            self.assertGreater(hurdle_senior, hurdle_youth * 1.8)
            self.assertEqual(cooldown_senior, 10)
        finally:
            agent_mod._agentid_counter[0] = saved_id

    def test_occupational_tenure_and_skill_tier_gating(self):
        import agent as agent_mod
        from labor_choice import (
            occupational_tenure_multiplier,
            can_enter_independent_trade,
        )
        saved_id = agent_mod._agentid_counter[0]
        try:
            worker = Agent(0)
            initialize_agent(worker, Goods.food, 0, 0, 2)
            worker.last_career_switch = 0
            worker.productivity = 0.45
            # 10 turns of continuous tenure in food gives +20% (1.20x), while unfamiliar wood is 1.00x
            self.assertAlmostEqual(occupational_tenure_multiplier(worker, Goods.food, 10), 1.20)
            self.assertAlmostEqual(occupational_tenure_multiplier(worker, Goods.wood, 10), 1.00)

            # Without capital/tools or prior joinery experience, Tier 2 furniture entry is gated
            allowed, reason = can_enter_independent_trade(worker, Goods.furniture, input_cost=2.0, turn=10)
            self.assertFalse(allowed)
            self.assertEqual(reason, 'artisan tool/skill barrier')

            # Prior experience in mem_career_history unlocks Tier 2 craft re-entry and retains partial tenure
            worker.mem_push('mem_career_history', 'furniture')
            allowed2, reason2 = can_enter_independent_trade(worker, Goods.furniture, input_cost=2.0, turn=10)
            self.assertTrue(allowed2)
            self.assertEqual(reason2, 'prior_craft_experience')
            self.assertAlmostEqual(occupational_tenure_multiplier(worker, Goods.furniture, 10), 1.04)
        finally:
            agent_mod._agentid_counter[0] = saved_id

    def test_emergency_fast_path_directionality_and_congestion_cap(self):
        import agent as agent_mod
        from economy.labor_mobility import LaborMobilityScheduler
        saved_id = agent_mod._agentid_counter[0]
        try:
            scheduler = LaborMobilityScheduler(base_batch_size=10)
            hungry_farmer = Agent(0)
            initialize_agent(hungry_farmer, Goods.food, 0, 0, 20)
            hungry_farmer.hungry_steps = 2
            hungry_farmer.assigned_plot_id = 'plot-1'
            hungry_farmer.social_class = 'serf'

            hungry_woodcutter = Agent(0)
            initialize_agent(hungry_woodcutter, Goods.wood, 0, 0, 20)
            hungry_woodcutter.hungry_steps = 2
            hungry_woodcutter.assigned_plot_id = 'plot-1'
            hungry_woodcutter.social_class = 'serf'

            region = SimpleNamespace(
                name='Parish',
                agents=[hungry_farmer, hungry_woodcutter],
                buildings=[],
                terrain={Goods.food: 1.0, Goods.wood: 1.0},
                recipes={
                    Goods.food: {'production': 6, 'price': 2.0, 'numInput': 0, 'maxinv': 10},
                    Goods.wood: {'production': 6, 'price': 15.0, 'numInput': 0, 'maxinv': 10},
                },
                sold_log={Goods.food: [10, 10, 10], Goods.wood: [20, 20, 20]},
                labor_scheduler_last_turn=-1,
            )
            scheduler.step_labor_cohort(region, t=5)
            # Hungry farmer must not switch out of food into wood despite high wood price
            self.assertEqual(hungry_farmer.output, Goods.food)
        finally:
            agent_mod._agentid_counter[0] = saved_id


if __name__ == '__main__':
    unittest.main()

