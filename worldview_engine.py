"""
Simulation stepping, event ticking, and world state initialization for worldview.
"""

import random
from goods import Goods
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade
from regime import step_regime
from migration import run_migrations
from trade_settle import settle_wilderness
from claims import check_and_apply_claims
from hexmap import rectangular_hex_layout, hex_bbox
import ledger
from sim_world import build_world, GRID_ROWS, GRID_COLS
from worldview_camera import HEX_SIZE, clamp_cam
from worldview_charts import MIG_C
from worldview_map import ACCENT as CLAIM_C, RED as DESTROY_C


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
    clamp_cam(world)
    return world


def ticker_push(world, t, kind, text, color, n=140):
    world['ticker_events'].append({'t': t, 'kind': kind, 'text': text,
                                   'color': color})
    if len(world['ticker_events']) > n:
        del world['ticker_events'][:len(world['ticker_events']) - n]


def step_world(world):
    """Advance one turn of the engine; mirrors sim_world.main() turn body."""
    t = world['turn'] + 1
    tiles = world['tiles']
    currencies = world['currencies']
    violations = []

    curr_before = {c: fx.audit_currency_total(tiles, c) for c in currencies}
    pair_orders = world['pair_orders']

    for r in tiles:
        pending = {}
        for other in tiles:
            if other is r or other not in r.neighbors.values():
                continue
            for g, entries in pending_imports(r, other).items():
                pending.setdefault(g, []).extend(entries)
        r.pending_imports = pending
        r._auction_import_sales = {}

    _provinces = [p for n in world['nations']
                  for p in getattr(n, 'provinces', [])]
    _prov_tiles = {}
    for p in _provinces:
        for r in p.tiles:
            _prov_tiles[r.name] = r
    for p in _provinces:
        p.step(t)
    for r in tiles:
        if r.name in _prov_tiles:
            continue
        r.step(t)

    for r in tiles:
        for rt in r._all_routes():
            rt.advance()
            rt.deliver_pending()

    resolve_parked(tiles)

    for r, other in pair_orders:
        settle_trade(t, other, r)

    fx.cycle_all_markets(tiles, t)

    mig_events = run_migrations(t, tiles)
    for ev in mig_events:
        ticker_push(world, t, 'MIGRATE',
                    f"MIGRATE a{ev['agent_id']} {ev['from']} -> {ev['to']} "
                    f"({ev['via']})", MIG_C)

    claim_events = check_and_apply_claims(t, tiles, world['nations'])
    for ev in claim_events:
        ticker_push(world, t, 'CLAIM',
                    f"CLAIM {ev['nation']} claimed {ev['tile']} "
                    f"({ev['origin_count']}/{ev['pop']} {ev['share']*100:.1f}%)",
                    CLAIM_C)
    if claim_events:
        world['pair_orders'] = [(r, o) for r in tiles for o in tiles if o is not r
                                and r.neighbors.get(o.name) is not None
                                and not getattr(o, 'wilderness', False)
                                and not getattr(r, 'wilderness', False)]

    for r in tiles:
        if getattr(r, 'owner_nation', None) is None or not r.trader_agents:
            continue
        for other in r.neighbors.values():
            if not getattr(other, 'wilderness', False):
                continue
            if not any(getattr(a, 'is_homesteader', False) for a in other.agents):
                continue
            for trader in r.trader_agents:
                settle_wilderness(trader, other, t)

    for n in world['nations']:
        step_regime(n, t)

    for r, other in world['pair_orders']:
        desk = r.forex_desks.get(other.name)
        if desk is not None:
            ppp = max(0.1, other.cost_of_living) / max(0.1, r.cost_of_living)
            desk.update(0, bank=r.bank, fx_regime='managed', ppp_target=ppp)
            if getattr(r, 'destination_region', None) is other:
                desk.save_rate(r)

    for c in currencies:
        delta = fx.audit_currency_total(tiles, c) - curr_before[c]
        recorded = ledger.cleared(t, c)
        unaccounted = delta + recorded
        if abs(unaccounted) > 5.0:
            violations.append((t, c, unaccounted))

    for ev in ledger.all_events():
        if ev['t'] != t:
            continue
        ticker_push(world, t, 'DESTROY',
                    f"DESTROY {ev['currency'] or '-'} ${ev['amount']:.2f} "
                    f"({ev['reason']})", DESTROY_C)

    for r in tiles:
        for other in tiles:
            if other is r or other not in r.neighbors.values():
                continue
            turn_export = sum(r.export_val[g][-1]
                              for g in [Goods.food, Goods.wood, Goods.furniture]
                              if r.export_val[g])
            turn_import = sum(r.import_val[g][-1]
                              for g in [Goods.food, Goods.wood, Goods.furniture]
                              if r.import_val[g])
            r.cumulative_trade_balance += (turn_export - turn_import)
            r.trade_flow_log.append(turn_export - turn_import)

    world['turn'] = t
    world['currency_totals'] = {c: fx.audit_currency_total(tiles, c)
                                for c in currencies}
    world['violations'] = violations
    return violations
