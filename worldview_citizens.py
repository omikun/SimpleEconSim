"""
worldview_citizens.py — Changing Status of Citizens Visualizer for REGNUM.

Provides interactive visualizations and time-series charts of citizen status
across individual Cities/Tiles and Sovereign Nations:
  1. Social Class Composition (Serfs, Tenants, Proletarians, Dispossessed, Gentry, Bourgeoisie)
  2. Subsistence Food Source (Free Commons Foraging vs Cash Market Purchases vs Hunger)
  3. Land Tenure & Rent Burden (Commons Access % vs Cash Rent Extracted vs Debt Arrears)
  4. Economic Disparity & Protest (Gini Inequality vs Protest Energy)
"""

from __future__ import annotations
import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import TEXT, DIM, RED, GREEN, ACCENT, HEX_EDGE
from worldview_charts import (
    draw_chart_grid, draw_chart_large, chart_at_pixel,
    CHART_BOX
)

PANEL_LEFT = MAP_RIGHT + 12
PANEL_W = WIDTH - PANEL_LEFT - 6

# Color palette for social classes
C_SERF = (110, 205, 130)        # Earthy green (customary commons)
C_TENANT = (235, 195, 75)       # Amber/gold (rent-paying tenant)
C_PROLE = (220, 85, 85)         # Labor red (wage workers)
C_DISPOSS = (145, 145, 155)     # Despair grey (landless/unemployed)
C_GENTRY = (165, 115, 230)      # Aristocratic purple (lords/landlords)
C_BOURG = (85, 175, 235)        # Commercial blue (artisan/merchant/firm)

# Food & economic colors
C_FORAGE = (120, 215, 140)
C_MARKET = (240, 165, 60)
C_HUNGER = (240, 70, 70)
C_COMMONS = (90, 215, 130)
C_RENT = (230, 120, 50)
C_ARREARS = (230, 70, 115)
C_GINI = (230, 185, 70)
C_PROTEST = (240, 75, 75)


def _get_class_series(class_logs: list[dict], key: str) -> list[int]:
    """Extract one class series from a list of {class_name: count} dicts."""
    return [d.get(key, 0) for d in class_logs]


def tile_citizen_charts(region):
    """4 comprehensive citizen status charts for a single tile/city."""
    if not region:
        return []
    clogs = getattr(region, 'social_class_log', []) or []
    serfs = _get_class_series(clogs, 'serf')
    tenants = _get_class_series(clogs, 'tenant')
    proles = _get_class_series(clogs, 'proletarian')
    disposs = _get_class_series(clogs, 'dispossessed')
    gentry = [d.get('lord', 0) + d.get('landlord', 0) for d in clogs]
    bourg = [d.get('petty_bourgeois', 0) + d.get('industrialist', 0) for d in clogs]

    foraged = getattr(region, 'food_foraged_log', []) or []
    purchased = getattr(region, 'food_purchased_log', []) or []
    hs = [region.hungry_log.get(gd, []) for gd in (Goods.food, Goods.wood, Goods.furniture)]
    hungry = [sum(row) for row in zip(*hs)] if any(hs) else []

    commons = [c * 100.0 for c in (getattr(region, 'tenure_log', []) or [])]
    rent = getattr(region, 'rent_collected_log', []) or []
    arrears = getattr(region, 'rent_arrears_log', []) or []

    gini = [g * 100.0 for g in (region.gini_log.get(Goods.food, []) or [])]
    protest = region.protest_energy_log or []

    return [
        ("1. Social Classes", "line",
         [serfs, tenants, proles, disposs, gentry, bourg],
         [C_SERF, C_TENANT, C_PROLE, C_DISPOSS, C_GENTRY, C_BOURG],
         ["serf", "tenant", "worker", "disposs", "gentry", "artisan"]),

        ("2. Subsistence & Food", "line",
         [foraged, purchased, hungry],
         [C_FORAGE, C_MARKET, C_HUNGER],
         ["foraged", "market food", "hungry"]),

        ("3. Commons & Rent Burden", "line",
         [commons, rent, arrears],
         [C_COMMONS, C_RENT, C_ARREARS],
         ["commons %", "rent ($)", "arrears ($)"]),

        ("4. Disparity & Unrest", "line",
         [gini, protest],
         [C_GINI, C_PROTEST],
         ["gini (x100)", "protest"]),
    ]


