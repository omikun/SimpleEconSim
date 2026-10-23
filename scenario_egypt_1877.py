"""Authored setup and player-facing content for Egypt's 1877 crisis scenario."""

from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change

from contextlib import contextmanager
from copy import deepcopy
from heapq import heappop, heappush
from math import exp, hypot
import random
from goods import Goods
from nutrition import deficit_fraction


SCENARIO_ID = "egypt_1877"
SCENARIO = {
    "id": SCENARIO_ID,
    "title": "Egypt's Grain and Debt Crisis",
    "year": 1877,
    "polity": "Khedivate of Egypt",
    "ruler": "Khedive Ismail Pasha",
    "capital": "Cairo",
    "locations": ("Cairo", "Nile Delta", "Upper Egypt", "Alexandria",
                  "Port Said", "Ismailia", "Tel el Kebir"),
    "institutions": ("Caisse de la Dette Publique",),
    "briefing": (
        "A weak Nile flood has left poorer households short of maize. Cairo's "
        "relief stores and treasury are limited, while landowners hold private "
        "grain and three debt-service windows remain. Cultivators face tax "
        "arrears, and workers can organize. Choose whose claims to protect.",
    ),
    "horizon_turns": 20,
    "chapter_two_min_turns": 8,
    "occupation_min_turns": 5,
    "relief_stock_turns": 1,
    "relief_households_per_release": 110,
    "payment_window_turn": 6,
    "thresholds": {"protected_hunger_rate": 0.20, "breakdown_legitimacy": 0.10, "breakdown_unrest": 0.85},
    "pressures": (
        {"id": "food_access", "title": "Household maize access"},
        {"id": "debt_service", "title": "Next debt-service window"},
        {"id": "political_support", "title": "Political support"},
    ),
    "opening_events": (
        {"turn": 1, "id": "low_nile", "kind": "harvest_shock", "severity": 0.65},
        {"turn": 6, "id": "debt_service_window", "kind": "payment_due"},
    ),
    "outcomes": (
        {"id": "relief_and_payment", "food_access": "protected", "debt": "paid"},
        {"id": "creditor_settlement", "food_access": "protected", "debt": "restructured"},
        {"id": "sovereign_compromise", "debt": "mediated", "government_control": "Egyptian"},
        {"id": "imposed_financial_control", "revenue_control": "Caisse assignment"},
        {"id": "successful_repudiation", "debt": "defaulted", "territory": "Egyptian"},
        {"id": "stalled_intervention", "territory": "contested"},
        {"id": "nationalist_victory", "territory": "Egyptian", "government_control": "nationalist"},
        {"id": "occupation", "government_control": "British"},
        {"id": "coercive_extraction", "tax_policy": "high extraction", "political_cost": "high"},
        {"id": "breakdown", "government_control": "lost"},
        {"id": "fiscal_hardship", "food_access": "poor", "debt": "resolved"},
        {"id": "coerced_disarmament", "military_concession": "disarmed", "debt": "unresolved"},
        {"id": "unresolved_crisis", "debt": "unresolved", "government_control": "Egyptian"},
        {"id": "joint_financial_control", "revenue_control": "joint Caisse assignment"},
        {"id": "french_brokered_settlement", "debt": "French mediated", "government_control": "Egyptian"},
    ),
    # Fixed map seeds make this authored campaign reproducible without affecting
    # ordinary sandbox generation. CLI seed flags remain available for tuning.
    "seeds": {"world": 1877, "terrain": 1877, "nations": 1877},
    "terrain": {"shape": "radial", "points": 1000, "rivers": 25, "wave_intensity": 1.0},
    "foreign_grievance_scale": 0.20,
    "camera": {"zoom": 2.0},
    "actions": (
        {"id": "release_maize", "title": "Release maize reserves", "turn_cost": 1},
        {"id": "repair_delta_channels", "title": "Repair Delta Nile channels", "turn_cost": 1},
        {"id": "repair_upper_channels", "title": "Repair Upper Egypt channels", "turn_cost": 1},
        {"id": "build_revenue_office", "title": "Staff Alexandria revenue office", "turn_cost": 1},
        {"id": "prepare_canal_line", "title": "Prepare Tel el Kebir defenses", "turn_cost": 1},
        {"id": "repair_canal_line", "title": "Repair Tel el Kebir works", "turn_cost": 1},
        {"id": "publish_revenue_accounts", "title": "Publish Alexandria accounts", "turn_cost": 1},
        {"id": "refuse_revenue_inspection", "title": "Refuse Caisse inspection", "turn_cost": 1},
        {"id": "prioritize_domestic_grain", "title": "Keep more grain in Egypt", "turn_cost": 1},
        {"id": "enact_grain_entitlement", "title": "Levy private surplus for relief", "turn_cost": 1},
        {"id": "end_grain_entitlement", "title": "End the private grain levy", "turn_cost": 1},
        {"id": "recall_district_reserves", "title": "Call district reserves to Cairo", "turn_cost": 1},
        {"id": "reduce_fellahin_tax", "title": "Reduce cultivator taxes", "turn_cost": 1},
        {"id": "raise_local_taxes", "title": "Raise local taxes", "turn_cost": 1},
        {"id": "intensify_requisitions", "title": "Enforce emergency requisitions", "turn_cost": 1},
        {"id": "district_relief", "title": "Feed a selected district", "turn_cost": 1},
        {"id": "district_tax_relief", "title": "Suspend selected district taxes", "turn_cost": 1},
        {"id": "district_negotiate", "title": "Negotiate in a selected district", "turn_cost": 1},
        {"id": "district_repress", "title": "Disperse a selected district protest", "turn_cost": 1},
        {"id": "buy_private_grain", "title": "Buy privately held maize", "turn_cost": 1},
        {"id": "requisition_private_grain", "title": "Requisition privately held maize", "turn_cost": 1},
        {"id": "open_private_grain_market", "title": "Leave grain to private markets", "turn_cost": 1},
        {"id": "district_arrears_relief", "title": "Forgive district tax arrears", "turn_cost": 1},
        {"id": "district_support_mutual_aid", "title": "Support local mutual aid", "turn_cost": 1},
        {"id": "district_bargain_workers", "title": "Bargain with local workers", "turn_cost": 1},
        {"id": "district_break_strike", "title": "Break a local strike", "turn_cost": 1},
        {"id": "extend_collection_term", "title": "Trade a lower levy for longer inspection", "turn_cost": 1},
        {"id": "pay_remittance", "title": "Pay debt service", "turn_cost": 1},
        {"id": "defer_remittance", "title": "Defer debt service", "turn_cost": 1},
        {"id": "concede_revenue", "title": "Concede revenue oversight", "turn_cost": 1},
        {"id": "default_remittance", "title": "Default on debt service", "turn_cost": 1},
        {"id": "reinforce_alexandria", "title": "Prepare Alexandria's defenses", "turn_cost": 1},
        {"id": "pay_army_arrears", "title": "Pay officer arrears", "turn_cost": 1},
        {"id": "promote_egyptian_officers", "title": "Promote Egyptian officers", "turn_cost": 1},
        {"id": "invite_representative_cabinet", "title": "Invite representative cabinet", "turn_cost": 1},
        {"id": "dismiss_foreign_controllers", "title": "Dismiss foreign controllers", "turn_cost": 1},
        {"id": "close_canal", "title": "Close canal to foreign transit", "turn_cost": 1},
        {"id": "comply_oversight", "title": "Fund Caisse inspection", "turn_cost": 1},
        {"id": "seek_narrower_oversight", "title": "Seek narrower inspection", "turn_cost": 1},
        {"id": "revoke_oversight", "title": "Revoke Caisse oversight", "turn_cost": 1},
        {"id": "request_french_mediation", "title": "Request French mediation", "turn_cost": 1},
        {"id": "offer_joint_guarantee", "title": "Offer joint creditor guarantee", "turn_cost": 1},
        {"id": "seek_french_opposition", "title": "Seek French opposition", "turn_cost": 1},
        {"id": "organize_boycott", "title": "Organize customs boycott", "turn_cost": 1},
        {"id": "call_general_strike", "title": "Call general strike", "turn_cost": 1},
        {"id": "coordinate_insurgency", "title": "Coordinate resistance", "turn_cost": 1},
        {"id": "collaborate_with_occupation", "title": "Collaborate with occupation", "turn_cost": 1},
        {"id": "negotiate_withdrawal", "title": "Negotiate withdrawal", "turn_cost": 1},
    ),
}


