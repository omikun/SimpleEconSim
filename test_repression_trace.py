import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from nation import Nation
from region import Region
from unrest import apply_repression


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, force=True):
    nation = Nation('Test Nation', 'TST')
    nation.legitimacy = 0.6
    tile = Region('Mill District', 0)
    tile.owner_nation = nation
    nation.tiles = [tile]
    nation.capital = tile
    tile.protest_energy_log = [4.0]
    tile.police_employed = 2 if force else 0
    tile.military_units = []
    person = Agent(17)
    initialize_agent(person, Goods.food, 0, 0, 1.0)
    person.id = 17
    person.memory = {}
    tile.agents = [person]
    faction = SimpleNamespace(membership=[person.id], grievances={'taxes': 0.8})
    tile.factions = SimpleNamespace(factions={'workers': faction})
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 3, 'phase': 'policy_action', 'next': 1}
    return nation, tile, person, faction, trace


class RepressionTraceTests(unittest.TestCase):
    def test_force_use_records_effects_and_memory_targets(self):
        nation, tile, person, _faction, trace = _fixture()

        seeded = apply_repression(tile, 3)

        self.assertEqual(seeded, 1)
        event = next(row for row in trace.rows
                     if row.get('kind') == 'repression_resolved')
        self.assertEqual(event['metric_id'], 'politics.repression')
        self.assertEqual(event['inputs']['outcome'], 'repressed')
        self.assertEqual(event['inputs']['police_employed'], 2)
        self.assertEqual(event['inputs']['legitimacy_before'], 0.6)
        self.assertAlmostEqual(event['inputs']['legitimacy_after'], 0.45)
        self.assertEqual(event['inputs']['protest_energy_before'], 4.0)
        self.assertEqual(event['inputs']['protest_energy_after'], 2.0)
        self.assertEqual(event['inputs']['faction_grievance_total_before'], 0.8)
        self.assertEqual(event['inputs']['faction_grievance_total_after'], 0.4)
        self.assertEqual(event['inputs']['seeded_agent_ids'], ['17'])
        self.assertEqual(person.memory['mem_casualties'], [1.0])
        self.assertAlmostEqual(nation.legitimacy, 0.45)

    def test_missing_force_records_failed_attempt_without_effect(self):
        nation, tile, _person, _faction, trace = _fixture(force=False)

        seeded = apply_repression(tile, 3)

        self.assertEqual(seeded, 0)
        event = next(row for row in trace.rows
                     if row.get('kind') == 'repression_resolved')
        self.assertEqual(event['inputs']['outcome'], 'no_force_available')
        self.assertEqual(event['inputs']['legitimacy_before'], 0.6)
        self.assertEqual(event['inputs']['legitimacy_after'], 0.6)
        self.assertEqual(event['inputs']['protest_energy_before'], 4.0)
        self.assertEqual(event['inputs']['protest_energy_after'], 4.0)
        self.assertEqual(nation.legitimacy, 0.6)

    def test_tracing_does_not_change_repression_results(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        plain_count = apply_repression(plain[1], 3)
        traced_count = apply_repression(traced[1], 3)

        def state(fixture):
            nation, tile, person, faction, _trace = fixture
            return (nation.legitimacy, tuple(tile.protest_energy_log),
                    person.memory, dict(faction.grievances))

        self.assertEqual(plain_count, traced_count)
        self.assertEqual(state(plain), state(traced))


if __name__ == '__main__':
    unittest.main()
