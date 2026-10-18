import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from demographics_consumption import transfer_dependent_food
from econsim_live import Live, LiveContext
from goods import Goods
from nutrition import update_dependent_need


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True):
    parent = Agent(0)
    child = Agent(1)
    initialize_agent(parent, Goods.food, 0, 4, 0)
    initialize_agent(child, Goods.food, 0, 0, 0)
    parent.id = 40
    child.id = 41
    child.is_native_child = True
    child.parent = parent
    parent.region = child.region = 'Home'
    update_dependent_need(child, 2)
    region = SimpleNamespace(name='Home')
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 2, 'phase': 'demographics', 'next': 1}
    return [parent, child], region, trace


class DependentFoodTraceTests(unittest.TestCase):
    def test_parent_debit_and_child_credit_are_linked(self):
        agents, region, trace = _fixture()

        total, recipients, event_ids = transfer_dependent_food(
            agents, 2, region=region, return_event_ids=True)

        self.assertEqual((total, recipients), (2, 1))
        self.assertEqual(len(event_ids), 1)
        event = trace.rows[0]
        contract = event['inputs']['transfer_contract']
        self.assertEqual(event['kind'], 'dependent_food_inventory_transfer')
        self.assertEqual(event['metric_id'], 'goods.dependent_food_transfer')
        self.assertEqual(contract['contract_version'], 'goods_transfer.v1')
        self.assertEqual(contract['operation_type'],
                         'dependent_household_food_transfer')
        self.assertEqual(contract['payer_account']['balance_before'], 4)
        self.assertEqual(contract['payer_account']['balance_after'], 2)
        self.assertEqual(contract['payee_account']['balance_before'], 0)
        self.assertEqual(contract['payee_account']['balance_after'], 2)
        self.assertEqual(event_ids, [event['event_id']])

    def test_trace_does_not_change_dependent_food_transfer(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        self.assertEqual(transfer_dependent_food(plain[0], 2), (2, 1))
        self.assertEqual(transfer_dependent_food(
            traced[0], 2, region=traced[1], return_event_ids=True)[:2], (2, 1))
        self.assertEqual(
            (plain[0][0].inv_get(Goods.food), plain[0][1].inv_get(Goods.food)),
            (traced[0][0].inv_get(Goods.food), traced[0][1].inv_get(Goods.food)))

    def test_lifecycle_summary_links_to_household_transfer(self):
        agents, region, trace = _fixture()
        context = LiveContext(
            recipes={}, goods=[Goods.food], governments=[], default_gov=None,
            hungry_log={Goods.food: []}, dead_pop=[], deadstarve_pop=[0],
            production_log={}, starve_limit=1, profession={},
            max_career_switches=1, p_birth=0.0, birth_gap=1, bank=None,
            most_demand=None, source_region=region)

        def no_switch(_ctx, _turn, _agent, _agents, _choices, _weights, count):
            return 0, count

        with (patch('econsim_live.compute_bottleneck_weights', return_value=[]),
              patch('econsim_live.consume_goods', side_effect=lambda _ctx, _agent, food, wood, furniture: (food, wood, furniture)),
              patch('econsim_live.consume_daily_food', return_value=0),
              patch('econsim_live.handle_career_switching', side_effect=no_switch),
              patch('econsim_live.handle_job_seeking'),
              patch('econsim_live.handle_reproduction', return_value=0),
              patch('econsim_live.handle_death', return_value=False),
              patch('econsim_live.build_employer_cache', return_value={}),
              patch('econsim_live.random.shuffle')):
            Live(2, agents, context)

        transfer = next(row for row in trace.rows
                        if row.get('kind') == 'dependent_food_inventory_transfer')
        summary = next(row for row in trace.rows
                       if row.get('kind') == 'household_food_transfer')
        self.assertEqual(summary['after'], 2)
        self.assertEqual(summary['cause_event_ids'], [transfer['event_id']])


if __name__ == '__main__':
    unittest.main()
