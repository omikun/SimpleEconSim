"""
Camera, viewport bounds, zooming, panning, and coordinate transformations for worldview.
"""

import math
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
    from world_config import is_voronoi_topology
    pad_ratio = 0.0 if is_voronoi_topology() else MAP_PAD_RATIO
    pad_x = (x1 - x0) * pad_ratio
    pad_y = (y1 - y0) * pad_ratio
    return (x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y)


def get_min_zoom(world):
    """Return minimum zoom factor required so that the map strictly fills the viewport (no out of bounds)."""
    min_wx, min_wy, max_wx, max_wy = get_map_bounds(world)
    world_w = max(1.0, max_wx - min_wx)
    world_h = max(1.0, max_wy - min_wy)
    vw = MAP_RIGHT
    vh = HEIGHT - TOP_BAR_H - TICKER_H
    return max(vw / world_w, vh / world_h)


def world_to_screen(world, wx, wy, elevation=0.0):
    """Project world coordinate (wx, wy) with elevation into screen pixels.

    When pitch > 0 (zoomed in, Civilization style), applies perspective foreshortening
    and elevation relief lift. When pitch == 0 (zoomed out), reduces strictly to 2D pan/zoom.
    """
    cam = world['cam']
    zoom = cam['zoom']
    ox, oy = cam['ox'], cam['oy']
    pitch = cam.get('pitch', 0.0)

    if pitch < 0.2:
        return (int(wx * zoom + ox), int(wy * zoom + oy))

    # Viewport center
    vcx = MAP_RIGHT / 2.0
    vcy = TOP_BAR_H + (HEIGHT - TOP_BAR_H - TICKER_H) / 2.0

    # Coordinates relative to viewport center
    fx = wx * zoom + ox - vcx
    fy = wy * zoom + oy - vcy

    pitch_rad = math.radians(pitch)
    cos_p = math.cos(pitch_rad)
    sin_p = math.sin(pitch_rad)

    # Foreshortening along vertical Y axis
    fy_tilted = fy * cos_p

    # Mountain/elevation vertical pop in 3D side view
    if elevation > 0.0:
        elev_pop = elevation * 90.0 * zoom * sin_p
        fy_tilted -= elev_pop

    # Perspective depth scale (horizon tapers slightly into distance)
    k = 0.00065 * sin_p
    depth_scale = 1.0 / max(0.2, (1.0 + fy_tilted * k))

    sx = int(vcx + fx * depth_scale)
    sy = int(vcy + fy_tilted * depth_scale)
    return (sx, sy)


def screen_to_world(world, sx, sy):
    """Invert screen pixels back to world (wx, wy) on the ground plane (elevation=0)."""
    cam = world['cam']
    zoom = cam['zoom']
    ox, oy = cam['ox'], cam['oy']
    pitch = cam.get('pitch', 0.0)

    if pitch < 0.2:
        return ((sx - ox) / zoom, (sy - oy) / zoom)

    vcx = MAP_RIGHT / 2.0
    vcy = TOP_BAR_H + (HEIGHT - TOP_BAR_H - TICKER_H) / 2.0

    fx_prime = sx - vcx
    fy_prime = sy - vcy

    pitch_rad = math.radians(pitch)
    cos_p = math.cos(pitch_rad)
    sin_p = math.sin(pitch_rad)

    k = 0.00065 * sin_p
    denom = 1.0 - fy_prime * k
    if abs(denom) < 1e-4:
        denom = 1e-4
    Y = fy_prime / denom
    fy = Y / max(1e-4, cos_p)

    depth_scale = 1.0 / max(0.2, (1.0 + Y * k))
    fx = fx_prime / max(1e-4, depth_scale)

    wx = (fx + vcx - ox) / zoom
    wy = (fy + vcy - oy) / zoom
    return (wx, wy)


