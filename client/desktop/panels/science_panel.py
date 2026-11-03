"""
worldview_science_panel.py — Left Drawer for Science, Induced Innovation & Royal Bounties.

Duplicates cross-nation innovation functionality from the Sovereign Actions modal:
- National strategic resource endowments ribbon (Iron, Coal, Timber, Petroleum, etc.).
- Era Selector (Era I: Feudal, Era II: Renaissance, Era III: Industrial, Era IV: Modern).
- Technological tree and discovery status:
  - MASTERED (known capability; production benefits require installed equipment)
  - DIFFUSING (Progress from foreign trade partners)
  - ROYAL PRIZE ACTIVE (Bounty posted for researchers)
  - BLOCKED (Missing prerequisites or required strategic resources)
  - PRESSURE (Induced bottleneck pressure & accumulated domain XP)
- Interactive Action: Pledge Royal Science Prize ($300) to incentivize breakthroughs.
"""

from __future__ import annotations
import pygame
from client.desktop.camera import HEIGHT, TOP_BAR_H, TICKER_H
from client.desktop.map.map_renderer import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon, draw_progress_bar_button, draw_icon_badge
from innovation import get_innovation_system, TECH_CATALOG, TechDomain
from tile_resources import TileResource, RESOURCE_META, get_nation_resources
from client.desktop.panels.left_dock import (
    PANEL_X, PANEL_Y, PANEL_W, PANEL_H,
    draw_drawer_top_tabs, drawer_top_tabs_hit,
    open_left_panel, close_left_panels
)
from client.desktop.engine import ticker_push

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
    if enabled:
        from ui_targets import register_target
        clipped = pygame.Rect(rect).clip(surface.get_clip())
        if clipped.width > 0 and clipped.height > 0:
            register_target(world, tuple(clipped), ('science_btn', btn_id), tooltip_id=btn_id, scope='science')
    is_hov = (bx <= mx <= bx + bw and by <= my <= by + bh) and enabled
    if is_hov and btn_id and world is not None:
        from client.desktop.tooltips.core import get_button_tooltip_data
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

    visible = label
    while len(visible) > 2 and font_small.size(visible)[0] > bw - 24:
        visible = visible[:-2] + '…'
    txt_surf = font_small.render(visible, True, tc)
    if icon_kind:
        ico = get_icon(icon_kind, size=13)
        total_w = 13 + 4 + txt_surf.get_width()
        start_x = bx + (bw - total_w) // 2
        surface.blit(ico, (start_x, by + (bh - 13) // 2))
        surface.blit(txt_surf, (start_x + 17, by + (bh - txt_surf.get_height()) // 2))
    else:
        surface.blit(txt_surf, txt_surf.get_rect(center=(bx + bw // 2, by + bh // 2)))


def _draw_engineering_detail(surface, world, nation, tech, x, y, w, font, mouse_pos):
    """A focused detail view keeps program controls out of the tree cards."""
    from engineering import OBJECTIVE_LABELS
    inno = get_innovation_system()
    turn = world.get('turn', 0)
    key = (nation.name, tech.tech_id)
    program = inno.get_engineering_program(*key)
    drafts = world.setdefault('engineering_drafts', {})
    if key not in drafts:
        best = max(nation.tiles, key=lambda tile: sum(b.name in ('workshop', 'engineering_workshop') for b in getattr(tile, 'buildings', ())), default=None)
        drafts[key] = {'budget': program['budget'] or 25, 'objective': program['objective'] if program['budget'] else 'performance',
                       'host': program['host'] or (best.name if best else None)}
    draft = drafts[key]
    e = inno.engineering_status(nation, tech.tech_id, turn,
                               {**draft, 'status': 'active' if draft['budget'] else 'inactive'})
    mx, my = mouse_pos

    def line(text, color=TEXT):
        nonlocal y
        # Wrap to measured width, including narrow drawer layouts.
        words, current = str(text).split(), ''
        for word in words:
            candidate = (current + ' ' + word).strip()
            if current and font.size(candidate)[0] > w - 32:
                surface.blit(font.render(current, True, color), (x + 16, y))
                y += 17
                current = word
            else:
                current = candidate
        if current:
            surface.blit(font.render(current, True, color), (x + 16, y))
            y += 19

    def button(label, action, enabled=True):
        nonlocal y
        _draw_btn(surface, (x + 16, y, w - 32, 24), label, font, mx, my,
                  enabled=enabled, btn_id='sci_eng_' + action, world=world, nation=nation)
        y += 29

    button('Back to technology tree', 'back')
    _draw_btn(surface, (x + 16, y, (w - 38) // 2, 24), 'Scroll up', font, mx, my,
              btn_id='sci_eng_up', world=world, nation=nation)
    _draw_btn(surface, (x + 22 + (w - 38) // 2, y, (w - 38) // 2, 24), 'Scroll down', font, mx, my,
              btn_id='sci_eng_down', world=world, nation=nation)
    y += 32
    top = y
    old_clip = surface.get_clip()
    surface.set_clip(pygame.Rect(x + 8, top, w - 16, max(1, PANEL_Y + PANEL_H - top - 8)).clip(old_clip))
    scroll = world.get('engineering_detail_scroll', 0)
    y -= scroll
    line(tech.name, ACCENT)
    line(f"Capability: {e['capability_name']} (Tier {inno.get_tech_tier(nation.name, tech.tech_id)}/4)")
    line(f"Commercial maturity: {e['maturity_name']} ({e['maturity']:.0f}%)")
    if tech.production_modifiers:
        from goods import Goods
        line('Installed equipment helps: ' + ', '.join(
            f"{Goods(good).name.replace('_', ' ')} +{(value - 1) * 100:.0f}%"
            for good, value in tech.production_modifiers.items()) + ' at frontier capability.', DIM)
    line(f"{e['operating_installations']} operating installations; {e['utilization']:.0%} utilization", DIM)
    button(OBJECTIVE_LABELS[draft['objective']], 'objective')
    button(f"Budget ceiling: {draft['budget']:.0f}/turn (click to change)", 'budget')
    host_label = next((getattr(tile, 'display_name', tile.name) for tile in nation.tiles if tile.name == draft['host']), 'No territory')
    button(f"Host: {host_label} (click to change)", 'host', bool(nation.tiles))
    forecast = e['forecast']
    target = 'economy' if draft['objective'] == 'economy' else 'capability'
    def turns(value):
        return 'no progress' if value is None else 'reached' if value == 0 else f'~{value} turns'
    line(f"Next {'cost reduction' if target == 'economy' else 'capability'}: {turns(forecast[target + '_turns'])}")
    line(f"Industry alone: {turns(forecast[target + '_turns_without_program'])}; expected spending {e['expected_spend']:.0f}/turn", DIM)
    line(e['constraint'] or 'Forecast assumes current operation, staff and supplies.', DIM)
    for decision in e.get('commercial_decisions', ()):
        line(f"{decision['firm']} (turn {decision['turn']}): {decision['reason_text']}", DIM)
        if decision.get('installed_generation'):
            line(f"Installed tier {decision['installed_generation']}", DIM)
        line(f"Investment {decision['cost']:.0f}; estimated extra receipts {decision['expected_gain_per_turn']:.1f}/turn", DIM)
        if decision.get('constraint'):
            line(decision['constraint'], DIM)
    button('Fund to next milestone', 'apply', bool(nation.tiles))
    button('Stop public funding', 'stop', program['status'] == 'active')
    button('Build testing workshop (300)', 'workshop', bool(nation.tiles))
    button('Acquire foreign designs (+1 tier)', 'steal')
    if inno.get_guild_blockade(nation, tech.tech_id)['active']:
        button('Repeal incumbent guild blockade', 'guild')
    if inno.has_tech(nation.name, tech.tech_id):
        from engineering import quote_recipe
        from buildings import BUILDING_RECIPES
        quote = quote_recipe(nation, BUILDING_RECIPES[tech.tech_id + '_prototype'], inno)
        button(f'Build pilot installation ({quote.cost:.0f})', 'pilot')
        options = inno.adoption_options(nation, tech.tech_id)
        if options:
            choice = world.get('engineering_adoption_index', 0) % len(options)
            option = options[choice]
            button(f"Upgrade {option['building']} / {option.get('tile_label', option['tile'])} (cycle)", 'adoption')
            line(f"Cost {option['cost']:.0f}; at least 2 turns offline. Extra output value ~{option['gross_value_per_turn']:.0f}/turn.", DIM)
            button('Commission selected retrofit', 'retrofit')
    world['engineering_detail_scroll_max'] = max(0, y + scroll - (PANEL_Y + PANEL_H - 8))
    surface.set_clip(old_clip)


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
    from ui_targets import register_target
    register_target(world, close_rect, 'close_left', scope='science')
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
            from client.desktop.tooltips.core import get_button_tooltip_data
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
        from ui_targets import register_target
        register_target(world, e_rect, ('science_era', e_num), tooltip_id=f"sci_era_{e_num}", scope='science')
        is_sel = (cur_era == e_num)
        is_hov = e_rect[0] <= mx <= e_rect[0] + era_w and e_rect[1] <= my <= e_rect[1] + 24
        if is_hov and world is not None:
            from client.desktop.tooltips.core import get_button_tooltip_data
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

    detail = TECH_CATALOG.get(world.get('science_detail_tech'))
    if detail is not None and detail.era == cur_era:
        _draw_engineering_detail(surface, world, active_n, detail, x, cur_y, w,
                                 font_small, (mx, my))
        return

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

        tier = inno.get_tech_tier(active_n.name, tech_id)
        ref_xp = inno.get_refinement_xp(active_n.name, tech_id)
        sub_mode = inno.get_subsidy_mode(active_n.name, tech_id)
        g_block = inno.get_guild_blockade(active_n.name, tech_id)

        # Status badge
        if is_disc:
            maturity = inno.get_commercial_maturity(active_n.name, tech_id)
            badge_txt = f"CAPABILITY {max(1, tier)}/4 | MATURITY {maturity:.0f}%"
            if g_block.get('active'):
                badge_txt += " • GUILD BLOCK"
                badge_col = (245, 130, 130)
            else:
                badge_col = GREEN
        elif diff_prog > 0:
            badge_txt = f"DIFFUSING ({int(diff_prog*100)}%) • T{tier}"
            badge_col = (80, 200, 255)
        elif has_bounty:
            badge_txt = f"PRIZE ACTIVE • {sub_mode[:4].upper()}"
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

        # Top-right compact Steal / Subsidy / Guild button
        aux_rect = (x + w - 82, cur_y + 6, 66, 18)
        _draw_btn(surface, aux_rect, 'Details', font_small, mx, my,
                  btn_id=f'sci_detail_{tech_id}', world=world, nation=active_n)

        # Badge
        b_surf = font_small.render(f"[{badge_txt}]", True, badge_col)
        surface.blit(b_surf, (x + 16, cur_y + 26))

        # Action Button or Progress Bar
        btn_rect = (x + 16, cur_y + 46, w - 32, 26)

        # Card & button hover detection
        is_card_hov = card_rect[0] <= mx <= card_rect[0] + card_rect[2] and card_rect[1] <= my <= card_rect[1] + card_rect[3]
        is_btn_hov = btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]
        if is_card_hov and world is not None and not is_btn_hov:
            from client.desktop.tooltips.core import get_button_tooltip_data
            tdata = get_button_tooltip_data(f"tech_{tech_id}", world, nation=active_n)
            if tdata:
                tdata['btn_rect'] = card_rect
                world['_hovered_left_tooltip'] = tdata

        if is_disc:
            ref_pct = min(1.0, max(0.05, ref_xp / 100.0))
            _draw_btn(surface, btn_rect, 'Engineering program & adoption', font_small, mx, my,
                      btn_id=f'sci_detail_{tech_id}', world=world, nation=active_n)
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
            _draw_btn(surface, btn_rect, 'Develop a working prototype', font_small, mx, my,
                      enabled=True, color=ACCENT,
                      btn_id=f'sci_detail_{tech_id}', world=world, nation=active_n)

        cur_y += t_card_h + 8


def science_panel_hit(pos: tuple[int, int], world: dict) -> bool:
    """Hit-test and interactive execution for Left Science Drawer."""
    if not world.get('science_panel_open', False):
        return False

    if world is not None:
        from ui_targets import find_target
        t = find_target(world, pos, scope='science')
        if t is not None:
            if t.action == 'close_left':
                from client.desktop.panels.left_dock import close_left_panels
                close_left_panels(world)
                return True
            elif isinstance(t.action, tuple) and t.action[0] == 'science_era':
                world['innovation_era'] = t.action[1]
                return True
            elif isinstance(t.action, tuple) and t.action[0] == 'science_btn':
                btn_id = t.action[1]
                if btn_id and btn_id.startswith('sci_detail_'):
                    world['science_detail_tech'] = btn_id[len('sci_detail_'):]
                    world['engineering_adoption_index'] = 0
                    world['engineering_detail_scroll'] = 0
                    return True
                if btn_id and btn_id.startswith('sci_eng_'):
                    action = btn_id[len('sci_eng_'):]
                    if action in ('up', 'down'):
                        world['engineering_detail_scroll'] = max(0, min(
                            world.get('engineering_detail_scroll_max', 0),
                            world.get('engineering_detail_scroll', 0) + (120 if action == 'down' else -120)))
                        return True
                    if action == 'back':
                        world.pop('science_detail_tech', None)
                        return True
                    nation = _get_active_nation(world)
                    tid = world.get('science_detail_tech')
                    if nation is None or tid not in TECH_CATALOG:
                        return True
                    draft = world['engineering_drafts'][nation.name, tid]
                    inno = get_innovation_system()
                    if action == 'objective':
                        choices = ['performance', 'balanced', 'economy'] if inno.has_tech(nation.name, tid) else ['performance', 'balanced']
                        draft['objective'] = choices[(choices.index(draft['objective']) + 1) % len(choices)]
                    elif action == 'budget':
                        choices = [0, 25, 50, 100, 200]
                        draft['budget'] = next((v for v in choices if v > draft['budget']), 0)
                    elif action == 'host':
                        names = [tile.name for tile in nation.tiles]
                        draft['host'] = names[(names.index(draft['host']) + 1) % len(names)] if draft['host'] in names else names[0]
                    elif action == 'adoption':
                        world['engineering_adoption_index'] = world.get('engineering_adoption_index', 0) + 1
                    else:
                        turn = world.get('turn', 0)
                        if action in ('apply', 'stop'):
                            ok, msg = inno.set_engineering_program(nation, tid,
                                draft['budget'] if action == 'apply' else 0, draft['objective'], draft['host'], turn)
                        elif action in ('workshop', 'pilot'):
                            from intents import BuildIntent
                            recipe = 'engineering_workshop' if action == 'workshop' else tid + '_prototype'
                            intent = BuildIntent(nation.name, draft['host'], recipe, submitted_turn=turn)
                            ok, msg = intent.execute({r.name: r for r in nation.tiles}, {nation.name: nation}, turn)
                        elif action == 'retrofit':
                            options = inno.adoption_options(nation, tid)
                            if not options:
                                return True
                            option = options[world.get('engineering_adoption_index', 0) % len(options)]
                            ok, msg = inno.commission_retrofit(nation, tid, option['tile'], option['building_index'], turn)
                        elif action == 'steal':
                            ok, msg = inno.attempt_tech_espionage(nation, tid, t=turn, nations=world.get('nations', []))
                        elif action == 'guild':
                            ok, msg = inno.resolve_guild_blockade(nation, tid, 'repeal', t=turn)
                        else:
                            return True
                        ticker_push(world, turn, 'INNOVATION', msg, GREEN if ok else RED)
                    return True
                if btn_id and btn_id.startswith('sci_pledge_'):
                    tech_id = btn_id.replace('sci_pledge_', '')
                    active_n = _get_active_nation(world)
                    if active_n:
                        inno = get_innovation_system()
                        turn = world.get('turn', 0)
                        tech = TECH_CATALOG.get(tech_id)
                        ok = inno.post_royal_bounty(active_n, tech_id, 300.0, turn)
                        if ok and tech:
                            ticker_push(world, turn, 'INNOVATION', f"{active_n.name} established a $300 Royal Innovation Prize for {tech.name}!", (80, 200, 255))
                    return True
                elif btn_id and btn_id.startswith('sci_steal_'):
                    tech_id = btn_id.replace('sci_steal_', '')
                    active_n = _get_active_nation(world)
                    if active_n:
                        inno = get_innovation_system()
                        turn = world.get('turn', 0)
                        ok, msg = inno.attempt_tech_espionage(active_n, tech_id, t=turn, nations=world.get('nations', []))
                        ticker_push(world, turn, 'INNOVATION', msg, (255, 200, 90))
                    return True
                elif btn_id and btn_id.startswith('sci_guild_'):
                    tech_id = btn_id.replace('sci_guild_', '')
                    active_n = _get_active_nation(world)
                    if active_n:
                        inno = get_innovation_system()
                        turn = world.get('turn', 0)
                        ok, msg = inno.resolve_guild_blockade(active_n, tech_id, 'repeal', t=turn)
                        ticker_push(world, turn, 'INNOVATION', msg, (120, 235, 160))
                    return True
                elif btn_id and btn_id.startswith('sci_sub_'):
                    tech_id = btn_id.replace('sci_sub_', '')
                    active_n = _get_active_nation(world)
                    if active_n:
                        inno = get_innovation_system()
                        turn = world.get('turn', 0)
                        cur_m = inno.get_subsidy_mode(active_n.name, tech_id)
                        order = ['commercial', 'standard', 'crash']
                        nxt_m = order[(order.index(cur_m) + 1) % len(order)] if cur_m in order else 'standard'
                        inno.set_subsidy_mode(active_n, tech_id, nxt_m, t=turn)
                        ticker_push(world, turn, 'INNOVATION', f"{active_n.name} switched {tech_id} R&D mode to {nxt_m}.", (120, 200, 255))
                    return True

    # Legacy fallback calculation
    mx, my = pos
    x, y, w, h = PANEL_X, PANEL_Y, PANEL_W, PANEL_H

    if not (x <= mx <= x + w and y <= my <= y + h):
        return False

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    if close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18:
        from client.desktop.panels.left_dock import close_left_panels
        close_left_panels(world)
        return True

    # Drawer Top Switcher
    from client.desktop.panels.left_dock import drawer_top_tabs_hit
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
