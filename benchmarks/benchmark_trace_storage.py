"""Compare native legacy, packed, and checked-coverage trace storage.

Run configurations in separate sequential processes with PYTHONHASHSEED=0.
Timings exclude map generation, evidence lookup, and equivalence hashing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import time
from types import SimpleNamespace


def normalized_evidence(row, run_id, identities):
    """Normalize identities inside strings, never numeric economic values."""
    def visit(value):
        if isinstance(value, str):
            return re.sub(r'(?<![a-z0-9])[0-9a-f]{8}(?![a-z0-9])',
                lambda match: identities.setdefault(match[0], 'UUID' + str(len(identities))),
                value.replace(run_id, 'RUN'))
        if isinstance(value, dict):
            return {visit(key): visit(value[key]) for key in sorted(value)}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value
    row = {key: value for key, value in row.items() if key not in ('sha256_before', 'digest_scope')}
    return json.dumps(visit(row), sort_keys=True, separators=(',', ':'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('legacy', 'packed', 'coverage'), required=True)
    parser.add_argument('--seed', type=int, default=777)
    parser.add_argument('--turns', type=int, default=3)
    parser.add_argument('--scenario', choices=('egypt_1877',))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ['COC_TRACE_STORAGE'] = 'legacy' if args.mode == 'legacy' else 'packed'
    os.environ['COC_TRACE_SPARSE'] = '1' if args.mode == 'coverage' else '0'
    from client.worldview.worldview_engine import build_world_view, step_world
    from simulation_semantics import normalized_metrics
    from trace_codec import iter_records, storage_stats
    from run_trace import verify
    import numpy as np

    np.random.seed(args.seed)
    world = build_world_view(seed=args.seed, terrain_seed=args.seed, nation_seed=args.seed,
                             **({'scenario_id': args.scenario} if args.scenario else {}))
    trace = world['run_trace']
    try:
        timings = []
        for _ in range(args.turns):
            start = time.perf_counter(); step_world(world); seconds = time.perf_counter() - start
            timings.append(seconds)
            print(json.dumps({'mode': args.mode, 'turn': world['turn'], 'seconds': seconds,
                              'logical_records': trace.count}), flush=True)
        trace.publish()
        metrics = normalized_metrics(SimpleNamespace(tiles=world['tiles'], nations=world['nations']))
        metrics_digest = hashlib.sha256(json.dumps(sorted(metrics.items()), sort_keys=True).encode()).hexdigest()
        python_rng = hashlib.sha256(repr(random.getstate()).encode()).hexdigest()
        numpy_rng = hashlib.sha256(repr(np.random.get_state()).encode()).hexdigest()
        evidence = hashlib.sha256(); identities = {}
        for record in iter_records(trace.path):
            row = dict(record.row) if record.row is not None else json.loads(record.payload)
            if row.get('record_class') == 'metadata': continue
            payload = normalized_evidence(row, trace.run_id, identities)
            evidence.update(payload.encode())
        from trace_index import TraceIndex
        index = TraceIndex(trace.path)
        start = time.perf_counter()
        options = index.available_metrics(turn=world['turn'], subject={'type': 'tile', 'id': world['tiles'][0].name})
        cold = time.perf_counter() - start
        start = time.perf_counter()
        again = index.available_metrics(turn=world['turn'], subject={'type': 'tile', 'id': world['tiles'][0].name})
        warm = time.perf_counter() - start
        assert options == again
        report = {'mode': args.mode, 'seed': args.seed, 'scenario': world.get('scenario_id'),
                  'turns': timings, 'tiles': len(world['tiles']),
                  'stats': storage_stats(trace.path), 'trace': str(trace.path), 'integrity': verify(trace.path),
                  'metrics_digest': metrics_digest, 'evidence_digest': evidence.hexdigest(),
                  'python_rng_digest': python_rng, 'numpy_rng_digest': numpy_rng,
                  'catalog_cold_seconds': cold, 'catalog_warm_seconds': warm, 'catalog_options': len(options),
                  'normalization': 'Run/operation identities and format-specific checkpoint digest metadata only.'}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
    finally:
        trace._compact_writer.close()


if __name__ == '__main__': main()
