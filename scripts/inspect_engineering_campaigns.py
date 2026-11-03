"""Read-only economic and demographic telemetry for the engineering acceptance run.

Wraps its original runner; verifies the resulting acceptance snapshots still match.
Each invocation must be a fresh process because engine registries are global.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sitecustomize
from scripts import audit_engineering_campaigns as campaign
from goods import Goods
import region_production


def last(region, field, default=None):
    rows = getattr(region, field, ())
    return rows[-1] if rows else default


def inspect(variant, baseline=None, public_steam_pilot=False):
    original_create, original_step = campaign.create_campaign, campaign.step_turn
    context, rows, events, staffing = {}, [], [], []
    investments = {}
    actual_production = {}
    totals = Counter()

    original_produce = region_production.produce_corporation
    def produce(region, actor, recipe, output, *args, **kwargs):
        before = actor.inv_get(output, 0)
        result = original_produce(region, actor, recipe, output, *args, **kwargs)
        if context and actor is context['world'][2]:
            actual_production[getattr(region, '_last_turn', 0)] = {
                'good': output.name, 'quantity': actor.inv_get(output, 0) - before}
        return result
    region_production.produce_corporation = produce

    def snapshot(turn):
        nation, region, firm, system = context['world']
        live = [a for a in region.agents if a.alive]
        persons = [a for a in live if not a.is_corporation and not a.is_government]
        for actor in live:
            investment = getattr(actor, 'last_technology_investment', None)
            if investment is not None:
                investments.setdefault(investment['project_id'], {
                    **investment, 'firm_id': actor.id,
                    'firm': getattr(actor, 'company_name', None), 'output': actor.output.name})
        journal = [e for e in getattr(region, 'economic_events', ()) if e['turn'] == turn]
        sample = campaign.observe_firm_market(region, firm, turn)[-1] if turn else {}
        good_rows = {}
        for good in (Goods.food, Goods.wood, Goods.furniture, Goods.iron, Goods.iron_ore, Goods.coal):
            production = region.production_log.get(good, ())
            good_rows[good.name] = {
                'price': region.recipes[good]['price'],
                'produced': production[-1] if production else 0,
                'inventory': sum(a.inv_get(good, 0) for a in live),
                'sold': sum(e['quantity'] for e in journal if e['kind'] == 'spot_sale'
                            and e.get('good') == good.name),
                'independent_producers': sum(a.output == good and a.employer is None for a in persons),
            }
        return {
            'turn': turn, 'residents': len(persons),
            'children': sum(getattr(a, 'is_native_child', False) for a in persons),
            'corporations': sum(a.is_corporation for a in live),
            'companies': [{'id': a.id, 'name': getattr(a, 'company_name', None),
                'output': a.output.name, 'workers': len(a.employees), 'cash': a.cash,
                'contractor': getattr(a, 'is_construction_company', False)}
                for a in live if a.is_corporation],
            'assets': [{'recipe': b.name, 'owner_id': getattr(b, 'private_owner_id', None),
                'designs': dict(getattr(b, 'technology_designs', {}))} for b in region.buildings],
            'employed_residents': sum(a.employer is not None for a in persons),
            'hungry': sum(a.hungry_steps > 0 for a in persons),
            'resident_cash': sum(a.cash for a in persons),
            'resident_deposits': sum(region.bank.deposits.get(a, 0) for a in persons),
            'births': getattr(region, 'births_this_turn', 0),
            'deaths': dict(getattr(region, 'deaths_by_cause_this_turn', {})),
            'gdp_nominal_reference_value': last(region, 'gdp_log', 0),
            'cost_of_living': getattr(region, 'cost_of_living', None),
            'goods': good_rows,
            'firm': {'cash': firm.cash, 'alive': firm.alive,
                'output_good': firm.output.name,
                'physical_production': actual_production.get(turn, {'good': firm.output.name, 'quantity': 0}),
                'corporation': firm.is_corporation, 'employees': [a.id for a in firm.employees],
                'wage': firm.wage, 'cash_sales': sample.get('revenue', 0),
                'produced': sample.get('produced', 0), 'operating_cost': sample.get('operating_cost', 0),
                'inventory': {g.name: firm.inv_get(g, 0) for g in (Goods.food, Goods.wood, Goods.furniture)},
                'deposits': region.bank.deposits.get(firm, 0),
                'debt': sum(max(0, loan.principle - loan.principle_paid) for loan in firm.loans),
                'strikers': sum(getattr(a, 'is_striking', False) for a in firm.employees),
                'revolting_workers': sum(getattr(a, 'in_revolt', False) for a in firm.employees),
                'pollution_withholding_workers': [a.id for a in firm.employees
                    if a.id in getattr(region, 'pollution_revolt_ids', set())],
                'hungry_workers': sum(a.hungry_steps > 0 for a in firm.employees),
                'broken_machinery': getattr(firm, 'broken_machinery', 0),
                'machines': getattr(firm, 'machinery_level', 0)},
            'bank': {'capital': region.bank.capital, 'deposits': region.bank.total_deposits,
                'loans_outstanding': region.bank.total_liabilities, 'frozen': region.bank.is_frozen,
                'interest_rate': region.bank.interest_rate},
            'politics': {'regime': nation.regime_type, 'legitimacy': nation.legitimacy,
                'ruling_faction': nation.ruling_faction,
                'protest_energy': last(region, 'protest_energy_log'),
                'unrest': last(region, 'unrest_log'),
                'national_treasury': nation.government.agent.cash,
                'local_treasury': region.gov.agent.cash, 'local_tax_rate': region.gov.tax_rate},
            'environment': {field: getattr(region, field, None) for field in
                ('soil_fertility', 'nutrition_density', 'pollution_air', 'pollution_water', 'pollution_soil')},
            'health': {field: last(region, field) for field in ('disease_cases_log',
                'untreated_cases_log', 'medical_spending_private_log', 'medical_spending_public_log',
                'avg_health_attrition_log', 'workplace_accidents_log', 'strikers_log', 'sabotage_log')},
            'techs': sorted(system.get_discovered_techs(nation.name)),
            'machine_usage': [dict(u) for u in getattr(region, 'technology_usage', {}).values()
                if u['tech_id'] == 'steam_engines'],
            'labor_status_events': [e for e in getattr(region, 'labor_status_events', ()) if e['turn'] == turn],
        }

    def create(*args, **kwargs):
        world = original_create(*args, **kwargs)
        context['world'] = world
        rows.append(snapshot(0))
        return world

    def step(turn, tiles, **kwargs):
        nation, region, firm, system = context['world']
        before = {a.id: a for a in firm.employees}
        result = original_step(turn, tiles, **kwargs,
            on_event=lambda t, kind, message: events.append({'turn': t, 'kind': kind, 'message': message}))
        row = snapshot(turn)
        rows.append(row)
        totals['births'] += row['births']
        totals.update({f'deaths_{cause}': count for cause, count in row['deaths'].items()})
        after = {a.id: a for a in firm.employees}
        if before.keys() != after.keys():
            departures = []
            for ident in sorted(before.keys() - after.keys()):
                actor = before[ident]
                departures.append({'id': ident, 'alive': actor.alive,
                    'death_cause': getattr(actor, 'death_cause', None),
                    'new_employer': getattr(getattr(actor, 'employer', None), 'id', None),
                    'hungry_steps': actor.hungry_steps,
                    'output': actor.output.name, 'corporation': actor.is_corporation})
            staffing.append({'turn': turn, 'before': sorted(before), 'after': sorted(after),
                'departures': departures, 'status_events': row['labor_status_events']})
        return result

    campaign.create_campaign, campaign.step_turn = create, step
    acceptance = campaign.run_campaign(variant, public_steam_pilot=public_steam_pilot)
    expected_path = baseline or ROOT / f'planning/reports/engineering_{variant}_seed4243_100.json'
    expected = json.loads(Path(expected_path).read_text())
    if json.loads(json.dumps(acceptance)) != expected:
        Path(f'/private/tmp/engineering-{variant}-diagnostic-mismatch.json').write_text(
            json.dumps({'actual': acceptance, 'expected': expected}, indent=2))
        raise AssertionError(f'{variant}: diagnostic replay diverged from saved acceptance snapshots')
    nation, region, firm, system = context['world']
    return {'variant': variant, 'seed': 4243, 'acceptance_matches': True,
        'totals': dict(totals), 'rows': rows, 'staffing_changes': staffing,
        'engine_events': events, 'regime_events': nation.regime_log,
        'all_private_investments': list(investments.values()),
        'tracked_firm_hiring_decisions': dict(Counter(e['reason']
            for e in getattr(region, 'labor_decision_log', ()) if e['firm_id'] == firm.id)),
        'tracked_firm_last_offers': [e for e in getattr(region, 'labor_decision_log', ())
            if e['firm_id'] == firm.id][-5:],
        'tracked_firm_lifetime_journal_summary': dict(Counter(
            e['reason'] for e in getattr(region, 'labor_status_events', ())
            if e.get('employer_before') == firm.id)),
        'units': 'Cash is Crown. GDP is output valued at current reference prices; it includes unsold output. Resident counts are live non-corporate non-government agents, not a census of families. Event counters are engine records.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=('commercial', 'public', 'low_demand', 'control'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, help='Acceptance JSON for the current rules; defaults to the original campaign.')
    parser.add_argument('--public-steam-pilot', action='store_true')
    args = parser.parse_args()
    with redirect_stdout(io.StringIO()):
        result = inspect(args.variant, args.baseline, args.public_steam_pilot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'variant': args.variant, 'matches': result['acceptance_matches'],
                      'totals': result['totals'], 'staffing': result['staffing_changes']}, default=str))
