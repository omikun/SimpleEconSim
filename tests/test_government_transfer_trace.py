import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from goods import Goods
from government import Government, _trace_public_transfer
from nutrition import appetite_units


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        sequence = clock['next']
        clock['next'] += 1
        self.rows.append({'event_id': f'test:{sequence}', **row})


class GovernmentTransferTraceTests(unittest.TestCase):
    def test_public_outflow_and_revenue_use_shared_transfer_contract(self):
        trace = MemoryTrace()
        clock = {'turn': 5, 'phase': 'government', 'next': 1}
        nation = SimpleNamespace(name='North', currency='NRC')
        region = SimpleNamespace(name='Delta', owner_nation=nation,
                                 home_currency='NRC', _run_trace=trace,
                                 _collective_trace_clock=clock, _last_turn=5)
        government = Government('North', 0)
        government.regions = [region]
        government.agent.cash = 90.0

        _trace_public_transfer(government, 'welfare_distributed', 10.0,
                               [101, 202], turn=5)
        government.agent.cash = 100.0
        _trace_public_transfer(government, 'legacy_tax_collected', 10.0, [],
                               outflow=False, tax_source='legacy_collect_tax',
                               turn=5)

        self.assertEqual(len(trace.rows), 2)
        welfare, tax = [row['inputs']['transfer_contract'] for row in trace.rows]
        self.assertEqual(welfare['contract_version'], 'treasury_transfer.v1')
        self.assertEqual(welfare['side'], 'payer')
        self.assertEqual(welfare['payer_account']['balance_before'], 100.0)
        self.assertEqual(welfare['payer_account']['balance_after'], 90.0)
        self.assertEqual(welfare['payee_account']['member_ids'], ['101', '202'])
        self.assertEqual(tax['side'], 'payee')
        self.assertEqual(tax['payee_account']['balance_before'], 90.0)
        self.assertEqual(tax['payee_account']['balance_after'], 100.0)
        self.assertEqual(tax['payee_account']['currency'], 'NRC')
        self.assertNotEqual(welfare['operation_id'], tax['operation_id'])

    def test_tariff_receipt_traces_national_and_local_treasury_shares(self):
        trace = MemoryTrace()
        clock = {'turn': 7, 'phase': 'government', 'next': 1}
        nation = SimpleNamespace(name='North', currency='NRC')
        region = SimpleNamespace(name='Port', owner_nation=nation,
                                 home_currency='NRC', _run_trace=trace,
                                 _collective_trace_clock=clock, _last_turn=7)
        nation_government = Government('North', 0)
        local_government = Government('Port District', 0)
        nation.government = nation_government
        nation_government.agent.cash = 100.0
        local_government.agent.cash = 20.0

        with patch('imperialism.get_imperialism_manager') as get_manager:
            get_manager.return_value.intercept_revenue.return_value = (100.0, 0.0, None)
            local_government.receive_tariff(7, 100.0, region=region)

        flows = [row for row in trace.rows
                 if row.get('metric_id') == 'finance.treasury_flow']
        self.assertEqual(len(flows), 2)
        self.assertEqual([row['after'] for row in flows], [80.0, 20.0])
        self.assertAlmostEqual(nation_government.agent.cash, 180.0)
        self.assertAlmostEqual(local_government.agent.cash, 40.0)
        self.assertEqual({row['inputs']['transfer_contract']['operation_id']
                          for row in flows}, {flows[0]['inputs']['operation_id']})
        allocations = {row['inputs']['tariff_allocation']: row for row in flows}
        for allocation, government, amount in (
                ('national', nation_government, 80.0),
                ('local_port', local_government, 20.0)):
            row = allocations[allocation]
            contract = row['inputs']['transfer_contract']
            self.assertEqual(contract['contract_version'], 'treasury_transfer.v1')
            self.assertEqual(contract['side'], 'payee')
            self.assertEqual(contract['payee_account']['id'], government.name)
            self.assertEqual(contract['payee_account']['balance_after']
                             - contract['payee_account']['balance_before'], amount)
            self.assertEqual(row['inputs']['gross_tariff'], 100.0)

    def test_emergency_food_levy_records_exact_donor_and_public_stock_changes(self):
        trace = MemoryTrace()
        clock = {'turn': 3, 'phase': 'livelihood', 'next': 1}
        nation = SimpleNamespace(name='North', currency='NRC')
        region = SimpleNamespace(name='Delta', owner_nation=nation,
                                 home_currency='NRC', _run_trace=trace,
                                 _collective_trace_clock=clock,
                                 emergency_grain_levy_units=0)
        donor = Agent(11)
        initialize_agent(donor, Goods.food, 0, 0, 0)
        donor.alive = True
        donor.is_corporation = False
        donor.is_government = False
        donor.inv_add(Goods.food, 24)
        recipient = Agent(12)
        initialize_agent(recipient, Goods.food, 0, 0, 0)
        recipient.alive = True
        recipient.is_corporation = False
        recipient.is_government = False
        recipients_need = appetite_units(recipient)
        government = Government('North', 0)
        government.food_inventory = 0
        donor_before = donor.inv_get(Goods.food, 0)
        government._levy_emergency_food(3, [donor, recipient], region)

        rows = [row for row in trace.rows
                if row.get('metric_id') == 'goods.emergency_levy']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        contract = row['inputs']['transfer_contract']
        donor_leg = contract['donor_legs'][0]
        self.assertEqual(contract['contract_version'], 'goods_transfer.v1')
        self.assertEqual(contract['amount'], recipients_need)
        self.assertEqual(contract['payee_account']['balance_before'], 0)
        self.assertEqual(contract['payee_account']['balance_after'], recipients_need)
        self.assertEqual(donor_leg['food_before'], donor_before)
        self.assertEqual(donor_leg['food_after'], donor_before - recipients_need)
        self.assertEqual(row['inputs']['remaining_meal_gap_units'], 0)


if __name__ == '__main__':
    unittest.main()
