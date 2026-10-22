"""
worldview_policies.py — Interactive Governance & Policy Actions panel for the right sidebar.

Allows players and governors to view and execute targeted actions for the currently
selected City / Tile, Province, or Sovereign Nation (or Frontier Wilderness).
All actions maintain strict money and resource conservation.
"""

from __future__ import annotations
import pygame
from goods import Goods
from worldview_camera import WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from worldview_map import (
    NATION_COLORS, PROVINCE_COLORS, TEXT, DIM, RED, GREEN, ACCENT, HEX_EDGE
)
from army import recruit_unit
from intents import BuildIntent
from buildings import BUILDING_RECIPES
from unrest import apply_repression

# Dimensions & Layout
PANEL_LEFT = MAP_RIGHT + 12
PANEL_W = WIDTH - PANEL_LEFT - 6

# Colors
CARD_BG = (24, 26, 36)
CARD_BORDER = (45, 50, 70)
BTN_BG = (36, 42, 58)
BTN_HOVER = (52, 60, 84)
BTN_BORDER = (70, 85, 115)
BTN_ACTIVE = (60, 110, 180)

# Registered hitboxes for the current frame
_ACTION_BUTTONS = []
_SCOPE_TABS = []


def _policy_trace_region(world, target):
    candidates = [target]
    candidates.extend(getattr(target, 'tiles', ()))
    candidates.extend(world.get('tiles', ()))
    return next((tile for tile in candidates
                 if (getattr(tile, '_run_trace', None) is not None
                     and getattr(tile, '_collective_trace_clock', None) is not None)), None)


def _policy_operation_id(world, target, action_id, region):
    if region is None:
        return None
    clock = region._collective_trace_clock
    return (f"policy:{action_id}:{getattr(target, 'name', 'unnamed')}:"
            f"{int(world.get('turn', 0))}:{int(clock.get('next', 0))}")


def _trace_policy_funding(world, target, action_id, *, cost, source_cash,
                          affordable, reason, funded=None, recipient_count=None,
                          decision_inputs=None):
    region = _policy_trace_region(world, target)
    operation_id = _policy_operation_id(world, target, action_id, region)
    if region is None:
        return {'region': None, 'operation_id': None, 'event_id': None}
    from run_trace import emit
    nation = (getattr(target, 'nation', None)
              or next((getattr(tile, 'owner_nation', None)
                       for tile in getattr(target, 'tiles', ())
                       if getattr(tile, 'owner_nation', None) is not None), None))
    currency = (getattr(target, 'currency', None)
                or getattr(nation, 'currency', None)
                or getattr(region, 'home_currency', None)
                or 'local_currency')
    inputs = {
        'operation_id': operation_id, 'turn': int(world.get('turn', 0)),
        'action_id': action_id, 'amount_requested': float(cost),
        'source_cash_before': float(source_cash),
        'cash_shortfall': max(0.0, float(cost) - float(source_cash)),
        'affordable': bool(affordable),
        'funded': bool(affordable if funded is None else funded),
        'recipient_count': recipient_count,
        'reason': reason,
    }
    inputs.update(decision_inputs or {})
    event_id = emit(
        region, kind='provincial_policy_funding_decision',
        record_class='decision', phase='policy_action',
        subject={'type': 'province', 'id': getattr(target, 'name', 'unnamed')},
        metric_id='scenario.provincial_policy_funding', unit='funded',
        after=inputs['funded'], inputs=inputs)
    return {'region': region, 'operation_id': operation_id,
            'event_id': event_id, 'currency': currency,
            'turn': int(world.get('turn', 0))}


def _emit_policy_outcome(trace, target, action_id, *, success, reason,
                         before=None, after=None, cause_event_ids=None,
                         inputs=None):
    region = trace.get('region')
    if region is None:
        return None
    from run_trace import emit
    return emit(
        region, kind='provincial_policy_action_outcome',
        record_class='outcome', phase='policy_action',
        subject={'type': 'province', 'id': getattr(target, 'name', 'unnamed')},
        metric_id='scenario.provincial_policy_action',
        before='pending', after='applied' if success else 'no_effect',
        unit='policy_result',
        inputs={'operation_id': trace.get('operation_id'),
                'turn': trace.get('turn'), 'action_id': action_id,
                'success': bool(success), 'reason': reason,
                'source_cash_before': before,
                'source_cash_after': after,
                **(inputs or {})},
        cause_event_ids=cause_event_ids)


def _trace_provincial_internal_transfer(world, target, recipient_tile, *,
                                        action_id, trace, amount,
                                        payer_before, payer_after,
                                        payee_before, payee_after):
    region = trace.get('region')
    if region is None:
        return None, None
    from finance_trace import account_ref, transfer_contract
    from run_trace import emit
    nation = (getattr(target, 'nation', None)
              or getattr(recipient_tile, 'owner_nation', None))
    currency = (trace.get('currency')
                or getattr(recipient_tile, 'home_currency', None)
                or 'local_currency')
    payer_agent = target.gov.agent
    payee_agent = recipient_tile.gov.agent
    operation_id = trace['operation_id']
    common = {
        'amount': float(amount), 'amount_currency': currency,
        'payer_account': account_ref(
            'provincial_treasury', str(payer_agent.id), currency,
            province_id=target.name, nation_id=getattr(nation, 'name', None),
            balance_before=float(payer_before), balance_after=float(payer_after),
            balance_scope='government_agent.cash'),
        'payee_account': account_ref(
            'municipal_treasury', str(payee_agent.id),
            getattr(recipient_tile, 'home_currency', None) or currency,
            tile=recipient_tile.name, nation_id=getattr(nation, 'name', None),
            balance_before=float(payee_before), balance_after=float(payee_after),
            balance_scope='government_agent.cash'),
        'local_cash_leg_amount': float(amount),
        'counterparty_leg_status': 'paired_internal_transfer_same_nation',
        'source': action_id, 'turn': int(world.get('turn', 0)),
    }
    payer_contract = transfer_contract(
        operation_id, 'provincial_equalization_grant', side='payer',
        local_cash_leg_currency=currency, **common)
    payer_event_id = emit(
        region, kind='provincial_equalization_grant_debit',
        record_class='transfer', phase='policy_action',
        subject={'type': 'province', 'id': target.name},
        metric_id='finance.internal_transfer', unit=currency, after=-float(amount),
        inputs={'operation_id': operation_id,
                'transfer_contract': payer_contract},
        cause_event_ids=([trace['event_id']] if trace.get('event_id') else None))
    payee_contract = transfer_contract(
        operation_id, 'provincial_equalization_grant', side='payee',
        local_cash_leg_currency=(getattr(recipient_tile, 'home_currency', None)
                                 or currency), **common)
    payee_event_id = emit(
        region, kind='provincial_equalization_grant_receipt',
        record_class='transfer', phase='policy_action',
        subject={'type': 'tile/treasury', 'id': recipient_tile.name},
        metric_id='finance.internal_transfer',
        unit=getattr(recipient_tile, 'home_currency', None) or currency,
        after=float(amount),
        inputs={'operation_id': operation_id,
                'transfer_contract': payee_contract},
        cause_event_ids=[payer_event_id] if payer_event_id else None)
    return payer_event_id, payee_event_id


def _trace_provincial_policy_expenditure(world, target, action_id, trace, *,
                                         amount, payer_before, payer_after,
                                         service):
    region = trace.get('region')
    if region is None:
        return None
    from finance_trace import account_ref, transfer_contract
    from run_trace import emit
    payer_agent = target.gov.agent
    currency = trace.get('currency') or 'local_currency'
    operation_id = trace['operation_id']
    contract = transfer_contract(
        operation_id, action_id, side='payer', amount=float(amount),
        amount_currency=currency,
        payer_account=account_ref(
            'provincial_treasury', str(payer_agent.id), currency,
            province_id=target.name,
            balance_before=float(payer_before), balance_after=float(payer_after),
            balance_scope='government_agent.cash'),
        payee_account={'type': 'public_policy_service', 'id': target.name,
                        'service': service, 'cash_balance_captured': False},
        local_cash_leg_amount=float(amount), local_cash_leg_currency=currency,
        counterparty_leg_status='policy_expenditure_no_cash_payee',
        source=action_id, turn=int(world.get('turn', 0)))
    return emit(
        region, kind='provincial_policy_expenditure', record_class='transfer',
        phase='policy_action', subject={'type': 'province', 'id': target.name},
        metric_id='finance.policy_expenditure', unit=currency,
        after=-float(amount),
        inputs={'operation_id': operation_id, 'service': service,
                'transfer_contract': contract},
        cause_event_ids=([trace['event_id']] if trace.get('event_id') else None))


def _execute_city_emergency_food(world, target):
    cost = 50.0
    government = getattr(target, 'gov', None)
    bank = getattr(target, 'bank', None)
    owner = getattr(target, 'owner_nation', None)
    region = _policy_trace_region(world, target)
    operation_id = _policy_operation_id(world, target, 'city_emergency_food', region)
    currency = (getattr(target, 'home_currency', None)
                or getattr(owner, 'currency', None) or 'local_currency')
    candidates = []
    source = None
    payer = None
    payer_type = None
    payer_balance_before = None

    government_available = (float(government.agent.cash)
                            if government and hasattr(government, 'agent') else None)
    government_tested = government_available is not None
    candidates.append({'source': 'city_government_cash',
                       'evaluated': government_tested,
                       'available_cash': government_available,
                       'sufficient': bool(government_tested
                                          and government_available >= cost)})
    if government_tested and government_available >= cost:
        source, payer_type = 'city_government_cash', 'municipal_treasury'
        payer = government.agent
        payer_balance_before = government_available
    else:
        bank_available = (float(bank.capital)
                          if bank is not None and hasattr(bank, 'capital') else None)
        bank_tested = bank_available is not None
        candidates.append({'source': 'tile_bank_capital',
                           'evaluated': bank_tested,
                           'available_cash': bank_available,
                           'sufficient': bool(bank_tested and bank_available >= cost)})
        if bank_tested and bank_available >= cost:
            source, payer_type = 'tile_bank_capital', 'commercial_bank_capital'
            payer = bank
            payer_balance_before = bank_available
        elif owner is not None:
            owner_treasury_cash = float(owner.treasury()['cash'])
            candidates.append({'source': 'owner_national_treasury',
                               'evaluated': True,
                               'available_cash': owner_treasury_cash,
                               'sufficient': owner_treasury_cash >= cost})
            if owner_treasury_cash >= cost:
                payer = owner.tiles[0].gov.agent
                source, payer_type = 'owner_national_treasury', 'national_treasury'
                payer_balance_before = float(payer.cash)

    funding_reason = ('funded_by_priority_source' if source is not None
                      else 'no_candidate_source_can_cover_cost')
    funding_event_id = None
    expenditure_event_id = None
    if region is not None:
        from run_trace import emit
        funding_event_id = emit(
            region, kind='city_emergency_food_funding_decision',
            record_class='decision', phase='policy_action',
            subject={'type': 'tile/action', 'id': target.name},
            metric_id='scenario.city_emergency_food_funding', unit='funded',
            after=source is not None,
            inputs={'operation_id': operation_id,
                    'turn': int(world.get('turn', 0)), 'action_id': 'city_emergency_food',
                    'amount_requested': cost, 'source_priority': [
                        'city_government_cash', 'tile_bank_capital',
                        'owner_national_treasury'],
                    'candidate_sources': candidates,
                    'selected_source': source,
                    'source_balance_before': payer_balance_before,
                    'cash_shortfall': (max(0.0, cost -
                                           max([row['available_cash'] or 0.0
                                                for row in candidates], default=0.0))
                                       if source is None else 0.0),
                    'funded': source is not None, 'reason': funding_reason,
                    'food_distribution_occurs_without_funding': True})

    source_balance_after = payer_balance_before
    if source == 'city_government_cash':
        payer.cash -= cost
        source_balance_after = float(payer.cash)
    elif source == 'tile_bank_capital':
        from bank_trace import begin_change, finish_change
        bank_change = begin_change(payer, region)
        payer.capital -= cost
        finish_change(payer, bank_change, 'policy_food_bank_funding',
                      inputs={'amount': cost, 'funding_source': source})
        source_balance_after = float(payer.capital)
    elif source == 'owner_national_treasury':
        payer.cash -= cost
        source_balance_after = float(payer.cash)

    if region is not None and source is not None:
        from finance_trace import account_ref, transfer_contract
        from run_trace import emit
        payer_id = str(getattr(payer, 'id', getattr(payer, 'name', source)))
        contract = transfer_contract(
            operation_id, 'city_emergency_food_aid', side='payer',
            amount=cost, amount_currency=currency,
            payer_account=account_ref(
                payer_type, payer_id, currency, tile=target.name,
                balance_before=payer_balance_before,
                balance_after=source_balance_after,
                balance_scope=('bank.capital' if source == 'tile_bank_capital'
                               else 'government_agent.cash')),
            payee_account={'type': 'public_food_aid_service',
                           'id': target.name, 'cash_balance_captured': False},
            local_cash_leg_amount=cost, local_cash_leg_currency=currency,
            counterparty_leg_status='food_aid_service_no_cash_payee',
            source=source, turn=int(world.get('turn', 0)),
            cash_source_priority=candidates)
        expenditure_event_id = emit(
            region, kind='city_emergency_food_policy_expenditure',
            record_class='transfer', phase='policy_action',
            subject={'type': 'tile', 'id': target.name},
            metric_id='finance.policy_expenditure', unit=currency,
            after=-cost,
            inputs={'operation_id': operation_id, 'source': source,
                    'transfer_contract': contract},
            cause_event_ids=([funding_event_id] if funding_event_id else None))

    recipients = [agent for agent in target.agents
                  if not agent.is_corporation and not agent.is_government
                  and agent.hungry_steps > 0][:30]
    recipient_rows = []
    for index, agent in enumerate(recipients):
        inventory_before = float(agent.inv_get(Goods.food, 0))
        hungry_before = int(agent.hungry_steps)
        alive = bool(getattr(agent, 'alive', True))
        agent.inv_add(Goods.food, 1)
        agent.hungry_steps = 0
        inventory_after = float(agent.inv_get(Goods.food, 0))
        recipient_row = {
            'agent_id': str(agent.id),
            'inventory_food_before': inventory_before,
            'inventory_food_after': inventory_after,
            'hungry_steps_before': hungry_before,
            'hungry_steps_after': int(agent.hungry_steps),
            'alive': alive,
        }
        recipient_rows.append(recipient_row)
        if region is not None:
            from run_trace import emit
            emit(
                region, kind='city_emergency_food_recipient_outcome',
                record_class='outcome', phase='policy_action',
                subject={'type': 'agent', 'id': str(agent.id), 'tile': target.name},
                metric_id='goods.city_emergency_food_creation',
                before=inventory_before, after=inventory_after, unit='food_units',
                inputs={'operation_id': operation_id,
                        'turn': int(world.get('turn', 0)),
                        'source': 'policy_action_created_food_without_stock_debit',
                        'recipient_rank': index + 1,
                        'recipient_selection_rule':
                        'first 30 tile agents excluding government and corporations with hungry_steps above zero',
                        **recipient_row,
                        'funding_event_id': funding_event_id,
                        'cash_expenditure_event_id': expenditure_event_id},
                cause_event_ids=([expenditure_event_id] if expenditure_event_id else
                                 [funding_event_id] if funding_event_id else None))

    if region is not None:
        from run_trace import emit
        emit(
            region, kind='city_emergency_food_policy_outcome',
            record_class='outcome', phase='policy_action',
            subject={'type': 'tile/action', 'id': target.name},
            metric_id='scenario.city_emergency_food_action',
            after=len(recipient_rows), unit='households',
            inputs={'operation_id': operation_id,
                    'turn': int(world.get('turn', 0)),
                    'cost_requested': cost,
                    'cash_paid': cost if source is not None else 0.0,
                    'selected_source': source,
                    'source_balance_before': payer_balance_before,
                    'source_balance_after': source_balance_after,
                    'funding_reason': funding_reason,
                    'recipient_count': len(recipient_rows),
                    'food_units_created': len(recipient_rows),
                    'stock_debit_recorded': False,
                    'recipient_ids': [row['agent_id'] for row in recipient_rows],
                    'policy_message': 'Emergency food aid distributed',
                    'funding_event_id': funding_event_id,
                    'cash_expenditure_event_id': expenditure_event_id},
            cause_event_ids=([event_id for event_id in
                              (funding_event_id, expenditure_event_id) if event_id]
                             or None))
    world['policy_feedback'] = (f"Emergency food aid distributed in {target.name}!", GREEN)


