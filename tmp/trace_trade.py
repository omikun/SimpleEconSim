#!/usr/bin/env python3
"""
Trace every cash movement inside _trade() on the first turn.
"""
import sys
sys.path.insert(0, '.')

from region import Region, get_total_cash
from goods import Goods
from logger import logInit
from econsim_two_region import foreign_sell
import random

logInit()
random.seed(42)

rA = Region('Region_A', t=0, number_of_agents=110,
            profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rB = Region('Region_B', t=0, number_of_agents=110,
            profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
rA.recipes[Goods.food]['production'] *= 2
rB.recipes[Goods.wood]['production'] *= 2
rA.destination_region = rB
rB.destination_region = rA
for trader in rA.agents:
    if trader.is_trader:
        trader.destination_region = rB
for trader in rB.agents:
    if trader.is_trader:
        trader.destination_region = rA

t = 1

def snap(region):
    ac = sum(a.cash for a in region.agents)
    td = region.bank.total_deposits
    tl = region.bank.total_liabilities
    cc = region.charity.cash
    return ac + (td - tl) + cc

# Run preliminaries to get to _trade
for a in rA.agents:
    a.clear_wealth_cache()
for a in rB.agents:
    a.clear_wealth_cache()
rA.charity.collect_donations(t, rA.agents, rA.bank)
rB.charity.collect_donations(t, rB.agents, rB.bank)
newA = rA._run_labour(t)
newB = rB._run_labour(t)
if newA: rA.agents.extend(newA)
if newB: rB.agents.extend(newB)
rA._produce(t)
rB._produce(t)

# Now we're about to enter _trade. Snap before.
before = snap(rA) + snap(rB)
print(f"Before _trade: total=${before:.2f}")

# Trace _trade manually for Region A
trade_goods = [Goods.food, Goods.wood, Goods.furniture]
recipes = rA.recipes
agents = rA.agents

# --- PayDepositInterest ---
td_before = rA.bank.total_deposits
agent_cash_before = sum(a.cash for a in agents)
rA.bank.PayDepositInterest(agents)
td_after = rA.bank.total_deposits
agent_cash_after = sum(a.cash for a in agents)
print(f"  PayDepositInterest: td={td_before:.2f}->{td_after:.2f} "
      f"agents={agent_cash_before:.2f}->{agent_cash_after:.2f} "
      f"net={(td_after-td_before)+(agent_cash_after-agent_cash_before):+.2f}")

# --- _decide_borrow_deposit ---
all_goods_price = sum(recipes[g]['price'] for g in trade_goods)
food_price = recipes[Goods.food]['price']
td_before = rA.bank.total_deposits
tl_before = rA.bank.total_liabilities
ac_before = sum(a.cash for a in agents)
rA._decide_borrow_deposit(agents, all_goods_price, food_price, t)
td_after = rA.bank.total_deposits
tl_after = rA.bank.total_liabilities
ac_after = sum(a.cash for a in agents)
net = (td_after - td_before) - (tl_after - tl_before) + (ac_after - ac_before)
print(f"  _decide_borrow_deposit: td={td_before:.2f}->{td_after:.2f} "
      f"tl={tl_before:.2f}->{tl_after:.2f} agents={ac_before:.2f}->{ac_after:.2f} "
      f"net={net:+.2f}")

# --- Single-pass bid/ask gathering ---
before_net = rA.bank.total_deposits - rA.bank.total_liabilities + sum(a.cash for a in agents) + rA.charity.cash

desired_food = 16
desired_wood = 10
desired_furn = max(1, int(16 / max(1, recipes[Goods.furniture]['price'])))
desires = {Goods.food: desired_food, Goods.wood: desired_wood, Goods.furniture: desired_furn}
prices = {g: recipes[g]['price'] for g in trade_goods}
total_asks = {g: 0 for g in trade_goods}
total_bids = {g: 0 for g in trade_goods}
for a in agents:
    ar = recipes[a.output]
    is_emp = a.employer is not None
    mult = a.consumption_multiplier
    for g in trade_goods:
        p = prices[g]
        d = desires[g]
        rA._withdraw_if_needed(a, p, d)
        bid = rA._calculate_bid(a, g, p, d, ar, is_emp, mult)
        a.bid = bid
        a.remainingCash -= bid * p
        total_bids[g] += bid
        ask = rA._calculate_ask(a, g, p, is_emp)
        a.ask = ask
        total_asks[g] += ask

after_gather = rA.bank.total_deposits - rA.bank.total_liabilities + sum(a.cash for a in agents) + rA.charity.cash
print(f"  Bid/ask gathering: net={after_gather - before_net:+.6f}")

# --- Per-good execution ---
for good in trade_goods:
    ta = total_asks[good]
    tb = total_bids[good]
    if ta == 0 and tb == 0:
        rA._price_decay(good)
        print(f"  {good}: no asks or bids, price decay")
        continue
    demand_ratio = 5.0 if ta == 0 else tb / ta
    price = rA._set_price(demand_ratio, good)
    if min(ta, tb) == 0:
        print(f"  {good}: no trades (asks={ta} bids={tb})")
        continue
    
    snap_before = rA.bank.total_deposits - rA.bank.total_liabilities + sum(a.cash for a in agents) + rA.charity.cash
    
    total_bought, total_cash_purchases = rA._buy(t, good, price, ta)
    snap_after_buy = rA.bank.total_deposits - rA.bank.total_liabilities + sum(a.cash for a in agents) + rA.charity.cash
    
    askers = sorted(agents, key=lambda a: a.ask, reverse=True)
    total_cash_sales, total_sold = rA._sell(askers, good, price, t, total_bought, total_cash_purchases)
    snap_after_sell = rA.bank.total_deposits - rA.bank.total_liabilities + sum(a.cash for a in agents) + rA.charity.cash
    
    print(f"  {good}: price={price:.2f} bids={tb} asks={ta} "
          f"bought={total_bought} sold={total_sold} "
          f"cash_buy={total_cash_purchases:.2f} cash_sell={total_cash_sales:.2f} "
          f"delta_buy={snap_after_buy-snap_before:+.4f} delta_sell={snap_after_sell-snap_after_buy:+.4f}")

# Charity food purchase
after_charity = rA.bank.total_deposits - rA.bank.total_liabilities + sum(a.cash for a in agents) + rA.charity.cash

total_system = rA.bank.total_deposits - rA.bank.total_liabilities + sum(a.cash for a in agents) + rA.charity.cash
print(f"  Region A after full _trade: ${total_system:.2f}")

# Also check: is this region alone leaking? 
# What about inter-region transfers during foreign_sell BEFORE _trade for the other region?
# Actually no — the two regions are independent at this point.

print(f"\nPre-existing leak before any of my changes? The _trade leak may be inherent.")
print(f"Key observation: the system had {before:.2f} before _trade, {total_system:.2f} after.")
print(f"Difference: ${before - total_system:+.4f}")

# Now let's check if the _cash_purchases vs _cash_sales mismatch is the source
print(f"\nChecking: total cash purchases in _buy = sold * price in _sell?")
print(f"  In the code, _buy deducts cash from buyers, _sell adds cash to sellers.")
print(f"  If they disagree, the difference is the leak source.")