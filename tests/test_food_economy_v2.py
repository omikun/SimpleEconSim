"""Causal acceptance for the replacement economy, independent of old balance."""
import copy
import pickle
import unittest
from collections import defaultdict

from agent import Agent, initialize_agent
from goods import Goods
from region import Region
from land_tenure import LandPlot, TileTenure, TenureStatus
from agriculture import initialize, produce, phase
from food_economy import begin_turn, prepare_work, finish_turn
from food_accounts import balance, transfer, reserve, available, stocks
from households import rebuild, allocate
from demographics_consumption import consume_daily_food
from work_allocation import finish
from foraging import forage_tile


def economy(count=3, *, commons=0):
    region = Region('Acceptance farm', 0, 0, number_of_traders=0)
    region.agents = []
    region.agricultural_area = count * .6
    region.commons_capacity = commons
    region.tenure = TileTenure([LandPlot('field', region.name, -1, 1, TenureStatus.COMMONS)])
    region._access_rights_seeded = False
    region.access_rights = {}
    for _ in range(count):
        person = Agent(0)
        initialize_agent(person, Goods.food, 0, 0, 100)
        person.founding_age_offset = 25
        person.assigned_plot_id = 'field'
        person.region = region.name
        person.home_currency = region.home_currency
        region.agents.append(person)
        region.tenure.plots[0].tenant_ids.append(person.id)
    return region


def domain_turn(region, turn):
    region._last_turn = turn
    begin_turn(region, turn)
    prepare_work(region, turn)
    forage_tile(region, turn)
    finish(region, turn)
    region.production_receipts = []
    totals, receipts = defaultdict(float), {}
    produce(region, turn, totals, receipts)
    allocate(region, turn)
    for person in region.agents:
        if not person.is_government and not person.is_corporation:
            consume_daily_food(person, region=region, turn=turn)
    finish_turn(region, turn)
    return totals