def _execute_frontier_pioneer_grant(world, target):
    region = _policy_trace_region(world, target)
    operation_id = _policy_operation_id(
        world, target, 'frontier_pioneer_grant', region)
    turn = int(world.get('turn', 0))
    homesteaders = [agent for agent in target.agents
                    if getattr(agent, 'is_homesteader', False)]
    decision_event_id = None
    if region is not None:
        from run_trace import emit
        decision_event_id = emit(
            region, kind='frontier_pioneer_aid_decision',
            record_class='decision', phase='policy_action',
            subject={'type': 'frontier/action', 'id': target.name},
            metric_id='scenario.frontier_pioneer_aid_gate',
            unit='eligible_households',
            after=len(homesteaders),
            inputs={'operation_id': operation_id, 'turn': turn,
                    'action_id': 'frontier_pioneer_grant',
                    'recipient_count': len(homesteaders),
                    'eligible_agent_ids': [str(getattr(agent, 'id',
                                                       getattr(agent, 'name', 'unknown')))
                                           for agent in homesteaders],
                    'selection_rule': 'all tile agents with is_homesteader true',
                    'food_units_per_recipient': 2.0,
                    'displayed_policy_cost': 40.0,
                    'cash_debited': 0.0,
                    'stock_debit_recorded': False,
                    'food_source': 'policy_action_created_food',
                    'reason': ('eligible_homesteaders_present' if homesteaders
                               else 'no_eligible_homesteaders')})

    recipient_ids = []
    food_units_created = 0.0
    for agent in homesteaders:
        recipient_id = str(getattr(agent, 'id',
                                   getattr(agent, 'name', 'unknown')))
        inventory_before = float(agent.inv_get(Goods.food, 0))
        agent.inv_add(Goods.food, 2)
        inventory_after = float(agent.inv_get(Goods.food, 0))
        actual_food_added = inventory_after - inventory_before
        food_units_created += actual_food_added
        recipient_ids.append(recipient_id)
        if region is not None:
            from run_trace import emit
            emit(
                region, kind='frontier_pioneer_food_recipient_outcome',
                record_class='outcome', phase='policy_action',
                subject={'type': 'frontier_pioneer', 'id': recipient_id,
                         'tile': target.name},
                metric_id='goods.frontier_pioneer_food',
                before=inventory_before, after=inventory_after,
                unit='food_units',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'food_units_added': actual_food_added,
                        'alive': bool(getattr(agent, 'alive', True)),
                        'food_source': 'policy_action_created_food',
                        'stock_debit_recorded': False,
                        'displayed_policy_cost': 40.0,
                        'funding_event_id': decision_event_id},
                cause_event_ids=([decision_event_id]
                                 if decision_event_id else None))

    if region is not None:
        from run_trace import emit
        emit(
            region, kind='frontier_pioneer_aid_outcome',
            record_class='outcome', phase='policy_action',
            subject={'type': 'frontier/action', 'id': target.name},
            metric_id='scenario.frontier_pioneer_aid',
            after=food_units_created, unit='food_units',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'recipient_count': len(recipient_ids),
                    'recipient_ids': recipient_ids,
                    'food_units_per_recipient': 2.0,
                    'food_units_created': food_units_created,
                    'stock_debit_recorded': False,
                    'displayed_policy_cost': 40.0,
                    'cash_debited': 0.0,
                    'funding_event_id': decision_event_id},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
    world['policy_feedback'] = (
        f"Pioneer aid delivered to homesteaders in {target.name}!",
        (200, 230, 150))


