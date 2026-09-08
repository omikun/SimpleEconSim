"""
scratch/test_all_visualizations.py — Comprehensive Headless Verification of all 7 Visualizations:

1. Circuit of Capital Sankey (M -> C -> P -> C' -> M')
2. 4D Alienation Spider Chart (Product, Process, Nature, Species)
3. TRPF Curve & Organic Composition (c/v)
4. Rebellion Attractor 2D Phase-Space Plot
5. Electoral Struggle Tug-of-War Barometer
6. Class Wealth Pyramid & Lorenz Curve
7. Thematic Hex-Map Choropleth Layers (Layer 7 & 8)
"""

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["MPLCONFIGDIR"] = "/tmp"

import pygame
pygame.init()
pygame.font.init()

from worldview import build_world_view, step_world
from worldview_camera import WIDTH, HEIGHT
from worldview_ui import get_font
from worldview_compare import draw_nations_comparison, compare_tab_hit
from worldview_compare_extraction import draw_tab4_extraction
from worldview_compare_protest import draw_tab5_protest
from worldview_vis_circuits import draw_circuit_of_capital_sankey, draw_trpf_curve, circuit_sankey_hit
from worldview_vis_radar import draw_alienation_radar, draw_electoral_barometer, compute_alienation_4d
from worldview_vis_protest_attractor import draw_rebellion_attractor_phasespace
from worldview_vis_pyramid import draw_class_wealth_pyramid, draw_lorenz_curve
from worldview_citizens import draw_citizens_panel, citizen_panel_hit
from worldview_labor_ui import draw_labor_dashboard, labor_panel_hit
from worldview_gov_panel import draw_gov_panel
from worldview_map import draw_hex_map, tile_stats
from worldview_layers import draw_layer_sidebar, layer_sidebar_hit, MAP_LAYERS


