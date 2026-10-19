"""Conserved cotton procurement and contested cloth settlement for the small scenario."""

from __future__ import annotations

from collections import defaultdict, deque

import forex as fx
from goods import Goods


FREIGHT_PER_EDGE = 0.15
CLOTH_TAX_RATE = 0.06
COTTON_TAX_RATE = 0.04
MAX_DELIVERED_CLOTH_PRICE = 12.5


def _ordinary(person):
    return (person.alive and not person.is_corporation and not person.is_government
            and not person.is_trader and not getattr(person, 'is_lord', False))


def initialize_market(world):
    state = world['scenario_state']
    state['cloth_buyer_ids'] = {
        region.name: [a.id for a in sorted(region.agents, key=lambda a: a.id)
                      if _ordinary(a)][:14]
        for region in world['tiles'] if region.scenario_location == 'capital'
    }
    # These funded household orders are an explicit starting endowment. Their
    # balances are counted in the initial currency stock and never refilled.
    for region in world['tiles']:
        buyer_ids = state['cloth_buyer_ids'].get(region.name, ())
        for person in region.agents:
            if person.id in buyer_ids:
                person.cash += 120.0
    state['initial_buyer_endowment_each'] = 120.0
    state['market_sales'] = []
    state['market_summary'] = {}
    state['firm_statements'] = {}
    state['cotton_purchases'] = []
    state['market_cash_baseline'] = fx.audit_currency_total(world['tiles'], world['currencies'][0])
    state['machinery_projects'] = []


def start_machinery_project(world, nation_name, turn, public_contribution=15):
    """Owner and government fund a two-turn project with physical inputs."""
    state = world['scenario_state']
    matches = [(region, firm) for region, firm in _firms(world)
               if region.owner_nation.name == nation_name]
    if not matches:
        return False, 'No operating textile mill.'
    region, firm = matches[0]
    if any(p['nation'] == nation_name and p['status'] == 'active'
           for p in state['machinery_projects']):
        return False, 'Machinery project already active.'
    owner = firm.owner
    gov = region.owner_nation.government.agent
    public_contribution = float(public_contribution)
    if public_contribution not in (0.0, 15.0):
        return False, 'Unsupported funding split.'
    owner_share = 45.0 - public_contribution
    if owner is None or owner.cash < owner_share or gov.cash < public_contribution:
        return False, f'Owner needs {owner_share:g} cash and sovereign treasury needs {public_contribution:g}.'
    sellers = {}
    for good, amount in ((Goods.iron, 2), (Goods.coal, 1)):
        seller = next((a for a in region.agents if a.alive and a is not firm and
                       a.inv_get(good, 0) >= amount), None)
        if seller is None:
            return False, f'Need {amount} physical {good.name} in {region.name}.'
        sellers[good] = seller
    iron_cost = 2 * region.recipes[Goods.iron]['price']
    coal_cost = region.recipes[Goods.coal]['price']
    if iron_cost + coal_cost + 8 > 45:
        return False, 'Input prices exceed the funded 45 cash budget.'
    owner.cash -= owner_share
    gov.cash -= public_contribution
    firm.cash += 45
    if public_contribution > 0:
        from run_trace import emit
        emit(region, kind='machinery_public_funding', record_class='transfer',
             phase='scenario_market',
             subject={'type': 'nation', 'id': nation_name},
             metric_id='finance.treasury_flow', unit=region.owner_nation.currency,
             after=-public_contribution,
             inputs={'tile': region.name, 'firm_id': firm.id,
                     'owner_contribution': owner_share,
                     'public_contribution': public_contribution})
    for good, amount, price in ((Goods.iron, 2, iron_cost),
                                (Goods.coal, 1, coal_cost)):
        seller = sellers[good]
        firm.cash -= price
        seller.cash += price
        seller.inv_add(good, -amount)
        firm.inv_add(good, amount)
    artisan = sellers[Goods.iron]
    firm.cash -= 8
    artisan.cash += 8
    project = {'nation': nation_name, 'firm_id': firm.id, 'start_turn': turn,
               'due_turn': turn + 2, 'status': 'active',
               'owner_paid': owner_share, 'public_paid': public_contribution,
               'iron_supplier_id': sellers[Goods.iron].id,
               'coal_supplier_id': sellers[Goods.coal].id}
    state['machinery_projects'].append(project)
    return True, 'Funded machinery work; completion in two turns.'


