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
from typing import Any, Dict, List, Optional, Tuple

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


class HydraulicErosionResult:
    """Continuous 2D height and sediment field resulting from global hydraulic erosion."""

    def __init__(
        self,
        base_grid: np.ndarray,
        eroded_grid: np.ndarray,
        sediment_map: np.ndarray,
        width: float,
        height: float,
        grid_size: int,
    ):
        self.base_grid = base_grid.astype(np.float32)
        self.eroded_grid = eroded_grid.astype(np.float32)
        self.sediment_map = sediment_map.astype(np.float32)
        self.delta_grid = (self.eroded_grid - self.base_grid).astype(np.float32)
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))
        self.grid_size = grid_size
        self._scale_x = (grid_size - 1) / self.width
        self._scale_y = (grid_size - 1) / self.height

    def sample_elevation(self, x: float, y: float) -> float:
        """Continuous bilinear sampling of eroded elevation at any (x, y) coordinates."""
        gx = max(0.0, min(self.grid_size - 1.001, x * self._scale_x))
        gy = max(0.0, min(self.grid_size - 1.001, y * self._scale_y))
        ix = int(gx)
        iy = int(gy)
        fx = gx - ix
        fy = gy - iy
        g = self.eroded_grid
        return float(
            (g[iy, ix] * (1.0 - fx) + g[iy, ix + 1] * fx) * (1.0 - fy)
            + (g[iy + 1, ix] * (1.0 - fx) + g[iy + 1, ix + 1] * fx) * fy
        )

    def sample_delta(self, x: float, y: float) -> float:
        """Continuous bilinear sampling of erosion/deposition delta at any (x, y) coordinates."""
        gx = max(0.0, min(self.grid_size - 1.001, x * self._scale_x))
        gy = max(0.0, min(self.grid_size - 1.001, y * self._scale_y))
        ix = int(gx)
        iy = int(gy)
        fx = gx - ix
        fy = gy - iy
        d = self.delta_grid
        return float(
            (d[iy, ix] * (1.0 - fx) + d[iy, ix + 1] * fx) * (1.0 - fy)
            + (d[iy + 1, ix] * (1.0 - fx) + d[iy + 1, ix + 1] * fx) * fy
        )


def build_continuous_island_heightmap(
    gen,
    grid_size: int = 256,
) -> Tuple[np.ndarray, np.ndarray, Any]:
    """
    Builds a continuous, smooth 2D elevation grid across the entire island
    using Delaunay barycentric interpolation from polygon centers and corners.
    Eliminates all discrete per-cell discontinuities and stair-stepping.
    """
    from scipy.interpolate import LinearNDInterpolator

    pts = []
    vals = []
    for c in gen.centers:
        pts.append([c.x, c.y])
        vals.append(c.elevation if not c.water else 0.0)
    for cn in gen.corners:
        pts.append([cn.x, cn.y])
        vals.append(0.0 if (cn.water or cn.ocean or getattr(cn, "coast", False)) else cn.elevation)

    # Pin ocean coastline edge midpoints strictly to 0.0 to ensure continuous zero waterline
    for edge in getattr(gen, "edges", []):
        if edge.d0 and edge.d1 and edge.v0 and edge.v1:
            if (edge.d0.water != edge.d1.water) and (edge.d0.ocean or edge.d1.ocean):
                pts.append([edge.midpoint[0], edge.midpoint[1]])
                vals.append(0.0)

    # Frame boundary points strictly outside the island to prevent boundary extrapolation NaNs
    w, h = gen.width, gen.height
    for bx in [-w * 0.2, w * 1.2]:
        for by in np.linspace(-h * 0.2, h * 1.2, 7):
            pts.append([bx, by])
            vals.append(0.0)
    for by in [-h * 0.2, h * 1.2]:
        for bx in np.linspace(-w * 0.2, w * 1.2, 7):
            pts.append([bx, by])
            vals.append(0.0)

    pts_arr = np.array(pts, dtype=np.float64)
    vals_arr = np.array(vals, dtype=np.float64)
    interp = LinearNDInterpolator(pts_arr, vals_arr, fill_value=0.0)

    gx, gy = np.meshgrid(
        np.linspace(0, w, grid_size),
        np.linspace(0, h, grid_size),
    )
    base_grid = interp(gx, gy)
    base_grid = np.nan_to_num(base_grid, nan=0.0).astype(np.float32)
    land_mask = base_grid > 0.02
    return base_grid, land_mask, interp


def _droplet_worker_chunk(args):
    """Worker process task for parallel droplet chunk execution."""
    grid, num_drops, seed, land_mask, carving_scale = args
    sim = HydraulicErosionSim(grid_size=grid.shape[0], seed=seed)
    eroded, sed = sim.simulate_droplets(
        grid,
        num_droplets=num_drops,
        land_mask=land_mask,
        carving_scale=carving_scale,
    )
    return (eroded - grid), sed


