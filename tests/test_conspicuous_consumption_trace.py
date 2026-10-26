import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from economy.conspicuous_consumption import (
    ConspicuousConsumptionManager,
    PrestigeTier,
)
from goods import Goods
from run_trace import RunTrace, verify


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, prestige=0.0, luxury_stock=2, porcelain_stock=1):
    region = SimpleNamespace(
        name='Cotton District',
        goods=[Goods.foreign_luxuries, Goods.porcelain])
    agent = Agent(501)
    initialize_agent(agent, Goods.food, 0, 0, 0.0)
    agent.id = 501
    agent.is_lord = True
    agent.prestige_score = prestige
    agent.inv_set(Goods.foreign_luxuries, luxury_stock)
    agent.inv_set(Goods.porcelain, porcelain_stock)
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 7, 'phase': 'scenario_economy', 'next': 1}
    return region, agent, trace


class ConspicuousConsumptionTraceTests(unittest.TestCase):
    def test_consumption_and_prestige_link_with_diminishing_gain(self):
        traced = _fixture()
        plain = _fixture(traced=False)

        traced_result = ConspicuousConsumptionManager.consume_luxuries_for_agent(
            traced[1], traced[0], t=7)
        plain_result = ConspicuousConsumptionManager.consume_luxuries_for_agent(
            plain[1], plain[0], t=7)

        self.assertEqual(traced_result, plain_result)
        self.assertEqual(traced[1].prestige_score, plain[1].prestige_score)
        self.assertEqual(traced[1].status_tier, PrestigeTier.BURGHER)
        self.assertEqual(traced[1].inv_get(Goods.foreign_luxuries, 0), 1)
        self.assertEqual(traced[1].inv_get(Goods.porcelain, 0), 0)

        consumption = [row for row in traced[2].rows
                       if row.get('kind') == 'elite_luxury_consumption']
        prestige = next(row for row in traced[2].rows
                        if row.get('kind') == 'elite_prestige_update')
        self.assertEqual(len(consumption), 2)
        self.assertEqual(
            {row['subject']['good']: (row['before'], row['after'])
             for row in consumption},
            {'foreign_luxuries': (2, 1), 'porcelain': (1, 0)})
        self.assertEqual(prestige['formula_id'], 'prestige.luxury_gain.v1')
        self.assertEqual(prestige['before'], 0.0)
        self.assertEqual(prestige['after'], 33.0)
        self.assertEqual(prestige['inputs']['status_tier_before'],
                         PrestigeTier.PROVINCIAL)
        self.assertEqual(prestige['inputs']['status_tier_after'],
                         PrestigeTier.BURGHER)
        calculations = prestige['inputs']['prestige_calculations']
        self.assertEqual(calculations[0]['prestige_gain'], 25.0)
        self.assertEqual(calculations[1]['prestige_before'], 25.0)
        self.assertEqual(calculations[1]['saturation_multiplier'], 0.6666666666666666)
        self.assertEqual(calculations[1]['prestige_gain'], 8.0)
        self.assertEqual(prestige['cause_event_ids'],
                         [row['event_id'] for row in consumption])

    def test_empty_luxury_holdings_explain_prestige_decay(self):
        region, agent, trace = _fixture(
            prestige=0.2, luxury_stock=0, porcelain_stock=0)

        result = ConspicuousConsumptionManager.consume_luxuries_for_agent(
            agent, region, t=7)

        self.assertEqual(result['current_score'], 0.0)
        event = next(row for row in trace.rows
                     if row.get('kind') == 'elite_prestige_decay')
        self.assertEqual(event['formula_id'], 'prestige.no_luxury_decay.v1')
        self.assertEqual((event['before'], event['after']), (0.2, 0.0))
        self.assertEqual(event['inputs']['decay_applied'], 0.2)
        self.assertEqual(event['inputs']['eligible_luxury_holdings'], [
            {'good': 'foreign_luxuries', 'held_units': 0},
            {'good': 'porcelain', 'held_units': 0},
        ])
        self.assertEqual(event['inputs']['status_tier_after'],
                         PrestigeTier.PROVINCIAL)
        self.assertIsNone(event['cause_event_ids'])

    def test_empty_unprestigious_agent_does_not_emit_noise(self):
        region, agent, trace = _fixture(
            prestige=0.0, luxury_stock=0, porcelain_stock=0)

        ConspicuousConsumptionManager.consume_luxuries_for_agent(
            agent, region, t=7)

        self.assertEqual(trace.rows, [])

    def test_prestige_events_round_trip_through_compact_trace_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'prestige.ctr'
            trace = RunTrace(path, 'prestige-fixture')
            region, agent, _memory_trace = _fixture(traced=False)
            region._run_trace = trace
            region._collective_trace_clock = {
                'turn': 7, 'phase': 'scenario_economy', 'next': 1}

            ConspicuousConsumptionManager.consume_luxuries_for_agent(
                agent, region, t=7)

            decoded = trace.query(metric_id='society.elite_prestige')
            self.assertEqual(decoded['total'], 1)
            self.assertEqual(decoded['events'][0]['inputs']['outcome'],
                             'luxury_gain')
            self.assertEqual(verify(path)['rows'], trace.count)


if __name__ == '__main__':
    unittest.main()
