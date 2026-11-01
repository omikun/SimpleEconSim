"""Compare active policy routes, recording parity and fresh-process replay."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from scripts.verify_governing_network import ROOT, run_campaign


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps', type=int, default=19)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/governing_network/governing-verification.json')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--engine', default='client.desktop.engine', help=argparse.SUPPRESS)
    parser.add_argument('--route', default='buy', help=argparse.SUPPRESS)
    parser.add_argument('--traced', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        result = run_campaign(args.engine, 'governing', args.route, args.steps, args.traced)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        return
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONHASHSEED='0',
               SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', MPLCONFIGDIR='/private/tmp/regnum-mpl')
    jobs = [(engine, route, traced) for engine in ('client.desktop.engine', 'worldview_engine')
            for route in ('buy', 'requisition', 'market') for traced in (False, True)]
    jobs.append(('client.desktop.engine', 'buy', False))
    with tempfile.TemporaryDirectory() as directory:
        def run_job(job):
            index, (engine, route, traced) = job
            output = Path(directory) / f'{index}.json'
            command = [sys.executable, '-m', 'scripts.verify_governing_campaign', '--worker',
                       '--engine', engine, '--route', route, '--steps', str(args.steps), '--output', str(output)]
            if traced:
                command.append('--traced')
            completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
            if completed.returncode:
                raise RuntimeError(completed.stdout + completed.stderr)
            print(f'{engine} / {route} / recording={traced}: completed', flush=True)
            return json.loads(output.read_text())
        with ThreadPoolExecutor(max_workers=2) as executor:
            runs = list(executor.map(run_job, enumerate(jobs)))
    checks = []
    for engine in ('client.desktop.engine', 'worldview_engine'):
        for route in ('buy', 'requisition', 'market'):
            a, b = [r for r in runs[:12] if r['engine'] == engine and r['route'] == route]
            checks.append(dict(engine=engine, route=route,
                               sampled_equal=a['digests'] == b['digests'],
                               presentation_equal=a['observations'] == b['observations'],
                               network_equal=a['diagnostic_digest'] == b['diagnostic_digest'],
                               notices_equal=a['notices'] == b['notices'],
                               outcome_equal=a['campaign_outcome'] == b['campaign_outcome'],
                               decisions_equal=a['decisions'] == b['decisions']))
    replay = {key: runs[0][key] == runs[-1][key]
              for key in ('digests', 'economic_final', 'observations', 'diagnostic_digest', 'decisions', 'notices', 'campaign_outcome')}
    distinct = {engine: len({r['economic_final'] for r in runs[:12]
                            if r['engine'] == engine and not r['traced']}) == 3
                for engine in ('client.desktop.engine', 'worldview_engine')}
    passed = all(all(v for k, v in c.items() if k.endswith('_equal')) for c in checks)
    report = dict(passed=passed and all(replay.values()) and all(distinct.values()),
                  steps=args.steps, recording_parity=checks, fresh_process_replay=replay,
                  distinct_policy_routes=distinct, runs=runs,
                  limitations='One authored seed. Automated consistency does not establish human usability or fun.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    if not report['passed']:
        raise SystemExit('Active governing checks failed: ' + str(args.output))
    print('Active governing checks passed: ' + str(args.output), flush=True)


if __name__ == '__main__':
    main()
