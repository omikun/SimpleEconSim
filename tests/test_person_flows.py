"""Person conservation and death recording invariants."""

import unittest
from types import SimpleNamespace

from collections import Counter

from benchmark_career_mobility import (compare_people, entity_roles, snapshot,
                                       unmatched_event_balance)
from person_death import record_person_death


def person(identifier, *, born=0):
    return SimpleNamespace(
        id=identifier, alive=True, is_corporation=False,
        is_government=False, is_native_child=False, birth_round=born,
        output=SimpleNamespace(name='food'), employer=None,
        age=lambda turn: turn - born)


def tile(name, owner, agents):
    return SimpleNamespace(name=name, owner_nation=owner, agents=agents)


class PersonFlowsTests(unittest.TestCase):
    def test_migration_and_death_reconcile_without_phantom_exit(self):
        owner = SimpleNamespace(name='A')
        migrant = person(1)
        victim = person(2)
        home = tile('home', owner, [migrant, victim])
        frontier = tile('frontier', None, [])
        world = SimpleNamespace(tiles=[home, frontier])
        before = snapshot(world, 0)
        home.agents.remove(migrant)
        frontier.agents.append(migrant)
        record_person_death(home, victim, 1, 'combat')
        after = snapshot(world, 1)
        flows, unknown = compare_people(before, after, world, 1,
                                        {1: 'person', 2: 'person'})
        self.assertFalse(unknown)
        self.assertEqual(flows['A']['deaths_combat'], 1)
        self.assertEqual(flows['A']['departures'], 1)
        self.assertEqual(flows['Unclaimed']['arrivals'], 1)

    def test_role_conversion_is_not_death(self):
        founder = person(3)
        home = tile('home', SimpleNamespace(name='A'), [founder])
        world = SimpleNamespace(tiles=[home])
        before = snapshot(world, 0)
        prior_roles = entity_roles(world)
        founder.is_corporation = True
        after = snapshot(world, 1)
        flows, unknown = compare_people(before, after, world, 1, prior_roles)
        self.assertFalse(unknown)
        self.assertEqual(flows['A']['role_conversions_out'], 1)
        self.assertEqual(flows['A']['deaths'], 0)

    def test_death_is_recorded_once(self):
        victim = person(4)
        home = tile('home', None, [victim])
        self.assertTrue(record_person_death(home, victim, 2, 'state_violence'))
        self.assertFalse(record_person_death(home, victim, 2, 'state_violence'))
        self.assertEqual(home.deaths_this_turn, 1)
        self.assertEqual(home.deaths_by_cause_this_turn, {'state_violence': 1})

    def test_duplicate_person_id_fails(self):
        world = SimpleNamespace(tiles=[tile('a', None, [person(5)]),
                                       tile('b', None, [person(5)])])
        with self.assertRaisesRegex(AssertionError, 'duplicate living person'):
            snapshot(world, 0)

    def test_same_turn_birth_and_death_balance_without_snapshot_presence(self):
        self.assertEqual(unmatched_event_balance({}, 1, 1), 0)
        self.assertEqual(unmatched_event_balance({'A': Counter(birth=1)}, 2, 1), 0)


if __name__ == '__main__':
    unittest.main()
