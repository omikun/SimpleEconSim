"""Patch econsim_two_region.py for Phase 1 FX (small, ASCII-only)."""

p = '/Users/sli/Code/econsim_two_region.py'
src = open(p).read()

reps = [
    # use_fx setup + dest_currency
    ("    traders = [a for a in source_region.trader_agents\n               if a.home_region == sname]\n    total_sold_value = 0.0",
     "    traders = [a for a in source_region.trader_agents\n               if a.home_region == sname]\n    use_fx = (getattr(source_region, 'forex', None) is not None\n              and getattr(source_region, 'home_currency', None) is not None)\n    dest_currency = destination_region.home_currency\n    total_sold_value = 0.0"),
    # remove legacy fx pricing wedge in foreign_sell
    ("            ask_price = price * 0.95\n            fx_rate = source_region.exchange_rate\n            if fx_rate != 1.0 and source_region.gov.floating_exchange_rate_enabled:\n                # Stronger currency (rate > 1) makes this region's exports\n                # pricier abroad, damping a trade surplus (self-correcting).\n                ask_price = ask_price * fx_rate\n            buyers",
     "            ask_price = price * 0.95\n            buyers"),
    # pay trader in destination-currency wallet
    ("                trader.cash += trader_share\n                trader._trader_revenue += trader_share\n                if bank_share > 0:",
     "                if use_fx:\n                    trader.wallets[dest_currency] += trader_share\n                else:\n                    trader.cash += trader_share\n                trader._trader_revenue += trader_share\n                if bank_share > 0:"),
    # food affordability from foreign wallet
    ("            need = 8 - trader.inv_get(Goods.food, 0)\n            afford = int(trader.cash / food_price) if food_price > 0 else 0\n            to_buy = min(need, afford)",
     "            need = 8 - trader.inv_get(Goods.food, 0)\n            if use_fx:\n                wallet_bal = trader.wallets.get(dest_currency, 0.0)\n                afford = int(wallet_bal / food_price) if food_price > 0 else 0\n            else:\n                afford = int(trader.cash / food_price) if food_price > 0 else 0\n            to_buy = min(need, afford)"),
    # food purchase paid from wallet + repatriation after loop
    ("                    seller.cash += take * food_price\n                    trader.cash -= take * food_price\n                    trader.inv_add(Goods.food, take)\n                    bought += take\n\n    if total_sold_value > 0 and t % 50 == 0:",
     "                    seller.cash += take * food_price\n                    if use_fx:\n                        trader.wallets[dest_currency] -= take * food_price\n                    else:\n                        trader.cash -= take * food_price\n                    trader.inv_add(Goods.food, take)\n                    bought += take\n\n    if use_fx:\n        fx.repatriate_traders(traders, source_region, t)\n\n    if total_sold_value > 0 and t % 50 == 0:"),
]

for old, new in reps:
    assert old in src, 'MISSING: ' + old[:60]
    src = src.replace(old, new)

open(p, 'w').write(src)
print('main patch applied')