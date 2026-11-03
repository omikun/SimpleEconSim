"""Engineering rules shared by the economy, science panels and tech simulator.

No clock-based refinement: operation supplies routine learning; funded workshop
shifts supply dedicated engineering. All forecasts call the same pure rules.
"""
from __future__ import annotations

import math
from copy import copy

from goods import Goods

OBJECTIVES = ('performance', 'economy', 'balanced')
OBJECTIVE_LABELS = {
    'performance': 'Develop a new capability',
    'economy': 'Make existing designs economical',
    'balanced': 'Improve both',
}
CAPABILITY_NAMES = ('Undiscovered', 'Working prototype', 'Industrial standard',
                    'Advanced applications', 'Frontier capability')


def tier_for_xp(xp):
    return sum(float(xp) >= threshold for threshold in (1, 25, 60, 90))


def refinement_rates(*, installations=0, utilization=0.0, readiness=1.0,
                     capability=1.0, public_effort=0.0, private_effort=0.0,
                     objective='balanced', blockaded=False):
    """Usage has diminishing returns, never an exhausted lifetime allowance.

    Effort is delivered skilled half-day workshop shifts, not announced money.
    Private engineering targets economy; public objectives allocate real effort.
    """
    scale = max(0.0, float(installations)) ** 0.6
    intensity = min(1.5, max(0.0, float(utilization)))
    routine = scale * intensity * max(0.0, float(readiness))
    # Approaching the frontier slows progress but does not make it asymptotic.
    difficulty = 1.0 + max(0.0, float(capability)) / 100.0
    split = {'performance': 1.0, 'economy': 0.0, 'balanced': 0.5}[objective]
    political = 0.25 if blockaded else 1.0
    return {
        'capability': political * (routine + 1.8 * public_effort * split
                                   + 0.2 * private_effort) / difficulty,
        'maturity': political * (0.5 * routine + 2.0 * public_effort * (1.0 - split)
                                 + 2.0 * private_effort),
        'operational_learning': routine * political / difficulty,
        'public_effort': public_effort,
        'private_effort': private_effort,
    }


def build_cost_factor(maturity):
    return 1.6 - 0.8 * min(100.0, max(0.0, float(maturity))) / 100.0


def experiment_goods(tech):
    """Small real input bundle for one workshop shift; no invented resources."""
    from tile_resources import TileResource
    goods = {Goods.wood: 1}
    resources = set(tech.required_resources)
    if TileResource.IRON_ORE in resources:
        goods[Goods.iron] = 1
    elif tech.era >= 2:
        goods[Goods.furniture] = 1
    if TileResource.COAL_SEAM in resources:
        goods[Goods.coal] = 1
    return goods


def workshop_capacity(tile):
    return sum(3 for b in getattr(tile, 'buildings', ())
               if b.name in ('workshop', 'engineering_workshop')
               and not getattr(b, 'retrofit_project_id', None))


def engineering_skill(worker):
    return min(2.0, max(0.5, float(getattr(worker, 'engineering_skill', 1.0))))


def _people(tile, turn, payer=None):
    return [a for a in getattr(tile, 'agents', ())
            if a is not payer and getattr(a, 'alive', True)
            and not any(getattr(a, flag, False) for flag in
                        ('is_corporation', 'is_government', 'is_lord', 'is_trader',
                         'is_native_child', 'is_striking', 'in_revolt'))
            and getattr(a, 'employer', None) is None
            and not getattr(a, 'military_unit_id', None)
            and getattr(a, 'output', None) in (Goods.furniture, Goods.iron, Goods.cloth,
                                              Goods.porcelain)
            and (getattr(a, 'engineering_work_turn', None) != turn
                 or getattr(a, 'engineering_work_share', 0.0) < 0.5)]


def _stockists(tile, good, payer=None):
    return [a for a in getattr(tile, 'agents', ())
            if a is not payer and getattr(a, 'alive', True)
            and callable(getattr(a, 'inv_get', None)) and a.inv_get(good, 0) >= 1
            and not getattr(a, 'is_government', False)]


