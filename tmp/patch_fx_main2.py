"""Patch econsim_two_region.py main(): connect_regions + per-currency baseline. ASCII only."""

p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

reps = [
    # connect_regions + currencies after trader destination wiring
    ("            trader.destination_region = region_a\n\n    print(f\"Region_A: {len(region_a.agents)} agents, Gov: ${region_a.gov.agent.cash:.2f}\")",
     "            trader.destination_region = region_a\n\n    fx.connect_regions(region_a, region_b, t=0)\n    currencies = [region_a.home_currency, region_b.home_currency]\n\n    print(f\"Region_A: {len(region_a.agents)} agents, Gov: ${region_a.gov.agent.cash:.2f}\")"),
    # per-currency baseline before each turn
    ("    for t in range(1, time_steps + 1):\n        cash_before = ",
     "    for t in range(1, time_steps + 1):\n        curr_before = {c: fx.audit_currency_total([region_a, region_b], c)\n                       for c in currencies}\n        cash_before = "),
]

for old, new in reps:
    assert old in src, "MISSING: " + old[:60]
    src = src.replace(old, new)

open(p, "w").write(src)
print("main2 patch applied")