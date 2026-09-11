"""
heightmap.py — Realistic Continuous Landmass, Elevation, and Biomes for REGNUM.

Generates a continuous, single-component continental landmass where all nations
and land tiles connect seamlessly, surrounded by deep and shallow ocean basins:
- Below Sea Level (< 0.0): Deep & Shallow Ocean
- Lowlands & Plains (0.0 to 0.22)
- Highland Forests (0.22 to 0.48)
- Rolling Hills (0.48 to 0.70)
- High Rocky Mountains (0.70 to 0.88)
- Glacial Snow-Capped Alpine Peaks (>= 0.88)

Ensures that the entire landmass is ONE continuous chunk (1 connected component).
"""

import math
import random
from collections import deque
from hexmap import rectangular_hex_layout, axial_neighbors, axial_to_offset, axial_to_pixel, HEX_DIRS, _SQRT3


import numpy as np


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
        for i, t in enumerate(sorted_land):
            if i >= max_mountains and t.elevation >= 0.72:
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
_TOPOGRAPHIC_SURFACE_CACHE = {}


def get_cached_topographic_surface(seed, bbox, tiles=None, layout=None, canvas_w=2400, canvas_h=1800, progress_callback=None):
    """Return pre-rendered, 4x Ultra-HD topographic elevation surface conforming closely to the hex tile map."""
    tile_sig = tuple((t.name, round(getattr(t, 'elevation', 0.0), 3), bool(getattr(t, 'is_ocean', False))) for t in tiles) if tiles else None
    cache_key = (seed, bbox, canvas_w, canvas_h, tile_sig)
    if cache_key in _TOPOGRAPHIC_SURFACE_CACHE:
        return _TOPOGRAPHIC_SURFACE_CACHE[cache_key]

    generator = HeightMapGenerator(seed=seed if seed is not None else 42)
    surf = generator.generate_topographic_surface(bbox, tiles=tiles, layout=layout, width=canvas_w, height=canvas_h, progress_callback=progress_callback)
    _TOPOGRAPHIC_SURFACE_CACHE[cache_key] = surf
    return surf
