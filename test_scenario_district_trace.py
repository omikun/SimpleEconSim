import copy
import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from scenario_district import apply_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _person(agent_id, cash, *, underfed=True):
    person = Agent(agent_id)
    initialize_agent(person, Goods.food, 0, 0, cash)
    person.id = agent_id
    person.alive = True
    person.is_government = False
    person.is_corporation = False
    person.is_trader = False
    person.calorie_need_kcal = 2000.0
    person.calorie_deficit_kcal = 800.0 if underfed else 0.0
    person.hungry_steps = 1 if underfed else 0
    return person


def _fixture(*, with_trace=True):
    people = [_person(11, 0.0), _person(12, 2.0), _person(13, 4.0, underfed=False)]
    faction = SimpleNamespace(
        membership=[11, 12], grievances={'taxes': 0.8, 'wages': 0.4})
    nation_government = SimpleNamespace(
        name='Cairo', agent=SimpleNamespace(id=900, cash=40.0),
        food_inventory=20)
    nation = SimpleNamespace(name='Egypt', currency='EGP', government=nation_government,
                             legitimacy=0.6, tiles=[])
    tile_government = SimpleNamespace(name='District Treasury', tax_rate=0.1)
    tile = SimpleNamespace(
        name='District', home_currency='EGP', agents=people,
        gov=tile_government, owner_nation=nation,
        unrest_level=0.5, protest_energy_log=[4.0], police_employed=0,
        military_units=[], factions=SimpleNamespace(factions={'organizers': faction}),
        scenario_location='District')
    nation.tiles = [tile]
    nation.capital = tile
    trace = MemoryTrace()
    if with_trace:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 4, 'phase': 'scenario_action', 'next': 1}
    world = {
        'turn': 4, 'selected_region': tile,
        'scenario_state': {'public_maize_stock_units': 20, 'extraction_level': 2},
    }
    return SimpleNamespace(world=world, nation=nation, tile=tile,
                           people=people, trace=trace, faction=faction)


def _state(fixture):
    return {
        'people': [(person.cash, person.emergency_food_units,
                    tuple(person.memory.get('mem_casualties', [])),
                    tuple(person.memory.get('mem_promises', [])))
                   for person in fixture.people],
        'public_food': fixture.nation.government.food_inventory,
        'treasury_cash': fixture.nation.government.agent.cash,
        'local_tax': fixture.tile.gov.tax_rate,
        'unrest': fixture.tile.unrest_level,
        'protest': tuple(fixture.tile.protest_energy_log),
        'legitimacy': fixture.nation.legitimacy,
        'grievances': dict(fixture.faction.grievances),
        'extraction': fixture.world['scenario_state']['extraction_level'],
    }


def _contract(row):
    return row['inputs']['transfer_contract']


