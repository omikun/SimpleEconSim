"""
REGNUM v3_wilderness — Cross-Nation & Provincial Economic Comparison Suite.
Provides a comprehensive 3-tab analytical accounts dashboard with turn delta tracking:
  Tab 1: Macro Accounts & Leaderboard
  Tab 2: Goods Market & Provincial Industrial Economy (Food / Wood / Furniture)
  Tab 3: Sovereign Monetary Accounts (National NEER) + Provincial Branch Banking + Bilateral FX Matrix
"""

import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT
from worldview_map import (
    NATION_COLORS, TEXT, DIM, RED, GREEN, ACCENT, PROVINCE_COLORS
)

# Colors for Table Modal
BG_MODAL = (20, 20, 28)
BORDER_MODAL = (65, 65, 85)
ROW_BG1 = (24, 24, 34)
ROW_BG2 = (28, 28, 40)
SEC_BG = (32, 32, 46)
TAB_ACTIVE_BG = (48, 48, 68)
TAB_INACTIVE_BG = (30, 30, 42)


def fmt_delta(cur, prev, is_curr=False, decimals=2, invert_good=False):
    """Format value and per-turn delta (+/-) with color coding."""
    delta = cur - prev if prev is not None else 0.0
    if is_curr:
        val_str = f"${cur:,.{decimals}f}"
    else:
        val_str = f"{cur:,.{decimals}f}" if isinstance(cur, float) else f"{cur:,}"

    if abs(delta) < 1e-4:
        return val_str, "-", DIM

    sign = "+" if delta > 0 else ""
    if is_curr:
        delta_str = f"({sign}${delta:,.{decimals}f})"
    else:
        delta_str = f"({sign}{delta:,.{decimals}f})" if isinstance(cur, float) else f"({sign}{delta:,})"

    if delta > 0:
        color = RED if invert_good else GREEN
    else:
        color = GREEN if invert_good else RED
    return val_str, delta_str, color


def draw_tab_headers(surface, world, box_x, box_y, box_w, font, font_small, mouse_pos=None):
    """Draw top tabs: 1. Leaderboard, 2. Goods, 3. Forex & Banking."""
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


