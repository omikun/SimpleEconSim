"""Elite activation decisions and their evidence."""
from __future__ import annotations
from typing import Any, List, Optional, Tuple
from goods import Goods
from economy.transformation_graph import TransformationGraph


def get_market_luxuries(self, region: Any) -> List[Tuple[Any, float, float, int]]:
    """Identify available luxury goods in region or trade pipelines.

    Returns: list of (good, price, prestige_rating, available_qty)
    """
    luxuries = []
    recipes = getattr(region, 'recipes', {})
    goods = getattr(region, 'goods', ())
    if not goods:
        return luxuries
    luxury_specs = []
    for g in goods:
        spec = TransformationGraph.get_commodity_spec(g)
        if spec and spec.prestige_rating > 0:
            price = float(recipes.get(g, {}).get('price', spec.base_price))
            g_idx = g.value if isinstance(g, Goods) else None
            luxury_specs.append((g, g_idx, price, spec.prestige_rating))
    if not luxury_specs:
        return luxuries
    non_lords = [a for a in getattr(region, 'agents', ())
                 if getattr(a, 'alive', True) and not getattr(a, 'is_lord', False)]
    if not non_lords:
        return luxuries
    for g, g_idx, price, prestige in luxury_specs:
        if g_idx is not None:
            market_qty = sum(a.inventory[g_idx] for a in non_lords)
        else:
            market_qty = sum(a.inv_get(g, 0) for a in non_lords)
        if market_qty > 0:
            luxuries.append((g, price, prestige, market_qty))
    return luxuries

def check_new_market_items(self, region: Any) -> bool:
    """Check if any previously unobserved goods have appeared on the region market."""
    reg_name = getattr(region, 'name', 'default')
    known = self._known_market_goods.get(reg_name, set())
    current = set()
    live_agents = [a for a in getattr(region, 'agents', ()) if getattr(a, 'alive', True)]
    if live_agents:
        for g in getattr(region, 'goods', ()):
            if isinstance(g, Goods):
                g_idx = g.value
                for a in live_agents:
                    if a.inventory[g_idx] > 0:
                        current.add(g)
                        break
            else:
                for a in live_agents:
                    if a.inv_get(g, 0) > 0:
                        current.add(g)
                        break

    new_items = current - known
    self._known_market_goods[reg_name] = current
    has_new_items = bool(new_items)

    from run_trace import emit
    clock = getattr(region, '_collective_trace_clock', None)
    novelty_event_id = emit(
        region, kind='elite_market_novelty_scan',
        record_class='calculation', phase='local',
        subject={'type': 'tile', 'id': reg_name},
        metric_id='market.elite_market_novelty', unit='goods',
        after=len(new_items), formula_id='elite.market_novelty.v1',
        inputs={
            'previously_known_count': len(known),
            'currently_available_count': len(current),
            'new_goods': sorted(getattr(g, 'value', getattr(g, 'name', str(g)))
                                for g in new_items),
            'removed_goods': sorted(getattr(g, 'value', getattr(g, 'name', str(g)))
                                    for g in known - current),
            'market_has_new_items': has_new_items,
        })
    if novelty_event_id is not None and clock is not None:
        self._last_market_novelty_trace[id(region)] = (
            int(clock.get('turn', 0)), novelty_event_id)
    else:
        self._last_market_novelty_trace.pop(id(region), None)
    return has_new_items

def calculate_shadow_price_cash(self, agent: Any, region: Any,
                                _luxuries: Optional[List[Tuple[Any, float, float, int]]] = None) -> float:
    """Calculate dynamic shadow price of cash (lambda_cash) based on luxury desires."""
    base_lambda = 1.0
    luxuries = _luxuries if _luxuries is not None else self.get_market_luxuries(region)
    if not luxuries:
        return base_lambda

    # Check agent's existing luxury satisfaction
    held_luxury_prestige = 0.0
    for g, _, prestige, _ in luxuries:
        held_luxury_prestige += agent.inv_get(g, 0) * prestige

    # Marginal utility of cash spikes when high-prestige luxuries are available
    best_luxury_ratio = max(prestige / max(1.0, price) for _, price, prestige, _ in luxuries)
    saturation_discount = 1.0 / (1.0 + 0.1 * held_luxury_prestige)
    shadow_price = base_lambda + (best_luxury_ratio * 2.0 * saturation_discount)
    return round(shadow_price, 3)

