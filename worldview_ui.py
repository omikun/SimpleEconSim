"""
UI components: top stats bar, right panel, regime readout, ticker, zoom HUD, and 2-page paginated help overlay.
"""

import os
from collections import Counter
import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_charts import (PANEL_LEFT, draw_chart_grid, draw_chart_large,
                              tile_charts, EXP_C, IMP_C)
from worldview_map import (HEX_EDGE, ACCENT, TEXT, DIM, RED, GREEN, UNREST_COLORS,
                           PROVINCE_COLORS, NATION_COLORS, BADGE_ORANGE, BADGE_RED,
                           BADGE_TRA, BADGE_GINI)
from worldview_compare import draw_nations_comparison, compare_tab_hit
from diplomacy import get_diplomacy, TreatyType

PANEL_BG = (40, 40, 48)

# Cached fonts and overlay surfaces to eliminate frame-rate allocations and high idle CPU
_FONT_CACHE = {}
_FONT_PATH = None


def _find_best_font_path():
    global _FONT_PATH
    if _FONT_PATH is not None:
        return _FONT_PATH
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:\\Windows\\Fonts\\seguiemj.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                f = pygame.font.Font(p, 16)
                f.render("🌾 Test", True, (255, 255, 255))
                _FONT_PATH = p
                return _FONT_PATH
            except Exception:
                continue
    _FONT_PATH = ""
    return _FONT_PATH


def get_font(size):
    """Return cached Pygame font instance with full Unicode/Emoji glyph support and calibrated point scale."""
    f = _FONT_CACHE.get(size)
    if f is None:
        p = _find_best_font_path()
        if p:
            try:
                # Scale TrueType point size to match default Pygame bitmapped layout metrics
                scaled_size = max(9, int(size * 0.65))
                f = pygame.font.Font(p, scaled_size)
            except Exception:
                f = pygame.font.Font(None, size)
        else:
            f = pygame.font.Font(None, size)
        _FONT_CACHE[size] = f
    return f


_OVERLAY_SURFACE = None


def get_modal_overlay(width=WIDTH, height=HEIGHT, color=(12, 12, 18, 248)):
    """Return cached transparent modal overlay surface."""
    global _OVERLAY_SURFACE
    if _OVERLAY_SURFACE is None:
        _OVERLAY_SURFACE = pygame.Surface((width, height), pygame.SRCALPHA)
        _OVERLAY_SURFACE.fill(color)
    return _OVERLAY_SURFACE

# Zoom HUD button rectangles: (x, y, w, h)
ZOOM_BTN_IN = (MAP_RIGHT - 110, TOP_BAR_H + 12, 30, 26)
ZOOM_BTN_OUT = (MAP_RIGHT - 75, TOP_BAR_H + 12, 30, 26)
ZOOM_BTN_RESET = (MAP_RIGHT - 40, TOP_BAR_H + 12, 32, 26)

# Compare Nations button in top-right command dock
COMPARE_BTN = (1228, 5, 160, 20)

# Help Page Tab Rectangles
HELP_TAB1_RECT = (32, 56, 310, 28)
HELP_TAB2_RECT = (352, 56, 350, 28)


