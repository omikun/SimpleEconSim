"""Seeded adult occupation and employer-flow benchmark for the default nations.

Run with: PYTHONHASHSEED=0 venv/bin/python benchmark_career_mobility.py --turns 50
One turn is one agent year; ten turns complete one seasonal production cycle.
"""

import argparse
import json
import random
from collections import Counter, defaultdict

from goods import Goods


def snapshot(server, turn):
    people = {}
    for nation in server.nations:
        for tile in nation.tiles:
            for person in tile.agents:
                if (not person.alive or person.is_corporation or person.is_government
                        or person.id in people):
                    continue
                adult = not (getattr(person, 'is_native_child', False)
                             and person.age(turn) < 14)
                employer = getattr(person, 'employer', None)
                people[person.id] = (
                    nation.name, tile.name, person.output.name,
                    employer.id if employer is not None else None, adult)
    return people


def benchmark(turns=50, seed=777):
    from sim_server.sim_server import SimServer
    import trace_snapshots

    random.seed(seed)
    server = SimServer(seed=seed, terrain_seed=seed, nation_seed=seed,
                       topology='voronoi', autoplay_nations=True)
    for tile in server.tiles:
        tile._run_trace = None
    trace_snapshots.record = lambda _server: None
    server.run_trace.checkpoint = lambda _clock: None

    before = snapshot(server, 0)
    flows = defaultdict(Counter)
    for turn in range(1, turns + 1):
        server.step()
        after = snapshot(server, turn)
        for person_id, row in after.items():
            nation = row[0]
            prior = before.get(person_id)
            if not row[4]:
                flows[nation]['dependent_person_years'] += 1
                if prior is None:
                    flows[nation]['new_dependents'] += 1
                continue
            flows[nation]['adult_person_years'] += 1
            if prior is None:
                flows[nation]['new_residents'] += 1
                continue
            if not prior[4]:
                flows[nation]['adult_entries'] += 1
                continue
            if prior[0] != nation:
                flows[nation]['cross_nation_migrations'] += 1
            if prior[1] != row[1]:
                flows[nation]['cross_tile_migrations'] += 1
            if prior[2] != row[2]:
                flows[nation]['occupation_changes'] += 1
            if prior[3] != row[3]:
                flows[nation]['employer_changes'] += 1
        for person_id, row in before.items():
            if person_id not in after:
                flows[row[0]]['exits'] += 1
        before = after
    outcomes = {}
    for nation in server.nations:
        residents = [row for row in before.values() if row[0] == nation.name]
        adults = [row for row in residents if row[4]]
        tiles = nation.tiles
        outcomes[nation.name] = {
            'living_residents': len(residents),
            'living_adults': len(adults),
            'adult_food_career_share': round(
                sum(row[2] == Goods.food.name for row in adults) / max(1, len(adults)), 4),
            'reported_deaths': sum(sum(getattr(tile, 'dead_pop', [])) for tile in tiles),
            'reported_starvation_deaths': sum(
                (getattr(tile, 'dead_starved_population', []) or [0])[-1]
                for tile in tiles),
        }
    return {
        'seed': seed, 'turns': turns, 'agent_years': turns,
        'seasonal_cycles': turns / 10,
        'outcomes': outcomes,
        'by_nation': {
            name: {
                **dict(counts),
                'occupation_changes_per_adult_year': round(
                    counts['occupation_changes'] / max(1, counts['adult_person_years']), 5),
                'employer_changes_per_adult_year': round(
                    counts['employer_changes'] / max(1, counts['adult_person_years']), 5),
            }
            for name, counts in sorted(flows.items())
        },
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--turns', type=int, default=50)
    parser.add_argument('--seed', type=int, default=777)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.turns, args.seed), indent=2, sort_keys=True))