def engineering_supply(tile, tech, turn, payer=None):
    people = _people(tile, turn, payer)
    goods = experiment_goods(tech)
    stocks = {g: sum(int(a.inv_get(g, 0)) for a in _stockists(tile, g, payer))
              for g in goods}
    material_limit = min((stocks[g] // q for g, q in goods.items()), default=0)
    capacity = min(workshop_capacity(tile), len(people), material_limit)
    price = sum(q * max(0.01, float(getattr(tile, 'recipes', {}).get(g, {}).get('price', 1)))
                for g, q in goods.items())
    wage = max(2.0, sum(max(0.0, float(getattr(a, 'wage', 0))) for a in people)
               / max(1, len(people)))
    reason = ('Build an engineering workshop.' if not workshop_capacity(tile) else
              'Short of skilled artisans and engineers.' if not people else
              'Missing experiment supplies: ' + ', '.join(g.name for g in goods if stocks[g] < goods[g])
              if material_limit == 0 else '')
    return {'capacity': capacity, 'unit_cost': price + wage, 'wage': wage,
            'reason': reason, 'goods': goods, 'people': people}


def _pay(tile, nation, payer, payee, amount, turn, tech_id, kind, index,
         good=None, quantity=0):
    """Conserved cash transfer, with economic journal and paired trace contract."""
    from treasury_trace import begin_public_change, finish_public_change
    from finance_trace import account_ref, cash_transfer_contract, emit_cash_transfer
    from economy.actor_accounts import record
    amount = round(float(amount), 2)
    before_p, before_r = float(payer.cash), float(payee.cash)
    if amount <= 0 or amount > before_p + 1e-9:
        raise ValueError('Engineering payment must be positive and affordable')
    wp, wr = begin_public_change(None, payer), begin_public_change(None, payee)
    payer.cash = before_p - amount
    payee.cash = before_r + amount
    finish_public_change(wp, 'engineering:_pay')
    finish_public_change(wr, 'engineering:_pay')
    currency = getattr(nation, 'currency', getattr(tile, 'home_currency', 'local_currency'))
    ident = f'engineering:{nation.name}:{tech_id}:{turn}:{getattr(payer, "id", "treasury")}:{index}'
    public = payer is getattr(getattr(nation, 'government', None), 'agent', None)
    contract = cash_transfer_contract(
        ident, kind, amount=amount, currency=currency,
        payer_account=account_ref('government_treasury' if public else 'agent',
                                  getattr(nation.government, 'name', nation.name) if public else payer.id,
                                  currency, balance_before=before_p, balance_after=payer.cash,
                                  balance_scope='government_agent.cash' if public else 'cash'),
        payee_account=account_ref('agent', payee.id, currency,
                                  balance_before=before_r, balance_after=payee.cash,
                                  balance_scope='cash'),
        counterparty_leg_status='payer_debited_recipient_credited')
    event_id = emit_cash_transfer(tile, kind=kind, contract=contract, phase='innovation',
                                 inputs={'tech_id': tech_id, 'turn': turn})
    record(tile, 'spot_sale' if good is not None else 'wage' if 'wage' in kind else 'cash_transfer',
           turn=turn, payer_id=getattr(payer, 'id', None), good=good, quantity=quantity,
           recipient_id=payee.id, amount=amount, currency=currency,
           detail={'payment_kind': kind, 'tech_id': tech_id})
    return event_id


def consume_engineering_input(tile, payer, seller, good, units, cost, turn, tech_id, cause):
    from economy.actor_accounts import record
    from run_trace import emit
    before = float(seller.inv_get(good, 0))
    seller.inv_add(good, -units)
    if good in (Goods.food, Goods.prepared_food):
        from food_accounts import record as food_record
        food_record(tile, 'engineering_food_input', units, source=seller, good=good,
                    tech_id=tech_id)
    record(tile, 'input_consumed', turn=turn, payer_id=getattr(payer, 'id', None),
           good=good, quantity=units, amount=cost,
           detail={'tech_id': tech_id, 'purpose': 'engineering', 'immediate_use': True})
    return emit(tile, kind='engineering_input_delivered_and_consumed', record_class='outcome',
        phase='innovation', subject={'type': 'agent', 'id': seller.id, 'good': good.name},
        metric_id='goods.inventory', unit='units', before=before,
        after=float(seller.inv_get(good, 0)), cause_event_ids=[cause] if cause else None,
        inputs={'turn': turn, 'tech_id': tech_id, 'consumed': units,
                'consumer_id': getattr(payer, 'id', None), 'purchase_cost': cost})


def deliver_engineering(tile, nation, tech, payer, budget, turn, slots=None):
    """Purchase complete experiment bundles and reserve real half-day labor.

    Workers retain half their day for their usual occupation. A person cannot
    work on two programs in one turn, even in different technologies.
    """
    supply = engineering_supply(tile, tech, turn, payer)
    capacity = min(supply['capacity'], slots if slots is not None else supply['capacity'])
    remaining = min(max(0.0, float(budget)), max(0.0, float(payer.cash)))
    effort, spent, causes, consumed, workers = 0.0, 0.0, [], {}, []
    for worker in supply['people'][:capacity]:
        # Recheck stock after every purchase; a shared seller may exhaust stock.
        sellers = {g: next(iter(_stockists(tile, g, payer)), None) for g in supply['goods']}
        if not all(sellers.values()):
            break
        prices = {g: round(max(0.01, float(tile.recipes.get(g, {}).get('price', 1))), 2)
                  for g in sellers}
        wage = round(max(2.0, float(getattr(worker, 'wage', 0))), 2)
        cost = sum(prices.values()) + wage
        if remaining + 1e-9 < cost:
            continue
        for g, seller in sellers.items():
            event = _pay(tile, nation, payer, seller, prices[g], turn, tech.tech_id,
                         'engineering_material_payment', len(causes), good=g, quantity=1)
            if event is not None:
                causes.append(event)
            consumed_id = consume_engineering_input(tile, payer, seller, g, 1, prices[g], turn,
                                                     tech.tech_id, event)
            if consumed_id is not None:
                causes.append(consumed_id)
            consumed[g.name] = consumed.get(g.name, 0) + 1
        event = _pay(tile, nation, payer, worker, wage, turn, tech.tech_id,
                     'engineering_wage_payment', len(causes))
        if event is not None:
            causes.append(event)
        worker.engineering_work_turn = turn
        worker.engineering_work_share = 0.5
        workers.append(worker.id)
        effort += engineering_skill(worker)
        worker.engineering_skill = min(2.0, engineering_skill(worker) + 0.005)
        spent += cost
        remaining -= cost
    reason = supply['reason']
    if not reason and effort < capacity:
        reason = 'Budget or available treasury cash limits engineering.'
    elif not reason and spent + supply['unit_cost'] < budget:
        reason = 'Available workshop staff and supplies limit spending.'
    return {'effort': effort, 'spent': round(spent, 2), 'reason': reason,
            'cause_event_ids': causes, 'consumed': consumed, 'worker_ids': workers}


def production_work_share(agent, turn):
    return (float(getattr(agent, 'engineering_work_share', 0.0))
            if getattr(agent, 'engineering_work_turn', None) == turn else 0.0)


def record_operation(region, producer, output, work, capacity, turn, event_id=None):
    """Attribute productive work to installed designs, never to national ownership."""
    if getattr(region, '_technology_usage_turn', None) != turn:
        region._technology_usage_turn = turn
        region.technology_usage = {}
    for i, building in enumerate(getattr(region, 'buildings', ())):
        from technology_adoption import applies_to_producer
        if not applies_to_producer(building, producer):
            continue
        if output not in building.production_bonuses or getattr(building, 'retrofit_project_id', None):
            continue
        for tech_id, tier in getattr(building, 'technology_designs', {}).items():
            key = f'{i}:{tech_id}'
            row = region.technology_usage.setdefault(key, {
                'tech_id': tech_id, 'generation': tier, 'work': 0.0, 'capacity': 0.0,
                'owner_ids': [], 'cause_event_ids': []})
            row['work'] += max(0.0, work)
            row['capacity'] += max(0.0, capacity)
            if work > 0 and producer.id not in row['owner_ids']:
                row['owner_ids'].append(producer.id)
            if event_id is not None and len(row['cause_event_ids']) < 32:
                row['cause_event_ids'].append(event_id)


def register_recipes():
    """Every discovered technology has a buildable physical pilot application."""
    from buildings import BUILDING_RECIPES, BuildingRecipe
    from innovation import TECH_CATALOG
    BUILDING_RECIPES.setdefault('engineering_workshop', BuildingRecipe(
        'engineering_workshop', 'Engineering & Testing Workshop', 300, 3,
        required_goods={Goods.wood: 4, Goods.furniture: 2}, construction_workers=2,
        description='Hosts paid engineering experiments. Requires skilled artisans and real supplies.'))
    for tid, tech in TECH_CATALOG.items():
        name = f'{tid}_prototype'
        bonuses = {Goods(g): value for g, value in tech.production_modifiers.items()}
        if not bonuses:
            good = {'agronomy': Goods.food, 'manufacturing': Goods.furniture,
                    'civil_engineering': Goods.transport, 'finance': Goods.transport,
                    'military': Goods.iron}.get(tech.domain.value, Goods.furniture)
            bonuses = {good: 1.15}
        recipe = BuildingRecipe(name, f'{tech.name} · Pilot Installation',
                                200 + tech.era * 100, 3,
                                required_goods={g: q * 3 for g, q in experiment_goods(tech).items()},
                                production_bonuses=bonuses, construction_workers=2,
                                description='Operating pilot: generates learning from actual production.')
        recipe.technology_id = tid
        BUILDING_RECIPES.setdefault(name, recipe)


def quote_recipe(nation, recipe, system):
    """Snapshot a design at commissioning; future discoveries do not replace it."""
    from innovation import TECH_CATALOG
    tid = getattr(recipe, 'technology_id', None)
    if tid is None:
        tid = next((tid for tid, tech in TECH_CATALOG.items()
                    if recipe.name in tech.unlocked_buildings and system.has_tech(nation.name, tid)), None)
    if not tid:
        return recipe
    if not system.has_tech(nation.name, tid):
        raise ValueError('Discover this technology before commissioning a pilot installation.')
    tier = system.get_tech_tier(nation.name, tid)
    factor = build_cost_factor(system.get_commercial_maturity(nation.name, tid, tier))
    result = copy(recipe)
    result.cost = round(recipe.cost * factor, 2)
    result.required_goods = {g: max(1, math.ceil(q * factor)) for g, q in recipe.required_goods.items()}
    result.technology_designs = {tid: tier}
    result.technology_id = tid
    return result


def engineering_forecast(capability, maturity, rates, baseline, cap=100.0,
                         capability_target=None, maturity_target=None):
    """Conditional milestone estimates; unavailable progress is represented by None."""
    def estimate(start, target, rate, technical=False):
        if start >= target:
            return 0
        if rate <= 0 or (technical and target > cap):
            return None
        # Capability rates depend on current difficulty; project the same rule.
        turns, value = 0, float(start)
        while value < target and turns < 10000:
            value += rate * ((1 + capability / 100) / (1 + value / 100) if technical else 1)
            turns += 1
        return turns if turns < 10000 else None
    target = capability_target or next((x for x in (25, 60, 90, 100) if x > capability), 100)
    economy_target = maturity_target if maturity_target is not None else min(100.0, maturity + 20.0)
    return {'capability_target': target,
            'capability_turns': estimate(capability, target, rates['capability'], True),
            'capability_turns_without_program': estimate(capability, target, baseline['capability'], True),
            'economy_turns': estimate(maturity, economy_target, rates['maturity']),
            'economy_turns_without_program': estimate(maturity, economy_target, baseline['maturity']),
            'conditional': 'At current operation, staffing and supply; not a completion guarantee.'}


class EngineeringMixin:
    """Nation-owned programs and generation-specific industrial experience."""

    def get_commercial_maturity(self, nation_name, tech_id, generation=None):
        generation = generation or max(1, self.get_tech_tier(nation_name, tech_id))
        generations = getattr(self, 'tech_commercial_maturity', {}).get(nation_name, {}).get(tech_id, {})
        if generation in generations:
            return float(generations[generation])
        # Earlier manufacturing knowledge transfers partially, never completely.
        previous = max((g for g in generations if g < generation), default=None)
        return float(generations[previous]) * 0.35 ** (generation - previous) if previous else 0.0

    def commission_retrofit(self, nation, tech_id, tile_name, building_index, t=0):
        from buildings import BUILDING_RECIPES
        from intents import BuildIntent
        from innovation import TECH_CATALOG
        tile = next((r for r in nation.tiles if r.name == tile_name), None)
        try:
            index = int(building_index)
        except (TypeError, ValueError):
            return False, 'Select an installation to upgrade.'
        if tile is None or index < 0 or index >= len(getattr(tile, 'buildings', ())):
            return False, 'Installation not found in your territory.'
        if tech_id not in TECH_CATALOG or not self.has_tech(nation.name, tech_id):
            return False, 'Discover this technology before commissioning a retrofit.'
        target = tile.buildings[index]
        if getattr(target, 'retrofit_project_id', None):
            return False, 'A retrofit is already in progress.'
        tier = self.get_tech_tier(nation.name, tech_id)
        if getattr(target, 'technology_designs', {}).get(tech_id, 0) >= tier:
            return False, 'This installation already uses the current design.'
        prototype = BUILDING_RECIPES[f'{tech_id}_prototype']
        if not set(prototype.production_bonuses).intersection(target.recipe.production_bonuses):
            return False, 'This technology does not apply to the selected installation.'
        recipe = copy(quote_recipe(nation, prototype, self))
        recipe.cost = round(recipe.cost * 0.4, 2)
        recipe.required_goods = {g: max(1, math.ceil(q * 0.4)) for g, q in recipe.required_goods.items()}
        recipe.display_name = f'Retrofit {target.display_name}: {TECH_CATALOG[tech_id].name}'
        recipe.base_turns = 2
        intent = BuildIntent(nation.name, tile.name, prototype.name, submitted_turn=t)
        intent.recipe_override = recipe
        intent.retrofit_target = target
        return intent.execute({r.name: r for r in nation.tiles}, {nation.name: nation}, t)

    def adoption_options(self, nation, tech_id):
        from buildings import BUILDING_RECIPES
        if not self.has_tech(nation.name, tech_id):
            return []
        prototype = BUILDING_RECIPES[f'{tech_id}_prototype']
        quote = quote_recipe(nation, prototype, self)
        tier = self.get_tech_tier(nation.name, tech_id)
        options = []
        for tile in nation.tiles:
            for index, building in enumerate(getattr(tile, 'buildings', ())):
                if (getattr(building, 'technology_designs', {}).get(tech_id, 0) >= tier
                        or getattr(building, 'retrofit_project_id', None)
                        or getattr(building, 'private_owner_id', None) is not None
                        or not set(prototype.production_bonuses).intersection(building.recipe.production_bonuses)):
                    continue
                upgraded = copy(building)
                upgraded.technology_designs = {**getattr(building, 'technology_designs', {}), tech_id: tier}
                before, after = building.production_bonuses, upgraded.production_bonuses
                value = 0.0
                for good in before:
                    history = getattr(tile, 'production_log', {}).get(good, [])
                    quantity = history[-1] if history else 0
                    price = getattr(tile, 'recipes', {}).get(good, {}).get('price', 1)
                    value += max(0.0, quantity * price * (after.get(good, 1) / before[good] - 1))
                cost = round(quote.cost * 0.4, 2)
                options.append({'tile': tile.name, 'tile_label': getattr(tile, 'display_name', tile.name),
                                'building_index': index, 'building': building.display_name,
                                'cost': cost, 'downtime_turns': 2, 'generation': tier,
                                'gross_value_per_turn': round(value, 2),
                                'gross_payback_turns': math.ceil(cost / value) if value > 0 else None})
        return options

    def get_engineering_program(self, nation_name, tech_id):
        return dict(getattr(self, 'engineering_programs', {}).get(nation_name, {}).get(tech_id, {
            'budget': 0.0, 'objective': 'balanced', 'host': None, 'status': 'inactive'}))

    def set_engineering_program(self, nation, tech_id, budget, objective='balanced', host=None, t=0):
        from innovation import TECH_CATALOG
        from innovation_trace import emit_innovation
        try:
            budget = float(budget)
        except (TypeError, ValueError):
            return False, 'Enter a finite, non-negative engineering budget.'
        if (tech_id not in TECH_CATALOG or objective not in OBJECTIVES
                or not math.isfinite(budget) or budget < 0 or budget > 1_000_000):
            return False, 'Invalid technology, objective or engineering budget.'
        tiles = list(getattr(nation, 'tiles', ()))
        if budget > 0 and not tiles:
            return False, 'An engineering program needs a host region.'
        prior = self.get_engineering_program(nation.name, tech_id)
        host = host or prior['host']
        if budget > 0 and not host:
            host = max(tiles, key=workshop_capacity).name
        if host and not any(tile.name == host for tile in tiles):
            return False, 'The workshop must be in your territory.'
        if budget > 0 and not self.has_tech(nation.name, tech_id) and objective == 'economy':
            return False, 'Develop a working prototype before funding cost reduction.'
        xp = self.get_refinement_xp(nation.name, tech_id)
        maturity_now = self.get_commercial_maturity(nation.name, tech_id)
        if budget > 0 and ((objective == 'performance' and xp >= 100)
                           or (objective == 'economy' and maturity_now >= 100)
                           or (objective == 'balanced' and xp >= 100 and maturity_now >= 100)):
            return False, 'This design has already reached the selected engineering frontier.'
        target = next((x for x in (1, 25, 60, 90, 100) if x > xp), 100)
        program = {'budget': round(budget, 2), 'objective': objective, 'host': host,
                   'status': 'active' if budget else 'inactive', 'started_turn': int(t),
                   'capability_target': target,
                   'maturity_target': min(100.0, self.get_commercial_maturity(nation.name, tech_id) + 20),
                   'generation': max(1, self.get_tech_tier(nation.name, tech_id))}
        if not hasattr(self, 'engineering_programs'):
            self.engineering_programs = {}
        self.engineering_programs.setdefault(nation.name, {})[tech_id] = program
        emit_innovation(nation, kind='engineering_program_changed', record_class='decision',
                        subject_fields={'tech_id': tech_id}, metric_id='innovation.engineering_program',
                        unit='status', after=program['status'], inputs={'turn': t, **program})
        host_label = next((getattr(tile, 'display_name', tile.name) for tile in tiles if tile.name == host), host)
        return True, (f"Engineering program: {OBJECTIVE_LABELS[objective]}, up to {budget:.0f}/turn in {host_label}."
                      if budget else 'Public program stopped. Industry continues learning from operation.')

    def _engineering_readiness(self, nation, tech):
        from tile_resources import get_nation_resources, TileResource
        from innovation import TECH_CATALOG
        def names(ids):
            return ', '.join(TECH_CATALOG[tid].name if tid in TECH_CATALOG else tid for tid in ids)
        known = self.get_discovered_techs(nation.name)
        missing = [tid for tid in tech.required_techs if tid not in known]
        if missing:
            return 0.0, 0.0, 'Supporting technology needed: ' + names(missing)
        # Existing operating equipment is evidence of physical feasibility.
        # For first prototypes, imported stocks can substitute for local geology.
        if not self.has_tech(nation.name, tech.tech_id):
            resources = get_nation_resources(nation, nation.tiles)
            alternatives = {TileResource.TIMBER: (Goods.wood,),
                            TileResource.IRON_ORE: (Goods.iron, Goods.iron_ore),
                            TileResource.COAL_SEAM: (Goods.coal,),
                            TileResource.PASTURE_FLAX: (Goods.wool, Goods.cotton),
                            TileResource.NATURAL_NITRATES: (Goods.nitrates,)}
            for resource in tech.required_resources:
                imported = any(callable(getattr(a, 'inv_get', None)) and a.inv_get(g, 0) > 0
                               for tile in nation.tiles for a in getattr(tile, 'agents', ())
                               for g in alternatives.get(resource, ()))
                if resource not in resources and not imported:
                    return 0.0, 100.0, 'Missing prototype resource: ' + resource.value
        tier_deps = tech.tier_dependencies.get(3, [])
        weak = [tid for tid in tier_deps if self.get_tech_tier(nation.name, tid) < 2]
        supporting = [self.get_tech_tier(nation.name, tid) for tid in tech.required_techs]
        readiness = min(1.25, 0.75 + 0.125 * (sum(supporting) / len(supporting) - 1)) if supporting else 1.0
        return readiness, 59.0 if weak else 100.0, (
            'Higher performance needs industrial-standard ' + names(weak) + '.' if weak else '')

    def prepare_region_engineering(self, nation, tile, turn):
        """Called before production, so paid workshop time displaces normal work."""
        from innovation import TECH_CATALOG
        if getattr(tile, '_engineering_turn', None) == turn:
            return
        tile._engineering_turn = turn
        tile.engineering_deliveries = {}
        capacity_left = workshop_capacity(tile)

        def deliver(tid, payer, budget, public, generation=None):
            nonlocal capacity_left
            tech = TECH_CATALOG.get(tid)
            if not tech:
                return
            readiness, cap, reason = self._engineering_readiness(nation, tech)
            if not readiness:
                result = {'effort': 0.0, 'spent': 0.0, 'reason': reason,
                          'cause_event_ids': [], 'consumed': {}, 'worker_ids': []}
            else:
                result = deliver_engineering(tile, nation, tech, payer, budget, turn, capacity_left)
            capacity_left -= len(result['worker_ids'])
            delivery = tile.engineering_deliveries.setdefault(tid, {
                'public_effort': 0.0, 'private_effort': 0.0, 'public_spent': 0.0,
                'private_spent': 0.0, 'cause_event_ids': [], 'reason': '', 'consumed': {},
                'worker_ids': [], 'private_generations': {}})
            prefix = 'public' if public else 'private'
            delivery[prefix + '_effort'] += result['effort']
            delivery[prefix + '_spent'] += result['spent']
            if not public:
                generation = generation or max(1, self.get_tech_tier(nation.name, tid))
                delivery['private_generations'][generation] = delivery['private_generations'].get(generation, 0) + result['effort']
            delivery['cause_event_ids'].extend(result['cause_event_ids'])
            delivery['worker_ids'].extend(result['worker_ids'])
            delivery['reason'] = result['reason']
            for g, quantity in result['consumed'].items():
                delivery['consumed'][g] = delivery['consumed'].get(g, 0) + quantity
            if result['spent'] > 0:
                from innovation_trace import emit_innovation
                delivery_id = emit_innovation(nation, kind='engineering_work_delivered', record_class='outcome',
                    subject_fields={'tech_id': tid, 'host': tile.name},
                    metric_id='innovation.engineering_effort', unit='skilled_shifts', after=result['effort'],
                    inputs={'turn': turn, 'public': public, 'budget_ceiling': budget,
                            'spent': result['spent'], 'consumed': result['consumed'],
                            'worker_ids': result['worker_ids'], 'work_share_per_worker': 0.5},
                    cause_event_ids=result['cause_event_ids'] or None)
                if delivery_id is not None:
                    delivery['cause_event_ids'].append(delivery_id)
                    for actor in tile.agents:
                        if actor.id in result['worker_ids']:
                            actor.engineering_work_event_id = delivery_id

        for tid, program in sorted(getattr(self, 'engineering_programs', {}).get(nation.name, {}).items()):
            if program['status'] == 'active' and program['budget'] > 0 and program['host'] == tile.name:
                capability_done = self.get_refinement_xp(nation.name, tid) >= program.get('capability_target', 100)
                cost_done = self.get_commercial_maturity(nation.name, tid, program.get('generation', 1)) >= program.get('maturity_target', 100)
                finished = capability_done if program['objective'] == 'performance' else cost_done if program['objective'] == 'economy' else capability_done and cost_done
                if finished:
                    continue  # Completion is announced by the innovation phase.
                deliver(tid, nation.government.agent, program['budget'], True)
        # Firms decide from last turn's actual use, not possession of a blueprint.
        if getattr(tile, '_technology_usage_turn', None) != turn - 1:
            return
        actors = {a.id: a for a in getattr(tile, 'agents', ())}
        seen = set()
        for row in tile.technology_usage.values():
            if row['work'] <= 0:
                continue
            for owner in row['owner_ids']:
                key = (row['tech_id'], owner)
                actor = actors.get(owner)
                if key in seen or actor is None or not getattr(actor, 'alive', True):
                    continue
                seen.add(key)
                # Cash reserve protects payroll and inputs. No fictitious profits
                # or research money are created when the firm cannot afford it.
                from technology_adoption import firm_reserve
                reserve = firm_reserve(actor, tile)
                intensity = min(1.0, row['work'] / max(1.0, row['capacity']))
                budget = min(25.0, max(0.0, actor.cash - reserve) * 0.05 * intensity)
                if budget > 0:
                    deliver(row['tech_id'], actor, budget, False, row['generation'])

    def engineering_status(self, nation, tech_id, t=None, program_override=None):
        """Read-only live projection used by every science UI."""
        from innovation import TECH_CATALOG
        tech = TECH_CATALOG[tech_id]
        program = self.get_engineering_program(nation.name, tech_id)
        if program_override is not None:
            program.update(program_override)
        xp = self.get_refinement_xp(nation.name, tech_id)
        generation = max(1, self.get_tech_tier(nation.name, tech_id))
        if program_override is not None:
            program['generation'] = generation
            program['capability_target'] = next((v for v in (1, 25, 60, 90, 100) if v > xp), 100)
            program['maturity_target'] = min(100, self.get_commercial_maturity(nation.name, tech_id, generation) + 20)
        maturity = self.get_commercial_maturity(nation.name, tech_id, generation)
        readiness, cap, constraint = self._engineering_readiness(nation, tech)
        rows, deliveries = [], []
        for tile in nation.tiles:
            if t is None or getattr(tile, '_technology_usage_turn', None) == t:
                rows.extend(r for r in getattr(tile, 'technology_usage', {}).values()
                            if r['tech_id'] == tech_id)
            if t is None or getattr(tile, '_engineering_turn', None) == t:
                deliveries.append(getattr(tile, 'engineering_deliveries', {}).get(tech_id, {}))
        active = [row for row in rows if row['work'] > 0]
        work, capacity = sum(r['work'] for r in rows), sum(r['capacity'] for r in rows)
        utilization = min(1.5, work / capacity) if capacity else 0.0
        private_effort = sum(d.get('private_effort', 0) for d in deliveries)
        host = next((tile for tile in nation.tiles if tile.name == program['host']), None)
        expected_spend, public_effort = 0.0, 0.0
        reason = constraint
        if program['status'] == 'active' and host is not None:
            # Use next-turn availability, not workers already reserved this turn.
            supply = engineering_supply(host, tech, (t or 0) + 1, nation.government.agent)
            affordable = min(program['budget'], max(0.0, nation.government.agent.cash))
            material_cost = sum(round(max(0.01, float(host.recipes.get(g, {}).get('price', 1))), 2)
                                for g in supply['goods'])
            if readiness:
                for worker in supply['people'][:supply['capacity']]:
                    cost = material_cost + round(max(2.0, float(getattr(worker, 'wage', 0))), 2)
                    if expected_spend + cost <= affordable:
                        expected_spend += cost
                        public_effort += engineering_skill(worker) * readiness
            expected_spend = round(expected_spend, 2)
            reason = reason or supply['reason']
            if not reason and expected_spend + supply['unit_cost'] <= program['budget']:
                reason = 'Available workshop staff and supplies limit spending.'
            if not reason and not public_effort:
                reason = 'Budget or available treasury cash limits engineering.'
        kwargs = dict(installations=len(active), utilization=utilization,
                      readiness=readiness, capability=xp, private_effort=private_effort * readiness,
                      objective=program['objective'],
                      blockaded=self.get_guild_blockade(nation, tech_id)['active'])
        baseline = refinement_rates(**kwargs)
        rates = refinement_rates(public_effort=public_effort, **kwargs)
        if xp == 0:
            # Developing the first prototype uses the same delivered effort.
            progress = getattr(self, 'engineering_discovery', {}).get(nation.name, {}).get(tech_id, 0.0)
            discovery_rate = 3 * public_effort * (0.25 if kwargs['blockaded'] else 1)
            forecast = {'capability_turns': math.ceil((100 - progress) / discovery_rate) if discovery_rate else None,
                        'capability_turns_without_program': None, 'economy_turns': None,
                        'economy_turns_without_program': None, 'capability_target': 1,
                        'conditional': 'At current staff and supply. Organic discovery may also occur.'}
        else:
            cost_generation = program.get('generation', generation) if program['status'] == 'active' else generation
            cost_rows = [r for r in active if r['generation'] == cost_generation]
            cost_capacity = sum(r['capacity'] for r in cost_rows)
            cost_private = sum(d.get('private_generations', {}).get(cost_generation, 0) for d in deliveries)
            cost_kwargs = dict(installations=len(cost_rows),
                               utilization=sum(r['work'] for r in cost_rows) / cost_capacity if cost_capacity else 0,
                               readiness=readiness, capability=xp, private_effort=cost_private * readiness,
                               objective=program['objective'], blockaded=kwargs['blockaded'])
            baseline['maturity'] = refinement_rates(**cost_kwargs)['maturity']
            rates['maturity'] = refinement_rates(public_effort=public_effort, **cost_kwargs)['maturity']
            forecast = engineering_forecast(xp, self.get_commercial_maturity(nation.name, tech_id, cost_generation),
                rates, baseline, cap,
                program.get('capability_target') if program['status'] == 'active' else None,
                program.get('maturity_target') if program['status'] == 'active' else None)
        from technology_adoption import REASON_LABELS
        commercial = []
        for tile in nation.tiles:
            for firm in getattr(tile, 'agents', ()):
                if not getattr(firm, 'is_corporation', False) or not getattr(firm, 'alive', True):
                    continue
                decision = getattr(firm, 'technology_adoption_decisions', {}).get(tech_id,
                    getattr(firm, 'last_technology_adoption_decision', {}))
                if decision.get('tech_id') != tech_id:
                    continue
                commercial.append({**decision, 'firm_id': firm.id,
                    'reason_text': REASON_LABELS.get(decision['reason'], decision['reason'].replace('_', ' ')),
                    'firm': getattr(firm, 'company_name', None) or f'Firm {firm.id}',
                    'tile': tile.name, 'constraint': decision.get('constraint', ''),
                    'installed_generation': max((getattr(b, 'technology_designs', {}).get(tech_id, 0)
                        for b in getattr(tile, 'buildings', ())
                        if getattr(b, 'private_owner_id', None) == firm.id), default=0),
                    'project_status': next((p.status for p in reversed(getattr(tile, 'construction_projects', ()))
                        if getattr(p, 'private_owner_id', None) == firm.id
                        and tech_id in getattr(p.recipe, 'technology_designs', {})), None)})
        return {'capability': xp, 'capability_name': CAPABILITY_NAMES[tier_for_xp(xp)],
                'generation': generation, 'maturity': maturity,
                'maturity_name': 'Mature' if maturity >= 75 else 'Developing' if maturity >= 25 else 'Experimental',
                'build_cost_factor': build_cost_factor(maturity), 'program': program,
                'operating_installations': len(active), 'utilization': utilization,
                'private_effort': private_effort, 'expected_spend': expected_spend,
                'last_public_spend': sum(d.get('public_spent', 0) for d in deliveries),
                'constraint': reason or ('No operating installations or funded experiments.'
                                         if not active and not public_effort else ''),
                'rates': rates, 'baseline_rates': baseline, 'forecast': forecast,
                'commercial_decisions': commercial,
                'hosts': [{'name': tile.name, 'label': getattr(tile, 'display_name', tile.name),
                           'workshop_capacity': workshop_capacity(tile)} for tile in nation.tiles]}

    def step_engineering_refinement(self, nations, t):
        from innovation import TECH_CATALOG
        from innovation_trace import record_refinement_progress, emit_innovation, record_technology
        events = []
        if not hasattr(self, 'tech_commercial_maturity'):
            self.tech_commercial_maturity = {}
        if not hasattr(self, 'engineering_discovery'):
            self.engineering_discovery = {}
        for nation in nations:
            if not nation.tiles:
                continue
            candidates = self.get_discovered_techs(nation.name) | set(
                getattr(self, 'engineering_programs', {}).get(nation.name, {}))
            for tid in sorted(candidates):
                if tid not in TECH_CATALOG:
                    continue
                if getattr(self, '_engineering_processed', {}).get((nation.name, tid)) == t:
                    continue
                if not hasattr(self, '_engineering_processed'):
                    self._engineering_processed = {}
                self._engineering_processed[nation.name, tid] = t
                tech = TECH_CATALOG[tid]
                rows, deliveries, manufactured = [], [], []
                for tile in nation.tiles:
                    if getattr(tile, '_technology_usage_turn', None) == t:
                        rows.extend(r for r in tile.technology_usage.values() if r['tech_id'] == tid)
                    if getattr(tile, '_engineering_turn', None) == t:
                        deliveries.append(getattr(tile, 'engineering_deliveries', {}).get(tid, {}))
                    manufactured.extend(row for row in getattr(tile, 'technology_manufactures', ())
                                        if row['turn'] == t and row['tech_id'] == tid)
                active = [r for r in rows if r['work'] > 0]
                work, capacity = sum(r['work'] for r in rows), sum(r['capacity'] for r in rows)
                public = sum(d.get('public_effort', 0) for d in deliveries)
                private = sum(d.get('private_effort', 0) for d in deliveries)
                program = self.get_engineering_program(nation.name, tid)
                readiness, cap, constraint = self._engineering_readiness(nation, tech)
                before = self.get_refinement_xp(nation.name, tid)
                old_tier = self.get_tech_tier(nation.name, tid)
                causes = [eid for row in rows + deliveries + manufactured for eid in row.get('cause_event_ids', ())]
                rates = refinement_rates(installations=len(active),
                    utilization=work / capacity if capacity else 0, readiness=readiness,
                    capability=before, public_effort=public * readiness,
                    private_effort=private * readiness, objective=program['objective'],
                    blockaded=self.get_guild_blockade(nation, tid)['active'])
                if not self.has_tech(nation.name, tid):
                    progress = self.engineering_discovery.setdefault(nation.name, {})
                    prior = progress.get(tid, 0.0)
                    progress[tid] = min(100.0, prior + public * readiness * 3 * (
                        0.25 if self.get_guild_blockade(nation, tid)['active'] else 1))
                    if progress[tid] != prior:
                        emit_innovation(nation, kind='engineering_prototype_progress', record_class='calculation',
                            subject_fields={'tech_id': tid}, metric_id='innovation.prototype_progress',
                            unit='percent', before=prior, after=progress[tid],
                            formula_id='engineering.prototype.v1',
                            inputs={'turn': t, 'prior': prior, 'increment': progress[tid] - prior,
                                    'delivered_effort': public, 'readiness': readiness},
                            cause_event_ids=causes or None)
                    if progress[tid] < 100:
                        continue
                    self.get_discovered_techs(nation.name).add(tid)
                    self.tech_refinement_xp.setdefault(nation.name, {})[tid] = 1.0
                    record_technology(nation, tid, t, 'funded_engineering_prototype', cause_event_ids=causes or None)
                    events.append({'t': t, 'nation': nation.name, 'tech_id': tid, 'event': 'DISCOVERY',
                                   'message': f'{nation.name}: funded experiments demonstrated a working {tech.name} prototype.'})
                    before = 1.0
                    rates = dict(rates, capability=0.0)
                after = max(before, min(cap, before + rates['capability']))
                self.tech_refinement_xp.setdefault(nation.name, {})[tid] = after
                if after != before:
                    record_refinement_progress(nation, tid, t, before, after, rates['capability'],
                        cap_xp=max(before, cap), operational_learning=rates['operational_learning'],
                        public_effort=public, private_effort=private, installed_count=len(active),
                        utilization=work / capacity if capacity else 0, constraint=constraint,
                        delivery_event_ids=causes, cause_event_ids=causes)
                generations = self.tech_commercial_maturity.setdefault(nation.name, {}).setdefault(tid, {})
                current_generation = max(1, old_tier)
                funded_generation = program.get('generation', current_generation)
                used_generations = {r['generation'] for r in active} | {r['generation'] for r in manufactured}
                if public or private:
                    used_generations.add(funded_generation)
                private_generations = {}
                for delivery in deliveries:
                    for generation, effort in delivery.get('private_generations', {}).items():
                        private_generations[generation] = private_generations.get(generation, 0) + effort
                used_generations.update(private_generations)
                for generation in sorted(used_generations):
                    already_recorded = generation in generations
                    prior = self.get_commercial_maturity(nation.name, tid, generation)
                    generation_rows = [r for r in active if r['generation'] == generation]
                    generation_capacity = sum(r['capacity'] for r in generation_rows)
                    grow = refinement_rates(
                        installations=len(generation_rows),
                        utilization=sum(r['work'] for r in generation_rows) / generation_capacity if generation_capacity else 0,
                        readiness=readiness, capability=before,
                        public_effort=public * readiness if generation == funded_generation else 0,
                        private_effort=private_generations.get(generation, 0) * readiness,
                        objective=program['objective'],
                        blockaded=self.get_guild_blockade(nation, tid)['active'])['maturity']
                    grow += 4.0 * sum(r['generation'] == generation for r in manufactured)
                    generations[generation] = min(100.0, prior + grow)
                    if generations[generation] != prior or not already_recorded:
                        recorded_before = prior if already_recorded else 0.0
                        emit_innovation(nation, kind='engineering_commercial_maturity', record_class='calculation',
                            subject_fields={'tech_id': tid, 'generation': generation},
                            metric_id='innovation.commercial_maturity', unit='percent',
                            before=recorded_before, after=generations[generation], formula_id='engineering.maturity.v1',
                            inputs={'turn': t, 'prior': recorded_before,
                                    'increment': prior + grow - recorded_before,
                                    'inherited_maturity': prior if not already_recorded else 0.0,
                                    'manufactures': len(manufactured)},
                            cause_event_ids=causes or None)
                        if prior < 75 <= generations[generation]:
                            events.append({'t': t, 'nation': nation.name, 'tech_id': tid, 'event': 'ENGINEERING',
                                'message': f'{nation.name}: Tier {generation} {tech.name} designs are now mature to manufacture. Review installation and retrofit costs.'})
                new_tier = self.get_tech_tier(nation.name, tid)
                if new_tier > old_tier and old_tier > 0:
                    events.append({'t': t, 'nation': nation.name, 'tech_id': tid, 'event': 'REFINEMENT',
                        'message': f'{nation.name}: {tech.name} reached {CAPABILITY_NAMES[new_tier]} (Tier {new_tier}). New installations and paid retrofits can use this design.'})
                if program['status'] == 'active':
                    reason = constraint or next((d.get('reason') for d in deliveries if d.get('reason')), '')
                    if not hasattr(self, '_engineering_constraints'):
                        self._engineering_constraints = {}
                    previous = self._engineering_constraints.get((nation.name, tid), '')
                    if reason and reason != previous:
                        events.append({'t': t, 'nation': nation.name, 'tech_id': tid, 'event': 'ENGINEERING',
                            'message': f'{nation.name}: {tech.name} engineering — {reason}'})
                    self._engineering_constraints[nation.name, tid] = reason
                    reached_cap = after >= program.get('capability_target', 100)
                    reached_cost = self.get_commercial_maturity(nation.name, tid, program.get('generation', 1)) >= program.get('maturity_target', 100)
                    done = reached_cap if program['objective'] == 'performance' else reached_cost if program['objective'] == 'economy' else reached_cap and reached_cost
                    if done:
                        self.engineering_programs[nation.name][tid]['status'] = 'completed'
                        emit_innovation(nation, kind='engineering_program_completed', record_class='outcome',
                            subject_fields={'tech_id': tid}, metric_id='innovation.engineering_program',
                            unit='status', before='active', after='completed',
                            inputs={'turn': t, 'capability': after,
                                    'capability_target': program.get('capability_target'),
                                    'maturity_target': program.get('maturity_target')},
                            cause_event_ids=causes or None)
                        events.append({'t': t, 'nation': nation.name, 'tech_id': tid, 'event': 'ENGINEERING',
                            'message': f'{nation.name}: {tech.name} engineering milestone reached. Public spending stopped.'})
        self.discovery_log.extend(events)
        return events
