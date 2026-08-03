"""Fix trader export gate: Phase 5 broke `_calculate_bid` profitability.

Old gate (line ~919):  effective_sell = dest_price * fee_mult * buy_rate
                         if effective_sell <= good_price * 1.01: return 0

Under Phase 5, fx_rate (dest->home buy_rate) can be ~0.5 at the band floor,
so dest_price * 0.95 * 0.5 << local good_price -> the 1.01 margin test kills
EVERY trader bid -> inventory_export stays 0 -> no imports ever auctioned.

The Phase-5 auction already guarantees the trader their cost+margin via the
import ask.  The bid gate should therefore check break-even against NEXT-TURN
repatriation at the CURRENT rate, PLUS the expected margin, not a hard 1.01x
clip.  Use:  profitable if effective_sell > good_price * 0.99 (allow ~0
margin; margin comes from the auction ask), and keep a floor so traders don't
destroy wealth on hopeless liquidity.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """                effective_sell = destination.recipes[good]['price'] * self._trade_fee_mult * fx_rate
                if effective_sell <= good_price * 1.01:  # need at least 1% margin
                    return 0"""
new = """                effective_sell = destination.recipes[good]['price'] * self._trade_fee_mult * fx_rate
                # Phase 5: the round-1 auction pays the trader their import ask
                # (cost+margin, netted through the tariff and the buy rate), so
                # the gate only needs break-even here — not a 1% clip that the
                # ~0.5 FX floor made impossible.  Margin is earned at auction.
                if effective_sell <= good_price * 0.99:  # break-even ~1% buffer
                    return 0"""
assert old in src, "bid-gate-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("trader bid gate relaxed to break-even (0.99)")