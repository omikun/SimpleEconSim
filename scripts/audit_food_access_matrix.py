"""Run food access comparisons in independent processes at fixed source/hash seeds."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'planning/reports/food_access_final_20261030'
CASES = {
    'commercial': ['--variant', 'commercial'],
    'regional': ['--variant', 'commercial', '--public-steam-pilot'],
    'control': ['--variant', 'control'],
    'responsive': ['--variant', 'commercial', '--labor-policy', 'responsive'],
    'responsive_relief': ['--variant', 'commercial', '--labor-policy', 'responsive', '--relief', 'emergency'],
    'frozen_relief': ['--variant', 'commercial', '--relief', 'emergency'],
}


def run(item):
    name, seed = item
    target = OUTPUT / f'{name}_{seed}.json'
    command = [sys.executable, str(ROOT / 'scripts/audit_engineering_campaigns.py'),
               *CASES[name], '--seed', str(seed), '--output', str(target)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
        env={**os.environ, 'PYTHONHASHSEED': '0', 'MPLCONFIGDIR': '/private/tmp/engineering-mpl'})
    if completed.returncode:
        raise RuntimeError(f'{name}/{seed}: {completed.stderr[-3000:]}')
    data = json.loads(target.read_text())
    end = data['snapshots'][-1]
    food = end['food_security']
    row = {'case': name, 'seed': seed, 'source': data['source_signature'],
           'source_unchanged': data['source_unchanged'],
           'residents': end['living_households'], 'underfed': food['underfed_residents'],
           'starvation_deaths': end['deaths_by_cause'].get('starvation', 0),
           'deaths': end['deaths_by_cause'], 'company_food': food['company_food_units'],
           'farm_output': food['production_units_last_turn'], 'foraged': food['foraged_units_last_turn'],
           'meal_cost': food['meal_reference_cost'],
           'currency_violations': len(data['currency_audit_violations']),
           'food_violations': sum(abs(r['unexplained']) > .0001 for r in data.get('food_conservation', ())),
           'farm_support': food['farm_support_adult_equivalents'],
           'resident_need': food['resident_adult_equivalents']}
    print(json.dumps(row), flush=True)
    return row


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUTPUT)
    OUTPUT = parser.parse_args().output
    OUTPUT.mkdir(parents=True, exist_ok=True)
    jobs = [(name, seed) for seed in (4243, 4242, 4244) for name in CASES]
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(run, jobs))
    (OUTPUT / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    if len({r['source'] for r in rows}) != 1 or not all(r['source_unchanged'] for r in rows):
        raise RuntimeError('Source changed across the matrix; retain evidence and rerun at one version.')
    if any(r['currency_violations'] or r['food_violations'] for r in rows):
        raise RuntimeError('A currency or food audit failed.')