def _execute_national_guano_subsidy(world, target):
    cost = 100.0
    gov_agent = target.government.agent
    treasury_before = float(gov_agent.cash)
    tiles = list(getattr(target, 'tiles', []))
    region = _policy_trace_region(world, target)
    operation_id = _policy_operation_id(
        world, target, 'nat_subsidize_guano_import', region)
    currency = (getattr(target, 'currency', None)
                or getattr(region, 'home_currency', None) or 'local_currency')
    funding_event_id = None
    ports_event_id = None
    if region is not None:
        from run_trace import emit
        funding_event_id = emit(
            region, kind='national_guano_funding_decision',
            record_class='decision', phase='policy_action',
            subject={'type': 'nation/action', 'id': target.name},
            metric_id='scenario.national_guano_funding', unit='funded',
            after=treasury_before >= cost,
            inputs={'operation_id': operation_id,
                    'turn': int(world.get('turn', 0)),
                    'action_id': 'nat_subsidize_guano_import',
                    'cost_requested': cost,
                    'treasury_before': treasury_before,
                    'cash_shortfall': max(0.0, cost - treasury_before),
                    'coastal_port_search_performed': treasury_before >= cost,
                    'funded': treasury_before >= cost,
                    'reason': ('treasury_funds_guano_subsidy'
                               if treasury_before >= cost
                               else 'treasury_cash_below_cost')})
    if treasury_before < cost:
        world['policy_feedback'] = (
            f"Insufficient Treasury: Requires ${cost:.0f} (Current: ${gov_agent.cash:.0f}).",
            (240, 80, 80))
        return

    coastal_tiles = [
        tile for tile in tiles
        if (getattr(tile, 'is_coast', False)
            or any(getattr(neighbor, 'is_water', False)
                   for neighbor in getattr(tile, 'neighbors', {}).values()))]
    if region is not None:
        from run_trace import emit
        ports_event_id = emit(
            region, kind='national_guano_port_availability',
            record_class='decision', phase='policy_action',
            subject={'type': 'nation/action', 'id': target.name},
            metric_id='scenario.national_guano_ports', unit='coastal_tiles',
            after=len(coastal_tiles),
            inputs={'operation_id': operation_id,
                    'turn': int(world.get('turn', 0)),
                    'eligible_tile_ids': [tile.name for tile in coastal_tiles],
                    'eligible_tile_count': len(coastal_tiles),
                    'selection_rule':
                    'nation tiles marked coastal or adjacent to a water neighbor',
                    'treasury_gate_event_id': funding_event_id,
                    'available': bool(coastal_tiles),
                    'reason': ('coastal_ports_available' if coastal_tiles
                               else 'no_coastal_port_tiles')},
            cause_event_ids=([funding_event_id] if funding_event_id else None))
    if not coastal_tiles:
        world['policy_feedback'] = (
            "No coastal port tiles exist to receive guano blockade runners!",
            (240, 80, 80))
        return

    gov_agent.cash -= cost
    treasury_after_debit = float(gov_agent.cash)
    share_cost = cost / len(coastal_tiles)
    expenditure_event_id = None
    if region is not None:
        from finance_trace import account_ref, transfer_contract
        from run_trace import emit
        payer_account = account_ref(
            'national_treasury', str(getattr(gov_agent, 'id', target.name)),
            currency, nation_id=target.name,
            balance_before=treasury_before, balance_after=treasury_after_debit,
            balance_scope='government_agent.cash')
        contract = transfer_contract(
            operation_id, 'national_guano_import_subsidy', side='payer',
            amount=cost, amount_currency=currency,
            payer_account=payer_account,
            payee_account={'type': 'guano_import_allocation',
                           'id': target.name,
                           'cash_balance_captured': False},
            local_cash_leg_amount=cost, local_cash_leg_currency=currency,
            counterparty_leg_status=
            'allocated_to_coastal_agent_receipts_or_treasury_refunds',
            source='nat_subsidize_guano_import',
            coastal_tile_count=len(coastal_tiles),
            per_tile_cash_share=share_cost,
            turn=int(world.get('turn', 0)))
        expenditure_event_id = emit(
            region, kind='national_guano_subsidy_treasury_debit',
            record_class='transfer', phase='policy_action',
            subject={'type': 'nation/treasury', 'id': target.name},
            metric_id='finance.policy_expenditure', unit=currency,
            after=-cost,
            inputs={'operation_id': operation_id,
                    'treasury_balance_after': treasury_after_debit,
                    'transfer_contract': contract},
            cause_event_ids=([funding_event_id, ports_event_id]
                             if funding_event_id and ports_event_id else
                             [event_id for event_id in
                              (funding_event_id, ports_event_id) if event_id]
                             or None))

    delivered_total = 0.0
    paid_total = 0.0
    refund_total = 0.0
    recipient_rows = []
    for tile in coastal_tiles:
        stock_existed = hasattr(tile, 'fertilizer_stock')
        stock_before = float(getattr(tile, 'fertilizer_stock', 12.0))
        depleted_before = bool(getattr(tile, 'is_nitrate_depleted', False))
        tile.fertilizer_stock = min(80.0, stock_before + 20.0)
        tile.is_nitrate_depleted = False
        stock_after = float(tile.fertilizer_stock)
        delivery = stock_after - stock_before
        delivered_total += delivery

        traders = [agent for agent in getattr(tile, 'agents', [])
                   if getattr(agent, 'is_trader', False)]
        recipients = traders[:1] if traders else list(tile.agents[:1])
        recipient = recipients[0] if recipients else None
        receipt_event_id = None
        refund_event_id = None
        if recipient is not None:
            cash_before = float(recipient.cash)
            recipient.cash += share_cost
            cash_after = float(recipient.cash)
            paid_total += share_cost
            recipient_type = ('trader' if traders else 'local_agent')
            recipient_row = {'tile_id': tile.name,
                             'recipient_id': str(getattr(recipient, 'id',
                                                         None)
                                                 or getattr(recipient, 'name',
                                                            'unknown')),
                             'recipient_type': recipient_type,
                             'amount': share_cost,
                             'cash_before': cash_before,
                             'cash_after': cash_after,
                             'destination': 'selected_tile_agent'}
            recipient_rows.append(recipient_row)
            if region is not None:
                from finance_trace import account_ref, transfer_contract
                from run_trace import emit
                payee_currency = (getattr(recipient, 'home_currency', None)
                                  or currency)
                allocation_contract = transfer_contract(
                    operation_id, 'national_guano_import_allocation', side='payee',
                    amount=share_cost, amount_currency=currency,
                    payer_account={'type': 'guano_import_allocation',
                                   'id': target.name, 'currency': currency,
                                   'cash_balance_captured': False},
                    payee_account=account_ref(
                        recipient_type, recipient_row['recipient_id'],
                        payee_currency, tile=tile.name,
                        balance_before=cash_before, balance_after=cash_after,
                        balance_scope='agent.cash'),
                    local_cash_leg_amount=share_cost,
                    local_cash_leg_currency=payee_currency,
                    counterparty_leg_status=
                    'allocated_from_aggregate_national_treasury_debit',
                    source='nat_subsidize_guano_import',
                    turn=int(world.get('turn', 0)))
                receipt_event_id = emit(
                    region, kind='national_guano_import_payment_receipt',
                    record_class='transfer', phase='policy_action',
                    subject={'type': 'tile/agent',
                             'id': recipient_row['recipient_id'],
                             'tile': tile.name},
                    metric_id='finance.policy_payment_receipt',
                    unit=payee_currency, after=share_cost,
                    inputs={'operation_id': operation_id,
                            'cash_balance_after': cash_after,
                            'recipient_type': recipient_type,
                            'transfer_contract': allocation_contract},
                    cause_event_ids=([expenditure_event_id]
                                     if expenditure_event_id else None))
        else:
            treasury_refund_before = float(gov_agent.cash)
            gov_agent.cash += share_cost
            treasury_refund_after = float(gov_agent.cash)
            refund_total += share_cost
            recipient_row = {'tile_id': tile.name,
                             'recipient_id': str(getattr(gov_agent, 'id',
                                                         target.name)),
                             'recipient_type': 'national_treasury_refund',
                             'amount': share_cost,
                             'cash_before': treasury_refund_before,
                             'cash_after': treasury_refund_after,
                             'destination': 'no_tile_agent_refund'}
            recipient_rows.append(recipient_row)
            if region is not None:
                from finance_trace import account_ref, transfer_contract
                from run_trace import emit
                refund_contract = transfer_contract(
                    operation_id, 'national_guano_import_refund', side='payee',
                    amount=share_cost, amount_currency=currency,
                    payer_account={'type': 'guano_import_allocation',
                                   'id': target.name, 'currency': currency,
                                   'cash_balance_captured': False},
                    payee_account=account_ref(
                        'national_treasury', recipient_row['recipient_id'],
                        currency, nation_id=target.name,
                        balance_before=treasury_refund_before,
                        balance_after=treasury_refund_after,
                        balance_scope='government_agent.cash'),
                    local_cash_leg_amount=share_cost,
                    local_cash_leg_currency=currency,
                    counterparty_leg_status=
                    'unspent_tile_share_refunded_to_national_treasury',
                    source='nat_subsidize_guano_import',
                    turn=int(world.get('turn', 0)))
                refund_event_id = emit(
                    region, kind='national_guano_import_treasury_refund',
                    record_class='transfer', phase='policy_action',
                    subject={'type': 'nation/treasury', 'id': target.name},
                    metric_id='finance.treasury_flow', unit=currency,
                    after=share_cost,
                    inputs={'operation_id': operation_id,
                            'cash_balance_after': treasury_refund_after,
                            'tile_id': tile.name,
                            'transfer_contract': refund_contract},
                    cause_event_ids=([expenditure_event_id]
                                     if expenditure_event_id else None))

        if region is not None:
            from run_trace import emit
            stock_event_id = emit(
                region, kind='national_guano_fertilizer_stock_outcome',
                record_class='outcome', phase='policy_action',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='ecology.fertilizer_stock',
                before=stock_before, after=stock_after,
                unit='fertilizer_units',
                inputs={'operation_id': operation_id,
                        'turn': int(world.get('turn', 0)),
                        'subsidized_delivery_requested': 20.0,
                        'actual_stock_increase': delivery,
                        'stock_cap': 80.0,
                        'stock_before_attribute_existed': stock_existed,
                        'nitrate_depleted_before': depleted_before,
                        'nitrate_depleted_after': False,
                        'cash_share': share_cost,
                        'cash_destination': recipient_row['destination'],
                        'cash_recipient_id': recipient_row['recipient_id'],
                        'funding_event_id': funding_event_id,
                        'port_event_id': ports_event_id,
                        'cash_expenditure_event_id': expenditure_event_id,
                        'cash_receipt_event_id': receipt_event_id,
                        'cash_refund_event_id': refund_event_id},
                cause_event_ids=([event_id for event_id in
                                  (expenditure_event_id, receipt_event_id,
                                   refund_event_id) if event_id] or None))
            if delivery > 0.0:
                emit(
                    region, kind='national_guano_import_delivery',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'tile', 'id': tile.name},
                    metric_id='goods.guano_delivery', before=0.0,
                    after=delivery, unit='fertilizer_units',
                    inputs={'operation_id': operation_id,
                            'turn': int(world.get('turn', 0)),
                            'stock_before': stock_before,
                            'stock_after': stock_after,
                            'requested_per_tile': 20.0,
                            'capped_by_storage': delivery < 20.0,
                            'nitrate_depleted_before': depleted_before,
                            'nitrate_depleted_after': False},
                    cause_event_ids=([stock_event_id]
                                     if stock_event_id else None))
            if depleted_before:
                emit(
                    region, kind='national_guano_nitrate_recovery',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'tile', 'id': tile.name},
                    metric_id='ecology.nitrate_depletion', before=True,
                    after=False, unit='depleted',
                    inputs={'operation_id': operation_id,
                            'turn': int(world.get('turn', 0)),
                            'fertilizer_stock_after': stock_after},
                    cause_event_ids=([stock_event_id]
                                     if stock_event_id else None))

    if region is not None:
        from run_trace import emit
        emit(
            region, kind='national_guano_subsidy_outcome',
            record_class='outcome', phase='policy_action',
            subject={'type': 'nation/action', 'id': target.name},
            metric_id='scenario.national_guano_subsidy',
            before='pending', after='applied', unit='policy_result',
            inputs={'operation_id': operation_id,
                    'turn': int(world.get('turn', 0)),
                    'treasury_before': treasury_before,
                    'treasury_after': float(gov_agent.cash),
                    'gross_cost': cost,
                    'coastal_tile_count': len(coastal_tiles),
                    'cash_share_per_tile': share_cost,
                    'agent_receipt_total': paid_total,
                    'treasury_refund_total': refund_total,
                    'cash_shares_reconciled':
                    abs(paid_total + refund_total - cost) < 1e-8,
                    'fertilizer_units_requested': 20.0 * len(coastal_tiles),
                    'fertilizer_units_added': delivered_total,
                    'fertilizer_shortfall_from_storage_caps':
                    20.0 * len(coastal_tiles) - delivered_total,
                    'recipient_rows': recipient_rows,
                    'treasury_debit_event_id': expenditure_event_id,
                    'funding_event_id': funding_event_id,
                    'port_event_id': ports_event_id},
            cause_event_ids=([event_id for event_id in
                              (funding_event_id, ports_event_id,
                               expenditure_event_id) if event_id] or None))

    msg = (f"Blockade Runner Chartered! Disbursed ${cost:.0f} to deliver "
           f"+20t emergency guano to coastal ports.")
    world['policy_feedback'] = (msg, (120, 240, 150))
    from worldview_engine import ticker_push
    ticker_push(world, world['turn'], 'POLICY', msg, (120, 240, 150))


