"""Conservative, pure action metadata; never invokes handlers or AI planners."""

VERSION = '1'


def snapshot(nation, tile, client):
    actions = []
    name = getattr(nation, 'name', None)
    if nation is not None and client == 'web':
        # The server checks aggregate treasury food; describe that exact gate.
        food = nation.treasury()['food']
        actions.append({'id': 'granary_relief', 'label': 'Granary relief',
                        'target': name, 'capabilities': ['immediate_food_relief'],
                        'available': food >= 20,
                        'prerequisites': 'The SET_POLICY handler requires at least 20 aggregate treasury food units.',
                        'effect': 'Disburses up to 50 food units and resets hunger for selected hungry agents; does not restore harvest output.',
                        'tradeoffs': 'Uses stored food. Distribution and available recipients limit relief.',
                        'navigation': 'AI explainer → Review granary relief',
                        'command': {'cmd': 'SET_POLICY', 'payload': {'key': 'granary_relief', 'val': True, 'nation': name}}})
        actions.append({'id': 'ten_hour_act', 'label': 'Ten-Hour Act', 'target': name,
                        'capabilities': ['limit_workday'], 'available': True,
                        'prerequisites': 'National SET_POLICY control.',
                        'effect': 'Sets the legal workday ceiling to at most ten hours across member territories.',
                        'tradeoffs': 'A legal limit is not proof of effective enforcement or improved wages.',
                        'navigation': 'Government → Ten-Hour Act',
                        'command': {'cmd': 'SET_POLICY', 'payload': {'key': 'ten_hour_act', 'val': True, 'nation': name}}})
    province = getattr(tile, 'province', None)
    if province is not None and client == 'desktop':
        provincial_agent = getattr(getattr(province, 'gov', None), 'agent', None)
        cash = float(getattr(provincial_agent, 'cash', 0))
        actions.append({'id': 'prov_healthcare', 'label': 'Regional Health Initiative',
                        'target': province.name, 'navigation_tile': tile.name,
                        'capabilities': ['health_program_expenditure'],
                        'available': cash >= 150, 'prerequisites': 'Provincial government cash of at least 150 local units.',
                        'effect': 'The current left-drawer handler spends 150 and records a program announcement. It does not itself establish a treatment or sanitation improvement.',
                        'tradeoffs': 'Expenditure alone must not be described as proven disease prevention or successful care.',
                        'navigation': 'Governance → Province → Regional Health Initiative'})
    if nation is not None and client == 'desktop':
        hungry = sum(bool(getattr(a, 'alive', True) and getattr(a, 'hungry_steps', 0) > 0)
                     for t in getattr(nation, 'tiles', ()) for a in getattr(t, 'agents', ()))
        actions.append({'id': 'nat_emergency_granary', 'label': 'Granary relief',
                        'target': name, 'capabilities': ['immediate_food_relief'],
                        'available': hungry > 0, 'prerequisites': 'Living hungry households in the nation.',
                        'effect': 'The existing desktop handler resets hunger for up to twenty-five selected people per tile; it records reserves separately.',
                        'tradeoffs': 'The desktop implementation differs from web relief. Do not assume equivalent stock consumption or restored production.',
                        'navigation': 'Governance → Nation → Granary relief'})
    return actions


COVERAGE = ('Catalog is conservative and incomplete: indexed web granary/workday and desktop '
            'health-program/granary controls only. Other policies, projects, and scenario actions '
            'relief may exist. Future designs are provisional coverage gaps requiring code review; '
            'never claim catalog omission proves absence. Unaffordable actions are implemented.')


def current(world, packet):
    """Refresh availability locally; never rerun the model or the simulation."""
    trace = world.get('run_trace')
    if getattr(trace, 'run_id', None) != packet['selection']['run_id']:
        return {'state': 'world_changed', 'actions': [], 'turn': world.get('turn')}
    subject = packet['selection']['subject']
    tile = next((t for t in world.get('tiles', ()) if t.name == subject['id']), None) if subject['type'] != 'nation' else None
    nation = next((n for n in world.get('nations', ()) if n.name == subject['id']), None) if subject['type'] == 'nation' else getattr(tile, 'owner_nation', None)
    return {'state': 'current', 'turn': world.get('turn'),
            'actions': snapshot(nation, tile, packet['selection']['client'])}
