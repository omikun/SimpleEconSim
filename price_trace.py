"""Pure replay of recorded market price formulas.

These functions inspect evidence captured at the mutation point. They never
read or modify simulation objects, so a failed replay exposes a trace defect.
"""

import math


def replay_reference(inputs):
    prior = inputs['prior_reference']
    demand_ratio = inputs['demand_ratio']
    inflation = 0.25 * math.tanh(demand_ratio - 1.0)
    raw_scarcity = max(-0.6, min(1.0, 1.0 - inputs['average_producer_inventory']
                                 / max(0.1, inputs['max_inventory'] * 0.5)))
    if raw_scarcity > 0.0:
        scarcity = raw_scarcity * max(0.0, min(1.0, (demand_ratio - 1.0) / 0.50))
    else:
        scarcity = raw_scarcity * max(0.0, min(1.0, 1.15 - demand_ratio))
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


def replay_econsim_market_price(inputs):
    """Replay the standalone econsim demand, subsistence and producer floors."""
    price = inputs['prior_display_price']
    ratio = inputs['demand_ratio']
    if ratio >= 1:
        multiplier = 1.01 + (1.20 - 1.01) * min(5.0, ratio - 1) / 5.0
        price *= multiplier
    elif ratio < 0.2:
        multiplier = 0.90 + (0.95 - 0.90) * ratio / 0.2
        price *= multiplier
    elif ratio < 0.5:
        multiplier = 0.95 + (1.0 - 0.95) * (ratio - 0.2) / 0.3
        price *= multiplier

    input_quantity = inputs.get('input_quantity', 0)
    production_quantity = inputs.get('production_quantity', 0)
    if input_quantity > 0 and production_quantity > 0:
        fundamental_cost = (input_quantity * inputs['input_price']) / production_quantity
    else:
        fundamental_cost = 1.0
    production_rate = inputs.get('production_rate', 1)
    living_cost_floor = (4 * inputs['food_price']) / max(1, production_rate)
    if input_quantity > 0:
        min_price_floor = max(fundamental_cost * 1.10, living_cost_floor)
    else:
        min_price_floor = max(living_cost_floor, 0.10)

    producer_multipliers = []
    for producer in inputs.get('producers', ()):
        poor_factor = max(0.2, min(1.0, producer['cash'] / 20.0))
        hungry_factor = max(0.1, 0.8 ** producer['hungry_steps'])
        producer_multipliers.append(poor_factor * hungry_factor)
    if producer_multipliers:
        dynamic_price = fundamental_cost * (
            sum(producer_multipliers) / len(producer_multipliers))
        price = max(price, dynamic_price)
    return max(min_price_floor, price, 0.1)


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


def replay_living_basket(inputs):
    """Replay the local food, heating, and shelter price basket."""
    weights = inputs['basket_weights']
    prices = (inputs['food_price'], inputs['wood_price'],
              inputs['furniture_price'])
    subtotal = sum(weight * price for weight, price in zip(weights, prices))
    return max(0.1, subtotal * inputs['regional_multiplier']
               * inputs['climate_multiplier'])


def replay_event(row):
    formula = row.get('formula_id')
    if formula == 'market.reference.v1':
        expected = replay_reference(row['inputs'])['final']
    elif formula in ('market.decay.v1', 'econsim.price_decay.v1'):
        expected = replay_decay(row['inputs'])
    elif formula == 'market.transport.v1':
        expected = replay_transport(row['inputs'])
    elif formula == 'market.local_ask.v1':
        i = row['inputs']
        scarcity = 1.10 - 0.30 * max(0.0, min(1.0, i['stock']
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
    elif formula == 'market.local_bid.v1':
        i = row['inputs']
        expected = i['reference'] * (1.0 + max(
            i.get('demand_premium', 0.0), i.get('need_premium', 0.0)))
        expected = min(expected, i['cash_limit'])
        if i.get('input_value_ceiling') is not None:
            expected = min(expected, i['input_value_ceiling'])
        if i.get('trader_net_value') is not None:
            expected = min(expected, max(0.0, i['trader_net_value']))
    elif formula == 'market.sum_bids.v1':
        expected = sum(item['quantity']
                       for item in row['inputs']['bid_quantities'])
    elif formula == 'market.local_plus_imports.v1':
        i = row['inputs']
        expected = i['local_asks'] + i['imported_asks']
    elif formula == 'market.demand_supply_ratio.v1':
        i = row['inputs']
        expected = (i['zero_supply_ratio'] if i['total_asks'] == 0
                    else i['bids'] / i['total_asks'])
    elif formula == 'living.basket_prices_climate.v1':
        expected = replay_living_basket(row['inputs'])
    elif formula == 'aggregate.mean.v1':
        inputs = row['inputs']
        values = inputs['member_values']
        if values:
            expected = sum(values) / inputs['denominator']
        else:
            expected = inputs.get('empty_value', 0.0)
    elif formula == 'aggregate.sum.v1':
        expected = sum(row['inputs']['member_values'])
    elif formula == 'econsim.market_price.v1':
        expected = replay_econsim_market_price(row['inputs'])
    else:
        return None
    actual = row['value_after']
    return {'expected': expected, 'actual': actual,
            'matches': math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-10)}
