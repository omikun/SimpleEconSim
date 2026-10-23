"""Trace patient-level reasons behind the untreated-cases chart."""

import random
import tempfile
import unittest
from pathlib import Path

from agent import Agent, initialize_agent
from disease import DIS_RESPIRATORY, step_medical_care
from goods import Goods
from region import Region
from run_trace import RunTrace


class TestUntreatedDiseaseTrace(unittest.TestCase):
    def test_cured_case_history_and_closing_live_count_are_distinct(self):
        from trace_snapshots import sample,record
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            region=Region('Cure timing',0,number_of_agents=0)
            patient=Agent(0);initialize_agent(patient,Goods.wood,0,5,100)
            patient.diseases=[DIS_RESPIRATORY];region.agents=[patient]
            trace=RunTrace(Path(tmp)/'cure.ctr','cure')
            region._run_trace=trace
            region._collective_trace_clock={'turn':1,'phase':'healthcare','next':1}
            step_medical_care(region,1,rand_gen=random.Random(1))
            self.assertNotIn(DIS_RESPIRATORY,patient.diseases)
            self.assertEqual(1,region.disease_cases_log[-1][DIS_RESPIRATORY])
            values=sample([region],[])
            self.assertEqual(1,values[('health.disease_cases',region.name,DIS_RESPIRATORY)][2])
            self.assertEqual(0,values[('health.active_disease_cases',region.name,DIS_RESPIRATORY)][2])
            record(SimpleNamespace(tiles=[region],nations=[],run_trace=trace,_trace_previous={}))
            rows=trace.query(metric_id='health.active_disease_cases',subject={'disease':DIS_RESPIRATORY})['events']
            census=next(row for row in rows if row['kind']=='closing_active_disease_census')
            self.assertEqual([],census['inputs']['case_agent_ids'])
            self.assertTrue(census['formula_replay']['matches'])

    def test_unaffordable_case_is_linked_to_aggregate_chart_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            region = Region('Medical_Trace_Tile', 1)
            patient = Agent(701)
            initialize_agent(patient, Goods.wood, 0, 5, 5.0)
            patient.diseases = [DIS_RESPIRATORY]
            doctor = Agent(702)
            initialize_agent(doctor, Goods.furniture, 0, 5, 100.0)
            region.agents = [patient, doctor]
            region.public_healthcare_decree = False

            trace = RunTrace(Path(tmp) / 'medical.ctr', 'medical-fixture')
            region._run_trace = trace
            region._collective_trace_clock = {
                'next': 1, 'turn': 1, 'phase': 'healthcare'}

            result = step_medical_care(region, 1, rand_gen=random.Random(1))

            self.assertEqual(result['untreated'], 1)
            summary = trace.query(
                turn=1,
                subject={'type': 'tile', 'id': region.name},
                metric_id='health.untreated_cases')['events']
            calculation = next(
                row for row in summary
                if row['kind'] == 'disease_untreated_cases_observed')
            patient_row = calculation['inputs']['untreated_patients'][0]
            self.assertEqual(calculation['value_after'], 1)
            self.assertEqual(calculation['inputs']['replay_count'], 1)
            self.assertEqual(patient_row['patient_id'], patient.id)
            self.assertEqual(patient_row['patient_cash'], 5.0)
            self.assertEqual(patient_row['reason'], 'unaffordable')
            self.assertEqual(calculation['cause_event_ids'], [patient_row['event_id']])

            unaffordable = trace.query(event_id=patient_row['event_id'])['events'][0]
            self.assertEqual(unaffordable['kind'], 'medical_treatment_unaffordable')
            self.assertEqual(unaffordable['inputs']['treatment_cost'],
                             patient_row['treatment_cost'])


if __name__ == '__main__':
    unittest.main()
