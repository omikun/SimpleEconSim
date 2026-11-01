"""Policy costs, authority and normal campaign controls for the active slice."""

from copy import deepcopy
import unittest

import pygame

from governing_actions import project_actions, execute
from ui_targets import clear_targets
from tests.test_governing_collectives import governing_fixture
from client.desktop.panels.governing_campaign_ui import draw_panel, handle_action


class GoverningCampaignTests(unittest.TestCase):
    def test_real_due_payment_clears_inline_warning_so_later_campaign_phases_can_run(self):
        from client.desktop.engine import build_world_view, step_world
        from world_config import get_map_topology, set_map_topology
        previous = get_map_topology()
        self.addCleanup(set_map_topology, previous)
        set_map_topology('voronoi')
        world = build_world_view(scenario_id='egypt_1877', governing_network_mode='governing',
                                 trace_enabled=False)
        self.assertTrue(execute(world, 'release_maize')[0])
        for _ in range(5):
            step_world(world)
        self.assertEqual(world['scenario_warning_modal']['kind'], 'debt_due')
        self.assertTrue(execute(world, 'pay_remittance')[0])
        self.assertNotEqual((world.get('scenario_warning_modal') or {}).get('kind'), 'debt_due')
        self.assertNotEqual(world['scenario_state']['payment_status'], 'unpaid')

    def test_urgent_notice_is_visible_modal_and_its_real_response_prevents_click_through(self):
        from client.desktop.app import is_any_modal_open
        from client.desktop.panels.governing_campaign_ui import draw_warning
        from client.desktop.panels.scenario_ui import guided_ui_hit
        pygame.font.init()
        world = governing_fixture()
        world['scenario_warning_modal'] = {'kind': 'risk', 'message': 'A real crisis requires a response.'}
        before = deepcopy(world['scenario_state'])
        self.assertTrue(is_any_modal_open(world))
        clear_targets(world)
        draw_warning(pygame.Surface((1400, 900)), world)
        self.assertTrue(guided_ui_hit((1, 1), world))
        self.assertIsNotNone(world['scenario_warning_modal'])
        target = next(t for t in world['_ui_targets'] if t.action == ('scenario_warning', 'review_risk'))
        self.assertTrue(guided_ui_hit(target.rect.center, world))
        self.assertIsNone(world['scenario_warning_modal'])
        self.assertFalse(is_any_modal_open(world))
        self.assertEqual(before, world['scenario_state'])

    def test_main_controls_show_real_routes_and_only_the_target_district(self):
        pygame.font.init()
        world = governing_fixture()
        world['tiles'][1].agents[-1].is_lord = True
        world['scenario_state']["ending"] = None
        # The full two-demand/debt layout must fit the normal 900px view.
        world['scenario_state']['political_economy']['arrears'][100] = {'balance': 9.}
        from governing_network import advance, prepare_turn
        prepare_turn(world, 2)
        world['turn'] = 2
        advance(world)
        world['scenario_state']['payment_window_turn'] = 2
        surface = pygame.Surface((1400, 900))
        clear_targets(world)
        draw_panel(surface, world, lambda n: pygame.font.Font(None, n),
                   x=1060, y=66, width=330, height=788)
        targets = world['_ui_targets']
        actions = [t.action[1] for t in targets if isinstance(t.action, tuple)]
        for action in ('buy_private_grain', 'requisition_private_grain', 'open_private_grain_market',
                       'district_bargain_workers', 'district_arrears_relief', 'pay_remittance'):
            self.assertIn(action, actions)
        self.assertTrue(all(t.rect.bottom < 806 for t in targets))
        self.assertTrue(handle_action(world, 'governing_all_policies'))
        self.assertTrue(world['_ui_governing_all_policies'])
        self.assertTrue(handle_action(world, 'governing_back'))
        self.assertFalse(world['_ui_governing_all_policies'])

    def test_opening_purchase_quote_matches_actual_transfers_and_decision_limit(self):
        from client.desktop.engine import build_world_view
        from goods import Goods
        from world_config import get_map_topology, set_map_topology
        previous = get_map_topology()
        self.addCleanup(set_map_topology, previous)
        set_map_topology('voronoi')
        world = build_world_view(scenario_id='egypt_1877', governing_network_mode='governing')
        egypt = next(n for n in world['nations'] if n.name == 'Egypt')
        before = deepcopy(world['scenario_state'])
        people_cash = sum(p.cash for tile in world['tiles'] for p in tile.agents)
        inventories = sum(p.inv_get(Goods.food, 0) for tile in world['tiles'] for p in tile.agents)
        treasury, public = egypt.government.agent.cash, egypt.government.food_inventory
        quote = project_actions(world)['purchase_quote']
        self.assertEqual(before, world['scenario_state'])
        self.assertFalse(execute(world, 'district_bargain_workers', 'foreign-district')[0])
        self.assertTrue(execute(world, 'buy_private_grain')[0])
        self.assertAlmostEqual(treasury - egypt.government.agent.cash, quote['treasury_cost'])
        self.assertEqual(egypt.government.food_inventory - public, quote['units'])
        self.assertAlmostEqual(sum(p.cash for tile in world['tiles'] for p in tile.agents) - people_cash,
                               quote['treasury_cost'])
        self.assertEqual(inventories - sum(p.inv_get(Goods.food, 0) for tile in world['tiles'] for p in tile.agents),
                         quote['units'])
        self.assertFalse(execute(world, 'requisition_private_grain')[0])
        self.assertTrue(all(not a['enabled'] for a in project_actions(world)['food']))


if __name__ == '__main__':
    unittest.main()
