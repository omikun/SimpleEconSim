"""Guided scenario UI composition and reusable priority pressure cards."""

from __future__ import annotations

import pygame
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from worldview_ui import get_font


def scenario_pressures(world: dict) -> list[dict]:
    """Build a compact set of readable national pressures from current sim state."""
    nation = world.get('selected_nation')
    if nation is None:
        nation = next((n for n in world.get('nations', []) if n.name == world.get('player_nation_name')), None)
    if nation is None and world.get('nations'):
        nation = world['nations'][0]
    tiles = list(getattr(nation, 'tiles', [])) if nation else []
    if not tiles:
        return [{'title': 'Choose a nation', 'value': 'Select a nation to review its situation.',
                 'cause': 'National decisions and pressures are shown for the selected country.', 'tone': 'neutral'}]

    agents = [a for tile in tiles for a in getattr(tile, 'agents', [])
              if getattr(a, 'alive', True) and not getattr(a, 'is_government', False)
              and not getattr(a, 'is_corporation', False)]
    hungry = sum(1 for a in agents if getattr(a, 'hungry_steps', 0) > 0)
    hunger_rate = hungry / max(1, len(agents))
    treasury = nation.treasury().get('total', 0.0)
    protest = sum((r.protest_energy_log[-1] if getattr(r, 'protest_energy_log', []) else 0.0) for r in tiles) / len(tiles)
    food_price = sum(r.recipes.get(__import__('goods').Goods.food, {}).get('price', 1.0) for r in tiles) / len(tiles)
    currency = getattr(nation, 'currency', '')

    if hunger_rate >= 0.15:
        food_tone, food_text = 'urgent', f'{hunger_rate:.0%} of people went hungry last turn'
        food_cause = 'Households cannot reliably afford or gather enough food.'
    elif food_price >= 2.0:
        food_tone, food_text = 'warning', f'Food prices are high ({food_price:.1f})'
        food_cause = 'High prices can push more households into hunger.'
    else:
        food_tone, food_text = 'good', f'Food prices are stable ({food_price:.1f})'
        food_cause = 'Keep watching prices and household access as policy changes.'

    try:
        from sovereign_bonds import get_bond_market
        coupons = sum(b.per_turn_coupon for b in get_bond_market().get_bonds_owed_by(nation.name))
    except Exception:
        coupons = 0.0
    fiscal_tone = 'urgent' if treasury < max(100.0, coupons * 8) else ('warning' if coupons else 'good')
    fiscal_text = f'${treasury:,.0f} {currency} available'
    fiscal_cause = (f'Bond coupons require about ${coupons:,.0f} each turn.' if coupons
                    else 'No active bond coupon is reported for this country.')

    stability_tone = 'urgent' if protest >= 6.5 else ('warning' if protest >= 3.5 else 'good')
    stability_text = f'Popular pressure {protest:.1f} / 10'
    stability_cause = 'Hunger, land loss, and repression can raise organized resistance.'
    return [
        {'title': 'Household food access', 'value': food_text, 'cause': food_cause, 'tone': food_tone},
        {'title': 'Treasury & debt', 'value': fiscal_text, 'cause': fiscal_cause, 'tone': fiscal_tone},
        {'title': 'Political support', 'value': stability_text, 'cause': stability_cause, 'tone': stability_tone},
    ]


