"""Generalized domestic politics, unrest translation, and cabinet coalition dynamics."""

from __future__ import annotations

from typing import Any, Dict
from scenarios.modules.base import BaseDynamicModule


class PoliticsModule(BaseDynamicModule):
    """Manages ruler authority, army loyalty, cabinet transitions, and protest-to-unrest translation."""

    def initialize(self, world: dict, context: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        factions = self.config.get('initial_factions', {})
        state['politics'] = {
            'ruler': self.config.get('ruler', 'Head of State'),
            'governing_coalition': self.config.get('governing_coalition', 'palace'),
            'palace_authority': float(factions.get('palace_authority', 0.85)),
            'army_loyalty': float(factions.get('army_loyalty', 0.75)),
            'nationalist_movement': float(factions.get('nationalist_movement', 0.20)),
            'cabinet_authority': float(factions.get('cabinet_authority', 0.20)),
            'crisis_resolved': False,
            'deposition_resolved': False,
            'officers_paid': False,
            'events': [],
        }

    def advance_turn(self, world: dict, turn: int, ticker_push, context: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        politics = state.setdefault('politics', {})
        player = context.get('player_nation')
        if not player:
            return

        # 1. Translate granular agent tile protest energy into nation unrest
        for tile in player.tiles:
            history = getattr(tile, 'protest_energy_log', [])
            pressure = min(1.0, max(0.0, float(history[-1]) / 10.0)) if history else 0.0
            current = float(getattr(tile, 'unrest_level', 0.0))
            tile.unrest_level = max(0.0, min(1.0, current * 0.75 + pressure * 0.25))

        # 2. Check political transitions defined in module config
        transitions = self.config.get('transitions', [])
        for trans in transitions:
            tid = trans.get('id')
            trigger_expr = trans.get('trigger', '')
            if trigger_expr and not politics.get(f'{tid}_fired', False):
                from scenarios.evaluator import evaluate_condition
                ctx = {
                    'palace_authority': politics.get('palace_authority', 0.8),
                    'army_loyalty': politics.get('army_loyalty', 0.7),
                    'nationalist_movement': politics.get('nationalist_movement', 0.2),
                    'fiscal_autonomy': state.get('fiscal_autonomy', 1.0),
                    'legitimacy': getattr(player, 'legitimacy', 0.5),
                    'turn': turn,
                }
                if evaluate_condition(trigger_expr, ctx):
                    politics[f'{tid}_fired'] = True
                    modal_def = trans.get('modal', {})
                    if modal_def:
                        world['playing'] = False
                        world['scenario_warning_modal'] = modal_def
                        if ticker_push:
                            ticker_push(world, turn, 'POLITICS', modal_def.get('title', 'Political shift occurring.'), (193, 160, 220))
                    break

    def snapshot_metrics(self, world: dict, context: Dict[str, Any]) -> Dict[str, Any]:
        politics = world.get('scenario_state', {}).get('politics', {})
        return {
            'ruler': politics.get('ruler', ''),
            'governing_coalition': politics.get('governing_coalition', ''),
            'palace_authority': politics.get('palace_authority', 0.0),
            'army_loyalty': politics.get('army_loyalty', 0.0),
        }
