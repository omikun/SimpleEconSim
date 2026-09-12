"""
worldview_cadastre.py — Visual Plot Inspector & Estate Cadastre UI for REGNUM.

Provides an interactive estate cadastre and land tenure inspection panel in the right sidebar:
  1. Parish Land Summary (Commons Usufruct %, Feudal Manorial %, Enclosed Private %, Pasture vs Arable).
  2. Discrete Plot Inspection: Authentic country plot name, acreage fraction, tenure status badge.
  3. Land Use & Labor Allocation (Arable grain crops vs Pasture sheep grazing).
  4. Bound Tenant Roster (Social class, living status, cash, survey debts).
  5. Statutory Foreclosure Countdown (Pending enclosure surveying fees & foreclosure deadlines).
  6. Contextual Land Decrees: [Enclose Feudal Plot], [Convert to Pasture/Arable], [Restore Commons].
"""

from __future__ import annotations
import pygame
from goods import Goods
from land_tenure import TenureStatus, LandPlot
from enclosure import calculate_charter_fee, execute_enclosure
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import TEXT, DIM, RED, GREEN, ACCENT, HEX_EDGE
from ui_icons import get_icon

PANEL_LEFT = MAP_RIGHT + 12
PANEL_W = WIDTH - PANEL_LEFT - 6

# Color palette for cadastre tenure
C_COMMONS = (100, 215, 130)       # Lush customary green
C_FEUDAL = (220, 180, 75)         # Warm feudal gold
C_ENCLOSED = (215, 120, 60)       # Parched enclosed amber/brown
C_PASTURE = (160, 210, 150)       # Sage wool pasture
C_ARABLE = (235, 205, 110)        # Golden grain wheat

CARD_BG = (24, 28, 38)
CARD_BORDER = (45, 52, 70)
BTN_BG = (38, 44, 60)
BTN_HOVER = (55, 65, 90)

_CADASTRE_BUTTONS = []


