"""Tile-level responses and measured pressures for the Egypt campaign."""

from __future__ import annotations

import math

from goods import Goods
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


def _grievance_balances(tile):
    return {
        str(faction_id): {
            str(grievance): float(value)
            for grievance, value in getattr(faction, 'grievances', {}).items()
        }
        for faction_id, faction in getattr(
            getattr(tile, 'factions', None), 'factions', {}).items()
    }


def _trace_district_action(tile, *, nation, action_id, turn, success,
                           operation_key, inputs, cause_event_ids=None):
    from run_trace import emit

    operation_id = (f'district-action:{tile.name}:{int(turn)}:{action_id}:'
                    f'{operation_key}')
    return emit(
        tile, kind='district_action_resolved', record_class='outcome',
        phase='scenario_action',
        subject={'type': 'tile', 'id': tile.name, 'nation': nation.name,
                 'action_id': action_id},
        metric_id='scenario.district_action', unit='success',
        before=0, after=int(bool(success)),
        formula_id='scenario_district.action_resolution.v1',
        inputs={'operation_id': operation_id, 'action_id': action_id,
                'turn': int(turn), 'success': bool(success), **inputs},
        cause_event_ids=cause_event_ids)


def _trace_district_ration(tile, *, operation_id, turn, nation, recipient,
                           units, stock_before, stock_after,
                           queue_before, queue_after):
    from run_trace import emit

    contract = {
        'contract_version': 'goods_transfer.v1',
        'operation_id': operation_id,
        'operation_type': 'district_relief_ration',
        'good': Goods.food.name,
        'unit': 'food_units',
        'amount': int(units),
        'payer_account': {
            'type': 'government_food_inventory', 'id': str(nation.government.name),
            'good': Goods.food.name, 'balance_before': int(stock_before),
            'balance_after': int(stock_after), 'balance_scope': 'food_inventory',
        },
        'payee_account': {
            'type': 'agent_emergency_ration_queue', 'id': str(recipient.id),
            'good': Goods.food.name, 'balance_before': int(queue_before),
            'balance_after': int(queue_after),
            'balance_scope': 'next_meal_entitlement',
        },
        'delivery_status': 'queued_for_next_consumption_step',
        'counterparty_leg_status': 'public_stock_and_household_entitlement_captured',
    }
    return emit(
        tile, kind='district_relief_ration_transfer', record_class='transfer',
        phase='scenario_action',
        subject={'type': 'tile', 'id': tile.name, 'agent_id': recipient.id,
                 'good': Goods.food.name},
        metric_id='goods.district_relief', unit='food_units',
        before=0, after=int(units),
        inputs={'operation_id': operation_id, 'turn': int(turn),
                'recipient_id': recipient.id, 'transfer_contract': contract})


def _trace_district_settlement(tile, *, nation, turn, operation_id, cost,
                               treasury_before, treasury_after, payments):
    from finance_trace import cash_transfer_contract, emit_cash_transfer

    currency = (getattr(nation, 'currency', None)
                or getattr(tile, 'home_currency', None) or 'local_currency')
    accounts = [
        {'id': str(person.id), 'currency': currency,
         'balance_before': float(before), 'balance_after': float(after),
         'amount': float(amount)}
        for person, amount, before, after in payments
    ]
    contract = cash_transfer_contract(
        operation_id, 'district_settlement', amount=cost, currency=currency,
        payer_account={
            'type': 'national_government_agent_cash',
            'id': str(nation.government.agent.id), 'currency': currency,
            'balance_before': float(treasury_before),
            'balance_after': float(treasury_after), 'balance_scope': 'cash',
        },
        payee_account={
            'type': 'household_agent_cash_group',
            'id': f'{operation_id}:recipients', 'currency': currency,
            'member_count': len(accounts),
            'member_ids': [row['id'] for row in accounts],
            'members': accounts, 'balance_scope': 'member_cash_balances',
        },
        recipient_count=len(accounts),
        counterparty_leg_status='treasury debit and each household cash balance captured',
    )
    return emit_cash_transfer(
        tile, kind='district_settlement_payment', contract=contract,
        phase='scenario_action',
        subject={'type': 'tile', 'id': tile.name, 'nation': nation.name},
        inputs={'turn': int(turn), 'district': tile.name,
                'recipient_ids': [row['id'] for row in accounts]})


