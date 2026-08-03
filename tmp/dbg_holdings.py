"""Debug: trace how trader 417-F accumulates foreign food holdings."""
import sys, random, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.argv = ['econsim_two_region.py', '16']

import econsim_two_region as sim
from goods import Goods
import wealth_lineage, wealth_diagnostic

random.seed(42)

region_a = sim.Region("Region_A", t=0, number_of_agents=200,
                       profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037},
                       number_of_traders=3)
region_b = sim.Region("Region_B", t=0, number_of_agents=200,
                       profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05},
                       number_of_traders=3)
region_a.recipes[Goods.food]['production'] *= 2
region_b.recipes[Goods.wood]['production'] *= 2
region_a.destination_region = region_b
region_b.destination_region = region_a
for tr in region_a.agents:
    if getattr(tr, 'is_trader', False):
        tr.destination_region = region_b
for tr in region_b.agents:
    if getattr(tr, 'is_trader', False):
        tr.destination_region = region_a
from transporter import Route
region_a.route = Route("A->B", region_a, region_b, base_delay=sim.TRANSPORT_DELAY)
region_b.route = Route("B->A", region_b, region_a, base_delay=sim.TRANSPORT_DELAY)
sim.fx.connect_regions(region_a, region_b, t=0)

wealth_lineage.init_collectors()
wealth_diagnostic.init_collectors()

def dump(tag, tr, turn):
    if getattr(tr, 'trade_good', None) == Goods.food:
        print(f"T{turn} {tag} {tr.name()} trade_good=FOOD"
              f" local_food={tr.inv_get(Goods.food,0)}"
              f" export_food={tr.inventory_export[Goods.food.value]}"
              f" foreign_food={tr.inventory_foreign[Goods.food.value]}"
              f" route_food={region_b.route.holdings_of(tr).get(Goods.food,0)}"
              f" cost_food={tr.cost_get(Goods.food,0):.2f}"
              f" cash={tr.cash:.0f}")

for t in range(1, 17):
    region_a.pending_imports = sim._pending_imports(region_a, region_b)
    region_b.pending_imports = sim._pending_imports(region_b, region_a)
    region_a._auction_import_sales = {}
    region_b._auction_import_sales = {}
    region_a.step(t)
    region_b.step(t)
    region_a.route.advance(); region_a.route.deliver_pending()
    region_b.route.advance(); region_b.route.deliver_pending()
    sim.settle_trade(t, region_a, region_b)
    sim.settle_trade(t, region_b, region_a)
    sim.fx.cycle_market(region_a, region_b, t)
    if t in (2, 4, 8, 16):
        for tr in region_a.trader_agents + region_b.trader_agents:
            if getattr(tr, 'id', 0) in (417, 415):
                dump('A' if tr.home_region == 'Region_A' else 'B', tr, t)