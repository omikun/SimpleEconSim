"""
Pygame time-series chart rendering (line, paired bars, stacked bars) and dashboard layouts.
"""

import pygame
from goods import Goods

WIDTH = 1400
MAP_RIGHT = 1060
PANEL_LEFT = MAP_RIGHT + 12

ACCENT = (240, 200, 90)
FOOD_C = (120, 200, 80)
WOOD_C = (190, 150, 70)
FURN_C = (90, 140, 230)
POP_C = (230, 230, 230)
HUNGER_C = (235, 90, 90)
EXP_C = (110, 210, 120)
IMP_C = (230, 110, 100)
TAX_C = (240, 200, 90)
TAR_C = (110, 150, 235)
INH_C = (200, 120, 230)
GINI_C = (200, 120, 230)
MIG_C = (120, 200, 220)
CHART_BOX = (72, 72, 84)


def sum_turns(lists):
    """Per-turn totals across a list of equal-length per-turn series."""
    n = max((len(s) for s in lists), default=0)
    return [sum(s[i] for s in lists if i < len(s)) for i in range(n)]


def tile_charts(region):
    """Six (title, kind, series, colors, labels) charts; safe for unclaimed tiles."""
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
         [FOOD_C, WOOD_C, FURN_C], ["food", "wood", "furn"]),
        ("Population / Hunger", "line",
         [pop, hungry], [POP_C, HUNGER_C], ["pop", "hungry"]),
        ("Production", "line",
         [region.production_log.get(gd, []) for gd in (Goods.food, Goods.wood,
                                                       Goods.furniture)],
         [FOOD_C, WOOD_C, FURN_C], ["food", "wood", "furn"]),
        ("Trade flow", "bars",
         [sum_turns(exp), sum_turns(imp)],
         [EXP_C, IMP_C], ["export", "import"]),
        ("Gov income", "stack",
         [tax, tariff, inherit],
         [TAX_C, TAR_C, INH_C], ["tax", "tariff", "inherit"]),
        ("Gini / Migration", "line",
         [region.gini_log.get(Goods.food, []), region.migration_intent_log],
         [GINI_C, MIG_C], ["gini", "migr"]),
    ]


def chart_labels(surface, labels, colors, font, rect, y_start=2, step=13):
    y = y_start
    for label, color in zip(labels, colors):
        txt = font.render(label, True, color)
        surface.blit(txt, (rect[0] + 4, rect[1] + y))
        y += step


def plot_line_chart(surface, rect, series_list, colors, labels, window, font):
    """Axes box + one normalized polyline per series (last *window* turns)."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, CHART_BOX, rect, 1)
    data = [s[-window:] for s in series_list]
    if not any(data):
        chart_labels(surface, labels, colors, font, rect)
        return
    vals = [v for d in data for v in d]
    vmin, vmax = min(vals), max(vals)
    if vmax - vmin < 1e-9:
        vmax = vmin + 1.0
    n = max(len(d) for d in data)
    if n < 2:
        chart_labels(surface, labels, colors, font, rect)
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
    chart_labels(surface, labels, colors, font, rect)


def plot_bar_pairs(surface, rect, series_list, colors, labels, window, font):
    """Side-by-side per-turn bars for two series (e.g. export vs import)."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, CHART_BOX, rect, 1)
    n = max((len(s) for s in series_list), default=0)
    n_show = min(window, n)
    if n_show <= 0:
        chart_labels(surface, labels, colors, font, rect)
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
    chart_labels(surface, labels, colors, font, rect)


def plot_stacked_bars(surface, rect, series_list, colors, labels, window, font):
    """Stacked per-turn bars (gov income decomposition)."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, CHART_BOX, rect, 1)
    n = max((len(s) for s in series_list), default=0)
    n_show = min(window, n)
    if n_show <= 0:
        chart_labels(surface, labels, colors, font, rect)
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
    chart_labels(surface, labels, colors, font, rect)


def draw_chart_cell(surface, chart, rect, font, font_small, window):
    """Draw one chart (title + plot) into *rect*."""
    title, kind, series, colors, labels = chart
    tsurf = font_small.render(title, True, ACCENT)
    surface.blit(tsurf, (rect[0] + 4, rect[1] + 2))
    plot_rect = (rect[0], rect[1] + 20, rect[2], rect[3] - 20)
    if kind == 'line':
        plot_line_chart(surface, plot_rect, series, colors, labels, window,
                        font_small)
    elif kind == 'bars':
        plot_bar_pairs(surface, plot_rect, series, colors, labels, window,
                       font_small)
    elif kind == 'stack':
        plot_stacked_bars(surface, plot_rect, series, colors, labels, window,
                          font_small)


def draw_chart_grid(surface, charts, font, font_small, window, y0, y1):
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
            draw_chart_cell(surface, charts[idx], rect, font, font_small,
                            window)
            idx += 1


def draw_chart_large(surface, chart, font, font_small, window, y0, y1):
    """Single chart drawn large (zoom view 1..6)."""
    rect = (PANEL_LEFT + 6, y0, WIDTH - 14 - PANEL_LEFT, y1 - y0)
    draw_chart_cell(surface, chart, rect, font, font_small, window)
