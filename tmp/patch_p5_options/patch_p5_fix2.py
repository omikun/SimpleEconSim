"""Fix: after Option C removed `price = self._set_price(...)`, the downstream
charity/gov food purchase blocks still read `price`.  Bind `price` to the
sector reference `ref` (the anchor) so those buyers transact at the reference,
consistent with Option C."""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """            self._update_price_ref(good, demand_ratio)
            ref = self._price_ref[good]
            if min(price_ta, tb) == 0:"""
new = """            self._update_price_ref(good, demand_ratio)
            ref = self._price_ref[good]
            price = ref  # sector reference price for charity/gov buyers
            if min(price_ta, tb) == 0:"""
assert old in src, "price-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("price binding fix applied")