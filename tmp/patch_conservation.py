p = "/Users/sli/Code/forex.py"
src = open(p).read()
old = "        if target_pool > bank.fx_pool:\n            bank.fx_pool += (target_pool - bank.fx_pool) * 0.1"
new = "        if False:\n            bank.fx_pool += 0.0"
assert old in src, "pool-anchor"
src = src.replace(old, new)

old = """            total += bank.total_deposits - bank.total_liabilities
            total += bank.fx_pool"""
new = """            total += bank.total_deposits - bank.total_liabilities
            total += bank.fx_pool
            if getattr(r, 'charity', None) is not None:
                total += r.charity.agent.cash"""
assert old in src, "charity-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("conservation patch applied")