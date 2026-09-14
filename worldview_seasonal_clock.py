"""
worldview_seasonal_clock.py — Interactive 10-Turn Seasonal Agricultural Clock HUD for REGNUM.

Renders:
1. Current Year & 10-Turn Season Phase (Spring 🌱, Summer ☀️, Autumn 🌾, Frost 🍂, Deep Winter ❄️).
2. Live biological crop yield multiplier (+45% bumper harvest vs -45% winter trough).
3. 10-segment year ribbon showing current seasonal position with active glow.
4. Emergent famine & lean season alerts during deep winter (Turn 9).
5. Hover breakdown card explaining granary buffer inflows/outflows and off-season cottage trades.
"""

from __future__ import annotations
import math
import pygame
from worldview_camera import MAP_RIGHT, TOP_BAR_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon

# Rect: positioned right beneath the Zoom HUD buttons in the upper-right map area
SEASON_CLOCK_RECT = (MAP_RIGHT - 188, TOP_BAR_H + 46, 178, 66)

SEASON_METADATA = [
    # (Turn % 10, Season Name, Icon Kind, Theme Color, Phase Desc)
    (0, "Early Spring", "spring", (120, 225, 140), "Thaw & Sowing"),
    (1, "Mid Spring", "spring", (140, 235, 150), "Germination"),
    (2, "Late Spring", "spring", (160, 240, 160), "Baseline Growth"),
    (3, "Early Summer", "summer", (255, 230, 90), "Crop Maturation"),
    (4, "Mid Summer", "summer", (255, 215, 60), "Pre-Harvest Ripening"),
    (5, "Harvest Peak", "autumn", (255, 175, 45), "Harvest Festival (+45%)"),
    (6, "Autumn Harvest", "autumn", (245, 140, 40), "Granary Inflow (+15%)"),
    (7, "Frost Fallow", "autumn", (210, 120, 50), "Post-Harvest Tillage"),
    (8, "Early Winter", "winter", (160, 210, 245), "Dormancy & Chill"),
    (9, "Deep Winter", "winter", (120, 220, 255), "The Lean Season (-45%)"),
]


