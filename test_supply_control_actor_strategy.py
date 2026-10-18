"""Named actors and route in a normal seasonal engine step."""
import unittest
import pickle
from types import SimpleNamespace

from economy.actor_accounts import begin_turn, record, seal_turn
from goods import Goods
from scenario_labor_frontier_rivalry import create_world, step_world
from test_supply_rights import Person, Region
from supply_proposals import decide, propose
from economy.capitalist_planner import EliteCapitalistPlanner


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
        grower.inventory[Goods.food] = 7
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
        self.assertEqual((grower.inv_get(Goods.food), mill.inv_get(Goods.food)), (4, 3))

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

    def test_company_scrip_is_recorded_without_faking_cash_wages(self):
        region = Region()
        worker, firm = Person(3, 0), Person(8, 20, Goods.cloth)
        firm.is_corporation = True
        region.agents = [worker, firm]
        begin_turn(region, 5)
        worker.scrip_wallet = 6.0
        record(region, 'scrip_wage', turn=5, payer_id=firm.id,
               recipient_id=worker.id, amount=6,
               detail={'tender': 'company_scrip'})
        rows = {a['actor_id']: a for a in seal_turn(region, 5)}
        self.assertEqual(rows[firm.id]['wages_cash'], 0)
        self.assertEqual(rows[worker.id]['cash_change'], 0)
        self.assertEqual(rows[worker.id]['scrip_change'], 6)
        self.assertEqual(rows[firm.id]['unposted_cash_change'], 0)


class SupplyProposalTests(unittest.TestCase):
    def test_direct_settlement_without_acceptance_is_rejected(self):
        from crop_credit import offer_advance
        from supply_rights import acquire_water_right, transfer_plot_title
        region = Region()
        seller, buyer, grower = Person(1), Person(8, 100), Person(3, 0, Goods.food)
        grower.assigned_plot_id = 'p1'
        region.agents = [seller, buyer, grower]
        self.assertIsNone(transfer_plot_title(region, seller, buyer, 'p1', 30, turn=2))
        self.assertIsNone(acquire_water_right(region, seller, buyer, 'p1', 'p2', .25, 5, 2))
        self.assertIsNone(offer_advance(buyer, grower, region, 8, 3, 'p1'))
        self.assertEqual((seller.cash, buyer.cash, grower.cash), (0, 100, 0))

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

    def test_pending_offer_survives_save_load_without_prepaid_transfer(self):
        region = Region()
        seller, buyer = Person(1, 0), Person(8, 100)
        region.agents = [seller, buyer]
        proposal = propose(region, 'land_sale', buyer, seller, turn=2,
                           price=30, plot_id='p1')
        loaded = pickle.loads(pickle.dumps(region))
        self.assertEqual(loaded.supply_proposals[0]['id'], proposal['id'])
        self.assertEqual((loaded.agents[0].cash, loaded.agents[1].cash), (0, 100))
        decide(loaded, 3)
        self.assertEqual(loaded.tenure.find_plot('p1').lord_id, 8)
        self.assertEqual((loaded.agents[0].cash, loaded.agents[1].cash), (30, 70))

    def test_duplicate_offer_and_lost_buyer_funds_cannot_settle(self):
        region = Region()
        seller, buyer = Person(1, 0), Person(8, 30)
        region.agents = [seller, buyer]
        first = propose(region, 'land_sale', buyer, seller, turn=2,
                        price=30, plot_id='p1')
        self.assertIsNone(propose(region, 'land_sale', buyer, seller, turn=2,
                                  price=30, plot_id='p1'))
        buyer.cash = 5
        decide(region, 3)
        self.assertEqual(first['status'], 'rejected')
        self.assertEqual(region.tenure.find_plot('p1').lord_id, 1)
        self.assertEqual(seller.cash, 0)

    def test_food_plot_keeps_minimum_water_and_contract_food_reserve(self):
        region = Region()
        farmer, buyer = Person(3, 0, Goods.food), Person(8, 100)
        farmer.assigned_plot_id = 'p1'
        region.agents = [farmer, buyer]
        from supply_rights import _seed_water_rights
        _seed_water_rights(region)
        owner = Person(1, 0, Goods.food)
        owner.assigned_plot_id = 'p1'
        region.agents.append(owner)
        self.assertIsNone(propose(region, 'water_right', buyer, owner, turn=2,
                                  price=20, units=.75, from_plot_id='p1',
                                  to_plot_id='p2'))
        region.recipes[Goods.food]['production'] = 8
        self.assertIsNone(propose(region, 'advance_offtake', buyer, farmer, turn=2,
                                  price=10, plot_id='p1', good='food', quantity=5,
                                  unit_price=2, due_turn=4))


