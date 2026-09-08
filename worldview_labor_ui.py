"""
worldview_labor_ui.py — Interactive Labor Commodification & Alienation UI dashboard.

Visualizes the labor struggle and workplace dynamics for individual Tiles and Nations:
  1. Labor Exploitation: Average shift hours, statutory workday cap, and surplus value rate (s/v).
  2. Alienation & Health: 4D Alienation index, physiological health attrition, vice spending.
  3. Consciousness & Pacification: Proletarian consciousness, mass entertainment pacification, protest energy.
  4. Workplace Resistance: Active strikes (walkouts), Luddite sabotaged machinery, operational machines.
"""

from __future__ import annotations
import pygame
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import TEXT, DIM, RED, GREEN, ACCENT, HEX_EDGE
from worldview_charts import draw_chart_grid, draw_chart_large, chart_at_pixel

PANEL_LEFT = MAP_RIGHT + 12
PANEL_W = WIDTH - PANEL_LEFT - 6

# Color palette for labor UI
C_SHIFT = (230, 90, 90)        # Shift length red
C_CAP = (100, 180, 240)        # Legal cap blue
C_SV = (240, 190, 60)          # Surplus value amber
C_ALIEN = (180, 120, 220)      # Alienation purple
C_HEALTH = (220, 70, 70)       # Health hazard crimson
C_VICE = (100, 210, 180)       # Despair vice teal
C_CONSC = (240, 75, 75)        # Consciousness red
C_ENTERTAIN = (70, 195, 235)   # Spectacle cyan
C_PROTEST = (240, 150, 50)     # Unrest orange
C_STRIKE = (235, 60, 60)       # Strike bright red
C_SABOTAGE = (220, 140, 40)    # Sabotage yellow-orange
C_MACHINES = (110, 215, 130)   # Capital green


def tile_labor_charts(region):
    """4 specialized labor charts for a single tile/city."""
    if not region:
        return []

    shifts = getattr(region, 'labor_shift_log', []) or []
    sv_rates = [v * 100.0 for v in (getattr(region, 'labor_sv_log', []) or [])]
    caps = [getattr(region, 'max_workday_hours', 16.0)] * len(shifts) if shifts else []

    alienation = [a * 100.0 for a in (getattr(region, 'alienation_log', []) or [])]
    health = [h * 1000.0 for h in (getattr(region, 'health_attrition_log', []) or [])]
    vice = getattr(region, 'vice_spending_log', []) or []

    consc = [c * 100.0 for c in (getattr(region, 'class_consciousness_log', []) or [])]
    entertain = [e * 100.0 for e in (getattr(region, 'entertainment_level_log', []) or [])]
    protest = getattr(region, 'protest_energy_log', []) or []

    strikers = getattr(region, 'strikes_log', []) or []
    broken = getattr(region, 'sabotage_log', []) or []
    machines = getattr(region, 'machinery_stock_log', []) or []

    return [
        ("1. Shift Hours & Exploitation (s/v)", "line",
         [shifts, caps, sv_rates],
         [C_SHIFT, C_CAP, C_SV],
         ["shift hrs", "legal cap", "s/v rate (%)"]),

        ("2. Alienation & Health Attrition", "line",
         [alienation, health, vice],
         [C_ALIEN, C_HEALTH, C_VICE],
         ["alienation (x100)", "health risk (x1k)", "vice spend ($)"]),

        ("3. Consciousness vs Entertainment", "line",
         [consc, entertain, protest],
         [C_CONSC, C_ENTERTAIN, C_PROTEST],
         ["consciousness", "entertainment", "protest"]),

        ("4. Strikes & Machine Sabotage", "line",
         [strikers, broken, machines],
         [C_STRIKE, C_SABOTAGE, C_MACHINES],
         ["strikers", "broken machines", "active machines"]),
    ]