def draw_zoom_hud(surface, font_small, mouse_pos=None):
    """Draw on-screen zoom control buttons in the top-right corner of the map area."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    buttons = [
        (ZOOM_BTN_IN, "+", "Zoom In"),
        (ZOOM_BTN_OUT, "-", "Zoom Out"),
        (ZOOM_BTN_RESET, "1:1", "Reset Zoom"),
    ]
    for rect, label, _tip in buttons:
        is_hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        bg_color = (60, 60, 75) if is_hover else (38, 38, 48)
        border_color = ACCENT if is_hover else (80, 80, 95)
        pygame.draw.rect(surface, bg_color, rect, border_radius=4)
        pygame.draw.rect(surface, border_color, rect, 1, border_radius=4)
        tsurf = font_small.render(label, True, (255, 255, 255) if is_hover else TEXT)
        surface.blit(tsurf, tsurf.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))


# Right-hand panel top tabs (Charts vs Policies)
CHARTS_TAB_RECT = (PANEL_LEFT, 152 + TOP_BAR_H, (WIDTH - PANEL_LEFT - 14) // 2, 22)
POLICIES_TAB_RECT = (PANEL_LEFT + (WIDTH - PANEL_LEFT - 14) // 2 + 4, 152 + TOP_BAR_H, (WIDTH - PANEL_LEFT - 14) // 2, 22)


def panel_tab_hit(pos):
    """Return 'charts' or 'policies' if the right panel tab header was clicked."""
    mx, my = pos
    cx, cy, cw, ch = CHARTS_TAB_RECT
    if cx <= mx <= cx + cw and cy <= my <= cy + ch:
        return 'charts'
    px, py, pw, ph = POLICIES_TAB_RECT
    if px <= mx <= px + pw and py <= my <= py + ph:
        return 'policies'
    return None


def zoom_hud_hit(pos):
    """Return 'in', 'out', 'reset', or None if a zoom button was clicked."""
    mx, my = pos
    if ZOOM_BTN_IN[0] <= mx <= ZOOM_BTN_IN[0] + ZOOM_BTN_IN[2] and ZOOM_BTN_IN[1] <= my <= ZOOM_BTN_IN[1] + ZOOM_BTN_IN[3]:
        return 'in'
    if ZOOM_BTN_OUT[0] <= mx <= ZOOM_BTN_OUT[0] + ZOOM_BTN_OUT[2] and ZOOM_BTN_OUT[1] <= my <= ZOOM_BTN_OUT[1] + ZOOM_BTN_OUT[3]:
        return 'out'
    if ZOOM_BTN_RESET[0] <= mx <= ZOOM_BTN_RESET[0] + ZOOM_BTN_RESET[2] and ZOOM_BTN_RESET[1] <= my <= ZOOM_BTN_RESET[1] + ZOOM_BTN_RESET[3]:
        return 'reset'
    return None


def compare_btn_hit(pos):
    """Return True if the top-bar Compare Nations button was clicked."""
    mx, my = pos
    return COMPARE_BTN[0] <= mx <= COMPARE_BTN[0] + COMPARE_BTN[2] and COMPARE_BTN[1] <= my <= COMPARE_BTN[1] + COMPARE_BTN[3]


def help_page_hit(pos):
    """Return 1 or 2 if a help page tab was clicked, else None."""
    mx, my = pos
    if HELP_TAB1_RECT[0] <= mx <= HELP_TAB1_RECT[0] + HELP_TAB1_RECT[2] and HELP_TAB1_RECT[1] <= my <= HELP_TAB1_RECT[1] + HELP_TAB1_RECT[3]:
        return 1
    if HELP_TAB2_RECT[0] <= mx <= HELP_TAB2_RECT[0] + HELP_TAB2_RECT[2] and HELP_TAB2_RECT[1] <= my <= HELP_TAB2_RECT[1] + HELP_TAB2_RECT[3]:
        return 2
    return None


def selected_nation(world):
    """Return the currently selected or hovered nation, falling back to world nations."""
    pinned = world.get('selected_region') or world.get('hover_region')
    if pinned is not None and getattr(pinned, 'owner_nation', None) is not None:
        return pinned.owner_nation
    if world.get('selected_nation') is not None:
        return world['selected_nation']
    return world['nations'][0] if world.get('nations') else None


def draw_top_bar_dropdown_card(surface, font, font_small, title, badge_text, badge_color, lines, anchor_rect):
    """Render a sleek floating dropdown card for hovered top-bar stat breakdowns."""
    padding_x = 14
    padding_y = 10
    line_h = 17
    
    # Calculate required card width based on text
    title_w = font.size(title)[0] + font_small.size(badge_text)[0] + 36
    max_row_w = 0
    for label, val, _ in lines:
        if val:
            row_w = font_small.size(label)[0] + font_small.size(val)[0] + 28
        else:
            row_w = font_small.size(label)[0] + 8
        if row_w > max_row_w:
            max_row_w = row_w
            
    card_w = max(310, max(title_w, max_row_w) + padding_x * 2)
    card_h = padding_y * 2 + 22 + len(lines) * line_h + 6

    # Position dropdown directly below the hovered tab, clamped cleanly to screen
    card_x = max(8, min(WIDTH - card_w - 8, anchor_rect[0] - 6))
    card_y = TOP_BAR_H + 4
    
    # Alpha card background
    card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
    pygame.draw.rect(card_surf, (20, 22, 32, 248), (0, 0, card_w, card_h), border_radius=6)
    pygame.draw.rect(card_surf, (75, 85, 115), (0, 0, card_w, card_h), 1, border_radius=6)
    
    # Header: Title & Pill Badge
    t_surf = font.render(title, True, (255, 255, 255))
    card_surf.blit(t_surf, (padding_x, padding_y))
    
    if badge_text:
        b_surf = font_small.render(badge_text, True, badge_color)
        b_rect = pygame.Rect(card_w - padding_x - b_surf.get_width() - 8, padding_y - 1, b_surf.get_width() + 8, 17)
        pygame.draw.rect(card_surf, (38, 44, 58, 220), b_rect, border_radius=4)
        pygame.draw.rect(card_surf, badge_color, b_rect, 1, border_radius=4)
        card_surf.blit(b_surf, (b_rect.x + 4, b_rect.y + 2))
        
    # Divider line
    div_y = padding_y + 20
    pygame.draw.line(card_surf, (50, 56, 76), (padding_x, div_y), (card_w - padding_x, div_y), 1)
    
    # Rows
    cur_y = div_y + 6
    for label, val, val_col in lines:
        if not val:
            # Section header
            h_surf = font_small.render(label, True, (135, 145, 170))
            card_surf.blit(h_surf, (padding_x, cur_y))
        else:
            # Label
            lbl_surf = font_small.render(label, True, (185, 190, 205))
            card_surf.blit(lbl_surf, (padding_x, cur_y))
            # Value
            val_surf = font_small.render(val, True, val_col)
            val_x = card_w - padding_x - val_surf.get_width()
            card_surf.blit(val_surf, (val_x, cur_y))
        cur_y += line_h

    # Shadow & Blit
    shadow_surf = pygame.Surface((card_w + 8, card_h + 8), pygame.SRCALPHA)
    pygame.draw.rect(shadow_surf, (8, 8, 14, 140), (4, 4, card_w, card_h), border_radius=8)
    surface.blit(shadow_surf, (card_x - 2, card_y - 2))
    surface.blit(card_surf, (card_x, card_y))


def _get_stat_breakdown(world, n, tiles, key):
    """Generate detailed breakdown metrics and factor rows for the hovered top bar stat."""
    turn = world.get('turn', 0)
    agents = [a for r in tiles for a in getattr(r, 'agents', []) if getattr(a, 'alive', True)]
    adults = [a for a in agents if not a.is_corporation and not a.is_government and a.age(turn) > 20]
    unemp_adults = sum(1 for a in adults if a.employer is None and not a.is_trader)
    unemp_rate = unemp_adults / max(1, len(adults))
    
    hungry_now = sum(1 for a in agents if not a.is_corporation and not a.is_government and getattr(a, 'hungry_steps', 0) > 0)
    mem_hunger = sum(a.mem_avg('mem_hunger', 0.0) for a in agents if not a.is_corporation and not a.is_government)
    trauma = sum(a.mem_avg('mem_casualties', 0.0) + a.mem_avg('mem_promises', 0.0) for a in agents if not a.is_corporation and not a.is_government)
    
    # Calculate Gini across regions
    avg_gini = 0.0
    for r in tiles:
        for g in (Goods.food, Goods.wood, Goods.furniture):
            vals = sorted(a.cash for a in r.agents if getattr(a, 'output', None) == g)
            if len(vals) > 5:
                n_v = len(vals)
                s_v = sum(vals)
                if s_v > 0:
                    wsum = sum((i + 1) * v for i, v in enumerate(vals))
                    avg_gini = max(avg_gini, (2 * wsum) / (n_v * s_v) - (n_v + 1) / n_v)

    tax_rate = (sum(r.gov.tax_rate for r in tiles) / len(tiles)) if tiles else 0.25
    tariff_rate = (sum(r.gov.import_tariff_rate for r in tiles) / len(tiles)) if tiles else 0.05
    total_garrison = sum(len(getattr(r, 'army', [])) for r in tiles)
    
    # Identify top aggrieved faction
    all_factions = {}
    for r in tiles:
        if hasattr(r, 'factions') and r.factions:
            for fname, f in r.factions.factions.items():
                if fname not in all_factions:
                    all_factions[fname] = {'gv': 0.0, 'kind': f.kind, 'demand': f.demands[0].name if f.demands else 'None'}
                all_factions[fname]['gv'] += f.total_grievance()
    top_f = max(all_factions.items(), key=lambda x: x[1]['gv']) if all_factions else ("None", {'kind': '', 'demand': 'None', 'gv': 0.0})

    if key == 'protest':
        protest_cur = (sum(r.protest_energy_log[-1] if r.protest_energy_log else 0.0 for r in tiles) / len(tiles)) if tiles else 0.0
        protest_prev = (sum(r.protest_energy_log[-2] if len(r.protest_energy_log) >= 2 else (r.protest_energy_log[-1] if r.protest_energy_log else 0.0) for r in tiles) / len(tiles)) if tiles else 0.0
        d_p = protest_cur - protest_prev
        
        stage = "Calm"
        st_color = GREEN
        if protest_cur >= 9.5:
            stage, st_color = "Takeover", RED
        elif protest_cur >= 8.0:
            stage, st_color = "Compromise", RED
        elif protest_cur >= 6.5:
            stage, st_color = "Mob/Riot", RED
        elif protest_cur >= 4.0:
            stage, st_color = "Protest", BADGE_ORANGE
        elif protest_cur >= 2.0:
            stage, st_color = "Unrest", BADGE_ORANGE
            
        lines = [
            ("Average Protest Energy", f"{protest_cur:.2f} / 10.00", st_color),
            ("Turn Delta", f"{'+' if d_p > 0 else ''}{d_p:.2f} per turn", RED if d_p > 0 else (GREEN if d_p < 0 else TEXT)),
            ("--- Grievance Drivers ---", "", DIM),
            ("• Unemployment Rate", f"{unemp_rate:.1%} ({unemp_adults}/{len(adults)} adults)", RED if unemp_rate > 0.3 else TEXT),
            ("• Wealth Disparity (Gini)", f"{avg_gini:.2f} index", BADGE_ORANGE if avg_gini > 0.4 else TEXT),
            ("• Hunger & Malnutrition", f"{hungry_now} hungry ({mem_hunger / 120.0:.2f} mem)", RED if hungry_now > 0 else GREEN),
            ("• Income Tax Burden", f"{tax_rate:.1%} effective rate", TEXT),
            ("• Repression & Casualties", f"{trauma / 60.0:.2f} trauma score", RED if trauma > 0 else TEXT),
            ("--- Suppression & Politics ---", "", DIM),
            ("• Stationed Garrison", f"{total_garrison} soldiers (-{total_garrison * 0.05:.2f} / turn)", GREEN if total_garrison > 0 else TEXT),
            ("• Top Discontent Faction", f"{top_f[0]} ({top_f[1]['demand']})", ACCENT),
        ]
        return "Civil Unrest & Protest Breakdown", f"Stage: {stage}", st_color, lines

    elif key == 'pop':
        pop_cur = sum(r.total_population[-1] if r.total_population else len(r.agents) for r in tiles)
        pop_prev = sum(r.total_population[-2] if len(r.total_population) >= 2 else (r.total_population[-1] if r.total_population else len(r.agents)) for r in tiles)
        d_pop = pop_cur - pop_prev
        tot_traders = sum(1 for a in agents if getattr(a, 'is_trader', False))
        tot_homesteaders = sum(1 for a in agents if getattr(a, 'is_homesteader', False))
        employed_workers = len(adults) - unemp_adults
        
        lines = [
            ("Total Population", f"{pop_cur:,} living citizens", TEXT),
            ("Turn Growth Delta", f"{'+' if d_pop > 0 else ''}{d_pop} net", GREEN if d_pop > 0 else (RED if d_pop < 0 else TEXT)),
            ("Working Adults (>20 yrs)", f"{len(adults):,} ({len(adults) / max(1, pop_cur):.1%})", TEXT),
            ("Youth & Children (<=20 yrs)", f"{max(0, pop_cur - len(adults)):,}", TEXT),
            ("Employed Corporate Workers", f"{employed_workers:,} laborers", GREEN),
            ("Unemployed Adults", f"{unemp_adults:,} looking for work", RED if unemp_adults > 0 else TEXT),
            ("Independent Traders", f"{tot_traders:,} active traders", BADGE_TRA),
            ("Homesteaders & Settlers", f"{tot_homesteaders:,} pioneers", BADGE_ORANGE),
            ("Undernourished Citizens", f"{hungry_now:,} hungry", RED if hungry_now > 0 else GREEN),
        ]
        return "Demographics & Population Breakdown", f"{pop_cur:,} Pops", ACCENT, lines

    elif key == 'treasury':
        tr = n.treasury()
        tr_cur = tr['total']
        tr_prev = n._treasury_hist[-2][1] if hasattr(n, '_treasury_hist') and len(n._treasury_hist) >= 2 else tr_cur
        d_tr = tr_cur - tr_prev
        tot_debt = sum(getattr(r.gov, 'debt', 0.0) for r in tiles)
        
        lines = [
            ("Liquid Treasury Vault", f"${tr_cur:,.0f} {n.currency}", GREEN if tr_cur > 0 else RED),
            ("Emergency Food Granary", f"{tr['food']} food units", TEXT),
            ("Turn Balance Delta", f"{'+' if d_tr > 0 else ''}${d_tr:,.0f} / turn", GREEN if d_tr > 0 else (RED if d_tr < 0 else TEXT)),
            ("Average Tax Revenue", f"{tax_rate:.1%} income tax rate", TEXT),
            ("Import Tariff Inflow", f"{tariff_rate:.1%} customs rate", TEXT),
            ("Active Soldier Payroll", f"{total_garrison} standing troops", TEXT),
            ("Outstanding Public Debt", f"${tot_debt:,.0f}", RED if tot_debt > 0 else GREEN),
        ]
        return "National Treasury & Fiscal Reserves", f"${tr_cur:,.0f}", GREEN if tr_cur > 0 else RED, lines

    elif key == 'col':
        col_cur = (sum(r.cost_of_living for r in tiles) / len(tiles)) if tiles else 0.0
        avg_food = sum(r.recipes[Goods.food]['price'] for r in tiles if Goods.food in r.recipes) / max(1, len(tiles))
        avg_wood = sum(r.recipes[Goods.wood]['price'] for r in tiles if Goods.wood in r.recipes) / max(1, len(tiles))
        avg_furn = sum(r.recipes[Goods.furniture]['price'] for r in tiles if Goods.furniture in r.recipes) / max(1, len(tiles))
        
        wages = [a.wage for a in agents if hasattr(a, 'wage') and a.wage > 0]
        avg_wage = (sum(wages) / len(wages)) if wages else 1.0
        
        lines = [
            ("Average Cost of Living", f"Index {col_cur:.2f}", TEXT),
            ("Food Market Basket Price", f"${avg_food:.2f} / food unit", BADGE_ORANGE if avg_food > 2.0 else TEXT),
            ("Timber / Wood Price", f"${avg_wood:.2f} / timber unit", TEXT),
            ("Manufactured Furniture", f"${avg_furn:.2f} / furniture unit", TEXT),
            ("Average Employee Wage", f"${avg_wage:.2f} / turn", GREEN),
            ("Wage-to-Food Ratio", f"{avg_wage / max(0.01, avg_food):.1f}x food purchasing power", GREEN if avg_wage >= avg_food else RED),
        ]
        return "Cost of Living & Market Basket", f"CoL {col_cur:.2f}", ACCENT, lines

    elif key == 'gdp':
        gdp_cur = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in tiles)
        gdp_prev = sum(r.gdp_log[-2] if len(r.gdp_log) >= 2 else (r.gdp_log[-1] if r.gdp_log else 0.0) for r in tiles)
        d_gdp = gdp_cur - gdp_prev
        pop_cur = sum(r.total_population[-1] if r.total_population else len(r.agents) for r in tiles)
        
        lines = [
            ("Gross Domestic Product", f"${gdp_cur:,.0f} total value", ACCENT),
            ("Turn Growth Delta", f"{'+' if d_gdp > 0 else ''}${d_gdp:,.0f} / turn", GREEN if d_gdp > 0 else (RED if d_gdp < 0 else TEXT)),
            ("GDP per Capita", f"${gdp_cur / max(1, pop_cur):,.1f} / citizen", TEXT),
            ("Territorial Hexes", f"{len(tiles)} productive regions", TEXT),
            ("National Provinces", f"{len(n.provinces)} administrative provinces", TEXT),
        ]
        return "Gross Domestic Product & Production", f"${gdp_cur:,.0f}", ACCENT, lines

    elif key == 'ex':
        exports_cur = sum(sum(v[-1] for v in r.export_val.values() if v) for r in tiles)
        exports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.export_val.values() if v) for r in tiles)
        d_ex = exports_cur - exports_prev
        food_ex = sum(r.export_val.get(Goods.food, [0])[-1] if r.export_val.get(Goods.food) else 0 for r in tiles)
        wood_ex = sum(r.export_val.get(Goods.wood, [0])[-1] if r.export_val.get(Goods.wood) else 0 for r in tiles)
        furn_ex = sum(r.export_val.get(Goods.furniture, [0])[-1] if r.export_val.get(Goods.furniture) else 0 for r in tiles)
        
        lines = [
            ("Total Export Value", f"${exports_cur:,.0f} shipped abroad", EXP_C),
            ("Turn Export Delta", f"{'+' if d_ex > 0 else ''}${d_ex:,.0f} / turn", GREEN if d_ex > 0 else (RED if d_ex < 0 else TEXT)),
            ("• Agricultural Food Exports", f"${food_ex:,.0f}", TEXT),
            ("• Timber & Forestry Exports", f"${wood_ex:,.0f}", TEXT),
            ("• Manufactured Goods Exports", f"${furn_ex:,.0f}", TEXT),
        ]
        return "Foreign Exports Breakdown", f"${exports_cur:,.0f}", EXP_C, lines

    elif key == 'im':
        imports_cur = sum(sum(v[-1] for v in r.import_val.values() if v) for r in tiles)
        imports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.import_val.values() if v) for r in tiles)
        d_im = imports_cur - imports_prev
        food_im = sum(r.import_val.get(Goods.food, [0])[-1] if r.import_val.get(Goods.food) else 0 for r in tiles)
        wood_im = sum(r.import_val.get(Goods.wood, [0])[-1] if r.import_val.get(Goods.wood) else 0 for r in tiles)
        furn_im = sum(r.import_val.get(Goods.furniture, [0])[-1] if r.import_val.get(Goods.furniture) else 0 for r in tiles)
        
        lines = [
            ("Total Import Value", f"${imports_cur:,.0f} imported", IMP_C),
            ("Turn Import Delta", f"{'+' if d_im > 0 else ''}${d_im:,.0f} / turn", TEXT),
            ("• Food Goods Imported", f"${food_im:,.0f}", TEXT),
            ("• Timber Goods Imported", f"${wood_im:,.0f}", TEXT),
            ("• Manufactured Imports", f"${furn_im:,.0f}", TEXT),
            ("• Tariff Rate Applied", f"{tariff_rate:.1%}", TEXT),
        ]
        return "Foreign Imports Breakdown", f"${imports_cur:,.0f}", IMP_C, lines

    elif key == 'net':
        exports_cur = sum(sum(v[-1] for v in r.export_val.values() if v) for r in tiles)
        imports_cur = sum(sum(v[-1] for v in r.import_val.values() if v) for r in tiles)
        net_cur = exports_cur - imports_cur
        exports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.export_val.values() if v) for r in tiles)
        imports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.import_val.values() if v) for r in tiles)
        net_prev = exports_prev - imports_prev
        d_net = net_cur - net_prev
        active_tr = get_diplomacy().get_active_treaties(n.name)
        trade_pacts = len([tr for tr in active_tr if tr.treaty_type == TreatyType.TRADE_PACT.value or tr.treaty_type == TreatyType.TRADE_PACT])
        
        lines = [
            ("Trade Balance Position", "Trade Surplus" if net_cur >= 0 else "Trade Deficit", GREEN if net_cur >= 0 else RED),
            ("Net Trade Balance", f"{'+' if net_cur >= 0 else ''}${net_cur:,.0f}", GREEN if net_cur >= 0 else RED),
            ("Turn Balance Delta", f"{'+' if d_net > 0 else ''}${d_net:,.0f} / turn", GREEN if d_net > 0 else (RED if d_net < 0 else TEXT)),
            ("Total Exports", f"${exports_cur:,.0f}", EXP_C),
            ("Total Imports", f"${imports_cur:,.0f}", IMP_C),
            ("Bilateral Trade Pacts", f"{trade_pacts} signed treaties", ACCENT),
        ]
        return "Net Trade Balance & Commerce", f"{'+' if net_cur >= 0 else ''}${net_cur:,.0f}", GREEN if net_cur >= 0 else RED, lines

    elif key == 'header':
        ruling = getattr(n, 'ruling_faction', None)
        legit = getattr(n, 'legitimacy', 1.0)
        legit_desc = "Stable" if legit > 0.6 else ("Fragile" if legit > 0.25 else "Crisis")
        legit_col = GREEN if legit > 0.6 else (BADGE_ORANGE if legit > 0.25 else RED)
        treaties_cnt = len(get_diplomacy().get_active_treaties(n.name))
        
        lines = [
            ("Sovereign Nation", f"{n.name} (Currency: {n.currency})", ACCENT),
            ("Government Regime", f"{n.regime_type.title()}", TEXT),
            ("Legitimacy Score", f"{legit:.2f} / 1.00 ({legit_desc})", legit_col),
            ("Ruling Faction", f"{ruling or 'Popular Front'}", ACCENT),
            ("Organized Provinces", f"{len(n.provinces)} provinces", TEXT),
            ("Member City Hexes", f"{len(tiles)} claimed tiles", TEXT),
            ("Active Foreign Treaties", f"{treaties_cnt} diplomatic pacts", ACCENT),
        ]
        return "Sovereignty & Governance Breakdown", f"{n.regime_type.title()}", ACCENT, lines

    return "", "", TEXT, []


def draw_top_bar(surface, world, font_small, mouse_pos=None):
    """Civ-style top strip: stats for the currently selected nation with turn deltas + interactive hover breakdowns."""
    n = selected_nation(world)
    pygame.draw.rect(surface, (34, 34, 42), (0, 0, WIDTH, TOP_BAR_H))
    pygame.draw.line(surface, HEX_EDGE, (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 2)
    pygame.draw.line(surface, (55, 55, 70), (MAP_RIGHT, 0), (MAP_RIGHT, TOP_BAR_H), 1)
    font = font_small
    font_bold = get_font(13)
    
    hovered_dropdown = None

    if n is None:
        head = font.render("REGNUM v3 — 9x9 Hex World", True, ACCENT)
        surface.blit(head, (8, 14))
    else:
        n_col = NATION_COLORS.get(n.name, ACCENT)
        tiles = n.tiles
        pop_cur = sum(r.total_population[-1] if r.total_population else len(r.agents) for r in tiles)
        pop_prev = sum(r.total_population[-2] if len(r.total_population) >= 2 else (r.total_population[-1] if r.total_population else len(r.agents)) for r in tiles)
        d_pop = pop_cur - pop_prev

        tr = n.treasury()
        tr_cur = tr['total']
        if not hasattr(n, '_treasury_hist'):
            n._treasury_hist = []
        if not n._treasury_hist or n._treasury_hist[-1][0] != world['turn']:
            n._treasury_hist.append((world['turn'], tr_cur))
            if len(n._treasury_hist) > 50:
                n._treasury_hist.pop(0)
        tr_prev = n._treasury_hist[-2][1] if len(n._treasury_hist) >= 2 else tr_cur
        d_tr = tr_cur - tr_prev

        col_cur = (sum(r.cost_of_living for r in tiles) / len(tiles)) if tiles else 0.0
        gdp_cur = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in tiles)
        gdp_prev = sum(r.gdp_log[-2] if len(r.gdp_log) >= 2 else (r.gdp_log[-1] if r.gdp_log else 0.0) for r in tiles)
        d_gdp = gdp_cur - gdp_prev

        exports_cur = sum(sum(v[-1] for v in r.export_val.values() if v) for r in tiles)
        imports_cur = sum(sum(v[-1] for v in r.import_val.values() if v) for r in tiles)
        net_cur = exports_cur - imports_cur

        exports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.export_val.values() if v) for r in tiles)
        imports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.import_val.values() if v) for r in tiles)
        net_prev = exports_prev - imports_prev
        d_net = net_cur - net_prev

        # Protest calculation
        protest_cur = (sum(r.protest_energy_log[-1] if r.protest_energy_log else 0.0 for r in tiles) / len(tiles)) if tiles else 0.0
        protest_prev = (sum(r.protest_energy_log[-2] if len(r.protest_energy_log) >= 2 else (r.protest_energy_log[-1] if r.protest_energy_log else 0.0) for r in tiles) / len(tiles)) if tiles else 0.0
        d_protest = protest_cur - protest_prev

        from ui_icons import get_icon
        crown_icon = get_icon('crown', 14)

        ruling = getattr(n, 'ruling_faction', None)
        ruler = f"  ruling {ruling}" if ruling else ""
        head_text = f"{n.name} ({n.currency})  {n.regime_type}  legit {n.legitimacy:.2f}{ruler}  provinces {len(n.provinces)}  tiles {len(tiles)}"
        head = font.render(head_text, True, n_col)
        
        # Check hover on header
        header_rect = pygame.Rect(6, 4, 20 + head.get_width() + 8, 20)
        mx, my = mouse_pos if mouse_pos else (-1, -1)
        if header_rect.collidepoint(mx, my):
            pygame.draw.rect(surface, (50, 50, 68), header_rect, border_radius=3)
            hovered_dropdown = ('header', header_rect)
            
        surface.blit(crown_icon, (8, 7))
        surface.blit(head, (26, 6))

        # Format deltas with color
        pop_str = f"Pop {pop_cur:,}" + (f" ({'+' if d_pop > 0 else ''}{d_pop})" if d_pop != 0 else "")
        pop_color = GREEN if d_pop > 0 else (RED if d_pop < 0 else TEXT)

        tr_str = f"Treasury ${tr_cur:,.0f}" + (f" ({'+' if d_tr > 0 else ''}${d_tr:,.0f})" if abs(d_tr) >= 1.0 else "") + f" ({tr['food']} food)"
        tr_color = GREEN if d_tr > 0.5 else (RED if d_tr < -0.5 else TEXT)

        gdp_str = f"GDP ${gdp_cur:,.0f}" + (f" ({'+' if d_gdp > 0 else ''}${d_gdp:,.0f})" if abs(d_gdp) >= 1.0 else "")
        gdp_color = GREEN if d_gdp > 0.5 else (RED if d_gdp < -0.5 else TEXT)

        net_str = f"Net {'+' if net_cur >= 0 else ''}{net_cur:,.0f}" + (f" ({'+' if d_net > 0 else ''}{d_net:,.0f})" if abs(d_net) >= 1.0 else "")
        net_color = GREEN if net_cur >= 0 else RED

        protest_str = f"Protest {protest_cur:.2f}" + (f" ({'+' if d_protest > 0 else ''}{d_protest:.2f})" if abs(d_protest) >= 0.01 else "")
        protest_color = RED if protest_cur >= 4.0 else (BADGE_ORANGE if protest_cur >= 2.0 else (GREEN if d_protest < 0 else TEXT))

        stats = [
            (pop_str, pop_color, 'pop'),
            (tr_str, tr_color, 'treasury'),
            (f"CoL {col_cur:.2f}", TEXT, 'col'),
            (gdp_str, gdp_color, 'gdp'),
            (f"Ex ${exports_cur:,.0f}", EXP_C, 'ex'),
            (f"Im ${imports_cur:,.0f}", IMP_C, 'im'),
            (net_str, net_color, 'net'),
            (protest_str, protest_color, 'protest'),
        ]
        
        x = 8
        for text, color, key in stats:
            icon_surf = get_icon(key, size=13)
            label = font.render(text, True, color)
            total_item_w = 13 + 4 + label.get_width()
            item_rect = pygame.Rect(x - 3, 27, total_item_w + 6, 20)
            
            # Hover highlight
            if item_rect.collidepoint(mx, my):
                pygame.draw.rect(surface, (50, 52, 70), item_rect, border_radius=3)
                hovered_dropdown = (key, item_rect)
                
            surface.blit(icon_surf, (x, 30))
            surface.blit(label, (x + 17, 30))
            x += total_item_w + 14

    world['_hovered_topbar_dropdown'] = hovered_dropdown

    # Top-Right Command Buttons (Help, Compare, Diplomacy, Military)
    from worldview_actions import draw_top_bar_action_buttons
    draw_top_bar_action_buttons(surface, world, font_small, mouse_pos=mouse_pos)


def draw_top_bar_dropdown(surface, world, font_small, mouse_pos=None):
    """Render floating stat breakdown dropdown card on top of all UI elements."""
    is_modal_open = world.get('help_open') or world.get('compare_open') or world.get('actions_open')
    if is_modal_open:
        return

    n = selected_nation(world)
    if n is None:
        return

    hovered_dropdown = world.get('_hovered_topbar_dropdown')
    if hovered_dropdown:
        key, rect = hovered_dropdown
        title, badge_txt, badge_col, lines = _get_stat_breakdown(world, n, n.tiles, key)
        if lines:
            font_title = get_font(18)
            font_body = get_font(15)
            draw_top_bar_dropdown_card(surface, font_title, font_body, title, badge_txt, badge_col, lines, rect)


def draw_regime_readout(surface, region, font_small, y):
    """Protest / unrest / top faction / owner nation readout."""
    if getattr(region, 'owner_nation', None) is None:
        hs = sum(1 for a in region.agents if getattr(a, 'is_homesteader', False))
        line = font_small.render(f"unclaimed wilderness  (homesteaders: {hs})", True, DIM)
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


def draw_panel(surface, world, font, font_small, mouse_pos=None):
    """Right-hand panel: header, play state, audit, per-tile charts, wilderness card."""
    d = TOP_BAR_H
    panel_w = WIDTH - PANEL_LEFT - 6
    panel_h = HEIGHT - 20 - d - TICKER_H
    pygame.draw.rect(surface, PANEL_BG,
                     (PANEL_LEFT - 10, 10 + d, panel_w + 4, panel_h))

    title = font.render("REGNUM — Hex World", True, ACCENT)
    surface.blit(title, (PANEL_LEFT, 20 + d))

    t_ = world['turn']
    turn_line = font_small.render(f"Turn: {t_}  win={world['window']}t  zoom={world['cam']['zoom']:.2f}x", True, TEXT)
    surface.blit(turn_line, (PANEL_LEFT, 50 + d))

    cursors = world.get('currency_totals', {})
    y = 76 + d
    for c, total in cursors.items():
        line = font_small.render(f"{c}: ${total:,.0f}", True, TEXT)
        surface.blit(line, (PANEL_LEFT, y))
        y += 20

    if world.get('playing'):
        pn = font_small.render("[ PLAYING ]  Space=pause", True, GREEN)
    else:
        pn = font_small.render("[ PAUSED ]  N=step  Space=play", True, DIM)
    surface.blit(pn, (PANEL_LEFT, 130 + d))

    # Right Panel Header Tabs: [ 📊 Charts ] vs [ ⚖️ Policies ]
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    active_tab = world.get('panel_tab', 'charts')

    c_hit = panel_tab_hit((mx, my))
    c_sel = (active_tab == 'charts')
    c_hov = (c_hit == 'charts')
    pygame.draw.rect(surface, (55, 75, 110) if c_sel else ((40, 48, 65) if c_hov else (28, 30, 40)), CHARTS_TAB_RECT, border_radius=4)
    pygame.draw.rect(surface, ACCENT if c_sel else (HEX_EDGE if c_hov else (45, 52, 70)), CHARTS_TAB_RECT, 1, border_radius=4)
    c_txt = font_small.render("Charts", True, (255, 255, 255) if c_sel else (TEXT if c_hov else DIM))
    surface.blit(c_txt, c_txt.get_rect(center=(CHARTS_TAB_RECT[0] + CHARTS_TAB_RECT[2] // 2, CHARTS_TAB_RECT[1] + CHARTS_TAB_RECT[3] // 2)))

    p_sel = (active_tab == 'policies')
    p_hov = (c_hit == 'policies')
    pygame.draw.rect(surface, (55, 75, 110) if p_sel else ((40, 48, 65) if p_hov else (28, 30, 40)), POLICIES_TAB_RECT, border_radius=4)
    pygame.draw.rect(surface, ACCENT if p_sel else (HEX_EDGE if p_hov else (45, 52, 70)), POLICIES_TAB_RECT, 1, border_radius=4)
    from ui_icons import get_icon, draw_icon_badge
    scale_icon = get_icon('policies', 14)
    surface.blit(scale_icon, (POLICIES_TAB_RECT[0] + 6, POLICIES_TAB_RECT[1] + 5))
    p_txt = font_small.render("Policies", True, (255, 255, 255) if p_sel else (TEXT if p_hov else DIM))
    surface.blit(p_txt, (POLICIES_TAB_RECT[0] + 24, POLICIES_TAB_RECT[1] + 4))

    region = world.get('selected_region') or world.get('hover_region')
    chart_top = 178 + d
    chart_bottom = HEIGHT - TICKER_H - 96

    if active_tab == 'policies':
        from worldview_policies import draw_policies_panel
        draw_policies_panel(surface, world, region, font, font_small, mouse_pos=mouse_pos)
        # Audit footer line
        audit_y = HEIGHT - TICKER_H - 28
        if world.get('violations'):
            v1 = font.render("AUDIT VIOLATION", True, RED)
            surface.blit(v1, (PANEL_LEFT, audit_y - 4))
            vline = font_small.render(
                "; ".join(f"T{v[0]} {v[1]} {v[2]:+.2f}" for v in world['violations']),
                True, RED)
            surface.blit(vline, (PANEL_LEFT, audit_y + 18))
        else:
            ok = font.render("Conserved: 0 LEAK / 0 SHIFT", True, GREEN)
            surface.blit(ok, (PANEL_LEFT, audit_y))
        return

    if world.get('scope', 'tile') == 'nation':
        n = selected_nation(world)
        if n is not None:
            owner_pop = sum(r.total_population[-1] if r.total_population
                            else len(r.agents) for r in n.tiles)
            tr = n.treasury()
            col = (sum(r.cost_of_living for r in n.tiles) / max(1, len(n.tiles)))
            gdp = sum(r.gdp_log[-1] if r.gdp_log else 0.0 for r in n.tiles)
            lines = [
                (f"{n.name} ({n.currency})  {n.regime_type}", ACCENT),
                (f"legit {n.legitimacy:.2f}  provinces {len(n.provinces)}  tiles {len(n.tiles)}", TEXT),
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
            draw_regime_readout(surface, region if region is not None else n.tiles[0],
                                font_small, chart_bottom + 24)
        return

    # Check if region is Wilderness
    if region is not None and getattr(region, 'owner_nation', None) is None:
        head = font.render(f"{region.name} — Frontier Wilderness", True, ACCENT)
        surface.blit(head, (PANEL_LEFT, chart_top - 6))
        col_line = font_small.render(
            f"Climate: {region.climate.capitalize()}  |  CoL: {region.cost_of_living:.2f}", True, DIM)
        surface.blit(col_line, (PANEL_LEFT, chart_top + 20))

        hs_agents = [a for a in region.agents if getattr(a, 'is_homesteader', False)]
        wild_native = getattr(region, 'wilderness_pop', 0)
        total_settlers = len(hs_agents) + wild_native
        origin_counts = Counter(getattr(a, 'origin_nation', 'Unknown') for a in hs_agents)

        yy = chart_top + 48
        surface.blit(font_small.render("FRONTIER DEMOGRAPHICS", True, ACCENT), (PANEL_LEFT, yy))
        yy += 20
        surface.blit(font_small.render(f"Homesteaders: {len(hs_agents)}", True, TEXT), (PANEL_LEFT, yy))
        yy += 18
        surface.blit(font_small.render(f"Native Wilderness Pop: {wild_native}", True, TEXT), (PANEL_LEFT, yy))
        yy += 18
        surface.blit(font_small.render(f"Total Frontier Pop: {total_settlers}", True, (255, 255, 255)), (PANEL_LEFT, yy))
        yy += 24

        surface.blit(font_small.render("SETTLER HOMELANDS (50% Claim Rule)", True, ACCENT), (PANEL_LEFT, yy))
        yy += 20
        if origin_counts:
            for nation_name, cnt in origin_counts.most_common():
                pct = (cnt / total_settlers) * 100 if total_settlers > 0 else 0
                claimable = " (CLAIM MAJORITY!)" if cnt / float(total_settlers) > 0.50 else ""
                color = GREEN if claimable else TEXT
                surface.blit(font_small.render(f"• {nation_name}: {cnt} ({pct:.1f}%){claimable}", True, color), (PANEL_LEFT, yy))
                yy += 18
        else:
            surface.blit(font_small.render("No homesteaders present yet", True, DIM), (PANEL_LEFT, yy))
            yy += 18

        yy += 10
        surface.blit(font_small.render("NATURAL PRODUCTIVITY", True, ACCENT), (PANEL_LEFT, yy))
        yy += 20
        food_bonus = region.terrain.get(Goods.food, 1.0)
        wood_bonus = region.terrain.get(Goods.wood, 1.0)
        surface.blit(font_small.render(f"Farmland Fertility: {food_bonus:.2f}x {'(High)' if food_bonus > 1.3 else ''}", True, TEXT), (PANEL_LEFT, yy))
        yy += 18
        surface.blit(font_small.render(f"Forest Density: {wood_bonus:.2f}x {'(Dense)' if wood_bonus > 1.3 else ''}", True, TEXT), (PANEL_LEFT, yy))
        yy += 24

        surface.blit(font_small.render("NEIGHBORING CLAIMED HOSTS", True, ACCENT), (PANEL_LEFT, yy))
        yy += 20
        claimed_neighbors = [n for n in region.neighbors.values() if getattr(n, 'owner_nation', None) is not None]
        if claimed_neighbors:
            for nb in claimed_neighbors[:4]:
                prov_name = nb.province.name if getattr(nb, 'province', None) else nb.owner_nation.name
                surface.blit(font_small.render(f"• {nb.name} ({nb.owner_nation.name} - {prov_name})", True, DIM), (PANEL_LEFT, yy))
                yy += 18
        else:
            surface.blit(font_small.render("Deep frontier wilderness", True, DIM), (PANEL_LEFT, yy))
            yy += 18

        draw_regime_readout(surface, region, font_small, chart_bottom + 24)
        return

    # Claimed Tile 10-Chart Dashboard
    if region is not None:
        prov_s = ""
        prov_color = TEXT
        if getattr(region, 'province', None) is not None:
            prov = region.province
            nation = getattr(region, 'owner_nation', None)
            if nation and getattr(nation, 'provinces', None):
                try:
                    p_idx = nation.provinces.index(prov)
                    prov_color = PROVINCE_COLORS[p_idx % len(PROVINCE_COLORS)]
                except ValueError:
                    prov_color = ACCENT
            prov_s = f"  [{prov.name}]"

        head = font_small.render(f"{region.name}{prov_s}", True, prov_color)
        surface.blit(head, (PANEL_LEFT, chart_top - 6))

        # Natural Resources display with procedural icons
        res_list = getattr(region, 'natural_resources', set())
        y_cursor = chart_top - 6 + 14
        if res_list:
            from tile_resources import RESOURCE_META
            dep_lbl = font_small.render("Deposits:", True, (245, 210, 110))
            surface.blit(dep_lbl, (PANEL_LEFT, y_cursor))
            dx = PANEL_LEFT + dep_lbl.get_width() + 8
            for r in sorted(res_list, key=lambda x: x.value):
                w = draw_icon_badge(surface, dx, y_cursor - 1, r.value, RESOURCE_META[r].name, font_small, color=RESOURCE_META[r].color, icon_size=15)
                dx += w + 8
            y_cursor += 18

        # Land tenure status strip (P1.4)
        tenure = getattr(region, 'tenure', None)
        if tenure and tenure.plots:
            t_txt = f"Tenure: Feudal {tenure.feudal_fraction*100:.0f}% | Encl {tenure.enclosed_fraction*100:.0f}% | Commons: {tenure.commons_access*100:.0f}%"
            t_color = (130, 210, 140) if tenure.commons_access > 0.5 else (230, 140, 70)
            surface.blit(font_small.render(t_txt, True, t_color), (PANEL_LEFT, y_cursor))
            y_cursor += 16

        col_line = font_small.render(
            f"CoL {region.cost_of_living:.2f}  {region.climate}  (V=nation)", True, DIM)
        surface.blit(col_line, (PANEL_LEFT, y_cursor))
        chart_y_offset = (y_cursor - (chart_top - 6)) + 14

        charts = tile_charts(region)
        view = world.get('view', 0)
        if view == 0:
            draw_chart_grid(surface, charts, font, font_small, world['window'],
                            chart_top + chart_y_offset, chart_bottom, mouse_pos=mouse_pos)
            hint = font_small.render(
                f"Click/1-9,0: Zoom chart  Tab: Grid", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_bottom + 6))
        else:
            idx = max(0, min(len(charts) - 1, view - 1))
            draw_chart_large(surface, charts[idx], font, font_small,
                             world['window'], chart_top + 16, chart_bottom)
            hint = font_small.render(
                f"{charts[idx][0]}  (Click or Tab/Esc = Grid)", True, DIM)
            surface.blit(hint, (PANEL_LEFT, chart_bottom + 6))
        draw_regime_readout(surface, region, font_small, chart_bottom + 24)
    else:
        hint = font_small.render("Hover or click a hex for charts", True, DIM)
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


def draw_ticker(surface, world, font_small):
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


def draw_help(surface, world, font_small, mouse_pos=None):
    """2-Page Paginated Help Guide: Page 1 (Controls & Map), Page 2 (3-Tab Economic Glossary)."""
    if not world.get('help_open', False):
        return

    title_font = get_font(30)
    header_font = get_font(23)
    item_font = get_font(20)

    surface.blit(get_modal_overlay(), (0, 0))

    cur_page = world.get('help_page', 1)

    # Modal Header
    surface.blit(title_font.render('REGNUM v3 — Comprehensive Reference & Economic Guide', True, ACCENT),
                 (32, 18))
    close_hint = font_small.render("[Press H, Esc, or Click to Close | Page 1 / 2 to switch]", True, DIM)
    surface.blit(close_hint, (WIDTH - close_hint.get_width() - 32, 22))

    # Page Tab Headers
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for p_num, rect, label in [(1, HELP_TAB1_RECT, "Page 1: Map Controls & Visual Legend"),
                               (2, HELP_TAB2_RECT, "Page 2: Economic Metrics & Accounts Glossary")]:
        is_sel = (cur_page == p_num)
        is_hov = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        bg = (50, 50, 70) if is_sel else ((40, 40, 54) if is_hov else (28, 28, 38))
        border_c = ACCENT if is_sel else ((110, 110, 130) if is_hov else (60, 60, 75))
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        pygame.draw.rect(surface, border_c, rect, 1, border_radius=4)
        tsurf = font_small.render(label, True, (255, 255, 255) if is_sel else (TEXT if is_hov else DIM))
        surface.blit(tsurf, tsurf.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))

    pygame.draw.line(surface, (70, 70, 85), (32, 94), (WIDTH - 32, 94), 1)

    col_w = (WIDTH - 96) // 3
    col1_x = 32
    col2_x = 32 + col_w + 16
    col3_x = 32 + (col_w + 16) * 2

    # =========================================================================
    # PAGE 1: CONTROLS, CHARTS & MAP VISUAL LEGEND
    # =========================================================================
    if cur_page == 1:
        # Column 1: Controls & Accounts Suite Navigation
        y = 104
        surface.blit(header_font.render('1. CONTROLS & NAVIGATION', True, ACCENT), (col1_x, y))
        y += 24
        col1_items = [
            ("Space", "Play / pause auto-step (~150ms)"),
            ("N or .", "Step 1 turn (while paused)"),
            ("WASD / Arrows", "Pan map camera in 4 directions"),
            ("Middle/Right Drag", "Hold & drag mouse to pan map"),
            ("Mouse Wheel", "Smooth zoom anchored at cursor"),
            ("0 or R / Home", "Reset zoom & center map (1:1)"),
            ("C or [Compare]", "Open 3-Tab Economic Accounts Suite"),
            ("1, 2, 3 in Table", "Switch Macro / Goods / FX tabs"),
            ("F, W, U in Table", "Switch Food / Wood / Furniture"),
            ("On-Screen [+] / [-]", "Map zoom HUD buttons (top-right)"),
            ("Tab / Esc", "Return to 10-chart grid view"),
            ("1 .. 9, 0", "Zoom into individual sidebar chart"),
            ("Click Mini-Chart", "Instant click-to-zoom for chart"),
            ("Click Hex Tile", "Pin tile (multi-province highlights)"),
            ("V", "Toggle Tile vs Nation scope view"),
            ("H or ?", "Toggle this help guide overlay"),
            ("Q or Esc", "Close modal / Quit"),
        ]
        for key, desc in col1_items:
            k_surf = font_small.render(f"{key:<17}", True, (255, 255, 255))
            d_surf = font_small.render(desc, True, DIM)
            surface.blit(k_surf, (col1_x, y))
            surface.blit(d_surf, (col1_x + 130, y))
            y += 18

        y += 8
        surface.blit(header_font.render('ECONOMIC ACCOUNTS SUITE (C)', True, ACCENT), (col1_x, y))
        y += 20
        suite_desc = [
            "Tab 1: Macro Accounts & Leaderboard (GDP/CoL/Pop)",
            "Tab 2: Goods & Provincial Economy (Prices/Inv/D vs S)",
            "Tab 3: External Sector, FX & Banking (Rates/Equity)",
            "* All metrics feature real-time turn deltas (+/-Delta)",
        ]
        for item in suite_desc:
            surface.blit(font_small.render(item, True, ACCENT if '*' in item else TEXT), (col1_x, y))
            y += 16

        # Column 2: Hex Colors & Labels
        y = 104
        surface.blit(header_font.render('2. MAP COLORS & LABELS', True, ACCENT), (col2_x, y))
        y += 24

        color_items = [
            ("Mint Green Hex", "Nation Alpha sovereign territory", (141, 211, 199)),
            ("Pale Yellow Hex", "Nation Beta sovereign territory", (255, 255, 179)),
            ("Lavender Hex", "Nation Gamma sovereign territory", (190, 186, 218)),
            ("Dark Grey Hex", "Unclaimed wilderness (unsettled)", (120, 120, 128)),
            ("Luminance Glow", "Pop heatmap (brighter = denser pop)", (255, 255, 220)),
            ("Province Outlines", "Multi-color province borders per nation", (60, 210, 230)),
        ]
        for title, desc, col in color_items:
            pygame.draw.rect(surface, col, (col2_x, y + 2, 10, 10), border_radius=2)
            surface.blit(font_small.render(title, True, col), (col2_x + 18, y))
            surface.blit(font_small.render(desc, True, DIM), (col2_x + 18, y + 13))
            y += 28

        y += 4
        surface.blit(header_font.render('TILE TEXT SUMMARY', True, ACCENT), (col2_x, y))
        y += 20
        text_items = [
            ("rXcY", "Hex axial coordinates (Row X, Col Y)"),
            ("pop <N>", "Total living agents residing on tile"),
            ("food $<P>", "Local market clearing price for food"),
            ("tr <N>", "Count of active merchant traders based here"),
            ("hs <H>+<W>n", "Homesteaders (H) + wilderness pop (W)"),
            ("+N / -N", "Net pop delta from last turn (Green/Red)"),
        ]
        for tag, desc in text_items:
            surface.blit(font_small.render(f"{tag:<12}", True, (255, 255, 255)), (col2_x, y))
            surface.blit(font_small.render(desc, True, DIM), (col2_x + 85, y))
            y += 17

        y += 6
        surface.blit(header_font.render('TRADE NETWORK & TICKER', True, ACCENT), (col2_x, y))
        y += 20
        net_items = [
            ("Grey Lines", "Overland trade routes connecting hexes"),
            ("Cyan Arrows", "Active bilateral trade (width = volume)"),
            ("Pulsing Dots", "Trade animation showing shipment direction"),
            ("MIGRATE (Cyan)", "Agents moving across tiles / homesteading"),
            ("CLAIM (Gold)", "Wilderness tile annexed by a nation"),
            ("DESTROY (Red)", "Business bankruptcy or debt liquidation"),
        ]
        for tag, desc in net_items:
            surface.blit(font_small.render(tag, True, TEXT), (col2_x, y))
            surface.blit(font_small.render(desc, True, DIM), (col2_x, y + 12))
            y += 25

        # Column 3: Badges, Rings & Glyphs
        y = 104
        surface.blit(header_font.render('3. BADGES, RINGS & GLYPHS', True, ACCENT), (col3_x, y))
        y += 24

        badge_items = [
            ("Green [ W ]", "Frontier wilderness border tile", (90, 210, 120)),
            ("Orange [ U ]", "Unrest stage (discontent brewing)", (230, 170, 60)),
            ("Deep Orange [ P ]", "Protest stage (street demonstrations)", (240, 140, 40)),
            ("Bright Red [ M ]", "Mob stage (riots / unrest violence)", (235, 70, 70)),
            ("Lime Green [ C ]", "Compromise stage (regime concessions)", (160, 230, 90)),
            ("Purple [ T ]", "Takeover stage (regime overthrown)", (180, 100, 230)),
            ("Orange Top Dot", "Food demand scarcity alert (ratio > 1.5)", (240, 150, 60)),
            ("Red Left Dot", "Severe hunger warning (>5 starving agents)", (235, 70, 70)),
            ("Green Tag T<N>", "Active traders operating on tile", (90, 210, 120)),
            ("Purple Left Dot", "High wealth inequality warning (Gini > 0.6)", (190, 110, 230)),
        ]
        for tag, desc, col in badge_items:
            pygame.draw.circle(surface, col, (col3_x + 5, y + 7), 4)
            surface.blit(font_small.render(tag, True, col), (col3_x + 16, y))
            surface.blit(font_small.render(desc, True, DIM), (col3_x + 16, y + 12))
            y += 25

        y += 4
        surface.blit(header_font.render('TERRAIN GLYPHS & ARBITRAGE', True, ACCENT), (col3_x, y))
        y += 20
        glyph_items = [
            ("Gold Triangle", "Fertile Farmland (food productivity bonus > 1.3x)", (240, 200, 90)),
            ("Green Triangle", "Dense Forest (timber productivity bonus > 1.3x)", (110, 190, 110)),
            ("White Circle", "Cold Climate (higher heating/food living cost)", (240, 245, 250)),
            ("Orange Hot Ring", "Local food price is >15% higher than neighbors", (235, 120, 60)),
            ("Blue Cold Ring", "Local food price is >15% cheaper than neighbors", (110, 170, 235)),
        ]
        for tag, desc, col in glyph_items:
            pygame.draw.circle(surface, col, (col3_x + 5, y + 7), 4)
            surface.blit(font_small.render(tag, True, col), (col3_x + 16, y))
            surface.blit(font_small.render(desc, True, DIM), (col3_x + 16, y + 12))
            y += 25

    # =========================================================================
    # PAGE 2: ECONOMIC METRICS & 3-TAB ACCOUNTS GLOSSARY
    # =========================================================================
    elif cur_page == 2:
        # Column 1: Tab 1 - Macro Accounts & Leaderboard
        y = 104
        surface.blit(header_font.render('TAB 1: MACRO ACCOUNTS & LEADERBOARD', True, ACCENT), (col1_x, y))
        y += 24
        tab1_glossary = [
            ("Nominal GDP ($/turn)", "Total value of all finished goods produced and cleared in market auctions at current clearing prices."),
            ("Real Chained GDP ($)", "Physical production valued at fixed baseline basket prices. Isolates true physical output growth from price inflation."),
            ("GDP per Capita ($)", "Average gross economic output produced per living citizen (Nominal GDP / Living Population)."),
            ("Cost of Living (CoL / CPI)", "Price index of the essential subsistence basket (Food, Wood heating, Furniture shelter)."),
            ("Gini Inequality Index", "Wealth concentration ratio (0.0 = perfect equality, 1.0 = hyper-inequality with extreme elite capture)."),
            ("Severe Hunger Count", "Count of impoverished citizens unable to purchase minimum subsistence rations (starvation risk)."),
            ("Social Protest Energy", "Civil discontent energy accumulated from inequality, high food costs, and corruption towards riots/coups."),
            ("Treasury Total Reserves ($)", "Sovereign liquidity held by the government in hand cash and central bank deposits."),
            ("Strategic Food Reserve", "Physical grain stockpiles held in government silos for emergency famine relief and market stability."),
            ("Regime Legitimacy (0-1.0)", "Public acceptance of government authority. High legitimacy deters civil unrest and coups."),
        ]
        for term, explanation in tab1_glossary:
            surface.blit(font_small.render(term, True, (255, 255, 255)), (col1_x, y))
            y += 15
            # Wrap explanation
            words = explanation.split()
            line = ""
            for w in words:
                test_line = line + (" " if line else "") + w
                if item_font.size(test_line)[0] > col_w - 10:
                    surface.blit(item_font.render(line, True, DIM), (col1_x, y))
                    y += 13
                    line = w
                else:
                    line = test_line
            if line:
                surface.blit(item_font.render(line, True, DIM), (col1_x, y))
                y += 13
            y += 6

        # Column 2: Tab 2 - Goods & Provincial Economy
        y = 104
        surface.blit(header_font.render('TAB 2: GOODS MARKET & PROVINCES', True, ACCENT), (col2_x, y))
        y += 24
        tab2_glossary = [
            ("Market Clearing Price ($)", "Equilibrium price established in double auctions where local buyers and sellers match."),
            ("Physical Output (Units)", "Total gross quantity of physical units harvested, cut, or crafted by producers this turn."),
            ("Labor Productivity", "Output units generated per active worker agent in that specific commodity profession."),
            ("Inventory per Capita", "Total warehouse inventory divided by total living population (community reserve buffer)."),
            ("Inventory per Producer", "Warehouse buffer stock held per farmer, lumberjack, or craftsperson (producer safety cushion)."),
            ("Demand vs Supply (D / S)", "Total units of buy orders submitted vs sell orders offered in local pay-as-bid auctions."),
            ("Demand Ratio (D/S)", "Market scarcity index (>1.0 = demand exceeds supply / price inflation; <1.0 = supply glut / deflation)."),
            ("Sector Net Trade ($)", "Export revenues minus import expenditures for that specific commodity category."),
        ]
        for term, explanation in tab2_glossary:
            surface.blit(font_small.render(term, True, (255, 255, 255)), (col2_x, y))
            y += 15
            words = explanation.split()
            line = ""
            for w in words:
                test_line = line + (" " if line else "") + w
                if item_font.size(test_line)[0] > col_w - 10:
                    surface.blit(item_font.render(line, True, DIM), (col2_x, y))
                    y += 13
                    line = w
                else:
                    line = test_line
            if line:
                surface.blit(item_font.render(line, True, DIM), (col2_x, y))
                y += 13
            y += 7

        # Column 3: Tab 3 - External Sector, Forex & Banking
        y = 104
        surface.blit(header_font.render('TAB 3: FX, MONETARY & BANKING', True, ACCENT), (col3_x, y))
        y += 24
        tab3_glossary = [
            ("ForexDesk Mid Quote", "Central bank exchange rate: units of domestic currency required to purchase 1 unit of foreign currency."),
            ("PPP Valuation Gap (%)", "Exchange rate deviation from Purchasing Power Parity. (+% = undervalued / cheap exports, -% = overvalued currency)."),
            ("Bank Domestic FX Pool ($)", "Domestic cash liquidity set aside by the provincial central bank to buy foreign currency from exporters."),
            ("Foreign Reserves War Chest", "Foreign paper currency stored in bank vaults to supply local traders purchasing imports abroad."),
            ("Commercial Bank Deposits ($)", "Customer savings liabilities owed by the provincial bank to private citizens and corporations."),
            ("Bank Equity Capital ($)", "Share capital and retained earnings absorbing loan defaults and bad debts (solvency cushion)."),
            ("Solvency Ratio (Equity/Deposits)", "Capital adequacy ratio (>15% = rock-solid credit buffer, <5% = distress zone / insolvency risk)."),
            ("Net Trade Balance ($)", "Aggregate foreign trade surplus (+) or deficit (-) across all commodities."),
        ]
        for term, explanation in tab3_glossary:
            surface.blit(font_small.render(term, True, (255, 255, 255)), (col3_x, y))
            y += 15
            words = explanation.split()
            line = ""
            for w in words:
                test_line = line + (" " if line else "") + w
                if item_font.size(test_line)[0] > col_w - 10:
                    surface.blit(item_font.render(line, True, DIM), (col3_x, y))
                    y += 13
                    line = w
                else:
                    line = test_line
            if line:
                surface.blit(item_font.render(line, True, DIM), (col3_x, y))
                y += 13
            y += 7
