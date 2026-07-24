"""
Module-level state for the single-region simulation (econsim.py).

These are the log dictionaries and config constants used by econsim.py's
module-level functions.  The Region class in region.py owns identical
state per region for multi-region simulations.

Over time these should be absorbed into Region, Agent, Bank, or Government
as appropriate.
"""

from collections import defaultdict
from goods import Goods

# Simulation constants
number_of_agents = 110
time_steps = 300
probability_birth = 0.04
probability_death = 0.05
birth_gap = 7
max_career_switches = 5
starvation_limit = 20
over_production_derate = 0.5

# Shared config objects
recipes = {}
goods = [Goods.food, Goods.wood, Goods.furniture, Goods.gov]
total_production = defaultdict(int)
agent_id_counter = 0
governments = []
default_government = None

# Log dictionaries (used by econsim.py)
population_log = {}
inventory_log = {}
hungry_log = {}
production_log = {}
demand_ratio_log = dict()
supply_log = dict()
demand_log = dict()
per_capita_inventory = dict()
cash_log = {}
gini_log = {}
total_cash_log = []
bank_cash_log = []
price_log = {Goods.food: [], Goods.wood: [], Goods.furniture: []}
sold_log = {Goods.food: [], Goods.wood: [], Goods.furniture: []}
bought_log = dict()
dead_pop = [0]
dead_starved_population = [0]
total_population = []
population_change_rate_log = []
gdp_log = []
gdp_by_profession_log = {Goods.food: [], Goods.wood: [], Goods.furniture: []}