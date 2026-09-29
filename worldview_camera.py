"""
Camera, viewport bounds, zooming, panning, and coordinate transformations for worldview.
True 3D perspective projection with 35mm lens and constant view angle (pitch 52°, yaw 9°).
"""

import math
import numpy as np
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
    x0, y0, x1, y1 = world.get('bbox', (0, 0, 1024, 1024))
    from world_config import is_voronoi_topology
    pad_ratio = 0.0 if is_voronoi_topology() else MAP_PAD_RATIO
    pad_x = (x1 - x0) * pad_ratio
    pad_y = (y1 - y0) * pad_ratio
    return (x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y)


def get_min_zoom(world):
    """Return minimum zoom factor required so that the map strictly fills the viewport."""
    return 0.85


_cam_mvp_cache = {}


def compute_pitch_yaw(zoom):
    """Compute camera pitch and yaw based on zoom level.
    Zoomed out (zoom <= 0.9): straight down top-down perspective (pitch 89.0°, yaw 0.0°).
    Zoomed in (zoom >= 2.2): regular 35mm 3D perspective (pitch 52.0°, yaw 9.0°).
    Smooth S-curve interpolation between overview and close-up.
    """
    t = float(np.clip((zoom - 0.90) / (2.20 - 0.90), 0.0, 1.0))
    ts = t * t * (3.0 - 2.0 * t)
    pitch = 89.0 - ts * (89.0 - 52.0)
    yaw = 0.0 + ts * 9.0
    return pitch, yaw


def get_camera_mvp(world):
    """Compute and cache the 35mm regular perspective MVP matrix for the current frame."""
    global _cam_mvp_cache
    cam = world['cam']
    pitch = float(cam.get('pitch', 52.0))
    yaw = float(cam.get('yaw', 9.0))
    zoom = max(0.2, float(cam.get('zoom', 1.0)))
    tx = float(cam.get('target_x', 512.0))
    ty = float(cam.get('target_y', 512.0))

    key = (pitch, yaw, zoom, tx, ty)
    if key in _cam_mvp_cache:
        return _cam_mvp_cache[key]

    target = np.array([tx, ty, 0.0], dtype=np.float32)

    p_rad = math.radians(pitch)
    y_rad = math.radians(yaw)
    v_dir = np.array([
        math.sin(y_rad) * math.cos(p_rad),
        -math.cos(y_rad) * math.cos(p_rad),
        math.sin(p_rad)
    ], dtype=np.float32)
    v_norm = np.linalg.norm(v_dir)
    v_dir = v_dir / (v_norm if v_norm > 1e-6 else 1.0)

    # Base overview distance transitions smoothly from 1100 (top-down) to 760 (tilted 52°)
    t_pitch = float(np.clip((89.0 - pitch) / (89.0 - 52.0), 0.0, 1.0))
    base_dist = 1100.0 - t_pitch * (1100.0 - 760.0)
    dist = base_dist / zoom
    eye = target + v_dir * dist

    vw = float(MAP_RIGHT)
    vh = float(HEIGHT - TOP_BAR_H - TICKER_H)
    aspect = vw / max(1.0, vh)
    fovy_rad = math.radians(45.0)

    from render_engine.gpu.micropoly_3d_renderer import mat4_perspective, mat4_lookat
    proj = mat4_perspective(fovy_rad, aspect, 10.0, 25000.0)
    view = mat4_lookat(eye, target, (0.0, 0.0, 1.0))
    mvp = proj @ view

    if len(_cam_mvp_cache) > 8:
        _cam_mvp_cache.clear()
    _cam_mvp_cache[key] = mvp
    return mvp


def project_pts_3d_to_screen(world, pts_homo, mvp=None):
    """Vectorized projection of (N, 4) homogeneous points [x, y, z, 1.0] to (N, 2) screen pixels."""
    if mvp is None:
        mvp = get_camera_mvp(world)

    clip = pts_homo @ mvp.T
    w = clip[:, 3]
    valid = w > 1e-4

    vw = float(MAP_RIGHT)
    vh = float(HEIGHT - TOP_BAR_H - TICKER_H)

    w_safe = np.where(valid, w, 1.0)
    ndc_x = clip[:, 0] / w_safe
    ndc_y = clip[:, 1] / w_safe

    sx = ((ndc_x * 0.5 + 0.5) * vw).astype(np.int32)
    sy = (TOP_BAR_H + (1.0 - (ndc_y * 0.5 + 0.5)) * vh).astype(np.int32)

    sx = np.where(valid, sx, -9999)
    sy = np.where(valid, sy, -9999)
    return np.column_stack([sx, sy])


def world_to_screen(world, wx, wy, elevation=0.0, wz=None):
    """Project world coordinate (wx, wy) with 3D elevation into screen pixels using 35mm perspective."""
    from world_config import is_voronoi_topology
    if not is_voronoi_topology():
        cam = world['cam']
        zoom = cam['zoom']
        ox, oy = cam['ox'], cam['oy']
        return (int(wx * zoom + ox), int(wy * zoom + oy))

    mvp = get_camera_mvp(world)
    if wz is None:
        slot_state = world.get('slot_state') or {}
        h_scale = float(slot_state.get('height_scale', 48.0))
        wz = float(elevation) * h_scale

    v4 = np.array([float(wx), float(wy), wz, 1.0], dtype=np.float32)
    clip = mvp @ v4
    w = float(clip[3])
    if w <= 1e-4:
        return (-9999, -9999)

    ndc_x = float(clip[0]) / w
    ndc_y = float(clip[1]) / w

    vw = float(MAP_RIGHT)
    vh = float(HEIGHT - TOP_BAR_H - TICKER_H)
    sx = int((ndc_x * 0.5 + 0.5) * vw)
    sy = int(TOP_BAR_H + (1.0 - (ndc_y * 0.5 + 0.5)) * vh)
    return (sx, sy)