def _advance_machinery(world, turn):
    firms = {firm.id: firm for _, firm in _firms(world)}
    for project in world['scenario_state']['machinery_projects']:
        if project['status'] != 'active' or project['due_turn'] > turn:
            continue
        firm = firms.get(project['firm_id'])
        if firm is None or firm.inv_get(Goods.iron, 0) < 2 or firm.inv_get(Goods.coal, 0) < 1:
            project['status'] = 'stalled'
            continue
        firm.inv_add(Goods.iron, -2)
        firm.inv_add(Goods.coal, -1)
        firm.machinery_level += 1
        project['status'] = 'complete'
        project['completed_turn'] = turn


def _route(source, destination):
    if source is destination:
        return [source]
    pending = deque([(source, [source])])
    seen = {source.name}
    while pending:
        region, path = pending.popleft()
        for other in region.neighbors.values():
            if other.name in seen or getattr(other, 'wilderness', False):
                continue
            if other is destination:
                return path + [other]
            seen.add(other.name)
            pending.append((other, path + [other]))
    return None


def _freight_recipient(source):
    return next((a for a in source.agents if a.is_trader and a.alive), None)


def _firms(world):
    return [(region, a) for region in world['tiles'] for a in region.agents
            if a.alive and a.is_corporation and a.output == Goods.cloth
            and str(a.company_name).endswith('Textile Mill')]


def _cotton_ask(field, grower, purpose='sale_offer', trace_event_ids=None):
    ask = (1.5 + 0.12 * grower.wage if grower.is_corporation
           else field.recipes[Goods.cotton]['price'])
    from run_trace import emit
    event_id = emit(
        field, kind='scenario_cotton_ask', record_class='calculation',
        phase='scenario_market',
        subject={'type': 'tile', 'id': field.name, 'good': 'cotton',
                 'seller_id': grower.id},
        metric_id='goods.seller_ask', unit='local_currency_per_unit',
        after=ask, formula_id='scenario.cotton_ask.v1',
        inputs={'purpose': purpose, 'corporation': grower.is_corporation,
                'wage': grower.wage if grower.is_corporation else None,
                'base': 1.5 if grower.is_corporation else None,
                'wage_coefficient': 0.12 if grower.is_corporation else None,
                'recipe_reference': field.recipes[Goods.cotton]['price'],
                'seller_nation_at_quote': getattr(
                    getattr(field, 'owner_nation', None), 'name', None),
                'seller_tile_at_quote': field.name,
                'currency': field.home_currency})
    if event_id is not None and trace_event_ids is not None:
        trace_event_ids.append(event_id)
    return ask