def is_scenario_id(value: str | None) -> bool:
    return value == SCENARIO_ID


def campaign_horizon(world: dict) -> int:
    return int(world.get('scenario', SCENARIO).get('horizon_turns', SCENARIO['horizon_turns']))


def ensure_campaign_horizon(world: dict, final_turn: int) -> int:
    """Allow a late sovereignty crisis to play out before the debrief."""
    old = campaign_horizon(world)
    final_turn = max(old, int(final_turn))
    if final_turn == old:
        return old
    world['scenario']['horizon_turns'] = final_turn
    state = world['scenario_state']
    state['campaign_horizon_turn'] = final_turn
    state['turns_remaining'] = max(0, final_turn - int(world['turn']))
    from scenario_debt import bonds
    for bond in bonds(world):
        if bond.status in ('active', 'defaulted'):
            bond.maturity_turn = max(bond.maturity_turn, final_turn + 1)
    agreement = state.get('oversight_agreement') or {}
    if agreement.get('status') == 'active':
        agreement['expires_turn'] = max(int(agreement.get('expires_turn', 0)), final_turn)
    return final_turn


def enter_chapter_two(world: dict, cause: str) -> bool:
    """Pause once when the political or foreign crisis becomes the main task."""
    state = world['scenario_state']
    if int(state.get('chapter', 1)) >= 2:
        return False
    turn = int(world['turn'])
    state['chapter'] = 2
    state['chapter_two_start_turn'] = turn
    state['chapter_two_cause'] = cause
    minimum = int(world['scenario'].get('chapter_two_min_turns', 8))
    ensure_campaign_horizon(world, turn + minimum - 1)
    world['scenario_bookend_modal'] = 'chapter2'
    world['scenario_bookend_scroll'] = 0
    world['guided_action_scroll'] = 0
    world['playing'] = False
    return True


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

    def find_branch(*, allow_existing_river, preferred_coast=True):
        queue = [(0.0, fork.index, fork)]
        distances = {fork: 0.0}
        previous = {}
        while queue:
            cost, _, corner = heappop(queue)
            if cost != distances[corner]:
                continue
            if corner.ocean:
                separation = hypot(corner.x - mouth.x, corner.y - mouth.y)
                preferred = (65.0 <= separation <= 145.0 and corner.x > mouth.x + 65.0
                             and corner.y > mouth.y - 65.0)
                alternate = (65.0 <= separation <= 220.0
                             and corner.y > mouth.y - 120.0)
                eligible = preferred if preferred_coast else alternate
                if eligible:
                    return corner, previous
                continue
            for neighbor in corner.adjacent:
                if neighbor in main_set and neighbor is not fork:
                    continue
                if preferred_coast and (neighbor.x < fork.x - 15.0 or neighbor.y < fork.y - 25.0):
                    continue
                edge = next((edge for edge in corner.protrudes
                             if edge.v0 is neighbor or edge.v1 is neighbor), None)
                if edge is None:
                    continue
                if (not allow_existing_river
                        and (edge.river or (neighbor.river and neighbor is not fork))):
                    continue
                step = hypot(neighbor.x - corner.x, neighbor.y - corner.y)
                new_cost = (cost + step
                            + max(0.0, neighbor.elevation - corner.elevation) * 80.0)
                if (new_cost < distances.get(neighbor, float("inf"))
                        and new_cost < (300.0 if preferred_coast else 450.0)):
                    distances[neighbor] = new_cost
                    previous[neighbor] = (corner, edge)
                    heappush(queue, (new_cost, neighbor.index, neighbor))
        return None, {}

    outlet, previous = find_branch(allow_existing_river=False)
    used_existing_river = False
    if outlet is None:
        # On some radial maps the intended fork is surrounded by channels from
        # other generated rivers. Reuse the cheapest connected side channel to
        # reach the second coast instead of rejecting the entire campaign map.
        outlet, previous = find_branch(allow_existing_river=True)
        used_existing_river = outlet is not None
    if outlet is None:
        # A north-eastern main mouth can have no further eastern coast in the
        # preferred narrow band. Use a nearby northern outlet on either side,
        # retaining the same fork and a continuous, bounded side channel.
        outlet, previous = find_branch(allow_existing_river=True, preferred_coast=False)
        used_existing_river = outlet is not None
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
    gen.scenario_nile_branch_reused_river = used_existing_river


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
        "campaign_horizon_turn": SCENARIO["horizon_turns"],
        "chapter": 1,
        "public_maize_stock_units": (SCENARIO["relief_stock_turns"]
                                     * SCENARIO["relief_households_per_release"] * 4),
        "relief_units_per_turn": SCENARIO["relief_households_per_release"],
        "scheduled_remittance": float(debt_rules['initial_payment']),
        "service_periods_paid": 0,
        "service_concession_used": False,
        "payment_window_turn": int(debt_rules['first_due_turn']),
        "payment_status": "upcoming",
        "deferral_count": 0,
        "creditor_levy_per_turn": 0.0,
        "creditor_levy_remaining": 0.0,
        "settlement_path": None,
        "oversight_agreement": None,
        "disarmed_batteries": False,
        "naval_withdrawal_cause": None,
        "naval_crisis": {"stage": "none"},
        "naval_news": [],
        "creditor_reactions": [],
        "creditor_news": [],
        "creditor_confidence": 0.6,
        "fiscal_autonomy": 1.0,
        "extraction_level": 0,
        "tax_relief_enacted": False,
        "domestic_grain_priority": False,
        "ending": None,
        "actions_taken": [],
        "events_fired": ["low_nile"],
    }
    from scenario_debt import initialize as initialize_debt
    initialize_debt(world)
    egypt.government.food_inventory = world["scenario_state"]["public_maize_stock_units"]
    # The sovereign can spend only its own cash. Move the generated surplus to
    # private Egyptian holders so the opening debt decision requires receipts
    # or a concession without creating or destroying currency.
    households = [agent for tile in egypt.tiles for agent in getattr(tile, 'agents', [])
                  if getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False)
                  and not getattr(agent, 'is_corporation', False) and not getattr(agent, 'is_trader', False)]
    households.sort(key=lambda agent: (float(agent.cash), agent.id))
    treasury = egypt.government.agent
    transfer = max(0.0, float(treasury.cash) - 235.0)
    _public_write = begin_public_change(None, treasury)
    treasury.cash -= transfer
    finish_public_change(_public_write, 'scenario_egypt_1877:prepare_world',
                         inputs={'source_writer': 'scenario_egypt_1877.py:prepare_world:b0b528072f9a528f:1', 'semantic_operation_id': locals().get('operation_id')})
    affluent = households[-max(1, len(households) // 5):]
    for agent in affluent:
        _public_write = begin_public_change(None, agent)
        agent.cash += transfer / len(affluent)
        finish_public_change(_public_write, 'scenario_egypt_1877:prepare_world',
                             inputs={'source_writer': 'scenario_egypt_1877.py:prepare_world:bc94b0016c4764ba:1', 'semantic_operation_id': locals().get('operation_id')})
        agent.energy_reserve_kcal = 60000.0
    # Food remains in private stores, but poorer households have little access.
    vulnerable = households[:len(households) // 4]
    for index, agent in enumerate(vulnerable):
        food = agent.inv_get(Goods.food)
        agent.inv_set(Goods.food, 0)
        affluent[index % len(affluent)].inv_add(Goods.food, food)
        agent.hungry_steps = 1
        agent.calorie_deficit_kcal = agent.calorie_need_kcal
        agent.energy_reserve_kcal = 20000.0
        purchasing_power = agent.cash * .95
        _public_write = begin_public_change(None, agent)
        agent.cash -= purchasing_power
        finish_public_change(_public_write, 'scenario_egypt_1877:prepare_world',
                             inputs={'source_writer': 'scenario_egypt_1877.py:prepare_world:02a7e18445e1abc4:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, affluent[index % len(affluent)])
        affluent[index % len(affluent)].cash += purchasing_power
        finish_public_change(_public_write, 'scenario_egypt_1877:prepare_world',
                             inputs={'source_writer': 'scenario_egypt_1877.py:prepare_world:b647a0853006fbb0:1', 'semantic_operation_id': locals().get('operation_id')})
    world["scenario_feedback"] = "Opening crisis: low Nile, threatened maize harvest, and debt service."
    world["scenario_location_by_tile"] = _assign_location_roles(egypt)
    from scenario_political_economy import initialize as initialize_political_economy
    initialize_political_economy(world, egypt)
    from scenario_geography import initialize as initialize_geography
    initialize_geography(world)
    from scenario_projects import initialize as initialize_projects
    initialize_projects(world)
    from scenario_politics import initialize as initialize_politics
    initialize_politics(world)
    from scenario_campaign import initialize as initialize_campaign
    initialize_campaign(world)
    from scenario_occupation import initialize as initialize_occupation
    initialize_occupation(world)
    from scenario_diplomacy import initialize as initialize_diplomacy
    initialize_diplomacy(world)
    from scenario_history import initialize as initialize_history
    initialize_history(world)
    for tile in egypt.tiles:
        tile.scenario_food_yield_modifier = (0.35 if getattr(tile, "scenario_location", "")
                                             in ("Nile Delta", "Upper Egypt") else 0.55)
        tile.scenario_food_yield_modifier_until = 12
        tile.scenario_grievance_scale = 0.4
    # The authored foreign governments have broader administrative capacity
    # than the five Egyptian crisis districts. Their simulated protests remain
    # real and visible, but should not max out before the first creditor reply.
    for nation in world['nations']:
        if nation.name in ('Britain', 'France'):
            for tile in nation.tiles:
                tile.scenario_grievance_scale = SCENARIO['foreign_grievance_scale']
    capital = getattr(egypt, "capital", None)
    if capital is not None:
        world["selected_region"] = capital
        capital.display_name = "Cairo"
    world["turn"] = 1
    world["playing"] = False
    world["guided_analysis_open"] = False
    world["scenario_bookend_modal"] = "briefing"
    from scenario_status import initialize
    initialize(world)
    from scenario_situation import update_foreign_reports
    update_foreign_reports(world)
    return world


def _trace_national_maize_ration(tile, *, operation_id, turn, nation,
                                  recipient, units, stock_before,
                                  stock_after, queue_before, queue_after):
    from run_trace import emit

    contract = {
        'contract_version': 'goods_transfer.v1',
        'operation_id': operation_id,
        'operation_type': 'national_maize_release_ration',
        'good': Goods.food.name,
        'unit': 'food_units',
        'amount': int(units),
        'payer_account': {
            'type': 'government_food_inventory',
            'id': str(nation.government.name), 'good': Goods.food.name,
            'balance_before': int(stock_before),
            'balance_after': int(stock_after),
            'balance_scope': 'food_inventory',
        },
        'payee_account': {
            'type': 'agent_emergency_ration_queue', 'id': str(recipient.id),
            'good': Goods.food.name, 'balance_before': int(queue_before),
            'balance_after': int(queue_after),
            'balance_scope': 'next_meal_entitlement',
        },
        'delivery_status': 'queued_for_next_consumption_step',
        'counterparty_leg_status': 'public_stock_and_household_entitlement_captured',
    }
    return emit(
        tile, kind='national_maize_ration_transfer', record_class='transfer',
        phase='scenario_action',
        subject={'type': 'tile', 'id': tile.name, 'agent_id': recipient.id,
                 'good': Goods.food.name},
        metric_id='goods.national_relief_ration', unit='food_units',
        before=0, after=int(units),
        inputs={'operation_id': operation_id, 'turn': int(turn),
                'recipient_id': recipient.id, 'transfer_contract': contract})


def _trace_national_maize_release(world, nation, *, operation_id, turn,
                                   outcome, stock_before, stock_after,
                                   ration_limit, underfed_count,
                                   recipient_ids=(), cause_event_ids=None):
    from run_trace import emit

    region = (getattr(nation, 'capital', None)
              or next(iter(getattr(nation, 'tiles', ())), None))
    return emit(
        region, kind='national_maize_release_resolved',
        record_class='outcome', phase='scenario_action',
        subject={'type': 'nation', 'id': nation.name},
        metric_id='scenario.national_maize_release', unit='households',
        before=0, after=len(recipient_ids),
        formula_id='scenario.national_maize_release_allocation.v1',
        inputs={'operation_id': operation_id, 'action_id': 'release_maize',
                'turn': int(turn), 'outcome': outcome,
                'public_food_inventory_before': int(stock_before),
                'public_food_inventory_after': int(stock_after),
                'food_units_per_household': 4,
                'ration_limit': int(ration_limit),
                'underfed_household_count': int(underfed_count),
                'recipient_ids': [str(agent_id) for agent_id in recipient_ids]},
        cause_event_ids=cause_event_ids)


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

    from scenario_district import DISTRICT_ACTIONS
    from scenario_political_economy import NATIONAL_ACTIONS, DISTRICT_ACTIONS as ECONOMY_DISTRICT_ACTIONS
    if action_id in ('enact_grain_entitlement', 'end_grain_entitlement'):
        from scenario_projects import set_grain_entitlement
        ok, message = set_grain_entitlement(world, action_id == 'enact_grain_entitlement')
        if not ok:
            return False, message
    elif action_id == 'recall_district_reserves':
        from scenario_projects import recall_district_reserves
        ok, message = recall_district_reserves(world)
        if not ok:
            return False, message
    elif action_id in NATIONAL_ACTIONS or action_id in ECONOMY_DISTRICT_ACTIONS:
        from scenario_political_economy import apply_action as apply_economy_action
        from scenario_district import selected_district
        tile = selected_district(world, nation) if action_id in ECONOMY_DISTRICT_ACTIONS else None
        ok, message = apply_economy_action(world, nation, action_id, tile)
        if not ok:
            return False, message
    elif action_id in DISTRICT_ACTIONS:
        from scenario_district import apply_action as apply_district_action
        ok, message = apply_district_action(world, nation, action_id)
        if not ok:
            return False, message
    elif action_id == "release_maize":
        ration_size = 4
        stock_before = int(getattr(nation.government, "food_inventory", 0))
        release_limit = int(state.get("relief_units_per_turn", 30))
        operation_id = (f'national-maize-release:{nation.name}:{turn}:'
                        f'{stock_before}:{release_limit}')
        available = min(int(state.get("relief_units_per_turn", 30)),
                        int(getattr(nation.government, "food_inventory", 0)) // ration_size)
        if available <= 0:
            reason = ('release_limit_is_zero' if release_limit <= 0
                      else 'public_stock_below_full_ration')
            _trace_national_maize_release(
                world, nation, operation_id=operation_id, turn=turn,
                outcome=reason, stock_before=stock_before,
                stock_after=stock_before, ration_limit=release_limit,
                underfed_count=0)
            return False, "The public maize reserve is empty."
        households = [a for tile in nation.tiles for a in getattr(tile, "agents", [])
                      if getattr(a, "alive", True) and not getattr(a, "is_government", False)
                      and not getattr(a, "is_corporation", False) and not getattr(a, "is_trader", False)
                      and deficit_fraction(a) > 0]
        households.sort(key=lambda a: (a.inv_get(Goods.food),
                                       float(getattr(a, "cash", 0.0)),
                                       -deficit_fraction(a)))
        recipients = households[:available]
        if not recipients:
            _trace_national_maize_release(
                world, nation, operation_id=operation_id, turn=turn,
                outcome='no_underfed_households', stock_before=stock_before,
                stock_after=stock_before, ration_limit=release_limit,
                underfed_count=len(households))
            return False, "No households currently need a public maize meal."
        # The public stock moves into reserved household rations. Consumption
        # uses them next turn, before the ending measures household hunger.
        from nutrition import queue_emergency_meal
        transfer_event_ids = []
        for person in recipients:
            queue_before = int(getattr(person, 'emergency_food_units', 0))
            queue_emergency_meal(person, ration_size)
            person_tile = next((tile for tile in nation.tiles
                                if person in getattr(tile, 'agents', ())),
                               getattr(nation, 'capital', None))
            stock_at_start = int(nation.government.food_inventory)
            nation.government.food_inventory -= ration_size
            transfer_id = _trace_national_maize_ration(
                person_tile, operation_id=f'{operation_id}:{person.id}',
                turn=turn, nation=nation, recipient=person, units=ration_size,
                stock_before=stock_at_start,
                stock_after=int(nation.government.food_inventory),
                queue_before=queue_before,
                queue_after=int(getattr(person, 'emergency_food_units', 0)))
            if transfer_id:
                transfer_event_ids.append(transfer_id)
        state["public_maize_stock_units"] = nation.government.food_inventory
        _trace_national_maize_release(
            world, nation, operation_id=operation_id, turn=turn,
            outcome='rations_queued', stock_before=stock_before,
            stock_after=int(nation.government.food_inventory),
            ration_limit=release_limit, underfed_count=len(households),
            recipient_ids=[person.id for person in recipients],
            cause_event_ids=transfer_event_ids)
        message = f"Issued next-meal maize rations to {len(recipients)} households from the public reserve."
    elif action_id == "prioritize_domestic_grain":
        if state.get("domestic_grain_priority"):
            return False, "More grain is already being retained for domestic supply."
        for tile in nation.tiles:
            tile.food_export_fraction = 0.5
        state["domestic_grain_priority"] = True
        state["creditor_confidence"] = max(0.0, state.get("creditor_confidence", 0.6) - 0.10)
        message = "More food exports will be retained in local granaries; export receipts may fall."
    elif action_id in ('repair_delta_channels', 'repair_upper_channels'):
        from scenario_projects import start_project
        site = 'Nile Delta' if action_id == 'repair_delta_channels' else 'Upper Egypt'
        ok, message = start_project(world, 'nile_repair', site)
        if not ok:
            return False, message
    elif action_id == 'build_revenue_office':
        from scenario_projects import start_project
        ok, message = start_project(world, 'revenue_office', 'Alexandria')
        if not ok:
            return False, message
    elif action_id == 'prepare_canal_line':
        from scenario_projects import start_project
        ok, message = start_project(world, 'canal_line', 'Tel el Kebir')
        if not ok:
            return False, message
    elif action_id == 'repair_canal_line':
        from scenario_projects import repair_project
        ok, message = repair_project(world, 'canal_line', 'Tel el Kebir')
        if not ok:
            return False, message
    elif action_id in ('publish_revenue_accounts', 'refuse_revenue_inspection'):
        from scenario_projects import answer_fiscal_challenge
        ok, message = answer_fiscal_challenge(world, action_id == 'publish_revenue_accounts')
        if not ok:
            return False, message
    elif action_id == "reduce_fellahin_tax":
        if all(float(getattr(tile.gov, "tax_rate", 0.0)) <= 0.0 for tile in nation.tiles):
            return False, "Local taxes are already at zero."
        effective_cut = 0.0
        for tile in nation.tiles:
            old_rate = float(getattr(tile.gov, "tax_rate", 0.0))
            tile.gov.tax_rate = max(0.0, old_rate - 0.03)
            fraction = (old_rate - tile.gov.tax_rate) / 0.03
            effective_cut += fraction
            tile.unrest_level = float(getattr(tile, "unrest_level", 0.0)) * exp(-0.11 * fraction)
        nation.legitimacy = min(1.0, float(getattr(nation, "legitimacy", 0.5))
                                + 0.04 * effective_cut / max(1, len(nation.tiles)))
        state["tax_relief_enacted"] = True
        state["extraction_level"] = max(0, int(state.get("extraction_level", 0)) - 1)
        message = "Reduced regional taxes for cultivators; the treasury will collect less revenue."
    elif action_id == "raise_local_taxes":
        if all(float(getattr(tile.gov, "tax_rate", 0.0)) >= 0.60 for tile in nation.tiles):
            return False, "Local taxes are already at the 60% ceiling."
        effective_hike = 0.0
        for tile in nation.tiles:
            old_rate = float(getattr(tile.gov, "tax_rate", 0.0))
            tile.gov.tax_rate = min(0.60, old_rate + 0.05)
            fraction = (tile.gov.tax_rate - old_rate) / 0.05
            effective_hike += fraction
            prior = float(getattr(tile, "unrest_level", 0.0))
            tile.unrest_level = 1.0 - (1.0 - prior) * exp(-0.16 * fraction)
        nation.legitimacy = max(0.0, float(getattr(nation, "legitimacy", 0.5))
                                - 0.08 * effective_hike / max(1, len(nation.tiles)))
        state["extraction_level"] += 1
        message = "Raised local taxes to protect revenue; cultivator unrest and political strain increased."
    elif action_id == "intensify_requisitions":
        if state.get('extraction_level', 0) <= 0:
            return False, 'Raise local taxes before ordering repeated requisitions.'
        below_ceiling = any(float(getattr(tile.gov, 'tax_rate', 0)) < .60 for tile in nation.tiles)
        for tile in nation.tiles:
            tile.gov.tax_rate = min(.60, float(getattr(tile.gov, 'tax_rate', 0)) + .04)
            prior = float(getattr(tile, 'unrest_level', 0))
            tile.unrest_level = 1.0 - (1.0 - prior) * exp(-.16)
        nation.legitimacy = max(0.0, float(nation.legitimacy) - .08)
        state['extraction_level'] += 1
        message = ('Ordered another round of requisitions; future tax receipts can rise, but unrest and legitimacy deteriorate.'
                   if below_ceiling else
                   'Enforced the emergency tax ceiling through another round of requisitions; unrest and legitimacy deteriorate.')
    elif action_id == 'reinforce_alexandria':
        from scenario_gunboat import reinforce_batteries
        ok, message = reinforce_batteries(world)
        if not ok:
            return False, message
    elif action_id == 'close_canal':
        from scenario_geography import close_canal
        ok, message = close_canal(world)
        if not ok:
            return False, message
    elif action_id in ('comply_oversight', 'seek_narrower_oversight', 'revoke_oversight'):
        from scenario_oversight import action as oversight_action
        ok, message = oversight_action(world, action_id)
        if not ok:
            return False, message
    elif action_id in ('request_french_mediation', 'offer_joint_guarantee', 'seek_french_opposition'):
        from scenario_diplomacy import make_offer
        ok, message = make_offer(world, action_id)
        if not ok:
            return False, message
    elif action_id in ('organize_boycott', 'call_general_strike', 'coordinate_insurgency',
                       'collaborate_with_occupation', 'negotiate_withdrawal'):
        from scenario_occupation import apply_action as apply_occupation_action
        ok, message = apply_occupation_action(world, action_id)
        if not ok:
            return False, message
    elif action_id in ('pay_army_arrears', 'promote_egyptian_officers',
                       'invite_representative_cabinet', 'dismiss_foreign_controllers'):
        from scenario_politics import apply_action as apply_political_action
        ok, message = apply_political_action(world, action_id)
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
        if action_id == "defer_remittance" and turn + deferral_delay > campaign_horizon(world):
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
            from scenario_debt import pay as pay_debt, outstanding, write_down
            ok, reason = pay_debt(world, amount, kind='payment' if action_id == 'pay_remittance' else 'concession_payment')
            if not ok:
                return False, reason
            if action_id == 'concede_revenue':
                write_down(world, amount)
                state['service_concession_used'] = True
            state['service_periods_paid'] += 1
            remaining_claim = outstanding(world)
            state["payment_status"] = ("restructured" if state['service_concession_used'] else "paid") if remaining_claim <= .01 else "upcoming"
            state["settlement_path"] = "revenue_concession" if state['service_concession_used'] else "scheduled_payment"
            if remaining_claim > .01:
                state['scheduled_remittance'] = min(float(debt_rules['initial_payment']), remaining_claim)
                state['payment_window_turn'] = min(turn + int(debt_rules['service_interval_turns']),
                                                   campaign_horizon(world))
            else:
                state['scheduled_remittance'] = 0.0
            state["creditor_levy_per_turn"] = 0.0
            state["creditor_levy_remaining"] = 0.0
            if state.get('collection_assignment'):
                state['collection_assignment']['status'] = 'discharged'
            state["creditor_confidence"] = min(1.0, state.get("creditor_confidence", 0.6) + 0.15)
            if action_id == "concede_revenue":
                state["fiscal_autonomy"] = max(0.0, state.get("fiscal_autonomy", 1.0) - 0.25)
                from scenario_oversight import sign as sign_oversight
                sign_oversight(world, amount)
                message = f"Paid {amount:,.0f} and wrote down {amount:,.0f} under Caisse oversight; {remaining_claim:,.0f} remains due."
            else:
                message = f"Paid {amount:,.0f} in debt service; {remaining_claim:,.0f} remains due."
            if remaining_claim <= .01 and state.get('naval_crisis', {}).get('stage') in ('mobilizing', 'ultimatum', 'blockaded'):
                from scenario_gunboat import withdraw
                withdraw(world, 'Debt service is settled; the British squadron withdraws from Alexandria.', cause='settlement')
        elif action_id == "defer_remittance":
            state["payment_status"] = "deferred"
            state["deferral_count"] = int(state.get("deferral_count", 0)) + 1
            state["payment_window_turn"] = turn + deferral_delay
            from scenario_debt import adjust_service
            adjust_service(world, round(amount * float(debt_rules['deferral_multiplier']), 2),
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
    from scenario_history import record as record_history
    record_history(world, message)
    world["scenario_feedback"] = message
    from client.desktop.engine import ticker_push
    ticker_push(world, turn, "SCENARIO", message, (120, 220, 170))
    from scenario_situation import queue_creditor_reaction
    queue_creditor_reaction(world, action_id)
    record_change(world, action_id, status_before, snapshot(world))
    try:
        from economy.true_cost_ledger import get_decision_tracker
        get_decision_tracker().record_decision(action_id, turn=turn)
    except Exception:
        pass
    return True, message


def advance_scenario(world: dict, turn: int, ticker_push, on_phase=None) -> None:
    """Resolve calendar events, thresholds, and the campaign's terminal outcome."""
    if not is_scenario_id(world.get("scenario_id")):
        return
    state = world.setdefault("scenario_state", {})
    nation = next((n for n in world.get("nations", []) if n.name == world.get("player_nation_name")), None)
    if nation is None:
        return
    state["turns_remaining"] = max(0, campaign_horizon(world) - turn)
    state.setdefault("events_fired", [])
    if turn == 1 and "low_nile" not in state["events_fired"]:
        state["events_fired"].append("low_nile")
        ticker_push(world, turn, "SCENARIO", "The weak Nile flood cuts the expected food harvest along the Nile corridor.", (230, 174, 88))
    from scenario_situation import collect_creditor_levy, update_foreign_reports, advance_creditor_reactions
    levy_paid = collect_creditor_levy(world)
    if levy_paid:
        ticker_push(world, turn, "CREDITOR", f"The Caisse collected {levy_paid:,.0f} units from Egyptian receipts.", (225, 178, 87))
    if on_phase:
        on_phase('levy')
    from scenario_projects import advance as advance_projects
    advance_projects(world)
    from scenario_projects import record_food_results
    record_food_results(world)
    if on_phase:
        on_phase('strategic_projects')
    from scenario_political_economy import advance as advance_political_economy
    advance_political_economy(world, nation, turn)
    from scenario_projects import advance_grain_entitlement
    advance_grain_entitlement(world)
    if on_phase:
        on_phase('political_economy')
    if turn >= int(state.get("payment_window_turn", 6)) and state.get("payment_status") in ("upcoming", "deferred"):
        state["payment_status"] = "unpaid"
        world["playing"] = False
        world["scenario_warning_modal"] = {"kind": "debt_due"}
        state["events_fired"].append(f"debt_service_window_{turn}")
        from scenario_debt import outstanding
        world["scenario_feedback"] = (f"Debt instalment of {state['scheduled_remittance']:,.0f} is due now; "
                                       f"{outstanding(world):,.0f} remains on the Caisse bonds.")
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
        energy = max(0.0, float(history[-1])) if history else 0.0
        # Local protest is already reflected in the shared simulation's
        # unrest value. Translate it into scenario pressure with diminishing
        # returns so persistent petitioning alone does not force every ending
        # into political collapse; coercion can still push unrest over 0.85.
        pressure = 0.72 * (1.0 - exp(-energy / 4.0))
        current = float(getattr(tile, "unrest_level", 0.0))
        tile.unrest_level = max(0.0, min(1.0, current * 0.75 + pressure * 0.25))
    if on_phase:
        on_phase('protest_pressure')
    update_foreign_reports(world)
    from scenario_oversight import advance as advance_oversight
    advance_oversight(world, turn, ticker_push)
    from scenario_politics import advance as advance_politics
    advance_politics(world)
    if state['politics']['crisis_resolved'] or state.get('naval_crisis', {}).get('stage') not in ('none',):
        enter_chapter_two(world, 'political crisis' if state['politics']['crisis_resolved'] else 'naval crisis')
    if on_phase:
        on_phase('politics')

    metrics = _outcome_metrics(nation)
    thresholds = world.get('scenario', SCENARIO)['thresholds']
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
    from scenario_diplomacy import advance as advance_diplomacy
    advance_diplomacy(world, turn, ticker_push)
    if world.get("scenario_warning_modal"):
        return
    from scenario_gunboat import advance_naval_crisis
    advance_naval_crisis(world)
    if on_phase:
        on_phase('naval_crisis')
    if world.get("scenario_warning_modal"):
        return
    from scenario_campaign import advance_expedition
    advance_expedition(world)
    if on_phase:
        on_phase('campaign')
    if world.get("scenario_warning_modal"):
        return
    from scenario_occupation import advance as advance_occupation
    advance_occupation(world)
    if on_phase:
        on_phase('occupation')
    if world.get("scenario_warning_modal"):
        return
    finish_due_campaign(world)


def classify_outcome(world: dict, metrics: dict | None = None) -> str:
    """Select one declared ending from measured control, debt, and welfare."""
    state = world.get('scenario_state', {})
    nation = next((n for n in world.get('nations', [])
                   if n.name == world.get('player_nation_name')), None)
    if nation is None:
        return 'breakdown'
    metrics = metrics if metrics is not None else _outcome_metrics(nation)
    evidence = outcome_evidence(world, metrics)
    thresholds = world.get('scenario', SCENARIO)['thresholds']
    control = evidence['territorial_control']
    if control.get('Cairo') == 'Britain':
        return 'occupation'
    if any(owner == 'Britain' for owner in control.values()):
        return 'stalled_intervention'
    if metrics['legitimacy'] <= thresholds['breakdown_legitimacy'] or metrics['unrest'] >= thresholds['breakdown_unrest']:
        return 'breakdown'
    if evidence['joint_collection']:
        return 'joint_financial_control'
    if evidence['active_assignment']:
        return 'imposed_financial_control'
    if evidence['french_treaty'] and evidence['outstanding_claim'] <= .01:
        return 'french_brokered_settlement'
    if state.get('settlement_path') == 'ottoman_mediation' and state.get('payment_status') == 'restructured':
        return 'sovereign_compromise'
    if evidence['disarmed'] and evidence['outstanding_claim'] > 0:
        return 'coerced_disarmament'
    if (evidence['nationalist'] and evidence['foreign_defeated']
            and not evidence['active_assignment'] and not evidence['disarmed']):
        return 'nationalist_victory'
    if (state.get('payment_status') == 'defaulted' and evidence['foreign_defeated']
            and not evidence['active_assignment'] and not evidence['disarmed']):
        return 'successful_repudiation'
    if state.get('extraction_level', 0) > 0:
        return 'coercive_extraction'
    if evidence['outstanding_claim'] <= .01 and metrics['hunger_rate'] > thresholds['protected_hunger_rate']:
        return 'fiscal_hardship'
    if evidence['outstanding_claim'] <= .01 and metrics['hunger_rate'] <= thresholds['protected_hunger_rate'] and state.get('payment_status') == 'paid':
        return 'relief_and_payment'
    if evidence['outstanding_claim'] <= .01 and metrics['hunger_rate'] <= thresholds['protected_hunger_rate'] and state.get('payment_status') == 'restructured':
        return 'creditor_settlement'
    return 'unresolved_crisis'


def outcome_evidence(world: dict, metrics: dict | None = None) -> dict:
    """Facts used by the ending and shown in the debrief."""
    from scenario_debt import outstanding
    state = world.get('scenario_state', {})
    campaign = state.get('campaign', {})
    cause = state.get('naval_withdrawal_cause')
    expedition = campaign.get('expedition', {})
    claim = outstanding(world)
    diplomatic = state.get('diplomatic_crisis') or {}
    treaty = diplomatic.get('treaty') or {}
    assignment = state.get('collection_assignment') or {}
    recipients = {entry.get('creditor') for entry in state.get('debt_ledger', [])
                  if entry.get('kind') == 'assigned_revenue'}
    return {
        'outstanding_claim': claim,
        'territorial_control': dict(campaign.get('territorial_control', {})),
        'active_assignment': (float(state.get('creditor_levy_per_turn', 0)) > 0
                              and claim > .01),
        'disarmed': bool(state.get('disarmed_batteries')),
        'withdrawal_cause': cause,
        'foreign_defeated': (cause in ('deterrence', 'unsustainable', 'military_defeat',
                                      'no_access', 'negotiated_withdrawal')
                             or expedition.get('stage') == 'repelled'),
        'nationalist': state.get('politics', {}).get('governing_coalition') == 'nationalist',
        'joint_collection': (assignment.get('status') == 'active'
                             and assignment.get('origin') == 'joint_guarantee'
                             and {'Egypt', 'Britain', 'France'} <= set(treaty.get('signatories', []))
                             and {'Britain', 'France'} <= recipients and claim > .01),
        'french_treaty': (treaty.get('kind') == 'french_mediation'
                          and treaty.get('status') == 'active'
                          and {'Egypt', 'Britain', 'France'} <= set(treaty.get('signatories', []))),
        'french_policy': diplomatic.get('french_policy', 'abstain'),
        'french_fleet_joined': bool(state.get('naval_crisis', {}).get('french_fleet_ever_joined')),
    }


def finish_due_campaign(world: dict) -> None:
    """Complete the current campaign horizon after pending decisions are answered."""
    state = world.get('scenario_state', {})
    turn = int(world.get('turn', 0))
    if (turn < campaign_horizon(world) or state.get('ending')
            or world.get('scenario_warning_modal')):
        return
    from client.desktop.engine import ticker_push
    from scenario_situation import advance_creditor_reactions
    advance_creditor_reactions(world, turn, ticker_push)
    if world.get('scenario_warning_modal'):
        return
    from scenario_diplomacy import advance as advance_diplomacy
    advance_diplomacy(world, turn, ticker_push)
    if world.get('scenario_warning_modal'):
        return
    nation = next((n for n in world.get('nations', [])
                   if n.name == world.get('player_nation_name')), None)
    if nation is None:
        return
    metrics = _outcome_metrics(nation)
    outcome = classify_outcome(world, metrics)
    _finish_scenario(world, nation, outcome, turn, metrics)


def _outcome_metrics(nation) -> dict:
    households = [a for tile in nation.tiles for a in getattr(tile, "agents", [])
                  if getattr(a, "alive", True) and not getattr(a, "is_government", False)
                  and not getattr(a, "is_corporation", False) and not getattr(a, "is_trader", False)]
    hungry = sum(1 for a in households if deficit_fraction(a) > 0)
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
    from scenario_status import record_social_costs
    record_social_costs(world, turn)
    state = world["scenario_state"]
    state["ending"] = outcome
    state["ending_turn"] = turn
    state["ending_metrics"] = metrics
    state["ending_evidence"] = outcome_evidence(world, metrics)
    state["turns_remaining"] = max(0, campaign_horizon(world) - turn)
    state["debrief"] = build_debrief(world, outcome, metrics)
    world["playing"] = False
    world["scenario_feedback"] = state["debrief"]["summary"]
    world["scenario_bookend_modal"] = "debrief"
    world["scenario_bookend_scroll"] = 0


def build_debrief(world: dict, outcome: str, metrics: dict | None = None) -> dict:
    """Summarize the ending and cite the player's decisions and measured state."""
    from scenario_political_economy import stock as warehouse_stock
    nation = next((n for n in world.get("nations", []) if n.name == world.get("player_nation_name")), None)
    metrics = metrics or (_outcome_metrics(nation) if nation else {})
    state = world.get("scenario_state", {})
    from scenario_status import snapshot
    current = snapshot(world) or {}
    social = world.get('scenario_status_history', {}).get('social_costs', {})
    debt_transfers = sum(float(entry.get('amount', 0.0)) for entry in state.get('debt_ledger', [])
                         if entry.get('kind') in ('payment', 'concession_payment', 'assigned_revenue',
                                                  'french_mediation', 'naval_settlement',
                                                  'landing_settlement', 'ottoman_mediation'))
    economy = state.get('political_economy', {})
    grain_log = economy.get('grain_transactions', [])
    transfers = economy.get('tenure_transfers', [])
    fiscal_reports = economy.get('fiscal_reports', [])
    diverted = sum(float(row.get('diverted', 0.0)) for row in fiscal_reports)
    relief_gap = sum(float(row.get('attributable_to_assignment', 0.0)) for row in fiscal_reports)
    mutual_aid = sum(int(row.get('mutual_aid_meals', 0))
                     for row in economy.get('collective_by_tile', {}).values())
    injuries = sum(int(row.get('injuries', 0))
                   for row in economy.get('collective_by_tile', {}).values())
    social_stats = [
        {'label': 'Household hunger',
         'value': f"{int(social.get('household_hunger_turns', metrics.get('hungry', 0))):,} household-turns",
         'note': 'One household counted once for each turn it went hungry.'},
        {'label': 'Worst food shortage',
         'value': f"{int(social.get('peak_hungry', metrics.get('hungry', 0))):,} households on turn {social.get('peak_hunger_turn', world.get('turn', 0))}",
         'note': f"Households and owners still held {float(social.get('private_food_at_peak', current.get('private_food', 0))):,.0f} private food units then; this includes ordinary pantry stocks."},
        {'label': 'Cash concentration',
         'value': f"Top fifth: {float(current.get('top_fifth_cash_share', 0)):.0%} of cash",
         'note': f"Bottom quarter: {float(current.get('bottom_quarter_cash_share', 0)):.0%}. Opening shares: {float(social.get('opening_top_fifth_cash_share', 0)):.0%} and {float(social.get('opening_bottom_quarter_cash_share', 0)):.0%}. Positive balances only."},
        {'label': 'Tax taken from districts',
         'value': f"{float(social.get('tax_collected', 0)):,.0f} units",
         'note': 'Gross tax collected across national, provincial, and local governments.'},
        {'label': 'Caisse debt transferred',
         'value': f'{debt_transfers:,.0f} units',
         'note': 'Actual Caisse bond payments and assigned receipts transferred to Britain and France.'},
        {'label': 'Private grain held and traded',
         'value': f'{int(current.get("private_food", 0)):,} private food units',
         'note': f'{warehouse_stock(world, nation) if nation else 0:,} deliberately reserved by warehouse owners at the end. '
                 f'{sum(row["units"] for row in grain_log if row["kind"] == "public_buy")} bought by Cairo; '
                 f'{sum(row["units"] for row in grain_log if row["kind"] == "requisition")} requisitioned.'},
        {'label': 'Land access and migration',
         'value': f'{len(transfers)} cultivators lost plot access',
         'note': f'{len(economy.get("migrations", []))} moved district; title holders and use-right buyers are recorded by agent ID.'},
        {'label': 'Collective food and violence',
         'value': f'{mutual_aid} food units shared',
         'note': f'{injuries} people received injury memories during strikebreaking.'},
        {'label': 'Assigned receipts vs relief',
         'value': f'{diverted:,.1f} transferred to creditors',
         'note': f'Up to {relief_gap:,.1f} of measured relief purchasing shortfalls coincide with money diverted from actual receipts.'},
        {'label': 'Civilians injured',
         'value': f"{int(state.get('campaign', {}).get('civilian_casualties', 0)):,}",
         'note': 'Recorded injuries from bombardment and occupation resistance.'},
        {'label': 'Unmet calories',
         'value': f"{float(social.get('total_deficit_kcal', 0)):,.0f} kcal",
         'note': 'Sum of household calorie deficits across completed campaign turns.'},
        {'label': 'Surplus and fat reserve',
         'value': f"{float(social.get('total_surplus_kcal', 0)):,.0f} kcal surplus",
         'note': f"Final mean body energy reserve: {float(current.get('mean_fat_kg', 0)):.1f} kg fat equivalent."},
    ]
    from scenario_projects import debrief_evidence
    project_summary = debrief_evidence(world)
    social_stats.extend(project_summary['social_stats'])
    if int(state.get('chapter', 1)) >= 2:
        campaign = state.get('campaign', {})
        occupation = state.get('occupation', {})
        battles = campaign.get('battles', [])
        occupation_receipts = sum(float(row.get('amount', 0.0))
                                  for row in occupation.get('revenue_ledger', [])
                                  if row.get('source') in ('tax', 'tariff'))
        war_stats = [
            {'label': 'Battle losses',
             'value': (f'{sum(int(row.get("def_losses", 0)) for row in battles)} Egyptian; '
                       f'{sum(int(row.get("atk_losses", 0)) for row in battles)} British'),
             'note': f'{len(battles)} land battles recorded; Alexandria port damage '
                     f'{float(campaign.get("infrastructure_damage", {}).get("Alexandria", 0)):.0%}.'},
            {'label': 'Occupation revenue and supply',
             'value': f'{occupation_receipts:,.1f} units taken',
             'note': f'British garrison supply cost {float(occupation.get("garrison_supply_paid", 0)):,.1f}; '
                     f'resistance at the end {float(occupation.get("resistance", 0)):.0%}.'},
        ]
        civilian = next(stat for stat in social_stats if stat['label'] == 'Civilians injured')
        social_stats = ([social_stats[0], social_stats[1], civilian] + war_stats
                        + [stat for stat in social_stats[2:] if stat is not civilian])
    labels = {
        "relief_and_payment": ("Relief and payment", "Food access held and the full Caisse claim was paid."),
        "creditor_settlement": ("Creditor settlement", "Food access held and the Caisse claim was cleared through payments and conditional revenue concessions."),
        "sovereign_compromise": ("Sovereign compromise", "Ottoman mediation secured reduced debt terms without foreign control of Egyptian territory or revenue."),
        "imposed_financial_control": ("Creditor financial control", "The Caisse still collects assigned Egyptian receipts under a creditor demand."),
        "coercive_extraction": ("Coercive extraction", "The government protected revenue by raising local taxes, increasing unrest and political strain."),
        "breakdown": ("Government breakdown", "The administration lost control of the crisis before it could protect both food access and fiscal capacity."),
        "occupation": ("British occupation", "British troops hold Cairo and control the tax administration despite Egypt's formal sovereignty."),
        "stalled_intervention": ("Stalled intervention", "Britain holds a foothold but has not taken Cairo or its government."),
        "nationalist_victory": ("Nationalist victory", "The Egyptian governing coalition retained authority and the British expedition withdrew."),
        "successful_repudiation": ("Successful repudiation", "Egypt withheld payment and the foreign expedition withdrew without gaining control."),
        "fiscal_hardship": ("Fiscal settlement amid hardship", "Debt was settled, but household food access remained poor."),
        "coerced_disarmament": ("Disarmed under pressure", "Egypt disarmed its coastal batteries while the creditor claim remained unresolved."),
        "unresolved_crisis": ("Unresolved crisis", "Egypt still governs, but the debt or foreign claim remains unsettled."),
        "joint_financial_control": ("Joint creditor control", "Britain and France jointly collect assigned Egyptian receipts under a signed guarantee."),
        "french_brokered_settlement": ("French-brokered settlement", "France brokered a paid agreement accepted by Egypt and Britain without foreign revenue control."),
    }
    title, summary = labels.get(outcome, labels["breakdown"])
    actions = [entry.get("message", "") for entry in state.get("actions_taken", [])]
    if not actions:
        actions = ["No major scenario decision was recorded before the ending."]
    evidence = outcome_evidence(world, metrics)
    debt_detail = (f"Debt service {state.get('payment_status', 'unresolved')}; "
                   f"outstanding Caisse claim {evidence['outstanding_claim']:,.0f}; "
                   f"fiscal autonomy {state.get('fiscal_autonomy', 1.0):.0%}.")
    if state.get('payment_status') in ('deferred', 'unpaid'):
        debt_detail += (f" Next due: turn {state.get('payment_window_turn', '?')}, "
                        f"{state.get('scheduled_remittance', 0):,.0f} units.")
    if float(state.get('creditor_levy_per_turn', 0.0)) > 0:
        debt_detail += (f" Caisse levy: up to {state['creditor_levy_per_turn']:,.0f} units per turn, "
                        f"{state.get('creditor_levy_remaining', 0.0):,.0f} remaining.")
    assignment = state.get('collection_assignment') or {}
    if assignment.get('status') == 'active':
        debt_detail += f" Active assignment: {assignment.get('origin', 'creditor demand').replace('_', ' ')}."
    occupation = state.get('occupation', {})
    institutions = occupation.get('institutional_control', {})
    territorial = evidence['territorial_control']
    control_detail = (f'Alexandria: {territorial.get("Alexandria", "Egypt")}; '
                      f'Cairo: {territorial.get("Cairo", "Egypt")}; '
                      f'formal sovereign: {occupation.get("formal_sovereign", "Egypt")}; '
                      f'customs: {institutions.get("customs", "Egypt")}; '
                      f'cabinet: {institutions.get("cabinet", "Egypt")}.')
    diplomatic = state.get('diplomatic_crisis') or {}
    treaty = diplomatic.get('treaty') or {}
    diplomacy_detail = (f'France: {evidence["french_policy"].replace("_", " ")}; '
                        f'French fleet joined: {"yes" if evidence["french_fleet_joined"] else "no"}; '
                        f'treaty: {treaty.get("kind", "none").replace("_", " ")}; '
                        f'British withdrawal: {evidence["withdrawal_cause"] or "none"}.')
    if evidence['disarmed']:
        diplomacy_detail += ' Egyptian coastal batteries were disarmed.'
    return {
        "outcome": outcome,
        "title": title,
        "summary": summary,
        "social_stats": social_stats,
        "food": f"{metrics.get('hungry', 0)} of {metrics.get('households', 0)} households hungry ({metrics.get('hunger_rate', 0.0):.0%}).",
        "debt": debt_detail,
        "control": control_detail,
        "projects": project_summary['projects'],
        "project_social_stats": project_summary['social_stats'],
        "diplomacy": diplomacy_detail,
        "politics": f"Government legitimacy {metrics.get('legitimacy', 0.0):.0%}; average unrest {metrics.get('unrest', 0.0):.2f}.",
        "authority": (f"{state.get('politics', {}).get('ruler', 'Unknown ruler')}; "
                      f"{state.get('politics', {}).get('governing_coalition', 'unknown')} coalition; "
                      f"army loyalty {state.get('politics', {}).get('army_loyalty', 0.0):.0%}; "
                      f"resistance {occupation.get('resistance', 0.0):.0%}; "
                      f"civilian injuries {state.get('campaign', {}).get('civilian_casualties', 0)}."),
        "actions": actions,
        "creditor_reactions": [entry['headline'] for entry in state.get('creditor_news', [])],
        "historical_log": list(state.get('historical_log', [])),
        "naval_events": [entry['text'] for entry in state.get('naval_news', [])],
        "diplomacy_history": list(diplomatic.get('history', [])),
        "grain_transactions": list(grain_log),
        "tenure_transfers": list(transfers),
        "tax_assessments": list(economy.get('tax_assessments', [])),
        "fiscal_reports": list(fiscal_reports),
        "strategic_projects": project_summary['strategic_projects'],
        "project_payments": project_summary['project_payments'],
        "project_revenue_reports": project_summary['project_revenue_reports'],
        "corporate_externalities": _get_egypt_corps_externalities(world),
        "decisions_externalities": _get_egypt_decisions_externalities(),
    }


def _get_egypt_corps_externalities(world: dict) -> dict:
    try:
        from economy.true_cost_ledger import get_true_cost_ledger
        p_name = world.get('player_nation_name', 'Egypt')
        return get_true_cost_ledger().get_national_corporate_externalities(p_name, world)
    except Exception:
        return {}


def _get_egypt_decisions_externalities() -> list:
    try:
        from economy.true_cost_ledger import get_decision_tracker
        return get_decision_tracker().get_all_entries_dict()
    except Exception:
        return []


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
