"""
worldview_transfer_dialog.py — Interactive Inter-Governmental Fiscal Transfer & Borrowing Modal.

When a sovereign or municipal government attempts to commission an infrastructure project
with insufficient funds on hand, this modal prompts the player to resolve the shortfall via:
1. Inter-Governmental Equalization Grant from the Province.
2. Sovereign Infrastructure Grant / Bailout from the National Treasury.
3. Municipal Deficit Bond / Loan from the Local Tile Bank.
"""

import pygame
from worldview_camera import WIDTH, HEIGHT
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from buildings import BUILDING_RECIPES
from intents import execute_fiscal_transfer_and_build


def draw_transfer_dialog(surface, world, font, font_small, mouse_pos=None):
    """Render the high-contrast interactive Fiscal Transfer & Borrowing Modal."""
    dialog = world.get('transfer_dialog')
    if not dialog or not dialog.get('open'):
        return

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    
    # Modal dimensions (centered)
    modal_w = 640
    modal_h = 370
    modal_x = (WIDTH - modal_w) // 2
    modal_y = (HEIGHT - modal_h) // 2

    # Dim overlay
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((8, 8, 14, 215))
    surface.blit(overlay, (0, 0))

    # Main Card
    pygame.draw.rect(surface, (22, 22, 32), (modal_x, modal_y, modal_w, modal_h), border_radius=10)
    pygame.draw.rect(surface, (245, 180, 50), (modal_x, modal_y, modal_w, modal_h), 2, border_radius=10)

    action_kind = dialog.get('action_kind', 'building')
    region = dialog.get('region')
    nation = dialog.get('nation')
    city_name = getattr(region, 'display_name', getattr(region, 'city_name', region.name if region else "Tile"))

    if action_kind == 'policy':
        policy_name = dialog.get('policy_name', 'Policy Decree')
        cost = float(dialog.get('cost', 100.0))
        on_hand = float(dialog.get('on_hand', 0.0))
        shortfall = max(0.0, cost - on_hand)
        tier_title = "Policy Mandate (10-Turn Budget)"
        recipe_name = policy_name
        prompt_text = "Select a funding authority to disburse the shortfall and enact this 10-turn policy:"
        icon_name = 'policies'
    else:
        building_type = dialog.get('building_type', 'granary')
        recipe = BUILDING_RECIPES.get(building_type)
        recipe_name = recipe.display_name if recipe else building_type
        tier = recipe.tier if recipe else 'tile'
        tier_title = {'tile': 'Municipal', 'province': 'Provincial', 'nation': 'National Sovereign'}.get(tier, 'Municipal')
        cost = recipe.cost if recipe else 250.0
        on_hand = float(dialog.get('on_hand', 0.0))
        shortfall = max(0.0, cost - on_hand)
        prompt_text = "Select a funding authority to disburse the shortfall and initiate construction:"
        icon_name = 'municipal'

    # Title Header with vector icon
    from ui_icons import get_icon
    m_icon = get_icon(icon_name, 18)
    surface.blit(m_icon, (modal_x + 24, modal_y + 22))

    header = font.render(f"Fiscal Shortfall: {recipe_name}", True, (255, 220, 100))
    surface.blit(header, (modal_x + 48, modal_y + 20))

    sub = font_small.render(f"Scope: {tier_title} on [{city_name}] ({nation.name if nation else ''})", True, DIM)
    surface.blit(sub, (modal_x + 24, modal_y + 46))

    # Cost breakdown box
    b_rect = (modal_x + 24, modal_y + 74, modal_w - 48, 64)
    pygame.draw.rect(surface, (14, 14, 22), b_rect, border_radius=6)
    pygame.draw.rect(surface, (60, 60, 80), b_rect, 1, border_radius=6)

    c_lbl = font_small.render(f"Total Commitment: ${cost:,.2f}", True, TEXT)
    h_lbl = font_small.render(f"Treasury on Hand: ${on_hand:,.2f}", True, (120, 220, 140))
    s_lbl = font.render(f"Budget Shortfall: ${shortfall:,.2f}", True, (245, 90, 90))

    surface.blit(c_lbl, (modal_x + 36, modal_y + 84))
    surface.blit(h_lbl, (modal_x + 36, modal_y + 108))
    surface.blit(s_lbl, (modal_x + modal_w - s_lbl.get_width() - 40, modal_y + 92))

    # Prompt text
    prompt = font_small.render(prompt_text, True, TEXT)
    surface.blit(prompt, (modal_x + 24, modal_y + 150))

    # 3 Option Cards
    btn_y = modal_y + 176
    btn_w = modal_w - 48
    btn_h = 44

    # 1. Provincial Grant
    province = getattr(region, 'province', None)
    prov_cash = sum(getattr(t.gov.agent, 'cash', 0.0) for t in (province.tiles if province else nation.tiles) if t != region and getattr(t, 'gov', None)) if nation else 0.0
    can_prov = prov_cash >= shortfall

    btn1_rect = (modal_x + 24, btn_y, btn_w, btn_h)
    h1 = btn1_rect[0] <= mx <= btn1_rect[0] + btn_w and btn1_rect[1] <= my <= btn1_rect[1] + btn_h
    bg1 = (36, 44, 36) if can_prov else (28, 28, 34)
    pygame.draw.rect(surface, (50, 65, 50) if (h1 and can_prov) else bg1, btn1_rect, border_radius=6)
    pygame.draw.rect(surface, (80, 180, 100) if can_prov else (55, 55, 70), btn1_rect, 1, border_radius=6)
    t1 = font.render(f"1. Provincial Equalization Grant (${shortfall:,.0f})", True, (140, 240, 160) if can_prov else DIM)
    d1 = font_small.render(f"Disburses from member province tiles (Available: ${prov_cash:,.0f})", True, DIM)
    surface.blit(t1, (modal_x + 36, btn_y + 6))
    surface.blit(d1, (modal_x + 36, btn_y + 26))

    # 2. National Sovereign Bailout
    btn_y += 50
    nat_cash = getattr(nation.government.agent, 'cash', 0.0) if nation else 0.0
    can_nat = nat_cash >= shortfall

    btn2_rect = (modal_x + 24, btn_y, btn_w, btn_h)
    h2 = btn2_rect[0] <= mx <= btn2_rect[0] + btn_w and btn2_rect[1] <= my <= btn2_rect[1] + btn_h
    bg2 = (44, 40, 30) if can_nat else (28, 28, 34)
    pygame.draw.rect(surface, (65, 60, 40) if (h2 and can_nat) else bg2, btn2_rect, border_radius=6)
    pygame.draw.rect(surface, (245, 180, 60) if can_nat else (55, 55, 70), btn2_rect, 1, border_radius=6)
    t2 = font.render(f"2. Sovereign National Infrastructure Grant (${shortfall:,.0f})", True, (255, 215, 100) if can_nat else DIM)
    d2 = font_small.render(f"Disburses from Central State Treasury (Available: ${nat_cash:,.0f})", True, DIM)
    surface.blit(t2, (modal_x + 36, btn_y + 6))
    surface.blit(d2, (modal_x + 36, btn_y + 26))

    # 3. Municipal Bank Loan
    btn_y += 50
    bank = getattr(region, 'bank', None)
    bank_cap = getattr(bank, 'capital', 0.0) if bank else 0.0
    can_bank = bank_cap >= shortfall

    btn3_rect = (modal_x + 24, btn_y, btn_w, btn_h)
    h3 = btn3_rect[0] <= mx <= btn3_rect[0] + btn_w and btn3_rect[1] <= my <= btn3_rect[1] + btn_h
    bg3 = (32, 40, 48) if can_bank else (28, 28, 34)
    pygame.draw.rect(surface, (45, 60, 75) if (h3 and can_bank) else bg3, btn3_rect, border_radius=6)
    pygame.draw.rect(surface, (100, 180, 240) if can_bank else (55, 55, 70), btn3_rect, 1, border_radius=6)
    t3 = font.render(f"3. Municipal Deficit Bond / Bank Loan (${shortfall:,.0f})", True, (140, 210, 255) if can_bank else DIM)
    d3 = font_small.render(f"Borrows directly from local Municipal Bank (Capital: ${bank_cap:,.0f})", True, DIM)
    surface.blit(t3, (modal_x + 36, btn_y + 6))
    surface.blit(d3, (modal_x + 36, btn_y + 26))

    # Cancel Button
    cancel_rect = (modal_x + modal_w - 130, modal_y + modal_h - 38, 106, 26)
    hc = cancel_rect[0] <= mx <= cancel_rect[0] + cancel_rect[2] and cancel_rect[1] <= my <= cancel_rect[1] + cancel_rect[3]
    pygame.draw.rect(surface, (55, 55, 70) if hc else (38, 38, 50), cancel_rect, border_radius=4)
    pygame.draw.rect(surface, (90, 90, 110), cancel_rect, 1, border_radius=4)
    c_txt = font_small.render("Cancel [Esc]", True, TEXT if not hc else (255, 255, 255))
    surface.blit(c_txt, c_txt.get_rect(center=(cancel_rect[0] + cancel_rect[2] // 2, cancel_rect[1] + cancel_rect[3] // 2)))


def transfer_dialog_hit(pos, world) -> bool:
    """Handle mouse clicks on the Fiscal Transfer & Borrowing Modal."""
    dialog = world.get('transfer_dialog')
    if not dialog or not dialog.get('open'):
        return False

    mx, my = pos
    modal_w = 640
    modal_h = 370
    modal_x = (WIDTH - modal_w) // 2
    modal_y = (HEIGHT - modal_h) // 2

    # Click outside modal closes it
    if mx < modal_x or mx > modal_x + modal_w or my < modal_y or my > modal_y + modal_h:
        dialog['open'] = False
        return True

    # Cancel Button
    cancel_rect = (modal_x + modal_w - 130, modal_y + modal_h - 38, 106, 26)
    if cancel_rect[0] <= mx <= cancel_rect[0] + cancel_rect[2] and cancel_rect[1] <= my <= cancel_rect[1] + cancel_rect[3]:
        dialog['open'] = False
        return True

    action_kind = dialog.get('action_kind', 'building')
    region = dialog.get('region')
    nation = dialog.get('nation')
    t = world.get('turn', 1)
    btn_w = modal_w - 48
    btn_h = 44

    if action_kind == 'policy':
        policy_id = dialog.get('policy_id')
        policy_name = dialog.get('policy_name', 'Policy')
        cost = float(dialog.get('cost', 100.0))
        on_hand = float(dialog.get('on_hand', 0.0))
        shortfall = max(0.0, cost - on_hand)

        btn1_y = modal_y + 176
        btn1_rect = (modal_x + 24, btn1_y, btn_w, btn_h)
        if btn1_rect[0] <= mx <= btn1_rect[0] + btn_w and btn1_rect[1] <= my <= btn1_rect[1] + btn_h:
            ok, msg = execute_fiscal_transfer_and_policy(world, nation.name if nation else "", region.name, policy_id, 'province_grant', shortfall, t)
            world['action_feedback'] = (f"Enacted {policy_name} via Provincial Grant!", GREEN, t)
            dialog['open'] = False
            return True

        btn2_y = btn1_y + 50
        btn2_rect = (modal_x + 24, btn2_y, btn_w, btn_h)
        if btn2_rect[0] <= mx <= btn2_rect[0] + btn_w and btn2_rect[1] <= my <= btn2_rect[1] + btn_h:
            ok, msg = execute_fiscal_transfer_and_policy(world, nation.name if nation else "", region.name, policy_id, 'national_bailout', shortfall, t)
            world['action_feedback'] = (f"Enacted {policy_name} via Sovereign Grant!", GREEN, t)
            dialog['open'] = False
            return True

        btn3_y = btn2_y + 50
        btn3_rect = (modal_x + 24, btn3_y, btn_w, btn_h)
        if btn3_rect[0] <= mx <= btn3_rect[0] + btn_w and btn3_rect[1] <= my <= btn3_rect[1] + btn_h:
            ok, msg = execute_fiscal_transfer_and_policy(world, nation.name if nation else "", region.name, policy_id, 'bank_loan', shortfall, t)
            world['action_feedback'] = (f"Enacted {policy_name} via Municipal Bank Loan!", GREEN, t)
            dialog['open'] = False
            return True
        return True

    # Infrastructure Building Project
    building_type = dialog.get('building_type')
    recipe = BUILDING_RECIPES.get(building_type)
    if not recipe:
        dialog['open'] = False
        return True

    cost = recipe.cost
    on_hand = float(dialog.get('on_hand', 0.0))
    shortfall = max(0.0, cost - on_hand)

    # 1. Option 1: Provincial Grant
    btn1_y = modal_y + 176
    btn1_rect = (modal_x + 24, btn1_y, btn_w, btn_h)
    if btn1_rect[0] <= mx <= btn1_rect[0] + btn_w and btn1_rect[1] <= my <= btn1_rect[1] + btn_h:
        ok, msg = execute_fiscal_transfer_and_build(world, nation.name, region.name, building_type, 'province_grant', shortfall, t)
        if ok:
            world['action_feedback'] = (f"Commissioned {recipe.display_name} via Provincial Grant!", GREEN, t)
            dialog['open'] = False
        else:
            world['action_feedback'] = (msg, RED, t)
        return True

    # 2. Option 2: Sovereign National Bailout
    btn2_y = btn1_y + 50
    btn2_rect = (modal_x + 24, btn2_y, btn_w, btn_h)
    if btn2_rect[0] <= mx <= btn2_rect[0] + btn_w and btn2_rect[1] <= my <= btn2_rect[1] + btn_h:
        ok, msg = execute_fiscal_transfer_and_build(world, nation.name, region.name, building_type, 'national_bailout', shortfall, t)
        if ok:
            world['action_feedback'] = (f"Commissioned {recipe.display_name} via Sovereign Grant!", GREEN, t)
            dialog['open'] = False
        else:
            world['action_feedback'] = (msg, RED, t)
        return True

    # 3. Option 3: Municipal Bank Loan
    btn3_y = btn2_y + 50
    btn3_rect = (modal_x + 24, btn3_y, btn_w, btn_h)
    if btn3_rect[0] <= mx <= btn3_rect[0] + btn_w and btn3_rect[1] <= my <= btn3_rect[1] + btn_h:
        ok, msg = execute_fiscal_transfer_and_build(world, nation.name, region.name, building_type, 'bank_loan', shortfall, t)
        if ok:
            world['action_feedback'] = (f"Commissioned {recipe.display_name} via Municipal Bank Loan!", GREEN, t)
            dialog['open'] = False
        else:
            world['action_feedback'] = (msg, RED, t)
        return True

    return True


def execute_fiscal_transfer_and_policy(world, nation_name: str, region_name: str, policy_id: str,
                                       transfer_source: str, transfer_amount: float, t: int) -> tuple[bool, str]:
    """Execute fiscal transfer and disburse funds to municipal government to enact a policy decree."""
    tiles_by_name = {r.name: r for r in world.get('tiles', [])}
    nations_by_name = {n.name: n for n in world.get('nations', [])}

    region = tiles_by_name.get(region_name)
    nation = nations_by_name.get(nation_name)
    if not region:
        return False, "Region not found."

    rgov = getattr(region, 'gov', None)
    if not rgov:
        return False, "Region has no municipal government."

    transfer_amount = max(0.0, float(transfer_amount))

    if transfer_source == 'province_grant':
        province = getattr(region, 'province', None)
        prov_siblings = [t for t in getattr(province, 'tiles', []) if t != region and getattr(t, 'gov', None)] if province else []
        nation_siblings = [t for t in nation.tiles if t != region and t not in prov_siblings and getattr(t, 'gov', None)] if nation else []
        gathered = 0.0
        for ot in (prov_siblings + nation_siblings):
            ogov = ot.gov
            if ogov.agent.cash > 0:
                take = min(transfer_amount - gathered, ogov.agent.cash)
                ogov.agent.cash -= take
                rgov.agent.cash += take
                gathered += take
                if gathered >= transfer_amount - 0.01:
                    break
    elif transfer_source == 'national_bailout':
        if nation and hasattr(nation, 'government') and nation.government:
            nat_cash = nation.government.agent.cash
            take = min(transfer_amount, nat_cash)
            nation.government.agent.cash -= take
            rgov.agent.cash += take
    elif transfer_source == 'bank_loan':
        bank = getattr(region, 'bank', None)
        if bank:
            bank.capital -= transfer_amount
            rgov.agent.cash += transfer_amount

    # Enact the policy decree
    from worldview_gov_panel import _execute_gov_policy
    _execute_gov_policy(world, policy_id, region)
    return True, f"Enacted policy decree via {transfer_source}."
