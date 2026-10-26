"""Behavioral checks for the response gaps found in the twenty-turn trace."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent import Agent, initialize_agent
from goods import Goods
from nation import Nation
from province import Province
from region import Region
from region_logistics import repoint_traders
from food_logistics import dispatch_province_food, deliver_province_food, prepare_food_relief


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        json.dumps(row, allow_nan=False)
        self.rows.append(row)
        return f'test:{len(self.rows)}'


def route_fixture():
    source = SimpleNamespace(
        name='Source', recipes={Goods.wood: {'price': 5},
                               Goods.furniture: {'price': 5},
                               Goods.transport: {'price': 1, 'capacity': 10}},
        neighbors={}, routes={}, trader_agents=[], forex_desks={}, forex=None,
        IMPORT_MARGIN_MIN=0.05, home_currency='D', agents=[], _last_turn=3)
    destination = SimpleNamespace(
        name='Destination', recipes={Goods.wood: {'price': 7},
                                    Goods.furniture: {'price': 7.1, 'input': Goods.wood, 'numInput': 1},
                                    Goods.food: {'price': 1}}, agents=[], gov=None, _last_turn=3)
    source.neighbors[destination.name] = destination
    source.routes[destination.name] = object()
    artisan = Agent(0)
    initialize_agent(artisan, Goods.furniture, 0, 0, 20)
    artisan.inv_set(Goods.food, 4)
    artisan.inv_set(Goods.wood, 0)
    destination.agents.append(artisan)
    trader = Agent(0)
    initialize_agent(trader, Goods.food, 0, 0, 100)
    trader.is_trader = True
    trader.destination_region = destination
    trader.trade_good = Goods.furniture
    source.trader_agents.append(trader)
    source._run_trace = MemoryTrace()
    source._collective_trace_clock = {'turn': 3, 'phase': 'trade', 'next': 1}
    return source, destination, artisan, trader


def relief_fixture():
    nation = Nation('Domestic', initial_cash=500)
    nation.ai = object()
    provinces = [Province('Surplus Province', nation), Province('Hungry Province', nation)]
    nation.provinces.extend(provinces)
    tiles = [Region(name, 0, 3, institutions=province.institutions)
             for name, province in zip(('Surplus', 'Hungry'), provinces)]
    trace = MemoryTrace()
    for tile, province in zip(tiles, provinces):
        province.add_tile(tile)
        nation.add_tile(tile)
        tile._run_trace = trace
        tile._collective_trace_clock = {'turn': 1, 'phase': 'local', 'next': 1}
        for person in tile.agents:
            person.inv_set(Goods.food, 0)
            person.calorie_deficit_kcal = 1000 if tile is tiles[1] else 0
            person.hungry_steps = 2 if tile is tiles[1] else 0
        province.gov.agent.cash = 100
    donor = next(a for a in tiles[0].agents if not a.is_government and not a.is_corporation)
    donor.inv_set(Goods.food, 1000)
    tiles[1].gov.emergency_food_policy = True
    tiles[0].add_neighbor(tiles[1])
    tiles[1].add_neighbor(tiles[0])
    return nation, provinces, tiles, donor, trace


class EconomicPolicyResponseTests(unittest.TestCase):
    def test_artisan_input_request_changes_choice_between_profitable_routes(self):
        source, destination, artisan, trader = route_fixture()
        with patch('terrain_edges.get_edge_manager', return_value=None):
            destination.independent_input_requests_enabled = False
            repoint_traders(source)
            self.assertEqual(trader.trade_good, Goods.furniture)
            destination.independent_input_requests_enabled = True
            repoint_traders(source)
        self.assertEqual(trader.trade_good, Goods.wood)
        decision = next(r for r in reversed(source._run_trace.rows)
                        if r['kind'] == 'trader_route_decision')
        wood = next(r for r in decision['inputs']['candidate_evaluations'] if r['good'] == 'wood')
        self.assertEqual(wood['requested_input_units'], 2)
        self.assertEqual(wood['requesting_producers'][0]['producer_role'], 'independent')

    def test_unfunded_or_employed_artisan_cannot_create_route_demand(self):
        for employed, cash, food in ((True, 20, 4), (False, 2, 0)):
            with self.subTest(employed=employed, cash=cash):
                source, destination, artisan, trader = route_fixture()
                artisan.employer = object() if employed else None
                artisan.cash = cash
                artisan.inv_set(Goods.food, food)
                with patch('terrain_edges.get_edge_manager', return_value=None):
                    repoint_traders(source)
                self.assertEqual(trader.trade_good, Goods.furniture)

    def test_cross_province_relief_is_paid_delayed_and_not_double_booked(self):
        nation, provinces, tiles, donor, trace = relief_fixture()
        source, destination = tiles
        holders = [a for tile in tiles for a in tile.agents
                   if not a.is_corporation and not a.is_government]
        initial_cash = sum(a.cash for a in holders) + sum(p.gov.agent.cash for p in provinces)
        initial_food = sum(a.inv_get(Goods.food, 0) for a in holders)
        with patch('terrain_edges.get_edge_manager', return_value=None):
            dispatched = dispatch_province_food(provinces[0], 1)
            self.assertTrue(dispatched)
            self.assertEqual(dispatched[0]['logistics_scope'], 'nation')
            self.assertEqual(dispatched[0]['arrival_turn'], 2)
            self.assertGreater(dispatched[0]['haulage_wages'], 0)
            self.assertEqual(dispatch_province_food(provinces[0], 1), [])
        self.assertAlmostEqual(initial_cash, sum(a.cash for a in holders) + sum(p.gov.agent.cash for p in provinces))
        cargo = sum(s['units'] for p in provinces for s in p.food_shipments)
        self.assertEqual(initial_food, sum(a.inv_get(Goods.food, 0) for a in holders) + cargo)
        self.assertEqual(sum(a.inv_get(Goods.food, 0) for a in destination.agents), 0)
        # Destination province is first: deliveries still happen before any
        # province's meals, regardless of the source's iteration order.
        with patch('terrain_edges.get_edge_manager', return_value=None):
            prepare_food_relief(list(reversed(provinces)), 2)
        self.assertFalse(provinces[0].food_shipments)
        self.assertGreater(sum(a.inv_get(Goods.food, 0) for a in destination.agents), 0)
        self.assertEqual(initial_food, sum(a.inv_get(Goods.food, 0) for a in holders)
                         + sum(p.gov.food_inventory for p in provinces))
        self.assertTrue(any(r['kind'] == 'provincial_food_haulage_payment' for r in trace.rows))

    def test_national_relief_respects_player_control_cash_and_blocked_routes(self):
        for gate in ('player', 'disabled', 'cash', 'blocked'):
            with self.subTest(gate=gate):
                nation, provinces, tiles, donor, trace = relief_fixture()
                before = donor.inv_get(Goods.food, 0)
                if gate == 'player':
                    nation.ai = None
                if gate == 'disabled':
                    nation.national_food_logistics_enabled = False
                if gate == 'cash':
                    provinces[0].gov.agent.cash = 0
                    provinces[0].bank.deposits.clear()
                edges = SimpleNamespace(get_friction=lambda *_: float('inf')) if gate == 'blocked' else None
                with patch('terrain_edges.get_edge_manager', return_value=edges):
                    self.assertEqual(dispatch_province_food(provinces[0], 1), [])
                self.assertEqual(donor.inv_get(Goods.food, 0), before)

    def test_cargo_is_retained_if_destination_changes_owner(self):
        nation, provinces, tiles, donor, trace = relief_fixture()
        with patch('terrain_edges.get_edge_manager', return_value=None):
            dispatched = dispatch_province_food(provinces[0], 1)
        foreign = Nation('Foreign')
        tiles[1].owner_nation = foreign
        deliver_province_food(provinces[0], 2)
        self.assertEqual(provinces[0].food_shipments, dispatched)
        self.assertEqual(sum(a.inv_get(Goods.food, 0) for a in tiles[1].agents), 0)

    def test_haulage_is_inside_the_same_turn_actor_account_boundary(self):
        nation, provinces, tiles, donor, trace = relief_fixture()
        source = tiles[0]
        before = {a.id: a.cash for a in source.agents}
        with patch('terrain_edges.get_edge_manager', return_value=None):
            prepare_food_relief(provinces, 1)
        self.assertTrue(provinces[0].food_shipments)
        self.assertEqual(source._economic_opening_turn, 1)
        self.assertEqual(source._economic_opening[donor.id]['cash'], before[donor.id])
        self.assertGreater(donor.cash, before[donor.id])
        # Province.step's idempotent begin_turn must not move the opening
        # balance past the already paid haulage receipt.
        from economy.actor_accounts import begin_turn
        begin_turn(source, 1)
        self.assertEqual(source._economic_opening[donor.id]['cash'], before[donor.id])

    def test_two_source_provinces_do_not_both_cover_the_same_meal_gap(self):
        nation, provinces, tiles, donor, trace = relief_fixture()
        extra_province = Province('Second Surplus Province', nation)
        nation.provinces.append(extra_province)
        extra = Region('Second Surplus', 0, 3, institutions=extra_province.institutions)
        extra_province.add_tile(extra)
        nation.add_tile(extra)
        for person in extra.agents:
            person.calorie_deficit_kcal = 0
            person.inv_set(Goods.food, 0)
        next(a for a in extra.agents if not a.is_government).inv_set(Goods.food, 1000)
        extra.add_neighbor(tiles[1])
        with patch('terrain_edges.get_edge_manager', return_value=None):
            self.assertTrue(dispatch_province_food(provinces[0], 1))
            self.assertEqual(dispatch_province_food(extra_province, 1), [])
        self.assertFalse(extra_province.food_shipments)

    def test_domestic_relief_does_not_cross_foreign_transit_territory(self):
        nation, provinces, tiles, donor, trace = relief_fixture()
        bridge = SimpleNamespace(name='Foreign Bridge', neighbors={tiles[1].name: tiles[1]})
        tiles[0].neighbors = {bridge.name: bridge}
        with patch('terrain_edges.get_edge_manager', return_value=None):
            self.assertEqual(dispatch_province_food(provinces[0], 1), [])
        self.assertEqual(donor.inv_get(Goods.food, 0), 1000)

    def test_a_source_cannot_reuse_its_cart_capacity_for_multiple_destinations(self):
        nation, provinces, tiles, donor, trace = relief_fixture()
        extra_province = Province('Another Hungry Province', nation)
        nation.provinces.append(extra_province)
        extra = Region('Another Hungry', 0, 3, institutions=extra_province.institutions)
        extra_province.add_tile(extra)
        nation.add_tile(extra)
        extra.gov.emergency_food_policy = True
        for person in extra.agents:
            person.calorie_deficit_kcal = 1000
            person.inv_set(Goods.food, 0)
        tiles[0].add_neighbor(extra)
        source_residents = sum(not a.is_government and not a.is_corporation
                               for a in tiles[0].agents)
        with patch('terrain_edges.get_edge_manager', return_value=None):
            shipments = dispatch_province_food(provinces[0], 1)
        self.assertTrue(shipments)
        self.assertLessEqual(sum(s['units'] for s in shipments), max(32, 4 * source_residents))


if __name__ == '__main__':
    unittest.main()
