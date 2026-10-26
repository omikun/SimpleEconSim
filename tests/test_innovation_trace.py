"""Innovation evidence follows actual learning, research and diffusion decisions."""

from copy import deepcopy
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from goods import Goods
import innovation
from innovation import InnovationSystem, RoyalBounty, TechDomain, Technology
from innovation_trace import record_pressure
from run_trace import RunTrace


def _nation(name='Alpha', *, trace=None, clock=None):
    agents = [SimpleNamespace(id=index, wage=3.0, hungry_steps=1, cash=10.0)
              for index in range(12)]
    tile = SimpleNamespace(
        name=f'{name}-Delta', agents=agents,
        recipes={Goods.food: {'price': 2.5}},
        production_log={Goods.food: [200], Goods.wood: [50], Goods.furniture: [20]},
        export_vol={Goods.food: [10], Goods.wood: [5]},
        export_val={Goods.food: [0.0], Goods.wood: [0.0]},
        gov=SimpleNamespace(), military_units=[SimpleNamespace(id=1, strength=1),
                                             SimpleNamespace(id=2, strength=500)],
        elevation=0.6, all_adjacent_names=[])
    nation = SimpleNamespace(name=name, tiles=[tile], provinces=[1, 2], currency='D')
    tile.owner_nation = nation
    if trace is not None:
        tile._run_trace = trace
        tile._collective_trace_clock = clock
    return nation


def _state(system, nations):
    return (deepcopy(system.domain_experience), deepcopy(system.discovered_techs),
            deepcopy(system.diffusion_progress), deepcopy(system.active_bounties),
            deepcopy(system.discovery_log),
            [[person.cash for tile in nation.tiles for person in tile.agents]
             for nation in nations])


def _funded_nation(*, trace=None, clock=None, cash=100.0, deposits=0.0):
    nation = _nation(trace=trace, clock=clock)
    nation.government = SimpleNamespace(name='Alpha Treasury',
                                        agent=SimpleNamespace(cash=cash))
    nation.treasury = Mock(side_effect=lambda: {
        'cash': nation.government.agent.cash, 'deposits': deposits,
        'total': nation.government.agent.cash + deposits})
    return nation


