"""Decompose one Region_B turn to find the conservation break."""
import random
from goods import Goods
from region import Region
import forex as fx
from econsim_two_region import foreign_sell, process_transport
import wealth_lineage, wealth_diagnostic

random.seed(42)
ra = Region("Region_A", 0, 55, {Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rb = Region("Region_B", 0, 55, {Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
ra.recipes[Goods.food]['production'] *= 2
rb.recipes[Goods.wood]['production'] *= 2
ra.destination_region = rb
rb.destination_region = ra
for a in ra.agents + rb.agents:
    if getattr(a, 'is_trader', False):
        a.destination_region = rb if a in ra.agents else ra
fx.connect_regions(ra, rb, 0)
wealth_lineage.init_collectors()
wealth_diagnostic.init_collectors()

def comp(r, c):
    b = r.bank
    d = {}
    if r.home_currency == c:
        d['cash'] = sum(a.cash for a in r.agents)
        d['eq'] = b.total_deposits - b.total_liabilities
        d['pool'] = b.fx_pool
        d['char'] = r.charity.agent.cash
    d['wal' + c] = sum(fx.fx_balance(a, c) for a in r.agents)
    d['res' + c] = b.foreign_reserves.get(c, 0.0)
    return d

for t in range(1, 13):
    ra.step(t); rb.step(t)
    process_transport(t, ra, rb)
    foreign_sell(t, ra, rb); foreign_sell(t, rb, ra)
    wealth_lineage.record_turn(t, ra, rb); wealth_diagnostic.record_turn(t, ra, rb)
    for r in (ra, rb):
        r.forex.update(t, bank=r.bank, fx_regime='managed')
        r.forex.save_rate(r)

for r in (ra, rb):
    base = sum(comp(r, r.home_currency).values())
    b0 = dict(comp(r, r.home_currency))
    r.step(13)
    b1 = dict(comp(r, r.home_currency))
    print(r.name, "step13 net:", sum(b1.values()) - base)
    for k in b0:
        d = b1[k] - b0[k]
        if abs(d) > 1e-6:
            print("   ", k, f"{d:+.4f}")