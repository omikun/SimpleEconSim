"""
render_engine/layers.py — Visual map layer definitions and color conventions.
"""

from enum import Enum
from typing import List, Tuple, Optional


class LayerType(str, Enum):
    OVERVIEW = 'overview'
    PHYSICAL = 'physical'
    POPULATION = 'population'
    ECONOMY = 'economy'
    PRODUCTION = 'production'
    MILITARY = 'military'
    ENCLOSURE = 'enclosure'
    EXPLOITATION = 'exploitation'
    EXTERNALITIES = 'externalities'


class LayerInfo:
    def __init__(self, layer_type: LayerType, name: str, key: str, color: Tuple[int, int, int], description: str):
        self.layer_type = layer_type
        self.name = name
        self.key = key
        self.color = color
        self.description = description


MAP_LAYERS = [
    ('overview', '1. Overview', '1', (245, 210, 95), 'General map overview'),
    ('physical', '2. Physical & Height', '2', (140, 225, 255), 'Elevation, biomes & terrain bonuses'),
    ('population', '3. Population & Unrest', '3', (245, 140, 60), 'Demographics, hunger & social order'),
    ('economy', '4. Economy & Wealth', '4', (120, 225, 130), 'Regional GDP, price basket & deposits'),
    ('production', '5. Production & Output', '5', (245, 210, 90), 'Resource outputs & completed buildings'),
    ('military', '6. Military & Defense', '6', (235, 80, 80), 'Troops, garrison strength & border threat'),
    ('enclosure', '7. Land Tenure', '7', (215, 175, 75), 'Customary commons vs enclosed plots'),
    ('exploitation', '8. Exploitation & Strikes', '8', (235, 75, 75), 'Surplus rate s/v & active wildcat strikes'),
    ('externalities', '9. Ecology & Rift', '9', (100, 215, 140), 'Soil fertility, smog & toxic runoff'),
]

LAYER_KEYS = {item[2]: item[0] for item in MAP_LAYERS}


def get_all_layers() -> List[LayerInfo]:
    return [
        LayerInfo(LayerType(item[0]), item[1], item[2], item[3], item[4])
        for item in MAP_LAYERS
    ]


def get_layer_by_key(key: str) -> Optional[LayerInfo]:
    for layer in get_all_layers():
        if layer.key == key:
            return layer
    return None


def get_layer_by_hotkey(pygame_key: int) -> Optional[LayerInfo]:
    # Support 1-9 and numpad 1-9
    key_map = {
        49: '1', 50: '2', 51: '3', 52: '4', 53: '5', 54: '6', 55: '7', 56: '8', 57: '9',
        1073741913: '1', 1073741914: '2', 1073741915: '3', 1073741916: '4', 1073741917: '5',
        1073741918: '6', 1073741919: '7', 1073741920: '8', 1073741921: '9',
    }
    char_key = key_map.get(pygame_key)
    if char_key:
        return get_layer_by_key(char_key)
    return None
