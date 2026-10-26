import unittest

from scenario_egypt_1877 import apply_action
from worldview_engine import build_world_view


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, with_trace=True, stock=12, ration_limit=2, underfed=2):
    world = build_world_view(scenario_id='egypt_1877')
    nation = next(n for n in world['nations'] if n.name == 'Egypt')
    households = [agent for tile in nation.tiles for agent in tile.agents
                  if agent.alive and not agent.is_government
                  and not agent.is_corporation and not agent.is_trader]
    for person in households:
        person.calorie_deficit_kcal = 0.0
        person.hungry_steps = 0
    for person in households[:underfed]:
        person.calorie_deficit_kcal = 1200.0
        person.hungry_steps = 1
    nation.government.food_inventory = stock
    world['scenario_state']['public_maize_stock_units'] = stock
    world['scenario_state']['relief_units_per_turn'] = ration_limit
    world['turn'] = 1
    trace = MemoryTrace()
    clock = {'turn': 1, 'phase': 'scenario_action', 'next': 1}
    if with_trace:
        for tile in nation.tiles:
            tile._run_trace = trace
            tile._collective_trace_clock = clock
    return world, nation, households, trace


def _snapshot(world, nation, households):
    return {
        'stock': nation.government.food_inventory,
        'state_stock': world['scenario_state']['public_maize_stock_units'],
        'ration_queues': tuple(getattr(person, 'emergency_food_units', 0)
                               for person in households),
        'last_action_turn': world['scenario_state'].get('last_action_turn'),
        'actions_taken': list(world['scenario_state'].get('actions_taken', [])),
    }


class NationalMaizeReleaseTraceTests(unittest.TestCase):
    def test_release_pairs_public_stock_with_household_queues(self):
        world, nation, households, trace = _fixture()

        success, _ = apply_action(world, 'release_maize')

        self.assertTrue(success)
        transfers = [row for row in trace.rows
                     if row.get('kind') == 'national_maize_ration_transfer']
        self.assertEqual(len(transfers), 2)
        for row in transfers:
            contract = row['inputs']['transfer_contract']
            self.assertEqual(contract['contract_version'], 'goods_transfer.v1')
            self.assertEqual(contract['operation_type'],
                             'national_maize_release_ration')
            self.assertEqual(contract['payer_account']['balance_before']
                             - contract['payer_account']['balance_after'], 4)
            self.assertEqual(contract['payee_account']['balance_after']
                             - contract['payee_account']['balance_before'], 4)
            self.assertEqual(contract['delivery_status'],
                             'queued_for_next_consumption_step')
        summary = next(row for row in trace.rows
                       if row.get('kind') == 'national_maize_release_resolved')
        self.assertEqual(summary['inputs']['outcome'], 'rations_queued')
        self.assertEqual(summary['after'], 2)
        self.assertTrue(all(row['event_id'] in summary['cause_event_ids']
                            for row in transfers))
        self.assertEqual(nation.government.food_inventory, 4)
        self.assertEqual(world['scenario_state']['public_maize_stock_units'], 4)
        self.assertTrue(all(getattr(person, 'emergency_food_units', 0) == 4
                            for person in households[:2]))

    def test_release_records_empty_reserve_and_no_household_reasons(self):
        world, _nation, _households, trace = _fixture(ration_limit=0)
        success, _ = apply_action(world, 'release_maize')
        self.assertFalse(success)
        event = next(row for row in trace.rows
                     if row.get('kind') == 'national_maize_release_resolved')
        self.assertEqual(event['inputs']['outcome'], 'release_limit_is_zero')

        world, nation, _households, trace = _fixture(stock=2)
        success, _ = apply_action(world, 'release_maize')
        self.assertFalse(success)
        event = next(row for row in trace.rows
                     if row.get('kind') == 'national_maize_release_resolved')
        self.assertEqual(event['inputs']['outcome'],
                         'public_stock_below_full_ration')
        self.assertEqual(event['after'], 0)

        world, nation, _households, trace = _fixture(underfed=0)
        success, _ = apply_action(world, 'release_maize')
        self.assertFalse(success)
        event = next(row for row in trace.rows
                     if row.get('kind') == 'national_maize_release_resolved')
        self.assertEqual(event['inputs']['outcome'], 'no_underfed_households')
        self.assertEqual(event['inputs']['underfed_household_count'], 0)

    def test_trace_does_not_change_release_result(self):
        plain_world, plain_nation, plain_households, _ = _fixture(with_trace=False)
        traced_world, traced_nation, traced_households, _trace = _fixture(with_trace=True)

        self.assertEqual(apply_action(traced_world, 'release_maize')[0],
                         apply_action(plain_world, 'release_maize')[0])
        self.assertEqual(_snapshot(traced_world, traced_nation, traced_households),
                         _snapshot(plain_world, plain_nation, plain_households))


if __name__ == '__main__':
    unittest.main()
