"""Gameplay pollution indices per unit of actual output, not firm count.

Coefficients are balancing parameters, not physical emission factors. Nitrates
represent the game's fertilizer/mineral chemical supply; logging and carpentry
have no generic smokestack or industrial-effluent charge.
"""
from goods import Goods

# (air particulates / combustion, industrial water effluent)
EMISSION_FACTORS = {
    Goods.nitrates: (0.35, 0.30),
    Goods.coal: (0.50, 0.25),
    Goods.iron_ore: (0.15, 0.30),
    Goods.iron: (0.80, 0.50),
    Goods.porcelain: (0.50, 0.15),
    Goods.cloth: (0.0, 0.25),
    Goods.fine_textiles: (0.0, 0.30),
    Goods.rum: (0.10, 0.40),
}
CROPS = (Goods.food, Goods.cotton, Goods.sugar, Goods.tobacco, Goods.tea)


def output_emissions(region, good, quantity):
    """Return untreated flows for one production receipt (independent or firm)."""
    quantity = max(0.0, float(quantity))
    air, water = EMISSION_FACTORS.get(good, (0.0, 0.0))
    fertilized = (getattr(region, 'farming_regime', 'rotation') == 'intensive'
                  or getattr(region, 'use_fertilizer', False)
                  or getattr(region, 'mandate_fertilizer', False))
    pesticides = (getattr(region, 'use_pesticides', False)
                  or getattr(region, 'mandate_pesticides', False))
    techs = getattr(getattr(region, 'owner_nation', None), 'unlocked_techs', set())
    return {'air': quantity * air, 'industrial_water': quantity * water,
            'fertilizer_runoff': quantity * 0.02 if good in CROPS and fertilized else 0.0,
            'pesticide_soil': quantity * 0.03 if good in CROPS and pesticides
            and 'biological_pest_control' not in techs else 0.0}


def pollution_controls(region):
    names = {getattr(b, 'name', '') for b in getattr(region, 'buildings', ())}
    water_factor = (0.3 if 'trunk_sewer' in names else 1.0)
    if 'water_filtration_plant' in names or getattr(region, 'clean_water_act', False):
        water_factor *= 0.3
    return ('smoke_scrubber' in names), water_factor
