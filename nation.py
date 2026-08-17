"""
Nation — sovereign wrapper around a Government for the REGNUM tile game (M0).

A Nation owns one sovereign Government and a list of tiles (Region objects).
It is deliberately dependency-light: it imports `government` and `region` (for
type annotations) but does NOT start a simulation or touch module-level sim
state at import time.  Only creating a Nation registers its Government with
`econsim_states.governments` (so `find_government_for_agent` resolves).

Currency seam (future phase): `Nation.currency` is the authoritative field.
`add_tile` sets `region.home_currency = nation.currency` at claim time so all
tiles of a nation share one currency.  A later `set_currency()` hook re-points
tile currencies + rebuilds FX desks; `forex.audit_currency_total` already
iterates arbitrary currency names, so a switch is audit-safe by construction.

M0 scope:
  - Nation init over 1..N Regions; gov.regions populated;
    legitimacy baseline 0.6; importable without running a sim.
  - add_tile / remove_tile
  - treasury() accessor
  - claim_tile / transfer_tile (single-call citizen reparenting)  [M0.4]
"""

from __future__ import annotations

import econsim_states
from government import Government


DEFAULT_LEGITIMACY = 0.6


class Nation:
    """One sovereign state owning 0..N tiles (Regions).

    Attributes
    ----------
    name : str
        Nation identifier.  Also the default currency name.
    government : Government
        The sovereign government of this nation.  Its ``regions`` list is
        populated by ``add_tile``.
    tiles : list[Region]
        Tiles (Region objects) currently under this nation's control.
    legitimacy : float
        0..1 consent metric; baseline 0.6 (per priority_tasks.md M0.1).
    regime_type : str
        e.g. 'autocracy' | 'democracy' | 'theocracy'.  Default 'autocracy'.
    currency : str
        Authoritative currency name for all tiles.
    claims : dict[str, float]
        Claimant nation name -> claim strength (M0.4).  This nation's own
        entry reflects its ownership; foreign entries are pending/invasive.
    """

    def __init__(self, name: str, currency: str | None = None,
                 regime_type: str = 'autocracy',
                 legitimacy: float = DEFAULT_LEGITIMACY,
                 initial_cash: float = 0.0,
                 t: int = 0,
                 register: bool = True):
        self.name = name
        self.currency = currency if currency is not None else name
        self.regime_type = regime_type
        self.legitimacy = float(
            max(0.0, min(1.0, legitimacy if legitimacy is not None
                         else DEFAULT_LEGITIMACY)))
        self.tiles: list = []
        self.provinces: list = []   # v3 province model (shared institutions)
        self.claims: dict = {name: 1.0}
        # ---- M3 regime state (population-driven consent / ruling faction) ----
        # ruling_faction: name of the faction currently holding power (None =
        # no faction in power).  opposition: list of faction names that were
        # deposed and continue as opposition (M3.6 engine-only UI seam).
        self.ruling_faction = None
        self.opposition: list = []
        self._incumbent_faction = None   # incumbent for betrayal memory (M3.3)
        self.regime_log: list = []       # per-turn regime events (state archive)
        self.claim_log: list = []        # per-turn claim events (v3 claims)

        # One sovereign Government per Nation.  The Government class already
        # owns `regions` + `citizen_ids`; add_tile wires them.
        self.government = Government(name, t, initial_cash=initial_cash)
        # Give the government a stable currency pointer too (same seam).
        self.government.currency = self.currency

        if register:
            econsim_states.governments.append(self.government)

    # ------------------------------------------------------------------
    # Tile membership
    # ------------------------------------------------------------------

    def add_tile(self, region) -> None:
        """Take sovereignty of *region*.

        Wires:
          1. region.owner_nation -> self
          2. region.home_currency = self.currency  (nation-shared currency seam)
          3. region.gov registered into this nation's government.regions
          4. every non-gov agent of the region re-registered as a citizen
        """
        region.owner_nation = self
        region.home_currency = self.currency
        # Sync the government's currency pointer (kept in lockstep).
        self.government.currency = self.currency
        # Record the owning nation's claim on the tile (strength 1.0).
        claims = self._claims_of(region)
        claims[self.name] = 1.0
        if region not in self.tiles:
            self.tiles.append(region)
        if region not in self.government.regions:
            self.government.regions.append(region)
        for agent in list(getattr(region, 'agents', [])):
            if agent is getattr(region.gov, 'agent', None):
                continue
            self.government._add_citizen(agent)
            agent.region = region.name
            agent.home_currency = self.currency
            # v3: seed the persistent homeland once at claim time (the
            # tile is the birth homeland for founders).  NEVER updated on
            # later moves - only citizenship changes; the claim rule
            # counts stable origin_nation so it stays meaningful.
            if getattr(agent, 'origin_nation', None) is None:
                agent.origin_nation = self.name

    def remove_tile(self, region) -> bool:
        """Release sovereignty over *region* without transferring it.

        Removes region from tiles + gov.regions.  Citizen re-registration is
        the caller's responsibility (transfer uses _reparent_tile; removal is
        for eviction-style flows that later migrate the population).
        Returns True if the tile was owned.
        """
        if region not in self.tiles:
            return False
        self.tiles = [r for r in self.tiles if r is not region]
        if region in self.government.regions:
            self.government.regions = [
                r for r in self.government.regions if r is not region]
        if getattr(region, 'owner_nation', None) is self:
            region.owner_nation = None
        return True

    def owned_tiles(self) -> list:
        """Alias returning the territory list (map code reads this)."""
        return list(self.tiles)

    # ------------------------------------------------------------------
    # Treasury
    # ------------------------------------------------------------------

    def treasury(self) -> dict:
        """Nation-level treasury snapshot across all tiles.

        Sums the sovereign government's own cash/deposits plus each tile
        government's cash/deposits and food inventory.  Deposits are read
        from each tile's bank.  Conserved-money view: this never moves money,
        it only tallies.
        """
        gov = self.government
        bank = getattr(gov, '_bank_ref', None)
        cash = gov.agent.cash
        deposits = 0.0
        if bank is not None:
            deposits = bank.deposits.get(gov.agent, 0.0)
        food = int(getattr(gov, 'food_inventory', 0))

        for region in self.tiles:
            rgov = getattr(region, 'gov', None)
            if rgov is not None and rgov is not gov:
                cash += rgov.agent.cash
                rbank = getattr(region, 'bank', None)
                if rbank is not None:
                    deposits += rbank.deposits.get(rgov.agent, 0.0)
                food += int(getattr(rgov, 'food_inventory', 0))

        return {
            'name': self.name,
            'currency': self.currency,
            'cash': cash,
            'deposits': deposits,
            'food': food,
            'total': cash + deposits,
        }

    # ------------------------------------------------------------------
    # Ownership / claims  (M0.4 seam)
    # ------------------------------------------------------------------

    @staticmethod
    def _claims_of(region) -> dict:
        """Returns the region's claims dict, lazily creating it if absent.

        Region does not own a ``claims`` attribute until M0.4 touches
        Region.__init__; this helper keeps Nation working on plain Regions
        in the meantime.
        """
        claims = getattr(region, 'claims', None)
        if claims is None:
            claims = {}
            region.claims = claims
        return claims

    def claim_tile(self, region, strength: float = 1.0) -> None:
        """Record a claim on *region*; owning-nation claims adjust strength."""
        claims = self._claims_of(region)
        claims[self.name] = max(claims.get(self.name, 0.0), strength)
        if getattr(region, 'owner_nation', None) is self:
            region.owner_nation = self
            claims[self.name] = 1.0

    def transfer_tile(self, region, new_nation) -> bool:
        """Transfer sovereignty of *region* to *new_nation*.

        Single-call citizen reparenting: resolves every agent in the tile to
        the new nation's government (the seam M4 annexation / eviction reuse).
        Money and goods never move — only jurisdiction does.
        Returns True on success.
        """
        old_gov = self.government
        new_gov = new_nation.government
        self._reparent_tile(region, old_gov, new_gov, new_nation)
        return True

    def _reparent_tile(self, region, old_gov, new_gov, new_nation) -> None:
        """Migrate *region* from old_gov to new_gov jurisdiction.

        Moves tiles membership, gov.regions membership, owner_nation,
        home_currency, and all agent citizenship in one call.
        """
        # 1. Territory lists
        if region in self.tiles:
            self.tiles = [r for r in self.tiles if r is not region]
        if region in old_gov.regions:
            old_gov.regions = [r for r in old_gov.regions if r is not region]
        # 2. Ownership pointer
        region.owner_nation = new_nation
        region.home_currency = new_nation.currency
        new_gov.currency = new_nation.currency
        # 3. Government membership
        if region not in new_gov.regions:
            new_gov.regions.append(region)
        if region not in new_nation.tiles:
            new_nation.tiles.append(region)
        # 4. Citizenship migration (every non-gov agent)
        for agent in list(getattr(region, 'agents', [])):
            if agent is getattr(region.gov, 'agent', None):
                continue
            old_gov.citizen_ids.discard(agent.id)
            new_gov._add_citizen(agent)
            agent.region = region.name
            agent.home_currency = new_nation.currency
        # 5. Claims bookkeeping: the new owner claims the tile at 1.0; the
        #    old nation's claim (if any) is left intact as a latent claim.
        claims = self._claims_of(region)
        claims[new_nation.name] = 1.0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __repr__(self):
        return (f"Nation({self.name}, tiles={len(self.tiles)}, "
                f"legitimacy={self.legitimacy:.2f}, cur={self.currency})")