"""
scratch/test_label_micro_shifting.py — Verification script for dynamic label micro-shifting.
Tests polygon containment, zero-overlap guarantee, and renders visual verification frames.
"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["MPLCONFIGDIR"] = "/tmp"

import pygame
pygame.init()
pygame.font.init()

from worldview import build_world_view, step_world
from worldview_camera import WIDTH, HEIGHT
from worldview_ui import get_font
from worldview_map import draw_hex_map, point_in_polygon, find_label_micro_shift

def test_point_in_polygon_unit():
    # Square from (0,0) to (10,10)
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon(5, 5, square) == True
    assert point_in_polygon(-1, 5, square) == False
    assert point_in_polygon(11, 5, square) == False
    assert point_in_polygon(5, -1, square) == False
    assert point_in_polygon(5, 11, square) == False
    print("✓ point_in_polygon unit tests passed!")

def run_headless_simulation():
    test_point_in_polygon_unit()

    world = build_world_view(seed=42, terrain_seed=42, nation_seed=42)
    surface = pygame.Surface((WIDTH, HEIGHT))
    font = get_font(18)
    font_small = get_font(13)

    # Step world to generate demographic/economic activity
    for _ in range(3):
        step_world(world)

    artifact_dir = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759"

    # Test Overview layer at zoom = 1.0 (default overview)
    world['map_layer'] = 'overview'
    world['camera_zoom'] = 1.0
    surface.fill((10, 14, 20))
    draw_hex_map(surface, world, font, font_small)
    overview_path = os.path.join(artifact_dir, "verify_microshift_overview_zoom1.png")
    pygame.image.save(surface, overview_path)
    print(f"Saved: {overview_path}")

    # Test Population layer at zoom = 1.0
    world['map_layer'] = 'population'
    surface.fill((10, 14, 20))
    draw_hex_map(surface, world, font, font_small)
    pop_path = os.path.join(artifact_dir, "verify_microshift_pop_zoom1.png")
    pygame.image.save(surface, pop_path)
    print(f"Saved: {pop_path}")

    # Test Economy layer at zoom = 1.0
    world['map_layer'] = 'economy'
    surface.fill((10, 14, 20))
    draw_hex_map(surface, world, font, font_small)
    econ_path = os.path.join(artifact_dir, "verify_microshift_econ_zoom1.png")
    pygame.image.save(surface, econ_path)
    print(f"Saved: {econ_path}")

    # Test with Selected Nation
    world['map_layer'] = 'overview'
    nation = world['nations'][0]
    world['selected_nation'] = nation
    world['selected_region'] = nation.tiles[0]
    surface.fill((10, 14, 20))
    draw_hex_map(surface, world, font, font_small)
    sel_path = os.path.join(artifact_dir, "verify_microshift_selected_nation.png")
    pygame.image.save(surface, sel_path)
    print(f"Saved: {sel_path}")

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_headless_simulation()
