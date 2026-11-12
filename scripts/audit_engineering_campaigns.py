"""Reproducible live-economy acceptance runs for commercial engineering.

Run each variant in a fresh process (the engine owns process-global registries):
  venv/bin/python scripts/audit_engineering_campaigns.py --variant commercial --output /tmp/commercial.json
No sales, operating work, technology progress or recurring income are injected.
"""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
import hashlib
import os
from collections import Counter
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sitecustomize  # noqa: E402
from agent import Agent, seed_traits
from buildings import BUILDING_RECIPES, Building
from engineering import quote_recipe
from goods import Goods
from innovation import get_innovation_system
from nation import Nation
from region import Region
from sim_engine import step_turn
from tile_resources import TileResource
from random_cache import rand
from land_tenure import TenureStatus
from technology_adoption import observe_firm_market
from food_security import diagnose_tile
from world_config import FULL_GAMEPLAY_FLAGS


def create_campaign(variant, seed):
    random.seed(seed)
    rand._idx = rand._capacity
    nation = Nation('Engineering Republic', currency='Crown', initial_cash=10000)
    population = 18 if variant == 'low_demand' else 75
    region = Region('Works', 0, population, number_of_traders=0,
        profession_distribution={Goods.food: .65, Goods.wood: .15, Goods.iron: .05,
                                 Goods.iron_ore: .05, Goods.coal: .05, Goods.furniture: .05})
    nation.add_tile(region)
    region.scenario_owner_policy = True
    region.cash_tax_per_person = 0.1
    region.natural_resources = list(TileResource)
    region.resources = {resource: 1 for resource in TileResource}
    for plot in region.tenure.plots:
        plot.tenure = TenureStatus.COMMONS
        plot.tribute_rate = plot.rent_rate = 0
    region.buildings.append(Building('engineering_workshop', BUILDING_RECIPES['engineering_workshop'], 0, region.name))
    people = [a for a in region.agents if not a.is_government and not a.is_lord]
    # Authored opening endowments, never replenished during the run.
    for person in people:
        person.cash = 40 if variant == 'low_demand' else 250
    suppliers = people[-5:]
    for supplier, good in zip(suppliers, (Goods.wood, Goods.iron, Goods.coal, Goods.iron_ore, Goods.porcelain)):
        supplier.output = good
        supplier.inv_add(good, 160)
    suppliers[1].inv_add(Goods.iron_ore, 300)
    owner = people[0]
    owner.cash += 2500
    firm = Agent(0)
    seed_traits(firm)
    firm.is_corporation = True
    firm.company_name = 'Republic Furniture Works'
    firm.owner = owner
    firm.output = Goods.furniture
    firm.region = region.name
    firm.home_currency = nation.currency
    firm._bank_ref = region.bank
    firm.wage = 2.5
    firm.max_employees = 4
    firm.risk_tolerance = 0.65
    firm.cash = 2500
    owner.cash -= firm.cash
    owner.company_owned = firm
    firm.inv_add(Goods.wood, 60)
    firm.cost_set(Goods.wood, 1)
    firm.employees = people[1:5]
    for worker in firm.employees:
        worker.employer = firm
    region.agents.append(firm)
    nation.government._add_citizen(firm)
    region.recipes[Goods.furniture]['production'] = 2
    region.recipes[Goods.furniture]['maxinv'] = 12
    region.recipes[Goods.wood].update(production=30, maxtotalprod=2000, maxinv=200)
    region.recipes[Goods.food]['maxtotalprod'] = 2000
    system = get_innovation_system()
    known = system.get_discovered_techs(nation.name)
    known.add('coal_coking')
    system.tech_refinement_xp.setdefault(nation.name, {})['coal_coking'] = 90
    system.get_guild_blockade(nation, 'coal_coking')['active'] = False
    if variant != 'public':
        known.add('steam_engines')
        system.tech_refinement_xp[nation.name]['steam_engines'] = 1
    system.get_guild_blockade(nation, 'steam_engines')['active'] = False
    return nation, region, firm, system


