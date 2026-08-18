#!/usr/bin/env python3
"""
REGNUM v3_wilderness — Pygame hex-world viewer for the 9x9 honeycomb.

Thin presentation layer over the conserved-money engine (gdd.md): it builds
sim_world.build_world() (9x9 = 81 tiles, true 6-neighbor hex topology, each
nation a contiguous 3/4/5-tile cluster), steps the world with the EXACT
sim_world.main() turn order + per-currency audit (including the ledger DESTROY
exemption), and renders the honeycomb tinted by owner nation.  Unclaimed
(wilderness) tiles render grey with their homesteader count + wilderness_pop.

Features:
  - True hex grid: every interior tile is edge-adjacent to all six neighbors.
  - Right panel: the V2a per-tile chart dashboard (Prices, Population/Hunger,
    Production, Trade flow, Gov income, Gini/Migration) for the hovered or
    pinned tile, plus the per-currency audit readout.  Unclaimed tiles are
    guarded (no bank/gov/factions => empty/inert charts, no crashes).
  - Camera: pan (arrows / WASD / middle-drag), zoom (+ / - / mouse wheel).
  - Ticker: bottom strip scrolling MIGRATE / CLAIM / DESTROY events.
  - Audit readout in the panel; red flag on > $5.0 SUPPLY SHIFT / leak.

Controls:
    Space  : play / pause (auto-advance ~150 ms/turn)
    S / -> : step one turn (when paused)
    Arrows / WASD : pan the camera
    + / -  : zoom in / out (mouse wheel too)
    Tab    : chart grid view    1 .. 6 : zoom one chart
    Click  : pin a tile (charts stay); hover works over the unpinned map
    H / ?  : help menu
    Esc/Q  : quit

Usage:
    python3 worldview.py
"""

import os
import random
import sys

# IMPORTANT: keep this line BEFORE pygame so headless tests (SDL_VIDEODRIVER=dummy)
# and interactive runs both work.
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from goods import Goods
from logger import logInit
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade
from regime import step_regime
from migration import run_migrations
from trade_settle import settle_wilderness
from claims import check_and_apply_claims
from hexmap import (rectangular_hex_layout, axial_to_pixel, hex_corners,
                    pixel_to_axial, hex_bbox)
import ledger
from sim_world import build_world, GRID_ROWS, GRID_COLS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 1400, 900
MAP_RIGHT = 1060            # map area spans x in [0, MAP_RIGHT)
PANEL_LEFT = MAP_RIGHT + 12
HEX_SIZE = 50
FPS = 60
TURN_MS = 150
TOP_BAR_H = 52             # Civ-style selected-nation stats strip at the top
TICKER_H = 64              # bottom world-event ticker strip

# Nation palette matching sim_nation.draw_map (matplotlib map).
NATION_COLORS = {
    'Alpha': (141, 211, 199),    # #8dd3c7
    'Beta':  (255, 255, 179),    # #ffffb3
    'Gamma': (190, 186, 218),    # #bebada
}
WILD_COLOR = (96, 96, 100)       # unclaimed wilderness tiles
WILD_EDGE = (70, 70, 76)
HEX_EDGE = (20, 20, 20)
BG = (24, 24, 30)
PANEL_BG = (40, 40, 48)
TEXT = (235, 235, 235)
DIM = (170, 170, 180)
RED = (235, 90, 90)
GREEN = (120, 210, 120)
ACCENT = (240, 200, 90)
EDGE_LINE = (58, 58, 68)         # wired-edge strokes (connectivity overlay)

# Ticker event colors.
MIG_C = (120, 200, 220)
CLAIM_C = (240, 200, 90)
DESTROY_C = (235, 90, 90)

# Chart series colors.
_FOOD_C = (120, 200, 80)
_WOOD_C = (190, 150, 70)
_FURN_C = (90, 140, 230)
_POP_C = (230, 230, 230)
_HUNGER_C = (235, 90, 90)
_EXP_C = (110, 210, 120)
_IMP_C = (230, 110, 100)
_TAX_C = (240, 200, 90)
_TAR_C = (110, 150, 235)
_INH_C = (200, 120, 230)
_GINI_C = (200, 120, 230)
_MIG_C = (120, 200, 220)
_CHART_BOX = (72, 72, 84)

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

# Camera clamp margins (px) around the play area.
_MARGIN = 24

# Keeps track of last-turn population per region name for delta badges.
_pops = {}


def _layout():
    return rectangular_hex_layout(GRID_ROWS, GRID_COLS)


def _reverse_layout():
    return {v: k for k, v in _layout().items()}


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

def _clamp_cam(world):
    """Keep the (scaled) hex bbox within the map viewport, centered if smaller."""
    cam = world['cam']
    zoom = cam['zoom']
    x0, y0, x1, y1 = world['bbox']
    sx0, sy0, sx1, sy1 = x0 * zoom, y0 * zoom, x1 * zoom, y1 * zoom
    map_w, map_h = MAP_RIGHT - 2 * _MARGIN, (HEIGHT - TOP_BAR_H - TICKER_H) - 2 * _MARGIN
    # X clamp
    if sx1 - sx0 <= map_w:
        cam['ox'] = (MAP_RIGHT - (sx0 + sx1)) / 2.0
    else:
        cam['ox'] = max(_MARGIN - sx0, min(MAP_RIGHT - _MARGIN - sx1, cam['ox']))
    # Y clamp (play area between top bar and ticker)
    top = TOP_BAR_H + _MARGIN
    bottom = HEIGHT - TICKER_H - _MARGIN
    if sy1 - sy0 <= bottom - top:
        cam['oy'] = (top + bottom - (sy0 + sy1)) / 2.0
    else:
        cam['oy'] = max(top - sy0, min(bottom - sy1, cam['oy']))


