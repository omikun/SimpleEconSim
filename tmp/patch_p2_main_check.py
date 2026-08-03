"""Phase 2: main() COMBINED check must include fx_pool + wallets.

The legacy get_total_cash excludes fx_pool/wallets, so funding the FX desk's
working capital (deposit -> fx_pool) looks like a per-turn leak.  Use the
per-currency audits summed over both currencies:  they include fx_pool,
wallets, reserves, equity, and agent cash, so any real leak shows up
consistently in both the COMBINED and per-currency checks.
"""
p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

old = """        curr_before = {c: fx.audit_currency_total([region_a, region_b], c)
                       for c in currencies}
        cash_before = (get_total_cash(region_a.agents, region_a.bank) + region_a.charity.cash
                       + get_total_cash(region_b.agents, region_b.bank) + region_b.charity.cash)"""
new = """        curr_before = {c: fx.audit_currency_total([region_a, region_b], c)
                       for c in currencies}
        cash_before = sum(curr_before.values())"""
assert old in src, "before-anchor"
src = src.replace(old, new)

old = """        cash_after = (get_total_cash(region_a.agents, region_a.bank) + region_a.charity.cash
                      + get_total_cash(region_b.agents, region_b.bank) + region_b.charity.cash)
        if abs(cash_after - cash_before) > 5.0:
            print(f"  T={t}: COMBINED CASH LEAK ${cash_after-cash_before:.2f}")"""
new = """        cash_after = sum(fx.audit_currency_total([region_a, region_b], c)
                         for c in currencies)
        if abs(cash_after - cash_before) > 5.0:
            print(f"  T={t}: COMBINED CASH LEAK ${cash_after-cash_before:.2f}")"""
assert old in src, "after-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("main combined-check patch applied")