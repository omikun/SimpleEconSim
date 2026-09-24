import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import LinearNDInterpolator
from scipy.ndimage import gaussian_filter
import pygame

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

sys.path.insert(0, '/Users/sli/Code')
from polygon_map import PolygonMapGenerator, BIOME_COLORS

def chaikin_smooth(pts, iterations=1):
    """Apply Chaikin corner-cutting smoothing to remove sharp needle spikes."""
    if len(pts) < 3:
        return pts
    result = pts
    for _ in range(iterations):
        smoothed = []
        n = len(result)
        for i in range(n):
            p0 = result[i]
            p1 = result[(i + 1) % n]
            smoothed.append(0.75 * p0 + 0.25 * p1)
            smoothed.append(0.25 * p0 + 0.75 * p1)
        result = np.array(smoothed)
    return result

def main():
    seed = 777
    size = 1000
    render_size = 900

    print("Generating map...")
    gen = PolygonMapGenerator(
        seed=seed,
        width=size,
        height=size,
        num_points=600,
        enable_corner_improvement=True,
        enable_noisy_edges=True,
        enable_roads=True,
        enable_lava=True,
        enable_watersheds=True,
        noisy_tradeoff=0.30,  # gentler edge deviation
    )

    # 1. Current rendering (overblown + jagged)
    print("Rendering current...")
    surf_curr = gen.render_to_surface(
        width=render_size, height=render_size,
        use_brdf=True, use_noisy_edges=True, show_roads=True, show_lava=True,
        continuous_relief=True
    )
    buf = pygame.image.tostring(surf_curr, 'RGB')
    img_curr = np.frombuffer(buf, dtype=np.uint8).reshape((render_size, render_size, 3))

    # 2. Perfected lighting & smooth organic boundaries
    print("Rendering perfected...")
    scale_x = render_size / gen.width
    scale_y = render_size / gen.height

    surf = pygame.Surface((render_size, render_size))
    surf.fill((13, 36, 82))

    # Draw ocean and land polygons with unlit base color
    for c in gen.centers:
        if len(c.corners) < 3: continue
        poly_np = gen.get_polygon_noisy_boundary(c)
        # Apply smoothing to polygon points
        poly_smooth = chaikin_smooth(poly_np, iterations=1)
        poly_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in poly_smooth]

        if c.water:
            shaded_color = c.brdf_color
        else:
            base_c = np.array(BIOME_COLORS.get(c.biome, (120, 160, 100)), dtype=np.float32)
            # Riparian margin along rivers
            if any(e.river > 0 for e in c.borders):
                base_c = base_c * 0.75 + np.array([43, 102, 38], dtype=np.float32) * 0.25
            # Cliff scree darkening on steep terrain
            if 1.0 - c.normal[2] > 0.12:
                cliff_w = min(0.60, (1.0 - c.normal[2] - 0.12) / 0.20)
                base_c = base_c * (1.0 - cliff_w) + np.array([66, 64, 71], dtype=np.float32) * cliff_w
            shaded_color = (int(base_c[0]), int(base_c[1]), int(base_c[2]))

        if len(poly_pts) >= 3:
            pygame.draw.polygon(surf, shaded_color, poly_pts)

    # Shaded relief with soft-knee highlight clamp (NEVER blows out!)
    buf2 = pygame.image.tostring(surf, 'RGB')
    img = np.frombuffer(buf2, dtype=np.uint8).reshape((render_size, render_size, 3)).astype(np.float32)

    pts = [[c.x, c.y] for c in gen.centers] + [[cn.x, cn.y] for cn in gen.corners]
    elevs = [c.elevation for c in gen.centers] + [cn.elevation for cn in gen.corners]
    interp = LinearNDInterpolator(np.array(pts, dtype=np.float32), np.array(elevs, dtype=np.float32))
    gy, gx = np.mgrid[0:size:render_size*1j, 0:size:render_size*1j]
    H = np.nan_to_num(interp(gx, gy), nan=0.0)
    H_smooth = gaussian_filter(H, sigma=4.5)

    dHy, dHx = np.gradient(H_smooth)
    kh = 55.0
    nx = -dHx * kh; ny = -dHy * kh; nz = np.ones_like(nx)
    norm = np.sqrt(nx*nx + ny*ny + nz*nz)
    nx /= norm; ny /= norm; nz /= norm

    L = np.array([-0.55, -0.55, 0.70], dtype=np.float64)
    L /= np.linalg.norm(L)
    NdotL = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0.0, 1.0)

    # Filmic / soft-knee lighting formula:
    # diffuse term is moderate (max +0.22), ambient is 0.78, shadow dips to 0.60
    sun_diffuse = 0.24 * np.power(NdotL, 1.2)
    ambient = 0.74 + 0.12 * (nz - 0.7)
    hillshade = ambient + sun_diffuse

    # Add gentle micro-relief noise (max +- 0.02)
    rng = np.random.RandomState(42)
    micro_noise = (rng.rand(render_size, render_size) - 0.5) * 0.025
    hillshade = np.clip(hillshade + micro_noise, 0.58, 1.18)

    is_land = H > 0.16
    for ch in range(3):
        # Soft-knee highlight roll-off: val * hillshade
        val = img[:, :, ch] * hillshade
        # Tone curve: compress highlights above 225
        val = np.where(val > 225.0, 225.0 + (val - 225.0) * 0.40, val)
        img[:, :, ch] = np.where(is_land, np.clip(val, 0, 248), img[:, :, ch])

    surf = pygame.image.fromstring(img.astype(np.uint8).tobytes(), (render_size, render_size), 'RGB')

    # Draw rivers, lava, roads
    river_base = (56, 138, 220)
    for e in gen.edges:
        if e.river > 0 and e.v0 and e.v1:
            w_line = min(7, max(1, int(1 + np.log2(e.river + 1))))
            pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
            pts_sm = chaikin_smooth(pts, iterations=1)
            line_pts = [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in pts_sm]
            if len(line_pts) >= 2:
                pygame.draw.lines(surf, river_base, False, line_pts, width=w_line)

    lava_outer = (180, 32, 16)
    lava_core = (255, 190, 32)
    for e in gen.edges:
        if getattr(e, 'lava', False) and e.v0 and e.v1:
            pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
            pts_sm = chaikin_smooth(pts, iterations=1)
            line_pts = [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in pts_sm]
            if len(line_pts) >= 2:
                pygame.draw.lines(surf, lava_outer, False, line_pts, width=4)
                pygame.draw.lines(surf, lava_core, False, line_pts, width=2)

    road_color = (195, 170, 125)
    for e in gen.edges:
        if getattr(e, 'road', 0) > 0 and e.v0 and e.v1:
            if (e.d0 and e.d0.ocean) and (e.d1 and e.d1.ocean): continue
            pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
            pts_sm = chaikin_smooth(pts, iterations=1)
            line_pts = [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in pts_sm]
            if len(line_pts) >= 2:
                pygame.draw.lines(surf, road_color, False, line_pts, width=2)

    coast_color = (18, 55, 95)
    for e in gen.edges:
        if e.v0 and e.v1 and e.d0 and e.d1:
            if (e.d0.ocean != e.d1.ocean) or (e.d0.water != e.d1.water):
                pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
                pts_sm = chaikin_smooth(pts, iterations=1)
                line_pts = [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in pts_sm]
                if len(line_pts) >= 2:
                    pygame.draw.lines(surf, coast_color, False, line_pts, width=2)

    buf_new = pygame.image.tostring(surf, 'RGB')
    img_new = np.frombuffer(buf_new, dtype=np.uint8).reshape((render_size, render_size, 3))

    # Side-by-side
    fig, axes = plt.subplots(1, 2, figsize=(18, 9), dpi=150)
    axes[0].imshow(img_curr)
    axes[0].set_title("BEFORE: Overblown Northwest Face & Jagged Buzzsaw Micropoly", fontsize=12, fontweight='bold')
    axes[0].axis('off')

    axes[1].imshow(img_new)
    axes[1].set_title("AFTER: Controlled Soft-Knee Exposure + Organic Curvature Smoothing", fontsize=12, fontweight='bold')
    axes[1].axis('off')

    plt.tight_layout()
    out_path = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759/fix_overblown_comparison.png"
    plt.savefig(out_path, bbox_inches='tight')
    print(f"Saved {out_path}")

if __name__ == '__main__':
    main()
