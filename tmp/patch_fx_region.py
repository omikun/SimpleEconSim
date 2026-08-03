"""Small patch: region.py trader profitability uses FX buy_rate when desk exists."""

p = "/Users/sli/Code/region.py"
src = open(p).read()

old = "                effective_sell = destination.recipes[good]['price'] * self._trade_fee_mult * self.exchange_rate"
new = """                fx_rate = self.exchange_rate
                desk = getattr(self, 'forex', None)
                if desk is not None:
                    fx_rate = desk.buy_rate()
                effective_sell = destination.recipes[good]['price'] * self._trade_fee_mult * fx_rate"""

assert old in src, "MISSING bid anchor"
src = src.replace(old, new)

old = "                foreign_net = dest.recipes.get(good, {}).get('price', 0) * self._trade_fee_mult * self.exchange_rate"
new = """                fx_rate = self.exchange_rate
                desk = getattr(self, 'forex', None)
                if desk is not None:
                    fx_rate = desk.buy_rate()
                foreign_net = dest.recipes.get(good, {}).get('price', 0) * self._trade_fee_mult * fx_rate"""

assert old in src, "MISSING ask anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("region patch applied")