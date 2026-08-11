#!/usr/bin/env python3
"""
V1 headless verification for the pygame hex-map viewer.

Checks:
  1. Every edge sim_nation wires is hex-adjacent on the axial lattice
     (proves "all hexes connect like Civilization").
  2. pixel <-> axial round-trip for all 6 tile coordinates.
  3. SDL dummy: build_world_view + step_world x10 -> 0 audit violations,
     render_frame -> screenshot PNG written.

Usage:
    python3 tmp/probe_hex.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from logger import logInit

from hexmap import (LAYOUT_2X3, axial_to_pixel, pixel_to_axial,
                    edge_list_from_tiles, assert_edges_are_hex_adjacent)

from sim_nation import build_world


def check_adjacency():
    """Every simulation-wired edge must be hex-adjacent (full-edge share)."""
    tiles, _ = build_world()
    edges = edge_list_from_tiles(tiles)
    bad = assert_edges_are_hex_adjacent(tiles)
    print(f"[1/3] adjacency: {len(edges)} wired edges, "
          f"{len(bad)} non-adjacent")
    for a, b in bad:
        print(f"  BAD EDGE: {a} <-> {b}")
    return len(bad) == 0


def check_pixel_roundtrip(size=55):
    """pixel_to_axial(axial_to_pixel(q,r)) == (q,r) for all tiles."""
    ok = True
    for name, (q, r) in sorted(LAYOUT_2X3.items()):
        x, y = axial_to_pixel(q, r, size)
        q2, r2 = pixel_to_axial(x, y, size)
        if (q2, r2) != (q, r):
            print(f"  MISMATCH {name}: ({q},{r}) -> pixel({x:.1f},{y:.1f}) "
                  f"-> ({q2},{r2})")
            ok = False
    print(f"[2/3] pixel<->axial round-trip for {len(LAYOUT_2X3)} tiles "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def check_dummy_render():
    """Render one frame headlessly after stepping 10 turns; screenshot it."""
    import pygame

    import hexview as hv

    pygame.init()
    surface = pygame.display.set_mode((hv.WIDTH, hv.HEIGHT))
    world = hv.build_world_view()
    world["playing"] = False

    violations_total = 0
    for _ in range(10):
        violations_total += len(hv.step_world(world))

    world["hover_region"] = world["by_name"]["B1"]
    hv.render_frame(surface, world)
    pygame.image.save(surface, "hexview_frame.png")

    totals_str = ", ".join(f"{k}={round(v)}"
                           for k, v in world["currency_totals"].items())
    print(f"[3/3] dummy render: stepped to T={world['turn']}, "
          f"violations={violations_total}, current totals={{{totals_str}}}")
    print(f"      screenshot -> hexview_frame.png "
          f"({surface.get_width()}x{surface.get_height()})")
    pygame.quit()
    return violations_total == 0


def main():
    logInit()
    random.seed(42)
    ok = True
    ok &= check_adjacency()
    ok &= check_pixel_roundtrip()
    ok &= check_dummy_render()
    print("\n" + "=" * 60)
    print("PROBE PASS" if ok else "PROBE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())