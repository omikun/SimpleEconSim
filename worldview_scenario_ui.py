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
    protected_rate = float(world.get('scenario', {}).get('thresholds', {}).get('protected_hunger_rate', .20))
    food_tone = ('urgent' if hunger_rate >= protected_rate else
                 'warning' if stock_turns < 2 or hunger_rate >= protected_rate * .5 else 'good')
    food_value = f'{hunger_rate:.0%} hungry • {stock_turns:.1f} turns of public maize'
    food_cause = 'Reserve release can feed households; it uses finite state stores.'

    payment_turn = int(state.get('payment_window_turn', 6))
    remaining = max(0, payment_turn - int(world.get('turn', 0)))
    payment_status = state.get('payment_status', 'upcoming')
    cash = float(getattr(nation.government.agent, 'cash', 0.0))
    remittance = float(state.get('scheduled_remittance', 200.0))
    confidence = float(state.get('creditor_confidence', 0.6))
    if payment_status in ('upcoming', 'unpaid', 'deferred'):
        debt_value = (f'Due now • {remittance:.0f} cash needed' if remaining == 0
                      else f'{remaining} turns to {remittance:.0f} payment • {cash:.0f} cash')
        if payment_status == 'deferred':
            debt_cause = f'Deferral added a surcharge. Pay by turn {payment_turn}; no second deferral is available.'
        else:
            debt_cause = f'Pay {remittance:.0f}, concede {remittance / 2:.0f}, or defer once; creditor confidence {confidence:.0%}.'
    else:
        debt_value = f'{payment_status.title()} • creditor confidence {confidence:.0%}'
        levy = float(state.get('creditor_levy_per_turn', 0.0))
        debt_cause = (f'The Caisse collects up to {levy:.0f} units each turn until '
                      f'{float(state.get("creditor_levy_remaining", 0.0)):.0f} units are repaid. '
                      if levy else '') + f'Fiscal autonomy {float(state.get("fiscal_autonomy", 1.0)):.0%}.'
    naval_stage = state.get('naval_crisis', {}).get('stage', 'none')
    if naval_stage == 'mobilizing':
        debt_value = 'Britain weighs a naval expedition'
        debt_cause = 'No customs levy applies. Britain must fund a credible force before its claim can be imposed.'
    elif naval_stage == 'ultimatum':
        debt_value = 'British squadron off Alexandria'
        debt_cause = 'Respond to the naval ultimatum before advancing.'
    elif naval_stage == 'blockaded':
        debt_value = 'Alexandria under blockade'
        debt_cause = 'Coastal routes are blocked. Britain pays fleet upkeep each turn; Cairo can settle or hold out.'
    elif naval_stage == 'mediation':
        debt_value = 'Ottoman mediation pending'
        debt_cause = 'The fleet remains off Alexandria for one turn while Istanbul seeks terms.'
    diplomatic = state.get('diplomatic_crisis') or {}
    debt_title = 'Debt service'
    pending_offer = diplomatic.get('egyptian_proposal')
    if pending_offer:
        debt_title = 'Foreign decision'
        debt_value = f'Paris replies on turn {diplomatic.get("proposal_due_turn", "?")}'
        offer_effects = {
            'mediation': f'If both governments agree, Cairo may settle for {remittance * .5:.0f} cash.',
            'joint_guarantee': 'If all sign, creditors may collect up to 5 units per turn from actual receipts.',
            'oppose_unilateral': 'French opposition raises British mobilization cost by 20; Britain may still proceed.',
        }
        debt_cause = offer_effects.get(pending_offer, 'Paris and London will weigh Cairo’s offer.')
    debt_tone = 'urgent' if payment_status in ('deferred', 'defaulted') or (remaining <= 1 and payment_status in ('upcoming', 'unpaid')) else 'warning'
    if naval_stage in ('mobilizing', 'ultimatum', 'blockaded'):
        debt_tone = 'urgent'
    occupation = state.get('occupation', {})
    controlled = [site for site, holder in state.get('campaign', {}).get('territorial_control', {}).items()
                  if holder == 'Britain']
    if controlled and not pending_offer:
        debt_title = 'Occupation & revenue'
        debt_value = 'British foothold: ' + ', '.join(controlled)
        institutions = occupation.get('institutional_control', {})
        debt_cause = (f'Customs: {institutions.get("customs", "Egypt")}; '
                      f'cabinet: {institutions.get("cabinet", "Egypt")}. '
                      f'Resistance {float(occupation.get("resistance", 0)):.0%}.')
        debt_tone = 'urgent'

    unrest = sum(float(getattr(r, 'unrest_level', 0.0)) for r in nation.tiles) / max(1, len(nation.tiles))
    legitimacy = float(getattr(nation, 'legitimacy', 0.5))
    political_tone = 'urgent' if legitimacy < 0.30 or unrest >= 0.6 else ('warning' if legitimacy < 0.5 or unrest >= 0.3 else 'good')
    politics = state.get('politics', {})
    loyalty = float(politics.get('army_loyalty', 1.0))
    movement = float(politics.get('nationalist_movement', 0.0))
    if loyalty < 0.58 or movement >= 0.55:
        political_tone = 'urgent'
    elif loyalty < 0.70 or movement >= 0.40:
        political_tone = 'warning'
    ledger = state.get('debt_ledger', [])
    recent = [entry for entry in ledger if entry.get('kind') in ('payment', 'concession_payment',
                                                                'naval_settlement', 'assigned_revenue')]
    debt_details = [f'Outstanding Caisse bonds: {remittance:,.0f} units, held by Britain and France.']
    if pending_offer:
        debt_details.insert(0, f'Cairo proposed {pending_offer.replace("_", " ")}. '
                               f'France answers on turn {diplomatic["proposal_due_turn"]}; '
                               'Britain then accepts terms, proceeds alone, or withdraws.')
    assignment = state.get('collection_assignment') or {}
    if assignment.get('status') == 'active':
        sources = assignment.get('sources', {})
        debt_details.append(f'Assigned receipts: {float(sources.get("tax", 0)):.0%} of eligible tax and '
                            f'{float(sources.get("tariff", 0)):.0%} of customs, capped at '
                            f'{float(assignment.get("per_turn_cap", 0)):,.0f} units each turn.')
        debt_details.append(f'Collected from actual receipts this turn: '
                            f'{float(state.get("debt_collected_this_turn", 0.0)):,.1f} units.')
    else:
        debt_details.append('No active Caisse collection assignment.')
    oversight = state.get('oversight_agreement') or {}
    if oversight.get('status') == 'active':
        debt_details.append(f'Caisse inspection covers {" and ".join(oversight["scope"])} receipts; '
                            f'next review turn {oversight["review_turn"]}. Inspection alone seizes no cash.')
    if recent:
        entry = recent[-1]
        debt_details.append(f'Latest transfer: turn {entry["turn"]}, {entry["amount"]:,.2f} to {entry["creditor"]} '
                            f'from {entry.get("source", entry["kind"])}.')
    geography = state.get('geography', {})
    fleet = geography.get('fleets', {}).get('Britain')
    if fleet:
        debt_details.append(f'British fleet: {fleet["ships"]} ships, {fleet["guns"]:.0f} guns at '
                            f'{fleet["location"]}; coal {fleet["coal"]}, '
                            f'{"supplied" if fleet["supplied"] else "unsupplied"}.')
    french_fleet = geography.get('fleets', {}).get('France')
    if french_fleet:
        authorized = diplomatic.get('french_authorization', {})
        debt_details.append(f'French fleet: {french_fleet["ships"]} ships at {french_fleet["location"]}; '
                            f'{"authorized" if authorized.get("bombard") else "not authorized"} to fire.')
    debt_details.append(f'Canal: {"open" if geography.get("canal_open", True) else "closed"} to foreign transit; '
                        f'controller {geography.get("canal_controller", "Egypt")}.' )
    diplomacy = geography.get('diplomacy', {})
    if diplomacy:
        debt_details.append('Foreign positions: ' + ', '.join(f'{name} {policy.replace("_", " ")}'
                                                             for name, policy in diplomacy.items()) + '.')
    for actor in ('France', 'Britain'):
        if diplomatic.get('reasons', {}).get(actor):
            debt_details.append(f'{actor}: {diplomatic["reasons"][actor]}')
    if controlled:
        debt_details.append(f'Occupied receipts collected this turn: {float(occupation.get("collected_this_turn", 0)):.1f}; '
                            f'garrison supply paid so far: {float(occupation.get("garrison_supply_paid", 0)):.1f}.')
        debt_details.append(f'Alexandria port damage: '
                            f'{float(state.get("campaign", {}).get("infrastructure_damage", {}).get("Alexandria", 0)):.0%}; '
                            'damaged customs infrastructure lowers collectible tariff receipts.')
        debt_details.append(f'Formal sovereignty remains {occupation.get("formal_sovereign", "Egypt")}; '
                            f'Egyptian resistance is {float(occupation.get("resistance", 0)):.0%}.')
    return [
        {'title': 'Household maize access', 'value': food_value, 'cause': food_cause, 'tone': food_tone},
        {'title': debt_title,
         'value': debt_value, 'cause': debt_cause, 'tone': debt_tone,
         'details': debt_details},
        {'title': 'Political support', 'value': f'Legitimacy {legitimacy:.0%} • palace army {loyalty:.0%}',
         'cause': f'{politics.get("ruler", "Ismail Pasha")} • {politics.get("governing_coalition", "palace")} cabinet • movement {movement:.0%}.',
         'tone': political_tone, 'details': [
             f'Officer access: {float(politics.get("officer_access", 0.0)):.0%}; army loyalty to the palace: {loyalty:.0%}.',
             f'Civilian backing for change: {float(politics.get("civilian_support", 0.0)):.0%}; movement strength: {movement:.0%}.',
             f'Palace authority: {float(politics.get("palace_authority", 0.0)):.0%}; cabinet authority: {float(politics.get("cabinet_authority", 0.0)):.0%}.',
             'Unpaid troops, blocked promotions, food stress, tax extraction, and foreign control can shift support.',
         ]},
    ]


