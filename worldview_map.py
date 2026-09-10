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
from worldview_camera import hex_px, HEX_SIZE, MAP_RIGHT, TOP_BAR_H, TICKER_H, HEIGHT
from heightmap import get_cached_topographic_surface

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

        top_badge = f"Soil: {fert*100:.0f}% • Nut: {nut*100:.0f}%"
        stat_line = f"Smog: {air_p:.0f} | Water: {wat_p:.0f}"
        chem_tags = []
        if use_f:
            chem_tags.append("FERT")
        if use_p:
            chem_tags.append("PEST")
        tr_line = f"Chem: {', '.join(chem_tags)}" if chem_tags else "Natural Organic"

        b_col = (100, 220, 140) if fert >= 0.90 and nut >= 0.90 else ((240, 180, 80) if fert >= 0.60 else (225, 100, 80))
        t_col = (235, 90, 90) if (air_p > 20.0 or wat_p > 20.0) else ((140, 210, 255) if chem_tags else GREEN)
        return top_badge, stat_line, tr_line, b_col, TEXT, t_col

    # 6. OVERVIEW LAYER (Default)
    if is_ocean or owner is None:
        return "", "", "", DIM, DIM, DIM

    # Claimed tile: Show Nation Name ONLY on nation capital; Province Name ONLY on province seat
    is_nation_capital = (owner.tiles and region == owner.tiles[0])
    prov = next((p for p in getattr(owner, 'provinces', []) if region in p.tiles), None)
    is_prov_capital = (prov and prov.tiles and region == prov.tiles[0])

    top_badge = ""
    badge_col = NATION_COLORS.get(owner.name, ACCENT)
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


def draw_thematic_choropleth(surface, region, pts, layer_mode, frame=0):
    """Draw Layer 7 (Land Tenure / Enclosure) or Layer 8 (Exploitation / Strikes) choropleth tint."""
    is_ocean = getattr(region, 'is_ocean', False) or getattr(region, 'elevation', 0) < 0
    if is_ocean:
        return

    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)
    w = max(1, int(max_x - min_x) + 2)
    h = max(1, int(max_y - min_y) + 2)

    tint_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    local_pts = [(p[0] - min_x, p[1] - min_y) for p in pts]

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
    """Render geographic trade routes: rivers, mountain passes, standard paths, and alpine barriers."""
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
        c1 = hex_px(world, *layout[r.name])
        c2 = hex_px(world, *layout[other.name])
        
        edge = em.get_edge(r.name, other.name) if em else None
        if edge and edge.is_river:
            # Fluvial River Corridor (Glowing Cyan-Blue)
            pygame.draw.line(surface, (50, 130, 210), c1, c2, 3)
            pygame.draw.line(surface, (120, 215, 255), c1, c2, 1)
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
                    c1 = hex_px(world, *layout[name_a])
                    c2 = hex_px(world, *layout[name_b])
                    # Draw mid-point barrier hash
                    mx = (c1[0] + c2[0]) // 2
                    my = (c1[1] + c2[1]) // 2
                    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
                    dist = max(1.0, math.sqrt(dx*dx + dy*dy))
                    nx, ny = -dy / dist * 6, dx / dist * 6
                    pygame.draw.line(surface, (190, 50, 50), (int(mx - nx), int(my - ny)), (int(mx + nx), int(my + ny)), 2)


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
    surface.blit(txt, txt.get_rect(center=(cx + 34, cy - 24)))


def draw_text_with_shadow(surface, font, text, center, color, shadow_color=(12, 12, 16)):
    """Render text with a soft drop shadow for ultra-crisp readability over elevation terrain."""
    cx, cy = center
    # 4-direction shadow
    for sx, sy in [(cx-1, cy), (cx+1, cy), (cx, cy-1), (cx, cy+1)]:
        s_surf = font.render(text, True, shadow_color)
        surface.blit(s_surf, s_surf.get_rect(center=(sx, sy)))
    t_surf = font.render(text, True, color)
    surface.blit(t_surf, t_surf.get_rect(center=(cx, cy)))


