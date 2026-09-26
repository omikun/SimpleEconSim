#!/usr/bin/env python3
"""
mapgen_web.py — High-Performance Mobile-Ready Web Server for Mapgen2 Terrain Explorer.

Serves an interactive web application optimized for iPhone (and desktop), providing
instant visual map updates, touch cell inspection, and native Apple AR Quick Look
3D USDZ streaming over Tailscale.

Usage:
    python3 mapgen_web.py [--port 8080] [--host 0.0.0.0]
"""

import sys
import os
import io
import time
import json
import urllib.parse
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Tuple, Any, Optional, List
import queue
import threading

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from polygon_map import PolygonMapGenerator
from render_island_micropolys import (
    build_island_mesh,
    render_mesh,
    export_island_wireframe_usdz,
    compute_catmull_rom_river_streams,
)
from goods import Goods
from sim_world_voronoi import build_world_voronoi
from render_voronoi_geopolitics import render_voronoi_geopolitics
from render_regnum_terrain import render_regnum_terrain

# ---------------------------------------------------------------------------
# Dedicated Thread-Affinity Worker for Headless ModernGL GPU Execution
# ---------------------------------------------------------------------------
GPU_TASK_QUEUE = queue.Queue()
GPU_AVAILABLE = False
_GPU_READY = threading.Event()


def _gpu_worker_loop():
    global GPU_AVAILABLE
    pipe = None
    try:
        from render_engine.gpu.mesh_brdf_pipeline import GPUMeshBRDFPipeline
        pipe = GPUMeshBRDFPipeline()
        if pipe.is_available():
            GPU_AVAILABLE = True
    except Exception as exc:
        sys.stderr.write(f"GPU ModernGL worker initialization note: {exc}\n")
    finally:
        _GPU_READY.set()

    while True:
        task = GPU_TASK_QUEUE.get()
        if task is None:
            break
        func, args, kwargs, reply_q = task
        try:
            if pipe is None or not GPU_AVAILABLE:
                raise RuntimeError("ModernGL GPU pipeline is unavailable on this system")
            res = func(pipe, *args, **kwargs)
            reply_q.put((True, res))
        except Exception as e:
            reply_q.put((False, e))
        finally:
            GPU_TASK_QUEUE.task_done()


_gpu_thread = threading.Thread(target=_gpu_worker_loop, daemon=True)
_gpu_thread.start()


def is_gpu_ready(timeout: float = 2.0) -> bool:
    _GPU_READY.wait(timeout)
    return GPU_AVAILABLE


def run_on_gpu(func, *args, **kwargs):
    is_gpu_ready()
    reply_q = queue.Queue()
    GPU_TASK_QUEUE.put((func, args, kwargs, reply_q))
    ok, res = reply_q.get()
    if ok:
        return res
    raise res


def _render_gpu_mesh_surface(
    pipe,
    gen: PolygonMapGenerator,
    triangles: list,
    width: int,
    height: int,
    uniforms: dict,
    mesh_key: Any = None,
) -> pygame.Surface:
    """Invoked inside dedicated GPU worker thread to render CPU mapgen mesh with BRDF."""
    return pipe.render_mesh(
        gen=gen,
        triangles=triangles,
        width=width,
        height=height,
        uniforms=uniforms,
        mesh_cache_key=mesh_key,
    )

# ---------------------------------------------------------------------------
# Two-Tier In-Memory Cache for Instant Interactive Response
# ---------------------------------------------------------------------------
CANONICAL_WORLD_SIZE = 1024
GRAPH_CACHE: Dict[Tuple, PolygonMapGenerator] = {}
MESH_CACHE: Dict[Tuple, Tuple[List[Tuple], int]] = {}
MAX_CACHE_ENTRIES = 12


def get_cached_graph(
    seed: int,
    shape: str,
    points: int,
    rivers: int,
    sharpness: float,
    moisture_bias: float = 0.0,
    north_temp: float = 0.0,
    south_temp: float = 0.0,
    persistence: float = 0.0,
    size: int = CANONICAL_WORLD_SIZE,
    canyon_depth: float = 1.5,
    valley_width: float = 1.0,
    **kwargs,
) -> PolygonMapGenerator:
    key = (
        seed,
        shape,
        points,
        rivers,
        round(sharpness, 2),
        round(moisture_bias, 2),
        round(north_temp, 2),
        round(south_temp, 2),
        round(persistence, 2),
        round(canyon_depth, 2),
        round(valley_width, 2),
    )
    if key in GRAPH_CACHE:
        return GRAPH_CACHE[key]

    gen = PolygonMapGenerator(
        seed=seed,
        width=CANONICAL_WORLD_SIZE,
        height=CANONICAL_WORLD_SIZE,
        num_points=points,
        island_shape=shape,
        river_count=rivers,
        mountain_sharpness=sharpness,
        moisture_bias=moisture_bias,
        north_temperature=north_temp,
        south_temperature=south_temp,
        persistence=persistence,
        enable_corner_improvement=True,
        enable_roads=True,
        enable_lava=False,
        enable_noisy_edges=True,
        canyon_depth=canyon_depth,
        valley_width=valley_width,
    )

    if len(GRAPH_CACHE) >= MAX_CACHE_ENTRIES:
        GRAPH_CACHE.pop(next(iter(GRAPH_CACHE)))
    GRAPH_CACHE[key] = gen
    return gen


def get_cached_micropolys(
    gen: PolygonMapGenerator,
    graph_key: Tuple,
    polys: int,
    roughness: float,
    jitter: float,
    alpha: float,
    height_scale: float,
    smooth: float,
    quad_fold: bool = True,
    ridge_noise: float = 0.35,
    erosion_strength: float = 0.30,
    erosion_droplets: int = 15000,
) -> Tuple[List[Tuple], int]:
    mesh_key = (
        graph_key,
        polys,
        round(roughness, 1),
        round(jitter, 2),
        round(alpha, 2),
        round(height_scale, 1),
        round(smooth, 2),
        quad_fold,
        round(ridge_noise, 2),
        round(erosion_strength, 2),
        int(erosion_droplets),
    )
    if mesh_key in MESH_CACHE:
        return MESH_CACHE[mesh_key]

    triangles, actual_count = build_island_mesh(
        gen,
        width=CANONICAL_WORLD_SIZE,
        height=CANONICAL_WORLD_SIZE,
        mode="fractal",
        target_polys=polys,
        roughness=roughness,
        lateral_jitter=jitter,
        elevation_alpha=alpha,
        elev_scale=height_scale,
        normal_smooth_ratio=smooth,
        quad_fold=quad_fold,
        ridge_noise=ridge_noise,
        erosion_strength=erosion_strength,
        erosion_droplets=erosion_droplets,
    )

    if len(MESH_CACHE) >= MAX_CACHE_ENTRIES:
        MESH_CACHE.pop(next(iter(MESH_CACHE)))
    MESH_CACHE[mesh_key] = (triangles, actual_count)
    return triangles, actual_count


GEOPOLITICS_CACHE: Dict[Tuple, Tuple[List[Any], List[Any]]] = {}


