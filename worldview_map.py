"""
worldview_map.py — Realistic Topographic Elevation Hex Map Rendering for REGNUM.

Renders realistic procedural terrain heightmaps with:
- Deep & Shallow Ocean with water ripples and depth colormaps
- Coastal Lowlands & Plains
- Highland Forests & Steppes with tree canopy clusters
- Rolling Hills with topographic contour lines
- Shaded Relief Rocky Mountain Ranges
- Glacial Snow-Capped Alpine Summits
- Translucent Nation & Multi-Province Territory Highlighting (elevation peeks through below UI text)
- Crisp Text Rendering with altitude badges (e.g. ▲ 1,840m, ≈ -450m)
"""

import math
import pygame
from goods import Goods
from hexmap import hex_corners
from worldview_camera import hex_px, HEX_SIZE

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

# Palette of distinct, vibrant highlight colors for each province of a selected nation
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

WILD_COLOR = (70, 75, 80)
WILD_EDGE = (45, 50, 58)
HEX_EDGE = (24, 24, 30)
TEXT = (245, 245, 250)
DIM = (185, 190, 200)
RED = (235, 90, 90)
GREEN = (120, 220, 130)
ACCENT = (245, 210, 95)
EDGE_LINE = (58, 58, 68)

BADGE_ORANGE = (240, 150, 60)
BADGE_RED = (235, 70, 70)
BADGE_TRA = (90, 210, 120)
BADGE_GINI = (190, 110, 230)
HOT_RING = (235, 120, 60)
COLD_RING = (110, 170, 235)

UNREST_COLORS = {
    'unrest': (230, 170, 60),
    'protest': (240, 140, 40),
    'mob': (235, 70, 70),
    'compromise': (160, 230, 90),
    'takeover': (180, 100, 230),
}

# Keeps track of last-turn population per region name for delta badges.
pops_history = {}


def nation_color(region):
    owner = getattr(region, 'owner_nation', None)
    if owner is not None:
        return NATION_COLORS.get(owner.name, (150, 150, 150))
    return WILD_COLOR


def region_pop(region):
    if region.total_population:
        return region.total_population[-1]
    return len(region.agents)


def homesteaders(region):
    return sum(1 for a in region.agents if getattr(a, 'is_homesteader', False))


