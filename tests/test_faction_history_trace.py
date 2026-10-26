"""Faction chart histories retain their real support and grievance timing."""

from copy import deepcopy
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest

from agent import Agent, initialize_agent
from faction import Faction, FactionSystem
from goods import Goods
from region import Region
from region_factions import step_factions
from run_trace import RunTrace
from trace_snapshots import sample


def _fixture(trace=None):
    region = Region('Parish', 0, number_of_agents=0)
    region.agents = []
    for ident, social_class in ((1, 'tenant'), (2, 'industrialist')):
        person = Agent(0)
        person.id = ident
        initialize_agent(person, Goods.food, 0, 4, 10.0)
        person.social_class = social_class
        person.politics = 'liberal'
        person.religion = 'sol'
        person.ethnicity = 'yor'
        person.employer = None
        region.agents.append(person)
    region.tenure = SimpleNamespace(commons_access=0.4)
    region.gov.tax_rate = 0.25
    region.gov.ubi_enabled = False
    region.compromise_concessions = {'welfare'}
    region.factions = FactionSystem()
    peasantry = Faction('Peasantry', 'class', membership={99}, support=0.2,
                       grievances={'legacy': 2.0, 'tiny': 1e-5})
    peasantry.add_demand('commons_protection', 1.5)
    peasantry.add_demand('welfare', 1.0)
    liberal = Faction('Liberal', 'political')
    liberal.add_demand('tax_cut', 2.0)
    liberal.add_demand('welfare', 1.0)
    absent = Faction('Absent', 'religion', membership={99}, support=0.7)
    absent.add_demand('custom', 1.0, 0.6)
    for faction in (peasantry, liberal, absent):
        region.factions.register(faction)
    if trace is not None:
        region._run_trace = trace
        region._collective_trace_clock = {'turn': 1, 'phase': 'politics', 'next': 1}
    return region


def _state(region):
    return ([(name, faction.support, deepcopy(faction.grievances),
              set(faction.membership), deepcopy(faction.demands))
             for name, faction in region.factions.factions.items()],
            deepcopy(region.faction_support_log), deepcopy(region.faction_grievance_log),
            deepcopy(region.grievance_sources_log), list(region.protest_energy_log))


class FactionHistoryTraceTests(unittest.TestCase):
    def test_histories_replay_membership_policy_and_pre_decay_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'factions.ctr', 'factions')
            traced, plain = _fixture(trace), _fixture()
            before_random = random.getstate()
            step_factions(traced, 1)
            step_factions(plain, 1)
            self.assertEqual(_state(traced), _state(plain))
            self.assertEqual(random.getstate(), before_random)
            rows = [row for row in trace.recent if row.get('kind') in (
                'faction_support_history_calculation', 'faction_grievance_history_calculation')]
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(row['formula_replay']['matches'] for row in rows))
            support = next(row for row in rows if row['metric_id'] == 'politics.faction_support'
                           and row['subject']['id'] == 'Peasantry')
            self.assertEqual(support['inputs']['added_member_ids'], [1])
            self.assertEqual(support['inputs']['removed_member_ids'], [99])
            self.assertEqual(support['inputs']['eligible_agent_ids'], [1, 2])
            self.assertAlmostEqual(sum(support['inputs']['grievances_before_decay'].values()),
                                   3.25001)
            self.assertEqual(support['inputs']['demands'][1]['satisfied'], 0.85)
            grievance = next(row for row in rows if row['metric_id'] == 'politics.faction_grievance'
                             and row['subject']['id'] == 'Peasantry')
            self.assertAlmostEqual(grievance['value_after'], 3.0875)
            self.assertNotIn('tiny', grievance['inputs']['sources_after_decay'])
            self.assertTrue(support['cause_event_ids'])
            absent = next(row for row in rows if row['metric_id'] == 'politics.faction_support'
                          and row['subject']['id'] == 'Absent')
            self.assertEqual(absent['value_after'], 0.7)
            self.assertEqual(absent['inputs']['reason'], 'retained_no_eligible_members')
            values = sample([traced], [])
            for row in rows:
                subject = row['subject']
                key = (row['metric_id'], traced.name, subject['id'], subject['history_field'])
                self.assertEqual(values[key][2], row['value_after'])

    def test_empty_population_records_retained_support_and_grievance_decay(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'empty.ctr', 'empty')
            region = _fixture(trace)
            region.agents = []
            step_factions(region, 1)
            rows = [row for row in trace.recent
                    if row.get('kind') == 'faction_support_history_calculation']
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row['inputs']['reason'] == 'retained_no_eligible_agents' for row in rows))
            self.assertTrue(all(row['formula_replay']['matches'] for row in rows))
            self.assertEqual(region.faction_support_log[-1]['Peasantry'], 0.2)
            self.assertAlmostEqual(region.faction_grievance_log[-1]['Peasantry'], 1.9)

    def test_support_bounds_and_history_remain_distinct_from_later_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            for index, grievance in enumerate((0.0, 100.0)):
                trace = RunTrace(Path(tmp) / f'bounds-{index}.ctr', f'bounds-{index}')
                region = _fixture(trace)
                faction = region.factions.get('Peasantry')
                faction.demands.clear()
                faction.add_demand('custom', 1.0, 10.0)
                faction.grievances = {'legacy': grievance}
                step_factions(region, 1)
                expected = 1.0 if grievance == 0 else 0.0
                self.assertEqual(region.faction_support_log[-1]['Peasantry'], expected)
                row = next(row for row in trace.recent
                           if row.get('kind') == 'faction_support_history_calculation'
                           and row['subject']['id'] == 'Peasantry')
                self.assertTrue(row['formula_replay']['matches'])
                faction.support = 0.4
                trace.emit(region._collective_trace_clock, kind='policy_support_change',
                           record_class='outcome',
                           subject={'type': 'tile/faction', 'id': faction.name, 'tile': region.name},
                           metric_id='politics.faction_support', after=0.4)
                trace.snapshot(region._collective_trace_clock, subject=row['subject'],
                               metric_id='politics.faction_support', unit='ratio',
                               before=None, after=expected)
                self.assertEqual(trace.recent[-1]['explanation_status'], 'calculation_recorded')


if __name__ == '__main__':
    unittest.main()
