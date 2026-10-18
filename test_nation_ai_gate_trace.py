"""Causal coverage for nation AI gates and final decision links."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai_nation import NationPolicyAI
from diplomacy import DiplomacySystem
from goods import Goods
from intents import EncloseCommonsIntent, MoveArmyIntent
from war_logic import WarAim, WarRecord, WarSide


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'nation-ai-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Tile:
    def __init__(self, name, owner=None, *, grain=1.0, wool=2.0,
                 protest=0.0):
        self.name = name
        self.owner_nation = owner
        self.neighbors = {}
        self.agents = []
        self.recipes = {
            Goods.food: {'price': grain},
            Goods.wool: {'price': wool}}
        self.construction_projects = []
        self.buildings = []
        self.tenure = None
        self.protest_energy_log = [protest]
        self.food_enclosure_moratorium = False


class Nation:
    def __init__(self, name, cash=20.0, soldiers=0):
        self.name = name
        self.cash = cash
        self.regime_type = 'autocracy'
        self.ruling_faction = name
        self.tiles = []
        self.intents = []
        self.military_units = []
        self.government = SimpleNamespace(food_inventory=100.0)
        if soldiers:
            self.military_units.append(SimpleNamespace(
                unit_id=f'{name}-army', region_name=f'{name}-tile',
                soldiers=soldiers, strength=float(soldiers),
                wage_per_soldier=1.0, food_per_soldier=0.1,
                morale=1.0, is_garrison=False))

    def treasury(self):
        return {'total': self.cash}

    def submit_intent(self, intent, turn):
        intent.submitted_turn = turn
        self.intents.append(intent)


class Tenure:
    def __init__(self, plots):
        self.plots = plots

    def feudal_plots(self):
        return list(self.plots)


def _trace_nation(nation, tiles, *, traced):
    nation.tiles = tiles
    for tile in tiles:
        tile.owner_nation = nation
    trace = MemoryTrace()
    if traced and tiles:
        tiles[0]._run_trace = trace
        tiles[0]._collective_trace_clock = {
            'turn': 5, 'phase': 'strategy', 'next': 1}
    return trace


def _run_turn(nation, tiles, nations, diplomacy, turn, *, traced,
              food_responses=None):
    trace = _trace_nation(nation, tiles, traced=traced)
    ai = NationPolicyAI(nation)
    with patch('food_security.enact_nation_food_response',
               return_value=food_responses or []):
        intents = ai.decide_turn(turn, tiles, nations, diplomacy)
    return intents, trace


def _intent_signature(intents):
    return [(type(intent).__name__, getattr(intent, 'region_name', None),
             getattr(intent, 'building_type', None),
             getattr(intent, 'plot_id', None)) for intent in intents]


class NationAIGateTraceTests(unittest.TestCase):
    def test_silent_defense_subsidy_public_works_and_enclosure_gates(self):
        nation = Nation('Alpha', cash=20.0)
        no_tenure = Tile('NoTenure', nation)
        no_plots = Tile('NoPlots', nation)
        no_plots.tenure = Tenure([])
        high_protest = Tile('HighProtest', nation, protest=4.5)
        high_protest.tenure = Tenure([SimpleNamespace(plot_id='high')])
        low_prices = Tile('LowPrices', nation, grain=1.0, wool=2.0)
        low_prices.tenure = Tenure([SimpleNamespace(plot_id='low')])
        missing_lord = Tile('MissingLord', nation, grain=1.6)
        missing_lord.tenure = Tenure([SimpleNamespace(
            plot_id='missing-lord', lord_id=7, fraction=0.1)])
        poor_lord = Tile('PoorLord', nation, grain=1.6)
        poor_lord.tenure = Tenure([SimpleNamespace(
            plot_id='poor-lord', lord_id=8, fraction=0.1)])
        poor_lord.agents = [SimpleNamespace(id=8, cash=1.0)]
        tiles = [no_tenure, no_plots, high_protest, low_prices,
                 missing_lord, poor_lord]
        diplomacy = DiplomacySystem()
        _intents, trace = _run_turn(
            nation, tiles, [nation], diplomacy, 4, traced=True)
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'nation_ai_decision')
        considered = decision['inputs']['considered']

        defense = next(row for row in considered
                       if row.get('candidate') == 'recruit_defense')
        self.assertEqual(defense['reason_code'],
                         'vulnerability_below_threshold')
        self.assertFalse(defense['treasury_gate'])
        subsidy = next(row for row in considered
                       if row.get('candidate') == 'contractor_subsidy')
        self.assertEqual(subsidy['reason_code'],
                         'treasury_below_threshold')
        public_works = next(row for row in considered
                            if row.get('candidate') == 'public_works')
        self.assertEqual(public_works['reason_code'],
                         'treasury_below_threshold')

        enclosure_rows = [row for row in considered
                          if row.get('candidate') == 'enclose_commons'
                          and row.get('tile')]
        reasons = {row['tile']: row['reason_code']
                   for row in enclosure_rows}
        self.assertEqual(reasons, {
            'NoTenure': 'no_tenure_system',
            'NoPlots': 'no_feudal_plots',
            'HighProtest': 'protest_energy_at_or_above_threshold',
            'LowPrices': 'market_and_schedule_gates_not_met',
            'MissingLord': 'lord_not_found',
            'PoorLord': 'lord_cannot_afford_charter_fee'})

    def test_enclosure_selection_and_land_use_are_trace_neutral(self):
        outcomes = []
        traced_rows = None
        for traced in (False, True):
            nation = Nation('Alpha', cash=20.0)
            tile = Tile('PastureFrontier', nation, grain=1.0, wool=2.0)
            plot = SimpleNamespace(plot_id='pasture-plot', lord_id=7,
                                   fraction=0.1, production_type='arable')
            tile.tenure = Tenure([plot])
            tile.agents = [SimpleNamespace(id=7, cash=20.0)]
            intents, trace = _run_turn(
                nation, [tile], [nation], DiplomacySystem(), 5,
                traced=traced)
            outcomes.append((_intent_signature(intents), plot.production_type))
            if traced:
                traced_rows = trace.rows
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(outcomes[0][0][0][0], 'EncloseCommonsIntent')
        self.assertEqual(outcomes[0][1], 'pasture')
        decision = next(row for row in traced_rows
                        if row.get('kind') == 'nation_ai_decision')
        selected = next(row for row in decision['inputs']['considered']
                        if row.get('candidate') == 'enclose_commons'
                        and row.get('reason_code') == 'enclosure_selected')
        self.assertEqual(selected['selected_production_type'], 'pasture')
        self.assertEqual(selected['pasture_ratio_threshold'], 1.8)
        self.assertTrue(selected['scheduled_turn_gate'])

    def test_contractor_projects_record_cash_and_stall_reasons(self):
        nation = Nation('Alpha', cash=150.0)
        tile = Tile('Works', nation)
        tile.construction_projects = [
            SimpleNamespace(project_id='no-contractor', status='in_progress',
                            contractor=None),
            SimpleNamespace(project_id='funded-contractor', status='in_progress',
                            contractor=SimpleNamespace(cash=10.0)),
            SimpleNamespace(project_id='stalled-project', status='stalled',
                            contractor=None)]
        intents, trace = _run_turn(
            nation, [tile], [nation], DiplomacySystem(), 4, traced=True)
        self.assertEqual([type(intent).__name__ for intent in intents],
                         ['SubsidizeContractorIntent'])
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'nation_ai_decision')
        projects = {row.get('project'): row for row in
                    decision['inputs']['considered']
                    if row.get('candidate') == 'contractor_subsidy'
                    and row.get('project')}
        self.assertEqual(projects['no-contractor']['reason_code'],
                         'contractor_missing')
        self.assertEqual(projects['funded-contractor']['reason_code'],
                         'contractor_cash_sufficient')
        self.assertEqual(projects['stalled-project']['reason_code'],
                         'project_stalled')
        self.assertTrue(projects['stalled-project']['feasible'])

    def test_public_works_records_complete_and_busy_tile_gates(self):
        nation = Nation('Alpha', cash=500.0)
        complete = Tile('Complete', nation)
        complete.buildings = [SimpleNamespace(name='turnpike_road'),
                              SimpleNamespace(name='barge_canal')]
        busy = Tile('Busy', nation)
        busy.construction_projects = [SimpleNamespace(
            project_id='busy-project', status='in_progress', contractor=None)]
        _intents, trace = _run_turn(
            nation, [complete, busy], [nation], DiplomacySystem(), 4,
            traced=True)
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'nation_ai_decision')
        rows = {row.get('tile'): row for row in decision['inputs']['considered']
                if row.get('candidate') == 'public_works'
                and row.get('tile')}
        self.assertEqual(rows['Complete']['reason_code'],
                         'turnpike_and_canal_present')
        self.assertEqual(rows['Busy']['reason_code'],
                         'active_construction_project')
        self.assertFalse(rows['Complete']['feasible'])
        self.assertFalse(rows['Busy']['feasible'])

    def test_food_emergency_blocks_subsidy_infrastructure_and_enclosure(self):
        nation = Nation('Alpha', cash=200.0)
        tile = Tile('Capital', nation)
        _intents, trace = _run_turn(
            nation, [tile], [nation], DiplomacySystem(), 4, traced=True,
            food_responses=[{'emergency': True, 'tile': tile.name}])
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'nation_ai_decision')
        candidates = [row for row in decision['inputs']['considered']
                      if row.get('candidate') in {
                          'contractor_subsidy', 'public_works',
                          'enclose_commons'}]
        food_blocked = [row for row in candidates
                        if row.get('reason_code') == 'food_emergency']
        self.assertEqual({row['candidate'] for row in food_blocked}, {
            'contractor_subsidy', 'public_works', 'enclose_commons'})

    def test_final_nation_decision_links_to_war_ai_choice(self):
        alpha, beta = Nation('Alpha', cash=100.0, soldiers=30), Nation(
            'Beta', cash=100.0, soldiers=5)
        alpha_tile, beta_tile = Tile('Alpha-tile', alpha), Tile('Beta-tile', beta)
        alpha_tile.neighbors[beta_tile.name] = beta_tile
        beta_tile.neighbors[alpha_tile.name] = alpha_tile
        alpha.tiles, beta.tiles = [alpha_tile], [beta_tile]
        alpha.military_units[0].region_name = alpha_tile.name
        beta.military_units[0].region_name = beta_tile.name
        side_a = WarSide(aims=[WarAim('border_tile', beta_tile.name)],
                         initial_tiles={alpha_tile.name},
                         initial_enemy_tiles={beta_tile.name})
        side_b = WarSide(aims=[WarAim('defend')],
                         initial_tiles={beta_tile.name},
                         initial_enemy_tiles={alpha_tile.name})
        war = WarRecord(('Alpha', 'Beta'), 1,
                        {'Alpha': side_a, 'Beta': side_b})
        diplomacy = DiplomacySystem()
        key = diplomacy._pair_key('Alpha', 'Beta')
        diplomacy.active_wars.add(key)
        diplomacy.war_records[key] = war
        diplomacy.set_relation('Alpha', 'Beta', 0.0)
        trace = _trace_nation(alpha, [alpha_tile], traced=True)
        beta.tiles = [beta_tile]
        ai = NationPolicyAI(alpha)
        with patch('food_security.enact_nation_food_response',
                   return_value=[]):
            intents = ai.decide_turn(2, [alpha_tile, beta_tile],
                                     [alpha, beta], diplomacy)
        self.assertTrue(any(isinstance(intent, MoveArmyIntent)
                            for intent in intents))
        war_choice = next(row for row in trace.rows
                          if row.get('metric_id') == 'war.ai_intent')
        diplomacy_choice = next(row for row in trace.rows
                                if row.get('metric_id') ==
                                'diplomacy.ai_candidates')
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'nation_ai_decision')
        self.assertIn(war_choice['event_id'], decision['cause_event_ids'])
        self.assertIn(diplomacy_choice['event_id'], decision['cause_event_ids'])
        self.assertIn(war_choice['event_id'], decision['inputs'][
            'war_ai_decision_event_ids'])


if __name__ == '__main__':
    unittest.main()
