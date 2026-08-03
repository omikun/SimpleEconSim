"""Phase 2 econsim_two_region.py: null-aware wallet usage in foreign_sell."""
p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

# ---- 1. Pay trader in destination currency via null-aware fx_add ----
old = """                if use_fx:
                    trader.wallets[dest_currency] += trader_share
                else:
                    trader.cash += trader_share"""
new = """                if use_fx:
                    fx.fx_add(trader, dest_currency, trader_share)
                else:
                    trader.cash += trader_share"""
assert old in src, "pay-anchor"
src = src.replace(old, new)

# ---- 2. Trader food purchase: read wallet balance null-aware ----
old = """            if use_fx:
                wallet_bal = trader.wallets.get(dest_currency, 0.0)
                afford = int(wallet_bal / food_price) if food_price > 0 else 0
            else:
                afford = int(trader.cash / food_price) if food_price > 0 else 0"""
new = """            if use_fx:
                wallet_bal = fx.fx_balance(trader, dest_currency)
                afford = int(wallet_bal / food_price) if food_price > 0 else 0
            else:
                afford = int(trader.cash / food_price) if food_price > 0 else 0"""
assert old in src, "afford-anchor"
src = src.replace(old, new)

# ---- 3. Trader food purchase: debit wallet null-aware ----
old = """                    if use_fx:
                        trader.wallets[dest_currency] -= take * food_price
                    else:
                        trader.cash -= take * food_price"""
new = """                    if use_fx:
                        fx.fx_sub(trader, dest_currency, take * food_price)
                    else:
                        trader.cash -= take * food_price"""
assert old in src, "debit-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("econsim_two_region.py Phase 2 patch applied")