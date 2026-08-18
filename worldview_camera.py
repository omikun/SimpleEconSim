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
    min_ox = 100 - sx1
    max_ox = (MAP_RIGHT - 100) - sx0
    if min_ox > max_ox:
        target_cx = MAP_RIGHT / 2.0
        cam['ox'] = target_cx - ((x0 + x1) / 2.0) * zoom
    else:
        cam['ox'] = max(min_ox, min(max_ox, cam['ox']))

    top = TOP_BAR_H
    bottom = HEIGHT - TICKER_H
    min_oy = top + 80 - sy1
    max_oy = bottom - 80 - sy0
    if min_oy > max_oy:
        target_cy = top + (bottom - top) / 2.0
        cam['oy'] = target_cy - ((y0 + y1) / 2.0) * zoom
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
    """Fit and center the entire hex map cleanly in the viewport."""
    x0, y0, x1, y1 = world['bbox']
    bw = max(1.0, x1 - x0)
    bh = max(1.0, y1 - y0)
    vw = MAP_RIGHT - 2 * _MARGIN
    vh = (HEIGHT - TOP_BAR_H - TICKER_H) - 2 * _MARGIN

    fit_zoom = min(vw / bw, vh / bh) * 0.95
    world['cam']['zoom'] = round(fit_zoom, 2)

    target_cx = MAP_RIGHT / 2.0
    target_cy = TOP_BAR_H + (HEIGHT - TOP_BAR_H - TICKER_H) / 2.0
    world['cam']['ox'] = target_cx - ((x0 + x1) / 2.0) * world['cam']['zoom']
    world['cam']['oy'] = target_cy - ((y0 + y1) / 2.0) * world['cam']['zoom']
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