def draw_scenario_route_overlay(surface, world: dict) -> None:
    """Mark strategic canal sites above the rendered terrain in Guided play."""
    state = world.get('scenario_state', {})
    geography = state.get('geography', {})
    sites = geography.get('sites', {})
    if not sites:
        return
    from worldview_camera import world_to_screen
    clipped = surface.get_clip()
    surface.set_clip(pygame.Rect(0, TOP_BAR_H + 48, MAP_RIGHT, HEIGHT - TOP_BAR_H - TICKER_H - 48))
    points = {name: world_to_screen(world, *site['position']) for name, site in sites.items()
              if site.get('position') is not None}
    canal_color = (210, 163, 90) if geography.get('canal_open') else (164, 77, 67)
    for start, end in (('Port Said', 'Ismailia'), ('Ismailia', 'Tel el Kebir'),
                       ('Tel el Kebir', 'Cairo')):
        if start in points and end in points:
            pygame.draw.line(surface, (20, 30, 39), points[start], points[end], 5)
            pygame.draw.line(surface, canal_color if end == 'Ismailia' else (176, 168, 122),
                             points[start], points[end], 2)
    control = state.get('campaign', {}).get('territorial_control', {})
    fleet = geography.get('fleets', {}).get('Britain')
    for name in ('Port Said', 'Ismailia', 'Tel el Kebir'):
        if name not in points:
            continue
        point = points[name]
        color = (222, 107, 95) if control.get(name) == 'Britain' else canal_color
        pygame.draw.circle(surface, (18, 24, 33), point, 6)
        pygame.draw.circle(surface, color, point, 5, 2)
        label = _scenario_font(13).render(name, True, (240, 222, 183))
        surface.blit(label, (point[0] + 9, point[1] - 17))
    if fleet and fleet.get('location') in points:
        px, py = points[fleet['location']]
        pygame.draw.circle(surface, (238, 113, 96), (px - 9, py + 10), 5)
        label = _scenario_font(12).render('British fleet', True, (255, 200, 181))
        surface.blit(label, (px + 1, py + 6))
    french_fleet = geography.get('fleets', {}).get('France')
    if french_fleet and french_fleet.get('location') in points:
        px, py = points[french_fleet['location']]
        pygame.draw.circle(surface, (118, 164, 225), (px - 9, py + 23), 5)
        label = _scenario_font(12).render('French fleet', True, (180, 211, 250))
        surface.blit(label, (px + 1, py + 19))
    surface.set_clip(clipped)
    from scenario_projects import draw_map_overlay
    draw_map_overlay(surface, world)


