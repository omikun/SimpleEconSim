import unittest

from agent import Agent, initialize_agent
from buildings import BUILDING_RECIPES, ConstructionProject
from construction_politics import subsidize_contractor
from goods import Goods
from nation import Nation
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, contractor=True, cash=1000.0, traced=True):
    nation = Nation('Commonwealth', initial_cash=cash)
    tile = Region('Canal District', 0)
    nation.add_tile(tile)
    firm = None
    if contractor:
        firm = Agent(700)
        initialize_agent(firm, Goods.transport, 0, 0, 10.0)
        firm.id = 700
        firm.is_corporation = True
        firm.is_construction_company = True
        firm.home_currency = getattr(tile, 'home_currency', 'local_currency')
        firm.company_name = 'Canal Works'
        tile.agents.append(firm)
    project = ConstructionProject(
        project_id='canal-overrun-1', nation_name=nation.name, region=tile,
        recipe=BUILDING_RECIPES['barge_canal'], contractor=firm,
        started_turn=2)
    project.status = 'stalled'
    tile.construction_projects = [project]
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 5, 'phase': 'policy_action', 'next': 1}
    return nation, tile, firm, project, trace


class ConstructionSubsidyTraceTests(unittest.TestCase):
    def test_subsidy_pairs_treasury_debit_and_contractor_credit(self):
        nation, _tile, firm, project, trace = _fixture()
        treasury_before = nation.government.agent.cash
        contractor_before = firm.cash

        success, _ = subsidize_contractor(project, 100.0, nation,
                                          world={'turn': 5})

        self.assertTrue(success)
        transfer = next(row for row in trace.rows
                        if row.get('kind') == 'construction_overrun_subsidy_payment')
        contract = transfer['inputs']['transfer_contract']
        self.assertEqual(contract['contract_version'], 'cash_transfer.v1')
        self.assertEqual(contract['operation_type'], 'construction_overrun_subsidy')
        self.assertEqual(contract['payer_account']['balance_before']
                         - contract['payer_account']['balance_after'], 100.0)
        self.assertEqual(contract['payee_account']['balance_after']
                         - contract['payee_account']['balance_before'], 100.0)
        self.assertEqual(nation.government.agent.cash, treasury_before - 100.0)
        self.assertEqual(firm.cash, contractor_before + 100.0)

        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'construction_subsidy_resolved')
        self.assertEqual(outcome['inputs']['reason'], 'subsidy_paid')
        self.assertEqual(outcome['inputs']['project_status_before'], 'stalled')
        self.assertEqual(outcome['inputs']['project_status_after'], 'in_progress')
        self.assertEqual(outcome['inputs']['subsidies_received_before'], 0.0)
        self.assertEqual(outcome['inputs']['subsidies_received_after'], 100.0)
        self.assertEqual(outcome['cause_event_ids'], [transfer['event_id']])

    def test_rejected_grant_records_reason_and_balances(self):
        nation, _tile, _firm, project, trace = _fixture(cash=10.0)

        success, _ = subsidize_contractor(project, 100.0, nation,
                                          world={'turn': 5})

        self.assertFalse(success)
        self.assertEqual(nation.government.agent.cash, 10.0)
        self.assertEqual(project.status, 'stalled')
        self.assertFalse(any(row.get('kind') == 'construction_overrun_subsidy_payment'
                             for row in trace.rows))
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'construction_subsidy_resolved')
        self.assertEqual(outcome['inputs']['reason'], 'insufficient_treasury_cash')
        self.assertEqual(outcome['inputs']['treasury_cash_before'], 10.0)
        self.assertEqual(outcome['inputs']['treasury_cash_after'], 10.0)

    def test_missing_contractor_is_recorded(self):
        nation, _tile, _firm, project, trace = _fixture(contractor=False)

        success, _ = subsidize_contractor(project, 100.0, nation,
                                          world={'turn': 5})

        self.assertFalse(success)
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'construction_subsidy_resolved')
        self.assertEqual(outcome['inputs']['reason'], 'project_has_no_contractor')
        self.assertEqual(outcome['after'], 0.0)

    def test_trace_does_not_change_subsidy_state(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        self.assertEqual(subsidize_contractor(plain[3], 100.0, plain[0],
                                              world={'turn': 5})[0],
                         subsidize_contractor(traced[3], 100.0, traced[0],
                                              world={'turn': 5})[0])
        self.assertEqual((plain[0].government.agent.cash, plain[2].cash,
                          plain[3].status, plain[3].emergency_subsidies_received),
                         (traced[0].government.agent.cash, traced[2].cash,
                          traced[3].status, traced[3].emergency_subsidies_received))


if __name__ == '__main__':
    unittest.main()
