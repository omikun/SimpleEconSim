import os
import sys
import math
import pygame
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import LinearNDInterpolator

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

from polygon_map import PolygonMapGenerator, BIOME_COLORS

ARTIFACT_DIR = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759"
OUTPUT_PATH = os.path.join(ARTIFACT_DIR, "shading_comparison.png")

def surface_to_array(surface: pygame.Surface) -> np.ndarray:
    w, h = surface.get_size()
    buf = pygame.image.tostring(surface, "RGB")
    return np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 3)).copy()

def main():
    seed = 777
    size = 1000
    render_size = 800

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
    )

    # 1. Current BRDF rendering (flat cell fills, under-scaled normals)
    print("Rendering 1: Current BRDF...")
    surf_curr = gen.render_to_surface(
        width=render_size, height=render_size,
        use_brdf=True, use_noisy_edges=True, show_roads=True, show_lava=True
    )
    img_curr = surface_to_array(surf_curr)

    # 2. Enhanced Normal Scale BRDF (per-polygon but with realistic 3D slope scale kh=500)
    print("Rendering 2: Recalibrated BRDF normals...")
    # Recalculate BRDF shading with proper height exaggeration
    # In polygon_map, nx = -dx * height_exaggeration * 40.0
    # Since dx ~ 0.001, we want height_exaggeration around 15.0 to 20.0 (or kh ~ 600)
    gen.compute_brdf_shading(height_exaggeration=16.0)
    surf_boosted = gen.render_to_surface(
        width=render_size, height=render_size,
        use_brdf=True, use_noisy_edges=True, show_roads=True, show_lava=True
    )
    img_boosted = surface_to_array(surf_boosted)

    # 3. Continuous Cartographic Shaded Relief (per-pixel hillshading interpolated across mesh)
    print("Rendering 3: Continuous Shaded Relief...")
    # Get base surface with noisy edges and biome colors (unlit)
    surf_base = gen.render_to_surface(
        width=render_size, height=render_size,
        use_brdf=False, use_noisy_edges=True, show_roads=True, show_lava=True
    )
    img_base = surface_to_array(surf_base).astype(np.float32)

    # Continuous elevation interpolation
    pts = []
    elevs = []
    for c in gen.centers:
        pts.append([c.x, c.y])
        elevs.append(c.elevation)
    for cn in gen.corners:
        pts.append([cn.x, cn.y])
        elevs.append(cn.elevation)

    interp = LinearNDInterpolator(np.array(pts), np.array(elevs))
    gy, gx = np.mgrid[0:size:render_size*1j, 0:size:render_size*1j]
    H = interp(gx, gy)
    H = np.nan_to_num(H, nan=0.0)

    # Gradient & surface normals
    dHy, dHx = np.gradient(H)
    kh = 140.0  # Cartographic vertical exaggeration
    nx = -dHx * kh
    ny = -dHy * kh
    nz = np.ones_like(nx)
    norm = np.sqrt(nx*nx + ny*ny + nz*nz)
    nx /= norm
    ny /= norm
    nz /= norm

    # Light NW (-0.55, -0.55, 0.70)
    L = np.array([-0.55, -0.55, 0.70])
    L /= np.linalg.norm(L)

    NdotL = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0.0, 1.0)
    diffuse = np.power(NdotL, 1.15) * 1.35
    ambient = (nz * 0.60 + 0.40) * 0.85
    shade = diffuse + ambient - 0.45

    # Add subtle micro-relief texture noise (fractal high-frequency detail)
    rng = np.random.RandomState(42)
    noise = (rng.rand(render_size, render_size) - 0.5) * 0.08
    shade = np.clip(shade + noise, 0.25, 1.75)

    # Identify land vs ocean pixels (ocean is blueish)
    is_ocean = (img_base[:, :, 2] > img_base[:, :, 0] + 30) & (img_base[:, :, 1] < 120) & (H < 0.22)

    img_continuous = img_base.copy()
    for ch in range(3):
        img_continuous[:, :, ch] = np.where(
            is_ocean,
            img_curr[:, :, ch],  # keep ocean BRDF water waves & specular
            np.clip(img_base[:, :, ch] * shade, 0, 255)
        )
    img_continuous = img_continuous.astype(np.uint8)

    # 4. Side-by-side composite
    fig, axes = plt.subplots(1, 3, figsize=(20, 7), dpi=150)
    axes[0].imshow(img_curr)
    axes[0].set_title("1. Current BRDF (Flat Polygon Fills)\nUnder-scaled normals (Nz ≈ 0.98), solid cell colors", fontsize=11, fontweight='bold')
    axes[0].axis('off')

    axes[1].imshow(img_boosted)
    axes[1].set_title("2. Boosted Polygon Normal Relief\nProper vertical exaggeration, but still per-cell flat fills", fontsize=11, fontweight='bold')
    axes[1].axis('off')

    axes[2].imshow(img_continuous)
    axes[2].set_title("3. Continuous Shaded Relief (Cartographic Hillshade)\nPer-pixel interpolated normals + micro-relief + soft lighting", fontsize=11, fontweight='bold')
    axes[2].axis('off')

    plt.suptitle("Diagnosis: Why Polygonal Terrain Appears Flat & Solution", fontsize=15, fontweight='heavy', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(OUTPUT_PATH, bbox_inches='tight')
    print(f"Saved comparison to {OUTPUT_PATH}")

if __name__ == '__main__':
    main()
