import json
import pickle
import unittest

from labor_frontier_labor import _advance_restriction, _right_rows
from scenario_labor_frontier_rivalry import create_world


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _prepared_world(*, treasury_cash=1.0, deposits=5.0, eligible_officer=True):
    world = create_world(seed=612)
    border = world['by_name']['Meridian Fields']
    rights = _right_rows(border)
    snapshot = [
        {'person_id': person_id, 'plot_id': right.plot_id,
         'legal': right.legal_share, 'usable': right.usable_share}
        for person_id, right in rights]
    for _person_id, right in rights:
        right.legal_share = 0.0
    record = {
        'nation': 'Meridian', 'region': border.name, 'plot_id': 'commons',
        'petition_id': 1, 'sponsor_id': -1, 'requested_turn': 0,
        'deadline_turn': 2, 'status': 'approved', 'effective_turn': 1,
        'fee': 5.0, 'rights_snapshot': snapshot, 'officer_id': None,
    }
    world['scenario_state']['restrictions']['Meridian'] = record

    government = border.gov.agent
    government.cash = float(treasury_cash)
    bank = border.bank
    prior_deposit = float(bank.deposits[government])
    bank.deposits[government] = float(deposits)
    bank.total_deposits += float(deposits) - prior_deposit
    if not eligible_officer:
        for person in border.agents:
            if (person.alive and not person.is_trader
                    and not person.is_corporation and not person.is_government
                    and not getattr(person, 'is_lord', False)):
                person.employer = object()
    return world


def _traced_clone(world):
    clone = pickle.loads(pickle.dumps(world))
    trace = MemoryTrace()
    clock = {'turn': 1, 'phase': 'scenario_labor', 'next': 1}
    for region in clone['tiles']:
        region._run_trace = trace
        region._collective_trace_clock = clock
    return clone, trace


def _state(world):
    border = world['by_name']['Meridian Fields']
    treasury = border.gov.agent
    record = world['scenario_state']['restrictions']['Meridian']
    officer = next((person for person in border.agents
                    if person.id == record.get('officer_id')), None)
    rights = tuple(sorted(
        (person_id, right.plot_id, right.legal_share, right.usable_share)
        for person_id, rows in border.access_rights.items()
        for right in rows if right.resource == 'commons_food'))
    return (record['status'], record.get('last_patrol_paid_turn'),
            record.get('officer_id'), treasury.cash,
            border.bank.deposits[treasury], border.bank.total_deposits,
            officer.cash if officer is not None else None,
            officer.social_class if officer is not None else None,
            border.police_employed, rights)


