"""Causal traces for strategic-project staffing and lifecycle gates."""

import json
import tempfile
import unittest
from pathlib import Path

from run_trace import RunTrace, verify
from scenario_projects import (advance, cancel_project, damage_project,
                               get_project, repair_project, start_project)
from worldview_engine import build_world_view


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        sequence = clock['next']
        clock['next'] += 1
        event_id = f'project-test:{sequence}'
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True):
    world = build_world_view(scenario_id='egypt_1877')
    world['turn'] = 1
    trace = MemoryTrace()
    clock = {'turn': 1, 'phase': 'scenario_projects', 'next': 1}
    if traced:
        for tile in world['tiles']:
            tile._run_trace = trace
            tile._collective_trace_clock = clock
    return world, trace


class StrategicProjectLifecycleTraceTests(unittest.TestCase):
    @staticmethod
    def _row(trace, action, *, turn=None, reason=None):
        return next(row for row in trace.rows
                    if row.get('metric_id') == 'scenario.project_lifecycle'
                    and row.get('inputs', {}).get('action') == action
                    and (turn is None or row['inputs'].get('turn') == turn)
                    and (reason is None or row['inputs'].get('reason') == reason))

    @staticmethod
    def _rows(trace, metric_id, *, kind=None):
        return [row for row in trace.rows
                if row.get('metric_id') == metric_id
                and (kind is None or row.get('kind') == kind)]

    def test_start_and_duplicate_gate_link_construction_wages(self):
        world, trace = _fixture()

        self.assertTrue(start_project(world, 'nile_repair', 'Nile Delta')[0])
        started = self._row(trace, 'start', reason='construction_funded')
        wages = self._rows(trace, 'finance.treasury_flow',
                           kind='scenario_construction_wage')
        self.assertEqual(len(wages), 3)
        self.assertEqual(set(started['cause_event_ids']),
                         {row['event_id'] for row in wages})
        self.assertEqual(started['inputs']['state_after']['status'], 'building')
        self.assertEqual(started['inputs']['required_work_turns'], 2)
        self.assertEqual(set(started['inputs']['selected_worker_ids']),
                         {row['inputs']['worker_id'] for row in wages})

        self.assertFalse(start_project(world, 'nile_repair', 'Nile Delta')[0])
        duplicate = self._row(trace, 'start', reason='already_active')
        self.assertFalse(duplicate['inputs']['success'])
        self.assertEqual(duplicate['inputs']['state_before']['status'], 'building')
        self.assertEqual(duplicate['inputs']['state_after'],
                         duplicate['inputs']['state_before'])

    def test_start_and_repair_rejection_gates_include_blocking_conditions(self):
        occupied_world, occupied_trace = _fixture()
        occupied_world['scenario_state']['campaign']['territorial_control'][
            'Alexandria'] = 'Britain'
        self.assertFalse(start_project(
            occupied_world, 'revenue_office', 'Alexandria')[0])
        occupied_start = self._row(occupied_trace, 'start', reason='site_occupied')
        self.assertEqual(occupied_start['inputs']['occupying_nation'], 'Britain')
        self.assertIsNone(occupied_start['inputs']['state_before'])
        self.assertIsNone(occupied_start['inputs']['state_after'])

        poor_world, poor_trace = _fixture()
        poor_egypt = next(nation for nation in poor_world['nations']
                          if nation.name == 'Egypt')
        poor_egypt.government.agent.cash = 0
        self.assertFalse(start_project(poor_world, 'nile_repair', 'Nile Delta')[0])
        poor_start = self._row(poor_trace, 'start',
                               reason='insufficient_treasury')
        self.assertEqual(poor_start['inputs']['required_construction_cash'], 45.0)
        self.assertEqual(poor_start['inputs']['treasury_cash_before'], 0.0)
        self.assertIsNone(get_project(poor_world, 'nile_repair', 'Nile Delta'))

        repair_world, repair_trace = _fixture()
        self.assertTrue(start_project(
            repair_world, 'canal_line', 'Tel el Kebir')[0])
        self.assertTrue(damage_project(
            repair_world, 'canal_line', 'Tel el Kebir', .7))
        repair_world['scenario_state']['campaign']['territorial_control'][
            'Tel el Kebir'] = 'Britain'
        self.assertFalse(repair_project(
            repair_world, 'canal_line', 'Tel el Kebir')[0])
        blocked_repair = self._row(repair_trace, 'repair', reason='site_occupied')
        self.assertEqual(blocked_repair['inputs']['occupying_nation'], 'Britain')
        self.assertEqual(blocked_repair['inputs']['state_before'],
                         blocked_repair['inputs']['state_after'])

    def test_advance_records_occupation_work_and_upkeep_causes(self):
        world, trace = _fixture()
        self.assertTrue(start_project(world, 'revenue_office', 'Alexandria')[0])
        project = get_project(world, 'revenue_office', 'Alexandria')
        world['scenario_state']['campaign']['territorial_control']['Alexandria'] = 'Britain'
        world['turn'] = 2
        advance(world)
        occupied = self._row(trace, 'advance', turn=2, reason='site_occupied')
        self.assertEqual(occupied['inputs']['occupying_nation'], 'Britain')
        self.assertFalse(occupied['inputs']['work_progressed'])
        self.assertEqual(project['progress'], 0)

        world['scenario_state']['campaign']['territorial_control'].clear()
        world['turn'] = 3
        advance(world)
        work = self._row(trace, 'advance', turn=3,
                         reason='staffed_work_progress')
        self.assertEqual(work['inputs']['progress_before'], 0)
        self.assertEqual(work['inputs']['progress_after'], 1)
        self.assertEqual(project['progress'], 1)

        world['turn'] = 4
        advance(world)
        world['turn'] = 5
        advance(world)
        operating = self._row(trace, 'advance', turn=5,
                              reason='operating_upkeep_paid')
        wages = self._rows(trace, 'finance.treasury_flow',
                           kind='scenario_staff_wage')
        self.assertTrue(wages)
        self.assertTrue(set(row['event_id'] for row in wages)
                        .issubset(set(operating['cause_event_ids'])))
        self.assertTrue(operating['inputs']['construction_completed_this_turn'])
        self.assertEqual(project['status'], 'operating')

    def test_canal_crew_food_is_itemized_and_linked_to_operation(self):
        world, trace = _fixture()
        self.assertTrue(start_project(world, 'canal_line', 'Tel el Kebir')[0])
        egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
        stock_before = int(egypt.government.food_inventory)
        for turn in (2, 3):
            world['turn'] = turn
            advance(world)

        transfers = self._rows(trace, 'goods.project_crew_food',
                               kind='scenario_project_crew_food_transfer')
        self.assertEqual(len(transfers), 3)
        self.assertEqual(sum(row['after'] - row['before'] for row in transfers), 6)
        self.assertEqual(stock_before - int(egypt.government.food_inventory), 6)
        self.assertEqual({row['inputs']['source_inventory_after'] for row in transfers},
                         {int(next(n for n in world['nations'] if n.name == 'Egypt')
                              .government.food_inventory)})
        operating = self._row(trace, 'advance', turn=3,
                              reason='operating_upkeep_paid')
        self.assertEqual(set(operating['inputs']['crew_food_event_ids']),
                         {row['event_id'] for row in transfers})
        self.assertTrue(set(row['event_id'] for row in transfers)
                        .issubset(set(operating['cause_event_ids'])))

    def test_advance_records_missing_crew_food_and_treasury_gates(self):
        stalled_world, stalled_trace = _fixture()
        self.assertTrue(start_project(stalled_world, 'nile_repair', 'Nile Delta')[0])
        project = get_project(stalled_world, 'nile_repair', 'Nile Delta')
        tile = next(tile for tile in stalled_world['tiles']
                    if tile.name == project['tile'])
        departed = next(agent for agent in tile.agents
                        if agent.id == project['worker_ids'][0])
        departed.alive = False
        stalled_world['turn'] = 2
        advance(stalled_world)
        stalled = self._row(stalled_trace, 'advance', turn=2,
                            reason='original_crew_unavailable')
        self.assertIn(departed.id, stalled['inputs']['missing_worker_ids'])
        self.assertEqual(project['status'], 'stalled')

        food_world, food_trace = _fixture()
        self.assertTrue(start_project(food_world, 'canal_line', 'Tel el Kebir')[0])
        egypt = next(nation for nation in food_world['nations'] if nation.name == 'Egypt')
        egypt.government.food_inventory = 0
        project = get_project(food_world, 'canal_line', 'Tel el Kebir')
        for turn in (2, 3):
            food_world['turn'] = turn
            advance(food_world)
        unsupplied = self._row(food_trace, 'advance', turn=3,
                               reason='insufficient_public_food')
        self.assertEqual(unsupplied['inputs']['food_required'], 6)
        self.assertEqual(unsupplied['inputs']['public_food_inventory'], 0)
        self.assertEqual(project['status'], 'unsupplied')

        poor_world, poor_trace = _fixture()
        self.assertTrue(start_project(poor_world, 'nile_repair', 'Nile Delta')[0])
        poor_egypt = next(nation for nation in poor_world['nations']
                          if nation.name == 'Egypt')
        project = get_project(poor_world, 'nile_repair', 'Nile Delta')
        poor_world['turn'] = 2
        advance(poor_world)
        poor_egypt.government.agent.cash = 0
        poor_world['turn'] = 3
        advance(poor_world)
        unfunded = self._row(poor_trace, 'advance', turn=3,
                             reason='upkeep_unaffordable')
        self.assertEqual(unfunded['inputs']['treasury_cash_before_upkeep'], 0)
        self.assertEqual(project['status'], 'unfunded')

    def test_damage_repair_and_cancellation_record_sunk_costs_and_causes(self):
        world, trace = _fixture()
        self.assertTrue(start_project(world, 'nile_repair', 'Nile Delta')[0])
        construction = self._rows(trace, 'finance.treasury_flow',
                                  kind='scenario_construction_wage')[0]

        self.assertTrue(damage_project(
            world, 'nile_repair', 'Nile Delta', .7,
            cause_event_ids=[construction['event_id']]))
        damage = self._row(trace, 'damage', reason='project_integrity_damaged')
        self.assertIn(construction['event_id'], damage['cause_event_ids'])
        self.assertAlmostEqual(damage['inputs']['integrity_after'], .3)

        self.assertTrue(repair_project(world, 'nile_repair', 'Nile Delta')[0])
        repair = self._row(trace, 'repair', reason='repair_wages_paid')
        repair_wages = self._rows(trace, 'finance.treasury_flow',
                                  kind='scenario_repair_wage')
        self.assertEqual(set(repair['cause_event_ids']),
                         {row['event_id'] for row in repair_wages})
        self.assertEqual(repair['inputs']['state_after']['integrity'], 1.0)

        self.assertTrue(cancel_project(world, 'nile_repair', 'Nile Delta')[0])
        cancelled = self._row(trace, 'cancel', reason='project_abandoned')
        self.assertFalse(cancelled['inputs']['wages_reclaimed'])
        self.assertEqual(cancelled['inputs']['sunk_construction_cash'], 60.75)

    def test_battle_damage_links_to_project_integrity_change(self):
        from scenario_campaign import _battle
        from scenario_geography import create_fleet

        world, trace = _fixture()
        self.assertTrue(start_project(world, 'canal_line', 'Tel el Kebir')[0])
        for turn in (2, 3):
            world['turn'] = turn
            advance(world)
        create_fleet(world, 'Britain')
        world['turn'] = 4
        _battle(world, 'Tel el Kebir')

        battle = self._rows(trace, 'war.battle')[-1]
        damage = self._row(trace, 'damage', reason='project_integrity_damaged')
        self.assertEqual(battle['inputs']['project_defense_bonus'], 55.0)
        self.assertIn(battle['event_id'], damage['cause_event_ids'])
        self.assertEqual(damage['inputs']['integrity_before'], 1.0)
        self.assertEqual(damage['inputs']['integrity_after'], .65)

    def test_trace_on_off_parity_and_compact_serialization(self):
        def run(traced):
            world, trace = _fixture(traced=traced)
            start_project(world, 'nile_repair', 'Nile Delta')
            world['turn'] = 2
            advance(world)
            damage_project(world, 'nile_repair', 'Nile Delta', .7)
            repair_project(world, 'nile_repair', 'Nile Delta')
            cancel_project(world, 'nile_repair', 'Nile Delta')
            project = world['scenario_state']['strategic_projects']['projects'][0]
            egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
            return ({key: project[key] for key in
                     ('status', 'progress', 'integrity', 'paid_cash', 'upkeep_paid')},
                    float(egypt.government.agent.cash),
                    [float(agent.cash) for tile in egypt.tiles for agent in tile.agents],
                    trace)

        state_on, treasury_on, people_on, _ = run(True)
        state_off, treasury_off, people_off, _ = run(False)
        self.assertEqual(state_on, state_off)
        self.assertAlmostEqual(treasury_on, treasury_off)
        self.assertEqual(people_on, people_off)

        world, _ = _fixture(traced=False)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'project-lifecycle.ctr'
            recorder = RunTrace(path, 'project-lifecycle-test')
            clock = {'turn': 1, 'phase': 'scenario_projects', 'next': 1}
            for tile in world['tiles']:
                tile._run_trace = recorder
                tile._collective_trace_clock = clock
            start_project(world, 'nile_repair', 'Nile Delta')
            damage_project(world, 'nile_repair', 'Nile Delta', .7)
            repair_project(world, 'nile_repair', 'Nile Delta')
            result = recorder.query(metric_id='scenario.project_lifecycle')
            self.assertEqual(result['total'], 3)
            self.assertGreater(verify(path)['rows'], 1)


if __name__ == '__main__':
    unittest.main()
