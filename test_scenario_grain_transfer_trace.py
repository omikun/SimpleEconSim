import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from scenario_political_economy import (_buy_harvest, _sell_to_households,
                                         apply_action)


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        sequence = clock['next']
        clock['next'] += 1
        event_id = f'test:{sequence}'
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _person(person_id, *, cash, food, output=Goods.food, lord=False):
    person = Agent(person_id)
    person.id = person_id
    initialize_agent(person, output, 0, 0, cash)
    person.alive = True
    person.is_lord = lord
    person.is_corporation = False
    person.is_government = False
    person.is_trader = False
    person.inv_set(Goods.food, food)
    return person


def _fixture(people, *, reserve, turn=3):
    trace = MemoryTrace()
    clock = {'turn': turn, 'phase': 'scenario_economy', 'next': 1}
    tile = SimpleNamespace(
        name='Nile Delta', home_currency='EGP',
        recipes={Goods.food: {'price': 2.0}}, agents=people,
        unrest_level=0.1, _run_trace=trace,
        _collective_trace_clock=clock)
    owner = next(person for person in people if person.is_lord)
    tile.scenario_grain_reserved_units = reserve
    economy = {
        'warehouse_by_tile': {tile.name: owner.id},
        'private_reserve_by_tile': {tile.name: reserve},
        'grain_policy': 'hold', 'grain_transactions': [],
    }
    world = {'turn': turn, 'scenario_state': {'political_economy': economy}}
    return world, tile, owner, trace, economy


