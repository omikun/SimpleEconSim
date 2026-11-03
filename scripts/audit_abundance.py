"""Run the real local turn loop and report abundance outcomes.

Use a fresh process per case: the engine has process-global registries.
The productivity treatment is a declared experimental yield change at turn 16;
no purchases, births, workshop output, or recurring income are injected.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sitecustomize
from goods import Goods
from region import Region
from random_cache import rand
from sim_engine import step_turn


def run(seed=4243, turns=60, productivity=1.0):
    random.seed(seed)
    rand._idx = rand._capacity
    region = Region('Abundance parish', 0, 70, number_of_traders=0,
                    profession_distribution={Goods.food: .75, Goods.wood: .15, Goods.furniture: .1},
                    terrain={Goods.food: 1.0, Goods.wood: 1.0})
    rows, violations = [], []
    for turn in range(1, turns+1):
        if turn == 16:
            region.terrain[Goods.food] *= productivity
        problems, _ = step_turn(turn, [region])
        violations.extend(problems)
        people = [a for a in region.agents if a.alive and not a.is_corporation and not a.is_government]
        negative = [(a.id, g.name, a.inv_get(g)) for a in region.agents for g in region.goods if a.inv_get(g) < 0]
        if negative:
            raise AssertionError(negative)
        rows.append({'turn': turn, 'population': len(people),
                     'food_produced': region.production_log[Goods.food][-1],
                     'food_price': region.recipes[Goods.food]['price'],
                     'prepared_food_produced': region.production_log[Goods.prepared_food][-1],
                     'prepared_food_sold': region.sold_log[Goods.prepared_food][-1] if region.sold_log[Goods.prepared_food] else 0,
                     'prepared_food_price': region.recipes[Goods.prepared_food]['price'],
                     'workshops': sum(a.output == Goods.prepared_food for a in people),
                     'farmers': sum(a.output == Goods.food and a.employer is None for a in people),
                     'farm_firms': sum(a.is_corporation and a.output == Goods.food for a in region.agents),
                     'soil_fertility': region.soil_fertility,
                     'pasture_fraction': region.tenure.pasture_fraction,
                     'hungry_people': sum(a.calorie_deficit_kcal > 0 for a in people),
                     'food_stock': sum(a.inv_get(Goods.food) for a in region.agents),
                     'prepared_food_stock': sum(a.inv_get(Goods.prepared_food) for a in region.agents),
                     'nonfood_stock': sum(a.inv_get(Goods.cloth) + a.inv_get(Goods.furniture) for a in people),
                     'practice_work': sum(sum(getattr(a, 'productive_practice', {}).values()) for a in people)})
    return {'seed': seed, 'turns': turns, 'productivity_at_turn_16': productivity,
            'cash_conservation_violations': violations, 'observations': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=4243)
    parser.add_argument('--turns', type=int, default=60)
    parser.add_argument('--productivity', type=float, default=1.0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with redirect_stdout(io.StringIO()):
        result = run(args.seed, args.turns, args.productivity)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'observations'}))
