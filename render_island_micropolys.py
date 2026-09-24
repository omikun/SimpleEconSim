#!/usr/bin/env python3
"""
render_island_micropolys.py — Interactive CLI & Generator for High-Poly Polygonal Islands.

Allows tweaking:
- Target polygon count (e.g., 2,000, 8,000, 16,000, 32,000, 64,000+)
- Subdivision methods:
    1. 'adaptive'  : Isotropic 1-to-4 recursive subdivision prioritized by area (default)
    2. 'depth'     : Uniform 1-to-4 recursive subdivision with fixed depth (4x per depth)
    3. 'spokes'    : Radial perimeter fan subdivision along fractal noisy edges
    4. 'redblob'   : Red Blob Games 2-way fold (mountain ridges vs river valleys)
- Fractal elevation roughness
- Corner ridge elevation boost alpha (Red Blob model)
- Island seeds and point density

Usage examples:
    ./venv/bin/python3 render_island_micropolys.py --polys 16000
    ./venv/bin/python3 render_island_micropolys.py --polys 32000 --roughness 6.0
    ./venv/bin/python3 render_island_micropolys.py --mode spokes --polys 12000
    ./venv/bin/python3 render_island_micropolys.py --mode redblob --seed 42
    ./venv/bin/python3 render_island_micropolys.py --help
"""

import argparse
import math
import os
import sys
import time
from typing import List, Tuple

# Enable headless pygame rendering by default unless window is requested
if "--window" not in sys.argv:
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

import numpy as np
import pygame

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from polygon_map import PolygonMapGenerator, BIOME_COLORS


def procedural_fbm_elevation(x, y, seed=42, amplitude=1.0):
    """Continuous multi-scale procedural elevation noise to break piecewise planar ramps."""
    fx = x * 0.006 + seed * 0.17
    fy = y * 0.006 + seed * 0.23
    return amplitude * (
        (math.sin(fx * 1.0) * math.cos(fy * 1.0)) * 4.0 +
        (math.sin(fx * 2.3 + 1.2) * math.cos(fy * 2.1 - 0.7)) * 2.2 +
        (math.sin(fx * 4.7 - 2.1) * math.cos(fy * 4.9 + 1.4)) * 1.1 +
        (math.sin(fx * 9.3 + 0.5) * math.cos(fy * 9.1 - 1.9)) * 0.55
    )


def procedural_ridged_elevation(x, y, base_elevation, seed=42, amplitude=1.0, ridge_roughness=0.35):
    """
    Musgrave ridged multifractal noise with domain warping and elevation weighting.
    Computes inverted noise ridges: (1.0 - |noise|)^2, attenuated on lowlands so only
    mountain peaks and high plateaus form razor-sharp arêtes.
    """
    if ridge_roughness <= 1e-4 or base_elevation <= 0.20:
        return 0.0

    # Domain warping to give organic geological strata folds
    warp_x = math.sin(x * 0.004 + seed * 0.31) * 12.0
    warp_y = math.cos(y * 0.004 + seed * 0.47) * 12.0
    wx = x + warp_x
    wy = y + warp_y

    fx = wx * 0.008 + seed * 0.13
    fy = wy * 0.008 + seed * 0.29

    # Multi-octave ridged noise accumulation: (1 - |noise|)^2
    n1 = 1.0 - abs(math.sin(fx * 1.0) * math.cos(fy * 1.0))
    n2 = 1.0 - abs(math.sin(fx * 2.1 + 0.9) * math.cos(fy * 2.3 - 0.5))
    n3 = 1.0 - abs(math.sin(fx * 4.4 - 1.7) * math.cos(fy * 4.2 + 1.1))
    n4 = 1.0 - abs(math.sin(fx * 8.9 + 0.4) * math.cos(fy * 8.7 - 1.3))

    ridged = (n1 * n1 * 4.0 + n2 * n2 * 2.2 + n3 * n3 * 1.2 + n4 * n4 * 0.6) - 3.2

    # Attenuation factor: 0 on lowlands/coast, ramp up nonlinearly on mountain peaks
    crag_weight = max(0.0, (base_elevation - 0.25) / 0.75) ** 1.35
    return amplitude * ridge_roughness * ridged * crag_weight



