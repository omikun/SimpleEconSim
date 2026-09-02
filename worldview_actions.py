"""
worldview_actions.py — Interactive Player Command, Diplomacy, Military, and Construction UI.

Provides an interactive Sovereign Control Suite for REGNUM:
- Tab 1: Global Diplomacy & Treaties (Bilateral relations, Trade Pacts, NAPs, Defensive Alliances, Betrayals, Wars)
- Tab 2: Military Operations & Defense (Garrison recruitment, Troop movements, Combat orders, Deserter stats)
- Tab 3: Strategic Intents & Physical Construction (Commissioning Farms, Mills, Workshops, Granaries)
- Sovereign Switcher: Lets player instantly take command of ANY nation in the honeycomb world.
- AI Sovereign Advisory: Shows AI terrain scores, resource bottlenecks, vulnerability ratings, and AI autonomy toggle.
"""

import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H
from worldview_map import (
    NATION_COLORS, TEXT, DIM, RED, GREEN, ACCENT, PROVINCE_COLORS
)
from diplomacy import get_diplomacy, TreatyType
from army import recruit_unit
from ai_nation import NationPolicyAI
from buildings import BUILDING_RECIPES
from intents import (RecruitArmyIntent, MoveArmyIntent, ProposeTreatyIntent,
                     BreakTreatyIntent, DeclareWarIntent, BuildIntent)

# Colors
BG_MODAL = (18, 18, 26, 248)
BORDER_MODAL = (70, 70, 95)
CARD_BG = (26, 26, 36)
CARD_HOVER = (38, 38, 52)
BTN_BG = (42, 42, 58)
BTN_HOVER = (60, 60, 85)
BTN_BORDER = (90, 90, 120)
TAB_ACTIVE_BG = (52, 52, 75)
TAB_INACTIVE_BG = (28, 28, 38)

# Top-Right Command Buttons: (x, y, w, h)
# Positioned directly above the right-hand sidebar panel (x = 1060..1400, y = 0..52)
HELP_BTN = (1066, 5, 156, 20)
COMPARE_BTN = (1228, 5, 160, 20)
DIPLOMACY_BTN = (1066, 27, 156, 20)
MILITARY_BTN = (1228, 27, 160, 20)


