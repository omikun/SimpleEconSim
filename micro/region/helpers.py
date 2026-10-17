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
    Goods.cotton: {
        'commodity': Goods.cotton, 'production': 3, 'price': 3.0, 'numInput': 0,
        'maxtotalprod': 1200, 'maxinv': 15,
    },
    Goods.iron_ore: {
        'commodity': Goods.iron_ore, 'production': 2, 'price': 4.0, 'numInput': 0,
        'maxtotalprod': 800, 'maxinv': 20,
    },
    Goods.iron: {
        'commodity': Goods.iron, 'production': 1, 'input': Goods.iron_ore,
        'numInput': 2, 'price': 16.0, 'maxtotalprod': 400, 'maxinv': 10,
    },
    Goods.coal: {
        'commodity': Goods.coal, 'production': 3, 'price': 3.5, 'numInput': 0,
        'maxtotalprod': 1000, 'maxinv': 25,
    },
    Goods.tobacco: {
        'commodity': Goods.tobacco, 'production': 2, 'price': 5.0, 'numInput': 0,
        'maxtotalprod': 600, 'maxinv': 15,
    },
    Goods.sugar: {
        'commodity': Goods.sugar, 'production': 2, 'price': 4.5, 'numInput': 0,
        'maxtotalprod': 700, 'maxinv': 20,
    },
    Goods.tea: {
        'commodity': Goods.tea, 'production': 2, 'price': 6.0, 'numInput': 0,
        'maxtotalprod': 500, 'maxinv': 15,
    },
    Goods.fine_textiles: {
        'commodity': Goods.fine_textiles, 'production': 1, 'input': Goods.cloth,
        'numInput': 2, 'price': 50.0, 'maxtotalprod': 200, 'maxinv': 5,
        'is_luxury': True, 'prestige_rating': 10.0,
    },
    Goods.porcelain: {
        'commodity': Goods.porcelain, 'production': 1, 'input': Goods.iron_ore,
        'numInput': 1, 'price': 55.0, 'maxtotalprod': 150, 'maxinv': 5,
        'is_luxury': True, 'prestige_rating': 12.0,
    },
    Goods.rum: {
        'commodity': Goods.rum, 'production': 1, 'input': Goods.sugar,
        'numInput': 2, 'price': 30.0, 'maxtotalprod': 300, 'maxinv': 10,
        'is_luxury': True, 'prestige_rating': 6.0,
    },
    Goods.foreign_luxuries: {
        'commodity': Goods.foreign_luxuries, 'production': 1, 'price': 100.0, 'numInput': 0,
        'maxtotalprod': 100, 'maxinv': 5,
        'is_luxury': True, 'prestige_rating': 25.0, 'import_only': True,
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