def build_island_mesh(
    gen: PolygonMapGenerator,
    width: int = 1000,
    height: int = 1000,
    mode: str = "fractal",
    target_polys: int = 16000,
    subdivision_depth: int = 1,
    roughness: float = 3.0,
    lateral_jitter: float = 0.22,
    elevation_alpha: float = 0.0,
    elev_scale: float = 70.0,
    normal_smooth_ratio: float = 0.70,
    quad_fold: bool = True,
    ridge_noise: float = 0.35,
    erosion_strength: float = 0.30,
    erosion_droplets: int = 15000,
) -> Tuple[List[Tuple], int]:
    """
    Builds and subdivides the island's 3D micropoly mesh according to the chosen mode.
    Integrates:
    1. Global Continuous Island Heightmap Interpolation (eliminating per-polygon domes/pyramids).
    2. Continuous Particle-based Hydraulic & Thermal Erosion Field sampling.
    3. Musgrave Ridged Multifractal Elevation Noise with Domain Warping.
    Returns: (triangles_list, total_poly_count)
    """
    scale_x = width / gen.width
    scale_y = height / gen.height

    # 1. Global Continuous Hydraulic & Thermal Erosion Simulation
    from hydraulic_erosion import simulate_global_erosion
    erosion_field = simulate_global_erosion(
        gen,
        grid_size=192,
        num_droplets=int(erosion_droplets) if (erosion_strength > 0 and erosion_droplets > 0) else 0,
        carving_scale=erosion_strength,
        thermal_iterations=2,
        seed=gen.seed,
    )

    # Mode: Fractal Watertight Edge-Cached 2D+3D Subdivision (Default)
    if mode == "fractal":
        from collections import defaultdict
        vertices = []
        vertex_map = {}
        is_boundary_vertex = {}

        def get_or_add_vertex(pt3d, is_fixed=False):
            key = (round(float(pt3d[0]), 1), round(float(pt3d[1]), 1))
            if key in vertex_map:
                idx = vertex_map[key]
                if is_fixed:
                    is_boundary_vertex[idx] = True
                return idx
            idx = len(vertices)
            vertices.append(np.array(pt3d, dtype=np.float64))
            vertex_map[key] = idx
            is_boundary_vertex[idx] = is_fixed
            return idx

        base_triangles = []

        for edge in gen.edges:
            d0, d1 = edge.d0, edge.d1
            v0, v1 = edge.v0, edge.v1
            if not d0 or not d1 or not v0 or not v1:
                continue
            if d0.water and d1.water:
                continue

            z_v0 = erosion_field.sample_elevation(v0.x, v0.y) * elev_scale if not (v0.ocean or v0.coast) else 0.0
            z_v1 = erosion_field.sample_elevation(v1.x, v1.y) * elev_scale if not (v1.ocean or v1.coast) else 0.0
            z_d0 = erosion_field.sample_elevation(d0.x, d0.y) * elev_scale if not (d0.ocean or d0.coast) else 0.0
            z_d1 = erosion_field.sample_elevation(d1.x, d1.y) * elev_scale if not (d1.ocean or d1.coast) else 0.0

            if elevation_alpha > 0.0:
                adj_v0 = [erosion_field.sample_elevation(c.x, c.y) * elev_scale for c in v0.touches if not c.water]
                if adj_v0:
                    z_v0 += elevation_alpha * (max(adj_v0) - min(adj_v0)) * 0.5
                adj_v1 = [erosion_field.sample_elevation(c.x, c.y) * elev_scale for c in v1.touches if not c.water]
                if adj_v1:
                    z_v1 += elevation_alpha * (max(adj_v1) - min(adj_v1)) * 0.5

            # River channel bed carving for physical valleys
            if edge.river > 0:
                z_v0 -= min(3.5, edge.river * 0.75)
                z_v1 -= min(3.5, edge.river * 0.75)

            p_v0 = np.array([v0.x * scale_x, v0.y * scale_y, z_v0], dtype=np.float64)
            p_v1 = np.array([v1.x * scale_x, v1.y * scale_y, z_v1], dtype=np.float64)
            p_d0 = np.array([d0.x * scale_x, d0.y * scale_y, z_d0], dtype=np.float64)
            p_d1 = np.array([d1.x * scale_x, d1.y * scale_y, z_d1], dtype=np.float64)

            idx_v0 = get_or_add_vertex(p_v0, is_fixed=(v0.ocean or v0.coast))
            idx_v1 = get_or_add_vertex(p_v1, is_fixed=(v1.ocean or v1.coast))
            idx_d0 = get_or_add_vertex(p_d0, is_fixed=(d0.ocean or d0.coast))
            idx_d1 = get_or_add_vertex(p_d1, is_fixed=(d1.ocean or d1.coast))

            col0 = np.array(BIOME_COLORS.get(d0.biome, (120, 160, 100)), dtype=np.float64)
            col1 = np.array(BIOME_COLORS.get(d1.biome, (120, 160, 100)), dtype=np.float64)
            if not d1.water:
                col0 = col0 * 0.70 + col1 * 0.30
                col1 = col1 * 0.70 + col0 * 0.30

            if edge.river > 0:
                col0 = col0 * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25
                col1 = col1 * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25
                # River fold along v0-v1 preserves continuous valley channel
                base_triangles.append((idx_v0, idx_v1, idx_d0, col0, (z_v0 + z_v1 + z_d0) / (3.0 * elev_scale), True))
                base_triangles.append((idx_v1, idx_v0, idx_d1, col1, (z_v1 + z_v0 + z_d1) / (3.0 * elev_scale), True))
            else:
                diag_v = np.linalg.norm(p_v0 - p_v1)
                diag_d = np.linalg.norm(p_d0 - p_d1)
                if diag_v < diag_d:
                    if not d0.water:
                        base_triangles.append((idx_v0, idx_v1, idx_d0, col0, (z_v0 + z_v1 + z_d0) / (3.0 * elev_scale), False))
                    if not d1.water:
                        base_triangles.append((idx_v1, idx_v0, idx_d1, col1, (z_v1 + z_v0 + z_d1) / (3.0 * elev_scale), False))
                else:
                    base_triangles.append((idx_v0, idx_d1, idx_d0, col0 if not d0.water else col1, (z_v0 + z_d1 + z_d0) / (3.0 * elev_scale), False))
                    base_triangles.append((idx_v1, idx_d0, idx_d1, col1 if not d1.water else col0, (z_v1 + z_d0 + z_d1) / (3.0 * elev_scale), False))

        vertex_colors = {}
        for idx_a, idx_b, idx_c, col, el, riv in base_triangles:
            for idx in (idx_a, idx_b, idx_c):
                if idx not in vertex_colors:
                    vertex_colors[idx] = col.copy()
                else:
                    vertex_colors[idx] = vertex_colors[idx] * 0.5 + col * 0.5

        triangles_idx = list(base_triangles)
        edge_midpoints = {}
        rng = np.random.RandomState(gen.seed)

        def get_midpoint(i_a, i_b, depth):
            edge_key = (min(i_a, i_b), max(i_a, i_b))
            if edge_key in edge_midpoints:
                return edge_midpoints[edge_key]

            pa = vertices[i_a]
            pb = vertices[i_b]
            e_xy = pb[:2] - pa[:2]
            length = float(np.linalg.norm(e_xy))
            mid = (pa + pb) * 0.5

            if length > 1.2:
                n_perp = np.array([-e_xy[1], e_xy[0]], dtype=np.float64) / length
                decay = 0.70 ** depth
                disp_lat = rng.uniform(-lateral_jitter, lateral_jitter) * length * decay
                disp_long = rng.uniform(-0.10, 0.10) * length * decay

                mid[0] += n_perp[0] * disp_lat + (e_xy[0] / length) * disp_long
                mid[1] += n_perp[1] * disp_lat + (e_xy[1] / length) * disp_long

                # Continuous global height sampling at subdivided midpoint
                base_h = erosion_field.sample_elevation(mid[0] / scale_x, mid[1] / scale_y) * elev_scale
                fbm_val = procedural_fbm_elevation(mid[0], mid[1], gen.seed, amplitude=elev_scale / 70.0) * (decay * 0.35)
                mid_norm_elev = base_h / max(1.0, elev_scale)
                rdg_val = procedural_ridged_elevation(mid[0], mid[1], mid_norm_elev, gen.seed, amplitude=elev_scale / 45.0, ridge_roughness=ridge_noise) * (decay * 0.5)
                disp_z = rng.uniform(-0.35, 0.35) * roughness * (length / 24.0) + fbm_val + rdg_val
                mid[2] = 0.70 * base_h + 0.30 * mid[2] + disp_z
                if is_boundary_vertex.get(i_a, False) and is_boundary_vertex.get(i_b, False):
                    mid[2] = 0.0

            idx_mid = len(vertices)
            vertices.append(mid)
            is_boundary_vertex[idx_mid] = is_boundary_vertex.get(i_a, False) and is_boundary_vertex.get(i_b, False)

            c_a = vertex_colors.get(i_a, np.array([120, 160, 100], dtype=np.float64))
            c_b = vertex_colors.get(i_b, np.array([120, 160, 100], dtype=np.float64))
            vertex_colors[idx_mid] = (c_a + c_b) * 0.5

            edge_midpoints[edge_key] = idx_mid
            return idx_mid

        depth = 0
        while len(triangles_idx) < target_polys:
            new_triangles = []
            for i_a, i_b, i_c, col, el, riv in triangles_idx:
                m_ab = get_midpoint(i_a, i_b, depth)
                m_bc = get_midpoint(i_b, i_c, depth)
                m_ca = get_midpoint(i_c, i_a, depth)

                new_triangles.append((i_a, m_ab, m_ca, col, el, riv))
                new_triangles.append((i_b, m_bc, m_ab, col, el, riv))
                new_triangles.append((i_c, m_ca, m_bc, col, el, riv))
                new_triangles.append((m_ab, m_bc, m_ca, col, el, riv))

            triangles_idx = new_triangles

            # Multi-level vertex elevation relaxation for smooth natural transitions
            adj_map = defaultdict(set)
            for i_a, i_b, i_c, _, _, _ in triangles_idx:
                adj_map[i_a].add(i_b)
                adj_map[i_a].add(i_c)
                adj_map[i_b].add(i_a)
                adj_map[i_b].add(i_c)
                adj_map[i_c].add(i_a)
                adj_map[i_c].add(i_b)

            relax_weight = 0.20 * (0.75 ** depth)
            for v_idx in list(adj_map.keys()):
                if is_boundary_vertex.get(v_idx, False):
                    continue
                neighbors = list(adj_map[v_idx])
                if len(neighbors) >= 3:
                    neighbor_z_mean = float(np.mean([vertices[n][2] for n in neighbors]))
                    vertices[v_idx][2] = (1.0 - relax_weight * 1.5) * vertices[v_idx][2] + (relax_weight * 1.5) * neighbor_z_mean
                    vertices[v_idx][2] += rng.uniform(-0.5, 0.5) * (roughness * 0.15 * (0.65 ** depth))

            depth += 1
            if len(triangles_idx) >= target_polys:
                break

        # Fast vectorized area-weighted vertex and face normals computation
        num_verts = len(vertices)
        num_tris = len(triangles_idx)

        verts_arr = np.asarray(vertices, dtype=np.float64)
        tri_indices = np.array([(t[0], t[1], t[2]) for t in triangles_idx], dtype=np.int32)

        pa_all = verts_arr[tri_indices[:, 0]]
        pb_all = verts_arr[tri_indices[:, 1]]
        pc_all = verts_arr[tri_indices[:, 2]]

        va_all = pb_all - pa_all
        vb_all = pc_all - pa_all
        cross_norms = np.cross(va_all, vb_all)

        # Ensure outward pointing normal
        neg_z = cross_norms[:, 2] < 0
        cross_norms[neg_z] = -cross_norms[neg_z]

        double_areas = np.linalg.norm(cross_norms, axis=1, keepdims=True)
        areas = double_areas * 0.5
        safe_double_areas = np.where(double_areas > 1e-6, double_areas, 1.0)
        face_normals = np.where(double_areas > 1e-6, cross_norms / safe_double_areas, np.array([0.0, 0.0, 1.0]))

        # Accumulate weighted normals at vertices
        weighted_face_norms = face_normals * areas
        vertex_normals = np.zeros((num_verts, 3), dtype=np.float64)
        np.add.at(vertex_normals, tri_indices[:, 0], weighted_face_norms)
        np.add.at(vertex_normals, tri_indices[:, 1], weighted_face_norms)
        np.add.at(vertex_normals, tri_indices[:, 2], weighted_face_norms)

        vn_lens = np.linalg.norm(vertex_normals, axis=1, keepdims=True)
        safe_vn_lens = np.where(vn_lens > 1e-6, vn_lens, 1.0)
        vertex_normals = np.where(vn_lens > 1e-6, vertex_normals / safe_vn_lens, np.array([0.0, 0.0, 1.0]))

        # Vectorized blended normals
        avg_vert_norms = (vertex_normals[tri_indices[:, 0]] + vertex_normals[tri_indices[:, 1]] + vertex_normals[tri_indices[:, 2]]) / 3.0
        avg_vn_lens = np.linalg.norm(avg_vert_norms, axis=1, keepdims=True)
        safe_avg_vn_lens = np.where(avg_vn_lens > 1e-6, avg_vn_lens, 1.0)
        avg_vert_norms = np.where(avg_vn_lens > 1e-6, avg_vert_norms / safe_avg_vn_lens, face_normals)

        blended_norms = avg_vert_norms * normal_smooth_ratio + face_normals * (1.0 - normal_smooth_ratio)
        bn_lens = np.linalg.norm(blended_norms, axis=1, keepdims=True)
        safe_bn_lens = np.where(bn_lens > 1e-6, bn_lens, 1.0)
        blended_norms = np.where(bn_lens > 1e-6, blended_norms / safe_bn_lens, face_normals)

        # Unpack indices into (pa, pb, pc, col, avg_elev, is_riv, area, blended_norm)
        final_triangles = []
        for tri_idx, (i_a, i_b, i_c, col_base, avg_elev, is_riv) in enumerate(triangles_idx):
            pa = pa_all[tri_idx]
            pb = pb_all[tri_idx]
            pc = pc_all[tri_idx]
            area = float(areas[tri_idx, 0])
            blended_norm = blended_norms[tri_idx]

            col = (vertex_colors.get(i_a, col_base) + vertex_colors.get(i_b, col_base) + vertex_colors.get(i_c, col_base)) / 3.0
            final_triangles.append((pa, pb, pc, col, avg_elev, is_riv, area, blended_norm))

        return final_triangles, len(final_triangles)

    # 3. Legacy base triangles for other modes
    base_triangles = []
    for edge in gen.edges:
        d0, d1 = edge.d0, edge.d1
        v0, v1 = edge.v0, edge.v1
        if not d0 or not d1 or not v0 or not v1:
            continue
        if d0.water and d1.water:
            continue

        z_v0 = erosion_field.sample_elevation(v0.x, v0.y) * elev_scale if not (v0.ocean or v0.coast) else 0.0
        z_v1 = erosion_field.sample_elevation(v1.x, v1.y) * elev_scale if not (v1.ocean or v1.coast) else 0.0
        z_mid = (z_v0 + z_v1) * 0.5

        p_v0 = np.array([v0.x * scale_x, v0.y * scale_y, z_v0], dtype=np.float64)
        p_v1 = np.array([v1.x * scale_x, v1.y * scale_y, z_v1], dtype=np.float64)
        p_mid = np.array([edge.midpoint[0] * scale_x, edge.midpoint[1] * scale_y, z_mid], dtype=np.float64)

        col0 = np.array(BIOME_COLORS.get(d0.biome, (120, 160, 100)), dtype=np.float64)
        col1 = np.array(BIOME_COLORS.get(d1.biome, (120, 160, 100)), dtype=np.float64)
        if not d1.water:
            col0 = col0 * 0.70 + col1 * 0.30
            col1 = col1 * 0.70 + col0 * 0.30

        if edge.river > 0:
            col0 = col0 * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25
            col1 = col1 * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25

        def add_base_tri(pa, pb, pc, c, el, riv):
            area = 0.5 * abs((pb[0] - pa[0]) * (pc[1] - pa[1]) - (pc[0] - pa[0]) * (pb[1] - pa[1]))
            base_triangles.append((pa, pb, pc, c, el, riv, area))

        z_d0 = erosion_field.sample_elevation(d0.x, d0.y) * elev_scale if not (d0.ocean or d0.coast) else 0.0
        z_d1 = erosion_field.sample_elevation(d1.x, d1.y) * elev_scale if not (d1.ocean or d1.coast) else 0.0
        p_d0 = np.array([d0.x * scale_x, d0.y * scale_y, z_d0], dtype=np.float64)
        p_d1 = np.array([d1.x * scale_x, d1.y * scale_y, z_d1], dtype=np.float64)

        if mode == "redblob":
            if edge.river > 0:
                c_mix = (col0 + col1) * 0.5
                add_base_tri(p_v0, p_d1, p_d0, c_mix, (v0.elevation + d0.elevation) * 0.5, True)
                add_base_tri(p_v1, p_d0, p_d1, c_mix, (v1.elevation + d1.elevation) * 0.5, True)
            else:
                if not d0.water:
                    add_base_tri(p_v0, p_v1, p_d0, col0, (v0.elevation + v1.elevation + d0.elevation) / 3.0, False)
                if not d1.water:
                    add_base_tri(p_v1, p_v0, p_d1, col1, (v0.elevation + v1.elevation + d1.elevation) / 3.0, False)
        else:
            if not d0.water:
                add_base_tri(p_d0, p_v0, p_mid, col0, (d0.elevation + v0.elevation) * 0.5, edge.river > 0)
                add_base_tri(p_d0, p_mid, p_v1, col0, (d0.elevation + v1.elevation) * 0.5, edge.river > 0)

            if not d1.water:
                add_base_tri(p_d1, p_v1, p_mid, col1, (d1.elevation + v1.elevation) * 0.5, edge.river > 0)
                add_base_tri(p_d1, p_mid, p_v0, col1, (d1.elevation + v0.elevation) * 0.5, edge.river > 0)

    # 3. Apply Chosen Subdivision Strategy
    if mode == "adaptive":
        triangles = list(base_triangles)
        rng_seed = 101
        while len(triangles) < target_polys:
            needed = target_polys - len(triangles)
            num_to_subdiv = min(len(triangles), max(1, needed // 3))

            triangles.sort(key=lambda t: t[6], reverse=True)
            to_split = triangles[:num_to_subdiv]
            untouched = triangles[num_to_subdiv:]

            new_triangles = list(untouched)
            for idx, (pa, pb, pc, c, el, riv, _) in enumerate(to_split):
                rng = np.random.RandomState(rng_seed + idx)
                m_ab = (pa + pb) * 0.5
                m_bc = (pb + pc) * 0.5
                m_ca = (pc + pa) * 0.5

                edge_len = (np.linalg.norm(pb[:2] - pa[:2]) + np.linalg.norm(pc[:2] - pb[:2]) + np.linalg.norm(pa[:2] - pc[:2])) / 3.0
                scale = roughness * (edge_len / 40.0)
                m_ab[2] += (rng.rand() - 0.5) * scale
                m_bc[2] += (rng.rand() - 0.5) * scale
                m_ca[2] += (rng.rand() - 0.5) * scale

                for sa, sb, sc in [(pa, m_ab, m_ca), (pb, m_bc, m_ab), (pc, m_ca, m_bc), (m_ab, m_bc, m_ca)]:
                    area = 0.5 * abs((sb[0] - sa[0]) * (sc[1] - sa[1]) - (sc[0] - sa[0]) * (sb[1] - sa[1]))
                    new_triangles.append((sa, sb, sc, c, el, riv, area))

            triangles = new_triangles
            rng_seed += 1000
            if len(triangles) >= target_polys or num_to_subdiv == len(to_split) == 0:
                break

        return triangles, len(triangles)

    elif mode == "depth":
        def subdivide_depth(tri, d, seed):
            if d <= 0:
                return [tri]
            pa, pb, pc, c, el, riv, _ = tri
            rng = np.random.RandomState(seed)
            m_ab = (pa + pb) * 0.5
            m_bc = (pb + pc) * 0.5
            m_ca = (pc + pa) * 0.5

            edge_len = (np.linalg.norm(pb[:2] - pa[:2]) + np.linalg.norm(pc[:2] - pb[:2]) + np.linalg.norm(pa[:2] - pc[:2])) / 3.0
            scale = (roughness / (2.0 ** (subdivision_depth - d))) * (edge_len / 40.0)
            m_ab[2] += (rng.rand() - 0.5) * scale
            m_bc[2] += (rng.rand() - 0.5) * scale
            m_ca[2] += (rng.rand() - 0.5) * scale

            res = []
            for i, (sa, sb, sc) in enumerate([(pa, m_ab, m_ca), (pb, m_bc, m_ab), (pc, m_ca, m_bc), (m_ab, m_bc, m_ca)]):
                area = 0.5 * abs((sb[0] - sa[0]) * (sc[1] - sa[1]) - (sc[0] - sa[0]) * (sb[1] - sa[1]))
                res.extend(subdivide_depth((sa, sb, sc, c, el, riv, area), d - 1, seed * 7 + i * 31 + 5))
            return res

        triangles = []
        for idx, tri in enumerate(base_triangles):
            triangles.extend(subdivide_depth(tri, subdivision_depth, idx * 13 + 7))
        return triangles, len(triangles)

    elif mode == "spokes":
        # Radial perimeter spoke fans
        triangles = []
        segs = max(1, target_polys // (max(1, len(base_triangles)) // 2))
        for p in gen.centers:
            if p.water or len(p.corners) < 3:
                continue
            p_pt3d = np.array([p.x * scale_x, p.y * scale_y, p.elevation * elev_scale], dtype=np.float64)
            base_color = np.array(BIOME_COLORS.get(p.biome, (120, 160, 100)), dtype=np.float64)

            for r in p.neighbors:
                edge = next((e for e in p.borders if e.d0 == r or e.d1 == r), None)
                if not edge or not edge.v0 or not edge.v1:
                    continue
                col = base_color.copy()
                if not r.water:
                    col = col * 0.70 + np.array(BIOME_COLORS.get(r.biome, col), dtype=np.float64) * 0.30
                if edge.river > 0:
                    col = col * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25

                z_v0 = v_elev.get(edge.v0.index, edge.v0.elevation) * elev_scale
                z_v1 = v_elev.get(edge.v1.index, edge.v1.elevation) * elev_scale
                p_v0 = np.array([edge.v0.x * scale_x, edge.v0.y * scale_y, z_v0], dtype=np.float64)
                p_v1 = np.array([edge.v1.x * scale_x, edge.v1.y * scale_y, z_v1], dtype=np.float64)
                p_mid = np.array([edge.midpoint[0] * scale_x, edge.midpoint[1] * scale_y, (z_v0 + z_v1) * 0.5], dtype=np.float64)

                for start, end in [(p_v0, p_mid), (p_mid, p_v1)]:
                    for s in range(segs):
                        t0 = s / segs
                        t1 = (s + 1) / segs
                        pa = p_pt3d
                        pb = (1.0 - t0) * start + t0 * end
                        pc = (1.0 - t1) * start + t1 * end
                        area = 0.5 * abs((pb[0] - pa[0]) * (pc[1] - pa[1]) - (pc[0] - pa[0]) * (pb[1] - pa[1]))
                        triangles.append((pa, pb, pc, col, p.elevation, edge.river > 0, area))

        return triangles, len(triangles)

    else:
        # Default 'redblob' fold without extra subdivision
        return base_triangles, len(base_triangles)


def render_mesh(
    gen: PolygonMapGenerator,
    triangles: List[Tuple],
    width: int = 1000,
    height: int = 1000,
    snow_threshold: float = 0.82,
    sun_azimuth: float = -135.0,
    sun_elevation: float = 42.0,
    sun_intensity: float = 1.15,
    ambient_intensity: float = 0.45,
) -> pygame.Surface:
    """Rasterizes the 3D micropoly mesh onto a Pygame surface with multi-light shading."""
    surface = pygame.Surface((width, height))
    surface.fill((28, 48, 85))  # Deep ocean background

    scale_x = width / gen.width
    scale_y = height / gen.height

    # Draw ocean cells
    for c in gen.centers:
        if not c.water or len(c.corners) < 3:
            continue
        poly_pts = [(int(cn.x * scale_x), int(cn.y * scale_y)) for cn in c.corners]
        if len(poly_pts) >= 3:
            pygame.draw.polygon(surface, (28, 48, 85), poly_pts)

    # Dynamic Sun vector from azimuth & elevation (matching ModernGL GPU pipeline)
    az_rad = math.radians(sun_azimuth)
    el_rad = math.radians(max(5.0, min(88.0, sun_elevation)))
    sun_x = math.cos(el_rad) * math.cos(az_rad)
    sun_y = math.cos(el_rad) * math.sin(az_rad)
    sun_z = math.sin(el_rad)
    L_sun = np.array([sun_x, sun_y, sun_z], dtype=np.float64)
    L_sun /= (np.linalg.norm(L_sun) + 1e-6)

    # Ambient sky fill light
    L_fill = np.array([0.45, -0.65, 0.60], dtype=np.float64)
    L_fill /= np.linalg.norm(L_fill)

    for tri in triangles:
        if len(tri) == 8:
            pa, pb, pc, col_base, avg_elev, is_riv, _, norm = tri
        else:
            pa, pb, pc, col_base, avg_elev, is_riv, _ = tri
            va = pb - pa
            vb = pc - pa
            norm = np.cross(va, vb)
            if norm[2] < 0:
                norm = -norm
            n_len = np.linalg.norm(norm)
            norm = norm / n_len if n_len > 1e-6 else np.array([0.0, 0.0, 1.0], dtype=np.float64)

        # Multi-light illumination with configurable sun angle and intensities
        NdotL_sun = max(0.0, float(np.dot(norm, L_sun)))
        NdotL_fill = max(0.0, float(np.dot(norm, L_fill)))
        diffuse_sun = 0.44 * sun_intensity * math.pow(NdotL_sun, 1.05)
        diffuse_fill = 0.14 * NdotL_fill
        ambient = (0.65 + 0.15 * (norm[2] - 0.7)) * (ambient_intensity / 0.45)
        shade = ambient + diffuse_sun + diffuse_fill

        col = col_base.copy()

        # Dynamic steep cliff scree
        slope_val = 1.0 - norm[2]
        if slope_val > 0.14:
            cliff_w = min(0.60, (slope_val - 0.14) / 0.22)
            col = col * (1.0 - cliff_w) + np.array([66, 64, 71], dtype=np.float64) * cliff_w

        # Snow on high peaks
        if avg_elev > snow_threshold:
            snow_w = min(0.95, math.pow((avg_elev - snow_threshold) / (1.0 - snow_threshold), 2.0))
            col = col * (1.0 - snow_w) + np.array([242, 244, 250], dtype=np.float64) * snow_w

        shaded_rgb = col * shade
        # Soft-knee highlight compression
        for k in range(3):
            if shaded_rgb[k] > 220.0:
                shaded_rgb[k] = 220.0 + (shaded_rgb[k] - 220.0) * 0.35

        final_rgb = (
            min(248, max(0, int(shaded_rgb[0]))),
            min(248, max(0, int(shaded_rgb[1]))),
            min(248, max(0, int(shaded_rgb[2]))),
        )

        pts2d = [
            (int(pa[0]), int(pa[1])),
            (int(pb[0]), int(pb[1])),
            (int(pc[0]), int(pc[1])),
        ]
        if len(pts2d) >= 3:
            pygame.draw.polygon(surface, final_rgb, pts2d)

    # Rivers along noisy paths
    for e in gen.edges:
        if e.river > 0 and gen.noisy_edges:
            pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
            if len(pts) >= 2:
                r_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in pts]
                w = min(5, max(2, int(1 + math.sqrt(e.river))))
                pygame.draw.lines(surface, (28, 75, 135), False, r_pts, width=w)

    # Volcanic lava fissures
    for e in gen.edges:
        if getattr(e, 'lava', False):
            p0 = (int(e.v0.x * scale_x), int(e.v0.y * scale_y))
            p1 = (int(e.v1.x * scale_x), int(e.v1.y * scale_y))
            pygame.draw.line(surface, (255, 60, 0), p0, p1, 4)
            pygame.draw.line(surface, (255, 210, 50), p0, p1, 2)

    return surface


def export_island_wireframe_usdz(
    gen: PolygonMapGenerator,
    triangles: List[Tuple],
    usdz_path: str,
    wire_width: float = 0.8,
) -> str:
    """
    Exports the 3D micropoly wireframe mesh as an Apple Quick Look & AR compliant USDZ package.
    Each triangle edge is extruded into a thin quad strut mesh with Whittaker biome colors,
    oriented Y-up and centered so it spins cleanly in macOS Finder / Quick Look.
    """
    try:
        from pxr import Usd, UsdGeom, Sdf, Gf, UsdUtils
    except ImportError:
        print("Error: 'usd-core' (pxr) is required to export USDZ files. Install via: pip install usd-core", file=sys.stderr)
        return ""

    t0 = time.time()
    # 1. Extract unique edges with shared color
    unique_edges = {}
    for tri in triangles:
        pa, pb, pc = tri[0], tri[1], tri[2]
        pt_a = (round(float(pa[0]), 2), round(float(pa[1]), 2), round(float(pa[2]), 2))
        pt_b = (round(float(pb[0]), 2), round(float(pb[1]), 2), round(float(pb[2]), 2))
        pt_c = (round(float(pc[0]), 2), round(float(pc[1]), 2), round(float(pc[2]), 2))

        col_arr = np.array(tri[3], dtype=np.float64)
        for p1, p2 in [(pt_a, pt_b), (pt_b, pt_c), (pt_c, pt_a)]:
            edge_key = (min(p1, p2), max(p1, p2))
            if edge_key not in unique_edges:
                unique_edges[edge_key] = col_arr

    print(f"Extracted {len(unique_edges):,} unique wireframe edges from {len(triangles):,} triangles.")

    # 2. Build USD stage using binary crate package (.usdc in .usdz)
    os.makedirs(os.path.dirname(os.path.abspath(usdz_path)), exist_ok=True)
    temp_usdc = usdz_path.replace(".usdz", ".usdc") if usdz_path.endswith(".usdz") else usdz_path + ".usdc"

    if os.path.exists(temp_usdc):
        os.remove(temp_usdc)

    stage = Usd.Stage.CreateNew(temp_usdc)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)  # Apple Quick Look Y-up standard
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)       # Centimeters

    root = UsdGeom.Xform.Define(stage, "/Island")
    stage.SetDefaultPrim(root.GetPrim())

    mesh_prim = UsdGeom.Mesh.Define(stage, "/Island/WireframeMesh")

    points = []
    face_vertex_counts = []
    face_vertex_indices = []
    colors = []

    # Center model around origin (X: width/2, Z: height/2)
    cx = gen.width * 0.5
    cz = gen.height * 0.5
    half_w = wire_width * 0.5

    for (p1, p2), col in unique_edges.items():
        # Coordinate mapping to Y-up:
        # map X -> 3D X
        # map Y (screen downwards) -> 3D Z
        # map Z (elevation) -> 3D Y (up)
        p1_3d = np.array([p1[0] - cx, p1[2], p1[1] - cz], dtype=np.float64)
        p2_3d = np.array([p2[0] - cx, p2[2], p2[1] - cz], dtype=np.float64)

        edge_vec = p2_3d - p1_3d
        edge_len = np.linalg.norm(edge_vec)
        if edge_len < 1e-4:
            continue

        # Perpendicular horizontal vector in XZ plane
        horiz_dir = np.array([-edge_vec[2], 0.0, edge_vec[0]], dtype=np.float64)
        h_len = np.linalg.norm(horiz_dir)
        if h_len > 1e-6:
            perp = (horiz_dir / h_len) * half_w
        else:
            perp = np.array([half_w, 0.0, 0.0], dtype=np.float64)

        # 4 vertices for the thin quad strut
        v0 = p1_3d - perp
        v1 = p1_3d + perp
        v2 = p2_3d + perp
        v3 = p2_3d - perp

        base_idx = len(points)
        points.extend([
            Gf.Vec3f(float(v0[0]), float(v0[1]), float(v0[2])),
            Gf.Vec3f(float(v1[0]), float(v1[1]), float(v1[2])),
            Gf.Vec3f(float(v2[0]), float(v2[1]), float(v2[2])),
            Gf.Vec3f(float(v3[0]), float(v3[1]), float(v3[2])),
        ])

        # Double-sided quad (two triangles forward, two triangles reverse)
        face_vertex_counts.extend([3, 3, 3, 3])
        face_vertex_indices.extend([
            base_idx, base_idx + 1, base_idx + 2,
            base_idx, base_idx + 2, base_idx + 3,
            base_idx + 2, base_idx + 1, base_idx,
            base_idx + 3, base_idx + 2, base_idx,
        ])

        # Biome / elevation RGB in [0, 1]
        c_gf = Gf.Vec3f(float(col[0] / 255.0), float(col[1] / 255.0), float(col[2] / 255.0))
        colors.extend([c_gf, c_gf, c_gf, c_gf])

    mesh_prim.CreatePointsAttr().Set(points)
    mesh_prim.CreateFaceVertexCountsAttr().Set(face_vertex_counts)
    mesh_prim.CreateFaceVertexIndicesAttr().Set(face_vertex_indices)

    # Display colors per face
    color_primvar = mesh_prim.CreateDisplayColorPrimvar(UsdGeom.Tokens.uniform)
    color_primvar.Set(colors)

    # Double-sided attribute ensures strut faces render from any camera angle
    mesh_prim.CreateDoubleSidedAttr().Set(True)

    # Save binary layer
    stage.GetRootLayer().Save()

    # Package into USDZ
    success = UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(temp_usdc), usdz_path)
    if os.path.exists(temp_usdc):
        os.remove(temp_usdc)

    elapsed_ms = (time.time() - t0) * 1000.0
    if success:
        size_mb = os.path.getsize(usdz_path) / (1024 * 1024)
        print(f"USDZ Wireframe Export: {usdz_path} ({size_mb:.2f} MB, {elapsed_ms:.1f} ms)")
        return usdz_path
    else:
        print(f"Failed to package USDZ at: {usdz_path}", file=sys.stderr)
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="Generate and render high-resolution polygonal terrain with custom micropoly subdivision knobs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--polys", "-p", type=int, default=16000, help="Target polygon count (e.g. 2,000, 16,000, 64,000, 250,000, 1,000,000)")
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        default="fractal",
        choices=["fractal", "adaptive", "depth", "spokes", "redblob"],
        help="Subdivision algorithm: 'fractal' (watertight 2D+3D edge-cached), 'adaptive' (1-to-4 area-priority), 'depth' (uniform 1-to-4), 'spokes' (radial fan), 'redblob' (2-way ridge/valley fold)",
    )
    parser.add_argument("--depth", "-d", type=int, default=1, help="Subdivision depth for 'depth' mode (each level quadruples poly count)")
    parser.add_argument("--height-scale", "--elev-scale", dest="height_scale", type=float, default=70.0, help="Vertical elevation scale in 3D world units (default: 70.0, down from exaggerated 320.0)")
    parser.add_argument("--mountain-sharpness", "--sharpness", dest="mountain_sharpness", type=float, default=1.0, help="Mountain sharpness power exponent (default: 1.0 for Amit's exact curve, >1.0 for sharper peaks / flatter plains)")
    parser.add_argument("--roughness", "-r", type=float, default=3.0, help="Fractal midpoint displacement height roughness")
    parser.add_argument("--lateral-jitter", "-j", type=float, default=0.22, help="2D lateral displacement ratio perpendicular to edges (dissolves straight polygon seams)")
    parser.add_argument("--normal-smooth", type=float, default=0.70, help="Ratio of smoothed vertex normals to micro-facet normals (eliminates stair-step shading)")
    parser.add_argument("--alpha", "-a", type=float, default=0.25, help="Red Blob corner ridge elevation boost alpha")
    parser.add_argument("--quad-fold", dest="quad_fold", action="store_true", default=True, help="Enable dynamic quad folding (v0-v1 for ridges, d0-d1 for river ravines)")
    parser.add_argument("--no-quad-fold", dest="quad_fold", action="store_false", help="Disable dynamic quad folding")
    parser.add_argument("--ridge-noise", type=float, default=0.35, help="Musgrave ridged multifractal roughness factor (0.0 to 1.0)")
    parser.add_argument("--erosion-strength", type=float, default=0.30, help="Hydraulic erosion bedrock carving scale (0.0 to 1.0)")
    parser.add_argument("--erosion-droplets", type=int, default=15000, help="Number of hydraulic erosion simulation particles")
    parser.add_argument("--seed", "-s", type=int, default=777, help="Random seed for map generator")
    parser.add_argument("--points", "-n", type=int, default=1000, help="Number of Voronoi seed points")
    parser.add_argument("--size", type=int, default=1000, help="Render resolution in pixels (width=height)")
    parser.add_argument("--output", "-o", type=str, default="island_output.png", help="Output PNG file path")
    parser.add_argument("--usdz", type=str, default="", help="Optional output path to export 3D wireframe model (.usdz)")
    parser.add_argument("--wire-width", type=float, default=0.8, help="Strut width for 3D wireframe export")
    parser.add_argument("--window", "--gui", action="store_true", help="Launch interactive graphical Mapgen2 GUI explorer")

    args = parser.parse_args()

    if args.window:
        from mapgen_gui import MapgenGUI
        gui = MapgenGUI(seed=args.seed, num_points=args.points, target_polys=args.polys)
        gui.run()
        return

    print(f"\n========================================================")
    print(f"  Polygonal Terrain Micropoly Generator")
    print(f"========================================================")
    print(f"  • Target Polygons : {args.polys:,}")
    print(f"  • Subdivision Mode: {args.mode}")
    print(f"  • World Seed      : {args.seed}")
    print(f"  • Voronoi Points  : {args.points}")
    print(f"  • Height Scale    : {args.height_scale}")
    print(f"  • Sharpness Power : {args.mountain_sharpness}")
    print(f"  • Roughness       : {args.roughness}")
    print(f"  • Lateral Jitter  : {args.lateral_jitter}")
    print(f"  • Normal Smooth   : {args.normal_smooth}")
    print(f"  • Ridge Alpha (α) : {args.alpha}")
    print(f"  • Quad-Folding    : {'ON (Adaptive)' if args.quad_fold else 'OFF'}")
    print(f"  • Ridge Noise     : {args.ridge_noise}")
    print(f"  • Erosion Strength: {args.erosion_strength} ({args.erosion_droplets:,} drops)")
    print(f"  • Resolution      : {args.size} x {args.size}")
    if args.usdz:
        print(f"  • USDZ Wireframe  : {args.usdz}")
    print(f"--------------------------------------------------------")

    t_start = time.time()
    print("Generating base Voronoi dual-mesh & hydrology...")
    gen = PolygonMapGenerator(
        seed=args.seed,
        width=args.size,
        height=args.size,
        num_points=args.points,
        mountain_sharpness=args.mountain_sharpness,
        enable_corner_improvement=True,
        enable_roads=True,
        enable_lava=True,
    )
    t_gen = time.time()

    print(f"Subdividing mesh with '{args.mode}' method...")
    triangles, actual_poly_count = build_island_mesh(
        gen,
        width=args.size,
        height=args.size,
        mode=args.mode,
        target_polys=args.polys,
        subdivision_depth=args.depth,
        roughness=args.roughness,
        lateral_jitter=args.lateral_jitter,
        normal_smooth_ratio=args.normal_smooth,
        elevation_alpha=args.alpha,
        elev_scale=args.height_scale,
        quad_fold=args.quad_fold,
        ridge_noise=args.ridge_noise,
        erosion_strength=args.erosion_strength,
        erosion_droplets=args.erosion_droplets,
    )
    t_subdiv = time.time()

    print(f"Rasterizing {actual_poly_count:,} micropolygons with multi-light shading...")
    surface = render_mesh(gen, triangles, width=args.size, height=args.size)
    t_render = time.time()

    # Save output image
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pygame.image.save(surface, output_path)

    # Optional 3D USDZ wireframe export
    if args.usdz:
        usdz_out = os.path.abspath(args.usdz)
        export_island_wireframe_usdz(gen, triangles, usdz_out, wire_width=args.wire_width)

    print(f"\n[DONE] Successfully generated {actual_poly_count:,} micropolygons!")
    print(f"  - Map Generation : {(t_gen - t_start)*1000:.1f} ms")
    print(f"  - Subdivision    : {(t_subdiv - t_gen)*1000:.1f} ms")
    print(f"  - Shading/Render : {(t_render - t_subdiv)*1000:.1f} ms")
    print(f"  - Total Elapsed  : {(t_render - t_start)*1000:.1f} ms")
    print(f"  - Saved Image to : {output_path}")
    if args.usdz:
        print(f"  - Saved USDZ to  : {os.path.abspath(args.usdz)}")

    # Also copy to artifact directory if inside antigravity environment
    artifact_dir = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759"
    if os.path.isdir(artifact_dir):
        art_path = os.path.join(artifact_dir, "custom_island_render.png")
        pygame.image.save(surface, art_path)
        print(f"  - Artifact Saved : {art_path}")

    print(f"========================================================\n")


if __name__ == "__main__":
    main()
