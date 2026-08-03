"""Phase 3: fix transport-market cash destruction in Region._trade.

The Phase B transport clear did:
    total_bought, _ = self._buy(t, Goods.transport, price, tr_asks)
    _, total_sold = self._sell(askers, Goods.transport, price, t, total_bought, 0)

_sell only credits sellers while (total_cash_purchases > total_cash_sales).
Passing 0 makes that condition 0 > 0 == False, so sellers NEVER receive cash:
every transport purchase destroys exactly (bought * price) of the region's
currency (Region_B's persistent -20.56/turn).

Fix: capture the cash actually collected by _buy and pass it to _sell so the
buyer-out / seller-in pair matches.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """            price = self._set_price(dr, Goods.transport)
            if dr > 0 and tr_bids > 0 and tr_asks > 0:
                total_bought, _ = self._buy(t, Goods.transport, price, tr_asks)
                askers = sorted(agents, key=lambda a: a.ask_transport, reverse=True)
                _, total_sold = self._sell(askers, Goods.transport, price, t, total_bought, 0)
                self.sold_log[Goods.transport].append(total_sold)"""
new = """            price = self._set_price(dr, Goods.transport)
            if dr > 0 and tr_bids > 0 and tr_asks > 0:
                total_bought, tcash = self._buy(t, Goods.transport, price, tr_asks)
                askers = sorted(agents, key=lambda a: a.ask_transport, reverse=True)
                _, total_sold = self._sell(askers, Goods.transport, price, t,
                                           total_bought, tcash)
                self.sold_log[Goods.transport].append(total_sold)"""
assert old in src, "transport-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("transport cash-destruction fix applied to region.py")