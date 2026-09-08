"""
worldview_vis_circuits.py — Circuit of Capital Sankey & TRPF Profit Curve Visualizer.

Implements:
1. The Marxian Circuit of Capital (M -> C -> P -> C' -> M') Sankey Flow Diagram:
   - Variable Capital V (wages) & Constant Capital C (machinery + materials).
   - Living labor extraction yielding Surplus Value S.
   - Realization into Capitalist Net Profit, Machinery Reinvestment, and Campaign War Chest.
   - Wage expenditure into Subsistence Food, Ground Rent, Despair Vices, and Entertainment.
2. Organic Composition of Capital (c/v) vs Tendency of Rate of Profit to Fall (TRPF) curve.
"""

import math
import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT
from worldview_map import (
    NATION_COLORS, TEXT, DIM, RED, GREEN, ACCENT
)

COL_M = (245, 210, 85)        # Gold (Money Capital M)
COL_C = (100, 180, 240)       # Blue (Constant Capital C)
COL_V = (235, 90, 90)         # Crimson (Variable Capital V)
COL_P = (180, 110, 230)       # Purple (Production Process P)
COL_S = (240, 140, 50)        # Orange (Surplus Value S)
COL_RENT = (235, 125, 55)     # Orange-red
COL_VICE = (90, 210, 180)     # Teal (Despair spending)
COL_ENT = (70, 195, 235)      # Cyan (Mass entertainment)
COL_BACKLASH = (220, 60, 60)  # Dark Red (Political opposition fund)

CARD_BG = (22, 24, 36)
CARD_BORDER = (50, 55, 75)


def _get_font(size):
    from worldview_ui import get_font
    return get_font(size)


def _draw_flow_ribbon(surface, p1, p2, w1, w2, color, alpha=160):
    """Draw a smooth Bezier flow band between two vertical node segments."""
    x1, y1 = p1
    x2, y2 = p2

    surf = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
    fill_col = (*color[:3], min(230, max(60, alpha)))

    # Compute cubic Bezier control points
    dx = (x2 - x1) * 0.5
    steps = 24
    top_pts = []
    bot_pts = []

    for i in range(steps + 1):
        t = i / steps
        # Cubic bezier interpolation
        bx = (1-t)**3 * x1 + 3*(1-t)**2*t*(x1+dx) + 3*(1-t)*t**2*(x2-dx) + t**3 * x2
        by1 = (1-t)**3 * y1 + 3*(1-t)**2*t*y1 + 3*(1-t)*t**2*y2 + t**3 * y2
        by2 = (1-t)**3 * (y1+w1) + 3*(1-t)**2*t*(y1+w1) + 3*(1-t)*t**2*(y2+w2) + t**3 * (y2+w2)
        top_pts.append((bx, by1))
        bot_pts.append((bx, by2))

    poly = top_pts + bot_pts[::-1]
    if len(poly) >= 4:
        pygame.draw.polygon(surf, fill_col, poly)
        # Subtle border outline
        pygame.draw.lines(surf, (*color[:3], min(255, alpha + 30)), False, top_pts, 1)
        pygame.draw.lines(surf, (*color[:3], min(255, alpha + 30)), False, bot_pts, 1)

    surface.blit(surf, (0, 0))


