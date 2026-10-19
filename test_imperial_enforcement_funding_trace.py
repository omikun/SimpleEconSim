"""Trace setup and recurring costs for hired imperial enforcement agents."""

import json
import random
import unittest

from agent import Agent
from macro.imperialism.manager import ImperialismManager
from nation import Nation
from random_cache import rand
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'imperial-funding-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, recipient=True):
    creditor = Nation('Empire', initial_cash=100.0, register=False)
    debtor = Nation('Protectorate', initial_cash=50.0, register=False)
    creditor.currency = 'GBP'
    creditor.government.currency = 'GBP'
    debtor.currency = 'EGP'
    debtor.government.currency = 'EGP'
    creditor_tile = Region('London', 0, 0)
    debtor_tile = Region('Port', 1, 0)
    creditor.add_tile(creditor_tile)
    debtor.add_tile(debtor_tile)
    creditor_tile.home_currency = 'GBP'
    debtor_tile.home_currency = 'EGP'
    creditor_tile.agents = []
    debtor_tile.agents = []
    bailiff = None
    if recipient:
        bailiff = Agent(1)
        bailiff.id = 921
        bailiff.alive = True
        bailiff.cash = 10.0
        bailiff.region = creditor_tile.name
        bailiff.home_currency = 'GBP'
        creditor_tile.agents.append(bailiff)

    trace = MemoryTrace()
    if traced:
        for tile in (creditor_tile, debtor_tile):
            tile._run_trace = trace
            tile._collective_trace_clock = {
                'turn': 1, 'phase': 'imperialism', 'next': 1}
    manager = ImperialismManager()
    world = {'turn': 1, 'nations': [creditor, debtor],
             'tiles': [creditor_tile, debtor_tile]}
    return manager, creditor, debtor, creditor_tile, debtor_tile, bailiff, world, trace


