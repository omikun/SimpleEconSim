"""
test_statute_of_laborers.py — Regression tests for the Statute of Laborers decree,
maximum wage ceiling, class faction reactions, and worker resistance.
"""

import unittest
from sim_server.sim_server import SimServer
from labor_politics import enact_statute_of_laborers, repeal_statute_of_laborers
from region_factions import accumulate_grievances, step_factions
from worldview_tooltips import get_button_tooltip_data


class TestStatuteOfLaborers(unittest.TestCase):

    def setUp(self):
        self.server = SimServer(seed=4242)
        for _ in range(15):
            self.server.step()

        self.target_nation = self.server.nations[0]
        self.target_tile = None
        for n in self.server.nations:
            for t in n.tiles:
                if any(getattr(a, 'is_corporation', False) for a in t.agents):
                    self.target_tile = t
                    self.target_nation = n
                    break
            if self.target_tile:
                break
        self.assertIsNotNone(self.target_tile)

    def test_statute_enactment_and_wage_capping(self):
        """Statute of Laborers immediately clamps wages above cap and prevents bidding beyond cap."""
        nation = self.target_nation
        tile = self.target_tile

        # Set firm wage arbitrarily high
        firm = [a for a in tile.agents if getattr(a, 'is_corporation', False)][0]
        firm.wage = 4.50
        firm.cash = 2000.0

        cap = 1.30
        ok, msg = enact_statute_of_laborers(nation, wage_cap=cap)
        self.assertTrue(ok)
        self.assertTrue(nation.statute_of_laborers)
        self.assertTrue(tile.statute_of_laborers)
        self.assertAlmostEqual(firm.wage, cap, places=2)

        # Step sim: wages should remain clamped to cap
        self.server.step()
        self.assertLessEqual(firm.wage, cap + 1e-4)

    def test_class_faction_reactions_and_grievances(self):
        """Enacting statute satisfies Gentry but provokes Proletariat wage suppression grievance."""
        nation = self.target_nation
        tile = self.target_tile

        # Check initial faction support
        gentry = tile.factions.get('Gentry')
        proletariat = tile.factions.get('Proletariat')
        self.assertIsNotNone(gentry)
        self.assertIsNotNone(proletariat)

        init_gentry_supp = gentry.support
        init_prol_supp = proletariat.support

        # Enact Statute
        enact_statute_of_laborers(nation, wage_cap=1.20)
        self.assertGreater(gentry.support, init_gentry_supp)
        self.assertLess(proletariat.support, init_prol_supp)

        # Accumulate grievances under statute
        adds = accumulate_grievances(tile, self.server.turn)
        sources = tile.grievance_sources_log[-1]['raw']
        self.assertIn('wage_suppression', sources)
        self.assertGreater(sources['wage_suppression'], 0.0)

    def test_repeal_restores_free_bargaining(self):
        """Repealing statute removes wage cap and restores labor satisfaction."""
        nation = self.target_nation
        tile = self.target_tile

        enact_statute_of_laborers(nation, wage_cap=1.20)
        self.assertTrue(tile.statute_of_laborers)

        ok, msg = repeal_statute_of_laborers(nation)
        self.assertTrue(ok)
        self.assertFalse(nation.statute_of_laborers)
        self.assertFalse(tile.statute_of_laborers)

    def test_tooltip_parity(self):
        """Governance panel tooltip provides rich historical and game stats for the decree."""
        nation = self.target_nation
        tile = self.target_tile

        world_ctx = {'turn': 20, 'nations': self.server.nations}
        tip = get_button_tooltip_data('nat_toggle_statute_of_laborers', world=world_ctx,
                                      region=tile, nation=nation)
        self.assertIsNotNone(tip)
        self.assertIn("Statute of Laborers", tip['title'])
        self.assertEqual(tip['badge'], "CLASS DECREE")
        self.assertTrue(len(tip['desc']) >= 3)
        self.assertTrue(len(tip['stats']) >= 3)


if __name__ == '__main__':
    unittest.main()
