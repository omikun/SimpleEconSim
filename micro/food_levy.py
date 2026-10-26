"""Shared per-holder ceiling for emergency in-kind food collection."""

from __future__ import annotations

from math import ceil

from goods import Goods
from nutrition import appetite_units


def levy_capacity(agent, reserve_units):
    """Return collectible food without exceeding a quarter of initial surplus."""
    cap = getattr(agent, 'food_levy_cap_this_turn', None)
    if cap is None:
        personal_reserve = 0 if agent.is_corporation else appetite_units(agent)
        initial_surplus = max(0, agent.inv_get(Goods.food, 0) - personal_reserve)
        cap = ceil(initial_surplus * 0.25)
        agent.food_levy_cap_this_turn = cap
    return max(0, min(agent.inv_get(Goods.food, 0) - reserve_units,
                      cap - getattr(agent, 'food_levied_this_turn', 0)))


def record_levy(agent, units):
    agent.food_levied_this_turn = getattr(agent, 'food_levied_this_turn', 0) + units
