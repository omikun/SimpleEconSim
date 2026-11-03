"""Comparable independent livelihood returns and the common career-phase adapter."""

from __future__ import annotations
from typing import Any
from goods import Goods
from labor_choice import (
    occupational_tenure_multiplier,
    can_enter_independent_trade,
)


def _trace_scheduler_gate(region, *, turn, outcome, total_non_elites,
                          group_count, active_group_index=None,
                          active_agent_ids=(), emergency_agent_reasons=(),
                          execution_agent_ids=(), deferred_count=0):
    from run_trace import emit

    return emit(
        region, kind='labor_scheduler_gate', record_class='decision',
        phase='labor', subject={'type': 'tile', 'id': region.name},
        metric_id='labor.cohort_schedule', unit='workers',
        before=int(total_non_elites), after=len(execution_agent_ids),
        formula_id='labor.common_career_phase.v1',
        inputs={'turn': int(turn), 'outcome': outcome,
                'total_non_elite_workers': int(total_non_elites),
                'group_count': int(group_count),
                'active_group_index': active_group_index,
                'active_cohort_agent_ids': [int(agent_id)
                                            for agent_id in active_agent_ids],
                'emergency_agent_reasons': list(emergency_agent_reasons),
                'execution_order_agent_ids': [int(agent_id)
                                              for agent_id in execution_agent_ids],
                'deferred_worker_count': int(deferred_count)})


def potential_commons_food(worker: Any, region: Any) -> int:
    """Meal a worker could gather after leaving paid work."""
    from foraging import BASE_FORAGE_YIELD
    from livelihood_access import effective_access

    access = effective_access(worker, region, 'commons_food')
    fertility = getattr(region, 'terrain', {}).get(Goods.food, 1.0)
    return min(4, max(0, int(BASE_FORAGE_YIELD * access * fertility)))


