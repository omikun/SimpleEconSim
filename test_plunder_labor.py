"""Behavior checks for the first Plunder of Labor implementation slice."""

import unittest
from types import SimpleNamespace

from agent import Agent
from economy.labor_mobility import LaborMobilityScheduler
from goods import Goods
from labor_choice import evaluate_offer, attach_worker
from land_tenure import LandPlot, TenureStatus, TileTenure
from foraging import forage_tile


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
        plot = LandPlot('p1', self.region.name, 8, 0.5, TenureStatus.FEUDAL)
        self.region.tenure.add_plot(plot)
        worker.assigned_plot_id = plot.plot_id
        before = (worker.employer, list(firm.employees), worker.output)

        secure = evaluate_offer(worker, firm, self.region, 1, tightness=0.5)
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


if __name__ == '__main__':
    unittest.main()
