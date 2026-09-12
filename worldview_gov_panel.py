"""
worldview_gov_panel.py — Left Governance & Policies Panel for City, Province, and Nation Scopes.

Provides a dedicated left drawer matching the Build Menu:
- Segmented Scope Switcher: City / Tile (🏛️), Province (🗺️), Nation (👑).
- Detailed multi-tier treasury and demographic stats.
- Interactive policy decrees (Tax adjustments, Emergency food relief, Highway maintenance,
  Scientific grants, Law enforcement, and Equalization transfers).
"""

from __future__ import annotations
import pygame
from worldview_camera import HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon
from unrest import apply_repression
from worldview_tooltips import get_button_tooltip_data

GOV_PANEL_X = 14
GOV_PANEL_Y = TOP_BAR_H + 10
GOV_PANEL_W = 310
GOV_PANEL_H = HEIGHT - TOP_BAR_H - TICKER_H - 18

CARD_BG = (24, 26, 36)
CARD_BORDER = (45, 50, 70)
BTN_BG = (36, 42, 58)
BTN_HOVER = (52, 60, 84)
BTN_BORDER = (70, 85, 115)

_GOV_BUTTONS: list[tuple[tuple[int, int, int, int], str, any]] = []


def draw_left_dock_buttons(surface, world, font_small, mouse_pos=None):
    """Draw the floating left dock toggle buttons for all left-hand panels."""
    from worldview_left_dock import draw_left_dock_buttons as _draw_dock
    _draw_dock(surface, world, font_small, mouse_pos)


