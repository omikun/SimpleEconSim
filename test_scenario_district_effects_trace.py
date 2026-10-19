import copy
import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from scenario_political_economy import apply_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _common_trace(region, trace):
    region._run_trace = trace
    region._collective_trace_clock = {
        'turn': 5, 'phase': 'scenario_action', 'next': 1}


def _arrears_fixture(*, traced=True, with_arrears=True):
    debtor = SimpleNamespace(
        id=31, alive=True, cash=0.0, is_government=False,
        is_corporation=False, is_trader=False, is_lord=False)
    municipal = SimpleNamespace(id=901, alive=True, cash=30.0,
                                is_government=True)
    national = SimpleNamespace(id=902, alive=True, cash=40.0,
                               is_government=True)
    nation = SimpleNamespace(
        name='Egypt', currency='EGP', legitimacy=0.5,
        government=SimpleNamespace(agent=national))
    region = SimpleNamespace(
        name='Delta', home_currency='EGP', agents=[debtor, municipal, national],
        owner_nation=nation, economic_events=[],
        gov=SimpleNamespace(agent=municipal, tax_rate=0.20))
    nation.tiles = [region]
    collective = {'petitioners': 0, 'strikers': 0, 'mutual_aid_meals': 0,
                  'injuries': 0, 'support': 0.0, 'settlement_until_turn': 0}
    arrears = ({debtor.id: {'balance': 40.0, 'missed': 3,
                            'plot_id': 'plot-1'}} if with_arrears else {})
    world = {'turn': 5, 'scenario_state': {'political_economy': {
        'arrears': arrears,
        'collective_by_tile': {region.name: collective},
        'scenario_strikers_by_tile': {region.name: []},
    }}}
    trace = MemoryTrace()
    if traced:
        _common_trace(region, trace)
    return SimpleNamespace(world=world, nation=nation, tile=region,
                           debtor=debtor, municipal=municipal,
                           national=national, collective=collective, trace=trace)


def _strike_fixture(*, traced=True, force=True):
    worker = Agent(71)
    initialize_agent(worker, Goods.food, 0, 0, 2.0)
    worker.id = 71
    worker.is_striking = True
    nation = SimpleNamespace(
        name='Egypt', currency='EGP', legitimacy=0.6,
        government=SimpleNamespace(agent=SimpleNamespace(id=903, cash=10.0)))
    faction = SimpleNamespace(membership=[worker.id], grievances={'wages': 0.8})
    region = SimpleNamespace(
        name='Delta', scenario_location='Nile Delta', home_currency='EGP',
        agents=[worker], owner_nation=nation, police_employed=2 if force else 0,
        military_units=[], protest_energy_log=[4.0],
        factions=SimpleNamespace(factions={'workers': faction}))
    nation.tiles = [region]
    collective = {'petitioners': 1, 'strikers': 1, 'mutual_aid_meals': 0,
                  'injuries': 0, 'support': 0.0, 'settlement_until_turn': 0}
    world = {'turn': 5, 'scenario_state': {'political_economy': {
        'arrears': {}, 'collective_by_tile': {region.name: collective},
        'scenario_strikers_by_tile': {region.name: [worker.id]},
    }}}
    trace = MemoryTrace()
    if traced:
        _common_trace(region, trace)
    return SimpleNamespace(world=world, nation=nation, tile=region,
                           worker=worker, faction=faction,
                           collective=collective, trace=trace)


def _strike_state(fixture):
    return {
        'worker_striking': fixture.worker.is_striking,
        'worker_memory': copy.deepcopy(fixture.worker.memory),
        'collective': copy.deepcopy(fixture.collective),
        'scenario_strikers': copy.deepcopy(
            fixture.world['scenario_state']['political_economy']
            ['scenario_strikers_by_tile'][fixture.tile.name]),
        'legitimacy': fixture.nation.legitimacy,
        'protest': copy.deepcopy(fixture.tile.protest_energy_log),
        'grievances': copy.deepcopy(fixture.faction.grievances),
    }