def _generate_topographic_surface_impl(generator, bbox, tiles=None, layout=None, width: int = 2400, height: int = 1800, progress_callback=None) -> "pygame.Surface":
    """Render an Ultra-HD photorealistic 3D raymarched terrain surface with full-strength derivative erosion fractals conforming to the hex tile map."""
    import pygame
    import numpy as np
    import random

    HEX_SIZE = 50

    if layout is None:
        layout = rectangular_hex_layout(generator.grid_rows, generator.grid_cols)

    tile_dict = {}
    mountain_centers = []

    if tiles is not None:
        for t in tiles:
            coords = layout.get(t.name)
            if coords is not None:
                q, r = coords
                cx, cy = axial_to_pixel(q, r, HEX_SIZE)
                is_ocean = getattr(t, 'is_ocean', False)
                elev = getattr(t, 'elevation', 0.0)
                biome = getattr(t, 'biome', 'plains')
                tile_dict[(q, r)] = (float(elev), is_ocean, (cx, cy), biome)
                if not is_ocean and (elev >= 0.65 or biome in ('mountains', 'snow_peaks')):
                    mountain_centers.append((cx, cy))
    else:
        for name, (q, r) in layout.items():
            h = generator.get_continuous_height(
                (q - (generator.grid_cols - 1) / 2.0) / (generator.grid_cols / 2.0),
                (r - (generator.grid_rows - 1) / 2.0) / (generator.grid_rows / 2.0)
            )
            cx, cy = axial_to_pixel(q, r, HEX_SIZE)
            is_ocean = h < 0.0
            biome = generator.get_biome(h)
            tile_dict[(q, r)] = (h, is_ocean, (cx, cy), biome)
            if not is_ocean and h >= 0.65:
                mountain_centers.append((cx, cy))

    x0, y0, x1, y1 = bbox
    pad_x = (x1 - x0) * 0.18
    pad_y = (y1 - y0) * 0.18
    min_wx = x0 - pad_x
    max_wx = x1 + pad_x
    min_wy = y0 - pad_y
    max_wy = y1 + pad_y

    span_x = (x1 - x0) / 2.0
    span_y = (y1 - y0) / 2.0
    cx_center = (x0 + x1) / 2.0
    cy_center = (y0 + y1) / 2.0

    y_vals = np.linspace(min_wy, max_wy, height, dtype=np.float32)
    x_vals = np.linspace(min_wx, max_wx, width, dtype=np.float32)
    WX, WY = np.meshgrid(x_vals, y_vals)

    NX = (WX - cx_center) / span_x
    NY = (WY - cy_center) / span_y

    if progress_callback:
        progress_callback(0.05, "Synthesizing hexagonal plate tectonics & grid...")
    # 1. 7-Octave Inigo Quilez Derivative Erosion fBm (eliminates noisy 1-pixel grain)
    scale = 3.0
    PX = NX * scale
    PY = NY * scale

    a = np.zeros_like(NX, dtype=np.float32)
    b = 1.0
    dx_accum = np.zeros_like(NX, dtype=np.float32)
    dy_accum = np.zeros_like(NY, dtype=np.float32)
    noise_tbl = generator.noise_table
    m2 = generator.m2

    for i in range(7):
        ix = np.floor(PX).astype(np.int32)
        iy = np.floor(PY).astype(np.int32)
        fx = PX - ix
        fy = PY - iy

        ux = fx * fx * (3.0 - 2.0 * fx)
        uy = fy * fy * (3.0 - 2.0 * fy)
        dux = 6.0 * fx * (1.0 - fx)
        duy = 6.0 * fy * (1.0 - fy)

        ix0 = ix & 255
        iy0 = iy & 255
        ix1 = (ix + 1) & 255
        iy1 = (iy + 1) & 255

        c_a = noise_tbl[iy0, ix0]
        c_b = noise_tbl[iy0, ix1]
        c_c = noise_tbl[iy1, ix0]
        c_d = noise_tbl[iy1, ix1]

        k0 = c_a
        k1 = c_b - c_a
        k2 = c_c - c_a
        k3 = c_a - c_b - c_c + c_d

        n_val = k0 + k1 * ux + k2 * uy + k3 * ux * uy
        ndx = dux * (k1 + k3 * uy)
        ndy = duy * (k2 + k3 * ux)

        dx_accum += ndx
        dy_accum += ndy

        erosion_term = 1.0 + (dx_accum**2 + dy_accum**2) * 0.75
        a += b * n_val / erosion_term

        b *= 0.50
        npx = 2.0 * (m2[0, 0] * PX + m2[0, 1] * PY)
        npy = 2.0 * (m2[1, 0] * PX + m2[1, 1] * PY)
        PX, PY = npx, npy

    H_noise = (a - 0.85) * 0.70

    # 2. Hex Conformation & True Biome Fields
    warp_amp = HEX_SIZE * 0.12
    XW = WX + dx_accum * 0.20 * warp_amp
    YW = WY + dy_accum * 0.20 * warp_amp

    q_frac = (_SQRT3 / 3.0 * XW - 1.0 / 3.0 * YW) / HEX_SIZE
    r_frac = (2.0 / 3.0 * YW) / HEX_SIZE
    x_cube = q_frac
    y_cube = r_frac
    z_cube = -q_frac - r_frac
    rx = np.round(x_cube).astype(np.int32)
    ry = np.round(y_cube).astype(np.int32)
    rz = np.round(z_cube).astype(np.int32)
    dx = np.abs(rx - x_cube)
    dy = np.abs(ry - y_cube)
    dz = np.abs(rz - z_cube)
    mask_x = (dx > dy) & (dx > dz)
    mask_y = (~mask_x) & (dy > dz)
    q_near = np.where(mask_x, -ry - rz, rx)
    r_near = np.where(mask_y, -rx - rz, ry)

    all_dirs = ((0, 0),) + HEX_DIRS
    all_qs = [q for q, r in tile_dict.keys()]
    all_rs = [r for q, r in tile_dict.keys()]
    min_q, max_q = min(all_qs) - 2, max(all_qs) + 2
    min_r, max_r = min(all_rs) - 2, max(all_rs) + 2
    q_size = max_q - min_q + 1
    r_size = max_r - min_r + 1

    grid_land = np.zeros((r_size, q_size), dtype=np.float32)
    grid_forest = np.zeros((r_size, q_size), dtype=np.float32)
    grid_mountain = np.zeros((r_size, q_size), dtype=np.float32)
    grid_snow = np.zeros((r_size, q_size), dtype=np.float32)
    grid_hills = np.zeros((r_size, q_size), dtype=np.float32)

    for (q, r), (elev, is_ocean, _, biome) in tile_dict.items():
        if not is_ocean:
            grid_land[r - min_r, q - min_q] = 1.0
            if biome == 'forest':
                grid_forest[r - min_r, q - min_q] = 1.0
            elif biome in ('mountains', 'snow_peaks') or elev >= 0.65:
                grid_mountain[r - min_r, q - min_q] = 1.0
                if biome == 'snow_peaks':
                    grid_snow[r - min_r, q - min_q] = 1.0
            elif biome == 'hills':
                grid_hills[r - min_r, q - min_q] = 1.0

    H_land_sum = np.zeros_like(WX, dtype=np.float32)
    H_forest_sum = np.zeros_like(WX, dtype=np.float32)
    H_mount_sum = np.zeros_like(WX, dtype=np.float32)
    H_snow_sum = np.zeros_like(WX, dtype=np.float32)
    H_hills_sum = np.zeros_like(WX, dtype=np.float32)
    W_total = np.zeros_like(WX, dtype=np.float32)

    R_blend = HEX_SIZE * 2.2
    R2 = R_blend * R_blend

    for dq, dr in all_dirs:
        qc = q_near + dq
        rc = r_near + dr
        qc_clamped = np.clip(qc - min_q, 0, q_size - 1)
        rc_clamped = np.clip(rc - min_r, 0, r_size - 1)
        in_bounds = (qc >= min_q) & (qc <= max_q) & (rc >= min_r) & (rc <= max_r)

        l_cand = np.where(in_bounds, grid_land[rc_clamped, qc_clamped], 0.0)
        f_cand = np.where(in_bounds, grid_forest[rc_clamped, qc_clamped], 0.0)
        m_cand = np.where(in_bounds, grid_mountain[rc_clamped, qc_clamped], 0.0)
        s_cand = np.where(in_bounds, grid_snow[rc_clamped, qc_clamped], 0.0)
        h_cand = np.where(in_bounds, grid_hills[rc_clamped, qc_clamped], 0.0)

        cx_cand = HEX_SIZE * _SQRT3 * (qc + rc / 2.0)
        cy_cand = HEX_SIZE * 1.5 * rc
        d2 = (XW - cx_cand)**2 + (YW - cy_cand)**2

        w = np.maximum(0.0, 1.0 - (d2 / R2))**2.5
        H_land_sum += w * l_cand
        H_forest_sum += w * f_cand
        H_mount_sum += w * m_cand
        H_snow_sum += w * s_cand
        H_hills_sum += w * h_cand
        W_total += w

    H_land_prob = H_land_sum / (W_total + 1e-6)
    H_forest_prob = H_forest_sum / (W_total + 1e-6)
    H_mount_prob = H_mount_sum / (W_total + 1e-6)
    H_snow_prob = H_snow_sum / (W_total + 1e-6)
    H_hills_prob = H_hills_sum / (W_total + 1e-6)

    if progress_callback:
        progress_callback(0.20, "Synthesizing multi-fractal mountain massifs & relief...")
    # 3. Inigo Quilez Multi-Fractal & Domain Warping Machinery
    def iq_noised(px_arr, py_arr):
        ix = np.floor(px_arr).astype(np.int32)
        iy = np.floor(py_arr).astype(np.int32)
        fx = px_arr - ix
        fy = py_arr - iy
        ux = fx * fx * (3.0 - 2.0 * fx)
        uy = fy * fy * (3.0 - 2.0 * fy)
        dux = 6.0 * fx * (1.0 - fx)
        duy = 6.0 * fy * (1.0 - fy)
        ix0 = ix & 255
        iy0 = iy & 255
        ix1 = (ix + 1) & 255
        iy1 = (iy + 1) & 255
        c_a = noise_tbl[iy0, ix0]
        c_b = noise_tbl[iy0, ix1]
        c_c = noise_tbl[iy1, ix0]
        c_d = noise_tbl[iy1, ix1]
        k0 = c_a
        k1 = c_b - c_a
        k2 = c_c - c_a
        k3 = c_a - c_b - c_c + c_d
        val = k0 + k1 * ux + k2 * uy + k3 * ux * uy
        dx = dux * (k1 + k3 * uy)
        dy = duy * (k2 + k3 * ux)
        return val, dx, dy

    # Domain warp for organic geological patterns
    warp_scale = 1.0 / (HEX_SIZE * 3.5)
    qw_val, qw_dx, qw_dy = iq_noised(WX * warp_scale, WY * warp_scale)
    rw_val, rw_dx, rw_dy = iq_noised((WX + 120.0) * warp_scale + qw_dx * 0.5, (WY - 80.0) * warp_scale + qw_dy * 0.5)
    
    WX_warped = WX + (qw_dx * 0.4 + rw_dx * 0.6) * (HEX_SIZE * 0.4)
    WY_warped = WY + (qw_dy * 0.4 + rw_dy * 0.6) * (HEX_SIZE * 0.4)

    # IQ Ridged Mountain Multi-Fractal (Natural rugged jagged spines and eroded valleys)
    mount_px = WX_warped / (HEX_SIZE * 2.2)
    mount_py = WY_warped / (HEX_SIZE * 2.2)
    
    mount_relief = np.zeros_like(WX, dtype=np.float32)
    mount_amp = 1.0
    mount_freq = 1.0
    m_dx_accum = np.zeros_like(WX, dtype=np.float32)
    m_dy_accum = np.zeros_like(WY, dtype=np.float32)

    for oct_idx in range(6):
        n_val, ndx, ndy = iq_noised(mount_px * mount_freq, mount_py * mount_freq)
        ridge = 1.0 - np.abs(2.0 * n_val - 1.0)
        ridge = ridge * ridge
        m_dx_accum += ndx * mount_freq
        m_dy_accum += ndy * mount_freq
        erosion = 1.0 + (m_dx_accum**2 + m_dy_accum**2) * 0.35
        mount_relief += mount_amp * (ridge / erosion)
        mount_amp *= 0.52
        mount_freq *= 2.05

    mount_relief = (mount_relief - 0.45) * 1.35
    mount_relief = np.maximum(0.0, mount_relief)

    # Plains Multi-Scale Micro-Details (IQ multi-octave turf, meadow swells, micro-creeks)
    plains_px = WX_warped / (HEX_SIZE * 0.5)
    plains_py = WY_warped / (HEX_SIZE * 0.5)
    plains_fbm = np.zeros_like(WX, dtype=np.float32)
    p_amp = 0.5
    p_freq = 1.0
    for _ in range(6):
        p_val, _, _ = iq_noised(plains_px * p_freq, plains_py * p_freq)
        plains_fbm += p_amp * p_val
        p_amp *= 0.5
        p_freq *= 2.15

    # Subtle micro-relief for plains (organic rolling turf and fine grass texture)
    plains_details = (plains_fbm - 0.50) * 0.035

    # Coastal shelf + bathymetry are built below, after the hill/mountain
    # relief -- they need the coastal gradient of that relief.  See "COAST".

    # Hills: Gentle rolling multi-octave mounds
    hill_fbm, _, _ = iq_noised(WX_warped / (HEX_SIZE * 1.8), WY_warped / (HEX_SIZE * 1.8))
    hill_ridge = H_hills_prob * (0.26 + 0.14 * hill_fbm)

    # Mountains: Continuous alpine ranges with natural IQ ridged fractal relief
    mount_range_mask = np.clip(H_mount_prob * 1.5 + H_snow_prob * 0.6, 0.0, 1.0) ** 0.85
    mountain_ridge = mount_range_mask * (0.16 + 0.88 * mount_relief)

    # -------------------------------------------------------------------
    # COAST -- shelf + bathymetry.  The near-shore heightfield is ONE
    # C1-continuous function of the blurred land-occupancy field
    # `H_land_prob`: a shelving ramp above the water line, spliced by
    # smoothstep into a real sea floor below it.  Both the above-water
    # climb-rate and the sub-sea plunge-rate scale with `coast_steep` (a
    # blurred gradient magnitude of the hill+mountain relief, windowed to
    # the near-shore band), so a cliff coast rises then plunges fast --
    # thin beach, narrow turquoise shelf -- while a plains coast shelves
    # out shallow and wide.  The sea floor carries the ridged multifractal
    # + plains fBm so it has structure, faded in offshore so the water
    # line itself stays smooth.  No np.where band step -> no dark contour.
    from scipy.ndimage import gaussian_filter as _gf
    shore_ref = 0.30

    _rp = hill_ridge + mountain_ridge
    _gpx = np.gradient(_rp, axis=1)
    _gpy = np.gradient(_rp, axis=0)
    coast_steep = _gf(np.sqrt(_gpx * _gpx + _gpy * _gpy), sigma=HEX_SIZE * 0.7)
    coast_steep = np.clip(coast_steep / 0.010, 0.0, 1.0) ** 0.75

    # near-shore window: 1 at the water line, 0 by the time we are well inland
    # (keeps the steepening from inflating interior hills / mountains).
    _near = np.clip(1.0 - (H_land_prob - shore_ref) / 0.20, 0.0, 1.0)
    _t_up = np.clip((H_land_prob - shore_ref) / 0.17, 0.0, 1.0)
    _above_rate = 0.075 + 0.85 * coast_steep * _near
    land_shelf_above = _above_rate * (_t_up ** 1.3) + np.clip(H_land_prob - 0.46, 0.0, 1.0) * 0.04

    _off = np.clip(shore_ref - H_land_prob, 0.0, shore_ref)   # 0 at water line, grows seaward
    _plunge = 0.85 + 6.5 * coast_steep
    seabed_dc = -(_off * _plunge + _off * _off * 3.5 * (0.2 + coast_steep))
    seabed_struct = ((mount_relief * 0.10 + (plains_fbm - 0.5) * 0.11)
                     * np.clip(_off * 6.0, 0.0, 1.0)
                     * (0.35 + 0.65 * coast_steep))
    seabed_H = seabed_dc + seabed_struct

    _wsea = np.clip((shore_ref + 0.012 - H_land_prob) / 0.042, 0.0, 1.0)
    _wsea = _wsea * _wsea * (3.0 - 2.0 * _wsea)
    land_shelf = land_shelf_above * (1.0 - _wsea) + seabed_H * _wsea

    # Base Ground Elevation
    base_ground_H = land_shelf + hill_ridge + mountain_ridge + plains_details * (1.0 - mount_range_mask)

    # Alpine Treeline: Trees do not climb high into the mountain peaks
    # Below elevation 0.20 and mountain mask 0.15: 100% full tree density
    # Above elevation 0.36 or mountain mask 0.35: 0% trees (rocky alpine peaks & cliffs)
    elev_treeline = np.clip(1.0 - (base_ground_H - 0.20) / 0.16, 0.0, 1.0)
    mount_treeline = np.clip(1.0 - mount_range_mask * 2.2, 0.0, 1.0)
    treeline_factor = elev_treeline * mount_treeline

    # -------------------------------------------------------------
    # Procedural Hydraulic Valley Carving & Depression-Flooded Lakes
    # -------------------------------------------------------------
    if progress_callback:
        progress_callback(0.38, "Tracing hydraulic river descents & mountain springs...")
    spring_candidates = []
    if mountain_centers:
        for cx, cy in mountain_centers:
            px = int(round((cx - min_wx) / (max_wx - min_wx) * (width - 1)))
            py = int(round((cy - min_wy) / (max_wy - min_wy) * (height - 1)))
            if 4 <= px < width - 4 and 4 <= py < height - 4:
                spring_candidates.append((cx, cy, base_ground_H[py, px]))

    if tiles is not None:
        for t in tiles:
            if getattr(t, 'elevation', 0.0) >= 0.50 and not getattr(t, 'is_ocean', False):
                coords = layout.get(t.name)
                if coords is not None:
                    q, r = coords
                    cx, cy = axial_to_pixel(q, r, HEX_SIZE)
                    px = int(round((cx - min_wx) / (max_wx - min_wx) * (width - 1)))
                    py = int(round((cy - min_wy) / (max_wy - min_wy) * (height - 1)))
                    if 4 <= px < width - 4 and 4 <= py < height - 4:
                        spring_candidates.append((cx, cy, base_ground_H[py, px]))
    else:
        sample_ny = np.linspace(-0.80, 0.80, 30)
        sample_nx = np.linspace(-0.80, 0.80, 30)
        for s_ny in sample_ny:
            for s_nx in sample_nx:
                px_c = float(s_nx * span_x + cx_center)
                py_c = float(s_ny * span_y + cy_center)
                px = int(round((px_c - min_wx) / (max_wx - min_wx) * (width - 1)))
                py = int(round((py_c - min_wy) / (max_wy - min_wy) * (height - 1)))
                if 4 <= px < width - 4 and 4 <= py < height - 4:
                    h_val = base_ground_H[py, px]
                    if 0.45 <= h_val <= 0.85:
                        spring_candidates.append((px_c, py_c, h_val))

    rng_riv = random.Random(generator.seed + 999)
    rng_riv.shuffle(spring_candidates)

    selected_springs = []
    for sc in spring_candidates:
        if all((sc[0] - prev[0])**2 + (sc[1] - prev[1])**2 > (HEX_SIZE * 1.6)**2 for prev in selected_springs):
            selected_springs.append(sc)
            if len(selected_springs) >= 8:
                break

    carved_ground_H = base_ground_H.copy()
    water_surface_H = np.full((height, width), -999.0, dtype=np.float32)
    is_lake_water = np.zeros((height, width), dtype=bool)

    # v11: horizontal distance (px) from every pixel to the nearest open-sea
    # pixel, for river-mouth classification.  The two lowland "push toward the
    # sea" fallbacks in the tracer set `reached_ocean=True` even for a trace
    # merely stuck in a pit or a loop, and the v10 test then keyed only on
    # terminus ELEVATION (`end_ground <= 0.12`) -- a low inland hollow passed,
    # so an inland terminus got the ocean coast-blend AND the estuary fan ~45 px
    # from any coast (the seed-12345 bulbous head).  A true ocean mouth is now
    # one whose terminus sits within a few px of open water (deadends.md).  One
    # EDT on the same ocean mask `_sea` uses below -- constant cost.
    _ocean_edt_mask = H_land_prob < shore_ref
    if _ocean_edt_mask.any() and (~_ocean_edt_mask).any():
        from scipy.ndimage import distance_transform_edt as _edt_sea
        sea_dist_px = _edt_sea(~_ocean_edt_mask).astype(np.float32)
    else:
        sea_dist_px = np.full((height, width), 1e9, dtype=np.float32)
    MOUTH_SEA_DIST = 16.0   # px; a genuine mouth terminates at H_land_prob ~ 0.32
                            # (a few px inside this mask); inland stubs stop 30+ px off.

    # v10: rivers are carved into the heightfield BEFORE normals via a global
    # distance-to-channel field (built after this loop).  Here we only TRACE
    # each spring downhill to a polyline and stash a 1-D water-level /
    # accumulated-flow / distance-to-mouth profile along it.
    step_dist = 6.0
    river_polylines = []
    valid_rivers_count = 0

    for sx, sy, _ in selected_springs:
        cur_x, cur_y = sx, sy
        px_0 = int(round((cur_x - min_wx) / (max_wx - min_wx) * (width - 1)))
        py_0 = int(round((cur_y - min_wy) / (max_wy - min_wy) * (height - 1)))
        pts = [(cur_x, cur_y, px_0, py_0, base_ground_H[py_0, px_0])]
        vel_x, vel_y = 0.0, 0.0
        visited_pts = {(px_0 // 6, py_0 // 6)}

        step_dist = 6.0
        reached_ocean = False
        reached_lake = False
        pit_point = None

        for _ in range(250):
            px_i = int(round((cur_x - min_wx) / (max_wx - min_wx) * (width - 1)))
            py_i = int(round((cur_y - min_wy) / (max_wy - min_wy) * (height - 1)))

            if not (4 <= px_i < width - 4 and 4 <= py_i < height - 4):
                break

            h_now = base_ground_H[py_i, px_i]

            # TERMINATE PRECISELY AT OCEAN LEVEL (No pushing into ocean)
            if h_now <= 0.005 or H_land_prob[py_i, px_i] < 0.32:
                reached_ocean = True
                break

            best_dir = None
            best_score = -1e9

            out_x = (cur_x - cx_center) / span_x
            out_y = (cur_y - cy_center) / span_y
            out_len = math.sqrt(out_x**2 + out_y**2) + 1e-5
            out_x /= out_len
            out_y /= out_len

            num_angles = 16
            for a_idx in range(num_angles):
                ang = a_idx * (2.0 * math.pi / num_angles)
                dx = math.cos(ang)
                dy = math.sin(ang)

                cand_x = cur_x + dx * step_dist
                cand_y = cur_y + dy * step_dist
                c_px = int(round((cand_x - min_wx) / (max_wx - min_wx) * (width - 1)))
                c_py = int(round((cand_y - min_wy) / (max_wy - min_wy) * (height - 1)))

                if not (2 <= c_px < width - 2 and 2 <= c_py < height - 2):
                    continue

                cand_h = base_ground_H[c_py, c_px]
                dh = h_now - cand_h

                if dh > 0.0001:
                    score = dh * 10.0
                    if vel_x != 0.0 or vel_y != 0.0:
                        score += (dx * vel_x + dy * vel_y) * 0.005
                    score += (dx * out_x + dy * out_y) * 0.003
                    if score > best_score:
                        best_score = score
                        best_dir = (dx, dy, cand_h)

            # Bridge small flats by looking ahead towards ocean
            if best_dir is None:
                for a_idx in range(num_angles):
                    ang = a_idx * (2.0 * math.pi / num_angles)
                    dx = math.cos(ang)
                    dy = math.sin(ang)
                    cand_x = cur_x + dx * (step_dist * 3.0)
                    cand_y = cur_y + dy * (step_dist * 3.0)
                    c_px = int(round((cand_x - min_wx) / (max_wx - min_wx) * (width - 1)))
                    c_py = int(round((cand_y - min_wy) / (max_wy - min_wy) * (height - 1)))
                    if 2 <= c_px < width - 2 and 2 <= c_py < height - 2:
                        cand_h = base_ground_H[c_py, c_px]
                        if cand_h < h_now - 0.0002:
                            best_dir = (dx, dy, cand_h)
                            break

            # If still no downhill path: only form a lake if trapped in an actual
            # high mountain valley.  v10 fix: the old 0.16 gate let a short
            # lowland stub pool a round tarn at ~0.15-0.17 -- the "lollipop" head
            # on seed 12345.  Real alpine tarns sit far higher; a low pit just
            # terminates the river and it fades out (see the flow taper below).
            if best_dir is None:
                if len(pts) >= 8 and h_now >= 0.30:
                    reached_lake = True
                    pit_point = (px_i, py_i, h_now)
                elif len(pts) >= 8:
                    # In lowlands: push towards ocean to terminate at sea
                    reached_ocean = True
                break

            target_vx, target_vy, _ = best_dir
            if vel_x == 0.0 and vel_y == 0.0:
                vel_x, vel_y = target_vx, target_vy
            else:
                v_blend_x = vel_x * 0.35 + target_vx * 0.65
                v_blend_y = vel_y * 0.35 + target_vy * 0.65
                v_len = math.sqrt(v_blend_x**2 + v_blend_y**2) + 1e-6
                v_blend_x /= v_len
                v_blend_y /= v_len

                test_px = int(round((cur_x + v_blend_x * step_dist - min_wx) / (max_wx - min_wx) * (width - 1)))
                test_py = int(round((cur_y + v_blend_y * step_dist - min_wy) / (max_wy - min_wy) * (height - 1)))
                if 2 <= test_px < width - 2 and 2 <= test_py < height - 2 and base_ground_H[test_py, test_px] < h_now:
                    vel_x, vel_y = v_blend_x, v_blend_y
                else:
                    vel_x, vel_y = target_vx, target_vy

            cur_x += vel_x * step_dist
            cur_y += vel_y * step_dist
            p_pix_x = int(round((cur_x - min_wx) / (max_wx - min_wx) * (width - 1)))
            p_pix_y = int(round((cur_y - min_wy) / (max_wy - min_wy) * (height - 1)))
            grid_pt = (p_pix_x // 5, p_pix_y // 5)
            if grid_pt in visited_pts:
                if len(pts) >= 8 and h_now >= 0.30:
                    reached_lake = True
                    pit_point = (p_pix_x, p_pix_y, h_now)
                elif len(pts) >= 8:
                    reached_ocean = True
                break
            visited_pts.add(grid_pt)
            pts.append((cur_x, cur_y, p_pix_x, p_pix_y, base_ground_H[p_pix_y, p_pix_x]))

        # v10: accept the trace + derive its 1-D channel profile.  The carve and
        # the water surface are applied globally, after the loop.  A slightly
        # longer minimum length culls the shortest mid-slope stubs the tracer
        # sometimes leaves.
        if (reached_ocean or reached_lake) and len(pts) >= 12:
            valid_rivers_count += 1
            n_pts = len(pts)
            water_levels = np.array([pts[k][4] for k in range(n_pts)], dtype=np.float32)
            # v10 fix: `reached_ocean` is also set by the two lowland "push
            # toward the sea" fallbacks, for rivers whose trace actually stops
            # well above sea level.  Only a trace that ENDS at the water line is
            # a true ocean mouth; the rest must taper out inland, or they bloom
            # into a blunt radial disc off the global distance field (the
            # seed-12345 "lollipop").
            end_px_i = int(np.clip(pts[-1][2], 0, width - 1))
            end_py_i = int(np.clip(pts[-1][3], 0, height - 1))
            end_sea_dist = float(sea_dist_px[end_py_i, end_px_i])
            # v11: classify a mouth by HORIZONTAL proximity of the terminus to
            # open sea, not by height (deadends.md -- the elevation test was a
            # hair-trigger that a low inland hollow passed).  A trace failing
            # this keeps the flow taper below AND, via OCN=False, has the
            # estuary fan / mouth_zone / coast-blend suppressed, so it necks to
            # a thread and dies with no bulb.
            truly_ocean = bool(reached_ocean) and end_sea_dist <= MOUTH_SEA_DIST
            # strict downhill monotonicity, then blend the level toward ~0 over
            # the last few points so an ocean-bound channel meets the sea flush
            for k in range(1, n_pts):
                water_levels[k] = min(water_levels[k], water_levels[k - 1] - 0.0005)
            if truly_ocean:
                for k in range(n_pts):
                    t_coast = max(0.0, (k - (n_pts - 8)) / 8.0)
                    water_levels[k] = water_levels[k] * (1.0 - t_coast) + 0.002 * t_coast
            # accumulated downstream flow: 0 at the source, 1 at the mouth,
            # biased so the upper half stays a thin crease; a longer descent
            # carries proportionally more water at its mouth
            prog = np.arange(n_pts, dtype=np.float32) / max(1, n_pts - 1)
            length_scale = float(np.clip(n_pts / 45.0, 0.35, 1.0))
            flow = (prog ** 0.7) * length_scale
            # neck the flow (hence w_chan / v_reach / w_water) back toward ~0
            # over the last third of an inland-terminating trace so its end
            # fades to a thread instead of a blob.  True ocean mouths keep full
            # flow -- their width is handed off to the sea by shore_fade below.
            if not truly_ocean:
                taper_n = max(4, n_pts // 3)
                kk = np.arange(n_pts, dtype=np.float32)
                _tt = np.clip((kk - (n_pts - 1 - taper_n)) / float(taper_n), 0.0, 1.0)
                flow = flow * (1.0 - _tt * _tt * (3.0 - 2.0 * _tt))
            mouthdist = (n_pts - 1 - np.arange(n_pts, dtype=np.float32)) * step_dist
            river_polylines.append((pts, water_levels, flow, mouthdist, truly_ocean))

            # alpine tarn in a trapped mountain basin -- unchanged tight BFS flood
            if reached_lake and pit_point is not None:
                px_pit, py_pit, h_pit = pit_point
                H_lake = h_pit + 0.018
                from collections import deque
                q_bfs = deque([(py_pit, px_pit)])
                lake_submask = np.zeros((height, width), dtype=bool)
                lake_submask[py_pit, px_pit] = True
                # v10 fix: scale the tarn to the river feeding it -- a short
                # stub trace should pool a small pond, not a fixed 22 px disc
                # that dwarfs its own channel (the seed-12345 lollipop head).
                max_rad = HEX_SIZE * (0.18 + 0.30 * length_scale)
                while q_bfs:
                    cy_l, cx_l = q_bfs.popleft()
                    for dy_l, dx_l in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny_l, nx_l = cy_l + dy_l, cx_l + dx_l
                        if 0 <= ny_l < height and 0 <= nx_l < width and not lake_submask[ny_l, nx_l]:
                            dist = math.sqrt((nx_l - px_pit) ** 2 + (ny_l - py_pit) ** 2)
                            n_f, _, _ = iq_noised(nx_l / 14.0, ny_l / 14.0)
                            dist_warped = dist * (0.80 + 0.40 * n_f)
                            if dist_warped <= max_rad and carved_ground_H[ny_l, nx_l] <= H_lake + 0.002:
                                lake_submask[ny_l, nx_l] = True
                                q_bfs.append((ny_l, nx_l))
                is_lake_water |= lake_submask
                water_surface_H = np.where(lake_submask, H_lake, water_surface_H)
                carved_ground_H = np.where(lake_submask, np.minimum(carved_ground_H, H_lake - 0.008), carved_ground_H)

            if valid_rivers_count >= 6:
                break

    # --------------------------------------------------------------------
    # v10: rasterise every centreline into ONE label image (each centre
    # pixel carries its 1-D water-level / accumulated-flow / distance-to-
    # mouth), then a single Euclidean distance transform gives the global
    # distance-to-channel field `Dr` plus those quantities looked up at the
    # nearest centreline pixel.  No per-segment capsule stamps -> no beaded
    # sausage caps, one continuous field.
    # --------------------------------------------------------------------
    cl_mask = np.zeros((height, width), dtype=bool)
    cl_wl = np.zeros((height, width), dtype=np.float32)
    cl_flow = np.zeros((height, width), dtype=np.float32)
    cl_md = np.full((height, width), 1e9, dtype=np.float32)
    cl_ocn = np.zeros((height, width), dtype=bool)

    for pts, water_levels, flow, mouthdist, reached_ocean in river_polylines:
        n_pts = len(pts)
        # skip the first 1-3 "settling" points near the spring (the tracer often
        # wanders in place before it finds the exit -> a clustered, fat head)
        k_start = min(3, n_pts // 5)
        for k in range(k_start, n_pts - 1):
            x0f, y0f = pts[k][2], pts[k][3]
            x1f, y1f = pts[k + 1][2], pts[k + 1][3]
            seg_n = max(1, int(round(math.hypot(x1f - x0f, y1f - y0f))))
            for s in range(seg_n + 1):
                tt = s / seg_n
                xi = int(round(x0f + tt * (x1f - x0f)))
                yi = int(round(y0f + tt * (y1f - y0f)))
                if 0 <= xi < width and 0 <= yi < height:
                    f = flow[k] + tt * (flow[k + 1] - flow[k])
                    if (not cl_mask[yi, xi]) or f > cl_flow[yi, xi]:
                        cl_mask[yi, xi] = True
                        cl_wl[yi, xi] = water_levels[k] + tt * (water_levels[k + 1] - water_levels[k])
                        cl_flow[yi, xi] = f
                        cl_md[yi, xi] = mouthdist[k] + tt * (mouthdist[k + 1] - mouthdist[k])
                        cl_ocn[yi, xi] = reached_ocean

    have_rivers = bool(cl_mask.any())
    if have_rivers:
        from scipy.ndimage import distance_transform_edt
        Dr, (nn_y, nn_x) = distance_transform_edt(~cl_mask, return_indices=True)
        Dr = Dr.astype(np.float32)
        # the nearest-centreline lookups are piecewise-constant across the
        # Voronoi cells of the centreline pixels; a light blur removes the
        # cell seams (they only matter within a few px of the channel anyway)
        WL    = _gf(cl_wl[nn_y, nn_x], sigma=2.0)
        FLOWn = np.clip(_gf(cl_flow[nn_y, nn_x], sigma=2.0), 0.0, 1.0)
        MD    = _gf(cl_md[nn_y, nn_x], sigma=2.0)
        OCN   = cl_ocn[nn_y, nn_x]
    else:
        Dr = np.full((height, width), 1e9, dtype=np.float32)
        WL = np.zeros((height, width), dtype=np.float32)
        FLOWn = np.zeros((height, width), dtype=np.float32)
        MD = np.full((height, width), 1e9, dtype=np.float32)
        OCN = np.zeros((height, width), dtype=bool)

    # -- carve the valley.  A flat thalweg of half-width `w_chan` (flow-scaled:
    #    a ~3 px crease near the source, opening to a ~30 px floor near the
    #    mouth) is cut to an explicit level `chan_depth` below the local water
    #    line; from `w_chan` outward the floor eases back up to the natural
    #    terrain over `v_reach` px with a smoothstep, so the shoulders are
    #    smooth, not trench walls.  Using an explicit floor (not base - noise)
    #    keeps the channel bottom clean of the plains micro-relief so the
    #    waterline is a controlled offset into the V, not a puddle field.
    #    Faded to zero over the last ~90 px before an ocean mouth so the carve
    #    never perturbs coast_steep / beach width / surf gating.
    _vmarg, _, _ = iq_noised(WX_warped * 0.045 + 402.0, WY_warped * 0.045 - 251.0)
    _vjit = (0.85 + 0.30 * _vmarg)
    w_chan     = (1.5 + 9.0 * FLOWn) * _vjit                 # flat thalweg half-width
    v_reach    = (12.0 + 26.0 * FLOWn) * _vjit               # shoulder blend-out
    chan_depth = 0.010 + 0.026 * FLOWn                       # thalweg below water line
    v_free     = 0.0030 + 0.0025 * FLOWn                     # water sits this far below bank
    water_level = np.maximum(WL - v_free, 0.0006)            # never below sea level

    _tsh = np.clip((Dr - w_chan) / np.maximum(v_reach, 1e-3), 0.0, 1.0)
    _ssh = _tsh * _tsh * (3.0 - 2.0 * _tsh)                  # 0 in the channel, 1 at the shoulder
    carved_floor = (water_level - chan_depth) * (1.0 - _ssh) + base_ground_H * _ssh
    carved_floor = np.minimum(base_ground_H, carved_floor)
    shore_fade = np.where(OCN, np.clip(MD / 90.0, 0.0, 1.0), 1.0).astype(np.float32)
    carve_amt = _gf((base_ground_H - carved_floor).astype(np.float32), sigma=1.6) * shore_fade
    carved_ground_H = carved_ground_H - carve_amt

    # -- river water surface.  Width is set by a flow-scaled water half-width
    #    `w_water` (a ~3 px thread near the source, opening to a ~20 px channel
    #    low down), so it falls out of the same flow field that opens the
    #    valley; the wider carved trench around it gives the hillshaded banks.
    #    The waterline is feathered (a soft px band + a noisy Dr break) so it is
    #    never a clean contour.  `mouth_zone` fans the last stretch into a
    #    shallow delta that hands off to the sea; the water level clamp keeps it
    #    from ever cutting below sea level at the mouth.
    # mouth fan: only within ~70 px of a genuine ocean mouth AND only where the
    # ground is actually near sea level (so a tracer stub stuck mid-slope does
    # not sprout a fan), ramped gently.
    _lowland = 1.0 - np.clip((base_ground_H - 0.010) / 0.045, 0.0, 1.0)
    mouth_zone = (np.where(OCN, np.clip(1.0 - MD / 70.0, 0.0, 1.0), 0.0) * _lowland).astype(np.float32)
    _wedge, _, _ = iq_noised(WX * 0.16 + 34.0, WY * 0.16 - 78.0)
    _wedge2, _, _ = iq_noised(WX * 0.055 - 12.0, WY * 0.055 + 40.0)
    # source taper: kill the fat head where flow is still ~0
    _srctap = np.clip(FLOWn / 0.05, 0.4, 1.0)
    w_water = (1.2 + 7.0 * FLOWn) * _vjit * _srctap * (1.0 + 0.55 * mouth_zone)
    edge_soft = 1.6 + 2.4 * FLOWn
    dr_break = Dr + (0.55 * (_wedge - 0.5) + 0.30 * (_wedge2 - 0.5)) * (2.0 * edge_soft)
    river_alpha = np.clip((w_water - dr_break) / np.maximum(edge_soft, 1e-3), 0.0, 1.0)
    river_gate = (H_land_prob >= 0.28) & bool(have_rivers)
    river_alpha = np.where(river_gate, river_alpha, 0.0).astype(np.float32)
    is_river_water = river_alpha > 0.4
    water_surface_H = np.where(river_alpha > 0.05, water_level, water_surface_H)

    is_inland_water = is_river_water | is_lake_water

    # -- riparian band: a damp vegetated margin keyed on the same distance
    #    field, a few channel-widths wide with a noisy (not hard) outer edge.
    #    Drives a damper/darker/greener ground tint below and lifts the 2D
    #    canopy probability along the bank (gated to near existing forest so it
    #    thickens a gallery rather than spawning new woods in bare plains).
    _rip_w = w_water + v_reach * 0.9 + 12.0
    _ripn, _, _ = iq_noised(WX_warped * 0.06 + 88.0, WY_warped * 0.06 + 131.0)
    _ripn2, _, _ = iq_noised(WX * 0.22 - 40.0, WY * 0.22 + 15.0)
    riparian = np.where(
        have_rivers,
        np.clip(1.0 - (Dr + (_ripn - 0.5) * 26.0 + (_ripn2 - 0.5) * 7.0) / np.maximum(_rip_w, 1e-3),
                0.0, 1.0),
        0.0,
    ).astype(np.float32)
    riparian = riparian * (1.0 - river_alpha)

    # -------------------------------------------------------------------------
    # Hashed value helpers (canopy stamp scatter + parcel field below)
    # -------------------------------------------------------------------------
    def hash2_vec(cx_arr, cy_arr):
        p1 = cx_arr * 127.1 + cy_arr * 311.7
        p2 = cx_arr * 269.5 + cy_arr * 183.3
        h1 = np.sin(p1) * 43758.5453
        h2 = np.sin(p2) * 43758.5453
        return h1 - np.floor(h1), h2 - np.floor(h2)

    def hash1_vec(cx_arr, cy_arr):
        p = cx_arr * 127.1 + cy_arr * 311.7
        h = np.sin(p) * 43758.5453
        return h - np.floor(h)

    if progress_callback:
        progress_callback(0.55, "Calculating 3D surface derivatives & solar lighting...")
    # Combine Base Elevation with Carved Valleys and Flat Inland Water.
    # The forest is a pure 2D layer now (built further below, after lighting) --
    # it no longer perturbs the heightfield, so normals / slope / hillshade
    # stay clean under the wood.
    raw_H = np.where(is_inland_water, water_surface_H, carved_ground_H)

    # Open water deepens smoothly toward an abyss as land occupancy falls to 0
    # (this, not the shelf ramp, carries the depth of the open sea -- the shelf
    # `_off` term saturates at the water line).  Confined to the sub-sea region;
    # the cap is ~0 at the water line (matching the seabed there, so no step) and
    # drops to the abyss offshore.  `_ab` is a smooth function of the smooth
    # `H_land_prob`, so no ring.
    _sea = H_land_prob < shore_ref
    _ab = np.clip((shore_ref - H_land_prob) / shore_ref, 0.0, 1.0) ** 3.0   # stays ~0 across the shelf
    raw_H = np.where(_sea, np.minimum(raw_H, 0.02 - 2.6 * _ab), raw_H)

    H = raw_H

    # Surface normals (incorporates pointy tree spire details and flat water)
    height_exaggeration = 0.13
    dHx = np.gradient(H, axis=1) * (width / 2.0) * height_exaggeration
    dHy = np.gradient(H, axis=0) * (height / 2.0) * height_exaggeration
    Nz = np.ones_like(H, dtype=np.float32)
    norm = np.sqrt(dHx**2 + dHy**2 + Nz**2)
    Nx = -dHx / norm
    Ny = -dHy / norm
    Nz = Nz / norm

    # Flatten normals on inland water -- lakes hard-flat, river water feathered
    # by its coverage alpha so the carved bank hillshade does not step at the
    # exact waterline (v10).
    _flatw = np.maximum(is_lake_water.astype(np.float32), river_alpha)
    Nx = Nx * (1.0 - _flatw)
    Ny = Ny * (1.0 - _flatw)
    Nz = Nz * (1.0 - _flatw) + _flatw
    _nlen = np.sqrt(Nx * Nx + Ny * Ny + Nz * Nz) + 1e-6
    Nx, Ny, Nz = Nx / _nlen, Ny / _nlen, Nz / _nlen
    slope = 1.0 - Nz

    # Lighting
    sun_x, sun_y, sun_z = -0.55, -0.55, 0.70
    sun_len = math.sqrt(sun_x**2 + sun_y**2 + sun_z**2)
    sun_x /= sun_len
    sun_y /= sun_len
    sun_z /= sun_len

    NdotL = np.clip(Nx * sun_x + Ny * sun_y + Nz * sun_z, 0.0, 1.0)
    diffuse_sun = np.power(NdotL, 1.05)
    sky_light = Nz * 0.60 + 0.40

    # Soft shadows (water is recessed so rivers and lakes do not cast shadows)
    H_shadow = np.where(is_inland_water, carved_ground_H, H)
    step_dx = 2.5
    step_dy = 2.5
    step_dz = 0.055
    shadow_mask = np.ones((height, width), dtype=np.float32)

    for s in range(1, 15):
        ox = int(round(s * step_dx))
        oy = int(round(s * step_dy))
        dz = s * step_dz
        if oy >= height or ox >= width:
            break
        occluder = np.full_like(H_shadow, -1.0)
        occluder[oy:, ox:] = H_shadow[:-oy, :-ox]
        diff = occluder - (H + dz)
        in_shadow = diff > 0.010
        penumbra = np.clip(1.0 - diff * 4.0, 0.45, 1.0)
        shadow_mask = np.where(in_shadow, np.minimum(shadow_mask, penumbra), shadow_mask)

    direct_sun = diffuse_sun * shadow_mask

    # =====================================================================
    if progress_callback:
        progress_callback(0.70, "Synthesizing 2D volumetric forest canopy layers...")
    # FOREST CANOPY -- 2D layer over the lit relief (v03).
    # Mass first, stipple second: a continuous density field (blurred hex
    # forest-prob with its 0.5 contour pushed around by multi-octave noise)
    # lays a dark connected underlay + AO on the ground; crown stamps only
    # TEXTURE that mass, they never define the forest shape. Density carries
    # interior clearings and thins on slope / toward the rock.
    # =====================================================================
    from scipy.ndimage import gaussian_filter

    _cseed = float(generator.seed % 4096) * 0.017113

    def _ss(lo, hi, x):
        t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    # -- crown stamps FIRST: an overlapping Voronoi-ish scatter (~5 px cells).
    #    Accumulated as CONTINUOUS weighted fields (no hard per-cell gate, so
    #    no lattice): a smooth blend of nearby crown tones (3 families), a
    #    bumpy dome-relief field, a sun-rim highlight and a far-rim self
    #    shadow.  They only texture the mass and crown-scallop its margin --
    #    they never decide *whether* there is forest.
    _iseed = int(generator.seed) & 0x7FFFFFFF
    _ntab = noise_tbl

    def _cellhash(ai, bi, salt):
        # integer hash of a cell index -> a decorrelated value from the noise
        # table (the sin-hash correlates badly on a regular grid -> lattice).
        h = (ai * np.int64(374761393)) ^ (bi * np.int64(668265263)) ^ np.int64(salt * 2246822519 + _iseed)
        h = (h ^ (h >> np.int64(13))) * np.int64(1274126177)
        h = (h ^ (h >> np.int64(16))) & np.int64(0xFFFF)
        return _ntab[(h >> np.int64(8)).astype(np.int64), (h & np.int64(255)).astype(np.int64)]

    _cc = 5.0
    _u = WX / _cc
    _vv = WY / _cc
    _nu = np.floor(_u)
    _nv = np.floor(_vv)
    _fu = (_u - _nu).astype(np.float32)
    _fv = (_vv - _nv).astype(np.float32)

    _wsum = np.full_like(WX, 1e-4, dtype=np.float32)
    _tone_ws = np.zeros_like(WX, dtype=np.float32)
    _relief_ws = np.zeros_like(WX, dtype=np.float32)
    canopy_hi = np.zeros_like(WX, dtype=np.float32)
    canopy_sh = np.zeros_like(WX, dtype=np.float32)
    canopy_cov = np.zeros_like(WX, dtype=np.float32)

    # full 3x3 neighbourhood (a 2x2 quadrant trick pops crowns at the cell
    # seams -> a faint lattice; 3x3 is seamless)
    for _gv in (-1, 0, 1):
        for _gu in (-1, 0, 1):
            _cellu = (_nu + _gu).astype(np.int64)
            _cellv = (_nv + _gv).astype(np.int64)
            _ox = _cellhash(_cellu, _cellv, 1)
            _oy = _cellhash(_cellu, _cellv, 2)
            _hr = _cellhash(_cellu, _cellv, 3)
            _hv = _cellhash(_cellu, _cellv, 4)
            _ru = (_gu - _fu + _ox) * _cc                 # full-jitter centre offset
            _rv = (_gv - _fv + _oy) * _cc
            _rad = _cc * (0.70 + 0.55 * _hr)              # ~3.5 .. 6.3 px, always overlaps
            _d = np.sqrt(_ru * _ru + _rv * _rv)
            _qn = _d / np.maximum(_rad, 1e-4)
            _prof = np.where(_qn < 1.35, np.maximum(0.0, 1.0 - _qn * _qn), 0.0)
            _tone = np.where(_hv < 0.42, -0.55, np.where(_hv < 0.80, 0.05, 0.55))
            _sunlit = -(_ru * sun_x + _rv * sun_y) / np.maximum(_d, 1e-4)  # +1 on sun rim
            _wsum += _prof
            _tone_ws += _prof * _tone
            _relief_ws += _prof * _sunlit
            canopy_cov = np.maximum(canopy_cov, _prof)
            canopy_hi = np.maximum(canopy_hi, np.clip(_sunlit, 0.0, 1.0) * _prof)
            _ring = _ss(1.0, 1.35, _qn) * _ss(1.85, 1.35, _qn)   # just off the crown rim
            canopy_sh = np.where(_sunlit < -0.10,
                                 np.maximum(canopy_sh, _ring * (-_sunlit)), canopy_sh)

    tone_blend = _tone_ws / _wsum                          # smooth -0.55..0.55
    relief_blend = _relief_ws / _wsum                      # smooth -1..1 (sun vs shade side)
    # value texture on the mass: tone family + bumpy dome relief + sun rim
    canopy_tex = np.clip(0.55 * tone_blend
                         + 0.50 * (canopy_cov - 0.62)
                         + 0.22 * relief_blend, -0.80, 0.60)

    # -- multi-octave boundary noise: edge interpenetrates at several scales
    #    (coarse -> bays & peninsulas; fine ~5 px -> crenellated pixel edge)
    cbn = np.zeros_like(WX, dtype=np.float32)
    _a, _f = 1.0, 1.0 / (HEX_SIZE * 4.2)
    for _o in range(6):
        _v, _, _ = iq_noised(WX_warped * _f + _cseed, WY_warped * _f - _cseed)
        cbn += _a * (_v - 0.5)
        _a *= 0.58
        _f *= 2.05
    cbn = np.clip(cbn / 0.52, -1.0, 1.0)

    # -- fine dither noise (~2-4 px) to keep every canopy edge from ever
    #    reading as a clean airbrushed contour.
    _fd0, _, _ = iq_noised(WX * 0.30 + 9.0 + _cseed, WY * 0.30 - 4.0)
    _fd1, _, _ = iq_noised(WX * 0.62 - 3.0, WY * 0.62 + 7.0 + _cseed)
    cfn = np.clip(((_fd0 - 0.5) * 0.7 + (_fd1 - 0.5) * 0.3) / 0.35, -1.0, 1.0)

    # -- continuous density.  Light blur only (the forest-prob field is already
    #    smooth); its 0.5-ish contour is then pushed around by cbn + the crown
    #    bulge + fine dither and re-thresholded fairly sharply so the mass is
    #    solid with a ragged, multi-scale, crown-scalloped margin -- no hex
    #    facet, no soft gradient.
    fprob = gaussian_filter(H_forest_prob.astype(np.float32), sigma=HEX_SIZE * 0.14)
    # v10: riparian gallery -- lift canopy probability along the river banks so
    # the margin reads as vegetation, not an outline.  A thin unconditional
    # fringe plus a stronger boost where forest tiles are already nearby (so it
    # thickens an existing wood toward the water rather than seeding a new one).
    _fp_near = gaussian_filter(H_forest_prob.astype(np.float32), sigma=HEX_SIZE * 0.6)
    edge = (fprob + 0.36 * cbn + 0.15 * cfn + 0.07 * (canopy_cov - 0.55)
            + 0.06 * riparian + 0.30 * riparian * np.clip(_fp_near * 4.0, 0.0, 1.0))
    canopy_density = _ss(0.28, 0.50, edge)

    # -- interior clearings: low-freq patches thin / punch ragged holes even in
    #    the core of the wood (rims dithered so they aren't clean ovals).
    _cl, _, _ = iq_noised(WX_warped / (HEX_SIZE * 1.7) + 71.0 + _cseed,
                          WY_warped / (HEX_SIZE * 1.7) - 33.0)
    clearing = _ss(0.52, 0.80, _cl + 0.18 * cfn)
    canopy_density = canopy_density * (1.0 - 0.85 * clearing)

    # -- thin toward the rock: elevation/treeline + slope
    canopy_density = canopy_density * treeline_factor
    canopy_density = canopy_density * np.clip(1.0 - (slope - 0.14) / 0.34, 0.0, 1.0)
    canopy_density = np.where(is_inland_water, 0.0, canopy_density)
    canopy_density = np.clip(canopy_density, 0.0, 1.0)

    # -- AO halo (soft, a touch wider than the mass) for floor shading
    canopy_ao = np.clip(gaussian_filter(canopy_density, sigma=4.0) * 1.15, 0.0, 1.0)

    # -- drop shadow: the mass shifted toward anti-sun (SE), softened a little
    _shp = 4
    _src = np.zeros_like(canopy_density)
    _src[_shp:, _shp:] = canopy_density[:-_shp, :-_shp]
    canopy_drop = np.clip(gaussian_filter(_src, sigma=1.5) - canopy_density, 0.0, 1.0)

    # -- underlay tone: deep shadow-green <-> mid canopy, low-freq patchy
    canopy_deep = np.array([0.060, 0.140, 0.075], dtype=np.float32)
    canopy_core = np.array([0.130, 0.270, 0.120], dtype=np.float32)
    canopy_olive = np.array([0.300, 0.380, 0.170], dtype=np.float32)
    _tp, _, _ = iq_noised(WX_warped / (HEX_SIZE * 0.85) + 12.0 + _cseed,
                          WY_warped / (HEX_SIZE * 0.85) - 5.0)
    _um = np.clip(0.5 + 0.75 * (_tp - 0.5) * 2.0, 0.0, 1.0)[:, :, None]
    canopy_under_col = canopy_deep * (1.0 - _um) + canopy_core * _um

    # Ocean water -- depth-extinction (per-channel Beer-Lambert) of the seabed
    # albedo, composited against a volume IN-SCATTER colour (v05).  transmittance
    # = exp(-k*depth), k largest for red, then green, smallest for blue;
    # composited over a sand->rock seabed that itself fades out with depth.  No
    # thresholds -> a smooth turquoise -> deep blue-grey gradient with no bands;
    # the near-constant Fresnel sky add below keeps shallow water cooler than
    # the beach so the shore line stays legible without a step.
    is_ocean_water = H < 0.0
    depth = np.clip(-H, 0.0, 5.0)
    _d3 = depth[:, :, None]

    seabed_sand = np.array([0.40, 0.42, 0.33], dtype=np.float32)
    seabed_rock = np.array([0.18, 0.23, 0.22], dtype=np.float32)
    _sbn, _, _ = iq_noised(WX_warped / (HEX_SIZE * 0.55) + 4.0,
                           WY_warped / (HEX_SIZE * 0.55) - 9.0)
    _sbn2, _, _ = iq_noised(WX_warped / (HEX_SIZE * 1.6) - 21.0,
                            WY_warped / (HEX_SIZE * 1.6) + 6.0)
    sb_mix = np.clip((depth - 0.010) / 0.10 + 0.75 * (_sbn - 0.5) + 0.45 * (_sbn2 - 0.5),
                     0.0, 1.0)[:, :, None]
    seabed_alb = seabed_sand * (1.0 - sb_mix) + seabed_rock * sb_mix

    # v08: DEPTH-DEPENDENT volume in-scatter.  v05 blended two near-identical
    # mid-teals (seabed_rock ~ inscatter_col) so every depth returned the same
    # colour and the shelf went invisible; now the in-scatter colour itself
    # interpolates shallow -> deep, red then green going extinct as the water
    # deepens (hue rotates bluewards, value drops).  Extinction is back near
    # v04 contrast so open water is ~all in-scatter (the seabed rock albedo
    # stops greying it) and the shelf falloff actually shows.  v05's turbidity
    # floor + the Fresnel sky ADD (the black-sea fix) are KEPT; Fresnel is now
    # depth-INDEPENDENT -- its variation moves onto the wave normals below.
    k_ext = np.array([4.6, 1.8, 1.0], dtype=np.float32)
    trans = np.exp(-k_ext * _d3)
    turb = 0.06
    inv_t = 1.0 - trans * (1.0 - turb)                        # in-scatter fraction, floored at turb

    isc_shallow = np.array([0.120, 0.300, 0.245], dtype=np.float32)   # shelf: green-teal, G >> B
    isc_deep    = np.array([0.100, 0.205, 0.223], dtype=np.float32)   # v10: slate-blue, value lifted
    # v09: the v08 `G >= B` deep-water rule is RETIRED -- it forced open sea into
    # an olive-teal that shared the plains-grass hue and killed land/sea
    # figure-ground (deadends.md).  Green now lives on the shelf only; deep
    # water rotates past teal to a slate-blue (B >= G).
    # v10: open-sea luminance had drifted to ~0.16 (v07 .269 -> v08 .199 -> v09
    # .161) against the `sea` ref's .215 -- the frame was reading too dark and
    # flat over water.  `isc_deep` raised ~46% in luminance (constant lum .113
    # -> .165) with G nudged up proportionally MORE than B, so it stays
    # slate-blue (B >= G) but less severely: constant B-G .050 -> .024, landing
    # rendered open-sea B-G ~= 0.03 not 0.06.  This is the mandated 1-constant
    # precondition for v10; nothing else in the water model is touched.
    # depth -> shallow/deep mix.  Most of the swing is spent across the shelf
    # (0 .. ~0.6) so a wide plains shelf reads as a broad turquoise band that
    # darkens gradually, while a cliff plunge crosses it in a handful of px.
    isc_t = (1.0 - np.exp(-depth / 0.42))[:, :, None]
    inscatter_field = isc_shallow[None, None, :] * (1.0 - isc_t) + isc_deep[None, None, :] * isc_t
    w_col = seabed_alb * (1.0 - inv_t) + inscatter_field * inv_t

    # --- Surface wave NORMALS (v09): a real two-component perturbed normal.
    #     v08 added a SCALAR slope proxy monotonically to `fres`, so brightness
    #     traced iso-contours of the noise field and the big (+-30 px) flow warp
    #     smeared them into long parallel light ribbons (deadends.md).  v09:
    #       * swell weight cut to ~1/3, warp displacement shrunk +-30/10 ->
    #         +-10/6 px so it DECORRELATES the ripple field, not stretches it;
    #       * the swell + ripple analytic derivatives are assembled into an
    #         actual normal vector (nx, ny, nz), normalized;
    #       * shading comes from the normal's FACING, not its slope magnitude:
    #         a tight specular lobe (high N.H power) so crests glint and die
    #         between crests, and a sky ADD split by the normal's tilt
    #         DIRECTION so one flank of each crest catches sky and the other
    #         does not.
    #     Still: low-freq swell (~2.5 hex, along surf vector (0.72,-0.69)) +
    #     fine anisotropic ripple (~7 px), phase-warped by a slow flow field so
    #     nothing tiles or shows a 0/90 axis; faded out in the surf band.
    _wv = np.array([0.72, -0.69], dtype=np.float32)
    _wv /= np.linalg.norm(_wv)
    _wp = np.array([-_wv[1], _wv[0]], dtype=np.float32)       # across-swell axis
    # flow field on the DOMAIN-WARPED coords (not raw WX/WY) so the phase warp
    # carries no residual screen-axis alignment (deadends.md).
    _flw, _fldx, _fldy = iq_noised(WX_warped * 0.012 + 5.0, WY_warped * 0.012 - 9.0)
    _flw2, _fl2dx, _fl2dy = iq_noised(WX_warped * 0.028 - 14.0, WY_warped * 0.028 + 22.0)
    _pwx = WX + _fldx * 10.0 + _fl2dx * 6.0                   # v08 was 30 / 10 -- shrunk
    _pwy = WY + _fldy * 10.0 + _fl2dy * 6.0
    _along = _pwx * _wv[0] + _pwy * _wv[1]
    _acr   = _pwx * _wp[0] + _pwy * _wp[1]
    _swf = 1.0 / (HEX_SIZE * 2.5)                             # swell: ~2.5 hex along travel
    _sv, _sdx, _sdy = iq_noised(_along * _swf + 0.6 * _flw, _acr * _swf * 0.45 + 11.0)
    _rpf = 1.0 / 7.0                                          # ripple: ~7 px along, ~3x stretched across
    _rv, _rdx, _rdy = iq_noised(_along * _rpf + 1.7 * _flw, _acr * _rpf * 0.33 - 4.0)
    # frame-space height gradient (along-travel, across-travel).  Swell weight
    # 0.06-equivalent (~1/3 of v08's 0.18); the fine ripple carries the crests.
    _g_al = _sdx * 0.35 + _rdx * 1.05
    _g_ac = _sdy * 0.35 + _rdy * 0.55
    # rotate the frame-space gradient back into screen x / y
    _g_x = _g_al * _wv[0] + _g_ac * _wp[0]
    _g_y = _g_al * _wv[1] + _g_ac * _wp[1]
    _surf_fade = np.clip((depth - 0.06) / 0.10, 0.0, 1.0) * is_ocean_water
    _g_x = _g_x * _surf_fade
    _g_y = _g_y * _surf_fade
    # perturbed unit normal  N = normalize(-A*grad_x, -A*grad_y, 1)
    _wamp = 1.0
    _nx = -_wamp * _g_x
    _ny = -_wamp * _g_y
    _ninv = 1.0 / np.sqrt(_nx * _nx + _ny * _ny + 1.0)
    _nx = _nx * _ninv
    _ny = _ny * _ninv
    _nz = _ninv

    half_vec = np.array([sun_x, sun_y, sun_z + 1.0], dtype=np.float32)
    half_vec /= np.linalg.norm(half_vec)
    # The sea body is still lit near-flat (N=(0,0,1)); the wave normal drives
    # only the specular + sky ADD, not the body lighting, so the shore never
    # hillshades into a dark rim.
    _wsun = float(sun_z) ** 1.05
    _wshadow = 0.78 + 0.22 * shadow_mask
    # TIGHT specular lobe off the perturbed normal: a facet pointing near the
    # sun half-vector glints hard; the high power kills it between crests.  A
    # tiny flat-water sheen underneath keeps the open sea off matte-black.
    # The lobe is further GATED to actual ripple + swell crest tops (`_rv`,
    # `_sv` are the noise values, not slopes) so glints stay DISCRETE and
    # clustered on the up-faces of swells, not a whole-sea speckle field.
    _NdotH = np.clip(_nx * half_vec[0] + _ny * half_vec[1] + _nz * half_vec[2], 0.0, 1.0)
    _crest = (np.clip((_rv - 0.60) / 0.40, 0.0, 1.0) ** 1.4
              * (0.35 + 0.65 * np.clip((_sv - 0.42) / 0.45, 0.0, 1.0)))
    _spec_glint = (_NdotH ** 100) * 0.55 * _crest * _surf_fade
    _wspec = ((float(np.clip(half_vec[2], 0.0, 1.0)) ** 24) * 0.055
              + _spec_glint)
    # Fresnel sky ADD, now split by the normal's TILT DIRECTION not its
    # magnitude: facets tilted toward the sun azimuth catch bright sky, the
    # opposite flank catches almost none -- an asymmetric per-crest split, not
    # a brighten-wherever-there-is-slope wash.
    _saz = np.array([sun_x, sun_y], dtype=np.float32)
    _saz /= np.linalg.norm(_saz)
    _tilt = _nx * _saz[0] + _ny * _saz[1]                     # signed, ~ +-0.3
    sky_col = np.array([0.50, 0.575, 0.66], dtype=np.float32)  # v09: B >= G
    fres = np.clip(0.045 + 0.11 * _tilt, 0.012, 0.11)
    ocean_lit = (w_col * (0.30 + 0.70 * _wsun * _wshadow[:, :, None])
                 + _wspec[:, :, None] + sky_col[None, None, :] * fres[:, :, None])

    # Surf -- foam only in shallow water, gated by exposure of the shore normal
    # to a fixed swell direction, broken into arcs by noise, concentrated on
    # headlands and thinned in bays.  Not a continuous ribbon / outline.
    _shl = np.sqrt(dHx * dHx + dHy * dHy) + 1e-6
    _outx, _outy = dHx / _shl, dHy / _shl                     # unit vector, points seaward (downhill)
    _swell = np.array([0.72, -0.69], dtype=np.float32)
    _swell /= np.linalg.norm(_swell)
    _expose = np.clip(-(_outx * _swell[0] + _outy * _swell[1]), 0.0, 1.0) ** 0.8
    _lm = (H > 0.0).astype(np.float32)
    _head = _gf(_lm, sigma=7.0) - _gf(_lm, sigma=22.0)        # >0 on headlands, <0 in bays
    _head_gate = np.clip(0.62 + _head * 4.5, 0.40, 1.35)
    _fn0, _, _ = iq_noised(WX * 0.13 + 3.0, WY * 0.13 - 7.0)
    _fn1, _, _ = iq_noised(WX * 0.40 - 11.0, WY * 0.40 + 5.0)
    _fn2, _, _ = iq_noised(WX * 1.10 + 2.0, WY * 1.10 + 1.0)
    _fbreak = _ss(0.30, 0.66, _fn0 * 0.55 + _fn1 * 0.30 + _fn2 * 0.15)
    _szone = np.clip((0.075 - depth) / 0.075, 0.0, 1.0) * is_ocean_water
    _szone = _szone * np.clip(depth / 0.004, 0.0, 1.0)        # drop the last sliver at the very edge
    foam = np.clip((_szone ** 0.5) * (0.42 + 1.9 * _expose) * _fbreak * _head_gate, 0.0, 1.0)
    foam_col = np.array([0.94, 0.965, 0.975], dtype=np.float32)
    ocean_lit = ocean_lit * (1.0 - foam[:, :, None]) + foam_col * foam[:, :, None]

    # --- Inland Rivers & Lakes Flat Smooth Water Shader ---
    inland_water_depth = np.clip((water_surface_H - carved_ground_H) / 0.025, 0.0, 1.0)[:, :, None]
    lake_deep = np.array([0.10, 0.28, 0.54], dtype=np.float32)
    lake_shallow = np.array([0.22, 0.52, 0.68], dtype=np.float32)
    inland_water_col = lake_shallow * (1.0 - inland_water_depth) + lake_deep * inland_water_depth
    # v10: pull the river-mouth water toward a shallow estuarine green-blue over
    # the delta fan so the channel hands off to the sea instead of ending on a
    # hard colour seam.
    _estu = np.clip(mouth_zone, 0.0, 1.0)[:, :, None]
    estuary_col = np.array([0.15, 0.33, 0.40], dtype=np.float32)
    inland_water_col = inland_water_col * (1.0 - 0.55 * _estu) + estuary_col * (0.55 * _estu)
    inland_specular = (np.clip(half_vec[2], 0.0, 1.0)**32 * 0.35) * direct_sun[:, :, None]
    inland_water_lit = inland_water_col * (0.65 + 0.35 * direct_sun[:, :, None]) + inland_specular

    # --- Rich Varied Biome Materials & Inigo Quilez Procedural Textures ---
    # 1. EXPANSIVE & PROMINENT BEACHES (Large, wide sandy coastal shores & dunes)
    wet_sand = np.array([0.72, 0.66, 0.50], dtype=np.float32)
    gold_sand = np.array([0.88, 0.82, 0.60], dtype=np.float32)
    dune_sand = np.array([0.94, 0.89, 0.72], dtype=np.float32)
    sand_ripple = np.sin((WX * 0.6 + WY * 0.8) / 10.0) * 0.5 + 0.5
    
    t_beach = np.clip(H / 0.065, 0.0, 1.0)[:, :, None]
    beach_col = wet_sand * (1.0 - t_beach) + gold_sand * t_beach
    beach_col = beach_col * (0.94 + 0.06 * sand_ripple[:, :, None])
    beach_col = beach_col * (1.0 - np.clip((H - 0.040)/0.035, 0.0, 1.0)[:, :, None]) + dune_sand * np.clip((H - 0.040)/0.035, 0.0, 1.0)[:, :, None]

    if progress_callback:
        progress_callback(0.82, "Generating multi-scale ground cover, grain & soil parcels...")
    # 2. GROUND-COVER ALBEDO LAYER (2D field)  -- v02: spectrum redistributed
    # HUE is held near-constant (a desaturated sage/olive); the low (>= hex)
    # octaves drive VALUE and SATURATION only. The reclaimed amplitude is spent
    # at 1-4 px as value-dominant grain plus sparse ridged filaments (tracks /
    # hedge lines). A hard chroma cap + a structural "green leads blue" guard
    # keep the cool areas from ever approaching the shelf-water turquoise
    # (coastal_turquoise / shallow_shelf). The Worley parcel lookup is now
    # FULLY domain-warped (no unwarped residual) so its borders carry no grid
    # axis. Albedo only -- heightfield / relief / hillshade / rivers / trees are
    # untouched here; there is no coast-distance vignette term to retire.
    _seed_off = float(generator.seed % 1000) * 0.1731

    def _sstep(a, b, x):
        t = np.clip((x - a) / (b - a), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    # --- directional domain warp: mild stringiness (features a little longer
    #     along X); Y warp is no longer near-zero, to avoid horizontal banding.
    gw_s = 1.0 / (HEX_SIZE * 2.6)
    gw1_v, gw1_dx, gw1_dy = iq_noised(WX * gw_s + _seed_off, WY * gw_s * 0.7 - _seed_off)
    gw2_v, gw2_dx, gw2_dy = iq_noised((WX + 61.0) * gw_s * 1.9 + gw1_v * 1.6,
                                      (WY - 43.0) * gw_s * 1.1 + gw1_v * 1.6)
    warpX = (gw1_dx * 0.7 + gw2_dx * 0.5) * (HEX_SIZE * 1.5)
    warpY = (gw1_dy * 0.7 + gw2_dy * 0.5) * (HEX_SIZE * 0.9)
    GX = WX + warpX
    GY = WY + warpY

    # --- LOW-FREQUENCY field (>= hex scale). Drives VALUE + SATURATION, NOT hue.
    gc_coarse = np.zeros_like(WX, dtype=np.float32)
    c_amp, c_freq = 1.0, 1.0 / (HEX_SIZE * 3.4)
    for _ in range(3):
        cv, _, _ = iq_noised(GX * c_freq + _seed_off, GY * c_freq * 0.8)
        gc_coarse += c_amp * (cv - 0.5)
        c_amp *= 0.55
        c_freq *= 2.07
    gc_coarse = np.clip(gc_coarse / 0.62, -1.0, 1.0)             # ~zero-mean [-1,1]

    gs_v, _, _ = iq_noised((GX * 0.8 + 210.0) / (HEX_SIZE * 3.6) - _seed_off,
                           (GY * 1.1 - 90.0) / (HEX_SIZE * 3.6))
    gs_low = np.clip((gs_v - 0.5) * 2.3, -1.0, 1.0)             # saturation swings

    # --- SUB-HEX clump mottle (~9-20 px): tussock / graze patchiness, the scale
    #     that was entirely missing in v01. Value-dominant.
    clump = np.zeros_like(WX, dtype=np.float32)
    k_amp, k_freq = 1.0, 1.0 / 20.0
    for _ in range(2):
        kv, _, _ = iq_noised(GX * k_freq + 40.0 + _seed_off, GY * k_freq * 1.15 - 12.0)
        clump += k_amp * (kv - 0.5)
        k_amp *= 0.6
        k_freq *= 2.1
    clump = np.clip(clump / 0.72, -1.0, 1.0)

    # --- HIGH-FREQUENCY value grain at ~3-13 px. Own loop, high gain (0.8) so
    #     the top octaves actually reach a pixel; value-dominant, no hue term.
    #     A mild contrast curve pushes it off the mushy midtone so it reads as
    #     grazed texture rather than faint dither.
    grain = np.zeros_like(WX, dtype=np.float32)
    n_amp, n_freq = 1.0, 1.0 / 6.0
    for _ in range(3):
        nv, _, _ = iq_noised(WX * n_freq + _seed_off * 1.7, WY * n_freq * 1.25 - _seed_off)
        grain += n_amp * (nv - 0.5)
        n_amp *= 0.8
        n_freq *= 2.0
    grain = np.clip(grain / 0.9, -1.0, 1.0)
    grain = np.sign(grain) * np.abs(grain) ** 0.72

    # --- shared two-octave ISOTROPIC domain warp used for BOTH the filament
    #     ridge input and the Worley parcel lookup (deadends.md entry 2: the
    #     parcel lookup must carry no unwarped grid axis).
    pw_s = 1.0 / (HEX_SIZE * 3.0)
    pw1_v, pw1_dx, pw1_dy = iq_noised(WX * pw_s + 17.0 + _seed_off, WY * pw_s - 5.0)
    pw2_v, pw2_dx, pw2_dy = iq_noised((WX - 9.0) * pw_s * 2.1, (WY + 22.0) * pw_s * 2.1 + _seed_off)

    # --- sparse thin linear filaments (tracks / hedge lines) from ridged noise
    #     thresholded to hairlines. The ridge input is itself domain-warped and
    #     two-octave so crests meander (no long straight lines at island scale);
    #     two orientations, gated so they only touch a fraction of the area.
    #     Dark filaments = furrows / hedge shadow, light = worn tracks.
    FLX = WX + (pw1_dx * 0.6 + pw2_dx * 0.5) * (HEX_SIZE * 0.9)
    FLY = WY + (pw1_dy * 0.6 + pw2_dy * 0.5) * (HEX_SIZE * 0.9)
    fr_s = 1.0 / (HEX_SIZE * 1.25)
    fa0, _, _ = iq_noised(FLX * fr_s * 0.40 + 5.0 + _seed_off, FLY * fr_s * 1.55 - 2.0)
    fa1, _, _ = iq_noised(FLX * fr_s * 0.90 + 51.0, FLY * fr_s * 3.10 - 7.0)
    fb0, _, _ = iq_noised(FLX * fr_s * 1.60 - 8.0, FLY * fr_s * 0.44 + 11.0 + _seed_off)
    fb1, _, _ = iq_noised(FLX * fr_s * 3.20 + 17.0, FLY * fr_s * 0.95 - 4.0)
    ft0, _, _ = iq_noised(FLX * fr_s * 1.05 + 22.0, FLY * fr_s * 1.05 - 30.0 + _seed_off)
    fa_v = fa0 * 0.7 + fa1 * 0.3
    fb_v = fb0 * 0.7 + fb1 * 0.3
    ridgeA = 1.0 - np.abs(2.0 * fa_v - 1.0)
    ridgeB = 1.0 - np.abs(2.0 * fb_v - 1.0)
    ridgeT = 1.0 - np.abs(2.0 * ft0 - 1.0)
    fil_dark = np.maximum(_sstep(0.88, 0.972, ridgeA), _sstep(0.90, 0.978, ridgeB))
    fil_lite = _sstep(0.90, 0.980, ridgeT)
    sp_v, _, _ = iq_noised(WX / (HEX_SIZE * 5.0) + 30.0, WY / (HEX_SIZE * 5.0) - 14.0 + _seed_off)
    fil_dark = fil_dark * np.clip((sp_v - 0.42) / 0.28, 0.0, 1.0)
    fil_lite = fil_lite * np.clip((0.58 - sp_v) / 0.28, 0.0, 1.0)

    # --- SMALL edge-bounded soil parcels, on the fully-warped domain above
    #     (v11).  v10 used one huge ~210 px Worley cell driving a smooth
    #     per-parcel tone -- that read as more of the airbrushed lobing.  Now
    #     the cell is ~36 px (well under the 40-90 px lobe scale the Critic
    #     flagged), the warp is scaled down to match so parcels stay bounded
    #     rather than dissolving into noise, and only a minority of parcels
    #     (gated on `parcel_id`) take a modest dry/soil chroma shift.
    PWX = WX + (pw1_dx * 0.85 + pw2_dx * 0.42) * (HEX_SIZE * 0.36)
    PWY = WY + (pw1_dy * 0.85 + pw2_dy * 0.42) * (HEX_SIZE * 0.36)
    parcel_cell = HEX_SIZE * 0.72
    pcx = PWX / parcel_cell
    pcy = PWY / parcel_cell
    p_nu = np.floor(pcx)
    p_nv = np.floor(pcy)
    f1 = np.full_like(WX, 1e9, dtype=np.float32)
    f2 = np.full_like(WX, 1e9, dtype=np.float32)
    parcel_id = np.zeros_like(WX, dtype=np.float32)
    for _jj in (-1.0, 0.0, 1.0):
        for _ii in (-1.0, 0.0, 1.0):
            cu = p_nu + _ii
            cv = p_nv + _jj
            ox, oy = hash2_vec(cu + 3.7 + _seed_off, cv + 8.1 - _seed_off)
            featx = cu + 0.15 + 0.70 * ox
            featy = cv + 0.15 + 0.70 * oy
            pd2 = (pcx - featx) ** 2 + (pcy - featy) ** 2
            closer = pd2 < f1
            f2 = np.where(closer, f1, np.minimum(f2, pd2))
            f1 = np.where(closer, pd2, f1)
            cid = hash1_vec(cu + 19.3 + _seed_off, cv + 4.2)
            parcel_id = np.where(closer, cid, parcel_id)
    # sharp interior mask: seam transition ~5 px at the new cell size, so the
    # parcels read as bounded patches, not a gradient.
    parcel_edge = np.clip((np.sqrt(f2) - np.sqrt(f1)) / 0.14, 0.0, 1.0)  # 0 at seam -> 1 interior
    # gate: only parcels with id > ~0.58 turn dry/soil (a minority), the rest
    # stay uniform mid-green like the plains3 ref.
    parcel_dry = np.clip((parcel_id - 0.58) / 0.22, 0.0, 1.0) * parcel_edge

    # --- v12: HILL-BAND ground-cover retarget.  v11 and earlier blended
    #     `ground_c` up to 75% toward the flat constant `hills_col` on a smooth
    #     `clip(H_hills_prob*1.3)` ramp, *downstream* of all plains texture -- an
    #     airbrushed gradient AND a zero-grain uniform fill that multiplied the
    #     grain / clump / parcel texture down ~4x wherever it bit (the "khaki
    #     donut").  Now the hill band is pushed DRIER, LESS SATURATED and a touch
    #     DARKER through the SAME dryness / sat / value fields the plains texture
    #     already rides -- so the 3-13 px grain, the 9-20 px clump mottle and the
    #     soil parcels keep FULL strength inside the band.  The grass<->scrub
    #     boundary is perturbed by fine (~5-15 px) noise BEFORE it is used as a
    #     weight, so grass fingers run uphill and scrub tongues run downhill
    #     instead of following a clean probability contour.  Hue is never driven
    #     directly here (dryness/sat/value only); the downstream chroma cap +
    #     "green leads blue" guard still apply.
    _hpn0, _, _ = iq_noised(WX / 12.0 + 6.0 + _seed_off, WY / 12.0 - 21.0)
    _hpn1, _, _ = iq_noised(WX / 4.6 - 27.0, WY / 4.6 + 9.0 + _seed_off * 1.3)
    hill_edge_noise = (_hpn0 - 0.5) * 0.32 + (_hpn1 - 0.5) * 0.14      # ~+-0.23
    h_prob_n = np.clip(H_hills_prob + hill_edge_noise, 0.0, 1.0)
    hillw = np.clip(h_prob_n * 1.25, 0.0, 1.0)
    hillw = hillw * hillw * (3.0 - 2.0 * hillw)                        # broken S, not mush

    # --- assemble (v11).  The large-scale octaves (`gc_coarse` ~40-170 px,
    #     `gs_low` ~180 px) no longer drive luminance -- they were the smooth
    #     airbrushed 40-90 px tone lobes the Critic flagged.  `gc_coarse` is cut
    #     ~85% out of value and trimmed in dryness/sat (the lobes read chromatic
    #     too); `gs_low` trimmed in sat.  The reclaimed budget goes to
    #     `parcel_dry`: small (~36 px) edge-bounded soil patches with a modest
    #     warm + desaturated shift, not a smooth gradient.  The 3-13 px `grain`
    #     loop and its 0.26 value weight / 0.05 dryness / 0.14 sat terms are
    #     UNTOUCHED (hi-freq std measured right at .078 vs ref .068).  `clump`
    #     (9-20 px, sub-hex) value weight is trimmed only slightly (0.13 -> 0.11).
    # HUE: near-constant; a small dryness swing, now mostly per-parcel.
    # v12: `+ 0.22*hillw` pushes the hill band toward `grass_dry` (scrub straw)
    # through the same blend the grain/clump/parcel ride -- no flat fill.
    dryness = np.clip(0.50 + 0.06 * gs_low + 0.018 * gc_coarse + 0.16 * parcel_dry
                      + 0.05 * clump + 0.05 * grain
                      + 0.22 * hillw, 0.18, 0.86)
    # SATURATION: large-scale swings pulled way down; grain/clump breaks kept.
    # v12: `- 0.24*hillw` desaturates the hill band (dusty scrub) texturally.
    sat_mod = np.clip(0.50 + 0.16 * gs_low + 0.05 * gc_coarse - 0.12 * parcel_dry
                      + 0.14 * clump + 0.14 * grain
                      - 0.24 * hillw, 0.0, 1.0)
    # VALUE: large-scale contribution gutted; texture now carried by the
    # untouched fine grain + clump; soil parcels sit a touch darker.
    # v12: `- 0.09*hillw` drops the hill band a little (grain still swings +-0.37).
    value_mott = np.clip(1.0 + 0.008 * gc_coarse - 0.045 * parcel_dry
                         + 0.11 * clump + 0.26 * grain
                         - 0.20 * fil_dark + 0.12 * fil_lite
                         - 0.09 * hillw, 0.66, 1.32)
    seam_shade = 0.975 + 0.025 * parcel_edge

    grass_sage = np.array([0.40, 0.46, 0.34], dtype=np.float32)     # desaturated cool sage
    grass_mid  = np.array([0.37, 0.45, 0.27], dtype=np.float32)     # neutral meadow olive
    grass_dry  = np.array([0.55, 0.52, 0.30], dtype=np.float32)     # warm straw

    d = dryness[:, :, None]
    plains_col = np.where(
        d < 0.5,
        grass_sage * (1.0 - d / 0.5) + grass_mid * (d / 0.5),
        grass_mid * (1.0 - (d - 0.5) / 0.5) + grass_dry * ((d - 0.5) / 0.5),
    )
    luma = plains_col[:, :, 0:1] * 0.299 + plains_col[:, :, 1:2] * 0.587 + plains_col[:, :, 2:3] * 0.114
    sfac = (0.82 + 0.40 * sat_mod)[:, :, None]                      # ~0.82 .. 1.22
    plains_col = luma + (plains_col - luma) * sfac
    plains_col = plains_col * (seam_shade[:, :, None] * value_mott[:, :, None])

    # --- hard chroma cap + structural hue guard away from the shelf-water hue.
    mx = plains_col.max(axis=2, keepdims=True)
    mn = plains_col.min(axis=2, keepdims=True)
    chroma = mx - mn
    cap = 0.24
    over = np.clip((chroma - cap) / (chroma + 1e-6), 0.0, 1.0)
    lg = plains_col[:, :, 0:1] * 0.299 + plains_col[:, :, 1:2] * 0.587 + plains_col[:, :, 2:3] * 0.114
    plains_col = plains_col + (lg - plains_col) * over
    # green must lead blue (turquoise has B > G) and red must not collapse
    # -> grass can never read as shallow water whatever the fields do.
    plains_col[:, :, 2] = np.minimum(plains_col[:, :, 2], plains_col[:, :, 1] * 0.86)
    plains_col[:, :, 0] = np.maximum(plains_col[:, :, 0], plains_col[:, :, 2] * 0.95)
    plains_col = np.clip(plains_col, 0.02, 1.0)

    # 3. FOREST CANOPY MATERIAL -- see the 2D canopy layer built above; the
    #    underlay colour / stamp texture / AO / drop shadow all live there.

    # 4. HILLS & HIGHLANDS
    hills_col = np.array([0.46, 0.43, 0.30], dtype=np.float32)

    # 5. MOUNTAINS (Natural Alpine Rock - Slate & Granite Strata)
    rock_slate = np.array([0.38, 0.37, 0.41], dtype=np.float32)   # Dark mountain slate
    rock_granite = np.array([0.52, 0.51, 0.55], dtype=np.float32) # Sunlit granite face
    rock_scree = np.array([0.44, 0.42, 0.40], dtype=np.float32)   # Alpine talus / scree
    cliff_dark = np.array([0.26, 0.25, 0.28], dtype=np.float32)   # Deep rock crevice
    
    # 6. GLACIAL SNOW (Strictly Snow Peaks)
    snow_base = np.array([0.92, 0.95, 0.98], dtype=np.float32)
    snow_summit = np.array([1.00, 1.00, 1.00], dtype=np.float32)

    # --- Continuous Biome Ground Composition ---
    if progress_callback:
        progress_callback(0.92, "Compositing biome materials, optical water & surf...")
    ground_c = plains_col.copy()

    # Blend the riparian band: damp, darker, greener ground cover along the
    # carved valley (v10 -- keyed on the noisy distance-field band `riparian`,
    # no hard edge).
    riparian_turf = np.array([0.17, 0.40, 0.15], dtype=np.float32)   # lush damp meadow
    _rip_b = np.clip(riparian * 0.85, 0.0, 1.0)[:, :, None]
    ground_c = ground_c * (1.0 - _rip_b) + riparian_turf * _rip_b
    # extra damp darkening right at the waterline (strongest in the inner band)
    ground_c = ground_c * (1.0 - 0.16 * np.clip(riparian * 1.4, 0.0, 1.0)[:, :, None])

    # Forest floor: darken the ground under & around the canopy (AO from the
    # blurred density field) and tint it toward leaf-litter where the wood is
    # genuinely dense -- this shading is what gives the canopy mass its weight.
    woodland_floor = np.array([0.13, 0.22, 0.11], dtype=np.float32)
    ground_c = ground_c * (1.0 - 0.30 * canopy_ao[:, :, None])
    _wf = (_ss(0.5, 0.95, canopy_density) * treeline_factor)[:, :, None]
    ground_c = ground_c * (1.0 - 0.55 * _wf) + woodland_floor * (0.55 * _wf)

    # Blend Hills -- v12: HEAVILY NEUTERED.  Was
    #   `ground_c*(1 - w*0.75) + hills_col*(w*0.75)` on a smooth
    #   `w = clip(H_hills_prob*1.3)` -- the airbrushed khaki ramp + flat fill.
    # The dry/sat/value retarget above now carries the hill look through the
    # textured pipeline; this is only a low-cap (0.16 max) hue anchor toward
    # `hills_col`, and it rides the *perturbed* `hillw` so even the residual is
    # not a clean contour.  Grain is now crushed ~16%, not ~75%.
    h_weight = (hillw * 0.16)[:, :, None]
    ground_c = ground_c * (1.0 - h_weight) + hills_col * h_weight

    # Blend Mountain rock
    m_weight = np.clip(H_mount_prob * 1.5 + np.clip((H - 0.22)/0.25, 0.0, 1.0), 0.0, 1.0)[:, :, None]
    m_rock = rock_slate * (1.0 - np.clip((H - 0.35)/0.35, 0.0, 1.0)[:, :, None]) + rock_granite * np.clip((H - 0.35)/0.35, 0.0, 1.0)[:, :, None]
    m_rock = np.where(slope[:, :, None] < 0.12, rock_scree, m_rock)
    ground_c = ground_c * (1.0 - m_weight) + m_rock * m_weight

    # Cliff rock exposure on steep slopes in mountain/hill areas
    rock_presence = np.clip(H_mount_prob * 1.5 + H_hills_prob * 0.5, 0.0, 1.0)[:, :, None]
    cliff_factor = np.clip((slope - 0.16) / 0.20, 0.0, 1.0)[:, :, None] * rock_presence
    cliff_col = np.where(H[:, :, None] >= 0.85, rock_granite, cliff_dark)
    ground_c = ground_c * (1.0 - cliff_factor * 0.40) + cliff_col * (cliff_factor * 0.40)

    # BEACH: strand up to a wiggly upper elevation.  Width falls out of the
    # offshore gradient -- H climbs slowly out of a shelving plains coast so the
    # [0 .. beach_hi] band is many pixels wide; it climbs fast off a cliff coast
    # so the band is a sliver.  A low-freq noise wiggle + a slope taper keep the
    # sand/grass boundary from reading as a clean iso-elevation contour.
    _bwig, _, _ = iq_noised(WX * 0.06 + 21.0, WY * 0.06 - 8.0)
    _bwig2, _, _ = iq_noised(WX * 0.19 - 5.0, WY * 0.19 + 12.0)
    beach_hi = 0.056 + 0.028 * (_bwig - 0.5) * 2.0 + 0.012 * (_bwig2 - 0.5) * 2.0
    beach_hi = beach_hi * np.clip(1.0 - (slope - 0.05) / 0.30, 0.35, 1.0)
    beach_mask = np.clip((beach_hi - H) / np.maximum(beach_hi, 1e-3), 0.0, 1.0)[:, :, None]
    ground_c = ground_c * (1.0 - beach_mask) + beach_col * beach_mask

    # Snow Peaks (STRICTLY snow mountain tiles and high summits >= 0.76)
    snow_weight = np.clip(H_snow_prob * 1.6, 0.0, 1.0) * np.clip((H - 0.74) / 0.12, 0.0, 1.0)
    snow_col = snow_base * (1.0 - np.clip((H - 0.82)/0.12, 0.0, 1.0)[:, :, None]) + snow_summit * np.clip((H - 0.82)/0.12, 0.0, 1.0)[:, :, None]
    ground_c = ground_c * (1.0 - snow_weight[:, :, None]) + snow_col * snow_weight[:, :, None]

    # --- 2D forest canopy: dark connected underlay, crown stamps only texture it ---
    canopy_rgb = canopy_under_col * (1.0 + np.clip(canopy_tex, -0.75, 0.60)[:, :, None] * 1.35)
    canopy_rgb = canopy_rgb + (canopy_olive - canopy_rgb) * (0.60 * canopy_hi[:, :, None])
    canopy_rgb = canopy_rgb * (1.0 - 0.34 * canopy_sh[:, :, None])
    canopy_rgb = np.clip(canopy_rgb, 0.0, 1.0)

    # granular drop shadow cast onto the ground just off the SE margin of the wood
    ground_c = ground_c * (1.0 - 0.34 * canopy_drop[:, :, None])

    # underlay alpha: mostly opaque over the mass (raggedness is already baked
    # into canopy_density via cbn + crown bulge + dither), with crowns scalloping
    # a little past the contour so the margin is crown-shaped, not a smooth curve.
    canopy_a = np.clip(_ss(0.14, 0.42, canopy_density)
                       + 0.40 * canopy_cov * _ss(0.04, 0.22, canopy_density),
                       0.0, 1.0)[:, :, None]
    land_c = ground_c * (1.0 - canopy_a) + canopy_rgb * canopy_a

    # Lighting
    sun_color = np.array([1.18, 1.10, 0.96], dtype=np.float32)
    sky_color = np.array([0.22, 0.28, 0.40], dtype=np.float32)
    total_light = (direct_sun[:, :, None] * sun_color + sky_light[:, :, None] * sky_color + 0.12)

    snow_specular = (np.clip(Nx * half_vec[0] + Ny * half_vec[1] + Nz * half_vec[2], 0.0, 1.0)**20 * 0.25)[:, :, None] * direct_sun[:, :, None]
    land_lit = land_c * total_light + snow_weight[:, :, None] * snow_specular

    # Composite: Ocean -> Land -> Inland Rivers & Lakes.  River water is
    # composited with its coverage alpha (v10) so the waterline feathers into
    # the bank instead of a hard 1-px edge; lakes stay fully opaque.
    final_rgb = np.where(is_ocean_water[:, :, None], ocean_lit, land_lit)
    _iw_a = np.maximum(is_lake_water.astype(np.float32), river_alpha)[:, :, None]
    final_rgb = final_rgb * (1.0 - _iw_a) + inland_water_lit * _iw_a

    final_rgb = np.clip(final_rgb, 0.0, 1.0)
    final_rgb = np.power(final_rgb, 1.0 / 1.15)

    # =====================================================================
    if progress_callback:
        progress_callback(0.98, "Applying atmospheric grade, cloud shadows & aerial haze...")
    # ATMOSPHERE -- final pass over the composited RGB (v06).
    # Grades the finished image only: split-tone sun/sky, elevation-scaled
    # aerial haze, domain-warped cloud shadows, filmic S-curve + vignette.
    # Reads H / H_land_prob / NX,NY as aux buffers; runs no material or
    # lighting logic.  Sun is NW, elev ~42 deg -- matches the hillshade sun
    # (sun_x,sun_y = -0.55,-0.55) and the v03 canopy drop shadow (+x,+y = SE).
    # =====================================================================
    from scipy.ndimage import zoom as _zoom

    _lc = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    warm_col = np.array([1.00, 0.955, 0.86], dtype=np.float32)
    warm_norm = warm_col / float(warm_col @ _lc)          # unit-luminance white balance
    cool_col = np.array([0.66, 0.74, 0.90], dtype=np.float32)
    cool_norm = cool_col / float(cool_col @ _lc)
    frame_w_world = float(max_wx - min_wx)
    _rad = np.sqrt(NX * NX + NY * NY)                     # 0 centre .. ~1.35 frame corner

    # -- 1. split-tone: warm the pixels above their wide local-mean luminance,
    #    cool the ones below it.  Local mean = a 4x-downsampled wide Gaussian
    #    (sigma ~110 px full-res) so the term stays cheap.  Chroma shift capped
    #    at +-8% -- a grade, not a repaint.
    lum = final_rgb @ _lc
    _sm = gaussian_filter(lum[::4, ::4].astype(np.float32), sigma=110.0 / 4.0)
    lum_mean = _zoom(_sm, (height / _sm.shape[0], width / _sm.shape[1]), order=1)[:height, :width]
    st_t = np.clip(0.5 + (lum - lum_mean) * 3.6, 0.0, 1.0)          # 1 = lit, 0 = shade
    st_tint = cool_norm[None, None, :] * (1.0 - st_t)[:, :, None] + warm_norm[None, None, :] * st_t[:, :, None]
    st_tint = np.clip(1.0 + (st_tint - 1.0) * 0.48, 0.93, 1.07)
    final_rgb = final_rgb * st_tint

    # -- 2. aerial haze scaled by ELEVATION (near-top-down -> air column ~ how
    #    low the ground is), not screen depth.  f_lo ~0.09 at sea/lowland ->
    #    ~0.02 at peaks; +2% screen-radial at the corners only; haze colour
    #    pulled ~10% warm on the NW (sun) side.  Capped at 6% over land so the
    #    v02 plains grain and v03 canopy texture are not washed out.
    h_norm = np.clip(H / 0.80, 0.0, 1.0)
    _f_lo = np.where(is_ocean_water, 0.065, 0.09)          # v07: de-haze open water so the sea keeps its depth
    haze_f = 0.02 + (_f_lo - 0.02) * (1.0 - h_norm) ** 1.5
    haze_f = haze_f + 0.02 * np.clip((_rad - 1.10) / 0.60, 0.0, 1.0)
    haze_f = np.where(is_ocean_water, haze_f, np.minimum(haze_f, 0.05))
    _nw = np.clip(0.5 - 0.5 * (NX + NY) / 1.35, 0.0, 1.0)          # 1 at NW (top-left), 0 at SE
    haze_base = np.array([0.70, 0.76, 0.85], dtype=np.float32)
    haze_nwc = np.array([0.770, 0.782, 0.773], dtype=np.float32)   # ~10% warmer
    haze_col = haze_base[None, None, :] * (1.0 - _nw)[:, :, None] + haze_nwc[None, None, :] * _nw[:, :, None]
    final_rgb = final_rgb * (1.0 - haze_f[:, :, None]) + haze_col * haze_f[:, :, None]

    # -- 3. cloud shadows on land AND sea (the biggest win).  2-octave fBm on a
    #    FULLY domain-warped domain (never axis-aligned -- deadends.md), soft-
    #    thresholded to ~27% coverage.  Primary blob ~1/3 the island diameter,
    #    a secondary layer 1/4 of that; a high-freq displacement frays the
    #    contour (soft penumbra).  In shadow: x0.85 AND a shift toward the cool
    #    sky tint -- so the open sea gains variation + temperature, not just
    #    darkness, without touching the water model.
    _land_m = (H_land_prob >= shore_ref)
    if _land_m.any():
        _cols = np.where(np.any(_land_m, axis=0))[0]
        _rows = np.where(np.any(_land_m, axis=1))[0]
        _diam_px = 0.5 * ((_cols[-1] - _cols[0]) + (_rows[-1] - _rows[0]))
    else:
        _diam_px = 0.6 * width
    prim_cell = float(_diam_px) * frame_w_world / width / 3.3
    inv_c = 1.0 / max(prim_cell, 1.0)
    _cs = float(generator.seed % 977) * 0.1313 + 11.0

    _cw1v, _cw1dx, _cw1dy = iq_noised(WX * inv_c * 0.5 + _cs, WY * inv_c * 0.5 - _cs)
    _cw2v, _cw2dx, _cw2dy = iq_noised((WX + 130.0) * inv_c * 0.5 + _cw1dx * 1.3,
                                      (WY - 90.0) * inv_c * 0.5 + _cw1dy * 1.3)
    CWX = WX + (_cw1dx * 0.60 + _cw2dx * 0.50) * prim_cell * 0.55
    CWY = WY + (_cw1dy * 0.60 + _cw2dy * 0.50) * prim_cell * 0.55
    _cl0, _, _ = iq_noised(CWX * inv_c + _cs, CWY * inv_c - _cs)
    _cl1, _, _ = iq_noised(CWX * inv_c * 4.0 - _cs, CWY * inv_c * 4.0 + _cs)   # secondary = 1/4 cell
    # multi-scale contour fray so the shadow rim is ragged, not a smooth curve
    _clhf, _, _ = iq_noised(CWX * inv_c * 16.0 + 5.0, CWY * inv_c * 16.0 - 8.0)
    _clhf2, _, _ = iq_noised(CWX * inv_c * 33.0 - 12.0, CWY * inv_c * 33.0 + 3.0)
    cloud_field = (_cl0 * 0.55 + _cl1 * 0.45) + (_clhf - 0.5) * 0.05 + (_clhf2 - 0.5) * 0.02
    cl_thr, cl_soft = 0.615, 0.11
    cloud_sh = _ss(cl_thr - cl_soft, cl_thr + cl_soft, cloud_field)           # 1 = full shadow
    _csh = cloud_sh[:, :, None]
    final_rgb = final_rgb * (1.0 - 0.15 * _csh)
    final_rgb = final_rgb * (1.0 + (cool_norm[None, None, :] - 1.0) * 0.14 * _csh)

    # -- 4. grade: filmic S-curve (pivot 0.45, strength 1.12) with a soft
    #    highlight knee so the snow peaks keep headroom, then a <=4% cool
    #    corner vignette.  Nothing else.
    _p, _s, _knee = 0.45, 1.12, 0.86
    y = _p + (final_rgb - _p) * _s
    _over = np.maximum(0.0, y - _knee)
    y = np.where(y > _knee, _knee + _over / (1.0 + _over / (1.0 - _knee) * 1.20), y)
    final_rgb = np.maximum(y, 0.0)
    _vig = np.clip((_rad - 0.90) / 0.90, 0.0, 1.0) ** 2
    final_rgb = final_rgb * (1.0 - 0.04 * _vig)[:, :, None]
    final_rgb = final_rgb * (1.0 + (cool_norm[None, None, :] - 1.0) * 0.05 * _vig[:, :, None])

    final_rgb = np.clip(final_rgb, 0.0, 1.0)

    img_uint8 = (final_rgb * 255).astype(np.uint8)
    surf = pygame.surfarray.make_surface(np.transpose(img_uint8, (1, 0, 2)))
    if progress_callback:
        progress_callback(1.00, "Topographic elevation map synthesis complete!")
    return surf


HeightMapGenerator.generate_topographic_surface = _generate_topographic_surface_impl
render_terrain = _generate_topographic_surface_impl
