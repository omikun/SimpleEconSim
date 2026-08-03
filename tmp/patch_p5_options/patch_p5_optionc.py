"""Phase 5 (Option C): anchored per-agent pay-as-bid limit order book.

Every seller (local producer + import lot) quotes their OWN ask price:
  LOCAL:  ask = ref_good * scarcity_urgency
  IMPORT: ask = cost_home*(1+margin) / ((1 - tariff) * buy_rate)

ref_good is a SLOW damped sector reference (VWAP-of-trades + demand/supply
ratio) updated with an asymmetric step: supply shocks move prices UP fast,
gluts ease gently; per-agent urgency scales bids/asks but is bounded, so an
individual agent cannot run the market off a cliff.

Clearing: cheapest-first pay-as-bid.  Each unit sells at ITS OWN ask price.
Locals get cash; import owners get destination-currency wallets.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

# ---- 1. Price reference state on Region ----
old = """        self.pending_imports = {}
        self._auction_import_sales = {}"""
new = """        self.pending_imports = {}
        self._auction_import_sales = {}
        # Phase 5 (Option C): slow sector price reference per good (VWAP +
        # demand/supply), and per-turn realized trade history for the VWAP.
        self._price_ref = {g: max(0.1, self.recipes[g].get('price', 1.0))
                           for g in self.goods
                           if g != Goods.gov and g != Goods.transport}
        self._trade_prices = defaultdict(list)  # good -> [price, ...] realized"""
assert old in src, "ref-state-anchor"
src = src.replace(old, new)

# ---- 2. Per-agent ask price + import ask (insert before _gather_import_pool) ----
old = """    def _gather_import_pool(self, good):"""
new = """    ASK_URGENCY_MIN = 0.7   # floor multiplier
    ASK_URGENCY_MAX = 1.8   # ceiling multiplier
    IMPORT_MARGIN_MIN = 0.05
    IMPORT_MARGIN_MAX = 0.10

    def _calculate_ask_price(self, agent, good, ref):
        \"\"\"Per-agent local ask price for output *good*.

        Base is the sector reference; per-agent urgency scales it:
          - low stock / near-empty => scarcity => HIGHER price (last units dear)
          - high stock / near cap   => clearance => LOWER price (fire-sale)
          - hungry                  => urgency => LOWER price (sell fast, buy food)
        Bound to [ASK_URGENCY_MIN, ASK_URGENCY_MAX].
        \"\"\"
        if agent.is_trader or agent.output != good:
            return ref
        stock = agent.inv_get(good, 0)
        maxinv = self.recipes.get(good, {}).get('maxinv', 10)
        ratio = stock / max(1, maxinv)
        scarcity = 1.4 - 0.4 * max(0.0, min(1.0, ratio))  # 1.4 empty .. 1.0 full
        hungry = getattr(agent, 'hungry_steps', 0)
        urgency = max(0.0, 1.0 - 0.12 * hungry)  # hungry => lower ask
        mult = scarcity * urgency
        mult = max(self.ASK_URGENCY_MIN, min(self.ASK_URGENCY_MAX, mult))
        return ref * mult

    def _import_ask_price(self, trader, good):
        \"\"\"Import ask: cost_home*(1+margin) / ((1 - tariff) * repatriate_rate).

        Repatriate_rate (dest->home) includes the FX spread, so the trader
        nets the margin after conversion.  Tariff passes through into price.
        \"\"\"
        cost_home = max(0.05, trader.cost_get(good, 0))
        margin = self.IMPORT_MARGIN_MIN + (
            self.IMPORT_MARGIN_MAX - self.IMPORT_MARGIN_MIN) * (
                abs(hash((trader.id, good))) % 1000) / 1000.0
        tariff = getattr(self.gov, 'import_tariff_rate', 0.0)
        dest_desk = getattr(self.destination_region, 'forex', None)
        buy_rate = dest_desk.buy_rate() if dest_desk is not None else 1.0
        denom = max(0.05, (1.0 - tariff) * buy_rate)
        return cost_home * (1.0 + margin) / denom

    def _gather_import_pool(self, good):"""
assert old in src, "ask-price-anchor"
src = src.replace(old, new)

