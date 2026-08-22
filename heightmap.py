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


class HeightMapGenerator:
    """Generates continuous continental landmasses with realistic shaded relief."""

    def __init__(self, seed: int = 42, grid_rows: int = 9, grid_cols: int = 9):
        self.seed = seed
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self._layout = rectangular_hex_layout(grid_rows, grid_cols)
        
        rng = random.Random(seed)
        self.octaves = [
            (0.85, 0.85, 0.45, rng.uniform(0, math.pi * 2), rng.uniform(0, math.pi * 2)),
            (1.7, 1.6, 0.22, rng.uniform(0, math.pi * 2), rng.uniform(0, math.pi * 2)),
            (3.4, 3.2, 0.12, rng.uniform(0, math.pi * 2), rng.uniform(0, math.pi * 2)),
            (6.5, 6.0, 0.05, rng.uniform(0, math.pi * 2), rng.uniform(0, math.pi * 2)),
        ]
        self.spine_angle = rng.uniform(-0.35, 0.35)
        self.spine_offset = rng.uniform(-0.15, 0.15)

    def get_continuous_height(self, nx: float, ny: float) -> float:
        """Calculate continuous normalized elevation at normalized coords (nx, ny)."""
        dist_sq = nx * nx + ny * ny
        continent_base = 0.52 - 0.72 * dist_sq

        harmonics = 0.0
        for fx, fy, amp, px, py in self.octaves:
            harmonics += amp * math.sin(nx * fx * math.pi + px) * math.cos(ny * fy * math.pi + py)

        diag = nx * math.cos(self.spine_angle) + ny * math.sin(self.spine_angle) + self.spine_offset
        ridge = math.exp(-3.2 * (diag ** 2)) * 0.60

        total_h = continent_base + harmonics + ridge
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
        elif h < 0.70:
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
        elif h < 0.70:
            t = (h - 0.48) / 0.22
            return self._lerp_color((135, 122, 84), (120, 108, 92), t)
        elif h < 0.88:
            t = (h - 0.70) / 0.18
            return self._lerp_color((138, 134, 140), (175, 172, 180), t)
        else:
            t = min(1.0, (h - 0.88) / 0.12)
            return self._lerp_color((215, 222, 235), (245, 250, 255), t)

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
    """Render a 4x high-resolution topographic map surface with contour lines and hillshading."""
    import pygame
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

    surf = pygame.Surface((width, height))
    surf.fill((12, 28, 62))
    
    step = 2
    cols = width // step + 1
    rows = height // step + 1

    # 1. Sample continuous heights grid mapped smoothly without any modulus or tears
    h_grid = []
    for r in range(rows):
        row_h = []
        wy = min_wy + (r / max(1, rows - 1)) * (max_wy - min_wy)
        ny = (wy - cy_center) / span_y
        for c in range(cols):
            wx = min_wx + (c / max(1, cols - 1)) * (max_wx - min_wx)
            nx = (wx - cx_center) / span_x
            h = generator.get_continuous_height(nx, ny)
            row_h.append(h)
        h_grid.append(row_h)

    # 2. Render shaded terrain and contour lines
    sun_dx, sun_dy = -0.707, -0.707
    
    for r in range(rows - 1):
        py = r * step
        for c in range(cols - 1):
            px = c * step
            h = h_grid[r][c]
            
            # Compute gradient for analytical hillshading
            dh_dx = (h_grid[r][min(cols-1, c+1)] - h_grid[r][max(0, c-1)]) * 0.5
            dh_dy = (h_grid[min(rows-1, r+1)][c] - h_grid[max(0, r-1)][c]) * 0.5
            slope_illum = -(dh_dx * sun_dx + dh_dy * sun_dy)
            hillshade = max(0.68, min(1.36, 1.0 + slope_illum * 1.8))

            # Base hypsometric / bathymetric color
            base_c = generator.get_base_color(h)
            r_col = min(255, max(0, int(base_c[0] * hillshade)))
            g_col = min(255, max(0, int(base_c[1] * hillshade)))
            b_col = min(255, max(0, int(base_c[2] * hillshade)))
            col = (r_col, g_col, b_col)

            # Check for Topographic Contour lines (Isolines)
            meters = generator.get_elevation_meters(h)
            is_index_contour = False
            is_contour = False
            is_coastline = False

            if h >= 0.0:
                if abs(meters) <= 8:
                    is_coastline = True
                elif abs(meters % 1000) <= 12 or abs((meters % 1000) - 1000) <= 12:
                    is_index_contour = True
                elif abs(meters % 250) <= 6 or abs((meters % 250) - 250) <= 6:
                    is_contour = True
            else:
                abs_m = abs(meters)
                if abs(abs_m % 300) <= 8 or abs((abs_m % 300) - 300) <= 8:
                    is_contour = True

            if is_coastline:
                col = (195, 182, 135)
            elif is_index_contour:
                col = (255, 255, 255) if h >= 0.85 else ((40, 36, 30) if h >= 0.65 else (35, 55, 32))
            elif is_contour:
                col = (18, 48, 88) if h < 0.0 else ((210, 225, 240) if h >= 0.85 else ((80, 72, 65) if h >= 0.65 else (55, 88, 52)))

            pygame.draw.rect(surf, col, (px, py, step, step))

    return surf

HeightMapGenerator.generate_topographic_surface = _generate_topographic_surface_impl
