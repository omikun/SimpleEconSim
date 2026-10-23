"""
Simulation stepping, event ticking, and world state initialization for worldview.
"""

import random
from desktop_trace_session import traced_world_builder, traced_world_step
import forex as fx
from hexmap import rectangular_hex_layout, hex_bbox
from sim_world import build_world, GRID_ROWS, GRID_COLS
from worldview_camera import HEX_SIZE, clamp_cam, reset_cam
from worldview_charts import MIG_C
from worldview_map import ACCENT as CLAIM_C, RED as DESTROY_C
import sim_engine
from world_config import get_ui_mode


def get_layout():
    return rectangular_hex_layout(GRID_ROWS, GRID_COLS)


def get_reverse_layout():
    return {v: k for k, v in get_layout().items()}


@traced_world_builder
def build_world_view(seed=None, terrain_seed=None, nation_seed=None, scenario_id=None):
    """Build the 9x9 hex world + prepare viewer state."""
    from scenario_egypt_1877 import SCENARIO, is_scenario_id
    if is_scenario_id(scenario_id):
        seeds = SCENARIO['seeds']
        seed = seeds['world'] if seed is None else seed
        terrain_seed = seeds['terrain'] if terrain_seed is None else terrain_seed
        nation_seed = seeds['nations'] if nation_seed is None else nation_seed
        # A new authored campaign must not inherit bonds, blockades, or ID-based
        # foreclosure draws from a previously generated world in this process.
        import agent
        import sovereign_bonds
        from agents.resistance.manager import reset_popular_resistance_manager
        from macro.imperialism import manager as imperialism_manager
        agent._agentid_counter[0] = 0
        sovereign_bonds._GLOBAL_BOND_MARKET = None
        imperialism_manager._GLOBAL_IMPERIALISM_MANAGER = None
        reset_popular_resistance_manager()
    if is_scenario_id(scenario_id):
        from scenario_egypt_1877 import deterministic_generation
        with deterministic_generation(seed):
            tiles, nations, _grid = build_world(seed=seed, terrain_seed=terrain_seed,
                                                nation_seed=nation_seed, scenario_id=scenario_id)
    else:
        tiles, nations, _grid = build_world(seed=seed, terrain_seed=terrain_seed,
                                            nation_seed=nation_seed, scenario_id=scenario_id)
    from world_names import assign_world_identities
    assign_world_identities(tiles, nations, seed=nation_seed)
    currencies = [n.currency for n in nations]
    from world_config import is_voronoi_topology, VORONOI_WIDTH, VORONOI_HEIGHT
    if is_voronoi_topology():
        layout = {t.name: getattr(t, 'centroid', (0.0, 0.0)) for t in tiles}
        reverse = {}
        bbox = (0.0, 0.0, VORONOI_WIDTH, VORONOI_HEIGHT)
        gen = _grid
    else:
        layout = get_layout()
        reverse = get_reverse_layout()
        bbox = hex_bbox(layout, HEX_SIZE)
        gen = None

    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None
                   and not getattr(o, 'wilderness', False)]
    by_name = {r.name: r for r in tiles}
    world = {
        'tiles': tiles,
        'nations': nations,
        'player_nation_name': nations[0].name if nations else None,
        'currencies': currencies,
        'pair_orders': pair_orders,
        'by_name': by_name,
        'layout': layout,
        'reverse': reverse,
        'bbox': bbox,
        'gen': gen,
        'slot_1_state': getattr(gen, 'slot_1_state', {}),
        'cam': {'ox': 0.0, 'oy': 0.0, 'zoom': 1.0, 'pitch': 0.0},
        'selected_region': None,
        'turn': 0,
        'playing': False,
        'hover_region': None,
        'frame': 0,
        'view': 0,
        'window': 100,
        'currency_totals': {c: fx.audit_currency_total(tiles, c)
                            for c in currencies},
        'violations': [],
        'ticker_events': [],
        'scope': 'tile',
        'help_open': False,
        'help_scroll': 0,
        'map_layer': 'overview',
        'layers_collapsed': True,
        'panel_tab': 'charts',
        'left_panel': None,
        'last_left_panel': 'build',
        'policy_scope': 'tile',
        'policy_feedback': None,
        'seed': seed,
        'terrain_seed': terrain_seed,
        'nation_seed': nation_seed,
        'ui_mode': get_ui_mode(),
        'guided_analysis_open': False,
        'settings_open': False,
    }
    if is_scenario_id(scenario_id):
        from scenario_egypt_1877 import prepare_world
        prepare_world(world)
    reset_cam(world)
    if is_scenario_id(scenario_id):
        egypt = world['selected_nation']
        centers = [tile.centroid for tile in egypt.tiles if hasattr(tile, 'centroid')]
        if centers:
            world['cam']['target_x'] = sum(x for x, _ in centers) / len(centers)
            world['cam']['target_y'] = sum(y for _, y in centers) / len(centers)
            world['cam']['zoom'] = float(SCENARIO['camera']['zoom'])
            clamp_cam(world)
    return world


