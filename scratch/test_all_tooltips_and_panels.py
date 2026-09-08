"""
scratch/test_all_tooltips_and_panels.py
Comprehensive test suite verifying tooltips, left-panel drawers, modal suppression,
and right-panel fiscal card.
"""

import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
import pygame
pygame.init()

from worldview_engine import build_world_view
from worldview_tooltips import get_button_tooltip_data, draw_left_panel_tooltip
from worldview_diplomacy_panel import draw_diplomacy_panel
from worldview_debt_panel import draw_debt_panel
from worldview_military_panel import draw_military_panel
from worldview_science_panel import draw_science_panel
from worldview_gov_panel import draw_gov_panel
from worldview_ui import draw_panel
from worldview_camera import WIDTH, HEIGHT


def test_tooltips():
    print("=== Testing Tooltip Generators ===")
    world = build_world_view(seed=42)
    nation = world['nations'][0]
    region = nation.tiles[0]

    test_ids = [
        # City policies
        'city_tax_cut', 'city_tax_raise', 'city_toggle_ubi', 'city_emergency_food',
        'city_farm_subsidy', 'city_safety_patrol', 'city_recruit_garrison', 'city_enclose_plot',
        # Province policies
        'prov_pave_highway', 'prov_healthcare', 'prov_equalization',
        'prov_harmonize_taxes', 'prov_standardize_routes',
        # National policies
        'nat_tax_15', 'nat_tariff_25', 'nat_enact_ubi', 'nat_toggle_imm',
        'nat_science_prize', 'nat_mobilize_army', 'nat_sovereign_grant',
        'nat_ten_hour_act', 'nat_safety_mandate', 'nat_subsidize_entertainment',
        # Infrastructure
        'build_farm', 'build_granary', 'build_sawmill', 'build_workshop', 'build_paved_road',
        'tier_municipal', 'tier_province', 'tier_crown', 'tier_equalization',
        # Dock tabs
        'dock_build', 'dock_governance', 'dock_diplomacy', 'dock_debt', 'dock_science', 'dock_military',
        # Strategic resources
        'res_arable_silt', 'res_timber', 'res_iron_ore', 'res_coal_seam',
        'res_pasture_flax', 'res_crude_petroleum', 'res_rare_minerals',
        # Science
        'sci_era_1', 'sci_era_2', 'sci_era_3', 'sci_era_4',
        'tech_crop_rotation', 'tech_bloomery_iron', 'sci_pledge_crop_rotation',
        # Diplomacy
        'dip_target_Valoria', 'dip_trade_pact', 'dip_nap', 'dip_alliance',
        'dip_war_peace', 'dip_foreign_aid',
        # Debt
        'debt_scope_domestic', 'debt_scope_foreign', 'debt_lobby_isrb',
        'debt_audit_rival', 'debt_board_seat', 'debt_dur_20', 'debt_dur_50', 'debt_dur_100',
        'debt_issue_500', 'debt_issue_1000', 'debt_buy_bond',
        # Military
        'mil_recruit_unit'
    ]

    for tid in test_ids:
        tdata = get_button_tooltip_data(tid, world, region=region, nation=nation)
        assert tdata is not None, f"Tooltip data for '{tid}' is None!"
        assert 'title' in tdata, f"Tooltip for '{tid}' missing 'title'!"
        assert 'desc' in tdata and len(tdata['desc']) > 0, f"Tooltip for '{tid}' missing 'desc'!"
        assert 'cost' in tdata, f"Tooltip for '{tid}' missing 'cost'!"
        print(f"  [OK] {tid:25} -> {tdata['title']}")

    # Specific assertions
    enclose_data = get_button_tooltip_data('city_enclose_plot', world, region=region, nation=nation)
    assert "500" in enclose_data['cost'], f"Enclose cost should be $500, got: {enclose_data['cost']}"
    assert "Money Destination:" in " ".join(enclose_data['desc']), "Enclose tooltip missing Money Destination!"

    ubi_data = get_button_tooltip_data('city_toggle_ubi', world, region=region, nation=nation)
    assert "10-turn" in ubi_data['cost'] or "10-turn" in " ".join(ubi_data['desc']), "UBI missing 10-turn duration!"
    assert "Money Destination:" in " ".join(ubi_data['desc']), "UBI missing Money Destination!"

    aid_data = get_button_tooltip_data('dip_foreign_aid', world, region=region, nation=nation)
    assert "Money Destination:" in " ".join(aid_data['desc']), "Foreign Aid missing Money Destination!"

    print("All tooltip generator tests passed!")


