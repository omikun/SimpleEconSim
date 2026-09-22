"""
hydraulic_erosion.py — Particle-based hydraulic & thermal erosion simulation for island meshes.

Implements droplet erosion mechanics based on fluvial sediment transport:
- Droplets land on terrain and accelerate along surface downhill gradient: g = -grad(h).
- Sediment capacity: C = Kc * sin(slope) * velocity * water_volume.
- Bedrock dissolution & alluvial deposition:
    - If sediment < C: erode bedrock up to max erosion rate Ke.
    - If sediment > C: deposit excess sediment, filling pits and forming alluvial fans.
- Evaporation and drag dampening.
- Thermal erosion (scree/talus slopes): mass transport when local slope exceeds angle of repose.

Operates directly on elevation grids or polygonal dual-mesh interpolations.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np


class HydraulicErosionSim:
    """Fast particle-based droplet and thermal erosion simulator."""

    def __init__(
        self,
        grid_size: int = 256,
        inertia: float = 0.05,
        sediment_capacity_factor: float = 4.0,
        min_sediment_capacity: float = 0.01,
        erode_speed: float = 0.3,
        deposit_speed: float = 0.3,
        evaporate_speed: float = 0.01,
        gravity: float = 4.0,
        max_droplet_lifetime: int = 30,
        initial_water_volume: float = 1.0,
        initial_speed: float = 1.0,
        erosion_radius: int = 3,
        talus_angle_deg: float = 33.0,
        seed: int = 42,
    ):
        self.grid_size = grid_size
        self.inertia = inertia
        self.capacity_factor = sediment_capacity_factor
        self.min_capacity = min_sediment_capacity
        self.erode_speed = erode_speed
        self.deposit_speed = deposit_speed
        self.evaporate_speed = evaporate_speed
        self.gravity = gravity
        self.max_lifetime = max_droplet_lifetime
        self.initial_water = initial_water_volume
        self.initial_speed = initial_speed
        self.erosion_radius = erosion_radius
        self.talus_threshold = math.tan(math.radians(talus_angle_deg))
        self.rng = np.random.RandomState(seed)

        # Precompute brush weight kernel for erosion radius
        self.brush_offsets, self.brush_weights = self._build_brush_kernel(erosion_radius)

    def _build_brush_kernel(self, radius: int) -> Tuple[np.ndarray, np.ndarray]:
        offsets = []
        weights = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                dist = math.hypot(dx, dy)
                if dist <= radius:
                    weight = max(0.0, 1.0 - dist / radius)
                    offsets.append((dx, dy))
                    weights.append(weight)
        offsets = np.array(offsets, dtype=np.int32)
        weights = np.array(weights, dtype=np.float32)
        w_sum = np.sum(weights)
        if w_sum > 0:
            weights /= w_sum
        return offsets, weights

    def compute_height_and_gradient(
        self, heightmap: np.ndarray, x: float, y: float
    ) -> Tuple[float, float, float]:
        """Bilinear height and gradient interpolation."""
        gx = int(x)
        gy = int(y)
        fx = x - gx
        fy = y - gy

        N = self.grid_size
        gx = max(0, min(N - 2, gx))
        gy = max(0, min(N - 2, gy))

        h00 = heightmap[gy, gx]
        h10 = heightmap[gy, gx + 1]
        h01 = heightmap[gy + 1, gx]
        h11 = heightmap[gy + 1, gx + 1]

        grad_x = (h10 - h00) * (1.0 - fy) + (h11 - h01) * fy
        grad_y = (h01 - h00) * (1.0 - fx) + (h11 - h10) * fx
        height = (
            h00 * (1.0 - fx) * (1.0 - fy)
            + h10 * fx * (1.0 - fy)
            + h01 * (1.0 - fx) * fy
            + h11 * fx * fy
        )
        return height, grad_x, grad_y

    def simulate_droplets(
        self,
        heightmap: np.ndarray,
        num_droplets: int = 15000,
        land_mask: Optional[np.ndarray] = None,
        carving_scale: float = 1.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Runs particle droplet simulation on the given 2D heightmap.
        Returns:
            eroded_heightmap: 2D np.ndarray float32 of updated heights.
            sediment_map: 2D np.ndarray float32 of net sediment deposited/eroded.
        """
        h = heightmap.astype(np.float32).copy()
        initial_h = h.copy()
        N = self.grid_size
        brush_offsets = self.brush_offsets
        brush_weights = self.brush_weights

        # Find valid candidate coordinates where land is present
        if land_mask is not None and np.any(land_mask):
            land_y, land_x = np.where(land_mask)
            num_candidates = len(land_y)
        else:
            land_y, land_x = None, None
            num_candidates = 0

        # Run droplets
        for _ in range(num_droplets):
            if num_candidates > 0:
                idx = self.rng.randint(0, num_candidates)
                # Jitter slightly within the grid cell
                px = float(land_x[idx]) + self.rng.uniform(0.1, 0.9)
                py = float(land_y[idx]) + self.rng.uniform(0.1, 0.9)
            else:
                px = self.rng.uniform(1.0, N - 2)
                py = self.rng.uniform(1.0, N - 2)

            dir_x = 0.0
            dir_y = 0.0
            speed = self.initial_speed
            water = self.initial_water
            sediment = 0.0

            for _step in range(self.max_lifetime):
                gx = int(px)
                gy = int(py)
                fx = px - gx
                fy = py - gy

                if gx < 1 or gx >= N - 2 or gy < 1 or gy >= N - 2:
                    break

                curr_h, grad_x, grad_y = self.compute_height_and_gradient(h, px, py)

                # Update droplet direction with momentum inertia
                dir_x = dir_x * self.inertia - grad_x * (1.0 - self.inertia)
                dir_y = dir_y * self.inertia - grad_y * (1.0 - self.inertia)

                dir_len = math.hypot(dir_x, dir_y)
                if dir_len < 1e-6:
                    # Flat or local pit: deposit all remaining sediment and stop
                    h[gy, gx] += sediment * 0.25 * (1.0 - fx) * (1.0 - fy)
                    h[gy, gx + 1] += sediment * 0.25 * fx * (1.0 - fy)
                    h[gy + 1, gx] += sediment * 0.25 * (1.0 - fx) * fy
                    h[gy + 1, gx + 1] += sediment * 0.25 * fx * fy
                    sediment = 0.0
                    break

                dir_x /= dir_len
                dir_y /= dir_len

                new_px = px + dir_x
                new_py = py + dir_y

                if new_px < 1 or new_px >= N - 2 or new_py < 1 or new_py >= N - 2:
                    break

                new_h, _, _ = self.compute_height_and_gradient(h, new_px, new_py)
                delta_h = new_h - curr_h

                # Compute sediment capacity
                slope = max(0.0, -delta_h)
                capacity = max(
                    slope * speed * water * self.capacity_factor,
                    self.min_capacity,
                )

                if delta_h > 0:
                    # Flowing uphill: fill pit up to delta_h
                    deposit_amt = min(sediment, delta_h)
                    sediment -= deposit_amt
                    h[gy, gx] += deposit_amt * (1.0 - fx) * (1.0 - fy)
                    h[gy, gx + 1] += deposit_amt * fx * (1.0 - fy)
                    h[gy + 1, gx] += deposit_amt * (1.0 - fx) * fy
                    h[gy + 1, gx + 1] += deposit_amt * fx * fy
                elif sediment > capacity:
                    # Oversaturated: deposit excess sediment
                    deposit_amt = (sediment - capacity) * self.deposit_speed
                    sediment -= deposit_amt
                    h[gy, gx] += deposit_amt * (1.0 - fx) * (1.0 - fy)
                    h[gy, gx + 1] += deposit_amt * fx * (1.0 - fy)
                    h[gy + 1, gx] += deposit_amt * (1.0 - fx) * fy
                    h[gy + 1, gx + 1] += deposit_amt * fx * fy
                else:
                    # Undersaturated: erode bedrock
                    erode_amt = min((capacity - sediment) * self.erode_speed, -delta_h) * carving_scale
                    sediment += erode_amt

                    # Distribute erosion smoothly across brush kernel
                    for k in range(len(brush_offsets)):
                        ox, oy = brush_offsets[k]
                        bx = gx + ox
                        by = gy + oy
                        if 0 <= bx < N and 0 <= by < N:
                            h[by, bx] -= erode_amt * brush_weights[k]

                # Update speed and water volume
                speed = math.sqrt(max(0.01, speed * speed - delta_h * self.gravity))
                water *= (1.0 - self.evaporate_speed)
                px = new_px
                py = new_py

        sediment_map = h - initial_h
        return h, sediment_map

    def apply_thermal_erosion(
        self,
        heightmap: np.ndarray,
        iterations: int = 3,
        talus_angle: float = 0.08,
    ) -> np.ndarray:
        """
        Thermal erosion / talus relaxation:
        Transports material downhill if the local gradient between neighboring cells
        exceeds the critical angle of repose.
        """
        h = heightmap.copy()
        N = self.grid_size

        for _ in range(iterations):
            # Compute differences to 4 cardinal neighbors
            up_diff = h[1:-1, 1:-1] - h[:-2, 1:-1]
            down_diff = h[1:-1, 1:-1] - h[2:, 1:-1]
            left_diff = h[1:-1, 1:-1] - h[1:-1, :-2]
            right_diff = h[1:-1, 1:-1] - h[1:-1, 2:]

            # Mask where difference exceeds talus threshold
            for diff, slice_target in [
                (up_diff, (slice(0, -2), slice(1, -1))),
                (down_diff, (slice(2, None), slice(1, -1))),
                (left_diff, (slice(1, -1), slice(0, -2))),
                (right_diff, (slice(1, -1), slice(2, None))),
            ]:
                excess = diff - talus_angle
                mask = excess > 0
                if np.any(mask):
                    transfer = excess[mask] * 0.15
                    h[1:-1, 1:-1][mask] -= transfer
                    h[slice_target][mask] += transfer

        return h


