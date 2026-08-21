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

        # Switch to Beta
        world['player_nation_name'] = 'Beta'
        render_frame(self.surface, world)

        # Top bar action hits
        self.assertEqual(top_bar_action_hit((DIPLOMACY_BTN[0] + 5, DIPLOMACY_BTN[1] + 5)), 'diplomacy')
        self.assertEqual(top_bar_action_hit((MILITARY_BTN[0] + 5, MILITARY_BTN[1] + 5)), 'military')

        # Test recruiting from military tab
        world['actions_tab'] = 2
        beta_nation = next(n for n in world['nations'] if n.name == 'Beta')
        world['selected_region'] = beta_nation.tiles[0]
        
        # Click recruit button: (box_x + 280, recruit_bar_y + 12) = (304, 184)
        hit = actions_tab_hit((320, 188), 24, 16, world)
        self.assertTrue(hit, "Military recruitment click should register and submit intent.")
        self.assertEqual(len(beta_nation.intents), 1, "Beta should have 1 submitted RecruitArmyIntent.")

    def test_diplomacy_instant_clicks_and_war(self):
        """Verify instant out-of-turn execution for diplomacy buttons: trade, alliance, war, peace."""
        from worldview_actions import actions_tab_hit
        from diplomacy import get_diplomacy
        world = self.world
        world['actions_open'] = True
        world['actions_tab'] = 1
        world['player_nation_name'] = 'Alpha'
        diplomacy = get_diplomacy()

        # Target button for Beta:
        # box_x = 24, box_w = 1400 - 48 = 1352, card_w = 1312
        # bx = 24 + 1312 - 530 = 806
        # by = 16 + 128 + 36 + 36 = 216
        
        # 1. Propose Trade Pact (bx = 806, by = 216)
        hit = actions_tab_hit((820, 220), 24, 16, world)
        self.assertTrue(hit, "Trade pact click should register.")
        self.assertIsNotNone(world.get('action_feedback'))
        print(f"Trade click feedback: {world.get('action_feedback')}")

        # 2. Declare War (bx + 390 = 1196, by = 216)
        hit = actions_tab_hit((1210, 220), 24, 16, world)
        self.assertTrue(hit, "Declare war click should register.")
        self.assertTrue(diplomacy.are_at_war('Alpha', 'Beta'), "Alpha and Beta should now be at war.")
        self.assertIsNotNone(world.get('action_feedback'))
        print(f"War declaration feedback: {world.get('action_feedback')}")

        # 3. Sign Peace (bx + 390 = 1196, by = 216)
        hit = actions_tab_hit((1210, 220), 24, 16, world)
        self.assertTrue(hit, "Sign peace click should register.")
        self.assertFalse(diplomacy.are_at_war('Alpha', 'Beta'), "Alpha and Beta should no longer be at war.")
        print(f"Peace signing feedback: {world.get('action_feedback')}")

    def test_recruit_before_first_turn_and_step(self):
        """User bug regression: recruit unit before first turn and step world across turns."""
        from worldview_engine import step_world
        world = self.world
        beta_nation = next(n for n in world['nations'] if n.name == 'Beta')
        world['player_nation_name'] = 'Beta'
        world['selected_region'] = beta_nation.tiles[0]

        # Submit recruitment intent before first turn
        world['actions_open'] = True
        world['actions_tab'] = 2
        actions_tab_hit((320, 188), 24, 16, world)
        self.assertGreater(len(beta_nation.intents), 0)

        # Step the world across 5 turns without crashing
        for _ in range(5):
            step_world(world)

        self.assertGreater(world['turn'], 1)
        self.assertGreater(len(beta_nation.military_units), 0, "Beta should have active recruited military units.")
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

        for tile in tiles:
            if getattr(tile, 'is_ocean', False) or getattr(tile, 'elevation', 0.0) < 0.0:
                self.assertEqual(len(tile.agents), 0, f"Ocean tile {tile.name} should have 0 agents, found {len(tile.agents)}")
                self.assertIsNone(getattr(tile, 'owner_nation', None), f"Ocean tile {tile.name} should never be claimed")

        print("Verified 100% single continuous landmass connectivity and complete ocean isolation.")


if __name__ == "__main__":
    unittest.main()
