"""Fix two bugs in the Phase 5 patch:
1. __init__ used local `goods_goods` — use self.goods (skip Goods.gov).
2. _clear_discriminatory references `t` but lacks the parameter; add `t` and
   pass it from the caller.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

# ---- Fix 1: price-ref init uses self.goods ----
old = """        self._price_ref = {g: max(0.1, self.recipes[g].get('price', 1.0))
                           for g in goods_goods if g != Goods.gov}"""
new = """        self._price_ref = {g: max(0.1, self.recipes[g].get('price', 1.0))
                           for g in self.goods
                           if g != Goods.gov and g != Goods.transport}"""
assert old in src, "ref-init-anchor"
src = src.replace(old, new)

# ---- Fix 2: pass t into _clear_discriminatory ----
old = """            total_bought, total_cash_purchases, realized = self._clear_discriminatory(
                good, ref, price_ta, tb, imp_pool, agents)"""
new = """            total_bought, total_cash_purchases, realized = self._clear_discriminatory(
                good, ref, price_ta, tb, imp_pool, agents, t)"""
assert old in src, "call-anchor"
src = src.replace(old, new)

old = """    def _clear_discriminatory(self, good, ref, total_asks, total_bids,
                               imp_pool, agents):"""
new = """    def _clear_discriminatory(self, good, ref, total_asks, total_bids,
                               imp_pool, agents, t):"""
assert old in src, "sig-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("Phase 5 fix1 applied (self.goods + t param)")