def nation_labor_charts(nation):
    """4 aggregated labor charts across all constituent tiles of a nation."""
    tiles = getattr(nation, 'tiles', [])
    if not tiles:
        return []

    max_len = max((len(getattr(r, 'labor_shift_log', []) or []) for r in tiles), default=0)
    if max_len == 0:
        return []

    def _avg_tile_series(attr_name, mult=1.0):
        out = []
        for i in range(max_len):
            vals = []
            for r in tiles:
                s = getattr(r, attr_name, []) or []
                if i < len(s):
                    vals.append(s[i] * mult)
            out.append(sum(vals) / len(vals) if vals else 0.0)
        return out

    def _sum_tile_series(attr_name):
        out = []
        for i in range(max_len):
            tot = sum((getattr(r, attr_name, []) or [])[i]
                      for r in tiles if i < len(getattr(r, attr_name, []) or []))
            out.append(tot)
        return out

    shifts = _avg_tile_series('labor_shift_log')
    sv_rates = _avg_tile_series('labor_sv_log', mult=100.0)
    caps = [getattr(nation, 'max_workday_hours', 16.0)] * len(shifts) if shifts else []

    alienation = _avg_tile_series('alienation_log', mult=100.0)
    health = _avg_tile_series('health_attrition_log', mult=1000.0)
    vice = _sum_tile_series('vice_spending_log')

    consc = _avg_tile_series('class_consciousness_log', mult=100.0)
    entertain = _avg_tile_series('entertainment_level_log', mult=100.0)
    protest = _avg_tile_series('protest_energy_log')

    strikers = _sum_tile_series('strikes_log')
    broken = _sum_tile_series('sabotage_log')
    machines = _sum_tile_series('machinery_stock_log')

    return [
        ("1. Shift Hours & Exploitation (s/v)", "line",
         [shifts, caps, sv_rates],
         [C_SHIFT, C_CAP, C_SV],
         ["avg shift hrs", "legal cap", "avg s/v rate (%)"]),

        ("2. Alienation & Health Attrition", "line",
         [alienation, health, vice],
         [C_ALIEN, C_HEALTH, C_VICE],
         ["alienation (x100)", "health risk (x1k)", "total vice ($)"]),

        ("3. Consciousness vs Entertainment", "line",
         [consc, entertain, protest],
         [C_CONSC, C_ENTERTAIN, C_PROTEST],
         ["consciousness", "entertainment", "protest"]),

        ("4. Workplace Strikes & Broken Capital", "line",
         [strikers, broken, machines],
         [C_STRIKE, C_SABOTAGE, C_MACHINES],
         ["total strikers", "broken machines", "active machines"]),
    ]


