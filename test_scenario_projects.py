"""Funded project lifecycle, conserved wages, and map-state checks."""

import unittest

import pygame

from scenario_projects import (advance, cancel_project, damage_project,
                               draw_map_overlay, effectiveness, get_project,
                               repair_project, start_project)
from worldview_engine import build_world_view


class StrategicProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def setUp(self):
        self.world = build_world_view(scenario_id='egypt_1877')
        self.egypt = next(nation for nation in self.world['nations'] if nation.name == 'Egypt')

    def _egypt_cash(self):
        return (float(self.egypt.government.agent.cash)
                + sum(float(agent.cash) for tile in self.egypt.tiles for agent in tile.agents))

    def test_local_wages_progress_upkeep_damage_and_repair(self):
        before = self._egypt_cash()
        ok, _ = start_project(self.world, 'nile_repair', 'Nile Delta')
        self.assertTrue(ok)
        self.assertAlmostEqual(self._egypt_cash(), before, places=4)
        project = get_project(self.world, 'nile_repair', 'Nile Delta')
        self.assertEqual(project['progress'], 0)
        self.assertEqual(len(project['worker_ids']), 3)
        self.assertFalse(start_project(self.world, 'nile_repair', 'Nile Delta')[0])
        for turn in (2, 3):
            self.world['turn'] = turn
            advance(self.world)
        self.assertEqual(project['status'], 'operating')
        self.assertGreater(effectiveness(self.world, 'nile_repair', 'Nile Delta'), 0)
        self.assertAlmostEqual(self._egypt_cash(), before, places=4)
        self.assertEqual(project['progress'], 2)
        advance(self.world)
        self.assertEqual(project['progress'], 2)
        self.assertTrue(damage_project(self.world, 'nile_repair', 'Nile Delta', .7))
        self.assertEqual(effectiveness(self.world, 'nile_repair', 'Nile Delta'), 0)
        self.assertTrue(repair_project(self.world, 'nile_repair', 'Nile Delta')[0])
        self.world['turn'] = 4
        advance(self.world)
        self.assertEqual(project['status'], 'operating')
        self.assertAlmostEqual(self._egypt_cash(), before, places=4)
        self.assertTrue(cancel_project(self.world, 'nile_repair', 'Nile Delta')[0])
        self.assertEqual(effectiveness(self.world, 'nile_repair', 'Nile Delta'), 0)

    def test_occupation_stops_work_and_overlay_supports_both_modes(self):
        ok, _ = start_project(self.world, 'revenue_office', 'Alexandria')
        self.assertTrue(ok)
        project = get_project(self.world, 'revenue_office', 'Alexandria')
        self.world['scenario_state']['campaign']['territorial_control']['Alexandria'] = 'Britain'
        self.world['turn'] = 2
        advance(self.world)
        self.assertEqual(project['status'], 'occupied')
        self.assertEqual(project['progress'], 0)
        surface = pygame.Surface((1400, 900))
        for mode in ('guided', 'advanced'):
            self.world['ui_mode'] = mode
            draw_map_overlay(surface, self.world)
        self.world['scenario_state']['campaign']['territorial_control'].clear()
        self.world['turn'] = 3
        advance(self.world)
        self.assertEqual(project['progress'], 1)


if __name__ == '__main__':
    unittest.main()
