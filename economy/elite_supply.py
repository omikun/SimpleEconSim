"""Elite supply decisions and their evidence."""
from __future__ import annotations
from typing import Any, Dict, List, Optional


def _input_control_options(self, agent: Any, region: Any) -> List[Dict[str, Any]]:
    """Score practical supply-security moves for a short-input corporation."""
    if not getattr(agent, 'is_corporation', False) or agent.output not in region.recipes:
        return []
    recipe = region.recipes[agent.output]
    if recipe.get('numInput', 0) <= 0 or recipe.get('input') is None:
        return []
    good = recipe['input']
    price = float(region.recipes.get(good, {}).get('price', 1.0))
    needed = max(1, int(recipe['numInput'] * max(1, len(getattr(agent, 'employees', [])))))
    stock = int(agent.inv_get(good, 0))
    shortage = max(0, needed - stock)
    if shortage <= 0:
        return []
    margin = (float(recipe.get('production', 1.0))
              * float(recipe.get('price', 1.0)) - price * float(recipe.get('numInput', 0))
              - float(getattr(agent, 'wage', 0.0)) * max(1, len(getattr(agent, 'employees', []))))
    if margin <= 0:
        return [{'candidate': 'reduce_or_pause_output', 'feasible': bool(getattr(agent, 'employees', [])),
                 'good': good.name, 'shortage': shortage, 'estimated_margin': margin,
                 'score': max(0.0, -margin) + float(getattr(agent, 'wage', 0.0))
                 * len(getattr(agent, 'employees', [])),
                 'reason': 'input cost and payroll exceed expected output receipts'}]
    urgency = min(1.0, shortage / needed)
    options = []
    active_contract = any(c.get('status') == 'active' and c.get('lender_id') == agent.id
                          for c in getattr(region, 'offtake_contracts', []))
    growers = [a for a in region.agents if a.id != agent.id and getattr(a, 'alive', True)
               and not getattr(a, 'is_corporation', False) and a.output == good
               and getattr(a, 'assigned_plot_id', None)]
    grower = min(growers, key=lambda a: (a.cash, a.id), default=None)
    advance = min(15.0, max(3.0, price * 2.0))
    options.append({'candidate': 'advance_offtake', 'feasible': bool(grower and not active_contract
                      and agent.cash >= advance + 5.0), 'good': good.name,
                    'grower_id': grower.id if grower else None,
                    'plot_id': getattr(grower, 'assigned_plot_id', None) if grower else None,
                    'advance': advance, 'quantity': min(3, shortage),
                    'unit_price': round(price * .8, 2), 'shortage': shortage,
                    'estimated_margin': margin,
                    'score': urgency * min(1.0, margin / max(1.0, price * needed)) * 1.2,
                    'reason': 'fund a named grower and reserve part of the next harvest'})

    if grower is not None:
        from supply_rights import _seed_water_rights
        _seed_water_rights(region)
        target_plot = grower.assigned_plot_id
        rights = getattr(region, 'water_rights', [])
        target_units = sum(r.units for r in rights if r.plot_id == target_plot)
        water_units = min(.25, max(0.0, 1.25 - target_units))
        water_source = next((r for r in rights if r.plot_id != target_plot and r.units >= water_units
                             and any(a.id == r.holder_id and a.id != agent.id
                                     for a in region.agents)), None)
        if water_source is not None and water_units > 0:
            water_seller = next((a for a in region.agents if a.id == water_source.holder_id), None)
            options.append({'candidate': 'acquire_water_right',
                            'feasible': bool(water_seller and agent.cash >= 5.0),
                            'good': good.name, 'grower_id': grower.id,
                            'from_plot_id': water_source.plot_id, 'to_plot_id': target_plot,
                            'seller_id': water_seller.id, 'units': water_units, 'price': 5.0,
                            'shortage': shortage,
                            'score': urgency * min(.65, margin / max(1.0, price * needed)) * .7,
                            'reason': 'redirect a measured seasonal allocation to a named input grower'})

    controlled = [p for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                  if getattr(p, 'controlled_by_id', p.lord_id) == agent.id]
    for plot in getattr(getattr(region, 'tenure', None), 'plots', []):
        seller = next((a for a in region.agents if a.id == plot.lord_id), None)
        if (plot in controlled or seller is None or seller is agent or not getattr(seller, 'alive', True)
                or any(l.get('plot_id') == plot.plot_id and l.get('status') == 'active'
                       for l in getattr(region, 'land_leases', []))):
            continue
        lease_cost = max(5.0, price * max(.25, float(plot.fraction)) * 4.0)
        options.append({'candidate': 'lease_input_land', 'feasible': agent.cash >= lease_cost + 5,
                        'good': good.name, 'plot_id': plot.plot_id, 'seller_id': seller.id,
                        'price': lease_cost, 'shortage': shortage,
                        'score': urgency * min(.8, margin / max(1.0, price * needed)) * .6,
                        'reason': 'lease titled land while retaining named tenants and customary tenure'})

    existing = [c for c in getattr(region, 'market_charters', [])
                if c.get('status') == 'active' and c.get('sponsor_id') == agent.id]
    pending = [c for c in getattr(region, 'concession_petitions', [])
               if c.get('status') == 'proposed' and c.get('sponsor_id') == agent.id]
    options.append({'candidate': 'exclusive_processing_charter',
                    'feasible': (shortage >= 2 and agent.cash >= 20 and not existing and not pending
                                 and getattr(region, 'gov', None) is not None),
                    'good': good.name, 'fee': 10.0, 'term_turns': 10,
                    'shortage': shortage,
                    'score': urgency * min(.75, margin / max(1.0, price * needed)) * .5,
                    'reason': 'ask the government to restrict competing processors; approval is uncertain'})
    from economy.supply_strategy import value_options
    return value_options(agent, region, options)