def draw_guided_header(surface, world: dict, font_small, mouse_pos=None) -> None:
    """Draw turn objective and simple composition controls above the map."""
    pygame.draw.rect(surface, (21, 25, 34), (0, TOP_BAR_H, MAP_RIGHT, 48))
    pygame.draw.line(surface, (64, 73, 94), (0, TOP_BAR_H + 47), (MAP_RIGHT, TOP_BAR_H + 47), 1)
    title = font_small.render('EGYPT 1877  •  Protect food access, preserve government capacity', True, (235, 225, 190))
    surface.blit(title, (18, TOP_BAR_H + 7))
    turn = world.get('turn', 0)
    turn_text = font_small.render(f'Turn {turn} / 20', True, ACCENT)
    surface.blit(turn_text, (18, TOP_BAR_H + 27))
    analysis_rect = (MAP_RIGHT - 220, TOP_BAR_H + 8, 98, 28)
    settings_rect = (MAP_RIGHT - 112, TOP_BAR_H + 8, 96, 28)
    from ui_targets import register_target
    register_target(world, analysis_rect, 'toggle_guided_analysis', scope='guided')
    register_target(world, settings_rect, 'open_settings', scope='guided')
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for rect, label in ((analysis_rect, 'Analysis'), (settings_rect, 'Settings')):
        hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        pygame.draw.rect(surface, (48, 55, 73) if hover else (31, 37, 51), rect, border_radius=4)
        pygame.draw.rect(surface, ACCENT if hover else (76, 88, 112), rect, 1, border_radius=4)
        text = font_small.render(label, True, TEXT)
        surface.blit(text, text.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))
    controls = [((MAP_RIGHT - 326, TOP_BAR_H + 9, 46, 28), 'play_pause', 'Pause' if world.get('playing') else 'Play'),
                ((MAP_RIGHT - 274, TOP_BAR_H + 9, 42, 28), 'step_next', 'Next')]
    for rect, action, label in controls:
        register_target(world, rect, action, scope='guided')
        hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        pygame.draw.rect(surface, (48, 55, 73) if hover else (31, 37, 51), rect, border_radius=3)
        txt = font_small.render(label, True, TEXT)
        surface.blit(txt, txt.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))
    if world.get('guided_analysis_open'):
        analysis_tabs = [('overview', 'Overview'), ('land', 'Land'), ('people', 'People')]
        for idx, (tab, label) in enumerate(analysis_tabs):
            rect = (MAP_RIGHT + 10 + idx * 108, TOP_BAR_H + 60, 102, 24)
            register_target(world, rect, ('analysis_tab', tab), scope='guided')
            active = world.get('analysis_tab', 'overview') == tab
            pygame.draw.rect(surface, (53, 68, 92) if active else (30, 36, 48), rect, border_radius=4)
            txt = font_small.render(label, True, TEXT if active else DIM)
            surface.blit(txt, txt.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))