def nation_citizen_charts(nation):
    """4 aggregated citizen status charts across all constituent tiles of a nation."""
    tiles = getattr(nation, 'tiles', [])
    if not tiles:
        return []

    max_len = max((len(getattr(r, 'social_class_log', [])) for r in tiles), default=0)

    def agg_class(key):
        res = []
        for t in range(max_len):
            total = sum(r.social_class_log[t].get(key, 0)
                        for r in tiles if t < len(r.social_class_log))
            res.append(total)
        return res

    def agg_gentry():
        res = []
        for t in range(max_len):
            total = sum(r.social_class_log[t].get('lord', 0) + r.social_class_log[t].get('landlord', 0)
                        for r in tiles if t < len(r.social_class_log))
            res.append(total)
        return res

    def agg_bourg():
        res = []
        for t in range(max_len):
            total = sum(r.social_class_log[t].get('petty_bourgeois', 0) + r.social_class_log[t].get('industrialist', 0)
                        for r in tiles if t < len(r.social_class_log))
            res.append(total)
        return res

    def agg_series(attr):
        res = []
        for t in range(max_len):
            total = sum(getattr(r, attr)[t]
                        for r in tiles if hasattr(r, attr) and t < len(getattr(r, attr)))
            res.append(total)
        return res

    def agg_avg(attr, mult=1.0):
        res = []
        for t in range(max_len):
            vals = [getattr(r, attr)[t]
                    for r in tiles if hasattr(r, attr) and t < len(getattr(r, attr))]
            avg = (sum(vals) / len(vals)) * mult if vals else 0.0
            res.append(avg)
        return res

    serfs = agg_class('serf')
    tenants = agg_class('tenant')
    proles = agg_class('proletarian')
    disposs = agg_class('dispossessed')
    gentry = agg_gentry()
    bourg = agg_bourg()

    foraged = agg_series('food_foraged_log')
    purchased = agg_series('food_purchased_log')

    hungry_series = []
    for t in range(max_len):
        h_sum = 0
        for r in tiles:
            for gd in (Goods.food, Goods.wood, Goods.furniture):
                hlog = r.hungry_log.get(gd, [])
                if t < len(hlog):
                    h_sum += hlog[t]
        hungry_series.append(h_sum)

    avg_commons = agg_avg('tenure_log', 100.0)
    total_rent = agg_series('rent_collected_log')
    total_arrears = agg_series('rent_arrears_log')

    avg_gini = []
    for t in range(max_len):
        gvals = [r.gini_log.get(Goods.food, [])[t]
                 for r in tiles if t < len(r.gini_log.get(Goods.food, []))]
        avg_gini.append((sum(gvals) / len(gvals) * 100.0) if gvals else 0.0)

    avg_protest = agg_avg('protest_energy_log')

    return [
        (f"1. {nation.name} Classes", "line",
         [serfs, tenants, proles, disposs, gentry, bourg],
         [C_SERF, C_TENANT, C_PROLE, C_DISPOSS, C_GENTRY, C_BOURG],
         ["serf", "tenant", "worker", "disposs", "gentry", "artisan"]),

        (f"2. {nation.name} Food Source", "line",
         [foraged, purchased, hungry_series],
         [C_FORAGE, C_MARKET, C_HUNGER],
         ["foraged", "market food", "hungry"]),

        (f"3. {nation.name} Commons & Rent", "line",
         [avg_commons, total_rent, total_arrears],
         [C_COMMONS, C_RENT, C_ARREARS],
         ["avg commons %", "rent ($)", "arrears ($)"]),

        (f"4. {nation.name} Disparity & Protest", "line",
         [avg_gini, avg_protest],
         [C_GINI, C_PROTEST],
         ["avg gini (x100)", "avg protest"]),
    ]