def independent_return(region: Any, worker: Any, good: Goods,
                       producer_count: int, turn: int | None = None) -> tuple[float, str]:
    """Expected *reachable* cash sales plus food kept for the worker's meal.

    Recipe prices alone are not income. A new independent producer can sell
    only into a market that actually cleared in recent turns; firms can still
    recruit workers into emerging sectors through a funded wage offer.
    """
    recipe = getattr(region, 'recipes', {}).get(good, {})
    if recipe.get('import_only') or recipe.get('production', 0) <= 0:
        return 0.0, 'not locally producible'
    if good not in (Goods.food, Goods.wood, Goods.wool, Goods.cotton,
                    Goods.furniture, Goods.cloth, Goods.prepared_food):
        return 0.0, 'no independent local market'
    from livelihood_access import effective_access, due_cash_for
    if good in (Goods.food, Goods.cotton) and effective_access(worker, region, 'field') <= 0:
        return 0.0, 'no usable field right'
    if good == Goods.wool and effective_access(worker, region, 'pasture') <= 0:
        return 0.0, 'no usable pasture right'
    if good == Goods.wood and (effective_access(worker, region, 'commons_food') <= 0
                               and worker.inv_get(Goods.wood, 0) <= 0):
        return 0.0, 'no reachable woodland right'
    if good in (Goods.cotton, Goods.wool) and float(getattr(region, 'terrain', {}).get(good, 0.0)) <= 0.1:
        return 0.0, 'terrain unsuitable'
    from career_transitions import profession
    incumbent = profession(worker) == good
    physical_output_cap = float(recipe.get('maxtotalprod', 0.0))
    if (good in (Goods.food, Goods.cotton, Goods.wool) and not incumbent
            and physical_output_cap > 0
            and producer_count >= max(1, int(physical_output_cap / float(recipe['production'])))):
        return 0.0, 'no field capacity'
    input_qty = float(recipe.get('numInput', 0))
    input_good = recipe.get('input')
    input_cost = 0.0
    if input_qty:
        input_price = float(region.recipes.get(input_good, {}).get('price', 0.0))
        if input_price <= 0 or worker.inv_get(input_good, 0) < input_qty and worker.cash < input_price * input_qty:
            return 0.0, 'inputs inaccessible'
        input_cost = input_price * input_qty
    cur_turn = int(turn if turn is not None else (getattr(region, '_last_turn', 0) or 0))
    allowed, gate_reason = can_enter_independent_trade(worker, good, input_cost, cur_turn)
    if not allowed:
        return 0.0, gate_reason
    if recipe.get('setup_good'):
        from abundance import enabled
        if not enabled(region):
            return 0.0, 'workshops disabled'
        equipment = recipe['setup_good']
        units = recipe.get('setup_units', 1)
        setup_cost = max(0, units - worker.inv_get(equipment, 0)) * region.recipes[equipment]['price']
        meal_cost = 4 * region.recipes[Goods.food]['price']
        if not incumbent and worker.cash < setup_cost + 2 * input_cost + 2 * meal_cost:
            return 0.0, 'workshop equipment or input capital unavailable'
    recent_sales = list(getattr(region, 'sold_log', {}).get(good, []))[-6:]
    if recent_sales:
        weights = [idx + 1 for idx in range(len(recent_sales))]
        smoothed_sales = sum(s * w for s, w in zip(recent_sales, weights)) / sum(weights)
    else:
        smoothed_sales = 0.0
    if recipe.get('setup_good'):
        # A new workshop may serve real, funded unfilled household orders even
        # before the first sale. A posted quote by itself is still no market.
        buyers = {a.id: a for a in region.agents if getattr(a, 'alive', True)}
        funded_orders = 0.0
        price = max(.001, float(recipe.get('price', 0.0)))
        for ident, plan in getattr(region, 'household_orders', {}).items():
            order = plan.get(good, {})
            buyer = buyers.get(ident)
            if buyer is not None and order.get('limit', 0) >= price:
                funded_orders += min(order.get('quantity', 0), max(0, buyer.cash) / price)
        stocked = sum(a.inv_get(good, 0) for a in region.agents if getattr(a, 'alive', True))
        smoothed_sales = max(smoothed_sales, max(0.0, funded_orders - stocked))
    is_incumbent = incumbent
    effective_producers = max(1, producer_count if is_incumbent else producer_count + 1)
    input_supply_factor = 1.0
    if input_qty > 0 and input_good is not None:
        recent_in_prod = list(getattr(region, 'production_log', {}).get(input_good, []))[-4:]
        recent_in_sold = list(getattr(region, 'sold_log', {}).get(input_good, []))[-4:]
        in_hist = recent_in_prod or recent_in_sold
        if in_hist:
            avg_in_avail = max(
                sum(recent_in_prod) / len(recent_in_prod) if recent_in_prod else 0.0,
                sum(recent_in_sold) / len(recent_in_sold) if recent_in_sold else 0.0,
            )
            total_in_needed = max(1.0, effective_producers * input_qty)
            input_supply_factor = min(1.0, avg_in_avail / total_in_needed)
            if not is_incumbent and input_supply_factor < 0.75 and worker.inv_get(input_good, 0) < input_qty:
                return 0.0, 'input supply bottleneck'
    sales_per_producer = smoothed_sales / effective_producers
    tenure_mult = occupational_tenure_multiplier(worker, good, cur_turn)
    yield_units = float(recipe['production']) * tenure_mult * input_supply_factor
    from abundance import enabled, proficiency
    if enabled(region):
        yield_units *= proficiency(worker, good)
    price = float(recipe.get('price', 0.0))
    dependents = sum(1 for child in getattr(worker, 'descendants', [])
                     if getattr(child, 'alive', False)
                     and getattr(child, 'is_native_child', False)
                     and child.age(cur_turn) < 14)
    retained_food = min(4.0 * (1 + min(2, dependents)), yield_units) if good == Goods.food else 0.0
    saleable = max(0.0, yield_units - retained_food)
    expected_sales = min(saleable, sales_per_producer) * price
    # Avoiding a lethal calorie deficit is worth more than its market price
    # to someone who has actually been hungry. This is a household utility
    # term, not an invented cash receipt.
    hunger_value = (min(40.0, 8.0 * max(0.0, float(worker.hungry_steps)))
                    if good == Goods.food else 0.0)
    subsistence_value = retained_food * price + hunger_value
    obligations = min(float(due_cash_for(worker.id, region, cur_turn)), expected_sales)
    if good != Goods.food and expected_sales <= 0.0:
        return 0.0, 'no observed buyer'
    setup_allowance = (setup_cost / 12 if recipe.get('setup_good') else 0.0)
    return max(0.0, expected_sales + subsistence_value - input_cost - obligations - setup_allowance), 'observed sales, access and household food'


class LaborMobilityScheduler:
    """Compatibility facade for the common regional career decision phase."""

    def __init__(self, target_group_time_sec=1.0, base_batch_size=80):
        self.target_group_time_sec = target_group_time_sec
        self.batch_size = base_batch_size
        self._n_groups = 1
        self._last_execution_times = []

    def calculate_n_groups(self, num_non_elites):
        return 1

    def get_non_elites(self, region, turn=None):
        from career_transitions import working_adult
        turn = int(turn if turn is not None else getattr(region, '_last_turn', 0) or 0)
        return [a for a in region.agents if working_adult(a, turn)]

    def step_labor_cohort(self, region, t):
        from career_transitions import step_careers
        result = step_careers(region, t)
        result['reallocations_count'] = result.get('switched', 0)
        result['cohort_size'] = result.get('processed', 0)
        result['cohort_index'] = 0
        _trace_scheduler_gate(region, turn=t,
            outcome=('already_processed_this_turn' if result.get('already_processed') else 'all_adults_considered'),
            total_non_elites=len(self.get_non_elites(region, t)), group_count=1,
            active_group_index=0, execution_agent_ids=[a.id for a in self.get_non_elites(region, t)]
            if not result.get('already_processed') else [])
        return result
