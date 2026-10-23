"""History provenance must survive later cash changes and delayed sampling."""
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest

from agent import Agent, initialize_agent
from causal_contracts import validate
from disease import step_medical_care
from goods import Goods
from region import Region
from run_trace import RunTrace


class NativeHistoryTraceTests(unittest.TestCase):
    def fixture(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        tile = Region('Native history', 0, number_of_agents=0)
        trace = RunTrace(Path(directory.name) / 'history.ctr', 'history')
        tile._run_trace = trace
        tile._collective_trace_clock = {'turn': 10, 'phase': 'local', 'next': 1}
        return tile, trace

    def person(self, cash):
        person = Agent(0)
        initialize_agent(person, Goods.food, 0, 0, cash)
        return person

    def test_gini_keeps_writer_inputs_when_members_and_cash_later_change(self):
        from gini_trace import record_sample
        from micro.region.helpers import compute_gini
        from trace_snapshots import record
        tile, trace = self.fixture()
        tile.agents = [self.person(10), self.person(30)]
        history = tile.gini_log[Goods.food]
        history.append(compute_gini(tile.agents, Goods.food))
        record_sample(tile, tile.agents, Goods.food, 10, history)
        source = trace.query(kind='gini_series_calculation')['events'][0]
        tile.agents[0].cash = 100
        tile.agents.append(self.person(70))
        record(SimpleNamespace(tiles=[tile], nations=[], run_trace=trace,
                               _trace_previous={}))
        snapshots = trace.query(kind='metric_snapshot', metric_id='economy.gini',
                                subject={'good': 'food'})['events']
        self.assertEqual(source['event_id'], snapshots[-1]['inputs']['source_event_id'])
        self.assertEqual([10, 30], [p['cash'] for p in source['inputs']['members_sorted_by_cash']])
        tile._collective_trace_clock['turn'] = 11
        history.append(history[-1])
        record_sample(tile, tile.agents, Goods.food, 11, history)
        held = trace.query(turn=11, kind='gini_series_calculation')['events'][0]
        self.assertEqual([source['event_id']], held['cause_event_ids'])
        self.assertTrue(held['formula_replay']['matches'])

    def test_disease_death_is_linked_across_turns_and_counter_reset(self):
        from health_trace import remember_fatality
        tile, trace = self.fixture()
        person = self.person(0)
        tile.agents = []  # The death has already been probated and removed.
        source = trace.emit(tile._collective_trace_clock,
                            kind='mortality_assessment', record_class='outcome',
                            subject={'type': 'tile', 'id': tile.name, 'agent_id': person.id},
                            metric_id='health.mortality_risk', after=.35,
                            inputs={'death_draw': .2, 'probability_without_disease': .001,
                                    'active_diseases': ['pestilence'], 'died': True,
                                    'disease_attributed_by_threshold_crossing': True})
        remember_fatality(tile, person, 10, source, .2, .001, .35, ['pestilence'])
        tile.disease_fatalities_this_turn = 1
        tile._collective_trace_clock['turn'] = 11
        step_medical_care(tile, 11, rand_gen=random.Random(1))
        result = trace.query(turn=11, kind='disease_fatalities_observed')['events'][0]
        self.assertEqual(1, result['value_after'])
        self.assertEqual([source], result['cause_event_ids'])
        self.assertTrue(result['formula_replay']['matches'])
        lookup = lambda ident: trace.query(event_id=ident)['events'][0]
        self.assertTrue(validate(result, lookup)['matches'])
        result['cause_event_ids'] = []
        self.assertFalse(validate(result, lookup)['matches'])
        self.assertEqual(0, tile.disease_fatalities_this_turn)
        tile._collective_trace_clock['turn'] = 12
        step_medical_care(tile, 12, rand_gen=random.Random(1))
        closing = trace.query(turn=12, kind='disease_fatalities_observed')['events'][0]
        self.assertEqual([], closing['inputs']['fatalities'])
        self.assertEqual(0, closing['value_after'])

    def test_missing_positive_fatality_contributor_remains_a_replay_gap(self):
        tile, trace = self.fixture()
        tile.disease_fatalities_this_turn = 1
        step_medical_care(tile, 10, rand_gen=random.Random(1))
        result = trace.query(kind='disease_fatalities_observed')['events'][0]
        self.assertFalse(result['formula_replay']['matches'])

    def test_wilderness_output_and_gdp_use_this_turns_actual_food_receipts(self):
        from wilderness import step_wilderness
        from trace_audit import audit
        tile, trace = self.fixture()
        tile.wilderness = True
        person = self.person(0)
        person.is_homesteader = True
        person.last_forage_turn = 7
        tile.agents = [person]
        step_wilderness(tile, 10)
        production = trace.query(kind='wilderness_food_production')['events'][0]
        self.assertEqual(1, production['value_after'])
        self.assertEqual(1, tile.production_log[Goods.food][-1])
        receipt = trace.query(event_id=production['cause_event_ids'][0])['events'][0]
        self.assertEqual(person.id, receipt['inputs']['agent_id'])
        self.assertEqual(1, receipt['value_after'])
        self.assertTrue(audit(trace.path)['structural_and_supported_formula_checks_pass'])


if __name__ == '__main__':
    unittest.main()
