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

# Top Bar Action Buttons: (x, y, w, h)
DIPLOMACY_BTN = (MAP_RIGHT - 300, 12, 140, 28)
MILITARY_BTN = (MAP_RIGHT - 445, 12, 135, 28)


def draw_top_bar_action_buttons(surface, world, font_small, mouse_pos=None):
    """Draw top-bar shortcuts for Diplomacy (D) and Military / Command (M)."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    
    # 1. Diplomacy Button
    is_dip_open = world.get('actions_open') and world.get('actions_tab') == 1
    dip_hover = DIPLOMACY_BTN[0] <= mx <= DIPLOMACY_BTN[0] + DIPLOMACY_BTN[2] and DIPLOMACY_BTN[1] <= my <= DIPLOMACY_BTN[1] + DIPLOMACY_BTN[3]
    dip_bg = (75, 75, 100) if is_dip_open else ((60, 60, 80) if dip_hover else (40, 40, 52))
    pygame.draw.rect(surface, dip_bg, DIPLOMACY_BTN, border_radius=5)
    pygame.draw.rect(surface, ACCENT if (dip_hover or is_dip_open) else (90, 90, 110), DIPLOMACY_BTN, 1, border_radius=5)
    dip_txt = font_small.render("Diplomacy (D)", True, (255, 255, 255) if (dip_hover or is_dip_open) else TEXT)
    surface.blit(dip_txt, dip_txt.get_rect(center=(DIPLOMACY_BTN[0] + DIPLOMACY_BTN[2] // 2, DIPLOMACY_BTN[1] + DIPLOMACY_BTN[3] // 2)))

    # 2. Military Button
    is_mil_open = world.get('actions_open') and world.get('actions_tab') == 2
    mil_hover = MILITARY_BTN[0] <= mx <= MILITARY_BTN[0] + MILITARY_BTN[2] and MILITARY_BTN[1] <= my <= MILITARY_BTN[1] + MILITARY_BTN[3]
    mil_bg = (75, 75, 100) if is_mil_open else ((60, 60, 80) if mil_hover else (40, 40, 52))
    pygame.draw.rect(surface, mil_bg, MILITARY_BTN, border_radius=5)
    pygame.draw.rect(surface, ACCENT if (mil_hover or is_mil_open) else (90, 90, 110), MILITARY_BTN, 1, border_radius=5)
    mil_txt = font_small.render("Military (M)", True, (255, 255, 255) if (mil_hover or is_mil_open) else TEXT)
    surface.blit(mil_txt, mil_txt.get_rect(center=(MILITARY_BTN[0] + MILITARY_BTN[2] // 2, MILITARY_BTN[1] + MILITARY_BTN[3] // 2)))


def top_bar_action_hit(pos):
    """Return 'diplomacy', 'military', or None if an action button was clicked."""
    mx, my = pos
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

    # Tabs (Diplomacy, Military, Construction, AI Advisory)
    cur_y = draw_action_tabs(surface, world, box_x, box_y + 84, font_small, mouse_pos)

    active_tab = world.get('actions_tab', 1)
    if active_tab == 1:
        draw_diplomacy_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)
    elif active_tab == 2:
        draw_military_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)
    elif active_tab == 3:
        draw_construction_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)
    elif active_tab == 4:
        draw_ai_advisory_tab(surface, world, box_x, cur_y, box_w, box_h - (cur_y - box_y), font, font_small, mouse_pos)


def get_active_nation(world):
    """Return currently active nation object controlled by player."""
    nations = world.get('nations', [])
    active_name = world.get('player_nation_name')
    if active_name:
        for n in nations:
            if n.name == active_name:
                return n
    pinned = world.get('selected_region')
    if pinned is not None and getattr(pinned, 'owner_nation', None) is not None:
        return pinned.owner_nation
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
    """Draw action tabs: 1. Diplomacy, 2. Military, 3. Construction, 4. AI Advisory."""
    active_tab = world.get('actions_tab', 1)
    tabs = [
        (1, "1. Diplomacy & Treaties (D)"),
        (2, "2. Military & Garrisons (M)"),
        (3, "3. Physical Construction & Intents"),
        (4, "4. AI Sovereign Advisory"),
    ]
    tab_w = 230
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
        start_x += tab_w + 12

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
    card_h = 105

    for other in other_nations:
        rel = diplomacy.get_relation(active_n.name, other.name)
        is_war = diplomacy.are_at_war(active_n.name, other.name)
        has_trade = diplomacy.has_treaty(active_n.name, other.name, TreatyType.TRADE_PACT.value)
        has_nap = diplomacy.has_treaty(active_n.name, other.name, TreatyType.NON_AGGRESSION.value)
        has_alliance = diplomacy.has_treaty(active_n.name, other.name, TreatyType.DEFENSIVE_ALLIANCE.value)

        card_rect = (box_x + 20, card_y, card_w, card_h)
        pygame.draw.rect(surface, CARD_BG, card_rect, border_radius=6)
        pygame.draw.rect(surface, RED if is_war else ((70, 70, 90)), card_rect, 2 if is_war else 1, border_radius=6)

        # Nation Name & Status
        n_col = NATION_COLORS.get(other.name, TEXT)
        n_txt = font.render(f"{other.name} ({other.currency}) — Regime: {other.regime_type}", True, n_col)
        surface.blit(n_txt, (box_x + 36, card_y + 12))

        # Relation readout
        rel_color = GREEN if rel > 0.2 else (RED if rel < -0.2 else TEXT)
        rel_label = "WAR" if is_war else ("ALLIED" if has_alliance else ("FRIENDLY" if rel > 0.3 else ("HOSTILE" if rel < -0.3 else "NEUTRAL")))
        rel_txt = font_small.render(f"Relation: {rel:+.2f} [{rel_label}]", True, rel_color)
        surface.blit(rel_txt, (box_x + 36, card_y + 40))

        # Treaties readout
        treaty_badges = []
        if has_trade:
            treaty_badges.append(("TRADE PACT (50% Tariff Cut)", GREEN))
        if has_nap:
            treaty_badges.append(("NON-AGGRESSION PACT", ACCENT))
        if has_alliance:
            treaty_badges.append(("DEFENSIVE ALLIANCE", (80, 200, 255)))
        if is_war:
            treaty_badges.append(("STATE OF WAR", RED))

        tx = box_x + 36
        for t_label, t_col in treaty_badges:
            t_surf = font_small.render(f"[{t_label}]", True, t_col)
            surface.blit(t_surf, (tx, card_y + 68))
            tx += t_surf.get_width() + 12

        # Action Buttons for this Nation
        bx = box_x + card_w - 530
        btn_w = 120
        btn_h = 28
        by = card_y + 36

        # 1. Trade Pact Button (Click to Propose or Cancel)
        trade_rect = (bx, by, btn_w, btn_h)
        trade_label = "Cancel Trade" if has_trade else "Trade Pact"
        draw_action_button(surface, trade_rect, trade_label, font_small, mx, my,
                           disabled=is_war, active=has_trade, color=GREEN if not has_trade else (100, 220, 140))

        # 2. NAP Button (Click to Propose or Cancel)
        nap_rect = (bx + 130, by, btn_w, btn_h)
        nap_label = "Cancel NAP" if has_nap else "NAP Treaty"
        draw_action_button(surface, nap_rect, nap_label, font_small, mx, my,
                           disabled=is_war, active=has_nap, color=ACCENT if not has_nap else (255, 220, 120))

        # 3. Alliance Button (Click to Propose or Cancel)
        ally_rect = (bx + 260, by, btn_w, btn_h)
        ally_label = "Cancel Ally" if has_alliance else "Def Alliance"
        draw_action_button(surface, ally_rect, ally_label, font_small, mx, my,
                           disabled=is_war, active=has_alliance, color=(80, 200, 255))

        # 4. War / Peace Button (Click to Declare War or Sign Peace)
        war_rect = (bx + 390, by, btn_w, btn_h)
        if is_war:
            draw_action_button(surface, war_rect, "Sign Peace", font_small, mx, my, color=GREEN)
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
    tile_name = pinned_tile.name if pinned_tile else (active_n.tiles[0].name if active_n.tiles else "None")
    is_owned = pinned_tile in active_n.tiles if pinned_tile else True

    header = font.render(f"Physical Construction & Strategic Intents on [{tile_name}] (Treasury: ${treasury['total']:,.2f})", True, TEXT)
    surface.blit(header, (box_x + 20, y))

    card_y = y + 36
    card_w = box_w - 40

    recipes = [
        ('farm', 'Commercial Farm', '$100', '+50% Food Output, +10% Labor'),
        ('lumber_mill', 'Industrial Lumber Mill', '$120', '+50% Wood Output'),
        ('workshop', 'Furniture Workshop', '$150', '+50% Furniture Output'),
        ('granary', 'Provincial Granary', '$80', '+100 Food Storage Capacity'),
    ]

    for r_key, r_name, r_cost, r_desc in recipes:
        recipe_obj = BUILDING_RECIPES.get(r_key)
        cost_val = recipe_obj.cost if recipe_obj else 100.0
        can_afford = treasury['total'] >= cost_val

        card_rect = (box_x + 20, card_y, card_w, 68)
        pygame.draw.rect(surface, CARD_BG, card_rect, border_radius=6)
        pygame.draw.rect(surface, (70, 70, 90), card_rect, 1, border_radius=6)

        t_lbl = font.render(f"{r_name} — Cost: {r_cost}", True, ACCENT)
        surface.blit(t_lbl, (box_x + 36, card_y + 10))

        d_lbl = font_small.render(f"Modifiers: {r_desc}", True, DIM)
        surface.blit(d_lbl, (box_x + 36, card_y + 36))

        btn_rect = (box_x + card_w - 220, card_y + 18, 190, 32)
        draw_action_button(surface, btn_rect, f"Commission ({r_cost})", font_small, mx, my,
                           disabled=not is_owned or not can_afford)

        card_y += 78

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
            pygame.draw.rect(surface, CARD_BG, p_rect, border_radius=4)
            p_txt = font_small.render(
                f"Project {p.project_id}: Building {p.recipe.display_name} in {p.region.name} — Progress: {p.turns_worked}/{p.total_turns} turns (Status: {p.status})",
                True, GREEN if p.status == 'completed' else ACCENT
            )
            surface.blit(p_txt, (box_x + 36, card_y + 12))
            card_y += 48


# =============================================================================
# TAB 4: AI SOVEREIGN ADVISORY
# =============================================================================

def draw_ai_advisory_tab(surface, world, box_x, y, box_w, box_h, font, font_small, mouse_pos=None):
    active_n = get_active_nation(world)
    if not active_n:
        return

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    ai = getattr(active_n, 'ai', None)
    if ai is None:
        ai = NationPolicyAI(active_n)
        active_n.ai = ai

    diplomacy = get_diplomacy()
    header = font.render(f"AI Strategic Advisory & Terrain Analysis for {active_n.name}", True, TEXT)
    surface.blit(header, (box_x + 20, y))

    card_y = y + 36
    card_w = box_w - 40

    # 1. Border Vulnerability Card
    vuln_rect = (box_x + 20, card_y, card_w, 100)
    pygame.draw.rect(surface, CARD_BG, vuln_rect, border_radius=6)
    pygame.draw.rect(surface, (70, 70, 90), vuln_rect, 1, border_radius=6)

    v_hdr = font.render("Border Vulnerability & Threat Assessment:", True, ACCENT)
    surface.blit(v_hdr, (box_x + 36, card_y + 10))

    vy = card_y + 36
    for tile in active_n.tiles:
        v_score, v_reason = ai.evaluate_tile_vulnerability(tile, world.get('nations', []), diplomacy)
        v_col = RED if v_score > 0.5 else (GREEN if v_score == 0.0 else TEXT)
        v_txt = font_small.render(f"Tile [{tile.name}]: {v_reason}", True, v_col)
        surface.blit(v_txt, (box_x + 36, vy))
        vy += 20

    card_y += 114

    # 2. Expansion Opportunities Card
    exp_plan = ai.evaluate_expansion(world.get('tiles', []), world.get('nations', []), diplomacy)
    exp_rect = (box_x + 20, card_y, card_w, 80)
    pygame.draw.rect(surface, CARD_BG, exp_rect, border_radius=6)
    pygame.draw.rect(surface, (70, 70, 90), exp_rect, 1, border_radius=6)

    e_hdr = font.render("Top AI Expansion Recommendation:", True, ACCENT)
    surface.blit(e_hdr, (box_x + 36, card_y + 10))

    if exp_plan:
        e_txt = font_small.render(f"Recommended Target: [{exp_plan['tile'].name}] ({exp_plan['reason']}) — Score: {exp_plan['score']:.1f}", True, GREEN)
    else:
        e_txt = font_small.render("No adjacent expansion targets currently meet profitability/safety thresholds.", True, DIM)
    surface.blit(e_txt, (box_x + 36, card_y + 40))


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
    if box_y + 48 <= my <= box_y + 74:
        sx = box_x + 20 + 200
        for n in nations:
            if sx <= mx <= sx + 130:
                world['player_nation_name'] = n.name
                world['selected_region'] = n.tiles[0] if n.tiles else None
                return True
            sx += 140

    # 2. Check Action Tabs Click: y in [box_y + 84, box_y + 114]
    if box_y + 84 <= my <= box_y + 114:
        sx = box_x + 20
        for tab_id in (1, 2, 3, 4):
            if sx <= mx <= sx + 230:
                world['actions_tab'] = tab_id
                return True
            sx += 242

    active_tab = world.get('actions_tab', 1)
    card_w = (WIDTH - 48) - 40

    # 3. Tab 1 Diplomacy Actions Click Handling
    if active_tab == 1 and active_n:
        other_nations = [n for n in nations if n.name != active_n.name]
        card_y = box_y + 128 + 36
        card_h = 105
        for other in other_nations:
            by = card_y + 36
            bx = box_x + card_w - 530
            btn_w = 120
            btn_h = 28

            has_trade = diplomacy.has_treaty(active_n.name, other.name, TreatyType.TRADE_PACT.value)
            has_nap = diplomacy.has_treaty(active_n.name, other.name, TreatyType.NON_AGGRESSION.value)
            has_alliance = diplomacy.has_treaty(active_n.name, other.name, TreatyType.DEFENSIVE_ALLIANCE.value)
            is_war = diplomacy.are_at_war(active_n.name, other.name)

            # 1. Trade Pact
            if bx <= mx <= bx + btn_w and by <= my <= by + btn_h:
                if has_trade:
                    res = diplomacy.break_treaty(active_n.name, other.name, TreatyType.TRADE_PACT.value, t=t, reason="Sovereign decision")
                    world['action_feedback'] = (res.get('message', 'Trade pact broken.'), RED, t)
                else:
                    ok, reason = diplomacy.propose_treaty(active_n.name, other.name, TreatyType.TRADE_PACT.value, t=t)
                    world['action_feedback'] = (reason, GREEN if ok else RED, t)
                return True

            # 2. NAP
            if bx + 130 <= mx <= bx + 130 + btn_w and by <= my <= by + btn_h:
                if has_nap:
                    res = diplomacy.break_treaty(active_n.name, other.name, TreatyType.NON_AGGRESSION.value, t=t, reason="Sovereign decision")
                    world['action_feedback'] = (res.get('message', 'NAP broken.'), RED, t)
                else:
                    ok, reason = diplomacy.propose_treaty(active_n.name, other.name, TreatyType.NON_AGGRESSION.value, t=t)
                    world['action_feedback'] = (reason, ACCENT if ok else RED, t)
                return True

            # 3. Defensive Alliance
            if bx + 260 <= mx <= bx + 260 + btn_w and by <= my <= by + btn_h:
                if has_alliance:
                    res = diplomacy.break_treaty(active_n.name, other.name, TreatyType.DEFENSIVE_ALLIANCE.value, t=t, reason="Sovereign decision")
                    world['action_feedback'] = (res.get('message', 'Alliance broken.'), RED, t)
                else:
                    ok, reason = diplomacy.propose_treaty(active_n.name, other.name, TreatyType.DEFENSIVE_ALLIANCE.value, t=t)
                    world['action_feedback'] = (reason, (80, 200, 255) if ok else RED, t)
                return True

            # 4. War / Peace
            if bx + 390 <= mx <= bx + 390 + btn_w and by <= my <= by + btn_h:
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
        recipes = ['farm', 'lumber_mill', 'workshop', 'granary']
        pinned_tile = world.get('selected_region')
        tile_name = pinned_tile.name if pinned_tile else (active_n.tiles[0].name if active_n.tiles else None)
        
        for r_key in recipes:
            btn_rect = (box_x + card_w - 220, card_y + 18, 190, 32)
            if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3] and tile_name:
                intent = BuildIntent(active_n.name, tile_name, r_key, submitted_turn=t, regime_type=active_n.regime_type)
                active_n.submit_intent(intent, t)
                return True
            card_y += 78

    return False
