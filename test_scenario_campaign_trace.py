import tempfile
import unittest
import copy
from pathlib import Path

from run_trace import RunTrace, verify
from scenario_campaign import bombard_alexandria, resolve_landing
from scenario_geography import create_fleet, move_fleet
from worldview_engine import build_world_view


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, landing_warning=True, fleet=True):
    world = build_world_view(scenario_id='egypt_1877')
    if fleet:
        create_fleet(world, 'Britain')
        move_fleet(world, 'Britain', 'Alexandria')
    world['scenario_warning_modal'] = (
        {'kind': 'landing_warning'} if landing_warning else None)
    tile_name = world['scenario_state']['geography']['sites']['Alexandria']['tile']
    tile = next(tile for tile in world['tiles'] if tile.name == tile_name)
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': int(world['turn']), 'phase': 'campaign', 'next': 1}
    return world, tile, trace


class ScenarioCampaignTraceTests(unittest.TestCase):
    @staticmethod
    def _action_row(trace):
        rows = [row for row in trace.rows
                if row.get('metric_id') == 'scenario.landing_response']
        if not rows:
            raise AssertionError('landing response trace was not emitted')
        return rows[-1]

    @staticmethod
    def _garrison(world):
        egypt = next(n for n in world['nations'] if n.name == 'Egypt')
        garrison_id = world['scenario_state']['politics']['garrison_id']
        return next(unit for unit in egypt.military_units
                    if unit.unit_id == garrison_id)

    def test_evacuation_traces_garrison_move_and_new_occupation_force(self):
        world, _tile, trace = _fixture()
        garrison_before = self._garrison(world)
        old_region = garrison_before.region_name
        garrison_id = garrison_before.unit_id
        transports = world['scenario_state']['geography']['fleets']['Britain']['transports']
        cairo_tile = world['scenario_state']['geography']['sites']['Cairo']['tile']

        ok, _ = resolve_landing(world, 'evacuate_port')

        self.assertTrue(ok)
        row = self._action_row(trace)
        inputs = row['inputs']
        self.assertFalse(row.get('cause_event_ids'))
        self.assertTrue(inputs['garrison_moved'])
        self.assertEqual(inputs['garrison_unit_id'], garrison_id)
        self.assertEqual(inputs['state_before']['egyptian_garrison']['region'], old_region)
        self.assertEqual(inputs['state_after']['egyptian_garrison']['region'], cairo_tile)
        self.assertEqual(inputs['landing_unit_soldiers'], transports)
        self.assertEqual(inputs['state_after']['territorial_control']['Alexandria'],
                         'Britain')
        self.assertEqual(len(inputs['state_after']['british_landing_units']), 1)

    def test_battle_records_are_linked_to_the_selected_landing_response(self):
        world, _tile, trace = _fixture()

        ok, _ = resolve_landing(world, 'defend_alexandria')

        self.assertTrue(ok)
        row = self._action_row(trace)
        battle_ids = [event['event_id'] for event in trace.rows
                      if event.get('metric_id') == 'war.battle']
        control_ids = [event['event_id'] for event in trace.rows
                       if event.get('metric_id') == 'war.territory_control']
        self.assertGreaterEqual(len(battle_ids), 1)
        self.assertTrue(set(battle_ids).issubset(set(row['cause_event_ids'])))
        self.assertTrue(set(control_ids).issubset(set(row['cause_event_ids'])))
        self.assertEqual(row['inputs']['battle_location'], 'Alexandria')
        self.assertEqual(row['inputs']['state_after']['battle_count'], 1)

    def test_canal_defense_traces_funding_choice_and_denial_reroute(self):
        funded, _tile, funded_trace = _fixture()
        funded_result = resolve_landing(funded, 'defend_canal')
        self.assertTrue(funded_result[0], funded_result[1])
        funded_inputs = self._action_row(funded_trace)['inputs']
        self.assertTrue(funded_inputs['garrison_moved'])
        self.assertTrue(funded_inputs['canal_access'])
        self.assertGreater(funded_inputs['upkeep_per_turn'], 0)
        self.assertGreater(funded_inputs['forecast_cash_required'], 0)
        self.assertEqual(funded_inputs['route_decision'],
                         'funded_canal_expedition')

        denied, _tile, denied_trace = _fixture()
        denied['scenario_state']['geography']['canal_open'] = False
        denied_result = resolve_landing(denied, 'defend_canal')
        self.assertTrue(denied_result[0], denied_result[1])
        denied_inputs = self._action_row(denied_trace)['inputs']
        self.assertFalse(denied_inputs['canal_access'])
        self.assertEqual(denied_inputs['route_decision'],
                         'canal_denial_reroutes_landing')
        self.assertTrue(denied_inputs['state_after']['battle_count'])

    def test_unaffordable_canal_expedition_records_withdrawal_reason(self):
        world, _tile, trace = _fixture()
        britain = next(n for n in world['nations'] if n.name == 'Britain')
        britain.government.agent.cash = 0.0

        ok, _ = resolve_landing(world, 'defend_canal')

        self.assertTrue(ok)
        inputs = self._action_row(trace)['inputs']
        self.assertEqual(inputs['route_decision'], 'expedition_unaffordable')
        self.assertEqual(inputs['british_cash_available'], 0.0)
        self.assertEqual(inputs['state_after']['expedition_stage'], 'repelled')
        self.assertEqual(inputs['state_after']['naval_crisis_stage'], 'withdrawn')

    def test_landing_rejection_gates_are_traced(self):
        no_warning, _tile, no_warning_trace = _fixture(landing_warning=False)
        self.assertFalse(resolve_landing(no_warning, 'evacuate_port')[0])
        no_warning_row = self._action_row(no_warning_trace)
        self.assertEqual(no_warning_row['inputs']['reason'],
                         'no_landing_decision_pending')

        unknown, _tile, unknown_trace = _fixture()
        self.assertFalse(resolve_landing(unknown, 'not_a_landing_order')[0])
        self.assertEqual(self._action_row(unknown_trace)['inputs']['reason'],
                         'unknown_landing_response')

        unaffordable, _tile, unaffordable_trace = _fixture()
        egypt = next(n for n in unaffordable['nations'] if n.name == 'Egypt')
        egypt.government.agent.cash = 0.0
        self.assertFalse(resolve_landing(unaffordable, 'negotiate_landing')[0])
        funding_row = self._action_row(unaffordable_trace)
        self.assertEqual(funding_row['inputs']['reason'],
                         'landing_response_funding_gate')
        self.assertFalse(funding_row['inputs']['payment_gate_met'])

    def test_tracing_does_not_change_evacuation_state(self):
        traced, _tile, _trace = _fixture(traced=True)
        plain, _plain_tile, _plain_trace = _fixture(traced=False)

        self.assertEqual(resolve_landing(traced, 'evacuate_port'),
                         resolve_landing(plain, 'evacuate_port'))

        for key in ('campaign', 'occupation', 'fiscal_autonomy', 'payment_status',
                    'actions_taken'):
            self.assertEqual(traced['scenario_state'].get(key),
                             plain['scenario_state'].get(key), key)
        self.assertEqual(traced['scenario_state']['geography'],
                         plain['scenario_state']['geography'])
        self.assertEqual(traced['scenario_state']['politics'],
                         plain['scenario_state']['politics'])

    def test_landing_response_is_serializable_in_compact_trace(self):
        world, tile, _trace = _fixture(traced=False)
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / 'landing.ctr'
            recorder = RunTrace(trace_path, 'landing-test')
            tile._run_trace = recorder
            tile._collective_trace_clock = {
                'turn': int(world['turn']), 'phase': 'campaign', 'next': 1}

            self.assertTrue(bombard_alexandria(world)[0])
            self.assertTrue(resolve_landing(world, 'evacuate_port')[0])

            result = recorder.query(metric_id='scenario.landing_response')
            self.assertEqual(result['total'], 1)
            self.assertEqual(result['events'][0]['inputs']['result_message'],
                             world['scenario_feedback'])
            self.assertEqual(
                recorder.query(metric_id='scenario.bombardment')['total'], 1)
            self.assertEqual(verify(trace_path)['checkpoints'], 0)

    def test_bombardment_explains_guns_battery_injuries_and_port_damage(self):
        world, tile, trace = _fixture()
        households = [agent for agent in tile.agents
                      if getattr(agent, 'alive', True)
                      and not getattr(agent, 'is_government', False)
                      and not getattr(agent, 'is_corporation', False)]
        households[0].health_attrition = 2.4
        households[1].health_attrition = 0.1

        ok, _ = bombard_alexandria(world)

        self.assertTrue(ok)
        rows = [row for row in trace.rows
                if row.get('metric_id') == 'scenario.bombardment']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        inputs = row['inputs']
        self.assertTrue(inputs['fort_battery_active'])
        self.assertEqual(inputs['fort_ammunition_spent'], 3)
        self.assertGreater(inputs['british_effective_guns_after_battery_hit'], 0)
        self.assertFalse(inputs['french_fire_authorized'])
        self.assertEqual(inputs['casualties'],
                         min(inputs['eligible_household_count'],
                             max(1, int(inputs['strike'] / 24))))
        injured = inputs['injured_households']
        self.assertEqual(injured[0]['health_attrition_before'], 2.4)
        self.assertEqual(injured[0]['health_attrition_after'], 2.5)
        self.assertEqual(inputs['state_after']['civilian_casualty_counter'],
                         inputs['casualties'])
        self.assertGreater(inputs['state_after']['infrastructure_damage'], 0)
        self.assertAlmostEqual(inputs['state_after']['tile_unrest'], 0.2)

    def test_bombardment_gate_and_trace_off_state_parity(self):
        missing, _tile, missing_trace = _fixture(fleet=False)
        state_before = copy.deepcopy(missing['scenario_state']['campaign'])

        self.assertFalse(bombard_alexandria(missing)[0])

        event = next(row for row in missing_trace.rows
                     if row.get('metric_id') == 'scenario.bombardment')
        self.assertEqual(event['inputs']['reason'], 'british_fleet_missing')
        self.assertEqual(missing['scenario_state']['campaign']['forts'],
                         state_before['forts'])

        traced, traced_tile, _trace = _fixture(traced=True)
        plain, plain_tile, _plain_trace = _fixture(traced=False)
        self.assertEqual(bombard_alexandria(traced),
                         bombard_alexandria(plain))
        self.assertEqual(traced['scenario_state']['campaign'],
                         plain['scenario_state']['campaign'])
        traced_fleet = traced['scenario_state']['geography']['fleets']['Britain']
        plain_fleet = plain['scenario_state']['geography']['fleets']['Britain']
        self.assertEqual(traced_fleet, plain_fleet)
        self.assertEqual(
            [getattr(agent, 'health_attrition', 0.0) for agent in traced_tile.agents],
            [getattr(agent, 'health_attrition', 0.0) for agent in plain_tile.agents])


if __name__ == '__main__':
    unittest.main()
