"""Deterministic corporate production arithmetic shared by execution and forecasts."""


def active_slots(workers, available, input_units):
    return int(min(workers, available // input_units)) if input_units > 0 else int(workers)


def production_per_slot(base, workers, terrain, shift, practice, machinery):
    synergy = 1.0 + (.15 if workers < 4 else .20 if workers < 8 else .25 if workers < 12 else .30) * workers
    units = base * synergy * terrain * shift * practice
    if machinery < 1:
        units *= .5
    elif machinery > 1:
        units *= 1.0 + .40 * min(3, machinery - 1)
    return units


def success_probability(hungry_steps, stock, maximum, resource_factor=1.0):
    chance = 1.0
    if hungry_steps > 0:
        chance *= 1 / (1 + hungry_steps * .2)
    chance *= resource_factor
    return chance * max(0, 1 - stock / maximum)


def output_units(successful_slots, units_per_slot):
    return int(successful_slots * units_per_slot)
