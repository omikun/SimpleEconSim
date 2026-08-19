"""
Pygame time-series chart rendering (line, paired bars, stacked bars) and dashboard layouts.
Expanded 10-chart interactive dashboard with click-to-zoom and detailed statistics.
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

# Colors for additional graphs
PROTEST_C = (245, 140, 40)
UNREST_C = (235, 75, 75)
GDP_C = (100, 225, 150)
DEMAND_FOOD_C = (245, 180, 70)
DEMAND_WOOD_C = (180, 220, 90)
DEMAND_FURN_C = (130, 175, 245)


# Game-level moving average parameter for GDP and Gov Income charts
GDP_GOV_MA_WINDOW = 10
MA_WINDOW = GDP_GOV_MA_WINDOW


def moving_average(series, window=GDP_GOV_MA_WINDOW):
    """Calculate moving average of the last `window` rounds or num rounds so far."""
    if not series:
        return []
    res = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        sub = series[start:i + 1]
        res.append(sum(sub) / len(sub))
    return res


def sum_turns(lists):
    """Per-turn totals across a list of equal-length per-turn series."""
    n = max((len(s) for s in lists), default=0)
    return [sum(s[i] for s in lists if i < len(s)) for i in range(n)]


def tile_charts(region):
    """10 (title, kind, series, colors, labels) charts; safe for unclaimed tiles."""
    g_price = lambda gd: region.price_log.get(gd, [])
    g_prod = lambda gd: region.production_log.get(gd, [])
    g_inv = lambda gd: region.inventory_log.get(gd, [])
    g_dem = lambda gd: region.demand_ratio_log.get(gd, [])

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
    tax = moving_average([e.get('tax', 0.0) for e in income])
    tariff = moving_average([e.get('tariff', 0.0) for e in income])
    inherit = moving_average([e.get('inheritance', 0.0) for e in income])

    protest = region.protest_energy_log or []
    gdp = moving_average(region.gdp_log or [])

    return [
        ("1. Prices", "line",
         [g_price(Goods.food), g_price(Goods.wood), g_price(Goods.furniture)],
         [FOOD_C, WOOD_C, FURN_C], ["food", "wood", "furn"]),
        ("2. Pop / Hunger", "line",
         [pop, hungry], [POP_C, HUNGER_C], ["pop", "hungry"]),
        ("3. Production", "line",
         [g_prod(Goods.food), g_prod(Goods.wood), g_prod(Goods.furniture)],
         [FOOD_C, WOOD_C, FURN_C], ["food", "wood", "furn"]),
        ("4. Trade flow", "bars",
         [sum_turns(exp), sum_turns(imp)],
         [EXP_C, IMP_C], ["export", "import"]),
        ("5. Gov income", "stack",
         [tax, tariff, inherit],
         [TAX_C, TAR_C, INH_C], ["tax", "tariff", "inherit"]),
        ("6. Gini / Migr", "line",
         [region.gini_log.get(Goods.food, []), region.migration_intent_log],
         [GINI_C, MIG_C], ["gini", "migr"]),
        ("7. Inventories", "line",
         [g_inv(Goods.food), g_inv(Goods.wood), g_inv(Goods.furniture)],
         [FOOD_C, WOOD_C, FURN_C], ["food", "wood", "furn"]),
        ("8. Protest / Energy", "line",
         [protest], [PROTEST_C], ["protest"]),
        ("9. GDP Output", "line",
         [gdp], [GDP_C], ["GDP/t"]),
        ("10. Demand Ratio", "line",
         [g_dem(Goods.food), g_dem(Goods.wood), g_dem(Goods.furniture)],
         [DEMAND_FOOD_C, DEMAND_WOOD_C, DEMAND_FURN_C], ["food", "wood", "furn"]),
    ]


AXIS_C = (150, 150, 165)


def fmt_chart_val(v):
    """Compact string format for chart axis min/max values."""
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 10_000:
        return f"{v/1_000:.0f}k"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}k"
    if abs(v) >= 100:
        return f"{v:.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}" if abs(v - round(v)) > 1e-4 else f"{int(round(v))}"
    if abs(v) >= 1:
        return f"{v:.2f}" if abs(v - round(v)) > 1e-4 else f"{int(round(v))}"
    if abs(v) >= 0.001:
        return f"{v:.2f}"
    return "0"


def draw_axis_minmax(surface, rect, vmin, vmax, font):
    """Draw min and max scale numbers at the right edge of chart rect."""
    x0, y0, w, h = rect
    max_surf = font.render(fmt_chart_val(vmax), True, AXIS_C)
    min_surf = font.render(fmt_chart_val(vmin), True, AXIS_C)
    surface.blit(max_surf, (x0 + w - max_surf.get_width() - 4, y0 + 2))
    surface.blit(min_surf, (x0 + w - min_surf.get_width() - 4, y0 + h - min_surf.get_height() - 2))


def chart_labels(surface, labels, colors, font, rect, y_start=2, step=12):
    y = y_start
    for label, color in zip(labels, colors):
        txt = font.render(label, True, color)
        surface.blit(txt, (rect[0] + 4, rect[1] + y))
        y += step


def plot_line_chart(surface, rect, series_list, colors, labels, window, font):
    """Axes box + one normalized polyline per series (last *window* turns)."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, CHART_BOX, rect, 1)
    data = [s[-window:] for s in series_list if s]
    if not any(data):
        chart_labels(surface, labels, colors, font, rect)
        return
    vals = [v for d in data for v in d]
    if not vals:
        chart_labels(surface, labels, colors, font, rect)
        return
    actual_min, actual_max = min(vals), max(vals)
    vmin, vmax = actual_min, actual_max
    if vmax - vmin < 1e-9:
        vmax = vmin + 1.0
    n = max(len(d) for d in data)
    if n < 2:
        chart_labels(surface, labels, colors, font, rect)
        draw_axis_minmax(surface, rect, actual_min, actual_max, font)
        return
    label_h = min(h // 2, 12 + 11 * len(colors))
    iw, ih = max(10, w - 12), max(10, h - label_h - 6)
    for d, color in zip(data, colors):
        if not d:
            continue
        pts = []
        for j, v in enumerate(d):
            x = x0 + 6 + j * iw / max(1, len(d) - 1)
            y = y0 + h - 5 - ((v - vmin) / (vmax - vmin)) * ih
            pts.append((x, y))
        if len(pts) >= 2:
            pygame.draw.lines(surface, color, False, pts, 2)
    chart_labels(surface, labels, colors, font, rect)
    draw_axis_minmax(surface, rect, actual_min, actual_max, font)


def plot_bar_pairs(surface, rect, series_list, colors, labels, window, font):
    """Side-by-side per-turn bars for two series (e.g. export vs import)."""
    x0, y0, w, h = rect
    pygame.draw.rect(surface, CHART_BOX, rect, 1)
    n = max((len(s) for s in series_list), default=0)
    n_show = min(window, n)
    if n_show <= 0:
        chart_labels(surface, labels, colors, font, rect)
        return
    vals = [v for s in series_list for v in s[-n_show:]]
    actual_max = max(vals, default=0.0)
    actual_min = min([0.0] + vals)
    vmax = max(actual_max, 1.0)
    stride = max(1, n_show // 90)
    label_h = min(h // 2, 12 + 11 * len(colors))
    iw = (w - 12) / n_show
    nser = len(series_list)
    for i in range(n_show):
        if i % stride:
            continue
        bw = max(2, iw * 0.85 / nser)
        for k, (s, color) in enumerate(zip(series_list, colors)):
            v = s[i] if i < len(s) else 0.0
            bh = (v / vmax) * max(5, h - label_h - 8)
            bx = x0 + 6 + i * iw + k * bw
            if bh > 0.5:
                pygame.draw.rect(surface, color,
                                 (bx, y0 + h - 6 - bh, bw, bh))
    chart_labels(surface, labels, colors, font, rect)
    draw_axis_minmax(surface, rect, actual_min, actual_max, font)


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
    actual_max = max(totals, default=0.0)
    actual_min = min([0.0] + totals)
    vmax = max(actual_max, 1.0)
    stride = max(1, n_show // 90)
    label_h = min(h // 2, 12 + 11 * len(colors))
    iw = (w - 12) / n_show
    for i in range(n_show):
        if i % stride:
            continue
        bw = max(2, iw * 0.85)
        bx = x0 + 6 + i * iw
        y = y0 + h - 6
        for s, color in zip(series_list, colors):
            v = s[i] if i < len(s) else 0.0
            bh = (v / vmax) * max(5, h - label_h - 8)
            if bh > 0.5:
                pygame.draw.rect(surface, color, (bx, y - bh, bw, bh))
                y -= bh
    chart_labels(surface, labels, colors, font, rect)
    draw_axis_minmax(surface, rect, actual_min, actual_max, font)


def draw_chart_cell(surface, chart, rect, font, font_small, window, is_hovered=False):
    """Draw one chart (title + plot) into *rect*."""
    title, kind, series, colors, labels = chart
    if is_hovered:
        pygame.draw.rect(surface, (55, 55, 68), rect)
    tsurf = font_small.render(title, True, ACCENT if not is_hovered else (255, 240, 150))
    surface.blit(tsurf, (rect[0] + 4, rect[1] + 2))
    plot_rect = (rect[0], rect[1] + 16, rect[2], max(10, rect[3] - 18))
    if kind == 'line':
        plot_line_chart(surface, plot_rect, series, colors, labels, window,
                        font_small)
    elif kind == 'bars':
        plot_bar_pairs(surface, plot_rect, series, colors, labels, window,
                       font_small)
    elif kind == 'stack':
        plot_stacked_bars(surface, plot_rect, series, colors, labels, window,
                          font_small)


def draw_chart_grid(surface, charts, font, font_small, window, y0, y1, mouse_pos=None):
    """2-column x 5-row responsive grid of all 10 charts in the panel area."""
    left = PANEL_LEFT + 6
    right = WIDTH - 8
    top, bottom = y0, y1
    cols, rows = 2, 5
    cw = (right - left) // cols
    ch = (bottom - top) // rows
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(charts):
                break
            rect = (left + c * cw, top + r * ch, cw - 4, ch - 4)
            is_hovered = False
            if mouse_pos:
                mx, my = mouse_pos
                if rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]:
                    is_hovered = True
            draw_chart_cell(surface, charts[idx], rect, font, font_small,
                            window, is_hovered=is_hovered)
            idx += 1


def chart_at_pixel(pos, y0, y1, num_charts=10):
    """Return 1-indexed chart index under mouse pos, or None."""
    mx, my = pos
    left = PANEL_LEFT + 6
    right = WIDTH - 8
    if mx < left or mx > right or my < y0 or my > y1:
        return None
    cols, rows = 2, 5
    cw = (right - left) // cols
    ch = (y1 - y0) // rows
    c = (mx - left) // cw
    r = (my - y0) // ch
    if 0 <= c < cols and 0 <= r < rows:
        idx = r * cols + c
        if 0 <= idx < num_charts:
            return idx + 1
    return None


def draw_chart_large(surface, chart, font, font_small, window, y0, y1):
    """Detailed single chart drawn large with min/max/current statistics readout."""
    title, kind, series, colors, labels = chart
    rect = (PANEL_LEFT + 6, y0, WIDTH - 14 - PANEL_LEFT, y1 - y0)
    pygame.draw.rect(surface, (34, 34, 44), rect)
    pygame.draw.rect(surface, CHART_BOX, rect, 1)

    # Title header
    tsurf = font.render(f"Zoom: {title}", True, ACCENT)
    surface.blit(tsurf, (rect[0] + 8, rect[1] + 6))

    # Readout latest and peak values
    stats_y = rect[1] + 32
    for label, color, s in zip(labels, colors, series):
        if not s:
            continue
        cur_v = s[-1]
        max_v = max(s[-window:]) if s[-window:] else cur_v
        min_v = min(s[-window:]) if s[-window:] else cur_v
        stat_line = f"{label.upper()}: cur={cur_v:,.2f}  min={min_v:,.2f}  max={max_v:,.2f}"
        lsurf = font_small.render(stat_line, True, color)
        surface.blit(lsurf, (rect[0] + 8, stats_y))
        stats_y += 18

    plot_top = stats_y + 8
    plot_rect = (rect[0] + 6, plot_top, rect[2] - 12, max(20, (rect[1] + rect[3]) - plot_top - 8))
    if kind == 'line':
        plot_line_chart(surface, plot_rect, series, colors, labels, window, font_small)
    elif kind == 'bars':
        plot_bar_pairs(surface, plot_rect, series, colors, labels, window, font_small)
    elif kind == 'stack':
        plot_stacked_bars(surface, plot_rect, series, colors, labels, window, font_small)
