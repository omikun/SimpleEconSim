import os
import sys
import math
import time
import numpy as np
import pygame
import matplotlib.pyplot as plt

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polygon_map import PolygonMapGenerator, BIOME_COLORS

ARTIFACT_DIR = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759"

def render_16k_recursive_subdivision(gen: PolygonMapGenerator, width: int = 1000, height: int = 1000,
                                     subdivision_depth: int = 1,
                                     elevation_alpha: float = 0.25,
                                     roughness: float = 8.0) -> tuple[pygame.Surface, int]:
    scale_x = width / gen.width
    scale_y = height / gen.height
    elev_scale = 320.0

    # 1. Corner elevations
    v_elev = {}
    for cn in gen.corners:
        if cn.ocean or cn.coast:
            v_elev[cn.index] = 0.0
        else:
            adj_elevs = [c.elevation for c in cn.touches if not c.water]
            if adj_elevs:
                c_max = max(adj_elevs)
                c_min = min(adj_elevs)
                v_elev[cn.index] = c_max + elevation_alpha * (c_max - c_min)
            else:
                v_elev[cn.index] = cn.elevation

    surface = pygame.Surface((width, height))
    surface.fill((28, 48, 85))

    # Base water
    for c in gen.centers:
        if not c.water or len(c.corners) < 3:
            continue
        poly_pts = [(int(cn.x * scale_x), int(cn.y * scale_y)) for cn in c.corners]
        if len(poly_pts) >= 3:
            pygame.draw.polygon(surface, (28, 48, 85), poly_pts)

    L_sun = np.array([-0.55, -0.55, 0.70], dtype=np.float64)
    L_sun /= np.linalg.norm(L_sun)
    L_fill = np.array([0.45, -0.65, 0.60], dtype=np.float64)
    L_fill /= np.linalg.norm(L_fill)

    # Build base triangle mesh across the island
    # Each quad (p, v0, r, v1) has 4 triangles: (p, v0, m), (p, m, v1), (r, v1, m), (r, m, v0)
    base_triangles = [] # (pa, pb, pc, col, avg_elev, is_river)

    for edge in gen.edges:
        d0, d1 = edge.d0, edge.d1
        v0, v1 = edge.v0, edge.v1
        if not d0 or not d1 or not v0 or not v1:
            continue
        if d0.water and d1.water:
            continue

        z_v0 = v_elev.get(v0.index, v0.elevation) * elev_scale
        z_v1 = v_elev.get(v1.index, v1.elevation) * elev_scale
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

        if not d0.water:
            p_d0 = np.array([d0.x * scale_x, d0.y * scale_y, d0.elevation * elev_scale], dtype=np.float64)
            base_triangles.append((p_d0, p_v0, p_mid, col0, (d0.elevation + v0.elevation)*0.5, edge.river > 0))
            base_triangles.append((p_d0, p_mid, p_v1, col0, (d0.elevation + v1.elevation)*0.5, edge.river > 0))

        if not d1.water:
            p_d1 = np.array([d1.x * scale_x, d1.y * scale_y, d1.elevation * elev_scale], dtype=np.float64)
            base_triangles.append((p_d1, p_v1, p_mid, col1, (d1.elevation + v1.elevation)*0.5, edge.river > 0))
            base_triangles.append((p_d1, p_mid, p_v0, col1, (d1.elevation + v0.elevation)*0.5, edge.river > 0))

    print(f"Base island triangles: {len(base_triangles)}")

    # 1-to-4 triangle subdivision
    def subdivide_tri(t, depth, seed_val):
        if depth <= 0:
            return [t]
        pa, pb, pc, col, elev, is_riv = t
        rng = np.random.RandomState(seed_val)
        
        # Midpoints with fractal displacement
        m_ab = (pa + pb) * 0.5
        m_bc = (pb + pc) * 0.5
        m_ca = (pc + pa) * 0.5

        # Vertical perturbation
        scale = roughness / (2.0 ** (2 - depth))
        m_ab[2] += (rng.rand() - 0.5) * scale
        m_bc[2] += (rng.rand() - 0.5) * scale
        m_ca[2] += (rng.rand() - 0.5) * scale

        t1 = (pa, m_ab, m_ca, col, elev, is_riv)
        t2 = (pb, m_bc, m_ab, col, elev, is_riv)
        t3 = (pc, m_ca, m_bc, col, elev, is_riv)
        t4 = (m_ab, m_bc, m_ca, col, elev, is_riv)

        res = []
        for i, sub_t in enumerate([t1, t2, t3, t4]):
            res.extend(subdivide_tri(sub_t, depth - 1, seed_val * 7 + i * 31 + 11))
        return res

    final_triangles = []
    # If base is ~4,000 triangles, 1 subdivision gives ~16,000 triangles!
    # If base is ~2,000 triangles, depth 1 gives 8,000; or we can subdivide selectively to hit 16,000!
    for idx, tri in enumerate(base_triangles):
        # We can subdivide each triangle into 4 (depth 1)
        sub_tris = subdivide_tri(tri, subdivision_depth, idx * 13 + 5)
        final_triangles.extend(sub_tris)

    print(f"Total subdivided triangles: {len(final_triangles)}")

    t0 = time.time()
    for (pa, pb, pc, col_base, avg_elev, is_riv) in final_triangles:
        va = pb - pa
        vb = pc - pa
        norm = np.cross(va, vb)
        if norm[2] < 0:
            norm = -norm
        n_len = np.linalg.norm(norm)
        if n_len > 1e-6:
            norm /= n_len
        else:
            norm = np.array([0.0, 0.0, 1.0], dtype=np.float64)

        NdotL_sun = max(0.0, float(np.dot(norm, L_sun)))
        NdotL_fill = max(0.0, float(np.dot(norm, L_fill)))
        diffuse_sun = 0.44 * math.pow(NdotL_sun, 1.15)
        diffuse_fill = 0.14 * NdotL_fill
        ambient = 0.68 + 0.12 * (norm[2] - 0.7)
        shade = ambient + diffuse_sun + diffuse_fill

        col = col_base.copy()
        slope_val = 1.0 - norm[2]
        if slope_val > 0.14:
            cliff_w = min(0.60, (slope_val - 0.14) / 0.22)
            col = col * (1.0 - cliff_w) + np.array([66, 64, 71], dtype=np.float64) * cliff_w

        if avg_elev > 0.82:
            snow_w = min(0.95, math.pow((avg_elev - 0.82) / 0.18, 2.0))
            col = col * (1.0 - snow_w) + np.array([242, 244, 250], dtype=np.float64) * snow_w

        shaded_rgb = col * shade
        for k in range(3):
            if shaded_rgb[k] > 220.0:
                shaded_rgb[k] = 220.0 + (shaded_rgb[k] - 220.0) * 0.35

        final_rgb = (
            min(248, max(0, int(shaded_rgb[0]))),
            min(248, max(0, int(shaded_rgb[1]))),
            min(248, max(0, int(shaded_rgb[2]))),
        )

        pts2d = [(int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), (int(pc[0]), int(pc[1]))]
        pygame.draw.polygon(surface, final_rgb, pts2d)

    t1 = time.time()
    print(f"Rasterized {len(final_triangles)} triangles in {(t1 - t0)*1000:.2f} ms")

    # Draw rivers & lava
    for edge in gen.edges:
        if edge.river > 0 and edge.v0 and edge.v1:
            r_w = max(1, min(6, int(math.sqrt(edge.river) * 1.5)))
            p0 = (int(edge.v0.x * scale_x), int(edge.v0.y * scale_y))
            p1 = (int(edge.v1.x * scale_x), int(edge.v1.y * scale_y))
            pygame.draw.line(surface, (45, 95, 145), p0, p1, r_w)

    for edge in gen.edges:
        if getattr(edge, 'lava', False) and edge.v0 and edge.v1:
            p0 = (int(edge.v0.x * scale_x), int(edge.v0.y * scale_y))
            p1 = (int(edge.v1.x * scale_x), int(edge.v1.y * scale_y))
            pygame.draw.line(surface, (255, 60, 0), p0, p1, 4)
            pygame.draw.line(surface, (255, 210, 50), p0, p1, 2)

    return surface, len(final_triangles)

def main():
    seed = 777
    size = 1000
    print("Generating polygon map with 1000 points...")
    gen = PolygonMapGenerator(seed=seed, width=size, height=size, num_points=1000,
                              enable_corner_improvement=True, enable_roads=True, enable_lava=True)

    print("Subdividing 1-to-4 recursively...")
    surf_subdiv, poly_count = render_16k_recursive_subdivision(gen, 1000, 1000, subdivision_depth=1, roughness=6.0)

    buf = pygame.image.tostring(surf_subdiv, "RGB")
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((1000, 1000, 3))

    out_path = os.path.join(ARTIFACT_DIR, "island_16k_recursive.png")
    plt.figure(figsize=(10, 10), dpi=150)
    plt.imshow(arr)
    plt.title(f"Procedural Elevation: 16k Micropoly Island ({poly_count:,} Polygons, 1-to-4 Subdivision)\n(https://www.redblobgames.com/x/1725-procedural-elevation/#rendering)",
              fontsize=11, fontweight='bold', pad=12)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches='tight')
    plt.close()
    print(f"Saved artifact to {out_path}")

if __name__ == '__main__':
    main()
