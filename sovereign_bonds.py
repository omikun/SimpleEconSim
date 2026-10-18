"""
sovereign_bonds.py — International Sovereign Rating Bureau (ISRB) & Cross-Border Sovereign Bond Market.

Provides:
- BondOffering: Public sovereign bond offering with a 1-turn announcement window before going live.
- SovereignBond: Active cross-border or domestically underwritten sovereign debt instrument.
- InternationalRatingBureau (ISRB): Central rating agency managing credit ratings (AAA to CCC),
  influence lobbying, adversary audits, board seats, and scandal risks.
- SovereignBondMarket: Global debt registry executing 1-turn announcements, autonomous AI reserve buying,
  domestic bank underwriting, coupon distributions, bond redemptions, and defaults.
"""

from __future__ import annotations
import uuid
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from finance_trace import account_ref, transfer_contract

if TYPE_CHECKING:
    from nation import Nation


_BOND_OPERATION_TYPES = {
    'sovereign_bond_purchase': 'principal_issue',
    'sovereign_bond_proceeds': 'principal_issue',
    'sovereign_bond_early_redemption': 'early_principal_redemption',
    'sovereign_bond_redemption_received': 'early_principal_redemption',
    'sovereign_bond_maturity_paid': 'maturity_principal',
    'sovereign_bond_maturity_received': 'maturity_principal',
    'sovereign_bond_coupon_paid': 'coupon_payment',
    'sovereign_bond_coupon_received': 'coupon_payment',
    'sovereign_bond_domestic_underwrite': 'domestic_bank_underwrite',
    'municipal_sewer_bond_underwritten': 'municipal_sewer_underwrite',
}


def _bond_transfer_evidence(nation, kind, t, bond, treasury_delta, inputs):
    """Describe the cash leg without implying an unrecorded counterparty leg."""
    operation_type = _BOND_OPERATION_TYPES.get(kind, kind)
    operation_turn = t if operation_type == 'coupon_payment' else 'principal'
    operation_id = f'bond:{bond.bond_id}:{operation_type}:{operation_turn}'
    counterparty = inputs.get('counterparty')
    local_currency = getattr(nation, 'currency', None)
    bond_currency = getattr(bond, 'currency', None) or local_currency or 'USD'
    local_cash_after = float(nation.government.agent.cash)
    local_cash_before = local_cash_after - float(treasury_delta)
    local_account = account_ref(
        'nation_treasury', nation.name, local_currency,
        subaccount='government_agent.cash', balance_before=local_cash_before,
        balance_after=local_cash_after, balance_scope='government_agent.cash')
    if counterparty == 'Domestic Commercial Banks':
        counterparty_account = account_ref(
            'domestic_bank_portfolio', nation.name, bond_currency,
            cash_balance_status='not_captured')
    else:
        counterparty_account = account_ref(
            'nation_treasury', counterparty, bond_currency,
            subaccount='government_agent.cash',
            cash_balance_status='captured_in_matching_leg'
            if counterparty else 'counterparty_not_recorded')
    if treasury_delta < 0:
        payer_account, payee_account, side = local_account, counterparty_account, 'payer'
    else:
        payer_account, payee_account, side = counterparty_account, local_account, 'payee'

    gross_amount = float(inputs.get('coupon_total', abs(treasury_delta)))
    if operation_type in ('domestic_bank_underwrite', 'municipal_sewer_underwrite'):
        gross_amount = float(inputs.get('funding_amount', bond.principal))
    if operation_type == 'coupon_payment' and inputs.get('coupon_total') is not None:
        gross_amount = float(inputs['coupon_total'])
    funding_components = None
    if operation_type == 'coupon_payment':
        resident_amount = float(inputs.get('resident_contributions', 0.0))
        funding_components = [
            {'account_type': 'nation_treasury',
             'amount': abs(float(treasury_delta)) if side == 'payer'
             else max(0.0, gross_amount - resident_amount),
             'currency': local_currency},
            {'account_type': 'resident_households',
             'amount': resident_amount, 'currency': bond_currency,
             'balance_status': 'aggregate_contribution_only'}]
    cash_creation_rule = None
    if operation_type == 'domestic_bank_underwrite':
        cash_creation_rule = 'simulation_adds_principal_to_nation_cash_without_bank_cash_debit'
    return transfer_contract(
        operation_id, operation_type, side=side, amount=gross_amount,
        amount_currency=bond_currency, payer_account=payer_account,
        payee_account=payee_account,
        local_cash_leg_amount=abs(float(treasury_delta)),
        local_cash_leg_currency=local_currency,
        counterparty_leg_status=(
            'bank_cash_debit_not_modelled'
            if counterparty == 'Domestic Commercial Banks'
            else 'paired_nation_leg_uses_same_operation_id'),
        funding_components=funding_components,
        cash_creation_rule=cash_creation_rule,
        mutation_reference={'bond_id': bond.bond_id, 'event_kind': kind,
                            'turn': t})


