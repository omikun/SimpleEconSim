"""Phase 4: imports compete in the destination's round-1 auction.

Problem (user-identified): imports only sold by foreign_sell AFTER the main
auction at fixed 0.95x local price, so they could never displace local goods
in round 1, and FX never directly priced imports.

Fix:
  * econsim_two_region computes, before each step, the pending import pool
    for each destination from source traders' arrived inventory_foreign.
  * Region._trade Phase A folds those import asks into the auction supply
    (price discovery AND clearing).  Locals sell first (price-sorted as
    before); imports then absorb the residual demand, crediting source
    traders in DESTINATION-currency wallets (fx.fx_add) so the per-currency
    audit stays balanced.  inventory_foreign is decremented for what sold.
  * foreign_sell only sells the (now-smaller) leftover, and its export/import
    logs include the auction-sold amounts so trade balance remains accurate.

Conservation: buyers pay dest cash; local sellers receive cash; import owners
receive dest-currency wallets.  Sum = buyer outflow.  Both legs counted in
fx.audit_currency_total (locals' cash + everyone's wallets).  Goods are not
audited currency.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

# ---- 1. Initialize pending-import state on Region ----
old = """        # Cached list of living trader agents (avoid O(N) filter per call)
        self.trader_agents = []"""
new = """        # Cached list of living trader agents (avoid O(N) filter per call)
        self.trader_agents = []

        # Phase 4: pending import asks computed by the main loop each turn;
        # _trade folds them into the round-1 auction so imports can displace
        # local goods.  _auction_import_sales records what sold there so
        # foreign_sell can log it (and only sell the leftover).
        self.pending_imports = {}
        self._auction_import_sales = {}"""
assert old in src, "init-anchor"
src = src.replace(old, new)

# ---- 2. Replace Phase A market loop: imports join round-1 auction ----
old = """        for good in goods_goods:
            ta = total_asks[good]
            tb = total_bids[good]
            if ta == 0 and tb == 0:
                self._price_decay(good)
                continue
            # Imports add to effective supply ONLY for price discovery
            # (suppressing local prices).  The market still clears against
            # LOCAL asks only: imported goods are already sold to destination
            # buyers by foreign_sell, so letting _buy fill against imported
            # units would take real cash out with no local seller to receive
            # it (money destruction = import value).
            price_ta = ta
            if self.import_vol.get(good) and self.import_vol[good]:
                price_ta += self.import_vol[good][-1]
            demand_ratio = 5.0 if price_ta == 0 else tb / price_ta
            self.demand_ratio_log[good].append(demand_ratio)
            self.demand_log[good].append(tb)
            self.supply_log[good].append(price_ta)
            if max_demand_ratio < demand_ratio and tb > 0:
                max_demand_ratio = demand_ratio
                most_demand_good = good
            price = self._set_price(demand_ratio, good)
            if min(ta, tb) == 0:
                continue
            total_bought, total_cash_purchases = self._buy(t, good, price, ta)
            askers = sorted(agents, key=lambda a: a.ask, reverse=True)
            total_cash_sales, total_sold = self._sell(askers, good, price, t, total_bought, total_cash_purchases)
            self.sold_log[good].append(total_sold)"""
new = """        for good in goods_goods:
            ta = total_asks[good]
            tb = total_bids[good]
            # Phase 4: arrived imports join the round-1 auction supply so they
            # can genuinely displace local goods at the market price.
            imp_pool, imp_total = self._gather_import_pool(good)
            if ta == 0 and imp_total == 0 and tb == 0:
                self._price_decay(good)
                continue
            price_ta = ta + imp_total
            demand_ratio = 5.0 if price_ta == 0 else tb / price_ta
            self.demand_ratio_log[good].append(demand_ratio)
            self.demand_log[good].append(tb)
            self.supply_log[good].append(price_ta)
            if max_demand_ratio < demand_ratio and tb > 0:
                max_demand_ratio = demand_ratio
                most_demand_good = good
            price = self._set_price(demand_ratio, good)
            if min(price_ta, tb) == 0:
                self._auction_import_sales[good] = (0, 0.0)
                continue
            total_bought, total_cash_purchases = self._buy(t, good, price, price_ta)
            askers = sorted(agents, key=lambda a: a.ask, reverse=True)
            total_cash_sales, total_sold = self._sell(askers, good, price, t, total_bought, total_cash_purchases)
            # Imports absorb the residual demand (locals already sold first).
            imp_sold = 0
            imp_value = 0.0
            if imp_pool and total_bought > total_sold:
                imp_sold, imp_value = self._sell_imports(imp_pool, good, price,
                                                         total_bought - total_sold)
            self._auction_import_sales[good] = (imp_sold, imp_value)
            self.sold_log[good].append(total_sold + imp_sold)"""
assert old in src, "phase-a-anchor"
src = src.replace(old, new)

# ---- 3. Add helpers _gather_import_pool / _sell_imports before _buy ----
old = """    def _input_good(self, agent):
        return self.recipes[agent.output].get('input', Goods.none)

    def _buy(self, t, good, price, total_asks):"""
new = """    def _input_good(self, agent):
        return self.recipes[agent.output].get('input', Goods.none)

    def _gather_import_pool(self, good):
        \"\"\"Return (pool, total) of pending import asks for *good*.

        pool is a list of [trader, qty] entries whose source-region traders
        have physically delivered goods to this market.  These asks now
        participate in the round-1 auction (price discovery + clearing).
        \"\"\"
        pend = getattr(self, 'pending_imports', None) or {}
        entries = pend.get(good)
        if not entries:
            return [], 0
        pool = []
        total = 0
        for trader, qty in entries:
            if qty > 0 and getattr(trader, 'is_trader', False):
                pool.append([trader, qty])
                total += qty
        return pool, total

    def _sell_imports(self, pool, good, price, remaining_qty):
        \"\"\"Sell remaining auction demand to import owners.

        Each source trader is credited in DESTINATION currency via wallets
        (fx.fx_add), which the per-currency audit counts regardless of the
        trader's home region — so currency stays conserved.  Corresponding
        quantities are removed from inventory_foreign so foreign_sell only
        handles the truly-unsold leftover.
        Returns (units sold, value in destination currency).
        \"\"\"
        sold = 0
        value = 0.0
        for item in pool:
            if remaining_qty <= 0:
                break
            trader, qty = item
            take = min(qty, remaining_qty)
            if take <= 0:
                continue
            trader.inventory_foreign[good.value] -= take
            home = take * price
            fx_add(trader, self.home_currency, home)
            item[1] -= take
            remaining_qty -= take
            sold += take
            value += home
        return sold, value

    def _buy(self, t, good, price, total_asks):"""
assert old in src, "helpers-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("region.py Phase 4 unified-import auction applied")

# =============================================================================
# econsim_two_region.py: compute pending pools each turn + log auction sales
# =============================================================================
p2 = "/Users/sli/Code/econsim_two_region.py"
src2 = open(p2).read()

# ---- 4. _pending_imports helper (insert before foreign_sell) ----
old2 = """def foreign_sell(t, destination_region, source_region):"""
new2 = """def _pending_imports(dest, src):
    \"\"\"Goods that *src*'s traders have physically delivered to *dest*.

    Returns {Goods.good: [(trader, qty), ...]}.  The main loop installs this
    on each destination before step so the round-1 auction can include them.
    \"\"\"
    pend = {}
    for trader in src.trader_agents:
        if getattr(trader, 'destination_region', None) is not dest:
            continue
        for g in (Goods.food, Goods.wood, Goods.furniture):
            qty = trader.inventory_foreign[g.value]
            if qty > 0:
                pend.setdefault(g, []).append((trader, qty))
    return pend


