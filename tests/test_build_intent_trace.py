"""Causal trace for public construction funding and contractor commissioning."""

import json
import random
import unittest

from econsim_trade_money import Bank
from intents import BuildIntent
from nation import Nation
from random_cache import rand
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'construction-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, funding, traced):
    rng_state_before = random.getstate()
    rng_cache_index_before = rand._idx
    random.seed(3402)
    # Keep construction's cached RNG draw comparable without making a cache
    # refill (which intentionally consumes the module-level random stream).
    rand._idx = 0
    nation = Nation('Commonwealth', initial_cash=0.0, register=False)
    tile = Region('Oxfordshire', 0, 0)
    nation.add_tile(tile)
    tile.bank = Bank(tile.gov)
    tile.gov.agent.cash = 0.0
    nation.government.agent.cash = 0.0
    tile.gov.agent.home_currency = nation.currency
    nation.government.agent.home_currency = nation.currency

    if funding == 'cash':
        tile.gov.agent.cash = 300.0
    elif funding in ('deposit', 'frozen_deposit'):
        tile.bank.deposits[tile.gov.agent] = 300.0
        tile.bank.total_deposits = 300.0
        if funding == 'frozen_deposit':
            tile.bank.is_frozen = True
            tile.bank.subsistence_withdrawal_cap = 5.0
    elif funding == 'rollback':
        tile.bank.deposits[tile.gov.agent] = 100.0
        tile.bank.total_deposits = 100.0
        tile.bank.capital = 0.0
        national_bank = Bank(nation.government)
        national_bank.deposits[nation.government.agent] = 200.0
        national_bank.total_deposits = 200.0
        nation.government._bank_ref = national_bank
    else:
        raise ValueError(f'Unknown funding fixture: {funding}')

    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 4, 'phase': 'strategy', 'next': 1}
    intent = BuildIntent(nation.name, tile.name, 'turnpike_road', submitted_turn=4)
    result = intent.execute({tile.name: tile}, {nation.name: nation}, t=4)
    contractor_cash = (intent.project.contractor.cash if intent.project else None)
    national_bank = getattr(nation.government, '_bank_ref', None)
    state = {
        'success': result[0],
        'status': intent.status,
        'municipal_cash': tile.gov.agent.cash,
        'national_cash': nation.government.agent.cash,
        'deposit': float(tile.bank.deposits[tile.gov.agent]),
        'national_deposit': float(
            national_bank.deposits.get(nation.government.agent, 0.0)
            if national_bank is not None else 0.0),
        'bank_capital': float(tile.bank.capital),
        'contractor_cash': contractor_cash,
        'project_status': intent.project.status if intent.project else None,
        'rng_state_after': random.getstate(),
        'rng_cache_index_after': rand._idx,
    }
    random.setstate(rng_state_before)
    rand._idx = rng_cache_index_before
    return nation, tile, intent, result, state, trace


