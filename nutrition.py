"""Continuous household nutrition expressed in daily-equivalent calories.

Food remains a conserved, discrete market good. Calorie balance, hunger severity,
and body energy stores are continuous, so partial meals have proportional effects.
"""

from __future__ import annotations

import math


CALORIES_PER_FOOD = 500.0
DAILY_NEED_KCAL = 2000.0
INITIAL_RESERVE_KCAL = 40000.0
MAX_RESERVE_KCAL = 160000.0
KCAL_PER_KG_FAT = 7700.0


def appetite_units(agent) -> int:
    """Wealth and depleted reserves raise desired intake on a smooth curve."""
    wealth = max(1.0, float(getattr(agent, 'consumption_multiplier', 1.0)))
    reserve = max(0.0, float(getattr(agent, 'energy_reserve_kcal', INITIAL_RESERVE_KCAL)))
    luxury = 6.0 * (1.0 - math.exp(-(wealth - 1.0) / 3.0))
    catch_up = 2.0 * (1.0 - math.exp(-max(0.0, INITIAL_RESERVE_KCAL - reserve) / INITIAL_RESERVE_KCAL))
    return min(12, max(4, round(4.0 + luxury + catch_up)))


def record_intake(agent, food_units: float) -> None:
    """Use intake to update fat reserves and the unmet calorie need this turn."""
    need = float(getattr(agent, 'calorie_need_kcal', DAILY_NEED_KCAL))
    eaten = max(0.0, food_units) * CALORIES_PER_FOOD
    balance = eaten - need
    agent.last_calories_eaten = eaten
    agent.calorie_deficit_kcal = max(0.0, -balance)
    agent.calorie_surplus_kcal = max(0.0, balance)
    agent.energy_reserve_kcal = min(MAX_RESERVE_KCAL, max(0.0,
        float(getattr(agent, 'energy_reserve_kcal', INITIAL_RESERVE_KCAL)) + balance))
    agent.hungry_steps = (max(0.0, float(agent.hungry_steps)) + agent.calorie_deficit_kcal / need
                          if agent.calorie_deficit_kcal > 0 else 0.0)
    agent.mem_push('mem_hunger', agent.calorie_deficit_kcal / need)


def feed_emergency_meal(agent, food_units: float) -> None:
    """Apply a conserved food transfer already consumed outside the life cycle."""
    calories = max(0.0, food_units) * CALORIES_PER_FOOD
    previous_deficit = float(getattr(agent, 'calorie_deficit_kcal', 0.0))
    agent.last_calories_eaten = float(getattr(agent, 'last_calories_eaten', 0.0)) + calories
    agent.calorie_deficit_kcal = max(0.0, previous_deficit - calories)
    remainder = max(0.0, calories - previous_deficit)
    agent.calorie_surplus_kcal = float(getattr(agent, 'calorie_surplus_kcal', 0.0)) + remainder
    agent.energy_reserve_kcal = min(MAX_RESERVE_KCAL,
        float(getattr(agent, 'energy_reserve_kcal', INITIAL_RESERVE_KCAL)) + calories)
    need = float(getattr(agent, 'calorie_need_kcal', DAILY_NEED_KCAL))
    agent.hungry_steps = max(0.0, float(agent.hungry_steps) - calories / need)


def queue_emergency_meal(agent, food_units: int) -> None:
    """Reserve physically transferred public food for the next consumption step."""
    agent.emergency_food_units = max(0, int(agent.emergency_food_units) + int(food_units))


def starvation_hazard(agent) -> float:
    """Daily-equivalent death risk grows smoothly as body stores run out."""
    deficit = max(0.0, float(getattr(agent, 'calorie_deficit_kcal', 0.0)))
    need = max(1.0, float(getattr(agent, 'calorie_need_kcal', DAILY_NEED_KCAL)))
    reserve = max(0.0, float(getattr(agent, 'energy_reserve_kcal', INITIAL_RESERVE_KCAL)))
    return min(0.8, (1.0 - math.exp(-0.7 * deficit / need)) * math.exp(-reserve / 5000.0))


def fat_kg(agent) -> float:
    return max(0.0, float(getattr(agent, 'energy_reserve_kcal', INITIAL_RESERVE_KCAL))) / KCAL_PER_KG_FAT


def deficit_fraction(agent) -> float:
    need = max(1.0, float(getattr(agent, 'calorie_need_kcal', DAILY_NEED_KCAL)))
    return min(1.0, max(0.0, float(getattr(agent, 'calorie_deficit_kcal', 0.0))) / need)


def food_credit_pressure(agent) -> float:
    """Chance of seeking an emergency food loan as deficits accumulate."""
    return deficit_fraction(agent) * (1.0 - math.exp(-max(0.0, float(agent.hungry_steps)) / 5.0))
