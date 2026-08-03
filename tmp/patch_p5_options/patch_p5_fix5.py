"""Fix: `take` can be a float (import lots' qty may be fractional), and
`[ask] * float` raises.  Use int() for the price-list extension."""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """                prices.extend([ask] * take)"""
new = """                prices.extend([ask] * int(take))"""
assert old in src, "prices-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("prices int-cast fix applied")