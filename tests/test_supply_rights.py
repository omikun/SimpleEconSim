from types import SimpleNamespace
import unittest
import pickle

from crop_credit import settle_offtake_contracts
from goods import Goods
from land_tenure import LandPlot, TileTenure, TenureStatus
from market_concessions import (decide_concession_petitions, filter_chartered_bids,
                                submit_concession_petition)
from supply_rights import (acquire_water_right, allocate_seasonal_water,
                           transfer_plot_title, water_yield_factor)
from supply_proposals import propose, decide


class Person:
    def __init__(self, ident, cash=0, output=Goods.food):
        self.id = ident
        self.cash = cash
        self.output = output
        self.alive = True
        self.is_government = False
        self.is_corporation = False
        self.inventory = {Goods.food: 0}
        self.land_plots = []

    def inv_add(self, good, quantity):
        self.inventory[good] = self.inventory.get(good, 0) + quantity

    def inv_get(self, good, default=0):
        return self.inventory.get(good, default)


class Region:
    def __init__(self):
        self.name = 'Test'
        self.tenure = TileTenure([
            LandPlot('p1', 'Test', 1, .5, TenureStatus.FEUDAL, tenant_ids=[3]),
            LandPlot('p2', 'Test', 2, .5, TenureStatus.FEUDAL, tenant_ids=[4]),
        ])
        self.agents = []
        self.recipes = {Goods.food: {'price': 2.0}}
        self.cash_obligations = []
        self.production_receipts = []


