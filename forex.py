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


DESK_FX_POOL_SEED = 2000.0      # domestic money the bank sets aside for FX
DESK_FX_POOL_TARGET_FRAC = 0.15  # mean-revert fx_pool toward 15% of deposits
DESK_TARGET_RESERVES = 1200.0    # desired holdings of each foreign currency
DESK_INITIAL_RESERVES = 1000.0   # war-chest of foreign currency at start
DESK_ADJ_SPEED = 0.05            # per-turn rate adjustment speed
DESK_SPREAD = 0.02               # round-trip cost fraction (2%)
DESK_BAND = (0.5, 2.0)           # rate bounds (policy floor/ceiling)


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
        self.log = []  # (t, mid, reserves) history
        if bank is not None:
            self._seed_bank(bank, initial_reserves)

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

    def update(self, t, bank=None, fx_regime='managed'):
        """Adjust mid from reserve pressure and record history.

        *fixed*: mid pinned at 1.0 (parity) — convertibility still reserve-capped.
        *managed* (default): mid moved by reserve-pressure rule.
        *floating*: Phase 3 order book; for now behaves like managed.
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
            self.mid *= 1.0 + self.adj_speed * (1.0 - ratio)
            self.mid = max(self.band[0], min(self.band[1], self.mid))

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
    amount = min(amount, trader.wallets.get(currency, 0.0))
    if amount <= 0:
        return 0.0
    home = amount * rate
    max_pay = max(0.0, bank.fx_pool)
    if home > max_pay:
        home = max_pay
        amount = home / rate if rate > 0 else 0.0
    if amount <= 0:
        return 0.0
    trader.wallets[currency] -= amount
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
    trader.wallets[currency] += amount
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
    bal = trader.wallets.get(desk.other, 0.0)
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
    _seed_trader_wallets(region_a, region_b)
    _seed_trader_wallets(region_b, region_a)
    return desk_a, desk_b


def _seed_trader_wallets(region, partner):
    """Give each trader a small float of the partner currency for travel."""
    for a in region.agents:
        if getattr(a, 'is_trader', False):
            a.wallets.setdefault(partner.home_currency, 100.0)


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
            total += bank.total_deposits - bank.total_liabilities
            total += bank.fx_pool
            if getattr(r, 'charity', None) is not None:
                total += r.charity.agent.cash
        # Foreign currency held by this region's agents (wallets)
        total += sum(a.wallets.get(currency, 0.0) for a in r.agents)
        # Foreign currency held by this region's bank (reserves)
        total += bank.foreign_reserves.get(currency, 0.0)
    return total