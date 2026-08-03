"""Small patch: add per-currency conservation check in main()."""

p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

old = '            print(f"  T={t}: COMBINED CASH LEAK ${cash_after-cash_before:.2f}")\n\n        for region, other in [(region_a, region_b), (region_b, region_a)]:'
new = '            print(f"  T={t}: COMBINED CASH LEAK ${cash_after-cash_before:.2f}")\n\n        for c in currencies:\n            delta = fx.audit_currency_total([region_a, region_b], c) - curr_before[c]\n            if abs(delta) > 5.0:\n                print(f"  T={t}: CURRENCY {c!r} SUPPLY SHIFT ${delta:.2f}")\n\n        for region, other in [(region_a, region_b), (region_b, region_a)]:'

assert old in src, "MISSING audit anchor"
src = src.replace(old, new)
open(p, "w").write(src)
print("audit patch applied")