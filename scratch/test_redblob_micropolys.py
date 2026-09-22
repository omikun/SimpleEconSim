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

def render_redblob_elevation_mesh(gen: PolygonMapGenerator, width: int = 1000, height: int = 1000,
                                   elevation_alpha: float = 0.25,
                                   subdivide_midpoint: bool = True,
                                   mode: str = "whittaker") -> pygame.Surface:
    """
    Renders the terrain by breaking the ENTIRE island into a mesh of micropolygons
    as described in https://www.redblobgames.com/x/1725-procedural-elevation/#rendering
    """
    surface = pygame.Surface((width, height))
    surface.fill((28, 48, 85))  # Deep ocean background

    scale_x = width / gen.width
    scale_y = height / gen.height
    elev_scale = 280.0

    # 1. Calculate corner elevations with alpha elevation boost above centers (peaks & ridges)
    # v_elevation[v] = max + alpha * (max - min)
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

    # Lights setup from draw-3d.js
    L_sun = np.array([-0.55, -0.55, 0.70], dtype=np.float64)
    L_sun /= np.linalg.norm(L_sun)

    L_fill = np.array([0.45, -0.65, 0.60], dtype=np.float64)
    L_fill /= np.linalg.norm(L_fill)

    # 2. Render Ocean first
    for c in gen.centers:
        if not c.water or len(c.corners) < 3:
            continue
        poly_pts = [(int(cn.x * scale_x), int(cn.y * scale_y)) for cn in c.corners]
        if len(poly_pts) >= 3:
            pygame.draw.polygon(surface, (28, 48, 85), poly_pts)

    # 3. Generate Triangles across the ENTIRE island for EVERY edge
    triangles = [] # list of (pt_a, pt_b, pt_c, base_color, is_water, elev_avg)

    for edge in gen.edges:
        d0, d1 = edge.d0, edge.d1
        v0, v1 = edge.v0, edge.v1

        if not d0 or not d1 or not v0 or not v1:
            continue
        
        # If both are water, skip land micropoly
        if d0.water and d1.water:
            continue

        p_d0 = (d0.x * scale_x, d0.y * scale_y, d0.elevation * elev_scale)
        p_d1 = (d1.x * scale_x, d1.y * scale_y, d1.elevation * elev_scale)
        p_v0 = (v0.x * scale_x, v0.y * scale_y, v_elev.get(v0.index, v0.elevation) * elev_scale)
        p_v1 = (v1.x * scale_x, v1.y * scale_y, v_elev.get(v1.index, v1.elevation) * elev_scale)

        # Base colors for d0 and d1
        if mode == "whittaker":
            col0 = np.array(BIOME_COLORS.get(d0.biome, (120, 160, 100)), dtype=np.float64)
            col1 = np.array(BIOME_COLORS.get(d1.biome, (120, 160, 100)), dtype=np.float64)
        else: # Red Blob green-brown-blue style
            def rbg_col(elev, moist):
                r = int(255 * (0.2 + 0.65 * elev))
                g = int(255 * (0.85 - 0.55 * elev + 0.15 * moist))
                b = int(255 * (0.45 + 0.25 * moist - 0.25 * elev))
                return np.array([r, g, b], dtype=np.float64)
            col0 = rbg_col(d0.elevation, d0.moisture)
            col1 = rbg_col(d1.elevation, d1.moisture)

        is_river = edge.river > 0
        
        if subdivide_midpoint:
            # Subdivide quad into 4 micropolygons meeting at edge midpoint m
            # Midpoint in 3D
            m_elev = (p_v0[2] + p_v1[2]) * 0.5
            p_m = ((p_v0[0] + p_v1[0]) * 0.5, (p_v0[1] + p_v1[1]) * 0.5, m_elev)
            
            # Quad triangles:
            # 1: (d0, v0, m)
            # 2: (d0, m, v1)
            # 3: (d1, v1, m)
            # 4: (d1, m, v0)
            if not d0.water:
                triangles.append((p_d0, p_v0, p_m, col0, (d0.elevation + v0.elevation)*0.5, is_river))
                triangles.append((p_d0, p_m, p_v1, col0, (d0.elevation + v1.elevation)*0.5, is_river))
            if not d1.water:
                triangles.append((p_d1, p_v1, p_m, col1, (d1.elevation + v1.elevation)*0.5, is_river))
                triangles.append((p_d1, p_m, p_v0, col1, (d1.elevation + v0.elevation)*0.5, is_river))
        else:
            # Red Blob article fold:
            # River: fold up on white edge (d0, d1)
            # Ridge: fold down on black edge (v0, v1)
            if is_river:
                # River valley fold
                if not d0.water or not d1.water:
                    c_mix = (col0 + col1) * 0.5
                    triangles.append((p_v0, p_d1, p_d0, c_mix, (v0.elevation + d0.elevation)*0.5, True))
                    triangles.append((p_v1, p_d0, p_d1, c_mix, (v1.elevation + d1.elevation)*0.5, True))
            else:
                # Mountain ridge fold
                if not d0.water:
                    triangles.append((p_v0, p_v1, p_d0, col0, (v0.elevation + v1.elevation + d0.elevation)/3.0, False))
                if not d1.water:
                    triangles.append((p_v1, p_v0, p_d1, col1, (v0.elevation + v1.elevation + d1.elevation)/3.0, False))

    print(f"Generated {len(triangles)} micropolygons covering the entire island.")

    # 4. Rasterize all micropolygons
    for (pa, pb, pc, base_col, avg_elev, is_riv) in triangles:
        # Calculate 3D face normal
        va = np.array([pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]], dtype=np.float64)
        vb = np.array([pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]], dtype=np.float64)
        norm = np.cross(va, vb)
        if norm[2] < 0:
            norm = -norm
        n_len = np.linalg.norm(norm)
        if n_len > 1e-6:
            norm /= n_len
        else:
            norm = np.array([0.0, 0.0, 1.0], dtype=np.float64)

        # Multi-light illumination
        NdotL_sun = max(0.0, float(np.dot(norm, L_sun)))
        NdotL_fill = max(0.0, float(np.dot(norm, L_fill)))
        
        diffuse_sun = 0.48 * math.pow(NdotL_sun, 1.2)
        diffuse_fill = 0.16 * NdotL_fill
        ambient = 0.65 + 0.12 * (norm[2] - 0.7)
        total_light = ambient + diffuse_sun + diffuse_fill

        col = base_col.copy()

        # Cliff rock scree on steep slope
        slope_val = 1.0 - norm[2]
        if slope_val > 0.14:
            cliff_w = min(0.60, (slope_val - 0.14) / 0.22)
            col = col * (1.0 - cliff_w) + np.array([66, 64, 71], dtype=np.float64) * cliff_w

        # Snow on high peaks (mix with white based on z^2, like Amit's shader)
        z_norm = max(0.0, min(1.0, avg_elev))
        if z_norm > 0.65:
            snow_w = min(0.95, math.pow((z_norm - 0.65) / 0.28, 2.0))
            col = col * (1.0 - snow_w) + np.array([242, 244, 250], dtype=np.float64) * snow_w

        # Riparian vegetation greening along rivers
        if is_riv:
            col = col * 0.75 + np.array([40, 100, 35], dtype=np.float64) * 0.25

        shaded_rgb = col * total_light
        # Soft-knee compression
        for i in range(3):
            if shaded_rgb[i] > 220.0:
                shaded_rgb[i] = 220.0 + (shaded_rgb[i] - 220.0) * 0.35

        final_rgb = (
            min(248, max(0, int(shaded_rgb[0]))),
            min(248, max(0, int(shaded_rgb[1]))),
            min(248, max(0, int(shaded_rgb[2]))),
        )

        pts2d = [(int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), (int(pc[0]), int(pc[1]))]
        pygame.draw.polygon(surface, final_rgb, pts2d)

    # Rivers on top
    for edge in gen.edges:
        if edge.river > 0 and edge.v0 and edge.v1:
            r_w = max(1, min(6, int(math.sqrt(edge.river) * 1.5)))
            p0 = (int(edge.v0.x * scale_x), int(edge.v0.y * scale_y))
            p1 = (int(edge.v1.x * scale_x), int(edge.v1.y * scale_y))
            pygame.draw.line(surface, (45, 95, 145), p0, p1, r_w)

    # Volcanic Lava fissures on top
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
    gen = PolygonMapGenerator(seed=seed, width=size, height=size, num_points=600,
                              enable_corner_improvement=True, enable_roads=True, enable_lava=True)

    print("Rendering with 4-way midpoint micropolygons (Whittaker)...")
    surf_whittaker = render_redblob_elevation_mesh(gen, 1000, 1000, elevation_alpha=0.30, subdivide_midpoint=True, mode="whittaker")

    print("Rendering with Red Blob Green-Brown style...")
    surf_redblob = render_redblob_elevation_mesh(gen, 1000, 1000, elevation_alpha=0.30, subdivide_midpoint=True, mode="redblob")

    print("Rendering 2-way ridge/valley fold (Whittaker)...")
    surf_fold = render_redblob_elevation_mesh(gen, 1000, 1000, elevation_alpha=0.30, subdivide_midpoint=False, mode="whittaker")

    # Save images
    def surf_to_arr(s):
        w, h = s.get_size()
        buf = pygame.image.tostring(s, "RGB")
        return np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 3))

    fig, axes = plt.subplots(1, 3, figsize=(24, 8), dpi=150)
    axes[0].imshow(surf_fold_arr := surf_to_arr(surf_fold))
    axes[0].set_title("1. Red Blob 2-Way Fold (Ridge/Valley Micropolys)", fontsize=13, fontweight='bold')
    axes[0].axis('off')

    axes[1].imshow(surf_whit_arr := surf_to_arr(surf_whittaker))
    axes[1].set_title("2. Full Island 4-Way Micropolys (Whittaker Biomes)", fontsize=13, fontweight='bold')
    axes[1].axis('off')

    axes[2].imshow(surf_rb_arr := surf_to_arr(surf_redblob))
    axes[2].set_title("3. Full Island 4-Way Micropolys (Red Blob Style)", fontsize=13, fontweight='bold')
    axes[2].axis('off')

    out_path = os.path.join(ARTIFACT_DIR, "redblob_micropolys_comparison.png")
    plt.suptitle("Procedural Elevation Micropoly Rendering (Red Blob Games Reference)", fontsize=16, fontweight='heavy')
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches='tight')
    plt.close()
    print(f"Saved comparison to {out_path}")

if __name__ == '__main__':
    main()
