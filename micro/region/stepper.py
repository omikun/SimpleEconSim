"""Regional turn entry points and shared accounting helpers."""

from __future__ import annotations
from typing import Any

from goods import Goods
from micro.region.helpers import get_total_cash


def _profession_population_members(region: Any) -> dict:
    """Capture the agents included by the local profession headcount rule."""
    members = {getattr(group, 'name', str(group)): {} for group in region.goods}
    members['trader'] = {}
    for agent in getattr(region, 'agents', ()):
        if (not getattr(agent, 'alive', True) or getattr(agent, 'is_corporation', False)
                or getattr(agent, 'is_government', False) or getattr(agent, 'is_trader', False)):
            continue
        output = getattr(agent, 'output', None)
        if output == Goods.food:
            group_name = Goods.food.name
        elif output != Goods.gov and output in region.goods:
            group_name = getattr(output, 'name', str(output))
        else:
            continue
        members.setdefault(group_name, {})[getattr(agent, 'id', None)] = agent
    for agent in getattr(region, 'trader_agents', ()):
        members['trader'][getattr(agent, 'id', None)] = agent
    return members


def sample_effective_workday_cap(region: Any) -> float:
    """Record the workday cap that governed this tile's production turn."""
    cap = float(getattr(region, 'workday_cap',
                        getattr(region, 'max_workday_hours', 16.0)))
    history = getattr(region, 'workday_cap_log', None)
    if history is None:
        history = []
        region.workday_cap_log = history
    before = history[-1] if history else None
    history.append(cap)
    from wilderness_trace import quiet
    if quiet(region):return cap
    from run_trace import emit
    emit(region, kind='effective_workday_cap_sample',
         record_class='calculation', phase='local',
         subject={'type': 'tile', 'id': region.name},
         metric_id='labor.statutory_workday', unit='hours',
         before=before, after=cap,
         formula_id='labor.effective_workday_cap_sample.v1',
         inputs={'effective_workday_cap': cap,
                 'workday_cap_field': 'workday_cap',
                 'statute_display_value': float(getattr(
                     region, 'max_workday_hours', cap)),
                 'sample_point': 'effective cap state recorded for this turn'})
    return cap


def step_economy(region: Any, t: int, gameplay_flags=None):
    """Run the ordered, independently gated regional turn phases."""
    from world_config import FULL_GAMEPLAY_FLAGS
    flags = FULL_GAMEPLAY_FLAGS if gameplay_flags is None else gameplay_flags
    region._gameplay_flags = flags
    legacy = getattr(region, 'province', None) is None
    region._last_turn = t
    if getattr(region, '_food_closed_turn', None) == t:
        return

    from micro.region.opening_phase import run as run_opening
    from micro.region.production_phase import run as run_production
    from micro.region.society_phase import run as run_society
    from micro.region.health_phase import run as run_health
    from micro.region.closeout_phase import run as run_closeout
    run_opening(region, t, flags, legacy)
    run_production(region, t, flags)
    run_society(region, t, flags, legacy)
    run_health(region, t, flags)
    run_closeout(region, t, flags, legacy)

def audit_cash(region: Any, t: int, label: str):
    """Log all cash components when anomalies occur."""
    current_actor_cash = {a.id: float(a.cash) for a in region.agents}
    if getattr(region, '_actor_cash_phase_turn', None) != int(t):
        region._actor_cash_phase_turn = int(t)
        region._actor_cash_phase_snapshot = current_actor_cash
        region._actor_cash_phase_changes = {}
    else:
        previous_actor_cash = getattr(region, '_actor_cash_phase_snapshot', {})
        phase_changes = getattr(region, '_actor_cash_phase_changes', {})
        for actor_id in set(previous_actor_cash) | set(current_actor_cash):
            change = current_actor_cash.get(actor_id, 0.0) - previous_actor_cash.get(actor_id, 0.0)
            if abs(change) > 1e-9:
                rows = phase_changes.setdefault(actor_id, [])
                rows.append({'phase': label, 'cash_change': round(change, 4)})
        region._actor_cash_phase_changes = phase_changes
        region._actor_cash_phase_snapshot = current_actor_cash

    agent_cash = sum(a.cash for a in region.agents)
    deposits = region.bank.total_deposits
    liabilities = region.bank.total_liabilities
    bank_equity = region.bank.equity
    total = agent_cash + bank_equity
    if total < 0 or agent_cash < 0 or deposits < 0 or liabilities < 0:
        print(f"  CASH AUDIT [{label}] T={t}: "
              f"agents=${agent_cash:.0f} "
              f"deposits=${deposits:.0f} "
              f"liabilities=${liabilities:.0f} "
              f"bank_eq=${bank_equity:.0f} "
              f"TOTAL=${total:.0f}")


def record_start(region: Any):
    for a in region.agents:
        a._start_cash = a.cash
        a._start_deposits = region.bank.deposits.get(a, 0)


def record_delta(region: Any):
    for a in region.agents:
        a._delta_cash = a.cash - a._start_cash
        a._delta_deposits = region.bank.deposits.get(a, 0) - a._start_deposits


def total_cash(region: Any) -> float:
    """Total cash including agents, bank equity, and charity's hand cash."""
    return get_total_cash(region.agents, region.bank) + region.charity.agent.cash


def live(region: Any, t: int, gameplay_flags=None):
    """Compatibility entry point for region lifecycle stepping."""
    from micro.region.lifecycle import step
    return step(region, t, gameplay_flags=gameplay_flags)


def log_gdp(region: Any):
    total = 0
    terms = {}
    for g in region.goods:
        if g != Goods.gov:
            value = region.production_log[g][-1] * region.recipes[g]['price']
            total += value
            region.gdp_by_profession_log[g].append(value)
            terms[g.name if hasattr(g, 'name') else str(g)] = {
                'units': region.production_log[g][-1],
                'reference_price': region.recipes[g]['price'], 'value': value}
    region.gdp_log.append(total)
    from run_trace import emit
    emit(region, kind='nominal_gdp_calculation', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='economy.gdp_nominal', unit='local_currency_per_turn',
         before=region.gdp_log[-2] if len(region.gdp_log) > 1 else None,
         after=total, formula_id='gdp.sum_output_times_reference_price.v1',
         inputs={'goods': terms})


def log_metrics(region: Any, t: int):
    from micro.region.telemetry import log_metrics as sample
    return sample(region, t)


def _trace_profession_population(region: Any, by_output: dict) -> None:
    from micro.region.telemetry import _trace_profession_population as trace
    return trace(region, by_output)


def log_population_rate(region: Any, turn: int | None = None):
    from micro.region.telemetry import log_population_rate as sample
    return sample(region, turn)
