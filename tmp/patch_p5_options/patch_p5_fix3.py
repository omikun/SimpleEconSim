"""Fix: charity/gov food blocks still reference `askers` (sorted by ask qty).
Restore the sort in the new Option C Phase-A loop."""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """            total_bought, tcash, realized = self._clear_discriminatory(
                good, ref, price_ta, tb, imp_pool, agents, t)
            self.sold_log[good].append(total_bought)
            self._trade_prices[good].append(realized)"""
new = """            total_bought, tcash, realized = self._clear_discriminatory(
                good, ref, price_ta, tb, imp_pool, agents, t)
            self.sold_log[good].append(total_bought)
            self._trade_prices[good].append(realized)
            # Charity/gov food buyers still need askers (ask quantity sort)
            askers = sorted(agents, key=lambda a: a.ask, reverse=True)"""
assert old in src, "askers-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("askers restore applied")