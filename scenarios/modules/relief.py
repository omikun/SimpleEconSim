"""Generalized resource, public reserve stocks, and famine relief dynamics."""

from __future__ import annotations

from typing import Any, Dict
from scenarios.modules.base import BaseDynamicModule


class ReliefModule(BaseDynamicModule):
    """Manages public grain/food inventories, hunger monitoring, and harvest shocks."""

    def initialize(self, world: dict, context: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        player = context.get('player_nation')
        if not player:
            return

        initial_relief_turns = int(self.config.get('relief_stock_turns', 4))
        relief_rate = int(self.config.get('relief_units_per_turn', 30))
        initial_stock = initial_relief_turns * relief_rate

        state['relief_units_per_turn'] = relief_rate
        state['public_maize_stock_units'] = initial_stock
        state['domestic_grain_priority'] = False

        if hasattr(player, 'government'):
            player.government.food_inventory = initial_stock

    def advance_turn(self, world: dict, turn: int, ticker_push, context: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        player = context.get('player_nation')
        if not player:
            return

        # Synchronize public stock tracking
        if hasattr(player, 'government'):
            state['public_maize_stock_units'] = getattr(player.government, 'food_inventory', 0)

        # Apply opening harvest shocks if defined
        shocks = self.config.get('harvest_shocks', [])
        for shock in shocks:
            if shock.get('turn') == turn and f"shock_{turn}" not in state.setdefault('events_fired', []):
                state['events_fired'].append(f"shock_{turn}")
                if ticker_push:
                    ticker_push(world, turn, 'SCENARIO', shock.get('message', 'A harvest shock impacts food yields.'), (230, 174, 88))

    def snapshot_metrics(self, world: dict, context: Dict[str, Any]) -> Dict[str, Any]:
        player = context.get('player_nation')
        if not player:
            return {'hunger_rate': 0.0, 'public_stock': 0}

        households = [a for tile in player.tiles for a in getattr(tile, 'agents', [])
                      if getattr(a, 'alive', True) and not getattr(a, 'is_government', False)
                      and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_trader', False)]
        hungry = sum(1 for a in households if getattr(a, 'hungry_steps', 0) > 0)
        hunger_rate = (hungry / max(1, len(households))) if households else 0.0

        return {
            'hunger_rate': hunger_rate,
            'public_stock': getattr(getattr(player, 'government', None), 'food_inventory', 0),
        }
