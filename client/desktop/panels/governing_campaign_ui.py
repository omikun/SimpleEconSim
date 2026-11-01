"""Compact policy/dispute interface for autonomous civilian organization."""

import pygame

from governing_network import project, is_governing
from governing_actions import project_actions, execute
from ui_targets import register_target
from client.desktop.panels.governing_network_ui import _lines, BACKGROUND, CARD, TEXT, DIM, ACCENT


def _fit(text, font, width):
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + '…')[0] > width:
        text = text[:-1]
    return text + '…' if text else ''


def _button(surface, world, rect, action, font, *, mouse_pos=None, compact=False):
    enabled = action['enabled']
    hover = mouse_pos is not None and rect.collidepoint(mouse_pos)
    pygame.draw.rect(surface, (52, 65, 83) if hover and enabled else CARD if enabled else (28, 33, 43), rect, border_radius=4)
    pygame.draw.rect(surface, ACCENT if enabled else (66, 75, 89), rect, 1, border_radius=4)
    if enabled:
        register_target(world, rect, ('governing_action', action['id'], action['tile']), scope='guided')
    surface.blit(font.render(_fit(action['label'], font, rect.w - 12), True, TEXT if enabled else DIM),
                 (rect.x + 6, rect.y + 5))
    detail = action['detail'] if enabled or not action['reason'] else action['reason']
    for i, line in enumerate(_lines(detail, font, rect.w - 12)[:2]):
        surface.blit(font.render(line, True, DIM), (rect.x + 6, rect.y + 23 + i * 13))
    line = _fit(action['consequence'], font, rect.w - 12)
    surface.blit(font.render(line, True, DIM), (rect.x + 6, rect.bottom - 15))


def draw_panel(surface, world, font_for_pixels, *, x, y, width, height, mouse_pos=None):
    info, choices = project(world), project_actions(world)
    title, body, small = (font_for_pixels(size) for size in (18, 13, 11))
    panel = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, BACKGROUND, panel, border_radius=7)
    pygame.draw.rect(surface, (73, 85, 106), panel, 1, border_radius=7)
    surface.blit(title.render('Governing Egypt', True, TEXT), (x + 12, y + 12))
    all_rect = pygame.Rect(x + width - 105, y + 10, 94, 27)
    pygame.draw.rect(surface, CARD, all_rect, border_radius=4)
    surface.blit(small.render('All policies', True, ACCENT), (all_rect.x + 14, all_rect.y + 7))
    register_target(world, all_rect, 'governing_all_policies', scope='guided')
    surface.blit(small.render('One decision per turn · groups act for themselves', True, DIM), (x + 12, y + 42))
    yy = y + 63
    metrics = [f'Treasury {choices["treasury"]:.1f} · public maize {choices["public_maize"]}',
               f'Private reserved maize {choices["private_maize"]}',
               f'Debt {choices["payment_status"]} · due turn {choices["due_turn"]}']
    for line in metrics:
        surface.blit(body.render(line, True, TEXT), (x + 12, yy))
        yy += 19
    yy += 8
    surface.blit(body.render('Food policy', True, ACCENT), (x + 12, yy))
    yy += 22
    gap = 5
    bw = (width - 24 - gap) // 2
    for index, action in enumerate(choices['food']):
        rect = pygame.Rect(x + 12 + index % 2 * (bw + gap), yy + index // 2 * 68, bw, 63)
        _button(surface, world, rect, action, small, mouse_pos=mouse_pos)
    yy += 142
    surface.blit(body.render('Organized demands', True, ACCENT), (x + 12, yy))
    yy += 22
    if not info['disputes']:
        for line in _lines('No current organized demand. You can advance without a political upkeep action.', small, width - 24):
            surface.blit(small.render(line, True, DIM), (x + 12, yy))
            yy += 15
        yy += 8
    for dispute in info['disputes']:
        surface.blit(body.render(f'{dispute["title"]} · {dispute["count"]}', True, TEXT), (x + 12, yy))
        yy += 18
        explanation = f'{dispute["striking"]} in this walkout · focus: {dispute["name"]}'
        surface.blit(small.render(_fit(explanation, small, width - 24), True, DIM), (x + 12, yy))
        yy += 17
        action = choices['responses'][dispute['id']]
        rect = pygame.Rect(x + 12, yy, width - 24, 64)
        _button(surface, world, rect, action, small, mouse_pos=mouse_pos, compact=True)
        yy += 71
    if choices['debt']:
        surface.blit(body.render('Debt decision is due', True, ACCENT), (x + 12, yy))
        yy += 21
        for index, action in enumerate(choices['debt']):
            rect = pygame.Rect(x + 12 + index % 2 * (bw + gap), yy + index // 2 * 69, bw, 64)
            _button(surface, world, rect, action, small, mouse_pos=mouse_pos, compact=True)
        yy += 138
    feedback = world.get('scenario_feedback') or ('Decision recorded. Advance to see the results.'
                                                  if choices['spent'] else 'Advance when ready; organizing runs automatically.')
    for index, line in enumerate(_lines(feedback, small, width - 24)[:3]):
        surface.blit(small.render(line, True, ACCENT), (x + 12, y + height - 48 + index * 14))


def draw_back(surface, world, font, *, x, y, width):
    rect = pygame.Rect(x + width - 140, y + 9, 128, 27)
    pygame.draw.rect(surface, CARD, rect, border_radius=4)
    surface.blit(font.render('Back to governing', True, ACCENT), (rect.x + 9, rect.y + 7))
    register_target(world, rect, 'governing_back', scope='guided')


def handle_action(world, action):
    if not is_governing(world):
        return False
    if action == 'governing_all_policies':
        world['_ui_governing_all_policies'] = True
        world['guided_action_scroll'] = 0
    elif action == 'governing_back':
        world['_ui_governing_all_policies'] = False
    elif isinstance(action, tuple) and action[0] == 'governing_action':
        ok, message = execute(world, action[1], action[2])
        world['scenario_feedback'] = message if ok else f'Not enacted: {message}'
    else:
        return False
    world['needs_redraw'] = True
    return True


def scroll(world, wheel_delta):
    if not is_governing(world) or not world.get('_ui_governing_all_policies'):
        return False
    maximum = world.get('guided_action_scroll_max', 0)
    world['guided_action_scroll'] = max(0, min(maximum, world.get('guided_action_scroll', 0) - wheel_delta))
    world['needs_redraw'] = True
    return True


def warning_open(world):
    warning = world.get('scenario_warning_modal')
    return bool(warning and warning.get('kind') != 'debt_due' and is_governing(world))


def draw_warning(surface, world, mouse_pos=None):
    if warning_open(world):
        from worldview_scenario_ui import draw_scenario_warning_modal
        draw_scenario_warning_modal(surface, world, mouse_pos)


def handle_warning(pos, world):
    if not warning_open(world):
        return False
    from worldview_scenario_ui import scenario_warning_modal_hit
    return scenario_warning_modal_hit(pos, world)
