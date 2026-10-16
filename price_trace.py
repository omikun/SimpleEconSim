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
    floor = inputs['input_cost_floor']
    if price > floor * 1.05:
        price = max(floor, price * 0.95)
    return max(floor, price)


def replay_event(row):
    formula = row.get('formula_id')
    if formula == 'market.reference.v1':
        expected = replay_reference(row['inputs'])['final']
    elif formula == 'market.decay.v1':
        expected = replay_decay(row['inputs'])
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
