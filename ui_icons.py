"""
ui_icons.py — High-Definition Procedural Icon Renderer for REGNUM.

Generates crisp, anti-aliased, color-coded pixel vector icon surfaces that render
reliably across all operating systems without relying on OS emoji fonts:
- Resources: Arable Silt, Timber, Iron Ore, Coal, Pasture/Flax, Petroleum, Rare Minerals
- Domains: Agronomy, Manufacturing, Civil Engineering, Finance, Military
- System: Policies, Diplomacy, Treasury, War, Checkmark, Warning
"""

from __future__ import annotations
import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tile_resources import TileResource

_ICON_CACHE: dict[tuple[str, int], pygame.Surface] = {}


def get_icon(kind: str, size: int = 16) -> pygame.Surface:
    """Return a cached procedural icon surface for the given icon kind and pixel size."""
    key = (kind, size)
    surf = _ICON_CACHE.get(key)
    if surf is not None:
        return surf

    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    s = float(size)

    # -------------------------------------------------------------------------
    # NATURAL RESOURCES
    # -------------------------------------------------------------------------
    if kind in ('arable_silt', 'agronomy', 'grain'):
        # Golden wheat grain sheaf
        pygame.draw.line(surf, (245, 205, 70), (s * 0.3, s * 0.85), (s * 0.75, s * 0.15), max(1, int(s // 9)))
        pygame.draw.circle(surf, (255, 225, 90), (int(s * 0.72), int(s * 0.2)), int(s // 5))
        pygame.draw.circle(surf, (245, 205, 70), (int(s * 0.58), int(s * 0.38)), int(s // 5.5))
        pygame.draw.circle(surf, (235, 195, 60), (int(s * 0.44), int(s * 0.56)), int(s // 6))
        pygame.draw.circle(surf, (220, 180, 50), (int(s * 0.32), int(s * 0.72)), int(s // 7))

    elif kind in ('timber', 'wood', 'forestry'):
        # Emerald evergreen pine tree
        pts1 = [(s * 0.5, s * 0.1), (s * 0.22, s * 0.48), (s * 0.78, s * 0.48)]
        pts2 = [(s * 0.5, s * 0.36), (s * 0.14, s * 0.76), (s * 0.86, s * 0.76)]
        pygame.draw.polygon(surf, (60, 185, 85), pts1)
        pygame.draw.polygon(surf, (45, 150, 65), pts2)
        pygame.draw.rect(surf, (140, 90, 50), (s * 0.42, s * 0.76, s * 0.16, s * 0.2))

    elif kind in ('iron_ore', 'iron', 'mining'):
        # Mountain iron ore rock & ingot
        pts = [(s * 0.2, s * 0.55), (s * 0.5, s * 0.15), (s * 0.85, s * 0.4), (s * 0.75, s * 0.85), (s * 0.25, s * 0.8)]
        pygame.draw.polygon(surf, (215, 115, 65), pts)
        pygame.draw.polygon(surf, (250, 155, 95), [(s * 0.5, s * 0.15), (s * 0.85, s * 0.4), (s * 0.6, s * 0.55)])
        pygame.draw.line(surf, (255, 200, 150), (s * 0.5, s * 0.15), (s * 0.6, s * 0.55), 1)

    elif kind in ('coal_seam', 'coal'):
        # Faceted dark anthracite coal nugget
        pts = [(s * 0.15, s * 0.45), (s * 0.45, s * 0.15), (s * 0.85, s * 0.3), (s * 0.82, s * 0.82), (s * 0.35, s * 0.88)]
        pygame.draw.polygon(surf, (75, 78, 92), pts)
        pygame.draw.polygon(surf, (130, 135, 155), [(s * 0.45, s * 0.15), (s * 0.85, s * 0.3), (s * 0.58, s * 0.52)])
        pygame.draw.line(surf, (180, 185, 205), (s * 0.45, s * 0.15), (s * 0.58, s * 0.52), 1)

    elif kind in ('pasture_flax', 'pasture', 'wool', 'flax'):
        # Soft wool puff & linen spool
        pygame.draw.circle(surf, (240, 235, 200), (int(s * 0.38), int(s * 0.5)), int(s // 3.8))
        pygame.draw.circle(surf, (255, 250, 220), (int(s * 0.62), int(s * 0.45)), int(s // 3.8))
        pygame.draw.circle(surf, (230, 220, 180), (int(s * 0.5), int(s * 0.68)), int(s // 4.5))

    elif kind in ('crude_petroleum', 'petroleum', 'oil'):
        # Industrial oil drum barrel
        pygame.draw.rect(surf, (55, 58, 70), (s * 0.22, s * 0.25, s * 0.56, s * 0.65), border_radius=max(2, int(s // 8)))
        pygame.draw.ellipse(surf, (235, 185, 50), (s * 0.22, s * 0.16, s * 0.56, s * 0.22))
        pygame.draw.line(surf, (95, 100, 118), (s * 0.22, s * 0.48), (s * 0.78, s * 0.48), 1)
        pygame.draw.line(surf, (95, 100, 118), (s * 0.22, s * 0.70), (s * 0.78, s * 0.70), 1)

    elif kind in ('rare_minerals', 'quartz', 'electricity'):
        # Electric crystal lightning
        pts = [(s * 0.5, s * 0.08), (s * 0.85, s * 0.5), (s * 0.5, s * 0.92), (s * 0.15, s * 0.5)]
        pygame.draw.polygon(surf, (70, 210, 255), pts)
        pygame.draw.polygon(surf, (190, 245, 255), [(s * 0.5, s * 0.08), (s * 0.85, s * 0.5), (s * 0.5, s * 0.5)])
        pygame.draw.line(surf, (255, 255, 255), (s * 0.5, s * 0.08), (s * 0.5, s * 0.92), 1)

    # -------------------------------------------------------------------------
    # DOMAINS & SYSTEM
    # -------------------------------------------------------------------------
    elif kind in ('manufacturing', 'industry', 'workshop'):
        # Mechanical cog gear
        pygame.draw.circle(surf, (190, 195, 215), (int(s * 0.5), int(s * 0.5)), int(s * 0.4))
        pygame.draw.circle(surf, (30, 32, 42), (int(s * 0.5), int(s * 0.5)), int(s * 0.2))
        for angle in (0, 45, 90, 135):
            pygame.draw.rect(surf, (190, 195, 215), (s * 0.42, s * 0.06, s * 0.16, s * 0.88), border_radius=1)

    elif kind in ('civil_engineering', 'engineering', 'mountain'):
        # Mountain peak with road/bridge pass
        pts = [(s * 0.5, s * 0.15), (s * 0.1, s * 0.85), (s * 0.9, s * 0.85)]
        pygame.draw.polygon(surf, (120, 130, 150), pts)
        pygame.draw.polygon(surf, (235, 240, 250), [(s * 0.5, s * 0.15), (s * 0.35, s * 0.45), (s * 0.65, s * 0.45)])
        pygame.draw.line(surf, (245, 205, 70), (s * 0.35, s * 0.85), (s * 0.65, s * 0.55), 2)

    elif kind in ('finance', 'banking', 'granary'):
        # Classical bank column temple
        pygame.draw.polygon(surf, (235, 205, 80), [(s * 0.5, s * 0.12), (s * 0.15, s * 0.35), (s * 0.85, s * 0.35)])
        pygame.draw.rect(surf, (235, 205, 80), (s * 0.24, s * 0.38, s * 0.12, s * 0.42))
        pygame.draw.rect(surf, (235, 205, 80), (s * 0.64, s * 0.38, s * 0.12, s * 0.42))
        pygame.draw.rect(surf, (235, 205, 80), (s * 0.15, s * 0.82, s * 0.7, s * 0.12), border_radius=1)

    elif kind in ('military', 'war', 'army'):
        # Crossed swords
        pygame.draw.line(surf, (235, 80, 80), (s * 0.15, s * 0.15), (s * 0.85, s * 0.85), 2)
        pygame.draw.line(surf, (235, 80, 80), (s * 0.85, s * 0.15), (s * 0.15, s * 0.85), 2)
        pygame.draw.circle(surf, (255, 215, 90), (int(s * 0.5), int(s * 0.5)), int(s // 5))

    elif kind in ('policies', 'law', 'scales', 'net'):
        # Golden balance scales
        pygame.draw.line(surf, (245, 210, 70), (s * 0.5, s * 0.15), (s * 0.5, s * 0.85), 2)
        pygame.draw.line(surf, (245, 210, 70), (s * 0.2, s * 0.32), (s * 0.8, s * 0.32), 2)
        pygame.draw.polygon(surf, (245, 210, 70), [(s * 0.2, s * 0.32), (s * 0.1, s * 0.6), (s * 0.3, s * 0.6)])
        pygame.draw.polygon(surf, (245, 210, 70), [(s * 0.8, s * 0.32), (s * 0.7, s * 0.6), (s * 0.9, s * 0.6)])

    # -------------------------------------------------------------------------
    # TOP-BAR & STRUCTURES
    # -------------------------------------------------------------------------
    elif kind in ('crown', 'nation', 'sovereign'):
        # Sovereign golden crown
        pts = [(s * 0.1, s * 0.75), (s * 0.1, s * 0.35), (s * 0.35, s * 0.5),
               (s * 0.5, s * 0.2), (s * 0.65, s * 0.5), (s * 0.9, s * 0.35), (s * 0.9, s * 0.75)]
        pygame.draw.polygon(surf, (245, 205, 60), pts)
        pygame.draw.rect(surf, (220, 160, 40), (s * 0.1, s * 0.75, s * 0.8, s * 0.15))

    elif kind in ('pop', 'population', 'citizens'):
        # Citizens silhouette
        pygame.draw.circle(surf, (170, 200, 240), (int(s * 0.4), int(s * 0.35)), int(s * 0.22))
        pygame.draw.circle(surf, (140, 170, 215), (int(s * 0.75), int(s * 0.4)), int(s * 0.18))
        pygame.draw.ellipse(surf, (170, 200, 240), (s * 0.15, s * 0.58, s * 0.5, s * 0.4))
        pygame.draw.ellipse(surf, (140, 170, 215), (s * 0.55, s * 0.62, s * 0.4, s * 0.35))

    elif kind in ('treasury', 'gold', 'money'):
        # Gold coin
        pygame.draw.circle(surf, (245, 205, 60), (int(s * 0.5), int(s * 0.5)), int(s * 0.42))
        pygame.draw.circle(surf, (220, 160, 40), (int(s * 0.5), int(s * 0.5)), int(s * 0.42), 1)
        pygame.draw.line(surf, (140, 90, 20), (s * 0.5, s * 0.25), (s * 0.5, s * 0.75), 1)

    elif kind in ('gdp', 'growth', 'economy'):
        # 3 ascending GDP chart bars
        pygame.draw.rect(surf, (80, 200, 120), (s * 0.15, s * 0.55, s * 0.2, s * 0.35), border_radius=1)
        pygame.draw.rect(surf, (100, 220, 140), (s * 0.42, s * 0.35, s * 0.2, s * 0.55), border_radius=1)
        pygame.draw.rect(surf, (130, 240, 170), (s * 0.7, s * 0.15, s * 0.2, s * 0.75), border_radius=1)

    elif kind in ('col', 'cost_of_living', 'living'):
        # Price tag & grain loaf
        pygame.draw.circle(surf, (220, 170, 100), (int(s * 0.5), int(s * 0.5)), int(s * 0.38))
        pygame.draw.line(surf, (255, 220, 160), (s * 0.3, s * 0.5), (s * 0.7, s * 0.5), 1)

    elif kind in ('ex', 'exports'):
        # Outbound export arrow
        pygame.draw.line(surf, (120, 220, 130), (s * 0.2, s * 0.8), (s * 0.8, s * 0.2), 2)
        pygame.draw.polygon(surf, (120, 220, 130), [(s * 0.8, s * 0.2), (s * 0.45, s * 0.2), (s * 0.8, s * 0.55)])

    elif kind in ('im', 'imports'):
        # Inbound import arrow
        pygame.draw.line(surf, (120, 180, 255), (s * 0.2, s * 0.2), (s * 0.8, s * 0.8), 2)
        pygame.draw.polygon(surf, (120, 180, 255), [(s * 0.8, s * 0.8), (s * 0.45, s * 0.8), (s * 0.8, s * 0.45)])

    elif kind in ('protest', 'unrest', 'alert'):
        # Red warning triangle & flare
        pts = [(s * 0.5, s * 0.12), (s * 0.1, s * 0.88), (s * 0.9, s * 0.88)]
        pygame.draw.polygon(surf, (245, 80, 80), pts)
        pygame.draw.line(surf, (255, 255, 255), (s * 0.5, s * 0.38), (s * 0.5, s * 0.62), 2)
        pygame.draw.circle(surf, (255, 255, 255), (int(s * 0.5), int(s * 0.75)), 1)

    elif kind in ('check', 'checkmark', 'ready'):
        # Green checkmark
        pts = [(s * 0.2, s * 0.55), (s * 0.45, s * 0.8), (s * 0.85, s * 0.25)]
        pygame.draw.lines(surf, (80, 225, 110), False, pts, max(2, int(s // 7)))

    elif kind in ('cross', 'blocked', 'missing'):
        # Red X
        pygame.draw.line(surf, (235, 80, 80), (s * 0.25, s * 0.25), (s * 0.75, s * 0.75), max(2, int(s // 7)))
        pygame.draw.line(surf, (235, 80, 80), (s * 0.75, s * 0.25), (s * 0.25, s * 0.75), max(2, int(s // 7)))

    elif kind in ('hammer', 'build', 'construction'):
        # Crisp construction hammer
        pygame.draw.line(surf, (190, 140, 80), (s * 0.25, s * 0.78), (s * 0.68, s * 0.32), max(2, int(s // 6)))
        head_pts = [(s * 0.52, s * 0.2), (s * 0.78, s * 0.1), (s * 0.88, s * 0.25), (s * 0.65, s * 0.38)]
        pygame.draw.polygon(surf, (215, 225, 245), head_pts)
        pygame.draw.polygon(surf, (130, 145, 170), head_pts, 1)

    elif kind in ('municipal', 'city', 'temple', 'pillar'):
        # Classical municipal building / temple columns
        pygame.draw.polygon(surf, (235, 215, 120), [(s * 0.5, s * 0.14), (s * 0.15, s * 0.4), (s * 0.85, s * 0.4)])
        pygame.draw.rect(surf, (210, 195, 110), (s * 0.22, s * 0.4, s * 0.12, s * 0.35))
        pygame.draw.rect(surf, (210, 195, 110), (s * 0.44, s * 0.4, s * 0.12, s * 0.35))
        pygame.draw.rect(surf, (210, 195, 110), (s * 0.66, s * 0.4, s * 0.12, s * 0.35))
        pygame.draw.rect(surf, (245, 225, 130), (s * 0.12, s * 0.75, s * 0.76, s * 0.12))

    elif kind in ('province', 'provincial', 'shield'):
        # Provincial heraldic shield
        pts = [(s * 0.2, s * 0.18), (s * 0.8, s * 0.18), (s * 0.8, s * 0.55), (s * 0.5, s * 0.85), (s * 0.2, s * 0.55)]
        pygame.draw.polygon(surf, (90, 175, 245), pts)
        pygame.draw.polygon(surf, (160, 220, 255), pts, 1)
        pygame.draw.line(surf, (255, 255, 255), (s * 0.5, s * 0.22), (s * 0.5, s * 0.75), 1)

    elif kind in ('bank', 'loan'):
        # Bank vault coin
        pygame.draw.circle(surf, (130, 210, 255), (int(s * 0.5), int(s * 0.5)), int(s * 0.38))
        pygame.draw.circle(surf, (60, 140, 220), (int(s * 0.5), int(s * 0.5)), int(s * 0.38), 1)
        pygame.draw.line(surf, (255, 255, 255), (s * 0.5, s * 0.25), (s * 0.5, s * 0.75), 2)

    elif kind in ('scale', 'equalize', 'justice', 'balance'):
        # Scales of justice / fiscal equalization
        pygame.draw.line(surf, (245, 215, 120), (s * 0.5, s * 0.15), (s * 0.5, s * 0.85), 2)
        pygame.draw.line(surf, (245, 215, 120), (s * 0.18, s * 0.35), (s * 0.82, s * 0.35), 2)
        # Left pan
        pygame.draw.line(surf, (180, 190, 210), (s * 0.25, s * 0.35), (s * 0.25, s * 0.65), 1)
        pygame.draw.arc(surf, (245, 215, 120), (s * 0.12, s * 0.55, s * 0.26, s * 0.2), 3.14, 0, 2)
        # Right pan
        pygame.draw.line(surf, (180, 190, 210), (s * 0.75, s * 0.35), (s * 0.75, s * 0.65), 1)
        pygame.draw.arc(surf, (245, 215, 120), (s * 0.62, s * 0.55, s * 0.26, s * 0.2), 3.14, 0, 2)

    else:
        # Generic glowing orb
        pygame.draw.circle(surf, (200, 200, 220), (int(s * 0.5), int(s * 0.5)), int(s * 0.35))

    _ICON_CACHE[key] = surf
    return surf


def draw_icon_badge(surface: pygame.Surface, x: int, y: int, icon_kind: str, label: str,
                    font_small: pygame.font.Font, color: tuple[int, int, int] = (220, 220, 230),
                    dimmed: bool = False, icon_size: int = 16) -> int:
    """Render a crisp icon + label badge and return the total width consumed."""
    icon_surf = get_icon(icon_kind, size=icon_size)
    if dimmed:
        # Fade icon if missing / dimmed
        faded = icon_surf.copy()
        faded.fill((120, 120, 130, 140), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(faded, (x, y))
        txt_col = (110, 115, 130)
    else:
        surface.blit(icon_surf, (x, y))
        txt_col = color

    tsurf = font_small.render(label, True, txt_col)
    surface.blit(tsurf, (x + icon_size + 5, y + 1))
    return icon_size + 5 + tsurf.get_width()


def draw_progress_bar_button(surface: pygame.Surface, rect: tuple[int, int, int, int],
                             label: str, progress: float, font_small: pygame.font.Font,
                             theme: str = 'construction', icon_kind: str | None = None) -> None:
    """Render an interactive button that has morphed into a high-visibility live progress bar gauge."""
    bx, by, bw, bh = rect
    pct = min(1.0, max(0.0, float(progress)))

    if theme == 'science':
        track_bg = (14, 20, 32)
        fill_col = (45, 185, 245)
        border_col = (70, 210, 255)
        txt_col = (255, 255, 255)
    elif theme == 'diffusion':
        track_bg = (22, 16, 32)
        fill_col = (165, 105, 235)
        border_col = (195, 135, 255)
        txt_col = (255, 255, 255)
    elif theme == 'complete':
        track_bg = (18, 42, 28)
        fill_col = (45, 175, 95)
        border_col = (60, 205, 115)
        txt_col = (255, 255, 255)
    else:  # 'construction'
        track_bg = (24, 20, 14)
        fill_col = (235, 175, 45)
        border_col = (255, 200, 60)
        txt_col = (255, 255, 255)

    # Inset background track
    pygame.draw.rect(surface, track_bg, rect, border_radius=4)
    # Animated progress fill gauge
    fill_w = max(3, int((bw - 2) * pct))
    pygame.draw.rect(surface, fill_col, (bx + 1, by + 1, fill_w, bh - 2), border_radius=3)
    # Highlight border
    pygame.draw.rect(surface, border_col, rect, 1, border_radius=4)

    # Label with icon
    txt_surf = font_small.render(label, True, txt_col)
    if icon_kind:
        icon_surf = get_icon(icon_kind, size=min(14, bh - 4))
        icon_w = icon_surf.get_width()
        total_w = icon_w + 4 + txt_surf.get_width()
        start_x = bx + (bw - total_w) // 2
        # Soft shadow behind text
        shadow = font_small.render(label, True, (10, 10, 15))
        surface.blit(shadow, (start_x + icon_w + 5, by + (bh - txt_surf.get_height()) // 2 + 1))
        surface.blit(icon_surf, (start_x, by + (bh - icon_surf.get_height()) // 2))
        surface.blit(txt_surf, (start_x + icon_w + 4, by + (bh - txt_surf.get_height()) // 2))
    else:
        # Centered text with shadow
        shadow = font_small.render(label, True, (10, 10, 15))
        s_rect = shadow.get_rect(center=(bx + bw // 2 + 1, by + bh // 2 + 1))
        surface.blit(shadow, s_rect)
        t_rect = txt_surf.get_rect(center=(bx + bw // 2, by + bh // 2))
        surface.blit(txt_surf, t_rect)
