#!/usr/bin/env python3
"""
REGNUM V1/V2 — Pygame hex-map viewer (Civ-style connected hexagons).

Thin presentation layer over the conserved-money engine (gdd.md): it reads
sim_nation.build_world(), steps the world with the exact same turn order +
per-currency audit as sim_nation.main(), and renders an axial pointy-top
hex map tinted by owner nation.

V2a: per-tile hover chart dashboard.  Hovering a hex turns the right panel
into a grid of six mini-charts drawn in pure pygame from that tile's logs
(prices, population/hunger, production, trade flow, gov income, gini/
migration).  Tab shows the grid, 1-6 zooms one chart, and every chart
updates live as the world steps.

Controls:
    Space  : play / pause (auto-advance ~150 ms/turn)
    S / -> : step one turn (when paused)
    Tab    : chart grid view
    1 .. 6 : zoom one of the six hover charts
    N      : toggle the national HUD strip
    H / ?  : help menu explaining every UI/UX element (Up/Down scroll)
    Esc/Q  : quit (Esc closes help first)
    Hover  : tile tooltip + chart dashboard

Usage:
    python3 hexview.py
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
from world_trade import pending_imports, resolve_parked, settle_trade, trader_wealth
from sim_nation import build_world
from regime import step_regime
from hexmap import (LAYOUT_2X3, axial_to_pixel, hex_corners, pixel_to_axial)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 1200, 800
MAP_RIGHT = 860            # map area spans x in [0, MAP_RIGHT)
PANEL_LEFT = MAP_RIGHT + 12

HEX_SIZE = 55
FPS = 60
TURN_MS = 150

# Nation palette matching sim_nation.draw_map (matplotlib map).
NATION_COLORS = {
    'Alpha': (141, 211, 199),    # #8dd3c7
    'Beta':  (255, 255, 179),    # #ffffb3
    'Gamma': (190, 186, 218),    # #bebada
}
HEX_EDGE = (20, 20, 20)
BG = (28, 28, 34)
PANEL_BG = (40, 40, 48)
TEXT = (235, 235, 235)
DIM = (170, 170, 180)
RED = (235, 90, 90)
GREEN = (120, 210, 120)
ACCENT = (240, 200, 90)

# Map offset so the 2x3 layout is centered in the map area.
# center of layout: A1(0,0)->(0,0); G2(1,2)->(190.5, 165); pad by hex radius.
_OFFSET_X = (MAP_RIGHT / 2.0) - 95.0
_OFFSET_Y = (HEIGHT / 2.0) - 82.0

REVERSE_LAYOUT = {v: k for k, v in LAYOUT_2X3.items()}

# Series colors for the hover charts.
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

# V2b: on-map economic/trade indicators.
_ARROW_PHASE = 9       # animation step counter for trade-flow arrows
_TRADE_WINDOW = 8      # turns of export/import value averaged for arrows
BADGE_ORANGE = (240, 150, 60)
BADGE_RED = (235, 70, 70)
BADGE_TRA = (90, 210, 120)
BADGE_GINI = (190, 110, 230)
HOT_RING = (235, 120, 60)
COLD_RING = (110, 170, 235)

# M3: unrest-stage badge colors (ladder calm->unrest->protest->mob->compromise->takeover).
UNREST_COLORS = {
    'unrest': (230, 170, 60),
    'protest': (240, 140, 40),
    'mob': (235, 70, 70),
    'compromise': (160, 230, 90),
    'takeover': (180, 100, 230),
}
# M3: regime-event flash glyph colors (election vs coup).
ELECTION_C = (110, 200, 250)
COUP_C = (235, 90, 90)

# Keeps track of last-turn population per region name for delta badges.
_pops = {}


def _hex_px(q, r):
    x, y = axial_to_pixel(q, r, HEX_SIZE)
    return (int(x + _OFFSET_X), int(y + _OFFSET_Y))


# ---------------------------------------------------------------------------
# World stepping (mirrors sim_nation.main() exactly)
# ---------------------------------------------------------------------------

def build_world_view():
    """Build the world + prepare viewer state."""
    tiles, nations = build_world()
    currencies = [n.currency for n in nations]
    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None]
    # name -> tile for hover lookup
    by_name = {r.name: r for r in tiles}
    return {
        'tiles': tiles,
        'nations': nations,
        'currencies': currencies,
        'pair_orders': pair_orders,
        'by_name': by_name,
        'turn': 0,
        'view': 0,          # 0 = grid of all 6 charts; 1..6 = zoom one chart
        'window': 100,      # sparkline window (in turns)
        'currency_totals': {c: fx.audit_currency_total(tiles, c)
                            for c in currencies},
        'violations': [],
        'hud': False,       # V2c: national HUD strip toggle (N)
        'nation_history': [],   # per-turn per-nation snapshots
        'help_open': False, # V2e: help menu overlay (H / ?)
        'help_scroll': 0,   # help overlay scroll (lines)
    }


def step_world(world):
    """Advance one turn of the engine; mirror sim_nation.main() turn body."""
    t = world['turn'] + 1
    tiles = world['tiles']
    currencies = world['currencies']
    pair_orders = world['pair_orders']

    curr_before = {c: fx.audit_currency_total(tiles, c) for c in currencies}
    cash_before = sum(curr_before.values())
    violations = []

    for r in tiles:
        pending = {}
        for other in tiles:
            if other is r or other not in r.neighbors.values():
                continue
            for g, entries in pending_imports(r, other).items():
                pending.setdefault(g, []).extend(entries)
        r.pending_imports = pending
        r._auction_import_sales = {}

    for r in tiles:
        r.step(t)

    for r in tiles:
        for rt in r._all_routes():
            rt.advance()
            rt.deliver_pending()

    resolve_parked(tiles)

    for r, other in pair_orders:
        settle_trade(t, other, r)

    fx.cycle_all_markets(tiles, t)

    # M3: regime bookkeeping per nation (elections / coups / legitimacy).
    regime_events = {}
    for n in world['nations']:
        ev = step_regime(n, t)
        if ev:
            regime_events[n.name] = ev[-1]

    for r, other in pair_orders:
        desk = r.forex_desks.get(other.name)
        if desk is not None:
            ppp = max(0.1, other.cost_of_living) / max(0.1, r.cost_of_living)
            desk.update(0, bank=r.bank, fx_regime='managed', ppp_target=ppp)
            if getattr(r, 'destination_region', None) is other:
                desk.save_rate(r)

    for c in currencies:
        delta = fx.audit_currency_total(tiles, c) - curr_before[c]
        if abs(delta) > 5.0:
            violations.append((t, c, delta))
    cash_after = sum(fx.audit_currency_total(tiles, c) for c in currencies)
    if abs(cash_after - cash_before) > 5.0:
        violations.append((t, 'ALL', cash_after - cash_before))

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

    # V2c: per-nation snapshot for the national HUD strip.
    for n in world['nations']:
        tr = n.treasury()
        pop = sum(r.total_population[-1] if r.total_population
                  else len(r.agents) for r in n.tiles)
        ex = sum(sum(v) for r in n.tiles
                 for v in r.export_val.values())
        im = sum(sum(v) for r in n.tiles
                 for v in r.import_val.values())
        world['nation_history'].append({
            'name': n.name,
            'treasury': tr['total'],
            'exports': ex,
            'imports': im,
            'pop': pop,
            'legitimacy': n.legitimacy,
            'regime': n.regime_type,
            'currency': n.currency,
            'ruling': getattr(n, 'ruling_faction', None),
            'opposition': list(getattr(n, 'opposition', [])),
            'event': regime_events.get(n.name),
            'turn': t,
        })
    # Bound the history (sparkline window).
    hist = world['nation_history']
    if len(hist) > 250:
        del hist[:len(hist) - 250]
    return violations


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _nation_color(region):
    owner = getattr(region, 'owner_nation', None)
    if owner is not None:
        return NATION_COLORS.get(owner.name, (150, 150, 150))
    return (150, 150, 150)


def _tile_stats(region):
    """Summary line(s) printed on each hex: pop, food price, traders."""
    pop = region.total_population[-1] if region.total_population else len(region.agents)
    food = region.recipes[Goods.food]['price']
    traders = sum(1 for a in region.agents if a.is_trader)
    return f"pop {pop}", f"food ${food:.2f}", f"tr {traders}"


def _draw_terrain_glyph(surface, region, cx, cy):
    """Small vector terrain markers under the hex center.

    wheat  -> amber wedge  (food terrain > 1.3)
    forest -> green wedge  (wood terrain > 1.3)
    cold   -> white dot    (climate == 'cold')
    """
    y = cy + 22
    if region.terrain.get(Goods.food, 1.0) > 1.3:
        pts = [(cx, y - 8), (cx - 9, y + 6), (cx + 9, y + 6)]
        pygame.draw.polygon(surface, (240, 200, 90), pts)
    if region.terrain.get(Goods.wood, 1.0) > 1.3:
        pts = [(cx, y - 8), (cx - 9, y + 6), (cx + 9, y + 6)]
        pygame.draw.polygon(surface, (110, 190, 110), pts)
    if region.climate == 'cold':
        pygame.draw.circle(surface, (240, 245, 250), (cx, y), 4)


def _region_pop(region):
    """Current population count for *region* (log-based or live agent count)."""
    if region.total_population:
        return region.total_population[-1]
    return len(region.agents)


def _draw_pop_heat(surface, region, pts, cx, cy):
    """Brighten the hex fill by population density (density rendering)."""
    pop = _region_pop(region)
    max_pop = 420.0  # normalization: sim_nation tiles hover near 300-420
    f = min(0.45, 0.18 * (pop / max_pop))
    extra = (int(255 * f), int(255 * f), int(245 * f))
    base = _nation_color(region)
    blended = tuple(min(255, int(v) + e) for v, e in zip(base, extra))
    pygame.draw.polygon(surface, blended, pts)


def _trade_flow_pairs(world):
    """Return [(x1,y1,x2,y2, strength, dir_flip)] for each wired edge.

    Strength and direction come from the last *_TRADE_WINDOW* turns of the
    exporter's export_val and the importer's import_val on that edge pair.
    """
    tiles = world['tiles']
    pair_orders = world['pair_orders']
    out = []
    for r, other in pair_orders:
        exp = sum(sum(v) for v in r.export_val.values()) or 0.0
        imp = sum(sum(v) for v in r.import_val.values()) or 0.0
        # net flow on this directed pair (r -> other)
        strength = exp + imp
        if strength <= 0:
            continue
        c1 = _hex_px(*LAYOUT_2X3[r.name])
        c2 = _hex_px(*LAYOUT_2X3[other.name])
        # scale strength to a line width 1..8
        width = max(1, min(8, int(strength / 3000.0) + 1))
        # direction: exporter -> importer if net export positive
        flip = exp >= imp
        out.append((c1, c2, width, flip))
    return out


def _draw_trade_arrows(surface, world, frame):
    """Animated arrows on wired edges scaled by recent trade value."""
    for c1, c2, width, flip in _trade_flow_pairs(world):
        (x1, y1), (x2, y2) = c1, c2
        # midpoint + perpendicular offset running phase
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        dx, dy = x2 - x1, y2 - y1
        length = max(1, int((dx * dx + dy * dy) ** 0.5))
        ux, uy = dx / length, dy / length
        if flip:
            x1, y1, x2, y2 = x2, y2, x1, y1
        phase = (frame // 2) % 12
        off = phase - 6
        mx2 = int(x1 + ux * (length / 2 + off * 2))
        my2 = int(y1 + uy * (length / 2 + off * 2))
        # draw line + animated dot
        pygame.draw.line(surface, (80, 190, 220), (x1, y1), (x2, y2), width)
        pygame.draw.circle(surface, (180, 230, 245), (mx2, my2), 3)


def _draw_activity_badges(surface, region, cx, cy, font_small):
    """Small indicators around the hex: demand, hunger, trader, gini, price ring."""
    # food price vs neighbor average -> border tint of arbitrage pressure
    food = region.recipes[Goods.food]['price']
    neighbors = [n for n in region.neighbors.values()
                 if getattr(n, 'recipes', None)]
    if neighbors:
        avg = sum(n.recipes[Goods.food]['price'] for n in neighbors) / len(neighbors)
        ring_color = HOT_RING if food > avg * 1.15 else \
                     COLD_RING if food < avg * 0.85 else None
        if ring_color is not None:
            pygame.draw.circle(surface, ring_color, (cx, cy), HEX_SIZE - 8, 2)
    # demand ratio alert
    dr = region.demand_ratio_log.get(Goods.food, [])
    if dr and dr[-1] > 1.5:
        pygame.draw.circle(surface, BADGE_ORANGE, (cx + 32, cy - 34), 7)
    # recent hunger (any profession hungry this turn)
    if any(region.hungry_log[g] and region.hungry_log[g][-1] > 5
           for g in (Goods.food, Goods.wood, Goods.furniture)):
        pygame.draw.circle(surface, BADGE_RED, (cx - 32, cy - 34), 7)
    # trader count badge
    traders = sum(1 for a in region.agents if a.is_trader)
    if traders > 0:
        t = font_small.render(f"T{traders}", True, BADGE_TRA)
        surface.blit(t, (cx + 24, cy + 30))
    # gini dot
    gini = region.gini_log.get(Goods.food, [])
    if gini and gini[-1] > 0.6:
        pygame.draw.circle(surface, BADGE_GINI, (cx - 32, cy + 30), 5)
    # migration intent arrow
    mig = region.migration_intent_log
    if mig and mig[-1] > 2.0:
        pts = [(cx + 22, cy - 44), (cx + 22, cy - 54),
               (cx + 28, cy - 46)]
        pygame.draw.polygon(surface, _MIG_C, pts)
    # M3: unrest-stage badge when the ladder fired this turn (not calm).
    unrest = region.unrest_log[-1] if region.unrest_log else {}
    stage = unrest.get('stage', 'calm')
    if stage != 'calm' and stage in UNREST_COLORS:
        color = UNREST_COLORS[stage]
        pygame.draw.circle(surface, color, (cx, cy - 48), 8)
        tag = font_small.render(stage[0].upper(), True, (255, 255, 255))
        surface.blit(tag, tag.get_rect(center=(cx, cy - 48)))


def _draw_pop_delta(surface, region, cx, cy, font_small):
    """+B / -D per-turn population delta badge under the hex name."""
    if not region.total_population or len(region.total_population) < 2:
        return
    prev = _pops.get(region.name)
    cur = region.total_population[-1]
    if prev is None:
        _pops[region.name] = cur
        return
    delta = cur - prev
    _pops[region.name] = cur
    if delta >= 0:
        txt = font_small.render(f"+{delta}", True, GREEN)
    else:
        txt = font_small.render(f"{delta}", True, RED)
    surface.blit(txt, txt.get_rect(center=(cx, cy - 44)))


def _draw_hex_map(surface, world, font, font_small):
    tiles = world['tiles']
    for region in tiles:
        coords = LAYOUT_2X3.get(region.name)
        if coords is None:
            continue
        cx, cy = _hex_px(*coords)
        pts = hex_corners((cx, cy), HEX_SIZE - 1)
        _draw_pop_heat(surface, region, pts, cx, cy)
        pygame.draw.polygon(surface, HEX_EDGE, pts, 2)
        # Name headline
        name_surf = font.render(region.name, True, TEXT)
        surface.blit(name_surf, name_surf.get_rect(center=(cx, cy - 20)))
        # pop / food / traders
        line1, line2, line3 = _tile_stats(region)
        s1 = font_small.render(line1, True, TEXT)
        s2 = font_small.render(line2, True, DIM)
        s3 = font_small.render(line3, True, DIM)
        surface.blit(s1, s1.get_rect(center=(cx, cy - 2)))
        surface.blit(s2, s2.get_rect(center=(cx, cy + 12)))
        surface.blit(s3, s3.get_rect(center=(cx, cy + 26)))
        _draw_terrain_glyph(surface, region, cx, cy - 34)
        _draw_activity_badges(surface, region, cx, cy, font_small)
        _draw_pop_delta(surface, region, cx, cy, font_small)
    _draw_trade_arrows(surface, world, world.get('frame', 0))


# ---------------------------------------------------------------------------
# V2a: per-tile hover chart dashboard (pure pygame plot helpers)
# ---------------------------------------------------------------------------

def _sum_turns(lists):
    """Per-turn totals across a list of equal-length per-turn series."""
    n = max((len(s) for s in lists), default=0)
    return [sum(s[i] for s in lists if i < len(s)) for i in range(n)]


def _tile_charts(region):
    """Return six (title, kind, series, colors, labels) hover charts for *region*."""
    g = lambda gd: region.price_log.get(gd, [])
    pop = region.total_population or []
    # Explicit per-turn hungry sum (robust to unequal log lengths).
    hs = [region.hungry_log.get(gd, []) for gd in (Goods.food, Goods.wood,
                                                   Goods.furniture)]
    hungry = ([sum(row) for row in zip(*hs)] if all(hs)
              else [sum(row) for row in zip(*[h for h in hs if h])])
    exp = [region.export_val.get(gd, []) for gd in (Goods.food, Goods.wood,
                                                    Goods.furniture)]
    imp = [region.import_val.get(gd, []) for gd in (Goods.food, Goods.wood,
                                                    Goods.furniture)]
    gov = region.gov
    income = getattr(gov, 'income_log', [])
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


def _draw_regime_readout(surface, region, font_small, y):
    """M3: one-line readout of protest energy / unrest stage / top faction /
    the owning nation's legitimacy + ruling faction."""
    protest = (region.protest_energy_log[-1]
               if region.protest_energy_log else 0.0)
    unrest = region.unrest_log[-1] if region.unrest_log else {}
    stage = unrest.get('stage', 'calm')
    # top faction by latest support snapshot
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