def _execute_input_control(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
    from economy.elite_plan_execution import review_plan
    planned = review_plan(self, agent, region, t)
    if planned is not None:
        return planned
    active_plan = self._active_plans.get(agent.id)
    if active_plan and active_plan.get('proposal_id') is not None:
        proposal = next((p for p in getattr(region, 'supply_proposals', [])
                         if p['id'] == active_plan['proposal_id']), None)
        if proposal and proposal['status'] in ('proposed', 'countered'):
            return None
        if proposal:
            active_plan['status'] = proposal['status']
            active_plan['outcome_turn'] = t
    from run_trace import emit
    options = self._input_control_options(agent, region)
    viable = [row for row in options if row.get('feasible') and row.get('score', 0) > .08]
    if not viable:
        if options:
            emit(region, kind='supply_strategy_decision', record_class='decision',
                 subject={'type': 'agent', 'id': agent.id},
                 metric_id='market.supply_strategy', unit='candidate',
                 after='spot_or_route', formula_id='supply.incremental_owner_value.v1',
                 inputs={'candidates': options, 'selected': 'spot_or_route'})
        return None
    # Contracts are reversible and deliver material next harvest; leases and
    # charters have longer consequences and need materially higher pressure.
    viable.sort(key=lambda row: (-row['score'],
                                {'advance_offtake': 0, 'lease_input_land': 1,
                                 'exclusive_processing_charter': 2}.get(row['candidate'], 9)))
    best = viable[0]
    decision_event_id = emit(region, kind='supply_strategy_decision', record_class='decision',
                             subject={'type': 'agent', 'id': agent.id},
                             metric_id='market.supply_strategy', unit='candidate',
                             after=best['candidate'],
                             formula_id='supply.incremental_owner_value.v1',
                             inputs={'candidates': options, 'selected': best['candidate'],
                                     'runner_up': viable[1]['candidate'] if len(viable) > 1
                                     else 'spot_or_route',
                                     'action_stage': 'before_execution'})
    cause_event_ids = [decision_event_id] if decision_event_id is not None else None

    def record_submission_failure():
        emit(region, kind='supply_strategy_outcome', record_class='outcome',
             subject={'type': 'agent', 'id': agent.id},
             metric_id='market.supply_strategy_outcome', unit='status',
             after='submission_failed', formula_id='supply.action_submission.v1',
             cause_event_ids=cause_event_ids,
             inputs={'candidate': best['candidate'],
                     'reason': 'proposal validation or duplicate-offer gate blocked submission'})

    good = next(g for g in region.recipes if g.name == best['good'])
    if best['candidate'] == 'reduce_or_pause_output':
        worker_ids = []
        max_employees_before = int(getattr(agent, 'max_employees', 0))
        for worker in list(getattr(agent, 'employees', [])):
            worker_ids.append(worker.id)
            if getattr(worker, 'employer', None) is agent:
                worker.employer = None
            agreement = getattr(worker, 'labor_agreement', None)
            if agreement is not None:
                agreement.active = False
        agent.employees.clear()
        agent._supply_prior_max_employees = int(getattr(agent, 'max_employees', 0))
        agent.max_employees = 0
        agent.supply_pause_until = t + 5
        details = {'worker_ids': worker_ids, 'resume_turn': t + 5,
                   'estimated_margin': best['estimated_margin'],
                   'max_employees_before': max_employees_before,
                   'max_employees_after': int(agent.max_employees)}
        emit(region, kind='supply_strategy_outcome', record_class='outcome',
             subject={'type': 'agent', 'id': agent.id},
             metric_id='market.supply_strategy_outcome', unit='status',
             before='operating', after='output_paused',
             formula_id='supply.output_pause.v1', cause_event_ids=cause_event_ids,
             inputs={'candidate': best['candidate'], **details})
    elif best['candidate'] == 'advance_offtake':
        grower = next(a for a in region.agents if a.id == best['grower_id'])
        from supply_proposals import propose
        proposal = propose(region, 'advance_offtake', agent, grower,
                           turn=t, price=best['advance'], due_turn=t + 2,
                           plot_id=best['plot_id'], good=best['good'],
                           quantity=best['quantity'], unit_price=best['unit_price'],
                           max_price=best['advance'],
                           cause_event_ids=cause_event_ids)
        if proposal is None:
            record_submission_failure()
            return None
        details = proposal
    elif best['candidate'] == 'acquire_water_right':
        seller = next(a for a in region.agents if a.id == best['seller_id'])
        from supply_proposals import propose
        proposal = propose(region, 'water_right', agent, seller, turn=t,
                           price=best['price'], units=best['units'],
                           from_plot_id=best['from_plot_id'],
                           to_plot_id=best['to_plot_id'], max_price=best['price'] * 1.25,
                           cause_event_ids=cause_event_ids)
        if proposal is None:
            record_submission_failure()
            return None
        details = proposal
    elif best['candidate'] == 'lease_input_land':
        seller = next(a for a in region.agents if a.id == best['seller_id'])
        from supply_proposals import propose
        proposal = propose(region, 'land_lease', agent, seller, turn=t,
                           price=best['price'], plot_id=best['plot_id'],
                           lease_turns=10, max_price=best['price'] * 1.25,
                           cause_event_ids=cause_event_ids)
        if proposal is None:
            record_submission_failure()
            return None
        details = proposal
    else:
        from market_concessions import submit_concession_petition
        petition = submit_concession_petition(agent, region, good, 'exclusive_processing',
                                               best['fee'], best['term_turns'], t,
                                               cause_event_ids=cause_event_ids)
        if petition is None:
            record_submission_failure()
            return None
        details = petition
    self._active_plans[agent.id] = {'candidate': best['candidate'],
                                    'target_id': best.get('grower_id', best.get('plot_id')),
                                    'created_turn': t, 'review_turn': t + 5,
                                    'proposal_id': details.get('id') if isinstance(details, dict)
                                    and best['candidate'] in ('advance_offtake',
                                                               'acquire_water_right',
                                                               'lease_input_land') else None,
                                    'budget': best.get('advance', best.get('price', best.get('fee', 0))),
                                    'status': 'active'}
    return {'action_taken': best['candidate'].upper(), 'details': details,
            'selected_score': best['score'], 'candidate_options': options}
