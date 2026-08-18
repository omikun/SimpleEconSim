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


def get_layout():
    return rectangular_hex_layout(GRID_ROWS, GRID_COLS)


def get_reverse_layout():
    return {v: k for k, v in get_layout().items()}


def build_world_view(seed=None):
    """Build the 9x9 hex world + prepare viewer state."""
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()
    tiles, nations, _grid = build_world(seed=seed)
    currencies = [n.currency for n in nations]
    layout = get_layout()
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
        'reverse': get_reverse_layout(),
        'bbox': hex_bbox(layout, HEX_SIZE),
        'cam': {'ox': 0.0, 'oy': 0.0, 'zoom': 1.0},
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
    }
    reset_cam(world)
    return world


def ticker_push(world, t, kind, text, color, n=140):
    world['ticker_events'].append({'t': t, 'kind': kind, 'text': text,
                                   'color': color})
    if len(world['ticker_events']) > n:
        del world['ticker_events'][:len(world['ticker_events']) - n]


def step_world(world):
    """Advance one turn of the engine via sim_engine."""
    t = world['turn'] + 1
    tiles = world['tiles']
    currencies = world['currencies']
    nations = world['nations']
    pair_orders = world['pair_orders']

    def on_event(turn, kind, text):
        color = MIG_C if kind == 'MIGRATE' else CLAIM_C if kind == 'CLAIM' else DESTROY_C
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

    world['turn'] = t
    world['currency_totals'] = {c: fx.audit_currency_total(tiles, c)
                                for c in currencies}
    world['violations'] = violations
    return violations
