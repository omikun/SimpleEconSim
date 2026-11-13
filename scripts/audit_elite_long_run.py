"""Observe 100 full normal-world turns in a fresh process for each planner mode."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sitecustomize
from sim_server.sim_server import SimServer
from world_config import ElitePlanningConfig
from scripts.elite_audit_observer import EliteAudit


def source_signature():
    digest = hashlib.sha256()
    for folder in ('core', 'agents', 'economy', 'micro', 'meso', 'macro', 'sim_server', 'scripts'):
        for path in sorted((ROOT/folder).rglob('*.py')):
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def aggregate(rows):
    result = {}
    for role in ('corporation', 'lord', 'capitalist_owner'):
        group = [r for r in rows if r['role'] == role]
        alive = [r for r in group if r['alive'] and r['present']]
        currencies = {}
        for unit in sorted({r['currency'] for r in alive}):
            members = [r for r in alive if r['currency'] == unit]
            currencies[unit] = dict(count=len(members), cash=sum(r['cash'] for r in members),
                deposits=sum(r['deposits_by_currency'].get(unit, 0) for r in members),
                bank_debt=sum(r['bank_debt_by_currency'].get(unit, 0) for r in members),
                arrears=sum(r['wage_arrears'] for r in members))
        result[role] = dict(ever_seen=len(group), alive_present=len(alive),
            dead=sum(not r['alive'] for r in group), missing_alive=sum(r['alive'] and not r['present'] for r in group),
            employees=sum(r['employees'] for r in alive), no_employees=sum(r['employees']==0 for r in alive),
            input_short=sum(r['nominal_input_gap']>0 for r in alive), currencies=currencies)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('active', 'off'), required=True)
    parser.add_argument('--turns', type=int, default=100)
    parser.add_argument('--seed', type=int, default=4243)
    parser.add_argument('--topology', choices=('hex', 'voronoi'), default='hex')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    signature = source_signature()
    server = SimServer(seed=args.seed, terrain_seed=args.seed, nation_seed=args.seed,
                       topology=args.topology, trace_enabled=False,
                       elite_planning_config=ElitePlanningConfig(mode=args.mode))
    audit = EliteAudit(server, args.output)
    audit.install()
    initial = audit.collect(0)
    meta = dict(seed=args.seed, topology=args.topology, mode=args.mode, turns_requested=args.turns,
        source_signature=signature, git_head=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT,text=True).strip(),
        flags=server.gameplay_flags.as_dict(), settings=server.elite_planning_config.as_dict(),
        nation_autoplay=server.autoplay_nations, tiles=len(server.tiles), nations=len(server.nations),
        initial=aggregate(initial), initial_actors=initial, tracing='native recorder off; read-only source observers')
    (args.output/'metadata.json').write_text(json.dumps(meta, indent=2))
    started = time.perf_counter()
    progress = []
    try:
        for turn in range(1, args.turns+1):
            server.step()
            if server.turn != turn:
                raise RuntimeError(f'Expected turn {turn}, reached {server.turn}')
            actors = audit.collect(turn)
            row = dict(turn=turn, elapsed=time.perf_counter()-started, population=len({a.id for r in server.tiles for a in r.agents if a.alive and not a.is_corporation and not a.is_government}),
                       groups=aggregate(actors), violations=server.violations)
            progress.append(row)
            if turn == 1 or turn % 10 == 0:
                (args.output/'progress.json').write_text(json.dumps(progress, indent=2))
                print(json.dumps({k:row[k] for k in ('turn','elapsed','population','groups')}), flush=True)
        summary = dict(metadata=meta, turns_completed=server.turn, progress=progress,
                       decisions=dict(audit.counts), final_actors=actors,
                       elapsed=time.perf_counter()-started, source_unchanged=source_signature()==signature)
        (args.output/'summary.json').write_text(json.dumps(summary, indent=2))
    finally:
        audit.close()


if __name__ == '__main__':
    main()
