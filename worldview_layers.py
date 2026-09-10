"""
worldview_layers.py — Bottom-Left Map Info Layer Drop-Up Dock for REGNUM.

Allows switching between 6 rich information layers across the hex map:
1. Overview (Default) — General summary of elevation, population, and food prices
2. Physical & Height — Elevation in meters, biomes, and natural terrain yield bonuses
3. Population & Unrest — Demographics, starvation/hunger counts, and social unrest stages
4. Economy & Wealth — Nominal GDP/revenue, price basket, and banking deposits
5. Production & Output — Commodity output volumes, factories, and completed buildings
6. Military & Defense — Garrison troops, combat strength, veteran XP, and border threats

Docked in the bottom-left corner with a sleek upward drop-up menu.
"""

import pygame
from worldview_camera import HEIGHT, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from worldview_tooltips import get_button_tooltip_data

SIDEBAR_X = 14
SIDEBAR_W = 184
BTN_H = 32
BTN_SPACING = 5

MAP_LAYERS = [
    ('overview', '1. Overview', '1', ACCENT, 'General map overview'),
    ('physical', '2. Physical & Height', '2', (140, 225, 255), 'Elevation, biomes & terrain bonuses'),
    ('population', '3. Population & Unrest', '3', (245, 140, 60), 'Demographics, hunger & social order'),
    ('economy', '4. Economy & Wealth', '4', (120, 225, 130), 'Regional GDP, price basket & deposits'),
    ('production', '5. Production & Output', '5', (245, 210, 90), 'Resource outputs & completed buildings'),
    ('military', '6. Military & Defense', '6', (235, 80, 80), 'Troops, garrison strength & border threat'),
    ('enclosure', '7. Land Tenure', '7', (215, 175, 75), 'Customary commons vs enclosed plots'),
    ('exploitation', '8. Exploitation & Strikes', '8', (235, 75, 75), 'Surplus rate s/v & active wildcat strikes'),
    ('externalities', '9. Ecology & Rift', '9', (100, 215, 140), 'Soil fertility, smog & toxic runoff'),
]

DOCK_H = 36 + len(MAP_LAYERS) * (BTN_H + BTN_SPACING) + 4  # 262px
PILL_H = 28
PILL_Y = HEIGHT - TICKER_H - 36
DOCK_Y = HEIGHT - TICKER_H - 10 - DOCK_H

# Backward compatibility alias
SIDEBAR_Y = DOCK_Y