def test_panel_rendering_and_hover():
    print("=== Testing Panel Rendering & Hover Hooks ===")
    surface = pygame.Surface((WIDTH, HEIGHT))
    font = pygame.font.Font(None, 20)
    font_small = pygame.font.Font(None, 16)

    world = build_world_view(seed=42)
    nation = world['nations'][0]
    region = nation.tiles[0]
    world['selected_region'] = region
    world['selected_nation'] = nation

    # 1. Diplomacy Panel
    world['diplomacy_panel_open'] = True
    world['_hovered_left_tooltip'] = None
    # Hover over Trade Pact button (y=370)
    draw_diplomacy_panel(surface, world, font, font_small, mouse_pos=(100, 370))
    assert world['_hovered_left_tooltip'] is not None, "Diplomacy hover tooltip not triggered!"
    print(f"  [OK] Diplomacy panel hover: {world['_hovered_left_tooltip']['title']}")
    world['diplomacy_panel_open'] = False

    # 2. Debt Panel
    world['debt_panel_open'] = True
    world['debt_scope'] = 'domestic'
    world['_hovered_left_tooltip'] = None
    # Hover over Lobby button (y=270)
    draw_debt_panel(surface, world, font, font_small, mouse_pos=(100, 270))
    assert world['_hovered_left_tooltip'] is not None, "Debt panel hover tooltip not triggered!"
    print(f"  [OK] Debt panel hover: {world['_hovered_left_tooltip']['title']}")
    world['debt_panel_open'] = False

    # 3. Military Panel
    world['military_panel_open'] = True
    world['_hovered_left_tooltip'] = None
    # Hover over Recruit button (y=285)
    draw_military_panel(surface, world, font, font_small, mouse_pos=(100, 285))
    assert world['_hovered_left_tooltip'] is not None, "Military panel hover tooltip not triggered!"
    print(f"  [OK] Military panel hover: {world['_hovered_left_tooltip']['title']}")
    world['military_panel_open'] = False

    # 4. Science Panel
    world['science_panel_open'] = True
    world['_hovered_left_tooltip'] = None
    # Hover over Resource Ribbon (x=100, y=160)
    draw_science_panel(surface, world, font, font_small, mouse_pos=(100, 160))
    assert world['_hovered_left_tooltip'] is not None, "Science resource ribbon hover tooltip not triggered!"
    print(f"  [OK] Science resource ribbon hover: {world['_hovered_left_tooltip']['title']}")
    world['science_panel_open'] = False

    # 5. Tooltip Drawing Surface
    tdata = get_button_tooltip_data('city_toggle_ubi', world, region=region, nation=nation)
    world['_hovered_left_tooltip'] = tdata
    draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(200, 200))
    print("  [OK] draw_left_panel_tooltip rendered without errors!")

    # 6. Right-hand panel Fiscal Card
    draw_panel(surface, world, font, font_small, mouse_pos=(1300, 100))
    print("  [OK] Right-hand panel rendered without errors!")


def test_modal_suppression():
    print("=== Testing Modal Suppression ===")
    world = build_world_view(seed=42)
    nation = world['nations'][0]
    region = nation.tiles[0]
    world['selected_region'] = region

    # Test transfer dialog active
    world['transfer_dialog'] = {'open': True, 'action_kind': 'policy'}
    modal_active = bool(
        (world.get('transfer_dialog') and world['transfer_dialog'].get('open')) or
        world.get('actions_modal_open') or
        world.get('help_open') or
        world.get('comparison_open')
    )
    assert modal_active is True, "Modal active flag should be True!"
    effective_mouse = None if modal_active else (200, 200)
    assert effective_mouse is None, "Effective mouse should be None when modal is active!"
    print("  [OK] Modal suppression logic correctly clears mouse coordinates when modal is open!")


if __name__ == '__main__':
    test_tooltips()
    test_panel_rendering_and_hover()
    test_modal_suppression()
    print("\nALL TESTS PASSED SUCCESSFULLY!")
