#!/usr/bin/env python3
"""
v3_wilderness headless verification for the hex-world viewer (worldview.py).

Checks:
  1. 9x9 = 81 tiles; every engine-wired edge is hex-adjacent on the honeycomb
     (0 bad edges = "all hexes connect like Civilization").
  2. pixel <-> axial round-trip for all 81 tile coordinates.
  3. SDL dummy: build_world_view + step_world x20 -> renders, screenshots
     of the map + ticker written.
  4. Ticker archive: MIGRATE/CLAIM/DESTROY events collected (may be empty in
     early turns; the strip still renders).

Known: the still-open late-run BE-/GA+ class (tasks.md item 1) may fire on
longer runs — reported, NOT a hard fail.

Usage:
    python3 tmp/probe_worldview.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from logger import logInit

from hexmap import (rectangular_hex_layout, axial_to_pixel, pixel_to_axial,
                    assert_edges_are_hex_adjacent)
from sim_world import build_world, GRID_ROWS, GRID_COLS

TURNS = 20


def check_adjacency():
    tiles, _, _ = build_world()
    layout = rectangular_hex_layout(GRID_ROWS, GRID_COLS)
    bad = assert_edges_are_hex_adjacent(tiles, layout=layout)
    print(f"[1/3] world adjacency: {len(tiles)} tiles, "
          f"{len(bad)} non-adjacent edges")
    for a, b in bad:
        print(f"  BAD EDGE: {a} <-> {b}")
    return len(bad) == 0


def check_pixel_roundtrip(size=50):
    layout = rectangular_hex_layout(GRID_ROWS, GRID_COLS)
    ok = True
    for name, (q, r) in sorted(layout.items()):
        x, y = axial_to_pixel(q, r, size)
        q2, r2 = pixel_to_axial(x, y, size)
        if (q2, r2) != (q, r):
            print(f"  MISMATCH {name}: ({q},{r}) -> ({q2},{r2})")
            ok = False
    print(f"[2/3] pixel<->axial round-trip ({len(layout)} tiles) "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def check_dummy_render():
    import pygame

    import worldview as wv

    pygame.init()
    surface = pygame.display.set_mode((wv.WIDTH, wv.HEIGHT))
    world = wv.build_world_view()

    shifts = []
    for _ in range(TURNS):
        shifts.extend(wv.step_world(world))

    # Hover a claimed tile if any claimed tiles exist (else first tile).
    claimed = [r for r in world["tiles"]
               if getattr(r, "owner_nation", None) is not None]
    world["hover_region"] = claimed[0] if claimed else world["tiles"][0]
    wv.render_frame(surface, world)
    pygame.image.save(surface, "worldview_frame.png")

    # Pin a wilderness tile to exercise the UNCLAIMED card path.
    wild = [r for r in world["tiles"]
            if getattr(r, "owner_nation", None) is None]
    if wild:
        world["selected_region"] = wild[0]
        world["hover_region"] = None
    wv.render_frame(surface, world)
    pygame.image.save(surface, "worldview_wild.png")

    # Zoomed view (exercises camera clamp + scaled hit-test).
    world["cam"]["zoom"] = 1.6
    wv._clamp_cam(world)
    wv.render_frame(surface, world)
    pygame.image.save(surface, "worldview_zoom.png")

    events = world["ticker_events"]
    kinds = sorted({e["kind"] for e in events})
    totals = ", ".join(f"{k}={round(v)}"
                       for k, v in world["currency_totals"].items())
    print(f"[3/3] dummy render: stepped to T={world['turn']}, "
          f"violations={len(world['violations'])} "
          f"({len(shifts)} shift entries over {TURNS} turns)")
    print(f"      ticker events={len(events)} kinds={kinds}")
    print(f"      current totals={{{totals}}}")
    print("      screenshots -> worldview_frame.png / worldview_wild.png / "
          "worldview_zoom.png")
    pygame.quit()
    return True


def main():
    logInit()
    random.seed(42)
    ok = True
    ok &= check_adjacency()
    ok &= check_pixel_roundtrip()
    check_dummy_render()
    print("\n" + "=" * 60)
    print("WORLDVIEW PROBE PASS" if ok else "WORLDVIEW PROBE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())