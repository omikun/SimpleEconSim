"""
Feudal tribute — lords collect a share of serf production in kind.

Under feudalism, serfs owe the lord a portion of their harvest
(tribute_rate, default 50%). This is NOT cash rent — it is grain,
wood, and goods transferred directly into the lord's inventory.
The lord does not need money to eat; tribute feeds the lord's household
and gives the lord surplus goods to sell at market.

Serfs keep their subsistence food reserve (4 food) so the feudal
commons sustain the peasantry as intended by customary tenure.
"""

from goods import Goods
from land_tenure import TenureStatus


def _find_agent(region, agent_id: int):
    """Find agent by ID in region."""
    for a in region.agents:
        if a.id == agent_id:
            return a
    return None


def collect_tribute(region, t: int) -> dict:
    """Lords collect in-kind tribute from serfs on their feudal plots.

    For each FEUDAL plot:
    - Identify serfs assigned to this lord based on plot fraction.
    - Transfer tribute_rate fraction of their output/surplus to the lord.
    - Strictly conserved: serf inventory -> lord inventory.

    Returns: {lord_id: {good: amount_collected}}
    """
    tenure = getattr(region, 'tenure', None)
    if tenure is None or not tenure.plots:
        return {}

    # Identify all active serfs/workers (not lords, traders, or government)
    serfs = [a for a in region.agents
             if not a.is_trader and not a.is_government
             and not getattr(a, 'is_lord', False)
             and a.alive]

    if not serfs:
        return {}

    results = {}
    serfs_count = len(serfs)
    current_idx = 0

    for plot in tenure.plots:
        if plot.tenure != TenureStatus.FEUDAL or plot.tribute_rate <= 0:
            continue

        lord = _find_agent(region, plot.lord_id)
        if lord is None or not lord.alive:
            continue

        # Each lord claims a proportional slice of serfs
        slice_size = max(1, int(serfs_count * plot.fraction))
        assigned = serfs[current_idx:current_idx + slice_size]
        current_idx = (current_idx + slice_size) % serfs_count

        collected = {}
        for serf in assigned:
            # For food: protect 4 subsistence food from tribute
            food_held = serf.inv_get(Goods.food, 0)
            if food_held > 4:
                taxable_food = food_held - 4
                tribute_food = int(taxable_food * plot.tribute_rate)
                if tribute_food > 0:
                    serf.inv_add(Goods.food, -tribute_food)
                    lord.inv_add(Goods.food, tribute_food)
                    collected[Goods.food] = collected.get(Goods.food, 0) + tribute_food

            # For wood and furniture: collect tribute on total held
            for good in (Goods.wood, Goods.furniture):
                held = serf.inv_get(good, 0)
                if held > 0:
                    tribute = int(held * plot.tribute_rate)
                    if tribute > 0:
                        serf.inv_add(good, -tribute)
                        lord.inv_add(good, tribute)
                        collected[good] = collected.get(good, 0) + tribute

        if collected:
            results[plot.lord_id] = collected

    return results
