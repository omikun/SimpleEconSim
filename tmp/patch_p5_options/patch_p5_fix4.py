"""Fix: charity/gov food blocks reference `total_sold`; set it from the
book-clear result (total_bought), matching the old semantics."""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """            total_bought, tcash, realized = self._clear_discriminatory(
                good, ref, price_ta, tb, imp_pool, agents, t)
            self.sold_log[good].append(total_bought)
            self._trade_prices[good].append(realized)
            # Charity/gov food buyers still need askers (ask quantity sort)
            askers = sorted(agents, key=lambda a: a.ask, reverse=True)"""
new = """            total_bought, tcash, realized = self._clear_discriminatory(
                good, ref, price_ta, tb, imp_pool, agents, t)
            self.sold_log[good].append(total_bought)
            self._trade_prices[good].append(realized)
            total_sold = total_bought  # for charity/gov food blocks below
            # Charity/gov food buyers still need askers (ask quantity sort)
            askers = sorted(agents, key=lambda a: a.ask, reverse=True)"""
assert old in src, "total-sold-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("total_sold binding fix applied")