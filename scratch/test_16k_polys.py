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

def render_with_target_polys(gen: PolygonMapGenerator, width: int = 1000, height: int = 1000,
                             target_polys: int = 16000, elevation_alpha: float = 0.25) -> tuple[pygame.Surface, int]:
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

    # Calculate current number of land half-edges
    land_borders = []
    for p in gen.centers:
        if p.water or len(p.corners) < 3:
            continue
        for r in p.neighbors:
            edge = next((e for e in p.borders if e.d0 == r or e.d1 == r), None)
            if edge and edge.v0 and edge.v1:
                land_borders.append((p, r, edge))

    num_borders = len(land_borders)
    # Each border will have 2 half-edges (path0 and path1).
    # To reach target_polys: segments_per_half = target_polys / (num_borders * 2)
    segments_per_half = max(1, int(round(target_polys / (num_borders * 2))))
    print(f"Land borders: {num_borders}. Required segments per half-edge: {segments_per_half}")

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

    total_micropolys = 0
    t0 = time.time()

    for p, r, edge in land_borders:
        p_pt3d = np.array([p.x * scale_x, p.y * scale_y, p.elevation * elev_scale], dtype=np.float64)
        base_color = np.array(BIOME_COLORS.get(p.biome, (120, 160, 100)), dtype=np.float64)
        col_edge = base_color.copy()
        if not r.water:
            r_col = np.array(BIOME_COLORS.get(r.biome, col_edge), dtype=np.float64)
            col_edge = col_edge * 0.70 + r_col * 0.30

        if edge.river > 0:
            col_edge = col_edge * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25

        z_v0 = v_elev.get(edge.v0.index, edge.v0.elevation) * elev_scale
        z_v1 = v_elev.get(edge.v1.index, edge.v1.elevation) * elev_scale
        z_mid = (z_v0 + z_v1) * 0.5

        # Subdivide path0 (v0 to mid) into segments_per_half segments
        # Subdivide path1 (v1 to mid) into segments_per_half segments
        # Using fractal displacement or noisy edge paths
        p_v0 = np.array([edge.v0.x * scale_x, edge.v0.y * scale_y, z_v0], dtype=np.float64)
        p_v1 = np.array([edge.v1.x * scale_x, edge.v1.y * scale_y, z_v1], dtype=np.float64)
        p_mid = np.array([edge.midpoint[0] * scale_x, edge.midpoint[1] * scale_y, z_mid], dtype=np.float64)

        # Generate points for half0 and half1 with subtle noise
        def interpolate_with_noise(pt_start, pt_end, n_segs, seed_val):
            pts = [pt_start]
            vec = pt_end - pt_start
            normal_2d = np.array([-vec[1], vec[0], 0.0], dtype=np.float64)
            n_norm = np.linalg.norm(normal_2d)
            if n_norm > 1e-6:
                normal_2d /= n_norm

            rng = np.random.RandomState(seed_val)
            for s in range(1, n_segs):
                t = s / n_segs
                disp = (rng.rand() - 0.5) * 0.30 * np.linalg.norm(vec[:2]) * math.sin(t * math.pi)
                disp_z = (rng.rand() - 0.5) * 0.15 * np.linalg.norm(vec[:2])
                pt = pt_start + t * vec + normal_2d * disp
                pt[2] += disp_z
                pts.append(pt)
            pts.append(pt_end)
            return pts

        pts_half0 = interpolate_with_noise(p_v0, p_mid, segments_per_half, edge.index * 13 + 7)
        pts_half1 = interpolate_with_noise(p_v1, p_mid, segments_per_half, edge.index * 17 + 11)

        for half_pts, corner_elev in [(pts_half0, edge.v0.elevation), (pts_half1, edge.v1.elevation)]:
            for i in range(len(half_pts) - 1):
                pa = p_pt3d
                pb = half_pts[i]
                pc = half_pts[i + 1]

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

                col = col_edge.copy()
                slope_val = 1.0 - norm[2]
                if slope_val > 0.14:
                    cliff_w = min(0.60, (slope_val - 0.14) / 0.22)
                    col = col * (1.0 - cliff_w) + np.array([66, 64, 71], dtype=np.float64) * cliff_w

                avg_elev = (p.elevation + corner_elev) * 0.5
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
                total_micropolys += 1

    t1 = time.time()
    print(f"Rendered {total_micropolys} micropolygons in {(t1 - t0)*1000:.2f} ms")

    # Rivers & lava
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

    return surface, total_micropolys

def main():
    seed = 777
    size = 1000
    print("Generating polygon map...")
    gen = PolygonMapGenerator(seed=seed, width=size, height=size, num_points=1000,
                              enable_corner_improvement=True, enable_roads=True, enable_lava=True)

    print("Rendering 16k poly surface...")
    surf, poly_count = render_with_target_polys(gen, 1000, 1000, target_polys=16000)

    buf = pygame.image.tostring(surf, "RGB")
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((1000, 1000, 3))

    out_path = os.path.join(ARTIFACT_DIR, "island_16k_polys.png")
    plt.figure(figsize=(10, 10), dpi=150)
    plt.imshow(arr)
    plt.title(f"Procedural Elevation: 16k Micropoly Island ({poly_count:,} Polygons)\n(https://www.redblobgames.com/x/1725-procedural-elevation/#rendering)",
              fontsize=11, fontweight='bold', pad=12)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches='tight')
    plt.close()
    print(f"Saved artifact to {out_path}")

if __name__ == '__main__':
    main()
