import os
import sys
import math
import numpy as np
import pygame
import matplotlib.pyplot as plt

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polygon_map import PolygonMapGenerator, BIOME_COLORS

ARTIFACT_DIR = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759"

def render_full_island_micropolys(gen: PolygonMapGenerator, width: int = 1000, height: int = 1000,
                                  elevation_alpha: float = 0.25,
                                  elev_scale: float = 320.0,
                                  snow_threshold: float = 0.82) -> pygame.Surface:
    """
    Tessellates 100% of the island into micropolygons radiating from cell centers to
    subdivided noisy edge segments, with corner elevation enhancement and multi-light shading.
    Reference: https://www.redblobgames.com/x/1725-procedural-elevation/#rendering
    """
    surface = pygame.Surface((width, height))
    surface.fill((28, 48, 85))  # Deep ocean background

    scale_x = width / gen.width
    scale_y = height / gen.height

    # 1. Red Blob corner elevation rule:
    # v_elevation[v] = max + alpha * (max - min) of adjacent centers
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

    # 2. Lighting setup (draw-3d.js multi-light model)
    L_sun = np.array([-0.55, -0.55, 0.70], dtype=np.float64)
    L_sun /= np.linalg.norm(L_sun)

    L_fill = np.array([0.45, -0.65, 0.60], dtype=np.float64)
    L_fill /= np.linalg.norm(L_fill)

    # 3. Draw water cells first
    for c in gen.centers:
        if not c.water or len(c.corners) < 3:
            continue
        poly_pts = [(int(cn.x * scale_x), int(cn.y * scale_y)) for cn in c.corners]
        if len(poly_pts) >= 3:
            pygame.draw.polygon(surface, (28, 48, 85), poly_pts)

    # 4. Generate micropolygons for 100% of the island
    total_micropolys = 0

    for p in gen.centers:
        if p.water or len(p.corners) < 3:
            continue

        p_pt3d = np.array([p.x * scale_x, p.y * scale_y, p.elevation * elev_scale], dtype=np.float64)
        base_color = np.array(BIOME_COLORS.get(p.biome, (120, 160, 100)), dtype=np.float64)

        for r in p.neighbors:
            edge = next((e for e in p.borders if e.d0 == r or e.d1 == r), None)
            if not edge or not edge.v0 or not edge.v1:
                continue

            # Neighbor color blend
            col_edge = base_color.copy()
            if not r.water:
                r_col = np.array(BIOME_COLORS.get(r.biome, col_edge), dtype=np.float64)
                col_edge = col_edge * 0.70 + r_col * 0.30

            # Riparian greening along river edges
            if edge.river > 0:
                col_edge = col_edge * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25

            # Get noisy edge paths or fallback straight segments
            z_v0 = v_elev.get(edge.v0.index, edge.v0.elevation) * elev_scale
            z_v1 = v_elev.get(edge.v1.index, edge.v1.elevation) * elev_scale
            z_mid = (z_v0 + z_v1) * 0.5

            path0 = gen.noisy_edges.path0.get(edge.index) if gen.noisy_edges else None
            path1 = gen.noisy_edges.path1.get(edge.index) if gen.noisy_edges else None

            # Process path0 (v0 to midpoint)
            if path0 is not None and len(path0) >= 2:
                n_pts = len(path0)
                pts3d = []
                for i, pt in enumerate(path0):
                    t = i / max(1, n_pts - 1)
                    z_pt = (1.0 - t) * z_v0 + t * z_mid
                    pts3d.append(np.array([pt[0] * scale_x, pt[1] * scale_y, z_pt], dtype=np.float64))
            else:
                pts3d = [
                    np.array([edge.v0.x * scale_x, edge.v0.y * scale_y, z_v0], dtype=np.float64),
                    np.array([edge.midpoint[0] * scale_x, edge.midpoint[1] * scale_y, z_mid], dtype=np.float64)
                ]

            for i in range(len(pts3d) - 1):
                p_a = p_pt3d
                p_b = pts3d[i]
                p_c = pts3d[i + 1]

                # Normal of micro-triangle
                va = p_b - p_a
                vb = p_c - p_a
                norm = np.cross(va, vb)
                if norm[2] < 0:
                    norm = -norm
                n_len = np.linalg.norm(norm)
                if n_len > 1e-6:
                    norm /= n_len
                else:
                    norm = np.array([0.0, 0.0, 1.0], dtype=np.float64)

                # Shading
                NdotL_sun = max(0.0, float(np.dot(norm, L_sun)))
                NdotL_fill = max(0.0, float(np.dot(norm, L_fill)))
                diffuse_sun = 0.44 * math.pow(NdotL_sun, 1.15)
                diffuse_fill = 0.14 * NdotL_fill
                ambient = 0.68 + 0.12 * (norm[2] - 0.7)
                shade = ambient + diffuse_sun + diffuse_fill

                col = col_edge.copy()

                # Cliff scree on steep slopes
                slope_val = 1.0 - norm[2]
                if slope_val > 0.14:
                    cliff_w = min(0.60, (slope_val - 0.14) / 0.22)
                    col = col * (1.0 - cliff_w) + np.array([66, 64, 71], dtype=np.float64) * cliff_w

                # Snow on high peaks (mix with white based on z^2, like Amit's shader)
                avg_elev = (p.elevation + ((1.0 - (i/len(pts3d))) * edge.v0.elevation + (i/len(pts3d)) * 0.5 * (edge.v0.elevation + edge.v1.elevation))) * 0.5
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
                pts2d = [(int(p_a[0]), int(p_a[1])), (int(p_b[0]), int(p_b[1])), (int(p_c[0]), int(p_c[1]))]
                pygame.draw.polygon(surface, final_rgb, pts2d)
                total_micropolys += 1

            # Process path1 (v1 to midpoint)
            if path1 is not None and len(path1) >= 2:
                n_pts = len(path1)
                pts3d = []
                for i, pt in enumerate(path1):
                    t = i / max(1, n_pts - 1)
                    z_pt = (1.0 - t) * z_v1 + t * z_mid
                    pts3d.append(np.array([pt[0] * scale_x, pt[1] * scale_y, z_pt], dtype=np.float64))
            else:
                pts3d = [
                    np.array([edge.v1.x * scale_x, edge.v1.y * scale_y, z_v1], dtype=np.float64),
                    np.array([edge.midpoint[0] * scale_x, edge.midpoint[1] * scale_y, z_mid], dtype=np.float64)
                ]

            for i in range(len(pts3d) - 1):
                p_a = p_pt3d
                p_b = pts3d[i]
                p_c = pts3d[i + 1]

                va = p_b - p_a
                vb = p_c - p_a
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

                avg_elev = (p.elevation + ((1.0 - (i/len(pts3d))) * edge.v1.elevation + (i/len(pts3d)) * 0.5 * (edge.v0.elevation + edge.v1.elevation))) * 0.5
                if avg_elev > snow_threshold:
                    snow_w = min(0.95, math.pow((avg_elev - snow_threshold) / (1.0 - snow_threshold), 2.0))
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
                pts2d = [(int(p_a[0]), int(p_a[1])), (int(p_b[0]), int(p_b[1])), (int(p_c[0]), int(p_c[1]))]
                pygame.draw.polygon(surface, final_rgb, pts2d)
                total_micropolys += 1

    print(f"Rendered {total_micropolys} micropolygons across the entire island!")

    # 5. Rivers on top
    for edge in gen.edges:
        if edge.river > 0 and edge.v0 and edge.v1:
            r_w = max(1, min(6, int(math.sqrt(edge.river) * 1.5)))
            p0 = (int(edge.v0.x * scale_x), int(edge.v0.y * scale_y))
            p1 = (int(edge.v1.x * scale_x), int(edge.v1.y * scale_y))
            pygame.draw.line(surface, (45, 95, 145), p0, p1, r_w)

    # 6. Lava fissures on top
    for edge in gen.edges:
        if getattr(edge, 'lava', False) and edge.v0 and edge.v1:
            p0 = (int(edge.v0.x * scale_x), int(edge.v0.y * scale_y))
            p1 = (int(edge.v1.x * scale_x), int(edge.v1.y * scale_y))
            pygame.draw.line(surface, (255, 60, 0), p0, p1, 4)
            pygame.draw.line(surface, (255, 210, 50), p0, p1, 2)

    return surface

def main():
    seed = 777
    size = 1000
    print("Generating polygon map...")
    # Using 1000 points for extra density
    gen = PolygonMapGenerator(seed=seed, width=size, height=size, num_points=1000,
                              enable_corner_improvement=True, enable_roads=True, enable_lava=True,
                              noisy_tradeoff=0.35)

    print("Rendering entire island as micropolygons...")
    surf = render_full_island_micropolys(gen, 1000, 1000, elevation_alpha=0.25, elev_scale=320.0, snow_threshold=0.80)

    buf = pygame.image.tostring(surf, "RGB")
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((1000, 1000, 3))

    out_path = os.path.join(ARTIFACT_DIR, "entire_island_micropolys.png")
    plt.figure(figsize=(10, 10), dpi=150)
    plt.imshow(arr)
    plt.title("Procedural Elevation: Entire Island Tessellated into Micropolygons\n(https://www.redblobgames.com/x/1725-procedural-elevation/#rendering)",
              fontsize=11, fontweight='bold', pad=12)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches='tight')
    plt.close()
    print(f"Saved artifact to {out_path}")

if __name__ == '__main__':
    main()
