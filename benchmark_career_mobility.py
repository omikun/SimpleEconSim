"""Seeded person ledger and adult labor flows for the default three-nation game.

PYTHONHASHSEED=0 venv/bin/python benchmark_career_mobility.py --turns 50
One turn is one agent year; ten turns make a seasonal crop cycle.
"""

import argparse
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass

from goods import Goods


@dataclass(frozen=True)
class PersonState:
    agent: object
    nation: str
    tile: str
    career: str
    employer_id: int | None
    adult: bool
    status: str = 'independent'


def snapshot(server, turn):
    """Include all tiles, including wilderness and tiles outside a nation."""
    people = {}
    for tile in server.tiles:
        owner = getattr(tile, 'owner_nation', None)
        nation = owner.name if owner is not None else 'Unclaimed'
        for person in tile.agents:
            if not person.alive or person.is_corporation or person.is_government:
                continue
            if person.id in people:
                raise AssertionError(f'duplicate living person {person.id}: '
                                     f'{people[person.id].tile}, {tile.name}')
            adult = not (getattr(person, 'is_native_child', False)
                         and person.age(turn) < 14)
            employer = getattr(person, 'employer', None)
            status = ('military' if getattr(person, 'military_unit_id', None) else
                      'trader' if getattr(person, 'is_trader', False) else
                      'workhouse' if getattr(person, 'in_workhouse', False) else
                      'employed' if employer is not None else 'independent')
            primary = getattr(person, 'primary_livelihood', None)
            people[person.id] = PersonState(
                person, nation, tile.name,
                primary.name if primary is not None else 'none',
                employer.id if employer is not None else None, adult, status)
    return people


def entity_roles(server):
    return {a.id: ('corporation' if a.is_corporation else
                   'government' if a.is_government else 'person')
            for tile in server.tiles for a in tile.agents}


def validate_employment_rosters(server, turn):
    """Every employed person has exactly one matching firm roster entry."""
    people = [a for tile in server.tiles for a in tile.agents
              if a.alive and not a.is_corporation and not a.is_government]
    for worker in people:
        firm = worker.employer
        if firm is not None and (not firm.alive or worker not in firm.employees
                                or firm.employees.count(worker) != 1):
            raise AssertionError(f'turn {turn}: worker {worker.id} has unmatched employer')
    for tile in server.tiles:
        for firm in tile.agents:
            if not firm.is_corporation:
                continue
            seen = set()
            for worker in firm.employees:
                if worker.id in seen or worker.employer is not firm or not worker.alive:
                    raise AssertionError(f'turn {turn}: firm {firm.id} has invalid roster')
                seen.add(worker.id)


def compare_people(before, after, server, turn, prior_roles=None):
    """Classify each stock change once; absence alone is never a death."""
    flows = defaultdict(Counter)
    raw = {a.id: a for tile in server.tiles for a in tile.agents}
    unexplained = []
    for person_id, now in after.items():
        country = now.nation
        prior = before.get(person_id)
        if prior is None:
            if (prior_roles or {}).get(person_id) in ('corporation', 'government'):
                kind = 'role_conversions_in'
            elif (getattr(now.agent, 'is_native_child', False)
                  and now.agent.birth_round == turn):
                kind = 'birth'
            else:
                kind = 'immigration_or_entry'
            flows[country][kind] += 1
        else:
            if prior.tile != now.tile:
                flows[prior.nation]['departures'] += 1
                flows[country]['arrivals'] += 1
                flows[country]['cross_tile_migrations'] += 1
                if prior.nation != country:
                    flows[country]['cross_nation_migrations'] += 1
            if now.adult and not prior.adult:
                flows[country]['adult_entries'] += 1
        if not now.adult:
            flows[country]['dependent_person_years'] += 1
            continue
        flows[country]['adult_person_years'] += 1
        flows[country][f'{now.status}_adult_years'] += 1
        if prior is not None and prior.adult:
            if prior.career != now.career:
                flows[country]['occupation_changes'] += 1
            if prior.employer_id != now.employer_id:
                flows[country]['employer_changes'] += 1
            if prior.status != now.status:
                flows[country]['status_changes'] += 1

    for person_id, prior in before.items():
        if person_id in after:
            continue
        if not prior.agent.alive:
            flows[prior.nation]['deaths'] += 1
            cause = getattr(prior.agent, 'death_cause', None) or 'unclassified'
            flows[prior.nation][f'deaths_{cause}'] += 1
        elif person_id in raw and (raw[person_id].is_corporation
                                   or raw[person_id].is_government):
            flows[prior.nation]['role_conversions_out'] += 1
        else:
            unexplained.append({'turn': turn, 'person_id': person_id,
                                'last_tile': prior.tile, 'last_nation': prior.nation})
            flows[prior.nation]['unknown_exits'] += 1

    before_counts = Counter(row.nation for row in before.values())
    after_counts = Counter(row.nation for row in after.values())
    for nation in before_counts.keys() | after_counts.keys() | flows.keys():
        f = flows[nation]
        expected = (before_counts[nation] + f['birth'] + f['immigration_or_entry']
                    + f['arrivals'] + f['role_conversions_in']
                    - f['departures'] - f['deaths']
                    - f['role_conversions_out'] - f['unknown_exits'])
        if expected != after_counts[nation]:
            raise AssertionError(f'person ledger turn {turn} {nation}: '
                                 f'expected {expected}, observed {after_counts[nation]}')
    tile_flows = defaultdict(Counter)
    for person_id, now in after.items():
        prior = before.get(person_id)
        if prior is None:
            kind = ('role_conversions_in' if (prior_roles or {}).get(person_id)
                    in ('corporation', 'government') else
                    'birth' if getattr(now.agent, 'is_native_child', False)
                    and now.agent.birth_round == turn else 'immigration_or_entry')
            tile_flows[now.tile][kind] += 1
        elif prior.tile != now.tile:
            tile_flows[prior.tile]['departures'] += 1
            tile_flows[now.tile]['arrivals'] += 1
    for person_id, prior in before.items():
        if person_id in after:
            continue
        if not prior.agent.alive:
            tile_flows[prior.tile]['deaths'] += 1
        elif person_id in raw and (raw[person_id].is_corporation
                                   or raw[person_id].is_government):
            tile_flows[prior.tile]['role_conversions_out'] += 1
        else:
            tile_flows[prior.tile]['unknown_exits'] += 1
    old_tiles = Counter(row.tile for row in before.values())
    new_tiles = Counter(row.tile for row in after.values())
    for tile in old_tiles.keys() | new_tiles.keys() | tile_flows.keys():
        f = tile_flows[tile]
        expected = (old_tiles[tile] + f['birth'] + f['immigration_or_entry']
                    + f['arrivals'] + f['role_conversions_in']
                    - f['departures'] - f['deaths']
                    - f['role_conversions_out'] - f['unknown_exits'])
        if expected != new_tiles[tile]:
            raise AssertionError(f'person ledger turn {turn} tile {tile}: '
                                 f'expected {expected}, observed {new_tiles[tile]}')
    return flows, unexplained