def _trace_bond(nation, kind, t, bond, *, treasury_delta=None, **inputs):
    """Record a sovereign debt event against its nation and treasury."""
    tiles = getattr(nation, 'tiles', [])
    if not tiles:
        return
    from run_trace import emit
    data = {'bond_id': bond.bond_id, 'issuer': bond.issuer_nation,
            'holder': bond.holder_nation, 'principal': bond.principal,
            'coupon_rate': bond.coupon_rate, 'maturity_turn': bond.maturity_turn,
            'status': bond.status, 'purpose': bond.bond_purpose,
            'currency': getattr(bond, 'currency', None)}
    if treasury_delta is not None:
        transfer = _bond_transfer_evidence(nation, kind, t, bond,
                                           treasury_delta, inputs)
        data.update({'operation_id': transfer['operation_id'],
                     'operation_type': transfer['operation_type']})
    data.update(inputs)
    emit(tiles[0], kind=kind, record_class='transfer' if treasury_delta is not None else 'outcome',
         phase='finance', subject={'type': 'nation', 'id': nation.name},
         metric_id='finance.sovereign_bond', unit=nation.currency,
         after=bond.principal, formula_id='finance.sovereign_bond_lifecycle.v1',
         inputs=data)
    if treasury_delta is not None:
        emit(tiles[0], kind=kind, record_class='transfer', phase='finance',
             subject={'type': 'nation', 'id': nation.name},
             metric_id='finance.treasury_flow', unit=nation.currency,
             after=treasury_delta,
             inputs={'bond_id': bond.bond_id, 'bond_event': kind,
                     'counterparty': bond.holder_nation if nation.name == bond.issuer_nation
                     else bond.issuer_nation, 'principal': bond.principal,
                     'purpose': bond.bond_purpose, **inputs,
                     'transfer_contract': transfer})

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
class BondOffering:
    """A public sovereign bond offering with a 1-turn announcement window before going live."""
    offering_id: str
    issuer_nation: str
    principal: float
    coupon_rate: float
    duration_turns: int
    announced_turn: int
    live_turn: int             # announced_turn + 1
    status: str = "announced"  # 'announced' | 'live' | 'filled' | 'cancelled'
    currency: str = "USD"

    @property
    def per_turn_coupon(self) -> float:
        return round(self.principal * self.coupon_rate, 2)


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
    bond_purpose: str = "sovereign" # 'sovereign' | 'municipal_sewer'
    target_tile_name: str = ""
    currency: str = "USD"

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
    """Global Sovereign Bond Market managing debt instruments, offerings, and foreign reserves."""

    def __init__(self):
        self.bonds: list[SovereignBond] = []
        self.offerings: list[BondOffering] = []
        self.isrb = InternationalRatingBureau()

    def announce_bond_offering(self, issuer: Nation, principal: float, duration_turns: int,
                               t: int, world: dict | None = None) -> tuple[bool, str, BondOffering | None]:
        """Announce a public sovereign bond offering that goes live 1 turn later."""
        principal = float(principal)
        if principal <= 0:
            return False, "Bond principal must be positive.", None

        if duration_turns not in (20, 50, 100):
            duration_turns = 20

        rating, yield_rate = self.isrb.get_market_yield(issuer, duration_turns, world)
        offering_id = f"off_{uuid.uuid4().hex[:6]}"

        offering = BondOffering(
            offering_id=offering_id,
            issuer_nation=issuer.name,
            principal=principal,
            coupon_rate=yield_rate,
            duration_turns=duration_turns,
            announced_turn=t,
            live_turn=t + 1,
            status="announced",
            currency=getattr(issuer, 'currency', 'USD')
        )
        self.offerings.append(offering)

        if world:
            from client.desktop.engine import ticker_push
            ticker_push(
                world, t, 'FINANCE',
                f"📢 {issuer.name} announced ${principal:.0f} ({duration_turns}t @ {yield_rate*100:.2f}%/t) Bond Offering. Auction goes live Turn {t+1}!",
                (245, 190, 80)
            )

        return True, f"Announced ${principal:.0f} ({duration_turns}t @ {yield_rate*100:.2f}%/t) Sovereign Bond Offering #{offering_id}. Live next turn.", offering

    @property
    def active_offerings(self) -> list[BondOffering]:
        """Backward-compatible alias for offerings list."""
        return self.offerings

    def get_announced_offerings(self) -> list[BondOffering]:
        """Return list of upcoming bond offerings currently in the 1-turn announcement window."""
        return [o for o in self.offerings if o.status == "announced"]

    def get_live_offerings(self) -> list[BondOffering]:
        """Return list of active live bond offerings open for purchase."""
        return [o for o in self.offerings if o.status == "live"]

    def purchase_bond(self, buyer_nation_name: str, issuer_nation_name: str,
                      principal: float, coupon_rate: float, duration_turns: int, t: int) -> SovereignBond:
        """Helper to directly create and record a purchased bond in foreign reserves."""
        bond_id = f"bnd_{uuid.uuid4().hex[:6]}"
        bond = SovereignBond(
            bond_id=bond_id,
            issuer_nation=issuer_nation_name,
            holder_nation=buyer_nation_name,
            principal=principal,
            coupon_rate=coupon_rate,
            duration_turns=duration_turns,
            issued_turn=t,
            maturity_turn=t + duration_turns,
            status="active",
            currency=getattr(issuer_nation, 'currency', 'USD')
        )
        self.bonds.append(bond)
        return bond

    def purchase_live_offering(self, buyer: Nation, offering_id: str,
                               world: dict, t: int) -> tuple[bool, str, SovereignBond | None]:
        """A foreign nation (or player) purchases a live bond offering into foreign reserves."""
        offering = next((o for o in self.offerings if o.offering_id == offering_id and o.status == "live"), None)
        if not offering:
            return False, "Live offering not found or already filled.", None

        if buyer.name == offering.issuer_nation:
            return False, "Cannot purchase your own bond offering as foreign reserves.", None

        nations_by_name = {n.name: n for n in world.get('nations', [])}
        issuer = nations_by_name.get(offering.issuer_nation)
        if not issuer:
            return False, "Issuer nation not found.", None

        if buyer.government.agent.cash < offering.principal:
            return False, f"Insufficient treasury cash (${buyer.government.agent.cash:.0f} < ${offering.principal:.0f}).", None

        # Money Transfer: Buyer -> Issuer
        buyer.government.agent.cash -= offering.principal
        issuer.government.agent.cash += offering.principal

        bond_id = f"bnd_{uuid.uuid4().hex[:6]}"
        bond = SovereignBond(
            bond_id=bond_id,
            issuer_nation=issuer.name,
            holder_nation=buyer.name,
            principal=offering.principal,
            coupon_rate=offering.coupon_rate,
            duration_turns=offering.duration_turns,
            issued_turn=t,
            maturity_turn=t + offering.duration_turns,
            status="active",
            currency=offering.currency
        )
        self.bonds.append(bond)
        offering.status = "filled"
        _trace_bond(buyer, 'sovereign_bond_purchase', t, bond,
                    treasury_delta=-offering.principal,
                    counterparty=issuer.name, offering_id=offering.offering_id)
        _trace_bond(issuer, 'sovereign_bond_proceeds', t, bond,
                    treasury_delta=offering.principal,
                    counterparty=buyer.name, offering_id=offering.offering_id)

        from client.desktop.engine import ticker_push
        ticker_push(
            world, t, 'FINANCE',
            f"🌐 {buyer.name} purchased {issuer.name}'s ${offering.principal:.0f} ({offering.duration_turns}t) Sovereign Bond #{bond_id} into Foreign Reserves!",
            (120, 220, 140)
        )

        return True, f"Purchased {issuer.name}'s ${offering.principal:.0f} Bond #{bond_id} (+${bond.per_turn_coupon:.2f}/t).", bond

    def issue_bond(self, issuer: Nation, holder: Nation | None, principal: float,
                   duration_turns: int, t: int, world: dict | None = None) -> tuple[bool, str, SovereignBond | None]:
        """Direct bond creation (used for direct underwrites or immediate testing)."""
        principal = float(principal)
        if principal <= 0:
            return False, "Bond principal must be positive.", None

        if duration_turns not in (20, 50, 100):
            duration_turns = 20

        rating, yield_rate = self.isrb.get_market_yield(issuer, duration_turns, world)
        bond_id = f"bnd_{uuid.uuid4().hex[:6]}"
        holder_name = holder.name if holder else "Domestic Commercial Banks"

        if holder:
            if holder.government.agent.cash < principal:
                return False, f"{holder.name} treasury has insufficient cash (${holder.government.agent.cash:.0f} < ${principal:.0f}).", None
            holder.government.agent.cash -= principal
            issuer.government.agent.cash += principal
        else:
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
            status="active",
            currency=getattr(issuer, 'currency', 'USD')
        )
        self.bonds.append(bond)
        if holder:
            _trace_bond(holder, 'sovereign_bond_purchase', t, bond,
                        treasury_delta=-principal, counterparty=issuer.name)
        _trace_bond(issuer, 'sovereign_bond_proceeds', t, bond,
                    treasury_delta=principal, counterparty=holder_name)
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
        _trace_bond(issuer, 'sovereign_bond_early_redemption', t, bond,
                    treasury_delta=-bond.principal, counterparty=bond.holder_nation)
        if holder:
            _trace_bond(holder, 'sovereign_bond_redemption_received', t, bond,
                        treasury_delta=bond.principal, counterparty=issuer.name)
        return True, f"Redeemed Sovereign Bond #{bond_id} for ${bond.principal:.0f}."

    def get_bonds_held_by(self, nation_name: str) -> list[SovereignBond]:
        """Return list of active foreign bonds held by this nation (Assets / Reserves)."""
        return [b for b in self.bonds if b.holder_nation == nation_name and b.status == "active"]

    def get_bonds_owed_by(self, nation_name: str) -> list[SovereignBond]:
        """Return list of active domestic bonds owed by this nation (Liabilities)."""
        return [b for b in self.bonds if b.issuer_nation == nation_name and b.status == "active"]

    def issue_municipal_sewer_bond(self, issuer: Nation, tile, t: int, world: dict | None = None) -> tuple[bool, str, SovereignBond | None]:
        """Float a 50-turn Municipal Revenue Sewer Bond to finance the Bazalgette Intercepting Sewer Network."""
        principal = 1000.0
        duration_turns = 50
        tier, base_yield = self.isrb.get_market_yield(issuer, duration_turns, world)

        # 1. Start Bazalgette Sewer megaproject on the tile
        from buildings import BUILDING_RECIPES, ConstructionProject
        from construction_politics import find_or_emerge_contractor
        contractor = find_or_emerge_contractor(tile, principal, t)

        proj = ConstructionProject(
            project_id=f"proj_sewer_{uuid.uuid4().hex[:6]}",
            nation_name=issuer.name,
            region=tile,
            recipe=BUILDING_RECIPES['trunk_sewer'],
            contractor=contractor,
            started_turn=t
        )
        if not hasattr(tile, 'construction_projects'):
            tile.construction_projects = []
        tile.construction_projects.append(proj)
        if hasattr(issuer, 'construction_projects') and proj not in issuer.construction_projects:
            issuer.construction_projects.append(proj)

        # 2. Credit the contractor; the source side has no cash debit in this model.
        contractor_cash_before = float(contractor.cash)
        contractor.cash += principal
        contractor_cash_after = float(contractor.cash)
        proj.emergency_subsidies_received = getattr(proj, 'emergency_subsidies_received', 0.0) + principal

        # 3. Create Bond instance held by Domestic Commercial Banks
        bond_id = f"bnd_sewer_{uuid.uuid4().hex[:6]}"
        bond = SovereignBond(
            bond_id=bond_id,
            issuer_nation=issuer.name,
            holder_nation="Domestic Commercial Banks",
            principal=principal,
            coupon_rate=base_yield,
            duration_turns=duration_turns,
            issued_turn=t,
            maturity_turn=t + duration_turns,
            status="active",
            bond_purpose="municipal_sewer",
            target_tile_name=tile.name,
            currency=getattr(issuer, 'currency', 'USD')
        )
        self.bonds.append(bond)
        operation_id = f'bond:{bond_id}:municipal_sewer_underwrite:principal'
        from run_trace import emit
        emit(tile, kind='municipal_sewer_underwriting_credit_created',
             record_class='outcome', phase='finance',
             subject={'type': 'construction_project', 'id': proj.project_id},
             metric_id='finance.cash_creation', unit=bond.currency,
             after=principal,
             inputs={'operation_id': operation_id,
                     'bond_id': bond_id,
                     'funding_source': 'domestic_bank_underwriting',
                     'funding_source_balance_status': 'no_cash_debit_modelled',
                     'recipient_account': {
                         'type': 'contractor',
                         'id': getattr(contractor, 'id', None),
                         'balance_before': contractor_cash_before,
                         'balance_after': contractor_cash_after,
                         'currency': bond.currency},
                     'project_id': proj.project_id,
                     'target_tile': tile.name,
                     'reconciliation_status': 'cash_credit_without_recorded_source_debit'})
        _trace_bond(issuer, 'municipal_sewer_bond_underwritten', t, bond,
                    operation_id=operation_id,
                    contractor_id=getattr(contractor, 'id', None),
                    target_tile=tile.name, project_id=proj.project_id,
                    funding_amount=principal)

        msg = (f"🏛️ MUNICIPAL SEWER BOND: {issuer.name} issued ${principal:.0f} Municipal Revenue Bond #{bond_id} "
               f"to construct the Bazalgette Intercepting Sewer Network in {tile.name}!")
        if world:
            from client.desktop.engine import ticker_push
            ticker_push(world, t, 'FINANCE', msg, (100, 220, 140))

        return True, msg, bond

    def step(self, world: dict, t: int):
        """Step bond offerings, autonomous AI buying, domestic underwrites, coupons, and maturities."""
        nations_by_name = {n.name: n for n in world.get('nations', [])}
        self.isrb.step_modifiers(t)
        from diplomacy import get_diplomacy
        diplomacy = get_diplomacy()

        # 1. Advance Announced Offerings to Live on T >= live_turn
        for offering in self.offerings:
            if offering.status == "announced" and t >= offering.live_turn:
                offering.status = "live"
                from client.desktop.engine import ticker_push
                ticker_push(
                    world, t, 'FINANCE',
                    f"🔔 AUCTION LIVE: {offering.issuer_nation}'s ${offering.principal:.0f} ({offering.duration_turns}t) Bond offering is now open for bidding!",
                    (120, 220, 140)
                )

        # 2. Autonomous Friendly AI Purchasing
        player_nation_name = world.get('player_nation_name', '')
        live_offerings = self.get_live_offerings()

        for buyer in world.get('nations', []):
            # AI Nations with surplus cash (> $1,000) evaluate open live offerings
            if buyer.name == player_nation_name:
                continue

            if buyer.government.agent.cash < 1000.0:
                continue

            for offering in list(live_offerings):
                if offering.status != "live":
                    continue
                if offering.issuer_nation == buyer.name:
                    continue

                # Check bilateral relations: friendly (>= +0.10) and not at war
                rel = diplomacy.get_relation(buyer.name, offering.issuer_nation)
                at_war = diplomacy.are_at_war(buyer.name, offering.issuer_nation)

                if rel >= 0.10 and not at_war and buyer.government.agent.cash >= offering.principal + 500.0:
                    # AI purchases the bond into its foreign reserves
                    ok, msg, _ = self.purchase_live_offering(buyer, offering.offering_id, world, t)
                    if ok:
                        break  # 1 purchase per turn per AI nation to avoid over-concentration

        # 3. Domestic Bank Underwriting (if unpurchased after 2 turns live)
        for offering in list(self.offerings):
            if offering.status == "live" and t >= offering.live_turn + 2:
                issuer = nations_by_name.get(offering.issuer_nation)
                if issuer:
                    issuer.government.agent.cash += offering.principal
                    bond_id = f"bnd_{uuid.uuid4().hex[:6]}"
                    bond = SovereignBond(
                        bond_id=bond_id,
                        issuer_nation=issuer.name,
                        holder_nation="Domestic Commercial Banks",
                        principal=offering.principal,
                        coupon_rate=offering.coupon_rate,
                        duration_turns=offering.duration_turns,
                        issued_turn=t,
                        maturity_turn=t + offering.duration_turns,
                        status="active",
                        currency=offering.currency
                    )
                    self.bonds.append(bond)
                    offering.status = "filled"
                    _trace_bond(issuer, 'sovereign_bond_domestic_underwrite', t, bond,
                                treasury_delta=offering.principal,
                                counterparty='Domestic Commercial Banks',
                                offering_id=offering.offering_id)
                    # Register bond holding across issuer's domestic commercial banks
                    issuer_banks = [r.bank for r in getattr(issuer, 'tiles', []) if getattr(r, 'bank', None)]
                    if issuer_banks:
                        share_p = round(offering.principal / len(issuer_banks), 2)
                        share_c = round(offering.per_turn_coupon / len(issuer_banks), 2)
                        for b_inst in issuer_banks:
                            if not hasattr(b_inst, 'sovereign_bonds_held'):
                                b_inst.sovereign_bonds_held = []
                            b_inst.sovereign_bonds_held.append({
                                'bond_id': bond_id,
                                'principal': share_p,
                                'coupon': share_c,
                                'duration_turns': offering.duration_turns
                            })
                    from client.desktop.engine import ticker_push
                    ticker_push(
                        world, t, 'FINANCE',
                        f"🏛️ Domestic Commercial Banks underwrote {issuer.name}'s unsold ${offering.principal:.0f} Sovereign Bond #{bond_id}.",
                        (245, 205, 120)
                    )

        # 4. Coupon Servicing & Maturity Redemption
        for bond in list(self.bonds):
            if bond.status != "active":
                continue
            if bond.bond_purpose == 'scenario_caisse':
                # Guided campaign settlements are decided explicitly and recorded
                # by scenario_debt; the market must not auto-pay the same claim.
                continue

            issuer = nations_by_name.get(bond.issuer_nation)
            holder = nations_by_name.get(bond.holder_nation)
            if not issuer:
                continue

            # Maturity Redemption
            if t >= bond.maturity_turn:
                if issuer.government.agent.cash >= bond.principal:
                    issuer.government.agent.cash -= bond.principal
                    if holder:
                        holder.government.agent.cash += bond.principal
                    elif bond.holder_nation == "Domestic Commercial Banks":
                        issuer_banks = [r.bank for r in getattr(issuer, 'tiles', []) if getattr(r, 'bank', None)]
                        if issuer_banks:
                            share_p = bond.principal / len(issuer_banks)
                            for b_inst in issuer_banks:
                                b_inst.capital += share_p
                                b_inst.sovereign_bonds_held = [x for x in getattr(b_inst, 'sovereign_bonds_held', []) if x.get('bond_id') != bond.bond_id]
                    bond.status = "matured"
                    _trace_bond(issuer, 'sovereign_bond_maturity_paid', t, bond,
                                treasury_delta=-bond.principal,
                                counterparty=bond.holder_nation)
                    if holder:
                        _trace_bond(holder, 'sovereign_bond_maturity_received', t, bond,
                                    treasury_delta=bond.principal,
                                    counterparty=issuer.name)
                    from client.desktop.engine import ticker_push
                    ticker_push(
                        world, t, 'FINANCE',
                        f"Sovereign Bond #{bond.bond_id} matured! {issuer.name} repaid ${bond.principal:.0f} to {bond.holder_nation}.",
                        (120, 220, 140)
                    )
                else:
                    # Sovereign Default on Principal
                    bond.status = "defaulted"
                    _trace_bond(issuer, 'sovereign_bond_principal_default', t, bond,
                                principal_loss=bond.principal)
                    self.isrb.rating_modifiers[issuer.name] = -3
                    self.isrb.modifier_expiry[issuer.name] = t + 25
                    if bond.holder_nation == "Domestic Commercial Banks":
                        issuer_banks = [(r, r.bank) for r in getattr(issuer, 'tiles', [])
                                        if getattr(r, 'bank', None)]
                        if issuer_banks:
                            loss_share = bond.principal / len(issuer_banks)
                            for bank_tile, b_inst in issuer_banks:
                                was_frozen = getattr(b_inst, 'is_frozen', False)
                                b_inst.write_down_bonds(
                                    loss_share, trace_region=bank_tile,
                                    bond_id=bond.bond_id, issuer_nation=issuer.name,
                                    default_kind='principal_default',
                                    defaulted_amount=bond.principal, turn=t)
                                b_inst.sovereign_bonds_held = [x for x in getattr(b_inst, 'sovereign_bonds_held', []) if x.get('bond_id') != bond.bond_id]
                                if getattr(b_inst, 'is_frozen', False) and not was_frozen:
                                    from client.desktop.engine import ticker_push
                                    ticker_push(
                                        world, t, 'ALERT',
                                        f"🚨 BANKING CONTAGION: Sovereign default wiped out bank equity in {issuer.name}! Emergency Corralito deposit freeze enacted!",
                                        (255, 60, 60)
                                    )
                    try:
                        from imperialism import get_imperialism_manager
                        get_imperialism_manager().register_default(bond, world, t)
                    except Exception:
                        pass
                    from client.desktop.engine import ticker_push
                    ticker_push(
                        world, t, 'ALERT',
                        f"SOVEREIGN DEFAULT! {issuer.name} failed to repay ${bond.principal:.0f} on Bond #{bond.bond_id}!",
                        (240, 80, 80)
                    )
                continue

            # Per-Turn Coupon Servicing
            coupon = bond.per_turn_coupon
            if coupon > 0:
                funds_collected = 0.0
                if getattr(bond, 'bond_purpose', '') == 'municipal_sewer' and bond.target_tile_name:
                    target_tile = next((tl for tl in getattr(issuer, 'tiles', []) if tl.name == bond.target_tile_name), None)
                    if target_tile:
                        for a in getattr(target_tile, 'agents', []):
                            if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_government', False):
                                fee = min(0.10, a.cash)
                                a.cash -= fee
                                funds_collected += fee
                                if funds_collected >= coupon:
                                    break

                remaining_coupon = max(0.0, coupon - funds_collected)
                if issuer.government.agent.cash >= remaining_coupon:
                    issuer.government.agent.cash -= remaining_coupon
                    if holder:
                        holder.government.agent.cash += coupon
                    elif bond.holder_nation == "Domestic Commercial Banks":
                        issuer_banks = [r.bank for r in getattr(issuer, 'tiles', []) if getattr(r, 'bank', None)]
                        if issuer_banks:
                            share_c = coupon / len(issuer_banks)
                            for b_inst in issuer_banks:
                                b_inst.pay_interest(share_c)
                    _trace_bond(issuer, 'sovereign_bond_coupon_paid', t, bond,
                                treasury_delta=-remaining_coupon,
                                coupon_total=coupon, resident_contributions=funds_collected,
                                counterparty=bond.holder_nation)
                    if holder:
                        _trace_bond(holder, 'sovereign_bond_coupon_received', t, bond,
                                    treasury_delta=coupon, counterparty=issuer.name,
                                    coupon_total=coupon,
                                    resident_contributions=funds_collected)
                else:
                    # Default on Coupon
                    bond.status = "defaulted"
                    _trace_bond(issuer, 'sovereign_bond_coupon_default', t, bond,
                                coupon_due=coupon, available_treasury_cash=issuer.government.agent.cash,
                                resident_contributions=funds_collected)
                    self.isrb.rating_modifiers[issuer.name] = -3
                    self.isrb.modifier_expiry[issuer.name] = t + 25
                    if bond.holder_nation == "Domestic Commercial Banks":
                        issuer_banks = [(r, r.bank) for r in getattr(issuer, 'tiles', [])
                                        if getattr(r, 'bank', None)]
                        if issuer_banks:
                            loss_share = bond.principal / len(issuer_banks)
                            for bank_tile, b_inst in issuer_banks:
                                was_frozen = getattr(b_inst, 'is_frozen', False)
                                b_inst.write_down_bonds(
                                    loss_share, trace_region=bank_tile,
                                    bond_id=bond.bond_id, issuer_nation=issuer.name,
                                    default_kind='coupon_default',
                                    defaulted_amount=coupon, turn=t)
                                b_inst.sovereign_bonds_held = [x for x in getattr(b_inst, 'sovereign_bonds_held', []) if x.get('bond_id') != bond.bond_id]
                                if getattr(b_inst, 'is_frozen', False) and not was_frozen:
                                    from client.desktop.engine import ticker_push
                                    ticker_push(
                                        world, t, 'ALERT',
                                        f"🚨 BANKING CONTAGION: Sovereign coupon default wiped out bank equity in {issuer.name}! Emergency Corralito deposit freeze enacted!",
                                        (255, 60, 60)
                                    )
                    try:
                        from imperialism import get_imperialism_manager
                        get_imperialism_manager().register_default(bond, world, t)
                    except Exception:
                        pass
                    from client.desktop.engine import ticker_push
                    ticker_push(
                        world, t, 'ALERT',
                        f"SOVEREIGN COUPON DEFAULT! {issuer.name} defaulted on ${coupon:.2f} payment for Bond #{bond.bond_id}!",
                        (240, 80, 80)
                    )


_GLOBAL_BOND_MARKET: SovereignBondMarket | None = None


def get_bond_market() -> SovereignBondMarket:
    """Return singleton SovereignBondMarket instance."""
    global _GLOBAL_BOND_MARKET
    if _GLOBAL_BOND_MARKET is None:
        _GLOBAL_BOND_MARKET = SovereignBondMarket()
    return _GLOBAL_BOND_MARKET
