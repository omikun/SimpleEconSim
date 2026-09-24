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
    """Linearly interpolate between two RGB tuples."""
    f = max(0.0, min(1.0, float(factor)))
    return (
        int(c1[0] * (1.0 - f) + c2[0] * f),
        int(c1[1] * (1.0 - f) + c2[1] * f),
        int(c1[2] * (1.0 - f) + c2[2] * f),
    )

def calculate_triangle_lighting(p_pt, p_elev, r_pt, r_elev, s_pt, s_elev, light_vec=(-1.0, -1.0, 0.0)):
    """Amit Patel's exact calculateLighting function from mapgen2.as"""
    # Vector3D A = (p.x, p.y, p.elevation)
    # Scale elevation to map coordinates for realistic slopes
    # In mapgen2, SIZE=1000, elevation in [0, 1]
    # normal = (B - A) x (C - A)
    Ax, Ay, Az = p_pt[0], p_pt[1], p_elev * 200.0
    Bx, By, Bz = r_pt[0], r_pt[1], r_elev * 200.0
    Cx, Cy, Cz = s_pt[0], s_pt[1], s_elev * 200.0

    # V1 = B - A, V2 = C - A
    v1x, v1y, v1z = Bx - Ax, By - Ay, Bz - Az
    v2x, v2y, v2z = Cx - Ax, Cy - Ay, Cz - Az

    # cross product
    nx = v1y * v2z - v1z * v2y
    ny = v1z * v2x - v1x * v2z
    nz = v1x * v2y - v1y * v2x

    if nz < 0:
        nx, ny, nz = -nx, -ny, -nz

    n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
    if n_len > 1e-6:
        nx /= n_len
        ny /= n_len
        nz /= n_len

    # lightVector = (-1, -1, 0) normalized is (-0.707, -0.707, 0)
    # normal.dotProduct(lightVector)
    lx, ly, lz = light_vec
    l_len = math.sqrt(lx*lx + ly*ly + lz*lz)
    lx /= l_len; ly /= l_len; lz /= l_len

    dot = nx * lx + ny * ly + nz * lz
    # light = 0.5 + 35 * normal.dotProduct(lightVector) in AS3 where lightVector is unnormalized (-1, -1, 0)
    # with normalized dot, scale factor ~ 0.5 + 0.5 * dot
    light = 0.5 + 0.45 * dot
    return max(0.0, min(1.0, light))

def color_with_slope(p, q, edge):
    """Amit Patel's exact colorWithSlope from mapgen2.as"""
    r = edge.v0
    s = edge.v1
    if not r or not s:
        return (13, 36, 82)
    
    color = BIOME_COLORS.get(p.biome, (120, 160, 100))
    if p.water:
        return color

    if q is not None and (p.water == q.water):
        q_color = BIOME_COLORS.get(q.biome, color)
        color = interpolate_color(color, q_color, 0.35)

    color_low = interpolate_color(color, (40, 40, 40), 0.65)
    color_high = interpolate_color(color, (255, 255, 255), 0.30)

    light = calculate_triangle_lighting(
        (p.x, p.y), p.elevation,
        (r.x, r.y), r.elevation,
        (s.x, s.y), s.elevation
    )

    if light < 0.5:
        return interpolate_color(color_low, color, light * 2.0)
    else:
        return interpolate_color(color, color_high, light * 2.0 - 1.0)

def main():
    seed = 777
    size = 1000
    render_size = 900
    scale_x = render_size / size
    scale_y = render_size / size

    print("Generating map...")
    gen = PolygonMapGenerator(
        seed=seed, width=size, height=size, num_points=600,
        enable_corner_improvement=True, enable_noisy_edges=True,
        noisy_tradeoff=0.30
    )

    surf = pygame.Surface((render_size, render_size))
    surf.fill((13, 36, 82))

    # Render each center using Amit Patel's micropolys!
    for p in gen.centers:
        for r in p.neighbors:
            edge = next((e for e in p.borders if e.d0 == r or e.d1 == r), None)
            if not edge or not edge.v0 or not edge.v1:
                continue

            # Compute micropoly color with slope & neighbor blending
            col = color_with_slope(p, r, edge)

            p_pt = (int(p.x * scale_x), int(p.y * scale_y))

            # drawPath0: p -> v0 -> ... -> midpoint -> p
            path0 = gen.noisy_edges.path0.get(edge.index)
            if path0 is not None and len(path0) >= 2:
                pts0 = [p_pt] + [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in path0]
                if len(pts0) >= 3:
                    pygame.draw.polygon(surf, col, pts0)

            # drawPath1: p -> v1 -> ... -> midpoint -> p
            path1 = gen.noisy_edges.path1.get(edge.index)
            if path1 is not None and len(path1) >= 2:
                pts1 = [p_pt] + [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in path1]
                if len(pts1) >= 3:
                    pygame.draw.polygon(surf, col, pts1)

    # Rivers
    river_col = (56, 138, 220)
    for e in gen.edges:
        if e.river > 0 and e.v0 and e.v1:
            w = min(7, max(1, int(1 + math.log2(e.river + 1))))
            pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
            line_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in pts]
            if len(line_pts) >= 2:
                pygame.draw.lines(surf, river_col, False, line_pts, width=w)

    # Coastline outline
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

    out_path = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759/amit_micropolys.png"
    plt.figure(figsize=(10, 10), dpi=150)
    plt.imshow(img)
    plt.title("Amit Patel's True Micropoly Architecture (renderPolygons)", fontsize=13, fontweight='bold')
    plt.axis('off')
    plt.savefig(out_path, bbox_inches='tight')
    print(f"Saved {out_path}")

if __name__ == '__main__':
    main()
