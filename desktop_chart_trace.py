"""Point selection and trace lookup for the Pygame historical charts."""

from __future__ import annotations

import math


_ECON_BINDINGS = {
    1: {'food': ('goods.price', 'food'), 'wood': ('goods.price', 'wood'),
        'furn': ('goods.price', 'furniture')},
    2: {'pop': ('people.population', None),
        'hungry': ('people.hungry', None)},
    3: {'food': ('goods.production', 'food'),
        'wood': ('goods.production', 'wood'),
        'furn': ('goods.production', 'furniture')},
    4: {'export': ('trade.export_value', None),
        'import': ('trade.import_value', None)},
    5: {'tax': ('finance.government_income', None),
        'tariff': ('finance.government_income', None),
        'inherit': ('finance.government_income', None)},
    6: {'gini': ('economy.gini', 'food'),
        'migr': ('people.migration_pressure', None)},
    7: {'food': ('goods.producer_inventory', 'food'),
        'wood': ('goods.producer_inventory', 'wood'),
        'furn': ('goods.producer_inventory', 'furniture')},
    8: {'protest': ('politics.protest_energy', None),
        'commons x5': ('land.commons_access', None)},
    9: {'gdp/t': ('economy.gdp_nominal', None)},
    10: {'food': ('goods.demand_ratio', 'food'),
         'wood': ('goods.demand_ratio', 'wood'),
         'furn': ('goods.demand_ratio', 'furniture')},
}

_ECO_BINDINGS = {
    1: {'soil %': ('ecology.soil_fertility', None),
        'nutr %': ('ecology.nutrition_density', None)},
    2: {'smog': ('ecology.pollution_air', None),
        'water': ('ecology.pollution_water', None),
        'toxin': ('ecology.pollution_soil', None)},
    3: {'malnutr': ('health.disease_cases', 'malnutrition'),
        'cholera': ('health.disease_cases', 'waterborne'),
        'smog-br': ('health.disease_cases', 'respiratory'),
        'toxic': ('health.disease_cases', 'chemical')},
    4: {'private$': ('health.medical_spending', None),
        'public$': ('health.medical_spending', None)},
    5: {'untreated': ('health.untreated_cases', None),
        'deaths': ('health.fatalities', None),
        'infant✝': ('health.infant_fatalities', None)},
    6: {'wear %': ('health.average_bodily_wear', None)},
}

_CITIZEN_BINDINGS = {
    1: {'serf': ('society.class_population', 'serf'),
        'tenant': ('society.class_population', 'tenant'),
        'worker': ('society.class_population', 'worker'),
        'disposs': ('society.class_population', 'dispossessed'),
        'gentry': ('society.class_population', 'gentry'),
        'artisan': ('society.class_population', 'artisan')},
    2: {'foraged': ('food.foraged', None),
        'market food': ('food.purchased', None),
        'hungry': ('people.hungry', None)},
    3: {'commons %': ('land.commons_access', None),
        'rent ($)': ('finance.rent_collected', None),
        'arrears ($)': ('finance.rent_arrears', None)},
    4: {'gini (x100)': ('economy.gini', 'food'),
        'protest': ('politics.protest_energy', None)},
}

_LABOR_BINDINGS = {
    1: {'shift hrs': ('labor.average_shift_hours', None),
        'effective cap': ('labor.statutory_workday', None),
        's/v rate (%)': ('labor.exploitation_rate', None)},
    2: {'alienation (x100)': ('labor.average_alienation', None),
        'bodily wear (x100)': ('health.average_bodily_wear', None),
        'accidents': ('labor.workplace_accidents', None)},
    3: {'consciousness (x100)': ('labor.average_class_consciousness', None),
        'entertainment (x100)': ('society.entertainment_level', None),
        'protest': ('politics.protest_energy', None)},
    4: {'strikers': ('labor.strikers', None),
        'broken stock': ('labor.broken_machinery', None),
        'sabotaged this turn': ('labor.machinery_sabotaged', None)},
}

