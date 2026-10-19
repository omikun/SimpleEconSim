"""Funded, staffed strategic repairs in the Guided Egypt campaign.

These small works use actual Egyptian treasury cash and local household labor.
They deliberately do not duplicate the sandbox's larger building recipes.
"""

from __future__ import annotations

from math import ceil
from typing import Any

from finance_trace import account_ref, emit_treasury_leg, transfer_contract
from goods import Goods
from nutrition import CALORIES_PER_FOOD, deficit_fraction, feed_emergency_meal


PROJECT_DEFS = {
    'nile_repair': {
        'front': 'food', 'title': 'Repair Nile channels',
        'sites': ('Nile Delta', 'Upper Egypt'), 'cash_cost': 45.0,
        'work_turns': 2, 'workers': 3, 'upkeep': 2.0,
    },
    'revenue_office': {
        'front': 'fiscal', 'title': 'Staff Egyptian revenue office',
        'sites': ('Alexandria',), 'cash_cost': 60.0,
        'work_turns': 3, 'workers': 3, 'upkeep': 3.0,
        'national_share': 0.4,
    },
    'canal_line': {
        'front': 'sovereignty', 'title': 'Prepare the canal defense line',
        'sites': ('Tel el Kebir',), 'cash_cost': 70.0,
        'work_turns': 2, 'workers': 3, 'upkeep': 5.0, 'supply_food': 6,
    },
}


def initialize(world: dict) -> None:
    world['scenario_state']['strategic_projects'] = {
        'projects': [], 'payments': [], 'events': [], 'food_reports': [],
        'revenue_reports': [], 'fiscal_challenge': None, 'selected': None,
        'grain_entitlement_active': False, 'grain_entitlement_reports': [],
        'reserve_recall_used': False, 'reserve_recall_reports': [],
    }


def _state(world: dict) -> dict:
    return world['scenario_state']['strategic_projects']


def _trace_district_action(region, nation, *, action_id, turn, success,
                           reason, inputs, cause_event_ids=None):
    if region is None:
        return None
    from run_trace import emit

    return emit(
        region, kind=f'{action_id}_resolved', record_class='outcome',
        phase='scenario_projects',
        subject={'type': 'tile', 'id': region.name,
                 'nation': getattr(nation, 'name', region.name),
                 'action_id': action_id},
        metric_id='scenario.district_action', unit='success',
        before=0, after=int(bool(success)),
        formula_id='scenario_projects.district_action.v1',
        inputs={'operation_id': f'{action_id}:{getattr(nation, "name", "unknown")}:{int(turn)}',
                'action_id': action_id, 'turn': int(turn),
                'success': bool(success), 'reason': reason, **inputs},
        cause_event_ids=cause_event_ids)


def _nation(world: dict, name: str):
    return next((nation for nation in world['nations'] if nation.name == name), None)


def _tile(world: dict, site: str):
    tile_name = world['scenario_state']['geography']['sites'][site]['tile']
    return next((tile for tile in world['tiles'] if tile.name == tile_name), None)


def _occupier(world: dict, site: str) -> str | None:
    control = world['scenario_state']['campaign']['territorial_control']
    if site == 'Tel el Kebir':
        return control.get('Tel el Kebir') or control.get('Cairo')
    return control.get(site)


def _workers(tile, count: int) -> list:
    people = [agent for agent in getattr(tile, 'agents', [])
              if getattr(agent, 'alive', True)
              and not getattr(agent, 'is_government', False)
              and not getattr(agent, 'is_corporation', False)
              and not getattr(agent, 'is_trader', False)
              and not getattr(agent, 'is_lord', False)]
    people.sort(key=lambda agent: (getattr(agent, 'employer', None) is not None,
                                   float(agent.cash), agent.id))
    return people[:count]


def _record_person_cash_payment(region, nation, *, operation_id, kind, amount,
                                person, turn, treasury_before, treasury_after,
                                person_before, person_after, references):
    currency = getattr(nation, 'currency', None) or 'local_currency'
    recipient_currency = getattr(region, 'home_currency', None) or currency
    payer = account_ref(
        'nation_treasury', nation.name, currency,
        subaccount='government_agent.cash', balance_before=treasury_before,
        balance_after=treasury_after, balance_scope='government_agent.cash')
    payee = account_ref(
        'agent', person.id, recipient_currency,
        balance_before=person_before, balance_after=person_after,
        balance_scope='cash')
    contract = transfer_contract(
        operation_id, kind, side='payer', amount=amount,
        amount_currency=currency, payer_account=payer, payee_account=payee,
        local_cash_leg_amount=amount, local_cash_leg_currency=currency,
        counterparty_leg_status='recipient_cash_balance_captured',
        mutation_reference={**references, 'person_id': person.id,
                            'turn': turn, 'payment_kind': kind})
    return emit_treasury_leg(
        region, kind=f'scenario_{kind}', nation_name=nation.name,
        currency=currency, signed_amount=-amount, contract=contract,
        phase='scenario_projects', inputs={**references, 'person_id': person.id,
                                           'turn': turn})


def _record_internal_cash_transfer(region, nation, *, operation_id, kind,
                                   amount, payer_name, payer_balance_before,
                                   payer_balance_after, payee_name,
                                   payee_balance_before, payee_balance_after,
                                   turn, payer_type='municipal_government',
                                   payee_type='sovereign_government'):
    currency = getattr(nation, 'currency', None) or 'local_currency'
    payer = account_ref(
        payer_type, payer_name, currency, subaccount='government_agent.cash',
        balance_before=payer_balance_before, balance_after=payer_balance_after,
        balance_scope='government_agent.cash')
    payee = account_ref(
        payee_type, payee_name, currency, subaccount='government_agent.cash',
        balance_before=payee_balance_before, balance_after=payee_balance_after,
        balance_scope='government_agent.cash')
    event_ids = []
    for side, signed_amount in (('payer', -amount), ('payee', amount)):
        contract = transfer_contract(
            operation_id, kind, side=side, amount=amount,
            amount_currency=currency, payer_account=payer, payee_account=payee,
            local_cash_leg_amount=amount, local_cash_leg_currency=currency,
            counterparty_leg_status='paired_internal_transfer_same_nation',
            mutation_reference={'turn': turn, 'operation': kind})
        event_id = emit_treasury_leg(
            region, kind=f'{kind}_{side}', nation_name=nation.name,
            currency=currency, signed_amount=signed_amount, contract=contract,
            phase='scenario_projects',
            inputs={'turn': turn, 'operation_id': operation_id})
        if event_id is not None:
            event_ids.append(event_id)
    return event_ids


def _pay_workers(world: dict, project: dict, amount: float, kind: str,
                 trace_event_ids=None) -> bool:
    egypt = _nation(world, 'Egypt')
    treasury = egypt.government.agent
    tile = _tile(world, project['site'])
    by_id = {agent.id: agent for agent in _workers(tile, len(tile.agents))}
    workers = [by_id[ident] for ident in project['worker_ids'] if ident in by_id]
    if len(workers) < int(PROJECT_DEFS[project['kind']]['workers']) or treasury.cash < amount:
        return False
    amount = round(float(amount), 6)
    share = round(amount / len(workers), 6)
    for index, worker in enumerate(workers):
        wage = share if index < len(workers) - 1 else round(amount - share * (len(workers) - 1), 6)
        treasury_before = float(treasury.cash)
        worker_before = float(worker.cash)
        treasury.cash -= wage
        worker.cash += wage
        event_id = _record_person_cash_payment(
            tile, egypt, operation_id=(
                f"project:{project['id']}:{world['turn']}:{kind}:{worker.id}:"
                f'{treasury_before:.6f}'),
            kind=kind, amount=wage, person=worker, turn=int(world['turn']),
            treasury_before=treasury_before, treasury_after=float(treasury.cash),
            person_before=worker_before, person_after=float(worker.cash),
            references={'project_id': project['id'], 'worker_id': worker.id,
                        'site': project['site']})
        if event_id is not None and trace_event_ids is not None:
            trace_event_ids.append(event_id)
        _state(world)['payments'].append({
            'turn': int(world['turn']), 'kind': kind, 'project': project['id'],
            'payer': 'Egypt', 'recipient_id': worker.id, 'amount': wage,
        })
    return True


def _event(world: dict, project: dict, message: str) -> None:
    event = {'turn': int(world['turn']), 'project': project['id'], 'message': message}
    project['events'].append(event)
    _state(world)['events'].append(event)
    world['scenario_feedback'] = message


def _project_trace_region(world: dict, site: str | None = None):
    tiles = list(world.get('tiles', ()))
    if site is not None:
        site_data = world.get('scenario_state', {}).get('geography', {}).get(
            'sites', {}).get(site, {})
        site_tile = next((tile for tile in tiles
                          if tile.name == site_data.get('tile')), None)
        if (site_tile is not None
                and getattr(site_tile, '_run_trace', None) is not None
                and getattr(site_tile, '_collective_trace_clock', None) is not None):
            return site_tile
    return next((tile for tile in tiles
                 if getattr(tile, '_run_trace', None) is not None
                 and getattr(tile, '_collective_trace_clock', None) is not None), None)


def _project_operation_id(world: dict, action: str, kind: str, site: str):
    region = _project_trace_region(world, site)
    clock = getattr(region, '_collective_trace_clock', None) if region else None
    ordinal = int(clock.get('next', 1)) if clock is not None else int(world.get('turn', 0))
    return f'project:{action}:{kind}:{site}:{int(world.get("turn", 0))}:{ordinal}'