def compare_tab_hit(pos, box_x, box_y, world=None):
    """Return clicked tab ID (1, 2, 3), Good enum, or None."""
    mx, my = pos
    tab_w = 260
    tab_h = 32
    start_x = box_x + 20
    y = box_y + 48
    for tab_id in (1, 2, 3):
        if start_x <= mx <= start_x + tab_w and y <= my <= y + tab_h:
            return ('tab', tab_id)
        start_x += tab_w + 14

    # Good sub-selectors on Tab 2: y = box_y + 92
    sub_y = box_y + 92
    if sub_y <= my <= sub_y + 28:
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
        pop_prev = sum(get_prev(r.total_population, default=len(r.agents)) for r in tiles)

        gdp_cur = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in tiles)
        gdp_prev = sum(get_prev(r.gdp_log, default=0.0) for r in tiles)

        base_prices = {Goods.food: 1.0, Goods.wood: 1.5, Goods.furniture: 3.0}
        real_gdp_cur = sum(sum(r.production_log[g][-1] * base_prices[g] for g in (Goods.food, Goods.wood, Goods.furniture) if g in r.production_log and r.production_log[g]) for r in tiles)
        real_gdp_prev = sum(sum(get_prev(r.production_log[g], default=0.0) * base_prices[g] for g in (Goods.food, Goods.wood, Goods.furniture) if g in r.production_log) for r in tiles)

        col_cur = (sum(r.cost_of_living for r in tiles) / len(tiles)) if tiles else 0.0
        col_prev = col_cur

        tr = n.treasury()
        tr_cur = tr['total']
        tr_prev = tr_cur

        exports = sum(v[-1] for r in tiles for v in r.export_val.values() if v)
        imports = sum(v[-1] for r in tiles for v in r.import_val.values() if v)
        net_trade = exports - imports

        hungry_cur = sum(sum(r.hungry_log[g][-1] if (g in r.hungry_log and r.hungry_log[g]) else 0 for g in (Goods.food, Goods.wood, Goods.furniture)) for r in tiles)
        hungry_prev = sum(sum(get_prev(r.hungry_log[g], default=0) if g in r.hungry_log else 0 for g in (Goods.food, Goods.wood, Goods.furniture)) for r in tiles)

        def calc_gini(r, idx=-1):
            if not getattr(r, 'gini_log', None):
                return 0.0
            vals = [r.gini_log[g][idx] for g in (Goods.food, Goods.wood, Goods.furniture) if g in r.gini_log and len(r.gini_log[g]) >= abs(idx)]
            return sum(vals) / len(vals) if vals else 0.0

        gini_cur = (sum(calc_gini(r, -1) for r in tiles) / len(tiles)) if tiles else 0.0
        gini_prev = (sum(calc_gini(r, -2) for r in tiles) / len(tiles)) if tiles else 0.0

        protest_cur = (sum(r.protest_energy_log[-1] if r.protest_energy_log else 0.0 for r in tiles) / len(tiles)) if tiles else 0.0
        protest_prev = (sum(get_prev(r.protest_energy_log, default=0.0) for r in tiles) / len(tiles)) if tiles else 0.0

        nation_data.append({
            'nation': n,
            'color': NATION_COLORS.get(n.name, TEXT),
            'tiles': len(tiles),
            'provinces': len(n.provinces),
            'pop_cur': pop_cur, 'pop_prev': pop_prev,
            'gdp_cur': gdp_cur, 'gdp_prev': gdp_prev,
            'real_gdp_cur': real_gdp_cur, 'real_gdp_prev': real_gdp_prev,
            'gdp_pc': (gdp_cur / max(1, pop_cur)),
            'gdp_pc_prev': (gdp_prev / max(1, pop_prev)),
            'col_cur': col_cur, 'col_prev': col_prev,
            'tr_cur': tr_cur, 'tr_prev': tr_prev,
            'tr_food': tr['food'],
            'exports': exports, 'imports': imports, 'net_trade': net_trade,
            'hungry_cur': hungry_cur, 'hungry_prev': hungry_prev,
            'gini_cur': gini_cur, 'gini_prev': gini_prev,
            'protest_cur': protest_cur, 'protest_prev': protest_prev,
            'legitimacy': n.legitimacy,
            'regime': n.regime_type,
            'ruling': getattr(n, 'ruling_faction', '-') or '-',
        })

    label_col_w = 310
    col_w = (box_w - label_col_w - 40) // max(1, len(nations))

    # Header row
    y = start_y
    surface.blit(cell_font.render("METRIC / INDICATOR", True, ACCENT), (box_x + 24, y + 4))
    for i, data in enumerate(nation_data):
        cx = box_x + label_col_w + i * col_w
        n = data['nation']
        col_box = (cx, y, col_w - 10, 30)
        pygame.draw.rect(surface, (34, 34, 46), col_box, border_radius=4)
        pygame.draw.rect(surface, data['color'], col_box, 1, border_radius=4)
        n_label = font.render(f"{n.name} ({n.currency})", True, data['color'])
        surface.blit(n_label, n_label.get_rect(center=(cx + (col_w - 10) // 2, y + 15)))

    y += 38
    table_sections = [
        ("MACROECONOMIC OUTPUT & GROWTH", [
            ("Gross Domestic Product (Nominal GDP)", lambda d: fmt_delta(d['gdp_cur'], d['gdp_prev'], is_curr=True), True),
            ("Real Chained GDP (Base Price Output)", lambda d: fmt_delta(d['real_gdp_cur'], d['real_gdp_prev'], is_curr=True), True),
            ("GDP per Capita ($ / pop)", lambda d: fmt_delta(d['gdp_pc'], d['gdp_pc_prev'], is_curr=True), False),
            ("Cost of Living Index (CPI / CoL)", lambda d: fmt_delta(d['col_cur'], d['col_prev'], decimals=2, invert_good=True), False),
        ]),
        ("DEMOGRAPHICS, WELFARE & EQUALITY", [
            ("Total Living Population", lambda d: fmt_delta(d['pop_cur'], d['pop_prev']), True),
            ("Starving / Severe Hunger Count", lambda d: fmt_delta(d['hungry_cur'], d['hungry_prev'], invert_good=True), False),
            ("Gini Wealth Inequality Index", lambda d: fmt_delta(d['gini_cur'], d['gini_prev'], decimals=3, invert_good=True), False),
            ("Social Protest Energy Level", lambda d: fmt_delta(d['protest_cur'], d['protest_prev'], decimals=2, invert_good=True), False),
        ]),
        ("PUBLIC TREASURY & SOVEREIGNTY", [
            ("Treasury Total Wealth Reserves", lambda d: fmt_delta(d['tr_cur'], d['tr_prev'], is_curr=True), True),
            ("Strategic Food Reserve Stockpile", lambda d: (f"{d['tr_food']} units", "-", DIM), False),
            ("Government Regime Type", lambda d: (f"{d['regime']}", "-", DIM), False),
            ("Regime Legitimacy Rating", lambda d: (f"{d['legitimacy']:.2f}", "-", DIM), True),
        ]),
        ("EXTERNAL SECTOR & INTERNATIONAL TRADE", [
            ("Gross Exports Value", lambda d: (f"${d['exports']:,.1f}", "-", DIM), False),
            ("Gross Imports Value", lambda d: (f"${d['imports']:,.1f}", "-", DIM), False),
            ("Net Trade Balance", lambda d: (f"{'+' if d['net_trade']>=0 else ''}${d['net_trade']:,.1f}", "-", GREEN if d['net_trade']>=0 else RED), True),
        ]),
    ]

    row_h = 20
    for sec_title, rows in table_sections:
        sec_rect = (box_x + 16, y, box_w - 32, 20)
        pygame.draw.rect(surface, SEC_BG, sec_rect)
        surface.blit(section_font.render(sec_title, True, ACCENT), (box_x + 22, y + 2))
        y += 22

        for row_idx, (label, val_fn, is_key) in enumerate(rows):
            row_bg = ROW_BG1 if row_idx % 2 == 0 else ROW_BG2
            pygame.draw.rect(surface, row_bg, (box_x + 16, y, box_w - 32, row_h))

            lbl_color = (255, 255, 255) if is_key else TEXT
            surface.blit(cell_font.render(label, True, lbl_color), (box_x + 24, y + 3))

            for i, data in enumerate(nation_data):
                cx = box_x + label_col_w + i * col_w
                val_str, delta_str, delta_color = val_fn(data)
                val_color = ACCENT if is_key else TEXT
                val_surf = cell_font.render(val_str, True, val_color)
                surface.blit(val_surf, (cx + 8, y + 3))

                if delta_str != "-":
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
        nat_rect = (box_x + 16, y, box_w - 32, 22)
        pygame.draw.rect(surface, SEC_BG, nat_rect)
        nat_c = NATION_COLORS.get(n.name, TEXT)
        surface.blit(section_font.render(f"{n.name} ({n.currency}) — Sovereign Provinces", True, nat_c), (box_x + 24, y + 2))
        y += 24

        for p_idx, prov in enumerate(n.provinces):
            tiles = prov.tiles
            if not tiles:
                continue

            pop = sum(r.total_population[-1] if r.total_population else len(r.agents) for r in tiles)
            col = sum(r.cost_of_living for r in tiles) / len(tiles)

            p_cur = sum(r.recipes[active_good]['price'] for r in tiles) / len(tiles)
            p_prev = sum(get_prev(r.price_log[active_good], default=p_cur) if active_good in r.price_log else p_cur for r in tiles) / len(tiles)

            prod_cur = sum(r.production_log[active_good][-1] if (active_good in r.production_log and r.production_log[active_good]) else 0.0 for r in tiles)
            prod_prev = sum(get_prev(r.production_log[active_good], default=0.0) if active_good in r.production_log else 0.0 for r in tiles)

            inv_cur = sum(r.inventory_log[active_good][-1] if (active_good in r.inventory_log and r.inventory_log[active_good]) else 0.0 for r in tiles)
            inv_prev = sum(get_prev(r.inventory_log[active_good], default=0.0) if active_good in r.inventory_log else 0.0 for r in tiles)

            producers = sum(sum(1 for a in r.agents if not a.is_trader and getattr(a, 'profession', None) == active_good) for r in tiles)
            labor_prod = (prod_cur / max(1, producers)) if producers > 0 else 0.0
            inv_capita = (inv_cur / max(1, pop))
            inv_producer = (inv_cur / max(1, producers)) if producers > 0 else 0.0

            dem_cur = sum(r.demand_log[active_good][-1] if (active_good in r.demand_log and r.demand_log[active_good]) else 0.0 for r in tiles)
            sup_cur = sum(r.supply_log[active_good][-1] if (active_good in r.supply_log and r.supply_log[active_good]) else 0.0 for r in tiles)

            dr_cur = sum(r.demand_ratio_log[active_good][-1] if (active_good in r.demand_ratio_log and r.demand_ratio_log[active_good]) else 1.0 for r in tiles) / len(tiles)
            dr_prev = sum(get_prev(r.demand_ratio_log[active_good], default=1.0) if active_good in r.demand_ratio_log else 1.0 for r in tiles) / len(tiles)

            exp_good = sum(r.export_val[active_good][-1] if (active_good in r.export_val and r.export_val[active_good]) else 0.0 for r in tiles)
            imp_good = sum(r.import_val[active_good][-1] if (active_good in r.import_val and r.import_val[active_good]) else 0.0 for r in tiles)
            net_good = exp_good - imp_good

            row_bg = ROW_BG1 if row_idx % 2 == 0 else ROW_BG2
            row_idx += 1
            pygame.draw.rect(surface, row_bg, (box_x + 16, y, box_w - 32, row_h))

            p_color = PROVINCE_COLORS[p_idx % len(PROVINCE_COLORS)]
            cx = box_x + 24

            surface.blit(cell_font.render(f"• {prov.name}", True, p_color), (cx, y + 3))
            cx += 190

            surface.blit(cell_font.render(f"{col:.2f}", True, DIM), (cx, y + 3))
            cx += 70

            pv, pd, pc = fmt_delta(p_cur, p_prev, is_curr=True, decimals=2, invert_good=True)
            p_surf = cell_font.render(pv, True, TEXT)
            surface.blit(p_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {pd}", True, pc), (cx + p_surf.get_width(), y + 3))
            cx += 110

            prv, prd, prc = fmt_delta(prod_cur, prod_prev, decimals=1)
            pr_surf = cell_font.render(prv, True, TEXT)
            surface.blit(pr_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {prd}", True, prc), (cx + pr_surf.get_width(), y + 3))
            cx += 120

            surface.blit(cell_font.render(f"{labor_prod:.2f}/p", True, TEXT), (cx, y + 3))
            cx += 105

            surface.blit(cell_font.render(f"{inv_capita:.2f}", True, TEXT), (cx, y + 3))
            cx += 115

            surface.blit(cell_font.render(f"{inv_producer:.1f}", True, TEXT), (cx, y + 3))
            cx += 120

            surface.blit(cell_font.render(f"{dem_cur:.0f} / {sup_cur:.0f}", True, TEXT), (cx, y + 3))
            cx += 130

            drv, drd, drc = fmt_delta(dr_cur, dr_prev, decimals=2, invert_good=True)
            dr_surf = cell_font.render(drv, True, (240, 150, 60) if dr_cur > 1.3 else TEXT)
            surface.blit(dr_surf, (cx, y + 3))
            surface.blit(cell_font.render(f" {drd}", True, drc), (cx + dr_surf.get_width(), y + 3))
            cx += 95

            sign = "+" if net_good >= 0 else ""
            st_c = GREEN if net_good >= 0 else RED
            surface.blit(cell_font.render(f"{sign}${net_good:,.1f}", True, st_c), (cx, y + 3))

            y += row_h


# =============================================================================
# TAB 3: EXTERNAL SECTOR, FOREX & BANKING
# =============================================================================

def draw_tab3_fx_banking(surface, world, box_x, start_y, box_w, box_h, font, cell_font, section_font, mouse_pos=None):
    nations = world.get('nations', [])
    y = start_y - 8

    # -------------------------------------------------------------------------
    # SECTION 1: SOVEREIGN NATIONAL ACCOUNTS & PROVINCIAL BRANCH BANKING
    # -------------------------------------------------------------------------
    surface.blit(section_font.render("SOVEREIGN MONETARY ACCOUNTS & PROVINCIAL BRANCH BANKING", True, ACCENT), (box_x + 20, y))
    y += 22

    cols = [
        ("Province / Branch Bank", 210),
        ("Branch Deposits", 150),
        ("Branch Equity Buffer", 160),
        ("Branch Solvency", 130),
        ("Branch FX Pool", 145),
        ("Vault Foreign Reserves", 165),
        ("Provincial Net Trade", 150),
    ]

    header_rect = (box_x + 16, y, box_w - 32, 22)
    pygame.draw.rect(surface, (34, 34, 48), header_rect)
    cx = box_x + 24
    for title, width in cols:
        surface.blit(cell_font.render(title, True, ACCENT), (cx, y + 3))
        cx += width
    y += 24

    row_idx = 0
    row_h = 20

    for n in nations:
        # Calculate Sovereign National Monetary Metrics across all provinces of nation n
        nat_desks = [d for r in n.tiles for d in getattr(r, 'forex_desks', {}).values()]
        if nat_desks:
            rates = [d.mid for d in nat_desks]
            prev_rates = [d.log[-2][1] if len(d.log) >= 2 else d.mid for d in nat_desks]
            gaps = [((d.mid - getattr(d, 'ppp_target', 1.0)) / max(0.01, getattr(d, 'ppp_target', 1.0))) * 100.0 for d in nat_desks]
            nat_neer_cur = (sum(rates) / len(rates)) * 100.0
            nat_neer_prev = (sum(prev_rates) / len(prev_rates)) * 100.0
            nat_gap = sum(gaps) / len(gaps)
        else:
            nat_neer_cur = 100.0
            nat_neer_prev = 100.0
            nat_gap = 0.0

        nv, nd, nc = fmt_delta(nat_neer_cur, nat_neer_prev, decimals=1)
        tot_nat_res = sum(sum(p.bank.foreign_reserves.values()) for p in n.provinces if p.bank)
        tot_nat_dep = sum(p.bank.total_deposits for p in n.provinces if p.bank)
        tot_nat_eq = sum(p.bank.equity for p in n.provinces if p.bank)
        nat_solv = (tot_nat_eq / max(1.0, tot_nat_dep)) * 100.0
        tr = n.treasury()

        nat_rect = (box_x + 16, y, box_w - 32, 21)
        pygame.draw.rect(surface, SEC_BG, nat_rect)
        nat_c = NATION_COLORS.get(n.name, TEXT)

        # Render Sovereign Header Text
        hdr_txt = f"{n.name} ({n.currency}) — Sovereign NEER: {nv} {nd if nd!='-' else ''} | Avg PPP Gap: {'+' if nat_gap>=0 else ''}{nat_gap:.1f}% | FX Reserves: ${tot_nat_res:,.1f} | Treasury: ${tr['total']:,.0f} | National Solvency: {nat_solv:.1f}%"
        surface.blit(cell_font.render(hdr_txt, True, nat_c), (box_x + 24, y + 3))
        y += 22

        for p_idx, prov in enumerate(n.provinces):
            tiles = prov.tiles
            if not tiles:
                continue

            bank = prov.bank
            total_dep_cur = bank.total_deposits if bank else 0.0
            total_eq_cur = bank.equity if bank else 0.0
            fx_pool_cur = bank.fx_pool if bank else 0.0
            res_cur = sum(bank.foreign_reserves.values()) if bank else 0.0

            total_dep_prev = total_dep_cur
            total_eq_prev = total_eq_cur
            fx_pool_prev = fx_pool_cur
            res_prev = res_cur
            solvency_cur = (total_eq_cur / max(1.0, total_dep_cur)) * 100.0

            exp_val = sum(v[-1] for r in tiles for v in r.export_val.values() if v)
            imp_val = sum(v[-1] for r in tiles for v in r.import_val.values() if v)
            net_trade = exp_val - imp_val

            row_bg = ROW_BG1 if row_idx % 2 == 0 else ROW_BG2
            row_idx += 1
            pygame.draw.rect(surface, row_bg, (box_x + 16, y, box_w - 32, row_h))

            p_color = PROVINCE_COLORS[p_idx % len(PROVINCE_COLORS)]
            cx = box_x + 24

            # 1. Province Name
            surface.blit(cell_font.render(f"  • {prov.name}", True, p_color), (cx, y + 2))
            cx += 210

            # 2. Commercial Deposits
            dpv, dpd, dpc = fmt_delta(total_dep_cur, total_dep_prev, is_curr=True, decimals=1)
            dp_surf = cell_font.render(dpv, True, TEXT)
            surface.blit(dp_surf, (cx, y + 2))
            surface.blit(cell_font.render(f" {dpd}", True, dpc), (cx + dp_surf.get_width(), y + 2))
            cx += 150

            # 3. Bank Equity
            eqv, eqd, eqc = fmt_delta(total_eq_cur, total_eq_prev, is_curr=True, decimals=1)
            eq_surf = cell_font.render(eqv, True, GREEN if total_eq_cur > 0 else RED)
            surface.blit(eq_surf, (cx, y + 2))
            surface.blit(cell_font.render(f" {eqd}", True, eqc), (cx + eq_surf.get_width(), y + 2))
            cx += 160

            # 4. Solvency Ratio
            solv_c = GREEN if solvency_cur >= 15.0 else (ACCENT if solvency_cur >= 8.0 else RED)
            surface.blit(cell_font.render(f"{solvency_cur:.1f}%", True, solv_c), (cx, y + 2))
            cx += 130

            # 5. Bank FX Pool
            fpv, fpd, fpc = fmt_delta(fx_pool_cur, fx_pool_prev, is_curr=True, decimals=1)
            fp_surf = cell_font.render(fpv, True, TEXT)
            surface.blit(fp_surf, (cx, y + 2))
            surface.blit(cell_font.render(f" {fpd}", True, fpc), (cx + fp_surf.get_width(), y + 2))
            cx += 145

            # 6. Foreign Reserves
            rv, rd, rc = fmt_delta(res_cur, res_prev, is_curr=True, decimals=1)
            r_surf = cell_font.render(rv, True, TEXT)
            surface.blit(r_surf, (cx, y + 2))
            surface.blit(cell_font.render(f" {rd}", True, rc), (cx + r_surf.get_width(), y + 2))
            cx += 165

            # 7. Net Trade
            nt_sign = "+" if net_trade >= 0 else ""
            nt_c = GREEN if net_trade >= 0 else RED
            surface.blit(cell_font.render(f"{nt_sign}${net_trade:,.1f}", True, nt_c), (cx, y + 2))

            y += row_h

    # -------------------------------------------------------------------------
    # SECTION 2: DEDICATED BILATERAL FOREX MATRIX & CROSS-RATES TABLE
    # -------------------------------------------------------------------------
    y += 14
    surface.blit(section_font.render("BILATERAL FOREIGN EXCHANGE MATRIX & PPP VALUATION BENCHMARKS", True, ACCENT), (box_x + 20, y))
    y += 22

    fx_cols = [
        ("Currency Pair (Base / Quote)", 230),
        ("Exchange Rate (Mid Quote)", 210),
        ("PPP Fair Value", 160),
        ("PPP Valuation Gap", 200),
        ("Foreign Vault Reserves", 200),
        ("Market Spread (Bid / Ask)", 180),
    ]

    fx_head_rect = (box_x + 16, y, box_w - 32, 22)
    pygame.draw.rect(surface, (34, 34, 48), fx_head_rect)
    cx = box_x + 24
    for title, width in fx_cols:
        surface.blit(cell_font.render(title, True, ACCENT), (cx, y + 3))
        cx += width
    y += 24

    pair_rows = []
    for home_n in nations:
        for foreign_n in nations:
            if home_n == foreign_n:
                continue
            target_desk = None
            for r in home_n.tiles:
                for d in getattr(r, 'forex_desks', {}).values():
                    if getattr(d, 'other', None) == foreign_n.currency:
                        target_desk = d
                        break
                if target_desk:
                    break

            if target_desk:
                rc = target_desk.mid
                rp = target_desk.log[-2][1] if len(target_desk.log) >= 2 else rc
                tgt = getattr(target_desk, 'ppp_target', 1.0)
                gap = ((rc - tgt) / max(0.01, tgt)) * 100.0
                spread = getattr(target_desk, 'spread', 0.02)
                bid = rc * (1.0 - spread)
                ask = rc * (1.0 + spread)

                tot_res = sum(prov.bank.foreign_reserves.get(foreign_n.currency, 0.0) for prov in home_n.provinces if prov.bank)

                pair_rows.append({
                    'home_n': home_n,
                    'foreign_n': foreign_n,
                    'pair_label': f"{home_n.currency} / {foreign_n.currency} ({home_n.name} -> {foreign_n.name})",
                    'rc': rc, 'rp': rp,
                    'tgt': tgt,
                    'gap': gap,
                    'bid': bid, 'ask': ask,
                    'res': tot_res,
                })

    for p_idx, pdata in enumerate(pair_rows):
        row_bg = ROW_BG1 if p_idx % 2 == 0 else ROW_BG2
        pygame.draw.rect(surface, row_bg, (box_x + 16, y, box_w - 32, row_h))
        cx = box_x + 24

        home_c = NATION_COLORS.get(pdata['home_n'].name, TEXT)
        surface.blit(cell_font.render(pdata['pair_label'], True, home_c), (cx, y + 2))
        cx += 230

        qv, qd, qc = fmt_delta(pdata['rc'], pdata['rp'], decimals=3)
        q_str = f"1 {pdata['foreign_n'].currency} = {qv} {pdata['home_n'].currency}"
        q_surf = cell_font.render(q_str, True, (255, 255, 255))
        surface.blit(q_surf, (cx, y + 2))
        if qd != "-":
            surface.blit(cell_font.render(f" {qd}", True, qc), (cx + q_surf.get_width(), y + 2))
        cx += 210

        surface.blit(cell_font.render(f"{pdata['tgt']:.3f} {pdata['home_n'].currency}", True, DIM), (cx, y + 2))
        cx += 160

        gap_sign = "+" if pdata['gap'] >= 0 else ""
        gap_desc = "Undervalued (Exports Cheap)" if pdata['gap'] > 5.0 else ("Overvalued (Imports Cheap)" if pdata['gap'] < -5.0 else "Fairly Valued (Parity)")
        gap_c = GREEN if abs(pdata['gap']) < 5.0 else (ACCENT if pdata['gap'] > 0 else RED)
        surface.blit(cell_font.render(f"{gap_sign}{pdata['gap']:.1f}% [{gap_desc}]", True, gap_c), (cx, y + 2))
        cx += 200

        surface.blit(cell_font.render(f"${pdata['res']:,.1f} {pdata['foreign_n'].currency}", True, TEXT), (cx, y + 2))
        cx += 200

        surface.blit(cell_font.render(f"{pdata['bid']:.3f} / {pdata['ask']:.3f}", True, DIM), (cx, y + 2))

        y += row_h


# =============================================================================
# MAIN WINDOW CONTROLLER
# =============================================================================

def draw_nations_comparison(surface, world, font, font_small, mouse_pos=None):
    """Render full-screen 3-tab comparison overlay."""
    if not world.get('compare_open', False):
        return

    title_font = pygame.font.Font(None, 30)
    section_font = pygame.font.Font(None, 23)
    cell_font = pygame.font.Font(None, 19)

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
        draw_tab3_fx_banking(surface, world, box_x, content_y, box_w, box_h, font, cell_font, section_font, mouse_pos=mouse_pos)
