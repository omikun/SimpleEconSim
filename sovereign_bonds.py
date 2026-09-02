"""
sovereign_bonds.py — International Sovereign Rating Bureau (ISRB) & Cross-Border Sovereign Bond Market.

Provides:
- SovereignBond: Cross-border sovereign debt instrument (20/50/100 turn terms, 0.10%-0.38% per-turn yield).
- InternationalRatingBureau (ISRB): Central rating agency managing credit ratings (AAA to CCC),
  influence lobbying, adversary audits, board seats, and scandal risks.
- SovereignBondMarket: Global debt registry executing coupon distributions, bond redemptions,
  sovereign defaults, and foreign reserve portfolios with strict money conservation.
"""

from __future__ import annotations
import uuid
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nation import Nation

# Standardized Credit Rating Tiers and Base Per-Turn Yield Rates (aligned with in-game bank loan rate ~0.10%/turn)
RATING_TIERS = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]
RATING_BASE_YIELDS = {
    "AAA": 0.0010,  # 0.10% / turn ($1.00 / turn on $1,000)
    "AA":  0.0012,  # 0.12% / turn ($1.20 / turn on $1,000)
    "A":   0.0015,  # 0.15% / turn ($1.50 / turn on $1,000)
    "BBB": 0.0018,  # 0.18% / turn ($1.80 / turn on $1,000)
    "BB":  0.0022,  # 0.22% / turn ($2.20 / turn on $1,000)
    "B":   0.0028,  # 0.28% / turn ($2.80 / turn on $1,000)
    "CCC": 0.0038,  # 0.38% / turn ($3.80 / turn on $1,000 - Junk/High Risk)
}

# Duration Yield Premiums
DURATION_PREMIUMS = {
    20: 0.0000,   # 0.00% extra
    50: 0.0002,   # +0.02% / turn for 50-turn medium term
    100: 0.0005,  # +0.05% / turn for 100-turn century term
}


@dataclass
class SovereignBond:
    """A cross-border sovereign debt bond issued by one nation and held by another."""
    bond_id: str
    issuer_nation: str
    holder_nation: str
    principal: float
    coupon_rate: float        # per-turn interest rate (e.g. 0.0012 = 0.12%/turn)
    duration_turns: int       # 20, 50, or 100 turns
    issued_turn: int
    maturity_turn: int
    status: str = "active"    # 'active' | 'matured' | 'defaulted' | 'redeemed'

    @property
    def per_turn_coupon(self) -> float:
        return round(self.principal * self.coupon_rate, 2)


