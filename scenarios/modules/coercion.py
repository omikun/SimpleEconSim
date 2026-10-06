"""Generalized coercion, gunboat diplomacy, and expedition dynamics."""

from __future__ import annotations

from typing import Any, Dict
from scenarios.modules.base import BaseDynamicModule


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
                crisis['stage'] = 'ultimatum'
                world['playing'] = False
                world['scenario_warning_modal'] = {
                    'kind': 'naval_ultimatum',
                    'ratio': crisis['squadron_strength'] / max(1.0, crisis['battery_strength']),
                }
                if ticker_push:
                    ticker_push(world, turn, 'WAR', "Foreign squadron arrives off port with an ultimatum.", (230, 90, 80))

        # 2. Blockade upkeep and protest pressure
        elif stage == 'blockaded':
            upkeep = float(crisis.get('upkeep_per_turn', 8.0))
            if aggressor and getattr(getattr(aggressor, 'government', None), 'agent', None):
                aggressor_cash = float(aggressor.government.agent.cash)
                if aggressor_cash >= upkeep:
                    aggressor.government.agent.cash -= upkeep
                else:
                    # Aggressor runs out of cash, withdraws
                    crisis['stage'] = 'withdrawn'
                    crisis['withdrawal_cause'] = 'insolvency'
                    if ticker_push:
                        ticker_push(world, turn, 'NAVAL', "Foreign fleet withdraws due to lack of supply.", (120, 220, 170))

    def snapshot_metrics(self, world: dict, context: Dict[str, Any]) -> Dict[str, Any]:
        crisis = world.get('scenario_state', {}).get('naval_crisis', {})
        return {
            'naval_stage': crisis.get('stage', 'none'),
            'squadron_strength': crisis.get('squadron_strength', 0.0),
            'battery_strength': crisis.get('battery_strength', 0.0),
        }
