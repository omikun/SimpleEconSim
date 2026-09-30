"""Guided scenario UI composition and reusable priority pressure cards."""

from __future__ import annotations

import pygame
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from worldview_ui import get_font


def scenario_pressures(world: dict) -> list[dict]:
    """Build a compact set of readable national pressures from current sim state."""
    if world.get('scenario_id') == 'egypt_1877':
        return _egypt_scenario_pressures(world)
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


def _egypt_scenario_pressures(world: dict) -> list[dict]:
    nation = next((n for n in world.get('nations', []) if n.name == world.get('player_nation_name')), None)
    if nation is None:
        return [{'title': 'Government unavailable', 'value': 'Select the Egyptian administration.',
                 'cause': 'The scenario needs a player government.', 'tone': 'urgent'}]
    state = world.get('scenario_state', {})
    people = [a for tile in nation.tiles for a in getattr(tile, 'agents', [])
              if getattr(a, 'alive', True) and not getattr(a, 'is_government', False)
              and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_trader', False)]
    hungry = sum(1 for a in people if getattr(a, 'hungry_steps', 0) > 0)
    hunger_rate = hungry / max(1, len(people))
    stock = int(getattr(nation.government, 'food_inventory', 0))
    stock_turns = stock / max(1, int(state.get('relief_units_per_turn', 30)))
    food_tone = 'urgent' if hunger_rate >= 0.15 else ('warning' if stock_turns < 2 else 'good')
    food_value = f'{hunger_rate:.0%} hungry • {stock_turns:.1f} turns of public maize'
    food_cause = 'Reserve release can feed households; it uses finite state stores.'

    payment_turn = int(state.get('payment_window_turn', 6))
    remaining = max(0, payment_turn - int(world.get('turn', 0)))
    payment_status = state.get('payment_status', 'upcoming')
    debt_value = f'{payment_status.title()} • {remaining} turns to payment window'
    confidence = float(state.get('creditor_confidence', 0.6))
    debt_tone = 'urgent' if payment_status == 'deferred' or (remaining <= 1 and payment_status != 'paid') else 'warning'
    debt_cause = f'Creditor confidence {confidence:.0%}; payment draws from the treasury.'

    unrest = sum(float(getattr(r, 'unrest_level', 0.0)) for r in nation.tiles) / max(1, len(nation.tiles))
    legitimacy = float(getattr(nation, 'legitimacy', 0.5))
    political_tone = 'urgent' if legitimacy < 0.30 or unrest >= 0.6 else ('warning' if legitimacy < 0.5 or unrest >= 0.3 else 'good')
    return [
        {'title': 'Household maize access', 'value': food_value, 'cause': food_cause, 'tone': food_tone},
        {'title': 'Debt service', 'value': debt_value, 'cause': debt_cause, 'tone': debt_tone},
        {'title': 'Political support', 'value': f'Legitimacy {legitimacy:.0%} • unrest {unrest:.2f}',
         'cause': 'Hunger and heavier taxes can erode support.', 'tone': political_tone},
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
    scenario_ended = world.get('scenario_id') == 'egypt_1877' and bool(world.get('scenario_state', {}).get('ending'))
    controls = [((MAP_RIGHT - 326, TOP_BAR_H + 9, 46, 28), 'play_pause', 'Pause' if world.get('playing') else 'Play'),
                ((MAP_RIGHT - 274, TOP_BAR_H + 9, 42, 28), 'step_next', 'Next')]
    for rect, action, label in controls:
        if not scenario_ended:
            register_target(world, rect, action, scope='guided')
        hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        pygame.draw.rect(surface, (48, 55, 73) if hover and not scenario_ended else (31, 37, 51), rect, border_radius=3)
        txt = font_small.render(label, True, TEXT if not scenario_ended else DIM)
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
    if world.get('scenario_id') == 'egypt_1877':
        _draw_egypt_scenario_panel(surface, world, mouse_pos=mouse_pos)
        return
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


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    lines = []
    line = ''
    for word in str(text).split():
        trial = f'{line} {word}'.strip()
        if line and font.size(trial)[0] > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _draw_egypt_scenario_panel(surface, world: dict, mouse_pos=None) -> None:
    """Scenario-first briefing, three pressures, and focused action choices."""
    if world.get('scenario_state', {}).get('ending'):
        _draw_egypt_scenario_debrief(surface, world)
        return
    from ui_targets import register_target
    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 14, WIDTH - MAP_RIGHT - 20
    h = HEIGHT - TOP_BAR_H - TICKER_H - 28
    pygame.draw.rect(surface, (25, 28, 38), (x, y, w, h), border_radius=7)
    pygame.draw.rect(surface, (58, 66, 86), (x, y, w, h), 1, border_radius=7)
    title_font, body_font, small_font = get_font(23), get_font(17), get_font(14)
    nation = next((n for n in world.get('nations', []) if n.name == world.get('player_nation_name')), None)
    name = getattr(nation, 'display_name', 'Khedivate of Egypt')
    surface.blit(title_font.render('Situation', True, TEXT), (x + 14, y + 12))
    surface.blit(small_font.render(name, True, ACCENT), (x + 14, y + 39))

    cur_y = y + 61
    briefing = world.get('scenario', {}).get('briefing', ('',))[0]
    brief_rect = pygame.Rect(x + 9, cur_y, w - 18, 86)
    pygame.draw.rect(surface, (32, 37, 50), brief_rect, border_radius=5)
    pygame.draw.rect(surface, (75, 91, 119), brief_rect, 1, border_radius=5)
    for idx, line in enumerate(_wrap_text(briefing, small_font, brief_rect.w - 18)[:4]):
        surface.blit(small_font.render(line, True, TEXT if idx < 3 else DIM), (brief_rect.x + 9, brief_rect.y + 8 + idx * 17))
    cur_y = brief_rect.bottom + 8

    colors = {'urgent': (226, 102, 94), 'warning': (225, 178, 87), 'good': (112, 205, 145), 'neutral': (140, 160, 195)}
    for pressure in scenario_pressures(world):
        card_h = 68
        rect = pygame.Rect(x + 9, cur_y, w - 18, card_h)
        color = colors.get(pressure['tone'], ACCENT)
        pygame.draw.rect(surface, (34, 38, 51), rect, border_radius=5)
        pygame.draw.rect(surface, color, rect, 1, border_radius=5)
        surface.blit(small_font.render(pressure['title'], True, color), (rect.x + 9, rect.y + 6))
        surface.blit(small_font.render(pressure['value'], True, TEXT), (rect.x + 9, rect.y + 25))
        cause = _wrap_text(pressure['cause'], get_font(12), rect.w - 18)
        if cause:
            surface.blit(get_font(12).render(cause[0], True, DIM), (rect.x + 9, rect.y + 46))
        cur_y += card_h + 5

    cur_y += 4
    state = world.get('scenario_state', {})
    turn = int(world.get('turn', 0))
    spent = state.get('last_action_turn') == turn
    stock = int(getattr(getattr(nation, 'government', None), 'food_inventory', 0)) if nation else 0
    suggested = 'Release maize reserves' if stock > 0 else 'Keep more food in Egypt'
    surface.blit(get_font(13).render(f'Suggested first move: {suggested}', True, ACCENT), (x + 13, cur_y))
    cur_y += 19
    surface.blit(body_font.render('Choose one decision this turn', True, TEXT), (x + 13, cur_y))
    cur_y += 24
    payment_ready = turn >= int(state.get('payment_window_turn', 6)) and state.get('payment_status') in ('upcoming', 'unpaid')
    treasury_cash = float(getattr(getattr(getattr(nation, 'government', None), 'agent', None), 'cash', 0.0)) if nation else 0.0
    scheduled_payment = float(state.get('scheduled_remittance', 200.0))
    tax_available = not state.get('tax_decision_taken', False)
    action_rows = [
        [('release_maize', 'Release maize reserves', 'Use public stores to feed households', stock > 0)],
        [('prioritize_domestic_grain', 'Keep more food in Egypt', 'Retain half of food exports in granaries', not state.get('domestic_grain_priority', False))],
        [('reduce_fellahin_tax', 'Reduce local taxes', 'Lower future receipts', tax_available),
         ('raise_local_taxes', 'Raise local taxes', 'More receipts; more unrest', tax_available)],
    ]
    if payment_ready:
        action_rows.extend([
            [('pay_remittance', 'Pay debt service', f'Pay {scheduled_payment:.0f} units to creditors', treasury_cash >= scheduled_payment)],
            [('concede_revenue', 'Concede revenue', f'Pay {scheduled_payment * 0.5:.0f} units; lose autonomy', treasury_cash >= scheduled_payment * 0.5)],
            [('defer_remittance', 'Defer debt service', 'Keep cash now; risk creditor confidence', True)],
        ])
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for row in action_rows:
        button_h = 44
        gap = 5
        button_w = (w - 18 - gap * (len(row) - 1)) // len(row)
        for col, (action_id, label, detail, available) in enumerate(row):
            rect = (x + 9 + col * (button_w + gap), cur_y, button_w, button_h)
            enabled = available and not spent
            if enabled:
                register_target(world, rect, ('scenario_action', action_id), scope='guided')
            hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
            bg = (52, 66, 88) if hover and enabled else ((37, 44, 59) if enabled else (30, 33, 42))
            edge = ACCENT if hover and enabled else ((80, 96, 124) if enabled else (53, 58, 70))
            pygame.draw.rect(surface, bg, rect, border_radius=4)
            pygame.draw.rect(surface, edge, rect, 1, border_radius=4)
            color = TEXT if enabled else DIM
            button_font = get_font(13) if len(row) == 1 else get_font(12)
            surface.blit(button_font.render(label, True, color), (rect[0] + 7, rect[1] + 5))
            detail_font = get_font(12) if len(row) == 1 else get_font(11)
            surface.blit(detail_font.render(detail, True, DIM), (rect[0] + 7, rect[1] + 24))
        cur_y += button_h + 5

    message = world.get('scenario_feedback', '')
    if message:
        lines = _wrap_text(message, get_font(12), w - 28)
        for idx, line in enumerate(lines[:2]):
            surface.blit(get_font(12).render(line, True, ACCENT), (x + 14, y + h - 31 + idx * 14))
    elif spent:
        surface.blit(get_font(12).render('Decision recorded. Advance a turn to see its effects.', True, DIM), (x + 14, y + h - 24))
    else:
        surface.blit(get_font(12).render('Select a district to inspect its details.', True, DIM), (x + 14, y + h - 24))


def _draw_egypt_scenario_debrief(surface, world: dict) -> None:
    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 14, WIDTH - MAP_RIGHT - 20
    h = HEIGHT - TOP_BAR_H - TICKER_H - 28
    pygame.draw.rect(surface, (25, 28, 38), (x, y, w, h), border_radius=7)
    pygame.draw.rect(surface, ACCENT, (x, y, w, h), 1, border_radius=7)
    debrief = world.get('scenario_state', {}).get('debrief', {})
    title_font, body_font, small_font = get_font(25), get_font(17), get_font(14)
    cur_y = y + 18
    surface.blit(title_font.render(debrief.get('title', 'Campaign complete'), True, ACCENT), (x + 14, cur_y))
    cur_y += 39
    for line in _wrap_text(debrief.get('summary', ''), body_font, w - 28)[:4]:
        surface.blit(body_font.render(line, True, TEXT), (x + 14, cur_y))
        cur_y += 22
    cur_y += 8
    for key in ('food', 'debt', 'politics'):
        for line in _wrap_text(debrief.get(key, ''), small_font, w - 28)[:2]:
            surface.blit(small_font.render(line, True, DIM), (x + 14, cur_y))
            cur_y += 19
        cur_y += 4
    cur_y += 9
    surface.blit(body_font.render('Decisions that shaped this result', True, TEXT), (x + 14, cur_y))
    cur_y += 26
    for action in debrief.get('actions', [])[:6]:
        lines = _wrap_text(f'• {action}', small_font, w - 32)
        for line in lines[:2]:
            if cur_y > y + h - 30:
                return
            surface.blit(small_font.render(line, True, TEXT), (x + 17, cur_y))
            cur_y += 18
        cur_y += 4


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

    notice = get_font(16).render('Egypt 1877 • Schematic map; place labels mark scenario roles', True, DIM)
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
        ended = world.get('scenario_id') == 'egypt_1877' and bool(world.get('scenario_state', {}).get('ending'))
        if not ended:
            world['playing'] = not world.get('playing', False)
    elif action == 'step_next':
        from worldview_engine import step_world
        world['playing'] = False
        step_world(world)
    elif isinstance(action, tuple) and action[0] == 'analysis_tab':
        world['analysis_tab'] = action[1]
        world['guided_analysis_open'] = True
    elif isinstance(action, tuple) and action[0] == 'scenario_action':
        from scenario_egypt_1877 import apply_action
        ok, message = apply_action(world, action[1])
        world['scenario_feedback'] = message
        if not ok:
            world['scenario_feedback'] = f"Not enacted: {message}"
        world['needs_redraw'] = True
    elif action == 'open_debt_analysis':
        world['debt_panel_open'] = True
        world['left_panel'] = 'debt'
        world['guided_analysis_open'] = True
        world['analysis_tab'] = 'overview'
    return True
