"""Per-recipient trace contracts for government cash benefits."""

import json
import unittest
from types import SimpleNamespace

from agent import Agent
from government import Government


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f"public-benefit-test:{clock['next']}"
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, cash, traced):
    trace = MemoryTrace()
    region = SimpleNamespace(
        name='Benefit Ward', home_currency='USD',
        owner_nation=SimpleNamespace(name='Benefit Nation', currency='USD'),
        economic_events=[], _last_turn=1)
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 1, 'phase': 'government', 'next': 1}
    government = Government('Benefit Nation', 0, initial_cash=cash)
    government.regions = [region]
    return government, region, trace


def _payments(trace, benefit_kind):
    return [row for row in trace.rows
            if row.get('metric_id') == 'finance.cash_transfer'
            and row.get('record_class') == 'transfer'
            and row.get('inputs', {}).get('benefit_kind') == benefit_kind]


class PublicBenefitTraceTests(unittest.TestCase):
    def test_empty_or_negative_treasury_cannot_mint_ubi_or_erase_debt(self):
        for cash in (0., -3.):
            for traced in (False, True):
                with self.subTest(cash=cash, traced=traced):
                    government, region, trace = _fixture(cash=cash, traced=traced)
                    citizens = [Agent(0), Agent(0)]
                    for citizen in citizens:
                        citizen.cash = 5.
                        government._add_citizen(citizen)
                    government.ubi_enabled = True
                    government.ubi_amount_per_turn = 2.
                    before = government.agent.cash+sum(c.cash for c in citizens)
                    paid = government.distribute_ubi(1, citizens, region)
                    self.assertEqual(0., paid)
                    self.assertEqual(cash, government.agent.cash)
                    self.assertEqual([5.,5.], [c.cash for c in citizens])
                    self.assertEqual(before, government.agent.cash+sum(c.cash for c in citizens))
                    self.assertEqual([], region.economic_events)
                    if traced:
                        self.assertEqual('ubi_unfunded', trace.rows[0]['kind'])
                        self.assertEqual([], _payments(trace, 'ubi_payment'))

    def test_baby_bonus_receipt_links_to_treasury_outflow(self):
        fixtures = [_fixture(cash=100.0, traced=False),
                    _fixture(cash=100.0, traced=True)]
        states = []
        for government, region, _trace in fixtures:
            parent, newborn = Agent(0), Agent(0)
            parent.cash = 4.0
            government.baby_bonus_enabled = True
            government.baby_bonus_amount = 10.0
            government.provide_baby_bonus(1, parent, newborn, region)
            states.append((government.agent.cash, parent.cash,
                           [row['amount'] for row in region.economic_events]))
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[0][:2], (90.0, 14.0))

        rows = fixtures[1][2].rows
        treasury = next(row for row in rows
                        if row.get('metric_id') == 'finance.treasury_flow')
        payment = _payments(fixtures[1][2], 'baby_bonus')[0]
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(contract['amount'], 10.0)
        self.assertEqual(contract['payer_account']['balance_status'],
                         'see_linked_aggregate_treasury_leg')
        self.assertEqual(contract['payer_account']['aggregate_treasury_event_ids'],
                         [treasury['event_id']])
        self.assertEqual(contract['payee_account']['balance_before'], 4.0)
        self.assertEqual(contract['payee_account']['balance_after'], 14.0)
        self.assertEqual(payment['cause_event_ids'], [treasury['event_id']])
        journal = next(event for event in fixtures[1][1].economic_events
                       if event['kind'] == 'baby_bonus')
        self.assertEqual(journal['source_id'], contract['operation_id'])
        self.assertEqual(treasury['cause_event_ids'], None)

    def test_scaled_ubi_traces_each_actual_recipient_amount(self):
        fixtures = [_fixture(cash=3.0, traced=False),
                    _fixture(cash=3.0, traced=True)]
        states = []
        for government, region, _trace in fixtures:
            citizens = [Agent(0), Agent(0)]
            citizens[0].cash, citizens[1].cash = 5.0, 7.0
            for citizen in citizens:
                government._add_citizen(citizen)
            government.ubi_enabled = True
            government.ubi_amount_per_turn = 2.0
            total = government.distribute_ubi(1, citizens, region)
            states.append((government.agent.cash,
                           [citizen.cash for citizen in citizens], total))
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[1], (0.0, [6.5, 8.5], 3.0))

        rows = fixtures[1][2].rows
        treasury = next(row for row in rows
                        if row.get('metric_id') == 'finance.treasury_flow')
        payments = _payments(fixtures[1][2], 'ubi_payment')
        self.assertEqual(len(payments), 2)
        self.assertEqual([row['after'] for row in payments], [1.5, 1.5])
        self.assertEqual(
            [row['inputs']['transfer_contract']['payee_account']['balance_before']
             for row in payments], [5.0, 7.0])
        self.assertEqual(
            [row['inputs']['transfer_contract']['payee_account']['balance_after']
             for row in payments], [6.5, 8.5])
        self.assertTrue(all(row['cause_event_ids'] == [treasury['event_id']]
                            for row in payments))
        self.assertTrue(all(row['inputs']['transfer_contract']['counterparty_leg_status']
                            == 'exact_recipient_wallet_and_linked_aggregate_payer_balance'
                            for row in payments))

    def test_parental_leave_and_starvation_welfare_have_linked_receipts(self):
        parental_fixtures = [_fixture(cash=10.0, traced=False),
                             _fixture(cash=10.0, traced=True)]
        parental_states = []
        for government, region, _trace in parental_fixtures:
            parents = [Agent(0), Agent(0)]
            parents[0].cash, parents[1].cash = 15.0, 2.0
            for parent in parents:
                parent._parental_leave_turns_remaining = 1
            government.parental_leave_enabled = True
            government.parental_leave_amount_per_turn = 6.0
            paid = government.process_parental_leave(1, parents, region)
            parental_states.append((government.agent.cash,
                                    [parent.cash for parent in parents], paid))
        self.assertEqual(parental_states[0], parental_states[1])
        self.assertEqual(parental_states[1], (0.0, [21.0, 6.0], 10.0))

        trace = parental_fixtures[1][2]
        leave_payments = _payments(trace, 'parental_leave')
        self.assertEqual([row['after'] for row in leave_payments], [6.0, 4.0])
        self.assertEqual(
            [row['inputs']['transfer_contract']['payee_account']['balance_before']
             for row in leave_payments], [15.0, 2.0])
        self.assertEqual(
            [row['inputs']['transfer_contract']['payee_account']['balance_after']
             for row in leave_payments], [21.0, 6.0])

        welfare_fixtures = [_fixture(cash=40.0, traced=False),
                            _fixture(cash=40.0, traced=True)]
        welfare_states = []
        for government, region, _trace in welfare_fixtures:
            starving = [Agent(0), Agent(0)]
            starving[0].cash, starving[1].cash = 1.0, 3.0
            for person in starving:
                person.hungry_steps = 1
            welfare_paid = government.distribute_welfare(
                1, starving, min_reserve=0, region=region)
            welfare_states.append((government.agent.cash,
                                   [person.cash for person in starving],
                                   welfare_paid))
        self.assertEqual(welfare_states[0], welfare_states[1])
        self.assertEqual(welfare_states[1], (0.0, [21.0, 23.0], 40.0))

        welfare_payments = _payments(welfare_fixtures[1][2], 'welfare_payment')
        self.assertEqual([row['after'] for row in welfare_payments], [20.0, 20.0])
        self.assertEqual(
            [row['inputs']['transfer_contract']['payee_account']['balance_before']
             for row in welfare_payments], [1.0, 3.0])
        self.assertEqual(
            [row['inputs']['transfer_contract']['payee_account']['balance_after']
             for row in welfare_payments], [21.0, 23.0])
        self.assertTrue(all(row['cause_event_ids'] for row in
                            [*leave_payments, *welfare_payments]))


if __name__ == '__main__':
    unittest.main()