def _hex_px(world, q, r):
    x, y = axial_to_pixel(q, r, HEX_SIZE * world['cam']['zoom'])
    return (int(x + world['cam']['ox']), int(y + world['cam']['oy']))


def _tile_at(world, mx, my):
    """Return the Region under screen pixel (mx, my), or None."""
    if mx >= MAP_RIGHT or my < TOP_BAR_H or my > HEIGHT - TICKER_H:
        return None
    cam = world['cam']
    q, r = pixel_to_axial((mx - cam['ox']) / cam['zoom'],
                          (my - cam['oy']) / cam['zoom'],
                          HEX_SIZE)
    name = world['reverse'].get((q, r))
    return world['by_name'].get(name) if name is not None else None


def _selected_nation(world):
    pinned = world.get('selected_region')
    if pinned is not None and getattr(pinned, 'owner_nation', None) is not None:
        return pinned.owner_nation
    return world['nations'][0] if world['nations'] else None


# ---------------------------------------------------------------------------
# World stepping (mirrors sim_world.main() exactly)
# ---------------------------------------------------------------------------

def build_world_view(seed=None):
    """Build the 9x9 hex world + prepare viewer state.

    ``seed=None`` seeds from entropy; an int makes the world reproducible.
    """
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()
    tiles, nations, _grid = build_world(seed=seed)
    currencies = [n.currency for n in nations]
    layout = _layout()
    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None
                   and not getattr(o, 'wilderness', False)]
    by_name = {r.name: r for r in tiles}
    world = {
        'tiles': tiles,
        'nations': nations,
        'currencies': currencies,
        'pair_orders': pair_orders,
        'by_name': by_name,
        'layout': layout,
        'reverse': _reverse_layout(),
        'bbox': hex_bbox(layout, HEX_SIZE),
        'cam': {'ox': 0.0, 'oy': 0.0, 'zoom': 1.0},
        'selected_region': None,
        'turn': 0,
        'playing': False,
        'hover_region': None,
        'frame': 0,
        'view': 0,             # 0 = chart grid; 1..6 = zoom one chart
        'window': 100,         # chart sparkline window (turns)
        'currency_totals': {c: fx.audit_currency_total(tiles, c)
                            for c in currencies},
        'violations': [],
        'ticker_events': [],      # bounded list of {kind, text, t}
        'scope': 'tile',          # 'tile' = per-region charts; 'nation' = aggregates
        'help_open': False,
        'help_scroll': 0,
    }
    _clamp_cam(world)
    return world


def _ticker_push(world, t, kind, text, color, n=140):
    world['ticker_events'].append({'t': t, 'kind': kind, 'text': text,
                                   'color': color})
    if len(world['ticker_events']) > n:
        del world['ticker_events'][:len(world['ticker_events']) - n]


