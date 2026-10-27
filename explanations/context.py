"""Freeze the minimum live context at a player request, under the caller's lock."""
from pathlib import Path
import math

from explanations import mechanics

DIMENSIONS = ('good', 'disease', 'class_group', 'cohort', 'base_currency', 'quote_currency')


def capture(world, request, client='desktop'):
    """world is a dict of live objects, accessed only synchronously by the caller."""
    if not isinstance(request, dict):
        raise ValueError('Explanation selection must be an object.')
    turn = request.get('turn')
    if type(turn) is not int or turn < 0 or turn > world.get('turn', 0):
        raise ValueError('Choose an existing completed turn.')
    metric = request.get('metric_id')
    if not isinstance(metric, str) or not 1 <= len(metric) <= 160:
        raise ValueError('Select a statistic with a trace metric ID.')
    entity = request.get('entity', '')
    if not isinstance(entity, str):
        raise ValueError('Invalid entity.')
    kind, _, name = entity.partition(':')
    tiles, nations = world.get('tiles', []), world.get('nations', [])
    tile = next((t for t in tiles if t.name == name), None) if kind in ('tile', 'fx_desk') else None
    nation = next((n for n in nations if n.name == name), None) if kind == 'nation' else getattr(tile, 'owner_nation', None)
    if kind not in ('tile', 'nation', 'fx_desk') or (tile is None and nation is None):
        raise ValueError('Entity is not present in this world.')
    trace = world.get('run_trace')
    if trace is None:
        raise ValueError('Causal recording is disabled for this run.')
    if trace.write_error:
        raise ValueError('Causal recording failed; inspect recorded evidence before requesting a narrative.')
    trace.publish()
    published = trace._compact_writer.end_offset
    boundary = request.get('boundary')
    if boundary is None:
        boundary = published
    if type(boundary) is not int or not 0 < boundary <= published:
        raise ValueError('Invalid published evidence boundary.')
    subject = {'type': kind, 'id': name}
    dimensions = request.get('dimensions', {})
    if not isinstance(dimensions, dict) or len(dimensions) > 16:
        raise ValueError('Invalid stat dimensions.')
    for key, value in dimensions.items():
        if (not isinstance(key, str) or not 1 <= len(key) <= 100
                or key in ('type', 'id') or type(value) not in (str, int, float, bool, type(None))
                or (type(value) is float and not math.isfinite(value))
                or (isinstance(value, str) and len(value) > 100)):
            raise ValueError('Invalid stat dimension.')
        subject[key] = value
    for key in DIMENSIONS:
        if request.get(key) is not None:
            if not isinstance(request[key], str) or len(request[key]) > 100:
                raise ValueError('Invalid stat dimension.')
            subject[key] = request[key]
    display = request.get('display')
    if display is not None and (not isinstance(display, str) or len(display) > 300):
        raise ValueError('Invalid display context.')
    epoch = request.get('epoch')
    if epoch is not None and (type(epoch) is not int or epoch < 0):
        raise ValueError('Invalid evidence epoch.')
    selection = {'run_id': trace.run_id, 'branch_id': trace.branch_id, 'turn': turn, 'subject': subject,
                 'metric_id': metric, 'boundary': boundary, 'client': client,
                 'epoch': epoch, 'display': display, 'locale': 'en', 'detail': 'short'}
    era = 1877 if world.get('scenario_id') == 'egypt_1877' else None
    return {'selection': selection, 'trace_path': str(Path(trace.path).resolve()),
            'boundary_explicit': request.get('boundary') is not None,
            'boundary': boundary, 'scenario': world.get('scenario_id'),
            'nation': getattr(nation, 'name', None), 'era': era,
            'action_context_turn': world.get('turn'),
            'actions': mechanics.snapshot(nation, tile, client),
            'catalog_coverage': mechanics.COVERAGE}


def capture_server(sim, request):
    with sim._lock:
        expected = request.get('run_id')
        trace = sim.run_trace
        if expected is not None and (trace is None or expected != trace.run_id):
            raise ValueError('The selected world has changed. Reopen the explainer.')
        return capture({'tiles': sim.tiles, 'nations': sim.nations,
                        'turn': sim.turn, 'run_trace': trace,
                        'scenario_id': sim.scenario_id}, request, 'web')
