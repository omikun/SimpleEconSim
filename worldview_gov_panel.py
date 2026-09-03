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

GOV_PANEL_X = 14
GOV_PANEL_Y = TOP_BAR_H + 10
GOV_PANEL_W = 286
GOV_PANEL_H = HEIGHT - TOP_BAR_H - TICKER_H - 18

CARD_BG = (24, 26, 36)
CARD_BORDER = (45, 50, 70)
BTN_BG = (36, 42, 58)
BTN_HOVER = (52, 60, 84)
BTN_BORDER = (70, 85, 115)


def draw_left_dock_buttons(surface, world, font_small, mouse_pos=None):
    """Draw the floating left dock toggle buttons for all left-hand panels."""
    from worldview_left_dock import draw_left_dock_buttons as _draw_dock
    _draw_dock(surface, world, font_small, mouse_pos)


def draw_gov_panel(surface, world, font, font_small, mouse_pos=None):
    """Draw the left-hand Governance & Policies Panel for the selected tile/province/nation."""
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
    prov_name = province.name if province else "Province"
    nat_name = nation.name if nation else "Wilderness"

    # Header
    g_icon = get_icon('municipal', 16)
    surface.blit(g_icon, (x + 12, y + 12))

    head_txt = font.render(f"Governance: {city_name}", True, (245, 215, 110))
    surface.blit(head_txt, (x + 32, y + 10))

    sub_txt = font_small.render(f"{prov_name} • {nat_name}", True, DIM)
    surface.blit(sub_txt, (x + 32, y + 30))

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
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
    scopes = [('tile', 'City', 'municipal'), ('province', 'Province', 'roads'), ('nation', 'Nation', 'crown')]
    tab_w = (w - 24) // 3

    for i, (sc_id, sc_label, sc_ico) in enumerate(scopes):
        tx = x + 8 + i * (tab_w + 4)
        t_rect = (tx, scope_y, tab_w, 24)
        is_sel = (active_scope == sc_id)
        is_hov = t_rect[0] <= mx <= t_rect[0] + tab_w and t_rect[1] <= my <= t_rect[1] + 24

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
    if active_scope == 'tile':
        _draw_left_city_scope(surface, world, pinned, nation, cur_y, x, w, font, font_small, mx, my)
    elif active_scope == 'province':
        _draw_left_province_scope(surface, world, pinned, province, nation, cur_y, x, w, font, font_small, mx, my)
    else:
        _draw_left_nation_scope(surface, world, pinned, nation, cur_y, x, w, font, font_small, mx, my)


def _draw_btn(surface, rect, label, font_small, mx, my, enabled=True, color=TEXT, custom_bg=None, icon_kind=None):
    bx, by, bw, bh = rect
    is_hov = (bx <= mx <= bx + bw and by <= my <= by + bh) and enabled
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


