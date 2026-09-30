"""
terrain/elevation/heightmap.py — Continuous Landmass, Elevation, and Biomes for REGNUM.
"""

import math
import random
from collections import deque
import numpy as np

from hexmap import rectangular_hex_layout, axial_neighbors, axial_to_offset, axial_to_pixel, HEX_DIRS, _SQRT3
from terrain.elevation.topographic import get_cached_topographic_surface, _generate_topographic_surface_impl

class HeightMapGenerator:
    """Generates continuous continental landmasses with Inigo Quilez derivative erosion fBm."""

    def __init__(self, seed: int = 42, grid_rows: int = 9, grid_cols: int = 9):
        self.seed = seed
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self._layout = rectangular_hex_layout(grid_rows, grid_cols)
        
        rng = np.random.default_rng(seed if seed is not None else 42)
        # 256x256 random texture table (equivalent to iChannel0)
        self.noise_table = rng.uniform(0.0, 1.0, (256, 256)).astype(np.float32)
        # Inigo Quilez rotation matrix mat2(0.8, -0.6, 0.6, 0.8)
        self.m2 = np.array([[0.8, -0.6], [0.6, 0.8]], dtype=np.float32)
        
        py_rng = random.Random(seed if seed is not None else 42)
        self.spine_angle = py_rng.uniform(-0.35, 0.35)
        self.spine_offset = py_rng.uniform(-0.15, 0.15)

    def noised_scalar(self, px: float, py: float) -> tuple[float, float, float]:
        """Value noise with analytical derivatives for single coordinate (returns val, dx, dy)."""
        ix = int(math.floor(px))
        iy = int(math.floor(py))
        fx = px - ix
        fy = py - iy

        ux = fx * fx * (3.0 - 2.0 * fx)
        uy = fy * fy * (3.0 - 2.0 * fy)
        dux = 6.0 * fx * (1.0 - fx)
        duy = 6.0 * fy * (1.0 - fy)

        ix0 = ix & 255
        iy0 = iy & 255
        ix1 = (ix + 1) & 255
        iy1 = (iy + 1) & 255

        a = float(self.noise_table[iy0, ix0])
        b = float(self.noise_table[iy0, ix1])
        c = float(self.noise_table[iy1, ix0])
        d = float(self.noise_table[iy1, ix1])

        k0 = a
        k1 = b - a
        k2 = c - a
        k3 = a - b - c + d

        val = k0 + k1 * ux + k2 * uy + k3 * ux * uy
        dx = dux * (k1 + k3 * uy)
        dy = duy * (k2 + k3 * ux)
        return val, dx, dy

    def get_continuous_height(self, nx: float, ny: float) -> float:
        """Calculate continuous normalized elevation with Inigo Quilez derivative erosion."""
        dist_sq = nx * nx + ny * ny
        continent_base = 0.54 - 0.76 * dist_sq

        diag = nx * math.cos(self.spine_angle) + ny * math.sin(self.spine_angle) + self.spine_offset
        ridge = math.exp(-4.2 * (diag ** 2)) * 0.38

        # 8-octave derivative erosion loop
        px = nx * 3.2
        py = ny * 3.2
        a = 0.0
        b = 1.0
        dx_accum = 0.0
        dy_accum = 0.0

        for _ in range(8):
            n_val, ndx, ndy = self.noised_scalar(px, py)
            dx_accum += ndx
            dy_accum += ndy
            a += b * n_val / (1.0 + (dx_accum * dx_accum + dy_accum * dy_accum))
            b *= 0.50
            npx = 2.0 * (0.8 * px - 0.6 * py)
            npy = 2.0 * (0.6 * px + 0.8 * py)
            px, py = npx, npy

        h_noise = (a - 0.9) * 0.75
        raw_H = continent_base + ridge + h_noise
        total_h = raw_H * 0.92 if raw_H > 0.0 else raw_H
        return max(-1.0, min(1.0, total_h))

    def get_raw_height(self, r: int, c: int) -> float:
        """Calculate continuous normalized elevation in [-1.0, 1.0]."""
        nx = (c - (self.grid_cols - 1) / 2.0) / (self.grid_cols / 2.0)
        ny = (r - (self.grid_rows - 1) / 2.0) / (self.grid_rows / 2.0)
        return self.get_continuous_height(nx, ny)

    def get_elevation_meters(self, h: float) -> int:
        """Convert normalized elevation [-1.0, 1.0] to realistic meters."""
        if h < 0.0:
            return int(h * 1500)
        else:
            return int(h * 3200)

    def get_biome(self, h: float) -> str:
        """Return descriptive biome name based on elevation."""
        if h < -0.30:
            return 'deep_ocean'
        elif h < 0.0:
            return 'shallow_ocean'
        elif h < 0.22:
            return 'plains'
        elif h < 0.48:
            return 'forest'
        elif h < 0.72:
            return 'hills'
        elif h < 0.88:
            return 'mountains'
        else:
            return 'snow_peaks'

    def get_base_color(self, h: float) -> tuple[int, int, int]:
        """Return base natural terrain color for a given elevation."""
        if h < -0.30:
            t = (h - (-1.0)) / 0.70
            return self._lerp_color((12, 28, 62), (22, 58, 105), t)
        elif h < 0.0:
            t = (h - (-0.30)) / 0.30
            return self._lerp_color((22, 58, 105), (42, 110, 150), t)
        elif h < 0.22:
            t = h / 0.22
            return self._lerp_color((85, 150, 80), (75, 138, 72), t)
        elif h < 0.48:
            t = (h - 0.22) / 0.26
            return self._lerp_color((32, 95, 42), (48, 108, 45), t)
        elif h < 0.72:
            t = (h - 0.48) / 0.24
            return self._lerp_color((135, 122, 84), (120, 108, 92), t)
        elif h < 0.88:
            t = (h - 0.72) / 0.16
            return self._lerp_color((105, 102, 110), (138, 134, 140), t)
        else:
            t = min(1.0, (h - 0.88) / 0.12)
            return self._lerp_color((215, 222, 235), (245, 250, 255), t)

    def generate_river_paths(self) -> list[list[tuple[float, float]]]:
        """Generate continuous natural river paths flowing strictly downhill from mountain springs to the ocean or inland lakes."""
        import numpy as np
        spring_candidates = []
        sample_ny = np.linspace(-0.80, 0.80, 32)
        sample_nx = np.linspace(-0.80, 0.80, 32)
        for s_ny in sample_ny:
            for s_nx in sample_nx:
                h_val = self.get_continuous_height(float(s_nx), float(s_ny))
                if 0.50 <= h_val <= 0.85:
                    spring_candidates.append((float(s_nx), float(s_ny), h_val))

        rng = random.Random(self.seed + 12345)
        rng.shuffle(spring_candidates)

        selected_springs = []
        for sc in spring_candidates:
            if all((sc[0] - prev[0])**2 + (sc[1] - prev[1])**2 > 0.12 for prev in selected_springs):
                selected_springs.append(sc)
                if len(selected_springs) >= 8:
                    break

        river_paths = []
        step_len = 0.015

        for sx, sy, _ in selected_springs:
            path = [(sx, sy)]
            cur_x, cur_y = sx, sy
            vel_x, vel_y = 0.0, 0.0
            reached_water = False

            for _ in range(160):
                h_c = self.get_continuous_height(cur_x, cur_y)
                if h_c <= 0.005:
                    reached_water = True
                    break

                best_dir = None
                best_dh = 0.0

                # 16-point directional downhill check (H_cand < H_c)
                for a_idx in range(16):
                    ang = a_idx * (2.0 * math.pi / 16.0)
                    dx = math.cos(ang)
                    dy = math.sin(ang)
                    c_x = cur_x + dx * step_len
                    c_y = cur_y + dy * step_len
                    h_cand = self.get_continuous_height(c_x, c_y)
                    dh = h_c - h_cand
                    if dh > 0.0001:
                        score = dh
                        if vel_x != 0.0 or vel_y != 0.0:
                            score += max(0.0, dx * vel_x + dy * vel_y) * 0.002
                        if score > best_dh:
                            best_dh = score
                            best_dir = (dx, dy)

                if best_dir is None:
                    # Depression / sink reached (inland lake)
                    if len(path) >= 6:
                        reached_water = True
                    break

                target_vx, target_vy = best_dir
                if vel_x == 0.0 and vel_y == 0.0:
                    vel_x, vel_y = target_vx, target_vy
                else:
                    vel_x = vel_x * 0.35 + target_vx * 0.65
                    vel_y = vel_y * 0.35 + target_vy * 0.65
                    v_len = math.sqrt(vel_x**2 + vel_y**2) + 1e-6
                    vel_x /= v_len
                    vel_y /= v_len

                cur_x += vel_x * step_len
                cur_y += vel_y * step_len
                path.append((cur_x, cur_y))

            if reached_water and len(path) >= 6:
                river_paths.append(path)
                if len(river_paths) >= 5:
                    break

        return river_paths

    @staticmethod
    def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple[int, int, int]:
        t = max(0.0, min(1.0, t))
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )


