"""Observe seasonal tribute and estate relief without changing a saved run."""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sitecustomize
from scripts import audit_abundance as campaign
from economy import actor_accounts
from feudal_tribute import estate_residents
from goods import Goods


def signature():
    digest = hashlib.sha256()
    for folder in ('core', 'agents', 'micro', 'meso', 'macro', 'economy', 'terrain', 'scenarios', 'trace', 'sim_server'):
        for path in sorted((ROOT/folder).rglob('*.py')):
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def inspect(seed, productivity, reference):
    source = signature()
    transfers, rows = [], []
    original_record, original_step = actor_accounts.record, campaign.step_turn

    def record(region, kind, **kwargs):
        result = original_record(region, kind, **kwargs)
        if kind in ('feudal_tribute', 'estate_food_relief'):
            transfers.append(dict(result))
        return result

    def step(turn, tiles, *args, **kwargs):
        result = original_step(turn, tiles, *args, **kwargs)
        r = tiles[0]
        people = [a for a in r.agents if a.alive and not a.is_government and not a.is_corporation]
        hungry = [a for a in people if a.calorie_deficit_kcal > 0]
        resident_ids = {a.id for group in estate_residents(r).values() for a in group}
        owner_ids = {p.lord_id for p in r.tenure.plots}
        owner_food = sum(a.inv_get(Goods.food, 0) for a in r.agents if a.id in owner_ids)
        today = [e for e in transfers if e['turn'] == turn]
        rows.append({'turn': turn, 'population': len(people), 'underfed': len(hungry),
                     'underfed_estate_residents': sum(a.id in resident_ids for a in hungry),
                     'underfed_others': sum(a.id not in resident_ids for a in hungry),
                     'underfed_children_under14': sum(a.is_native_child and a.age(turn) < 14 for a in hungry),
                     'owner_food': owner_food, 'private_food': sum(a.inv_get(Goods.food, 0) for a in r.agents),
                     'estate_relief_food': sum(e['quantity'] for e in today if e['kind'] == 'estate_food_relief'),
                     'tribute_food': sum(e['quantity'] for e in today if e['kind'] == 'feudal_tribute' and e['good'] == 'food'),
                     'collection_boundary': getattr(r, '_feudal_tribute_collection_turn', None) == turn,
                     'starvation_deaths': getattr(r, 'deaths_by_cause_this_turn', {}).get('starvation', 0),
                     'top_food_holders': [{'id': a.id, 'owner': a.id in owner_ids,
                                           'food': a.inv_get(Goods.food, 0)}
                                          for a in sorted(r.agents, key=lambda a: a.inv_get(Goods.food, 0), reverse=True)[:5]]})
        return result

    with patch.object(actor_accounts, 'record', record), patch.object(campaign, 'step_turn', step):
        with redirect_stdout(io.StringIO()):
            actual = campaign.run(seed=seed, turns=60, productivity=productivity)
    if actual != json.loads(Path(reference).read_text()):
        raise AssertionError('Observers changed the benchmark result')
    after = signature()
    if source != after:
        raise AssertionError('Simulation source changed during the run')
    counts = Counter(e['kind'] for e in transfers)
    return {'seed': seed, 'productivity_at_turn_16': productivity,
            'acceptance_matches': True, 'source_unchanged': True, 'source_signature': source,
            'collection_turns': [r['turn'] for r in rows if r['collection_boundary']],
            'event_counts': dict(counts), 'total_estate_relief_food': sum(r['estate_relief_food'] for r in rows),
            'total_food_tribute': sum(r['tribute_food'] for r in rows),
            'starvation_deaths': sum(r['starvation_deaths'] for r in rows),
            'observations': rows, 'transfers': transfers}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=4243)
    parser.add_argument('--productivity', type=float, default=2)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.seed, args.productivity, args.reference)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('observations', 'transfers')}))
