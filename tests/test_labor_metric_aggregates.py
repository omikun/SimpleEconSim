import unittest
from types import SimpleNamespace

from labor_contract import (FirmLaborStats, aggregate_tile_surplus,
                            record_surplus_value)
from goods import Goods


class TestLaborMetricAggregates(unittest.TestCase):
    def test_shift_and_exploitation_inputs_replay_aggregate(self):
        firms = [
            SimpleNamespace(
                id=11, is_corporation=True, employees=[object(), object()],
                shift_hours=10.0, machinery_level=2, broken_machinery=0,
                _latest_labor_stats=FirmLaborStats(
                    firm_id=11, num_workers=2, shift_hours=10.0,
                    safety_investment=0.0, machinery_level=2,
                    broken_machinery=0, variable_capital=20.0,
                    constant_capital=10.0, gross_output_value=70.0,
                    surplus_value=40.0, rate_of_exploitation=2.0)),
            SimpleNamespace(
                id=12, is_corporation=True, employees=[object()],
                shift_hours=6.0, machinery_level=1, broken_machinery=0,
                _latest_labor_stats=FirmLaborStats(
                    firm_id=12, num_workers=1, shift_hours=6.0,
                    safety_investment=0.0, machinery_level=1,
                    broken_machinery=0, variable_capital=40.0,
                    constant_capital=5.0, gross_output_value=55.0,
                    surplus_value=10.0, rate_of_exploitation=0.25)),
        ]
        stats = aggregate_tile_surplus(SimpleNamespace(agents=firms))

        shift_inputs = stats['avg_shift_hours_inputs']
        shift_replay = (shift_inputs['weighted_shift_hours_sum']
                        / shift_inputs['worker_count'])
        self.assertAlmostEqual(shift_replay, stats['avg_shift_hours'])
        self.assertAlmostEqual(stats['avg_shift_hours'], 26.0 / 3.0)

        exploitation_inputs = stats['exploitation_inputs']
        exploitation_replay = (
            exploitation_inputs['total_surplus_value']
            / exploitation_inputs['total_variable_capital'])
        self.assertAlmostEqual(exploitation_replay,
                               stats['avg_rate_of_exploitation'])
        self.assertAlmostEqual(stats['avg_rate_of_exploitation'], 50.0 / 60.0)
        self.assertEqual(len(shift_inputs['firms']), 2)
        self.assertTrue(all(row['included_in_rate']
                            for row in exploitation_inputs['firms']))

    def test_empty_metrics_record_explicit_fallbacks(self):
        stats = aggregate_tile_surplus(SimpleNamespace(agents=[]))
        self.assertEqual(stats['avg_shift_hours_inputs']['empty_value'], 8.0)
        self.assertEqual(stats['exploitation_inputs']['empty_value'], 0.0)
        self.assertEqual(stats['avg_shift_hours_inputs']['firms'], [])
        self.assertEqual(stats['exploitation_inputs']['firms'], [])

    def test_current_turn_surplus_excludes_prior_turn_firm_stats(self):
        current = SimpleNamespace(
            id=11, is_corporation=True, employees=[object()], shift_hours=8.0,
            machinery_level=1, broken_machinery=0,
            _latest_labor_stats_turn=5, _latest_labor_surplus_event_id='run:11',
            _latest_labor_stats=FirmLaborStats(
                firm_id=11, num_workers=1, shift_hours=8.0,
                safety_investment=0.0, machinery_level=1, broken_machinery=0,
                variable_capital=20.0, constant_capital=10.0,
                gross_output_value=70.0, surplus_value=40.0,
                rate_of_exploitation=2.0))
        stale = SimpleNamespace(
            id=12, is_corporation=True, employees=[object()], shift_hours=6.0,
            machinery_level=1, broken_machinery=0,
            _latest_labor_stats_turn=4, _latest_labor_surplus_event_id='run:12',
            _latest_labor_stats=FirmLaborStats(
                firm_id=12, num_workers=1, shift_hours=6.0,
                safety_investment=0.0, machinery_level=1, broken_machinery=0,
                variable_capital=40.0, constant_capital=5.0,
                gross_output_value=55.0, surplus_value=10.0,
                rate_of_exploitation=0.25))
        unknown_turn = SimpleNamespace(
            id=13, is_corporation=True, employees=[], shift_hours=8.0,
            machinery_level=1, broken_machinery=0,
            _latest_labor_stats=FirmLaborStats(
                firm_id=13, num_workers=0, shift_hours=8.0,
                safety_investment=0.0, machinery_level=1, broken_machinery=0,
                variable_capital=0.0, constant_capital=0.0,
                gross_output_value=99.0, surplus_value=99.0,
                rate_of_exploitation=0.0))

        stats = aggregate_tile_surplus(
            SimpleNamespace(agents=[current, stale, unknown_turn]), turn=5)

        self.assertEqual(stats['total_surplus_value'], 40.0)
        self.assertEqual(stats['avg_rate_of_exploitation'], 2.0)
        self.assertEqual(stats['surplus_inputs']['total_surplus_value'], 40.0)
        self.assertEqual(stats['surplus_inputs']['firms'][0]['source_event_id'],
                         'run:11')
        stale_row = stats['surplus_inputs']['firms'][1]
        self.assertEqual(stale_row['contribution'], 0.0)
        self.assertFalse(stale_row['included_in_current_turn'])
        self.assertEqual(stale_row['exclusion_reason'],
                         'latest_labor_stats_from_prior_turn')
        unknown_row = stats['surplus_inputs']['firms'][2]
        self.assertEqual(unknown_row['contribution'], 0.0)
        self.assertEqual(unknown_row['exclusion_reason'],
                         'latest_labor_stats_turn_unknown')

    def test_firm_surplus_trace_records_formula_inputs_and_causes(self):
        class TraceStub:
            def __init__(self):
                self.events = []

            def latest_metric_event_id(self, metric_id, subject):
                self.asserted_production_subject = (metric_id, subject)
                return 'run:production'

            def latest_reference_price_event_id(self, tile_id, good_name):
                self.asserted_price_subject = (tile_id, good_name)
                return f'run:price:{good_name}'

            def emit(self, clock, **kwargs):
                event_id = f"run:{clock['next']}"
                clock['next'] += 1
                self.events.append((event_id, kwargs))
                return event_id

        trace = TraceStub()
        region = SimpleNamespace(
            name='Delta', home_currency='pounds',
            recipes={Goods.cloth: {'price': 3.0}, Goods.cotton: {'price': 2.0}},
            _collective_trace_clock={'turn': 6, 'next': 1, 'phase': 'production'},
            _run_trace=trace)
        firm = SimpleNamespace(
            id=21, employees=[object(), object(), object()], shift_hours=9.0,
            safety_investment=2.0, machinery_level=2, broken_machinery=1,
            wage=5.0)

        stats = record_surplus_value(
            firm, region, Goods.cloth, units_produced=20,
            raw_inputs_cost=10.0, wages_paid=15.0, turn=6,
            input_good=Goods.cotton, input_units=5,
            input_reference_price=2.0,
            input_inventory_unit_cost_basis=1.5,
            input_inventory_cost_basis_known=True)

        self.assertEqual(stats.surplus_value, 29.0)
        self.assertEqual(firm._latest_labor_stats_turn, 6)
        self.assertEqual(firm._latest_labor_surplus_event_id, 'run:1')
        event = trace.events[0][1]
        self.assertEqual(event['metric_id'], 'labor.firm_surplus_value')
        self.assertEqual(event['formula_id'], 'labor.gross_value_minus_capital.v1')
        self.assertEqual(event['after'], 29.0)
        self.assertEqual(event['unit'], 'pounds')
        self.assertEqual(event['cause_event_ids'], [
            'run:production', f'run:price:{Goods.cloth.name}',
            f'run:price:{Goods.cotton.name}'])
        self.assertEqual(event['inputs']['gross_output_value'], 60.0)
        self.assertEqual(event['inputs']['constant_capital'], 16.0)
        self.assertEqual(event['inputs']['variable_capital'], 15.0)
        self.assertEqual(event['inputs']['pre_floor_surplus'], 29.0)
        self.assertEqual(event['inputs']['input_good'], Goods.cotton.name)
        self.assertEqual(event['inputs']['input_units'], 5)
        self.assertEqual(event['inputs']['input_reference_price'], 2.0)
        self.assertEqual(event['inputs']['input_inventory_unit_cost_basis'], 1.5)
        self.assertTrue(event['inputs']['input_inventory_cost_basis_known'])


if __name__ == '__main__':
    unittest.main()
