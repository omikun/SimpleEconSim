"""
worldview_vis_radar.py — 4D Alienation Spider Chart & Electoral Tug-of-War Barometer.

Implements:
1. 4-Dimensional Alienation Spider / Radar Chart (Product, Process, Nature, Species-Being).
   - Polar radar plot comparing Proletarians, Serfs, and Capitalists.
2. The Electoral Struggle & Capitalist Backlash Tug-of-War Barometer:
   - Popular Uprising Pressure vs Capitalist Opposition Campaign War Chest.
   - Dynamic equilibrium needle and incumbent re-election odds.
"""

import math
import pygame
from worldview_map import TEXT, DIM, RED, GREEN, ACCENT

CARD_BG = (22, 24, 36)
CARD_BORDER = (50, 55, 75)

COL_PROLE = (235, 75, 75)       # Crimson (Proletariat)
COL_SERF = (100, 210, 140)      # Green (Customary Serf)
COL_BOURG = (245, 210, 80)      # Gold (Bourgeoisie / Ruling Elite)

COL_POPULAR = (235, 90, 90)     # Popular pressure (red/coral)
COL_WARCHEST = (75, 155, 235)   # Capitalist war chest (blue/navy)


def _get_font(size):
    from worldview_ui import get_font
    return get_font(size)


# =============================================================================
# 1. 4-DIMENSIONAL ALIENATION SPIDER / RADAR CHART
# =============================================================================

def compute_alienation_4d(target):
    """
    Compute normalized 4D alienation components (0.0 to 1.0) for a tile or nation:
    - product: Separation from the output / surplus extraction
    - process: Mechanical assembly discipline, shift length, speedup
    - nature: Severed customary land relation, enclosure, lost foraging
    - species: Degradation of creative human faculties, despair, vices
    """
    if target is None:
        return {'product': 0.5, 'process': 0.5, 'nature': 0.5, 'species': 0.5}

    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    if not tiles:
        tiles = [target]

    tot_pop = 0
    p_prod, p_proc, p_nat, p_spec = 0.0, 0.0, 0.0, 0.0

    for t in tiles:
        pop = max(1, len(getattr(t, 'agents', [])))
        tot_pop += pop

        # 1. Product alienation: surplus extraction rate s/v
        sv_log = getattr(t, 'rate_of_exploitation_log', [])
        sv_rate = sv_log[-1] if sv_log else 0.5
        prod_val = min(1.0, max(0.05, sv_rate / 1.5))

        # 2. Process alienation: shift hours above 8h + workplace accidents
        shifts = getattr(t, 'avg_shift_hours_log', [])
        avg_s = shifts[-1] if shifts else 12.0
        acc = getattr(t, 'workplace_accidents_log', [0])[-1] if getattr(t, 'workplace_accidents_log', None) else 0
        proc_val = min(1.0, max(0.05, (avg_s - 8.0) / 8.0 + (acc * 0.1)))

        # 3. Nature alienation: lack of commons access / enclosure fraction
        tenure = getattr(t, 'tenure', None)
        if tenure:
            nat_val = min(1.0, max(0.05, 1.0 - tenure.commons_access))
        else:
            nat_val = 0.4

        # 4. Species-Being alienation: despair, vice spending, lack of agency
        vice_log = getattr(t, 'vice_spending_log', [])
        vice_val = vice_log[-1] if vice_log else 0.0
        alien_log = getattr(t, 'avg_alienation_log', [])
        base_alien = alien_log[-1] if alien_log else 0.35
        spec_val = min(1.0, max(0.05, base_alien * 0.7 + min(0.3, vice_val / 50.0)))

        p_prod += prod_val * pop
        p_proc += proc_val * pop
        p_nat += nat_val * pop
        p_spec += spec_val * pop

    if tot_pop > 0:
        return {
            'product': p_prod / tot_pop,
            'process': p_proc / tot_pop,
            'nature': p_nat / tot_pop,
            'species': p_spec / tot_pop,
        }
    return {'product': 0.5, 'process': 0.5, 'nature': 0.5, 'species': 0.5}


