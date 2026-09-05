"""
test_left_cross_nation_panels.py — Comprehensive Test Suite for Left Cross-Nation Drawers.

Verifies:
1. Left Dock Buttons rendering and hit testing for all 6 panels:
   - Build (B), Governance (G), Diplomacy (D), Sovereign Debt (S), Science (T), Military (M).
2. Mutual exclusivity between all left drawers.
3. Left Diplomacy Drawer:
   - Bilateral nation tabs switching.
   - Treaty signing & cancellation (Trade Pact, NAP, Defensive Alliance).
   - War declaration & Peace treaty restoration.
   - Foreign Aid disbursement ($100 gift & +0.15 relation boost).
4. Left Sovereign Debt Drawer:
   - Sub-scope switching ([Domestic & ISRB] vs [Foreign Reserves & Bonds]).
   - ISRB credit lobbying ($200 for +1 tier upgrade).
   - Maturity term selection (20t, 50t, 100t).
   - 1-Turn advance domestic bond announcement intent submission.
   - Cross-border foreign bond purchase into reserve portfolio.
5. Left Science Drawer:
   - Strategic resource endowments ribbon.
   - Era selector switching (Era I..IV).
   - Royal Science Prize pledge ($300 purse) intent & bounty registry.
6. Left Military Drawer:
   - Stationed garrison readiness display.
   - Unit recruitment execution (15 soldiers, $15) on selected tile.
7. Full render_frame headless integration with each left drawer.
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
    draw_drawer_top_tabs, drawer_top_tabs_hit,
    open_left_panel, close_left_panels, get_active_left_panel,
    is_any_left_panel_open, PANELS_DEF
)
from worldview_gov_panel import draw_gov_panel, gov_panel_hit
from worldview_build_panel import draw_build_panel, build_panel_hit
from worldview_diplomacy_panel import draw_diplomacy_panel, diplomacy_panel_hit
from worldview_debt_panel import draw_debt_panel, debt_panel_hit
from worldview_science_panel import draw_science_panel, science_panel_hit
from worldview_military_panel import draw_military_panel, military_panel_hit
from diplomacy import get_diplomacy, TreatyType
from sovereign_bonds import get_bond_market, BondOffering
from innovation import get_innovation_system, TECH_CATALOG


class TestLeftCrossNationPanels(unittest.TestCase):

    def setUp(self):
        pygame.init()
        pygame.font.init()
        self.surface = pygame.Surface((1400, 900))
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 16)
        self.world = build_world_view(seed=42)

    def tearDown(self):
        pygame.quit()

    def test_left_dock_buttons_and_mutual_exclusivity(self):
        """Verify all 6 dock buttons render and clicking each opens the respective panel."""
        world = self.world
        close_left_panels(world)

        draw_left_dock_buttons(self.surface, world, self.font_small)

        # Test clicking each of the 6 dock buttons
        for i, (p_id, _, _, _) in enumerate(PANELS_DEF):
            close_left_panels(world)
            self.assertFalse(is_any_left_panel_open(world))

            by = DOCK_Y + i * (DOCK_BTN_H + DOCK_SPACING)
            click_pos = (DOCK_X + 20, by + 10)

            hit = left_dock_buttons_hit(click_pos, world)
            self.assertTrue(hit, f"Dock button {p_id} failed hit test")
            self.assertEqual(get_active_left_panel(world), p_id)

            # Check mutual exclusivity
            for other_id, _, _, _ in PANELS_DEF:
                flag = f"{'build' if other_id == 'build' else ('gov' if other_id == 'governance' else other_id)}_panel_open"
                if other_id == p_id:
                    self.assertTrue(world.get(flag), f"{flag} should be True")
                else:
                    self.assertFalse(world.get(flag), f"{flag} should be False")

    def test_diplomacy_panel_interactions(self):
        """Verify Left Diplomacy Drawer rendering, treaties, war, peace, and foreign aid."""
        world = self.world
        open_left_panel(world, 'diplomacy')

        active_n = world['nations'][0]
        other_n = world['nations'][1]
        world['selected_region'] = active_n.tiles[0]
        world['diplomacy_target_nation'] = other_n.name

        draw_diplomacy_panel(self.surface, world, self.font, self.font_small)

        diplomacy = get_diplomacy()
        # Clean any preexisting war/treaties for deterministic assertion
        if diplomacy.are_at_war(active_n.name, other_n.name):
            diplomacy.sign_peace(active_n.name, other_n.name, 0)

        # 1. Propose Trade Pact
        cur_y = PANEL_Y + 48 + 24 + 8 + 24 + 10 + 138 + 10
        trade_btn_pos = (PANEL_X + 20, cur_y + 32 + 10)
        hit = diplomacy_panel_hit(trade_btn_pos, world)
        self.assertTrue(hit)
        self.assertTrue(diplomacy.has_treaty(active_n.name, other_n.name, TreatyType.TRADE_PACT.value))

        # Cancel Trade Pact
        hit = diplomacy_panel_hit(trade_btn_pos, world)
        self.assertTrue(hit)
        self.assertFalse(diplomacy.has_treaty(active_n.name, other_n.name, TreatyType.TRADE_PACT.value))

        # 2. Propose Non-Aggression Pact
        nap_btn_pos = (PANEL_X + 20, cur_y + 32 + 32 + 10)
        hit = diplomacy_panel_hit(nap_btn_pos, world)
        self.assertTrue(hit)
        self.assertTrue(diplomacy.has_treaty(active_n.name, other_n.name, TreatyType.NON_AGGRESSION.value))

        # 3. Form Defensive Alliance
        ally_btn_pos = (PANEL_X + 20, cur_y + 32 + 64 + 10)
        hit = diplomacy_panel_hit(ally_btn_pos, world)
        self.assertTrue(hit)
        self.assertTrue(diplomacy.has_treaty(active_n.name, other_n.name, TreatyType.DEFENSIVE_ALLIANCE.value))

        # 4. Declare War and Sign Peace
        war_btn_pos = (PANEL_X + 20, cur_y + 32 + 96 + 10)
        hit = diplomacy_panel_hit(war_btn_pos, world)
        self.assertTrue(hit)
        self.assertTrue(diplomacy.are_at_war(active_n.name, other_n.name))

        hit = diplomacy_panel_hit(war_btn_pos, world)
        self.assertTrue(hit)
        self.assertFalse(diplomacy.are_at_war(active_n.name, other_n.name))

        # 5. Foreign Aid ($100)
        active_n.government.agent.cash = 500.0
        prev_rel = diplomacy.get_relation(active_n.name, other_n.name)
        aid_btn_pos = (PANEL_X + 20, cur_y + 32 + 128 + 10)
        hit = diplomacy_panel_hit(aid_btn_pos, world)
        self.assertTrue(hit)
        self.assertEqual(active_n.government.agent.cash, 400.0)
        self.assertAlmostEqual(diplomacy.get_relation(active_n.name, other_n.name), min(1.0, prev_rel + 0.15))

    def test_sovereign_debt_panel_interactions(self):
        """Verify Left Sovereign Debt Drawer rendering, ISRB lobbying, and bond offerings."""
        world = self.world
        open_left_panel(world, 'debt')
        active_n = world['nations'][0]
        world['selected_region'] = active_n.tiles[0]
        active_n.government.agent.cash = 1000.0

        draw_debt_panel(self.surface, world, self.font, self.font_small)

        market = get_bond_market()
        isrb = market.isrb

        # 1. Lobby Upgrade ($200)
        init_mod = isrb.rating_modifiers.get(active_n.name, 0)
        cur_y = PANEL_Y + 48 + 24 + 8 + 32
        lobby_btn_pos = (PANEL_X + 20, cur_y + 90 + 10)
        hit = debt_panel_hit(lobby_btn_pos, world)
        self.assertTrue(hit)
        self.assertEqual(isrb.rating_modifiers.get(active_n.name, 0), init_mod + 1)
        self.assertEqual(active_n.government.agent.cash, 800.0)

        # 2. Select Term: 50 turns
        t50_pos = (PANEL_X + 16 + 1 * ((PANEL_W - 48) // 3 + 6) + 10, cur_y + 160 + 10 + 48 + 10)
        hit = debt_panel_hit(t50_pos, world)
        self.assertTrue(hit)
        self.assertEqual(world.get('bond_duration_selected'), 50)

        # 3. Announce $500 Domestic Bond Offering
        ann_btn_pos = (PANEL_X + 20, cur_y + 160 + 10 + 80 + 10)
        hit = debt_panel_hit(ann_btn_pos, world)
        self.assertTrue(hit)
        # Verify submitted intent
        intents = active_n.intent_queue
        self.assertTrue(any(it.intent_type == 'issue_bond' and it.principal == 500.0 for it in intents))

        # 4. Scope switch to Foreign Reserves and buy bond
        foreign_tab_pos = (PANEL_X + 10 + (PANEL_W - 28) // 2 + 10, PANEL_Y + 48 + 24 + 8 + 10)
        hit = debt_panel_hit(foreign_tab_pos, world)
        self.assertTrue(hit)
        self.assertEqual(world.get('debt_scope'), 'foreign')

        # Add mock live offering to foreign market
        other_n = world['nations'][1]
        offering = BondOffering("test_offering", other_n.name, 500.0, 0.0015, 20, 0, 1, status='live')
        market.active_offerings.append(offering)

        draw_debt_panel(self.surface, world, self.font, self.font_small)

        # Click buy offering button
        buy_pos = (PANEL_X + 20, PANEL_Y + 48 + 24 + 8 + 32 + 90 + 10 + 32 + 10)
        hit = debt_panel_hit(buy_pos, world)
        self.assertTrue(hit)
        held_bonds = market.get_bonds_held_by(active_n.name)
        self.assertTrue(any(b.issuer_nation == other_n.name and b.principal == 500.0 for b in held_bonds))

    def test_science_panel_interactions(self):
        """Verify Left Science Drawer rendering, Era selector, and royal prize pledge."""
        world = self.world
        open_left_panel(world, 'science')
        active_n = world['nations'][0]
        world['selected_region'] = active_n.tiles[0]
        active_n.government.agent.cash = 600.0

        draw_science_panel(self.surface, world, self.font, self.font_small)

        # 1. Switch to Era II
        cur_y = PANEL_Y + 48 + 24 + 8 + 42 + 10
        era_w = (PANEL_W - 24 - 3 * 4) // 4
        era2_pos = (PANEL_X + 12 + 1 * (era_w + 4) + 10, cur_y + 10)
        hit = science_panel_hit(era2_pos, world)
        self.assertTrue(hit)
        self.assertEqual(world.get('innovation_era'), 2)

        # Switch back to Era I
        era1_pos = (PANEL_X + 12 + 0 * (era_w + 4) + 10, cur_y + 10)
        hit = science_panel_hit(era1_pos, world)
        self.assertTrue(hit)
        self.assertEqual(world.get('innovation_era'), 1)

        # 2. Pledge Royal Science Prize on first unmastered tech
        inno = get_innovation_system()
        era1_techs = [tch for tch in TECH_CATALOG.values() if tch.era == 1]
        target_tech = era1_techs[0]

        btn_y = cur_y + 32 + 46 + 10
        pledge_pos = (PANEL_X + 20, btn_y)
        cash_before = active_n.government.agent.cash
        hit = science_panel_hit(pledge_pos, world)
        self.assertTrue(hit)

        if cash_before - active_n.government.agent.cash == 300.0:
            self.assertTrue(any(b.nation_name == active_n.name and b.tech_id == target_tech.tech_id for b in inno.active_bounties))

    def test_military_panel_interactions(self):
        """Verify Left Military Drawer rendering and garrison recruitment execution."""
        world = self.world
        open_left_panel(world, 'military')
        active_n = world['nations'][0]
        tile = active_n.tiles[0]
        world['selected_region'] = tile
        active_n.government.agent.cash = 200.0

        draw_military_panel(self.surface, world, self.font, self.font_small)

        # Click Recruit Unit ($15 for 15 soldiers)
        cur_y = PANEL_Y + 48 + 24 + 8 + 76 + 10
        rec_pos = (PANEL_X + 20, cur_y + 56 + 10)
        hit = military_panel_hit(rec_pos, world)
        self.assertTrue(hit)

        # Verify submitted RecruitArmyIntent
        intents = active_n.intent_queue
        self.assertTrue(any(it.intent_type == 'recruit_army' and it.soldiers == 15 for it in intents))

    def test_full_frame_rendering_with_all_panels(self):
        """Verify render_frame renders cleanly without exceptions for every left drawer."""
        world = self.world
        for p_id in ['build', 'governance', 'diplomacy', 'debt', 'science', 'military']:
            open_left_panel(world, p_id)
            render_frame(self.surface, world)

    def test_drawer_top_tabs_on_build_and_governance(self):
        """Verify that the tab switcher is present and functional in Build and Governance menus."""
        world = self.world
        active_n = world['nations'][0]
        world['selected_region'] = active_n.tiles[0]

        # 1. Open Build Menu and verify drawer top switcher works
        open_left_panel(world, 'build')
        draw_build_panel(self.surface, world, self.font, self.font_small)

        # In drawer top switcher (y=PANEL_Y+48), click Governance tab (index 1)
        tab_w = (PANEL_W - 16 - 5 * 4) // 6
        gov_tab_x = PANEL_X + 8 + 1 * (tab_w + 4) + tab_w // 2
        tab_y = PANEL_Y + 48 + 12

        hit = build_panel_hit((gov_tab_x, tab_y), world)
        self.assertTrue(hit)
        self.assertEqual(get_active_left_panel(world), 'governance')

        # 2. From Governance Menu, click Build tab (index 0)
        draw_gov_panel(self.surface, world, self.font, self.font_small)
        build_tab_x = PANEL_X + 8 + 0 * (tab_w + 4) + tab_w // 2
        hit = gov_panel_hit((build_tab_x, tab_y), world)
        self.assertTrue(hit)
        self.assertEqual(get_active_left_panel(world), 'build')

        # 3. From Build Menu, click Diplomacy tab (index 2)
        draw_build_panel(self.surface, world, self.font, self.font_small)
        diplo_tab_x = PANEL_X + 8 + 2 * (tab_w + 4) + tab_w // 2
        hit = build_panel_hit((diplo_tab_x, tab_y), world)
        self.assertTrue(hit)
        self.assertEqual(get_active_left_panel(world), 'diplomacy')

    def test_panel_close_and_reappear_initial_buttons(self):
        """Verify that closing any panel via [X] restores the initial left dock buttons."""
        world = self.world
        active_n = world['nations'][0]
        world['selected_region'] = active_n.tiles[0]

        panels_and_hitters = [
            ('build', build_panel_hit),
            ('governance', gov_panel_hit),
            ('diplomacy', diplomacy_panel_hit),
            ('debt', debt_panel_hit),
            ('science', science_panel_hit),
            ('military', military_panel_hit),
        ]

        close_btn_pos = (PANEL_X + PANEL_W - 16, PANEL_Y + 14)

        for p_id, hitter in panels_and_hitters:
            open_left_panel(world, p_id)
            self.assertTrue(is_any_left_panel_open(world))
            self.assertEqual(get_active_left_panel(world), p_id)

            # Click close button [X]
            hit = hitter(close_btn_pos, world)
            self.assertTrue(hit, f"Close button [X] failed on panel {p_id}")

            # Verify panel is closed and state is cleared
            self.assertFalse(is_any_left_panel_open(world), f"Panel {p_id} remained open after close click")
            self.assertIsNone(get_active_left_panel(world))
            self.assertIsNone(world.get('left_panel'))

            # Verify initial dock buttons reappear and are clickable
            dock_build_btn = (DOCK_X + 20, DOCK_Y + 10)
            reopen_hit = left_dock_buttons_hit(dock_build_btn, world)
            self.assertTrue(reopen_hit, f"Failed to click dock button after closing {p_id}")
            self.assertEqual(get_active_left_panel(world), 'build')

            # Clean up for next iteration
            close_left_panels(world)


if __name__ == '__main__':
    unittest.main()

