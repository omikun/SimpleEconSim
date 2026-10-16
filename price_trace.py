"""Pure replay of recorded market price formulas.

These functions inspect evidence captured at the mutation point. They never
read or modify simulation objects, so a failed replay exposes a trace defect.
"""

import math


def replay_reference(inputs):
    prior = inputs['prior_reference']
    inflation = 0.25 * math.tanh(inputs['demand_ratio'] - 1.0)
    scarcity = max(0.0, min(1.0, 1.0 - inputs['average_producer_inventory']
                             / max(0.1, inputs['max_inventory'] * 0.6)))
    influence = max(-0.35, min(0.50, inflation + 0.30 * scarcity))
    target = prior * (1.0 + influence)
    move = prior + (target - prior) * 0.25
    samples = inputs['recent_market_price_samples']
    mean = sum(samples) / len(samples) if samples else None
    blended = 0.7 * move + 0.3 * mean if mean is not None else move
    if inputs.get('input_quantity', 0) > 0 and inputs.get('production_quantity', 0) > 0:
        floor = max(0.1, inputs['input_quantity'] * inputs['input_price']
                    / inputs['production_quantity'])
    else:
        floor = 1.0
    final = max(0.1, min(50.0, max(floor, blended)))
    return {'inflation_term': inflation, 'scarcity': scarcity,
            'bounded_influence': influence, 'target': target,
            'move_blend': move, 'recent_sample_mean': mean,
            'after_sample_blend': blended, 'input_cost_floor': floor,
            'final': final}


def replay_decay(inputs):
    price = inputs['prior_display_price']
    if inputs.get('input_quantity', 0) > 0 and inputs.get('production_quantity', 0) > 0:
        floor = inputs['input_quantity'] * inputs['input_price'] / inputs['production_quantity']
    else:
        floor = 1.0
    if price > floor * 1.05:
        price = max(floor, price * 0.95)
    return max(floor, price)


def replay_transport(inputs):
    ratio = inputs['demand_ratio']
    price = inputs['prior_display_price']
    if ratio >= 1:
        price *= 1.01 + (1.20 - 1.01) * min(5.0, ratio - 1) / 5.0
    elif ratio < 0.2:
        price *= 0.90 + (0.95 - 0.90) * ratio / 0.2
    elif ratio < 0.5:
        price *= 0.95 + (1.0 - 0.95) * (ratio - 0.2) / 0.3
    if inputs['input_quantity'] > 0:
        floor = inputs['fundamental_cost'] * 1.10
    else:
        floor = max(inputs['living_cost_floor'], 0.10)
    return max(floor, price, 0.1)


def replay_event(row):
    formula = row.get('formula_id')
    if formula == 'market.reference.v1':
        expected = replay_reference(row['inputs'])['final']
    elif formula == 'market.decay.v1':
        expected = replay_decay(row['inputs'])
    elif formula == 'market.transport.v1':
        expected = replay_transport(row['inputs'])
    elif formula == 'market.local_ask.v1':
        i = row['inputs']
        scarcity = 1.4 - 0.4 * max(0.0, min(1.0, i['stock']
                                                   / max(1, i['max_inventory'])))
        urgency = max(0.0, 1.0 - 0.12 * i['hungry_steps'])
        factor = max(i['urgency_min'], min(i['urgency_max'], scarcity * urgency))
        expected = i['reference'] * factor
    elif formula == 'market.import_ask.v1':
        i = row['inputs']
        denom = max(0.05, (1.0 - i['tariff'] * (1.0 - i['drawback']))
                    * i['fx_buy_rate'])
        expected = i['home_cost'] * (1.0 + i['margin']) / denom
        if i['destination_reference'] > 0:
            expected = min(expected, i['destination_reference']
                           * (1.0 + i['minimum_import_margin']))
        expected = max(0.05, expected)
    elif formula == 'scenario.cotton_ask.v1':
        i = row['inputs']
        expected = (i['base'] + i['wage_coefficient'] * i['wage']
                    if i['corporation'] else i['recipe_reference'])
    elif formula == 'scenario.cloth_ask.v1':
        i = row['inputs']
        expected = round(i['base'] + i['wage'] * i['wage_coefficient']
                         + i['cotton_quantity'] * i['cotton_cost']
                         / max(1.0, i['productive_slots']), i['round_digits'])
    elif formula == 'scenario.delivered_quote.v1':
        i = row['inputs']
        expected = i['ask'] + i['freight']
    elif formula == 'market.transaction_vwap.v1':
        i = row['inputs']
        expected = i['total_paid'] / i['quantity']
    else:
        return None
    actual = row['value_after']
    return {'expected': expected, 'actual': actual,
            'matches': math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-10)}