def simulate_global_erosion(
    gen,
    grid_size: int = 256,
    num_droplets: int = 15000,
    carving_scale: float = 0.45,
    thermal_iterations: int = 2,
    seed: Optional[int] = None,
) -> HydraulicErosionResult:
    """
    Simulates global hydraulic and thermal erosion across the entire continuous island continuum.
    Droplets carve natural dendritic river channels and deposit alluvial sediment seamlessly
    across polygon boundaries.
    """
    base_grid, land_mask, _ = build_continuous_island_heightmap(gen, grid_size=grid_size)
    sim_seed = seed if seed is not None else getattr(gen, "seed", 42)

    if num_droplets <= 0 and thermal_iterations <= 0:
        return HydraulicErosionResult(
            base_grid=base_grid,
            eroded_grid=base_grid,
            sediment_map=np.zeros_like(base_grid),
            width=float(gen.width),
            height=float(gen.height),
            grid_size=grid_size,
        )

    # Multi-core CPU parallel execution for high droplet counts
    sim = HydraulicErosionSim(grid_size=grid_size, seed=sim_seed)
    if num_droplets >= 2000:
        import os
        from concurrent.futures import ProcessPoolExecutor
        num_workers = min(8, max(2, os.cpu_count() or 4))
        chunk = num_droplets // num_workers
        remainder = num_droplets % num_workers
        args_list = [
            (
                base_grid,
                chunk + (remainder if i == 0 else 0),
                sim_seed + i * 1337,
                land_mask,
                carving_scale,
            )
            for i in range(num_workers)
        ]
        try:
            with ProcessPoolExecutor(max_workers=num_workers) as ex:
                results = list(ex.map(_droplet_worker_chunk, args_list))
            delta_total = np.zeros_like(base_grid)
            sediment_map = np.zeros_like(base_grid)
            for d, s in results:
                delta_total += d
                sediment_map += s
            eroded_grid = base_grid + delta_total
        except Exception as exc:
            # Fallback to single thread if multiprocessing is restricted
            eroded_grid, sediment_map = sim.simulate_droplets(
                base_grid,
                num_droplets=num_droplets,
                land_mask=land_mask,
                carving_scale=carving_scale,
            )
    else:
        eroded_grid, sediment_map = sim.simulate_droplets(
            base_grid,
            num_droplets=num_droplets,
            land_mask=land_mask,
            carving_scale=carving_scale,
        )

    if thermal_iterations > 0:
        eroded_grid = sim.apply_thermal_erosion(eroded_grid, iterations=thermal_iterations)

    return HydraulicErosionResult(
        base_grid=base_grid,
        eroded_grid=eroded_grid,
        sediment_map=sediment_map,
        width=float(gen.width),
        height=float(gen.height),
        grid_size=grid_size,
    )


def apply_erosion_to_polygon_mesh(
    gen,
    grid_size: int = 256,
    num_droplets: int = 15000,
    carving_scale: float = 0.35,
    thermal_iterations: int = 2,
    return_field: bool = False,
):
    """
    Simulates hydraulic and thermal erosion across an entire PolygonMapGenerator island.
    Rasterizes dual-graph elevations to a continuous smooth grid, runs erosion droplets,
    and returns elevation deltas for Voronoi centers and corners.
    
    Returns:
        If return_field is False: (center_deltas, corner_deltas)
        If return_field is True:  (center_deltas, corner_deltas, erosion_field)
    """
    if num_droplets <= 0 and thermal_iterations <= 0:
        empty_field = HydraulicErosionResult(
            base_grid=np.zeros((grid_size, grid_size), dtype=np.float32),
            eroded_grid=np.zeros((grid_size, grid_size), dtype=np.float32),
            sediment_map=np.zeros((grid_size, grid_size), dtype=np.float32),
            width=float(gen.width),
            height=float(gen.height),
            grid_size=grid_size,
        )
        if return_field:
            return {}, {}, empty_field
        return {}, {}

    result = simulate_global_erosion(
        gen,
        grid_size=grid_size,
        num_droplets=num_droplets,
        carving_scale=carving_scale,
        thermal_iterations=thermal_iterations,
    )

    center_deltas: Dict[int, float] = {}
    for c in gen.centers:
        if c.water:
            center_deltas[c.index] = 0.0
        else:
            center_deltas[c.index] = result.sample_delta(c.x, c.y)

    corner_deltas: Dict[int, float] = {}
    for cn in gen.corners:
        if cn.water:
            corner_deltas[cn.index] = 0.0
        else:
            corner_deltas[cn.index] = result.sample_delta(cn.x, cn.y)

    if return_field:
        return center_deltas, corner_deltas, result
    return center_deltas, corner_deltas
