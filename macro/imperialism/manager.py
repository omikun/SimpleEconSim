"""
macro/imperialism/manager.py — Global manager for financial imperialism.
"""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
import math
import uuid
from typing import Optional, List, Dict, Tuple, Any, Set, TYPE_CHECKING

from macro.imperialism.models import (
    ThreatAssessment,
    CustomsReceivership,
    UnequalTreaty,
    CorePeripheryScore,
)

if TYPE_CHECKING:
    from nation import Nation
    from region import Region


def _imperial_trace_region(world: dict | None, *nations):
    """Choose an existing tile trace for an imperialism operation."""
    candidates = []
    seen = set()
    for nation in nations:
        for tile in getattr(nation, 'tiles', ()) or ():
            if id(tile) not in seen:
                seen.add(id(tile))
                candidates.append(tile)
    for tile in (world or {}).get('tiles', ()) or ():
        if id(tile) not in seen:
            seen.add(id(tile))
            candidates.append(tile)
    return next((tile for tile in candidates
                 if getattr(tile, '_run_trace', None) is not None
                 and getattr(tile, '_collective_trace_clock', None) is not None),
                candidates[0] if candidates else None)


def _trace_enforcement_funding_gate(region, *, operation_id, receivership_id,
                                    creditor, debtor_name, turn, fee_required,
                                    amount_required, cash_before, funded, reason,
                                    enforcement_mode):
    if region is None:
        return None
    from run_trace import emit

    return emit(
        region, kind='imperial_enforcement_funding_gate',
        record_class='outcome', phase='imperialism',
        subject={'type': 'nation/receivership', 'id': receivership_id,
                 'nation': creditor.name},
        metric_id='finance.enforcement_agent_funding', unit='funded',
        before=None, after=bool(funded), operation_id=operation_id,
        inputs={'operation_id': operation_id,
                'receivership_id': receivership_id,
                'creditor_nation': creditor.name,
                'debtor_nation': debtor_name, 'turn': int(turn),
                'enforcement_mode': enforcement_mode,
                'fee_required': bool(fee_required),
                'amount_required': float(amount_required),
                'creditor_treasury_cash_before': float(cash_before),
                'cash_shortfall': max(0.0, float(amount_required)
                                      - float(cash_before)),
                'funded': bool(funded), 'reason': reason})


def _trace_enforcement_agent_payment(region, *, operation_id, receivership_id,
                                     creditor, turn, amount, reason,
                                     cash_before, cash_after, disbursement,
                                     cause_event_id=None, world=None):
    """Trace the creditor debit and the actual hired-agent wallet, if any."""
    if region is None:
        return None
    from finance_trace import account_ref, cash_transfer_contract, emit_cash_transfer
    from run_trace import emit

    government = getattr(creditor, 'government', None)
    currency = (getattr(creditor, 'currency', None)
                or getattr(government, 'currency', None)
                or getattr(region, 'home_currency', None) or 'local_currency')
    payer = account_ref(
        'government_treasury', creditor.name, currency,
        nation_id=creditor.name, subaccount='government_agent.cash',
        balance_before=float(cash_before), balance_after=float(cash_after),
        balance_scope='government_agent.cash', balance_status='exact_cash_debit')
    causes = [cause_event_id] if cause_event_id else None
    recipient = (disbursement or {}).get('recipient')
    if recipient is not None:
        payee_currency = (getattr(recipient, 'home_currency', None)
                          or getattr(recipient, 'currency', None) or currency)
        recipient_region = next((tile for tile in
                                 [*(getattr(creditor, 'tiles', ()) or ()),
                                  *((world or {}).get('tiles', ()) or ())]
                                 if recipient in getattr(tile, 'agents', ())), None)
        payee = account_ref(
            ('corporate_wallet' if getattr(recipient, 'is_corporation', False)
             else 'agent_wallet'), str(recipient.id), payee_currency,
            person_id=recipient.id,
            balance_before=float(disbursement['cash_before']),
            balance_after=float(disbursement['cash_after']),
            balance_scope='cash_wallet', balance_status='exact_cash_credit',
            tile=getattr(recipient, 'region', None))
        contract = cash_transfer_contract(
            operation_id, 'imperial_enforcement_agent_payment',
            amount=amount, currency=currency, payer_account=payer,
            payee_account=payee,
            counterparty_leg_status='creditor and hired-agent cash balances captured',
            receivership_id=receivership_id,
            payee_currency=payee_currency,
            currency_conversion_applied=False)
        return emit_cash_transfer(
            region, kind='imperial_enforcement_agent_payment', contract=contract,
            phase='imperialism',
            subject={'type': 'nation/receivership', 'id': receivership_id,
                     'nation': creditor.name},
            cause_event_ids=causes,
            inputs={'turn': int(turn), 'reason': reason,
                    'recipient_id': recipient.id,
                    'recipient_region': (recipient_region.name
                                         if recipient_region else
                                         getattr(recipient, 'region', None)),
                    'payer_cash_before': float(cash_before),
                    'payer_cash_after': float(cash_after),
                    'payee_cash_before': float(disbursement['cash_before']),
                    'payee_cash_after': float(disbursement['cash_after']),
                    'currency_conversion_applied': False})

    payee = account_ref(
        'uncredited_agent_fee', operation_id, currency,
        balance_scope='missing_agent_payee',
        balance_status='no_eligible_agent_wallet_found')
    contract = cash_transfer_contract(
        operation_id, 'imperial_enforcement_agent_payment',
        amount=amount, currency=currency, payer_account=payer,
        payee_account=payee,
        counterparty_leg_status='treasury debited; no eligible agent received cash',
        receivership_id=receivership_id)
    return emit(
        region, kind='imperial_enforcement_agent_payment_uncredited',
        record_class='outcome', phase='imperialism',
        subject={'type': 'nation/receivership', 'id': receivership_id,
                 'nation': creditor.name},
        metric_id='finance.policy_expenditure', unit=currency,
        before=float(cash_before), after=float(cash_after),
        operation_id=operation_id, cause_event_ids=causes,
        inputs={'turn': int(turn), 'reason': reason,
                'amount_paid': float(amount), 'recipient_found': False,
                'payer_cash_before': float(cash_before),
                'payer_cash_after': float(cash_after),
                'transfer_contract': contract})

