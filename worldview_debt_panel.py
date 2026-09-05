"""
worldview_debt_panel.py — Left Drawer for Sovereign Debt, ISRB Rating Bureau & Bond Market.

Duplicates cross-nation sovereign debt functionality from the Sovereign Actions modal:
- Scope Switcher: [Domestic & ISRB] and [Foreign Reserves & Bonds].
- International Sovereign Rating Bureau (ISRB):
  - Credit Rating (AAA..D) and benchmark per-turn yield.
  - Board Member status and rating modifiers.
  - Diplomatic influence actions: Lobby Upgrade ($200), Audit Rival ($350), Board Seat ($600).
- Domestic Sovereign Debt Issuance:
  - Maturity term selector (20, 50, 100 turns).
  - 1-Turn Advance Announcement offerings ($500 / $1,000 tranches).
  - Outstanding debt and per-turn coupon servicing obligations.
- Cross-Border Bond Market & Reserves:
  - Portfolio of foreign bonds held and passive per-turn coupon income.
  - Purchase foreign sovereign debt to accumulate foreign currency reserves.
"""

from __future__ import annotations
import pygame
from worldview_camera import HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon
from sovereign_bonds import get_bond_market
from intents import IssueSovereignBondIntent
from worldview_left_dock import (
    PANEL_X, PANEL_Y, PANEL_W, PANEL_H,
    draw_drawer_top_tabs, drawer_top_tabs_hit,
    open_left_panel, close_left_panels
)
from worldview_engine import ticker_push

CARD_BG = (24, 26, 36)
CARD_BORDER = (45, 50, 70)
BTN_BG = (36, 42, 58)
BTN_HOVER = (52, 60, 84)
BTN_BORDER = (70, 85, 115)


def _get_active_nation(world: dict):
    nations = world.get('nations', [])
    pinned = world.get('selected_region')
    if pinned is not None and getattr(pinned, 'owner_nation', None) is not None:
        return pinned.owner_nation
    active_name = world.get('player_nation_name')
    if active_name:
        for n in nations:
            if n.name == active_name:
                return n
    if world.get('selected_nation') is not None:
        return world['selected_nation']
    return nations[0] if nations else None


def _draw_btn(surface, rect, label, font_small, mx, my, enabled=True, color=TEXT, custom_bg=None, icon_kind=None,
              btn_id: str = None, world: dict = None, nation=None):
    bx, by, bw, bh = rect
    is_hov = (bx <= mx <= bx + bw and by <= my <= by + bh) and enabled
    if is_hov and btn_id and world is not None:
        from worldview_tooltips import get_button_tooltip_data
        tdata = get_button_tooltip_data(btn_id, world, nation=nation)
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