class CommonsPatrolTraceTests(unittest.TestCase):
    def test_bank_funded_patrol_pairs_with_constable_pay_and_closes_access(self):
        baseline = _prepared_world(treasury_cash=1.0, deposits=5.0)
        initial_access = sum(row['usable'] for row in
                             baseline['scenario_state']['restrictions']
                             ['Meridian']['rights_snapshot'])
        plain = pickle.loads(pickle.dumps(baseline))
        traced, trace = _traced_clone(baseline)

        _advance_restriction(plain, 'Meridian', 1)
        _advance_restriction(traced, 'Meridian', 1)

        self.assertEqual(_state(traced), _state(plain))
        state = _state(traced)
        self.assertEqual(state[0], 'active')
        self.assertEqual(state[1], 1)
        self.assertEqual(state[3:6], (0.0, 3.0, 3.0))
        withdrawal = next(row for row in trace.rows
                          if row.get('kind') == 'bank_withdrawal_posted')
        self.assertEqual(withdrawal['inputs']['requested_amount'], 2.0)
        self.assertEqual(withdrawal['inputs']['settled_amount'], 2.0)

        gate = next(row for row in trace.rows
                    if row.get('kind') == 'commons_patrol_funding_decision')
        self.assertEqual(gate['inputs']['reason'], 'funded_constable_available')
        self.assertEqual(gate['inputs']['bank_withdrawal_settled'], 2.0)
        self.assertIn(withdrawal['event_id'], gate['cause_event_ids'])
        payment = next(row for row in trace.rows
                       if row.get('kind') == 'commons_patrol_cash_payment')
        contract = payment['inputs']['transfer_contract']
        self.assertEqual(contract['amount'], 3.0)
        self.assertEqual(contract['payer_account']['balance_before'], 3.0)
        self.assertEqual(contract['payer_account']['balance_after'], 0.0)
        self.assertEqual(contract['payee_account']['balance_after']
                         - contract['payee_account']['balance_before'], 3.0)
        treasury_flow = next(row for row in trace.rows
                             if row.get('kind') == 'commons_patrol_payroll')
        self.assertEqual(treasury_flow['after'], -3.0)
        self.assertEqual(treasury_flow['inputs']['treasury_cash_before'], 3.0)
        self.assertEqual(treasury_flow['inputs']['treasury_cash_after'], 0.0)
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'commons_patrol_outcome')
        self.assertEqual(outcome['inputs']['reason'], 'patrol_funded_and_enforced')
        self.assertEqual(outcome['inputs']['usable_access_before'], initial_access)
        self.assertEqual(outcome['inputs']['usable_access_after'], 0.0)
        self.assertIn(payment['event_id'], outcome['cause_event_ids'])
        status = next(row for row in trace.rows
                      if row.get('kind') == 'labor_status_change'
                      and row.get('after') == 'constable')
        self.assertEqual(status['cause_event_ids'], [gate['event_id']])

    def test_partial_bank_balance_suspends_patrol_and_records_access(self):
        baseline = _prepared_world(treasury_cash=1.0, deposits=0.5)
        initial_access = sum(row['usable'] for row in
                             baseline['scenario_state']['restrictions']
                             ['Meridian']['rights_snapshot'])
        plain = pickle.loads(pickle.dumps(baseline))
        traced, trace = _traced_clone(baseline)

        _advance_restriction(plain, 'Meridian', 1)
        _advance_restriction(traced, 'Meridian', 1)

        self.assertEqual(_state(traced), _state(plain))
        self.assertEqual(_state(traced)[0], 'suspended')
        self.assertEqual(_state(traced)[3:6], (1.5, 0.0, 0.0))
        self.assertEqual(_state(traced)[8], 0)
        withdrawal = next(row for row in trace.rows
                          if row.get('kind') == 'bank_withdrawal_posted')
        self.assertEqual(withdrawal['inputs']['settled_amount'], 0.5)
        self.assertFalse(any(row.get('kind') == 'commons_patrol_cash_payment'
                             for row in trace.rows))
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'commons_patrol_outcome')
        self.assertEqual(outcome['inputs']['reason'],
                         'treasury_cash_below_patrol_cost')
        self.assertEqual(outcome['inputs']['patrol_paid'], False)
        self.assertEqual(outcome['inputs']['usable_access_before'], initial_access)
        self.assertEqual(outcome['inputs']['usable_access_after'], initial_access)
        self.assertIn(withdrawal['event_id'], outcome['cause_event_ids'])

    def test_missing_constable_suspends_even_with_funded_treasury(self):
        world = _prepared_world(treasury_cash=5.0, deposits=0.0,
                                eligible_officer=False)
        traced, trace = _traced_clone(world)

        _advance_restriction(traced, 'Meridian', 1)

        gate = next(row for row in trace.rows
                    if row.get('kind') == 'commons_patrol_funding_decision')
        self.assertEqual(gate['inputs']['reason'], 'no_eligible_constable')
        self.assertEqual(gate['inputs']['treasury_cash_after_funding'], 5.0)
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'commons_patrol_outcome')
        self.assertEqual(outcome['after'], 'suspended')
        self.assertFalse(outcome['inputs']['patrol_paid'])
        self.assertFalse(any(row.get('kind') == 'commons_patrol_cash_payment'
                             for row in trace.rows))


if __name__ == '__main__':
    unittest.main()
