"""Named actors and route in a normal seasonal engine step."""
import unittest
from types import SimpleNamespace

from economy.actor_accounts import begin_turn, record, seal_turn
from goods import Goods
from scenario_labor_frontier_rivalry import create_world, step_world
from test_supply_rights import Person, Region
from supply_proposals import decide, propose


class SupplyControlActorFixtureTests(unittest.TestCase):
    def test_two_growers_two_mills_and_route_survive_normal_tick(self):
        world = create_world(seed=612)
        fields = world['by_name']['Meridian Fields']
        works = world['by_name']['Meridian Works']
        rival_works = world['by_name']['Vesper Works']
        growers = [a for a in fields.agents if a.output == Goods.cotton
                   and not a.is_corporation and getattr(a, 'alive', True)]
        mills = [a for r in (works, rival_works) for a in r.agents
                 if a.is_corporation and a.output == Goods.cloth]
        self.assertGreaterEqual(len(growers), 2)
        self.assertEqual(len(mills), 2)
        self.assertIn('Meridian Works', fields.routes)
        self.assertIn('Vesper Fields', fields.routes)
        named = [growers[0], growers[1], mills[0], mills[1]]
        before = {a.id: (a.cash, a.inv_get(a.output, 0)) for a in named}
        violations = step_world(world)
        self.assertFalse(violations)
        self.assertEqual(world['turn'], 1)
        for a in named:
            self.assertIn(a.id, before)
            self.assertTrue(any(person.id == a.id for person in
                                (fields if a in growers else works if a is mills[0]
                                 else rival_works).agents))
            home = fields if a in growers else works if a is mills[0] else rival_works
            self.assertTrue(any(row['actor_id'] == a.id for row in home.actor_turn_accounts))

    def test_poor_water_year_reduces_named_plot_allocation(self):
        world = create_world(seed=612)
        fields = world['by_name']['Meridian Fields']
        from supply_rights import allocate_seasonal_water
        normal = sum(allocate_seasonal_water(fields, 1).values())
        fields.seasonal_rainfall = 0.4
        drought = sum(allocate_seasonal_water(fields, 2).values())
        self.assertLess(drought, normal)


class ActorAccountTests(unittest.TestCase):
    def test_contract_cash_and_debt_credit_are_separate(self):
        from crop_credit import settle_offtake_contracts
        region = Region()
        grower, mill = Person(3), Person(8, 20)
        region.agents = [grower, mill]
        grower.inventory[Goods.food] = 5
        region.production_receipts = [{'turn': 2, 'person_id': 3,
                                       'good': Goods.food, 'quantity': 5}]
        region.cash_obligations = [SimpleNamespace(id=7, balance=4.0,
                                                   status='active', debtor_id=3,
                                                   creditor_id=8)]
        region.offtake_contracts = [{'id': 1, 'lender_id': 8, 'grower_id': 3,
                                     'good': 'food', 'quantity': 3, 'remaining': 3,
                                     'unit_price': 2.0, 'due_turn': 2, 'claim_id': 7,
                                     'status': 'active'}]
        begin_turn(region, 2)
        settle_offtake_contracts(region, 2)
        accounts = {a['actor_id']: a for a in seal_turn(region, 2)}
        self.assertEqual(accounts[3]['sales_cash'], 2)
        self.assertEqual(accounts[3]['crop_value'], 6)
        self.assertEqual(accounts[3]['opening_debt'], 4)
        self.assertEqual(accounts[3]['closing_debt'], 0)
        self.assertEqual(accounts[8]['purchases_cash'], 2)
        self.assertEqual((grower.cash, mill.cash), (2, 18))
        self.assertEqual((grower.inv_get(Goods.food), mill.inv_get(Goods.food)), (2, 3))

    def test_owner_financing_changes_cash_without_recorded_profit(self):
        region = Region()
        owner, firm = Person(1, 100), Person(8, 10, Goods.cloth)
        firm.is_corporation = True
        region.agents = [owner, firm]
        begin_turn(region, 4)
        owner.cash -= 15
        firm.cash += 15
        record(region, 'owner_financing', turn=4, payer_id=1, recipient_id=8,
               amount=15)
        account = next(a for a in seal_turn(region, 4) if a['actor_id'] == 8)
        self.assertEqual(account['cash_change'], 15)
        self.assertEqual(account['owner_financing_received'], 15)
        self.assertEqual(account['operating_result_recorded'], 0)


class SupplyProposalTests(unittest.TestCase):
    def test_secure_grower_refuses_low_offtake_without_transfer(self):
        region = Region()
        region.recipes[Goods.cotton] = {'price': 5.0, 'production': 5}
        grower, mill = Person(3, 20, Goods.cotton), Person(8, 100, Goods.cloth)
        grower.assigned_plot_id = 'p1'
        region.agents = [grower, mill]
        proposal = propose(region, 'advance_offtake', mill, grower, turn=2,
                           price=10, plot_id='p1', good='cotton', quantity=2,
                           unit_price=2, due_turn=4)
        self.assertEqual((grower.cash, mill.cash), (20, 100))
        decide(region, 3)
        self.assertEqual(proposal['status'], 'rejected')
        self.assertEqual((grower.cash, mill.cash), (20, 100))
        self.assertFalse(region.cash_obligations)

    def test_cash_poor_grower_accepts_useful_advance(self):
        region = Region()
        region.recipes[Goods.cotton] = {'price': 5.0, 'production': 5}
        grower, mill = Person(3, 0, Goods.cotton), Person(8, 100, Goods.cloth)
        grower.assigned_plot_id = 'p1'
        region.agents = [grower, mill]
        proposal = propose(region, 'advance_offtake', mill, grower, turn=2,
                           price=10, plot_id='p1', good='cotton', quantity=2,
                           unit_price=3, due_turn=4)
        decide(region, 3)
        self.assertEqual(proposal['status'], 'settled')
        self.assertEqual((grower.cash, mill.cash), (10, 90))
        self.assertEqual(region.offtake_contracts[0]['remaining'], 2)

    def test_title_holder_counters_and_can_refuse(self):
        region = Region()
        seller, buyer = Person(1, 0), Person(8, 100)
        region.agents = [seller, buyer]
        low = propose(region, 'land_sale', buyer, seller, turn=2,
                      price=8, plot_id='p1')
        decide(region, 3)
        self.assertEqual(low['status'], 'rejected')
        self.assertEqual(region.tenure.find_plot('p1').lord_id, 1)
        offer = propose(region, 'land_sale', buyer, seller, turn=3,
                        price=18, plot_id='p1', max_price=25)
        decide(region, 4)
        self.assertEqual(offer['status'], 'countered')
        decide(region, 5)
        self.assertEqual(offer['status'], 'settled')
        self.assertEqual(region.tenure.find_plot('p1').lord_id, 8)
        self.assertEqual((seller.cash, buyer.cash), (20, 80))

    def test_water_holder_can_refuse_diversion(self):
        region = Region()
        seller, buyer = Person(1), Person(8, 100)
        region.agents = [seller, buyer]
        proposal = propose(region, 'water_right', buyer, seller, turn=2,
                           price=0, units=.5, from_plot_id='p1',
                           to_plot_id='p2')
        decide(region, 3)
        self.assertEqual(proposal['status'], 'rejected')
        self.assertEqual(next(r.units for r in region.water_rights
                              if r.plot_id == 'p1' and r.holder_id == 1), 1.0)


if __name__ == '__main__':
    unittest.main()
