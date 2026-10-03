"""Funded, staffed strategic repairs in the Guided Egypt campaign.

These small works use actual Egyptian treasury cash and local household labor.
They deliberately do not duplicate the sandbox's larger building recipes.
"""

from __future__ import annotations

from typing import Any


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
    },
    'canal_line': {
        'front': 'sovereignty', 'title': 'Prepare the canal defense line',
        'sites': ('Tel el Kebir',), 'cash_cost': 70.0,
        'work_turns': 2, 'workers': 3, 'upkeep': 5.0,
    },
}


def initialize(world: dict) -> None:
    world['scenario_state']['strategic_projects'] = {
        'projects': [], 'payments': [], 'events': [], 'food_reports': [], 'selected': None,
    }


def _state(world: dict) -> dict:
    return world['scenario_state']['strategic_projects']


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


def _pay_workers(world: dict, project: dict, amount: float, kind: str) -> bool:
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
        treasury.cash -= wage
        worker.cash += wage
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


def get_project(world: dict, kind: str, site: str | None = None) -> dict | None:
    return next((project for project in _state(world)['projects']
                 if project['kind'] == kind and (site is None or project['site'] == site)
                 and project['status'] != 'cancelled'), None)


def start_project(world: dict, kind: str, site: str) -> tuple[bool, str]:
    definition = PROJECT_DEFS.get(kind)
    if definition is None or site not in definition['sites']:
        return False, 'This strategic repair is unavailable at that site.'
    if get_project(world, kind, site):
        return False, f'{definition["title"]} is already funded at {site}.'
    if _occupier(world, site):
        return False, f'Egypt cannot begin this work while foreign troops hold {site}.'
    tile = _tile(world, site)
    workers = _workers(tile, definition['workers'])
    if len(workers) < definition['workers']:
        return False, f'{site} lacks enough available local workers.'
    project = {
        'id': f'{kind}:{site}', 'kind': kind, 'front': definition['front'],
        'site': site, 'tile': tile.name, 'sponsor': 'Egypt',
        'status': 'building', 'started_turn': int(world['turn']),
        'last_advanced_turn': int(world['turn']), 'progress': 0,
        'required_work': definition['work_turns'], 'worker_ids': [agent.id for agent in workers],
        'paid_cash': 0.0, 'upkeep_paid': 0.0, 'last_upkeep_turn': None,
        'integrity': 1.0, 'events': [],
    }
    if not _pay_workers(world, project, definition['cash_cost'], 'construction_wage'):
        return False, f'Egypt needs {definition["cash_cost"]:.0f} treasury units for {definition["title"].lower()}.'
    project['paid_cash'] = definition['cash_cost']
    _state(world)['projects'].append(project)
    _state(world)['selected'] = project['id']
    message = (f'{definition["title"]} begins at {site}. Cairo paid '
               f'{definition["cash_cost"]:.0f} to {len(workers)} local workers; '
               f'completion needs {definition["work_turns"]} staffed turns.')
    _event(world, project, message)
    return True, message


def advance(world: dict) -> None:
    turn = int(world['turn'])
    for project in _state(world)['projects']:
        if project['status'] == 'cancelled' or project['last_advanced_turn'] >= turn:
            continue
        project['last_advanced_turn'] = turn
        if _occupier(world, project['site']):
            if project['status'] != 'occupied':
                project['status'] = 'occupied'
                _event(world, project, f'{project["site"]} is occupied; Egyptian project work and benefits stop.')
            continue
        if project['integrity'] < 0.5:
            project['status'] = 'damaged'
            continue
        definition = PROJECT_DEFS[project['kind']]
        tile = _tile(world, project['site'])
        living_ids = {agent.id for agent in _workers(tile, len(tile.agents))}
        if len(living_ids.intersection(project['worker_ids'])) < definition['workers']:
            project['status'] = 'stalled'
            continue
        if project['progress'] < project['required_work']:
            project['status'] = 'building'
            project['progress'] += 1
            if project['progress'] == project['required_work']:
                _event(world, project, f'{definition["title"]} is complete at {project["site"]}.')
            else:
                continue
        if _pay_workers(world, project, definition['upkeep'], 'staff_wage'):
            project['status'] = 'operating'
            project['last_upkeep_turn'] = turn
            project['upkeep_paid'] = round(project['upkeep_paid'] + definition['upkeep'], 6)
        else:
            project['status'] = 'unfunded'
            if project['last_upkeep_turn'] != turn - 1:
                _event(world, project, f'{definition["title"]} cannot operate without paid staff.')


def effectiveness(world: dict, kind: str, site: str) -> float:
    project = get_project(world, kind, site)
    if (project is None or project['status'] != 'operating' or _occupier(world, site)
            or project['last_upkeep_turn'] is None
            or project['last_upkeep_turn'] < int(world['turn']) - 1):
        return 0.0
    return max(0.0, min(1.0, float(project['integrity'])))


def damage_project(world: dict, kind: str, site: str, damage: float) -> bool:
    project = get_project(world, kind, site)
    if project is None or damage <= 0:
        return False
    project['integrity'] = max(0.0, project['integrity'] - float(damage))
    if project['integrity'] < 0.5:
        project['status'] = 'damaged'
    _event(world, project, f'{PROJECT_DEFS[kind]["title"]} at {site} is damaged to {project["integrity"]:.0%}.')
    return True


def repair_project(world: dict, kind: str, site: str) -> tuple[bool, str]:
    project = get_project(world, kind, site)
    if project is None or project['integrity'] >= 1.0:
        return False, 'No damaged strategic work needs repair here.'
    if _occupier(world, site):
        return False, 'Egypt cannot repair occupied works.'
    cost = round(PROJECT_DEFS[kind]['cash_cost'] * (1.0 - project['integrity']) * 0.5, 2)
    if not _pay_workers(world, project, cost, 'repair_wage'):
        return False, f'Repair needs {cost:.0f} treasury units and the original local crew.'
    project['paid_cash'] = round(project['paid_cash'] + cost, 6)
    project['integrity'] = 1.0
    project['status'] = 'building' if project['progress'] < project['required_work'] else 'unfunded'
    message = f'Egypt paid {cost:.0f} to repair {PROJECT_DEFS[kind]["title"].lower()} at {site}.'
    _event(world, project, message)
    return True, message


def cancel_project(world: dict, kind: str, site: str) -> tuple[bool, str]:
    project = get_project(world, kind, site)
    if project is None:
        return False, 'No active project exists here.'
    project['status'] = 'cancelled'
    message = f'Egypt abandoned {PROJECT_DEFS[kind]["title"].lower()} at {site}; paid wages remain with the workers.'
    _event(world, project, message)
    return True, message


def current_plan(world: dict) -> dict[str, Any] | None:
    projects = _state(world)['projects']
    selected = _state(world).get('selected')
    return next((project for project in reversed(projects)
                 if project['id'] == selected and project['status'] != 'cancelled'), None) or next(
                     (project for project in reversed(projects) if project['status'] != 'cancelled'), None)


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
