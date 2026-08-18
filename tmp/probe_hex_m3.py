#!/usr/bin/env python3
"""
M3 viewer gate — headless SDL run of hexview with the M3 regime layer wired.

Steps the world ~40 turns (enough for adults to form and legitimacy to
drift, and for the democratic nation to at least drift), renders a frame with
the national HUD + one hovered tile (so the regime readout line executes),
and asserts 0 LEAK / 0 SUPPLY SHIFT across every stepped turn.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
import hexview


def main():
    pygame.init()
    surface = pygame.display.set_mode((hexview.WIDTH, hexview.HEIGHT))
    world = hexview.build_world_view()
    world['playing'] = False
    world['frame'] = 0
    world['hud'] = True

    # Top bar: with nothing pinned it shows the first nation.
    assert hexview._selected_nation(world) is world['nations'][0], \
        "top bar default nation is not the first nation"
    hexview.render_frame(surface, world)
    pygame.image.save(surface, "hexview_topbar.png")
    print("top-bar frame rendered -> hexview_topbar.png")

    # Prime the pop-delta cache (mirrors main()).
    for r in world['tiles']:
        hexview._pops[r.name] = hexview._region_pop(r)

    violations = []
    for _ in range(40):
        violations.extend(hexview.step_world(world))

    assert not violations, f"viewer step violations: {violations}"

    # Hover the first tile so the M3 readout path executes.
    world['hover_region'] = world['tiles'][0]
    hexview.render_frame(surface, world)

    # Simulate a click on the first tile: pin it, reset hover, then render
    # so the pinned readout (charts + regime + nation summary) executes with
    # the mouse away from the tile.
    clicked = hexview._tile_at(world, *hexview._hex_px(*hexview.LAYOUT_2X3[
        world['tiles'][0].name]))
    assert clicked is world['tiles'][0], "click hit-test failed"
    world['selected_region'] = clicked
    world['hover_region'] = None
    hexview.render_frame(surface, world)
    pygame.image.save(surface, "hexview_m3_pinned.png")
    print("pinned frame rendered -> hexview_m3_pinned.png")

    # Confirm M3 state actually changed (legitimacy drift / regime events).
    events = [h for h in world['nation_history'] if h.get('event')]
    legit_moved = len({h['legitimacy'] for h in world['nation_history']}) > 1
    any_ruling = any(h.get('ruling') for h in world['nation_history'])

    print(f"turns={world['turn']}  events={len(events)} "
          f"legit_moved={legit_moved}  any_ruling={any_ruling}  "
          f"violations={len(violations)}")

    # The democratic nation should have drifted legitimacy by turn 40.
    assert legit_moved, "legitimacy did not drift over 40 turns"

    pygame.image.save(surface, "hexview_m3_frame.png")
    print("PROBE PASS: M3 viewer runs headlessly, 0 LEAK / SHIFT, "
          "legitimacy drifts, frame rendered to hexview_m3_frame.png")


if __name__ == "__main__":
    main()