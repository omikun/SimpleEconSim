"""
worldview_vis_pyramid.py — Class Wealth Stratification Pyramid & Lorenz Curve Visualizer.

Implements:
1. 4-Tier Demographic Wealth & Population Stratification Pyramid:
   - Apex: Bourgeoisie, Capitalists & Feudal Gentry (Top 1-5% pop, owning dominant wealth).
   - Upper-Mid: Petty Bourgeoisie, Master Artisans & Affluent Tenants.
   - Base: Customary Serfs & Factory Wage Proletarians (Living at subsistence).
   - Sub-Base: Dispossessed, Destitute Vagabonds & Unemployed.
2. The Lorenz Curve & Gini Coefficient Distribution:
   - 45-degree line of perfect equality.
   - Live bowed cumulative wealth curve with shaded inequality region.
   - Live Gini coefficient calculation and societal assessment.
"""

import math
import pygame
from worldview_map import TEXT, DIM, RED, GREEN, ACCENT

CARD_BG = (22, 24, 36)
CARD_BORDER = (50, 55, 75)

COL_APEX = (245, 210, 80)       # Gold (Bourgeoisie & High Gentry)
COL_MID = (100, 180, 240)       # Blue (Artisans & Yeoman Tenants)
COL_BASE = (235, 90, 90)        # Crimson (Wage Workers & Serfs)
COL_SUBBASE = (140, 145, 160)   # Grey (Dispossessed & Destitute)


def _get_font(size):
    from worldview_ui import get_font
    return get_font(size)


def _collect_agents_and_classes(target):
    """Extract agents, class counts, and accumulated cash across tiles."""
    if target is None:
        return [], {}, 0.0

    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    if not tiles:
        tiles = [target]

    all_agents = []
    for t in tiles:
        all_agents.extend(getattr(t, 'agents', []))

    # Tiers classification
    # Tier 1 (Apex): Bourgeoisie, Industrialists, Landlords, Lords
    t1_agents = [a for a in all_agents if getattr(a, 'is_corporation', False) or getattr(a, 'is_lord', False) or getattr(a, 'role', '') in ('lord', 'landlord', 'industrialist')]
    # Tier 2 (Mid): Artisans, Merchants, Traders, Wealthy Tenants
    t2_agents = [a for a in all_agents if not getattr(a, 'is_corporation', False) and not getattr(a, 'is_lord', False) and (getattr(a, 'is_trader', False) or getattr(a, 'role', '') in ('petty_bourgeois', 'merchant', 'artisan'))]
    # Tier 3 (Base): Proletarians, Serfs, Common Tenants
    t3_agents = [a for a in all_agents if getattr(a, 'role', '') in ('serf', 'tenant', 'proletarian', 'laborer') or (getattr(a, 'employer', None) is not None and not getattr(a, 'is_corporation', False))]
    # Tier 4 (Sub-Base): Dispossessed, Unemployed, Vagabonds
    accounted_ids = set(id(a) for a in (t1_agents + t2_agents + t3_agents))
    t4_agents = [a for a in all_agents if id(a) not in accounted_ids and not getattr(a, 'is_government', False)]

    # If t3 is empty because roles aren't tagged, use heuristic
    if not t3_agents and len(all_agents) > len(t1_agents):
        remaining = [a for a in all_agents if a not in t1_agents and a not in t2_agents]
        t3_agents = remaining[:int(len(remaining)*0.85)]
        t4_agents = remaining[int(len(remaining)*0.85):]

    tiers = {
        'apex': t1_agents,
        'mid': t2_agents,
        'base': t3_agents,
        'subbase': t4_agents,
    }
    tot_wealth = max(1.0, sum(getattr(a, 'cash', 0.0) for a in all_agents))
    return all_agents, tiers, tot_wealth


