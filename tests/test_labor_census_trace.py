"""Final labor rollups explain classification, membership and world-phase changes."""

from copy import deepcopy
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest

from agent import Agent, initialize_agent
from goods import Goods
from labor_census_trace import capture_labor_censuses, census_groups
from labor_choice import apply_career_switch, record_labor_status
from region import Region
from run_trace import RunTrace
from trace_snapshots import (entity_role_census, record, resident_census, sample)


def _person(ident, good=Goods.food):
    person = Agent(0)
    person.id = ident
    initialize_agent(person, good, 0, 4, 10.0)
    person.birth_round = -30
    person.alive = True
    person.temporary_work_share = 0.0
    return person


def _world(trace):
    first, second = Region('Origin', 0, number_of_agents=0), Region('Destination', 0, number_of_agents=0)
    people = {index: _person(1000 + index) for index in range(1, 11)}
    people[1].hungry_steps = 1
    people[1].temporary_work_share = 0.25
    people[2].primary_livelihood = Goods.wood
    people[2].birth_round = 0  # Non-native-child agents are included by the existing rule.
    people[2].is_trader = True
    people[2].military_unit_id = 7
    people[3].primary_livelihood = Goods.cloth
    people[3].is_native_child = True
    people[3].birth_round = -4  # Exactly 14 at the initial age-evaluation turn.
    people[3].employer = SimpleNamespace(id=9000)
    people[3].temporary_work_share = 0.125
    people[4].is_native_child = True
    people[4].birth_round = -3
    people[4].hungry_steps = 1
    people[5].is_corporation = True
    people[6].is_government = True
    people[7].alive = False
    people[8].social_class = 'constable'
    people[8].in_workhouse = True
    people[8].employer = SimpleNamespace(id=9000)
    people[9].in_workhouse = True
    people[9].employer = SimpleNamespace(id=9000)
    people[9].hungry_steps = 2
    people[10].is_trader = True
    first.agents, second.agents = list(people.values()), []
    clock = {'turn': 10, 'phase': 'local', 'next': 1}
    for tile in (first, second):
        tile._last_turn = 10
        tile._run_trace = trace
        tile._collective_trace_clock = clock
    tiles = [first, second]
    baseline = capture_labor_censuses(tiles)
    server = SimpleNamespace(
        tiles=tiles, nations=[], run_trace=trace,
        _trace_previous=sample(tiles, [], labor_censuses=baseline),
        _trace_previous_labor_censuses=baseline,
        _trace_previous_people=resident_census(tiles),
        _trace_previous_roles=entity_role_census(tiles))
    return server, people, clock


