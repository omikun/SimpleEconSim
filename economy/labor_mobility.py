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
    career_lifecycle_age,
    career_switch_hurdle_and_cooldown,
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
        formula_id='labor.round_robin_emergency_cohort.v1',
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
                    Goods.furniture, Goods.cloth):
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
    incumbent = getattr(worker, 'primary_livelihood', getattr(worker, 'output', None)) == good
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
    recent_sales = list(getattr(region, 'sold_log', {}).get(good, []))[-6:]
    if recent_sales:
        weights = [idx + 1 for idx in range(len(recent_sales))]
        smoothed_sales = sum(s * w for s, w in zip(recent_sales, weights)) / sum(weights)
    else:
        smoothed_sales = 0.0
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
    sales_per_producer = smoothed_sales / effective_producers if recent_sales else 0.0
    tenure_mult = occupational_tenure_multiplier(worker, good, cur_turn)
    yield_units = float(recipe['production']) * tenure_mult * input_supply_factor
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
    return max(0.0, expected_sales + subsistence_value - input_cost - obligations), 'observed sales, access and household food'


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

    def get_non_elites(self, region: Any, turn: int | None = None) -> List[Any]:
        """Filter region agents to all living non-elite agents (commoners, serfs, workers)."""
        return [
            a for a in getattr(region, 'agents', [])
            if getattr(a, 'alive', True)
            and not getattr(a, 'is_lord', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_corporation', False)
            and not (turn is not None and getattr(a, 'is_native_child', False)
                     and a.age(turn) < 14)
            and getattr(a, 'cash', 0.0) < 150.0
        ]

    def step_labor_cohort(self, region: Any, t: int) -> Dict[str, Any]:
        """Execute labor mobility and profession decisions for the active cohort on turn t."""
        start_time = time.perf_counter()
        if getattr(region, 'labor_scheduler_last_turn', None) == t:
            _trace_scheduler_gate(
                region, turn=t, outcome='already_processed_this_turn',
                total_non_elites=0, group_count=self._n_groups)
            return {'t': t, 'cohort_size': 0, 'n_groups': self._n_groups,
                    'elapsed_sec': 0.0, 'reallocations': [], 'already_processed': True}
        non_elites = self.get_non_elites(region, t)
        total_non_elites = len(non_elites)

        if total_non_elites == 0:
            region.labor_scheduler_last_turn = t
            _trace_scheduler_gate(
                region, turn=t, outcome='no_eligible_non_elite_workers',
                total_non_elites=0, group_count=1)
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

        # Prioritize emergency fast-path workers first, ordering younger entrants before seniors
        emergency_fast_path.sort(key=lambda a: career_lifecycle_age(a, t))
        active_cohort_sorted = sorted(active_cohort, key=lambda a: career_lifecycle_age(a, t))
        execution_queue = [(a, True) for a in emergency_fast_path] + [(a, False) for a in active_cohort_sorted]
        emergency_reasons = []
        for worker in emergency_fast_path:
            reasons = []
            if getattr(worker, 'hungry_steps', 0) >= 2:
                reasons.append('acute_hunger')
            if (getattr(worker, 'employer', None) is None
                    and getattr(worker, 'hungry_steps', 0) > 0):
                reasons.append('unemployed_hunger')
            if (getattr(worker, 'employer', None) is None
                    and getattr(worker, 'social_class', None) == 'dispossessed'):
                reasons.append('unemployed_dispossessed')
            if (getattr(worker, 'employer', None) is None
                    and getattr(worker, 'mem_avg', lambda *_: 0.0)(
                        'mem_eviction', 0.0) > 0):
                reasons.append('unemployed_eviction_memory')
            emergency_reasons.append({'agent_id': int(worker.id),
                                      'reasons': reasons})
        cohort_event_id = _trace_scheduler_gate(
            region, turn=t, outcome='cohort_selected',
            total_non_elites=total_non_elites, group_count=self._n_groups,
            active_group_index=active_group_idx,
            active_agent_ids=[worker.id for worker in active_cohort_sorted],
            emergency_agent_reasons=emergency_reasons,
            execution_agent_ids=[worker.id for worker, _ in execution_queue],
            deferred_count=total_non_elites - len(execution_queue))

        reallocations = []
        recipes_map = getattr(region, 'recipes', {})

        def _firm_effective_cap(f: Any) -> int:
            max_emp = int(getattr(f, 'max_employees', 10))
            rec = recipes_map.get(getattr(f, 'output', None), {})
            num_in = float(rec.get('numInput', 0))
            in_good = rec.get('input')
            if num_in > 0 and in_good is not None and not getattr(region, 'scenario_owner_policy', False):
                avail = float(f.inv_get(in_good, 0))
                if avail <= 0 and len(getattr(f, 'employees', [])) == 0:
                    return max_emp
                return min(max_emp, max(2, int(avail // num_in) + 2))
            return max_emp

        firms_with_vacancies = [
            f for f in getattr(region, 'agents', [])
            if getattr(f, 'is_corporation', False)
            and getattr(f, 'alive', True)
            and len(getattr(f, 'employees', [])) < _firm_effective_cap(f)
            and getattr(f, 'wage', 0.0) > 0.0
            and getattr(f, 'cash', 0.0) >= getattr(f, 'wage', 1.0)
        ]
        # Sort firms by highest wage offered
        firms_with_vacancies.sort(key=lambda f: (-f.wage, f.id))

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
                                     'quit_penalty_claim_id': outcome.get('claim_id')},
                             cause_event_ids=[cohort_event_id]
                             if cohort_event_id else None)
                        continue
            # 1. Dispossessed Serf or Unemployed Seeking Wage Work
            is_dispossessed = (getattr(worker, 'assigned_plot_id', None) is None
                               and (getattr(worker, 'social_class', None) == 'dispossessed'
                                    or getattr(worker, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0))
            is_unemployed = getattr(worker, 'employer', None) is None

            # Consider every funded vacancy in stable wage order. A rejection
            # from the highest bidder does not hide a feasible lower offer.
            if (is_unemployed and firms_with_vacancies
                    and not (getattr(getattr(region, 'gov', None), 'emergency_food_policy', False)
                             and worker.hungry_steps > 0
                             and worker.inv_get(Goods.food, 0) < 4
                             and potential_commons_food(worker, region) >= 2)):
                log = getattr(region, 'labor_decision_log', None)
                if log is None:
                    region.labor_decision_log = []
                    log = region.labor_decision_log
                from collective_trace_clock import stamp
                hired = False
                offer_rows = []
                for firm in list(firms_with_vacancies):
                    decision = evaluate_offer(worker, firm, region, t)
                    row = {'turn': t, 'worker_id': worker.id, 'firm_id': firm.id,
                           'accepted': decision.accepted, 'reason': decision.reason,
                           'offer': round(decision.offered_wage, 4),
                           'reservation': round(decision.reservation_wage, 4)}
                    log.append(stamp(region, row))
                    if len(offer_rows) < 8:
                        offer_rows.append(row)
                    if not decision.accepted:
                        continue
                    old_output = worker.output
                    if not attach_worker(worker, firm, t, decision, region=region):
                        continue
                    producer_counts[old_output] = max(0, producer_counts.get(old_output, 0) - 1)
                    reallocations.append({
                        'agent_id': worker.id, 'type': 'HIRED_BY_FIRM',
                        'firm_id': firm.id,
                        'old_profession': old_output.name if hasattr(old_output, 'name') else str(old_output),
                        'new_profession': worker.output.name if hasattr(worker.output, 'name') else str(worker.output),
                        'wage': decision.offered_wage,
                        'was_dispossessed': is_dispossessed,
                        'is_emergency_fast_path': is_emergency,
                    })
                    if len(firm.employees) >= _firm_effective_cap(firm):
                        firms_with_vacancies.remove(firm)
                    hired = True
                    break
                from run_trace import emit
                emit(region, kind='worker_wage_options', record_class='decision',
                     phase='labor', subject={'type': 'agent', 'id': worker.id,
                                             'tile': region.name},
                     metric_id='labor.offer_options', unit='decision',
                     after='hired' if hired else 'no_offer_accepted',
                     formula_id='labor.funded_offer_search.v1',
                     inputs={'offers': offer_rows, 'offers_truncated':
                             max(0, len(firms_with_vacancies) - len(offer_rows))},
                     cause_event_ids=[cohort_event_id]
                     if cohort_event_id else None)
                if hired:
                    continue

            # Retain non-starving operational building staff in their assigned facility role
            if worker.id in building_staff_ids and getattr(worker, 'hungry_steps', 0) < 2:
                continue

            # 2. Independent Craftsman / Commoner Career Switch:
            # If independent and not bound to a lord, evaluate market returns across professions
            is_acute_emergency = is_emergency and (is_dispossessed or getattr(worker, 'hungry_steps', 0) >= 3)
            hurdle_mult, min_cooldown, age_factor = career_switch_hurdle_and_cooldown(
                worker, t, is_emergency=is_acute_emergency)
            last_switch_turn = int(getattr(worker, 'last_career_switch', 0))
            turns_since_switch = t - last_switch_turn
            emergency_ready = is_acute_emergency and (last_switch_turn == 0 or turns_since_switch >= 4)
            regular_ready = turns_since_switch >= min_cooldown
            if is_unemployed and age_factor > 0.0 and (regular_ready or emergency_ready):
                # Keep a viable field while hungry; loss of access permits
                # another feasible livelihood even if the old output says food.
                from livelihood_access import effective_access
                if (getattr(worker, 'hungry_steps', 0) > 0 and not is_dispossessed
                        and worker.output == Goods.food
                        and effective_access(worker, region, 'field') > 0):
                    continue
                recipes = getattr(region, 'recipes', {})
                best_good = None
                best_return = -999.0
                prior_prof = worker.mem_last('mem_career_history') if hasattr(worker, 'mem_last') else None

                candidate_scores = []
                for g, r in recipes.items():
                    if g in (Goods.gov, Goods.none):
                        continue
                    # Emergency fast-path for hungry workers (non-dispossessed) only allows moving into food
                    if (not regular_ready and getattr(worker, 'hungry_steps', 0) > 0
                            and not is_dispossessed and g not in (Goods.food, worker.output)):
                        continue
                    expected_net, basis = independent_return(
                        region, worker, g, producer_counts.get(g, 0), turn=t)

                    # If dispossessed, penalize food farming because they lack fields
                    if is_dispossessed and g == Goods.food:
                        expected_net *= 0.25
                    # Anti-ping-pong hysteresis: penalize switching back to the immediately prior craft
                    if (g != worker.output and prior_prof == g.name
                            and not (g == Goods.food and getattr(worker, 'hungry_steps', 0) >= 2)):
                        expected_net *= 0.72
                    candidate_scores.append({'good': g.name, 'return': round(expected_net, 3),
                                             'basis': basis})

                    if expected_net > best_return:
                        best_return = expected_net
                        best_good = g

                # If another profession offers significantly higher returns, switch!
                current_return = next((row['return'] for row in candidate_scores
                                       if row['good'] == worker.output.name), 0.0)
                from run_trace import emit
                ranked_options = sorted(candidate_scores,
                                        key=lambda row: (-row['return'], row['good']))
                option_row = {'turn': int(t), 'person_id': int(worker.id),
                              'current': worker.output.name,
                              'current_return': round(current_return, 3),
                              'best': best_good.name if best_good is not None else 'none',
                              'best_return': round(best_return, 3),
                              'hurdle': round(hurdle_mult, 4),
                              'emergency': bool(is_emergency),
                              'options': ranked_options[:8]}
                decisions = getattr(region, 'livelihood_decision_events', [])
                decisions.append(option_row)
                region.livelihood_decision_events = decisions[-1000:]
                emit(region, kind='worker_livelihood_options', record_class='decision',
                     phase='labor', subject={'type': 'agent', 'id': worker.id,
                                             'tile': region.name},
                     metric_id='labor.livelihood_options', unit='decision',
                     after=best_good.name if best_good is not None else 'none',
                     formula_id='labor.observed_livelihood_search.v1',
                     inputs={'current': worker.output.name,
                             'current_return': current_return,
                             'best_return': round(best_return, 3),
                             'hurdle': round(hurdle_mult, 4),
                             'options': ranked_options[:8],
                             'options_omitted': max(0, len(ranked_options) - 8),
                             'emergency': is_emergency},
                     cause_event_ids=[cohort_event_id]
                     if cohort_event_id else None)
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
                            'candidates': ranked_options[:8],
                        },
                        constraints={
                            'min_cooldown_turns': min_cooldown,
                            'required_return_ratio': round(hurdle_mult, 4),
                            'capacity_basis': 'observed_sales_and_recipe_output',
                        },
                        cause_event_ids=[cohort_event_id]
                        if cohort_event_id else None,
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

        # Wall-clock time is diagnostic only. Letting machine load change the
        # batch size would change which people act on a seeded turn.

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