def tile_stats(region, layer_mode='overview', world=None):
    """Summary lines and colors printed on each hex based on active map layer mode."""
    elev = getattr(region, 'elevation_meters', 0)
    biome = getattr(region, 'biome', 'plains')
    is_ocean = getattr(region, 'is_ocean', False) or elev < 0
    owner = getattr(region, 'owner_nation', None)
    pop = region_pop(region)

    # 1. PHYSICAL & HEIGHT LAYER
    if layer_mode == 'physical':
        if is_ocean:
            return f"≈ {elev:,}m", "Ocean Basin", "No Land Yield", (140, 225, 255), (100, 180, 240), DIM
        b_name = biome.replace('_', ' ').title()
        b_bonuses = []
        if region.terrain.get(Goods.food, 1.0) > 1.1:
            b_bonuses.append(f"Fd +{int((region.terrain[Goods.food]-1.0)*100)}%")
        if region.terrain.get(Goods.wood, 1.0) > 1.1:
            b_bonuses.append(f"Wd +{int((region.terrain[Goods.wood]-1.0)*100)}%")
        bonus_str = " ".join(b_bonuses) if b_bonuses else "Standard Yield"
        clim = "Cold (1.2x)" if getattr(region, 'climate', '') == 'cold' else "Temperate"
        return f"▲ {elev:,}m", b_name, f"{bonus_str} | {clim}", (255, 240, 180), ACCENT, DIM

    # 2. POPULATION & UNREST LAYER
    if layer_mode == 'population':
        if is_ocean:
            return "Pop: 0", "Uninhabited", "Ocean Basin", DIM, DIM, DIM
        if owner is None:
            hs = homesteaders(region)
            wild = getattr(region, 'wilderness_pop', 0)
            return f"HS Pop: {hs}", f"Natives: {wild}", "Wilderness", ACCENT, TEXT, DIM
        hungry_cnt = 0
        for g in (Goods.food, Goods.wood, Goods.furniture):
            if g in region.hungry_log and region.hungry_log[g]:
                hungry_cnt = max(hungry_cnt, region.hungry_log[g][-1])
        h_color = RED if hungry_cnt > 5 else (ACCENT if hungry_cnt > 0 else GREEN)
        unrest = region.unrest_log[-1] if region.unrest_log else {}
        stage = unrest.get('stage', 'calm').upper()
        u_col = UNREST_COLORS.get(stage.lower(), GREEN if stage == 'CALM' else ACCENT)
        return f"Pop: {pop}", f"Hungry: {hungry_cnt}", f"Order: {stage}", TEXT, h_color, u_col

    # 3. ECONOMY & WEALTH LAYER
    if layer_mode == 'economy':
        if is_ocean or owner is None:
            return "GDP: $0", "Wilderness", "No Banking", DIM, DIM, DIM
        # Nominal GDP approximation (food + wood + furniture revenue)
        gdp = 0.0
        for g in (Goods.food, Goods.wood, Goods.furniture):
            out_qty = region.production_log[g][-1] if (g in region.production_log and region.production_log[g]) else 0
            pr = region.recipes.get(g, {}).get('price', 1.0)
            gdp += out_qty * pr
        food_p = region.recipes.get(Goods.food, {}).get('price', 1.0)
        wood_p = region.recipes.get(Goods.wood, {}).get('price', 1.0)
        dep = region.bank.deposits_total() if hasattr(region, 'bank') and hasattr(region.bank, 'deposits_total') else sum(region.bank.deposits.values()) if hasattr(region, 'bank') else 0.0
        return f"GDP: ${gdp:,.0f}", f"Fd ${food_p:.1f}  Wd ${wood_p:.1f}", f"Bank: ${dep:,.0f}", GREEN, ACCENT, TEXT

    # 4. PRODUCTION & OUTPUT LAYER
    if layer_mode == 'production':
        if is_ocean:
            return "Output: None", "Ocean Basin", "--", DIM, DIM, DIM
        if owner is None:
            return "Wilderness", "Forage Only", "--", DIM, DIM, DIM
        fd_out = region.production_log[Goods.food][-1] if (Goods.food in region.production_log and region.production_log[Goods.food]) else 0
        wd_out = region.production_log[Goods.wood][-1] if (Goods.wood in region.production_log and region.production_log[Goods.wood]) else 0
        blds = getattr(region, 'buildings', [])
        b_summary = f"Bld: {len(blds)} Active" if blds else "Bld: None"
        workers = sum(1 for a in region.agents if getattr(a, 'output', Goods.none) != Goods.none)
        return f"Fd: {fd_out}  Wd: {wd_out}", b_summary, f"Labor: {workers}/{pop}", ACCENT, GREEN if blds else DIM, TEXT

    # 5. MILITARY & DEFENSE LAYER
    if layer_mode == 'military':
        if is_ocean:
            return "No Garrison", "Ocean Basin", "Naval Zone", DIM, DIM, DIM
        # Find units stationed in this region
        nations = world.get('nations', []) if world else []
        stationed_units = []
        for n in nations:
            for u in getattr(n, 'military_units', []):
                if u.region_name == region.name:
                    stationed_units.append(u)
        if stationed_units:
            tot_soldiers = sum(u.soldiers for u in stationed_units)
            tot_str = sum(u.strength for u in stationed_units)
            avg_xp = sum(u.veteran_xp for u in stationed_units) / len(stationed_units)
            return f"⚔ {tot_soldiers} Troops", f"Strength: {tot_str:.1f}", f"XP: {avg_xp:.2f}", RED, ACCENT, GREEN
        else:
            threat_str = "Border: Guarded" if owner else "Wilderness"
            return "No Garrison", threat_str, "Vulnerability: High" if owner else "--", DIM, ACCENT if owner else DIM, RED if owner else DIM

    # 6. OVERVIEW LAYER (Default)
    city_name = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
    if owner is None:
        if is_ocean:
            return "Open Sea (Ocean)", "Ocean Basin", "", (140, 225, 255), DIM, DIM
        hs = homesteaders(region)
        wild = getattr(region, 'wilderness_pop', 0)
        return "Wild Frontier (Unclaimed)", f"hs {hs}+{wild}n", "", DIM, TEXT, DIM

    # Claimed tile: Province & Nation overlay
    prov = next((p for p in getattr(owner, 'provinces', []) if region in p.tiles), None)
    prov_name = getattr(prov, 'display_name', prov.name) if prov else getattr(region, 'province_display', 'Core')
    n_col = NATION_COLORS.get(owner.name, ACCENT)
    prov_nation_str = f"{prov_name} ({owner.name})"

    food = region.recipes[Goods.food]['price'] if hasattr(region, 'recipes') and Goods.food in region.recipes else 1.0
    traders = sum(1 for a in region.agents if getattr(a, 'is_trader', False))
    return prov_nation_str, f"pop {pop}  fd ${food:.1f}", f"tr {traders}" if traders > 0 else "", n_col, TEXT, DIM


