import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim.world import World
from sim.config import Params, Dials, PRESETS


def run(years, **kw):
    dials = kw.pop("dials", None)
    w = World(Params(**kw), dials)
    for _ in range(years * 4):
        if not w.adults():
            break
        w.step()          # step() audits money and food every tick (raises on a leak)
    return w


class SimTests(unittest.TestCase):
    def test_conservation_all_presets(self):
        for preset in PRESETS:
            w = run(45, seed=3, preset=preset)
            self.assertAlmostEqual(w.total_money(), w.money0, places=6)

    def test_determinism(self):
        a = run(10, seed=7)
        b = run(10, seed=7)
        self.assertEqual(a.series["pop"], b.series["pop"])
        self.assertEqual(a.series["gdp"], b.series["gdp"])

    def test_livable_baseline(self):
        """Before markets bite, life must look good: little work, high health, no hunger."""
        w = run(10, seed=1)
        S = w.series
        self.assertGreater(S["pop"][-1], 120)
        self.assertGreater(sum(S["med_health"][-4:]) / 4, 0.8)
        self.assertGreater(sum(S["free_hours"][-4:]) / 4, 9.0)
        self.assertLess(sum(S["hunger"][-4:]) / 4, 0.05)

    def test_customary_tenure_blocks_foreclosure(self):
        w = run(80, seed=1, dials=Dials(land_alienable=False))
        self.assertEqual(w.cause_counts.get("foreclosure", 0), 0)

    def test_hours_cap_dial(self):
        w = run(60, seed=1, dials=Dials(hours_cap=8.0))
        self.assertLessEqual(max(w.series["emp_hours"]), 8.0 + 1e-9)

    def test_emergence_not_scripted(self):
        """Capitalism emerges in the default endogenous run: land concentrates and capital appears."""
        w = run(100, seed=1)
        S = w.series
        self.assertGreater(S["land_gini"][-1], S["land_gini"][0] + 0.25)
        self.assertGreater(max(S["capital"]), 3)


if __name__ == "__main__":
    unittest.main()
