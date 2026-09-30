"""
micro/region/helpers.py — Shared constants and helper functions for regions.
"""

from goods import Goods
from econsim_states import recipes

_recipes_init = {
    Goods.food: {
        'commodity': Goods.food, 'production': 5, 'price': 1, 'numInput': 0,
        'maxtotalprod': 2000, 'maxinv': 20,
    },
    Goods.wood: {
        'commodity': Goods.wood, 'production': 2, 'price': 1, 'numInput': 0,
        'maxtotalprod': 3000, 'maxinv': 10,
    },
    Goods.furniture: {
        'commodity': Goods.furniture, 'production': 1, 'input': Goods.wood,
        'numInput': 2, 'price': 25, 'maxtotalprod': 300, 'maxinv': 5,
    },
    Goods.transport: {
        'commodity': Goods.transport, 'production': 1, 'price': 1, 'numInput': 0,
        'maxtotalprod': 1000, 'maxinv': 1, 'capacity': 10,
    },
    Goods.wool: {
        'commodity': Goods.wool, 'production': 3, 'price': 3.5, 'numInput': 0,
        'maxtotalprod': 1500, 'maxinv': 15,
    },
    Goods.cloth: {
        'commodity': Goods.cloth, 'production': 1, 'input': Goods.wool,
        'numInput': 2, 'price': 18.0, 'maxtotalprod': 400, 'maxinv': 10,
    },
    Goods.nitrates: {
        'commodity': Goods.nitrates, 'production': 2, 'price': 6.0, 'numInput': 0,
        'maxtotalprod': 600, 'maxinv': 20,
    },
    Goods.gov: {
        'commodity': Goods.gov, 'production': 0, 'numInput': 0, 'price': 1,
        'maxtotalprod': 0, 'maxinv': 0,
    },
}

for _g, _r in _recipes_init.items():
    recipes[_g] = _r

DEFAULT_PROFESSION_DISTRIBUTION = {
    Goods.food: 0.65,
    Goods.wool: 0.05,
    Goods.cloth: 0.02,
    Goods.wood: 0.05,
    Goods.furniture: 0.01,
    Goods.transport: 0.08,
}

MAX_AGENTS = 500


def count_agents(agents, good):
    """Number of agents whose output is *good*."""
    return sum(agent.output == good for agent in agents)


def compute_gini(agents, good):
    """Gini coefficient over cash held by agents producing *good*."""
    vals = sorted([agent.cash for agent in agents if agent.output == good])
    n = len(vals)
    if n == 0:
        return 0
    total = sum(vals)
    if total == 0:
        return 0
    weighted_sum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * weighted_sum) / (n * total) - (n + 1) / n


def get_total_cash(agents, bank=None):
    """Total cash in the system: agent cash + bank equity."""
    if bank is None:
        return sum(agent.cash for agent in agents)
    return sum(a.cash for a in agents) + bank.equity
