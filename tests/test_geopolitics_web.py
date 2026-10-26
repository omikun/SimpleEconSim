"""Unit tests for Voronoi Geopolitics Renderer & Mapgen2 Explorer Web Integration."""
import os
import unittest
import pygame

from polygon_map import PolygonMapGenerator
import mapgen_web
from render_voronoi_geopolitics import render_voronoi_geopolitics


class TestGeopoliticsWebIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = 42
        cls.gen = mapgen_web.get_cached_graph(
            seed=cls.seed,
            shape="island",
            points=1500,
            rivers=20,
            sharpness=0.8,
        )

    def test_cached_geopolitics_build(self):
        tiles, nations = mapgen_web.get_cached_geopolitics(
            self.gen,
            self.seed,
            num_nations=4,
            nation_seed=777,
        )
        self.assertGreater(len(tiles), 500)
        self.assertEqual(len(nations), 4)

        # Ensure nations have valid sovereign capitals and names
        for n in nations:
            self.assertIsNotNone(n.capital)
            self.assertIsNotNone(n.name)
            self.assertTrue(hasattr(n, "provinces"))

    def test_geopolitics_renderer_all_layers(self):
        tiles, nations = mapgen_web.get_cached_geopolitics(
            self.gen,
            self.seed,
            num_nations=3,
            nation_seed=123,
        )
        layers = ["overview", "nations", "provinces", "trade", "resources", "tenure", "strikes"]
        for layer in layers:
            surf = render_voronoi_geopolitics(
                gen=self.gen,
                tiles=tiles,
                nations=nations,
                width=256,
                height=256,
                layer_mode=layer,
                show_cities=True,
                show_trade_routes=True,
                show_provinces=True,
                show_cell_outlines=True,
                show_resources=True,
                nation_alpha=0.6,
                selected_cell_index=None,
                frame=0,
            )
            self.assertIsInstance(surf, pygame.Surface)
            self.assertEqual(surf.get_size(), (256, 256))

    def test_save_slot_geopolitics_persistence(self):
        slot_data = {
            "slot": 3,
            "date": "2026-09-24 20:20",
            "summary": "Test Geopolitics Slot",
            "state": {
                "mode": "geopolitics",
                "geo_layer": "provinces",
                "nations": 5,
                "nation_seed": 999,
                "nation_alpha": 0.75,
                "show_cities": False,
                "show_trade": True,
                "show_provinces": True,
                "show_outlines": False,
                "show_resources": True,
            }
        }
        ok = mapgen_web.save_slot_to_file(3, slot_data)
        self.assertTrue(ok)

        slots = mapgen_web.get_all_saved_slots()
        slot_3 = slots.get("slots", {}).get("3")
        self.assertIsNotNone(slot_3)
        state = slot_3.get("state", {})
        self.assertEqual(state.get("mode"), "geopolitics")
        self.assertEqual(state.get("geo_layer"), "provinces")
        self.assertEqual(state.get("nations"), 5)
        self.assertEqual(state.get("nation_seed"), 999)
        self.assertEqual(state.get("nation_alpha"), 0.75)
        self.assertFalse(state.get("show_cities"))

        # Clean up test slot
        mapgen_web.clear_slot_file(3)


if __name__ == "__main__":
    unittest.main()
