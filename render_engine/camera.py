"""
render_engine/camera.py — Camera and coordinate transformations for the rendering engine.
"""

from hexmap import axial_to_pixel, pixel_to_axial

HEX_SIZE = 50
WIDTH, HEIGHT = 1400, 900
MAP_RIGHT = 1060
TOP_BAR_H = 52
TICKER_H = 64
MAP_PAD_RATIO = 0.18


class Camera:
    """Manages viewport pan and zoom with strict bounds clamping."""

    def __init__(self, bbox=None, vw=None, vh=None, v_x0=0, v_y0=None,
                 width=WIDTH, height=HEIGHT, map_right=MAP_RIGHT,
                 top_bar_h=TOP_BAR_H, ticker_h=TICKER_H):
        self.ox = 0.0
        self.oy = 0.0
        self.zoom = 1.0
        self.bbox = bbox if bbox is not None else (-400, -300, 400, 300)

        if vw is None:
            vw = map_right
        if v_y0 is None:
            v_y0 = top_bar_h
        if vh is None:
            vh = height - top_bar_h - ticker_h

        self.vw = vw
        self.vh = vh
        self.v_x0 = v_x0
        self.v_y0 = v_y0
        self.v_x1 = v_x0 + vw
        self.v_y1 = v_y0 + vh
        self.min_zoom_floor = 0.25
        self.max_zoom_ceil = 4.0
        self.reset()

    def set_bbox(self, bbox):
        self.bbox = bbox
        self.clamp()

    def get_map_bounds(self):
        x0, y0, x1, y1 = self.bbox
        pad_x = (x1 - x0) * MAP_PAD_RATIO
        pad_y = (y1 - y0) * MAP_PAD_RATIO
        return (x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y)

    def get_min_zoom(self):
        min_wx, min_wy, max_wx, max_wy = self.get_map_bounds()
        world_w = max(1.0, max_wx - min_wx)
        world_h = max(1.0, max_wy - min_wy)
        return max(self.vw / world_w, self.vh / world_h)

    def clamp(self):
        min_zoom = self.get_min_zoom()
        if self.zoom < min_zoom:
            self.zoom = min_zoom

        min_wx, min_wy, max_wx, max_wy = self.get_map_bounds()

        max_ox = self.v_x0 - min_wx * self.zoom
        min_ox = self.v_x1 - max_wx * self.zoom
        if min_ox > max_ox:
            self.ox = (self.v_x0 + self.v_x1) / 2.0 - ((min_wx + max_wx) / 2.0) * self.zoom
        else:
            self.ox = max(min_ox, min(max_ox, self.ox))

        max_oy = self.v_y0 - min_wy * self.zoom
        min_oy = self.v_y1 - max_wy * self.zoom
        if min_oy > max_oy:
            self.oy = (self.v_y0 + self.v_y1) / 2.0 - ((min_wy + max_wy) / 2.0) * self.zoom
        else:
            self.oy = max(min_oy, min(max_oy, self.oy))

    def zoom_at(self, factor, mx, my):
        old_zoom = self.zoom
        min_z = self.get_min_zoom()
        new_zoom = max(min_z, min(self.max_zoom_ceil, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-6:
            return
        ratio = new_zoom / old_zoom
        self.ox = mx - (mx - self.ox) * ratio
        self.oy = my - (my - self.oy) * ratio
        self.zoom = new_zoom
        self.clamp()

    def reset(self):
        min_wx, min_wy, max_wx, max_wy = self.get_map_bounds()
        fit_zoom = self.get_min_zoom()
        self.zoom = fit_zoom

        target_cx = self.v_x0 + self.vw / 2.0
        target_cy = self.v_y0 + self.vh / 2.0
        self.ox = target_cx - ((min_wx + max_wx) / 2.0) * fit_zoom
        self.oy = target_cy - ((min_wy + max_wy) / 2.0) * fit_zoom
        self.clamp()

    def world_to_screen(self, wx, wy):
        return (int(wx * self.zoom + self.ox), int(wy * self.zoom + self.oy))

    def screen_to_world(self, sx, sy):
        return ((sx - self.ox) / self.zoom, (sy - self.oy) / self.zoom)

    def hex_to_screen(self, q, r, hex_size=HEX_SIZE):
        x, y = axial_to_pixel(q, r, hex_size * self.zoom)
        return (int(x + self.ox), int(y + self.oy))

    def screen_to_hex(self, sx, sy, hex_size=HEX_SIZE):
        if sx >= self.v_x1 or sy < self.v_y0 or sy > self.v_y1:
            return None
        wx, wy = self.screen_to_world(sx, sy)
        return pixel_to_axial(wx, wy, hex_size)

    def sync_to_dict(self, cam_dict):
        """Export state into legacy world['cam'] dict."""
        cam_dict['ox'] = self.ox
        cam_dict['oy'] = self.oy
        cam_dict['zoom'] = self.zoom

    def sync_from_dict(self, cam_dict):
        """Import state from legacy world['cam'] dict."""
        self.ox = cam_dict.get('ox', self.ox)
        self.oy = cam_dict.get('oy', self.oy)
        self.zoom = cam_dict.get('zoom', self.zoom)