def draw_top_bar_action_buttons(surface, world, font_small, mouse_pos=None):
    """Draw top-right shortcuts above sidebar: Help (?), Compare (C), Diplomacy (D), and Military (M)."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    
    # 0. Help Button (?)
    is_help_open = world.get('help_open', False)
    help_hover = HELP_BTN[0] <= mx <= HELP_BTN[0] + HELP_BTN[2] and HELP_BTN[1] <= my <= HELP_BTN[1] + HELP_BTN[3]
    help_bg = (75, 75, 100) if is_help_open else ((60, 60, 80) if help_hover else (40, 40, 52))
    pygame.draw.rect(surface, help_bg, HELP_BTN, border_radius=4)
    pygame.draw.rect(surface, ACCENT if (help_hover or is_help_open) else (80, 80, 100), HELP_BTN, 1, border_radius=4)
    help_txt = font_small.render("[?] Help (H)", True, (255, 255, 255) if (help_hover or is_help_open) else TEXT)
    surface.blit(help_txt, help_txt.get_rect(center=(HELP_BTN[0] + HELP_BTN[2] // 2, HELP_BTN[1] + HELP_BTN[3] // 2)))

    # 1. Compare Nations Button (C)
    is_comp_open = world.get('compare_open', False)
    comp_hover = COMPARE_BTN[0] <= mx <= COMPARE_BTN[0] + COMPARE_BTN[2] and COMPARE_BTN[1] <= my <= COMPARE_BTN[1] + COMPARE_BTN[3]
    comp_bg = (75, 75, 100) if is_comp_open else ((60, 60, 80) if comp_hover else (40, 40, 52))
    pygame.draw.rect(surface, comp_bg, COMPARE_BTN, border_radius=4)
    pygame.draw.rect(surface, ACCENT if (comp_hover or is_comp_open) else (80, 80, 100), COMPARE_BTN, 1, border_radius=4)
    comp_txt = font_small.render("Compare (C)", True, (255, 255, 255) if (comp_hover or is_comp_open) else TEXT)
    surface.blit(comp_txt, comp_txt.get_rect(center=(COMPARE_BTN[0] + COMPARE_BTN[2] // 2, COMPARE_BTN[1] + COMPARE_BTN[3] // 2)))

    # 2. Diplomacy Button (D)
    is_dip_open = world.get('actions_open') and world.get('actions_tab') == 1
    dip_hover = DIPLOMACY_BTN[0] <= mx <= DIPLOMACY_BTN[0] + DIPLOMACY_BTN[2] and DIPLOMACY_BTN[1] <= my <= DIPLOMACY_BTN[1] + DIPLOMACY_BTN[3]
    dip_bg = (75, 75, 100) if is_dip_open else ((60, 60, 80) if dip_hover else (40, 40, 52))
    pygame.draw.rect(surface, dip_bg, DIPLOMACY_BTN, border_radius=4)
    pygame.draw.rect(surface, ACCENT if (dip_hover or is_dip_open) else (80, 80, 100), DIPLOMACY_BTN, 1, border_radius=4)
    dip_txt = font_small.render("Diplomacy (D)", True, (255, 255, 255) if (dip_hover or is_dip_open) else TEXT)
    surface.blit(dip_txt, dip_txt.get_rect(center=(DIPLOMACY_BTN[0] + DIPLOMACY_BTN[2] // 2, DIPLOMACY_BTN[1] + DIPLOMACY_BTN[3] // 2)))

    # 3. Military Button (M)
    is_mil_open = world.get('actions_open') and world.get('actions_tab') == 2
    mil_hover = MILITARY_BTN[0] <= mx <= MILITARY_BTN[0] + MILITARY_BTN[2] and MILITARY_BTN[1] <= my <= MILITARY_BTN[1] + MILITARY_BTN[3]
    mil_bg = (75, 75, 100) if is_mil_open else ((60, 60, 80) if mil_hover else (40, 40, 52))
    pygame.draw.rect(surface, mil_bg, MILITARY_BTN, border_radius=4)
    pygame.draw.rect(surface, ACCENT if (mil_hover or is_mil_open) else (80, 80, 100), MILITARY_BTN, 1, border_radius=4)
    mil_txt = font_small.render("Military (M)", True, (255, 255, 255) if (mil_hover or is_mil_open) else TEXT)
    surface.blit(mil_txt, mil_txt.get_rect(center=(MILITARY_BTN[0] + MILITARY_BTN[2] // 2, MILITARY_BTN[1] + MILITARY_BTN[3] // 2)))


def top_bar_action_hit(pos):
    """Return 'help', 'compare', 'diplomacy', 'military', or None if an action button was clicked."""
    mx, my = pos
    if HELP_BTN[0] <= mx <= HELP_BTN[0] + HELP_BTN[2] and HELP_BTN[1] <= my <= HELP_BTN[1] + HELP_BTN[3]:
        return 'help'
    if COMPARE_BTN[0] <= mx <= COMPARE_BTN[0] + COMPARE_BTN[2] and COMPARE_BTN[1] <= my <= COMPARE_BTN[1] + COMPARE_BTN[3]:
        return 'compare'
    if DIPLOMACY_BTN[0] <= mx <= DIPLOMACY_BTN[0] + DIPLOMACY_BTN[2] and DIPLOMACY_BTN[1] <= my <= DIPLOMACY_BTN[1] + DIPLOMACY_BTN[3]:
        return 'diplomacy'
    if MILITARY_BTN[0] <= mx <= MILITARY_BTN[0] + MILITARY_BTN[2] and MILITARY_BTN[1] <= my <= MILITARY_BTN[1] + MILITARY_BTN[3]:
        return 'military'
    return None


def draw_actions_modal(surface, world, font, font_small, mouse_pos=None):
    """Draw comprehensive Sovereign Actions Suite modal overlay."""
    if not world.get('actions_open', False):
        return

    box_x = 24
    box_y = 16
    box_w = WIDTH - 48
    box_h = HEIGHT - 32

    # Dim background
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((10, 10, 16, 230))
    surface.blit(overlay, (0, 0))

    # Main modal card
    pygame.draw.rect(surface, (20, 20, 28), (box_x, box_y, box_w, box_h), border_radius=8)
    pygame.draw.rect(surface, BORDER_MODAL, (box_x, box_y, box_w, box_h), 2, border_radius=8)

    # Title & Active Sovereign Switcher
    active_nation = get_active_nation(world)
    title_txt = font.render(f"SOVEREIGN COMMAND SUITE — Sovereign Nation: {active_nation.name if active_nation else 'None'}", True, ACCENT)
    surface.blit(title_txt, (box_x + 20, box_y + 16))

    # Close hint
    close_hint = font_small.render("[Esc / Click outside to close]", True, DIM)
    surface.blit(close_hint, (box_x + box_w - close_hint.get_width() - 20, box_y + 18))

    # Nation Switcher Buttons (top-right of header)
    draw_nation_switcher(surface, world, box_x, box_y + 48, font_small, mouse_pos)

    # Tabs (Diplomacy, Military, Construction, Innovation)
    cur_y = draw_action_tabs(surface, world, box_x, box_y + 84, font_small, mouse_pos)

    active_tab = world.get('actions_tab', 1)
    if active_tab == 1:
        draw_diplomacy_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)
    elif active_tab == 2:
        draw_military_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)
    elif active_tab == 3:
        draw_construction_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)
    elif active_tab == 4:
        draw_innovation_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)
    elif active_tab == 5:
        draw_sovereign_bonds_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)


def get_active_nation(world):
    """Return currently active nation object controlled by player."""
    nations = world.get('nations', [])
    pinned = world.get('selected_region')
    if pinned is not None and getattr(pinned, 'owner_nation', None) is not None:
        return pinned.owner_nation
    active_name = world.get('player_nation_name')
    if active_name:
        for n in nations:
            if n.name == active_name:
                return n
    if world.get('selected_nation') is not None:
        return world['selected_nation']
    return nations[0] if nations else None


def draw_nation_switcher(surface, world, box_x, y, font_small, mouse_pos=None):
    """Draw sovereign switcher buttons so player can switch active nation in 1 click."""
    nations = world.get('nations', [])
    active_n = get_active_nation(world)
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    lbl = font_small.render("Switch Sovereign Nation:", True, TEXT)
    surface.blit(lbl, (box_x + 20, y + 4))

    sx = box_x + 20 + lbl.get_width() + 14
    for n in nations:
        is_active = (active_n is not None and active_n.name == n.name)
        col = NATION_COLORS.get(n.name, (100, 100, 100))
        btn_rect = (sx, y, 130, 26)
        is_hover = btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]
        
        bg = (50, 50, 70) if is_active else ((40, 40, 55) if is_hover else (28, 28, 38))
        pygame.draw.rect(surface, bg, btn_rect, border_radius=4)
        pygame.draw.rect(surface, col if is_active else (80, 80, 100), btn_rect, 2 if is_active else 1, border_radius=4)
        
        txt = font_small.render(f"{n.name} ({n.currency})", True, (255, 255, 255) if is_active else TEXT)
        surface.blit(txt, txt.get_rect(center=(sx + 65, y + 13)))
        sx += 140


def draw_action_tabs(surface, world, box_x, y, font_small, mouse_pos=None):
    """Draw action tabs: 1. Diplomacy, 2. Military, 3. Construction, 4. Innovation, 5. Sovereign Bonds."""
    active_tab = world.get('actions_tab', 1)
    tabs = [
        (1, "1. Diplomacy & Treaties (D)"),
        (2, "2. Military & Defense (M)"),
        (3, "3. Physical Construction"),
        (4, "4. Innovation & Bounties"),
        (5, "5. Sovereign Debt & Bonds"),
    ]
    tab_w = 216
    tab_h = 30
    start_x = box_x + 20
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    for tab_id, label in tabs:
        is_active = (active_tab == tab_id)
        rect = (start_x, y, tab_w, tab_h)
        is_hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3]
        bg = TAB_ACTIVE_BG if is_active else ((40, 40, 55) if is_hover else TAB_INACTIVE_BG)
        border_c = ACCENT if is_active else ((110, 110, 130) if is_hover else (60, 60, 75))
        pygame.draw.rect(surface, bg, rect, border_radius=5)
        pygame.draw.rect(surface, border_c, rect, 1, border_radius=5)
        txt_c = (255, 255, 255) if is_active else (TEXT if is_hover else DIM)
        tsurf = font_small.render(label, True, txt_c)
        surface.blit(tsurf, tsurf.get_rect(center=(start_x + tab_w // 2, y + tab_h // 2)))
        start_x += tab_w + 10

    return y + tab_h + 14


# =============================================================================
# TAB 1: DIPLOMACY & TREATIES
# =============================================================================

def draw_diplomacy_tab(surface, world, box_x, y, box_w, box_h, font, font_small, mouse_pos=None):
    active_n = get_active_nation(world)
    if not active_n:
        return

    nations = world.get('nations', [])
    diplomacy = get_diplomacy()
    other_nations = [n for n in nations if n.name != active_n.name]
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    header = font.render(f"Bilateral Relations & Treaties for {active_n.name}", True, TEXT)
    surface.blit(header, (box_x + 20, y))

    feedback = world.get('action_feedback')
    if feedback:
        fb_text, fb_col, _ = feedback
        fb_surf = font_small.render(f"• {fb_text}", True, fb_col)
        surface.blit(fb_surf, (box_x + 360, y + 4))

    card_y = y + 36
    card_w = box_w - 40
    card_h = 126

    for other in other_nations:
        rel = diplomacy.get_relation(active_n.name, other.name)
        is_war = diplomacy.are_at_war(active_n.name, other.name)
        has_trade = diplomacy.has_treaty(active_n.name, other.name, TreatyType.TRADE_PACT.value)
        has_nap = diplomacy.has_treaty(active_n.name, other.name, TreatyType.NON_AGGRESSION.value)
        has_alliance = diplomacy.has_treaty(active_n.name, other.name, TreatyType.DEFENSIVE_ALLIANCE.value)

        card_rect = (box_x + 20, card_y, card_w, card_h)
        pygame.draw.rect(surface, CARD_BG, card_rect, border_radius=6)
        pygame.draw.rect(surface, RED if is_war else ((70, 70, 90)), card_rect, 2 if is_war else 1, border_radius=6)

        # Left Column: Nation Info & Relation
        n_col = NATION_COLORS.get(other.name, TEXT)
        n_txt = font.render(f"{other.name} ({other.currency}) — Regime: {other.regime_type}", True, n_col)
        surface.blit(n_txt, (box_x + 36, card_y + 12))

        rel_color = GREEN if rel > 0.2 else (RED if rel < -0.2 else TEXT)
        rel_label = "WAR" if is_war else ("ALLIED" if has_alliance else ("FRIENDLY" if rel > 0.3 else ("HOSTILE" if rel < -0.3 else "NEUTRAL")))
        rel_txt = font_small.render(f"Relation: {rel:+.2f} [{rel_label}]", True, rel_color)
        surface.blit(rel_txt, (box_x + 36, card_y + 40))

        # Visual Relation Bar (-1.0 to +1.0)
        bar_x, bar_y_pos, bar_w, bar_h = box_x + 36, card_y + 64, 280, 8
        pygame.draw.rect(surface, (35, 35, 48), (bar_x, bar_y_pos, bar_w, bar_h), border_radius=3)
        fill_pct = max(0.0, min(1.0, (rel + 1.0) / 2.0))
        fill_w = int(bar_w * fill_pct)
        pygame.draw.rect(surface, rel_color, (bar_x, bar_y_pos, fill_w, bar_h), border_radius=3)

        # Active Treaties Summary Line
        treaties_str = []
        if has_trade: treaties_str.append("Trade Pact")
        if has_nap: treaties_str.append("NAP")
        if has_alliance: treaties_str.append("Alliance")
        t_summary = f"Active Treaties: {', '.join(treaties_str) if treaties_str else 'None'}"
        t_surf = font_small.render(t_summary, True, (80, 200, 255) if has_alliance else (GREEN if has_trade else DIM))
        surface.blit(t_surf, (box_x + 36, card_y + 84))

        # Right Column: 2x2 Action Button Grid
        btn_x1 = box_x + card_w - 510
        btn_x2 = box_x + card_w - 250
        btn_w = 240
        btn_h = 36
        row1_y = card_y + 16
        row2_y = card_y + 64

        # 1. Trade Pact Button (Top Left)
        trade_rect = (btn_x1, row1_y, btn_w, btn_h)
        trade_label = "Cancel Trade Pact" if has_trade else "+ Propose Trade Pact"
        draw_action_button(surface, trade_rect, trade_label, font_small, mx, my,
                           disabled=is_war, active=has_trade, color=GREEN if not has_trade else (100, 220, 140))

        # 2. NAP Button (Top Right)
        nap_rect = (btn_x2, row1_y, btn_w, btn_h)
        nap_label = "Cancel NAP Treaty" if has_nap else "+ Propose NAP Treaty"
        draw_action_button(surface, nap_rect, nap_label, font_small, mx, my,
                           disabled=is_war, active=has_nap, color=ACCENT if not has_nap else (255, 220, 120))

        # 3. Defensive Alliance Button (Bottom Left)
        ally_rect = (btn_x1, row2_y, btn_w, btn_h)
        ally_label = "Cancel Def Alliance" if has_alliance else "+ Form Def Alliance"
        draw_action_button(surface, ally_rect, ally_label, font_small, mx, my,
                           disabled=is_war, active=has_alliance, color=(80, 200, 255))

        # 4. War / Peace Button (Bottom Right)
        war_rect = (btn_x2, row2_y, btn_w, btn_h)
        if is_war:
            draw_action_button(surface, war_rect, "Sign Peace Treaty", font_small, mx, my, color=GREEN)
        else:
            draw_action_button(surface, war_rect, "Declare War", font_small, mx, my, color=RED)

        card_y += card_h + 12

    # Live Event Log Section
    log_y = card_y + 10
    pygame.draw.rect(surface, (24, 24, 34), (box_x + 20, log_y, card_w, box_h - (log_y - y) - 10), border_radius=5)
    log_hdr = font_small.render("Recent Diplomatic Events & Betrayal Memory Log:", True, ACCENT)
    surface.blit(log_hdr, (box_x + 32, log_y + 8))

    events = list(diplomacy.diplomacy_log[-6:])
    events.reverse()
    ey = log_y + 32
    for ev in events:
        msg = f"T={ev.get('t', '?')}: {ev.get('message', '')}"
        e_surf = font_small.render(msg, True, RED if 'WAR' in ev.get('event', '') or 'BETRAY' in ev.get('event', '') else TEXT)
        surface.blit(e_surf, (box_x + 32, ey))
        ey += 20


# =============================================================================
# TAB 2: MILITARY & GARRISONS
# =============================================================================

def draw_military_tab(surface, world, box_x, y, box_w, box_h, font, font_small, mouse_pos=None):
    active_n = get_active_nation(world)
    if not active_n:
        return

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    units = getattr(active_n, 'military_units', [])
    total_strength = sum(u.strength for u in units)
    total_soldiers = sum(u.soldiers for u in units)
    treasury = active_n.treasury()

    header = font.render(f"Armed Forces & Garrisons of {active_n.name} (Total Soldiers: {total_soldiers:,}, Total Strength: {total_strength:.1f})", True, TEXT)
    surface.blit(header, (box_x + 20, y))

    # Selected Tile Recruitment Action Bar
    pinned_tile = world.get('selected_region')
    tile_name = pinned_tile.name if pinned_tile else (active_n.tiles[0].name if active_n.tiles else "None")
    is_owned = pinned_tile in active_n.tiles if pinned_tile else True

    recruit_bar_y = y + 36
    pygame.draw.rect(surface, CARD_BG, (box_x + 20, recruit_bar_y, box_w - 40, 52), border_radius=6)
    
    rec_lbl = font_small.render(f"Recruitment on Tile [{tile_name}]:", True, ACCENT if is_owned else DIM)
    surface.blit(rec_lbl, (box_x + 36, recruit_bar_y + 16))

    rec_btn_rect = (box_x + 280, recruit_bar_y + 12, 220, 28)
    draw_action_button(surface, rec_btn_rect, "Recruit Unit (15 soldiers, $15)", font_small, mx, my,
                       disabled=not is_owned or treasury['total'] < 15.0)

    # Unit List
    card_y = recruit_bar_y + 64
    card_w = box_w - 40
    unit_h = 75

    unit_title = font_small.render("Deployed Military Units & Garrisons:", True, TEXT)
    surface.blit(unit_title, (box_x + 20, card_y))
    card_y += 24

    if not units:
        empty_lbl = font_small.render("No active military units deployed. Recruit soldiers above to defend your borders.", True, DIM)
        surface.blit(empty_lbl, (box_x + 36, card_y + 16))
    else:
        for u in units:
            card_rect = (box_x + 20, card_y, card_w, unit_h)
            pygame.draw.rect(surface, CARD_BG, card_rect, border_radius=6)
            pygame.draw.rect(surface, (70, 70, 90), card_rect, 1, border_radius=6)

            u_name = font.render(f"Unit ID: {u.unit_id} — Stationed on Tile [{u.region_name}]", True, ACCENT)
            surface.blit(u_name, (box_x + 36, card_y + 10))

            u_stats = font_small.render(
                f"Soldiers: {u.soldiers}  |  Morale: {u.morale*100:.0f}%  |  Equipment: {u.equipment_quality:.1f}x  |  XP: {u.veteran_xp:.2f}  |  Strength: {u.strength:.1f}",
                True, GREEN if u.morale > 0.7 else (RED if u.morale < 0.3 else TEXT)
            )
            surface.blit(u_stats, (box_x + 36, card_y + 38))

            card_y += unit_h + 10


# =============================================================================
# TAB 3: PHYSICAL CONSTRUCTION & INTENTS
# =============================================================================

def draw_construction_tab(surface, world, box_x, y, box_w, box_h, font, font_small, mouse_pos=None):
    active_n = get_active_nation(world)
    if not active_n:
        return

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    treasury = active_n.treasury()
    pinned_tile = world.get('selected_region')
    target_tile = pinned_tile if (pinned_tile and pinned_tile in active_n.tiles) else (active_n.tiles[0] if active_n.tiles else None)
    tile_name = getattr(target_tile, 'display_name', getattr(target_tile, 'city_name', target_tile.name)) if target_tile else "None"
    is_owned = target_tile in active_n.tiles if target_tile else False

    header = font.render(f"Physical Construction & Strategic Intents on [{tile_name}] (Treasury: ${treasury['total']:,.2f})", True, TEXT)
    surface.blit(header, (box_x + 20, y))

    card_y = y + 36
    card_w = box_w - 40

    recipes = [
        ('mountain_pass', 'Alpine Mountain Pass Road', '$380', 'Unblocks overland trade across impassable alpine ridges & steep cliffs'),
        ('river_bridge', 'Fluvial River Bridge & Port', '$300', 'Constructs permanent river crossing & maximizes fluvial trade throughput'),
        ('paved_road', 'Paved Highway Network', '$350', 'Reduces regional transport friction and delays by 40%'),
        ('granary', 'State Granary', '$250', '+25% Food Output and grain reserves'),
        ('sawmill', 'Mechanized Sawmill', '$300', '+30% Timber extraction and lumber yield'),
        ('workshop', 'Artisan Workshop & Guild', '$400', '+30% Furniture manufacturing output'),
    ]

    for r_key, r_name, r_cost, r_desc in recipes:
        recipe_obj = BUILDING_RECIPES.get(r_key)
        cost_val = recipe_obj.cost if recipe_obj else 100.0
        can_afford = treasury['total'] >= cost_val

        # Check status on target tile
        is_built = any(b.name == r_key for b in getattr(target_tile, 'buildings', [])) if target_tile else False
        active_proj = next((p for p in getattr(target_tile, 'construction_projects', []) if p.recipe.name == r_key and p.status == 'in_progress'), None) if target_tile else None
        if active_proj is None and active_n:
            active_proj = next((p for p in getattr(active_n, 'construction_projects', []) if p.recipe.name == r_key and p.status == 'in_progress' and p.region == target_tile), None)

        card_rect = (box_x + 20, card_y, card_w, 58)
        btn_rect = (box_x + card_w - 220, card_y + 13, 190, 32)

        if is_built:
            # Whole card box changes color to Emerald Green
            pygame.draw.rect(surface, (22, 44, 32), card_rect, border_radius=6)
            pygame.draw.rect(surface, (60, 180, 100), card_rect, 1, border_radius=6)
            t_lbl = font.render(f"{r_name} — [Installed / Active]", True, (120, 240, 150))
            surface.blit(t_lbl, (box_x + 36, card_y + 8))
            d_lbl = font_small.render(f"Modifiers: {r_desc}", True, DIM)
            surface.blit(d_lbl, (box_x + 36, card_y + 32))
            from ui_icons import draw_progress_bar_button
            draw_progress_bar_button(surface, btn_rect, "Structure Active", 1.0, font_small, theme='complete', icon_kind='check')

        elif active_proj is not None:
            # Whole card box changes color to Construction Amber
            pygame.draw.rect(surface, (46, 38, 20), card_rect, border_radius=6)
            pygame.draw.rect(surface, (245, 180, 50), card_rect, 1, border_radius=6)
            pct = min(1.0, max(0.0, active_proj.turns_elapsed / max(1, active_proj.total_turns)))
            t_lbl = font.render(f"{r_name} — [Under Construction...]", True, (255, 210, 80))
            surface.blit(t_lbl, (box_x + 36, card_y + 8))
            d_lbl = font_small.render(f"Progress: {active_proj.turns_elapsed}/{active_proj.total_turns} turns ({int(pct*100)}%) — {r_desc}", True, (240, 220, 180))
            surface.blit(d_lbl, (box_x + 36, card_y + 32))

            # In-button live progress bar
            from ui_icons import draw_progress_bar_button
            draw_progress_bar_button(surface, btn_rect, f"Building... {active_proj.turns_elapsed}/{active_proj.total_turns}t ({int(pct*100)}%)", pct, font_small, theme='construction', icon_kind=r_key)

        else:
            pygame.draw.rect(surface, CARD_BG, card_rect, border_radius=6)
            pygame.draw.rect(surface, (70, 70, 90), card_rect, 1, border_radius=6)
            t_lbl = font.render(f"{r_name} — Cost: {r_cost}", True, ACCENT)
            surface.blit(t_lbl, (box_x + 36, card_y + 8))
            d_lbl = font_small.render(f"Modifiers: {r_desc}", True, DIM)
            surface.blit(d_lbl, (box_x + 36, card_y + 32))
            draw_action_button(surface, btn_rect, f"Commission ({r_cost})", font_small, mx, my,
                               disabled=not is_owned or not can_afford)

        card_y += 66

    # Active Projects List
    active_projects = getattr(active_n, 'construction_projects', [])
    proj_hdr = font_small.render("Active Construction Projects:", True, TEXT)
    surface.blit(proj_hdr, (box_x + 20, card_y + 8))
    card_y += 32

    if not active_projects:
        empty_lbl = font_small.render("No ongoing construction projects in this nation.", True, DIM)
        surface.blit(empty_lbl, (box_x + 36, card_y + 6))
    else:
        for p in active_projects:
            p_rect = (box_x + 20, card_y, card_w, 42)
            pct = min(1.0, max(0.0, p.turns_elapsed / max(1, p.total_turns)))
            pygame.draw.rect(surface, (34, 30, 22) if p.status == 'in_progress' else CARD_BG, p_rect, border_radius=4)
            pygame.draw.rect(surface, (245, 180, 50) if p.status == 'in_progress' else (70, 70, 90), p_rect, 1, border_radius=4)

            # Draw progress bar track
            if p.status == 'in_progress':
                pb_rect = (box_x + card_w - 180, card_y + 10, 160, 22)
                from ui_icons import draw_progress_bar_button
                draw_progress_bar_button(surface, pb_rect, f"{p.turns_elapsed}/{p.total_turns}t ({int(pct*100)}%)", pct, font_small, theme='construction', icon_kind=p.recipe.name)

            p_txt = font_small.render(
                f"Project {p.project_id}: Building {p.recipe.display_name} in {p.region.name} (Status: {p.status.upper()})",
                True, GREEN if p.status == 'completed' else (255, 215, 90)
            )
            surface.blit(p_txt, (box_x + 36, card_y + 12))
            card_y += 48


# =============================================================================
# TAB 4: AI SOVEREIGN ADVISORY
# =============================================================================
# TAB 4: INDUCED INNOVATION & ROYAL BOUNTIES
# =============================================================================

def draw_innovation_tab(surface, world, box_x, y, box_w, box_h, font, font_small, mouse_pos=None):
    active_n = get_active_nation(world)
    if not active_n:
        return

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    from innovation import get_innovation_system, TECH_CATALOG, TechDomain
    from tile_resources import TileResource, RESOURCE_META, get_nation_resources
    inno = get_innovation_system()

    treasury = active_n.treasury()
    header = font.render(f"Induced Innovation & Historical Tech Tree — {active_n.name} (Treasury: ${treasury['total']:,.2f})", True, TEXT)
    surface.blit(header, (box_x + 20, y))

    card_y = y + 34
    card_w = box_w - 40

    # 1. National Resource Endowments Ribbon
    res_rect = (box_x + 20, card_y, card_w, 32)
    pygame.draw.rect(surface, (24, 26, 36), res_rect, border_radius=5)
    pygame.draw.rect(surface, (60, 65, 85), res_rect, 1, border_radius=5)

    from ui_icons import get_icon, draw_icon_badge, draw_progress_bar_button
    accessible_res = get_nation_resources(active_n, world=world)
    rx = box_x + 30
    lbl_r = font_small.render("Resources:", True, TEXT)
    surface.blit(lbl_r, (rx, card_y + 8))
    rx += lbl_r.get_width() + 14

    for r_enum, r_info in RESOURCE_META.items():
        has_r = r_enum in accessible_res
        w = draw_icon_badge(surface, rx, card_y + 7, r_enum.value, r_info.name, font_small, color=r_info.color, dimmed=not has_r, icon_size=16)
        rx += w + 14

    card_y += 40

    # 2. Era Selector Buttons (Era I..IV)
    cur_era = world.get('innovation_era', 1)
    eras = [
        (1, "Era I: Feudal & Medieval"),
        (2, "Era II: Renaissance & Commercial"),
        (3, "Era III: Steam & Industrial"),
        (4, "Era IV: Petroleum & Modern"),
    ]
    era_btn_w = (card_w - 30) // 4
    ex = box_x + 20
    for era_num, era_label in eras:
        is_sel = (cur_era == era_num)
        eb_rect = (ex, card_y, era_btn_w, 28)
        is_h = eb_rect[0] <= mx <= eb_rect[0] + eb_rect[2] and eb_rect[1] <= my <= eb_rect[1] + eb_rect[3]
        bg = (55, 75, 105) if is_sel else ((40, 40, 55) if is_h else (28, 28, 38))
        border_c = ACCENT if is_sel else ((110, 110, 130) if is_h else (60, 60, 75))
        pygame.draw.rect(surface, bg, eb_rect, border_radius=4)
        pygame.draw.rect(surface, border_c, eb_rect, 1, border_radius=4)
        t_col = (255, 255, 255) if is_sel else (TEXT if is_h else DIM)
        t_s = font_small.render(era_label, True, t_col)
        surface.blit(t_s, t_s.get_rect(center=(ex + era_btn_w // 2, card_y + 14)))
        ex += era_btn_w + 10

    card_y += 38

    # 3. Technologies in Current Era
    discovered = inno.get_discovered_techs(active_n.name)
    diffusing = inno.diffusion_progress.get(active_n.name, {})

    era_techs = [t for t in TECH_CATALOG.values() if t.era == cur_era]

    for tech in era_techs:
        tech_id = tech.tech_id
        card_rect = (box_x + 20, card_y, card_w, 62)
        pygame.draw.rect(surface, CARD_BG, card_rect, border_radius=6)
        pygame.draw.rect(surface, (70, 70, 90), card_rect, 1, border_radius=6)

        is_disc = tech_id in discovered
        diff_prog = diffusing.get(tech_id, 0.0)
        has_bounty = any(b.nation_name == active_n.name and b.tech_id == tech_id for b in inno.active_bounties)

        # Check missing prerequisites
        missing_techs = [t_req for t_req in tech.required_techs if t_req not in discovered]
        missing_res = [r_req for r_req in tech.required_resources if r_req not in accessible_res]

        # Status badge
        if is_disc:
            badge_txt = "MASTERED"
            badge_col = GREEN
        elif diff_prog > 0:
            badge_txt = f"DIFFUSING ({int(diff_prog*100)}%)"
            badge_col = (80, 200, 255)
        elif has_bounty:
            badge_txt = "ROYAL PRIZE ACTIVE"
            badge_col = (245, 200, 70)
        elif missing_techs or missing_res:
            reasons = []
            if missing_techs:
                reasons.append("Tech Pre-Reqs")
            if missing_res:
                reasons.append(f"Missing {', '.join(RESOURCE_META[r].name for r in missing_res)}")
            badge_txt = f"BLOCKED: {', '.join(reasons)}"
            badge_col = RED
        else:
            pressure = tech.bottleneck_evaluator(active_n, active_n.tiles) if tech.bottleneck_evaluator else 1.0
            cur_xp = inno.get_domain_xp(active_n.name, tech.domain)
            badge_txt = f"PRESSURE: {pressure:.1f}x ({int(cur_xp)}/{int(tech.base_xp_required)} XP)"
            badge_col = (235, 140, 50) if pressure > 1.5 else DIM

        # Draw Domain icon
        dom_icon = get_icon(tech.domain.value, size=16)
        surface.blit(dom_icon, (box_x + 36, card_y + 9))

        t_lbl = font.render(f"{tech.name} ({tech.domain.value.capitalize()})", True, (255, 255, 255) if is_disc else TEXT)
        surface.blit(t_lbl, (box_x + 58, card_y + 7))

        b_surf = font_small.render(f"[{badge_txt}]", True, badge_col)
        surface.blit(b_surf, (box_x + 460, card_y + 9))

        # Required resources subtext with mini-icons
        sub_x = box_x + 36
        if tech.required_resources:
            lbl_req = font_small.render("Requires:", True, DIM)
            surface.blit(lbl_req, (sub_x, card_y + 36))
            sub_x += lbl_req.get_width() + 8
            for req_r in tech.required_resources:
                has_req = req_r in accessible_res
                w = draw_icon_badge(surface, sub_x, card_y + 35, req_r.value, RESOURCE_META[req_r].name, font_small,
                                    color=RESOURCE_META[req_r].color if has_req else (235, 90, 90),
                                    dimmed=not has_req, icon_size=14)
                sub_x += w + 8
            dot = font_small.render("• " + tech.description, True, DIM)
            surface.blit(dot, (sub_x, card_y + 36))
        else:
            d_lbl = font_small.render(f"General Practice • {tech.description}", True, DIM)
            surface.blit(d_lbl, (sub_x, card_y + 36))

        # Royal Bounty Button / Science Progress Bar
        btn_rect = (box_x + card_w - 230, card_y + 14, 210, 32)
        if is_disc:
            draw_progress_bar_button(surface, btn_rect, "Technology Mastered", 1.0, font_small, theme='complete', icon_kind='check')
        elif has_bounty:
            cur_xp = inno.get_domain_xp(active_n.name, tech.domain)
            pct = min(1.0, max(0.0, cur_xp / max(1.0, tech.base_xp_required)))
            draw_progress_bar_button(surface, btn_rect, f"Researching {int(pct*100)}% ({int(cur_xp)}/{int(tech.base_xp_required)} XP)", pct, font_small, theme='science', icon_kind='rare_minerals')
        elif diff_prog > 0:
            draw_progress_bar_button(surface, btn_rect, f"Diffusing... {int(diff_prog*100)}%", diff_prog, font_small, theme='diffusion', icon_kind='im')
        elif missing_techs or missing_res:
            draw_action_button(surface, btn_rect, "Pledge Royal Prize ($300)", font_small, mx, my, disabled=True)
        else:
            can_afford = treasury['total'] >= 300.0
            draw_action_button(surface, btn_rect, "Pledge Royal Prize ($300)", font_small, mx, my, disabled=not can_afford)

        card_y += 70

# =============================================================================
# TAB 5: SOVEREIGN DEBT & ISRB BONDS
# =============================================================================

def draw_sovereign_bonds_tab(surface, world, box_x, y, box_w, box_h, font, font_small, mouse_pos=None):
    """Draw Tab 5: Sovereign Debt, ISRB Rating Bureau, and Cross-Border Bond Market."""
    active_n = get_active_nation(world)
    if not active_n:
        return

    from sovereign_bonds import get_bond_market
    market = get_bond_market()
    isrb = market.isrb

    selected_duration = world.get('bond_duration_selected', 20)
    rating, market_yield = isrb.get_market_yield(active_n, selected_duration, world)
    has_board_seat = active_n.name in isrb.board_seats
    active_mod = isrb.rating_modifiers.get(active_n.name, 0)
    treasury = active_n.treasury()
    total_debt = sum(b.principal for b in market.get_bonds_owed_by(active_n.name))
    foreign_reserves = sum(b.principal for b in market.get_bonds_held_by(active_n.name))
    passive_income = sum(b.per_turn_coupon for b in market.get_bonds_held_by(active_n.name))
    servicing_cost = sum(b.per_turn_coupon for b in market.get_bonds_owed_by(active_n.name))

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    col_w = (box_w - 50) // 2
    left_x = box_x + 20
    right_x = box_x + 30 + col_w

    # -------------------------------------------------------------------------
    # LEFT COLUMN: ISRB BUREAU & DOMESTIC ISSUANCE
    # -------------------------------------------------------------------------

    # 1. ISRB Rating Card
    card1_y = y
    card1_h = 160
    pygame.draw.rect(surface, CARD_BG, (left_x, card1_y, col_w, card1_h), border_radius=6)
    pygame.draw.rect(surface, (60, 60, 80), (left_x, card1_y, col_w, card1_h), 1, border_radius=6)

    # Title & Rating
    from ui_icons import get_icon
    scale_ico = get_icon('scale', 18)
    surface.blit(scale_ico, (left_x + 14, card1_y + 12))
    t_title = font.render("International Sovereign Rating Bureau (ISRB)", True, ACCENT)
    surface.blit(t_title, (left_x + 38, card1_y + 10))

    rating_color = (120, 240, 150) if rating in ('AAA', 'AA') else ((245, 205, 70) if rating in ('A', 'BBB') else (240, 90, 90))
    rating_lbl = font.render(f"Rating: {rating}", True, rating_color)
    surface.blit(rating_lbl, (left_x + 16, card1_y + 36))

    seat_str = "✓ Board Member" if has_board_seat else "Standard Member"
    stat_txt = font_small.render(
        f"Base Yield: {market_yield*100:.2f}%/t  •  Seat: {seat_str}  •  Mod: {'+' if active_mod > 0 else ''}{active_mod}",
        True, TEXT
    )
    surface.blit(stat_txt, (left_x + 150, card1_y + 40))

    # Influence Actions
    inf_hdr = font_small.render("SOVEREIGN DIPLOMATIC INFLUENCE ACTIONS:", True, DIM)
    surface.blit(inf_hdr, (left_x + 16, card1_y + 66))

    btn_w = (col_w - 40) // 3
    bx1 = left_x + 14
    bx2 = bx1 + btn_w + 6
    bx3 = bx2 + btn_w + 6
    btn_y = card1_y + 86

    can_lobby = active_n.government.agent.cash >= 200.0
    can_downgrade = active_n.government.agent.cash >= 350.0
    can_seat = active_n.government.agent.cash >= 600.0 and not has_board_seat

    draw_action_button(surface, (bx1, btn_y, btn_w, 28), "Lobby Upgrade ($200)", font_small, mx, my, disabled=not can_lobby)
    draw_action_button(surface, (bx2, btn_y, btn_w, 28), "Audit Rival ($350)", font_small, mx, my, disabled=not can_downgrade)
    draw_action_button(surface, (bx3, btn_y, btn_w, 28), "Board Seat ($600)" if not has_board_seat else "✓ Board Member", font_small, mx, my, disabled=not can_seat)

    # Risk Warning
    risk_lbl = font_small.render("15%-20% Risk of Rating Scandal if influence tampering is leaked by auditors.", True, (210, 160, 100))
    surface.blit(risk_lbl, (left_x + 16, card1_y + 124))

    # 2. Domestic Sovereign Debt Issuance Card
    card2_y = card1_y + card1_h + 10
    card2_h = box_h - card1_h - 22
    pygame.draw.rect(surface, CARD_BG, (left_x, card2_y, col_w, card2_h), border_radius=6)
    pygame.draw.rect(surface, (60, 60, 80), (left_x, card2_y, col_w, card2_h), 1, border_radius=6)

    crown_ico = get_icon('crown', 18)
    surface.blit(crown_ico, (left_x + 14, card2_y + 12))
    iss_title = font.render("Issue Domestic Sovereign Debt", True, (245, 215, 120))
    surface.blit(iss_title, (left_x + 38, card2_y + 10))

    # Duration selector buttons (20t, 50t, 100t)
    dur_lbl = font_small.render("Select Maturity Term:", True, TEXT)
    surface.blit(dur_lbl, (left_x + 16, card2_y + 36))

    d_w = 90
    dx = left_x + 160
    for d in (20, 50, 100):
        _, d_yield = isrb.get_market_yield(active_n, d, world)
        is_sel = (selected_duration == d)
        draw_action_button(surface, (dx, card2_y + 32, d_w, 24), f"{d}t ({d_yield*100:.2f}%)", font_small, mx, my, active=is_sel)
        dx += d_w + 8

    # Issuance amounts ($500, $1,000, $2,500)
    iss_y = card2_y + 64
    amounts = [500.0, 1000.0, 2500.0]
    ib_w = (col_w - 40) // 3
    ib_x = left_x + 14

    for amt in amounts:
        _, y_rate = isrb.get_market_yield(active_n, selected_duration, world)
        c_cost = round(amt * y_rate, 2)
        draw_action_button(surface, (ib_x, iss_y, ib_w, 30), f"Issue ${amt:.0f}", font_small, mx, my, color=(245, 190, 80))
        sub_c = font_small.render(f"Cost: -${c_cost:.2f}/t", True, DIM)
        surface.blit(sub_c, (ib_x + 6, iss_y + 34))
        ib_x += ib_w + 6

    # Domestic debt summary
    d_sum_y = iss_y + 58
    pygame.draw.line(surface, (50, 50, 65), (left_x + 14, d_sum_y), (left_x + col_w - 14, d_sum_y), 1)

    debt_txt = font_small.render(f"Outstanding Debt: ${total_debt:,.0f}  •  Per-Turn Servicing: -${servicing_cost:.2f}/turn", True, (240, 140, 120))
    surface.blit(debt_txt, (left_x + 16, d_sum_y + 6))

    # List active debt owed with redeem button
    owed_bonds = market.get_bonds_owed_by(active_n.name)
    list_y = d_sum_y + 26
    if not owed_bonds:
        no_d = font_small.render("No active domestic debt issued. State balance sheet is unencumbered.", True, (120, 220, 140))
        surface.blit(no_d, (left_x + 16, list_y))
    else:
        for b in owed_bonds[:3]:
            turns_left = max(0, b.maturity_turn - world.get('turn', 1))
            b_txt = font_small.render(f"#{b.bond_id}: ${b.principal:.0f} owed to {b.holder_nation} (-${b.per_turn_coupon:.2f}/t, {turns_left}t left)", True, TEXT)
            surface.blit(b_txt, (left_x + 16, list_y + 3))
            can_redeem = active_n.government.agent.cash >= b.principal
            draw_action_button(surface, (left_x + col_w - 110, list_y, 96, 20), "Redeem Early", font_small, mx, my, disabled=not can_redeem)
            list_y += 24

    # -------------------------------------------------------------------------
    # RIGHT COLUMN: FOREIGN SOVEREIGN BOND MARKET & RESERVES
    # -------------------------------------------------------------------------

    # 3. Foreign Sovereign Bond Market
    card3_y = y
    card3_h = 220
    pygame.draw.rect(surface, CARD_BG, (right_x, card3_y, col_w, card3_h), border_radius=6)
    pygame.draw.rect(surface, (60, 60, 80), (right_x, card3_y, col_w, card3_h), 1, border_radius=6)

    glob_ico = get_icon('im', 18)
    surface.blit(glob_ico, (right_x + 14, card3_y + 12))
    mkt_title = font.render("Foreign Sovereign Bond Market (Buy Foreign Debt)", True, (120, 220, 140))
    surface.blit(mkt_title, (right_x + 38, card3_y + 10))

    sub_mkt = font_small.render("Invest State Treasury cash into foreign sovereign debt to earn passive coupon yields.", True, DIM)
    surface.blit(sub_mkt, (right_x + 16, card3_y + 32))

    # Foreign listings
    from worldview_ui import NATION_COLORS
    other_nations = [n for n in world.get('nations', []) if n.name != active_n.name]
    row_y = card3_y + 52
    for other in other_nations[:3]:
        o_rating, o_yield = isrb.get_market_yield(other, selected_duration, world)
        col = NATION_COLORS.get(other.name, (120, 120, 120))
        
        pygame.draw.rect(surface, (32, 32, 44), (right_x + 14, row_y, col_w - 28, 42), border_radius=4)
        pygame.draw.rect(surface, (55, 55, 75), (right_x + 14, row_y, col_w - 28, 42), 1, border_radius=4)

        # Dot + Nation
        pygame.draw.circle(surface, col, (right_x + 26, row_y + 21), 5)
        n_lbl = font_small.render(f"{other.name} ({o_rating})", True, (255, 255, 255))
        surface.blit(n_lbl, (right_x + 38, row_y + 6))

        y_lbl = font_small.render(f"{selected_duration}t Yield: {o_yield*100:.2f}%/t  •  Coupon: +${500*o_yield:.2f}/t", True, (120, 220, 140))
        surface.blit(y_lbl, (right_x + 38, row_y + 23))

        can_buy = active_n.government.agent.cash >= 500.0
        draw_action_button(surface, (right_x + col_w - 146, row_y + 7, 120, 28), "Buy $500 Bond", font_small, mx, my, disabled=not can_buy, color=(120, 220, 140))
        row_y += 48

    # 4. Active Foreign Reserves Portfolio
    card4_y = card3_y + card3_h + 10
    card4_h = box_h - card3_h - 22
    pygame.draw.rect(surface, CARD_BG, (right_x, card4_y, col_w, card4_h), border_radius=6)
    pygame.draw.rect(surface, (60, 60, 80), (right_x, card4_y, col_w, card4_h), 1, border_radius=6)

    sec_ico = get_icon('treasury', 18)
    surface.blit(sec_ico, (right_x + 14, card4_y + 12))
    res_title = font.render("Active Foreign Reserves Portfolio", True, ACCENT)
    surface.blit(res_title, (right_x + 38, card4_y + 10))

    res_summary = font_small.render(f"Total Foreign Reserves: ${foreign_reserves:,.0f}  •  Passive Revenue: +${passive_income:.2f}/turn", True, (120, 240, 150))
    surface.blit(res_summary, (right_x + 16, card4_y + 34))

    held_bonds = market.get_bonds_held_by(active_n.name)
    h_list_y = card4_y + 56
    if not held_bonds:
        no_h = font_small.render("No foreign sovereign bonds held in reserve. Purchase bonds to earn passive income.", True, DIM)
        surface.blit(no_h, (right_x + 16, h_list_y))
    else:
        for b in held_bonds[:4]:
            turns_left = max(0, b.maturity_turn - world.get('turn', 1))
            hb_txt = font_small.render(f"• {b.issuer_nation} ${b.principal:.0f} #{b.bond_id}: +${b.per_turn_coupon:.2f}/t (Matures T={b.maturity_turn}, {turns_left}t left)", True, (220, 245, 230))
            surface.blit(hb_txt, (right_x + 16, h_list_y + 4))
            h_list_y += 24


# =============================================================================
# Helper Drawing Utilities & Click Dispatchers
# =============================================================================

def draw_action_button(surface, rect, label, font_small, mx, my, disabled=False, active=False, color=None):
    is_hover = rect[0] <= mx <= rect[0] + rect[2] and rect[1] <= my <= rect[1] + rect[3] and not disabled
    if disabled:
        bg = (28, 28, 38)
        border_c = (50, 50, 65)
        txt_c = (80, 80, 100)
    elif active:
        bg = (50, 70, 95)
        border_c = ACCENT
        txt_c = (255, 255, 255)
    elif is_hover:
        bg = BTN_HOVER
        border_c = color or ACCENT
        txt_c = (255, 255, 255)
    else:
        bg = BTN_BG
        border_c = color or BTN_BORDER
        txt_c = color or TEXT

    pygame.draw.rect(surface, bg, rect, border_radius=4)
    pygame.draw.rect(surface, border_c, rect, 1, border_radius=4)
    tsurf = font_small.render(label, True, txt_c)
    surface.blit(tsurf, tsurf.get_rect(center=(rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)))


def actions_tab_hit(pos, box_x, box_y, world):
    """Handle click interactions inside Sovereign Actions Suite."""
    mx, my = pos
    nations = world.get('nations', [])
    active_n = get_active_nation(world)
    t = world.get('turn', 1)
    diplomacy = get_diplomacy()

    # 1. Check Nation Switcher Click: y in [box_y + 48, box_y + 74]
    if box_y + 46 <= my <= box_y + 76:
        from worldview_ui import get_font
        font_small = get_font(11)
        lbl_w = font_small.render("Switch Sovereign Nation:", True, (255, 255, 255)).get_width()
        sx = box_x + 20 + lbl_w + 14
        for n in nations:
            if sx <= mx <= sx + 130:
                world['player_nation_name'] = n.name
                world['selected_nation'] = n
                world['selected_region'] = n.tiles[0] if n.tiles else None
                return True
            sx += 140

    # 2. Check Action Tabs Click: y in [box_y + 84, box_y + 114]
    if box_y + 84 <= my <= box_y + 114:
        sx = box_x + 20
        for tab_id in (1, 2, 3, 4, 5):
            if sx <= mx <= sx + 216:
                world['actions_tab'] = tab_id
                return True
            sx += 226

    active_tab = world.get('actions_tab', 1)
    card_w = (WIDTH - 48) - 40

    # 3. Tab 1 Diplomacy Actions Click Handling
    if active_tab == 1 and active_n:
        other_nations = [n for n in nations if n.name != active_n.name]
        card_y = box_y + 128 + 36
        card_h = 126
        for other in other_nations:
            btn_x1 = box_x + card_w - 510
            btn_x2 = box_x + card_w - 250
            btn_w = 240
            btn_h = 36
            row1_y = card_y + 16
            row2_y = card_y + 64

            has_trade = diplomacy.has_treaty(active_n.name, other.name, TreatyType.TRADE_PACT.value)
            has_nap = diplomacy.has_treaty(active_n.name, other.name, TreatyType.NON_AGGRESSION.value)
            has_alliance = diplomacy.has_treaty(active_n.name, other.name, TreatyType.DEFENSIVE_ALLIANCE.value)
            is_war = diplomacy.are_at_war(active_n.name, other.name)

            # 1. Trade Pact Button (Top Left)
            if btn_x1 <= mx <= btn_x1 + btn_w and row1_y <= my <= row1_y + btn_h:
                if has_trade:
                    res = diplomacy.break_treaty(active_n.name, other.name, TreatyType.TRADE_PACT.value, t=t, reason="Sovereign decision")
                    world['action_feedback'] = (res.get('message', 'Trade pact broken.'), RED, t)
                else:
                    ok, reason = diplomacy.propose_treaty(active_n.name, other.name, TreatyType.TRADE_PACT.value, t=t)
                    world['action_feedback'] = (reason, GREEN if ok else RED, t)
                return True

            # 2. NAP Button (Top Right)
            if btn_x2 <= mx <= btn_x2 + btn_w and row1_y <= my <= row1_y + btn_h:
                if has_nap:
                    res = diplomacy.break_treaty(active_n.name, other.name, TreatyType.NON_AGGRESSION.value, t=t, reason="Sovereign decision")
                    world['action_feedback'] = (res.get('message', 'NAP broken.'), RED, t)
                else:
                    ok, reason = diplomacy.propose_treaty(active_n.name, other.name, TreatyType.NON_AGGRESSION.value, t=t)
                    world['action_feedback'] = (reason, ACCENT if ok else RED, t)
                return True

            # 3. Defensive Alliance Button (Bottom Left)
            if btn_x1 <= mx <= btn_x1 + btn_w and row2_y <= my <= row2_y + btn_h:
                if has_alliance:
                    res = diplomacy.break_treaty(active_n.name, other.name, TreatyType.DEFENSIVE_ALLIANCE.value, t=t, reason="Sovereign decision")
                    world['action_feedback'] = (res.get('message', 'Alliance broken.'), RED, t)
                else:
                    ok, reason = diplomacy.propose_treaty(active_n.name, other.name, TreatyType.DEFENSIVE_ALLIANCE.value, t=t)
                    world['action_feedback'] = (reason, (80, 200, 255) if ok else RED, t)
                return True

            # 4. War / Peace Button (Bottom Right)
            if btn_x2 <= mx <= btn_x2 + btn_w and row2_y <= my <= row2_y + btn_h:
                if is_war:
                    res = diplomacy.sign_peace(active_n.name, other.name, t=t)
                    world['action_feedback'] = (res.get('message', 'Peace signed.'), GREEN if res.get('success') else RED, t)
                else:
                    events = diplomacy.declare_war(active_n.name, other.name, t=t, reason="Sovereign declaration of war")
                    msg = events[0]['message'] if events else f"State of war declared between {active_n.name} and {other.name}."
                    world['action_feedback'] = (msg, RED, t)
                return True

            card_y += card_h + 12

    # 4. Tab 2 Military Actions Click Handling
    elif active_tab == 2 and active_n:
        recruit_bar_y = box_y + 120 + 36
        rec_btn_rect = (box_x + 280, recruit_bar_y + 12, 220, 28)
        if rec_btn_rect[0] <= mx <= rec_btn_rect[0] + rec_btn_rect[2] and rec_btn_rect[1] <= my <= rec_btn_rect[1] + rec_btn_rect[3]:
            pinned_tile = world.get('selected_region')
            tile_name = pinned_tile.name if pinned_tile else (active_n.tiles[0].name if active_n.tiles else None)
            if tile_name:
                intent = RecruitArmyIntent(active_n.name, tile_name, 15, wage=1.0, submitted_turn=t, regime_type=active_n.regime_type)
                active_n.submit_intent(intent, t)
                return True

    # 5. Tab 3 Construction Click Handling
    elif active_tab == 3 and active_n:
        card_y = box_y + 120 + 36
        recipes = ['mountain_pass', 'river_bridge', 'paved_road', 'granary', 'sawmill', 'workshop']
        pinned_tile = world.get('selected_region')
        target_tile = pinned_tile if (pinned_tile and pinned_tile in active_n.tiles) else (active_n.tiles[0] if active_n.tiles else None)
        tile_name = target_tile.name if target_tile else None
        
        for r_key in recipes:
            btn_rect = (box_x + card_w - 220, card_y + 13, 190, 32)
            if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3] and tile_name:
                is_built = any(b.name == r_key for b in getattr(target_tile, 'buildings', [])) if target_tile else False
                active_proj = next((p for p in getattr(target_tile, 'construction_projects', []) if p.recipe.name == r_key and p.status == 'in_progress'), None) if target_tile else None
                if active_proj is None and active_n:
                    active_proj = next((p for p in getattr(active_n, 'construction_projects', []) if p.recipe.name == r_key and p.status == 'in_progress' and p.region == target_tile), None)
                if not is_built and active_proj is None:
                    intent = BuildIntent(active_n.name, tile_name, r_key, submitted_turn=t, regime_type=active_n.regime_type)
                    active_n.submit_intent(intent, t)
                    tiles_by_name = {r.name: r for r in world.get('tiles', [])}
                    nations_by_name = {n.name: n for n in world.get('nations', [])}
                    ok, msg = intent.execute(tiles_by_name, nations_by_name, t)
                    rec = BUILDING_RECIPES.get(r_key)
                    name_str = rec.display_name if rec else r_key
                    if ok:
                        from worldview_engine import ticker_push
                        ticker_push(world, t, 'CONSTRUCT', f"Commissioned {name_str} in {tile_name} (${rec.cost if rec else 0:.0f}).", (245, 180, 50))
                        world['action_feedback'] = (f"Commissioned {name_str} on [{tile_name}]!", GREEN, t)
                    else:
                        world['action_feedback'] = (msg, RED, t)
                    return True
            card_y += 66

    # 6. Tab 4 Innovation & Royal Bounties Click Handling
    elif active_tab == 4 and active_n:
        # Era buttons click check
        card_y_era = box_y + 120 + 34 + 40
        eras = [1, 2, 3, 4]
        era_btn_w = (card_w - 30) // 4
        ex = box_x + 20
        for era_num in eras:
            eb_rect = (ex, card_y_era, era_btn_w, 28)
            if eb_rect[0] <= mx <= eb_rect[0] + eb_rect[2] and eb_rect[1] <= my <= eb_rect[1] + eb_rect[3]:
                world['innovation_era'] = era_num
                return True
            ex += era_btn_w + 10

        # Tech bounty buttons click check
        card_y = box_y + 120 + 34 + 40 + 38
        cur_era = world.get('innovation_era', 1)
        from innovation import get_innovation_system, TECH_CATALOG
        from tile_resources import get_nation_resources
        inno = get_innovation_system()
        discovered = inno.get_discovered_techs(active_n.name)
        accessible_res = get_nation_resources(active_n, world=world)
        era_techs = [t for t in TECH_CATALOG.values() if t.era == cur_era]

        for tech in era_techs:
            tech_id = tech.tech_id
            btn_rect = (box_x + card_w - 230, card_y + 14, 210, 32)
            if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]:
                missing_techs = [t_req for t_req in tech.required_techs if t_req not in discovered]
                missing_res = [r_req for r_req in tech.required_resources if r_req not in accessible_res]
                if tech_id not in discovered and not missing_techs and not missing_res and not any(b.nation_name == active_n.name and b.tech_id == tech_id for b in inno.active_bounties):
                    ok = inno.post_royal_bounty(active_n, tech_id, 300.0, t)
                    if ok:
                        from worldview_engine import ticker_push
                        ticker_push(world, t, 'INNOVATION', f"{active_n.name} posted $300 Royal Bounty for '{tech.name}'.", (80, 200, 255))
                        world['action_feedback'] = (f"Posted $300 Royal Prize for '{tech.name}'!", GREEN, t)
                    else:
                        world['action_feedback'] = ("Insufficient treasury funds to post prize.", RED, t)
                    return True
            card_y += 70

    # 7. Tab 5 Sovereign Debt & ISRB Bonds Click Handling
    elif active_tab == 5 and active_n:
        box_w = WIDTH - 48
        col_w = (box_w - 50) // 2
        left_x = box_x + 20
        right_x = box_x + 30 + col_w
        cur_y = box_y + 128
        selected_duration = world.get('bond_duration_selected', 20)

        from sovereign_bonds import get_bond_market
        market = get_bond_market()
        isrb = market.isrb

        # 7.1. ISRB Influence Actions
        card1_y = cur_y
        btn_w = (col_w - 40) // 3
        bx1 = left_x + 14
        bx2 = bx1 + btn_w + 6
        bx3 = bx2 + btn_w + 6
        btn_y = card1_y + 86

        # Lobby Upgrade ($200)
        if bx1 <= mx <= bx1 + btn_w and btn_y <= my <= btn_y + 28:
            from intents import LobbyRatingUpgradeIntent
            intent = LobbyRatingUpgradeIntent(active_n.name)
            ok, msg = intent.execute({}, {n.name: n for n in nations}, t, world)
            world['action_feedback'] = (msg, GREEN if ok else RED, t)
            return True

        # Audit Rival ($350)
        if bx2 <= mx <= bx2 + btn_w and btn_y <= my <= btn_y + 28:
            other_nations = [n for n in nations if n.name != active_n.name]
            if other_nations:
                target_nation = other_nations[0].name
                from intents import LobbyAdversaryDowngradeIntent
                intent = LobbyAdversaryDowngradeIntent(active_n.name, target_nation_name=target_nation)
                ok, msg = intent.execute({}, {n.name: n for n in nations}, t, world)
                world['action_feedback'] = (msg, GREEN if ok else RED, t)
            return True

        # Acquire Board Seat ($600)
        if bx3 <= mx <= bx3 + btn_w and btn_y <= my <= btn_y + 28:
            from intents import AcquireBoardSeatIntent
            intent = AcquireBoardSeatIntent(active_n.name)
            ok, msg = intent.execute({}, {n.name: n for n in nations}, t, world)
            world['action_feedback'] = (msg, GREEN if ok else RED, t)
            return True

        # 7.2. Domestic Bond Issuance
        card2_y = card1_y + 160 + 10
        # Duration Selectors (20t, 50t, 100t)
        d_w = 90
        dx = left_x + 160
        for d in (20, 50, 100):
            if dx <= mx <= dx + d_w and card2_y + 32 <= my <= card2_y + 56:
                world['bond_duration_selected'] = d
                return True
            dx += d_w + 8

        # Issuance Buttons ($500, $1,000, $2,500)
        iss_y = card2_y + 64
        amounts = [500.0, 1000.0, 2500.0]
        ib_w = (col_w - 40) // 3
        ib_x = left_x + 14
        for amt in amounts:
            if ib_x <= mx <= ib_x + ib_w and iss_y <= my <= iss_y + 30:
                from intents import IssueSovereignBondIntent
                intent = IssueSovereignBondIntent(active_n.name, principal=amt, duration_turns=selected_duration)
                ok, msg = intent.execute({}, {n.name: n for n in nations}, t, world)
                world['action_feedback'] = (msg, GREEN if ok else RED, t)
                return True
            ib_x += ib_w + 6

        # Redeem Early Buttons
        owed_bonds = market.get_bonds_owed_by(active_n.name)
        d_sum_y = iss_y + 58
        list_y = d_sum_y + 26
        for b in owed_bonds[:3]:
            btn_rect = (left_x + col_w - 110, list_y, 96, 20)
            if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]:
                from intents import RedeemBondEarlyIntent
                intent = RedeemBondEarlyIntent(active_n.name, bond_id=b.bond_id)
                ok, msg = intent.execute({}, {n.name: n for n in nations}, t, world)
                world['action_feedback'] = (msg, GREEN if ok else RED, t)
                return True
            list_y += 24

        # 7.3. Buy Foreign Sovereign Bonds
        card3_y = cur_y
        other_nations = [n for n in nations if n.name != active_n.name]
        row_y = card3_y + 52
        for other in other_nations[:3]:
            btn_rect = (right_x + col_w - 146, row_y + 7, 120, 28)
            if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]:
                from intents import BuyForeignBondIntent
                intent = BuyForeignBondIntent(active_n.name, target_nation_name=other.name, principal=500.0, duration_turns=selected_duration)
                ok, msg = intent.execute({}, {n.name: n for n in nations}, t, world)
                world['action_feedback'] = (msg, GREEN if ok else RED, t)
                return True
            row_y += 48

    return False
