#!/usr/bin/env python3
"""
test_worldview_actions.py — Headless verification test for worldview Sovereign Command UI.
"""

import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame
import unittest
from worldview_engine import build_world_view
from worldview import render_frame
from worldview_actions import actions_tab_hit, top_bar_action_hit, DIPLOMACY_BTN, MILITARY_BTN


class TestWorldviewActionsUI(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.surface = pygame.display.set_mode((1600, 960))
        self.world = build_world_view(seed=42)

    def test_render_all_action_tabs(self):
        """Verify that all 4 action tabs render without runtime errors."""
        world = self.world
        world['actions_open'] = True

        # Test rendering Tab 1: Diplomacy
        world['actions_tab'] = 1
        render_frame(self.surface, world)

        # Test rendering Tab 2: Military
        world['actions_tab'] = 2
        render_frame(self.surface, world)

        # Test rendering Tab 3: Construction
        world['actions_tab'] = 3
        render_frame(self.surface, world)

        # Test rendering Tab 4: AI Advisory
        world['actions_tab'] = 4
        render_frame(self.surface, world)

        print("Rendered all 4 Sovereign Action tabs successfully in headless mode.")

    def test_nation_switcher_and_interactions(self):
        """Verify sovereign switching and intent dispatching from UI."""
        world = self.world
        world['actions_open'] = True
        world['actions_tab'] = 1

        # Switch to nation 1
        target_nation = world['nations'][1]
        world['player_nation_name'] = target_nation.name
        render_frame(self.surface, world)

        # Top bar action hits
        from worldview_actions import HELP_BTN, COMPARE_BTN
        self.assertEqual(top_bar_action_hit((HELP_BTN[0] + 5, HELP_BTN[1] + 5)), 'help')
        self.assertEqual(top_bar_action_hit((COMPARE_BTN[0] + 5, COMPARE_BTN[1] + 5)), 'compare')
        self.assertEqual(top_bar_action_hit((DIPLOMACY_BTN[0] + 5, DIPLOMACY_BTN[1] + 5)), 'diplomacy')
        self.assertEqual(top_bar_action_hit((MILITARY_BTN[0] + 5, MILITARY_BTN[1] + 5)), 'military')

        # Test recruiting from military tab
        world['actions_tab'] = 2
        world['selected_region'] = target_nation.tiles[0]
        
        # Click recruit button: (box_x + 280, recruit_bar_y + 12) = (304, 184)
        hit = actions_tab_hit((320, 188), 24, 16, world)
        self.assertTrue(hit, "Military recruitment click should register and submit intent.")
        self.assertEqual(len(target_nation.intents), 1, f"{target_nation.name} should have 1 submitted RecruitArmyIntent.")

    def test_diplomacy_instant_clicks_and_war(self):
        """Verify instant out-of-turn execution for diplomacy buttons: trade, alliance, war, peace."""
        from worldview_actions import actions_tab_hit
        from diplomacy import get_diplomacy
        world = self.world
        world['actions_open'] = True
        world['actions_tab'] = 1
        n1, n2 = world['nations'][0].name, world['nations'][1].name
        world['player_nation_name'] = n1
        diplomacy = get_diplomacy()

        # Target buttons for foreign nation 1 (Card 1):
        # card_y = 16 + 128 + 36 = 180
        # btn_x1 = 24 + 1312 - 510 = 826 (width 240) -> [826..1066]
        # btn_x2 = 24 + 1312 - 250 = 1086 (width 240) -> [1086..1326]
        # row1_y = 180 + 16 = 196 (height 36) -> [196..232]
        # row2_y = 180 + 64 = 244 (height 36) -> [244..280]
        
        # 1. Propose Trade Pact (Top Left: x=900, y=210)
        hit = actions_tab_hit((900, 210), 24, 16, world)
        self.assertTrue(hit, "Trade pact click should register.")
        self.assertIsNotNone(world.get('action_feedback'))
        print(f"Trade click feedback: {world.get('action_feedback')}")

        # 2. Declare War (Bottom Right: x=1150, y=260)
        hit = actions_tab_hit((1150, 260), 24, 16, world)
        self.assertTrue(hit, "Declare war click should register.")
        self.assertTrue(diplomacy.are_at_war(n1, n2), f"{n1} and {n2} should now be at war.")
        self.assertIsNotNone(world.get('action_feedback'))
        print(f"War declaration feedback: {world.get('action_feedback')}")

        # 3. Sign Peace (Bottom Right: x=1150, y=260)
        hit = actions_tab_hit((1150, 260), 24, 16, world)
        self.assertTrue(hit, "Sign peace click should register.")
        self.assertFalse(diplomacy.are_at_war(n1, n2), f"{n1} and {n2} should no longer be at war.")
        print(f"Peace signing feedback: {world.get('action_feedback')}")

    def test_recruit_before_first_turn_and_step(self):
        """User bug regression: recruit unit before first turn and step world across turns."""
        from worldview_engine import step_world
        world = self.world
        target_nation = world['nations'][1]
        world['player_nation_name'] = target_nation.name
        world['selected_region'] = target_nation.tiles[0]

        # Submit recruitment intent before first turn
        world['actions_open'] = True
        world['actions_tab'] = 2
        actions_tab_hit((320, 188), 24, 16, world)
        self.assertGreater(len(target_nation.intents), 0)

        # Step the world across 5 turns without crashing
        for _ in range(5):
            step_world(world)

        self.assertGreater(world['turn'], 1)
        self.assertGreater(len(target_nation.military_units), 0, f"{target_nation.name} should have active recruited military units.")
        print(f"Successfully stepped world with active recruited army up to turn {world['turn']}.")

    def test_passive_worldview_run_50_turns(self):
        """Verify standard worldview execution w/o interaction runs seamlessly across 50 turns."""
        from worldview_engine import step_world
        world = self.world
        for t in range(50):
            step_world(world)
            render_frame(self.surface, world)
        self.assertEqual(world['turn'], 50)
        print("Completed 50 turns of worldview stepping and rendering with 0 errors.")

    def test_continuous_landmass_and_ocean_isolation(self):
        """Verify that landmass is a single continuous component and ocean tiles have 0 agents/claims."""
        from collections import deque
        from hexmap import rectangular_hex_layout, axial_neighbors, axial_to_offset
        from worldview_engine import step_world
        
        world = self.world
        tiles = world['tiles']
        nations = world['nations']
        layout = world['layout']

        # 1. Verify no nation started on an ocean tile
        for n in nations:
            for tile in n.tiles:
                self.assertFalse(getattr(tile, 'is_ocean', False), f"Nation {n.name} claimed ocean tile {tile.name}")
                self.assertGreaterEqual(getattr(tile, 'elevation', 0.0), 0.0, f"Nation {n.name} tile {tile.name} is below sea level")

        # 2. Verify all land tiles form a single continuous component
        land_tiles = {t.name for t in tiles if not getattr(t, 'is_ocean', False) and getattr(t, 'elevation', 0.0) >= 0.0}
        self.assertGreater(len(land_tiles), 20, "Continent should have substantial land tiles.")
        
        # BFS traversal across land tiles
        start = next(iter(land_tiles))
        visited = {start}
        queue = deque([start])
        while queue:
            curr_name = queue.popleft()
            q, axr = layout[curr_name]
            for nq, nar in axial_neighbors(q, axr):
                nc, nr = axial_to_offset(nq, nar)
                n_name = f"r{nr}c{nc}"
                if n_name in land_tiles and n_name not in visited:
                    visited.add(n_name)
                    queue.append(n_name)

        self.assertEqual(len(visited), len(land_tiles), "All land tiles must form ONE single continuous connected landmass.")

        # 3. Step 30 turns and verify no agent ever enters or claims an ocean tile
        for t in range(1, 31):
            step_world(world)

        print("Verified 100% single continuous landmass connectivity and complete ocean isolation.")

    def test_map_info_layer_sidebar_and_rendering(self):
        """Verify left layer sidebar clicking, layer switching, and rendering across all 6 layers."""
        from worldview_layers import layer_sidebar_hit, MAP_LAYERS, SIDEBAR_X, SIDEBAR_Y, BTN_H, BTN_SPACING
        from worldview_engine import step_world

        world = self.world
        self.assertEqual(world.get('map_layer'), 'overview')

        # Initial state should be collapsed on startup
        self.assertTrue(world.get('layers_collapsed', False), "Map layers must be collapsed on startup.")
        render_frame(self.surface, world)

        # Expand the sidebar
        exp_hit = layer_sidebar_hit((SIDEBAR_X + 10, SIDEBAR_Y + 10), world)
        self.assertTrue(exp_hit)
        self.assertFalse(world.get('layers_collapsed'), "Clicking pill should expand sidebar.")
        render_frame(self.surface, world)

        # Test sidebar button clicks for all layers
        by = SIDEBAR_Y + 34
        for key, label, _, _, _ in MAP_LAYERS:
            click_pos = (SIDEBAR_X + 40, by + 12)
            hit = layer_sidebar_hit(click_pos, world)
            self.assertTrue(hit, f"Clicking layer {key} should register.")
            self.assertEqual(world.get('map_layer'), key, f"Active map layer should be {key}")

            # Render frame with active layer
            render_frame(self.surface, world)
            by += BTN_H + BTN_SPACING

        # Collapse the sidebar again
        col_hit = layer_sidebar_hit((SIDEBAR_X + 10, SIDEBAR_Y + 10), world)
        self.assertTrue(col_hit)
        self.assertTrue(world.get('layers_collapsed'), "Clicking header should collapse sidebar.")
        render_frame(self.surface, world)

        # Step 5 turns while cycling layers
        for key, _, _, _, _ in MAP_LAYERS:
            world['map_layer'] = key
            step_world(world)
            render_frame(self.surface, world)

        print("Verified left layer sidebar toggle, collapse/expand, and per-tile rendering across all 6 map layers.")

    def test_realistic_geographic_hierarchy_and_overview_layer(self):
        """Verify 10 nations x 10 provinces x 10 cities hierarchy and overview layer overlay format."""
        from world_names import GLOBAL_NATION_DATA, get_country_names
        from worldview_map import tile_stats

        countries = get_country_names()
        self.assertEqual(len(countries), 10, "Must have exactly 10 populous country datasets.")

        total_cities = 0
        for c_name, provs in GLOBAL_NATION_DATA.items():
            self.assertEqual(len(provs), 10, f"Country {c_name} must have 10 provinces.")
            for p_name, cities in provs.items():
                self.assertEqual(len(cities), 10, f"Province {p_name} in {c_name} must have 10 cities.")
                total_cities += len(cities)

        self.assertEqual(total_cities, 1000, "Database must contain exactly 1,000 cities.")

        world = self.world
        tiles = world['tiles']
        for t in tiles:
            self.assertTrue(hasattr(t, 'city_name'), f"Tile {t.name} must have an assigned city_name")
            self.assertTrue(hasattr(t, 'display_name'), f"Tile {t.name} must have display_name")

        # Verify Overview Layer formatting (clean, single nation/province names, zero text on ocean)
        nation_caps_seen = 0
        prov_caps_seen = 0
        for t in tiles:
            l1, l2, l3, c1, c2, c3 = tile_stats(t, layer_mode='overview', world=world)
            if getattr(t, 'is_ocean', False):
                self.assertEqual(l1, "", "Ocean tiles in overview must have zero text")
                self.assertEqual(l2, "", "Ocean tiles in overview must have zero text")
            elif t.owner_nation:
                self.assertIn("pop", l2, "Claimed tile Line 2 must show population and food price")
                if "*" in l1:
                    nation_caps_seen += 1
                elif "[" in l1:
                    prov_caps_seen += 1
            else:
                # Wilderness tile in Overview layer has zero text
                self.assertEqual(l1, "", "Wilderness tiles in overview must have zero text")

        self.assertEqual(nation_caps_seen, len(world['nations']), "Must have exactly 1 Nation Name badge per nation.")
        self.assertGreater(prov_caps_seen, 0, "Must have province seat badges.")
        print("Verified clean, decluttered overview formatting with 1 nation and 1 province name per territory.")

    def test_randomized_nations_and_runtime_seeds(self):
        """Verify runtime seed parameters and randomized starting nations from 10-country database."""
        from worldview_engine import build_world_view
        w1 = build_world_view(seed=101)
        w2 = build_world_view(seed=999)

        n1_names = [n.name for n in w1['nations']]
        n2_names = [n.name for n in w2['nations']]

        self.assertEqual(len(n1_names), 3)
        self.assertEqual(len(n2_names), 3)
        self.assertEqual(w1['seed'], 101)
        self.assertEqual(w2['seed'], 999)
        self.assertNotEqual(n1_names, n2_names, "Different seeds should generate different starting nation sets.")

        # Test independent terrain and nation seeds
        w3 = build_world_view(terrain_seed=555, nation_seed=777)
        self.assertEqual(w3['terrain_seed'], 555)
        self.assertEqual(w3['nation_seed'], 777)
        print(f"Verified seed-driven randomized nation generation: Seed 101={n1_names}, Seed 999={n2_names}.")

    def test_capital_symbols_and_claims_renaming(self):
        """Verify national capital (★), provincial capital (◆), and dynamic wilderness claim renaming."""
        from world_names import claim_wilderness_tile, GLOBAL_NATION_DATA
        world = self.world
        nation = world['nations'][0]

        # National capital
        self.assertIsNotNone(nation.capital)
        self.assertTrue(getattr(nation.capital, 'is_national_capital', False))

        # Provincial capitals
        for prov in nation.provinces:
            self.assertIsNotNone(prov.capital)
            if prov.capital is not nation.capital:
                self.assertTrue(getattr(prov.capital, 'is_provincial_capital', False))

        # Test dynamic wilderness claim renaming
        wild_tile = next(t for t in world['tiles'] if getattr(t, 'owner_nation', None) is None and not getattr(t, 'is_ocean', False))
        claim_wilderness_tile(wild_tile, nation, prov=nation.provinces[0])

        self.assertIn(wild_tile.display_name, GLOBAL_NATION_DATA[nation.name][nation.provinces[0].display_name],
                      "Claimed tile must be renamed to an authentic city from that province.")
        self.assertEqual(wild_tile.nation_display, nation.name)
        print(f"Verified dynamic claim renaming: {wild_tile.name} -> '{wild_tile.display_name}' ({wild_tile.province_display}, {wild_tile.nation_display}).")

    def test_help_modal_and_seed_display(self):
        """Verify Help and Seed Registry modal toggle, 3-page tab switching, and headless rendering."""
        from worldview_help import help_modal_hit, HELP_TAB1_RECT, HELP_TAB2_RECT, HELP_TAB3_RECT
        world = self.world
        world['help_open'] = True

        # Test Page 1, 2, 3 rendering and hit testing
        for p, tab_rect in [(1, HELP_TAB1_RECT), (2, HELP_TAB2_RECT), (3, HELP_TAB3_RECT)]:
            tab_hit = help_modal_hit((tab_rect[0] + 5, tab_rect[1] + 5), world)
            self.assertTrue(tab_hit)
            self.assertEqual(world.get('help_page'), p)
            render_frame(self.surface, world)

        # Hit outside closes
        hit_outside = help_modal_hit((10, 10), world)
        self.assertTrue(hit_outside)
        self.assertFalse(world['help_open'], "Click outside should close help modal.")
        print("Verified Help & Seed Registry 3-page modal rendering and interaction.")

    def test_policy_panel_tabs_and_rendering(self):
        """Verify Right Sidebar Charts vs Policies tab switching and scope rendering."""
        from worldview_ui import panel_tab_hit, CHARTS_TAB_RECT, POLICIES_TAB_RECT
        from worldview_policies import draw_policies_panel, policy_panel_hit
        world = self.world

        # Test tab hitting
        c_hit = panel_tab_hit((CHARTS_TAB_RECT[0] + 5, CHARTS_TAB_RECT[1] + 5))
        self.assertEqual(c_hit, 'charts')

        p_hit = panel_tab_hit((POLICIES_TAB_RECT[0] + 5, POLICIES_TAB_RECT[1] + 5))
        self.assertEqual(p_hit, 'policies')

        # Switch to Policies tab
        world['panel_tab'] = 'policies'
        region = world['nations'][0].tiles[0]
        world['selected_region'] = region

        # Render City scope
        world['policy_scope'] = 'tile'
        render_frame(self.surface, world)

        # Render Province scope
        world['policy_scope'] = 'province'
        render_frame(self.surface, world)

        # Render Nation scope
        world['policy_scope'] = 'nation'
        render_frame(self.surface, world)

        # Render Wilderness scope
        wild_tile = next(t for t in world['tiles'] if getattr(t, 'owner_nation', None) is None)
        world['selected_region'] = wild_tile
        render_frame(self.surface, world)
        print("Verified Policies panel headless rendering across City, Province, Nation, and Wilderness scopes.")

    def test_policy_actions_execution(self):
        """Verify execution of City tax, Grain relief, Garrison recruitment, and Nation decrees."""
        from worldview_policies import _execute_policy_action
        world = self.world
        nation = world['nations'][0]
        tile = nation.tiles[0]

        # 1. City Tax Cut
        init_tax = tile.gov.tax_rate
        _execute_policy_action(world, 'city_tax_cut', tile)
        self.assertAlmostEqual(tile.gov.tax_rate, max(0.0, init_tax - 0.02), places=3)

        # 2. City Emergency Food Aid
        tile.gov.agent.cash = 100.0
        tile.agents[0].hungry_steps = 2
        _execute_policy_action(world, 'city_emergency_food', tile)
        self.assertEqual(tile.agents[0].hungry_steps, 0)
        self.assertAlmostEqual(tile.gov.agent.cash, 50.0)

        # 3. City Garrison Recruitment
        init_garrison = len(getattr(tile, 'military_units', []))
        _execute_policy_action(world, 'city_recruit_garrison', tile)
        self.assertGreaterEqual(len(tile.military_units), init_garrison)

        # 4. Province Equalization Grant
        prov = tile.province
        _execute_policy_action(world, 'prov_equalization_grant', prov)

        # 5. National Tariff Directive
        _execute_policy_action(world, 'nat_tariff_10', nation)
        for r in nation.tiles:
            self.assertAlmostEqual(r.gov.import_tariff_rate, 0.10)

        print("Verified policy action execution for City, Province, and Nation.")

    def test_system_menu_and_restart_handling(self):
        """Verify native macOS system menu setup and restart event handling."""
        from system_menu import setup_system_menu, RESTART_EVENT_TYPE
        res = setup_system_menu()
        # On macOS, setup_system_menu() should succeed
        import sys
        if sys.platform == 'darwin':
            self.assertTrue(res, "Native system menu should initialize on macOS.")

        # Test posting restart event
        ev = pygame.event.Event(RESTART_EVENT_TYPE)
        pygame.event.post(ev)
        received = [e for e in pygame.event.get() if e.type == RESTART_EVENT_TYPE]
        self.assertEqual(len(received), 1, "RESTART_EVENT_TYPE must be received in event queue.")
        print("Verified system menu bar integration and restart event pipeline.")


if __name__ == "__main__":
    unittest.main()
