import json
import unittest

from agent import Agent, initialize_agent
from army import MilitaryUnit, step_armies
from econsim_trade_money import Bank
from goods import Goods
from nation import Nation
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _agent(agent_id, output, cash=0.0):
    person = Agent(0)
    initialize_agent(person, output, 0, 0, cash)
    person.id = agent_id
    person.alive = True
    return person


def _scenario_personnel_fixture(*, traced=True):
    nation = Nation('Khedivate', currency='EGP', initial_cash=100.0,
                    register=False)
    region = Region('Cairo', t=0, number_of_agents=0)
    region.recipes[Goods.food]['price'] = 3.0
    nation.add_tile(region)
    seller = _agent(501, Goods.food, cash=10.0)
    seller.inv_add(Goods.food, 12)
    soldiers = [_agent(601, Goods.none), _agent(602, Goods.none)]
    region.agents.extend([seller, *soldiers])
    nation.government.food_inventory = 0
    unit = MilitaryUnit('cairo-guard', nation.name, region.name,
                        soldiers=2, wage_per_soldier=2.0,
                        food_per_soldier=2.0)
    unit.scenario_personnel = True
    unit.person_ids = [person.id for person in soldiers]
    unit.prior_outputs = {person.id: Goods.none.name for person in soldiers}
    nation.military_units = [unit]
    region.military_units = [unit]
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 3, 'phase': 'military', 'next': 1}
    sellers = [person for person in region.agents
               if person.output == Goods.food and not person.is_government]
    seller_balances_before = {person.id: (person.cash,
                                           person.inv_get(Goods.food, 0))
                              for person in sellers}
    return nation, region, sellers, seller_balances_before, soldiers, unit, trace


