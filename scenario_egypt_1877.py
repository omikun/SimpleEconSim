"""Authored setup and player-facing content for Egypt's 1877 crisis scenario."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import random


SCENARIO_ID = "egypt_1877"
SCENARIO = {
    "id": SCENARIO_ID,
    "title": "Egypt's Grain and Debt Crisis",
    "year": 1877,
    "polity": "Khedivate of Egypt",
    "ruler": "Khedive Ismail Pasha",
    "capital": "Cairo",
    "locations": ("Cairo", "Nile Delta", "Upper Egypt", "Alexandria"),
    "institutions": ("Caisse de la Dette Publique",),
    "briefing": (
        "A very low Nile has put the maize harvest at risk. Cairo's relief stores "
        "are limited, while Egypt's assigned revenues and export receipts are "
        "already tied to debt service overseen by the Caisse. Decide what food "
        "to release, what revenue to protect, and whose burden will rise.",
    ),
    "horizon_turns": 20,
    "relief_stock_turns": 4,
    "payment_window_turn": 6,
    "pressures": (
        {"id": "food_access", "title": "Household maize access"},
        {"id": "debt_service", "title": "Next debt-service window"},
        {"id": "political_support", "title": "Political support"},
    ),
    "opening_events": (
        {"turn": 1, "id": "low_nile", "kind": "harvest_shock", "severity": 0.30},
        {"turn": 6, "id": "debt_service_window", "kind": "payment_due"},
    ),
    "outcomes": (
        {"id": "relief_and_payment", "food_access": "protected", "debt": "paid"},
        {"id": "creditor_settlement", "food_access": "protected", "debt": "restructured"},
        {"id": "coercive_extraction", "food_access": "poor", "political_cost": "high"},
        {"id": "breakdown", "government_control": "lost"},
    ),
    # Fixed map seeds make this authored campaign reproducible without affecting
    # ordinary sandbox generation. CLI seed flags remain available for tuning.
    "seeds": {"world": 1877, "terrain": 1877, "nations": 1877},
}


def is_scenario_id(value: str | None) -> bool:
    return value == SCENARIO_ID


@contextmanager
def deterministic_generation(seed: int):
    """Seed both standard and cached RNGs for scenario setup, then restore them."""
    from random_cache import rand

    random_state = random.getstate()
    cache_state = (rand._seed, rand._idx, rand._buf)
    random.seed(seed)
    rand._seed = seed
    rand._idx = rand._capacity
    rand._buf = [0.0] * rand._capacity
    try:
        yield
    finally:
        random.setstate(random_state)
        rand._seed, rand._idx, rand._buf = cache_state


def prepare_world(world: dict) -> dict:
    """Attach scenario identity and opening state to a generated deterministic map."""
    egypt = next((nation for nation in world.get("nations", []) if nation.name == "Egypt"), None)
    if egypt is None:
        raise ValueError("Egypt 1877 setup requires the Egypt starting nation.")

    egypt.display_name = SCENARIO["polity"]
    egypt.regime_type = "autocracy"
    egypt.government.regime_type = "autocracy"
    world["player_nation_name"] = egypt.name
    world["selected_nation"] = egypt
    world["scenario_id"] = SCENARIO_ID
    world["scenario"] = deepcopy(SCENARIO)
    world["scenario_state"] = {
        "turns_remaining": SCENARIO["horizon_turns"],
        "public_maize_stock_turns": SCENARIO["relief_stock_turns"],
        "payment_window_turn": SCENARIO["payment_window_turn"],
        "ending": None,
        "actions_taken": [],
        "events_fired": [],
    }
    world["scenario_feedback"] = "Opening crisis: low Nile, threatened maize harvest, and debt service."
    world["scenario_location_by_tile"] = _assign_location_roles(egypt)
    capital = getattr(egypt, "capital", None)
    if capital is not None:
        world["selected_region"] = capital
        capital.display_name = "Cairo"
    world["turn"] = 0
    world["playing"] = False
    world["guided_analysis_open"] = False
    return world


def _assign_location_roles(nation) -> dict[str, str]:
    """Assign stable display roles to this generated Egypt cluster's regions."""
    tiles = list(getattr(nation, "tiles", []))
    if not tiles:
        return {}

    def north_south_key(tile):
        if hasattr(tile, "centroid"):
            return (float(tile.centroid[1]), tile.name)
        return (float(getattr(tile, "grid_r", 0)), tile.name)

    ordered = sorted(tiles, key=north_south_key)
    capital = getattr(nation, "capital", None) or ordered[len(ordered) // 2]
    aliases = {capital.name: "Cairo"}
    remaining = [tile for tile in ordered if tile is not capital]

    coastal = [tile for tile in remaining if getattr(tile, "is_coast", False)]
    if coastal:
        alexandria = coastal[0]
        aliases[alexandria.name] = "Alexandria"
        remaining.remove(alexandria)

    if remaining:
        northern = min(remaining, key=north_south_key)
        aliases[northern.name] = "Nile Delta"
        remaining.remove(northern)
    if remaining:
        southern = max(remaining, key=north_south_key)
        aliases[southern.name] = "Upper Egypt"

    for tile in tiles:
        if tile.name in aliases:
            tile.display_name = aliases[tile.name]
            tile.scenario_location = aliases[tile.name]
    return aliases
