import copy
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from run_trace import RunTrace, verify
from scenario_political_economy import apply_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _actor(agent_id, cash, *, employer=None, wage=0.0, striking=False):
    return SimpleNamespace(
        id=agent_id, alive=True, cash=float(cash), wage=float(wage),
        is_government=False, is_corporation=employer == 'corporation',
        is_lord=employer == 'lord', is_trader=False,
        is_striking=bool(striking), company_name=f'Firm {agent_id}')


def _fixture(*, with_trace=True, petitioners=4, employer_cash=(100.0, 50.0),
             striking=True):
    employers = [
        _actor(201, employer_cash[0], employer='corporation', wage=2.0),
        _actor(202, employer_cash[1], employer='lord', wage=10.0),
    ]
    workers = [_actor(101, 1.0, striking=striking),
               _actor(102, 3.0, striking=striking)]
    collective = {
        'petitioners': petitioners, 'strikers': 2 if striking else 0,
        'mutual_aid_meals': 0, 'injuries': 0, 'support': 0.0,
        'settlement_until_turn': 0,
    }
    nation = SimpleNamespace(
        name='Egypt', currency='EGP', legitimacy=0.6,
        government=SimpleNamespace(agent=SimpleNamespace(cash=100.0)))
    tile = SimpleNamespace(
        name='Delta', scenario_location='Nile Delta', home_currency='EGP',
        agents=employers + workers, unrest_level=0.5, owner_nation=nation)
    nation.tiles = [tile]
    trace = MemoryTrace()
    if with_trace:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 4, 'phase': 'scenario_action', 'next': 1}
    econ = {
        'collective_by_tile': {tile.name: collective},
        'scenario_strikers_by_tile': {tile.name: [101, 102]},
    }
    world = {'turn': 4, 'scenario_state': {'political_economy': econ}}
    return SimpleNamespace(world=world, nation=nation, tile=tile,
                           employers=employers, workers=workers,
                           collective=collective, trace=trace)


def _state(fixture):
    return {
        'employers': [(a.cash, a.wage) for a in fixture.employers],
        'workers': [(a.cash, a.is_striking) for a in fixture.workers],
        'collective': copy.deepcopy(fixture.collective),
        'scenario_strikers': copy.deepcopy(
            fixture.world['scenario_state']['political_economy']
            ['scenario_strikers_by_tile'][fixture.tile.name]),
        'unrest': fixture.tile.unrest_level,
        'legitimacy': fixture.nation.legitimacy,
    }


def _contract(row):
    return row['inputs']['transfer_contract']