def _audit_panel(surface, world, font, font_small):
    """Right-hand panel: header info + hover charts + audit readout."""
    hud_on = world.get('hud', False)
    chart_bottom = 640 if hud_on else 700
    chart_hint_y = chart_bottom + 6
    audit_y = 748 if hud_on else 736
    audit_vgap = 12
    audit_head_y = audit_y - 24
    pygame.draw.rect(surface, PANEL_BG,
                     (PANEL_LEFT - 10, 10, WIDTH - PANEL_LEFT - 6,
                      HEIGHT - 20))

    title = font.render("REGNUM — Hex View", True, ACCENT)
    surface.blit(title, (PANEL_LEFT, 20))

    t_ = world['turn']
    turn_line = font_small.render(f"Turn: {t_}  "
                                  f"win={world['window']}t", True, TEXT)
    surface.blit(turn_line, (PANEL_LEFT, 50))

    cursors = world.get('currency_totals', {})
    y = 80
    for c, total in cursors.items():
        line = font_small.render(f"{c}: ${total:,.0f}", True, TEXT)
        surface.blit(line, (PANEL_LEFT, y))
        y += 22

    if world.get('playing'):
        pn = font_small.render("[ PLAYING ]  Space=pause  Q=quit", True, GREEN)
    else:
        pn = font_small.render("[ PAUSED ]  S=step  Space=play", True, DIM)
    surface.blit(pn, (PANEL_LEFT, 148))

    region = world.get('hover_region')
    if region is not None:
        charts = _tile_charts(region)
        view = world.get('view', 0)
        if view == 0:
            _draw_chart_grid(surface, charts, font, font_small, world['window'],
                             185, chart_bottom)
            hint = font_small.render(
                f"{region.name}: Tab=grid  1-6=zoom  N=hud", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_hint_y))
        else:
            idx = max(0, min(len(charts) - 1, view - 1))
            _draw_chart_large(surface, charts[idx], font, font_small,
                              world['window'], 185, chart_bottom)
            hint = font_small.render(
                f"{charts[idx][0]}  (Tab=grid  N=hud)", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_hint_y))
        # M3: regime readout line — protest / unrest / top faction / nation ruling
        _draw_regime_readout(surface, region, font_small, y=chart_hint_y + 18)
    else:
        hint = font_small.render("Hover a hex for charts", True, DIM)
        surface.blit(hint, (PANEL_LEFT, 190))
        if hud_on:
            hint2 = font_small.render("N = hide national HUD", True, DIM)
            surface.blit(hint2, (PANEL_LEFT, 210))

    if world.get('violations'):
        v1 = font.render("AUDIT VIOLATION", True, RED)
        surface.blit(v1, (PANEL_LEFT, audit_head_y))
        vline = font_small.render(
            "; ".join(f"T{v[0]} {v[1]} {v[2]:+.2f}"
                      for v in world['violations']),
            True, RED)
        surface.blit(vline, (PANEL_LEFT, audit_head_y + audit_vgap))
    else:
        ok = font.render("Conserved: 0 LEAK / 0 SHIFT", True, GREEN)
        surface.blit(ok, (PANEL_LEFT, audit_y))