def ticker_push(world, t, kind, text, color, n=140):
    if not isinstance(world, dict):
        return
    if 'ticker_events' not in world:
        world['ticker_events'] = []
    world['ticker_events'].append({'t': t, 'kind': kind, 'text': text,
                                   'color': color})
    if len(world['ticker_events']) > n:
        del world['ticker_events'][:len(world['ticker_events']) - n]


@traced_world_step
def step_world(world):
    """Advance one turn of the engine via sim_engine."""
    if world.get('scenario_id') == 'egypt_1877' and world.get('scenario_state', {}).get('ending'):
        world['playing'] = False
        return world.get('violations', [])
    if not world.get('scenario_id'):
        from ai_nation import NationPolicyAI
        player_name = world.get('player_nation_name')
        for nation in world.get('nations', []):
            if nation.name == player_name:
                if isinstance(nation.ai, NationPolicyAI):
                    nation.ai = None
            elif nation.ai is None:
                nation.ai = NationPolicyAI(nation)
    t = world['turn'] + 1
    tiles = world['tiles']
    currencies = world['currencies']
    nations = world['nations']
    pair_orders = world['pair_orders']

    status_before = None
    if world.get('scenario_id') == 'egypt_1877':
        from scenario_status import initialize, record_change, snapshot, finish_turn
        if 'scenario_status_history' not in world:
            initialize(world)
        status_before = snapshot(world)

    def on_phase(source):
        nonlocal status_before
        after = snapshot(world)
        record_change(world, source, status_before, after)
        status_before = after

    def on_event(turn, kind, text):
        if kind in ('COMPLETED', 'CONSTRUCT', 'BUILD'):
            color = (120, 240, 150)
        elif kind in ('OVERRUN', 'DELAY'):
            color = (245, 180, 50)
        elif kind in ('RESEARCH', 'TECH', 'INNOVATION'):
            color = (80, 200, 255)
        elif kind in ('WAR', 'BATTLE'):
            color = (240, 80, 80)
        elif kind in ('PEACE', 'TREATY'):
            color = (130, 210, 240)
        elif kind == 'MIGRATE':
            color = MIG_C
        elif kind == 'CLAIM':
            color = CLAIM_C
        else:
            color = DESTROY_C
        ticker_push(world, turn, kind, text, color)

    violations, claim_events = sim_engine.step_turn(
        t, tiles, nations=nations, pair_orders=pair_orders,
        currencies=currencies, on_event=on_event, ledger_exempt=True,
        on_phase=on_phase if status_before is not None else None,
    )
    if status_before is not None:
        on_phase('markets')

    if claim_events:
        world['pair_orders'] = [(r, o) for r in tiles for o in tiles if o is not r
                                and r.neighbors.get(o.name) is not None
                                and not getattr(o, 'wilderness', False)
                                and not getattr(r, 'wilderness', False)]

    # Step Sovereign Bond Market (coupons, maturities, defaults)
    try:
        from sovereign_bonds import get_bond_market
        get_bond_market().step(world, t)
    except Exception:
        pass
    if status_before is not None:
        on_phase('bonds')

    # Check for The Great Stink Catalyst Event
    for n in nations:
        cap_tile = getattr(n, 'tiles', [None])[0] if getattr(n, 'tiles', []) else None
        if cap_tile and getattr(cap_tile, 'pollution_water', 0.0) >= 60.0 and not getattr(n, '_great_stink_triggered', False):
            has_sewer = any(getattr(b, 'name', '') == 'trunk_sewer' for b in getattr(cap_tile, 'buildings', []))
            if not has_sewer:
                n._great_stink_triggered = True
                n.legitimacy = max(0.05, getattr(n, 'legitimacy', 0.6) - 0.20)
                ticker_push(
                    world, t, 'ALERT',
                    f"🚨 THE GREAT STINK: Putrid river effluent engulfs Parliament in {cap_tile.name}! Chamber evacuated; {n.name} legitimacy plunges!",
                    (255, 75, 75)
                )
    if status_before is not None:
        on_phase('catalyst')

    world['turn'] = t
    world['currency_totals'] = {c: fx.audit_currency_total(tiles, c)
                                for c in currencies}
    world['violations'] = violations
    if world.get('scenario_id') == 'egypt_1877':
        from scenario_egypt_1877 import advance_scenario
        advance_scenario(world, t, ticker_push, on_phase=on_phase)
        finish_turn(world, t)
    return violations


