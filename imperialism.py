"""
imperialism.py — Financial Imperialism, Gunboat Debt Enforcement, and Concessions.

Implements core geopolitical finance dynamics:
  1. Customs Receivership: Creditor nations intercept customs tariffs and taxes
     from defaulting debtor states to service delinquent sovereign debt.
     100% money-conserved transfer from debtor revenue to creditor treasury.
  2. Debt-Enforcement War & Gunboat Blockade: Creditors use military force to
     blockade ports, freezing maritime logistics and starving trade until debt terms are met.
  3. Unequal Treaties & Concession Zones: Creditors demand tariff exemptions and exclusive
     resource extraction concessions with profit repatriation in exchange for debt restructuring.
  4. Core-Periphery Dependency Index: Evaluates each nation's structural standing
     (Imperial Core vs Indebted Periphery) based on external debt exposure and terms of trade.
  5. Sovereign Debt Repudiation: Revolutionary or resistant regimes can unilaterally
     repudiate imperial debts and expel receiverships, sparking imperial crises.
"""

from __future__ import annotations
import math
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from nation import Nation
    from region import Region


@dataclass
class ThreatAssessment:
    """Calculus of military force, projection logistics, and takeover credibility."""
    creditor_name: str
    debtor_name: str
    creditor_force: float          # Combined combat strength of standing units + enforcers
    debtor_force: float            # Combined combat strength of debtor army + garrisons + militias
    force_ratio: float             # creditor_force / max(1.0, debtor_force)
    expeditionary_cost: float      # Estimated maintenance/transit cost per turn
    debt_amount: float             # Defaulted debt to collect
    logistics_viable: bool         # Creditor can afford projection and cost is rational
    resistance_deterrence: float   # Unrest & popular insurgency friction
    credibility_score: float       # S_cred: continuous credibility metric
    tier: str                      # 'Overwhelming Hegemony' | 'Credible Threat' | 'Contested / Risky' | 'Hollow Bluff'
    reason: str                    # Summary explanation


@dataclass
class CustomsReceivership:
    """An imperial customs receivership intercepting debtor state revenues."""
    receivership_id: str
    creditor_nation: str
    debtor_nation: str
    intercept_share: float = 0.40       # 40% of tariffs and taxes diverted (65% in Caisse)
    remaining_debt: float = 500.0       # Outstanding debt balance to collect
    total_collected: float = 0.0        # Cumulative diverted funds
    start_turn: int = 0
    status: str = "active"              # 'active' | 'cleared' | 'expelled' | 'suspended'
    enforcement_mode: str = "military"  # 'military' | 'hired_agents'
    agent_retainer_cost: float = 2.0    # per turn cost to maintain hired agents
    agents_hired: int = 1
    level: str = "customs"              # 'customs' | 'caisse_de_la_dette'
    turns_active: int = 0
    seized_tolls: float = 0.0           # Cumulative toll revenue seized from routes
    seized_granary_grain: float = 0.0   # Cumulative physical grain seized from granaries
    seized_royalties: float = 0.0       # Cumulative resource/timber/nitrate royalties seized
    creditor_obj: Optional[Any] = None



def _disburse_agent_funds(world: dict | None, creditor: Any | None, amount: float):
    """Conserve currency by paying hired agents/bailiffs from creditor funds into living non-gov agents."""
    if amount <= 0:
        return
    recipient = None
    if creditor and hasattr(creditor, 'tiles'):
        for tile in creditor.tiles:
            for a in getattr(tile, 'agents', []):
                if getattr(a, 'alive', True) and not getattr(a, 'is_government', False):
                    recipient = a
                    break
            if recipient:
                break
    if not recipient and world:
        for tile in world.get('tiles', []):
            for a in getattr(tile, 'agents', []):
                if getattr(a, 'alive', True) and not getattr(a, 'is_government', False):
                    recipient = a
                    break
            if recipient:
                break
    if recipient:
        recipient.cash += amount


