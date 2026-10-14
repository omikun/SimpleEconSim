"""
terrain/generator/parallel.py — Parallel Multi-Core Map Generation & World Integration Adapter.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from terrain.generator.polygon import PolygonMapGenerator


class ParallelPolygonMapGenerator:
    """Manages parallel map generation across worker processes and threads."""

    @staticmethod
    def _worker_generate_map(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Worker function executing independent polygonal map generation."""
        t0 = time.perf_counter()
        gen = PolygonMapGenerator(**kwargs)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        # Summarize output metrics for serialization
        n_centers = len(gen.centers)
        n_corners = len(gen.corners)
        n_edges = len(gen.edges)
        land_centers = sum(1 for c in gen.centers if not c.water)
        ocean_centers = sum(1 for c in gen.centers if c.ocean)
        lake_centers = sum(1 for c in gen.centers if c.water and not c.ocean)
        river_edges = sum(1 for e in gen.edges if e.river > 0)

        # Count biomes
        biomes: Dict[str, int] = {}
        for c in gen.centers:
            biomes[c.biome] = biomes.get(c.biome, 0) + 1

        return {
            'seed': kwargs.get('seed', 0),
            'duration_ms': duration_ms,
            'centers_count': n_centers,
            'corners_count': n_corners,
            'edges_count': n_edges,
            'land_centers': land_centers,
            'ocean_centers': ocean_centers,
            'lake_centers': lake_centers,
            'river_edges': river_edges,
            'biomes': biomes,
            'generator': gen,
        }

    @classmethod
    def generate_batch_parallel(
        cls,
        seeds: List[int],
        num_points: int = 1000,
        max_workers: Optional[int] = None,
        use_processes: bool = False,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Generate multiple polygonal maps in parallel using multi-core worker pool."""
        tasks = []
        for s in seeds:
            task_kwargs = {
                'seed': s,
                'num_points': num_points,
                **kwargs,
            }
            tasks.append(task_kwargs)

        executor_cls = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
        with executor_cls(max_workers=max_workers) as executor:
            results = list(executor.map(cls._worker_generate_map, tasks))

        return results


def apply_polygon_map_to_world(
    tiles: list,
    seed: int = 42,
    grid_rows: int = 9,
    grid_cols: int = 9,
    num_points: int = 800,
    island_shape: str = 'radial',
) -> PolygonMapGenerator:
    """Sample polygonal geography onto the Call of Capital 9x9 hex tile grid.
    
    Provides 100% plug-and-play parity with apply_heightmap_to_world in heightmap.py.
    """
    from hexmap import rectangular_hex_layout, axial_to_pixel

    gen = PolygonMapGenerator(
        seed=seed,
        width=1000.0,
        height=1000.0,
        num_points=num_points,
        island_shape=island_shape,
    )

    layout = rectangular_hex_layout(grid_rows, grid_cols)

    hex_size = 48.0
    coords = [axial_to_pixel(q, r, hex_size) for q, r in layout.values()]
    min_x = min(p[0] for p in coords)
    max_x = max(p[0] for p in coords)
    min_y = min(p[1] for p in coords)
    max_y = max(p[1] for p in coords)

    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)

    margin = 80.0
    target_span_x = gen.width - 2 * margin
    target_span_y = gen.height - 2 * margin

    for tile in tiles:
        if tile.name.startswith('r') and 'c' in tile.name:
            parts = tile.name[1:].split('c')
            r, c = int(parts[0]), int(parts[1])
        else:
            r, c = 0, 0

        tile.grid_r = r
        tile.grid_c = c

        q, ax_r = layout.get(f"r{r}c{c}", (c, r))
        px, py = axial_to_pixel(q, ax_r, hex_size)

        mx = margin + ((px - min_x) / span_x) * target_span_x
        my = margin + ((py - min_y) / span_y) * target_span_y

        center = gen.get_center_at(mx, my)

        tile.elevation = float(center.elevation if not center.water else -0.20)
        tile.moisture = float(center.moisture)
        tile.is_ocean = bool(center.ocean)
        tile.biome = center.biome.lower()

        if tile.elevation < 0.0:
            tile.elevation_meters = int(tile.elevation * 1500)
        else:
            tile.elevation_meters = int(tile.elevation * 3200)

        tile.terrain_color = center.brdf_color
        tile.hillshade = float(center.total_light)
        tile.normal = center.normal

    return gen
