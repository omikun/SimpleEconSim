"""Turn-aligned political samples and final regional accounting."""
import math
from logger import logwarning
from goods import Goods
import region_logistics as _logistics
import region_factions as _factions
from micro.region import disabled_phases


def run(region, t, flags, legacy):
    from micro.region.stepper import (audit_cash, log_metrics, total_cash,
                                      log_population_rate)
    from run_trace import emit
    # Metrics, Factions & Unrest
    log_metrics(region, t)
    region.migration_intent_log.append(_logistics.migration_intent_score(region))
    if flags.factions:
        _factions.step_factions(region, t)
    else:
        disabled_phases.factions(region)

    from unrest import step_unrest
    if flags.unrest:
        ev = step_unrest(region, t)
        region.unrest_flag = ev['stage'] != 'calm'
    else:
        disabled_phases.unrest(region)
    if legacy:
        income_snapshot = region.gov.seal_income(t)
        from government import trace_income_snapshot
        trace_income_snapshot(region.gov, region, income_snapshot, t,
                              scope='tile', member_tiles=[region.name])

    region.total_population.append(sum(v[-1] for v in region.population_log.values()))
    emit(region, kind='population_count_calculation', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='people.population', unit='people',
         before=region.total_population[-2] if len(region.total_population) > 1 else None,
         after=region.total_population[-1], formula_id='population.sum_professions.v1',
         inputs={'by_profession': {g.name if hasattr(g, 'name') else str(g): history[-1]
                                   for g, history in region.population_log.items() if history}})
    region.cost_of_living_log.append(region.cost_of_living)
    region.tenure_log.append(region.tenure.commons_access)
    plot_composition = [
        {'plot_id': str(plot.plot_id), 'fraction': float(plot.fraction),
         'tenure': getattr(plot.tenure, 'value', str(plot.tenure))}
        for plot in getattr(region.tenure, 'plots', [])]
    commons_access = float(region.tenure.commons_access)
    emit(region, kind='commons_access_calculation', record_class='calculation',
         phase='local', subject={'type': 'tile', 'id': region.name},
         metric_id='land.commons_access', unit='ratio',
         before=region.tenure_log[-2] if len(region.tenure_log) > 1 else None,
         after=commons_access, formula_id='tenure.commons_access_from_plots.v1',
         inputs={'plots': plot_composition, 'no_plot_default': 1.0,
                 'feudal_weight': 1.0, 'leasehold_weight': 0.5,
                 'commons_weight': 1.0, 'enclosed_weight': 0.0,
                 'upper_bound': 1.0})
    for history_name, attr_name, metric_id, kind in (
            ('food_foraged_log', 'food_foraged', 'food.foraged',
             'foraged_food_total'),
            ('food_purchased_log', 'food_purchased', 'food.purchased',
             'purchased_food_total')):
        agent_food_units = [
            {'agent_id': str(agent.id), 'food_units': int(
                getattr(agent, attr_name, 0))}
            for agent in region.agents
            if int(getattr(agent, attr_name, 0)) != 0]
        total_food = sum(row['food_units'] for row in agent_food_units)
        history = getattr(region, history_name)
        history.append(total_food)
        emit(region, kind=kind, record_class='calculation', phase='local',
             subject={'type': 'tile', 'id': region.name}, metric_id=metric_id,
             unit='food_units',
             before=history[-2] if len(history) > 1 else None,
             after=total_food, formula_id='food.source_total.v1',
             inputs={'agent_food_units': agent_food_units,
                     'agent_count': len(region.agents),
                     'contributor_count': len(agent_food_units)})
    bank = region.bank
    bank_equity = float(bank.equity)
    bank_equity_before = (float(region.bank_cash_log[-1])
                          if region.bank_cash_log else None)
    region.bank_cash_log.append(bank_equity)
    emit(region, kind='bank_equity_calculation', record_class='calculation',
         phase='finance', subject={'type': 'tile', 'id': region.name,
                                   'history_field': 'bank_cash_log'},
         metric_id='finance.bank_equity',
         unit=getattr(region, 'home_currency', None) or 'local_currency',
         before=bank_equity_before, after=bank_equity,
         formula_id='finance.bank_equity_balance_sheet.v1',
         inputs={'capital': float(bank.capital),
                 'deposits': float(bank.total_deposits),
                 'liabilities': float(bank.total_liabilities),
                 'equity_formula': 'capital + deposits - liabilities'})
    if getattr(region.bank, 'is_frozen', False):
        region.bank.frozen_turns += 1
        for a, dep in list(getattr(region.bank, 'deposits', {}).items()):
            if dep > 0 and hasattr(a, 'despair'):
                a.despair = min(1.0, getattr(a, 'despair', 0.0) + 0.02)
    cash_by_role = {}
    for agent in region.agents:
        role = ('government' if getattr(agent, 'is_government', False) else
                'corporation' if getattr(agent, 'is_corporation', False) else
                'trader' if getattr(agent, 'is_trader', False) else 'resident')
        cash_by_role[role] = cash_by_role.get(role, 0.0) + float(agent.cash)
    agent_cash_total = sum(float(agent.cash) for agent in region.agents)
    charity_cash = float(region.charity.agent.cash)
    total_cash_before = (float(region.total_cash_log[-1])
                         if region.total_cash_log else None)
    total_cash_value = total_cash(region)
    region.total_cash_log.append(total_cash_value)
    emit(region, kind='total_cash_calculation', record_class='calculation',
         phase='finance', subject={'type': 'tile', 'id': region.name},
         metric_id='finance.total_cash',
         unit=getattr(region, 'home_currency', None) or 'local_currency',
         before=total_cash_before, after=total_cash_value,
         formula_id='finance.total_cash_from_components.v1',
         inputs={'agent_cash_total': agent_cash_total,
                 'agent_cash_by_role': cash_by_role,
                 'agent_count': len(region.agents),
                 'bank_equity': bank_equity,
                 'charity_hand_cash': charity_cash,
                 'included_components': ['agent_wallets', 'bank_equity',
                                         'charity_hand_cash']})
    log_population_rate(region, turn=t)

    for p in region.goods:
        for g in region.goods:
            region.bought_log[p][g].append(0)

    if len(region.total_cash_log) >= 2:
        difference = math.fabs(region.total_cash_log[-2] - region.total_cash_log[-1])
        if difference > 1e-8:
            logwarning(t, f"Region '{region.name}' cash: {region.total_cash_log[-2]:.2f}->{region.total_cash_log[-1]:.2f} (d={difference:.2f})")

    if getattr(region, 'province', None) is None:
        from economy.actor_accounts import seal_turn
        seal_turn(region, t)

    if t % 100 == 0:
        circulating_cash = sum(a.cash for a in region.agents)
        print(f"--- Region '{region.name}' T={t}: circ=${circulating_cash:.0f}, "
              f"dep=${region.bank.total_deposits:.0f}, "
              f"liab=${region.bank.total_liabilities:.0f}, "
              f"r={region.bank.total_deposits/max(1,circulating_cash):.1f}x")