class InternationalRatingBureau:
    """The International Sovereign Rating Bureau (ISRB) evaluating sovereign risk and managing influence."""

    def __init__(self):
        # Nation name -> temporary tier modifier (+1 upgrade, -1 downgrade)
        self.rating_modifiers: dict[str, int] = {}
        # Nation name -> turns remaining on modifier
        self.modifier_expiry: dict[str, int] = {}
        # Nations holding permanent board seats
        self.board_seats: set[str] = set()

    def get_rating(self, nation: Nation, world: dict | None = None) -> tuple[str, float]:
        """Compute the ISRB Credit Rating and 20t base yield for a sovereign nation."""
        treasury = nation.treasury()
        total_wealth = treasury.get('total', 0.0)
        debt = nation.government.agent.cash_debt if hasattr(nation.government.agent, 'cash_debt') else 0.0

        # Base rating score (0 to 6 index in RATING_TIERS)
        if total_wealth > 2500.0:
            tier_idx = 0  # AAA
        elif total_wealth > 1800.0:
            tier_idx = 1  # AA
        elif total_wealth > 1200.0:
            tier_idx = 2  # A
        elif total_wealth > 700.0:
            tier_idx = 3  # BBB
        elif total_wealth > 400.0:
            tier_idx = 4  # BB
        elif total_wealth > 150.0:
            tier_idx = 5  # B
        else:
            tier_idx = 6  # CCC

        # Apply active war penalty
        if world and world.get('diplomacy'):
            try:
                wars = world['diplomacy'].get_active_wars()
                if any(w.involves(nation.name) for w in wars):
                    tier_idx = min(6, tier_idx + 1)
            except Exception:
                pass

        # Apply board seat buffer (+1 tier improvement)
        if nation.name in self.board_seats:
            tier_idx = max(0, tier_idx - 1)

        # Apply active influence lobbying modifier (+1 upgrade or -1 downgrade)
        mod = self.rating_modifiers.get(nation.name, 0)
        tier_idx = max(0, min(6, tier_idx - mod))

        rating = RATING_TIERS[tier_idx]
        base_yield = RATING_BASE_YIELDS[rating]
        return rating, base_yield

    def get_market_yield(self, nation: Nation, duration: int = 20, world: dict | None = None) -> tuple[str, float]:
        """Return credit rating and total market yield for a specific bond duration."""
        rating, base_yield = self.get_rating(nation, world)
        term_premium = DURATION_PREMIUMS.get(duration, 0.0)
        total_yield = round(base_yield + term_premium, 5)
        return rating, total_yield

    def lobby_upgrade(self, nation: Nation, t: int) -> tuple[bool, str, bool]:
        """Lobby ISRB for a +1 tier rating upgrade ($200 fee). 15% scandal chance."""
        fee = 200.0
        gov = nation.government
        if gov.agent.cash < fee:
            return False, f"Insufficient treasury cash (${gov.agent.cash:.0f} < ${fee:.0f}).", False

        gov.agent.cash -= fee

        # 15% chance of Rating Scandal
        if random.random() < 0.15:
            # Scandal exposed: -2 tier penalty for 15 turns
            self.rating_modifiers[nation.name] = -2
            self.modifier_expiry[nation.name] = t + 15
            return False, f"SCANDAL! ISRB influence peddling exposed for {nation.name}! Rating penalized -2 tiers.", True

        self.rating_modifiers[nation.name] = 1
        self.modifier_expiry[nation.name] = t + 20
        return True, f"Successfully lobbied ISRB: {nation.name} credit rating upgraded by +1 tier for 20 turns.", False

    def lobby_adversary_downgrade(self, nation: Nation, target_nation_name: str, t: int) -> tuple[bool, str, bool]:
        """Commission an aggressive audit targeting a rival's debt ($350 fee). 20% scandal chance."""
        fee = 350.0
        gov = nation.government
        if gov.agent.cash < fee:
            return False, f"Insufficient treasury cash (${gov.agent.cash:.0f} < ${fee:.0f}).", False

        gov.agent.cash -= fee

        # 20% chance of Scandal
        if random.random() < 0.20:
            self.rating_modifiers[nation.name] = -1
            self.modifier_expiry[nation.name] = t + 10
            return False, f"DIPLOMATIC BLOWBACK! Smear audit against {target_nation_name} leaked back to {nation.name}.", True

        self.rating_modifiers[target_nation_name] = -1
        self.modifier_expiry[target_nation_name] = t + 15
        return True, f"Aggressive ISRB Audit published: {target_nation_name} downgraded by -1 tier for 15 turns.", False

    def acquire_board_seat(self, nation: Nation) -> tuple[bool, str]:
        """Acquire a permanent seat on the ISRB Board of Governors ($600 fee)."""
        fee = 600.0
        gov = nation.government
        if nation.name in self.board_seats:
            return False, f"{nation.name} already holds a permanent seat on the ISRB Board."
        if gov.agent.cash < fee:
            return False, f"Insufficient treasury cash (${gov.agent.cash:.0f} < ${fee:.0f})."

        gov.agent.cash -= fee
        self.board_seats.add(nation.name)
        return True, f"{nation.name} acquired a permanent seat on the ISRB Board of Governors (+1 Rating Tier buffer)."

    def step_modifiers(self, t: int):
        """Expire temporary rating modifiers."""
        expired = [n for n, exp in self.modifier_expiry.items() if t >= exp]
        for n in expired:
            self.rating_modifiers.pop(n, None)
            self.modifier_expiry.pop(n, None)


