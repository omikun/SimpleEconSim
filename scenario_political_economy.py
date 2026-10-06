"""Private grain, cultivator tenure, collective action, and fiscal choices in Egypt."""

from __future__ import annotations

from math import exp
from random import Random

from goods import Goods
from nutrition import deficit_fraction


NATIONAL_ACTIONS = frozenset({'buy_private_grain', 'requisition_private_grain',
                              'open_private_grain_market', 'extend_collection_term'})
DISTRICT_ACTIONS = frozenset({'district_arrears_relief', 'district_bargain_workers',
                              'district_support_mutual_aid', 'district_break_strike'})
WAREHOUSE_CAPACITY_PER_DISTRICT = 60
CADASTRAL_ASSESSMENT_MULTIPLIER = 1.0
NATIONAL_CADASTRAL_SHARE = 0.25


def _households(tile):
    return [a for a in tile.agents if getattr(a, 'alive', True)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_trader', False)
            and not getattr(a, 'is_lord', False)]


def _name(tile):
    return getattr(tile, 'scenario_location', None) or getattr(tile, 'display_name', tile.name)


def _price(tile):
    return max(0.25, float(tile.recipes.get(Goods.food, {}).get('price', 1.0)))


def _economy(world):
    return world['scenario_state']['political_economy']


def initialize(world, nation):
    state = world['scenario_state']
    state['political_economy'] = {
        'warehouse_by_tile': {}, 'private_reserve_by_tile': {},
        'grain_policy': 'hold', 'arrears': {},
        'reservation_price_by_tile': {},
        'tenure_transfers': [], 'migrations': [], 'collective_by_tile': {},
        'scenario_strikers_by_tile': {},
        'grain_transactions': [], 'tax_assessments': [], 'fiscal_reports': [],
        'control_extension_turns': 0,
    }
    for tile in nation.tiles:
        holders = [a for a in tile.agents if getattr(a, 'alive', True)
                   and getattr(a, 'is_lord', False)]
        if not holders:
            holders = [a for a in tile.agents if getattr(a, 'alive', True)
                       and getattr(a, 'is_trader', False)]
        if holders:
            owner = max(holders, key=lambda a: float(a.cash))
            _economy(world)['warehouse_by_tile'][tile.name] = owner.id
            _economy(world)['reservation_price_by_tile'][tile.name] = round(_price(tile) * 1.5, 2)
            _economy(world)['private_reserve_by_tile'][tile.name] = min(4, owner.inv_get(Goods.food, 0))
            tile.scenario_grain_holder_id = owner.id
            tile.scenario_grain_policy = 'hold'
            tile.scenario_grain_reserved_units = _economy(world)['private_reserve_by_tile'][tile.name]
            tile.scenario_grain_offer_units = 0
        _economy(world)['collective_by_tile'][tile.name] = {
            'petitioners': 0, 'strikers': 0, 'mutual_aid_meals': 0,
            'injuries': 0, 'support': 0.0, 'settlement_until_turn': 0,
        }
        _economy(world)['scenario_strikers_by_tile'][tile.name] = []


def _holder(world, tile):
    owner_id = _economy(world)['warehouse_by_tile'].get(tile.name)
    return next((a for a in tile.agents if a.id == owner_id and a.alive), None)


def _reserved(world, tile):
    owner = _holder(world, tile)
    units = min(max(0, int(_economy(world)['private_reserve_by_tile'].get(tile.name, 0))),
                max(0, owner.inv_get(Goods.food, 0)) if owner else 0)
    _economy(world)['private_reserve_by_tile'][tile.name] = units
    tile.scenario_grain_reserved_units = units
    return units


def _set_reserved(world, tile, units):
    _economy(world)['private_reserve_by_tile'][tile.name] = max(0, int(units))
    _reserved(world, tile)


def stock(world, nation):
    return sum(_reserved(world, tile) for tile in nation.tiles)


def district_snapshot(world, tile):
    econ = _economy(world)
    owner = _holder(world, tile)
    ids = {a.id for a in _households(tile)}
    arrears = sum(float(row['balance']) for key, row in econ['arrears'].items()
                  if key in ids)
    collective = econ['collective_by_tile'].get(tile.name, {})
    return {'private_stock': _reserved(world, tile) if owner else 0,
            'owner_id': owner.id if owner else None,
            'arrears': arrears,
            'at_risk': sum(row['balance'] > 0 and row['missed'] >= 2
                           for key, row in econ['arrears'].items() if key in ids),
            'petitioners': int(collective.get('petitioners', 0)),
            'strikers': int(collective.get('strikers', 0)),
            'mutual_aid_meals': int(collective.get('mutual_aid_meals', 0))}


