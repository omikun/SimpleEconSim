import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from demographics_consumption import consume_daily_food
from goods import Goods
from nutrition import INITIAL_RESERVE_KCAL, queue_emergency_meal
from person_death import record_person_death


class MemoryTrace:
    def __init__(self):
        self.rows = []
        self.latest_food_intake = {}

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        if row.get('kind') == 'household_food_intake':
            agent_id = row['inputs']['agent_id']
            self.latest_food_intake[str(agent_id)] = event_id
        return event_id

    def food_intake_event_id(self, agent_id):
        return self.latest_food_intake.get(str(agent_id))


def _fixture(*, traced=True, inventory=1, ration=2):
    person = Agent(0)
    initialize_agent(person, Goods.food, 0, inventory, 0)
    person.id = 52
    person.calorie_need_kcal = 2000.0
    person.energy_reserve_kcal = INITIAL_RESERVE_KCAL
    person.calorie_deficit_kcal = 0.0
    person.hungry_steps = 0.0
    queue_emergency_meal(person, ration)
    region = SimpleNamespace(name='Mill District')
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 4, 'phase': 'demographics', 'next': 1}
    return person, region, trace


class FoodIntakeTraceTests(unittest.TestCase):
    def test_shortfall_records_sources_and_health_changes(self):
        person, region, trace = _fixture()

        eaten = consume_daily_food(person, region=region, turn=4)

        self.assertEqual(eaten, 3)
        event = next(row for row in trace.rows
                     if row.get('kind') == 'household_food_intake')
        inputs = event['inputs']
        self.assertEqual(inputs['outcome'], 'shortfall')
        self.assertEqual(inputs['food_sources'], {
            'emergency_ration_queue': 2,
            'household_inventory': 1,
            'foreign_trader_inventory': 0,
            'export_trader_inventory': 0})
        self.assertEqual(inputs['food_shortfall_units'], 1)
        self.assertEqual(inputs['calorie_deficit_before_kcal'], 0.0)
        self.assertEqual(inputs['calorie_deficit_after_kcal'], 500.0)
        self.assertEqual(inputs['energy_reserve_before_kcal'], INITIAL_RESERVE_KCAL)
        self.assertEqual(inputs['energy_reserve_after_kcal'],
                         INITIAL_RESERVE_KCAL - 500.0)
        self.assertEqual(inputs['household_food_inventory_before'], 1)
        self.assertEqual(inputs['household_food_inventory_after'], 0)
        self.assertEqual(person.emergency_food_units, 0)

    def test_starvation_death_links_to_that_turns_intake_record(self):
        person, region, trace = _fixture()
        consume_daily_food(person, region=region, turn=4)
        intake = next(row for row in trace.rows
                      if row.get('kind') == 'household_food_intake')

        record_person_death(region, person, 4, 'starvation')

        death = next(row for row in trace.rows
                     if row.get('kind') == 'person_died')
        self.assertEqual(death['cause_event_ids'], [intake['event_id']])

    def test_fully_met_normal_meal_does_not_add_routine_trace_noise(self):
        person, region, trace = _fixture(inventory=4, ration=0)

        self.assertEqual(consume_daily_food(person, region=region, turn=4), 4)
        self.assertFalse(any(row.get('kind') == 'household_food_intake'
                             for row in trace.rows))

    def test_trader_intake_identifies_foreign_and_export_stock(self):
        person, region, trace = _fixture(inventory=0, ration=0)
        person.is_trader = True
        person.inventory_foreign[Goods.food.value] = 2
        person.inventory_export[Goods.food.value] = 2

        self.assertEqual(consume_daily_food(person, region=region, turn=4), 4)

        event = next(row for row in trace.rows
                     if row.get('kind') == 'household_food_intake')
        self.assertEqual(event['inputs']['food_sources'], {
            'emergency_ration_queue': 0,
            'household_inventory': 0,
            'foreign_trader_inventory': 2,
            'export_trader_inventory': 2})

    def test_trace_does_not_change_intake_or_health_state(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        plain_eaten = consume_daily_food(plain[0], region=plain[1], turn=4)
        traced_eaten = consume_daily_food(traced[0], region=traced[1], turn=4)

        def state(person):
            return (person.inv_get(Goods.food), person.emergency_food_units,
                    person.calorie_deficit_kcal, person.energy_reserve_kcal,
                    person.hungry_steps)

        self.assertEqual(plain_eaten, traced_eaten)
        self.assertEqual(state(plain[0]), state(traced[0]))


if __name__ == '__main__':
    unittest.main()
