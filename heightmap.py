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


def get_cached_topographic_surface(seed, bbox, tiles=None, layout=None, canvas_w=2400, canvas_h=1800):
    """Return pre-rendered, 4x Ultra-HD topographic elevation surface conforming closely to the hex tile map."""
    tile_sig = tuple((t.name, round(getattr(t, 'elevation', 0.0), 3), bool(getattr(t, 'is_ocean', False))) for t in tiles) if tiles else None
    cache_key = (seed, bbox, canvas_w, canvas_h, tile_sig)
    if cache_key in _TOPOGRAPHIC_SURFACE_CACHE:
        return _TOPOGRAPHIC_SURFACE_CACHE[cache_key]

    generator = HeightMapGenerator(seed=seed if seed is not None else 42)
    surf = generator.generate_topographic_surface(bbox, tiles=tiles, layout=layout, width=canvas_w, height=canvas_h)
    _TOPOGRAPHIC_SURFACE_CACHE[cache_key] = surf
    return surf
def _generate_topographic_surface_impl(generator, bbox, tiles=None, layout=None, width: int = 2400, height: int = 1800) -> "pygame.Surface":
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

    # General Land Shelf: Gentle coastal slope creating large, wide beaches
    t_land = np.clip((H_land_prob - 0.28) / 0.18, 0.0, 1.0)
    land_shelf = np.where(
        H_land_prob < 0.28,
        (H_land_prob - 0.28) * 0.85,
        -0.02 + 0.10 * (t_land ** 1.3) + (H_land_prob - 0.46) * 0.04
    )

    # Hills: Gentle rolling multi-octave mounds
    hill_fbm, _, _ = iq_noised(WX_warped / (HEX_SIZE * 1.8), WY_warped / (HEX_SIZE * 1.8))
    hill_ridge = H_hills_prob * (0.26 + 0.14 * hill_fbm)

    # Mountains: Continuous alpine ranges with natural IQ ridged fractal relief
    mount_range_mask = np.clip(H_mount_prob * 1.5 + H_snow_prob * 0.6, 0.0, 1.0) ** 0.85
    mountain_ridge = mount_range_mask * (0.16 + 0.88 * mount_relief)

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
    is_river_water = np.zeros((height, width), dtype=bool)
    is_lake_water = np.zeros((height, width), dtype=bool)
    river_valley_bank = np.zeros((height, width), dtype=np.float32)

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

            # If still no downhill path: only form a lake if trapped in an actual high mountain valley
            if best_dir is None:
                if len(pts) >= 8 and h_now >= 0.16:
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
                if len(pts) >= 8 and h_now >= 0.16:
                    reached_lake = True
                    pit_point = (p_pix_x, p_pix_y, h_now)
                elif len(pts) >= 8:
                    reached_ocean = True
                break
            visited_pts.add(grid_pt)
            pts.append((cur_x, cur_y, p_pix_x, p_pix_y, base_ground_H[p_pix_y, p_pix_x]))

        # Hydraulic River Valley Carving
        if (reached_ocean or reached_lake) and len(pts) >= 8:
            valid_rivers_count += 1
            n_pts = len(pts)
            water_levels = np.array([pts[k][4] for k in range(n_pts)], dtype=np.float32)
            # Enforce strict monotonicity and coast blend down to 0.0 at ocean mouth
            for k in range(1, n_pts):
                water_levels[k] = min(water_levels[k], water_levels[k-1] - 0.0005)
            if reached_ocean:
                for k in range(n_pts):
                    t_coast = max(0.0, (k - (n_pts - 8)) / 8.0)
                    water_levels[k] = water_levels[k] * (1.0 - t_coast) + 0.002 * t_coast

            for idx in range(n_pts - 1):
                t_prog = idx / float(n_pts)
                p1 = (pts[idx][2], pts[idx][3])
                p2 = (pts[idx + 1][2], pts[idx + 1][3])
                seg_hw = water_levels[idx]

                rw = 1.8 + t_prog * 2.8          # River water width radius (1.8 to 4.6px)
                vw = rw + 8.0 + t_prog * 6.0     # Carved valley width radius (10 to 18px)

                min_x_seg = max(0, int(min(p1[0], p2[0]) - vw - 2))
                max_x_seg = min(width - 1, int(max(p1[0], p2[0]) + vw + 2))
                min_y_seg = max(0, int(min(p1[1], p2[1]) - vw - 2))
                max_y_seg = min(height - 1, int(max(p1[1], p2[1]) + vw + 2))

                if max_x_seg > min_x_seg and max_y_seg > min_y_seg:
                    grid_y, grid_x = np.ogrid[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1]
                    vx = p2[0] - p1[0]
                    vy = p2[1] - p1[1]
                    seg_len2 = max(1e-4, vx**2 + vy**2)
                    proj = ((grid_x - p1[0]) * vx + (grid_y - p1[1]) * vy) / seg_len2
                    proj = np.clip(proj, 0.0, 1.0)
                    near_x = p1[0] + proj * vx
                    near_y = p1[1] + proj * vy
                    dist = np.sqrt((grid_x - near_x)**2 + (grid_y - near_y)**2)

                    # River Channel (ONLY on land, terminates cleanly at sea level)
                    sub_land = H_land_prob[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1] >= 0.30
                    in_river = (dist <= rw) & sub_land
                    is_river_water[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1] |= in_river
                    
                    sub_w_H = water_surface_H[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1]
                    # Water level sits at seg_hw - 0.003, seamlessly recessed below ground
                    water_surface_H[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1] = np.where(
                        in_river, np.maximum(sub_w_H, seg_hw - 0.003), sub_w_H
                    )

                    # Valley Carving (cuts terrain smoothly down to river level)
                    in_valley = dist <= vw
                    t_val = np.clip((dist - rw) / np.maximum(1e-4, vw - rw), 0.0, 1.0)
                    s_val = t_val * t_val * (3.0 - 2.0 * t_val)
                    
                    sub_H = carved_ground_H[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1]
                    target_carved_H = (seg_hw - 0.008) * (1.0 - s_val) + sub_H * s_val
                    carved_ground_H[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1] = np.where(
                        in_valley, np.minimum(sub_H, target_carved_H), sub_H
                    )
                    sub_bank = river_valley_bank[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1]
                    river_valley_bank[min_y_seg:max_y_seg+1, min_x_seg:max_x_seg+1] = np.where(
                        in_valley, np.maximum(sub_bank, (1.0 - t_val)), sub_bank
                    )

            # Natural Mountain Basin Depression Flooding (Tightly Contoured, No Big Ovals)
            if reached_lake and pit_point is not None:
                px_pit, py_pit, h_pit = pit_point
                H_lake = h_pit + 0.018  # Shallow natural alpine tarn level
                
                from collections import deque
                q_bfs = deque([(py_pit, px_pit)])
                lake_submask = np.zeros((height, width), dtype=bool)
                lake_submask[py_pit, px_pit] = True
                max_rad = HEX_SIZE * 0.45  # Small-to-medium natural basin size

                while q_bfs:
                    cy_l, cx_l = q_bfs.popleft()
                    for dy_l, dx_l in ((-1,0), (1,0), (0,-1), (0,1)):
                        ny_l, nx_l = cy_l + dy_l, cx_l + dx_l
                        if 0 <= ny_l < height and 0 <= nx_l < width and not lake_submask[ny_l, nx_l]:
                            dist = math.sqrt((nx_l - px_pit)**2 + (ny_l - py_pit)**2)
                            # Organic fractal boundary shaping (fjords, coves, jagged inlets)
                            n_f, _, _ = iq_noised(nx_l / 14.0, ny_l / 14.0)
                            dist_warped = dist * (0.80 + 0.40 * n_f)
                            if dist_warped <= max_rad and carved_ground_H[ny_l, nx_l] <= H_lake + 0.002:
                                lake_submask[ny_l, nx_l] = True
                                q_bfs.append((ny_l, nx_l))

                # Apply flat lake surface
                is_lake_water |= lake_submask
                water_surface_H = np.where(lake_submask, H_lake, water_surface_H)
                carved_ground_H = np.where(lake_submask, np.minimum(carved_ground_H, H_lake - 0.008), carved_ground_H)

            if valid_rivers_count >= 6:
                break

    is_inland_water = is_river_water | is_lake_water

    # -------------------------------------------------------------------------
    # Tall, Pointy, 10x Smaller Whole Trees (Strictly in Forest Biomes)
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

    # 10x smaller tree spacing: ~2.6px per tree cell
    tree_cell_size = 2.6
    u_grid = WX / tree_cell_size
    v_grid = WY / tree_cell_size

    n_u = np.floor(u_grid)
    n_v = np.floor(v_grid)
    f_u = u_grid - n_u
    f_v = v_grid - n_v

    step_u = np.where(f_u < 0.5, 1.0, 0.0)
    step_v = np.where(f_v < 0.5, 1.0, 0.0)

    # Macro forest species / density variation (bb in IQ code)
    bb_scale = 1.0 / (HEX_SIZE * 1.5)
    bb_val, _, _ = iq_noised(WX * bb_scale, WY * bb_scale)
    bb = bb_val - 0.50

    kMaxTreeHeight = 0.024
    base_tree_width = 1.85  # Tiny 1.85px radius

    tree_height_accum = np.zeros_like(WX, dtype=np.float32)
    tree_mat_accum = np.zeros_like(WX, dtype=np.float32)
    tree_hei_accum = np.zeros_like(WX, dtype=np.float32)

    for j in range(2):
        for i in range(2):
            g_u = float(i) - step_u
            g_v = float(j) - step_v

            cell_u = n_u + g_u
            cell_v = n_v + g_v

            o_u, o_v = hash2_vec(cell_u, cell_v)
            v_u, v_v = hash2_vec(cell_u + 13.1, cell_v + 71.7)

            # Exact world center position of this tree instance
            tree_cx = (cell_u + o_u) * tree_cell_size
            tree_cy = (cell_v + o_v) * tree_cell_size

            # Organic meandering warp for forest boundary (80% hex alignment + 20% natural fractal meander)
            warp_fx = (np.sin(tree_cy * 0.075 + 1.3) * 0.65 + np.cos(tree_cx * 0.045 - tree_cy * 0.035) * 0.35)
            warp_fy = (np.cos(tree_cx * 0.075 + 2.7) * 0.65 + np.sin(tree_cx * 0.035 + tree_cy * 0.045) * 0.35)
            tree_cx_w = tree_cx + warp_fx * (HEX_SIZE * 0.20)
            tree_cy_w = tree_cy + warp_fy * (HEX_SIZE * 0.20)

            # Check if this WHOLE tree center is located in a Forest hex
            q_tc = (_SQRT3 / 3.0 * tree_cx_w - 1.0 / 3.0 * tree_cy_w) / HEX_SIZE
            r_tc = (2.0 / 3.0 * tree_cy_w) / HEX_SIZE
            rx_tc = np.round(q_tc).astype(np.int32)
            ry_tc = np.round(r_tc).astype(np.int32)
            rz_tc = np.round(-q_tc - r_tc).astype(np.int32)
            dx_tc = np.abs(rx_tc - q_tc)
            dy_tc = np.abs(ry_tc - r_tc)
            dz_tc = np.abs(rz_tc - (-q_tc - r_tc))
            mx_tc = (dx_tc > dy_tc) & (dx_tc > dz_tc)
            my_tc = (~mx_tc) & (dy_tc > dz_tc)
            q_tree = np.where(mx_tc, -ry_tc - rz_tc, rx_tc)
            r_tree = np.where(my_tc, -rx_tc - rz_tc, ry_tc)

            q_tr_clamped = np.clip(q_tree - min_q, 0, q_size - 1)
            r_tr_clamped = np.clip(r_tree - min_r, 0, r_size - 1)
            in_tr_bounds = (q_tree >= min_q) & (q_tree <= max_q) & (r_tree >= min_r) & (r_tree <= max_r)
            
            # Binary whole-tree forest presence: 1.0 if tree center is in forest, 0.0 otherwise
            is_forest_tree = np.where(in_tr_bounds, grid_forest[r_tr_clamped, q_tr_clamped], 0.0)

            # Natural density variation inside forests & alpine treeline cutoff, excluding inland water
            tree_present = (is_forest_tree > 0.5) & (v_v < 0.88) & (treeline_factor > 0.05) & (~is_inland_water)

            r_u = (g_u - f_u + o_u) * tree_cell_size
            r_v = (g_v - f_v + o_v) * tree_cell_size

            t_height = kMaxTreeHeight * (0.6 + 0.6 * v_u) * (0.3 + 0.7 * treeline_factor)
            t_width = base_tree_width * (0.7 + 0.3 * v_u + 0.2 * v_v)

            # Conifer vs deciduous spire
            t_width = np.where(bb < 0.0, t_width * 0.70, t_width)
            t_height = np.where(bb >= 0.0, t_height * 0.85, t_height)

            r_dist = np.sqrt(r_u**2 + r_v**2)
            q_norm = r_dist / np.maximum(1e-4, t_width)

            # Tall, pointy conical / gothic spire profile
            in_crown = (q_norm < 1.0) & tree_present
            pointy_profile = np.maximum(0.0, 1.0 - q_norm) ** 0.65
            dome_h = np.where(in_crown, t_height * pointy_profile, 0.0)

            cand_mat = 0.5 * hash1_vec(cell_u, cell_v + 111.0) + np.where(bb > 0.0, 0.5, 0.0)
            cand_hei = np.where(in_crown, pointy_profile, 0.0)

            is_higher = dome_h > tree_height_accum
            tree_height_accum = np.where(is_higher, dome_h, tree_height_accum)
            tree_mat_accum = np.where(is_higher, cand_mat, tree_mat_accum)
            tree_hei_accum = np.where(is_higher, cand_hei, tree_hei_accum)

    # Complete whole-tree canopy relief (no partial tree slicing)
    tree_canopy_relief = tree_height_accum

    # Combine Base Elevation with Carved Valleys, Flat Inland Water, and Trees
    raw_H = np.where(is_inland_water, water_surface_H, carved_ground_H + tree_canopy_relief)

    deep_ocean_mask = H_land_prob < 0.10
    raw_H = np.where(deep_ocean_mask, np.minimum(-0.20, raw_H), raw_H)

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

    # Flatten normals on inland water (rivers and lakes are perfectly flat and smooth)
    Nx = np.where(is_inland_water, 0.0, Nx)
    Ny = np.where(is_inland_water, 0.0, Ny)
    Nz = np.where(is_inland_water, 1.0, Nz)
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

    # Ocean Water & Coastal Waters
    is_ocean_water = H < 0.0
    water_depth = np.clip(-H / 0.25, 0.0, 1.0)
    deep_ocean = np.array([0.05, 0.10, 0.22], dtype=np.float32)
    mid_ocean = np.array([0.08, 0.20, 0.38], dtype=np.float32)
    shallow_shelf = np.array([0.14, 0.40, 0.52], dtype=np.float32)
    coastal_turquoise = np.array([0.25, 0.58, 0.62], dtype=np.float32)

    w_col = np.where(
        water_depth[:, :, None] > 0.30,
        mid_ocean * (1.0 - (water_depth[:, :, None]-0.30)/0.70) + deep_ocean * ((water_depth[:, :, None]-0.30)/0.70),
        coastal_turquoise * (1.0 - water_depth[:, :, None]/0.30) + shallow_shelf * (water_depth[:, :, None]/0.30)
    )
    half_vec = np.array([sun_x, sun_y, sun_z + 1.0], dtype=np.float32)
    half_vec /= np.linalg.norm(half_vec)
    specular = np.clip(Nx * half_vec[0] + Ny * half_vec[1] + Nz * half_vec[2], 0.0, 1.0)**28 * 0.25
    ocean_lit = w_col * (0.60 + 0.40 * direct_sun[:, :, None]) + specular[:, :, None]

    # --- Inland Rivers & Lakes Flat Smooth Water Shader ---
    inland_water_depth = np.clip((water_surface_H - carved_ground_H) / 0.025, 0.0, 1.0)[:, :, None]
    lake_deep = np.array([0.10, 0.28, 0.54], dtype=np.float32)
    lake_shallow = np.array([0.22, 0.52, 0.68], dtype=np.float32)
    inland_water_col = lake_shallow * (1.0 - inland_water_depth) + lake_deep * inland_water_depth
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

    # 2. VIBRANT, RICH & DETAILED PLAINS (Multi-octave lush grassland, clover meadow, rich soil)
    grass_lush = np.array([0.28, 0.54, 0.24], dtype=np.float32)     # Deep emerald meadow
    grass_meadow = np.array([0.38, 0.62, 0.28], dtype=np.float32)   # Bright sunlit pasture
    grass_savannah = np.array([0.48, 0.58, 0.30], dtype=np.float32) # Warm savannah/steppe
    grass_loam = np.array([0.34, 0.45, 0.22], dtype=np.float32)     # Rich humus loam
    
    t_grass1 = np.clip((plains_fbm - 0.35) / 0.30, 0.0, 1.0)[:, :, None]
    t_grass2 = np.clip((rw_val - 0.45) / 0.30, 0.0, 1.0)[:, :, None]
    t_grass3 = np.clip((qw_val - 0.40) / 0.35, 0.0, 1.0)[:, :, None]
    
    plains_col = grass_lush * (1.0 - t_grass1) + grass_meadow * t_grass1
    plains_col = plains_col * (1.0 - t_grass2 * 0.35) + grass_savannah * (t_grass2 * 0.35)
    plains_col = plains_col * (1.0 - t_grass3 * 0.25) + grass_loam * (t_grass3 * 0.25)

    # 3. IQ TREES & FOREST CANOPY MATERIAL (Individual tree species colors & canopy volume AO)
    forest_spruce = np.array([0.05, 0.18, 0.08], dtype=np.float32)  # Dark conifer needle
    forest_emerald = np.array([0.12, 0.35, 0.14], dtype=np.float32) # Vibrant emerald spruce
    forest_olive = np.array([0.18, 0.32, 0.12], dtype=np.float32)   # Olive canopy
    forest_golden = np.array([0.28, 0.36, 0.14], dtype=np.float32)  # Golden pine

    woodland_floor = np.array([0.20, 0.42, 0.18], dtype=np.float32) # Deep forest floor

    t_mat = tree_mat_accum[:, :, None]
    tree_base_col = np.where(
        t_mat < 0.35,
        forest_spruce * (1.0 - t_mat/0.35) + forest_emerald * (t_mat/0.35),
        np.where(
            t_mat < 0.70,
            forest_emerald * (1.0 - (t_mat-0.35)/0.35) + forest_olive * ((t_mat-0.35)/0.35),
            forest_olive * (1.0 - (t_mat-0.70)/0.30) + forest_golden * ((t_mat-0.70)/0.30)
        )
    )
    crown_ao = (0.50 + 0.50 * tree_hei_accum[:, :, None])
    forest_canopy_color = tree_base_col * crown_ao

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
    ground_c = plains_col.copy()

    # Blend Riparian lush green valley slopes along carved river valleys
    riparian_turf = np.array([0.22, 0.50, 0.20], dtype=np.float32)
    ground_c = ground_c * (1.0 - river_valley_bank[:, :, None] * 0.70) + riparian_turf * (river_valley_bank[:, :, None] * 0.70)

    # Blend Woodland Floor on forest hexes (modulated by treeline so high mountains stay stone)
    f_floor_weight = np.clip(H_forest_prob * 1.4, 0.0, 1.0) * treeline_factor
    ground_c = ground_c * (1.0 - f_floor_weight[:, :, None] * 0.75) + woodland_floor * (f_floor_weight[:, :, None] * 0.75)

    # Blend Hills
    h_weight = np.clip(H_hills_prob * 1.3, 0.0, 1.0)[:, :, None]
    ground_c = ground_c * (1.0 - h_weight * 0.75) + hills_col * (h_weight * 0.75)

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

    # EXPANSIVE BEACHES: Wide sandy beaches extending along coast up to H=0.075
    beach_mask = np.clip((0.075 - H) / 0.075, 0.0, 1.0)[:, :, None]
    ground_c = ground_c * (1.0 - beach_mask) + beach_col * beach_mask

    # Snow Peaks (STRICTLY snow mountain tiles and high summits >= 0.76)
    snow_weight = np.clip(H_snow_prob * 1.6, 0.0, 1.0) * np.clip((H - 0.74) / 0.12, 0.0, 1.0)
    snow_col = snow_base * (1.0 - np.clip((H - 0.82)/0.12, 0.0, 1.0)[:, :, None]) + snow_summit * np.clip((H - 0.82)/0.12, 0.0, 1.0)[:, :, None]
    ground_c = ground_c * (1.0 - snow_weight[:, :, None]) + snow_col * snow_weight[:, :, None]

    # --- Place Green 3D Tree Canopies on top of ground (TREES ARE ALWAYS GREEN) ---
    tree_mask = np.clip(tree_height_accum / 0.003, 0.0, 1.0)[:, :, None]
    land_c = ground_c * (1.0 - tree_mask) + forest_canopy_color * tree_mask

    # Lighting
    sun_color = np.array([1.18, 1.10, 0.96], dtype=np.float32)
    sky_color = np.array([0.22, 0.28, 0.40], dtype=np.float32)
    total_light = (direct_sun[:, :, None] * sun_color + sky_light[:, :, None] * sky_color + 0.12)

    snow_specular = (np.clip(Nx * half_vec[0] + Ny * half_vec[1] + Nz * half_vec[2], 0.0, 1.0)**20 * 0.25)[:, :, None] * direct_sun[:, :, None]
    land_lit = land_c * total_light + snow_weight[:, :, None] * snow_specular

    # Composite: Ocean -> Land -> Inland Rivers & Lakes (Smooth untextured flat water)
    final_rgb = np.where(is_ocean_water[:, :, None], ocean_lit, land_lit)
    final_rgb = np.where(is_inland_water[:, :, None], inland_water_lit, final_rgb)

    final_rgb = np.clip(final_rgb, 0.0, 1.0)
    final_rgb = np.power(final_rgb, 1.0 / 1.15)

    img_uint8 = (final_rgb * 255).astype(np.uint8)
    surf = pygame.surfarray.make_surface(np.transpose(img_uint8, (1, 0, 2)))
    return surf


HeightMapGenerator.generate_topographic_surface = _generate_topographic_surface_impl
