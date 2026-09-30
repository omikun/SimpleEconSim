"""
terrain/biomes/whittaker.py — 2D Whittaker Biome Classification and Color Palette.
"""

from typing import Dict, Tuple

BIOME_COLORS: Dict[str, Tuple[int, int, int]] = {
    'OCEAN': (44, 78, 122),
    'LAKE': (58, 118, 168),
    'BEACH': (198, 185, 142),
    'SNOW': (248, 250, 252),
    'TUNDRA': (180, 186, 172),
    'BARE': (142, 142, 138),
    'SCORCHED': (92, 88, 82),
    'TAIGA': (144, 166, 116),
    'SHRUBLAND': (140, 158, 120),
    'TEMPERATE_DESERT': (206, 212, 156),
    'TEMPERATE_RAIN_FOREST': (58, 132, 82),
    'TEMPERATE_DECIDUOUS_FOREST': (96, 148, 86),
    'GRASSLAND': (132, 172, 88),
    'TROPICAL_RAIN_FOREST': (48, 110, 68),
    'TROPICAL_SEASONAL_FOREST': (82, 140, 78),
    'SUBTROPICAL_DESERT': (218, 204, 154),
}


def mapgen2_biome(temperature: float, moisture: float) -> str:
    """Whittaker diagram mapping (temperature, moisture) in [0.0, 1.0] to a biome.

    Matches Amit Patel's mapgen2 reference classification:
    https://github.com/amitp/mapgen2/blob/master/Map.as (getBiome)
    """
    if temperature < 0.25:
        if moisture > 0.50:
            return 'SNOW'
        elif moisture > 0.33:
            return 'TUNDRA'
        elif moisture > 0.16:
            return 'BARE'
        else:
            return 'SCORCHED'
    elif temperature < 0.50:
        if moisture > 0.66:
            return 'TAIGA'
        elif moisture > 0.33:
            return 'SHRUBLAND'
        else:
            return 'TEMPERATE_DESERT'
    elif temperature < 0.70:
        if moisture > 0.83:
            return 'TEMPERATE_RAIN_FOREST'
        elif moisture > 0.50:
            return 'TEMPERATE_DECIDUOUS_FOREST'
        elif moisture > 0.16:
            return 'GRASSLAND'
        else:
            return 'TEMPERATE_DESERT'
    else:
        if moisture > 0.66:
            return 'TROPICAL_RAIN_FOREST'
        elif moisture > 0.33:
            return 'TROPICAL_SEASONAL_FOREST'
        elif moisture > 0.16:
            return 'GRASSLAND'
        else:
            return 'SUBTROPICAL_DESERT'


def whittaker_biome(elevation: float, moisture: float) -> str:
    """Whittaker diagram mapping (elevation, moisture) in [0.0, 1.0] to a terrestrial biome.

    Equivalent to mapgen2_biome(1.0 - elevation, moisture).
    """
    return mapgen2_biome(1.0 - elevation, moisture)
