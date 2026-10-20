"""Read-only innovation evidence and pure replay of recorded research rules."""


def trace_region(nation):
    return next((tile for tile in getattr(nation, 'tiles', ())
                 if getattr(tile, '_run_trace', None) is not None
                 and getattr(tile, '_collective_trace_clock', None) is not None), None)


def emit_innovation(nation, *, subject_fields=None, region_override=None, **row):
    from run_trace import emit

    region = region_override if region_override is not None else trace_region(nation)
    if region is None:
        return None
    return emit(region, phase='innovation',
                subject={'type': 'nation', 'id': nation.name,
                         **(subject_fields or {})}, **row)


def latest_innovation_event(nation, metric_id, **subject_fields):
    region = trace_region(nation)
    latest = getattr(getattr(region, '_run_trace', None),
                     'latest_metric_calculation_event_id', None)
    if not callable(latest):
        return None
    return latest(metric_id, {'type': 'nation', 'id': nation.name, **subject_fields})


def record_research_gate(nation, tech_id, turn, reason, *, region_override=None, **inputs):
    return emit_innovation(
        nation, kind='innovation_research_gate', record_class='decision',
        subject_fields={'tech_id': tech_id}, metric_id='innovation.research_gate',
        unit='status', after=reason,
        inputs={'turn': int(turn), 'reason': reason, **inputs},
        region_override=region_override)


def record_diffusion_gate(nation, turn, reason, source_tile, destination_tile):
    return emit_innovation(
        nation, kind='innovation_diffusion_gate', record_class='decision',
        metric_id='innovation.diffusion_gate', unit='status', after=reason,
        inputs={'turn': int(turn), 'reason': reason,
                'source_tile': source_tile, 'destination_tile': destination_tile})


def record_technology(nation, tech_id, turn, source, *, cause_event_ids=None,
                      **inputs):
    return emit_innovation(
        nation, kind='innovation_technology_unlocked', record_class='outcome',
        subject_fields={'tech_id': tech_id}, metric_id='innovation.technology_known',
        unit='boolean', before=0, after=1,
        inputs={'turn': int(turn), 'source': source, **inputs},
        cause_event_ids=cause_event_ids)


def record_pressure(nation, tech_id, turn, pressure, evidence, *, known_formula):
    region = trace_region(nation)
    price_event = getattr(getattr(region, '_run_trace', None),
                          'latest_reference_price_event_id', None)
    causes = []
    if callable(price_event):
        for row in evidence.get('tile_food_prices', ()):
            event_id = price_event(row['tile'], 'food')
            row['reference_price_event_id'] = event_id
            if event_id is not None:
                causes.append(event_id)
    return emit_innovation(
        nation, kind='innovation_bottleneck_pressure',
        record_class='calculation' if known_formula else 'observation',
        subject_fields={'tech_id': tech_id},
        metric_id='innovation.bottleneck_pressure', unit='multiplier', after=pressure,
        formula_id='innovation.bottleneck.v1' if known_formula else None,
        inputs={'turn': int(turn), **evidence},
        cause_event_ids=list(dict.fromkeys(causes)) or None)


def record_learning(nation, domain, before, after, terms, *, turn, fixed_increment=0.0):
    region = trace_region(nation)
    latest = getattr(getattr(region, '_run_trace', None),
                     'latest_metric_calculation_event_id', None)
    causes = []
    for term in terms:
        for sample in term.get('tile_samples', ()):
            source_id = None
            if callable(latest) and sample.get('source_metric_id'):
                subject = {'type': 'tile', 'id': sample['tile']}
                if sample.get('good'):
                    subject['good'] = sample['good']
                source_id = latest(sample['source_metric_id'], subject)
            sample['source_event_id'] = source_id
            if source_id is not None:
                causes.append(source_id)
    return emit_innovation(
        nation, kind='innovation_learning_calculation', record_class='calculation',
        subject_fields={'domain': domain}, metric_id='innovation.domain_experience',
        unit='experience_points', before=before, after=after,
        formula_id='innovation.learning_by_doing.v1',
        inputs={'turn': int(turn), 'prior_experience': before,
                'terms': terms, 'fixed_increment': fixed_increment,
                'territory_membership': [tile.name for tile in nation.tiles]},
        cause_event_ids=list(dict.fromkeys(causes)) or None)


def replay_formula(formula, inputs):
    if formula == 'innovation.learning_by_doing.v1':
        return (inputs['prior_experience']
                + sum(term['quantity'] * term['coefficient'] for term in inputs['terms'])
                + inputs['fixed_increment'])
    if formula == 'innovation.bottleneck.v1':
        model = inputs['model']
        if inputs.get('no_tiles') or model == 'none':
            return 1.0
        if model == 'food':
            average = sum(row['price'] for row in inputs['tile_food_prices']) / len(inputs['tile_food_prices'])
            hungry = len(inputs['hungry_agents'])
            multiplier = 1.0
            if average > 1.8:
                multiplier += (average - 1.8) * 1.5
            if hungry > 10:
                multiplier += min(3.0, hungry * 0.10)
            return min(4.0, multiplier)
        if model == 'mountain':
            return min(4.5, 1.0 + len(inputs['high_tiles']) * 0.4
                       + len(inputs['blocked_adjacencies']) * 0.3)
        if model == 'wages':
            wages = [row['wage'] for row in inputs['positive_wages']]
            average = sum(wages) / len(wages) if wages else 1.0
            return min(3.5, 1.0 + ((average - 2.0) * 1.2 if average > 2.0 else 0.0))
        if model == 'war':
            wars = len(inputs['active_wars'])
            return 2.5 + wars if wars else 1.0
    if formula == 'innovation.breakthrough_draw.v1':
        pressure = inputs['bottleneck_multiplier']
        if inputs['bounty_active']:
            pressure *= 3.5
        effective = inputs['domain_experience'] * pressure
        threshold = inputs['required_experience']
        if effective < threshold:
            return 0
        chance = 0.06 + 0.12 * min(1.0, (effective - threshold) / threshold)
        if inputs['bounty_active']:
            chance = min(0.40, chance + 0.20)
        return int(inputs['random_draw'] < chance)
    if formula == 'innovation.trade_diffusion.v1':
        increment = 0.008
        if inputs['source_trade_value'] > 25.0:
            increment += 0.012
        if inputs['trade_pact']:
            increment += 0.015
        return inputs['prior_progress'] + increment
    if formula == 'innovation.diffusion_adoption_reset.v1':
        return 0.0
    raise ValueError(f'unsupported innovation formula: {formula}')
