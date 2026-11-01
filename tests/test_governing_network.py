"""Material observation, sparse diffusion and isolation from live campaign state."""

from copy import deepcopy
import json
import random
from types import SimpleNamespace
import unittest

from goods import Goods
import governing_network as network


class Person(SimpleNamespace):
    def inv_get(self, good, default=0):
        return self.inventory.get(good, default)


def fixture():
    def person(pid, deficit=0, **roles):
        return Person(id=pid, alive=True, cash=5., inventory={Goods.food: 4},
                      calorie_deficit_kcal=2000 * deficit, calorie_need_kcal=2000,
                      energy_reserve_kcal=40000., is_striking=False, **roles)
    a = SimpleNamespace(name='a', scenario_location='Upper Egypt',
                        agents=[person(1, .8), person(2), person(3, is_lord=True),
                                person(4, is_trader=True)], gov=SimpleNamespace(tax_rate=.1))
    b = SimpleNamespace(name='b', scenario_location='Cairo',
                        agents=[person(5), person(6, is_trader=True)],
                        gov=SimpleNamespace(tax_rate=.1))
    nation = SimpleNamespace(name='Egypt', tiles=[a, b],
                             government=SimpleNamespace(agent=SimpleNamespace(cash=235.),
                                                        food_inventory=440))
    collective = dict(petitioners=1, strikers=0, mutual_aid_meals=0)
    return dict(scenario_id='egypt_1877', turn=1, nations=[nation], tiles=[a, b],
                scenario_state=dict(actions_taken=[], political_economy=dict(
                    warehouse_by_tile={'a': 3, 'b': 6}, grain_policy='hold',
                    private_reserve_by_tile={'a': 100, 'b': 3},
                    collective_by_tile={'a': collective.copy(), 'b': collective.copy()},
                    arrears={1: {'balance': 9.}}, grain_transactions=[])))


def authoritative(world):
    state = deepcopy(world)
    state['scenario_state'].pop(network.KEY, None)
    return state


