"""Authored setup and player-facing content for Egypt's 1877 crisis scenario."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import random
from goods import Goods


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
        "A weak Nile flood threatens the maize harvest. Cairo's relief stores are "
        "limited, and assigned revenues support debt service overseen by the "
        "Caisse. Choose what food to release and whose claims to protect.",
    ),
    "horizon_turns": 20,
    "relief_stock_turns": 4,
    "payment_window_turn": 6,
    "thresholds": {"protected_hunger_rate": 0.20, "breakdown_legitimacy": 0.10, "breakdown_unrest": 0.85},
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
    "actions": (
        {"id": "release_maize", "title": "Release maize reserves", "turn_cost": 1},
        {"id": "prioritize_domestic_grain", "title": "Keep more grain in Egypt", "turn_cost": 1},
        {"id": "reduce_fellahin_tax", "title": "Reduce cultivator taxes", "turn_cost": 1},
        {"id": "raise_local_taxes", "title": "Raise local taxes", "turn_cost": 1},
        {"id": "pay_remittance", "title": "Pay debt service", "turn_cost": 1},
        {"id": "defer_remittance", "title": "Defer debt service", "turn_cost": 1},
        {"id": "concede_revenue", "title": "Concede revenue oversight", "turn_cost": 1},
    ),
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
        "public_maize_stock_units": SCENARIO["relief_stock_turns"] * 30,
        "relief_units_per_turn": 30,
        "scheduled_remittance": 200.0,
        "payment_window_turn": SCENARIO["payment_window_turn"],
        "payment_status": "upcoming",
        "creditor_confidence": 0.6,
        "fiscal_autonomy": 1.0,
        "extraction_level": 0,
        "tax_relief_enacted": False,
        "tax_decision_taken": False,
        "domestic_grain_priority": False,
        "ending": None,
        "actions_taken": [],
        "events_fired": [],
    }
    egypt.government.food_inventory = world["scenario_state"]["public_maize_stock_units"]
    world["scenario_feedback"] = "Opening crisis: low Nile, threatened maize harvest, and debt service."
    world["scenario_location_by_tile"] = _assign_location_roles(egypt)
    for tile in egypt.tiles:
        if getattr(tile, "scenario_location", "") in ("Nile Delta", "Upper Egypt"):
            tile.scenario_food_yield_modifier = 0.55
            tile.scenario_food_yield_modifier_until = 8
    capital = getattr(egypt, "capital", None)
    if capital is not None:
        world["selected_region"] = capital
        capital.display_name = "Cairo"
    world["turn"] = 0
    world["playing"] = False
    world["guided_analysis_open"] = False
    return world


def apply_action(world: dict, action_id: str) -> tuple[bool, str]:
    """Resolve a scenario choice against simulation state and record its cost."""
    if not is_scenario_id(world.get("scenario_id")):
        return False, "This decision is only available in the Egypt 1877 scenario."
    state = world.get("scenario_state", {})
    nation = next((n for n in world.get("nations", []) if n.name == world.get("player_nation_name")), None)
    if nation is None:
        return False, "The scenario government is unavailable."
    turn = int(world.get("turn", 0))
    if state.get("ending"):
        return False, "The campaign has ended."
    if state.get("last_action_turn") == turn:
        return False, "Choose one major decision per turn."

    if action_id == "release_maize":
        available = min(int(state.get("relief_units_per_turn", 30)),
                        int(getattr(nation.government, "food_inventory", 0)))
        if available <= 0:
            return False, "The public maize reserve is empty."
        households = [a for tile in nation.tiles for a in getattr(tile, "agents", [])
                      if getattr(a, "alive", True) and not getattr(a, "is_government", False)
                      and not getattr(a, "is_corporation", False) and not getattr(a, "is_trader", False)]
        households.sort(key=lambda a: (0 if getattr(a, "hungry_steps", 0) > 0 else 1,
                                       float(getattr(a, "cash", 0.0)),
                                       getattr(a, "age_turns", 0)))
        recipients = households[:available]
        if not recipients:
            return False, "No households can receive the public maize reserve."
        for person in recipients:
            person.inv_add(Goods.food, 1)
            if getattr(person, "hungry_steps", 0) > 0:
                person.hungry_steps = 0
        nation.government.food_inventory -= len(recipients)
        state["public_maize_stock_units"] = nation.government.food_inventory
        message = f"Released {len(recipients)} maize rations from the public reserve."
    elif action_id == "prioritize_domestic_grain":
        if state.get("domestic_grain_priority"):
            return False, "More grain is already being retained for domestic supply."
        for tile in nation.tiles:
            tile.food_export_fraction = 0.5
        state["domestic_grain_priority"] = True
        state["creditor_confidence"] = max(0.0, state.get("creditor_confidence", 0.6) - 0.10)
        message = "More food exports will be retained in local granaries; export receipts may fall."
    elif action_id == "reduce_fellahin_tax":
        if state.get("tax_decision_taken"):
            return False, "A local tax decision is already in effect."
        for tile in nation.tiles:
            tile.gov.tax_rate = max(0.0, float(getattr(tile.gov, "tax_rate", 0.0)) - 0.03)
            tile.unrest_level = max(0.0, float(getattr(tile, "unrest_level", 0.0)) - 0.08)
        nation.legitimacy = min(1.0, float(getattr(nation, "legitimacy", 0.5)) + 0.04)
        state["tax_relief_enacted"] = True
        state["tax_decision_taken"] = True
        message = "Reduced regional taxes for cultivators; the treasury will collect less revenue."
    elif action_id == "raise_local_taxes":
        if state.get("tax_decision_taken"):
            return False, "A local tax decision is already in effect."
        for tile in nation.tiles:
            tile.gov.tax_rate = min(0.60, float(getattr(tile.gov, "tax_rate", 0.0)) + 0.05)
            tile.unrest_level = min(1.0, float(getattr(tile, "unrest_level", 0.0)) + 0.12)
        nation.legitimacy = max(0.0, float(getattr(nation, "legitimacy", 0.5)) - 0.08)
        state["tax_decision_taken"] = True
        state["extraction_level"] += 1
        message = "Raised local taxes to protect revenue; cultivator unrest and political strain increased."
    elif action_id in ("pay_remittance", "defer_remittance", "concede_revenue"):
        if turn < int(state.get("payment_window_turn", 6)):
            return False, "The debt-service window has not opened yet."
        if state.get("payment_status") not in ("upcoming", "unpaid"):
            return False, "The debt-service decision has already been resolved."
        amount = float(state.get("scheduled_remittance", 200.0))
        if action_id in ("pay_remittance", "concede_revenue"):
            amount = amount if action_id == "pay_remittance" else amount * 0.5
            if nation.government.agent.cash < amount:
                return False, f"The treasury needs {amount:,.0f} treasury units to make this payment."
            creditors = [n for n in world.get("nations", []) if n.name in ("Britain", "France")]
            if not creditors:
                return False, "The creditor account is unavailable."
            nation.government.agent.cash -= amount
            share = amount / len(creditors)
            for creditor in creditors:
                creditor.government.agent.cash += share
            state["payment_status"] = "paid" if action_id == "pay_remittance" else "restructured"
            state["creditor_confidence"] = min(1.0, state.get("creditor_confidence", 0.6) + 0.15)
            if action_id == "concede_revenue":
                state["fiscal_autonomy"] = max(0.0, state.get("fiscal_autonomy", 1.0) - 0.25)
                message = f"Accepted a reduced {amount:,.0f}-unit remittance and creditor oversight of future revenues."
            else:
                message = f"Paid the {amount:,.0f}-unit scheduled debt-service remittance."
        else:
            state["payment_status"] = "deferred"
            state["creditor_confidence"] = max(0.0, state.get("creditor_confidence", 0.6) - 0.30)
            nation.legitimacy = min(1.0, float(getattr(nation, "legitimacy", 0.5)) + 0.02)
            message = "Deferred the remittance to protect cash for domestic needs; creditor confidence fell."
    else:
        return False, "Unknown scenario decision."

    state["last_action_turn"] = turn
    state.setdefault("actions_taken", []).append({"turn": turn, "action": action_id, "message": message})
    world["scenario_feedback"] = message
    from worldview_engine import ticker_push
    ticker_push(world, turn, "SCENARIO", message, (120, 220, 170))
    return True, message


def advance_scenario(world: dict, turn: int, ticker_push) -> None:
    """Resolve calendar events, thresholds, and the campaign's terminal outcome."""
    if not is_scenario_id(world.get("scenario_id")):
        return
    state = world.setdefault("scenario_state", {})
    nation = next((n for n in world.get("nations", []) if n.name == world.get("player_nation_name")), None)
    if nation is None:
        return
    state["turns_remaining"] = max(0, int(SCENARIO["horizon_turns"]) - turn)
    state.setdefault("events_fired", [])
    if turn == 1 and "low_nile" not in state["events_fired"]:
        state["events_fired"].append("low_nile")
        ticker_push(world, turn, "SCENARIO", "The weak Nile flood cuts the expected food harvest in the Delta and Upper Egypt.", (230, 174, 88))
    if turn == int(state.get("payment_window_turn", 6)) and state.get("payment_status") == "upcoming":
        state["payment_status"] = "unpaid"
        world["playing"] = False
        state["events_fired"].append("debt_service_window")
        ticker_push(world, turn, "ALERT", "The debt-service window is open. Pay, concede revenue oversight, or defer.", (240, 180, 72))
    elif turn > int(state.get("payment_window_turn", 6)) and state.get("payment_status") == "unpaid":
        state["payment_status"] = "defaulted"
        state["creditor_confidence"] = 0.0
        nation.legitimacy = max(0.0, float(getattr(nation, "legitimacy", 0.5)) - 0.15)
        ticker_push(world, turn, "ALERT", "The government missed the debt-service window; default deepens the crisis.", (240, 90, 82))

    metrics = _outcome_metrics(nation)
    thresholds = SCENARIO["thresholds"]
    ended = (metrics["legitimacy"] <= thresholds["breakdown_legitimacy"]
             or metrics["unrest"] >= thresholds["breakdown_unrest"])
    if ended:
        _finish_scenario(world, nation, "breakdown", turn, metrics)
    elif turn >= int(SCENARIO["horizon_turns"]):
        if (metrics["hunger_rate"] <= thresholds["protected_hunger_rate"]
                and state.get("payment_status") == "paid"):
            outcome = "relief_and_payment"
        elif (metrics["hunger_rate"] <= thresholds["protected_hunger_rate"]
              and state.get("payment_status") == "restructured"):
            outcome = "creditor_settlement"
        elif state.get("extraction_level", 0) > 0:
            outcome = "coercive_extraction"
        else:
            outcome = "breakdown"
        _finish_scenario(world, nation, outcome, turn, metrics)