def _project_trace_state(project):
    if project is None:
        return None
    return {
        'status': project.get('status'),
        'progress': int(project.get('progress', 0)),
        'required_work': int(project.get('required_work', 0)),
        'integrity': float(project.get('integrity', 1.0)),
        'paid_cash': float(project.get('paid_cash', 0.0)),
        'upkeep_paid': float(project.get('upkeep_paid', 0.0)),
        'last_upkeep_turn': project.get('last_upkeep_turn'),
        'last_advanced_turn': project.get('last_advanced_turn'),
        'review_due_turn': project.get('review_due_turn'),
        'worker_ids': list(project.get('worker_ids', ())),
    }


def _trace_project_lifecycle(world, *, action, kind, site, project_id,
                             success, reason, before, after, details=None,
                             operation_id=None, cause_event_ids=None):
    region = _project_trace_region(world, site)
    if region is None:
        return None
    from run_trace import emit
    operation_id = operation_id or _project_operation_id(world, action, kind, site)
    return emit(
        region, kind=f'scenario_project_{action}',
        record_class='outcome' if success else 'decision',
        phase='scenario_projects',
        subject={'type': 'nation/project', 'id': project_id,
                 'nation': 'Egypt', 'site': site},
        metric_id='scenario.project_lifecycle', unit='project_state',
        before=before, after=after,
        formula_id='scenario_projects.lifecycle.v1',
        inputs={'operation_id': operation_id, 'action': action,
                'turn': int(world.get('turn', 0)), 'success': bool(success),
                'reason': reason, 'state_before': before, 'state_after': after,
                **(details or {})},
        cause_event_ids=cause_event_ids)


def _trace_project_crew_food(world, project, egypt, workers, supply_needed,
                             stock_before, worker_food_before):
    from run_trace import emit
    tile = _tile(world, project['site'])
    units_per_worker = int(supply_needed) // max(1, len(workers))
    stock_after = int(egypt.government.food_inventory)
    event_ids = []
    for worker in workers:
        worker_before = int(worker_food_before.get(worker.id, 0))
        event_id = emit(
            tile, kind='scenario_project_crew_food_transfer',
            record_class='transfer', phase='scenario_projects',
            subject={'type': 'agent', 'id': worker.id},
            metric_id='goods.project_crew_food', unit='food_units',
            before=worker_before, after=worker_before + units_per_worker,
            inputs={'operation_id':
                    f"project:{project['id']}:{int(world['turn'])}:crew_food:{worker.id}",
                    'project_id': project['id'], 'site': project['site'],
                    'source': 'Egyptian public stores',
                    'source_inventory_before': int(stock_before),
                    'source_inventory_after': stock_after,
                    'recipient_id': worker.id,
                    'emergency_food_units': units_per_worker,
                    'crew_food_units_total': int(supply_needed)})
        if event_id is not None:
            event_ids.append(event_id)
    return event_ids


def get_project(world: dict, kind: str, site: str | None = None) -> dict | None:
    return next((project for project in _state(world)['projects']
                 if project['kind'] == kind and (site is None or project['site'] == site)
                 and project['status'] != 'cancelled'), None)


def start_project(world: dict, kind: str, site: str) -> tuple[bool, str]:
    operation_id = _project_operation_id(world, 'start', kind, site)
    before = _project_trace_state(get_project(world, kind, site))

    def reject(reason, message, details=None):
        _trace_project_lifecycle(
            world, action='start', kind=kind, site=site,
            project_id=f'{kind}:{site}', success=False, reason=reason,
            before=before, after=before, details=details,
            operation_id=operation_id)
        return False, message

    definition = PROJECT_DEFS.get(kind)
    if definition is None or site not in definition['sites']:
        return reject('unavailable_kind_or_site',
                      'This strategic repair is unavailable at that site.',
                      {'requested_kind': kind, 'requested_site': site,
                       'available_kind': definition is not None})
    if get_project(world, kind, site):
        active = get_project(world, kind, site)
        return reject('already_active',
                      f'{definition["title"]} is already funded at {site}.',
                      {'active_project_id': active['id'],
                       'active_project_status': active['status']})
    occupier = _occupier(world, site)
    if occupier:
        return reject('site_occupied',
                      f'Egypt cannot begin this work while foreign troops hold {site}.',
                      {'occupying_nation': occupier})
    tile = _tile(world, site)
    workers = _workers(tile, definition['workers'])
    if len(workers) < definition['workers']:
        return reject('insufficient_local_workers',
                      f'{site} lacks enough available local workers.',
                      {'available_workers': len(workers),
                       'required_workers': definition['workers'],
                       'available_worker_ids': [agent.id for agent in workers]})
    egypt = _nation(world, 'Egypt')
    treasury_before = float(egypt.government.agent.cash)
    project = {
        'id': f'{kind}:{site}', 'kind': kind, 'front': definition['front'],
        'site': site, 'tile': tile.name, 'sponsor': 'Egypt',
        'status': 'building', 'started_turn': int(world['turn']),
        'last_advanced_turn': int(world['turn']), 'progress': 0,
        'required_work': definition['work_turns'], 'worker_ids': [agent.id for agent in workers],
        'paid_cash': 0.0, 'upkeep_paid': 0.0, 'last_upkeep_turn': None,
        'integrity': 1.0, 'events': [],
    }
    payment_event_ids = []
    if not _pay_workers(world, project, definition['cash_cost'],
                        'construction_wage', trace_event_ids=payment_event_ids):
        treasury_after = float(egypt.government.agent.cash)
        return reject('insufficient_treasury',
                      f'Egypt needs {definition["cash_cost"]:.0f} treasury units for {definition["title"].lower()}.',
                      {'required_construction_cash': float(definition['cash_cost']),
                       'treasury_cash_before': treasury_before,
                       'treasury_cash_after': treasury_after,
                       'available_worker_ids': list(project['worker_ids'])})
    project['paid_cash'] = definition['cash_cost']
    _state(world)['projects'].append(project)
    _state(world)['selected'] = project['id']
    message = (f'{definition["title"]} begins at {site}. Cairo paid '
               f'{definition["cash_cost"]:.0f} to {len(workers)} local workers; '
               f'completion needs {definition["work_turns"]} staffed turns.')
    _event(world, project, message)
    _trace_project_lifecycle(
        world, action='start', kind=kind, site=site, project_id=project['id'],
        success=True, reason='construction_funded', before=before,
        after=_project_trace_state(project), operation_id=operation_id,
        cause_event_ids=payment_event_ids or None,
        details={'construction_cost': float(definition['cash_cost']),
                 'required_work_turns': int(definition['work_turns']),
                 'required_workers': int(definition['workers']),
                 'selected_worker_ids': list(project['worker_ids']),
                 'treasury_cash_before': treasury_before,
                 'treasury_cash_after': float(egypt.government.agent.cash),
                 'construction_payment_event_ids': payment_event_ids})
    return True, message


