"""Causal records for the sovereign expansion evaluator."""

import json
import unittest
from types import SimpleNamespace

from ai_nation import NationPolicyAI
from goods import Goods
from metric_catalog import METRICS, TRACE_INSTRUMENTED


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'expansion-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Tile:
    def __init__(self, name, *, owner=None, elevation=1.0, ocean=False,
                 food_price=10.0, wood_price=10.0,
                 food_productivity=1.0, wood_productivity=1.0,
                 population=0):
        self.name = name
        self.owner_nation = owner
        self.elevation = elevation
        self.is_ocean = ocean
        self.neighbors = {}
        self.climate = 'temperate'
        self.agents = [object() for _ in range(population)]
        self.wilderness_pop = 0
        self.recipes = {
            Goods.food: {'price': food_price,
                         'productivity_mult': food_productivity},
            Goods.wood: {'price': wood_price,
                         'productivity_mult': wood_productivity},
            Goods.furniture: {'price': 10.0,
                              'productivity_mult': 1.0}}


class Diplomacy:
    def __init__(self, relation=0.0, allied=False):
        self.relation = relation
        self.allied = allied

    def get_relation(self, _nation, _other):
        return self.relation

    def has_treaty(self, _nation, _other, _treaty):
        return self.allied


def _build(*, traced=True, own_strength=0.0, expansionist=0.9,
           militarism=0.5, relation=0.0, allied=False):
    nation = SimpleNamespace(name='Alpha', tiles=[],
                             military_units=[SimpleNamespace(
                                 strength=own_strength)])
    home = Tile('Home', owner=nation, food_price=16, wood_price=26)
    nation.tiles.append(home)
    trace = MemoryTrace()
    if traced:
        home._run_trace = trace
        home._collective_trace_clock = {
            'turn': 4, 'phase': 'strategy', 'next': 1}
    ai = NationPolicyAI(nation, personality={
        'expansionist': expansionist, 'militarism': militarism,
        'diplomatic': 0.7, 'risk_tolerance': 0.4, 'loyalty': 0.8})
    diplomacy = Diplomacy(relation=relation, allied=allied)
    return nation, home, ai, diplomacy, trace


def _plan_signature(plan):
    if plan is None:
        return None
    return (plan['tile'].name, plan['mode'], plan.get('target_nation'),
            plan['score'])


