"""
heightmap.py — Realistic Procedural Elevation, Biomes, and Shaded Relief for REGNUM.

Generates realistic continuous heightmaps across the 9x9 honeycomb world using
multi-octave harmonic noise. Maps elevation to:
- Deep & Shallow Ocean (< 0.0 sea level)
- Coastal Lowlands & Plains (0.0 to 0.2)
- Highland Forests & Steppes (0.2 to 0.45)
- Rolling Hills & Plateaus (0.45 to 0.70)
- Rocky Mountain Ranges (0.70 to 0.88)
- Glacial Snow-Capped Alpine Peaks (>= 0.88)

Provides hillshading / shaded relief vector calculations for rich topographic visuals.
"""

import math
import random


class HeightMapGenerator:
    """Procedural multi-octave harmonic heightmap generator."""

    def __init__(self, seed: int = 42, grid_rows: int = 9, grid_cols: int = 9):
        self.seed = seed
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        
        # Deterministic pseudo-random harmonic phase offsets
        rng = random.Random(seed)
        self.octaves = [
            # (frequency_x, frequency_y, amplitude, phase_x, phase_y)
            (0.75, 0.75, 0.55, rng.uniform(0, math.pi * 2), rng.uniform(0, math.pi * 2)),
            (1.6, 1.5, 0.30, rng.uniform(0, math.pi * 2), rng.uniform(0, math.pi * 2)),
            (3.2, 3.1, 0.15, rng.uniform(0, math.pi * 2), rng.uniform(0, math.pi * 2)),
            (6.0, 5.8, 0.08, rng.uniform(0, math.pi * 2), rng.uniform(0, math.pi * 2)),
        ]
        # Central mountain spine tilt
        self.spine_angle = rng.uniform(-0.4, 0.4)
        self.spine_offset = rng.uniform(-0.2, 0.2)

    def get_raw_height(self, r: int, c: int) -> float:
        """Calculate continuous normalized elevation in [-1.0, 1.0]."""
        # Normalized coordinates centered around (0, 0)
        nx = (c - (self.grid_cols - 1) / 2.0) / (self.grid_cols / 2.0)
        ny = (r - (self.grid_rows - 1) / 2.0) / (self.grid_rows / 2.0)

        # Multi-octave wave superposition
        h = 0.0
        for fx, fy, amp, px, py in self.octaves:
            h += amp * math.sin(nx * fx * math.pi + px) * math.cos(ny * fy * math.pi + py)
            h += (amp * 0.5) * math.cos((nx + ny) * fx * 0.8 + px + py)

        # Central / diagonal continental ridge
        diag = nx * math.cos(self.spine_angle) + ny * math.sin(self.spine_angle) + self.spine_offset
        ridge = math.exp(-2.5 * (diag ** 2)) * 0.55
        h += ridge

        # Edge coastal falloff towards borders
        dist_from_center = math.sqrt(nx ** 2 + ny ** 2)
        edge_drop = 0.35 * (dist_from_center ** 2)
        h -= edge_drop

        # Clamp to [-1.0, 1.0]
        return max(-1.0, min(1.0, h))

    def get_elevation_meters(self, h: float) -> int:
        """Convert normalized elevation [-1.0, 1.0] to realistic meters."""
        if h < 0.0:
            # Below sea level: -1500m to 0m
            return int(h * 1500)
        else:
            # Above sea level: 0m to 3200m
            return int(h * 3200)

    def get_biome(self, h: float) -> str:
        """Return descriptive biome name based on elevation."""
        if h < -0.30:
            return 'deep_ocean'
        elif h < 0.0:
            return 'shallow_ocean'
        elif h < 0.20:
            return 'plains'
        elif h < 0.45:
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
            # Deep Ocean
            t = (h - (-1.0)) / 0.70
            return self._lerp_color((14, 32, 68), (24, 62, 110), t)
        elif h < 0.0:
            # Shallow Ocean / Coastal waters
            t = (h - (-0.30)) / 0.30
            return self._lerp_color((24, 62, 110), (45, 115, 155), t)
        elif h < 0.20:
            # Coastal Plains & Grasslands
            t = h / 0.20
            return self._lerp_color((75, 142, 85), (68, 128, 72), t)
        elif h < 0.45:
            # Highland Forests
            t = (h - 0.20) / 0.25
            return self._lerp_color((52, 108, 58), (78, 112, 62), t)
        elif h < 0.70:
            # Hills & Plateaus
            t = (h - 0.45) / 0.25
            return self._lerp_color((135, 122, 84), (120, 108, 92), t)
        elif h < 0.88:
            # High Mountains
            t = (h - 0.70) / 0.18
            return self._lerp_color((138, 134, 140), (175, 172, 180), t)
        else:
            # Snow-capped Alpine Peaks
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
    """Generate and attach elevation, biomes, and terrain heights to all world tiles."""
    generator = HeightMapGenerator(seed=seed, grid_rows=grid_rows, grid_cols=grid_cols)
    
    # First pass: compute raw elevations
    for tile in tiles:
        # Parse row and col from name 'rXcY'
        if tile.name.startswith('r') and 'c' in tile.name:
            parts = tile.name[1:].split('c')
            r, c = int(parts[0]), int(parts[1])
        else:
            r, c = 0, 0

        h = generator.get_raw_height(r, c)
        tile.elevation = h
        tile.elevation_meters = generator.get_elevation_meters(h)
        tile.biome = generator.get_biome(h)
        tile.grid_r = r
        tile.grid_c = c

    # Second pass: calculate slope and shaded relief hillshading
    tile_map = {t.name: t for t in tiles}
    sun_dir = (-0.707, -0.707)  # Northwest sunlight

    for tile in tiles:
        r, c = getattr(tile, 'grid_r', 0), getattr(tile, 'grid_c', 0)
        h = getattr(tile, 'elevation', 0.0)

        # Approximate partial derivatives from neighbors
        left = tile_map.get(f"r{r}c{max(0, c-1)}")
        right = tile_map.get(f"r{r}c{min(grid_cols-1, c+1)}")
        up = tile_map.get(f"r{max(0, r-1)}c{c}")
        down = tile_map.get(f"r{min(grid_rows-1, r+1)}c{c}")

        dx = (getattr(right, 'elevation', h) - getattr(left, 'elevation', h)) * 0.5
        dy = (getattr(down, 'elevation', h) - getattr(up, 'elevation', h)) * 0.5

        # Dot product with sun direction
        slope_illum = -(dx * sun_dir[0] + dy * sun_dir[1])
        hillshade = 1.0 + slope_illum * 0.45  # [0.75, 1.25]
        tile.hillshade = max(0.65, min(1.35, hillshade))

        # Base color with hillshading applied
        base_c = generator.get_base_color(h)
        shaded_c = (
            min(255, max(0, int(base_c[0] * tile.hillshade))),
            min(255, max(0, int(base_c[1] * tile.hillshade))),
            min(255, max(0, int(base_c[2] * tile.hillshade))),
        )
        tile.terrain_color = shaded_c

    return generator