def _draw_nation_hud(surface, world, font_small):
    """V2c: bottom national HUD strip — per-nation treasury/export/import
    time-series sparklines plus regime/legitimacy/pop summary.

    Pure pygame drawing from world['nation_history'] (appended each turn).
    Toggled by the N key; drawn as a semi-opaque overlay across the bottom.
    """
    if not world.get('hud', False) or not world['nation_history']:
        return
    font = font_small
    strip_rect = (0, HEIGHT - 140, WIDTH, 140)
    overlay = pygame.Surface((strip_rect[2], strip_rect[3]),
                             pygame.SRCALPHA)
    overlay.fill((34, 34, 42, 235))
    surface.blit(overlay, (strip_rect[0], strip_rect[1]))

    nations = world['nations']
    ncol = len(nations)
    col_w = WIDTH // ncol
    hist = world['nation_history']
    window = world['window']
    for i, n in enumerate(nations):
        x0 = i * col_w + 8
        y0 = strip_rect[1] + 6
        # Per-nation history subset (computed first so the ticker + sparkline
        # both read the same latest snapshot).
        nh = [h for h in hist if h['name'] == n.name][-window:]
        if not nh:
            continue
        # Header line: name + regime + legitimacy + ruling faction + opposition
        ruling = getattr(n, 'ruling_faction', None)
        opp = getattr(n, 'opposition', []) or []
        ruling_s = f"  ruling {ruling}" if ruling else ""
        opp_s = f"  opp:{','.join(opp)}" if opp else ""
        header = font.render(
            f"{n.name} ({n.currency})  {n.regime_type}  "
            f"legit {n.legitimacy:.2f}{ruling_s}{opp_s}", True, ACCENT)
        surface.blit(header, (x0, y0))
        # M3: regime-event ticker (latest election/coup this turn)
        ev = nh[-1].get('event')
        if ev is not None:
            if ev.get('kind') == 'election':
                tline = font.render(
                    f"T{ev.get('turn')} election: {ev.get('winner_faction')}",
                    True, ELECTION_C)
            else:
                tline = font.render(
                    f"T{ev.get('turn')} coup! {ev.get('old_regime')}->"
                    f"{ev.get('new_regime')}", True, COUP_C)
            surface.blit(tline, (x0, y0 + 18))
        # Treasury sparkline
        treas = [h['treasury'] for h in nh]
        exps = [h['exports'] for h in nh]
        imps = [h['imports'] for h in nh]
        pop = nh[-1]['pop']
        cy = y0 + 22
        line_h = 24
        # Normalize within column
        vmax = max(max(treas), max(exps + imps), 1.0)
        def scale(v):
            return v / vmax
        # Draw treasury polyline (cyan)
        pts = []
        npts = len(treas)
        for j, v in enumerate(treas):
            x = x0 + j * (col_w - 16) / max(1, npts - 1)
            y = cy + line_h - scale(v) * line_h
            pts.append((x, y))
        pygame.draw.lines(surface, (120, 200, 220), False, pts, 2)
        # Exports (green) / imports (red) thin bars along the same baseline
        bx = x0
        bw = max(2, (col_w - 16) / max(1, npts))
        for j in range(npts):
            eh = scale(exps[j]) * line_h
            ih = scale(imps[j]) * line_h
            if eh > 0.5:
                pygame.draw.rect(surface, _EXP_C,
                                 (bx, cy + line_h - eh, bw * 0.45, eh))
            if ih > 0.5:
                pygame.draw.rect(surface, _IMP_C,
                                 (bx + bw * 0.55, cy + line_h - ih,
                                  bw * 0.45, ih))
            bx += bw
        # Pop text at bottom
        popline = font.render(f"pop {pop}", True, TEXT)
        surface.blit(popline, (x0, cy + line_h + 4))
        # Last treasury / net exports values
        net = nh[-1]['exports'] - nh[-1]['imports']
        sign = "+" if net >= 0 else ""
        netline = font.render(f"treasury ${nh[-1]['treasury']:,.0f}  "
                              f"net {sign}${net:,.0f}", True, DIM)
        surface.blit(netline, (x0, cy + line_h + 22))


