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
    Esc/Q  : quit
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


def _draw_hex_map(surface, world, font, font_small):
    tiles = world['tiles']
    for region in tiles:
        coords = LAYOUT_2X3.get(region.name)
        if coords is None:
            continue
        cx, cy = _hex_px(*coords)
        pts = hex_corners((cx, cy), HEX_SIZE - 1)
        color = _nation_color(region)
        pygame.draw.polygon(surface, color, pts)
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


def _audit_panel(surface, world, font, font_small):
    """Right-hand panel: header info + hover charts + audit readout."""
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
                             185, 700)
            hint = font_small.render(
                f"{region.name}: Tab=grid  1-6=zoom", True, DIM)
            surface.blit(hint, (PANEL_LEFT, 706))
        else:
            idx = max(0, min(len(charts) - 1, view - 1))
            _draw_chart_large(surface, charts[idx], font, font_small,
                              world['window'], 185, 700)
            hint = font_small.render(
                f"{charts[idx][0]}  (Tab=grid)", True, DIM)
            surface.blit(hint, (PANEL_LEFT, 706))
    else:
        hint = font_small.render("Hover a hex for charts", True, DIM)
        surface.blit(hint, (PANEL_LEFT, 190))

    if world.get('violations'):
        v1 = font.render("AUDIT VIOLATION", True, RED)
        surface.blit(v1, (PANEL_LEFT, HEIGHT - 90))
        vline = font_small.render(
            "; ".join(f"T{v[0]} {v[1]} {v[2]:+.2f}"
                      for v in world['violations']),
            True, RED)
        surface.blit(vline, (PANEL_LEFT, HEIGHT - 64))
    else:
        ok = font.render("Conserved: 0 LEAK / 0 SHIFT", True, GREEN)
        surface.blit(ok, (PANEL_LEFT, HEIGHT - 64))


def render_frame(surface, world):
    """Draw one full frame (map + panel).  Reusable by the headless probe."""
    font = pygame.font.Font(None, 28)
    font_small = pygame.font.Font(None, 22)
    surface.fill(BG)
    _draw_hex_map(surface, world, font, font_small)
    _audit_panel(surface, world, font, font_small)


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

    last_tick = pygame.time.get_ticks()
    running = True
    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE:
                    world['playing'] = not world['playing']
                    last_tick = now
                elif event.key in (pygame.K_s, pygame.K_RIGHT):
                    if not world['playing']:
                        step_world(world)
                elif event.key == pygame.K_TAB:
                    world['view'] = 0
                elif pygame.K_1 <= event.key <= pygame.K_6:
                    world['view'] = event.key - pygame.K_1 + 1

        # Auto-advance when playing
        if world['playing'] and now - last_tick >= TURN_MS:
            step_world(world)
            last_tick = now

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