def draw_citizens_panel(surface, world, region, font, font_small, mouse_pos=None):
    """Draw the Citizens / Society tab showing changing citizen status."""
    d = TOP_BAR_H
    panel_top = 180 + d
    panel_bottom = HEIGHT - TICKER_H - 24
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    if region is None and world.get('nations') and world['nations'][0].tiles:
        region = world['nations'][0].tiles[0]

    scope = world.get('citizen_scope', world.get('scope', 'tile'))
    nation = getattr(region, 'owner_nation', None) if region is not None else None
    if nation is None and world.get('nations'):
        nation = world['nations'][0]

    # 1. Header Scope Toggle Buttons: [ City / Tile ]  [ Nation ]
    btn_w = (PANEL_W - 20) // 2
    btn_h = 22
    tile_btn = (PANEL_LEFT + 6, panel_top + 4, btn_w, btn_h)
    nat_btn = (PANEL_LEFT + 10 + btn_w, panel_top + 4, btn_w, btn_h)

    is_tile_hov = tile_btn[0] <= mx <= tile_btn[0] + btn_w and tile_btn[1] <= my <= tile_btn[1] + btn_h
    is_nat_hov = nat_btn[0] <= mx <= nat_btn[0] + btn_w and nat_btn[1] <= my <= nat_btn[1] + btn_h

    pygame.draw.rect(surface, (55, 75, 110) if scope == 'tile' else ((40, 48, 65) if is_tile_hov else (28, 30, 40)), tile_btn, border_radius=4)
    pygame.draw.rect(surface, ACCENT if scope == 'tile' else (HEX_EDGE if is_tile_hov else (45, 52, 70)), tile_btn, 1, border_radius=4)
    city_name = getattr(region, 'display_name', getattr(region, 'city_name', region.name)) if region else 'None'
    t_lbl = font_small.render(f"Tile: {city_name}", True, (255, 255, 255) if scope == 'tile' else TEXT)
    surface.blit(t_lbl, t_lbl.get_rect(center=(tile_btn[0] + btn_w // 2, tile_btn[1] + btn_h // 2)))

    pygame.draw.rect(surface, (55, 75, 110) if scope == 'nation' else ((40, 48, 65) if is_nat_hov else (28, 30, 40)), nat_btn, border_radius=4)
    pygame.draw.rect(surface, ACCENT if scope == 'nation' else (HEX_EDGE if is_nat_hov else (45, 52, 70)), nat_btn, 1, border_radius=4)
    n_lbl = font_small.render(f"Nation: {nation.name if nation else 'None'}", True, (255, 255, 255) if scope == 'nation' else TEXT)
    surface.blit(n_lbl, n_lbl.get_rect(center=(nat_btn[0] + btn_w // 2, nat_btn[1] + btn_h // 2)))

    # 1b. Sub-Tab Switcher: [ Class & Tenure ]  [ Labor & Alienation ]
    subtab = world.get('citizen_subtab', 'class')
    sub_class_btn = (PANEL_LEFT + 6, panel_top + 28, btn_w, 20)
    sub_labor_btn = (PANEL_LEFT + 10 + btn_w, panel_top + 28, btn_w, 20)

    is_sc_hov = sub_class_btn[0] <= mx <= sub_class_btn[0] + btn_w and sub_class_btn[1] <= my <= sub_class_btn[1] + 20
    is_sl_hov = sub_labor_btn[0] <= mx <= sub_labor_btn[0] + btn_w and sub_labor_btn[1] <= my <= sub_labor_btn[1] + 20

    pygame.draw.rect(surface, (50, 70, 95) if subtab == 'class' else ((35, 42, 55) if is_sc_hov else (24, 26, 35)), sub_class_btn, border_radius=4)
    pygame.draw.rect(surface, (110, 205, 130) if subtab == 'class' else (HEX_EDGE if is_sc_hov else (45, 52, 70)), sub_class_btn, 1, border_radius=4)
    sc_lbl = font_small.render("Class & Tenure", True, (255, 255, 255) if subtab == 'class' else TEXT)
    surface.blit(sc_lbl, sc_lbl.get_rect(center=(sub_class_btn[0] + btn_w // 2, sub_class_btn[1] + 10)))

    pygame.draw.rect(surface, (70, 50, 90) if subtab == 'labor' else ((35, 42, 55) if is_sl_hov else (24, 26, 35)), sub_labor_btn, border_radius=4)
    pygame.draw.rect(surface, (230, 90, 90) if subtab == 'labor' else (HEX_EDGE if is_sl_hov else (45, 52, 70)), sub_labor_btn, 1, border_radius=4)
    sl_lbl = font_small.render("Labor & Alienation", True, (255, 255, 255) if subtab == 'labor' else TEXT)
    surface.blit(sl_lbl, sl_lbl.get_rect(center=(sub_labor_btn[0] + btn_w // 2, sub_labor_btn[1] + 10)))

    if subtab == 'labor':
        from worldview_labor_ui import draw_labor_dashboard
        draw_labor_dashboard(surface, world, region, font, font_small, mouse_pos=mouse_pos)
        return

    # 2. Live Citizen Status KPI Card
    card_y = panel_top + 52
    card_h = 60
    card_rect = (PANEL_LEFT + 6, card_y, PANEL_W - 14, card_h)
    pygame.draw.rect(surface, (24, 26, 36), card_rect, border_radius=5)
    pygame.draw.rect(surface, (45, 50, 70), card_rect, 1, border_radius=5)

    if scope == 'nation' and nation is not None:
        total_pop = sum(len(r.agents) for r in nation.tiles)
        clogs = [r.social_class_log[-1] if r.social_class_log else {} for r in nation.tiles]
        serf_c = sum(d.get('serf', 0) for d in clogs)
        tenant_c = sum(d.get('tenant', 0) for d in clogs)
        prole_c = sum(d.get('proletarian', 0) for d in clogs)
        disposs_c = sum(d.get('dispossessed', 0) for d in clogs)
        gentry_c = sum(d.get('lord', 0) + d.get('landlord', 0) for d in clogs)
        bourg_c = sum(d.get('petty_bourgeois', 0) + d.get('industrialist', 0) for d in clogs)
        title_txt = f"{nation.name} Citizens ({total_pop:,} Pop)"
        charts = nation_citizen_charts(nation)
    elif region is not None:
        agents = getattr(region, 'agents', [])
        total_pop = len(agents)
        clog = region.social_class_log[-1] if getattr(region, 'social_class_log', None) else {}
        serf_c = clog.get('serf', 0)
        tenant_c = clog.get('tenant', 0)
        prole_c = clog.get('proletarian', 0)
        disposs_c = clog.get('dispossessed', 0)
        gentry_c = clog.get('lord', 0) + clog.get('landlord', 0)
        bourg_c = clog.get('petty_bourgeois', 0) + clog.get('industrialist', 0)
        title_txt = f"{city_name} Citizens ({total_pop} Pop)"
        charts = tile_citizen_charts(region)
    else:
        total_pop = 0
        serf_c = tenant_c = prole_c = disposs_c = gentry_c = bourg_c = 0
        title_txt = "No Region Selected"
        charts = []

    surface.blit(font_small.render(title_txt, True, ACCENT), (PANEL_LEFT + 12, card_y + 5))

    # Proportional Class Distribution Color Bar Gauge
    bar_x = PANEL_LEFT + 12
    bar_y = card_y + 22
    bar_w = PANEL_W - 26
    bar_h = 10
    pygame.draw.rect(surface, (35, 38, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=3)

    classes_counts = [
        (serf_c, C_SERF),
        (tenant_c, C_TENANT),
        (prole_c, C_PROLE),
        (disposs_c, C_DISPOSS),
        (gentry_c, C_GENTRY),
        (bourg_c, C_BOURG),
    ]
    cur_bx = bar_x
    if total_pop > 0:
        for cnt, color in classes_counts:
            if cnt <= 0:
                continue
            seg_w = max(1, int((cnt / total_pop) * bar_w))
            seg_w = min(seg_w, (bar_x + bar_w) - cur_bx)
            pygame.draw.rect(surface, color, (cur_bx, bar_y, seg_w, bar_h))
            cur_bx += seg_w

    # Class breakdown text summary
    s_desc = (f"Serf {serf_c} | Ten {tenant_c} | Prole {prole_c} | "
              f"Disp {disposs_c} | Gent {gentry_c}")
    surface.blit(font_small.render(s_desc, True, (190, 205, 220)), (PANEL_LEFT + 12, card_y + 38))

    # 2b. View Switcher: [ Historical Charts ]  [ Wealth Pyramid & Lorenz ]
    c_mode = world.get('citizen_class_mode', 'charts')
    mode_w = (PANEL_W - 20) // 2
    btn_charts = (PANEL_LEFT + 6, card_y + card_h + 6, mode_w, 20)
    btn_pyr = (PANEL_LEFT + 10 + mode_w, card_y + card_h + 6, mode_w, 20)

    is_ch_hov = btn_charts[0] <= mx <= btn_charts[0] + mode_w and btn_charts[1] <= my <= btn_charts[1] + 20
    is_py_hov = btn_pyr[0] <= mx <= btn_pyr[0] + mode_w and btn_pyr[1] <= my <= btn_pyr[1] + 20

    pygame.draw.rect(surface, (45, 55, 75) if c_mode == 'charts' else ((32, 38, 50) if is_ch_hov else (22, 24, 34)), btn_charts, border_radius=4)
    pygame.draw.rect(surface, ACCENT if c_mode == 'charts' else (HEX_EDGE if is_ch_hov else (45, 52, 70)), btn_charts, 1, border_radius=4)
    surface.blit(font_small.render("Historical Charts", True, (255, 255, 255) if c_mode == 'charts' else TEXT), (btn_charts[0] + 10, btn_charts[1] + 2))

    pygame.draw.rect(surface, (75, 65, 45) if c_mode == 'pyramid' else ((32, 38, 50) if is_py_hov else (22, 24, 34)), btn_pyr, border_radius=4)
    pygame.draw.rect(surface, (245, 210, 80) if c_mode == 'pyramid' else (HEX_EDGE if is_py_hov else (45, 52, 70)), btn_pyr, 1, border_radius=4)
    surface.blit(font_small.render("Pyramid & Lorenz", True, (255, 255, 255) if c_mode == 'pyramid' else TEXT), (btn_pyr[0] + 10, btn_pyr[1] + 2))

    # 3. Chart Grid, Zoom View, or Wealth Pyramid
    chart_y0 = card_y + card_h + 30
    chart_y1 = panel_bottom

    if c_mode == 'pyramid':
        from worldview_vis_pyramid import draw_class_wealth_pyramid, draw_lorenz_curve
        target = region if scope == 'tile' else nation
        avail_h = chart_y1 - chart_y0 - 6
        h_each = avail_h // 2
        draw_class_wealth_pyramid(surface, (PANEL_LEFT + 6, chart_y0, PANEL_W - 12, h_each), target, font_small)
        draw_lorenz_curve(surface, (PANEL_LEFT + 6, chart_y0 + h_each + 6, PANEL_W - 12, h_each), target, font_small)
        return

    c_view = world.get('citizen_chart_view', 0)
    if c_view == 0 or not charts:
        # Draw 2x2 grid
        if charts:
            draw_chart_grid(surface, charts, font, font_small, world['window'],
                            chart_y0, chart_y1, mouse_pos=mouse_pos)
            hint = font_small.render("Click chart to zoom | Tab/Esc = Grid", True, DIM)
            surface.blit(hint, (PANEL_LEFT + 6, chart_y1 + 4))
        else:
            hint = font_small.render("Hover or click a hex for citizen data", True, DIM)
            surface.blit(hint, (PANEL_LEFT + 12, chart_y0 + 20))
    else:
        idx = max(0, min(len(charts) - 1, c_view - 1))
        draw_chart_large(surface, charts[idx], font, font_small,
                         world['window'], chart_y0, chart_y1)
        hint = font_small.render(f"{charts[idx][0]} (Click/Esc = Grid)", True, DIM)
        surface.blit(hint, (PANEL_LEFT + 6, chart_y1 + 4))


def citizen_panel_hit(pos, world):
    """Handle clicks inside the Citizens tab."""
    mx, my = pos
    d = TOP_BAR_H
    panel_top = 180 + d
    btn_w = (PANEL_W - 20) // 2
    btn_h = 22
    tile_btn = (PANEL_LEFT + 6, panel_top + 4, btn_w, btn_h)
    nat_btn = (PANEL_LEFT + 10 + btn_w, panel_top + 4, btn_w, btn_h)

    # Scope Toggle
    if tile_btn[0] <= mx <= tile_btn[0] + btn_w and tile_btn[1] <= my <= tile_btn[1] + btn_h:
        world['citizen_scope'] = 'tile'
        return True
    if nat_btn[0] <= mx <= nat_btn[0] + btn_w and nat_btn[1] <= my <= nat_btn[1] + btn_h:
        world['citizen_scope'] = 'nation'
        return True

    # Sub-tab Toggle
    sub_class_btn = (PANEL_LEFT + 6, panel_top + 28, btn_w, 20)
    sub_labor_btn = (PANEL_LEFT + 10 + btn_w, panel_top + 28, btn_w, 20)
    if sub_class_btn[0] <= mx <= sub_class_btn[0] + btn_w and sub_class_btn[1] <= my <= sub_class_btn[1] + 20:
        world['citizen_subtab'] = 'class'
        world['citizen_chart_view'] = 0
        return True
    if sub_labor_btn[0] <= mx <= sub_labor_btn[0] + btn_w and sub_labor_btn[1] <= my <= sub_labor_btn[1] + 20:
        world['citizen_subtab'] = 'labor'
        world['citizen_chart_view'] = 0
        return True

    # If in labor subtab, pass to labor panel hit
    if world.get('citizen_subtab') == 'labor':
        from worldview_labor_ui import labor_panel_hit
        return labor_panel_hit(pos, world)

    # Class View Mode Toggle (Charts vs Pyramid)
    card_y = panel_top + 52
    card_h = 60
    btn_charts = (PANEL_LEFT + 6, card_y + card_h + 6, btn_w, 20)
    btn_pyr = (PANEL_LEFT + 10 + btn_w, card_y + card_h + 6, btn_w, 20)
    if btn_charts[0] <= mx <= btn_charts[0] + btn_w and btn_charts[1] <= my <= btn_charts[1] + 20:
        world['citizen_class_mode'] = 'charts'
        return True
    if btn_pyr[0] <= mx <= btn_pyr[0] + btn_w and btn_pyr[1] <= my <= btn_pyr[1] + 20:
        world['citizen_class_mode'] = 'pyramid'
        return True

    # Chart Zoom Hit (when in charts mode)
    if world.get('citizen_class_mode', 'charts') == 'charts':
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