_NATION_CITIZEN_BINDINGS = {
    1: {'serf': ('society.class_population', 'serf', 'sum'),
        'tenant': ('society.class_population', 'tenant', 'sum'),
        'worker': ('society.class_population', 'worker', 'sum'),
        'disposs': ('society.class_population', 'dispossessed', 'sum'),
        'gentry': ('society.class_population', 'gentry', 'sum'),
        'artisan': ('society.class_population', 'artisan', 'sum')},
    2: {'foraged': ('food.foraged', None, 'sum'),
        'market food': ('food.purchased', None, 'sum'),
        'hungry': ('people.hungry', None, 'sum')},
    3: {'avg commons %': ('land.commons_access', None, 'mean'),
        'rent ($)': ('finance.rent_collected', None, 'sum'),
        'arrears ($)': ('finance.rent_arrears', None, 'sum')},
    4: {'avg gini (x100)': ('economy.gini', 'food', 'mean'),
        'avg protest': ('politics.protest_energy', None, 'mean')},
}

_NATION_LABOR_BINDINGS = {
    1: {'avg shift hrs': ('labor.average_shift_hours', None, 'mean'),
        'avg effective cap': ('labor.statutory_workday', None, 'mean'),
        'avg s/v rate (%)': ('labor.exploitation_rate', None, 'mean')},
    2: {'alienation (x100)': ('labor.average_alienation', None, 'mean'),
        'bodily wear (x100)': ('health.average_bodily_wear', None, 'mean'),
        'accidents': ('labor.workplace_accidents', None, 'sum')},
    3: {'consciousness (x100)': ('labor.average_class_consciousness', None, 'mean'),
        'entertainment (x100)': ('society.entertainment_level', None, 'mean'),
        'protest': ('politics.protest_energy', None, 'mean')},
    4: {'strikers': ('labor.strikers', None, 'sum'),
        'broken stock': ('labor.broken_machinery', None, 'sum'),
        'sabotaged this turn': ('labor.machinery_sabotaged', None, 'sum')},
}


def chart_trace_binding(chart_mode: str, chart_idx: int, label: str,
                        chart_scope: str = 'tile') -> dict | None:
    """Return trace filters for one plotted series, if that series is mapped."""
    label_key = str(label).strip().lower()
    if chart_scope == 'nation' and chart_mode == 'citizen':
        mapping = _NATION_CITIZEN_BINDINGS
    elif chart_scope == 'nation' and chart_mode == 'labor':
        mapping = _NATION_LABOR_BINDINGS
    else:
        mapping = {'eco': _ECO_BINDINGS, 'citizen': _CITIZEN_BINDINGS,
                   'labor': _LABOR_BINDINGS}.get(chart_mode, _ECON_BINDINGS)
    row = mapping.get(int(chart_idx), {}).get(label_key)
    if row is None:
        return None
    metric_id, filter_value, *aggregate = row
    binding = {'metric_id': metric_id}
    if aggregate:
        binding['aggregation'] = aggregate[0]
    if metric_id == 'health.disease_cases':
        binding['disease'] = filter_value
    elif metric_id == 'society.class_population':
        binding['class_group'] = filter_value
    elif filter_value is not None:
        binding['good'] = filter_value
    if metric_id == 'finance.government_income':
        binding['component'] = {
            'tax': 'tax', 'tariff': 'tariff', 'inherit': 'inheritance'}[label_key]
    elif metric_id == 'health.medical_spending':
        binding['component'] = {
            'private$': 'private_spending',
            'public$': 'public_spending'}[label_key]
    transforms = {
        ('econ', 8, 'commons x5'): '×5 display scale',
        ('eco', 1): '×100 display scale',
        ('eco', 6): '×100 display scale',
        ('citizen', 3, 'commons %'): '×100 display scale',
        ('citizen', 4, 'gini (x100)'): '×100 display scale',
        ('labor', 1, 's/v rate (%)'): '×100 display scale',
        ('labor', 2, 'alienation (x100)'): '×100 display scale',
        ('labor', 2, 'bodily wear (x100)'): '×100 display scale',
        ('labor', 3, 'consciousness (x100)'): '×100 display scale',
        ('labor', 3, 'entertainment (x100)'): '×100 display scale',
        ('nation_citizen', 3, 'avg commons %'): '×100 display scale',
        ('nation_citizen', 4, 'avg gini (x100)'): '×100 display scale',
        ('nation_labor', 1, 'avg s/v rate (%)'): '×100 display scale',
        ('nation_labor', 2, 'alienation (x100)'): '×100 display scale',
        ('nation_labor', 2, 'bodily wear (x100)'): '×100 display scale',
        ('nation_labor', 3, 'consciousness (x100)'): '×100 display scale',
        ('nation_labor', 3, 'entertainment (x100)'): '×100 display scale',
    }
    transform_mode = (f'nation_{chart_mode}' if chart_scope == 'nation'
                      else chart_mode)
    transform = transforms.get((transform_mode, int(chart_idx), label_key))
    if transform is None:
        transform = transforms.get((chart_mode, int(chart_idx)))
    if chart_mode == 'econ' and int(chart_idx) in (5, 9):
        from worldview_charts import GDP_GOV_MA_WINDOW
        transform = f"{GDP_GOV_MA_WINDOW}-turn moving average"
        binding['moving_average_window'] = GDP_GOV_MA_WINDOW
    if transform is not None:
        binding['plot_transform'] = transform
    return binding


