"""
wealth_collector.py — Unified state snapshotting and distribution metrics for wealth diagnostics.
"""

import math
from goods import Goods

OUTPUT_TO_CAT = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furniture: 'Furniture'}
CAT_LABELS = ['Food', 'Wood', 'Furniture', 'Trader', 'Institutions']


class WealthCollector:
    """Stateful snapshot recorder for two-region and multi-region simulations."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.snapshots = {'Region_A': {}, 'Region_B': {}}
        self.cumulative_births = 0
        self.cumulative_deaths = 0
        self.current_t = 0
        self._prev_agent_ids = set()
        self._seeded = False

    def record_turn(self, t, region_a, region_b):
        """Record birth/death deltas and wealth snapshots for simulation turn t."""
        self.current_t = t
        current_ids = {a.id for a in region_a.agents} | {a.id for a in region_b.agents}
        if not self._seeded:
            self._prev_agent_ids = current_ids
            self._seeded = True
        else:
            self.cumulative_births += len(current_ids - self._prev_agent_ids)
            self.cumulative_deaths += len(self._prev_agent_ids - current_ids)
            self._prev_agent_ids = current_ids

        if t % 10 == 0:
            for rname, region in [('Region_A', region_a), ('Region_B', region_b)]:
                bank = region.bank
                cat_agents = {c: [] for c in CAT_LABELS}
                for a in region.agents:
                    wealth = a.cash + bank.deposits.get(a, 0)
                    debt = sum(l.principle - l.principle_paid for l in a.loans) if a.loans else 0
                    if a.is_trader:
                        cat_agents['Trader'].append((wealth, debt, a.id))
                    elif a.is_government:
                        gov_food_price = region.recipes.get(Goods.food, {}).get('price', 1.0)
                        gov_food = region.gov.food_inventory * gov_food_price
                        cat_agents['Institutions'].append((wealth + gov_food, debt, -10))
                    else:
                        cat = OUTPUT_TO_CAT.get(a.output, 'Food')
                        cat_agents[cat].append((wealth, debt, a.id))
                bank_wealth = bank.equity
                bank_liab = bank.total_liabilities
                cat_agents['Institutions'].append((bank_wealth, bank_liab, -20))
                charity = region.charity
                food_price = region.recipes.get(Goods.food, {}).get('price', 1.0)
                charity_wealth = charity.agent.cash + bank.deposits.get(charity.agent, 0) \
                                 + charity.food_inventory * food_price
                cat_agents['Institutions'].append((charity_wealth, 0, -30))
                self.snapshots[rname][t] = cat_agents


def compute_stats(vals):
    """Return (min, max, mean, median, std, count) for a list of numbers."""
    n = len(vals)
    if n == 0:
        return (0, 0, 0, 0, 0, 0)
    s = sorted(vals)
    mn = s[0]
    mx = s[-1]
    avg = sum(vals) / n
    med = s[n // 2]
    var = sum((v - avg) ** 2 for v in vals) / n
    std = math.sqrt(var)
    return (mn, mx, avg, med, std, n)
