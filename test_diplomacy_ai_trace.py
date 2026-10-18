import json
import unittest

from ai_nation import NationPolicyAI
from army import MilitaryUnit
from diplomacy import DiplomacySystem
from nation import Nation
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _nation(name, *, regime='autocracy', soldiers=0):
    nation = Nation(name, currency=name, regime_type=regime,
                    initial_cash=0.0, register=False)
    tile = Region(f'{name}-tile', t=0, number_of_agents=0)
    nation.add_tile(tile)
    if soldiers:
        nation.military_units.append(MilitaryUnit(
            unit_id=f'{name}-unit', nation_name=name,
            region_name=tile.name, soldiers=soldiers))
    return nation, tile


def _intent_signature(intents):
    return [(type(intent).__name__,
             getattr(intent, 'target_nation_name', None),
             getattr(intent, 'treaty_type', None))
            for intent in intents]


class DiplomacyAITraceTests(unittest.TestCase):
    def test_candidate_trace_explains_all_diplomacy_gates(self):
        alpha, alpha_tile = _nation('Alpha', soldiers=60)
        beta, _ = _nation('Beta', soldiers=1)
        gamma, _ = _nation('Gamma', regime='democracy', soldiers=100)
        delta, _ = _nation('Delta', regime='democracy', soldiers=40)
        trace = MemoryTrace()
        clock = {'turn': 4, 'phase': 'strategy', 'next': 1}
        alpha_tile._run_trace = trace
        alpha_tile._collective_trace_clock = clock
        diplomacy = DiplomacySystem()
        diplomacy.set_relation('Alpha', 'Beta', 0.05)
        diplomacy.set_relation('Alpha', 'Gamma', -0.8)
        diplomacy.set_relation('Alpha', 'Delta', -0.8)
        self.assertTrue(diplomacy.propose_treaty(
            'Alpha', 'Beta', 'non_aggression', t=3)[0])

        ai = NationPolicyAI(alpha, personality={
            'expansionist': 0.6, 'militarism': 0.5, 'diplomatic': 0.7,
            'risk_tolerance': 0.4, 'loyalty': 0.4})
        intents = ai.evaluate_diplomacy(
            [alpha, beta, gamma, delta], diplomacy, t=4)

        event = next(row for row in trace.rows
                     if row.get('kind') == 'nation_diplomacy_evaluation')
        self.assertEqual(event['metric_id'], 'diplomacy.ai_candidates')
        candidates = event['inputs']['candidate_evaluations']
        gamma_threat = next(row for row in candidates
                            if row['policy'] == 'dominant_threat'
                            and row['target'] == 'Gamma')
        self.assertTrue(gamma_threat['eligible'])
        self.assertTrue(gamma_threat['selected'])
        beta_alliance = next(row for row in candidates
                             if row['policy'] == 'counterbalance_alliance'
                             and row['target'] == 'Beta')
        self.assertEqual(beta_alliance['reason'],
                         'first_eligible_counterbalance_partner')
        beta_trade = next(row for row in candidates
                          if row['policy'] == 'trade_pact'
                          and row['target'] == 'Beta')
        self.assertTrue(beta_trade['selected'])
        beta_betrayal = next(row for row in candidates
                             if row['policy'] == 'treaty_betrayal'
                             and row['target'] == 'Beta')
        self.assertEqual(beta_betrayal['reason'],
                         'partner_weak_low_loyalty_and_relation_below_0_3')
        delta_war = next(row for row in candidates
                         if row['policy'] == 'ideological_war'
                         and row['target'] == 'Delta')
        self.assertEqual(delta_war['reason'],
                         'hostile_relation_regime_clash_and_strength_advantage')
        self.assertEqual(event['inputs']['proposed_intent_count'], 4)
        recorded_intents = event['inputs']['proposed_intents']
        self.assertEqual([(row['intent_type'], row['target'], row['treaty_type'])
                          for row in recorded_intents],
                         _intent_signature(intents))
        self.assertEqual([row['target'] for row in recorded_intents],
                         ['Beta', 'Beta', 'Beta', 'Delta'])

    def test_nation_decision_links_to_diplomacy_evaluation_and_trace_is_behavior_neutral(self):
        alpha, alpha_tile = _nation('Alpha')
        beta, _ = _nation('Beta')
        trace = MemoryTrace()
        alpha_tile._run_trace = trace
        alpha_tile._collective_trace_clock = {
            'turn': 1, 'phase': 'strategy', 'next': 1}
        diplomacy = DiplomacySystem()
        diplomacy.set_relation('Alpha', 'Beta', 0.2)

        traced_ai = NationPolicyAI(alpha)
        traced_result = traced_ai.decide_turn(
            1, [alpha_tile], [alpha, beta], diplomacy)

        evaluation = next(row for row in trace.rows
                          if row.get('kind') == 'nation_diplomacy_evaluation')
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'nation_ai_decision')
        self.assertEqual(decision['cause_event_ids'], [evaluation['event_id']])
        self.assertIn('diplomacy.ai_candidates', {
            row['metric_id'] for row in trace.rows if row.get('metric_id')})

        plain_alpha, plain_tile = _nation('Alpha')
        plain_beta, _ = _nation('Beta')
        plain_diplomacy = DiplomacySystem()
        plain_diplomacy.set_relation('Alpha', 'Beta', 0.2)
        plain_result = NationPolicyAI(plain_alpha).decide_turn(
            1, [plain_tile], [plain_alpha, plain_beta], plain_diplomacy)
        self.assertEqual(_intent_signature(traced_result),
                         _intent_signature(plain_result))


if __name__ == '__main__':
    unittest.main()