def advance(world: dict) -> None:
    turn = int(world['turn'])
    for project in _state(world)['projects']:
        if project['status'] == 'cancelled' or project['last_advanced_turn'] >= turn:
            continue
        operation_id = _project_operation_id(
            world, 'advance', project['kind'], project['site'])
        before = _project_trace_state(project)
        definition = PROJECT_DEFS[project['kind']]
        payment_event_ids = []
        food_event_ids = []
        review_event_id = None
        project['last_advanced_turn'] = turn
        occupier = _occupier(world, project['site'])
        if occupier:
            if project['status'] != 'occupied':
                project['status'] = 'occupied'
                _event(world, project, f'{project["site"]} is occupied; Egyptian project work and benefits stop.')
            _trace_project_lifecycle(
                world, action='advance', kind=project['kind'], site=project['site'],
                project_id=project['id'], success=False, reason='site_occupied',
                before=before, after=_project_trace_state(project),
                operation_id=operation_id,
                details={'occupying_nation': occupier, 'work_progressed': False})
            continue
        if project['integrity'] < 0.5:
            project['status'] = 'damaged'
            _trace_project_lifecycle(
                world, action='advance', kind=project['kind'], site=project['site'],
                project_id=project['id'], success=False,
                reason='integrity_below_operating_threshold', before=before,
                after=_project_trace_state(project), operation_id=operation_id,
                details={'integrity': float(project['integrity']),
                         'minimum_operating_integrity': 0.5,
                         'work_progressed': False})
            continue
        tile = _tile(world, project['site'])
        living_ids = {agent.id for agent in _workers(tile, len(tile.agents))}
        available_worker_ids = sorted(living_ids.intersection(project['worker_ids']))
        if len(available_worker_ids) < definition['workers']:
            project['status'] = 'stalled'
            _trace_project_lifecycle(
                world, action='advance', kind=project['kind'], site=project['site'],
                project_id=project['id'], success=False,
                reason='original_crew_unavailable', before=before,
                after=_project_trace_state(project), operation_id=operation_id,
                details={'required_workers': int(definition['workers']),
                         'available_worker_ids': available_worker_ids,
                         'missing_worker_ids': sorted(set(project['worker_ids'])
                                                      - set(available_worker_ids)),
                         'work_progressed': False})
            continue
        progress_before = int(project['progress'])
        if project['progress'] < project['required_work']:
            project['status'] = 'building'
            project['progress'] += 1
            if project['progress'] == project['required_work']:
                _event(world, project, f'{definition["title"]} is complete at {project["site"]}.')
                if project['kind'] == 'revenue_office':
                    project['review_due_turn'] = turn + 1
            else:
                _trace_project_lifecycle(
                    world, action='advance', kind=project['kind'],
                    site=project['site'], project_id=project['id'], success=True,
                    reason='staffed_work_progress', before=before,
                    after=_project_trace_state(project), operation_id=operation_id,
                    details={'progress_before': progress_before,
                             'progress_after': int(project['progress']),
                             'required_work': int(project['required_work']),
                             'available_worker_ids': available_worker_ids,
                             'work_progressed': True})
                continue
        supply_needed = int(definition.get('supply_food', 0))
        egypt = _nation(world, 'Egypt')
        if supply_needed and int(egypt.government.food_inventory) < supply_needed:
            project['status'] = 'unsupplied'
            if project.get('supply_warning_turn') != turn - 1:
                _event(world, project, f'{project["site"]} defense staff lack public food supplies.')
            project['supply_warning_turn'] = turn
            _trace_project_lifecycle(
                world, action='advance', kind=project['kind'], site=project['site'],
                project_id=project['id'], success=False,
                reason='insufficient_public_food', before=before,
                after=_project_trace_state(project), operation_id=operation_id,
                details={'food_required': supply_needed,
                         'public_food_inventory': int(egypt.government.food_inventory),
                         'progress_before': progress_before,
                         'progress_after': int(project['progress']),
                         'work_progressed': project['progress'] > progress_before})
            continue
        treasury_before_upkeep = float(egypt.government.agent.cash)
        if _pay_workers(world, project, definition['upkeep'], 'staff_wage',
                        trace_event_ids=payment_event_ids):
            project['status'] = 'operating'
            project['last_upkeep_turn'] = turn
            project['upkeep_paid'] = round(project['upkeep_paid'] + definition['upkeep'], 6)
            if supply_needed:
                from nutrition import queue_emergency_meal
                crew = {agent.id: agent for agent in _workers(_tile(world, project['site']),
                                                                len(_tile(world, project['site']).agents))}
                crew_workers = [crew[worker_id] for worker_id in project['worker_ids']]
                worker_food_before = {
                    worker.id: int(getattr(worker, 'emergency_food_units', 0))
                    for worker in crew_workers}
                food_inventory_before = int(egypt.government.food_inventory)
                for worker_id in project['worker_ids']:
                    queue_emergency_meal(crew[worker_id], supply_needed // len(project['worker_ids']))
                egypt.government.food_inventory -= supply_needed
                world['scenario_state']['public_maize_stock_units'] = egypt.government.food_inventory
                food_event_ids = _trace_project_crew_food(
                    world, project, egypt, crew_workers, supply_needed,
                    food_inventory_before, worker_food_before)
                _state(world)['payments'].append({
                    'turn': turn, 'kind': 'crew_food', 'project': project['id'],
                    'payer': 'Egyptian public stores', 'recipient_ids': list(project['worker_ids']),
                    'food_units': supply_needed,
                })
        else:
            project['status'] = 'unfunded'
            if project['last_upkeep_turn'] != turn - 1:
                _event(world, project, f'{definition["title"]} cannot operate without paid staff.')
            review_event_id = None
        if (project['kind'] == 'revenue_office' and project.get('review_due_turn') is not None
                and project['review_due_turn'] <= turn and project['status'] == 'operating'):
            review_event_id = _review_revenue_office(world, project)
        cause_event_ids = [*payment_event_ids, *food_event_ids]
        if review_event_id is not None:
            cause_event_ids.append(review_event_id)
        paid_upkeep = project['last_upkeep_turn'] == turn
        _trace_project_lifecycle(
            world, action='advance', kind=project['kind'], site=project['site'],
            project_id=project['id'], success=paid_upkeep,
            reason='operating_upkeep_paid' if paid_upkeep else 'upkeep_unaffordable',
            before=before, after=_project_trace_state(project),
            operation_id=operation_id, cause_event_ids=cause_event_ids or None,
            details={'required_staff_wage': float(definition['upkeep']),
                     'staff_wage_paid': paid_upkeep,
                     'treasury_cash_before_upkeep': treasury_before_upkeep,
                     'treasury_cash_after_upkeep': float(egypt.government.agent.cash),
                     'progress_before': progress_before,
                     'progress_after': int(project['progress']),
                     'required_work': int(project['required_work']),
                     'available_worker_ids': available_worker_ids,
                     'construction_completed_this_turn':
                     progress_before < project['required_work']
                     and project['progress'] >= project['required_work'],
                     'crew_food_event_ids': food_event_ids,
                     'wage_event_ids': payment_event_ids,
                     'revenue_office_review_event_id': review_event_id})


def set_grain_entitlement(world: dict, active: bool) -> tuple[bool, str]:
    """A continuing food-access decision, paid for by owners and the treasury."""
    state = _state(world)
    previous = bool(state['grain_entitlement_active'])
    egypt = _nation(world, 'Egypt')
    turn = int(world['turn'])
    trace_region = (egypt.tiles[0] if egypt is not None and egypt.tiles else
                    next(iter(world.get('tiles', ())), None))
    if state['grain_entitlement_active'] == active:
        if trace_region is not None:
            from run_trace import emit
            emit(
                trace_region, kind='grain_entitlement_policy_unchanged',
                record_class='decision', phase='scenario_action',
                subject={'type': 'nation',
                         'id': getattr(egypt, 'name', 'Egypt')},
                metric_id='scenario.grain_entitlement_policy', unit='active',
                before=int(previous), after=int(previous),
                formula_id='scenario_projects.grain_entitlement_policy.v1',
                inputs={'operation_id': (
                            f'grain-entitlement-policy:{turn}:{int(previous)}:{int(bool(active))}'),
                        'turn': turn, 'requested_state': bool(active),
                        'success': False, 'reason': 'policy_already_in_requested_state'})
        return False, ('The grain entitlement is already active.' if active else
                       'The grain entitlement has already ended.')
    state['grain_entitlement_active'] = active
    if trace_region is not None:
        from run_trace import emit
        emit(
            trace_region, kind='grain_entitlement_policy_changed',
            record_class='outcome', phase='scenario_action',
            subject={'type': 'nation', 'id': getattr(egypt, 'name', 'Egypt')},
            metric_id='scenario.grain_entitlement_policy', unit='active',
            before=int(previous), after=int(bool(active)),
            formula_id='scenario_projects.grain_entitlement_policy.v1',
            inputs={'operation_id': f'grain-entitlement-policy:{turn}:{int(previous)}:{int(bool(active))}',
                    'turn': turn, 'requested_state': bool(active),
                    'success': True,
                    'reason': 'policy_activated' if active else 'policy_deactivated',
                    'protected_private_stock_rule': '4 if owner is lord else 8',
                    'carrier_fee_per_food_unit': .05})
    return True, ('Cairo orders a recurring in-kind levy on private maize above protected reserves. '
                  'Carriers are paid from the treasury; holders resist each turn.' if active else
                  'Cairo ends the recurring grain levy and public entitlement.')


def reserve_recall_capacity(world: dict) -> float:
    """Cash local Egyptian governments can send while retaining 20 each."""
    egypt = _nation(world, 'Egypt')
    if egypt is None or _state(world)['reserve_recall_used']:
        return 0.0
    governments = {id(tile.gov): tile.gov for tile in egypt.tiles
                   if tile.gov is not egypt.government}
    return round(min(80.0, sum(max(0.0, float(gov.agent.cash) - 20.0)
                               for gov in governments.values())), 2)


def recall_district_reserves(world: dict) -> tuple[bool, str]:
    """Move already collected district cash to Cairo, once, with local costs."""
    state = _state(world)
    egypt = _nation(world, 'Egypt')
    turn = int(world['turn'])
    trace_region = (getattr(egypt, 'tiles', [None])[0]
                    if egypt is not None and getattr(egypt, 'tiles', None)
                    else next(iter(world.get('tiles', ())), None))
    if state['reserve_recall_used']:
        _trace_district_action(
            trace_region, egypt, action_id='recall_district_reserves', turn=turn,
            success=False, reason='recall_already_used',
            inputs={'reserve_recall_used_before': True,
                    'capacity_available': 0.0})
        return False, 'Cairo has already recalled the district reserves.'
    capacity = reserve_recall_capacity(world)
    if capacity < 1.0:
        _trace_district_action(
            trace_region, egypt, action_id='recall_district_reserves', turn=turn,
            success=False, reason='no_cash_above_protected_reserves',
            inputs={'reserve_recall_used_before': False,
                    'capacity_available': float(capacity),
                    'protected_reserve_per_district': 20.0})
        return False, 'District governments have no cash above their protected operating reserves.'
    operation_id = f'recall_district_reserves:{getattr(egypt, "name", "Egypt")}:{turn}'
    sovereign_cash_before = float(egypt.government.agent.cash)
    legitimacy_before = float(egypt.legitimacy)
    by_government = {}
    for tile in egypt.tiles:
        if tile.gov is not egypt.government:
            by_government.setdefault(id(tile.gov), (tile.gov, []))[1].append(tile)
    remaining = capacity
    receipts = []
    transfer_event_ids = []
    district_effects = []
    for gov, tiles in sorted(by_government.values(),
                             key=lambda row: (-float(row[0].agent.cash), row[0].name)):
        amount = round(min(remaining, max(0.0, float(gov.agent.cash) - 20.0)), 6)
        if amount <= 0:
            continue
        payer_before = float(gov.agent.cash)
        payee_before = float(egypt.government.agent.cash)
        gov.agent.cash -= amount
        egypt.government.agent.cash += amount
        transfer_operation_id = (f'reserve-recall:{turn}:{gov.name}:'
                                 f'{payer_before:.6f}:{amount:.6f}')
        operation_event_ids = _record_internal_cash_transfer(
            tiles[0], egypt, operation_id=transfer_operation_id,
            kind='district_reserve_recall', amount=amount,
            payer_name=gov.name, payer_balance_before=payer_before,
            payer_balance_after=float(gov.agent.cash), payee_name=egypt.name,
            payee_balance_before=payee_before,
            payee_balance_after=float(egypt.government.agent.cash),
            turn=turn)
        transfer_event_ids.extend(operation_event_ids)
        remaining -= amount
        for tile in tiles:
            unrest_before = float(getattr(tile, 'unrest_level', 0.0))
            tile.unrest_level = min(1.0, float(getattr(tile, 'unrest_level', 0.0)) + .02)
            district_effects.append({
                'district': tile.name, 'unrest_before': unrest_before,
                'unrest_after': float(tile.unrest_level),
                'unrest_increase': float(tile.unrest_level) - unrest_before,
                'unrest_increment_capped_at': 1.0,
                'transfer_operation_id': transfer_operation_id,
                'cause_event_ids': operation_event_ids})
        receipts.append({'operation_id': transfer_operation_id,
                         'districts': [getattr(tile, 'scenario_location', tile.name)
                                        for tile in tiles],
                         'amount': amount, 'collector': gov.name})
        if remaining < .01:
            break
    transferred = round(capacity - remaining, 6)
    state['reserve_recall_used'] = True
    state['reserve_recall_reports'].append({'turn': int(world['turn']),
                                           'total': transferred, 'districts': receipts})
    egypt.legitimacy = max(0.0, float(egypt.legitimacy) - .035)
    from run_trace import emit
    for effect in district_effects:
        tile = next((candidate for candidate in egypt.tiles
                     if candidate.name == effect['district']), None)
        if tile is None:
            continue
        unrest_event_id = emit(
            tile, kind='district_reserve_recall_unrest',
            record_class='outcome', phase='scenario_projects',
            subject={'type': 'tile', 'id': tile.name, 'nation': egypt.name},
            metric_id='politics.unrest_level', unit='ratio',
            before=effect['unrest_before'], after=effect['unrest_after'],
            formula_id='scenario_projects.reserve_recall_unrest.v1',
            inputs={'operation_id': operation_id,
                    'transfer_operation_id': effect['transfer_operation_id'],
                    'action_id': 'recall_district_reserves',
                    'turn': turn, 'unrest_increment': .02},
            cause_event_ids=effect['cause_event_ids'] or None)
        if unrest_event_id is not None:
            effect['unrest_event_id'] = unrest_event_id
    legitimacy_event_id = emit(
        trace_region, kind='district_reserve_recall_legitimacy',
        record_class='outcome', phase='scenario_projects',
        subject={'type': 'nation', 'id': egypt.name},
        metric_id='politics.legitimacy', unit='ratio',
        before=legitimacy_before, after=float(egypt.legitimacy),
        formula_id='scenario_projects.reserve_recall_legitimacy.v1',
        inputs={'operation_id': operation_id, 'action_id': 'recall_district_reserves',
                'turn': turn, 'requested_decrease': .035,
                'applied_decrease': legitimacy_before - float(egypt.legitimacy)},
        cause_event_ids=transfer_event_ids or None)
    _trace_district_action(
        trace_region, egypt, action_id='recall_district_reserves', turn=turn,
        success=True, reason='district_reserves_recalled',
        inputs={'capacity_available': float(capacity),
                'total_transferred': transferred,
                'protected_reserve_per_district': 20.0,
                'transfer_operation_ids': [receipt['operation_id']
                                           for receipt in receipts],
                'transfer_event_ids': transfer_event_ids,
                'district_receipts': receipts,
                'district_effects': district_effects,
                'sovereign_cash_before': sovereign_cash_before,
                'sovereign_cash_after': float(egypt.government.agent.cash),
                'legitimacy_before': legitimacy_before,
                'legitimacy_after': float(egypt.legitimacy),
                'legitimacy_event_id': legitimacy_event_id},
        cause_event_ids=transfer_event_ids or None)
    return True, (f'Called {transferred:.1f} already-collected treasury units from district governments '
                  'to Cairo. Local budgets retain 20 each; district unrest and political resentment rise.')


def advance_grain_entitlement(world: dict) -> None:
    """Deliver conserved grain after consumption, using actual private surplus."""
    state = _state(world)
    if not state['grain_entitlement_active']:
        return
    egypt = _nation(world, 'Egypt')
    if egypt is None:
        return
    turn = int(world['turn'])
    operation_id = f'grain-entitlement-turn:{egypt.name}:{turn}'
    treasury = egypt.government.agent
    treasury_cash_before = float(treasury.cash)
    legitimacy_before = float(egypt.legitimacy)
    deficit_households_before = sum(
        deficit_fraction(agent) > 0
        for tile in egypt.tiles for agent in _workers(tile, len(tile.agents)))
    unrest_before_by_tile = {
        tile.name: float(getattr(tile, 'unrest_level', 0.0))
        for tile in egypt.tiles}
    carriers = {tile.name: (_workers(tile, 1) or [None])[0] for tile in egypt.tiles}
    donors = sorted(((tile, agent) for tile in egypt.tiles for agent in tile.agents
                     if carriers[tile.name] is not None
                     and getattr(agent, 'alive', True)
                     and not getattr(agent, 'is_government', False)
                     and not getattr(agent, 'is_corporation', False)
                     and not getattr(agent, 'is_trader', False)
                     and agent.inv_get(Goods.food, 0) > (4 if getattr(agent, 'is_lord', False) else 8)),
                    key=lambda row: (-row[1].inv_get(Goods.food, 0), row[1].id))
    eligible_surplus_donor_count = len(donors)
    recipients = sorted((agent for tile in egypt.tiles for agent in _workers(tile, len(tile.agents))
                         if deficit_fraction(agent) > 0),
                        key=lambda agent: (-deficit_fraction(agent), float(agent.cash), agent.id))
    moved = helped = 0
    transport_paid = 0.0
    payment_sequence = 0
    food_transfer_event_ids = []
    transfer_operations = []
    economy = world['scenario_state']['political_economy']
    for person in recipients:
        need = ceil(float(person.calorie_deficit_kcal) / CALORIES_PER_FOOD)
        received = 0
        while need > 0 and donors and treasury.cash >= .05:
            tile, owner = donors[0]
            protected = 4 if getattr(owner, 'is_lord', False) else 8
            surplus = max(0, owner.inv_get(Goods.food, 0) - protected)
            if surplus <= 0:
                donors.pop(0)
                continue
            units = min(need, surplus, int(treasury.cash / .05))
            if units <= 0:
                break
            owner_food_before = int(owner.inv_get(Goods.food, 0))
            owner.inv_add(Goods.food, -units)
            if economy['warehouse_by_tile'].get(tile.name) == owner.id:
                reserved = min(int(economy['private_reserve_by_tile'].get(tile.name, 0)),
                               owner.inv_get(Goods.food, 0))
                economy['private_reserve_by_tile'][tile.name] = reserved
                tile.scenario_grain_reserved_units = reserved
            carrier = carriers[tile.name]
            fee = round(units * .05, 6)
            treasury_before = float(treasury.cash)
            carrier_before = float(carrier.cash)
            treasury.cash -= fee
            carrier.cash += fee
            transport_paid += fee
            payment_sequence += 1
            grain_transfer_id = (f'grain-entitlement:{turn}:{tile.name}:{owner.id}:'
                                 f'{person.id}:{payment_sequence}')
            transfer_operations.append(grain_transfer_id)
            carrier_event_id = _record_person_cash_payment(
                tile, egypt, operation_id=f'{grain_transfer_id}:carrier-wage',
                kind='grain_carrier_wage', amount=fee, person=carrier,
                turn=turn, treasury_before=treasury_before,
                treasury_after=float(treasury.cash),
                person_before=carrier_before, person_after=float(carrier.cash),
                references={'grain_transfer_id': grain_transfer_id,
                            'food_owner_id': owner.id,
                            'food_recipient_id': person.id,
                            'food_units': units})
            deficit_before = float(person.calorie_deficit_kcal)
            eaten_before = float(person.last_calories_eaten)
            feed_emergency_meal(person, units)
            from run_trace import emit
            food_event_id = emit(
                tile, kind='grain_entitlement_food_transfer',
                record_class='transfer', phase='scenario_projects',
                subject={'type': 'agent', 'id': person.id},
                metric_id='goods.food_entitlement_transfer', unit='food_units',
                after=units,
                inputs={'operation_id': grain_transfer_id,
                        'food_owner_id': owner.id,
                        'food_recipient_id': person.id,
                        'carrier_id': carrier.id,
                        'source_tile': tile.name,
                        'source_inventory_before': owner_food_before,
                        'source_inventory_after': int(owner.inv_get(Goods.food, 0)),
                        'recipient_deficit_before_kcal': deficit_before,
                        'recipient_deficit_after_kcal': float(person.calorie_deficit_kcal),
                        'recipient_calories_eaten_before': eaten_before,
                        'recipient_calories_eaten_after': float(person.last_calories_eaten),
                        'carrier_wage_operation_id': f'{grain_transfer_id}:carrier-wage'},
                cause_event_ids=[carrier_event_id] if carrier_event_id else None)
            if food_event_id is not None:
                food_transfer_event_ids.append(food_event_id)
            moved += units
            received += units
            need -= units
            economy['grain_transactions'].append({
                'turn': turn, 'tile': tile.name, 'kind': 'grain_entitlement',
                'operation_id': grain_transfer_id,
                'units': units, 'cash': 0.0, 'owner_id': owner.id,
                'recipient_id': person.id, 'carrier_id': carrier.id,
            })
        if received:
            helped += 1
        if not donors or treasury.cash < .05:
            break
    legitimacy_event_id = None
    unrest_event_ids = []
    if moved:
        egypt.legitimacy = max(0.0, float(egypt.legitimacy) - .012)
        from run_trace import emit
        legitimacy_event_id = emit(
            egypt.tiles[0], kind='grain_entitlement_legitimacy',
            record_class='outcome', phase='scenario_projects',
            subject={'type': 'nation', 'id': egypt.name},
            metric_id='politics.legitimacy', unit='ratio',
            before=legitimacy_before, after=float(egypt.legitimacy),
            formula_id='scenario_projects.grain_entitlement_legitimacy.v1',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'food_units_moved': int(moved),
                    'requested_decrease': .012,
                    'applied_decrease': legitimacy_before - float(egypt.legitimacy)},
            cause_event_ids=food_transfer_event_ids or None)
        for tile in egypt.tiles:
            unrest_before = unrest_before_by_tile[tile.name]
            tile.unrest_level = min(1.0, float(getattr(tile, 'unrest_level', 0.0)) + .004)
            unrest_event_id = emit(
                tile, kind='grain_entitlement_unrest',
                record_class='outcome', phase='scenario_projects',
                subject={'type': 'tile', 'id': tile.name, 'nation': egypt.name},
                metric_id='politics.unrest_level', unit='ratio',
                before=unrest_before, after=float(tile.unrest_level),
                formula_id='scenario_projects.grain_entitlement_unrest.v1',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'food_units_moved': int(moved),
                        'requested_increase': .004,
                        'applied_increase': float(tile.unrest_level) - unrest_before},
                cause_event_ids=food_transfer_event_ids or None)
            if unrest_event_id is not None:
                unrest_event_ids.append(unrest_event_id)
    underfed_after = sum(
        deficit_fraction(agent) > 0
        for tile in egypt.tiles for agent in _workers(tile, len(tile.agents)))
    report = {
        'turn': turn, 'units': moved, 'households_reached': helped,
        'transport_wages': round(transport_paid, 2),
        'remaining_underfed': underfed_after}
    state['grain_entitlement_reports'].append(report)
    trace_region = egypt.tiles[0] if egypt.tiles else None
    if trace_region is not None:
        from run_trace import emit
        if moved:
            reason = 'food_delivered'
        elif not deficit_households_before:
            reason = 'no_underfed_households'
        elif not donors:
            reason = 'no_surplus_donor_with_available_carrier'
        elif treasury_cash_before < .05:
            reason = 'treasury_below_minimum_carrier_fee'
        else:
            reason = 'no_food_units_delivered'
        emit(
            trace_region, kind='grain_entitlement_turn_resolved',
            record_class='outcome', phase='scenario_projects',
            subject={'type': 'nation', 'id': egypt.name},
            metric_id='scenario.grain_entitlement', unit='food_units',
            before=0, after=int(moved),
            formula_id='scenario_projects.grain_entitlement_delivery.v1',
            inputs={'operation_id': operation_id, 'turn': turn, 'active': True,
                    'reason': reason,
                    'eligible_surplus_donor_count': eligible_surplus_donor_count,
                    'available_carrier_tiles': [name for name, carrier in carriers.items()
                                                if carrier is not None],
                    'underfed_households_before': int(deficit_households_before),
                    'households_reached': int(helped),
                    'underfed_households_after': int(underfed_after),
                    'food_units_moved': int(moved),
                    'transport_wages_paid': float(transport_paid),
                    'treasury_cash_before': treasury_cash_before,
                    'treasury_cash_after': float(treasury.cash),
                    'transfer_operations': transfer_operations,
                    'food_transfer_event_ids': food_transfer_event_ids,
                    'legitimacy_event_id': legitimacy_event_id,
                    'unrest_event_ids': unrest_event_ids,
                    'report': report},
            cause_event_ids=food_transfer_event_ids or None)


