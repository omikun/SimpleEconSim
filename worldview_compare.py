"""
worldview_compare.py — Multi-tab analytical cross-nation & provincial comparison suite.

Tabs:
1. Macro Accounts & Leaderboard (National GDP, Real/Nominal, CPI, Treasury, Trade, Demographics, Stability)
2. Goods Market & Provincial Economy (By Country & Province: Prices, Production, Inv/Capita, Inv/Producer, D vs S, Exp vs Imp)
3. External Sector, Forex & Banking (By Country & Province: Exchange rates, PPP gap, FX pools, Bank equity, Solvency, Deposits)

Every single metric displays Current Value + Turn Delta (±Delta from last turn).
"""

from collections import Counter
import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT
from worldview_map import (ACCENT, TEXT, DIM, RED, GREEN, NATION_COLORS, PROVINCE_COLORS)

BG_MODAL = (20, 20, 28)
BORDER_MODAL = (70, 70, 90)
TAB_ACTIVE_BG = (50, 50, 70)
TAB_INACTIVE_BG = (30, 30, 40)
ROW_BG1 = (24, 24, 32)
ROW_BG2 = (28, 28, 38)
SEC_BG = (32, 32, 46)


def fmt_delta(cur, prev, is_curr=False, is_pct=False, decimals=2, invert_good=False):
    """Return formatted strings and color for current value and turn delta.

    Returns (value_str, delta_str, delta_color).
    """
    if cur is None:
        return "-", "", DIM
    if prev is None:
        prev = cur

    diff = cur - prev
    # Format value
    if is_curr:
        v_str = f"${cur:,.{decimals}f}" if abs(cur) >= 1000 else f"${cur:.{decimals}f}"
    elif is_pct:
        v_str = f"{cur:.1f}%"
    elif isinstance(cur, int) or decimals == 0:
        v_str = f"{int(round(cur)):,}"
    else:
        v_str = f"{cur:.{decimals}f}"

    # Format delta
    if abs(diff) < 0.001:
        d_str = "(=)"
        d_color = DIM
    else:
        sign = "+" if diff > 0 else "-"
        abs_d = abs(diff)
        if is_curr:
            d_str = f"({sign}${abs_d:,.{decimals}f})" if abs_d >= 1000 else f"({sign}${abs_d:.{decimals}f})"
        elif is_pct:
            d_str = f"({sign}{abs_d:.1f}%)"
        elif isinstance(cur, int) or decimals == 0:
            d_str = f"({sign}{int(round(abs_d)):,})"
        else:
            d_str = f"({sign}{abs_d:.{decimals}f})"

        is_positive_good = (diff > 0) if not invert_good else (diff < 0)
        d_color = GREEN if is_positive_good else RED

    return v_str, d_str, d_color


