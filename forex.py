"""
ForexDesk — central-bank quote with reserve constraints (Phase 1).

Real-world analog: managed float / Bretton Woods / gold standard.
The central bank (region's bank) quotes a mid rate with a spread and
holds foreign reserves.  Convertibility is hard-capped by available
reserves (can't print foreign currency), and the mid rate adjusts by
reserve pressure (reserve drain -> domestic currency weakens ->
imports become more expensive -> self-correcting).

Phase 3 (interbank order book) can layer on top by quoting inside the
band exposed here (mid / spread / band) without restructuring.
"""

import math


DESK_FX_POOL_SEED = 2000.0      # domestic money the bank sets aside for FX
DESK_FX_POOL_TARGET_FRAC = 0.15  # mean-revert fx_pool toward 15% of deposits
DESK_TARGET_RESERVES = 2500.0    # desired holdings of each foreign currency
DESK_INITIAL_RESERVES = 3000.0   # war-chest of foreign currency at start
# (raised from 1000/1200: 100-turn runs drained both desks to 0 reserves and
#  pinned the rate at the band ceiling — initial stock was far below the
#  realized trade volume, stalling convertibility)
DESK_ADJ_SPEED = 0.05            # per-turn rate adjustment speed
DESK_SPREAD = 0.02               # round-trip cost fraction (2%)
DESK_BAND = (0.4, 2.5)           # rate bounds (policy floor/ceiling);
# widened from (0.5, 2.0): sustained reserve pressure pinned both desks
# at the ceiling even after damping — more room lets the float express
# relative competitiveness instead of resting on the band wall


def fx_wallets(a):
    """Return a's wallet dict, lazily creating it if needed."""
    w = getattr(a, 'wallets', None)
    if w is None:
        w = {}
        a.wallets = w
    return w


def fx_balance(a, currency):
    """Balance of *currency* in a's wallet (None-safe, no allocation)."""
    w = getattr(a, 'wallets', None)
    return w.get(currency, 0.0) if w else 0.0


def fx_add(a, currency, amount):
    """Add to a's wallet balance; returns new balance. Lazy materialize."""
    if amount == 0:
        return fx_balance(a, currency)
    w = fx_wallets(a)
    w[currency] = w.get(currency, 0.0) + amount


def fx_sub(a, currency, amount):
    """Subtract from a's wallet balance (floored at 0). Returns new balance."""
    if amount == 0:
        return fx_balance(a, currency)
    w = getattr(a, 'wallets', None)
    if w is None:
        return 0.0
    w[currency] = max(0.0, w.get(currency, 0.0) - amount)
    return w[currency]


def fx_clear(a):
    """Drop a's wallet entirely (dead agents, no-heir escheat)."""
    w = getattr(a, 'wallets', None)
    if w is not None:
        w.clear()


