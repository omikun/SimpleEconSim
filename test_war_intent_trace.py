"""Causal trace coverage for active-war AI intent choices."""

import json
import unittest
from types import SimpleNamespace

from ai_nation import NationPolicyAI
from diplomacy import DiplomacySystem
from intents import (MoveArmyIntent, ProposePeaceIntent,
                     RespondPeaceIntent)
from metric_catalog import METRICS, TRACE_INSTRUMENTED
from war_logic import PeaceOffer, WarAim


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'war-ai-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Tile:
    def __init__(self, name):
        self.name = name
        self.neighbors = {}
        self.owner_nation = None


class Nation:
    def __init__(self, name, tile, soldiers, *, food=100):
        self.name = name
        self.tiles = [tile]
        tile.owner_nation = self
        self.military_units = [SimpleNamespace(
            unit_id=f'{name}-army', region_name=tile.name,
            soldiers=soldiers, strength=float(soldiers),
            wage_per_soldier=1.0, food_per_soldier=0.1,
            morale=1.0, is_garrison=False)]
        self.cash = 100.0
        self.government = SimpleNamespace(food_inventory=food)
        self.regime_type = 'autocracy'
        self.ruling_faction = name

    def treasury(self):
        return {'total': self.cash}


def _world(*, traced=True, food=100):
    alpha_tile, beta_tile = Tile('Alpha-tile'), Tile('Beta-tile')
    alpha_tile.neighbors[beta_tile.name] = beta_tile
    beta_tile.neighbors[alpha_tile.name] = alpha_tile
    alpha = Nation('Alpha', alpha_tile, 30, food=food)
    beta = Nation('Beta', beta_tile, 5)
    trace = MemoryTrace()
    clock = {'turn': 2, 'phase': 'strategy', 'next': 1}
    if traced:
        alpha_tile._run_trace = trace
        alpha_tile._collective_trace_clock = clock
    diplomacy = DiplomacySystem()
    diplomacy.declare_war(
        'Alpha', 'Beta', t=1, aim=WarAim('border_tile', 'Beta-tile'),
        nations={'Alpha': alpha, 'Beta': beta})
    war = diplomacy.get_war('Alpha', 'Beta')
    return alpha, beta, war, trace


def _intent_signature(intent):
    if intent is None:
        return None
    if isinstance(intent, MoveArmyIntent):
        return (type(intent).__name__, intent.unit_id,
                intent.from_region, intent.to_region)
    if isinstance(intent, RespondPeaceIntent):
        return (type(intent).__name__, intent.proposer_name, intent.accept)
    if isinstance(intent, ProposePeaceIntent):
        return (type(intent).__name__, intent.target_nation_name)
    return type(intent).__name__


class WarIntentTraceTests(unittest.TestCase):
    def test_attack_forecast_and_selected_move_are_explained(self):
        outcomes = []
        traced_rows = None
        for traced in (False, True):
            alpha, beta, war, trace = _world(traced=traced)
            intent = NationPolicyAI(alpha).choose_war_intent(war, beta, t=2)
            outcomes.append(_intent_signature(intent))
            if traced:
                traced_rows = trace.rows
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(outcomes[0][0], 'MoveArmyIntent')
        event = next(row for row in traced_rows
                     if row.get('metric_id') == 'war.ai_intent')
        self.assertEqual(event['inputs']['reason'],
                         'best_attack_forecast_exceeds_cost_margin')
        self.assertEqual(event['after']['to'], 'Beta-tile')
        self.assertEqual(event['inputs']['attack_margin_threshold'], 0.15)
        self.assertGreater(
            event['inputs']['selected_forecast_margin'], 0.15)
        self.assertEqual(event['inputs']['forecast_count'], 1)

    def test_peace_response_links_to_acceptance_calculation(self):
        outcomes = []
        traced_rows = None
        for traced in (False, True):
            alpha, beta, war, trace = _world(traced=traced, food=0)
            war.pending_offer = PeaceOffer(
                proposer='Beta', recipient='Alpha', turn=1)
            intent = NationPolicyAI(alpha).choose_war_intent(war, beta, t=2)
            outcomes.append(_intent_signature(intent))
            if traced:
                traced_rows = trace.rows
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertIsInstance(intent, RespondPeaceIntent)
        self.assertTrue(intent.accept)
        evaluation = next(row for row in traced_rows
                          if row.get('metric_id') ==
                          'war.peace_offer_evaluation')
        choice = next(row for row in traced_rows
                      if row.get('metric_id') == 'war.ai_intent')
        self.assertTrue(evaluation['after'])
        self.assertEqual(evaluation['record_class'], 'calculation')
        self.assertEqual(evaluation['inputs']['supply_runway_turns'], 0.0)
        self.assertIn(evaluation['event_id'], choice['cause_event_ids'])
        self.assertEqual(choice['after']['accept'], True)

    def test_unsecured_regime_change_penalty_can_reject_peace(self):
        alpha, beta, war, trace = _world(food=0)
        war.sides['Alpha'].aims = [WarAim('regime_change')]
        war.pending_offer = PeaceOffer(
            proposer='Beta', recipient='Alpha', turn=1)
        intent = NationPolicyAI(alpha).choose_war_intent(war, beta, t=2)
        self.assertIsInstance(intent, RespondPeaceIntent)
        self.assertFalse(intent.accept)
        evaluation = next(row for row in trace.rows
                          if row.get('metric_id') ==
                          'war.peace_offer_evaluation')
        self.assertTrue(evaluation['inputs'][
            'unsecured_regime_change_penalty_applied'])
        self.assertEqual(
            evaluation['inputs']['accept_value_components'][
                'unsecured_regime_change'], -1.25)

    def test_declaration_turn_gate_and_peace_offer_gate_are_traced(self):
        alpha, beta, war, trace = _world()
        ai = NationPolicyAI(alpha)
        self.assertIsNone(ai.choose_war_intent(war, beta, t=1))
        gate = next(row for row in trace.rows
                    if row.get('metric_id') == 'war.ai_intent')
        self.assertEqual(gate['inputs']['reason'],
                         'post_declaration_response_turn')

        war.pending_offer = PeaceOffer(
            proposer='Beta', recipient='Alpha', turn=2)
        self.assertIsNone(ai.choose_war_intent(war, beta, t=2))
        pending = [row for row in trace.rows
                   if row.get('metric_id') == 'war.ai_intent'][-1]
        self.assertEqual(pending['inputs']['reason'],
                         'offer_response_turn_not_elapsed')

    def test_secured_aim_records_the_peace_proposal_choice(self):
        alpha, beta, war, trace = _world()
        alpha.tiles.append(beta.tiles.pop())
        alpha.tiles[-1].owner_nation = alpha
        war.sides['Alpha'].posture = 'culminated'
        intent = NationPolicyAI(alpha).choose_war_intent(war, beta, t=2)
        self.assertIsInstance(intent, ProposePeaceIntent)
        event = next(row for row in trace.rows
                     if row.get('metric_id') == 'war.ai_intent')
        self.assertEqual(event['inputs']['reason'],
                         'aim_secured_or_offensive_culminated')
        self.assertTrue(event['inputs']['aim_secured'])

    def test_metrics_are_registered_and_instrumented(self):
        for metric_id in ('war.ai_intent', 'war.peace_offer_evaluation'):
            self.assertIn(metric_id, METRICS)
            self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