class ScenarioGrainTransferTraceTests(unittest.TestCase):
    def _assert_linked_cash_and_food(self, trace, operation_type, amount,
                                     source_id, destination_id):
        cash = next(row for row in trace.rows
                    if row.get('metric_id') == 'finance.cash_transfer'
                    and row.get('kind') == f'{operation_type}_payment')
        goods = next(row for row in trace.rows
                     if row.get('metric_id') == 'goods.grain_transfer'
                     and row.get('inputs', {}).get('operation_id') ==
                     cash['inputs']['operation_id'])
        cash_contract = cash['inputs']['transfer_contract']
        goods_contract = goods['inputs']['transfer_contract']
        self.assertEqual(cash_contract['contract_version'], 'cash_transfer.v1')
        self.assertEqual(cash_contract['side'], 'payer')
        self.assertEqual(goods_contract['contract_version'], 'goods_transfer.v1')
        self.assertAlmostEqual(cash_contract['amount'], amount)
        self.assertEqual(goods_contract['operation_id'],
                         cash_contract['operation_id'])
        self.assertEqual(goods['cause_event_ids'], [cash['event_id']])
        self.assertEqual(str(goods_contract['payer_account']['id']), str(source_id))
        self.assertEqual(str(goods_contract['payee_account']['id']), str(destination_id))
        return cash, goods

    def test_private_owner_buys_harvest_with_linked_cash_and_food_legs(self):
        owner = _person(100, cash=200.0, food=0, lord=True)
        producer = _person(101, cash=0.0, food=100)
        world, tile, owner, trace, economy = _fixture([owner, producer], reserve=0)

        _buy_harvest(world, tile, owner, turn=3)

        transaction = economy['grain_transactions'][0]
        units = transaction['units']
        cash, goods = self._assert_linked_cash_and_food(
            trace, 'private_harvest_purchase', units * 2.0,
            producer.id, owner.id)
        self.assertEqual(transaction['operation_ids'], [cash['inputs']['operation_id']])
        self.assertEqual(cash['inputs']['transfer_contract']['payer_account']['id'],
                         owner.id)
        self.assertEqual(cash['inputs']['transfer_contract']['payee_account']['id'],
                         producer.id)
        self.assertEqual(goods['inputs']['transfer_contract']['payer_account']
                         ['balance_before'] - goods['inputs']['transfer_contract']
                         ['payer_account']['balance_after'], units)
        self.assertEqual(owner.cash + producer.cash, 200.0)

    def test_optional_trace_does_not_change_private_grain_transaction(self):
        traced_owner = _person(110, cash=200.0, food=0, lord=True)
        traced_producer = _person(111, cash=0.0, food=100)
        traced_world, traced_tile, _, trace, traced_economy = _fixture(
            [traced_owner, traced_producer], reserve=0)
        plain_owner = _person(110, cash=200.0, food=0, lord=True)
        plain_producer = _person(111, cash=0.0, food=100)
        plain_world, plain_tile, _, _, plain_economy = _fixture(
            [plain_owner, plain_producer], reserve=0)
        del plain_tile._run_trace
        del plain_tile._collective_trace_clock

        _buy_harvest(traced_world, traced_tile, traced_owner, turn=3)
        _buy_harvest(plain_world, plain_tile, plain_owner, turn=3)

        self.assertEqual(traced_economy['grain_transactions'],
                         plain_economy['grain_transactions'])
        self.assertEqual((traced_owner.cash, traced_producer.cash,
                          traced_owner.inv_get(Goods.food, 0),
                          traced_producer.inv_get(Goods.food, 0)),
                         (plain_owner.cash, plain_producer.cash,
                          plain_owner.inv_get(Goods.food, 0),
                          plain_producer.inv_get(Goods.food, 0)))
        self.assertTrue(trace.rows)

    def test_private_warehouse_sale_to_household_records_both_legs(self):
        owner = _person(200, cash=10.0, food=10, lord=True)
        buyer = _person(201, cash=20.0, food=0, output=Goods.wood)
        world, tile, owner, trace, economy = _fixture([owner, buyer], reserve=10)

        sold = _sell_to_households(world, tile, owner, limit=4)

        transaction = economy['grain_transactions'][0]
        self.assertEqual(sold, 4)
        cash, goods = self._assert_linked_cash_and_food(
            trace, 'private_household_grain_sale', 8.0, owner.id, buyer.id)
        self.assertEqual(transaction['operation_ids'], [cash['inputs']['operation_id']])
        self.assertEqual(cash['inputs']['transfer_contract']['payer_account']['id'],
                         buyer.id)
        self.assertEqual(cash['inputs']['transfer_contract']['payee_account']['id'],
                         owner.id)
        self.assertEqual(goods['inputs']['transfer_contract']['amount'], sold)
        self.assertEqual(owner.cash + buyer.cash, 30.0)

    def _public_action_fixture(self, action_id):
        owner = _person(300, cash=5.0, food=20, lord=True)
        trace_world, tile, owner, trace, economy = _fixture([owner], reserve=12)
        treasury_agent = _person(301, cash=100.0, food=0, output=Goods.gov)
        government = SimpleNamespace(agent=treasury_agent, food_inventory=0)
        nation = SimpleNamespace(name='Egypt', currency='EGP', government=government,
                                 tiles=[tile], legitimacy=0.6)
        tile.owner_nation = nation
        scenario_state = trace_world['scenario_state']
        scenario_state['public_maize_stock_units'] = 0
        return trace_world, nation, tile, owner, government, trace, economy

    def test_public_grain_purchase_pairs_treasury_payment_and_food_transfer(self):
        world, nation, tile, owner, government, trace, economy = \
            self._public_action_fixture('buy_private_grain')
        treasury_before = government.agent.cash
        owner_cash_before = owner.cash

        ok, _ = apply_action(world, nation, 'buy_private_grain')

        self.assertTrue(ok)
        cash = next(row for row in trace.rows
                    if row.get('metric_id') == 'finance.treasury_flow'
                    and row.get('kind') == 'scenario_public_grain_purchase')
        goods = next(row for row in trace.rows
                     if row.get('metric_id') == 'goods.grain_transfer'
                     and row.get('kind') == 'public_grain_purchase_food')
        contract = cash['inputs']['transfer_contract']
        goods_contract = goods['inputs']['transfer_contract']
        self.assertEqual(contract['contract_version'], 'treasury_transfer.v1')
        self.assertEqual(contract['payer_account']['balance_before'], treasury_before)
        self.assertEqual(contract['payer_account']['balance_after'], government.agent.cash)
        self.assertEqual(contract['payee_account']['balance_before'], owner_cash_before)
        self.assertEqual(contract['payee_account']['balance_after'], owner.cash)
        self.assertEqual(contract['operation_id'], goods_contract['operation_id'])
        self.assertEqual(goods['cause_event_ids'], [cash['event_id']])
        self.assertEqual(goods_contract['payer_account']['balance_before']
                         - goods_contract['payer_account']['balance_after'],
                         goods_contract['amount'])
        self.assertEqual(goods_contract['payee_account']['balance_after']
                         - goods_contract['payee_account']['balance_before'],
                         goods_contract['amount'])
        self.assertEqual(economy['grain_transactions'][0]['operation_ids'],
                         [contract['operation_id']])

    def test_private_grain_requisition_records_unpaid_stock_seizure_and_unrest(self):
        world, nation, tile, owner, government, trace, _ = \
            self._public_action_fixture('requisition_private_grain')
        owner_food_before = owner.inv_get(Goods.food, 0)
        public_food_before = government.food_inventory
        unrest_before = tile.unrest_level
        legitimacy_before = nation.legitimacy

        ok, _ = apply_action(world, nation, 'requisition_private_grain')

        self.assertTrue(ok)
        goods = next(row for row in trace.rows
                     if row.get('metric_id') == 'goods.grain_transfer'
                     and row.get('kind') == 'private_grain_requisition_food')
        contract = goods['inputs']['transfer_contract']
        self.assertEqual(contract['cash_transfer_status'], 'not_paid_requisition')
        self.assertEqual(contract['payer_account']['balance_before']
                         - contract['payer_account']['balance_after'],
                         contract['amount'])
        self.assertEqual(contract['payee_account']['balance_after']
                         - contract['payee_account']['balance_before'],
                         contract['amount'])
        self.assertEqual(owner.cash, 5.0)
        self.assertGreater(government.food_inventory, public_food_before)
        self.assertEqual(owner.inv_get(Goods.food, 0), owner_food_before
                         - contract['amount'])
        unrest = next(row for row in trace.rows
                      if row.get('metric_id') == 'politics.unrest_level')
        legitimacy = next(row for row in trace.rows
                          if row.get('metric_id') == 'politics.legitimacy')
        self.assertEqual(unrest['cause_event_ids'], [goods['event_id']])
        self.assertEqual(unrest['before'], unrest_before)
        self.assertGreater(unrest['after'], unrest_before)
        self.assertEqual(legitimacy['cause_event_ids'], [goods['event_id']])
        self.assertEqual(legitimacy['before'], legitimacy_before)
        self.assertLess(legitimacy['after'], legitimacy_before)


if __name__ == '__main__':
    unittest.main()
