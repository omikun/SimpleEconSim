"""Fix trader bid gate for Option-1 auction model.

The old gate checked  dest_price * fee_mult * fx_rate  against local price.
Under Phase-5 Option-1 the import ask ALREADY passes the tariff and FX
through (cost_home*(1+margin)/((1-tariff)*buy_rate)), so multiplying the
gate by fee and fx double-counts them and can refuse bids that are actually
profitable (e.g. fee 0.95 * fx 0.99 = 0.94 < 0.99 -> refuse despite a real
cost advantage).

Correct gate under Option-1: pure price-spread test.  The trader buys at
local price and sells at their own cost+margin ask, which is competitive if
the destination price exceeds local price by at least the minimum margin.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """            destination = agent.destination_region
            if destination is not None:
                # Use cached fee multiplier + FX to check true profitability
                # (foreign_sell prices exports at dest price * fee mult * fx).
                fx_rate = self.exchange_rate
                desk = getattr(self, 'forex', None)
                if desk is not None:
                    fx_rate = desk.buy_rate()
                effective_sell = destination.recipes[good]['price'] * self._trade_fee_mult * fx_rate
                # Phase 5: the round-1 auction pays the trader their import ask
                # (cost+margin, netted through the tariff and the buy rate), so
                # the gate only needs break-even here — not a 1% clip that the
                # ~0.5 FX floor made impossible.  Margin is earned at auction.
                if effective_sell <= good_price * 0.99:  # break-even ~1% buffer
                    return 0"""
new = """            destination = agent.destination_region
            if destination is not None:
                # Phase-5 (Option 1) gate: the import ask already passes the
                # tariff and FX through (cost*(1+margin)/((1-tariff)*buy_rate)),
                # so profitability is guaranteed by the ask construction.  The
                # only real requirement is that the destination price exceeds
                # the local price by at least the minimum import margin —
                # a pure arbitrage-spread test (no fee/fx double-count).
                dest_price = destination.recipes.get(good, {}).get('price', 0)
                min_margin = self.IMPORT_MARGIN_MIN  # 5%
                if dest_price <= good_price * (1.0 + min_margin):
                    return 0"""
assert old in src, "bid-gate-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("bid gate corrected: pure price-spread test (fee/fx not double-counted)")