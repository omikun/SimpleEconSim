"""config.py — constants, scenario presets and player dials for Commonweal.

1 tick = 1 season (D1).  150 years = 600 ticks.  All "free parameters" live here
so the model fits in one head.
"""
from dataclasses import dataclass, asdict

SEASONS = 4
SEASON_NAMES = ("spring", "summer", "autumn", "winter")
AWAKE = 16.0            # waking hours per day
MIN_LEISURE = 4.0       # a person never works below this much free time voluntarily
ADULT_AGE = 15 * SEASONS
OLD_AGE = 60 * SEASONS

# Harvest multipliers per season (land) and foraging
LAND_MULT = (0.6, 1.0, 1.6, 0.0)
FORAGE_MULT = (0.8, 1.0, 1.4, 0.4)
YIELD_A = 1.00          # land yield coefficient
FORAGE_A = 0.30
HOURS_EXP = 0.7         # diminishing returns to hours
NEED_ADULT = 1.0        # food units per season
NEED_CHILD = 0.5
SPOIL = 0.12            # share of stored food lost per season

PRACTICES = ("festival", "song", "weaving", "herbal_medicine", "storytelling", "mutual_aid")

# Presets (B): how capitalism is allowed to start
PRESETS = {
    "endogenous": {"desc": "Harvest luck and lending only (B1)", "merchant_year": None, "tax_year": None},
    "merchant":   {"desc": "Outside merchants buy surplus food for cash from year 30 (B2)", "merchant_year": 30, "tax_year": None},
    "tax":        {"desc": "An outside state demands a cash tax from year 30 (B3)", "merchant_year": 30, "tax_year": 30},
}


@dataclass
class Dials:
    """Policy dials the observer may turn (A1).  Defaults = laissez-faire."""
    land_alienable: bool = True    # may land be foreclosed / sold?  (False = customary tenure)
    hours_cap: float = 14.0        # legal maximum working day for hired labour
    relief_levy: float = 0.0       # share of owners' cash above a floor taxed into poor relief
    usury_cap: float = 0.25        # maximum interest per season

    def to_dict(self):
        return asdict(self)


@dataclass
class Params:
    n_start: int = 160
    grid_w: int = 20
    grid_h: int = 12
    plots_per_person: float = 0.62
    cash_start: float = 20.0
    price_start: float = 1.0
    base_interest: float = 0.04
    emp_hours_start: float = 8.0
    tech_cost: float = 12.0
    tech_gain: float = 0.25
    merchant_cash: float = 4000.0
    export_price: float = 0.8
    tax_per_adult: float = 0.35
    seed: int = 1
    preset: str = "endogenous"