def _buy_cotton(world, turn):
    purchases = []
    for mill_region, firm in _firms(world):
        wanted = min(12, max(0, 16 - firm.inv_get(Goods.cotton, 0)))
        while wanted > 0:
            offers = []
            for field in world['tiles']:
                if (field.scenario_location != 'borderland' or
                        field.owner_nation is not mill_region.owner_nation):
                    continue
                path = _route(field, mill_region)
                if path is None:
                    continue
                freight = FREIGHT_PER_EDGE * (len(path) - 1)
                for grower in field.agents:
                    if grower.alive and grower.output == Goods.cotton and grower.inv_get(Goods.cotton, 0) > 0:
                        seller_currency = field.home_currency
                        buyer_currency = mill_region.home_currency
                        seller_nation = getattr(
                            getattr(field, 'owner_nation', None), 'name', None)
                        buyer_nation = getattr(
                            getattr(mill_region, 'owner_nation', None), 'name', None)
                        ask_event_ids = []
                        ask = _cotton_ask(
                            field, grower, trace_event_ids=ask_event_ids)
                        from run_trace import emit
                        delivered_quote_event_id = emit(
                            field, kind='scenario_cotton_delivered_quote',
                            record_class='calculation', phase='scenario_market',
                            subject={'type': 'tile', 'id': field.name,
                                     'good': 'cotton', 'seller_id': grower.id,
                                     'buyer_id': firm.id},
                            metric_id='goods.delivered_quote',
                            unit='local_currency_per_unit', after=ask + freight,
                            formula_id='scenario.delivered_quote.v1',
                            inputs={'ask': ask, 'freight': freight,
                                    'buyer_cash': firm.cash,
                                    'price_basis': 'delivered_to_mill',
                                    'origin_tile': field.name,
                                    'destination_tile': mill_region.name,
                                    'seller_nation_at_quote': seller_nation,
                                    'buyer_nation_at_quote': buyer_nation,
                                    'seller_currency': seller_currency,
                                    'buyer_currency': buyer_currency,
                                    'counterparty_currency_mismatch': (
                                        seller_currency != buyer_currency),
                                    'currency_conversion_applied': False,
                                    'currency': seller_currency},
                            cause_event_ids=ask_event_ids or None)
                        offers.append((ask + freight, field.name, grower.id,
                                       field, grower, freight,
                                       delivered_quote_event_id))
            if not offers:
                break
            (delivered, _, _, field, grower, freight,
             selected_quote_event_id) = min(offers, key=lambda row: row[:3])
            if firm.cash + 1e-9 < delivered:
                break
            carrier = _freight_recipient(field)
            if freight > 0 and carrier is None:
                break
            price = delivered - freight
            firm.cash -= delivered
            tax = round(price * COTTON_TAX_RATE, 6)
            grower.cash += price - tax
            field.gov.agent.cash += tax
            field.gov.record_income(turn, 'cotton_sales_tax', tax)
            from run_trace import emit
            emit(field, kind='scenario_cotton_sales_tax', record_class='transfer',
                 phase='scenario_market',
                 subject={'type': 'nation', 'id': field.owner_nation.name},
                 metric_id='finance.treasury_flow', unit=field.owner_nation.currency,
                 after=tax,
                 inputs={'tile': field.name, 'grower_id': grower.id,
                         'firm_id': firm.id, 'cotton_price': price,
                         'freight': freight, 'tax_rate': COTTON_TAX_RATE},
                 cause_event_ids=([selected_quote_event_id]
                                  if selected_quote_event_id else None))
            if carrier is not None:
                carrier.cash += freight
            grower.inv_add(Goods.cotton, -1)
            old_stock = firm.inv_get(Goods.cotton, 0)
            old_cost = firm.cost_get(Goods.cotton, 3.0)
            firm.inv_add(Goods.cotton, 1)
            firm.cost_set(Goods.cotton,
                          (old_stock * old_cost + delivered) / (old_stock + 1))
            emit(field, kind='scenario_cotton_paid_price', record_class='observation',
                 phase='scenario_market',
                 subject={'type': 'tile', 'id': field.name, 'good': 'cotton',
                          'seller_id': grower.id, 'buyer_id': firm.id},
                 metric_id='goods.transaction_price',
                 unit='local_currency_per_unit', after=delivered,
                 inputs={'seller_receipt_before_tax': price, 'freight': freight,
                         'quantity': 1, 'price_basis': 'delivered_to_mill',
                         'quote_turn': int(turn),
                         'origin_tile': field.name,
                         'destination_tile': mill_region.name,
                         'seller_nation_at_quote': seller_nation,
                         'buyer_nation_at_quote': buyer_nation,
                         'seller_currency': seller_currency,
                         'buyer_currency': buyer_currency,
                         'counterparty_currency_mismatch': (
                             seller_currency != buyer_currency),
                         'currency_conversion_applied': False,
                         'currency': seller_currency,
                         'selected_quote_event_id': selected_quote_event_id},
                 cause_event_ids=([selected_quote_event_id]
                                  if selected_quote_event_id else None))
            wanted -= 1
            from collective_trace_clock import stamp
            purchases.append(stamp(field, {'turn': turn, 'mill': mill_region.name,
                              'origin': field.name, 'grower_id': grower.id,
                              'firm_id': firm.id, 'price': price, 'freight': freight,
                              'public_tax': tax, 'tax_nation': field.owner_nation.name}))
    return purchases


