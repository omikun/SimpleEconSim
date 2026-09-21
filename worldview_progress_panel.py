"""
worldview_progress_panel.py — Unified Progress & Development Drawer for REGNUM.

Displays everything being:
1. Built: Active & stalled construction projects (progress %, turns left, stalled status & reasons, contractor).
2. Researched: Technologies in progress, diffusing, or royal bounties active, plus mastered breakthroughs.
3. Legislated: Parliamentary bills, statutory workday caps, active survey debts, and government decrees.

Supports:
- Filter mode: Active Nation vs All Nations (grouped by Nation and Province).
- Visual progress bars with category color coding and turns remaining.
- Stalled icons and warning badges with one-click emergency subsidies.
- Smooth scrolling via mouse wheel and scroll buttons.
"""

from __future__ import annotations
import pygame
from typing import TYPE_CHECKING
from worldview_camera import HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon
from worldview_left_dock import (
    PANEL_X, PANEL_Y, PANEL_W, PANEL_H,
    draw_drawer_top_tabs, drawer_top_tabs_hit,
    open_left_panel, close_left_panels
)
from innovation import get_innovation_system, TECH_CATALOG
from goods import Goods

if TYPE_CHECKING:
    from region import Region
    from nation import Nation


CARD_BG = (22, 24, 34)
CARD_BORDER = (42, 46, 64)
SECTION_BG = (28, 32, 46)

_PROGRESS_BUTTONS: list[tuple[tuple[int, int, int, int], str, object]] = []


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