class NationExpansionTraceTests(unittest.TestCase):
    def test_settlement_trace_explains_terrain_shortages_and_score(self):
        results = []
        traced_rows = None
        for traced in (False, True):
            nation, home, ai, diplomacy, trace = _build(traced=traced)
            candidate = Tile('Frontier', food_productivity=1.5,
                             wood_productivity=1.4, population=4)
            home.neighbors[candidate.name] = candidate
            plan = ai.evaluate_expansion(
                [home, candidate], [nation], diplomacy)
            results.append(_plan_signature(plan))
            if traced:
                traced_rows = trace.rows

        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0:2], ('Frontier', 'settle'))
        event = next(row for row in traced_rows
                     if row.get('metric_id') == 'expansion.ai_candidates')
        candidate_row = event['inputs']['candidate_evaluations'][0]
        self.assertEqual(candidate_row['valuation_score'], 74.0)
        components = candidate_row['valuation_components']
        self.assertEqual(components['bottleneck_relief']['food_bonus'], 18.0)
        self.assertEqual(components['bottleneck_relief']['wood_bonus'], 15.0)
        self.assertAlmostEqual(candidate_row['plan_score'], 64.6)
        self.assertEqual(candidate_row['selection_result'],
                         'highest_score_so_far')
        self.assertEqual(event['after']['tile'], 'Frontier')

    def test_conquest_candidate_records_military_and_diplomatic_gates(self):
        nation, home, ai, diplomacy, trace = _build(
            own_strength=100, relation=-0.5)
        foreign = SimpleNamespace(name='Beta', military_units=[
            SimpleNamespace(strength=10.0)])
        border = Tile('Border', owner=foreign)
        home.neighbors[border.name] = border
        plan = ai.evaluate_expansion([home, border], [nation, foreign],
                                     diplomacy)
        self.assertIsNotNone(plan)
        self.assertEqual(plan['mode'], 'conquest')
        self.assertAlmostEqual(plan['score'], 7.5)
        event = next(row for row in trace.rows
                     if row.get('metric_id') == 'expansion.ai_candidates')
        candidate = event['inputs']['candidate_evaluations'][0]
        self.assertTrue(candidate['military_advantage_gate'])
        self.assertEqual(candidate['diplomatic_fallout_penalty'], 15.0)
        self.assertEqual(candidate['score_formula'],
                         'valuation*militarism*1.5 - diplomatic_fallout')

    def test_owned_ocean_and_submerged_tiles_record_frontier_exclusions(self):
        nation, home, ai, diplomacy, trace = _build()
        ocean = Tile('Ocean', ocean=True)
        submerged = Tile('Submerged', elevation=-0.5)
        home.neighbors.update({home.name: home,
                               ocean.name: ocean,
                               submerged.name: submerged})
        self.assertIsNone(ai.evaluate_expansion(
            [home, ocean, submerged], [nation], diplomacy))
        event = next(row for row in trace.rows
                     if row.get('metric_id') == 'expansion.ai_candidates')
        reasons = {row['candidate_tile']: row['reason']
                   for row in event['inputs']['candidate_gate_evaluations']}
        self.assertEqual(reasons, {'Home': 'already_owned',
                                   'Ocean': 'ocean_tile',
                                   'Submerged': 'below_sea_level'})
        self.assertEqual(event['after']['mode'], None)

    def test_allied_owner_blocks_conquest_even_with_strength_advantage(self):
        nation, home, ai, diplomacy, trace = _build(
            own_strength=100, relation=-0.5, allied=True)
        foreign = SimpleNamespace(name='Beta', military_units=[
            SimpleNamespace(strength=10.0)])
        border = Tile('Border', owner=foreign)
        home.neighbors[border.name] = border
        self.assertIsNone(ai.evaluate_expansion(
            [home, border], [nation, foreign], diplomacy))
        event = next(row for row in trace.rows
                     if row.get('metric_id') == 'expansion.ai_candidates')
        candidate = event['inputs']['candidate_evaluations'][0]
        self.assertEqual(candidate['reason'],
                         'defensive_alliance_blocks_conquest')
        self.assertTrue(candidate['military_advantage_gate'])
        self.assertFalse(candidate['eligible_plan'])

    def test_military_and_minimum_score_gates_reject_candidates(self):
        nation, home, ai, diplomacy, trace = _build(
            own_strength=10, expansionist=0.0)
        foreign = SimpleNamespace(name='Beta', military_units=[
            SimpleNamespace(strength=10.0)])
        border = Tile('Border', owner=foreign)
        wilderness = Tile('Wilderness')
        home.neighbors.update({border.name: border,
                               wilderness.name: wilderness})
        self.assertIsNone(ai.evaluate_expansion(
            [home, border, wilderness], [nation, foreign], diplomacy))
        event = next(row for row in trace.rows
                     if row.get('metric_id') == 'expansion.ai_candidates')
        evaluations = {row['tile']: row for row in
                       event['inputs']['candidate_evaluations']}
        self.assertEqual(evaluations['Border']['reason'],
                         'insufficient_military_advantage')
        self.assertEqual(evaluations['Wilderness']['selection_result'],
                         'below_minimum_plan_score')
        self.assertFalse(evaluations['Wilderness']['eligible_plan'])

    def test_expansion_metric_is_registered(self):
        self.assertIn('expansion.ai_candidates', METRICS)
        self.assertIn('expansion.ai_candidates', TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