def chart_point_at_pixel(position, chart, plot_rect, window: int) -> dict | None:
    """Find the nearest visible series point under a click in a zoomed chart."""
    title, kind, series, _colors, labels = chart
    x0, y0, width, height = plot_rect
    mx, my = position
    if not (x0 <= mx <= x0 + width and y0 <= my <= y0 + height):
        return None
    data = [list(values[-window:]) for values in series]
    if kind == 'line':
        nonempty = [values for values in data if values]
        if not nonempty:
            return None
        all_values = [value for values in nonempty for value in values]
        vmin, vmax = min(all_values), max(all_values)
        if vmax - vmin < 1e-9:
            vmax = vmin + 1.0
        label_height = min(height // 2, 12 + 11 * len(series))
        inner_width = max(10, width - 12)
        inner_height = max(10, height - label_height - 6)
        closest = None
        for series_index, values in enumerate(data):
            if len(values) < 2:
                continue
            for point_index, value in enumerate(values):
                px = x0 + 6 + point_index * inner_width / max(1, len(values) - 1)
                py = y0 + height - 5 - ((value - vmin) / (vmax - vmin)) * inner_height
                distance = math.hypot(mx - px, my - py)
                if closest is None or distance < closest['distance']:
                    closest = {'distance': distance, 'series_index': series_index,
                               'point_index': point_index, 'value': value}
        if closest is None or closest['distance'] > 20:
            return None
        selected = closest
    elif kind in ('bars', 'stack'):
        nonempty = [values for values in data if values]
        if not nonempty:
            return None
        count = max(len(values) for values in nonempty)
        label_height = min(height // 2, 12 + 11 * len(series))
        value_height = max(5, height - label_height - 8)
        inner_width = (width - 12) / count
        if kind == 'stack':
            max_value = max((sum(values[index] for values in data if index < len(values))
                             for index in range(count)), default=0.0)
        else:
            max_value = max((value for values in nonempty for value in values), default=0.0)
        max_value = max(max_value, 1.0)
        stride = max(1, count // 90)
        if kind == 'bars':
            series_count = len(series)
            bar_width = max(2, inner_width * 0.85 / series_count)
            point_index = int((mx - (x0 + 6)) / inner_width)
            if not 0 <= point_index < count or point_index % stride:
                return None
            selected = None
            for series_index, values in enumerate(data):
                value = values[point_index] if point_index < len(values) else 0.0
                bar_height = (value / max_value) * value_height
                bar_x = x0 + 6 + point_index * inner_width + series_index * bar_width
                bar_y = y0 + height - 6 - bar_height
                if (bar_height > 0.5 and bar_x <= mx <= bar_x + bar_width
                        and bar_y <= my <= y0 + height - 6):
                    selected = {'series_index': series_index,
                                'point_index': point_index, 'value': value}
                    break
            if selected is None:
                return None
        else:
            bar_width = max(2, inner_width * 0.85)
            point_index = int((mx - (x0 + 6)) / inner_width)
            if not 0 <= point_index < count or point_index % stride:
                return None
            y = y0 + height - 6
            selected = None
            for series_index, values in enumerate(data):
                value = values[point_index] if point_index < len(values) else 0.0
                bar_height = (value / max_value) * value_height
                top = y - bar_height
                bar_x = x0 + 6 + point_index * inner_width
                if (bar_height > 0.5 and bar_x <= mx <= bar_x + bar_width
                        and top <= my <= y):
                    selected = {'series_index': series_index,
                                'point_index': point_index, 'value': value}
                    break
                y = top
            if selected is None:
                return None
    else:
        return None

    series_index = selected['series_index']
    values = series[series_index]
    visible_values = data[series_index]
    global_index = len(values) - len(visible_values) + selected['point_index']
    return {
        'chart_title': title,
        'series_index': series_index,
        'label': labels[series_index] if series_index < len(labels) else str(series_index),
        'point_index': global_index,
        'value': float(selected['value']),
        'series_length': len(values),
    }


def select_chart_trace(region, chart_mode, chart_idx, chart, plot_rect,
                       position, window: int, fallback_turn: int = 0,
                       chart_scope: str = 'tile', nation_name: str | None = None,
                       nation_tiles=None) -> dict | None:
    """Select a chart point and query its tile or nation trace evidence."""
    point = chart_point_at_pixel(position, chart, plot_rect, window)
    if point is None:
        return None
    binding = chart_trace_binding(chart_mode, chart_idx, point['label'],
                                  chart_scope=chart_scope)
    if binding is None:
        return None
    last_turn = int(getattr(region, '_last_turn', fallback_turn))
    turn = max(0, last_turn - (point['series_length'] - 1 - point['point_index']))
    subject_type = 'nation' if chart_scope == 'nation' else 'tile'
    subject_id = nation_name if chart_scope == 'nation' else region.name
    subject = {'type': subject_type, 'id': subject_id}
    for key in ('good', 'disease', 'class_group'):
        if binding.get(key) is not None:
            subject[key] = binding[key]
    trace = getattr(region, '_run_trace', None)
    rows = []
    aggregation = None
    if trace is not None:
        if chart_scope == 'nation':
            contributing_tiles = list(nation_tiles or ())
            if not contributing_tiles and region is not None:
                contributing_tiles = [region]
            member_values = []
            source_rows = []
            for tile in contributing_tiles:
                tile_subject = {'type': 'tile', 'id': tile.name}
                for key in ('good', 'disease', 'class_group'):
                    if binding.get(key) is not None:
                        tile_subject[key] = binding[key]
                result = trace.query(turn=turn, subject=tile_subject,
                                     metric_id=binding['metric_id'], limit=200)
                tile_rows = result.get('events', [])
                calculations = [row for row in tile_rows
                                if row.get('record_class') == 'calculation'
                                and row.get('kind') != 'metric_snapshot'
                                and row.get('value_after') is not None]
                candidates = calculations or [
                    row for row in tile_rows
                    if row.get('kind') == 'metric_snapshot'
                    and row.get('value_after') is not None]
                if candidates:
                    source_row = candidates[-1]
                    member_values.append({'tile_id': tile.name,
                                          'value': float(source_row['value_after']),
                                          'event_id': source_row.get('event_id'),
                                          'evidence': 'calculation' if calculations
                                          else 'snapshot'})
                    source_rows.append(source_row)
                else:
                    member_values.append({'tile_id': tile.name, 'value': None,
                                          'event_id': None,
                                          'evidence': 'missing'})
            known = [row['value'] for row in member_values
                     if row['value'] is not None]
            reducer = binding.get('aggregation', 'mean')
            denominator = len(known)
            replay = ((sum(known) if reducer == 'sum' else
                       sum(known) / denominator) if denominator else None)
            transform_scale = (100.0 if binding.get('plot_transform') ==
                               '×100 display scale' else 1.0)
            plotted_replay = (replay * transform_scale
                              if replay is not None else None)
            tolerance = max(1e-6, abs(point['value']) * 1e-6)
            aggregation = {
                'reducer': reducer,
                'member_values': member_values,
                'member_count': len(contributing_tiles),
                'coverage_count': denominator,
                'coverage_complete': denominator == len(contributing_tiles),
                'source_value': replay,
                'plotted_value': plotted_replay,
                'matches_chart_point': (plotted_replay is not None and
                                        abs(plotted_replay - point['value']) <= tolerance),
                'membership_basis': 'nation.tiles at inspection time',
            }
            nation_result = trace.query(
                turn=turn, subject=subject,
                metric_id=binding['metric_id'], limit=200)
            nation_calculations = [row for row in nation_result.get('events', ())
                                   if row.get('record_class') == 'calculation'
                                   and row.get('kind') != 'metric_snapshot'
                                   and row.get('value_after') is not None]
            if nation_calculations:
                nation_row = nation_calculations[-1]
                recorded_value = float(nation_row['value_after'])
                recorded_plotted = recorded_value * transform_scale
                recorded_members = ((nation_row.get('inputs') or {}).get(
                    'member_tiles') or [])
                aggregation.update({
                    'recorded_nation_value': recorded_value,
                    'recorded_nation_plotted_value': recorded_plotted,
                    'recorded_nation_matches_chart_point': (
                        abs(recorded_plotted - point['value']) <= tolerance),
                    'recorded_membership_matches_current': (
                        set(recorded_members)
                        == {tile.name for tile in contributing_tiles}),
                })
            rows = source_rows
        else:
            result = trace.query(turn=turn, subject=subject,
                                 metric_id=binding['metric_id'], limit=200)
            rows = result.get('events', [])
    if chart_scope != 'nation':
        preferred = [row for row in rows
                     if row.get('record_class') == 'calculation'
                     and row.get('kind') != 'metric_snapshot']
        if preferred:
            rows = preferred
        else:
            rows = [row for row in rows if row.get('kind') != 'metric_snapshot']
    else:
        rows = [row for row in rows if row is not None]
    source_window = None
    moving_window = binding.get('moving_average_window')
    if trace is not None and moving_window and chart_scope == 'tile':
        first_index = max(0, point['point_index'] - moving_window + 1)
        first_turn = turn - (point['point_index'] - first_index)
        source_points = []
        source_events = []
        for source_turn in range(first_turn, turn + 1):
            result = trace.query(turn=source_turn, subject=subject,
                                 metric_id=binding['metric_id'], limit=200)
            source_rows = result.get('events', [])
            calculations = [row for row in source_rows
                            if row.get('record_class') == 'calculation'
                            and row.get('kind') != 'metric_snapshot']
            candidates = calculations or [
                row for row in source_rows
                if row.get('kind') == 'metric_snapshot']
            source_row = candidates[-1] if candidates else None
            source_value = None
            if source_row is not None:
                if binding.get('component'):
                    components = (source_row.get('inputs') or {}).get(
                        'components') or {}
                    if binding['component'] in components:
                        source_value = float(components[binding['component']])
                elif source_row.get('value_after') is not None:
                    source_value = float(source_row['value_after'])
                if source_value is not None:
                    source_events.append(source_row)
            source_points.append({
                'turn': source_turn, 'value': source_value,
                'event_id': source_row.get('event_id') if source_row else None,
                'evidence': ('calculation' if calculations else 'snapshot')
                if source_row else 'missing'})
        complete = all(row['value'] is not None for row in source_points)
        replay = (sum(row['value'] for row in source_points) / len(source_points)
                  if complete and source_points else None)
        tolerance = max(1e-6, abs(point['value']) * 1e-6)
        source_window = {
            'window_turns': moving_window,
            'first_turn': first_turn, 'last_turn': turn,
            'expected_source_turns': len(source_points),
            'source_points': source_points,
            'coverage_count': sum(row['value'] is not None
                                  for row in source_points),
            'coverage_complete': complete,
            'replayed_value': replay,
            'matches_chart_point': (replay is not None and
                                    abs(replay - point['value']) <= tolerance),
            'component': binding.get('component'),
        }
    return {
        'tile': region.name,
        'nation': nation_name if chart_scope == 'nation' else None,
        'chart_scope': chart_scope,
        'turn': turn,
        'metric_id': binding['metric_id'],
        'series_label': point['label'],
        'chart_value': point['value'],
        'component': binding.get('component'),
        'plot_transform': binding.get('plot_transform'),
        'events': rows[:4],
        'aggregation': aggregation,
        'source_window': source_window,
        'has_trace': trace is not None,
        'chart_idx': int(chart_idx),
        'chart_mode': chart_mode,
        'chart_family': ('nation' if chart_scope == 'nation' else
                         chart_mode if chart_mode in ('citizen', 'labor')
                         else 'tile'),
    }


def trace_selection_matches(selection, info, region, chart_idx):
    """Whether a selection belongs to the currently rendered chart context."""
    if not selection or not info:
        return False
    if (selection.get('chart_family', 'tile') != info.get('chart_family', 'tile')
            or selection.get('chart_idx') != chart_idx
            or selection.get('chart_mode') != info.get('chart_mode')
            or selection.get('chart_scope', 'tile') != info.get('chart_scope', 'tile')):
        return False
    if info.get('chart_scope') == 'nation':
        return selection.get('nation') == info.get('nation')
    return selection.get('tile') == getattr(region, 'name', None)


def draw_trace_selection(surface, selection, rect, font):
    """Draw compact causal evidence over the zoomed chart after point selection."""
    if not selection:
        return
    x, y, width, height = rect
    aggregation = selection.get('aggregation')
    source_window = selection.get('source_window')
    panel_height = (min(240, max(180, height // 2)) if source_window else
                    min(200, max(150, height // 2)) if aggregation else
                    min(132, max(96, height // 2)))
    panel = (x + 8, y + height - panel_height - 8, width - 16, panel_height)
    import pygame
    pygame.draw.rect(surface, (10, 14, 22), panel, border_radius=5)
    pygame.draw.rect(surface, (100, 120, 150), panel, 1, border_radius=5)
    tx, ty = panel[0] + 8, panel[1] + 6
    scope_name = (f"{selection['nation']} · " if selection.get('nation') else '')
    header = (f"Trace {scope_name}T{selection['turn']} · {selection['metric_id']} · "
              f"{selection['series_label']}")
    if selection.get('component'):
        header += f" / {selection['component']}"
    lines = [header, f"Chart point: {selection['chart_value']:,.3f}"]
    if selection.get('plot_transform'):
        lines.append(f"Chart transform: {selection['plot_transform']}")
    if aggregation:
        replay = aggregation.get('plotted_value')
        status = ('matches' if aggregation.get('matches_chart_point') else
                  'does not match' if replay is not None else 'unavailable')
        lines.append(
            f"Nation {aggregation['reducer']} across "
            f"{aggregation['coverage_count']}/{aggregation['member_count']} tiles; "
            f"replay {status} point")
        examples = [f"{row['tile_id']}={row['value']:,.3f}"
                    for row in aggregation.get('member_values', ())
                    if row.get('value') is not None][:2]
        if examples:
            lines.append('Tile values: ' + ', '.join(examples))
        if aggregation.get('recorded_nation_value') is not None:
            membership = ('same' if aggregation.get(
                'recorded_membership_matches_current') else 'different')
            recorded = ('matches' if aggregation.get(
                'recorded_nation_matches_chart_point') else 'differs from')
            lines.append(
                f"Run record {membership} membership: "
                f"{recorded} plotted point")
    if source_window:
        replay = source_window.get('replayed_value')
        status = ('matches' if source_window.get('matches_chart_point') else
                  'does not match' if replay is not None else 'unavailable')
        lines.append(
            f"Moving average: {source_window['coverage_count']}/"
            f"{source_window['expected_source_turns']} turns; replay {status}")
        source_points = source_window.get('source_points', ())
        for start in range(0, len(source_points), 5):
            group = source_points[start:start + 5]
            values = [f"T{row['turn']}="
                      f"{row['value']:,.3g}" if row.get('value') is not None
                      else f"T{row['turn']}=missing" for row in group]
            if values:
                lines.append('Sources: ' + ', '.join(values))
    events = selection.get('events', [])
    if not selection.get('has_trace'):
        lines.append('No run trace is attached to this tile.')
    elif not events:
        lines.append('No matching records were captured for this point.')
    for row in events[:1]:
        if source_window and source_window.get('component'):
            component_value = next((item.get('value') for item in
                                    source_window.get('source_points', ())
                                    if item.get('turn') == selection['turn']), None)
            shown_value = ('missing' if component_value is None
                           else f"{component_value:,.3f}")
            lines.append(f"Recorded {source_window['component']}: {shown_value}")
        else:
            before = row.get('value_before')
            after = row.get('value_after')
            change = (f"{before} → {after}" if before is not None else str(after))
            lines.append(f"{row.get('kind', 'record')}: {change} {row.get('unit', '')}".strip())
        formula = row.get('formula_id')
        if formula:
            lines.append(f"Formula: {formula}")
        inputs = row.get('inputs') or {}
        simple = []
        for key, value in inputs.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                simple.append(f"{key}={value}")
            elif isinstance(value, (list, dict)):
                simple.append(f"{key}[{len(value)}]")
            if len(simple) >= 3:
                break
        if simple:
            lines.append('Inputs: ' + ', '.join(simple))
    for line in lines[:10]:
        surface.blit(font.render(line[:115], True, (220, 225, 235)), (tx, ty))
        ty += 18