def run_all_tests():
    print("Building world...")
    world = build_world_view(seed=42, terrain_seed=42, nation_seed=42)
    surface = pygame.Surface((WIDTH, HEIGHT))

    # Advance world 3 steps to generate history logs
    for _ in range(3):
        step_world(world)

    nation = world['nations'][0]
    region = nation.tiles[0]
    font = get_font(18)
    font_small = get_font(13)
    cell_font = get_font(16)
    section_font = get_font(20)

    # -------------------------------------------------------------
    # 1. Visualization 1 & 3: Circuit of Capital Sankey & TRPF Curve
    # -------------------------------------------------------------
    print("Testing 1 & 3: Circuit of Capital Sankey and TRPF Curve...")
    draw_circuit_of_capital_sankey(surface, world, 30, 40, WIDTH - 60, HEIGHT - 80, font, cell_font, section_font)
    draw_trpf_curve(surface, (50, 100, 400, 200), nation, font_small)
    # Test nation switcher hit
    nx = 30 + (WIDTH - 60) - 360
    hit = circuit_sankey_hit((nx + 10, 48), world, 30, 40, WIDTH - 60, HEIGHT - 80)
    assert hit is True, "Circuit sankey nation hit failed"

    # Test Tab 4 Circuit Mode toggle
    world['compare_open'] = True
    world['compare_tab'] = 4
    world['compare_ext_mode'] = 'table'
    draw_tab4_extraction(surface, world, 30, 96, WIDTH - 60, HEIGHT - 40, font, cell_font, section_font)
    # Toggle to circuit mode
    world['compare_ext_mode'] = 'circuit'
    draw_tab4_extraction(surface, world, 30, 96, WIDTH - 60, HEIGHT - 40, font, cell_font, section_font)
    print("  -> Passed Sankey & TRPF.")

    # -------------------------------------------------------------
    # 2. Visualization 2: 4D Alienation Spider / Radar Chart
    # -------------------------------------------------------------
    print("Testing 2: 4D Alienation Spider Chart...")
    a4d = compute_alienation_4d(region)
    assert 'product' in a4d and 'process' in a4d and 'nature' in a4d and 'species' in a4d
    assert all(0.0 <= v <= 1.0 for v in a4d.values())
    draw_alienation_radar(surface, (60, 60, 300, 280), region, font_small)
    draw_alienation_radar(surface, (60, 60, 300, 280), nation, font_small)

    # Test via labor dashboard sub-mode
    world['citizen_subtab'] = 'labor'
    world['labor_sub_mode'] = 'radar'
    draw_labor_dashboard(surface, world, region, font, font_small)
    print("  -> Passed 4D Alienation Radar.")

    # -------------------------------------------------------------
    # 3. Visualization 4: Rebellion Attractor Phase-Space Plot
    # -------------------------------------------------------------
    print("Testing 4: Rebellion Attractor Phase-Space Dynamic Plot...")
    draw_rebellion_attractor_phasespace(surface, (30, 40, WIDTH - 60, HEIGHT - 80), world, font, cell_font, section_font)
    for sc in ('country', 'province', 'city'):
        world['compare_protest_scope'] = sc
        draw_rebellion_attractor_phasespace(surface, (30, 40, WIDTH - 60, HEIGHT - 80), world, font, cell_font, section_font)

    # Test Tab 5 Attractor Mode toggle
    world['compare_tab'] = 5
    world['compare_protest_mode'] = 'table'
    draw_tab5_protest(surface, world, 30, 96, WIDTH - 60, HEIGHT - 40, font, cell_font, section_font)
    world['compare_protest_mode'] = 'attractor'
    draw_tab5_protest(surface, world, 30, 96, WIDTH - 60, HEIGHT - 40, font, cell_font, section_font)
    print("  -> Passed Rebellion Attractor.")

    # -------------------------------------------------------------
    # 4. Visualization 5: Electoral Struggle Tug-of-War Barometer
    # -------------------------------------------------------------
    print("Testing 5: Electoral Struggle & Capitalist Backlash Barometer...")
    draw_electoral_barometer(surface, (50, 50, 280, 80), nation, font_small)
    # Test under national governance panel
    world['gov_panel_open'] = True
    world['policy_scope'] = 'nation'
    world['selected_region'] = region
    draw_gov_panel(surface, world, font, font_small)
    print("  -> Passed Electoral Barometer in Gov Panel.")

    # -------------------------------------------------------------
    # 5. Visualization 6: Class Wealth Stratification Pyramid & Lorenz Curve
    # -------------------------------------------------------------
    print("Testing 6: Class Wealth Stratification Pyramid & Lorenz Curve...")
    draw_class_wealth_pyramid(surface, (50, 50, 280, 180), region, font_small)
    draw_class_wealth_pyramid(surface, (50, 50, 280, 180), nation, font_small)
    draw_lorenz_curve(surface, (50, 250, 280, 180), region, font_small)
    draw_lorenz_curve(surface, (50, 250, 280, 180), nation, font_small)

    # Test under Citizens panel
    world['panel_tab'] = 'citizens'
    world['citizen_subtab'] = 'class'
    world['citizen_class_mode'] = 'pyramid'
    draw_citizens_panel(surface, world, region, font, font_small)
    print("  -> Passed Wealth Pyramid & Lorenz Curve.")

    # -------------------------------------------------------------
    # 6. Visualization 7: Choropleth Layer Modes 7 & 8
    # -------------------------------------------------------------
    print("Testing 7: Thematic Hex-Map Choropleth Layer Modes 7 & 8...")
    assert any(k == 'enclosure' for k, *_ in MAP_LAYERS), "Layer 7 enclosure missing"
    assert any(k == 'exploitation' for k, *_ in MAP_LAYERS), "Layer 8 exploitation missing"

    # Test tile stats for Layer 7 & 8
    s7 = tile_stats(region, 'enclosure')
    assert "Commons" in s7[0] or "Feud" in s7[1]
    s8 = tile_stats(region, 'exploitation')
    assert "s/v" in s8[0]

    # Test rendering map in both layers
    world['map_layer'] = 'enclosure'
    draw_hex_map(surface, world, font, font_small)
    world['map_layer'] = 'exploitation'
    draw_hex_map(surface, world, font, font_small)

    # Test layer sidebar hit
    draw_layer_sidebar(surface, world, font_small)
    # Check that clicking layer 7 and 8 works
    world['layers_collapsed'] = False
    from worldview_layers import DOCK_Y
    by = DOCK_Y + 34
    # Layer 7 button is index 6
    hit7 = layer_sidebar_hit((50, by + 6 * 37 + 10), world)
    assert world['map_layer'] == 'enclosure', f"Expected enclosure, got {world['map_layer']}"
    hit8 = layer_sidebar_hit((50, by + 7 * 37 + 10), world)
    assert world['map_layer'] == 'exploitation', f"Expected exploitation, got {world['map_layer']}"
    print("  -> Passed Layer 7 & 8 Choropleth.")

    print("\nALL 7 VISUALIZATIONS VERIFIED SUCCESSFULLY!")


if __name__ == '__main__':
    run_all_tests()
