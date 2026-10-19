import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from goods import Goods
from nutrition import CALORIES_PER_FOOD
from scenario_projects import (_pay_workers, advance_grain_entitlement,
                               allocate_revenue, recall_district_reserves)


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        sequence = clock['next']
        clock['next'] += 1
        event_id = f'test:{sequence}'
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _agent(agent_id, cash=0.0, *, lord=False):
    person = Agent(agent_id)
    initialize_agent(person, Goods.food, 0, 0, cash)
    person.is_lord = lord
    person.is_trader = False
    person.is_corporation = False
    person.is_government = False
    person.alive = True
    return person


def _traced_region(name, nation, people, trace, clock):
    return SimpleNamespace(name=name, scenario_location=name,
                           home_currency=getattr(nation, 'currency', 'EGP'),
                           owner_nation=nation,
                           agents=people, unrest_level=0.0,
                           _run_trace=trace, _collective_trace_clock=clock)


class ScenarioProjectTransferTraceTests(unittest.TestCase):
    def test_project_wages_record_balanced_actor_accounts(self):
        trace = MemoryTrace()
        clock = {'turn': 1, 'phase': 'scenario_projects', 'next': 1}
        workers = [_agent(i, cash=float(i)) for i in range(1, 4)]
        government = SimpleNamespace(agent=SimpleNamespace(cash=200.0))
        nation = SimpleNamespace(name='Egypt', currency='EGP', government=government,
                                 tiles=[])
        tile = _traced_region('Nile Delta', nation, workers, trace, clock)
        nation.tiles.append(tile)
        world = {'turn': 1, 'nations': [nation], 'tiles': [tile],
                 'scenario_state': {
                     'strategic_projects': {'payments': []},
                     'geography': {'sites': {'Nile Delta': {'tile': 'Nile Delta'}}}}}
        project = {'id': 'nile_repair:Nile Delta', 'kind': 'nile_repair',
                   'site': 'Nile Delta', 'worker_ids': [worker.id for worker in workers]}
        before = float(government.agent.cash)

        self.assertTrue(_pay_workers(world, project, 45.0, 'construction_wage'))
        rows = [row for row in trace.rows
                if row.get('metric_id') == 'finance.treasury_flow']
        self.assertEqual(len(rows), 3)
        self.assertAlmostEqual(sum(row['after'] for row in rows), -45.0)
        self.assertEqual(rows[0]['inputs']['transfer_contract']['payer_account']
                         ['balance_before'], before)
        for row in rows:
            contract = row['inputs']['transfer_contract']
            self.assertEqual(contract['contract_version'], 'treasury_transfer.v1')
            self.assertEqual(contract['side'], 'payer')
            self.assertEqual(contract['payee_account']['balance_after']
                             - contract['payee_account']['balance_before'],
                             row['inputs']['transfer_contract']['amount'])

    def test_district_recall_pairs_internal_treasury_legs(self):
        trace = MemoryTrace()
        clock = {'turn': 2, 'phase': 'scenario_projects', 'next': 1}
        sovereign = SimpleNamespace(agent=SimpleNamespace(cash=100.0))
        egypt = SimpleNamespace(name='Egypt', currency='EGP', government=sovereign,
                                tiles=[], legitimacy=0.8)
        local_governments = [
            SimpleNamespace(name='District A', agent=SimpleNamespace(cash=70.0)),
            SimpleNamespace(name='District B', agent=SimpleNamespace(cash=40.0)),
        ]
        tiles = [_traced_region(f'District {index}', egypt, [], trace, clock)
                 for index in ('A', 'B')]
        for tile, local in zip(tiles, local_governments):
            tile.gov = local
            egypt.tiles.append(tile)
        egypt.tiles.extend([])
        state = {'reserve_recall_used': False, 'reserve_recall_reports': []}
        world = {'turn': 2, 'nations': [egypt], 'tiles': tiles,
                 'scenario_state': {'strategic_projects': state}}

        ok, _ = recall_district_reserves(world)
        self.assertTrue(ok)
        rows = [row for row in trace.rows
                if row.get('metric_id') == 'finance.treasury_flow']
        self.assertEqual(len(rows), 4)
        grouped = {}
        for row in rows:
            contract = row['inputs']['transfer_contract']
            grouped.setdefault(contract['operation_id'], []).append(row)
        self.assertEqual(len(grouped), 2)
        for legs in grouped.values():
            self.assertEqual({leg['inputs']['transfer_contract']['side']
                              for leg in legs}, {'payer', 'payee'})
            self.assertAlmostEqual(sum(leg['after'] for leg in legs), 0.0)
        action = next(row for row in trace.rows
                      if row.get('kind') == 'recall_district_reserves_resolved')
        self.assertEqual(action['after'], 1)
        self.assertEqual(set(action['cause_event_ids']),
                         {row['event_id'] for row in rows})
        self.assertAlmostEqual(action['inputs']['total_transferred'], 70.0)
        self.assertEqual(action['inputs']['sovereign_cash_before'], 100.0)
        self.assertEqual(action['inputs']['sovereign_cash_after'], 170.0)
        self.assertEqual(action['inputs']['legitimacy_before'], 0.8)
        self.assertEqual(action['inputs']['legitimacy_after'], 0.765)
        unrest = [row for row in trace.rows
                  if row.get('kind') == 'district_reserve_recall_unrest']
        self.assertEqual(len(unrest), 2)
        self.assertTrue(all(row['before'] == 0.0 and row['after'] == 0.02
                            for row in unrest))
        legitimacy = next(row for row in trace.rows
                          if row.get('kind') == 'district_reserve_recall_legitimacy')
        self.assertEqual((legitimacy['before'], legitimacy['after']), (0.8, 0.765))

    def test_recall_rejection_records_used_gate(self):
        trace = MemoryTrace()
        clock = {'turn': 3, 'phase': 'scenario_projects', 'next': 1}
        sovereign = SimpleNamespace(agent=SimpleNamespace(cash=100.0))
        egypt = SimpleNamespace(name='Egypt', currency='EGP', government=sovereign,
                                tiles=[], legitimacy=0.8)
        tile = _traced_region('District', egypt, [], trace, clock)
        tile.gov = SimpleNamespace(agent=SimpleNamespace(cash=70.0))
        egypt.tiles.append(tile)
        state = {'reserve_recall_used': True, 'reserve_recall_reports': []}
        world = {'turn': 3, 'nations': [egypt], 'tiles': [tile],
                 'scenario_state': {'strategic_projects': state}}

        success, _ = recall_district_reserves(world)

        self.assertFalse(success)
        event = next(row for row in trace.rows
                     if row.get('kind') == 'recall_district_reserves_resolved')
        self.assertEqual(event['after'], 0)
        self.assertEqual(event['inputs']['reason'], 'recall_already_used')
        self.assertEqual(egypt.government.agent.cash, 100.0)

    def test_tracing_does_not_change_reserve_recall_state(self):
        def fixture(traced):
            trace = MemoryTrace()
            clock = {'turn': 2, 'phase': 'scenario_projects', 'next': 1}
            sovereign = SimpleNamespace(agent=SimpleNamespace(cash=100.0))
            egypt = SimpleNamespace(name='Egypt', currency='EGP', government=sovereign,
                                    tiles=[], legitimacy=0.8)
            locals_ = [SimpleNamespace(name='District A',
                                       agent=SimpleNamespace(cash=70.0)),
                       SimpleNamespace(name='District B',
                                       agent=SimpleNamespace(cash=40.0))]
            tiles = [_traced_region(f'District {index}', egypt, [],
                                    trace if traced else None, clock)
                     for index in ('A', 'B')]
            for tile, government in zip(tiles, locals_):
                tile.gov = government
                egypt.tiles.append(tile)
            state = {'reserve_recall_used': False, 'reserve_recall_reports': []}
            world = {'turn': 2, 'nations': [egypt], 'tiles': tiles,
                     'scenario_state': {'strategic_projects': state}}
            return world, egypt, tiles, locals_, trace, state

        plain = fixture(False)
        traced = copy.deepcopy(plain)
        clock = {'turn': 2, 'phase': 'scenario_projects', 'next': 1}
        for tile in traced[2]:
            tile._run_trace = traced[4]
            tile._collective_trace_clock = clock
        self.assertEqual(recall_district_reserves(plain[0])[0],
                         recall_district_reserves(traced[0])[0])
        self.assertEqual(
            ([plain[1].government.agent.cash, plain[1].legitimacy],
             [tile.unrest_level for tile in plain[2]],
             [government.agent.cash for government in plain[3]], plain[5]),
            ([traced[1].government.agent.cash, traced[1].legitimacy],
             [tile.unrest_level for tile in traced[2]],
             [government.agent.cash for government in traced[3]], traced[5]))

    def test_central_revenue_remittance_pairs_local_and_cairo_legs(self):
        trace = MemoryTrace()
        clock = {'turn': 4, 'phase': 'scenario_projects', 'next': 1}
        local = SimpleNamespace(name='Alexandria District',
                                agent=SimpleNamespace(cash=50.0))
        sovereign = SimpleNamespace(agent=SimpleNamespace(cash=200.0),
                                    _income_pending={})
        egypt = SimpleNamespace(name='Egypt', currency='EGP', government=sovereign,
                                tiles=[], legitimacy=0.8)
        tile = _traced_region('Alexandria', egypt, [], trace, clock)
        tile.gov = local
        egypt.tiles.append(tile)
        state = {'revenue_reports': []}
        world = {'turn': 4, 'nations': [egypt],
                 'scenario_state': {'strategic_projects': state}}

        with patch('scenario_projects.get_project', return_value={'kind': 'revenue_office'}), \
                patch('scenario_projects.effectiveness', return_value=1.0):
            retained = allocate_revenue(world, local, 'tax', 20.0, turn=4)

        self.assertAlmostEqual(retained, 12.0)
        self.assertAlmostEqual(local.agent.cash, 42.0)
        self.assertAlmostEqual(sovereign.agent.cash, 208.0)
        flows = [row for row in trace.rows
                 if row.get('metric_id') == 'finance.treasury_flow']
        self.assertEqual(len(flows), 2)
        self.assertEqual(flows[0]['inputs']['transfer_contract']['operation_id'],
                         flows[1]['inputs']['transfer_contract']['operation_id'])
        self.assertAlmostEqual(sum(row['after'] for row in flows), 0.0)
        self.assertEqual(state['revenue_reports'][0]['operation_id'],
                         flows[0]['inputs']['transfer_contract']['operation_id'])

    def test_grain_delivery_links_food_and_carrier_payments(self):
        trace = MemoryTrace()
        clock = {'turn': 2, 'phase': 'scenario_projects', 'next': 1}
        owner = _agent(100, 20.0, lord=True)
        owner.inv_set(Goods.food, 20)
        carrier = _agent(101, 0.0)
        recipient = _agent(102, 5.0)
        recipient.calorie_deficit_kcal = CALORIES_PER_FOOD * 2
        recipient.last_calories_eaten = 0.0
        tile = _traced_region('Nile Delta', None, [owner, carrier, recipient],
                              trace, clock)
        nation = SimpleNamespace(name='Egypt', currency='EGP', tiles=[tile],
                                 legitimacy=0.8,
                                 government=SimpleNamespace(agent=SimpleNamespace(cash=50.0)))
        tile.owner_nation = nation
        world = {'turn': 2, 'nations': [nation], 'tiles': [tile],
                 'scenario_state': {
                     'strategic_projects': {'grain_entitlement_active': True,
                                            'grain_entitlement_reports': []},
                     'political_economy': {'warehouse_by_tile': {},
                                           'private_reserve_by_tile': {},
                                           'grain_transactions': []}}}

        advance_grain_entitlement(world)
        food_row = next(row for row in trace.rows
                        if row.get('metric_id') == 'goods.food_entitlement_transfer')
        wage_row = next(row for row in trace.rows
                        if row.get('kind') == 'scenario_grain_carrier_wage')
        self.assertEqual(food_row['after'], 2)
        self.assertEqual(food_row['inputs']['food_owner_id'], owner.id)
        self.assertEqual(food_row['inputs']['food_recipient_id'], recipient.id)
        self.assertEqual(food_row['inputs']['source_inventory_after'],
                         food_row['inputs']['source_inventory_before'] - 2)
        self.assertIn(wage_row['event_id'], food_row['cause_event_ids'])
        self.assertEqual(owner.inv_get(Goods.food, 0), 18)
        self.assertEqual(recipient.calorie_deficit_kcal, 0)
        summary = next(row for row in trace.rows
                       if row.get('kind') == 'grain_entitlement_turn_resolved')
        self.assertEqual(summary['metric_id'], 'scenario.grain_entitlement')
        self.assertEqual(summary['after'], 2)
        self.assertEqual(summary['inputs']['reason'], 'food_delivered')
        self.assertEqual(summary['cause_event_ids'], [food_row['event_id']])
        self.assertEqual(summary['inputs']['underfed_households_before'], 1)
        self.assertEqual(summary['inputs']['underfed_households_after'], 0)
        self.assertEqual(nation.legitimacy, 0.788)
        self.assertEqual(tile.unrest_level, 0.004)
        legitimacy = next(row for row in trace.rows
                          if row.get('kind') == 'grain_entitlement_legitimacy')
        self.assertAlmostEqual(legitimacy['before'], 0.8)
        self.assertAlmostEqual(legitimacy['after'], 0.788)
        unrest = next(row for row in trace.rows
                      if row.get('kind') == 'grain_entitlement_unrest')
        self.assertEqual((unrest['before'], unrest['after']), (0.0, 0.004))

    def test_active_entitlement_records_zero_delivery_reason(self):
        trace = MemoryTrace()
        clock = {'turn': 3, 'phase': 'scenario_projects', 'next': 1}
        owner = _agent(200, 20.0, lord=True)
        owner.inv_set(Goods.food, 20)
        carrier = _agent(201, 0.0)
        recipient = _agent(202, 5.0)
        recipient.calorie_deficit_kcal = 0.0
        recipient.last_calories_eaten = 0.0
        tile = _traced_region('Delta', None, [owner, carrier, recipient],
                              trace, clock)
        nation = SimpleNamespace(
            name='Egypt', currency='EGP', tiles=[tile], legitimacy=0.8,
            government=SimpleNamespace(agent=SimpleNamespace(cash=50.0)))
        tile.owner_nation = nation
        world = {'turn': 3, 'nations': [nation], 'tiles': [tile],
                 'scenario_state': {
                     'strategic_projects': {'grain_entitlement_active': True,
                                            'grain_entitlement_reports': []},
                     'political_economy': {'warehouse_by_tile': {},
                                           'private_reserve_by_tile': {},
                                           'grain_transactions': []}}}

        advance_grain_entitlement(world)

        summary = next(row for row in trace.rows
                       if row.get('kind') == 'grain_entitlement_turn_resolved')
        self.assertEqual(summary['after'], 0)
        self.assertEqual(summary['inputs']['reason'], 'no_underfed_households')
        self.assertEqual(summary['inputs']['eligible_surplus_donor_count'], 1)
        self.assertFalse(any(row.get('metric_id') == 'politics.legitimacy'
                             for row in trace.rows))

    def test_tracing_does_not_change_grain_entitlement_state(self):
        def fixture(traced):
            trace = MemoryTrace()
            clock = {'turn': 3, 'phase': 'scenario_projects', 'next': 1}
            owner = _agent(400, 20.0, lord=True)
            owner.inv_set(Goods.food, 20)
            carrier = _agent(401, 0.0)
            recipient = _agent(402, 5.0)
            recipient.calorie_deficit_kcal = CALORIES_PER_FOOD * 2
            recipient.last_calories_eaten = 0.0
            tile = _traced_region('Delta', None, [owner, carrier, recipient],
                                  trace if traced else None, clock)
            nation = SimpleNamespace(
                name='Egypt', currency='EGP', tiles=[tile], legitimacy=0.8,
                government=SimpleNamespace(agent=SimpleNamespace(cash=50.0)))
            tile.owner_nation = nation
            state = {'grain_entitlement_active': True,
                     'grain_entitlement_reports': []}
            econ = {'warehouse_by_tile': {}, 'private_reserve_by_tile': {},
                    'grain_transactions': []}
            world = {'turn': 3, 'nations': [nation], 'tiles': [tile],
                     'scenario_state': {'strategic_projects': state,
                                        'political_economy': econ}}
            return world, nation, tile, owner, carrier, recipient, trace, state, econ

        plain = fixture(False)
        traced = copy.deepcopy(plain)
        traced[2]._run_trace = traced[6]
        traced[2]._collective_trace_clock = {
            'turn': 3, 'phase': 'scenario_projects', 'next': 1}
        advance_grain_entitlement(plain[0])
        advance_grain_entitlement(traced[0])
        def result(fixture):
            _world, nation, tile, owner, carrier, recipient, _trace, state, econ = fixture
            return (nation.government.agent.cash, nation.legitimacy,
                    tile.unrest_level, owner.cash, owner.inv_get(Goods.food),
                    carrier.cash, recipient.calorie_deficit_kcal,
                    recipient.last_calories_eaten, copy.deepcopy(state),
                    copy.deepcopy(econ))
        self.assertEqual(result(traced), result(plain))

    def test_grain_entitlement_policy_activation_repeat_and_end_are_logged(self):
        from scenario_projects import set_grain_entitlement

        trace = MemoryTrace()
        clock = {'turn': 4, 'phase': 'scenario_action', 'next': 1}
        worker = _agent(301, 3.0)
        government = SimpleNamespace(agent=SimpleNamespace(cash=100.0))
        nation = SimpleNamespace(name='Egypt', currency='EGP', tiles=[], legitimacy=0.8,
                                 government=government)
        tile = _traced_region('Delta', nation, [worker], trace, clock)
        nation.tiles.append(tile)
        state = {'grain_entitlement_active': False}
        world = {'turn': 4, 'nations': [nation], 'tiles': [tile],
                 'scenario_state': {'strategic_projects': state}}

        self.assertTrue(set_grain_entitlement(world, True)[0])
        self.assertFalse(set_grain_entitlement(world, True)[0])
        self.assertTrue(set_grain_entitlement(world, False)[0])

        events = [row for row in trace.rows
                  if row.get('metric_id') == 'scenario.grain_entitlement_policy']
        self.assertEqual(len(events), 3)
        self.assertEqual([(row['before'], row['after']) for row in events],
                         [(0, 1), (1, 1), (1, 0)])
        self.assertEqual(events[1]['inputs']['reason'],
                         'policy_already_in_requested_state')


if __name__ == '__main__':
    unittest.main()