def step_world(world):
    """Advance one turn of the engine; mirror sim_world.main() turn body."""
    t = world['turn'] + 1
    tiles = world['tiles']
    currencies = world['currencies']
    violations = []

    curr_before = {c: fx.audit_currency_total(tiles, c) for c in currencies}
    pair_orders = world['pair_orders']

    for r in tiles:
        pending = {}
        for other in tiles:
            if other is r or other not in r.neighbors.values():
                continue
            for g, entries in pending_imports(r, other).items():
                pending.setdefault(g, []).extend(entries)
        r.pending_imports = pending
        r._auction_import_sales = {}

    # v3 provinces: shared institutionals run ONCE per province; member tiles
    # step their per-tile economy only.  Legacy/unclaimed tiles keep r.step().
    _provinces = [p for n in world['nations']
                  for p in getattr(n, 'provinces', [])]
    _prov_tiles = {}
    for p in _provinces:
        for r in p.tiles:
            _prov_tiles[r.name] = r
    for p in _provinces:
        p.step(t)
    for r in tiles:
        if r.name in _prov_tiles:
            continue
        r.step(t)

    for r in tiles:
        for rt in r._all_routes():
            rt.advance()
            rt.deliver_pending()

    resolve_parked(tiles)

    for r, other in pair_orders:
        settle_trade(t, other, r)

    fx.cycle_all_markets(tiles, t)

    # v3: migration events -> ticker.
    mig_events = run_migrations(t, tiles)
    for ev in mig_events:
        _ticker_push(world, t, 'MIGRATE',
                     f"MIGRATE a{ev['agent_id']} {ev['from']} -> {ev['to']} "
                     f"({ev['via']})", MIG_C)

    # v3: claims -> ticker; refresh pairs when a tile becomes claimed.
    claim_events = check_and_apply_claims(t, tiles, world['nations'])
    for ev in claim_events:
        _ticker_push(world, t, 'CLAIM',
                     f"CLAIM {ev['nation']} claimed {ev['tile']} "
                     f"({ev['origin_count']}/{ev['pop']} {ev['share']*100:.1f}%)",
                     CLAIM_C)
    if claim_events:
        world['pair_orders'] = [(r, o) for r in tiles for o in tiles if o is not r
                                and r.neighbors.get(o.name) is not None
                                and not getattr(o, 'wilderness', False)
                                and not getattr(r, 'wilderness', False)]

    # v3: trader wilderness settlement.
    for r in tiles:
        if getattr(r, 'owner_nation', None) is None or not r.trader_agents:
            continue
        for other in r.neighbors.values():
            if not getattr(other, 'wilderness', False):
                continue
            if not any(getattr(a, 'is_homesteader', False) for a in other.agents):
                continue
            for trader in r.trader_agents:
                settle_wilderness(trader, other, t)

    for n in world['nations']:
        step_regime(n, t)

    for r, other in world['pair_orders']:
        desk = r.forex_desks.get(other.name)
        if desk is not None:
            ppp = max(0.1, other.cost_of_living) / max(0.1, r.cost_of_living)
            desk.update(0, bank=r.bank, fx_regime='managed', ppp_target=ppp)
            if getattr(r, 'destination_region', None) is other:
                desk.save_rate(r)

    # Audit: exempt the ledger-recorded destruction.
    for c in currencies:
        delta = fx.audit_currency_total(tiles, c) - curr_before[c]
        recorded = ledger.cleared(t, c)
        unaccounted = delta + recorded
        if abs(unaccounted) > 5.0:
            violations.append((t, c, unaccounted))
    # Ledger destruction events -> ticker (deduped per turn).
    for ev in ledger.all_events():
        if ev['t'] != t:
            continue
        _ticker_push(world, t, 'DESTROY',
                     f"DESTROY {ev['currency'] or '-'} ${ev['amount']:.2f} "
                     f"({ev['reason']})", DESTROY_C)

    for r in tiles:
        for other in tiles:
            if other is r or other not in r.neighbors.values():
                continue
            turn_export = sum(r.export_val[g][-1]
                              for g in [Goods.food, Goods.wood, Goods.furniture]
                              if r.export_val[g])
            turn_import = sum(r.import_val[g][-1]
                              for g in [Goods.food, Goods.wood, Goods.furniture]
                              if r.import_val[g])
            r.cumulative_trade_balance += (turn_export - turn_import)
            r.trade_flow_log.append(turn_export - turn_import)

    world['turn'] = t
    world['currency_totals'] = {c: fx.audit_currency_total(tiles, c)
                                for c in currencies}
    world['violations'] = violations
    return violations


# ---------------------------------------------------------------------------
# Rendering helpers (map)
# ---------------------------------------------------------------------------

def _nation_color(region):
    owner = getattr(region, 'owner_nation', None)
    if owner is not None:
        return NATION_COLORS.get(owner.name, (150, 150, 150))
    return WILD_COLOR


def _region_pop(region):
    if region.total_population:
        return region.total_population[-1]
    return len(region.agents)


def _homesteaders(region):
    return sum(1 for a in region.agents if getattr(a, 'is_homesteader', False))


def _tile_stats(region):
    """Summary lines printed on each hex (claimed vs unclaimed)."""
    if getattr(region, 'owner_nation', None) is None:
        hs = _homesteaders(region)
        wild = getattr(region, 'wilderness_pop', 0)
        return f"hs {hs}+{wild}n", f"food --", ""
    pop = _region_pop(region)
    food = region.recipes[Goods.food]['price']
    traders = sum(1 for a in region.agents if a.is_trader)
    return f"pop {pop}", f"food ${food:.2f}", f"tr {traders}"


def _draw_terrain_glyph(surface, region, cx, cy):
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


def _draw_pop_heat(surface, region, pts, cx, cy):
    """Brighten the hex fill by population density (claimed tiles only)."""
    if getattr(region, 'owner_nation', None) is None:
        pygame.draw.polygon(surface, WILD_COLOR, pts)
        return
    pop = _region_pop(region)
    max_pop = 420.0
    f = min(0.45, 0.18 * (pop / max_pop))
    extra = (int(255 * f), int(255 * f), int(245 * f))
    base = _nation_color(region)
    blended = tuple(min(255, int(v) + e) for v, e in zip(base, extra))
    pygame.draw.polygon(surface, blended, pts)


def _trade_anim(world):
    """Animated arrows: last-turn net trade flow on claimed pairs."""
    out = []
    for r, other in world['pair_orders']:
        flow = r.trade_flow_log[-1] if r.trade_flow_log else 0.0
        if abs(flow) < 0.5:
            continue
        c1 = _hex_px(world, *world['layout'][r.name])
        c2 = _hex_px(world, *world['layout'][other.name])
        width = max(1, min(8, int(abs(flow) / 1500.0) + 1))
        out.append((c1, c2, width, flow > 0))
    return out


def _draw_edges(surface, world):
    """Static thin strokes on every wired edge (connectivity overlay)."""
    for r, other in world['pair_orders']:
        c1 = _hex_px(world, *world['layout'][r.name])
        c2 = _hex_px(world, *world['layout'][other.name])
        pygame.draw.line(surface, EDGE_LINE, c1, c2, 1)
    for r in world['tiles']:
        if getattr(r, 'owner_nation', None) is not None:
            continue
        for other in r.neighbors.values():
            if other.name < r.name:
                continue
            c1 = _hex_px(world, *world['layout'][r.name])
            c2 = _hex_px(world, *world['layout'][other.name])
            pygame.draw.line(surface, (40, 40, 48), c1, c2, 1)


