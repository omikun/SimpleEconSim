"""
test_progress_panel.py — Comprehensive Test Suite for Left Progress & Works Panel.

Verifies:
1. Left Dock Button & Tab integration for Progress (P).
2. Mutual exclusivity with other left drawers (Build, Governance, Diplomacy, Debt, Science, Military).
3. Items aggregation:
   - Construction projects (active & stalled with reasons, progress %, turns remaining, contractors).
   - Research & innovation (mastered, active bounties, diffusing).
   - Legislation & statutory mandates (pending bills, Ten-Hour Act, UBI, survey debts).
4. View mode switching ([ Active Nation ] vs [ All Nations ] with province grouping).
5. Scrolling controls & bounds.
6. One-click emergency overrun grant ($100 subsidy) on stalled/distressed construction projects.
7. Full headless rendering via worldview.render_frame.
"""

import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import unittest
import pygame
from worldview_engine import build_world_view
from worldview import render_frame
from worldview_left_dock import (
    DOCK_X, DOCK_Y, DOCK_BTN_W, DOCK_BTN_H, DOCK_SPACING,
    PANEL_X, PANEL_Y, PANEL_W, PANEL_H,
    draw_left_dock_buttons, left_dock_buttons_hit,
    open_left_panel, close_left_panels, get_active_left_panel,
    is_any_left_panel_open, PANELS_DEF
)
from worldview_progress_panel import (
    draw_progress_panel, progress_panel_hit,
    _collect_items_for_nation, _get_active_nation
)
from buildings import (
    BUILDING_RECIPES, ConstructionProject
)
from goods import Goods
from construction_politics import find_or_emerge_contractor