class SovereignBondMarket:
    """Global Sovereign Bond Market managing debt instruments, foreign reserves, and payouts."""

    def __init__(self):
        self.bonds: list[SovereignBond] = []
        self.isrb = InternationalRatingBureau()

    def issue_bond(self, issuer: Nation, holder: Nation | None, principal: float,
                   duration_turns: int, t: int, world: dict | None = None) -> tuple[bool, str, SovereignBond | None]:
        """Issue a domestic or cross-border sovereign bond."""
        principal = float(principal)
        if principal <= 0:
            return False, "Bond principal must be positive.", None

        if duration_turns not in (20, 50, 100):
            duration_turns = 20

        rating, yield_rate = self.isrb.get_market_yield(issuer, duration_turns, world)
        bond_id = f"bnd_{uuid.uuid4().hex[:6]}"
        holder_name = holder.name if holder else "International Investors"

        if holder:
            # Cross-border purchase: holder pays principal to issuer
            if holder.government.agent.cash < principal:
                return False, f"{holder.name} treasury has insufficient cash (${holder.government.agent.cash:.0f} < ${principal:.0f}).", None
            holder.government.agent.cash -= principal
            issuer.government.agent.cash += principal
        else:
            # Primary market issuance: capital injected into issuer
            issuer.government.agent.cash += principal

        bond = SovereignBond(
            bond_id=bond_id,
            issuer_nation=issuer.name,
            holder_nation=holder_name,
            principal=principal,
            coupon_rate=yield_rate,
            duration_turns=duration_turns,
            issued_turn=t,
            maturity_turn=t + duration_turns,
            status="active"
        )
        self.bonds.append(bond)
        return True, f"Issued {duration_turns}t Sovereign Bond #{bond_id} for ${principal:.0f} ({rating} @ {yield_rate*100:.2f}%/t).", bond

    def redeem_bond_early(self, bond_id: str, world: dict, t: int) -> tuple[bool, str]:
        """Issuer calls and repays a bond early to eliminate recurring interest obligations."""
        bond = next((b for b in self.bonds if b.bond_id == bond_id and b.status == "active"), None)
        if not bond:
            return False, "Active bond not found."

        nations_by_name = {n.name: n for n in world.get('nations', [])}
        issuer = nations_by_name.get(bond.issuer_nation)
        holder = nations_by_name.get(bond.holder_nation)

        if not issuer:
            return False, "Issuer nation not found."

        if issuer.government.agent.cash < bond.principal:
            return False, f"Insufficient treasury cash to redeem principal (${issuer.government.agent.cash:.0f} < ${bond.principal:.0f})."

        issuer.government.agent.cash -= bond.principal
        if holder:
            holder.government.agent.cash += bond.principal

        bond.status = "redeemed"
        return True, f"Redeemed Sovereign Bond #{bond_id} for ${bond.principal:.0f}."

    def get_bonds_held_by(self, nation_name: str) -> list[SovereignBond]:
        """Return list of active foreign bonds held by this nation (Assets / Reserves)."""
        return [b for b in self.bonds if b.holder_nation == nation_name and b.status == "active"]

    def get_bonds_owed_by(self, nation_name: str) -> list[SovereignBond]:
        """Return list of active domestic bonds owed by this nation (Liabilities)."""
        return [b for b in self.bonds if b.issuer_nation == nation_name and b.status == "active"]

    def step(self, world: dict, t: int):
        """Execute per-turn coupon servicing, maturities, and defaults with exact money conservation."""
        nations_by_name = {n.name: n for n in world.get('nations', [])}
        self.isrb.step_modifiers(t)

        for bond in list(self.bonds):
            if bond.status != "active":
                continue

            issuer = nations_by_name.get(bond.issuer_nation)
            holder = nations_by_name.get(bond.holder_nation)
            if not issuer:
                continue

            # 1. Maturity Redemption
            if t >= bond.maturity_turn:
                if issuer.government.agent.cash >= bond.principal:
                    issuer.government.agent.cash -= bond.principal
                    if holder:
                        holder.government.agent.cash += bond.principal
                    bond.status = "matured"
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'FINANCE', f"Sovereign Bond #{bond.bond_id} matured! {issuer.name} repaid ${bond.principal:.0f} to {bond.holder_nation}.", (120, 220, 140))
                else:
                    # Sovereign Default on Principal
                    bond.status = "defaulted"
                    self.isrb.rating_modifiers[issuer.name] = -3
                    self.isrb.modifier_expiry[issuer.name] = t + 25
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'ALERT', f"SOVEREIGN DEFAULT! {issuer.name} failed to repay ${bond.principal:.0f} on Bond #{bond.bond_id}!", (240, 80, 80))
                continue

            # 2. Per-Turn Coupon Servicing
            coupon = bond.per_turn_coupon
            if coupon > 0:
                if issuer.government.agent.cash >= coupon:
                    issuer.government.agent.cash -= coupon
                    if holder:
                        holder.government.agent.cash += coupon
                else:
                    # Default on Coupon
                    bond.status = "defaulted"
                    self.isrb.rating_modifiers[issuer.name] = -3
                    self.isrb.modifier_expiry[issuer.name] = t + 25
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'ALERT', f"SOVEREIGN COUPON DEFAULT! {issuer.name} defaulted on ${coupon:.2f} payment for Bond #{bond.bond_id}!", (240, 80, 80))


_GLOBAL_BOND_MARKET: SovereignBondMarket | None = None


def get_bond_market() -> SovereignBondMarket:
    """Return singleton SovereignBondMarket instance."""
    global _GLOBAL_BOND_MARKET
    if _GLOBAL_BOND_MARKET is None:
        _GLOBAL_BOND_MARKET = SovereignBondMarket()
    return _GLOBAL_BOND_MARKET
