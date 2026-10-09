"""Behavior checks for the first Plunder of Labor implementation slice."""

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


class TestPlunderLaborPhase1(unittest.TestCase):
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
        claim = offer_advance(lender, farmer, self.region, 8, 1, 'farm', lien_share=0.5)
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
        claim = assess_obligation(self.region, debtor.id, creditor.id, 'rent', 5, 0,
                                  collateral_plot_id=plot.plot_id)
        process_default_cases(self.region, 0)
        self.assertIn(debtor.id, plot.tenant_ids)
        self.assertEqual(self.region.enforcement_cases[0].earliest_turn, 1)
        self.region.police_employed = 1
        process_default_cases(self.region, 1)
        self.assertNotIn(debtor.id, plot.tenant_ids)
        self.assertEqual(self.region.enforcement_cases[0].claim_id, claim.id)

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


if __name__ == '__main__':
    unittest.main()
