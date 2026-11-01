"""Source ownership, actual participation, opposing influence and delivered terms."""

from copy import deepcopy
from types import SimpleNamespace
import json
import random
from pathlib import Path
import tempfile
import unittest

from goods import Goods
import governing_network as network
import governing_collectives as collectives
from strike_status import enable, set_striking, source, has_source, clear_all
from tests.test_governing_network import fixture, Person


def governing_fixture(count=24, deficit=.8):
    world = fixture()
    world['scenario_state'].update(relief_units_per_turn=110, payment_window_turn=6,
                                   payment_status='upcoming', scheduled_remittance=200.)
    world['nations'][0].legitimacy = .6
    world['nations'][0].currency = 'EGP'
    world['scenario_state']['political_economy']['arrears'] = {}
    world['scenario_state']['political_economy']['scenario_strikers_by_tile'] = {t.name: [] for t in world['tiles']}
    for row in world['scenario_state']['political_economy']['collective_by_tile'].values():
        row.update(settlement_until_turn=0, injuries=0, support=0.)
    for index, tile in enumerate(world['tiles']):
        tile.recipes = {Goods.food: {'price': 1.}}
        tile.unrest_level = .2
        keep = [p for p in tile.agents if getattr(p, 'is_lord', False) or getattr(p, 'is_trader', False)]
        for p in keep:
            p.wage = 1.
            p.cash = 300.
        workers = [Person(id=100 + index * 100 + i, alive=True, cash=10.,
                          inventory={Goods.food: 2}, calorie_deficit_kcal=deficit * 2000,
                          calorie_need_kcal=2000., energy_reserve_kcal=40000.,
                          is_striking=False, output=Goods.food, employer=None,
                          risk_tolerance=.5) for i in range(count)]
        tile.agents = workers + keep
    network.initialize(world, 'governing')
    return world


def assets(world):
    people = [p for tile in world['tiles'] for p in tile.agents]
    gov = world['nations'][0].government
    return (sum(p.cash for p in people) + gov.agent.cash,
            sum(p.inv_get(Goods.food, 0) for p in people) + gov.food_inventory)