def _draw_help(surface, world, font_small):
    """V2e: full-screen help overlay explaining every UI/UX element."""
    if not world.get('help_open', False):
        return
    title_font = pygame.font.Font(None, 30)
    header_font = pygame.font.Font(None, 22)
    body_font = font_small

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((16, 16, 22, 242))
    surface.blit(overlay, (0, 0))
    surface.blit(title_font.render(
        'REGNUM — Control & UI Reference', True, ACCENT), (24, 14))

    sections = [
        ('KEYBOARD', [
            'Space .......... play / pause (auto-advance ~150 ms/turn)',
            'S or -> ........ step one turn (while paused)',
            'Tab ............ chart-grid view on the hovered hex',
            '1 .. 6 ......... zoom the 1st..6th hover chart',
            'N .............. toggle the national HUD strip',
            'H or ? ......... toggle this help (Up/Down scrolls)',
            'Esc ............ close help first; Q quits either way',
        ]),
        ('MAP (HEXES)', [
            'Hex fill = owner nation; brighter fill = higher population (heat).',
            'Hex name headline; below it: pop / food $ / trader count.',
            'Amber wedge = food terrain; green wedge = wood/forest; white dot = cold.',
            'Orange dot = high demand.  Red dot = many hungry this turn.',
            'Green T# = trader count.  Purple dot = high gini.',
            'Cyan up-arrow = strong migration intent.',
            'Hot ring = food price ABOVE neighbours; cold ring = BELOW (arbitrage).',
            'Cyan edge strokes + moving dot = trade flow; width = volume,',
            'direction points from net exporter to net importer.',
            '+N / -N under the name = this turn\'s population change.',
            'Top-center colored dot = unrest stage (U=unrest P=protest M=mob',
            'C=compromise T=takeover), shown only while the ladder is active.',
        ]),
        ('RIGHT PANEL (HOVER A HEX)', [
            'Top: turn counter, per-currency totals (AL / BE / GA), play state.',
            'Hovering a hex shows a 2x3 grid of six live mini-charts:',
            '  1 Prices      2 Population/Hunger   3 Production',
            '  4 Trade flow (exports vs imports)',
            '  5 Government income (tax / tariff / inheritance)',
            '  6 Gini / Migration intent',
            'Tab returns to the grid; 1..6 zooms one chart.',
            'Below the grid (M3): protest energy / unrest stage / top faction,',
            'plus the owner nation\'s legitimacy and ruling faction.',
            'Bottom line: green "Conserved" or red "AUDIT VIOLATION"',
            '(per-currency supply-shift or leak > $5.0 this turn).',
        ]),
        ('NATIONAL HUD STRIP (N)', [
            'One column per nation: name (currency) + regime + legitimacy',
            '+ ruling faction + opposition list (M3).',
            'Line below the header = election/coup ticker for that turn.',
            'Cyan polyline = treasury over the chart window.',
            'Green bars = exports; red bars = imports (same window).',
            'Bottom: live population, last treasury, net trade balance.',
        ]),
    ]

    # Flatten entries, wrapping body text to the panel width.
    wrapped = []
    max_w = WIDTH - 72
    for header, lines in sections:
        wrapped.append((0, 'header', header))
        for ln in lines:
            cur = ''
            for w in ln.split(' '):
                test = (cur + ' ' + w).strip()
                if body_font.size(test)[0] <= max_w or not cur:
                    cur = test
                else:
                    wrapped.append((8, 'body', cur))
                    cur = w
            wrapped.append((8, 'body', cur))

    line_h = 20
    visible = 32
    scroll = world.get('help_scroll', 0)
    scroll = max(0, min(scroll, max(0, len(wrapped) - visible)))
    y = 52
    for i in range(scroll, min(len(wrapped), scroll + visible)):
        indent, kind, text = wrapped[i]
        color = ACCENT if kind == 'header' else TEXT
        f = header_font if kind == 'header' else body_font
        surface.blit(f.render(text, True, color), (24 + indent, y))
        y += line_h

    if len(wrapped) > visible:
        hint = body_font.render(
            'Up / Down scrolls • Esc closes • Q quits', True, ACCENT)
        surface.blit(hint, (24, HEIGHT - 28))