class ForexDesk:
    """A region's central-bank FX desk quoting home<->foreign rates.

    Convention: ``mid`` is *home units per 1 unit of foreign* currency.
    So for Region_A with partner Region_B, ``mid = 1.2`` means 1 B buys 1.2 A.
    """

    def __init__(self, home_currency, other_currency, bank=None, *,
                 mid=1.0, spread=DESK_SPREAD,
                 target_reserves=DESK_TARGET_RESERVES,
                 initial_reserves=DESK_INITIAL_RESERVES,
                 adj_speed=DESK_ADJ_SPEED, band=DESK_BAND):
        self.home = home_currency
        self.other = other_currency
        self.bank = bank
        self.mid = float(mid)
        self.spread = float(spread)
        self.target_reserves = float(target_reserves)
        self.adj_speed = float(adj_speed)
        self.band = band
        self.ppp_target = 1.0  # PPP anchor: home basket / foreign basket
        self.log = []  # (t, mid, reserves) history
        # Interbank order book (Phase 3): entries are
        #   {'kind': 'bid'|'ask', 'trader': trader, 'qty': float, 'rate': float}
        self.book = []
        if bank is not None:
            self._seed_bank(bank, initial_reserves)

    def post_order(self, kind, trader, qty, rate):
        """Post a bid (buy foreign) or ask (sell foreign) to this desk's book."""
        if qty <= 0 or rate <= 0:
            return 0.0
        self.book.append({'kind': kind, 'trader': trader, 'qty': qty,
                          'rate': rate})
        return qty

    def clear_book(self):
        """Match crossed orders inside the bank's rate band.

        A bid (buy foreign) at rate B crosses an ask (sell foreign) at rate A
        when B >= A.  Matching transfers foreign between the two traders'
        wallets bilaterally, and home cash between them:  the bidder pays
        (qty * A) home cash to the asker, both in home currency.  This is
        conservation-safe (home cash moves home-cash; foreign wallet moves
        foreign wallet).  Uses the ASK's rate A as the trade price so the
        bidder gets the more favorable fill for the market maker.
        Returns total home value matched.
        """
        total_home = 0.0
        bids = [o for o in self.book if o['kind'] == 'bid']
        asks = [o for o in self.book if o['kind'] == 'ask']
        # Sort: highest bids first, lowest asks first (best price)
        bids.sort(key=lambda o: -o['rate'])
        asks.sort(key=lambda o: o['rate'])
        i = j = 0
        _heartbeat = len(bids) + len(asks) + 1  # defensive: every iteration
        # must advance at least one pointer; cap anyway to avoid deadlock
        while i < len(bids) and j < len(asks) and _heartbeat > 0:
            _heartbeat -= 1
            b = bids[i]
            a = asks[j]
            if b['rate'] < a['rate']:
                i += 1
                continue  # no cross; move to next bid
            price = a['rate']  # match at ask rate
            btrader = b['trader']
            atrader = a['trader']
            # Cap the match by the asker's ACTUAL wallet balance (the posted
            # qty may exceed it if the ask persisted across turns while the
            # trader's wallet shrank).  Also cap by the bidder's home cash.
            avail_foreign = fx_balance(atrader, self.other)
            qty = min(b['qty'], a['qty'], avail_foreign)
            if qty <= 0:
                j += 1
                continue
            home = qty * price
            if btrader.cash < home:
                home = btrader.cash
                qty = home / price if price > 0 else 0.0
            if qty <= 0:
                i += 1
                continue
            # Home leg (both are home-region traders)
            btrader.cash -= home
            atrader.cash += home
            # Foreign leg: transfer exactly what fx_sub actually removes
            before = fx_balance(atrader, self.other)
            fx_sub(atrader, self.other, qty)
            moved = before - fx_balance(atrader, self.other)
            fx_add(btrader, self.other, moved)
            total_home += moved * price
            b['qty'] -= moved
            a['qty'] -= moved
            if a['qty'] <= 0 or fx_balance(atrader, self.other) <= 0:
                j += 1
            if b['qty'] <= 0:
                i += 1
        self.book = [o for o in self.book if o['qty'] > 0]
        return total_home

    def _seed_bank(self, bank, initial_reserves):
        """Seed the bank's foreign-reserve war chest + domestic FX pool."""
        bank.foreign_reserves.setdefault(self.other, float(initial_reserves))
        if bank.fx_pool <= 0:
            bank.fx_pool = DESK_FX_POOL_SEED

    # ------------------------------------------------------------------
    # Quotes
    # ------------------------------------------------------------------

    def buy_rate(self):
        """Home units a trader receives per 1 unit of foreign (trader sells FX)."""
        return self.mid * (1.0 - self.spread / 2.0)

    def sell_rate(self):
        """Home units a trader must pay per 1 unit of foreign (trader buys FX)."""
        return self.mid * (1.0 + self.spread / 2.0)

    def expected_repatriate_rate(self):
        """Rate traders expect when converting foreign earnings home."""
        return self.buy_rate()

    def save_rate(self, region):
        """Sync this desk's mid into the region's legacy exchange_rate field."""
        region.exchange_rate = self.mid
        return self.mid

    # ------------------------------------------------------------------
    # Reserve-pressure update (managed float)
    # ------------------------------------------------------------------

    def update(self, t, bank=None, fx_regime='managed', ppp_target=None):
        """Adjust mid from reserve pressure and record history.

        *fixed*: mid pinned at 1.0 (parity) — convertibility still reserve-capped.
        *managed* (default): mid moved by reserve-pressure rule.
        *floating*: Phase 3 order book; for now behaves like managed.

        Phase 6: log-space capped step (the old multiplicative update
        compounded past the band once a desk drained) + a slow PPP anchor so
        the rate tracks relative basket costs instead of drifting to the band.
        """
        bank = bank if bank is not None else self.bank
        if bank is None:
            return self.mid

        # Mean-revert the domestic FX pool toward a fraction of deposits so
        # the desk doesn't permanently exhaust its ability to pay out.
        deposits = max(0.0, bank.total_deposits)
        target_pool = deposits * DESK_FX_POOL_TARGET_FRAC
        if False:
            bank.fx_pool += 0.0

        reserves = bank.foreign_reserves.get(self.other, 0.0)

        if fx_regime == 'fixed':
            self.mid = 1.0
        else:
            ratio = reserves / self.target_reserves if self.target_reserves > 0 else 1.0
            # Drain (ratio < 1) -> foreign scarce -> mid up (home weakens),
            # discouraging imports and encouraging exports / repatriation.
            # Log-space BOUNDED step: can't overshoot the band in one turn.
            pressure = self.adj_speed * (1.0 / max(0.05, ratio) - 1.0)
            pressure = max(-0.02, min(0.02, pressure))
            new_mid = self.mid * math.exp(pressure)
            # PPP anchor: slow pull toward partner/home basket-cost ratio.
            if ppp_target is not None and ppp_target > 0:
                self.ppp_target = ppp_target
            if self.ppp_target > 0:
                ppp_gap = math.log(self.ppp_target / max(0.01, self.mid))
                new_mid *= math.exp(0.005 * ppp_gap)
            self.mid = max(self.band[0], min(self.band[1], new_mid))

        self.log.append((t, self.mid, reserves))
        return self.mid