class StrikeSourceTests(unittest.TestCase):
    def test_legacy_flags_keep_their_old_shape(self):
        person = SimpleNamespace(is_striking=False)
        set_striking(person, 'workplace:old', True)
        self.assertTrue(person.is_striking)
        set_striking(person, 'another', False)
        self.assertFalse(person.is_striking)
        self.assertNotIn('_strike_sources', vars(person))

    def test_settlement_releases_only_its_source_and_repression_is_explicit(self):
        person = SimpleNamespace(is_striking=False)
        enable(person)
        set_striking(person, 'network:Delta', True)
        set_striking(person, 'workplace:Delta:1', True)
        set_striking(person, 'workplace:Delta:1', False)
        self.assertTrue(person.is_striking)
        self.assertEqual(list(person._strike_sources), ['network:Delta'])
        set_striking(person, 'enclosure:Delta', True)
        self.assertEqual(clear_all(person), ['enclosure:Delta', 'network:Delta'])
        self.assertFalse(person.is_striking)

    def test_actual_workplace_offer_does_not_cancel_a_network_walkout(self):
        from agent import Agent
        from collective_action import _start, _offer, CollectiveOrganization
        region = SimpleNamespace(name='Works', recipes={Goods.food: {'price': 1.},
                                  Goods.cloth: {'price': 20., 'production': 5}},
                                  collective_organizations={}, collective_log=[],
                                  _governing_strike_sources=True)
        firm, worker = Agent(0), Agent(0)
        firm.is_corporation, firm.output, firm.cash, firm.wage = True, Goods.cloth, 300., 1.
        firm.shift_hours = worker.shift_hours = 12.
        worker.employer = firm
        worker.hungry_steps = 0
        worker.inv_set(Goods.food, 4)
        firm.employees = [worker]
        region.agents = [firm, worker]
        set_striking(worker, source('network', region), True, region=region)
        org = CollectiveOrganization(firm_id=firm.id, firm_name='Mill')
        region.collective_organizations[firm.id] = org
        strike = _start(region, firm, org, [worker], [worker], 1)
        self.assertTrue(_offer(region, firm, org, strike, [worker], 2))
        self.assertTrue(worker.is_striking)
        self.assertTrue(has_source(worker, source('network', region)))
        self.assertFalse(has_source(worker, source('workplace', region, firm)))

    def test_enclosure_dissolution_preserves_unrelated_withholding(self):
        from popular_resistance import PopularResistanceManager
        from tests.test_charismatic_rebellion import DummyTile, DummyTenure, DummyPlot
        from agent import Agent
        tile, person = DummyTile(), Agent(0)
        tile._governing_strike_sources = True
        tile.tenure = DummyTenure([DummyPlot('other', .4)])
        tile.tenure.plots = tile.tenure._plots
        tile.agents = [person]
        manager = PopularResistanceManager()
        state = manager.get_state(tile.name)
        state.enclosure_stage, state.target_plot_id = 'marching', 'missing'
        state.revolt_participants = [person.id]
        for kind in ('enclosure', 'network', 'workplace'):
            set_striking(person, source(kind, tile), True, region=tile)
        manager.evaluate_anti_enclosure_revolt(tile, 2)
        self.assertTrue(person.is_striking)
        self.assertFalse(has_source(person, source('enclosure', tile)))
        self.assertTrue(has_source(person, source('network', tile)))

    def test_network_only_strikes_do_not_also_freeze_all_routes(self):
        from popular_resistance import PopularResistanceManager
        tile = SimpleNamespace(name='Delta', agents=[], unrest_level=.2,
                               routes={'port': SimpleNamespace(is_blocked_by_strike=False)},
                               _governing_strike_sources=True)
        for pid in range(10):
            person = SimpleNamespace(id=pid, alive=True, is_striking=False, social_class='proletarian')
            set_striking(person, source('network', tile), True, region=tile)
            tile.agents.append(person)
        manager = PopularResistanceManager()
        self.assertEqual(manager.evaluate_general_strike(tile, 2), [])
        self.assertFalse(tile.routes['port'].is_blocked_by_strike)
        for person in tile.agents[:4]:
            set_striking(person, source('workplace', tile, 77), True, region=tile)
        self.assertTrue(manager.evaluate_general_strike(tile, 3))
        self.assertTrue(tile.routes['port'].is_blocked_by_strike)


