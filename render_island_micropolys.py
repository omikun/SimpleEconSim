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


def build_island_mesh(
    gen: PolygonMapGenerator,
    width: int = 1000,
    height: int = 1000,
    mode: str = "adaptive",
    target_polys: int = 16000,
    subdivision_depth: int = 1,
    roughness: float = 5.0,
    elevation_alpha: float = 0.25,
    elev_scale: float = 320.0,
) -> Tuple[List[Tuple], int]:
    """
    Builds and subdivides the island's 3D micropoly mesh according to the chosen mode.
    Returns: (triangles_list, total_poly_count)
    """
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

    # 2. Build initial base triangles for all land edges
    base_triangles = []

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

        def add_base_tri(pa, pb, pc, c, el, riv):
            area = 0.5 * abs((pb[0] - pa[0]) * (pc[1] - pa[1]) - (pc[0] - pa[0]) * (pb[1] - pa[1]))
            base_triangles.append((pa, pb, pc, c, el, riv, area))

        if mode == "redblob":
            # Red Blob 2-way fold (ridges along v0-v1, valleys along d0-d1)
            p_d0 = np.array([d0.x * scale_x, d0.y * scale_y, d0.elevation * elev_scale], dtype=np.float64)
            p_d1 = np.array([d1.x * scale_x, d1.y * scale_y, d1.elevation * elev_scale], dtype=np.float64)
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
            # 4-quadrant base decomposition
            if not d0.water:
                p_d0 = np.array([d0.x * scale_x, d0.y * scale_y, d0.elevation * elev_scale], dtype=np.float64)
                add_base_tri(p_d0, p_v0, p_mid, col0, (d0.elevation + v0.elevation) * 0.5, edge.river > 0)
                add_base_tri(p_d0, p_mid, p_v1, col0, (d0.elevation + v1.elevation) * 0.5, edge.river > 0)

            if not d1.water:
                p_d1 = np.array([d1.x * scale_x, d1.y * scale_y, d1.elevation * elev_scale], dtype=np.float64)
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

    # Multi-light setup (from Red Blob draw-3d.js)
    L_sun = np.array([-0.55, -0.55, 0.70], dtype=np.float64)
    L_sun /= np.linalg.norm(L_sun)
    L_fill = np.array([0.45, -0.65, 0.60], dtype=np.float64)
    L_fill /= np.linalg.norm(L_fill)

    for (pa, pb, pc, col_base, avg_elev, is_riv, _) in triangles:
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

        # Multi-light illumination
        NdotL_sun = max(0.0, float(np.dot(norm, L_sun)))
        NdotL_fill = max(0.0, float(np.dot(norm, L_fill)))
        diffuse_sun = 0.44 * math.pow(NdotL_sun, 1.15)
        diffuse_fill = 0.14 * NdotL_fill
        ambient = 0.68 + 0.12 * (norm[2] - 0.7)
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

        pts2d = [(int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), (int(pc[0]), int(pc[1]))]
        if len(pts2d) >= 3:
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
        if getattr(edge, "lava", False) and edge.v0 and edge.v1:
            p0 = (int(edge.v0.x * scale_x), int(edge.v0.y * scale_y))
            p1 = (int(edge.v1.x * scale_x), int(edge.v1.y * scale_y))
            pygame.draw.line(surface, (255, 60, 0), p0, p1, 4)
            pygame.draw.line(surface, (255, 210, 50), p0, p1, 2)

    return surface


def main():
    parser = argparse.ArgumentParser(
        description="Generate and render high-resolution polygonal terrain with custom micropoly subdivision knobs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--polys", "-p", type=int, default=16000, help="Target polygon count (e.g. 2000, 8000, 16000, 32000, 64000)")
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        default="adaptive",
        choices=["adaptive", "depth", "spokes", "redblob"],
        help="Subdivision algorithm: 'adaptive' (1-to-4 area-priority), 'depth' (uniform 1-to-4), 'spokes' (radial fan), 'redblob' (2-way ridge/valley fold)",
    )
    parser.add_argument("--depth", "-d", type=int, default=1, help="Subdivision depth for 'depth' mode (each level quadruples poly count)")
    parser.add_argument("--roughness", "-r", type=float, default=5.0, help="Fractal midpoint displacement height roughness")
    parser.add_argument("--alpha", "-a", type=float, default=0.25, help="Red Blob corner ridge elevation boost alpha")
    parser.add_argument("--seed", "-s", type=int, default=777, help="Random seed for map generator")
    parser.add_argument("--points", "-n", type=int, default=1000, help="Number of Voronoi seed points")
    parser.add_argument("--size", type=int, default=1000, help="Render resolution in pixels (width=height)")
    parser.add_argument("--output", "-o", type=str, default="island_output.png", help="Output PNG file path")
    parser.add_argument("--window", action="store_true", help="Display interactive live window (requires graphical desktop)")

    args = parser.parse_args()

    print(f"\n========================================================")
    print(f"  Polygonal Terrain Micropoly Generator")
    print(f"========================================================")
    print(f"  • Target Polygons : {args.polys:,}")
    print(f"  • Subdivision Mode: {args.mode}")
    print(f"  • World Seed      : {args.seed}")
    print(f"  • Voronoi Points  : {args.points}")
    print(f"  • Roughness       : {args.roughness}")
    print(f"  • Ridge Alpha (α) : {args.alpha}")
    print(f"  • Resolution      : {args.size} x {args.size}")
    print(f"--------------------------------------------------------")

    t_start = time.time()
    print("Generating base Voronoi dual-mesh & hydrology...")
    gen = PolygonMapGenerator(
        seed=args.seed,
        width=args.size,
        height=args.size,
        num_points=args.points,
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
        elevation_alpha=args.alpha,
    )
    t_subdiv = time.time()

    print(f"Rasterizing {actual_poly_count:,} micropolygons with multi-light shading...")
    surface = render_mesh(gen, triangles, width=args.size, height=args.size)
    t_render = time.time()

    # Save output image
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pygame.image.save(surface, output_path)

    print(f"\n[DONE] Successfully generated {actual_poly_count:,} micropolygons!")
    print(f"  - Map Generation : {(t_gen - t_start)*1000:.1f} ms")
    print(f"  - Subdivision    : {(t_subdiv - t_gen)*1000:.1f} ms")
    print(f"  - Shading/Render : {(t_render - t_subdiv)*1000:.1f} ms")
    print(f"  - Total Elapsed  : {(t_render - t_start)*1000:.1f} ms")
    print(f"  - Saved Image to : {output_path}")

    # Also copy to artifact directory if inside antigravity environment
    artifact_dir = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759"
    if os.path.isdir(artifact_dir):
        art_path = os.path.join(artifact_dir, "custom_island_render.png")
        pygame.image.save(surface, art_path)
        print(f"  - Artifact Saved : {art_path}")

    print(f"========================================================\n")


if __name__ == "__main__":
    main()
