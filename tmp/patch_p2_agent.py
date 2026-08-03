p = "/Users/sli/Code/agent.py"
src = open(p).read()

old = """        # ---- Multi-currency wallets (Phase 1 FX) ----
        self.wallets = defaultdict(float)             # currency -> balance (foreign only)
        self.home_currency = None                     # set by Region"""
new = """        # ---- Multi-currency wallets (Phase 2: lazy, practical) ----
        # Only traders normally need foreign balances.  Non-traders keep this
        # as None (no empty-dict allocation); forex.fx_add() materializes a
        # dict lazily when a balance is actually needed (e.g. inheritance).
        self.wallets = None                           # dict | None
        self.home_currency = None                     # set by Region"""
assert old in src, "agent-wallets-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("agent.py lazy wallets applied")