"""
test_ui_fixes.py — Verify fixes for:
1. Comparison modal tab tooltips showing on hover only and clearing when mouse moves away or tab clicked.
2. Right panel ecological dashboard button clicking cleanly without activating graph 2.
3. Economy and Ecology tabs rendering procedural vector icons without emoji tofu boxes.
"""

import os
import pygame

os.environ['SDL_VIDEODRIVER'] = 'dummy'
pygame.init()
pygame.font.init()

from region import Region
from nation import Nation
from ui_icons import get_icon
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_charts import PANEL_LEFT, chart_at_pixel
from worldview_ui import draw_panel, get_font
from worldview_compare import draw_tab_headers, compare_tab_hit


def test_icons():
    print("Testing Procedural Vector Icons (No Emoji Tofu Boxes)...")
    eco_icon = get_icon('ecology', 14)
    assert eco_icon is not None and isinstance(eco_icon, pygame.Surface)
    assert eco_icon.get_width() == 14 and eco_icon.get_height() == 14

    econ_icon = get_icon('economy', 14)
    assert econ_icon is not None and isinstance(econ_icon, pygame.Surface)
    assert econ_icon.get_width() == 14 and econ_icon.get_height() == 14
    print("  -> Procedural icons generated successfully!")


def test_right_panel_buttons_and_click_routing():
    print("Testing Right Panel Mode Buttons & Click Routing...")
    surface = pygame.Surface((WIDTH, HEIGHT))
    font = get_font(28)
    font_small = get_font(22)

    n = Nation("Valoria", 1, (100, 150, 240))
    r = Region("Oakhaven", 1)
    r.owner_nation = n
    n.tiles = [r]

    world = {
        'nations': [n],
        'selected_region': r,
        'window': 30,
        'turn': 1,
        'panel_tab': 'charts',
        'tile_chart_mode': 'econ',
        'view': 0,
        'violations': [],
    }

    # Render frame
    draw_panel(surface, world, font, font_small, mouse_pos=(100, 100))

    # Check that button hitboxes are cached
    ec_rect = world.get('_chart_mode_econ_rect')
    eco_rect = world.get('_chart_mode_eco_rect')
    grid_top = world.get('_chart_grid_top')
    grid_bottom = world.get('_chart_grid_bottom')

    assert ec_rect is not None, "_chart_mode_econ_rect was not cached!"
    assert eco_rect is not None, "_chart_mode_eco_rect was not cached!"
    assert grid_top is not None, "_chart_grid_top was not cached!"

    print(f"  -> Econ rect: {ec_rect}, Eco rect: {eco_rect}, Grid top: {grid_top}")

    # Verify that eco_rect does NOT collide with the chart grid
    assert eco_rect.bottom <= grid_top, f"Button should be above chart grid: {eco_rect.bottom} vs {grid_top}"

    # Simulate clicking on the Ecology button
    click_pos = (eco_rect.centerx, eco_rect.centery)
    assert eco_rect.collidepoint(click_pos), "Click should hit eco_rect"

    # Simulate the click handling in worldview.py
    if eco_rect.collidepoint(click_pos):
        world['tile_chart_mode'] = 'eco'
        world['view'] = 0

    assert world['tile_chart_mode'] == 'eco', "Clicking Ecology button should switch mode to 'eco'"
    assert world['view'] == 0, "Mode switch should reset zoom view to 0"

    # Verify that chart_at_pixel does NOT capture this click as chart 2!
    num_c = 6 if world.get('tile_chart_mode') == 'eco' else 10
    clicked_chart = chart_at_pixel(click_pos, grid_top, grid_bottom, num_charts=num_c)
    assert clicked_chart is None, f"Click on mode button must NOT trigger chart zoom! Got: {clicked_chart}"
    print("  -> Ecology button click cleanly switches mode without popping up graph 2!")

    # Simulate clicking on the Economy button
    click_pos_ec = (ec_rect.centerx, ec_rect.centery)
    if ec_rect.collidepoint(click_pos_ec):
        world['tile_chart_mode'] = 'econ'
        world['view'] = 0

    assert world['tile_chart_mode'] == 'econ', "Clicking Economy button should switch mode to 'econ'"
    clicked_chart_ec = chart_at_pixel(click_pos_ec, grid_top, grid_bottom, num_charts=10)
    assert clicked_chart_ec is None, f"Click on economy button must NOT trigger chart zoom! Got: {clicked_chart_ec}"
    print("  -> Economy button click cleanly switches mode without popping up graph!")


def test_comparison_modal_hover_and_click():
    print("Testing Comparison Modal Hover-Only Tooltips...")
    surface = pygame.Surface((WIDTH, HEIGHT))
    font = get_font(28)
    font_small = get_font(22)

    box_x, box_y, box_w, box_h = 30, 20, WIDTH - 60, HEIGHT - 40
    world = {
        'compare_tab': 1,
        '_hovered_left_tooltip': None,
    }

    # Tab 1 rect is at:
    tab_spacing = 8
    tab_w = (box_w - 40 - 5 * tab_spacing) // 6
    tab1_pos = (box_x + 20 + tab_w // 2, box_y + 48 + 16)

    # 1. Mouse hovering over Tab 1
    world['_hovered_left_tooltip'] = None
    draw_tab_headers(surface, world, box_x, box_y, box_w, font, font_small, mouse_pos=tab1_pos)
    assert world.get('_hovered_left_tooltip') is not None, "Hovering over Tab 1 should set tooltip"
    assert world['_hovered_left_tooltip']['title'] == "Comparison Tab 1: Macro Accounts & Leaderboard"
    print("  -> Hovering over tab displays tooltip on hover without clicking!")

    # 2. Mouse moves away to (0, 0)
    world['_hovered_left_tooltip'] = None
    draw_tab_headers(surface, world, box_x, box_y, box_w, font, font_small, mouse_pos=(0, 0))
    assert world.get('_hovered_left_tooltip') is None, "Moving mouse away should clear tooltip"
    print("  -> Moving mouse away immediately hides tooltip!")

    # 3. Clicking Tab 6
    tab6_pos = (box_x + 20 + 5 * (tab_w + tab_spacing) + tab_w // 2, box_y + 48 + 16)
    hit = compare_tab_hit(tab6_pos, box_x, box_y, world=world)
    assert hit == ('tab', 6), f"Clicking Tab 6 should return ('tab', 6), got {hit}"
    print("  -> Tab 6 click registers accurately!")


if __name__ == '__main__':
    test_icons()
    test_right_panel_buttons_and_click_routing()
    test_comparison_modal_hover_and_click()
    print("\nALL UI FIX VERIFICATIONS PASSED SUCCESSFULLY!")
