"""
world_config.py — Centralized Topology and World Generation Configuration for REGNUM.

Provides top-level configuration switches between:
- "voronoi": Native Mapgen2 Voronoi irregular polygon cells (Crusader Kings / RimWorld style)
- "hex": Classic 9x9 axial pointy-top honeycomb grid (Civilization style)

Allows zero-risk instant rollback between implementations.
"""

import os
import json
import tempfile
from typing import Literal

TopologyType = Literal["voronoi", "hex"]

# Default topology setting
_DEFAULT_TOPOLOGY: TopologyType = "voronoi"

# Runtime active topology
_ACTIVE_TOPOLOGY: TopologyType = os.environ.get("REGNUM_TOPOLOGY", _DEFAULT_TOPOLOGY).lower()
if _ACTIVE_TOPOLOGY not in ("voronoi", "hex"):
    _ACTIVE_TOPOLOGY = _DEFAULT_TOPOLOGY

# Voronoi World Configuration
VORONOI_POINTS = 80          # Comparable to 81 cells in 9x9 hex grid
VORONOI_ISLAND_SHAPE = "perlin"
VORONOI_WIDTH = 1000.0
VORONOI_HEIGHT = 1000.0

# Hex World Configuration
HEX_GRID_ROWS = 9
HEX_GRID_COLS = 9
HEX_SIZE = 50.0

UIMode = Literal["guided", "advanced"]
_DEFAULT_UI_MODE: UIMode = "advanced"
_UI_SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".regnum", "ui_settings.json")


def get_ui_mode() -> UIMode:
    """Return the configured UI composition (environment override, then user setting)."""
    override = os.environ.get("REGNUM_UI_MODE", "").strip().lower()
    if override in ("guided", "advanced"):
        return override
    try:
        with open(_UI_SETTINGS_PATH, "r", encoding="utf-8") as settings_file:
            mode = json.load(settings_file).get("ui_mode", _DEFAULT_UI_MODE)
        return mode if mode in ("guided", "advanced") else _DEFAULT_UI_MODE
    except (OSError, ValueError, TypeError):
        return _DEFAULT_UI_MODE


def set_ui_mode(mode: str, persist: bool = True) -> UIMode:
    """Set UI composition and, by default, persist it for future launches."""
    global _DEFAULT_UI_MODE
    normalized = str(mode).strip().lower()
    if normalized not in ("guided", "advanced"):
        raise ValueError("UI mode must be 'guided' or 'advanced'.")
    _DEFAULT_UI_MODE = normalized
    if persist:
        os.makedirs(os.path.dirname(_UI_SETTINGS_PATH), exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="ui_settings.", suffix=".tmp", dir=os.path.dirname(_UI_SETTINGS_PATH))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as settings_file:
                json.dump({"ui_mode": normalized}, settings_file, indent=2)
                settings_file.write("\n")
            os.replace(temp_path, _UI_SETTINGS_PATH)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    return normalized


def get_map_topology() -> TopologyType:
    """Return the currently active map topology ('voronoi' or 'hex')."""
    return _ACTIVE_TOPOLOGY


def set_map_topology(topology: TopologyType) -> None:
    """Dynamically set the active map topology."""
    global _ACTIVE_TOPOLOGY
    top_clean = topology.lower().strip()
    if top_clean not in ("voronoi", "hex"):
        raise ValueError(f"Invalid topology '{topology}'. Must be 'voronoi' or 'hex'.")
    _ACTIVE_TOPOLOGY = top_clean


def is_voronoi_topology() -> bool:
    """Return True if the current active topology is Voronoi irregular polygons."""
    return get_map_topology() == "voronoi"


def is_hex_topology() -> bool:
    """Return True if the current active topology is standard hex honeycomb."""
    return get_map_topology() == "hex"