def _record_grain(world, tile, kind, units, cash, owner_id, turn=None):
    _economy(world)['grain_transactions'].append({
        'turn': int(world['turn'] if turn is None else turn), 'tile': tile.name, 'kind': kind,
        'units': int(units), 'cash': round(float(cash), 2), 'owner_id': owner_id})


def _buy_harvest(world, tile, owner, turn):
    """Owners buy real excess maize from producers, then withhold it from asks."""
    if _economy(world)['grain_policy'] == 'open':
        return
    hungry = sum(deficit_fraction(a) for a in _households(tile))
    desire = 0.08 + 0.22 * (1.0 - exp(-hungry / 10.0))
    if _economy(world)['grain_policy'] == 'open':
        desire *= 0.20
    price = _price(tile)
    bought = 0
    room = max(0, WAREHOUSE_CAPACITY_PER_DISTRICT - _reserved(world, tile))
    for producer in sorted((a for a in tile.agents if a is not owner
                            and getattr(a, 'alive', True) and a.output == Goods.food),
                           key=lambda a: a.id):
        surplus = max(0, producer.inv_get(Goods.food, 0) - 4)
        units = min(int(surplus * desire), int(owner.cash / price), 8, room - bought)
        if units <= 0:
            continue
        cost = units * price
        producer.inv_add(Goods.food, -units)
        producer.cash += cost
        owner.inv_add(Goods.food, units)
        owner.cash -= cost
        bought += units
    if bought:
        _set_reserved(world, tile, _reserved(world, tile) + bought)
        _record_grain(world, tile, 'private_purchase', bought, bought * price, owner.id, turn=turn)


def hold_after_harvest(tile, turn):
    """Called by production before market asks are gathered."""
    world = getattr(getattr(tile, 'gov', None), 'scenario_debt_world', None)
    if not world or world.get('scenario_id') != 'egypt_1877':
        return
    owner = _holder(world, tile)
    if owner is not None:
        _buy_harvest(world, tile, owner, turn)
        if _economy(world)['grain_policy'] == 'hold':
            neighbor_offer = max((_price(other) for other in tile.neighbors.values()), default=0.0)
            target = max(_economy(world)['reservation_price_by_tile'][tile.name],
                         neighbor_offer * 1.05)
            relative_price = _price(tile) / max(.25, target)
            release_share = .8 / (1.0 + exp(-5.0 * (relative_price - 1.0)))
            tile.scenario_grain_offer_units = int(_reserved(world, tile) * release_share)
        else:
            tile.scenario_grain_offer_units = _reserved(world, tile)


def _sell_to_households(world, tile, owner, limit=None):
    price = _price(tile)
    reserved_before = _reserved(world, tile)
    sold = 0
    buyers = sorted(_households(tile), key=lambda a: (-deficit_fraction(a), a.cash))
    for buyer in buyers:
        if owner.inv_get(Goods.food, 0) <= 0 or (limit is not None and sold >= limit):
            break
        need = max(0, 4 - buyer.inv_get(Goods.food, 0))
        units = min(need, int(buyer.cash / price), owner.inv_get(Goods.food, 0))
        if limit is not None:
            units = min(units, limit - sold)
        if units <= 0:
            continue
        buyer.cash -= units * price
        owner.cash += units * price
        owner.inv_add(Goods.food, -units)
        buyer.inv_add(Goods.food, units)
        sold += units
    if sold:
        _set_reserved(world, tile, max(0, reserved_before - sold))
        _record_grain(world, tile, 'market_sale', sold, sold * price, owner.id)
    return sold