def allocate_revenue(world: dict, government, source: str, net: float, turn: int) -> float:
    """Move a share of an actual local receipt to Cairo after lawful interceptions."""
    if not world.get('scenario_state', {}).get('strategic_projects'):
        return net
    egypt = _nation(world, 'Egypt')
    office = get_project(world, 'revenue_office', 'Alexandria')
    if (egypt is None or office is None or source not in ('tax', 'tariff')
            or government is egypt.government or net <= 0
            or not any(tile.gov is government for tile in egypt.tiles)
            or effectiveness(world, 'revenue_office', 'Alexandria') <= 0):
        return net
    amount = round(min(float(net) * PROJECT_DEFS['revenue_office']['national_share'],
                       float(government.agent.cash)), 6)
    if amount <= 0:
        return net
    payer_before = float(government.agent.cash)
    payee_before = float(egypt.government.agent.cash)
    government.agent.cash -= amount
    egypt.government.agent.cash += amount
    districts = [tile.name for tile in egypt.tiles if tile.gov is government]
    region = next(tile for tile in egypt.tiles if tile.gov is government)
    operation_id = (f'central-remittance:{int(turn)}:{source}:{government.name}:'
                    f'{payer_before:.6f}:{amount:.6f}')
    _record_internal_cash_transfer(
        region, egypt, operation_id=operation_id,
        kind='central_revenue_remittance', amount=amount,
        payer_name=government.name, payer_type='district_government',
        payer_balance_before=payer_before,
        payer_balance_after=float(government.agent.cash), payee_name=egypt.name,
        payee_balance_before=payee_before,
        payee_balance_after=float(egypt.government.agent.cash), turn=int(turn))
    central = egypt.government._income_pending
    central[source] = central.get(source, 0.0) + amount
    _state(world)['revenue_reports'].append({
        'operation_id': operation_id,
        'turn': int(turn), 'source': source,
        'payer': 'Egyptian taxpayers' if source == 'tax' else 'tariff-paying merchants',
        'districts': districts,
        'collector': government.name, 'recipient': 'Egyptian treasury',
        'receipt_after_interception': round(float(net), 6),
        'central_transfer': amount, 'local_retained': round(float(net) - amount, 6),
    })
    return max(0.0, float(net) - amount)


