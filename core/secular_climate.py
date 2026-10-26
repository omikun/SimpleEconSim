"""
secular_climate.py — Multi-Decade Secular Climate Cycles and Ecological Regimes.

Models multi-turn secular climate shifts (such as the Medieval Warm Optimum and the
Little Ice Age) beyond the 10-turn intra-year seasonal curve.

Historical dynamics:
1. Medieval Warm Optimum: Extended growing seasons, higher harvest yields (+15-25%),
   mild winters, and agrarian frontier expansion.
2. Little Ice Age / Secular Cooling: Abrupt multi-year cooling, torrential rains, shortened
   growing seasons, harvest failures (-25-35%), granary depletion, and famine vulnerability.
"""

from __future__ import annotations
import math
from typing import Dict, Any

DEFAULT_CYCLE_LENGTH = 80
SECULAR_CYCLE_TURNS = DEFAULT_CYCLE_LENGTH


def get_secular_climate(turn: int | None, cycle_length: int = DEFAULT_CYCLE_LENGTH) -> Dict[str, Any]:
    """Compute the secular climate anomaly, current climatic epoch, and yield modifiers."""
    if turn is None:
        t = 0
    else:
        t = int(turn)

    # Normalized phase in the multi-decade cycle [0.0, 1.0)
    phase = (t % cycle_length) / float(cycle_length)

    # Base sine anomaly ranging from -0.50 to +0.50
    # Phase 0.0 -> 0.25: Warming toward peak (turns 0-20)
    # Phase 0.25 -> 0.50: Cooling toward temperate (turns 20-40)
    # Phase 0.50 -> 0.75: Deep secular cooling / Little Ice Age (turns 40-60)
    # Phase 0.75 -> 1.00: Warming recovery (turns 60-80)
    anomaly = 0.50 * math.sin(2.0 * math.pi * phase)

    if anomaly > 0.15:
        epoch = "warm_optimum"
        epoch_name = "Warm Optimum"
        epoch_icon = "☀️"
        epoch_code = "warm"
        # Increased agricultural yield up to +25%
        yield_multiplier = max(1.0, 1.0 + (anomaly * 0.50))
        col_modifier = 0.95  # Mild weather slightly eases heating/fuel cost
        desc = "Prolonged mild temperatures and longer growing seasons boost agricultural yields."
    elif anomaly < -0.15:
        epoch = "ice_age"
        epoch_name = "Little Ice Age"
        epoch_icon = "❄️"
        epoch_code = "cold"
        # Depressed agricultural yield down to -35%
        yield_multiplier = max(0.65, 1.0 + (anomaly * 0.70))
        col_modifier = 1.15  # Harsh cold raises fuel and winter clothing cost of living (+15%)
        desc = "Colder seasons and torrential rains cause crop blights, rotting harvests, and famine vulnerability."
    else:
        epoch = "temperate"
        epoch_name = "Temperate"
        epoch_icon = "⛅"
        epoch_code = "temperate"
        yield_multiplier = 1.0
        col_modifier = 1.0
        desc = "Balanced climatic conditions with standard seasonal variability."

    return {
        'turn': t,
        'anomaly': round(anomaly, 3),
        'epoch': epoch,
        'epoch_name': epoch_name,
        'epoch_icon': epoch_icon,
        'epoch_code': epoch_code,
        'yield_multiplier': round(yield_multiplier, 3),
        'col_modifier': round(col_modifier, 3),
        'description': desc,
    }
