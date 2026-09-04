"""
Commons foraging — serfs on feudal land gather food from shared pastures,
forests, and fisheries. This is not charity; it is a customary RIGHT tied
to the feudal social contract. Enclosure destroys this right.

Yield scales with tile.tenure.commons_access:
  FEUDAL (1.0):    full foraging — serfs feed themselves
  LEASEHOLD (0.5): reduced — partial commons access
  ENCLOSED (0.0):  no foraging — must buy food on market

Employed workers do NOT forage (they are at the factory/workshop).
Lords do NOT forage (they collect tribute).
Traders and government agents do not forage.
Homesteaders on wilderness tiles forage according to wilderness rules.
"""

from goods import Goods

BASE_FORAGE_YIELD = 4  # food/turn at full commons access (daily subsistence)


def can_forage(agent, region) -> bool:
    """Agent can forage if: not a lord, not employed, not trader/corp/gov,
    and the tile has commons access > 0."""
    if getattr(agent, 'is_lord', False):
        return False
    if agent.is_trader or agent.is_corporation or agent.is_government:
        return False
    if getattr(agent, 'employer', None) is not None:
        return False
    tenure = getattr(region, 'tenure', None)
    if tenure is None or tenure.commons_access <= 0.0:
        return False
    return True


def forage_tile(region, t: int) -> int:
    """Eligible agents forage on the tile. Returns total food gathered."""
    if getattr(region, 'is_ocean', False) or getattr(region, 'elevation', 0.0) < 0.0:
        return 0

    tenure = getattr(region, 'tenure', None)
    if tenure is None or tenure.commons_access <= 0.0:
        return 0

    fertility = region.terrain.get(Goods.food, 1.0)
    access = tenure.commons_access
    max_yield = max(1, int(BASE_FORAGE_YIELD * access * fertility))
    total = 0

    for a in region.agents:
        # Check if homesteader on wilderness
        if getattr(region, 'wilderness', False):
            if not getattr(a, 'is_homesteader', False):
                continue
            last = getattr(a, 'last_forage_turn', t)
            # Homesteaders forage +1 every 3 turns
            if t - last >= 3:
                a.inv_add(Goods.food, 1)
                a.last_forage_turn = t
                a.food_foraged += 1
                total += 1
            continue

        if not can_forage(a, region):
            continue

        # Cap at daily subsistence need (4 food)
        foraged = min(max_yield, 4)
        if foraged > 0:
            a.inv_add(Goods.food, foraged)
            a.food_foraged += foraged
            a.last_forage_turn = t
            total += foraged

    return total
