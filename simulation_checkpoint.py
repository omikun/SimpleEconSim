"""Atomic local simulation saves paired with immutable, verified trace prefixes.

Checkpoints are trusted local Python state, never a network upload format. Map
presets remain separate. A restore activates process-global simulation registries
and must replace the active simulation; concurrent worlds are not supported by
those existing registries. Every restore forks without modifying the parent.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
from enum import Enum
import importlib
import io
import json
import os
from pathlib import Path
import pickle
import platform
import random
import sys
import types
import uuid
from contextlib import contextmanager

import numpy as np

from run_trace import verify
from trace_codec import iter_records, CorruptTrace, TornTraceTail
from python_code_signature import code_signature

VERSION = 1
ROOT = Path(__file__).resolve().parent
# Runtime services are recreated by their owners; their gameplay objects and
# account state are already retained through the simulation graph.
SERVICE_PREFIXES = ('client.', 'render_engine', 'worldview', 'test_', 'logger',
                    'simulation_checkpoint', 'trace_', 'run_trace', 'causal_gap_inventory')


@contextmanager
def _graph_recursion_budget(limit=20000):
    """Bounded depth for the authored 1,000-cell cyclic native map graph."""
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(max(previous, limit))
        yield
    finally:
        sys.setrecursionlimit(previous)


def _modules():
    for name, module in sorted(tuple(sys.modules.items())):
        filename = getattr(module, '__file__', None)
        if (name == '__main__' or name.startswith('test_') or not filename
                or not filename.endswith('.py')):
            continue
        path = Path(filename).resolve()
        if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / 'venv'):
            yield name, module, path


def _assigned(body):
    """Assignments at module/class scope, including conditional initialization."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for child in ast.walk(target):
                    if isinstance(child, ast.Name):
                        yield child.id
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, ast.expr):
                yield from _assigned([child])


def _runtime_value(value):
    return not (isinstance(value, (types.ModuleType, type, property, staticmethod, classmethod))
                or callable(value))


def capture_globals():
    values = {}; sources = {}
    for name, module, path in _modules():
        source = path.read_bytes()
        sources[name] = hashlib.sha256(source).hexdigest()
        if name.startswith(SERVICE_PREFIXES):
            continue
        tree = ast.parse(source)
        names = set(_assigned(tree.body))
        names.update(field for node in ast.walk(tree) if isinstance(node, ast.Global) for field in node.names)
        for field in sorted(names):
            if field in vars(module) and _runtime_value(vars(module)[field]):
                values[name, '', field] = vars(module)[field]
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            cls = getattr(module, node.name, None)
            if not isinstance(cls, type) or issubclass(cls, Enum):
                continue
            for field in sorted(set(_assigned(node.body))):
                if field in vars(cls) and _runtime_value(vars(cls)[field]):
                    values[name, node.name, field] = vars(cls)[field]
    # Imported mutable aliases must continue to reference the same restored
    # recipes, government lists, random cache and registries after unpickling.
    identities = {id(value): value for value in values.values()
                  if not isinstance(value, (str, bytes, int, float, bool, tuple, frozenset, type(None)))}
    for name, module, _ in _modules():
        if name.startswith(SERVICE_PREFIXES):
            continue
        for field, value in vars(module).items():
            if id(value) in identities:
                values[name, '', field] = value
    return values, sources


def _restore_globals(values):
    for (name, class_name, field), value in values.items():
        target = importlib.import_module(name)
        if class_name:
            target = getattr(target, class_name)
        setattr(target, field, value)


def _restore_native_callback(operator_id, field, name, digest):
    from economy.transformation_graph import TransformationGraph
    function = getattr(TransformationGraph.get_operator(operator_id), field)
    if (function.__qualname__ != name or function.__closure__
            or code_signature(function.__code__) != digest):
        raise ValueError('checkpoint native action function mismatch: ' + operator_id)
    return function


class _NativeCallbackReducers:
    def reducer_override(self, value):
        if isinstance(value, types.FunctionType) and '<locals>' in value.__qualname__:
            # These native ontology callbacks have no closures. Resolve them
            # from the exact validated rules, preserving mutable operator state
            # in the ordinary pickle graph rather than dropping the registry.
            from economy.transformation_graph import TransformationGraph
            for operator in TransformationGraph.all_operators():
                for field in ('on_execute', 'check_prerequisites', 'estimate_return_hook'):
                    if getattr(operator, field) is value and not value.__closure__:
                        digest = code_signature(value.__code__)
                        return _restore_native_callback, (operator.id, field, value.__qualname__, digest)
        return NotImplemented


class CheckpointPickler(_NativeCallbackReducers, pickle.Pickler):
    pass


