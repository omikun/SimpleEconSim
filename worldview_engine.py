"""
Simulation stepping, event ticking, and world state initialization for worldview.
"""

import random
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


def build_world_view(seed=None, terrain_seed=None, nation_seed=None, scenario_id=None):
    """Build the 9x9 hex world + prepare viewer state."""
    from scenario_egypt_1877 import SCENARIO, is_scenario_id
    if is_scenario_id(scenario_id):
        seeds = SCENARIO['seeds']
        seed = seeds['world'] if seed is None else seed
        terrain_seed = seeds['terrain'] if terrain_seed is None else terrain_seed
        nation_seed = seeds['nations'] if nation_seed is None else nation_seed
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


def step_world(world):
    """Advance one turn of the engine via sim_engine."""
    if world.get('scenario_id') == 'egypt_1877' and world.get('scenario_state', {}).get('ending'):
        world['playing'] = False
        return world.get('violations', [])
    t = world['turn'] + 1
    tiles = world['tiles']
    currencies = world['currencies']
    nations = world['nations']
    pair_orders = world['pair_orders']

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
        currencies=currencies, on_event=on_event, ledger_exempt=True
    )

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

    world['turn'] = t
    world['currency_totals'] = {c: fx.audit_currency_total(tiles, c)
                                for c in currencies}
    world['violations'] = violations
    if world.get('scenario_id') == 'egypt_1877':
        from scenario_egypt_1877 import advance_scenario
        advance_scenario(world, t, ticker_push)
    return violations
