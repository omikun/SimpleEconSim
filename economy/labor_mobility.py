"""
economy/labor_mobility.py — Cohort Scheduling & Labor Attraction Engine.

User Requirements:
1. "other agents should be split into n groups, each group runs on a different turn
    such that each group takes no more than 1 second to run"
2. "those with money invest in production or in labor that then stimulates more people
    to do those professions"
3. "when feudal lords cast out their serfs... [serfs become wage labor]"

Theoretical Grounding (Sven Beckert / Karl Polanyi):
Enclosure and dispossession tear customary producers away from the means of subsistence.
Lacking usufruct access to land, dispossessed commoners have no choice but to offer their
labor on the market. Meanwhile, capital investments by elites bid up wages and open vacancies
in new sectors (textiles, cotton, coal, iron), drawing free and dispossessed labor into
those expanding professions.
"""

from __future__ import annotations
import time
from typing import List, Dict, Any, Optional
from goods import Goods
from labor_choice import (
    evaluate_offer,
    attach_worker,
    apply_career_switch,
    career_switch_hurdle_and_cooldown,
    occupational_tenure_multiplier,
    can_enter_independent_trade,
)


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
    if good not in (Goods.food, Goods.wood, Goods.furniture):
        return 0.0, 'no independent local market'
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
    recent_sales = list(getattr(region, 'sold_log', {}).get(good, []))[-3:]
    sales_per_producer = ((sum(recent_sales) / len(recent_sales)) / max(1, producer_count)
                          if recent_sales else 0.0)
    tenure_mult = occupational_tenure_multiplier(worker, good, cur_turn)
    yield_units = float(recipe['production']) * tenure_mult
    price = float(recipe.get('price', 0.0))
    retained_food = min(4.0, yield_units) if good == Goods.food else 0.0
    saleable = max(0.0, yield_units - retained_food)
    expected_sales = min(saleable, sales_per_producer) * price
    # Avoiding a lethal calorie deficit is worth more than its market price
    # to someone who has actually been hungry. This is a household utility
    # term, not an invented cash receipt.
    hunger_value = (min(40.0, 8.0 * max(0.0, float(worker.hungry_steps)))
                    if good == Goods.food else 0.0)
    subsistence_value = retained_food * price + hunger_value
    return max(0.0, expected_sales + subsistence_value - input_cost), 'realized market and own meal'