class ScenarioDistrictEffectsTraceTests(unittest.TestCase):
    def test_arrears_relief_links_writeoffs_tax_rate_and_legitimacy(self):
        fixture = _arrears_fixture()

        success, _ = apply_action(
            fixture.world, fixture.nation, 'district_arrears_relief', fixture.tile)

        self.assertTrue(success)
        self.assertEqual(fixture.world['scenario_state']['political_economy']
                         ['arrears'][fixture.debtor.id]['balance'], 0.0)
        self.assertEqual(fixture.world['scenario_state']['political_economy']
                         ['arrears'][fixture.debtor.id]['missed'], 0)
        self.assertEqual(fixture.tile.gov.tax_rate, 0.17)
        self.assertEqual(fixture.nation.legitimacy, 0.515)
        writeoff = next(row for row in fixture.trace.rows
                        if row.get('kind') == 'tax_arrears_forgiven')
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_arrears_relief_resolved')
        self.assertEqual(action['cause_event_ids'], [writeoff['event_id']])
        self.assertEqual(action['inputs']['forgiven_total'], 40.0)
        self.assertEqual(action['inputs']['municipal_writeoff_total'], 30.0)
        self.assertEqual(action['inputs']['national_writeoff_total'], 10.0)
        self.assertEqual(action['inputs']['tax_rate_before'], 0.20)
        self.assertEqual(action['inputs']['tax_rate_after'], 0.17)
        self.assertEqual(action['inputs']['legitimacy_before'], 0.5)
        self.assertEqual(action['inputs']['legitimacy_after'], 0.515)

    def test_missing_arrears_gate_is_recorded_without_effect(self):
        fixture = _arrears_fixture(with_arrears=False)

        success, _ = apply_action(
            fixture.world, fixture.nation, 'district_arrears_relief', fixture.tile)

        self.assertFalse(success)
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_arrears_relief_resolved')
        self.assertEqual(action['inputs']['reason'], 'no_recorded_cultivator_arrears')
        self.assertEqual(action['after'], 0)
        self.assertEqual(fixture.tile.gov.tax_rate, 0.20)
        self.assertEqual(fixture.nation.legitimacy, 0.5)

    def test_repression_action_links_force_effect_and_strike_clearance(self):
        fixture = _strike_fixture()

        success, _ = apply_action(
            fixture.world, fixture.nation, 'district_break_strike', fixture.tile)

        self.assertTrue(success)
        self.assertFalse(fixture.worker.is_striking)
        self.assertEqual(fixture.collective['strikers'], 0)
        self.assertEqual(fixture.collective['injuries'], 1)
        self.assertEqual(fixture.world['scenario_state']['political_economy']
                         ['scenario_strikers_by_tile']['Delta'], [])
        self.assertEqual(fixture.worker.memory['mem_casualties'], [1.0])
        self.assertEqual(fixture.worker.memory['mem_promises'], [1.0])
        repression = next(row for row in fixture.trace.rows
                          if row.get('kind') == 'repression_resolved')
        labor = next(row for row in fixture.trace.rows
                     if row.get('kind') == 'district_strike_broken')
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_break_strike_resolved')
        self.assertEqual(repression['inputs']['operation_id'],
                         'district-break-strike:Delta:5')
        self.assertEqual(labor['cause_event_ids'], [repression['event_id']])
        self.assertEqual(action['cause_event_ids'], [labor['event_id']])
        self.assertEqual(action['inputs']['injury_memory_count_added'], 1)
        self.assertEqual(action['inputs']['police_employed'], 2)

    def test_repression_force_gate_and_trace_on_off_parity(self):
        plain = _strike_fixture(traced=False)
        traced = _strike_fixture(traced=True)

        plain_success, _ = apply_action(
            plain.world, plain.nation, 'district_break_strike', plain.tile)
        traced_success, _ = apply_action(
            traced.world, traced.nation, 'district_break_strike', traced.tile)

        self.assertEqual(traced_success, plain_success)
        self.assertEqual(_strike_state(traced), _strike_state(plain))

        unavailable = _strike_fixture(force=False)
        success, _ = apply_action(
            unavailable.world, unavailable.nation,
            'district_break_strike', unavailable.tile)
        self.assertFalse(success)
        labor = next(row for row in unavailable.trace.rows
                     if row.get('kind') == 'district_strike_repression_gate_rejected')
        self.assertEqual(labor['inputs']['reason'], 'no_police_or_garrison')
        action = next(row for row in unavailable.trace.rows
                      if row.get('kind') == 'district_break_strike_resolved')
        self.assertEqual(action['after'], 0)


if __name__ == '__main__':
    unittest.main()
