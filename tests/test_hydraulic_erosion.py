import unittest
import numpy as np
from hydraulic_erosion import HydraulicErosionSim, apply_erosion_to_polygon_mesh
from polygon_map import PolygonMapGenerator

class TestHydraulicErosion(unittest.TestCase):
    def test_erosion_simulation_basic(self):
        # Create a simple conical mountain
        N = 64
        x, y = np.meshgrid(np.linspace(-1, 1, N), np.linspace(-1, 1, N))
        dist = np.sqrt(x*x + y*y)
        h = np.clip(1.0 - dist, 0.0, 1.0).astype(np.float32)

        sim = HydraulicErosionSim(grid_size=N, seed=42)
        eroded, sediment = sim.simulate_droplets(h, num_droplets=2000, carving_scale=0.5)

        self.assertEqual(eroded.shape, (N, N))
        self.assertEqual(sediment.shape, (N, N))
        # The peak should have experienced erosion (reduced height)
        self.assertLess(eroded[N//2, N//2], h[N//2, N//2] + 1e-3)
        # Total elevation should change due to carved river beds/gullies
        self.assertTrue(np.any(sediment != 0))

    def test_thermal_erosion(self):
        # Create a cliff with a steep step
        N = 32
        h = np.zeros((N, N), dtype=np.float32)
        h[:16, :] = 10.0  # Very steep cliff

        sim = HydraulicErosionSim(grid_size=N, seed=42)
        relaxed = sim.apply_thermal_erosion(h, iterations=5, talus_angle=0.1)

        # Cliff top should decrease, bottom of cliff should increase
        self.assertLess(relaxed[15, N//2], 10.0)
        self.assertGreater(relaxed[16, N//2], 0.0)

    def test_apply_erosion_to_polygon_mesh(self):
        gen = PolygonMapGenerator(seed=123, width=500, height=500, num_points=100)
        c_deltas, cn_deltas = apply_erosion_to_polygon_mesh(gen, grid_size=64, num_droplets=1000)

        self.assertTrue(len(c_deltas) > 0)
        self.assertTrue(len(cn_deltas) > 0)

if __name__ == "__main__":
    unittest.main()