def render_frame(surface, world):
    """Draw one full frame (map + panel).  Reusable by the headless probe."""
    font = pygame.font.Font(None, 28)
    font_small = pygame.font.Font(None, 22)
    surface.fill(BG)
    _draw_hex_map(surface, world, font, font_small)
    _audit_panel(surface, world, font, font_small)
    _draw_nation_hud(surface, world, font_small)
    _draw_help(surface, world, font_small)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    logInit()
    random.seed(42)
    pygame.init()
    surface = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("REGNUM V2a — Hex Map + Hover Charts")
    clock = pygame.time.Clock()

    world = build_world_view()
    world['playing'] = False
    world['hover_region'] = None
    world['frame'] = 0
    # prime the population-delta cache
    for r in world['tiles']:
        _pops[r.name] = _region_pop(r)

    last_tick = pygame.time.get_ticks()
    running = True
    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
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
                    world['help_scroll'] = 0
                elif world.get('help_open') and event.key == pygame.K_UP:
                    world['help_scroll'] = max(
                        0, world.get('help_scroll', 0) - 5)
                elif world.get('help_open') and event.key == pygame.K_DOWN:
                    world['help_scroll'] = world.get('help_scroll', 0) + 5
                elif event.key == pygame.K_SPACE:
                    world['playing'] = not world['playing']
                    last_tick = now
                elif event.key in (pygame.K_s, pygame.K_RIGHT):
                    if not world['playing']:
                        step_world(world)
                elif event.key == pygame.K_n:
                    world['hud'] = not world.get('hud', False)
                elif event.key == pygame.K_TAB:
                    world['view'] = 0
                elif pygame.K_1 <= event.key <= pygame.K_6:
                    world['view'] = event.key - pygame.K_1 + 1

        # Auto-advance when playing
        if world['playing'] and now - last_tick >= TURN_MS:
            step_world(world)
            last_tick = now
        world['frame'] = (world.get('frame', 0) + 1) % 600

        # Hover hit-test (map area only)
        mx, my = pygame.mouse.get_pos()
        world['hover_region'] = None
        if mx < MAP_RIGHT:
            size = HEX_SIZE
            q, r = pixel_to_axial(mx - _OFFSET_X, my - _OFFSET_Y, size)
            name = REVERSE_LAYOUT.get((q, r))
            if name is not None:
                world['hover_region'] = world['by_name'].get(name)

        render_frame(surface, world)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()