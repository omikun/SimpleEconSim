"""
world_config.py — Centralized world and gameplay configuration for Call of Capital (CoC).

Provides top-level configuration switches between:
- "voronoi": Native Mapgen2 Voronoi irregular polygon cells (Crusader Kings / RimWorld style)
- "hex": Classic 9x9 axial pointy-top honeycomb grid (Civilization style)

GameplayFlags is an immutable per-run value; topology remains a legacy
process-wide setting until its own migration.
"""

import os
import json
import tempfile
from dataclasses import asdict, dataclass, fields, replace
from typing import Literal

TopologyType = Literal["voronoi", "hex"]


@dataclass(frozen=True, slots=True)
class GameplayFlags:
    """Per-run switches for independently stepped gameplay mechanisms.

    Defaults preserve the full game. Player policies and scenario state are not
    feature switches and remain on their owning objects.
    """

    nation_ai: bool = True
    construction_projects: bool = True
    private_technology_adoption: bool = True
    wage_quotes: bool = True
    trade_epidemic_spread: bool = True
    migration: bool = True
    frontier_claims: bool = True
    regime: bool = True
    military: bool = True
    wars: bool = True
    diplomacy: bool = True
    innovation: bool = True
    popular_resistance: bool = True
    imperialism: bool = True
    sovereign_bonds: bool = True
    scenario_progression: bool = True
    workhouse: bool = True
    elite_planning: bool = True
    career_mobility: bool = True
    workplace_resistance: bool = True
    foraging: bool = True
    wilderness: bool = True
    feudal_tribute: bool = True
    abundance: bool = True
    national_food_logistics: bool = True
    food_spoilage: bool = True
    food_relief: bool = True
    household_food: bool = True
    taxation: bool = True
    profits: bool = True
    household_lifecycle: bool = True
    local_market: bool = True
    labor_market: bool = True
    wages: bool = True
    production: bool = True
    independent_input_requests: bool = True
    forex: bool = True
    regional_trade: bool = True
    land_rent: bool = True
    crop_credit: bool = True
    crop_share_tenancy: bool = True
    alienation: bool = True
    pollution: bool = True
    disease: bool = True
    factions: bool = True
    unrest: bool = True

    def __post_init__(self):
        invalid = [field.name for field in fields(self)
                   if type(getattr(self, field.name)) is not bool]
        if invalid:
            raise TypeError(f"Gameplay flags must be booleans: {', '.join(invalid)}")

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


GAMEPLAY_FLAGS_VERSION = 3
FULL_GAMEPLAY_FLAGS = GameplayFlags()
GAMEPLAY_FLAG_NAMES = frozenset(field.name for field in fields(GameplayFlags))
GAMEPLAY_FLAG_DEPENDENCIES = {
    "trade_epidemic_spread": ("disease",),
    "wilderness": ("foraging", "household_food", "household_lifecycle"),
}
GAMEPLAY_PROFILE_NAMES = ("full", "core")
SCENARIO_GAMEPLAY_OVERRIDES = {
    "labor_frontier_rivalry": {
        "elite_planning": False,
        "career_mobility": False,
        "abundance": False,
        "private_technology_adoption": False,
        "wage_quotes": False,
    },
    "supply_rivalry": {
        "elite_planning": False,
        "career_mobility": False,
        "abundance": False,
        "private_technology_adoption": False,
        "wage_quotes": False,
    },
}


def validate_gameplay_profile(profile: str) -> str:
    """Return a canonical profile name or reject an unknown experiment."""
    if not isinstance(profile, str):
        raise ValueError(f"Unknown gameplay profile: {profile!r}")
    if profile in GAMEPLAY_PROFILE_NAMES:
        return profile
    prefix = "isolate:"
    if profile.startswith(prefix) and profile[len(prefix):] in GAMEPLAY_FLAG_NAMES:
        return profile
    raise ValueError(f"Unknown gameplay profile: {profile!r}")


def _dependency_closure(names):
    resolved = set(names)
    pending = list(resolved)
    while pending:
        for dependency in GAMEPLAY_FLAG_DEPENDENCIES.get(pending.pop(), ()):
            if dependency not in resolved:
                resolved.add(dependency)
                pending.append(dependency)
    return resolved


def gameplay_flags_for(owner) -> GameplayFlags:
    """Read the explicit run context attached to a region or nation."""
    return getattr(owner, '_gameplay_flags', FULL_GAMEPLAY_FLAGS)