def get_cached_geopolitics(
    gen: PolygonMapGenerator,
    seed: int,
    num_nations: int = 3,
    nation_seed: int = 777,
) -> Tuple[List[Any], List[Any]]:
    key = (id(gen), seed, num_nations, nation_seed)
    if key in GEOPOLITICS_CACHE:
        return GEOPOLITICS_CACHE[key]

    tiles, nations, _ = build_world_voronoi(
        seed=seed,
        terrain_seed=seed,
        nation_seed=nation_seed,
        existing_gen=gen,
        num_nations=num_nations,
    )
    if len(GEOPOLITICS_CACHE) >= MAX_CACHE_ENTRIES:
        GEOPOLITICS_CACHE.pop(next(iter(GEOPOLITICS_CACHE)))
    GEOPOLITICS_CACHE[key] = (tiles, nations)
    return tiles, nations


REGNUM_SURF_CACHE: Dict[Tuple, pygame.Surface] = {}


# ---------------------------------------------------------------------------
# Persistent Save Slots Storage & Versioning
# ---------------------------------------------------------------------------
SLOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_slots")
os.makedirs(SLOTS_DIR, exist_ok=True)
CURRENT_SLOT_SCHEMA_VERSION = 1


def migrate_slot_data(raw_data: dict) -> dict:
    """Migrates slot data from older schemas to CURRENT_SLOT_SCHEMA_VERSION for backwards compatibility."""
    if not isinstance(raw_data, dict):
        return {}
    ver = raw_data.get("schema_version", 1)
    # Forward migrations can be appended here if schema_version increases in future releases
    raw_data["schema_version"] = CURRENT_SLOT_SCHEMA_VERSION
    return raw_data


