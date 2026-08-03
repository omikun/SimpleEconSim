p = "/Users/sli/Code/econsim_live.py"
src = open(p).read()

# ---- 1. Heirs branch: distribute foreign-currency wallets to heirs ----
old = """        for i, descendent in enumerate(living_descendants):
            extra_cash = cash_remainder if i == 0 else 0
            descendent.cash += cash_share + extra_cash
        # Distribute inventory — iterate over Goods enum (list-based inventory)"""
new = """        for i, descendent in enumerate(living_descendants):
            extra_cash = cash_remainder if i == 0 else 0
            descendent.cash += cash_share + extra_cash
        # Distribute foreign-currency wallets evenly to heirs
        for currency, bal in list(agent.wallets.items()):
            if bal <= 0:
                continue
            wallet_share = bal / num_heirs
            for descendent in living_descendants:
                descendent.wallets[currency] += wallet_share
                agent.wallets[currency] = 0.0
        # Distribute inventory — iterate over Goods enum (list-based inventory)"""
assert old in src, "heirs-anchor"
src = src.replace(old, new)

# ---- 2. No-heirs branch: transfer foreign-currency wallets to government ----
old = """        if government is not None:
            government.agent.cash += inheritance_cash
            if inheritance_deposits > 0:"""
new = """        if government is not None:
            government.agent.cash += inheritance_cash
            # Transfer foreign-currency wallets to government
            for currency, bal in list(agent.wallets.items()):
                if bal <= 0:
                    continue
                government.agent.wallets[currency] += bal
                agent.wallets[currency] = 0.0
            if inheritance_deposits > 0:"""
assert old in src, "no-heirs-anchor"
src = src.replace(old, new)

# ---- 3. _zero_out_dead_agent: clear remaining wallets as a safety net ----
old = """def _zero_out_dead_agent(ctx: LiveContext, agent):
    \"\"\"Clear dead agent's assets so they don't leak from the cash sum.\"\"\"
    agent.cash = 0
    if agent in ctx.bank.deposits:
        del ctx.bank.deposits[agent]"""
new = """def _zero_out_dead_agent(ctx: LiveContext, agent):
    \"\"\"Clear dead agent's assets so they don't leak from the cash sum.\"\"\"
    agent.cash = 0
    if agent in ctx.bank.deposits:
        del ctx.bank.deposits[agent]
    agent.wallets.clear()"""
assert old in src, "zero-out-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("inheritance wallet patch applied")