def draw_class_wealth_pyramid(surface, rect, target, font_small, font_title=None):
    """Render 4-tier demographic and wealth stratification pyramid."""
    rx, ry, rw, rh = rect
    pygame.draw.rect(surface, CARD_BG, rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, rect, 1, border_radius=6)

    t_font = font_title if font_title else _get_font(13)
    target_name = getattr(target, 'name', 'Regional')
    surface.blit(t_font.render(f"Class Stratification Pyramid: {target_name}", True, ACCENT), (rx + 10, ry + 6))

    all_agents, tiers, tot_wealth = _collect_agents_and_classes(target)
    tot_pop = max(1, len(all_agents))

    tier_specs = [
        ('apex', 'Bourgeoisie & Gentry', COL_APEX),
        ('mid', 'Artisans & Free Yeomen', COL_MID),
        ('base', 'Wage Workers & Serfs', COL_BASE),
        ('subbase', 'Dispossessed Vagabonds', COL_SUBBASE),
    ]

    # Layout geometry
    pyr_cx = rx + rw // 2
    pyr_top_y = ry + 32
    tier_h = (rh - 45) // 4

    for i, (key, label, col) in enumerate(tier_specs):
        group = tiers.get(key, [])
        pop_cnt = len(group)
        pop_share = (pop_cnt / tot_pop) * 100.0
        w_sum = sum(getattr(a, 'cash', 0.0) for a in group)
        w_share = (w_sum / tot_wealth) * 100.0

        ty = pyr_top_y + i * tier_h
        # Pyramid width expands toward base
        top_w = 40 + i * (rw - 120) // 4
        bot_w = 40 + (i + 1) * (rw - 120) // 4

        # Draw trapezoid tier
        pts = [
            (pyr_cx - top_w // 2, ty),
            (pyr_cx + top_w // 2, ty),
            (pyr_cx + bot_w // 2, ty + tier_h - 4),
            (pyr_cx - bot_w // 2, ty + tier_h - 4),
        ]
        tier_surf = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        pygame.draw.polygon(tier_surf, (*col, 175), pts)
        pygame.draw.polygon(tier_surf, col, pts, 1)
        surface.blit(tier_surf, (0, 0))

        # Text inside tier: Class name + Pop % vs Wealth %
        txt_name = _get_font(11).render(label, True, (20, 20, 26) if col == COL_APEX else (255, 255, 255))
        surface.blit(txt_name, txt_name.get_rect(center=(pyr_cx, ty + tier_h // 2 - 4)))

        # Left label: Population %
        pop_lbl = _get_font(10).render(f"{pop_share:.1f}% Pop ({pop_cnt})", True, TEXT)
        surface.blit(pop_lbl, (rx + 8, ty + tier_h // 2 - 6))

        # Right label: Wealth %
        w_lbl = _get_font(10).render(f"${w_sum:,.0f} ({w_share:.1f}% $)", True, col)
        surface.blit(w_lbl, (rx + rw - w_lbl.get_width() - 8, ty + tier_h // 2 - 6))


def draw_lorenz_curve(surface, rect, target, font_small, font_title=None):
    """Render live Lorenz Curve & Gini calculation for accumulated wealth."""
    rx, ry, rw, rh = rect
    pygame.draw.rect(surface, CARD_BG, rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, rect, 1, border_radius=6)

    t_font = font_title if font_title else _get_font(13)
    surface.blit(t_font.render("Lorenz Wealth Curve & Gini Distribution", True, ACCENT), (rx + 10, ry + 6))

    all_agents, _, tot_wealth = _collect_agents_and_classes(target)
    if not all_agents or tot_wealth <= 0:
        surface.blit(font_small.render("No population wealth data", True, DIM), (rx + 10, ry + 30))
        return

    # Extract and sort agent wealth
    wealths = sorted(max(0.0, getattr(a, 'cash', 0.0)) for a in all_agents)
    n = len(wealths)

    # Compute Lorenz points
    cum_pop = [0.0]
    cum_wealth = [0.0]
    running_w = 0.0

    step = max(1, n // 25)
    for i in range(0, n, step):
        chunk_w = sum(wealths[:i+1])
        cum_pop.append((i + 1) / n)
        cum_wealth.append(chunk_w / tot_wealth)

    cum_pop.append(1.0)
    cum_wealth.append(1.0)

    # Calculate Gini Coefficient
    # Gini = (A) / (A + B) where A + B = 0.5
    # Area under Lorenz curve using trapezoidal rule:
    area_under_lorenz = 0.0
    for j in range(len(cum_pop) - 1):
        dx = cum_pop[j+1] - cum_pop[j]
        h_avg = (cum_wealth[j] + cum_wealth[j+1]) * 0.5
        area_under_lorenz += dx * h_avg

    gini = max(0.0, min(1.0, 1.0 - 2.0 * area_under_lorenz))

    # Graph Geometry
    plot_x = rx + 36
    plot_y = ry + 28
    plot_w = rw - 50
    plot_h = rh - 55

    # Equality 45-degree diagonal line
    pygame.draw.line(surface, (100, 110, 135), (plot_x, plot_y + plot_h), (plot_x + plot_w, plot_y), 1)

    # Lorenz Curve Coordinates
    lorenz_pts = []
    for px, py in zip(cum_pop, cum_wealth):
        lx = plot_x + int(px * plot_w)
        ly = plot_y + plot_h - int(py * plot_h)
        lorenz_pts.append((lx, ly))

    # Shaded Gini Area between equality line and Lorenz curve
    equality_pts = [(plot_x, plot_y + plot_h), (plot_x + plot_w, plot_y)]
    poly_pts = lorenz_pts + [(plot_x + plot_w, plot_y + plot_h)]
    if len(poly_pts) >= 3:
        gini_surf = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        pygame.draw.polygon(gini_surf, (220, 70, 70, 60), poly_pts)
        surface.blit(gini_surf, (0, 0))

    # Draw Lorenz curve line
    if len(lorenz_pts) >= 2:
        pygame.draw.lines(surface, (245, 185, 75), False, lorenz_pts, 2)

    # Axes
    pygame.draw.line(surface, (60, 65, 85), (plot_x, plot_y + plot_h), (plot_x + plot_w, plot_y + plot_h), 1)
    pygame.draw.line(surface, (60, 65, 85), (plot_x, plot_y), (plot_x, plot_y + plot_h), 1)

    # Gini Score Badge
    g_col = RED if gini > 0.45 else ((240, 180, 80) if gini > 0.30 else GREEN)
    rating = "Extremely Unequal" if gini > 0.50 else ("Unequal" if gini > 0.35 else "Equitable")
    gini_txt = f"Gini: {gini:.3f} [{rating}]"
    surface.blit(_get_font(11).render(gini_txt, True, g_col), (plot_x + 8, plot_y + 4))
    surface.blit(_get_font(10).render("Cumulative Population %  -->", True, DIM), (plot_x + plot_w // 2 - 50, plot_y + plot_h + 4))