def draw_guided_header(surface, world: dict, font_small, mouse_pos=None) -> None:
    """Draw turn objective and simple composition controls above the map."""
    pygame.draw.rect(surface, (21, 25, 34), (0, TOP_BAR_H, MAP_RIGHT, 48))
    pygame.draw.line(surface, (64, 73, 94), (0, TOP_BAR_H + 47), (MAP_RIGHT, TOP_BAR_H + 47), 1)
    chapter = int(world.get('scenario_state', {}).get('chapter', 1))
    chapter_text = ('I: Nile flood and Caisse debt' if chapter == 1
                    else 'II: Sovereignty, officers, and intervention')
    title = font_small.render(f'EGYPT 1876–82  •  {chapter_text}', True, (235, 225, 190))
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
        analysis_tabs = [('overview', 'Overview'), ('land', 'Land'),
                         ('people', 'People'), ('projects', 'Projects')]
        for idx, (tab, label) in enumerate(analysis_tabs):
            rect = (MAP_RIGHT + 10 + idx * 78, TOP_BAR_H + 60, 75, 24)
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
        if mouse_pos and rect.collidepoint(mouse_pos):
            world['_guided_hover_tip'] = (pressure['title'], pressure.get('details', [pressure['cause']]),
                                          rect, 'action')
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
    if action_id in ('repair_delta_channels', 'repair_upper_channels'):
        from scenario_projects import PROJECT_DEFS, get_project
        site = 'Nile Delta' if action_id == 'repair_delta_channels' else 'Upper Egypt'
        definition = PROJECT_DEFS['nile_repair']
        project = get_project(world, 'nile_repair', site)
        if project:
            return (f'{site}: {project["status"]}', [
                f'Paid {project["paid_cash"]:.0f} to local workers; progress '
                f'{project["progress"]}/{project["required_work"]} staffed turns.',
                f'Current state: {project["status"]}. Operating work needs '
                f'{definition["upkeep"]:.0f} treasury units of local wages per turn.',
                'Map marker and district harvest show its effects. Private owners may still hold the extra grain.',
            ])
        return (f'−{definition["cash_cost"]:.0f} treasury • {definition["work_turns"]} turns', [
            f'Pay {definition["cash_cost"]:.0f} to three local workers in {site} now; '
            f'allow {definition["work_turns"]} staffed turns for the repair.',
            f'After completion, pay {definition["upkeep"]:.0f} per turn. '
            'Restored channels raise actual food yields during the low Nile and modestly afterward.',
            'Owners can buy and reserve some extra maize; household hunger falls only if people can access it.',
            'This spending competes with the next 200-unit Caisse instalment.',
        ])
    if action_id == 'build_revenue_office':
        from scenario_projects import PROJECT_DEFS, get_project
        definition = PROJECT_DEFS['revenue_office']
        project = get_project(world, 'revenue_office', 'Alexandria')
        if project:
            return (f'Alexandria office: {project["status"]}', [
                f'Progress {project["progress"]}/{project["required_work"]} staffed turns; '
                f'{definition["upkeep"]:.0f} in local wages each operating turn.',
                'Receipts and transfers appear in the project ledger. A signed Caisse assignment is honored first.',
            ])
        return (f'−{definition["cash_cost"]:.0f} treasury • {definition["work_turns"]} turns', [
            'Pay 60 treasury units to local workers now; staff the Alexandria office for three turns.',
            'When operating, 40% of actual local Egyptian tax and tariff receipts moves to Cairo after lawful creditor claims.',
            'Tax rates and total collection do not rise. Local governments keep the rest; Cairo pays 3 per turn in wages.',
            'The Caisse reviews the accounts one turn after completion and may demand publication.',
        ])
    if action_id in ('publish_revenue_accounts', 'refuse_revenue_inspection'):
        if action_id == 'publish_revenue_accounts':
            return ('Show receipts • creditor confidence ↑', [
                'Publish the office ledger: each payer, local collector, Cairo transfer and local remainder.',
                'The Caisse can verify the existing claim; this does not pay it or extend its legal assignment.',
                'Creditor confidence rises by 6 points. This uses this turn’s major decision.',
            ])
        return ('Keep accounts private • creditor confidence ↓', [
            'Refuse the Caisse request. The office keeps collecting lawful unassigned receipts.',
            'Creditor confidence falls by 12 points. Defaulted creditors may escalate their funded naval claim.',
            'This does not erase the debt or any signed collection assignment.',
        ])
    if action_id in ('prepare_canal_line', 'repair_canal_line'):
        from scenario_projects import PROJECT_DEFS, get_project
        definition = PROJECT_DEFS['canal_line']
        project = get_project(world, 'canal_line', 'Tel el Kebir')
        if action_id == 'repair_canal_line' and project:
            cost = definition['cash_cost'] * (1.0 - project['integrity']) * .5
            return (f'Repair costs about {cost:.0f}', [
                f'Restore Tel el Kebir works from {project["integrity"]:.0%} integrity.',
                'Pay the original local crew. The line must still receive 5 in wages and 6 public food units each turn.',
                'Repairs improve the next defensive battle only while the site is staffed, supplied and unoccupied.',
            ])
        return ('−70 treasury • two turns', [
            'Pay 70 treasury units to three local workers now; two staffed turns complete the line.',
            'Operating wages cost 5 and crew meals use 6 public maize units per turn.',
            'A supplied line adds up to 55 trench strength at Tel el Kebir; battle damage and occupation can disable it.',
            'Britain budgets for the longer route and can bargain, blockade, change approach or withdraw.',
            'Food and cash spent here cannot feed households or service the 200-unit debt instalment.',
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
    if action_id == 'intensify_requisitions':
        next_unrest = sum(min(1, float(getattr(tile, 'unrest_level', 0.0)) + .12) for tile in tiles) / max(1, len(tiles))
        tax_increase = any(float(getattr(tile.gov, 'tax_rate', 0)) < .60 for tile in tiles)
        return (('Tax up to +4pp' if tax_increase else 'Tax ceiling held') + ' • legitimacy −8pp', [
            ('Now: raise district tax rates by up to 4 points, capped at 60%.' if tax_increase
             else 'Now: enforce the 60% emergency tax ceiling for another turn.'),
            f'Average unrest {unrest:.2f} → {next_unrest:.2f}; legitimacy {legitimacy:.0%} → {max(0, legitimacy - .08):.0%}.',
            'Repeated requisitions can cause government breakdown; higher taxes can raise future receipts.',
        ])
    if action_id == 'comply_oversight':
        return ('−2 treasury • creditor confidence +3pp', [
            'Pay Egyptian inspectors to disclose receipts at the next Caisse review.',
            'The conditional debt write-down remains in force.',
        ])
    if action_id == 'seek_narrower_oversight':
        return ('−20 treasury • request tax-only review', [
            'Pay 20 units to Britain and France and propose removing tariff inspection.',
            'The Caisse accepts only if disclosed receipts and creditor confidence are strong.',
        ])
    if action_id == 'revoke_oversight':
        agreement = state.get('oversight_agreement') or {}
        return ('Autonomy +15pp • debt claim restored', [
            f'Revoke inspection; the conditional {float(agreement.get("conditional_write_down", 0)):,.0f}-unit write-down becomes due in two turns.',
            'Creditor confidence falls 25 points. The due-debt warning will pause play.',
        ])
    if action_id == 'request_french_mediation':
        return ('Paris replies next turn', [
            'Ask France to broker a half-claim settlement with Britain.',
            'France weighs its bond exposure, treasury, and domestic protests; Britain may reject the proposal.',
        ])
    if action_id == 'offer_joint_guarantee':
        return ('Shared levy proposal', [
            'Offer Britain and France a capped collection assignment instead of a naval expedition.',
            'Both governments must agree; an accepted levy transfers only actual Egyptian receipts.',
        ])
    if action_id == 'seek_french_opposition':
        return ('Raise British intervention cost', [
            'Ask Paris to oppose unilateral British enforcement.',
            'Opposition raises Britain’s mobilization cost and protest sensitivity, but Britain may still act alone.',
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
        from scenario_situation import situation_template
        rules = situation_template()['debt_rules']
        due_turn = int(world.get('turn', 0)) + int(rules['deferral_delay_turns'])
        revised = amount * float(rules['deferral_multiplier'])
        return (f'Due turn {due_turn} • {revised:.0f} units', [
            f'Now: keep {cash:.0f} treasury cash. The payment rises to {revised:.0f} and is due on turn {due_turn}.',
            f'Creditor confidence {confidence:.0%} → {max(0, confidence - .30):.0%}.',
            f'Legitimacy {legitimacy:.0%} → {min(1, legitimacy + .02):.0%}. A second deferral is unavailable.',
        ])
    if action_id == 'default_remittance':
        return ('Keep cash • creditors 0%', [
            'Default keeps cash now, sets creditor confidence to zero, and cuts legitimacy by 15 points.',
            'The Caisse will claim customs receipts next turn. Cairo can contest, consent to collection, or propose arrears; force requires naval mobilization.',
        ])
    if action_id == 'reinforce_alexandria':
        from scenario_situation import situation_template
        rules = situation_template()['naval_crisis']
        crisis = state.get('naval_crisis', {})
        current = float(crisis.get('battery_strength', rules['alexandria_battery_strength']))
        cost = float(rules['battery_reinforcement_cost'])
        stronger = current + float(rules['battery_reinforcement_strength'])
        return (f'−{cost:.0f} cash • defense {current:.0f}→{stronger:.0f}', [
            f'Pay {cost:.0f} treasury units to Egyptian workers preparing Alexandria’s batteries.',
            f'Coastal defense strength rises from {current:.0f} to {stronger:.0f}; a strong defense can deter a British fleet.',
            'This uses this turn’s major domestic decision and can be done only once while Britain mobilizes.',
        ])
    if action_id == 'close_canal':
        return ('Foreign canal transit closed • confidence −10 points', [
            'Britain cannot enter the Port Said–Ismailia route while transit is closed.',
            'A fleet already off Alexandria stays there; creditor confidence falls by 10 points.',
        ])
    occupation = state.get('occupation', {})
    if action_id == 'organize_boycott':
        return ('Occupied customs receipts ↓ for 2 turns', [
            'Merchants withhold customs cooperation for two turns; collection falls to one quarter.',
            f'Resistance {float(occupation.get("resistance", 0)):.0%} → {min(1, float(occupation.get("resistance", 0)) + .12):.0%}.'])
    if action_id == 'call_general_strike':
        return ('Occupied revenue ↓ for 2 turns • resistance ↑', [
            'Tax and customs receipts available to Britain are halved for two turns.',
            'Resistance rises 15 points and Egyptian legitimacy rises 3 points.'])
    if action_id == 'coordinate_insurgency':
        return ('British garrison −3 • civilian injuries +1', [
            'Resistance rises 18 points; Egyptian legitimacy falls 3 points.',
            'If the garrison becomes too small Britain may have to withdraw.'])
    if action_id == 'collaborate_with_occupation':
        return ('Resistance −18 • legitimacy −5 points', [
            'Local collaboration improves garrison stability and weakens resistance.',
            'It increases collaboration by 25 points and costs Egyptian legitimacy.'])
    if action_id == 'negotiate_withdrawal':
        return ('Pay 30 • request withdrawal', [
            'Britain accepts only if resistance reaches 35% or its treasury falls below 30 units.',
            'A successful offer transfers 30 units to Britain and restores Egyptian control.'])
    politics = state.get('politics', {})
    if action_id == 'pay_army_arrears':
        from scenario_situation import situation_template
        cost = float(situation_template()['politics']['officer_pay_cost'])
        loyalty = float(politics.get('army_loyalty', 0.0))
        return (f'−{cost:.0f} cash • army loyalty ↑', [
            f'Pay {cost:.0f} treasury units to Alexandria garrison households. Palace loyalty {loyalty:.0%} → {min(1, loyalty + .22):.0%}.',
            'Alexandria garrison morale also improves. Continued wages still depend on the treasury.',
        ])
    if action_id == 'promote_egyptian_officers':
        access = float(politics.get('officer_access', 0.0))
        return (f'Officer access {access:.0%}→{min(1, access + .4):.0%}', [
            'Open senior appointments to Egyptian officers: access rises 40 points and army loyalty rises 12 points.',
            'Palace authority falls 8 points as appointments move beyond the court.',
        ])
    if action_id == 'invite_representative_cabinet':
        return ('Cabinet authority ↑ • legitimacy +5pp', [
            'Invite a representative cabinet: cabinet authority rises 35 points and civilian support 15 points.',
            'Legitimacy rises 5 points; palace authority falls 18 points.',
        ])
    if action_id == 'dismiss_foreign_controllers':
        return ('Autonomy +15pp • credit −20pp', [
            'Dismiss foreign controllers: fiscal autonomy rises 15 points; creditor confidence falls 20 points.',
            'Nationalist support rises 12 points; palace authority falls 12 points.',
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
    from scenario_situation import response_label
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
            label = ACTION_LABELS.get(source, PHASE_LABELS.get(source, response_label(source) or source))
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

    cur_y = y + 68

    colors = {'urgent': (226, 102, 94), 'warning': (225, 178, 87), 'good': (112, 205, 145), 'neutral': (140, 160, 195)}
    for pressure in scenario_pressures(world):
        card_h = 70
        rect = pygame.Rect(x + 9, cur_y, w - 18, card_h)
        color = colors.get(pressure['tone'], ACCENT)
        pygame.draw.rect(surface, (34, 38, 51), rect, border_radius=5)
        pygame.draw.rect(surface, color, rect, 1, border_radius=5)
        if mouse_pos and rect.collidepoint(mouse_pos):
            world['_guided_hover_tip'] = (pressure['title'], pressure.get('details', [pressure['cause']]),
                                          rect, 'action')
        surface.blit(small_font.render(pressure['title'], True, color), (rect.x + 9, rect.y + 6))
        value_font = _scenario_font(13)
        value_lines = _wrap_text(pressure['value'], value_font, rect.w - 18)
        for idx, line in enumerate(value_lines[:2]):
            surface.blit(value_font.render(line, True, TEXT),
                         (rect.x + 9, rect.y + 25 + idx * 16))
        cause_font = _scenario_font(11)
        cause = _wrap_text(pressure['cause'], cause_font, rect.w - 18)
        for idx, line in enumerate(cause[:1]):
            surface.blit(cause_font.render(line, True, DIM),
                         (rect.x + 9, rect.y + 48 + idx * 13))
        cur_y += card_h + 4

    cur_y += 4
    from scenario_projects import strategic_strip
    strip_font = _scenario_font(12)
    strip_label_font = _scenario_font(11)
    for index, item in enumerate(strategic_strip(world)):
        strip_rect = pygame.Rect(x + 9, cur_y, w - 18, 26)
        pygame.draw.rect(surface, (34, 40, 54), strip_rect, border_radius=4)
        pygame.draw.rect(surface, (72, 85, 107), strip_rect, 1, border_radius=4)
        tone = (ACCENT if index == 0 else
                (225, 178, 87) if index == 1 else (139, 190, 166))
        surface.blit(strip_label_font.render(item['title'], True, tone),
                     (strip_rect.x + 6, strip_rect.y + 7))
        text_x = strip_rect.x + 132
        label = _fit_button_text(item['text'], strip_font, strip_rect.right - text_x - 7)
        surface.blit(strip_font.render(label, True, TEXT), (text_x, strip_rect.y + 6))
        if mouse_pos and strip_rect.collidepoint(mouse_pos):
            world['_guided_hover_tip'] = (item['title'], item['details'], strip_rect, 'action')
        cur_y += 28
    cur_y += 2
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
    from scenario_situation import situation_template
    debt_rules = situation_template()['debt_rules']
    can_defer_again = (int(state.get('deferral_count', 0)) < int(debt_rules['maximum_deferrals'])
                       and turn + int(debt_rules['deferral_delay_turns'])
                       <= int(world.get('scenario', {}).get('horizon_turns', 20)))
    tax_available = not state.get('tax_decision_taken', False)
    politics = state.get('politics', {})
    action_rows = [
        [('release_maize', 'Release maize reserves', stock > 0)],
        [('prioritize_domestic_grain', 'Keep more food in Egypt', not state.get('domestic_grain_priority', False))],
    ]
    from scenario_projects import PROJECT_DEFS, get_project
    repair_cost = PROJECT_DEFS['nile_repair']['cash_cost']
    action_rows.append([
        ('repair_delta_channels', 'Repair Delta channels',
         treasury_cash >= repair_cost and get_project(world, 'nile_repair', 'Nile Delta') is None),
        ('repair_upper_channels', 'Repair Upper channels',
         treasury_cash >= repair_cost and get_project(world, 'nile_repair', 'Upper Egypt') is None),
    ])
    office = get_project(world, 'revenue_office', 'Alexandria')
    office_cost = PROJECT_DEFS['revenue_office']['cash_cost']
    action_rows.append([('build_revenue_office', 'Staff Alexandria revenue office',
                         treasury_cash >= office_cost and office is None)])
    line = get_project(world, 'canal_line', 'Tel el Kebir')
    line_def = PROJECT_DEFS['canal_line']
    action_rows.append([('prepare_canal_line', 'Prepare Tel el Kebir defenses',
                         treasury_cash >= line_def['cash_cost'] and line is None)])
    if line and line['integrity'] < 1.0:
        repair_cost = line_def['cash_cost'] * (1.0 - line['integrity']) * .5
        action_rows.append([('repair_canal_line', 'Repair Tel el Kebir works',
                             treasury_cash >= repair_cost)])
    if (state.get('strategic_projects', {}).get('fiscal_challenge') or {}).get('status') == 'pending':
        action_rows.append([
            ('publish_revenue_accounts', 'Publish revenue accounts', True),
            ('refuse_revenue_inspection', 'Refuse Caisse inspection', True),
        ])
    if tax_available:
        action_rows.append([('reduce_fellahin_tax', 'Reduce local taxes', True),
                            ('raise_local_taxes', 'Raise local taxes', True)])
    elif state.get('extraction_level', 0) > 0:
        action_rows.append([('intensify_requisitions', 'Enforce requisitions', True)])
    if (float(politics.get('army_loyalty', 1.0)) < 0.72
            or float(politics.get('nationalist_movement', 0.0)) >= 0.35):
        army_rows = []
        if not politics.get('officers_paid'):
            army_rows.append(('pay_army_arrears', 'Pay officer arrears',
                              treasury_cash >= float(situation_template()['politics']['officer_pay_cost'])))
        if not politics.get('officers_promoted'):
            army_rows.append(('promote_egyptian_officers', 'Promote Egyptian officers', True))
        if army_rows:
            action_rows.append(army_rows)
    if (float(politics.get('palace_authority', 1.0)) < 0.72
            or float(politics.get('nationalist_movement', 0.0)) >= 0.4
            or float(state.get('fiscal_autonomy', 1.0)) < 0.9):
        cabinet_rows = []
        if not politics.get('representative_cabinet'):
            cabinet_rows.append(('invite_representative_cabinet', 'Invite representative cabinet', True))
        if not politics.get('controllers_dismissed'):
            cabinet_rows.append(('dismiss_foreign_controllers', 'Dismiss foreign controllers', True))
        if cabinet_rows:
            action_rows.append(cabinet_rows)
    if state.get('naval_crisis', {}).get('stage') == 'mobilizing':
        from scenario_situation import situation_template
        reinforce_cost = float(situation_template()['naval_crisis']['battery_reinforcement_cost'])
        action_rows.append([('reinforce_alexandria', 'Prepare Alexandria defenses',
                             not state['naval_crisis'].get('reinforced') and treasury_cash >= reinforce_cost)])
    if (state.get('payment_status') in ('defaulted', 'deferred', 'unpaid')
            and state.get('naval_crisis', {}).get('stage') in ('none', 'mobilizing')
            and not state.get('diplomatic_crisis', {}).get('egyptian_proposal')):
        action_rows.append([('request_french_mediation', 'French mediation', True),
                            ('offer_joint_guarantee', 'Joint guarantee', True)])
        action_rows.append([('seek_french_opposition', 'Seek French opposition', True)])
    if (state.get('naval_crisis', {}).get('stage') in ('mobilizing', 'ultimatum', 'blockaded')
            and state.get('geography', {}).get('canal_open')):
        action_rows.append([('close_canal', 'Close canal to foreign transit', True)])
    oversight = state.get('oversight_agreement') or {}
    if oversight.get('status') == 'active':
        action_rows.append([('comply_oversight', 'Fund inspection', treasury_cash >= 2),
                            ('seek_narrower_oversight', 'Narrow inspection',
                             treasury_cash >= 20 and not oversight.get('proposal')
                             and oversight.get('scope') != ['tax'])])
        action_rows.append([('revoke_oversight', 'Revoke oversight', True)])
    occupation = state.get('occupation', {})
    if any(owner == 'Britain' for owner in state.get('campaign', {}).get('territorial_control', {}).values()):
        action_rows.append([('organize_boycott', 'Organize customs boycott', True),
                            ('call_general_strike', 'Call general strike', True)])
        action_rows.append([('coordinate_insurgency', 'Coordinate resistance', True),
                            ('collaborate_with_occupation', 'Collaborate locally', True)])
        withdrawal_ready = (treasury_cash >= 30 and
                            (float(occupation.get('resistance', 0)) >= .35 or
                             float(next((n.government.agent.cash for n in world.get('nations', [])
                                         if n.name == 'Britain'), 100)) < 30))
        action_rows.append([('negotiate_withdrawal', 'Negotiate withdrawal', withdrawal_ready)])
    if state.get('payment_status') in ('upcoming', 'unpaid', 'deferred'):
        action_rows.append([
            ('pay_remittance', 'Pay debt service', payment_ready and treasury_cash >= scheduled_payment)
        ])
    if payment_ready:
        action_rows[-1].append(('concede_revenue', 'Concede revenue', treasury_cash >= scheduled_payment * 0.5))
        action_rows.append([
            ('defer_remittance', 'Defer debt service', can_defer_again),
            ('default_remittance', 'Default', True),
        ])
    button_h, gap = 35, 3
    action_bottom = y + h - 89
    visible_rows = max(1, (action_bottom - cur_y) // (button_h + gap))
    max_scroll = max(0, len(action_rows) - visible_rows)
    scroll = min(max_scroll, max(0, int(world.get('guided_action_scroll', 0))))
    world['guided_action_scroll'] = scroll
    world['guided_action_scroll_max'] = max_scroll
    if max_scroll:
        hint = f'Decisions {scroll + 1}–{min(len(action_rows), scroll + visible_rows)} / {len(action_rows)} • scroll panel'
        surface.blit(_scenario_font(11).render(hint, True, ACCENT), (x + 13, cur_y - 13))
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    for row in action_rows[scroll:scroll + visible_rows]:
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
            elif len(row) > 1 and action_id == 'pay_remittance':
                detail = f'−{scheduled_payment:.0f} cash • credit ↑'
            elif len(row) > 1 and action_id == 'concede_revenue':
                detail = f'−{scheduled_payment * .5:.0f} cash • autonomy ↓'
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
                    elif action_id in ('repair_delta_channels', 'repair_upper_channels',
                                       'build_revenue_office', 'prepare_canal_line'):
                        project_id, site = ({
                            'repair_delta_channels': ('nile_repair', 'Nile Delta'),
                            'repair_upper_channels': ('nile_repair', 'Upper Egypt'),
                            'build_revenue_office': ('revenue_office', 'Alexandria'),
                            'prepare_canal_line': ('canal_line', 'Tel el Kebir'),
                        })[action_id]
                        existing = get_project(world, project_id, site)
                        reason = (f'{site} already has this project.' if existing else
                                  f'The treasury needs {PROJECT_DEFS[project_id]["cash_cost"]:.0f} units to start it.')
                    elif action_id == 'repair_canal_line':
                        reason = f'The treasury needs {repair_cost:.0f} units and the original crew for repairs.'
                    elif action_id in ('reduce_fellahin_tax', 'raise_local_taxes'):
                        reason = 'A local tax decision is already in effect.'
                    elif action_id == 'defer_remittance':
                        reason = ('The Caisse grants only one deferral in this situation.'
                                  if int(state.get('deferral_count', 0)) >= int(debt_rules['maximum_deferrals'])
                                  else 'The revised due date would fall after the campaign ends.')
                    elif action_id == 'reinforce_alexandria':
                        reason = ('Alexandria’s batteries have already been prepared.'
                                  if state['naval_crisis'].get('reinforced')
                                  else f'Treasury cash is below the {reinforce_cost:.0f} units required.')
                    elif action_id == 'pay_army_arrears':
                        reason = 'The treasury cannot cover the officer arrears package.'
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
            surface.blit(detail_font.render(detail, True, DIM), (rect[0] + 7, rect[1] + 19))
        cur_y += button_h + gap

    cur_y = max(cur_y, action_bottom + 4)

    reports = state.get('foreign_reports', [])
    report_font = _scenario_font(13)
    for index, report in enumerate(reports[:2]):
        report_y = cur_y + 5 + index * 19
        if report_y + 16 >= y + h - 37:
            break
        report_rect = pygame.Rect(x + 9, report_y, w - 18, 18)
        hover = report_rect.collidepoint(mx, my)
        if hover:
            pygame.draw.rect(surface, (45, 53, 71), report_rect, border_radius=3)
            world['_guided_hover_tip'] = (
                f'{report["nation"]} situation',
                [report['summary'], report['detail']], report_rect, 'action',
            )
        delta_text = report.get('delta_label')
        if delta_text is None:
            delta_text = f'{report.get("delta", 0.0):+.1f}'
        report_line = f'{report["nation"]}: {report["stage"]} {report["energy"]:.1f} ({delta_text})'
        surface.blit(report_font.render(report_line, True, ACCENT if hover else DIM),
                     (report_rect.x + 4, report_rect.y + 2))

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
    small_font = _scenario_font(15)
    surface.blit(title_font.render(debrief.get('title', 'Campaign complete'), True, ACCENT),
                 (x + 14, y + 18))
    entries = []

    def add(value, font=small_font, color=DIM, gap=0):
        for line in _wrap_text(str(value), font, w - 36):
            entries.append((line, font, color, 23 if font is body_font else 21))
        if gap:
            entries.append(('', small_font, DIM, gap))

    def heading(value):
        add(value, body_font, TEXT, 4)

    add(debrief.get('summary', ''), body_font, TEXT, 10)
    heading('What the campaign ended with')
    for key in ('projects', 'food', 'debt', 'control', 'diplomacy', 'politics', 'authority'):
        if debrief.get(key):
            add(f'{key.title()}: {debrief[key]}', gap=4)
    for stat in debrief.get('project_social_stats', []):
        add(f"{stat['label']}: {stat['value']} — {stat['note']}", gap=4)
    diplomatic_events = debrief.get('diplomacy_history', [])
    if diplomatic_events:
        heading('Foreign decisions')
        for entry in diplomatic_events[-6:]:
            add(f'{entry["actor"]}: {entry["decision"].replace("_", " ")} — {entry["reason"]}', gap=3)
    reactions = debrief.get('creditor_reactions', [])
    if reactions:
        heading('Caisse responses')
        for headline in reactions[-3:]:
            add(f'• {headline}', gap=3)
    naval_events = debrief.get('naval_events', [])
    if naval_events:
        heading('Alexandria crisis')
        for event in naval_events[-2:]:
            add(event, gap=3)
    historical_log = debrief.get('historical_log', [])
    if historical_log:
        heading('History and game model')
        for entry in historical_log[:2] + historical_log[-2:]:
            add(f'{entry["kind"].replace("_", " ").title()}: {entry["text"]}', gap=3)
    heading('Decisions that shaped this result')
    for action in debrief.get('actions', [])[-8:]:
        add(f'• {action}', small_font, TEXT, 4)

    viewport = pygame.Rect(x + 9, y + 61, w - 18, h - 82)
    content_height = sum(height for _, _, _, height in entries)
    maximum = max(0, content_height - viewport.h)
    world['guided_debrief_scroll_max'] = (maximum + 27) // 28
    scroll_lines = max(0, min(int(world.get('guided_debrief_scroll', 0)),
                               world['guided_debrief_scroll_max']))
    world['guided_debrief_scroll'] = scroll_lines
    cursor = viewport.y - min(maximum, scroll_lines * 28)
    previous_clip = surface.get_clip()
    surface.set_clip(viewport)
    for line, font, color, line_height in entries:
        if line and cursor + line_height >= viewport.y and cursor < viewport.bottom:
            surface.blit(font.render(line, True, color), (x + 14, cursor))
        cursor += line_height
    surface.set_clip(previous_clip)
    if maximum:
        hint = f'Scroll for full debrief • {scroll_lines + 1}/{world["guided_debrief_scroll_max"] + 1}'
        surface.blit(_scenario_font(11).render(hint, True, ACCENT), (x + 14, y + h - 20))


def _draw_guided_projects_analysis(surface, world: dict, mouse_pos=None) -> None:
    """Show project inputs, ownership, and measured effects on the Analysis page."""
    from scenario_projects import PROJECT_DEFS

    x, y, w = MAP_RIGHT + 10, TOP_BAR_H + 96, WIDTH - MAP_RIGHT - 20
    h = HEIGHT - y - TICKER_H - 14
    panel = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, (25, 28, 38), panel, border_radius=7)
    pygame.draw.rect(surface, (58, 66, 86), panel, 1, border_radius=7)
    title_font = _scenario_font(19)
    body_font = _scenario_font(13)
    tiny_font = _scenario_font(12)
    surface.blit(title_font.render('Strategic projects', True, TEXT), (x + 12, y + 11))
    surface.blit(tiny_font.render('Actual inputs and receipts • one major order per turn', True, DIM),
                 (x + 12, y + 38))
    project_state = world.get('scenario_state', {}).get('strategic_projects', {})
    projects = project_state.get('projects', [])
    payments = project_state.get('payments', [])
    wages = sum(float(row.get('amount', 0)) for row in payments)
    crew_food = sum(int(row.get('food_units', 0)) for row in payments
                    if row.get('kind') == 'crew_food')
    transfers = sum(float(row['central_transfer']) for row in
                    project_state.get('revenue_reports', []))
    surface.blit(body_font.render(f'Crews paid {wages:.0f} • crew maize {crew_food} • Cairo receipts +{transfers:.0f}',
                                  True, ACCENT), (x + 12, y + 60))
    if not projects:
        for index, line in enumerate(('No project has been funded.',
                                      'Choose an irrigation repair, revenue office, or defense line',
                                      'in the Situation panel. Its site will appear on the map.')):
            surface.blit(body_font.render(line, True, DIM), (x + 12, y + 97 + index * 20))
        return
    for index, project in enumerate(projects[:4]):
        definition = PROJECT_DEFS[project['kind']]
        card = pygame.Rect(x + 9, y + 91 + index * 113, w - 18, 106)
        pygame.draw.rect(surface, (34, 40, 54), card, border_radius=5)
        pygame.draw.rect(surface, ACCENT if project['status'] == 'operating'
                         else (110, 125, 151), card, 1, border_radius=5)
        title = f'{definition["title"]} • {project["site"]}'
        surface.blit(body_font.render(_fit_button_text(title, body_font, card.w - 16), True, TEXT),
                     (card.x + 8, card.y + 7))
        rows = [
            f'{project["status"].title()} • work {project["progress"]}/{project["required_work"]} '
            f'• integrity {project["integrity"]:.0%}',
            f'Local wages {project["paid_cash"]:.0f} + {project["upkeep_paid"]:.0f} upkeep '
            f'• next upkeep {definition["upkeep"]:.0f}/turn',
        ]
        if project['kind'] == 'nile_repair':
            reports = [row for row in project_state.get('food_reports', [])
                       if row['project'] == project['id']]
            if reports:
                last = reports[-1]
                rows.append(f'Harvest {last["food_produced"]} • private stock '
                            f'{last["private_reserved"]} • underfed {last["underfed"]}/{last["households"]}')
            else:
                rows.append('Harvest and household access are measured after the next production turn.')
        elif project['kind'] == 'revenue_office':
            total = sum(row['central_transfer'] for row in project_state.get('revenue_reports', []))
            rows.append(f'{total:.0f} actual local receipts transferred to Cairo after prior claims.')
        else:
            meals = sum(row.get('food_units', 0) for row in payments
                        if row.get('project') == project['id'] and row.get('kind') == 'crew_food')
            rows.append(f'{meals} public maize fed crew • up to 55 trench strength when supplied.')
        for row_index, line in enumerate(rows):
            surface.blit(tiny_font.render(_fit_button_text(line, tiny_font, card.w - 18), True, DIM),
                         (card.x + 8, card.y + 29 + row_index * 21))
        if mouse_pos and card.collidepoint(mouse_pos):
            details = [title] + rows + [
                'The map marker shows whether this site remains under Egyptian control.',
                'Every payment and food transfer is recorded in strategic project state.',
            ]
            world['_guided_hover_tip'] = (definition['front'].title() + ' project', details, card, 'action')


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
    if world.get('scenario_id') == 'egypt_1877':
        draw_scenario_route_overlay(surface, world)
    world['_guided_hover_tip'] = None
    if world.get('scenario_id') == 'egypt_1877':
        _draw_guided_status_bar(surface, world, mouse_pos=mouse_pos)
    else:
        pygame.draw.rect(surface, (12, 14, 20), (0, 0, WIDTH, TOP_BAR_H))
        pygame.draw.line(surface, (58, 66, 86), (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 1)
    draw_guided_header(surface, world, font_small, mouse_pos=mouse_pos)
    draw_pressure_panel(surface, world, mouse_pos=mouse_pos)
    if world.get('scenario_id') == 'egypt_1877':
        from scenario_projects import project_hover_tip
        marker_tip = project_hover_tip(world, mouse_pos)
        if marker_tip is not None:
            world['_guided_hover_tip'] = marker_tip
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
        elif world.get('analysis_tab') == 'projects' and world.get('scenario_id') == 'egypt_1877':
            _draw_guided_projects_analysis(surface, world, mouse_pos=mouse_pos)
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
    card = pygame.Rect(310, 220, 780, 440 if kind in ('debt_due', 'creditor_reaction', 'naval_ultimatum', 'naval_blockade', 'landing_warning', 'capital_warning', 'dynastic_crisis', 'officer_movement', 'french_terms', 'joint_guarantee_terms') else 360)
    border = (225, 178, 87) if kind in ('debt_due', 'creditor_reaction') else (226, 102, 94)
    pygame.draw.rect(surface, (24, 29, 41), card, border_radius=10)
    pygame.draw.rect(surface, border, card, 2, border_radius=10)
    title_font, body_font = _scenario_font(24), _scenario_font(16)
    state = world.get('scenario_state', {})
    nation = _egypt_nation(world)
    if kind == 'debt_due':
        from scenario_situation import situation_template
        debt_rules = situation_template()['debt_rules']
        delay = int(debt_rules['deferral_delay_turns'])
        multiplier = float(debt_rules['deferral_multiplier'])
        amount = float(state.get('scheduled_remittance', 200.0))
        cash = float(getattr(getattr(getattr(nation, 'government', None), 'agent', None), 'cash', 0.0)) if nation else 0.0
        can_defer = (int(state.get('deferral_count', 0)) < int(debt_rules['maximum_deferrals'])
                     and int(world.get('turn', 0)) + delay <= int(world.get('scenario', {}).get('horizon_turns', 20)))
        title = 'Revised debt service is due now' if state.get('deferral_count', 0) else 'Debt service is due now'
        lines = [
            f'Treasury cash: {cash:,.0f} units. Scheduled payment: {amount:,.0f}.',
            'Default collapses creditor confidence and reduces legitimacy by 15 percentage points.',
            'Choose how to settle the debt service:',
        ]
        options = [
            ('pay_remittance', f'Pay {amount:,.0f}', cash >= amount),
            ('concede_revenue', f'Concede • pay {amount / 2:,.0f}', cash >= amount / 2),
            ('defer_remittance', 'Defer • keep cash' if can_defer else 'Defer • unavailable', can_defer),
            ('default_remittance', 'Default • severe loss', True),
        ]
    elif kind == 'creditor_reaction':
        from scenario_situation import situation_template, creditor_response_options
        action_id = warning.get('action_id', '')
        reaction = situation_template()['branches'].get(action_id, {}).get('reaction', {})
        title = reaction.get('headline', 'Creditors demand a response')
        lines = [reaction.get('body', ''), 'Choose Cairo’s response. This diplomatic reply does not use your major domestic decision this turn.']
        response_options = creditor_response_options(world, action_id)
        options = [(f'creditor_response:{response["id"]}', response['label'], response['enabled'])
                   for response in response_options]
    elif kind in ('french_terms', 'joint_guarantee_terms'):
        cash = float(getattr(getattr(getattr(nation, 'government', None), 'agent', None), 'cash', 0.0)) if nation else 0.0
        amount = float(state.get('scheduled_remittance', 0)) * .5
        if kind == 'french_terms':
            title = 'French settlement proposal'
            lines = [
                f'Paris and London propose settling the claim for {amount:,.0f} treasury units.',
                'Egypt retains its revenue offices and territory; France brokers the agreement.',
                'Accepting settles the bonds. Rejecting leaves the creditor dispute open.',
            ]
            enabled = cash >= amount
        else:
            title = 'Joint creditor guarantee'
            lines = [
                'Britain and France offer a capped 5-unit claim on actual Egyptian tax and tariff receipts each turn.',
                'Both creditors receive their bond share. The assignment ends when the claim is paid.',
                'Rejecting leaves the creditor dispute open.',
            ]
            enabled = True
        options = [('diplomacy_response:accept', 'Accept terms', enabled),
                   ('diplomacy_response:reject', 'Reject terms', True)]
    elif kind in ('naval_ultimatum', 'naval_blockade'):
        from scenario_gunboat import naval_response_options, coastal_balance
        crisis = state.get('naval_crisis', {})
        balance = coastal_balance(world)
        diplomatic = state.get('diplomatic_crisis') or {}
        french_fleet = state.get('geography', {}).get('fleets', {}).get('France')
        french_stance = diplomatic.get('french_policy', 'abstain').replace('_', ' ')
        french_status = (f'France: {french_stance}; a funded French fleet is present and '
                         f'{"may fire" if diplomatic.get("french_authorization", {}).get("bombard") else "may not fire"}.'
                         if french_fleet else f'France: {french_stance}; no French fleet is present.')
        title = 'British ultimatum at Alexandria' if kind == 'naval_ultimatum' else 'Alexandria is under naval blockade'
        lines = ([
            french_status,
            'London demands customs oversight or disarmament. Defending the batteries risks bombardment and a real trade blockade.',
            f'Force at Alexandria: Britain {balance["british_force"]:.0f}, Egyptian defense {balance["egyptian_defense"]:.0f}; ratio {balance["ratio"]:.2f}.',
        ] if kind == 'naval_ultimatum' else [
            'British guns have struck the coastal batteries and the shared trade system is blocking Alexandria’s routes.',
            'Britain pays for its fleet each turn. Its domestic unrest and treasury can force a withdrawal.',
        ])
        naval_options = naval_response_options(world, kind)
        options = [(f'naval_response:{response["id"]}', response['label'], response['enabled'])
                   for response in naval_options]
    elif kind == 'landing_warning':
        from scenario_campaign import landing_options
        fleet = state['geography']['fleets'].get('Britain', {})
        fort = state['campaign']['forts']['Alexandria']
        title = 'British landing preparations'
        lines = [
            f'British transports carry {fleet.get("transports", 0)} troops; Alexandria fort integrity {fort["integrity"]:.0f}%, ammunition {fort["ammunition"]}.',
            f'Civilian injuries so far: {state["campaign"]["civilian_casualties"]}. Choose where the Egyptian army makes its stand.',
            'The shared battle model resolves casualties and territorial control after the order.',
        ]
        campaign_options = landing_options(world)
        options = [(f'landing_response:{response["id"]}', response['label'], response['enabled'])
                   for response in campaign_options]
    elif kind == 'capital_warning':
        from scenario_occupation import response_options
        title = 'The British expedition approaches Cairo'
        control = state['campaign']['territorial_control']
        lines = [
            f'British foothold: {", ".join(site for site, holder in control.items() if holder == "Britain")}.',
            f'Egyptian resistance {state["occupation"]["resistance"]:.0%}; British garrison must keep paying supply costs.',
            'Defending Cairo uses the shared battle resolver. Losing the capital gives Britain control of the tax office.',
        ]
        capital_options = response_options(world)
        options = [(f'capital_response:{response["id"]}', response['label'], response['enabled'])
                   for response in capital_options]
    elif kind in ('dynastic_crisis', 'officer_movement'):
        from scenario_politics import response_options
        politics = state.get('politics', {})
        title = 'The khedive’s authority is contested' if kind == 'dynastic_crisis' else 'Egyptian officers demand a new government'
        lines = ([
            f'Ismail’s palace authority is {float(politics.get("palace_authority", 0)):.0%}; creditor supervision has weakened his position.',
            'Choose who governs Egypt. The player continues as the governing coalition after any succession.',
        ] if kind == 'dynastic_crisis' else [
            f'Army loyalty is {float(politics.get("army_loyalty", 0)):.0%}; the officer-civilian movement is {float(politics.get("nationalist_movement", 0)):.0%}.',
            'Choose whether the palace, a shared cabinet, or ‘Urabi’s coalition gives orders to the army.',
        ])
        political_options = response_options(world, kind)
        options = [(f'politics_response:{response["id"]}', response['label'], True)
                   for response in political_options]
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
                + f'Spends {amount:,.0f} treasury units. Marks the debt service paid, ends any collection levy, and raises creditor confidence by up to 15 points. The Caisse acknowledges payment next turn.'
                if kind == 'debt_due' else 'Enacts this debt payment.'
            ),
            'concede_revenue': (
                (f'Unavailable: the treasury has {cash:,.0f} units and needs {amount / 2:,.0f}. ' if cash < amount / 2 else '')
                + f'Spends {amount / 2:,.0f} units and restructures the payment. Creditor confidence rises by up to 15 points; fiscal autonomy falls by 25 points. The Caisse begins oversight next turn.'
                if kind == 'debt_due' else 'Enacts this revenue concession.'
            ),
            'defer_remittance': (
                ('A second deferral is unavailable. '
                 if int(state.get('deferral_count', 0)) >= int(debt_rules['maximum_deferrals'])
                 else 'The revised due date would exceed the campaign. '
                 if int(world.get('turn', 0)) + delay > int(world.get('scenario', {}).get('horizon_turns', 20))
                 else '')
                + f'Keeps cash, but makes {amount * multiplier:,.0f} units due on turn {int(world.get("turn", 0)) + delay}. Creditor confidence falls by 30 points; legitimacy rises by 2 points.'
                if kind == 'debt_due' else 'Defers the payment.'
            ),
            'default_remittance': (
                'Keeps the cash, but creditor confidence falls to zero and legitimacy drops by 15 points. Next turn, creditors claim customs; they cannot collect without Cairo’s consent or credible force.'
                if kind == 'debt_due' else 'Defaults on the payment.'
            ),
            'scenario_rescue_tax': 'Reduces local taxes, lowering treasury revenue. It can avert breakdown if unrest and legitimacy move back across their thresholds.',
            'accept_breakdown': 'Ends the campaign immediately with government breakdown.',
            'review_risk': 'Closes this warning and pauses the simulation so you can inspect the situation.',
            'continue_risk': 'Advances one turn despite the warning. The reported crisis may worsen or trigger its consequences.',
        }
        detail = consequences.get(hovered_option)
        if hovered_option.startswith('creditor_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in response_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
                if not response['enabled']:
                    if response_id == 'offer_arrears_plan' and state.get('arrears_plan_used'):
                        detail = 'Unavailable: the Caisse has already accepted one arrears plan. ' + detail
                    elif (response_id == 'offer_arrears_plan'
                          and int(world.get('turn', 0)) + 3 > int(world.get('scenario', {}).get('horizon_turns', 20))):
                        detail = 'Unavailable: the new due date would fall after the campaign ends. ' + detail
                    else:
                        detail = f'Unavailable: requires {float(response.get("requires_cash", 0.0)):,.0f} treasury units. ' + detail
        if hovered_option.startswith('diplomacy_response:'):
            detail = ('Accept the stated treaty terms and record every payment or assigned receipt in the debt ledger.'
                      if hovered_option.endswith('accept') else
                      'Reject the proposed terms. Britain and France retain their current claims and may continue escalation.')
        if hovered_option.startswith('naval_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in naval_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
                if not response['enabled']:
                    detail = (('Unavailable: the treasury cannot cover this settlement. '
                               if response_id == 'naval_settle' else '') + detail)
        if hovered_option.startswith('politics_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in political_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
        if hovered_option.startswith('landing_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in campaign_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
                if not response['enabled']:
                    detail = 'Unavailable with current canal access or treasury cash. ' + detail
        if hovered_option.startswith('capital_response:'):
            response_id = hovered_option.split(':', 1)[1]
            response = next((item for item in capital_options if item['id'] == response_id), None)
            if response is not None:
                detail = response['tooltip']
                if not response['enabled']:
                    detail = 'Unavailable: treasury cash is below 40 units. ' + detail
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
            from scenario_situation import advance_creditor_reactions
            from client.desktop.engine import ticker_push
            advance_creditor_reactions(world, int(world.get('turn', 0)), ticker_push)
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('creditor_response:'):
        from scenario_situation import resolve_creditor_response, advance_creditor_reactions
        from client.desktop.engine import ticker_push
        ok, message = resolve_creditor_response(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            advance_creditor_reactions(world, int(world.get('turn', 0)), ticker_push)
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('diplomacy_response:'):
        from scenario_diplomacy import resolve_terms
        ok, message = resolve_terms(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('naval_response:'):
        from scenario_gunboat import resolve_naval_response
        previous_modal = world.get('scenario_warning_modal')
        ok, message = resolve_naval_response(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            if world.get('scenario_warning_modal') is previous_modal:
                world['scenario_warning_modal'] = None
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('politics_response:'):
        from scenario_politics import resolve
        ok, message = resolve(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_situation import advance_creditor_reactions
            from client.desktop.engine import ticker_push
            advance_creditor_reactions(world, int(world.get('turn', 0)), ticker_push)
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('landing_response:'):
        from scenario_campaign import resolve_landing
        ok, message = resolve_landing(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
    elif action.startswith('capital_response:'):
        from scenario_occupation import resolve_capital
        ok, message = resolve_capital(world, action.split(':', 1)[1])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
        if ok:
            world['scenario_warning_modal'] = None
            from scenario_egypt_1877 import finish_due_campaign
            finish_due_campaign(world)
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