def _disburse_agent_funds(world: dict | None, creditor: Any | None, amount: float):
    """Conserve currency by paying hired agents/bailiffs from creditor funds into living non-gov agents."""
    if amount <= 0:
        return None
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
        cash_before = float(getattr(recipient, 'cash', 0.0))
        _trace_cash_write = _trace_public_begin(None, recipient)
        recipient.cash += amount
        _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:_disburse_agent_funds',
                             inputs={"source_writer": 'macro/imperialism/manager.py:_disburse_agent_funds:84e6162c6b33ec4c:1'})
        # Callers that only need the legacy side effect may ignore this return.
        # Instrumented callers can identify the actual wallet that was credited.
        return {
            'recipient': recipient,
            'cash_before': cash_before,
            'cash_after': float(recipient.cash),
        }
    return None


def _trace_caisse_cash_seizure(tile, *, debtor, creditor, operation_id, kind,
                               amount, turn, source_cash_debited,
                               creditor_cash_credited, debtor_cash_before=None,
                               debtor_cash_after=None, creditor_cash_before=None,
                               creditor_cash_after=None, source_account_type=None,
                               source_status=None, cause_event_ids=None,
                               details=None):
    """Trace only the cash legs that actually mutate; expose missing legs."""
    from finance_trace import account_ref, emit_treasury_leg, transfer_contract

    debtor_currency = getattr(debtor, 'currency', None) or 'local_currency'
    creditor_currency = getattr(creditor, 'currency', None) or debtor_currency
    source_account = account_ref(
        'government_treasury' if source_cash_debited else
        (source_account_type or 'receivership_unfunded_source'),
        getattr(getattr(debtor, 'government', None), 'name', debtor.name),
        debtor_currency,
        nation_id=debtor.name,
        subaccount='government_agent.cash' if source_cash_debited else None,
        balance_before=(float(debtor_cash_before)
                        if source_cash_debited else None),
        balance_after=(float(debtor_cash_after)
                       if source_cash_debited else None),
        balance_scope=('government_agent.cash' if source_cash_debited else
                       'collection_source'),
        balance_status=('exact_cash_debit' if source_cash_debited else
                        source_status or 'no_source_cash_debit_recorded'))
    payee_government = getattr(creditor, 'government', None) if creditor else None
    payee_account = account_ref(
        'government_treasury' if creditor_cash_credited else
        'uncredited_receivership_claim',
        getattr(payee_government, 'name', getattr(creditor, 'name', 'missing_creditor')),
        creditor_currency, nation_id=getattr(creditor, 'name', None),
        subaccount=('government_agent.cash' if creditor_cash_credited else None),
        balance_before=(float(creditor_cash_before)
                        if creditor_cash_credited else None),
        balance_after=(float(creditor_cash_after)
                       if creditor_cash_credited else None),
        balance_scope=('government_agent.cash' if creditor_cash_credited else
                       'receivable'),
        balance_status=('exact_cash_credit' if creditor_cash_credited else
                        'creditor_cash_credit_not_recorded'))
    common = {
        'amount': float(amount), 'amount_currency': debtor_currency,
        'payer_account': source_account, 'payee_account': payee_account,
        'counterparty_leg_status': (
            'cash legs recorded where present; missing source or payee leg disclosed'),
        'counterparty_currency': creditor_currency,
        'counterparty_currency_mismatch': debtor_currency != creditor_currency,
        'currency_conversion_applied': False,
        'mutation_reference': {'turn': int(turn), 'operation_id': operation_id},
    }
    events = []
    if source_cash_debited:
        payer_contract = transfer_contract(
            operation_id, kind, side='payer', local_cash_leg_amount=amount,
            local_cash_leg_currency=debtor_currency, **common)
        event_id = emit_treasury_leg(
            tile, kind=f'{kind}_debtor_payment', nation_name=debtor.name,
            currency=debtor_currency, signed_amount=-float(amount),
            contract=payer_contract, phase='imperialism', subject_type='nation',
            inputs={'turn': int(turn), 'operation_id': operation_id,
                    'creditor_cash_credited': bool(creditor_cash_credited),
                    **(details or {})})
        if event_id is not None:
            events.append(event_id)
    if creditor_cash_credited:
        payee_contract = transfer_contract(
            operation_id, kind, side='payee', local_cash_leg_amount=amount,
            local_cash_leg_currency=creditor_currency, **common)
        event_id = emit_treasury_leg(
            tile, kind=f'{kind}_creditor_receipt', nation_name=creditor.name,
            currency=creditor_currency, signed_amount=float(amount),
            contract=payee_contract, phase='imperialism', subject_type='nation',
            cause_event_ids=cause_event_ids,
            inputs={'turn': int(turn), 'operation_id': operation_id,
                    'source_cash_debited': bool(source_cash_debited),
                    **(details or {})})
        if event_id is not None:
            events.append(event_id)
    return events