class FoodEconomyTests(unittest.TestCase):
    def test_fixed_point_views_and_checkpoint_have_one_balance(self):
        r = economy(1)
        a = r.agents[0]
        for _ in range(1000):
            a.inv_add(Goods.food, .001)
        self.assertEqual(a.inv_get(Goods.food), 1)
        self.assertEqual(list(a.inventory)[Goods.food], 1)
        restored = pickle.loads(pickle.dumps(a))
        self.assertEqual(restored.inv_get(Goods.food), 1)
        restored.inventory[Goods.food] += .003
        self.assertEqual(restored.inv_get(Goods.food), 1.003)
        self.assertEqual(a.inv_get(Goods.food), 1)

    def test_reserving_and_transferring_never_duplicates_grain(self):
        r = economy(2)
        a, b = r.agents
        a.inv_set(Goods.food, 10)
        reserve(r, a, 'seed', 3)
        self.assertEqual(available(r, a), 7)
        self.assertEqual(transfer(r, a, b, 100), 7)
        self.assertEqual(a.inv_get(Goods.food) + b.inv_get(Goods.food), 10)
        self.assertEqual(a.inv_get(Goods.food), 3)

    def test_wealth_does_not_increase_calories_and_recovery_is_bounded(self):
        from nutrition import appetite_units
        a = economy(1).agents[0]
        a.consumption_multiplier = 1000
        self.assertEqual(appetite_units(a), 4)
        a.energy_reserve_kcal = 0
        self.assertEqual(appetite_units(a), 5)

    def test_prepared_food_substitutes_and_meal_is_idempotent(self):
        r = economy(1)
        a = r.agents[0]
        a.inv_set(Goods.food, 10)
        a.inv_set(Goods.prepared_food, 3)
        self.assertEqual(consume_daily_food(a, region=r, turn=1), 4)
        self.assertEqual(a.inv_get(Goods.food), 9)
        self.assertEqual(a.inv_get(Goods.prepared_food), 0)
        self.assertEqual(consume_daily_food(a, region=r, turn=1), 0)

    def test_renewable_farms_feed_households_for_three_cycles(self):
        r = economy(3)
        for turn in range(1, 31):
            domain_turn(r, turn)
            self.assertTrue(all(a.last_calories_eaten >= 2000 for a in r.agents))
            self.assertTrue(all(a.calorie_deficit_kcal == 0 for a in r.agents))
        self.assertGreater(sum(f['harvest_total'] for f in r.farms.values()), 0)
        self.assertGreater(sum(balance(f) for f in r.farms.values()), 0)
        self.assertTrue(all(row['used'] <= row['available'] + 1e-9 for row in r.work_allocations['people'].values()))

    def test_pantry_does_not_stop_a_committed_crop(self):
        r = economy(1)
        for turn in range(1, 7):
            domain_turn(r, turn)
        other = copy.deepcopy(r)
        other.agents[0].inv_set(Goods.food, 10000)
        first = second = 0
        for turn in range(7, 11):
            first += domain_turn(r, turn)[Goods.food]
            second += domain_turn(other, turn)[Goods.food]
        self.assertGreater(first, 0)
        self.assertEqual(first, second)

    def test_crop_persists_after_occupation_change(self):
        r = economy(1)
        for turn in range(1, 5):
            domain_turn(r, turn)
        farm = next(iter(r.farms.values()))
        planted = copy.deepcopy(farm['crop'])
        r.agents[0].output = Goods.wood
        domain_turn(r, 5)
        self.assertEqual(next(iter(r.farms.values()))['crop']['planted_area'], planted['planted_area'])

    def test_employed_hungry_person_can_forage_but_time_and_capacity_bind(self):
        r = economy(2, commons=2)
        r.food_opening_mode = 'authored'
        employer = Agent(0)
        employer.output = Goods.wood
        employer.is_corporation = True
        for a in r.agents:
            a.employer = employer
        begin_turn(r, 1)
        prepare_work(r, 1)
        gathered = forage_tile(r, 1)
        finish(r, 1)
        self.assertGreater(gathered, 0)
        self.assertLessEqual(gathered, 2)
        self.assertAlmostEqual(sum(a.food_foraged for a in r.agents), gathered)
        for row in r.work_allocations['people'].values():
            self.assertLessEqual(row['used'], row['available'] + 1e-9)
        before = gathered
        r.commons_capacity = 0
        self.assertEqual(forage_tile(r, 1), before)

    def test_stable_livelihood_stays_under_pressure_searches(self):
        from livelihood_viability import assess
        r = economy(1)
        a = r.agents[0]
        a.primary_livelihood = Goods.food
        a.inv_set(Goods.food, 40)
        self.assertFalse(assess(r, a, 1, 10)['seeking'])
        a.cash = 0
        a.inv_set(Goods.food, 0)
        self.assertFalse(assess(r, a, 2, 0)['seeking'])
        self.assertTrue(assess(r, a, 3, 0)['seeking'])
        a.calorie_deficit_kcal = 500
        self.assertEqual(assess(r, a, 4, 100)['reason'], 'meal_failure')

    def test_strike_does_not_prohibit_subsistence_and_hunger_can_recover(self):
        r = economy(1, commons=100)
        r.food_opening_mode = 'authored'
        a = r.agents[0]
        a.is_striking = True
        a.hungry_steps = 70
        a.energy_reserve_kcal = 0
        a.output = Goods.wood
        domain_turn(r, 1)
        self.assertGreaterEqual(a.last_calories_eaten, 2000)
        self.assertGreater(a.energy_reserve_kcal, 0)
        self.assertEqual(r.work_allocations['people'][a.id]['activities'].get('main', 0), 0)

    def test_closed_company_remains_an_entity(self):
        from region_labor import close_firm
        r = economy(1)
        a = Agent(0)
        a.is_corporation = True
        a.owner = r.agents[0]
        a.owner.company_owned = a
        a.cash = 7
        a.inv_set(Goods.food, 3)
        r.agents.append(a)
        before = stocks(r)['total']
        close_firm(r, a, 1)
        self.assertTrue(a.is_corporation)
        self.assertTrue(a.business_closed)
        self.assertIsNone(a.owner.company_owned)
        self.assertEqual(stocks(r)['total'], before)

    def test_public_program_is_funded_and_expires_with_refund(self):
        from production_policy import submit, settle_programs
        r = economy(1)
        r.gov.agent.cash = 100
        before = sum(a.cash for a in r.agents) + r.gov.agent.cash
        p = submit(r, 'procurement', 'wood', 10, 25, 1, 0)
        self.assertEqual(r.gov.agent.cash, 75)
        self.assertEqual(sum(a.cash for a in r.agents) + r.gov.agent.cash, before)
        settle_programs(r, 1)
        self.assertEqual(p['status'], 'expired')
        self.assertEqual(r.gov.agent.cash, 100)

    def test_local_accounts_close_for_three_cycles_without_unexplained_food(self):
        from food_audit import open_turn, close_turn
        r = economy(3)
        for turn in range(1, 31):
            from food_economy import prepare_region
            prepare_region(r, turn)
            opening = open_turn([r], [], turn)
            domain_turn(r, turn)
            row = close_turn([r], [], opening)
            self.assertEqual(row['unexplained'], 0, row)

    def test_migration_plans_a_household_and_arrives_at_next_boundary(self):
        from migration import run_migrations, arrive_subsistence_moves
        source, destination = economy(1), economy(1, commons=100)
        destination.name = 'Nearby commons'
        source.neighbors = {destination.name: destination}
        destination.neighbors = {source.name: source}
        source.tenure.plots[0].tenure = TenureStatus.ENCLOSED
        person = source.agents[0]
        person.cash = 0
        person.inv_set(Goods.food, 0)
        destination.agents[0].inv_set(Goods.food, 40)
        child = Agent(1)
        child.is_native_child = True
        child.parent = person
        source.agents.append(child)
        events = run_migrations(1, [source, destination])
        self.assertEqual(len(events), 1)
        self.assertIn(person, source.agents)
        self.assertEqual(source.subsistence_journeys[0]['member_ids'], [person.id, child.id])
        arrive_subsistence_moves(2, [source, destination])
        self.assertNotIn(person, source.agents)
        self.assertIn(person, destination.agents)
        self.assertIn(child, destination.agents)
        self.assertEqual(person.output, Goods.food)

    def test_enforced_movement_policy_discourages_subsistence_migration(self):
        from migration import run_migrations
        source, destination = economy(1), economy(1, commons=100)
        destination.name = 'Restricted commons'
        source.neighbors = {destination.name: destination}
        source.tenure.plots[0].tenure = TenureStatus.ENCLOSED
        person = source.agents[0]
        person.cash = 0
        destination.agents[0].inv_set(Goods.food, 40)
        source.movement_policy = {'permit_required': True, 'enforcement': .5}
        self.assertEqual(run_migrations(1, [source, destination]), [])
        self.assertEqual(source.subsistence_migration_log[-1]['reason'], 'deterred_by_movement_law')

    def test_procurement_requires_owned_goods_and_actual_payment(self):
        from production_policy import submit, settle_programs
        r = economy(1)
        seller = r.agents[0]
        seller.output = Goods.wood
        seller.inv_set(Goods.wood, 5)
        r.gov.agent.cash = 100
        before = seller.cash + r.gov.agent.cash
        p = submit(r, 'procurement', 'wood', 3, 10, 2, 0)
        settle_programs(r, 1)
        escrow = next(a for a in r.agents if a.id == p['escrow_id'])
        self.assertEqual(p['status'], 'completed')
        self.assertEqual(seller.inv_get(Goods.wood), 2)
        self.assertEqual(escrow.inv_get(Goods.wood), 3)
        self.assertAlmostEqual(seller.cash + r.gov.agent.cash + escrow.cash, before)
        self.assertGreater(p['spent'], 0)

    def test_shared_public_store_is_located_and_cannot_teleport(self):
        r, other = economy(1), economy(1)
        other.name = 'Other district'
        other.gov = r.gov
        r.gov.receive_food(10, r)
        r.gov.bind_food_site(other)
        self.assertEqual(r.gov.food_at(r), 10)
        self.assertEqual(r.gov.food_at(other), 0)
        self.assertEqual(r.gov.food_inventory, 10)

    def test_outlook_and_economic_needs_are_read_only(self):
        from food_outlook import snapshot
        from production_needs import needs
        r = economy(2)
        domain_turn(r, 1)
        before = pickle.dumps(r)
        f = snapshot(r)
        needs(r)
        self.assertEqual(pickle.dumps(r), before)
        self.assertIsNone(f['farm_support_adult_equivalents'])
        self.assertIsNone(f['support_for_others'])

    def test_checkpoint_keeps_crops_reservations_and_phase_guards(self):
        r = economy(2)
        for turn in range(1, 7):
            domain_turn(r, turn)
        restored = pickle.loads(pickle.dumps(r))
        for turn in range(7, 21):
            domain_turn(r, turn)
            domain_turn(restored, turn)
        self.assertEqual(r.food_history, restored.food_history)
        self.assertEqual(r.farms, restored.farms)
        self.assertEqual([a.inventory for a in r.agents], [a.inventory for a in restored.agents])

    def test_next_harvest_window_includes_remaining_phase_seven(self):
        from food_outlook import snapshot
        r = economy(1)
        for t in range(1, 10):
            domain_turn(r, t)
        forecast = snapshot(r)
        next_row = forecast['stock_path'][0]
        self.assertEqual(next_row['phase'], 7)
        self.assertGreater(next_row['committed_harvest'], 0)
        actual = domain_turn(r, 10)[Goods.food]
        self.assertAlmostEqual(next_row['committed_harvest'], actual, places=3)

    def test_new_cultivators_share_land_and_storage_without_creating_either(self):
        from agriculture import ensure_operations
        r = economy(1)
        initialize(r, 1)
        area = sum(f['area'] for f in r.farms.values())
        storage = sum(f['storage_capacity'] for f in r.farms.values())
        entrant = Agent(0)
        initialize_agent(entrant, Goods.food, 0, 10, 10)
        entrant.founding_age_offset = 25
        entrant.assigned_plot_id = 'field'
        r.agents.append(entrant)
        r.tenure.plots[0].tenant_ids.append(entrant.id)
        ensure_operations(r, 3)
        self.assertAlmostEqual(sum(f['area'] for f in r.farms.values()), area)
        self.assertAlmostEqual(sum(f['storage_capacity'] for f in r.farms.values()), storage)
        self.assertTrue(all(f['area'] > 0 for f in r.farms.values()))

    def test_seed_is_purchased_before_sowing_in_the_canonical_turn(self):
        from micro.region.stepper import step_economy
        r = economy(2)
        r.food_opening_mode = 'authored'
        farmer, seller = r.agents
        farmer.inv_set(Goods.food, 0)
        seller.output = Goods.wood
        seller.inv_set(Goods.food, 100)
        step_economy(r, 3)
        crops = [f['crop'] for f in r.farms.values() if f.get('crop')]
        self.assertTrue(crops)
        self.assertGreater(sum(c['seed_used'] for c in crops), 0)
        self.assertGreater(sum(c['sow_work'] for c in crops), 0)

    def test_private_enclosed_estate_can_pay_real_temporary_farm_work(self):
        r = economy(4)
        owner = r.agents[0]
        owner.is_lord = True
        owner.output = Goods.furniture
        owner.cash = 1000
        r.tenure.plots[0].tenure = TenureStatus.ENCLOSED
        r.tenure.plots[0].lord_id = owner.id
        r.tenure.plots[0].controlled_by_id = owner.id
        for a in r.agents[1:]:
            a.output = Goods.wood
        domain_turn(r, 1)
        owner.inv_set(Goods.food, 20)
        owner.health_attrition = 3
        for t in range(2, 5):
            domain_turn(r, t)
        farm = next(f for f in r.farms.values() if f['operator_id'] == owner.id)
        self.assertGreater(farm['crop']['sow_work'], .5)
        self.assertTrue(any(o['delivered'] > 0 for o in r.seasonal_work_orders))
        self.assertTrue(all(a.output == Goods.wood for a in r.agents[1:]))

    def test_army_cannot_eat_remote_public_grain(self):
        from army import MilitaryUnit
        r, remote = economy(1), economy(1)
        remote.name = 'Remote grain'
        gov = r.gov
        gov.receive_food(10, remote)
        unit = MilitaryUnit('garrison', 'Test', r.name, 2, wage_per_soldier=0, food_per_soldier=1)
        _, consumed, supplied, _ = unit.pay_and_feed(gov, None, t=1, trace_region=r)
        self.assertEqual(consumed, 0)
        self.assertFalse(supplied)
        self.assertEqual(gov.food_at(remote), 10)

    def test_crop_inputs_are_consumed_once_and_queries_cannot_consume_them(self):
        from agriculture import yield_factor, commit_crop_inputs
        r = economy(1)
        for t in range(1, 5):
            domain_turn(r, t)
        r.use_fertilizer = True
        r._last_turn = 5
        before = r.fertilizer_stock
        plain = yield_factor(r, r.agents[0], 5)
        commit_crop_inputs(r, 5)
        used = before - r.fertilizer_stock
        self.assertGreater(used, 0)
        self.assertGreater(yield_factor(r, r.agents[0], 5), plain)
        for _ in range(5):
            yield_factor(r, r.agents[0], 5)
            commit_crop_inputs(r, 5)
        self.assertEqual(r.fertilizer_stock, before - used)

    def test_fractional_duration_is_rejected_before_public_money_moves(self):
        from production_policy import submit
        r = economy(1)
        r.gov.agent.cash = 100
        with self.assertRaises(ValueError):
            submit(r, 'procurement', 'wood', 5, 25, 1.7, 0)
        self.assertEqual(r.gov.agent.cash, 100)
        self.assertFalse(getattr(r, 'production_programs', []))

    def test_installed_harvest_machinery_reduces_work_without_creating_crop_yield(self):
        from buildings import Building, BUILDING_RECIPES
        from agriculture import requirements
        plain = economy(1)
        plain.scenario_owner_policy = True  # Hold skill accumulation fixed.
        domain_turn(plain, 1)
        powered = copy.deepcopy(plain)
        machine = Building('mechanized_harvesting_prototype',
                           BUILDING_RECIPES['mechanized_harvesting_prototype'], 0, powered.name)
        machine.private_owner_id = powered.agents[0].id
        powered.buildings.append(machine)
        work_plain = work_powered = harvest_plain = harvest_powered = 0
        for t in range(2, 11):
            harvest_plain += domain_turn(plain, t)[Goods.food]
            harvest_powered += domain_turn(powered, t)[Goods.food]
            work_plain += sum(row['used'] for row in plain.work_allocations['people'].values())
            work_powered += sum(row['used'] for row in powered.work_allocations['people'].values())
        self.assertGreater(harvest_plain, 0)
        self.assertAlmostEqual(harvest_plain, harvest_powered, places=3)
        self.assertLess(work_powered, work_plain)

    def test_migration_is_not_prevented_by_cash_when_no_food_is_reachable(self):
        from migration import run_migrations
        source, destination = economy(1), economy(1, commons=100)
        destination.name = 'Open commons'
        source.neighbors = {destination.name: destination}
        source.tenure.plots[0].tenure = TenureStatus.ENCLOSED
        source.agents[0].cash = 100
        source.agents[0].inv_set(Goods.food, 0)
        self.assertEqual(len(run_migrations(1, [source, destination])), 1)

    def test_food_processing_cannot_multiply_calories_with_productivity(self):
        from abundance import produce_workshop
        from food_audit import physical_stock
        r = economy(1)
        person = r.agents[0]
        person.output = Goods.prepared_food
        person.inv_set(Goods.food, 40)
        recipe = r.recipes[Goods.prepared_food]
        person.inv_set(recipe['setup_good'], recipe['setup_units'])
        before = physical_stock([r])
        produce_workshop(r, person, {**recipe, 'production': recipe['production'] * 10}, {}, [], 1)
        self.assertGreater(person.inv_get(Goods.prepared_food), 0)
        self.assertLessEqual(physical_stock([r]), before)

    def test_farm_uses_its_water_right_and_operating_company_equipment(self):
        from agriculture import yield_factor
        from buildings import Building, BUILDING_RECIPES
        r = economy(2)
        begin_turn(r, 1)
        person, other = r.agents
        firm = Agent(0)
        firm.is_corporation = True
        firm.output = Goods.food
        firm.owner = person
        person.company_owned = firm
        r.agents.append(firm)
        farm = next(f for f in r.farms.values() if f['operator_id'] == person.id)
        base = yield_factor(r, person, 1, farm=farm)
        installation = Building('crop_rotation_prototype', BUILDING_RECIPES['crop_rotation_prototype'], 0, r.name)
        installation.private_owner_id = firm.id
        r.buildings.append(installation)
        self.assertGreater(yield_factor(r, person, 1, farm=farm), base)
        self.assertAlmostEqual(yield_factor(r, other, 1, farm=farm), base)
        person.assigned_plot_id = None
        self.assertGreater(yield_factor(r, person, 1, farm=farm), base)

    def test_funded_seasonal_work_pays_a_worker_without_reclassifying_them(self):
        from production_policy import submit, prepare_programs, settle_programs
        r = economy(2)
        r.agents[1].output = Goods.wood
        domain_turn(r, 1)
        farmer, worker = r.agents
        farmer.inv_set(Goods.food, 0)
        farmer.cash = 0
        farmer.is_striking = True
        r.gov.agent.cash = 100
        program = submit(r, 'seasonal_hiring', 'food', 2, 100, 5, 1)
        domain_turn(r, 2)
        cash_before = worker.cash
        prepare_programs(r, 3)
        domain_turn(r, 3)
        settle_programs(r, 3)
        self.assertGreater(program['delivered'], 0)
        self.assertGreater(worker.cash, cash_before)
        self.assertEqual(worker.output, Goods.wood)

    def test_refreshing_customary_rights_cannot_undo_an_enforced_closure(self):
        from livelihood_access import seed_access_rights
        from foraging import can_forage
        r = economy(1, commons=100)
        seed_access_rights(r)
        person = r.agents[0]
        right = next(right for right in r.access_rights[person.id] if right.resource == 'commons_food')
        right.legal_share = right.usable_share = 0
        r._access_rights_seeded = False
        seed_access_rights(r)
        self.assertEqual(right.usable_share, 0)
        self.assertFalse(can_forage(person, r))


if __name__ == '__main__':
    unittest.main()
