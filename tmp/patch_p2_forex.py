"""Phase 2 forex.py: lazy trader-only wallets, conservation-safe working capital.

- Helpers fx_balance/fx_add/fx_sub/fx_clear treat a None wallet as empty and
  lazily materialize a dict only when a balance is needed.  Non-traders carry
  no defaultdict allocation.
- sell_fx_to_bank / buy_fx_from_bank / repatriate_trader are null-aware.
- _seed_trader_wallets no longer prints money: traders *buy* their foreign
  float from their home bank (home deposit -> fx_pool; reserves -> wallet).
- audit_currency_total is null-aware.
"""
p = "/Users/sli/Code/forex.py"
src = open(p).read()

# ---- 1. Null-aware wallet helpers (insert after DESK_BAND constants) ----
old = """class ForexDesk:"""
new = """def fx_wallets(a):
    \"\"\"Return a's wallet dict, lazily creating it if needed.\"\"\"
    w = getattr(a, 'wallets', None)
    if w is None:
        w = {}
        a.wallets = w
    return w


def fx_balance(a, currency):
    \"\"\"Balance of *currency* in a's wallet (None-safe, no allocation).\"\"\"
    w = getattr(a, 'wallets', None)
    return w.get(currency, 0.0) if w else 0.0


def fx_add(a, currency, amount):
    \"\"\"Add to a's wallet balance; returns new balance. Lazy materialize.\"\"\"
    if amount == 0:
        return fx_balance(a, currency)
    w = fx_wallets(a)
    w[currency] = w.get(currency, 0.0) + amount


def fx_sub(a, currency, amount):
    \"\"\"Subtract from a's wallet balance (floored at 0). Returns new balance.\"\"\"
    if amount == 0:
        return fx_balance(a, currency)
    w = getattr(a, 'wallets', None)
    if w is None:
        return 0.0
    w[currency] = max(0.0, w.get(currency, 0.0) - amount)
    return w[currency]


def fx_clear(a):
    \"\"\"Drop a's wallet entirely (dead agents, no-heir escheat).\"\"\"
    w = getattr(a, 'wallets', None)
    if w is not None:
        w.clear()


class ForexDesk:"""
assert old in src, "helpers-anchor"
src = src.replace(old, new)

# ---- 2. sell_fx_to_bank: null-aware wallet read/write ----
old = """    amount = min(amount, trader.wallets.get(currency, 0.0))
    if amount <= 0:
        return 0.0
    home = amount * rate
    max_pay = max(0.0, bank.fx_pool)
    if home > max_pay:
        home = max_pay
        amount = home / rate if rate > 0 else 0.0
    if amount <= 0:
        return 0.0
    trader.wallets[currency] -= amount
    bank.foreign_reserves[currency] += amount
    bank.fx_pool -= home
    trader.cash += home
    return home"""
new = """    amount = min(amount, fx_balance(trader, currency))
    if amount <= 0:
        return 0.0
    home = amount * rate
    max_pay = max(0.0, bank.fx_pool)
    if home > max_pay:
        home = max_pay
        amount = home / rate if rate > 0 else 0.0
    if amount <= 0:
        return 0.0
    fx_sub(trader, currency, amount)
    bank.foreign_reserves[currency] += amount
    bank.fx_pool -= home
    trader.cash += home
    return home"""
assert old in src, "sell-anchor"
src = src.replace(old, new)

# ---- 3. buy_fx_from_bank: null-aware wallet write ----
old = """    trader.wallets[currency] += amount
    bank.foreign_reserves[currency] -= amount
    bank.fx_pool += home
    trader.cash -= home
    return amount"""
new = """    fx_add(trader, currency, amount)
    bank.foreign_reserves[currency] -= amount
    bank.fx_pool += home
    trader.cash -= home
    return amount"""
assert old in src, "buy-anchor"
src = src.replace(old, new)

# ---- 4. repatriate_trader: null-aware balance read ----
old = """    bal = trader.wallets.get(desk.other, 0.0)
    if bal <= 0:
        return 0.0"""
new = """    bal = fx_balance(trader, desk.other)
    if bal <= 0:
        return 0.0"""
assert old in src, "repat-anchor"
src = src.replace(old, new)

# ---- 5. Replace money-printing seed with conservation-safe working capital ----
old = """def _seed_trader_wallets(region, partner):
    \"\"\"Give each trader a small float of the partner currency for travel.\"\"\"
    for a in region.agents:
        if getattr(a, 'is_trader', False):
            a.wallets.setdefault(partner.home_currency, 100.0)"""
new = """def _give_working_capital(trader, bank, currency, amount, rate):
    \"\"\"Trader buys *amount* of foreign *currency* from its home bank.

    Conservation-safe replacement for the old free seed: home money moves
    from the trader's deposit into the bank's fx_pool, and foreign money
    moves from the bank's reserves into the trader's wallet.  Both
    currencies are conserved; nothing is printed.
    Returns foreign amount actually obtained.
    \"\"\"
    if amount <= 0:
        return 0.0
    amount = min(amount, bank.foreign_reserves.get(currency, 0.0))
    if amount <= 0:
        return 0.0
    home = amount * rate
    max_home = bank.deposits.get(trader, 0) + trader.cash
    if home > max_home:
        home = max_home
        amount = home / rate if rate > 0 else 0.0
    if amount <= 0:
        return 0.0
    # Home leg: draw from trader deposit first, then cash
    from_deposit = min(home, bank.deposits.get(trader, 0))
    if from_deposit > 0:
        bank.total_deposits -= from_deposit
        bank.deposits[trader] -= from_deposit
    home_cash = home - from_deposit
    if home_cash > 0:
        trader.cash -= home_cash
    bank.fx_pool += home
    # Foreign leg: reserves -> wallet
    bank.foreign_reserves[currency] -= amount
    fx_add(trader, currency, amount)
    return amount


def seed_trader_wallet(region, partner, t=0):
    \"\"\"Give each trader an initial foreign float OUT OF WORKING CAPITAL.

    The old _seed_trader_wallets printed 100 of partner currency per trader
    out of thin air.  Now traders buy their float from the home bank:
      home deposit/cash -> fx_pool  (home currency conserved)
      reserves -> wallet            (foreign currency conserved)

    Returns total foreign amount seeded.
    \"\"\"
    total = 0.0
    for a in region.agents:
        if not getattr(a, 'is_trader', False):
            continue
        total += _give_working_capital(a, region.bank, partner.home_currency,
                                       100.0, region.forex.sell_rate())
    return total"""
assert old in src, "seed-anchor"
src = src.replace(old, new)

# ---- 6. connect_regions uses seed_trader_wallet ----
old = """    region_a.forex = desk_a
    region_b.forex = desk_b
    _seed_trader_wallets(region_a, region_b)
    _seed_trader_wallets(region_b, region_a)
    return desk_a, desk_b"""
new = """    region_a.forex = desk_a
    region_b.forex = desk_b
    seed_trader_wallet(region_a, region_b, t)
    seed_trader_wallet(region_b, region_a, t)
    return desk_a, desk_b"""
assert old in src, "connect-anchor"
src = src.replace(old, new)

# ---- 7. audit_currency_total: null-aware wallet sum ----
old = """        # Foreign currency held by this region's agents (wallets)
        total += sum(a.wallets.get(currency, 0.0) for a in r.agents)"""
new = """        # Foreign currency held by this region's agents (wallets)
        total += sum(fx_balance(a, currency) for a in r.agents)"""
assert old in src, "audit-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("forex.py Phase 2 patch applied")