class SupplyRightsTests(unittest.TestCase):
  def test_corporation_planner_uses_advance_offtake_for_an_input_shortage(self):
    from economy.capitalist_planner import EliteCapitalistPlanner
    from goods import Goods
    region = Region()
    region.recipes = {Goods.food: {'price': 2.0}, Goods.cotton: {'price': 5.0},
                      Goods.cloth: {'price': 40.0, 'input': Goods.cotton,
                                    'numInput': 2, 'production': 4}}
    grower = Person(3, 1, Goods.cotton)
    grower.assigned_plot_id = 'p1'
    firm = Person(8, 100, Goods.cloth)
    firm.is_corporation = True
    region.agents = [grower, firm]
    action = EliteCapitalistPlanner()._execute_input_control(firm, region, 3)
    self.assertEqual(action['action_taken'], 'ADVANCE_OFFTAKE')
    self.assertEqual(firm.cash, 100)
    self.assertEqual(grower.cash, 1)
    from supply_proposals import decide
    decide(region, 4)
    self.assertEqual(firm.cash, 90)
    self.assertEqual(grower.cash, 11)
    self.assertEqual(region.offtake_contracts[0]['remaining'], 2)
    self.assertEqual(region.offtake_contracts[0]['good'], 'cotton')

  def test_land_title_transfer_pays_seller_and_preserves_tenant_rights(self):
    region = Region()
    seller, buyer = Person(1, 0), Person(9, 100)
    region.agents = [seller, buyer]
    proposal = propose(region, 'land_sale', buyer, seller, turn=3,
                       price=30, plot_id='p1')
    decide(region, 4)
    ev = proposal['result']
    self.assertEqual(ev['basis'], 'voluntary_sale')
    self.assertEqual(region.tenure.find_plot('p1').lord_id, 9)
    self.assertEqual(region.tenure.find_plot('p1').tenant_ids, [3])
    self.assertEqual((buyer.cash, seller.cash), (70, 30))


  def test_water_right_transfer_changes_real_plot_allocation(self):
    region = Region()
    seller, buyer = Person(1), Person(9, 100)
    region.agents = [seller, buyer]
    allocate_seasonal_water(region, 1)
    before = water_yield_factor(region, SimpleNamespace(assigned_plot_id='p1'))
    proposal = propose(region, 'water_right', buyer, seller, turn=1,
                       from_plot_id='p1', to_plot_id='p2', units=.5, price=20)
    decide(region, 2)
    ev = proposal['result']
    self.assertEqual(ev['units'], .5)
    allocation = allocate_seasonal_water(region, 2)
    self.assertEqual((allocation['p1'], allocation['p2']), (.5, 1.5))
    self.assertLess(water_yield_factor(region, SimpleNamespace(assigned_plot_id='p1')), before)
    self.assertEqual(water_yield_factor(region, SimpleNamespace(assigned_plot_id='p2')), 1.25)
    self.assertEqual((buyer.cash, seller.cash), (80, 20))


  def test_offtake_delivers_only_real_harvest_and_mutates_spot_receipt(self):
    region = Region()
    grower, mill = Person(3), Person(8, 20)
    grower.inventory[Goods.food] = 7
    region.agents = [grower, mill]
    region.production_receipts = [{'turn': 2, 'person_id': 3, 'good': Goods.food, 'quantity': 5}]
    region.cash_obligations = [SimpleNamespace(id=7, balance=4.0, status='active')]
    region.offtake_contracts = [{
        'id': 1, 'lender_id': 8, 'grower_id': 3, 'good': 'food', 'quantity': 3,
        'remaining': 3, 'unit_price': 2.0, 'due_turn': 2, 'claim_id': 7, 'status': 'active'
    }]
    events = settle_offtake_contracts(region, 2)
    self.assertEqual(events[0]['quantity'], 3)
    self.assertEqual((grower.inv_get(Goods.food), mill.inv_get(Goods.food)), (4, 3))
    self.assertEqual(region.production_receipts[0]['quantity'], 2)
    self.assertEqual((grower.cash, mill.cash), (2, 18))
    self.assertEqual(region.cash_obligations[0].balance, 0)


  def test_charter_requires_public_decision_and_filters_competing_bids(self):
    region = Region()
    region.recipes[Goods.cotton] = {'price': 5.0}
    gov, mill, rival = Person(20, 50), Person(21, 100), Person(22, 100)
    region.gov = SimpleNamespace(agent=gov)
    region.agents = [gov, mill, rival]
    region.government_legitimacy = .8
    petition = submit_concession_petition(mill, region, Goods.cotton,
                                           'exclusive_buying', 10, 20, 1)
    self.assertTrue(petition)
    self.assertEqual((mill.cash, gov.cash), (90, 60))
    self.assertFalse(getattr(region, 'market_charters', []))
    events = decide_concession_petitions(region, 2)
    self.assertEqual(events[0]['status'], 'enacted')
    filtered = filter_chartered_bids(region, Goods.cotton, [
        {'agent': mill, 'quantity': 10}, {'agent': rival, 'quantity': 10}], 2)
    self.assertEqual([row['agent'].id for row in filtered], [21, 22])
    self.assertEqual(filtered[1]['quantity'], 3)
    for turn in range(3, 11):
      filter_chartered_bids(region, Goods.cotton, [
          {'agent': mill, 'quantity': 10}, {'agent': rival, 'quantity': 10}], turn)
    repeal = decide_concession_petitions(region, 11)
    self.assertEqual(repeal[-1]['status'], 'repealed')
    self.assertEqual(repeal[-1]['reason'], 'opposition_or_unrest')

  def test_rights_and_future_contract_survive_pickle_save_load(self):
    region = Region()
    seller, buyer = Person(1), Person(9, 50)
    region.agents = [seller, buyer]
    propose(region, 'water_right', buyer, seller, turn=0,
            from_plot_id='p1', to_plot_id='p2', units=.25, price=5)
    decide(region, 1)
    region.offtake_contracts = [{'id': 7, 'good': 'cotton', 'grower_id': 3,
                                 'lender_id': 9, 'remaining': 4, 'status': 'active',
                                 'due_turn': 8}]
    loaded = pickle.loads(pickle.dumps(region))
    self.assertEqual(loaded.water_rights, region.water_rights)
    self.assertEqual(loaded.offtake_contracts, region.offtake_contracts)

  def test_route_charter_restricts_unlicensed_physical_shipment(self):
    from agent import Agent, initialize_agent
    from region_logistics import post_exports_to_route
    from transporter import Route
    source, destination = SimpleNamespace(name='Source'), SimpleNamespace(name='Destination')
    source._last_turn = 2
    source.routes = {}
    source.trader_agents = []
    source.neighbors = {}
    source.transport_delay = 1
    source.market_charters = [{'id': 1, 'good': Goods.cotton.value,
                               'type': 'exclusive_route', 'sponsor_id': 99,
                               'start_turn': 0, 'expiry_turn': 10,
                               'enforcement': .6, 'status': 'active'}]
    route = Route('Source->Destination', source, destination, base_delay=1)
    source.routes[destination.name] = route
    trader = Agent(0)
    initialize_agent(trader, Goods.food, 0, 0, 20)
    trader.is_trader = True
    trader.destination_region = destination
    trader.inventory_export[Goods.cotton.value] = 10
    source.trader_agents.append(trader)
    post_exports_to_route(source)
    self.assertEqual(trader.inventory_export[Goods.cotton.value], 6)
    self.assertEqual(route.pending[0][2], 4)


if __name__ == '__main__':
    unittest.main()
