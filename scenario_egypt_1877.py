"""Authored setup and player-facing content for Egypt's 1877 crisis scenario."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from heapq import heappop, heappush
from math import hypot
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
    "terrain": {"shape": "radial", "points": 1000, "rivers": 25, "wave_intensity": 1.0},
    "camera": {"zoom": 2.0},
    "actions": (
        {"id": "release_maize", "title": "Release maize reserves", "turn_cost": 1},
        {"id": "prioritize_domestic_grain", "title": "Keep more grain in Egypt", "turn_cost": 1},
        {"id": "reduce_fellahin_tax", "title": "Reduce cultivator taxes", "turn_cost": 1},
        {"id": "raise_local_taxes", "title": "Raise local taxes", "turn_cost": 1},
        {"id": "pay_remittance", "title": "Pay debt service", "turn_cost": 1},
        {"id": "defer_remittance", "title": "Defer debt service", "turn_cost": 1},
        {"id": "concede_revenue", "title": "Concede revenue oversight", "turn_cost": 1},
        {"id": "default_remittance", "title": "Default on debt service", "turn_cost": 1},
        {"id": "reinforce_alexandria", "title": "Prepare Alexandria's defenses", "turn_cost": 1},
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


def _nile_mainstem(gen):
    """Use a long river that reaches the northern coast of the generated island."""
    mouths = [path for path in gen.river_paths
              if len(path) >= 8 and path[-1][4] >= 1.0]
    if not mouths:
        raise ValueError("Egypt's map needs a river reaching the northern coast.")
    # The renderer projects increasing world y toward the top of the screen.
    return max(mouths, key=lambda path: (path[-1][1], len(path), -path[-1][0]))


def shape_nile_delta(gen) -> None:
    """Give the scenario's north-flowing river a second coastal outlet."""
    if hasattr(gen, "scenario_nile_outlets"):
        return
    mainstem = _nile_mainstem(gen)
    corners = {(corner.x, corner.y): corner for corner in gen.corners}
    main_corners = [corners[(point[0], point[1])] for point in mainstem]
    gen.scenario_nile_mainstem = mainstem
    mouth = main_corners[-1]
    fork = main_corners[-5]
    main_set = set(main_corners)
    queue = [(0.0, fork.index, fork)]
    distances = {fork: 0.0}
    previous = {}
    outlet = None
    while queue:
        cost, _, corner = heappop(queue)
        if cost != distances[corner]:
            continue
        if corner.ocean:
            separation = hypot(corner.x - mouth.x, corner.y - mouth.y)
            if (65.0 <= separation <= 145.0 and corner.x > mouth.x + 65.0
                    and corner.y > mouth.y - 65.0):
                outlet = corner
                break
            continue
        for neighbor in corner.adjacent:
            if neighbor in main_set and neighbor is not fork:
                continue
            if neighbor.x < fork.x - 15.0 or neighbor.y < fork.y - 25.0:
                continue
            edge = next((edge for edge in corner.protrudes
                         if edge.v0 is neighbor or edge.v1 is neighbor), None)
            if edge is None or edge.river or (neighbor.river and neighbor is not fork):
                continue
            step = hypot(neighbor.x - corner.x, neighbor.y - corner.y)
            new_cost = cost + step + max(0.0, neighbor.elevation - corner.elevation) * 80.0
            if new_cost < distances.get(neighbor, float("inf")) and new_cost < 300.0:
                distances[neighbor] = new_cost
                previous[neighbor] = (corner, edge)
                heappush(queue, (new_cost, neighbor.index, neighbor))
    if outlet is None:
        raise ValueError("Egypt's river needs a second coastal outlet for its delta.")

    branch = [outlet]
    while branch[-1] is not fork:
        parent, edge = previous[branch[-1]]
        edge.river = max(edge.river, 1)
        branch[-1].river = max(branch[-1].river, 1)
        branch.append(parent)
    branch.reverse()
    gen.river_paths.append([(corner.x, corner.y, corner.elevation,
                             float(corner.river), 1.0 if corner is outlet else 0.0)
                            for corner in branch])
    gen.scenario_nile_outlets = (mouth, outlet)