# =============================================================================
# Bank-level conversion (booked on the Bank for conservation transparency)
# =============================================================================

def sell_fx_to_bank(bank, trader, currency, amount, rate):
    """Trader sells *currency* (foreign) to the bank; bank pays home currency.

    Constraint: bank's domestic FX pool (fx_pool) caps the payout.
    Conservation: trader wallet -foreign; bank foreign_reserves +foreign;
    bank fx_pool -home; trader cash +home.  Both currencies conserved.
    Returns home amount actually paid.
    """
    amount = min(amount, fx_balance(trader, currency))
    if amount <= 0:
        return 0.0
    home = amount * rate
    max_pay = max(0.0, bank.fx_pool)
    if home > max_pay:
        home = max_pay
        amount = home / rate if rate > 0 else 0.0
    if amount <= 0:
        return 0.0
    fx_sub(trader, currency, amount)
    bank.foreign_reserves[currency] += amount
    bank.fx_pool -= home
    trader.cash += home
    return home


def buy_fx_from_bank(bank, trader, currency, amount, rate):
    """Trader buys *currency* (foreign) from the bank, paying home currency.

    Constraint: bank's foreign reserves cap the sale.
    Returns amount of foreign currency actually bought.
    """
    amount = min(amount, bank.foreign_reserves.get(currency, 0.0))
    if amount <= 0:
        return 0.0
    home = amount * rate
    if trader.cash < home:
        home = trader.cash
        amount = home / rate if rate > 0 else 0.0
    if amount <= 0:
        return 0.0
    fx_add(trader, currency, amount)
    bank.foreign_reserves[currency] -= amount
    bank.fx_pool += home
    trader.cash -= home
    return amount


# =============================================================================
# Per-trader repatriation
# =============================================================================

def repatriate_trader(trader, region, t):
    """Convert a trader's foreign wallet back to home currency at region's desk.

    Returns home-currency value repatriated (and credited to _trader_revenue).
    """
    desk = getattr(region, 'forex', None)
    if desk is None or not getattr(trader, 'is_trader', False):
        return 0.0
    bal = fx_balance(trader, desk.other)
    if bal <= 0:
        return 0.0
    rate = desk.buy_rate()
    home = sell_fx_to_bank(region.bank, trader, desk.other, bal, rate)
    if home > 0:
        trader._trader_revenue += home
        return home
    return 0.0


