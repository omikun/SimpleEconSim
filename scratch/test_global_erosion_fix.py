import math, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.interpolate import LinearNDInterpolator
from polygon_map import PolygonMapGenerator
from hydraulic_erosion import HydraulicErosionSim

print("Generating map...")
gen = PolygonMapGenerator(width=1000, height=1000, num_points=1000, seed=42)

# Build continuous global elevation field
pts, vals = [], []
for c in gen.centers:
    pts.append([c.x, c.y])
    vals.append(c.elevation if not c.water else 0.0)
for cn in gen.corners:
    pts.append([cn.x, cn.y])
    vals.append(cn.elevation if not cn.water else 0.0)

w, h = gen.width, gen.height
for bx in [-100, 0, w//2, w, w+100]:
    for by in [-100, 0, h//2, h, h+100]:
        pts.append([bx, by])
        vals.append(0.0)

pts = np.array(pts, dtype=np.float64)
vals = np.array(vals, dtype=np.float64)
interp = LinearNDInterpolator(pts, vals, fill_value=0.0)

grid_size = 256
gx, gy = np.meshgrid(np.linspace(0, w, grid_size), np.linspace(0, h, grid_size))
base_grid = interp(gx, gy)
base_grid = np.nan_to_num(base_grid, nan=0.0)

print(f"Base grid shape: {base_grid.shape}, min: {base_grid.min():.3f}, max: {base_grid.max():.3f}")

# Hydraulic erosion
sim = HydraulicErosionSim(grid_size=grid_size, seed=42)
land_mask = base_grid > 0.02
t0 = time.time()
eroded_grid, sediment_map = sim.simulate_droplets(base_grid, num_droplets=8000, land_mask=land_mask, carving_scale=0.35)
eroded_grid = sim.apply_thermal_erosion(eroded_grid, iterations=2)
print(f"Erosion simulation time: {time.time() - t0:.2f}s")

delta = eroded_grid - base_grid
print(f"Delta min: {delta.min():.4f}, max: {delta.max():.4f}, std: {delta.std():.4f}")

fig, axs = plt.subplots(1, 3, figsize=(18, 6))
axs[0].imshow(base_grid, origin='lower', cmap='terrain')
axs[0].set_title("1. Continuous Base Heightmap")
axs[1].imshow(delta, origin='lower', cmap='seismic', vmin=-0.1, vmax=0.1)
axs[1].set_title("2. Global Erosion/Deposition Deltas")
axs[2].imshow(eroded_grid, origin='lower', cmap='terrain')
axs[2].set_title("3. Final Eroded Island Heightmap")
for ax in axs: ax.axis('off')
plt.tight_layout()
plt.savefig("scratch/global_erosion_preview.png", dpi=150)
print("Saved preview to scratch/global_erosion_preview.png")
