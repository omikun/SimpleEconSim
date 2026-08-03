"""Fix patch_p4: region.py needs forex import; _sell_imports must use _fx.fx_add."""
p = "/Users/sli/Code/region.py"
src = open(p).read()

# Add forex import (leaf module — no circular import)
old = """from random_cache import rand
try:"""
new = """from random_cache import rand
import forex as _fx
try:"""
assert old in src, "import-anchor"
src = src.replace(old, new)

old = """            trader.inventory_foreign[good.value] -= take
            home = take * price
            fx_add(trader, self.home_currency, home)"""
new = """            trader.inventory_foreign[good.value] -= take
            home = take * price
            _fx.fx_add(trader, self.home_currency, home)"""
assert old in src, "fxadd-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("region.py forex import + _fx.fx_add applied")