def resolve_gameplay_flags(*, disabled=(), base: GameplayFlags | None = None,
                           profile: str | None = None,
                           scenario_id: str | None = None) -> GameplayFlags:
    """Resolve a full, core, or one-mechanism experiment before world creation."""
    if base is not None and profile is not None:
        raise ValueError("Choose either a named profile or an explicit base config")
    if base is not None:
        flags = base
    else:
        selected_profile = validate_gameplay_profile(profile or "full")
        if selected_profile == "full":
            flags = FULL_GAMEPLAY_FLAGS
        elif selected_profile == "core":
            flags = replace(FULL_GAMEPLAY_FLAGS,
                            **{name: False for name in GAMEPLAY_FLAG_NAMES})
        else:
            mechanism = selected_profile[len("isolate:"):]
            enabled = _dependency_closure((mechanism,))
            flags = replace(FULL_GAMEPLAY_FLAGS,
                            **{name: name in enabled for name in GAMEPLAY_FLAG_NAMES})
    if not isinstance(flags, GameplayFlags):
        raise TypeError("base must be a GameplayFlags value")
    if scenario_id is not None and (base is not None or selected_profile == "full"):
        overrides = SCENARIO_GAMEPLAY_OVERRIDES.get(scenario_id, {})
        flags = replace(flags, **overrides)
    disabled = (disabled,) if isinstance(disabled, str) else tuple(disabled)
    unknown = set(disabled) - GAMEPLAY_FLAG_NAMES
    if unknown:
        raise ValueError(f"Unknown gameplay flags: {', '.join(sorted(unknown))}")
    if (profile and profile.startswith("isolate:")
            and set(disabled) & _dependency_closure((profile[len("isolate:"):],))):
        raise ValueError("Cannot disable a mechanism required by the isolate profile")
    flags = replace(flags, **{name: False for name in disabled})
    if not flags.disease:
        flags = replace(flags, trade_epidemic_spread=False)
    for mechanism, dependencies in GAMEPLAY_FLAG_DEPENDENCIES.items():
        if getattr(flags, mechanism) and any(not getattr(flags, name) for name in dependencies):
            flags = replace(flags, **{mechanism: False})
    return flags


def describe_gameplay_flags(profile: str, flags: GameplayFlags) -> str:
    """Format the resolved mechanism set for reproducible CLI startup logs."""
    profile = validate_gameplay_profile(profile)
    enabled = [name for name, active in flags.as_dict().items() if active]
    return (f"Profile: {profile}; enabled: "
            f"{', '.join(enabled) if enabled else 'none'}")

# Default topology setting
_DEFAULT_TOPOLOGY: TopologyType = "voronoi"

# Runtime active topology
_ACTIVE_TOPOLOGY: TopologyType = (os.environ.get("COC_TOPOLOGY") or _DEFAULT_TOPOLOGY).lower()
if _ACTIVE_TOPOLOGY not in ("voronoi", "hex"):
    _ACTIVE_TOPOLOGY = _DEFAULT_TOPOLOGY

# Voronoi World Configuration
VORONOI_POINTS = 80          # Comparable to 81 cells in 9x9 hex grid
VORONOI_ISLAND_SHAPE = "perlin"
VORONOI_WIDTH = 1024.0
VORONOI_HEIGHT = 1024.0


def load_mapgen_slot_one() -> dict:
    """Load the saved Mapgen2 world used by the default Voronoi client."""
    slot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saved_slots", "slot_1.json")
    try:
        with open(slot_path, "r", encoding="utf-8") as slot_file:
            state = json.load(slot_file).get("state", {})
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def mapgen_mesh_graph_key(gen) -> tuple:
    """Identify the actual generator behind a cached micropolygon mesh."""
    return (
        int(gen.seed), gen.island_shape,
        int(gen.num_points), int(gen.river_count),
        round(float(gen.mountain_sharpness), 2),
        round(float(gen.moisture_bias), 2),
        round(float(gen.north_temperature), 2),
        round(float(gen.south_temperature), 2),
        round(float(gen.persistence), 2),
        round(float(gen.canyon_depth), 2),
        round(float(gen.valley_width), 2),
        int(gen.width), int(gen.height),
    )

# Hex World Configuration
HEX_GRID_ROWS = 9
HEX_GRID_COLS = 9
HEX_SIZE = 50.0

UIMode = Literal["guided", "advanced"]
_DEFAULT_UI_MODE: UIMode = "advanced"
_UI_SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".coc", "ui_settings.json")


def get_ui_mode() -> UIMode:
    """Return the configured UI composition (environment override, then user setting)."""
    override = (os.environ.get("COC_UI_MODE") or "").strip().lower()
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
