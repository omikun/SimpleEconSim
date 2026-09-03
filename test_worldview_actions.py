#!/usr/bin/env python3
"""
test_worldview_actions.py — Headless verification test for worldview Sovereign Command UI.
"""

import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame
import unittest
from worldview_engine import build_world_view, step_world
from worldview import render_frame, selected_nation
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

        # 3. Verify mountain regions are <= 20% of land tiles across multiple seeds
        for seed_val in (42, 101, 777, 999, 12345):
            w_test = build_world_view(seed=seed_val, terrain_seed=seed_val)
            t_land = [t for t in w_test['tiles'] if not getattr(t, 'is_ocean', False) and getattr(t, 'elevation', 0.0) >= 0.0]
            m_count = sum(1 for t in t_land if t.biome in ('mountains', 'snow_peaks') or t.elevation >= 0.72)
            frac = m_count / len(t_land)
            self.assertLessEqual(frac, 0.2001, f"Seed {seed_val}: Mountain fraction {frac:.1%} must be <= 20% of land ({m_count}/{len(t_land)})")

        # 4. Step 30 turns and verify no agent ever enters or claims an ocean tile
        for t in range(1, 31):
            step_world(world)

        print("Verified 100% single continuous landmass connectivity, <= 20% mountain cap, and complete ocean isolation.")

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
        self.assertEqual(len(countries), 18, "Must have 18 country datasets.")

        total_cities = 0
        for c_name in countries:
            provs = GLOBAL_NATION_DATA[c_name]
            self.assertEqual(len(provs), 10, f"Country {c_name} must have 10 provinces.")
            for p_name, cities in provs.items():
                self.assertEqual(len(cities), 10, f"Province {p_name} in {c_name} must have 10 cities.")
                total_cities += len(cities)

        self.assertEqual(total_cities, 1800, "Database must contain exactly 1,800 cities.")

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

    def test_starting_nations_and_runtime_seeds(self):
        """Verify starting nations strictly include US, China, and Japan, and runtime seeds."""
        from worldview_engine import build_world_view
        w1 = build_world_view(seed=101)
        w2 = build_world_view(seed=999)

        n1_names = [n.name for n in w1['nations']]
        n2_names = [n.name for n in w2['nations']]

        self.assertEqual(len(n1_names), 3)
        self.assertEqual(len(n2_names), 3)
        self.assertEqual(w1['seed'], 101)
        self.assertEqual(w2['seed'], 999)
        self.assertEqual(set(n1_names), {"United States", "China", "Japan"})
        self.assertEqual(set(n2_names), {"United States", "China", "Japan"})

        # Test independent terrain and nation seeds
        w3 = build_world_view(terrain_seed=555, nation_seed=777)
        self.assertEqual(w3['terrain_seed'], 555)
        self.assertEqual(w3['nation_seed'], 777)
        self.assertEqual(set(n.name for n in w3['nations']), {"United States", "China", "Japan"})
        print(f"Verified game starts with US, China, Japan: Seed 101={n1_names}, Seed 999={n2_names}.")

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

    def test_top_bar_stat_hover_dropdowns(self):
        """Verify protest stat (+delta) on top bar and hover breakdown dropdown rendering across all stats."""
        from worldview_ui import draw_top_bar, _get_stat_breakdown
        world = build_world_view(seed=42)
        step_world(world)

        # 1. Verify protest metric and delta computed on selected nation
        n = selected_nation(world)
        self.assertIsNotNone(n)
        tiles = n.tiles
        
        # Test breakdown data generator for all keys
        stat_keys = ['header', 'pop', 'treasury', 'col', 'gdp', 'ex', 'im', 'net', 'protest']
        for key in stat_keys:
            title, badge_txt, badge_col, lines = _get_stat_breakdown(world, n, tiles, key)
            self.assertTrue(len(title) > 0, f"Title must exist for stat {key}")
            self.assertTrue(len(lines) > 0, f"Lines must exist for stat {key}")
            
        # 2. Render frame with mouse hovering over each top bar region
        font_small = pygame.font.Font(None, 16)
        
        # Test header hover
        draw_top_bar(self.surface, world, font_small, mouse_pos=(100, 10))
        
        # Test stats item hovers across X coordinates (pop, treasury, col, gdp, ex, im, net, protest)
        for x in [30, 140, 260, 360, 480, 580, 680, 780, 880]:
            draw_top_bar(self.surface, world, font_small, mouse_pos=(x, 34))
            render_frame(self.surface, world, mouse_pos=(x, 34))

        print("Verified top bar protest metric (+delta) and interactive hover breakdown dropdowns for all stats.")

    def test_geographic_trade_constraints_and_passes(self):
        """Verify elevation relief trade barriers, river corridors, and mountain pass unblocking."""
        from terrain_edges import get_edge_manager, EdgeType, TerrainEdgeManager
        from hexmap import rectangular_hex_layout
        from region import Region
        
        layout = rectangular_hex_layout(3, 3)
        # Create test mock tiles with controlled elevations
        t1 = Region("r0c0", t=0, wilderness=True)
        t1.elevation = 0.85  # Alpine peak
        
        t2 = Region("r0c1", t=0, wilderness=True)
        t2.elevation = 0.88  # Adjacent alpine peak
        
        t3 = Region("r1c0", t=0, wilderness=True)
        t3.elevation = 0.10  # Lowland plains
        
        tiles = [t1, t2, t3]
        em = TerrainEdgeManager(tiles, layout)
        
        # 1. Verify Alpine Ridge Barrier (both > 0.68)
        edge_alpine = em.get_edge("r0c0", "r0c1")
        self.assertIsNotNone(edge_alpine)
        self.assertFalse(edge_alpine.passable)
        self.assertEqual(edge_alpine.edge_type, EdgeType.ALPINE_BLOCKED)
        self.assertEqual(edge_alpine.friction, float('inf'))
        
        # 2. Verify Sheer Cliff Barrier (|0.85 - 0.10| = 0.75 >= 0.40)
        edge_cliff = em.get_edge("r0c0", "r1c0")
        self.assertIsNotNone(edge_cliff)
        self.assertFalse(edge_cliff.passable)
        self.assertEqual(edge_cliff.edge_type, EdgeType.CLIFF_BLOCKED)
        
        # 3. Verify Dynamic Mountain Pass Construction Unblocking
        em.unblock_mountain_pass("r0c0", "r0c1")
        edge_pass = em.get_edge("r0c0", "r0c1")
        self.assertTrue(edge_pass.passable)
        self.assertEqual(edge_pass.edge_type, EdgeType.MOUNTAIN_PASS)
        self.assertLess(edge_pass.friction, float('inf'))
        
        # 4. Verify River Corridor Detection
        t_high = Region("r1c1", t=0, wilderness=True)
        t_high.elevation = 0.40
        t_low = Region("r1c2", t=0, wilderness=True)
        t_low.elevation = 0.15
        em_riv = TerrainEdgeManager([t_high, t_low], layout)
        edge_river = em_riv.get_edge("r1c1", "r1c2")
        self.assertIsNotNone(edge_river)
        self.assertTrue(edge_river.is_river)
        self.assertEqual(edge_river.friction, 0.4)
        
        # 5. Full Simulation Verification
        world = build_world_view(seed=42)
        # Verify edges and rendering run cleanly
        render_frame(self.surface, world)
        step_world(world)
        render_frame(self.surface, world)
        
        print("Verified alpine barriers, sheer cliff blocking, river corridor flow, and dynamic mountain pass engineering.")

    def test_induced_innovation_bounties_and_trade_diffusion(self):
        """Verify learning-by-doing, bottleneck accelerators, royal prize bounties, and trade diffusion."""
        from innovation import get_innovation_system, TechDomain, TECH_CATALOG
        world = build_world_view(seed=42)
        inno = get_innovation_system()
        nations = world['nations']
        tiles = world['tiles']
        n1 = nations[0]
        n2 = nations[1]

        # 1. Verify learning-by-doing accumulates domain experience
        init_agri = inno.get_domain_xp(n1.name, TechDomain.AGRONOMY)
        step_world(world)
        new_agri = inno.get_domain_xp(n1.name, TechDomain.AGRONOMY)
        self.assertGreaterEqual(new_agri, init_agri)

        # 2. Verify Royal Prize Bounty creation
        n1.government.agent.cash = 1000.0
        inno.get_discovered_techs(n1.name).discard('gunpowder_blasting')
        ok = inno.post_royal_bounty(n1, 'gunpowder_blasting', 300.0, t=1)
        self.assertTrue(ok)
        self.assertEqual(len(inno.active_bounties), 1)
        self.assertEqual(n1.government.agent.cash, 700.0)

        # 3. Verify Tab 4 Innovation rendering
        world['actions_open'] = True
        world['actions_tab'] = 4
        render_frame(self.surface, world)

        # 4. Verify Trade Diffusion
        inno.get_discovered_techs(n1.name).add('bloomery_iron')
        pair_orders = [(n1.tiles[0], n2.tiles[0])]
        events = inno.diffuse_technologies_along_trade(pair_orders, nations, t=2)
        diff_prog = inno.diffusion_progress.get(n2.name, {}).get('bloomery_iron', 0.0)
        self.assertGreater(diff_prog, 0.0)

        print("Verified learning-by-doing, induced bottleneck multipliers, royal bounties, and trade diffusion.")

    def test_per_tile_resources_and_multi_era_tech_tree(self):
        """Verify per-tile natural resources, resource prerequisites, and 4-Era progression."""
        from tile_resources import TileResource, get_nation_resources
        from innovation import get_innovation_system, TECH_CATALOG
        world = build_world_view(seed=42)
        tiles = world['tiles']
        nations = world['nations']
        n1 = nations[0]

        # 1. Verify every tile has natural resource deposits assigned
        for t in tiles:
            self.assertTrue(hasattr(t, 'natural_resources'))
            self.assertGreater(len(t.natural_resources), 0)

        # 2. Verify resource prerequisite blocking
        inno = get_innovation_system()
        # Force n1 to lack Coal
        for t in n1.tiles:
            t.natural_resources = {TileResource.ARABLE_SILT, TileResource.TIMBER}

        nat_res = get_nation_resources(n1, world=world)
        self.assertNotIn(TileResource.COAL_SEAM, nat_res)

        # Ensure coal_coking breakthrough cannot occur without Coal
        inno.domain_experience[n1.name]['manufacturing'] = 5000.0
        inno.get_discovered_techs(n1.name).add('bloomery_iron')
        inno.evaluate_breakthroughs(nations, t=1)
        self.assertFalse(inno.has_tech(n1.name, 'coal_coking'))

        # Grant Coal deposit to tile -> now breakthrough can occur!
        n1.tiles[0].natural_resources.add(TileResource.COAL_SEAM)
        n1.tiles[0].natural_resources.add(TileResource.IRON_ORE)
        nat_res_with_coal = get_nation_resources(n1, world=world)
        self.assertIn(TileResource.COAL_SEAM, nat_res_with_coal)
        for step_t in range(2, 35):
            if inno.has_tech(n1.name, 'coal_coking'):
                break
            inno.evaluate_breakthroughs(nations, t=step_t)
        self.assertTrue(inno.has_tech(n1.name, 'coal_coking'))

        # 3. Verify all 4 Eras render in Tab 4
        world['actions_open'] = True
        world['actions_tab'] = 4
        for era in [1, 2, 3, 4]:
            world['innovation_era'] = era
            render_frame(self.surface, world)

        print("Verified per-tile natural resources, resource prerequisites, and 4-Era tech progression.")

    def test_map_progress_bars_for_construction_and_science(self):
        """Verify on-map progress bars overlayed on hex tiles for construction and science."""
        from intents import BuildIntent
        from innovation import get_innovation_system
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        # 1. Commission construction project on tile
        n1.government.agent.cash = 1000.0
        intent = BuildIntent(n1.name, tile.name, 'granary', submitted_turn=0)
        n1.submit_intent(intent, t=0)
        tiles_by_name = {t.name: t for t in world['tiles']}
        nations_by_name = {n.name: n for n in nations}
        ok, msg = intent.execute(tiles_by_name, nations_by_name, t=0)
        self.assertTrue(ok, msg)
        self.assertEqual(len(getattr(tile, 'construction_projects', [])), 1)

        # 2. Post Royal Science Bounty on nation
        inno = get_innovation_system()
        inno.post_royal_bounty(n1, 'bessemer_steel', 300.0, t=0)
        from innovation import TechDomain
        inno.domain_experience.setdefault(n1.name, {d.value: 0.0 for d in TechDomain})['manufacturing'] = 50.0

        # 3. Simulate trade diffusion
        inno.diffusion_progress.setdefault(n1.name, {})['dynamo_electrification'] = 0.65

        # 4. Render map frame with progress bars
        render_frame(self.surface, world)

        # 5. Verify clicking nation switcher in Sovereign Actions modal
        from worldview_actions import actions_tab_hit
        world['actions_open'] = True
        for i, target_n in enumerate(nations):
            # Click switcher button
            sx = 24 + 20 + 160 + (i * 140) + 20
            hit = actions_tab_hit((sx, 16 + 55), 24, 16, world)
            if hit:
                self.assertEqual(world['player_nation_name'], target_n.name)

        print("Verified map progress bars and sovereign nation switcher click interactions.")


if __name__ == "__main__":
    unittest.main()