def evaluate_credible_takeover_threat(creditor: Any, debtor: Any, world: dict | None = None) -> ThreatAssessment:
    """Evaluate whether creditor has a credible military threat of armed takeover over debtor.

    Coercion Calculus:
    - Force Ratio: Creditor military units + hired agents vs Debtor army + garrisons + militias.
    - Projection & Logistics: Distance between territories, expeditionary upkeep vs creditor treasury.
    - Asymmetric Resistance Deterrence: Debtor tile unrest, barricades, general strikes.
    - Composite Credibility Score (S_cred):
        >= 2.0: Overwhelming Hegemony (can impose Caisse de la Dette, toll/granary seizures)
        1.2 - 2.0: Credible Threat (can enforce Customs Receivership, naval blockades)
        0.7 - 1.2: Contested / Risky (diplomatic workout / Brady bond restructuring)
        < 0.7: Hollow Bluff (debtor can safely repudiate foreign debt)
    """
    if world:
        nations_by_name = {n.name: n for n in world.get('nations', [])}
        if isinstance(creditor, str):
            creditor = nations_by_name.get(creditor, creditor)
        if isinstance(debtor, str):
            debtor = nations_by_name.get(debtor, debtor)

    c_name = getattr(creditor, 'name', str(creditor))
    d_name = getattr(debtor, 'name', str(debtor))

    # 1. Armed force calculations
    c_units = getattr(creditor, 'military_units', [])
    c_strength = sum(getattr(u, 'strength', getattr(u, 'soldiers', 0) * 1.0) for u in c_units)

    # Check if creditor has cash to hire mercenary agents if no standing units
    c_gov = getattr(creditor, 'government', None)
    c_cash = c_gov.agent.cash if (c_gov and hasattr(c_gov, 'agent')) else 0.0
    if c_strength <= 0 and c_cash >= 50.0:
        c_strength = min(150.0, c_cash * 0.5)

    d_units = getattr(debtor, 'military_units', [])
    d_strength = sum(getattr(u, 'strength', getattr(u, 'soldiers', 0) * 1.0) for u in d_units)

    d_tiles = getattr(debtor, 'tiles', [])
    for t_obj in d_tiles:
        for u in getattr(t_obj, 'military_units', []):
            if u not in d_units:
                d_strength += getattr(u, 'strength', getattr(u, 'soldiers', 0) * 1.0)

    # Minimum baseline for debtor home guard / constabulary
    effective_debtor_force = max(10.0, d_strength)
    force_ratio = c_strength / effective_debtor_force

    # 2. Logistics, distance, and expeditionary cost
    distance = 1.0
    shared_border = False
    c_tiles = getattr(creditor, 'tiles', [])
    if c_tiles and d_tiles:
        min_dist = 999.0
        for ct in c_tiles:
            for dt in d_tiles:
                dist = math.hypot(getattr(ct, 'x', 0) - getattr(dt, 'x', 0),
                                  getattr(ct, 'y', 0) - getattr(dt, 'y', 0))
                if dist < min_dist:
                    min_dist = dist
                if dt in getattr(ct, 'neighbors', {}).values() or ct in getattr(dt, 'neighbors', {}).values():
                    shared_border = True
        distance = max(1.0, min_dist)

    expeditionary_cost = round(distance * 3.0 + c_strength * 0.02, 2)

    debt_amount = 500.0
    imp_mgr = get_imperialism_manager()
    if imp_mgr:
        open_defs = imp_mgr.get_unresolved_defaults_against(d_name, c_name)
        if open_defs:
            debt_amount = sum(d.get('principal', d.get('amount', 500.0)) for d in open_defs)
        else:
            rec = imp_mgr.get_active_receivership_on(d_name)
            if rec and rec.creditor_nation == c_name:
                debt_amount = rec.remaining_debt

    logistics_viable = (c_cash >= expeditionary_cost * 2.0 or shared_border)
    if expeditionary_cost * 10 > debt_amount * 3.0 and not shared_border:
        logistics_viable = False

    # 3. Asymmetric resistance deterrence
    avg_unrest = 0.0
    has_insurgency = False
    if d_tiles:
        avg_unrest = sum(getattr(t_obj, 'unrest_level', 0.0) for t_obj in d_tiles) / len(d_tiles)
        try:
            from popular_resistance import get_popular_resistance_manager
            res_mgr = get_popular_resistance_manager()
            for t_obj in d_tiles:
                st = res_mgr.get_state(t_obj.name)
                if st.has_barricades or st.is_general_strike or st.militia_strength > 0:
                    has_insurgency = True
                    break
        except Exception:
            pass

    resistance_deterrence = 1.0 + (avg_unrest * 0.4) + (0.5 if has_insurgency else 0.0)

    # 4. Composite Credibility Score
    score = force_ratio
    if shared_border:
        score += 0.25
    if not logistics_viable:
        score *= 0.50
    if c_cash < 50.0 and not shared_border:
        score *= 0.70
    score = score / max(0.5, resistance_deterrence)
    score = max(0.0, round(score, 2))

    if score >= 2.0:
        tier = "Overwhelming Hegemony"
        reason = f"Creditor military forces ({c_strength:.0f} vs {d_strength:.0f}) hold decisive dominance. Credible takeover threat."
    elif score >= 1.2:
        tier = "Credible Threat"
        reason = f"Creditor commands superior force ({c_strength:.0f} vs {d_strength:.0f}). Receivership and blockade threats are credible."
    elif score >= 0.7:
        tier = "Contested / Risky"
        reason = f"Forces are evenly balanced ({c_strength:.0f} vs {d_strength:.0f}) or debtor resistance deterrence ({resistance_deterrence:.1f}x) is high. Takeover risks bloody quagmire."
    else:
        tier = "Hollow Bluff"
        reason = f"Creditor lacks projection capability ({c_strength:.0f} vs {d_strength:.0f}, logistics viable={logistics_viable}). Threat of armed takeover is an empty bluff."

    return ThreatAssessment(
        creditor_name=c_name,
        debtor_name=d_name,
        creditor_force=round(c_strength, 1),
        debtor_force=round(d_strength, 1),
        force_ratio=round(force_ratio, 2),
        expeditionary_cost=expeditionary_cost,
        debt_amount=round(debt_amount, 1),
        logistics_viable=logistics_viable,
        resistance_deterrence=round(resistance_deterrence, 2),
        credibility_score=score,
        tier=tier,
        reason=reason
    )


@dataclass
class UnequalTreaty:
    """Coerced treaty granting imperial concessions in exchange for debt relief."""
    treaty_id: str
    imperial_nation: str
    subject_nation: str
    treaty_type: str                    # 'tariff_exemption' | 'resource_concession'
    concession_tile: Optional[str] = None
    profit_repatriation_share: float = 0.50
    signed_turn: int = 0
    status: str = "active"              # 'active' | 'repudiated'


@dataclass
class CorePeripheryScore:
    """Structural economic standing of a sovereign nation."""
    nation_name: str
    external_debt_ratio: float          # foreign debt / treasury
    net_creditor_balance: float         # foreign bonds held - foreign bonds owed
    terms_of_trade_ratio: float         # manufactured exports / primary exports
    composite_index: float              # -1.0 (Periphery) to +1.0 (Imperial Core)
    tier: str                           # 'Imperial Core' | 'Semi-Periphery' | 'Indebted Periphery'