def draw_circuit_of_capital_sankey(surface, world, box_x, box_y, box_w, box_h, font, cell_font, section_font, mouse_pos=None):
    """Render the full Marxian Capital Circuit (M -> C -> P -> C' -> M') Sankey diagram."""
    nations = world.get('nations', [])
    if not nations:
        return

    # Select target nation
    n_idx = world.get('compare_circuit_nation', 0) % len(nations)
    active_nation = nations[n_idx]

    mx, my = mouse_pos if mouse_pos else (-1, -1)

    # 1. Header & Nation Switcher
    surface.blit(section_font.render(f"Marxian Circuit of Capital: {active_nation.name} ({active_nation.currency})", True, ACCENT), (box_x + 20, box_y + 8))

    # Switcher buttons across nations
    nx = box_x + box_w - 360
    for i, n in enumerate(nations):
        btn_r = (nx + i * 115, box_y + 8, 110, 24)
        is_sel = (i == n_idx)
        is_hov = btn_r[0] <= mx <= btn_r[0] + btn_r[2] and btn_r[1] <= my <= btn_r[1] + btn_r[3]
        if is_hov:
            from worldview_tooltips import get_button_tooltip_data
            tip = get_button_tooltip_data('circuit_nation_btn', world, nation=n)
            if tip:
                tip['btn_rect'] = btn_r
                world['_hovered_left_tooltip'] = tip
        bg = ACCENT if is_sel else ((44, 44, 58) if is_hov else (30, 30, 42))
        pygame.draw.rect(surface, bg, btn_r, border_radius=4)
        pygame.draw.rect(surface, (80, 80, 100), btn_r, 1, border_radius=4)
        ts = cell_font.render(n.name[:11], True, (20, 20, 24) if is_sel else (255, 255, 255) if is_hov else TEXT)
        surface.blit(ts, ts.get_rect(center=(btn_r[0] + 55, btn_r[1] + 12)))

    # Compute Capital Circuit Aggregates for Active Nation
    tiles = active_nation.tiles
    wages_total = 0.0
    constant_total = 0.0
    surplus_total = 0.0
    rent_total = 0.0
    despair_total = 0.0
    ent_total = 0.0
    backlash_donations = 0.0

    for t in tiles:
        # Variable capital (wages paid)
        for a in getattr(t, 'agents', []):
            if getattr(a, 'employer', None) is not None and not getattr(a, 'is_corporation', False):
                wages_total += getattr(a, 'wage', 1.0)
            if getattr(a, 'is_corporation', False):
                # Constant capital: machinery stock upkeep & material inputs
                constant_total += getattr(a, 'machinery_level', 1) * 3.5 + 5.0
            # Despair spending
            if getattr(a, 'despair', 0.0) > 0.4:
                despair_total += 0.50
            # Capitalist political donations
            if getattr(a, 'is_corporation', False) or getattr(a, 'is_lord', False):
                if active_nation.ten_hour_act or active_nation.factory_safety_act:
                    backlash_donations += min(15.0, getattr(a, 'cash', 0.0) * 0.05)

        surplus_log = getattr(t, 'surplus_value_log', [])
        surplus_total += surplus_log[-1] if surplus_log else 15.0
        rent_log = getattr(t, 'rent_collected_log', [])
        rent_total += rent_log[-1] if rent_log else 5.0
        ent_total += getattr(t, 'entertainment_level', 0.0) * 8.0

    wages_total = max(20.0, wages_total)
    constant_total = max(30.0, constant_total)
    surplus_total = max(25.0, surplus_total)
    m_initial = wages_total + constant_total
    c_prime_total = m_initial + surplus_total

    # Worker wage distribution
    rent_flow = min(wages_total * 0.40, max(5.0, rent_total))
    despair_flow = min(wages_total * 0.20, max(2.0, despair_total))
    ent_flow = min(wages_total * 0.15, max(1.0, ent_total))
    food_flow = max(5.0, wages_total - rent_flow - despair_flow - ent_flow)

    # Surplus value distribution
    backlash_flow = min(surplus_total * 0.30, max(2.0, backlash_donations))
    reinvest_flow = surplus_total * 0.45
    luxury_flow = max(5.0, surplus_total - backlash_flow - reinvest_flow)

    # 2. Sankey Layout Geometry (5 Stage Columns)
    col_x = [
        box_x + 30,                 # Stage 1: Money M
        box_x + 240,                # Stage 2: C (Constant) & V (Variable)
        box_x + 470,                # Stage 3: Production P
        box_x + 700,                # Stage 4: Commodities C' (Realization)
        box_x + 940,                # Stage 5: Final Splits (Surplus Realized & Wages Consumed)
    ]

    base_y = box_y + 46
    diag_h = box_h - 70

    # Column Titles
    stage_titles = [
        "1. Money Capital (M)",
        "2. Productive Inputs",
        "3. Production (P)",
        "4. Commodity Value (C')",
        "5. Realization & Class Split",
    ]
    for i, st in enumerate(stage_titles):
        surface.blit(_get_font(13).render(st, True, ACCENT), (col_x[i], base_y))

    sankey_top_y = base_y + 26
    scale_y = min(1.2, (diag_h - 60) / max(1.0, c_prime_total * 1.3))

    # --- Stage 1 Node: Money Capital M ---
    m_h = int(m_initial * scale_y)
    m_rect = (col_x[0], sankey_top_y + 40, 24, m_h)
    pygame.draw.rect(surface, COL_M, m_rect, border_radius=4)
    surface.blit(_get_font(13).render(f"M: ${m_initial:,.0f}", True, (255, 240, 160)), (col_x[0], m_rect[1] - 16))

    # --- Stage 2 Nodes: Constant Capital C & Variable Capital V ---
    c_h = int(constant_total * scale_y)
    v_h = int(wages_total * scale_y)
    c_rect = (col_x[1], sankey_top_y + 10, 24, c_h)
    v_rect = (col_x[1], sankey_top_y + 20 + c_h, 24, v_h)

    pygame.draw.rect(surface, COL_C, c_rect, border_radius=4)
    pygame.draw.rect(surface, COL_V, v_rect, border_radius=4)

    surface.blit(_get_font(12).render(f"Constant C (${constant_total:,.0f})", True, COL_C), (col_x[1] + 28, c_rect[1] + 2))
    surface.blit(_get_font(11).render("Machinery & Raw Materials", True, DIM), (col_x[1] + 28, c_rect[1] + 16))

    surface.blit(_get_font(12).render(f"Variable V (${wages_total:,.0f})", True, COL_V), (col_x[1] + 28, v_rect[1] + 2))
    surface.blit(_get_font(11).render("Wages Paid to Labor", True, DIM), (col_x[1] + 28, v_rect[1] + 16))

    # Flow Ribbons: M -> C and M -> V
    _draw_flow_ribbon(surface, (col_x[0] + 24, m_rect[1]), (col_x[1], c_rect[1]), c_h, c_h, COL_C)
    _draw_flow_ribbon(surface, (col_x[0] + 24, m_rect[1] + c_h), (col_x[1], v_rect[1]), v_h, v_h, COL_V)

    # --- Stage 3 Node: Production Process P (Living Labor Extraction) ---
    p_h = int((constant_total + wages_total + surplus_total) * scale_y)
    p_rect = (col_x[2], sankey_top_y + 10, 24, p_h)
    pygame.draw.rect(surface, COL_P, p_rect, border_radius=4)

    surface.blit(_get_font(12).render(f"Production P (${c_prime_total:,.0f})", True, COL_P), (col_x[2] + 28, p_rect[1] + 4))
    surface.blit(_get_font(11).render(f"Surplus s/v: +${surplus_total:,.0f} extracted", True, COL_S), (col_x[2] + 28, p_rect[1] + 18))

    # Flow Ribbons: C -> P, V -> P
    _draw_flow_ribbon(surface, (col_x[1] + 24, c_rect[1]), (col_x[2], p_rect[1]), c_h, c_h, COL_C)
    _draw_flow_ribbon(surface, (col_x[1] + 24, v_rect[1]), (col_x[2], p_rect[1] + c_h), v_h, v_h, COL_V)

    # --- Stage 4 Node: Commodities C' (Realization) ---
    c_prime_rect = (col_x[3], sankey_top_y + 10, 24, p_h)
    pygame.draw.rect(surface, (210, 195, 120), c_prime_rect, border_radius=4)
    surface.blit(_get_font(12).render(f"Commodities C' (${c_prime_total:,.0f})", True, (255, 235, 160)), (col_x[3] + 28, c_prime_rect[1] + 4))
    surface.blit(_get_font(11).render("Sold on Domestic & Foreign Markets", True, DIM), (col_x[3] + 28, c_prime_rect[1] + 18))

    _draw_flow_ribbon(surface, (col_x[2] + 24, p_rect[1]), (col_x[3], c_prime_rect[1]), p_h, p_h, COL_P)

    # --- Stage 5 Nodes: Split Realization & Class Consumption ---
    # Top Branch: Capitalist Surplus Value Realization (S)
    s_reinvest_h = int(reinvest_flow * scale_y)
    s_lux_h = int(luxury_flow * scale_y)
    s_backlash_h = int(backlash_flow * scale_y)

    cur_s_y = sankey_top_y + 5
    r_reinvest = (col_x[4], cur_s_y, 20, s_reinvest_h)
    pygame.draw.rect(surface, (110, 215, 130), r_reinvest, border_radius=3)
    surface.blit(_get_font(11).render(f"Machinery Reinvestment: ${reinvest_flow:,.0f}", True, (120, 230, 140)), (col_x[4] + 26, cur_s_y + 1))
    cur_s_y += s_reinvest_h + 6

    r_lux = (col_x[4], cur_s_y, 20, s_lux_h)
    pygame.draw.rect(surface, COL_S, r_lux, border_radius=3)
    surface.blit(_get_font(11).render(f"Capitalist Luxury Consumption: ${luxury_flow:,.0f}", True, (255, 190, 90)), (col_x[4] + 26, cur_s_y + 1))
    cur_s_y += s_lux_h + 6

    r_backlash = (col_x[4], cur_s_y, 20, s_backlash_h)
    pygame.draw.rect(surface, COL_BACKLASH, r_backlash, border_radius=3)
    surface.blit(_get_font(11).render(f"Electoral War Chest (Anti-Labor): ${backlash_flow:,.0f}", True, (255, 90, 90)), (col_x[4] + 26, cur_s_y + 1))
    cur_s_y += s_backlash_h + 16

    # Bottom Branch: Proletarian Wage Expenditures (V)
    w_food_h = int(food_flow * scale_y)
    w_rent_h = int(rent_flow * scale_y)
    w_despair_h = int(despair_flow * scale_y)
    w_ent_h = int(ent_flow * scale_y)

    r_food = (col_x[4], cur_s_y, 20, w_food_h)
    pygame.draw.rect(surface, (230, 210, 80), r_food, border_radius=3)
    surface.blit(_get_font(11).render(f"Subsistence Food: ${food_flow:,.0f}", True, (240, 220, 100)), (col_x[4] + 26, cur_s_y + 1))
    cur_s_y += w_food_h + 6

    r_rent = (col_x[4], cur_s_y, 20, w_rent_h)
    pygame.draw.rect(surface, COL_RENT, r_rent, border_radius=3)
    surface.blit(_get_font(11).render(f"Ground Rent to Landlords: ${rent_flow:,.0f}", True, COL_RENT), (col_x[4] + 26, cur_s_y + 1))
    cur_s_y += w_rent_h + 6

    r_despair = (col_x[4], cur_s_y, 20, w_despair_h)
    pygame.draw.rect(surface, COL_VICE, r_despair, border_radius=3)
    surface.blit(_get_font(11).render(f"Despair Spending (Vices/Vagabonds): ${despair_flow:,.0f}", True, COL_VICE), (col_x[4] + 26, cur_s_y + 1))
    cur_s_y += w_despair_h + 6

    r_ent = (col_x[4], cur_s_y, 20, w_ent_h)
    pygame.draw.rect(surface, COL_ENT, r_ent, border_radius=3)
    surface.blit(_get_font(11).render(f"Spectacle & Entertainment Fees: ${ent_flow:,.0f}", True, COL_ENT), (col_x[4] + 26, cur_s_y + 1))

    # Flow Ribbons from C' to Final Branches
    _draw_flow_ribbon(surface, (col_x[3] + 24, c_prime_rect[1]), (col_x[4], r_reinvest[1]), s_reinvest_h, s_reinvest_h, (110, 215, 130))
    _draw_flow_ribbon(surface, (col_x[3] + 24, c_prime_rect[1] + s_reinvest_h), (col_x[4], r_lux[1]), s_lux_h, s_lux_h, COL_S)
    _draw_flow_ribbon(surface, (col_x[3] + 24, c_prime_rect[1] + s_reinvest_h + s_lux_h), (col_x[4], r_backlash[1]), s_backlash_h, s_backlash_h, COL_BACKLASH)

    v_flow_start_y = c_prime_rect[1] + s_reinvest_h + s_lux_h + s_backlash_h
    _draw_flow_ribbon(surface, (col_x[3] + 24, v_flow_start_y), (col_x[4], r_food[1]), w_food_h, w_food_h, (230, 210, 80))
    _draw_flow_ribbon(surface, (col_x[3] + 24, v_flow_start_y + w_food_h), (col_x[4], r_rent[1]), w_rent_h, w_rent_h, COL_RENT)
    _draw_flow_ribbon(surface, (col_x[3] + 24, v_flow_start_y + w_food_h + w_rent_h), (col_x[4], r_despair[1]), w_despair_h, w_despair_h, COL_VICE)
    # Draw TRPF curve in bottom strip
    trpf_y = box_y + box_h - 185
    trpf_h = 175
    trpf_rect = (box_x + 30, trpf_y, box_w - 60, trpf_h)
    if trpf_rect[0] <= mx <= trpf_rect[0] + trpf_rect[2] and trpf_rect[1] <= my <= trpf_rect[1] + 28:
        from worldview_tooltips import get_button_tooltip_data
        tip = get_button_tooltip_data('trpf_curve_plot', world, nation=active_nation)
        if tip:
            tip['btn_rect'] = trpf_rect
            world['_hovered_left_tooltip'] = tip
    draw_trpf_curve(surface, trpf_rect, active_nation, _get_font(12))


