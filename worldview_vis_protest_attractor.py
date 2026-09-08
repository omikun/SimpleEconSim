"""
worldview_vis_protest_attractor.py — The Rebellion Attractor: 2D Phase-Space Dynamic Plot.

Visualizes the dynamic trajectory of territories in the 2D state space:
- X-axis: Shift Length (8h to 16h per workday)
- Y-axis: Proletarian Class Consciousness (0.0 to 1.0)
- Crimson Hazard Attractor Zone: Where shift hours > 10h and consciousness > 0.40,
  triggering wildcat strikes, factory walkouts, and Luddite machine sabotage.
- Mass Entertainment Damping Vector: Counteracting vector pacifying rebellion energy.
"""

import math
import pygame
from worldview_map import TEXT, DIM, RED, GREEN, ACCENT, NATION_COLORS

CARD_BG = (20, 22, 32)
CARD_BORDER = (48, 52, 70)
HAZARD_BG = (90, 25, 30, 140)
HAZARD_BORDER = (220, 60, 60)


def _get_font(size):
    from worldview_ui import get_font
    return get_font(size)


def draw_rebellion_attractor_phasespace(surface, rect, world, font, cell_font, section_font, mouse_pos=None):
    """
    Render 2D Phase-Space Dynamic Plot of Shift Hours vs Class Consciousness.
    Includes strike hazard zone, dynamic bubble plotting, trajectory tails,
    mass entertainment pacification vectors, and interactive hover tooltips.
    """
    rx, ry, rw, rh = rect
    pygame.draw.rect(surface, CARD_BG, rect, border_radius=6)
    pygame.draw.rect(surface, CARD_BORDER, rect, 1, border_radius=6)

    # 1. Title & Legend Header
    surface.blit(section_font.render("The Rebellion Attractor: 2D Phase-Space Dynamic Plot", True, ACCENT), (rx + 16, ry + 8))

    leg_x = rx + 16
    leg_y = ry + 32
    legends = [
        ("Calm (<2.0)", GREEN),
        ("Simmering (2.0-4.0)", (240, 180, 80)),
        ("Rebellion (>4.0)", RED),
        ("Strike & Sabotage Hazard", (220, 60, 60)),
    ]
    for lbl, col in legends:
        pygame.draw.rect(surface, col, (leg_x, leg_y + 2, 8, 8), border_radius=2)
        surface.blit(_get_font(10).render(lbl, True, TEXT), (leg_x + 12, leg_y))
        leg_x += 130

    # 2. Graph Geometry
    plot_x = rx + 55
    plot_y = ry + 54
    plot_w = rw - 80
    plot_h = rh - 90

    # Grid background lines
    for sh in [8, 10, 12, 14, 16]:
        gx = plot_x + int(((sh - 8) / 8.0) * plot_w)
        pygame.draw.line(surface, (36, 40, 56), (gx, plot_y), (gx, plot_y + plot_h), 1)
        surface.blit(_get_font(10).render(f"{sh}h", True, DIM), (gx - 8, plot_y + plot_h + 4))

    for cc in [0.0, 0.25, 0.50, 0.75, 1.0]:
        gy = plot_y + plot_h - int(cc * plot_h)
        pygame.draw.line(surface, (36, 40, 56), (plot_x, gy), (plot_x + plot_w, gy), 1)
        surface.blit(_get_font(10).render(f"{cc:.2f}", True, DIM), (plot_x - 32, gy - 6))

    # Axis Labels
    surface.blit(_get_font(11).render("Shift Length (Hours / Day)  -->", True, ACCENT), (plot_x + plot_w // 2 - 80, plot_y + plot_h + 18))
    # Y-axis vertical label
    surface.blit(_get_font(11).render("Class Consciousness  ^", True, ACCENT), (rx + 10, ry + 40))

    # 3. Shaded Strike & Sabotage Hazard Zone (X > 10h, Y > 0.40)
    hz_x = plot_x + int(((10.0 - 8.0) / 8.0) * plot_w)
    hz_w = plot_x + plot_w - hz_x
    hz_y = plot_y
    hz_h = int((1.0 - 0.40) * plot_h)

    hz_surf = pygame.Surface((hz_w, hz_h), pygame.SRCALPHA)
    hz_surf.fill(HAZARD_BG)
    surface.blit(hz_surf, (hz_x, hz_y))
    pygame.draw.rect(surface, HAZARD_BORDER, (hz_x, hz_y, hz_w, hz_h), 1)

    # Diagonal hatching inside hazard zone
    for diag_x in range(hz_x - hz_h, hz_x + hz_w, 24):
        p1 = (max(hz_x, diag_x), hz_y + max(0, hz_x - diag_x))
        p2 = (min(hz_x + hz_w, diag_x + hz_h), hz_y + min(hz_h, hz_x + hz_w - diag_x))
        if p1[0] < hz_x + hz_w and p2[1] <= hz_y + hz_h:
            pygame.draw.line(surface, (180, 50, 60, 60), p1, p2, 1)

    hz_label = _get_font(11).render("[ WILDCAT STRIKE & LUDDITE SABOTAGE ZONE ]", True, (255, 140, 140))
    surface.blit(hz_label, (hz_x + 12, hz_y + 10))

    # 4. Collect territory data points
    scope = world.get('compare_protest_scope', 'country')
    nations = world.get('nations', [])
    entities = []

    if scope == 'country':
        for n in nations:
            tiles = n.tiles
            if not tiles:
                continue
            pop = sum(len(getattr(t, 'agents', [])) for t in tiles)
            shifts = [t.avg_shift_hours_log[-1] for t in tiles if getattr(t, 'avg_shift_hours_log', None)]
            avg_s = sum(shifts) / len(shifts) if shifts else 12.0
            conscs = [t.class_consciousness_log[-1] for t in tiles if getattr(t, 'class_consciousness_log', None)]
            avg_c = sum(conscs) / len(conscs) if conscs else 0.25
            protest_vals = [t.protest_energy_log[-1] for t in tiles if getattr(t, 'protest_energy_log', None)]
            avg_p = sum(protest_vals) / len(protest_vals) if protest_vals else 1.0
            strikers = sum(getattr(t, 'strikers_log', [0])[-1] for t in tiles if getattr(t, 'strikers_log', None))
            broken = sum(getattr(t, 'broken_machinery_log', [0])[-1] for t in tiles if getattr(t, 'broken_machinery_log', None))
            ent = sum(getattr(t, 'entertainment_level', 0.0) for t in tiles) / len(tiles)

            entities.append({
                'name': n.name,
                'pop': pop,
                'shift': avg_s,
                'consc': avg_c,
                'protest': avg_p,
                'strikers': strikers,
                'broken': broken,
                'ent': ent,
                'color': NATION_COLORS.get(n.name, ACCENT),
            })
    elif scope == 'province':
        for n in nations:
            for p in n.provinces:
                tiles = p.tiles
                if not tiles:
                    continue
                pop = sum(len(getattr(t, 'agents', [])) for t in tiles)
                shifts = [t.avg_shift_hours_log[-1] for t in tiles if getattr(t, 'avg_shift_hours_log', None)]
                avg_s = sum(shifts) / len(shifts) if shifts else 12.0
                conscs = [t.class_consciousness_log[-1] for t in tiles if getattr(t, 'class_consciousness_log', None)]
                avg_c = sum(conscs) / len(conscs) if conscs else 0.25
                protest_vals = [t.protest_energy_log[-1] for t in tiles if getattr(t, 'protest_energy_log', None)]
                avg_p = sum(protest_vals) / len(protest_vals) if protest_vals else 1.0
                strikers = sum(getattr(t, 'strikers_log', [0])[-1] for t in tiles if getattr(t, 'strikers_log', None))
                broken = sum(getattr(t, 'broken_machinery_log', [0])[-1] for t in tiles if getattr(t, 'broken_machinery_log', None))
                ent = sum(getattr(t, 'entertainment_level', 0.0) for t in tiles) / len(tiles)

                entities.append({
                    'name': f"{p.name} ({n.name[:3]})",
                    'pop': pop,
                    'shift': avg_s,
                    'consc': avg_c,
                    'protest': avg_p,
                    'strikers': strikers,
                    'broken': broken,
                    'ent': ent,
                    'color': NATION_COLORS.get(n.name, ACCENT),
                })
    else:  # 'city' / individual tiles
        for n in nations:
            for t in n.tiles:
                pop = max(1, len(getattr(t, 'agents', [])))
                s_log = getattr(t, 'avg_shift_hours_log', [])
                sh = s_log[-1] if s_log else 12.0
                c_log = getattr(t, 'class_consciousness_log', [])
                cc = c_log[-1] if c_log else 0.25
                p_log = getattr(t, 'protest_energy_log', [])
                pe = p_log[-1] if p_log else 1.0
                strikers = getattr(t, 'strikers_log', [0])[-1] if getattr(t, 'strikers_log', None) else 0
                broken = getattr(t, 'broken_machinery_log', [0])[-1] if getattr(t, 'broken_machinery_log', None) else 0
                ent = getattr(t, 'entertainment_level', 0.0)

                entities.append({
                    'name': getattr(t, 'display_name', t.name),
                    'pop': pop,
                    'shift': sh,
                    'consc': cc,
                    'protest': pe,
                    'strikers': strikers,
                    'broken': broken,
                    'ent': ent,
                    'color': NATION_COLORS.get(n.name, ACCENT),
                })

    # 5. Plot Bubbles & Vectors
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    hovered_ent = None

    for ent in entities:
        # Convert (shift, consc) to pixel (bx, by)
        sh_clamped = min(16.0, max(8.0, ent['shift']))
        cc_clamped = min(1.0, max(0.0, ent['consc']))

        bx = plot_x + int(((sh_clamped - 8.0) / 8.0) * plot_w)
        by = plot_y + plot_h - int(cc_clamped * plot_h)

        # Bubble radius proportional to population
        r = min(22, max(6, int(math.sqrt(ent['pop']) * 1.5)))

        # Bubble color based on protest energy
        p_val = ent['protest']
        b_col = RED if p_val > 4.0 else ((240, 180, 80) if p_val > 2.0 else GREEN)

        # Check hover
        dist = math.hypot(mx - bx, my - by)
        is_hov = dist <= r + 3

        # Draw Mass Entertainment Damping Vector (if spectacle level > 0)
        if ent['ent'] > 0.05:
            d_len = int(ent['ent'] * 35.0)
            # Damping pulls downwards (reducing consciousness)
            pygame.draw.line(surface, (70, 195, 235), (bx, by), (bx, by + d_len), 2)
            pygame.draw.polygon(surface, (70, 195, 235), [(bx - 3, by + d_len - 4), (bx + 3, by + d_len - 4), (bx, by + d_len)])

        # Draw bubble
        bubble_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(bubble_surf, (*b_col, 180), (r + 2, r + 2), r)
        pygame.draw.circle(bubble_surf, (255, 255, 255) if is_hov else b_col, (r + 2, r + 2), r, 2 if is_hov else 1)
        surface.blit(bubble_surf, (bx - r - 2, by - r - 2))

        # Short label
        lbl_surf = _get_font(10).render(ent['name'][:9], True, TEXT)
        surface.blit(lbl_surf, (bx - lbl_surf.get_width() // 2, by + r + 2))

        if is_hov:
            hovered_ent = (ent, bx, by)

    # 6. Interactive Tooltip
    if hovered_ent:
        ent, bx, by = hovered_ent
        tip_w, tip_h = 240, 84
        tx = min(rx + rw - tip_w - 10, max(rx + 10, bx + 15))
        ty = min(ry + rh - tip_h - 10, max(ry + 10, by - tip_h - 10))

        tip_bg = pygame.Surface((tip_w, tip_h), pygame.SRCALPHA)
        tip_bg.fill((16, 18, 26, 245))
        surface.blit(tip_bg, (tx, ty))
        pygame.draw.rect(surface, ACCENT, (tx, ty, tip_w, tip_h), 1, border_radius=5)

        surface.blit(_get_font(12).render(ent['name'], True, ACCENT), (tx + 8, ty + 6))
        surface.blit(_get_font(11).render(f"Pop: {ent['pop']:,}  •  Protest: {ent['protest']:.2f}/10", True, TEXT), (tx + 8, ty + 24))
        surface.blit(_get_font(11).render(f"Shift Length: {ent['shift']:.1f}h  •  Consc: {ent['consc']*100:.0f}%", True, (245, 180, 80)), (tx + 8, ty + 42))

        st_txt = f"Strikers: {ent['strikers']} | Sabotaged: {ent['broken']}"
        st_col = RED if (ent['strikers'] > 0 or ent['broken'] > 0) else GREEN
        surface.blit(_get_font(11).render(st_txt, True, st_col), (tx + 8, ty + 60))