def _collect_items_for_nation(nation: Nation, world: dict) -> list[dict]:
    """Collect all construction, research, and legislation items for one nation."""
    items = []
    t = world.get('turn', 1)
    inn_sys = get_innovation_system()

    # 1. Construction Projects
    seen_projs = set()
    all_projs = list(getattr(nation, 'construction_projects', []))
    for tile in getattr(nation, 'tiles', []):
        for p in getattr(tile, 'construction_projects', []):
            if p not in all_projs:
                all_projs.append(p)

    for p in all_projs:
        if p.project_id in seen_projs:
            continue
        seen_projs.add(p.project_id)
        pct = getattr(p, 'progress_pct', 0.0)
        rem = p.turns_remaining
        is_stalled = (p.status == 'stalled')
        reason = getattr(p, 'stall_reason', '')
        r_label = "Missing Materials" if reason == "missing_materials" else ("Missing Labor" if reason == "missing_labor" else "Resource Shortage")
        contractor = getattr(p, 'contractor', None)
        c_name = getattr(contractor, 'company_name', 'Contractor') if contractor else 'State Bureau'
        prov_name = getattr(getattr(p.region, 'province', None), 'name', 'Direct Rule')

        items.append({
            'category': 'construction',
            'nation': nation.name,
            'province': prov_name,
            'region': p.region.name,
            'title': p.recipe.display_name,
            'subtitle': f"{p.region.name} • {c_name}",
            'progress_pct': pct,
            'turns_left': rem,
            'status': p.status,
            'is_stalled': is_stalled,
            'stall_reason': r_label,
            'icon': 'hammer',
            'bar_color': (235, 75, 75) if is_stalled else (245, 180, 50),
            'project': p,
        })

    # 2. Innovation & Research
    nat_xp = inn_sys.domain_experience.get(nation.name, {})
    discovered = inn_sys.get_discovered_techs(nation.name)
    bounties = [b.tech_id for b in inn_sys.active_bounties if b.nation_name == nation.name]

    for tech_id, tech in TECH_CATALOG.items():
        is_mastered = (tech_id in discovered)
        cur_xp = nat_xp.get(tech.domain.value, 0.0)
        req_xp = tech.base_xp_required
        diff_prog = inn_sys.diffusion_progress.get(nation.name, {}).get(tech_id, 0.0)
        xp_prog = min(1.0, cur_xp / max(1.0, req_xp))
        prog = 1.0 if is_mastered else max(xp_prog, diff_prog)
        has_bounty = (tech_id in bounties)

        # Show if mastered, has bounty, diffusing, or significant domain experience
        if is_mastered or has_bounty or prog >= 0.10:
            status_label = 'mastered' if is_mastered else ('bounty_active' if has_bounty else 'researching')
            turns_est = 0 if is_mastered else max(1, int((req_xp - cur_xp) / 25.0))
            items.append({
                'category': 'research',
                'nation': nation.name,
                'province': 'National Academy',
                'region': 'Realm Capital',
                'title': tech.name,
                'subtitle': f"{tech.domain.value.title()} • Era {tech.era}",
                'progress_pct': prog * 100.0,
                'turns_left': turns_est,
                'status': status_label,
                'is_stalled': False,
                'stall_reason': '',
                'icon': 'rare_minerals',
                'bar_color': (100, 220, 140) if is_mastered else (75, 180, 245),
            })

    # 3. Legislation, Parliamentary Decrees & Statutory Mandates
    # Pending Intents
    for intent in getattr(nation, 'intents', []):
        is_pending = (intent.status == 'pending_approval')
        delay = getattr(intent, 'approval_delay', 0)
        pct = 50.0 if is_pending else 100.0
        i_title = intent.intent_type.replace('_', ' ').title()
        items.append({
            'category': 'legislation',
            'nation': nation.name,
            'province': 'Parliament',
            'region': 'Chamber',
            'title': f"Bill: {i_title}",
            'subtitle': f"Parliamentary Intent #{intent.intent_id}",
            'progress_pct': pct,
            'turns_left': delay,
            'status': intent.status,
            'is_stalled': False,
            'stall_reason': '',
            'icon': 'policies',
            'bar_color': (180, 120, 240),
        })

    # Enacted Statutory Mandates on Tiles
    gov = getattr(nation, 'government', None)
    if gov is not None:
        if getattr(gov, 'ubi_enabled', False):
            items.append({
                'category': 'legislation',
                'nation': nation.name,
                'province': 'Treasury',
                'region': 'National',
                'title': 'Universal Basic Income ($2.0/t)',
                'subtitle': 'Statutory Welfare Guarantee',
                'progress_pct': 100.0,
                'turns_left': 0,
                'status': 'enacted',
                'is_stalled': False,
                'stall_reason': '',
                'icon': 'policies',
                'bar_color': (100, 220, 140),
            })
        if getattr(gov, 'baby_bonus_enabled', False):
            items.append({
                'category': 'legislation',
                'nation': nation.name,
                'province': 'Interior',
                'region': 'National',
                'title': 'Pronatalist Baby Bonus ($50.0)',
                'subtitle': 'Demographic Growth Decree',
                'progress_pct': 100.0,
                'turns_left': 0,
                'status': 'enacted',
                'is_stalled': False,
                'stall_reason': '',
                'icon': 'policies',
                'bar_color': (100, 220, 140),
            })

    for tile in getattr(nation, 'tiles', []):
        prov_name = getattr(getattr(tile, 'province', None), 'name', 'Crown Territory')
        # Workday shift cap
        if getattr(tile, 'ten_hour_act', False):
            items.append({
                'category': 'legislation',
                'nation': nation.name,
                'province': prov_name,
                'region': tile.name,
                'title': f"Ten-Hour Workday Act ({tile.workday_cap:.1f}h)",
                'subtitle': f"Statutory Shift Cap • {tile.name}",
                'progress_pct': 100.0,
                'turns_left': 0,
                'status': 'enacted',
                'is_stalled': False,
                'stall_reason': '',
                'icon': 'clock',
                'bar_color': (100, 220, 140),
            })
        # Active Survey Debts countdown
        for debt in getattr(tile, 'enclosure_survey_debts', []):
            rem_t = debt.get('countdown', 0)
            title_fee = int(debt.get('fee', 0.0))
            items.append({
                'category': 'legislation',
                'nation': nation.name,
                'province': prov_name,
                'region': tile.name,
                'title': f"Survey Debt Assessment (${title_fee})",
                'subtitle': f"Foreclosure Debt • {tile.name}",
                'progress_pct': max(0.0, (1.0 - rem_t / 3.0) * 100.0),
                'turns_left': rem_t,
                'status': 'pending_foreclosure',
                'is_stalled': (rem_t <= 1),
                'stall_reason': 'Auction Soon' if rem_t <= 1 else '',
                'icon': 'debt',
                'bar_color': (235, 90, 90) if rem_t <= 1 else (245, 180, 50),
            })

    return items


