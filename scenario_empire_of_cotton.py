"""
scenario_empire_of_cotton.py — JSON-Driven Historical Scenario Runner for Empire of Cotton.

Integrates the procedural map generator, Sven Beckert capitalist propagation mechanics,
and the generic ScenarioInterpreter framework.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

from scenarios.interpreter import ScenarioInterpreter
from economy.map_generator import generate_capitalism_map
from goods import Goods
from agent import Agent, initialize_agent


TEMPLATE_PATH = Path(__file__).parent / 'scenarios' / 'templates' / 'empire_of_cotton.scenario.json'


def get_empire_of_cotton_interpreter() -> ScenarioInterpreter:
    """Load the declarative Empire of Cotton scenario interpreter from JSON template."""
    return ScenarioInterpreter.from_file(TEMPLATE_PATH)


def create_empire_of_cotton_world(seed: int = 42) -> Dict[str, Any]:
    """Generates and configures a complete world for the Empire of Cotton scenario.

    Guarantees:
    - Player nation 'Lancashire_Metropole' with urban manufacturing and merchant banking.
    - Rival nation 'Agrarian_Feudality' with customary manorial land tenure.
    - Peripheral wilderness tiles 'Colonial_Frontier' for War Capitalism conquest.
    """
    tiles, nations, grid = generate_capitalism_map(seed=seed)

    # Configure player nation
    player_nation = nations[0]
    player_nation.name = "Lancashire_Metropole"
    player_nation.currency = "Pound_Sterling"
    if hasattr(player_nation, 'government') and player_nation.government:
        player_nation.government.agent.cash = 500.0

    # Configure rival feudal nation
    if len(nations) > 1:
        feudal_nation = nations[1]
        feudal_nation.name = "Agrarian_Feudality"
        feudal_nation.currency = "Livre_Tournois"

    # Separate wilderness frontier tiles
    wilderness_tiles = [t for t in tiles if getattr(t, 'wilderness', False) and getattr(t, 'wilderness_pop', 0) > 0]
    for wt in wilderness_tiles:
        wt.name = f"Colonial_Frontier_{wt.name}"

    # Seat a wealthy merchant investor in Lancashire capital
    capital_tile = player_nation.tiles[0]
    if capital_tile.agents:
        investor = capital_tile.agents[0]
        investor.is_lord = False
        investor.is_trader = True
        investor.cash = max(150.0, getattr(investor, 'cash', 0.0))
        investor.inv_add(Goods.cotton, 25)
        investor.inv_add(Goods.cloth, 10)

    # Establish initial trade routes between player and frontier
    if wilderness_tiles and not capital_tile.neighbors:
        capital_tile.add_neighbor(wilderness_tiles[0])
        wilderness_tiles[0].add_neighbor(capital_tile)

    from economy.triangular_trade import TradeTriangleManager
    from economy.trade_circuit_discovery import TradeCircuitGraphSearch
    from economy.luddite_resistance import LudditeMovementManager
    from economy.geopolitical_rivalry import GeopoliticalRivalryManager

    circuits = TradeCircuitGraphSearch.discover_circuits()
    trade_mgr = TradeTriangleManager(circuits)
    capital_tile.trade_manager = trade_mgr
    luddite_mgr = LudditeMovementManager()
    rivalry_mgr = GeopoliticalRivalryManager()

    world = {
        'turn': 1,
        'player_nation_name': "Lancashire_Metropole",
        'nations': nations,
        'wilderness_tiles': wilderness_tiles,
        'tiles': tiles,
        'grid': grid,
        'scenario_state': {
            'trade_manager_ref': trade_mgr,
            'luddite_manager_ref': luddite_mgr,
            'rivalry_manager_ref': rivalry_mgr,
        },
    }
    return world


def step_empire_of_cotton_turn(
    world: Dict[str, Any],
    interpreter: ScenarioInterpreter,
    action_id: Optional[str] = None,
    modal_response: Optional[str] = None,
    ticker_push: Optional[Callable] = None
) -> Dict[str, Any]:
    """Advances one turn of the Empire of Cotton scenario with optional player action."""
    turn = int(world.get('turn', 1))
    action_result = None

    # 1. Apply interactive modal response if one was pending
    if modal_response:
        ok_modal, msg_modal = interpreter.resolve_reaction_response(world, modal_response)
        action_result = {'type': 'MODAL_RESPONSE', 'success': ok_modal, 'message': msg_modal}

    # 2. Apply player action if chosen
    elif action_id:
        ok_act, msg_act = interpreter.apply_action(world, action_id)
        action_result = {'type': 'ACTION', 'id': action_id, 'success': ok_act, 'feedback': msg_act}

    # 3. Advance scenario turn lifecycle & dynamic capitalism modules
    interpreter.advance_turn(world, turn, ticker_push=ticker_push)

    # 3b. Advance oceanic merchant voyages & conspicuous consumption
    trade_mgr = world.get('scenario_state', {}).get('trade_manager_ref')
    if trade_mgr:
        voyage_events = trade_mgr.step_all_voyages(world, turn)
        for ev in voyage_events:
            if ticker_push and ev.get('message'):
                ticker_push(world, turn, 'TRADE', ev['message'], (100, 200, 255))

    from economy.conspicuous_consumption import ConspicuousConsumptionManager
    for tile in world.get('tiles', []):
        ConspicuousConsumptionManager.step_region_conspicuous_consumption(tile, turn)

    # 3c. Step Luddite resistance and machine-breaking
    luddite_mgr = world.get('scenario_state', {}).get('luddite_manager_ref')
    if luddite_mgr:
        for tile in world.get('tiles', []):
            ludd_events = luddite_mgr.step_region_luddites(tile, turn)
            for lev in ludd_events:
                if ticker_push and lev.get('message'):
                    ticker_push(world, turn, 'LUDDITE', lev['message'], (245, 70, 70))

    # 3d. Step AI nation geopolitical rivalry & mercantilist tariffs
    rivalry_mgr = world.get('scenario_state', {}).get('rivalry_manager_ref')
    if rivalry_mgr:
        riv_events = rivalry_mgr.evaluate_and_step_rivals(world, turn)
        for rev in riv_events:
            if ticker_push and rev.get('message'):
                ticker_push(world, turn, 'RIVALRY', rev['message'], (240, 180, 50))

    # 4. Evaluate pressures & outcomes
    pressures = interpreter.evaluate_pressures(world)
    outcome = interpreter.evaluate_outcome(world)

    # Increment turn
    world['turn'] = turn + 1

    return {
        'turn_completed': turn,
        'action_result': action_result,
        'pressures': pressures,
        'warning_modal': world.get('scenario_warning_modal'),
        'outcome': outcome,
    }


def run_headless_playthrough(turns: int = 10, seed: int = 42) -> Dict[str, Any]:
    """Executes an automated multi-turn playthrough of the Empire of Cotton scenario."""
    world = create_empire_of_cotton_world(seed=seed)
    interpreter = get_empire_of_cotton_interpreter()
    interpreter.initialize_scenario(world)

    log: List[Dict[str, Any]] = []
    actions_sequence = [
        'incorporate_steam_mill',
        'charter_enclosure_decree',
        'issue_merchant_bills',
        'launch_frontier_expedition',
        'procure_plantation_gangs',
    ]

    for t in range(1, turns + 1):
        chosen_action = actions_sequence[t - 1] if t - 1 < len(actions_sequence) else None
        modal_choice = None

        # If a warning modal was triggered on previous turn, choose first available response
        modal = world.get('scenario_warning_modal')
        if modal and modal.get('responses'):
            modal_choice = modal['responses'][0]['id']
            chosen_action = None

        step_res = step_empire_of_cotton_turn(
            world=world,
            interpreter=interpreter,
            action_id=chosen_action,
            modal_response=modal_choice,
            ticker_push=lambda w, turn, tag, text, color: None
        )
        log.append(step_res)

        if step_res.get('outcome'):
            break

    return {
        'turns_run': len(log),
        'final_turn': world.get('turn'),
        'final_state': world.get('scenario_state'),
        'final_outcome': log[-1].get('outcome') if log else None,
        'playthrough_log': log,
    }