class LaborCensusTraceTests(unittest.TestCase):
    def test_census_keeps_actual_age_and_status_priority_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'classify.ctr', 'classify')
            server, people, _clock = _world(trace)
            before = deepcopy(server._trace_previous_labor_censuses)
            rng = random.getstate()
            current = capture_labor_censuses(server.tiles)
            self.assertEqual(current, before)
            self.assertEqual(random.getstate(), rng)
            first = current['Origin']
            self.assertEqual(len(first['adults']), 6)
            self.assertEqual({row['person_id']: row['reason'] for row in first['excluded']},
                             {'1004': 'native_child_under_14', '1005': 'corporation',
                              '1006': 'government', '1007': 'dead'})
            statuses = census_groups(first, 'status')
            self.assertEqual(statuses['military'], ['1002'])
            self.assertEqual(statuses['constable'], ['1008'])
            self.assertEqual(statuses['workhouse'], ['1009'])
            self.assertEqual(statuses['employed'], ['1003'])
            self.assertEqual(statuses['trader'], ['1010'])
            values = sample(server.tiles, [], labor_censuses=current)
            self.assertEqual(values[('labor.hungry_adults', 'Origin')][2], 2)
            self.assertEqual(values[('labor.temporary_work_share', 'Origin')][2], 0.0625)
            self.assertEqual(people[3].birth_round, -4)

    def test_final_rollups_link_career_status_migration_and_intake_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'world-changes.ctr', 'world-changes')
            server, people, clock = _world(trace)
            clock['turn'] = 11
            first, second = server.tiles
            for tile in server.tiles:
                tile._last_turn = 11
            self.assertTrue(apply_career_switch(first, people[1], Goods.wood, 11,
                                               reason='TEST_OCCUPATION_CHANGE'))
            career_id = trace.recent[-1]['event_id']
            people[1].hungry_steps = 0
            intake_id = trace.emit(
                clock, kind='household_food_intake', record_class='calculation',
                subject={'type': 'tile/agent', 'id': str(people[1].id),
                         'tile': first.name, 'good': 'food'},
                metric_id='health.calorie_deficit', after=0,
                inputs={'agent_id': people[1].id})
            people[1].temporary_work_share = 0.0
            former_employer = people[3].employer
            people[3].employer = None
            record_labor_status(first, people[3], 11, before='employed', after='independent',
                                reason='TEST_STATUS_CHANGE', employer_before=former_employer)
            first.agents.remove(people[2])
            second.agents.append(people[2])
            for tile, kind in ((first, 'migration_departure'), (second, 'migration_arrival')):
                trace.emit(clock, kind=kind, record_class='transfer',
                           subject={'type': 'agent', 'id': people[2].id, 'tile': tile.name},
                           metric_id='people.migration', after=1,
                           inputs={'agent_id': people[2].id})
            before_record = capture_labor_censuses(server.tiles)
            rng = random.getstate()
            record(server)
            self.assertEqual(capture_labor_censuses(server.tiles), before_record)
            self.assertEqual(random.getstate(), rng)
            rows = list(trace.recent)
            calculations = [row for row in rows if row['kind'] in (
                'final_labor_member_count', 'final_temporary_work_share_mean')]
            self.assertTrue(calculations)
            self.assertTrue(all(row['formula_replay']['matches'] for row in calculations))
            origin_military = next(row for row in calculations
                                   if row['metric_id'] == 'labor.employment_status'
                                   and row['subject'] == {'type': 'tile', 'id': 'Origin', 'status': 'military'})
            self.assertEqual(origin_military['value_after'], 0)
            self.assertEqual(origin_military['inputs']['removed_member_ids'], ['1002'])
            destination_military = next(row for row in calculations
                                        if row['metric_id'] == 'labor.employment_status'
                                        and row['subject'] == {'type': 'tile', 'id': 'Destination', 'status': 'military'})
            self.assertEqual(destination_military['value_before'], 0)
            self.assertEqual(destination_military['value_after'], 1)
            by_id = {row['event_id']: row for row in rows}
            self.assertTrue(any(by_id[event_id]['kind'] == 'migration_departure'
                                for event_id in origin_military['cause_event_ids']))
            hungry = next(row for row in calculations if row['metric_id'] == 'labor.hungry_adults'
                          and row['subject']['id'] == 'Origin')
            # Aging-in replaces the relieved adult, so the total stays at two.
            self.assertEqual(hungry['value_before'], hungry['value_after'])
            self.assertEqual(hungry['inputs']['added_member_ids'], ['1004'])
            self.assertEqual(hungry['inputs']['removed_member_ids'], ['1001'])
            self.assertIn(intake_id, hungry['cause_event_ids'])
            self.assertNotIn(career_id, hungry['cause_event_ids'])
            self.assertNotIn(intake_id, origin_military['cause_event_ids'])
            snapshots = [row for row in rows if row['kind'] == 'metric_snapshot'
                         and row['metric_id'] in ('labor.primary_livelihood', 'labor.employment_status',
                                                  'labor.hungry_adults', 'labor.temporary_work_share')]
            self.assertTrue(snapshots)
            self.assertTrue(all(row['explanation_status'] == 'calculation_recorded' for row in snapshots))

    def test_empty_population_closes_old_categories_at_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'empty.ctr', 'empty')
            server, _people, clock = _world(trace)
            clock['turn'] = 11
            server.tiles[0].agents = []
            record(server)
            rows = [row for row in trace.recent if row['kind'] in (
                'final_labor_member_count', 'final_temporary_work_share_mean')
                    and row['subject']['id'] == 'Origin']
            self.assertTrue(rows)
            self.assertTrue(all(row['value_after'] == 0 for row in rows))
            self.assertTrue(all(row['formula_replay']['matches'] for row in rows))
            mean = next(row for row in rows if row['metric_id'] == 'labor.temporary_work_share')
            self.assertEqual(mean['inputs']['denominator'], 1)


if __name__ == '__main__':
    unittest.main()