def repatriate_traders(agents, region, t):
    """Repatriate all traders in *agents* belonging to *region*.

    Called at the end of foreign_sell so every audit point sees wallets ~ 0.
    Returns total home value repatriated.
    """
    total = 0.0
    for a in agents:
        if not getattr(a, 'is_trader', False):
            continue
        total += repatriate_trader(a, region, t)
    return total


# =============================================================================
# Setup + per-currency audit
# =============================================================================

def connect_regions(region_a, region_b, t=0):
    """Wire up bilateral ForexDesks between two regions.

    Creates a desk on each region (home=own, other=partner), seeds reserves
    and FX pools, and returns (desk_a, desk_b).
    """
    desk_a = ForexDesk(region_a.home_currency, region_b.home_currency,
                       bank=region_a.bank)
    desk_b = ForexDesk(region_b.home_currency, region_a.home_currency,
                       bank=region_b.bank)
    region_a.forex = desk_a
    region_b.forex = desk_b
    seed_trader_wallet(region_a, region_b, t)
    seed_trader_wallet(region_b, region_a, t)
    return desk_a, desk_b


def _give_working_capital(trader, bank, currency, amount, rate):
    """Trader buys *amount* of foreign *currency* from its home bank.

    Conservation-safe replacement for the old free seed: home money moves
    from the trader's deposit into the bank's fx_pool, and foreign money
    moves from the bank's reserves into the trader's wallet.  Both
    currencies are conserved; nothing is printed.
    Returns foreign amount actually obtained.
    """
    if amount <= 0:
        return 0.0
    amount = min(amount, bank.foreign_reserves.get(currency, 0.0))
    if amount <= 0:
        return 0.0
    home = amount * rate
    max_home = bank.deposits.get(trader, 0) + trader.cash
    if home > max_home:
        home = max_home
        amount = home / rate if rate > 0 else 0.0
    if amount <= 0:
        return 0.0
    # Home leg: draw from trader deposit first, then cash
    from_deposit = min(home, bank.deposits.get(trader, 0))
    if from_deposit > 0:
        bank.total_deposits -= from_deposit
        bank.deposits[trader] -= from_deposit
    home_cash = home - from_deposit
    if home_cash > 0:
        trader.cash -= home_cash
    bank.fx_pool += home
    # Foreign leg: reserves -> wallet
    bank.foreign_reserves[currency] -= amount
    fx_add(trader, currency, amount)
    return amount


def seed_trader_wallet(region, partner, t=0, desk=None):
    """Give each trader an initial foreign float OUT OF WORKING CAPITAL.

    The old _seed_trader_wallets printed 100 of partner currency per trader
    out of thin air.  Now traders buy their float from the home bank:
      home deposit/cash -> fx_pool  (home currency conserved)
      reserves -> wallet            (foreign currency conserved)

    *desk* selects the conversion desk (defaults to region.forex).  In a
    multi-neighbor world each trader may float in several partner currencies,
    so callers pass the per-partner desk.

    Returns total foreign amount seeded.
    """
    desk = desk if desk is not None else region.forex
    total = 0.0
    for a in region.agents:
        if not getattr(a, 'is_trader', False):
            continue
        total += _give_working_capital(a, region.bank, partner.home_currency,
                                       100.0, desk.sell_rate())
    return total


def connect_desks(region, partner, t=0):
    """Wire a bilateral desk pair for a multi-neighbor setup.

    Creates a ForexDesk on each region (home=own, other=partner), stores it
    in the region's ``forex_desks[partner.name]``, seeds trader wallets with
    the partner currency, and — when the partner is the region's primary
    ``destination_region`` — keeps the legacy ``region.forex`` alias in sync.
    Returns (desk_region, desk_partner).
    """
    desk = ForexDesk(region.home_currency, partner.home_currency,
                     bank=region.bank)
    pdesk = ForexDesk(partner.home_currency, region.home_currency,
                      bank=partner.bank)
    region.forex_desks[partner.name] = desk
    partner.forex_desks[region.name] = pdesk
    if getattr(region, 'destination_region', None) is partner:
        region.forex = desk
    if getattr(partner, 'destination_region', None) is region:
        partner.forex = pdesk
    seed_trader_wallet(region, partner, t, desk=desk)
    seed_trader_wallet(partner, region, t, desk=pdesk)
    return desk, pdesk


