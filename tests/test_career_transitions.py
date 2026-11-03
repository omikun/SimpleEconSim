"""Behavioral checks for the shared career market and protected professions."""
import copy
import unittest
from unittest.mock import patch

from agent import Agent, initialize_agent
from goods import Goods
from region import Region
from labor_choice import LaborDecision, apply_career_switch, attach_worker
from career_transitions import begin_turn, prepare_budgets, populations, step_careers


def fixture(count=10):
    region = Region('Career market', 0)
    people = []
    for _ in range(count):
        person = Agent(0)
        initialize_agent(person, Goods.food, 0, 0, 100)
        person.founding_age_offset = 25
        person.is_lord = False
        people.append(person)
    region.agents = people[:]
    return region, people


def firm(region, *, good=Goods.wood, wage=100, cash=100000, slots=100):
    employer = Agent(0)
    initialize_agent(employer, good, 0, 0, cash)
    employer.is_corporation = True
    employer.wage, employer.max_employees = wage, slots
    employer.employees = []
    region.agents.append(employer)
    return employer


class CareerTransitionTests(unittest.TestCase):
    def test_lucrative_moves_scale_with_population_above_floor(self):
        for count, gain, expected in ((50, 1, 4), (50, 2.5, 11), (10, 1, 0), (4, 9, 0)):
            region, _ = fixture(count)
            state = prepare_budgets(region, 1, {'food': gain})
            self.assertEqual(state['budgets']['food']['quota'], expected)

    def test_fractional_carry_reaches_four_and_stops(self):
        region, people = fixture(5)
        for turn in range(1, 10):
            prepare_budgets(region, turn, {'food': 1})
            self.assertFalse(apply_career_switch(region, people[0], Goods.wood, turn))
        prepare_budgets(region, 10, {'food': 1})
        self.assertTrue(apply_career_switch(region, people[0], Goods.wood, 10))
        for turn in range(11, 25):
            prepare_budgets(region, turn, {'food': 50})
            self.assertFalse(apply_career_switch(region, people[1], Goods.wood, turn))
        self.assertEqual(populations(region, 24)['food'], 4)

    def test_unused_whole_slots_expire_and_idle_resets_fraction(self):
        region, _ = fixture(50)
        prepare_budgets(region, 1, {'food': 1})
        self.assertAlmostEqual(region.career_transition_carry['food'], .6)
        state = prepare_budgets(region, 2, {'food': 1})
        self.assertEqual(state['budgets']['food']['quota'], 5)
        prepare_budgets(region, 3, {})
        self.assertEqual(region.career_transition_carry['food'], 0)

    def test_adults_actual_work_and_nonpeople(self):
        region, people = fixture(5)
        employer = firm(region)
        people[0].employer = employer
        child = Agent(1)
        initialize_agent(child, Goods.food, 0, 0, 1)
        child.is_native_child = True
        region.agents.append(child)
        self.assertEqual(populations(region, 1), {'food': 4, 'wood': 1})

    def test_authored_output_overrides_stale_primary_label(self):
        region, people = fixture(5)
        for person in people:
            person.output = Goods.cotton
        self.assertEqual(populations(region, 1), {'cotton': 5})
        prepare_budgets(region, 1, {'cotton': 10})
        self.assertFalse(apply_career_switch(region, people[0], Goods.wood, 1))
        prepare_budgets(region, 2, {'cotton': 10})
        prepare_budgets(region, 3, {'cotton': 10})
        prepare_budgets(region, 4, {'cotton': 10})
        self.assertTrue(apply_career_switch(region, people[0], Goods.wood, 4))
        self.assertEqual(populations(region, 4), {'cotton': 4, 'wood': 1})

    def test_arrivals_do_not_refill_and_live_losses_restrict(self):
        region, people = fixture(8)
        state = prepare_budgets(region, 1, {'food': 10})
        self.assertEqual(state['budgets']['food']['quota'], 1)
        extra = fixture(20)[1]
        region.agents.extend(extra)
        self.assertIs(begin_turn(region, 1), state)
        self.assertTrue(apply_career_switch(region, people[0], Goods.wood, 1))
        self.assertFalse(apply_career_switch(region, people[1], Goods.wood, 1))
        region, people = fixture(8)
        prepare_budgets(region, 1, {'food': 10})
        for p in people[:4]:
            p.alive = False
        self.assertFalse(apply_career_switch(region, people[4], Goods.wood, 1))

    def test_failed_attachment_preserves_job_and_slot(self):
        region, people = fixture(8)
        employer = firm(region, cash=0)
        prepare_budgets(region, 1, {'food': 10})
        decision = LaborDecision(people[0].id, employer.id, 1, True, 'accepted', 0, 100, 0)
        self.assertFalse(attach_worker(people[0], employer, 1, decision, region))
        self.assertIsNone(people[0].employer)
        self.assertEqual(region.career_transition_state['budgets']['food']['used'], 0)
        employer.cash = 100000
        self.assertTrue(attach_worker(people[0], employer, 1, decision, region))
        self.assertEqual(region.career_transition_state['budgets']['food']['used'], 1)
        self.assertFalse(apply_career_switch(region, people[1], Goods.wood, 1))

    def test_same_profession_job_and_forced_move(self):
        region, people = fixture(4)
        employer = firm(region, good=Goods.food)
        prepare_budgets(region, 1, {})
        decision = LaborDecision(people[0].id, employer.id, 1, True, 'accepted', 0, 100, 0)
        self.assertTrue(attach_worker(people[0], employer, 1, decision, region))
        self.assertEqual(region.career_transition_state['budgets']['food']['used'], 0)
        self.assertTrue(apply_career_switch(region, people[1], Goods.wood, 1, reason='forced_displacement'))
        self.assertEqual(populations(region, 1)['food'], 3)

    def test_trader_role_cannot_bypass_the_protected_profession(self):
        from region_logistics import make_trader_internal
        region, people = fixture(4)
        region._last_turn = 1
        prepare_budgets(region, 1, {})
        self.assertFalse(make_trader_internal(region, people[0]))
        self.assertFalse(people[0].is_trader)
        region, people = fixture(8)
        region._last_turn = 1
        prepare_budgets(region, 1, {'food': 10})
        self.assertTrue(make_trader_internal(region, people[0]))
        self.assertFalse(apply_career_switch(region, people[1], Goods.wood, 1))
        self.assertEqual(region.career_transition_state['budgets']['food']['used'], 1)

    def test_adult_entry_records_household_trade_without_another_move(self):
        from types import SimpleNamespace
        from demographics_career import handle_career_switching
        region, people = fixture(4)
        person = people[0]
        person.primary_livelihood = None
        region.labor_scheduler_last_turn = 1
        prepare_budgets(region, 1, {})
        handle_career_switching(SimpleNamespace(source_region=region), 1, person,
                                people, [], [], 0)
        self.assertEqual(person.primary_livelihood, Goods.food)
        self.assertEqual(region.career_transition_state['budgets']['food']['used'], 0)

    def test_serialized_midturn_ledger_and_fraction_cannot_reset(self):
        region, people = fixture(10)
        prepare_budgets(region, 1, {'food': 2})
        self.assertTrue(apply_career_switch(region, people[0], Goods.wood, 1))
        restored = copy.deepcopy(region)
        self.assertEqual(restored.career_transition_state, region.career_transition_state)
        prepare_budgets(restored, 1, {'food': 100})
        self.assertFalse(apply_career_switch(restored, restored.agents[1], Goods.wood, 1))
        prepare_budgets(restored, 2, {'food': 1})
        self.assertAlmostEqual(restored.career_transition_carry['food'], .7)

    def test_stable_workers_stay_and_hungry_wealth_is_not_excluded(self):
        region, people = fixture(8)
        people[-1].cash = 1000
        employer = firm(region, slots=2)
        def returns(r, p, good, counts, turn):
            return ((1 if p is people[-1] else 10), 'test current') if good == Goods.food else (0, 'not feasible')
        with patch('career_transitions._returns', side_effect=returns):
            result = step_careers(region, 1)
            self.assertEqual(result['hired'], 0)
            people[-1].calorie_deficit_kcal = 500
            result = step_careers(region, 2)
        self.assertEqual(result['hired'], 1)
        self.assertIs(people[-1].employer, employer)
        self.assertEqual(populations(region, 1)['food'], 7)
        from region_labor import hire_workers
        self.assertTrue(hire_workers(region, 2)['already_processed'])

    def test_employed_worker_can_choose_food_when_market_and_commons_cannot_feed(self):
        region, people = fixture(8)
        region.commons_capacity = 0
        employer = firm(region)
        employer.output = Goods.wood
        employer.employees = people[:]
        for p in people:
            p.employer = employer
            p.output = p.primary_livelihood = Goods.wood
            p.wage = 1
            p.cash = 500
            p.hungry_steps = 3
            p.calorie_deficit_kcal = 500
        def returns(r, p, good, counts, turn):
            return (50, 'usable food') if good == Goods.food else (0, 'no market')
        with patch('career_transitions._returns', side_effect=returns):
            for turn in range(1, 4):
                result = step_careers(region, turn)
        self.assertEqual(result['switched'], 1)
        entrant = next(p for p in people if p.output == Goods.food)
        self.assertIsNone(entrant.employer)
        self.assertNotIn(entrant, employer.employees)


if __name__ == '__main__':
    unittest.main()
