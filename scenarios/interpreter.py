"""Generic Scenario Template Interpreter orchestrating declarative gameplay from JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from scenarios.effects import apply_declarative_effects
from scenarios.evaluator import evaluate_condition, evaluate_metric
from scenarios.modules.base import BaseDynamicModule
from scenarios.modules.coercion import CoercionModule
from scenarios.modules.debt import DebtClaimsModule
from scenarios.modules.politics import PoliticsModule
from scenarios.modules.relief import ReliefModule
from scenarios.modules.capitalism import CapitalismModule
from scenarios.schema import ActionResponse, ActionSpec, ScenarioSpec, load_scenario_spec


MODULE_REGISTRY = {
    'debt': DebtClaimsModule,
    'naval_coercion': CoercionModule,
    'politics': PoliticsModule,
    'relief': ReliefModule,
    'capitalism': CapitalismModule,
}


class ScenarioInterpreter:
    """Orchestrates scenario gameplay, dynamic modules, branching reactions, and debriefs."""

    def __init__(self, spec: ScenarioSpec):
        self.spec = spec
        self.modules: Dict[str, BaseDynamicModule] = {}
        self._init_modules()

    @classmethod
    def from_file(cls, path: str | Path) -> ScenarioInterpreter:
        spec = load_scenario_spec(path)
        return cls(spec)

    def _init_modules(self) -> None:
        """Instantiate configured dynamics modules."""
        for mod_name, mod_config in self.spec.modules.items():
            mod_cls = MODULE_REGISTRY.get(mod_name)
            if mod_cls:
                self.modules[mod_name] = mod_cls(mod_name, mod_config)

    def bind_context(self, world: dict) -> Dict[str, Any]:
        """Resolve abstract role bindings against active world objects."""
        context: Dict[str, Any] = {
            'world': world,
            'state': world.setdefault('scenario_state', {}),
            'turn': int(world.get('turn', 0)),
        }

        # Resolve actor roles
        actor_roles = self.spec.roles.get('actors', {})
        nations = world.get('nations', [])
        player_name = world.get('player_nation_name')

        player = next((n for n in nations if n.name == player_name), None)
        if player is None and nations:
            player = nations[0]
        context['player_nation'] = player
        context['$player'] = player

        creditors = []
        for role_key, role_spec in actor_roles.items():
            if role_key == '$player':
                continue
            filt = role_spec.get('filter', {})
            name = filt.get('name')
            matched = next((n for n in nations if n.name == name), None)
            if matched:
                context[role_key] = matched
                if 'creditor' in role_key:
                    creditors.append(matched)
                if 'aggressor' in role_key:
                    context['aggressor_nation'] = matched
        context['creditor_nations'] = creditors
        if not context.get('aggressor_nation') and creditors:
            context['aggressor_nation'] = creditors[0]

        return context

    def initialize_scenario(self, world: dict) -> None:
        """Initialize scenario state, modules, and public tracking."""
        state = world.setdefault('scenario_state', {})
        state['scenario_id'] = self.spec.id
        state['horizon_turns'] = self.spec.meta.get('horizon_turns', 20)
        state['creditor_confidence'] = 0.60
        state['fiscal_autonomy'] = 1.00
        state['creditor_reactions'] = []
        state['actions_taken'] = []
        state['ending'] = None

        context = self.bind_context(world)
        for module in self.modules.values():
            module.initialize(world, context)

    def advance_turn(self, world: dict, turn: int, ticker_push: Optional[Callable] = None) -> None:
        """Advance scenario turn lifecycle, step dynamics, and resolve due reactions."""
        state = world.setdefault('scenario_state', {})
        if state.get('ending'):
            return

        state['turns_remaining'] = max(0, int(self.spec.meta.get('horizon_turns', 20)) - turn)
        context = self.bind_context(world)

        # 1. Advance all active dynamic simulation modules
        for module in self.modules.values():
            module.advance_turn(world, turn, ticker_push, context)
            if world.get('scenario_warning_modal'):
                return

        # 2. Advance delayed reaction queue
        self._advance_reactions(world, turn, ticker_push, context)
        if world.get('scenario_warning_modal'):
            return

        # 3. Check terminal outcomes and horizon expiration
        self._evaluate_outcomes(world, turn, ticker_push, context)

    def _advance_reactions(self, world: dict, turn: int, ticker_push, context: Dict[str, Any]) -> None:
        """Resolve queued actor reactions whose delay countdown has completed."""
        state = world.setdefault('scenario_state', {})
        for pending in state.get('creditor_reactions', []):
            if pending.get('status') != 'pending' or int(pending.get('due_turn', 0)) > turn:
                continue

            action_id = pending['action_id']
            branch = self.spec.branches.get(action_id)
            if not branch:
                pending['status'] = 'resolved'
                continue

            # Evaluate conditional branching if specified on branch
            eval_ctx = self._build_eval_context(world, context)
            if branch.condition:
                cond_met = evaluate_condition(branch.condition, eval_ctx)
                reaction = branch.reaction if cond_met else branch.fallback_reaction
            else:
                reaction = branch.reaction

            if not reaction:
                pending['status'] = 'resolved'
                continue

            ok, msg = apply_declarative_effects(world, reaction.effects, context)
            headline = reaction.headline
            body = reaction.body
            feedback = f"{headline}. {body}"
            world['scenario_feedback'] = feedback
            state['creditor_feedback'] = feedback

            if ticker_push:
                ticker_push(world, turn, 'CREDITOR', feedback, (225, 178, 87))

            if reaction.responses:
                # Halt game with interactive player modal
                pending['status'] = 'awaiting_response'
                world['playing'] = False
                world['scenario_warning_modal'] = {
                    'kind': 'creditor_reaction',
                    'action_id': action_id,
                    'headline': headline,
                    'body': body,
                    'responses': [{'id': r.id, 'label': r.label} for r in reaction.responses],
                }
                return
            else:
                pending['status'] = 'resolved'

    def get_available_actions(self, world: dict) -> List[Dict[str, Any]]:
        """Return list of actions with current validity and tooltips."""
        context = self.bind_context(world)
        eval_ctx = self._build_eval_context(world, context)
        turn = int(world.get('turn', 0))
        last_turn = world.get('scenario_state', {}).get('last_action_turn')
        already_acted = (last_turn == turn)

        results = []
        for action in self.spec.actions:
            enabled = not already_acted
            if action.precondition:
                enabled = enabled and evaluate_condition(action.precondition, eval_ctx)
            if action.requires_cash > 0:
                enabled = enabled and (eval_ctx.get('player_cash', 0.0) >= action.requires_cash)

            results.append({
                'id': action.id,
                'title': action.title,
                'category': action.category,
                'enabled': enabled,
                'tooltip': action.tooltip,
            })
        return results

    def apply_action(self, world: dict, action_id: str) -> Tuple[bool, str]:
        """Apply a player scenario decision, apply effects, and schedule delayed reactions."""
        state = world.setdefault('scenario_state', {})
        turn = int(world.get('turn', 0))

        if state.get('ending'):
            return False, "The scenario campaign has already ended."
        if state.get('last_action_turn') == turn:
            return False, "Only one major decision may be taken per turn."

        action = next((a for a in self.spec.actions if a.id == action_id), None)
        if not action:
            return False, f"Unknown action: {action_id}"

        context = self.bind_context(world)
        eval_ctx = self._build_eval_context(world, context)

        if action.precondition and not evaluate_condition(action.precondition, eval_ctx):
            return False, "Preconditions for this action are not met."

        ok, msg = apply_declarative_effects(world, action.effects, context)
        if not ok:
            return False, msg

        state['last_action_turn'] = turn
        feedback = action.feedback or f"Ordered: {action.title}."
        world['scenario_feedback'] = feedback
        state.setdefault('actions_taken', []).append({
            'turn': turn,
            'action': action_id,
            'message': feedback,
        })
        try:
            from economy.true_cost_ledger import get_decision_tracker
            get_decision_tracker().record_decision(
                action_id, title=action.title, turn=turn, category=action.category
            )
        except Exception:
            pass

        # Queue reaction if defined in branch tree
        branch = self.spec.branches.get(action_id)
        if branch:
            state.setdefault('creditor_reactions', []).append({
                'action_id': action_id,
                'due_turn': turn + branch.delay_turns,
                'status': 'pending',
            })

        return True, feedback

    def resolve_reaction_response(self, world: dict, response_id: str) -> Tuple[bool, str]:
        """Resolve player choice to an awaiting creditor reaction modal."""
        state = world.setdefault('scenario_state', {})
        pending = next((item for item in state.get('creditor_reactions', [])
                        if item.get('status') == 'awaiting_response'), None)
        if not pending:
            return False, "No creditor reaction is awaiting a response."

        branch = self.spec.branches.get(pending['action_id'])
        if not branch:
            return False, "Branch not found."

        all_responses = list(branch.reaction.responses)
        if branch.fallback_reaction:
            all_responses.extend(branch.fallback_reaction.responses)
        response = next((r for r in all_responses if r.id == response_id), None)
        if not response:
            return False, f"Invalid response: {response_id}"

        context = self.bind_context(world)
        ok, msg = apply_declarative_effects(world, response.effects, context)
        if not ok:
            return False, msg

        pending['status'] = 'resolved'
        world['scenario_warning_modal'] = None
        feedback = f"Creditor reply: {response.label}."
        world['scenario_feedback'] = feedback
        state.setdefault('actions_taken', []).append({
            'turn': int(world.get('turn', 0)),
            'action': response_id,
            'message': feedback,
        })
        try:
            from economy.true_cost_ledger import get_decision_tracker
            get_decision_tracker().record_decision(
                response_id, title=response.label, turn=int(world.get('turn', 0)), category='response'
            )
        except Exception:
            pass
        return True, feedback

    def evaluate_pressures(self, world: dict) -> List[Dict[str, Any]]:
        """Compute values for the UI headline pressure cards."""
        context = self.bind_context(world)
        eval_ctx = self._build_eval_context(world, context)
        results = []
        for pressure in self.spec.pressures:
            val = evaluate_metric(pressure.metric, eval_ctx, default=0.0)
            formatted = pressure.status_format.format(value=val)
            results.append({
                'id': pressure.id,
                'title': pressure.title,
                'target': pressure.target,
                'value': val,
                'display': formatted,
            })
        return results

    def evaluate_outcome(self, world: dict) -> Optional[Dict[str, Any]]:
        """Return debrief dictionary if scenario has ended, otherwise None."""
        debrief = world.get('scenario_state', {}).get('debrief')
        if not debrief:
            return None
        res = dict(debrief)
        res['id'] = debrief.get('outcome_id')
        return res

    def _evaluate_outcomes(self, world: dict, turn: int, ticker_push, context: Dict[str, Any]) -> None:
        """Check outcome predicates and conclude scenario if triggered or horizon reached."""
        state = world.setdefault('scenario_state', {})
        eval_ctx = self._build_eval_context(world, context)
        horizon = int(self.spec.meta.get('horizon_turns', 20))

        # Check explicit outcome rules in order
        for outcome in self.spec.outcomes:
            if outcome.when and evaluate_condition(outcome.when, eval_ctx):
                self._conclude_scenario(world, outcome.id, outcome.title, outcome.summary, eval_ctx)
                return

        # Check campaign horizon end
        if turn >= horizon:
            self._conclude_scenario(world, 'horizon_reached', 'Campaign Concluded',
                                    'The campaign reached the end of its planning horizon.', eval_ctx)

    def _conclude_scenario(self, world: dict, outcome_id: str, title: str, summary: str, eval_ctx: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        state['ending'] = outcome_id
        world['playing'] = False

        debrief = {
            'outcome_id': outcome_id,
            'title': title,
            'summary': summary,
            'metrics': eval_ctx,
        }

        try:
            from economy.true_cost_ledger import get_true_cost_ledger, get_decision_tracker
            p_nation = world.get('player_nation_name') or 'Kingdom'
            debrief['corporate_externalities'] = get_true_cost_ledger().get_national_corporate_externalities(p_nation, world)
            debrief['decisions_externalities'] = get_decision_tracker().get_all_entries_dict()
        except Exception:
            pass

        state['debrief'] = debrief

    def _build_eval_context(self, world: dict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten world and scenario metrics for easy AST evaluation."""
        state = world.get('scenario_state', {})
        player = context.get('player_nation')
        turn = int(world.get('turn', 0))

        eval_ctx = {
            'turn': turn,
            'state': state,
            'horizon_turns': int(self.spec.meta.get('horizon_turns', 20)),
            'creditor_confidence': float(state.get('creditor_confidence', 0.6)),
            'fiscal_autonomy': float(state.get('fiscal_autonomy', 1.0)),
            'payment_status': state.get('payment_status', 'unpaid'),
            'scheduled_remittance': float(state.get('scheduled_remittance', 0.0)),
            'due_turn': int(state.get('payment_window_turn', 6)),
        }

        if player:
            eval_ctx['legitimacy'] = float(getattr(player, 'legitimacy', 0.5))
            eval_ctx['player_cash'] = float(getattr(getattr(player, 'government', None), 'agent', None).cash) if getattr(player, 'government', None) else 0.0
            tiles = list(player.tiles)
            eval_ctx['unrest'] = sum(float(getattr(t, 'unrest_level', 0.0)) for t in tiles) / max(1, len(tiles))

        # Gather metrics from dynamic modules
        for mod in self.modules.values():
            eval_ctx.update(mod.snapshot_metrics(world, context))

        return eval_ctx
