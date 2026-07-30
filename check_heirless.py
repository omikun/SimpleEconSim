#!/usr/bin/env python3
"""Diagnostic: check heirless rate for wealthy vs poor traders after wealth-based fertility and mortality changes."""
import sys, random
sys.path.insert(0, '.')
from goods import Goods
from region import Region
from logger import logInit
import econsim_two_region as sim
import wealth_lineage as wl

random.seed(42)
logInit()

region_a = Region('Region_A', 0, 110,
                   {Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
region_b = Region('Region_B', 0, 110,
                   {Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
region_a.recipes[Goods.food]['production'] *= 2
region_b.recipes[Goods.wood]['production'] *= 2
region_a.destination_region = region_b
region_b.destination_region = region_a

# Apply the same patches wealth_lineage.main() would use
wl._patch_bank()
wl._patch_lifecycle()

# Run 300 turns with lineage instrumentation
for t in range(1, 301):
    region_a.step(t)
    region_b.step(t)
    sim.process_transport(t, region_a, region_b)
    sim.foreign_sell(t, region_a, region_b)
    sim.foreign_sell(t, region_b, region_a)
    for a in region_a.agents + region_b.agents:
        if hasattr(a, 'parent') and a.parent is not None:
            wl.parent_map[a.id] = a.parent.id

# Analyze inheritance events
total_trader = 0
heirless_count = 0
has_heir_count = 0
total_wealth_heirless = 0.0
total_wealth_has_heir = 0.0

for evt in wl.inheritance_events:
    t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
    if prof != 'Trader' or total_val <= 0:
        continue
    total_trader += 1
    if to_gov:
        heirless_count += 1
        total_wealth_heirless += total_val
    else:
        has_heir_count += 1
        total_wealth_has_heir += total_val

print(f"Total trader deaths with wealth: {total_trader}")
if total_trader > 0:
    print(f"  → Gov (no heirs): {heirless_count} ({heirless_count/total_trader*100:.0f}%) total=${total_wealth_heirless:.0f}")
    print(f"  → Heirs:           {has_heir_count} ({has_heir_count/total_trader*100:.0f}%) total=${total_wealth_has_heir:.0f}")

# Also show summary for all professions
print()
for prof in ['Trader', 'Food', 'Wood', 'Furniture', 'Gov']:
    n = hc = hwc = 0
    for evt in wl.inheritance_events:
        t, aid, p, tv, w, d, heirs, tg = evt
        if p != prof:
            continue
        n += 1
        if tg:
            hc += 1
            hwc += tv
    pct = (hc / n * 100) if n else 0
    print(f"  {prof:>12}: {n:>3} deaths, {hc:>3} gov ({pct:.0f}%)")