"""Conserved cotton procurement and contested cloth settlement for the small scenario."""

from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change

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
                _public_write = begin_public_change(None, person)
                person.cash += 120.0
                finish_public_change(_public_write, 'labor_frontier_market:initialize_market',
                                     inputs={'source_writer': 'labor_frontier_market.py:initialize_market:affe9419d54e8684:1', 'semantic_operation_id': locals().get('operation_id')})
    state['initial_buyer_endowment_each'] = 120.0
    state['market_sales'] = []
    state['market_summary'] = {}
    state['firm_statements'] = {}
    state['cotton_purchases'] = []
    state['market_price_history'] = {}
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
    _public_write = begin_public_change(None, owner)
    owner.cash -= owner_share
    finish_public_change(_public_write, 'labor_frontier_market:start_machinery_project',
                         inputs={'source_writer': 'labor_frontier_market.py:start_machinery_project:e9c40f02059daa9e:1', 'semantic_operation_id': locals().get('operation_id')})
    _public_write = begin_public_change(None, gov)
    gov.cash -= public_contribution
    finish_public_change(_public_write, 'labor_frontier_market:start_machinery_project',
                         inputs={'source_writer': 'labor_frontier_market.py:start_machinery_project:a4daf06b9eb67316:1', 'semantic_operation_id': locals().get('operation_id')})
    _public_write = begin_public_change(None, firm)
    firm.cash += 45
    finish_public_change(_public_write, 'labor_frontier_market:start_machinery_project',
                         inputs={'source_writer': 'labor_frontier_market.py:start_machinery_project:ec3ef6c5c9b405cd:1', 'semantic_operation_id': locals().get('operation_id')})
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
        _public_write = begin_public_change(None, firm)
        firm.cash -= price
        finish_public_change(_public_write, 'labor_frontier_market:start_machinery_project',
                             inputs={'source_writer': 'labor_frontier_market.py:start_machinery_project:9e806d4d39fd2c45:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, seller)
        seller.cash += price
        finish_public_change(_public_write, 'labor_frontier_market:start_machinery_project',
                             inputs={'source_writer': 'labor_frontier_market.py:start_machinery_project:455e4aaec8281444:1', 'semantic_operation_id': locals().get('operation_id')})
        seller.inv_add(good, -amount)
        firm.inv_add(good, amount)
    artisan = sellers[Goods.iron]
    _public_write = begin_public_change(None, firm)
    firm.cash -= 8
    finish_public_change(_public_write, 'labor_frontier_market:start_machinery_project',
                         inputs={'source_writer': 'labor_frontier_market.py:start_machinery_project:20ba43b3021ec194:1', 'semantic_operation_id': locals().get('operation_id')})
    _public_write = begin_public_change(None, artisan)
    artisan.cash += 8
    finish_public_change(_public_write, 'labor_frontier_market:start_machinery_project',
                         inputs={'source_writer': 'labor_frontier_market.py:start_machinery_project:c9a0bf5df4aaf146:1', 'semantic_operation_id': locals().get('operation_id')})
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
            _public_write = begin_public_change(None, firm)
            firm.cash -= delivered
            finish_public_change(_public_write, 'labor_frontier_market:_buy_cotton',
                                 inputs={'source_writer': 'labor_frontier_market.py:_buy_cotton:5e00da7d5c59b139:1', 'semantic_operation_id': locals().get('operation_id')})
            tax = round(price * COTTON_TAX_RATE, 6)
            _public_write = begin_public_change(None, grower)
            grower.cash += price - tax
            finish_public_change(_public_write, 'labor_frontier_market:_buy_cotton',
                                 inputs={'source_writer': 'labor_frontier_market.py:_buy_cotton:369888dd373af367:1', 'semantic_operation_id': locals().get('operation_id')})
            _public_write = begin_public_change(None, field.gov.agent)
            field.gov.agent.cash += tax
            finish_public_change(_public_write, 'labor_frontier_market:_buy_cotton',
                                 inputs={'source_writer': 'labor_frontier_market.py:_buy_cotton:dc8a97fcba1c7e46:1', 'semantic_operation_id': locals().get('operation_id')})
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
                _public_write = begin_public_change(None, carrier)
                carrier.cash += freight
                finish_public_change(_public_write, 'labor_frontier_market:_buy_cotton',
                                     inputs={'source_writer': 'labor_frontier_market.py:_buy_cotton:0b855e1386359680:1', 'semantic_operation_id': locals().get('operation_id')})
            grower.inv_add(Goods.cotton, -1)
            old_stock = firm.inv_get(Goods.cotton, 0)
            old_cost = firm.cost_get(Goods.cotton, 3.0)
            firm.inv_add(Goods.cotton, 1)
            firm.cost_set(Goods.cotton,
                          (old_stock * old_cost + delivered) / (old_stock + 1))
            paid_event_id = emit(field, kind='scenario_cotton_paid_price', record_class='observation',
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
                              'paid_price': delivered, 'quantity': 1,
                              'destination_nation': buyer_nation,
                              'seller_nation': seller_nation,
                              'currency': seller_currency,
                              'seller_currency': seller_currency,
                              'buyer_currency': buyer_currency,
                              'trace_event_id': paid_event_id,
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
            _public_write = begin_public_change(None, buyer)
            buyer.cash -= delivered
            finish_public_change(_public_write, 'labor_frontier_market:_sell_cloth',
                                 inputs={'source_writer': 'labor_frontier_market.py:_sell_cloth:f23a1cef8d1f0b24:1', 'semantic_operation_id': locals().get('operation_id')})
            _public_write = begin_public_change(None, firm)
            firm.cash += ask
            finish_public_change(_public_write, 'labor_frontier_market:_sell_cloth',
                                 inputs={'source_writer': 'labor_frontier_market.py:_sell_cloth:d848f47def9c018b:1', 'semantic_operation_id': locals().get('operation_id')})
            carrier = _freight_recipient(source)
            if freight:
                _public_write = begin_public_change(None, carrier)
                carrier.cash += freight
                finish_public_change(_public_write, 'labor_frontier_market:_sell_cloth',
                                     inputs={'source_writer': 'labor_frontier_market.py:_sell_cloth:4dc9a021841186ce:1', 'semantic_operation_id': locals().get('operation_id')})
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
            _public_write = begin_public_change(None, firm)
            firm.cash -= tax
            finish_public_change(_public_write, 'labor_frontier_market:_sell_cloth',
                                 inputs={'source_writer': 'labor_frontier_market.py:_sell_cloth:e5a09a48194829b0:1', 'semantic_operation_id': locals().get('operation_id')})
            _public_write = begin_public_change(None, source.gov.agent)
            source.gov.agent.cash += tax
            finish_public_change(_public_write, 'labor_frontier_market:_sell_cloth',
                                 inputs={'source_writer': 'labor_frontier_market.py:_sell_cloth:c0391410efa932ef:1', 'semantic_operation_id': locals().get('operation_id')})
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
                          'delivered_price': delivered, 'paid_price': delivered,
                          'quantity': 1,
                          'destination_nation': buyer_nation,
                          'currency': seller_currency,
                          'seller_currency': seller_currency,
                          'buyer_currency': buyer_currency,
                          'trace_event_id': paid_event_id,
                          'freight': freight,
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
            _public_write = begin_public_change(None, region.gov.agent)
            region.gov.agent.cash -= amount
            finish_public_change(_public_write, 'labor_frontier_market:_sweep_sales_tax',
                                 inputs={'source_writer': 'labor_frontier_market.py:_sweep_sales_tax:20c96f7a06fbcd43:1', 'semantic_operation_id': locals().get('operation_id')})
            _public_write = begin_public_change(None, region.owner_nation.government.agent)
            region.owner_nation.government.agent.cash += amount
            finish_public_change(_public_write, 'labor_frontier_market:_sweep_sales_tax',
                                 inputs={'source_writer': 'labor_frontier_market.py:_sweep_sales_tax:16a024f28524d64e:1', 'semantic_operation_id': locals().get('operation_id')})
            transfers.append({'region': region.name,
                              'nation': region.owner_nation.name, 'amount': amount})
    return transfers


def _record_scenario_market_prices(world, turn, purchases, sales):
    """Write destination-market paid-price VWAPs with turn-time composition."""
    state = world['scenario_state']
    currency = world['currencies'][0]
    grouped = defaultdict(list)
    for good, rows in ((Goods.cotton, purchases), (Goods.cloth, sales)):
        for row in rows:
            nation_name = row.get('destination_nation')
            paid_event_id = row.get('trace_event_id')
            quantity = int(row.get('quantity', 1))
            if not nation_name or quantity <= 0:
                continue
            grouped[(nation_name, good)].append({
                'event_id': paid_event_id,
                'price': float(row['paid_price']),
                'quantity': quantity,
                'origin_tile': row['origin'],
                'destination_tile': row.get('mill', row.get('market')),
                'seller_nation': row.get('seller_nation'),
                'buyer_nation': nation_name,
                'currency': row.get('currency', currency),
                'seller_currency': row.get('seller_currency',
                                           row.get('currency', currency)),
                'buyer_currency': row.get('buyer_currency', currency),
            })

    by_name = {region.name: region for region in world['tiles']}
    history = state.setdefault('market_price_history', {})
    from run_trace import emit
    for nation in world['nations']:
        destination_membership = sorted(
            tile.name for tile in getattr(nation, 'tiles', ()))
        nation_history = history.setdefault(nation.name, {})
        for good in (Goods.cotton, Goods.cloth):
            trades = grouped.get((nation.name, good), ())
            quantity = sum(int(row['quantity']) for row in trades)
            total_paid = sum(float(row['price']) * int(row['quantity'])
                             for row in trades)
            contributing_tiles = sorted({row['destination_tile'] for row in trades})
            source_tiles = sorted({row['origin_tile'] for row in trades})
            seller_nations = sorted({row['seller_nation'] for row in trades
                                     if row['seller_nation']})
            seller_currencies = sorted({row['seller_currency'] for row in trades}) or [currency]
            buyer_currencies = sorted({row['buyer_currency'] for row in trades}) or [currency]
            currency_basis = sorted(set(seller_currencies) | set(buyer_currencies))
            currency_pairs = sorted({(row['seller_currency'], row['buyer_currency'])
                                     for row in trades})
            # The scenario currently shares one currency. Keep future variants
            # honest: the market average is unavailable when counterparties
            # use different units because these settlements do not convert FX.
            compatible = (len(seller_currencies) == 1 and len(buyer_currencies) == 1
                          and seller_currencies[0] == buyer_currencies[0])
            market_currency = (seller_currencies[0] if len(seller_currencies) == 1
                               else currency)
            price = (total_paid / quantity
                     if quantity and compatible else None)
            member_totals = defaultdict(lambda: [0.0, 0])
            for trade in trades:
                member = member_totals[trade['destination_tile']]
                member[0] += trade['price'] * trade['quantity']
                member[1] += trade['quantity']
            member_market_prices = {
                tile_name: total_paid / member_quantity
                for tile_name, (total_paid, member_quantity) in member_totals.items()
                if member_quantity and compatible
            }
            previous_points = nation_history.setdefault(good.name.lower(), [])
            previous_point = previous_points[-1] if previous_points else None
            previous_membership = set(
                (previous_point or {}).get('territory_membership', ()))
            current_membership = set(destination_membership)
            common_members = sorted(previous_membership & current_membership)
            previous_member_prices = (previous_point or {}).get(
                'member_market_prices', {})
            comparable_members = [tile_name for tile_name in common_members
                                  if tile_name in previous_member_prices
                                  and tile_name in member_market_prices]
            prior_common_mean = (
                sum(previous_member_prices[tile_name]
                    for tile_name in comparable_members) / len(comparable_members)
                if comparable_members else None)
            current_common_mean = (
                sum(member_market_prices[tile_name]
                    for tile_name in comparable_members) / len(comparable_members)
                if comparable_members else None)
            continuing_market_change = (
                current_common_mean - prior_common_mean
                if prior_common_mean is not None and current_common_mean is not None
                else None)
            currency_stable = bool(
                previous_point is not None and compatible
                and previous_point.get('currency') == market_currency)
            previous_price = ((previous_point or {}).get('price'))
            national_market_change = (
                price - previous_price
                if price is not None and previous_price is not None and currency_stable
                else None)
            composition_residual = (
                national_market_change - continuing_market_change
                if national_market_change is not None
                and continuing_market_change is not None else None)
            decomposition_status = (
                'arithmetic_decomposition_available'
                if composition_residual is not None else
                'mixed_or_changed_currency' if not currency_stable else
                'no_prior_common_market_value')
            clock_tile = (by_name.get(contributing_tiles[0]) if contributing_tiles
                          else next(iter(getattr(nation, 'tiles', ())), None))
            if clock_tile is None:
                continue
            causes = [row['event_id'] for row in trades if row['event_id']]
            coverage_id = emit(
                clock_tile, kind='scenario_market_price_coverage',
                record_class='calculation', phase='scenario_market',
                subject={'type': 'nation', 'id': nation.name,
                         'good': good.name.lower()},
                metric_id='goods.scenario_market_coverage', unit='units',
                after=quantity, formula_id='aggregate.sum.v1',
                inputs={'member_values': [row['quantity'] for row in trades],
                        'transaction_count': len(trades),
                        'currency_basis': currency_basis,
                        'seller_currency_basis': seller_currencies,
                        'buyer_currency_basis': buyer_currencies,
                        'currency_pairs': [list(pair) for pair in currency_pairs],
                        'currency_basis_compatible': compatible,
                        'currency_conversion_applied': False,
                        'no_settled_trade': not trades,
                        'price_unavailable_reason': (
                            'no_settled_trade' if not trades else
                            'counterparty_currency_mismatch'
                            if any(seller != buyer for seller, buyer in currency_pairs)
                            else 'mixed_currency_basis' if not compatible else None)},
                cause_event_ids=causes or None)
            vwap_id = None
            if price is not None:
                vwap_id = emit(
                    clock_tile, kind='scenario_market_transaction_vwap',
                    record_class='calculation', phase='scenario_market',
                    subject={'type': 'nation', 'id': nation.name,
                             'good': good.name.lower()},
                    metric_id='goods.scenario_transaction_vwap',
                    unit='local_currency_per_unit', after=price,
                    formula_id='scenario.market_vwap.v1',
                    inputs={'total_paid': total_paid, 'quantity': quantity,
                            'transaction_count': len(trades),
                            'transactions': trades,
                            'price_basis': ('delivered_to_mill' if good is Goods.cotton
                                            else 'delivered_to_household_market'),
                            'destination_nation': nation.name,
                            'destination_territory_membership': destination_membership,
                            'contributing_destination_tiles': contributing_tiles,
                            'contributing_source_tiles': source_tiles,
                            'member_market_prices': member_market_prices,
                            'previous_territory_membership': sorted(previous_membership),
                            'added_territory_tiles': sorted(
                                current_membership - previous_membership),
                            'removed_territory_tiles': sorted(
                                previous_membership - current_membership),
                            'territory_membership_changed': (
                                previous_membership != current_membership),
                            'previous_contributing_destination_tiles': sorted(
                                (previous_point or {}).get(
                                    'contributing_destination_tiles', ())),
                            'common_market_tiles': comparable_members,
                            'previous_common_market_mean': prior_common_mean,
                            'current_common_market_mean': current_common_mean,
                            'continuing_market_price_change': continuing_market_change,
                            'national_market_price_change': national_market_change,
                            'territorial_composition_residual': composition_residual,
                            'currency_membership_stable': currency_stable,
                            'delta_decomposition_status': decomposition_status,
                            'delta_decomposition_note': (
                                'Continuing-market change plus residual is an '
                                'arithmetic decomposition, not a causal share; '
                                'the residual also contains transaction mix and '
                                'volume-weight changes.'),
                            'seller_nations': seller_nations,
                            'currency': currency_basis[0],
                            'seller_currency_basis': seller_currencies,
                            'buyer_currency_basis': buyer_currencies,
                            'currency_pairs': [list(pair) for pair in currency_pairs],
                            'currency_conversion_applied': False,
                            'currency_basis_compatible': compatible},
                    cause_event_ids=[*causes, coverage_id])
            point = {
                'turn': int(turn), 'price': round(price, 4) if price is not None else None,
                'quantity': quantity, 'transaction_count': len(trades),
                'currency': market_currency if compatible else None,
                'currency_basis': currency_basis,
                'currency_conversion_applied': False,
                'territory_count': len(destination_membership),
                'territory_membership': destination_membership,
                'contributing_destination_tiles': contributing_tiles,
                'contributing_source_tiles': source_tiles,
                'member_market_prices': member_market_prices,
                'seller_nations': seller_nations,
                'territory_membership_changed': (
                    previous_membership != current_membership),
                'added_territory_tiles': sorted(current_membership - previous_membership),
                'removed_territory_tiles': sorted(previous_membership - current_membership),
                'national_market_price_change': national_market_change,
                'continuing_market_price_change': continuing_market_change,
                'territorial_composition_residual': composition_residual,
                'currency_membership_stable': currency_stable,
                'delta_decomposition_status': decomposition_status,
                'price_unavailable_reason': (
                    'no_settled_trade' if not trades else
                    'counterparty_currency_mismatch'
                    if any(seller != buyer for seller, buyer in currency_pairs)
                    else 'mixed_currency_basis' if not compatible else None),
                'trace_event_id': vwap_id or coverage_id,
                'trace_metric_id': ('goods.scenario_transaction_vwap'
                                    if price is not None
                                    else 'goods.scenario_market_coverage'),
            }
            previous_points.append(point)


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
    _record_scenario_market_prices(world, turn, purchases, sales)
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