class GoverningParticipationTests(unittest.TestCase):
    def test_petition_is_immediate_but_work_changes_only_next_turn_once(self):
        world = governing_fixture()
        state = world['scenario_state'][network.KEY]
        self.assertGreater(sum(len(p['petition_ids']) for p in state['pending'].values()), 0)
        self.assertGreater(sum(len(p['strike_ids']) for p in state['pending'].values()), 0)
        self.assertFalse(any(p.is_striking for t in world['tiles'] for p in t.agents))
        before = assets(world)
        network.prepare_turn(world, 2)
        self.assertTrue(any(p.is_striking for t in world['tiles'] for p in t.agents))
        once = deepcopy(state['events'])
        network.prepare_turn(world, 2)
        self.assertEqual(once, state['events'])
        self.assertEqual(before, assets(world))

    def test_same_hardship_connected_and_fragmented_organizations_mobilize_differently(self):
        connected = governing_fixture(count=40)
        isolated = deepcopy(connected)
        state = isolated['scenario_state'][network.KEY]
        state['edges'], state['organizations'], state['pending'] = {}, {}, {}
        collectives.plan(isolated, previous=state['observation'])
        def count(world):
            return sum(len(p['strike_ids']) for p in world['scenario_state'][network.KEY]['pending'].values())
        self.assertGreater(count(connected), count(isolated))
        network.prepare_turn(connected, 2)
        network.prepare_turn(isolated, 2)
        self.assertNotEqual(sum(a.is_striking for t in connected['tiles'] for a in t.agents),
                            sum(a.is_striking for t in isolated['tiles'] for a in t.agents))
        self.assertEqual(assets(connected), assets(isolated))

    def test_resolved_hardship_stands_down_without_rallies(self):
        world = governing_fixture()
        network.prepare_turn(world, 2)
        for tile in world['tiles']:
            for person in tile.agents:
                person.calorie_deficit_kcal = 0.
        world['turn'] = 2
        network.advance(world)
        network.prepare_turn(world, 3)
        self.assertFalse(any(has_source(a, source('network', t)) for t in world['tiles'] for a in t.agents))
        for turn in range(3, 9):
            world['turn'] = turn
            network.advance(world)
            network.prepare_turn(world, turn + 1)
        self.assertEqual(network.project(world)['organized_people'], 0)

    def test_real_queued_food_prevents_joining_without_changing_other_strikes(self):
        world = governing_fixture(count=1, deficit=1.)
        person, tile = world['tiles'][0].agents[0], world['tiles'][0]
        self.assertIn(person.id, world['scenario_state'][network.KEY]['pending'][tile.name]['strike_ids'])
        person.emergency_food_units = 4
        set_striking(person, source('workplace', tile, 99), True, region=tile)
        network.prepare_turn(world, 2)
        self.assertFalse(has_source(person, source('network', tile)))
        self.assertTrue(has_source(person, source('workplace', tile, 99)))
        event = next(e for e in world['scenario_state'][network.KEY]['events'] if e['tile'] == tile.name)
        self.assertEqual(event['reasons'][str(person.id)], 'funded_next_meal_ration')

    def test_owner_counterpressure_is_bounded_and_reconstructible(self):
        world = governing_fixture()
        state = world['scenario_state'][network.KEY]
        nodes = deepcopy(state['nodes'])
        nodes['a:holders']['pressure']['property'] = 1.
        obs = state['observation']
        sources = {key: network.material_inputs(obs, obs['districts'][n['tile']], n['community'])['sources']
                   for key, n in nodes.items()}
        values, terms, _ = collectives.diffuse(nodes, state['edges'], sources, obs)
        friendly = {key: e for key, e in state['edges'].items() if e['basis'] == 'authored_association_contact'}
        without, _, _ = collectives.diffuse(nodes, friendly, sources, obs)
        self.assertLess(values['a:households']['food'], without['a:households']['food'])
        row = terms['a:households']['food']
        self.assertAlmostEqual(row['after'], row['before'] + row['material']
                               + sum(row['contacts'].values()) + sum(row['opposition'].values())
                               + row['empty_membership_adjustment'])
        self.assertTrue(all(0 <= value <= 1 for p in values.values() for value in p.values()))

    def test_paid_bargain_preserves_another_strike_and_conserves_the_payment(self):
        from scenario_political_economy import apply_action
        world = governing_fixture(count=1, deficit=1.)
        network.prepare_turn(world, 2)
        world['turn'] = 2
        tile, person = world['tiles'][0], world['tiles'][0].agents[0]
        set_striking(person, source('workplace', tile, 99), True, region=tile)
        before = assets(world)
        ok, message = apply_action(world, world['nations'][0], 'district_bargain_workers', tile)
        self.assertTrue(ok, message)
        receipt = world['scenario_state'][network.KEY]['receipts'][-1]
        self.assertIn(person.id, receipt['accepted_ids'])
        self.assertTrue(person.is_striking)
        self.assertFalse(has_source(person, source('network', tile)))
        self.assertEqual(before, assets(world))

    def test_unfunded_bargain_has_no_settlement_or_wage_reward(self):
        from scenario_political_economy import apply_action
        world = governing_fixture(count=1, deficit=1.)
        network.prepare_turn(world, 2)
        world['turn'] = 2
        tile = world['tiles'][0]
        for person in tile.agents:
            if getattr(person, 'is_lord', False):
                person.cash = 0.
        before = [(a.id, a.cash, getattr(a, 'wage', None)) for a in tile.agents]
        legitimacy = world['nations'][0].legitimacy
        ok, message = apply_action(world, world['nations'][0], 'district_bargain_workers', tile)
        self.assertFalse(ok)
        self.assertIn('cannot fund', message)
        self.assertEqual(before, [(a.id, a.cash, getattr(a, 'wage', None)) for a in tile.agents])
        self.assertEqual(legitimacy, world['nations'][0].legitimacy)
        self.assertEqual(world['scenario_state'][network.KEY]['settlements'], {})

    def test_people_can_refuse_a_paid_representative_settlement(self):
        from scenario_political_economy import apply_action
        world = governing_fixture(count=40, deficit=1.)
        network.prepare_turn(world, 2)
        world['turn'] = 2
        tile = world['tiles'][0]
        for person in tile.agents:
            if getattr(person, 'is_lord', False):
                person.cash = 10.
        ok, _ = apply_action(world, world['nations'][0], 'district_bargain_workers', tile)
        self.assertTrue(ok)
        receipt = world['scenario_state'][network.KEY]['receipts'][-1]
        self.assertLess(len(receipt['accepted_ids']), len(receipt['recipient_ids']))
        self.assertTrue(any(has_source(p, source('network', tile)) for p in tile.agents))

    def test_state_roundtrip_preserves_individual_intents_and_no_rng_is_consumed(self):
        from random_cache import rand
        world = governing_fixture()
        py_rng, cache = random.getstate(), (rand._idx, rand._buf.copy())
        copied = deepcopy(world)
        copied['scenario_state'][network.KEY] = json.loads(json.dumps(world['scenario_state'][network.KEY]))
        for w in (world, copied):
            network.prepare_turn(w, 2)
            w['turn'] = 2
            network.advance(w)
        self.assertEqual(world['scenario_state'][network.KEY], copied['scenario_state'][network.KEY])
        self.assertEqual(py_rng, random.getstate())
        self.assertEqual(cache, (rand._idx, rand._buf))


