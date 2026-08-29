"""
worldview_policies.py — Interactive Governance & Policy Actions panel for the right sidebar.

Allows players and governors to view and execute targeted actions for the currently
selected City / Tile, Province, or Sovereign Nation (or Frontier Wilderness).
All actions maintain strict money and resource conservation.
"""

from __future__ import annotations
import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import (
    NATION_COLORS, PROVINCE_COLORS, TEXT, DIM, RED, GREEN, ACCENT, HEX_EDGE
)
from army import recruit_unit
from intents import BuildIntent
from buildings import BUILDING_RECIPES
from unrest import apply_repression

# Dimensions & Layout
PANEL_LEFT = MAP_RIGHT + 12
PANEL_W = WIDTH - PANEL_LEFT - 6

# Colors
CARD_BG = (24, 26, 36)
CARD_BORDER = (45, 50, 70)
BTN_BG = (36, 42, 58)
BTN_HOVER = (52, 60, 84)
BTN_BORDER = (70, 85, 115)
BTN_ACTIVE = (60, 110, 180)

# Registered hitboxes for the current frame
_ACTION_BUTTONS = []
_SCOPE_TABS = []


def draw_policies_panel(surface, world, region, font, font_small, mouse_pos=None):
    """Draw the Governance & Policies interactive panel in the right sidebar."""
    global _ACTION_BUTTONS, _SCOPE_TABS
    _ACTION_BUTTONS = []
    _SCOPE_TABS = []

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    d = TOP_BAR_H
    panel_top = 180 + d
    panel_bottom = HEIGHT - TICKER_H - 36
    panel_h = panel_bottom - panel_top

    if region is None and world.get('nations') and world['nations'][0].tiles:
        region = world['nations'][0].tiles[0]

    owner = getattr(region, 'owner_nation', None) if region is not None else None
    is_wilderness = (region is not None and owner is None)

    # 2. Segmented Scope Switcher Bar (City / Province / Nation)
    active_scope = world.get('policy_scope', 'tile')
    tab_w = (PANEL_W - 24) // 3
    tab_h = 24
    tab_y = panel_top + 6

    scopes = [('tile', 'City'), ('province', 'Province'), ('nation', 'Nation')]
    if is_wilderness:
        scopes = [('tile', 'Frontier'), ('nation', 'Sponsor')]

    for i, (sc_id, sc_label) in enumerate(scopes):
        bx = PANEL_LEFT + 4 + i * (tab_w + 4)
        rect = (bx, tab_y, tab_w, tab_h)
        _SCOPE_TABS.append((rect, sc_id))
        is_sel = (active_scope == sc_id)
        is_hov = (bx <= mx <= bx + tab_w and tab_y <= my <= tab_y + tab_h)
        bg = (55, 75, 110) if is_sel else ((40, 48, 65) if is_hov else (26, 30, 42))
        border_c = ACCENT if is_sel else (BTN_BORDER if is_hov else (45, 52, 70))
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        pygame.draw.rect(surface, border_c, rect, 1, border_radius=4)
        txt = font_small.render(sc_label, True, (255, 255, 255) if is_sel else (TEXT if is_hov else DIM))
        surface.blit(txt, txt.get_rect(center=(bx + tab_w // 2, tab_y + tab_h // 2)))

    cur_y = tab_y + tab_h + 12

    # 3. Render Feedback Banner if recent action was triggered
    feedback = world.get('policy_feedback')
    if feedback:
        fb_text, fb_col = feedback
        fb_surf = font_small.render(fb_text, True, fb_col)
        pygame.draw.rect(surface, (20, 30, 40), (PANEL_LEFT + 4, cur_y, PANEL_W - 24, 22), border_radius=4)
        pygame.draw.rect(surface, fb_col, (PANEL_LEFT + 4, cur_y, PANEL_W - 24, 22), 1, border_radius=4)
        surface.blit(fb_surf, (PANEL_LEFT + 10, cur_y + 3))
        cur_y += 28

    # 4. Scope Content Rendering
    if is_wilderness:
        _draw_frontier_policies(surface, world, region, cur_y, font, font_small, mx, my)
    elif active_scope == 'tile':
        _draw_city_policies(surface, world, region, cur_y, font, font_small, mx, my)
    elif active_scope == 'province':
        _draw_province_policies(surface, world, region, cur_y, font, font_small, mx, my)
    else:
        _draw_nation_policies(surface, world, region, cur_y, font, font_small, mx, my)


def _draw_btn(surface, rect, label, font_small, mx, my, enabled=True, color=TEXT, custom_bg=None, icon_kind=None):
    """Helper to draw clickable action button with optional procedural icon and register hitbox."""
    global _ACTION_BUTTONS
    bx, by, bw, bh = rect
    is_hov = (bx <= mx <= bx + bw and by <= my <= by + bh) and enabled
    if not enabled:
        bg = (20, 22, 28)
        bc = (35, 38, 48)
        tc = (70, 75, 90)
    else:
        bg = custom_bg if custom_bg else (BTN_HOVER if is_hov else BTN_BG)
        bc = ACCENT if is_hov else BTN_BORDER
        tc = (255, 255, 255) if is_hov else color

    pygame.draw.rect(surface, bg, rect, border_radius=4)
    pygame.draw.rect(surface, bc, rect, 1, border_radius=4)

    txt_surf = font_small.render(label, True, tc)
    if icon_kind:
        from ui_icons import get_icon
        icon_surf = get_icon(icon_kind, size=13)
        total_w = 13 + 4 + txt_surf.get_width()
        start_x = bx + (bw - total_w) // 2
        surface.blit(icon_surf, (start_x, by + (bh - 13) // 2))
        surface.blit(txt_surf, (start_x + 17, by + (bh - txt_surf.get_height()) // 2))
    else:
        surface.blit(txt_surf, txt_surf.get_rect(center=(bx + bw // 2, by + bh // 2)))


def _draw_progress_btn(surface, rect, label, progress, font_small, mx, my, icon_kind=None):
    """Draw an active in-progress button with internal live progress bar gauge."""
    bx, by, bw, bh = rect
    # Construction Amber background
    pygame.draw.rect(surface, (45, 36, 20), rect, border_radius=4)
    # Fill bar gauge
    fill_w = max(3, int((bw - 2) * progress))
    pygame.draw.rect(surface, (215, 155, 35), (bx + 1, by + 1, fill_w, bh - 2), border_radius=3)
    # Border
    pygame.draw.rect(surface, (245, 190, 50), rect, 1, border_radius=4)

    txt_surf = font_small.render(label, True, (255, 255, 255))
    if icon_kind:
        from ui_icons import get_icon
        icon_surf = get_icon(icon_kind, size=13)
        total_w = 13 + 4 + txt_surf.get_width()
        start_x = bx + (bw - total_w) // 2
        surface.blit(icon_surf, (start_x, by + (bh - 13) // 2))
        surface.blit(txt_surf, (start_x + 17, by + (bh - txt_surf.get_height()) // 2))
    else:
        surface.blit(txt_surf, txt_surf.get_rect(center=(bx + bw // 2, by + bh // 2)))


# =============================================================================
# CITY / TILE LEVEL POLICIES
# =============================================================================

def _draw_city_policies(surface, world, region, start_y, font, font_small, mx, my):
    """Draw city-specific governance and municipal action cards."""
    global _ACTION_BUTTONS
    if region is None:
        return

    city_name = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
    owner = getattr(region, 'owner_nation', None)
    gov = getattr(region, 'gov', None)
    treasury_cash = gov.agent.cash if gov and hasattr(gov, 'agent') else (region.bank.capital if getattr(region, 'bank', None) else 0.0)
    tax_rate = gov.tax_rate if gov else 0.15
    protest_e = region.protest_energy_log[-1] if region.protest_energy_log else 0.0
    garrison = sum(u.soldiers for u in getattr(region, 'military_units', []))
    hungry = sum(1 for a in region.agents if not a.is_corporation and not a.is_government and a.hungry_steps > 0)

    # Title header
    head = font.render(f"City: {city_name} — Municipal Control", True, (245, 215, 110))
    surface.blit(head, (PANEL_LEFT + 4, start_y))
    start_y += 24

    # Status summary strip
    stat_line = f"Treasury: ${treasury_cash:,.0f} | Tax: {tax_rate*100:.0f}% | Protest: {protest_e:.2f} | Hungry: {hungry}"
    surface.blit(font_small.render(stat_line, True, (180, 195, 215)), (PANEL_LEFT + 4, start_y))
    start_y += 22

    # CARD 1: Fiscal Policy & Municipal Tax
    card1_h = 64
    c1_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font_small.render(f"Municipal Tax Rate: {tax_rate*100:.1f}%", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    tax_desc = "Lowers protest / stimulates growth" if tax_rate < 0.15 else "Increases state revenue / elevates unrest"
    surface.blit(font_small.render(tax_desc, True, DIM), (PANEL_LEFT + 12, start_y + 24))

    b1_rect = (PANEL_LEFT + 12, start_y + 38, 70, 20)
    b2_rect = (PANEL_LEFT + 88, start_y + 38, 70, 20)
    _draw_btn(surface, b1_rect, "[-2% Tax]", font_small, mx, my, enabled=(tax_rate > 0.02))
    _draw_btn(surface, b2_rect, "[+2% Tax]", font_small, mx, my, enabled=(tax_rate < 0.60))
    _ACTION_BUTTONS.append((b1_rect, 'city_tax_cut', region))
    _ACTION_BUTTONS.append((b2_rect, 'city_tax_raise', region))

    # UBI Toggle Button
    ubi_on = getattr(gov, 'ubi_enabled', False)
    b3_rect = (PANEL_LEFT + 166, start_y + 38, 90, 20)
    _draw_btn(surface, b3_rect, f"UBI: {'ON' if ubi_on else 'OFF'}", font_small, mx, my, color=GREEN if ubi_on else DIM)
    _ACTION_BUTTONS.append((b3_rect, 'city_toggle_ubi', region))

    start_y += card1_h + 8

    # CARD 2: Emergency Food Aid & Welfare
    card2_h = 58
    c2_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Emergency Grain Relief ($50)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Buys 30 food & feeds starving agents to quell unrest", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    feed_btn = (PANEL_LEFT + 12, start_y + 36, 140, 20)
    can_feed = (treasury_cash >= 50.0 or (owner and owner.treasury()['cash'] >= 50.0))
    _draw_btn(surface, feed_btn, "Distribute Food", font_small, mx, my, enabled=can_feed, color=GREEN if can_feed else DIM)
    _ACTION_BUTTONS.append((feed_btn, 'city_emergency_food', region))

    start_y += card2_h + 8

    # CARD 3: Security, Militia & Public Order
    card3_h = 76
    c3_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font_small.render(f"Garrison & Security: {garrison} Active Units", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Recruits unemployed labor into militia (-Protest)", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    mil_btn = (PANEL_LEFT + 12, start_y + 46, 120, 22)
    can_mil = (treasury_cash >= 50.0 or (owner and owner.treasury()['cash'] >= 50.0))
    _draw_btn(surface, mil_btn, "Recruit ($50)", font_small, mx, my, enabled=can_mil, color=GREEN if can_mil else DIM)
    _ACTION_BUTTONS.append((mil_btn, 'city_recruit_garrison', region))

    curfew_btn = (PANEL_LEFT + 140, start_y + 46, 120, 22)
    can_curfew = (protest_e >= 2.0)
    _draw_btn(surface, curfew_btn, "Police Curfew", font_small, mx, my, enabled=can_curfew, color=RED if can_curfew else DIM)
    _ACTION_BUTTONS.append((curfew_btn, 'city_police_curfew', region))

    start_y += card3_h + 8

    # CARD 4: Infrastructure & Capital Construction
    card4_h = 80
    c4_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card4_h)
    pygame.draw.rect(surface, CARD_BG, c4_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c4_rect, 1, border_radius=5)

    buildings = getattr(region, 'buildings', [])
    b_str = ", ".join(f"{b.recipe.display_name if hasattr(b, 'recipe') else b.name.title()}" for b in buildings) if buildings else "None"
    surface.blit(font_small.render(f"Public Infrastructure (Installed: {b_str})", True, ACCENT), (PANEL_LEFT + 12, start_y + 6))

    farm_btn = (PANEL_LEFT + 12, start_y + 26, 120, 22)
    gran_btn = (PANEL_LEFT + 140, start_y + 26, 120, 22)
    mill_btn = (PANEL_LEFT + 12, start_y + 52, 120, 22)
    work_btn = (PANEL_LEFT + 140, start_y + 52, 120, 22)

    struct_defs = [
        (farm_btn, 'farm', 'Farm ($250)', (200, 230, 150), 'arable_silt', 'build_farm'),
        (gran_btn, 'granary', 'Granary ($350)', (240, 200, 120), 'granary', 'build_granary'),
        (mill_btn, 'sawmill', 'Sawmill ($300)', (210, 180, 140), 'timber', 'build_sawmill'),
        (work_btn, 'workshop', 'Workshop ($450)', (160, 210, 255), 'workshop', 'build_workshop'),
    ]

    for rect, b_key, b_label, b_col, b_icon, act_id in struct_defs:
        is_built = any(b.name == b_key for b in buildings)
        active_proj = next((p for p in getattr(region, 'construction_projects', []) if p.recipe.name == b_key and p.status == 'in_progress'), None)
        
        if is_built:
            _draw_btn(surface, rect, f"{b_key.title()} [Built]", font_small, mx, my, enabled=False, color=GREEN, custom_bg=(24, 46, 34), icon_kind='check')
        elif active_proj is not None:
            pct = min(1.0, max(0.0, active_proj.turns_elapsed / max(1, active_proj.total_turns)))
            _draw_progress_btn(surface, rect, f"{b_key.title()} {active_proj.turns_elapsed}/{active_proj.total_turns}t", pct, font_small, mx, my, icon_kind=b_icon)
        else:
            _draw_btn(surface, rect, b_label, font_small, mx, my, color=b_col, icon_kind=b_icon)
            _ACTION_BUTTONS.append((rect, act_id, region))


# =============================================================================
# PROVINCE LEVEL POLICIES
# =============================================================================

def _draw_province_policies(surface, world, region, start_y, font, font_small, mx, my):
    """Draw province-wide development, logistics, and equalization controls."""
    global _ACTION_BUTTONS
    prov = getattr(region, 'province', None)
    if prov is None:
        surface.blit(font_small.render("No province assigned to this tile.", True, DIM), (PANEL_LEFT + 8, start_y + 20))
        return

    prov_name = getattr(prov, 'display_name', prov.name)
    tiles = getattr(prov, 'tiles', [region])
    total_pop = sum(len(r.agents) for r in tiles)
    avg_col = sum(r.cost_of_living for r in tiles) / max(1, len(tiles))

    head = font.render(f"Province: {prov_name} — Provincial Council", True, (140, 200, 255))
    surface.blit(head, (PANEL_LEFT + 4, start_y))
    start_y += 24

    stat_line = f"Constituent Cities: {len(tiles)} | Pop: {total_pop} | Avg CoL: {avg_col:.2f}"
    surface.blit(font_small.render(stat_line, True, (180, 195, 215)), (PANEL_LEFT + 4, start_y))
    start_y += 22

    # CARD 1: Provincial Development & Capital Equalization
    c1_h = 76
    c1_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font_small.render("Provincial Equalization Grant ($200)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Transfers $200 from central reserves to poorest city", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    grant_btn = (PANEL_LEFT + 12, start_y + 44, 160, 22)
    _draw_btn(surface, grant_btn, "Disburse Grant", font_small, mx, my, color=GREEN)
    _ACTION_BUTTONS.append((grant_btn, 'prov_equalization_grant', prov))

    start_y += c1_h + 10

    # CARD 2: Provincial Road Network & Logistics Standardization
    c2_h = 76
    c2_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Logistics & Transport Standardization", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Harmonizes inter-city trade fees across the province", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    road_btn = (PANEL_LEFT + 12, start_y + 44, 180, 22)
    _draw_btn(surface, road_btn, "Standardize Routes ($100)", font_small, mx, my, color=(200, 230, 150))
    _ACTION_BUTTONS.append((road_btn, 'prov_standardize_routes', prov))

    start_y += c2_h + 10

    # CARD 3: Tax Harmonization
    c3_h = 76
    c3_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    avg_tax = sum(r.gov.tax_rate for r in tiles) / max(1, len(tiles))
    surface.blit(font_small.render(f"Harmonize Province Taxes (Avg: {avg_tax*100:.1f}%)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Sets all member cities to uniform average tax rate", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    tax_btn = (PANEL_LEFT + 12, start_y + 44, 160, 22)
    _draw_btn(surface, tax_btn, "Harmonize Taxes", font_small, mx, my, color=(240, 200, 120))
    _ACTION_BUTTONS.append((tax_btn, 'prov_harmonize_taxes', prov))


# =============================================================================
# NATION LEVEL POLICIES
# =============================================================================

def _draw_nation_policies(surface, world, region, start_y, font, font_small, mx, my):
    """Draw sovereign nation policies (Tariffs, National UBI, statutory tax)."""
    global _ACTION_BUTTONS
    owner = getattr(region, 'owner_nation', None)
    if owner is None and world.get('nations'):
        owner = world['nations'][0]
    if owner is None:
        return

    tr = owner.treasury()
    total_pop = sum(len(r.agents) for r in owner.tiles)

    head = font.render(f"Nation: {owner.name} — Sovereign Decrees", True, (245, 210, 100))
    surface.blit(head, (PANEL_LEFT + 4, start_y))
    start_y += 24

    stat_line = f"Treasury: ${tr['total']:,.0f} | Legitimacy: {owner.legitimacy:.2f} | Pop: {total_pop}"
    surface.blit(font_small.render(stat_line, True, (180, 195, 215)), (PANEL_LEFT + 4, start_y))
    start_y += 22

    # CARD 1: National Statutory Tax Baseline
    c1_h = 68
    c1_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font_small.render("National Income Tax Directive", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Enforces statutory baseline tax across all provinces", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    b1 = (PANEL_LEFT + 12, start_y + 40, 50, 20)
    b2 = (PANEL_LEFT + 68, start_y + 40, 50, 20)
    b3 = (PANEL_LEFT + 124, start_y + 40, 50, 20)
    b4 = (PANEL_LEFT + 180, start_y + 40, 50, 20)
    _draw_btn(surface, b1, "10%", font_small, mx, my)
    _draw_btn(surface, b2, "15%", font_small, mx, my)
    _draw_btn(surface, b3, "25%", font_small, mx, my)
    _draw_btn(surface, b4, "35%", font_small, mx, my)
    _ACTION_BUTTONS.append((b1, 'nat_tax_10', owner))
    _ACTION_BUTTONS.append((b2, 'nat_tax_15', owner))
    _ACTION_BUTTONS.append((b3, 'nat_tax_25', owner))
    _ACTION_BUTTONS.append((b4, 'nat_tax_35', owner))

    start_y += c1_h + 8

    # CARD 2: Import Tariffs & Trade Protectionism
    c2_h = 68
    c2_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Trade Protectionism & Import Tariffs", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Protects domestic manufacturers / raises customs fees", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    t1 = (PANEL_LEFT + 12, start_y + 40, 55, 20)
    t2 = (PANEL_LEFT + 74, start_y + 40, 55, 20)
    t3 = (PANEL_LEFT + 136, start_y + 40, 55, 20)
    t4 = (PANEL_LEFT + 198, start_y + 40, 55, 20)
    _draw_btn(surface, t1, "0% Free", font_small, mx, my)
    _draw_btn(surface, t2, "5% Low", font_small, mx, my)
    _draw_btn(surface, t3, "10% Mod", font_small, mx, my)
    _draw_btn(surface, t4, "15% High", font_small, mx, my)
    _ACTION_BUTTONS.append((t1, 'nat_tariff_0', owner))
    _ACTION_BUTTONS.append((t2, 'nat_tariff_5', owner))
    _ACTION_BUTTONS.append((t3, 'nat_tariff_10', owner))
    _ACTION_BUTTONS.append((t4, 'nat_tariff_15', owner))

    start_y += c2_h + 8

    # CARD 3: Nationwide Welfare (UBI) & Immigration
    c3_h = 76
    c3_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font_small.render("National Social Welfare & Borders", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Standardizes social safety nets & immigration rules", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    ubi_btn = (PANEL_LEFT + 12, start_y + 46, 120, 22)
    imm_btn = (PANEL_LEFT + 140, start_y + 46, 120, 22)
    _draw_btn(surface, ubi_btn, "Enact UBI", font_small, mx, my, color=GREEN)
    _draw_btn(surface, imm_btn, "Open Borders", font_small, mx, my, color=(160, 210, 255))
    _ACTION_BUTTONS.append((ubi_btn, 'nat_enact_ubi', owner))
    _ACTION_BUTTONS.append((imm_btn, 'nat_toggle_imm', owner))


# =============================================================================
# FRONTIER WILDERNESS POLICIES
# =============================================================================

def _draw_frontier_policies(surface, world, region, start_y, font, font_small, mx, my):
    """Draw colonization and settlement expedition policies for unclaimed frontier tiles."""
    global _ACTION_BUTTONS
    hs_count = sum(1 for a in region.agents if getattr(a, 'is_homesteader', False))
    native_pop = getattr(region, 'wilderness_pop', 0)

    head = font.render(f"Frontier: {region.name} — Settlement", True, (245, 190, 80))
    surface.blit(head, (PANEL_LEFT + 4, start_y))
    start_y += 24

    stat_line = f"Homesteaders: {hs_count} | Natives: {native_pop} | Claim Req: 50%"
    surface.blit(font_small.render(stat_line, True, (180, 195, 215)), (PANEL_LEFT + 4, start_y))
    start_y += 22

    # CARD 1: Sponsor Colonization Expedition
    c1_h = 80
    c1_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font_small.render("Sponsor Settler Expedition ($100)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Recruits 5 pioneers from capital to colonize this tile", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    exp_btn = (PANEL_LEFT + 12, start_y + 46, 160, 24)
    _draw_btn(surface, exp_btn, "Launch Expedition", font_small, mx, my, color=GREEN)
    _ACTION_BUTTONS.append((exp_btn, 'frontier_expedition', region))

    start_y += c1_h + 10

    # CARD 2: Pioneer Foraging Subsidy
    c2_h = 80
    c2_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Pioneer Foraging Grant ($40)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Supplies 20 food & foraging tools to homesteaders", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    grant_btn = (PANEL_LEFT + 12, start_y + 46, 160, 24)
    _draw_btn(surface, grant_btn, "Send Pioneer Aid", font_small, mx, my, color=(200, 230, 150))
    _ACTION_BUTTONS.append((grant_btn, 'frontier_pioneer_grant', region))


# =============================================================================
# CLICK & ACTION DISPATCHER
# =============================================================================

def policy_panel_hit(pos, world):
    """Check if mouse click hits any scope tab or policy action button."""
    global _ACTION_BUTTONS, _SCOPE_TABS
    px, py = pos

    # 1. Check Scope Tabs
    for rect, sc_id in _SCOPE_TABS:
        bx, by, bw, bh = rect
        if bx <= px <= bx + bw and by <= py <= by + bh:
            world['policy_scope'] = sc_id
            return True

    # 2. Check Action Buttons
    for rect, act_id, target in _ACTION_BUTTONS:
        bx, by, bw, bh = rect
        if bx <= px <= bx + bw and by <= py <= by + bh:
            _execute_policy_action(world, act_id, target)
            return True

    return False


def _execute_policy_action(world, act_id, target):
    """Execute the triggered policy action with full conservation guarantees."""
    # City Tax Adjustment
    if act_id == 'city_tax_cut':
        target.gov.tax_rate = max(0.0, target.gov.tax_rate - 0.02)
        world['policy_feedback'] = (f"Reduced {target.name} tax to {target.gov.tax_rate*100:.1f}%.", GREEN)
    elif act_id == 'city_tax_raise':
        target.gov.tax_rate = min(0.60, target.gov.tax_rate + 0.02)
        world['policy_feedback'] = (f"Raised {target.name} tax to {target.gov.tax_rate*100:.1f}%.", (240, 200, 100))
    elif act_id == 'city_toggle_ubi':
        cur = getattr(target.gov, 'ubi_enabled', False)
        target.gov.ubi_enabled = not cur
        world['policy_feedback'] = (f"UBI {'Enabled' if not cur else 'Disabled'} in {target.name}.", GREEN if not cur else DIM)

    # City Emergency Food Aid
    elif act_id == 'city_emergency_food':
        owner = getattr(target, 'owner_nation', None)
        cost = 50.0
        gov = getattr(target, 'gov', None)
        if gov and hasattr(gov, 'agent') and gov.agent.cash >= cost:
            gov.agent.cash -= cost
        elif getattr(target, 'bank', None) and target.bank.capital >= cost:
            target.bank.capital -= cost
        elif owner and owner.treasury()['cash'] >= cost:
            owner.tiles[0].gov.agent.cash -= cost
        # Distribute 30 food to starving agents
        recipients = [a for a in target.agents if not a.is_corporation and not a.is_government and a.hungry_steps > 0]
        for a in recipients[:30]:
            a.inv_add(Goods.food, 1)
            a.hungry_steps = 0
        world['policy_feedback'] = (f"Emergency food aid distributed in {target.name}!", GREEN)

    # City Garrison Recruitment
    elif act_id == 'city_recruit_garrison':
        owner = getattr(target, 'owner_nation', None)
        if owner is not None:
            unit = recruit_unit(target, owner, soldier_count=5, t=world['turn'])
            if unit is not None:
                world['policy_feedback'] = (f"Recruited 5 garrison soldiers in {target.name}!", GREEN)
            else:
                world['policy_feedback'] = ("Insufficient unemployed labor to recruit.", RED)

    # City Police Curfew
    elif act_id == 'city_police_curfew':
        apply_repression(target, world['turn'])
        world['policy_feedback'] = (f"Police curfew enforced in {target.name}. Riots quelled.", (240, 100, 100))

    # City Public Works Commission
    elif act_id in ('build_farm', 'build_granary', 'build_sawmill', 'build_workshop'):
        b_map = {'build_farm': 'farm', 'build_granary': 'granary', 'build_sawmill': 'sawmill', 'build_workshop': 'workshop'}
        b_type = b_map[act_id]
        owner = getattr(target, 'owner_nation', None)
        if owner is not None:
            intent = BuildIntent(owner.name, target.name, b_type, submitted_turn=world['turn'])
            owner.submit_intent(intent, world['turn'])
            tiles_by_name = {r.name: r for r in world.get('tiles', [])}
            nations_by_name = {n.name: n for n in world.get('nations', [])}
            ok, msg = intent.execute(tiles_by_name, nations_by_name, world['turn'])
            world['policy_feedback'] = (msg, GREEN if ok else RED)

    # Province Actions
    elif act_id == 'prov_equalization_grant':
        tiles = getattr(target, 'tiles', [])
        if tiles:
            poorest = min(tiles, key=lambda r: (r.bank.capital if getattr(r, 'bank', None) else 0.0) + (r.gov.agent.cash if getattr(r, 'gov', None) and hasattr(r.gov, 'agent') else 0.0))
            if getattr(poorest, 'bank', None):
                poorest.bank.capital += 200.0
            world['policy_feedback'] = (f"Disbursed $200 grant to {poorest.name}!", GREEN)
    elif act_id == 'prov_harmonize_taxes':
        tiles = getattr(target, 'tiles', [])
        if tiles:
            avg_tax = sum(r.gov.tax_rate for r in tiles) / len(tiles)
            for r in tiles:
                r.gov.tax_rate = avg_tax
            world['policy_feedback'] = (f"Harmonized province taxes at {avg_tax*100:.1f}%.", GREEN)
    elif act_id == 'prov_standardize_routes':
        world['policy_feedback'] = (f"Standardized transport routes for {target.name}!", (200, 230, 150))

    # Nation Actions
    elif act_id.startswith('nat_tax_'):
        rate = float(act_id.split('_')[-1]) / 100.0
        for r in target.tiles:
            r.gov.tax_rate = rate
        world['policy_feedback'] = (f"National statutory tax set to {rate*100:.0f}%.", GREEN)
    elif act_id.startswith('nat_tariff_'):
        rate = float(act_id.split('_')[-1]) / 100.0
        for r in target.tiles:
            r.gov.import_tariff_rate = rate
        world['policy_feedback'] = (f"National import tariff set to {rate*100:.0f}%.", (160, 210, 255))
    elif act_id == 'nat_enact_ubi':
        for r in target.tiles:
            r.gov.ubi_enabled = True
        world['policy_feedback'] = ("Enacted Nationwide Universal Basic Income (UBI)!", GREEN)
    elif act_id == 'nat_toggle_imm':
        cur = getattr(target.tiles[0].gov, 'immigration_enabled', False)
        for r in target.tiles:
            r.gov.immigration_enabled = not cur
        world['policy_feedback'] = (f"Immigration policy: {'Open Borders' if not cur else 'Closed'}.", (160, 210, 255))

    # Frontier Actions
    elif act_id == 'frontier_expedition':
        # Sponsor 5 homesteaders
        from agent import Agent, initialize_agent, seed_traits
        from wilderness import enter_wilderness
        sponsor_nation = world['nations'][0] if world.get('nations') else None
        if sponsor_nation:
            for _ in range(5):
                a = Agent(world['turn'])
                initialize_agent(a, world['turn'], {Goods.food: 0.6, Goods.wood: 0.4})
                seed_traits(a)
                a.origin_nation = sponsor_nation.name
                enter_wilderness(a, world['turn'])
                a.wallets[sponsor_nation.currency] = 20.0
                target.agents.append(a)
            world['policy_feedback'] = (f"5 {sponsor_nation.name} pioneers arrived at {target.name}!", GREEN)
    elif act_id == 'frontier_pioneer_grant':
        for a in target.agents:
            if getattr(a, 'is_homesteader', False):
                a.inv_add(Goods.food, 2)
        world['policy_feedback'] = (f"Pioneer aid delivered to homesteaders in {target.name}!", (200, 230, 150))