def get_season_info(t: int) -> dict:
    """Return seasonal attributes for simulation turn *t*."""
    t_mod = t % 10
    meta = SEASON_METADATA[t_mod]
    # Smooth biological sine curve: 1.0 + 0.45 * sin(2pi * (t%10 - 2) / 10)
    mult = 1.0 + 0.45 * math.sin(2.0 * math.pi * (t_mod - 2) / 10.0)
    pct_delta = int(round((mult - 1.0) * 100))

    is_winter_trough = (t_mod == 9)
    is_storing = (4 <= t_mod <= 7)
    is_buffering = (t_mod in (9, 0, 1))

    return {
        'turn': t,
        'year': (t // 10) + 1,
        'turn_in_year': t_mod,
        'name': meta[1],
        'icon': meta[2],
        'color': meta[3],
        'phase_desc': meta[4],
        'mult': mult,
        'pct_delta': pct_delta,
        'is_winter': is_winter_trough,
        'is_storing': is_storing,
        'is_buffering': is_buffering
    }


def draw_seasonal_clock(surface: pygame.Surface, world: dict, font_small: pygame.font.Font,
                        mouse_pos: tuple[int, int] | None = None) -> None:
    """Render the 10-turn seasonal agricultural clock in the top-right map viewport."""
    t = world.get('turn', 0)
    info = get_season_info(t)
    bx, by, bw, bh = SEASON_CLOCK_RECT
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    is_hover = bx <= mx <= bx + bw and by <= my <= by + bh

    # 1. Register UI hit target
    from ui_targets import register_target
    register_target(world, SEASON_CLOCK_RECT, 'seasonal_clock', tooltip_id='seasonal_clock', scope='hud')

    # 2. Semi-Transparent Glassmorphic Container
    box_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
    bg_color = (20, 22, 32, 240) if not is_hover else (30, 34, 48, 245)
    box_surf.fill(bg_color)
    surface.blit(box_surf, (bx, by))

    # Border: glow red/cyan during winter lean season, accent if hovered, otherwise subtle slate
    frame = world.get('frame', 0)
    if info['is_winter']:
        pulse = int(170 + 80 * math.sin(frame * 0.18))
        border_col = (120, 220, 255, pulse)
    else:
        border_col = ACCENT if is_hover else (65, 72, 92)
    pygame.draw.rect(surface, border_col, SEASON_CLOCK_RECT, 1, border_radius=6)

    # 3. Header Row: Season Icon + Name + Year
    icon_surf = get_icon(info['icon'], size=14)
    surface.blit(icon_surf, (bx + 8, by + 7))

    txt_season = font_small.render(info['name'], True, info['color'])
    surface.blit(txt_season, (bx + 26, by + 6))

    txt_year = font_small.render(f"Yr {info['year']}", True, DIM)
    surface.blit(txt_year, (bx + bw - txt_year.get_width() - 8, by + 6))

    # 4. Multiplier Row: Live biological food yield readout
    d = info['pct_delta']
    sign = "+" if d > 0 else ""
    delta_str = f"Yield: {sign}{d}%"
    if d > 15:
        yield_col = (120, 235, 130)  # Bumper harvest
    elif d < -15:
        yield_col = (130, 215, 255) if not info['is_winter'] else (245, 110, 110)
    else:
        yield_col = TEXT

    txt_yield = font_small.render(delta_str, True, yield_col)
    surface.blit(txt_yield, (bx + 8, by + 25))

    # Status tag: Storing vs Buffering vs Lean
    if info['is_winter']:
        tag_str = "❄ LEAN"
        tag_col = (255, 95, 95)
    elif info['is_storing']:
        tag_str = "📥 STORE"
        tag_col = (120, 225, 130)
    elif info['is_buffering']:
        tag_str = "📤 BUFFER"
        tag_col = (130, 210, 245)
    else:
        tag_str = f"T{info['turn_in_year']}/10"
        tag_col = DIM

    txt_tag = font_small.render(tag_str, True, tag_col)
    surface.blit(txt_tag, (bx + bw - txt_tag.get_width() - 8, by + 25))

    # 5. 10-Segment Year Ribbon / Dial
    ribbon_y = by + bh - 14
    ribbon_w = bw - 16
    seg_w = max(2, (ribbon_w - 9) // 10)

    for i in range(10):
        seg_x = bx + 8 + i * (seg_w + 1)
        seg_color = SEASON_METADATA[i][3]
        seg_rect = (seg_x, ribbon_y, seg_w, 6)

        if i == info['turn_in_year']:
            # Active segment glows and has bright white cap
            pygame.draw.rect(surface, (255, 255, 255), (seg_x - 1, ribbon_y - 2, seg_w + 2, 10), border_radius=2)
            pygame.draw.rect(surface, seg_color, seg_rect, border_radius=1)
        else:
            # Inactive segments: slightly dimmed
            dimmed = (int(seg_color[0] * 0.45), int(seg_color[1] * 0.45), int(seg_color[2] * 0.45))
            pygame.draw.rect(surface, dimmed, seg_rect, border_radius=1)

    # 6. Tooltip Registration
    if is_hover and not world.get('_hovered_left_tooltip'):
        world['_hovered_seasonal_clock'] = True


def draw_seasonal_clock_tooltip(surface: pygame.Surface, world: dict, font_small: pygame.font.Font,
                                mouse_pos: tuple[int, int] | None = None) -> None:
    """Render floating detailed breakdown card when the player hovers over the seasonal clock."""
    if not world.get('_hovered_seasonal_clock'):
        return

    t = world.get('turn', 0)
    info = get_season_info(t)
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    card_w = 260
    card_h = 176
    card_x = max(10, min(MAP_RIGHT - card_w - 10, mx - card_w // 2))
    card_y = min(SEASON_CLOCK_RECT[1] + SEASON_CLOCK_RECT[3] + 8, 800 - card_h - 20)

    card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
    card_surf.fill((16, 18, 28, 250))
    surface.blit(card_surf, (card_x, card_y))
    pygame.draw.rect(surface, ACCENT, (card_x, card_y, card_w, card_h), 1, border_radius=6)

    # Title
    icon_s = get_icon(info['icon'], size=16)
    surface.blit(icon_s, (card_x + 10, card_y + 10))
    txt_t = font_small.render(f"Year {info['year']} • {info['name']} (T{info['turn_in_year']})", True, (255, 255, 255))
    surface.blit(txt_t, (card_x + 32, card_y + 10))

    pygame.draw.line(surface, (60, 65, 85), (card_x + 10, card_y + 32), (card_x + card_w - 10, card_y + 32), 1)

    lines = [
        ("Biological Multiplier:", f"{info['mult']:.2f}x ({'+' if info['pct_delta']>0 else ''}{info['pct_delta']}%)",
         GREEN if info['pct_delta'] > 0 else (RED if info['pct_delta'] < 0 else TEXT)),
        ("Seasonal Phase:", info['phase_desc'], info['color']),
        ("Granary Buffer Flow:",
         "Storing 15% harvest reserve" if info['is_storing'] else
         ("Injecting up to 4.0t to market" if info['is_buffering'] else "Stable storage"),
         (120, 225, 130) if info['is_storing'] else ((130, 210, 245) if info['is_buffering'] else DIM)),
        ("Off-Season Labor:",
         "Shifting to spinning & weaving" if info['turn_in_year'] in (8, 9, 0) else "Field cultivation active",
         (245, 205, 90)),
        ("Metabolic Vulnerability:",
         "HIGH: Depleted soil + no guano = famine!" if info['is_winter'] else "Moderate: Monitor fertilizer stock",
         RED if info['is_winter'] else DIM),
    ]

    yy = card_y + 40
    for label, val, val_col in lines:
        l_surf = font_small.render(label, True, DIM)
        surface.blit(l_surf, (card_x + 10, yy))
        yy += 14
        v_surf = font_small.render(val, True, val_col)
        surface.blit(v_surf, (card_x + 16, yy))
        yy += 18