def step_world_with_warning(world):
    """Pause before advancing into a known high-risk riot or breakdown state."""
    if world.get('scenario_warning_modal') or world.get('scenario_bookend_modal'):
        return False
    if world.get('scenario_id') == 'egypt_1877':
        nation = next((n for n in world.get('nations', [])
                       if n.name == world.get('player_nation_name')), None)
        state = world.get('scenario_state', {})
        if nation is not None and not state.get('ending'):
            unrest = sum(float(getattr(tile, 'unrest_level', 0.0)) for tile in nation.tiles) / max(1, len(nation.tiles))
            legitimacy = float(getattr(nation, 'legitimacy', 0.5))
            if (unrest >= 0.65 or legitimacy <= 0.20) and world.get('crisis_warning_ack_turn') != int(world.get('turn', 0)):
                world['playing'] = False
                world['scenario_warning_modal'] = {
                    'kind': 'political_risk', 'unrest': unrest, 'legitimacy': legitimacy,
                    'preemptive': True,
                }
                return False

    if world.get('crisis_warning_ack_turn') != int(world.get('turn', 0)):
        from unrest import MOB_THRESHOLD, PROTEST_THRESHOLD, unrest_intensities
        candidates = []
        player_only = world.get('scenario_id') == 'egypt_1877'
        nations_at_risk = (n for n in world.get('nations', [])
                           if not player_only or n.name == world.get('player_nation_name'))
        for nation in nations_at_risk:
            for tile in getattr(nation, 'tiles', []):
                history = getattr(tile, 'protest_energy_log', [])
                energy = float(history[-1]) if history else 0.0
                if energy >= PROTEST_THRESHOLD:
                    candidates.append((energy, nation, tile))
        if candidates:
            energy, nation, tile = max(candidates, key=lambda candidate: candidate[0])
            world['playing'] = False
            world['scenario_warning_modal'] = {
                'kind': 'riot_risk', 'nation': nation.name,
                'region': getattr(tile, 'display_name', getattr(tile, 'name', 'district')),
                'region_key': tile.name,
                'energy': energy, 'threshold': MOB_THRESHOLD,
                'riot_chance': unrest_intensities(energy)['mob'],
                'already_mob': energy >= MOB_THRESHOLD,
            }
            return False
    previous_event_count = len(world.get('ticker_events', []))
    step_world(world)
    recent_events = world.get('ticker_events', [])[previous_event_count:]
    if world.get('scenario_id') == 'egypt_1877':
        egypt = next((nation for nation in world.get('nations', [])
                      if nation.name == world.get('player_nation_name')), None)
        locations = ['egypt'] + [name.lower() for tile in getattr(egypt, 'tiles', [])
                                 for name in (tile.name, getattr(tile, 'display_name', tile.name))]
        recent_events = [event for event in recent_events
                         if any(location in str(event.get('text', '')).lower() for location in locations)]
    crisis_event = next((event for event in reversed(recent_events)
                         if any(token in str(event.get('text', '') if isinstance(event, dict) else event).upper()
                                for token in ('BREAD RIOT', 'RIOT', 'REVOLT', 'TAKEOVER'))), None)
    if crisis_event is not None and not world.get('scenario_warning_modal'):
        message = crisis_event.get('text', 'Civil unrest has escalated.') if isinstance(crisis_event, dict) else str(crisis_event)
        affected = next((tile for tile in world.get('tiles', [])
                         if any(name and str(name).lower() in message.lower()
                                for name in (getattr(tile, 'scenario_location', None),
                                             getattr(tile, 'display_name', None), tile.name))), None)
        world['playing'] = False
        world['scenario_warning_modal'] = {'kind': 'riot_event', 'message': message,
                                           'region_key': affected.name if affected else None}
        return False
    return True
