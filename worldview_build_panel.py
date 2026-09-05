"""
worldview_build_panel.py — Left Build Panel for Multi-Tier Infrastructure & Governance.

Shows constructible structures separated into 3 distinct governance tiers:
1. Municipal / Tile Level (funded by region.gov)
2. Provincial Level (funded by province.gov / member tiles)
3. National Sovereign Level (funded by nation.government)

Interactive buttons morph into live progress bar gauges when in-progress.
If funds are insufficient, clicking opens the Fiscal Transfer & Borrowing Modal.
"""

import pygame
from worldview_camera import HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from buildings import BUILDING_RECIPES
from intents import BuildIntent
from ui_icons import draw_progress_bar_button, get_icon

BUILD_PANEL_X = 14
BUILD_PANEL_Y = TOP_BAR_H + 10
BUILD_PANEL_W = 310
BUILD_PANEL_H = HEIGHT - TOP_BAR_H - TICKER_H - 18


def draw_build_panel(surface, world, font, font_small, mouse_pos=None):
    """Draw the multi-tier left build panel for the selected tile (or collapsed toggle button)."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    x, y, w, h = BUILD_PANEL_X, BUILD_PANEL_Y, BUILD_PANEL_W, BUILD_PANEL_H

    pinned = world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    # If collapsed or no tile selected, return
    if not world.get('build_panel_open', False) or pinned is None:
        return

    # Auto-collapse layer dock and close other left panels so they don't overlap
    world['layers_collapsed'] = True
    world['gov_panel_open'] = False
    world['diplomacy_panel_open'] = False
    world['debt_panel_open'] = False
    world['science_panel_open'] = False
    world['military_panel_open'] = False
    world['left_panel'] = 'build'

    # Background frame
    panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    panel_surf.fill((16, 18, 26, 240))
    surface.blit(panel_surf, (x, y))
    pygame.draw.rect(surface, (65, 70, 90), (x, y, w, h), 1, border_radius=8)

    # Header
    city_name = getattr(pinned, 'display_name', getattr(pinned, 'city_name', pinned.name))
    nation = getattr(pinned, 'owner_nation', None)
    province = getattr(pinned, 'province', None)
    prov_name = province.name if province else "Province"
    nat_name = nation.name if nation else "Wilderness"

    # Procedural hammer icon
    h_icon = get_icon('hammer', 16)
    surface.blit(h_icon, (x + 12, y + 12))

    head_txt = font.render(f"Construction: {city_name}", True, ACCENT)
    surface.blit(head_txt, (x + 32, y + 10))

    sub_txt = font_small.render(f"{prov_name} • {nat_name}", True, DIM)
    surface.blit(sub_txt, (x + 32, y + 30))

    # Close button [X]
    close_rect = (x + w - 26, y + 8, 18, 18)
    hc = close_rect[0] <= mx <= close_rect[0] + 18 and close_rect[1] <= my <= close_rect[1] + 18
    pygame.draw.rect(surface, (60, 60, 80) if hc else (35, 35, 48), close_rect, border_radius=3)
    x_txt = font_small.render("×", True, (255, 255, 255) if hc else DIM)
    surface.blit(x_txt, (close_rect[0] + 4, close_rect[1] + 1))
    # Drawer Top Switcher Tabs
    from worldview_left_dock import draw_drawer_top_tabs
    cur_y = draw_drawer_top_tabs(surface, world, x, y + 48, w, 'build', font_small, mouse_pos)

    # ─────────────────────────────────────────────────────────────
    # Tier 1: Municipal / Tile Level
    # ─────────────────────────────────────────────────────────────
    rgov = getattr(pinned, 'gov', None)
    tile_cash = (rgov.agent.cash if rgov else 0.0) + (pinned.bank.deposits.get(rgov.agent, 0.0) if hasattr(pinned, 'bank') and rgov else 0.0)
    
    cur_y = _draw_tier_section(
        surface, world, pinned, nation,
        icon_kind='municipal',
        tier_title="Municipal Infrastructure",
        treasury_label=f"Tile: ${tile_cash:,.0f}",
        treasury_amt=tile_cash,
        recipes_keys=['farm', 'granary', 'sawmill', 'workshop'],
        x=x + 8, y=cur_y, w=w - 16,
        font=font, font_small=font_small, mouse_pos=mouse_pos
    )

    # ─────────────────────────────────────────────────────────────
    # Tier 2: Provincial Public Works
    # ─────────────────────────────────────────────────────────────
    prov_cash = sum(getattr(t.gov.agent, 'cash', 0.0) + (t.bank.deposits.get(t.gov.agent, 0.0) if hasattr(t, 'bank') else 0.0)
                    for t in (province.tiles if province else (nation.tiles if nation else [pinned])) if getattr(t, 'gov', None))
    
    cur_y = _draw_tier_section(
        surface, world, pinned, nation,
        icon_kind='province',
        tier_title="Provincial Public Works",
        treasury_label=f"Province: ${prov_cash:,.0f}",
        treasury_amt=prov_cash,
        recipes_keys=['paved_road', 'river_bridge', 'sanatorium'],
        x=x + 8, y=cur_y, w=w - 16,
        font=font, font_small=font_small, mouse_pos=mouse_pos
    )

    # ─────────────────────────────────────────────────────────────
    # Tier 3: National Strategic Projects
    # ─────────────────────────────────────────────────────────────
    nat_cash = (nation.treasury()['total']) if nation else 0.0

    cur_y = _draw_tier_section(
        surface, world, pinned, nation,
        icon_kind='crown',
        tier_title="National Strategic Projects",
        treasury_label=f"State: ${nat_cash:,.0f}",
        treasury_amt=nat_cash,
        recipes_keys=['mountain_pass', 'central_mint', 'military_citadel'],
        x=x + 8, y=cur_y, w=w - 16,
        font=font, font_small=font_small, mouse_pos=mouse_pos
    )

    # ─────────────────────────────────────────────────────────────
    # Tier 4: Manual Fiscal Equalization
    # ─────────────────────────────────────────────────────────────
    _draw_equalization_section(
        surface, world, pinned, nation,
        x=x + 8, y=cur_y, w=w - 16,
        font_small=font_small, mouse_pos=mouse_pos
    )


def _draw_equalization_section(surface, world, pinned, nation, x, y, w, font_small, mouse_pos=None):
    """Render manual Horizontal Fiscal Equalization action button."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    # Header bar
    eq_hdr_rect = (x, y, w, 20)
    eq_hdr_hover = eq_hdr_rect[0] <= mx <= eq_hdr_rect[0] + w and eq_hdr_rect[1] <= my <= eq_hdr_rect[1] + 20
    if eq_hdr_hover:
        from worldview_tooltips import get_button_tooltip_data
        tdata = get_button_tooltip_data("tier_equalization", world, pinned, nation)
        if tdata:
            tdata['btn_rect'] = eq_hdr_rect
            world['_hovered_left_tooltip'] = tdata

    pygame.draw.rect(surface, (36, 40, 56) if eq_hdr_hover else (28, 30, 42), eq_hdr_rect, border_radius=4)
    pygame.draw.rect(surface, (80, 95, 130) if eq_hdr_hover else (50, 55, 75), eq_hdr_rect, 1, border_radius=4)

    eq_ico = get_icon('scale', 14)
    surface.blit(eq_ico, (x + 6, y + 3))

    t_txt = font_small.render("Fiscal Equalization", True, (255, 235, 160) if eq_hdr_hover else (240, 220, 140))
    surface.blit(t_txt, (x + 24, y + 3))

    btn_y = y + 24
    btn_rect = (x, btn_y, w, 26)

    nat_cash = (nation.government.agent.cash) if nation else 0.0
    can_grant = nat_cash >= 250.0

    hb = btn_rect[0] <= mx <= btn_rect[0] + w and btn_rect[1] <= my <= btn_rect[1] + 26
    bg = (32, 44, 36) if can_grant else (30, 30, 38)
    if hb and can_grant:
        bg = (45, 62, 50)
    if hb:
        from worldview_tooltips import get_button_tooltip_data
        tdata = get_button_tooltip_data('nat_sovereign_grant', world, pinned, nation)
        if tdata:
            tdata['btn_rect'] = btn_rect
            world['_hovered_left_tooltip'] = tdata
    pygame.draw.rect(surface, bg, btn_rect, border_radius=4)
    pygame.draw.rect(surface, (70, 160, 90) if can_grant else (60, 50, 55), btn_rect, 1, border_radius=4)

    lbl_name = font_small.render("Disburse Equalization Grant", True, (220, 245, 225) if can_grant else (160, 160, 160))
    lbl_cost = font_small.render("$250", True, (120, 220, 140) if can_grant else (180, 90, 90))
    surface.blit(lbl_name, (btn_rect[0] + 8, btn_y + 5))
    surface.blit(lbl_cost, (btn_rect[0] + w - lbl_cost.get_width() - 8, btn_y + 5))


