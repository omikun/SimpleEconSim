"""Exact cash and treatment links for private and public medical care."""

import json
import random
import unittest
from types import SimpleNamespace

from agent import Agent
from disease import DIS_MALNUTRITION, step_medical_care
from goods import Goods


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f"medical-care-test:{clock['next']}"
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, public, traced, self_administered=False):
    patient = Agent(1)
    patient.output = Goods.food
    patient.cash = 60.0
    patient.diseases = [DIS_MALNUTRITION]

    provider = None
    if not self_administered:
        provider = Agent(1)
        provider.output = Goods.furniture
        provider.cash = 40.0

    government = Agent(1)
    government.output = Goods.gov
    government.is_government = True
    government.cash = 100.0

    agents = [patient, *([provider] if provider else []), government]
    nation = SimpleNamespace(name='Medical Nation', currency='USD',
                             unlocked_techs=set())
    nation.treasury = lambda: {'accounts': [
        {'government_id': government.id, 'tier': 'provincial'}]}
    region = SimpleNamespace(
        name='Clinic Ward', agents=agents, gov=SimpleNamespace(agent=government),
        owner_nation=nation, home_currency='USD', public_healthcare_decree=public,
        province=None, buildings=[], disease_fatalities_this_turn=0)
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 4, 'phase': 'healthcare', 'next': 1}
    return region, patient, provider, government, trace


def _run(*, public, traced, self_administered=False):
    fixture = _fixture(public=public, traced=traced,
                       self_administered=self_administered)
    region, _patient, _provider, _government, _trace = fixture
    result = step_medical_care(region, 4, random.Random(18))
    return fixture, result


def _state(fixture, result):
    region, patient, provider, government, _trace = fixture
    return {
        'patient_cash': patient.cash,
        'provider_cash': provider.cash if provider is not None else None,
        'government_cash': government.cash,
        'patient_diseases': list(patient.diseases),
        'patient_treatments': patient.medical_treatments_count,
        'patient_expenses': patient.medical_expenses_paid,
        'region_public_spending': region.medical_spending_public_log[-1],
        'region_private_spending': region.medical_spending_private_log[-1],
        'result': result,
    }