def _draw_trade_arrows(surface, world):
    """Animated dots on claimed-pair edges scaled by recent net flow."""
    frame = world.get('frame', 0)
    for c1, c2, width, forward in _trade_anim(world):
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


def _draw_activity_badges(surface, region, cx, cy, font_small):
    """Small indicators around the hex (claimed-only readouts)."""
    if getattr(region, 'owner_nation', None) is None:
        pygame.draw.circle(surface, (90, 210, 120), (cx, cy - 48), 8)
        tag = font_small.render("W", True, (255, 255, 255))
        surface.blit(tag, tag.get_rect(center=(cx, cy - 48)))
        if _homesteaders(region) > 0:
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


def _draw_pop_delta(surface, region, cx, cy, font_small):
    """+B / -D per-turn population delta badge under the hex name."""
    if getattr(region, 'owner_nation', None) is None:
        return
    if not region.total_population or len(region.total_population) < 2:
        return
    prev = _pops.get(region.name)
    cur = region.total_population[-1]
    if prev is None:
        _pops[region.name] = cur
        return
    delta = cur - prev
    _pops[region.name] = cur
    txt = font_small.render(f"+{delta}" if delta >= 0 else f"{delta}",
                            True, GREEN if delta >= 0 else RED)
    surface.blit(txt, txt.get_rect(center=(cx, cy - 38)))


def _province_members(world, region):
    """Tiles in the same province as *region* (or just the tile if none)."""
    prov = getattr(region, 'province', None)
    if prov is not None:
        return list(prov.tiles)
    return [region]


def _draw_hex_map(surface, world, font, font_small):
    tiles = world['tiles']
    layout = world['layout']
    highlighted = set()
    sel = world.get('selected_region')
    if sel is not None:
        highlighted = {r.name for r in _province_members(world, sel)}
    for region in tiles:
        coords = layout.get(region.name)
        if coords is None:
            continue
        cx, cy = _hex_px(world, *coords)
        pts = hex_corners((cx, cy), HEX_SIZE * world['cam']['zoom'] - 1)
        _draw_pop_heat(surface, region, pts, cx, cy)
        edge = WILD_EDGE if getattr(region, 'owner_nation', None) is None else HEX_EDGE
        pygame.draw.polygon(surface, edge, pts, 2)
        if region.name in highlighted:
            # v3: selecting a tile highlights its WHOLE province.
            pygame.draw.polygon(surface, ACCENT, pts, 4)
        name_surf = font.render(region.name, True, TEXT)
        surface.blit(name_surf, name_surf.get_rect(center=(cx, cy - 20)))
        line1, line2, line3 = _tile_stats(region)
        s1 = font_small.render(line1, True, TEXT)
        s2 = font_small.render(line2, True, DIM)
        surface.blit(s1, s1.get_rect(center=(cx, cy - 2)))
        surface.blit(s2, s2.get_rect(center=(cx, cy + 12)))
        if line3:
            s3 = font_small.render(line3, True, DIM)
            surface.blit(s3, s3.get_rect(center=(cx, cy + 26)))
        _draw_terrain_glyph(surface, region, cx, cy - 34)
        _draw_activity_badges(surface, region, cx, cy, font_small)
        _draw_pop_delta(surface, region, cx, cy, font_small)
    _draw_edges(surface, world)
    _draw_trade_arrows(surface, world)


# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------

def _draw_top_bar(surface, world, font_small):
    """Civ-style top strip: stats for the currently selected nation."""
    n = _selected_nation(world)
    pygame.draw.rect(surface, (34, 34, 42), (0, 0, MAP_RIGHT, TOP_BAR_H))
    pygame.draw.line(surface, HEX_EDGE, (0, TOP_BAR_H), (MAP_RIGHT, TOP_BAR_H), 2)
    font = font_small
    if n is None:
        head = font.render("REGNUM v3 — 9x9 Hex World", True, ACCENT)
        surface.blit(head, (8, 14))
        return
    tiles = n.tiles
    pop = sum(r.total_population[-1] if r.total_population else len(r.agents)
              for r in tiles)
    tr = n.treasury()
    col = (sum(r.cost_of_living for r in tiles) / len(tiles)
           if tiles else 0.0)
    gdp = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in tiles)
    exports = sum(sum(v) for r in tiles for v in r.export_val.values())
    imports = sum(sum(v) for r in tiles for v in r.import_val.values())
    net = exports - imports
    ruling = getattr(n, 'ruling_faction', None)
    ruler = f"  ruling {ruling}" if ruling else ""
    head = font.render(
        f"{n.name} ({n.currency})  {n.regime_type}  legit {n.legitimacy:.2f}"
        f"{ruler}  tiles {len(tiles)}", True, ACCENT)
    surface.blit(head, (8, 6))
    stats = [
        (f"Pop {pop}", TEXT),
        (f"Treasury ${tr['total']:,.0f} ({tr['food']} food)", TEXT),
        (f"CoL {col:.2f}", TEXT),
        (f"GDP ${gdp:,.0f}", TEXT),
        (f"Ex ${exports:,.0f}", _EXP_C),
        (f"Im ${imports:,.0f}", _IMP_C),
        (f"Net {'+' if net >= 0 else ''}{net:,.0f}",
         GREEN if net >= 0 else RED),
    ]
    x = 8
    for text, color in stats:
        label = font.render(text, True, color)
        surface.blit(label, (x, 30))
        x += label.get_width() + 22


