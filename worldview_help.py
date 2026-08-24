"""
worldview_help.py — Interactive Help & Seed Registry Modal for REGNUM.

Displays:
- Active runtime seeds (Master Seed, Terrain Seed, Nation Seed)
- Sovereign nation registry with capitals and currencies
- Comprehensive keyboard shortcuts and navigation controls
"""

import pygame

HELP_PANEL_RECT = (160, 80, 1080, 740)
CLOSE_BTN_RECT = (1200, 95, 26, 26)


def draw_help_modal(surface, world, font, font_small):
    """Draw full-screen modal showing simulation seeds, nation registry, and hotkeys."""
    if not world.get('help_open', False):
        return

    # Dim background overlay
    overlay = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
    overlay.fill((8, 10, 16, 190))
    surface.blit(overlay, (0, 0))

    bx, by, bw, bh = HELP_PANEL_RECT

    # Main card container
    card = pygame.Surface((bw, bh), pygame.SRCALPHA)
    card.fill((16, 20, 30, 248))
    surface.blit(card, (bx, by))
    pygame.draw.rect(surface, (70, 130, 200), (bx, by, bw, bh), 2, border_radius=8)

    # Title Bar
    title_surf = font.render("REGNUM WORLDVIEW — SEEDS & SYSTEM GUIDE", True, (245, 210, 100))
    surface.blit(title_surf, (bx + 24, by + 20))

    # Close Button (X)
    cx, cy, cw, ch = CLOSE_BTN_RECT
    pygame.draw.rect(surface, (45, 55, 75), (cx, cy, cw, ch), border_radius=4)
    pygame.draw.rect(surface, (140, 160, 190), (cx, cy, cw, ch), 1, border_radius=4)
    x_tag = font.render("X", True, (240, 240, 240))
    surface.blit(x_tag, x_tag.get_rect(center=(cx + cw // 2, cy + ch // 2)))

    cur_y = by + 65

    # 1. SECTION: ACTIVE SEEDS & WORLD PARAMETERS
    pygame.draw.rect(surface, (28, 38, 56), (bx + 20, cur_y, bw - 40, 90), border_radius=6)
    pygame.draw.rect(surface, (50, 75, 110), (bx + 20, cur_y, bw - 40, 90), 1, border_radius=6)
    
    sec1_title = font_small.render("ACTIVE PROCEDURAL WORLD SEEDS", True, (130, 200, 255))
    surface.blit(sec1_title, (bx + 34, cur_y + 12))

    seed_val = world.get('seed', 'Default')
    t_seed = world.get('terrain_seed', 'Auto')
    n_seed = world.get('nation_seed', 'Auto')

    s_text1 = font_small.render(f"- Master Seed: {seed_val}    (Pass with --seed <val>)", True, (230, 235, 245))
    s_text2 = font_small.render(f"- Terrain / Landmass Seed: {t_seed}    (--terrain-seed <val>)", True, (200, 230, 180))
    s_text3 = font_small.render(f"- Nations & Placement Seed: {n_seed}    (--nation-seed <val>)", True, (255, 205, 150))
    surface.blit(s_text1, (bx + 34, cur_y + 36))
    surface.blit(s_text2, (bx + 34, cur_y + 56))
    surface.blit(s_text3, (bx + 520, cur_y + 56))

    cur_y += 105

    # 2. SECTION: SOVEREIGN NATIONS & CAPITALS REGISTRY
    nations = world.get('nations', [])
    sec2_h = 160
    pygame.draw.rect(surface, (28, 38, 56), (bx + 20, cur_y, bw - 40, sec2_h), border_radius=6)
    pygame.draw.rect(surface, (50, 75, 110), (bx + 20, cur_y, bw - 40, sec2_h), 1, border_radius=6)

    sec2_title = font_small.render("SOVEREIGN NATIONS & CAPITAL REGISTRY", True, (130, 200, 255))
    surface.blit(sec2_title, (bx + 34, cur_y + 12))

    ny = cur_y + 38
    for n in nations:
        cap_tile = getattr(n, 'capital', n.tiles[0] if n.tiles else None)
        cap_city = getattr(cap_tile, 'display_name', cap_tile.name) if cap_tile else 'Unknown'
        provs = getattr(n, 'provinces', [])
        prov_summary = ", ".join(f"[{getattr(p, 'display_name', p.name)}]" for p in provs)
        
        n_line = font_small.render(
            f"* {n.name} ({n.currency}) — Regime: {n.regime_type.title()} | Capital: {cap_city} | Tiles: {len(n.tiles)}",
            True, (245, 220, 120)
        )
        p_line = font_small.render(f"   Provinces ({len(provs)}): {prov_summary}", True, (180, 190, 210))
        surface.blit(n_line, (bx + 34, ny))
        surface.blit(p_line, (bx + 34, ny + 20))
        ny += 42

    cur_y += sec2_h + 15

    # 3. SECTION: CONTROLS & SHORTCUTS GUIDE
    ctrl_h = 320
    pygame.draw.rect(surface, (28, 38, 56), (bx + 20, cur_y, bw - 40, ctrl_h), border_radius=6)
    pygame.draw.rect(surface, (50, 75, 110), (bx + 20, cur_y, bw - 40, ctrl_h), 1, border_radius=6)

    sec3_title = font_small.render("KEYBOARD SHORTCUTS & INTERACTIVE CONTROLS", True, (130, 200, 255))
    surface.blit(sec3_title, (bx + 34, cur_y + 12))

    shortcuts_left = [
        ("Space", "Pause / Resume continuous auto-stepping"),
        ("N / Step", "Advance exactly 1 simulation turn"),
        ("1..6 / F1..F6", "Switch Map Layers (Overview, Physical, Pop, Econ, Prod, Military)"),
        ("Tab", "Open / Close Sovereign Actions command tabs"),
        ("1..4 (in Actions)", "Switch between Fiscal, Sovereign, Military, Diplomacy tabs"),
        ("H / ? / Help", "Toggle this Help & Seed Registry guide"),
        ("Esc", "Close active modals, tabs, and clear selection"),
    ]

    shortcuts_right = [
        ("WASD / Arrows", "Pan map camera across the continental landmass"),
        ("Right-Click Drag", "Smooth continuous viewport drag"),
        ("Scroll / +/-", "Zoom map camera in and out"),
        ("R", "Reset camera zoom and center on continent"),
        ("Left-Click Hex", "Select tile and inspect regional economy & agents"),
        ("Left Sidebar Dock", "Click layer buttons (Overview, Height, Pop, etc.) to toggle"),
        ("Diplomacy Clicks", "Sign trade pacts, declare war, or negotiate peace instantly"),
    ]

    cy_k = cur_y + 38
    for key, desc in shortcuts_left:
        k_surf = font_small.render(f"[{key}]", True, (240, 200, 100))
        d_surf = font_small.render(desc, True, (210, 215, 225))
        surface.blit(k_surf, (bx + 34, cy_k))
        surface.blit(d_surf, (bx + 160, cy_k))
        cy_k += 26

    cy_k = cur_y + 38
    for key, desc in shortcuts_right:
        k_surf = font_small.render(f"[{key}]", True, (240, 200, 100))
        d_surf = font_small.render(desc, True, (210, 215, 225))
        surface.blit(k_surf, (bx + 540, cy_k))
        surface.blit(d_surf, (bx + 680, cy_k))
        cy_k += 26

    # Bottom hint
    hint_surf = font_small.render("Press [H], [Esc], or click [X] to close this help guide.", True, (140, 160, 185))
    surface.blit(hint_surf, hint_surf.get_rect(center=(bx + bw // 2, by + bh - 20)))


def help_modal_hit(pos, world):
    """Check if click closes the help modal or hits inside."""
    if not world.get('help_open', False):
        return False

    px, py = pos
    cx, cy, cw, ch = CLOSE_BTN_RECT
    if cx <= px <= cx + cw and cy <= py <= cy + ch:
        world['help_open'] = False
        return True

    bx, by, bw, bh = HELP_PANEL_RECT
    if not (bx <= px <= bx + bw and by <= py <= by + bh):
        # Click outside modal closes it
        world['help_open'] = False
        return True

    return True