def _assess_arrears(world, tile, assessed_ids):
    econ = _economy(world)
    rate = max(0.0, float(tile.gov.tax_rate))
    turn = int(world['turn'])
    collected = 0.0
    for agent in _households(tile):
        if agent.id in assessed_ids or not agent.assigned_plot_id:
            continue
        assessed_ids.add(agent.id)
        # Separate scenario cadastre levy; paid receipts enter the local tax log.
        assessment = round(CADASTRAL_ASSESSMENT_MULTIPLIER * rate, 2)
        if assessment <= 0:
            continue
        row = econ['arrears'].setdefault(agent.id, {'balance': 0.0, 'missed': 0,
                                                     'plot_id': agent.assigned_plot_id})
        due = round(row['balance'] + assessment, 2)
        paid = min(max(0.0, float(agent.cash)), due)
        agent.cash -= paid
        collected += paid
        row['balance'] = round(due - paid, 2)
        row['missed'] = row['missed'] + 1 if row['balance'] > 0 else 0
        econ['tax_assessments'].append({'turn': turn, 'tile': tile.name,
                                        'agent_id': agent.id, 'assessed': assessment,
                                        'paid': round(paid, 2), 'arrears': row['balance']})
        # A continuous arrears hazard avoids an automatic cliff at a fixed bill.
        exposure = max(0.0, float(row['balance'])) * max(0, row['missed'] - 1)
        foreclosure_chance = 1.0 - exp(-0.01 * exposure)
        draw = Random(agent.id * 7919 + turn * 104729).random()
        if draw < foreclosure_chance:
            _foreclose(world, tile, agent, row)
    if collected:
        national = round(collected * NATIONAL_CADASTRAL_SHARE, 6)
        local = collected - national
        nation = getattr(tile, 'owner_nation', None)
        if nation is not None:
            nation.government.agent.cash += national
            nation.government.record_income(turn, 'tax', national)
        else:
            local = collected
            national = 0.0
        tile.gov.agent.cash += local
        tile.gov.record_income(turn, 'tax', local)
        if getattr(tile, 'tax_distribution_log', None):
            tile.tax_distribution_log[-1]['total'] += collected
            tile.tax_distribution_log[-1]['national'] += national
            tile.tax_distribution_log[-1]['municipal'] += local


def _foreclose(world, tile, cultivator, row):
    plot = tile.tenure.find_plot(cultivator.assigned_plot_id) if getattr(tile, 'tenure', None) else None
    if plot is None:
        return
    owner = next((a for a in tile.agents if a.id == plot.lord_id), None)
    bidders = [a for a in tile.agents if a is not cultivator and a.alive
               and not a.is_government and not a.is_corporation
               and not getattr(a, 'assigned_plot_id', None)
               and float(a.cash) >= 2.0]
    buyer = max(bidders, key=lambda a: float(a.cash), default=None)
    price = min(10.0, float(buyer.cash) * .1) if buyer else 0.0
    arrears_before = float(row['balance'])
    if buyer:
        buyer.cash -= price
        recovery = min(price, arrears_before)
        tile.gov.agent.cash += recovery
        tile.gov.record_income(int(world['turn']), 'tax', recovery)
        if getattr(tile, 'tax_distribution_log', None):
            tile.tax_distribution_log[-1]['total'] += recovery
            tile.tax_distribution_log[-1]['municipal'] += recovery
        cultivator.cash += price - recovery
        row['balance'] = round(arrears_before - recovery, 2)
    if cultivator.id in plot.tenant_ids:
        plot.tenant_ids.remove(cultivator.id)
    cultivator.assigned_plot_id = None
    cultivator.social_class = 'dispossessed'
    cultivator.mem_push('mem_eviction', 1.0)
    cultivator.mem_push('mem_debt_trap', 1.0)
    if buyer and not getattr(buyer, 'is_lord', False) and buyer.id not in plot.tenant_ids:
        plot.tenant_ids.append(buyer.id)
        buyer.assigned_plot_id = plot.plot_id
    row['missed'] = 0
    record = {'turn': int(world['turn']), 'tile': tile.name,
              'cultivator_id': cultivator.id, 'title_holder_id': owner.id if owner else plot.lord_id,
              'new_use_right_holder_id': buyer.id if buyer else None,
              'plot_id': plot.plot_id, 'arrears_before': arrears_before,
              'arrears_after': row['balance'], 'auction_price': round(price, 2)}
    _economy(world)['tenure_transfers'].append(record)
    tile.unrest_level = min(1.0, float(tile.unrest_level) + .03)
    nation = tile.owner_nation
    if nation is not None:
        nation.legitimacy = max(0.0, float(nation.legitimacy) - .005)
        destinations = [other for other in nation.tiles if other is not tile]
        def open_jobs(other):
            return [a for a in other.agents if getattr(a, 'is_corporation', False)
                    and a.alive and a.output == cultivator.output
                    and len(a.employees) < a.max_employees
                    and a.cash >= 2 * a.wage]
        if destinations:
            target = min(destinations, key=lambda other: (
                -len(open_jobs(other)),
                sum(deficit_fraction(a) for a in _households(other)) / max(1, len(_households(other))),
                len(other.agents)))
            if cultivator.employer is None and not getattr(tile.bank, 'is_frozen', False):
                scenario_strikers = _economy(world)['scenario_strikers_by_tile'][tile.name]
                if cultivator.id in scenario_strikers:
                    scenario_strikers.remove(cultivator.id)
                    cultivator.is_striking = False
                deposit = float(tile.bank.deposits.get(cultivator, 0.0))
                if deposit > 0:
                    tile.bank.Withdraw(cultivator, deposit)
                    target.bank.Deposit(cultivator, deposit)
                tile.agents.remove(cultivator)
                target.agents.append(cultivator)
                cultivator.region = target.name
                cultivator._bank_ref = target.bank
                record['migrated_to'] = target.name
                jobs = open_jobs(target)
                if jobs:
                    employer = max(jobs, key=lambda a: float(a.wage))
                    cultivator.employer = employer
                    cultivator.hired_at = int(world['turn'])
                    employer.employees.append(cultivator)
                    record['wage_employer_id'] = employer.id
                _economy(world)['migrations'].append(record.copy())