class BuildIntentTraceTests(unittest.TestCase):
    def test_cash_and_deposit_funding_link_through_contractor_payment(self):
        for funding in ('cash', 'deposit'):
            with self.subTest(funding=funding):
                plain = _fixture(funding=funding, traced=False)
                traced = _fixture(funding=funding, traced=True)
                self.assertEqual(traced[3][0], plain[3][0])
                self.assertEqual(traced[4], plain[4])
                self.assertTrue(traced[3][0])

                rows = traced[5].rows
                decision = next(row for row in rows
                                if row.get('metric_id') ==
                                'construction.funding_decision')
                payment = next(row for row in rows
                               if row.get('metric_id') == 'finance.cash_transfer'
                               and row.get('kind') == 'construction_contractor_payment')
                commission = next(row for row in rows
                                  if row.get('metric_id') ==
                                  'construction.project_commission')
                self.assertTrue(decision['after'])
                self.assertEqual(decision['inputs']['amount_counted_for_project'], 300.0)
                contract = payment['inputs']['transfer_contract']
                self.assertEqual(contract['amount'], 300.0)
                self.assertEqual(contract['payee_account']['balance_after'],
                                 contract['payee_account']['balance_before'] + 300.0)
                payer = payment['inputs']['transfer_contract']['payer_account']
                self.assertFalse(payer['cash_balance_captured'])
                self.assertEqual(len(payer['source_legs']), 1)
                self.assertEqual(payment['cause_event_ids'][0], decision['event_id'])
                self.assertEqual(commission['cause_event_ids'],
                                 [decision['event_id'], payment['event_id']])

                leg = payer['source_legs'][0]
                if funding == 'cash':
                    self.assertEqual(leg['source_kind'], 'government_wallet_cash')
                    self.assertEqual(leg['cash_before'], 300.0)
                    self.assertEqual(leg['cash_after'], 0.0)
                else:
                    self.assertEqual(leg['source_kind'], 'government_bank_deposit')
                    self.assertEqual(leg['bank_withdrawal_settled'], 300.0)
                    self.assertEqual(len(leg['withdrawal_event_ids']), 1)
                    withdrawal = next(row for row in rows
                                      if row['event_id'] == leg['withdrawal_event_ids'][0])
                    self.assertEqual(withdrawal['metric_id'], 'finance.bank_withdrawal')
                    self.assertIn(withdrawal['event_id'], payment['cause_event_ids'])

    def test_frozen_deposit_trace_shows_requested_settled_and_wallet_gap(self):
        plain = _fixture(funding='frozen_deposit', traced=False)
        traced = _fixture(funding='frozen_deposit', traced=True)
        self.assertEqual(traced[3][0], plain[3][0])
        self.assertEqual(traced[4], plain[4])
        self.assertTrue(traced[3][0])
        self.assertEqual(traced[4]['municipal_cash'], -295.0)
        self.assertEqual(traced[4]['deposit'], 295.0)

        rows = traced[5].rows
        payment = next(row for row in rows
                       if row.get('kind') == 'construction_contractor_payment')
        leg = payment['inputs']['transfer_contract']['payer_account']['source_legs'][0]
        self.assertEqual(leg['bank_withdrawal_requested'], 300.0)
        self.assertEqual(leg['bank_withdrawal_settled'], 5.0)
        self.assertEqual(leg['unsettled_withdrawal_request'], 295.0)
        self.assertEqual(leg['government_cash_after_funding_debit'], -295.0)
        payee = payment['inputs']['transfer_contract']['payee_account']
        self.assertEqual(payee['balance_after'], payee['balance_before'] + 300.0)

    def test_shortfall_trace_records_cash_rollback_but_kept_bank_settlement(self):
        plain = _fixture(funding='rollback', traced=False)
        traced = _fixture(funding='rollback', traced=True)
        self.assertEqual(traced[3][0], plain[3][0])
        self.assertEqual(traced[4], plain[4])
        self.assertFalse(traced[3][0])
        self.assertIsNone(traced[2].project)
        self.assertEqual(traced[4]['municipal_cash'], 100.0)
        self.assertEqual(traced[4]['deposit'], 0.0)
        self.assertEqual(traced[4]['national_deposit'], 200.0)

        rows = traced[5].rows
        decision = next(row for row in rows
                        if row.get('metric_id') ==
                        'construction.funding_decision')
        self.assertFalse(decision['after'])
        self.assertEqual(decision['inputs']['remaining_gap'], 200.0)
        self.assertEqual(decision['inputs']['treasury_total_before'], 300.0)
        self.assertEqual(decision['inputs']['treasury_total_after_rollback'], 300.0)
        self.assertEqual(decision['inputs']['rollback_legs'][0]['amount_restored'],
                         100.0)
        self.assertEqual(decision['inputs']['rollback_legs'][0]['cash_after'], 100.0)
        self.assertEqual(len(decision['inputs']['bank_withdrawal_event_ids']), 1)
        withdrawal = next(row for row in rows
                          if row['event_id'] ==
                          decision['inputs']['bank_withdrawal_event_ids'][0])
        self.assertEqual(withdrawal['inputs']['settled_amount'], 100.0)
        self.assertFalse(any(row.get('metric_id') == 'finance.cash_transfer'
                             for row in rows))


if __name__ == '__main__':
    unittest.main()