def apply_erosion_to_polygon_mesh(
    gen,
    grid_size: int = 256,
    num_droplets: int = 15000,
    carving_scale: float = 0.35,
    thermal_iterations: int = 2,
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """
    Simulates hydraulic and thermal erosion across an entire PolygonMapGenerator island.
    Rasterizes dual-graph elevations to an N x N float grid, runs erosion particles,
    and returns elevation deltas for Voronoi centers and corners.
    
    Returns:
        center_deltas: {center.index: float delta}
        corner_deltas: {corner.index: float delta}
    """
    if num_droplets <= 0 and thermal_iterations <= 0:
        return {}, {}

    scale_x = (grid_size - 1) / gen.width
    scale_y = (grid_size - 1) / gen.height

    # 1. Rasterize mesh elevations onto grid
    grid = np.zeros((grid_size, grid_size), dtype=np.float32)
    counts = np.zeros((grid_size, grid_size), dtype=np.float32)
    land_mask = np.zeros((grid_size, grid_size), dtype=bool)

    for c in gen.centers:
        gx = int(np.clip(round(c.x * scale_x), 0, grid_size - 1))
        gy = int(np.clip(round(c.y * scale_y), 0, grid_size - 1))
        grid[gy, gx] += c.elevation
        counts[gy, gx] += 1.0
        if not c.water:
            land_mask[gy, gx] = True

    for cn in gen.corners:
        gx = int(np.clip(round(cn.x * scale_x), 0, grid_size - 1))
        gy = int(np.clip(round(cn.y * scale_y), 0, grid_size - 1))
        grid[gy, gx] += cn.elevation
        counts[gy, gx] += 1.0
        if not cn.water:
            land_mask[gy, gx] = True

    # Fill unpopulated grid cells using nearest neighbor / distance fill
    valid = counts > 0
    if not np.any(valid):
        return {}, {}

    # Normalize populated cells
    grid[valid] /= counts[valid]

    # Simple 2D diffusion / blur to fill holes
    from scipy.ndimage import gaussian_filter
    filled_grid = grid.copy()
    diffused = gaussian_filter(grid, sigma=1.5)
    filled_grid[~valid] = diffused[~valid]

    # 2. Run hydraulic and thermal erosion
    sim = HydraulicErosionSim(grid_size=grid_size, seed=gen.seed)
    eroded_grid, _ = sim.simulate_droplets(
        filled_grid,
        num_droplets=num_droplets,
        land_mask=land_mask,
        carving_scale=carving_scale,
    )
    if thermal_iterations > 0:
        eroded_grid = sim.apply_thermal_erosion(eroded_grid, iterations=thermal_iterations)

    elevation_delta_grid = eroded_grid - filled_grid

    # 3. Sample delta map back to mesh centers and corners
    center_deltas: Dict[int, float] = {}
    for c in gen.centers:
        if c.water:
            center_deltas[c.index] = 0.0
            continue
        gx = int(np.clip(round(c.x * scale_x), 0, grid_size - 1))
        gy = int(np.clip(round(c.y * scale_y), 0, grid_size - 1))
        center_deltas[c.index] = float(elevation_delta_grid[gy, gx])

    corner_deltas: Dict[int, float] = {}
    for cn in gen.corners:
        if cn.water:
            corner_deltas[cn.index] = 0.0
            continue
        gx = int(np.clip(round(cn.x * scale_x), 0, grid_size - 1))
        gy = int(np.clip(round(cn.y * scale_y), 0, grid_size - 1))
        corner_deltas[cn.index] = float(elevation_delta_grid[gy, gx])

    return center_deltas, corner_deltas