def _draw_left_city_scope(surface, world, region, nation, start_y, x, w, font, font_small, mx, my):
    """Render City / Tile governance cards."""
    rgov = getattr(region, 'gov', None)
    tile_cash = (rgov.agent.cash if rgov else 0.0) + (region.bank.deposits.get(rgov.agent, 0.0) if hasattr(region, 'bank') and rgov else 0.0)
    tax_rate = rgov.tax_rate if rgov else 0.15
    hungry = sum(1 for a in region.agents if not a.is_corporation and not a.is_government and a.hungry_steps > 0)
    protest_e = region.protest_energy_log[-1] if region.protest_energy_log else 0.0
    ubi_active = getattr(rgov, 'ubi_active', False)

    # 1. Municipal Treasury & Stats Card
    card1_h = 76
    c1_rect = (x + 8, start_y, w - 16, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    m_ico = get_icon('municipal', 14)
    surface.blit(m_ico, (x + 16, start_y + 8))
    surface.blit(font_small.render(f"Municipal Treasury: ${tile_cash:,.0f}", True, (120, 240, 150)), (x + 34, start_y + 7))
    surface.blit(font_small.render(f"Tax Rate: {tax_rate*100:.1f}%  •  Protest Energy: {protest_e:.2f}", True, (220, 230, 245)), (x + 16, start_y + 26))
    food_inv = getattr(rgov, 'food_inventory', getattr(rgov, 'food_reserve', 0.0)) if rgov else 0.0
    surface.blit(font_small.render(f"Hungry Citizens: {hungry}  •  Food Inventory: {food_inv:.1f}", True, (245, 180, 80)), (x + 16, start_y + 44))

    cur_y = start_y + card1_h + 10

    # 2. Tax Adjusters & UBI Card
    card2_h = 80
    c2_rect = (x + 8, cur_y, w - 16, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Fiscal Taxation & Welfare:", True, (245, 215, 120)), (x + 16, cur_y + 8))

    b1_rect = (x + 16, cur_y + 28, 80, 22)
    b2_rect = (x + 102, cur_y + 28, 80, 22)
    _draw_btn(surface, b1_rect, "[-2% Tax]", font_small, mx, my, enabled=(tax_rate > 0.02))
    _draw_btn(surface, b2_rect, "[+2% Tax]", font_small, mx, my, enabled=(tax_rate < 0.60))

    b3_rect = (x + 16, cur_y + 52, w - 32, 22)
    ubi_lbl = "UBI Welfare: Active ($5/t)" if ubi_active else "Enact UBI Welfare ($5/t)"
    _draw_btn(surface, b3_rect, ubi_lbl, font_small, mx, my, enabled=True, color=(120, 240, 150) if ubi_active else TEXT)

    cur_y += card2_h + 10

    # 3. Municipal Policy Decrees Card
    card3_h = 135
    c3_rect = (x + 8, cur_y, w - 16, card3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font_small.render("Municipal Policy Decrees:", True, ACCENT), (x + 16, cur_y + 8))

    # Decree 1: Emergency Food Rations ($50)
    d1_rect = (x + 16, cur_y + 28, w - 32, 28)
    _draw_btn(surface, d1_rect, "Disburse Food Relief ($50)", font_small, mx, my, enabled=(tile_cash >= 50.0), icon_kind='food')

    # Decree 2: Agricultural Subsidy ($100)
    d2_rect = (x + 16, cur_y + 60, w - 32, 28)
    _draw_btn(surface, d2_rect, "Subsidize Farming ($100)", font_small, mx, my, enabled=(tile_cash >= 100.0), icon_kind='farm')

    # Decree 3: Law Enforcement & Anti-Riot Patrol ($60)
    d3_rect = (x + 16, cur_y + 92, w - 32, 28)
    _draw_btn(surface, d3_rect, "Deploy Safety Patrol ($60)", font_small, mx, my, enabled=(tile_cash >= 60.0), icon_kind='shield')


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
    p_ico = get_icon('roads', 14)
    surface.blit(p_ico, (x + 16, start_y + 8))
    surface.blit(font_small.render(f"Province: {p_name}", True, (245, 215, 120)), (x + 34, start_y + 7))
    surface.blit(font_small.render(f"Provincial Treasury: ${prov_cash:,.0f}", True, (120, 240, 150)), (x + 16, start_y + 26))
    surface.blit(font_small.render(f"Member Territories: {member_count} Cities / Tiles", True, (220, 230, 245)), (x + 16, start_y + 44))

    cur_y = start_y + card1_h + 10

    # 2. Provincial Decrees Card
    card2_h = 160
    c2_rect = (x + 8, cur_y, w - 16, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Provincial Strategic Actions:", True, ACCENT), (x + 16, cur_y + 8))

    # Decree 1: Maintain Highway Network ($120)
    p1_rect = (x + 16, cur_y + 28, w - 32, 28)
    _draw_btn(surface, p1_rect, "Pave Regional Highway ($120)", font_small, mx, my, enabled=(prov_cash >= 120.0), icon_kind='roads')

    # Decree 2: Regional Healthcare ($150)
    p2_rect = (x + 16, cur_y + 60, w - 32, 28)
    _draw_btn(surface, p2_rect, "Regional Health Initiative ($150)", font_small, mx, my, enabled=(prov_cash >= 150.0), icon_kind='heart')

    # Decree 3: Provincial Equalization Fund ($200)
    p3_rect = (x + 16, cur_y + 92, w - 32, 28)
    _draw_btn(surface, p3_rect, "Provincial Equalization ($200)", font_small, mx, my, enabled=(prov_cash >= 200.0), icon_kind='scale')

    # Subtext
    sub_desc = font_small.render("Funded via 30% statutory provincial tax share.", True, DIM)
    surface.blit(sub_desc, (x + 16, cur_y + 130))


def _draw_left_nation_scope(surface, world, region, nation, start_y, x, w, font, font_small, mx, my):
    """Render National Sovereign governance cards."""
    nat_gov = getattr(nation, 'government', None) if nation else None
    treasury = nation.treasury() if nation else {'total': 0.0, 'sovereign_cash': 0.0}
    nat_cash = treasury.get('sovereign_cash', 0.0)
    tot_cash = treasury.get('total', 0.0)

    from sovereign_bonds import get_bond_market
    market = get_bond_market()
    rating, market_yield = market.isrb.get_market_yield(nation, 20, world) if nation else ("N/A", 0.0)

    # 1. Sovereign Treasury & ISRB Rating Card
    card1_h = 76
    c1_rect = (x + 8, start_y, w - 16, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    n_name = nation.name if nation else "Sovereign State"
    n_ico = get_icon('crown', 14)
    surface.blit(n_ico, (x + 16, start_y + 8))
    surface.blit(font_small.render(f"Nation: {n_name}", True, (245, 215, 120)), (x + 34, start_y + 7))
    surface.blit(font_small.render(f"Sovereign Treasury: ${nat_cash:,.0f} (Tot: ${tot_cash:,.0f})", True, (120, 240, 150)), (x + 16, start_y + 26))
    surface.blit(font_small.render(f"ISRB Rating: {rating}  •  Yield: {market_yield*100:.2f}%/t", True, (220, 230, 245)), (x + 16, start_y + 44))

    cur_y = start_y + card1_h + 10

    # 2. National Strategic Decrees Card
    card2_h = 160
    c2_rect = (x + 8, cur_y, w - 16, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("National Sovereign Decrees:", True, ACCENT), (x + 16, cur_y + 8))

    # Decree 1: National Research Bounty ($300)
    n1_rect = (x + 16, cur_y + 28, w - 32, 28)
    _draw_btn(surface, n1_rect, "Fund Science Prize ($300)", font_small, mx, my, enabled=(nat_cash >= 300.0), icon_kind='science')

    # Decree 2: Recruit & Mobilize Garrison ($250)
    n2_rect = (x + 16, cur_y + 60, w - 32, 28)
    _draw_btn(surface, n2_rect, "Mobilize Standing Army ($250)", font_small, mx, my, enabled=(nat_cash >= 250.0), icon_kind='sword')

    # Decree 3: Sovereign Fiscal Equalization ($250)
    n3_rect = (x + 16, cur_y + 92, w - 32, 28)
    _draw_btn(surface, n3_rect, "Disburse Sovereign Grant ($250)", font_small, mx, my, enabled=(nat_cash >= 250.0), icon_kind='scale')

    # Subtext
    sub_desc = font_small.render("Funded via 50% state tax + 80% customs tariffs.", True, DIM)
    surface.blit(sub_desc, (x + 16, cur_y + 130))


def gov_panel_hit(pos, world) -> bool:
    """Handle click interactions on the Left Governance Panel and Left Dock Buttons."""
    mx, my = pos
    x, y, w, h = GOV_PANEL_X, GOV_PANEL_Y, GOV_PANEL_W, GOV_PANEL_H
    t = world.get('turn', 1)

    build_open = world.get('build_panel_open', False)
    gov_open = world.get('gov_panel_open', False)

    # 1. Left Dock Button Clicks (when panels are closed)
    from worldview_left_dock import left_dock_buttons_hit, open_left_panel
    if not gov_open:
        if left_dock_buttons_hit(pos, world):
            return True
        return False

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

    # Scope Switcher Tabs (new layout at y + 80, legacy at y + 50)
    tab_w = (w - 24) // 3
    for scope_y_test in (y + 48 + 24 + 8, y + 50):
        for i, (sc_id, _) in enumerate([('tile', 'City'), ('province', 'Province'), ('nation', 'Nation')]):
            tx = x + 8 + i * (tab_w + 4)
            if tx <= mx <= tx + tab_w and scope_y_test <= my <= scope_y_test + 24:
                world['policy_scope'] = sc_id
                return True

    pinned = world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    if pinned is None:
        return False

    nation = getattr(pinned, 'owner_nation', None)
    province = getattr(pinned, 'province', None)
    rgov = getattr(pinned, 'gov', None)
    prov_gov = getattr(province, 'gov', None) if province else None
    nat_gov = getattr(nation, 'government', None) if nation else None
    active_scope = world.get('policy_scope', 'tile')

    for base_scope_y in (y + 48 + 24 + 8, y + 50):
        scope_y = base_scope_y
        cur_y = scope_y + 32

        # --- CITY / TILE SCOPE CLICKS ---
        if active_scope == 'tile' and rgov:
            card1_h = 76
            start_y = cur_y
            tax_card_y = start_y + card1_h + 10

            # [-2% Tax]
            b1_rect = (x + 16, tax_card_y + 28, 80, 22)
            if b1_rect[0] <= mx <= b1_rect[0] + 80 and b1_rect[1] <= my <= b1_rect[1] + 22:
                rgov.tax_rate = max(0.02, round(rgov.tax_rate - 0.02, 3))
                from worldview_engine import ticker_push
                ticker_push(world, t, 'POLICY', f"Decreed Tax Cut in {pinned.name}: New Rate {rgov.tax_rate*100:.1f}%.", (120, 220, 140))
                return True

            # [+2% Tax]
            b2_rect = (x + 102, tax_card_y + 28, 80, 22)
            if b2_rect[0] <= mx <= b2_rect[0] + 80 and b2_rect[1] <= my <= b2_rect[1] + 22:
                rgov.tax_rate = min(0.60, round(rgov.tax_rate + 0.02, 3))
                from worldview_engine import ticker_push
                ticker_push(world, t, 'POLICY', f"Decreed Tax Hike in {pinned.name}: New Rate {rgov.tax_rate*100:.1f}%.", (245, 180, 50))
                return True

            # UBI Toggle
            b3_rect = (x + 16, tax_card_y + 52, w - 32, 22)
            if b3_rect[0] <= mx <= b3_rect[0] + w - 32 and b3_rect[1] <= my <= b3_rect[1] + 22:
                rgov.ubi_active = not getattr(rgov, 'ubi_active', False)
                status_str = "enacted" if rgov.ubi_active else "repealed"
                from worldview_engine import ticker_push
                ticker_push(world, t, 'POLICY', f"Universal Basic Income {status_str} in {pinned.name}.", (120, 220, 140) if rgov.ubi_active else (240, 80, 80))
                return True

            # Decrees
            dec_card_y = tax_card_y + 80 + 10

            # Food Relief ($50)
            d1_rect = (x + 16, dec_card_y + 28, w - 32, 28)
            if d1_rect[0] <= mx <= d1_rect[0] + w - 32 and d1_rect[1] <= my <= d1_rect[1] + 28:
                if rgov.agent.cash >= 50.0:
                    rgov.agent.cash -= 50.0
                    rgov.food_inventory += 20.0
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'POLICY', f"Disbursed $50 Emergency Food Rations in {pinned.name}.", (120, 220, 140))
                return True

            # Subsidize Farming ($100)
            d2_rect = (x + 16, dec_card_y + 60, w - 32, 28)
            if d2_rect[0] <= mx <= d2_rect[0] + w - 32 and d2_rect[1] <= my <= d2_rect[1] + 28:
                if rgov.agent.cash >= 100.0:
                    rgov.agent.cash -= 100.0
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'POLICY', f"Granted $100 Agricultural Subsidy to farms in {pinned.name}.", (120, 220, 140))
                return True

            # Law Enforcement / Safety Patrol ($60)
            d3_rect = (x + 16, dec_card_y + 92, w - 32, 28)
            if d3_rect[0] <= mx <= d3_rect[0] + w - 32 and d3_rect[1] <= my <= d3_rect[1] + 28:
                if rgov.agent.cash >= 60.0:
                    rgov.agent.cash -= 60.0
                    if pinned.protest_energy_log:
                        pinned.protest_energy_log[-1] = max(0.0, pinned.protest_energy_log[-1] - 0.40)
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'POLICY', f"Deployed Public Safety Patrols in {pinned.name} (-0.40 Protest).", (120, 220, 140))
                return True

        # --- PROVINCE SCOPE CLICKS ---
        elif active_scope == 'province' and prov_gov:
            card1_h = 76
            dec_card_y = cur_y + card1_h + 10

            # Pave Highway ($120)
            p1_rect = (x + 16, dec_card_y + 28, w - 32, 28)
            if p1_rect[0] <= mx <= p1_rect[0] + w - 32 and p1_rect[1] <= my <= p1_rect[1] + 28:
                if prov_gov.agent.cash >= 120.0:
                    prov_gov.agent.cash -= 120.0
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'POLICY', f"Provincial Administration funded $120 Highway Maintenance in {province.name}.", (120, 220, 140))
                return True

            # Health Initiative ($150)
            p2_rect = (x + 16, dec_card_y + 60, w - 32, 28)
            if p2_rect[0] <= mx <= p2_rect[0] + w - 32 and p2_rect[1] <= my <= p2_rect[1] + 28:
                if prov_gov.agent.cash >= 150.0:
                    prov_gov.agent.cash -= 150.0
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'POLICY', f"Provincial Administration launched $150 Healthcare Program in {province.name}.", (120, 220, 140))
                return True

            # Provincial Equalization ($200)
            p3_rect = (x + 16, dec_card_y + 92, w - 32, 28)
            if p3_rect[0] <= mx <= p3_rect[0] + w - 32 and p3_rect[1] <= my <= p3_rect[1] + 28:
                from intents import execute_equalization_grant
                execute_equalization_grant(world, nation.name, pinned.name, 'provincial_pool', 200.0, t)
                return True

        # --- NATION SCOPE CLICKS ---
        elif active_scope == 'nation' and nat_gov and nation:
            card1_h = 76
            dec_card_y = cur_y + card1_h + 10

            # Fund Science Prize ($300)
            n1_rect = (x + 16, dec_card_y + 28, w - 32, 28)
            if n1_rect[0] <= mx <= n1_rect[0] + w - 32 and n1_rect[1] <= my <= n1_rect[1] + 28:
                if nat_gov.agent.cash >= 300.0:
                    nat_gov.agent.cash -= 300.0
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'INNOVATION', f"{nation.name} funded a $300 Sovereign Science Grant.", (80, 200, 255))
                return True

            # Mobilize Garrison ($250)
            n2_rect = (x + 16, dec_card_y + 60, w - 32, 28)
            if n2_rect[0] <= mx <= n2_rect[0] + w - 32 and n2_rect[1] <= my <= n2_rect[1] + 28:
                from intents import RecruitArmyIntent
                intent = RecruitArmyIntent(nation.name, pinned.name, 15, wage=1.0, submitted_turn=t, regime_type=nation.regime_type)
                nation.submit_intent(intent, t)
                return True

            # Sovereign Fiscal Equalization ($250)
            n3_rect = (x + 16, dec_card_y + 92, w - 32, 28)
            if n3_rect[0] <= mx <= n3_rect[0] + w - 32 and n3_rect[1] <= my <= n3_rect[1] + 28:
                from intents import execute_equalization_grant
                execute_equalization_grant(world, nation.name, pinned.name, 'national_sovereign', 250.0, t)
                return True

    return False

    return False
