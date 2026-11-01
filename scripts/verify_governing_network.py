"""Compare full native economic state with society observations off and on.

Run from the workspace: venv/bin/python -m scripts.verify_governing_network.
Each route runs in a fresh process because the economy owns global registries.
Uses the repository's canonical economic graph. The observation sidecar is
excluded, and the exact native trace run UUID is relabeled consistently while
retaining event/operation suffixes, ordering, balances and every RNG value.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import gzip
import importlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def economic_digest(world, graph_output=None):
    from governing_network import KEY
    from simulation_semantics import canonical_state, state_digest
    sidecar = world['scenario_state'].pop(KEY, None)
    try:
        state = canonical_state(world['tiles'], world['nations'], extra={
            'turn': world['turn'], 'scenario_state': world['scenario_state'],
            'currencies': world['currencies'], 'pair_orders': world['pair_orders'],
            'currency_totals': world['currency_totals'], 'violations': world['violations'],
            'player_nation_name': world['player_nation_name'],
        })
        trace = world.get('run_trace')
        if trace is not None:
            normalize_trace_identity(state['graph'], trace.run_id)
        if graph_output is not None:
            graph_output.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(graph_output, 'wt') as output:
                json.dump(state['graph'], output)
        return state_digest(state)
    finally:
        if sidecar is not None:
            world['scenario_state'][KEY] = sidecar


def normalize_trace_identity(graph, run_id):
    """Fresh native recorders have UUID identities unrelated to gameplay.

    Replace only the known recorder's exact identity, not arbitrary UUIDs or
    event sequence numbers. Nothing in the live world or its trace is edited.
    """
    todo = [graph]
    while todo:
        value = todo.pop()
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str):
                    value[key] = item.replace(run_id, 'verification-native-run')
                elif isinstance(item, (dict, list)):
                    todo.append(item)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    value[index] = item.replace(run_id, 'verification-native-run')
                elif isinstance(item, (dict, list)):
                    todo.append(item)


def sampled_digest(world):
    from trace_snapshots import sample
    values = sample(world['tiles'], world['nations'], full=True)
    rows = sorted((list(key), value) for key, value in values.items())
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()


def run_campaign(engine_name, mode, route, steps, traced, graph_output=None):
    import numpy as np
    from world_config import set_map_topology
    from random_cache import rand
    from scenario_egypt_1877 import apply_action
    from governing_network import project, KEY
    # Import dependent modules before setting the gameplay RNG, as in native
    # campaign regression tests. Use the authored terrain, not a mock economy.
    engine = importlib.import_module(engine_name)
    set_map_topology('voronoi')
    random.seed(1877)
    np.random.seed(1877)
    world = engine.build_world_view(scenario_id='egypt_1877',
                                    governing_network_mode=mode, trace_enabled=traced)
    random.seed(1877)
    np.random.seed(1877)
    rand._idx = rand._capacity
    state = world['scenario_state']
    observations, decisions, digests = [], [], []
    policies = {
        1: 'release_maize',
        2: {'buy': 'buy_private_grain', 'requisition': 'requisition_private_grain',
            'market': 'open_private_grain_market'}[route],
        3: 'release_maize' if route != 'market' else 'reduce_fellahin_tax',
    }
    digests.append(dict(turn=int(world['turn']), sampled=sampled_digest(world)))
    for _ in range(steps):
        turn = int(world['turn'])
        decision = policies.get(turn)
        if (turn >= state['payment_window_turn']
                and state['payment_status'] in ('upcoming', 'unpaid', 'deferred')):
            egypt = next(n for n in world['nations'] if n.name == 'Egypt')
            decision = ('pay_remittance' if egypt.government.agent.cash >= state['scheduled_remittance']
                        else 'defer_remittance' if state.get('deferral_count', 0) == 0
                        else 'default_remittance')
        if decision:
            ok, message = apply_action(world, decision)
            # The route records unavailable actions honestly; failure grants no
            # meal or observation reward, and the two modes must fail alike.
            decisions.append(dict(turn=turn, action=decision, success=ok, message=message))
        engine.step_world(world)
        digests.append(dict(turn=int(world['turn']), sampled=sampled_digest(world)))
        if mode == 'observe':
            info = project(world)
            # Full member IDs stay in the saved sidecar and canonical economic
            # graph. Keep this human-readable route report compact.
            for community in info['communities']:
                community.pop('member_ids')
            observations.append(info)
        if state.get('ending'):
            break
    shadow = state.get(KEY)
    diagnostic_digest = None
    if shadow is not None:
        diagnostic_digest = hashlib.sha256(json.dumps(
            dict(nodes=shadow['nodes'], diagnostics=shadow['diagnostics'],
                 inputs=[row['inputs'] for row in shadow['history']]),
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return dict(engine=engine_name, mode=mode, route=route, traced=traced,
                steps=steps, digests=digests, decisions=decisions,
                observations=observations, diagnostic_digest=diagnostic_digest,
                economic_final=economic_digest(world, graph_output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/governing_network/verification.json')
    parser.add_argument('--steps', type=int, default=7)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--engine', default='client.desktop.engine', help=argparse.SUPPRESS)
    parser.add_argument('--mode', default='off', help=argparse.SUPPRESS)
    parser.add_argument('--route', default='buy', help=argparse.SUPPRESS)
    parser.add_argument('--traced', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--graph-output', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.steps < 1:
        parser.error('--steps must be positive')
    if args.worker:
        result = run_campaign(args.engine, args.mode, args.route, args.steps, args.traced, args.graph_output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        return
    comparisons, runs = [], []
    environment = dict(os.environ, PYTHONPATH=str(ROOT), SDL_VIDEODRIVER='dummy',
                       SDL_AUDIODRIVER='dummy', MPLCONFIGDIR='/private/tmp/regnum-mpl', PYTHONHASHSEED='0')
    with tempfile.TemporaryDirectory() as directory:
        for engine in ('client.desktop.engine', 'worldview_engine'):
            for route in ('buy', 'requisition', 'market'):
                for traced in (False, True):
                    def run_one(mode):
                        output = Path(directory) / f'{mode}.json'
                        command = [sys.executable, '-m', 'scripts.verify_governing_network',
                                   '--worker', '--engine', engine, '--mode', mode, '--route', route,
                                   '--steps', str(args.steps), '--output', str(output)]
                        if traced:
                            command.append('--traced')
                        completed = subprocess.run(command, cwd=ROOT, env=environment,
                                                   text=True, capture_output=True)
                        if completed.returncode:
                            raise RuntimeError(completed.stdout + completed.stderr)
                        return json.loads(output.read_text())
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        paired = list(executor.map(run_one, ('off', 'observe')))
                    off, observed = paired
                    sampled_equal = off['digests'] == observed['digests']
                    economic_equal = off['economic_final'] == observed['economic_final']
                    decisions_equal = off['decisions'] == observed['decisions']
                    equal = sampled_equal and economic_equal and decisions_equal
                    comparisons.append(dict(engine=engine, route=route, traced=traced,
                                            equal=equal, turn_count=len(off['digests']),
                                            sampled_equal=sampled_equal, economic_equal=economic_equal,
                                            decisions_equal=decisions_equal))
                    runs.append(observed)
                    print(f'{engine} / {route} / trace={traced}: {"PASS" if equal else "FAIL"}', flush=True)
    diagnostic_parity = []
    for engine in ('client.desktop.engine', 'worldview_engine'):
        for route in ('buy', 'requisition', 'market'):
            matches = [r for r in runs if r['engine'] == engine and r['route'] == route]
            diagnostic_parity.append(dict(engine=engine, route=route,
                                          equal=matches[0]['diagnostic_digest'] == matches[1]['diagnostic_digest']))
    report = dict(schema_version=1, mode='read_only_observation', comparisons=comparisons,
                  normalization='Repository canonical graph; exclude observation sidecar; relabel exact recorder run UUID only.',
                  traced_untraced_diagnostics=diagnostic_parity, runs=runs,
                  passed=all(row['equal'] for row in comparisons + diagnostic_parity))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    if not report['passed']:
        raise SystemExit('Society observation parity failed; inspect ' + str(args.output))
    print('Full-state observation parity passed: ' + str(args.output), flush=True)


if __name__ == '__main__':
    main()
