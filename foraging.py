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
from livelihood_access import effective_access

# A typical shared half-plot right (effective access 0.5) can supply the
# four-unit daily meal. Smaller, leasehold, or enclosed rights yield less.
BASE_FORAGE_YIELD = 8


def can_forage(agent, region) -> bool:
    """Agent can forage if: not a lord, not employed, not trader/corp/gov,
    and the tile has commons access > 0."""
    if (getattr(agent, 'is_native_child', False)
            and agent.age(getattr(region, '_last_turn', 0)) < 14):
        return False
    if getattr(agent, 'is_lord', False):
        return False
    if getattr(agent, 'social_class', None) == 'constable':
        return False
    if getattr(agent, 'military_unit_id', None):
        return False
    if agent.is_trader or agent.is_corporation or agent.is_government:
        return False
    if getattr(agent, 'employer', None) is not None:
        return False
    if (getattr(agent, 'assigned_plot_id', None) is None
            and getattr(agent, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0):
        return False
    return effective_access(agent, region, 'commons_food') > 0.0


def forage_tile(region, t: int) -> int:
    """Eligible agents forage on the tile. Returns total food gathered."""
    if getattr(region, 'is_ocean', False) or getattr(region, 'elevation', 0.0) < 0.0:
        return 0

    tenure = getattr(region, 'tenure', None)
    if tenure is None or (not getattr(region, 'wilderness', False) and not any(
            effective_access(a, region, 'commons_food') > 0 for a in region.agents)):
        return 0

    fertility = region.terrain.get(Goods.food, 1.0)
    total = 0

    for a in region.agents:
        if getattr(a, 'is_native_child', False) and a.age(t) < 14:
            continue
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
                a.temporary_work_share = 0.05
                _record_activity(region, a, t, 1)
                total += 1
            continue

        if not can_forage(a, region):
            continue

        access = effective_access(a, region, 'commons_food')
        max_yield = max(1, int(BASE_FORAGE_YIELD * access * fertility))

        # Cap at daily subsistence need (4 food)
        foraged = min(max_yield, 4)
        if foraged > 0:
            a.inv_add(Goods.food, foraged)
            a.food_foraged += foraged
            a.last_forage_turn = t
            a.temporary_work_share = min(0.25, foraged / 16.0)
            _record_activity(region, a, t, foraged)
            total += foraged

    return total


def _record_activity(region, agent, turn, food_units):
    from run_trace import emit
    emit(region, kind='commons_foraging', record_class='outcome',
         subject={'type': 'agent', 'id': agent.id, 'tile': region.name},
         metric_id='labor.temporary_activity', unit='turn_share',
         after=agent.temporary_work_share,
         formula_id='commons.forage_activity.v1',
         inputs={'food_units': food_units, 'good': Goods.food.name,
                 'access': round(effective_access(agent, region, 'commons_food'), 4),
                 'turn': turn})
