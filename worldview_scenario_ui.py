"""Guided scenario UI composition and reusable priority pressure cards."""

from __future__ import annotations

import math
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
    nation = _egypt_nation(world)
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
    cash = float(getattr(nation.government.agent, 'cash', 0.0))
    remittance = float(state.get('scheduled_remittance', 200.0))
    confidence = float(state.get('creditor_confidence', 0.6))
    if payment_status in ('upcoming', 'unpaid'):
        debt_value = (f'Due now • {remittance:.0f} cash needed' if remaining == 0
                      else f'{remaining} turns to payment • {cash:.0f} cash')
        debt_cause = f'Pay {remittance:.0f}, concede {remittance / 2:.0f}, or defer; creditor confidence {confidence:.0%}.'
    else:
        debt_value = f'{payment_status.title()} • creditor confidence {confidence:.0%}'
        debt_cause = f'Treasury cash {cash:.0f}; fiscal autonomy {float(state.get("fiscal_autonomy", 1.0)):.0%}.'
    debt_tone = 'urgent' if payment_status in ('deferred', 'defaulted') or (remaining <= 1 and payment_status in ('upcoming', 'unpaid')) else 'warning'

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


def _scenario_font(pixel_size: float):
    """Request a font that renders at the pixel size used by this panel."""
    # get_font applies a 0.65 calibration for the rest of the interface.
    return get_font(max(9, math.ceil(pixel_size / 0.65)))


def _egypt_nation(world: dict):
    return next((n for n in world.get('nations', []) if n.name == world.get('player_nation_name')), None)


