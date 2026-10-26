"""Causal evidence for enclosure enforcement and charter settlements."""

import json
import unittest

from agent import Agent
from enclosure import execute_enclosure
from land_tenure import LandPlot, TenureStatus, TileTenure
from nation import Nation
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'enclosure-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced, protest=4.0, lord_cash=30.0, include_recipient=True):
    nation = Nation('Commonwealth', 'GBP', initial_cash=0.0, register=False)
    tile = Region('Wessex', 0)
    nation.add_tile(tile)
    tile.agents.clear()

    lord = Agent(0)
    lord.cash = float(lord_cash)
    lord.is_lord = True
    tile.agents.append(lord)
    recipient = None
    if include_recipient:
        recipient = Agent(0)
        recipient.cash = 3.0
        tile.agents.append(recipient)

    plot = LandPlot(
        plot_id='feudal-plot', tile_name=tile.name, lord_id=lord.id,
        fraction=0.20, tenure=TenureStatus.FEUDAL)
    tile.tenure = TileTenure(plots=[plot])
    tile.protest_energy_log = [float(protest)]

    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 10, 'phase': 'policy_action', 'next': 1}
    return nation, tile, lord, recipient, plot, trace


def _state(fixture):
    nation, tile, lord, recipient, plot, _trace = fixture
    return {
        'lord_cash': lord.cash,
        'recipient_cash': recipient.cash if recipient else None,
        'government_cash': tile.gov.agent.cash,
        'plot_tenure': plot.tenure.value,
        'plot_rent': plot.rent_rate,
        'commons_access': tile.tenure.commons_access,
        'nation_treasury': nation.government.agent.cash,
    }


class EnclosurePaymentTraceTests(unittest.TestCase):
    def test_bailiff_and_charter_payments_link_to_enclosure_outcome(self):
        baseline = _fixture(traced=False)
        traced = _fixture(traced=True)
        government_cash_before = traced[1].gov.agent.cash

        plain_result = execute_enclosure(baseline[1], baseline[4].plot_id, 10)
        traced_result = execute_enclosure(traced[1], traced[4].plot_id, 10)

        self.assertEqual(traced_result, plain_result)
        self.assertTrue(traced_result[0])
        self.assertEqual(_state(traced), _state(baseline))
        self.assertEqual(_state(traced)['lord_cash'], 10.0)
        self.assertEqual(_state(traced)['recipient_cash'], 13.0)
        self.assertEqual(_state(traced)['government_cash'],
                         government_cash_before + 10.0)
        self.assertEqual(_state(traced)['commons_access'], 0.0)

        rows = traced[5].rows
        decision = next(row for row in rows
                        if row.get('kind') == 'enclosure_bailiff_force_decision')
        self.assertEqual(decision['inputs']['reason_code'], 'bailiff_affordable')
        self.assertTrue(decision['after'])

        bailiff = next(row for row in rows
                       if row.get('kind') == 'bailiff_service')
        charter = next(row for row in rows
                       if row.get('kind') == 'enclosure_charter_fee')
        for payment, payer_before, payee_before in (
                (bailiff, 30.0, 3.0),
                (charter, 20.0, government_cash_before)):
            self.assertEqual(payment['metric_id'], 'finance.cash_transfer')
            contract = payment['inputs']['transfer_contract']
            self.assertEqual(contract['contract_version'], 'cash_transfer.v1')
            self.assertEqual(contract['payer_account']['balance_before'], payer_before)
            self.assertEqual(contract['payer_account']['balance_after'], payer_before - 10.0)
            self.assertEqual(contract['payee_account']['balance_before'], payee_before)
            self.assertEqual(contract['payee_account']['balance_after'], payee_before + 10.0)
            self.assertEqual(payment['inputs']['actor_account_event_id'],
                             next(event['id'] for event in traced[1].economic_events
                                  if event['source_id'] == contract['operation_id']))
        self.assertEqual(bailiff['cause_event_ids'], [decision['event_id']])
        self.assertEqual(charter['cause_event_ids'], [decision['event_id']])

        outcome = next(row for row in rows
                       if row.get('kind') == 'enclosure_charter_granted')
        self.assertEqual(outcome['metric_id'], 'land.enclosure_transition')
        self.assertEqual(outcome['before'], 'feudal')
        self.assertEqual(outcome['after'], 'enclosed')
        self.assertEqual(outcome['cause_event_ids'],
                         [decision['event_id'], bailiff['event_id'],
                          charter['event_id']])

    def test_unaffordable_bailiff_records_defied_gate_without_transfer(self):
        baseline = _fixture(traced=False, lord_cash=15.0)
        traced = _fixture(traced=True, lord_cash=15.0)

        plain_result = execute_enclosure(baseline[1], baseline[4].plot_id, 10)
        traced_result = execute_enclosure(traced[1], traced[4].plot_id, 10)

        self.assertEqual(traced_result, plain_result)
        self.assertFalse(traced_result[0])
        self.assertEqual(_state(traced), _state(baseline))
        self.assertEqual(traced[2].cash, 15.0)
        self.assertEqual(traced[4].tenure, TenureStatus.FEUDAL)

        rows = traced[5].rows
        self.assertFalse(any(row.get('metric_id') == 'finance.cash_transfer'
                             for row in rows))
        decision = next(row for row in rows
                        if row.get('kind') == 'enclosure_bailiff_force_decision')
        self.assertFalse(decision['after'])
        self.assertEqual(decision['inputs']['reason_code'],
                         'insufficient_cash_for_bailiff')
        outcome = next(row for row in rows
                       if row.get('kind') == 'enclosure_attempt_outcome')
        self.assertFalse(outcome['inputs']['success'])
        self.assertEqual(outcome['cause_event_ids'], [decision['event_id']])

    def test_government_receives_bailiff_payment_when_no_private_recipient_exists(self):
        fixture = _fixture(traced=True, include_recipient=False)
        opening_government_cash = fixture[1].gov.agent.cash

        ok, _message, _events = execute_enclosure(
            fixture[1], fixture[4].plot_id, 10)

        self.assertTrue(ok)
        bailiff = next(row for row in fixture[5].rows
                       if row.get('kind') == 'bailiff_service')
        contract = bailiff['inputs']['transfer_contract']
        self.assertEqual(contract['payee_account']['type'], 'government_wallet')
        self.assertEqual(contract['payee_account']['balance_before'],
                         opening_government_cash)
        self.assertEqual(contract['payee_account']['balance_after'],
                         opening_government_cash + 10.0)
        self.assertEqual(fixture[1].gov.agent.cash,
                         opening_government_cash + 20.0)


if __name__ == '__main__':
    unittest.main()