def choose_egypt_geography(tiles, gen) -> dict[str, str]:
    """Claim a connected Nile corridor with Cairo inland and the Delta at the mouth."""
    mainstem = gen.scenario_nile_mainstem
    path_coords = [(point[0], point[1]) for point in mainstem]
    edge_positions = {}
    for index, (start, end) in enumerate(zip(path_coords, path_coords[1:])):
        edge_positions[frozenset((start, end))] = index
    river_positions = {}
    for tile in tiles:
        if tile.is_ocean:
            continue
        positions = [edge_positions[frozenset(((edge.v0.x, edge.v0.y),
                                               (edge.v1.x, edge.v1.y)))]
                     for edge in tile.borders
                     if edge.river and edge.v0 and edge.v1
                     and frozenset(((edge.v0.x, edge.v0.y),
                                    (edge.v1.x, edge.v1.y))) in edge_positions]
        if positions:
            river_positions[tile.name] = min(positions)

    mouth, outlet = gen.scenario_nile_outlets
    middle_x = (mouth.x + outlet.x) / 2.0
    delta_candidates = [tile for tile in tiles if tile.is_coast
                        and tile.name in river_positions]
    delta_candidates.sort(key=lambda tile: (abs(tile.centroid[0] - middle_x),
                                            abs(tile.centroid[1] - mouth.y), tile.name))
    for delta in delta_candidates:
        alex_candidates = [neighbor for neighbor in delta.adjacent_tiles.values()
                           if neighbor.is_coast and not neighbor.is_ocean
                           and neighbor.centroid[0] < delta.centroid[0]]
        if not alex_candidates:
            continue
        alexandria = min(alex_candidates,
                         key=lambda tile: (abs(tile.centroid[0] - mouth.x), tile.name))

        def upstream_chains(current, depth):
            if depth == 0:
                yield ()
                return
            neighbors = [tile for tile in current.adjacent_tiles.values()
                         if not tile.is_ocean and not tile.is_coast
                         and tile.name in river_positions
                         and river_positions[tile.name] < river_positions[current.name]
                         and tile.centroid[1] < current.centroid[1]]
            for neighbor in sorted(neighbors, key=lambda tile: tile.name):
                for tail in upstream_chains(neighbor, depth - 1):
                    yield (neighbor,) + tail

        chains = list(upstream_chains(delta, 3))
        if not chains:
            continue
        chain = max(chains, key=lambda part: (
            -part[-1].centroid[1],
            -sum(abs(tile.centroid[0] - delta.centroid[0]) for tile in part),
            tuple(tile.name for tile in part)))
        near, cairo, upper = chain
        return {cairo.name: "Cairo", delta.name: "Nile Delta",
                upper.name: "Upper Egypt", alexandria.name: "Alexandria",
                near.name: "Nile Valley"}
    raise ValueError("Egypt's generated coast has no connected Nile corridor.")