def unmatched_event_balance(changes, registered_births, registered_deaths):
    """A birth and death within one turn cancel without entering either snapshot."""
    seen_births = sum(counts['birth'] for counts in changes.values())
    seen_deaths = sum(counts['deaths'] for counts in changes.values())
    return (registered_births - seen_births) - (registered_deaths - seen_deaths)


def benchmark(turns=50, seed=777, *, trace=False):
    from sim_server.sim_server import SimServer
    import trace_snapshots

    random.seed(seed)
    server = SimServer(seed=seed, terrain_seed=seed, nation_seed=seed,
                       topology='voronoi', autoplay_nations=True)
    if not trace:
        for tile in server.tiles:
            tile._run_trace = None
        trace_snapshots.record = lambda _server: None
        server.run_trace.checkpoint = lambda _clock: None

    before = snapshot(server, 0)
    validate_employment_rosters(server, 0)
    prior_roles = entity_roles(server)
    totals = defaultdict(Counter)
    unexplained = []
    event_reconciliation = []
    for turn in range(1, turns + 1):
        server.step()
        validate_employment_rosters(server, turn)
        after = snapshot(server, turn)
        changes, unknown = compare_people(before, after, server, turn, prior_roles)
        for nation, counts in changes.items():
            totals[nation].update(counts)
        registered_births = sum(int(getattr(tile, 'births_this_turn', 0))
                                for tile in server.tiles)
        registered_deaths = sum(int(getattr(tile, 'deaths_this_turn', 0))
                                for tile in server.tiles)
        event_reconciliation.append({
            'turn': turn, 'registered_births': registered_births,
            'registered_deaths': registered_deaths,
            'end_snapshot_births': sum(c['birth'] for c in changes.values()),
            'prior_snapshot_deaths': sum(c['deaths'] for c in changes.values()),
            'unmatched_event_balance': unmatched_event_balance(
                changes, registered_births, registered_deaths),
        })
        unexplained.extend(unknown[:max(0, 20 - len(unexplained))])
        before = after
        prior_roles = entity_roles(server)
    failures = [row for row in event_reconciliation
                if row['unmatched_event_balance'] != 0]
    if unexplained or failures:
        raise AssertionError({'unexplained_people': unexplained[:10],
                              'event_reconciliation': failures[:10]})

    outcomes = {}
    for nation in server.nations:
        residents = [row for row in before.values() if row.nation == nation.name]
        adults = [row for row in residents if row.adult]
        livelihoods = Counter(row.career for row in adults)
        sold = Counter()
        for tile in nation.tiles:
            for good, history in getattr(tile, 'sold_log', {}).items():
                sold[getattr(good, 'name', str(good))] += sum(history[-10:])
        outcomes[nation.name] = {
            'living_residents': len(residents),
            'living_adults': len(adults),
            'adult_livelihoods': dict(sorted(livelihoods.items())),
            'last_crop_cycle_sales': dict(sorted(sold.items())),
            'adult_food_career_share': round(
                sum(row.career == Goods.food.name for row in adults) / max(1, len(adults)), 4),
            'reported_demographic_deaths': sum(
                sum(getattr(tile, 'dead_pop', [])) for tile in nation.tiles),
            'reported_starvation_deaths': sum(
                (getattr(tile, 'dead_starved_population', []) or [0])[-1]
                for tile in nation.tiles),
        }
    return {
        'seed': seed, 'turns': turns, 'agent_years': turns,
        'seasonal_cycles': turns / 10,
        'outcomes': outcomes,
        'event_reconciliation_failures': failures,
        'unexplained_examples': unexplained,
        'by_nation': {
            name: {
                **dict(counts),
                'occupation_changes_per_adult_year': round(
                    counts['occupation_changes'] / max(1, counts['adult_person_years']), 5),
                'employer_changes_per_adult_year': round(
                    counts['employer_changes'] / max(1, counts['adult_person_years']), 5),
            }
            for name, counts in sorted(totals.items())
        },
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--turns', type=int, default=50)
    parser.add_argument('--seed', type=int, default=777)
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    print(json.dumps(benchmark(args.turns, args.seed, trace=args.trace),
                     indent=2, sort_keys=True))
