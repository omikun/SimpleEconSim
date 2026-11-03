"""Observe food access without changing the engineering acceptance campaign.

Run each case in a fresh process. The complete acceptance result must still
equal the saved baseline; observers never move cash, food, or random state.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
import io
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sitecustomize
from scripts import audit_engineering_campaigns as campaign
from economy import actor_accounts
import econsim_live
from goods import Goods
import foraging
from government import Government
import nutrition
import person_death
import region_market
import region_finance


def inspect(variant, baseline, public_steam_pilot=False, *, seed=4243,
            labor_policy='frozen', relief='ordinary'):
    context = {}
    rows, meals, orders, transfers, deaths, phases, auctions = [], [], [], [], [], [], []
    forage = Counter()
    aid = Counter()
    original_create, original_step = campaign.create_campaign, campaign.step_turn

    def category(a):
        if a.is_government:
            return 'government'
        if a.is_corporation:
            return 'food_firms' if a.output == Goods.food else 'nonfood_firms'
        if a.employer is not None:
            return 'employees'
        return 'food_growers' if a.output == Goods.food else 'other_people'

    def actor(a, region):
        return {'id': a.id, 'category': category(a), 'output': a.output.name,
                'age': a.age(region._last_turn),
                'employer': getattr(a.employer, 'id', None),
                'cash': a.cash, 'deposits': region.bank.deposits.get(a, 0),
                'food': a.inv_get(Goods.food, 0),
                'foraged': getattr(a, 'food_foraged', 0),
                'purchased_counter': getattr(a, 'food_purchased', 0),
                'scrip': getattr(a, 'scrip_wallet', 0),
                'company_debt': getattr(a, 'company_debt', 0),
                'reserve_kcal': getattr(a, 'energy_reserve_kcal', 0),
                'hungry_steps': getattr(a, 'hungry_steps', 0),
                'wage': getattr(a.employer, 'wage', None)}

    def stocks(region):
        totals = Counter()
        for a in region.agents:
            if a.alive:
                totals[category(a)] += a.inv_get(Goods.food, 0)
        return dict(totals)

    def create(*args, **kwargs):
        world = original_create(*args, **kwargs)
        context['world'] = world
        context['workers'] = [a.id for a in world[2].employees]
        context['actors'] = {a.id: a for a in world[1].agents}
        return world

    original_meal = econsim_live.consume_daily_food
    def meal(a, *, region=None, turn=None):
        before = actor(a, region)
        before['need_kcal'] = nutrition.effective_calorie_need(a)
        before['baseline_need_kcal'] = getattr(a, 'calorie_need_kcal', nutrition.DAILY_NEED_KCAL)
        before['appetite'] = nutrition.appetite_units(a)
        eaten = original_meal(a, region=region, turn=turn)
        meals.append({'turn': turn, **before, 'eaten': eaten,
                      'deficit_kcal': a.calorie_deficit_kcal,
                      'reserve_after': a.energy_reserve_kcal})
        return eaten

    original_bid, original_ask = region_market.calculate_bid, region_market.calculate_ask
    def bid(region, a, good, price, *args, **kwargs):
        result = original_bid(region, a, good, price, *args, **kwargs)
        if good == Goods.food:
            quantity, reason = result if kwargs.get('return_reason') else (result, None)
            orders.append({'turn': region._last_turn, 'side': 'bid',
                           **actor(a, region), 'quantity': quantity, 'reason': reason,
                           'price': price, 'remaining_cash': a.remainingCash})
        return result

    def ask(region, a, good, price, *args, **kwargs):
        result = original_ask(region, a, good, price, *args, **kwargs)
        if good == Goods.food:
            quantity, reason = result if kwargs.get('return_reason') else (result, None)
            orders.append({'turn': region._last_turn, 'side': 'ask',
                           'id': a.id, 'category': category(a),
                           'stock': a.inv_get(good, 0), 'quantity': quantity,
                           'reason': reason, 'price': price})
        return result

    original_record = actor_accounts.record
    def record(region, kind, **kwargs):
        event = original_record(region, kind, **kwargs)
        if event['good'] == 'food' or kind in ('cash_wage', 'scrip_wage'):
            transfers.append(dict(event))
        return event

    original_clear = region_market.clear_discriminatory
    def clear(region, good, ref, total_asks, total_bids, imp_pool, agents, t,
              local_orders=None):
        audit = None
        if good == Goods.food and local_orders is not None:
            audit = {'turn': t, 'reference': ref, 'total_asks': total_asks,
                     'total_bids': total_bids, 'buyers': [], 'sellers': []}
            for side in ('buyers', 'sellers'):
                audit[side] = [
                    {'id': r['agent'].id, 'category': category(r['agent']),
                     'quantity': r['quantity'], 'limit': r['limit_price'],
                     'cash': r['agent'].cash, 'stock': r['agent'].inv_get(Goods.food, 0)}
                    for r in local_orders.get(side, ())]
        result = original_clear(region, good, ref, total_asks, total_bids,
                                imp_pool, agents, t, local_orders=local_orders)
        if audit is not None:
            by_id = {a.id: a for a in agents}
            for r in audit['buyers']:
                r['received'] = by_id[r['id']].inv_get(Goods.food, 0) - r['stock']
            auctions.append(audit)
        return result

    original_forage = foraging.forage_tile
    def gather(region, t):
        result = original_forage(region, t)
        forage[t] += result
        return result

    original_death = person_death.record_person_death
    def death(region, a, turn, cause, **kwargs):
        before = actor(a, region)
        result = original_death(region, a, turn, cause, **kwargs)
        if result:
            deaths.append({'turn': turn, 'cause': cause, **before,
                           'food_stocks_at_death': stocks(region),
                           'employer_food': a.employer.inv_get(Goods.food, 0)
                               if a.employer is not None else None,
                           'price': region.food_price})
        return result

    original_aid = Government.provide_food_aid
    def provide_aid(government, t, agents, food_price, region=None):
        result = original_aid(government, t, agents, food_price, region=region)
        aid[t] += result
        return result

    def wrap_phase(module, name):
        original = getattr(module, name)
        def call(region, t, *args, **kwargs):
            before = stocks(region)
            before_people = {a.id: a.inv_get(Goods.food, 0) for a in region.agents
                             if a.alive and not a.is_corporation and not a.is_government}
            result = original(region, t, *args, **kwargs)
            after_people = {a.id: a.inv_get(Goods.food, 0) for a in region.agents
                            if a.alive and not a.is_corporation and not a.is_government}
            phases.append({'turn': t, 'phase': name, 'before': before,
                           'after': stocks(region),
                           'person_food_gains': sum(max(0, amount - before_people.get(ident, 0))
                                                    for ident, amount in after_people.items())})
            return result
        setattr(module, name, call)

    def step(t, tiles, **kwargs):
        nation, region, firm, system = context['world']
        result = original_step(t, tiles, **kwargs)
        context['actors'].update({a.id: a for a in region.agents})
        today = [m for m in meals if m['turn'] == t]
        people = [a for a in region.agents if a.alive and not a.is_corporation
                  and not a.is_government]
        bids = [o for o in orders if o['turn'] == t and o['side'] == 'bid']
        asks = [o for o in orders if o['turn'] == t and o['side'] == 'ask']
        rows.append({'turn': t, 'people': len(people), 'price': region.food_price,
                     'production': region.production_log[Goods.food][-1],
                     'foraged': forage[t], 'stocks': stocks(region),
                     'need_units': sum(m['need_kcal'] for m in today) / 500,
                     'baseline_need_units': sum(m['baseline_need_kcal'] for m in today) / 500,
                     'eaten': sum(m['eaten'] for m in today),
                     'deficit_units': sum(m['deficit_kcal'] for m in today) / 500,
                     'people_with_deficit': sum(m['deficit_kcal'] > 0 for m in today),
                     'bids': dict(Counter({c: sum(o['quantity'] for o in bids if o['category'] == c)
                                            for c in set(o['category'] for o in bids)})),
                     'asks': sum(o['quantity'] for o in asks),
                     'charity_food': region.charity.food_inventory,
                     'charity_cash': region.charity.agent.cash,
                     'charity_deposits': region.bank.deposits.get(region.charity.agent, 0),
                     'charity_log': dict(region.charity.log),
                     'public_aid_units': aid[t],
                     'public_food': region.gov.food_inventory,
                     'granary_food': getattr(region, 'granary_stock', 0),
                     'emergency_policy': region.gov.emergency_food_policy,
                     'local_treasury': region.gov.agent.cash,
                     'national_treasury': nation.government.agent.cash,
                     'firm_food': firm.inv_get(Goods.food, 0),
                     'firm_cash': firm.cash,
                     'firm_workers': [a.id for a in firm.employees],
                     'food_holders': sorted(
                         [{'id': a.id, 'category': category(a), 'food': a.inv_get(Goods.food, 0)}
                          for a in region.agents if a.alive and a.inv_get(Goods.food, 0) > 0],
                         key=lambda x: x['food'], reverse=True)[:10]})
        return result

    campaign.create_campaign, campaign.step_turn = create, step
    econsim_live.consume_daily_food = meal
    region_market.calculate_bid, region_market.calculate_ask = bid, ask
    region_market.clear_discriminatory = clear
    actor_accounts.record, foraging.forage_tile = record, gather
    person_death.record_person_death = death
    Government.provide_food_aid = provide_aid
    wrap_phase(region_finance, 'redeem_company_scrip')
    wrap_phase(region_market, 'trade')
    acceptance = campaign.run_campaign(variant, seed=seed, public_steam_pilot=public_steam_pilot,
                                      labor_policy=labor_policy, relief=relief)
    expected = json.loads(Path(baseline).read_text())
    if json.loads(json.dumps(acceptance)) != expected:
        raise AssertionError('Food observers changed the acceptance result')
    return {'variant': variant, 'public_steam_pilot': public_steam_pilot,
            'acceptance_matches': True, 'original_workers': context['workers'],
            'rows': rows, 'meals': meals, 'orders': orders,
            'food_transfers': transfers, 'deaths': deaths, 'phases': phases,
            'auctions': auctions}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--public-steam-pilot', action='store_true')
    parser.add_argument('--seed', type=int, default=4243)
    parser.add_argument('--labor-policy', choices=('frozen', 'responsive'), default='frozen')
    parser.add_argument('--relief', choices=('ordinary', 'emergency', 'ai'), default='ordinary')
    args = parser.parse_args()
    with redirect_stdout(io.StringIO()):
        result = inspect(args.variant, args.baseline, args.public_steam_pilot, seed=args.seed,
                         labor_policy=args.labor_policy, relief=args.relief)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix == '.gz':
        with gzip.open(args.output, 'wt') as stream:
            json.dump(result, stream, separators=(',', ':'))
    else:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'matches': result['acceptance_matches'],
                      'deaths': dict(Counter(d['cause'] for d in result['deaths'])),
                      'final': result['rows'][-1]}))
