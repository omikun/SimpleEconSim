"""Causal traces for Guided Egypt's autonomous naval-crisis turn resolution."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from macro.imperialism.manager import get_imperialism_manager
from run_trace import RunTrace, verify
from scenario_geography import create_fleet, move_fleet
from scenario_gunboat import advance_naval_crisis, begin_escalation
from worldview_engine import build_world_view


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'naval-crisis-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, stage='mobilizing', turn=4, traced=True):
    world = build_world_view(scenario_id='egypt_1877')
    world['turn'] = turn
    world['scenario_warning_modal'] = None
    state = world['scenario_state']
    crisis = state['naval_crisis']
    crisis.update(stage=stage, due_turn=turn, mediation_due_turn=turn,
                  last_offer_turn=-1, battery_strength=28.0)
    tile_name = state['geography']['sites']['Alexandria']['tile']
    manager = get_imperialism_manager()
    manager.blockaded_tiles.discard(tile_name)
    manager.blockade_enforcers.pop(tile_name, None)
    trace = MemoryTrace()
    clock = {'turn': turn, 'phase': 'naval_crisis', 'next': 1}
    if traced:
        for tile in world['tiles']:
            tile._run_trace = trace
            tile._collective_trace_clock = clock
    return world, trace


def _fleet_at_alexandria(world, nation):
    create_fleet(world, nation)
    return move_fleet(world, nation, 'Alexandria')


class ScenarioNavalCrisisTraceTests(unittest.TestCase):
    @staticmethod
    def _step(trace):
        rows = [row for row in trace.rows
                if row.get('metric_id') == 'scenario.naval_crisis_step']
        if not rows:
            raise AssertionError('naval crisis step trace was not emitted')
        return rows[-1]

    @staticmethod
    def _decisions(**overrides):
        return {'Britain': 'intervene', 'France': 'abstain', **overrides}

    def test_paid_debt_gate_records_withdrawal_reason(self):
        world, trace = _fixture(stage='blockaded')
        world['scenario_state']['payment_status'] = 'paid'

        advance_naval_crisis(world)

        row = self._step(trace)
        self.assertEqual(row['inputs']['reason'],
                         'debt_settlement_already_completed')
        self.assertEqual(row['inputs']['state_after']['naval_crisis_stage'],
                         'withdrawn')
        withdrawal = next(event for event in trace.rows
                          if event.get('metric_id') == 'scenario.naval_crisis_stage')
        self.assertIn(withdrawal['event_id'], row['cause_event_ids'])

    def test_access_and_british_protest_gates_explain_withdrawal(self):
        no_access, no_access_trace = _fixture(stage='ultimatum')
        alexandria = next(tile for tile in no_access['tiles']
                          if tile.name == no_access['scenario_state']['geography']
                          ['sites']['Alexandria']['tile'])
        alexandria.is_coast = False
        advance_naval_crisis(no_access)
        self.assertEqual(self._step(no_access_trace)['inputs']['reason'],
                         'coastal_access_unavailable')

        unrest, unrest_trace = _fixture(stage='ultimatum')
        unrest['scenario_state']['foreign_reports'] = [
            {'nation': 'Britain', 'energy': 8.0}]
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions()):
            advance_naval_crisis(unrest)
        row = self._step(unrest_trace)
        self.assertEqual(row['inputs']['reason'],
                         'british_domestic_protest_above_limit')
        self.assertEqual(row['inputs']['british_protest_energy'], 8.0)
        self.assertEqual(row['inputs']['state_after']['naval_crisis_stage'],
                         'withdrawn')

    def test_mobilization_due_and_force_gates_are_explained(self):
        waiting, waiting_trace = _fixture(stage='mobilizing', turn=4)
        waiting['scenario_state']['naval_crisis']['due_turn'] = 5
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions()):
            advance_naval_crisis(waiting)
        self.assertEqual(self._step(waiting_trace)['inputs']['reason'],
                         'mobilization_not_yet_due')

        deterred, deterred_trace = _fixture(stage='mobilizing', turn=4)
        deterred['scenario_state']['naval_crisis']['battery_strength'] = 1000.0
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions()):
            advance_naval_crisis(deterred)
        row = self._step(deterred_trace)
        self.assertEqual(row['inputs']['reason'],
                         'coastal_defense_force_gate_failed')
        self.assertLess(row['inputs']['force_ratio'],
                        row['inputs']['minimum_force_ratio'])

    def test_mobilization_funding_failure_links_unpaid_cost_and_withdrawal(self):
        world, trace = _fixture(stage='mobilizing')
        britain = next(n for n in world['nations'] if n.name == 'Britain')
        britain.government.agent.cash = 0.0
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions()), \
             patch('scenario_diplomacy.mobilization_cost', return_value=30.0):
            advance_naval_crisis(world)

        row = self._step(trace)
        self.assertEqual(row['inputs']['reason'],
                         'british_mobilization_funding_failed')
        funding = next(event for event in trace.rows
                       if event.get('metric_id') == 'scenario.household_cost_funding'
                       and event.get('inputs', {}).get('source')
                       == 'british_squadron_mobilization')
        withdrawal = next(event for event in trace.rows
                          if event.get('metric_id') == 'scenario.naval_crisis_stage')
        self.assertIn(funding['event_id'], row['cause_event_ids'])
        self.assertIn(withdrawal['event_id'], row['cause_event_ids'])

    def test_funded_mobilization_records_french_policy_and_arrival(self):
        world, trace = _fixture(stage='mobilizing')
        for nation in world['nations']:
            if nation.name in ('Britain', 'France'):
                nation.government.agent.cash = 10000.0
        decisions = self._decisions(France='join_enforcement')
        with patch('scenario_gunboat.foreign_decisions', return_value=decisions), \
             patch('scenario_diplomacy.mobilization_cost', return_value=30.0):
            advance_naval_crisis(world)

        row = self._step(trace)
        self.assertEqual(row['inputs']['status'], 'ultimatum_issued')
        self.assertEqual(row['inputs']['foreign_decisions'], decisions)
        self.assertTrue(row['inputs']['french_funding_succeeded'])
        self.assertTrue(row['inputs']['french_fleet_joined'])
        self.assertEqual(row['inputs']['state_after']['naval_crisis_stage'],
                         'ultimatum')
        mobilization = next(event for event in trace.rows
                            if event.get('metric_id') == 'military.fleet_mobilization')
        self.assertIn(mobilization['event_id'], row['cause_event_ids'])

    def test_tracing_does_not_change_funded_mobilization(self):
        def run(traced):
            world, _trace = _fixture(stage='mobilizing', traced=traced)
            for nation in world['nations']:
                if nation.name in ('Britain', 'France'):
                    nation.government.agent.cash = 10000.0
            with patch('scenario_gunboat.foreign_decisions',
                       return_value=self._decisions(France='join_enforcement')), \
                 patch('scenario_diplomacy.mobilization_cost', return_value=30.0):
                advance_naval_crisis(world)
            return {
                'stage': world['scenario_state']['naval_crisis']['stage'],
                'crisis': {key: world['scenario_state']['naval_crisis'].get(key)
                           for key in ('french_support', 'french_fleet_joined',
                                       'french_fleet_ever_joined', 'policy_lock')},
                'fleets': world['scenario_state']['geography']['fleets'],
                'cash': {nation.name: float(nation.government.agent.cash)
                         for nation in world['nations']
                         if nation.name in ('Britain', 'France')},
                'warning': world.get('scenario_warning_modal'),
                'playing': world.get('playing'),
            }

        self.assertEqual(run(True), run(False))

    def test_upkeep_failure_and_french_squadron_loss_are_distinguished(self):
        no_funds, no_funds_trace = _fixture(stage='ultimatum')
        _fleet_at_alexandria(no_funds, 'Britain')
        britain = next(n for n in no_funds['nations'] if n.name == 'Britain')
        britain.government.agent.cash = 0.0
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions()):
            advance_naval_crisis(no_funds)
        row = self._step(no_funds_trace)
        self.assertEqual(row['inputs']['reason'], 'british_fleet_upkeep_unaffordable')
        self.assertEqual(row['inputs']['state_after']['naval_crisis_stage'],
                         'withdrawn')

        french_short, french_trace = _fixture(stage='ultimatum')
        _fleet_at_alexandria(french_short, 'Britain')
        _fleet_at_alexandria(french_short, 'France')
        france = next(n for n in french_short['nations'] if n.name == 'France')
        france.government.agent.cash = 0.0
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions(France='join_enforcement')):
            advance_naval_crisis(french_short)
        row = self._step(french_trace)
        self.assertEqual(row['inputs']['status'], 'ultimatum_waiting_for_player')
        self.assertFalse(row['inputs']['french_funding_succeeded'])
        self.assertNotIn('France', row['inputs']['state_after']['fleets'])
        french_withdrawal = next(event for event in french_trace.rows
                                 if event.get('kind') ==
                                 'naval_french_squadron_supply_failure')
        self.assertIn(french_withdrawal['event_id'], row['cause_event_ids'])

    def test_mediation_acceptance_and_rejection_explain_exact_gates(self):
        accepted, accepted_trace = _fixture(stage='mediation', turn=6)
        _fleet_at_alexandria(accepted, 'Britain')
        egypt = next(n for n in accepted['nations'] if n.name == 'Egypt')
        egypt.government.agent.cash = 100000.0
        accepted_state = accepted['scenario_state']
        accepted_state['diplomatic_crisis'].update(
            french_policy='abstain',
            ottoman_offer={'turn': 5, 'payment_fraction': 0.5, 'status': 'pending'})
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions()):
            advance_naval_crisis(accepted)
        accepted_row = self._step(accepted_trace)
        self.assertEqual(accepted_row['inputs']['reason'],
                         'britain_accepted_and_egypt_paid_half_claim')
        self.assertEqual(accepted_row['inputs']['state_after']['naval_crisis_stage'],
                         'withdrawn')
        debt_rows = [event for event in accepted_trace.rows
                     if event.get('kind') == 'caisse_ottoman_mediation']
        self.assertTrue(debt_rows)
        self.assertTrue({event['event_id'] for event in debt_rows}.issubset(
            set(accepted_row['cause_event_ids'])))

        rejected, rejected_trace = _fixture(stage='mediation', turn=6)
        _fleet_at_alexandria(rejected, 'Britain')
        rejected_state = rejected['scenario_state']
        rejected_state['foreign_reports'] = [
            {'nation': 'Britain', 'energy': 0.0}]
        rejected_state['diplomatic_crisis'].update(
            french_policy='join_enforcement',
            ottoman_offer={'turn': 5, 'payment_fraction': 0.5, 'status': 'pending'})
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions(France='join_enforcement')):
            advance_naval_crisis(rejected)
        rejected_row = self._step(rejected_trace)
        self.assertEqual(rejected_row['inputs']['reason'],
                         'britain_rejected_due_to_funded_french_coalition')
        self.assertEqual(rejected_state['diplomatic_crisis']['ottoman_offer']['status'],
                         'rejected')
        self.assertEqual(rejected_row['inputs']['state_after']['naval_crisis_stage'],
                         'ultimatum')

        unaffordable, unaffordable_trace = _fixture(stage='mediation', turn=6)
        _fleet_at_alexandria(unaffordable, 'Britain')
        egypt = next(n for n in unaffordable['nations'] if n.name == 'Egypt')
        egypt.government.agent.cash = 0.0
        unaffordable['scenario_state']['diplomatic_crisis'].update(
            french_policy='abstain',
            ottoman_offer={'turn': 5, 'payment_fraction': 0.5, 'status': 'pending'})
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions()):
            advance_naval_crisis(unaffordable)
        unaffordable_row = self._step(unaffordable_trace)
        self.assertEqual(unaffordable_row['inputs']['reason'],
                         'egypt_treasury_below_half_claim')
        self.assertLess(unaffordable_row['inputs']['egypt_treasury_before'],
                        unaffordable_row['inputs']['required_payment'])

    def test_blockade_advance_links_to_expedition_step(self):
        world, trace = _fixture(stage='blockaded', turn=6)
        self.assertTrue(_fleet_at_alexandria(world, 'Britain'))
        world['scenario_state']['campaign']['expedition'].update(
            stage='none', landing_due_turn=6)
        with patch('scenario_gunboat.foreign_decisions',
                   return_value=self._decisions()):
            advance_naval_crisis(world)

        row = self._step(trace)
        self.assertEqual(row['inputs']['status'], 'expedition_advanced')
        expedition = next(event for event in trace.rows
                          if event.get('metric_id') == 'scenario.expedition_step')
        self.assertIn(expedition['event_id'], row['cause_event_ids'])
        self.assertEqual(row['inputs']['state_after']['warning_modal']['kind'],
                         'landing_warning')

    def test_naval_crisis_step_serializes_and_verifies(self):
        world, _memory_trace = _fixture(stage='blockaded', traced=False)
        world['scenario_state']['payment_status'] = 'paid'
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / 'naval-crisis.ctr'
            recorder = RunTrace(trace_path, 'naval-crisis-test')
            clock = {'turn': int(world['turn']),
                     'phase': 'naval_crisis', 'next': 1}
            for tile in world['tiles']:
                tile._run_trace = recorder
                tile._collective_trace_clock = clock

            advance_naval_crisis(world)

            row = recorder.query(metric_id='scenario.naval_crisis_step')['events'][0]
            self.assertEqual(row['inputs']['reason'],
                             'debt_settlement_already_completed')
            self.assertGreater(verify(trace_path)['rows'], 1)

    def test_escalation_trigger_records_cause_deadline_and_chapter_transition(self):
        world, trace = _fixture(stage='none', turn=5)
        tile = world['tiles'][0]
        upstream = trace.emit(tile._collective_trace_clock,
                              kind='creditor_response_resolved',
                              metric_id='scenario.creditor_effects')

        begin_escalation(world, 'contest_customs_claim',
                         cause_event_ids=[upstream])

        row = next(event for event in trace.rows
                   if event.get('metric_id') == 'scenario.naval_escalation')
        self.assertTrue(row['inputs']['success'])
        self.assertEqual(row['inputs']['gate_reason'],
                         'escalation_trigger_accepted')
        self.assertEqual(row['inputs']['stage_before'], 'none')
        self.assertEqual(row['inputs']['stage_after'], 'mobilizing')
        self.assertEqual(row['inputs']['due_turn'], 6)
        self.assertTrue(row['inputs']['chapter_transition_started'])
        self.assertIn(upstream, row['cause_event_ids'])

    def test_creditor_response_effect_links_into_escalation_trigger(self):
        from scenario_situation import resolve_creditor_response
        world, trace = _fixture(stage='none', turn=5)
        world['scenario_state']['creditor_reactions'] = [{
            'action_id': 'default_remittance', 'due_turn': 4,
            'status': 'awaiting_response'}]

        success, _ = resolve_creditor_response(world, 'contest_customs_claim')

        self.assertTrue(success)
        effect = next(event for event in trace.rows
                      if event.get('metric_id') == 'scenario.creditor_effects'
                      and event.get('inputs', {}).get('source')
                      == 'response:contest_customs_claim')
        escalation = next(event for event in trace.rows
                          if event.get('metric_id') == 'scenario.naval_escalation')
        self.assertIn(effect['event_id'], escalation['cause_event_ids'])
        self.assertEqual(escalation['inputs']['reason'],
                         'contest_customs_claim')

    def test_active_crisis_rejects_a_repeat_trigger_without_state_change(self):
        world, trace = _fixture(stage='ultimatum')
        before = world['scenario_state']['naval_crisis'].copy()

        begin_escalation(world, 'reject_revised_terms')

        row = next(event for event in trace.rows
                   if event.get('metric_id') == 'scenario.naval_escalation')
        self.assertFalse(row['inputs']['success'])
        self.assertEqual(row['inputs']['gate_reason'],
                         'naval_crisis_already_active')
        self.assertEqual(world['scenario_state']['naval_crisis'], before)

    def test_withdrawn_crisis_can_be_reopened_without_repeating_chapter_two(self):
        world, trace = _fixture(stage='withdrawn')
        world['scenario_state']['chapter'] = 2
        world['scenario_state']['chapter_two_start_turn'] = 2
        world['scenario_bookend_modal'] = None

        begin_escalation(world, 'refuse_revenue_inspection')

        row = next(event for event in trace.rows
                   if event.get('metric_id') == 'scenario.naval_escalation')
        self.assertTrue(row['inputs']['success'])
        self.assertEqual(world['scenario_state']['naval_crisis']['stage'],
                         'mobilizing')
        self.assertFalse(row['inputs']['chapter_transition_started'])
        self.assertEqual(world.get('scenario_bookend_modal'), None)

    def test_escalation_trace_is_state_neutral_and_compact_serializable(self):
        def run(traced):
            world, _trace = _fixture(stage='none', traced=traced)
            begin_escalation(world, 'contest_customs_claim')
            return (dict(world['scenario_state']['naval_crisis']),
                    world['scenario_state']['chapter'],
                    world['scenario_state'].get('chapter_two_cause'),
                    world['scenario_state'].get('chapter_two_start_turn'),
                    world.get('scenario_bookend_modal'),
                    world.get('playing'),
                    world['scenario_state'].get('naval_news'))

        self.assertEqual(run(True), run(False))

        world, _trace = _fixture(stage='none', traced=False)
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / 'naval-escalation.ctr'
            recorder = RunTrace(trace_path, 'naval-escalation-test')
            clock = {'turn': int(world['turn']),
                     'phase': 'naval_crisis', 'next': 1}
            for tile in world['tiles']:
                tile._run_trace = recorder
                tile._collective_trace_clock = clock
            begin_escalation(world, 'contest_customs_claim')
            row = recorder.query(metric_id='scenario.naval_escalation')['events'][0]
            self.assertTrue(row['inputs']['success'])
            self.assertGreater(verify(trace_path)['rows'], 1)


if __name__ == '__main__':
    unittest.main()