def screen_to_world(world, sx, sy):
    """Invert screen pixel back to world (wx, wy) on 3D terrain surface, accounting for mountain elevation."""
    from world_config import is_voronoi_topology
    if not is_voronoi_topology():
        cam = world['cam']
        pitch = float(cam.get('pitch', 0.0))
        if pitch < 0.5:
            zoom = cam['zoom']
            ox, oy = cam['ox'], cam['oy']
            return ((sx - ox) / zoom, (sy - oy) / zoom)

    mvp = get_camera_mvp(world)
    try:
        inv_mvp = np.linalg.inv(mvp)
    except np.linalg.LinAlgError:
        return (512.0, 512.0)

    vw = float(MAP_RIGHT)
    vh = float(HEIGHT - TOP_BAR_H - TICKER_H)
    ndc_x = (float(sx) / vw) * 2.0 - 1.0
    ndc_y = (1.0 - ((float(sy) - TOP_BAR_H) / vh)) * 2.0 - 1.0

    p_near = inv_mvp @ np.array([ndc_x, ndc_y, -1.0, 1.0], dtype=np.float32)
    p_far = inv_mvp @ np.array([ndc_x, ndc_y, 1.0, 1.0], dtype=np.float32)
    if abs(p_near[3]) < 1e-6 or abs(p_far[3]) < 1e-6:
        return (512.0, 512.0)

    p_near = p_near[:3] / p_near[3]
    p_far = p_far[:3] / p_far[3]
    d = p_far - p_near
    d_norm = np.linalg.norm(d)
    if d_norm < 1e-6 or abs(d[2]) < 1e-6:
        return (512.0, 512.0)

    d /= d_norm

    # 3D Ray-Terrain Elevation Surface Intersection
    gpu_renderer = world.get('_micropoly_gpu_renderer')
    sample_elev = getattr(gpu_renderer, 'sample_elevation_func', None)

    if sample_elev is not None and abs(d[2]) > 1e-4:
        slot_state = world.get('slot_state') or getattr(world.get('gen'), 'slot_1_state', None) or {}
        max_h = float(slot_state.get('height_scale', 48.0)) + 4.0
        t_top = (max_h - p_near[2]) / d[2]
        t_bot = (0.0 - p_near[2]) / d[2]
        t_lo = min(t_top, t_bot)
        t_hi = max(t_top, t_bot)

        # 8-step binary search along ray to find exact 3D surface intersection
        for _ in range(8):
            t_mid = 0.5 * (t_lo + t_hi)
            p_mid = p_near + d * t_mid
            z_surf = float(sample_elev(np.array([[p_mid[0], p_mid[1]]], dtype=np.float32))[0])
            if p_mid[2] > z_surf:
                t_lo = t_mid
            else:
                t_hi = t_mid
        hit = p_near + d * (0.5 * (t_lo + t_hi))
    else:
        t = -p_near[2] / d[2]
        hit = p_near + d * t

    return float(hit[0]), float(hit[1])


def clamp_cam(world):
    """Keep camera parameters strictly bounded; pitch and yaw tilt dynamically with zoom."""
    cam = world['cam']
    cam['zoom'] = max(0.5, min(6.0, float(cam.get('zoom', 1.0))))
    pitch, yaw = compute_pitch_yaw(cam['zoom'])
    cam['pitch'] = pitch
    cam['yaw'] = yaw
    cam['target_x'] = max(100.0, min(924.0, float(cam.get('target_x', 512.0))))
    cam['target_y'] = max(100.0, min(924.0, float(cam.get('target_y', 512.0))))


def zoom_cam_at(world, factor, mx, my):
    """Zoom camera anchored toward cursor; camera moves closer while tilting down smoothly."""
    cam = world['cam']
    old_zoom = cam.get('zoom', 1.0)
    new_zoom = max(0.5, min(6.0, old_zoom * factor))
    if abs(new_zoom - old_zoom) < 1e-4:
        return

    wx0, wy0 = screen_to_world(world, mx, my)
    cam['zoom'] = new_zoom
    pitch, yaw = compute_pitch_yaw(new_zoom)
    cam['pitch'] = pitch
    cam['yaw'] = yaw

    # Smoothly shift target towards the cursor world point
    ratio = 1.0 - 1.0 / factor
    cam['target_x'] = float(cam.get('target_x', 512.0) + (wx0 - cam.get('target_x', 512.0)) * ratio * 0.45)
    cam['target_y'] = float(cam.get('target_y', 512.0) + (wy0 - cam.get('target_y', 512.0)) * ratio * 0.45)
    clamp_cam(world)


def reset_cam(world):
    """Center the camera on the island with overview zoom and straight-down view."""
    cam = world['cam']
    cam['zoom'] = 1.0
    cam['pitch'], cam['yaw'] = compute_pitch_yaw(1.0)
    cam['target_x'] = 512.0
    cam['target_y'] = 512.0
    cam['ox'] = 0
    cam['oy'] = 0
    clamp_cam(world)


def hex_px(world, q, r, elevation=0.0):
    """Convert axial hex (q, r) or world (x, y) to screen pixel coordinates with 35mm perspective."""
    from world_config import is_voronoi_topology
    if is_voronoi_topology():
        return world_to_screen(world, q, r, elevation=elevation)
    x, y = axial_to_pixel(q, r, HEX_SIZE)
    return world_to_screen(world, x, y, elevation=elevation)


def tile_at(world, mx, my):
    """Return the Region under screen pixel (mx, my), or None, accounting for 3D perspective picking."""
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
