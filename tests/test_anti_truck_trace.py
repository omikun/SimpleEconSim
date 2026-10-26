import json
import unittest
from types import SimpleNamespace

from agent import Agent
from faction import Faction
from labor_politics import enact_anti_truck_act
from metric_catalog import METRICS, TRACE_INSTRUMENTED


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True):
    factions = {
        name: Faction(name, 'class')
        for name in ('Labor', 'Peasant', 'Commoners', 'Bourgeoisie')
    }
    for faction in factions.values():
        faction.support = 0.5
        faction.grievances['truck_system'] = 3.0

    tile = SimpleNamespace(name='Test Parish', home_currency='GBP',
                           _last_turn=4, truck_act_enacted=False,
                           agents=[], economic_events=[],
                           factions=SimpleNamespace(factions=factions))
    corporation = Agent(0)
    corporation.is_corporation = True
    corporation.pay_mode = 'scrip'
    worker = Agent(1)
    worker.company_debt = 25.0
    worker.despair = 0.1
    worker.employer = corporation
    tile.agents = [corporation, worker]
    target = SimpleNamespace(name='Testland', tiles=[tile],
                             truck_act_enacted=False)

    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 4, 'phase': 'policy_action', 'next': 1}
    return target, tile, corporation, worker, factions, trace


def _state(fixture):
    target, tile, corporation, worker, factions, _trace = fixture
    return {
        'nation_law': target.truck_act_enacted,
        'tile_law': tile.truck_act_enacted,
        'pay_mode': corporation.pay_mode,
        'debt': worker.company_debt,
        'despair': worker.despair,
        'faction_support': {name: faction.support
                            for name, faction in factions.items()},
        'truck_grievance': {name: faction.grievances['truck_system']
                            for name, faction in factions.items()},
    }


class AntiTruckTraceTests(unittest.TestCase):
    def test_enactment_traces_law_debt_payment_mode_and_faction_effects(self):
        traced = _fixture()
        plain = _fixture(traced=False)

        self.assertEqual(enact_anti_truck_act(traced[0]),
                         enact_anti_truck_act(plain[0]))
        self.assertEqual(_state(traced), _state(plain))
        self.assertEqual(traced[2].pay_mode, 'cash')
        self.assertEqual(traced[3].company_debt, 0.0)
        self.assertEqual(traced[3].despair, 0.0)
        self.assertAlmostEqual(traced[4]['Labor'].support, 0.65)
        # Faction.add_grievance intentionally ignores negative requests today.
        self.assertEqual(traced[4]['Labor'].grievances['truck_system'], 3.0)

        decision = self._row(traced, 'anti_truck_act_decision')
        debt = self._row(traced, 'company_store_debt_cancelled')
        payment_mode = self._row(traced, 'anti_truck_payment_mode_outcome')
        despair = self._row(traced, 'anti_truck_despair_outcome')
        grievance = self._row(traced, 'anti_truck_grievance_outcome')
        outcome = self._row(traced, 'anti_truck_act_outcome')
        self.assertEqual(debt['cause_event_ids'], [decision['event_id']])
        self.assertEqual(payment_mode['before'], 'scrip')
        self.assertEqual(payment_mode['after'], 'cash')
        self.assertEqual(despair['before'], 0.1)
        self.assertEqual(despair['after'], 0.0)
        self.assertEqual(grievance['inputs']['requested_grievance_change'], -2.0)
        self.assertEqual(grievance['inputs']['actual_grievance_change'], 0.0)
        self.assertFalse(grievance['inputs']['negative_adjustment_accepted'])
        self.assertEqual(outcome['inputs']['company_debt_discharged'], 25.0)
        self.assertEqual(outcome['inputs']['peons_freed'], 1)

        for row in traced[5].rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)

    def _row(self, fixture, kind):
        return next(row for row in fixture[5].rows
                    if row.get('kind') == kind)


if __name__ == '__main__':
    unittest.main()
