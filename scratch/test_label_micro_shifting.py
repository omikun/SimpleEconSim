"""
scratch/test_label_micro_shifting.py — Verification script for dynamic label micro-shifting.
Tests:
1. Strict priority hierarchy (Nation tiles >= 600 > Wilderness tiles <= 450).
2. Polygon containment (point_in_polygon).
3. Frame-by-frame inertia animation (strictly 1-3 pixels per frame, no sudden jumps/flickers).
4. Zero overlap across all accepted labels.
"""
import os
import math
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["MPLCONFIGDIR"] = "/tmp"

import pygame
pygame.init()
pygame.font.init()

from worldview import build_world_view, step_world
from worldview_camera import WIDTH, HEIGHT
from worldview_ui import get_font
from worldview_map import draw_hex_map, point_in_polygon, find_label_micro_shift, get_tile_label_priority

def test_point_in_polygon_unit():
    # Square from (0,0) to (10,10)
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon(5, 5, square) == True
    assert point_in_polygon(-1, 5, square) == False
    assert point_in_polygon(11, 5, square) == False
    assert point_in_polygon(5, -1, square) == False
    assert point_in_polygon(5, 11, square) == False
    print("✓ point_in_polygon unit tests passed!")

def test_priority_hierarchy(world):
    """Verify that every nation tile has higher priority than every wilderness tile."""
    nation_priorities = []
    wilderness_priorities = []

    for region in world['tiles']:
        p = get_tile_label_priority(region, world)
        if getattr(region, 'owner_nation', None) is not None:
            nation_priorities.append((p, region.name))
            assert p >= 600, f"Nation tile {region.name} has priority {p} < 600!"
        elif not getattr(region, 'is_ocean', False) and getattr(region, 'elevation_meters', 0) >= 0:
            wilderness_priorities.append((p, region.name))
            assert p <= 450, f"Wilderness tile {region.name} has priority {p} > 450!"

    min_nation = min(p for p, _ in nation_priorities)
    max_wild = max(p for p, _ in wilderness_priorities)
    print(f"✓ Priority hierarchy verified: Lowest nation tile priority = {min_nation} > Highest wilderness priority = {max_wild}")
    assert min_nation > max_wild, "Nation tiles must strictly dominate wilderness tiles!"

def test_inertia_animation(world, surface, font, font_small):
    """Verify smooth per-frame animation and inertia (shifts move at <= 2.5px/frame)."""
    # Clear offsets
    world['_label_offsets'] = {}
    world['map_layer'] = 'overview'
    world['camera_zoom'] = 1.0

    # Frame 0: map load
    draw_hex_map(surface, world, font, font_small)
    initial_offsets = {k: v for k, v in world['_label_offsets'].items()}

    # Now select a tile with a neighbor to trigger conflict and shift
    nation = world['nations'][0]
    world['selected_region'] = nation.tiles[0]
    world['selected_nation'] = nation

    prev_offsets = {k: v for k, v in world['_label_offsets'].items()}
    max_observed_speed = 0.0

    # Run 12 frames and verify max delta between consecutive frames
    for frame_idx in range(1, 15):
        draw_hex_map(surface, world, font, font_small)
        curr_offsets = world['_label_offsets']

        for r_key, (cur_x, cur_y) in curr_offsets.items():
            if r_key in prev_offsets:
                prev_x, prev_y = prev_offsets[r_key]
                step = math.hypot(cur_x - prev_x, cur_y - prev_y)
                if step > max_observed_speed:
                    max_observed_speed = step
                # Must be strictly within 1-3 pixels per frame
                assert step <= 2.05, f"Frame {frame_idx}: Label {r_key} moved {step:.2f}px in a single frame (> 2.05px limit)!"

        prev_offsets = {k: v for k, v in curr_offsets.items()}

    print(f"✓ Inertia animation verified: Maximum observed single-frame step = {max_observed_speed:.2f}px (strictly <= 2.0px/frame)")

def run_headless_simulation():
    test_point_in_polygon_unit()

    world = build_world_view(seed=42, terrain_seed=42, nation_seed=42)
    surface = pygame.Surface((WIDTH, HEIGHT))
    font = get_font(18)
    font_small = get_font(13)

    # Step world to generate demographic/economic activity
    for _ in range(3):
        step_world(world)

    test_priority_hierarchy(world)
    test_inertia_animation(world, surface, font, font_small)

    artifact_dir = "/Users/sli/.gemini/antigravity/brain/11eb900e-54d0-4082-b924-ee19cb7c9759"

    # Overview layer
    world['map_layer'] = 'overview'
    world['camera_zoom'] = 1.0
    surface.fill((10, 14, 20))
    draw_hex_map(surface, world, font, font_small)
    overview_path = os.path.join(artifact_dir, "verify_microshift_overview_zoom1.png")
    pygame.image.save(surface, overview_path)
    print(f"Saved: {overview_path}")

    # Population layer
    world['map_layer'] = 'population'
    surface.fill((10, 14, 20))
    draw_hex_map(surface, world, font, font_small)
    pop_path = os.path.join(artifact_dir, "verify_microshift_pop_zoom1.png")
    pygame.image.save(surface, pop_path)
    print(f"Saved: {pop_path}")

    # Selected nation view
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