def draw_labor_dashboard(surface, world, region, font, font_small, mouse_pos=None):
    """Render the Labor & Alienation visualizer tab."""
    d = TOP_BAR_H
    panel_top = 180 + d
    panel_bottom = HEIGHT - TICKER_H - 24
    scope = world.get('citizen_scope', 'tile')
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    nation = None
    if region is not None and getattr(region, 'owner_nation', None) is not None:
        nation = region.owner_nation
    elif world.get('nations'):
        nation = world['nations'][0]

    # Status summary card
    card_y = panel_top + 52
    card_h = 60
    pygame.draw.rect(surface, (22, 24, 34), (PANEL_LEFT + 6, card_y, PANEL_W - 12, card_h), border_radius=6)
    pygame.draw.rect(surface, (45, 52, 70), (PANEL_LEFT + 6, card_y, PANEL_W - 12, card_h), 1, border_radius=6)

    if scope == 'nation' and nation is not None:
        title_txt = f"{nation.name} Labor & Alienation (National)"
        charts = nation_labor_charts(nation)
        cap_val = getattr(nation, 'max_workday_hours', 16.0)
        has_ten = getattr(nation, 'ten_hour_act', False) or cap_val <= 10.0
        has_safe = getattr(nation, 'factory_safety_act', False)
        # Summary metrics
        shifts = [r.labor_shift_log[-1] for r in nation.tiles if getattr(r, 'labor_shift_log', None)]
        avg_shift = (sum(shifts) / len(shifts)) if shifts else 12.0
        strikers_cnt = sum(sum(1 for a in r.agents if getattr(a, 'is_striking', False)) for r in nation.tiles)
        broken_cnt = sum(getattr(r, 'sabotage_log', [0])[-1] for r in nation.tiles if getattr(r, 'sabotage_log', None))
        ent_vals = [getattr(r, 'entertainment_level', 0.0) for r in nation.tiles]
        avg_ent = (sum(ent_vals) / len(ent_vals)) * 100.0 if ent_vals else 0.0
    elif region is not None:
        city_name = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
        title_txt = f"{city_name} Labor & Alienation"
        charts = tile_labor_charts(region)
        cap_val = getattr(region, 'max_workday_hours', 16.0)
        has_ten = getattr(region, 'ten_hour_act', False) or cap_val <= 10.0
        has_safe = getattr(region, 'factory_safety_act', False)
        avg_shift = region.labor_shift_log[-1] if getattr(region, 'labor_shift_log', None) else 12.0
        strikers_cnt = sum(1 for a in getattr(region, 'agents', []) if getattr(a, 'is_striking', False))
        broken_cnt = getattr(region, 'sabotage_log', [0])[-1] if getattr(region, 'sabotage_log', None) else 0
        avg_ent = getattr(region, 'entertainment_level', 0.0) * 100.0
    else:
        title_txt = "No Region Selected"
        charts = []
        has_ten = has_safe = False
        avg_shift = 12.0
        strikers_cnt = broken_cnt = 0
        avg_ent = 0.0

    # Title header
    surface.blit(font_small.render(title_txt, True, (240, 140, 80)), (PANEL_LEFT + 12, card_y + 5))

    # Law status badges
    ten_txt = "10h Act: PASS" if has_ten else "10h Act: NO (16h)"
    ten_col = (110, 210, 130) if has_ten else (220, 100, 100)
    surface.blit(font_small.render(ten_txt, True, ten_col), (PANEL_LEFT + 12, card_y + 22))

    safe_txt = "Safety: MANDATED" if has_safe else "Safety: NONE"
    safe_col = (110, 210, 130) if has_safe else (200, 150, 90)
    surface.blit(font_small.render(safe_txt, True, safe_col), (PANEL_LEFT + 130, card_y + 22))

    # Metric summary row
    metric_s = f"Shift: {avg_shift:.1f}h | Strikers: {strikers_cnt} | Broken: {broken_cnt} | Spectacle: {avg_ent:.0f}%"
    surface.blit(font_small.render(metric_s, True, (190, 205, 220)), (PANEL_LEFT + 12, card_y + 40))

    # View Mode Switcher: [ Historical Charts ]  [ 4D Alienation Radar ]
    l_mode = world.get('labor_sub_mode', 'charts')
    mode_w = (PANEL_W - 20) // 2
    btn_charts = (PANEL_LEFT + 6, card_y + card_h + 6, mode_w, 20)
    btn_radar = (PANEL_LEFT + 10 + mode_w, card_y + card_h + 6, mode_w, 20)

    is_ch_hov = btn_charts[0] <= mx <= btn_charts[0] + mode_w and btn_charts[1] <= my <= btn_charts[1] + 20
    is_rd_hov = btn_radar[0] <= mx <= btn_radar[0] + mode_w and btn_radar[1] <= my <= btn_radar[1] + 20

    pygame.draw.rect(surface, (45, 55, 75) if l_mode == 'charts' else ((32, 38, 50) if is_ch_hov else (22, 24, 34)), btn_charts, border_radius=4)
    pygame.draw.rect(surface, ACCENT if l_mode == 'charts' else (HEX_EDGE if is_ch_hov else (45, 52, 70)), btn_charts, 1, border_radius=4)
    surface.blit(font_small.render("Historical Charts", True, (255, 255, 255) if l_mode == 'charts' else TEXT), (btn_charts[0] + 10, btn_charts[1] + 2))

    pygame.draw.rect(surface, (70, 45, 80) if l_mode == 'radar' else ((32, 38, 50) if is_rd_hov else (22, 24, 34)), btn_radar, border_radius=4)
    pygame.draw.rect(surface, (180, 120, 220) if l_mode == 'radar' else (HEX_EDGE if is_rd_hov else (45, 52, 70)), btn_radar, 1, border_radius=4)
    surface.blit(font_small.render("4D Alienation Radar", True, (255, 255, 255) if l_mode == 'radar' else TEXT), (btn_radar[0] + 10, btn_radar[1] + 2))

    # Render Charts or 4D Radar
    chart_y0 = card_y + card_h + 30
    chart_y1 = panel_bottom

    if l_mode == 'radar':
        from worldview_vis_radar import draw_alienation_radar
        target = region if scope == 'tile' else nation
        draw_alienation_radar(surface, (PANEL_LEFT + 6, chart_y0, PANEL_W - 12, chart_y1 - chart_y0 - 8), target, font_small)
        return

    c_view = world.get('citizen_chart_view', 0)
    if c_view == 0 or not charts:
        if charts:
            draw_chart_grid(surface, charts, font, font_small, world['window'],
                            chart_y0, chart_y1, mouse_pos=mouse_pos)
            hint = font_small.render("Click chart to zoom | Tab/Esc = Grid", True, DIM)
            surface.blit(hint, (PANEL_LEFT + 6, chart_y1 + 4))
        else:
            hint = font_small.render("No labor data available", True, DIM)
            surface.blit(hint, (PANEL_LEFT + 12, chart_y0 + 20))
    else:
        idx = max(0, min(len(charts) - 1, c_view - 1))
        draw_chart_large(surface, charts[idx], font, font_small,
                         world['window'], chart_y0, chart_y1)
        hint = font_small.render(f"{charts[idx][0]} (Click/Esc = Grid)", True, DIM)
        surface.blit(hint, (PANEL_LEFT + 6, chart_y1 + 4))


