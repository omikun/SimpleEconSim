"""Regression checks for the diagnosed food crisis and conserved response."""

import unittest
from unittest.mock import patch

from agent import Agent, initialize_agent
from ai_nation import NationPolicyAI
from economy.labor_mobility import LaborMobilityScheduler, independent_return
from economy.transformation_graph import TransformationGraph
from food_security import diagnose_tile, enact_nation_food_response
from food_logistics import deliver_province_food, dispatch_province_food
from goods import Goods
from government import Government
from land_tenure import LandPlot, TenureStatus
from labor_choice import evaluate_offer
from livelihood_access import effective_access, inherit_customary_access
from nation import Nation
from province import Province
from nutrition import deficit_fraction
from region import Region
from region_market import calculate_ask, calculate_bid, trade
from demographics_consumption import consume_daily_food
from foraging import forage_tile


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        sequence = clock['next']
        clock['next'] += 1
        event_id = f'test:{sequence}'
        self.rows.append({'event_id': event_id, **row})
        return event_id


class FoodSecurityRecoveryTests(unittest.TestCase):
    def test_enclosure_buffer_requires_a_full_crop_cycle(self):
        tile = Region('Cycle', 0, 4)
        tile.production_log[Goods.food] = [10000.0] * 9
        partial = diagnose_tile(tile)
        self.assertEqual(partial['observed_crop_cycle_turns'], 9)
        self.assertFalse(partial['food_buffer_proven'])

        tile.production_log[Goods.food].append(10000.0)
        complete = diagnose_tile(tile)
        self.assertEqual(complete['observed_crop_cycle_turns'], 10)
        self.assertTrue(complete['food_buffer_proven'])
        self.assertGreater(complete['projected_crop_cycle_margin'],
                           complete['crop_cycle_meal_demand'] * 0.1)

    def test_commons_food_does_not_make_enclosure_look_safe(self):
        tile = Region('Commons Buffer', 0, 4)
        tile.production_log[Goods.food] = [0.0] * 10
        with patch('food_security.forecast_commons_food', return_value=10):
            assessment = diagnose_tile(tile)
        self.assertFalse(assessment['food_buffer_proven'])
        self.assertEqual(assessment['accessible_food_buffer'],
                         assessment['household_food_units'] + assessment['government_food_units'])
        self.assertGreater(assessment['projected_crop_cycle_margin_with_commons'],
                           assessment['projected_crop_cycle_margin'])

    def test_imported_luxury_is_not_a_fictitious_independent_income(self):
        tile = Region('Market', 0, 2)
        worker = next(a for a in tile.agents if not a.is_government)
        worker.cash = 10
        plot = LandPlot('market-field', tile.name, worker.id, 0.5,
                        TenureStatus.FEUDAL, tenant_ids=[worker.id])
        tile.tenure.plots = []
        tile.access_rights.clear()
        tile._access_rights_seeded = False
        tile.tenure.add_plot(plot)
        worker.assigned_plot_id = plot.plot_id
        luxury_return, reason = independent_return(tile, worker, Goods.foreign_luxuries, 0)
        farming_return, _ = independent_return(tile, worker, Goods.food, 1)
        furniture_return, _ = independent_return(tile, worker, Goods.furniture, 0)
        self.assertEqual(luxury_return, 0)
        self.assertEqual(reason, 'not locally producible')
        self.assertGreater(farming_return, 0)
        self.assertEqual(furniture_return, 0)

    def test_grower_keeps_a_meal_and_can_buy_when_short(self):
        tile = Region('Grain', 0, 2)
        grower = next(a for a in tile.agents if not a.is_government)
        grower.output = Goods.food
        grower.consumption_multiplier = 1.0
        grower.inv_set(Goods.food, 6)
        self.assertEqual(calculate_ask(tile, grower, Goods.food, 1.0, False), 2)
        grower.inv_set(Goods.food, 2)
        grower.remainingCash = 5.0
        self.assertEqual(calculate_ask(tile, grower, Goods.food, 1.0, False), 0)
        self.assertEqual(calculate_bid(tile, grower, Goods.food, 1.0, 16,
                                       tile.recipes[Goods.food], False, 1.0), 2)

    def test_shared_commons_meal_has_to_be_replaced_by_a_wage(self):
        tile = Region('Commons', 0, 2)
        worker = next(a for a in tile.agents if not a.is_government)
        worker.is_lord = False
        worker.is_trader = False
        worker.employer = None
        worker.social_class = 'commoner'
        worker.inv_set(Goods.food, 0)
        plot = LandPlot('commons-half', tile.name, worker.id, 0.5,
                        TenureStatus.FEUDAL, tenant_ids=[worker.id])
        tile.tenure.plots = []
        tile.access_rights.clear()
        tile._access_rights_seeded = False
        tile.tenure.add_plot(plot)
        worker.assigned_plot_id = plot.plot_id
        forage_tile(tile, 1)
        self.assertEqual(worker.inv_get(Goods.food, 0), 4)
        firm = Agent(0)
        firm.is_corporation = True
        firm.alive = True
        firm.max_employees = 5
        firm.employees = []
        firm.cash = 100
        firm.wage = 3
        self.assertFalse(evaluate_offer(worker, firm, tile, 1, tightness=0).accepted)
        firm.wage = 4.5
        self.assertTrue(evaluate_offer(worker, firm, tile, 1, tightness=0).accepted)

    def test_hungry_worker_with_commons_can_leave_wage_job(self):
        tile = Region('Exit', 0, 2)
        worker = next(a for a in tile.agents if not a.is_government)
        worker.is_lord = False
        worker.is_trader = False
        worker.social_class = 'commoner'
        worker.cash = 0
        worker.hungry_steps = 3
        worker.inv_set(Goods.food, 0)
        plot = LandPlot('exit-half', tile.name, worker.id, 0.5,
                        TenureStatus.FEUDAL, tenant_ids=[worker.id])
        tile.tenure.plots = []
        tile.access_rights.clear()
        tile._access_rights_seeded = False
        tile.tenure.add_plot(plot)
        worker.assigned_plot_id = plot.plot_id
        firm = Agent(0)
        firm.is_corporation = True
        firm.alive = True
        firm.output = Goods.wood
        firm.max_employees = 5
        firm.cash = 100
        firm.wage = 3
        firm.employees = [worker]
        worker.employer = firm
        worker.wage = 3
        tile.agents.append(firm)
        LaborMobilityScheduler().step_labor_cohort(tile, 1)
        self.assertIsNone(worker.employer)
        self.assertNotIn(worker, firm.employees)
        self.assertTrue(any(event['outcome'] == 'lawful exit'
                            for event in tile.labor_events))

    def test_child_inherits_usable_customary_access(self):
        tile = Region('Birthright', 0, 2)
        parent = next(a for a in tile.agents if not a.is_government)
        plot = LandPlot('family-plot', tile.name, parent.id, 0.5,
                        TenureStatus.FEUDAL, tenant_ids=[parent.id])
        tile.tenure.plots = []
        tile.access_rights.clear()
        tile._access_rights_seeded = False
        tile.tenure.add_plot(plot)
        parent.assigned_plot_id = plot.plot_id
        child = Agent(1)
        self.assertTrue(inherit_customary_access(tile, parent, child, 1))
        self.assertEqual(child.assigned_plot_id, plot.plot_id)
        self.assertAlmostEqual(effective_access(child, tile),
                               effective_access(parent, tile))
        plot.tenure = TenureStatus.ENCLOSED
        later_child = Agent(2)
        self.assertFalse(inherit_customary_access(tile, parent, later_child, 2))

    def test_emergency_grain_is_conserved_and_eaten_before_death(self):
        gov = Government('Meal', 0)
        person = Agent(0)
        initialize_agent(person, Goods.wood, 0, 0, 0)
        person.inv_set(Goods.food, 0)
        person.hungry_steps = 4
        gov.food_inventory = 4
        gov.emergency_food_policy = True
        delivered = gov.provide_food_aid(1, [person], 1.0)
        self.assertEqual(delivered, 4)
        self.assertEqual(gov.food_inventory + person.inv_get(Goods.food, 0), 4)
        self.assertEqual(consume_daily_food(person), 4)
        self.assertEqual(deficit_fraction(person), 0)

    def test_emergency_market_buys_paid_surplus_from_former_grower(self):
        tile = Region('Surplus', 0, 3)
        people = [a for a in tile.agents if not a.is_government
                  and not a.is_corporation and not a.is_trader]
        self.assertGreaterEqual(len(people), 2)
        donor, hungry = people[:2]
        for person in people:
            person.output = Goods.wood
            person.inv_set(Goods.food, 0)
            person.cash = 0
        donor.inv_set(Goods.food, 12)
        tile.gov.emergency_food_policy = True
        tile.gov.agent.cash = 20
        trace = MemoryTrace()
        tile._run_trace = trace
        tile._collective_trace_clock = {'turn': 1, 'phase': 'market', 'next': 1}
        before_cash = sum(a.cash + tile.bank.deposits.get(a, 0)
                          for a in (donor, tile.gov.agent))
        before_food = sum(a.inv_get(Goods.food, 0) for a in people) + tile.gov.food_inventory
        trade(tile, 1)
        self.assertGreater(tile.gov.food_inventory, 0)
        self.assertGreater(donor.cash, 0)
        self.assertGreaterEqual(donor.inv_get(Goods.food, 0), 4)
        self.assertAlmostEqual(before_cash,
                               sum(a.cash + tile.bank.deposits.get(a, 0)
                                   for a in (donor, tile.gov.agent)))
        self.assertEqual(before_food, sum(a.inv_get(Goods.food, 0) for a in people)
                         + tile.gov.food_inventory)
        flows = [row for row in trace.rows
                 if row.get('metric_id') == 'finance.treasury_flow'
                 and row.get('kind') == 'government_food_purchase']
        self.assertEqual(len(flows), 1)
        contract = flows[0]['inputs']['transfer_contract']
        self.assertEqual(contract['contract_version'], 'treasury_transfer.v1')
        self.assertEqual(contract['payer_account']['balance_before']
                         - contract['payer_account']['balance_after'],
                         contract['amount'])
        self.assertEqual(contract['payee_account']['balance_after']
                         - contract['payee_account']['balance_before'],
                         contract['amount'])
        self.assertEqual(flows[0]['inputs']['public_food_inventory_after']
                         - flows[0]['inputs']['public_food_inventory_before'],
                         flows[0]['inputs']['quantity'])
        self.assertEqual(flows[0]['inputs']['seller_food_before']
                         - flows[0]['inputs']['seller_food_after'],
                         flows[0]['inputs']['quantity'])
        sale = next(row for row in trace.rows
                    if row.get('kind') == 'government_food_purchase'
                    and row.get('metric_id') == 'goods.sold')
        self.assertIn(flows[0]['event_id'], sale['cause_event_ids'])
        self.assertEqual(sale['inputs']['operation_id'],
                         contract['operation_id'])
        tile.gov.provide_food_aid(1, people, tile.recipes[Goods.food]['price'])
        self.assertGreater(hungry.inv_get(Goods.food, 0), 0)

    def test_emergency_grain_levy_feeds_people_without_creating_food(self):
        tile = Region('Granary', 0, 3)
        people = [a for a in tile.agents if not a.is_government
                  and not a.is_corporation and not a.is_trader]
        donor, hungry = people[:2]
        for person in people:
            person.inv_set(Goods.food, 0)
        donor.inv_set(Goods.food, 40)
        tile.gov.food_inventory = 0
        tile.gov.emergency_food_policy = True
        before = sum(a.inv_get(Goods.food, 0) for a in people)
        delivered = tile.gov.provide_food_aid(1, people, 1.0, region=tile)
        after = sum(a.inv_get(Goods.food, 0) for a in people) + tile.gov.food_inventory
        self.assertEqual(before, after)
        self.assertGreater(delivered, 0)
        self.assertGreater(tile.gov.food_levy_last_turn, 0)
        self.assertGreater(tile.emergency_grain_levy_units, 0)
        self.assertGreaterEqual(donor.inv_get(Goods.food, 0), 4)
        self.assertLessEqual(donor.food_levied_this_turn, 9)
        self.assertGreater(hungry.inv_get(Goods.food, 0), 0)

    def test_nation_food_funding_moves_existing_cash(self):
        nation = Nation('Relief', initial_cash=500)
        tile = Region('Hungry', 0, 10)
        nation.add_tile(tile)
        tile.gov.agent.cash = 0
        for person in tile.agents:
            if not person.is_government and not person.is_corporation:
                person.inv_set(Goods.food, 0)
                person.calorie_deficit_kcal = 1000
        before = nation.government.agent.cash + tile.gov.agent.cash
        response = enact_nation_food_response(nation, 1)[0]
        self.assertEqual(before, nation.government.agent.cash + tile.gov.agent.cash)
        self.assertTrue(tile.gov.emergency_food_policy)
        self.assertGreater(response['funding_transferred'], 0)
        self.assertEqual(response['diagnosis'], 'shortage_and_access')
        self.assertTrue(response['enclosure_risk'])
        enclosure = TransformationGraph.get_operator('enclose_plot_for_pasture')
        lord = next(a for a in tile.agents if not a.is_government)
        lord.is_lord = True
        lord.cash = 100
        allowed, reason = enclosure.can_agent_execute(lord, tile)
        self.assertFalse(allowed)
        self.assertIn('policy', reason)

    def test_shared_province_relief_remains_on_when_neighbor_is_stable(self):
        nation = Nation('Shared', initial_cash=500)
        hungry = Region('Hungry', 0, 4)
        stable = Region('Stable', 0, 4, institutions=hungry._institutions)
        nation.add_tile(hungry)
        nation.add_tile(stable)
        for person in hungry.agents:
            if not person.is_government:
                person.inv_set(Goods.food, 0)
                person.calorie_deficit_kcal = 1000
        for person in stable.agents:
            if not person.is_government:
                person.inv_set(Goods.food, 100)
                person.calorie_deficit_kcal = 0
        responses = enact_nation_food_response(nation, 1)
        self.assertTrue(next(row for row in responses if row['tile'] == 'Hungry')['emergency'])
        self.assertFalse(next(row for row in responses if row['tile'] == 'Stable')['emergency'])
        self.assertTrue(hungry.gov.emergency_food_policy)
        self.assertIs(hungry.gov, stable.gov)

    def test_provincial_grain_takes_a_turn_and_pays_haulers(self):
        nation = Nation('Route', initial_cash=500)
        province = Province('Route Province', nation)
        source = Region('Source', 0, 3, institutions=province.institutions)
        destination = Region('Destination', 0, 3, institutions=province.institutions)
        for tile in (source, destination):
            province.add_tile(tile)
            nation.add_tile(tile)
        source.add_neighbor(destination)
        destination.add_neighbor(source)
        source_people = [a for a in source.agents if not a.is_government
                         and not a.is_corporation and not a.is_trader]
        destination_people = [a for a in destination.agents if not a.is_government
                              and not a.is_corporation and not a.is_trader]
        for person in source_people + destination_people:
            person.inv_set(Goods.food, 0)
        source_people[0].inv_set(Goods.food, 1000)
        for person in destination_people:
            person.calorie_deficit_kcal = 1000
        province.gov.emergency_food_policy = True
        province.gov.agent.cash = 100
        starting_food = 1000
        source_cash_holders = [a for a in source.agents if not a.is_government
                               and not a.is_corporation]
        starting_cash = province.gov.agent.cash + sum(a.cash for a in source_cash_holders)
        shipments = dispatch_province_food(province, 1)
        self.assertTrue(shipments)
        self.assertEqual(shipments[0]['arrival_turn'], 2)
        self.assertEqual(sum(a.inv_get(Goods.food, 0) for a in destination_people), 0)
        self.assertAlmostEqual(starting_cash,
                               province.gov.agent.cash + sum(a.cash for a in source_cash_holders))
        self.assertEqual(starting_food,
                         sum(a.inv_get(Goods.food, 0) for a in source_people)
                         + sum(item['units'] for item in province.food_shipments))
        deliver_province_food(province, 1)
        self.assertTrue(province.food_shipments)
        deliver_province_food(province, 2)
        self.assertFalse(province.food_shipments)
        self.assertGreater(sum(a.inv_get(Goods.food, 0) for a in destination_people), 0)
        self.assertEqual(starting_food,
                         sum(a.inv_get(Goods.food, 0) for a in source_people + destination_people)
                         + province.gov.food_inventory)

    def test_default_server_keeps_selected_nation_player_controlled(self):
        from sim_server.sim_server import SimServer
        class NationStub:
            def __init__(self, name):
                self.name = name
                self.ai = None
        server = object.__new__(SimServer)
        server.scenario_id = None
        server.autoplay_nations = False
        server.nations = [NationStub('Player'), NationStub('Rival')]
        server.player_nation_name = 'Player'
        server._configure_nation_ai()
        self.assertIsNone(server.nations[0].ai)
        self.assertIsInstance(server.nations[1].ai, NationPolicyAI)
        server.player_nation_name = 'Rival'
        server._configure_nation_ai()
        self.assertIsInstance(server.nations[0].ai, NationPolicyAI)
        self.assertIsNone(server.nations[1].ai)


if __name__ == '__main__':
    unittest.main()