def _organize(world, tile):
    econ = _economy(world)
    row = econ['collective_by_tile'][tile.name]
    people = _households(tile)
    arrears = econ['arrears']
    petitioners = [a for a in people if deficit_fraction(a) > .05
                   or arrears.get(a.id, {}).get('balance', 0.0) > 0]
    row['petitioners'] = len(petitioners)
    pressure = (sum(deficit_fraction(a) for a in people) / max(1, len(people))
                + sum(arrears.get(a.id, {}).get('balance', 0.0) for a in people)
                / max(1, 10 * len(people)))
    share = .12 * (1.0 - exp(-3.0 * pressure))
    if int(world['turn']) <= int(row.get('settlement_until_turn', 0)):
        share *= .1
    recruits = int(len(petitioners) * share)
    recruits_by_id = {agent.id for agent in sorted(
        petitioners, key=lambda a: (-deficit_fraction(a), float(a.cash), a.id))[:recruits]}
    previous = set(econ['scenario_strikers_by_tile'].get(tile.name, []))
    for agent in people:
        if agent.id in previous and agent.id not in recruits_by_id:
            agent.is_striking = False
    for agent in petitioners:
        if agent.id not in recruits_by_id:
            continue
        agent.is_striking = True
    econ['scenario_strikers_by_tile'][tile.name] = sorted(recruits_by_id)
    row['strikers'] = sum(bool(getattr(a, 'is_striking', False)) for a in people)
    row['support'] = 1.0 - exp(-row['petitioners'] / max(1, len(people)))
    # Households redistribute only their own food; public stocks are untouched.
    donors = [a for a in people if a.inv_get(Goods.food, 0) >= 8
              and deficit_fraction(a) == 0]
    receivers = [a for a in people if a.inv_get(Goods.food, 0) == 0
                 and deficit_fraction(a) > 0]
    meals = 0
    for donor, receiver in zip(donors, receivers):
        donor.inv_add(Goods.food, -1)
        receiver.inv_add(Goods.food, 1)
        meals += 1
    row['mutual_aid_meals'] += meals


def advance(world, nation, turn):
    econ = _economy(world)
    assessed_ids = set()
    for tile in nation.tiles:
        owner = _holder(world, tile)
        if owner is not None:
            _reserved(world, tile)
            if econ['grain_policy'] == 'open':
                _sell_to_households(world, tile, owner, limit=_reserved(world, tile))
        _assess_arrears(world, tile, assessed_ids)
        _organize(world, tile)
    _resolve_collection_proposal(world, turn)
    _fiscal_report(world, nation, turn)


def _resolve_collection_proposal(world, turn):
    state = world['scenario_state']
    assignment = state.get('collection_assignment') or {}
    proposal = assignment.get('extension_proposal')
    if not proposal or turn < proposal['reply_turn']:
        return
    confidence = float(state.get('creditor_confidence', 0.0))
    accepted = assignment.get('status') == 'active' and confidence >= .4
    if accepted:
        old = float(assignment['per_turn_cap'])
        new = round(old * .5, 2)
        assignment['per_turn_cap'] = new
        assignment['extended'] = True
        assignment['control_until_turn'] = int(world['scenario']['horizon_turns']) + 8
        state['creditor_levy_per_turn'] = new
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - .10)
        _economy(world)['control_extension_turns'] += 8
        from scenario_oversight import sign as sign_oversight
        sign_oversight(world, 0.0)
        state['oversight_agreement']['expires_turn'] = assignment['control_until_turn']
        message = (f'The Caisse accepted a {old:.1f}→{new:.1f} collection cap in exchange '
                   'for eight additional turns of inspection after the campaign horizon.')
    else:
        state['creditor_confidence'] = max(0.0, confidence - .03)
        message = 'Britain and France rejected the lower levy because creditor confidence is too weak.'
    assignment['extension_proposal'] = None
    state.setdefault('creditor_news', []).append({'turn': turn, 'headline': 'Caisse collection terms', 'body': message})
    world['scenario_feedback'] = message