def prepare_world(world: dict) -> dict:
    """Attach scenario identity and opening state to a generated deterministic map."""
    egypt = next((nation for nation in world.get("nations", []) if nation.name == "Egypt"), None)
    if egypt is None:
        raise ValueError("Egypt 1877 setup requires the Egypt starting nation.")

    egypt.display_name = SCENARIO["polity"]
    egypt.regime_type = "autocracy"
    # The scenario starts with enough political authority to make non-coercive
    # outcomes possible across the otherwise volatile shared simulation.
    egypt.legitimacy = 1.0
    egypt.government.regime_type = "autocracy"
    world["player_nation_name"] = egypt.name
    world["selected_nation"] = egypt
    world["scenario_id"] = SCENARIO_ID
    world["scenario"] = deepcopy(SCENARIO)
    from scenario_situation import situation_template
    debt_rules = situation_template()['debt_rules']
    world["scenario_state"] = {
        "turns_remaining": SCENARIO["horizon_turns"],
        "public_maize_stock_units": SCENARIO["relief_stock_turns"] * 30,
        "relief_units_per_turn": 30,
        "scheduled_remittance": float(debt_rules['initial_payment']),
        "payment_window_turn": int(debt_rules['first_due_turn']),
        "payment_status": "upcoming",
        "deferral_count": 0,
        "creditor_levy_per_turn": 0.0,
        "creditor_levy_remaining": 0.0,
        "naval_crisis": {"stage": "none"},
        "naval_news": [],
        "creditor_reactions": [],
        "creditor_news": [],
        "creditor_confidence": 0.6,
        "fiscal_autonomy": 1.0,
        "extraction_level": 0,
        "tax_relief_enacted": False,
        "tax_decision_taken": False,
        "domestic_grain_priority": False,
        "ending": None,
        "actions_taken": [],
        "events_fired": ["low_nile"],
    }
    from scenario_debt import initialize as initialize_debt
    initialize_debt(world)
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
    world["turn"] = 1
    world["playing"] = False
    world["guided_analysis_open"] = False
    from scenario_status import initialize
    initialize(world)
    from scenario_situation import update_foreign_reports
    update_foreign_reports(world)
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

    from scenario_status import initialize, snapshot, record_change
    if 'scenario_status_history' not in world:
        initialize(world)
    status_before = snapshot(world)

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
    elif action_id == 'reinforce_alexandria':
        from scenario_gunboat import reinforce_batteries
        ok, message = reinforce_batteries(world)
        if not ok:
            return False, message
    elif action_id in ("pay_remittance", "defer_remittance", "concede_revenue", "default_remittance"):
        from scenario_situation import situation_template
        debt_rules = situation_template()['debt_rules']
        deferral_delay = int(debt_rules['deferral_delay_turns'])
        if turn < int(state.get("payment_window_turn", 6)):
            return False, "The debt-service window has not opened yet."
        if state.get("payment_status") not in ("upcoming", "unpaid"):
            return False, "The debt-service decision has already been resolved."
        if action_id == "defer_remittance" and int(state.get("deferral_count", 0)) >= int(debt_rules['maximum_deferrals']):
            return False, "The Caisse will not grant another deferral. Pay, concede, or default."
        if action_id == "defer_remittance" and turn + deferral_delay > int(SCENARIO['horizon_turns']):
            return False, "The revised due date would fall after the campaign ends. Pay, concede, or default."
        amount = float(state.get("scheduled_remittance", 200.0))
        if action_id == "default_remittance":
            state["payment_status"] = "defaulted"
            state["creditor_confidence"] = 0.0
            nation.legitimacy = max(0.0, float(getattr(nation, "legitimacy", 0.5)) - 0.15)
            from scenario_debt import default as default_debt
            default_debt(world)
            message = "Defaulted on the remittance: creditor confidence collapsed and government legitimacy fell."
        elif action_id in ("pay_remittance", "concede_revenue"):
            amount = amount if action_id == "pay_remittance" else amount * 0.5
            if nation.government.agent.cash < amount:
                return False, f"The treasury needs {amount:,.0f} treasury units to make this payment."
            from scenario_debt import pay as pay_debt
            ok, reason = pay_debt(world, amount, kind='payment' if action_id == 'pay_remittance' else 'concession_payment',
                                  forgive_remainder=action_id == 'concede_revenue')
            if not ok:
                return False, reason
            state["payment_status"] = "paid" if action_id == "pay_remittance" else "restructured"
            state["creditor_levy_per_turn"] = 0.0
            state["creditor_levy_remaining"] = 0.0
            state["creditor_confidence"] = min(1.0, state.get("creditor_confidence", 0.6) + 0.15)
            if action_id == "concede_revenue":
                state["fiscal_autonomy"] = max(0.0, state.get("fiscal_autonomy", 1.0) - 0.25)
                message = f"Accepted a reduced {amount:,.0f}-unit remittance and creditor oversight of future revenues."
            else:
                message = f"Paid the {amount:,.0f}-unit scheduled debt-service remittance."
            if state.get('naval_crisis', {}).get('stage') in ('mobilizing', 'ultimatum', 'blockaded'):
                from scenario_gunboat import withdraw
                withdraw(world, 'Debt service is settled; the British squadron withdraws from Alexandria.')
        elif action_id == "defer_remittance":
            state["payment_status"] = "deferred"
            state["deferral_count"] = int(state.get("deferral_count", 0)) + 1
            state["payment_window_turn"] = turn + deferral_delay
            from scenario_debt import revise as revise_debt
            revise_debt(world, round(amount * float(debt_rules['deferral_multiplier']), 2),
                        due_turn=state['payment_window_turn'])
            state["creditor_confidence"] = max(0.0, state.get("creditor_confidence", 0.6) - 0.30)
            nation.legitimacy = min(1.0, float(getattr(nation, "legitimacy", 0.5)) + 0.02)
            message = (f"Deferred the remittance to turn {state['payment_window_turn']}; "
                       f"{state['scheduled_remittance']:,.0f} units will be due after the surcharge.")
        else:
            return False, "Unknown debt-service decision."
    else:
        return False, "Unknown scenario decision."

    state["last_action_turn"] = turn
    state.setdefault("actions_taken", []).append({"turn": turn, "action": action_id, "message": message})
    world["scenario_feedback"] = message
    from client.desktop.engine import ticker_push
    ticker_push(world, turn, "SCENARIO", message, (120, 220, 170))
    from scenario_situation import queue_creditor_reaction
    queue_creditor_reaction(world, action_id)
    record_change(world, action_id, status_before, snapshot(world))
    return True, message


