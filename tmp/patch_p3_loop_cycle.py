"""Phase 3: call fx.cycle_market each turn in the main loop."""
p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

old = """        region_a.step(t)
        region_b.step(t)
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)
        foreign_sell(t, region_b, region_a)
        wealth_lineage.record_turn(t, region_a, region_b)
        wealth_diagnostic.record_turn(t, region_a, region_b)"""
new = """        region_a.step(t)
        region_b.step(t)
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)
        foreign_sell(t, region_b, region_a)
        fx.cycle_market(region_a, region_b, t)
        wealth_lineage.record_turn(t, region_a, region_b)
        wealth_diagnostic.record_turn(t, region_a, region_b)"""
assert old in src, "loop-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("fx.cycle_market wired into main loop")