class GoverningNetworkTests(unittest.TestCase):
    def test_off_keeps_old_save_untouched(self):
        world = fixture()
        before = deepcopy(world)
        network.initialize(world, 'off')
        network.advance(world)
        self.assertEqual(world, before)
        self.assertEqual(network.mode(world), 'off')
        self.assertIsNone(network.project(world))

    def test_observing_changes_no_actor_store_collective_or_rng(self):
        world = fixture()
        before = authoritative(world)
        from random_cache import rand
        rng = random.getstate()
        cached_rng = (rand._idx, rand._seed, rand._buf.copy())
        network.initialize(world, 'observe')
        self.assertEqual(before, authoritative(world))
        self.assertEqual(world['scenario_state']['political_economy']['private_reserve_by_tile']['a'], 100)
        world['turn'] = 2
        before['turn'] = 2
        network.advance(world)
        self.assertEqual(before, authoritative(world))
        self.assertEqual(rng, random.getstate())
        self.assertEqual(cached_rng, (rand._idx, rand._seed, rand._buf))

    def test_membership_overlaps_without_double_counting_real_people(self):
        world = fixture()
        # The warehouse owner is also a merchant; one person appears in both
        # views, without gaining a second body or being counted twice in either.
        world['tiles'][0].agents.append(world['tiles'][0].agents[0])
        network.initialize(world, 'observe')
        summary = network.project(world)['communities']
        self.assertEqual(summary[0]['member_ids'], [1, 2, 5])
        self.assertEqual(summary[1]['member_ids'], [3, 6])
        self.assertEqual(summary[2]['member_ids'], [4, 6])
        self.assertEqual(summary[0]['underfed'], 1)
        self.assertEqual(summary[0]['arrears'], 9.)

    def test_demand_observes_delivery_not_a_selected_policy_label(self):
        world = fixture()
        network.initialize(world, 'observe')
        world['scenario_state']['actions_taken'].append({'id': 'release_maize', 'turn': 1})
        world['turn'] = 2
        network.advance(world)
        self.assertEqual(network.project(world)['communities'][0]['underfed'], 1)
        world['tiles'][0].agents[0].calorie_deficit_kcal = 0
        world['scenario_state']['political_economy']['arrears'][1]['balance'] = 0
        world['turn'] = 3
        network.advance(world)
        household = network.project(world)['communities'][0]
        self.assertEqual(household['underfed'], 0)
        self.assertEqual(household['arrears'], 0)
        self.assertIn('No current', household['explanation'])

    def test_purchase_does_not_become_a_meal_and_seizure_has_distinct_source(self):
        world = fixture()
        econ = world['scenario_state']['political_economy']
        econ['grain_transactions'] = [dict(turn=1, tile='a', kind='public_buy', units=4, cash=4.)]
        network.initialize(world, 'observe')
        self.assertEqual(network.project(world)['communities'][0]['underfed'], 1)
        self.assertEqual(network.project(world)['communities'][1]['requisitioned'], 0)
        econ['grain_transactions'].append(dict(turn=2, tile='a', kind='requisition', units=4, cash=0.))
        world['turn'] = 2
        network.advance(world)
        row = world['scenario_state'][network.KEY]['history'][-1]
        self.assertGreater(row['inputs']['a:holders']['sources']['property'], 0)
        self.assertEqual(network.project(world)['communities'][1]['requisitioned'], 4)

    def test_snapshot_stays_frozen_between_turns_and_update_is_idempotent(self):
        world = fixture()
        network.initialize(world, 'observe')
        before = network.project(world)
        world['tiles'][0].agents[0].cash = 100.
        world['scenario_state']['political_economy']['arrears'][1]['balance'] = 0
        self.assertEqual(before, network.project(world))
        network.advance(world)
        self.assertEqual(len(world['scenario_state'][network.KEY]['history']), 1)
        world['turn'] = 3
        with self.assertRaisesRegex(ValueError, 'one update'):
            network.advance(world)

    def test_migration_and_death_refresh_membership_and_empty_nodes_stop_transmitting(self):
        world = fixture()
        network.initialize(world, 'observe')
        migrant = world['tiles'][0].agents.pop(0)
        world['tiles'][1].agents.append(migrant)
        world['tiles'][0].agents[0].alive = False
        world['turn'] = 2
        network.advance(world)
        state = world['scenario_state'][network.KEY]
        self.assertEqual(state['nodes']['a:households']['member_ids'], [])
        self.assertEqual(set(state['nodes']['b:households']['member_ids']), {1, 5})
        self.assertTrue(all(value == 0 for value in state['nodes']['a:households']['pressure'].values()))
        self.assertNotIn('a:households', state['diagnostics']['reachable'])

    def test_sparse_graph_radiates_one_hop_with_exact_attribution(self):
        world = fixture()
        network.initialize(world, 'observe')
        connected = world['scenario_state'][network.KEY]
        isolated_world = deepcopy(world)
        isolated_world['scenario_state'][network.KEY]['edges'] = {}
        world['turn'] = isolated_world['turn'] = 2
        network.advance(world)
        network.advance(isolated_world)
        isolated = isolated_world['scenario_state'][network.KEY]
        self.assertGreater(connected['nodes']['b:households']['pressure']['food'],
                           isolated['nodes']['b:households']['pressure']['food'])
        terms = connected['history'][-1]['pressure_terms']['b:households']['food']
        self.assertAlmostEqual(terms['after'], terms['before'] + terms['material']
                               + sum(terms['contacts'].values()) + terms['empty_membership_adjustment'])
        self.assertEqual(authoritative(world), authoritative(isolated_world))
        self.assertIn('b:households', connected['diagnostics']['reachable']['a:households'])
        self.assertEqual(isolated['diagnostics']['reachable']['a:households'], ['a:households'])

    def test_high_degree_does_not_destabilize_diffusion(self):
        world = fixture()
        obs = network.observe(world)
        nodes, _ = network.initial_graph(obs)
        sources = {key: dict.fromkeys(network.CHANNELS, 0.) for key in nodes}
        nodes['a:households']['pressure']['food'] = 1.
        # Many directed contacts exercise the receive budget, independently of
        # the currently small authored scenario.
        edges = {str(i): dict(source='a:households', target='b:households', weight=1.)
                 for i in range(100)}
        values, terms = network.propagate(nodes, edges, sources)
        self.assertAlmostEqual(values['b:households']['food'], .25)
        self.assertTrue(all(0 <= p <= 1 for row in values.values() for p in row.values()))

    def test_pressure_does_not_jump_across_two_contacts_in_one_turn(self):
        world = fixture()
        third = SimpleNamespace(name='c', scenario_location='Nile Delta',
                                 agents=[deepcopy(world['tiles'][1].agents[0])],
                                 gov=SimpleNamespace(tax_rate=.1))
        third.agents[0].id = 7
        world['nations'][0].tiles.append(third)
        world['tiles'].append(third)
        network.initialize(world, 'observe')
        world['turn'] = 2
        network.advance(world)
        state = world['scenario_state'][network.KEY]
        self.assertGreater(state['nodes']['b:households']['pressure']['food'], 0.)
        self.assertEqual(state['nodes']['c:households']['pressure']['food'], 0.)
        world['turn'] = 3
        network.advance(world)
        self.assertGreater(state['nodes']['c:households']['pressure']['food'], 0.)

    def test_quiet_community_needs_no_support_refresh_and_journal_is_bounded(self):
        world = fixture()
        world['tiles'][0].agents[0].calorie_deficit_kcal = 0
        world['scenario_state']['political_economy']['arrears'] = {}
        network.initialize(world, 'observe')
        for turn in range(2, 40):
            world['turn'] = turn
            network.advance(world)
        state = world['scenario_state'][network.KEY]
        self.assertEqual(len(state['history']), network.HISTORY_LIMIT)
        self.assertEqual(state['nodes']['a:households']['pressure']['food'], 0.)
        self.assertEqual(state['nodes']['a:households']['pressure']['arrears'], 0.)

    def test_sidecar_roundtrip_resumes_same_diagnostic_without_external_references(self):
        world = fixture()
        network.initialize(world, 'observe')
        copied = deepcopy(world)
        copied['scenario_state'][network.KEY] = json.loads(json.dumps(world['scenario_state'][network.KEY]))
        world['turn'] = copied['turn'] = 2
        network.advance(world)
        network.advance(copied)
        self.assertEqual(world['scenario_state'][network.KEY], copied['scenario_state'][network.KEY])

    def test_future_modes_versions_live_conversion_and_invalid_references_fail_closed(self):
        for selection in ('governing', 'invalid'):
            with self.assertRaises(ValueError):
                network.initialize(fixture(), selection)
        with self.assertRaises(ValueError):
            network.validate_creation_mode('observe', None)
        world = fixture()
        world['turn'] = 2
        with self.assertRaisesRegex(ValueError, 'new campaign'):
            network.initialize(world, 'observe')
        world['turn'] = 1
        network.initialize(world, 'observe')
        with self.assertRaisesRegex(ValueError, 'new campaign'):
            network.initialize(world, 'off')
        state = world['scenario_state'][network.KEY]
        state['nodes']['a:households']['member_ids'] = [999]
        with self.assertRaises(ValueError):
            network.project(world)
        state['version'] = 999
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            network.advance(world)


if __name__ == '__main__':
    unittest.main()