def advance_scenario(world: dict, turn: int, ticker_push, on_phase=None) -> None:
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
    from scenario_situation import collect_creditor_levy, update_foreign_reports, advance_creditor_reactions
    levy_paid = collect_creditor_levy(world)
    if levy_paid:
        ticker_push(world, turn, "CREDITOR", f"The Caisse collected {levy_paid:,.0f} units from Egyptian receipts.", (225, 178, 87))
    if on_phase:
        on_phase('levy')
    if turn >= int(state.get("payment_window_turn", 6)) and state.get("payment_status") in ("upcoming", "deferred"):
        state["payment_status"] = "unpaid"
        world["playing"] = False
        world["scenario_warning_modal"] = {"kind": "debt_due"}
        state["events_fired"].append(f"debt_service_window_{turn}")
        world["scenario_feedback"] = f"Debt service of {state['scheduled_remittance']:,.0f} units is due now."
        ticker_push(world, turn, "ALERT", "Debt service is due. Choose payment, concession, deferral if available, or default.", (240, 180, 72))
    elif turn > int(state.get("payment_window_turn", 6)) and state.get("payment_status") == "unpaid":
        state["payment_status"] = "defaulted"
        state["creditor_confidence"] = 0.0
        nation.legitimacy = max(0.0, float(getattr(nation, "legitimacy", 0.5)) - 0.15)
        from scenario_debt import default as default_debt
        default_debt(world)
        ticker_push(world, turn, "ALERT", "The government missed the debt-service window; default deepens the crisis.", (240, 90, 82))
    if on_phase:
        on_phase('deadline')

    # The general simulation updates faction protest energy; this scenario
    # translates that live pressure into its 0..1 political unrest measure.
    for tile in nation.tiles:
        history = getattr(tile, "protest_energy_log", [])
        pressure = min(1.0, max(0.0, float(history[-1]) / 10.0)) if history else 0.0
        current = float(getattr(tile, "unrest_level", 0.0))
        tile.unrest_level = max(0.0, min(1.0, current * 0.75 + pressure * 0.25))
    if on_phase:
        on_phase('protest_pressure')
    update_foreign_reports(world)

    metrics = _outcome_metrics(nation)
    thresholds = SCENARIO["thresholds"]
    ended = (metrics["legitimacy"] <= thresholds["breakdown_legitimacy"]
             or metrics["unrest"] >= thresholds["breakdown_unrest"])
    if ended:
        world["playing"] = False
        world["scenario_warning_modal"] = {
            "kind": "breakdown",
            "legitimacy": metrics["legitimacy"],
            "unrest": metrics["unrest"],
        }
        return
    advance_creditor_reactions(world, turn, ticker_push)
    if on_phase:
        on_phase('creditor_reaction')
    if world.get("scenario_warning_modal"):
        return
    from scenario_gunboat import advance_naval_crisis
    advance_naval_crisis(world)
    if on_phase:
        on_phase('naval_crisis')
    if world.get("scenario_warning_modal"):
        return
    finish_due_campaign(world)