def draw_tile_progress_bars(surface, region, cx, cy, font_small, world):
    """Draw sleek on-map progress bars overlayed on hex tiles for active construction, science, and diffusion."""
    if getattr(region, 'is_ocean', False) or getattr(region, 'elevation_meters', 0) < 0:
        return

    owner = getattr(region, 'owner_nation', None)
    is_cap = (owner is not None and owner.tiles and region == owner.tiles[0])
    
    from ui_icons import get_icon
    bar_w = 78
    bar_h = 12
    bar_y = cy + 34
    
    # 1. Construction Progress Bar
    projects = getattr(region, 'construction_projects', [])
    active_proj = next((p for p in projects if getattr(p, 'status', '') == 'in_progress'), None)
    
    if active_proj is not None:
        pct = min(1.0, max(0.0, active_proj.turns_elapsed / max(1, active_proj.total_turns)))
        bx = int(cx - bar_w // 2)
        by = int(bar_y)
        
        # Background track
        bg_rect = pygame.Rect(bx, by, bar_w, bar_h)
        pygame.draw.rect(surface, (18, 20, 28, 230), bg_rect, border_radius=3)
        
        # Progress fill (Golden Amber / Construction Yellow)
        fill_w = max(2, int((bar_w - 2) * pct))
        fill_rect = pygame.Rect(bx + 1, by + 1, fill_w, bar_h - 2)
        pygame.draw.rect(surface, (235, 175, 45), fill_rect, border_radius=2)
        
        # Border
        pygame.draw.rect(surface, (120, 110, 80), bg_rect, 1, border_radius=3)
        
        # Mini icon & text
        icon = get_icon(active_proj.recipe.name, size=10)
        surface.blit(icon, (bx + 3, by + 1))
        
        short_name = active_proj.recipe.name.replace('_', ' ').capitalize()[:6]
        txt = font_small.render(f"{short_name} {active_proj.turns_elapsed}/{active_proj.total_turns}t", True, (255, 255, 255))
        surface.blit(txt, (bx + 15, by + 1))
        
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
                bx = int(cx - bar_w // 2)
                by = int(bar_y)
                
                bg_rect = pygame.Rect(bx, by, bar_w, bar_h)
                pygame.draw.rect(surface, (18, 20, 32, 230), bg_rect, border_radius=3)
                
                fill_w = max(2, int((bar_w - 2) * pct))
                fill_rect = pygame.Rect(bx + 1, by + 1, fill_w, bar_h - 2)
                pygame.draw.rect(surface, (60, 190, 245), fill_rect, border_radius=2)
                
                pygame.draw.rect(surface, (70, 120, 160), bg_rect, 1, border_radius=3)
                
                icon = get_icon('rare_minerals', size=10)
                surface.blit(icon, (bx + 3, by + 1))
                
                short_tech = tech.name.split()[0][:6]
                txt = font_small.render(f"R&D {short_tech} {int(pct*100)}%", True, (255, 255, 255))
                surface.blit(txt, (bx + 15, by + 1))
                
        elif active_diff is not None and is_cap:
            t_id, diff_prog = active_diff
            tech = TECH_CATALOG.get(t_id)
            if tech:
                bx = int(cx - bar_w // 2)
                by = int(bar_y)
                
                bg_rect = pygame.Rect(bx, by, bar_w, bar_h)
                pygame.draw.rect(surface, (24, 18, 32, 230), bg_rect, border_radius=3)
                
                fill_w = max(2, int((bar_w - 2) * diff_prog))
                fill_rect = pygame.Rect(bx + 1, by + 1, fill_w, bar_h - 2)
                pygame.draw.rect(surface, (170, 110, 240), fill_rect, border_radius=2)
                
                pygame.draw.rect(surface, (110, 80, 150), bg_rect, 1, border_radius=3)
                
                icon = get_icon('im', size=10)
                surface.blit(icon, (bx + 3, by + 1))
                
                short_tech = tech.name.split()[0][:6]
                txt = font_small.render(f"Diff {short_tech} {int(diff_prog*100)}%", True, (255, 255, 255))
                surface.blit(txt, (bx + 15, by + 1))


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
    cam = world['cam']
    zoom = cam['zoom']
    ox, oy = cam['ox'], cam['oy']
    frame = world.get('frame', 0)
    bbox = world['bbox']

    # 0. Draw Continuous Topographic Elevation Background Surface with Contour Lines & Hillshading
    seed = world.get('terrain_seed', world.get('seed', 42))

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

        topo_surf = get_cached_topographic_surface(
            seed, bbox, tiles=tiles, layout=layout, canvas_w=2400, canvas_h=1800,
            progress_callback=progress_cb
        )
        world['_cached_topo_surface'] = topo_surf
        world['_map_generation_done'] = True
        world['loading_modal'] = None
        if not world.get('_cached_from_disk', False):
            from world_cache import save_map_cache
            save_map_cache(world, topo_surf)
            world['_cached_from_disk'] = True


    x0, y0, x1, y1 = bbox
    pad_x = (x1 - x0) * 0.18
    pad_y = (y1 - y0) * 0.18
    min_wx = x0 - pad_x
    min_wy = y0 - pad_y
    world_w = (x1 - x0) + 2 * pad_x
    world_h = (y1 - y0) + 2 * pad_y

    screen_x = int(min_wx * zoom + ox)
    screen_y = int(min_wy * zoom + oy)
    screen_w = int(world_w * zoom)
    screen_h = int(world_h * zoom)

    # Clip map rendering strictly to viewport
    map_clip_rect = pygame.Rect(0, TOP_BAR_H, MAP_RIGHT, HEIGHT - TOP_BAR_H - TICKER_H)
    prev_clip = surface.get_clip()
    surface.set_clip(map_clip_rect)

    if screen_w > 0 and screen_h > 0:
        scaled_topo = pygame.transform.smoothscale(topo_surf, (screen_w, screen_h))
        surface.blit(scaled_topo, (screen_x, screen_y))

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
    border_overlay = pygame.Surface((MAP_RIGHT, HEIGHT), pygame.SRCALPHA)
    hex_geom = []

    for region in tiles:
        coords = layout.get(region.name)
        if coords is None:
            continue
        cx, cy = hex_px(world, *coords)
        pts = hex_corners((cx, cy), HEX_SIZE * zoom - 1)
        hex_geom.append((region, cx, cy, pts))

        # 1a. Ocean wave shimmer (if water)
        draw_elevation_terrain(surface, region, pts, cx, cy, zoom=zoom, frame=frame)

        # 1b. Semi-Transparent Nation Territory Overlay & Thematic Choropleth
        draw_nation_overlay(surface, region, pts)
        active_layer = world.get('map_layer', 'overview')
        if active_layer in ('enclosure', 'exploitation', 'externalities'):
            draw_thematic_choropleth(surface, region, pts, active_layer, frame=frame)

        # 1c. 50% Transparent White Hex Outline (RGBA: 255, 255, 255, 128)
        pygame.draw.polygon(border_overlay, (255, 255, 255, 128), pts, 1)

    # Blit 50% transparent white hex grid overlay
    surface.blit(border_overlay, (0, 0))

    # 2. National Borders, Province Highlights, and Selection
    for region, cx, cy, pts in hex_geom:
        owner = getattr(region, 'owner_nation', None)
        if owner is not None:
            n_col = NATION_COLORS.get(owner.name, (255, 255, 255))
            pygame.draw.polygon(surface, n_col, pts, max(2, int(2 * zoom)))

        if region.name in highlight_map:
            color, _pname = highlight_map[region.name]
            pygame.draw.polygon(surface, color, pts, max(3, int(3 * zoom)))

        if sel is region:
            pygame.draw.polygon(surface, (255, 255, 255), pts, 4 if region.name not in highlight_map else 2)

    # 3. Connection Edges and Trade Arrows (RENDERED UNDER ALL TEXT)
    draw_edges(surface, world)
    draw_trade_arrows(surface, world)

    # 4. Text, City Titles, Stats Lines, and Badges (RENDERED ON TOP OF TRADE LINES)
    layer_mode = world.get('map_layer', 'overview')
    for region, cx, cy, pts in hex_geom:
        is_ocean = getattr(region, 'is_ocean', False) or getattr(region, 'elevation_meters', 0) < 0
        owner = getattr(region, 'owner_nation', None)

        if not is_ocean:
            raw_city = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
            is_nat_cap = getattr(region, 'is_national_capital', False) or (owner and owner.tiles and region == owner.tiles[0])
            is_prov_cap = getattr(region, 'is_provincial_capital', False)
            if not is_nat_cap and owner and getattr(owner, 'provinces', None):
                prov = next((p for p in owner.provinces if region in p.tiles), None)
                if prov and prov.tiles and region == prov.tiles[0]:
                    is_prov_cap = True

            if is_nat_cap:
                city_title = f"* {raw_city}"
            elif is_prov_cap:
                city_title = f"+ {raw_city}"
            else:
                city_title = raw_city

            name_font = font_small if len(city_title) > 10 else font
            line1, line2, line3, c1, c2, c3 = tile_stats(region, layer_mode=layer_mode, world=world)

            if layer_mode == 'overview':
                if owner is not None:
                    if line1:
                        # Nation or Province Capital
                        draw_text_with_shadow(surface, font_small, line1, (cx, cy - 32), c1)
                        draw_text_with_shadow(surface, name_font, city_title, (cx, cy - 18), (255, 255, 255))
                    else:
                        # Regular member city tile (moved comfortably high up)
                        draw_text_with_shadow(surface, name_font, city_title, (cx, cy - 24), (255, 255, 255))
                    
                    if line2:
                        draw_text_with_shadow(surface, font_small, line2, (cx, cy + 6), c2)
                    if line3:
                        draw_text_with_shadow(surface, font_small, line3, (cx, cy + 24), c3)
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
            if layer_mode != 'overview':
                line1, line2, line3, c1, c2, c3 = tile_stats(region, layer_mode=layer_mode, world=world)
                if line1:
                    draw_text_with_shadow(surface, font_small, line1, (cx, cy), c1)

        if not is_ocean:
            draw_terrain_glyph(surface, region, cx, cy - 34)
            draw_activity_badges(surface, region, cx, cy, font_small)
            draw_pop_delta(surface, region, cx, cy, font_small)
            draw_tile_progress_bars(surface, region, cx, cy, font_small, world)

    surface.set_clip(prev_clip)