def _fiscal_report(world, nation, turn):
    state = world['scenario_state']
    ledger = [entry for entry in state.get('debt_ledger', [])
              if entry.get('turn') == turn and entry.get('kind') == 'assigned_revenue']
    by_creditor = {}
    by_source = {}
    for entry in ledger:
        creditor = entry.get('creditor', 'Unknown')
        source = entry.get('source', 'unknown')
        by_creditor[creditor] = by_creditor.get(creditor, 0.0) + float(entry['amount'])
        by_source[source] = by_source.get(source, 0.0) + float(entry['amount'])
    hungry = sum(deficit_fraction(a) > 0 for tile in nation.tiles for a in _households(tile))
    public_meals = min(int(nation.government.food_inventory) // 4,
                       int(state.get('relief_units_per_turn', 30)))
    unfunded = max(0, hungry - public_meals)
    avg_price = sum(_price(tile) for tile in nation.tiles) / max(1, len(nation.tiles))
    buy_budget = unfunded * 4 * avg_price
    available = max(0.0, float(nation.government.agent.cash))
    missing_cash = max(0.0, buy_budget - available)
    diverted = sum(by_creditor.values())
    report = {'turn': turn, 'creditors': by_creditor, 'sources': by_source,
              'diverted': round(diverted, 2), 'unfunded_meals': unfunded,
              'relief_purchase_cost': round(buy_budget, 2),
              'cash_shortfall': round(missing_cash, 2),
              'attributable_to_assignment': round(min(diverted, missing_cash), 2)}
    _economy(world)['fiscal_reports'].append(report)


