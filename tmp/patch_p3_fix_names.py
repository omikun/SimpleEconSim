"""Phase 3: fix NameError — forex.py functions referenced via 'fx.' prefix but
the module isn't imported as 'fx' inside itself.  Use direct names."""
p = "/Users/sli/Code/forex.py"
src = open(p).read()

old = """            cur_bal = fx_balance(trader, other)"""
new = old  # already direct
# The only fx. prefixed calls inside forex.py cycle_market:
old2 = """            if qty > 0:
                desk.post_order('bid', trader, qty, rate)

        # ---- Clear the book (wallet-to-wallet, conserved) ----
        matched = desk.clear_book()
        result[region.name] = matched

        # ---- Desk last resort: repatriate residual asks ----
        fx.repatriate_traders(region.trader_agents, region, t)

        # ---- Desk last resort: fill residual bids from reserves ----
        for order in list(desk.book):
            if order['kind'] != 'bid':
                continue
            trader = order['trader']
            qty = order['qty']
            if qty <= 0:
                continue
            bought = fx.buy_fx_from_bank(bank, trader, other, qty,
                                         desk.sell_rate())"""
new2 = """            if qty > 0:
                desk.post_order('bid', trader, qty, rate)

        # ---- Clear the book (wallet-to-wallet, conserved) ----
        matched = desk.clear_book()
        result[region.name] = matched

        # ---- Desk last resort: repatriate residual asks ----
        repatriate_traders(region.trader_agents, region, t)

        # ---- Desk last resort: fill residual bids from reserves ----
        for order in list(desk.book):
            if order['kind'] != 'bid':
                continue
            trader = order['trader']
            qty = order['qty']
            if qty <= 0:
                continue
            bought = buy_fx_from_bank(bank, trader, other, qty,
                                      desk.sell_rate())"""
assert old2 in src, "fxref-anchor"
src = src.replace(old2, new2)

open(p, "w").write(src)
print("forex.py internal fx. references fixed")