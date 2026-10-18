"""Matched short-horizon strategy runs for the labor frontier scenario.

Example:
    MPLCONFIGDIR=/private/tmp/regnum-mpl PYTHONHASHSEED=0 \
      venv/bin/python benchmark_labor_strategy.py --seeds 612 613 614 --turns 6

Each arm starts from the same authored world and resets both random streams to
the seed after setup. The output is diagnostic evidence, not a balance target.
"""

import argparse
import json
import random
import subprocess
from collections import Counter

from goods import Goods
from random_cache import rand
from livelihood_access import effective_access
from labor_frontier_labor import apply_action
from scenario_labor_frontier_rivalry import create_world, step_world


STRATEGY_ACTIONS = ('protect_access', 'approve_petition', 'fair_terms')


def run_arm(seed, action, turns):
    world = create_world(seed=seed)
    random.seed(seed)
    rand._idx = rand._capacity
    step_world(world)
    applied, message = apply_action(world, action)
    if not applied:
        raise RuntimeError(f'{action} failed at turn {world["turn"]}: {message}')
    for _ in range(max(0, turns - 1)):
        step_world(world)

    nations = {}
    for nation in world['nations']:
        people = [a for tile in nation.tiles for a in tile.agents
                  if a.alive and not a.is_corporation and not a.is_government]
        adults = [a for a in people
                  if not (getattr(a, 'is_native_child', False) and a.age(world['turn']) < 14)]
        livelihoods = Counter(getattr(getattr(a, 'primary_livelihood', None), 'name', 'none')
                              for a in adults)
        firms = [a for tile in nation.tiles for a in tile.agents
                 if a.alive and a.is_corporation]
        nations[nation.name] = {
            'living_residents': len(people),
            'living_adults': len(adults),
            'adult_livelihoods': dict(sorted(livelihoods.items())),
            'hungry_adults': sum(1 for a in adults if getattr(a, 'hungry_steps', 0) > 0),
            'adult_food_inventory': round(sum(a.inv_get(Goods.food, 0) for a in adults), 2),
            'mean_usable_commons_access': round(
                sum(effective_access(a, tile, 'commons_food')
                    for tile in nation.tiles for a in adults if a in tile.agents)
                / max(1, len(adults)), 4),
            'wage_workers': sum(len(f.employees) for f in firms),
            'firm_cash': round(sum(f.cash for f in firms), 2),
            'recent_gdp': round(sum(tile.gdp_log[-1] if tile.gdp_log else 0.0
                                    for tile in nation.tiles), 2),
            'protest_energy': round(sum(tile.protest_energy_log[-1]
                                        if tile.protest_energy_log else 0.0
                                        for tile in nation.tiles), 3),
            'military_soldiers': sum(unit.soldiers for unit in nation.military_units),
        }
    state = world['scenario_state']
    return {'seed': seed, 'action': action, 'turns': world['turn'],
            'action_result': message, 'nations': nations,
            'market_summary': state.get('market_summary', {}),
            'actions_taken': state.get('actions_taken', [])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', nargs='+', type=int, default=[612, 613, 614])
    parser.add_argument('--turns', type=int, default=6)
    args = parser.parse_args()
    print(json.dumps({'scenario': 'labor_frontier_rivalry',
                      'commit': subprocess.check_output(
                          ['git', 'rev-parse', 'HEAD'], text=True).strip(),
                      'turns_per_arm': args.turns,
                      'post_setup_rng_reset': True,
                      'arms': [run_arm(seed, action, args.turns)
                               for seed in args.seeds
                               for action in STRATEGY_ACTIONS]},
                     indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
