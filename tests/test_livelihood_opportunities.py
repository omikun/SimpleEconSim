"""Feasible livelihood choices use access, buyers, and funded offers."""

import unittest

from agent import Agent, initialize_agent
from economy.labor_mobility import LaborMobilityScheduler, independent_return
from goods import Goods
from land_tenure import LandPlot, TenureStatus
from region import Region


class LivelihoodOpportunityTests(unittest.TestCase):
    def test_field_right_required_for_farming_and_cotton(self):
        tile = Region('Opportunity', 0, 2)
        worker = Agent(0)
        initialize_agent(worker, Goods.wood, 0, 0, 20)
        worker.region = tile.name
        self.assertEqual(independent_return(tile, worker, Goods.food, 0)[1],
                         'no usable field right')
        plot = LandPlot('field-1', tile.name, worker.id, 0.5,
                        TenureStatus.FEUDAL, tenant_ids=[worker.id])
        tile.tenure.plots = []
        tile.access_rights.clear()
        tile._access_rights_seeded = False
        tile.tenure.add_plot(plot)
        worker.assigned_plot_id = plot.plot_id
        value, reason = independent_return(tile, worker, Goods.food, 0)
        self.assertGreater(value, 0)
        self.assertIn('household food', reason)

    def test_craft_with_no_observed_buyer_has_no_cash_return(self):
        tile = Region('No buyer', 0, 2)
        worker = Agent(0)
        initialize_agent(worker, Goods.furniture, 10, 0, 100)
        tile.sold_log[Goods.furniture] = [0, 0, 0]
        value, reason = independent_return(tile, worker, Goods.furniture, 0)
        self.assertEqual(value, 0)
        self.assertEqual(reason, 'no observed buyer')

    def test_rejected_top_offer_does_not_hide_funded_lower_offer(self):
        tile = Region('Two offers', 0, 2)
        worker = Agent(0)
        initialize_agent(worker, Goods.wood, 0, 0, 0)
        worker.region = tile.name
        worker.hungry_steps = 3
        incumbent = Agent(0)
        initialize_agent(incumbent, Goods.wood, 0, 0, 0)
        high = Agent(0)
        initialize_agent(high, Goods.wood, 0, 0, 11)
        high.is_corporation = True
        high.wage = 10
        high.max_employees = 3
        high.employees = [incumbent]
        incumbent.employer = high
        low = Agent(0)
        initialize_agent(low, Goods.wood, 0, 0, 100)
        low.is_corporation = True
        low.wage = 5
        low.max_employees = 3
        tile.agents = [worker, incumbent, high, low]
        LaborMobilityScheduler().step_labor_cohort(tile, 1)
        self.assertIs(worker.employer, low)
        offers = [row for row in tile.labor_decision_log if row['worker_id'] == worker.id]
        self.assertEqual([row['firm_id'] for row in offers[:2]], [high.id, low.id])
        self.assertEqual([row['reason'] for row in offers[:2]], ['unfunded', 'accepted'])


if __name__ == '__main__':
    unittest.main()
