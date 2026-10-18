import json
import unittest
from types import SimpleNamespace

from agent import Agent
from buildings import BUILDING_RECIPES, Building
from goods import Goods
from land_tenure import LandPlot, TenureStatus
from labor_cases import process_default_cases, process_vagrancy_cases
from livelihood_access import assess_obligation, grant_access
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


def _person(agent_id, *, cash=0.0, social_class='independent'):
    person = Agent(0)
    person.id = agent_id
    person.alive = True
    person.cash = cash
    person.social_class = social_class
    person.output = Goods.none
    return person


def _foreclosure_fixture(*, traced=True, funded=True):
    region = Region('Parish', t=0, number_of_agents=0)
    region.home_currency = 'GBP'
    debtor = _person(11, social_class='tenant')
    creditor = _person(12, cash=4.0, social_class='landlord')
    officer = _person(13, social_class='constable')
    officer.is_police = True
    region.agents.extend([debtor, creditor, officer])
    region.tenure.plots.clear()
    plot = LandPlot('claim-plot', region.name, creditor.id, 0.5,
                    TenureStatus.FEUDAL, tenant_ids=[debtor.id])
    region.tenure.add_plot(plot)
    debtor.assigned_plot_id = plot.plot_id
    grant_access(region, debtor.id, plot.plot_id, 'commons_food')
    region.gov.agent.cash = 5.0 if funded else 0.0
    region.police_employed = 1
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 0, 'phase': 'labor_enforcement', 'next': 1}
    claim = assess_obligation(region, debtor.id, creditor.id, 'rent', 5, 0,
                              collateral_plot_id=plot.plot_id)
    process_default_cases(region, 0)
    return region, debtor, creditor, officer, plot, claim, trace


def _vagrancy_fixture(*, traced=True, funded=True, law_active=True):
    region = Region('Poor Parish', t=0, number_of_agents=0)
    region.home_currency = 'GBP'
    region.buildings.append(Building(
        name='workhouse', recipe=BUILDING_RECIPES['workhouse'],
        built_turn=0, region_name=region.name))
    region.vagrancy_law_active = law_active
    region.gov.agent.cash = 5.0 if funded else 0.0
    region.police_employed = 1
    pauper = _person(21, cash=0.0, social_class='dispossessed')
    officer = _person(22, cash=0.0, social_class='constable')
    officer.is_police = True
    region.agents.extend([pauper, officer])
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 2, 'phase': 'labor_enforcement', 'next': 1}
    return region, pauper, officer, trace


def _foreclosure_state(fixture):
    region, debtor, _creditor, officer, plot, claim, _trace = fixture
    return (region.gov.agent.cash, debtor.cash, officer.cash,
            tuple(plot.tenant_ids), debtor.assigned_plot_id,
            debtor.social_class, claim.balance,
            tuple((case.state, case.outcome, case.officer_cost)
                  for case in region.enforcement_cases))


