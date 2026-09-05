"""
worldview_science_panel.py — Left Drawer for Science, Induced Innovation & Royal Bounties.

Duplicates cross-nation innovation functionality from the Sovereign Actions modal:
- National strategic resource endowments ribbon (Iron, Coal, Timber, Petroleum, etc.).
- Era Selector (Era I: Feudal, Era II: Renaissance, Era III: Industrial, Era IV: Modern).
- Technological tree and discovery status:
  - MASTERED (100% bonus active)
  - DIFFUSING (Progress from foreign trade partners)
  - ROYAL PRIZE ACTIVE (Bounty posted for researchers)
  - BLOCKED (Missing prerequisites or required strategic resources)
  - PRESSURE (Induced bottleneck pressure & accumulated domain XP)
- Interactive Action: Pledge Royal Science Prize ($300) to incentivize breakthroughs.
"""

from __future__ import annotations
import pygame
from worldview_camera import HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon, draw_progress_bar_button, draw_icon_badge
from innovation import get_innovation_system, TECH_CATALOG, TechDomain
from tile_resources import TileResource, RESOURCE_META, get_nation_resources
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


def draw_science_panel(surface: pygame.Surface, world: dict, font: pygame.font.Font,
                       font_small: pygame.font.Font, mouse_pos=None) -> None:
    """Draw the Left Science & Innovation Drawer Panel."""
    if not world.get('science_panel_open', False):
        return

    world['layers_collapsed'] = True
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H

    active_n = _get_active_nation(world)
    if not active_n:
        return

    inno = get_innovation_system()
    gov_cash = active_n.government.agent.cash if hasattr(active_n, 'government') and active_n.government else 0.0

    # Background frame
    panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    panel_surf.fill((16, 18, 26, 245))
    surface.blit(panel_surf, (x, y))
    pygame.draw.rect(surface, (65, 70, 90), (x, y, w, h), 1, border_radius=8)

    # Header
    r_icon = get_icon('rare_minerals', 16)
    surface.blit(r_icon, (x + 12, y + 12))
    surface.blit(font.render(f"Science: {active_n.name}", True, ACCENT), (x + 32, y + 10))
    surface.blit(font_small.render(f"Treasury: ${gov_cash:,.0f} {active_n.currency}", True, DIM), (x + 32, y + 30))

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    hc = close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18
    pygame.draw.rect(surface, (60, 60, 80) if hc else (35, 35, 48), close_rect, border_radius=3)
    x_txt = font_small.render("×", True, (255, 255, 255) if hc else DIM)
    surface.blit(x_txt, (close_rect[0] + 4, close_rect[1] + 1))

    # Drawer Top Switcher Tabs
    cur_y = draw_drawer_top_tabs(surface, world, x, y + 48, w, 'science', font_small, mouse_pos)

    # Strategic Resource Endowments Ribbon
    res_card_h = 42
    rc_rect = (x + 8, cur_y, w - 16, res_card_h)
    pygame.draw.rect(surface, CARD_BG, rc_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, rc_rect, 1, border_radius=5)

    accessible_res = get_nation_resources(active_n, world=world)
    rx = x + 14
    surface.blit(font_small.render("Resources:", True, DIM), (rx, cur_y + 12))
    rx += 66

    for r_enum, r_info in RESOURCE_META.items():
        has_r = r_enum in accessible_res
        ico = get_icon(r_enum.value, size=16)
        r_rect = (rx, cur_y + 12, 18, 18)
        is_r_hov = rx <= mx <= rx + 18 and cur_y + 12 <= my <= cur_y + 30
        if is_r_hov and world is not None:
            from worldview_tooltips import get_button_tooltip_data
            tdata = get_button_tooltip_data(f"res_{r_enum.value}", world, nation=active_n)
            if tdata:
                tdata['btn_rect'] = r_rect
                world['_hovered_left_tooltip'] = tdata

        if not has_r:
            faded = ico.copy()
            faded.fill((90, 90, 100, 120), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(faded, (rx, cur_y + 12))
        else:
            surface.blit(ico, (rx, cur_y + 12))
        rx += 22

    cur_y += res_card_h + 10

    # Era Selector Tabs (I, II, III, IV)
    cur_era = world.get('innovation_era', 1)
    eras = [(1, "Era I"), (2, "Era II"), (3, "Era III"), (4, "Era IV")]
    era_w = (w - 24 - 3 * 4) // 4
    for i, (e_num, e_lbl) in enumerate(eras):
        ex = x + 12 + i * (era_w + 4)
        e_rect = (ex, cur_y, era_w, 24)
        is_sel = (cur_era == e_num)
        is_hov = e_rect[0] <= mx <= e_rect[0] + era_w and e_rect[1] <= my <= e_rect[1] + 24
        if is_hov and world is not None:
            from worldview_tooltips import get_button_tooltip_data
            tdata = get_button_tooltip_data(f"sci_era_{e_num}", world, nation=active_n)
            if tdata:
                tdata['btn_rect'] = e_rect
                world['_hovered_left_tooltip'] = tdata

        bg = (52, 72, 100) if is_sel else ((38, 42, 56) if is_hov else (24, 26, 36))
        pygame.draw.rect(surface, bg, e_rect, border_radius=4)
        pygame.draw.rect(surface, ACCENT if is_sel else (60, 65, 80), e_rect, 1, border_radius=4)
        tsurf = font_small.render(e_lbl, True, (255, 255, 255) if is_sel else TEXT)
        surface.blit(tsurf, tsurf.get_rect(center=(ex + era_w // 2, cur_y + 12)))

    cur_y += 32

    # Tech Cards for Selected Era
    discovered = inno.get_discovered_techs(active_n.name)
    diffusing = inno.diffusion_progress.get(active_n.name, {})
    era_techs = [t for t in TECH_CATALOG.values() if t.era == cur_era]

    for tech in era_techs:
        tech_id = tech.tech_id
        is_disc = tech_id in discovered
        diff_prog = diffusing.get(tech_id, 0.0)
        has_bounty = any(b.nation_name == active_n.name and b.tech_id == tech_id for b in inno.active_bounties)

        missing_techs = [t_req for t_req in tech.required_techs if t_req not in discovered]
        missing_res = [r_req for r_req in tech.required_resources if r_req not in accessible_res]

        t_card_h = 82
        card_rect = (x + 8, cur_y, w - 16, t_card_h)
        pygame.draw.rect(surface, CARD_BG, card_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, card_rect, 1, border_radius=5)

        # Status badge
        if is_disc:
            badge_txt = "MASTERED"
            badge_col = GREEN
        elif diff_prog > 0:
            badge_txt = f"DIFFUSING ({int(diff_prog*100)}%)"
            badge_col = (80, 200, 255)
        elif has_bounty:
            badge_txt = "PRIZE ACTIVE"
            badge_col = (245, 205, 70)
        elif missing_techs or missing_res:
            reasons = []
            if missing_techs: reasons.append("Pre-Reqs")
            if missing_res: reasons.append("Resources")
            badge_txt = f"BLOCKED ({', '.join(reasons)})"
            badge_col = RED
        else:
            pressure = tech.bottleneck_evaluator(active_n, active_n.tiles) if tech.bottleneck_evaluator else 1.0
            cur_xp = inno.get_domain_xp(active_n.name, tech.domain)
            badge_txt = f"XP: {int(cur_xp)}/{int(tech.base_xp_required)} ({pressure:.1f}x)"
            badge_col = (235, 140, 50) if pressure > 1.5 else DIM

        # Domain icon & Title
        dom_ico = get_icon(tech.domain.value, size=15)
        surface.blit(dom_ico, (x + 16, cur_y + 8))
        surface.blit(font_small.render(tech.name, True, (255, 255, 255) if is_disc else TEXT), (x + 36, cur_y + 7))

        # Badge
        b_surf = font_small.render(f"[{badge_txt}]", True, badge_col)
        surface.blit(b_surf, (x + 16, cur_y + 26))

        # Action Button or Progress Bar
        btn_rect = (x + 16, cur_y + 46, w - 32, 26)

        # Card & button hover detection
        is_card_hov = card_rect[0] <= mx <= card_rect[0] + card_rect[2] and card_rect[1] <= my <= card_rect[1] + card_rect[3]
        is_btn_hov = btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]
        if is_card_hov and world is not None and not is_btn_hov:
            from worldview_tooltips import get_button_tooltip_data
            tdata = get_button_tooltip_data(f"tech_{tech_id}", world, nation=active_n)
            if tdata:
                tdata['btn_rect'] = card_rect
                world['_hovered_left_tooltip'] = tdata

        if is_disc:
            draw_progress_bar_button(surface, btn_rect, "Technology Mastered", 1.0, font_small, theme='complete', icon_kind='check')
        elif has_bounty:
            cur_xp = inno.get_domain_xp(active_n.name, tech.domain)
            pct = min(1.0, max(0.0, cur_xp / max(1.0, tech.base_xp_required)))
            draw_progress_bar_button(surface, btn_rect, f"Researching {int(pct*100)}%", pct, font_small, theme='science', icon_kind='rare_minerals')
        elif diff_prog > 0:
            draw_progress_bar_button(surface, btn_rect, f"Diffusing {int(diff_prog*100)}%", diff_prog, font_small, theme='diffusion', icon_kind='im')
        elif missing_techs or missing_res:
            _draw_btn(surface, btn_rect, "Pledge Prize ($300)", font_small, mx, my, enabled=False,
                      btn_id=f"sci_pledge_{tech_id}", world=world, nation=active_n)
        else:
            can_afford = gov_cash >= 300.0
            _draw_btn(surface, btn_rect, "Pledge Royal Prize ($300)", font_small, mx, my,
                      enabled=can_afford, color=ACCENT, icon_kind='treasury',
                      btn_id=f"sci_pledge_{tech_id}", world=world, nation=active_n)

        cur_y += t_card_h + 8


def science_panel_hit(pos: tuple[int, int], world: dict) -> bool:
    """Hit-test and interactive execution for Left Science Drawer."""
    if not world.get('science_panel_open', False):
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

    inno = get_innovation_system()
    gov = active_n.government
    gov_cash = gov.agent.cash if gov else 0.0
    t = world.get('turn', 0)

    cur_y = y + 48 + 24 + 8 + 42 + 10

    # Era Selector Tabs (I, II, III, IV)
    eras = [(1, "Era I"), (2, "Era II"), (3, "Era III"), (4, "Era IV")]
    era_w = (w - 24 - 3 * 4) // 4
    for i, (e_num, _) in enumerate(eras):
        ex = x + 12 + i * (era_w + 4)
        if ex <= mx <= ex + era_w and cur_y <= my <= cur_y + 24:
            world['innovation_era'] = e_num
            return True

    cur_y += 32

    # Tech Action Buttons
    cur_era = world.get('innovation_era', 1)
    discovered = inno.get_discovered_techs(active_n.name)
    accessible_res = get_nation_resources(active_n, world=world)
    era_techs = [tch for tch in TECH_CATALOG.values() if tch.era == cur_era]

    for tech in era_techs:
        tech_id = tech.tech_id
        is_disc = tech_id in discovered
        has_bounty = any(b.nation_name == active_n.name and b.tech_id == tech_id for b in inno.active_bounties)
        missing_techs = [t_req for t_req in tech.required_techs if t_req not in discovered]
        missing_res = [r_req for r_req in tech.required_resources if r_req not in accessible_res]

        btn_rect = (x + 16, cur_y + 46, w - 32, 26)
        if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]:
            if not is_disc and not has_bounty and not missing_techs and not missing_res:
                ok = inno.post_royal_bounty(active_n, tech_id, 300.0, t)
                if ok:
                    ticker_push(world, t, 'INNOVATION', f"{active_n.name} established a $300 Royal Innovation Prize for {tech.name}!", (80, 200, 255))
            return True

        cur_y += 82 + 8

    return True