class ScenarioDistrictTraceTests(unittest.TestCase):
    def test_relief_pairs_public_stock_and_queued_rations(self):
        fixture = _fixture()

        success, _ = apply_action(fixture.world, fixture.nation, 'district_relief')

        self.assertTrue(success)
        transfers = [row for row in fixture.trace.rows
                     if row.get('kind') == 'district_relief_ration_transfer']
        self.assertEqual(len(transfers), 2)
        self.assertEqual(sum(_contract(row)['amount'] for row in transfers), 8)
        for row in transfers:
            contract = _contract(row)
            self.assertEqual(contract['contract_version'], 'goods_transfer.v1')
            self.assertEqual(contract['payer_account']['balance_before']
                             - contract['payer_account']['balance_after'], 4)
            self.assertEqual(contract['payee_account']['balance_after']
                             - contract['payee_account']['balance_before'], 4)
            self.assertEqual(contract['delivery_status'],
                             'queued_for_next_consumption_step')
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_action_resolved')
        self.assertTrue(all(row['event_id'] in action['cause_event_ids']
                            for row in transfers))
        self.assertEqual(fixture.nation.government.food_inventory, 12)
        self.assertEqual(fixture.people[0].emergency_food_units, 4)

    def test_settlement_pairs_treasury_debit_and_household_credits(self):
        fixture = _fixture()

        success, _ = apply_action(fixture.world, fixture.nation, 'district_negotiate')

        self.assertTrue(success)
        payment = next(row for row in fixture.trace.rows
                       if row.get('kind') == 'district_settlement_payment')
        contract = _contract(payment)
        self.assertEqual(contract['contract_version'], 'cash_transfer.v1')
        self.assertEqual(contract['amount'], 15.0)
        self.assertEqual(contract['payer_account']['balance_before']
                         - contract['payer_account']['balance_after'], 15.0)
        members = contract['payee_account']['members']
        self.assertEqual(sum(row['amount'] for row in members), 15.0)
        self.assertTrue(all(row['balance_after'] - row['balance_before']
                            == row['amount'] for row in members))
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_action_resolved')
        self.assertEqual(action['cause_event_ids'], [payment['event_id']])
        self.assertLess(fixture.tile.unrest_level, 0.5)
        self.assertLess(fixture.faction.grievances['taxes'], 0.8)

    def test_tax_relief_records_policy_and_social_effects(self):
        fixture = _fixture()

        success, _ = apply_action(fixture.world, fixture.nation, 'district_tax_relief')

        self.assertTrue(success)
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_action_resolved')
        inputs = action['inputs']
        self.assertEqual(inputs['reason'], 'local_tax_reduced')
        self.assertEqual(inputs['tax_rate_before'], 0.1)
        self.assertAlmostEqual(inputs['tax_rate_after'], 0.06)
        self.assertLess(inputs['unrest_after'], inputs['unrest_before'])
        self.assertEqual(inputs['extraction_level_after'], 1)
        self.assertEqual(inputs['nation_legitimacy_after'], 0.61)

    def test_repression_records_force_use_memories_and_legitimacy_loss(self):
        fixture = _fixture()
        fixture.tile.police_employed = 3

        success, _ = apply_action(fixture.world, fixture.nation, 'district_repress')

        self.assertTrue(success)
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_action_resolved')
        inputs = action['inputs']
        self.assertEqual(inputs['reason'], 'force_used_to_disperse_protest')
        self.assertEqual(inputs['police_employed'], 3)
        self.assertEqual(inputs['people_seeded_with_memories'], 2)
        self.assertEqual(inputs['legitimacy_before'], 0.6)
        self.assertEqual(inputs['legitimacy_after'], 0.44999999999999996)
        self.assertEqual(fixture.people[0].memory['mem_casualties'], [1.0])
        self.assertEqual(inputs['broken_promise_memory_count_after'], 2)

    def test_failed_action_records_why_it_did_not_execute(self):
        fixture = _fixture()
        fixture.nation.government.food_inventory = 0

        success, _ = apply_action(fixture.world, fixture.nation, 'district_relief')

        self.assertFalse(success)
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_action_resolved')
        self.assertEqual(action['after'], 0)
        self.assertEqual(action['inputs']['reason'], 'public_stock_below_full_meal')
        self.assertEqual(action['inputs']['rations_available'], 0)

    def test_cash_and_force_failures_are_recorded(self):
        settlement = _fixture()
        settlement.nation.government.agent.cash = 10.0
        success, _ = apply_action(
            settlement.world, settlement.nation, 'district_negotiate')
        self.assertFalse(success)
        event = next(row for row in settlement.trace.rows
                     if row.get('kind') == 'district_action_resolved')
        self.assertEqual(event['inputs']['reason'], 'insufficient_treasury_cash')
        self.assertEqual(event['inputs']['treasury_cash_before'], 10.0)

        repression = _fixture()
        success, _ = apply_action(
            repression.world, repression.nation, 'district_repress')
        self.assertFalse(success)
        event = next(row for row in repression.trace.rows
                     if row.get('kind') == 'district_action_resolved')
        self.assertEqual(event['inputs']['reason'], 'no_police_or_garrison')

    def test_trace_does_not_change_district_action_results(self):
        plain = _fixture(with_trace=False)
        traced = copy.deepcopy(plain)
        traced.tile._run_trace = traced.trace
        traced.tile._collective_trace_clock = {
            'turn': 4, 'phase': 'scenario_action', 'next': 1}
        for action_id in ('district_relief', 'district_negotiate',
                          'district_tax_relief', 'district_repress'):
            if action_id == 'district_repress':
                plain.tile.police_employed = traced.tile.police_employed = 3
            self.assertEqual(
                apply_action(traced.world, traced.nation, action_id)[0],
                apply_action(plain.world, plain.nation, action_id)[0])
        self.assertEqual(_state(traced), _state(plain))


if __name__ == '__main__':
    unittest.main()
