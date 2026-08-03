#!/usr/bin/env python3
# Phase 6F: ROI metric — trader total wealth (cash + deposits + foreign wallet)
TARGET = 'econsim_two_region.py'
src = open(TARGET).read()

# ---- 1. Add helper after foreign_sell ----
anchor = "    return total_sold_quantity, total_sold_value\n"

helper = """    return total_sold_quantity, total_sold_value


def trader_wealth(region):
    \"\"\"Total trader wealth in home currency.

    Cash + bank deposits + foreign wallet converted at the home desk's
    current buy rate (the rate at which the trader could repatriate today).
    \"\"\"
    total = 0.0
    desk = getattr(region, 'forex', None)
    for a in region.trader_agents:
        w = a.cash + region.bank.deposits.get(a, 0)
        if desk is not None:
            w += fx.fx_balance(a, desk.other) * desk.buy_rate()
        total += w
    return total
"""

assert src.count(anchor) == 1, "foreign_sell tail not found"
src = src.replace(anchor, helper, 1)

# ---- 2. Capture initial trader wealth after connect_regions ----
old_conn = "    fx.connect_regions(region_a, region_b, t=0)\n"
new_conn = "    fx.connect_regions(region_a, region_b, t=0)\n" \
           "    region_a._init_trader_wealth = trader_wealth(region_a)\n" \
           "    region_b._init_trader_wealth = trader_wealth(region_b)\n"
assert src.count(old_conn) == 1, "connect_regions line not found"
src = src.replace(old_conn, new_conn)

# ---- 3. Replace cash-only ROI computation ----
old_roi = """        trader_roi = 0.0
        init_trader_cash = region.trader_cash_log[0] if region.trader_cash_log else 1
        final_trader_cash = region.trader_cash_log[-1] if region.trader_cash_log else 0
        if init_trader_cash > 0:
            trader_roi = (final_trader_cash - init_trader_cash) / init_trader_cash * 100"""

new_roi = """        init_trader_wealth = getattr(region, '_init_trader_wealth', 0.0)
        final_traders = [a for a in region.agents if a.is_trader]
        final_cash = sum(a.cash for a in final_traders)
        final_deposits = sum(region.bank.deposits.get(a, 0) for a in final_traders)
        desk = getattr(region, 'forex', None)
        final_wallet = 0.0
        if desk is not None:
            final_wallet = sum(fx.fx_balance(a, desk.other) for a in final_traders) * desk.buy_rate()
        final_trader_wealth = final_cash + final_deposits + final_wallet
        trader_roi = 0.0
        if init_trader_wealth > 0:
            trader_roi = (final_trader_wealth - init_trader_wealth) / init_trader_wealth * 100"""

assert src.count(old_roi) == 1, "ROI computation block not found"
src = src.replace(old_roi, new_roi)

# ---- 4. Replace trader summary print ----
old_print = """        # Trader summary
        traders = [a for a in region.agents if a.is_trader]
        print(f"  Traders: {len(traders)} traders, "
              f"${sum(a.cash for a in traders):.2f} total cash, "
              f"ROI: {trader_roi:.1f}% (${init_trader_cash:.0f}->${final_trader_cash:.0f})")"""

new_print = """        # Trader summary (wealth = cash + deposits + foreign wallet @ buy rate)
        print(f"  Traders: {len(final_traders)} traders, "
              f"cash ${final_cash:.0f}, deposits ${final_deposits:.0f}, "
              f"wallet ${final_wallet:.0f}, wealth ${final_trader_wealth:.0f} "
              f"(start ${init_trader_wealth:.0f}), "
              f"ROI: {trader_roi:.1f}%")"""

assert src.count(old_print) == 1, "trader summary print block not found"
src = src.replace(old_print, new_print)

open(TARGET, 'w').write(src)
print("patch_p6f.py applied OK")