class MedicalCareTraceTests(unittest.TestCase):
    def test_public_payment_links_treasury_provider_and_treatment(self):
        plain, plain_result = _run(public=True, traced=False)
        traced, traced_result = _run(public=True, traced=True)

        self.assertEqual(_state(plain, plain_result), _state(traced, traced_result))
        self.assertEqual(traced[1].cash, 60.0)
        self.assertEqual(traced[2].cash, 60.0)
        self.assertEqual(traced[3].cash, 80.0)

        rows = traced[4].rows
        payment = next(row for row in rows
                       if row.get('kind') == 'medical_care_payment')
        treatment = next(row for row in rows
                         if row.get('kind') == 'medical_treatment')
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(contract['operation_type'], 'medical_care_payment')
        self.assertEqual(contract['payer_account']['balance_before'], 100.0)
        self.assertEqual(contract['payer_account']['balance_after'], 80.0)
        self.assertEqual(contract['payee_account']['balance_before'], 40.0)
        self.assertEqual(contract['payee_account']['balance_after'], 60.0)
        self.assertEqual(treatment['cause_event_ids'], [payment['event_id']])
        self.assertEqual(treatment['inputs']['payer'], 'public')
        self.assertEqual(treatment['inputs']['cash_settlement'],
                         'government_to_provider_cash_transfer')
        self.assertEqual(treatment['inputs']['actor_account_event_id'],
                         payment['inputs']['actor_account_event_id'])
        journal = next(event for event in traced[0].economic_events
                       if event['kind'] == 'medical_care')
        self.assertEqual(journal['source_id'], contract['operation_id'])
        self.assertEqual(journal['amount'], 20.0)

        spending = next(row for row in rows
                        if row.get('kind') == 'public_healthcare_spending')
        self.assertEqual(spending['cause_event_ids'], [payment['event_id']])
        summary = next(row for row in rows
                       if row.get('kind') == 'medical_care_summary')
        self.assertEqual(summary['inputs']['actual_cash_transfer_outflow'], 20.0)
        self.assertEqual(summary['cause_event_ids'], [payment['event_id']])
        treasury_flow = next(row for row in rows
                             if row.get('metric_id') == 'finance.treasury_flow'
                             and row.get('kind') ==
                             'medical_public_provider_payment')
        self.assertEqual(treasury_flow['after'], -20.0)
        self.assertEqual(treasury_flow['subject'],
                         {'type': 'nation', 'id': 'Medical Nation'})

    def test_private_payment_links_patient_provider_and_treatment(self):
        plain, plain_result = _run(public=False, traced=False)
        traced, traced_result = _run(public=False, traced=True)

        self.assertEqual(_state(plain, plain_result), _state(traced, traced_result))
        self.assertEqual(traced[1].cash, 40.0)
        self.assertEqual(traced[2].cash, 60.0)
        self.assertEqual(traced[3].cash, 100.0)

        rows = traced[4].rows
        payment = next(row for row in rows
                       if row.get('kind') == 'medical_care_payment')
        treatment = next(row for row in rows
                         if row.get('kind') == 'medical_treatment')
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(contract['payer_type'], 'private')
        self.assertEqual(contract['payer_account']['balance_before'], 60.0)
        self.assertEqual(contract['payer_account']['balance_after'], 40.0)
        self.assertEqual(contract['payee_account']['balance_before'], 40.0)
        self.assertEqual(contract['payee_account']['balance_after'], 60.0)
        self.assertEqual(treatment['cause_event_ids'], [payment['event_id']])
        self.assertEqual(treatment['inputs']['cash_settlement'],
                         'patient_to_provider_cash_transfer')
        summary = next(row for row in rows
                       if row.get('kind') == 'medical_care_summary')
        self.assertEqual(summary['inputs']['private_transfer_outflow'], 20.0)
        self.assertEqual(summary['inputs']['actual_cash_transfer_outflow'], 20.0)

    def test_government_patient_payment_records_treasury_outflow(self):
        fixture = _fixture(public=False, traced=True)
        region, patient, _provider, government, trace = fixture
        patient.is_government = True
        region.owner_nation.treasury = lambda: {'accounts': [
            {'government_id': patient.id, 'tier': 'municipal'},
            {'government_id': government.id, 'tier': 'provincial'}]}

        step_medical_care(region, 4, random.Random(18))

        flow = next(row for row in trace.rows
                    if row.get('kind') ==
                    'government_medical_patient_payment')
        self.assertEqual(flow['after'], -20.0)
        self.assertEqual(flow['subject'],
                         {'type': 'nation', 'id': 'Medical Nation'})

    def test_self_administered_public_care_does_not_invent_cash_transfer(self):
        fixture, result = _run(public=True, traced=True,
                               self_administered=True)

        rows = fixture[4].rows
        treatment = next(row for row in rows
                         if row.get('kind') == 'medical_treatment')
        summary = next(row for row in rows
                       if row.get('kind') == 'medical_care_summary')
        self.assertFalse(any(row.get('metric_id') == 'finance.cash_transfer'
                             for row in rows))
        self.assertEqual(treatment['inputs']['cash_settlement'],
                         'self_administered_no_net_cash_transfer')
        self.assertIsNone(treatment.get('cause_event_ids'))
        self.assertEqual(summary['inputs']['public_spending'], 20.0)
        self.assertEqual(summary['inputs']['actual_cash_transfer_outflow'], 0.0)
        self.assertEqual(summary['inputs']['non_transfer_treatment_count'], 1)
        self.assertEqual(fixture[3].cash, 100.0)
        self.assertEqual(result['spending_public'], 20.0)


if __name__ == '__main__':
    unittest.main()
