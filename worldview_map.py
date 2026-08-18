"""
Hexagonal map rendering, terrain glyphs, population heatmaps, trade animations, and status badges.
"""

import pygame
from goods import Goods
from hexmap import hex_corners
from worldview_camera import hex_px, HEX_SIZE

NATION_COLORS = {
    'Alpha': (141, 211, 199),
    'Beta':  (255, 255, 179),
    'Gamma': (190, 186, 218),
}
WILD_COLOR = (96, 96, 100)
WILD_EDGE = (70, 70, 76)
HEX_EDGE = (20, 20, 20)
TEXT = (235, 235, 235)
DIM = (170, 170, 180)
RED = (235, 90, 90)
GREEN = (120, 210, 120)
ACCENT = (240, 200, 90)
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


def tile_stats(region):
    """Summary lines printed on each hex (claimed vs unclaimed)."""
    if getattr(region, 'owner_nation', None) is None:
        hs = homesteaders(region)
        wild = getattr(region, 'wilderness_pop', 0)
        return f"hs {hs}+{wild}n", f"food --", ""
    pop = region_pop(region)
    food = region.recipes[Goods.food]['price']
    traders = sum(1 for a in region.agents if a.is_trader)
    return f"pop {pop}", f"food ${food:.2f}", f"tr {traders}"


def draw_terrain_glyph(surface, region, cx, cy):
    """Small vector terrain markers under the hex center."""
    y = cy + 22
    if region.terrain.get(Goods.food, 1.0) > 1.3:
        pts = [(cx, y - 8), (cx - 9, y + 6), (cx + 9, y + 6)]
        pygame.draw.polygon(surface, (240, 200, 90), pts)
    if region.terrain.get(Goods.wood, 1.0) > 1.3:
        pts = [(cx, y - 8), (cx - 9, y + 6), (cx + 9, y + 6)]
        pygame.draw.polygon(surface, (110, 190, 110), pts)
    if region.climate == 'cold':
        pygame.draw.circle(surface, (240, 245, 250), (cx, y), 4)


def draw_pop_heat(surface, region, pts, cx, cy):
    """Brighten the hex fill by population density (claimed tiles only)."""
    if getattr(region, 'owner_nation', None) is None:
        pygame.draw.polygon(surface, WILD_COLOR, pts)
        return
    pop = region_pop(region)
    max_pop = 420.0
    f = min(0.45, 0.18 * (pop / max_pop))
    extra = (int(255 * f), int(255 * f), int(245 * f))
    base = nation_color(region)
    blended = tuple(min(255, int(v) + e) for v, e in zip(base, extra))
    pygame.draw.polygon(surface, blended, pts)


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
        pygame.draw.circle(surface, (90, 210, 120), (cx, cy - 48), 8)
        tag = font_small.render("W", True, (255, 255, 255))
        surface.blit(tag, tag.get_rect(center=(cx, cy - 48)))
        if homesteaders(region) > 0:
            pygame.draw.circle(surface, BADGE_ORANGE, (cx + 32, cy - 34), 7)
        return
    food = region.recipes[Goods.food]['price']
    neighbors = [n for n in region.neighbors.values()
                 if getattr(n, 'recipes', None) and not getattr(n, 'wilderness', False)]
    if neighbors:
        avg = sum(n.recipes[Goods.food]['price'] for n in neighbors) / len(neighbors)
        ring_color = HOT_RING if food > avg * 1.15 else \
                     COLD_RING if food < avg * 0.85 else None
        if ring_color is not None:
            pygame.draw.circle(surface, ring_color, (cx, cy), HEX_SIZE - 8, 2)
    dr = region.demand_ratio_log.get(Goods.food, [])
    if dr and dr[-1] > 1.5:
        pygame.draw.circle(surface, BADGE_ORANGE, (cx + 32, cy - 34), 7)
    if any(region.hungry_log[g] and region.hungry_log[g][-1] > 5
           for g in (Goods.food, Goods.wood, Goods.furniture)):
        pygame.draw.circle(surface, BADGE_RED, (cx - 32, cy - 34), 7)
    traders = sum(1 for a in region.agents if a.is_trader)
    if traders > 0:
        tag = font_small.render(f"T{traders}", True, BADGE_TRA)
        surface.blit(tag, (cx + 24, cy + 30))
    gini = region.gini_log.get(Goods.food, [])
    if gini and gini[-1] > 0.6:
        pygame.draw.circle(surface, BADGE_GINI, (cx - 32, cy + 30), 5)
    unrest = region.unrest_log[-1] if region.unrest_log else {}
    stage = unrest.get('stage', 'calm')
    if stage != 'calm' and stage in UNREST_COLORS:
        pygame.draw.circle(surface, UNREST_COLORS[stage], (cx, cy - 48), 8)
        tag = font_small.render(stage[0].upper(), True, (255, 255, 255))
        surface.blit(tag, tag.get_rect(center=(cx, cy - 48)))


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
    surface.blit(txt, txt.get_rect(center=(cx, cy - 38)))


def province_members(world, region):
    """Tiles in the same province as *region* (or just the tile if none)."""
    prov = getattr(region, 'province', None)
    if prov is not None:
        return list(prov.tiles)
    return [region]


def draw_hex_map(surface, world, font, font_small):
    """Draw full hex grid map with terrain, population heatmap, badges, edges, and trade animations."""
    tiles = world['tiles']
    layout = world['layout']
    highlighted = set()
    sel = world.get('selected_region')
    if sel is not None:
        highlighted = {r.name for r in province_members(world, sel)}
    for region in tiles:
        coords = layout.get(region.name)
        if coords is None:
            continue
        cx, cy = hex_px(world, *coords)
        pts = hex_corners((cx, cy), HEX_SIZE * world['cam']['zoom'] - 1)
        draw_pop_heat(surface, region, pts, cx, cy)
        edge = WILD_EDGE if getattr(region, 'owner_nation', None) is None else HEX_EDGE
        pygame.draw.polygon(surface, edge, pts, 2)
        if region.name in highlighted:
            pygame.draw.polygon(surface, ACCENT, pts, 4)
        name_surf = font.render(region.name, True, TEXT)
        surface.blit(name_surf, name_surf.get_rect(center=(cx, cy - 20)))
        line1, line2, line3 = tile_stats(region)
        s1 = font_small.render(line1, True, TEXT)
        s2 = font_small.render(line2, True, DIM)
        surface.blit(s1, s1.get_rect(center=(cx, cy - 2)))
        surface.blit(s2, s2.get_rect(center=(cx, cy + 12)))
        if line3:
            s3 = font_small.render(line3, True, DIM)
            surface.blit(s3, s3.get_rect(center=(cx, cy + 26)))
        draw_terrain_glyph(surface, region, cx, cy - 34)
        draw_activity_badges(surface, region, cx, cy, font_small)
        draw_pop_delta(surface, region, cx, cy, font_small)
    draw_edges(surface, world)
    draw_trade_arrows(surface, world)
