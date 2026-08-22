"""
worldview_layers.py — Left Sidebar Map Info Layer Toggle Dock for REGNUM.

Allows switching between 6 rich information layers across the hex map:
1. Overview (Default) — General summary of elevation, population, and food prices
2. Physical & Height — Elevation in meters, biomes, and natural terrain yield bonuses
3. Population & Unrest — Demographics, starvation/hunger counts, and social unrest stages
4. Economy & Wealth — Nominal GDP/revenue, price basket, and banking deposits
5. Production & Output — Commodity output volumes, factories, and completed buildings
6. Military & Defense — Garrison troops, combat strength, veteran XP, and border threats
"""

import pygame
from worldview_camera import TOP_BAR_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN

SIDEBAR_X = 14
SIDEBAR_Y = TOP_BAR_H + 14
SIDEBAR_W = 174
SIDEBAR_H = 268
BTN_H = 34
BTN_SPACING = 6

MAP_LAYERS = [
    ('overview', '1. Overview', '1', ACCENT, 'General map overview'),
    ('physical', '2. Physical & Height', '2', (140, 225, 255), 'Elevation, biomes & terrain bonuses'),
    ('population', '3. Population & Unrest', '3', (245, 140, 60), 'Demographics, hunger & social order'),
    ('economy', '4. Economy & Wealth', '4', (120, 225, 130), 'Regional GDP, price basket & deposits'),
    ('production', '5. Production & Output', '5', (245, 210, 90), 'Resource outputs & completed buildings'),
    ('military', '6. Military & Defense', '6', (235, 80, 80), 'Troops, garrison strength & border threat'),
]


def draw_layer_sidebar(surface, world, font_small, mouse_pos=None):
    """Draw interactive left sidebar dock for switching map information layers."""
    active_layer = world.get('map_layer', 'overview')
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    # 1. Dock Container Background (Semi-Transparent Dark Glassmorphism)
    dock_rect = (SIDEBAR_X, SIDEBAR_Y, SIDEBAR_W, SIDEBAR_H)
    dock_surf = pygame.Surface((SIDEBAR_W, SIDEBAR_H), pygame.SRCALPHA)
    dock_surf.fill((16, 16, 24, 235))
    surface.blit(dock_surf, (SIDEBAR_X, SIDEBAR_Y))
    pygame.draw.rect(surface, (60, 60, 80), dock_rect, 1, border_radius=6)

    # 2. Header
    hdr = font_small.render("MAP INFO LAYERS", True, ACCENT)
    surface.blit(hdr, (SIDEBAR_X + 12, SIDEBAR_Y + 10))

    # 3. Layer Toggle Buttons
    by = SIDEBAR_Y + 34
    btn_w = SIDEBAR_W - 20
    bx = SIDEBAR_X + 10

    for key, label, key_num, color, desc in MAP_LAYERS:
        is_active = (active_layer == key)
        b_rect = (bx, by, btn_w, BTN_H)
        is_hover = b_rect[0] <= mx <= b_rect[0] + b_rect[2] and b_rect[1] <= my <= b_rect[1] + b_rect[3]

        if is_active:
            bg_col = (45, 52, 70)
            border_col = color
            txt_col = (255, 255, 255)
            # Active indicator pill
            pygame.draw.rect(surface, color, (bx - 4, by + 4, 3, BTN_H - 8), border_radius=2)
        elif is_hover:
            bg_col = (36, 38, 52)
            border_col = color
            txt_col = (255, 255, 255)
        else:
            bg_col = (24, 24, 34)
            border_col = (48, 48, 62)
            txt_col = DIM

        pygame.draw.rect(surface, bg_col, b_rect, border_radius=4)
        pygame.draw.rect(surface, border_col, b_rect, 2 if is_active else 1, border_radius=4)

        tsurf = font_small.render(label, True, txt_col)
        surface.blit(tsurf, (bx + 10, by + 9))

        by += BTN_H + BTN_SPACING


def layer_sidebar_hit(pos, world):
    """Detect click interaction on the left layer sidebar and update world['map_layer']."""
    mx, my = pos
    if not (SIDEBAR_X <= mx <= SIDEBAR_X + SIDEBAR_W and SIDEBAR_Y <= my <= SIDEBAR_Y + SIDEBAR_H):
        return False

    by = SIDEBAR_Y + 34
    btn_w = SIDEBAR_W - 20
    bx = SIDEBAR_X + 10

    for key, label, key_num, color, desc in MAP_LAYERS:
        b_rect = (bx, by, btn_w, BTN_H)
        if b_rect[0] <= mx <= b_rect[0] + b_rect[2] and b_rect[1] <= my <= b_rect[1] + b_rect[3]:
            world['map_layer'] = key
            return True
        by += BTN_H + BTN_SPACING

    return False