class LaborEnforcementTraceTests(unittest.TestCase):
    def test_foreclosure_payment_reconciles_and_causes_eviction(self):
        traced = _foreclosure_fixture()
        plain = _foreclosure_fixture(traced=False)

        traced[0]._collective_trace_clock['turn'] = 1
        self.assertEqual(process_default_cases(traced[0], 1), [1])
        self.assertEqual(process_default_cases(plain[0], 1), [1])
        self.assertEqual(_foreclosure_state(traced), _foreclosure_state(plain))
        self.assertEqual((traced[0].gov.agent.cash, traced[3].cash), (4.0, 1.0))

        transfer = next(row for row in traced[6].rows
                        if row.get('kind') == 'labor_enforcement_officer_payment')
        contract = transfer['inputs']['transfer_contract']
        self.assertEqual(contract['operation_type'], 'labor_enforcement_service')
        self.assertEqual(contract['amount'], 1.0)
        self.assertEqual(contract['payer_account']['balance_before'], 5.0)
        self.assertEqual(contract['payer_account']['balance_after'], 4.0)
        self.assertEqual(contract['payee_account']['balance_before'], 0.0)
        self.assertEqual(contract['payee_account']['balance_after'], 1.0)
        outcome = next(row for row in traced[6].rows
                       if row.get('kind') == 'labor_enforcement_case'
                       and row['inputs']['reason'] == 'foreclosure_eviction')
        self.assertEqual(outcome['inputs']['reason'], 'foreclosure_eviction')
        self.assertEqual(outcome['cause_event_ids'], [transfer['event_id']])
        self.assertEqual(outcome['inputs']['tenant_removed'], True)
        self.assertEqual(outcome['inputs']['debtor_social_class_after'], 'dispossessed')
        self.assertNotEqual(outcome['inputs']['access_shares_before'],
                            outcome['inputs']['access_shares_after'])

    def test_unfunded_foreclosure_is_explained_without_cash_change(self):
        fixture = _foreclosure_fixture(funded=False)

        self.assertEqual(process_default_cases(fixture[0], 1), [])

        case = fixture[0].enforcement_cases[0]
        self.assertEqual(case.state, 'pending')
        self.assertEqual(fixture[0].gov.agent.cash, 0.0)
        self.assertEqual(fixture[3].cash, 0.0)
        self.assertFalse(any(row.get('kind') == 'labor_enforcement_officer_payment'
                             for row in fixture[6].rows))
        outcome = next(row for row in fixture[6].rows
                       if row.get('kind') == 'labor_enforcement_case'
                       and row['inputs']['reason'] == 'treasury_cannot_fund_constable')
        self.assertEqual(outcome['inputs']['reason'], 'treasury_cannot_fund_constable')
        self.assertEqual(outcome['inputs']['treasury_cash'], 0.0)

    def test_vagrancy_payment_links_to_confinement_and_status_change(self):
        traced = _vagrancy_fixture()
        plain = _vagrancy_fixture(traced=False)

        self.assertEqual(process_vagrancy_cases(traced[0], 2), [1])
        self.assertEqual(process_vagrancy_cases(plain[0], 2), [1])
        self.assertEqual((traced[0].gov.agent.cash, traced[1].cash,
                          traced[2].cash, traced[1].in_workhouse,
                          traced[1].social_class),
                         (plain[0].gov.agent.cash, plain[1].cash,
                          plain[2].cash, plain[1].in_workhouse,
                          plain[1].social_class))
        self.assertTrue(traced[1].in_workhouse)
        transfer = next(row for row in traced[3].rows
                        if row.get('kind') == 'labor_enforcement_officer_payment')
        outcome = next(row for row in traced[3].rows
                       if row.get('kind') == 'labor_enforcement_case'
                       and row['inputs']['reason'] == 'vagrancy_confinement')
        status = next(row for row in traced[3].rows
                      if row.get('kind') == 'labor_status_change')
        self.assertEqual(outcome['inputs']['reason'], 'vagrancy_confinement')
        gate_id = next(row['event_id'] for row in traced[3].rows
                       if row.get('kind') == 'labor_vagrancy_enforcement_gate')
        opened = next(row for row in traced[3].rows
                      if row.get('kind') == 'labor_enforcement_case'
                      and row['inputs']['reason'] == 'vagrancy_eligibility_met')
        self.assertEqual(opened['inputs']['candidate_reasons'], ['dispossessed',
                                                                  'plotless_cash_below_5'])
        self.assertEqual(outcome['cause_event_ids'], [gate_id,
                                                      opened['event_id'],
                                                      transfer['event_id']])
        self.assertEqual(status['after'], 'workhouse')
        self.assertEqual(status['cause_event_ids'], outcome['cause_event_ids'])
        self.assertEqual(transfer['inputs']['officer_id'], 22)

    def test_vagrancy_law_gate_and_unfunded_case_have_stable_reasons(self):
        disabled = _vagrancy_fixture(law_active=False)
        self.assertEqual(process_vagrancy_cases(disabled[0], 2), [])
        gate = next(row for row in disabled[3].rows
                    if row.get('kind') == 'labor_vagrancy_enforcement_gate')
        self.assertEqual(gate['inputs']['law_active'], False)
        self.assertEqual(gate['after'], 'vagrancy_law_inactive')
        self.assertFalse(disabled[1].in_workhouse)

        unfunded = _vagrancy_fixture(funded=False)
        self.assertEqual(process_vagrancy_cases(unfunded[0], 2), [])
        case = unfunded[0].enforcement_cases[0]
        self.assertEqual(case.state, 'pending')
        outcome = next(row for row in unfunded[3].rows
                       if row.get('kind') == 'labor_enforcement_case'
                       and row['inputs']['reason'] == 'treasury_cannot_fund_constable')
        gate_id = next(row['event_id'] for row in unfunded[3].rows
                       if row.get('kind') == 'labor_vagrancy_enforcement_gate')
        opened = next(row for row in unfunded[3].rows
                      if row.get('kind') == 'labor_enforcement_case'
                      and row['inputs']['reason'] == 'vagrancy_eligibility_met')
        self.assertEqual(outcome['cause_event_ids'], [gate_id, opened['event_id']])


if __name__ == '__main__':
    unittest.main()
