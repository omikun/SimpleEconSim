"""Observe a feudal parish for 200 turns with real national innovation.

Run one case per fresh process. No recurring endowments, granted designs,
construction orders, or productivity treatments are supplied by this harness.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sitecustomize
from abundance import enabled, proficiency
from ai_nation import NationPolicyAI
from career_transitions import populations, profession, working_adult
from goods import Goods
from innovation import get_innovation_system
from nation import Nation
from nutrition import basic_food_units
from random_cache import rand
from region import Region
from sim_engine import step_turn
from scripts.food_growth import analyze_growth
from tile_resources import TileResource


def source_signature():
    digest = hashlib.sha256()
    for folder in ('core', 'agents', 'micro', 'macro', 'meso', 'economy', 'terrain',
                   'scenarios', 'trace', 'sim_server', 'scripts'):
        for path in sorted((ROOT / folder).rglob('*.py')):
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    digest.update((ROOT / 'sitecustomize.py').read_bytes())
    return digest.hexdigest()


class DiscardOutput(io.TextIOBase):
    """Discard engine chatter without retaining hundreds of turns in memory."""
    def write(self, value):
        return len(value)


def residents(region):
    return [a for a in region.agents if a.alive and not a.is_corporation
            and not a.is_government and not getattr(a, 'military_unit_id', None)]


def installations(region):
    return [{'name': b.name, 'owner': getattr(b, 'private_owner_id', None),
             'designs': dict(getattr(b, 'technology_designs', {})),
             'efficiency': b.operational_efficiency,
             'food_multiplier': b.production_bonuses.get(Goods.food, 1.0),
             'under_retrofit': bool(getattr(b, 'retrofit_project_id', None))}
            for b in region.buildings]


def observe(region, nation, system, turn):
    people = residents(region)
    farmers = [a for a in people if working_adult(a, turn)
               and profession(a) == Goods.food]
    companies = [a for a in region.agents if a.alive and a.is_corporation]
    owners = {p.lord_id for p in region.tenure.plots}
    paid = next((row for row in getattr(region, '_paid_price_observations', {}).get(Goods.food, [])
                 if row['turn'] == turn), None)
    today = [e for e in getattr(region, 'economic_events', ()) if e['turn'] == turn]
    usages = list(getattr(region, 'technology_usage', {}).values())
    known = sorted(system.get_discovered_techs(nation.name))
    food_day = next((row for row in reversed(getattr(region, 'food_history', ()))
                     if row['turn'] == turn), None)
    return {
        'turn': turn, 'population': len(people),
        'underfed': sum(a.calorie_deficit_kcal > 0 for a in people),
        'basic_meal_demand': (food_day['ordinary_need'] if food_day is not None
                              else sum(basic_food_units(a) for a in people)),
        'food_seed_use': food_day['seed_use'] if food_day is not None else None,
        'food_storage_losses': food_day['losses'] if food_day is not None else None,
        'births_counter': getattr(region, 'births_this_turn', 0),
        'deaths_by_cause': dict(getattr(region, 'deaths_by_cause_this_turn', {})),
        'adult_professions': dict(populations(region, turn)),
        'farm_adults': len(farmers),
        'farm_practice_multiplier_mean': (sum(proficiency(a, Goods.food) for a in farmers)
                                           / len(farmers) if farmers else None),
        'production': {getattr(g, 'name', str(g)): values[-1] if values and turn else 0
                       for g, values in region.production_log.items()},
        'foraged_food': getattr(region, 'food_foraged_this_turn', 0) if turn else 0,
        'food_quote': region.recipes[Goods.food]['price'],
        'food_paid_quantity': paid['quantity'] if paid else 0,
        'food_paid_total': paid['paid'] if paid else 0,
        'food_paid_vwap': paid['paid'] / paid['quantity'] if paid else None,
        'prepared_food_sold': (region.sold_log[Goods.prepared_food][-1]
                               if turn and region.sold_log[Goods.prepared_food] else 0),
        'private_food_stock': sum(a.inv_get(Goods.food, 0) for a in region.agents),
        'prepared_food_stock': sum(a.inv_get(Goods.prepared_food, 0) for a in region.agents),
        'owner_food_stock': sum(a.inv_get(Goods.food, 0) for a in region.agents if a.id in owners),
        'public_food_stock': getattr(region.gov, 'food_inventory', 0),
        'granary_stock': getattr(region, 'granary_stock', 0),
        'soil_fertility': region.soil_fertility,
        'pasture_fraction': region.tenure.pasture_fraction,
        'water_pollution': getattr(region, 'pollution_water', 0),
        'household_cash': sum(a.cash for a in people),
        'household_deposits': sum(region.bank.deposits.get(a, 0) for a in people),
        'food_wages': sum(e['amount'] for e in today if e['kind'] == 'wage'
                          and any(c.id == e['payer_id'] and c.output == Goods.food for c in companies)),
        'estate_food_relief': getattr(region, 'estate_food_relief_units', 0) if turn else 0,
        'food_tribute': sum(e['quantity'] for e in today
                            if e['kind'] == 'feudal_tribute' and e.get('good') == 'food'),
        'corporations': len(companies),
        'staffed_corporations': sum(bool(c.employees) for c in companies),
        'farm_corporations': sum(c.output == Goods.food for c in companies),
        'prepared_food_corporations': sum(c.output == Goods.prepared_food for c in companies),
        'known_technologies': known,
        'technology_tiers': {tid: system.get_tech_tier(nation.name, tid) for tid in known},
        'domain_xp': dict(system.domain_experience.get(nation.name, {})),
        'installations': installations(region),
        'technology_work': sum(row.get('work', 0) for row in usages),
        'technology_usage': [{'tech_id': row['tech_id'], 'generation': row['generation'],
                              'work': row['work'], 'capacity': row['capacity']}
                             for row in usages],
        'projects': [{'name': p.recipe.name, 'status': p.status,
                      'progress': p.progress_pct, 'reason': p.stall_reason}
                     for p in region.construction_projects],
    }


def summarize(rows):
    result = []
    for start in range(1, rows[-1]['turn'] + 1, 20):
        period = [r for r in rows if start <= r['turn'] < start + 20]
        production = sum(r['production'].get('food', 0) for r in period)
        forage = sum(r['foraged_food'] for r in period)
        workers = sum(r['farm_adults'] for r in period)
        paid_units = sum(r['food_paid_quantity'] for r in period)
        result.append({
            'turns': [start, period[-1]['turn']], 'population_end': period[-1]['population'],
            'farm_food_per_turn': production / len(period),
            'forage_per_turn': forage / len(period),
            'farm_adults_mean': workers / len(period),
            'farm_food_per_adult_snapshot': production / workers if workers else None,
            'farm_share_of_new_food': production / (production + forage) if production + forage else None,
            'underfed_share': sum(r['underfed'] for r in period) / max(1, sum(r['population'] for r in period)),
            'food_quote_mean': sum(r['food_quote'] for r in period) / len(period),
            'food_paid_vwap': sum(r['food_paid_total'] for r in period) / paid_units if paid_units else None,
            'paid_food_units': paid_units,
            'prepared_food_output': sum(r['production'].get('prepared_food', 0) for r in period),
            'starvation_deaths': sum(r['deaths_by_cause'].get('starvation', 0) for r in period),
            'food_technology_assets_end': sum(r['food_multiplier'] > 1 for r in period[-1]['installations']),
        })
    return result


def run(seed=4243, turns=200, progress=None):
    signature = source_signature()
    random.seed(seed)
    rand._idx = rand._capacity
    region = Region('Abundance parish', 0, 70, number_of_traders=0,
                    profession_distribution={Goods.food: .75, Goods.wood: .15, Goods.furniture: .1},
                    terrain={Goods.food: 1.0, Goods.wood: 1.0})
    # Authored geology only: deposits confer research access, not goods or equipment.
    region.natural_resources = {TileResource.ARABLE_SILT, TileResource.TIMBER,
                                TileResource.IRON_ORE, TileResource.COAL_SEAM}
    nation = Nation('Abundance nation', currency=region.home_currency)
    nation.add_tile(region)
    nation.ai = NationPolicyAI(nation)
    system = get_innovation_system()
    assert enabled(region)
    assert not system.get_discovered_techs(nation.name)
    opening = observe(region, nation, system, 0)
    rows, events, violations = [], [], []
    started = time.monotonic()
    for turn in range(1, turns + 1):
        found, _ = step_turn(turn, [region], nations=[nation], pair_orders=[],
                             currencies=[nation.currency],
                             on_event=lambda t, kind, message: events.append(
                                 {'turn': t, 'kind': kind, 'message': message}))
        violations.extend(found)
        negative = [(a.id, g.name, a.inv_get(g, 0)) for a in region.agents
                    for g in region.goods if a.inv_get(g, 0) < -1e-9]
        if negative:
            raise AssertionError(f'Negative inventories on turn {turn}: {negative}')
        rows.append(observe(region, nation, system, turn))
        if progress and turn % 20 == 0:
            progress.write_text(json.dumps({'seed': seed, 'turn': turn,
                'population': rows[-1]['population'], 'underfed': rows[-1]['underfed'],
                'known': rows[-1]['known_technologies'],
                'elapsed_seconds': time.monotonic() - started}, indent=2) + '\n')
    decisions = Counter()
    for person in region.agents:
        for decision in getattr(person, 'technology_adoption_decisions', {}).values():
            decisions[decision.get('reason', 'unknown')] += 1
    final_signature = source_signature()
    return {'seed': seed, 'turns': turns, 'source_signature': signature,
            'source_signature_end': final_signature, 'source_unchanged': signature == final_signature,
            'python_hash_seed': os.environ.get('PYTHONHASHSEED', 'unfixed'),
            'elapsed_seconds': time.monotonic() - started,
            'settings': {'national_ai': True, 'national_innovation': True,
                'abundance': True, 'artificial_yield_boost': False, 'outside_markets': False,
                'starting_resources': sorted(r.value for r in region.natural_resources),
                'extra_endowments': False,
                'food_model_version': getattr(region, 'food_economy_version', 1),
                'food_opening_mode': getattr(region, 'food_opening_mode', 'legacy'),
                'spoilage': getattr(region, 'food_economy_version', 1) == 2},
            'opening': opening, 'observations': rows, 'periods': summarize(rows),
            'growth_trends': analyze_growth(rows),
            'events': events, 'innovation_log': list(system.discovery_log),
            'latest_adoption_reasons': dict(decisions),
            'currency_audit_violations': violations, 'negative_inventory_checks_passed': True,
            'limitations': ['Single authored parish, no interregional trade or export test.',
                'Starting geology exposes crop and early industrial research; it does not supply physical materials.',
                'Population/death counters can include entity conversion; counts are not a matched birth/death cohort.',
                'Prepared food reprocesses grain and must not be added to grain as new calories.',
                'Farm output per adult snapshot is not measured output per actual shift.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=4243)
    parser.add_argument('--turns', type=int, default=200)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with redirect_stdout(DiscardOutput()):
        result = run(args.seed, args.turns, args.output.with_suffix('.progress.json'))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('seed', 'turns', 'source_unchanged',
                     'currency_audit_violations', 'elapsed_seconds')}))
    if not result['source_unchanged'] or result['currency_audit_violations']:
        raise SystemExit('Audit failed; retain evidence and investigate before accepting the run.')