def draw_policies_panel(surface, world, region, font, font_small, mouse_pos=None):
    """Draw the Governance & Policies interactive panel in the right sidebar."""
    global _ACTION_BUTTONS, _SCOPE_TABS
    _ACTION_BUTTONS = []
    _SCOPE_TABS = []

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    d = TOP_BAR_H
    panel_top = 180 + d
    panel_bottom = HEIGHT - TICKER_H - 36
    panel_h = panel_bottom - panel_top

    if region is None and world.get('nations') and world['nations'][0].tiles:
        region = world['nations'][0].tiles[0]

    owner = getattr(region, 'owner_nation', None) if region is not None else None
    is_wilderness = (region is not None and owner is None)

    # 2. Segmented Scope Switcher Bar (City / Province / Nation)
    active_scope = world.get('policy_scope', 'tile')
    tab_w = (PANEL_W - 24) // 3
    tab_h = 24
    tab_y = panel_top + 6

    scopes = [('tile', 'City'), ('province', 'Province'), ('nation', 'Nation')]
    if is_wilderness:
        scopes = [('tile', 'Frontier'), ('nation', 'Sponsor')]

    for i, (sc_id, sc_label) in enumerate(scopes):
        bx = PANEL_LEFT + 4 + i * (tab_w + 4)
        rect = (bx, tab_y, tab_w, tab_h)
        _SCOPE_TABS.append((rect, sc_id))
        is_sel = (active_scope == sc_id)
        is_hov = (bx <= mx <= bx + tab_w and tab_y <= my <= tab_y + tab_h)
        bg = (55, 75, 110) if is_sel else ((40, 48, 65) if is_hov else (26, 30, 42))
        border_c = ACCENT if is_sel else (BTN_BORDER if is_hov else (45, 52, 70))
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        pygame.draw.rect(surface, border_c, rect, 1, border_radius=4)
        txt = font_small.render(sc_label, True, (255, 255, 255) if is_sel else (TEXT if is_hov else DIM))
        surface.blit(txt, txt.get_rect(center=(bx + tab_w // 2, tab_y + tab_h // 2)))

    cur_y = tab_y + tab_h + 12

    # 3. Render Feedback Banner if recent action was triggered
    feedback = world.get('policy_feedback')
    if feedback:
        fb_text, fb_col = feedback
        fb_surf = font_small.render(fb_text, True, fb_col)
        pygame.draw.rect(surface, (20, 30, 40), (PANEL_LEFT + 4, cur_y, PANEL_W - 24, 22), border_radius=4)
        pygame.draw.rect(surface, fb_col, (PANEL_LEFT + 4, cur_y, PANEL_W - 24, 22), 1, border_radius=4)
        surface.blit(fb_surf, (PANEL_LEFT + 10, cur_y + 3))
        cur_y += 28

    # 4. Scope Content Rendering
    if is_wilderness:
        _draw_frontier_policies(surface, world, region, cur_y, font, font_small, mx, my)
    elif active_scope == 'tile':
        _draw_city_policies(surface, world, region, cur_y, font, font_small, mx, my)
    elif active_scope == 'province':
        _draw_province_policies(surface, world, region, cur_y, font, font_small, mx, my)
    else:
        _draw_nation_policies(surface, world, region, cur_y, font, font_small, mx, my)

    # Tooltip detection on policy action buttons
    if mouse_pos and not world.get('_hovered_left_tooltip'):
        for rect, act_id, target in _ACTION_BUTTONS:
            rx, ry, rw, rh = rect
            if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                from worldview_tooltips import get_button_tooltip_data
                plot_id = None
                r_arg = region
                n_arg = None
                p_arg = None
                if isinstance(target, tuple) and len(target) > 1:
                    r_arg = target[0]
                    plot_id = target[1]
                elif hasattr(target, 'tiles') and hasattr(target, 'provinces'):
                    n_arg = target
                elif hasattr(target, 'regions') or hasattr(target, 'prov_id'):
                    p_arg = target
                elif hasattr(target, 'agents'):
                    r_arg = target

                tdata = get_button_tooltip_data(act_id, world, region=r_arg, nation=n_arg, province=p_arg, plot_id=plot_id)
                if tdata:
                    tdata['btn_rect'] = rect
                    world['_hovered_left_tooltip'] = tdata
                break


def _draw_btn(surface, rect, label, font_small, mx, my, enabled=True, color=TEXT, custom_bg=None, icon_kind=None):
    """Helper to draw clickable action button with optional procedural icon and register hitbox."""
    global _ACTION_BUTTONS
    bx, by, bw, bh = rect
    is_hov = (bx <= mx <= bx + bw and by <= my <= by + bh) and enabled
    if not enabled:
        bg = (20, 22, 28)
        bc = (35, 38, 48)
        tc = (70, 75, 90)
    else:
        bg = custom_bg if custom_bg else (BTN_HOVER if is_hov else BTN_BG)
        bc = ACCENT if is_hov else BTN_BORDER
        tc = (255, 255, 255) if is_hov else color

    pygame.draw.rect(surface, bg, rect, border_radius=4)
    pygame.draw.rect(surface, bc, rect, 1, border_radius=4)

    txt_surf = font_small.render(label, True, tc)
    if icon_kind:
        from ui_icons import get_icon
        icon_surf = get_icon(icon_kind, size=13)
        total_w = 13 + 4 + txt_surf.get_width()
        start_x = bx + (bw - total_w) // 2
        surface.blit(icon_surf, (start_x, by + (bh - 13) // 2))
        surface.blit(txt_surf, (start_x + 17, by + (bh - txt_surf.get_height()) // 2))
    else:
        surface.blit(txt_surf, txt_surf.get_rect(center=(bx + bw // 2, by + bh // 2)))


def _draw_progress_btn(surface, rect, label, progress, font_small, mx, my, icon_kind=None):
    """Draw an active in-progress button with internal live progress bar gauge."""
    bx, by, bw, bh = rect
    # Construction Amber background
    pygame.draw.rect(surface, (45, 36, 20), rect, border_radius=4)
    # Fill bar gauge
    fill_w = max(3, int((bw - 2) * progress))
    pygame.draw.rect(surface, (215, 155, 35), (bx + 1, by + 1, fill_w, bh - 2), border_radius=3)
    # Border
    pygame.draw.rect(surface, (245, 190, 50), rect, 1, border_radius=4)

    txt_surf = font_small.render(label, True, (255, 255, 255))
    if icon_kind:
        from ui_icons import get_icon
        icon_surf = get_icon(icon_kind, size=13)
        total_w = 13 + 4 + txt_surf.get_width()
        start_x = bx + (bw - total_w) // 2
        surface.blit(icon_surf, (start_x, by + (bh - 13) // 2))
        surface.blit(txt_surf, (start_x + 17, by + (bh - txt_surf.get_height()) // 2))
    else:
        surface.blit(txt_surf, txt_surf.get_rect(center=(bx + bw // 2, by + bh // 2)))


# =============================================================================
# CITY / TILE LEVEL POLICIES
# =============================================================================

def _draw_city_policies(surface, world, region, start_y, font, font_small, mx, my):
    """Draw city-specific governance and municipal action cards."""
    global _ACTION_BUTTONS
    if region is None:
        return

    city_name = getattr(region, 'display_name', getattr(region, 'city_name', region.name))
    owner = getattr(region, 'owner_nation', None)
    gov = getattr(region, 'gov', None)
    treasury_cash = gov.agent.cash if gov and hasattr(gov, 'agent') else (region.bank.capital if getattr(region, 'bank', None) else 0.0)
    tax_rate = gov.tax_rate if gov else 0.15
    protest_e = region.protest_energy_log[-1] if region.protest_energy_log else 0.0
    garrison = sum(u.soldiers for u in getattr(region, 'military_units', []))
    hungry = sum(1 for a in region.agents if not a.is_corporation and not a.is_government and a.hungry_steps > 0)

    # Title header
    head = font.render(f"City: {city_name} — Municipal Control", True, (245, 215, 110))
    surface.blit(head, (PANEL_LEFT + 4, start_y))
    start_y += 24

    # Status summary strip
    stat_line = f"Treasury: ${treasury_cash:,.0f} | Tax: {tax_rate*100:.0f}% | Protest: {protest_e:.2f} | Hungry: {hungry}"
    surface.blit(font_small.render(stat_line, True, (180, 195, 215)), (PANEL_LEFT + 4, start_y))
    start_y += 22

    # CARD 1: Fiscal Policy & Municipal Tax
    card1_h = 64
    c1_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font_small.render(f"Municipal Tax Rate: {tax_rate*100:.1f}%", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    tax_desc = "Lowers protest / stimulates growth" if tax_rate < 0.15 else "Increases state revenue / elevates unrest"
    surface.blit(font_small.render(tax_desc, True, DIM), (PANEL_LEFT + 12, start_y + 24))

    b1_rect = (PANEL_LEFT + 12, start_y + 38, 70, 20)
    b2_rect = (PANEL_LEFT + 88, start_y + 38, 70, 20)
    _draw_btn(surface, b1_rect, "[-2% Tax]", font_small, mx, my, enabled=(tax_rate > 0.02))
    _draw_btn(surface, b2_rect, "[+2% Tax]", font_small, mx, my, enabled=(tax_rate < 0.60))
    _ACTION_BUTTONS.append((b1_rect, 'city_tax_cut', region))
    _ACTION_BUTTONS.append((b2_rect, 'city_tax_raise', region))

    # UBI Toggle Button
    ubi_on = getattr(gov, 'ubi_enabled', False)
    b3_rect = (PANEL_LEFT + 166, start_y + 38, 90, 20)
    _draw_btn(surface, b3_rect, f"UBI: {'ON' if ubi_on else 'OFF'}", font_small, mx, my, color=GREEN if ubi_on else DIM)
    _ACTION_BUTTONS.append((b3_rect, 'city_toggle_ubi', region))

    start_y += card1_h + 8

    # CARD 2: Emergency Food Aid & Welfare
    card2_h = 58
    c2_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Emergency Grain Relief ($50)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Buys 30 food & feeds starving agents to quell unrest", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    feed_btn = (PANEL_LEFT + 12, start_y + 36, 140, 20)
    can_feed = (treasury_cash >= 50.0 or (owner and owner.treasury()['cash'] >= 50.0))
    _draw_btn(surface, feed_btn, "Distribute Food", font_small, mx, my, enabled=can_feed, color=GREEN if can_feed else DIM)
    _ACTION_BUTTONS.append((feed_btn, 'city_emergency_food', region))

    start_y += card2_h + 8

    # CARD 3: Security, Militia & Public Order
    card3_h = 104
    c3_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font_small.render(f"Garrison & Security: {garrison} Active Units", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Recruits unemployed labor into militia (-Protest)", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    mil_btn = (PANEL_LEFT + 12, start_y + 44, 120, 22)
    can_mil = (treasury_cash >= 50.0 or (owner and owner.treasury()['cash'] >= 50.0))
    _draw_btn(surface, mil_btn, "Recruit ($50)", font_small, mx, my, enabled=can_mil, color=GREEN if can_mil else DIM)
    _ACTION_BUTTONS.append((mil_btn, 'city_recruit_garrison', region))

    curfew_btn = (PANEL_LEFT + 140, start_y + 44, 120, 22)
    can_curfew = (protest_e >= 2.0)
    _draw_btn(surface, curfew_btn, "Police Curfew", font_small, mx, my, enabled=can_curfew, color=RED if can_curfew else DIM)
    _ACTION_BUTTONS.append((curfew_btn, 'city_police_curfew', region))

    # Covert Shadow Warrant (Assassination)
    assass_btn = (PANEL_LEFT + 12, start_y + 72, 248, 22)
    try:
        from popular_resistance import get_popular_resistance_manager
        r_state_p = get_popular_resistance_manager().get_state(region.name)
        has_tgt = r_state_p.leader_id is not None
        has_active_plot = r_state_p.active_plot is not None and r_state_p.active_plot.status == "in_progress"
        can_assass = has_tgt and not has_active_plot and treasury_cash >= 75.0
        assass_lbl = f"Shadow Warrant (~{r_state_p.active_plot.turns_remaining}t)" if has_active_plot else "Shadow Warrant ($75)"
        assass_col = (245, 180, 50) if has_active_plot else ((230, 80, 80) if can_assass else DIM)
    except Exception:
        can_assass = False
        assass_lbl = "Shadow Warrant ($75)"
        assass_col = DIM

    _draw_btn(surface, assass_btn, assass_lbl, font_small, mx, my, enabled=can_assass, color=assass_col)
    _ACTION_BUTTONS.append((assass_btn, 'city_assassinate_leader', region))

    start_y += card3_h + 8

    # CARD 4: Infrastructure & Capital Construction
    card4_h = 80
    c4_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card4_h)
    pygame.draw.rect(surface, CARD_BG, c4_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c4_rect, 1, border_radius=5)

    buildings = getattr(region, 'buildings', [])
    b_str = ", ".join(f"{b.recipe.display_name if hasattr(b, 'recipe') else b.name.title()}" for b in buildings) if buildings else "None"
    surface.blit(font_small.render(f"Public Infrastructure (Installed: {b_str})", True, ACCENT), (PANEL_LEFT + 12, start_y + 6))

    farm_btn = (PANEL_LEFT + 12, start_y + 26, 120, 22)
    gran_btn = (PANEL_LEFT + 140, start_y + 26, 120, 22)
    mill_btn = (PANEL_LEFT + 12, start_y + 52, 120, 22)
    work_btn = (PANEL_LEFT + 140, start_y + 52, 120, 22)

    struct_defs = [
        (farm_btn, 'farm', 'Farm ($250)', (200, 230, 150), 'arable_silt', 'build_farm'),
        (gran_btn, 'granary', 'Granary ($350)', (240, 200, 120), 'granary', 'build_granary'),
        (mill_btn, 'sawmill', 'Sawmill ($300)', (210, 180, 140), 'timber', 'build_sawmill'),
        (work_btn, 'workshop', 'Workshop ($450)', (160, 210, 255), 'workshop', 'build_workshop'),
    ]

    for rect, b_key, b_label, b_col, b_icon, act_id in struct_defs:
        is_built = any(b.name == b_key for b in buildings)
        active_proj = next((p for p in getattr(region, 'construction_projects', []) if p.recipe.name == b_key and p.status == 'in_progress'), None)
        
        if is_built:
            from ui_icons import draw_progress_bar_button
            draw_progress_bar_button(surface, rect, f"{b_key.capitalize()} Active", 1.0, font_small, theme='complete', icon_kind='check')
        elif active_proj is not None:
            from ui_icons import draw_progress_bar_button
            pct = min(1.0, max(0.0, active_proj.turns_elapsed / max(1, active_proj.total_turns)))
            draw_progress_bar_button(surface, rect, f"{b_key.capitalize()} {active_proj.turns_elapsed}/{active_proj.total_turns}t ({int(pct*100)}%)", pct, font_small, theme='construction', icon_kind=b_icon)
        else:
            _draw_btn(surface, rect, b_label, font_small, mx, my, color=b_col, icon_kind=b_icon)
            _ACTION_BUTTONS.append((rect, act_id, region))

    start_y += card4_h + 8

    # CARD 5: Land Tenure & Enclosure Decrees (P1.4)
    tenure = getattr(region, 'tenure', None)
    if tenure and tenure.plots:
        card5_h = 76
        c5_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card5_h)
        pygame.draw.rect(surface, CARD_BG, c5_rect, border_radius=5)
        pygame.draw.rect(surface, CARD_BORDER, c5_rect, 1, border_radius=5)

        commons_pct = tenure.commons_access * 100
        surface.blit(font_small.render(f"Land Tenure: Commons Access {commons_pct:.0f}%", True, (235, 185, 80)), (PANEL_LEFT + 12, start_y + 8))
        desc = f"Feudal: {tenure.feudal_fraction*100:.0f}% | Enclosed: {tenure.enclosed_fraction*100:.0f}%"
        surface.blit(font_small.render(desc, True, DIM), (PANEL_LEFT + 12, start_y + 24))

        feudal_plots = tenure.feudal_plots()
        if feudal_plots:
            first_feudal = feudal_plots[0]
            from enclosure import calculate_charter_fee
            fee = calculate_charter_fee(first_feudal)
            lord = next((a for a in region.agents if a.id == first_feudal.lord_id), None)
            can_enclose = (lord is not None and lord.cash >= fee)
            enc_btn = (PANEL_LEFT + 12, start_y + 46, 140, 22)
            _draw_btn(surface, enc_btn, f"Enclose (${fee:.0f})", font_small, mx, my,
                       enabled=can_enclose, color=(240, 140, 70) if can_enclose else DIM)
            _ACTION_BUTTONS.append((enc_btn, 'city_enclose_plot', (region, first_feudal.plot_id)))
        else:
            surface.blit(font_small.render("All customary commons enclosed.", True, (130, 200, 140)), (PANEL_LEFT + 12, start_y + 48))

        enclosed_plots = tenure.enclosed_plots()
        if enclosed_plots:
            first_enc = enclosed_plots[0]
            is_pasture = (getattr(first_enc, 'production_type', 'arable') == 'pasture')
            p_lbl = "Pasture (Wool)" if is_pasture else "Arable (Grain)"
            pas_btn = (PANEL_LEFT + 158, start_y + 46, 120, 22)
            _draw_btn(surface, pas_btn, p_lbl, font_small, mx, my, enabled=True, color=(160, 210, 150) if is_pasture else (230, 200, 100))
            _ACTION_BUTTONS.append((pas_btn, 'city_convert_pasture', (region, first_enc.plot_id)))

        start_y += card5_h + 8

    # CARD 6: Ecological Regulations & Public Health (Phase 3)
    card6_h = 104
    c6_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, card6_h)
    pygame.draw.rect(surface, CARD_BG, c6_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c6_rect, 1, border_radius=5)

    fert_on = getattr(region, 'use_fertilizer', False)
    pest_on = getattr(region, 'use_pesticides', False)
    health_on = getattr(region, 'public_healthcare_decree', False)
    fert_lbl = f"Fertilizer: {'ON' if fert_on else 'OFF'}"
    pest_lbl = f"Pesticides: {'ON' if pest_on else 'OFF'}"
    health_lbl = f"Healthcare: {'PUBLIC SUBSIDY' if health_on else 'PRIVATE OUT-OF-POCKET'}"

    surface.blit(font_small.render("Ecological Decrees & Public Health", True, (130, 215, 160)), (PANEL_LEFT + 12, start_y + 8))
    desc_eco = f"Soil: {getattr(region, 'soil_fertility', 1.0)*100:.0f}% | Nut: {getattr(region, 'nutrition_density', 1.0)*100:.0f}% | Smog: {getattr(region, 'pollution_air', 0.0):.0f}"
    surface.blit(font_small.render(desc_eco, True, DIM), (PANEL_LEFT + 12, start_y + 24))

    f_btn = (PANEL_LEFT + 12, start_y + 44, 115, 22)
    p_btn = (PANEL_LEFT + 135, start_y + 44, 115, 22)
    h_btn = (PANEL_LEFT + 12, start_y + 72, PANEL_W - 40, 22)
    _draw_btn(surface, f_btn, fert_lbl, font_small, mx, my, color=GREEN if fert_on else DIM)
    _draw_btn(surface, p_btn, pest_lbl, font_small, mx, my, color=GREEN if pest_on else DIM)
    _draw_btn(surface, h_btn, health_lbl, font_small, mx, my, color=GREEN if health_on else (240, 180, 80))
    _ACTION_BUTTONS.append((f_btn, 'city_mandate_fertilizer', region))
    _ACTION_BUTTONS.append((p_btn, 'city_mandate_pesticides', region))
    _ACTION_BUTTONS.append((h_btn, 'city_toggle_public_healthcare', region))
    start_y += card6_h + 8


# =============================================================================
# PROVINCE LEVEL POLICIES
# =============================================================================

def _draw_province_policies(surface, world, region, start_y, font, font_small, mx, my):
    """Draw province-wide development, logistics, and equalization controls."""
    global _ACTION_BUTTONS
    prov = getattr(region, 'province', None)
    if prov is None:
        surface.blit(font_small.render("No province assigned to this tile.", True, DIM), (PANEL_LEFT + 8, start_y + 20))
        return

    prov_name = getattr(prov, 'display_name', prov.name)
    tiles = getattr(prov, 'tiles', [region])
    total_pop = sum(len(r.agents) for r in tiles)
    avg_col = sum(r.cost_of_living for r in tiles) / max(1, len(tiles))

    head = font.render(f"Province: {prov_name} — Provincial Council", True, (140, 200, 255))
    surface.blit(head, (PANEL_LEFT + 4, start_y))
    start_y += 24

    stat_line = f"Constituent Cities: {len(tiles)} | Pop: {total_pop} | Avg CoL: {avg_col:.2f}"
    surface.blit(font_small.render(stat_line, True, (180, 195, 215)), (PANEL_LEFT + 4, start_y))
    start_y += 22

    # CARD 1: Provincial Development & Capital Equalization
    c1_h = 76
    c1_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font_small.render("Provincial Equalization Grant ($200)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Transfers $200 from central reserves to poorest city", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    grant_btn = (PANEL_LEFT + 12, start_y + 44, 160, 22)
    _draw_btn(surface, grant_btn, "Disburse Grant", font_small, mx, my, color=GREEN)
    _ACTION_BUTTONS.append((grant_btn, 'prov_equalization_grant', prov))

    start_y += c1_h + 10

    # CARD 2: Provincial Road Network & Logistics Standardization
    c2_h = 76
    c2_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Logistics & Transport Standardization", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Harmonizes inter-city trade fees across the province", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    road_btn = (PANEL_LEFT + 12, start_y + 44, 180, 22)
    _draw_btn(surface, road_btn, "Standardize Routes ($100)", font_small, mx, my, color=(200, 230, 150))
    _ACTION_BUTTONS.append((road_btn, 'prov_standardize_routes', prov))

    start_y += c2_h + 10

    # CARD 3: Tax Harmonization
    c3_h = 76
    c3_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    avg_tax = sum(r.gov.tax_rate for r in tiles) / max(1, len(tiles))
    surface.blit(font_small.render(f"Harmonize Province Taxes (Avg: {avg_tax*100:.1f}%)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Sets all member cities to uniform average tax rate", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    tax_btn = (PANEL_LEFT + 12, start_y + 44, 160, 22)
    _draw_btn(surface, tax_btn, "Harmonize Taxes", font_small, mx, my, color=(240, 200, 120))
    _ACTION_BUTTONS.append((tax_btn, 'prov_harmonize_taxes', prov))

    start_y += c3_h + 10

    # CARD 4: Watershed & Soil Conservation Subsidy (Phase 3)
    c4_h = 76
    c4_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c4_h)
    pygame.draw.rect(surface, CARD_BG, c4_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c4_rect, 1, border_radius=5)

    surface.blit(font_small.render("Soil Conservation & Fallow Subsidies ($150)", True, (130, 220, 160)), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Subsidizes legume crop cover & fallow rest (+Soil Regen)", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    soil_btn = (PANEL_LEFT + 12, start_y + 44, 180, 22)
    _draw_btn(surface, soil_btn, "Fund Conservation ($150)", font_small, mx, my, color=(140, 230, 170))
    _ACTION_BUTTONS.append((soil_btn, 'prov_soil_conservation', prov))


# =============================================================================
# NATION LEVEL POLICIES
# =============================================================================

def _draw_nation_policies(surface, world, region, start_y, font, font_small, mx, my):
    """Draw sovereign nation policies (Tariffs, National UBI, statutory tax)."""
    global _ACTION_BUTTONS
    owner = getattr(region, 'owner_nation', None)
    if owner is None and world.get('nations'):
        owner = world['nations'][0]
    if owner is None:
        return

    tr = owner.treasury()
    total_pop = sum(len(r.agents) for r in owner.tiles)

    head = font.render(f"Nation: {owner.name} — Sovereign Decrees", True, (245, 210, 100))
    surface.blit(head, (PANEL_LEFT + 4, start_y))
    start_y += 24

    stat_line = f"Treasury: ${tr['total']:,.0f} | Legitimacy: {owner.legitimacy:.2f} | Pop: {total_pop}"
    surface.blit(font_small.render(stat_line, True, (180, 195, 215)), (PANEL_LEFT + 4, start_y))
    start_y += 22

    # CARD 1: National Statutory Tax Baseline
    c1_h = 68
    c1_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font_small.render("National Income Tax Directive", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Enforces statutory baseline tax across all provinces", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    b1 = (PANEL_LEFT + 12, start_y + 40, 50, 20)
    b2 = (PANEL_LEFT + 68, start_y + 40, 50, 20)
    b3 = (PANEL_LEFT + 124, start_y + 40, 50, 20)
    b4 = (PANEL_LEFT + 180, start_y + 40, 50, 20)
    _draw_btn(surface, b1, "10%", font_small, mx, my)
    _draw_btn(surface, b2, "15%", font_small, mx, my)
    _draw_btn(surface, b3, "25%", font_small, mx, my)
    _draw_btn(surface, b4, "35%", font_small, mx, my)
    _ACTION_BUTTONS.append((b1, 'nat_tax_10', owner))
    _ACTION_BUTTONS.append((b2, 'nat_tax_15', owner))
    _ACTION_BUTTONS.append((b3, 'nat_tax_25', owner))
    _ACTION_BUTTONS.append((b4, 'nat_tax_35', owner))

    start_y += c1_h + 8

    # CARD 2: Import Tariffs & Trade Protectionism
    c2_h = 68
    c2_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Trade Protectionism & Import Tariffs", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Protects domestic manufacturers / raises customs fees", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    t1 = (PANEL_LEFT + 12, start_y + 40, 55, 20)
    t2 = (PANEL_LEFT + 74, start_y + 40, 55, 20)
    t3 = (PANEL_LEFT + 136, start_y + 40, 55, 20)
    t4 = (PANEL_LEFT + 198, start_y + 40, 55, 20)
    _draw_btn(surface, t1, "0% Free", font_small, mx, my)
    _draw_btn(surface, t2, "5% Low", font_small, mx, my)
    _draw_btn(surface, t3, "10% Mod", font_small, mx, my)
    _draw_btn(surface, t4, "15% High", font_small, mx, my)
    _ACTION_BUTTONS.append((t1, 'nat_tariff_0', owner))
    _ACTION_BUTTONS.append((t2, 'nat_tariff_5', owner))
    _ACTION_BUTTONS.append((t3, 'nat_tariff_10', owner))
    _ACTION_BUTTONS.append((t4, 'nat_tariff_15', owner))

    start_y += c2_h + 8

    # CARD 3: Nationwide Welfare (UBI) & Immigration
    c3_h = 76
    c3_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c3_h)
    pygame.draw.rect(surface, CARD_BG, c3_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c3_rect, 1, border_radius=5)

    surface.blit(font_small.render("National Social Welfare & Borders", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Standardizes social safety nets & immigration rules", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    ubi_btn = (PANEL_LEFT + 12, start_y + 46, 120, 22)
    imm_btn = (PANEL_LEFT + 140, start_y + 46, 120, 22)
    _draw_btn(surface, ubi_btn, "Enact UBI", font_small, mx, my, color=GREEN)
    _draw_btn(surface, imm_btn, "Open Borders", font_small, mx, my, color=(160, 210, 255))
    _ACTION_BUTTONS.append((ubi_btn, 'nat_enact_ubi', owner))
    _ACTION_BUTTONS.append((imm_btn, 'nat_toggle_imm', owner))

    start_y += c3_h + 8

    # CARD 4: Labor Regulation & Mass Pacifier Decrees
    c4_h = 128
    c4_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c4_h)
    pygame.draw.rect(surface, CARD_BG, c4_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c4_rect, 1, border_radius=5)

    cur_shift = getattr(owner, 'max_workday_hours', 12.0)
    has_ten = getattr(owner, 'ten_hour_act', False) or cur_shift <= 10.0
    has_safe = getattr(owner, 'factory_safety_act', False)
    has_statute = getattr(owner, 'statute_of_laborers', False)
    has_quarantine = getattr(owner, 'quarantine_active', False)

    ten_tag = " (Ten-Hour Act)" if has_ten else ""
    surface.blit(font_small.render(f"Workday: {cur_shift:.1f}h/day{ten_tag}", True, (240, 140, 80)), (PANEL_LEFT + 12, start_y + 8))

    btn_down = (PANEL_LEFT + 12, start_y + 26, 68, 20)
    btn_up = (PANEL_LEFT + 84, start_y + 26, 68, 20)
    safe_btn = (PANEL_LEFT + 156, start_y + 26, 94, 20)
    spec_btn = (PANEL_LEFT + 12, start_y + 50, 238, 20)
    statute_btn = (PANEL_LEFT + 12, start_y + 74, 238, 20)
    quar_btn = (PANEL_LEFT + 12, start_y + 98, 116, 20)
    granary_btn = (PANEL_LEFT + 134, start_y + 98, 116, 20)

    can_down = (cur_shift > 8.0)
    can_up = (cur_shift < 16.0)

    _draw_btn(surface, btn_down, "-2h Shift", font_small, mx, my, enabled=can_down, color=(130, 210, 140) if can_down else DIM)
    _draw_btn(surface, btn_up, "+2h Shift", font_small, mx, my, enabled=can_up, color=(240, 120, 100) if can_up else DIM)
    _draw_btn(surface, safe_btn, "Safety Mandate" if not has_safe else "Safety: PASS", font_small, mx, my,
              enabled=not has_safe, color=GREEN if has_safe else TEXT)
    _draw_btn(surface, spec_btn, "Subsidize Spectacle ($50)", font_small, mx, my,
              color=(70, 195, 235))
    _draw_btn(surface, statute_btn, "Statute of Laborers (Cap $1.20)" if not has_statute else "Repeal Statute of Laborers", font_small, mx, my,
              color=(240, 180, 70) if not has_statute else (240, 100, 100))
    _draw_btn(surface, quar_btn, "Cordon Sanitaire" if not has_quarantine else "Lift Quarantine", font_small, mx, my,
              color=(240, 140, 60) if not has_quarantine else (240, 90, 90))
    _draw_btn(surface, granary_btn, "Granary Relief", font_small, mx, my,
              color=(120, 220, 140))

    _ACTION_BUTTONS.append((btn_down, 'nat_adjust_shift_-2', owner))
    _ACTION_BUTTONS.append((btn_up, 'nat_adjust_shift_+2', owner))
    _ACTION_BUTTONS.append((safe_btn, 'nat_safety_mandate', owner))
    _ACTION_BUTTONS.append((spec_btn, 'nat_subsidize_entertainment', owner))
    _ACTION_BUTTONS.append((statute_btn, 'nat_toggle_statute_of_laborers', owner))
    _ACTION_BUTTONS.append((quar_btn, 'nat_toggle_quarantine', owner))
    _ACTION_BUTTONS.append((granary_btn, 'nat_emergency_granary', owner))


# =============================================================================
# FRONTIER WILDERNESS POLICIES
# =============================================================================

def _draw_frontier_policies(surface, world, region, start_y, font, font_small, mx, my):
    """Draw colonization and settlement expedition policies for unclaimed frontier tiles."""
    global _ACTION_BUTTONS
    hs_count = sum(1 for a in region.agents if getattr(a, 'is_homesteader', False))
    native_pop = getattr(region, 'wilderness_pop', 0)

    head = font.render(f"Frontier: {region.name} — Settlement", True, (245, 190, 80))
    surface.blit(head, (PANEL_LEFT + 4, start_y))
    start_y += 24

    stat_line = f"Homesteaders: {hs_count} | Natives: {native_pop} | Claim Req: 50%"
    surface.blit(font_small.render(stat_line, True, (180, 195, 215)), (PANEL_LEFT + 4, start_y))
    start_y += 22

    # CARD 1: Sponsor Colonization Expedition
    c1_h = 80
    c1_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c1_h)
    pygame.draw.rect(surface, CARD_BG, c1_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c1_rect, 1, border_radius=5)

    surface.blit(font_small.render("Sponsor Settler Expedition ($100)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Recruits 5 pioneers from capital to colonize this tile", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    exp_btn = (PANEL_LEFT + 12, start_y + 46, 160, 24)
    _draw_btn(surface, exp_btn, "Launch Expedition", font_small, mx, my, color=GREEN)
    _ACTION_BUTTONS.append((exp_btn, 'frontier_expedition', region))

    start_y += c1_h + 10

    # CARD 2: Pioneer Foraging Subsidy
    c2_h = 80
    c2_rect = (PANEL_LEFT + 4, start_y, PANEL_W - 24, c2_h)
    pygame.draw.rect(surface, CARD_BG, c2_rect, border_radius=5)
    pygame.draw.rect(surface, CARD_BORDER, c2_rect, 1, border_radius=5)

    surface.blit(font_small.render("Pioneer Foraging Grant ($40)", True, ACCENT), (PANEL_LEFT + 12, start_y + 8))
    surface.blit(font_small.render("Supplies 20 food & foraging tools to homesteaders", True, DIM), (PANEL_LEFT + 12, start_y + 24))

    grant_btn = (PANEL_LEFT + 12, start_y + 46, 160, 24)
    _draw_btn(surface, grant_btn, "Send Pioneer Aid", font_small, mx, my, color=(200, 230, 150))
    _ACTION_BUTTONS.append((grant_btn, 'frontier_pioneer_grant', region))


# =============================================================================
# CLICK & ACTION DISPATCHER
# =============================================================================

def policy_panel_hit(pos, world):
    """Check if mouse click hits any scope tab or policy action button."""
    global _ACTION_BUTTONS, _SCOPE_TABS
    px, py = pos

    # 1. Check Scope Tabs
    for rect, sc_id in _SCOPE_TABS:
        bx, by, bw, bh = rect
        if bx <= px <= bx + bw and by <= py <= by + bh:
            world['policy_scope'] = sc_id
            return True

    # 2. Check Action Buttons
    for rect, act_id, target in _ACTION_BUTTONS:
        bx, by, bw, bh = rect
        if bx <= px <= bx + bw and by <= py <= by + bh:
            _execute_policy_action(world, act_id, target)
            return True

    return False


def _execute_world_policy_spending(world, action_id, target):
    """Run the shared treasury-funded policy actions for both clients."""
    scopes = {
        'city_toggle_ubi': 'tile', 'city_farm_subsidy': 'tile',
        'city_safety_patrol': 'tile', 'prov_pave_highway': 'province',
        'prov_healthcare': 'province', 'nat_science_prize': 'nation',
    }
    scope = scopes.get(action_id)
    if scope is None:
        return False

    turn = int(world.get('turn', 0))
    if scope == 'tile':
        government = getattr(target, 'gov', None)
        source = getattr(government, 'agent', None)
        source_type = 'municipal_treasury'
    elif scope == 'province':
        government = getattr(target, 'gov', None)
        source = getattr(government, 'agent', None)
        source_type = 'provincial_treasury'
    else:
        government = getattr(target, 'government', None)
        source = getattr(government, 'agent', None)
        source_type = 'national_treasury'

    trace_region = _policy_trace_region(world, target)
    if hasattr(target, 'agents') and hasattr(target, 'name'):
        journal_region = target
    else:
        journal_region = next(iter(getattr(target, 'tiles', ()) or ()), None)
    if journal_region is None:
        journal_region = trace_region or next(iter(world.get('tiles', ())), None)
    sequence = int(getattr(journal_region, '_next_economic_event_id', 1))
    target_name = str(getattr(target, 'name', 'unnamed'))
    operation_id = (_policy_operation_id(world, target, action_id, trace_region)
                    if trace_region is not None else None)
    if operation_id is None:
        operation_id = (f'policy:{action_id}:{target_name}:{turn}:'
                        f'{getattr(journal_region, "name", "world")}:{sequence}')
    owner = (getattr(target, 'owner_nation', None)
             or getattr(target, 'nation', None)
             or (target if scope == 'nation' else None))
    currency = (getattr(target, 'home_currency', None)
                or getattr(target, 'currency', None)
                or getattr(owner, 'currency', None)
                or (getattr(journal_region, 'home_currency', None)
                    if journal_region is not None else None)
                or 'local_currency')
    treasury_before = (float(getattr(source, 'cash', 0.0))
                       if source is not None else None)
    ubi_before = bool(getattr(government, 'ubi_enabled', False)) if government else False
    if action_id == 'city_toggle_ubi':
        population = sum(
            1 for agent in getattr(target, 'agents', ())
            if not getattr(agent, 'is_corporation', False)
            and not getattr(agent, 'is_government', False)
            and getattr(agent, 'alive', True))
        cost = 0.0 if ubi_before else float(population) * 50.0
        payment_required = not ubi_before
    else:
        population = None
        cost = {'city_farm_subsidy': 100.0,
                'city_safety_patrol': 60.0,
                'prov_pave_highway': 120.0,
                'prov_healthcare': 150.0,
                'nat_science_prize': 300.0}[action_id]
        payment_required = True

    affordable = (source is not None and
                  (not payment_required or treasury_before >= cost))
    reason = ('treasury_missing' if source is None else
              'mandate_repeal_requires_no_payment'
              if action_id == 'city_toggle_ubi' and ubi_before else
              'insufficient_treasury_cash' if not affordable else
              'treasury_funds_available')
    funding_event_id = None
    if trace_region is not None:
        from run_trace import emit
        funding_event_id = emit(
            trace_region, kind='world_policy_funding_decision',
            record_class='decision', phase='policy_action',
            subject={'type': f'{scope}/action', 'id': action_id,
                     'target': target_name},
            metric_id='scenario.world_policy_funding', unit='approved',
            before=False, after=bool(affordable),
            formula_id='world_policy.treasury_gate.v1',
            inputs={'operation_id': operation_id, 'action_id': action_id,
                    'scope': scope, 'target': target_name, 'turn': turn,
                    'treasury_present': source is not None,
                    'treasury_cash_before': treasury_before,
                    'amount_requested': cost,
                    'payment_required': payment_required,
                    'population_count': population,
                    'ubi_enabled_before': ubi_before
                    if action_id == 'city_toggle_ubi' else None,
                    'cash_shortfall': (max(0.0, cost - (treasury_before or 0.0))
                                       if payment_required else 0.0),
                    'reason_code': reason})

    if not affordable:
        if source is not None and action_id != 'nat_science_prize':
            dialog_region = (target if scope == 'tile'
                             else world.get('selected_region'))
            names = {
                'city_toggle_ubi':
                f'Universal Basic Income (10-Turn Mandate, ${cost:,.0f})',
                'city_farm_subsidy': 'Agricultural Development Subsidy ($100)',
                'city_safety_patrol': 'Constabulary Safety Patrol ($60)',
                'prov_pave_highway':
                f'Pave Regional Highway in {target_name} ($120)',
                'prov_healthcare':
                f'Provincial Health & Sanitation in {target_name} ($150)',
            }
            world['transfer_dialog'] = {
                'open': True, 'action_kind': 'policy',
                'policy_id': action_id, 'policy_name': names[action_id],
                'cost': cost, 'on_hand': treasury_before,
                'region': dialog_region,
                'nation': getattr(dialog_region, 'owner_nation', None),
            }
        if trace_region is not None:
            from run_trace import emit
            emit(
                trace_region, kind='world_policy_action_outcome',
                record_class='outcome', phase='policy_action',
                subject={'type': f'{scope}/action', 'id': action_id,
                         'target': target_name},
                metric_id='scenario.world_policy_action', unit='status',
                before='pending', after='no_effect',
                inputs={'operation_id': operation_id, 'action_id': action_id,
                        'scope': scope, 'turn': turn, 'success': False,
                        'reason_code': reason,
                        'treasury_cash_before': treasury_before,
                        'treasury_cash_after': treasury_before,
                        'amount_paid': 0.0},
                cause_event_ids=([funding_event_id]
                                 if funding_event_id else None))
        return True

    if action_id == 'city_toggle_ubi' and ubi_before:
        mandate_turns_before = int(getattr(government, 'ubi_mandate_turns_left', 0))
        mandate_treasury_before = float(source.cash)
        government.ubi_enabled = False
        government.ubi_mandate_turns_left = 0
        message = f'Repealed Universal Basic Income in {target_name}.'
        state_before, state_after = 'enabled', 'disabled'
        outcome = {'ubi_enabled_before': True, 'ubi_enabled_after': False,
                   'mandate_turns_before': mandate_turns_before,
                   'mandate_turns_after': 0, 'amount_paid': 0.0,
                   'treasury_cash_before': mandate_treasury_before,
                   'treasury_cash_after': float(source.cash)}
        payment_event_id = None
    else:
        treasury_before = float(source.cash)
        source.cash -= cost
        treasury_after = float(source.cash)
        recipient = None
        recipient_type = None
        recipient_tile = None
        recipient_before = recipient_after = None
        officers_before = officers_after = None
        protest_before = protest_after = None
        if action_id == 'city_safety_patrol':
            from imperialism import _disburse_agent_funds
            disbursement = _disburse_agent_funds(world, owner, cost)
            if disbursement:
                recipient = disbursement['recipient']
                recipient_before = float(disbursement['cash_before'])
                recipient_after = float(disbursement['cash_after'])
                recipient_type = ('corporate_wallet'
                                  if getattr(recipient, 'is_corporation', False)
                                  else 'agent_wallet')
                recipient_tile = next((tile for tile in
                                       [*(getattr(owner, 'tiles', ()) or ()),
                                        *world.get('tiles', ())]
                                       if recipient in getattr(tile, 'agents', ())),
                                      None)
            officers_before = int(getattr(target, 'police_officers', 0))
            target.police_officers = max(officers_before, 5)
            protest_log = getattr(target, 'protest_energy_log', None)
            protest_before = float(protest_log[-1]) if protest_log else None
            if protest_log:
                protest_log[-1] = max(0.0, protest_log[-1] - 0.40)
            protest_after = float(protest_log[-1]) if protest_log else None
        elif action_id == 'city_toggle_ubi':
            government.ubi_enabled = True
            government.ubi_mandate_turns_left = 10

        journal_event = None
        if journal_region is not None and cost > 0:
            from economy.actor_accounts import record as record_economic_event
            journal_event = record_economic_event(
                journal_region, f'world_policy_{action_id}', turn=turn,
                payer_id=getattr(source, 'id', None),
                recipient_id=getattr(recipient, 'id', None),
                amount=cost, asset_id=operation_id, source_id=operation_id,
                currency=currency,
                detail={'action_id': action_id, 'scope': scope,
                        'target': target_name,
                        'recipient_cash_credited': recipient is not None})

        payment_event_id = None
        if trace_region is not None and cost > 0:
            from finance_trace import (account_ref, cash_transfer_contract,
                                       emit_cash_transfer, transfer_contract)
            from run_trace import emit
            payer_account = account_ref(
                source_type, str(getattr(source, 'id', f'{target_name}-treasury')),
                currency, tile=target_name if scope == 'tile' else None,
                province_id=target_name if scope == 'province' else None,
                nation_id=target_name if scope == 'nation' else
                getattr(owner, 'name', None),
                balance_before=treasury_before, balance_after=treasury_after,
                balance_scope='government_agent.cash')
            if recipient is not None:
                recipient_currency = (getattr(recipient, 'home_currency', None)
                                     or getattr(recipient_tile, 'home_currency', None)
                                     or currency)
                contract = cash_transfer_contract(
                    operation_id, action_id, amount=cost, currency=currency,
                    payer_account=payer_account,
                    payee_account=account_ref(
                        recipient_type, str(recipient.id), recipient_currency,
                        tile=getattr(recipient_tile, 'name', None),
                        balance_before=recipient_before,
                        balance_after=recipient_after,
                        balance_scope='agent.cash'),
                    counterparty_leg_status='both_cash_balances_captured',
                    mutation_reference={'turn': turn, 'target': target_name})
                payment_event_id = emit_cash_transfer(
                    trace_region, kind='world_policy_agent_payment',
                    contract=contract, phase='policy_action',
                    subject={'type': 'tile/action', 'id': action_id,
                             'tile': target_name},
                    inputs={'action_id': action_id, 'target': target_name,
                            'recipient_id': str(recipient.id),
                            'recipient_tile': getattr(recipient_tile, 'name', None),
                            'actor_account_event_id': journal_event['id']
                            if journal_event else None},
                    cause_event_ids=([funding_event_id]
                                     if funding_event_id else None))
            else:
                contract = transfer_contract(
                    operation_id, action_id, side='payer', amount=cost,
                    amount_currency=currency, payer_account=payer_account,
                    payee_account={'type': 'unmodeled_public_policy_service',
                                   'id': action_id,
                                   'cash_balance_captured': False},
                    local_cash_leg_amount=cost,
                    local_cash_leg_currency=currency,
                    counterparty_leg_status='policy_expenditure_no_cash_payee',
                    source=action_id, turn=turn)
                payment_event_id = emit(
                    trace_region, kind='world_policy_expenditure',
                    record_class='transfer', phase='policy_action',
                    subject={'type': f'{scope}/treasury', 'id': target_name},
                    metric_id='finance.policy_expenditure', unit=currency,
                    after=-cost,
                    inputs={'operation_id': operation_id,
                            'action_id': action_id,
                            'actor_account_event_id': journal_event['id']
                            if journal_event else None,
                            'transfer_contract': contract},
                    cause_event_ids=([funding_event_id]
                                     if funding_event_id else None))

        if action_id == 'city_toggle_ubi':
            message = f'Enacted 10-Turn UBI in {target_name} (${cost:,.0f} budget committed).'
            state_before, state_after = 'disabled', 'enabled'
            outcome = {'ubi_enabled_before': False, 'ubi_enabled_after': True,
                       'mandate_turns_after': 10, 'population_count': population,
                       'amount_paid': cost, 'benefits_pay_on_later_turns': True}
        elif action_id == 'city_farm_subsidy':
            message = f'Granted $100 Agricultural Subsidy to farms in {target_name}.'
            state_before, state_after = 'not_applied', 'appropriation_debited'
            outcome = {'amount_paid': cost, 'recipient_cash_credited': False,
                       'production_or_farm_state_effect_modeled': False}
        elif action_id == 'city_safety_patrol':
            message = (f'Deployed Public Safety Patrols in {target_name} '
                       '(5 constables on duty, -0.40 Protest).')
            state_before, state_after = 'current_capacity', 'patrol_enforced'
            outcome = {'amount_paid': cost,
                       'police_officers_before': officers_before,
                       'police_officers_after': int(target.police_officers),
                       'protest_energy_before': protest_before,
                       'protest_energy_after': protest_after,
                       'recipient_cash_credited': recipient is not None,
                       'recipient_account_type': recipient_type,
                       'recipient_id': str(recipient.id) if recipient else None,
                       'recipient_tile': getattr(recipient_tile, 'name', None)}
        elif action_id == 'prov_pave_highway':
            message = f'Provincial Administration funded $120 Highway Maintenance in {target_name}.'
            state_before, state_after = 'not_applied', 'appropriation_debited'
            outcome = {'amount_paid': cost, 'recipient_cash_credited': False,
                       'road_or_route_state_effect_modeled': False}
        elif action_id == 'prov_healthcare':
            message = f'Provincial Administration launched $150 Healthcare Program in {target_name}.'
            state_before, state_after = 'not_applied', 'appropriation_debited'
            outcome = {'amount_paid': cost, 'recipient_cash_credited': False,
                       'health_or_service_state_effect_modeled': False}
        else:
            message = f'{target_name} funded a $300 Sovereign Science Grant.'
            state_before, state_after = 'not_awarded', 'appropriation_debited'
            outcome = {'amount_paid': cost, 'recipient_cash_credited': False,
                       'research_or_recipient_effect_modeled': False}
        outcome.update({'treasury_cash_before': treasury_before,
                        'treasury_cash_after': treasury_after})
        if journal_event:
            outcome['actor_account_event_id'] = journal_event['id']

    if trace_region is not None:
        from run_trace import emit
        emit(
            trace_region, kind='world_policy_action_outcome',
            record_class='outcome', phase='policy_action',
            subject={'type': f'{scope}/action', 'id': action_id,
                     'target': target_name},
            metric_id='scenario.world_policy_action', unit='status',
            before=state_before, after=state_after,
            formula_id='world_policy.spending_action.v1',
            inputs={'operation_id': operation_id, 'action_id': action_id,
                    'scope': scope, 'turn': turn, 'success': True,
                    'reason_code': reason, **outcome},
            cause_event_ids=[event_id for event_id in
                             (funding_event_id, payment_event_id)
                             if event_id] or None)
    world['policy_feedback'] = (message,
                                GREEN if state_after not in ('disabled',) else DIM)
    try:
        from worldview_engine import ticker_push
        category = ('HEALTH' if action_id == 'prov_healthcare' else
                    'INNOVATION' if action_id == 'nat_science_prize' else
                    'POLICY')
        ticker_push(world, turn, category, message, (120, 220, 140))
    except ImportError:
        pass
    return True


def _execute_policy_action(world, act_id, target):
    """Execute the triggered policy action with full conservation guarantees."""
    if _execute_world_policy_spending(world, act_id, target):
        return
    # City Tax Adjustment
    if act_id == 'city_tax_cut':
        target.gov.tax_rate = max(0.0, target.gov.tax_rate - 0.02)
        world['policy_feedback'] = (f"Reduced {target.name} tax to {target.gov.tax_rate*100:.1f}%.", GREEN)
    elif act_id == 'city_tax_raise':
        target.gov.tax_rate = min(0.60, target.gov.tax_rate + 0.02)
        world['policy_feedback'] = (f"Raised {target.name} tax to {target.gov.tax_rate*100:.1f}%.", (240, 200, 100))
    # City Emergency Food Aid
    elif act_id == 'city_emergency_food':
        _execute_city_emergency_food(world, target)

    # City Garrison Recruitment
    elif act_id == 'city_recruit_garrison':
        owner = getattr(target, 'owner_nation', None)
        if owner is not None:
            unit = recruit_unit(owner, target, soldier_count=5, t=world['turn'])
            if unit is not None:
                world['policy_feedback'] = (f"Recruited 5 garrison soldiers in {target.name}!", GREEN)
            else:
                world['policy_feedback'] = ("Insufficient unemployed labor to recruit.", RED)

    # City Police Curfew / Interdiction
    elif act_id == 'city_police_curfew':
        from popular_resistance import get_popular_resistance_manager
        res_mgr = get_popular_resistance_manager()
        st = res_mgr.get_state(target.name)
        if st.enclosure_stage not in ('dormant', 'leveling'):
            ok, msg, data = res_mgr.interdict_enclosure_revolt(target, world['turn'], world)
            if ok:
                apply_repression(target, world['turn'], cost_legitimacy=0.05)
                world['policy_feedback'] = (msg, (240, 100, 100))
            else:
                world['policy_feedback'] = (msg, (240, 60, 60))
        else:
            seeded = apply_repression(target, world['turn'])
            if seeded > 0:
                world['policy_feedback'] = (f"Police curfew enforced in {target.name}. Armed patrols quelled riots.", (240, 100, 100))
            else:
                world['policy_feedback'] = (f"Cannot enforce curfew in {target.name}: no armed military garrison or police on payroll!", (240, 60, 60))

    # City Covert Shadow Warrant (Assassination Contract)
    elif act_id == 'city_assassinate_leader':
        from popular_resistance import get_popular_resistance_manager
        res_mgr = get_popular_resistance_manager()
        ok, msg, data = res_mgr.initiate_assassination_plot(target, world['turn'], world=world, operative_funds=75.0)
        if ok:
            world['policy_feedback'] = (msg, (245, 180, 50))
            try:
                from worldview_engine import ticker_push
                ticker_push(world, world['turn'], 'POLICY', f"🗡️ {msg}", (200, 100, 100))
            except ImportError:
                pass
        else:
            world['policy_feedback'] = (msg, (240, 60, 60))

    # City Public Works Commission
    elif act_id in ('build_farm', 'build_granary', 'build_sawmill', 'build_workshop', 'build_workhouse'):
        b_map = {'build_farm': 'farm', 'build_granary': 'granary', 'build_sawmill': 'sawmill', 'build_workshop': 'workshop', 'build_workhouse': 'workhouse'}
        b_type = b_map[act_id]
        owner = getattr(target, 'owner_nation', None)
        if owner is not None:
            intent = BuildIntent(owner.name, target.name, b_type, submitted_turn=world['turn'])
            owner.submit_intent(intent, world['turn'])
            tiles_by_name = {r.name: r for r in world.get('tiles', [])}
            nations_by_name = {n.name: n for n in world.get('nations', [])}
            ok, msg = intent.execute(tiles_by_name, nations_by_name, world['turn'])
            if ok:
                try:
                    from worldview_engine import ticker_push
                    ticker_push(world, world['turn'], 'CONSTRUCT', msg, (245, 180, 50))
                except ImportError:
                    pass
            world['policy_feedback'] = (msg, GREEN if ok else RED)

    # City Feudal Enclosure Decree
    elif act_id == 'city_enclose_plot':
        reg, plot_id = target
        from enclosure import execute_enclosure
        ok, msg, events = execute_enclosure(reg, plot_id, world['turn'])
        if ok:
            try:
                from worldview_engine import ticker_push
                ticker_push(world, world['turn'], 'ENCLOSURE', msg, (230, 140, 70))
            except ImportError:
                pass
        world['policy_feedback'] = (msg, (230, 140, 70) if ok else RED)

    # City Pastoral Conversion Decree ("sheep eat men")
    elif act_id == 'city_convert_pasture':
        reg, plot_id = target
        plot = reg.tenure.find_plot(plot_id) if hasattr(reg, 'tenure') else None
        if plot:
            new_type = 'pasture' if getattr(plot, 'production_type', 'arable') != 'pasture' else 'arable'
            reg.tenure.convert_production_type(plot_id, new_type, world['turn'])
            state_msg = f"Plot {plot.display_name} converted to {new_type.upper()} on {reg.name}."
            if new_type == 'pasture':
                state_msg += " Labor demand slashed by 75% ('sheep eat men')."
            world['policy_feedback'] = (state_msg, (210, 180, 100))
            try:
                from worldview_engine import ticker_push
                ticker_push(world, world['turn'], 'LAND_USE', state_msg, (210, 180, 100))
            except ImportError:
                pass
        else:
            world['policy_feedback'] = (f"Plot {plot_id} not found.", RED)

    # City Phase 3: Chemical & Ecological Mandates
    elif act_id == 'city_mandate_fertilizer':
        cur = getattr(target, 'use_fertilizer', False)
        target.use_fertilizer = not cur
        state = "Mandated" if not cur else "Banned"
        world['policy_feedback'] = (f"Synthetic Fertilizers {state} in {target.name}.", GREEN if not cur else (240, 180, 80))
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'POLICY', f"Synthetic Fertilizers {state} in {target.name}.", (120, 220, 140))

    elif act_id == 'city_mandate_pesticides':
        cur = getattr(target, 'use_pesticides', False)
        target.use_pesticides = not cur
        state = "Mandated" if not cur else "Banned"
        world['policy_feedback'] = (f"Chemical Pesticides {state} in {target.name}.", GREEN if not cur else (240, 180, 80))
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'POLICY', f"Chemical Pesticides {state} in {target.name}.", (120, 220, 140))

    elif act_id == 'city_toggle_public_healthcare':
        cur = getattr(target, 'public_healthcare_decree', False)
        target.public_healthcare_decree = not cur
        state = "Enacted (Subsidized)" if not cur else "Repealed (Private Out-of-Pocket)"
        world['policy_feedback'] = (f"Public Healthcare Decree {state} in {target.name}.", GREEN if not cur else (240, 180, 80))
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'HEALTH', f"Healthcare {state} in {target.name}.", (100, 210, 255))

    # Province Actions
    elif act_id == 'prov_equalization_grant':
        tiles = getattr(target, 'tiles', [])
        prov_gov = getattr(target, 'gov', None)
        cost = 200.0
        on_hand = prov_gov.agent.cash if prov_gov and hasattr(prov_gov, 'agent') else 0.0
        affordable = on_hand >= cost
        funded = affordable and bool(tiles)
        trace = _trace_policy_funding(
            world, target, act_id, cost=cost, source_cash=on_hand,
            affordable=affordable, funded=funded,
            reason=('treasury_and_recipient_available' if funded else
                    'no_province_tiles' if affordable else
                    'treasury_cash_below_cost'),
            recipient_count=len(tiles),
            decision_inputs={'recipient_selection_rule':
                             'minimum local bank capital plus municipal treasury cash',
                             'tile_asset_scores': [
                                 {'tile': tile.name,
                                  'bank_capital': float(tile.bank.capital)
                                  if getattr(tile, 'bank', None) else 0.0,
                                  'municipal_cash': float(tile.gov.agent.cash)
                                  if (getattr(tile, 'gov', None)
                                      and hasattr(tile.gov, 'agent')) else 0.0}
                                 for tile in tiles]})
        if on_hand >= cost:
            if tiles:
                poorest = min(tiles, key=lambda r: (r.bank.capital if getattr(r, 'bank', None) else 0.0) + (r.gov.agent.cash if getattr(r, 'gov', None) and hasattr(r.gov, 'agent') else 0.0))
                payer_before = float(prov_gov.agent.cash)
                payee_before = float(poorest.gov.agent.cash)
                prov_gov.agent.cash -= cost
                poorest.gov.agent.cash += cost
                payer_event_id, payee_event_id = _trace_provincial_internal_transfer(
                    world, target, poorest, action_id=act_id, trace=trace,
                    amount=cost, payer_before=payer_before,
                    payer_after=float(prov_gov.agent.cash),
                    payee_before=payee_before,
                    payee_after=float(poorest.gov.agent.cash))
                _emit_policy_outcome(
                    trace, target, act_id, success=True,
                    reason='grant_paid_to_lowest_liquid_assets_tile',
                    before=payer_before, after=float(prov_gov.agent.cash),
                    cause_event_ids=[event_id for event_id in
                                     (trace.get('event_id'), payer_event_id,
                                      payee_event_id) if event_id] or None,
                    inputs={'amount_paid': cost,
                            'recipient_tile': poorest.name,
                            'recipient_selection_score':
                            (float(poorest.bank.capital)
                             if getattr(poorest, 'bank', None) else 0.0)
                            + payee_before,
                            'recipient_cash_before': payee_before,
                            'recipient_cash_after': float(poorest.gov.agent.cash)})
                world['policy_feedback'] = (f"Disbursed $200 grant from province treasury to {poorest.name}!", GREEN)
                from worldview_engine import ticker_push
                ticker_push(world, world['turn'], 'POLICY', f"Equalization grant: $200 transferred from {target.name} to {poorest.name}.", (130, 220, 160))
            else:
                _emit_policy_outcome(
                    trace, target, act_id, success=False,
                    reason='no_province_tiles', before=float(on_hand),
                    after=float(on_hand),
                    cause_event_ids=[trace['event_id']] if trace.get('event_id') else None,
                    inputs={'amount_requested': cost, 'tile_count': 0})
        else:
            _emit_policy_outcome(
                trace, target, act_id, success=False,
                reason='insufficient_provincial_treasury',
                before=float(on_hand), after=float(on_hand),
                cause_event_ids=[trace['event_id']] if trace.get('event_id') else None,
                inputs={'amount_requested': cost, 'cash_shortfall': cost - on_hand})
            world['policy_feedback'] = (f"Insufficient provincial treasury funds (${on_hand:.1f} < $200.0).", RED)
    elif act_id == 'prov_harmonize_taxes':
        tiles = getattr(target, 'tiles', [])
        if tiles:
            avg_tax = sum(r.gov.tax_rate for r in tiles) / len(tiles)
            for r in tiles:
                r.gov.tax_rate = avg_tax
            world['policy_feedback'] = (f"Harmonized province taxes at {avg_tax*100:.1f}%.", GREEN)
    elif act_id == 'prov_standardize_routes':
        world['policy_feedback'] = (f"Standardized transport routes for {target.name}!", (200, 230, 150))
    elif act_id == 'prov_soil_conservation':
        prov_gov = getattr(target, 'gov', None)
        cost = 150.0
        on_hand = prov_gov.agent.cash if prov_gov and hasattr(prov_gov, 'agent') else 0.0
        tiles = list(getattr(target, 'tiles', []))
        funded = on_hand >= cost
        trace = _trace_policy_funding(
            world, target, act_id, cost=cost, source_cash=on_hand,
            affordable=funded, funded=funded,
            reason='treasury_funds_soil_conservation' if funded
            else 'treasury_cash_below_cost', recipient_count=len(tiles),
            decision_inputs={'fertility_before_by_tile': {
                tile.name: float(getattr(tile, 'soil_fertility', 1.0))
                for tile in tiles}})
        if on_hand >= cost:
            payer_before = float(prov_gov.agent.cash)
            prov_gov.agent.cash -= cost
            expenditure_event_id = _trace_provincial_policy_expenditure(
                world, target, act_id, trace, amount=cost,
                payer_before=payer_before,
                payer_after=float(prov_gov.agent.cash),
                service='soil_conservation')
            fertility_changes = []
            trace_region = _policy_trace_region(world, target)
            for region in tiles:
                before_fertility = float(getattr(region, 'soil_fertility', 1.0))
                region.soil_fertility = min(1.50, before_fertility + 0.10)
                after_fertility = float(region.soil_fertility)
                fertility_changes.append({'tile': region.name,
                                          'before': before_fertility,
                                          'after': after_fertility})
                if before_fertility == after_fertility or trace_region is None:
                    continue
                from run_trace import emit
                emit(
                    trace_region, kind='provincial_soil_conservation_outcome',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'tile', 'id': region.name},
                    metric_id='ecology.soil_fertility',
                    before=before_fertility, after=after_fertility, unit='ratio',
                    inputs={'operation_id': trace.get('operation_id'),
                            'turn': int(world.get('turn', 0)),
                            'province': target.name,
                            'funding_event_id': trace.get('event_id'),
                            'expenditure_event_id': expenditure_event_id},
                    cause_event_ids=([expenditure_event_id]
                                     if expenditure_event_id else None))
            _emit_policy_outcome(
                trace, target, act_id, success=True,
                reason='policy_cost_paid_and_land_changes_applied' if tiles
                else 'policy_cost_paid_without_province_tiles',
                before=payer_before, after=float(prov_gov.agent.cash),
                cause_event_ids=[event_id for event_id in
                                 (trace.get('event_id'), expenditure_event_id)
                                 if event_id] or None,
                inputs={'amount_paid': cost, 'tile_count': len(tiles),
                        'fertility_changes': fertility_changes})
            world['policy_feedback'] = (f"Soil conservation grant deployed across {target.name}!", (130, 220, 160))
            from worldview_engine import ticker_push
            ticker_push(world, world['turn'], 'POLICY', f"Soil conservation subsidies funded in {target.name} (+10% Fertility).", (130, 220, 160))
        else:
            _emit_policy_outcome(
                trace, target, act_id, success=False,
                reason='insufficient_provincial_treasury',
                before=float(on_hand), after=float(on_hand),
                cause_event_ids=[trace['event_id']] if trace.get('event_id') else None,
                inputs={'amount_requested': cost, 'cash_shortfall': cost - on_hand,
                        'fertility_unchanged': True})
            world['policy_feedback'] = ("Insufficient provincial treasury funds.", RED)

    # Nation Actions
    elif act_id.startswith('nat_tax_'):
        rate = float(act_id.split('_')[-1]) / 100.0
        for r in target.tiles:
            r.gov.tax_rate = rate
        world['policy_feedback'] = (f"National statutory tax set to {rate*100:.0f}%.", GREEN)
    elif act_id.startswith('nat_tariff_'):
        rate = float(act_id.split('_')[-1]) / 100.0
        for r in target.tiles:
            r.gov.import_tariff_rate = rate
        world['policy_feedback'] = (f"National import tariff set to {rate*100:.0f}%.", (160, 210, 255))
    elif act_id == 'nat_enact_ubi':
        for r in target.tiles:
            r.gov.ubi_enabled = True
        world['policy_feedback'] = ("Enacted Nationwide Universal Basic Income (UBI)!", GREEN)
    elif act_id == 'nat_toggle_imm':
        cur = getattr(target.tiles[0].gov, 'immigration_enabled', False)
        for r in target.tiles:
            r.gov.immigration_enabled = not cur
        world['policy_feedback'] = (f"Immigration policy: {'Open Borders' if not cur else 'Closed'}.", (160, 210, 255))
    elif act_id.startswith('nat_adjust_shift_'):
        delta = float(act_id.split('_')[-1])
        from labor_politics import adjust_workday_hours
        ok, msg = adjust_workday_hours(target, delta)
        world['policy_feedback'] = (msg, GREEN if ok else RED)
        try:
            from worldview_engine import ticker_push
            ticker_push(world, world['turn'], 'LABOR', msg, (240, 140, 80) if delta > 0 else (120, 220, 140))
        except ImportError:
            pass
    elif act_id == 'nat_ten_hour_act':
        from labor_politics import enact_ten_hour_act
        ok, msg = enact_ten_hour_act(target)
        world['policy_feedback'] = (msg, GREEN if ok else RED)
    elif act_id == 'nat_safety_mandate':
        from labor_politics import enact_factory_safety_act
        ok, msg = enact_factory_safety_act(target)
        world['policy_feedback'] = (msg, GREEN if ok else RED)
    elif act_id == 'nat_truck_act':
        from labor_politics import enact_anti_truck_act
        ok, msg = enact_anti_truck_act(target)
        world['policy_feedback'] = (msg, GREEN if ok else RED)
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'POLICY', msg, (120, 240, 140))
    elif act_id == 'nat_subsidize_entertainment':
        from labor_politics import subsidize_mass_entertainment
        ok, msg = subsidize_mass_entertainment(target, cost=50.0)
        world['policy_feedback'] = (msg, (70, 195, 235) if ok else RED)
    elif act_id == 'nat_toggle_statute_of_laborers':
        from labor_politics import enact_statute_of_laborers, repeal_statute_of_laborers
        if getattr(target, 'statute_of_laborers', False):
            ok, msg = repeal_statute_of_laborers(target)
        else:
            ok, msg = enact_statute_of_laborers(target, wage_cap=1.20)
        world['policy_feedback'] = (msg, GREEN if ok else RED)
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'POLICY', msg, (240, 200, 100) if ok else RED)
    elif act_id == 'nat_toggle_quarantine':
        from labor_politics import enact_trade_quarantine, repeal_trade_quarantine
        if getattr(target, 'quarantine_active', False):
            ok, msg = repeal_trade_quarantine(target)
        else:
            ok, msg = enact_trade_quarantine(target)
        world['policy_feedback'] = (msg, GREEN if ok else RED)
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'POLICY', msg, (240, 160, 60) if ok else RED)
    elif act_id == 'nat_emergency_granary':
        from labor_politics import emergency_granary_relief
        ok, msg = emergency_granary_relief(target)
        world['policy_feedback'] = (msg, GREEN if ok else RED)
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'POLICY', msg, (120, 240, 140) if ok else RED)
    elif act_id == 'nat_restore_commons':
        restored = False
        for r in target.tiles:
            tenure = getattr(r, 'tenure', None)
            if tenure and tenure.enclosed_plots():
                p = tenure.enclosed_plots()[0]
                tenure.revert_plot_to_commons(p.plot_id, world['turn'])
                restored = True
                r.unrest_level = max(0.0, getattr(r, 'unrest_level', 0.0) - 0.3)
                target.legitimacy = min(1.0, getattr(target, 'legitimacy', 0.5) + 0.08)
                msg = f"Decreed Restoration of Ancestral Commons on {r.name}! (Commons: {tenure.commons_access*100:.0f}%)"
                world['policy_feedback'] = (msg, GREEN)
                from worldview_engine import ticker_push
                ticker_push(world, world['turn'], 'POLICY', msg, (120, 240, 140))
                break
        if not restored:
            world['policy_feedback'] = ("No enclosed plots remain to restore to commons.", (245, 180, 50))
    elif act_id == 'nat_martial_law':
        active_units = [u for u in getattr(target, 'military_units', []) if getattr(u, 'soldiers', 0) > 0]
        if not active_units:
            world['policy_feedback'] = ("Cannot declare Martial Law: Nation has no active standing military units!", (240, 60, 60))
            return
        from popular_resistance import get_popular_resistance_manager
        res_mgr = get_popular_resistance_manager()
        cleared_strikes = 0
        cleared_barricades = 0
        for r in target.tiles:
            st = res_mgr.get_state(r.name)
            if st.has_barricades:
                st.has_barricades = False
                cleared_barricades += 1
            if st.is_general_strike:
                st.is_general_strike = False
                cleared_strikes += 1
            r.unrest_level = max(0.0, getattr(r, 'unrest_level', 0.0) - 0.5)
            apply_repression(r, world['turn'], cost_legitimacy=0.10)
        msg = f"Martial Law declared! Army dismantled {cleared_barricades} barricades and suppressed {cleared_strikes} strikes."
        world['policy_feedback'] = (msg, (240, 80, 80))
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'MILITARY', msg, (240, 80, 80))
    elif act_id == 'nat_recapitalize_banks':
        from banking_policy import recapitalize_domestic_banks
        ok, msg = recapitalize_domestic_banks(target)
        world['policy_feedback'] = (msg, GREEN if ok else RED)
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'BANKING', msg, (120, 240, 150) if ok else (240, 80, 80))
    elif act_id == 'nat_deposit_haircut':
        from banking_policy import enact_deposit_bailin_haircut
        ok, msg = enact_deposit_bailin_haircut(target)
        world['policy_feedback'] = (msg, (245, 180, 50) if ok else RED)
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'BANKING', msg, (245, 180, 50) if ok else (240, 80, 80))
    elif act_id == 'nat_fertilizer_rationing':
        cur_val = any(getattr(r, 'fertilizer_rationing', False) for r in getattr(target, 'tiles', []))
        new_val = not cur_val
        for r in getattr(target, 'tiles', []):
            r.fertilizer_rationing = new_val
        status_s = "ENACTED (50% Consumption Cut)" if new_val else "REPEALED (Normal Intensive Consumption)"
        msg = f"Fertilizer Rationing Decree: {status_s} across {target.name}."
        world['policy_feedback'] = (msg, (245, 180, 50) if new_val else (120, 240, 150))
        from worldview_engine import ticker_push
        ticker_push(world, world['turn'], 'POLICY', msg, (245, 180, 50) if new_val else (120, 240, 150))
    elif act_id == 'nat_subsidize_guano_import':
        _execute_national_guano_subsidy(world, target)

    # Frontier Actions
    elif act_id == 'frontier_expedition':
        from frontier_policies import launch_frontier_expedition
        launch_frontier_expedition(world, target)
    elif act_id == 'frontier_pioneer_grant':
        _execute_frontier_pioneer_grant(world, target)
