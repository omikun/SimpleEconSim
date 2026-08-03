"""Phase 3: fix import double-count cash leak in Region._trade.

The import volume was added to local supply (ta) to tilt prices, but the SAME
inflated value was passed to _buy(), letting local buyers purchase imported
units with real cash while no local seller receives it -> buyer cash exits the
audited system (money destruction) equal to imported value x price.

Fix: keep the import-inflated value for price discovery (demand_ratio,
_set_price), but clear the market against LOCAL asks only.  Imports no longer
create phantom purchases; the foreign_sell flow already sells imported goods
to destination buyers.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """            # Imports add to effective supply, suppressing local prices
            if self.import_vol.get(good) and self.import_vol[good]:
                ta += self.import_vol[good][-1]
            demand_ratio = 5.0 if ta == 0 else tb / ta
            self.demand_ratio_log[good].append(demand_ratio)
            self.demand_log[good].append(tb)
            self.supply_log[good].append(ta)
            if max_demand_ratio < demand_ratio and tb > 0:
                max_demand_ratio = demand_ratio
                most_demand_good = good
            price = self._set_price(demand_ratio, good)
            if min(ta, tb) == 0:
                continue
            total_bought, total_cash_purchases = self._buy(t, good, price, ta)"""
new = """            # Imports add to effective supply ONLY for price discovery
            # (suppressing local prices).  The market still clears against
            # LOCAL asks only: imported goods are already sold to destination
            # buyers by foreign_sell, so letting _buy fill against imported
            # units would take real cash out with no local seller to receive
            # it (money destruction = import value).
            price_ta = ta
            if self.import_vol.get(good) and self.import_vol[good]:
                price_ta += self.import_vol[good][-1]
            demand_ratio = 5.0 if price_ta == 0 else tb / price_ta
            self.demand_ratio_log[good].append(demand_ratio)
            self.demand_log[good].append(tb)
            self.supply_log[good].append(price_ta)
            if max_demand_ratio < demand_ratio and tb > 0:
                max_demand_ratio = demand_ratio
                most_demand_good = good
            price = self._set_price(demand_ratio, good)
            if min(ta, tb) == 0:
                continue
            total_bought, total_cash_purchases = self._buy(t, good, price, ta)"""
assert old in src, "import-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("import double-count fix applied to region.py")