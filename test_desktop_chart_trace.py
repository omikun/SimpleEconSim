import unittest
from types import SimpleNamespace

from desktop_chart_trace import (
    chart_point_at_pixel,
    chart_trace_binding,
    select_chart_trace,
)


class FakeTrace:
    def __init__(self, events):
        self.events = events
        self.query_args = None

    def query(self, **kwargs):
        self.query_args = kwargs
        return {'events': self.events, 'total': len(self.events)}


class FakeRegion:
    name = 'Delta'
    _last_turn = 25

    def __init__(self, trace):
        self._run_trace = trace


class DesktopChartTraceTests(unittest.TestCase):
    def test_bindings_cover_economic_and_ecological_series_names(self):
        self.assertEqual(
            chart_trace_binding('econ', 1, 'WOOD'),
            {'metric_id': 'goods.price', 'good': 'wood'})
        self.assertEqual(
            chart_trace_binding('econ', 5, 'inherit'),
            {'metric_id': 'finance.government_income',
             'component': 'inheritance',
             'plot_transform': '10-turn moving average'})
        self.assertEqual(
            chart_trace_binding('eco', 1, 'soil %'),
            {'metric_id': 'ecology.soil_fertility',
             'plot_transform': '×100 display scale'})
        self.assertEqual(
            chart_trace_binding('eco', 6, 'wear %'),
            {'metric_id': 'health.average_bodily_wear',
             'plot_transform': '×100 display scale'})
        self.assertEqual(
            chart_trace_binding('eco', 3, 'cholera'),
            {'metric_id': 'health.disease_cases', 'disease': 'waterborne'})
        self.assertIsNone(chart_trace_binding('econ', 1, 'not a series'))

    def test_every_tile_economic_and_ecological_series_has_a_binding(self):
        from worldview_charts import tile_charts, tile_ecological_charts
        region = SimpleNamespace(
            price_log={}, production_log={}, inventory_log={},
            demand_ratio_log={}, total_population=[], hungry_log={},
            export_val={}, import_val={}, gov=None, protest_energy_log=[],
            gdp_log=[], gini_log={}, migration_intent_log=[], tenure_log=[],
            soil_fertility_log=[], nutrition_density_log=[],
            pollution_air_log=[], pollution_water_log=[], pollution_soil_log=[],
            disease_cases_log=[], medical_spending_private_log=[],
            medical_spending_public_log=[], untreated_cases_log=[],
            disease_fatalities_log=[], infant_fatalities_log=[],
            avg_health_attrition_log=[])
        for mode, charts in (('econ', tile_charts(region)),
                             ('eco', tile_ecological_charts(region))):
            for chart_idx, chart in enumerate(charts, start=1):
                for label in chart[4]:
                    self.assertIsNotNone(
                        chart_trace_binding(mode, chart_idx, label),
                        (mode, chart_idx, label))

    def test_line_click_uses_visible_latest_window_and_resolves_turn(self):
        chart = ('Prices', 'line', [[1.0, 2.0, 3.0], [100.0, 200.0, 300.0]],
                 ['red', 'blue'], ['food', 'wood'])
        # The last food point is at x=104, near the bottom of the shared scale.
        point = chart_point_at_pixel((104, 115), chart, (10, 20, 100, 100), 2)
        self.assertEqual(point['label'], 'food')
        self.assertEqual(point['point_index'], 2)
        self.assertEqual(point['value'], 3.0)
        self.assertIsNone(chart_point_at_pixel((50, 50), chart,
                                              (10, 20, 100, 100), 2))

    def test_grouped_bar_click_selects_the_rendered_series(self):
        chart = ('Trade', 'bars', [[10.0, 20.0, 30.0], [0.0, 5.0, 10.0]],
                 ['green', 'blue'], ['export', 'import'])
        point = chart_point_at_pixel((18, 80), chart, (10, 20, 100, 100), 2)
        self.assertEqual(point['label'], 'export')
        self.assertEqual(point['point_index'], 1)
        self.assertEqual(point['value'], 20.0)

    def test_stacked_bar_click_uses_total_stack_scale(self):
        chart = ('Government Revenue', 'stack',
                 [[1.0, 2.0], [2.0, 4.0], [1.0, 2.0]],
                 ['red', 'blue', 'green'], ['tax', 'tariff', 'inherit'])
        # On the final bar, y=72 is inside the top (inheritance) segment.
        point = chart_point_at_pixel((60, 72), chart, (10, 20, 100, 100), 2)
        self.assertEqual(point['label'], 'inherit')
        self.assertEqual(point['point_index'], 1)
        self.assertEqual(point['value'], 2.0)

    def test_trace_query_uses_selected_point_turn_and_filters(self):
        events = [
            {'kind': 'metric_snapshot', 'record_class': 'observation'},
            {'kind': 'price_calculation', 'record_class': 'calculation',
             'value_before': 2.5, 'value_after': 3.0},
            {'kind': 'other', 'record_class': 'operation'},
        ]
        trace = FakeTrace(events)
        region = FakeRegion(trace)
        chart = ('Prices', 'line', [[1.0, 2.0, 3.0, 4.0]], ['red'], ['food'])
        selection = select_chart_trace(
            region, 'econ', 1, chart, (10, 20, 100, 100), (16, 115), 2)
        self.assertEqual(selection['turn'], 24)
        self.assertEqual(selection['metric_id'], 'goods.price')
        self.assertEqual(selection['events'], [events[1]])
        self.assertEqual(selection['chart_mode'], 'econ')
        self.assertEqual(trace.query_args['turn'], 24)
        self.assertEqual(trace.query_args['subject'],
                         {'type': 'tile', 'id': 'Delta', 'good': 'food'})
        self.assertEqual(trace.query_args['metric_id'], 'goods.price')
        self.assertEqual(trace.query_args['limit'], 200)


if __name__ == '__main__':
    unittest.main()
