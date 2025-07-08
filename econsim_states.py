from collections import defaultdict

from goods import Goods

num_agents = 20
recipes = {}
goods = [Goods.food, Goods.wood, Goods.furn, Goods.gov]
overProductionDerate = .5
profession = {Goods.food:'F', Goods.wood:'W', Goods.furn:'C', Goods.gov:'G', Goods.none:'-'}
totalProd = defaultdict(int)
time_steps = 300
p_birth = .04
p_death = .1
birthGap = 7
starve_limit = 20
dead_pop = [0]
deadstarve_pop = [0]
total_pop = []
pop_log = {}
inv_log = {}
hungry_log = {}
production_log = {}
demand_ratio_log = dict()
supply_log = dict()
demand_log = dict()
perCapitaInv = dict()
agentid = 0
govCash = 0
govInv = defaultdict(int)
cash_log = {}
gini_log = {}
totalCash_log = []
bankCash_log = []
price_log = {Goods.food:[], Goods.wood:[], Goods.furn:[]}
sold_log = {Goods.food:[], Goods.wood:[], Goods.furn:[]}
bought_log = dict()
