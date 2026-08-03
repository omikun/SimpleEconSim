"""Fix foreign_sell loginfo — references vars removed by Option-1 rewrite
(total_trader_profit / total_bank_recycle / total_tariff only existed in the
deleted goods-dump loop).  The t%50 block crashed 100-turn runs at turn 50."""
p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

old = """    if total_sold_value > 0 and t % 50 == 0:
        loginfo(t, f"TRADE {source_region.name}->{destination_region.name}: "
                f"sold {total_sold_quantity} units worth ${total_sold_value:.2f} "
                f"({dict(trade_volumes)})"
                f"  trader ${total_trader_profit:.2f}"
                f"  bank recycle ${total_bank_recycle:.2f}"
                f"  tariff ${total_tariff:.2f}")"""
new = """    if total_sold_value > 0 and t % 50 == 0:
        loginfo(t, f"TRADE {source_region.name}->{destination_region.name}: "
                f"sold {total_sold_quantity} units worth ${total_sold_value:.2f} "
                f"through the priced auction")"""
assert old in src, "log-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("foreign_sell loginfo fixed (no stale vars)")