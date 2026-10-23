"""The authored delta must still reach two coasts on the release seeds."""
import unittest
from polygon_map import PolygonMapGenerator
from scenario_egypt_1877 import SCENARIO, shape_nile_delta


class EgyptDeltaSeedsTests(unittest.TestCase):
    def test_release_seeds_have_connected_distinct_coastal_outlets(self):
        terrain = SCENARIO['terrain']
        for seed in (1877, 1878):
            with self.subTest(seed=seed):
                gen = PolygonMapGenerator(
                    seed=seed, width=1024, height=1024,
                    num_points=terrain['points'], island_shape=terrain['shape'],
                    river_count=terrain['rivers'], mountain_sharpness=1.9,
                    canyon_depth=2.7, valley_width=1.4, enable_corner_improvement=True,
                    enable_roads=True, enable_lava=False, enable_noisy_edges=True)
                shape_nile_delta(gen)
                mouth, outlet = gen.scenario_nile_outlets
                self.assertIsNot(mouth, outlet)
                self.assertTrue(outlet.ocean)
                by_position = {(corner.x, corner.y): corner for corner in gen.corners}
                branch = [by_position[point[:2]] for point in gen.river_paths[-1]]
                self.assertIs(branch[-1], outlet)
                for parent, child in zip(branch, branch[1:]):
                    self.assertIn(child, parent.adjacent)
                paths_before = len(gen.river_paths)
                shape_nile_delta(gen)
                self.assertEqual(paths_before, len(gen.river_paths))


if __name__ == '__main__':
    unittest.main()
