"""Phase 5 (Option 1): auction-only import channel.

foreign_sell no longer dumps goods at 0.95x market after the auction.
ALL imports are sold through the destination's round-1 priced book:
  * arrived goods join the NEXT turn's auction (1-turn settlement lag),
  * unsold imports stay in inventory_foreign and re-offer until bought,
  * tariff is collected to the destination government at clearing.

foreign_sell becomes bookkeeping-only:
  * traders buy food at the destination out of their foreign wallet,
  * leftover foreign wallet balances post to the home desk's FX book,
  * trade-balance logs record the auction-sold import volumes.

Conservation at auction: buyer pays P; trader wallet gets P*(1-tau); dest
gov gets P*tau; locals get cash.  Sum zero.
"""
p = "/Users/sli/Code/econsim_two_region.py"
src = open(p).read()

old = """def foreign_sell(t, destination_region, source_region):
    sname = source_region.name
    # Use cached trader list (maintained on Region) — avoid O(N) filter per call
    traders = [a for a in source_region.trader_agents
               if a.home_region == sname]
    use_fx = (getattr(source_region, 'forex', None) is not None
              and getattr(source_region, 'home_currency', None) is not None)
    dest_currency = destination_region.home_currency
    total_sold_value = 0.0
    total_sold_quantity = 0
    trade_volumes = defaultdict(int)
    trade_values = defaultdict(float)

    total_trader_profit = 0.0
    total_bank_recycle = 0.0
    total_tariff = 0.0

    for trader in traders:
        for good in [Goods.food, Goods.wood, Goods.furniture]:
            qty = trader.inventory_foreign[good.value]
            if qty <= 0:
                continue
            price = destination_region.recipes[good]['price']
            ask_price = price * 0.95
            buyers = [a for a in destination_region.agents
                      if not getattr(a, 'is_trader', False) and a.cash > ask_price]
            random.shuffle(buyers)
            remaining = qty
            for buyer in buyers:
                if remaining <= 0:
                    break
                max_buy = int(buyer.cash / ask_price)
                if max_buy <= 0:
                    continue
                bought = min(remaining, max_buy, 3)
                cash = bought * ask_price
                buyer.cash -= cash
                trader_share = cash
                bank_share = 0.0
                tariff_share = 0.0

                if destination_region.gov.trader_recycling_enabled:
                    bank_share = cash * destination_region.gov.trader_recycling_rate
                    trader_share -= bank_share
                if destination_region.gov.import_tariff_enabled:
                    tariff_share = cash * destination_region.gov.import_tariff_rate
                    trader_share -= tariff_share

                if use_fx:
                    fx.fx_add(trader, dest_currency, trader_share)
                else:
                    trader.cash += trader_share
                trader._trader_revenue += trader_share
                if bank_share > 0:
                    destination_region.bank.total_deposits += bank_share
                if tariff_share > 0:
                    destination_region.gov.agent.cash += tariff_share
                total_trader_profit += trader_share
                total_bank_recycle += bank_share
                total_tariff += tariff_share
                old_quantity = buyer.inv_get(good, 0)
                old_cost = buyer.cost_get(good, 0)
                buyer.cost_set(good, ((old_quantity * old_cost + bought * ask_price) / (old_quantity + bought)) if (old_quantity + bought) > 0 else ask_price)
                buyer.inv_add(good, bought)
                remaining -= bought
                total_sold_quantity += bought
                total_sold_value += cash
                trade_volumes[good] += bought
                trade_values[good] += cash
            trader.inventory_foreign[good.value] = remaining"""
new = """def foreign_sell(t, destination_region, source_region):
    sname = source_region.name
    # Use cached trader list (maintained on Region) — avoid O(N) filter per call
    traders = [a for a in source_region.trader_agents
               if a.home_region == sname]
    use_fx = (getattr(source_region, 'forex', None) is not None
              and getattr(source_region, 'home_currency', None) is not None)
    dest_currency = destination_region.home_currency
    total_sold_value = 0.0
    total_sold_quantity = 0
    trade_volumes = defaultdict(int)
    trade_values = defaultdict(float)

    # Phase 5 (Option 1): ALL imports are sold through the destination's
    # round-1 priced auction (which cleared during step, decrementing
    # inventory_foreign).  No direct after-market dumping at 0.95x anymore;
    # unsold imports stay in inventory_foreign and re-offer next turn until
    # the book buys them at their own cost+margin ask.
    for good in [Goods.food, Goods.wood, Goods.furniture]:
        aq, av = destination_region._auction_import_sales.get(good, (0, 0.0))
        if aq > 0:
            source_region.export_vol[good].append(aq)
            source_region.export_val[good].append(av)
            destination_region.import_vol[good].append(aq)
            destination_region.import_val[good].append(av)
            total_sold_quantity += aq
            total_sold_value += av
        else:
            source_region.export_vol[good].append(0)
            source_region.export_val[good].append(0.0)
            destination_region.import_vol[good].append(0)
            destination_region.import_val[good].append(0.0)"""
assert old in src, "foreign-sell-anchor"
src = src.replace(old, new)

# ---- Remove the old per-good logging block (now handled above) ----
old = """    for good in [Goods.food, Goods.wood, Goods.furniture]:
        volume_sold = trade_volumes[good]
        value_sold = trade_values[good]
        # Phase 4: add what sold through the round-1 auction on the
        # destination (credits source traders in destination-currency wallets).
        aq, av = destination_region._auction_import_sales.get(good, (0, 0.0))
        volume_sold += aq
        value_sold += av
        if volume_sold > 0:
            source_region.export_vol[good].append(volume_sold)
            source_region.export_val[good].append(value_sold)
            destination_region.import_vol[good].append(volume_sold)
            destination_region.import_val[good].append(value_sold)
        else:
            source_region.export_vol[good].append(0)
            source_region.export_val[good].append(0.0)
            destination_region.import_vol[good].append(0)
            destination_region.import_val[good].append(0.0)

    return total_sold_quantity, total_sold_value"""
new = """    return total_sold_quantity, total_sold_value"""
assert old in src, "log-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("foreign_sell -> auction-only import channel (Option 1)")