def _cloth_ask(region, firm, trace_event_ids=None):
    recipe = region.recipes[Goods.cloth]
    # Posted terms derive from the real wage offer and productive recipe.
    productive_slots = float(recipe['production']) * (
        1.0 + 0.40 * min(3, max(0, firm.machinery_level - firm.broken_machinery - 1)))
    cotton_cost = firm.cost_get(Goods.cotton, region.recipes[Goods.cotton]['price'])
    local_offers = [
        _cotton_ask(field, grower, purpose='cloth_input_estimate') + FREIGHT_PER_EDGE
        for field in region.neighbors.values()
        if field.owner_nation is region.owner_nation and field.scenario_location == 'borderland'
        for grower in field.agents
        if grower.alive and grower.output == Goods.cotton and grower.inv_get(Goods.cotton, 0) > 0
    ]
    if local_offers:
        cotton_cost = min(cotton_cost, min(local_offers))
    ask = round(8.0 + float(firm.wage) * 0.7
                + (2.0 * cotton_cost)
                / max(1.0, productive_slots), 3)
    from run_trace import emit
    event_id = emit(
        region, kind='scenario_cloth_ask', record_class='calculation',
        phase='scenario_market',
        subject={'type': 'tile', 'id': region.name, 'good': 'cloth',
                 'seller_id': firm.id},
        metric_id='goods.seller_ask', unit='local_currency_per_unit',
        after=ask, formula_id='scenario.cloth_ask.v1',
        inputs={'base': 8.0, 'wage': float(firm.wage),
                'wage_coefficient': 0.7, 'cotton_cost': cotton_cost,
                'cotton_quantity': 2.0, 'productive_slots': productive_slots,
                'machinery_level': firm.machinery_level,
                'broken_machinery': firm.broken_machinery,
                'local_offer_count': len(local_offers),
                'round_digits': 3,
                'seller_nation_at_quote': getattr(
                    getattr(region, 'owner_nation', None), 'name', None),
                'seller_tile_at_quote': region.name,
                'currency': region.home_currency})
    if event_id is not None and trace_event_ids is not None:
        trace_event_ids.append(event_id)
    return ask