def _outcome_metrics(nation) -> dict:
    households = [a for tile in nation.tiles for a in getattr(tile, "agents", [])
                  if getattr(a, "alive", True) and not getattr(a, "is_government", False)
                  and not getattr(a, "is_corporation", False) and not getattr(a, "is_trader", False)]
    hungry = sum(1 for a in households if getattr(a, "hungry_steps", 0) > 0)
    unrest = sum(float(getattr(tile, "unrest_level", 0.0)) for tile in nation.tiles) / max(1, len(nation.tiles))
    return {
        "households": len(households),
        "hungry": hungry,
        "hunger_rate": hungry / max(1, len(households)),
        "unrest": unrest,
        "legitimacy": float(getattr(nation, "legitimacy", 0.5)),
        "treasury": float(getattr(nation.government.agent, "cash", 0.0)),
    }


def _finish_scenario(world: dict, nation, outcome: str, turn: int, metrics: dict) -> None:
    state = world["scenario_state"]
    state["ending"] = outcome
    state["ending_turn"] = turn
    state["ending_metrics"] = metrics
    state["turns_remaining"] = max(0, int(SCENARIO["horizon_turns"]) - turn)
    state["debrief"] = build_debrief(world, outcome, metrics)
    world["playing"] = False
    world["scenario_feedback"] = state["debrief"]["summary"]