def audit_currency_total(regions, currency):
    """Total global supply of *currency* across all agents, banks, reserves.

    Conservation invariant: each currency's total is unchanged by trade and
    FX conversion (fx_pool pays out home money only; reserves just shift
    foreign money between holders).
    """
    total = 0.0
    for r in regions:
        bank = r.bank
        if r.home_currency == currency:
            total += sum(a.cash for a in r.agents)
            total += bank.equity
            total += bank.fx_pool
            if getattr(r, 'charity', None) is not None:
                total += r.charity.agent.cash
        # Foreign currency held by this region's agents (wallets)
        total += sum(fx_balance(a, currency) for a in r.agents)
        # Foreign currency held by this region's bank (reserves)
        total += bank.foreign_reserves.get(currency, 0.0)
    return total

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
        repatriate_traders(region.trader_agents, region, t)

        # ---- Desk last resort: fill residual bids from reserves ----
        for order in list(desk.book):
            if order['kind'] != 'bid':
                continue
            trader = order['trader']
            qty = order['qty']
            if qty <= 0:
                continue
            bought = buy_fx_from_bank(bank, trader, other, qty,
                                      desk.sell_rate())
            if bought > 0:
                order['qty'] -= bought
        # Drop fully-filled bids and STALE asks (trader's wallet was drained
        # by repatriation this same turn, so those asks can never fill).
        # Without this, foreign_sell stacks a fresh ask per turn and the book
        # grows without bound -> O(T^2) hang.
        desk.book = [o for o in desk.book
                     if o['qty'] > 0 and o['kind'] == 'ask'
                     and fx_balance(o['trader'], other) > 0]

    return result


def _cycle_one_desk(region, partner, desk, t):
    """Run one desk's interbank cycle for region<->partner.

    Shared by cycle_market (legacy single-partner) and cycle_all_markets
    (multi-neighbor).  See cycle_market docstring for mechanics.
    Returns home value matched on this desk.
    """
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

    # ---- Desk last resort: repatriate residual asks ----
    for trader in region.trader_agents:
        if trader.home_region != region.name:
            continue
        bal = fx_balance(trader, other)
        if bal > 0:
            rate = desk.buy_rate()
            home = sell_fx_to_bank(bank, trader, other, bal, rate)
            if home > 0:
                trader._trader_revenue += home

    # ---- Desk last resort: fill residual bids from reserves ----
    for order in list(desk.book):
        if order['kind'] != 'bid':
            continue
        trader = order['trader']
        qty = order['qty']
        if qty <= 0:
            continue
        bought = buy_fx_from_bank(bank, trader, other, qty, desk.sell_rate())
        if bought > 0:
            order['qty'] -= bought

    # Drop fully-filled bids and STALE asks (trader's wallet was drained
    # by repatriation this same turn, so those asks can never fill).
    desk.book = [o for o in desk.book
                 if o['qty'] > 0 and o['kind'] == 'ask'
                 and fx_balance(o['trader'], other) > 0]
    return matched


def cycle_all_markets(regions, t=0):
    """Run one interbank cycle across every region-neighbour desk.

    For each region and each of its forex_desks (one per neighbour), run the
    cycle body (bid / clear / repatriate / desk-fill).  Legacy single-partner
    setups with only ``region.forex`` set are also served.
    Returns {f'{region.name}->{partner.name}': matched_value} for each desk.
    """
    result = {}
    for region in regions:
        desks = getattr(region, 'forex_desks', None)
        if desks:
            for pname, desk in desks.items():
                partner = region.neighbors.get(pname)
                if partner is None:
                    # desk exists but neighbor list not wired (shouldn't
                    # happen in ring/nation setups); fall back to name match
                    partner = next((r for r in regions if r.name == pname), None)
                if partner is None:
                    continue
                result[f"{region.name}->{pname}"] = _cycle_one_desk(
                    region, partner, desk, t)
        else:
            desk = getattr(region, 'forex', None)
            if desk is not None:
                partner = getattr(region, 'destination_region', None)
                if partner is not None:
                    result[f"{region.name}->{partner.name}"] = _cycle_one_desk(
                        region, partner, desk, t)
    return result


def _get_working_capital_target():
    return WORKING_CAPITAL_TARGET
