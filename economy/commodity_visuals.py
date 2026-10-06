"""
economy/commodity_visuals.py — Fast Slot Acceleration & UI Symbol/Texture Mapping (Issue-11).

Provides high-performance pre-allocated slot lookups, procedural color palettes,
UI glyphs, and map overlay badges for both core Goods and dynamically registered commodities.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Tuple
from goods import Goods, profession


# Static visual definitions for all core and capitalist propagation commodities
COMMODITY_METADATA: Dict[str, Dict[str, Any]] = {
    'food': {
        'symbol': '🌾',
        'color_rgb': (218, 165, 32), # Goldenrod
        'profession_char': 'F',
        'category': 'subsistence',
        'texture_style': 'grain_field',
    },
    'wood': {
        'symbol': '🪵',
        'color_rgb': (139, 69, 19),   # SaddleBrown
        'profession_char': 'W',
        'category': 'raw_material',
        'texture_style': 'timber_grove',
    },
    'furniture': {
        'symbol': '🪑',
        'color_rgb': (160, 82, 45),   # Sienna
        'profession_char': 'C',
        'category': 'manufacture',
        'texture_style': 'carpenter_workshop',
    },
    'transport': {
        'symbol': '🐎',
        'color_rgb': (112, 128, 144), # SlateGray
        'profession_char': 'P',
        'category': 'service',
        'texture_style': 'cart_depot',
    },
    'wool': {
        'symbol': '🐑',
        'color_rgb': (245, 245, 220), # Beige
        'profession_char': 'S',
        'category': 'cash_crop',
        'texture_style': 'enclosed_pasture',
    },
    'cloth': {
        'symbol': '🧵',
        'color_rgb': (70, 130, 180),  # SteelBlue
        'profession_char': 'T',
        'category': 'manufacture',
        'texture_style': 'weaving_loom',
    },
    'cotton': {
        'symbol': '☁️',
        'color_rgb': (250, 240, 230), # Linen / Cotton White
        'profession_char': 'O',
        'category': 'cash_crop',
        'texture_style': 'cotton_boll_rows',
    },
    'sugar': {
        'symbol': '🍬',
        'color_rgb': (255, 228, 196), # Bisque
        'profession_char': 'U',
        'category': 'cash_crop',
        'texture_style': 'cane_stalks',
    },
    'tobacco': {
        'symbol': '🍂',
        'color_rgb': (184, 115, 51),  # Copper Brown
        'profession_char': 'Y',
        'category': 'cash_crop',
        'texture_style': 'cured_leaf',
    },
    'iron_ore': {
        'symbol': '⛏️',
        'color_rgb': (105, 105, 105), # DimGray
        'profession_char': 'I',
        'category': 'mineral',
        'texture_style': 'rocky_shaft',
    },
    'iron': {
        'symbol': '🔩',
        'color_rgb': (192, 192, 192), # Silver
        'profession_char': 'B',
        'category': 'capital_goods',
        'texture_style': 'smelter_anvil',
    },
    'coal': {
        'symbol': '⬛',
        'color_rgb': (40, 40, 40),     # Charcoal
        'profession_char': 'K',
        'category': 'mineral',
        'texture_style': 'coal_pit',
    },
    'nitrates': {
        'symbol': '🧂',
        'color_rgb': (230, 230, 250), # Lavender
        'profession_char': 'N',
        'category': 'mineral',
        'texture_style': 'guano_bed',
    },
    'rum': {
        'symbol': '🍶',
        'color_rgb': (178, 34, 34),   # Firebrick
        'profession_char': 'V',
        'category': 'luxury',
        'texture_style': 'distillery_cask',
    },
    'fine_textiles': {
        'symbol': '👘',
        'color_rgb': (147, 112, 219), # MediumPurple
        'profession_char': 'X',
        'category': 'luxury',
        'texture_style': 'damask_loom',
    },
    'porcelain': {
        'symbol': '🏺',
        'color_rgb': (240, 255, 240), # Honeydew / White China
        'profession_char': 'Z',
        'category': 'luxury',
        'texture_style': 'pottery_kiln',
    },
    'foreign_luxuries': {
        'symbol': '💎',
        'color_rgb': (255, 215, 0),   # Gold
        'profession_char': 'L',
        'category': 'luxury',
        'texture_style': 'treasure_chest',
    },
}

# Pre-allocated slot mapping: good name -> integer array index
_COMMODITY_SLOT_CACHE: Dict[str, int] = {}
_NEXT_SLOT_INDEX = [0]

# Pre-populate with core Goods enum
for g in Goods:
    _COMMODITY_SLOT_CACHE[g.name] = g.value
    if g.value >= _NEXT_SLOT_INDEX[0]:
        _NEXT_SLOT_INDEX[0] = g.value + 1


def get_fast_commodity_slot(good: Any) -> int:
    """Returns the contiguous 0-based integer slot index for array lookups."""
    name = good.name if hasattr(good, 'name') else str(good)
    if name not in _COMMODITY_SLOT_CACHE:
        slot = _NEXT_SLOT_INDEX[0]
        _COMMODITY_SLOT_CACHE[name] = slot
        _NEXT_SLOT_INDEX[0] += 1
        return slot
    return _COMMODITY_SLOT_CACHE[name]


def get_commodity_visual(good: Any) -> Dict[str, Any]:
    """Retrieve UI symbol, color, and texture rendering metadata for any good."""
    name = good.name if hasattr(good, 'name') else str(good)
    if name in COMMODITY_METADATA:
        return COMMODITY_METADATA[name]

    # Procedural fallback for dynamically injected novel commodities
    # Deterministic hash color
    h = hash(name)
    r = (h & 0xFF0000) >> 16
    g = (h & 0x00FF00) >> 8
    b = (h & 0x0000FF)
    p_char = profession.get(good, name[0].upper() if name else '?')

    return {
        'symbol': '📦',
        'color_rgb': (min(240, max(40, r)), min(240, max(40, g)), min(240, max(40, b))),
        'profession_char': p_char,
        'category': 'novel_commodity',
        'texture_style': 'procedural_crate',
    }