def _review_revenue_office(world: dict, project: dict) -> None:
    from scenario_debt import outstanding

    state = world['scenario_state']
    review_turn = int(world['turn'])
    review_due_turn_before = project.get('review_due_turn')
    operation_id = _fiscal_challenge_operation_id(world)
    before = _fiscal_challenge_trace_state(world)
    claim = outstanding(world)
    assignment = state.get('collection_assignment') or {}
    if claim <= .01:
        review_status = 'claim_settled'
        confidence_before = float(state.get('creditor_confidence', .6))
        message = 'The Caisse records that its claim is settled; Egyptian revenue offices remain under Cairo.'
    elif assignment.get('status') == 'active':
        review_status = 'active_collection_assignment'
        confidence_before = float(state.get('creditor_confidence', .6))
        message = ('The Caisse accepts the new Egyptian accounts while its signed assignment '
                   'continues to intercept its legal share of actual receipts.')
        state['creditor_confidence'] = min(1.0, state.get('creditor_confidence', .6) + .03)
    else:
        review_status = 'inspection_challenge_created'
        confidence_before = float(state.get('creditor_confidence', .6))
        message = ('The Caisse demands Alexandria revenue accounts before the next instalment. '
                   'Cairo may publish them or refuse inspection; neither answer pays the claim.')
        _state(world)['fiscal_challenge'] = {
            'status': 'pending', 'due_turn': review_turn,
            'source_project_id': project['id'],
            'source_review_turn': review_turn,
            'claim_at_review': float(claim),
            'assignment_status_at_review': assignment.get('status'),
        }
    state.setdefault('creditor_news', []).append({
        'turn': review_turn, 'headline': 'Caisse reviews Alexandria office', 'body': message,
    })
    _event(world, project, message)
    project['review_due_turn'] = None
    after = _fiscal_challenge_trace_state(world)
    revenue_reports = [dict(row) for row in _state(world).get('revenue_reports', [])
                       if int(row.get('turn', -1)) <= review_turn
                       and int(row.get('turn', -1)) >= review_turn - 1]
    return _trace_revenue_office_review(
        world, operation_id=operation_id, project=project,
        status=review_status, before=before, after=after,
        details={'claim_at_review': float(claim),
                 'claim_settled_gate': claim <= .01,
                 'collection_assignment_status': assignment.get('status'),
                 'collection_assignment_origin': assignment.get('origin'),
                 'confidence_before': confidence_before,
                 'confidence_after': float(state.get('creditor_confidence', .6)),
                 'creditor_confidence_delta': float(state.get('creditor_confidence', .6))
                 - confidence_before,
                 'challenge_created': review_status == 'inspection_challenge_created',
                 'challenge_due_turn': (review_turn if review_status ==
                                        'inspection_challenge_created' else None),
                 'review_due_turn_before': review_due_turn_before,
                 'revenue_report_operation_ids': [row.get('operation_id')
                                                  for row in revenue_reports],
                 'revenue_reports': revenue_reports,
                 'review_message': message})