def draw_elevation_terrain(surface, region, pts, cx, cy, zoom=1.0, frame=0):
    """Draw realistic shaded-relief elevation terrain with ocean, hills, and mountain vectors."""
    # 1. Base terrain color (incorporates continuous elevation and shaded relief hillshading)
    base_color = getattr(region, 'terrain_color', (65, 135, 75))
    pygame.draw.polygon(surface, base_color, pts)

    biome = getattr(region, 'biome', 'plains')
    elev = getattr(region, 'elevation', 0.0)

    # 2. Ocean Waves and Water Depth Shimmer (< 0.0)
    if elev < 0.0 or biome in ('deep_ocean', 'shallow_ocean'):
        wave_color = (65, 140, 190, 80) if biome == 'shallow_ocean' else (35, 80, 140, 60)
        # Draw subtle wave lines
        for dy in (-18, 0, 18):
            wy = cy + int(dy * zoom)
            wx1 = cx - int(24 * zoom)
            wx2 = cx + int(24 * zoom)
            phase = math.sin(frame * 0.08 + cx * 0.05 + dy) * 3 * zoom
            pygame.draw.line(surface, wave_color[:3], (wx1, wy + int(phase)), (wx2, wy + int(phase)), 1)
        return

    # 3. Mountain Ranges and Snow-Capped Summits (>= 0.70)
    if biome in ('mountains', 'snow_peaks') or elev >= 0.70:
        is_snow = (biome == 'snow_peaks' or elev >= 0.88)
        
        # Central Mountain Peak Polygon
        peak_top = (cx, cy - int(38 * zoom))
        peak_left = (cx - int(28 * zoom), cy + int(10 * zoom))
        peak_right = (cx + int(28 * zoom), cy + int(10 * zoom))
        peak_mid = (cx + int(2 * zoom), cy + int(12 * zoom))

        # Northwest Sunlit Face
        sunlit_col = (195, 195, 205) if is_snow else (160, 155, 165)
        pygame.draw.polygon(surface, sunlit_col, [peak_top, peak_left, peak_mid])

        # Southeast Shadowed Face
        shadow_col = (135, 135, 150) if is_snow else (95, 90, 100)
        pygame.draw.polygon(surface, shadow_col, [peak_top, peak_mid, peak_right])

        # Snow Cap
        if is_snow:
            snow_mid = (cx, cy - int(22 * zoom))
            snow_left = (cx - int(12 * zoom), cy - int(18 * zoom))
            snow_right = (cx + int(12 * zoom), cy - int(18 * zoom))
            pygame.draw.polygon(surface, (248, 252, 255), [peak_top, snow_left, snow_mid, snow_right])

        # Secondary Mountain Ridge
        sec_top = (cx + int(16 * zoom), cy - int(26 * zoom))
        sec_left = (cx + int(2 * zoom), cy + int(6 * zoom))
        sec_right = (cx + int(32 * zoom), cy + int(6 * zoom))
        pygame.draw.polygon(surface, (150, 145, 155), [sec_top, sec_left, sec_right])
        return

    # 4. Rolling Hills & Plateaus (0.45 to 0.70)
    if biome == 'hills' or 0.45 <= elev < 0.70:
        hill_sun = (155, 142, 102)
        hill_shadow = (115, 102, 75)
        # Two overlapping gentle rounded hill silhouettes
        h1_center = (cx - int(10 * zoom), cy - int(6 * zoom))
        pygame.draw.arc(surface, hill_sun, (h1_center[0] - int(20*zoom), h1_center[1] - int(14*zoom), int(40*zoom), int(28*zoom)), 0.2, 2.9, 2)
        h2_center = (cx + int(12 * zoom), cy - int(2 * zoom))
        pygame.draw.arc(surface, hill_shadow, (h2_center[0] - int(18*zoom), h2_center[1] - int(12*zoom), int(36*zoom), int(24*zoom)), 0.2, 2.9, 2)
        return

    # 5. Highland Forests (0.20 to 0.45)
    if biome == 'forest' or 0.20 <= elev < 0.45:
        tree_color = (38, 85, 45)
        # Draw small vector evergreen tree clusters
        for ox, oy in [(-14, -8), (0, -14), (14, -6), (-6, 4), (8, 6)]:
            tx = cx + int(ox * zoom)
            ty = cy + int(oy * zoom)
            t_pts = [(tx, ty - int(8*zoom)), (tx - int(5*zoom), ty + int(4*zoom)), (tx + int(5*zoom), ty + int(4*zoom))]
            pygame.draw.polygon(surface, tree_color, t_pts)