class _DeepGraphPickler(_NativeCallbackReducers, pickle._Pickler):
    """Heap-backed Python frames for maps deeper than the C pickler permits.

    The artifact remains ordinary version-pinned protocol-5 pickle. Using the
    Python implementation for this fallback avoids raising the C stack budget
    for the large linked geometry graph.
    """


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(path, data):
    """Publish a new immutable file; an interrupted temp file is never a save."""
    temporary = path.with_name(path.name + '.pending-' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _copy_prefix(source, target, boundary):
    with Path(source).open('rb') as incoming, target.open('xb') as outgoing:
        remaining = boundary
        while remaining:
            block = incoming.read(min(1024 * 1024, remaining))
            if not block:
                raise TornTraceTail('source ended before saved boundary')
            outgoing.write(block)
            remaining -= len(block)
        outgoing.flush()
        os.fsync(outgoing.fileno())


def save(server, directory):
    """Return a new manifest only after its state and trace pair are durable."""
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with server._lock:
        trace = server.run_trace
        if trace is None:
            raise ValueError('a full causal checkpoint requires an enabled recorder')
        if trace.write_error:
            raise OSError(trace.write_error)
        clock = server.tiles[0]._collective_trace_clock
        if clock.get('command_event_id') or getattr(trace.treasury_book, '_composition_depth', 0):
            raise RuntimeError('checkpoint requires a completed simulation/command boundary')
        trace.checkpoint(clock)
        if trace.write_error:
            raise OSError(trace.write_error)
        boundary = trace._compact_writer.end_offset
        globals_state, sources = capture_globals()
        state = {'server': server, 'globals': globals_state,
                 'region_addresses': {id(tile): tile for tile in server.tiles},
                 'python_rng': random.getstate(), 'numpy_rng': np.random.get_state()}
        # Fail before publishing a manifest if any active gameplay state is not
        # serializable. No economic registry is silently dropped on failure.
        buffer = io.BytesIO()
        try:
            with _graph_recursion_budget():
                CheckpointPickler(buffer, protocol=5).dump(state)
        except RecursionError:
            buffer = io.BytesIO()
            with _graph_recursion_budget(100000):
                _DeepGraphPickler(buffer, protocol=5).dump(state)
        payload = buffer.getvalue()
        identity = uuid.uuid4().hex
        state_path = directory / (identity + '.state')
        trace_path = directory / (identity + '.ctr')
        _copy_prefix(trace.path, trace_path, boundary)
        checked = verify(trace_path)
        if checked['rows'] != trace.count or checked['sha256'] != trace.digest:
            raise CorruptTrace('checkpoint trace does not match live recorder state')
        _publish(state_path, payload)
        manifest = {'version': VERSION, 'python': platform.python_version(),
                    'numpy': np.__version__, 'sources': sources,
                    'run_id': trace.run_id, 'branch_id': trace.branch_id,
                    'turn': server.turn, 'epoch': clock.get('epoch', 0),
                    'next_sequence': clock['next'], 'trace_bytes': boundary,
                    'trace_rows': trace.count, 'trace_sha256': trace.digest,
                    'trace_file': trace_path.name, 'state_file': state_path.name,
                    'state_sha256': hashlib.sha256(payload).hexdigest()}
        manifest_path = directory / (identity + '.checkpoint.json')
        _publish(manifest_path, json.dumps(manifest, sort_keys=True, indent=2).encode())
        return manifest_path


def restore(manifest_path, branch_directory):
    """Verify a committed pair and fork; the original source is never changed."""
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    if (manifest['version'] != VERSION or manifest['python'] != platform.python_version()
            or manifest['numpy'] != np.__version__):
        raise ValueError('unsupported checkpoint runtime/version')
    for name, digest in manifest['sources'].items():
        module = importlib.import_module(name)
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != digest:
            raise ValueError('checkpoint rule/source mismatch: ' + name)
    def artifact(field):
        name = manifest[field]
        if Path(name).name != name:
            raise ValueError('invalid checkpoint artifact name')
        return manifest_path.parent / name
    saved_trace = artifact('trace_file')
    # Validate the exact saved boundary, not a best-effort prefix. An incomplete
    # uncommitted live tail is handled by choosing this immutable saved pair.
    if saved_trace.stat().st_size != manifest['trace_bytes']:
        raise CorruptTrace('checkpoint trace boundary mismatch')
    checked = verify(saved_trace)
    if checked['rows'] != manifest['trace_rows'] or checked['sha256'] != manifest['trace_sha256']:
        raise CorruptTrace('checkpoint trace digest/count mismatch')
    payload = artifact('state_file').read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest['state_sha256']:
        raise ValueError('checkpoint state digest mismatch')
    with _graph_recursion_budget():
        state = pickle.loads(payload)
    server = state['server']
    trace = server.run_trace
    clock = server.tiles[0]._collective_trace_clock
    if (trace.run_id != manifest['run_id'] or trace.count != manifest['trace_rows']
            or trace.digest != manifest['trace_sha256'] or server.turn != manifest['turn']
            or clock['next'] != manifest['next_sequence']):
        raise ValueError('checkpoint simulation/trace pair mismatch')
    branch_id = uuid.uuid4().hex
    directory = Path(branch_directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    branch_path = directory / (trace.run_id + '-' + branch_id + '.ctr')
    _copy_prefix(saved_trace, branch_path, manifest['trace_bytes'])
    trace.rebind(branch_path, branch_id)
    for old_address, tile in state['region_addresses'].items():
        planner = getattr(tile, 'elite_planner', None)
        cache = getattr(planner, '_last_market_novelty_trace', None)
        if cache is not None and old_address in cache:
            cache[id(tile)] = cache.pop(old_address)
    _restore_globals(state['globals'])
    random.setstate(state['python_rng'])
    np.random.set_state(state['numpy_rng'])
    trace.emit(clock, kind='branch_restored', record_class='audit', phase='checkpoint',
               inputs={'parent_run_id': manifest['run_id'], 'parent_branch_id': manifest['branch_id'],
                       'parent_sha256': manifest['trace_sha256'], 'parent_rows': manifest['trace_rows'],
                       'parent_bytes': manifest['trace_bytes'], 'checkpoint': manifest_path.name})
    return server


def recover(manifest_path, damaged_trace, branch_directory):
    """Recover a saved pair after a torn live tail; reject interior corruption."""
    manifest = json.loads(Path(manifest_path).read_text())
    boundary = manifest['trace_bytes']
    prefix_digest = '0' * 64
    prefix_rows = 0
    torn = None; complete_end = 0
    try:
        for record in iter_records(damaged_trace):
            complete_end = record.end_offset
            if record.end_offset <= boundary:
                prefix_digest = hashlib.sha256((prefix_digest + record.payload).encode()).hexdigest()
                prefix_rows += 1
    except TornTraceTail as error:
        torn = str(error)
    if prefix_rows != manifest['trace_rows'] or prefix_digest != manifest['trace_sha256']:
        raise CorruptTrace('damaged trace does not contain the saved checkpoint prefix')
    server = restore(manifest_path, branch_directory)
    report = {'damaged_artifact': str(Path(damaged_trace).resolve()), 'preserved': True,
              'saved_boundary': boundary, 'last_complete_record_end': complete_end,
              'discarded_tail_bytes': Path(damaged_trace).stat().st_size - boundary,
              'torn_tail': torn, 'restored_turn': server.turn}
    server.run_trace.emit(server.tiles[0]._collective_trace_clock,
                          kind='checkpoint_recovery', record_class='audit', phase='checkpoint', inputs=report)
    return server, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', type=Path)
    parser.add_argument('--recover-trace', type=Path)
    parser.add_argument('--directory', type=Path, default=Path('tmp/checkpoints'))
    parser.add_argument('--turns', type=int, default=1)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--scenario', choices=('default', 'labor_frontier_rivalry',
                                              'supply_rivalry', 'egypt_1877'), default='default')
    args = parser.parse_args()
    if args.recover_trace and not args.restore:
        parser.error('--recover-trace requires --restore')
    if args.restore:
        if args.recover_trace:
            server, report = recover(args.restore, args.recover_trace, args.directory)
            print(json.dumps(report, sort_keys=True))
        else:
            server = restore(args.restore, args.directory)
    else:
        seed = args.seed if args.seed is not None else {
            'default':4242, 'labor_frontier_rivalry':612, 'supply_rivalry':812,
            'egypt_1877':1877}[args.scenario]
        if args.scenario == 'egypt_1877':
            from world_config import set_map_topology
            from worldview_engine import build_world_view
            from native_simulation_checkpoint import NativeSimulation
            set_map_topology('voronoi')
            world = build_world_view(seed=seed, terrain_seed=seed, nation_seed=seed,
                                     scenario_id=args.scenario)
            server = NativeSimulation(world)
        else:
            from sim_server.sim_server import SimServer
            server = SimServer(seed=seed, terrain_seed=seed, nation_seed=seed,
                               scenario_id=None if args.scenario=='default' else args.scenario,
                               topology='voronoi' if args.scenario=='default' else 'hex')
    for _ in range(args.turns):
        server.step()
    from native_simulation_checkpoint import NativeSimulation, save_world
    print(save_world(server.world, args.directory, engine_module=server.engine_module)
          if isinstance(server, NativeSimulation) else save(server, args.directory))


if __name__ == '__main__':
    from simulation_checkpoint import main
    main()