def draw_pressure_panel(surface, world: dict, mouse_pos=None) -> None:
    """Show three priority pressures in a narrow readable right-side stack."""
    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 14, WIDTH - MAP_RIGHT - 20
    h = HEIGHT - TOP_BAR_H - TICKER_H - 28
    pygame.draw.rect(surface, (25, 28, 38), (x, y, w, h), border_radius=7)
    pygame.draw.rect(surface, (58, 66, 86), (x, y, w, h), 1, border_radius=7)
    title_font, body_font, small_font = get_font(24), get_font(19), get_font(16)
    title = title_font.render('Situation', True, (245, 245, 250))
    surface.blit(title, (x + 14, y + 14))
    nation = world.get('selected_nation')
    nation_name = getattr(nation, 'name', world.get('player_nation_name', 'Select a nation'))
    sub = small_font.render(nation_name, True, ACCENT)
    surface.blit(sub, (x + 14, y + 42))
    cur_y = y + 68
    colors = {'urgent': (226, 102, 94), 'warning': (225, 178, 87), 'good': (112, 205, 145), 'neutral': (140, 160, 195)}
    for pressure in scenario_pressures(world):
        color = colors.get(pressure['tone'], ACCENT)
        card_h = 87
        rect = (x + 9, cur_y, w - 18, card_h)
        pygame.draw.rect(surface, (34, 38, 51), rect, border_radius=5)
        pygame.draw.rect(surface, color, rect, 1, border_radius=5)
        head = body_font.render(pressure['title'], True, color)
        surface.blit(head, (rect[0] + 10, rect[1] + 10))
        value = small_font.render(pressure['value'], True, TEXT)
        surface.blit(value, (rect[0] + 10, rect[1] + 38))
        words = pressure['cause'].split()
        line, lines = '', []
        for word in words:
            trial = (line + ' ' + word).strip()
            if small_font.size(trial)[0] > w - 42 and line:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        for idx, text in enumerate(lines[:1]):
            rendered = small_font.render(text, True, DIM)
            surface.blit(rendered, (rect[0] + 10, rect[1] + 61 + idx * 14))
        cur_y += card_h + 6
    decisions_y = min(cur_y + 5, y + h - 166)
    decisions_title = body_font.render('Decisions', True, (245, 245, 250))
    surface.blit(decisions_title, (x + 14, decisions_y))
    choices = [
        ('analysis_tab', 'Review current policies', 'overview'),
        ('analysis_tab', 'Inspect land & commons', 'land'),
        ('open_debt_analysis', 'Inspect debt & bonds', None),
    ]
    for idx, (action, label, value) in enumerate(choices):
        rect = (x + 10, decisions_y + 32 + idx * 37, w - 20, 31)
        from ui_targets import register_target
        register_target(world, rect, (action, value) if value is not None else action, scope='guided')
        mx, my = mouse_pos if mouse_pos else (-1, -1)
        hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        pygame.draw.rect(surface, (49, 59, 77) if hover else (36, 42, 56), rect, border_radius=4)
        pygame.draw.rect(surface, (92, 112, 144), rect, 1, border_radius=4)
        txt = small_font.render(label, True, TEXT)
        surface.blit(txt, txt.get_rect(midleft=(rect[0] + 10, rect[1] + rect[3] // 2)))
    if world.get('scenario_feedback'):
        feedback = small_font.render(world['scenario_feedback'], True, ACCENT)
        surface.blit(feedback, (x + 14, y + h - 24))
    else:
        hint = small_font.render('Select a district to inspect it.', True, DIM)
        surface.blit(hint, (x + 14, y + h - 24))


def draw_guided_frame(surface, world: dict, font, font_small, mouse_pos=None) -> None:
    """Compose Guided mode from reusable overview components."""
    from worldview import _draw_cached_map  # lazy import avoids module-load cycle
    from worldview_map import draw_dynamic_map_overlays
    from worldview_ui import draw_ticker

    _draw_cached_map(surface, world, font, font_small)
    draw_dynamic_map_overlays(surface, world)
    labels = world.get('_ui_map_label_surface')
    if labels is not None:
        surface.blit(labels, (0, 0), pygame.Rect(0, TOP_BAR_H, MAP_RIGHT, HEIGHT - TOP_BAR_H - TICKER_H))
    pygame.draw.rect(surface, (12, 14, 20), (0, 0, WIDTH, TOP_BAR_H))
    pygame.draw.line(surface, (58, 66, 86), (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 1)
    world['_hovered_topbar_dropdown'] = None
    draw_guided_header(surface, world, font_small, mouse_pos=mouse_pos)
    draw_pressure_panel(surface, world, mouse_pos=mouse_pos)
    draw_ticker(surface, world, font_small)

    notice = get_font(16).render('Guided overview • Nile failure and debt-service crisis scenario', True, DIM)
    surface.blit(notice, (18, HEIGHT - TICKER_H - 24))

    if world.get('guided_analysis_open'):
        # Existing expert panels are reused intact inside the Analysis composition.
        from worldview_ui import draw_panel
        from worldview_charts import draw_chart_grid, draw_chart_large, tile_charts
        from worldview_cadastre import draw_cadastre_panel
        from worldview_citizens import draw_citizens_panel
        selected = world.get('selected_region')
        if world.get('analysis_tab', 'overview') == 'land':
            draw_cadastre_panel(surface, world, selected, font, font_small, mouse_pos=mouse_pos)
        elif world.get('analysis_tab') == 'people':
            draw_citizens_panel(surface, world, selected, font, font_small, mouse_pos=mouse_pos)
        else:
            draw_panel(surface, world, font, font_small, mouse_pos=mouse_pos)

    if world.get('settings_open'):
        draw_settings_dialog(surface, world, font_small, mouse_pos)


def draw_settings_dialog(surface, world: dict, font_small, mouse_pos=None) -> None:
    """Small settings dialog for switching Guided and Advanced UI composition."""
    from ui_targets import register_target
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((7, 9, 14, 190))
    surface.blit(overlay, (0, 0))
    rect = pygame.Rect(WIDTH // 2 - 240, HEIGHT // 2 - 145, 480, 290)
    pygame.draw.rect(surface, (25, 29, 40), rect, border_radius=8)
    pygame.draw.rect(surface, (95, 108, 136), rect, 1, border_radius=8)
    title = get_font(27).render('Interface settings', True, TEXT)
    surface.blit(title, (rect.x + 22, rect.y + 20))
    desc = get_font(18).render('Choose how much of the simulation UI is shown by default.', True, DIM)
    surface.blit(desc, (rect.x + 22, rect.y + 58))
    buttons = [((rect.x + 22, rect.y + 112, 204, 64), 'guided', 'Guided', 'Scenario first'),
               ((rect.x + 254, rect.y + 112, 204, 64), 'advanced', 'Advanced', 'Full system panels')]
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for btn, mode, label, subtitle in buttons:
        register_target(world, btn, ('set_ui_mode', mode), scope='settings')
        chosen = world.get('ui_mode', 'advanced') == mode
        hover = btn[0] <= mx <= btn[0] + btn[2] and btn[1] <= my <= btn[1] + btn[3]
        color = ACCENT if chosen else ((91, 112, 151) if hover else (68, 78, 100))
        pygame.draw.rect(surface, (40, 50, 70), btn, border_radius=6)
        pygame.draw.rect(surface, color, btn, 2 if chosen else 1, border_radius=6)
        l = get_font(22).render(label, True, TEXT)
        s = get_font(16).render(subtitle, True, DIM)
        surface.blit(l, l.get_rect(center=(btn[0] + btn[2] // 2, btn[1] + 24)))
        surface.blit(s, s.get_rect(center=(btn[0] + btn[2] // 2, btn[1] + 47)))
    close_rect = (rect.x + rect.w - 110, rect.y + rect.h - 52, 88, 32)
    register_target(world, close_rect, 'close_settings', scope='settings')
    pygame.draw.rect(surface, (47, 53, 69), close_rect, border_radius=4)
    close = get_font(18).render('Done', True, TEXT)
    surface.blit(close, close.get_rect(center=(close_rect[0] + close_rect[2] // 2, close_rect[1] + close_rect[3] // 2)))


def guided_ui_hit(pos, world: dict) -> bool:
    """Handle Guided composition and settings actions."""
    from ui_targets import find_target
    target = find_target(world, pos, scope='settings' if world.get('settings_open') else 'guided')
    if target is None:
        if world.get('settings_open'):
            world['settings_open'] = False
            return True
        return False
    action = target.action
    if isinstance(action, tuple) and action[0] == 'set_ui_mode':
        from world_config import set_ui_mode
        world['ui_mode'] = set_ui_mode(action[1])
    elif action == 'open_settings':
        world['settings_open'] = True
    elif action == 'close_settings':
        world['settings_open'] = False
    elif action == 'toggle_guided_analysis':
        world['guided_analysis_open'] = not world.get('guided_analysis_open', False)
    elif action == 'play_pause':
        world['playing'] = not world.get('playing', False)
    elif action == 'step_next':
        from worldview_engine import step_world
        world['playing'] = False
        step_world(world)
    elif isinstance(action, tuple) and action[0] == 'analysis_tab':
        world['analysis_tab'] = action[1]
        world['guided_analysis_open'] = True
    elif action == 'open_debt_analysis':
        world['debt_panel_open'] = True
        world['left_panel'] = 'debt'
        world['guided_analysis_open'] = True
        world['analysis_tab'] = 'overview'
    return True