def finish_due_campaign(world: dict) -> None:
    """Complete turn 20 after any debt or creditor modal has been answered."""
    state = world.get('scenario_state', {})
    turn = int(world.get('turn', 0))
    if (turn < int(SCENARIO['horizon_turns']) or state.get('ending')
            or world.get('scenario_warning_modal')):
        return
    nation = next((n for n in world.get('nations', [])
                   if n.name == world.get('player_nation_name')), None)
    if nation is None:
        return
    metrics = _outcome_metrics(nation)
    thresholds = SCENARIO['thresholds']
    if metrics['legitimacy'] <= thresholds['breakdown_legitimacy'] or metrics['unrest'] >= thresholds['breakdown_unrest']:
        outcome = 'breakdown'
    elif state.get('extraction_level', 0) > 0:
        outcome = 'coercive_extraction'
    elif metrics['hunger_rate'] <= thresholds['protected_hunger_rate'] and state.get('payment_status') == 'paid':
        outcome = 'relief_and_payment'
    elif metrics['hunger_rate'] <= thresholds['protected_hunger_rate'] and state.get('payment_status') == 'restructured':
        outcome = 'creditor_settlement'
    else:
        outcome = 'breakdown'
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
    debt_detail = (f"Debt service {state.get('payment_status', 'unresolved')}; "
                   f"creditor confidence {state.get('creditor_confidence', 0.0):.0%}; "
                   f"fiscal autonomy {state.get('fiscal_autonomy', 1.0):.0%}.")
    if state.get('payment_status') in ('deferred', 'unpaid'):
        debt_detail += (f" Next due: turn {state.get('payment_window_turn', '?')}, "
                        f"{state.get('scheduled_remittance', 0):,.0f} units.")
    if float(state.get('creditor_levy_per_turn', 0.0)) > 0:
        debt_detail += (f" Caisse levy: up to {state['creditor_levy_per_turn']:,.0f} units per turn, "
                        f"{state.get('creditor_levy_remaining', 0.0):,.0f} remaining.")
    naval_stage = state.get('naval_crisis', {}).get('stage', 'none')
    if naval_stage not in ('none',):
        debt_detail += f' Naval crisis: {naval_stage}.'
    return {
        "outcome": outcome,
        "title": title,
        "summary": summary,
        "food": f"{metrics.get('hungry', 0)} of {metrics.get('households', 0)} households hungry ({metrics.get('hunger_rate', 0.0):.0%}).",
        "debt": debt_detail,
        "politics": f"Government legitimacy {metrics.get('legitimacy', 0.0):.0%}; average unrest {metrics.get('unrest', 0.0):.2f}.",
        "actions": actions,
        "creditor_reactions": [entry['headline'] for entry in state.get('creditor_news', [])],
        "naval_events": [entry['text'] for entry in state.get('naval_news', [])],
    }


def _assign_location_roles(nation) -> dict[str, str]:
    """Assign stable display roles to this generated Egypt cluster's regions."""
    tiles = list(getattr(nation, "tiles", []))
    if not tiles:
        return {}

    authored = {tile.name: tile.scenario_location for tile in tiles
                if getattr(tile, "scenario_location", None)}
    if authored:
        if set(authored.values()) != {"Cairo", "Alexandria", "Nile Delta",
                                      "Upper Egypt", "Nile Valley"}:
            raise ValueError("Egypt's generated locations are incomplete.")
        for tile in tiles:
            tile.display_name = authored[tile.name]
        return authored

    def north_south_key(tile):
        if hasattr(tile, "centroid"):
            # The Voronoi camera projects increasing world y toward the top
            # of the screen.
            return (-float(tile.centroid[1]), tile.name)
        return (float(getattr(tile, "grid_r", 0)), tile.name)

    ordered = sorted(tiles, key=north_south_key)
    capital = getattr(nation, "capital", None) or ordered[len(ordered) // 2]
    aliases = {capital.name: "Cairo"}
    remaining = [tile for tile in ordered if tile is not capital]

    coastal = [tile for tile in remaining if getattr(tile, "is_coast", False)]
    named_alexandria = next((tile for tile in remaining
                             if getattr(tile, "display_name", "") == "Alexandria"), None)
    alexandria = coastal[0] if coastal else (named_alexandria or (remaining[0] if remaining else None))
    if alexandria is not None:
        aliases[alexandria.name] = "Alexandria"
        remaining.remove(alexandria)
    if named_alexandria is not None and named_alexandria is not alexandria:
        # Generic nation naming may have placed Alexandria inland. Keep one
        # Alexandria label at the campaign's coastal export connection.
        used_names = {getattr(tile, "display_name", "") for tile in tiles}
        named_alexandria.display_name = next(
            (name for name in ("Damanhur", "Rosetta", "Bulaq District") if name not in used_names),
            f"Egyptian district {named_alexandria.name}",
        )

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
