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
from hexmap import rectangular_hex_layout, axial_neighbors, axial_to_offset


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
            return self._lerp_color((78, 145, 88), (68, 130, 75), t)
        elif h < 0.48:
            t = (h - 0.22) / 0.26
            return self._lerp_color((52, 108, 58), (76, 114, 62), t)
        elif h < 0.72:
            t = (h - 0.48) / 0.24
            return self._lerp_color((135, 122, 84), (120, 108, 92), t)
        elif h < 0.88:
            t = (h - 0.72) / 0.16
            return self._lerp_color((138, 134, 140), (175, 172, 180), t)
        else:
            t = min(1.0, (h - 0.88) / 0.12)
            return self._lerp_color((215, 222, 235), (245, 250, 255), t)

    def generate_river_paths(self) -> list[list[tuple[float, float]]]:
        """Generate 5 to 7 continuous natural river paths starting from mountain springs down to the ocean."""
        import numpy as np
        spring_candidates = []
        sample_ny = np.linspace(-0.82, 0.82, 32)
        sample_nx = np.linspace(-0.82, 0.82, 32)
        for s_ny in sample_ny:
            for s_nx in sample_nx:
                h_val = self.get_continuous_height(float(s_nx), float(s_ny))
                if 0.48 <= h_val <= 0.82:
                    spring_candidates.append((float(s_nx), float(s_ny), h_val))

        rng = random.Random(self.seed + 12345)
        rng.shuffle(spring_candidates)

        selected_springs = []
        for sc in spring_candidates:
            if all((sc[0] - prev[0])**2 + (sc[1] - prev[1])**2 > 0.15 for prev in selected_springs):
                selected_springs.append(sc)
                if len(selected_springs) >= 6:
                    break

        river_paths = []
        for sx, sy, _ in selected_springs:
            path = [(sx, sy)]
            cur_x, cur_y = sx, sy
            step_len = 0.016
            for _ in range(130):
                eps = 0.012
                h_c = self.get_continuous_height(cur_x, cur_y)
                if h_c <= -0.04:
                    break
                h_right = self.get_continuous_height(cur_x + eps, cur_y)
                h_up = self.get_continuous_height(cur_x, cur_y + eps)
                dhx = (h_right - h_c) / eps
                dhy = (h_up - h_c) / eps

                grad_mag = math.sqrt(dhx * dhx + dhy * dhy)
                if grad_mag < 1e-4:
                    gx, gy = -cur_x, -cur_y
                else:
                    gx, gy = -dhx / grad_mag, -dhy / grad_mag

                # Natural meander noise
                meander_val, _, _ = self.noised_scalar(cur_x * 7.0, cur_y * 7.0)
                mx, my = -gy * meander_val * 0.40, gx * meander_val * 0.40

                dir_x = gx + mx
                dir_y = gy + my
                d_len = math.sqrt(dir_x * dir_x + dir_y * dir_y)
                if d_len > 0:
                    dir_x /= d_len
                    dir_y /= d_len

                cur_x += dir_x * step_len
                cur_y += dir_y * step_len
                path.append((cur_x, cur_y))
            if len(path) >= 6:
                river_paths.append(path)
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


def get_cached_topographic_surface(seed, bbox, canvas_w=2400, canvas_h=1800):
    """Return pre-rendered, 4x Ultra-HD topographic elevation surface with contour lines and hillshading."""
    cache_key = (seed, bbox, canvas_w, canvas_h)
    if cache_key in _TOPOGRAPHIC_SURFACE_CACHE:
        return _TOPOGRAPHIC_SURFACE_CACHE[cache_key]

    generator = HeightMapGenerator(seed=seed if seed is not None else 42)
    surf = generator.generate_topographic_surface(bbox, width=canvas_w, height=canvas_h)
    _TOPOGRAPHIC_SURFACE_CACHE[cache_key] = surf
    return surf