class GoverningIntegrationTests(unittest.TestCase):
    def test_bad_future_participation_is_rejected_instead_of_silently_converted(self):
        world = governing_fixture()
        state = world['scenario_state'][network.KEY]
        state['pending']['a']['strike_ids'].append(999999)
        with self.assertRaisesRegex(ValueError, 'references'):
            network.mode(world)

    def test_consumed_network_event_links_to_real_withheld_hours_and_zero_output(self):
        from agent import Agent, initialize_agent
        from region import Region
        from run_trace import RunTrace
        from labor_resistance import record_workforce_availability
        from region_production import produce_corporation
        world = governing_fixture()
        world['scenario_state'].pop(network.KEY)
        old = world['tiles'][0]
        tile = Region('a', 0, 1)
        tile.scenario_location = 'Upper Egypt'
        firm = Agent(0)
        initialize_agent(firm, Goods.cloth, 0, 0, 50.)
        firm.is_corporation, firm.output = True, Goods.cloth
        workers = []
        for _ in range(40):
            person = Agent(0)
            initialize_agent(person, Goods.food, 0, 0, 100.)
            person.calorie_need_kcal, person.calorie_deficit_kcal = 2000., 1900.
            person.inv_set(Goods.food, 0)
            workers.append(person)
        tile.agents = [firm] + workers + [p for p in old.agents if getattr(p, 'is_lord', False)]
        world['tiles'][0] = world['nations'][0].tiles[0] = tile
        with tempfile.TemporaryDirectory() as directory:
            trace = RunTrace(Path(directory) / 'network.ctr', 'network-test')
            tile._run_trace = trace
            network.initialize(world, 'governing')
            intent = world['scenario_state'][network.KEY]['pending']['a']
            selected = set(intent['strike_ids'])
            self.assertTrue(selected)
            # The production probe employs the actual volunteers, without
            # changing their network decision or assigning strike flags.
            firm.employees = [p for p in workers if p.id in selected]
            for person in firm.employees:
                person.employer = firm
            network.prepare_turn(world, 2)
            consumed = next(e for e in trace.recent if e['kind'] == 'network_participation_consumed')
            self.assertIn(intent['trace_event_id'], consumed['cause_event_ids'])
            workforce_ids = record_workforce_availability(tile, 2)
            workforce = trace.recent[-1]
            self.assertEqual(workforce['value_after'], 0.)
            self.assertEqual(workforce['inputs']['striking_employee_ids'], [p.id for p in firm.employees])
            self.assertIn(consumed['event_id'], workforce['cause_event_ids'])
            produce_corporation(tile, firm, tile.recipes[Goods.cloth], Goods.cloth, {Goods.cloth: 1}, {})
            outcome = trace.recent[-1]
            self.assertEqual(outcome['kind'], 'firm_production_zero')
            self.assertEqual(outcome['inputs']['reason'], 'all_employees_withheld_or_revolting')
            self.assertIn(workforce_ids[firm.id], outcome['cause_event_ids'])


if __name__ == '__main__':
    unittest.main()
