"""Generalized coercion, gunboat diplomacy, and expedition dynamics."""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

from typing import Any, Dict
from scenarios.modules.base import BaseDynamicModule


def _emit_trace(world: dict, nation, **event):
    """Emit a scenario record through the first active region trace."""
    candidates = list(getattr(nation, 'tiles', ())) if nation is not None else []
    candidates.extend(world.get('tiles', ()))
    region = next((tile for tile in candidates
                   if (getattr(tile, '_run_trace', None) is not None
                       and getattr(tile, '_collective_trace_clock', None) is not None)),
                  None)
    if region is None:
        return None
    from run_trace import emit
    return emit(region, **event)


class CoercionModule(BaseDynamicModule):
    """Manages naval gunboat escalation, blockades, force balance, and ultimatums."""

    def initialize(self, world: dict, context: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        state['naval_crisis'] = {
            'stage': 'none',
            'reason': '',
            'squadron_strength': float(self.config.get('squadron_strength', 80.0)),
            'battery_strength': float(self.config.get('battery_defense_base', 28.0)),
            'reinforcement_strength': float(self.config.get('battery_reinforcement_strength', 40.0)),
            'upkeep_per_turn': float(self.config.get('upkeep_per_turn', 8.0)),
            'max_protest_energy': float(self.config.get('max_protest_energy', 6.5)),
            'due_turn': -1,
            'historical_parallel': False,
        }

    def advance_turn(self, world: dict, turn: int, ticker_push, context: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        crisis = state.get('naval_crisis', {})
        stage = crisis.get('stage', 'none')

        if stage == 'none' or stage == 'withdrawn':
            return

        aggressor = context.get('aggressor_nation')
        player = context.get('player_nation')

        # 1. Mobilization phase -> Ultimatum
        if stage == 'mobilizing':
            if turn >= crisis.get('due_turn', 0):
                stage_before = stage
                crisis['stage'] = 'ultimatum'
                world['playing'] = False
                force_ratio = (crisis['squadron_strength'] /
                               max(1.0, crisis['battery_strength']))
                world['scenario_warning_modal'] = {
                    'kind': 'naval_ultimatum',
                    'ratio': force_ratio,
                }
                _emit_trace(
                    world, aggressor,
                    kind='scenario_naval_crisis_stage',
                    record_class='outcome', phase='scenario',
                    subject={'type': 'scenario/fleet',
                             'id': getattr(aggressor, 'name', 'unknown')},
                    metric_id='scenario.naval_crisis_stage', unit='stage',
                    before=stage_before, after=crisis['stage'],
                    formula_id='scenario.coercion.ultimatum_due.v1',
                    inputs={'turn': int(turn), 'due_turn': crisis.get('due_turn'),
                            'reason': 'mobilization_due',
                            'squadron_strength': crisis['squadron_strength'],
                            'battery_strength': crisis['battery_strength'],
                            'force_ratio': force_ratio,
                            'historical_parallel': bool(
                                crisis.get('historical_parallel', False))})
                if ticker_push:
                    ticker_push(world, turn, 'WAR', "Foreign squadron arrives off port with an ultimatum.", (230, 90, 80))

        # 2. Blockade upkeep and protest pressure
        elif stage == 'blockaded':
            upkeep = float(crisis.get('upkeep_per_turn', 8.0))
            treasury = getattr(getattr(aggressor, 'government', None), 'agent', None)
            cash_before = float(treasury.cash) if treasury is not None else None
            amount_paid = 0.0
            reason = None
            stage_before = stage
            if aggressor is None or treasury is None:
                reason = 'aggressor_treasury_unavailable'
            elif cash_before >= upkeep:
                _trace_cash_write = _trace_public_begin(None, treasury)
                treasury.cash -= upkeep
                _trace_public_finish(_trace_cash_write, 'scenarios/modules/coercion:CoercionModule.advance_turn',
                                     inputs={"source_writer": 'scenarios/modules/coercion.py:CoercionModule.advance_turn:55de81f3cb121178:1'})
                amount_paid = upkeep
                reason = 'upkeep_paid'
            else:
                # Aggressor runs out of cash, withdraws
                crisis['stage'] = 'withdrawn'
                crisis['withdrawal_cause'] = 'insolvency'
                reason = 'treasury_cash_below_upkeep'

            cash_after = float(treasury.cash) if treasury is not None else None
            scenario_id = world.get('scenario_state', {}).get('scenario_id',
                                                               self.name)
            operation_id = (f'naval-blockade-upkeep:{scenario_id}:{int(turn)}:'
                            f'{getattr(aggressor, "name", "unknown")}')
            currency = (getattr(aggressor, 'currency', None)
                        if aggressor is not None else None) or 'local_currency'
            upkeep_event_id = _emit_trace(
                world, aggressor,
                kind='scenario_blockade_upkeep', record_class='outcome',
                phase='scenario',
                subject={'type': 'scenario/fleet',
                         'id': getattr(aggressor, 'name', 'unknown')},
                metric_id='military.fleet_upkeep', unit=currency,
                before=0.0, after=amount_paid,
                formula_id='scenario.coercion.blockade_upkeep.v1',
                inputs={'operation_id': operation_id, 'turn': int(turn),
                        'scenario_id': scenario_id,
                        'fleet_stage_before': stage_before,
                        'fleet_stage_after': crisis.get('stage', stage_before),
                        'requested_upkeep': upkeep,
                        'amount_paid': amount_paid,
                        'treasury_cash_before': cash_before,
                        'treasury_cash_after': cash_after,
                        'cash_shortfall': max(0.0, upkeep - (cash_before or 0.0)),
                        'reason': reason,
                        'expense_counterparty_modeled': False,
                        'accounting_treatment':
                        'military_operating_expense_sink'})
            if crisis.get('stage') != stage_before:
                _emit_trace(
                    world, aggressor,
                    kind='scenario_naval_crisis_stage',
                    record_class='outcome', phase='scenario',
                    subject={'type': 'scenario/fleet',
                             'id': getattr(aggressor, 'name', 'unknown')},
                    metric_id='scenario.naval_crisis_stage', unit='stage',
                    before=stage_before, after=crisis['stage'],
                    formula_id='scenario.coercion.insolvency_withdrawal.v1',
                    inputs={'operation_id': operation_id, 'turn': int(turn),
                            'reason': 'insolvency',
                            'withdrawal_cause': crisis['withdrawal_cause'],
                            'requested_upkeep': upkeep,
                            'treasury_cash_before': cash_before,
                            'treasury_cash_after': cash_after,
                            'amount_paid': amount_paid},
                    cause_event_ids=[upkeep_event_id]
                    if upkeep_event_id is not None else None)
                if ticker_push:
                    ticker_push(world, turn, 'NAVAL', "Foreign fleet withdraws due to lack of supply.", (120, 220, 170))

    def snapshot_metrics(self, world: dict, context: Dict[str, Any]) -> Dict[str, Any]:
        crisis = world.get('scenario_state', {}).get('naval_crisis', {})
        return {
            'naval_stage': crisis.get('stage', 'none'),
            'squadron_strength': crisis.get('squadron_strength', 0.0),
            'battery_strength': crisis.get('battery_strength', 0.0),
        }
