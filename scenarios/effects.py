"""Generic effect dispatcher executing declarative scenario effects with strict value conservation."""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

from typing import Any, Dict, List, Optional, Tuple
from goods import Goods


def _clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(val)))


def apply_declarative_effects(world: dict, effects: Dict[str, Any], context: Dict[str, Any]) -> Tuple[bool, str]:
    """Apply bounded scenario effects against simulation state.
    
    Guarantees strict conservation of currency and inventory.
    """
    player = context.get('player_nation')
    if player is None:
        return False, "Player nation is unavailable."

    state = world.setdefault('scenario_state', {})
    gov_cash = float(getattr(getattr(player, 'government', None), 'agent', None).cash) if getattr(player, 'government', None) else 0.0

    # 1. Treasury cost check & deduction (Cash Conservation)
    cost = float(effects.get('treasury_cost', 0.0))
    if cost > 0:
        if gov_cash < cost:
            return False, f"Treasury requires {cost:,.0f} cash units (available: {gov_cash:,.0f})."
        _trace_cash_write = _trace_public_begin(None, player.government.agent)
        player.government.agent.cash -= cost
        _trace_public_finish(_trace_cash_write, 'scenarios/effects:apply_declarative_effects',
                             inputs={"source_writer": 'scenarios/effects.py:apply_declarative_effects:17d25d7639701f88:1'})

        # Credit foreign creditors or recipients if specified
        creditors = context.get('creditor_nations', [])
        if creditors:
            split_amount = cost / len(creditors)
            for cred in creditors:
                _trace_cash_write = _trace_public_begin(None, cred.government.agent)
                cred.government.agent.cash += split_amount
                _trace_public_finish(_trace_cash_write, 'scenarios/effects:apply_declarative_effects',
                                     inputs={"source_writer": 'scenarios/effects.py:apply_declarative_effects:bb6d6a450a13bcc0:1'})

    # 2. Ratio & macro state updates
    if 'confidence_delta' in effects:
        delta = float(effects['confidence_delta'])
        state['creditor_confidence'] = _clamp(state.get('creditor_confidence', 0.5) + delta)

    if 'autonomy_delta' in effects:
        delta = float(effects['autonomy_delta'])
        state['fiscal_autonomy'] = _clamp(state.get('fiscal_autonomy', 1.0) + delta)

    if 'legitimacy_delta' in effects:
        delta = float(effects['legitimacy_delta'])
        player.legitimacy = _clamp(getattr(player, 'legitimacy', 0.5) + delta)

    if 'palace_authority_delta' in effects:
        delta = float(effects['palace_authority_delta'])
        politics = state.setdefault('politics', {})
        politics['palace_authority'] = _clamp(politics.get('palace_authority', 0.8) + delta)

    if 'military_loyalty_delta' in effects:
        delta = float(effects['military_loyalty_delta'])
        politics = state.setdefault('politics', {})
        politics['army_loyalty'] = _clamp(politics.get('army_loyalty', 0.7) + delta)

    if 'nationalist_movement_delta' in effects:
        delta = float(effects['nationalist_movement_delta'])
        politics = state.setdefault('politics', {})
        politics['nationalist_movement'] = _clamp(politics.get('nationalist_movement', 0.2) + delta)

    # 3. Resource & Food Distribution (Inventory Conservation)
    if 'distribute_food' in effects:
        rule = effects['distribute_food']
        max_units = int(rule.get('max_units', 30))
        available_food = int(getattr(player.government, 'food_inventory', 0))
        distribute_qty = min(max_units, available_food)
        if distribute_qty > 0:
            households = [a for tile in player.tiles for a in getattr(tile, 'agents', [])
                          if getattr(a, 'alive', True) and not getattr(a, 'is_government', False)
                          and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_trader', False)]
            # Prioritize hungry households with least cash
            households.sort(key=lambda a: (0 if getattr(a, 'hungry_steps', 0) > 0 else 1,
                                           float(getattr(a, 'cash', 0.0))))
            recipients = households[:distribute_qty]
            for person in recipients:
                person.inv_add(Goods.food, 1)
                if getattr(person, 'hungry_steps', 0) > 0:
                    person.hungry_steps = 0
            player.government.food_inventory -= len(recipients)
            state['public_maize_stock_units'] = player.government.food_inventory

    if 'set_export_fraction' in effects:
        fraction = _clamp(float(effects['set_export_fraction']))
        for tile in player.tiles:
            tile.food_export_fraction = fraction
        state['domestic_grain_priority'] = (fraction < 1.0)

    # 4. Tax rates and unrest adjustments
    if 'set_tax_rate_delta' in effects:
        delta = float(effects['set_tax_rate_delta'])
        for tile in player.tiles:
            if hasattr(tile, 'gov'):
                tile.gov.tax_rate = _clamp(getattr(tile.gov, 'tax_rate', 0.2) + delta, 0.0, 0.60)

    if 'set_unrest_delta' in effects:
        delta = float(effects['set_unrest_delta'])
        for tile in player.tiles:
            tile.unrest_level = _clamp(getattr(tile, 'unrest_level', 0.0) + delta)

    # 5. Debt Service & Bond adjustments
    if 'debt_payment_multiplier' in effects or 'debt_due_in' in effects:
        mult = float(effects.get('debt_payment_multiplier', 1.0))
        due_in = effects.get('debt_due_in')
        turn = int(world.get('turn', 0))
        new_amount = float(state.get('scheduled_remittance', 200.0)) * mult
        state['scheduled_remittance'] = round(new_amount, 2)
        if due_in is not None:
            state['payment_window_turn'] = turn + int(due_in)
        # Update sovereign bond records if active
        try:
            from sovereign_bonds import get_bond_market
            for bond in get_bond_market().bonds:
                if bond.bond_id in state.get('debt_bond_ids', []):
                    bond.principal = round(new_amount / max(1, len(state.get('debt_bond_ids', []))), 2)
                    if due_in is not None:
                        bond.maturity_turn = state['payment_window_turn']
        except Exception:
            pass

    if 'debt_status' in effects:
        new_status = effects['debt_status']
        state['payment_status'] = new_status
        if new_status == 'deferred':
            state['deferral_count'] = int(state.get('deferral_count', 0)) + 1
        elif new_status == 'defaulted':
            state['creditor_confidence'] = 0.0
            player.legitimacy = _clamp(player.legitimacy - 0.15)
            try:
                from sovereign_bonds import get_bond_market
                for bond in get_bond_market().bonds:
                    if bond.bond_id in state.get('debt_bond_ids', []):
                        bond.status = 'defaulted'
            except Exception:
                pass

    if 'levy_per_turn' in effects:
        levy = max(0.0, float(effects['levy_per_turn']))
        state['creditor_levy_per_turn'] = levy

    # 6. Arbitrary scenario state flags
    if 'set_state_flag' in effects:
        for k, v in effects['set_state_flag'].items():
            state[k] = v

    # 7. Capitalist Propagation Dynamics
    if 'execute_transformation_op' in effects:
        from economy.transformation_graph import TransformationGraph
        op_id = effects['execute_transformation_op']
        op = TransformationGraph.get_operator(op_id)
        if op:
            tile = player.tiles[0] if getattr(player, 'tiles', None) else None
            agents = getattr(tile, 'agents', []) if tile else []
            actor = next((a for a in agents if getattr(a, 'is_lord', False) or getattr(a, 'is_trader', False)), agents[0] if agents else None)
            if actor and tile:
                can_run, msg = op.can_agent_execute(actor, tile)
                if can_run:
                    turn = int(world.get('turn', 0))
                    if op.on_execute:
                        op.on_execute(actor, tile, turn)
                else:
                    return False, f"Cannot execute {op.name}: {msg}"

    if 'grant_frontier_charter' in effects:
        from economy.transformation_graph import TransformationGraph
        war_op = TransformationGraph.get_operator('chartered_frontier_conquest')
        tile = player.tiles[0] if getattr(player, 'tiles', None) else None
        agents = getattr(tile, 'agents', []) if tile else []
        actor = next((a for a in agents if getattr(a, 'cash', 0) >= 50.0 or getattr(a, 'is_trader', False)), agents[0] if agents else None)
        if war_op and actor and tile:
            turn = int(world.get('turn', 0))
            res = war_op.on_execute(actor, tile, turn)
            if not res.get('success'):
                return False, res.get('message', 'Frontier conquest failed')

    if 'procure_captive_labor' in effects:
        from economy.transformation_graph import TransformationGraph
        proc_op = TransformationGraph.get_operator('procure_captive_labor')
        tile = player.tiles[0] if getattr(player, 'tiles', None) else None
        agents = getattr(tile, 'agents', []) if tile else []
        actor = next((a for a in agents if len(getattr(a, 'frontier_estates', [])) > 0), None)
        if not actor and agents:
            actor = agents[0]
            if not hasattr(actor, 'frontier_estates') or not actor.frontier_estates:
                actor.frontier_estates = [{'target_region': 'Overseas_Colony', 'primary_commodity': 'cotton', 'captive_labor': 0}]
        if proc_op and actor and tile:
            turn = int(world.get('turn', 0))
            proc_op.on_execute(actor, tile, turn)

    if 'mandate_plantation_labor' in effects:
        from economy.transformation_graph import TransformationGraph
        gang_op = TransformationGraph.get_operator('mandate_plantation_labor_gang')
        tile = player.tiles[0] if getattr(player, 'tiles', None) else None
        agents = getattr(tile, 'agents', []) if tile else []
        actor = next((a for a in agents if any(e.get('captive_labor', 0) >= 3 for e in getattr(a, 'frontier_estates', []))), None)
        if gang_op and actor and tile:
            turn = int(world.get('turn', 0))
            gang_op.on_execute(actor, tile, turn)

    if 'enforce_wage_cap' in effects:
        wage_cap = float(effects.get('enforce_wage_cap', 1.50))
        for tile in getattr(player, 'tiles', []):
            tile.statute_of_laborers = True
            tile.statutory_wage_cap = wage_cap
            for a in getattr(tile, 'agents', []):
                if getattr(a, 'is_corporation', False):
                    a.wage = min(getattr(a, 'wage', wage_cap), wage_cap)

    if 'issue_trade_bill' in effects:
        credit_mgr = state.get('credit_manager_ref')
        if credit_mgr:
            val = float(effects['issue_trade_bill'].get('face_value', 80.0))
            tenor = int(effects['issue_trade_bill'].get('tenor', 4))
            tile = player.tiles[0] if getattr(player, 'tiles', None) else None
            agents = getattr(tile, 'agents', []) if tile else []
            if len(agents) >= 3:
                credit_mgr.issue_bill(agents[0], agents[1], agents[2], val, int(world.get('turn', 0)), tenor)

    if 'incorporate_manufacturing_firm' in effects:
        from agent import Agent, seed_traits
        sector_name = effects['incorporate_manufacturing_firm'].get('sector', 'cloth')
        sector_good = getattr(Goods, sector_name, Goods.cloth)
        wage = float(effects['incorporate_manufacturing_firm'].get('wage', 2.50))
        tile = player.tiles[0] if getattr(player, 'tiles', None) else None
        if tile:
            turn = int(world.get('turn', 0))
            corp = Agent(turn)
            corp.is_corporation = True
            seed_traits(corp)
            corp.output = sector_good
            corp.wage = wage
            corp.max_employees = 15
            _trace_cash_write = _trace_public_begin(None, corp)
            corp.cash = 100.0
            _trace_public_finish(_trace_cash_write, 'scenarios/effects:apply_declarative_effects',
                                 inputs={"source_writer": 'scenarios/effects.py:apply_declarative_effects:1acba03c2a737bbd:1'})
            corp.machinery_level = 1
            tile.agents.append(corp)

    if 'cotton_reserves_delta' in effects:
        delta = int(effects['cotton_reserves_delta'])
        state['cotton_reserves'] = max(0, int(state.get('cotton_reserves', 0)) + delta)
        tile = player.tiles[0] if getattr(player, 'tiles', None) else None
        if tile and delta > 0:
            # Grant cotton inventory to first merchant or agent in tile to preserve physical circulation
            agents = getattr(tile, 'agents', [])
            trader = next((a for a in agents if getattr(a, 'is_trader', False)), agents[0] if agents else None)
            if trader:
                trader.inv_add(Goods.cotton, delta)

    return True, ""