# ---------------------------------------------------------------------------
# V2a chart machinery (ported from hexview.py, with wilderness guards)
# ---------------------------------------------------------------------------

def _sum_turns(lists):
    """Per-turn totals across a list of equal-length per-turn series."""
    n = max((len(s) for s in lists), default=0)
    return [sum(s[i] for s in lists if i < len(s)) for i in range(n)]


def _tile_charts(region):
    """Six (title, kind, series, colors, labels) charts; safe for unclaimed."""
    g = lambda gd: region.price_log.get(gd, [])
    pop = region.total_population or []
    hs = [region.hungry_log.get(gd, []) for gd in (Goods.food, Goods.wood,
                                                   Goods.furniture)]
    hungry = ([sum(row) for row in zip(*hs)] if all(hs)
              else [sum(row) for row in zip(*[h for h in hs if h])])
    exp = [region.export_val.get(gd, []) for gd in (Goods.food, Goods.wood,
                                                    Goods.furniture)]
    imp = [region.import_val.get(gd, []) for gd in (Goods.food, Goods.wood,
                                                    Goods.furniture)]
    gov = getattr(region, 'gov', None)
    income = getattr(gov, 'income_log', []) if gov is not None else []
    tax = [e.get('tax', 0.0) for e in income]
    tariff = [e.get('tariff', 0.0) for e in income]
    inherit = [e.get('inheritance', 0.0) for e in income]
    return [
        ("Prices", "line",
         [g(Goods.food), g(Goods.wood), g(Goods.furniture)],
         [_FOOD_C, _WOOD_C, _FURN_C], ["food", "wood", "furn"]),
        ("Population / Hunger", "line",
         [pop, hungry], [_POP_C, _HUNGER_C], ["pop", "hungry"]),
        ("Production", "line",
         [region.production_log.get(gd, []) for gd in (Goods.food, Goods.wood,
                                                       Goods.furniture)],
         [_FOOD_C, _WOOD_C, _FURN_C], ["food", "wood", "furn"]),
        ("Trade flow", "bars",
         [_sum_turns(exp), _sum_turns(imp)],
         [_EXP_C, _IMP_C], ["export", "import"]),
        ("Gov income", "stack",
         [tax, tariff, inherit],
         [_TAX_C, _TAR_C, _INH_C], ["tax", "tariff", "inherit"]),
        ("Gini / Migration", "line",
         [region.gini_log.get(Goods.food, []), region.migration_intent_log],
         [_GINI_C, _MIG_C], ["gini", "migr"]),
    ]


def _chart_labels(surface, labels, colors, font, rect, y_start=2, step=13):
    y = y_start
    for label, color in zip(labels, colors):
        txt = font.render(label, True, color)
        surface.blit(txt, (rect[0] + 4, rect[1] + y))
        y += step


