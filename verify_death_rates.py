#!/usr/bin/env python3
"""Statistically verify agent death rates match the configured probabilities.

Patches _handle_death to log every death roll (probability vs random draw),
then aggregates expected deaths (sum of probabilities) vs actual deaths.

Usage:
    python3 verify_death_rates.py [time_steps]
"""

import sys
import random
from collections import defaultdict

from goods import Goods
from region import Region
from logger import logInit
import econsim_two_region as sim
import econsim_live as _lm

PROF_NAMES = {
    Goods.food: 'Food',
    Goods.wood: 'Wood',
    Goods.furniture: 'Furniture',
    Goods.gov: 'Gov',
}


def prof_of(agent):
    if getattr(agent, 'is_trader', False):
        return 'Trader'
    if getattr(agent, 'is_corporation', False):
        return 'Corp'
    if getattr(agent, 'is_government', False):
        return 'Gov'
    return PROF_NAMES.get(agent.output, '?')


# ---------------------------------------------------------------
# Patch _handle_death to record every roll
# ---------------------------------------------------------------
death_rolls = []  # (prof, wealth, age, expected_prob, died)

orig_death = _lm._handle_death


def patched_death(ctx, t, agent, agents):
    # Compute the same adjusted_prob the original would use.
    # We copy the logic here instead of calling orig twice (double roll!).
    if agent.hungry_steps >= ctx.starve_limit:
        # starvation death — not a probabilistic roll
        return orig_death(ctx, t, agent, agents)
    base_death_prob = [0.0002, 0.0003, 0.0007, 0.0013, 0.0025,
                       0.006, 0.013, 0.027, 0.06, 0.13]
    import government as govmod
    government = govmod.find_government_for_agent(agent)
    if government is not None:
        adjusted_prob = government.get_death_probability(
            agent, base_death_prob[min(agent.age(t) // 30, 9)])
    else:
        adjusted_prob = base_death_prob[min(agent.age(t) // 30, 9)]
    agent_age = agent.age(t)
    wealth = agent.wealth()
    if agent_age < 210 and adjusted_prob > 0:
        food_price = ctx.recipes.get(Goods.food, {}).get('price', 1)
        wood_price = ctx.recipes.get(Goods.wood, {}).get('price', 1)
        furn_price = ctx.recipes.get(Goods.furniture, {}).get('price', 1)
        col = max(0.1, 4 * food_price + 1 * wood_price + 0.25 * furn_price)
        if wealth > col:
            age_weight = max(0.0, 1.0 - (agent_age / 210.0) ** 6)
            wealth_factor = (col / max(0.01, wealth)) ** 2
            wealth_factor = max(0.01, min(1.0, wealth_factor))
            if hasattr(agent, '_birth_parent_wealth') and t < getattr(agent, '_birth_protection_until', 0):
                parent_wealth_factor = (col / max(0.01, agent._birth_parent_wealth)) ** 2
                parent_wealth_factor = max(0.01, min(1.0, parent_wealth_factor))
                fade = max(0.0, (agent._birth_protection_until - t) / 50.0)
                wealth_factor = wealth_factor * (1 - fade) + parent_wealth_factor * fade
            mortality_discount = 1.0 - (1.0 - wealth_factor) * age_weight
            adjusted_prob *= mortality_discount
    current_pop = len(agents)
    threshold = ctx.carrying_capacity * 0.85
    if current_pop > threshold:
        overage = current_pop - threshold
        crowding_factor = 1.0 + (overage / (ctx.carrying_capacity * 0.15)) * 4.0
        adjusted_prob *= crowding_factor

    died = orig_death(ctx, t, agent, agents)
    death_rolls.append((prof_of(agent), wealth, agent_age, adjusted_prob, died))
    return died


_lm._handle_death = patched_death


def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    logInit()
    random.seed(42)

    region_a = Region('Region_A', 0, 55,
                       {Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
    region_b = Region('Region_B', 0, 55,
                       {Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
    region_a.recipes[Goods.food]['production'] *= 2
    region_b.recipes[Goods.wood]['production'] *= 2
    region_a.destination_region = region_b
    region_b.destination_region = region_a

    for t in range(1, time_steps + 1):
        region_a.step(t)
        region_b.step(t)
        sim.process_transport(t, region_a, region_b)
        sim.foreign_sell(t, region_a, region_b)
        sim.foreign_sell(t, region_b, region_a)

    # ---------------------------------------------------------------
    # Aggregate: expected deaths = sum of probabilities
    # ---------------------------------------------------------------
    print(f"\n=== DEATH RATE VERIFICATION ({time_steps} turns) ===")
    print(f"Total death rolls: {len(death_rolls)}")

    print(f"\n{'Category':<24} {'Rolls':>7} {'Exp Dea':>8} {'Act Dea':>8} {'Ratio':>7}")
    print("-" * 58)

    def summarize(rows, label):
        if not rows:
            print(f"{label:<24} {0:>7} {0:>8} {0:>8} {'n/a':>7}")
            return
        n = len(rows)
        exp = sum(p for _, _, _, p, _ in rows)
        act = sum(1 for _, _, _, _, d in rows if d)
        ratio = act / exp if exp > 0 else float('inf')
        flag = ""
        if exp > 30 and abs(ratio - 1.0) > 0.25:
            flag = "  <-- OFF"
        print(f"{label:<24} {n:>7} {exp:>8.1f} {act:>8} {ratio:>7.2f}{flag}")

    # Overall
    summarize(death_rolls, "ALL AGENTS")

    # By profession
    by_prof = defaultdict(list)
    for row in death_rolls:
        by_prof[row[0]].append(row)
    for prof in ['Food', 'Wood', 'Furniture', 'Trader', 'Gov', 'Corp']:
        summarize(by_prof[prof], prof)

    # By wealth bucket (relative to cost of living at the time)
    wealth_buckets = defaultdict(list)
    for prof, wealth, age, prob, died in death_rolls:
        col_est = 25.0  # rough avg cost of living across sim
        ratio = wealth / max(0.1, col_est)
        if ratio <= 1.0:
            bucket = '0-1x col'
        elif ratio <= 4.0:
            bucket = '1-4x col'
        elif ratio <= 10.0:
            bucket = '4-10x col'
        else:
            bucket = '>10x col'
        wealth_buckets[bucket].append((prof, wealth, age, prob, died))
    print()
    for bucket in ['0-1x col', '1-4x col', '4-10x col', '>10x col']:
        summarize(wealth_buckets[bucket], bucket)

    # Randomness sanity: for each roll, P(die | prob) should approximate prob.
    # Use a chi-square-like check bucketed by probability level.
    print("\n=== RANDOMNESS CHECK (by death-probability level) ===")
    prob_buckets = defaultdict(list)
    for prof, wealth, age, prob, died in death_rolls:
        if prob <= 0:
            bucket = '0 (no risk)'
        elif prob < 0.001:
            bucket = '<0.001'
        elif prob < 0.01:
            bucket = '0.001-0.01'
        elif prob < 0.05:
            bucket = '0.01-0.05'
        else:
            bucket = '>0.05'
        prob_buckets[bucket].append((prof, wealth, age, prob, died))
    print(f"{'Prob bucket':<16} {'Rolls':>7} {'Exp Dea':>8} {'Act Dea':>8} {'Ratio':>7}")
    print("-" * 52)
    for bucket in ['0 (no risk)', '<0.001', '0.001-0.01', '0.01-0.05', '>0.05']:
        summarize(prob_buckets[bucket], bucket)

    print("\nLegend: Ratio = actual deaths / expected deaths. "
          "Expected ~1.0 if the probability math and random cache are correct.")
    print("A ratio consistently >1.0 or <1.0 in large buckets indicates bias.")


if __name__ == "__main__":
    main()