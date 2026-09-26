"""
render_voronoi_geopolitics.py — Native Voronoi Geopolitics & Macroeconomic Renderer for Mapgen2.

Renders:
- Organic Mapgen2 shaded relief base terrain (biomes, hillshading, hydrology).
- Semi-transparent sovereign nation territory washes with distinct national palettes.
- Multi-tier provincial administrative subdivisions with vibrant province highlights.
- Polygonal Voronoi cell boundaries.
- Overland trade routes, river corridors with animated flow, and unblocked mountain passes.
- Procedural natural resource deposits (Iron, Timber, Oil, Coal, Grain, etc.).
- Sovereign Capitals, Provincial Capitals, City labels, and elevation/population badges.
- Thematic choropleth layers (Overview, Nations, Provinces, Trade, Enclosure, Exploitation, Resources).
- Selected cell highlight and inspection marker.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple
import pygame

from goods import Goods
from region import Region
from nation import Nation
from polygon_map import PolygonMapGenerator
from tile_resources import TileResource, RESOURCE_META


NATION_COLORS: Dict[str, Tuple[int, int, int]] = {
    'United States': (75, 155, 245),
    'China':         (235, 75, 75),
    'Japan':         (240, 110, 160),
    'India':         (245, 155, 55),
    'Indonesia':     (230, 90, 120),
    'Brazil':        (75, 215, 135),
    'Mexico':        (55, 195, 165),
    'Nigeria':       (95, 215, 95),
    'Pakistan':      (65, 185, 125),
    'Bangladesh':    (75, 195, 115),
    'Russia':        (155, 135, 240),
}

PROVINCE_COLORS: List[Tuple[int, int, int]] = [
    (245, 190, 60),   # 1. Vibrant Gold / Amber
    (60, 215, 235),   # 2. Bright Cyan / Turquoise
    (245, 95, 155),   # 3. Vivid Coral / Magenta
    (110, 235, 130),  # 4. Emerald Green
    (175, 120, 245),  # 5. Electric Purple
    (245, 135, 45),   # 6. Tangerine Orange
    (80, 165, 245),   # 7. Sky Blue
    (230, 230, 90),   # 8. Bright Lime Yellow
]

RESOURCE_SHORT_NAMES = {
    TileResource.ARABLE_SILT: "Silt",
    TileResource.TIMBER: "Wood",
    TileResource.IRON_ORE: "Iron",
    TileResource.COAL_SEAM: "Coal",
    TileResource.PASTURE_FLAX: "Flax",
    TileResource.CRUDE_PETROLEUM: "Oil",
    TileResource.RARE_MINERALS: "Rare",
    TileResource.NATURAL_NITRATES: "Nitr",
}


def _draw_pill_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    cx: int,
    cy: int,
    text_color: Tuple[int, int, int] = (255, 255, 255),
    bg_color: Tuple[int, int, int, int] = (16, 20, 28, 200),
    border_color: Optional[Tuple[int, int, int, int]] = None,
    pad_x: int = 5,
    pad_y: int = 2,
):
    """Draw text with a rounded pill background for high contrast against terrain."""
    txt_surf = font.render(text, True, text_color)
    tw, th = txt_surf.get_size()
    pw, ph = tw + pad_x * 2, th + pad_y * 2
    px, py = cx - pw // 2, cy - ph // 2

    pill = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(pill, bg_color, (0, 0, pw, ph), border_radius=max(3, ph // 2))
    if border_color:
        pygame.draw.rect(pill, border_color, (0, 0, pw, ph), width=1, border_radius=max(3, ph // 2))
    pill.blit(txt_surf, (pad_x, pad_y))
    surface.blit(pill, (px, py))


def render_voronoi_geopolitics(
    gen: PolygonMapGenerator,
    tiles: List[Region],
    nations: List[Nation],
    width: int = 1024,
    height: int = 1024,
    layer_mode: str = 'overview',
    show_cities: bool = True,
    show_trade_routes: bool = True,
    show_provinces: bool = True,
    show_cell_outlines: bool = True,
    show_resources: bool = True,
    nation_alpha: float = 0.55,
    selected_cell_index: Optional[int] = None,
    frame: int = 0,
) -> pygame.Surface:
    """Render a complete, interactive Voronoi geopolitical map on a Pygame Surface."""
    pygame.font.init()
    font_title = pygame.font.Font(None, max(13, int(width * 0.016)))
    font_bold = pygame.font.Font(None, max(12, int(width * 0.014)))
    font_small = pygame.font.Font(None, max(11, int(width * 0.012)))
    font_tiny = pygame.font.Font(None, max(9, int(width * 0.010)))

    # 1. Base Mapgen2 Shaded Relief Terrain
    base_surf = gen.render_to_surface(
        width=width,
        height=height,
        use_brdf=True,
        use_noisy_edges=True,
        show_roads=False,
        show_lava=False,
        render_micropolys=False,
    )
    surface = pygame.Surface((width, height))
    surface.blit(base_surf, (0, 0))

    scale_x = width / float(gen.width)
    scale_y = height / float(gen.height)

    # Pre-map province highlight colors
    prov_color_map: Dict[str, Tuple[int, int, int]] = {}
    for nation in nations:
        for i, prov in enumerate(getattr(nation, 'provinces', [])):
            col = PROVINCE_COLORS[i % len(PROVINCE_COLORS)]
            prov_color_map[prov.name] = col
            for t in prov.tiles:
                prov_color_map[t.name] = col

    # 2. Semi-Transparent Territory & Thematic Choropleth Overlays
    tint_layer = pygame.Surface((width, height), pygame.SRCALPHA)
    outline_layer = pygame.Surface((width, height), pygame.SRCALPHA)

    tile_screen_geoms = []

    for tile in tiles:
        if not hasattr(tile, 'polygon') or len(tile.polygon) < 3:
            continue
        pts = [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in tile.polygon]
        cx = int(tile.centroid[0] * scale_x)
        cy = int(tile.centroid[1] * scale_y)
        tile_screen_geoms.append((tile, cx, cy, pts))

        # Skip water for geopolitical fills
        if getattr(tile, 'is_ocean', False):
            continue

        owner = getattr(tile, 'owner_nation', None)

        # 2a. Determine fill color based on active layer
        fill_color = None
        alpha_val = int(255 * max(0.1, min(0.9, nation_alpha)))

        if layer_mode == 'enclosure':
            # Land Tenure / Enclosure ratio
            enc = getattr(tile, 'enclosure_ratio', 0.0)
            fill_color = (
                int(40 + 200 * enc),
                int(160 * (1.0 - enc)),
                int(60 + 80 * enc),
                160
            )
        elif layer_mode == 'exploitation':
            # Exploitation / Strikes / Unrest
            unrest = getattr(tile, 'unrest_score', 0.0)
            fill_color = (
                int(220 * min(1.0, unrest)),
                int(60 + 100 * (1.0 - unrest)),
                int(70),
                170
            )
        elif layer_mode == 'provinces' and tile.name in prov_color_map:
            p_col = prov_color_map[tile.name]
            fill_color = (p_col[0], p_col[1], p_col[2], alpha_val)
        elif owner is not None:
            n_col = NATION_COLORS.get(owner.name, (180, 180, 180))
            fill_color = (n_col[0], n_col[1], n_col[2], alpha_val)

        if fill_color:
            pygame.draw.polygon(tint_layer, fill_color, pts)

        # 2b. Province Highlights (subtle accent borders)
        if show_provinces and tile.name in prov_color_map and owner is not None:
            p_col = prov_color_map[tile.name]
            pygame.draw.polygon(outline_layer, (p_col[0], p_col[1], p_col[2], 180), pts, max(2, int(2 * (width / 1024.0))))

        # 2c. Cell Outline
        if show_cell_outlines:
            pygame.draw.polygon(outline_layer, (255, 255, 255, 45), pts, 1)

    surface.blit(tint_layer, (0, 0))
    surface.blit(outline_layer, (0, 0))

    # 3. National Borders (bold outlines around sovereign territory)
    border_layer = pygame.Surface((width, height), pygame.SRCALPHA)
    for tile, cx, cy, pts in tile_screen_geoms:
        owner = getattr(tile, 'owner_nation', None)
        if owner is None:
            continue
        n_col = NATION_COLORS.get(owner.name, (255, 255, 255))
        border_col = (min(255, n_col[0] + 40), min(255, n_col[1] + 40), min(255, n_col[2] + 40), 230)
        pygame.draw.polygon(border_layer, border_col, pts, max(2, int(2.5 * (width / 1024.0))))

    surface.blit(border_layer, (0, 0))

    # 4. Overland Trade Routes & River Corridors
    if show_trade_routes or layer_mode == 'trade':
        seen_pairs: Set[Tuple[str, str]] = set()
        for tile in tiles:
            if getattr(tile, 'is_ocean', False):
                continue
            c1 = (int(tile.centroid[0] * scale_x), int(tile.centroid[1] * scale_y))

            for other in tile.neighbors.values():
                if getattr(other, 'is_ocean', False):
                    continue
                pair_key = tuple(sorted((tile.name, other.name)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                c2 = (int(other.centroid[0] * scale_x), int(other.centroid[1] * scale_y))
                is_river = getattr(tile, 'is_river_corridor', False) and getattr(other, 'is_river_corridor', False)

                if is_river:
                    # River Corridor (Cyan line with animated downstream droplet)
                    pygame.draw.line(surface, (40, 110, 200), c1, c2, max(2, int(3 * (width / 1024.0))))
                    pygame.draw.line(surface, (120, 215, 255), c1, c2, max(1, int(1.5 * (width / 1024.0))))

                    # Flow droplet
                    h1 = getattr(tile, 'elevation', 0.0)
                    h2 = getattr(other, 'elevation', 0.0)
                    start_p, end_p = (c1, c2) if h1 >= h2 else (c2, c1)
                    dx = end_p[0] - start_p[0]
                    dy = end_p[1] - start_p[1]
                    dist = max(1.0, math.hypot(dx, dy))
                    phase = ((frame * 1.5) % 40) / 40.0
                    drop_x = int(start_p[0] + (dx / dist) * dist * phase)
                    drop_y = int(start_p[1] + (dy / dist) * dist * phase)
                    pygame.draw.circle(surface, (210, 245, 255), (drop_x, drop_y), max(2, int(2.5 * (width / 1024.0))))
                else:
                    # Overland Trade Route
                    pygame.draw.line(surface, (60, 160, 210, 160), c1, c2, max(1, int(1.5 * (width / 1024.0))))

                    # Mountain pass notch if high elevation delta
                    dh = abs(getattr(tile, 'elevation', 0.0) - getattr(other, 'elevation', 0.0))
                    if dh > 0.35:
                        mx = (c1[0] + c2[0]) // 2
                        my = (c1[1] + c2[1]) // 2
                        pygame.draw.circle(surface, (255, 220, 90), (mx, my), 3)

    # 5. Natural Resource Badges
    if show_resources or layer_mode == 'resources':
        for tile, cx, cy, pts in tile_screen_geoms:
            if getattr(tile, 'is_ocean', False):
                continue
            res_set = getattr(tile, 'natural_resources', None)
            if not res_set:
                continue

            res_list = list(res_set)[:2]  # Show up to 2 primary resources
            for idx, res in enumerate(res_list):
                meta = RESOURCE_META.get(res)
                if not meta:
                    continue
                label = RESOURCE_SHORT_NAMES.get(res, meta.name[:4])
                rx = cx + (idx * 30 - 15 if len(res_list) > 1 else 0)
                ry = cy + (18 if show_cities else 0)
                _draw_pill_text(
                    surface, font_tiny, label, rx, ry,
                    text_color=(250, 250, 250),
                    bg_color=(meta.color[0] // 3, meta.color[1] // 3, meta.color[2] // 3, 210),
                    border_color=(meta.color[0], meta.color[1], meta.color[2], 220),
                    pad_x=4, pad_y=1
                )

    # 6. Cities, Capitals & Labels
    if show_cities:
        for tile, cx, cy, pts in tile_screen_geoms:
            if getattr(tile, 'is_ocean', False):
                continue

            city_name = getattr(tile, 'display_name', getattr(tile, 'city_name', tile.name))
            owner = getattr(tile, 'owner_nation', None)
            is_nat_cap = getattr(tile, 'is_national_capital', False) or (owner and owner.tiles and tile == owner.tiles[0])
            is_prov_cap = getattr(tile, 'is_provincial_capital', False)

            if is_nat_cap:
                # Sovereign Capital: Gold crown / star
                label = f"★ {city_name}"
                _draw_pill_text(
                    surface, font_title, label, cx, cy - 8,
                    text_color=(255, 240, 160),
                    bg_color=(35, 25, 10, 225),
                    border_color=(245, 210, 95, 240),
                    pad_x=6, pad_y=2
                )
                if owner:
                    nat_title = owner.name.upper()
                    _draw_pill_text(
                        surface, font_tiny, nat_title, cx, cy - 24,
                        text_color=(220, 230, 250),
                        bg_color=(15, 20, 30, 190),
                        pad_x=4, pad_y=1
                    )
            elif is_prov_cap:
                # Provincial Capital: Cyan diamond / plus
                label = f"◆ {city_name}"
                _draw_pill_text(
                    surface, font_bold, label, cx, cy - 6,
                    text_color=(210, 245, 255),
                    bg_color=(12, 28, 42, 210),
                    border_color=(60, 200, 230, 200),
                    pad_x=5, pad_y=2
                )
            else:
                # Regular City / Settlement
                _draw_pill_text(
                    surface, font_small, city_name, cx, cy - 4,
                    text_color=(245, 245, 250),
                    bg_color=(15, 18, 25, 185),
                    pad_x=4, pad_y=1
                )

            # Subtitle: Elevation and Population
            elev_m = getattr(tile, 'elevation_meters', int(tile.elevation * 3000))
            pop = len(tile.agents) if getattr(tile, 'agents', None) else getattr(tile, 'wilderness_pop', 0)
            if pop > 0:
                sub_text = f"▲{elev_m}m · {pop}p"
                _draw_pill_text(
                    surface, font_tiny, sub_text, cx, cy + 9,
                    text_color=(175, 190, 210),
                    bg_color=(10, 14, 20, 170),
                    pad_x=3, pad_y=1
                )

    # 7. Selected Cell Highlight
    if selected_cell_index is not None:
        for tile, cx, cy, pts in tile_screen_geoms:
            c_idx = getattr(getattr(tile, 'center', None), 'index', None)
            if c_idx == selected_cell_index:
                # Pulsing selection ring & glowing polygon outline
                sel_layer = pygame.Surface((width, height), pygame.SRCALPHA)
                pygame.draw.polygon(sel_layer, (255, 255, 255, 100), pts)
                pygame.draw.polygon(sel_layer, (255, 230, 80, 255), pts, max(3, int(3.5 * (width / 1024.0))))
                pygame.draw.circle(sel_layer, (255, 255, 255, 255), (cx, cy), 6)
                pygame.draw.circle(sel_layer, (255, 220, 60, 255), (cx, cy), 10, 2)
                surface.blit(sel_layer, (0, 0))
                break

    return surface
