"""Located institutional stores for lightweight scenario fixtures."""
from types import SimpleNamespace
from food_store import FoodStore


class LocatedGovernment(FoodStore, SimpleNamespace):
    pass


def stock_defense_site(world, units=60):
    """Author existing opening grain at the defense site; create no grain."""
    nation = next(n for n in world['nations'] if n.name == 'Egypt')
    gov = nation.government
    source = next(t for t in nation.tiles if t.name == gov.food_default_site)
    name = world['scenario_state']['geography']['sites']['Tel el Kebir']['tile']
    target = next(t for t in nation.tiles if t.name == name)
    amount = min(units, gov.food_at(source))
    gov.add_food(source, -amount)
    gov.add_food(target, amount)
    return target
