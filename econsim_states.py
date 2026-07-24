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
num_agents = 110
time_steps = 300
p_birth = 0.04
p_death = 0.05
birthGap = 7
max_career_switches = 5
starve_limit = 20
overProductionDerate = 0.5

# Shared config objects
recipes = {}
goods = [Goods.food, Goods.wood, Goods.furn, Goods.gov]
totalProd = defaultdict(int)
agentid = 0
governments = []
default_gov = None

# Log dictionaries (used by econsim.py)
pop_log = {}
inv_log = {}
hungry_log = {}
production_log = {}
demand_ratio_log = dict()
supply_log = dict()
demand_log = dict()
perCapitaInv = dict()
cash_log = {}
gini_log = {}
totalCash_log = []
bankCash_log = []
price_log = {Goods.food: [], Goods.wood: [], Goods.furn: []}
sold_log = {Goods.food: [], Goods.wood: [], Goods.furn: []}
bought_log = dict()
dead_pop = [0]
deadstarve_pop = [0]
total_pop = []
pop_change_rate_log = []
gdp_log = []
gdp_by_profession_log = {Goods.food: [], Goods.wood: [], Goods.furn: []}