class ImperialEnforcementFundingTraceTests(unittest.TestCase):
    def test_establishment_fee_and_recurring_retainer_link_exact_wallets(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        random_state_before = random.getstate()
        random_cache_index_before = rand._idx
        results = []
        rng_states_after = []
        for fixture in (plain, traced):
            manager, creditor, debtor, creditor_tile, debtor_tile, _bailiff, world, _trace = fixture
            random.seed(8871)
            rand._idx = 0
            results.append(manager.establish_receivership(
                creditor, debtor, 400.0, t=1, world=world))
            for tile in (creditor_tile, debtor_tile):
                clock = getattr(tile, '_collective_trace_clock', None)
                if clock is not None:
                    clock['turn'] = 2
                    clock['phase'] = 'imperialism'
            manager.step_imperialism(world, t=2)
            rng_states_after.append((random.getstate(), rand._idx))
        random.setstate(random_state_before)
        rand._idx = random_cache_index_before

        self.assertTrue(results[0][0])
        self.assertTrue(results[1][0])
        self.assertEqual(rng_states_after[0], rng_states_after[1])

        self.assertEqual(plain[1].government.agent.cash,
                         traced[1].government.agent.cash)
        self.assertEqual(plain[5].cash, traced[5].cash)
        rec = traced[0].receiverships[0]
        self.assertEqual(plain[1].government.agent.cash,
                         traced[1].government.agent.cash)
        self.assertEqual(plain[5].cash, traced[5].cash)
        self.assertEqual(plain[0].receiverships[0].status, rec.status)
        self.assertEqual(plain[0].receiverships[0].enforcement_mode,
                         rec.enforcement_mode)
        self.assertEqual(plain[0].receiverships[0].remaining_debt,
                         rec.remaining_debt)
        self.assertEqual(traced[1].government.agent.cash, 48.0)
        self.assertEqual(traced[5].cash, 62.0)

        rows = traced[7].rows
        payments = [row for row in rows
                    if row.get('metric_id') == 'finance.cash_transfer'
                    and row.get('kind') == 'imperial_enforcement_agent_payment']
        self.assertEqual(len(payments), 2)
        by_reason = {row['inputs']['reason']: row for row in payments}
        contract = by_reason['receivership_agent_contract']['inputs']['transfer_contract']
        self.assertEqual(contract['amount'], 50.0)
        self.assertEqual(contract['payer_account']['balance_before'], 100.0)
        self.assertEqual(contract['payer_account']['balance_after'], 50.0)
        self.assertEqual(contract['payee_account']['balance_before'], 10.0)
        self.assertEqual(contract['payee_account']['balance_after'], 60.0)
        self.assertEqual(contract['unconverted_currency_mismatch'], False)
        retainer = by_reason['receivership_agent_retainer']['inputs']['transfer_contract']
        self.assertEqual(retainer['amount'], 2.0)
        self.assertEqual(retainer['payer_account']['balance_before'], 50.0)
        self.assertEqual(retainer['payer_account']['balance_after'], 48.0)
        self.assertEqual(retainer['payee_account']['balance_before'], 60.0)
        self.assertEqual(retainer['payee_account']['balance_after'], 62.0)
        for payment in payments:
            self.assertEqual(len(payment['cause_event_ids']), 1)
            gate = next(row for row in rows
                        if row['event_id'] == payment['cause_event_ids'][0])
            self.assertEqual(gate['metric_id'], 'finance.enforcement_agent_funding')
            self.assertEqual(gate['inputs']['operation_id'],
                             payment['inputs']['operation_id'])

    def test_missing_payee_is_recorded_as_expense_not_a_fake_transfer(self):
        fixture = _fixture(traced=True, recipient=False)
        manager, creditor, debtor, _ct, _dt, _bailiff, world, trace = fixture
        before = creditor.government.agent.cash
        ok, _message, rec = manager.establish_receivership(
            creditor, debtor, 400.0, t=1, world=world)
        self.assertTrue(ok)
        self.assertEqual(creditor.government.agent.cash, before - 50.0)
        self.assertEqual(rec.enforcement_mode, 'hired_agents')

        rows = trace.rows
        expense = next(row for row in rows
                       if row.get('metric_id') == 'finance.policy_expenditure')
        self.assertEqual(expense['inputs']['recipient_found'], False)
        contract = expense['inputs']['transfer_contract']
        self.assertEqual(contract['amount'], 50.0)
        self.assertEqual(contract['payer_account']['balance_before'], before)
        self.assertEqual(contract['payer_account']['balance_after'], before - 50.0)
        self.assertEqual(contract['payee_account']['balance_status'],
                         'no_eligible_agent_wallet_found')
        self.assertFalse(any(row.get('metric_id') == 'finance.cash_transfer'
                             for row in rows))

    def test_unaffordable_retainer_suspension_links_to_funding_gate(self):
        fixture = _fixture(traced=True)
        manager, creditor, debtor, creditor_tile, debtor_tile, _bailiff, world, trace = fixture
        ok, _message, rec = manager.establish_receivership(
            creditor, debtor, 400.0, t=1, world=world)
        self.assertTrue(ok)
        creditor.government.agent.cash = 0.5
        creditor_tile._collective_trace_clock['turn'] = 2
        debtor_tile._collective_trace_clock['turn'] = 2
        manager.step_imperialism(world, t=2)
        self.assertEqual(rec.status, 'suspended')

        rows = trace.rows
        gate = next(row for row in rows
                    if row.get('metric_id') == 'finance.enforcement_agent_funding'
                    and row['inputs'].get('turn') == 2)
        self.assertFalse(gate['after'])
        self.assertEqual(gate['inputs']['amount_required'], 2.0)
        self.assertEqual(gate['inputs']['cash_shortfall'], 1.5)
        state = next(row for row in rows
                     if row.get('metric_id') == 'imperialism.receivership_state'
                     and row['inputs'].get('turn') == 2)
        self.assertEqual(state['before'], 'active')
        self.assertEqual(state['after'], 'suspended')
        self.assertEqual(state['cause_event_ids'], [gate['event_id']])
        self.assertFalse(any(row.get('kind') == 'imperial_enforcement_agent_payment'
                             and row['inputs'].get('turn') == 2 for row in rows))


if __name__ == '__main__':
    unittest.main()
