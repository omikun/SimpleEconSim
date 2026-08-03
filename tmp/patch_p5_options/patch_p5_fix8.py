"""Fix foreign_sell structure after Option-1 patch.

The Option-1 replacement removed the `for trader in traders:` goods loop but
left two blocks that still reference `trader`:
  1. the trader food-buying block (lines ~190-221), now sitting inside the
     `for good` loop with no trader variable — must be split out into its own
     `for trader in traders:` loop.
  2. the FX ask-posting block (lines ~223-232) already has its own loop.

Plan: move the food-buying block OUT of the `for good` loop into a separate
`for trader in traders:` loop after the per-good logging.
"""
p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

# ---- 1. Remove the food-buying block from inside the for-good loop ----
old = """            destination_region.import_vol[good].append(0)
            destination_region.import_val[good].append(0.0)

        # Traders buy food for themselves at the destination out of sales
        # proceeds (they are away from home and must eat from local markets).
        if trader.inv_get(Goods.food, 0) < 8:
            food_price = destination_region.recipes[Goods.food]['price']
            need = 8 - trader.inv_get(Goods.food, 0)
            if use_fx:
                wallet_bal = fx.fx_balance(trader, dest_currency)
                afford = int(wallet_bal / food_price) if food_price > 0 else 0
            else:
                afford = int(trader.cash / food_price) if food_price > 0 else 0
            to_buy = min(need, afford)
            if to_buy > 0:
                sellers = [a for a in destination_region.agents
                           if a.output == Goods.food
                           and a.inv_get(Goods.food, 0) > 2
                           and not getattr(a, 'is_trader', False)]
                bought = 0
                for seller in sellers:
                    if bought >= to_buy:
                        break
                    available = seller.inv_get(Goods.food, 0) - 2
                    if available <= 0:
                        continue
                    take = min(available, to_buy - bought)
                    seller.inv_add(Goods.food, -take)
                    seller.cash += take * food_price
                    if use_fx:
                        fx.fx_sub(trader, dest_currency, take * food_price)
                    else:
                        trader.cash -= take * food_price
                    trader.inv_add(Goods.food, take)
                    bought += take

    if use_fx:"""
new = """            destination_region.import_vol[good].append(0)
            destination_region.import_val[good].append(0.0)

    # Traders buy food for themselves at the destination out of sales
    # proceeds (they are away from home and must eat from local markets).
    for trader in traders:
        if trader.inv_get(Goods.food, 0) < 8:
            food_price = destination_region.recipes[Goods.food]['price']
            need = 8 - trader.inv_get(Goods.food, 0)
            if use_fx:
                wallet_bal = fx.fx_balance(trader, dest_currency)
                afford = int(wallet_bal / food_price) if food_price > 0 else 0
            else:
                afford = int(trader.cash / food_price) if food_price > 0 else 0
            to_buy = min(need, afford)
            if to_buy > 0:
                sellers = [a for a in destination_region.agents
                           if a.output == Goods.food
                           and a.inv_get(Goods.food, 0) > 2
                           and not getattr(a, 'is_trader', False)]
                bought = 0
                for seller in sellers:
                    if bought >= to_buy:
                        break
                    available = seller.inv_get(Goods.food, 0) - 2
                    if available <= 0:
                        continue
                    take = min(available, to_buy - bought)
                    seller.inv_add(Goods.food, -take)
                    seller.cash += take * food_price
                    if use_fx:
                        fx.fx_sub(trader, dest_currency, take * food_price)
                    else:
                        trader.cash -= take * food_price
                    trader.inv_add(Goods.food, take)
                    bought += take

    if use_fx:"""
assert old in src, "food-block-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("foreign_sell food loop restructured")