"""
test_geographic_demographics_and_trade.py — Unit Tests for Geographic Demographics,
Mountain Terrain Preservation, Occupation Allocation, and Capped Trade Networks.

Verifies:
1. Mountain terrain preservation: Claimed regions on mountains retain high elevation and mountain biomes.
2. Geographic population scaling: Mountains (~45), Hills (~75), Plains (~95), Coasts (~135).
3. Zero loggers/carpenters in mountains (no trees), enhanced farming/fishing on coasts.
4. Natural resources: Zero timber generated on high mountain peaks.
5. Capped trade partners: Mountain tiles have <= 2 neighbors; general tiles have <= 3 neighbors.
6. Pioneer migration: Settlers prioritize mineral-rich wilderness tiles.
"""

import unittest
from sim_world import build_world
from goods import Goods
from tile_resources import TileResource
from migration import _score_wilderness_attractiveness


class TestGeographicDemographicsAndTrade(unittest.TestCase):

    def setUp(self):
        # Build deterministic world
        self.tiles, self.nations, self.grid = build_world(seed=42, terrain_seed=12345, nation_seed=67890)

    def test_mountain_terrain_preservation_and_no_plains_wipe(self):
        """Verify claimed nation tiles on mountain terrain are NOT wiped to flat plains."""
        mountain_found = False
        for n in self.nations:
            for t in n.tiles:
                # If the underlying topography is high elevation, it must keep mountain biome and high elevation
                if t.elevation >= 0.72:
                    mountain_found = True
                    self.assertIn(t.biome, ('mountains', 'snow_peaks'))
                    self.assertGreaterEqual(t.elevation_meters, 2000)
                    self.assertNotEqual(t.biome, 'plains')
                elif t.elevation >= 0.48:
                    self.assertIn(t.biome, ('hills', 'mountains', 'snow_peaks'))
                    self.assertNotEqual(t.biome, 'plains')

        # Across all claimed and wilderness tiles, verify mountain biomes exist on land
        land_mountains = [t for t in self.tiles if not getattr(t, 'is_ocean', False) and t.elevation >= 0.72]
        self.assertTrue(len(land_mountains) > 0)
        for m in land_mountains:
            self.assertIn(m.biome, ('mountains', 'snow_peaks'))

    def test_geographic_starting_population(self):
        """Verify starting population is scaled by terrain (mountains sparse, coasts populous)."""
        for t in self.tiles:
            if getattr(t, 'is_ocean', False):
                self.assertEqual(len(t.agents), 0)
                continue

            elev = getattr(t, 'elevation', 0.20)
            biome = getattr(t, 'biome', 'plains')
            is_mountain = (elev >= 0.72) or (biome in ('mountains', 'snow_peaks'))
            is_coast = getattr(t, 'is_coast', False) or (biome == 'coast')

            if getattr(t, 'owner_nation', None) is not None:
                citizens = [a for a in t.agents if not getattr(a, 'is_trader', False) and not getattr(a, 'is_government', False)]
                if is_mountain:
                    self.assertEqual(len(citizens), 45)
                elif is_coast:
                    self.assertEqual(len(citizens), 135)
                elif elev >= 0.40:
                    self.assertEqual(len(citizens), 75)
                else:
                    self.assertEqual(len(citizens), 95)

    def test_mountain_and_coast_occupations(self):
        """Verify zero loggers/carpenters in mountains, and higher farming on coasts."""
        for n in self.nations:
            for t in n.tiles:
                elev = getattr(t, 'elevation', 0.20)
                biome = getattr(t, 'biome', 'plains')
                is_mountain = (elev >= 0.72) or (biome in ('mountains', 'snow_peaks'))
                is_coast = getattr(t, 'is_coast', False) or (biome == 'coast')

                citizens = [a for a in t.agents if not getattr(a, 'is_trader', False) and not getattr(a, 'is_government', False)]
                loggers = sum(1 for a in citizens if a.output == Goods.wood)
                carpenters = sum(1 for a in citizens if a.output == Goods.furniture)
                farmers = sum(1 for a in citizens if a.output == Goods.food)

                if is_mountain:
                    # Strictly no trees in mountains -> 0 loggers and 0 carpenters
                    self.assertEqual(loggers, 0)
                    self.assertEqual(carpenters, 0)
                    self.assertEqual(farmers, len(citizens))
                elif is_coast:
                    # Coast has high agricultural and fishing concentration (>= 80%)
                    self.assertGreaterEqual(farmers / len(citizens), 0.80)

    def test_no_timber_on_high_mountain_summits(self):
        """Verify high mountain peaks (elevation >= 0.72) never generate timber."""
        for t in self.tiles:
            elev = getattr(t, 'elevation', 0.0)
            if elev >= 0.72:
                self.assertNotIn(TileResource.TIMBER, getattr(t, 'natural_resources', set()))

    def test_capped_trade_partner_network(self):
        """Verify mountains have at most 2 neighbors and general tiles have at most 3."""
        for t in self.tiles:
            if getattr(t, 'is_ocean', False):
                continue
            elev = getattr(t, 'elevation', 0.0)
            biome = getattr(t, 'biome', 'plains')
            is_mountain = (elev >= 0.72) or (biome in ('mountains', 'snow_peaks'))

            num_partners = len(t.neighbors)
            if is_mountain:
                self.assertLessEqual(num_partners, 2)
            else:
                self.assertLessEqual(num_partners, 3)

    def test_settlers_attracted_to_mineral_mountains(self):
        """Verify pioneer attractiveness scoring favors mineral-rich mountains."""
        class MockTile:
            def __init__(self, resources, pop=0):
                self.natural_resources = resources
                self.wilderness_pop = pop
                self.agents = []

        plain_tile = MockTile(resources={TileResource.PASTURE_FLAX}, pop=30)
        iron_mountain = MockTile(resources={TileResource.IRON_ORE, TileResource.RARE_MINERALS}, pop=10)

        score_plain = _score_wilderness_attractiveness(plain_tile)
        score_mountain = _score_wilderness_attractiveness(iron_mountain)

        # Mineral rush bonus must make rich mountain tile more attractive to pioneers
        self.assertGreater(score_mountain, score_plain)


if __name__ == "__main__":
    unittest.main()