# ---- 3. Price reference update (asymmetric step) — insert before _gather_import_pool ----
old = """    def _gather_import_pool(self, good):"""
new = """    def _update_price_ref(self, good, demand_ratio):
        \"\"\"Slow anchor: VWAP-of-trades + demand/supply, asymmetric step.

        Positive imbalance (fires / scarcity) moves ref UP fast — bounded per
        round so no runaway — while gluts ease gently.  Blends recent realized
        trade prices so the anchor tracks actuals.
        \"\"\"
        ref = self._price_ref[good]
        base_step = 1.0 + 0.08  # ~8% normal move
        if demand_ratio > 1.0:
            shock = 1.0 + 0.25 * min(5.0, (demand_ratio - 1.0) ** 2)
            ref = ref * base_step * shock
        else:
            ref = ref / base_step
        recent = self._trade_prices.get(good, [])[-12:]
        if recent:
            vwap = sum(recent) / len(recent)
            ref = 0.7 * ref + 0.3 * vwap
        r = self.recipes.get(good, {})
        cost_floor = 1.0
        if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
            cost_floor = max(0.1, (r['numInput'] * self.recipes[r['input']]['price'])
                             / r['production'])
        ref = max(cost_floor, ref)
        self._price_ref[good] = max(0.1, min(50.0, ref))

    def _gather_import_pool(self, good):"""
assert old in src, "ref-update-anchor"
src = src.replace(old, new, 1)

# ---- 4. Discriminatory clear (insert before _sell_imports) ----
old = """    def _sell_imports(self, pool, good, price, remaining_qty):"""
new = """    def _clear_discriminatory(self, good, ref, total_asks, total_bids,
                               imp_pool, agents, t):
        \"\"\"Cheapest-first pay-as-bid clear for one good.

        Builds [(ask_price, qty, seller, is_import)] for local producers and
        import lots, sorts ascending, walks buyers (hungry first); each unit
        sells at ITS OWN ask.  Locals get cash; import owners get
        dest-currency wallets.  Records import sales in _auction_import_sales.
        Returns (units_bought, cash_collected, realized_vwap).
        \"\"\"
        book = []
        for a in agents:
            if a.output != good or getattr(a, 'is_trader', False) or not getattr(a, 'alive', True):
                continue
            qty = a.inventory[good.value]
            if good == Goods.food:
                qty = max(0, qty - 2)   # producers keep 2 for themselves
            if qty > 0:
                book.append([self._calculate_ask_price(a, good, ref), qty, a, False])
        for item in imp_pool:
            trader, qty = item[0], item[1]
            ask = self._import_ask_price(trader, good)
            book.append([ask, qty, trader, True])
        book.sort(key=lambda o: o[0])  # ascending price

        if not hasattr(self, '_cached_hungry_sorted') or self._cached_hungry_turn != t:
            self._cached_hungry_sorted = sorted(
                agents, key=lambda a: a.hungry_steps, reverse=True)
            self._cached_hungry_turn = t
        buyers = self._cached_hungry_sorted

        cash_collected = 0.0
        units = 0
        prices = []
        imp_units = 0
        imp_value = 0.0
        bi = 0
        for b in book:
            ask, qty, seller, is_import = b
            if qty <= 0 or units >= total_bids:
                continue
            remaining = qty
            while remaining > 0 and units < total_bids and bi < len(buyers):
                buyer = buyers[bi]
                afford = int(buyer.cash / ask) if ask > 0 else 0
                take = min(remaining, max(0, afford))
                if take <= 0:
                    bi += 1
                    continue
                cost = take * ask
                buyer.cash -= cost
                if is_import:
                    _fx.fx_add(seller, self.home_currency, cost)
                    seller.inventory_foreign[good.value] -= take
                    imp_units += take
                    imp_value += cost
                else:
                    seller.cash += cost
                    seller.inventory[good.value] -= take
                    buyer.inv_add(good, take)
                cash_collected += cost
                units += take
                prices.extend([ask] * take)
                remaining -= take
                if buyer.cash < ask:
                    bi += 1
        self._auction_import_sales[good] = (imp_units, imp_value)
        realized = sum(prices) / len(prices) if prices else ref
        return units, cash_collected, realized

    def _sell_imports(self, pool, good, price, remaining_qty):"""
assert old in src, "clear-anchor"
src = src.replace(old, new)

# ---- 5. Replace the Phase-A uniform-price loop with the priced book ----
old = """        for good in goods_goods:
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
new = """        for good in goods_goods:
            ta = total_asks[good]
            tb = total_bids[good]
            # Phase 5 (Option C): imports + local asks merge into a PRICED
            # book; each ask transacts at ITS OWN price, cheapest first.
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
            self._update_price_ref(good, demand_ratio)
            ref = self._price_ref[good]
            if min(price_ta, tb) == 0:
                self._auction_import_sales[good] = (0, 0.0)
                continue
            total_bought, tcash, realized = self._clear_discriminatory(
                good, ref, price_ta, tb, imp_pool, agents, t)
            self.sold_log[good].append(total_bought)
            self._trade_prices[good].append(realized)"""
assert old in src, "phase-a-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("region.py Phase 5 (Option C) applied")