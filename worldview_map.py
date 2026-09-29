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

import os
import json
import math
import numpy as np
import pygame
from goods import Goods
from hexmap import hex_corners
from worldview_camera import hex_px, HEX_SIZE, MAP_RIGHT, TOP_BAR_H, TICKER_H, HEIGHT
from heightmap import get_cached_topographic_surface
from ui_icons import get_icon

NATION_COLORS = {
    'United States': (80, 160, 240),
    'China':         (235, 80, 80),
    'Japan':         (205, 80, 190),  # Vibrant orchid / magenta (strictly avoids white)
    'Russia':        (160, 140, 240),
    'India':         (245, 160, 60),
    'Indonesia':     (230, 90, 120),
    'Brazil':        (80, 220, 140),
    'Mexico':        (60, 200, 170),
    'Nigeria':       (100, 220, 100),
    'Pakistan':      (70, 190, 130),
    'Bangladesh':    (80, 200, 120),
    'Germany':       (225, 175, 55),
    'United Kingdom':(150, 110, 220),
    'France':        (75, 135, 230),
    'Alpha':         (141, 211, 199),
    'Beta':          (230, 200, 90),
    'Gamma':         (190, 140, 220),
}


def get_nation_color(name: str):
    """Return a vibrant, distinct RGB color for any nation, strictly avoiding white."""
    if not name:
        return (160, 165, 155)
    if name in NATION_COLORS:
        return NATION_COLORS[name]
    # Deterministic procedural color clamped away from white (saturation > 0.5, value 0.7-0.9)
    h = abs(hash(name))
    r = 70 + (h % 150)
    g = 70 + ((h // 150) % 150)
    b = 70 + ((h // 22500) % 150)
    return (r, g, b)

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
        return get_nation_color(owner.name)
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
            return "GDP: $0", "Wilderness" if not is_ocean else "Ocean Waters", "No Banking", DIM, DIM, DIM
        gdp = region.gdp_log[-1] if region.gdp_log else 0.0
        tax = region.gov.tax_rate if getattr(region, 'gov', None) else 0.15
        curr = getattr(region, 'home_currency', getattr(owner, 'currency', 'USD') if owner else 'WLD')
        return f"GDP ${gdp:,.0f} ({curr})", f"Tax Rate: {tax*100:.0f}%", f"Bank Cap: ${region.bank.capital:,.0f}", (120, 225, 130), ACCENT, DIM

    # 4. PRODUCTION & OUTPUT LAYER
    if layer_mode == 'production':
        if is_ocean:
            return "No Output", "Ocean Territory", "", DIM, DIM, DIM
        food_p = region.production_log[Goods.food][-1] if (Goods.food in region.production_log and region.production_log[Goods.food]) else 0.0
        wood_p = region.production_log[Goods.wood][-1] if (Goods.wood in region.production_log and region.production_log[Goods.wood]) else 0.0
        furn_p = region.production_log[Goods.furniture][-1] if (Goods.furniture in region.production_log and region.production_log[Goods.furniture]) else 0.0
        buildings = getattr(region, 'buildings', [])
        b_count = len(buildings)
        return f"Fd {food_p:.0f} | Wd {wood_p:.0f} | Fn {furn_p:.0f}", f"Industry: {b_count} Buildings", f"Farms: {sum(1 for b in buildings if b.building_type=='farm')}", (245, 210, 90), TEXT, DIM

    # 5. MILITARY & DEFENSE LAYER
    if layer_mode == 'military':
        if is_ocean:
            return "Naval Domain", "Ocean Waters", "", DIM, DIM, DIM
        garrison_units = getattr(region, 'military_units', [])
        total_soldiers = sum(u.soldiers for u in garrison_units)
        if total_soldiers > 0:
            avg_morale = sum(u.morale for u in garrison_units) / len(garrison_units)
            return f"Garrison: {total_soldiers} Men", f"Units: {len(garrison_units)} | Morale {avg_morale*100:.0f}%", "Status: Fortified", (235, 90, 90), TEXT, GREEN
        else:
            threat_str = "Border: Guarded" if owner else "Wilderness"
            return "No Garrison", threat_str, "Vulnerability: High" if owner else "--", DIM, ACCENT if owner else DIM, RED if owner else DIM

    # 7. LAND TENURE & ENCLOSURE LAYER
    if layer_mode == 'enclosure':
        if is_ocean:
            return "No Land Tenure", "Ocean Waters", "", DIM, DIM, DIM
        tenure = getattr(region, 'tenure', None)
        if tenure:
            commons_pct = tenure.commons_access * 100.0
            feudal_pct = tenure.feudal_fraction * 100.0
            encl_pct = tenure.enclosed_fraction * 100.0
            rent = region.rent_collected_log[-1] if getattr(region, 'rent_collected_log', None) else 0.0
            top_badge = f"Commons: {commons_pct:.0f}%"
            stat_line = f"Feud {feudal_pct:.0f}% | Encl {encl_pct:.0f}%"
            tr_line = f"Rent: ${rent:,.0f}" if rent > 0 else "Free Customary"
            b_col = (110, 215, 130) if commons_pct > 60 else ((240, 185, 75) if commons_pct > 25 else (230, 110, 60))
            return top_badge, stat_line, tr_line, b_col, TEXT, DIM
        else:
            return "Wilderness Commons", "Customary Foraging", "No Enclosure", (110, 215, 130), TEXT, DIM

    # 8. EXPLOITATION (s/v) & STRIKES LAYER
    if layer_mode == 'exploitation':
        if is_ocean:
            return "No Industry", "Ocean Waters", "", DIM, DIM, DIM
        sv_log = getattr(region, 'rate_of_exploitation_log', [])
        sv = sv_log[-1] if sv_log else 0.0
        shift_log = getattr(region, 'avg_shift_hours_log', [])
        sh = shift_log[-1] if shift_log else 8.0
        strikers = region.strikers_log[-1] if getattr(region, 'strikers_log', None) else 0
        broken = region.broken_machinery_log[-1] if getattr(region, 'broken_machinery_log', None) else 0

        top_badge = f"s/v: {sv*100:.0f}% ({sh:.1f}h)"
        stat_line = f"Strikers: {strikers} | Smashed: {broken}"
        tr_line = "WILDCAT STRIKE!" if (strikers > 0 or broken > 0) else "Peaceful Factory"
        b_col = RED if (strikers > 0 or broken > 0 or sv > 1.0) else ((240, 180, 80) if sv > 0.4 else (100, 180, 240))
        t_col = RED if (strikers > 0 or broken > 0) else GREEN
        return top_badge, stat_line, tr_line, b_col, TEXT, t_col

    # 9. EXTERNALITIES & METABOLIC RIFT LAYER (Phase 3)
    if layer_mode == 'externalities':
        if is_ocean:
            return "Ocean Waters", "Pristine Aquatic Sink", "", (100, 200, 230), DIM, DIM
        fert = getattr(region, 'soil_fertility', 1.0)
        nut = getattr(region, 'nutrition_density', 1.0)
        air_p = getattr(region, 'pollution_air', 0.0)
        wat_p = getattr(region, 'pollution_water', 0.0)
        use_f = getattr(region, 'use_fertilizer', False)
        use_p = getattr(region, 'use_pesticides', False)

        regime = getattr(region, 'farming_regime', 'rotation')
        g_stock = getattr(region, 'granary_stock', 0.0)

        # Top line: Soil Fertility & Nutrition Density
        top_badge = f"Soil: {fert*100:.0f}% • Nut: {nut*100:.0f}%"

        # Middle line: Farming Regime & Granary Buffer
        reg_name = "4-Field" if regime == 'rotation' else ("Monocult" if regime == 'intensive' else "Pasture")
        stat_line = f"Regime: {reg_name} | Gran: {g_stock:.0f}t"

        # Bottom line: Environmental Pollution & Crisis
        owner = getattr(region, 'owner_nation', None)
        is_cap = (owner and owner.tiles and region == owner.tiles[0])
        has_sewer = any(getattr(b, 'name', '') == 'trunk_sewer' for b in getattr(region, 'buildings', []))

        if is_cap and wat_p >= 60.0 and not has_sewer:
            tr_line = "🚨 THE GREAT STINK!"
            t_col = (255, 75, 75)
        elif getattr(region, 'is_nitrate_depleted', False):
            tr_line = "⚠️ NO NITRATES!"
            t_col = (245, 120, 40)
        else:
            tr_line = f"Smog: {air_p:.0f} | Water: {wat_p:.0f}"
            t_col = (235, 90, 90) if (air_p > 20.0 or wat_p > 20.0) else GREEN

        b_col = (100, 220, 140) if fert >= 0.90 and nut >= 0.90 else ((240, 180, 80) if fert >= 0.60 else (225, 100, 80))
        return top_badge, stat_line, tr_line, b_col, TEXT, t_col

    # 6. OVERVIEW LAYER (Default)
    if is_ocean or owner is None:
        return "", "", "", DIM, DIM, DIM

    # Claimed tile: Show Nation Name ONLY on nation capital; Province Name ONLY on province seat
    is_nation_capital = (owner.tiles and region == owner.tiles[0])
    prov = next((p for p in getattr(owner, 'provinces', []) if region in p.tiles), None)
    is_prov_capital = (prov and prov.tiles and region == prov.tiles[0])

    top_badge = ""
    badge_col = get_nation_color(owner.name)
    if is_nation_capital:
        prov_str = getattr(prov, 'display_name', '') if prov else ''
        top_badge = f"* {owner.name}" + (f" — {prov_str}" if prov_str else "")
    elif is_prov_capital and prov:
        top_badge = f"[{getattr(prov, 'display_name', prov.name)}]"

    food = region.recipes[Goods.food]['price'] if hasattr(region, 'recipes') and Goods.food in region.recipes else 1.0
    traders = sum(1 for a in region.agents if getattr(a, 'is_trader', False))
    stat_line = f"pop {pop}  fd ${food:.1f}"
    tr_line = f"tr {traders}" if traders > 0 else ""

    return top_badge, stat_line, tr_line, badge_col, TEXT, DIM


def draw_elevation_terrain(surface, region, pts, cx, cy, zoom=1.0, frame=0):
    """Draw subtle ambient wave shimmer over water while letting the 3D raymarched terrain shine through."""
    biome = getattr(region, 'biome', 'plains')
    elev = getattr(region, 'elevation', 0.0)

    # Ocean Waves and Water Depth Shimmer (< 0.0)
    if elev < 0.0 or biome in ('deep_ocean', 'shallow_ocean'):
        wave_color = (65, 140, 190, 70) if biome == 'shallow_ocean' else (35, 80, 140, 50)
        # Draw subtle dynamic wave shimmer lines
        for dy in (-18, 0, 18):
            wy = cy + int(dy * zoom)
            wx1 = cx - int(24 * zoom)
            wx2 = cx + int(24 * zoom)
            phase = math.sin(frame * 0.08 + cx * 0.05 + dy) * 3 * zoom
            pygame.draw.line(surface, wave_color[:3], (wx1, wy + int(phase)), (wx2, wy + int(phase)), 1)
        return


_HEX_TINT_SURF_CACHE: dict = {}  # (w, h) -> pygame.Surface reused across calls


def _get_hex_tint_surf(w: int, h: int) -> pygame.Surface:
    """Return a reusable SRCALPHA surface of the requested size, clearing it before use."""
    key = (w, h)
    surf = _HEX_TINT_SURF_CACHE.get(key)
    if surf is None:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        _HEX_TINT_SURF_CACHE[key] = surf
    else:
        surf.fill((0, 0, 0, 0))
    return surf


def _pts_bbox_and_local(pts):
    """Compute (min_x, min_y, w, h, local_pts) for a polygon — shared by tint helpers."""
    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)
    w = max(1, int(max_x - min_x) + 2)
    h = max(1, int(max_y - min_y) + 2)
    local_pts = [(p[0] - min_x, p[1] - min_y) for p in pts]
    return min_x, min_y, w, h, local_pts


def draw_nation_overlay(surface, region, pts):
    """Draw semi-transparent nation territory tint so realistic elevation peeks through."""
    owner = getattr(region, 'owner_nation', None)
    if owner is None:
        return

    col = get_nation_color(owner.name)
    # Population brightness factor
    pop = region_pop(region)
    f = min(0.35, 0.15 * (pop / 400.0))
    extra = int(40 * f)

    min_x, min_y, w, h, local_pts = _pts_bbox_and_local(pts)
    tint_surf = _get_hex_tint_surf(w, h)

    # Soft nation alpha wash (alpha = 60)
    tint_color = (min(255, col[0] + extra), min(255, col[1] + extra), min(255, col[2] + extra), 60)
    pygame.draw.polygon(tint_surf, tint_color, local_pts)
    surface.blit(tint_surf, (min_x, min_y))


def draw_thematic_choropleth(surface, region, pts, layer_mode, frame=0):
    """Draw Layer 7 (Land Tenure / Enclosure) or Layer 8 (Exploitation / Strikes) choropleth tint."""
    is_ocean = getattr(region, 'is_ocean', False) or getattr(region, 'elevation', 0) < 0
    if is_ocean:
        return

    min_x, min_y, w, h, local_pts = _pts_bbox_and_local(pts)
    tint_surf = _get_hex_tint_surf(w, h)

    if layer_mode == 'enclosure':
        tenure = getattr(region, 'tenure', None)
        c_acc = tenure.commons_access if tenure else 1.0
        # Blend from lush green (c_acc=1.0) to parched amber/brown (c_acc=0.0)
        cr = int(60 * c_acc + 195 * (1.0 - c_acc))
        cg = int(190 * c_acc + 95 * (1.0 - c_acc))
        cb = int(90 * c_acc + 40 * (1.0 - c_acc))
        pygame.draw.polygon(tint_surf, (cr, cg, cb, 90), local_pts)
        surface.blit(tint_surf, (min_x, min_y))

    elif layer_mode == 'exploitation':
        sv_log = getattr(region, 'rate_of_exploitation_log', [])
        sv = sv_log[-1] if sv_log else 0.5
        ratio = min(1.0, max(0.0, sv / 1.5))
        # Blend from deep blue (low s/v) to hot crimson (high s/v)
        cr = int(50 * (1.0 - ratio) + 235 * ratio)
        cg = int(120 * (1.0 - ratio) + 45 * ratio)
        cb = int(220 * (1.0 - ratio) + 65 * ratio)
        pygame.draw.polygon(tint_surf, (cr, cg, cb, 95), local_pts)
        surface.blit(tint_surf, (min_x, min_y))

        # Flashing strike warning border on hex
        strikers = getattr(region, 'strikers_log', [0])[-1] if getattr(region, 'strikers_log', None) else 0
        broken = getattr(region, 'broken_machinery_log', [0])[-1] if getattr(region, 'broken_machinery_log', None) else 0
        if strikers > 0 or broken > 0:
            pulse = int(140 + 115 * math.sin(frame * 0.2))
            pygame.draw.polygon(surface, (255, 60, 60, pulse), pts, 3)

    elif layer_mode == 'externalities':
        fert = getattr(region, 'soil_fertility', 1.0)
        air_p = getattr(region, 'pollution_air', 0.0)
        wat_p = getattr(region, 'pollution_water', 0.0)
        tot_poll = air_p + wat_p

        # Soil fertility component: rich emerald loam (fert=1.0) to bleached ochre dust (fert=0.2)
        r_f = int(45 * fert + 210 * (1.0 - fert))
        g_f = int(175 * fert + 140 * (1.0 - fert))
        b_f = int(90 * fert + 80 * (1.0 - fert))

        # Pollution smog/sludge overlay factor
        p_factor = min(1.0, tot_poll / 60.0)
        cr = int(r_f * (1.0 - p_factor) + 160 * p_factor)
        cg = int(g_f * (1.0 - p_factor) + 90 * p_factor)
        cb = int(b_f * (1.0 - p_factor) + 175 * p_factor)

        pygame.draw.polygon(tint_surf, (cr, cg, cb, 105), local_pts)
        surface.blit(tint_surf, (min_x, min_y))

        # Flashing haze/warning for severe pollution
        if air_p > 25.0 or wat_p > 25.0:
            pulse = int(120 + 90 * math.sin(frame * 0.15))
            pygame.draw.polygon(surface, (190, 80, 220, pulse), pts, 2)

        # The Great Stink Atmospheric FX: Rising toxic vapor particles over capital
        owner = getattr(region, 'owner_nation', None)
        is_cap = (owner and owner.tiles and region == owner.tiles[0])
        has_sewer = any(getattr(b, 'name', '') == 'trunk_sewer' for b in getattr(region, 'buildings', []))
        if is_cap and wat_p >= 60.0 and not has_sewer:
            for i in range(4):
                v_phase = (frame * 0.8 + i * 8) % 24
                vx = min_x + w * 0.3 + (i * 14) % int(w * 0.4)
                vy = min_y + h * 0.6 - v_phase * 1.5
                pygame.draw.circle(surface, (140, 160, 90, 80), (int(vx), int(vy)), int(4 + v_phase * 0.25))


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

    # Ultra-Rare Natural Guano & Nitrate Global Deposit Beacon
    from tile_resources import TileResource
    if TileResource.NATURAL_NITRATES in getattr(region, 'natural_resources', []):
        from ui_icons import get_icon
        icon = get_icon('guano', size=16)
        surface.blit(icon, (cx - 8, cy - 32))
        pygame.draw.circle(surface, (255, 235, 120), (cx, cy - 24), 12, 1)


def trade_anim(world, center_map=None):
    """Animated arrows: last-turn net trade flow on claimed pairs."""
    out = []
    for r, other in world['pair_orders']:
        flow = r.trade_flow_log[-1] if r.trade_flow_log else 0.0
        if abs(flow) < 0.5:
            continue
        e1 = getattr(r, 'elevation', 0.0) if not getattr(r, 'is_ocean', False) else 0.0
        e2 = getattr(other, 'elevation', 0.0) if not getattr(other, 'is_ocean', False) else 0.0
        c1 = center_map.get(r.name) if center_map else None
        c2 = center_map.get(other.name) if center_map else None
        if c1 is None:
            c1 = hex_px(world, *world['layout'][r.name], elevation=e1)
        if c2 is None:
            c2 = hex_px(world, *world['layout'][other.name], elevation=e2)
        width = max(1, min(8, int(abs(flow) / 1500.0) + 1))
        out.append((c1, c2, width, flow > 0))
    return out


def draw_edges(surface, world, center_map=None):
    """Render geographic trade routes: rivers, mountain passes, standard paths, and alpine barriers.

    center_map: optional dict of {region_name: (screen_cx, screen_cy)} to avoid recomputing
                hex_px for every edge pair. Falls back to hex_px if not provided.
    """
    from terrain_edges import get_edge_manager, EdgeType
    em = get_edge_manager(world.get('tiles'), world.get('layout'))
    layout = world.get('layout', {})
    
    seen_edges = set()

    # 1. Passable Trade Edges & River Corridors
    for r, other in world.get('pair_orders', []):
        key = tuple(sorted((r.name, other.name)))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        
        if r.name not in layout or other.name not in layout:
            continue
        e1 = getattr(r, 'elevation', 0.0) if not getattr(r, 'is_ocean', False) else 0.0
        e2 = getattr(other, 'elevation', 0.0) if not getattr(other, 'is_ocean', False) else 0.0
        if center_map is not None and r.name in center_map and other.name in center_map:
            c1 = center_map[r.name]
            c2 = center_map[other.name]
        else:
            c1 = hex_px(world, *layout[r.name], elevation=e1)
            c2 = hex_px(world, *layout[other.name], elevation=e2)
        
        edge = em.get_edge(r.name, other.name) if em else None
        if edge and edge.is_river:
            p_a = getattr(r, 'pollution_water', 0.0)
            p_b = getattr(other, 'pollution_water', 0.0)
            p_eff = max(p_a, p_b)

            # River Color Morphing based on water effluent toxicity
            if p_eff <= 10.0:
                col_outer = (50, 130, 210)    # Crystal Cyan-Blue
                col_inner = (120, 215, 255)
                part_col = (180, 240, 255)
            elif p_eff <= 30.0:
                col_outer = (65, 145, 80)     # Murky Algae Green (Fishery Threat)
                col_inner = (130, 210, 130)
                part_col = (190, 245, 120)
            else:
                col_outer = (135, 70, 80)     # Industrial Chemical Sludge Brown/Purple
                col_inner = (210, 105, 115)
                part_col = (255, 130, 140)

            pygame.draw.line(surface, col_outer, c1, c2, 3)
            pygame.draw.line(surface, col_inner, c1, c2, 1)

            # Animated Downstream Flow Droplet (from higher elevation to lower elevation)
            h_a = getattr(r, 'elevation', 0.0)
            h_b = getattr(other, 'elevation', 0.0)
            flow_start, flow_end = (c1, c2) if h_a >= h_b else (c2, c1)
            fdx = flow_end[0] - flow_start[0]
            fdy = flow_end[1] - flow_start[1]
            flen = max(1.0, math.hypot(fdx, fdy))
            frame = world.get('frame', 0)
            f_phase = ((frame * 1.5) % 40) / 40.0
            px = int(flow_start[0] + (fdx / flen) * flen * f_phase)
            py = int(flow_start[1] + (fdy / flen) * flen * f_phase)
            pygame.draw.circle(surface, part_col, (px, py), 2)

            # Riparian Dispute Marker between Sovereign Nations
            owner_a = getattr(r, 'owner_nation', None)
            owner_b = getattr(other, 'owner_nation', None)
            if owner_a and owner_b and owner_a.name != owner_b.name:
                cb_a = getattr(owner_a, 'active_casus_belli', set())
                cb_b = getattr(owner_b, 'active_casus_belli', set())
                has_dispute = (any(t == owner_b.name and cb == 'riparian_poisoning' for t, cb in cb_a) or
                               any(t == owner_a.name and cb == 'riparian_poisoning' for t, cb in cb_b))
                if has_dispute:
                    mid_x = (c1[0] + c2[0]) // 2
                    mid_y = (c1[1] + c2[1]) // 2
                    pulse = int(180 + 75 * math.sin(frame * 0.2))
                    pygame.draw.circle(surface, (235, 60, 60, pulse), (mid_x, mid_y), 5)
                    pygame.draw.circle(surface, (255, 255, 255), (mid_x, mid_y), 2)

        elif edge and edge.edge_type == EdgeType.MOUNTAIN_PASS:
            # Engineered / Natural Mountain Pass (Golden Mountain Road)
            pygame.draw.line(surface, (230, 185, 65), c1, c2, 2)
        else:
            pygame.draw.line(surface, EDGE_LINE, c1, c2, 1)

    # 2. Blocked Alpine & Cliff Barriers (Visual indicators)
    if em is not None:
        for (name_a, name_b), edge in em.edges.items():
            if not edge.passable and (name_a, name_b) not in seen_edges:
                if name_a in layout and name_b in layout:
                    if center_map is not None and name_a in center_map and name_b in center_map:
                        c1 = center_map[name_a]
                        c2 = center_map[name_b]
                    else:
                        c1 = hex_px(world, *layout[name_a])
                        c2 = hex_px(world, *layout[name_b])
                    # Draw mid-point barrier hash
                    mx = (c1[0] + c2[0]) // 2
                    my = (c1[1] + c2[1]) // 2
                    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
                    dist = max(1.0, math.hypot(dx, dy))
                    nx, ny = -dy / dist * 6, dx / dist * 6
                    pygame.draw.line(surface, (190, 50, 50), (int(mx - nx), int(my - ny)), (int(mx + nx), int(my + ny)), 2)


def draw_trade_arrows(surface, world, center_map=None):
    """Animated dots on claimed-pair edges scaled by recent net flow."""
    frame = world.get('frame', 0)
    for c1, c2, width, forward in trade_anim(world, center_map=center_map):
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
        from world_config import is_voronoi_topology
        ring_radius = 22 if is_voronoi_topology() else (HEX_SIZE - 8)
        if ring_color is not None:
            pygame.draw.circle(surface, ring_color, (cx, cy), ring_radius, 2)
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

    # Phase 4 Badges: Popular Resistance & Imperialism
    try:
        from popular_resistance import get_popular_resistance_manager
        r_state = get_popular_resistance_manager().get_state(region.name)
        if r_state.has_barricades:
            pygame.draw.rect(surface, (230, 80, 40), (cx - 36, cy + 24, 16, 14), border_radius=3)
            btxt = font_small.render("B", True, (255, 255, 255))
            surface.blit(btxt, (cx - 33, cy + 23))

        if r_state.is_general_strike:
            pygame.draw.rect(surface, (240, 40, 40), (cx - 16, cy + 34, 20, 14), border_radius=3)
            stxt = font_small.render("GS", True, (255, 255, 255))
            surface.blit(stxt, (cx - 14, cy + 33))

        if r_state.enclosure_stage in ('organizing', 'announced', 'marching', 'protest'):
            stg_map = {
                'organizing': ("ORG", (220, 180, 50)),
                'announced': ("ANN", (230, 150, 40)),
                'marching': ("MCH", (240, 90, 40)),
                'protest': ("PRT", (240, 30, 30))
            }
            lbl, bg = stg_map[r_state.enclosure_stage]
            pygame.draw.rect(surface, bg, (cx - 38, cy - 30, 24, 13), border_radius=3)
            etxt = font_small.render(lbl, True, (15, 15, 20))
            surface.blit(etxt, (cx - 36, cy - 31))
        elif r_state.terror_cooldown > 0:
            pygame.draw.rect(surface, (40, 40, 50), (cx - 38, cy - 30, 24, 13), border_radius=3)
            ttxt = font_small.render("TR", True, (200, 70, 70))
            surface.blit(ttxt, (cx - 34, cy - 31))
        elif r_state.leader_id is not None:
            # Ambient Agitator Badge (fermenting resistance)
            pygame.draw.rect(surface, (180, 70, 40), (cx - 38, cy - 30, 24, 13), border_radius=3)
            atxt = font_small.render("AGT", True, (255, 240, 220))
            surface.blit(atxt, (cx - 37, cy - 31))

        # Ambient Martyr Honor Badge (if tile has venerated martyrs)
        if getattr(r_state, 'martyrs', None) and len(r_state.martyrs) > 0:
            pygame.draw.rect(surface, (140, 30, 40), (cx - 38, cy - 44, 24, 13), border_radius=3)
            pygame.draw.rect(surface, (235, 195, 75), (cx - 38, cy - 44, 24, 13), 1, border_radius=3)
            mtxt = font_small.render("MTR", True, (255, 235, 160))
            surface.blit(mtxt, (cx - 37, cy - 45))

        from imperialism import get_imperialism_manager
        imp_mgr = get_imperialism_manager()
        if imp_mgr.is_tile_blockaded(region.name):
            pygame.draw.rect(surface, (180, 30, 30), (cx + 8, cy + 34, 24, 14), border_radius=3)
            blktxt = font_small.render("BLK", True, (255, 255, 255))
            surface.blit(blktxt, (cx + 9, cy + 33))

        owner = getattr(region, 'owner_nation', None)
        if owner:
            if getattr(owner, 'regime_type', '') == 'commune':
                pygame.draw.circle(surface, (220, 20, 20), (cx + 34, cy - 42), 7)
                pygame.draw.circle(surface, (20, 20, 20), (cx + 34, cy - 42), 7, 1)
                ctxt = font_small.render("*", True, (255, 255, 255))
                surface.blit(ctxt, ctxt.get_rect(center=(cx + 34, cy - 40)))
            elif imp_mgr.get_active_receivership_on(owner.name):
                pygame.draw.rect(surface, (220, 150, 40), (cx - 12, cy - 58, 24, 13), border_radius=3)
                rtxt = font_small.render("REC", True, (15, 15, 20))
                surface.blit(rtxt, (cx - 10, cy - 59))

        # Domestic Bank Freeze Badge (Corralito)
        bank = getattr(region, 'bank', None)
        if bank and getattr(bank, 'is_frozen', False):
            pygame.draw.rect(surface, (180, 40, 200), (cx + 18, cy - 58, 24, 13), border_radius=3)
            frztxt = font_small.render("FRZ", True, (255, 255, 255))
            surface.blit(frztxt, (cx + 20, cy - 59))

        # Turnip Winter Nitrate Depletion Harvest Shock Badge
        if getattr(region, 'is_nitrate_depleted', False):
            pygame.draw.rect(surface, (230, 110, 30), (cx - 40, cy - 58, 26, 13), border_radius=3)
            ntrtxt = font_small.render("NTR", True, (15, 15, 20))
            surface.blit(ntrtxt, (cx - 38, cy - 59))

        # The Great Pestilence (Black Death Vector Badge)
        pest_count = getattr(region, 'active_pestilence_count', 0)
        if pest_count == 0:
            pest_count = sum(1 for a in getattr(region, 'agents', []) if getattr(a, 'alive', True) and getattr(a, 'disease', None) == 'pestilence')
        if pest_count > 0:
            pygame.draw.rect(surface, (120, 20, 140), (cx + 16, cy - 44, 26, 13), border_radius=3)
            pygame.draw.rect(surface, (255, 100, 255), (cx + 16, cy - 44, 26, 13), 1, border_radius=3)
            surface.blit(font_small.render("PLG", True, (255, 230, 255)), (cx + 18, cy - 45))

        # Cordon Sanitaire / Quarantine Active Badge
        if getattr(region, 'quarantine_active', False):
            pygame.draw.rect(surface, (210, 120, 20), (cx + 16, cy - 30, 26, 13), border_radius=3)
            surface.blit(font_small.render("QRN", True, (255, 255, 255)), (cx + 18, cy - 31))

        # Phase 3 Farming Regime Badges
        regime = getattr(region, 'farming_regime', 'rotation')
        has_farms = any(getattr(b, 'building_type', '') == 'farm' for b in getattr(region, 'buildings', []))
        if has_farms or region.terrain.get(Goods.food, 1.0) > 1.1:
            if regime == 'rotation':
                pygame.draw.rect(surface, (40, 140, 70), (cx - 40, cy + 34, 26, 13), border_radius=3)
                surface.blit(font_small.render("ROT", True, (255, 255, 255)), (cx - 38, cy + 33))
            elif regime == 'intensive':
                if getattr(region, 'is_nitrate_depleted', False) or getattr(region, 'fertilizer_stock', 0.0) <= 0.0:
                    pygame.draw.rect(surface, (230, 45, 45), (cx - 42, cy + 34, 30, 13), border_radius=3)
                    surface.blit(font_small.render("!NTR", True, (255, 255, 255)), (cx - 40, cy + 33))
                else:
                    pygame.draw.rect(surface, (215, 140, 40), (cx - 40, cy + 34, 26, 13), border_radius=3)
                    surface.blit(font_small.render("INT", True, (15, 15, 20)), (cx - 38, cy + 33))

        # Capital Great Stink Badge
        is_cap = (owner is not None and owner.tiles and region == owner.tiles[0])
        p_wat = getattr(region, 'pollution_water', 0.0)
        has_sewer = any(getattr(b, 'name', '') == 'trunk_sewer' for b in getattr(region, 'buildings', []))
        if is_cap and p_wat >= 60.0 and not has_sewer:
            pygame.draw.rect(surface, (220, 40, 60), (cx - 26, cy - 70, 52, 14), border_radius=3)
            pygame.draw.rect(surface, (255, 220, 80), (cx - 26, cy - 70, 52, 14), 1, border_radius=3)
            surface.blit(font_small.render("STINK!", True, (255, 255, 255)), (cx - 22, cy - 71))
    except Exception:
        pass


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
    surface.blit(txt, txt.get_rect(center=(cx + 34, cy - 24)))


def get_tile_label_priority(region, world, is_nat_cap=False, is_prov_cap=False):
    """Compute importance score for dynamic label overlap culling.
    Hierarchy:
    1. Selected or hovered tile (1000/900)
    2. National Capitals (850)
    3. Selected nation's tiles (750)
    4. Provincial Capitals (700)
    5. Other nation tiles (600 + pop weight) — ALL nation tiles >= 600
    6. Wild tiles surrounding selected nation (450)
    7. Wild tiles surrounding any nation (400)
    8. General wilderness tiles (200)
    9. Ocean (100)
    """
    sel = world.get('selected_region')
    sel_name = getattr(sel, 'name', None) if sel is not None else world.get('selected')
    hover = world.get('hover_region')
    sel_nation = world.get('selected_nation')
    if isinstance(sel_nation, str):
        sel_nation_name = sel_nation
    else:
        sel_nation_name = getattr(sel_nation, 'name', None) or world.get('player_nation_name')

    r_name = getattr(region, 'name', '')
    owner = getattr(region, 'owner_nation', None)
    owner_name = getattr(owner, 'name', None)

    # 1. Selected or hovered tile (highest priority)
    if (sel is not None and region == sel) or (sel_name is not None and r_name == sel_name):
        return 1000
    if hover is not None and region == hover:
        return 900

    # 2. National Capitals
    if is_nat_cap:
        return 850

    # 3. Selected nation's tiles
    if owner is not None and (owner == sel_nation or (sel_nation_name and owner_name == sel_nation_name)):
        return 750

    # 4. Provincial Capitals
    if is_prov_cap:
        return 700

    # 5. Other nations' regular tiles (ALL nation tiles have priority >= 600)
    if owner is not None:
        pop = getattr(region, 'population', 0)
        return 600 + min(80, int(pop / 100))

    # 6. Wild tiles surrounding nations (priority < 500, strictly lower than any nation tile)
    is_wild = (owner is None or getattr(region, 'wilderness', False))
    if is_wild:
        neighbors = getattr(region, 'neighbors', [])
        surrounds_sel = False
        surrounds_any = False
        for nbr in neighbors:
            nbr_owner = getattr(nbr, 'owner_nation', None)
            if nbr_owner is not None:
                surrounds_any = True
                nbr_owner_name = getattr(nbr_owner, 'name', None)
                if nbr_owner == sel_nation or (sel_nation_name and nbr_owner_name == sel_nation_name):
                    surrounds_sel = True
                    break
        if surrounds_sel:
            return 450
        elif surrounds_any:
            return 400

    # 7. General wilderness tiles
    if is_wild:
        return 200

    # 8. Ocean / other
    return 100


def point_in_polygon(x: float, y: float, poly: list) -> bool:
    """Ray casting algorithm to test if point (x, y) is inside polygon poly."""
    n = len(poly)
    if n < 3:
        return False
    inside = False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def find_label_micro_shift(cand: dict, occupied_rects: list, blocker_rect: pygame.Rect | None):
    """Attempt to find a small spatial offset (dx, dy) within cand['pts'] that resolves collision.
    Returns (shifted_cx, shifted_cy, shifted_test_rect, dx, dy) if found, else None.
    Constraint: The text center must remain inside the tile polygon pts.
    """
    pts = cand.get('pts')
    if not pts or len(pts) < 3:
        return None

    cx, cy = cand.get('orig_cx', cand['cx']), cand.get('orig_cy', cand['cy'])
    test_rect = cand['test_rect']

    # Calculate escape vector away from the colliding blocker
    if blocker_rect is not None:
        vx = cx - blocker_rect.centerx
        vy = cy - blocker_rect.centery
    else:
        vx, vy = 0, 0

    mag = math.hypot(vx, vy)
    if mag > 0.001:
        escape_angle = math.atan2(vy, vx)
    else:
        escape_angle = 0.0

    # 24 radial directions around the unit circle (every 15 degrees)
    angles = [i * (2.0 * math.pi / 24) for i in range(24)]
    # Prioritize directions pointing away from the blocker
    angles.sort(key=lambda a: abs(math.atan2(math.sin(a - escape_angle), math.cos(a - escape_angle))))

    # Concentric distance rings: test fine micro-adjustments up to broad polygon extents
    distances = (6, 12, 18, 24, 30, 36, 44, 52, 60)

    for d in distances:
        for a in angles:
            dx = int(round(d * math.cos(a)))
            dy = int(round(d * math.sin(a)))
            nx = cx + dx
            ny = cy + dy

            # 1. Point-in-polygon constraint: center must remain strictly inside the tile's polygon
            if not point_in_polygon(nx, ny, pts):
                continue

            # 2. Collision test against all currently accepted labels
            shifted_test_rect = test_rect.move(dx, dy)
            if shifted_test_rect.collidelist(occupied_rects) == -1:
                return nx, ny, shifted_test_rect, dx, dy

    return None


def draw_text_with_shadow(surface, font, text, center, color, shadow_color=(12, 12, 16)):
    """Render text with a soft drop shadow for ultra-crisp readability over elevation terrain."""
    cx, cy = center
    # Render shadow once, blit at 4 offsets
    s_surf = font.render(text, True, shadow_color)
    for sx, sy in [(cx-1, cy), (cx+1, cy), (cx, cy-1), (cx, cy+1)]:
        surface.blit(s_surf, s_surf.get_rect(center=(sx, sy)))
    t_surf = font.render(text, True, color)
    surface.blit(t_surf, t_surf.get_rect(center=(cx, cy)))


def _draw_progress_bar(surface, bx, by, bar_w, bar_h, pct,
                       fill_color, border_color, bg_color,
                       icon_name, label_text, font_small):
    """Draw a single labelled progress bar. Shared by draw_tile_progress_bars."""
    from ui_icons import get_icon
    bg_rect = pygame.Rect(bx, by, bar_w, bar_h)
    pygame.draw.rect(surface, bg_color, bg_rect, border_radius=3)
    fill_w = max(2, int((bar_w - 2) * pct))
    fill_rect = pygame.Rect(bx + 1, by + 1, fill_w, bar_h - 2)
    pygame.draw.rect(surface, fill_color, fill_rect, border_radius=2)
    pygame.draw.rect(surface, border_color, bg_rect, 1, border_radius=3)
    icon = get_icon(icon_name, size=10)
    surface.blit(icon, (bx + 3, by + 1))
    txt = font_small.render(label_text, True, (255, 255, 255))
    surface.blit(txt, (bx + 15, by + 1))


def draw_tile_progress_bars(surface, region, cx, cy, font_small, world):
    """Draw sleek on-map progress bars overlayed on hex tiles for active construction, science, and diffusion."""
    if getattr(region, 'is_ocean', False) or getattr(region, 'elevation_meters', 0) < 0:
        return

    owner = getattr(region, 'owner_nation', None)
    is_cap = (owner is not None and owner.tiles and region == owner.tiles[0])

    bar_w = 78
    bar_h = 12
    bar_y = cy + 34

    # 1. Construction Progress Bar
    projects = getattr(region, 'construction_projects', [])
    active_proj = next((p for p in projects if getattr(p, 'status', '') == 'in_progress'), None)

    if active_proj is not None:
        pct = min(1.0, max(0.0, active_proj.turns_elapsed / max(1, active_proj.total_turns)))
        short_name = active_proj.recipe.name.replace('_', ' ').capitalize()[:6]
        _draw_progress_bar(
            surface, int(cx - bar_w // 2), int(bar_y), bar_w, bar_h, pct,
            fill_color=(235, 175, 45), border_color=(120, 110, 80), bg_color=(18, 20, 28),
            icon_name=active_proj.recipe.name,
            label_text=f"{short_name} {active_proj.turns_elapsed}/{active_proj.total_turns}t",
            font_small=font_small,
        )
        bar_y += 14  # Shift down if another bar exists
        
    # 2. Science Research / Royal Bounty / Trade Diffusion Progress Bar
    if owner is not None:
        from innovation import get_innovation_system, TECH_CATALOG
        inno = get_innovation_system()
        
        # Check active royal bounty on capital
        bounty = next((b for b in inno.active_bounties if b.nation_name == owner.name), None) if is_cap else None
        
        # Check active trade diffusion to this nation
        diff_map = inno.diffusion_progress.get(owner.name, {})
        active_diff = next(((t_id, prog) for t_id, prog in diff_map.items() if 0.0 < prog < 1.0), None)
        
        if bounty is not None:
            tech = TECH_CATALOG.get(bounty.tech_id)
            if tech:
                xp = inno.get_domain_xp(owner.name, tech.domain)
                pct = min(1.0, max(0.0, xp / max(1.0, tech.base_xp_required)))
                short_tech = tech.name.split()[0][:6]
                _draw_progress_bar(
                    surface, int(cx - bar_w // 2), int(bar_y), bar_w, bar_h, pct,
                    fill_color=(60, 190, 245), border_color=(70, 120, 160), bg_color=(18, 20, 32),
                    icon_name='rare_minerals',
                    label_text=f"R&D {short_tech} {int(pct*100)}%",
                    font_small=font_small,
                )

        elif active_diff is not None and is_cap:
            t_id, diff_prog = active_diff
            tech = TECH_CATALOG.get(t_id)
            if tech:
                short_tech = tech.name.split()[0][:6]
                _draw_progress_bar(
                    surface, int(cx - bar_w // 2), int(bar_y), bar_w, bar_h, diff_prog,
                    fill_color=(170, 110, 240), border_color=(110, 80, 150), bg_color=(24, 18, 32),
                    icon_name='im',
                    label_text=f"Diff {short_tech} {int(diff_prog*100)}%",
                    font_small=font_small,
                )
                bar_y += 14

    # 3. Granary Buffer Stock Gauge (shown on agricultural & urban tiles)
    g_stock = getattr(region, 'granary_stock', 0.0)
    has_farms = any(getattr(b, 'building_type', '') == 'farm' for b in getattr(region, 'buildings', []))
    is_agrarian = has_farms or region.terrain.get(Goods.food, 1.0) > 1.1 or g_stock > 1.0
    if is_agrarian and owner is not None:
        t = world.get('turn', 0)
        t_mod = t % 10
        bx = int(cx - bar_w // 2)
        by = int(bar_y)
        bg_rect = pygame.Rect(bx, by, bar_w, 10)
        pygame.draw.rect(surface, (16, 20, 26, 220), bg_rect, border_radius=2)
        fill_pct = min(1.0, max(0.0, g_stock / 50.0))
        fill_w = max(2, int((bar_w - 2) * fill_pct))

        # Color-coded by seasonal status
        if t_mod in (4, 5, 6, 7):
            fill_c = (80, 200, 110)    # Green (+15% storing)
            status_tag = f"Gran +15%"
        elif t_mod in (9, 0, 1):
            if g_stock <= 2.0:
                fill_c = (235, 60, 60)  # Red (Exhausted!)
                status_tag = f"Gran EMPTY"
            else:
                fill_c = (110, 210, 245) # Cyan (Buffering -4t)
                status_tag = f"Gran -4t"
        else:
            fill_c = (230, 195, 75)
            status_tag = f"Gran {g_stock:.0f}t"

        fill_rect = pygame.Rect(bx + 1, by + 1, fill_w, 8)
        pygame.draw.rect(surface, fill_c, fill_rect, border_radius=2)
        pygame.draw.rect(surface, (70, 85, 95), bg_rect, 1, border_radius=2)

        icon = get_icon('granary', size=8)
        surface.blit(icon, (bx + 2, by + 1))
        txt = font_small.render(status_tag, True, (255, 255, 255))
        surface.blit(txt, (bx + 12, by))


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
    hover_region = world.get('hover_region')
    cam = world['cam']
    zoom = cam['zoom']
    ox, oy = cam['ox'], cam['oy']
    frame = world.get('frame', 0)
    bbox = world['bbox']

    from world_config import is_voronoi_topology
    _is_voronoi = is_voronoi_topology()


    # 0. Draw Continuous Topographic Elevation Background Surface with Contour Lines & Hillshading
    seed = world.get('terrain_seed', world.get('seed', 42))

    # Retrieve or lazily create TerrainRenderer
    terrain_renderer = world.get('_terrain_renderer')
    if terrain_renderer is None:
        from render_engine.terrain import TerrainRenderer
        terrain_renderer = TerrainRenderer(force_cpu=not world.get('use_gpu_pipeline', True))
        world['_terrain_renderer'] = terrain_renderer

    # Synchronize force_cpu with world['use_gpu_pipeline']
    use_gpu = world.get('use_gpu_pipeline', not terrain_renderer.force_cpu)
    terrain_renderer.force_cpu = not use_gpu

    # Ensure slot_state is always reliably resolved; cache result to avoid disk reads each frame
    slot_state = getattr(world.get('gen'), 'slot_1_state', None) or world.get('slot_1_state')
    if not slot_state:
        cached_ss = world.get('_slot_state_cache')
        if cached_ss is not None:
            slot_state = cached_ss
        else:
            slot_1_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_slots", "slot_1.json")
            if os.path.exists(slot_1_file):
                try:
                    import json
                    with open(slot_1_file, "r", encoding="utf-8") as f:
                        slot_state = json.load(f).get("state", {})
                except Exception:
                    slot_state = {}
            else:
                slot_state = {}
            world['_slot_state_cache'] = slot_state

    if world.get('_cached_topo_surface') is not None:
        topo_surf = world['_cached_topo_surface']
        world['_map_generation_done'] = True
        world['loading_modal'] = None
    else:
        progress_cb = None
        if not world.get('_map_generation_done', False):
            def _on_map_progress(fraction, status_text):
                world['loading_modal'] = {'active': True, 'fraction': fraction, 'status': status_text}
                from worldview_ui import draw_loading_modal
                draw_loading_modal(surface, fraction, status_text, seed=seed)
                disp_surf = pygame.display.get_surface()
                if disp_surf is not None and disp_surf == surface:
                    pygame.display.flip()
                    pygame.event.pump()
            progress_cb = _on_map_progress

        if _is_voronoi and world.get('gen') is not None:
            gen = world['gen']
            cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_slots", "slot_1_terrain.png")
            if os.path.exists(cache_file):
                try:
                    topo_surf = pygame.image.load(cache_file)
                    if pygame.display.get_surface() is not None:
                        topo_surf = topo_surf.convert()
                except Exception:
                    topo_surf = None
            else:
                topo_surf = None

            if topo_surf is None:
                # Generate slot 1 micropoly mesh with low-poly 3D trees and Option A coastal waves
                from mapgen_web import get_cached_micropolys, build_micropoly_trees, build_coastal_surf_ribbon
                from render_island_micropolys import render_mesh
                from scipy.spatial import cKDTree

                graph_key = (
                    int(slot_state.get('seed', 777)),
                    slot_state.get('shape', 'radial'),
                    int(slot_state.get('points', 1000)),
                    int(slot_state.get('rivers', 25)),
                    round(float(slot_state.get('sharpness', 1.9)), 2),
                    0.0, 0.0, 0.0, 0.0,
                    round(float(slot_state.get('canyon_depth', 2.7)), 2),
                    round(float(slot_state.get('valley_width', 1.4)), 2)
                )

                triangles, _ = get_cached_micropolys(
                    gen,
                    graph_key,
                    int(slot_state.get('polys', 16000)),
                    float(slot_state.get('roughness', 3.0)),
                    float(slot_state.get('jitter', 0.22)),
                    float(slot_state.get('alpha', 0.0)),
                    float(slot_state.get('height_scale', 48.0)),
                    float(slot_state.get('smooth', 0.7)),
                    quad_fold=slot_state.get('quad_fold', True),
                    ridge_noise=float(slot_state.get('ridge_noise', 0.35)),
                    erosion_strength=float(slot_state.get('erosion_strength', 0.3)),
                    erosion_droplets=int(slot_state.get('erosion_droplets', 15000)),
                )

                mesh_pts = np.asarray([v for t in triangles for v in (t[0], t[1], t[2])], dtype=np.float32)
                mesh_tree = cKDTree(mesh_pts[:, :2])

                def sample_elevation(pts_xy):
                    dists, idxs = mesh_tree.query(pts_xy, k=min(3, len(mesh_pts)))
                    if dists.ndim == 1:
                        z = mesh_pts[idxs.flatten(), 2]
                    else:
                        w = 1.0 / np.maximum(dists, 1e-4)
                        w /= np.sum(w, axis=1, keepdims=True)
                        z = np.sum(mesh_pts[idxs, 2] * w, axis=1)
                    return np.maximum(0.0, z) + 0.08

                all_triangles = list(triangles)

                # Add 3D trees if enabled
                if slot_state.get('micropoly_trees', True):
                    tree_arr = build_micropoly_trees(
                        gen, sample_elevation,
                        height_scale=float(slot_state.get('height_scale', 48.0)),
                        tree_density=float(slot_state.get('tree_density', 1.28)),
                        subdivided_triangles=triangles
                    )
                    for i in range(0, len(tree_arr), 30):
                        p0 = np.array([tree_arr[i], tree_arr[i+1], tree_arr[i+2]], dtype=np.float64)
                        p1 = np.array([tree_arr[i+10], tree_arr[i+11], tree_arr[i+12]], dtype=np.float64)
                        p2 = np.array([tree_arr[i+20], tree_arr[i+21], tree_arr[i+22]], dtype=np.float64)
                        norm = np.array([tree_arr[i+3], tree_arr[i+4], tree_arr[i+5]], dtype=np.float64)
                        col = np.array([tree_arr[i+6]*255, tree_arr[i+7]*255, tree_arr[i+8]*255], dtype=np.float64)
                        elev = float(tree_arr[i+9])
                        all_triangles.append((p0, p1, p2, col, elev, False, 0, norm))

                # Add coastal waves (Option A) if enabled
                if slot_state.get('micropoly_waves', True):
                    surf_arr = build_coastal_surf_ribbon(
                        gen, ribbon_width=32.0 * float(slot_state.get('wave_intensity', 1.4))
                    )
                    for i in range(0, len(surf_arr), 30):
                        p0 = np.array([surf_arr[i], surf_arr[i+1], surf_arr[i+2]], dtype=np.float64)
                        p1 = np.array([surf_arr[i+10], surf_arr[i+11], surf_arr[i+12]], dtype=np.float64)
                        p2 = np.array([surf_arr[i+20], surf_arr[i+21], surf_arr[i+22]], dtype=np.float64)
                        norm = np.array([0.0, 0.0, 1.0], dtype=np.float64)
                        dist = float(surf_arr[i+9])
                        if dist < 0.25:
                            col = np.array([245.0, 252.0, 255.0])
                        elif dist < 0.55:
                            col = np.array([55.0, 185.0, 215.0])
                        else:
                            col = np.array([28.0, 120.0, 180.0])
                        all_triangles.append((p0, p1, p2, col, 0.0, False, 0, norm))

                topo_surf = render_mesh(
                    gen,
                    all_triangles,
                    width=2048,
                    height=2048,
                    sun_azimuth=float(slot_state.get('sun_azimuth', -45.0)),
                    sun_elevation=float(slot_state.get('sun_elevation', 24.0)),
                    sun_intensity=float(slot_state.get('sun_intensity', 1.15)),
                    ambient_intensity=float(slot_state.get('ambient_intensity', 0.45)),
                    rot_pitch=0.0,
                    rot_yaw=0.0,
                )
                try:
                    pygame.image.save(topo_surf, cache_file)
                except Exception:
                    pass
        else:
            topo_surf = terrain_renderer.get_or_generate_surface(
                seed, bbox, tiles=tiles, layout=layout,
                progress_callback=progress_cb
            )
        world['_cached_topo_surface'] = topo_surf
        world['_map_generation_done'] = True
        world['loading_modal'] = None
        if not world.get('_cached_from_disk', False) and not getattr(terrain_renderer, 'used_gpu', False) and not _is_voronoi:
            from world_cache import save_map_cache
            save_map_cache(world, topo_surf)
            world['_cached_from_disk'] = True


    pad_ratio = 0.0 if _is_voronoi else 0.18
    x0, y0, x1, y1 = bbox
    pad_x = (x1 - x0) * pad_ratio
    pad_y = (y1 - y0) * pad_ratio
    min_wx = x0 - pad_x
    min_wy = y0 - pad_y
    world_w = (x1 - x0) + 2 * pad_x
    world_h = (y1 - y0) + 2 * pad_y

    screen_x = int(min_wx * zoom + ox)
    screen_y = int(min_wy * zoom + oy)
    screen_x1 = int((min_wx + world_w) * zoom + ox)
    screen_y1 = int((min_wy + world_h) * zoom + oy)
    screen_w = max(1, screen_x1 - screen_x)
    screen_h = max(1, screen_y1 - screen_y)

    # Clip map rendering strictly to viewport
    map_clip_rect = pygame.Rect(0, TOP_BAR_H, MAP_RIGHT, HEIGHT - TOP_BAR_H - TICKER_H)
    prev_clip = surface.get_clip()
    surface.set_clip(map_clip_rect)

    if _is_voronoi:
        vw = MAP_RIGHT
        vh = HEIGHT - TOP_BAR_H - TICKER_H
        sim_time = world.get('frame', 0) * 0.04

        gpu_renderer = world.get('_micropoly_gpu_renderer')
        if gpu_renderer is None:
            from render_engine.gpu.micropoly_3d_renderer import get_micropoly_3d_renderer
            gpu_renderer = get_micropoly_3d_renderer()
            gpu_renderer.setup_scene(world['gen'], slot_state)
            world['_micropoly_gpu_renderer'] = gpu_renderer

        # Render 3D scene from GPU directly to Pygame surface
        gpu_surf = gpu_renderer.render(vw, vh, cam, sim_time=sim_time)
        surface.blit(gpu_surf, (0, TOP_BAR_H))
    else:
        pitch = cam.get('pitch', 0.0)
        if pitch < 0.5:
            if screen_w > 0 and screen_h > 0:
                scaled_topo = pygame.transform.smoothscale(topo_surf, (screen_w, screen_h))
                surface.blit(scaled_topo, (screen_x, screen_y))
        else:
            from worldview_camera import world_to_screen
            N = 48
            surf_w, surf_h = topo_surf.get_size()
            for i in range(N):
                wy0 = min_wy + (i / N) * world_h
                wy1 = min_wy + ((i + 1) / N) * world_h
                sy_top = int((i / N) * surf_h)
                sy_bot = int(((i + 1) / N) * surf_h)
                sh = max(1, sy_bot - sy_top)
                sub = topo_surf.subsurface((0, sy_top, surf_w, sh))

                sx0, sy0 = world_to_screen(world, min_wx, wy0)
                sx1, _ = world_to_screen(world, min_wx + world_w, wy0)
                _, sy1 = world_to_screen(world, min_wx, wy1)

                w = max(1, sx1 - sx0)
                h = max(1, sy1 - sy0 + 1)
                scaled = pygame.transform.scale(sub, (w, h))
                surface.blit(scaled, (sx0, sy0))

    # Build province color highlight map for the selected nation
    highlight_map = {}
    if sel is not None and getattr(sel, 'owner_nation', None) is not None:
        nation = sel.owner_nation
        provinces = getattr(nation, 'provinces', [])
        for i, prov in enumerate(provinces):
            color = PROVINCE_COLORS[i % len(PROVINCE_COLORS)]
            for r in prov.tiles:
                highlight_map[r.name] = (color, prov.name)

    # 1. Base Tile Overlays & 50% Transparent White Hex Outlines
    cam_state = (
        round(float(cam.get('zoom', 1.0)), 4),
        round(float(cam.get('target_x', 512.0)), 2),
        round(float(cam.get('target_y', 512.0)), 2),
        round(float(cam.get('pitch', 52.0)), 2),
        round(float(cam.get('yaw', 9.0)), 2),
        MAP_RIGHT, HEIGHT,
        id(getattr(world.get('_micropoly_gpu_renderer'), 'sample_elevation_func', None)),
        tuple((id(region), id(getattr(region, 'owner_nation', None)),
               bool(getattr(region, 'is_ocean', False)),
               float(getattr(region, 'elevation', 0.0))) for region in tiles),
    )

    if (
        world.get('_cached_hex_cam') == cam_state
        and '_cached_hex_geom' in world
        and '_cached_border_overlay' in world
    ):
        hex_geom = world['_cached_hex_geom']
        border_overlay = world['_cached_border_overlay']
    else:
        border_overlay = pygame.Surface((MAP_RIGHT, HEIGHT), pygame.SRCALPHA)
        hex_geom = []

        gpu_renderer = world.get('_micropoly_gpu_renderer')
        sample_elev = getattr(gpu_renderer, 'sample_elevation_func', None)
        hover_offset = 0.6  # Hover slightly above 3D mesh surface to prevent clipping and occlusion
        outline_alpha = 32 if _is_voronoi else 128

        from worldview_camera import project_pts_3d_to_screen, get_camera_mvp
        mvp = get_camera_mvp(world) if _is_voronoi else None

        for region in tiles:
            # User constraint: "don't show tiles in the sea;"
            is_sea = (
                getattr(region, 'is_ocean', False)
                or getattr(region, 'elevation', 0.0) <= 0.0
                or getattr(getattr(region, 'center', None), 'water', False)
                or getattr(getattr(region, 'center', None), 'ocean', False)
            )
            if is_sea:
                continue

            coords = layout.get(region.name)
            if coords is None:
                continue
            elev = getattr(region, 'elevation', 0.0)
            if _is_voronoi and hasattr(region, 'polygon') and region.polygon is not None and len(region.polygon) >= 3:
                # Precompute homogeneous 3D coordinates once per region
                if not hasattr(region, '_poly_homo') or getattr(region, '_poly_homo_sampler', None) != id(sample_elev):
                    poly_np = np.asarray(region.polygon, dtype=np.float32)
                    if sample_elev is not None:
                        z_vals = sample_elev(poly_np) + hover_offset
                        cz = float(sample_elev(np.array([[coords[0], coords[1]]], dtype=np.float32))[0]) + hover_offset
                    else:
                        slot_state = world.get('slot_state') or {}
                        h_scale = float(slot_state.get('height_scale', 48.0))
                        z_vals = np.full(len(poly_np), float(elev) * h_scale + hover_offset, dtype=np.float32)
                        cz = float(elev) * h_scale + hover_offset

                    region._poly_homo = np.column_stack([poly_np, z_vals, np.ones(len(poly_np), dtype=np.float32)])
                    region._center_homo = np.array([[coords[0], coords[1], cz, 1.0]], dtype=np.float32)
                    region._poly_homo_sampler = id(sample_elev)

                # Vectorized project to screen
                screen_pts = project_pts_3d_to_screen(world, region._poly_homo, mvp=mvp)
                valid = (screen_pts[:, 0] != -9999) & (screen_pts[:, 1] != -9999)
                if not np.all(valid):
                    screen_pts = screen_pts[valid]
                pts = [tuple(p) for p in screen_pts]

                c_screen = project_pts_3d_to_screen(world, region._center_homo, mvp=mvp)[0]
                cx, cy = int(c_screen[0]), int(c_screen[1])
            else:
                cx, cy = hex_px(world, *coords, elevation=elev)
                pts = hex_corners((cx, cy), HEX_SIZE * zoom - 1)

            if len(pts) < 3:
                continue

            hex_geom.append((region, cx, cy, pts))
            is_wild = (getattr(region, 'owner_nation', None) is None)
            if _is_voronoi:
                # Make wilderness boundaries clear and distinct with higher alpha
                line_alpha = 75 if is_wild else 35
                line_color = (205, 220, 210, line_alpha) if is_wild else (255, 255, 255, line_alpha)
            else:
                line_color = (255, 255, 255, 128)
            pygame.draw.polygon(border_overlay, line_color, pts, 1)

        world['_cached_hex_cam'] = cam_state
        world['_cached_hex_geom'] = hex_geom
        world['_cached_border_overlay'] = border_overlay

    # 1b. Render tile overlays and blit cartographic borders
    active_layer = world.get('map_layer', 'overview')
    for region, cx, cy, pts in hex_geom:
        if getattr(region, 'is_water', False):
            draw_elevation_terrain(surface, region, pts, cx, cy, zoom=zoom, frame=frame)
        owner = getattr(region, 'owner_nation', None)
        if owner is not None:
            draw_nation_overlay(surface, region, pts)
        else:
            # Unselected wilderness regions: subtle frontier outline
            pygame.draw.polygon(surface, (115, 130, 120), pts, 1)

        if active_layer in ('enclosure', 'exploitation', 'externalities'):
            draw_thematic_choropleth(surface, region, pts, active_layer, frame=frame)

    # Blit transparent hex/voronoi grid overlay
    surface.blit(border_overlay, (0, 0))

    # 2. National Borders, Province Highlights, and Hover Outline
    for region, cx, cy, pts in hex_geom:
        owner = getattr(region, 'owner_nation', None)
        if owner is not None:
            n_col = get_nation_color(owner.name)
            pygame.draw.polygon(surface, n_col, pts, max(2, int(2 * zoom)))

        if region.name in highlight_map:
            color, _pname = highlight_map[region.name]
            pygame.draw.polygon(surface, color, pts, max(3, int(3 * zoom)))

        if region is hover_region and region is not sel:
            h_col = (235, 215, 140) if owner is None else (255, 255, 255)
            pygame.draw.polygon(surface, h_col, pts, max(2, int(2 * zoom)))

    # Dedicated Selection Pass: RENDERED PROMINENTLY ABOVE ALL NATION & PROVINCE COLORS
    if sel is not None:
        sel_item = next((item for item in hex_geom if item[0] is sel), None)
        if sel_item is not None:
            _, scx, scy, spts = sel_item
            sel_w = max(5, int(5 * zoom))
            # 1. Dark outer drop-shadow halo for contrast on bright/snow terrain
            pygame.draw.polygon(surface, (15, 20, 25), spts, sel_w + 3)
            # 2. Wide, brilliant white selection perimeter above all nation/province colors
            pygame.draw.polygon(surface, (255, 255, 255), spts, sel_w)
            # 3. Inner golden accent ring for sovereign cartographic focus
            pygame.draw.polygon(surface, (255, 245, 180), spts, max(2, int(2 * zoom)))

    # 3. Connection Edges and Trade Arrows (RENDERED UNDER ALL TEXT)
    # Build screen-center lookup from already-computed hex_geom to avoid recomputing hex_px per edge pair
    _center_map = {region.name: (cx, cy) for region, cx, cy, pts in hex_geom}
    draw_edges(surface, world, center_map=_center_map)
    draw_trade_arrows(surface, world, center_map=_center_map)

    # 4. Text, City Titles, Stats Lines, and Badges (DYNAMIC OVERLAP-AWARE CULLING)
    layer_mode = world.get('map_layer', 'overview')

    label_candidates = []

    for region, cx, cy, pts in hex_geom:
        if cx < -60 or cx > MAP_RIGHT + 60 or cy < TOP_BAR_H - 40 or cy > HEIGHT - TICKER_H + 40:
            continue

        is_ocean = getattr(region, 'is_ocean', False) or getattr(region, 'elevation_meters', 0) < 0
        owner = getattr(region, 'owner_nation', None)

        is_nat_cap = False
        is_prov_cap = False
        raw_city = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
        if not is_ocean:
            is_nat_cap = getattr(region, 'is_national_capital', False) or (owner and owner.tiles and region == owner.tiles[0])
            is_prov_cap = getattr(region, 'is_provincial_capital', False)
            if not is_nat_cap and owner and getattr(owner, 'provinces', None):
                prov = next((p for p in owner.provinces if region in p.tiles), None)
                if prov and prov.tiles and region == prov.tiles[0]:
                    is_prov_cap = True

        city_title = f"* {raw_city}" if is_nat_cap else (f"+ {raw_city}" if is_prov_cap else raw_city)
        name_font = font_small if len(city_title) > 10 else font
        priority = get_tile_label_priority(region, world, is_nat_cap=is_nat_cap, is_prov_cap=is_prov_cap)

        # Pre-filter low-priority wilderness or non-capital tiles when zoomed far out
        if layer_mode == 'overview':
            if owner is None:
                if priority < 350 and zoom < 2.2:
                    continue
                if priority < 450 and zoom < 1.15:
                    continue
            else:
                if priority < 500 and zoom < 0.8:
                    continue
        else:
            if zoom < 1.0 and priority < 350:
                continue

        line1, line2, line3, c1, c2, c3 = tile_stats(region, layer_mode=layer_mode, world=world)

        # Compute label bounding box
        if not is_ocean:
            if layer_mode == 'overview':
                if owner is not None:
                    if is_nat_cap:
                        w = max(70, len(owner.name) * 8 + 24, len(city_title) * 8 + 16)
                        h = 44 if (zoom < 2.2 and region is not sel and region is not hover_region) else 68
                        box = pygame.Rect(cx - w // 2, cy - 28, w, h)
                    else:
                        w = max(50, len(city_title) * 7.5 + 14)
                        h = 24 if (zoom < 2.2 and region is not sel and region is not hover_region) else 54
                        box = pygame.Rect(cx - w // 2, cy - 16, w, h)
                else:
                    wild_title = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
                    w = max(50, len(wild_title) * 7 + 16)
                    h = 28
                    box = pygame.Rect(cx - w // 2, cy - 14, w, h)
            else:
                text_candidates = [city_title if owner else '']
                if line1: text_candidates.append(line1)
                if line2: text_candidates.append(line2)
                if line3: text_candidates.append(line3)
                max_len = max((len(s) for s in text_candidates), default=6)
                w = max(60, int(max_len * 7.5 + 14))
                h = max(24, len([s for s in text_candidates if s]) * 16 + 8)
                box = pygame.Rect(cx - w // 2, cy - 30 if owner else cy - 18, w, h)
        else:
            if layer_mode == 'overview' or not line1:
                continue
            w = 60
            h = 20
            box = pygame.Rect(cx - w // 2, cy - 10, w, h)

        r_key = getattr(region, 'id', None) or getattr(region, 'name', str(id(region)))
        label_candidates.append({
            'region': region,
            'r_key': r_key,
            'orig_cx': cx,
            'orig_cy': cy,
            'cx': cx,
            'cy': cy,
            'target_dx': 0.0,
            'target_dy': 0.0,
            'pts': pts,
            'priority': priority,
            'box': box,
            'test_rect': box.inflate(8, 6),
            'is_ocean': is_ocean,
            'owner': owner,
            'is_nat_cap': is_nat_cap,
            'is_prov_cap': is_prov_cap,
            'city_title': city_title,
            'name_font': name_font,
            'line1': line1, 'line2': line2, 'line3': line3,
            'c1': c1, 'c2': c2, 'c3': c3,
        })

    # Sort candidates by priority descending (selected tile > capitals > selected nation > regular nation > wilderness)
    # Secondary key by r_key prevents tie-breaking flip-flops between frames
    label_candidates.sort(key=lambda c: (c['priority'], str(c['r_key'])), reverse=True)

    occupied_rects = []
    accepted_tiles = set()

    for cand in label_candidates:
        # Priority >= 900 (selected tile or hovered tile) is NEVER culled, never shifted
        if cand['priority'] >= 900:
            cand['target_dx'] = 0.0
            cand['target_dy'] = 0.0
            occupied_rects.append(cand['test_rect'])
            accepted_tiles.add(cand['region'])
            continue

        # Check collision against all previously accepted higher-priority labels
        blocker_idx = cand['test_rect'].collidelist(occupied_rects)
        if blocker_idx == -1:
            cand['target_dx'] = 0.0
            cand['target_dy'] = 0.0
            occupied_rects.append(cand['test_rect'])
            accepted_tiles.add(cand['region'])
        else:
            # Overlap detected! Test micro-shifting within the tile's polygon
            shift_result = find_label_micro_shift(cand, occupied_rects, occupied_rects[blocker_idx])
            if shift_result is not None:
                nx, ny, shifted_test_rect, dx, dy = shift_result
                cand['target_dx'] = float(dx)
                cand['target_dy'] = float(dy)
                cand['box'] = cand['box'].move(dx, dy)
                cand['test_rect'] = shifted_test_rect
                # Register shifted rect so lower-priority tiles (e.g. wilderness) avoid or yield to this space
                occupied_rects.append(shifted_test_rect)
                accepted_tiles.add(cand['region'])
            else:
                cand['target_dx'] = 0.0
                cand['target_dy'] = 0.0

    # Smooth label offset animation with inertia (1-3 px/frame) to prevent jumping and flickering
    label_offsets = world.setdefault('_label_offsets', {})
    MAX_SHIFT_PER_FRAME = 2.0  # 1-3 pixel shift per frame

    for cand in label_candidates:
        r_key = cand['r_key']
        if cand['region'] not in accepted_tiles:
            # Decay culled tile offsets towards (0, 0)
            if r_key in label_offsets:
                cur_dx, cur_dy = label_offsets[r_key]
                if abs(cur_dx) > 0.2 or abs(cur_dy) > 0.2:
                    label_offsets[r_key] = (cur_dx * 0.7, cur_dy * 0.7)
                else:
                    label_offsets[r_key] = (0.0, 0.0)
            continue

        target_dx = cand['target_dx']
        target_dy = cand['target_dy']

        cur_state = label_offsets.get(r_key)
        if cur_state is None:
            cur_dx, cur_dy = target_dx, target_dy
        else:
            cur_dx, cur_dy = cur_state

        diff_x = target_dx - cur_dx
        diff_y = target_dy - cur_dy
        dist = math.hypot(diff_x, diff_y)

        if dist <= MAX_SHIFT_PER_FRAME:
            cur_dx = target_dx
            cur_dy = target_dy
        else:
            step = min(MAX_SHIFT_PER_FRAME, max(0.8, dist * 0.25))
            cur_dx += (diff_x / dist) * step
            cur_dy += (diff_y / dist) * step

        label_offsets[r_key] = (cur_dx, cur_dy)

        # Apply smooth animated center for rendering
        cand['cx'] = int(round(cand['orig_cx'] + cur_dx))
        cand['cy'] = int(round(cand['orig_cy'] + cur_dy))

    # Render only accepted labels
    for cand in label_candidates:
        region = cand['region']
        if region not in accepted_tiles:
            continue

        cx, cy = cand['cx'], cand['cy']
        is_ocean = cand['is_ocean']
        owner = cand['owner']
        is_nat_cap = cand['is_nat_cap']
        is_prov_cap = cand['is_prov_cap']
        city_title = cand['city_title']
        name_font = cand['name_font']
        line1, line2, line3 = cand['line1'], cand['line2'], cand['line3']
        c1, c2, c3 = cand['c1'], cand['c2'], cand['c3']

        if not is_ocean:
            if layer_mode == 'overview':
                if owner is not None:
                    if is_nat_cap:
                        # National Capital (bold star badge)
                        draw_text_with_shadow(surface, font_small, f"★ {owner.name.upper()}", (cx, cy - 24), (255, 230, 140))
                        draw_text_with_shadow(surface, name_font, city_title, (cx, cy - 10), (255, 255, 255))
                    elif is_prov_cap:
                        draw_text_with_shadow(surface, font_small, city_title, (cx, cy - 12), (210, 240, 255))
                    else:
                        draw_text_with_shadow(surface, font_small, city_title, (cx, cy - 10), (230, 230, 230))

                    if (zoom >= 2.2) or (region is sel) or (region is hover_region):
                        if line2:
                            draw_text_with_shadow(surface, font_small, line2, (cx, cy + 6), c2)
                        if line3:
                            draw_text_with_shadow(surface, font_small, line3, (cx, cy + 20), c3)
                else:
                    # Unselected wilderness regions: show natural territory title and altitude
                    elev_m = getattr(region, 'elevation_meters', int(region.elevation * 3000))
                    wild_title = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
                    draw_text_with_shadow(surface, font_small, f"◇ {wild_title}", (cx, cy - 8), (210, 230, 220))
                    draw_text_with_shadow(surface, font_small, f"{elev_m}m", (cx, cy + 8), (155, 185, 170))
            else:
                # Other Layer Modes (Physical, Population, Economy, Production, Military)
                if owner is not None:
                    draw_text_with_shadow(surface, name_font, city_title, (cx, cy - 28), (255, 255, 255))
                if line1:
                    draw_text_with_shadow(surface, font_small, line1, (cx, cy - 10 if owner else cy - 14), c1)
                if line2:
                    draw_text_with_shadow(surface, font_small, line2, (cx, cy + 8), c2)
                if line3:
                    draw_text_with_shadow(surface, font_small, line3, (cx, cy + 24), c3)
        else:
            # On ocean tiles: in non-overview layers, display minimal line if present
            if layer_mode != 'overview' and line1:
                draw_text_with_shadow(surface, font_small, line1, (cx, cy), c1)

        if not is_ocean:
            if region is sel or region is hover_region or (zoom >= 2.2 and owner is not None):
                draw_terrain_glyph(surface, region, cx, cy - 34)
                draw_activity_badges(surface, region, cx, cy, font_small)
                draw_pop_delta(surface, region, cx, cy, font_small)
                draw_tile_progress_bars(surface, region, cx, cy, font_small, world)

    surface.set_clip(prev_clip)
