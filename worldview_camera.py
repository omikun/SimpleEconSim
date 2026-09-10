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


MAP_PAD_RATIO = 0.18


def get_map_bounds(world):
    """Return world pixel coordinates (min_wx, min_wy, max_wx, max_wy) of the map surface."""
    x0, y0, x1, y1 = world['bbox']
    pad_x = (x1 - x0) * MAP_PAD_RATIO
    pad_y = (y1 - y0) * MAP_PAD_RATIO
    return (x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y)


def get_min_zoom(world):
    """Return minimum zoom factor required so that the map strictly fills the viewport (no out of bounds)."""
    min_wx, min_wy, max_wx, max_wy = get_map_bounds(world)
    world_w = max(1.0, max_wx - min_wx)
    world_h = max(1.0, max_wy - min_wy)
    vw = MAP_RIGHT
    vh = HEIGHT - TOP_BAR_H - TICKER_H
    return max(vw / world_w, vh / world_h)


def clamp_cam(world):
    """Keep camera strictly within bounds so only the map is visible with zero out-of-bounds view."""
    cam = world['cam']
    min_zoom = get_min_zoom(world)
    if cam['zoom'] < min_zoom:
        cam['zoom'] = min_zoom

    zoom = cam['zoom']
    min_wx, min_wy, max_wx, max_wy = get_map_bounds(world)

    # Viewport bounds: X in [0, MAP_RIGHT], Y in [TOP_BAR_H, HEIGHT - TICKER_H]
    v_x0, v_x1 = 0, MAP_RIGHT
    v_y0, v_y1 = TOP_BAR_H, HEIGHT - TICKER_H

    # screen_x0 = min_wx * zoom + ox <= v_x0  =>  ox <= v_x0 - min_wx * zoom
    max_ox = v_x0 - min_wx * zoom
    # screen_x1 = max_wx * zoom + ox >= v_x1  =>  ox >= v_x1 - max_wx * zoom
    min_ox = v_x1 - max_wx * zoom

    if min_ox > max_ox:
        cam['ox'] = (v_x0 + v_x1) / 2.0 - ((min_wx + max_wx) / 2.0) * zoom
    else:
        cam['ox'] = max(min_ox, min(max_ox, cam['ox']))

    # screen_y0 = min_wy * zoom + oy <= v_y0  =>  oy <= v_y0 - min_wy * zoom
    max_oy = v_y0 - min_wy * zoom
    # screen_y1 = max_wy * zoom + oy >= v_y1  =>  oy >= v_y1 - max_wy * zoom
    min_oy = v_y1 - max_wy * zoom

    if min_oy > max_oy:
        cam['oy'] = (v_y0 + v_y1) / 2.0 - ((min_wy + max_wy) / 2.0) * zoom
    else:
        cam['oy'] = max(min_oy, min(max_oy, cam['oy']))


def zoom_cam_at(world, factor, mx, my):
    """Zoom camera anchored at screen pixel (mx, my), preventing out-of-bounds view."""
    cam = world['cam']
    old_zoom = cam['zoom']
    min_zoom = get_min_zoom(world)
    max_zoom = 3.0
    new_zoom = max(min_zoom, min(max_zoom, old_zoom * factor))
    if abs(new_zoom - old_zoom) < 1e-6:
        return
    # Anchor: keep the world coordinate under (mx, my) fixed on screen
    ratio = new_zoom / old_zoom
    cam['ox'] = mx - (mx - cam['ox']) * ratio
    cam['oy'] = my - (my - cam['oy']) * ratio
    cam['zoom'] = new_zoom
    clamp_cam(world)


def reset_cam(world):
    """Fit and center the entire hex map cleanly in the viewport with zero out-of-bounds visible."""
    min_wx, min_wy, max_wx, max_wy = get_map_bounds(world)
    fit_zoom = get_min_zoom(world)
    world['cam']['zoom'] = fit_zoom

    target_cx = MAP_RIGHT / 2.0
    target_cy = TOP_BAR_H + (HEIGHT - TOP_BAR_H - TICKER_H) / 2.0
    world['cam']['ox'] = target_cx - ((min_wx + max_wx) / 2.0) * fit_zoom
    world['cam']['oy'] = target_cy - ((min_wy + max_wy) / 2.0) * fit_zoom
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
