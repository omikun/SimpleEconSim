"""
worldview_diplomacy_panel.py — Left Drawer for Bilateral Diplomacy & Treaties.

Duplicates cross-nation diplomacy functionality from the Sovereign Actions modal:
- Target foreign nation switcher tabs.
- Real-time bilateral relation score and status gauge (-1.0 to +1.0).
- Active treaties indicators (Trade Pact, Non-Aggression Pact, Defensive Alliance).
- Interactive diplomatic decrees:
  - Propose / Cancel Trade Pact
  - Propose / Cancel Non-Aggression Pact
  - Form / Break Defensive Alliance
  - Declare War / Sign Peace Treaty
  - Send Foreign Aid Gift ($100) (+0.15 relation boost)
- Live diplomatic memory & betrayal incident log.
"""

from __future__ import annotations
import pygame
from worldview_camera import HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN, NATION_COLORS
from ui_icons import get_icon
from diplomacy import get_diplomacy, TreatyType
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


def draw_diplomacy_panel(surface: pygame.Surface, world: dict, font: pygame.font.Font,
                         font_small: pygame.font.Font, mouse_pos=None) -> None:
    """Draw the Left Diplomacy & Treaties Drawer Panel."""
    if not world.get('diplomacy_panel_open', False):
        return

    world['layers_collapsed'] = True
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H

    active_n = _get_active_nation(world)
    if not active_n:
        return

    nations = world.get('nations', [])
    diplomacy = get_diplomacy()
    other_nations = [n for n in nations if n.name != active_n.name]

    # Target foreign nation selection
    target_name = world.get('diplomacy_target_nation')
    target_n = next((n for n in other_nations if n.name == target_name), other_nations[0] if other_nations else None)
    if target_n:
        world['diplomacy_target_nation'] = target_n.name

    # Background frame
    panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    panel_surf.fill((16, 18, 26, 245))
    surface.blit(panel_surf, (x, y))
    pygame.draw.rect(surface, (65, 70, 90), (x, y, w, h), 1, border_radius=8)

    # Header
    c_icon = get_icon('crown', 16)
    surface.blit(c_icon, (x + 12, y + 12))
    treasury_cash = active_n.government.agent.cash if hasattr(active_n, 'government') and active_n.government else 0.0
    head_txt = font.render(f"Diplomacy: {active_n.name}", True, ACCENT)
    surface.blit(head_txt, (x + 32, y + 10))

    sub_txt = font_small.render(f"Treasury: ${treasury_cash:,.0f} {active_n.currency}", True, DIM)
    surface.blit(sub_txt, (x + 32, y + 30))

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    hc = close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18
    pygame.draw.rect(surface, (60, 60, 80) if hc else (35, 35, 48), close_rect, border_radius=3)
    x_txt = font_small.render("×", True, (255, 255, 255) if hc else DIM)
    surface.blit(x_txt, (close_rect[0] + 4, close_rect[1] + 1))

    # Drawer Top Switcher Tabs
    cur_y = draw_drawer_top_tabs(surface, world, x, y + 48, w, 'diplomacy', font_small, mouse_pos)

    if not other_nations or not target_n:
        empty_lbl = font_small.render("No foreign nations discovered.", True, DIM)
        surface.blit(empty_lbl, (x + 20, cur_y + 20))
        return

    # Foreign Nation Selector Tabs
    tab_h = 24
    t_gap = 4
    n_count = len(other_nations)
    tab_w = (w - 24 - (n_count - 1) * t_gap) // max(1, n_count)

    for i, o_nat in enumerate(other_nations):
        tx = x + 12 + i * (tab_w + t_gap)
        t_rect = (tx, cur_y, tab_w, tab_h)
        is_sel = (o_nat.name == target_n.name)
        is_hov = t_rect[0] <= mx <= t_rect[0] + tab_w and t_rect[1] <= my <= t_rect[1] + tab_h

        n_col = NATION_COLORS.get(o_nat.name, ACCENT)
        bg = (45, 55, 78) if is_sel else ((35, 38, 50) if is_hov else (24, 26, 36))
        pygame.draw.rect(surface, bg, t_rect, border_radius=4)
        pygame.draw.rect(surface, n_col if is_sel else (60, 65, 80), t_rect, 2 if is_sel else 1, border_radius=4)

        t_name_surf = font_small.render(o_nat.name[:9], True, (255, 255, 255) if is_sel else TEXT)
        surface.blit(t_name_surf, t_name_surf.get_rect(center=(tx + tab_w // 2, cur_y + tab_h // 2)))

    cur_y += tab_h + 10

    # Foreign Nation Relations Card
    card1_h = 138
    c1_rect = (x + 8, cur_y, w - 16, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    rel = diplomacy.get_relation(active_n.name, target_n.name)
    is_war = diplomacy.are_at_war(active_n.name, target_n.name)
    has_trade = diplomacy.has_treaty(active_n.name, target_n.name, TreatyType.TRADE_PACT.value)
    has_nap = diplomacy.has_treaty(active_n.name, target_n.name, TreatyType.NON_AGGRESSION.value)
    has_alliance = diplomacy.has_treaty(active_n.name, target_n.name, TreatyType.DEFENSIVE_ALLIANCE.value)

    rel_color = RED if is_war else (GREEN if rel > 0.25 else (RED if rel < -0.25 else TEXT))
    rel_label = "WAR" if is_war else ("ALLIED" if has_alliance else ("FRIENDLY" if rel > 0.25 else ("HOSTILE" if rel < -0.25 else "NEUTRAL")))

    nat_title = font.render(f"{target_n.name}", True, NATION_COLORS.get(target_n.name, TEXT))
    surface.blit(nat_title, (x + 16, cur_y + 8))

    regime_txt = font_small.render(f"Regime: {getattr(target_n, 'regime_type', 'Monarchy')}", True, DIM)
    surface.blit(regime_txt, (x + 16, cur_y + 30))

    rel_txt = font_small.render(f"Relation: {rel:+.2f} [{rel_label}]", True, rel_color)
    surface.blit(rel_txt, (x + 16, cur_y + 48))

    # Meter Bar (-1.0 to 1.0)
    bar_x, bar_y, bar_w, bar_h = x + 16, cur_y + 68, w - 48, 8
    pygame.draw.rect(surface, (35, 38, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
    fill_pct = max(0.0, min(1.0, (rel + 1.0) / 2.0))
    pygame.draw.rect(surface, rel_color, (bar_x, bar_y, int(bar_w * fill_pct), bar_h), border_radius=3)

    # Active Treaties Summary Line
    t_list = []
    if has_trade: t_list.append("Trade Pact")
    if has_nap: t_list.append("NAP")
    if has_alliance: t_list.append("Alliance")
    t_str = f"Active Treaties: {', '.join(t_list) if t_list else 'None'}"
    surface.blit(font_small.render(t_str, True, (100, 210, 255) if has_alliance else (GREEN if has_trade else DIM)), (x + 16, cur_y + 82))

    # Bilateral Trade & Tariff info
    tariff_pct = 25 if not has_trade else 12
    surface.blit(font_small.render(f"Border Tariff: {tariff_pct}% (50% cut with Trade Pact)", True, DIM), (x + 16, cur_y + 104))

    cur_y += card1_h + 10

    # Interactive Diplomatic Decrees Card
    dec_card_h = 240
    dc_rect = (x + 8, cur_y, w - 16, dec_card_h)
    pygame.draw.rect(surface, CARD_BG, dc_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, dc_rect, 1, border_radius=5)

    surface.blit(font.render("Diplomatic Decrees", True, (245, 215, 110)), (x + 16, cur_y + 8))

    btn_x = x + 16
    btn_w = w - 32
    btn_h = 26
    btn_y = cur_y + 32

    # 1. Trade Pact Toggle
    trade_lbl = "Cancel Trade Pact" if has_trade else "+ Propose Trade Pact"
    _draw_btn(surface, (btn_x, btn_y, btn_w, btn_h), trade_lbl, font_small, mx, my,
              enabled=not is_war, color=GREEN if not has_trade else (120, 220, 140),
              custom_bg=(30, 48, 40) if has_trade else None, icon_kind='ex')
    btn_y += btn_h + 6

    # 2. Non-Aggression Pact Toggle
    nap_lbl = "Cancel Non-Aggression Pact" if has_nap else "+ Propose NAP Treaty"
    _draw_btn(surface, (btn_x, btn_y, btn_w, btn_h), nap_lbl, font_small, mx, my,
              enabled=not is_war, color=ACCENT if not has_nap else (245, 215, 110),
              custom_bg=(45, 45, 32) if has_nap else None, icon_kind='shield')
    btn_y += btn_h + 6

    # 3. Defensive Alliance Toggle
    ally_lbl = "Cancel Defensive Alliance" if has_alliance else "+ Form Defensive Alliance"
    _draw_btn(surface, (btn_x, btn_y, btn_w, btn_h), ally_lbl, font_small, mx, my,
              enabled=not is_war, color=(80, 200, 255),
              custom_bg=(30, 45, 65) if has_alliance else None, icon_kind='crown')
    btn_y += btn_h + 6

    # 4. War / Peace Decree
    if is_war:
        _draw_btn(surface, (btn_x, btn_y, btn_w, btn_h), "Sign Peace Treaty", font_small, mx, my,
                  enabled=True, color=GREEN, custom_bg=(30, 50, 36), icon_kind='check')
    else:
        _draw_btn(surface, (btn_x, btn_y, btn_w, btn_h), "Declare War", font_small, mx, my,
                  enabled=True, color=RED, custom_bg=(55, 25, 25), icon_kind='military')
    btn_y += btn_h + 6

    # 5. Foreign Aid Gift ($100)
    can_aid = treasury_cash >= 100.0 and not is_war
    _draw_btn(surface, (btn_x, btn_y, btn_w, btn_h), "Send Foreign Aid ($100)", font_small, mx, my,
              enabled=can_aid, color=(120, 240, 150), icon_kind='treasury')

    cur_y += dec_card_h + 10

    # Diplomatic Memory / Betrayal Log Card
    rem_h = (y + h) - cur_y - 8
    if rem_h > 50:
        log_rect = (x + 8, cur_y, w - 16, rem_h)
        pygame.draw.rect(surface, CARD_BG, log_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, log_rect, 1, border_radius=5)

        surface.blit(font_small.render("Recent Diplomatic Memory:", True, ACCENT), (x + 16, cur_y + 8))

        mem_list = diplomacy.betrayal_memory.get((active_n.name, target_n.name), [])
        if not mem_list:
            mem_list = diplomacy.betrayal_memory.get((target_n.name, active_n.name), [])

        ly = cur_y + 26
        if not mem_list:
            surface.blit(font_small.render("No grievances or betrayal memory recorded.", True, DIM), (x + 16, ly))
        else:
            for mem in mem_list[-3:]:
                m_txt = font_small.render(f"• T={mem.get('turn', 0)}: {mem.get('type', 'event')} ({mem.get('reason', '')})", True, RED if 'war' in mem.get('type', '') or 'broken' in mem.get('type', '') else TEXT)
                surface.blit(m_txt, (x + 16, ly))
                ly += 16


def diplomacy_panel_hit(pos: tuple[int, int], world: dict) -> bool:
    """Hit-test and interactive execution for Left Diplomacy Drawer."""
    if not world.get('diplomacy_panel_open', False):
        return False

    mx, my = pos
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H

    # Out-of-bounds click
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

    nations = world.get('nations', [])
    other_nations = [n for n in nations if n.name != active_n.name]
    if not other_nations:
        return True

    cur_y = y + 48 + 24 + 8
    tab_h = 24
    t_gap = 4
    n_count = len(other_nations)
    tab_w = (w - 24 - (n_count - 1) * t_gap) // max(1, n_count)

    # Foreign Nation Selector Tabs
    for i, o_nat in enumerate(other_nations):
        tx = x + 12 + i * (tab_w + t_gap)
        if tx <= mx <= tx + tab_w and cur_y <= my <= cur_y + tab_h:
            world['diplomacy_target_nation'] = o_nat.name
            return True

    target_name = world.get('diplomacy_target_nation')
    target_n = next((n for n in other_nations if n.name == target_name), other_nations[0])

    cur_y += tab_h + 10 + 138 + 10
    # Buttons inside Decrees Card
    btn_x = x + 16
    btn_w = w - 32
    btn_h = 26
    btn_y = cur_y + 32

    diplomacy = get_diplomacy()
    t = world.get('turn', 0)
    has_trade = diplomacy.has_treaty(active_n.name, target_n.name, TreatyType.TRADE_PACT.value)
    has_nap = diplomacy.has_treaty(active_n.name, target_n.name, TreatyType.NON_AGGRESSION.value)
    has_alliance = diplomacy.has_treaty(active_n.name, target_n.name, TreatyType.DEFENSIVE_ALLIANCE.value)
    is_war = diplomacy.are_at_war(active_n.name, target_n.name)

    # 1. Trade Pact Button
    if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h and not is_war:
        if has_trade:
            diplomacy.cancel_treaty(active_n.name, target_n.name, TreatyType.TRADE_PACT.value, t)
            ticker_push(world, t, 'DIPLOMACY', f"{active_n.name} cancelled Trade Pact with {target_n.name}.", (240, 140, 60))
        else:
            diplomacy.sign_treaty(active_n.name, target_n.name, TreatyType.TRADE_PACT.value, t)
            ticker_push(world, t, 'DIPLOMACY', f"{active_n.name} signed Trade Pact with {target_n.name}.", (120, 220, 130))
        return True
    btn_y += btn_h + 6

    # 2. NAP Button
    if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h and not is_war:
        if has_nap:
            diplomacy.cancel_treaty(active_n.name, target_n.name, TreatyType.NON_AGGRESSION.value, t)
            ticker_push(world, t, 'DIPLOMACY', f"{active_n.name} cancelled Non-Aggression Pact with {target_n.name}.", (240, 140, 60))
        else:
            diplomacy.sign_treaty(active_n.name, target_n.name, TreatyType.NON_AGGRESSION.value, t)
            ticker_push(world, t, 'DIPLOMACY', f"{active_n.name} concluded Non-Aggression Pact with {target_n.name}.", ACCENT)
        return True
    btn_y += btn_h + 6

    # 3. Defensive Alliance Button
    if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h and not is_war:
        if has_alliance:
            diplomacy.cancel_treaty(active_n.name, target_n.name, TreatyType.DEFENSIVE_ALLIANCE.value, t)
            ticker_push(world, t, 'DIPLOMACY', f"{active_n.name} dissolved Defensive Alliance with {target_n.name}.", (240, 140, 60))
        else:
            diplomacy.sign_treaty(active_n.name, target_n.name, TreatyType.DEFENSIVE_ALLIANCE.value, t)
            ticker_push(world, t, 'DIPLOMACY', f"{active_n.name} and {target_n.name} formed a Defensive Alliance!", (80, 200, 255))
        return True
    btn_y += btn_h + 6

    # 4. War / Peace Button
    if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h:
        if is_war:
            diplomacy.sign_peace(active_n.name, target_n.name, t)
            ticker_push(world, t, 'DIPLOMACY', f"Peace restored between {active_n.name} and {target_n.name}.", (120, 220, 130))
        else:
            diplomacy.declare_war(active_n.name, target_n.name, t, reason="Sovereign border declaration")
            ticker_push(world, t, 'WAR', f"WAR DECLARED: {active_n.name} declared war on {target_n.name}!", RED)
        return True
    btn_y += btn_h + 6

    # 5. Send Foreign Aid ($100)
    if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h:
        gov = active_n.government
        if gov and gov.agent.cash >= 100.0 and not is_war:
            gov.agent.cash -= 100.0
            if hasattr(target_n, 'government') and target_n.government:
                target_n.government.agent.cash += 100.0
            cur_rel = diplomacy.get_relation(active_n.name, target_n.name)
            diplomacy.set_relation(active_n.name, target_n.name, min(1.0, cur_rel + 0.15))
            ticker_push(world, t, 'DIPLOMACY', f"{active_n.name} dispatched $100 Foreign Aid Grant to {target_n.name} (+0.15 Relation).", (120, 240, 150))
        return True

    return True  # Consume all clicks inside panel