def apply_heightmap_to_world(tiles: list, seed: int = 42, grid_rows: int = 9, grid_cols: int = 9) -> HeightMapGenerator:
    """Generate and attach elevation, biomes, and terrain heights to all world tiles.
    
    Guarantees that all land tiles (elevation >= 0.0) form ONE SINGLE connected component.
    """
    generator = HeightMapGenerator(seed=seed, grid_rows=grid_rows, grid_cols=grid_cols)
    layout = rectangular_hex_layout(grid_rows, grid_cols)
    
    # 1. Compute raw elevations
    for tile in tiles:
        if tile.name.startswith('r') and 'c' in tile.name:
            parts = tile.name[1:].split('c')
            r, c = int(parts[0]), int(parts[1])
        else:
            r, c = 0, 0

        h = generator.get_raw_height(r, c)
        tile.elevation = h
        tile.grid_r = r
        tile.grid_c = c

    # 2. Enforce single continuous connected landmass
    # Find all land cells
    land_cells = {(t.grid_r, t.grid_c) for t in tiles if t.elevation >= 0.0}
    
    # If center cell is not land, elevate center
    center = (grid_rows // 2, grid_cols // 2)
    center_tile = next((t for t in tiles if (t.grid_r, t.grid_c) == center), None)
    if center_tile and center_tile.elevation < 0.1:
        center_tile.elevation = 0.35
        land_cells.add(center)

    # Find connected components of land cells
    visited = set()
    components = []
    
    for cell in land_cells:
        if cell in visited:
            continue
        comp = set()
        queue = deque([cell])
        visited.add(cell)
        while queue:
            curr = queue.popleft()
            comp.add(curr)
            cr, cc = curr
            q, axr = layout[f"r{cr}c{cc}"]
            for nq, nar in axial_neighbors(q, axr):
                nc, nr = axial_to_offset(nq, nar)
                n_key = (nr, nc)
                if n_key in land_cells and n_key not in visited:
                    visited.add(n_key)
                    queue.append(n_key)
        components.append(comp)

    # Main component is the largest one containing the center
    components.sort(key=lambda c: (center in c, len(c)), reverse=True)
    main_continent = components[0] if components else set()

    # Submerge any disconnected small islands so the landmass is 100% continuous
    for tile in tiles:
        key = (tile.grid_r, tile.grid_c)
        if key not in main_continent:
            tile.elevation = min(-0.15, tile.elevation if tile.elevation < 0 else -0.15)
            tile.is_ocean = True
            tile.wilderness_pop = 0
        else:
            tile.is_ocean = False

    # 2b. Enforce that mountain regions (elevation >= 0.72 or biome in ('mountains', 'snow_peaks'))
    # strictly do not exceed 20% of the total land tiles
    land_tiles = [t for t in tiles if not getattr(t, 'is_ocean', False) and t.elevation >= 0.0]
    if land_tiles:
        max_mountains = max(1, int(len(land_tiles) * 0.20))
        sorted_land = sorted(land_tiles, key=lambda t: t.elevation, reverse=True)
        n_snow = max(1, max_mountains // 3)
        for i, t in enumerate(sorted_land):
            if i < max_mountains:
                if t.elevation >= 0.72:
                    if i < n_snow:
                        t.elevation = max(0.88, t.elevation)
                    else:
                        t.elevation = min(0.87, max(0.72, t.elevation))
            else:
                if t.elevation >= 0.72:
                    # Smoothly map excess elevation into high rolling hills [0.55, 0.70]
                    t.elevation = min(0.70, max(0.55, 0.70 - (t.elevation - 0.72) * 0.25))

    for tile in tiles:
        tile.elevation_meters = generator.get_elevation_meters(tile.elevation)
        tile.biome = generator.get_biome(tile.elevation)

    # 3. Calculate slope and shaded relief hillshading
    tile_map = {t.name: t for t in tiles}
    sun_dir = (-0.707, -0.707)  # Northwest sunlight

    for tile in tiles:
        r, c = getattr(tile, 'grid_r', 0), getattr(tile, 'grid_c', 0)
        h = getattr(tile, 'elevation', 0.0)

        left = tile_map.get(f"r{r}c{max(0, c-1)}")
        right = tile_map.get(f"r{r}c{min(grid_cols-1, c+1)}")
        up = tile_map.get(f"r{max(0, r-1)}c{c}")
        down = tile_map.get(f"r{min(grid_rows-1, r+1)}c{c}")

        dx = (getattr(right, 'elevation', h) - getattr(left, 'elevation', h)) * 0.5
        dy = (getattr(down, 'elevation', h) - getattr(up, 'elevation', h)) * 0.5

        slope_illum = -(dx * sun_dir[0] + dy * sun_dir[1])
        hillshade = 1.0 + slope_illum * 0.45
        tile.hillshade = max(0.65, min(1.35, hillshade))

        base_c = generator.get_base_color(h)
        shaded_c = (
            min(255, max(0, int(base_c[0] * tile.hillshade))),
            min(255, max(0, int(base_c[1] * tile.hillshade))),
            min(255, max(0, int(base_c[2] * tile.hillshade))),
        )
        tile.terrain_color = shaded_c

    return generator
def sample_terrain_to_tiles(tiles, layout, bbox, H, snow_weight, m_weight, hill_ridge, hillw, canopy_a, mount_range_mask, is_ocean_water, width, height, generator=None):
    """Sample synthesized terrain fields across hex footprints to align tile elevations and biomes precisely with the visual terrain map."""
    if not tiles or not layout:
        return

    HEX_SIZE = 50
    x0, y0, x1, y1 = bbox
    pad_x = (x1 - x0) * 0.18
    pad_y = (y1 - y0) * 0.18
    min_wx = x0 - pad_x
    max_wx = x1 + pad_x
    min_wy = y0 - pad_y
    max_wy = y1 + pad_y

    sample_angles = [i * math.pi / 3.0 for i in range(6)]
    tile_samples = {}

    m_w_2d = m_weight.squeeze() if m_weight.ndim == 3 else m_weight
    c_a_2d = canopy_a.squeeze() if canopy_a.ndim == 3 else canopy_a

    for t in tiles:
        coords = layout.get(t.name)
        if coords is None:
            continue
        q, r = coords
        cx, cy = axial_to_pixel(q, r, HEX_SIZE)
        pts = [(cx, cy)]
        for a in sample_angles:
            pts.append((cx + 0.45 * HEX_SIZE * math.cos(a), cy + 0.45 * HEX_SIZE * math.sin(a)))
        for a in sample_angles:
            pts.append((cx + 0.75 * HEX_SIZE * math.cos(a + math.pi / 6.0), cy + 0.75 * HEX_SIZE * math.sin(a + math.pi / 6.0)))

        px_coords = []
        for wx, wy in pts:
            px = int(np.clip(round((wx - min_wx) / (max_wx - min_wx) * (width - 1)), 0, width - 1))
            py = int(np.clip(round((wy - min_wy) / (max_wy - min_wy) * (height - 1)), 0, height - 1))
            px_coords.append((py, px))

        py_arr = [p[0] for p in px_coords]
        px_arr = [p[1] for p in px_coords]

        h_vals = H[py_arr, px_arr]
        snow_vals = snow_weight[py_arr, px_arr]
        rock_vals = m_w_2d[py_arr, px_arr]
        hill_vals = hill_ridge[py_arr, px_arr]
        hillw_vals = hillw[py_arr, px_arr]
        forest_vals = c_a_2d[py_arr, px_arr]
        ocean_vals = is_ocean_water[py_arr, px_arr]
        mount_vals = mount_range_mask[py_arr, px_arr]

        # Mountain coverage across the tile footprint
        is_mt = (mount_vals >= 0.12) | ((rock_vals >= 0.28) & (h_vals >= 0.35)) | (snow_vals >= 0.08) | (h_vals >= 0.48)
        mt_cov = float(np.mean(is_mt))

        tile_samples[t.name] = {
            'mean_h': float(np.mean(h_vals)),
            'max_h': float(np.max(h_vals)),
            'mean_snow': float(np.mean(snow_vals)),
            'max_snow': float(np.max(snow_vals)),
            'mean_rock': float(np.mean(rock_vals)),
            'mean_hill': float(np.mean(hill_vals)),
            'mean_hillw': float(np.mean(hillw_vals)),
            'mean_forest': float(np.mean(forest_vals)),
            'ocean_frac': float(np.mean(ocean_vals)),
            'mean_mount': float(np.mean(mount_vals)),
            'mountain_coverage': mt_cov,
        }

    # Respect single continuous connected landmass from original connectivity
    land_tiles = [t for t in tiles if not getattr(t, 'is_ocean', False) and t.name in tile_samples]
    if not land_tiles:
        return

    for t in tiles:
        if t.name not in tile_samples:
            continue
        s = tile_samples[t.name]
        if getattr(t, 'is_ocean', False):
            if s['mean_h'] < -0.30:
                t.biome = 'deep_ocean'
            else:
                t.biome = 'shallow_ocean'
            t.elevation = min(-0.15, s['mean_h'])
        elif s['mountain_coverage'] >= 0.30:
            # If mountains cover more than 30% of the tile -> mountain tile
            if s['mean_snow'] >= 0.18 or (s['mean_snow'] >= 0.08 and s['max_h'] >= 1.00):
                t.biome = 'snow_peaks'
                t.elevation = max(0.88, min(1.00, 0.88 + s['mean_snow'] * 0.12))
            else:
                t.biome = 'mountains'
                t.elevation = max(0.72, min(0.87, 0.72 + s['mean_rock'] * 0.15))
        else:
            if s['mean_forest'] >= 0.35 and s['mean_hill'] < 0.12:
                t.biome = 'forest'
                t.elevation = max(0.22, min(0.47, 0.22 + s['mean_h'] * 0.25))
            elif s['mean_hill'] >= 0.10 or (s['mean_hillw'] >= 0.25 and s['mean_h'] >= 0.30):
                t.biome = 'hills'
                t.elevation = max(0.48, min(0.70, 0.48 + s['mean_h'] * 0.22))
            elif s['mean_forest'] >= 0.25:
                t.biome = 'forest'
                t.elevation = max(0.22, min(0.47, 0.22 + s['mean_h'] * 0.25))
            else:
                t.biome = 'plains'
                t.elevation = max(0.02, min(0.21, s['mean_h']))

        if generator is not None:
            t.elevation_meters = generator.get_elevation_meters(t.elevation)
            base_c = generator.get_base_color(t.elevation)
            hillshade = getattr(t, 'hillshade', 1.0)
            t.terrain_color = (
                min(255, max(0, int(base_c[0] * hillshade))),
                min(255, max(0, int(base_c[1] * hillshade))),
                min(255, max(0, int(base_c[2] * hillshade))),
            )


HeightMapGenerator.generate_topographic_surface = _generate_topographic_surface_impl

