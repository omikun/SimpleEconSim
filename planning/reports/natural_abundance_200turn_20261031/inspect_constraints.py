"""Read-only boundary diagnostics, required to reproduce the unobserved run."""
from collections import Counter
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(os.environ.get('ABUNDANCE_SOURCE_ROOT', Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(ROOT))
import sitecustomize
from scripts.audit_natural_abundance import DiscardOutput, run
from goods import Goods
import region_production
import technology_adoption

rows, decisions = [], []
original_produce = region_production.produce
original_adoption = technology_adoption.step_private_adoption


def produce(region, turn):
    farmers = [a for a in region.agents if a.alive and a.output == Goods.food
               and not a.is_corporation and not a.is_government and not a.is_trader
               and not a.employer and not (a.is_native_child and a.age(turn) < 14)]
    withheld = lambda a: (getattr(a, 'is_striking', False) or getattr(a, 'in_revolt', False)
                         or a.id in getattr(region, 'pollution_revolt_ids', set()))
    cap = region.recipes[Goods.food]['maxinv']
    blocked = [a for a in farmers if withheld(a)]
    full = [a for a in farmers if not withheld(a) and a.inv_get(Goods.food, 0) >= cap]
    eligible = [a for a in farmers if not withheld(a) and a.inv_get(Goods.food, 0) < cap]
    before = {a.id: getattr(a, 'productive_practice', {}).get('food', 0) for a in farmers}
    row = {'turn': turn, 'independent_farmers': len(farmers),
           'withheld_farmers': len(blocked), 'inventory_full_farmers': len(full),
           'eligible_farmers': len(eligible),
           'hungry_farmers': sum(a.hungry_steps > 0 for a in farmers),
           'mean_food_before_production': sum(a.inv_get(Goods.food, 0) for a in farmers) / max(1, len(farmers)),
           'temporary_work_share_total': sum(getattr(a, 'temporary_work_share', 0) for a in farmers),
           'farming_regime': getattr(region, 'farming_regime', 'rotation'),
           'soil_fertility': region.soil_fertility,
           'water_pollution': region.pollution_water,
           'striking_farmers': sum(getattr(a, 'is_striking', False) for a in farmers),
           'revolting_farmers': sum(getattr(a, 'in_revolt', False) for a in farmers),
           'pollution_revolt_farmers': sum(a.id in getattr(region, 'pollution_revolt_ids', set()) for a in farmers)}
    result = original_produce(region, turn)
    receipts = [r for r in region.production_receipts if r['good'] == Goods.food]
    row['successful_independent_operations'] = len(receipts)
    row['independent_food_output'] = sum(r['quantity'] for r in receipts)
    row['earned_farm_practice'] = sum(getattr(a, 'productive_practice', {}).get('food', 0) - before[a.id]
                                      for a in farmers)
    rows.append(row)
    return result


def adoption(tiles, nations, turn, system=None):
    result = original_adoption(tiles, nations, turn, system)
    for tile in tiles:
        for a in tile.agents:
            for decision in getattr(a, 'technology_adoption_decisions', {}).values():
                if decision['turn'] == turn:
                    decisions.append({'actor': a.id, 'output': a.output.name,
                                      'employees': len(a.employees), **decision})
    return result


if __name__ == '__main__':
    folder = Path(os.environ.get('ABUNDANCE_REPORT_ROOT', Path(__file__).resolve().parent))
    expected = json.loads((folder / 'seed_4243.json').read_text())
    with patch.object(region_production, 'produce', produce), \
            patch.object(technology_adoption, 'step_private_adoption', adoption), \
            redirect_stdout(DiscardOutput()):
        actual = run(4243, 200)
    for key in ('source_signature', 'opening', 'observations', 'periods', 'events',
                'innovation_log', 'currency_audit_violations', 'latest_adoption_reasons'):
        assert actual[key] == expected[key], f'Observer altered {key}'
    assert actual['source_unchanged']
    output = {'seed': 4243, 'observer_matches_unobserved_run': True,
              'source_signature': actual['source_signature'], 'rows': rows,
              'adoption_decisions': decisions,
              'decision_counts': dict(Counter(d['reason'] for d in decisions))}
    (folder / 'seed_4243_constraints.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({key: value for key, value in output.items()
                      if key not in ('rows', 'adoption_decisions')}))
