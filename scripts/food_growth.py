"""Compare food and population growth using complete seasonal observation blocks.

This module only reads saved observations. Matching growth can describe either
prosperity or contraction; coverage, food per person and hunger remain separate.
Prepared food converts grain and is never counted as additional new supply.
"""
from __future__ import annotations

import math


def ratio(numerator, denominator):
    return numerator / denominator if denominator > 0 else None


def growth(current, previous):
    return current / previous - 1 if previous > 0 else None


def analyze_growth(observations, *, window=20, seasonal_cycle=10,
                   alignment_tolerance=.02, sustained_comparisons=3):
    """Use aligned, nonoverlapping full blocks; rates are per block, not per turn.

    Near alignment means food per person changed by at most the chosen fraction
    between adjacent blocks. Three comparisons are a descriptive convention,
    never a simulation constraint. Unknown losses stay unknown, not zero.
    """
    if (not isinstance(window, int) or not isinstance(seasonal_cycle, int)
            or window <= 0 or seasonal_cycle <= 0 or window % seasonal_cycle):
        raise ValueError('Window must contain a positive whole number of seasonal cycles')
    if not math.isfinite(alignment_tolerance) or alignment_tolerance < 0:
        raise ValueError('Alignment tolerance must be finite and nonnegative')
    if not isinstance(sustained_comparisons, int) or sustained_comparisons < 1:
        raise ValueError('Sustained comparison count must be positive')
    rows = [r for r in observations if r['turn'] > 0]
    turns = [r['turn'] for r in rows]
    if turns and turns != list(range(turns[0], turns[-1] + 1)):
        raise ValueError('Observations must be ordered, consecutive and unique')
    blocks, omitted = [], []
    if rows:
        first = ((turns[0] - 1 + window - 1) // window) * window + 1
        omitted.extend(t for t in turns if t < first)
        for start in range(first, turns[-1] + 1, window):
            selected = [r for r in rows if start <= r['turn'] < start + window]
            if len(selected) != window:
                omitted.extend(r['turn'] for r in selected)
                continue
            population = sum(r['population'] for r in selected)
            farm = sum(r['production']['food'] for r in selected)
            gathered = sum(r['foraged_food'] for r in selected)
            need = sum(r['basic_meal_demand'] for r in selected)
            gross = farm + gathered
            has_costs = all(r.get('food_seed_use') is not None
                            and r.get('food_storage_losses') is not None for r in selected)
            seed = sum(r['food_seed_use'] for r in selected) if has_costs else None
            losses = sum(r['food_storage_losses'] for r in selected) if has_costs else None
            net = gross - seed - losses if has_costs else None
            block = {
                'turns': [start, start + window - 1],
                'population_mean': population / window,
                'farm_food_per_turn': farm / window,
                'commons_food_per_turn': gathered / window,
                'gross_new_food_per_turn': gross / window,
                'ordinary_need_per_turn': need / window,
                'food_per_resident_turn': ratio(gross, population),
                'farm_food_per_resident_turn': ratio(farm, population),
                'gross_ordinary_need_coverage': ratio(gross, need),
                'net_of_seed_and_storage_food_per_turn': net / window if net is not None else None,
                'net_of_seed_and_storage_need_coverage': ratio(net, need) if net is not None else None,
                'farm_share_of_new_food': ratio(farm, gross),
                'underfed_share': ratio(sum(r['underfed'] for r in selected), population),
                'population_growth': None, 'farm_food_growth': None,
                'gross_new_food_growth': None, 'ordinary_need_growth': None,
                'food_per_person_growth': None, 'food_minus_population_growth_pp': None,
                'near_alignment': False, 'aligned_while_both_growing': False,
                'sustained_alignment_while_both_growing': False,
            }
            blocks.append(block)
    aligned_streak = longest_streak = 0
    for index, block in enumerate(blocks):
        first = blocks[0]
        for name in ('population_mean', 'farm_food_per_turn', 'gross_new_food_per_turn'):
            base = first[name]
            block[name + '_index'] = 100 * block[name] / base if base > 0 else None
        if index == 0:
            continue
        previous = blocks[index - 1]
        for result, metric in (('population_growth', 'population_mean'),
                               ('farm_food_growth', 'farm_food_per_turn'),
                               ('gross_new_food_growth', 'gross_new_food_per_turn'),
                               ('ordinary_need_growth', 'ordinary_need_per_turn'),
                               ('food_per_person_growth', 'food_per_resident_turn')):
            current, prior = block[metric], previous[metric]
            block[result] = growth(current, prior) if current is not None and prior is not None else None
        food_rate, pop_rate = block['gross_new_food_growth'], block['population_growth']
        if food_rate is not None and pop_rate is not None:
            block['food_minus_population_growth_pp'] = 100 * (food_rate - pop_rate)
        per_person_rate = block['food_per_person_growth']
        block['near_alignment'] = per_person_rate is not None and abs(per_person_rate) <= alignment_tolerance
        block['aligned_while_both_growing'] = (block['near_alignment'] and food_rate is not None
                                                and pop_rate is not None and food_rate >= 0 and pop_rate >= 0)
        aligned_streak = aligned_streak + 1 if block['aligned_while_both_growing'] else 0
        longest_streak = max(longest_streak, aligned_streak)
        block['sustained_alignment_while_both_growing'] = aligned_streak >= sustained_comparisons
    return {
        'window_turns': window, 'seasonal_cycle_turns': seasonal_cycle,
        'alignment_tolerance': alignment_tolerance,
        'sustained_comparisons_required': sustained_comparisons,
        'longest_aligned_growth_streak': longest_streak,
        'sustained_alignment_while_both_growing': longest_streak >= sustained_comparisons,
        'omitted_partial_block_turns': omitted,
        'blocks': blocks,
        'basis': 'Gross locally produced farm grain plus commons gathering; prepared food is conversion.',
        'limitations': [
            'Net-of-seed/storage coverage is unknown when either component is unrecorded.',
            'Ordinary nutritional need is tracked separately from population because age composition changes.',
            'Imports, exports, stock drawdown, births and other nonmeal food uses require separate accounting.',
            'Alignment can coexist with underfeeding and does not establish affordable household access.',
            'The tolerance/streak settings summarize observations; they do not force demographic behavior.',
        ],
    }