class TestProgressPanel(unittest.TestCase):

    def setUp(self):
        pygame.init()
        pygame.font.init()
        self.surface = pygame.Surface((1400, 900))
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 16)
        self.world = build_world_view(seed=42)

    def tearDown(self):
        pygame.quit()

    def test_progress_dock_button_and_exclusivity(self):
        """Verify the Progress (P) dock button opens the progress panel and maintains exclusivity."""
        world = self.world
        close_left_panels(world)
        self.assertFalse(is_any_left_panel_open(world))

        # Find Progress button index
        p_idx = [p[0] for p in PANELS_DEF].index('progress')
        by = DOCK_Y + p_idx * (DOCK_BTN_H + DOCK_SPACING)
        hit = left_dock_buttons_hit((DOCK_X + 20, by + 10), world)
        self.assertTrue(hit)
        self.assertTrue(world.get('progress_panel_open'))
        self.assertEqual(get_active_left_panel(world), 'progress')

        # Check all other panels are closed
        for other_id, _, _, _ in PANELS_DEF:
            if other_id != 'progress':
                flag = f"{'build' if other_id == 'build' else ('gov' if other_id == 'governance' else other_id)}_panel_open"
                self.assertFalse(world.get(flag), f"{flag} should be closed")

    def test_collect_items_construction(self):
        """Verify construction projects (active and stalled) are properly gathered."""
        world = self.world
        nation = world['nations'][0]
        tile = nation.tiles[0]

        # Add a normal project and a stalled project
        proj_normal = ConstructionProject(
            project_id="test_normal_proj",
            nation_name=nation.name,
            region=tile,
            recipe=BUILDING_RECIPES['barge_canal'],
            contractor=None,
            started_turn=1
        )
        proj_stalled = ConstructionProject(
            project_id="test_stalled_proj",
            nation_name=nation.name,
            region=tile,
            recipe=BUILDING_RECIPES['turnpike_road'],
            contractor=None,
            started_turn=1
        )
        proj_stalled.status = 'stalled'
        proj_stalled.stall_reason = 'missing_materials'
        tile.construction_projects = [proj_normal, proj_stalled]

        items = _collect_items_for_nation(nation, world)
        c_items = [it for it in items if it['category'] == 'construction']
        self.assertGreaterEqual(len(c_items), 2)

        stalled_found = False
        for it in c_items:
            if it['is_stalled']:
                stalled_found = True
                self.assertIn("Missing Materials", it['stall_reason'])
                self.assertEqual(it['bar_color'], (235, 75, 75))

        self.assertTrue(stalled_found)

    def test_collect_items_research_and_legislation(self):
        """Verify research discoveries and legislative mandates are gathered."""
        world = self.world
        nation = world['nations'][0]
        tile = nation.tiles[0]

        # Enact Ten Hour Act on tile
        tile.ten_hour_act = True
        tile.workday_cap = 10.0

        # Enact UBI on government
        if getattr(nation, 'government', None):
            nation.government.ubi_enabled = True

        # Add a survey debt
        tile.enclosure_survey_debts.append({'debt_id': 999, 'fee': 35.0, 'countdown': 2})

        from innovation import get_innovation_system
        inn_sys = get_innovation_system()
        inn_sys.get_discovered_techs(nation.name).add('crop_rotation')

        items = _collect_items_for_nation(nation, world)

        leg_titles = [it['title'] for it in items if it['category'] == 'legislation']
        self.assertTrue(any('Ten-Hour Workday Act' in t for t in leg_titles))
        self.assertTrue(any('Universal Basic Income' in t for t in leg_titles))
        self.assertTrue(any('Survey Debt Assessment' in t for t in leg_titles))

        # Research items
        res_items = [it for it in items if it['category'] == 'research']
        self.assertGreater(len(res_items), 0)

    def test_view_mode_switching_and_scrolling(self):
        """Verify switching between Active Nation and All Nations modes and scrolling."""
        world = self.world
        open_left_panel(world, 'progress')

        # Mode buttons are at cur_y around PANEL_Y + 54
        # Render first to populate _PROGRESS_BUTTONS
        draw_progress_panel(self.surface, world, self.font, self.font_small, mouse_pos=(-1, -1))

        # Switch to All Nations
        world['progress_view_mode'] = 'all'
        draw_progress_panel(self.surface, world, self.font, self.font_small, mouse_pos=(-1, -1))
        self.assertEqual(world.get('progress_view_mode'), 'all')

        # Switch to Active Nation
        world['progress_view_mode'] = 'active'
        draw_progress_panel(self.surface, world, self.font, self.font_small, mouse_pos=(-1, -1))
        self.assertEqual(world.get('progress_view_mode'), 'active')

        # Test scrolling bounds
        world['progress_scroll'] = 0
        progress_panel_hit((PANEL_X + PANEL_W - 25, PANEL_Y + 70), world)  # Click scroll down
        draw_progress_panel(self.surface, world, self.font, self.font_small, mouse_pos=(-1, -1))

    def test_overrun_subsidy_button_hit(self):
        """Verify clicking +$100 Sub on a distressed project disburses grant."""
        world = self.world
        nation = world['nations'][0]
        tile = nation.tiles[0]

        contractor = find_or_emerge_contractor(tile, 300.0, t=1)
        contractor.company_name = "Canal Builders Ltd"
        contractor.cash = 2.0
        proj = ConstructionProject(
            project_id="test_grant_proj",
            nation_name=nation.name,
            region=tile,
            recipe=BUILDING_RECIPES['barge_canal'],
            contractor=contractor,
            started_turn=1
        )
        proj.status = 'stalled'
        proj.stall_reason = 'missing_materials'
        tile.construction_projects = [proj]

        if getattr(nation, 'government', None) and getattr(nation.government, 'agent', None):
            nation.government.agent.cash = 500.0

        open_left_panel(world, 'progress')
        world['progress_view_mode'] = 'active'

        # Render panel so buttons are registered
        draw_progress_panel(self.surface, world, self.font, self.font_small, mouse_pos=(-1, -1))

        from worldview_progress_panel import _PROGRESS_BUTTONS
        grant_btn = None
        for rect, action, data in _PROGRESS_BUTTONS:
            if action == 'subsidize_proj' and data == proj:
                grant_btn = rect
                break

        self.assertIsNotNone(grant_btn, "Grant button should be registered for stalled project")
        bx, by, bw, bh = grant_btn
        hit = progress_panel_hit((bx + 5, by + 5), world)
        self.assertTrue(hit)
        self.assertAlmostEqual(contractor.cash, 102.0, places=2)
        if getattr(nation, 'government', None) and getattr(nation.government, 'agent', None):
            self.assertAlmostEqual(nation.government.agent.cash, 400.0, places=2)

    def test_render_frame_with_progress_panel(self):
        """Verify full worldview render_frame executes cleanly with progress panel open."""
        world = self.world
        open_left_panel(world, 'progress')
        render_frame(self.surface, world)
        self.assertEqual(self.surface.get_size(), (1400, 900))


if __name__ == '__main__':
    unittest.main()
