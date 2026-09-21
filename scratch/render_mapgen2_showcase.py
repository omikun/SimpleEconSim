"""
render_mapgen2_showcase.py — Generates a 4-panel visual showcase comparing:
1. Classic Voronoi (straight edges, flat coloring)
2. Mapgen2 (Noisy edges, variable-width rivers, contour roads, volcanic lava fissures)
3. Watershed Drainage Basins (catchment zones, coastal outflows)
4. Mapgen2 with Full BRDF Shading (3D surface normals, soft shadows, specular glints, glowing lava)
"""

import os
import sys

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pygame
import matplotlib.pyplot as plt
import numpy as np

from polygon_map import PolygonMapGenerator

ARTIFACT_DIR = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759"
OUTPUT_PATH = os.path.join(ARTIFACT_DIR, "mapgen2_showcase.png")

def surface_to_array(surface: pygame.Surface) -> np.ndarray:
    """Convert a Pygame Surface to an RGB numpy array."""
    w, h = surface.get_size()
    buf = pygame.image.tostring(surface, "RGB")
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 3))
    return arr

def main():
    seed = 777
    size = 1000
    render_size = 900

    print(f"Generating Mapgen2 showcase with seed {seed}...")

    # 1. Classic Voronoi generator (Noisy edges and mapgen2 features disabled)
    gen_classic = PolygonMapGenerator(
        seed=seed,
        width=size,
        height=size,
        num_points=600,
        enable_corner_improvement=False,
        enable_noisy_edges=False,
        enable_roads=False,
        enable_lava=False,
        enable_watersheds=False,
    )

    # 2. Full Mapgen2 generator
    gen_mapgen2 = PolygonMapGenerator(
        seed=seed,
        width=size,
        height=size,
        num_points=600,
        enable_corner_improvement=True,
        enable_noisy_edges=True,
        enable_roads=True,
        enable_lava=True,
        enable_watersheds=True,
        noisy_tradeoff=0.5,
    )

    print("Rendering surfaces...")
    # Panel 1: Classic Voronoi
    surf1 = gen_classic.render_to_surface(
        width=render_size, height=render_size,
        use_brdf=False, use_noisy_edges=False, show_roads=False, show_lava=False
    )

    # Panel 2: Mapgen2 (Noisy Edges, Roads, Lava, Rivers)
    surf2 = gen_mapgen2.render_to_surface(
        width=render_size, height=render_size,
        use_brdf=False, use_noisy_edges=True, show_roads=True, show_lava=True
    )

    # Panel 3: Watershed Basins
    surf3 = gen_mapgen2.render_to_surface(
        width=render_size, height=render_size,
        use_brdf=False, use_noisy_edges=True, show_roads=True, show_lava=False, show_watersheds=True
    )

    # Panel 4: Mapgen2 with BRDF Shading
    surf4 = gen_mapgen2.render_to_surface(
        width=render_size, height=render_size,
        use_brdf=True, use_noisy_edges=True, show_roads=True, show_lava=True
    )

    img1 = surface_to_array(surf1)
    img2 = surface_to_array(surf2)
    img3 = surface_to_array(surf3)
    img4 = surface_to_array(surf4)

    print("Compositing 4-panel figure...")
    fig, axes = plt.subplots(2, 2, figsize=(16, 16), dpi=150)

    panels = [
        (axes[0, 0], img1, "1. Classic Voronoi (Straight Edges)",
         "Standard Voronoi dual-mesh: polygon slivers, straight edges, uniform lines."),
        (axes[0, 1], img2, "2. Mapgen2 (Noisy Edges + Roads + Lava)",
         "Recursive quad subdivision: organic fractal coasts, contour roads, volcanic lava fissures."),
        (axes[1, 0], img3, "3. Mapgen2 Watershed Drainage Basins",
         "Downslope-routed drainage catchments: distinct hydrological basins & river networks."),
        (axes[1, 1], img4, "4. Mapgen2 + Physically-Based BRDF Shading",
         "Full physical shading: 3D normals, soft shadows, Blinn-Phong specular glints, bathymetry."),
    ]

    for ax, img, title, subtitle in panels:
        ax.imshow(img)
        ax.set_title(f"{title}\n{subtitle}", fontsize=11, pad=14, fontweight='bold', wrap=True)
        ax.axis('off')

    plt.suptitle("Amit Patel's Mapgen2 Polygonal Terrain Architecture (Reference Port)", fontsize=16, fontweight='heavy', y=0.98)
    plt.tight_layout(rect=[0, 0.01, 1, 0.95])

    print(f"Saving comparison artifact to {OUTPUT_PATH}...")
    plt.savefig(OUTPUT_PATH, bbox_inches='tight')
    plt.close()
    print("Showcase rendering complete!")

if __name__ == '__main__':
    main()