def _draw_gov_btn(surface, rect, label, font_small, mx, my, act_id, target,
                  enabled=True, color=TEXT, custom_bg=None, icon_kind=None,
                  world=None, region=None, nation=None, province=None):
    """Draw an interactive policy decree button, register hit rect, and attach tooltip."""
    global _GOV_BUTTONS
    bx, by, bw, bh = rect
    is_hov = (bx <= mx <= bx + bw and by <= my <= by + bh)

    if enabled:
        from ui_targets import register_target
        register_target(world, rect, ('gov_policy', act_id), tooltip_id=act_id, scope='gov', data=target)
        _GOV_BUTTONS.append((rect, act_id, target))

    # Tooltip detection
    if is_hov and act_id and world is not None:
        tdata = get_button_tooltip_data(act_id, world, region=region, nation=nation, province=province)
        if tdata:
            tdata['btn_rect'] = rect
            world['_hovered_left_tooltip'] = tdata

    if not enabled:
        bg = (24, 26, 34)
        bc = (40, 42, 54)
        tc = (70, 75, 90)
    else:
        bg = custom_bg if custom_bg else (BTN_HOVER if is_hov else BTN_BG)
        bc = ACCENT if is_hov else BTN_BORDER
        tc = (255, 255, 255) if is_hov else color

    pygame.draw.rect(surface, bg, rect, border_radius=4)
    pygame.draw.rect(surface, bc, rect, 1, border_radius=4)

    txt_surf = font_small.render(label, True, tc)
    if icon_kind:
        ico = get_icon(icon_kind, size=13)
        total_w = 13 + 4 + txt_surf.get_width()
        start_x = bx + (bw - total_w) // 2
        surface.blit(ico, (start_x, by + (bh - 13) // 2))
        surface.blit(txt_surf, (start_x + 17, by + (bh - txt_surf.get_height()) // 2))
    else:
        surface.blit(txt_surf, txt_surf.get_rect(center=(bx + bw // 2, by + bh // 2)))


def draw_gov_panel(surface, world, font, font_small, mouse_pos=None):
    """Draw the left-hand Governance & Policies Panel for the selected tile/province/nation."""
    global _GOV_BUTTONS
    _GOV_BUTTONS = []

    if not world.get('gov_panel_open', False):
        return

    # Auto-collapse layer dock so it doesn't draw underneath
    world['layers_collapsed'] = True
    world['build_panel_open'] = False
    world['diplomacy_panel_open'] = False
    world['debt_panel_open'] = False
    world['science_panel_open'] = False
    world['military_panel_open'] = False
    world['left_panel'] = 'governance'

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    x, y, w, h = GOV_PANEL_X, GOV_PANEL_Y, GOV_PANEL_W, GOV_PANEL_H
    pinned = world.get('selected_region')

    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    if pinned is None:
        return

    # Background frame
    panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    panel_surf.fill((16, 18, 26, 245))
    surface.blit(panel_surf, (x, y))
    pygame.draw.rect(surface, (65, 70, 90), (x, y, w, h), 1, border_radius=8)

    city_name = getattr(pinned, 'display_name', getattr(pinned, 'city_name', pinned.name))
    nation = getattr(pinned, 'owner_nation', None)
    province = getattr(pinned, 'province', None)
    is_wilderness = (nation is None)
    prov_name = province.name if province else "Province"
    nat_name = nation.name if nation else "Wilderness Frontier"

    # Header
    g_icon = get_icon('camp' if is_wilderness else 'municipal', 16)
    surface.blit(g_icon, (x + 12, y + 12))

    head_txt = font.render(f"Governance: {city_name}", True, (245, 215, 110))
    surface.blit(head_txt, (x + 32, y + 10))

    sub_txt = font_small.render(f"{prov_name} • {nat_name}", True, DIM)
    surface.blit(sub_txt, (x + 32, y + 30))

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    from ui_targets import register_target
    register_target(world, close_rect, 'close_left', scope='gov')
    hc = close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18
    pygame.draw.rect(surface, (60, 60, 80) if hc else (35, 35, 48), close_rect, border_radius=3)
    x_txt = font_small.render("×", True, (255, 255, 255) if hc else DIM)
    surface.blit(x_txt, (close_rect[0] + 4, close_rect[1] + 1))

    # Drawer Top Switcher Tabs
    from worldview_left_dock import draw_drawer_top_tabs
    cur_y = draw_drawer_top_tabs(surface, world, x, y + 48, w, 'governance', font_small, mouse_pos)

    # Scope Switcher Tabs
    scope_y = cur_y
    active_scope = world.get('policy_scope', 'tile')

    if is_wilderness:
        scopes = [('tile', 'Frontier', 'camp'), ('nation', 'Sponsor', 'crown')]
    else:
        scopes = [('tile', 'City', 'municipal'), ('province', 'Province', 'roads'), ('nation', 'Nation', 'crown')]

    tab_w = (w - 24) // len(scopes)

    for i, (sc_id, sc_label, sc_ico) in enumerate(scopes):
        tx = x + 8 + i * (tab_w + 4)
        t_rect = (tx, scope_y, tab_w, 24)
        tip_id = 'tier_frontier' if (is_wilderness and sc_id == 'tile') else ('tier_municipal' if sc_id == 'tile' else f"tier_{sc_id}")
        register_target(world, t_rect, ('gov_scope', sc_id), tooltip_id=tip_id, scope='gov')
        is_sel = (active_scope == sc_id)
        is_hov = t_rect[0] <= mx <= t_rect[0] + tab_w and t_rect[1] <= my <= t_rect[1] + 24
        if is_hov and world is not None:
            from worldview_tooltips import get_button_tooltip_data
            tdata = get_button_tooltip_data(tip_id, world, region=pinned, nation=nation, province=province)
            if tdata:
                tdata['btn_rect'] = t_rect
                world['_hovered_left_tooltip'] = tdata

        bg = (52, 70, 95) if is_sel else ((40, 42, 56) if is_hov else (28, 30, 42))
        bc = ACCENT if is_sel else ((90, 95, 120) if is_hov else (55, 60, 80))
        pygame.draw.rect(surface, bg, t_rect, border_radius=4)
        pygame.draw.rect(surface, bc, t_rect, 1, border_radius=4)

        tc = (255, 255, 255) if is_sel else (TEXT if is_hov else DIM)
        tsurf = font_small.render(sc_label, True, tc)
        ico = get_icon(sc_ico, size=12)
        tot_w = 12 + 4 + tsurf.get_width()
        start_x = tx + (tab_w - tot_w) // 2
        surface.blit(ico, (start_x, scope_y + (24 - 12) // 2))
        surface.blit(tsurf, (start_x + 16, scope_y + (24 - tsurf.get_height()) // 2))

    cur_y = scope_y + 32

    # Render Scope Content
    if is_wilderness and active_scope == 'tile':
        _draw_left_frontier_scope(surface, world, pinned, cur_y, x, w, font, font_small, mx, my)
    elif active_scope == 'tile':
        _draw_left_city_scope(surface, world, pinned, nation, cur_y, x, w, font, font_small, mx, my)
    elif active_scope == 'province':
        _draw_left_province_scope(surface, world, pinned, province, nation, cur_y, x, w, font, font_small, mx, my)
    else:
        _draw_left_nation_scope(surface, world, pinned, nation, cur_y, x, w, font, font_small, mx, my)


def _draw_left_frontier_scope(surface, world, region, start_y, x, w, font, font_small, mx, my):
    """Render Frontier Wilderness colonization and settlement cards."""
    hs_count = sum(1 for a in region.agents if getattr(a, 'is_homesteader', False))
    native_pop = getattr(region, 'wilderness_pop', 0)
    sponsor = world['nations'][0] if world.get('nations') else None

    # 1. Frontier Status Card
    c1_h = 72
    c1_rect = (x + 8, start_y, w - 16, c1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(get_icon('camp', 14), (x + 16, start_y + 8))
    surface.blit(font_small.render("Unclaimed Frontier Territory", True, (245, 190, 80)), (x + 34, start_y + 7))
    surface.blit(font_small.render(f"Homesteaders: {hs_count}  •  Indigenous: {native_pop}", True, (220, 230, 245)), (x + 16, start_y + 26))
    surface.blit(font_small.render("Territorial Claim Threshold: 50%+ Settlers", True, DIM), (x + 16, start_y + 44))

    cur_y = start_y + c1_h + 10

    # 2. Colonization Decrees Card
    c2_h = 92
    c2_rect = (x + 8, cur_y, w - 16, c2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Frontier Settlement Decrees:", True, ACCENT), (x + 16, cur_y + 8))

    d1_rect = (x + 16, cur_y + 28, w - 32, 26)
    _draw_gov_btn(surface, d1_rect, "Sponsor Settlers ($100)", font_small, mx, my,
                  'frontier_expedition', region, enabled=True, color=GREEN, icon_kind='settler',
                  world=world, region=region, nation=sponsor)

    d2_rect = (x + 16, cur_y + 58, w - 32, 26)
    _draw_gov_btn(surface, d2_rect, "Send Pioneer Aid ($40)", font_small, mx, my,
                  'frontier_pioneer_grant', region, enabled=True, color=(160, 220, 150), icon_kind='food',
                  world=world, region=region, nation=sponsor)


def _draw_left_city_scope(surface, world, region, nation, start_y, x, w, font, font_small, mx, my):
    """Render City / Tile governance cards."""
    rgov = getattr(region, 'gov', None)
    tile_cash = (rgov.agent.cash if rgov and hasattr(rgov, 'agent') else 0.0) + (region.bank.deposits.get(rgov.agent, 0.0) if hasattr(region, 'bank') and rgov and hasattr(rgov, 'agent') else 0.0)
    tax_rate = rgov.tax_rate if rgov else 0.15
    hungry = sum(1 for a in region.agents if not a.is_corporation and not a.is_government and a.hungry_steps > 0)
    protest_e = region.protest_energy_log[-1] if region.protest_energy_log else 0.0
    ubi_active = getattr(rgov, 'ubi_enabled', getattr(rgov, 'ubi_active', False))

    # 1. Municipal Treasury & Stats Card
    card1_h = 76
    c1_rect = (x + 8, start_y, w - 16, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(get_icon('municipal', 14), (x + 16, start_y + 8))
    surface.blit(font_small.render(f"Municipal Treasury: ${tile_cash:,.0f}", True, (120, 240, 150)), (x + 34, start_y + 7))
    surface.blit(font_small.render(f"Tax Rate: {tax_rate*100:.1f}%  •  Protest: {protest_e:.2f}", True, (220, 230, 245)), (x + 16, start_y + 26))
    food_inv = getattr(rgov, 'food_inventory', getattr(rgov, 'food_reserve', 0.0)) if rgov else 0.0
    surface.blit(font_small.render(f"Hungry Citizens: {hungry}  •  Food Inv: {food_inv:.1f}", True, (245, 180, 80)), (x + 16, start_y + 44))

    cur_y = start_y + card1_h + 8

    # 2. Tax Adjusters & UBI Card
    card2_h = 78
    c2_rect = (x + 8, cur_y, w - 16, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Fiscal Taxation & Welfare:", True, (245, 215, 120)), (x + 16, cur_y + 8))

    b1_rect = (x + 16, cur_y + 26, (w - 38) // 2, 22)
    b2_rect = (x + 22 + (w - 38) // 2, cur_y + 26, (w - 38) // 2, 22)
    _draw_gov_btn(surface, b1_rect, "[-2% Tax]", font_small, mx, my,
                  'city_tax_cut', region, enabled=(tax_rate > 0.02),
                  world=world, region=region, nation=nation)
    _draw_gov_btn(surface, b2_rect, "[+2% Tax]", font_small, mx, my,
                  'city_tax_raise', region, enabled=(tax_rate < 0.60),
                  world=world, region=region, nation=nation)

    pop_count = len([a for a in region.agents if not a.is_corporation and not a.is_government and a.alive])
    ubi_turn = pop_count * 5.0
    ubi_mandate = pop_count * 50.0
    turns_rem = getattr(rgov, 'ubi_mandate_turns_left', 10 if ubi_active else 0)

    b3_rect = (x + 16, cur_y + 50, w - 32, 22)
    if ubi_active:
        ubi_lbl = f"UBI Active: {turns_rem}t rem (${ubi_turn:,.0f}/t)"
    else:
        ubi_lbl = f"Enact UBI (10t: ${ubi_mandate:,.0f} @ $5/cit)"
    _draw_gov_btn(surface, b3_rect, ubi_lbl, font_small, mx, my,
                  'city_toggle_ubi', region, enabled=True,
                  color=(120, 240, 150) if ubi_active else (TEXT if tile_cash >= ubi_mandate else (245, 190, 80)),
                  world=world, region=region, nation=nation)

    cur_y += card2_h + 8

    # 3. Municipal Policy Decrees Card
    card3_h = 122 if protest_e < 1.5 else 150
    c3_rect = (x + 8, cur_y, w - 16, card3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font_small.render("Municipal Policy Decrees:", True, ACCENT), (x + 16, cur_y + 8))

    d1_rect = (x + 16, cur_y + 26, w - 32, 26)
    _draw_gov_btn(surface, d1_rect, "Disburse Food Relief ($50)" if tile_cash >= 50 else "Disburse Food Relief ($50) [Short]", font_small, mx, my,
                  'city_emergency_food', region, enabled=True, icon_kind='food',
                  color=(120, 240, 150) if tile_cash >= 50 else (245, 180, 80),
                  world=world, region=region, nation=nation)

    d2_rect = (x + 16, cur_y + 56, w - 32, 26)
    _draw_gov_btn(surface, d2_rect, "Subsidize Farming ($100)" if tile_cash >= 100 else "Subsidize Farming ($100) [Short]", font_small, mx, my,
                  'city_farm_subsidy', region, enabled=True, icon_kind='farm',
                  color=(120, 240, 150) if tile_cash >= 100 else (245, 180, 80),
                  world=world, region=region, nation=nation)

    d3_rect = (x + 16, cur_y + 86, w - 32, 26)
    _draw_gov_btn(surface, d3_rect, "Deploy Safety Patrol ($60)" if tile_cash >= 60 else "Deploy Safety Patrol ($60) [Short]", font_small, mx, my,
                  'city_safety_patrol', region, enabled=True, icon_kind='shield',
                  color=(120, 240, 150) if tile_cash >= 60 else (245, 180, 80),
                  world=world, region=region, nation=nation)

    if protest_e >= 1.5:
        d4_rect = (x + 16, cur_y + 116, w - 32, 26)
        _draw_gov_btn(surface, d4_rect, "Enforce Police Curfew", font_small, mx, my,
                      'city_police_curfew', region, enabled=True, color=RED, icon_kind='shield',
                      world=world, region=region, nation=nation)

    cur_y += card3_h + 8

    # 4. Feudal Land Tenure & Enclosure Card (P1.4)
    tenure = getattr(region, 'tenure', None)
    if tenure and tenure.plots:
        card4_h = 74
        c4_rect = (x + 8, cur_y, w - 16, card4_h)
        pygame.draw.rect(surface, CARD_BG, c4_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, c4_rect, 1, border_radius=5)

        commons_pct = tenure.commons_access * 100
        surface.blit(font_small.render(f"Land Tenure: Commons Access {commons_pct:.0f}%", True, (235, 185, 80)), (x + 16, cur_y + 8))
        desc = f"Feudal: {tenure.feudal_fraction*100:.0f}%  •  Enclosed: {tenure.enclosed_fraction*100:.0f}%"
        surface.blit(font_small.render(desc, True, DIM), (x + 16, cur_y + 24))

        feudal_plots = tenure.feudal_plots()
        if feudal_plots:
            first_feudal = feudal_plots[0]
            from enclosure import calculate_charter_fee
            fee = calculate_charter_fee(first_feudal)
            lord = next((a for a in region.agents if a.id == first_feudal.lord_id), None)
            can_enclose = (lord is not None and lord.cash >= fee)
            enc_btn = (x + 16, cur_y + 44, w - 32, 22)
            _draw_gov_btn(surface, enc_btn, f"Enclose Feudal Plot (${fee:.0f})", font_small, mx, my,
                          'city_enclose_plot', (region, first_feudal.plot_id),
                          enabled=can_enclose, color=(240, 140, 70) if can_enclose else DIM,
                          world=world, region=region, nation=nation)
        else:
            surface.blit(font_small.render("Customary commons fully enclosed.", True, (130, 200, 140)), (x + 16, cur_y + 46))
        cur_y += card4_h + 8

    # 5. Ecological Regulations & Inputs Card (Phase 3)
    card5_h = 74
    c5_rect = (x + 8, cur_y, w - 16, card5_h)
    pygame.draw.rect(surface, CARD_BG, c5_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c5_rect, 1, border_radius=5)

    fert_on = getattr(region, 'use_fertilizer', False)
    pest_on = getattr(region, 'use_pesticides', False)
    surface.blit(font_small.render("Ecological Inputs & Chemical Agronomy:", True, (130, 215, 160)), (x + 16, cur_y + 8))
    desc_eco = f"Soil: {getattr(region, 'soil_fertility', 1.0)*100:.0f}% • Nut: {getattr(region, 'nutrition_density', 1.0)*100:.0f}% • Smog: {getattr(region, 'pollution_air', 0.0):.0f}"
    surface.blit(font_small.render(desc_eco, True, DIM), (x + 16, cur_y + 24))

    bw_half = (w - 38) // 2
    f_rect = (x + 16, cur_y + 44, bw_half, 22)
    p_rect = (x + 22 + bw_half, cur_y + 44, bw_half, 22)
    _draw_gov_btn(surface, f_rect, f"Fert: {'ON' if fert_on else 'OFF'}", font_small, mx, my,
                  'city_mandate_fertilizer', region, enabled=True, color=GREEN if fert_on else DIM,
                  world=world, region=region, nation=nation)
    _draw_gov_btn(surface, p_rect, f"Pest: {'ON' if pest_on else 'OFF'}", font_small, mx, my,
                  'city_mandate_pesticides', region, enabled=True, color=GREEN if pest_on else DIM,
                  world=world, region=region, nation=nation)


def _draw_left_province_scope(surface, world, region, province, nation, start_y, x, w, font, font_small, mx, my):
    """Render Province governance cards."""
    prov_gov = getattr(province, 'gov', None) if province else None
    prov_cash = prov_gov.agent.cash if prov_gov and hasattr(prov_gov, 'agent') else 0.0
    member_count = len(getattr(province, 'tiles', [])) if province else 1

    # 1. Provincial Administration Card
    card1_h = 76
    c1_rect = (x + 8, start_y, w - 16, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    p_name = province.name if province else "Province"
    surface.blit(get_icon('roads', 14), (x + 16, start_y + 8))
    surface.blit(font_small.render(f"Province: {p_name}", True, (245, 215, 120)), (x + 34, start_y + 7))
    surface.blit(font_small.render(f"Provincial Treasury: ${prov_cash:,.0f}", True, (120, 240, 150)), (x + 16, start_y + 26))
    surface.blit(font_small.render(f"Member Territories: {member_count} Cities / Tiles", True, (220, 230, 245)), (x + 16, start_y + 44))

    cur_y = start_y + card1_h + 8

    # 2. Provincial Strategic Actions Card
    card2_h = 118
    c2_rect = (x + 8, cur_y, w - 16, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Provincial Strategic Decrees:", True, ACCENT), (x + 16, cur_y + 8))

    p1_rect = (x + 16, cur_y + 26, w - 32, 26)
    _draw_gov_btn(surface, p1_rect, "Pave Regional Highway ($120)", font_small, mx, my,
                  'prov_pave_highway', province, enabled=(prov_cash >= 120.0), icon_kind='roads',
                  world=world, region=region, nation=nation, province=province)

    p2_rect = (x + 16, cur_y + 56, w - 32, 26)
    _draw_gov_btn(surface, p2_rect, "Regional Health Initiative ($150)", font_small, mx, my,
                  'prov_healthcare', province, enabled=(prov_cash >= 150.0), icon_kind='heart',
                  world=world, region=region, nation=nation, province=province)

    p3_rect = (x + 16, cur_y + 86, w - 32, 26)
    _draw_gov_btn(surface, p3_rect, "Provincial Equalization ($200)", font_small, mx, my,
                  'prov_equalization', province, enabled=(prov_cash >= 200.0), icon_kind='scale',
                  world=world, region=region, nation=nation, province=province)

    cur_y += card2_h + 8

    # 3. Logistics & Tax Harmonization Card
    card3_h = 104
    c3_rect = (x + 8, cur_y, w - 16, card3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font_small.render("Provincial Harmonization Accords:", True, (140, 200, 255)), (x + 16, cur_y + 8))

    r1_rect = (x + 16, cur_y + 26, w - 32, 22)
    _draw_gov_btn(surface, r1_rect, "Standardize Routes ($100)", font_small, mx, my,
                  'prov_standardize_routes', province, enabled=True, color=(200, 230, 150),
                  world=world, region=region, nation=nation, province=province)

    r2_rect = (x + 16, cur_y + 50, w - 32, 22)
    _draw_gov_btn(surface, r2_rect, "Harmonize Taxes (Uniform)", font_small, mx, my,
                  'prov_harmonize_taxes', province, enabled=True, color=(240, 200, 120),
                  world=world, region=region, nation=nation, province=province)

    r3_rect = (x + 16, cur_y + 74, w - 32, 22)
    _draw_gov_btn(surface, r3_rect, "Fund Soil Conservation ($150)", font_small, mx, my,
                  'prov_soil_conservation', province, enabled=(prov_cash >= 150.0), color=(140, 230, 170),
                  world=world, region=region, nation=nation, province=province)


def _draw_left_nation_scope(surface, world, region, nation, start_y, x, w, font, font_small, mx, my):
    """Render National Sovereign governance cards."""
    treasury = nation.treasury() if nation else {'total': 0.0, 'sovereign_cash': 0.0}
    nat_cash = treasury.get('sovereign_cash', 0.0)
    tot_cash = treasury.get('total', 0.0)

    from sovereign_bonds import get_bond_market
    market = get_bond_market()
    rating, market_yield = market.isrb.get_market_yield(nation, 20, world) if nation else ("N/A", 0.0)

    # 1. Sovereign Treasury & ISRB Rating Card
    card1_h = 74
    c1_rect = (x + 8, start_y, w - 16, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    n_name = nation.name if nation else "Sovereign State"
    surface.blit(get_icon('crown', 14), (x + 16, start_y + 8))
    surface.blit(font_small.render(f"Nation: {n_name}", True, (245, 215, 120)), (x + 34, start_y + 7))
    surface.blit(font_small.render(f"Treasury: ${nat_cash:,.0f} (Tot: ${tot_cash:,.0f})", True, (120, 240, 150)), (x + 16, start_y + 26))
    surface.blit(font_small.render(f"ISRB: {rating} • Yield: {market_yield*100:.2f}%/t", True, (220, 230, 245)), (x + 16, start_y + 44))

    cur_y = start_y + card1_h + 8

    # 2. National Strategic Decrees Card
    card2_h = 118
    c2_rect = (x + 8, cur_y, w - 16, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("National Strategic Decrees:", True, ACCENT), (x + 16, cur_y + 8))

    n1_rect = (x + 16, cur_y + 26, w - 32, 26)
    _draw_gov_btn(surface, n1_rect, "Fund Science Prize ($300)", font_small, mx, my,
                  'nat_science_prize', nation, enabled=(nat_cash >= 300.0), icon_kind='science',
                  world=world, region=region, nation=nation)

    n2_rect = (x + 16, cur_y + 56, w - 32, 26)
    _draw_gov_btn(surface, n2_rect, "Mobilize Standing Army ($250)", font_small, mx, my,
                  'nat_mobilize_army', nation, enabled=(nat_cash >= 250.0), icon_kind='sword',
                  world=world, region=region, nation=nation)

    n3_rect = (x + 16, cur_y + 86, w - 32, 26)
    _draw_gov_btn(surface, n3_rect, "Sovereign Equalization ($250)", font_small, mx, my,
                  'nat_sovereign_grant', nation, enabled=(nat_cash >= 250.0), icon_kind='scale',
                  world=world, region=region, nation=nation)

    cur_y += card2_h + 8

    # 3. Statutory Tax & Customs Tariffs Card
    card3_h = 76
    c3_rect = (x + 8, cur_y, w - 16, card3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font_small.render("Statutory Tax & Customs Tariffs:", True, (245, 180, 50)), (x + 16, cur_y + 6))

    tw = (w - 44) // 4
    for i, t_val in enumerate([10, 15, 25, 35]):
        bx = x + 16 + i * (tw + 4)
        _draw_gov_btn(surface, (bx, cur_y + 24, tw, 20), f"{t_val}%", font_small, mx, my,
                      f'nat_tax_{t_val}', nation, enabled=True,
                      world=world, region=region, nation=nation)

    for i, (tar_val, tar_lbl) in enumerate([(0, "0%"), (5, "5%"), (10, "10%"), (15, "15%")]):
        bx = x + 16 + i * (tw + 4)
        _draw_gov_btn(surface, (bx, cur_y + 48, tw, 20), tar_lbl, font_small, mx, my,
                      f'nat_tariff_{tar_val}', nation, enabled=True,
                      world=world, region=region, nation=nation)

    cur_y += card3_h + 8

    # 4. Labor Regulation & Social Directives Card
    card4_h = 170
    c4_rect = (x + 8, cur_y, w - 16, card4_h)
    pygame.draw.rect(surface, CARD_BG, c4_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c4_rect, 1, border_radius=5)

    surface.blit(font_small.render("Labor & Agrarian Legislation:", True, (240, 140, 80)), (x + 16, cur_y + 6))

    bw_half = (w - 38) // 2
    has_ten = getattr(nation, 'ten_hour_act', False) if nation else False
    has_safe = getattr(nation, 'factory_safety_act', False) if nation else False
    has_truck = getattr(nation, 'truck_act_enacted', False) if nation else False

    # Row 1: UBI and Open Borders
    _draw_gov_btn(surface, (x + 16, cur_y + 24, bw_half, 20), "Empire UBI", font_small, mx, my,
                  'nat_enact_ubi', nation, enabled=True, color=GREEN,
                  world=world, region=region, nation=nation)
    _draw_gov_btn(surface, (x + 22 + bw_half, cur_y + 24, bw_half, 20), "Borders", font_small, mx, my,
                  'nat_toggle_imm', nation, enabled=True, color=(160, 210, 255),
                  world=world, region=region, nation=nation)

    # Row 2: Ten-Hour Act and Safety Mandate
    _draw_gov_btn(surface, (x + 16, cur_y + 48, bw_half, 20), "Ten-Hour Act" if not has_ten else "Ten-Hour: PASS",
                  font_small, mx, my, 'nat_ten_hour_act', nation, enabled=not has_ten,
                  color=GREEN if has_ten else TEXT, world=world, region=region, nation=nation)
    _draw_gov_btn(surface, (x + 22 + bw_half, cur_y + 48, bw_half, 20), "Safety Mandate" if not has_safe else "Safety: PASS",
                  font_small, mx, my, 'nat_safety_mandate', nation, enabled=not has_safe,
                  color=GREEN if has_safe else TEXT, world=world, region=region, nation=nation)

    # Row 3: Anti-Truck Act (Abolish Scrip & Tommy Shops)
    _draw_gov_btn(surface, (x + 16, cur_y + 72, w - 32, 20), "Anti-Truck Act" if not has_truck else "Truck Act: PASS (Cash Only)",
                  font_small, mx, my, 'nat_truck_act', nation, enabled=not has_truck,
                  color=GREEN if has_truck else (255, 180, 100), world=world, region=region, nation=nation)

    # Row 4: Mass Spectacle / Entertainment
    _draw_gov_btn(surface, (x + 16, cur_y + 96, w - 32, 20), "Subsidize Spectacle ($50)", font_small, mx, my,
                  'nat_subsidize_entertainment', nation, enabled=True, color=(70, 195, 235),
                  world=world, region=region, nation=nation)

    # Row 5: Agrarian Commons & Insurgency Suppression
    _draw_gov_btn(surface, (x + 16, cur_y + 120, bw_half, 20), "Restore Commons",
                  font_small, mx, my, 'nat_restore_commons', nation, enabled=True,
                  color=(120, 220, 140), world=world, region=region, nation=nation)
    can_martial = any(getattr(u, 'soldiers', 0) > 0 for u in getattr(nation, 'military_units', [])) if nation else False
    _draw_gov_btn(surface, (x + 22 + bw_half, cur_y + 120, bw_half, 20), "Martial Law",
                  font_small, mx, my, 'nat_martial_law', nation, enabled=can_martial,
                  color=(240, 80, 80), world=world, region=region, nation=nation)

    # Row 6: Fertilizer Supply & War Economy
    is_rationed = any(getattr(r, 'fertilizer_rationing', False) for r in getattr(nation, 'tiles', [])) if nation else False
    _draw_gov_btn(surface, (x + 16, cur_y + 144, bw_half, 20), "Ration Fert" if not is_rationed else "Ration: ACTIVE",
                  font_small, mx, my, 'nat_fertilizer_rationing', nation, enabled=True,
                  color=(245, 180, 50) if is_rationed else TEXT, world=world, region=region, nation=nation)
    _draw_gov_btn(surface, (x + 22 + bw_half, cur_y + 144, bw_half, 20), "Import Guano ($100)",
                  font_small, mx, my, 'nat_subsidize_guano_import', nation, enabled=True,
                  color=(120, 240, 150), world=world, region=region, nation=nation)

    cur_y += card4_h + 8

    # 5. Electoral Struggle & Capitalist Backlash Barometer Card (Visualization 5)
    baro_h = 78
    baro_rect = (x + 8, cur_y, w - 16, baro_h)
    if mx >= 0 and my >= 0 and not world.get('_hovered_left_tooltip'):
        if baro_rect[0] <= mx <= baro_rect[0] + baro_rect[2] and baro_rect[1] <= my <= baro_rect[1] + baro_rect[3]:
            from worldview_tooltips import get_button_tooltip_data
            tdata = get_button_tooltip_data('gov_electoral_barometer', world, nation=nation)
            if tdata:
                tdata['btn_rect'] = baro_rect
                world['_hovered_left_tooltip'] = tdata
    from worldview_vis_radar import draw_electoral_barometer
    draw_electoral_barometer(surface, baro_rect, nation, font_small)


def gov_panel_hit(pos, world) -> bool:
    """Handle click interactions on the Left Governance Panel and registered buttons."""
    global _GOV_BUTTONS

    # Left Dock Buttons when closed
    from worldview_left_dock import left_dock_buttons_hit
    if not world.get('gov_panel_open', False):
        return left_dock_buttons_hit(pos, world)

    if world is not None:
        from ui_targets import find_target
        t = find_target(world, pos, scope='gov')
        if t is not None:
            if t.action == 'close_left':
                from worldview_left_dock import close_left_panels
                close_left_panels(world)
                return True
            elif isinstance(t.action, tuple) and t.action[0] == 'gov_scope':
                world['policy_scope'] = t.action[1]
                return True
            elif isinstance(t.action, tuple) and t.action[0] == 'gov_policy':
                _execute_gov_policy(world, t.action[1], t.data)
                return True

    # Legacy fallback calculation
    mx, my = pos
    x, y, w, h = GOV_PANEL_X, GOV_PANEL_Y, GOV_PANEL_W, GOV_PANEL_H

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    if close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18:
        from worldview_left_dock import close_left_panels
        close_left_panels(world)
        return True

    # Drawer Top Switcher
    from worldview_left_dock import drawer_top_tabs_hit
    if drawer_top_tabs_hit(pos, world, x, y + 48, w):
        return True

    # Scope Switcher Tabs
    pinned = world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    is_wilderness = (pinned is not None and getattr(pinned, 'owner_nation', None) is None)
    scopes = [('tile', 'Frontier'), ('nation', 'Sponsor')] if is_wilderness else [('tile', 'City'), ('province', 'Province'), ('nation', 'Nation')]
    tab_w = (w - 24) // len(scopes)
    scope_y = y + 80

    for i, (sc_id, _) in enumerate(scopes):
        tx = x + 8 + i * (tab_w + 4)
        if tx <= mx <= tx + tab_w and scope_y <= my <= scope_y + 24:
            world['policy_scope'] = sc_id
            return True

    # Check registered policy buttons
    for rect, act_id, target in _GOV_BUTTONS:
        bx, by, bw, bh = rect
        if bx <= mx <= bx + bw and by <= my <= by + bh:
            _execute_gov_policy(world, act_id, target)
            return True

    return False


def _execute_gov_policy(world: dict, act_id: str, target: any):
    """Execute triggered policy decree and notify world engine ticker."""
    t = world.get('turn', 1)
    from worldview_engine import ticker_push

    # 1. Custom City actions
    if act_id == 'city_toggle_ubi':
        rgov = getattr(target, 'gov', None)
        if not rgov:
            return
        pop_count = len([a for a in target.agents if not a.is_corporation and not a.is_government and a.alive])
        mandate_cost = pop_count * 50.0
        on_hand = (rgov.agent.cash if rgov else 0.0)
        if getattr(rgov, 'ubi_enabled', False):
            rgov.ubi_enabled = False
            rgov.ubi_mandate_turns_left = 0
            ticker_push(world, t, 'POLICY', f"Repealed Universal Basic Income in {target.name}.", (245, 180, 50))
            return
        elif on_hand >= mandate_cost:
            rgov.ubi_enabled = True
            rgov.ubi_mandate_turns_left = 10
            rgov.agent.cash -= mandate_cost
            ticker_push(world, t, 'POLICY', f"Enacted 10-Turn UBI in {target.name} (${mandate_cost:,.0f} budget committed).", (120, 240, 150))
            return
        else:
            nation = getattr(target, 'owner_nation', None)
            world['transfer_dialog'] = {
                'open': True,
                'action_kind': 'policy',
                'policy_id': 'city_toggle_ubi',
                'policy_name': f"Universal Basic Income (10-Turn Mandate, ${mandate_cost:,.0f})",
                'cost': mandate_cost,
                'on_hand': on_hand,
                'region': target,
                'nation': nation,
            }
            return

    if act_id == 'city_emergency_food':
        rgov = getattr(target, 'gov', None)
        if not rgov:
            return
        on_hand = rgov.agent.cash
        if on_hand >= 50.0:
            from worldview_policies import _execute_policy_action
            _execute_policy_action(world, 'city_food_relief', target)
        else:
            nation = getattr(target, 'owner_nation', None)
            world['transfer_dialog'] = {
                'open': True,
                'action_kind': 'policy',
                'policy_id': 'city_emergency_food',
                'policy_name': "Emergency Grain Relief ($50)",
                'cost': 50.0,
                'on_hand': on_hand,
                'region': target,
                'nation': nation,
            }
        return

    if act_id == 'city_farm_subsidy':
        rgov = getattr(target, 'gov', None)
        if not rgov:
            return
        on_hand = rgov.agent.cash
        if on_hand >= 100.0:
            rgov.agent.cash -= 100.0
            ticker_push(world, t, 'POLICY', f"Granted $100 Agricultural Subsidy to farms in {target.name}.", (120, 220, 140))
        else:
            nation = getattr(target, 'owner_nation', None)
            world['transfer_dialog'] = {
                'open': True,
                'action_kind': 'policy',
                'policy_id': 'city_farm_subsidy',
                'policy_name': "Agricultural Development Subsidy ($100)",
                'cost': 100.0,
                'on_hand': on_hand,
                'region': target,
                'nation': nation,
            }
        return

    if act_id == 'city_safety_patrol':
        rgov = getattr(target, 'gov', None)
        if not rgov:
            return
        on_hand = rgov.agent.cash
        if on_hand >= 60.0:
            rgov.agent.cash -= 60.0
            from imperialism import _disburse_agent_funds
            _disburse_agent_funds(world, getattr(target, 'owner_nation', None), 60.0)
            target.police_officers = max(getattr(target, 'police_officers', 0), 5)
            if target.protest_energy_log:
                target.protest_energy_log[-1] = max(0.0, target.protest_energy_log[-1] - 0.40)
            ticker_push(world, t, 'POLICY', f"Deployed Public Safety Patrols in {target.name} (5 constables on duty, -0.40 Protest).", (120, 220, 140))
        else:
            nation = getattr(target, 'owner_nation', None)
            world['transfer_dialog'] = {
                'open': True,
                'action_kind': 'policy',
                'policy_id': 'city_safety_patrol',
                'policy_name': "Constabulary Safety Patrol ($60)",
                'cost': 60.0,
                'on_hand': on_hand,
                'region': target,
                'nation': nation,
            }
        return

    # 2. Custom Province actions
    if act_id == 'prov_pave_highway':
        prov_gov = getattr(target, 'gov', None)
        on_hand = prov_gov.agent.cash if prov_gov and hasattr(prov_gov, 'agent') else 0.0
        if on_hand >= 120.0:
            prov_gov.agent.cash -= 120.0
            ticker_push(world, t, 'POLICY', f"Provincial Administration funded $120 Highway Maintenance in {target.name}.", (120, 220, 140))
        else:
            pinned = world.get('selected_region')
            nation = getattr(pinned, 'owner_nation', None)
            world['transfer_dialog'] = {
                'open': True,
                'action_kind': 'policy',
                'policy_id': 'prov_pave_highway',
                'policy_name': f"Pave Regional Highway in {target.name} ($120)",
                'cost': 120.0,
                'on_hand': on_hand,
                'region': pinned,
                'nation': nation,
            }
        return

    if act_id == 'prov_healthcare':
        prov_gov = getattr(target, 'gov', None)
        on_hand = prov_gov.agent.cash if prov_gov and hasattr(prov_gov, 'agent') else 0.0
        if on_hand >= 150.0:
            prov_gov.agent.cash -= 150.0
            ticker_push(world, t, 'POLICY', f"Provincial Administration launched $150 Healthcare Program in {target.name}.", (120, 220, 140))
        else:
            pinned = world.get('selected_region')
            nation = getattr(pinned, 'owner_nation', None)
            world['transfer_dialog'] = {
                'open': True,
                'action_kind': 'policy',
                'policy_id': 'prov_healthcare',
                'policy_name': f"Provincial Health & Sanitation in {target.name} ($150)",
                'cost': 150.0,
                'on_hand': on_hand,
                'region': pinned,
                'nation': nation,
            }
        return

    if act_id == 'prov_equalization':
        from intents import execute_equalization_grant
        pinned = world.get('selected_region')
        nation = getattr(pinned, 'owner_nation', None)
        nat_name = nation.name if nation else ""
        reg_name = pinned.name if pinned else ""
        execute_equalization_grant(world, nat_name, reg_name, 'provincial_pool', 200.0, t)
        return

    # 3. Custom Nation actions
    if act_id == 'nat_science_prize':
        nat_gov = getattr(target, 'government', None)
        if nat_gov and nat_gov.agent.cash >= 300.0:
            nat_gov.agent.cash -= 300.0
            ticker_push(world, t, 'INNOVATION', f"{target.name} funded a $300 Sovereign Science Grant.", (80, 200, 255))
        return

    if act_id == 'nat_mobilize_army':
        pinned = world.get('selected_region')
        reg_name = pinned.name if pinned else target.tiles[0].name
        from intents import RecruitArmyIntent
        intent = RecruitArmyIntent(target.name, reg_name, 15, wage=1.0, submitted_turn=t, regime_type=target.regime_type)
        target.submit_intent(intent, t)
        ticker_push(world, t, 'MILITARY', f"Mobilized standing army division in {reg_name}.", (240, 100, 100))
        return

    if act_id == 'nat_sovereign_grant':
        from intents import execute_equalization_grant
        pinned = world.get('selected_region')
        reg_name = pinned.name if pinned else target.tiles[0].name
        execute_equalization_grant(world, target.name, reg_name, 'national_sovereign', 250.0, t)
        return

    # 4. Delegate to worldview_policies for all standard policy actions
    from worldview_policies import _execute_policy_action
    _execute_policy_action(world, act_id, target)
