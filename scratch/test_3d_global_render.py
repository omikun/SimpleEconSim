import math, time
import numpy as np
import pygame
from scipy.interpolate import LinearNDInterpolator
from polygon_map import PolygonMapGenerator, BIOME_COLORS
from hydraulic_erosion import HydraulicErosionSim
from render_island_micropolys import (
    procedural_fbm_elevation,
    procedural_ridged_elevation,
    render_mesh,
)

print("Generating map...")
gen = PolygonMapGenerator(width=1000, height=1000, num_points=1000, seed=42)

# Build continuous global elevation field
pts, vals = [], []
for c in gen.centers:
    pts.append([c.x, c.y])
    vals.append(c.elevation if not c.water else 0.0)
for cn in gen.corners:
    pts.append([cn.x, cn.y])
    vals.append(cn.elevation if not cn.water else 0.0)

w, h = gen.width, gen.height
for bx in [-100, 0, w//2, w, w+100]:
    for by in [-100, 0, h//2, h, h+100]:
        pts.append([bx, by])
        vals.append(0.0)

pts = np.array(pts, dtype=np.float64)
vals = np.array(vals, dtype=np.float64)
interp = LinearNDInterpolator(pts, vals, fill_value=0.0)

grid_size = 256
gx, gy = np.meshgrid(np.linspace(0, w, grid_size), np.linspace(0, h, grid_size))
base_grid = interp(gx, gy)
base_grid = np.nan_to_num(base_grid, nan=0.0)

# Simulate droplets
sim = HydraulicErosionSim(grid_size=grid_size, seed=42)
land_mask = base_grid > 0.02
eroded_grid, _ = sim.simulate_droplets(base_grid, num_droplets=8000, land_mask=land_mask, carving_scale=0.35)
eroded_grid = sim.apply_thermal_erosion(eroded_grid, iterations=2)

def sample_h(x, y):
    gx_coord = max(0.0, min(grid_size - 1.001, (x / w) * (grid_size - 1)))
    gy_coord = max(0.0, min(grid_size - 1.001, (y / h) * (grid_size - 1)))
    ix, iy = int(gx_coord), int(gy_coord)
    fx, fy = gx_coord - ix, gy_coord - iy
    h00 = eroded_grid[iy, ix]
    h10 = eroded_grid[iy, ix + 1]
    h01 = eroded_grid[iy + 1, ix]
    h11 = eroded_grid[iy + 1, ix + 1]
    return (h00 * (1 - fx) + h10 * fx) * (1 - fy) + (h01 * (1 - fx) + h11 * fx) * fy

print("Building subdivided mesh with global continuous height sampling...")
elev_scale = 55.0
target_polys = 16000

vertices = []
vertex_map = {}
is_boundary_vertex = {}

def get_or_add_vertex(pt3d, is_fixed=False):
    key = (round(float(pt3d[0]), 1), round(float(pt3d[1]), 1))
    if key in vertex_map:
        idx = vertex_map[key]
        if is_fixed: is_boundary_vertex[idx] = True
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
    if not d0 or not d1 or not v0 or not v1: continue
    if d0.water and d1.water: continue

    z_v0 = sample_h(v0.x, v0.y) * elev_scale if not (v0.ocean or v0.coast) else 0.0
    z_v1 = sample_h(v1.x, v1.y) * elev_scale if not (v1.ocean or v1.coast) else 0.0
    z_d0 = sample_h(d0.x, d0.y) * elev_scale if not (d0.ocean or d0.coast) else 0.0
    z_d1 = sample_h(d1.x, d1.y) * elev_scale if not (d1.ocean or d1.coast) else 0.0

    p_v0 = np.array([v0.x, v0.y, z_v0], dtype=np.float64)
    p_v1 = np.array([v1.x, v1.y, z_v1], dtype=np.float64)
    p_d0 = np.array([d0.x, d0.y, z_d0], dtype=np.float64)
    p_d1 = np.array([d1.x, d1.y, z_d1], dtype=np.float64)

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
        base_triangles.append((idx_v0, idx_v1, idx_d0, col0, (z_v0 + z_v1 + z_d0) / (3.0 * elev_scale), True))
        base_triangles.append((idx_v1, idx_v0, idx_d1, col1, (z_v1 + z_v0 + z_d1) / (3.0 * elev_scale), True))
    else:
        diag_v = np.linalg.norm(p_v0 - p_v1)
        diag_d = np.linalg.norm(p_d0 - p_d1)
        if diag_v < diag_d:
            if not d0.water: base_triangles.append((idx_v0, idx_v1, idx_d0, col0, (z_v0 + z_v1 + z_d0) / (3.0 * elev_scale), False))
            if not d1.water: base_triangles.append((idx_v1, idx_v0, idx_d1, col1, (z_v1 + z_v0 + z_d1) / (3.0 * elev_scale), False))
        else:
            base_triangles.append((idx_v0, idx_d1, idx_d0, col0 if not d0.water else col1, (z_v0 + z_d1 + z_d0) / (3.0 * elev_scale), False))
            base_triangles.append((idx_v1, idx_d0, idx_d1, col1 if not d1.water else col0, (z_v1 + z_d0 + z_d1) / (3.0 * elev_scale), False))

vertex_colors = {}
for idx_a, idx_b, idx_c, col, el, riv in base_triangles:
    for idx in (idx_a, idx_b, idx_c):
        if idx not in vertex_colors: vertex_colors[idx] = col.copy()
        else: vertex_colors[idx] = vertex_colors[idx] * 0.5 + col * 0.5

triangles_idx = list(base_triangles)
edge_midpoints = {}
rng = np.random.RandomState(42)

def get_midpoint(i_a, i_b, depth):
    edge_key = (min(i_a, i_b), max(i_a, i_b))
    if edge_key in edge_midpoints:
        return edge_midpoints[edge_key]

    pa = vertices[i_a]
    pb = vertices[i_b]
    e_xy = pb[:2] - pa[:2]
    length = float(np.linalg.norm(e_xy))
    mid = (pa + pb) * 0.5

    if length > 1.5:
        decay = 0.70 ** depth
        base_h = sample_h(mid[0], mid[1]) * elev_scale
        fbm_val = procedural_fbm_elevation(mid[0], mid[1], 42, amplitude=elev_scale / 80.0) * (decay * 0.3)
        mid_norm_elev = base_h / elev_scale
        rdg_val = procedural_ridged_elevation(mid[0], mid[1], mid_norm_elev, 42, amplitude=elev_scale / 60.0, ridge_roughness=0.35) * (decay * 0.4)
        mid[2] = 0.70 * base_h + 0.30 * mid[2] + fbm_val + rdg_val + rng.uniform(-0.3, 0.3) * (length / 30.0) * decay
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
    needed = target_polys - len(triangles_idx)
    num_to_split = min(len(triangles_idx), max(1, needed // 3))
    def tri_area(t):
        p1, p2, p3 = vertices[t[0]], vertices[t[1]], vertices[t[2]]
        return 0.5 * abs((p2[0] - p1[0]) * (p3[1] - p1[1]) - (p3[0] - p1[0]) * (p2[1] - p1[1]))
    triangles_idx.sort(key=tri_area, reverse=True)
    to_split = triangles_idx[:num_to_split]
    untouched = triangles_idx[num_to_split:]
    new_triangles = list(untouched)
    for i_a, i_b, i_c, col, el, riv in to_split:
        m_ab = get_midpoint(i_a, i_b, depth)
        m_bc = get_midpoint(i_b, i_c, depth)
        m_ca = get_midpoint(i_c, i_a, depth)
        new_triangles.append((i_a, m_ab, m_ca, col, el, riv))
        new_triangles.append((i_b, m_bc, m_ab, col, el, riv))
        new_triangles.append((i_c, m_ca, m_bc, col, el, riv))
        new_triangles.append((m_ab, m_bc, m_ca, col, el, riv))
    triangles_idx = new_triangles
    depth += 1
    if len(triangles_idx) >= target_polys or num_to_split == 0: break

print(f"Total micropolygons: {len(triangles_idx):,}")

# Normals
vertex_normals = [np.array([0.0, 0.0, 0.0], dtype=np.float64) for _ in range(len(vertices))]
triangle_face_normals = []
for i_a, i_b, i_c, _, _, _ in triangles_idx:
    pa, pb, pc = vertices[i_a], vertices[i_b], vertices[i_c]
    norm = np.cross(pb - pa, pc - pa)
    area = float(np.linalg.norm(norm) * 0.5)
    if norm[2] < 0: norm = -norm
    norm_unit = norm / (area * 2.0) if area > 1e-6 else np.array([0.0, 0.0, 1.0])
    triangle_face_normals.append(norm_unit)
    vertex_normals[i_a] += norm_unit * area
    vertex_normals[i_b] += norm_unit * area
    vertex_normals[i_c] += norm_unit * area

for i in range(len(vertex_normals)):
    vn_len = float(np.linalg.norm(vertex_normals[i]))
    if vn_len > 1e-6: vertex_normals[i] /= vn_len
    else: vertex_normals[i] = np.array([0.0, 0.0, 1.0])

final_triangles = []
normal_smooth_ratio = 0.70
for tri_idx, (i_a, i_b, i_c, col_base, avg_elev, is_riv) in enumerate(triangles_idx):
    pa, pb, pc = vertices[i_a], vertices[i_b], vertices[i_c]
    face_norm = triangle_face_normals[tri_idx]
    avg_vert_norm = (vertex_normals[i_a] + vertex_normals[i_b] + vertex_normals[i_c]) / 3.0
    vn_len = float(np.linalg.norm(avg_vert_norm))
    if vn_len > 1e-6: avg_vert_norm /= vn_len
    else: avg_vert_norm = face_norm
    blended_norm = avg_vert_norm * normal_smooth_ratio + face_norm * (1.0 - normal_smooth_ratio)
    bn_len = float(np.linalg.norm(blended_norm))
    if bn_len > 1e-6: blended_norm /= bn_len
    col = (vertex_colors.get(i_a, col_base) + vertex_colors.get(i_b, col_base) + vertex_colors.get(i_c, col_base)) / 3.0
    area = 0.5 * abs((pb[0] - pa[0]) * (pc[1] - pa[1]) - (pc[0] - pa[0]) * (pb[1] - pa[1]))
    final_triangles.append((pa, pb, pc, col, avg_elev, is_riv, area, blended_norm))

surf = render_mesh(gen, final_triangles, width=1000, height=1000)
pygame.image.save(surf, "scratch/test_global_mesh_render.png")
print("Saved preview to scratch/test_global_mesh_render.png")
