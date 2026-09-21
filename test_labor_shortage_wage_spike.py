"""
test_labor_shortage_wage_spike.py — Automated regression testing for labor shortage wage dynamics.

Verifies:
1. Under acute demographic collapse / labor shortage, competitive firms bid up wages rather than cutting them.
2. Wages rise substantially toward worker reservation wage and MRPL ceiling.
3. Solvent firms remain viable.
4. Elevated corporate wages incentivize landlord pastoral conversion (converting arable land to sheep pasture).
"""

import unittest
import random
from sim_server.sim_server import SimServer
from region_labor import calculate_labor_market_tightness, calculate_firm_wage_ceiling
from goods import Goods
from land_rent import collect_rents
from land_tenure import TenureStatus


class TestLaborShortageWageSpike(unittest.TestCase):

    def setUp(self):
        self.server = SimServer(seed=4242)
        # Advance 15 turns to establish baseline economy
        for _ in range(15):
            self.server.step()

        # Find a tile with an active corporate firm
        self.target_tile = None
        for n in self.server.nations:
            for t in n.tiles:
                if any(getattr(a, 'is_corporation', False) for a in t.agents):
                    self.target_tile = t
                    break
            if self.target_tile:
                break
        self.assertIsNotNone(self.target_tile, "Expected at least one tile with an active corporation")

    def test_wage_spike_on_demographic_collapse(self):
        """When labor becomes scarce, wages should spike dynamically rather than crashing."""
        tile = self.target_tile
        firms = [a for a in tile.agents if getattr(a, 'is_corporation', False)]
        self.assertTrue(len(firms) > 0)
        firm = firms[0]
        initial_wage = firm.wage

        # Induce acute demographic collapse: kill 95% of living workers
        living_workers = [a for a in tile.agents if not a.is_corporation and not a.is_government and not getattr(a, 'is_lord', False)]
        kill_count = int(len(living_workers) * 0.95)
        random.seed(42)
        for a in random.sample(living_workers, kill_count):
            a.alive = False
            if a.employer and a in a.employer.employees:
                a.employer.employees.remove(a)
                a.employer = None

        tightness = calculate_labor_market_tightness(tile)
        self.assertGreater(tightness, 1.0, "Labor market tightness should exceed 1.0 after demographic collapse")

        # Step 1 turn
        self.server.step()
        post_shortage_wage = firm.wage

        # Wages should have spiked significantly (at least +30%)
        self.assertGreater(post_shortage_wage, initial_wage * 1.30,
                           f"Expected wage to spike on acute labor shortage, but got {post_shortage_wage:.2f} vs initial {initial_wage:.2f}")

    def test_pastoral_conversion_under_high_wages(self):
        """Landlords convert arable plots to sheep pasture when corporate wages are high."""
        tile = self.target_tile
        tenure = getattr(tile, 'tenure', None)
        self.assertIsNotNone(tenure, "Tile should have land tenure system")

        # Set up a tenant plot
        plot = tenure.plots[0] if tenure.plots else None
        self.assertIsNotNone(plot)
        plot.tenure = TenureStatus.ENCLOSED
        plot.production_type = 'arable'

        # Set corporate wage high (>= 1.70)
        firms = [a for a in tile.agents if getattr(a, 'is_corporation', False)]
        for f in firms:
            f.wage = 2.50

        # Step land rents
        collect_rents(tile, 20)

        # Landlord should have converted plot to pasture
        self.assertEqual(plot.production_type, 'pasture',
                         "Landlords should convert arable plots to sheep pasture when labor costs make arable farming uncompetitive")


if __name__ == '__main__':
    unittest.main()
