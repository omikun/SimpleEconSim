import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from agent import Agent
from demographics_estate import (
    handle_company_inheritance,
    handle_wealth_inheritance,
    zero_out_dead_agent,
)
from econsim_trade_money import Bank
from goods import Goods
from run_trace import RunTrace, verify


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Government:
    def __init__(self, agent, probate_fee_rate=0.3):
        self.agent = agent
        self.probate_fee_rate = probate_fee_rate
        self.income = []

    def record_income(self, turn, source, amount):
        self.income.append((turn, source, amount))


class Charity:
    def __init__(self, agent):
        self.agent = agent
        self.food_inventory = 0

    def receive_food(self, quantity):
        self.food_inventory += quantity


def _agent(agent_id, *, cash=0.0, output=Goods.none):
    agent = Agent(0)
    agent.id = agent_id
    agent.cash = cash
    agent.output = output
    return agent


def _fixture(*, traced=True, frozen=False, heirs=True, deposits=10.0):
    trace = MemoryTrace()
    region = SimpleNamespace(
        name='Probate District', home_currency='GBP', agents=[],
        economic_events=[], _last_turn=7)
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 7, 'phase': 'demographics', 'next': 1}
    government_agent = _agent(90, cash=2.0, output=Goods.gov)
    charity_agent = _agent(91, cash=1.0)
    government = Government(government_agent)
    charity = Charity(charity_agent)
    bank = Bank(gov=SimpleNamespace(agent=government_agent))
    bank.is_frozen = frozen
    bank._attached_regions = [region]
    decedent = _agent(1, cash=9.0, output=Goods.wood)
    decedent.inventory[Goods.food.value] = 5
    decedent.inventory[Goods.wood.value] = 3
    heir = _agent(2, cash=4.0, output=Goods.food)
    heir._bank_ref = bank
    decedent.descendants = [heir] if heirs else []
    if deposits > 0:
        bank.deposits[decedent] = deposits
        bank.total_deposits = deposits
    region.agents = [decedent, heir, government_agent, charity_agent]
    ctx = SimpleNamespace(bank=bank, default_gov=government,
                          charity=charity, source_region=region)
    return region, ctx, decedent, heir, government, charity, bank, trace