def labor_panel_hit(pos, world):
    """Handle clicks inside the Labor & Alienation panel."""
    mx, my = pos
    d = TOP_BAR_H
    panel_top = 180 + d
    btn_w = (PANEL_W - 20) // 2
    card_y = panel_top + 52
    card_h = 60

    # View Mode Toggle (Charts vs Radar)
    btn_charts = (PANEL_LEFT + 6, card_y + card_h + 6, btn_w, 20)
    btn_radar = (PANEL_LEFT + 10 + btn_w, card_y + card_h + 6, btn_w, 20)
    if btn_charts[0] <= mx <= btn_charts[0] + btn_w and btn_charts[1] <= my <= btn_charts[1] + 20:
        world['labor_sub_mode'] = 'charts'
        return True
    if btn_radar[0] <= mx <= btn_radar[0] + btn_w and btn_radar[1] <= my <= btn_radar[1] + 20:
        world['labor_sub_mode'] = 'radar'
        return True

    # Chart Zoom Hit (when in charts mode)
    if world.get('labor_sub_mode', 'charts') == 'charts':
        chart_y0 = card_y + card_h + 30
        chart_y1 = HEIGHT - TICKER_H - 24
        if world.get('citizen_chart_view', 0) == 0:
            hit_idx = chart_at_pixel(pos, chart_y0, chart_y1, num_charts=4)
            if hit_idx is not None:
                world['citizen_chart_view'] = hit_idx
                return True
        else:
            if PANEL_LEFT + 6 <= mx <= WIDTH - 8 and chart_y0 <= my <= chart_y1:
                world['citizen_chart_view'] = 0
                return True

    return False
