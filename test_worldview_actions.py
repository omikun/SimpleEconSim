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


if __name__ == "__main__":
    unittest.main()