def _plot_line_chart(surface, rect, series_list, colors, labels, window, font):
    """Axes box + one normalized polyline per series (last *window* turns)."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, _CHART_BOX, rect, 1)
    data = [s[-window:] for s in series_list]
    if not any(data):
        _chart_labels(surface, labels, colors, font, rect)
        return
    vals = [v for d in data for v in d]
    vmin, vmax = min(vals), max(vals)
    if vmax - vmin < 1e-9:
        vmax = vmin + 1.0
    n = max(len(d) for d in data)
    if n < 2:
        _chart_labels(surface, labels, colors, font, rect)
        return
    label_h = 14 + 13 * len(colors)
    iw, ih = w - 12, h - label_h - 6
    for d, color in zip(data, colors):
        pts = []
        for j, v in enumerate(d):
            x = x0 + 6 + j * iw / (n - 1)
            y = y0 + h - 5 - ((v - vmin) / (vmax - vmin)) * ih
            pts.append((x, y))
        pygame.draw.lines(surface, color, False, pts, 2)
    _chart_labels(surface, labels, colors, font, rect)


def _plot_bar_pairs(surface, rect, series_list, colors, labels, window, font):
    """Side-by-side per-turn bars for two series (e.g. export vs import)."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, _CHART_BOX, rect, 1)
    n = max((len(s) for s in series_list), default=0)
    n_show = min(window, n)
    if n_show <= 0:
        _chart_labels(surface, labels, colors, font, rect)
        return
    vmax = max((v for s in series_list for v in s[-n_show:]), default=1.0)
    if vmax <= 0:
        vmax = 1.0
    stride = max(1, n_show // 90)
    label_h = 14 + 13 * len(colors)
    iw = (w - 12) / n_show
    nser = len(series_list)
    for i in range(n_show):
        if i % stride:
            continue
        bw = max(2, iw * 0.85 / nser)
        for k, (s, color) in enumerate(zip(series_list, colors)):
            v = s[i] if i < len(s) else 0.0
            bh = (v / vmax) * (h - label_h - 8)
            bx = x0 + 6 + i * iw + k * bw
            if bh > 0.5:
                pygame.draw.rect(surface, color,
                                 (bx, y0 + h - 6 - bh, bw, bh))
    _chart_labels(surface, labels, colors, font, rect)


def _plot_stacked_bars(surface, rect, series_list, colors, labels, window, font):
    """Stacked per-turn bars (gov income decomposition)."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, _CHART_BOX, rect, 1)
    n = max((len(s) for s in series_list), default=0)
    n_show = min(window, n)
    if n_show <= 0:
        _chart_labels(surface, labels, colors, font, rect)
        return
    totals = [sum(s[i] for s in series_list if i < len(s))
              for i in range(n_show)]
    vmax = max(totals, default=1.0)
    if vmax <= 0:
        vmax = 1.0
    stride = max(1, n_show // 90)
    label_h = 14 + 13 * len(colors)
    iw = (w - 12) / n_show
    for i in range(n_show):
        if i % stride:
            continue
        bw = max(2, iw * 0.85)
        bx = x0 + 6 + i * iw
        y = y0 + h - 6
        for s, color in zip(series_list, colors):
            v = s[i] if i < len(s) else 0.0
            bh = (v / vmax) * (h - label_h - 8)
            if bh > 0.5:
                pygame.draw.rect(surface, color, (bx, y - bh, bw, bh))
                y -= bh
    _chart_labels(surface, labels, colors, font, rect)


def _draw_chart_cell(surface, chart, rect, font, font_small, window):
    """Draw one chart (title + plot) into *rect*."""
    title, kind, series, colors, labels = chart
    tsurf = font_small.render(title, True, ACCENT)
    surface.blit(tsurf, (rect[0] + 4, rect[1] + 2))
    plot_rect = (rect[0], rect[1] + 20, rect[2], rect[3] - 20)
    if kind == 'line':
        _plot_line_chart(surface, plot_rect, series, colors, labels, window,
                         font_small)
    elif kind == 'bars':
        _plot_bar_pairs(surface, plot_rect, series, colors, labels, window,
                        font_small)
    elif kind == 'stack':
        _plot_stacked_bars(surface, plot_rect, series, colors, labels, window,
                           font_small)


def _draw_chart_grid(surface, charts, font, font_small, window, y0, y1):
    """2-column x 3-row grid of all six charts in the panel area."""
    left = PANEL_LEFT + 6
    right = WIDTH - 8
    top, bottom = y0, y1
    cols, rows = 2, 3
    cw = (right - left) // cols
    ch = (bottom - top) // rows
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(charts):
                break
            rect = (left + c * cw, top + r * ch, cw - 4, ch - 4)
            _draw_chart_cell(surface, charts[idx], rect, font, font_small,
                             window)
            idx += 1


def _draw_chart_large(surface, chart, font, font_small, window, y0, y1):
    """Single chart drawn large (zoom view 1..6)."""
    rect = (PANEL_LEFT + 6, y0, WIDTH - 14 - PANEL_LEFT, y1 - y0)
    _draw_chart_cell(surface, chart, rect, font, font_small, window)


# ---------------------------------------------------------------------------
# Right panel (header + audit + per-tile charts)
# ---------------------------------------------------------------------------

def _draw_regime_readout(surface, region, font_small, y):
    """M3 line: protest / unrest / top faction / owner nation - unclaimed safe."""
    if getattr(region, 'owner_nation', None) is None:
        line = font_small.render("unclaimed wilderness", True, DIM)
        surface.blit(line, (PANEL_LEFT, y))
        return
    protest = (region.protest_energy_log[-1]
               if region.protest_energy_log else 0.0)
    unrest = region.unrest_log[-1] if region.unrest_log else {}
    stage = unrest.get('stage', 'calm')
    top = None
    if region.faction_support_log:
        snap = region.faction_support_log[-1]
        if snap:
            top = max(snap, key=lambda k: snap[k])
    owner = getattr(region, 'owner_nation', None)
    owner_s = ""
    if owner is not None:
        ruling = getattr(owner, 'ruling_faction', None)
        owner_s = f"  {owner.name}: legit {owner.legitimacy:.2f}" \
                  + (f" ruling {ruling}" if ruling else "")
    line = font_small.render(
        f"protest {protest:.1f}  unrest {stage}"
        + (f"  top {top}" if top else "")
        + owner_s, True, DIM)
    surface.blit(line, (PANEL_LEFT, y))


def _draw_panel(surface, world, font, font_small):
    """Right-hand panel: header, play state, audit, per-tile charts."""
    d = TOP_BAR_H
    panel_w = WIDTH - PANEL_LEFT - 6
    panel_h = HEIGHT - 20 - d - TICKER_H
    pygame.draw.rect(surface, PANEL_BG,
                     (PANEL_LEFT - 10, 10 + d, panel_w + 4, panel_h))

    title = font.render("REGNUM — Hex World", True, ACCENT)
    surface.blit(title, (PANEL_LEFT, 20 + d))

    t_ = world['turn']
    turn_line = font_small.render(f"Turn: {t_}  win={world['window']}t", True, TEXT)
    surface.blit(turn_line, (PANEL_LEFT, 50 + d))

    cursors = world.get('currency_totals', {})
    y = 80 + d
    for c, total in cursors.items():
        line = font_small.render(f"{c}: ${total:,.0f}", True, TEXT)
        surface.blit(line, (PANEL_LEFT, y))
        y += 22

    if world.get('playing'):
        pn = font_small.render("[ PLAYING ]  Space=pause", True, GREEN)
    else:
        pn = font_small.render("[ PAUSED ]  S=step  Space=play", True, DIM)
    surface.blit(pn, (PANEL_LEFT, 148 + d))

    region = world.get('selected_region') or world.get('hover_region')
    chart_top = 185 + d
    chart_bottom = HEIGHT - TICKER_H - 96
    scope = world.get('scope', 'tile')
    if scope == 'nation':
        # per-NATION scope: aggregate the owner nation's stats instead of the
        # tile charts.  (V toggles tile <-> nation.)
        n = _selected_nation(world)
        if n is not None:
            owner_pop = sum(r.total_population[-1] if r.total_population
                            else len(r.agents) for r in n.tiles)
            tr = n.treasury()
            col = (sum(r.cost_of_living for r in n.tiles) / max(1, len(n.tiles)))
            gdp = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in n.tiles)
            lines = [
                (f"{n.name} ({n.currency})  {n.regime_type}", ACCENT),
                (f"legit {n.legitimacy:.2f}  tiles {len(n.tiles)}", TEXT),
                (f"pop {owner_pop}", TEXT),
                (f"treasury ${tr['total']:,.0f} ({tr['food']} food)", TEXT),
                (f"avg CoL {col:.2f}", DIM),
                (f"GDP/turn ${gdp:,.0f}", GREEN),
            ]
            yy = chart_top + 4
            for text, color in lines:
                line = font_small.render(text, True, color)
                surface.blit(line, (PANEL_LEFT, yy))
                yy += 20
            hint = font_small.render(
                f"NATION scope (V=tile)  press V to toggle", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_bottom + 6))
            _draw_regime_readout(surface, region if region is not None else n.tiles[0],
                                 font_small, chart_bottom + 24)
        return
    if region is not None:
        prov_s = ""
        if getattr(region, 'province', None) is not None:
            prov_s = f"  [{region.province.name}]"
        head = font_small.render(f"{region.name}{prov_s}", True, TEXT)
        surface.blit(head, (PANEL_LEFT, chart_top - 6))
        # per-region CoL + climate on the tile card header line.
        col_line = font_small.render(
            f"CoL {region.cost_of_living:.2f}  {region.climate}  "
            f"(V=nation)", True, DIM)
        surface.blit(col_line, (PANEL_LEFT, chart_top - 6 + 16))
        charts = _tile_charts(region)
        view = world.get('view', 0)
        if view == 0:
            _draw_chart_grid(surface, charts, font, font_small, world['window'],
                             chart_top + 4, chart_bottom)
            hint = font_small.render(
                f"{region.name}: Tab=grid  1-6=zoom", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_bottom + 6))
        else:
            idx = max(0, min(len(charts) - 1, view - 1))
            _draw_chart_large(surface, charts[idx], font, font_small,
                              world['window'], chart_top + 4, chart_bottom)
            hint = font_small.render(
                f"{charts[idx][0]}  (Tab=grid)", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_bottom + 6))
        _draw_regime_readout(surface, region, font_small, chart_bottom + 24)
    else:
        hint = font_small.render("Hover or click a hex for its charts", True, DIM)
        surface.blit(hint, (PANEL_LEFT, 190 + d))

    audit_y = HEIGHT - TICKER_H - 28
    if world.get('violations'):
        v1 = font.render("AUDIT VIOLATION", True, RED)
        surface.blit(v1, (PANEL_LEFT, audit_y - 4))
        vline = font_small.render(
            "; ".join(f"T{v[0]} {v[1]} {v[2]:+.2f}"
                      for v in world['violations']),
            True, RED)
        surface.blit(vline, (PANEL_LEFT, audit_y + 18))
    else:
        ok = font.render("Conserved: 0 LEAK / 0 SHIFT", True, GREEN)
        surface.blit(ok, (PANEL_LEFT, audit_y))


# ---------------------------------------------------------------------------
# Ticker
# ---------------------------------------------------------------------------

def _draw_ticker(surface, world, font_small):
    """Bottom strip: scrolling archive of MIGRATE / CLAIM / DESTROY events."""
    y0 = HEIGHT - TICKER_H
    pygame.draw.rect(surface, (34, 34, 42), (0, y0, WIDTH, TICKER_H))
    pygame.draw.line(surface, HEX_EDGE, (0, y0), (WIDTH, y0), 2)
    title = font_small.render("Ticker", True, ACCENT)
    surface.blit(title, (8, y0 + 4))
    events = world['ticker_events']
    visible = 3
    start = max(0, len(events) - visible)
    yy = y0 + 6
    for ev in events[start:]:
        line = font_small.render(f"T{ev['t']}  {ev['text']}", True, ev['color'])
        surface.blit(line, (78, yy))
        yy += 18


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def _draw_help(surface, world, font_small):
    if not world.get('help_open', False):
        return
    title_font = pygame.font.Font(None, 30)
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((16, 16, 22, 242))
    surface.blit(overlay, (0, 0))
    surface.blit(title_font.render('REGNUM v3 — Hex World Controls', True, ACCENT),
                 (24, 14))
    lines = [
        'Space .......... play / pause (~150 ms/turn)',
        'S or -> ........ step one turn (while paused)',
        'Arrows / WASD .. pan the camera',
        '+ / - / wheel .. zoom in / out',
        'Tab ............ chart-grid view (hovered/pinned tile)',
        '1 .. 6 ......... zoom one of the six charts',
        'Click .......... pin a tile (charts stay anchored)',
        'H or ? ......... toggle this help',
        'Esc ............ close help first; Q quits either way',
        '',
        'Grey hex = UNCLAIMED wilderness (no bank/gov/factions).  Green W tag',
        '= frontier; orange dot = homesteaders present.  Colored hex = owned',
        'by a nation; brighter fill = higher population (heat).  Thin cyan',
        'arrows = net trade flow on claimed edges.  Bottom strip = world',
        'ticker (MIGRATE cyan / CLAIM gold / DESTROY red).  Right panel =',
        'per-currency audit + six live per-tile charts (guarded for',
        'unclaimed tiles).',
    ]
    max_w = WIDTH - 72
    wrapped = []
    for ln in lines:
        cur = ''
        for w in ln.split(' '):
            test = (cur + ' ' + w).strip()
            if font_small.size(test)[0] <= max_w or not cur:
                cur = test
            else:
                wrapped.append(cur)
                cur = w
        wrapped.append(cur)
    y = 52
    for text in wrapped:
        color = TEXT if text else (16, 16, 22)
        surface.blit(font_small.render(text, True, color), (24, y))
        y += 20


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------

def render_frame(surface, world):
    """Draw one full frame (map + top bar + panel + ticker + help)."""
    font = pygame.font.Font(None, 28)
    font_small = pygame.font.Font(None, 22)
    surface.fill(BG)
    _draw_top_bar(surface, world, font_small)
    _draw_hex_map(surface, world, font, font_small)
    _draw_panel(surface, world, font, font_small)
    _draw_ticker(surface, world, font_small)
    _draw_help(surface, world, font_small)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    seed = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--seed' and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        else:
            i += 1
    logInit()
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()
    pygame.init()
    surface = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("REGNUM v3 — Hex World")
    clock = pygame.time.Clock()

    world = build_world_view(seed=seed)
    _pops.clear()
    for r in world['tiles']:
        if getattr(r, 'owner_nation', None) is not None:
            _pops[r.name] = _region_pop(r)

    last_tick = pygame.time.get_ticks()
    running = True
    drag = False
    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked = _tile_at(world, *event.pos)
                if clicked is not None:
                    # v3: preserve the chart view (e.g. zoomed pop graph) when
                    # pinning a different tile.
                    world['selected_region'] = clicked
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                drag = True
                pygame.mouse.get_rel()
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                drag = False
            elif event.type == pygame.MOUSEMOTION and drag:
                dx, dy = pygame.mouse.get_rel()
                world['cam']['ox'] += dx
                world['cam']['oy'] += dy
                _clamp_cam(world)
            elif event.type == pygame.MOUSEWHEEL:
                z = world['cam']['zoom']
                world['cam']['zoom'] = max(0.4, min(2.5, z * (1.15 ** event.y)))
                _clamp_cam(world)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if world.get('help_open'):
                        world['help_open'] = False
                    else:
                        running = False
                elif event.key == pygame.K_q:
                    running = False
                elif event.key == pygame.K_h or event.key == pygame.K_QUESTION:
                    world['help_open'] = not world.get('help_open', False)
                elif world.get('help_open'):
                    pass
                elif event.key == pygame.K_SPACE:
                    world['playing'] = not world['playing']
                    last_tick = now
                elif event.key in (pygame.K_s, pygame.K_RIGHT):
                    if not world['playing']:
                        step_world(world)
                elif event.key == pygame.K_TAB:
                    world['view'] = 0
                elif event.key == pygame.K_v:
                    world['scope'] = 'nation' if world.get('scope', 'tile') == 'tile' else 'tile'
                elif pygame.K_1 <= event.key <= pygame.K_6:
                    world['view'] = event.key - pygame.K_1 + 1
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    world['cam']['ox'] += 30
                    _clamp_cam(world)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    world['cam']['ox'] -= 30
                    _clamp_cam(world)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    world['cam']['oy'] += 30
                    _clamp_cam(world)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    pass  # s steps when paused; pan-down handled below
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    world['cam']['zoom'] = min(2.5, world['cam']['zoom'] * 1.15)
                    _clamp_cam(world)
                elif event.key == pygame.K_MINUS:
                    world['cam']['zoom'] = max(0.4, world['cam']['zoom'] / 1.15)
                    _clamp_cam(world)

        if world['playing'] and now - last_tick >= TURN_MS:
            step_world(world)
            last_tick = now
        world['frame'] = (world.get('frame', 0) + 1) % 600

        world['hover_region'] = None
        mx, my = pygame.mouse.get_pos()
        if mx < MAP_RIGHT and TOP_BAR_H <= my <= HEIGHT - TICKER_H:
            world['hover_region'] = _tile_at(world, mx, my)

        render_frame(surface, world)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()