def _trace_revenue_office_review(world, *, operation_id, project, status,
                                 before, after, details=None):
    region = _fiscal_challenge_trace_region(world)
    if region is None:
        return None
    from run_trace import emit
    return emit(
        region, kind='revenue_office_review_resolved',
        record_class='outcome', phase='scenario_projects',
        subject={'type': 'nation/project', 'id': project['id'],
                 'nation': 'Egypt', 'site': project.get('site')},
        metric_id='scenario.revenue_office_review', unit='review_status',
        before=before.get('challenge_status'),
        after=after.get('challenge_status'),
        formula_id='scenario_projects.revenue_office_review.v1',
        inputs={'operation_id': operation_id,
                'turn': int(world.get('turn', 0)), 'project_id': project['id'],
                'project_site': project.get('site'),
                'review_due_turn_before': (details or {}).get(
                    'review_due_turn_before'),
                'review_status': status,
                'state_before': before, 'state_after': after,
                **(details or {})})


def _fiscal_challenge_trace_region(world):
    egypt = _nation(world, 'Egypt')
    candidates = list(getattr(egypt, 'tiles', ())) if egypt is not None else []
    candidates.extend(world.get('tiles', ()))
    return next((tile for tile in candidates
                 if (getattr(tile, '_run_trace', None) is not None
                     and getattr(tile, '_collective_trace_clock', None) is not None)), None)


def _fiscal_challenge_operation_id(world):
    region = _fiscal_challenge_trace_region(world)
    clock = getattr(region, '_collective_trace_clock', None) if region else None
    ordinal = int(clock.get('next', 1)) if clock is not None else int(world.get('turn', 0))
    return f'fiscal-challenge:{int(world.get("turn", 0))}:{ordinal}'


def _fiscal_challenge_trace_state(world):
    state = world.get('scenario_state', {})
    projects = state.get('strategic_projects', {})
    challenge = projects.get('fiscal_challenge') or {}
    egypt = _nation(world, 'Egypt')
    from scenario_debt import bonds, outstanding
    return {
        'turn': int(world.get('turn', 0)),
        'challenge_status': challenge.get('status'),
        'challenge_due_turn': challenge.get('due_turn'),
        'challenge_source_project_id': challenge.get('source_project_id'),
        'challenge_source_review_turn': challenge.get('source_review_turn'),
        'challenge_claim_at_review': challenge.get('claim_at_review'),
        'challenge_assignment_status_at_review': challenge.get(
            'assignment_status_at_review'),
        'creditor_confidence': float(state.get('creditor_confidence', 0.0)),
        'egypt_treasury_cash': (float(egypt.government.agent.cash)
                                if egypt is not None else None),
        'payment_status': state.get('payment_status'),
        'debt_outstanding': float(outstanding(world)),
        'defaulted_bond_ids': sorted(bond.bond_id for bond in bonds(world)
                                     if bond.status == 'defaulted'),
        'naval_crisis_stage': state.get('naval_crisis', {}).get('stage'),
        'chapter': int(state.get('chapter', 1)),
        'chapter_two_start_turn': state.get('chapter_two_start_turn'),
        'chapter_two_cause': state.get('chapter_two_cause'),
        'creditor_news_count': len(state.get('creditor_news', [])),
    }


def _trace_fiscal_challenge(world, *, operation_id, kind, publish, success,
                            reason, before, after, details=None,
                            cause_event_ids=None, metric_id='scenario.fiscal_challenge_response'):
    region = _fiscal_challenge_trace_region(world)
    if region is None:
        return None
    from run_trace import emit
    return emit(
        region, kind=kind,
        record_class='outcome' if success or before != after else 'decision',
        phase='scenario_projects',
        subject={'type': 'nation/action', 'id': f'Egypt:fiscal_challenge:{publish}',
                 'nation': 'Egypt',
                 'action_id': 'publish_revenue_accounts' if publish
                 else 'refuse_revenue_inspection'},
        metric_id=metric_id,
        unit='triggered' if metric_id == 'scenario.fiscal_challenge_escalation_decision'
        else 'success',
        before=0, after=int(bool(success)),
        formula_id='scenario_projects.fiscal_challenge_response.v1',
        inputs={'operation_id': operation_id, 'turn': int(world.get('turn', 0)),
                'publish': bool(publish), 'success': bool(success),
                'reason': reason, 'state_before': before, 'state_after': after,
                **(details or {})},
        cause_event_ids=cause_event_ids)


def _fiscal_challenge_review_event_id(world, challenge):
    source_project_id = challenge.get('source_project_id')
    review_turn = challenge.get('source_review_turn')
    if source_project_id is None or review_turn is None:
        return None
    region = _fiscal_challenge_trace_region(world)
    recorder = getattr(region, '_run_trace', None) if region is not None else None
    rows = getattr(recorder, 'recent', None)
    if rows is None:
        rows = getattr(recorder, 'rows', None)
    if rows is None:
        return None
    for row in reversed(list(rows)):
        inputs = ((row.get('inputs') or {})
                  if isinstance(row, dict) else {})
        if (row.get('metric_id') == 'scenario.revenue_office_review'
                and inputs.get('project_id') == source_project_id
                and int(inputs.get('turn', -1)) == int(review_turn)
                and inputs.get('challenge_created')):
            return row.get('event_id')
    return None


def answer_fiscal_challenge(world: dict, publish: bool) -> tuple[bool, str]:
    operation_id = _fiscal_challenge_operation_id(world)
    before = _fiscal_challenge_trace_state(world)
    challenge = _state(world).get('fiscal_challenge') or {}
    review_event_id = _fiscal_challenge_review_event_id(world, challenge)
    if challenge.get('status') != 'pending':
        _trace_fiscal_challenge(
            world, operation_id=operation_id,
            kind='fiscal_challenge_response_rejected', publish=publish,
            success=False, reason='no_pending_fiscal_challenge',
            before=before, after=before,
            details={'challenge_status': challenge.get('status')})
        return False, 'The Caisse has no outstanding demand for these accounts.'
    confidence_before = float(world['scenario_state'].get('creditor_confidence', 0.0))
    challenge['status'] = 'published' if publish else 'refused'
    state = world['scenario_state']
    defaulted_bond_ids = []
    escalation_decision_event_id = None
    escalation_event_id = None
    if publish:
        state['creditor_confidence'] = min(1.0, state.get('creditor_confidence', .6) + .06)
        message = ('Cairo publishes the actual Alexandria receipts. The Caisse can verify '
                   'its claim, but the Egyptian treasury retains control of unassigned cash.')
        reason = 'accounts_published'
    else:
        state['creditor_confidence'] = max(0.0, state.get('creditor_confidence', .6) - .12)
        message = ('Cairo refuses Caisse inspection. The office keeps collecting, while '
                   'creditors distrust the figures and may escalate an unpaid claim.')
        from scenario_debt import bonds
        defaulted_bond_ids = sorted(bond.bond_id for bond in bonds(world)
                                    if bond.status == 'defaulted')
        if defaulted_bond_ids:
            decision_event_id = _trace_fiscal_challenge(
                world, operation_id=operation_id,
                kind='fiscal_challenge_escalation_decision', publish=False,
                success=True, reason='inspection_refused_with_defaulted_obligation',
                before=before, after=_fiscal_challenge_trace_state(world),
                details={'defaulted_bond_ids': defaulted_bond_ids,
                         'confidence_before': confidence_before,
                         'confidence_after': float(state['creditor_confidence']),
                         'crisis_stage_before': before['naval_crisis_stage'],
                         'escalation_gate_open': before['naval_crisis_stage']
                         in ('none', 'withdrawn')},
                cause_event_ids=([review_event_id]
                                 if review_event_id is not None else None),
                metric_id='scenario.fiscal_challenge_escalation_decision')
            escalation_decision_event_id = decision_event_id
            from scenario_gunboat import begin_escalation
            escalation_event_id = begin_escalation(
                world, 'refuse_revenue_inspection',
                cause_event_ids=([decision_event_id]
                                 if decision_event_id is not None else None))
            reason = 'inspection_refused_with_defaulted_obligation'
        else:
            reason = 'inspection_refused_without_defaulted_obligation'
    state.setdefault('creditor_news', []).append({
        'turn': int(world['turn']), 'headline': 'Alexandria accounts', 'body': message,
    })
    cause_ids = [event_id for event_id in
                 (review_event_id, escalation_decision_event_id,
                  escalation_event_id)
                 if event_id is not None]
    _trace_fiscal_challenge(
        world, operation_id=operation_id,
        kind='fiscal_challenge_response_resolved', publish=publish,
        success=True, reason=reason, before=before,
        after=_fiscal_challenge_trace_state(world),
        details={'confidence_before': confidence_before,
                 'confidence_after': float(state['creditor_confidence']),
                 'defaulted_bond_ids': defaulted_bond_ids,
                 'escalation_attempted': bool(defaulted_bond_ids),
                 'escalation_gate_open': before['naval_crisis_stage']
                 in ('none', 'withdrawn') if defaulted_bond_ids else False,
                 'escalation_event_id': escalation_event_id,
                 'revenue_office_review_event_id': review_event_id,
                 'message': message},
        cause_event_ids=cause_ids or None)
    return True, message


def effectiveness(world: dict, kind: str, site: str) -> float:
    project = get_project(world, kind, site)
    if (project is None or project['status'] != 'operating' or _occupier(world, site)
            or project['last_upkeep_turn'] is None
            or project['last_upkeep_turn'] < int(world['turn']) - 1):
        return 0.0
    return max(0.0, min(1.0, float(project['integrity'])))


