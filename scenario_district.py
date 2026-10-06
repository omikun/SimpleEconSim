"""Tile-level responses and measured pressures for the Egypt campaign."""

from __future__ import annotations

import math

from nutrition import deficit_fraction, fat_kg, queue_emergency_meal


DISTRICT_ACTIONS = frozenset({
    'district_relief', 'district_tax_relief', 'district_negotiate', 'district_repress',
})


def selected_district(world, nation):
    tile = world.get('selected_region')
    if tile in getattr(nation, 'tiles', ()):
        return tile
    return getattr(nation, 'capital', None) or (nation.tiles[0] if nation.tiles else None)


def district_metrics(tile):
    people = [agent for agent in getattr(tile, 'agents', [])
              if getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False)
              and not getattr(agent, 'is_corporation', False) and not getattr(agent, 'is_trader', False)]
    deficit = sum(deficit_fraction(agent) for agent in people)
    underfed = sum(deficit_fraction(agent) > 0 for agent in people)
    energy = float(tile.protest_energy_log[-1]) if getattr(tile, 'protest_energy_log', None) else 0.0
    return {
        'people': len(people),
        'underfed': underfed,
        'mean_deficit': deficit / max(1, len(people)),
        'mean_fat_kg': sum(fat_kg(agent) for agent in people) / max(1, len(people)),
        'protest': energy,
        'tax_rate': float(getattr(tile.gov, 'tax_rate', 0.0)),
        'military_present': bool(getattr(tile, 'police_employed', 0)
                                 or any(getattr(unit, 'soldiers', 0) > 0 for unit in getattr(tile, 'military_units', []))),
    }


def apply_action(world, nation, action_id):
    tile = selected_district(world, nation)
    if tile is None:
        return False, 'Select an Egyptian district first.'
    metrics = district_metrics(tile)
    name = getattr(tile, 'scenario_location', None) or getattr(tile, 'display_name', tile.name)
    treasury = nation.government.agent
    if action_id == 'district_relief':
        available = min(10, int(nation.government.food_inventory) // 4)
        people = sorted((agent for agent in tile.agents
                         if getattr(agent, 'alive', True) and deficit_fraction(agent) > 0
                         and not getattr(agent, 'is_government', False)
                         and not getattr(agent, 'is_corporation', False)
                         and not getattr(agent, 'is_trader', False)),
                        key=lambda agent: (-deficit_fraction(agent), float(agent.cash)))
        recipients = people[:available]
        if not recipients:
            return False, f'No underfed households in {name} can receive a full public meal.'
        for agent in recipients:
            queue_emergency_meal(agent, 4)
        nation.government.food_inventory -= 4 * len(recipients)
        world['scenario_state']['public_maize_stock_units'] = nation.government.food_inventory
        return True, f'Issued next-meal rations to {len(recipients)} underfed households in {name}; used {4 * len(recipients)} public maize units.'
    if action_id == 'district_tax_relief':
        old_rate = metrics['tax_rate']
        if old_rate <= 0:
            return False, f'{name} already has no local tax.'
        tile.gov.tax_rate = max(0.0, old_rate - 0.04)
        # A proportional response keeps small cuts from causing a full-size jump.
        fraction = (old_rate - tile.gov.tax_rate) / 0.04
        tile.unrest_level = float(getattr(tile, 'unrest_level', 0.0)) * math.exp(-0.15 * fraction)
        if getattr(tile, 'protest_energy_log', None):
            tile.protest_energy_log[-1] *= math.exp(-0.15 * fraction)
        nation.legitimacy = min(1.0, float(nation.legitimacy) + 0.01 * fraction)
        state = world['scenario_state']
        state['tax_relief_enacted'] = True
        state['extraction_level'] = max(0, int(state.get('extraction_level', 0)) - 1)
        return True, f'Suspended four points of local tax in {name}; local protest pressure eased and future receipts will fall.'
    if action_id == 'district_negotiate':
        cost = 15.0
        if float(treasury.cash) < cost:
            return False, 'Cairo needs 15 treasury units to fund a district settlement.'
        people = sorted((agent for agent in tile.agents
                         if getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False)
                         and not getattr(agent, 'is_corporation', False)
                         and not getattr(agent, 'is_trader', False)),
                        key=lambda agent: (float(agent.cash), -deficit_fraction(agent)))[:15]
        if not people:
            return False, 'There are no local households to receive a settlement.'
        treasury.cash -= cost
        for agent in people:
            agent.cash += cost / len(people)
        relief = 1.0 - math.exp(-cost / (20.0 + 4.0 * metrics['protest']))
        if getattr(tile, 'protest_energy_log', None):
            tile.protest_energy_log[-1] *= 1.0 - relief
        tile.unrest_level = max(0.0, float(getattr(tile, 'unrest_level', 0.0)) * (1.0 - relief))
        for faction in getattr(getattr(tile, 'factions', None), 'factions', {}).values():
            for grievance in faction.grievances:
                faction.grievances[grievance] *= 1.0 - relief
        return True, f'Paid 15 treasury units to poorer households in {name} and negotiated with local organizers.'
    if action_id == 'district_repress':
        if not metrics['military_present']:
            return False, f'{name} has no police or garrison to disperse a crowd.'
        from unrest import apply_repression
        seeded = apply_repression(tile, int(world.get('turn', 0)))
        return True, f'Forces dispersed protesters in {name}; {seeded} people received a casualty or broken-promise memory. Legitimacy fell.'
    return False, 'Unknown district response.'