class MilitaryUpkeepTraceTests(unittest.TestCase):
    def test_ration_purchase_payroll_and_consumption_reconcile(self):
        (nation, region, sellers, seller_balances_before, soldiers, unit,
         trace) = _scenario_personnel_fixture()
        result = step_armies([region], [nation], t=3)
        plain = _scenario_personnel_fixture(traced=False)
        step_armies([plain[1]], [plain[0]], t=3)

        def state(fixture):
            fixture_nation, _region, fixture_sellers, _opening, fixture_soldiers, fixture_unit, _trace = fixture
            return (fixture_nation.government.agent.cash,
                    fixture_nation.government.food_inventory,
                    sorted((seller.cash, seller.inv_get(Goods.food, 0))
                           for seller in fixture_sellers),
                    [person.cash for person in fixture_soldiers],
                    fixture_unit.morale, fixture_unit.soldiers)

        self.assertEqual(state((nation, region, sellers, seller_balances_before,
                                soldiers, unit, trace)), state(plain))

        cash_transfers = [row for row in trace.rows
                          if row.get('kind') == 'army_ration_cash_payment']
        self.assertEqual(sum(row['after'] for row in cash_transfers), 24.0)
        cash_transfer = cash_transfers[0]
        cash_contract = cash_transfer['inputs']['transfer_contract']
        self.assertEqual(cash_contract['operation_type'],
                         'military_ration_procurement')

        food_sources = [row for row in trace.rows
                        if row.get('kind') == 'army_ration_food_source']
        food_receipts = [row for row in trace.rows
                         if row.get('kind') == 'army_ration_food_receipt']
        self.assertEqual(len(cash_transfers), len(food_sources))
        self.assertEqual(len(food_sources), len(food_receipts))
        self.assertEqual(sum(row['before'] - row['after']
                             for row in food_sources), 8)
        self.assertEqual(sum(row['after'] - row['before']
                             for row in food_receipts), 8)
        self.assertEqual({row['inputs']['operation_id'] for row in cash_transfers},
                         {row['inputs']['operation_id'] for row in food_sources})
        self.assertEqual({row['inputs']['operation_id'] for row in food_sources},
                         {row['inputs']['operation_id'] for row in food_receipts})
        for food_source, food_receipt in zip(food_sources, food_receipts):
            self.assertEqual(food_source['inputs']['transfer_contract'],
                             food_receipt['inputs']['transfer_contract'])
        procurement = next(row for row in trace.rows
                           if row.get('kind') == 'army_ration_procurement')
        self.assertEqual(procurement['inputs']['outcome'], 'target_funded')
        self.assertEqual(procurement['inputs']['food_purchased'], 8)
        self.assertTrue(all(row['event_id'] in procurement['cause_event_ids']
                            for row in [*cash_transfers, *food_sources,
                                        *food_receipts]))

        payroll = next(row for row in trace.rows
                       if row.get('kind') == 'army_payroll')
        self.assertEqual(payroll['after'], -4.0)
        self.assertEqual(payroll.get('cause_event_ids') or [], [])
        self.assertEqual(payroll['inputs']['treasury_cash_after_payroll'], 72.0)
        recipients = [row for row in trace.rows
                      if row.get('kind') == 'army_payroll_recipient']
        self.assertEqual(len(recipients), 2)
        self.assertEqual(sum(row['after'] - row['before'] for row in recipients), 4.0)
        self.assertTrue(all(row['cause_event_ids'] == [payroll['event_id']]
                            for row in recipients))

        consumption = next(row for row in trace.rows
                           if row.get('kind') == 'army_ration_consumption')
        self.assertEqual((consumption['before'], consumption['after']), (8, 4))
        upkeep = next(row for row in trace.rows
                      if row.get('kind') == 'army_upkeep_outcome')
        self.assertTrue(upkeep['inputs']['fully_supplied'])
        self.assertEqual(upkeep['inputs']['morale_after'], 1.0)
        self.assertEqual(upkeep['inputs']['deserters'], 0)
        self.assertEqual((nation.government.agent.cash,
                          nation.government.food_inventory), (72.0, 4))
        self.assertEqual(sum(person.cash - seller_balances_before[person.id][0]
                             for person in sellers), 24.0)
        self.assertEqual(sum(seller_balances_before[person.id][1]
                             - person.inv_get(Goods.food, 0)
                             for person in sellers), 8)
        self.assertEqual([person.cash for person in soldiers], [2.0, 2.0])
        self.assertEqual([event['event'] for event in result], ['ARMY_UPKEEP'])

    def test_bank_funding_and_shortage_explain_morale_drop_with_trace_parity(self):
        def run(traced):
            nation = Nation('Frontier', currency='FR', initial_cash=1.0,
                            register=False)
            region = Region('Fort', t=0, number_of_agents=0)
            nation.add_tile(region)
            nation.government.food_inventory = 0
            bank = Bank()
            bank.total_deposits = 3.0
            bank.deposits[nation.government.agent] = 3.0
            region.bank = bank
            unit = MilitaryUnit('frontier-unit', nation.name, region.name,
                                soldiers=2, morale=0.4,
                                wage_per_soldier=5.0, food_per_soldier=1.0)
            nation.military_units = [unit]
            region.military_units = [unit]
            trace = MemoryTrace()
            if traced:
                region._run_trace = trace
                region._collective_trace_clock = {
                    'turn': 4, 'phase': 'military', 'next': 1}
            step_armies([region], [nation], t=4)
            state = (nation.government.agent.cash, bank.total_deposits,
                     nation.government.food_inventory, unit.morale,
                     unit.soldiers)
            return state, trace

        traced_state, trace = run(True)
        plain_state, _ = run(False)
        self.assertEqual(traced_state, plain_state)
        withdrawal = next(row for row in trace.rows
                          if row.get('kind') == 'bank_withdrawal_posted')
        payroll = next(row for row in trace.rows
                       if row.get('kind') == 'army_payroll')
        self.assertEqual(withdrawal['inputs']['reason'], 'military_payroll')
        self.assertEqual(payroll['cause_event_ids'], [withdrawal['event_id']])
        self.assertEqual(payroll['after'], -4.0)
        upkeep = next(row for row in trace.rows
                      if row.get('kind') == 'army_upkeep_outcome')
        self.assertEqual(upkeep['inputs']['unpaid_wages'], 6.0)
        self.assertEqual(upkeep['inputs']['food_unmet'], 2)
        self.assertAlmostEqual(upkeep['inputs']['morale_after'], 0.1)
        self.assertEqual(upkeep['inputs']['supply_shortage_reason'],
                         'rations_below_unit_need')


if __name__ == '__main__':
    unittest.main()
