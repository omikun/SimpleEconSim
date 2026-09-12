"""
render_engine/hex_renderer.py — Vector hex cell rendering, borders, highlights, and badges.
"""

import math
import pygame
from hexmap import hex_corners
from render_engine.camera import Camera, HEX_SIZE

# Default nation palette for vector border highlights
NATION_COLORS = {
    'United States': (80, 160, 240),
    'China':         (235, 80, 80),
    'India':         (245, 160, 60),
    'Indonesia':     (230, 90, 120),
    'Brazil':        (80, 220, 140),
    'Mexico':        (60, 200, 170),
    'Nigeria':       (100, 220, 100),
    'Pakistan':      (70, 190, 130),
    'Bangladesh':    (80, 200, 120),
    'Russia':        (160, 140, 240),
    'Alpha':         (141, 211, 199),
    'Beta':          (255, 255, 179),
    'Gamma':         (190, 186, 218),
}

PROVINCE_COLORS = [
    (245, 190, 60),   # 1. Vibrant Gold / Amber
    (60, 210, 230),   # 2. Bright Cyan / Turquoise
    (240, 95, 155),   # 3. Vivid Coral / Magenta
    (110, 235, 130),  # 4. Emerald Green
    (175, 120, 245),  # 5. Electric Purple
    (245, 130, 45),   # 6. Tangerine Orange
    (80, 160, 245),   # 7. Sky Blue
    (230, 230, 90),   # 8. Bright Lime Yellow
]


class HexRenderer:
    """Renders vector hex overlays: outlines, nation borders, highlights, badges, and labels."""

    def __init__(self, font=None, font_small=None):
        self.font = font
        self.font_small = font_small

    def set_fonts(self, font, font_small):
        self.font = font
        self.font_small = font_small

    def compute_hex_corners(self, camera: Camera, q, r, hex_size=HEX_SIZE):
        cx, cy = camera.hex_to_screen(q, r, hex_size)
        pts = hex_corners((cx, cy), hex_size * camera.zoom - 1)
        return cx, cy, pts

    def draw_grid_lines(self, surface, hex_geometries, color=(255, 255, 255, 128), width=1):
        """Draw semi-transparent hex grid cell boundaries."""
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for _, _, _, pts in hex_geometries:
            pygame.draw.polygon(overlay, color, pts, width)
        surface.blit(overlay, (0, 0))

    def draw_nation_borders(self, surface, hex_geometries, camera: Camera):
        """Draw colored national boundaries around hex cells."""
        border_w = max(2, int(2 * camera.zoom))
        for item, _, _, pts in hex_geometries:
            owner = getattr(item, 'owner_nation', None)
            owner_name = getattr(owner, 'name', None) if owner else None
            if not owner_name and isinstance(item, dict):
                owner_name = item.get('owner_nation_name')
            if owner_name:
                col = NATION_COLORS.get(owner_name, (200, 200, 200))
                pygame.draw.polygon(surface, col, pts, border_w)

    def draw_selection(self, surface, hex_geometries, selected_name, hover_name=None):
        """Draw prominent selection and hover rings on the active hex."""
        for item, _, _, pts in hex_geometries:
            name = getattr(item, 'name', None) or (item.get('name') if isinstance(item, dict) else None)
            if name == hover_name and name != selected_name:
                pygame.draw.polygon(surface, (255, 255, 180), pts, 2)
            if name == selected_name:
                pygame.draw.polygon(surface, (255, 255, 255), pts, 4)

    def draw_labels(self, surface, hex_geometries, camera: Camera, show_elevation=True):
        """Draw city / tile names and elevation badges."""
        if not self.font or not self.font_small:
            return

        for item, cx, cy, _ in hex_geometries:
            is_ocean = getattr(item, 'is_ocean', False)
            if isinstance(item, dict):
                is_ocean = item.get('is_ocean', False)

            if is_ocean:
                continue

            name = getattr(item, 'display_name', getattr(item, 'name', ''))
            if isinstance(item, dict):
                name = item.get('display_name', item.get('name', ''))

            elev_m = getattr(item, 'elevation_meters', None)
            if isinstance(item, dict) and elev_m is None:
                elev_m = item.get('elevation_meters', 0)

            # Draw tile title
            f = self.font_small if len(name) > 10 else self.font
            txt = f.render(name, True, (245, 245, 250))
            sh = f.render(name, True, (10, 10, 15))
            tx = cx - txt.get_width() // 2
            ty = cy - txt.get_height() // 2
            surface.blit(sh, (tx + 1, ty + 1))
            surface.blit(txt, (tx, ty))

            # Optional elevation badge below name
            if show_elevation and elev_m is not None and camera.zoom >= 0.8:
                el_str = f"▲ {int(elev_m)}m" if elev_m >= 0 else f"≈ {int(elev_m)}m"
                el_txt = self.font_small.render(el_str, True, (200, 210, 220))
                el_sh = self.font_small.render(el_str, True, (10, 10, 15))
                ex = cx - el_txt.get_width() // 2
                ey = ty + txt.get_height() + 2
                surface.blit(el_sh, (ex + 1, ey + 1))
                surface.blit(el_txt, (ex, ey))