def clamp_cam(world):
    """Keep camera strictly within bounds so only the map is visible with zero out-of-bounds view."""
    cam = world['cam']
    min_zoom = get_min_zoom(world)
    if cam['zoom'] < min_zoom:
        cam['zoom'] = min_zoom

    # Update camera pitch smoothly: angles up toward side view as player zooms in (Civilization-style)
    max_zoom = 4.0
    t = max(0.0, min(1.0, (cam['zoom'] - min_zoom) / max(1e-4, max_zoom - min_zoom)))
    cam['pitch'] = max(0.0, min(52.0, (t ** 0.85) * 52.0))

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
    """Zoom camera anchored at screen pixel (mx, my), tilting camera to side view as it gets closer."""
    cam = world['cam']
    old_zoom = cam['zoom']
    min_zoom = get_min_zoom(world)
    max_zoom = 4.0
    new_zoom = max(min_zoom, min(max_zoom, old_zoom * factor))
    if abs(new_zoom - old_zoom) < 1e-6:
        return
    # Anchor: keep the world coordinate under (mx, my) fixed on screen
    ratio = new_zoom / old_zoom
    cam['ox'] = mx - (mx - cam['ox']) * ratio
    cam['oy'] = my - (my - cam['oy']) * ratio
    cam['zoom'] = new_zoom

    # Civilization zoom-tilt: as zoom increases, angle up toward a 3D side view
    t = max(0.0, min(1.0, (new_zoom - min_zoom) / max(1e-4, max_zoom - min_zoom)))
    cam['pitch'] = max(0.0, min(52.0, (t ** 0.85) * 52.0))
    clamp_cam(world)


def reset_cam(world):
    """Fit and center the entire hex map cleanly in the viewport with zero out-of-bounds visible."""
    min_wx, min_wy, max_wx, max_wy = get_map_bounds(world)
    fit_zoom = get_min_zoom(world)
    world['cam']['zoom'] = fit_zoom
    world['cam']['pitch'] = 0.0

    target_cx = MAP_RIGHT / 2.0
    target_cy = TOP_BAR_H + (HEIGHT - TOP_BAR_H - TICKER_H) / 2.0
    world['cam']['ox'] = target_cx - ((min_wx + max_wx) / 2.0) * fit_zoom
    world['cam']['oy'] = target_cy - ((min_wy + max_wy) / 2.0) * fit_zoom
    clamp_cam(world)


def hex_px(world, q, r, elevation=0.0):
    """Convert axial hex (q, r) or world (x, y) to screen pixel coordinates with pan, zoom, and Civilization tilt."""
    from world_config import is_voronoi_topology
    if is_voronoi_topology():
        return world_to_screen(world, q, r, elevation=elevation)
    x, y = axial_to_pixel(q, r, HEX_SIZE)
    return world_to_screen(world, x, y, elevation=elevation)


def tile_at(world, mx, my):
    """Return the Region under screen pixel (mx, my), or None, accounting for camera tilt."""
    if mx >= MAP_RIGHT or my < TOP_BAR_H or my > HEIGHT - TICKER_H:
        return None
    wx, wy = screen_to_world(world, mx, my)
    from world_config import is_voronoi_topology
    if is_voronoi_topology():
        gen = world.get('gen')
        if gen is not None and hasattr(gen, 'get_center_at'):
            center = gen.get_center_at(wx, wy)
            if center is not None:
                if hasattr(center, 'region'):
                    return center.region
                name = getattr(center, 'name', f"c{center.index}")
                return world['by_name'].get(name)
        # fallback: find nearest centroid
        best_t = None
        best_d2 = 1e12
        for t in world.get('tiles', []):
            cx, cy = getattr(t, 'centroid', (0.0, 0.0))
            d2 = (wx - cx) ** 2 + (wy - cy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_t = t
        return best_t

    q, r = pixel_to_axial(wx, wy, HEX_SIZE)
    name = world['reverse'].get((q, r))
    return world['by_name'].get(name) if name is not None else None