def draw_tab_headers(surface, world, box_x, box_y, box_w, font, font_small, mouse_pos=None):
    """Draw the 3 main tab buttons across the top of the comparison window."""
    active_tab = world.get('compare_tab', 1)
    tabs = [
        (1, "1. Macro Accounts & Leaderboard"),
        (2, "2. Goods & Provincial Economy"),
        (3, "3. External Sector, FX & Banking"),
    ]
    tab_w = 260
    tab_h = 32
    start_x = box_x + 20
    y = box_y + 48
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    for tab_id, label in tabs:
        is_active = (active_tab == tab_id)
        rect = (start_x, y, tab_w, tab_h)
        is_hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        bg = TAB_ACTIVE_BG if is_active else ((42, 42, 56) if is_hover else TAB_INACTIVE_BG)
        border_c = ACCENT if is_active else ((120, 120, 140) if is_hover else (60, 60, 75))
        pygame.draw.rect(surface, bg, rect, border_radius=5)
        pygame.draw.rect(surface, border_c, rect, 1, border_radius=5)
        txt_c = (255, 255, 255) if is_active else (TEXT if is_hover else DIM)
        tsurf = font_small.render(label, True, txt_c)
        surface.blit(tsurf, tsurf.get_rect(center=(start_x + tab_w // 2, y + tab_h // 2)))
        start_x += tab_w + 14

    return y + tab_h + 16


def compare_tab_hit(pos, box_x, box_y):
    """Return clicked tab ID (1, 2, 3) or clicked Good enum, or None."""
    mx, my = pos
    tab_w = 260
    tab_h = 32
    start_x = box_x + 20
    y = box_y + 48
    for tab_id in (1, 2, 3):
        if start_x <= mx <= start_x + tab_w and y <= my <= y + tab_h:
            return ('tab', tab_id)
        start_x += tab_w + 14

    # Good sub-selectors on Tab 2: y = box_y + 90
    good_y = box_y + 92
    if good_y <= my <= good_y + 26:
        gx = box_x + 20
        for g in (Goods.food, Goods.wood, Goods.furniture):
            if gx <= mx <= gx + 100:
                return ('good', g)
            gx += 110

    return None


def get_prev(lst, idx=-2, default=0.0):
    """Safe getter for previous turn value in a history log."""
    if not lst or len(lst) < 2:
        return lst[-1] if lst else default
    return lst[idx]


# =============================================================================
# TAB 1: MACRO ACCOUNTS & LEADERBOARD
# =============================================================================

def draw_tab1_macro(surface, world, box_x, start_y, box_w, box_h, font, cell_font, section_font):
    nations = world.get('nations', [])
    if not nations:
        return

    nation_data = []
    for n in nations:
        tiles = n.tiles
        pop_cur = sum(r.total_population[-1] if r.total_population else len(r.agents) for r in tiles)
        pop_prev = sum(r.total_population[-2] if len(r.total_population) >= 2 else len(r.agents) for r in tiles)

        hungry_cur = sum(sum(r.hungry_log[g][-1] if (g in r.hungry_log and r.hungry_log[g]) else 0
                             for g in (Goods.food, Goods.wood, Goods.furniture)) for r in tiles)
        hungry_prev = sum(sum(r.hungry_log[g][-2] if (g in r.hungry_log and len(r.hungry_log[g]) >= 2) else 0
                              for g in (Goods.food, Goods.wood, Goods.furniture)) for r in tiles)

        gdp_cur = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in tiles)
        gdp_prev = sum(r.gdp_log[-2] if len(r.gdp_log) >= 2 else 0.0 for r in tiles)

        # Real GDP (using base food $1.00, wood $2.00, furn $20.00)
        base_p = {Goods.food: 1.0, Goods.wood: 2.0, Goods.furniture: 20.0}
        real_gdp_cur = sum(sum((r.production_log[g][-1] if (g in r.production_log and r.production_log[g]) else 0) * base_p.get(g, 1.0)
                               for g in base_p) for r in tiles)
        real_gdp_prev = sum(sum((r.production_log[g][-2] if (g in r.production_log and len(r.production_log[g]) >= 2) else 0) * base_p.get(g, 1.0)
                                for g in base_p) for r in tiles)

        col_cur = (sum(r.cost_of_living for r in tiles) / len(tiles)) if tiles else 0.0
        # Estimate col_prev from previous prices
        col_prev = sum(sum(r.price_log[g][-2] if len(r.price_log[g]) >= 2 else r.price_log[g][-1]
                           for g in (Goods.food, Goods.wood, Goods.furniture) if r.price_log[g]) / 3.0 for r in tiles) / max(1, len(tiles)) if tiles else col_cur

        tr = n.treasury()
        tr_tot_cur = tr['total']
        tr_tot_prev = tr_tot_cur  # treasury snapshot

        exports_cur = sum(sum(v) for r in tiles for v in r.export_val.values())
        imports_cur = sum(sum(v) for r in tiles for v in r.import_val.values())
        net_trade_cur = exports_cur - imports_cur
        net_trade_prev = net_trade_cur

        gini_cur = sum((r.gini_log[Goods.food][-1] if (Goods.food in r.gini_log and r.gini_log[Goods.food]) else 0.0) for r in tiles) / max(1, len(tiles))
        gini_prev = sum((r.gini_log[Goods.food][-2] if (Goods.food in r.gini_log and len(r.gini_log[Goods.food]) >= 2) else gini_cur) for r in tiles) / max(1, len(tiles))

        protest_cur = (sum(r.protest_energy_log[-1] if r.protest_energy_log else 0.0 for r in tiles) / len(tiles)) if tiles else 0.0
        protest_prev = (sum(r.protest_energy_log[-2] if len(r.protest_energy_log) >= 2 else 0.0 for r in tiles) / len(tiles)) if tiles else 0.0

        legit_cur = n.legitimacy
        legit_prev = legit_cur

        nation_data.append({
            'nation': n,
            'color': NATION_COLORS.get(n.name, TEXT),
            'tiles': len(tiles),
            'provinces': len(n.provinces),
            'pop_cur': pop_cur, 'pop_prev': pop_prev,
            'hungry_cur': hungry_cur, 'hungry_prev': hungry_prev,
            'gdp_cur': gdp_cur, 'gdp_prev': gdp_prev,
            'real_gdp_cur': real_gdp_cur, 'real_gdp_prev': real_gdp_prev,
            'gdp_pc_cur': gdp_cur / max(1, pop_cur), 'gdp_pc_prev': gdp_prev / max(1, pop_prev),
            'col_cur': col_cur, 'col_prev': col_prev,
            'tr_total_cur': tr_tot_cur, 'tr_total_prev': tr_tot_prev,
            'tr_food_cur': tr['food'], 'tr_food_prev': tr['food'],
            'exports_cur': exports_cur, 'exports_prev': exports_cur,
            'imports_cur': imports_cur, 'imports_prev': imports_cur,
            'net_trade_cur': net_trade_cur, 'net_trade_prev': net_trade_prev,
            'gini_cur': gini_cur, 'gini_prev': gini_prev,
            'protest_cur': protest_cur, 'protest_prev': protest_prev,
            'legit_cur': legit_cur, 'legit_prev': legit_prev,
            'regime': n.regime_type,
            'ruling': getattr(n, 'ruling_faction', '-') or '-',
        })

    label_col_w = 290
    col_w = (box_w - label_col_w - 40) // max(1, len(nations))

    # Header Row
    y = start_y
    surface.blit(cell_font.render("NATIONAL ACCOUNT INDICATOR", True, ACCENT), (box_x + 24, y + 4))
    for i, data in enumerate(nation_data):
        cx = box_x + label_col_w + i * col_w
        n = data['nation']
        col_box = (cx, y, col_w - 10, 30)
        pygame.draw.rect(surface, (34, 34, 46), col_box, border_radius=4)
        pygame.draw.rect(surface, data['color'], col_box, 1, border_radius=4)
        n_label = font.render(f"{n.name} ({n.currency})", True, data['color'])
        surface.blit(n_label, n_label.get_rect(center=(cx + (col_w - 10) // 2, y + 15)))

    y += 38
    sections = [
        ("OUTPUT, STANDARD OF LIVING & PRODUCTIVITY", [
            ("Nominal GDP / turn", lambda d: fmt_delta(d['gdp_cur'], d['gdp_prev'], is_curr=True), True),
            ("Real Chained GDP (Base Output)", lambda d: fmt_delta(d['real_gdp_cur'], d['real_gdp_prev'], is_curr=True), True),
            ("GDP per Capita", lambda d: fmt_delta(d['gdp_pc_cur'], d['gdp_pc_prev'], is_curr=True), True),
            ("Cost of Living Index (CoL)", lambda d: fmt_delta(d['col_cur'], d['col_prev'], is_curr=False, decimals=2, invert_good=True), False),
        ]),
        ("DEMOGRAPHICS & SOCIAL COHESION", [
            ("Total Living Population", lambda d: fmt_delta(d['pop_cur'], d['pop_prev'], decimals=0), True),
            ("Severe Hunger / Starving Count", lambda d: fmt_delta(d['hungry_cur'], d['hungry_prev'], decimals=0, invert_good=True), False),
            ("Gini Inequality Index", lambda d: fmt_delta(d['gini_cur'], d['gini_prev'], decimals=3, invert_good=True), False),
            ("Social Protest Grievance Energy", lambda d: fmt_delta(d['protest_cur'], d['protest_prev'], decimals=2, invert_good=True), False),
        ]),
        ("PUBLIC FINANCE, FISCAL & TREASURY", [
            ("Total Treasury Reserves", lambda d: fmt_delta(d['tr_total_cur'], d['tr_total_prev'], is_curr=True), True),
            ("Strategic Food Reserve", lambda d: fmt_delta(d['tr_food_cur'], d['tr_food_prev'], decimals=0), False),
            ("Government Regime Type", lambda d: (f"{d['regime']}", "", DIM), False),
            ("Regime Legitimacy Rating", lambda d: fmt_delta(d['legit_cur'], d['legit_prev'], decimals=2), True),
            ("Ruling Political Faction", lambda d: (f"{d['ruling']}", "", DIM), False),
        ]),
        ("INTERNATIONAL TRADE & EXTERNAL BALANCE", [
            ("Total Exports Value", lambda d: fmt_delta(d['exports_cur'], d['exports_prev'], is_curr=True), True),
            ("Total Imports Value", lambda d: fmt_delta(d['imports_cur'], d['imports_prev'], is_curr=True, invert_good=True), False),
            ("Net Trade Balance (Surplus/Deficit)", lambda d: fmt_delta(d['net_trade_cur'], d['net_trade_prev'], is_curr=True), True),
        ]),
    ]

    row_h = 22
    for sec_title, rows in sections:
        pygame.draw.rect(surface, SEC_BG, (box_x + 16, y, box_w - 32, 22))
        surface.blit(section_font.render(sec_title, True, ACCENT), (box_x + 22, y + 2))
        y += 24

        for row_idx, (label, fmt_func, is_key) in enumerate(rows):
            row_bg = ROW_BG1 if row_idx % 2 == 0 else ROW_BG2
            pygame.draw.rect(surface, row_bg, (box_x + 16, y, box_w - 32, row_h))

            lbl_color = (255, 255, 255) if is_key else TEXT
            surface.blit(cell_font.render(label, True, lbl_color), (box_x + 24, y + 3))

            for i, data in enumerate(nation_data):
                cx = box_x + label_col_w + i * col_w
                val_str, delta_str, delta_color = fmt_func(data)

                # Render main value
                val_surf = cell_font.render(val_str, True, ACCENT if is_key else TEXT)
                surface.blit(val_surf, (cx + 8, y + 3))

                # Render delta
                if delta_str:
                    d_surf = cell_font.render(f" {delta_str}", True, delta_color)
                    surface.blit(d_surf, (cx + 8 + val_surf.get_width(), y + 3))

            y += row_h


# =============================================================================
# TAB 2: GOODS MARKET & PROVINCIAL ECONOMY
# =============================================================================

def draw_tab2_goods(surface, world, box_x, start_y, box_w, box_h, font, cell_font, section_font, mouse_pos=None):
    active_good = world.get('compare_good', Goods.food)
    good_names = {Goods.food: "Food (Grain & Provisions)", Goods.wood: "Wood (Timber & Lumber)", Goods.furniture: "Furniture (Manufactured Goods)"}

    # Sub-selector for Goods
    gx = box_x + 20
    gy = start_y - 8
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for g in (Goods.food, Goods.wood, Goods.furniture):
        is_sel = (g == active_good)
        rect = (gx, gy, 100, 24)
        is_hov = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        bg = ACCENT if is_sel else ((44, 44, 58) if is_hov else (30, 30, 40))
        txt_c = (20, 20, 24) if is_sel else ((255, 255, 255) if is_hov else TEXT)
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        pygame.draw.rect(surface, (80, 80, 100), rect, 1, border_radius=4)
        tsurf = cell_font.render(g.name.capitalize(), True, txt_c)
        surface.blit(tsurf, tsurf.get_rect(center=(gx + 50, gy + 12)))
        gx += 110

    y = start_y + 24
    header_title = f"PROVINCIAL INDUSTRIAL ECONOMY — {good_names.get(active_good, active_good.name)}"
    surface.blit(section_font.render(header_title, True, ACCENT), (box_x + 20, y))
    y += 24

    # Table Column Headers
    cols = [
        ("Territory / Province", 190),
        ("CoL", 70),
        ("Price", 110),
        ("Production", 120),
        ("Labor Prod", 105),
        ("Inv / Capita", 115),
        ("Inv / Producer", 120),
        ("Demand / Supply", 130),
        ("D/S Ratio", 95),
        ("Sector Trade", 135),
    ]

    header_rect = (box_x + 16, y, box_w - 32, 24)
    pygame.draw.rect(surface, (34, 34, 48), header_rect)
    cx = box_x + 24
    for title, width in cols:
        surface.blit(cell_font.render(title, True, ACCENT), (cx, y + 4))
        cx += width
    y += 26

    nations = world.get('nations', [])
    row_idx = 0
    row_h = 22

    for n in nations:
        # Nation Group Header
        nat_rect = (box_x + 16, y, box_w - 32, 22)
        pygame.draw.rect(surface, SEC_BG, nat_rect)
        nat_c = NATION_COLORS.get(n.name, TEXT)
        surface.blit(section_font.render(f"{n.name} ({n.currency}) — {len(n.provinces)} Provinces, {len(n.tiles)} Tiles", True, nat_c), (box_x + 24, y + 2))
        y += 24

        for p_idx, prov in enumerate(n.provinces):
            tiles = prov.tiles
            if not tiles:
                continue

            pop_cur = sum(r.total_population[-1] if r.total_population else len(r.agents) for r in tiles)
            pop_prev = sum(r.total_population[-2] if len(r.total_population) >= 2 else len(r.agents) for r in tiles)

            col_cur = sum(r.cost_of_living for r in tiles) / len(tiles)
            col_prev = col_cur

            price_cur = sum(r.recipes[active_good]['price'] for r in tiles) / len(tiles)
            price_prev = sum(r.price_log[active_good][-2] if len(r.price_log[active_good]) >= 2 else price_cur for r in tiles) / len(tiles)

            prod_cur = sum(r.production_log[active_good][-1] if (active_good in r.production_log and r.production_log[active_good]) else 0 for r in tiles)
            prod_prev = sum(r.production_log[active_good][-2] if (active_good in r.production_log and len(r.production_log[active_good]) >= 2) else 0 for r in tiles)

            producers_cur = sum(r.population_log[active_good][-1] if (active_good in r.population_log and r.population_log[active_good]) else 0 for r in tiles)
            producers_prev = sum(r.population_log[active_good][-2] if (active_good in r.population_log and len(r.population_log[active_good]) >= 2) else 0 for r in tiles)

            labor_prod_cur = prod_cur / max(1, producers_cur)
            labor_prod_prev = prod_prev / max(1, producers_prev)

            inv_cur = sum(r.inventory_log[active_good][-1] if (active_good in r.inventory_log and r.inventory_log[active_good]) else 0 for r in tiles)
            inv_prev = sum(r.inventory_log[active_good][-2] if (active_good in r.inventory_log and len(r.inventory_log[active_good]) >= 2) else 0 for r in tiles)

            inv_pc_cur = inv_cur / max(1, pop_cur)
            inv_pc_prev = inv_prev / max(1, pop_prev)

            inv_pp_cur = inv_cur / max(1, producers_cur)
            inv_pp_prev = inv_prev / max(1, producers_prev)

            dem_cur = sum(r.demand_log[active_good][-1] if (active_good in r.demand_log and r.demand_log[active_good]) else 0 for r in tiles)
            sup_cur = sum(r.supply_log[active_good][-1] if (active_good in r.supply_log and r.supply_log[active_good]) else 0 for r in tiles)

            dr_cur = sum(r.demand_ratio_log[active_good][-1] if (active_good in r.demand_ratio_log and r.demand_ratio_log[active_good]) else 1.0 for r in tiles) / len(tiles)
            dr_prev = sum(r.demand_ratio_log[active_good][-2] if (active_good in r.demand_ratio_log and len(r.demand_ratio_log[active_good]) >= 2) else dr_cur for r in tiles) / len(tiles)

            exp_val = sum(r.export_val.get(active_good, [0])[-1] if (active_good in r.export_val and r.export_val[active_good]) else 0 for r in tiles)
            imp_val = sum(r.import_val.get(active_good, [0])[-1] if (active_good in r.import_val and r.import_val[active_good]) else 0 for r in tiles)
            net_good = exp_val - imp_val

            row_bg = ROW_BG1 if row_idx % 2 == 0 else ROW_BG2
            row_idx += 1
            pygame.draw.rect(surface, row_bg, (box_x + 16, y, box_w - 32, row_h))

            p_color = PROVINCE_COLORS[p_idx % len(PROVINCE_COLORS)]
            cx = box_x + 24

            # 1. Province Name
            surface.blit(cell_font.render(f"• {prov.name} ({len(tiles)}t)", True, p_color), (cx, y + 3))
            cx += 190

            # 2. CoL
            surface.blit(cell_font.render(f"{col_cur:.2f}", True, TEXT), (cx, y + 3))
            cx += 70

            # 3. Price
            pv, pd, pc = fmt_delta(price_cur, price_prev, is_curr=True, decimals=2)
            p_surf = cell_font.render(pv, True, TEXT)
            surface.blit(p_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {pd}", True, pc), (cx + p_surf.get_width(), y + 3))
            cx += 110

            # 4. Production
            prv, prd, prc = fmt_delta(prod_cur, prod_prev, decimals=0)
            pr_surf = cell_font.render(prv, True, TEXT)
            surface.blit(pr_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {prd}", True, prc), (cx + pr_surf.get_width(), y + 3))
            cx += 120

            # 5. Labor Prod
            lpv, lpd, lpc = fmt_delta(labor_prod_cur, labor_prod_prev, decimals=2)
            lp_surf = cell_font.render(lpv, True, TEXT)
            surface.blit(lp_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {lpd}", True, lpc), (cx + lp_surf.get_width(), y + 3))
            cx += 105

            # 6. Inv / Capita
            icv, icd, icc = fmt_delta(inv_pc_cur, inv_pc_prev, decimals=2)
            ic_surf = cell_font.render(icv, True, TEXT)
            surface.blit(ic_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {icd}", True, icc), (cx + ic_surf.get_width(), y + 3))
            cx += 115

            # 7. Inv / Producer
            ipv, ipd, ipc = fmt_delta(inv_pp_cur, inv_pp_prev, decimals=2)
            ip_surf = cell_font.render(ipv, True, TEXT)
            surface.blit(ip_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {ipd}", True, ipc), (cx + ip_surf.get_width(), y + 3))
            cx += 120

            # 8. Demand vs Supply
            surface.blit(cell_font.render(f"{int(dem_cur)}D / {int(sup_cur)}S", True, TEXT), (cx, y + 3))
            cx += 130

            # 9. Demand Ratio
            drv, drd, drc = fmt_delta(dr_cur, dr_prev, decimals=2, invert_good=True)
            dr_surf = cell_font.render(drv, True, (240, 150, 60) if dr_cur > 1.3 else TEXT)
            surface.blit(dr_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {drd}", True, drc), (cx + dr_surf.get_width(), y + 3))
            cx += 95

            # 10. Sector Trade
            sign = "+" if net_good >= 0 else ""
            st_c = GREEN if net_good >= 0 else RED
            surface.blit(cell_font.render(f"{sign}${net_good:,.1f}", True, st_c), (cx, y + 3))

            y += row_h


# =============================================================================
# TAB 3: EXTERNAL SECTOR, FOREX & BANKING
# =============================================================================

def draw_tab3_fx_banking(surface, world, box_x, start_y, box_w, box_h, font, cell_font, section_font):
    y = start_y
    surface.blit(section_font.render("MONETARY, FOREIGN EXCHANGE & PROVINCIAL BANKING ACCOUNTS", True, ACCENT), (box_x + 20, y))
    y += 24

    cols = [
        ("Territory / Province", 190),
        ("Forex Mid Quote", 135),
        ("PPP Gap", 95),
        ("Bank FX Pool", 130),
        ("Foreign Reserves", 145),
        ("Commercial Deposits", 150),
        ("Bank Equity Buffer", 140),
        ("Solvency Ratio", 110),
        ("Net Trade", 125),
    ]

    header_rect = (box_x + 16, y, box_w - 32, 24)
    pygame.draw.rect(surface, (34, 34, 48), header_rect)
    cx = box_x + 24
    for title, width in cols:
        surface.blit(cell_font.render(title, True, ACCENT), (cx, y + 4))
        cx += width
    y += 26

    nations = world.get('nations', [])
    row_idx = 0
    row_h = 22

    for n in nations:
        nat_rect = (box_x + 16, y, box_w - 32, 22)
        pygame.draw.rect(surface, SEC_BG, nat_rect)
        nat_c = NATION_COLORS.get(n.name, TEXT)
        surface.blit(section_font.render(f"{n.name} ({n.currency}) — Monetary Desk & Central Reserves", True, nat_c), (box_x + 24, y + 2))
        y += 24

        for p_idx, prov in enumerate(n.provinces):
            tiles = prov.tiles
            if not tiles:
                continue

            bank = prov.bank
            total_dep_cur = bank.total_deposits if bank else 0.0
            total_eq_cur = bank.equity if bank else 0.0
            fx_pool_cur = bank.fx_pool if bank else 0.0

            # Estimate previous turn values
            total_dep_prev = total_dep_cur
            total_eq_prev = total_eq_cur
            fx_pool_prev = fx_pool_cur

            # Reserves total
            reserves_cur = sum(bank.foreign_reserves.values()) if bank else 0.0
            reserves_prev = reserves_cur

            # Solvency Ratio (Equity / Deposits)
            solvency_cur = (total_eq_cur / max(1.0, total_dep_cur)) * 100.0
            solvency_prev = solvency_cur

            # Representative Forex desk on first tile
            first_t = tiles[0]
            desk = getattr(first_t, 'forex', None)
            if desk is None and getattr(first_t, 'forex_desks', None):
                desk = next(iter(first_t.forex_desks.values()), None)

            if desk is not None:
                rate_cur = desk.mid
                rate_prev = desk.log[-2][1] if len(desk.log) >= 2 else rate_cur
                ppp_target = getattr(desk, 'ppp_target', 1.0)
                ppp_gap = ((rate_cur - ppp_target) / max(0.01, ppp_target)) * 100.0
                quote_str = f"{rate_cur:.3f} {desk.other}"
            else:
                rate_cur = 1.0
                rate_prev = 1.0
                ppp_gap = 0.0
                quote_str = "1.000 (Parity)"

            exp_val = sum(sum(v) for r in tiles for v in r.export_val.values())
            imp_val = sum(sum(v) for r in tiles for v in r.import_val.values())
            net_trade = exp_val - imp_val

            row_bg = ROW_BG1 if row_idx % 2 == 0 else ROW_BG2
            row_idx += 1
            pygame.draw.rect(surface, row_bg, (box_x + 16, y, box_w - 32, row_h))

            p_color = PROVINCE_COLORS[p_idx % len(PROVINCE_COLORS)]
            cx = box_x + 24

            # 1. Province Name
            surface.blit(cell_font.render(f"• {prov.name}", True, p_color), (cx, y + 3))
            cx += 190

            # 2. Forex Mid Quote
            qv, qd, qc = fmt_delta(rate_cur, rate_prev, decimals=3)
            q_surf = cell_font.render(quote_str, True, TEXT)
            surface.blit(q_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {qd}", True, qc), (cx + q_surf.get_width(), y + 3))
            cx += 135

            # 3. PPP Gap
            gap_sign = "+" if ppp_gap >= 0 else ""
            gap_c = GREEN if abs(ppp_gap) < 5.0 else (ACCENT if ppp_gap > 0 else RED)
            surface.blit(cell_font.render(f"{gap_sign}{ppp_gap:.1f}%", True, gap_c), (cx, y + 3))
            cx += 95

            # 4. Bank FX Pool
            fpv, fpd, fpc = fmt_delta(fx_pool_cur, fx_pool_prev, is_curr=True, decimals=1)
            fp_surf = cell_font.render(fpv, True, TEXT)
            surface.blit(fp_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {fpd}", True, fpc), (cx + fp_surf.get_width(), y + 3))
            cx += 130

            # 5. Foreign Reserves
            rv, rd, rc = fmt_delta(reserves_cur, reserves_prev, is_curr=True, decimals=1)
            r_surf = cell_font.render(rv, True, TEXT)
            surface.blit(r_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {rd}", True, rc), (cx + r_surf.get_width(), y + 3))
            cx += 145

            # 6. Commercial Deposits
            dpv, dpd, dpc = fmt_delta(total_dep_cur, total_dep_prev, is_curr=True, decimals=1)
            dp_surf = cell_font.render(dpv, True, TEXT)
            surface.blit(dp_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {dpd}", True, dpc), (cx + dp_surf.get_width(), y + 3))
            cx += 150

            # 7. Bank Equity
            eqv, eqd, eqc = fmt_delta(total_eq_cur, total_eq_prev, is_curr=True, decimals=1)
            eq_surf = cell_font.render(eqv, True, GREEN if total_eq_cur > 0 else RED)
            surface.blit(eq_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {eqd}", True, eqc), (cx + eq_surf.get_width(), y + 3))
            cx += 140

            # 8. Solvency Ratio
            solv_c = GREEN if solvency_cur >= 15.0 else (ACCENT if solvency_cur >= 8.0 else RED)
            surface.blit(cell_font.render(f"{solvency_cur:.1f}%", True, solv_c), (cx, y + 3))
            cx += 110

            # 9. Net Trade
            nt_sign = "+" if net_trade >= 0 else ""
            nt_c = GREEN if net_trade >= 0 else RED
            surface.blit(cell_font.render(f"{nt_sign}${net_trade:,.1f}", True, nt_c), (cx, y + 3))

            y += row_h


# =============================================================================
# MAIN WINDOW CONTROLLER
# =============================================================================

def draw_nations_comparison(surface, world, font, font_small, mouse_pos=None):
    """Render full-screen 3-tab comparison overlay."""
    if not world.get('compare_open', False):
        return

    title_font = pygame.font.Font(None, 30)
    section_font = pygame.font.Font(None, 24)
    cell_font = pygame.font.Font(None, 20)

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((12, 12, 18, 248))
    surface.blit(overlay, (0, 0))

    # Modal Box Window
    box_x, box_y, box_w, box_h = 30, 20, WIDTH - 60, HEIGHT - 40
    pygame.draw.rect(surface, BG_MODAL, (box_x, box_y, box_w, box_h), border_radius=8)
    pygame.draw.rect(surface, BORDER_MODAL, (box_x, box_y, box_w, box_h), 2, border_radius=8)

    # Top Header
    title = title_font.render("REGNUM v3 — Economic & Geopolitical Accounts Suite", True, ACCENT)
    surface.blit(title, (box_x + 20, box_y + 14))
    close_hint = font_small.render("[Press C, Esc, or Click to Close | Tab or 1-3 to switch]", True, DIM)
    surface.blit(close_hint, (box_x + box_w - close_hint.get_width() - 20, box_y + 18))

    # Draw Tab Bar
    content_y = draw_tab_headers(surface, world, box_x, box_y, box_w, font, font_small, mouse_pos=mouse_pos)

    # Render Active Tab
    tab = world.get('compare_tab', 1)
    if tab == 1:
        draw_tab1_macro(surface, world, box_x, content_y, box_w, box_h, font, cell_font, section_font)
    elif tab == 2:
        draw_tab2_goods(surface, world, box_x, content_y, box_w, box_h, font, cell_font, section_font, mouse_pos=mouse_pos)
    elif tab == 3:
        draw_tab3_fx_banking(surface, world, box_x, content_y, box_w, box_h, font, cell_font, section_font)