def _sell_cloth(world, turn):
    state = world['scenario_state']
    sales = []
    for market in (r for r in world['tiles'] if r.scenario_location == 'capital'):
        buyers = [a for a in market.agents
                  if a.id in state['cloth_buyer_ids'].get(market.name, ()) and _ordinary(a)]
        for buyer in sorted(buyers, key=lambda a: a.id):
            if buyer.inv_get(Goods.cloth, 0) >= 1:
                continue
            offers = []
            for source, firm in _firms(world):
                if firm.inv_get(Goods.cloth, 0) <= 0:
                    continue
                path = _route(source, market)
                if path is None:
                    continue
                freight = FREIGHT_PER_EDGE * (len(path) - 1)
                if freight and _freight_recipient(source) is None:
                    continue
                ask_event_ids = []
                ask = _cloth_ask(source, firm, trace_event_ids=ask_event_ids)
                delivered = ask + freight
                from run_trace import emit
                seller_currency = source.home_currency
                buyer_currency = market.home_currency
                seller_nation = getattr(
                    getattr(source, 'owner_nation', None), 'name', None)
                buyer_nation = getattr(
                    getattr(market, 'owner_nation', None), 'name', None)
                delivered_quote_event_id = emit(
                     source, kind='scenario_cloth_delivered_quote',
                     record_class='calculation', phase='scenario_market',
                     subject={'type': 'tile', 'id': source.name, 'good': 'cloth',
                              'seller_id': firm.id, 'buyer_id': buyer.id},
                     metric_id='goods.delivered_quote',
                     unit='local_currency_per_unit', after=delivered,
                     formula_id='scenario.delivered_quote.v1',
                     inputs={'ask': ask, 'freight': freight,
                             'buyer_cash': buyer.cash,
                             'ceiling': MAX_DELIVERED_CLOTH_PRICE,
                             'affordable': delivered <= min(MAX_DELIVERED_CLOTH_PRICE,
                                                            buyer.cash),
                             'price_basis': 'delivered_to_household',
                             'origin_tile': source.name,
                             'destination_tile': market.name,
                             'seller_nation_at_quote': seller_nation,
                             'buyer_nation_at_quote': buyer_nation,
                             'seller_currency': seller_currency,
                             'buyer_currency': buyer_currency,
                             'counterparty_currency_mismatch': (
                                 seller_currency != buyer_currency),
                             'currency_conversion_applied': False,
                             'currency': seller_currency},
                     cause_event_ids=ask_event_ids or None)
                if delivered <= min(MAX_DELIVERED_CLOTH_PRICE, buyer.cash):
                    offers.append((delivered, firm.id, source, firm, ask, freight,
                                   delivered_quote_event_id))
            if not offers:
                continue
            (delivered, _, source, firm, ask, freight,
             selected_quote_event_id) = min(offers, key=lambda row: row[:2])
            buyer.cash -= delivered
            firm.cash += ask
            carrier = _freight_recipient(source)
            if freight:
                carrier.cash += freight
            firm.inv_add(Goods.cloth, -1)
            buyer.inv_add(Goods.cloth, 1)
            paid_event_id = emit(
                source, kind='scenario_cloth_paid_price',
                record_class='observation', phase='scenario_market',
                subject={'type': 'tile', 'id': source.name, 'good': 'cloth',
                         'seller_id': firm.id, 'buyer_id': buyer.id},
                metric_id='goods.transaction_price',
                unit='local_currency_per_unit', after=delivered,
                inputs={'seller_receipt_before_tax': ask, 'freight': freight,
                        'quantity': 1, 'price_basis': 'delivered_to_household',
                        'quote_turn': int(turn),
                        'origin_tile': source.name,
                        'destination_tile': market.name,
                        'seller_nation_at_quote': seller_nation,
                        'buyer_nation_at_quote': buyer_nation,
                        'seller_currency': seller_currency,
                        'buyer_currency': buyer_currency,
                        'counterparty_currency_mismatch': (
                            seller_currency != buyer_currency),
                        'currency_conversion_applied': False,
                        'currency': seller_currency,
                        'selected_quote_event_id': selected_quote_event_id},
                cause_event_ids=([selected_quote_event_id]
                                 if selected_quote_event_id else None))
            tax = round(ask * CLOTH_TAX_RATE, 6)
            firm.cash -= tax
            source.gov.agent.cash += tax
            source.gov.record_income(turn, 'cloth_sales_tax', tax)
            from run_trace import emit
            emit(source, kind='scenario_cloth_sales_tax', record_class='transfer',
                 phase='scenario_market',
                 subject={'type': 'nation', 'id': source.owner_nation.name},
                 metric_id='finance.treasury_flow', unit=source.owner_nation.currency,
                 after=tax,
                 inputs={'tile': source.name, 'firm_id': firm.id,
                         'buyer_id': buyer.id, 'cloth_price': ask,
                         'freight': freight, 'tax_rate': CLOTH_TAX_RATE},
                 cause_event_ids=[paid_event_id] if paid_event_id else None)
            from collective_trace_clock import stamp
            sales.append(stamp(source, {'turn': turn, 'origin': source.name,
                          'seller_nation': source.owner_nation.name,
                          'market': market.name, 'buyer_id': buyer.id,
                          'firm_id': firm.id, 'mill_receipt': ask,
                          'delivered_price': delivered, 'freight': freight,
                          'public_tax': tax}))
    return sales


