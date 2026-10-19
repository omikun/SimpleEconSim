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


def chart_trace_binding(chart_mode: str, chart_idx: int, label: str) -> dict | None:
    """Return trace filters for one plotted series, if that series is mapped."""
    label_key = str(label).strip().lower()
    mapping = {'eco': _ECO_BINDINGS, 'citizen': _CITIZEN_BINDINGS}.get(
        chart_mode, _ECON_BINDINGS)
    row = mapping.get(int(chart_idx), {}).get(label_key)
    if row is None:
        return None
    metric_id, filter_value = row
    binding = {'metric_id': metric_id}
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
    }
    transform = transforms.get((chart_mode, int(chart_idx), label_key))
    if transform is None:
        transform = transforms.get((chart_mode, int(chart_idx)))
    if chart_mode == 'econ' and int(chart_idx) in (5, 9):
        from worldview_charts import GDP_GOV_MA_WINDOW
        transform = f"{GDP_GOV_MA_WINDOW}-turn moving average"
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
                       position, window: int, fallback_turn: int = 0) -> dict | None:
    """Select a chart point, query its tile trace records, and return display data."""
    point = chart_point_at_pixel(position, chart, plot_rect, window)
    if point is None:
        return None
    binding = chart_trace_binding(chart_mode, chart_idx, point['label'])
    if binding is None:
        return None
    last_turn = int(getattr(region, '_last_turn', fallback_turn))
    turn = max(0, last_turn - (point['series_length'] - 1 - point['point_index']))
    subject = {'type': 'tile', 'id': region.name}
    for key in ('good', 'disease', 'class_group'):
        if binding.get(key) is not None:
            subject[key] = binding[key]
    trace = getattr(region, '_run_trace', None)
    rows = []
    if trace is not None:
        result = trace.query(turn=turn, subject=subject,
                            metric_id=binding['metric_id'], limit=200)
        rows = result.get('events', [])
    preferred = [row for row in rows
                 if row.get('record_class') == 'calculation'
                 and row.get('kind') != 'metric_snapshot']
    if preferred:
        rows = preferred
    else:
        rows = [row for row in rows if row.get('kind') != 'metric_snapshot']
    return {
        'tile': region.name,
        'turn': turn,
        'metric_id': binding['metric_id'],
        'series_label': point['label'],
        'chart_value': point['value'],
        'component': binding.get('component'),
        'plot_transform': binding.get('plot_transform'),
        'events': rows[:4],
        'has_trace': trace is not None,
        'chart_idx': int(chart_idx),
        'chart_mode': chart_mode,
        'chart_family': 'citizen' if chart_mode == 'citizen' else 'tile',
    }


def draw_trace_selection(surface, selection, rect, font):
    """Draw compact causal evidence over the zoomed chart after point selection."""
    if not selection:
        return
    x, y, width, height = rect
    panel_height = min(132, max(96, height // 2))
    panel = (x + 8, y + height - panel_height - 8, width - 16, panel_height)
    import pygame
    pygame.draw.rect(surface, (10, 14, 22), panel, border_radius=5)
    pygame.draw.rect(surface, (100, 120, 150), panel, 1, border_radius=5)
    tx, ty = panel[0] + 8, panel[1] + 6
    header = (f"Trace T{selection['turn']} · {selection['metric_id']} · "
              f"{selection['series_label']}")
    if selection.get('component'):
        header += f" / {selection['component']}"
    lines = [header, f"Chart point: {selection['chart_value']:,.3f}"]
    if selection.get('plot_transform'):
        lines.append(f"Chart transform: {selection['plot_transform']}")
    events = selection.get('events', [])
    if not selection.get('has_trace'):
        lines.append('No run trace is attached to this tile.')
    elif not events:
        lines.append('No matching records were captured for this point.')
    for row in events[:1]:
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
    for line in lines[:6]:
        surface.blit(font.render(line[:115], True, (220, 225, 235)), (tx, ty))
        ty += 18