class EstateWealthTraceTests(unittest.TestCase):
    def test_heir_cash_and_goods_trace_links_with_source_balance_evidence(self):
        region, ctx, decedent, heir, _gov, _charity, bank, trace = _fixture()

        event_ids = handle_wealth_inheritance(ctx, 7, decedent, [heir])
        zero_out_dead_agent(ctx, decedent, t=7, cause_event_ids=event_ids)

        withdrawal = next(row for row in trace.rows
                          if row.get('kind') == 'bank_withdrawal_posted')
        cash = next(row for row in trace.rows
                    if row.get('kind') == 'estate_cash_allocated')
        cash_closeout = next(row for row in trace.rows
                             if row.get('kind') == 'estate_decedent_cash_closed')
        food = next(row for row in trace.rows
                    if row.get('metric_id') == 'goods.inheritance_transfer'
                    and row.get('subject', {}).get('good') == 'food')

        self.assertIn(withdrawal['event_id'], cash['cause_event_ids'])
        self.assertEqual(cash['inputs']['deposit_withdrawal_requested'], 10.0)
        self.assertEqual(cash['inputs']['deposit_withdrawal_settled'], 10.0)
        self.assertEqual(cash['before'], 4.0)
        self.assertEqual(cash['after'], 23.0)
        self.assertIn(cash['event_id'], cash_closeout['cause_event_ids'])
        self.assertEqual((cash_closeout['before'], cash_closeout['after']),
                         (19.0, 0.0))
        self.assertEqual(food['before'], 5)
        self.assertEqual(food['after'], 5)
        self.assertEqual(food['inputs']['allocations'][0]['units'], 5)
        self.assertFalse(food['inputs']['source_inventory_debited'])
        self.assertEqual(decedent.inventory[Goods.food.value], 5)
        self.assertEqual(heir.inventory[Goods.food.value], 5)
        self.assertNotIn(decedent, bank.deposits)

    def test_heirless_cash_deposits_and_goods_record_destinations(self):
        region, ctx, decedent, _heir, government, charity, bank, trace = _fixture(
            heirs=False, deposits=10.0)

        event_ids = handle_wealth_inheritance(ctx, 7, decedent, [])
        zero_out_dead_agent(ctx, decedent, t=7, cause_event_ids=event_ids)

        cash_rows = [row for row in trace.rows
                     if row.get('kind') == 'estate_cash_allocated']
        self.assertEqual({row['inputs']['destination'] for row in cash_rows},
                         {'government', 'charity'})
        self.assertAlmostEqual(sum(row['inputs']['transfer_contract']['amount']
                                   for row in cash_rows), 9.0)
        deposit_rows = [row for row in trace.rows
                        if row.get('kind') == 'estate_deposit_allocated']
        self.assertEqual({row['inputs']['destination'] for row in deposit_rows},
                         {'government_probate', 'charity'})
        self.assertAlmostEqual(sum(row['inputs']['transfer_contract']['amount']
                                   for row in deposit_rows), 10.0)
        deposit_closeout = next(row for row in trace.rows
                                if row.get('kind') == 'estate_decedent_deposit_closed')
        self.assertEqual(set(deposit_closeout['cause_event_ids']),
                         {row['event_id'] for row in deposit_rows})
        for row in deposit_rows:
            source = row['inputs']['transfer_contract']['payer_account']
            self.assertEqual(source['balance_before'], 10.0)
            self.assertEqual(source['balance_after'], 10.0)
            self.assertEqual(source['source_closeout'],
                             'captured_by_estate_deposit_closeout')
        self.assertEqual(bank.total_deposits, 10.0)
        self.assertEqual(sum(bank.deposits.values()), 10.0)
        food = next(row for row in trace.rows
                    if row.get('metric_id') == 'goods.inheritance_transfer'
                    and row.get('subject', {}).get('good') == 'food')
        self.assertEqual(food['inputs']['allocations'][0]['recipient_type'],
                         'charity_food_stock')
        self.assertEqual(food['inputs']['allocations'][0]['units'], 5)
        wood = next(row for row in trace.rows
                    if row.get('metric_id') == 'goods.inheritance_transfer'
                    and row.get('subject', {}).get('good') == 'wood')
        self.assertEqual(wood['inputs']['allocations'][0]['recipient_type'],
                         'government_inventory')
        self.assertEqual(government.agent.inventory[Goods.wood.value], 3)
        self.assertEqual(charity.food_inventory, 5)
        self.assertEqual(decedent.inventory[Goods.food.value], 5)

    def test_frozen_bank_records_requested_and_settled_probate_draw(self):
        region, ctx, decedent, heir, _gov, _charity, bank, trace = _fixture(
            frozen=True, deposits=20.0)

        event_ids = handle_wealth_inheritance(ctx, 7, decedent, [heir])
        zero_out_dead_agent(ctx, decedent, t=7, cause_event_ids=event_ids)

        withdrawal = next(row for row in trace.rows
                          if row.get('kind') == 'bank_withdrawal_posted')
        allocation = next(row for row in trace.rows
                          if row.get('kind') == 'estate_cash_allocated')
        deposit_closeout = next(row for row in trace.rows
                                if row.get('kind') == 'estate_decedent_deposit_closed')
        self.assertEqual(withdrawal['inputs']['requested_amount'], 20.0)
        self.assertEqual(withdrawal['inputs']['settled_amount'], 5.0)
        self.assertEqual(allocation['inputs']['deposit_withdrawal_settled'], 5.0)
        self.assertEqual(allocation['inputs']['cash_pool_before_distribution'], 29.0)
        self.assertEqual(heir.cash, 33.0)
        self.assertEqual(deposit_closeout['inputs']['bank_deposit_account_sum_before'],
                         15.0)
        self.assertEqual(deposit_closeout['inputs']['bank_deposit_account_sum_after'],
                         0.0)
        self.assertEqual(bank.total_deposits, 15.0)

    def test_company_succession_records_selection_rule(self):
        region, _ctx, decedent, heir, _gov, _charity, _bank, trace = _fixture(
            deposits=0.0)
        company = SimpleNamespace(
            id=51, owner=decedent, alive=True, is_corporation=True,
            employees=[], name=lambda: 'Probate Mill')
        decedent.company_owned = company

        handle_company_inheritance(7, decedent, region)

        event = next(row for row in trace.rows
                     if row.get('kind') == 'estate_company_inherited')
        self.assertEqual(company.owner, heir)
        self.assertEqual(event['before'], decedent.id)
        self.assertEqual(event['after'], heir.id)
        self.assertEqual(event['inputs']['selected_by'],
                         'highest_current_cash')

    def test_trace_on_and_off_preserve_estate_settlement_state(self):
        traced = _fixture(traced=True)
        plain = _fixture(traced=False)

        for fixture in (traced, plain):
            region, ctx, decedent, heir = fixture[:4]
            event_ids = handle_wealth_inheritance(ctx, 7, decedent, [heir])
            zero_out_dead_agent(
                ctx, decedent, t=7,
                cause_event_ids=event_ids)

        for traced_actor, plain_actor in zip(traced[2:4], plain[2:4]):
            self.assertEqual(traced_actor.cash, plain_actor.cash)
            self.assertEqual(traced_actor.inventory, plain_actor.inventory)
            self.assertEqual(traced_actor.wallets, plain_actor.wallets)
        self.assertEqual(traced[6].total_deposits, plain[6].total_deposits)
        self.assertEqual(dict(traced[6].deposits), dict(plain[6].deposits))

    def test_estate_allocation_events_round_trip_compact_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'estate.ctr'
            trace = RunTrace(path, 'estate-fixture')
            fixture = _fixture(traced=False)
            region, ctx, decedent, heir = fixture[:4]
            region._run_trace = trace
            region._collective_trace_clock = {
                'turn': 7, 'phase': 'demographics', 'next': 1}

            event_ids = handle_wealth_inheritance(ctx, 7, decedent, [heir])
            zero_out_dead_agent(
                ctx, decedent, t=7,
                cause_event_ids=event_ids)

            allocations = trace.query(metric_id='finance.inheritance')
            goods = trace.query(metric_id='goods.inheritance_transfer')
            self.assertEqual(allocations['total'], 1)
            self.assertEqual(goods['total'], 2)
            self.assertEqual(verify(path)['rows'], trace.count)


if __name__ == '__main__':
    unittest.main()
