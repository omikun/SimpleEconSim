"""Phase 3: per-turn interbank market cycle on each desk — APPENDS to forex.py."""
p = "/Users/sli/Code/forex.py"
src = open(p).read()

block = '''

# =============================================================================
# Phase 3: interbank market cycle (bids + clear + desk last resort)
# =============================================================================

WORKING_CAPITAL_TARGET = 100.0  # desired foreign float per trader


def set_working_capital_target(amount):
    """Globally adjust the per-trader foreign working-capital target."""
    global WORKING_CAPITAL_TARGET
    WORKING_CAPITAL_TARGET = float(amount)


def cycle_market(region_a, region_b, t=0):
    """Run one interbank market cycle across both desks.

    For each desk:
      * post a BID for each home trader's working-capital shortfall of the
        other currency (bounded by cash they can actually pay),
      * clear_book() matches crossing bids/asks wallet-to-wallet (conserved),
      * residual ASKs are repatriated by the desk (fx_pool-capped) — desk as
        market-maker of last resort,
      * residual BIDs buy from the desk's foreign reserves (reserve-capped).

    Conservation: book matches move home cash trader-to-trader and foreign
    wallet-to-wallet; desk legs use the existing reserve-capped conversions.
    Returns {'Region_A': value, 'Region_B': value} matched per desk.
    """
    result = {}

    for region, partner in ((region_a, region_b), (region_b, region_a)):
        desk = getattr(region, 'forex', None)
        if desk is None:
            continue
        other = partner.home_currency
        bank = region.bank

        # ---- Post working-capital BIDs (buy foreign to fund travel) ----
        for trader in region.trader_agents:
            if trader.home_region != region.name:
                continue
            cur_bal = fx_balance(trader, other)
            shortfall = max(0.0, WORKING_CAPITAL_TARGET - cur_bal)
            if shortfall <= 0:
                continue
            rate = desk.sell_rate()
            affordable = trader.cash / rate if rate > 0 else 0.0
            qty = min(shortfall, affordable)
            if qty > 0:
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
                                         desk.sell_rate())
            if bought > 0:
                order['qty'] -= bought
        # Drop fully-filled bids; leave unfilled asks for next turn
        desk.book = [o for o in desk.book
                     if o['qty'] > 0 and o['kind'] == 'ask']

    return result


def _get_working_capital_target():
    return WORKING_CAPITAL_TARGET
'''

if "def cycle_market" not in src:
    src = src + block
    open(p, "w").write(src)
    print("cycle_market appended to forex.py")
else:
    print("cycle_market already present")