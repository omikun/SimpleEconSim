"""Shared soil timing for ecological state and attributed depletion estimates."""

SOIL_DEGRADATION_SCALE = 0.1


def soil_change(extraction, regeneration, degradation_scale=SOIL_DEGRADATION_SCALE):
    """Slow a negative nutrient balance tenfold; retain natural recovery speed."""
    balance = regeneration - extraction
    return balance * degradation_scale if balance < 0 else balance