def is_elite(self, agent: Any, region: Any) -> bool:
    """Check if agent qualifies as an elite (lord, capitalist, large merchant)."""
    if getattr(agent, 'is_lord', False):
        return True
    if getattr(agent, 'is_corporation', False) or getattr(agent, 'company_owned', None) is not None:
        return True
    if getattr(agent, 'cash', 0.0) >= 150.0:
        return True
    if getattr(agent, 'is_trader', False) and getattr(agent, 'cash', 0.0) >= 50.0:
        return True
    return False

def should_run_planning(self, agent: Any, region: Any, t: int, market_has_new_items: bool) -> bool:
    """Check the elite, novelty, proposal, concession, and five-turn gates."""
    if not self.is_elite(agent, region):
        return False
    reason = None
    considered_gates = ['elite_eligibility', 'market_novelty']
    matched_trigger = None
    if market_has_new_items:
        reason = 'new_market_item'
    else:
        matched_trigger = next((e for e in getattr(region, 'supply_proposal_events', [])
                                if e.get('turn') == t
                                and e.get('buyer_id') == agent.id), None)
        considered_gates.append('same_turn_supply_proposal')
        if matched_trigger is not None:
            reason = 'same_turn_supply_proposal'
        else:
            matched_trigger = next((e for e in getattr(region, 'concession_events', [])
                                    if e.get('turn') == t
                                    and e.get('sponsor_id') == agent.id), None)
            considered_gates.append('same_turn_concession')
            if matched_trigger is not None:
                reason = 'same_turn_concession'
            else:
                considered_gates.append('five_turn_cadence')
                reason = 'five_turn_cadence' if t % 5 == 0 else 'not_due'

    should_run = reason != 'not_due'
    from world_config import elite_planning_for
    plan = self._active_plans.get(agent.id)
    if (elite_planning_for(region).mode == 'active' and plan
            and plan.get('kind') in ('production_chain', 'production_hold')
            and plan['status'] not in ('completed', 'cancelled') and plan['review_turn'] <= t):
        reason, should_run = 'active_plan_due', True
    from run_trace import emit
    clock = getattr(region, '_collective_trace_clock', None)
    novelty_trace = self._last_market_novelty_trace.get(id(region))
    cause_event_ids = None
    if (market_has_new_items and novelty_trace is not None and clock is not None
            and novelty_trace[0] == int(clock.get('turn', 0))):
        cause_event_ids = [novelty_trace[1]]
    trigger_detail = None
    if matched_trigger is not None:
        trigger_detail = {
            key: matched_trigger.get(key)
            for key in ('proposal_id', 'petition_id', 'kind', 'status', 'reason',
                        'turn', 'buyer_id', 'sponsor_id')
            if key in matched_trigger
        }
    emit(region, kind='elite_planning_gate', record_class='decision',
         phase='local', subject={'type': 'agent', 'id': agent.id,
                                 'tile': getattr(region, 'name', 'default')},
         metric_id='market.elite_planning_gate', unit='boolean',
         after=int(should_run), formula_id='elite.planning_cadence.v2',
         cause_event_ids=cause_event_ids,
         inputs={
             'turn': int(t),
             'eligible_elite': True,
             'actor_basis': {'is_lord': bool(getattr(agent, 'is_lord', False)),
                             'is_corporation': bool(getattr(agent, 'is_corporation', False)),
                             'owns_company': getattr(agent, 'company_owned', None) is not None,
                             'is_trader': bool(getattr(agent, 'is_trader', False)),
                             'cash': float(getattr(agent, 'cash', 0.0))},
             'market_has_new_items': bool(market_has_new_items),
             'considered_gates': considered_gates,
             'reason': reason,
             'matched_trigger': trigger_detail,
             'cadence_modulus': 5,
             'turn_remainder': int(t) % 5,
         })
    return should_run

def record_planning_phase_gate(self, region: Any, t: int,
                               planning_enabled: bool) -> None:
    """Record whether the caller enabled the elite planner for this region."""
    from run_trace import emit
    scenario_owner_policy = bool(getattr(region, 'scenario_owner_policy', False))
    emit(region, kind='elite_planner_phase_gate', record_class='decision',
         phase='local', subject={'type': 'tile',
                                 'id': getattr(region, 'name', 'default')},
         metric_id='market.elite_planner_phase_gate', unit='boolean',
         after=int(bool(planning_enabled)),
         formula_id='elite.planning_phase_gate.v1',
         inputs={'turn': int(t),
                 'enabled': bool(planning_enabled),
                 'scenario_owner_policy': scenario_owner_policy,
                 'reason': ('scenario_owner_policy' if scenario_owner_policy
                            else 'standard_economy_planner_enabled')})