class SupplyStrategyTests(unittest.TestCase):
    def _world(self, grower_cash):
        region = Region()
        region.recipes = {Goods.food: {'price': 2.0},
                          Goods.cotton: {'price': 5.0, 'production': 5},
                          Goods.cloth: {'price': 40.0, 'production': 4,
                                        'numInput': 2, 'input': Goods.cotton}}
        grower = Person(3, grower_cash, Goods.cotton)
        grower.assigned_plot_id = 'p1'
        mill = Person(8, 100, Goods.cloth)
        mill.is_corporation = True
        title_holder = Person(1, 20, Goods.food)
        region.agents = [title_holder, grower, mill]
        return region, grower, mill

    def test_secure_grower_outside_option_makes_advance_unprofitable(self):
        region, grower, mill = self._world(20)
        options = EliteCapitalistPlanner()._input_control_options(mill, region)
        advance = next(o for o in options if o['candidate'] == 'advance_offtake')
        lease = next(o for o in options if o['candidate'] == 'lease_input_land')
        self.assertEqual(advance['acceptance_probability'], 0)
        self.assertEqual(advance['score'], 0)
        self.assertFalse(lease['feasible'])
        self.assertIsNone(EliteCapitalistPlanner()._execute_input_control(mill, region, 5))

    def test_cash_poor_grower_makes_advance_valuable(self):
        region, grower, mill = self._world(0)
        planner = EliteCapitalistPlanner()
        options = planner._input_control_options(mill, region)
        advance = next(o for o in options if o['candidate'] == 'advance_offtake')
        self.assertGreater(advance['score'], 0)
        action = planner._execute_input_control(mill, region, 5)
        self.assertEqual(action['action_taken'], 'ADVANCE_OFFTAKE')
        self.assertEqual(region.supply_proposals[0]['status'], 'proposed')
        self.assertEqual(mill.cash, 100)

    def test_negative_unit_margin_pauses_and_releases_workers(self):
        region, grower, mill = self._world(0)
        region.recipes[Goods.cloth]['price'] = 1.0
        region.recipes[Goods.cloth]['production'] = 1
        worker = Person(9, 0)
        worker.employer = mill
        mill.employees = [worker]
        mill.max_employees = 3
        mill.wage = 3.0
        action = EliteCapitalistPlanner()._execute_input_control(mill, region, 5)
        self.assertEqual(action['action_taken'], 'REDUCE_OR_PAUSE_OUTPUT')
        self.assertEqual(mill.max_employees, 0)
        self.assertIsNone(worker.employer)
        self.assertEqual(mill.supply_pause_until, 10)


class SupplyRivalryScenarioTests(unittest.TestCase):
    def test_public_buyer_moves_paid_cash_and_existing_crop(self):
        from scenario_supply_rivalry import create_world, apply_action, project, step_world
        import forex
        world = create_world(seed=812)
        fields = world['by_name']['Cotton Fields']
        self.assertEqual(len([a for a in fields.agents if a.output == Goods.cotton
                              and not a.is_corporation]), 2)
        self.assertEqual(len([a for r in world['tiles'] for a in r.agents
                              if a.is_corporation and a.output == Goods.cloth]), 2)
        self.assertTrue(project(world)['petition_deadline'])
        cash_before = forex.audit_currency_total(world['tiles'], world['currencies'][0])
        public_crop_before = fields.gov.agent.inv_get(Goods.cotton, 0)
        ok, _ = apply_action(world, 'public_crop_purchase')
        self.assertTrue(ok)
        self.assertEqual(fields.gov.agent.inv_get(Goods.cotton, 0), public_crop_before + 2)
        self.assertAlmostEqual(forex.audit_currency_total(world['tiles'], world['currencies'][0]),
                               cash_before, places=6)
        self.assertFalse(step_world(world))

    def test_web_server_exposes_and_executes_supply_decisions(self):
        from sim_server.sim_server import SimServer
        from sim_server.protocol import CommandMessage, CommandType
        server = SimServer(seed=812, scenario_id='supply_rivalry')
        snapshot = server.serialize_world()
        self.assertEqual(snapshot['scenario_info']['scenario_name'], 'Cotton Supply Rivalry')
        self.assertTrue(any(a['id'] == 'approve_charter'
                            for a in snapshot['scenario_info']['actions']))
        response = server.execute_command(CommandMessage(
            CommandType.SCENARIO_ACTION, {'action_id': 'reject_charter'}))
        self.assertTrue(response['success'])
        self.assertEqual(server.by_name['Cotton Fields'].concession_petitions[0]['status'],
                         'rejected')

    def test_desktop_guided_world_uses_same_supply_projection(self):
        from client.desktop.engine import build_world_view
        from client.desktop.panels.scenario_ui import scenario_pressures
        world = build_world_view(seed=812, scenario_id='supply_rivalry')
        self.assertEqual(world['selected_region'].name, 'Cotton Fields')
        self.assertEqual(world['ui_mode'], 'guided')
        self.assertEqual(scenario_pressures(world)[0]['title'], 'Cotton market')

    def test_player_can_repeal_control_after_a_response_turn(self):
        from scenario_supply_rivalry import create_world, apply_action, step_world
        world = create_world(seed=812)
        self.assertTrue(apply_action(world, 'approve_charter')[0])
        fields = world['by_name']['Cotton Fields']
        self.assertEqual(fields.market_charters[0]['status'], 'active')
        step_world(world)
        self.assertTrue(apply_action(world, 'repeal_charter')[0])
        self.assertEqual(fields.market_charters[0]['status'], 'repealed')


if __name__ == '__main__':
    unittest.main()