def draw_nation_overlay(surface, region, pts):
    """Draw semi-transparent nation territory tint so realistic elevation peeks through."""
    owner = getattr(region, 'owner_nation', None)
    if owner is None:
        return

    col = NATION_COLORS.get(owner.name, (180, 180, 180))
    # Population brightness factor
    pop = region_pop(region)
    f = min(0.35, 0.15 * (pop / 400.0))
    extra = int(40 * f)

    # Semi-transparent overlay surface
    # Calculate bounding box of polygon points
    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)
    w = max(1, int(max_x - min_x) + 2)
    h = max(1, int(max_y - min_y) + 2)

    tint_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    local_pts = [(p[0] - min_x, p[1] - min_y) for p in pts]
    
    # Soft nation alpha wash (alpha = 55)
    tint_color = (min(255, col[0] + extra), min(255, col[1] + extra), min(255, col[2] + extra), 60)
    pygame.draw.polygon(tint_surf, tint_color, local_pts)
    surface.blit(tint_surf, (min_x, min_y))


def draw_pop_heat(surface, region, pts, cx, cy, zoom=1.0, frame=0):
    """Draw elevation terrain and nation overlay for a hex."""
    draw_elevation_terrain(surface, region, pts, cx, cy, zoom=zoom, frame=frame)
    draw_nation_overlay(surface, region, pts)


def draw_terrain_glyph(surface, region, cx, cy):
    """Small vector resource markers for high-yield food/wood/cold tiles."""
    y = cy + 26
    if region.terrain.get(Goods.food, 1.0) > 1.3:
        pts = [(cx - 10, y - 6), (cx - 16, y + 4), (cx - 4, y + 4)]
        pygame.draw.polygon(surface, (240, 200, 90), pts)
    if region.terrain.get(Goods.wood, 1.0) > 1.3:
        pts = [(cx + 10, y - 6), (cx + 4, y + 4), (cx + 16, y + 4)]
        pygame.draw.polygon(surface, (110, 205, 110), pts)
    if getattr(region, 'climate', '') == 'cold':
        pygame.draw.circle(surface, (230, 242, 255), (cx, y), 3)


def trade_anim(world):
    """Animated arrows: last-turn net trade flow on claimed pairs."""
    out = []
    for r, other in world['pair_orders']:
        flow = r.trade_flow_log[-1] if r.trade_flow_log else 0.0
        if abs(flow) < 0.5:
            continue
        c1 = hex_px(world, *world['layout'][r.name])
        c2 = hex_px(world, *world['layout'][other.name])
        width = max(1, min(8, int(abs(flow) / 1500.0) + 1))
        out.append((c1, c2, width, flow > 0))
    return out