def draw_alienation_radar(surface, rect, target, font_small, font_title=None):
    """
    Render 4D Alienation Spider Chart on a target Surface inside `rect`.
    Displays 4 axes (Product, Process, Nature, Species) with concentric rings
    and multi-class polygon profiles (Proletarians, Serfs, Ruling Elite).
    """
    rx, ry, rw, rh = rect
    pygame.draw.rect(surface, CARD_BG, rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, rect, 1, border_radius=6)

    # Title
    t_font = font_title if font_title else _get_font(13)
    target_name = getattr(target, 'name', 'Regional')
    surface.blit(t_font.render(f"4D Alienation Spectrum: {target_name}", True, ACCENT), (rx + 10, ry + 6))

    # Center and Radius
    cx = rx + rw // 2
    cy = ry + (rh // 2) + 10
    max_r = min(rw // 2 - 45, rh // 2 - 32)
    if max_r < 30:
        max_r = 30

    # 4 Axes: North (Product), East (Process), South (Nature), West (Species)
    axes = [
        ("Product (Surplus)", 0, -1),      # 0: Up / North
        ("Process (Shifts)", 1, 0),       # 1: Right / East
        ("Nature (Enclosure)", 0, 1),     # 2: Down / South
        ("Species (Agency)", -1, 0),      # 3: Left / West
    ]

    # Draw concentric grid rings (25%, 50%, 75%, 100%)
    for pct in [0.25, 0.50, 0.75, 1.0]:
        ring_r = int(max_r * pct)
        ring_pts = [
            (cx, cy - ring_r),
            (cx + ring_r, cy),
            (cx, cy + ring_r),
            (cx - ring_r, cy),
        ]
        pygame.draw.polygon(surface, (42, 46, 62), ring_pts, 1)

    # Draw axis spoke lines and text labels
    for lbl, dx, dy in axes:
        pygame.draw.line(surface, (60, 65, 85), (cx, cy), (cx + int(dx * max_r), cy + int(dy * max_r)), 1)
        # Label placement
        lx = cx + int(dx * (max_r + 14))
        ly = cy + int(dy * (max_r + 14))
        lsurf = _get_font(10).render(lbl, True, (180, 190, 210))
        surface.blit(lsurf, lsurf.get_rect(center=(lx, ly)))

    # Compute actual live 4D metrics
    actual_4d = compute_alienation_4d(target)

    # Benchmark profiles for comparison:
    # 1. Ruling Bourgeoisie / Lords: Very low on all (own product, dictate process, control nature)
    bourg_4d = {'product': 0.12, 'process': 0.15, 'nature': 0.10, 'species': 0.18}
    # 2. Feudal Serfs: Low on nature (forage commons), moderate on product (tribute), low on mechanical process
    serf_4d = {'product': 0.38, 'process': 0.22, 'nature': 0.20, 'species': 0.32}

    def _get_poly_points(data_dict):
        return [
            (cx, cy - int(max_r * data_dict['product'])),
            (cx + int(max_r * data_dict['process']), cy),
            (cx, cy + int(max_r * data_dict['nature'])),
            (cx - int(max_r * data_dict['species']), cy),
        ]

    # Draw translucent filled polygons
    poly_surf = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)

    # 1. Bourgeoisie profile (Gold)
    b_pts = _get_poly_points(bourg_4d)
    pygame.draw.polygon(poly_surf, (*COL_BOURG, 50), b_pts)
    pygame.draw.polygon(poly_surf, COL_BOURG, b_pts, 1)

    # 2. Customary Serf profile (Green)
    s_pts = _get_poly_points(serf_4d)
    pygame.draw.polygon(poly_surf, (*COL_SERF, 60), s_pts)
    pygame.draw.polygon(poly_surf, COL_SERF, s_pts, 1)

    # 3. Active Proletariat profile (Crimson)
    p_pts = _get_poly_points(actual_4d)
    pygame.draw.polygon(poly_surf, (*COL_PROLE, 110), p_pts)
    pygame.draw.polygon(poly_surf, (255, 120, 120), p_pts, 2)
    for px, py in p_pts:
        pygame.draw.circle(poly_surf, (255, 230, 230), (px, py), 3)

    surface.blit(poly_surf, (0, 0))

    # Legend at bottom
    leg_y = ry + rh - 18
    leg_x = rx + 12
    legends = [
        ("Proletariat (Live)", COL_PROLE),
        ("Customary Serf", COL_SERF),
        ("Bourgeoisie", COL_BOURG),
    ]
    for lbl, col in legends:
        pygame.draw.rect(surface, col, (leg_x, leg_y + 2, 8, 8), border_radius=2)
        surface.blit(_get_font(10).render(lbl, True, TEXT), (leg_x + 12, leg_y))
        leg_x += 105


# =============================================================================
# 2. THE ELECTORAL STRUGGLE & CAPITALIST BACKLASH TUG-OF-WAR BAROMETER
# =============================================================================

def draw_electoral_barometer(surface, rect, nation, font_small, font_title=None):
    """
    Render Visualization 5: Popular Uprising Pressure vs Capitalist War Chest.
    Horizontal dynamic tug-of-war meter balancing:
    - Popular pro-labor reform pressure (demanding 10h workday, safety, UBI).
    - Capitalist opposition war chest (campaign contributions backing challenger party).
    """
    rx, ry, rw, rh = rect
    pygame.draw.rect(surface, CARD_BG, rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, rect, 1, border_radius=6)

    t_font = font_title if font_title else _get_font(13)
    surface.blit(t_font.render("Electoral Struggle: Popular Pressure vs Capitalist PAC", True, ACCENT), (rx + 10, ry + 6))

    if nation is None:
        surface.blit(font_small.render("No sovereign nation selected", True, DIM), (rx + 10, ry + 28))
        return

    # Calculate Popular Pressure (0 to 100)
    tiles = getattr(nation, 'tiles', [])
    tot_pop = max(1, sum(len(getattr(t, 'agents', [])) for t in tiles))

    # Popular drivers: shift length, protest energy, strikes, food deprivation
    protest_e = sum(getattr(t, 'protest_energy_log', [0.0])[-1] for t in tiles if getattr(t, 'protest_energy_log', None))
    shifts = [t.avg_shift_hours_log[-1] for t in tiles if getattr(t, 'avg_shift_hours_log', None)]
    avg_s = sum(shifts) / len(shifts) if shifts else 12.0
    strikers = sum(getattr(t, 'strikers_log', [0])[-1] for t in tiles if getattr(t, 'strikers_log', None))

    pop_score = min(100.0, max(10.0, (protest_e * 4.0) + ((avg_s - 8.0) * 8.0) + (strikers * 3.0)))

    # Calculate Capitalist Opposition War Chest (0 to 100)
    # If Ten-Hour Act or Safety Mandate passed, capitalists contribute up to 30% of their profits
    has_ten = getattr(nation, 'ten_hour_act', False) or getattr(nation, 'max_workday_hours', 16.0) <= 10.0
    has_safe = getattr(nation, 'factory_safety_act', False)

    corp_cash = sum(a.cash for t in tiles for a in getattr(t, 'agents', []) if getattr(a, 'is_corporation', False) or getattr(a, 'is_lord', False))
    backlash_multiplier = (1.5 if has_ten else 0.5) + (1.2 if has_safe else 0.3)
    pac_score = min(100.0, max(10.0, (corp_cash / max(1.0, tot_pop * 15.0)) * 50.0 * backlash_multiplier))

    # Incumbent re-election probability
    total_pull = pop_score + pac_score
    incumbent_odds = (pop_score / max(1.0, total_pull)) * 100.0

    # Barometer geometry
    bar_x = rx + 14
    bar_y = ry + 28
    bar_w = rw - 28
    bar_h = 16

    # Left = Popular Pressure (Red), Right = Capitalist War Chest (Blue)
    pop_w = int((pop_score / total_pull) * bar_w)
    pac_w = bar_w - pop_w

    pygame.draw.rect(surface, COL_POPULAR, (bar_x, bar_y, pop_w, bar_h), border_top_left_radius=4, border_bottom_left_radius=4)
    pygame.draw.rect(surface, COL_WARCHEST, (bar_x + pop_w, bar_y, pac_w, bar_h), border_top_right_radius=4, border_bottom_right_radius=4)

    # Tug-of-war center fulcrum needle
    needle_x = bar_x + pop_w
    pygame.draw.line(surface, (255, 255, 255), (needle_x, bar_y - 3), (needle_x, bar_y + bar_h + 3), 2)
    pygame.draw.circle(surface, (255, 255, 255), (needle_x, bar_y + bar_h // 2), 4)

    # Sub-text labels
    surface.blit(_get_font(11).render(f"Popular Pressure: {pop_score:.0f} pts", True, (255, 160, 160)), (bar_x, bar_y + bar_h + 4))
    pac_txt = _get_font(11).render(f"Capitalist PAC Fund: ${corp_cash:,.0f}", True, (160, 200, 255))
    surface.blit(pac_txt, (bar_x + bar_w - pac_txt.get_width(), bar_y + bar_h + 4))

    # Equilibrium Analysis Badge
    status_y = bar_y + bar_h + 20
    if incumbent_odds >= 55:
        odds_txt = f"Incumbent Mandate: {incumbent_odds:.0f}% Odds (Labor Uprising dominates Capitalist Backlash)"
        odds_col = GREEN
    elif incumbent_odds <= 45:
        odds_txt = f"Capitalist Backlash Critical: {100-incumbent_odds:.0f}% Challenger Odds (Capitalists backing opposition party)"
        odds_col = RED
    else:
        odds_txt = f"Electoral Deadlock: 50/50 Toss-Up (Popular strike pressure balanced by capitalist lobby)"
        odds_col = (245, 210, 90)

    surface.blit(_get_font(11).render(odds_txt, True, odds_col), (bar_x, status_y))
