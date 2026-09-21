import os
import sys
import math
import pygame
import numpy as np
import matplotlib.pyplot as plt

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

sys.path.insert(0, '/Users/sli/Code')
from polygon_map import PolygonMapGenerator, BIOME_COLORS

def interpolate_color(c1, c2, factor):
    f = max(0.0, min(1.0, float(factor)))
    return (
        int(c1[0] * (1.0 - f) + c2[0] * f),
        int(c1[1] * (1.0 - f) + c2[1] * f),
        int(c1[2] * (1.0 - f) + c2[2] * f),
    )

def main():
    seed = 777
    size = 1000
    render_size = 900
    scale_x = render_size / size
    scale_y = render_size / size

    gen = PolygonMapGenerator(
        seed=seed, width=size, height=size, num_points=600,
        enable_corner_improvement=True, enable_noisy_edges=True,
        enable_roads=True, enable_lava=True, enable_watersheds=True,
        noisy_tradeoff=0.30
    )

    surf = pygame.Surface((render_size, render_size))
    # Fill deep ocean
    surf.fill((13, 36, 82))

    L = np.array([-0.55, -0.55, 0.70], dtype=np.float64)
    L /= np.linalg.norm(L)

    # 1. First draw ocean polygons (using bathymetric colors and wave specular)
    for c in gen.centers:
        if c.water and len(c.corners) >= 3:
            poly_np = gen.get_polygon_noisy_boundary(c)
            poly_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in poly_np]
            if len(poly_pts) >= 3:
                pygame.draw.polygon(surf, c.brdf_color, poly_pts)

    # 2. Draw land polygons using Amit Patel's constituent micropolys!
    for p in gen.centers:
        if p.water:
            continue

        p_pt = (int(p.x * scale_x), int(p.y * scale_y))
        base_color = np.array(BIOME_COLORS.get(p.biome, (120, 160, 100)), dtype=np.float64)

        for r in p.neighbors:
            edge = next((e for e in p.borders if e.d0 == r or e.d1 == r), None)
            if not edge or not edge.v0 or not edge.v1:
                continue

            # Compute micropoly normal for triangle (p, v0, v1)
            Ax, Ay, Az = p.x, p.y, p.elevation * 300.0
            Bx, By, Bz = edge.v0.x, edge.v0.y, edge.v0.elevation * 300.0
            Cx, Cy, Cz = edge.v1.x, edge.v1.y, edge.v1.elevation * 300.0

            # Normal = (B - A) x (C - A)
            v1 = np.array([Bx - Ax, By - Ay, Bz - Az])
            v2 = np.array([Cx - Ax, Cy - Ay, Cz - Az])
            norm = np.cross(v1, v2)
            if norm[2] < 0:
                norm = -norm
            norm_len = np.linalg.norm(norm)
            if norm_len > 1e-6:
                norm /= norm_len
            else:
                norm = np.array([0.0, 0.0, 1.0])

            # Micropoly color: blend towards neighbor biome if both land
            col = base_color.copy()
            if not r.water:
                r_col = np.array(BIOME_COLORS.get(r.biome, col), dtype=np.float64)
                col = col * 0.65 + r_col * 0.35

            # Steep cliff rock scree
            slope_val = 1.0 - norm[2]
            if slope_val > 0.15:
                cliff_w = min(0.55, (slope_val - 0.15) / 0.25)
                col = col * (1.0 - cliff_w) + np.array([66, 64, 71], dtype=np.float64) * cliff_w

            # Riparian greening along river edges
            if edge.river > 0:
                col = col * 0.70 + np.array([43, 102, 38], dtype=np.float64) * 0.30

            # Illumination: Diffuse + Ambient
            NdotL = max(0.0, float(np.dot(norm, L)))
            diffuse = 0.38 * math.pow(NdotL, 1.15)
            ambient = 0.70 + 0.15 * (norm[2] - 0.7)
            total_shade = ambient + diffuse

            # Soft-knee highlight compression to prevent blowout
            shaded_rgb = col * total_shade
            for i in range(3):
                if shaded_rgb[i] > 220.0:
                    shaded_rgb[i] = 220.0 + (shaded_rgb[i] - 220.0) * 0.35
            final_col = (
                min(246, max(0, int(shaded_rgb[0]))),
                min(246, max(0, int(shaded_rgb[1]))),
                min(246, max(0, int(shaded_rgb[2]))),
            )

            # Draw micropoly 0: (p -> v0 -> ... -> midpoint -> p)
            path0 = gen.noisy_edges.path0.get(edge.index)
            if path0 is not None and len(path0) >= 2:
                pts0 = [p_pt] + [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in path0]
                if len(pts0) >= 3:
                    pygame.draw.polygon(surf, final_col, pts0)

            # Draw micropoly 1: (p -> v1 -> ... -> midpoint -> p)
            path1 = gen.noisy_edges.path1.get(edge.index)
            if path1 is not None and len(path1) >= 2:
                pts1 = [p_pt] + [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in path1]
                if len(pts1) >= 3:
                    pygame.draw.polygon(surf, final_col, pts1)

    # 3. Draw rivers along noisy paths
    river_col = (56, 138, 220)
    for e in gen.edges:
        if e.river > 0 and e.v0 and e.v1:
            w = min(7, max(1, int(1 + math.log2(e.river + 1))))
            pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
            line_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in pts]
            if len(line_pts) >= 2:
                pygame.draw.lines(surf, river_col, False, line_pts, width=w)

    # 4. Draw lava fissures
    lava_outer = (180, 32, 16)
    lava_core = (255, 190, 32)
    for e in gen.edges:
        if getattr(e, 'lava', False) and e.v0 and e.v1:
            pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
            line_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in pts]
            if len(line_pts) >= 2:
                pygame.draw.lines(surf, lava_outer, False, line_pts, width=4)
                pygame.draw.lines(surf, lava_core, False, line_pts, width=2)

    # 5. Draw contour roads
    road_col = (195, 170, 125)
    for e in gen.edges:
        if getattr(e, 'road', 0) > 0 and e.v0 and e.v1:
            if (e.d0 and e.d0.ocean) and (e.d1 and e.d1.ocean): continue
            pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
            line_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in pts]
            if len(line_pts) >= 2:
                pygame.draw.lines(surf, road_col, False, line_pts, width=2)

    # 6. Draw coastline outline
    coast_col = (18, 55, 95)
    for e in gen.edges:
        if e.v0 and e.v1 and e.d0 and e.d1:
            if (e.d0.ocean != e.d1.ocean) or (e.d0.water != e.d1.water):
                pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
                line_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in pts]
                if len(line_pts) >= 2:
                    pygame.draw.lines(surf, coast_col, False, line_pts, width=2)

    buf = pygame.image.tostring(surf, 'RGB')
    img = np.frombuffer(buf, dtype=np.uint8).reshape((render_size, render_size, 3))

    out_path = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759/micropoly_brdf_showcase.png"
    plt.figure(figsize=(11, 11), dpi=150)
    plt.imshow(img)
    plt.title("Sculpted Micropoly 3D Terrain (Internal Triangles + Directional Lighting)", fontsize=13, fontweight='bold')
    plt.axis('off')
    plt.savefig(out_path, bbox_inches='tight')
    print(f"Saved {out_path}")

if __name__ == '__main__':
    main()
