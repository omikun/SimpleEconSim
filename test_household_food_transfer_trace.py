import unittest
from math import exp
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from government import Government
from scenario_political_economy import _organize, apply_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _aid_fixture(*, emergency=False, with_trace=True):
    government = Government('District Treasury', 1, initial_cash=0.0)
    government.food_inventory = 3
    government.emergency_food_policy = emergency
    person = Agent(11)
    initialize_agent(person, Goods.wood, 0, 0, 0)
    person.hungry_steps = 1
    person.calorie_deficit_kcal = 1000.0
    person.inv_set(Goods.food, 0)
    trace = MemoryTrace()
    region = SimpleNamespace(
        name='Delta', home_currency='EGP', gov=government,
        _collective_trace_clock={'turn': 4, 'phase': 'livelihood', 'next': 1})
    if with_trace:
        region._run_trace = trace
    government.regions = [region]
    return government, person, region, trace


def _person(agent_id, food, deficit):
    person = Agent(agent_id)
    initialize_agent(person, Goods.food, 0, 0, 0)
    person.id = agent_id
    person.alive = True
    person.is_government = False
    person.is_corporation = False
    person.is_trader = False
    person.is_lord = False
    person.inv_set(Goods.food, food)
    person.calorie_deficit_kcal = float(deficit)
    person.hungry_steps = 1 if deficit else 0
    return person


def _mutual_aid_fixture(*, with_trace=True):
    donor = _person(21, 10, 0)
    receiver = _person(22, 0, 1000)
    trace = MemoryTrace()
    tile = SimpleNamespace(
        name='Delta', agents=[donor, receiver],
        _collective_trace_clock={'turn': 6, 'phase': 'scenario_economy', 'next': 1})
    if with_trace:
        tile._run_trace = trace
    collective = {'petitioners': 0, 'strikers': 0, 'mutual_aid_meals': 0,
                  'support': 0.0, 'settlement_until_turn': 0}
    world = {'turn': 6, 'scenario_state': {'political_economy': {
        'collective_by_tile': {tile.name: collective}, 'arrears': {},
        'scenario_strikers_by_tile': {tile.name: []}}}}
    nation = SimpleNamespace(
        name='Egypt', legitimacy=0.7, tiles=[tile],
        government=SimpleNamespace(agent=SimpleNamespace(cash=0.0)))
    tile.owner_nation = nation
    return world, nation, tile, donor, receiver, collective, trace


class HouseholdFoodTransferTraceTests(unittest.TestCase):
    def test_public_food_aid_records_each_inventory_leg_and_summary(self):
        government, person, region, trace = _aid_fixture()
        delivered = government.provide_food_aid(4, [person], 1.0, region=region)

        self.assertEqual(delivered, 1)
        recipient = next(row for row in trace.rows
                         if row.get('metric_id') == 'goods.food_aid_recipient')
        contract = recipient['inputs']['transfer_contract']
        self.assertEqual(contract['amount'], 1)
        self.assertEqual(contract['payer_account']['balance_before'], 3)
        self.assertEqual(contract['payer_account']['balance_after'], 2)
        self.assertEqual(contract['payee_account']['balance_before'], 0)
        self.assertEqual(contract['payee_account']['balance_after'], 1)
        summary = next(row for row in trace.rows
                       if row.get('metric_id') == 'goods.food_aid')
        self.assertEqual((summary['before'], summary['after']), (3, 2))
        self.assertEqual(summary['cause_event_ids'], [recipient['event_id']])

    def test_emergency_aid_uses_same_exact_recipient_contract(self):
        government, person, region, trace = _aid_fixture(emergency=True)
        delivered = government.provide_food_aid(4, [person], 1.0)

        self.assertEqual(delivered, 3)
        self.assertEqual(government.food_inventory, 0)
        self.assertEqual(person.inv_get(Goods.food, 0), 3)
        recipients = [row for row in trace.rows
                      if row.get('metric_id') == 'goods.food_aid_recipient']
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]['inputs']['transfer_contract']['amount'], 3)
        self.assertTrue(recipients[0]['inputs']['emergency_policy'])

    def test_automatic_mutual_aid_records_household_inventories_and_total(self):
        world, nation, tile, donor, receiver, collective, trace = (
            _mutual_aid_fixture())
        _organize(world, tile)

        self.assertEqual((donor.inv_get(Goods.food, 0),
                          receiver.inv_get(Goods.food, 0)), (9, 1))
        self.assertEqual(collective['mutual_aid_meals'], 1)
        transfer = next(row for row in trace.rows
                        if row.get('metric_id') == 'goods.mutual_aid_transfer')
        contract = transfer['inputs']['transfer_contract']
        self.assertEqual(contract['payer_account']['balance_before'], 10)
        self.assertEqual(contract['payer_account']['balance_after'], 9)
        self.assertEqual(contract['payee_account']['balance_before'], 0)
        self.assertEqual(contract['payee_account']['balance_after'], 1)
        total = next(row for row in trace.rows
                     if row.get('metric_id') == 'politics.mutual_aid_meals')
        self.assertEqual((total['before'], total['after']), (0, 1))
        self.assertEqual(total['cause_event_ids'], [transfer['event_id']])

    def test_supported_mutual_aid_links_transfer_count_and_legitimacy(self):
        world, nation, tile, donor, receiver, collective, trace = (
            _mutual_aid_fixture())
        ok, _ = apply_action(world, nation, 'district_support_mutual_aid', tile)

        self.assertTrue(ok)
        self.assertEqual((donor.inv_get(Goods.food, 0),
                          receiver.inv_get(Goods.food, 0)), (9, 1))
        transfer = next(row for row in trace.rows
                        if row.get('metric_id') == 'goods.mutual_aid_transfer')
        total = next(row for row in trace.rows
                     if row.get('metric_id') == 'politics.mutual_aid_meals')
        legitimacy = next(row for row in trace.rows
                          if row.get('kind') == 'mutual_aid_legitimacy_gain')
        self.assertEqual(legitimacy['cause_event_ids'], [total['event_id']])
        self.assertEqual(total['cause_event_ids'], [transfer['event_id']])
        self.assertAlmostEqual(nation.legitimacy, 0.7 + .005 * (1 - exp(-1 / 5)))

    def test_trace_on_off_preserves_aid_and_mutual_aid_state(self):
        aid_traced = _aid_fixture(with_trace=True)
        aid_plain = _aid_fixture(with_trace=False)
        aid_traced[0].provide_food_aid(4, [aid_traced[1]], 1.0,
                                       region=aid_traced[2])
        aid_plain[0].provide_food_aid(4, [aid_plain[1]], 1.0,
                                      region=aid_plain[2])
        self.assertEqual((aid_traced[0].food_inventory,
                          aid_traced[1].inv_get(Goods.food, 0)),
                         (aid_plain[0].food_inventory,
                          aid_plain[1].inv_get(Goods.food, 0)))

        mutual_traced = _mutual_aid_fixture(with_trace=True)
        mutual_plain = _mutual_aid_fixture(with_trace=False)
        for fixture in (mutual_traced, mutual_plain):
            _organize(fixture[0], fixture[2])
        self.assertEqual((mutual_traced[3].inv_get(Goods.food, 0),
                          mutual_traced[4].inv_get(Goods.food, 0),
                          mutual_traced[5]['mutual_aid_meals']),
                         (mutual_plain[3].inv_get(Goods.food, 0),
                          mutual_plain[4].inv_get(Goods.food, 0),
                          mutual_plain[5]['mutual_aid_meals']))


if __name__ == '__main__':
    unittest.main()
