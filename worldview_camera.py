"""
Camera, viewport bounds, zooming, panning, and coordinate transformations for worldview.
"""

from hexmap import axial_to_pixel, pixel_to_axial

HEX_SIZE = 50
WIDTH, HEIGHT = 1400, 900
MAP_RIGHT = 1060
TOP_BAR_H = 52
TICKER_H = 64
_MARGIN = 24


def clamp_cam(world):
    """Keep the hex map within bounds while allowing generous panning."""
    cam = world['cam']
    zoom = cam['zoom']
    x0, y0, x1, y1 = world['bbox']
    sx0, sy0, sx1, sy1 = x0 * zoom, y0 * zoom, x1 * zoom, y1 * zoom

    # Map viewport bounds: X in [0, MAP_RIGHT], Y in [TOP_BAR_H, HEIGHT - TICKER_H]
    # Allow panning across the viewport; only clamp if the map is dragged far off-screen
    min_ox = 100 - sx1
    max_ox = (MAP_RIGHT - 100) - sx0
    if min_ox > max_ox:
        cam['ox'] = (MAP_RIGHT - (sx0 + sx1)) / 2.0
    else:
        cam['ox'] = max(min_ox, min(max_ox, cam['ox']))

    top = TOP_BAR_H
    bottom = HEIGHT - TICKER_H
    min_oy = top + 80 - sy1
    max_oy = bottom - 80 - sy0
    if min_oy > max_oy:
        cam['oy'] = (top + bottom - (sy0 + sy1)) / 2.0
    else:
        cam['oy'] = max(min_oy, min(max_oy, cam['oy']))


def zoom_cam_at(world, factor, mx, my):
    """Zoom camera anchored at screen pixel (mx, my)."""
    cam = world['cam']
    old_zoom = cam['zoom']
    new_zoom = max(0.35, min(3.0, old_zoom * factor))
    if abs(new_zoom - old_zoom) < 1e-6:
        return
    # Anchor: keep the world coordinate under (mx, my) fixed on screen
    ratio = new_zoom / old_zoom
    cam['ox'] = mx - (mx - cam['ox']) * ratio
    cam['oy'] = my - (my - cam['oy']) * ratio
    cam['zoom'] = new_zoom
    clamp_cam(world)


def reset_cam(world):
    """Reset zoom to 1.0 and center the map in the viewport."""
    world['cam']['zoom'] = 1.0
    x0, y0, x1, y1 = world['bbox']
    top = TOP_BAR_H
    bottom = HEIGHT - TICKER_H
    world['cam']['ox'] = (MAP_RIGHT - (x0 + x1)) / 2.0
    world['cam']['oy'] = (top + bottom - (y0 + y1)) / 2.0
    clamp_cam(world)


def hex_px(world, q, r):
    """Convert axial hex (q, r) to screen pixel coordinates with pan and zoom."""
    x, y = axial_to_pixel(q, r, HEX_SIZE * world['cam']['zoom'])
    return (int(x + world['cam']['ox']), int(y + world['cam']['oy']))


def tile_at(world, mx, my):
    """Return the Region under screen pixel (mx, my), or None."""
    if mx >= MAP_RIGHT or my < TOP_BAR_H or my > HEIGHT - TICKER_H:
        return None
    cam = world['cam']
    q, r = pixel_to_axial((mx - cam['ox']) / cam['zoom'],
                          (my - cam['oy']) / cam['zoom'],
                          HEX_SIZE)
    name = world['reverse'].get((q, r))
    return world['by_name'].get(name) if name is not None else None
