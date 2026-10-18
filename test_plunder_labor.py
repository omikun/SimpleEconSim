"""Behavior, conservation, serialization, and integration checks for labor mechanics."""

import unittest
from types import SimpleNamespace

from agent import Agent
from economy.labor_mobility import LaborMobilityScheduler
from goods import Goods
from labor_choice import evaluate_offer, attach_worker
from land_tenure import LandPlot, TenureStatus, TileTenure
from foraging import forage_tile
from livelihood_access import (assess_obligation, due_cash_for, settle_obligations,
                               grant_access, effective_access)
from crop_credit import offer_advance, settle_crop_liens, create_tenancy_agreement, settle_crop_shares
from labor_cases import process_default_cases
from labor_laws import submit_law_petition, decide_labor_laws, repeal_law
from labor_contract import calculate_work_effort, ensure_labor_agreement, quit_job
from region_finance import pay_wages
from labor_audit import audit_labor_institutions


class TestPlunderLaborMechanics(unittest.TestCase):
    def setUp(self):
        self.region = SimpleNamespace(
            name="Test Parish",
            recipes={Goods.food: {'price': 2.0}},
            tenure=TileTenure(),
            agents=[],
            terrain={Goods.food: 1.0},
            wilderness=False,
            elevation=0.0,
        )

    def _worker(self, agent_id=1):
        worker = Agent(agent_id)
        worker.cash = 0.0
        worker.social_class = 'dispossessed'
        self.region.agents.append(worker)
        return worker

    def _firm(self, wage=1.0, max_employees=1):
        firm = Agent(99)
        firm.is_corporation = True
        firm.cash = 100.0
        firm.wage = wage
        firm.max_employees = max_employees
        firm.shift_hours = 8.0
        firm.employees = []
        firm.alive = True
        firm.output = Goods.wood
        self.region.agents.append(firm)
        return firm

    def test_offer_evaluation_is_pure_and_access_changes_reservation(self):
        worker = self._worker()
        firm = self._firm(wage=2.2)
        plot = LandPlot('p1', self.region.name, 8, 0.5, TenureStatus.FEUDAL,
                        tenant_ids=[worker.id])
        self.region.tenure.add_plot(plot)
        worker.assigned_plot_id = plot.plot_id
        before = (worker.employer, list(firm.employees), worker.output)

        secure = evaluate_offer(worker, firm, self.region, 1, tightness=0.5)
        from livelihood_access import remove_access
        remove_access(self.region, worker.id, plot.plot_id)
        worker.assigned_plot_id = None
        landless = evaluate_offer(worker, firm, self.region, 1, tightness=0.5)

        self.assertGreater(secure.reservation_wage, landless.reservation_wage)
        self.assertEqual(before, (worker.employer, list(firm.employees), worker.output))
        self.assertFalse(secure.accepted)
        self.assertTrue(landless.accepted, landless.reason)

    def test_attach_worker_keeps_both_employment_references_aligned(self):
        worker = self._worker()
        firm = self._firm(wage=2.2)
        decision = evaluate_offer(worker, firm, self.region, 4, tightness=0.5)
        self.assertTrue(decision.accepted, decision.reason)
        self.assertTrue(attach_worker(worker, firm, 4, decision))
        self.assertIs(worker.employer, firm)
        self.assertIn(worker, firm.employees)
        self.assertEqual(worker.wage, decision.offered_wage)
        self.assertEqual(worker.labor_agreement.pay_rate, decision.offered_wage)
        self.assertFalse(attach_worker(worker, firm, 3, decision))

    def test_scheduler_rejects_below_reservation_offer_and_is_idempotent(self):
        worker = self._worker()
        firm = self._firm(wage=1.0)
        scheduler = LaborMobilityScheduler()

        result = scheduler.step_labor_cohort(self.region, t=0)
        repeated = scheduler.step_labor_cohort(self.region, t=0)

        self.assertIsNone(worker.employer)
        self.assertEqual(firm.employees, [])
        self.assertEqual(result['reallocations_count'], 0)
        self.assertTrue(repeated['already_processed'])
        self.assertTrue(any(not row['accepted'] and row['reason'] == 'insufficient_wage'
                            for row in self.region.labor_decision_log))

    def test_employed_worker_cannot_also_forage(self):
        worker = self._worker()
        employer = self._firm(wage=2.0)
        worker.employer = employer
        employer.employees.append(worker)
        plot = LandPlot('p1', self.region.name, 8, 1.0, TenureStatus.FEUDAL,
                        tenant_ids=[worker.id])
        self.region.tenure.add_plot(plot)

        gathered = forage_tile(self.region, t=1)

        self.assertEqual(gathered, 0)
        self.assertEqual(worker.inv_get(Goods.food, 0), 0)

    def test_named_rights_and_obligations_change_choice_without_mutation(self):
        worker = self._worker()
        firm = self._firm(wage=2.2)
        lord = Agent(70)
        lord.cash = 0.0
        self.region.agents.append(lord)
        plot = LandPlot('p2', self.region.name, lord.id, 0.5, TenureStatus.FEUDAL,
                        tenant_ids=[worker.id])
        self.region.tenure.add_plot(plot)
        grant_access(self.region, worker.id, plot.plot_id, 'commons_food')
        self.assertGreater(effective_access(worker, self.region), 0)
        secured = evaluate_offer(worker, firm, self.region, 1, tightness=0.5)
        claim = assess_obligation(self.region, worker.id, lord.id, 'rent', 10, 1)
        with_debt = evaluate_offer(worker, firm, self.region, 1, tightness=0.5)
        self.assertEqual(claim.balance, 10)
        self.assertEqual(due_cash_for(worker.id, self.region, 1), 10)
        self.assertGreater(secured.reservation_wage, with_debt.reservation_wage)
        self.assertEqual(worker.cash, 0)
        paid = settle_obligations(self.region, 1)
        self.assertEqual(paid[0]['paid'], 0)
        self.assertEqual(claim.balance, 10)

    def test_leasehold_access_is_half_and_enclosure_only_changes_named_holder(self):
        worker = self._worker()
        other = self._worker(2)
        plot = LandPlot('lease', self.region.name, 8, 0.5, TenureStatus.LEASEHOLD,
                        tenant_ids=[worker.id])
        self.region.tenure.add_plot(plot)
        grant_access(self.region, worker.id, plot.plot_id, 'commons_food')
        self.assertAlmostEqual(effective_access(worker, self.region), 0.25)
        self.assertEqual(effective_access(other, self.region), 0.0)

    def test_advance_transfers_cash_and_lien_uses_only_current_harvest(self):
        lender = Agent(51)
        lender.cash = 20
        self.region.agents.append(lender)
        farmer = self._worker(52)
        farmer.output = Goods.food
        plot = LandPlot('farm', self.region.name, 51, 0.5, TenureStatus.FEUDAL,
                        tenant_ids=[farmer.id])
        self.region.tenure.add_plot(plot)
        cash_before = lender.cash + farmer.cash
        from supply_proposals import propose, decide
        proposal = propose(self.region, 'crop_advance', lender, farmer, turn=0,
                           price=8, due_turn=1, plot_id='farm', good='food',
                           lien_share=0.5)
        decide(self.region, 1)
        claim = next(c for c in self.region.cash_obligations
                     if c.id == proposal['result']['claim_id'])
        self.assertIsNotNone(claim)
        self.assertEqual(lender.cash + farmer.cash, cash_before)
        farmer.inv_add(Goods.food, 4)  # old stores are not a current harvest receipt
        self.region.production_receipts = [{'person_id': farmer.id, 'good': Goods.food, 'quantity': 3}]
        food_before = farmer.inv_get(Goods.food, 0) + lender.inv_get(Goods.food, 0)
        events = settle_crop_liens(self.region, 1)
        self.assertEqual(events[0]['quantity'], 1)
        self.assertEqual(farmer.inv_get(Goods.food, 0) + lender.inv_get(Goods.food, 0), food_before)
        self.assertEqual(claim.balance, 6)

    def test_share_tenancy_keeps_worker_unemployed_and_transfers_real_crop(self):
        tenant = self._worker(61)
        landlord = Agent(62)
        landlord.cash = 5
        self.region.agents.append(landlord)
        plot = LandPlot('share', self.region.name, landlord.id, 0.5, TenureStatus.FEUDAL)
        self.region.tenure.add_plot(plot)
        agreement = create_tenancy_agreement(self.region, tenant, landlord, 'share',
                                             kind='crop_share', crop_share=0.5)
        self.assertEqual(tenant.employer, None)
        self.assertIn(tenant.id, plot.tenant_ids)
        tenant.output = Goods.food
        tenant.inv_add(Goods.food, 4)
        self.region.production_receipts = [{'person_id': tenant.id, 'good': Goods.food, 'quantity': 4}]
        before = tenant.inv_get(Goods.food, 0) + landlord.inv_get(Goods.food, 0)
        result = settle_crop_shares(self.region, 1)
        self.assertEqual(result[0]['quantity'], 2)
        self.assertEqual(tenant.inv_get(Goods.food, 0) + landlord.inv_get(Goods.food, 0), before)
        self.assertTrue(agreement.active)

    def test_foreclosure_case_waits_one_turn_and_requires_enforcement(self):
        debtor = self._worker(71)
        creditor = Agent(72)
        plot = LandPlot('claim', self.region.name, creditor.id, 0.5, TenureStatus.FEUDAL,
                        tenant_ids=[debtor.id])
        self.region.tenure.add_plot(plot)
        grant_access(self.region, debtor.id, plot.plot_id, 'commons_food')
        government = Agent(73)
        government.cash = 5
        officer = Agent(74)
        officer.is_police = True
        officer.social_class = 'constable'
        self.region.gov = SimpleNamespace(agent=government)
        self.region.agents.extend([government, officer])
        claim = assess_obligation(self.region, debtor.id, creditor.id, 'rent', 5, 0,
                                  collateral_plot_id=plot.plot_id)
        process_default_cases(self.region, 0)
        self.assertIn(debtor.id, plot.tenant_ids)
        self.assertEqual(self.region.enforcement_cases[0].earliest_turn, 1)
        self.region.police_employed = 1
        process_default_cases(self.region, 1)
        self.assertNotIn(debtor.id, plot.tenant_ids)
        self.assertEqual(self.region.enforcement_cases[0].claim_id, claim.id)
        self.assertEqual(government.cash, 4)
        self.assertEqual(officer.cash, 1)

    def test_petition_does_not_enact_law_and_repeal_restores_claim(self):
        sponsor = self._worker(91)
        sponsor.cash = 20
        government = Agent(92)
        government.cash = 0
        self.region.gov = SimpleNamespace(agent=government)
        plot = LandPlot('legal', self.region.name, 92, 0.5, TenureStatus.FEUDAL,
                        tenant_ids=[sponsor.id])
        self.region.tenure.add_plot(plot)
        grant_access(self.region, sponsor.id, plot.plot_id, 'commons_food')
        proposal = submit_law_petition(sponsor, self.region, 'gathering_restriction', 5, 0)
        self.assertIsNotNone(proposal)
        self.assertEqual(effective_access(sponsor, self.region), 0.5)
        self.assertFalse(decide_labor_laws(self.region, 0))
        self.assertEqual(effective_access(sponsor, self.region, official=True), 0.5)
        decide_labor_laws(self.region, 1)
        self.assertEqual(effective_access(sponsor, self.region, official=True), 0.0)
        self.assertEqual(effective_access(sponsor, self.region), 0.5)
        self.assertTrue(repeal_law(self.region, 'gathering_restriction'))
        self.assertEqual(effective_access(sponsor, self.region, official=True), 0.5)

    def test_effort_has_diminishing_hours_and_extreme_pace_fatigue(self):
        base = calculate_work_effort(8, 1.0, 1.0, 0.0)
        twelve = calculate_work_effort(12, 1.0, 1.0, 0.0)
        extreme = calculate_work_effort(12, 2.0, 1.0, 2.0)
        self.assertGreater(twelve, base)
        self.assertLess(twelve / base, 12 / 8)
        self.assertLess(calculate_work_effort(12, 1.75, 1.0, 2.0), twelve)

    def test_unpaid_cash_wage_is_recorded_as_liability(self):
        worker = self._worker(101)
        firm = self._firm(wage=2.0)
        firm.cash = 0.0
        worker.employer = firm
        firm.employees.append(worker)
        ensure_labor_agreement(worker, firm, 0)
        self.region.owner_nation = SimpleNamespace(truck_act_enacted=True)
        before = worker.cash
        pay_wages(self.region, 1)
        self.assertEqual(worker.cash, before)
        self.assertEqual(firm.wage_liabilities[0]['amount'], 2.0)
        self.assertEqual(worker.wage_withheld, 2.0)

    def test_wage_arrear_records_paired_non_cash_claim_and_cause(self):
        from economy.actor_accounts import begin_turn, seal_turn

        class Recorder:
            def __init__(self):
                self.rows = []

            def emit(self, clock, **row):
                self.rows.append({'turn': clock['turn'], **row})

        worker = self._worker(102)
        firm = self._firm(wage=2.0)
        firm.cash = 0.5
        worker.employer = firm
        firm.employees.append(worker)
        ensure_labor_agreement(worker, firm, 0)
        self.region.owner_nation = SimpleNamespace(truck_act_enacted=True)
        self.region.home_currency = 'USD'
        self.region._collective_trace_clock = {'turn': 1, 'next': 1, 'phase': 'finance'}
        self.region._run_trace = Recorder()
        begin_turn(self.region, 1)

        pay_wages(self.region, 1)
        accounts = {row['actor_id']: row for row in seal_turn(self.region, 1)}
        event = next(event for event in self.region.economic_events
                     if event['kind'] == 'wage_arrears_accrued')
        trace = next(row for row in self.region._run_trace.rows
                     if row['kind'] == 'wage_arrears_accrued')

        self.assertEqual(event['payer_id'], firm.id)
        self.assertEqual(event['recipient_id'], worker.id)
        self.assertEqual(event['amount'], 1.5)
        self.assertEqual(event['currency'], 'USD')
        self.assertEqual(event['detail']['reason'], 'employer_cash_below_nominal_wage')
        self.assertEqual(accounts[firm.id]['closing_wage_arrears_payable'], 1.5)
        self.assertEqual(accounts[firm.id]['wage_arrears_accrued'], 1.5)
        self.assertEqual(accounts[worker.id]['closing_wage_arrears_claim'], 1.5)
        self.assertEqual(accounts[worker.id]['wage_arrears_claim_accrued'], 1.5)
        self.assertEqual(accounts[firm.id]['posted_cash_change'], -0.5)
        self.assertEqual(accounts[worker.id]['posted_cash_change'], 0.5)
        self.assertEqual(trace['metric_id'], 'finance.wage_arrears')
        self.assertEqual(trace['before'], 0.0)
        self.assertEqual(trace['after'], 1.5)
        self.assertEqual(trace['inputs']['employer_cash_before'], 0.5)
        self.assertEqual(trace['inputs']['cash_paid'], 0.5)

    def test_wage_arrears_balance_survives_recent_detail_limit(self):
        from economy.actor_accounts import begin_turn, seal_turn

        worker = self._worker(103)
        firm = self._firm(wage=2.0)
        firm.cash = 0.0
        worker.employer = firm
        firm.employees.append(worker)
        ensure_labor_agreement(worker, firm, 0)
        self.region.owner_nation = SimpleNamespace(truck_act_enacted=True)

        for turn in range(1, 502):
            pay_wages(self.region, turn)
        self.assertEqual(len(firm.wage_liabilities), 500)

        begin_turn(self.region, 502)
        pay_wages(self.region, 502)
        accounts = {row['actor_id']: row for row in seal_turn(self.region, 502)}

        self.assertEqual(accounts[firm.id]['opening_wage_arrears_payable'], 1002.0)
        self.assertEqual(accounts[firm.id]['closing_wage_arrears_payable'], 1004.0)
        self.assertEqual(accounts[firm.id]['wage_arrears_accrued'], 2.0)
        self.assertEqual(accounts[worker.id]['opening_wage_arrears_claim'], 1002.0)
        self.assertEqual(accounts[worker.id]['closing_wage_arrears_claim'], 1004.0)

    def test_wage_arrears_paid_from_surplus_after_next_payroll_reserve(self):
        from economy.actor_accounts import (accrue_wage_arrear, begin_turn,
                                            seal_turn)
        from region_finance import settle_wage_arrears

        class Recorder:
            def __init__(self):
                self.rows = []

            def emit(self, clock, **row):
                self.rows.append({'turn': clock['turn'], **row})

        worker = self._worker(104)
        firm = self._firm(wage=2.0)
        firm.cash = 5.0
        worker.employer = firm
        firm.employees.append(worker)
        accrue_wage_arrear(firm, worker.id, 4.0)
        firm.wage_liabilities = [{'worker_id': worker.id, 'turn': 0,
                                  'amount': 4.0, 'status': 'unpaid'}]
        self.region.home_currency = 'USD'
        self.region._collective_trace_clock = {'turn': 1, 'next': 1,
                                               'phase': 'finance'}
        self.region._run_trace = Recorder()
        begin_turn(self.region, 1)

        payments = settle_wage_arrears(self.region, 1)
        accounts = {row['actor_id']: row for row in seal_turn(self.region, 1)}
        event = next(event for event in self.region.economic_events
                     if event['kind'] == 'wage_arrears_paid')
        trace = next(row for row in self.region._run_trace.rows
                     if row['kind'] == 'wage_arrears_repaid')

        self.assertEqual(payments[0]['amount'], 3.0)
        self.assertEqual(firm.cash, 2.0)  # one nominal payroll remains reserved
        self.assertEqual(worker.cash, 3.0)
        self.assertEqual(firm.wage_arrears_balance, 1.0)
        self.assertEqual(firm.wage_arrears_by_worker[worker.id], 1.0)
        self.assertEqual(firm.wage_liabilities[0]['paid_amount'], 3.0)
        self.assertEqual(firm.wage_liabilities[0]['status'], 'partial')
        self.assertEqual(event['payer_id'], firm.id)
        self.assertEqual(event['recipient_id'], worker.id)
        self.assertEqual(event['detail']['payroll_reserve'], 2.0)
        self.assertEqual(event['currency'], 'USD')
        self.assertEqual(accounts[firm.id]['closing_wage_arrears_payable'], 1.0)
        self.assertEqual(accounts[firm.id]['wage_arrears_payable_paid'], 3.0)
        self.assertEqual(accounts[worker.id]['closing_wage_arrears_claim'], 1.0)
        self.assertEqual(accounts[worker.id]['wage_arrears_claim_paid'], 3.0)
        self.assertEqual(accounts[firm.id]['posted_cash_change'], -3.0)
        self.assertEqual(accounts[worker.id]['posted_cash_change'], 3.0)
        self.assertEqual(accounts[firm.id]['unposted_cash_change'], 0.0)
        self.assertEqual(accounts[worker.id]['unposted_cash_change'], 0.0)
        self.assertEqual(trace['metric_id'], 'finance.wage_arrears')
        self.assertEqual(trace['before'], 4.0)
        self.assertEqual(trace['after'], 1.0)
        self.assertEqual(trace['inputs']['reason'],
                         'surplus_after_current_payroll')

    def test_quit_penalty_creates_claim_but_does_not_reattach_worker(self):
        worker = self._worker(111)
        firm = self._firm(wage=2.0)
        worker.employer = firm
        firm.employees.append(worker)
        ensure_labor_agreement(worker, firm, 0)
        self.region.labor_laws = {'quit_penalty': 'enacted'}
        result = quit_job(worker, self.region, 3, penalty=4)
        self.assertTrue(result['success'])
        self.assertIsNone(worker.employer)
        self.assertNotIn(worker, firm.employees)
        self.assertEqual(self.region.cash_obligations[0].origin, 'quit_penalty')

    def test_audit_accepts_consistent_rights_jobs_and_claims(self):
        worker = self._worker(121)
        firm = self._firm(wage=9.5)
        plot = LandPlot('audit', self.region.name, 8, 0.5, TenureStatus.FEUDAL,
                        tenant_ids=[worker.id])
        self.region.tenure.add_plot(plot)
        grant_access(self.region, worker.id, plot.plot_id, 'commons_food')
        claim = assess_obligation(self.region, worker.id, 8, 'rent', 1, 5)
        self.assertIsNotNone(claim)
        decision = evaluate_offer(worker, firm, self.region, 1, tightness=0.5)
        self.assertTrue(attach_worker(worker, firm, 1, decision))
        self.assertEqual(audit_labor_institutions(self.region), [])

    def test_authoritative_policy_command_and_snapshot_are_json_safe(self):
        import json
        from sim_server import SimServer, CommandType
        from sim_server.protocol import CommandMessage
        server = SimServer(seed=719)
        nation = next(n for n in server.nations if n.name == server.player_nation_name)
        tile = nation.tiles[0]
        result = server.execute_command(CommandMessage(CommandType.LABOR_LAW_ACTION,
                              {'tile': tile.name, 'law': 'vagrancy', 'action': 'enact'}))
        self.assertTrue(result['success'])
        self.assertTrue(tile.vagrancy_law_active)
        snapshot = SimServer.serialize_tile(tile, layout=server.layout, turn=server.turn)
        json.dumps(snapshot)
        self.assertIn('labor_institutions', snapshot)
        self.assertIn('counts', snapshot['labor_institutions'])

    def test_deterministic_world_survives_thirty_turns(self):
        from sim_server import SimServer
        server = SimServer(seed=90210)
        for _ in range(30):
            server.step()
        self.assertEqual(server.turn, 30)
        for nation in server.nations:
            for region in nation.tiles:
                self.assertEqual(audit_labor_institutions(region), [])


if __name__ == '__main__':
    unittest.main()