def _generate_topographic_surface_impl(generator, bbox, width: int = 2400, height: int = 1800) -> "pygame.Surface":
    """Render an Ultra-HD photorealistic 3D raymarched terrain surface with cast shadows, PBR lighting, and biomes."""
    import pygame
    import numpy as np

    x0, y0, x1, y1 = bbox
    pad_x = (x1 - x0) * 0.18
    pad_y = (y1 - y0) * 0.18
    min_wx = x0 - pad_x
    max_wx = x1 + pad_x
    min_wy = y0 - pad_y
    max_wy = y1 + pad_y

    cx_center = (x0 + x1) / 2.0
    cy_center = (y0 + y1) / 2.0
    span_x = (x1 - x0) / 2.0
    span_y = (y1 - y0) / 2.0

    # Meshgrid of normalized coords
    y_vals = np.linspace(min_wy, max_wy, height, dtype=np.float32)
    x_vals = np.linspace(min_wx, max_wx, width, dtype=np.float32)
    WX, WY = np.meshgrid(x_vals, y_vals)

    NX = (WX - cx_center) / span_x
    NY = (WY - cy_center) / span_y

    # Continuous Heightfield Evaluation
    R_sq = NX**2 + NY**2
    continent_base = 0.54 - 0.76 * R_sq

    diag = NX * math.cos(generator.spine_angle) + NY * math.sin(generator.spine_angle) + generator.spine_offset
    ridge = np.exp(-4.2 * (diag**2)) * 0.38

    # Inigo Quilez 10-Octave Derivative Erosion fBm
    scale = 3.2
    PX = NX * scale
    PY = NY * scale

    a = np.zeros_like(NX, dtype=np.float32)
    b = 1.0
    dx_accum = np.zeros_like(NX, dtype=np.float32)
    dy_accum = np.zeros_like(NY, dtype=np.float32)
    noise_tbl = generator.noise_table
    m2 = generator.m2

    for i in range(10):
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

        erosion_term = 1.0 + (dx_accum**2 + dy_accum**2)
        a += b * n_val / erosion_term

        b *= 0.50
        npx = 2.0 * (m2[0, 0] * PX + m2[0, 1] * PY)
        npy = 2.0 * (m2[1, 0] * PX + m2[1, 1] * PY)
        PX, PY = npx, npy

    H_noise = (a - 0.9) * 0.75
    raw_H = continent_base + ridge + H_noise
    H = np.where(raw_H > 0.0, raw_H * 0.92, raw_H)

    # Realistic 3D Analytical Surface Normals (Balanced gradient scale 0.14)
    height_exaggeration = 0.14
    dHx = np.gradient(H, axis=1) * (width / 2.0) * height_exaggeration
    dHy = np.gradient(H, axis=0) * (height / 2.0) * height_exaggeration
    Nz = np.ones_like(H, dtype=np.float32)
    norm = np.sqrt(dHx**2 + dHy**2 + Nz**2)
    Nx = -dHx / norm
    Ny = -dHy / norm
    Nz = Nz / norm

    slope = 1.0 - Nz

    # Natural Sun Lighting (Higher altitude, balanced angles)
    sun_x, sun_y, sun_z = -0.55, -0.55, 0.65
    sun_len = math.sqrt(sun_x**2 + sun_y**2 + sun_z**2)
    sun_x /= sun_len
    sun_y /= sun_len
    sun_z /= sun_len

    NdotL = np.clip(Nx * sun_x + Ny * sun_y + Nz * sun_z, 0.0, 1.0)
    diffuse_sun = np.power(NdotL, 1.05)

    # Soft Ambient Sky Light (Never pitch black in shadows)
    sky_light = Nz * 0.60 + 0.40

    # Subtle, Crisp Mountain Shadows (Tight local shadows behind peaks)
    step_dx = 1.8
    step_dy = 1.8
    step_dz = 0.040
    shadow_mask = np.ones((height, width), dtype=np.float32)

    for s in range(1, 20):
        ox = int(round(s * step_dx))
        oy = int(round(s * step_dy))
        dz = s * step_dz
        if oy >= height or ox >= width:
            break
        occluder = np.full_like(H, -1.0)
        occluder[oy:, ox:] = H[:-oy, :-ox]
        diff = occluder - (H + dz)
        in_shadow = diff > 0.002
        penumbra = np.clip(1.0 - diff * 6.0, 0.35, 1.0)
        shadow_mask = np.where(in_shadow, np.minimum(shadow_mask, penumbra), shadow_mask)

    direct_sun = diffuse_sun * shadow_mask

    # Compact, Delicate Ocean Depth (Fine coastal fringe, not chunky blobs)
    is_water = H < 0.0
    water_depth = np.clip(-H / 0.25, 0.0, 1.0)

    deep_ocean = np.array([0.05, 0.10, 0.22], dtype=np.float32)     # Abyssal deep blue
    mid_ocean = np.array([0.08, 0.20, 0.38], dtype=np.float32)      # Deep sea
    shallow_shelf = np.array([0.12, 0.35, 0.48], dtype=np.float32)  # Coastal shelf
    coastal_sand = np.array([0.22, 0.50, 0.52], dtype=np.float32)   # Delicate turquoise shore

    w_col = np.where(
        water_depth[:, :, None] > 0.35,
        mid_ocean * (1.0 - (water_depth[:, :, None]-0.35)/0.65) + deep_ocean * ((water_depth[:, :, None]-0.35)/0.65),
        coastal_sand * (1.0 - water_depth[:, :, None]/0.35) + shallow_shelf * (water_depth[:, :, None]/0.35)
    )

    half_vec = np.array([sun_x, sun_y, sun_z + 1.0], dtype=np.float32)
    half_vec /= np.linalg.norm(half_vec)
    specular = np.clip(Nx * half_vec[0] + Ny * half_vec[1] + Nz * half_vec[2], 0.0, 1.0)**28 * 0.25
    w_lit = w_col * (0.60 + 0.40 * direct_sun[:, :, None]) + specular[:, :, None]

    # Land Materials & Continuous Alpine Peak Gradients
    beach = np.array([0.74, 0.69, 0.52], dtype=np.float32)
    plains = np.array([0.28, 0.48, 0.24], dtype=np.float32)
    forest = np.array([0.16, 0.32, 0.18], dtype=np.float32)
    hills = np.array([0.46, 0.42, 0.30], dtype=np.float32)
    rock_strata = np.array([0.42, 0.40, 0.44], dtype=np.float32)
    cliff_dark = np.array([0.26, 0.25, 0.28], dtype=np.float32)
    snow_base = np.array([0.88, 0.91, 0.95], dtype=np.float32)
    snow_summit = np.array([0.98, 0.99, 1.00], dtype=np.float32)   # Crisp razor-sharp peak snow

    land_c = np.zeros((height, width, 3), dtype=np.float32)

    # Beach [0.0, 0.04]
    t_b = np.clip(H / 0.04, 0.0, 1.0)[:, :, None]
    land_c = np.where(H[:, :, None] < 0.04, beach * (1.0 - t_b) + plains * t_b, land_c)

    # Plains [0.04, 0.24]
    t_p = np.clip((H - 0.04) / 0.20, 0.0, 1.0)[:, :, None]
    land_c = np.where((H[:, :, None] >= 0.04) & (H[:, :, None] < 0.24), plains * (1.0 - t_p) + forest * t_p, land_c)

    # Forest [0.24, 0.48]
    t_f = np.clip((H - 0.24) / 0.24, 0.0, 1.0)[:, :, None]
    land_c = np.where((H[:, :, None] >= 0.24) & (H[:, :, None] < 0.48), forest * (1.0 - t_f) + hills * t_f, land_c)

    # Hills [0.48, 0.68]
    t_h = np.clip((H - 0.48) / 0.20, 0.0, 1.0)[:, :, None]
    land_c = np.where((H[:, :, None] >= 0.48) & (H[:, :, None] < 0.68), hills * (1.0 - t_h) + rock_strata * t_h, land_c)

    # Mountains [0.68, 0.84]
    t_m = np.clip((H - 0.68) / 0.16, 0.0, 1.0)[:, :, None]
    land_c = np.where((H[:, :, None] >= 0.68) & (H[:, :, None] < 0.84), rock_strata * (1.0 - t_m) + snow_base * t_m, land_c)

    # Snow Summits [>= 0.84] with pointy peak shading
    t_peak = np.clip((H - 0.84) / 0.20, 0.0, 1.0)[:, :, None]
    land_c = np.where(H[:, :, None] >= 0.84, snow_base * (1.0 - t_peak) + snow_summit * t_peak, land_c)

    # Cliff Face Exposure on steep slopes (> 28 deg)
    cliff_factor = np.clip((slope - 0.10) / 0.25, 0.0, 1.0)[:, :, None]
    cliff_col = np.where(H[:, :, None] >= 0.88, rock_strata, cliff_dark)
    land_c = land_c * (1.0 - cliff_factor * 0.70) + cliff_col * (cliff_factor * 0.70)

    # Natural Balanced Lighting
    sun_color = np.array([1.18, 1.10, 0.96], dtype=np.float32)
    sky_color = np.array([0.22, 0.28, 0.40], dtype=np.float32)
    total_light = (direct_sun[:, :, None] * sun_color + sky_light[:, :, None] * sky_color + 0.12)

    # Crisp Glacial Crest Specular
    snow_mask = np.clip((H - 0.78) / 0.18, 0.0, 1.0)[:, :, None]
    snow_specular = (np.clip(Nx * half_vec[0] + Ny * half_vec[1] + Nz * half_vec[2], 0.0, 1.0)**20 * 0.25)[:, :, None] * direct_sun[:, :, None]

    land_lit = land_c * total_light + snow_mask * snow_specular

    # -------------------------------------------------------------
    # Procedural River Overlay & Fluvial Corridors
    # -------------------------------------------------------------
    river_paths = generator.generate_river_paths()
    generator.river_paths = river_paths

    river_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    bank_surf = pygame.Surface((width, height), pygame.SRCALPHA)

    for path in river_paths:
        if len(path) < 2:
            continue
        pts = []
        for nx_p, ny_p in path:
            px_val = int((nx_p * span_x + cx_center - min_wx) / (max_wx - min_wx) * width)
            py_val = int((ny_p * span_y + cy_center - min_wy) / (max_wy - min_wy) * height)
            pts.append((px_val, py_val))

        for idx in range(len(pts) - 1):
            t_progress = idx / float(len(pts))
            river_w = max(2, int(3 + t_progress * 9))
            bank_w = river_w + 6
            p1, p2 = pts[idx], pts[idx + 1]
            pygame.draw.line(bank_surf, (80, 145, 60, 200), p1, p2, bank_w)
            pygame.draw.line(river_surf, (35, 115, 210, 255), p1, p2, river_w)
            pygame.draw.circle(river_surf, (35, 115, 210, 255), p2, max(1, river_w // 2))

    bank_mask = (pygame.surfarray.array_alpha(bank_surf).T > 40).astype(np.float32)
    river_mask = (pygame.surfarray.array_alpha(river_surf).T > 80).astype(np.float32)

    # Riparian greenery
    riparian_col = np.array([0.20, 0.44, 0.18], dtype=np.float32)
    land_lit = np.where(bank_mask[:, :, None] > 0.5, land_lit * 0.45 + riparian_col * total_light * 0.55, land_lit)

    # River water with sky reflection and specular
    river_water_col = np.array([0.14, 0.44, 0.74], dtype=np.float32)
    river_lit = river_water_col * (0.65 + 0.35 * direct_sun[:, :, None]) + specular[:, :, None] * 0.35
    land_lit = np.where(river_mask[:, :, None] > 0.5, river_lit, land_lit)

    final_rgb = np.where(is_water[:, :, None], w_lit, land_lit)
    final_rgb = np.clip(final_rgb, 0.0, 1.0)
    final_rgb = np.power(final_rgb, 1.0 / 1.15)

    img_uint8 = (final_rgb * 255).astype(np.uint8)
    surf = pygame.surfarray.make_surface(np.transpose(img_uint8, (1, 0, 2)))
    return surf

HeightMapGenerator.generate_topographic_surface = _generate_topographic_surface_impl