def _consume_worn_cloth(world, turn):
    if turn % 2 != 0:
        return 0
    used = 0
    buyer_ids = world['scenario_state']['cloth_buyer_ids']
    for region in world['tiles']:
        ids = buyer_ids.get(region.name, ())
        for person in region.agents:
            if person.id in ids and person.alive and person.inv_get(Goods.cloth, 0) > 0:
                person.inv_add(Goods.cloth, -1)
                used += 1
    return used


def _sweep_sales_tax(world, sales, purchases=()):
    # Municipalities remit only collected scenario sales tax; the rest of
    # their cash, including household taxes, stays available locally.
    due = defaultdict(float)
    for sale in [*sales, *purchases]:
        due[sale['origin']] += sale['public_tax'] * 0.5
    transfers = []
    for region in world['tiles']:
        amount = min(region.gov.agent.cash, due[region.name])
        if amount > 0:
            region.gov.agent.cash -= amount
            region.owner_nation.government.agent.cash += amount
            transfers.append({'region': region.name,
                              'nation': region.owner_nation.name, 'amount': amount})
    return transfers


def settle_markets(world, turn):
    """Clear one funded order per buyer and reconcile the shared currency."""
    state = world['scenario_state']
    currency = world['currencies'][0]
    cash_before = fx.audit_currency_total(world['tiles'], currency)
    _advance_machinery(world, turn)
    consumed = _consume_worn_cloth(world, turn)
    purchases = _buy_cotton(world, turn)
    sales = _sell_cloth(world, turn)
    transfers = _sweep_sales_tax(world, sales, purchases)
    cash_after = fx.audit_currency_total(world['tiles'], currency)
    if abs(cash_after - cash_before) > 1e-4:
        world.setdefault('violations', []).append((turn, currency, cash_after - cash_before))
    # Preserve the full paid-transaction history for run reconstruction.
    state['market_sales'].extend(sales)
    state['cotton_purchases'].extend(purchases)
    summary = {}
    statements = {}
    for region, firm in _firms(world):
        own = [row for row in sales if row['firm_id'] == firm.id]
        bought = [row for row in purchases if row['firm_id'] == firm.id]
        name = region.owner_nation.name
        statements[name] = {
            'firm_id': firm.id, 'units_sold': len(own),
            'settled_receipts': round(sum(row['mill_receipt'] for row in own), 3),
            'input_spend': round(sum(row['price'] + row['freight'] for row in bought), 3),
            'sales_tax_paid': round(sum(row['public_tax'] for row in own), 3),
            'inventory_cloth': firm.inv_get(Goods.cloth, 0),
            'inventory_cotton': firm.inv_get(Goods.cotton, 0),
            'cash': round(firm.cash, 3), 'wage_offer': firm.wage,
            'employees': len(firm.employees),
        }
        summary[name] = {'units_sold': len(own),
                         'foreign_units': sum(row['market'] != region.name for row in own),
                         'sales_receipts': statements[name]['settled_receipts'],
                         'public_tax': statements[name]['sales_tax_paid']}
    state['market_summary'] = summary
    state['firm_statements'] = statements
    state['last_market_turn'] = turn
    state['last_cloth_used'] = consumed
    state['last_tax_remittances'] = transfers
    return sales