def _get_tier_layout(y: int, recipes_keys: list[str], x: int, w: int):
    """Return next section y and list of (recipe_key, button_rect) pairs."""
    rects = []
    by = y + 24
    for r_key in recipes_keys:
        rects.append((r_key, (x, by, w, 28)))
        by += 32
    return by + 4, rects


def _draw_tier_section(surface, world, pinned, nation, icon_kind, tier_title, treasury_label,
                       treasury_amt, recipes_keys, x, y, w, font, font_small, mouse_pos=None):
    """Render one governance tier section with vector icon header and recipe buttons."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)

    # Header bar
    hdr_rect = (x, y, w, 20)
    hdr_hover = hdr_rect[0] <= mx <= hdr_rect[0] + w and hdr_rect[1] <= my <= hdr_rect[1] + 20
    if hdr_hover:
        from worldview_tooltips import get_button_tooltip_data
        tdata = get_button_tooltip_data(f"tier_{icon_kind}", world, pinned, nation)
        if tdata:
            tdata['btn_rect'] = hdr_rect
            world['_hovered_left_tooltip'] = tdata

    pygame.draw.rect(surface, (36, 40, 56) if hdr_hover else (28, 30, 42), hdr_rect, border_radius=4)
    pygame.draw.rect(surface, (80, 95, 130) if hdr_hover else (50, 55, 75), hdr_rect, 1, border_radius=4)

    # Vector Icon
    tier_ico = get_icon(icon_kind, 14)
    surface.blit(tier_ico, (x + 6, y + 3))

    t_txt = font_small.render(tier_title, True, (255, 235, 160) if hdr_hover else (240, 220, 140))
    surface.blit(t_txt, (x + 24, y + 3))

    tr_txt = font_small.render(treasury_label, True, (120, 220, 140))
    surface.blit(tr_txt, (x + w - tr_txt.get_width() - 6, y + 3))

    next_y, btn_layouts = _get_tier_layout(y, recipes_keys, x, w)
    for r_key, btn_rect in btn_layouts:
        recipe = BUILDING_RECIPES.get(r_key)
        if not recipe:
            continue

        cost = recipe.cost
        is_built = any(b.name == r_key for b in getattr(pinned, 'buildings', []))
        active_proj = next((p for p in getattr(pinned, 'construction_projects', []) if p.recipe.name == r_key and p.status == 'in_progress'), None)
        if active_proj is None and nation:
            active_proj = next((p for p in getattr(nation, 'construction_projects', []) if p.recipe.name == r_key and p.status == 'in_progress' and p.region == pinned), None)

        hb = btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]
        if hb:
            from worldview_tooltips import get_button_tooltip_data
            tdata = get_button_tooltip_data(f"build_{r_key}", world, pinned, nation)
            if tdata:
                tdata['btn_rect'] = btn_rect
                world['_hovered_left_tooltip'] = tdata

        if is_built:
            draw_progress_bar_button(surface, btn_rect, f"{recipe.display_name} Active", 1.0, font_small, theme='complete', icon_kind='check')
        elif active_proj is not None:
            pct = min(1.0, max(0.0, active_proj.turns_elapsed / max(1, active_proj.total_turns)))
            draw_progress_bar_button(surface, btn_rect, f"{recipe.display_name}: {active_proj.turns_elapsed}/{active_proj.total_turns}t ({int(pct*100)}%)", pct, font_small, theme='construction', icon_kind=r_key)
        else:
            can_afford = treasury_amt >= cost
            bg = (55, 58, 78) if (hb and can_afford) else ((42, 38, 42) if hb else ((40, 42, 56) if can_afford else (30, 30, 38)))
            pygame.draw.rect(surface, bg, btn_rect, border_radius=4)
            pygame.draw.rect(surface, (80, 85, 115) if can_afford else (60, 50, 55), btn_rect, 1, border_radius=4)

            # Name and Cost
            lbl_name = font_small.render(recipe.display_name, True, TEXT if can_afford else (170, 160, 160))
            lbl_cost = font_small.render(f"${cost:.0f}" if can_afford else f"${cost:.0f} [Short]", True, (245, 190, 80) if can_afford else (220, 110, 110))
            surface.blit(lbl_name, (btn_rect[0] + 8, btn_rect[1] + 6))
            surface.blit(lbl_cost, (btn_rect[0] + btn_rect[2] - lbl_cost.get_width() - 8, btn_rect[1] + 6))

    return next_y


def build_panel_hit(pos, world) -> bool:
    """Handle mouse clicks inside the Left Build Panel or collapsed button."""
    mx, my = pos
    x, y, w, h = BUILD_PANEL_X, BUILD_PANEL_Y, BUILD_PANEL_W, BUILD_PANEL_H
    pinned = world.get('selected_region')

    # If collapsed or no tile selected, check collapsed toggle button
    if not world.get('build_panel_open', True) or pinned is None:
        btn_w = 146
        btn_h = 28
        if x <= mx <= x + btn_w and y <= my <= y + btn_h:
            world['build_panel_open'] = True
            world['layers_collapsed'] = True
            if pinned is None and world.get('tiles'):
                # Select first nation tile by default
                nations = world.get('nations', [])
                if nations and nations[0].tiles:
                    world['selected_region'] = nations[0].tiles[0]
            return True
        return False

    if not (x <= mx <= x + w and y <= my <= y + h):
        return False

    # Close button [X]
    if x + w - 26 <= mx <= x + w - 8 and y + 8 <= my <= y + 26:
        from worldview_left_dock import close_left_panels
        close_left_panels(world)
        return True

    # Drawer Top Switcher
    from worldview_left_dock import drawer_top_tabs_hit
    if drawer_top_tabs_hit(pos, world, x, y + 48, w):
        return True

    nation = getattr(pinned, 'owner_nation', None)
    if nation is None:
        return True

    province = getattr(pinned, 'province', None)
    t = world.get('turn', 1)

    # Check button clicks in each tier (new layout with tabs at y+80, fallback to y+50)
    for base_y in (y + 48 + 24 + 8, y + 50):
        cur_y = base_y
        # 1. Tile Tier
        rgov = getattr(pinned, 'gov', None)
        tile_cash = (rgov.agent.cash if rgov else 0.0) + (pinned.bank.deposits.get(rgov.agent, 0.0) if hasattr(pinned, 'bank') and rgov else 0.0)
        cur_y, tier1_buttons = _get_tier_layout(cur_y, ['farm', 'granary', 'sawmill', 'workshop'], x + 8, w - 16)
        for r_key, btn_rect in tier1_buttons:
            if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]:
                _handle_build_click(world, pinned, nation, r_key, tile_cash, t)
                return True

        # 2. Province Tier
        prov_cash = sum(getattr(tg.gov.agent, 'cash', 0.0) + (tg.bank.deposits.get(tg.gov.agent, 0.0) if hasattr(tg, 'bank') else 0.0)
                        for tg in (province.tiles if province else nation.tiles) if getattr(tg, 'gov', None))
        cur_y, tier2_buttons = _get_tier_layout(cur_y, ['paved_road', 'river_bridge', 'sanatorium'], x + 8, w - 16)
        for r_key, btn_rect in tier2_buttons:
            if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]:
                _handle_build_click(world, pinned, nation, r_key, prov_cash, t)
                return True

        # 3. National Sovereign Tier
        nat_cash = (nation.treasury()['total']) if nation else 0.0
        cur_y, tier3_buttons = _get_tier_layout(cur_y, ['mountain_pass', 'central_mint', 'military_citadel'], x + 8, w - 16)
        for r_key, btn_rect in tier3_buttons:
            if btn_rect[0] <= mx <= btn_rect[0] + btn_rect[2] and btn_rect[1] <= my <= btn_rect[1] + btn_rect[3]:
                _handle_build_click(world, pinned, nation, r_key, nat_cash, t)
                return True

    # 4. Manual Fiscal Equalization Click
    eq_btn_rect = (x + 8, cur_y + 24, w - 16, 26)
    if eq_btn_rect[0] <= mx <= eq_btn_rect[0] + eq_btn_rect[2] and eq_btn_rect[1] <= my <= eq_btn_rect[1] + eq_btn_rect[3]:
        from intents import execute_equalization_grant
        ok, msg = execute_equalization_grant(world, nation.name, pinned.name, 'national_sovereign', 250.0, t)
        if ok:
            world['action_feedback'] = (msg, GREEN, t)
        else:
            world['action_feedback'] = (msg, RED, t)
        return True

    return True


def _handle_build_click(world, region, nation, building_type, available_funds, t):
    """Commission directly if affordable, or open the Fiscal Transfer Dialog if short."""
    recipe = BUILDING_RECIPES.get(building_type)
    if not recipe:
        return

    is_built = any(b.name == building_type for b in getattr(region, 'buildings', []))
    active_proj = next((p for p in getattr(region, 'construction_projects', []) if p.recipe.name == building_type and p.status == 'in_progress'), None)
    if is_built or active_proj is not None:
        return

    cost = recipe.cost
    if available_funds >= cost:
        # Direct execution
        intent = BuildIntent(nation.name, region.name, building_type, submitted_turn=t, regime_type=nation.regime_type)
        nation.submit_intent(intent, t)
        tiles_by_name = {r.name: r for r in world.get('tiles', [])}
        nations_by_name = {n.name: n for n in world.get('nations', [])}
        ok, msg = intent.execute(tiles_by_name, nations_by_name, t)
        if ok:
            from worldview_engine import ticker_push
            ticker_push(world, t, 'CONSTRUCT', f"Commissioned {recipe.display_name} in {region.name} (${cost:.0f}).", (245, 180, 50))
            world['action_feedback'] = (f"Commissioned {recipe.display_name}!", GREEN, t)
        else:
            world['action_feedback'] = (msg, RED, t)
    else:
        # Prompt user with Fiscal Transfer Modal
        world['transfer_dialog'] = {
            'open': True,
            'building_type': building_type,
            'region': region,
            'nation': nation,
            'on_hand': available_funds,
        }