def get_all_saved_slots() -> dict:
    slots = {}
    for slot_num in range(1, 5):
        slot_file = os.path.join(SLOTS_DIR, f"slot_{slot_num}.json")
        if os.path.exists(slot_file):
            try:
                with open(slot_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    slots[str(slot_num)] = migrate_slot_data(data)
            except Exception as e:
                sys.stderr.write(f"Error reading slot {slot_num}: {e}\n")
                slots[str(slot_num)] = None
        else:
            slots[str(slot_num)] = None

    active_file = os.path.join(SLOTS_DIR, "active_slot.json")
    active_slot = 1
    if os.path.exists(active_file):
        try:
            with open(active_file, "r", encoding="utf-8") as f:
                active_slot = json.load(f).get("active_slot", 1)
        except Exception:
            active_slot = 1

    return {"status": "ok", "active_slot": active_slot, "slots": slots}


def save_slot_to_file(slot_num: int, slot_data: dict) -> bool:
    try:
        os.makedirs(SLOTS_DIR, exist_ok=True)
        slot_data["schema_version"] = CURRENT_SLOT_SCHEMA_VERSION
        slot_file = os.path.join(SLOTS_DIR, f"slot_{slot_num}.json")
        temp_file = slot_file + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(slot_data, f, indent=2)
        os.replace(temp_file, slot_file)

        active_file = os.path.join(SLOTS_DIR, "active_slot.json")
        with open(active_file, "w", encoding="utf-8") as f:
            json.dump({"active_slot": slot_num}, f, indent=2)
        return True
    except Exception as e:
        sys.stderr.write(f"Error saving slot {slot_num}: {e}\n")
        return False


def clear_slot_file(slot_num: int) -> bool:
    try:
        slot_file = os.path.join(SLOTS_DIR, f"slot_{slot_num}.json")
        if os.path.exists(slot_file):
            os.remove(slot_file)
        return True
    except Exception as e:
        sys.stderr.write(f"Error clearing slot {slot_num}: {e}\n")
        return False


def set_active_slot(slot_num: int) -> bool:
    try:
        os.makedirs(SLOTS_DIR, exist_ok=True)
        active_file = os.path.join(SLOTS_DIR, "active_slot.json")
        with open(active_file, "w", encoding="utf-8") as f:
            json.dump({"active_slot": slot_num}, f, indent=2)
        return True
    except Exception:
        return False


def build_micropoly_trees(gen, sample_mesh_elevation, height_scale: float = 70.0, tree_density: float = 1.0):
    """Generates 3D low-poly faceted tree canopies with macro-cluster regions and organic faded edges.
    Returns Float32Array with 40-byte vertex stride [x, y, z, nx, ny, nz, r, g, b, elev].
    """
    import math
    import random

    FOREST_BIOMES = {
        "TAIGA": (0.13, 0.28, 0.18, 0.85),
        "TEMPERATE_RAIN_FOREST": (0.10, 0.38, 0.22, 1.00),
        "TEMPERATE_DECIDUOUS_FOREST": (0.16, 0.36, 0.18, 0.90),
        "TROPICAL_RAIN_FOREST": (0.12, 0.42, 0.25, 1.00),
        "TROPICAL_SEASONAL_FOREST": (0.22, 0.38, 0.16, 0.80),
        "SHRUBLAND": (0.28, 0.38, 0.20, 0.45),
        "GRASSLAND": (0.24, 0.36, 0.18, 0.20),
    }

    scale_x = CANONICAL_WORLD_SIZE / gen.width
    scale_y = CANONICAL_WORLD_SIZE / gen.height
    avg_cell_r = math.sqrt((gen.width * gen.height) / max(1, len(gen.centers))) * 0.50

    # Fast 2D coherent noise for macro-scale forest regions
    seed_offset = getattr(gen, 'seed', 42) * 1013 + 777
    def hash2d(ix, iy):
        n = ix * 374761393 + iy * 668265263 + seed_offset
        n = (n ^ (n >> 13)) * 1274126177
        return (n & 0x7fffffff) / float(0x7fffffff)

    def smooth_noise2d(x, y):
        ix = math.floor(x)
        iy = math.floor(y)
        fx = x - ix
        fy = y - iy
        ux = fx * fx * (3.0 - 2.0 * fx)
        uy = fy * fy * (3.0 - 2.0 * fy)
        n00 = hash2d(ix, iy)
        n10 = hash2d(ix + 1, iy)
        n01 = hash2d(ix, iy + 1)
        n11 = hash2d(ix + 1, iy + 1)
        return (n00 * (1.0 - ux) + n10 * ux) * (1.0 - uy) + (n01 * (1.0 - ux) + n11 * ux) * uy

    def fbm2d(x, y):
        return (smooth_noise2d(x, y) * 0.62 +
                smooth_noise2d(x * 2.13 + 1.7, y * 2.13 + 9.2) * 0.26 +
                smooth_noise2d(x * 4.41 + 5.1, y * 4.41 + 3.8) * 0.12)

    tree_verts = []
    rng = random.Random(getattr(gen, 'seed', 42) + 999)

    # Candidate density scales with slider
    candidate_count = int(max(3, min(96, round(3.5 * tree_density))))
    rad_scale = max(0.50, 1.0 / math.sqrt(1.0 + max(0.0, tree_density - 1.0) * 0.15))

    for c in gen.centers:
        if c.water or c.ocean or c.biome not in FOREST_BIOMES:
            continue
        base_col_info = FOREST_BIOMES[c.biome]
        base_col = base_col_info[:3]
        biome_affinity = base_col_info[3]

        elev_norm = min(1.0, max(0.0, c.elevation))
        # Treeline: altitude falloff above 0.70 elevation
        alt_factor = 1.0 - max(0.0, (elev_norm - 0.70) / 0.18)
        if alt_factor <= 0.05:
            continue

        for _ in range(candidate_count):
            # Uniform area distribution over the polygon (sqrt for radial Jacobian)
            angle = rng.uniform(0, 2 * math.pi)
            rad = math.sqrt(rng.uniform(0.01, 1.0)) * avg_cell_r * 1.30
            tx = (c.x + math.cos(angle) * rad) * scale_x
            ty = (c.y + math.sin(angle) * rad) * scale_y

            # Evaluate continuous macro forest noise at world scale
            noise_val = fbm2d(tx * 0.007, ty * 0.007)
            # Combine macro noise with biome suitability and altitude
            potential = (biome_affinity * 0.55 + noise_val * 0.45) * alt_factor

            # Ragged edge fading threshold
            edge_threshold = 0.42
            if potential < edge_threshold:
                continue

            # Normalized edge factor: 0.0 at edge, 1.0 in dense core
            f_edge = min(1.0, (potential - edge_threshold) / 0.28)

            # Random density fading at perimeter
            if rng.random() > (0.25 + 0.75 * (f_edge ** 0.8)):
                continue

            z_sample = sample_mesh_elevation([[tx, ty]])
            if z_sample is None:
                continue
            tz = float(z_sample[0])

            # Edge scale fading: trees at the fringe are smaller saplings/dwarf trees
            scale_fade = 0.45 + 0.55 * (f_edge ** 0.7)
            tree_h = rng.uniform(2.6, 5.0) * (1.0 + (height_scale / 100.0) * 0.35) * max(0.65, rad_scale) * scale_fade
            tree_r = rng.uniform(1.2, 2.2) * rad_scale * scale_fade

            col_var = rng.uniform(0.88, 1.12)
            tr = min(1.0, base_col[0] * col_var)
            tg = min(1.0, base_col[1] * col_var)
            tb = min(1.0, base_col[2] * col_var)

            base_z = tz + tree_h * 0.20
            apex = (tx, ty, tz + tree_h)
            corners = [
                (tx - tree_r, ty - tree_r, base_z),
                (tx + tree_r, ty - tree_r, base_z),
                (tx + tree_r, ty + tree_r, base_z),
                (tx - tree_r, ty + tree_r, base_z),
            ]

            for i in range(4):
                c_a = corners[i]
                c_b = corners[(i + 1) % 4]
                v1 = (c_a[0] - apex[0], c_a[1] - apex[1], c_a[2] - apex[2])
                v2 = (c_b[0] - apex[0], c_b[1] - apex[1], c_b[2] - apex[2])
                nx = v1[1] * v2[2] - v1[2] * v2[1]
                ny = v1[2] * v2[0] - v1[0] * v2[2]
                nz = v1[0] * v2[1] - v1[1] * v2[0]
                nlen = math.hypot(nx, ny, nz)
                if nlen > 1e-4:
                    nx /= nlen
                    ny /= nlen
                    nz /= nlen
                else:
                    nx, ny, nz = 0.0, 0.0, 1.0

                tree_verts.extend([apex[0], apex[1], apex[2], nx, ny, nz, tr, tg, tb, elev_norm])
                tree_verts.extend([c_a[0], c_a[1], c_a[2], nx, ny, nz, tr, tg, tb, elev_norm])
                tree_verts.extend([c_b[0], c_b[1], c_b[2], nx, ny, nz, tr, tg, tb, elev_norm])

    return np.array(tree_verts, dtype=np.float32)


def build_coastal_surf_ribbon(gen, ribbon_width: float = 18.0):
    """Generates 3D coastal wave ribbons along discrete island boundary edges.
    Returns Float32Array with 40-byte vertex stride [x, y, z, nx, ny, nz, r, g, b, coast_dist].
    """
    import math
    scale_x = CANONICAL_WORLD_SIZE / gen.width
    scale_y = CANONICAL_WORLD_SIZE / gen.height
    surf_verts = []

    if not hasattr(gen, "edges"):
        return np.empty((0,), dtype=np.float32)

    for e in gen.edges:
        if not (e.d0 and e.d1 and e.v0 and e.v1):
            continue
        is_coast = (e.d0.water != e.d1.water)
        if not is_coast:
            continue

        land_cell = e.d0 if not e.d0.water else e.d1
        water_cell = e.d1 if not e.d0.water else e.d0

        x0, y0 = e.v0.x * scale_x, e.v0.y * scale_y
        x1, y1 = e.v1.x * scale_x, e.v1.y * scale_y

        dx = x1 - x0
        dy = y1 - y0
        seg_len = math.hypot(dx, dy)
        if seg_len < 0.1:
            continue

        cand_nx = -dy / seg_len
        cand_ny = dx / seg_len
        to_water_x = (water_cell.x - land_cell.x) * scale_x
        to_water_y = (water_cell.y - land_cell.y) * scale_y
        if cand_nx * to_water_x + cand_ny * to_water_y < 0:
            cand_nx = -cand_nx
            cand_ny = -cand_ny

        ox0 = x0 + cand_nx * ribbon_width
        oy0 = y0 + cand_ny * ribbon_width
        ox1 = x1 + cand_nx * ribbon_width
        oy1 = y1 + cand_ny * ribbon_width

        z_shore = 0.04
        z_deep = -0.16

        nx, ny, nz = 0.0, 0.0, 1.0

        foam_r, foam_g, foam_b = 0.95, 0.98, 1.00
        sea_r, sea_g, sea_b = 0.14, 0.52, 0.68

        # Tri 1
        surf_verts.extend([x0, y0, z_shore, nx, ny, nz, foam_r, foam_g, foam_b, 0.0])
        surf_verts.extend([x1, y1, z_shore, nx, ny, nz, foam_r, foam_g, foam_b, 0.0])
        surf_verts.extend([ox0, oy0, z_deep, nx, ny, nz, sea_r, sea_g, sea_b, 1.0])
        # Tri 2
        surf_verts.extend([ox0, oy0, z_deep, nx, ny, nz, sea_r, sea_g, sea_b, 1.0])
        surf_verts.extend([x1, y1, z_shore, nx, ny, nz, foam_r, foam_g, foam_b, 0.0])
        surf_verts.extend([ox1, oy1, z_deep, nx, ny, nz, sea_r, sea_g, sea_b, 1.0])

    return np.array(surf_verts, dtype=np.float32)


def build_hydro_river_ribbons(gen, sample_mesh_elevation=None, height_scale: float = 70.0, river_width_mult: float = 1.0, river_count: int = 25):
    """Traces continuous downhill rivers directly along the carved riverbed network
    and generates watertight 3D water ribbon triangle strips.
    Returns Float32Array with 40-byte vertex stride [x, y, z, nx, ny, nz, r, g, b, flow_v].
    """
    import math

    if not hasattr(gen, "river_paths") or len(gen.river_paths) == 0:
        return np.empty((0,), dtype=np.float32)

    scale_x = CANONICAL_WORLD_SIZE / gen.width
    scale_y = CANONICAL_WORLD_SIZE / gen.height

    all_streams = compute_catmull_rom_river_streams(gen, scale_x, scale_y, height_scale, substeps=6)
    if not all_streams:
        return np.empty((0,), dtype=np.float32)

    # Extrude watertight 3D water ribbon mesh with strictly monotonic downhill flow
    river_verts = []
    base_w = 2.4 * max(0.2, river_width_mult)

    for stream in all_streams:
        n_pts = len(stream)
        if n_pts < 2:
            continue

        cum_dist = 0.0
        for i in range(n_pts - 1):
            p0 = stream[i]
            p1 = stream[i + 1]

            tx = p1[0] - p0[0]
            ty = p1[1] - p0[1]
            seg_len = math.hypot(tx, ty)
            if seg_len < 0.05:
                continue
            tx /= seg_len
            ty /= seg_len

            # Perpendicular bank normal
            nx_p = -ty
            ny_p = tx

            # Width increases with flow flux and downstream progression
            flux0 = p0[3]
            flux1 = p1[3]
            t_downstream0 = i / max(1, n_pts - 1)
            t_downstream1 = (i + 1) / max(1, n_pts - 1)
            w0 = base_w * (0.8 + 0.35 * math.sqrt(max(1.0, flux0)) + 0.5 * math.sqrt(t_downstream0))
            w1 = base_w * (0.8 + 0.35 * math.sqrt(max(1.0, flux1)) + 0.5 * math.sqrt(t_downstream1))

            # Left & Right bank points
            l0_x, l0_y = p0[0] + nx_p * (w0 * 0.5), p0[1] + ny_p * (w0 * 0.5)
            r0_x, r0_y = p0[0] - nx_p * (w0 * 0.5), p0[1] - ny_p * (w0 * 0.5)
            l1_x, l1_y = p1[0] + nx_p * (w1 * 0.5), p1[1] + ny_p * (w1 * 0.5)
            r1_x, r1_y = p1[0] - nx_p * (w1 * 0.5), p1[1] - ny_p * (w1 * 0.5)

            # River water ribbon sits cleanly inside the carved bedrock channel (+0.08 above monotonic water level)
            z0_surf = max(0.04, p0[2] + 0.08)
            z1_surf = max(0.04, p1[2] + 0.08)

            # River water is completely pure vibrant blue across its entire length
            t_stream = i / max(1, n_pts - 1)
            # Smooth subtle gradient from mountain crystal azure to deep lowland blue
            r_col = 0.10 * (1.0 - t_stream) + 0.06 * t_stream
            g_col = 0.54 * (1.0 - t_stream) + 0.42 * t_stream
            b_col = 0.92 * (1.0 - t_stream) + 0.84 * t_stream

            norm_x, norm_y, norm_z = 0.0, 0.0, 1.0
            flow0 = cum_dist * 0.05
            cum_dist += seg_len
            flow1 = cum_dist * 0.05

            # Quad strip -> 2 triangles
            river_verts.extend([l0_x, l0_y, z0_surf, norm_x, norm_y, norm_z, r_col, g_col, b_col, flow0])
            river_verts.extend([r0_x, r0_y, z0_surf, norm_x, norm_y, norm_z, r_col, g_col, b_col, flow0])
            river_verts.extend([l1_x, l1_y, z1_surf, norm_x, norm_y, norm_z, r_col, g_col, b_col, flow1])

            river_verts.extend([l1_x, l1_y, z1_surf, norm_x, norm_y, norm_z, r_col, g_col, b_col, flow1])
            river_verts.extend([r0_x, r0_y, z0_surf, norm_x, norm_y, norm_z, r_col, g_col, b_col, flow0])
            river_verts.extend([r1_x, r1_y, z1_surf, norm_x, norm_y, norm_z, r_col, g_col, b_col, flow1])

    return np.array(river_verts, dtype=np.float32)


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------
class MapgenHTTPHandler(BaseHTTPRequestHandler):
    """Processes static assets, map rasterization, inspection, and USDZ exports."""

    def log_message(self, format, *args):
        # Concise single-line request logging
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {format % args}\n")
        sys.stdout.flush()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Root / UI Client
        if path == "/" or path == "/index.html":
            self.serve_index()

        # 2. Map Render API
        elif path == "/api/render":
            self.handle_render(query)

        # 2b. High-FPS Client-Side WebGL 3D Mesh API
        elif path == "/api/mesh_binary":
            self.handle_mesh_binary(query)

        # 3. Cell Inspection API
        elif path == "/api/inspect":
            self.handle_inspect(query)

        # 4. Apple Quick Look 3D USDZ Stream API
        elif path == "/api/export_usdz":
            self.handle_export_usdz(query)

        # 5. Health Check
        elif path == "/api/health":
            self.send_json({"status": "ok", "cached_graphs": len(GRAPH_CACHE), "gpu_available": is_gpu_ready(0.2)})

        # 6. Client Diagnostics Log API
        elif path == "/api/log_error":
            msg = query.get("msg", [""])[0]
            sys.stderr.write(f"[CLIENT LOG] {msg}\n")
            sys.stderr.flush()
            self.send_json({"status": "logged"})

        # 7. Persistent Save Slots API
        elif path == "/api/slots":
            self.send_json(get_all_saved_slots())

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            body = {}

        if path == "/api/slots/save":
            slot_num = int(body.get("slot", 1))
            slot_num = max(1, min(16, slot_num))
            ok = save_slot_to_file(slot_num, body)
            self.send_json({"status": "ok" if ok else "error", "slot": slot_num})

        elif path == "/api/slots/clear":
            slot_num = int(body.get("slot", 1))
            ok = clear_slot_file(slot_num)
            self.send_json({"status": "ok" if ok else "error", "slot": slot_num})

        elif path == "/api/slots/active":
            slot_num = int(body.get("active_slot", 1))
            ok = set_active_slot(slot_num)
            self.send_json({"status": "ok" if ok else "error", "active_slot": slot_num})

        else:
            self.send_error(404, "Not Found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def serve_index(self):
        html_path = os.path.join(os.path.dirname(__file__), "web", "index.html")
        if not os.path.exists(html_path):
            self.send_error(404, "index.html not found")
            return

        with open(html_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(content)

    def handle_render(self, q: Dict[str, list]):
        t0 = time.time()
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["perlin"])[0]
        engine = q.get("engine", ["gpu" if is_gpu_ready(0.2) else "cpu"])[0].lower()
        mode = q.get("mode", ["micropolys"])[0]
        points = int(q.get("points", [1000])[0])
        polys = int(q.get("polys", [16000])[0])
        height_scale = float(q.get("height_scale", [70.0])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        roughness = float(q.get("roughness", [3.0])[0])
        jitter = float(q.get("jitter", [0.22])[0])
        smooth = float(q.get("smooth", [0.70])[0])
        alpha = float(q.get("alpha", [0.0])[0])
        rivers = int(q.get("rivers", [25])[0])
        moisture_bias = float(q.get("moisture_bias", [0.0])[0])
        north_temp = float(q.get("north_temp", [0.0])[0])
        south_temp = float(q.get("south_temp", [0.0])[0])
        persistence = float(q.get("persistence", [0.0])[0])
        quad_fold = q.get("quad_fold", ["true"])[0].lower() in ("true", "1", "yes")
        ridge_noise = float(q.get("ridge_noise", [0.35])[0])
        erosion_strength = float(q.get("erosion_strength", [0.30])[0])
        erosion_droplets = int(q.get("erosion_droplets", [15000])[0])
        size = int(q.get("size", [1024])[0])
        size = max(256, min(4096, size))

        # Dynamic lighting & sun angles
        sun_azimuth = float(q.get("sun_azimuth", [-135.0])[0])
        sun_elevation = float(q.get("sun_elevation", [42.0])[0])
        sun_intensity = float(q.get("sun_intensity", [1.15])[0])
        ambient_intensity = float(q.get("ambient_intensity", [0.45])[0])
        mountain_roughness = float(q.get("mountain_roughness", [1.0])[0])

        # 3D interactive mesh rotation
        rot_pitch = float(q.get("rot_pitch", [0.0])[0])
        rot_yaw = float(q.get("rot_yaw", [0.0])[0])

        # REGNUM Photorealistic Graphics Knobs
        show_canopy = q.get("show_canopy", ["true"])[0].lower() in ("true", "1", "yes")
        canopy_density = float(q.get("canopy_density", [0.85])[0])
        crown_size = float(q.get("crown_size", [5.0])[0])
        forest_shadows = q.get("forest_shadows", ["true"])[0].lower() in ("true", "1", "yes")
        forest_clearings = q.get("forest_clearings", ["true"])[0].lower() in ("true", "1", "yes")
        riparian_trees = q.get("riparian_trees", ["true"])[0].lower() in ("true", "1", "yes")

        show_ocean_fx = q.get("show_ocean_fx", ["true"])[0].lower() in ("true", "1", "yes")
        show_wave_ripples = q.get("show_wave_ripples", ["true"])[0].lower() in ("true", "1", "yes")
        wave_ripples = float(q.get("wave_ripples", [1.0])[0])
        show_specular_glints = q.get("show_specular_glints", ["true"])[0].lower() in ("true", "1", "yes")
        specular_glints = float(q.get("specular_glints", [1.0])[0])
        show_coastal_surf = q.get("show_coastal_surf", ["true"])[0].lower() in ("true", "1", "yes")
        coastal_surf = float(q.get("coastal_surf", [1.0])[0])
        shelf_width = float(q.get("shelf_width", [1.0])[0])

        show_beaches = q.get("show_beaches", ["true"])[0].lower() in ("true", "1", "yes")
        beach_width = float(q.get("beach_width", [1.0])[0])
        sand_dunes = q.get("sand_dunes", ["true"])[0].lower() in ("true", "1", "yes")
        show_coastal_cliffs = q.get("show_coastal_cliffs", ["true"])[0].lower() in ("true", "1", "yes")
        coastal_cliffs = float(q.get("coastal_cliffs", [1.0])[0])

        show_rock_strata = q.get("show_rock_strata", ["true"])[0].lower() in ("true", "1", "yes")
        rock_strata = float(q.get("rock_strata", [1.0])[0])
        show_snow_peaks = q.get("show_snow_peaks", ["true"])[0].lower() in ("true", "1", "yes")
        snow_peaks = float(q.get("snow_peaks", [1.0])[0])
        snow_altitude = float(q.get("snow_altitude", [0.70])[0])

        show_ground_grain = q.get("show_ground_grain", ["true"])[0].lower() in ("true", "1", "yes")
        ground_grain = float(q.get("ground_grain", [1.0])[0])
        show_soil_parcels = q.get("show_soil_parcels", ["true"])[0].lower() in ("true", "1", "yes")
        soil_parcels = float(q.get("soil_parcels", [1.0])[0])
        field_filaments = q.get("field_filaments", ["true"])[0].lower() in ("true", "1", "yes")

        carve_rivers = q.get("carve_rivers", ["true"])[0].lower() in ("true", "1", "yes")
        river_width = float(q.get("river_width", [1.0])[0])
        estuary_fan = q.get("estuary_fan", ["true"])[0].lower() in ("true", "1", "yes")
        riparian_turf = q.get("riparian_turf", ["true"])[0].lower() in ("true", "1", "yes")

        show_atmosphere = q.get("show_atmosphere", ["true"])[0].lower() in ("true", "1", "yes")
        show_cloud_shadows = q.get("show_cloud_shadows", ["true"])[0].lower() in ("true", "1", "yes")
        cloud_shadows = float(q.get("cloud_shadows", [0.55])[0])
        show_aerial_haze = q.get("show_aerial_haze", ["true"])[0].lower() in ("true", "1", "yes")
        aerial_haze = float(q.get("aerial_haze", [0.50])[0])
        show_split_tone = q.get("show_split_tone", ["true"])[0].lower() in ("true", "1", "yes")
        split_tone = float(q.get("split_tone", [0.60])[0])
        vignette = q.get("vignette", ["true"])[0].lower() in ("true", "1", "yes")
        frame = int(q.get("frame", [0])[0])

        # Geopolitics & Macroeconomics Knobs
        geo_layer = q.get("geo_layer", ["overview"])[0].lower()
        num_nations = int(q.get("nations", [3])[0])
        nation_seed = int(q.get("nation_seed", [777])[0])
        show_cities = q.get("show_cities", ["true"])[0].lower() in ("true", "1", "yes")
        show_trade = q.get("show_trade", ["true"])[0].lower() in ("true", "1", "yes")
        show_provinces = q.get("show_provinces", ["true"])[0].lower() in ("true", "1", "yes")
        show_outlines = q.get("show_outlines", ["true"])[0].lower() in ("true", "1", "yes")
        show_resources = q.get("show_resources", ["true"])[0].lower() in ("true", "1", "yes")
        nation_alpha = float(q.get("nation_alpha", [0.55])[0])
        selected_cell = int(q.get("selected_cell", [-1])[0])

        canyon_depth = float(q.get("canyon_depth", [1.5])[0])
        valley_width = float(q.get("valley_width", [1.0])[0])

        graph_key = (
            seed,
            shape,
            points,
            rivers,
            round(sharpness, 2),
            round(moisture_bias, 2),
            round(north_temp, 2),
            round(south_temp, 2),
            round(persistence, 2),
            round(canyon_depth, 2),
            round(valley_width, 2),
        )
        gen = get_cached_graph(
            seed,
            shape,
            points,
            rivers,
            sharpness,
            moisture_bias=moisture_bias,
            north_temp=north_temp,
            south_temp=south_temp,
            persistence=persistence,
            canyon_depth=canyon_depth,
            valley_width=valley_width,
        )

        surf = None
        used_engine = "cpu"

        # 1. GPU Pipeline Execution (ModernGL hardware rasterization of CPU mapgen mesh with BRDF)
        if mode in ("micropolys", "gpu") and (engine == "gpu" or mode == "gpu") and is_gpu_ready(0.2):
            uniforms = {
                "sun_azimuth": sun_azimuth,
                "sun_elevation": sun_elevation,
                "sun_intensity": sun_intensity,
                "ambient_intensity": ambient_intensity,
                "mountain_roughness": mountain_roughness,
                "rot_pitch": rot_pitch,
                "rot_yaw": rot_yaw,
            }
            try:
                triangles, _ = get_cached_micropolys(
                    gen,
                    graph_key,
                    polys,
                    roughness,
                    jitter,
                    alpha,
                    height_scale,
                    smooth,
                    quad_fold=quad_fold,
                    ridge_noise=ridge_noise,
                    erosion_strength=erosion_strength,
                    erosion_droplets=erosion_droplets,
                )
                mesh_key = (
                    graph_key,
                    polys,
                    round(roughness, 1),
                    round(jitter, 2),
                    round(alpha, 2),
                    round(height_scale, 1),
                    round(smooth, 2),
                    quad_fold,
                    ridge_noise,
                    erosion_strength,
                    int(erosion_droplets),
                )
                surf = run_on_gpu(
                    _render_gpu_mesh_surface,
                    gen,
                    triangles,
                    size,
                    size,
                    uniforms,
                    mesh_key=mesh_key,
                )
                used_engine = "gpu"
            except Exception as e:
                sys.stderr.write(f"GPU render error, fallback to CPU: {e}\n")
                surf = None

        # 2. CPU Fallback / Alternative Modes (Only execute if surf was not already rendered by GPU)
        if surf is None:
            used_engine = "cpu"
            if mode in ("micropolys", "gpu"):
                triangles, _ = get_cached_micropolys(
                    gen,
                    graph_key,
                    polys,
                    roughness,
                    jitter,
                    alpha,
                    height_scale,
                    smooth,
                    quad_fold=quad_fold,
                    ridge_noise=ridge_noise,
                    erosion_strength=erosion_strength,
                    erosion_droplets=erosion_droplets,
                )
                surf = render_mesh(
                    gen,
                    triangles,
                    width=size,
                    height=size,
                    sun_azimuth=sun_azimuth,
                    sun_elevation=sun_elevation,
                    sun_intensity=sun_intensity,
                    ambient_intensity=ambient_intensity,
                    rot_pitch=rot_pitch,
                    rot_yaw=rot_yaw,
                )

            elif mode == "biomes":
                surf = gen.render_to_surface(
                    width=size,
                    height=size,
                    use_brdf=True,
                    use_noisy_edges=True,
                    show_roads=True,
                    show_lava=False,
                    render_micropolys=False,
                )

            elif mode == "elevation":
                surf = pygame.Surface((size, size))
                surf.fill((18, 48, 100))
                for c in gen.centers:
                    if c.ocean:
                        col = (18, 48, 100)
                    elif c.water:
                        col = (40, 110, 175)
                    else:
                        e = min(1.0, max(0.0, c.elevation))
                        if e < 0.25:
                            t = e / 0.25
                            col = (int(50 + 60 * t), int(140 + 40 * t), int(50 + 30 * t))
                        elif e < 0.60:
                            t = (e - 0.25) / 0.35
                            col = (int(110 + 70 * t), int(180 - 40 * t), int(80 - 20 * t))
                        elif e < 0.82:
                            t = (e - 0.60) / 0.22
                            col = (int(180 - 40 * t), int(140 - 20 * t), int(60 + 40 * t))
                        else:
                            t = (e - 0.82) / 0.18
                            col = (int(140 + 110 * t), int(120 + 130 * t), int(100 + 155 * t))

                    poly = gen.get_polygon_noisy_boundary(c)
                    if len(poly) >= 3:
                        pygame.draw.polygon(surf, col, poly)

            elif mode == "moisture":
                surf = pygame.Surface((size, size))
                surf.fill((18, 48, 100))
                for c in gen.centers:
                    if c.ocean:
                        col = (18, 48, 100)
                    elif c.water:
                        col = (40, 110, 175)
                    else:
                        m = min(1.0, max(0.0, c.moisture))
                        col = (
                            int(210 * (1.0 - m) + 20 * m),
                            int(190 * (1.0 - m) + 160 * m),
                            int(90 * (1.0 - m) + 80 * m),
                        )
                    poly = gen.get_polygon_noisy_boundary(c)
                    if len(poly) >= 3:
                        pygame.draw.polygon(surf, col, poly)

            elif mode == "watersheds":
                surf = gen.render_to_surface(
                    width=size,
                    height=size,
                    use_brdf=False,
                    show_watersheds=True,
                    render_micropolys=False,
                )

            elif mode == "wireframe":
                surf = pygame.Surface((size, size))
                surf.fill((22, 26, 34))
                for e in gen.edges:
                    if e.v0 and e.v1:
                        col = (60, 90, 130) if (e.d0 and e.d0.water and e.d1 and e.d1.water) else (140, 160, 190)
                        pygame.draw.line(surf, col, (e.v0.x, e.v0.y), (e.v1.x, e.v1.y), 1)
            elif mode in ("photorealistic", "regnum", "topographic", "realistic"):
                used_engine = "regnum-topo"
                regnum_key = (
                    id(gen), size,
                    show_canopy, round(canopy_density, 2), round(crown_size, 1),
                    forest_shadows, forest_clearings, riparian_trees,
                    show_ocean_fx, show_wave_ripples, round(wave_ripples, 2),
                    show_specular_glints, round(specular_glints, 2),
                    show_coastal_surf, round(coastal_surf, 2), round(shelf_width, 2),
                    show_beaches, round(beach_width, 2), sand_dunes,
                    show_coastal_cliffs, round(coastal_cliffs, 2),
                    show_rock_strata, round(rock_strata, 2),
                    show_snow_peaks, round(snow_peaks, 2), round(snow_altitude, 2),
                    show_ground_grain, round(ground_grain, 2),
                    show_soil_parcels, round(soil_parcels, 2), field_filaments,
                    carve_rivers, round(river_width, 2), estuary_fan, riparian_turf,
                    show_atmosphere, show_cloud_shadows, round(cloud_shadows, 2),
                    show_aerial_haze, round(aerial_haze, 2),
                    show_split_tone, round(split_tone, 2), vignette,
                    round(sun_azimuth, 1), round(sun_elevation, 1),
                    frame
                )
                if regnum_key in REGNUM_SURF_CACHE:
                    surf = REGNUM_SURF_CACHE[regnum_key]
                else:
                    surf = render_regnum_terrain(
                        gen=gen,
                        width=size,
                        height=size,
                        show_canopy=show_canopy,
                        canopy_density=canopy_density,
                        crown_size=crown_size,
                        forest_shadows=forest_shadows,
                        forest_clearings=forest_clearings,
                        riparian_trees=riparian_trees,
                        show_ocean_fx=show_ocean_fx,
                        show_wave_ripples=show_wave_ripples,
                        wave_ripples=wave_ripples,
                        show_specular_glints=show_specular_glints,
                        specular_glints=specular_glints,
                        show_coastal_surf=show_coastal_surf,
                        coastal_surf=coastal_surf,
                        shelf_width=shelf_width,
                        show_beaches=show_beaches,
                        beach_width=beach_width,
                        sand_dunes=sand_dunes,
                        show_coastal_cliffs=show_coastal_cliffs,
                        coastal_cliffs=coastal_cliffs,
                        show_rock_strata=show_rock_strata,
                        rock_strata=rock_strata,
                        show_snow_peaks=show_snow_peaks,
                        snow_peaks=snow_peaks,
                        snow_altitude=snow_altitude,
                        show_ground_grain=show_ground_grain,
                        ground_grain=ground_grain,
                        show_soil_parcels=show_soil_parcels,
                        soil_parcels=soil_parcels,
                        field_filaments=field_filaments,
                        carve_rivers=carve_rivers,
                        river_width=river_width,
                        estuary_fan=estuary_fan,
                        riparian_turf=riparian_turf,
                        show_atmosphere=show_atmosphere,
                        show_cloud_shadows=show_cloud_shadows,
                        cloud_shadows=cloud_shadows,
                        show_aerial_haze=show_aerial_haze,
                        aerial_haze=aerial_haze,
                        show_split_tone=show_split_tone,
                        split_tone=split_tone,
                        vignette=vignette,
                        sun_azimuth=sun_azimuth,
                        sun_elevation=sun_elevation,
                        frame=frame,
                    )
                    if len(REGNUM_SURF_CACHE) >= MAX_CACHE_ENTRIES:
                        REGNUM_SURF_CACHE.pop(next(iter(REGNUM_SURF_CACHE)))
                    REGNUM_SURF_CACHE[regnum_key] = surf

            elif mode == "geopolitics":
                tiles, nations = get_cached_geopolitics(
                    gen, seed, num_nations=num_nations, nation_seed=nation_seed
                )
                surf = render_voronoi_geopolitics(
                    gen=gen,
                    tiles=tiles,
                    nations=nations,
                    width=size,
                    height=size,
                    layer_mode=geo_layer,
                    show_cities=show_cities,
                    show_trade_routes=show_trade,
                    show_provinces=show_provinces,
                    show_cell_outlines=show_outlines,
                    show_resources=show_resources,
                    nation_alpha=nation_alpha,
                    selected_cell_index=selected_cell if selected_cell >= 0 else None,
                    frame=int(time.time() * 10) % 100,
                )

            else:
                # Guaranteed non-black fallback for any unknown mode
                surf = gen.render_to_surface(width=size, height=size, use_brdf=True)

        # 3. Permanent Failsafe Guard: Verify the surface has non-zero pixels
        if surf is None:
            sys.stderr.write("WARNING: surf is None, invoking guaranteed CPU emergency fallback.\n")
            used_engine = "cpu-emergency"
            surf = gen.render_to_surface(width=size, height=size, use_brdf=True)
        else:
            # Check center and quarter pixels
            test_pts = [(size // 2, size // 2), (size // 4, size // 4), (3 * size // 4, 3 * size // 4)]
            if all(sum(surf.get_at(pt)[:3]) == 0 for pt in test_pts):
                raw_test = pygame.image.tobytes(surf, "RGB")
                if max(raw_test) == 0:
                    sys.stderr.write("WARNING: Render produced an all-black surface! Triggering guaranteed CPU fallback.\n")
                    used_engine = "cpu-failsafe"
                    surf = gen.render_to_surface(width=size, height=size, use_brdf=True)

        # Encode directly to fast WebP buffer
        raw_rgb = pygame.image.tobytes(surf, "RGB")
        img = Image.frombytes("RGB", (size, size), raw_rgb)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=82)
        payload = buf.getvalue()

        dur_ms = (time.time() - t0) * 1000.0
        self.send_response(200)
        self.send_header("Content-Type", "image/webp")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Render-Time-Ms", f"{dur_ms:.1f}")
        self.send_header("X-Render-Engine", used_engine)
        self.send_header("X-Render-Resolution", f"{size}x{size}")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(payload)

    def handle_mesh_binary(self, q: Dict[str, list]):
        """Streams compact binary 3D mesh + river lines for 60-120 FPS client WebGL rendering."""
        import struct
        import gzip
        t0 = time.time()
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["perlin"])[0]
        points = int(q.get("points", [1000])[0])
        polys = int(q.get("polys", [16000])[0])
        height_scale = float(q.get("height_scale", [70.0])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        roughness = float(q.get("roughness", [3.0])[0])
        jitter = float(q.get("jitter", [0.22])[0])
        smooth = float(q.get("smooth", [0.70])[0])
        alpha = float(q.get("alpha", [0.0])[0])
        rivers = int(q.get("rivers", [25])[0])
        moisture_bias = float(q.get("moisture_bias", [0.0])[0])
        north_temp = float(q.get("north_temp", [0.0])[0])
        south_temp = float(q.get("south_temp", [0.0])[0])
        persistence = float(q.get("persistence", [0.0])[0])
        quad_fold = q.get("quad_fold", ["true"])[0].lower() in ("true", "1", "yes")
        ridge_noise = float(q.get("ridge_noise", [0.35])[0])
        erosion_strength = float(q.get("erosion_strength", [0.30])[0])
        erosion_droplets = int(q.get("erosion_droplets", [15000])[0])
        tree_density = float(q.get("tree_density", [1.0])[0])
        wave_intensity = float(q.get("wave_intensity", [1.0])[0])
        river_width = float(q.get("river_width", [1.0])[0])
        canyon_depth = float(q.get("canyon_depth", [1.5])[0])
        valley_width = float(q.get("valley_width", [1.0])[0])
        size = int(q.get("size", [1024])[0])

        graph_key = (
            seed,
            shape,
            points,
            rivers,
            round(sharpness, 2),
            round(moisture_bias, 2),
            round(north_temp, 2),
            round(south_temp, 2),
            round(persistence, 2),
            round(canyon_depth, 2),
            round(valley_width, 2),
        )
        gen = get_cached_graph(
            seed,
            shape,
            points,
            rivers,
            sharpness,
            moisture_bias=moisture_bias,
            north_temp=north_temp,
            south_temp=south_temp,
            persistence=persistence,
            canyon_depth=canyon_depth,
            valley_width=valley_width,
        )

        triangles, _ = get_cached_micropolys(
            gen,
            graph_key,
            polys,
            roughness,
            jitter,
            alpha,
            height_scale,
            smooth,
            quad_fold=quad_fold,
            ridge_noise=ridge_noise,
            erosion_strength=erosion_strength,
            erosion_droplets=erosion_droplets,
        )

        from render_engine.gpu.mesh_brdf_pipeline import build_vbo_data
        vbo_data, max_z = build_vbo_data(triangles)

        # Build spatial 2D KD-tree on final subdivided terrain mesh vertices for exact surface elevation sampling
        mesh_tree = None
        mesh_verts = vbo_data[:, :3] if len(vbo_data) > 0 else None
        if mesh_verts is not None and len(mesh_verts) > 0:
            try:
                from scipy.spatial import cKDTree
                mesh_tree = cKDTree(mesh_verts[:, :2])
            except Exception:
                mesh_tree = None

        def sample_mesh_elevation(pts_xy):
            """Sample elevations directly from the subdivided terrain surface with IDW interpolation."""
            if mesh_tree is None or len(pts_xy) == 0:
                return None
            coords = np.asarray(pts_xy, dtype=np.float32)
            dists, idxs = mesh_tree.query(coords, k=min(3, len(mesh_verts)))
            if dists.ndim == 1 or (dists.ndim == 2 and dists.shape[1] == 1):
                z_vals = mesh_verts[idxs.flatten(), 2]
            else:
                weights = 1.0 / np.maximum(dists, 1e-4)
                weights /= np.sum(weights, axis=1, keepdims=True)
                z_vals = np.sum(mesh_verts[idxs, 2] * weights, axis=1)
            # Add small vertical bias (+0.08 units in 1024-world) to sit right on bed without z-fighting
            return np.maximum(0.0, z_vals) + 0.08

        # Continuous Steepest-Descent 3D Water Ribbon Meshes
        river_arr = build_hydro_river_ribbons(
            gen, sample_mesh_elevation, height_scale,
            river_width_mult=river_width, river_count=rivers
        )
        lava_arr = np.empty((0,), dtype=np.float32)

        # 3D Low-Poly Trees on Forest Cells
        tree_arr = build_micropoly_trees(gen, sample_mesh_elevation, height_scale, tree_density)

        # 3D Coastal Wave Ribbons along Island Boundary Edges
        surf_arr = build_coastal_surf_ribbon(gen, ribbon_width=18.0 * wave_intensity)

        n_verts = len(vbo_data)
        n_river = len(river_arr) // 10
        n_lava = len(lava_arr) // 3
        n_tree = len(tree_arr) // 10
        n_surf = len(surf_arr) // 10

        hdr = struct.pack('<4sIIfIIII', b'MMSH', 2, n_verts, float(max_z), n_river, n_lava, n_tree, n_surf)
        raw_payload = hdr + vbo_data.tobytes() + river_arr.tobytes() + lava_arr.tobytes() + tree_arr.tobytes() + surf_arr.tobytes()

        accept_enc = self.headers.get("Accept-Encoding", "")
        dur_ms = (time.time() - t0) * 1000.0

        if "gzip" in accept_enc:
            compressed = gzip.compress(raw_payload, compresslevel=1)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(compressed)))
            self.send_header("X-Mesh-Vertices", str(n_verts))
            self.send_header("X-Mesh-Time-Ms", f"{dur_ms:.1f}")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(compressed)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(raw_payload)))
            self.send_header("X-Mesh-Vertices", str(n_verts))
            self.send_header("X-Mesh-Time-Ms", f"{dur_ms:.1f}")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(raw_payload)

    def handle_inspect(self, q: Dict[str, list]):
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["radial"])[0]
        points = int(q.get("points", [1000])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        moisture_bias = float(q.get("moisture_bias", [0.0])[0])
        north_temp = float(q.get("north_temp", [0.0])[0])
        south_temp = float(q.get("south_temp", [0.0])[0])
        persistence = float(q.get("persistence", [0.0])[0])
        nx = float(q.get("nx", [0.5])[0])
        ny = float(q.get("ny", [0.5])[0])
        size = int(q.get("size", [1024])[0])

        gen = get_cached_graph(
            seed,
            shape,
            points,
            25,
            sharpness,
            moisture_bias=moisture_bias,
            north_temp=north_temp,
            south_temp=south_temp,
            persistence=persistence,
        )
        cx = nx * CANONICAL_WORLD_SIZE
        cy = ny * CANONICAL_WORLD_SIZE

        center = gen.get_center_at(cx, cy)
        if not center:
            self.send_json({"error": "not found"}, status=404)
            return

        res = {
            "index": center.index,
            "biome": center.biome,
            "elevation": round(center.elevation, 3),
            "moisture": round(center.moisture, 3),
            "temperature": round(center.temperature, 3),
            "is_water": center.water,
            "is_ocean": center.ocean,
            "is_coast": center.coast,
        }

        # Geopolitics inspection metadata
        num_nations = int(q.get("nations", [3])[0])
        nation_seed = int(q.get("nation_seed", [777])[0])
        try:
            tiles, nations = get_cached_geopolitics(gen, seed, num_nations=num_nations, nation_seed=nation_seed)
            if hasattr(center, "region") and center.region:
                r = center.region
                owner = getattr(r, "owner_nation", None)
                res["nation"] = owner.name if owner else "Wilderness"
                res["city"] = getattr(r, "display_name", getattr(r, "city_name", r.name))
                res["is_capital"] = getattr(r, "is_national_capital", False)
                res["is_prov_capital"] = getattr(r, "is_provincial_capital", False)
                res["population"] = len(r.agents) if getattr(r, "agents", None) else getattr(r, "wilderness_pop", 0)
                res["resources"] = [str(item.value if hasattr(item, "value") else item) for item in getattr(r, "natural_resources", set())]
                if owner and hasattr(r, "recipes") and Goods.food in r.recipes:
                    res["food_price"] = round(r.recipes[Goods.food]["price"], 2)
        except Exception as e:
            sys.stderr.write(f"Inspect geopolitics error: {e}\n")

        self.send_json(res)

    def handle_export_usdz(self, q: Dict[str, list]):
        """Package and stream Apple Quick Look USDZ model for iOS Safari AR."""
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["radial"])[0]
        points = int(q.get("points", [1000])[0])
        polys = int(q.get("polys", [16000])[0])
        height_scale = float(q.get("height_scale", [70.0])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        roughness = float(q.get("roughness", [3.0])[0])
        jitter = float(q.get("jitter", [0.22])[0])
        smooth = float(q.get("smooth", [0.70])[0])
        alpha = float(q.get("alpha", [0.0])[0])
        moisture_bias = float(q.get("moisture_bias", [0.0])[0])
        north_temp = float(q.get("north_temp", [0.0])[0])
        south_temp = float(q.get("south_temp", [0.0])[0])
        persistence = float(q.get("persistence", [0.0])[0])
        quad_fold = q.get("quad_fold", ["true"])[0].lower() in ("true", "1", "yes")
        ridge_noise = float(q.get("ridge_noise", [0.35])[0])
        erosion_strength = float(q.get("erosion_strength", [0.30])[0])
        erosion_droplets = int(q.get("erosion_droplets", [15000])[0])

        graph_key = (
            seed,
            shape,
            points,
            25,
            round(sharpness, 2),
            round(moisture_bias, 2),
            round(north_temp, 2),
            round(south_temp, 2),
            round(persistence, 2),
        )
        gen = get_cached_graph(
            seed,
            shape,
            points,
            25,
            sharpness,
            moisture_bias=moisture_bias,
            north_temp=north_temp,
            south_temp=south_temp,
            persistence=persistence,
        )
        triangles, _ = get_cached_micropolys(
            gen,
            graph_key,
            polys,
            roughness,
            jitter,
            alpha,
            height_scale,
            smooth,
            quad_fold=quad_fold,
            ridge_noise=ridge_noise,
            erosion_strength=erosion_strength,
            erosion_droplets=erosion_droplets,
        )

        tmp_out = f"/tmp/island_web_{seed}_{os.getpid()}.usdz"
        export_island_wireframe_usdz(gen, triangles, tmp_out, wire_width=0.8)

        if not os.path.exists(tmp_out):
            self.send_error(500, "USDZ export failed")
            return

        with open(tmp_out, "rb") as f:
            data = f.read()

        try:
            os.remove(tmp_out)
        except OSError:
            pass

        self.send_response(200)
        # model/vnd.usdz+zip tells iOS Safari to activate AR Quick Look
        self.send_header("Content-Type", "model/vnd.usdz+zip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'inline; filename="island_{seed}.usdz"')
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Server Launcher
# ---------------------------------------------------------------------------
def run_server(host: str = "0.0.0.0", port: int = 8080):
    server = ThreadingHTTPServer((host, port), MapgenHTTPHandler)
    print(f"\n==========================================================")
    print(f"  Mapgen2 Mobile & Web Server Running")
    print(f"==========================================================")
    print(f"  • Local URL     : http://localhost:{port}")
    print(f"  • Tailscale URL : http://100.126.125.100:{port}")
    print(f"  • iPhone URL    : http://100.126.125.100:{port}")
    print(f"==========================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mapgen2 Terrain Explorer Web Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port number")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)