def build_debrief(world: dict, outcome: str, metrics: dict | None = None) -> dict:
    """Summarize the ending and cite the player's decisions and measured state."""
    nation = next((n for n in world.get("nations", []) if n.name == world.get("player_nation_name")), None)
    metrics = metrics or (_outcome_metrics(nation) if nation else {})
    state = world.get("scenario_state", {})
    labels = {
        "relief_and_payment": ("Relief and payment", "Food access held and the scheduled remittance was paid."),
        "creditor_settlement": ("Creditor settlement", "Food access held after a reduced payment and revenue concession."),
        "coercive_extraction": ("Coercive extraction", "The government protected revenue by raising local taxes, increasing unrest and political strain."),
        "breakdown": ("Government breakdown", "The administration lost control of the crisis before it could protect both food access and fiscal capacity."),
    }
    title, summary = labels.get(outcome, labels["breakdown"])
    actions = [entry.get("message", "") for entry in state.get("actions_taken", [])]
    if not actions:
        actions = ["No major scenario decision was recorded before the ending."]
    return {
        "outcome": outcome,
        "title": title,
        "summary": summary,
        "food": f"{metrics.get('hungry', 0)} of {metrics.get('households', 0)} households hungry ({metrics.get('hunger_rate', 0.0):.0%}).",
        "debt": f"Debt service {state.get('payment_status', 'unresolved')}; creditor confidence {state.get('creditor_confidence', 0.0):.0%}; fiscal autonomy {state.get('fiscal_autonomy', 1.0):.0%}.",
        "politics": f"Government legitimacy {metrics.get('legitimacy', 0.0):.0%}; average unrest {metrics.get('unrest', 0.0):.2f}.",
        "actions": actions,
    }


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
