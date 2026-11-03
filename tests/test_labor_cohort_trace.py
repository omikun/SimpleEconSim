import unittest

from agent import Agent, initialize_agent
from economy.labor_mobility import LaborMobilityScheduler
from goods import Goods
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, hungry_steps=0.0):
    region = Region('Mill District', 0)
    worker = Agent(0)
    initialize_agent(worker, Goods.food, 0, 0, 5.0)
    worker.id = 41
    worker.alive = True
    worker.cash = 5.0
    worker.hungry_steps = hungry_steps
    worker.calorie_deficit_kcal = 1000.0 if hungry_steps else 0.0
    worker.social_class = 'dispossessed' if hungry_steps else 'artisan'
    region.agents = [worker]
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 1, 'phase': 'labor', 'next': 1}
    return region, worker, trace


class LaborCohortTraceTests(unittest.TestCase):
    def test_every_adult_is_considered_without_emergency_or_cash_gates(self):
        for hunger, cash in ((0, 5), (3, 500)):
            region, worker, trace = _fixture(hungry_steps=hunger)
            worker.cash = cash
            result = LaborMobilityScheduler().step_labor_cohort(region, 1)
            schedule = next(row for row in trace.rows if row.get('kind') == 'labor_scheduler_gate')
            self.assertEqual(result['cohort_index'], 0)
            self.assertEqual(result['processed'], 1)
            self.assertEqual(schedule['inputs']['outcome'], 'all_adults_considered')
            self.assertEqual(schedule['inputs']['execution_order_agent_ids'], [worker.id])
            self.assertEqual(schedule['inputs']['deferred_worker_count'], 0)
            livelihood = next(row for row in trace.rows if row.get('kind') in
                              ('worker_livelihood_options', 'worker_livelihood_stay'))
            self.assertIn('current_return', livelihood['inputs'])

    def test_repeat_call_records_the_same_turn_guard(self):
        region, _worker, trace = _fixture()
        scheduler = LaborMobilityScheduler()

        scheduler.step_labor_cohort(region, 1)
        result = scheduler.step_labor_cohort(region, 1)

        self.assertTrue(result['already_processed'])
        events = [row for row in trace.rows
                  if row.get('kind') == 'labor_scheduler_gate']
        self.assertEqual(events[-1]['inputs']['outcome'],
                         'already_processed_this_turn')

    def test_trace_does_not_change_cohort_or_worker_state(self):
        plain = _fixture(traced=False, hungry_steps=3.0)
        traced = _fixture(traced=True, hungry_steps=3.0)

        plain_result = LaborMobilityScheduler().step_labor_cohort(plain[0], 1)
        traced_result = LaborMobilityScheduler().step_labor_cohort(traced[0], 1)

        self.assertEqual(plain_result['reallocations_count'],
                         traced_result['reallocations_count'])
        self.assertEqual((plain[1].output, plain[1].employer, plain[1].cash,
                          plain[1].hungry_steps),
                         (traced[1].output, traced[1].employer, traced[1].cash,
                          traced[1].hungry_steps))


if __name__ == '__main__':
    unittest.main()