def source_signature():
    digest = hashlib.sha256()
    for directory in ('core', 'agents', 'micro', 'macro', 'meso', 'economy', 'trace', 'scripts'):
        for path in sorted((ROOT / directory).rglob('*.py')):
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def run_campaign(variant, seed=4243, turns=100, public_steam_pilot=False,
                 labor_policy='frozen', relief='ordinary', owner_planning='authored'):
    signature = source_signature()
    nation, region, firm, system = create_campaign(variant, seed)
    if (labor_policy not in ('frozen', 'responsive') or relief not in ('ordinary', 'emergency', 'ai')
            or owner_planning not in ('authored', 'autonomous')):
        raise ValueError('Unknown labor or relief policy')
    region.scenario_owner_policy = owner_planning == 'authored'
    region.responsive_wages = labor_policy == 'responsive'
    gameplay_flags = replace(
        FULL_GAMEPLAY_FLAGS,
        private_technology_adoption=variant != 'control',
        elite_planning=owner_planning == 'autonomous',
        abundance=owner_planning == 'autonomous',
        career_mobility=labor_policy == 'responsive',
        wage_quotes=labor_policy == 'responsive')
    if relief == 'ai':
        from ai_nation import NationPolicyAI
        nation.ai = NationPolicyAI(nation)
    deaths = Counter()
    snapshots, investments, violations, milestones = [], [], [], []
    career_history = []
    public_spend = private_spend = work = 0.0
    from food_economy import begin_turn as prepare_food_opening
    prepare_food_opening(region, 0)
    opening = len(region.resident_agents()) if hasattr(region, 'resident_agents') else sum(not a.is_corporation and not a.is_government for a in region.agents)
    last_investment = None
    pilot_intent = None
    for turn in range(1, turns + 1):
        if relief == 'emergency':
            from food_security import enact_nation_food_response
            enact_nation_food_response(nation, turn)
        if public_steam_pilot and pilot_intent is None and system.has_tech(nation.name, 'steam_engines'):
            from intents import BuildIntent
            intent = BuildIntent(nation.name, region.name, 'steam_engines_prototype', submitted_turn=turn - 1)
            ok, message = intent.execute({region.name: region}, {nation.name: nation}, turn - 1)
            if not ok:
                raise RuntimeError('Public steam pilot could not be commissioned: ' + message)
            pilot_intent = intent
        if variant == 'public' and system.get_refinement_xp(nation.name, 'steam_engines') < 100:
            if system.get_engineering_program(nation.name, 'steam_engines')['status'] != 'active':
                system.set_engineering_program(nation, 'steam_engines', 100, 'performance', t=turn - 1)
        found, _ = step_turn(turn, [region], nations=[nation], pair_orders=[],
                             currencies=[nation.currency], gameplay_flags=gameplay_flags)
        violations.extend(found)
        deaths.update(getattr(region, 'deaths_by_cause_this_turn', {}))
        from career_transitions import populations
        from copy import deepcopy
        career_history.append({'turn': turn, 'adult_professions': dict(populations(region, turn)),
            'departures': deepcopy(getattr(region, 'career_transition_state', {}).get('budgets', {})),
            'food_produced': region.production_log.get(Goods.food, [0])[-1],
            'food_foraged': getattr(region, 'food_foraged_this_turn', 0),
            'food_price': region.recipes[Goods.food]['price'],
            'food_balance': deepcopy(getattr(region, 'food_history', [{}])[-1]),
            'effective_farm_work': sum(value for row in getattr(region, 'work_allocations', {}).get('people', {}).values()
                                       for key, value in row['activities'].items() if key in region.farms),
            'soil_fertility': region.soil_fertility, 'water_pollution': region.pollution_water,
            'underfed': diagnose_tile(region)['underfed_residents'],
            'starvation_deaths': deaths.get('starvation', 0)})
        # Observe every completed turn, including the control and dissolved firms.
        sample = observe_firm_market(region, firm, turn)[-1]
        delivery = getattr(region, 'engineering_deliveries', {}).get('steam_engines', {})
        public_spend += delivery.get('public_spent', 0)
        private_spend += delivery.get('private_spent', 0)
        work += sum(r['work'] for r in getattr(region, 'technology_usage', {}).values()
                    if r['tech_id'] == 'steam_engines')
        investment = getattr(firm, 'last_technology_investment', None)
        if investment and investment['project_id'] != last_investment:
            investments.append(dict(investment))
            last_investment = investment['project_id']
        tier = system.get_tech_tier(nation.name, 'steam_engines')
        if tier and not any(m['tier'] == tier for m in milestones):
            milestones.append({'turn': turn, 'tier': tier})
        if turn in (20, 50, 100) or turn == turns:
            snapshots.append({'turn': turn,
                'capability': system.get_refinement_xp(nation.name, 'steam_engines'), 'tier': tier,
                'current_design_maturity': system.get_commercial_maturity(nation.name, 'steam_engines'),
                'maturity_by_generation': dict(getattr(system, 'tech_commercial_maturity', {}).get(nation.name, {}).get('steam_engines', {})),
                'public_engineering_spend': public_spend, 'private_engineering_spend': private_spend,
                'installation_spend': getattr(firm, 'technology_adoption_spent', 0),
                'firm_cash': firm.cash, 'firm_alive': firm.alive, 'firm_is_corporation': firm.is_corporation,
                'employees': len(firm.employees), 'sales_last_turn': sample['revenue'],
                'sales_mean_last_8_turns': sum(s['revenue'] for s in firm.technology_market_history) / len(firm.technology_market_history),
                'installed_design_quote': quote_recipe(nation,
                    BUILDING_RECIPES['steam_engines_prototype'], system).cost if tier else None,
                'recorded_operating_result_last_turn': sample['revenue'] - sample['operating_cost'],
                'productive_machine_work': work,
                'private_assets': [dict(b.technology_designs) for b in region.buildings
                                  if getattr(b, 'private_owner_id', None) == firm.id],
                'pending_projects': [{'action': getattr(p, 'adoption_action', 'public'), 'status': p.status,
                                      'progress': p.progress_pct, 'reason': p.stall_reason}
                                     for p in region.construction_projects],
                'latest_decision': getattr(firm, 'technology_adoption_decisions', {}).get('steam_engines'),
                'engineering_constraint': system.engineering_status(nation, 'steam_engines', turn)['constraint'],
                'living_households': sum(a.alive and not a.is_corporation and not a.is_government for a in region.agents),
                'hungry_households': sum(a.alive and not a.is_corporation and not a.is_government
                                         and a.hungry_steps > 0 for a in region.agents),
                'food_security': diagnose_tile(region),
                'adult_professions': __import__('career_transitions').populations(region, turn),
                'career_transitions': __import__('copy').deepcopy(getattr(region, 'career_transition_state', {})),
                'deaths_by_cause': dict(deaths),
                'firm_wage': firm.wage,
                'treasury_cash': nation.government.agent.cash})
    result = {'variant': variant, 'seed': seed, 'turns': turns, 'opening_households': opening,
            'snapshots': snapshots, 'career_history': career_history,
            'investments': investments, 'capability_milestones': milestones,
            'currency_audit_violations': violations,
            'food_conservation': getattr(region, 'food_conservation_history', []),
            'food_history': getattr(region, 'food_history', []),
            'food_initialization': getattr(region, 'food_initialization', {}),
            'farms_at_end': deepcopy(getattr(region, 'farms', {})),
            'work_at_end': deepcopy(getattr(region, 'work_allocations', {})),
            'programs_at_end': deepcopy(getattr(region, 'production_programs', [])),
            'settings': {'labor_policy': labor_policy, 'relief': relief,
                         'owner_planning': owner_planning,
                         'steam_scope': 'regional_pilot' if public_steam_pilot else 'private',
                         'national_ai': nation.ai is not None},
            'source_signature': signature,
            'python_hash_seed': os.environ.get('PYTHONHASHSEED', 'unfixed'),
            'assumptions': 'One authored commons region with abundant modeled forestry output; normal canonical turns, markets, labor, finance and innovation. Public strategy renews performance funding at each milestone; no recurring subsidies or fabricated sales. Low demand has 18 opening residents with 40 cash each versus 75 with 250; all variants use the same firm and initial design except public starts without steam knowledge. Control disables private adoption. These are authored strategy checks, not identical-economy causal comparisons.'}
    if public_steam_pilot:
        result['public_steam_pilot'] = {'commissioned': pilot_intent is not None,
            'cost': pilot_intent.project.recipe.cost if pilot_intent else 0,
            'status': pilot_intent.project.status if pilot_intent else 'unavailable',
            'physical_materials': {g.name: q for g, q in pilot_intent.project.materials_delivered.items()} if pilot_intent else {}}
    result['source_signature_end'] = source_signature()
    result['source_unchanged'] = result['source_signature_end'] == signature
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=('commercial', 'public', 'low_demand', 'control'), required=True)
    parser.add_argument('--seed', type=int, default=4243)
    parser.add_argument('--turns', type=int, default=100)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--public-steam-pilot', action='store_true', help='Commission one treasury-funded regional installation through normal construction.')
    parser.add_argument('--labor-policy', choices=('frozen', 'responsive'), default='frozen')
    parser.add_argument('--relief', choices=('ordinary', 'emergency', 'ai'), default='ordinary')
    parser.add_argument('--owner-planning', choices=('authored', 'autonomous'), default='authored')
    args = parser.parse_args()
    with redirect_stdout(io.StringIO()):
        result = run_campaign(args.variant, args.seed, args.turns, public_steam_pilot=args.public_steam_pilot,
                              labor_policy=args.labor_policy, relief=args.relief, owner_planning=args.owner_planning)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'variant': args.variant, 'final': result['snapshots'][-1],
                      'investments': len(result['investments']),
                      'audit_violations': len(result['currency_audit_violations'])}, indent=2))
