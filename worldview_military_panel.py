"""
worldview_military_panel.py — Left Drawer for Military, Armed Forces & Garrison Defense.

Duplicates cross-nation military functionality from the Sovereign Actions modal:
- National defense readiness and total military upkeep / turn.
- Stationed garrison and recruitment on selected territory.
- Standing armies registry (Unit ID, soldiers, morale, equipment, veteran XP, combat strength).
- Interactive Action: Recruit Garrison Division (15 soldiers, $15).
"""

from __future__ import annotations
import pygame
from worldview_camera import HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon
from intents import RecruitArmyIntent
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


def draw_military_panel(surface: pygame.Surface, world: dict, font: pygame.font.Font,
                        font_small: pygame.font.Font, mouse_pos=None) -> None:
    """Draw the Left Military & Defense Drawer Panel."""
    if not world.get('military_panel_open', False):
        return

    world['layers_collapsed'] = True
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H

    active_n = _get_active_nation(world)
    if not active_n:
        return

    gov_cash = active_n.government.agent.cash if hasattr(active_n, 'government') and active_n.government else 0.0
    units = getattr(active_n, 'units', [])
    total_troops = sum(getattr(u, 'soldiers', 0) for u in units)
    total_upkeep = total_troops * 0.10

    pinned_tile = world.get('selected_region')
    target_tile = pinned_tile if (pinned_tile and pinned_tile in active_n.tiles) else (active_n.tiles[0] if active_n.tiles else None)
    tile_name = getattr(target_tile, 'display_name', getattr(target_tile, 'city_name', target_tile.name)) if target_tile else "None"
    is_owned = target_tile in active_n.tiles if target_tile else False

    # Background frame
    panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    panel_surf.fill((16, 18, 26, 245))
    surface.blit(panel_surf, (x, y))
    pygame.draw.rect(surface, (65, 70, 90), (x, y, w, h), 1, border_radius=8)

    # Header
    m_icon = get_icon('military', 16)
    surface.blit(m_icon, (x + 12, y + 12))
    surface.blit(font.render(f"Military: {active_n.name}", True, ACCENT), (x + 32, y + 10))
    surface.blit(font_small.render(f"Treasury: ${gov_cash:,.0f} {active_n.currency}", True, DIM), (x + 32, y + 30))

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    hc = close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18
    pygame.draw.rect(surface, (60, 60, 80) if hc else (35, 35, 48), close_rect, border_radius=3)
    x_txt = font_small.render("×", True, (255, 255, 255) if hc else DIM)
    surface.blit(x_txt, (close_rect[0] + 4, close_rect[1] + 1))

    # Drawer Top Switcher Tabs
    cur_y = draw_drawer_top_tabs(surface, world, x, y + 48, w, 'military', font_small, mouse_pos)

    # Readiness & Upkeep Card
    card1_h = 76
    c1_rect = (x + 8, cur_y, w - 16, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font.render("Defense Readiness", True, (245, 215, 110)), (x + 16, cur_y + 8))
    surface.blit(font_small.render(f"Standing Troops: {total_troops:,} in {len(units)} Division(s)", True, TEXT), (x + 16, cur_y + 32))
    surface.blit(font_small.render(f"Upkeep Cost: ${total_upkeep:,.2f} / turn", True, (245, 180, 50) if total_upkeep > 0 else DIM), (x + 16, cur_y + 50))

    cur_y += card1_h + 10

    # Selected Tile Recruitment Card
    card2_h = 98
    c2_rect = (x + 8, cur_y, w - 16, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font.render("Territory Mobilization", True, ACCENT), (x + 16, cur_y + 8))
    surface.blit(font_small.render(f"Station: [{tile_name}]", True, (220, 230, 245) if is_owned else DIM), (x + 16, cur_y + 32))

    can_recruit = is_owned and gov_cash >= 15.0
    _draw_btn(surface, (x + 16, cur_y + 56, w - 32, 28), "Recruit Unit (15 soldiers, $15)", font_small, mx, my,
              enabled=can_recruit, color=(120, 240, 150), icon_kind='military')

    cur_y += card2_h + 10

    # Deployed Formations & Standing Armies List
    rem_h = (y + h) - cur_y - 8
    c3_rect = (x + 8, cur_y, w - 16, rem_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font.render("Active Formations", True, (245, 215, 110)), (x + 16, cur_y + 8))

    uy = cur_y + 34
    if not units:
        surface.blit(font_small.render("No active military divisions deployed.", True, DIM), (x + 16, uy))
        surface.blit(font_small.render("Recruit soldiers above to garrison your borders.", True, DIM), (x + 16, uy + 18))
    else:
        for u in units[:5]:
            reg_name = getattr(u, 'region_name', 'Field')
            soldiers = getattr(u, 'soldiers', 0)
            morale = getattr(u, 'morale', 1.0)
            xp = getattr(u, 'veteran_xp', 0.0)
            strength = getattr(u, 'strength', float(soldiers))

            u_col = GREEN if morale > 0.7 else (RED if morale < 0.3 else TEXT)
            surface.blit(font_small.render(f"• Div #{getattr(u, 'unit_id', 1)} [{reg_name}]: {soldiers} troops", True, ACCENT), (x + 16, uy))
            surface.blit(font_small.render(f"  Str: {strength:.1f} • Morale: {morale*100:.0f}% • XP: {xp:.2f}", True, u_col), (x + 16, uy + 16))
            uy += 36


def military_panel_hit(pos: tuple[int, int], world: dict) -> bool:
    """Hit-test and interactive execution for Left Military Drawer."""
    if not world.get('military_panel_open', False):
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

    gov = active_n.government
    gov_cash = gov.agent.cash if gov else 0.0
    pinned_tile = world.get('selected_region')
    target_tile = pinned_tile if (pinned_tile and pinned_tile in active_n.tiles) else (active_n.tiles[0] if active_n.tiles else None)
    is_owned = target_tile in active_n.tiles if target_tile else False

    cur_y = y + 48 + 24 + 8 + 76 + 10

    # Recruit Unit Button
    rec_btn_rect = (x + 16, cur_y + 56, w - 32, 28)
    if rec_btn_rect[0] <= mx <= rec_btn_rect[0] + rec_btn_rect[2] and rec_btn_rect[1] <= my <= rec_btn_rect[1] + rec_btn_rect[3]:
        if is_owned and gov_cash >= 15.0:
            t = world.get('turn', 0)
            intent = RecruitArmyIntent(active_n.name, target_tile.name, 15, wage=1.0, submitted_turn=t, regime_type=active_n.regime_type)
            active_n.submit_intent(intent, t)
            ticker_push(world, t, 'MILITARY', f"{active_n.name} commissioned 15 Infantrymen to garrison {target_tile.name}.", (235, 80, 80))
        return True

    return True