def draw_progress_panel(surface: pygame.Surface, world: dict, font: pygame.font.Font,
                        font_small: pygame.font.Font, mouse_pos=None) -> None:
    """Render the Left Progress & Realm Development Drawer."""
    if not world.get('progress_panel_open', False):
        return

    global _PROGRESS_BUTTONS
    _PROGRESS_BUTTONS.clear()

    world['layers_collapsed'] = True
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H

    # Dark background panel
    surf_bg = pygame.Surface((w, h), pygame.SRCALPHA)
    surf_bg.fill((16, 18, 26, 250))
    surface.blit(surf_bg, (x, y))
    pygame.draw.rect(surface, (60, 68, 90), (x, y, w, h), 1, border_radius=6)

    # 1. Drawer Top 7-Tab Switcher
    cur_y = draw_drawer_top_tabs(surface, world, x, y + 6, w, 'progress', font_small, mouse_pos=mouse_pos)

    # 2. Header & Close Button
    lbl_title = font_small.render("Realm Progress & Works", True, (255, 255, 255))
    surface.blit(lbl_title, (x + 12, cur_y))

    # [X] Close button
    close_rect = (x + w - 24, cur_y - 2, 18, 18)
    is_close_hov = close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18
    pygame.draw.rect(surface, (55, 30, 30) if is_close_hov else (30, 32, 42), close_rect, border_radius=3)
    lbl_x = font_small.render("×", True, (240, 100, 100) if is_close_hov else (180, 180, 190))
    surface.blit(lbl_x, (close_rect[0] + 4, close_rect[1] - 3))
    _PROGRESS_BUTTONS.append((close_rect, 'close', None))
    cur_y += 24

    # 3. View Mode Switcher: [ Active Nation ] vs [ All Nations ]
    mode = world.get('progress_view_mode', 'active')
    btn_w = (w - 30) // 2
    btn_h = 24

    rect_act = (x + 12, cur_y, btn_w, btn_h)
    rect_all = (x + 12 + btn_w + 6, cur_y, btn_w, btn_h)

    is_act_hov = rect_act[0] <= mx <= rect_act[0] + btn_w and rect_act[1] <= my <= rect_act[1] + btn_h
    is_all_hov = rect_all[0] <= mx <= rect_all[0] + btn_w and rect_all[1] <= my <= rect_all[1] + btn_h

    bg_act = (55, 75, 105) if mode == 'active' else ((40, 44, 60) if is_act_hov else (28, 30, 42))
    bg_all = (55, 75, 105) if mode == 'all' else ((40, 44, 60) if is_all_hov else (28, 30, 42))

    pygame.draw.rect(surface, bg_act, rect_act, border_radius=4)
    pygame.draw.rect(surface, ACCENT if mode == 'active' else (50, 56, 75), rect_act, 1, border_radius=4)
    txt_act = font_small.render("Active Nation", True, (255, 255, 255) if mode == 'active' else TEXT)
    surface.blit(txt_act, txt_act.get_rect(center=(rect_act[0] + btn_w // 2, rect_act[1] + btn_h // 2)))
    _PROGRESS_BUTTONS.append((rect_act, 'mode_active', None))

    pygame.draw.rect(surface, bg_all, rect_all, border_radius=4)
    pygame.draw.rect(surface, ACCENT if mode == 'all' else (50, 56, 75), rect_all, 1, border_radius=4)
    txt_all = font_small.render("All Nations", True, (255, 255, 255) if mode == 'all' else TEXT)
    surface.blit(txt_all, txt_all.get_rect(center=(rect_all[0] + btn_w // 2, rect_all[1] + btn_h // 2)))
    _PROGRESS_BUTTONS.append((rect_all, 'mode_all', None))

    cur_y += btn_h + 8

    # 4. Gather Items
    active_n = _get_active_nation(world)
    if mode == 'active' and active_n:
        nations_to_show = [active_n]
    else:
        nations_to_show = world.get('nations', [])

    all_items = []
    for n in nations_to_show:
        n_items = _collect_items_for_nation(n, world)
        all_items.extend(n_items)

    # Scroll Controls & Counter
    scroll = world.get('progress_scroll', 0)
    visible_count = 6
    max_scroll = max(0, len(all_items) - visible_count)
    if scroll > max_scroll:
        scroll = max_scroll
        world['progress_scroll'] = scroll

    # Scroll controls row
    btn_up = (x + w - 54, cur_y, 18, 18)
    btn_dn = (x + w - 30, cur_y, 18, 18)
    is_up_hov = btn_up[0] <= mx <= btn_up[0] + 18 and btn_up[1] <= my <= btn_up[1] + 18
    is_dn_hov = btn_dn[0] <= mx <= btn_dn[0] + 18 and btn_dn[1] <= my <= btn_dn[1] + 18

    lbl_count = font_small.render(f"Showing {len(all_items)} Projects", True, DIM)
    surface.blit(lbl_count, (x + 12, cur_y + 1))

    pygame.draw.rect(surface, (45, 50, 70) if is_up_hov else (28, 30, 42), btn_up, border_radius=3)
    lbl_u = font_small.render("▲", True, (255, 255, 255) if is_up_hov else DIM)
    surface.blit(lbl_u, (btn_up[0] + 4, btn_up[1] - 1))
    _PROGRESS_BUTTONS.append((btn_up, 'scroll_up', None))

    pygame.draw.rect(surface, (45, 50, 70) if is_dn_hov else (28, 30, 42), btn_dn, border_radius=3)
    lbl_d = font_small.render("▼", True, (255, 255, 255) if is_dn_hov else DIM)
    surface.blit(lbl_d, (btn_dn[0] + 4, btn_dn[1] - 1))
    _PROGRESS_BUTTONS.append((btn_dn, 'scroll_down', None))

    cur_y += 24

    # 5. Render Visible Item Cards
    visible_slice = all_items[scroll:scroll + visible_count]
    card_w = w - 24
    card_h = 74

    if not visible_slice:
        empty_surf = font_small.render("No active works or research in progress.", True, (140, 145, 165))
        surface.blit(empty_surf, (x + 16, cur_y + 20))
        return

    last_group = None
    for item in visible_slice:
        # Group Header if grouped by nation/province in 'all' mode
        group_key = f"{item['nation']} • {item['province']}"
        if mode == 'all' and group_key != last_group:
            last_group = group_key
            grp_lbl = font_small.render(group_key, True, (245, 200, 100))
            surface.blit(grp_lbl, (x + 14, cur_y + 2))
            cur_y += 18

        card_rect = (x + 12, cur_y, card_w, card_h)
        is_card_hov = card_rect[0] <= mx <= card_rect[0] + card_w and card_rect[1] <= my <= card_rect[1] + card_h

        # Card Background
        bg_col = (30, 34, 48) if is_card_hov else CARD_BG
        pygame.draw.rect(surface, bg_col, card_rect, border_radius=5)
        border_col = (235, 75, 75) if item.get('is_stalled') else (CARD_BORDER if not is_card_hov else (80, 95, 130))
        pygame.draw.rect(surface, border_col, card_rect, 1, border_radius=5)

        # Icon
        ico = get_icon(item.get('icon', 'hammer'), size=16)
        surface.blit(ico, (card_rect[0] + 8, card_rect[1] + 8))

        # Status / Stalled Badge
        pct = min(100.0, max(0.0, item.get('progress_pct', 0.0)))
        turns_left = item.get('turns_left', 0)
        is_stalled = bool(item.get('is_stalled'))

        if is_stalled:
            badge_txt = f"STALLED: {item.get('stall_reason', 'Shortage')}"
            badge_col = (235, 75, 75)
        elif item.get('status') in ('completed', 'mastered', 'enacted'):
            badge_txt = "DONE" if item['status'] == 'completed' else item['status'].upper()
            badge_col = (100, 220, 140)
        else:
            badge_txt = f"{turns_left}t left" if turns_left > 0 else "In Progress"
            badge_col = (245, 180, 60)

        lbl_badge = font_small.render(badge_txt, True, badge_col)
        badge_x = card_rect[0] + card_w - lbl_badge.get_width() - 8
        if is_stalled:
            ico_alert = get_icon('alert', size=12)
            surface.blit(ico_alert, (badge_x - 14, card_rect[1] + 7))
        surface.blit(lbl_badge, (badge_x, card_rect[1] + 6))

        # Title (clamped dynamically to prevent collision with right badge)
        t_col = (255, 255, 255) if is_card_hov else TEXT
        avail_title_w = max(40, (badge_x - 18 if is_stalled else badge_x) - (card_rect[0] + 30) - 6)
        t_str = item['title']
        if font_small.size(t_str)[0] > avail_title_w:
            while len(t_str) > 3 and font_small.size(t_str + "..")[0] > avail_title_w:
                t_str = t_str[:-1]
            t_str += ".."
        lbl_t = font_small.render(t_str, True, t_col)
        surface.blit(lbl_t, (card_rect[0] + 30, card_rect[1] + 6))

        # Subtitle
        lbl_sub = font_small.render(item.get('subtitle', ''), True, (130, 138, 160))
        surface.blit(lbl_sub, (card_rect[0] + 30, card_rect[1] + 24))

        # Progress Bar
        bar_w = card_w - 60
        bar_h = 7
        bar_x = card_rect[0] + 30
        bar_y = card_rect[1] + 46

        pygame.draw.rect(surface, (20, 22, 30), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * (pct / 100.0))
        if fill_w > 0:
            pygame.draw.rect(surface, item.get('bar_color', (245, 180, 50)), (bar_x, bar_y, fill_w, bar_h), border_radius=3)
        pygame.draw.rect(surface, (50, 56, 75), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)

        # Percentage text
        lbl_pct = font_small.render(f"{int(pct)}%", True, (180, 185, 205))
        surface.blit(lbl_pct, (bar_x + bar_w + 6, bar_y - 4))

        # If stalled or distressed construction project: offer one-click Overrun Grant button!
        proj = item.get('project')
        if proj and (item.get('is_stalled') or (proj.contractor and proj.contractor.cash < 5.0)):
            grant_rect = (card_rect[0] + card_w - 78, card_rect[1] + 24, 70, 18)
            is_grant_hov = grant_rect[0] <= mx <= grant_rect[0] + 70 and grant_rect[1] <= my <= grant_rect[1] + 18
            pygame.draw.rect(surface, (70, 45, 45) if is_grant_hov else (50, 32, 32), grant_rect, border_radius=3)
            pygame.draw.rect(surface, (235, 90, 90), grant_rect, 1, border_radius=3)
            lbl_g = font_small.render("+$100 Sub", True, (255, 220, 220))
            surface.blit(lbl_g, lbl_g.get_rect(center=(grant_rect[0] + 35, grant_rect[1] + 9)))
            _PROGRESS_BUTTONS.append((grant_rect, 'subsidize_proj', proj))

        cur_y += card_h + 6

    # Tooltip detection on progress panel action buttons
    if mouse_pos and not world.get('_hovered_left_tooltip'):
        for rect, act_id, payload in _PROGRESS_BUTTONS:
            rx, ry, rw, rh = rect
            if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                from worldview_tooltips import get_button_tooltip_data
                tdata = get_button_tooltip_data(act_id, world, project=payload)
                if tdata:
                    tdata['btn_rect'] = rect
                    world['_hovered_left_tooltip'] = tdata
                break


def progress_panel_hit(pos: tuple[int, int], world: dict) -> bool:
    """Handle mouse clicks inside the Progress Drawer Panel."""
    if not world.get('progress_panel_open', False):
        return False

    mx, my = pos
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H
    if not (x <= mx <= x + w and y <= my <= y + h):
        return False

    # Check Drawer Top 7-tab switcher
    if drawer_top_tabs_hit(pos, world, x, y + 6, w):
        return True

    # Check registered panel buttons
    global _PROGRESS_BUTTONS
    for rect, action, data in _PROGRESS_BUTTONS:
        bx, by, bw, bh = rect
        if bx <= mx <= bx + bw and by <= my <= by + bh:
            if action == 'close':
                close_left_panels(world)
                return True
            elif action == 'mode_active':
                world['progress_view_mode'] = 'active'
                world['progress_scroll'] = 0
                return True
            elif action == 'mode_all':
                world['progress_view_mode'] = 'all'
                world['progress_scroll'] = 0
                return True
            elif action == 'scroll_up':
                world['progress_scroll'] = max(0, world.get('progress_scroll', 0) - 1)
                return True
            elif action == 'scroll_down':
                world['progress_scroll'] = world.get('progress_scroll', 0) + 1
                return True
            elif action == 'subsidize_proj' and data is not None:
                # Disburse $100 emergency overrun grant to stalled/distressed contractor
                from construction_politics import subsidize_contractor
                active_n = _get_active_nation(world)
                if active_n:
                    t = world.get('turn', 1)
                    ok, msg = subsidize_contractor(data, 100.0, active_n, world=world)
                    if ok:
                        world['action_feedback'] = ("Disbursed $100 Overrun Grant!", GREEN, t)
                    else:
                        world['action_feedback'] = (msg, RED, t)
                return True

    return True
