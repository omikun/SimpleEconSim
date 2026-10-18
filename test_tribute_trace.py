import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from feudal_tribute import collect_tribute, record_tribute_value
from goods import Goods
from land_tenure import LandPlot, TileTenure, TenureStatus


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _person(agent_id, *, lord=False):
    person = Agent(agent_id)
    person.id = agent_id
    initialize_agent(person, Goods.food, 0, 0, 0.0)
    person.id = agent_id
    person.alive = True
    person.is_lord = lord
    person.is_government = False
    person.is_corporation = False
    person.is_trader = False
    person.hungry_steps = 0
    return person


def _fixture(with_trace=True, *, protest=0.0):
    lord = _person(1, lord=True)
    serf = _person(2)
    lord.inv_set(Goods.food, 0)
    lord.inv_set(Goods.wood, 0)
    serf.inv_set(Goods.food, 10)
    serf.inv_set(Goods.wood, 6)
    plot = LandPlot('feudal-plot', 'Serf Village', lord.id,
                    tenure=TenureStatus.FEUDAL, fraction=1.0,
                    tenant_ids=[serf.id], tribute_rate=0.5)
    trace = MemoryTrace()
    region = SimpleNamespace(
        name='Serf Village', home_currency='SRF', agents=[lord, serf],
        tenure=TileTenure([plot]), protest_energy_log=[protest],
        military_units=[], police_employed=0, food_price=2.0,
        recipes={Goods.food: {'price': 2.0}, Goods.wood: {'price': 4.0}},
        _run_trace=trace,
        _collective_trace_clock={'turn': 10, 'phase': 'economy', 'next': 1})
    if not with_trace:
        del region._run_trace
        del region._collective_trace_clock
    return region, lord, serf, trace


class FeudalTributeTraceTests(unittest.TestCase):
    def test_trace_return_shape_is_stable_when_region_has_no_feudal_plots(self):
        region = SimpleNamespace(name='Commons', tenure=TileTenure(), agents=[])
        self.assertEqual(collect_tribute(region, 10, return_trace=True), ({}, []))

    def test_tribute_records_inventory_legs_and_legacy_value_explanation(self):
        region, lord, serf, trace = _fixture()

        collected, event_ids = collect_tribute(region, 10, return_trace=True)
        value, valuation_id = record_tribute_value(
            region, 10, collected, cause_event_ids=event_ids)

        self.assertEqual(collected[lord.id], {Goods.food: 3, Goods.wood: 3})
        self.assertEqual((serf.inv_get(Goods.food), lord.inv_get(Goods.food)), (7, 3))
        self.assertEqual((serf.inv_get(Goods.wood), lord.inv_get(Goods.wood)), (3, 3))
        self.assertEqual(value, 18.0)
        transfers = [row for row in trace.rows
                     if row.get('metric_id') == 'goods.feudal_tribute'
                     and row.get('kind') == 'feudal_tribute_transfer']
        self.assertEqual(len(transfers), 2)
        for row in transfers:
            contract = row['inputs']['transfer_contract']
            self.assertEqual(contract['contract_version'], 'goods_transfer.v1')
            self.assertEqual(contract['cash_transfer_status'], 'in_kind_no_cash')
            self.assertEqual(contract['operation_id'], row['inputs']['operation_id'])
            self.assertEqual(
                contract['payer_account']['balance_before']
                - contract['payer_account']['balance_after'], contract['amount'])
            self.assertEqual(
                contract['payee_account']['balance_after']
                - contract['payee_account']['balance_before'], contract['amount'])
            self.assertFalse(row['inputs']['force_present'])
            self.assertEqual(row['inputs']['tribute_rate'], 0.5)
        valuation = next(row for row in trace.rows
                         if row.get('metric_id') == 'finance.tribute_value')
        self.assertEqual(valuation['event_id'], valuation_id)
        self.assertEqual(valuation['after'], 18.0)
        self.assertEqual(set(valuation['cause_event_ids']),
                         {row['event_id'] for row in transfers})
        self.assertEqual(
            {row['source_id'] for row in region.economic_events
             if row['kind'] == 'feudal_tribute'},
            {row['inputs']['operation_id'] for row in transfers})

    def test_trace_does_not_change_tribute_balances_or_operation_ids(self):
        traced, _, traced_serf, trace = _fixture(True)
        plain, _, plain_serf, _ = _fixture(False)

        traced_data, _ = collect_tribute(traced, 10, return_trace=True)
        plain_data, _ = collect_tribute(plain, 10, return_trace=True)
        traced_value, _ = record_tribute_value(traced, 10, traced_data)
        plain_value, _ = record_tribute_value(plain, 10, plain_data)

        self.assertEqual(traced_data, plain_data)
        self.assertEqual(traced_value, plain_value)
        self.assertEqual((traced_serf.inv_get(Goods.food), traced_serf.inv_get(Goods.wood)),
                         (plain_serf.inv_get(Goods.food), plain_serf.inv_get(Goods.wood)))
        traced_ids = sorted(row['inputs']['operation_id'] for row in trace.rows
                            if row.get('kind') == 'feudal_tribute_transfer')
        plain_ids = sorted(row['source_id'] for row in plain.economic_events
                           if row['kind'] == 'feudal_tribute')
        self.assertEqual(traced_ids, plain_ids)

    def test_open_resistance_records_why_lords_receive_no_tribute(self):
        region, lord, serf, trace = _fixture(protest=6.0)

        collected = collect_tribute(region, 10)

        self.assertEqual(collected, {})
        self.assertEqual(serf.inv_get(Goods.food), 10)
        self.assertEqual(lord.inv_get(Goods.food), 0)
        withheld = next(row for row in trace.rows
                        if row.get('kind') == 'feudal_tribute_withheld')
        self.assertEqual(withheld['inputs']['reason'],
                         'open_resistance_without_armed_enforcement')
        self.assertEqual(withheld['inputs']['assigned_serf_ids'], [serf.id])


if __name__ == '__main__':
    unittest.main()