def foreign_sell(t, destination_region, source_region):"""
assert old2 in src2, "helper2-anchor"
src2 = src2.replace(old2, new2)

# ---- 5. Main loop: set pending pools + reset auction-sales before steps ----
old2 = """        region_a.step(t)
        region_b.step(t)
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)
        foreign_sell(t, region_b, region_a)
        fx.cycle_market(region_a, region_b, t)"""
new2 = """        region_a.pending_imports = _pending_imports(region_a, region_b)
        region_b.pending_imports = _pending_imports(region_b, region_a)
        region_a._auction_import_sales = {}
        region_b._auction_import_sales = {}
        region_a.step(t)
        region_b.step(t)
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)
        foreign_sell(t, region_b, region_a)
        fx.cycle_market(region_a, region_b, t)"""
assert old2 in src2, "main-anchor"
src2 = src2.replace(old2, new2)

# ---- 6. foreign_sell: include auction-sold imports in trade-balance logs ----
old2 = """    for good in [Goods.food, Goods.wood, Goods.furniture]:
        volume_sold = trade_volumes[good]
        value_sold = trade_values[good]
        if volume_sold > 0:
            source_region.export_vol[good].append(volume_sold)
            source_region.export_val[good].append(value_sold)
            destination_region.import_vol[good].append(volume_sold)
            destination_region.import_val[good].append(value_sold)
        else:
            source_region.export_vol[good].append(0)
            source_region.export_val[good].append(0.0)
            destination_region.import_vol[good].append(0)
            destination_region.import_val[good].append(0.0)"""
new2 = """    for good in [Goods.food, Goods.wood, Goods.furniture]:
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
            destination_region.import_val[good].append(0.0)"""
assert old2 in src2, "log-anchor"
src2 = src2.replace(old2, new2)

open(p2, "w").write(src2)
print("econsim_two_region.py Phase 4 applied")