def circuit_sankey_hit(pos, world, box_x, box_y, box_w, box_h):
    """Detect clicks on nation switcher buttons inside Circuit Sankey view."""
    mx, my = pos
    nations = world.get('nations', [])
    if not nations:
        return False

    nx = box_x + box_w - 360
    for i in range(len(nations)):
        btn_r = (nx + i * 115, box_y + 8, 110, 24)
        if btn_r[0] <= mx <= btn_r[0] + btn_r[2] and btn_r[1] <= my <= btn_r[1] + btn_r[3]:
            world['compare_circuit_nation'] = i
            return True
    return False


def draw_trpf_curve(surface, rect, region_or_nation, font_small):
    """Render the Organic Composition (c/v) vs Tendency of Rate of Profit to Fall (TRPF) curve."""
    x, y, w, h = rect
    pygame.draw.rect(surface, CARD_BG, rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, rect, 1, border_radius=6)

    # Title & Legend
    surface.blit(font_small.render("TRPF & Organic Composition of Capital (c/v)", True, ACCENT), (x + 10, y + 6))

    leg_x = x + 10
    leg_y = y + 24
    legends = [
        ("Organic Comp (c/v)", COL_C),
        ("Rate of Profit %", COL_M),
        ("Shift Hours", COL_V),
    ]
    for lbl, col in legends:
        pygame.draw.rect(surface, col, (leg_x, leg_y + 2, 8, 8), border_radius=2)
        surface.blit(_get_font(10).render(lbl, True, TEXT), (leg_x + 12, leg_y))
        leg_x += 115

    # Extract historical logs
    sv_log = getattr(region_or_nation, 'surplus_value_log', []) or [20.0, 25.0, 32.0]
    shift_log = getattr(region_or_nation, 'avg_shift_hours_log', []) or [8.0, 10.0, 12.0]
    pts_count = max(len(sv_log), len(shift_log))

    # Synthetic c/v based on machinery accumulation and wage bill
    cv_series = []
    profit_series = []
    shift_series = shift_log[-pts_count:] if shift_log else [8.0]

    for i in range(pts_count):
        s_val = sv_log[i] if i < len(sv_log) else 20.0
        v_val = max(10.0, 25.0 + i * 1.5)
        c_val = max(15.0, 20.0 + i * 4.5)  # Capitalists accumulate constant capital
        cv_ratio = c_val / v_val
        profit_rate = (s_val / (c_val + v_val)) * 100.0
        cv_series.append(cv_ratio)
        profit_series.append(profit_rate)

    # Plot axes
    plot_x = x + 35
    plot_y = y + 42
    plot_w = w - 50
    plot_h = h - 55
    pygame.draw.line(surface, (60, 65, 85), (plot_x, plot_y + plot_h), (plot_x + plot_w, plot_y + plot_h), 1)
    pygame.draw.line(surface, (60, 65, 85), (plot_x, plot_y), (plot_x, plot_y + plot_h), 1)

    n_pts = len(cv_series)
    if n_pts < 2:
        return

    # Draw lines
    max_cv = max(3.0, max(cv_series))
    max_pr = max(50.0, max(profit_series))
    max_sh = 16.0

    cv_coords = []
    pr_coords = []
    sh_coords = []

    for i in range(n_pts):
        px = plot_x + int((i / (n_pts - 1)) * plot_w)
        py_cv = plot_y + plot_h - int((cv_series[i] / max_cv) * plot_h)
        py_pr = plot_y + plot_h - int((profit_series[i] / max_pr) * plot_h)
        py_sh = plot_y + plot_h - int(((shift_series[i] - 8.0) / (max_sh - 8.0)) * plot_h)

        cv_coords.append((px, py_cv))
        pr_coords.append((px, py_pr))
        sh_coords.append((px, py_sh))

    if len(cv_coords) >= 2:
        pygame.draw.lines(surface, COL_C, False, cv_coords, 2)
    if len(pr_coords) >= 2:
        pygame.draw.lines(surface, COL_M, False, pr_coords, 2)
    if len(sh_coords) >= 2:
        pygame.draw.lines(surface, COL_V, False, sh_coords, 1)
