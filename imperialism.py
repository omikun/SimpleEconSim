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
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from nation import Nation
    from region import Region


@dataclass
class CustomsReceivership:
    """An imperial customs receivership intercepting debtor state revenues."""
    receivership_id: str
    creditor_nation: str
    debtor_nation: str
    intercept_share: float = 0.40       # 40% of tariffs and taxes diverted
    remaining_debt: float = 500.0       # Outstanding debt balance to collect
    total_collected: float = 0.0        # Cumulative diverted funds
    start_turn: int = 0
    status: str = "active"              # 'active' | 'cleared' | 'expelled' | 'suspended'
    enforcement_mode: str = "military"  # 'military' | 'hired_agents'
    agent_retainer_cost: float = 2.0     # per turn cost to maintain hired agents
    agents_hired: int = 1


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
    # Customs Receivership
    # ------------------------------------------------------------------

    def establish_receivership(self, creditor: Nation, debtor: Nation,
                               amount: float, t: int, world: dict | None = None,
                               hire_agents: bool = False) -> Tuple[bool, str, Optional[CustomsReceivership]]:
        """Creditor establishes a customs receivership on debtor to divert revenues until debt cleared."""
        if creditor.name == debtor.name:
            return False, "Cannot establish receivership on own nation.", None

        # Check if active receivership already exists
        existing = next((r for r in self.receiverships
                         if r.debtor_nation == debtor.name and r.creditor_nation == creditor.name and r.status == "active"), None)
        if existing:
            existing.remaining_debt += amount
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

        rec_id = f"rec_{uuid.uuid4().hex[:6]}"
        receivership = CustomsReceivership(
            receivership_id=rec_id,
            creditor_nation=creditor.name,
            debtor_nation=debtor.name,
            intercept_share=0.40,
            remaining_debt=float(amount),
            start_turn=t,
            status="active",
            enforcement_mode=enforce_mode
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

        # 1. Update Core-Periphery scores
        for n in nations:
            self.compute_core_periphery_index(n, world)

        # 2. Receivership enforcement maintenance & grievance accrual
        for rec in self.receiverships:
            if rec.status != "active":
                continue
            debtor = next((n for n in nations if n.name == rec.debtor_nation), None)
            creditor = next((n for n in nations if n.name == rec.creditor_nation), None)

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

        # 4. AI Creditor Decisions on Unresolved Defaults
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

            c_score = self.core_periphery_scores.get(creditor.name)
            if c_score and c_score.composite_index >= 0.15:
                if not self.get_active_receivership_on(debtor.name):
                    self.establish_receivership(creditor, debtor, default['principal'], t, world)
                    default['status'] = 'in_receivership'
                elif not self.is_tile_blockaded(debtor.tiles[0].name) if debtor.tiles else False:
                    if default['principal'] >= 800.0:
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
