"""Legacy worldview entry points for the authoritative desktop action suite."""

from client.desktop import actions as _impl

# Keep existing imports (including private helpers) available without maintaining
# another implementation of diplomacy, construction, science and debt controls.
globals().update({name: value for name, value in vars(_impl).items()
                  if not name.startswith('__')})


def actions_tab_hit(pos, box_x, box_y, world):
    """Retain the legacy campaign guard before delegating ordinary actions."""
    if world.get('scenario_id') == 'labor_frontier_rivalry':
        world['scenario_feedback'] = 'Use the scenario decisions for this campaign.'
        world['actions_open'] = False
        return True
    return _impl.actions_tab_hit(pos, box_x, box_y, world)
