import copy
import unittest
from types import SimpleNamespace

from food_logistics import deliver_province_food, dispatch_province_food
from goods import Goods
from nation import Nation
from province import Province
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, with_trace=True):
    nation = Nation('Relief Nation', initial_cash=500)
    province = Province('Relief Province', nation)
    source = Region('Surplus', 0, 3, institutions=province.institutions)
    destination = Region('Hungry', 0, 3, institutions=province.institutions)
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
        person.calorie_deficit_kcal = 0
    source_people[0].inv_set(Goods.food, 1000)
    for person in destination_people:
        person.calorie_deficit_kcal = 1000
        person.hungry_steps = 1
    province.gov.emergency_food_policy = True
    province.gov.agent.cash = 100.0
    trace = MemoryTrace()
    clock = {'turn': 1, 'phase': 'local', 'next': 1}
    if with_trace:
        for tile in province.tiles:
            tile._run_trace = trace
            tile._collective_trace_clock = clock
    return SimpleNamespace(
        nation=nation, province=province, source=source,
        destination=destination, source_people=source_people,
        destination_people=destination_people, trace=trace)


def _contract(row):
    return row['inputs']['transfer_contract']


def _state(fixture):
    province = fixture.province
    agents = [a for tile in province.tiles for a in tile.agents]
    return {
        'food': sorted((a.output.name, bool(a.is_government), bool(a.is_corporation),
                        int(a.inv_get(Goods.food, 0))) for a in agents),
        'cash': sorted((a.output.name, bool(a.is_government), bool(a.is_corporation),
                        round(float(a.cash), 6)) for a in agents),
        'government_cash': round(float(province.gov.agent.cash), 6),
        'government_food': int(province.gov.food_inventory),
        'bank_deposit': round(float(province.bank.deposits.get(province.gov.agent, 0)), 6),
        'shipments': list(province.food_shipments),
        'levy_total': int(province.gov.food_levy_last_turn),
    }


class ProvincialReliefTransferTraceTests(unittest.TestCase):
    def test_route_traces_donor_cargo_haulage_and_household_legs(self):
        fixture = _fixture()
        province = fixture.province
        shipments = dispatch_province_food(province, 1)
        self.assertEqual(len(shipments), 1)
        shipment = shipments[0]
        shipment_id = shipment['shipment_id']
        rows = fixture.trace.rows

        donor_rows = [row for row in rows
                      if row.get('kind') == 'provincial_relief_donor_transfer']
        self.assertEqual(sum(_contract(row)['amount'] for row in donor_rows),
                         shipment['units'])
        for row in donor_rows:
            contract = _contract(row)
            self.assertEqual(contract['contract_version'], 'goods_transfer.v1')
            self.assertEqual(contract['operation_id'],
                             row['inputs']['operation_id'])
            self.assertEqual(contract['payer_account']['balance_before']
                             - contract['payer_account']['balance_after'],
                             contract['amount'])
            self.assertEqual(contract['payee_account']['balance_after']
                             - contract['payee_account']['balance_before'],
                             contract['amount'])

        haulage = next(row for row in rows
                       if row.get('kind') == 'provincial_food_haulage_payment')
        cash_contract = _contract(haulage)
        self.assertAlmostEqual(cash_contract['amount'], shipment['haulage_wages'])
        self.assertAlmostEqual(cash_contract['payer_account']['balance_before']
                               - cash_contract['payer_account']['balance_after'],
                               cash_contract['amount'])
        self.assertAlmostEqual(
            sum(member['amount'] for member in cash_contract['payee_account']['members']),
            cash_contract['amount'])
        self.assertIn(haulage['event_id'],
                      next(row for row in rows
                           if row.get('kind') == 'provincial_food_dispatch')
                      ['cause_event_ids'])
        treasury_flow = next(row for row in rows
                             if row.get('metric_id') == 'finance.treasury_flow'
                             and row.get('kind') ==
                             'government_provincial_food_haulage_payment')
        self.assertAlmostEqual(treasury_flow['after'],
                               -shipment['haulage_wages'])
        self.assertEqual(treasury_flow['subject'],
                         {'type': 'nation', 'id': 'Relief Nation'})
        self.assertIn(haulage['event_id'], treasury_flow['cause_event_ids'])

        deliver_province_food(province, 2)
        arrival_rows = [row for row in fixture.trace.rows
                        if row.get('kind') == 'provincial_relief_recipient_transfer']
        self.assertEqual(sum(_contract(row)['amount'] for row in arrival_rows),
                         shipment['units'])
        for row in arrival_rows:
            contract = _contract(row)
            self.assertEqual(contract['payer_account']['balance_before']
                             - contract['payer_account']['balance_after'],
                             contract['amount'])
            self.assertEqual(contract['payee_account']['balance_after']
                             - contract['payee_account']['balance_before'],
                             contract['amount'])
        arrival = next(row for row in fixture.trace.rows
                       if row.get('kind') == 'provincial_food_arrival')
        self.assertTrue(all(row['event_id'] in arrival['cause_event_ids']
                            for row in arrival_rows))
        self.assertEqual(arrival['inputs']['dispatch_operation_id'], shipment_id)
        self.assertFalse(province.food_shipments)

    def test_food_not_needed_at_arrival_moves_to_public_stock(self):
        fixture = _fixture()
        shipment = dispatch_province_food(fixture.province, 1)[0]
        for person in fixture.destination_people:
            person.inv_set(Goods.food, 100)

        deliver_province_food(fixture.province, 2)

        stock_transfer = next(row for row in fixture.trace.rows
                              if row.get('kind') ==
                              'provincial_relief_government_stock_transfer')
        contract = _contract(stock_transfer)
        self.assertEqual(contract['amount'], shipment['units'])
        self.assertEqual(contract['payee_account']['type'],
                         'government_food_inventory')
        self.assertEqual(contract['payee_account']['balance_after']
                         - contract['payee_account']['balance_before'],
                         shipment['units'])

    def test_unaffordable_route_records_why_no_shipment_was_dispatched(self):
        fixture = _fixture()
        fixture.province.gov.agent.cash = 0.0
        fixture.province.bank.deposits[fixture.province.gov.agent] = 0.0

        self.assertEqual(dispatch_province_food(fixture.province, 1), [])

        outcome = next(row for row in fixture.trace.rows
                       if row.get('kind') == 'provincial_food_dispatch_skipped')
        self.assertEqual(outcome['record_class'], 'outcome')
        self.assertEqual(outcome['inputs']['reason'], 'haulage_unaffordable')
        self.assertGreater(outcome['inputs']['unmet_food_units'], 0)
        self.assertEqual(outcome['inputs']['liquid_funds'], 0.0)
        self.assertEqual(outcome['inputs']['affordable_food_units'], 0)

    def test_optional_trace_does_not_change_relief_state(self):
        plain = _fixture(with_trace=False)
        traced = copy.deepcopy(plain)
        clock = {'turn': 1, 'phase': 'local', 'next': 1}
        for tile in traced.province.tiles:
            tile._run_trace = traced.trace
            tile._collective_trace_clock = clock
        traced_shipments = dispatch_province_food(traced.province, 1)
        plain_shipments = dispatch_province_food(plain.province, 1)
        self.assertEqual(traced_shipments, plain_shipments)
        self.assertEqual(_state(traced), _state(plain))

        deliver_province_food(traced.province, 2)
        deliver_province_food(plain.province, 2)
        self.assertEqual(_state(traced), _state(plain))


if __name__ == '__main__':
    unittest.main()
