"""
test_all_chart_tooltips.py — Comprehensive Automated Test for Chart & Tab Tooltips.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
import pygame
pygame.init()

from worldview_engine import build_world_view
from worldview_camera import WIDTH, HEIGHT
from worldview_tooltips import get_button_tooltip_data, draw_left_panel_tooltip
from worldview import get_font
from worldview_layers import draw_layer_sidebar

def test_tooltips():
    world = build_world_view(seed=42)
    font_small = get_font(22)
    surface = pygame.Surface((WIDTH, HEIGHT))

    region = world['tiles'][0]
    nation = world['nations'][0]

    # 1. Test 10 Sidebar Charts
    print("1. Testing 10 Sidebar Charts:")
    for idx in range(1, 11):
        btn_id = f"chart_{idx}"
        tdata = get_button_tooltip_data(btn_id, world, region=region, nation=nation)
        assert tdata is not None, f"Failed tooltip lookup for {btn_id}"
        assert 'title' in tdata and 'desc' in tdata and 'stats' in tdata
        print(f"  [OK] {btn_id}: {tdata['title']} (Badge: {tdata['badge']})")
        # Test rendering
        tdata['btn_rect'] = (1100, 200 + idx * 30, 120, 60)
        world['_hovered_left_tooltip'] = tdata
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(1100, 200))

    # 2. Test Citizen Tabs, Scopes, Modes, and 4 Charts
    print("\n2. Testing Citizen Tabs & Visualizations:")
    citizen_keys = [
        'tab_charts',
        'tab_citizens',
        'citizen_scope_tile',
        'citizen_scope_nation',
        'citizen_subtab_class',
        'citizen_subtab_labor',
        'citizen_mode_charts',
        'citizen_mode_pyramid',
        'citizen_chart_1',
        'citizen_chart_2',
        'citizen_chart_3',
        'citizen_chart_4',
        'citizen_viz_pyramid',
        'citizen_viz_lorenz',
    ]
    for c_key in citizen_keys:
        tdata = get_button_tooltip_data(c_key, world, region=region, nation=nation)
        assert tdata is not None, f"Failed tooltip lookup for {c_key}"
        assert 'title' in tdata and 'desc' in tdata
        print(f"  [OK] {c_key}: {tdata['title']} (Badge: {tdata['badge']})")
        tdata['btn_rect'] = (1100, 300, 140, 40)
        world['_hovered_left_tooltip'] = tdata
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(1100, 300))

    # 3. Test Labor Buttons, Radar & Charts
    print("\n3. Testing Labor Policy Buttons, Radar & Charts:")
    labor_keys = [
        'labor_workday_down',
        'labor_workday_up',
        'labor_subsidize_spectacle',
        'labor_mode_charts',
        'labor_mode_radar',
        'labor_chart_1',
        'labor_chart_2',
        'labor_chart_3',
        'labor_chart_4',
        'radar_axis_0',
        'radar_axis_1',
        'radar_axis_2',
        'radar_axis_3',
    ]
    for l_key in labor_keys:
        tdata = get_button_tooltip_data(l_key, world, region=region, nation=nation)
        assert tdata is not None, f"Failed tooltip lookup for {l_key}"
        assert 'title' in tdata and 'desc' in tdata
        print(f"  [OK] {l_key}: {tdata['title']} (Badge: {tdata['badge']})")
        tdata['btn_rect'] = (1100, 400, 140, 40)
        world['_hovered_left_tooltip'] = tdata
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(1100, 400))

    # 4. Test Comparison Suite Tabs & Filters
    print("\n4. Testing Comparison Suite Tabs & Filters:")
    compare_keys = [
        'compare_tab_1',
        'compare_tab_2',
        'compare_tab_3',
        'compare_tab_4',
        'compare_tab_5',
        'compare_filter_food',
        'compare_filter_wood',
        'compare_filter_furniture',
    ]
    for cmp_key in compare_keys:
        tdata = get_button_tooltip_data(cmp_key, world, region=region, nation=nation)
        assert tdata is not None, f"Failed tooltip lookup for {cmp_key}"
        assert 'title' in tdata and 'desc' in tdata
        print(f"  [OK] {cmp_key}: {tdata['title']} (Badge: {tdata['badge']})")
        tdata['btn_rect'] = (300, 100, 200, 32)
        world['_hovered_left_tooltip'] = tdata
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(300, 100))

    # 5. Test Comparison Tab 4: Extraction Matrix & Circuits
    print("\n5. Testing Tab 4 Extraction Matrix & Circuits Tooltips:")
    ext_keys = [
        'compare_ext_scope_country',
        'compare_ext_scope_province',
        'compare_ext_scope_city',
        'compare_ext_mode_table',
        'compare_ext_mode_circuit',
        'hdr_ext_tribute',
        'hdr_ext_rent',
        'hdr_ext_surplus',
        'hdr_ext_exploit',
        'hdr_ext_tax_muni',
        'hdr_ext_tax_prov',
        'hdr_ext_tax_sov',
        'hdr_ext_total_ext',
        'hdr_ext_wear',
        'hdr_ext_alien',
        'circuit_nation_btn',
        'trpf_curve_plot',
    ]
    for ext_key in ext_keys:
        tdata = get_button_tooltip_data(ext_key, world, region=region, nation=nation)
        assert tdata is not None, f"Failed tooltip lookup for {ext_key}"
        assert 'title' in tdata and 'desc' in tdata
        print(f"  [OK] {ext_key}: {tdata['title']} (Badge: {tdata['badge']})")
        tdata['btn_rect'] = (350, 180, 100, 26)
        world['_hovered_left_tooltip'] = tdata
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(350, 180))

    # 6. Test Comparison Tab 5: Grievance Matrix & Rebellion Attractor
    print("\n6. Testing Tab 5 Grievance Matrix & Attractor Tooltips:")
    protest_keys = [
        'compare_protest_scope_country',
        'compare_protest_scope_province',
        'compare_protest_scope_city',
        'compare_protest_mode_table',
        'compare_protest_mode_attractor',
        'hdr_protest_score',
        'hdr_protest_shifts',
        'hdr_protest_rent',
        'hdr_protest_food',
        'hdr_protest_strikes',
        'hdr_protest_taxes',
        'hdr_protest_driver',
        'attractor_hazard_zone',
    ]
    for pr_key in protest_keys:
        tdata = get_button_tooltip_data(pr_key, world, region=region, nation=nation)
        assert tdata is not None, f"Failed tooltip lookup for {pr_key}"
        assert 'title' in tdata and 'desc' in tdata
        print(f"  [OK] {pr_key}: {tdata['title']} (Badge: {tdata['badge']})")
        tdata['btn_rect'] = (400, 220, 100, 26)
        world['_hovered_left_tooltip'] = tdata
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(400, 220))

    # 7. Test Governance Panel: Electoral Barometer
    print("\n7. Testing Governance Electoral Barometer Tooltip:")
    gov_keys = ['gov_electoral_barometer']
    for g_key in gov_keys:
        tdata = get_button_tooltip_data(g_key, world, region=region, nation=nation)
        assert tdata is not None, f"Failed tooltip lookup for {g_key}"
        assert 'title' in tdata and 'desc' in tdata
        print(f"  [OK] {g_key}: {tdata['title']} (Badge: {tdata['badge']})")
        tdata['btn_rect'] = (20, 500, 260, 30)
        world['_hovered_left_tooltip'] = tdata
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(20, 500))

    # 8. Test Map Layers 1 through 8
    print("\n8. Testing Map Layers 1-8 Tooltips & Hover Dock:")
    layer_keys = [
        'layer_overview',
        'layer_physical',
        'layer_population',
        'layer_economy',
        'layer_production',
        'layer_military',
        'layer_enclosure',
        'layer_exploitation',
    ]
    for lay_key in layer_keys:
        tdata = get_button_tooltip_data(lay_key, world, region=region, nation=nation)
        assert tdata is not None, f"Failed tooltip lookup for {lay_key}"
        assert 'title' in tdata and 'desc' in tdata
        print(f"  [OK] {lay_key}: {tdata['title']} (Badge: {tdata['badge']})")
        tdata['btn_rect'] = (14, 500, 184, 32)
        world['_hovered_left_tooltip'] = tdata
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=(14, 500))

    # Test layer sidebar hover triggering tooltip assignment
    world['layers_collapsed'] = False
    world['_hovered_left_tooltip'] = None
    # Hover over Layer 8 (Exploitation at y=783..815)
    draw_layer_sidebar(surface, world, font_small, mouse_pos=(50, 790))
    hovered = world.get('_hovered_left_tooltip')
    assert hovered is not None, "draw_layer_sidebar failed to set _hovered_left_tooltip when mouse hovered a layer button!"
    assert 'Layer' in hovered['title'] or 'Exploitation' in hovered['title']
    print(f"  [OK] draw_layer_sidebar hover successfully triggered: {hovered['title']}")

    print("\nALL 60+ BUTTON, MODE, SCOPE, HEADER, RADAR, ATTRACTOR, CIRCUIT & LAYER TOOLTIPS VERIFIED SUCCESSFULLY!")

if __name__ == '__main__':
    test_tooltips()