def apply_action(world, nation, action_id, tile=None):
    econ = _economy(world)
    treasury = nation.government.agent
    if action_id in NATIONAL_ACTIONS:
        if action_id == 'extend_collection_term':
            assignment = world['scenario_state'].get('collection_assignment') or {}
            if assignment.get('status') != 'active':
                return False, 'There is no active collection assignment to renegotiate.'
            if assignment.get('extended') or assignment.get('extension_proposal'):
                return False, 'The collection term has already been extended.'
            old = float(assignment['per_turn_cap'])
            assignment['extension_proposal'] = {'reply_turn': int(world['turn']) + 1}
            return True, f'Proposed a {old:.1f}→{old * .5:.1f} collection cap for eight more inspection turns; the Caisse replies next turn.'
        total = stock(world, nation)
        if action_id == 'open_private_grain_market':
            if econ['grain_policy'] == 'open':
                return False, 'Private grain sales are already open.'
            econ['grain_policy'] = 'open'
            for tile in nation.tiles:
                tile.scenario_grain_policy = 'open'
                tile.scenario_grain_offer_units = _reserved(world, tile)
            sold = sum(_sell_to_households(world, tile, owner, limit=_reserved(world, tile))
                       for tile in nation.tiles if (owner := _holder(world, tile)) is not None)
            return True, f'Allowed private grain sales: {sold} units reached households that could pay; holders continue to set the price.'
        if total <= 0:
            return False, 'No private warehouse maize is available.'
        available = min(total, 80)
        bought = 0
        paid = 0.0
        for region in nation.tiles:
            owner = _holder(world, region)
            if owner is None:
                continue
            price = _price(region) * (1.20 if action_id == 'buy_private_grain' else 0.0)
            reserved_before = _reserved(world, region)
            units = min(reserved_before, available - bought,
                        int(treasury.cash / price) if price else available)
            if units <= 0:
                continue
            owner.inv_add(Goods.food, -units)
            _set_reserved(world, region, reserved_before - units)
            nation.government.food_inventory += units
            if price:
                treasury.cash -= units * price
                owner.cash += units * price
                paid += units * price
            _record_grain(world, region, 'public_buy' if price else 'requisition', units,
                          units * price, owner.id)
            if not price:
                region.unrest_level = min(1.0, float(region.unrest_level) + .04)
            bought += units
        if not bought:
            return False, 'The treasury cannot afford the available grain.'
        world['scenario_state']['public_maize_stock_units'] = nation.government.food_inventory
        if action_id == 'requisition_private_grain':
            nation.legitimacy = max(0.0, float(nation.legitimacy) - .04)
            return True, f'Requisitioned {bought} private maize units for public relief; owners protest and legitimacy fell.'
        nation.legitimacy = min(1.0, float(nation.legitimacy) + .01)
        return True, f'Bought {bought} private maize units for {paid:.1f} treasury units; owners received the cash.'
    if tile is None:
        return False, 'Select an Egyptian district first.'
    people = _households(tile)
    collective = econ['collective_by_tile'][tile.name]
    if action_id == 'district_arrears_relief':
        debtors = [a for a in people if econ['arrears'].get(a.id, {}).get('balance', 0) > 0]
        if not debtors:
            return False, 'No cultivator arrears are recorded here.'
        forgiven = 0.0
        for agent in debtors:
            row = econ['arrears'][agent.id]
            forgiven += row['balance']
            row['balance'] = 0.0
            row['missed'] = 0
        tile.gov.tax_rate = max(0.0, float(tile.gov.tax_rate) - .03)
        nation.legitimacy = min(1.0, float(nation.legitimacy) + .015)
        return True, f'Forgave {forgiven:.1f} unpaid cadastral taxes for {len(debtors)} cultivators in {_name(tile)}; the next assessments fall.'
    if action_id == 'district_support_mutual_aid':
        donors = [a for a in people if a.inv_get(Goods.food, 0) >= 5
                  and deficit_fraction(a) == 0]
        receivers = [a for a in people if deficit_fraction(a) > 0]
        if not donors or not receivers:
            return False, 'Mutual aid needs both a willing food donor and an underfed household.'
        moved = 0
        for receiver in receivers:
            if not donors:
                break
            donor = donors[0]
            donor.inv_add(Goods.food, -1)
            receiver.inv_add(Goods.food, 1)
            moved += 1
            if donor.inv_get(Goods.food, 0) < 5:
                donors.pop(0)
        collective['mutual_aid_meals'] += moved
        nation.legitimacy = min(1.0, float(nation.legitimacy) + .005 * (1 - exp(-moved / 5)))
        return True, f'Local mutual-aid networks moved {moved} food units from surplus households in {_name(tile)}.'
    if action_id == 'district_bargain_workers':
        strikers = [a for a in people if getattr(a, 'is_striking', False)]
        if not strikers and not collective['petitioners']:
            return False, 'No local petition or strike is active.'
        employers = [a for a in tile.agents if getattr(a, 'is_corporation', False) and a.alive]
        employers += [a for a in tile.agents if getattr(a, 'is_lord', False) and a.alive]
        if not employers:
            return False, 'No local owner or employer is available to bargain.'
        payments = 0.0
        for employer in employers:
            employer.wage = min(20.0, float(employer.wage) + .5)
            grant = min(5.0, max(0.0, float(employer.cash)) * .02)
            employer.cash -= grant
            payments += grant
        recipients = strikers or people[:max(1, min(len(people), collective['petitioners']))]
        for agent in recipients:
            agent.cash += payments / len(recipients)
            agent.is_striking = False
        collective['strikers'] = 0
        collective['petitioners'] = max(0, collective['petitioners'] // 2)
        collective['settlement_until_turn'] = int(world['turn']) + 3
        econ['scenario_strikers_by_tile'][tile.name] = []
        tile.unrest_level *= exp(-.12)
        nation.legitimacy = min(1.0, float(nation.legitimacy) + .02)
        return True, f'Owners in {_name(tile)} raised offered wages by 0.5 and paid {payments:.1f} to petitioners; the local strike ended.'
    if action_id == 'district_break_strike':
        from unrest import apply_repression
        if not (getattr(tile, 'police_employed', 0) or any(
                getattr(unit, 'soldiers', 0) > 0 for unit in getattr(tile, 'military_units', []))):
            return False, 'No police or garrison is present to break the strike.'
        injured = apply_repression(tile, int(world['turn']))
        for agent in people:
            if agent.is_striking:
                agent.is_striking = False
        collective['injuries'] += injured
        collective['strikers'] = 0
        econ['scenario_strikers_by_tile'][tile.name] = []
        return True, f'Police broke the {_name(tile)} strike; {injured} people received casualty memories and government support fell.'
    return False, 'Unknown political-economy decision.'
