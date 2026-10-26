"""Intentionally separate agent age from the ten-turn seasonal cycle."""

SEASONAL_PHASES_PER_CYCLE = 10


def agent_elapsed_years(birth_turn: int, turn: int) -> int:
    """Each elapsed turn is one year in an agent's life."""
    return max(0, int(turn) - int(birth_turn))


def seasonal_cycle_phase(turn: int) -> int:
    return int(turn) % SEASONAL_PHASES_PER_CYCLE


def seasonal_cycle_year(turn: int) -> int:
    return int(turn) // SEASONAL_PHASES_PER_CYCLE + 1
