"""Phase 2 econsim_live.py: null-aware wallet handling in inheritance/death.

Non-traders have a None wallet; only fork if a dict actually exists.
Also import forex helpers for lazy materialization.
"""
p = "/Users/sli/Code/econsim_live.py"
src = open(p).read()

# ---- 1. Import forex fx helpers (only if not already present) ----
if "import forex as fx" not in src:
    old = "from random_cache import rand"
    new = """from random_cache import rand
import forex as fx"""
    assert old in src, "import-anchor"
    src = src.replace(old, new, 1)

# ---- 2. Heirs branch: distribute foreign-currency wallets evenly to heirs ----
old = """        # Distribute foreign-currency wallets evenly to heirs
        for currency, bal in list(agent.wallets.items()):
            if bal <= 0:
                continue
            wallet_share = bal / num_heirs
            for descendent in living_descendants:
                descendent.wallets[currency] += wallet_share
                agent.wallets[currency] = 0.0"""
new = """        # Distribute foreign-currency wallets evenly to heirs (None-safe:
        # non-traders never have a wallet, so this loop is a no-op).
        dead_w = getattr(agent, 'wallets', None)
        if dead_w:
            for currency, bal in list(dead_w.items()):
                if bal <= 0:
                    continue
                wallet_share = bal / num_heirs
                for descendent in living_descendants:
                    fx.fx_add(descendent, currency, wallet_share)
                dead_w[currency] = 0.0"""
assert old in src, "heirs-anchor"
src = src.replace(old, new)

# ---- 3. No-heirs branch: transfer foreign-currency wallets to government ----
old = """            # Transfer foreign-currency wallets to government
            for currency, bal in list(agent.wallets.items()):
                if bal <= 0:
                    continue
                government.agent.wallets[currency] += bal
                agent.wallets[currency] = 0.0"""
new = """            # Transfer foreign-currency wallets to government (None-safe)
            dead_w = getattr(agent, 'wallets', None)
            if dead_w:
                for currency, bal in list(dead_w.items()):
                    if bal <= 0:
                        continue
                    fx.fx_add(government.agent, currency, bal)
                    dead_w[currency] = 0.0"""
assert old in src, "no-heirs-anchor"
src = src.replace(old, new)

# ---- 4. _zero_out_dead_agent: clear wallets (None-safe) ----
old = """    agent.wallets.clear()"""
new = """    dead_w = getattr(agent, 'wallets', None)
    if dead_w is not None:
        dead_w.clear()"""
assert old in src, "zero-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("econsim_live.py Phase 2 patch applied")