def draw_layer_sidebar(surface, world, font_small, mouse_pos=None):
    """Draw interactive bottom-left layer dock that drops UP above the bottom bar."""
    active_layer = world.get('map_layer', 'overview')
    is_collapsed = world.get('layers_collapsed', False)
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    # Active layer lookup for collapsed summary
    active_item = next((item for item in MAP_LAYERS if item[0] == active_layer), MAP_LAYERS[0])
    active_color = active_item[3]
    active_short = active_item[1].split('. ', 1)[-1]

    if is_collapsed:
        # Compact Floating Pill / Badge in Bottom-Left Corner
        pill_rect = (SIDEBAR_X, PILL_Y, SIDEBAR_W, PILL_H)
        from ui_targets import register_target
        register_target(world, pill_rect, 'expand_layers', tooltip_id=f"layer_{active_layer}", scope='layers')
        is_hover = pill_rect[0] <= mx <= pill_rect[0] + SIDEBAR_W and pill_rect[1] <= my <= pill_rect[1] + PILL_H

        pill_surf = pygame.Surface((SIDEBAR_W, PILL_H), pygame.SRCALPHA)
        pill_surf.fill((16, 18, 26, 240) if not is_hover else (30, 34, 48, 245))
        surface.blit(pill_surf, (SIDEBAR_X, PILL_Y))
        pygame.draw.rect(surface, active_color if is_hover else (65, 70, 90), pill_rect, 1, border_radius=5)

        # Indicator dot
        pygame.draw.circle(surface, active_color, (SIDEBAR_X + 12, PILL_Y + PILL_H // 2), 4)

        txt = font_small.render(f"Layer: {active_short}", True, TEXT if not is_hover else (255, 255, 255))
        surface.blit(txt, (SIDEBAR_X + 22, PILL_Y + 5))

        # Upward chevron icon indicating drop-up expansion
        arrow = font_small.render("▲", True, active_color)
        surface.blit(arrow, (SIDEBAR_X + SIDEBAR_W - 18, PILL_Y + 6))

        if is_hover and not world.get('_hovered_left_tooltip'):
            tdata = get_button_tooltip_data(f"layer_{active_layer}", world)
            if tdata:
                tdata['btn_rect'] = pill_rect
                world['_hovered_left_tooltip'] = tdata
        return

    # 1. Expanded Drop-Up Container Background (Semi-Transparent Glassmorphism)
    dock_rect = (SIDEBAR_X, DOCK_Y, SIDEBAR_W, DOCK_H)
    dock_surf = pygame.Surface((SIDEBAR_W, DOCK_H), pygame.SRCALPHA)
    dock_surf.fill((16, 18, 26, 245))
    surface.blit(dock_surf, (SIDEBAR_X, DOCK_Y))
    pygame.draw.rect(surface, (65, 70, 90), dock_rect, 1, border_radius=8)

    # 2. Header: Title + Collapse Button
    from ui_targets import register_target
    hdr_rect = (SIDEBAR_X, DOCK_Y, SIDEBAR_W, 32)
    register_target(world, hdr_rect, 'collapse_layers', scope='layers')

    txt_hdr = font_small.render("Map Overlays & Views", True, (240, 240, 255))
    surface.blit(txt_hdr, (SIDEBAR_X + 10, DOCK_Y + 7))

    col_btn = (SIDEBAR_X + SIDEBAR_W - 24, DOCK_Y + 7, 18, 18)
    col_hov = col_btn[0] <= mx <= col_btn[0] + 18 and col_btn[1] <= my <= col_btn[1] + 18
    pygame.draw.rect(surface, (40, 44, 60) if col_hov else (24, 26, 36), col_btn, border_radius=3)
    pygame.draw.rect(surface, ACCENT if col_hov else (65, 70, 90), col_btn, 1, border_radius=3)
    arrow_down = font_small.render("▼", True, (255, 255, 255) if col_hov else DIM)
    surface.blit(arrow_down, arrow_down.get_rect(center=(col_btn[0] + col_btn[2] // 2, col_btn[1] + col_btn[3] // 2)))

    # 3. Layer Toggle Buttons
    by = DOCK_Y + 34
    btn_w = SIDEBAR_W - 20
    bx = SIDEBAR_X + 10

    for key, label, key_num, color, desc in MAP_LAYERS:
        is_active = (active_layer == key)
        b_rect = (bx, by, btn_w, BTN_H)
        register_target(world, b_rect, ('map_layer', key), tooltip_id=f"layer_{key}", scope='layers')
        is_hover = b_rect[0] <= mx <= b_rect[0] + btn_w and b_rect[1] <= my <= b_rect[1] + BTN_H

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
        surface.blit(tsurf, (bx + 10, by + 8))

        if is_hover and not world.get('_hovered_left_tooltip'):
            tdata = get_button_tooltip_data(f"layer_{key}", world)
            if tdata:
                tdata['btn_rect'] = b_rect
                world['_hovered_left_tooltip'] = tdata

        by += BTN_H + BTN_SPACING


def layer_sidebar_hit(pos, world):
    """Detect click interaction on the bottom-left layer dock and update world['map_layer'] or collapse state."""
    if world is not None:
        from ui_targets import find_target
        t = find_target(world, pos, scope='layers')
        if t is not None:
            if t.action == 'expand_layers':
                world['layers_collapsed'] = False
                return True
            elif t.action == 'collapse_layers':
                world['layers_collapsed'] = True
                return True
            elif isinstance(t.action, tuple) and t.action[0] == 'map_layer':
                world['map_layer'] = t.action[1]
                return True

    # Legacy fallback calculation
    mx, my = pos
    is_collapsed = world.get('layers_collapsed', False)

    if is_collapsed:
        # Check bottom pill hitbox
        if (SIDEBAR_X <= mx <= SIDEBAR_X + SIDEBAR_W and PILL_Y <= my <= PILL_Y + PILL_H) or \
           (SIDEBAR_X <= mx <= SIDEBAR_X + SIDEBAR_W and DOCK_Y <= my <= DOCK_Y + 34):
            world['layers_collapsed'] = False
            return True
        return False

    if not (SIDEBAR_X <= mx <= SIDEBAR_X + SIDEBAR_W and DOCK_Y <= my <= DOCK_Y + DOCK_H):
        return False

    # Header / Collapse button click
    if DOCK_Y <= my <= DOCK_Y + 32:
        world['layers_collapsed'] = True
        return True

    by = DOCK_Y + 34
    btn_w = SIDEBAR_W - 20
    bx = SIDEBAR_X + 10

    for key, label, key_num, color, desc in MAP_LAYERS:
        b_rect = (bx, by, btn_w, BTN_H)
        if b_rect[0] <= mx <= b_rect[0] + b_rect[2] and b_rect[1] <= my <= b_rect[1] + b_rect[3]:
            world['map_layer'] = key
            return True
        by += BTN_H + BTN_SPACING

    return True