class ScenarioBargainTraceTests(unittest.TestCase):
    def test_settlement_links_wages_funding_receipts_and_social_outcomes(self):
        fixture = _fixture()

        success, _ = apply_action(
            fixture.world, fixture.nation, 'district_bargain_workers', fixture.tile)

        self.assertTrue(success)
        self.assertEqual([(a.cash, a.wage) for a in fixture.employers],
                         [(98.0, 2.5), (49.0, 10.5)])
        self.assertEqual([a.cash for a in fixture.workers], [2.5, 4.5])
        self.assertTrue(all(not a.is_striking for a in fixture.workers))
        self.assertEqual(fixture.collective['petitioners'], 2)
        self.assertEqual(fixture.collective['strikers'], 0)
        self.assertEqual(fixture.collective['settlement_until_turn'], 7)
        self.assertEqual(
            fixture.world['scenario_state']['political_economy']
            ['scenario_strikers_by_tile']['Delta'], [])
        self.assertAlmostEqual(fixture.tile.unrest_level, 0.5 * math.exp(-0.12))
        self.assertAlmostEqual(fixture.nation.legitimacy, 0.62)

        wage_rows = [row for row in fixture.trace.rows
                     if row.get('metric_id') == 'labor.firm_wage']
        self.assertEqual(len(wage_rows), 2)
        self.assertEqual([row['after'] - row['before'] for row in wage_rows],
                         [0.5, 0.5])
        payment = next(row for row in fixture.trace.rows
                       if row.get('kind') == 'district_bargain_cash_transfer')
        contract = _contract(payment)
        self.assertEqual(contract['amount'], 3.0)
        payer = contract['payer_account']
        self.assertTrue(payer['virtual_pool'])
        self.assertFalse(payer['balance_captured'])
        self.assertEqual(sum(row['amount'] for row in payer['source_legs']), 3.0)
        self.assertEqual([row['cash_before'] - row['cash_after']
                          for row in payer['source_legs']], [2.0, 1.0])
        payees = contract['payee_account']['members']
        self.assertEqual([row['amount'] for row in payees], [1.5, 1.5])
        self.assertEqual([row['balance_after'] - row['balance_before']
                          for row in payees], [1.5, 1.5])

        labor = next(row for row in fixture.trace.rows
                     if row.get('kind') == 'district_bargain_settled')
        self.assertEqual(set(labor['cause_event_ids']),
                         {row['event_id'] for row in wage_rows} | {payment['event_id']})
        self.assertEqual(labor['inputs']['recipient_basis'], 'active_strikers')
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_bargain_action_resolved')
        self.assertEqual(action['cause_event_ids'], [labor['event_id']])
        self.assertEqual(action['after'], 1)

    def test_trace_does_not_change_bargaining_outcome(self):
        plain = _fixture(with_trace=False)
        traced = _fixture(with_trace=True)

        self.assertEqual(
            apply_action(traced.world, traced.nation,
                         'district_bargain_workers', traced.tile)[0],
            apply_action(plain.world, plain.nation,
                         'district_bargain_workers', plain.tile)[0])
        self.assertEqual(_state(traced), _state(plain))

    def test_unfunded_settlement_is_explicit_and_does_not_fake_a_transfer(self):
        fixture = _fixture(employer_cash=(0.0, -4.0))

        success, _ = apply_action(
            fixture.world, fixture.nation, 'district_bargain_workers', fixture.tile)

        self.assertTrue(success)
        self.assertFalse(any(row.get('kind') == 'district_bargain_cash_transfer'
                             for row in fixture.trace.rows))
        labor = next(row for row in fixture.trace.rows
                     if row.get('kind') == 'district_bargain_settled')
        self.assertEqual(labor['inputs']['cash_transfer_status'],
                         'zero_employer_contribution')
        self.assertEqual(labor['inputs']['cash_pool_total'], 0.0)
        self.assertEqual([row['amount'] for row in
                          labor['inputs']['employer_contributions']], [0.0, 0.0])
        self.assertEqual([row.cash for row in fixture.workers], [1.0, 3.0])

    def test_positive_employer_debit_without_households_shows_missing_receipt(self):
        fixture = _fixture()
        fixture.tile.agents = fixture.employers

        success, _ = apply_action(
            fixture.world, fixture.nation, 'district_bargain_workers', fixture.tile)

        self.assertTrue(success)
        payment = next(row for row in fixture.trace.rows
                       if row.get('kind') == 'district_bargain_cash_debit_without_recipient')
        contract = _contract(payment)
        self.assertEqual(contract['amount'], 3.0)
        self.assertEqual(contract['recipient_count'], 0)
        self.assertEqual(contract['payee_account']['balance_scope'], 'missing_payee')
        self.assertEqual(contract['payee_account']['balance_status'],
                         'employer_cash_debited_without_worker_receipt')
        self.assertEqual([a.cash for a in fixture.workers], [1.0, 3.0])
        labor = next(row for row in fixture.trace.rows
                     if row.get('kind') == 'district_bargain_settled')
        self.assertEqual(labor['inputs']['cash_transfer_status'],
                         'employer_debit_without_household_receipt')

    def test_bargaining_gate_rejection_is_explained(self):
        fixture = _fixture(petitioners=0, striking=False)

        success, _ = apply_action(
            fixture.world, fixture.nation, 'district_bargain_workers', fixture.tile)

        self.assertFalse(success)
        labor = next(row for row in fixture.trace.rows
                     if row.get('kind') == 'district_bargain_gate_rejected')
        self.assertEqual(labor['inputs']['reason'],
                         'no_active_petition_or_strike')
        action = next(row for row in fixture.trace.rows
                      if row.get('kind') == 'district_bargain_action_resolved')
        self.assertEqual(action['after'], 0)

    def test_bargaining_without_a_living_employer_records_the_gate(self):
        fixture = _fixture()
        fixture.tile.agents = fixture.workers

        success, _ = apply_action(
            fixture.world, fixture.nation, 'district_bargain_workers', fixture.tile)

        self.assertFalse(success)
        labor = next(row for row in fixture.trace.rows
                     if row.get('kind') == 'district_bargain_gate_rejected')
        self.assertEqual(labor['inputs']['reason'], 'no_living_local_employer')
        self.assertEqual(labor['inputs']['active_striker_ids'], ['101', '102'])
        self.assertEqual([(a.cash, a.wage) for a in fixture.employers],
                         [(100.0, 2.0), (50.0, 10.0)])

    def test_compact_run_trace_serializes_and_verifies_bargain_chain(self):
        fixture = _fixture()
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / 'district-bargain.ctr'
            trace = RunTrace(trace_path, 'district-bargain')
            fixture.tile._run_trace = trace
            fixture.tile._collective_trace_clock = {
                'next': 1, 'turn': 4, 'phase': 'scenario_action'}

            success, _ = apply_action(
                fixture.world, fixture.nation, 'district_bargain_workers', fixture.tile)

            self.assertTrue(success)
            verified = verify(trace_path)
            self.assertGreaterEqual(verified['rows'], 6)
            transfers = trace.query(metric_id='finance.cash_transfer', turn=4)
            self.assertEqual(transfers['total'], 1)
            labor = trace.query(metric_id='labor.collective_action', turn=4)
            self.assertEqual(labor['total'], 1)
            self.assertEqual(labor['events'][0]['cause_event_ids'],
                             [event['event_id'] for event in
                              trace.query(metric_id='labor.firm_wage', turn=4)['events']]
                             + [transfers['events'][0]['event_id']])


if __name__ == '__main__':
    unittest.main()