def damage_project(world: dict, kind: str, site: str, damage: float,
                   cause_event_ids=None) -> bool:
    operation_id = _project_operation_id(world, 'damage', kind, site)
    project = get_project(world, kind, site)
    before = _project_trace_state(project)
    if project is None or damage <= 0:
        _trace_project_lifecycle(
            world, action='damage', kind=kind, site=site,
            project_id=f'{kind}:{site}', success=False,
            reason='no_active_project' if project is None else 'nonpositive_damage',
            before=before, after=before, operation_id=operation_id,
            cause_event_ids=cause_event_ids,
            details={'requested_damage': float(damage)})
        return False
    integrity_before = float(project['integrity'])
    project['integrity'] = max(0.0, integrity_before - float(damage))
    if project['integrity'] < 0.5:
        project['status'] = 'damaged'
    _event(world, project, f'{PROJECT_DEFS[kind]["title"]} at {site} is damaged to {project["integrity"]:.0%}.')
    _trace_project_lifecycle(
        world, action='damage', kind=kind, site=site, project_id=project['id'],
        success=True, reason='project_integrity_damaged', before=before,
        after=_project_trace_state(project), operation_id=operation_id,
        cause_event_ids=cause_event_ids,
        details={'requested_damage': float(damage),
                 'integrity_before': integrity_before,
                 'integrity_after': float(project['integrity']),
                 'operating_integrity_threshold': 0.5})
    return True


def repair_project(world: dict, kind: str, site: str) -> tuple[bool, str]:
    operation_id = _project_operation_id(world, 'repair', kind, site)
    project = get_project(world, kind, site)
    before = _project_trace_state(project)
    if project is None or project['integrity'] >= 1.0:
        _trace_project_lifecycle(
            world, action='repair', kind=kind, site=site,
            project_id=f'{kind}:{site}', success=False, reason='no_damaged_project',
            before=before, after=before, operation_id=operation_id)
        return False, 'No damaged strategic work needs repair here.'
    occupier = _occupier(world, site)
    if occupier:
        _trace_project_lifecycle(
            world, action='repair', kind=kind, site=site,
            project_id=project['id'], success=False, reason='site_occupied',
            before=before, after=before, operation_id=operation_id,
            details={'occupying_nation': occupier})
        return False, 'Egypt cannot repair occupied works.'
    cost = round(PROJECT_DEFS[kind]['cash_cost'] * (1.0 - project['integrity']) * 0.5, 2)
    egypt = _nation(world, 'Egypt')
    treasury_before = float(egypt.government.agent.cash)
    tile = _tile(world, site)
    available_worker_ids = {agent.id for agent in _workers(tile, len(tile.agents))}
    missing_worker_ids = sorted(set(project['worker_ids']) - available_worker_ids)
    payment_event_ids = []
    if not _pay_workers(world, project, cost, 'repair_wage',
                        trace_event_ids=payment_event_ids):
        reason = ('original_crew_unavailable'
                  if missing_worker_ids else 'insufficient_treasury')
        _trace_project_lifecycle(
            world, action='repair', kind=kind, site=site,
            project_id=project['id'], success=False, reason=reason,
            before=before, after=_project_trace_state(project),
            operation_id=operation_id,
            details={'repair_cost': float(cost),
                     'treasury_cash_before': treasury_before,
                     'treasury_cash_after': float(egypt.government.agent.cash),
                     'missing_worker_ids': missing_worker_ids,
                     'required_worker_ids': list(project['worker_ids'])})
        return False, f'Repair needs {cost:.0f} treasury units and the original local crew.'
    project['paid_cash'] = round(project['paid_cash'] + cost, 6)
    project['integrity'] = 1.0
    project['status'] = 'building' if project['progress'] < project['required_work'] else 'unfunded'
    message = f'Egypt paid {cost:.0f} to repair {PROJECT_DEFS[kind]["title"].lower()} at {site}.'
    _event(world, project, message)
    _trace_project_lifecycle(
        world, action='repair', kind=kind, site=site, project_id=project['id'],
        success=True, reason='repair_wages_paid', before=before,
        after=_project_trace_state(project), operation_id=operation_id,
        cause_event_ids=payment_event_ids or None,
        details={'repair_cost': float(cost),
                 'treasury_cash_before': treasury_before,
                 'treasury_cash_after': float(egypt.government.agent.cash),
                 'repair_payment_event_ids': payment_event_ids})
    return True, message


def cancel_project(world: dict, kind: str, site: str) -> tuple[bool, str]:
    operation_id = _project_operation_id(world, 'cancel', kind, site)
    project = get_project(world, kind, site)
    before = _project_trace_state(project)
    if project is None:
        _trace_project_lifecycle(
            world, action='cancel', kind=kind, site=site,
            project_id=f'{kind}:{site}', success=False,
            reason='no_active_project', before=before, after=before,
            operation_id=operation_id)
        return False, 'No active project exists here.'
    project['status'] = 'cancelled'
    message = f'Egypt abandoned {PROJECT_DEFS[kind]["title"].lower()} at {site}; paid wages remain with the workers.'
    _event(world, project, message)
    _trace_project_lifecycle(
        world, action='cancel', kind=kind, site=site, project_id=project['id'],
        success=True, reason='project_abandoned', before=before,
        after=_project_trace_state(project), operation_id=operation_id,
        details={'sunk_construction_cash': float(project.get('paid_cash', 0.0)),
                 'completed_work': int(project.get('progress', 0)),
                 'wages_reclaimed': False})
    return True, message


def current_plan(world: dict) -> dict[str, Any] | None:
    projects = _state(world)['projects']
    selected = _state(world).get('selected')
    return next((project for project in reversed(projects)
                 if project['id'] == selected and project['status'] != 'cancelled'), None) or next(
                     (project for project in reversed(projects) if project['status'] != 'cancelled'), None)


def strategic_strip(world: dict) -> list[dict[str, Any]]:
    """Three short Guided prompts backed by the same project and crisis state."""
    from scenario_debt import outstanding

    turn = int(world['turn'])
    state = world['scenario_state']
    projects = _state(world)
    plan = current_plan(world)
    if plan:
        definition = PROJECT_DEFS[plan['kind']]
        milestone = (f'{plan["required_work"] - plan["progress"]} staffed turns left'
                     if plan['progress'] < plan['required_work'] else
                     f'{definition["upkeep"]:.0f} wages/turn'
                     + (f' + {definition["supply_food"]} maize' if definition.get('supply_food') else ''))
        plan_text = f'{definition["front"].title()} • {plan["site"]}: {plan["status"]}'
        plan_details = [f'{definition["title"]} at {plan["site"]}: {plan["status"]}.',
                        f'Progress {plan["progress"]}/{plan["required_work"]}; {milestone}.',
                        f'Egypt has paid {plan["paid_cash"]:.0f} to local workers and '
                        f'{plan["upkeep_paid"]:.0f} in operating wages.',
                        'The map marker shows the site and whether the project still operates.']
    else:
        plan_text = 'No strategic project funded'
        plan_details = ['A food repair, revenue office, or defense line can anchor a plan.',
                        'Each costs a major decision, local wages, and future upkeep.']
    if projects['grain_entitlement_active']:
        plan_details.append('The standing grain entitlement moves private surplus to underfed households; Cairo pays carriers.')
    challenge = projects.get('fiscal_challenge') or {}
    naval = state.get('naval_crisis', {})
    due = int(state.get('payment_window_turn', 6))
    claim = outstanding(world)
    if challenge.get('status') == 'pending':
        threat_text = 'Caisse wants Alexandria accounts'
        threat_details = ['Publish or refuse the demand with a major decision.',
                          f'The bond claim remains {claim:.0f}; this answer does not pay it.']
    elif naval.get('stage') in ('mobilizing', 'ultimatum', 'blockaded', 'campaign'):
        threat_text = f'British naval crisis: {naval["stage"]}'
        threat_details = [f'Britain is {naval["stage"]}; check the map route and current foreign report.',
                          f'Outstanding Caisse claim: {claim:.0f}.']
    elif claim > .01:
        turns = max(0, due - turn)
        threat_text = (f'Caisse: {state.get("scheduled_remittance", 0):.0f} due '
                       + ('now' if turns == 0 else f'in {turns} turns'))
        threat_details = [f'Total claim: {claim:.0f}. Next instalment: '
                          f'{state.get("scheduled_remittance", 0):.0f} on turn {due}.',
                          'The current treasury, tax receipts, and project upkeep determine what Egypt can pay.']
    else:
        threat_text = 'Debt claim cleared; watch food access'
        threat_details = ['The Caisse claim has been settled.',
                          'Household calorie deficits, private stocks and district unrest can still worsen.']
    events = [event for event in projects['events'] if event['turn'] >= turn - 1]
    if events:
        latest = events[-1]
        consequence_text = latest['message']
        consequence_details = [latest['message']]
    else:
        fiscal = [row for row in projects['revenue_reports'] if row['turn'] == turn - 1]
        food = [row for row in projects['food_reports'] if row['turn'] == turn - 1]
        entitlement = [row for row in projects['grain_entitlement_reports'] if row['turn'] == turn - 1]
        if fiscal:
            transferred = sum(row['central_transfer'] for row in fiscal)
            consequence_text = f'{transferred:.0f} local receipts moved to Cairo'
            consequence_details = [f'{transferred:.1f} of actual net local receipts reached Cairo last turn.',
                                   'Caisse and occupation interceptions were applied first; local budgets kept the rest.']
        elif entitlement and entitlement[-1]['units']:
            last = entitlement[-1]
            consequence_text = f'{last["units"]} private maize fed {last["households_reached"]} households'
            consequence_details = [f'Carriers earned {last["transport_wages"]:.1f} treasury units.',
                                   f'{last["remaining_underfed"]} households still had a calorie deficit.']
        elif food:
            last = food[-1]
            consequence_text = (f'{last["site"]}: {last["food_produced"]} food made, '
                                f'{last["private_reserved"]} held')
            consequence_details = [f'{last["underfed"]}/{last["households"]} local households underfed.',
                                   'Production and access are different: extra food can remain privately held.']
        else:
            consequence_text = 'No new project result this turn'
            consequence_details = ['Advance a turn to see work progress, real receipts and rival responses.']
    return [
        {'title': 'Current plan', 'text': plan_text, 'details': plan_details},
        {'title': 'Next threat', 'text': threat_text, 'details': threat_details},
        {'title': 'Recent consequence', 'text': consequence_text, 'details': consequence_details},
    ]


