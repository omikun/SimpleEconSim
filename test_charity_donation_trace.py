"""Causal trace evidence for charity donations and their funding."""

import json
import unittest
from types import SimpleNamespace

from agent import Agent
from charity import Charity
from econsim_trade_money import Bank
from goods import Goods
from test_supply_rights import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f"charity-donation-test:{clock['next']}"
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced):
    region = Region()
    region.home_currency = 'USD'
    region.cash_obligations = []
    bank = Bank()
    bank._attached_regions = [region]
    region.bank = bank

    corporation = Agent(0)
    corporation.is_corporation = True
    corporation.cash = 20.0
    corporation.retained_earnings = 100.0

    wealthy = Agent(0)
    wealthy.cash = 2.0
    wealthy._bank_ref = bank
    bank.deposits[wealthy] = 1000.0
    bank.total_deposits = 1000.0
    wealthy.clear_wealth_cache()

    residents = [Agent(0) for _ in range(5)]
    for resident in residents:
        resident.hungry_steps = 1
    region.agents = [corporation, wealthy, *residents]

    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 8, 'phase': 'welfare', 'next': 1}
    charity = Charity(region.name, region.recipes)
    return charity, region, bank, corporation, wealthy, trace


def _state(fixture):
    charity, _region, bank, corporation, wealthy, _trace = fixture
    return {
        'corporation_cash': corporation.cash,
        'corporation_retained': corporation.retained_earnings,
        'wealthy_cash': wealthy.cash,
        'wealthy_deposit': bank.deposits[wealthy],
        'charity_cash': charity.agent.cash,
        'charity_deposit': bank.deposits[charity.agent],
        'donations_collected': charity.log['donations_collected'],
    }


class CharityDonationTraceTests(unittest.TestCase):
    def test_donor_transfers_and_bank_funding_are_exact_and_trace_neutral(self):
        fixtures = [_fixture(traced=False), _fixture(traced=True)]
        for charity, region, bank, _corp, _wealthy, _trace in fixtures:
            charity.collect_donations(8, region.agents, bank, regions=(region,))

        plain, traced = fixtures
        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(_state(traced)['corporation_cash'], 10.0)
        self.assertEqual(_state(traced)['corporation_retained'], 90.0)
        self.assertEqual(_state(traced)['wealthy_cash'], 0.0)
        self.assertEqual(_state(traced)['wealthy_deposit'], 965.92)
        self.assertEqual(_state(traced)['charity_deposit'], 46.08)

        rows = traced[5].rows
        transfers = [row for row in rows
                     if row.get('metric_id') == 'finance.cash_transfer'
                     and row.get('kind') == 'charity_donation']
        self.assertEqual(len(transfers), 2)
        by_type = {row['inputs']['donor_type']: row for row in transfers}

        corporate = by_type['corporation']['inputs']
        corporate_contract = corporate['transfer_contract']
        self.assertEqual(corporate_contract['amount'], 10.0)
        self.assertEqual(corporate_contract['payer_account']['balance_before'], 20.0)
        self.assertEqual(corporate_contract['payer_account']['balance_after'], 10.0)
        self.assertEqual(corporate_contract['payee_account']['balance_before'], 0.0)
        self.assertEqual(corporate_contract['payee_account']['balance_after'], 10.0)
        self.assertEqual(corporate['retained_earnings_before'], 100.0)
        self.assertEqual(corporate['retained_earnings_after'], 90.0)

        individual_row = by_type['wealthy_individual']
        individual = individual_row['inputs']
        individual_contract = individual['transfer_contract']
        self.assertEqual(individual_contract['amount'], 36.08)
        self.assertEqual(individual_contract['payer_account']['balance_before'], 36.08)
        self.assertEqual(individual_contract['payer_account']['balance_after'], 0.0)
        self.assertEqual(individual_contract['payee_account']['balance_before'], 10.0)
        self.assertEqual(individual_contract['payee_account']['balance_after'], 46.08)
        self.assertEqual(individual['bank_funding_requested'], 34.08)
        self.assertEqual(individual['bank_funding_settled'], 34.08)
        withdrawal_id = individual_row['cause_event_ids'][0]
        withdrawal = next(row for row in rows if row['event_id'] == withdrawal_id)
        self.assertEqual(withdrawal['metric_id'], 'finance.bank_withdrawal')
        self.assertEqual(withdrawal['inputs']['reason'], 'charity_donation')
        self.assertEqual(withdrawal['inputs']['settled_amount'], 34.08)


if __name__ == '__main__':
    unittest.main()
