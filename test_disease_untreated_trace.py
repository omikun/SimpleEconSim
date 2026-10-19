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