def draw_debt_panel(surface: pygame.Surface, world: dict, font: pygame.font.Font,
                    font_small: pygame.font.Font, mouse_pos=None) -> None:
    """Draw the Left Sovereign Debt & Bonds Drawer Panel."""
    if not world.get('debt_panel_open', False):
        return

    world['layers_collapsed'] = True
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H

    active_n = _get_active_nation(world)
    if not active_n:
        return

    market = get_bond_market()
    isrb = market.isrb

    selected_duration = world.get('bond_duration_selected', 20)
    rating, market_yield = isrb.get_market_yield(active_n, selected_duration, world)
    has_board_seat = active_n.name in isrb.board_seats
    active_mod = isrb.rating_modifiers.get(active_n.name, 0)
    gov_cash = active_n.government.agent.cash if hasattr(active_n, 'government') and active_n.government else 0.0

    total_debt = sum(b.principal for b in market.get_bonds_owed_by(active_n.name))
    servicing_cost = sum(b.per_turn_coupon for b in market.get_bonds_owed_by(active_n.name))
    foreign_reserves = sum(b.principal for b in market.get_bonds_held_by(active_n.name))
    passive_income = sum(b.per_turn_coupon for b in market.get_bonds_held_by(active_n.name))

    # Background frame
    panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    panel_surf.fill((16, 18, 26, 245))
    surface.blit(panel_surf, (x, y))
    pygame.draw.rect(surface, (65, 70, 90), (x, y, w, h), 1, border_radius=8)

    # Header
    s_icon = get_icon('scale', 16)
    surface.blit(s_icon, (x + 12, y + 12))
    surface.blit(font.render(f"Debt: {active_n.name}", True, ACCENT), (x + 32, y + 10))
    surface.blit(font_small.render(f"Treasury: ${gov_cash:,.0f} {active_n.currency}", True, DIM), (x + 32, y + 30))

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    hc = close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18
    pygame.draw.rect(surface, (60, 60, 80) if hc else (35, 35, 48), close_rect, border_radius=3)
    x_txt = font_small.render("×", True, (255, 255, 255) if hc else DIM)
    surface.blit(x_txt, (close_rect[0] + 4, close_rect[1] + 1))

    # Drawer Top Switcher Tabs
    cur_y = draw_drawer_top_tabs(surface, world, x, y + 48, w, 'debt', font_small, mouse_pos)

    # Sub-scope Switcher: Domestic & ISRB vs Foreign Reserves
    scope = world.get('debt_scope', 'domestic')
    scopes = [('domestic', 'Domestic & ISRB'), ('foreign', 'Foreign Reserves')]
    sc_w = (w - 28) // 2
    for i, (s_id, s_lbl) in enumerate(scopes):
        sx = x + 10 + i * (sc_w + 8)
        s_rect = (sx, cur_y, sc_w, 24)
        is_sel = (scope == s_id)
        is_hov = s_rect[0] <= mx <= s_rect[0] + sc_w and s_rect[1] <= my <= s_rect[1] + 24
        if is_hov and world is not None:
            from worldview_tooltips import get_button_tooltip_data
            tdata = get_button_tooltip_data(f"debt_scope_{s_id}", world, nation=active_n)
            if tdata:
                tdata['btn_rect'] = s_rect
                world['_hovered_left_tooltip'] = tdata

        bg = (52, 72, 100) if is_sel else ((38, 42, 56) if is_hov else (24, 26, 36))
        pygame.draw.rect(surface, bg, s_rect, border_radius=4)
        pygame.draw.rect(surface, ACCENT if is_sel else (60, 65, 80), s_rect, 1, border_radius=4)
        tsurf = font_small.render(s_lbl, True, (255, 255, 255) if is_sel else TEXT)
        surface.blit(tsurf, tsurf.get_rect(center=(sx + sc_w // 2, cur_y + 12)))

    cur_y += 32

    if scope == 'domestic':
        # 1. ISRB Rating Bureau Card
        card1_h = 160
        c1_rect = (x + 8, cur_y, w - 16, card1_h)
        pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

        surface.blit(font.render("ISRB Credit Bureau", True, (245, 215, 110)), (x + 16, cur_y + 8))

        rating_color = (120, 240, 150) if rating in ('AAA', 'AA') else ((245, 205, 70) if rating in ('A', 'BBB') else (240, 90, 90))
        surface.blit(font.render(f"Rating: {rating}", True, rating_color), (x + 16, cur_y + 30))

        seat_str = "✓ Board Member" if has_board_seat else "Standard Member"
        surface.blit(font_small.render(f"Base Yield: {market_yield*100:.2f}%/t • {seat_str}", True, TEXT), (x + 16, cur_y + 54))
        surface.blit(font_small.render(f"Rating Modifier: {'+' if active_mod > 0 else ''}{active_mod}", True, DIM), (x + 16, cur_y + 70))

        # Influence Actions
        btn_w = w - 32
        btn_h = 22
        by = cur_y + 90

        can_lobby = gov_cash >= 200.0
        _draw_btn(surface, (x + 16, by, btn_w, btn_h), "Lobby Upgrade ($200)", font_small, mx, my,
                  enabled=can_lobby, color=(120, 240, 150),
                  btn_id='debt_lobby_isrb', world=world, nation=active_n)
        by += btn_h + 4

        can_audit = gov_cash >= 350.0
        _draw_btn(surface, (x + 16, by, btn_w, btn_h), "Audit Rival ($350)", font_small, mx, my,
                  enabled=can_audit, color=(245, 180, 50),
                  btn_id='debt_audit_rival', world=world, nation=active_n)
        by += btn_h + 4

        can_seat = gov_cash >= 600.0 and not has_board_seat
        _draw_btn(surface, (x + 16, by, btn_w, btn_h), "Board Seat ($600)" if not has_board_seat else "✓ Board Seat Owned", font_small, mx, my,
                  enabled=can_seat, color=(80, 200, 255),
                  btn_id='debt_board_seat', world=world, nation=active_n)

        cur_y += card1_h + 10

        # 2. Domestic Sovereign Debt Issuance Card
        card2_h = 220
        c2_rect = (x + 8, cur_y, w - 16, card2_h)
        pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

        surface.blit(font.render("Issue Sovereign Bonds", True, (245, 215, 110)), (x + 16, cur_y + 8))
        surface.blit(font_small.render("Term Duration:", True, DIM), (x + 16, cur_y + 32))

        # Term duration selectors (20t, 50t, 100t)
        terms = [20, 50, 100]
        term_w = (w - 48) // 3
        for i, t_val in enumerate(terms):
            tx = x + 16 + i * (term_w + 6)
            t_rect = (tx, cur_y + 48, term_w, 22)
            is_sel = (selected_duration == t_val)
            is_hov = t_rect[0] <= mx <= t_rect[0] + term_w and t_rect[1] <= my <= t_rect[1] + 22
            if is_hov and world is not None:
                from worldview_tooltips import get_button_tooltip_data
                tdata = get_button_tooltip_data(f"debt_dur_{t_val}", world, nation=active_n)
                if tdata:
                    tdata['btn_rect'] = t_rect
                    world['_hovered_left_tooltip'] = tdata

            bg = (52, 72, 100) if is_sel else ((38, 42, 56) if is_hov else (26, 28, 38))
            pygame.draw.rect(surface, bg, t_rect, border_radius=3)
            pygame.draw.rect(surface, ACCENT if is_sel else (60, 65, 80), t_rect, 1, border_radius=3)
            tsurf = font_small.render(f"{t_val}t", True, (255, 255, 255) if is_sel else TEXT)
            surface.blit(tsurf, tsurf.get_rect(center=(tx + term_w // 2, cur_y + 59)))

        # Offering Announcement Buttons
        oy = cur_y + 80
        _draw_btn(surface, (x + 16, oy, w - 32, 26), f"Announce $500 Offering ({market_yield*100:.2f}%)", font_small, mx, my,
                  enabled=True, color=(120, 240, 150), icon_kind='scale',
                  btn_id='debt_issue_500', world=world, nation=active_n)
        oy += 32
        _draw_btn(surface, (x + 16, oy, w - 32, 26), f"Announce $1,000 Offering ({market_yield*100:.2f}%)", font_small, mx, my,
                  enabled=True, color=ACCENT, icon_kind='scale',
                  btn_id='debt_issue_1000', world=world, nation=active_n)

        # Outstanding Debt Summary
        oy += 34
        surface.blit(font_small.render(f"Outstanding Debt: ${total_debt:,.0f}", True, RED if total_debt > 0 else TEXT), (x + 16, oy))
        surface.blit(font_small.render(f"Servicing Cost: ${servicing_cost:,.2f} / turn", True, (245, 180, 50) if servicing_cost > 0 else DIM), (x + 16, oy + 16))
        surface.blit(font_small.render("1-Turn notice before underwriters purchase.", True, DIM), (x + 16, oy + 34))

    else:
        # Scope == 'foreign' (Foreign Reserves & Bond Market)
        card1_h = 90
        c1_rect = (x + 8, cur_y, w - 16, card1_h)
        pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

        surface.blit(font.render("Foreign Reserve Portfolio", True, (245, 215, 110)), (x + 16, cur_y + 8))
        surface.blit(font_small.render(f"Foreign Bonds Held: ${foreign_reserves:,.0f}", True, (120, 240, 150)), (x + 16, cur_y + 32))
        surface.blit(font_small.render(f"Passive Income: +${passive_income:,.2f} / turn", True, GREEN if passive_income > 0 else TEXT), (x + 16, cur_y + 50))
        surface.blit(font_small.render(f"National Reserves diversify monetary stability.", True, DIM), (x + 16, cur_y + 68))

        cur_y += card1_h + 10

        # Available Foreign Bond Offerings
        card2_h = 280
        c2_rect = (x + 8, cur_y, w - 16, card2_h)
        pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

        surface.blit(font.render("Cross-Border Bond Market", True, ACCENT), (x + 16, cur_y + 8))

        # Live offerings from foreign nations
        foreign_offerings = [o for o in market.get_live_offerings() if o.issuer_nation != active_n.name]
        oy = cur_y + 32

        if not foreign_offerings:
            surface.blit(font_small.render("No live foreign offerings currently on the market.", True, DIM), (x + 16, oy))
            surface.blit(font_small.render("Check back after foreign nations announce debt.", True, DIM), (x + 16, oy + 18))
        else:
            for off in foreign_offerings[:3]:
                can_buy = gov_cash >= off.principal
                b_lbl = f"Buy {off.issuer_nation} ${off.principal:.0f} ({off.coupon_rate*100:.2f}%)"
                _draw_btn(surface, (x + 16, oy, w - 32, 28), b_lbl, font_small, mx, my,
                          enabled=can_buy, color=(120, 240, 150), icon_kind='bank',
                          btn_id='debt_buy_bond', world=world, nation=active_n)
                oy += 34

        # List of bonds held
        held_bonds = market.get_bonds_held_by(active_n.name)
        hy = cur_y + 160
        surface.blit(font_small.render(f"Active Bonds Held ({len(held_bonds)}):", True, TEXT), (x + 16, hy))
        hy += 20
        if not held_bonds:
            surface.blit(font_small.render("No foreign debt instruments currently held.", True, DIM), (x + 16, hy))
        else:
            for b in held_bonds[:3]:
                rem_t = max(0, b.maturity_turn - world.get('turn', 0))
                surface.blit(font_small.render(f"• {b.issuer_nation} ${b.principal:,.0f} @ {b.coupon_rate*100:.2f}% ({rem_t}t left)", True, (120, 240, 150)), (x + 16, hy))
                hy += 18


def debt_panel_hit(pos: tuple[int, int], world: dict) -> bool:
    """Hit-test and interactive execution for Left Sovereign Debt Drawer."""
    if not world.get('debt_panel_open', False):
        return False

    mx, my = pos
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H

    if not (x <= mx <= x + w and y <= my <= y + h):
        return False

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    if close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18:
        close_left_panels(world)
        return True

    # Drawer Top Switcher
    if drawer_top_tabs_hit(pos, world, x, y + 48, w):
        return True

    active_n = _get_active_nation(world)
    if not active_n:
        return True

    market = get_bond_market()
    isrb = market.isrb
    t = world.get('turn', 0)
    gov = active_n.government
    gov_cash = gov.agent.cash if gov else 0.0

    cur_y = y + 48 + 24 + 8

    # Sub-scope Switcher
    scopes = [('domestic', 'Domestic & ISRB'), ('foreign', 'Foreign Reserves')]
    sc_w = (w - 28) // 2
    for i, (s_id, _) in enumerate(scopes):
        sx = x + 10 + i * (sc_w + 8)
        if sx <= mx <= sx + sc_w and cur_y <= my <= cur_y + 24:
            world['debt_scope'] = s_id
            return True

    cur_y += 32
    scope = world.get('debt_scope', 'domestic')

    if scope == 'domestic':
        card1_h = 160
        # Influence Action Clicks
        by = cur_y + 90
        btn_w = w - 32
        btn_h = 22

        # 1. Lobby Upgrade ($200)
        if x + 16 <= mx <= x + 16 + btn_w and by <= my <= by + btn_h:
            if gov_cash >= 200.0:
                gov.agent.cash -= 200.0
                isrb.rating_modifiers[active_n.name] = isrb.rating_modifiers.get(active_n.name, 0) + 1
                isrb.modifier_expiry[active_n.name] = t + 20
                ticker_push(world, t, 'ISRB', f"{active_n.name} lobbied ISRB for credit upgrade (+1 rating tier).", (120, 240, 150))
            return True
        by += btn_h + 4

        # 2. Audit Rival ($350)
        if x + 16 <= mx <= x + 16 + btn_w and by <= my <= by + btn_h:
            if gov_cash >= 350.0:
                gov.agent.cash -= 350.0
                other_nations = [n for n in world.get('nations', []) if n.name != active_n.name]
                if other_nations:
                    rival = other_nations[0]
                    isrb.rating_modifiers[rival.name] = isrb.rating_modifiers.get(rival.name, 0) - 1
                    isrb.modifier_expiry[rival.name] = t + 20
                    ticker_push(world, t, 'ISRB', f"{active_n.name} commissioned ISRB Forensic Audit against {rival.name} (-1 tier).", (245, 180, 50))
            return True
        by += btn_h + 4

        # 3. Board Seat ($600)
        if x + 16 <= mx <= x + 16 + btn_w and by <= my <= by + btn_h:
            if gov_cash >= 600.0 and active_n.name not in isrb.board_seats:
                gov.agent.cash -= 600.0
                isrb.board_seats.add(active_n.name)
                ticker_push(world, t, 'ISRB', f"{active_n.name} acquired permanent ISRB Board Seat (preferential yields).", (80, 200, 255))
            return True

        cur_y += card1_h + 10

        # Term duration selectors (20t, 50t, 100t)
        terms = [20, 50, 100]
        term_w = (w - 48) // 3
        for i, t_val in enumerate(terms):
            tx = x + 16 + i * (term_w + 6)
            if tx <= mx <= tx + term_w and cur_y + 48 <= my <= cur_y + 48 + 22:
                world['bond_duration_selected'] = t_val
                return True

        selected_duration = world.get('bond_duration_selected', 20)
        rating, market_yield = isrb.get_market_yield(active_n, selected_duration, world)

        # 4. Announce $500 Bond
        oy = cur_y + 80
        if x + 16 <= mx <= x + 16 + w - 32 and oy <= my <= oy + 26:
            intent = IssueSovereignBondIntent(active_n.name, 500.0, selected_duration, t)
            active_n.submit_intent(intent, t)
            ticker_push(world, t, 'BONDS', f"{active_n.name} announced $500 {selected_duration}t Sovereign Bond offering (1-turn notice).", (120, 240, 150))
            return True
        oy += 32

        # 5. Announce $1,000 Bond
        if x + 16 <= mx <= x + 16 + w - 32 and oy <= my <= oy + 26:
            intent = IssueSovereignBondIntent(active_n.name, 1000.0, selected_duration, t)
            active_n.submit_intent(intent, t)
            ticker_push(world, t, 'BONDS', f"{active_n.name} announced $1,000 {selected_duration}t Sovereign Bond offering (1-turn notice).", ACCENT)
            return True

    else:
        # Scope == 'foreign'
        cur_y += 90 + 10 + 32
        foreign_offerings = [o for o in market.get_live_offerings() if o.issuer_nation != active_n.name]
        for off in foreign_offerings[:3]:
            if x + 16 <= mx <= x + 16 + w - 32 and cur_y <= my <= cur_y + 28:
                if gov_cash >= off.principal:
                    if hasattr(market, 'purchase_live_offering'):
                        market.purchase_live_offering(active_n, off.offering_id, world, t)
                    else:
                        gov.agent.cash -= off.principal
                        market.purchase_bond(active_n.name, off.issuer_nation, off.principal, off.coupon_rate, off.duration_turns, t)
                        off.status = 'filled'
                        ticker_push(world, t, 'BONDS', f"{active_n.name} purchased ${off.principal:.0f} {off.issuer_nation} sovereign bonds into foreign reserves.", (120, 240, 150))
                return True
            cur_y += 34

    return True