def _guided_action_preview(world: dict, nation, action_id: str) -> tuple[str, list[str]]:
    """Describe immediate rule changes separately from later simulation effects."""
    if nation is None:
        return ('Government unavailable', ['The Egyptian administration is unavailable.'])
    state = world.get('scenario_state', {})
    stock = int(getattr(nation.government, 'food_inventory', 0))
    cash = float(nation.government.agent.cash)
    confidence = float(state.get('creditor_confidence', 0.6))
    autonomy = float(state.get('fiscal_autonomy', 1.0))
    legitimacy = float(getattr(nation, 'legitimacy', 0.5))
    tiles = list(nation.tiles)
    unrest = sum(float(getattr(tile, 'unrest_level', 0.0)) for tile in tiles) / max(1, len(tiles))
    if action_id == 'release_maize':
        households = [a for tile in tiles for a in getattr(tile, 'agents', [])
                      if getattr(a, 'alive', True) and not getattr(a, 'is_government', False)
                      and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_trader', False)]
        rations = min(stock, int(state.get('relief_units_per_turn', 30)), len(households))
        return (f'Feed {rations} • stores {stock}→{stock - rations}', [
            f'Now: give {rations} households one maize ration; public stores {stock} → {stock - rations}.',
            'Hungry households receive rations first. Their current hunger streak resets if reached.',
            'Next turns: fewer public rations remain; future hunger still depends on harvests and prices.',
        ])
    if action_id == 'prioritize_domestic_grain':
        return (f'Keep 50% • credit {confidence:.0%}→{max(0, confidence - .10):.0%}', [
            'Now: set each Egyptian district to retain 50% of food for local supply.',
            f'Creditor confidence {confidence:.0%} → {max(0, confidence - .10):.0%}.',
            'Next turns: local food supply can improve, while export receipts may fall.',
        ])
    if action_id == 'reduce_fellahin_tax':
        next_unrest = sum(max(0, float(getattr(tile, 'unrest_level', 0.0)) - .08) for tile in tiles) / max(1, len(tiles))
        return ('Tax −3pp • unrest ↓', [
            'Now: district tax rates fall by up to 3 percentage points (floor 0).',
            f'Average unrest {unrest:.2f} → {next_unrest:.2f}; legitimacy {legitimacy:.0%} → {min(1, legitimacy + .04):.0%}.',
            'Next turns: households keep more income; government tax receipts may fall.',
        ])
    if action_id == 'raise_local_taxes':
        next_unrest = sum(min(1, float(getattr(tile, 'unrest_level', 0.0)) + .12) for tile in tiles) / max(1, len(tiles))
        return ('Tax +5pp • unrest ↑', [
            'Now: district tax rates rise by up to 5 percentage points (cap 60%).',
            f'Average unrest {unrest:.2f} → {next_unrest:.2f}; legitimacy {legitimacy:.0%} → {max(0, legitimacy - .08):.0%}.',
            'Next turns: tax receipts may rise; this also counts as coercive extraction.',
        ])
    amount = float(state.get('scheduled_remittance', 200.0))
    if action_id == 'pay_remittance':
        if int(world.get('turn', 0)) < int(state.get('payment_window_turn', 6)):
            payment_turn = int(state.get('payment_window_turn', 6))
            return (f'Due on turn {payment_turn} • {amount:.0f} units', [
                f'The payment window opens on turn {payment_turn}; this button is unavailable until then.',
                f'If paid, treasury cash will change from {cash:.0f} to {cash - amount:.0f}; creditor confidence rises by 15 percentage points.',
            ])
        return (f'Cash {cash:.0f}→{cash - amount:.0f} • credit +15pp', [
            f'Now: treasury cash {cash:.0f} → {cash - amount:.0f}; debt service marked paid.',
            f'Creditor confidence {confidence:.0%} → {min(1, confidence + .15):.0%}.',
            'Tradeoff: less cash remains for domestic needs; fiscal autonomy stays intact.',
        ])
    if action_id == 'concede_revenue':
        amount *= .5
        return (f'Cash {cash:.0f}→{cash - amount:.0f} • autonomy −25pp', [
            f'Now: treasury cash {cash:.0f} → {cash - amount:.0f}; debt service restructured.',
            f'Creditor confidence {confidence:.0%} → {min(1, confidence + .15):.0%}.',
            f'Fiscal autonomy {autonomy:.0%} → {max(0, autonomy - .25):.0%} under creditor oversight.',
        ])
    if action_id == 'defer_remittance':
        return (f'Keep cash • credit {confidence:.0%}→{max(0, confidence - .30):.0%}', [
            f'Now: keep {cash:.0f} treasury cash; debt service marked deferred.',
            f'Creditor confidence {confidence:.0%} → {max(0, confidence - .30):.0%}.',
            f'Legitimacy {legitimacy:.0%} → {min(1, legitimacy + .02):.0%}; deferral weakens the final debt outcome.',
        ])
    return ('', [])


def _status_delta(stat: str, delta: float | None) -> str:
    if delta is None:
        return '—'
    if abs(delta) < 1e-9:
        return '0'
    if stat in ('hunger', 'legitimacy', 'creditors', 'autonomy'):
        return f'{delta * 100:+.1f}pp'
    if stat == 'unrest':
        return f'{delta:+.2f}'
    if abs(delta) < 1:
        return f'{delta:+.2f}'
    return f'{delta:+,.0f}'


def _status_value(stat: str, value: float, precise: bool = False) -> str:
    if stat in ('hunger', 'legitimacy', 'creditors', 'autonomy'):
        return f'{value:.1%}'
    if stat == 'unrest':
        return f'{value:.2f}'
    if stat == 'cash' and precise:
        return f'{value:,.2f}'
    return f'{value:,.0f}'


def _status_factor_lines(world: dict, current: dict, stat: str) -> list[str]:
    from scenario_status import ACTION_LABELS, PHASE_LABELS, display_change
    delta, previous_turn, factors = display_change(world, stat, current)
    if delta is None:
        return ['A previous-turn snapshot is not available yet. Changes will appear after the next turn.']
    previous = world['scenario_status_history']['comparison'][stat]
    lines = [f'Since turn {previous_turn}: {_status_value(stat, previous, precise=True)} → '
             f'{_status_value(stat, current[stat], precise=True)} ({_status_delta(stat, delta)}).']
    if stat == 'hunger':
        previous_snapshot = world['scenario_status_history']['comparison']
        lines.append(f'Hungry households {previous_snapshot["hungry_count"]} → {current["hungry_count"]}; '
                     f'total households {previous_snapshot["household_count"]} → {current["household_count"]}.')
    if stat == 'creditors':
        autonomy_delta, _, autonomy_factors = display_change(world, 'autonomy', current)
        if autonomy_delta is not None:
            lines.append(f'Fiscal autonomy {_status_value("autonomy", current["autonomy"])} '
                         f'({_status_delta("autonomy", autonomy_delta)} since turn {previous_turn}).')
            factors = factors + [factor for factor in autonomy_factors if factor not in factors]
    if factors:
        lines.append('Measured contributors:')
        for factor in factors:
            source = factor['source']
            label = ACTION_LABELS.get(source, PHASE_LABELS.get(source, source))
            contribution = factor['changes'].get(stat)
            if contribution is None and stat == 'creditors':
                contribution = factor['changes'].get('autonomy')
                label += ' (autonomy)'
                measure = 'autonomy'
            else:
                measure = stat
            factor_line = f'• {label}: {_status_delta(measure, contribution)}'
            if stat == 'creditors' and measure == 'creditors' and 'autonomy' in factor['changes']:
                factor_line += f' confidence, {_status_delta("autonomy", factor["changes"]["autonomy"])} autonomy'
            lines.append(factor_line)
            detail = factor.get('details', {}).get(stat)
            if detail:
                lines.append(detail)
    elif abs(delta) < 1e-9:
        lines.append('No change recorded since the previous turn.')
    else:
        lines.append('The change predates factor tracking for this saved game.')
    return lines


def _draw_guided_status_bar(surface, world: dict, mouse_pos=None) -> None:
    """Show turn deltas and the measured causes of each national stat."""
    from scenario_status import display_change, snapshot
    pygame.draw.rect(surface, (12, 14, 20), (0, 0, WIDTH, TOP_BAR_H))
    pygame.draw.line(surface, (58, 66, 86), (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 1)
    nation = _egypt_nation(world)
    current = snapshot(world)
    if nation is None or current is None:
        return
    state = world.get('scenario_state', {})
    payment = float(state.get('scheduled_remittance', 200.0))
    title = getattr(nation, 'display_name', nation.name)
    surface.blit(_scenario_font(13).render(f'{title}  •  National status', True, ACCENT), (12, 3))
    status = [
        ('cash', f'Treasury {_status_value("cash", current["cash"])}', 'Treasury cash', [
            f'Scheduled debt service costs {payment:,.0f}; a concession costs {payment / 2:,.0f}.',
        ]),
        ('maize', f'Maize {_status_value("maize", current["maize"])}', 'Public maize', [
            f'Releasing stores can feed up to {min(current["maize"], int(state.get("relief_units_per_turn", 30)))} households this turn.',
        ]),
        ('hunger', f'Hungry {current["hunger"]:.0%}', 'Household hunger', [
            'Reserve release reaches hungry households first. The weak Nile harvest persists through turn 8.',
        ]),
        ('legitimacy', f'Legitimacy {current["legitimacy"]:.0%}', 'Government legitimacy', [
            'The government breaks down if legitimacy reaches 10% or less.',
        ]),
        ('unrest', f'Unrest {current["unrest"]:.2f}', 'District unrest', [
            'The government breaks down if average unrest reaches 0.85.',
        ]),
        ('creditors', f'Creditors {current["creditors"]:.0%}', 'Creditor position', [
            'Payment or concession raises confidence; deferral and default damage it.',
        ]),
    ]
    x = 12
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    label_font = _scenario_font(13)
    delta_font = _scenario_font(12)
    for stat, label, tip_title, guidance in status:
        delta, _, _ = display_change(world, stat, current)
        delta_label = f' ({_status_delta(stat, delta)})'
        label_surface = label_font.render(label, True, TEXT)
        desirable = stat not in ('hunger', 'unrest')
        color = DIM if delta is None or abs(delta) < 1e-9 else (GREEN if (delta > 0) == desirable else RED)
        delta_surface = delta_font.render(delta_label, True, color)
        width = label_surface.get_width() + delta_surface.get_width() + 18
        rect = pygame.Rect(x - 2, 24, width - 5, 24)
        if rect.collidepoint(mx, my):
            pygame.draw.rect(surface, (45, 53, 71), rect, border_radius=3)
            world['_guided_hover_tip'] = (tip_title, _status_factor_lines(world, current, stat) + guidance, rect, 'status')
        surface.blit(label_surface, (x + 2, 27))
        surface.blit(delta_surface, (x + 2 + label_surface.get_width(), 28))
        x += width


def _draw_guided_hover_tip(surface, tip) -> None:
    title, paragraphs, anchor, kind = tip
    body_font = _scenario_font(14)
    title_font = _scenario_font(16)
    card_w = 390
    lines = []
    for paragraph in paragraphs:
        lines.extend(_wrap_text(paragraph, body_font, card_w - 28))
        if kind != 'status':
            lines.append('')
    if lines and kind != 'status':
        lines.pop()
    card_h = 42 + len(lines) * 19
    x = min(MAP_RIGHT - card_w - 8, max(8, anchor.x - 5)) if kind == 'status' else MAP_RIGHT - card_w - 14
    y = TOP_BAR_H + 51 if kind == 'status' else max(TOP_BAR_H + 55, min(HEIGHT - TICKER_H - card_h - 8, anchor.y - 4))
    rect = pygame.Rect(x, y, card_w, card_h)
    pygame.draw.rect(surface, (20, 24, 34), rect, border_radius=6)
    pygame.draw.rect(surface, ACCENT, rect, 1, border_radius=6)
    surface.blit(title_font.render(title, True, ACCENT), (x + 14, y + 9))
    for idx, line in enumerate(lines):
        if line:
            surface.blit(body_font.render(line, True, TEXT), (x + 14, y + 35 + idx * 19))


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
    title_font = _scenario_font(20)
    body_font = _scenario_font(16)
    small_font = _scenario_font(14)
    nation = next((n for n in world.get('nations', []) if n.name == world.get('player_nation_name')), None)
    name = getattr(nation, 'display_name', 'Khedivate of Egypt')
    surface.blit(title_font.render('Situation', True, TEXT), (x + 14, y + 12))
    surface.blit(_scenario_font(13).render(name, True, ACCENT), (x + 14, y + 42))

    cur_y = y + 66
    briefing = world.get('scenario', {}).get('briefing', ('',))[0]
    brief_rect = pygame.Rect(x + 9, cur_y, w - 18, 112)
    pygame.draw.rect(surface, (32, 37, 50), brief_rect, border_radius=5)
    pygame.draw.rect(surface, (75, 91, 119), brief_rect, 1, border_radius=5)
    briefing_font = _scenario_font(14)
    for idx, line in enumerate(_wrap_text(briefing, briefing_font, brief_rect.w - 18)[:5]):
        surface.blit(briefing_font.render(line, True, TEXT),
                     (brief_rect.x + 9, brief_rect.y + 8 + idx * 19))
    cur_y = brief_rect.bottom + 8

    colors = {'urgent': (226, 102, 94), 'warning': (225, 178, 87), 'good': (112, 205, 145), 'neutral': (140, 160, 195)}
    for pressure in scenario_pressures(world):
        card_h = 76
        rect = pygame.Rect(x + 9, cur_y, w - 18, card_h)
        color = colors.get(pressure['tone'], ACCENT)
        pygame.draw.rect(surface, (34, 38, 51), rect, border_radius=5)
        pygame.draw.rect(surface, color, rect, 1, border_radius=5)
        surface.blit(small_font.render(pressure['title'], True, color), (rect.x + 9, rect.y + 6))
        value_font = _scenario_font(13)
        value_lines = _wrap_text(pressure['value'], value_font, rect.w - 18)
        for idx, line in enumerate(value_lines[:2]):
            surface.blit(value_font.render(line, True, TEXT),
                         (rect.x + 9, rect.y + 25 + idx * 16))
        cause_font = _scenario_font(11)
        cause = _wrap_text(pressure['cause'], cause_font, rect.w - 18)
        for idx, line in enumerate(cause[:2]):
            surface.blit(cause_font.render(line, True, DIM),
                         (rect.x + 9, rect.y + 48 + idx * 13))
        cur_y += card_h + 4

    cur_y += 4
    state = world.get('scenario_state', {})
    turn = int(world.get('turn', 0))
    spent = state.get('last_action_turn') == turn
    payment_ready = turn >= int(state.get('payment_window_turn', 6)) and state.get('payment_status') in ('upcoming', 'unpaid')
    stock = int(getattr(getattr(nation, 'government', None), 'food_inventory', 0)) if nation else 0
    suggested = 'Release maize reserves' if stock > 0 else 'Keep more food in Egypt'
    if not payment_ready:
        surface.blit(_scenario_font(13).render(f'Suggested first move: {suggested}', True, ACCENT), (x + 13, cur_y))
        cur_y += 18
    surface.blit(body_font.render('Choose one decision this turn', True, TEXT), (x + 13, cur_y))
    cur_y += 24
    treasury_cash = float(getattr(getattr(getattr(nation, 'government', None), 'agent', None), 'cash', 0.0)) if nation else 0.0
    scheduled_payment = float(state.get('scheduled_remittance', 200.0))
    tax_available = not state.get('tax_decision_taken', False)
    action_rows = [
        [('release_maize', 'Release maize reserves', stock > 0)],
        [('prioritize_domestic_grain', 'Keep more food in Egypt', not state.get('domestic_grain_priority', False))],
        [('reduce_fellahin_tax', 'Reduce local taxes', tax_available),
         ('raise_local_taxes', 'Raise local taxes', tax_available)],
    ]
    action_rows.append([
        ('pay_remittance', 'Pay debt service', payment_ready and treasury_cash >= scheduled_payment)
    ])
    if payment_ready:
        action_rows.extend([
            [('concede_revenue', 'Concede revenue', treasury_cash >= scheduled_payment * 0.5)],
            [('defer_remittance', 'Defer debt service', True)],
        ])
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for row in action_rows:
        button_h = 39
        gap = 3
        button_w = (w - 18 - gap * (len(row) - 1)) // len(row)
        for col, (action_id, label, available) in enumerate(row):
            rect = (x + 9 + col * (button_w + gap), cur_y, button_w, button_h)
            detail, explanation = _guided_action_preview(world, nation, action_id)
            enabled = available and not spent and nation is not None
            if action_id == 'pay_remittance' and not payment_ready:
                turns_left = max(0, int(state.get('payment_window_turn', 6)) - turn)
                detail = f'Due in {turns_left} turns • {scheduled_payment:.0f} units'
            elif not available and action_id in ('pay_remittance', 'concede_revenue'):
                needed = scheduled_payment if action_id == 'pay_remittance' else scheduled_payment * .5
                detail = f'Need {needed:.0f} • cash {treasury_cash:.0f}'
            if enabled:
                register_target(world, rect, ('scenario_action', action_id), scope='guided')
            hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
            if hover:
                if spent:
                    explanation = ['A major decision has already been made this turn. Advance one turn to choose again.'] + explanation
                elif action_id == 'pay_remittance' and not payment_ready:
                    pass  # The preview already explains the future availability and cost.
                elif not available:
                    if action_id == 'release_maize':
                        reason = 'The public maize reserve is empty.'
                    elif action_id == 'prioritize_domestic_grain':
                        reason = 'Grain is already being retained for local supply.'
                    elif action_id in ('reduce_fellahin_tax', 'raise_local_taxes'):
                        reason = 'A local tax decision is already in effect.'
                    else:
                        needed = scheduled_payment if action_id == 'pay_remittance' else scheduled_payment * .5
                        reason = f'Treasury cash is below the {needed:.0f} units needed for this choice.'
                    explanation = [reason] + explanation
                world['_guided_hover_tip'] = (label, explanation, pygame.Rect(rect), 'action')
            bg = (52, 66, 88) if hover and enabled else ((37, 44, 59) if enabled else (30, 33, 42))
            edge = ACCENT if hover and enabled else ((80, 96, 124) if enabled else (53, 58, 70))
            pygame.draw.rect(surface, bg, rect, border_radius=4)
            pygame.draw.rect(surface, edge, rect, 1, border_radius=4)
            color = TEXT if enabled else DIM
            button_font = _scenario_font(14) if len(row) == 1 else _scenario_font(13)
            surface.blit(button_font.render(label, True, color), (rect[0] + 7, rect[1] + 2))
            detail_font = _scenario_font(12)
            surface.blit(detail_font.render(detail, True, DIM), (rect[0] + 7, rect[1] + 21))
        cur_y += button_h + gap

    message = world.get('scenario_feedback', '')
    if message:
        message_font = _scenario_font(12)
        lines = _wrap_text(message, message_font, w - 28)
        for idx, line in enumerate(lines[:2]):
            surface.blit(message_font.render(line, True, ACCENT), (x + 14, y + h - 35 + idx * 16))
    elif spent:
        surface.blit(_scenario_font(12).render('Decision recorded. Advance a turn to see its effects.', True, DIM), (x + 14, y + h - 24))
    else:
        surface.blit(_scenario_font(12).render('Select a district to inspect its details.', True, DIM), (x + 14, y + h - 24))


def _draw_egypt_scenario_debrief(surface, world: dict) -> None:
    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 14, WIDTH - MAP_RIGHT - 20
    h = HEIGHT - TOP_BAR_H - TICKER_H - 28
    pygame.draw.rect(surface, (25, 28, 38), (x, y, w, h), border_radius=7)
    pygame.draw.rect(surface, ACCENT, (x, y, w, h), 1, border_radius=7)
    debrief = world.get('scenario_state', {}).get('debrief', {})
    title_font = _scenario_font(22)
    body_font = _scenario_font(16)
    small_font = _scenario_font(13)
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
        surface.blit(labels, (0, TOP_BAR_H),
                     pygame.Rect(0, TOP_BAR_H, MAP_RIGHT, HEIGHT - TOP_BAR_H - TICKER_H))
    world['_guided_hover_tip'] = None
    if world.get('scenario_id') == 'egypt_1877':
        _draw_guided_status_bar(surface, world, mouse_pos=mouse_pos)
    else:
        pygame.draw.rect(surface, (12, 14, 20), (0, 0, WIDTH, TOP_BAR_H))
        pygame.draw.line(surface, (58, 66, 86), (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 1)
    draw_guided_header(surface, world, font_small, mouse_pos=mouse_pos)
    draw_pressure_panel(surface, world, mouse_pos=mouse_pos)
    draw_ticker(surface, world, font_small)

    notice = get_font(16).render('Egypt 1877 • Generated Nile and coast; outline is schematic', True, DIM)
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

    if world.get('_guided_hover_tip') and not world.get('settings_open'):
        _draw_guided_hover_tip(surface, world['_guided_hover_tip'])

    if world.get('settings_open'):
        draw_settings_dialog(surface, world, font_small, mouse_pos)


def draw_scenario_warning_modal(surface, world: dict, mouse_pos=None) -> None:
    """Show high-consequence scenario choices above either UI composition."""
    warning = world.get('scenario_warning_modal')
    if not warning:
        return
    from ui_targets import register_target
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((5, 7, 12, 210))
    surface.blit(veil, (0, 0))
    kind = warning.get('kind')
    card = pygame.Rect(310, 220, 780, 440 if kind == 'debt_due' else 360)
    border = (225, 178, 87) if kind == 'debt_due' else (226, 102, 94)
    pygame.draw.rect(surface, (24, 29, 41), card, border_radius=10)
    pygame.draw.rect(surface, border, card, 2, border_radius=10)
    title_font, body_font = _scenario_font(24), _scenario_font(16)
    state = world.get('scenario_state', {})
    nation = _egypt_nation(world)
    if kind == 'debt_due':
        amount = float(state.get('scheduled_remittance', 200.0))
        cash = float(getattr(getattr(getattr(nation, 'government', None), 'agent', None), 'cash', 0.0)) if nation else 0.0
        title = 'Debt service is due now'
        lines = [
            f'Treasury cash: {cash:,.0f} units. Scheduled payment: {amount:,.0f}.',
            'Default collapses creditor confidence and reduces legitimacy by 15 percentage points.',
            'Choose how to settle the debt service:',
        ]
        options = [
            ('pay_remittance', f'Pay {amount:,.0f}', cash >= amount),
            ('concede_revenue', f'Concede • pay {amount / 2:,.0f}', cash >= amount / 2),
            ('defer_remittance', 'Defer • keep cash', True),
            ('default_remittance', 'Default • severe loss', True),
        ]
    elif kind == 'breakdown':
        title = 'Political breakdown is imminent'
        lines = [
            f"Average unrest {warning.get('unrest', 0):.2f} (threshold 0.85); legitimacy {warning.get('legitimacy', 0):.0%} (threshold 10%).",
            'If still available, tax relief can lower unrest and raise legitimacy before the campaign ends.',
        ]
        can_relieve = (not state.get('tax_decision_taken', False)
                       and state.get('last_action_turn') != int(world.get('turn', 0)))
        options = ([('scenario_rescue_tax', 'Reduce local taxes now', True)] if can_relieve else [])
        options.append(('accept_breakdown', 'Accept government breakdown', True))
    elif kind == 'riot_risk':
        title = ('Riot level has been reached' if warning.get('already_mob')
                 else 'Civil unrest is approaching riot levels')
        lines = [
            f"{warning.get('nation', 'A nation')} • {warning.get('region', 'a district')}: protest energy {warning.get('energy', 0):.1f}/10.",
            (f"Mob and riot activity begins at {warning.get('threshold', 6.5):.1f}. Review food access, taxes, and local security before continuing."
             if not warning.get('already_mob') else 'Mob or riot activity may intensify next turn. Review food access, taxes, and local security before continuing.'),
        ]
        options = [('review_risk', 'Review situation', True), ('continue_risk', 'Advance one turn anyway', True)]
    elif kind == 'political_risk':
        title = 'Political stability is at risk'
        lines = [
            f"Average unrest is {warning.get('unrest', 0):.2f} (breakdown at 0.85); legitimacy is {warning.get('legitimacy', 0):.0%} (breakdown at 10%).",
            'Review the political support card and available actions before advancing, or continue one turn at risk.',
        ]
        options = [('review_risk', 'Review decisions', True), ('continue_risk', 'Advance one turn anyway', True)]
    elif kind == 'riot_event':
        title = 'Riot or revolt reported'
        lines = [str(warning.get('message', 'Civil unrest has escalated.')),
                 'The simulation is paused so you can review the situation before continuing.']
        options = [('review_risk', 'Review situation', True), ('continue_risk', 'Continue simulation', True)]
    else:
        title = 'Crisis warning'
        lines = [str(warning.get('message', 'A serious event may occur next turn.'))]
        options = [('review_risk', 'Review situation', True), ('continue_risk', 'Advance one turn anyway', True)]
    surface.blit(title_font.render(title, True, TEXT), (card.x + 26, card.y + 24))
    y = card.y + 76
    for line in lines:
        for wrapped in _wrap_text(line, body_font, card.w - 52):
            surface.blit(body_font.render(wrapped, True, TEXT), (card.x + 26, y))
            y += 24
        y += 8
    mouse = mouse_pos if mouse_pos else (-1, -1)
    hovered_option = None
    cols = 2 if len(options) > 2 else 1
    btn_w = (card.w - 52 - 12 * (cols - 1)) // cols
    btn_h = 48
    rows = (len(options) + cols - 1) // cols
    button_y = card.bottom - btn_h * rows - 24 - 10 * (rows - 1)
    for index, (action, label, enabled) in enumerate(options):
        row, col = divmod(index, cols)
        rect = pygame.Rect(card.x + 26 + col * (btn_w + 12), button_y + row * (btn_h + 10), btn_w, btn_h)
        hover = rect.collidepoint(mouse)
        if hover:
            hovered_option = action
        pygame.draw.rect(surface, (55, 66, 86) if hover and enabled else (38, 46, 62), rect, border_radius=5)
        pygame.draw.rect(surface, ACCENT if hover else (83, 99, 126), rect, 1, border_radius=5)
        label_surface = _scenario_font(14).render(label, True, TEXT if enabled else DIM)
        surface.blit(label_surface, label_surface.get_rect(center=rect.center))
        if enabled:
            register_target(world, rect, ('scenario_warning', action), scope='scenario_warning')

    if hovered_option:
        consequences = {
            'pay_remittance': (
                (f'Unavailable: the treasury has {cash:,.0f} units and needs {amount:,.0f}. ' if cash < amount else '')
                + f'Spends {amount:,.0f} treasury units. Marks the debt service paid and raises creditor confidence by up to 15 points.'
                if kind == 'debt_due' else 'Enacts this debt payment.'
            ),
            'concede_revenue': (
                (f'Unavailable: the treasury has {cash:,.0f} units and needs {amount / 2:,.0f}. ' if cash < amount / 2 else '')
                + f'Spends {amount / 2:,.0f} units and restructures the payment. Creditor confidence rises by up to 15 points, while fiscal autonomy falls by 25 points because creditors gain future revenue oversight.'
                if kind == 'debt_due' else 'Enacts this revenue concession.'
            ),
            'defer_remittance': (
                'Keeps the cash available for domestic needs and marks the payment deferred. Creditor confidence falls by 30 points; legitimacy rises by 2 points.'
                if kind == 'debt_due' else 'Defers the payment.'
            ),
            'default_remittance': (
                'Keeps the cash, but creditor confidence falls to zero and legitimacy drops by 15 percentage points.'
                if kind == 'debt_due' else 'Defaults on the payment.'
            ),
            'scenario_rescue_tax': 'Reduces local taxes, lowering treasury revenue. It can avert breakdown if unrest and legitimacy move back across their thresholds.',
            'accept_breakdown': 'Ends the campaign immediately with government breakdown.',
            'review_risk': 'Closes this warning and pauses the simulation so you can inspect the situation.',
            'continue_risk': 'Advances one turn despite the warning. The reported crisis may worsen or trigger its consequences.',
        }
        detail = consequences.get(hovered_option)
        if detail:
            tooltip_font = _scenario_font(13)
            tooltip_w = card.w - 52
            tooltip_lines = _wrap_text(detail, tooltip_font, tooltip_w - 24)
            tooltip_h = len(tooltip_lines) * 18 + 18
            tx = card.x + 26
            ty = max(card.y + 126, button_y - tooltip_h - 8)
            tooltip_rect = pygame.Rect(tx, ty, tooltip_w, tooltip_h)
            pygame.draw.rect(surface, (16, 20, 29), tooltip_rect, border_radius=5)
            pygame.draw.rect(surface, ACCENT, tooltip_rect, 1, border_radius=5)
            for line_index, line in enumerate(tooltip_lines):
                surface.blit(tooltip_font.render(line, True, TEXT), (tx + 12, ty + 9 + line_index * 18))


def scenario_warning_modal_hit(pos, world: dict) -> bool:
    """Resolve a warning choice without allowing clicks to fall through."""
    from ui_targets import find_target
    target = find_target(world, pos, scope='scenario_warning')
    if target is None:
        return True
    action = target.action[1]
    if action in ('pay_remittance', 'concede_revenue', 'defer_remittance', 'default_remittance'):
        from scenario_egypt_1877 import apply_action
        ok, message = apply_action(world, action)
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
    elif action == 'scenario_rescue_tax':
        from scenario_egypt_1877 import SCENARIO, _outcome_metrics, apply_action
        ok, message = apply_action(world, 'reduce_fellahin_tax')
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            metrics = _outcome_metrics(_egypt_nation(world))
            thresholds = SCENARIO['thresholds']
            if (metrics['legitimacy'] > thresholds['breakdown_legitimacy']
                    and metrics['unrest'] < thresholds['breakdown_unrest']):
                if world.get('scenario_state', {}).get('payment_status') == 'unpaid':
                    world['scenario_warning_modal'] = {'kind': 'debt_due'}
                else:
                    world['scenario_warning_modal'] = None
            else:
                world['scenario_warning_modal'] = {'kind': 'breakdown', **metrics}
    elif action == 'accept_breakdown':
        from scenario_egypt_1877 import _finish_scenario, _outcome_metrics
        nation = _egypt_nation(world)
        _finish_scenario(world, nation, 'breakdown', int(world.get('turn', 0)), _outcome_metrics(nation))
        world['scenario_warning_modal'] = None
    elif action == 'review_risk':
        world['scenario_warning_modal'] = None
        world['crisis_warning_ack_turn'] = int(world.get('turn', 0))
    elif action == 'continue_risk':
        world['scenario_warning_modal'] = None
        world['crisis_warning_ack_turn'] = int(world.get('turn', 0))
        from worldview_engine import step_world_with_warning
        step_world_with_warning(world)
    world['playing'] = False
    world['needs_redraw'] = True
    return True


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
        from worldview_engine import step_world_with_warning
        world['playing'] = False
        step_world_with_warning(world)
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
