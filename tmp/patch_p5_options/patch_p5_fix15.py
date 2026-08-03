"""Phase 5 fix 15: (a) import cost-recovery floor + (b) bigger FX reserves.

(a) Opportunity-cost floor on import asks: a trader must never quote an import
below what the good is worth AT HOME right now.  Between purchase and sale the
home price can rise (ref inflation), so the stale cost_basis under-covers the
opportunity cost.  Use max(cost_basis, current home recipe price) as the base:
    ask = max(cost_basis, home_price_now) * (1 + margin) / ((1-tau) * buy_rate)
guarantees zero-margin sales can't happen (loss prevention).

(b) The 100-turn run drained BOTH desks to zero foreign reserves (rates pinned
at the 2.0 band ceiling).  Seed and target reserves were far below the trade
volume.  Raise: DESK_INITIAL_RESERVES 1000 -> 3000, DESK_TARGET_RESERVES
1200 -> 2500, so the managed float has room and convertibility doesn't stall.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """        cost_home = max(0.05, trader.cost_get(good, 0))
        margin = self.IMPORT_MARGIN_MIN + ("""
new = """        home_price_now = self.recipes.get(good, {}).get('price', 0)
        cost_home = max(0.05, trader.cost_get(good, 0), home_price_now)
        margin = self.IMPORT_MARGIN_MIN + ("""
assert old in src, "import-ask-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("import opportunity-cost floor applied")

p2 = "/Users/sli/Code/forex.py"
src2 = open(p2).read()
old2 = """DESK_TARGET_RESERVES = 1200.0    # desired holdings of each foreign currency
DESK_INITIAL_RESERVES = 1000.0   # war-chest of foreign currency at start"""
new2 = """DESK_TARGET_RESERVES = 2500.0    # desired holdings of each foreign currency
DESK_INITIAL_RESERVES = 3000.0   # war-chest of foreign currency at start
# (raised from 1000/1200: 100-turn runs drained both desks to 0 reserves and
#  pinned the rate at the band ceiling — initial stock was far below the
#  realized trade volume, stalling convertibility)"""
assert old2 in src2, "reserves-anchor"
src2 = src2.replace(old2, new2)
open(p2, "w").write(src2)
print("desk reserves raised (init 3000 / target 2500)")