class InnovationTraceTests(unittest.TestCase):
    def test_learning_replays_actual_sources_and_legacy_proxies(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'learning.ctr', 'learning')
            clock = {'turn': 1, 'phase': 'production', 'next': 1}
            nation = _nation(trace=trace, clock=clock)
            second = _nation('Second', trace=trace, clock=clock).tiles[0]
            second.production_log = {Goods.food: [100], Goods.wood: [10],
                                     Goods.furniture: [0]}
            second.export_vol = {Goods.wood: [4]}
            second.gov.tax_revenue_log = [50.0]
            second.military_units = []
            nation.tiles.append(second)
            for tile in nation.tiles:
                for good, history in tile.production_log.items():
                    trace.emit(clock, kind='tile_production_total',
                               record_class='calculation',
                               subject={'type': 'tile', 'id': tile.name, 'good': good.name},
                               metric_id='goods.production', after=history[-1])
            system = InnovationSystem()
            opening = dict(zip((domain.value for domain in TechDomain), (10, 20, 30, 40, 50)))
            system.domain_experience[nation.name] = dict(opening)
            system.accumulate_learning_by_doing(nation.tiles, [nation], 1)
            expected = (14.5, 21.9, 30.38, 41.0, 50.6)
            for domain, value in zip(TechDomain, expected):
                self.assertAlmostEqual(system.get_domain_xp(nation.name, domain), value)
            rows = [row for row in trace.recent
                    if row.get('metric_id') == 'innovation.domain_experience']
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row['formula_replay']['matches'] for row in rows))
            agronomy = next(row for row in rows if row['subject']['domain'] == 'agronomy')
            self.assertEqual(len(agronomy['cause_event_ids']), 2)
            finance = next(row for row in rows if row['subject']['domain'] == 'finance')
            samples = finance['inputs']['terms'][0]['tile_samples']
            self.assertEqual([row['source_available'] for row in samples], [False, True])
            military = next(row for row in rows if row['subject']['domain'] == 'military')
            self.assertEqual(military['inputs']['terms'][0]['quantity'], 20)

    def test_builtin_pressure_evidence_replays_each_rule_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'pressure.ctr', 'pressure')
            clock = {'turn': 1, 'phase': 'innovation', 'next': 1}
            nation = _nation(trace=trace, clock=clock)
            tile = nation.tiles[0]
            high = SimpleNamespace(name='Highland', elevation=0.8,
                                   all_adjacent_names=[tile.name])
            tile.all_adjacent_names = [high.name]
            edges = SimpleNamespace(get_edge=Mock(return_value=SimpleNamespace(passable=False)))
            wars = SimpleNamespace(active_wars=[('Alpha', f'Enemy-{i}') for i in range(4)])
            cases = ((innovation._eval_food_bottleneck, [tile], 3.25),
                     (innovation._eval_mountain_bottleneck, [tile, high], 2.4),
                     (innovation._eval_wage_labor_bottleneck, [tile], 2.2),
                     (innovation._eval_war_bottleneck, [tile], 6.5))
            with patch('terrain_edges.get_edge_manager', return_value=edges), \
                    patch('diplomacy.get_diplomacy', return_value=wars):
                for evaluator, tiles, expected in cases:
                    evidence = {}
                    value = evaluator(nation, tiles, evidence=evidence)
                    self.assertAlmostEqual(value, expected)
                    record_pressure(nation, evaluator.__name__, 1, value,
                                    evidence, known_formula=True)
                    self.assertTrue(trace.recent[-1]['formula_replay']['matches'])
            self.assertEqual(edges.get_edge.call_count, 2)
            tile.recipes[Goods.food]['price'] = 10.0
            evidence = {}
            self.assertEqual(innovation._eval_food_bottleneck(nation, [tile], evidence=evidence), 4.0)
            record_pressure(nation, 'food_cap', 1, 4.0, evidence, known_formula=True)
            self.assertTrue(trace.recent[-1]['formula_replay']['matches'])
            for person in tile.agents:
                person.wage = 10.0
                person.hungry_steps = 0
            tile.recipes[Goods.food]['price'] = 1.0
            for evaluator, expected in ((innovation._eval_wage_labor_bottleneck, 3.5),
                                        (innovation._eval_food_bottleneck, 1.0)):
                evidence = {}
                value = evaluator(nation, [tile], evidence=evidence)
                self.assertEqual(value, expected)
                record_pressure(nation, 'bound', 1, value, evidence, known_formula=True)
                self.assertTrue(trace.recent[-1]['formula_replay']['matches'])
            mountain_tiles = [SimpleNamespace(name=f'Peak-{index}', elevation=0.6,
                                              all_adjacent_names=[]) for index in range(10)]
            evidence = {}
            with patch('terrain_edges.get_edge_manager', return_value=None):
                value = innovation._eval_mountain_bottleneck(nation, mountain_tiles, evidence=evidence)
            self.assertEqual(value, 4.5)
            record_pressure(nation, 'mountain_cap', 1, value, evidence, known_formula=True)
            self.assertTrue(trace.recent[-1]['formula_replay']['matches'])
            evidence = {}
            with patch('diplomacy.get_diplomacy', return_value=SimpleNamespace(active_wars=[])):
                value = innovation._eval_war_bottleneck(nation, [tile], evidence=evidence)
            self.assertEqual(value, 1.0)
            record_pressure(nation, 'peace', 1, value, evidence, known_formula=True)
            self.assertTrue(trace.recent[-1]['formula_replay']['matches'])
            for evaluator in (innovation._eval_food_bottleneck,
                              innovation._eval_mountain_bottleneck,
                              innovation._eval_wage_labor_bottleneck):
                evidence = {}
                self.assertEqual(evaluator(nation, [], evidence=evidence), 1.0)
                record_pressure(nation, 'empty', 1, 1.0, evidence, known_formula=True)
                self.assertTrue(trace.recent[-1]['formula_replay']['matches'])

    def test_research_gates_draws_and_bounty_effect_preserve_outcomes(self):
        domain = TechDomain.MANUFACTURING
        catalog = {key: Technology(key, key, domain, '', 100.0)
                   for key in ('known', 'prerequisite', 'resource', 'low', 'failed', 'won', 'bounty')}
        catalog['prerequisite'].required_techs = ['absent']
        catalog['resource'].required_resources = ['ore']
        catalog['low'].domain = catalog['bounty'].domain = TechDomain.AGRONOMY
        catalog['low'].bottleneck_evaluator = catalog['bounty'].bottleneck_evaluator = innovation._eval_food_bottleneck
        results = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(innovation, 'TECH_CATALOG', catalog):
            trace = RunTrace(Path(tmp) / 'research.ctr', 'research')
            clock = {'turn': 1, 'phase': 'innovation', 'next': 1}
            for traced in (False, True):
                nation = _nation(trace=trace if traced else None, clock=clock)
                system = InnovationSystem()
                system.discovered_techs['Alpha'] = {'known'}
                system.domain_experience['Alpha'] = {'agronomy': 10.0, 'manufacturing': 100.0}
                system.active_bounties = [RoyalBounty('bounty', 'Alpha', 60.0, 0)]
                random_draw = Mock(side_effect=[0.9, 0.01, 0.1])
                before_random = random.getstate()
                with patch.object(innovation, 'rand', SimpleNamespace(random=random_draw)), \
                        patch.object(innovation, 'get_nation_resources', return_value=set()) as resources:
                    events = system.evaluate_breakthroughs([nation], 1)
                self.assertEqual(random_draw.call_count, 3)
                self.assertEqual(resources.call_count, 5)
                self.assertEqual(random.getstate(), before_random)
                self.assertEqual([row['tech_id'] for row in events], ['won', 'bounty'])
                results.append(_state(system, [nation]))
            self.assertEqual(results[0], results[1])
            rows = list(trace.recent)
            gates = [row['value_after'] for row in rows if row.get('metric_id') == 'innovation.research_gate']
            self.assertEqual(gates, ['already_known', 'missing_prerequisites', 'missing_resources'])
            evaluations = [row for row in rows if row.get('metric_id') == 'innovation.breakthrough']
            self.assertEqual(len(evaluations), 4)
            self.assertTrue(all(row['formula_replay']['matches'] for row in evaluations))
            low = next(row for row in evaluations if row['subject']['tech_id'] == 'low')
            self.assertIsNone(low['inputs']['random_draw'])
            known = [row for row in rows if row.get('metric_id') == 'innovation.technology_known']
            self.assertEqual(len(known), 2)
            self.assertTrue(all(row['cause_event_ids'] for row in known))

    def test_custom_pressure_callback_runs_once_and_remains_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'custom.ctr', 'custom')
            nation = _nation(trace=trace, clock={'turn': 1, 'phase': 'innovation', 'next': 1})
            callback = Mock(return_value=2.0)
            tech = Technology('custom', 'custom', TechDomain.AGRONOMY, '', 100.0,
                              bottleneck_evaluator=callback)
            system = InnovationSystem()
            system.domain_experience['Alpha'] = {'agronomy': 100.0}
            with patch.object(innovation, 'TECH_CATALOG', {'custom': tech}), \
                    patch.object(innovation, 'get_nation_resources', return_value=set()), \
                    patch.object(innovation, 'rand', SimpleNamespace(random=Mock(return_value=0.9))):
                system.evaluate_breakthroughs([nation], 1)
            callback.assert_called_once()
            pressure = next(row for row in trace.recent
                            if row.get('metric_id') == 'innovation.bottleneck_pressure')
            self.assertEqual(pressure['record_class'], 'observation')
            self.assertEqual(pressure['confidence'], 'unknown')
            self.assertNotIn('formula_replay', pressure)

    def test_diffusion_rate_preserves_zero_trade_and_strict_trade_threshold(self):
        cases = ((0.0, False, 0.008), (25.0, False, 0.008), (100.0, True, 0.035))
        with tempfile.TemporaryDirectory() as tmp:
            for index, (trade, pact, expected) in enumerate(cases):
                trace = RunTrace(Path(tmp) / f'diffuse-{index}.ctr', f'd-{index}')
                clock = {'turn': 1, 'phase': 'innovation', 'next': 1}
                source = _nation('Alpha', trace=trace, clock=clock)
                destination = _nation('Beta', trace=trace, clock=clock)
                source.tiles[0].export_val[Goods.food] = [trade]
                system = InnovationSystem()
                system.discovered_techs['Alpha'] = {'crop_rotation'}
                diplomacy = SimpleNamespace(has_treaty=Mock(return_value=pact))
                with patch('diplomacy.get_diplomacy', return_value=diplomacy), \
                        patch.object(innovation, 'get_nation_resources') as resources:
                    system.diffuse_technologies_along_trade(
                        [(source.tiles[0], destination.tiles[0])], [source, destination], 1)
                resources.assert_not_called()
                row = next(row for row in trace.recent
                           if row.get('metric_id') == 'innovation.diffusion_progress')
                self.assertEqual(row['value_after'], expected)
                self.assertTrue(row['formula_replay']['matches'])

    def test_diffusion_pair_order_and_adoption_reset_match_without_trace(self):
        results = []
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'adoption.ctr', 'adoption')
            clock = {'turn': 1, 'phase': 'innovation', 'next': 1}
            for traced in (False, True):
                source = _nation('Alpha', trace=trace if traced else None, clock=clock)
                destination = _nation('Beta', trace=trace if traced else None, clock=clock)
                system = InnovationSystem()
                system.discovered_techs['Alpha'] = {'crop_rotation'}
                system.diffusion_progress['Beta'] = {'crop_rotation': 0.99}
                pair = (source.tiles[0], destination.tiles[0])
                diplomacy = SimpleNamespace(has_treaty=Mock(return_value=False))
                with patch('diplomacy.get_diplomacy', return_value=diplomacy):
                    events = system.diffuse_technologies_along_trade(
                        [pair, pair, pair], [source, destination], 1)
                self.assertEqual(len(events), 1)
                self.assertEqual(diplomacy.has_treaty.call_count, 2)
                self.assertIn('crop_rotation', system.discovered_techs['Beta'])
                self.assertNotIn('crop_rotation', system.diffusion_progress['Beta'])
                results.append(_state(system, [source, destination]))
            self.assertEqual(results[0], results[1])
            progress = [row for row in trace.recent
                        if row.get('metric_id') == 'innovation.diffusion_progress']
            self.assertEqual(len(progress), 3)
            self.assertIn(progress[0]['event_id'], progress[1]['cause_event_ids'])
            self.assertEqual(progress[-1]['value_after'], 0.0)
            self.assertTrue(all(row['formula_replay']['matches'] for row in progress))

    def test_bounty_offer_gates_and_cash_only_funding_are_explicit(self):
        cases = (('unknown', False, 100.0, 0.0, False, 'unknown_technology'),
                 ('crop_rotation', True, 100.0, 0.0, False, 'technology_already_known'),
                 ('crop_rotation', False, 10.0, 0.0, False, 'insufficient_total_treasury'),
                 ('crop_rotation', False, 20.0, 100.0, True, 'affordable_from_total_treasury'))
        with tempfile.TemporaryDirectory() as tmp:
            for index, (tech, known, cash, deposits, expected, reason) in enumerate(cases):
                trace = RunTrace(Path(tmp) / f'offer-{index}.ctr', f'offer-{index}')
                clock = {'turn': 1, 'phase': 'innovation', 'next': 1}
                nation = _funded_nation(trace=trace, clock=clock, cash=cash, deposits=deposits)
                system = InnovationSystem()
                if known:
                    system.discovered_techs['Alpha'] = {tech}
                self.assertEqual(system.post_royal_bounty(nation, tech, 60.0, 1), expected)
                gate = next(row for row in trace.recent
                            if row.get('metric_id') == 'innovation.bounty_offer')
                self.assertEqual(gate['inputs']['reason'], reason)
                self.assertEqual(nation.treasury.call_count, 0 if known or tech == 'unknown' else 1)
                if expected:
                    self.assertEqual(nation.government.agent.cash, -40.0)
                    reservation = next(row for row in trace.recent
                                       if row.get('metric_id') == 'innovation.bounty_escrow')
                    self.assertEqual(reservation['value_after'], 60.0)
                    self.assertTrue(reservation['formula_replay']['matches'])
                    cash_row = next(row for row in trace.recent
                                    if row['kind'] == 'innovation_bounty_treasury_reservation')
                    self.assertEqual(cash_row['value_after'], -60.0)
                    contract = cash_row['inputs']['transfer_contract']
                    self.assertEqual(contract['payer_account']['balance_before'], 20.0)
                    self.assertEqual(contract['payer_account']['balance_after'], -40.0)
                else:
                    self.assertEqual(nation.government.agent.cash, cash)
                    self.assertFalse(system.active_bounties)

    def test_diffusion_links_source_discovery_across_turns(self):
        from innovation_trace import record_technology

        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'source-tech.ctr', 'source-tech')
            clock = {'turn': 1, 'phase': 'innovation', 'next': 1}
            source = _nation('Alpha', trace=trace, clock=clock)
            destination = _nation('Beta', trace=trace, clock=clock)
            system = InnovationSystem()
            system.discovered_techs['Alpha'] = {'crop_rotation'}
            discovery_id = record_technology(source, 'crop_rotation', 1, 'domestic_breakthrough')
            trace.snapshot(clock, subject={'type': 'nation', 'id': source.name,
                                           'tech_id': 'crop_rotation'},
                           metric_id='innovation.technology_known', unit='boolean',
                           before=None, after=1)
            clock['turn'] = 2
            with patch('diplomacy.get_diplomacy', return_value=SimpleNamespace(
                    has_treaty=Mock(return_value=False))):
                system.diffuse_technologies_along_trade(
                    [(source.tiles[0], destination.tiles[0])], [source, destination], 2)
            progress = next(row for row in trace.recent
                            if row.get('metric_id') == 'innovation.diffusion_progress')
            self.assertEqual(progress['inputs']['source_knowledge_event_id'], discovery_id)
            self.assertIn(discovery_id, progress['cause_event_ids'])

    def test_bounty_funding_payouts_and_empty_capital_match_without_trace(self):
        tech = Technology('prize', 'Prize', TechDomain.AGRONOMY, '', 100.0)
        with tempfile.TemporaryDirectory() as tmp, patch.object(innovation, 'TECH_CATALOG', {'prize': tech}):
            for empty in (False, True):
                results = []
                trace = RunTrace(Path(tmp) / f'award-{empty}.ctr', f'award-{empty}')
                clock = {'turn': 1, 'phase': 'innovation', 'next': 1}
                for traced in (False, True):
                    nation = _funded_nation(trace=trace if traced else None, clock=clock)
                    if empty:
                        nation.tiles[0].agents = []
                    system = InnovationSystem()
                    self.assertTrue(system.post_royal_bounty(nation, 'prize', 60.0, 1))
                    system.domain_experience['Alpha'] = {'agronomy': 1000.0}
                    clock['turn'] = 2
                    draw = Mock(return_value=0.0)
                    with patch.object(innovation, 'get_nation_resources', return_value=set()), \
                            patch.object(innovation, 'rand', SimpleNamespace(random=draw)):
                        system.evaluate_breakthroughs([nation], 2)
                    draw.assert_called_once()
                    self.assertEqual(nation.government.agent.cash, 40.0)
                    self.assertFalse(system.active_bounties)
                    results.append((_state(system, [nation]), nation.government.agent.cash))
                    clock['turn'] = 1
                self.assertEqual(results[0], results[1])
                rows = list(trace.recent)
                reserved = next(row for row in rows
                                if row['kind'] == 'innovation_bounty_escrow_reserved')
                removed = next(row for row in rows
                               if row['kind'] == 'innovation_bounty_escrow_removed')
                self.assertEqual(reserved['subject']['bounty_id'], removed['subject']['bounty_id'])
                self.assertEqual(reserved['turn'], 1)
                self.assertEqual(removed['turn'], 2)
                self.assertTrue(removed['formula_replay']['matches'])
                self.assertEqual(removed['inputs']['unpaid_escrow_removed'], 60.0 if empty else 0.0)
                payments = [row for row in rows if row['kind'] == 'innovation_bounty_award_payment']
                self.assertEqual(len(payments), 0 if empty else 12)
                self.assertEqual(sum(row['value_after'] for row in payments), 0.0 if empty else 60.0)
                self.assertIn(reserved['event_id'], removed['cause_event_ids'])
                for payment in payments:
                    self.assertIn(reserved['event_id'], payment['cause_event_ids'])
                    self.assertEqual(payment['inputs']['transfer_contract']['payee_account']['balance_after'], 15.0)
                self.assertEqual(len([row for row in rows
                                      if row.get('metric_id') == 'finance.treasury_flow']), 1)

    def test_bounty_snapshot_and_journal_inventory_share_recorded_identity(self):
        from metric_catalog import inventory_histories
        from sim_server.sim_server import SimServer
        from trace_snapshots import sample

        system = InnovationSystem()
        with patch.object(innovation, '_INNOVATION_SYSTEM', system):
            server = SimServer(seed=627, scenario_id='labor_frontier_rivalry')
            nation = server.nations[0]
            nation.government.agent.cash = 1000.0
            self.assertTrue(system.post_royal_bounty(nation, 'crop_rotation', 60.0, 0))
            self.assertTrue(system.post_royal_bounty(nation, 'crop_rotation', 60.0, 0))
            first, second = system.active_bounties
            self.assertNotEqual(first._trace_operation_id, second._trace_operation_id)
            values = sample(server.tiles, server.nations)
            for bounty in system.active_bounties:
                key = ('innovation.bounty_escrow', nation.name, bounty._trace_operation_id)
                self.assertEqual(values[key][2], 60.0)
            fields = {row['field']: row for row in inventory_histories(system)}
            self.assertEqual(fields['discovery_log']['history_kind'], 'event_journal')
            self.assertEqual(fields['discovery_log']['coverage'], 'instrumented')
            # Nation trace context remains usable after loss of all territory.
            nation.tiles = []
            system.evaluate_breakthroughs([nation], 0)
            rows = server.run_trace.query(metric_id='innovation.research_gate', limit=1000)['events']
            self.assertTrue(any(row['inputs']['reason'] == 'no_territory' for row in rows))


if __name__ == '__main__':
    unittest.main()