class LaborMobilityScheduler:
    """Manages time-sliced execution of non-elite agents and career reallocation."""

    def __init__(self, target_group_time_sec: float = 1.0, base_batch_size: int = 80):
        self.target_group_time_sec = target_group_time_sec
        self.batch_size = base_batch_size
        self._n_groups: int = 5
        self._last_execution_times: List[float] = []

    def calculate_n_groups(self, num_non_elites: int) -> int:
        """Dynamically compute number of groups n so each group takes < 1 second."""
        if num_non_elites <= 0:
            return 1
        # Baseline estimation: 80 agents take ~0.01-0.05 seconds, well below 1.0s limit
        n = max(2, (num_non_elites + self.batch_size - 1) // self.batch_size)
        # Cap n between 2 and 10 for smooth cyclical interleaving
        return min(10, n)

    def get_non_elites(self, region: Any) -> List[Any]:
        """Filter region agents to all living non-elite agents (commoners, serfs, workers)."""
        return [
            a for a in getattr(region, 'agents', [])
            if getattr(a, 'alive', True)
            and not getattr(a, 'is_lord', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_corporation', False)
            and getattr(a, 'cash', 0.0) < 150.0
        ]

    def step_labor_cohort(self, region: Any, t: int) -> Dict[str, Any]:
        """Execute labor mobility and profession decisions for the active cohort on turn t."""
        start_time = time.perf_counter()
        if getattr(region, 'labor_scheduler_last_turn', None) == t:
            return {'t': t, 'cohort_size': 0, 'n_groups': self._n_groups,
                    'elapsed_sec': 0.0, 'reallocations': [], 'already_processed': True}
        non_elites = self.get_non_elites(region)
        total_non_elites = len(non_elites)

        if total_non_elites == 0:
            region.labor_scheduler_last_turn = t
            return {'t': t, 'cohort_size': 0, 'n_groups': 1, 'elapsed_sec': 0.0, 'reallocations': []}

        self._n_groups = self.calculate_n_groups(total_non_elites)
        active_group_idx = t % self._n_groups

        # Select agents belonging to active cohort evenly by list index
        active_cohort = [a for idx, a in enumerate(non_elites) if (idx % self._n_groups) == active_group_idx]
        active_ids = {a.id for a in active_cohort}

        # Event-driven emergency fast-path for starving or newly dispossessed commoners (Issue-10):
        # Workers with acute hunger (hungry_steps > 0) or unassigned evicted commoners
        # who are currently unemployed bypass their cohort turn barrier so they don't starve to death.
        emergency_fast_path = [
            a for a in non_elites
            if a.id not in active_ids
            and (getattr(a, 'hungry_steps', 0) >= 2
                 or (getattr(a, 'employer', None) is None
                     and (getattr(a, 'hungry_steps', 0) > 0
                          or getattr(a, 'social_class', None) == 'dispossessed'
                          or getattr(a, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0)))
        ]

        # Prioritize emergency fast-path workers first to fill urgent vacancies
        execution_queue = [(a, True) for a in emergency_fast_path] + [(a, False) for a in active_cohort]

        reallocations = []
        firms_with_vacancies = [
            f for f in getattr(region, 'agents', [])
            if getattr(f, 'is_corporation', False)
            and getattr(f, 'alive', True)
            and len(getattr(f, 'employees', [])) < getattr(f, 'max_employees', 10)
            and getattr(f, 'wage', 0.0) > 0.0
            and getattr(f, 'cash', 0.0) >= getattr(f, 'wage', 1.0)
        ]
        # Sort firms by highest wage offered
        firms_with_vacancies.sort(key=lambda f: f.wage, reverse=True)

        producer_counts = {}
        for person in getattr(region, 'agents', []):
            if (person.alive and person.employer is None and not person.is_trader
                    and not person.is_corporation):
                producer_counts[person.output] = producer_counts.get(person.output, 0) + 1

        building_staff_ids = {
            aid for b in getattr(region, 'buildings', [])
            for aid in getattr(b, 'staff_ids', [])
        }

        for worker, is_emergency in execution_queue:
            # A repeatedly hungry worker with a usable commons right can
            # recover food by leaving a job that keeps them from foraging.
            # Contract penalties remain named, enforceable obligations.
            firm = getattr(worker, 'employer', None)
            if firm is not None and worker.hungry_steps >= 2:
                possible_food = potential_commons_food(worker, region)
                if possible_food >= 2 and worker.inv_get(Goods.food, 0) < 4:
                    from labor_contract import quit_job
                    penalty = max(0.0, float(worker.wage) * 2.0)
                    outcome = quit_job(worker, region, t, penalty=penalty)
                    if outcome['success']:
                        from run_trace import emit
                        emit(region, kind='subsistence_job_exit',
                             record_class='decision', phase='labor',
                             subject={'type': 'agent', 'id': worker.id,
                                      'tile': region.name},
                             metric_id='labor.subsistence_exit', unit='worker',
                             after=1,
                             inputs={'firm_id': firm.id, 'hungry_steps': worker.hungry_steps,
                                     'wage': worker.wage, 'food_price': region.recipes[Goods.food]['price'],
                                     'potential_commons_food': possible_food,
                                     'quit_penalty_claim_id': outcome.get('claim_id')})
                        continue
            # 1. Dispossessed Serf or Unemployed Seeking Wage Work
            is_dispossessed = (getattr(worker, 'assigned_plot_id', None) is None
                               and (getattr(worker, 'social_class', None) == 'dispossessed'
                                    or getattr(worker, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0))
            is_unemployed = getattr(worker, 'employer', None) is None

            # If unemployed and vacancies exist, apply to highest paying firm
            if (is_unemployed and firms_with_vacancies
                    and not (getattr(getattr(region, 'gov', None), 'emergency_food_policy', False)
                             and worker.hungry_steps > 0
                             and worker.inv_get(Goods.food, 0) < 4
                             and potential_commons_food(worker, region) >= 2)):
                best_firm = firms_with_vacancies[0]
                old_output = worker.output
                decision = evaluate_offer(worker, best_firm, region, t)
                log = getattr(region, 'labor_decision_log', None)
                if log is None:
                    region.labor_decision_log = []
                    log = region.labor_decision_log
                row = {'turn': t, 'worker_id': worker.id, 'firm_id': best_firm.id,
                            'accepted': decision.accepted, 'reason': decision.reason,
                            'offer': round(decision.offered_wage, 4),
                            'reservation': round(decision.reservation_wage, 4)}
                from collective_trace_clock import stamp
                log.append(stamp(region, row))
                if decision.accepted and attach_worker(worker, best_firm, t, decision, region=region):
                    producer_counts[old_output] = max(0, producer_counts.get(old_output, 0) - 1)
                    reallocations.append({
                        'agent_id': worker.id,
                        'type': 'HIRED_BY_FIRM',
                        'firm_id': best_firm.id,
                        'old_profession': old_output.name if hasattr(old_output, 'name') else str(old_output),
                        'new_profession': worker.output.name if hasattr(worker.output, 'name') else str(worker.output),
                        'wage': decision.offered_wage,
                        'was_dispossessed': is_dispossessed,
                        'is_emergency_fast_path': is_emergency,
                    })
                    if len(best_firm.employees) >= best_firm.max_employees:
                        firms_with_vacancies.pop(0)
                    continue

            # Retain non-starving operational building staff in their assigned facility role
            if worker.id in building_staff_ids and getattr(worker, 'hungry_steps', 0) < 2:
                continue

            # 2. Independent Craftsman / Commoner Career Switch:
            # If independent and not bound to a lord, evaluate market returns across professions
            hurdle_mult, min_cooldown, age_factor = career_switch_hurdle_and_cooldown(
                worker, t, is_emergency=is_emergency)
            turns_since_switch = t - int(getattr(worker, 'last_career_switch', 0))
            if (is_unemployed and age_factor > 0.0
                    and (is_emergency or turns_since_switch >= min_cooldown)):
                recipes = getattr(region, 'recipes', {})
                best_good = None
                best_return = -999.0

                candidate_scores = []
                for g, r in recipes.items():
                    if g in (Goods.gov, Goods.none):
                        continue
                    expected_net, basis = independent_return(
                        region, worker, g, producer_counts.get(g, 0), turn=t)

                    # If dispossessed, penalize food farming because they lack fields
                    if is_dispossessed and g == Goods.food:
                        expected_net *= 0.25
                    candidate_scores.append({'good': g.name, 'return': round(expected_net, 3),
                                             'basis': basis})

                    if expected_net > best_return:
                        best_return = expected_net
                        best_good = g

                # If another profession offers significantly higher returns, switch!
                current_return = next((row['return'] for row in candidate_scores
                                       if row['good'] == worker.output.name), 0.0)
                if (best_good and best_good != worker.output
                        and best_return > max(1.5, current_return * hurdle_mult)):
                    old_output = worker.output
                    incumbent_tenure_mult = occupational_tenure_multiplier(worker, old_output, t)
                    apply_career_switch(
                        region, worker, best_good, t,
                        kind='independent_career_decision',
                        reason='independent_return_maximization',
                        record_class='decision',
                        formula_id='labor.independent_career_return.v2',
                        inputs={
                            'expected_return': best_return,
                            'current_return': current_return,
                            'hurdle_multiplier': round(hurdle_mult, 4),
                            'incumbent_tenure_multiplier': round(incumbent_tenure_mult, 4),
                            'emergency': is_emergency,
                            'candidates': candidate_scores,
                        },
                        constraints={
                            'min_cooldown_turns': min_cooldown,
                            'required_return_ratio': round(hurdle_mult, 4),
                        },
                    )
                    producer_counts[old_output] = max(0, producer_counts.get(old_output, 0) - 1)
                    producer_counts[best_good] = producer_counts.get(best_good, 0) + 1
                    reallocations.append({
                        'agent_id': worker.id,
                        'type': 'INDEPENDENT_SWITCH',
                        'old_profession': old_output.name if hasattr(old_output, 'name') else str(old_output),
                        'new_profession': best_good.name if hasattr(best_good, 'name') else str(best_good),
                        'expected_return': best_return,
                        'is_emergency_fast_path': is_emergency,
                    })

        region.labor_scheduler_last_turn = t
        elapsed_sec = time.perf_counter() - start_time
        self._last_execution_times.append(elapsed_sec)

        # Dynamic throttling safety: If group ever exceeds 0.8s, decrease batch size
        if elapsed_sec > 0.8:
            self.batch_size = max(20, int(self.batch_size * 0.75))

        return {
            't': t,
            'cohort_index': active_group_idx,
            'n_groups': self._n_groups,
            'cohort_size': len(active_cohort),
            'emergency_fast_path_count': len(emergency_fast_path),
            'elapsed_sec': round(elapsed_sec, 6),
            'reallocations_count': len(reallocations),
            'reallocations': reallocations,
        }