def draw_edges(surface, world):
    """Static thin strokes on every wired edge (connectivity overlay)."""
    for r, other in world['pair_orders']:
        c1 = hex_px(world, *world['layout'][r.name])
        c2 = hex_px(world, *world['layout'][other.name])
        pygame.draw.line(surface, EDGE_LINE, c1, c2, 1)
    for r in world['tiles']:
        if getattr(r, 'owner_nation', None) is not None:
            continue
        for other in r.neighbors.values():
            if other.name < r.name:
                continue
            c1 = hex_px(world, *world['layout'][r.name])
            c2 = hex_px(world, *world['layout'][other.name])
            pygame.draw.line(surface, (40, 40, 48), c1, c2, 1)


def draw_trade_arrows(surface, world):
    """Animated dots on claimed-pair edges scaled by recent net flow."""
    frame = world.get('frame', 0)
    for c1, c2, width, forward in trade_anim(world):
        (x1, y1), (x2, y2) = c1, c2
        dx, dy = x2 - x1, y2 - y1
        length = max(1, int((dx * dx + dy * dy) ** 0.5))
        ux, uy = dx / length, dy / length
        if not forward:
            x1, y1, x2, y2 = x2, y2, x1, y1
        phase = (frame // 2) % 12
        off = phase - 6
        mx = int(x1 + ux * (length / 2 + off * 2))
        my = int(y1 + uy * (length / 2 + off * 2))
        pygame.draw.line(surface, (80, 190, 220), (x1, y1), (x2, y2), width)
        pygame.draw.circle(surface, (180, 230, 245), (mx, my), 3)


def draw_activity_badges(surface, region, cx, cy, font_small):
    """Small indicators around the hex (claimed-only readouts)."""
    if getattr(region, 'owner_nation', None) is None:
        if getattr(region, 'elevation', 0.0) >= 0.0:
            pygame.draw.circle(surface, (90, 210, 120), (cx, cy - 46), 7)
            tag = font_small.render("W", True, (255, 255, 255))
            surface.blit(tag, tag.get_rect(center=(cx, cy - 46)))
        if homesteaders(region) > 0:
            pygame.draw.circle(surface, BADGE_ORANGE, (cx + 30, cy - 34), 6)
        return
    food = region.recipes[Goods.food]['price'] if hasattr(region, 'recipes') and Goods.food in region.recipes else 1.0
    neighbors = [n for n in region.neighbors.values()
                 if getattr(n, 'recipes', None) and not getattr(n, 'wilderness', False)]
    if neighbors:
        avg = sum(n.recipes[Goods.food]['price'] for n in neighbors if Goods.food in n.recipes) / max(1, len(neighbors))
        ring_color = HOT_RING if food > avg * 1.15 else \
                     COLD_RING if food < avg * 0.85 else None
        if ring_color is not None:
            pygame.draw.circle(surface, ring_color, (cx, cy), HEX_SIZE - 8, 2)
    dr = region.demand_ratio_log.get(Goods.food, [])
    if dr and dr[-1] > 1.5:
        pygame.draw.circle(surface, BADGE_ORANGE, (cx + 30, cy - 34), 6)
    if any(region.hungry_log[g] and region.hungry_log[g][-1] > 5
           for g in (Goods.food, Goods.wood, Goods.furniture) if g in region.hungry_log):
        pygame.draw.circle(surface, BADGE_RED, (cx - 30, cy - 34), 6)
    traders = sum(1 for a in region.agents if getattr(a, 'is_trader', False))
    if traders > 0:
        tag = font_small.render(f"T{traders}", True, BADGE_TRA)
        surface.blit(tag, (cx + 22, cy + 28))
    unrest = region.unrest_log[-1] if region.unrest_log else {}
    stage = unrest.get('stage', 'calm')
    if stage != 'calm' and stage in UNREST_COLORS:
        pygame.draw.circle(surface, UNREST_COLORS[stage], (cx, cy - 46), 7)
        tag = font_small.render(stage[0].upper(), True, (255, 255, 255))
        surface.blit(tag, tag.get_rect(center=(cx, cy - 46)))


def draw_pop_delta(surface, region, cx, cy, font_small):
    """+B / -D per-turn population delta badge under the hex name."""
    if getattr(region, 'owner_nation', None) is None:
        return
    if not region.total_population or len(region.total_population) < 2:
        return
    prev = pops_history.get(region.name)
    cur = region.total_population[-1]
    if prev is None:
        pops_history[region.name] = cur
        return
    delta = cur - prev
    pops_history[region.name] = cur
    txt = font_small.render(f"+{delta}" if delta >= 0 else f"{delta}",
                            True, GREEN if delta >= 0 else RED)
    surface.blit(txt, txt.get_rect(center=(cx, cy - 36)))


def draw_text_with_shadow(surface, font, text, center, color, shadow_color=(12, 12, 16)):
    """Render text with a soft drop shadow for ultra-crisp readability over elevation terrain."""
    cx, cy = center
    # 4-direction shadow
    for sx, sy in [(cx-1, cy), (cx+1, cy), (cx, cy-1), (cx, cy+1)]:
        s_surf = font.render(text, True, shadow_color)
        surface.blit(s_surf, s_surf.get_rect(center=(sx, sy)))
    t_surf = font.render(text, True, color)
    surface.blit(t_surf, t_surf.get_rect(center=(cx, cy)))


def province_members(world, region):
    """Tiles in the same province as *region* (or just the tile if none)."""
    prov = getattr(region, 'province', None)
    if prov is not None:
        return list(prov.tiles)
    return [region]


def draw_hex_map(surface, world, font, font_small):
    """Draw full hex grid map with realistic elevation heightmap, shaded relief, and territory highlights."""
    tiles = world['tiles']
    layout = world['layout']
    sel = world.get('selected_region')
    zoom = world['cam']['zoom']
    frame = world.get('frame', 0)

    # Build province color highlight map for the selected nation
    highlight_map = {}
    if sel is not None and getattr(sel, 'owner_nation', None) is not None:
        nation = sel.owner_nation
        provinces = getattr(nation, 'provinces', [])
        for i, prov in enumerate(provinces):
            color = PROVINCE_COLORS[i % len(PROVINCE_COLORS)]
            for r in prov.tiles:
                highlight_map[r.name] = (color, prov.name)

    for region in tiles:
        coords = layout.get(region.name)
        if coords is None:
            continue
        cx, cy = hex_px(world, *coords)
        pts = hex_corners((cx, cy), HEX_SIZE * zoom - 1)

        # 1. Realistic Elevation Heightmap & Biome Topography
        draw_elevation_terrain(surface, region, pts, cx, cy, zoom=zoom, frame=frame)

        # 2. Semi-Transparent Nation Territory Overlay (preserves elevation relief underneath)
        draw_nation_overlay(surface, region, pts)

        # 3. Outer Borders
        owner = getattr(region, 'owner_nation', None)
        if owner is not None:
            n_col = NATION_COLORS.get(owner.name, HEX_EDGE)
            pygame.draw.polygon(surface, n_col, pts, max(2, int(2 * zoom)))
        else:
            pygame.draw.polygon(surface, WILD_EDGE, pts, 1)

        # 4. Province Highlight Border
        if region.name in highlight_map:
            color, _pname = highlight_map[region.name]
            pygame.draw.polygon(surface, color, pts, max(3, int(3 * zoom)))

        # 5. Selected Tile Focal Highlight
        if sel is region:
            pygame.draw.polygon(surface, (255, 255, 255), pts, 4 if region.name not in highlight_map else 2)

        # 6. Readouts with Drop Shadows for Readability
        city_title = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
        name_font = font_small if len(city_title) > 8 else font
        draw_text_with_shadow(surface, name_font, city_title, (cx, cy - 20), (255, 255, 255))
        
        layer_mode = world.get('map_layer', 'overview')
        line1, line2, line3, c1, c2, c3 = tile_stats(region, layer_mode=layer_mode, world=world)
        draw_text_with_shadow(surface, font_small, line1, (cx, cy - 2), c1)
        draw_text_with_shadow(surface, font_small, line2, (cx, cy + 12), c2)
        if line3:
            draw_text_with_shadow(surface, font_small, line3, (cx, cy + 24), c3)

        draw_terrain_glyph(surface, region, cx, cy - 34)
        draw_activity_badges(surface, region, cx, cy, font_small)
        draw_pop_delta(surface, region, cx, cy, font_small)

    draw_edges(surface, world)
    draw_trade_arrows(surface, world)