def record_food_results(world: dict) -> None:
    """Show harvest, ownership, and access after the production stage."""
    from goods import Goods
    from nutrition import deficit_fraction
    from scenario_political_economy import district_snapshot

    turn = int(world['turn'])
    reports = _state(world)['food_reports']
    for project in _state(world)['projects']:
        if project['kind'] != 'nile_repair' or project['status'] == 'cancelled':
            continue
        tile = _tile(world, project['site'])
        food_log = getattr(tile, 'production_log', {}).get(Goods.food, [])
        people = [agent for agent in tile.agents if getattr(agent, 'alive', True)
                  and not getattr(agent, 'is_government', False)
                  and not getattr(agent, 'is_corporation', False)
                  and not getattr(agent, 'is_trader', False)
                  and not getattr(agent, 'is_lord', False)]
        district = district_snapshot(world, tile)
        report = {
            'turn': turn, 'project': project['id'], 'site': project['site'],
            'status': project['status'],
            'yield_applied': getattr(tile, 'scenario_repair_applied_turn', None) == turn,
            'yield_factor': (float(getattr(tile, 'scenario_repair_yield_factor', 1.0))
                             if getattr(tile, 'scenario_repair_applied_turn', None) == turn else 1.0),
            'soil_fertility': round(float(getattr(tile, 'soil_fertility', 1.0)), 3),
            'food_produced': int(food_log[-1]) if food_log else 0,
            'private_reserved': district['private_stock'],
            'strikers': district['strikers'],
            'underfed': sum(deficit_fraction(agent) > 0 for agent in people),
            'households': len(people),
        }
        if not any(row['turn'] == turn and row['project'] == project['id'] for row in reports):
            reports.append(report)
        purchases = [row for row in world['scenario_state']['political_economy']['grain_transactions']
                     if row['turn'] == turn and row['tile'] == tile.name
                     and row['kind'] == 'private_purchase']
        for purchase in purchases:
            record_owner_response(world, project['site'], purchase['units'], purchase['owner_id'])


def record_owner_response(world: dict, site: str, units: int, owner_id: int) -> None:
    project = get_project(world, 'nile_repair', site)
    if project is None or effectiveness(world, 'nile_repair', site) <= 0 or units <= 0:
        return
    event = {'turn': int(world['turn']), 'project': project['id'],
             'message': (f'Warehouse owner {owner_id} bought {units} food units in {site}; '
                         'the larger harvest may remain out of reach for poorer households.')}
    if event in project['events']:
        return
    project['events'].append(event)
    _state(world)['events'].append(event)


def draw_map_overlay(surface, world: dict) -> None:
    """Draw project markers over the native map in either desktop UI mode."""
    if 'strategic_projects' not in world.get('scenario_state', {}):
        return
    import pygame
    from worldview_camera import HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H, world_to_screen

    colors = {
        'building': (232, 189, 90), 'operating': (99, 213, 148),
        'stalled': (226, 143, 82), 'unfunded': (226, 143, 82),
        'damaged': (225, 92, 91), 'occupied': (174, 106, 190),
    }
    old_clip = surface.get_clip()
    surface.set_clip(pygame.Rect(0, TOP_BAR_H, MAP_RIGHT, HEIGHT - TOP_BAR_H - TICKER_H))
    sites = world['scenario_state']['geography']['sites']
    for project in _state(world)['projects']:
        if project['status'] == 'cancelled':
            continue
        point = sites[project['site']].get('position')
        if point is None:
            continue
        px, py = world_to_screen(world, *point)
        color = colors.get(project['status'], (200, 200, 200))
        pygame.draw.circle(surface, (17, 23, 32), (px, py), 12)
        pygame.draw.circle(surface, color, (px, py), 10, 3)
        pygame.draw.circle(surface, color, (px, py), 3)
    surface.set_clip(old_clip)


def project_hover_tip(world: dict, mouse_pos) -> tuple | None:
    """Explain a map marker from shared state in Guided or Advanced mode."""
    if mouse_pos is None or 'strategic_projects' not in world.get('scenario_state', {}):
        return None
    import pygame
    from worldview_camera import world_to_screen

    sites = world['scenario_state']['geography']['sites']
    for project in reversed(_state(world)['projects']):
        if project['status'] == 'cancelled':
            continue
        point = sites[project['site']].get('position')
        if point is None:
            continue
        px, py = world_to_screen(world, *point)
        if (mouse_pos[0] - px) ** 2 + (mouse_pos[1] - py) ** 2 > 14 ** 2:
            continue
        definition = PROJECT_DEFS[project['kind']]
        lines = [f'{definition["title"]} is {project["status"]} at {project["site"]}.',
                 f'Work {project["progress"]}/{project["required_work"]}; '
                 f'{project["integrity"]:.0%} intact. Egypt paid {project["paid_cash"]:.0f} '
                 f'to local workers plus {project["upkeep_paid"]:.0f} in operating wages.']
        if project['kind'] == 'nile_repair':
            reports = [row for row in _state(world)['food_reports']
                       if row['project'] == project['id']]
            if reports:
                last = reports[-1]
                lines.append(f'Last harvest: {last["food_produced"]} food made, '
                             f'{last["private_reserved"]} privately held, '
                             f'{last["underfed"]}/{last["households"]} households underfed.')
            lines.append('More production only helps households when food reaches them.')
        elif project['kind'] == 'revenue_office':
            transferred = sum(row['central_transfer'] for row in _state(world)['revenue_reports'])
            lines.append(f'{transferred:.0f} actual local receipt units reached Cairo after prior claims.')
            lines.append('Local governments lose that share; the Caisse keeps its signed rights.')
        else:
            meals = sum(row.get('food_units', 0) for row in _state(world)['payments']
                        if row.get('project') == project['id'] and row.get('kind') == 'crew_food')
            lines.append(f'{meals} public maize units fed the crew; '
                         'supplied works add up to 55 Tel el Kebir trench strength.')
        return definition['front'].title() + ' project', lines, pygame.Rect(px - 12, py - 12, 24, 24), 'action'
    return None


def debrief_evidence(world: dict) -> dict:
    """Keep investment, ownership and social costs beside the ending evidence."""
    state = _state(world)
    projects = list(state['projects'])
    payments = list(state['payments'])
    wages = sum(float(row.get('amount', 0)) for row in payments)
    crew_food = sum(int(row.get('food_units', 0)) for row in payments
                    if row.get('kind') == 'crew_food')
    cairo_transfers = sum(float(row.get('central_transfer', 0)) for row in
                          state['revenue_reports'])
    entitlement = list(state['grain_entitlement_reports'])
    owner_grain = sum(int(row['units']) for row in entitlement)
    carrier_wages = sum(float(row['transport_wages']) for row in entitlement)
    recalled = sum(float(row['total']) for row in state['reserve_recall_reports'])
    completed = sum(project['progress'] >= project['required_work'] for project in projects)
    selected_plan = state.get('selected') or 'none'
    detail = (f'Intended plan: {selected_plan.replace("_", " ")}. '
              + ('Built: ' + '; '.join(
                  f'{project["kind"].replace("_", " ")} at {project["site"]} '
                  f'({project["status"]}, {project["progress"]}/{project["required_work"]} turns, '
                  f'{project["integrity"]:.0%} intact)'
                  for project in projects) if projects else
                 'No strategic project was funded.'))
    if state['food_reports']:
        last = state['food_reports'][-1]
        detail += (f' Last measured {last["site"]} harvest: '
                   f'{last["food_produced"]} food units produced, '
                   f'{last["private_reserved"]} privately held, '
                   f'{last["underfed"]}/{last["households"]} local households underfed.')
    return {
        'projects': detail,
        'strategic_projects': projects,
        'project_payments': payments,
        'project_revenue_reports': list(state['revenue_reports']),
        'grain_entitlement_reports': entitlement,
        'reserve_recall_reports': list(state['reserve_recall_reports']),
        'social_stats': [
            {'label': 'Strategic works and labor',
             'value': f'{completed}/{len(projects)} completed',
             'note': f'{wages:,.0f} treasury units paid to local crews; '
                     f'{crew_food:,} public maize units fed defense crews.'},
            {'label': 'Local receipts moved to Cairo',
             'value': f'{cairo_transfers:,.1f} units',
             'note': 'Actual net local tax and tariff receipts centralized after prior claims.'},
            {'label': 'Private surplus delivered to households',
             'value': f'{owner_grain:,} food units',
             'note': f'Compulsory transfers from owners and well-stocked households; Cairo paid {carrier_wages:,.1f} to carriers.'},
            {'label': 'District reserves called to Cairo',
             'value': f'{recalled:,.1f} treasury units',
             'note': 'Cash moved from local governments, leaving less for district services and raising unrest.'},
        ],
    }
