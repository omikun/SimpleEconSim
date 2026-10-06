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
        non_elites = self.get_non_elites(region)
        total_non_elites = len(non_elites)

        if total_non_elites == 0:
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
            and getattr(a, 'employer', None) is None
            and (getattr(a, 'hungry_steps', 0) > 0
                 or getattr(a, 'social_class', None) == 'dispossessed'
                 or getattr(a, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0)
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

        for worker, is_emergency in execution_queue:
            # 1. Dispossessed Serf or Unemployed Seeking Wage Work
            is_dispossessed = (getattr(worker, 'assigned_plot_id', None) is None
                               and (getattr(worker, 'social_class', None) == 'dispossessed'
                                    or getattr(worker, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0))
            is_unemployed = getattr(worker, 'employer', None) is None

            # If unemployed and vacancies exist, apply to highest paying firm
            if is_unemployed and firms_with_vacancies:
                best_firm = firms_with_vacancies[0]
                worker.employer = best_firm
                best_firm.employees.append(worker)
                worker.wage = best_firm.wage
                old_output = worker.output
                worker.output = best_firm.output # Adopt firm's profession
                worker.last_career_switch = t

                reallocations.append({
                    'agent_id': worker.id,
                    'type': 'HIRED_BY_FIRM',
                    'firm_id': best_firm.id,
                    'old_profession': old_output.name if hasattr(old_output, 'name') else str(old_output),
                    'new_profession': worker.output.name if hasattr(worker.output, 'name') else str(worker.output),
                    'wage': best_firm.wage,
                    'was_dispossessed': is_dispossessed,
                    'is_emergency_fast_path': is_emergency,
                })

                # If firm reaches capacity, remove from open vacancies list
                if len(best_firm.employees) >= best_firm.max_employees:
                    firms_with_vacancies.pop(0)
                continue

            # 2. Independent Craftsman / Commoner Career Switch:
            # If independent and not bound to a lord, evaluate market returns across professions
            if is_unemployed and (is_emergency or (t - getattr(worker, 'last_career_switch', 0) >= 4)):
                recipes = getattr(region, 'recipes', {})
                best_good = None
                best_return = -999.0

                for g, r in recipes.items():
                    if g in (Goods.gov, Goods.none):
                        continue
                    p = float(r.get('price', 1.0))
                    yield_units = float(r.get('production', 1.0))
                    input_cost = 0.0
                    if r.get('numInput', 0) > 0 and r.get('input') in recipes:
                        input_cost = r['numInput'] * float(recipes[r['input']].get('price', 1.0))
                    expected_net = (p * yield_units) - input_cost

                    # If dispossessed, penalize food farming because they lack fields
                    if is_dispossessed and g == Goods.food:
                        expected_net *= 0.25

                    if expected_net > best_return:
                        best_return = expected_net
                        best_good = g

                # If another profession offers significantly higher returns, switch!
                if best_good and best_good != worker.output and best_return > 1.5:
                    old_output = worker.output
                    worker.output = best_good
                    worker.last_career_switch = t
                    reallocations.append({
                        'agent_id': worker.id,
                        'type': 'INDEPENDENT_SWITCH',
                        'old_profession': old_output.name if hasattr(old_output, 'name') else str(old_output),
                        'new_profession': best_good.name if hasattr(best_good, 'name') else str(best_good),
                        'expected_return': best_return,
                        'is_emergency_fast_path': is_emergency,
                    })

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