def _draw_btn(surface, rect, text, font_small, mx, my, enabled=True, color=TEXT, border_color=None):
    """Draw interactive button with hover highlight."""
    rx, ry, rw, rh = rect
    hov = enabled and (rx <= mx <= rx + rw and ry <= my <= ry + rh)
    bg = BTN_HOVER if hov else BTN_BG
    if not enabled:
        bg = (24, 26, 34)
    pygame.draw.rect(surface, bg, rect, border_radius=4)
    b_col = border_color or (ACCENT if hov else ((65, 75, 100) if enabled else (40, 44, 56)))
    pygame.draw.rect(surface, b_col, rect, 1, border_radius=4)
    txt_col = (255, 255, 255) if hov else (color if enabled else DIM)
    lbl = font_small.render(text, True, txt_col)
    surface.blit(lbl, lbl.get_rect(center=(rx + rw // 2, ry + rh // 2)))


def draw_cadastre_panel(surface, world: dict, region, font, font_small, mouse_pos=None):
    """Draw the Estate Cadastre & Land Plot Inspector in the right-hand panel."""
    global _CADASTRE_BUTTONS
    _CADASTRE_BUTTONS.clear()

    d = TOP_BAR_H
    panel_top = 180 + d
    panel_bottom = HEIGHT - TICKER_H - 24
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    if region is None and world.get('nations') and world['nations'][0].tiles:
        region = world['nations'][0].tiles[0]

    if region is None:
        surface.blit(font_small.render("No tile selected for cadastre inspection.", True, DIM), (PANEL_LEFT + 10, panel_top + 20))
        return

    tenure = getattr(region, 'tenure', None)
    cur_y = panel_top + 4

    # 1. Header Summary Card: Parish Land Breakdown
    h_card_h = 72
    h_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, h_card_h)
    pygame.draw.rect(surface, CARD_BG, h_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, h_rect, 1, border_radius=5)

    c_name = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
    surface.blit(font_small.render(f"Cadastre: {c_name}", True, (240, 200, 110)), (PANEL_LEFT + 12, cur_y + 6))

    if tenure and tenure.plots:
        com_pct = tenure.commons_access * 100
        feu_pct = tenure.feudal_fraction * 100
        enc_pct = tenure.enclosed_fraction * 100
        pas_pct = tenure.pasture_fraction * 100
        ara_pct = tenure.arable_fraction * 100

        l1 = f"Commons: {com_pct:.0f}%  •  Feudal: {feu_pct:.0f}%  •  Enclosed: {enc_pct:.0f}%"
        surface.blit(font_small.render(l1, True, (130, 210, 140) if com_pct > 40 else (230, 140, 70)), (PANEL_LEFT + 12, cur_y + 26))

        l2 = f"Land Use: Arable {ara_pct:.0f}%  |  Pasture {pas_pct:.0f}% (Wool)"
        surface.blit(font_small.render(l2, True, DIM), (PANEL_LEFT + 12, cur_y + 44))
    else:
        surface.blit(font_small.render("Wilderness or unchartered territory (Customary Commons).", True, (120, 200, 130)), (PANEL_LEFT + 12, cur_y + 28))

    cur_y += h_card_h + 8

    # 2. Scroll controls for Plot List
    scroll = world.get('cadastre_scroll', 0)
    plots = tenure.plots if tenure else []
    
    if not plots:
        surface.blit(font_small.render("No surveyed plots found on this parish.", True, DIM), (PANEL_LEFT + 12, cur_y + 10))
        return

    # Scroll header
    s_lbl = font_small.render(f"Surveyed Parcels ({len(plots)} Plots)", True, (200, 210, 225))
    surface.blit(s_lbl, (PANEL_LEFT + 10, cur_y))
    
    btn_up = (PANEL_LEFT + PANEL_W - 52, cur_y - 2, 22, 18)
    btn_dn = (PANEL_LEFT + PANEL_W - 26, cur_y - 2, 22, 18)
    _draw_btn(surface, btn_up, "▲", font_small, mx, my, enabled=(scroll > 0))
    _draw_btn(surface, btn_dn, "▼", font_small, mx, my, enabled=(scroll + 2 < len(plots)))
    _CADASTRE_BUTTONS.append((btn_up, 'cadastre_scroll_up', None))
    _CADASTRE_BUTTONS.append((btn_dn, 'cadastre_scroll_down', None))

    cur_y += 22

    # 3. Render Visible Plot Cards
    visible_plots = plots[scroll:scroll + 3]
    for plot in visible_plots:
        card_h = 106
        if cur_y + card_h > panel_bottom:
            break

        c_rect = (PANEL_LEFT + 4, cur_y, PANEL_W - 8, card_h)
        pygame.draw.rect(surface, CARD_BG, c_rect, border_radius=5)

        # Border colored by tenure
        b_col = C_COMMONS if plot.tenure == TenureStatus.COMMONS else (C_FEUDAL if plot.tenure == TenureStatus.FEUDAL else C_ENCLOSED)
        pygame.draw.rect(surface, b_col, c_rect, 1, border_radius=5)

        # Line 1: Authentic Plot Name + Fraction
        p_name = plot.display_name or f"Parcel #{plot.plot_id}"
        frac_txt = f"{plot.fraction*100:.0f}% Area"
        surface.blit(font_small.render(p_name, True, (240, 240, 240)), (PANEL_LEFT + 12, cur_y + 6))
        
        # Tenure badge
        t_badge = plot.tenure.value
        t_badge_lbl = font_small.render(f"[{t_badge}]", True, b_col)
        surface.blit(t_badge_lbl, (PANEL_LEFT + PANEL_W - t_badge_lbl.get_width() - 14, cur_y + 6))

        # Line 2: Land Use & Lord
        p_type = getattr(plot, 'production_type', 'arable')
        type_col = C_PASTURE if p_type == 'pasture' else C_ARABLE
        type_str = "🐑 Pasture (Wool)" if p_type == 'pasture' else "🌾 Arable (Grain)"

        lord = next((a for a in region.agents if a.id == plot.lord_id), None)
        lord_str = f"Lord: {getattr(lord, 'name', f'Agent #{plot.lord_id}')} (${lord.cash:.0f})" if lord else "Lord: Crown / Common"
        surface.blit(font_small.render(f"{type_str}  •  {frac_txt}", True, type_col), (PANEL_LEFT + 12, cur_y + 24))
        surface.blit(font_small.render(lord_str, True, DIM), (PANEL_LEFT + 12, cur_y + 40))

        # Line 3: Tenants & Debts
        t_count = len(plot.tenant_ids)
        debts = [d for d in getattr(region, 'enclosure_survey_debts', []) if d.get('plot_id') == plot.plot_id]
        
        t_info = f"Bound Tenants: {t_count}"
        if debts:
            d_first = debts[0]
            t_rem = max(0, d_first['deadline'] - world.get('turn', 0))
            t_info += f"  •  ⚠️ Foreclosure in {t_rem}t ($15 due)"
            surface.blit(font_small.render(t_info, True, (245, 140, 80)), (PANEL_LEFT + 12, cur_y + 56))
        else:
            surface.blit(font_small.render(t_info, True, (160, 200, 220)), (PANEL_LEFT + 12, cur_y + 56))

        # Line 4: Context Action Buttons
        by = cur_y + 76
        if plot.tenure == TenureStatus.FEUDAL:
            fee = calculate_charter_fee(plot)
            can_enc = (lord is not None and lord.cash >= fee)
            b_enc = (PANEL_LEFT + 12, by, 130, 22)
            _draw_btn(surface, b_enc, f"Enclose (${fee:.0f})", font_small, mx, my,
                      enabled=can_enc, color=(240, 140, 70) if can_enc else DIM)
            _CADASTRE_BUTTONS.append((b_enc, 'cadastre_enclose', (region, plot.plot_id)))
        elif plot.tenure == TenureStatus.ENCLOSED:
            # Pasture / Arable Toggle
            is_pas = (p_type == 'pasture')
            b_mode = (PANEL_LEFT + 12, by, 116, 22)
            lbl_mode = "To Arable" if is_pas else "To Pasture"
            _draw_btn(surface, b_mode, lbl_mode, font_small, mx, my, enabled=True, color=(230, 200, 100) if is_pas else (160, 210, 150))
            _CADASTRE_BUTTONS.append((b_mode, 'cadastre_toggle_pasture', (region, plot.plot_id)))

            # Restore Commons Button
            b_rest = (PANEL_LEFT + 134, by, 116, 22)
            _draw_btn(surface, b_rest, "Restore Commons", font_small, mx, my, enabled=True, color=(120, 220, 140))
            _CADASTRE_BUTTONS.append((b_rest, 'cadastre_restore_commons', (region, plot.plot_id)))
        else:
            # Customary Commons
            surface.blit(font_small.render("Traditional usufruct foraging active.", True, (130, 210, 140)), (PANEL_LEFT + 14, by + 4))

        cur_y += card_h + 8


def cadastre_panel_hit(pos, world: dict) -> bool:
    """Handle mouse clicks on the Estate Cadastre panel."""
    global _CADASTRE_BUTTONS
    mx, my = pos
    for rect, act_id, payload in _CADASTRE_BUTTONS:
        rx, ry, rw, rh = rect
        if rx <= mx <= rx + rw and ry <= my <= ry + rh:
            if act_id == 'cadastre_scroll_up':
                world['cadastre_scroll'] = max(0, world.get('cadastre_scroll', 0) - 1)
                return True
            elif act_id == 'cadastre_scroll_down':
                world['cadastre_scroll'] = world.get('cadastre_scroll', 0) + 1
                return True
            elif act_id == 'cadastre_enclose':
                reg, plot_id = payload
                from enclosure import execute_enclosure
                ok, msg, _evs = execute_enclosure(reg, plot_id, world.get('turn', 0))
                world['policy_feedback'] = (msg, (230, 140, 70) if ok else RED)
                try:
                    from worldview_engine import ticker_push
                    ticker_push(world, world.get('turn', 0), 'ENCLOSURE', msg, (230, 140, 70))
                except ImportError:
                    pass
                return True
            elif act_id == 'cadastre_toggle_pasture':
                reg, plot_id = payload
                plot = reg.tenure.find_plot(plot_id) if hasattr(reg, 'tenure') else None
                if plot:
                    new_t = 'pasture' if getattr(plot, 'production_type', 'arable') != 'pasture' else 'arable'
                    reg.tenure.convert_production_type(plot_id, new_t, world.get('turn', 0))
                    msg = f"Plot {plot.display_name} switched to {new_t.upper()}."
                    if new_t == 'pasture':
                        msg += " 75% tenants dispossessed."
                    world['policy_feedback'] = (msg, (210, 180, 100))
                    try:
                        from worldview_engine import ticker_push
                        ticker_push(world, world.get('turn', 0), 'LAND_USE', msg, (210, 180, 100))
                    except ImportError:
                        pass
                return True
            elif act_id == 'cadastre_restore_commons':
                reg, plot_id = payload
                if hasattr(reg, 'tenure'):
                    reg.tenure.revert_plot_to_commons(plot_id, world.get('turn', 0))
                    reg.unrest_level = max(0.0, getattr(reg, 'unrest_level', 0.0) - 0.25)
                    msg = f"Plot restored to Customary Commons on {reg.name}!"
                    world['policy_feedback'] = (msg, GREEN)
                    try:
                        from worldview_engine import ticker_push
                        ticker_push(world, world.get('turn', 0), 'COMMONS', msg, (120, 220, 140))
                    except ImportError:
                        pass
                return True
    return False
