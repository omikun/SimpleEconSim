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
    def test_round_robin_gate_records_deferred_and_emergency_workers(self):
        ordinary_region, ordinary_worker, ordinary_trace = _fixture()
        ordinary_result = LaborMobilityScheduler().step_labor_cohort(
            ordinary_region, 1)
        ordinary_event = next(row for row in ordinary_trace.rows
                              if row.get('kind') == 'labor_scheduler_gate')
        self.assertEqual(ordinary_result['cohort_index'], 1)
        self.assertEqual(ordinary_event['inputs']['outcome'], 'cohort_selected')
        self.assertEqual(ordinary_event['inputs']['total_non_elite_workers'], 1)
        self.assertEqual(ordinary_event['inputs']['active_cohort_agent_ids'], [])
        self.assertEqual(ordinary_event['inputs']['execution_order_agent_ids'], [])
        self.assertEqual(ordinary_event['inputs']['deferred_worker_count'], 1)

        emergency_region, emergency_worker, emergency_trace = _fixture(
            hungry_steps=3.0)
        emergency_result = LaborMobilityScheduler().step_labor_cohort(
            emergency_region, 1)
        schedule = next(row for row in emergency_trace.rows
                        if row.get('kind') == 'labor_scheduler_gate')
        reasons = schedule['inputs']['emergency_agent_reasons']
        self.assertEqual(emergency_result['emergency_fast_path_count'], 1)
        self.assertEqual(schedule['inputs']['execution_order_agent_ids'],
                         [emergency_worker.id])
        self.assertEqual(reasons, [{'agent_id': emergency_worker.id,
                                   'reasons': ['acute_hunger',
                                               'unemployed_hunger',
                                               'unemployed_dispossessed']}])
        livelihood = next(row for row in emergency_trace.rows
                          if row.get('kind') == 'worker_livelihood_options')
        self.assertEqual(livelihood['cause_event_ids'], [schedule['event_id']])

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