def _trace_receivership_balance(tile, *, debtor, creditor, rec, operation_id,
                                kind, before, after, turn, amount,
                                cause_event_ids=None, details=None):
    from run_trace import emit

    currency = getattr(debtor, 'currency', None) or 'local_currency'
    return emit(
        tile, kind=f'{kind}_debt_balance', record_class='outcome',
        phase='imperialism',
        subject={'type': 'nation/receivership', 'id': rec.receivership_id,
                 'nation': debtor.name},
        metric_id='finance.receivership_balance', unit=currency,
        before=float(before), after=float(after),
        formula_id='imperialism.caisse_asset_seizure_debt.v1',
        inputs={'operation_id': operation_id, 'turn': int(turn),
                'receivership_id': rec.receivership_id,
                'debtor_nation': debtor.name,
                'creditor_nation': creditor.name,
                'seizure_kind': kind, 'seizure_value': float(amount),
                'total_collected_after': float(rec.total_collected),
                'remaining_debt_after': float(rec.remaining_debt),
                **(details or {})},
        cause_event_ids=cause_event_ids)


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
            'bond_purpose': getattr(bond, 'bond_purpose', 'sovereign'),
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
            from client.desktop.engine import ticker_push
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

        rec_id = f"rec_{uuid.uuid4().hex[:6]}"
        operation_id = f'imperial-enforcement:{rec_id}:establishment'
        trace_region = _imperial_trace_region(world, creditor, debtor)
        fee_gate_event_id = None
        fee_payment_event_id = None

        # Enforcement validation: standing military forces or hired international agents
        has_military = any(getattr(u, 'soldiers', 0) > 0 for u in getattr(creditor, 'military_units', []))
        cred_gov = getattr(creditor, 'government', None)
        cred_cash = cred_gov.agent.cash if (cred_gov and hasattr(cred_gov, 'agent')) else 0.0

        if has_military and not hire_agents:
            enforce_mode = "military"
            fee_gate_event_id = _trace_enforcement_funding_gate(
                trace_region, operation_id=operation_id,
                receivership_id=rec_id, creditor=creditor,
                debtor_name=debtor.name, turn=t, fee_required=False,
                amount_required=0.0, cash_before=cred_cash, funded=True,
                reason='standing_military_force_no_agent_fee',
                enforcement_mode=enforce_mode)
        elif cred_cash >= 50.0:
            enforce_mode = "hired_agents"
            if cred_gov and hasattr(cred_gov, 'agent'):
                cash_before = float(cred_gov.agent.cash)
                fee_gate_event_id = _trace_enforcement_funding_gate(
                    trace_region, operation_id=operation_id,
                    receivership_id=rec_id, creditor=creditor,
                    debtor_name=debtor.name, turn=t, fee_required=True,
                    amount_required=50.0, cash_before=cash_before,
                    funded=True, reason='agent_contract_affordable',
                    enforcement_mode=enforce_mode)
                _trace_cash_write = _trace_public_begin(None, cred_gov.agent)
                cred_gov.agent.cash -= 50.0
                _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.establish_receivership',
                                     inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.establish_receivership:376807402f806688:1'})
                disbursement = _disburse_agent_funds(world, creditor, 50.0)
                fee_payment_event_id = _trace_enforcement_agent_payment(
                    trace_region, operation_id=operation_id,
                    receivership_id=rec_id, creditor=creditor, turn=t,
                    amount=50.0, reason='receivership_agent_contract',
                    cash_before=cash_before,
                    cash_after=float(cred_gov.agent.cash),
                    disbursement=disbursement,
                    cause_event_id=fee_gate_event_id, world=world)
        else:
            fee_gate_event_id = _trace_enforcement_funding_gate(
                trace_region, operation_id=operation_id,
                receivership_id=rec_id, creditor=creditor,
                debtor_name=debtor.name, turn=t, fee_required=True,
                amount_required=50.0, cash_before=cred_cash, funded=False,
                reason='insufficient_creditor_treasury_cash',
                enforcement_mode='hired_agents')
            return False, "Creditor lacks military forces and cannot afford $50 fee to hire enforcement agents.", None

        # Coercion gating: must have credible threat unless forced or consented
        if not force_override:
            can_enf, enf_msg, threat = self.can_enforce_receivership(creditor, debtor, world)
            if not can_enf and enforce_mode == "military":
                if trace_region is not None:
                    from run_trace import emit
                    emit(trace_region, kind='imperial_receivership_establishment_result',
                         record_class='outcome', phase='imperialism',
                         subject={'type': 'nation/receivership', 'id': rec_id,
                                  'nation': creditor.name},
                         metric_id='imperialism.receivership_state',
                         unit='status', before='absent', after='rejected',
                         operation_id=operation_id,
                         cause_event_ids=([fee_gate_event_id]
                                          if fee_gate_event_id else None),
                         inputs={'receivership_id': rec_id,
                                 'creditor_nation': creditor.name,
                                 'debtor_nation': debtor.name,
                                 'turn': int(t), 'reason': enf_msg,
                                 'enforcement_mode': enforce_mode,
                                 'enforcement_fee_paid': False,
                                 'credibility_score': threat.credibility_score,
                                 'threat_tier': threat.tier})
                return False, enf_msg, None

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
        legitimacy_before = float(getattr(debtor, 'legitimacy', 0.5))
        debtor.legitimacy = max(0.05, getattr(debtor, 'legitimacy', 0.5) - 0.15)
        legitimacy_after = float(debtor.legitimacy)
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
            from client.desktop.engine import ticker_push
            ticker_push(
                world, t, 'DIPLOMACY',
                f"⚓ IMPERIAL RECEIVERSHIP: {creditor.name} established Customs Receivership on {debtor.name} (intercepting 40% revenues for ${amount:.0f} debt)!",
                (240, 160, 60)
            )

        if trace_region is not None:
            from run_trace import emit
            causes = [event_id for event_id in
                      (fee_gate_event_id, fee_payment_event_id) if event_id]
            emit(trace_region, kind='imperial_receivership_establishment_result',
                 record_class='outcome', phase='imperialism',
                 subject={'type': 'nation/receivership', 'id': rec_id,
                          'nation': creditor.name},
                 metric_id='imperialism.receivership_state', unit='status',
                 before='absent', after=receivership.status,
                 operation_id=operation_id, cause_event_ids=causes or None,
                 inputs={'receivership_id': rec_id,
                         'creditor_nation': creditor.name,
                         'debtor_nation': debtor.name,
                         'turn': int(t), 'enforcement_mode': enforce_mode,
                         'remaining_debt': float(receivership.remaining_debt),
                         'intercept_share': float(receivership.intercept_share),
                         'enforcement_fee_required': enforce_mode == 'hired_agents',
                         'enforcement_fee_paid': fee_payment_event_id is not None,
                         'fee_gate_event_id': fee_gate_event_id,
                         'fee_payment_event_id': fee_payment_event_id,
                         'debtor_legitimacy_before': legitimacy_before,
                         'debtor_legitimacy_after': legitimacy_after})

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
            from client.desktop.engine import ticker_push
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
                          t: int, world: dict | None = None, *, trace_region=None,
                          trace_event_ids=None, source='tariff') -> Tuple[float, float, Optional[str]]:
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
        credited_government = None
        creditor_cash_before = None
        creditor_cash_after = None
        operation_id = (f'imperial-receivership:{rec.debtor_nation}:'
                        f'{rec.creditor_nation}:{source}:{int(t)}:'
                        f'{float(rec.total_collected):.6f}')
        if world:
            nations_by_name = {n.name: n for n in world.get('nations', [])}
            creditor = nations_by_name.get(rec.creditor_nation)
            if creditor and hasattr(creditor, 'government') and creditor.government:
                credited_government = creditor.government
                creditor_cash_before = float(credited_government.agent.cash)
                _trace_cash_write = _trace_public_begin(None, credited_government.agent)
                credited_government.agent.cash += actual_intercept
                _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.intercept_revenue',
                                     inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.intercept_revenue:180c1038821681d9:1'})
                creditor_cash_after = float(credited_government.agent.cash)
                creditor_credited = True

        if not creditor_credited:
            cred_obj = getattr(rec, 'creditor_obj', None)
            if cred_obj and hasattr(cred_obj, 'government') and cred_obj.government:
                credited_government = cred_obj.government
                creditor_cash_before = float(credited_government.agent.cash)
                _trace_cash_write = _trace_public_begin(None, credited_government.agent)
                credited_government.agent.cash += actual_intercept
                _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.intercept_revenue',
                                     inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.intercept_revenue:14e9da18f69d7bc4:1'})
                creditor_cash_after = float(credited_government.agent.cash)
                creditor_credited = True
            else:
                import econsim_states
                for g in econsim_states.governments:
                    if g.name == rec.creditor_nation:
                        credited_government = g
                        creditor_cash_before = float(g.agent.cash)
                        _trace_cash_write = _trace_public_begin(None, g.agent)
                        g.agent.cash += actual_intercept
                        _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.intercept_revenue',
                                             inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.intercept_revenue:c396245d460e433a:1'})
                        creditor_cash_after = float(g.agent.cash)
                        creditor_credited = True
                        break

        if trace_region is None:
            candidates = list((world or {}).get('tiles', []))
            if world is not None:
                candidates.extend(tile for nation in world.get('nations', [])
                                  if nation.name == rec.debtor_nation
                                  for tile in getattr(nation, 'tiles', []))
            trace_region = next((tile for tile in candidates
                                 if getattr(tile, '_run_trace', None) is not None), None)
        transfer_event_id = None
        if trace_region is not None and credited_government is not None:
            from finance_trace import account_ref, emit_treasury_leg, transfer_contract
            from run_trace import emit
            debtor_currency = (
                getattr(getattr(trace_region, 'owner_nation', None), 'currency', None)
                or getattr(trace_region, 'home_currency', None) or 'local_currency')
            creditor_currency = (getattr(credited_government, 'currency', None)
                                 or debtor_currency)
            payee_account = account_ref(
                'government_treasury', credited_government.name, creditor_currency,
                nation_id=rec.creditor_nation, subaccount='government_agent.cash',
                balance_before=creditor_cash_before,
                balance_after=creditor_cash_after,
                balance_scope='government_agent.cash')
            revenue_source = account_ref(
                'public_revenue_source', operation_id, debtor_currency,
                balance_scope='gross_revenue_receipt',
                balance_status='aggregate_source_not_identified')
            contract = transfer_contract(
                operation_id, 'customs_receivership_revenue_interception',
                side='payee', amount=actual_intercept,
                amount_currency=debtor_currency,
                payer_account=revenue_source, payee_account=payee_account,
                local_cash_leg_amount=actual_intercept,
                local_cash_leg_currency=creditor_currency,
                currency_conversion_applied=False,
                counterparty_leg_status=(
                    'gross tariff source aggregated by caller; creditor cash balance exact'),
                counterparty_currency=creditor_currency,
                counterparty_currency_mismatch=debtor_currency != creditor_currency,
                mutation_reference={'turn': int(t), 'source': source,
                                    'receivership_id': rec.receivership_id})
            transfer_event_id = emit_treasury_leg(
                trace_region, kind='customs_receivership_revenue_interception',
                nation_name=rec.creditor_nation, currency=creditor_currency,
                signed_amount=float(actual_intercept), contract=contract,
                phase='imperialism', subject_type='nation',
                inputs={'operation_id': operation_id, 'turn': int(t),
                        'debtor_nation': rec.debtor_nation,
                        'creditor_nation': rec.creditor_nation,
                        'gross_revenue': float(gross_amount),
                        'intercept_share': float(rec.intercept_share),
                        'desired_intercept': float(desired_intercept),
                        'actual_intercept': float(actual_intercept),
                        'net_revenue_for_debtor': float(gross_amount - actual_intercept),
                        'revenue_source': source,
                        'remaining_debt_before': float(rec.remaining_debt),
                        'creditor_cash_credited': True})

        if creditor_credited:
            credited_government.record_income(t, source, actual_intercept)

        remaining_debt_before = float(rec.remaining_debt)
        total_collected_before = float(rec.total_collected)
        rec.total_collected += actual_intercept
        rec.remaining_debt -= actual_intercept

        if rec.remaining_debt <= 0.01:
            rec.status = "cleared"
            if world:
                from client.desktop.engine import ticker_push
                ticker_push(
                    world, t, 'FINANCE',
                    f"✅ RECEIVERSHIP CLEARED: {debtor_nation} completed sovereign debt repayments to {rec.creditor_nation}!",
                    (120, 220, 140)
                )

        balance_event_id = None
        if trace_region is not None:
            from run_trace import emit
            debtor_currency = (
                getattr(getattr(trace_region, 'owner_nation', None), 'currency', None)
                or getattr(trace_region, 'home_currency', None) or 'local_currency')
            balance_event_id = emit(
                trace_region, kind='customs_receivership_debt_balance',
                record_class='outcome', phase='imperialism',
                subject={'type': 'nation/receivership', 'id': rec.receivership_id,
                         'nation': rec.debtor_nation},
                metric_id='finance.receivership_balance', unit=debtor_currency,
                before=remaining_debt_before, after=float(rec.remaining_debt),
                formula_id='imperialism.customs_receivership_intercept.v1',
                inputs={'operation_id': operation_id, 'turn': int(t),
                        'receivership_id': rec.receivership_id,
                        'debtor_nation': rec.debtor_nation,
                        'creditor_nation': rec.creditor_nation,
                        'gross_revenue': float(gross_amount),
                        'revenue_source': source,
                        'intercept_share': float(rec.intercept_share),
                        'desired_intercept': float(desired_intercept),
                        'actual_intercept': float(actual_intercept),
                        'total_collected_before': total_collected_before,
                        'total_collected_after': float(rec.total_collected),
                        'creditor_cash_credited': bool(creditor_credited),
                        'receivership_status_before': 'active',
                        'receivership_status_after': rec.status},
                cause_event_ids=([transfer_event_id]
                                 if transfer_event_id is not None else None))
        if trace_event_ids is not None:
            trace_event_ids.extend(event_id for event_id in
                                   (transfer_event_id, balance_event_id)
                                   if event_id is not None)

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
            reason=f"Debt-Enforcement War (gunboat collection of defaulted sovereign debt)",
            nations={n.name: n for n in world.get('nations', [])}
        )

        from client.desktop.engine import ticker_push
        ticker_push(
            world, t, 'WAR',
            f"⚔️ GUNBOAT DIPLOMACY: {creditor.name} declared Debt-Enforcement War against {debtor.name}!",
            (240, 60, 60)
        )
        return True, f"Declared Debt-Enforcement War against {debtor.name}."

    def impose_naval_blockade(self, enforcer: Nation, debtor: Nation,
                              tile: Region, t: int, world: dict) -> Tuple[bool, str]:
        """Impose a gunboat naval blockade on a debtor port tile, freezing maritime trade."""
        has_standing_units = any(getattr(u, 'soldiers', 0) > 0 for u in getattr(enforcer, 'military_units', []))
        has_scenario_fleet = False
        if world.get('scenario_id') == 'egypt_1877':
            from scenario_geography import fleet_at
            sites = world.get('scenario_state', {}).get('geography', {}).get('sites', {})
            has_scenario_fleet = (sites.get('Alexandria', {}).get('tile') == tile.name
                                  and fleet_at(world, enforcer.name, 'Alexandria'))
        if not has_standing_units and not has_scenario_fleet:
            return False, "Cannot impose naval blockade without active military fleet or standing units."

        if not getattr(tile, 'is_coast', False) and not any(getattr(n, 'is_water', False) for n in tile.neighbors.values()):
            return False, f"Cannot impose naval blockade on inland tile {tile.name}."

        self.blockaded_tiles.add(tile.name)
        self.blockade_enforcers[tile.name] = enforcer.name

        # Freeze local trade routes
        for r_name, r in getattr(tile, 'routes', {}).items():
            setattr(r, 'is_blockaded', True)

        from client.desktop.engine import ticker_push
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
                from client.desktop.engine import ticker_push
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
            from client.desktop.engine import ticker_push
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
            if b.bond_purpose == 'scenario_caisse':
                # Egypt's authored claim has its own visible creditor, naval,
                # and settlement decisions. A generic commune event cannot
                # erase that principal behind the player's back.
                continue
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
                reason="Revolutionary debt repudiation and expulsion of imperial assets",
                nations={n.name: n for n in world.get('nations', [])}
            )

        from client.desktop.engine import ticker_push
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
                        remaining_before = float(rec.remaining_debt)
                        total_collected_before = float(rec.total_collected)
                        toll_intercept = min(10.0, rec.remaining_debt)
                        debtor_cash_before = (float(debt_gov.agent.cash)
                                              if debt_gov and getattr(debt_gov, 'agent', None)
                                              else None)
                        debtor_cash_after = debtor_cash_before
                        source_cash_debited = False
                        if debt_gov and getattr(debt_gov, 'agent', None) and debt_gov.agent.cash >= toll_intercept:
                            _trace_cash_write = _trace_public_begin(None, debt_gov.agent)
                            debt_gov.agent.cash -= toll_intercept
                            _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.step_imperialism',
                                                 inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.step_imperialism:5c1621286b9148a6:1'})
                            debtor_cash_after = float(debt_gov.agent.cash)
                            source_cash_debited = True
                        else:
                            toll_intercept = min(5.0, rec.remaining_debt)

                        creditor_cash_before = None
                        creditor_cash_after = None
                        creditor_cash_credited = False
                        if cred_gov and hasattr(cred_gov, 'agent'):
                            creditor_cash_before = float(cred_gov.agent.cash)
                            _trace_cash_write = _trace_public_begin(None, cred_gov.agent)
                            cred_gov.agent.cash += toll_intercept
                            _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.step_imperialism',
                                                 inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.step_imperialism:cf6649e363456fe0:1'})
                            creditor_cash_after = float(cred_gov.agent.cash)
                            creditor_cash_credited = True
                        operation_id = (
                            f'caisse:{debtor.name}:{creditor.name}:toll:{int(t)}:'
                            f'{tile.name}:{total_collected_before:.6f}')
                        cash_event_ids = _trace_caisse_cash_seizure(
                            tile, debtor=debtor, creditor=creditor,
                            operation_id=operation_id, kind='caisse_transit_toll_seizure',
                            amount=toll_intercept, turn=t,
                            source_cash_debited=source_cash_debited,
                            creditor_cash_credited=creditor_cash_credited,
                            debtor_cash_before=debtor_cash_before,
                            debtor_cash_after=debtor_cash_after,
                            creditor_cash_before=creditor_cash_before,
                            creditor_cash_after=creditor_cash_after,
                            source_account_type='caisse_toll_shortfall_source',
                            source_status=(
                                'fallback_rule_created_receipt_without_debtor_debit'
                                if not source_cash_debited else 'exact_cash_debit'),
                            details={'remaining_debt_before': remaining_before,
                                     'debtor_cash_before': debtor_cash_before,
                                     'requested_toll_seizure': min(10.0, remaining_before),
                                     'cash_debit_rule': 'debit requested amount only when fully affordable',
                                     'fallback_rule': 'min(5, remaining debt); current simulation omits debtor debit',
                                     'has_toll_infrastructure': bool(has_toll_infra),
                                     'tile_is_coastal': bool(getattr(tile, 'is_coast', False))})
                        if creditor_cash_credited:
                            cred_gov.record_income(t, 'tariff', toll_intercept)
                        rec.remaining_debt -= toll_intercept
                        rec.total_collected += toll_intercept
                        rec.seized_tolls += toll_intercept
                        _trace_receivership_balance(
                            tile, debtor=debtor, creditor=creditor, rec=rec,
                            operation_id=operation_id, kind='caisse_transit_toll_seizure',
                            before=remaining_before, after=rec.remaining_debt,
                            turn=t, amount=toll_intercept,
                            cause_event_ids=cash_event_ids or None,
                            details={'total_collected_before': total_collected_before,
                                     'total_collected_after': float(rec.total_collected),
                                     'debtor_cash_debited': source_cash_debited,
                                     'creditor_cash_credited': creditor_cash_credited})
                        if rec.remaining_debt <= 0.01:
                            rec.status = "cleared"
                            break

                # B. Granary Buffer Food Seizure
                if rec.status == "active" and rec.remaining_debt > 0.01:
                    for tile in getattr(debtor, 'tiles', []):
                        g_stock = getattr(tile, 'granary_stock', 0.0)
                        if g_stock >= 2.0:
                            remaining_before = float(rec.remaining_debt)
                            total_collected_before = float(rec.total_collected)
                            granary_before = float(g_stock)
                            seized_grain = min(4.0, g_stock * 0.5, rec.remaining_debt / 2.0)
                            tile.granary_stock -= seized_grain
                            grain_val = seized_grain * 2.0
                            creditor_cash_before = None
                            creditor_cash_after = None
                            creditor_cash_credited = False
                            if cred_gov and hasattr(cred_gov, 'agent'):
                                creditor_cash_before = float(cred_gov.agent.cash)
                                _trace_cash_write = _trace_public_begin(None, cred_gov.agent)
                                cred_gov.agent.cash += grain_val
                                _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.step_imperialism',
                                                     inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.step_imperialism:05d979a547b6dd3d:1'})
                                creditor_cash_after = float(cred_gov.agent.cash)
                                creditor_cash_credited = True
                            operation_id = (
                                f'caisse:{debtor.name}:{creditor.name}:granary:{int(t)}:'
                                f'{tile.name}:{total_collected_before:.6f}')
                            from finance_trace import account_ref
                            from run_trace import emit
                            grain_contract = {
                                'contract_version': 'goods_seizure.v1',
                                'operation_id': operation_id,
                                'operation_type': 'caisse_granary_asset_seizure',
                                'good': 'food', 'amount': float(seized_grain),
                                'unit': 'food_units',
                                'source_account': account_ref(
                                    'tile_granary', tile.name, 'food_units',
                                    balance_before=granary_before,
                                    balance_after=float(tile.granary_stock),
                                    balance_scope='granary_stock'),
                                'destination_status': 'seized_and_monetized',
                                'counterparty_leg_status': (
                                    'creditor receives cash valuation, not food inventory'),
                            }
                            grain_event_id = emit(
                                tile, kind='caisse_granary_asset_seizure',
                                record_class='outcome', phase='imperialism',
                                subject={'type': 'tile/operation', 'id': operation_id,
                                         'tile': tile.name},
                                metric_id='goods.grain_transfer', unit='food_units',
                                before=0.0, after=float(seized_grain),
                                formula_id='imperialism.caisse_granary_valuation.v1',
                                inputs={'operation_id': operation_id,
                                        'turn': int(t),
                                        'goods_seizure_contract': grain_contract,
                                        'granary_stock_before': granary_before,
                                        'granary_stock_after': float(tile.granary_stock),
                                        'valuation_per_food_unit': 2.0,
                                        'cash_value': float(grain_val),
                                        'creditor_cash_credited': creditor_cash_credited,
                                        'creditor_receives_food_inventory': False})
                            cash_event_ids = _trace_caisse_cash_seizure(
                                tile, debtor=debtor, creditor=creditor,
                                operation_id=operation_id,
                                kind='caisse_granary_seizure_valuation',
                                amount=grain_val, turn=t,
                                source_cash_debited=False,
                                creditor_cash_credited=creditor_cash_credited,
                                creditor_cash_before=creditor_cash_before,
                                creditor_cash_after=creditor_cash_after,
                                source_account_type='caisse_grain_valuation_source',
                                source_status='converted_from_seized_granary_stock',
                                cause_event_ids=([grain_event_id]
                                                 if grain_event_id is not None else None),
                                details={'seized_food_units': float(seized_grain),
                                         'valuation_per_food_unit': 2.0,
                                         'creditor_cash_value': float(grain_val),
                                         'creditor_receives_food_inventory': False})
                            if creditor_cash_credited:
                                cred_gov.record_income(t, 'tariff', grain_val)
                            rec.remaining_debt -= grain_val
                            rec.total_collected += grain_val
                            rec.seized_granary_grain += seized_grain
                            causes = [event_id for event_id in
                                      ([grain_event_id] if grain_event_id is not None else [])
                                      + cash_event_ids if event_id is not None]
                            _trace_receivership_balance(
                                tile, debtor=debtor, creditor=creditor, rec=rec,
                                operation_id=operation_id,
                                kind='caisse_granary_asset_seizure',
                                before=remaining_before, after=rec.remaining_debt,
                                turn=t, amount=grain_val,
                                cause_event_ids=causes or None,
                                details={'total_collected_before': total_collected_before,
                                         'total_collected_after': float(rec.total_collected),
                                         'seized_food_units': float(seized_grain),
                                         'creditor_cash_credited': creditor_cash_credited})
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
                trace_region = _imperial_trace_region(world, creditor, debtor)

                if rec.enforcement_mode == "military":
                    if not has_military:
                        # Creditor lost military forces: auto-hire agents if cash available, else suspend
                        if cred_gov and hasattr(cred_gov, 'agent') and cred_gov.agent.cash >= 50.0:
                            operation_id = (f'imperial-enforcement:{rec.receivership_id}:'
                                            f'{int(t)}:replacement-agents')
                            cash_before = float(cred_gov.agent.cash)
                            gate_event_id = _trace_enforcement_funding_gate(
                                trace_region, operation_id=operation_id,
                                receivership_id=rec.receivership_id,
                                creditor=creditor, debtor_name=rec.debtor_nation,
                                turn=t, fee_required=True, amount_required=50.0,
                                cash_before=cash_before, funded=True,
                                reason='replacement_agents_affordable',
                                enforcement_mode='hired_agents')
                            _trace_cash_write = _trace_public_begin(None, cred_gov.agent)
                            cred_gov.agent.cash -= 50.0
                            _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.step_imperialism',
                                                 inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.step_imperialism:9f8754f73605cb5c:1'})
                            disbursement = _disburse_agent_funds(world, creditor, 50.0)
                            payment_event_id = _trace_enforcement_agent_payment(
                                trace_region, operation_id=operation_id,
                                receivership_id=rec.receivership_id,
                                creditor=creditor, turn=t, amount=50.0,
                                reason='receivership_replacement_agent_contract',
                                cash_before=cash_before,
                                cash_after=float(cred_gov.agent.cash),
                                disbursement=disbursement,
                                cause_event_id=gate_event_id, world=world)
                            mode_before = rec.enforcement_mode
                            rec.enforcement_mode = "hired_agents"
                            if trace_region is not None:
                                from run_trace import emit
                                causes = [event_id for event_id in
                                          (gate_event_id, payment_event_id)
                                          if event_id]
                                emit(trace_region,
                                     kind='imperial_receivership_enforcement_state',
                                     record_class='outcome', phase='imperialism',
                                     subject={'type': 'nation/receivership',
                                              'id': rec.receivership_id,
                                              'nation': creditor.name},
                                     metric_id='imperialism.receivership_state',
                                     unit='status',
                                     before=f'active:{mode_before}',
                                     after=f'active:{rec.enforcement_mode}',
                                     operation_id=operation_id,
                                     cause_event_ids=causes or None,
                                     inputs={'receivership_id': rec.receivership_id,
                                             'turn': int(t),
                                             'creditor_nation': creditor.name,
                                             'debtor_nation': rec.debtor_nation,
                                             'status': rec.status,
                                             'reason': 'military_force_lost; replacement agents contracted',
                                             'agent_payment_event_id': payment_event_id})
                            if world:
                                from client.desktop.engine import ticker_push
                                ticker_push(
                                    world, t, 'DIPLOMACY',
                                    f"📋 {creditor.name} contracted international agents ($50) to maintain receivership on {rec.debtor_nation}.",
                                    (245, 180, 50)
                                )
                        else:
                            operation_id = (f'imperial-enforcement:{rec.receivership_id}:'
                                            f'{int(t)}:replacement-agents')
                            cash_before = (float(cred_gov.agent.cash)
                                           if cred_gov and hasattr(cred_gov, 'agent')
                                           else 0.0)
                            gate_event_id = _trace_enforcement_funding_gate(
                                trace_region, operation_id=operation_id,
                                receivership_id=rec.receivership_id,
                                creditor=creditor, debtor_name=rec.debtor_nation,
                                turn=t, fee_required=True, amount_required=50.0,
                                cash_before=cash_before, funded=False,
                                reason='lost_military_force_and_insufficient_cash',
                                enforcement_mode='hired_agents')
                            status_before = rec.status
                            rec.status = "suspended"
                            if trace_region is not None:
                                from run_trace import emit
                                emit(trace_region,
                                     kind='imperial_receivership_enforcement_state',
                                     record_class='outcome', phase='imperialism',
                                     subject={'type': 'nation/receivership',
                                              'id': rec.receivership_id,
                                              'nation': creditor.name},
                                     metric_id='imperialism.receivership_state',
                                     unit='status', before=status_before,
                                     after=rec.status, operation_id=operation_id,
                                     cause_event_ids=([gate_event_id]
                                                      if gate_event_id else None),
                                     inputs={'receivership_id': rec.receivership_id,
                                             'turn': int(t),
                                             'creditor_nation': creditor.name,
                                             'debtor_nation': rec.debtor_nation,
                                             'reason': 'lost_military_force_and_agent_fee_unaffordable',
                                             'required_cash': 50.0,
                                             'cash_before': cash_before})
                            if world:
                                from client.desktop.engine import ticker_push
                                ticker_push(
                                    world, t, 'ALERT',
                                    f"⚠️ Customs Receivership on {rec.debtor_nation} suspended: {creditor.name} lacks military force and cannot afford hired agents!",
                                    (240, 80, 80)
                                )
                elif rec.enforcement_mode == "hired_agents":
                    retainer = rec.agent_retainer_cost
                    if cred_gov and hasattr(cred_gov, 'agent') and cred_gov.agent.cash >= retainer:
                        operation_id = (f'imperial-enforcement:{rec.receivership_id}:'
                                        f'{int(t)}:agent-retainer')
                        cash_before = float(cred_gov.agent.cash)
                        gate_event_id = _trace_enforcement_funding_gate(
                            trace_region, operation_id=operation_id,
                            receivership_id=rec.receivership_id,
                            creditor=creditor, debtor_name=rec.debtor_nation,
                            turn=t, fee_required=True,
                            amount_required=retainer, cash_before=cash_before,
                            funded=True, reason='agent_retainer_affordable',
                            enforcement_mode='hired_agents')
                        _trace_cash_write = _trace_public_begin(None, cred_gov.agent)
                        cred_gov.agent.cash -= retainer
                        _trace_public_finish(_trace_cash_write, 'macro/imperialism/manager:ImperialismManager.step_imperialism',
                                             inputs={"source_writer": 'macro/imperialism/manager.py:ImperialismManager.step_imperialism:f99da86178e4ba46:1'})
                        disbursement = _disburse_agent_funds(world, creditor, retainer)
                        _trace_enforcement_agent_payment(
                            trace_region, operation_id=operation_id,
                            receivership_id=rec.receivership_id,
                            creditor=creditor, turn=t, amount=retainer,
                            reason='receivership_agent_retainer',
                            cash_before=cash_before,
                            cash_after=float(cred_gov.agent.cash),
                            disbursement=disbursement,
                            cause_event_id=gate_event_id, world=world)
                    else:
                        operation_id = (f'imperial-enforcement:{rec.receivership_id}:'
                                        f'{int(t)}:agent-retainer')
                        cash_before = (float(cred_gov.agent.cash)
                                       if cred_gov and hasattr(cred_gov, 'agent')
                                       else 0.0)
                        gate_event_id = _trace_enforcement_funding_gate(
                            trace_region, operation_id=operation_id,
                            receivership_id=rec.receivership_id,
                            creditor=creditor, debtor_name=rec.debtor_nation,
                            turn=t, fee_required=True,
                            amount_required=retainer, cash_before=cash_before,
                            funded=False, reason='insufficient_cash_for_agent_retainer',
                            enforcement_mode='hired_agents')
                        status_before = rec.status
                        rec.status = "suspended"
                        if trace_region is not None:
                            from run_trace import emit
                            emit(trace_region,
                                 kind='imperial_receivership_enforcement_state',
                                 record_class='outcome', phase='imperialism',
                                 subject={'type': 'nation/receivership',
                                          'id': rec.receivership_id,
                                          'nation': creditor.name},
                                 metric_id='imperialism.receivership_state',
                                 unit='status', before=status_before,
                                 after=rec.status, operation_id=operation_id,
                                 cause_event_ids=([gate_event_id]
                                                  if gate_event_id else None),
                                 inputs={'receivership_id': rec.receivership_id,
                                         'turn': int(t),
                                         'creditor_nation': creditor.name,
                                         'debtor_nation': rec.debtor_nation,
                                         'reason': 'agent_retainer_unaffordable',
                                         'required_cash': float(retainer),
                                         'cash_before': cash_before})
                        if world:
                            from client.desktop.engine import ticker_push
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
                    from client.desktop.engine import ticker_push
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
            if default.get('bond_purpose') == 'scenario_caisse':
                # The Egypt situation resolves enforcement through its visible
                # creditor and naval choices, rather than a second AI takeover.
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
                        from client.desktop.engine import ticker_push
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
