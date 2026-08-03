"""Phase 3: wire the interbank book into the sim.

1. foreign_sell: post leftover foreign earnings as ASKs on the source desk
   (book persists across turns), and defer residual repatriation to the
   per-turn market cycle.
2. fx.cycle_market(ra, rb, t): for each desk —
     * post BIDs for each home trader's working-capital shortfall of the
       other currency (target 100),
     * clear_book() to match crossing bids/asks wallet-to-wallet,
     * repatriate_traders residual asks (desk last resort, fx_pool-capped),
     * buy_fx_from_bank for unfilled bids (reserve-capped last resort).
   Conserved: book matches move home cash between traders and foreign
   wallet-to-wallet; desk legs are the existing reserve-capped paths.
"""
p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

old = """    if use_fx:
        fx.repatriate_traders(traders, source_region, t)"""
new = """    if use_fx:
        # Phase 3: post leftover foreign earnings as ASKs on the home desk's
        # order book (book persists across turns so they can cross with
        # next-turn working-capital bids).  Residuals are repatriated by
        # fx.cycle_market (desk last resort) at the end of the turn.
        desk = source_region.forex
        for trader in traders:
            bal = fx.fx_balance(trader, dest_currency)
            if bal > 0:
                desk.post_order('ask', trader, bal, desk.buy_rate())"""
assert old in src, "post-ask-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("foreign_sell now posts asks to the source desk's book")