"""Three material community summaries over the campaign map, without inspectors."""

import pygame

from governing_network import project
from ui_targets import register_target


BACKGROUND = (24, 29, 39)
CARD = (33, 40, 53)
TEXT = (235, 237, 244)
DIM = (175, 187, 204)
ACCENT = (230, 192, 116)


def _lines(text, font, width):
    result, line = [], ''
    for word in text.split():
        trial = f'{line} {word}'.strip()
        if line and font.size(trial)[0] > width:
            result.append(line)
            line = word
        else:
            line = trial
    return result + ([line] if line else [])


def draw_society_observation(surface, world, font_for_pixels, *, top, mouse_pos=None):
    info = project(world)
    if info is None:
        return
    title, body, small = (font_for_pixels(size) for size in (17, 13, 12))
    x, y, width = 18, top + 62, 408
    if world.get('_ui_society_observation_hidden'):
        rect = pygame.Rect(x, y, 150, 31)
        pygame.draw.rect(surface, BACKGROUND, rect, border_radius=5)
        pygame.draw.rect(surface, ACCENT, rect, 1, border_radius=5)
        surface.blit(body.render('Show communities', True, TEXT), (x + 10, y + 7))
        register_target(world, rect, 'toggle_society_observation', scope='guided')
        return
    panel = pygame.Rect(x, y, width, 396)
    register_target(world, panel, 'society_observation_body', scope='guided')
    pygame.draw.rect(surface, BACKGROUND, panel, border_radius=7)
    pygame.draw.rect(surface, (103, 119, 143), panel, 1, border_radius=7)
    surface.blit(title.render('People and policy', True, TEXT), (x + 12, y + 12))
    rect = pygame.Rect(panel.right - 62, y + 9, 51, 27)
    hover = mouse_pos is not None and rect.collidepoint(mouse_pos)
    pygame.draw.rect(surface, (61, 72, 90) if hover else CARD, rect, border_radius=4)
    surface.blit(small.render('Hide', True, TEXT), (rect.x + 11, rect.y + 6))
    register_target(world, rect, 'toggle_society_observation', scope='guided')
    stamp = ('Opening conditions' if info['turn'] == 1 else f'After turn {info["turn"]} food and taxes')
    surface.blit(small.render(stamp, True, DIM), (x + 12, y + 39))
    current_y = y + 62
    for community in info['communities']:
        card = pygame.Rect(x + 10, current_y, width - 20, 88)
        pygame.draw.rect(surface, CARD, card, border_radius=5)
        surface.blit(body.render(f'{community["title"]} ({community["count"]})', True, ACCENT),
                     (card.x + 9, card.y + 8))
        surface.blit(body.render(community['concern'], True, TEXT), (card.x + 9, card.y + 29))
        for i, line in enumerate(_lines(community['explanation'], small, card.w - 18)):
            surface.blit(small.render(line, True, DIM), (card.x + 9, card.y + 50 + i * 15))
        current_y += 94
    for i, line in enumerate(_lines(
            'Observation only. Existing politics still decides petitions and strikes.', small, width - 24)):
        surface.blit(small.render(line, True, DIM), (x + 12, current_y + 3 + i * 15))


def handle_society_action(world, action):
    if action == 'society_observation_body':
        return True
    if action != 'toggle_society_observation' or project(world) is None:
        return False
    world['_ui_society_observation_hidden'] = not world.get('_ui_society_observation_hidden', False)
    world['needs_redraw'] = True
    return True
