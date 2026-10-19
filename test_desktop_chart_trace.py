import unittest
from types import SimpleNamespace

from desktop_chart_trace import (
    chart_point_at_pixel,
    chart_trace_binding,
    select_chart_trace,
)
from micro.region.stepper import sample_effective_workday_cap


class FakeTrace:
    def __init__(self, events):
        self.events = events
        self.query_args = None
        self.emitted = None

    def query(self, **kwargs):
        self.query_args = kwargs
        return {'events': self.events, 'total': len(self.events)}

    def emit(self, clock, **kwargs):
        self.emitted = (clock, kwargs)
        return 'event-1'


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
             'plot_transform': '10-turn moving average',
             'moving_average_window': 10})
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
        self.assertEqual(
            chart_trace_binding('citizen', 1, 'worker'),
            {'metric_id': 'society.class_population',
             'class_group': 'worker'})
        self.assertEqual(
            chart_trace_binding('citizen', 3, 'commons %'),
            {'metric_id': 'land.commons_access',
             'plot_transform': '×100 display scale'})
        self.assertEqual(
            chart_trace_binding('labor', 1, 'effective cap'),
            {'metric_id': 'labor.statutory_workday'})
        self.assertEqual(
            chart_trace_binding('labor', 3, 'entertainment (x100)'),
            {'metric_id': 'society.entertainment_level',
             'plot_transform': '×100 display scale'})
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

    def test_nation_citizen_and_labor_series_have_exact_reducers(self):
        from worldview_citizens import nation_citizen_charts
        from worldview_labor_ui import nation_labor_charts
        from goods import Goods

        def tile(name):
            return SimpleNamespace(
                name=name, social_class_log=[{'serf': 2, 'tenant': 1,
                    'proletarian': 3, 'dispossessed': 1, 'lord': 1,
                    'landlord': 1, 'petty_bourgeois': 1, 'industrialist': 1}],
                food_foraged_log=[4], food_purchased_log=[5],
                hungry_log={Goods.food: [1], Goods.wood: [0],
                    Goods.furniture: [0], 'trader': [0]},
                tenure_log=[0.8], rent_collected_log=[2.0],
                rent_arrears_log=[1.0], gini_log={Goods.food: [0.3]},
                protest_energy_log=[1.5], avg_shift_hours_log=[8.0],
                rate_of_exploitation_log=[0.5], workday_cap_log=[10.0],
                avg_alienation_log=[0.2], avg_health_attrition_log=[0.1],
                workplace_accidents_log=[1], avg_consciousness_log=[0.4],
                entertainment_log=[0.3], strikers_log=[3],
                broken_machinery_log=[1], sabotage_log=[1])

        nation = SimpleNamespace(name='Republic', tiles=[tile('North'), tile('South')])
        for mode, charts in (
                ('citizen', nation_citizen_charts(nation)),
                ('labor', nation_labor_charts(nation))):
            for chart_idx, chart in enumerate(charts, start=1):
                for label in chart[4]:
                    self.assertIsNotNone(
                        chart_trace_binding(mode, chart_idx, label,
                                            chart_scope='nation'),
                        (mode, chart_idx, label))
        self.assertEqual(
            chart_trace_binding('citizen', 1, 'worker', 'nation'),
            {'metric_id': 'society.class_population',
             'aggregation': 'sum', 'class_group': 'worker'})
        self.assertEqual(
            chart_trace_binding('labor', 1, 'avg shift hrs', 'nation'),
            {'metric_id': 'labor.average_shift_hours', 'aggregation': 'mean'})

    def test_nation_chart_selection_replays_member_tile_evidence(self):
        class NationTrace(FakeTrace):
            def __init__(self):
                super().__init__([])
                self.queries = []

            def query(self, **kwargs):
                self.queries.append(kwargs)
                subject = kwargs['subject']
                if subject['type'] == 'nation':
                    row = {'kind': 'nation_chart_history_aggregate',
                           'record_class': 'calculation', 'value_after': 4.0,
                           'event_id': 'nation-event',
                           'inputs': {'member_tiles': ['North', 'South']}}
                else:
                    value = {'North': 3.0, 'South': 1.0}[subject['id']]
                    row = {'kind': 'social_class_population_calculation',
                           'record_class': 'calculation', 'value_after': value,
                           'event_id': f"event-{subject['id']}"}
                return {'events': [row], 'total': 1}

        trace = NationTrace()
        north, south = FakeRegion(trace), FakeRegion(trace)
        north.name, south.name = 'North', 'South'
        nation_tiles = [north, south]
        chart = ('Classes', 'line', [[2.0, 4.0], [1.0, 2.0]],
                 ['green', 'yellow'], ['serf', 'tenant'])
        selection = select_chart_trace(
            north, 'citizen', 1, chart, (10, 20, 100, 100), (104, 55), 2,
            chart_scope='nation', nation_name='Republic',
            nation_tiles=nation_tiles)
        self.assertEqual(selection['chart_family'], 'nation')
        self.assertEqual(selection['nation'], 'Republic')
        self.assertEqual(selection['metric_id'], 'society.class_population')
        self.assertEqual(selection['aggregation']['reducer'], 'sum')
        self.assertEqual(selection['aggregation']['source_value'], 4.0)
        self.assertTrue(selection['aggregation']['matches_chart_point'])
        self.assertTrue(selection['aggregation'][
            'recorded_nation_matches_chart_point'])
        self.assertTrue(selection['aggregation'][
            'recorded_membership_matches_current'])
        self.assertEqual([row['tile_id'] for row in
                          selection['aggregation']['member_values']],
                         ['North', 'South'])
        self.assertEqual(len(selection['events']), 2)

    def test_nation_citizen_and_labor_panel_clicks_dispatch(self):
        from worldview_camera import HEIGHT, TICKER_H, TOP_BAR_H
        from worldview_citizens import PANEL_LEFT as CITIZEN_LEFT, citizen_panel_hit
        from worldview_labor_ui import PANEL_LEFT as LABOR_LEFT, labor_panel_hit

        citizen_trace = FakeTrace([{
            'kind': 'social_class_population_calculation',
            'record_class': 'calculation', 'value_after': 2.0,
            'event_id': 'class-1'}])
        tile = FakeRegion(citizen_trace)
        tile.owner_nation = SimpleNamespace(name='Republic')
        nation = tile.owner_nation
        nation.tiles = [tile]
        chart_y0 = 180 + TOP_BAR_H + 52 + 60 + 30
        plot_rect = (CITIZEN_LEFT + 10, chart_y0 + 50, 100, 100)
        chart = ('Classes', 'line', [[1.0, 2.0]], ['green'], ['serf'])
        world = {
            'selected_region': tile, 'nations': [nation], 'scope': 'tile',
            'citizen_scope': 'nation', 'citizen_subtab': 'class',
            'citizen_class_mode': 'charts', 'citizen_chart_view': 1,
            'window': 2, 'turn': 25,
            '_chart_zoom_trace_info': {
                'chart_family': 'nation', 'chart_mode': 'citizen',
                'chart_scope': 'nation', 'nation': nation.name,
                'chart_idx': 1, 'chart': chart, 'plot_rect': plot_rect,
                'window': 2},
        }
        citizen_point = (plot_rect[0] + 94, plot_rect[1] + 24)
        self.assertLess(citizen_point[1], HEIGHT - TICKER_H - 24)
        self.assertTrue(citizen_panel_hit(citizen_point, world))
        self.assertEqual(world['_chart_trace_selection']['chart_family'], 'nation')
        self.assertEqual(world['_chart_trace_selection']['nation'], nation.name)

        labor_trace = FakeTrace([{
            'kind': 'labor_shift_hours_calculation',
            'record_class': 'calculation', 'value_after': 9.0,
            'event_id': 'labor-1'}])
        tile._run_trace = labor_trace
        labor_chart = ('Shifts', 'line', [[8.0, 9.0]], ['red'],
                       ['avg shift hrs'])
        labor_rect = (LABOR_LEFT + 10, chart_y0 + 50, 100, 100)
        world.update({
            'labor_sub_mode': 'charts', 'citizen_chart_view': 1,
            '_chart_trace_selection': None,
            '_chart_zoom_trace_info': {
                'chart_family': 'nation', 'chart_mode': 'labor',
                'chart_scope': 'nation', 'nation': nation.name,
                'chart_idx': 1, 'chart': labor_chart,
                'plot_rect': labor_rect, 'window': 2},
        })
        labor_point = (labor_rect[0] + 94, labor_rect[1] + 24)
        self.assertTrue(labor_panel_hit(labor_point, world))
        self.assertEqual(world['_chart_trace_selection']['chart_family'], 'nation')
        self.assertEqual(world['_chart_trace_selection']['metric_id'],
                         'labor.average_shift_hours')

    def test_citizen_chart_series_bind_and_include_trader_hunger(self):
        from goods import Goods
        from worldview_citizens import tile_citizen_charts
        region = SimpleNamespace(
            social_class_log=[{'serf': 2, 'tenant': 1, 'proletarian': 3,
                               'dispossessed': 1, 'lord': 1, 'landlord': 1,
                               'petty_bourgeois': 1, 'industrialist': 1}],
            food_foraged_log=[4], food_purchased_log=[5],
            hungry_log={Goods.food: [1, 2], Goods.wood: [2, 3],
                        Goods.furniture: [3, 4], 'trader': [4, 5]},
            tenure_log=[0.8], rent_collected_log=[2.0],
            rent_arrears_log=[1.0], gini_log={Goods.food: [0.3]},
            protest_energy_log=[1.5])
        charts = tile_citizen_charts(region)
        self.assertEqual(charts[1][2][2], [10, 14])
        for chart_idx, chart in enumerate(charts, start=1):
            for label in chart[4]:
                self.assertIsNotNone(
                    chart_trace_binding('citizen', chart_idx, label),
                    (chart_idx, label))

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

    def test_moving_average_trace_replays_all_source_turns(self):
        class HistoryTrace:
            def __init__(self, missing_turn=None):
                self.missing_turn = missing_turn
                self.queries = []

            def query(self, **kwargs):
                self.queries.append(kwargs)
                turn = kwargs['turn']
                if turn == self.missing_turn:
                    return {'events': [], 'total': 0}
                return {'events': [{
                    'kind': 'nominal_gdp_calculation',
                    'record_class': 'calculation',
                    'value_after': float(turn - 13),
                    'event_id': f'gdp-{turn}'}], 'total': 1}

        smoothed = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5,
                    4.0, 4.5, 5.0, 5.5, 6.5, 7.5]
        chart = ('GDP Output', 'line', [smoothed], ['green'], ['gdp/t'])
        trace = HistoryTrace()
        selection = select_chart_trace(
            FakeRegion(trace), 'econ', 9, chart, (10, 20, 100, 100),
            (104, 44), 12)

        source_window = selection['source_window']
        self.assertEqual(selection['turn'], 25)
        self.assertEqual(source_window['first_turn'], 16)
        self.assertEqual(source_window['last_turn'], 25)
        self.assertEqual(source_window['coverage_count'], 10)
        self.assertEqual(source_window['replayed_value'], 7.5)
        self.assertTrue(source_window['matches_chart_point'])
        self.assertEqual([query['turn'] for query in trace.queries[-10:]],
                         list(range(16, 26)))

    def test_moving_average_replay_keeps_missing_turns_as_gaps(self):
        class HistoryTrace:
            def query(self, **kwargs):
                turn = kwargs['turn']
                if turn == 20:
                    return {'events': [], 'total': 0}
                return {'events': [{
                    'kind': 'nominal_gdp_calculation',
                    'record_class': 'calculation',
                    'value_after': float(turn - 13)}], 'total': 1}

        smoothed = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5,
                    4.0, 4.5, 5.0, 5.5, 6.5, 7.5]
        chart = ('GDP Output', 'line', [smoothed], ['green'], ['gdp/t'])
        selection = select_chart_trace(
            FakeRegion(HistoryTrace()), 'econ', 9, chart,
            (10, 20, 100, 100), (104, 44), 12)

        source_window = selection['source_window']
        self.assertEqual(source_window['coverage_count'], 9)
        self.assertFalse(source_window['coverage_complete'])
        self.assertIsNone(source_window['replayed_value'])
        self.assertFalse(source_window['matches_chart_point'])
        missing = next(row for row in source_window['source_points']
                       if row['turn'] == 20)
        self.assertIsNone(missing['value'])
        self.assertEqual(missing['evidence'], 'missing')

    def test_revenue_moving_average_uses_component_not_total(self):
        event = {
            'kind': 'government_income_calculation',
            'record_class': 'calculation', 'value_after': 20.0,
            'inputs': {'components': {
                'tax': 10.0, 'tariff': 4.0, 'inheritance': 6.0}},
            'event_id': 'income-25'}
        trace = FakeTrace([event])
        chart = ('Government Revenue', 'stack', [[10.0], [4.0], [6.0]],
                 ['red', 'blue', 'green'], ['tax', 'tariff', 'inherit'])
        selection = select_chart_trace(
            FakeRegion(trace), 'econ', 5, chart, (10, 20, 100, 100),
            (60, 75), 1)

        self.assertEqual(selection['series_label'], 'inherit')
        self.assertEqual(selection['chart_value'], 6.0)
        self.assertEqual(selection['source_window']['replayed_value'], 6.0)
        self.assertTrue(selection['source_window']['matches_chart_point'])
        self.assertEqual(selection['source_window']['component'], 'inheritance')

    def test_citizen_chart_query_filters_the_selected_class_group(self):
        trace = FakeTrace([{'kind': 'social_class_population_calculation',
                            'record_class': 'calculation', 'value_after': 12}])
        region = FakeRegion(trace)
        chart = ('Classes', 'line', [[8.0, 12.0]], ['green'], ['worker'])
        selection = select_chart_trace(
            region, 'citizen', 1, chart, (10, 20, 100, 100), (104, 44), 2)
        self.assertEqual(selection['chart_family'], 'citizen')
        self.assertEqual(selection['metric_id'], 'society.class_population')
        self.assertEqual(trace.query_args['subject'], {
            'type': 'tile', 'id': 'Delta', 'class_group': 'worker'})

    def test_citizen_panel_click_dispatches_point_to_trace_selection(self):
        from worldview_camera import HEIGHT, TICKER_H, TOP_BAR_H
        from worldview_citizens import PANEL_LEFT, citizen_panel_hit
        region = FakeRegion(FakeTrace([{
            'kind': 'social_class_population_calculation',
            'record_class': 'calculation', 'value_after': 12}]))
        chart = ('Classes', 'line', [[8.0, 12.0]], ['green'], ['worker'])
        chart_y0 = 180 + TOP_BAR_H + 52 + 60 + 30
        plot_rect = (PANEL_LEFT + 10, chart_y0 + 20, 100, 100)
        world = {
            'selected_region': region, 'scope': 'tile', 'citizen_scope': 'tile',
            'citizen_subtab': 'class', 'citizen_class_mode': 'charts',
            'citizen_chart_view': 1, 'window': 2, 'turn': 25,
            '_chart_zoom_trace_info': {
                'chart_family': 'citizen', 'chart_mode': 'citizen',
                'chart_idx': 1, 'chart': chart, 'plot_rect': plot_rect,
                'window': 2},
        }
        point = (plot_rect[0] + 94, plot_rect[1] + 24)
        self.assertLess(point[1], HEIGHT - TICKER_H - 24)
        self.assertTrue(citizen_panel_hit(point, world))
        self.assertEqual(world['_chart_trace_selection']['metric_id'],
                         'society.class_population')
        self.assertEqual(world['_chart_trace_selection']['chart_family'],
                         'citizen')

    def test_all_labor_chart_histories_have_trace_bindings(self):
        from worldview_labor_ui import tile_labor_charts
        region = SimpleNamespace(
            avg_shift_hours_log=[8.0], rate_of_exploitation_log=[0.5],
            workday_cap_log=[10.0], avg_alienation_log=[0.2],
            avg_health_attrition_log=[0.1], workplace_accidents_log=[1],
            avg_consciousness_log=[0.4], entertainment_log=[0.3],
            protest_energy_log=[2.0], strikers_log=[3],
            broken_machinery_log=[1], sabotage_log=[1])
        for chart_idx, chart in enumerate(tile_labor_charts(region), start=1):
            for label in chart[4]:
                self.assertIsNotNone(chart_trace_binding('labor', chart_idx, label),
                                     (chart_idx, label))

    def test_workday_cap_chart_history_matches_effective_cap_trace(self):
        recorder = FakeTrace([])
        region = SimpleNamespace(
            name='Delta', workday_cap=10.0, max_workday_hours=12.0,
            workday_cap_log=[16.0], _run_trace=recorder,
            _collective_trace_clock={'turn': 7})
        self.assertEqual(sample_effective_workday_cap(region), 10.0)
        self.assertEqual(region.workday_cap_log, [16.0, 10.0])
        clock, event = recorder.emitted
        self.assertEqual(clock, {'turn': 7})
        self.assertEqual(event['metric_id'], 'labor.statutory_workday')
        self.assertEqual(event['before'], 16.0)
        self.assertEqual(event['after'], 10.0)
        self.assertEqual(event['inputs']['statute_display_value'], 12.0)

    def test_labor_panel_click_dispatches_point_to_trace_selection(self):
        from worldview_camera import HEIGHT, TICKER_H, TOP_BAR_H
        from worldview_labor_ui import PANEL_LEFT, labor_panel_hit
        region = FakeRegion(FakeTrace([{
            'kind': 'effective_workday_cap_sample',
            'record_class': 'calculation', 'value_after': 10.0}]))
        chart = ('Shift Hours', 'line', [[10.0, 12.0]], ['blue'],
                 ['effective cap'])
        chart_y0 = 180 + TOP_BAR_H + 52 + 60 + 30
        plot_rect = (PANEL_LEFT + 10, chart_y0 + 20, 100, 100)
        world = {
            'selected_region': region, 'scope': 'tile', 'citizen_scope': 'tile',
            'labor_sub_mode': 'charts', 'citizen_chart_view': 1,
            'window': 2, 'turn': 25,
            '_chart_zoom_trace_info': {
                'chart_family': 'labor', 'chart_mode': 'labor',
                'chart_idx': 1, 'chart': chart, 'plot_rect': plot_rect,
                'window': 2},
        }
        point = (plot_rect[0] + 94, plot_rect[1] + 24)
        self.assertLess(point[1], HEIGHT - TICKER_H - 24)
        self.assertTrue(labor_panel_hit(point, world))
        self.assertEqual(world['_chart_trace_selection']['metric_id'],
                         'labor.statutory_workday')
        self.assertEqual(world['_chart_trace_selection']['chart_family'], 'labor')


if __name__ == '__main__':
    unittest.main()