def apply_action(world, nation, action_id):
    tile = selected_district(world, nation)
    if tile is None:
        return False, 'Select an Egyptian district first.'
    turn = int(world.get('turn', 0))
    metrics = district_metrics(tile)
    name = getattr(tile, 'scenario_location', None) or getattr(tile, 'display_name', tile.name)
    treasury = nation.government.agent

    def finish(success, message, *, reason, operation_key, inputs=None,
               cause_event_ids=None):
        _trace_district_action(
            tile, nation=nation, action_id=action_id, turn=turn,
            success=success, operation_key=operation_key,
            inputs={'reason': reason, **(inputs or {})},
            cause_event_ids=cause_event_ids)
        return success, message

    if action_id == 'district_relief':
        stock_before = int(nation.government.food_inventory)
        available = min(10, int(nation.government.food_inventory) // 4)
        people = sorted((agent for agent in tile.agents
                         if getattr(agent, 'alive', True) and deficit_fraction(agent) > 0
                         and not getattr(agent, 'is_government', False)
                         and not getattr(agent, 'is_corporation', False)
                         and not getattr(agent, 'is_trader', False)),
                        key=lambda agent: (-deficit_fraction(agent), float(agent.cash)))
        recipients = people[:available]
        if not recipients:
            reason = ('no_underfed_households' if not people
                      else 'public_stock_below_full_meal')
            return finish(
                False, f'No underfed households in {name} can receive a full public meal.',
                reason=reason, operation_key=f'stock-{stock_before}',
                inputs={'public_food_inventory': stock_before,
                        'underfed_household_count': len(people),
                        'rations_available': available})
        transfer_event_ids = []
        ration_operation_id = (f'district-relief:{tile.name}:{turn}:'
                               f'{stock_before}')
        for agent in recipients:
            queue_before = int(getattr(agent, 'emergency_food_units', 0))
            queue_emergency_meal(agent, 4)
            stock_at_start = int(nation.government.food_inventory)
            nation.government.food_inventory -= 4
            transfer_id = _trace_district_ration(
                tile, operation_id=f'{ration_operation_id}:{agent.id}',
                turn=turn, nation=nation, recipient=agent, units=4,
                stock_before=stock_at_start,
                stock_after=int(nation.government.food_inventory),
                queue_before=queue_before,
                queue_after=int(getattr(agent, 'emergency_food_units', 0)))
            if transfer_id:
                transfer_event_ids.append(transfer_id)
        world['scenario_state']['public_maize_stock_units'] = nation.government.food_inventory
        return finish(
            True, f'Issued next-meal rations to {len(recipients)} underfed households in {name}; used {4 * len(recipients)} public maize units.',
            reason='rations_queued', operation_key=f'stock-{stock_before}',
            inputs={'public_food_inventory_before': stock_before,
                    'public_food_inventory_after': int(nation.government.food_inventory),
                    'rations_queued': len(recipients),
                    'food_units_used': 4 * len(recipients),
                    'recipient_ids': [agent.id for agent in recipients]},
            cause_event_ids=transfer_event_ids)
    if action_id == 'district_tax_relief':
        old_rate = metrics['tax_rate']
        if old_rate <= 0:
            return finish(
                False, f'{name} already has no local tax.',
                reason='local_tax_already_zero', operation_key=f'rate-{old_rate:.6f}',
                inputs={'tax_rate_before': old_rate, 'tax_rate_after': old_rate})
        unrest_before = float(getattr(tile, 'unrest_level', 0.0))
        protest_before = (float(tile.protest_energy_log[-1])
                          if getattr(tile, 'protest_energy_log', None) else None)
        legitimacy_before = float(getattr(nation, 'legitimacy', 0.0))
        extraction_before = int(world['scenario_state'].get('extraction_level', 0))
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
        return finish(
            True, f'Suspended four points of local tax in {name}; local protest pressure eased and future receipts will fall.',
            reason='local_tax_reduced', operation_key=f'rate-{old_rate:.6f}',
            inputs={'tax_rate_before': old_rate,
                    'tax_rate_after': float(tile.gov.tax_rate),
                    'unrest_before': unrest_before,
                    'unrest_after': float(tile.unrest_level),
                    'protest_energy_before': protest_before,
                    'protest_energy_after': (float(tile.protest_energy_log[-1])
                                             if getattr(tile, 'protest_energy_log', None)
                                             else None),
                    'unrest_multiplier': math.exp(-0.15 * fraction),
                    'nation_legitimacy_before': legitimacy_before,
                    'nation_legitimacy_after': float(nation.legitimacy),
                    'extraction_level_before': extraction_before,
                    'extraction_level_after': int(state['extraction_level'])})
    if action_id == 'district_negotiate':
        cost = 15.0
        treasury_before = float(treasury.cash)
        if treasury_before < cost:
            return finish(
                False, 'Cairo needs 15 treasury units to fund a district settlement.',
                reason='insufficient_treasury_cash',
                operation_key=f'cash-{treasury_before:.6f}',
                inputs={'required_cash': cost,
                        'treasury_cash_before': treasury_before})
        people = sorted((agent for agent in tile.agents
                         if getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False)
                         and not getattr(agent, 'is_corporation', False)
                         and not getattr(agent, 'is_trader', False)),
                        key=lambda agent: (float(agent.cash), -deficit_fraction(agent)))[:15]
        if not people:
            return finish(
                False, 'There are no local households to receive a settlement.',
                reason='no_household_recipients',
                operation_key=f'cash-{treasury_before:.6f}',
                inputs={'required_cash': cost,
                        'treasury_cash_before': treasury_before})
        operation_id = (f'district-settlement:{tile.name}:{turn}:'
                        f'{treasury_before:.6f}')
        payment_balances = []
        treasury.cash -= cost
        for agent in people:
            amount = cost / len(people)
            recipient_before = float(agent.cash)
            agent.cash += amount
            payment_balances.append((agent, amount, recipient_before,
                                     float(agent.cash)))
        payment_event_id = _trace_district_settlement(
            tile, nation=nation, turn=turn, operation_id=operation_id,
            cost=cost, treasury_before=treasury_before,
            treasury_after=float(treasury.cash), payments=payment_balances)
        relief = 1.0 - math.exp(-cost / (20.0 + 4.0 * metrics['protest']))
        unrest_before = float(getattr(tile, 'unrest_level', 0.0))
        protest_before = (float(tile.protest_energy_log[-1])
                          if getattr(tile, 'protest_energy_log', None) else None)
        grievances_before = _grievance_balances(tile)
        if getattr(tile, 'protest_energy_log', None):
            tile.protest_energy_log[-1] *= 1.0 - relief
        tile.unrest_level = max(0.0, float(getattr(tile, 'unrest_level', 0.0)) * (1.0 - relief))
        for faction in getattr(getattr(tile, 'factions', None), 'factions', {}).values():
            for grievance in faction.grievances:
                faction.grievances[grievance] *= 1.0 - relief
        return finish(
            True, f'Paid 15 treasury units to poorer households in {name} and negotiated with local organizers.',
            reason='settlement_paid_and_pressure_reduced',
            operation_key=f'cash-{treasury_before:.6f}',
            inputs={'settlement_operation_id': operation_id,
                    'treasury_cash_before': treasury_before,
                    'treasury_cash_after': float(treasury.cash),
                    'settlement_amount': cost,
                    'recipient_ids': [agent.id for agent in people],
                    'relief_fraction': relief,
                    'unrest_before': unrest_before,
                    'unrest_after': float(tile.unrest_level),
                    'protest_energy_before': protest_before,
                    'protest_energy_after': (float(tile.protest_energy_log[-1])
                                             if getattr(tile, 'protest_energy_log', None)
                                             else None),
                    'grievances_before': grievances_before,
                    'grievances_after': _grievance_balances(tile)},
            cause_event_ids=[payment_event_id] if payment_event_id else None)
    if action_id == 'district_repress':
        if not metrics['military_present']:
            return finish(
                False, f'{name} has no police or garrison to disperse a crowd.',
                reason='no_police_or_garrison', operation_key='no-force',
                inputs={'police_employed': int(getattr(tile, 'police_employed', 0)),
                        'military_present': False})
        owner_nation = getattr(tile, 'owner_nation', None) or nation
        legitimacy_before = float(getattr(owner_nation, 'legitimacy', 0.0))
        protest_before = (float(tile.protest_energy_log[-1])
                          if getattr(tile, 'protest_energy_log', None) else None)
        grievances_before = _grievance_balances(tile)
        casualties_before = sum(
            len(getattr(agent, 'memory', {}).get('mem_casualties', []))
            for agent in tile.agents)
        promises_before = sum(
            len(getattr(agent, 'memory', {}).get('mem_promises', []))
            for agent in tile.agents)
        from unrest import apply_repression
        seeded = apply_repression(tile, turn)
        casualties_after = sum(
            len(getattr(agent, 'memory', {}).get('mem_casualties', []))
            for agent in tile.agents)
        promises_after = sum(
            len(getattr(agent, 'memory', {}).get('mem_promises', []))
            for agent in tile.agents)
        return finish(
            True, f'Forces dispersed protesters in {name}; {seeded} people received a casualty or broken-promise memory. Legitimacy fell.',
            reason='force_used_to_disperse_protest', operation_key='force-present',
            inputs={'police_employed': int(getattr(tile, 'police_employed', 0)),
                    'garrison_soldiers': sum(
                        int(getattr(unit, 'soldiers', 0))
                        for unit in getattr(tile, 'military_units', [])),
                    'people_seeded_with_memories': int(seeded),
                    'casualty_memory_count_before': casualties_before,
                    'casualty_memory_count_after': casualties_after,
                    'broken_promise_memory_count_before': promises_before,
                    'broken_promise_memory_count_after': promises_after,
                    'protest_energy_before': protest_before,
                    'protest_energy_after': (float(tile.protest_energy_log[-1])
                                             if getattr(tile, 'protest_energy_log', None)
                                             else None),
                    'legitimacy_before': legitimacy_before,
                    'legitimacy_after': float(owner_nation.legitimacy),
                    'legitimacy_cost': 0.15,
                    'grievances_before': grievances_before,
                    'grievances_after': _grievance_balances(tile)})
    return finish(False, 'Unknown district response.',
                  reason='unknown_action', operation_key='unknown',
                  inputs={'requested_action_id': action_id})