class ImperialismManager:
    """Global coordinator of financial imperialism, receiverships, blockades, and treaties."""

    def __init__(self):
        self.receiverships: List[CustomsReceivership] = []
        self.unequal_treaties: List[UnequalTreaty] = []
        self.blockaded_tiles: set[str] = set()       # tile_name -> blockaded
        self.blockade_enforcers: Dict[str, str] = {} # tile_name -> enforcer_nation
        self.core_periphery_scores: Dict[str, CorePeripheryScore] = {}
        self.delinquent_defaults: List[Dict[str, Any]] = []
        self.event_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Default Registration
    # ------------------------------------------------------------------

    def register_default(self, bond: Any, world: dict, t: int):
        """Record a sovereign bond default, generating enforcement casus belli for creditor."""
        entry = {
            'bond_id': bond.bond_id,
            'debtor': bond.issuer_nation,
            'creditor': bond.holder_nation,
            'principal': bond.principal,
            'coupon': getattr(bond, 'per_turn_coupon', 0.0),
            'turn': t,
            'status': 'unresolved'
        }
        self.delinquent_defaults.append(entry)

        # Lower debtor reputation and increase diplomatic grievance
        from diplomacy import get_diplomacy
        diplomacy = get_diplomacy()
        if bond.holder_nation != "Domestic Commercial Banks":
            diplomacy.adjust_relation(bond.holder_nation, bond.issuer_nation, -0.30)
            if hasattr(diplomacy, 'betrayal_memory'):
                mem_key = (bond.holder_nation, bond.issuer_nation)
                if mem_key not in diplomacy.betrayal_memory:
                    diplomacy.betrayal_memory[mem_key] = []
                diplomacy.betrayal_memory[mem_key].append({
                    't': t,
                    'treaty_type': 'sovereign_bond',
                    'reason': f"Sovereign bond #{bond.bond_id} default (${bond.principal:.0f})",
                    'severity': 0.5
                })

        ev = {
            'turn': t,
            'kind': 'IMPERIAL_DEBT_DEFAULT',
            'debtor': bond.issuer_nation,
            'creditor': bond.holder_nation,
            'amount': bond.principal,
            'msg': f"SOVEREIGN DEFAULT: {bond.issuer_nation} defaulted on debt to {bond.holder_nation}!"
        }
        self.event_log.append(ev)

    def get_unresolved_defaults_against(self, debtor_nation: str, creditor_nation: str | None = None) -> List[Dict[str, Any]]:
        """Return list of open sovereign defaults for debtor."""
        res = [d for d in self.delinquent_defaults if d['debtor'] == debtor_nation and d['status'] == 'unresolved']
        if creditor_nation:
            res = [d for d in res if d['creditor'] == creditor_nation]
        return res

    # ------------------------------------------------------------------
    # Customs Receivership & Caisse de la Dette
    # ------------------------------------------------------------------

    def can_enforce_receivership(self, creditor: Nation, debtor: Nation, world: dict | None = None) -> Tuple[bool, str, ThreatAssessment]:
        """Check whether creditor possesses credible military force to enforce receivership."""
        threat = evaluate_credible_takeover_threat(creditor, debtor, world)
        if threat.credibility_score < 0.8:
            return False, f"Cannot enforce receivership: Military takeover threat is a hollow bluff ({threat.tier}, score={threat.credibility_score:.2f}x).", threat
        return True, f"Military force supports receivership enforcement ({threat.tier}, score={threat.credibility_score:.2f}x).", threat

    def can_escalate_to_caisse(self, creditor: Nation, debtor: Nation, world: dict | None = None) -> Tuple[bool, str, ThreatAssessment]:
        """Check whether creditor commands overwhelming military hegemony to seize domestic monopolies."""
        threat = evaluate_credible_takeover_threat(creditor, debtor, world)
        rec = self.get_active_receivership_on(debtor.name)
        if not rec or rec.creditor_nation != creditor.name:
            return False, "No active receivership exists between these nations to escalate.", threat
        if rec.level == "caisse_de_la_dette":
            return False, "Receivership is already escalated to Caisse de la Dette Publique.", threat
        if threat.credibility_score < 1.4:
            return False, f"Cannot escalate to Caisse de la Dette: Insufficient military force projection ({threat.tier}, score={threat.credibility_score:.2f}x < 1.4x required). Debtor will repel seizure.", threat
        return True, f"Overwhelming military hegemony ({threat.tier}, score={threat.credibility_score:.2f}x) enables full fiscal takeover.", threat

    def escalate_to_caisse(self, receivership_id: str, world: dict | None = None, t: int = 0) -> Tuple[bool, str]:
        """Escalate customs receivership to full Caisse de la Dette Publique (65% revenue + tolls + granary seizures)."""
        rec = next((r for r in self.receiverships if r.receivership_id == receivership_id and r.status == "active"), None)
        if not rec:
            return False, "Active receivership not found."

        rec.level = "caisse_de_la_dette"
        rec.intercept_share = 0.65

        if world:
            nations = {n.name: n for n in world.get('nations', [])}
            debtor = nations.get(rec.debtor_nation)
            if debtor:
                debtor.legitimacy = max(0.05, getattr(debtor, 'legitimacy', 0.5) - 0.20)
                for tile in getattr(debtor, 'tiles', []):
                    factions = getattr(getattr(tile, 'factions', None), 'factions', {})
                    for f in factions.values():
                        f.add_grievance('foreign_oppression', 4.0)
            from worldview_engine import ticker_push
            ticker_push(
                world, t, 'ALERT',
                f"🏛️ CAISSE DE LA DETTE: {rec.creditor_nation} established fiscal administration over {rec.debtor_nation}! Seizing 65% revenues, transit tolls, and granaries!",
                (255, 60, 60)
            )
        return True, f"Receivership escalated to Caisse de la Dette Publique."

    def establish_receivership(self, creditor: Nation, debtor: Nation,
                               amount: float, t: int, world: dict | None = None,
                               hire_agents: bool = False,
                               force_override: bool = False) -> Tuple[bool, str, Optional[CustomsReceivership]]:
        """Creditor establishes a customs receivership on debtor to divert revenues until debt cleared.
        
        Gated by coercive capability: requires credible takeover threat unless agreed or override.
        """
        if creditor.name == debtor.name:
            return False, "Cannot establish receivership on own nation.", None

        # Check if active receivership already exists
        existing = next((r for r in self.receiverships
                         if r.debtor_nation == debtor.name and r.creditor_nation == creditor.name and r.status == "active"), None)
        if existing:
            existing.remaining_debt += amount
            if not getattr(existing, 'creditor_obj', None):
                existing.creditor_obj = creditor
            return True, f"Augmented active Customs Receivership on {debtor.name} by +${amount:.0f}.", existing

        # Enforcement validation: standing military forces or hired international agents
        has_military = any(getattr(u, 'soldiers', 0) > 0 for u in getattr(creditor, 'military_units', []))
        cred_gov = getattr(creditor, 'government', None)
        cred_cash = cred_gov.agent.cash if (cred_gov and hasattr(cred_gov, 'agent')) else 0.0

        if has_military and not hire_agents:
            enforce_mode = "military"
        elif cred_cash >= 50.0:
            enforce_mode = "hired_agents"
            if cred_gov and hasattr(cred_gov, 'agent'):
                cred_gov.agent.cash -= 50.0
                _disburse_agent_funds(world, creditor, 50.0)
        else:
            return False, "Creditor lacks military forces and cannot afford $50 fee to hire enforcement agents.", None

        # Coercion gating: must have credible threat unless forced or consented
        if not force_override:
            can_enf, enf_msg, threat = self.can_enforce_receivership(creditor, debtor, world)
            if not can_enf and enforce_mode == "military":
                return False, enf_msg, None

        rec_id = f"rec_{uuid.uuid4().hex[:6]}"
        receivership = CustomsReceivership(
            receivership_id=rec_id,
            creditor_nation=creditor.name,
            debtor_nation=debtor.name,
            intercept_share=0.40,
            remaining_debt=float(amount),
            start_turn=t,
            status="active",
            enforcement_mode=enforce_mode,
            creditor_obj=creditor
        )
        self.receiverships.append(receivership)

        # Mark delinquent defaults as covered by receivership
        for d in self.delinquent_defaults:
            if d['debtor'] == debtor.name and d['creditor'] == creditor.name and d['status'] == 'unresolved':
                d['status'] = 'in_receivership'

        # Debtor grievance & legitimacy hit
        debtor.legitimacy = max(0.05, getattr(debtor, 'legitimacy', 0.5) - 0.15)
        for tile in getattr(debtor, 'tiles', []):
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            for f in factions.values():
                f.add_grievance('foreign_oppression', 2.0)

        # Register diplomatic treaty of type CUSTOMS_RECEIVERSHIP
        from diplomacy import get_diplomacy, Treaty
        diplomacy = get_diplomacy()
        tr = Treaty(
            treaty_id=f"tr_{uuid.uuid4().hex[:6]}",
            treaty_type="customs_receivership",
            nation_a=creditor.name,
            nation_b=debtor.name,
            signed_turn=t,
            status="active"
        )
        diplomacy.treaties.append(tr)

        if world:
            from worldview_engine import ticker_push
            ticker_push(
                world, t, 'DIPLOMACY',
                f"⚓ IMPERIAL RECEIVERSHIP: {creditor.name} established Customs Receivership on {debtor.name} (intercepting 40% revenues for ${amount:.0f} debt)!",
                (240, 160, 60)
            )

        return True, f"Established Customs Receivership #{rec_id} on {debtor.name} for ${amount:.0f}.", receivership

    def negotiate_debt_restructuring(self, debtor: Nation, creditor: Nation,
                                      haircut_pct: float | None = None,
                                      use_brady_bonds: bool = True,
                                      grant_unequal_treaty: bool = False,
                                      world: dict | None = None,
                                      t: int = 0) -> Tuple[bool, str, Dict[str, Any]]:
        """Diplomatic debt workout: emergent haircut negotiated under the shadow of violence."""
        threat = evaluate_credible_takeover_threat(creditor, debtor, world)

        # Dynamic emergent haircut calculation based on S_cred if not explicitly specified
        if haircut_pct is None:
            # S_cred >= 2.0 -> 0.30 haircut; S_cred <= 0.8 -> 0.60 haircut
            calc_haircut = 0.80 - 0.25 * threat.credibility_score
            haircut_pct = max(0.20, min(0.80, round(calc_haircut, 2)))

        unresolved = self.get_unresolved_defaults_against(debtor.name, creditor.name)
        active_rec = self.get_active_receivership_on(debtor.name)

        total_delinquent = sum(d.get('principal', d.get('amount', 0.0)) for d in unresolved)
        if active_rec and active_rec.creditor_nation == creditor.name:
            total_delinquent = max(total_delinquent, active_rec.remaining_debt)

        if total_delinquent <= 0:
            total_delinquent = 500.0

        haircut_amount = round(total_delinquent * haircut_pct, 2)
        restructured_principal = round(total_delinquent - haircut_amount, 2)

        # 1. Clear delinquent defaults
        for d in self.delinquent_defaults:
            if d['debtor'] == debtor.name and d['creditor'] == creditor.name and d['status'] in ('unresolved', 'in_receivership'):
                d['status'] = 'settled_by_restructuring'

        # 2. Lift/clear active receivership
        if active_rec and active_rec.creditor_nation == creditor.name:
            active_rec.status = "cleared"

        # 3. Lift active blockades between creditor and debtor
        if world:
            for tile in getattr(debtor, 'tiles', []):
                if self.is_tile_blockaded(tile.name) and self.blockade_enforcers.get(tile.name) == creditor.name:
                    self.lift_blockade(tile.name, world, t)

        # 4. Issue replacement 50-turn Brady Bonds
        brady_bond = None
        if use_brady_bonds and restructured_principal > 0:
            from sovereign_bonds import SovereignBond, get_bond_market
            market = get_bond_market()
            b_id = f"brady_{uuid.uuid4().hex[:6]}"
            brady_bond = SovereignBond(
                bond_id=b_id,
                issuer_nation=debtor.name,
                holder_nation=creditor.name,
                principal=restructured_principal,
                coupon_rate=0.0015,  # 0.15% concessional per turn coupon
                duration_turns=50,
                issued_turn=t,
                maturity_turn=t + 50,
                status="active"
            )
            market.bonds.append(brady_bond)
            market.isrb.rating_modifiers[debtor.name] = 0
            market.isrb.modifier_expiry[debtor.name] = t

        # 5. Grant unequal treaty if part of accord
        treaty = None
        if grant_unequal_treaty:
            _, _, treaty = self.impose_unequal_treaty(creditor, debtor, "tariff_exemption", None, t, world)

        # Debtor legitimacy recovery
        debtor.legitimacy = min(1.0, getattr(debtor, 'legitimacy', 0.5) + 0.10)

        msg = (f"BRADY ACCORD: {debtor.name} and {creditor.name} ratified debt restructuring! "
               f"${haircut_amount:,.0f} ({haircut_pct*100:.0f}%) principal forgiven. "
               f"Replacement 50t Brady Bond (${restructured_principal:,.0f}) issued. Receivership lifted.")

        if world:
            from worldview_engine import ticker_push
            ticker_push(world, t, 'DIPLOMACY', f"🤝 {msg}", (120, 240, 150))

        return True, msg, {
            'haircut_pct': haircut_pct,
            'haircut_amount': haircut_amount,
            'restructured_principal': restructured_principal,
            'brady_bond': brady_bond,
            'treaty': treaty,
            'threat_assessment': threat
        }

    def get_active_receivership_on(self, debtor_nation: str) -> Optional[CustomsReceivership]:
        """Return the active receivership on a debtor nation, if any."""
        return next((r for r in self.receiverships if r.debtor_nation == debtor_nation and r.status == "active"), None)

    def intercept_revenue(self, debtor_nation: str, gross_amount: float,
                          t: int, world: dict | None = None) -> Tuple[float, float, Optional[str]]:
        """Intercept a fraction of debtor revenue (tariff or sales tax) and transfer to creditor treasury.

        100% money conserved:
          debtor gets: gross_amount - intercepted
          creditor gets: intercepted
        Returns: (net_amount_for_debtor, intercepted_amount, creditor_nation_name)
        """
        rec = self.get_active_receivership_on(debtor_nation)
        if not rec or gross_amount <= 0.0 or rec.remaining_debt <= 0.0:
            return gross_amount, 0.0, None

        desired_intercept = round(gross_amount * rec.intercept_share, 2)
        actual_intercept = min(desired_intercept, rec.remaining_debt, gross_amount)
        if actual_intercept <= 0:
            return gross_amount, 0.0, None

        # Conserved transfer to creditor nation treasury
        creditor_credited = False
        if world:
            nations_by_name = {n.name: n for n in world.get('nations', [])}
            creditor = nations_by_name.get(rec.creditor_nation)
            if creditor and hasattr(creditor, 'government') and creditor.government:
                creditor.government.agent.cash += actual_intercept
                creditor.government.record_income(t, 'tariff', actual_intercept)
                creditor_credited = True

        if not creditor_credited:
            cred_obj = getattr(rec, 'creditor_obj', None)
            if cred_obj and hasattr(cred_obj, 'government') and cred_obj.government:
                cred_obj.government.agent.cash += actual_intercept
                cred_obj.government.record_income(t, 'tariff', actual_intercept)
                creditor_credited = True
            else:
                import econsim_states
                for g in econsim_states.governments:
                    if g.name == rec.creditor_nation:
                        g.agent.cash += actual_intercept
                        g.record_income(t, 'tariff', actual_intercept)
                        break

        rec.total_collected += actual_intercept
        rec.remaining_debt -= actual_intercept

        if rec.remaining_debt <= 0.01:
            rec.status = "cleared"
            if world:
                from worldview_engine import ticker_push
                ticker_push(
                    world, t, 'FINANCE',
                    f"✅ RECEIVERSHIP CLEARED: {debtor_nation} completed sovereign debt repayments to {rec.creditor_nation}!",
                    (120, 220, 140)
                )

        net_debtor = gross_amount - actual_intercept
        return net_debtor, actual_intercept, rec.creditor_nation

    # ------------------------------------------------------------------
    # Debt Enforcement War & Naval Blockades
    # ------------------------------------------------------------------

    def declare_debt_enforcement_war(self, creditor: Nation, debtor: Nation,
                                     t: int, world: dict) -> Tuple[bool, str]:
        """Creditor declares a formal Debt-Enforcement War on debtor."""
        from diplomacy import get_diplomacy
        diplomacy = get_diplomacy()

        if diplomacy.are_at_war(creditor.name, debtor.name):
            return False, f"{creditor.name} and {debtor.name} are already at war."

        events = diplomacy.declare_war(
            creditor.name, debtor.name, t,
            reason=f"Debt-Enforcement War (gunboat collection of defaulted sovereign debt)"
        )

        from worldview_engine import ticker_push
        ticker_push(
            world, t, 'WAR',
            f"⚔️ GUNBOAT DIPLOMACY: {creditor.name} declared Debt-Enforcement War against {debtor.name}!",
            (240, 60, 60)
        )
        return True, f"Declared Debt-Enforcement War against {debtor.name}."

    def impose_naval_blockade(self, enforcer: Nation, debtor: Nation,
                              tile: Region, t: int, world: dict) -> Tuple[bool, str]:
        """Impose a gunboat naval blockade on a debtor port tile, freezing maritime trade."""
        if not any(getattr(u, 'soldiers', 0) > 0 for u in getattr(enforcer, 'military_units', [])):
            return False, "Cannot impose naval blockade without active military fleet or standing units."

        if not getattr(tile, 'is_coast', False) and not any(getattr(n, 'is_water', False) for n in tile.neighbors.values()):
            return False, f"Cannot impose naval blockade on inland tile {tile.name}."

        self.blockaded_tiles.add(tile.name)
        self.blockade_enforcers[tile.name] = enforcer.name

        # Freeze local trade routes
        for r_name, r in getattr(tile, 'routes', {}).items():
            setattr(r, 'is_blockaded', True)

        from worldview_engine import ticker_push
        ticker_push(
            world, t, 'WAR',
            f"⚓ NAVAL BLOCKADE: {enforcer.name} warships blockaded {debtor.name}'s port at {tile.name}! Trade frozen.",
            (220, 90, 90)
        )
        return True, f"Blockaded port {tile.name}."

    def lift_blockade(self, tile_name: str, world: dict | None = None, t: int = 0) -> bool:
        """Lift active naval blockade from tile."""
        if tile_name in self.blockaded_tiles:
            self.blockaded_tiles.remove(tile_name)
            self.blockade_enforcers.pop(tile_name, None)
            if world:
                tiles_by_name = {tile.name: tile for tile in world.get('tiles', [])}
                target = tiles_by_name.get(tile_name)
                if target:
                    for r in getattr(target, 'routes', {}).values():
                        setattr(r, 'is_blockaded', False)
                from worldview_engine import ticker_push
                ticker_push(
                    world, t, 'DIPLOMACY',
                    f"⚓ Naval blockade on {tile_name} lifted.",
                    (120, 220, 140)
                )
            return True
        return False

    def is_tile_blockaded(self, tile_name: str) -> bool:
        """Check if tile is under active naval blockade."""
        return tile_name in self.blockaded_tiles

    # ------------------------------------------------------------------
    # Unequal Treaties & Concessions
    # ------------------------------------------------------------------

    def impose_unequal_treaty(self, imperial: Nation, subject: Nation,
                              treaty_type: str, concession_tile: Optional[Region],
                              t: int, world: dict | None = None) -> Tuple[bool, str, UnequalTreaty]:
        """Subject nation concedes an unequal treaty (tariff exemption or resource concession) for debt restructuring."""
        treaty_id = f"uneq_{uuid.uuid4().hex[:6]}"
        tile_name = concession_tile.name if concession_tile else None

        treaty = UnequalTreaty(
            treaty_id=treaty_id,
            imperial_nation=imperial.name,
            subject_nation=subject.name,
            treaty_type=treaty_type,
            concession_tile=tile_name,
            profit_repatriation_share=0.50,
            signed_turn=t,
            status="active"
        )
        self.unequal_treaties.append(treaty)

        # Restructure open defaults: forgive up to $500 of delinquent debt in exchange for treaty
        for d in self.delinquent_defaults:
            if d['debtor'] == subject.name and d['creditor'] == imperial.name and d['status'] in ('unresolved', 'in_receivership'):
                d['status'] = 'settled_by_treaty'

        # Also relieve corresponding active receivership if present
        rec = self.get_active_receivership_on(subject.name)
        if rec and rec.creditor_nation == imperial.name:
            rec.status = "cleared"

        # Debtor grievance & loss of sovereignty
        subject.legitimacy = max(0.1, getattr(subject, 'legitimacy', 0.5) - 0.10)
        for tile in getattr(subject, 'tiles', []):
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            for f in factions.values():
                f.add_grievance('national_humiliation', 2.5)

        if treaty_type == "tariff_exemption":
            msg = f"UNEQUAL TREATY: {subject.name} granted 0% tariff extraterritorial privileges to {imperial.name} merchants!"
        else:
            msg = f"COLONIAL CONCESSION: {subject.name} surrendered resource extraction concession in {tile_name} to {imperial.name}!"

        if world:
            from worldview_engine import ticker_push
            ticker_push(world, t, 'DIPLOMACY', f"📜 {msg}", (240, 180, 50))

        return True, msg, treaty

    def has_tariff_exemption(self, trader_origin_nation: str, destination_nation: str) -> bool:
        """Check if trader from origin nation has 0% tariff privilege in destination nation."""
        for tr in self.unequal_treaties:
            if tr.status == "active" and tr.treaty_type == "tariff_exemption":
                if tr.imperial_nation == trader_origin_nation and tr.subject_nation == destination_nation:
                    return True
        return False

    # ------------------------------------------------------------------
    # Sovereign Debt Repudiation (Commune / Radical Action)
    # ------------------------------------------------------------------

    def repudiate_all_imperial_obligations(self, nation: Nation, t: int, world: dict) -> Dict[str, Any]:
        """Radical revolutionary decree: repudiate all foreign debt, expel receiverships, and revoke unequal treaties.

        Triggered by the Revolutionary Commune. Causes immediate imperial outrage and casus belli!
        """
        repudiated_debt_total = 0.0
        foreign_creditors = set()

        # 1. Repudiate all foreign bonds owed
        from sovereign_bonds import get_bond_market
        market = get_bond_market()
        for b in list(market.bonds):
            if b.issuer_nation == nation.name and b.holder_nation != "Domestic Commercial Banks" and b.holder_nation != nation.name:
                if b.status in ("active", "defaulted"):
                    b.status = "repudiated"
                    repudiated_debt_total += b.principal
                    foreign_creditors.add(b.holder_nation)

        # 2. Expel active receiverships
        expelled_receiverships = 0
        for r in self.receiverships:
            if r.debtor_nation == nation.name and r.status == "active":
                r.status = "expelled"
                expelled_receiverships += 1
                foreign_creditors.add(r.creditor_nation)

        # 3. Revoke all unequal treaties where nation was subject
        revoked_treaties = 0
        for tr in self.unequal_treaties:
            if tr.subject_nation == nation.name and tr.status == "active":
                tr.status = "repudiated"
                revoked_treaties += 1
                foreign_creditors.add(tr.imperial_nation)

        # 4. Lift any blockades if enforcers lose control
        for tile in nation.tiles:
            self.lift_blockade(tile.name, world, t)

        # 5. Massive diplomatic rupture with foreign creditors (-1.0 relations and casus belli)
        from diplomacy import get_diplomacy
        diplomacy = get_diplomacy()
        for creditor_name in foreign_creditors:
            diplomacy.set_relation(nation.name, creditor_name, -1.0)
            diplomacy.adjust_relation(creditor_name, nation.name, -1.0)
            diplomacy.declare_war(
                creditor_name, nation.name, t,
                reason="Revolutionary debt repudiation and expulsion of imperial assets"
            )

        from worldview_engine import ticker_push
        ticker_push(
            world, t, 'ALERT',
            f"🚩 DEBT REPUDIATION! {nation.name} repudiated ${repudiated_debt_total:.0f} of imperial debt and expelled all customs receivers!",
            (250, 40, 40)
        )

        res = {
            'repudiated_debt': repudiated_debt_total,
            'expelled_receiverships': expelled_receiverships,
            'revoked_treaties': revoked_treaties,
            'angered_creditors': list(foreign_creditors)
        }
        self.event_log.append({'turn': t, 'kind': 'DEBT_REPUDIATION', 'nation': nation.name, **res})
        return res

    # ------------------------------------------------------------------
    # Core-Periphery Structural Analysis
    # ------------------------------------------------------------------

    def compute_core_periphery_index(self, nation: Nation, world: dict) -> CorePeripheryScore:
        """Compute the structural Core-Periphery score for *nation*."""
        treasury = nation.treasury()
        total_wealth = max(100.0, treasury.get('total', 100.0))

        from sovereign_bonds import get_bond_market
        market = get_bond_market()

        foreign_debt_owed = sum(b.principal for b in market.bonds
                                if b.issuer_nation == nation.name
                                and b.holder_nation != "Domestic Commercial Banks"
                                and b.holder_nation != nation.name
                                and b.status in ("active", "defaulted"))

        foreign_reserves_held = sum(b.principal for b in market.bonds
                                    if b.holder_nation == nation.name
                                    and b.issuer_nation != nation.name
                                    and b.status == "active")

        debt_ratio = foreign_debt_owed / total_wealth
        net_balance = foreign_reserves_held - foreign_debt_owed

        prim_exports = 0.0
        mfg_exports = 0.0
        from goods import Goods
        for tile in getattr(nation, 'tiles', []):
            exp = getattr(tile, 'export_val', {})
            prim_exports += sum(exp.get(Goods.food, [0.0])[-3:]) + sum(exp.get(Goods.wood, [0.0])[-3:])
            mfg_exports += sum(exp.get(Goods.furniture, [0.0])[-3:])

        terms_ratio = (mfg_exports / max(1.0, prim_exports))

        balance_factor = max(-1.0, min(1.0, net_balance / 1500.0))
        wealth_factor = max(-1.0, min(1.0, (total_wealth - 1000.0) / 3000.0))
        trade_factor = max(-1.0, min(1.0, (terms_ratio - 1.0) / 2.0)) if (prim_exports > 0 or mfg_exports > 0) else 0.0
        debt_penalty = min(1.0, debt_ratio * 0.8)

        composite = (balance_factor * 0.4) + (wealth_factor * 0.3) + (trade_factor * 0.3) - (debt_penalty * 0.4)
        composite = max(-1.0, min(1.0, composite))

        if composite >= 0.25:
            tier = "Imperial Core"
        elif composite <= -0.20:
            tier = "Indebted Periphery"
        else:
            tier = "Semi-Periphery"

        score = CorePeripheryScore(
            nation_name=nation.name,
            external_debt_ratio=debt_ratio,
            net_creditor_balance=net_balance,
            terms_of_trade_ratio=terms_ratio,
            composite_index=round(composite, 2),
            tier=tier
        )
        self.core_periphery_scores[nation.name] = score
        return score

    # ------------------------------------------------------------------
    # Step Turn Lifecycle
    # ------------------------------------------------------------------

    def step_imperialism(self, world: dict, t: int):
        """Step turn for global imperialism: AI ultimatums, receivership grievance drift, and scores."""
        nations = world.get('nations', [])
        if not nations:
            return

        # 1. Update Core-Periphery scores & Banking Contagion
        for n in nations:
            self.compute_core_periphery_index(n, world)
            try:
                from banking_policy import evaluate_banking_contagion
                evaluate_banking_contagion(n, world, t)
            except Exception:
                pass

        # 2. Receivership enforcement maintenance & grievance accrual
        for rec in self.receiverships:
            if rec.status != "active":
                continue
            rec.turns_active += 1
            debtor = next((n for n in nations if n.name == rec.debtor_nation), None)
            creditor = next((n for n in nations if n.name == rec.creditor_nation), None)

            # Caisse de la Dette asset seizures (transit tolls, granaries, royalties)
            if rec.level == "caisse_de_la_dette" and debtor and creditor and rec.remaining_debt > 0.01:
                cred_gov = getattr(creditor, 'government', None)
                debt_gov = getattr(debtor, 'government', None)

                # A. Tile Transit Toll Seizures (turnpikes & canals)
                for tile in getattr(debtor, 'tiles', []):
                    routes = getattr(tile, 'routes', {})
                    has_toll_infra = any(getattr(r, 'has_turnpike', False) or getattr(r, 'has_canal', False) for r in routes.values())
                    if has_toll_infra or getattr(tile, 'is_coast', False):
                        toll_intercept = min(10.0, rec.remaining_debt)
                        if debt_gov and getattr(debt_gov, 'agent', None) and debt_gov.agent.cash >= toll_intercept:
                            debt_gov.agent.cash -= toll_intercept
                        else:
                            toll_intercept = min(5.0, rec.remaining_debt)

                        if cred_gov and hasattr(cred_gov, 'agent'):
                            cred_gov.agent.cash += toll_intercept
                            cred_gov.record_income(t, 'tariff', toll_intercept)
                        rec.remaining_debt -= toll_intercept
                        rec.total_collected += toll_intercept
                        rec.seized_tolls += toll_intercept
                        if rec.remaining_debt <= 0.01:
                            rec.status = "cleared"
                            break

                # B. Granary Buffer Food Seizure
                if rec.status == "active" and rec.remaining_debt > 0.01:
                    for tile in getattr(debtor, 'tiles', []):
                        g_stock = getattr(tile, 'granary_stock', 0.0)
                        if g_stock >= 2.0:
                            seized_grain = min(4.0, g_stock * 0.5, rec.remaining_debt / 2.0)
                            tile.granary_stock -= seized_grain
                            grain_val = seized_grain * 2.0
                            if cred_gov and hasattr(cred_gov, 'agent'):
                                cred_gov.agent.cash += grain_val
                                cred_gov.record_income(t, 'tariff', grain_val)
                            rec.remaining_debt -= grain_val
                            rec.total_collected += grain_val
                            rec.seized_granary_grain += seized_grain
                            if rec.remaining_debt <= 0.01:
                                rec.status = "cleared"
                                break

                # C. Urabi Anti-Imperial Resistance Backlash
                try:
                    from popular_resistance import get_popular_resistance_manager
                    res_mgr = get_popular_resistance_manager()
                    for tile in getattr(debtor, 'tiles', []):
                        res_mgr.inject_anti_imperial_unrest(tile, amount=2.5, t=t)
                except Exception:
                    pass

            if creditor:
                cred_gov = getattr(creditor, 'government', None)
                has_military = any(getattr(u, 'soldiers', 0) > 0 for u in getattr(creditor, 'military_units', []))

                if rec.enforcement_mode == "military":
                    if not has_military:
                        # Creditor lost military forces: auto-hire agents if cash available, else suspend
                        if cred_gov and hasattr(cred_gov, 'agent') and cred_gov.agent.cash >= 50.0:
                            cred_gov.agent.cash -= 50.0
                            _disburse_agent_funds(world, creditor, 50.0)
                            rec.enforcement_mode = "hired_agents"
                            if world:
                                from worldview_engine import ticker_push
                                ticker_push(
                                    world, t, 'DIPLOMACY',
                                    f"📋 {creditor.name} contracted international agents ($50) to maintain receivership on {rec.debtor_nation}.",
                                    (245, 180, 50)
                                )
                        else:
                            rec.status = "suspended"
                            if world:
                                from worldview_engine import ticker_push
                                ticker_push(
                                    world, t, 'ALERT',
                                    f"⚠️ Customs Receivership on {rec.debtor_nation} suspended: {creditor.name} lacks military force and cannot afford hired agents!",
                                    (240, 80, 80)
                                )
                elif rec.enforcement_mode == "hired_agents":
                    retainer = rec.agent_retainer_cost
                    if cred_gov and hasattr(cred_gov, 'agent') and cred_gov.agent.cash >= retainer:
                        cred_gov.agent.cash -= retainer
                        _disburse_agent_funds(world, creditor, retainer)
                    else:
                        rec.status = "suspended"
                        if world:
                            from worldview_engine import ticker_push
                            ticker_push(
                                world, t, 'ALERT',
                                f"⚠️ Customs Receivership on {rec.debtor_nation} suspended: {creditor.name} failed to pay agent retainer fee (${retainer:.2f})!",
                                (240, 80, 80)
                            )

            if rec.status == "active" and debtor:
                debtor.legitimacy = max(0.05, getattr(debtor, 'legitimacy', 0.5) - 0.005)
                for tile in getattr(debtor, 'tiles', []):
                    factions = getattr(getattr(tile, 'factions', None), 'factions', {})
                    for f in factions.values():
                        f.add_grievance('foreign_oppression', 0.3)

        # 3. Check active naval blockades: sustainment requires military units
        for tile_name in list(self.blockaded_tiles):
            enforcer_name = self.blockade_enforcers.get(tile_name)
            enforcer = next((n for n in nations if n.name == enforcer_name), None)
            has_mil = enforcer and any(getattr(u, 'soldiers', 0) > 0 for u in getattr(enforcer, 'military_units', []))
            if not has_mil:
                self.lift_blockade(tile_name, world, t)
                if world:
                    from worldview_engine import ticker_push
                    ticker_push(
                        world, t, 'ALERT',
                        f"⚓ Naval blockade on {tile_name} collapsed: {enforcer_name or 'Enforcer'} has no active military units to sustain blockade!",
                        (240, 80, 80)
                    )

        # 4. AI Creditor Decisions on Unresolved Defaults (gated by Coercion Calculus)
        player_nation_name = world.get('player_nation_name', '')
        for default in list(self.delinquent_defaults):
            if default['status'] != 'unresolved':
                continue

            creditor_name = default['creditor']
            debtor_name = default['debtor']
            if creditor_name == "Domestic Commercial Banks" or creditor_name == player_nation_name:
                continue

            creditor = next((n for n in nations if n.name == creditor_name), None)
            debtor = next((n for n in nations if n.name == debtor_name), None)
            if not creditor or not debtor:
                continue

            threat = evaluate_credible_takeover_threat(creditor, debtor, world)

            if not self.get_active_receivership_on(debtor.name):
                if threat.credibility_score >= 0.8:
                    self.establish_receivership(creditor, debtor, default['principal'], t, world)
                    default['status'] = 'in_receivership'
                elif threat.credibility_score < 0.7 and debtor_name != player_nation_name:
                    # Debtor calls bluff and repudiates
                    default['status'] = 'repudiated_bluff'
                    if world:
                        from worldview_engine import ticker_push
                        ticker_push(
                            world, t, 'DIPLOMACY',
                            f"📜 {debtor.name} refused debt payment to {creditor.name}! Creditor's threat dismissed as hollow bluff.",
                            (240, 180, 50)
                        )
            else:
                active_r = self.get_active_receivership_on(debtor.name)
                if active_r and active_r.level == "customs" and threat.credibility_score >= 1.5:
                    # Creditor escalates to Caisse de la Dette
                    self.escalate_to_caisse(active_r.receivership_id, world, t)
                elif not (self.is_tile_blockaded(debtor.tiles[0].name) if debtor.tiles else False):
                    if default['principal'] >= 800.0 and threat.credibility_score >= 1.2:
                        self.declare_debt_enforcement_war(creditor, debtor, t, world)
                        if debtor.tiles:
                            coast_tile = next((t_obj for t_obj in debtor.tiles if getattr(t_obj, 'is_coast', False)), debtor.tiles[0])
                            self.impose_naval_blockade(creditor, debtor, coast_tile, t, world)
                        default['status'] = 'gunboat_enforced'


_GLOBAL_IMPERIALISM_MANAGER: ImperialismManager | None = None


def get_imperialism_manager() -> ImperialismManager:
    """Return singleton ImperialismManager instance."""
    global _GLOBAL_IMPERIALISM_MANAGER
    if _GLOBAL_IMPERIALISM_MANAGER is None:
        _GLOBAL_IMPERIALISM_MANAGER = ImperialismManager()
    return _GLOBAL_IMPERIALISM_MANAGER
