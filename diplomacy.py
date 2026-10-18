"""
diplomacy.py — Bilateral Relations, Treaties, Alliances, and Betrayal Memory for Call of Capital (M5.4–M5.7).

Provides:
- DiplomacySystem: Global / inter-nation diplomatic state tracking bilateral relations (-1.0 to 1.0).
- Treaty types: TRADE_PACT (tariff cuts), NON_AGGRESSION, DEFENSIVE_ALLIANCE.
- Relation drivers:
    1. Ideology distance: alignment of dominant factions between nations.
    2. Trade intimacy: bilateral trade volumes and mutual economic interdependence.
    3. Shared threats: mutual borders with powerful/expansionist rivals.
    4. Betrayal memory: history of broken pacts, backstabs, and war-crimes grievances.
- Counterbalancing alliances (M5.5): weaker nations allying against a common expansionist power.
- Betrayal mechanics (M5.7): treaty backstabbing with persistent memory, relations penalties,
  and faction grievance escalation.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum
from war_logic import PeaceOffer, WarAim, WarRecord, WarSide


def _trace_nation_objects(world):
    if world is None:
        return []
    if isinstance(world, dict):
        nations = world.get('nations', world)
        if isinstance(nations, dict):
            return list(nations.values())
        if isinstance(nations, (list, tuple, set)):
            return list(nations)
        return []
    if isinstance(world, (list, tuple, set)):
        return list(world)
    return []


def _diplomacy_trace_context(world, actor, partner, turn, action_id,
                             shared=None):
    if shared is not None:
        return shared
    nations = _trace_nation_objects(world)
    ordered = sorted(nations, key=lambda n: (
        getattr(n, 'name', None) not in (actor, partner),
        getattr(n, 'name', None) != actor))
    region = next((tile for nation in ordered
                   for tile in getattr(nation, 'tiles', ())
                   if getattr(tile, '_run_trace', None) is not None
                   and getattr(tile, '_collective_trace_clock', None) is not None),
                  None)
    if region is None:
        return None
    clock = region._collective_trace_clock
    trace_turn = int(clock.get('turn', turn))
    return {'region': region, 'turn': trace_turn,
            'operation_id': (f'diplomacy:{action_id}:{actor}:{partner}:'
                             f'{trace_turn}:{int(clock.get("next", 0))}'),
            'event_ids': [], 'last_event_id': None}


def _emit_diplomacy_trace(context, *, kind, subject, metric_id, unit,
                          after, inputs, before=None, record_class='outcome',
                          cause_event_ids=None, **extra):
    if context is None:
        return None
    from run_trace import emit
    event_inputs = dict(inputs or {})
    event_inputs.setdefault('operation_id', context['operation_id'])
    event_inputs.setdefault('turn', context['turn'])
    event_id = emit(
        context['region'], kind=kind, record_class=record_class,
        phase='strategy', subject=subject, metric_id=metric_id,
        unit=unit, before=before, after=after, inputs=event_inputs,
        cause_event_ids=cause_event_ids, **extra)
    if event_id is not None:
        context.setdefault('event_ids', []).append(event_id)
        context['last_event_id'] = event_id
    return event_id


class TreatyType(str, Enum):
    TRADE_PACT = "trade_pact"
    NON_AGGRESSION = "non_aggression"
    DEFENSIVE_ALLIANCE = "defensive_alliance"
    CUSTOMS_RECEIVERSHIP = "customs_receivership"
    UNEQUAL_TREATY = "unequal_treaty"


@dataclass
class Treaty:
    """An active or historical bilateral treaty."""
    treaty_id: str
    treaty_type: str
    nation_a: str
    nation_b: str
    signed_turn: int
    tariff_discount: float = 0.5   # 50% tariff cut for trade pacts
    status: str = "active"         # 'active' | 'broken' | 'expired'
    broken_by: str | None = None
    broken_turn: int | None = None

    def involves(self, nation_name: str) -> bool:
        return nation_name in (self.nation_a, self.nation_b)

    def partner_of(self, nation_name: str) -> str | None:
        if nation_name == self.nation_a:
            return self.nation_b
        elif nation_name == self.nation_b:
            return self.nation_a
        return None


class DiplomacySystem:
    """Global diplomacy orchestrator managing relations, treaties, and alliance blocs."""

    def __init__(self):
        # Bilateral relations: (NationA, NationB) -> float in [-1.0, 1.0] (0.0 = neutral)
        self.relations: dict[tuple[str, str], float] = {}
        # Active and historical treaties
        self.treaties: list[Treaty] = []
        # Betrayal memory: (VictimNation, BetrayerNation) -> list of memory dicts
        self.betrayal_memory: dict[tuple[str, str], list[dict]] = {}
        # Active wars: set of sorted pairs (NationA, NationB)
        self.active_wars: set[tuple[str, str]] = set()
        self.war_records: dict[tuple[str, str], WarRecord] = {}
        # Diplomatic event log (state archive)
        self.diplomacy_log: list[dict] = []

    def _pair_key(self, n1: str, n2: str) -> tuple[str, str]:
        return tuple(sorted([n1, n2]))

    def get_relation(self, n1: str, n2: str) -> float:
        """Return the bilateral relation score between n1 and n2 in [-1.0, 1.0]."""
        if n1 == n2:
            return 1.0
        return self.relations.get(self._pair_key(n1, n2), 0.0)

    def set_relation(self, n1: str, n2: str, value: float) -> None:
        """Set the bilateral relation score between n1 and n2 clamped to [-1.0, 1.0]."""
        if n1 == n2:
            return
        self.relations[self._pair_key(n1, n2)] = max(-1.0, min(1.0, float(value)))

    def adjust_relation(self, n1: str, n2: str, delta: float) -> float:
        """Adjust bilateral relation score by delta and return new score."""
        cur = self.get_relation(n1, n2)
        new_val = max(-1.0, min(1.0, cur + delta))
        self.set_relation(n1, n2, new_val)
        return new_val

    # ------------------------------------------------------------------
    # Treaty Operations
    # ------------------------------------------------------------------

    def get_active_treaties(self, n1: str, n2: str | None = None) -> list[Treaty]:
        """Return all active treaties for n1 (or specifically between n1 and n2)."""
        res = []
        for tr in self.treaties:
            if tr.status != "active":
                continue
            if n2 is None:
                if tr.involves(n1):
                    res.append(tr)
            else:
                if (tr.nation_a == n1 and tr.nation_b == n2) or (tr.nation_a == n2 and tr.nation_b == n1):
                    res.append(tr)
        return res

    def has_treaty(self, n1: str, n2: str, treaty_type: str) -> bool:
        """Check if an active treaty of treaty_type exists between n1 and n2."""
        for tr in self.get_active_treaties(n1, n2):
            if tr.treaty_type == treaty_type:
                return True
        return False

    def get_tariff_discount(self, dest_nation: str, source_nation: str) -> float:
        """Return the tariff discount (0.0 to 1.0) applied to trade from source_nation."""
        if dest_nation == source_nation:
            return 1.0
        for tr in self.get_active_treaties(dest_nation, source_nation):
            if tr.treaty_type == TreatyType.TRADE_PACT.value or tr.treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value:
                return tr.tariff_discount
        return 0.0

    def propose_treaty(self, proposer: str, target: str, treaty_type: str, t: int = 0,
                       world: dict | None = None,
                       *, _trace_world=None) -> tuple[bool, str]:
        """Propose and sign a treaty between proposer and target if terms are accepted."""
        context = _diplomacy_trace_context(
            _trace_world if _trace_world is not None else world,
            proposer, target, t, 'propose_treaty')
        subject = {'type': 'nation_pair', 'id': proposer, 'other': target}
        if proposer == target:
            _emit_diplomacy_trace(
                context, kind='diplomacy_treaty_decision',
                record_class='decision', subject=subject,
                metric_id='diplomacy.treaty_decision', unit='boolean',
                before=False, after=False,
                inputs={'treaty_type': treaty_type,
                        'reason_code': 'self_treaty'})
            return False, "Cannot sign treaty with self."
        if self.are_at_war(proposer, target):
            _emit_diplomacy_trace(
                context, kind='diplomacy_treaty_decision',
                record_class='decision', subject=subject,
                metric_id='diplomacy.treaty_decision', unit='boolean',
                before=False, after=False,
                inputs={'treaty_type': treaty_type,
                        'reason_code': 'nations_at_war'})
            return False, f"{proposer} and {target} are currently at war."
        if self.has_treaty(proposer, target, treaty_type):
            _emit_diplomacy_trace(
                context, kind='diplomacy_treaty_decision',
                record_class='decision', subject=subject,
                metric_id='diplomacy.treaty_decision', unit='boolean',
                before=False, after=False,
                inputs={'treaty_type': treaty_type,
                        'reason_code': 'treaty_already_active'})
            return False, (f"Active {treaty_type} already exists between "
                           f"{proposer} and {target}.")

        rel = self.get_relation(proposer, target)
        betrayals = self.betrayal_memory.get((target, proposer), [])
        betrayal_penalty = len(betrayals) * 0.35
        proposer_military_strength = None
        security_threshold_applied = False
        if treaty_type == TreatyType.TRADE_PACT.value:
            threshold = -0.2 + betrayal_penalty
        elif treaty_type == TreatyType.NON_AGGRESSION.value:
            threshold = 0.0 + betrayal_penalty
        elif treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value:
            threshold = 0.3 + betrayal_penalty
            # Defensive alliance requires credible security contribution.
            # Keep this evaluation tied to the behavior world only; a trace-only
            # world must not enable a rule that the caller did not previously use.
            if world and world.get('nations'):
                p_obj = next((n for n in world['nations']
                              if n.name == proposer), None)
                if p_obj:
                    proposer_military_strength = sum(
                        u.strength for u in getattr(p_obj, 'military_units', []))
                    if proposer_military_strength < 5.0:
                        threshold = max(threshold, 0.60 + betrayal_penalty)
                        security_threshold_applied = True
        else:
            threshold = 0.0
        below_threshold = rel < threshold
        accepted = not below_threshold
        reason_code = 'accepted' if accepted else 'relation_below_threshold'
        gate_event_id = _emit_diplomacy_trace(
            context, kind='diplomacy_treaty_decision',
            record_class='decision', subject=subject,
            metric_id='diplomacy.treaty_decision', unit='boolean',
            before=False, after=accepted,
            inputs={'treaty_type': treaty_type, 'relation': float(rel),
                    'relation_threshold': float(threshold),
                    'betrayal_count': len(betrayals),
                    'betrayal_penalty': float(betrayal_penalty),
                    'proposer_military_strength': proposer_military_strength,
                    'security_threshold_applied': security_threshold_applied,
                    'acceptance_model':
                    'automatic_threshold_check_no_recipient_ai_response',
                    'reason_code': reason_code})
        if below_threshold:
            message = (f"{target} rejected {treaty_type} with {proposer}: "
                       f"relations ({rel:.2f}) below threshold ({threshold:.2f}).")
            return False, message

        relation_before = rel

        # Accept and sign treaty
        treaty_id = f"tr_{treaty_type[:4]}_{proposer[:3]}_{target[:3]}_{str(uuid.uuid4())[:6]}"
        discount = 0.5 if treaty_type == TreatyType.TRADE_PACT.value else (0.75 if treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value else 0.0)
        treaty = Treaty(
            treaty_id=treaty_id,
            treaty_type=treaty_type,
            nation_a=proposer,
            nation_b=target,
            signed_turn=t,
            tariff_discount=discount,
            status="active"
        )
        self.treaties.append(treaty)
        relation_after = self.adjust_relation(proposer, target, 0.15)

        event = {
            't': t,
            'event': 'TREATY_SIGNED',
            'treaty_id': treaty_id,
            'type': treaty_type,
            'parties': [proposer, target],
            'message': f"Signed {treaty_type} between {proposer} and {target} (ID {treaty_id})."
        }
        self.diplomacy_log.append(event)
        _emit_diplomacy_trace(
            context, kind='diplomacy_treaty_signed',
            subject={'type': 'nation_pair', 'id': proposer, 'other': target},
            metric_id='diplomacy.treaty_state', unit='status',
            before='absent', after='active',
            inputs={'treaty_id': treaty_id, 'treaty_type': treaty_type,
                    'parties': [proposer, target],
                    'signed_turn': int(t), 'tariff_discount': float(discount),
                    'relation_before': float(relation_before),
                    'relation_after': float(relation_after),
                    'relation_adjustment': 0.15},
            cause_event_ids=([gate_event_id] if gate_event_id else None))
        return True, event['message']

    def break_treaty(self, breaker: str, partner: str, treaty_type: str, t: int = 0,
                     reason: str = "strategic re-evaluation",
                     *, _trace_world=None) -> dict:
        """Break an active treaty. Inflicts betrayal memory, relations penalty, and grievance."""
        broken_treaty = None
        for tr in self.get_active_treaties(breaker, partner):
            if tr.treaty_type == treaty_type:
                broken_treaty = tr
                break

        context = _diplomacy_trace_context(
            _trace_world, breaker, partner, t, 'break_treaty')
        relation_before = self.get_relation(breaker, partner)
        betrayal_count_before = len(
            self.betrayal_memory.get((partner, breaker), []))
        decision_event_id = _emit_diplomacy_trace(
            context, kind='diplomacy_treaty_break_decision',
            record_class='decision',
            subject={'type': 'nation_pair', 'id': breaker, 'other': partner},
            metric_id='diplomacy.treaty_decision', unit='boolean',
            before=False, after=broken_treaty is not None,
            inputs={'treaty_type': treaty_type, 'reason': reason,
                    'active_treaty_found': broken_treaty is not None,
                    'treaty_id': (broken_treaty.treaty_id
                                  if broken_treaty else None),
                    'reason_code': ('active_treaty_found' if broken_treaty
                                    else 'no_active_treaty')})
        if broken_treaty is None:
            return {'success': False, 'message': f"No active {treaty_type} found to break."}

        broken_treaty.status = "broken"
        broken_treaty.broken_by = breaker
        broken_treaty.broken_turn = t
        # Severe relations hit
        rel_drop = -0.6 if treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value else -0.35
        relation_after = self.adjust_relation(breaker, partner, rel_drop)

        # Store betrayal memory in victim's perspective: (partner, breaker)
        mem_key = (partner, breaker)
        if mem_key not in self.betrayal_memory:
            self.betrayal_memory[mem_key] = []
        self.betrayal_memory[mem_key].append({
            't': t,
            'treaty_type': treaty_type,
            'reason': reason,
            'severity': 0.6 if treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value else 0.3
        })

        event = {
            't': t,
            'event': 'TREATY_BROKEN',
            'breaker': breaker,
            'victim': partner,
            'type': treaty_type,
            'reason': reason,
            'message': f"{breaker} BETRAYED {partner} by breaking {treaty_type} at T={t} ({reason})."
        }
        self.diplomacy_log.append(event)
        severity = (0.6 if treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value
                    else 0.3)
        _emit_diplomacy_trace(
            context, kind='diplomacy_treaty_broken',
            subject={'type': 'nation_pair', 'id': breaker, 'other': partner},
            metric_id='diplomacy.treaty_state', unit='status',
            before='active', after='broken',
            inputs={'treaty_id': broken_treaty.treaty_id,
                    'treaty_type': treaty_type, 'breaker': breaker,
                    'victim': partner, 'reason': reason, 'turn': int(t),
                    'relation_before': float(relation_before),
                    'relation_change': float(rel_drop),
                    'relation_after': float(relation_after),
                    'betrayal_count_before': betrayal_count_before,
                    'betrayal_count_after': betrayal_count_before + 1,
                    'memory_severity': severity},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
        return {'success': True, 'event': event, 'message': event['message']}

    def sign_treaty(self, proposer: str, target: str, treaty_type: str,
                    t: int = 0, *, _trace_world=None) -> tuple[bool, str]:
        """Convenience alias to propose and sign a treaty."""
        return self.propose_treaty(proposer, target, treaty_type, t,
                                   _trace_world=_trace_world)

    def cancel_treaty(self, breaker: str, partner: str, treaty_type: str, t: int = 0,
                      reason: str = "diplomatic cancellation",
                      *, _trace_world=None) -> dict:
        """Convenience alias to cancel an active treaty amicably."""
        broken_treaty = None
        for tr in self.get_active_treaties(breaker, partner):
            if tr.treaty_type == treaty_type:
                broken_treaty = tr
                break

        context = _diplomacy_trace_context(
            _trace_world, breaker, partner, t, 'cancel_treaty')
        decision_event_id = _emit_diplomacy_trace(
            context, kind='diplomacy_treaty_cancel_decision',
            record_class='decision',
            subject={'type': 'nation_pair', 'id': breaker, 'other': partner},
            metric_id='diplomacy.treaty_decision', unit='boolean',
            before=False, after=broken_treaty is not None,
            inputs={'treaty_type': treaty_type, 'reason': reason,
                    'active_treaty_found': broken_treaty is not None,
                    'treaty_id': (broken_treaty.treaty_id
                                  if broken_treaty else None),
                    'reason_code': ('active_treaty_found' if broken_treaty
                                    else 'no_active_treaty')})
        if broken_treaty is None:
            return {'success': False, 'message': f"No active {treaty_type} found to cancel."}

        broken_treaty.status = "cancelled"
        broken_treaty.broken_by = breaker
        broken_treaty.broken_turn = t
        event = {
            't': t,
            'event': 'TREATY_CANCELLED',
            'treaty_id': broken_treaty.treaty_id,
            'breaker': breaker,
            'partner': partner,
            'type': treaty_type,
            'reason': reason,
            'message': f"{breaker} cancelled {treaty_type} with {partner} at T={t} ({reason})."
        }
        self.diplomacy_log.append(event)
        _emit_diplomacy_trace(
            context, kind='diplomacy_treaty_cancelled',
            subject={'type': 'nation_pair', 'id': breaker, 'other': partner},
            metric_id='diplomacy.treaty_state', unit='status',
            before='active', after='cancelled',
            inputs={'treaty_id': broken_treaty.treaty_id,
                    'treaty_type': treaty_type, 'breaker': breaker,
                    'partner': partner, 'reason': reason, 'turn': int(t),
                    'betrayal_memory_created': False,
                    'relation_changed': False},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
        return {'success': True, 'event': event, 'message': event['message']}

    # ------------------------------------------------------------------
    # War & Alliance Mechanics
    # ------------------------------------------------------------------

    def are_at_war(self, n1: str, n2: str) -> bool:
        return self._pair_key(n1, n2) in self.active_wars

    def declare_war(self, aggressor: str, target: str, t: int = 0,
                    reason: str = "territorial dispute", aim: WarAim | None = None,
                    nations: dict | None = None) -> list[dict]:
        """Declare war between aggressor and target.

        Breaks all treaties with target, triggers defensive alliances, sets relations to -1.0.
        """
        events = []
        war_key = self._pair_key(aggressor, target)
        context = _diplomacy_trace_context(
            nations, aggressor, target, t, 'declare_war')
        if war_key in self.active_wars:
            _emit_diplomacy_trace(
                context, kind='diplomacy_war_decision',
                record_class='decision',
                subject={'type': 'nation_pair', 'id': aggressor,
                         'other': target},
                metric_id='diplomacy.war_decision', unit='boolean',
                before=False, after=False,
                inputs={'reason': reason, 'currently_at_war': True,
                        'reason_code': 'already_at_war'})
            return events
        relation_before = self.get_relation(aggressor, target)
        broken_treaties = self.get_active_treaties(aggressor, target)
        attack_aim = aim or WarAim()
        decision_event_id = _emit_diplomacy_trace(
            context, kind='diplomacy_war_decision', record_class='decision',
            subject={'type': 'nation_pair', 'id': aggressor, 'other': target},
            metric_id='diplomacy.war_decision', unit='boolean',
            before=False, after=True,
            inputs={'reason': reason, 'aim': {'kind': attack_aim.kind,
                                               'target': attack_aim.target,
                                               'value': float(attack_aim.value)},
                    'currently_at_war': False,
                    'relation_before': float(relation_before),
                    'treaties_broken_by_declaration': [
                        {'treaty_id': treaty.treaty_id,
                         'treaty_type': treaty.treaty_type}
                        for treaty in broken_treaties],
                    'reason_code': 'war_declared'})

        self.active_wars.add(war_key)
        self._start_war_record(aggressor, target, t, attack_aim, nations)
        self.set_relation(aggressor, target, -1.0)

        # Break any active bilateral treaties with target
        for tr in self.get_active_treaties(aggressor, target):
            tr.status = "broken"
            tr.broken_by = aggressor
            tr.broken_turn = t

        war_event = {
            't': t,
            'event': 'WAR_DECLARED',
            'aggressor': aggressor,
            'target': target,
            'reason': reason,
            'message': f"WAR OUTBREAK: {aggressor} declared war on {target} at T={t} ({reason})."
        }
        self.diplomacy_log.append(war_event)
        events.append(war_event)
        relation_after = self.get_relation(aggressor, target)
        declaration_event_id = _emit_diplomacy_trace(
            context, kind='diplomacy_war_declared',
            subject={'type': 'nation_pair', 'id': aggressor, 'other': target},
            metric_id='diplomacy.war_state', unit='boolean',
            before=False, after=True,
            inputs={'aggressor': aggressor, 'target': target,
                    'reason': reason, 'aim': {'kind': attack_aim.kind,
                                               'target': attack_aim.target,
                                               'value': float(attack_aim.value)},
                    'turn': int(t), 'relation_before': float(relation_before),
                    'relation_after': float(relation_after),
                    'treaties_broken': [
                        {'treaty_id': treaty.treaty_id,
                         'treaty_type': treaty.treaty_type}
                        for treaty in broken_treaties]},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
        ally_call_event_ids = []

        # Call defensive allies of target into the war
        allies = self.get_allies(target)
        for ally in allies:
            ally_war_key = self._pair_key(ally, aggressor)
            joined = ally != aggressor and ally_war_key not in self.active_wars
            matching_treaties = [
                treaty for treaty in self.get_active_treaties(target, ally)
                if treaty.treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value]
            ally_decision_id = _emit_diplomacy_trace(
                context, kind='diplomacy_alliance_call_decision',
                record_class='decision',
                subject={'type': 'nation_pair', 'id': ally,
                         'other': aggressor},
                metric_id='diplomacy.alliance_call', unit='boolean',
                before=False, after=joined,
                inputs={'ally': ally, 'called_by': target,
                        'enemy': aggressor,
                        'defensive_treaty_ids': [
                            treaty.treaty_id for treaty in matching_treaties],
                        'already_at_war': ally_war_key in self.active_wars,
                        'ally_is_aggressor': ally == aggressor,
                        'reason_code': ('joined_by_defensive_alliance' if joined
                                        else 'ally_is_aggressor'
                                        if ally == aggressor else
                                        'already_at_war')},
                cause_event_ids=([declaration_event_id]
                                 if declaration_event_id else None))
            if joined:
                self.active_wars.add(ally_war_key)
                self._start_war_record(aggressor, ally, t,
                                       WarAim('limited'), nations)
                relation_before_ally = self.get_relation(ally, aggressor)
                self.set_relation(ally, aggressor, -1.0)
                relation_after_ally = self.get_relation(ally, aggressor)
                call_event = {
                    't': t,
                    'event': 'ALLIANCE_CALL_TO_ARMS',
                    'ally': ally,
                    'called_by': target,
                    'enemy': aggressor,
                    'message': f"ALLIANCE DEFENSE: {ally} joined war against {aggressor} to defend {target}."
                }
                self.diplomacy_log.append(call_event)
                events.append(call_event)
                call_outcome_id = _emit_diplomacy_trace(
                    context, kind='diplomacy_alliance_called',
                    subject={'type': 'nation_pair', 'id': ally,
                             'other': aggressor},
                    metric_id='diplomacy.war_state', unit='boolean',
                    before=False, after=True,
                    inputs={'ally': ally, 'called_by': target,
                            'enemy': aggressor, 'turn': int(t),
                            'war_aim': 'limited',
                            'relation_before': float(relation_before_ally),
                            'relation_after': float(relation_after_ally),
                            'defensive_treaty_ids': [
                                treaty.treaty_id
                                for treaty in matching_treaties]},
                    cause_event_ids=([ally_decision_id]
                                     if ally_decision_id else None))
                if call_outcome_id:
                    ally_call_event_ids.append(call_outcome_id)

        _emit_diplomacy_trace(
            context, kind='diplomacy_war_outcome',
            subject={'type': 'nation_pair', 'id': aggressor, 'other': target},
            metric_id='diplomacy.war_state', unit='boolean',
            before=False, after=True,
            inputs={'aggressor': aggressor, 'target': target,
                    'alliance_calls_joined': [
                        event['ally'] for event in events
                        if event.get('event') == 'ALLIANCE_CALL_TO_ARMS'],
                    'wars_active_after_declaration': [
                        list(key) for key in sorted(self.active_wars)
                        if aggressor in key],
                    'result_event_count': len(events)},
            cause_event_ids=([declaration_event_id] if declaration_event_id
                             else []) + ally_call_event_ids or None)

        return events

    def _start_war_record(self, aggressor, target, t, aim, nations):
        nations = nations or {}
        attacker, defender = nations.get(aggressor), nations.get(target)

        def tiles(nation):
            return {r.name for r in nation.tiles} if nation else set()

        attack_tiles, defense_tiles = tiles(attacker), tiles(defender)
        attack_aim = aim or WarAim()
        sides = {
            aggressor: WarSide(aims=[attack_aim], initial_tiles=attack_tiles,
                               initial_enemy_tiles=defense_tiles,
                               initial_regime=(getattr(defender, 'regime_type', ''),
                                               getattr(defender, 'ruling_faction', None))),
            target: WarSide(aims=[WarAim('defend')], initial_tiles=defense_tiles,
                            initial_enemy_tiles=attack_tiles,
                            initial_regime=(getattr(attacker, 'regime_type', ''),
                                            getattr(attacker, 'ruling_faction', None))),
        }
        self.war_records[self._pair_key(aggressor, target)] = WarRecord(
            self._pair_key(aggressor, target), t, sides)

    def get_war(self, n1: str, n2: str) -> WarRecord | None:
        return self.war_records.get(self._pair_key(n1, n2))

    def wars_for(self, nation_name: str) -> list[WarRecord]:
        return [war for key, war in self.war_records.items()
                if key in self.active_wars and nation_name in key]

    def record_battle(self, attacker: str, defender: str,
                      attacker_losses: int, defender_losses: int) -> None:
        war = self.get_war(attacker, defender)
        if war is None:
            return
        war.battle_losses[attacker] = war.battle_losses.get(attacker, 0) + attacker_losses
        war.battle_losses[defender] = war.battle_losses.get(defender, 0) + defender_losses

    def propose_peace(self, proposer: str, recipient: str, t: int = 0,
                      *, _trace_world=None) -> dict:
        war = self.get_war(proposer, recipient)
        at_war = war is not None and self.are_at_war(proposer, recipient)
        reason_code = ('not_at_war' if not at_war else
                       'offer_already_pending'
                       if war.pending_offer is not None else 'offer_created')
        context = _diplomacy_trace_context(
            _trace_world, proposer, recipient, t, 'propose_peace')
        decision_event_id = _emit_diplomacy_trace(
            context, kind='diplomacy_peace_offer_decision',
            record_class='decision',
            subject={'type': 'nation_pair', 'id': proposer, 'other': recipient},
            metric_id='diplomacy.peace_decision', unit='boolean',
            before=False, after=at_war and war.pending_offer is None,
            inputs={'proposer': proposer, 'recipient': recipient,
                    'turn': int(t), 'at_war': at_war,
                    'pending_offer_exists': bool(war and war.pending_offer),
                    'reason_code': reason_code})
        if not at_war:
            return {'success': False, 'message': 'These nations are not at war.'}
        if war.pending_offer is not None:
            return {'success': False, 'message': 'A peace offer already awaits a reply.'}
        war.pending_offer = PeaceOffer(proposer, recipient, t)
        war.sides[proposer].last_offer_turn = t
        message = f'{proposer} offered {recipient} peace on the current territorial line.'
        self.diplomacy_log.append({'t': t, 'event': 'PEACE_OFFERED',
                                   'parties': [proposer, recipient], 'message': message})
        _emit_diplomacy_trace(
            context, kind='diplomacy_peace_offer_created',
            subject={'type': 'nation_pair', 'id': proposer, 'other': recipient},
            metric_id='diplomacy.peace_state', unit='state',
            before='none', after='pending',
            inputs={'proposer': proposer, 'recipient': recipient,
                    'offer_turn': int(t), 'terms': 'current_control',
                    'territory_transfer': False},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
        return {'success': True, 'message': message}

    def respond_peace(self, recipient: str, proposer: str, accept: bool,
                      t: int = 0, *, _trace_world=None) -> dict:
        war = self.get_war(recipient, proposer)
        offer = war.pending_offer if war else None
        context = _diplomacy_trace_context(
            _trace_world, recipient, proposer, t, 'respond_peace')
        invalid_reason = (
            'no_matching_offer' if offer is None or offer.recipient != recipient
            or offer.proposer != proposer else
            'reply_must_be_next_turn' if t <= offer.turn else None)
        decision_event_id = _emit_diplomacy_trace(
            context, kind='diplomacy_peace_response_decision',
            record_class='decision',
            subject={'type': 'nation_pair', 'id': recipient, 'other': proposer},
            metric_id='diplomacy.peace_decision', unit='boolean',
            before=False, after=invalid_reason is None,
            inputs={'recipient': recipient, 'proposer': proposer,
                    'accept': bool(accept), 'turn': int(t),
                    'offer_turn': (int(offer.turn) if offer else None),
                    'minimum_reply_turn': (int(offer.turn) + 1
                                           if offer else None),
                    'reason_code': invalid_reason or
                    ('accepted' if accept else 'rejected')})
        if offer is None or offer.recipient != recipient or offer.proposer != proposer:
            return {'success': False, 'message': 'No matching peace offer exists.'}
        if t <= offer.turn:
            return {'success': False, 'message': 'The other side replies next turn.'}
        if accept:
            result = self.sign_peace(proposer, recipient, t=t,
                                     _trace_world=_trace_world,
                                     _trace_context=context)
            _emit_diplomacy_trace(
                context, kind='diplomacy_peace_response_result',
                subject={'type': 'nation_pair', 'id': recipient,
                         'other': proposer},
                metric_id='diplomacy.peace_state', unit='state',
                before='pending', after=('accepted' if result['success']
                                         else 'pending'),
                inputs={'recipient': recipient, 'proposer': proposer,
                        'accept': True, 'success': bool(result['success']),
                        'reason_code': ('accepted' if result['success'] else
                                        'peace_signing_failed')},
                cause_event_ids=([decision_event_id,
                                  context.get('last_event_id')]
                                 if decision_event_id and context and
                                 context.get('last_event_id') else
                                 [decision_event_id]
                                 if decision_event_id else None))
            return result
        war.pending_offer = None
        message = f'{recipient} rejected {proposer}\'s peace offer.'
        self.diplomacy_log.append({'t': t, 'event': 'PEACE_REJECTED',
                                   'parties': [proposer, recipient], 'message': message})
        _emit_diplomacy_trace(
            context, kind='diplomacy_peace_response_result',
            subject={'type': 'nation_pair', 'id': recipient, 'other': proposer},
            metric_id='diplomacy.peace_state', unit='state',
            before='pending', after='rejected',
            inputs={'recipient': recipient, 'proposer': proposer,
                    'accept': False, 'success': True,
                    'reason_code': 'recipient_rejected_offer'},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
        return {'success': True, 'message': message}

    def sign_peace(self, n1: str, n2: str, t: int = 0,
                   world: dict | None = None, _trace_context=None,
                   _trace_world=None) -> dict:
        """End war between n1 and n2, evaluated under relative military leverage."""
        war_key = self._pair_key(n1, n2)
        at_war = war_key in self.active_wars
        context = _diplomacy_trace_context(
            _trace_world if _trace_world is not None else world,
            n1, n2, t, 'sign_peace', _trace_context)
        relation_before = self.get_relation(n1, n2)
        war = self.war_records.get(war_key)
        decision_event_id = _emit_diplomacy_trace(
            context, kind='diplomacy_peace_signing_decision',
            record_class='decision',
            subject={'type': 'nation_pair', 'id': n1, 'other': n2},
            metric_id='diplomacy.peace_decision', unit='boolean',
            before=False, after=at_war,
            inputs={'parties': [n1, n2], 'turn': int(t),
                    'at_war': at_war,
                    'pending_offer': ({'proposer': war.pending_offer.proposer,
                                       'recipient': war.pending_offer.recipient,
                                       'turn': int(war.pending_offer.turn)}
                                      if war and war.pending_offer else None),
                    'reason_code': 'war_ended' if at_war else 'not_at_war'})
        if not at_war:
            return {'success': False, 'message': f"{n1} and {n2} were not at war."}

        self.active_wars.remove(war_key)
        self.war_records.pop(war_key, None)
        self.set_relation(n1, n2, -0.2)
        relation_after = self.get_relation(n1, n2)
        indemnity_note = ""
        reparation_event_ids = []
        reparation_decision_event_ids = []
        reparation_details = {
            'evaluated': False,
            'reason_code': ('mechanic_world_not_supplied'
                            if world is None and _trace_world is not None
                            else 'world_unavailable')}
        if world and world.get('nations'):
            n_map = {n.name: n for n in world['nations']}
            n1_obj = n_map.get(n1)
            n2_obj = n_map.get(n2)
            if n1_obj and n2_obj:
                s1 = sum(u.strength for u in getattr(n1_obj, 'military_units', []))
                s2 = sum(u.strength for u in getattr(n2_obj, 'military_units', []))
                if s1 > s2 * 2.5 and s1 >= 20.0:
                    victor, vanquished = n1_obj, n2_obj
                elif s2 > s1 * 2.5 and s2 >= 20.0:
                    victor, vanquished = n2_obj, n1_obj
                else:
                    victor, vanquished = None, None
                reason_code = ('strength_threshold_met' if victor
                               else 'relative_strength_threshold_not_met')
                leverage_event_id = _emit_diplomacy_trace(
                    context, kind='diplomacy_reparations_leverage_decision',
                    record_class='decision',
                    subject={'type': 'nation_pair', 'id': n1, 'other': n2},
                    metric_id='diplomacy.reparations_leverage_gate', unit='boolean',
                    before=False, after=victor is not None,
                    inputs={'parties': [n1, n2], 'military_strength':
                            {n1: float(s1), n2: float(s2)},
                            'minimum_victor_strength': 20.0,
                            'minimum_strength_ratio': 2.5,
                            'selected_victor': getattr(victor, 'name', None),
                            'selected_vanquished':
                            getattr(vanquished, 'name', None),
                            'reason_code': reason_code},
                    cause_event_ids=([decision_event_id]
                                     if decision_event_id else None))
                if leverage_event_id:
                    reparation_decision_event_ids.append(leverage_event_id)
                reparation_details = {
                    'evaluated': True, 'reason_code': reason_code,
                    'victor': getattr(victor, 'name', None),
                    'vanquished': getattr(vanquished, 'name', None),
                    'military_strength': {n1: float(s1), n2: float(s2)},
                }
                if victor and vanquished:
                    v_gov = getattr(vanquished, 'government', None)
                    vic_gov = getattr(victor, 'government', None)
                    if (v_gov and hasattr(v_gov, 'agent') and vic_gov
                            and hasattr(vic_gov, 'agent')):
                        payer = v_gov.agent
                        recipient = vic_gov.agent
                        payer_cash_before = float(payer.cash)
                        recipient_cash_before = float(recipient.cash)
                        indemnity = round(min(payer_cash_before * 0.4, 50.0), 2)
                        reparation_details.update({
                            'payer_cash_before': payer_cash_before,
                            'recipient_cash_before': recipient_cash_before,
                            'reparation_rate': 0.4,
                            'reparation_cap': 50.0,
                            'indemnity': float(max(0.0, indemnity)),
                            'treasury_agents_available': True,
                        })
                        reparation_gate_id = _emit_diplomacy_trace(
                            context, kind='diplomacy_reparations_amount_decision',
                            record_class='decision',
                            subject={'type': 'nation_pair', 'id': n1,
                                     'other': n2},
                            metric_id='diplomacy.reparations_amount',
                            unit='currency', before=0.0,
                            after=float(max(0.0, indemnity)),
                            inputs={'victor': victor.name,
                                    'vanquished': vanquished.name,
                                    'payer_cash_before': payer_cash_before,
                                    'reparation_rate': 0.4,
                                    'reparation_cap': 50.0,
                                    'formula': 'round(min(payer_cash * 0.4, 50.0), 2)',
                                    'reason_code': ('positive_indemnity'
                                                    if indemnity > 0 else
                                                    'no_positive_treasury_cash')},
                            cause_event_ids=([leverage_event_id]
                                             if leverage_event_id else None))
                        if reparation_gate_id:
                            reparation_decision_event_ids.append(
                                reparation_gate_id)
                        if indemnity > 0:
                            payer.cash -= indemnity
                            recipient.cash += indemnity
                            payer_cash_after = float(payer.cash)
                            recipient_cash_after = float(recipient.cash)
                            operation_id = (context['operation_id']
                                            if context is not None else
                                            f'peace-reparations:{n1}:{n2}:{t}')
                            indemnity_note = f" {vanquished.name} paid ${indemnity:.0f} war reparations to {victor.name}."
                            from run_trace import emit
                            for side_nation, delta, flow_kind, cash_before, cash_after in (
                                    (vanquished, -indemnity,
                                     'war_reparations_paid', payer_cash_before,
                                     payer_cash_after),
                                    (victor, indemnity,
                                     'war_reparations_received',
                                     recipient_cash_before,
                                     recipient_cash_after)):
                                flow_inputs = {
                                    'counterparty':
                                    (victor.name if side_nation is vanquished
                                     else vanquished.name),
                                    'peace_parties': [n1, n2],
                                    'operation_id': operation_id,
                                    'amount': float(indemnity),
                                    'cash_balance_before': cash_before,
                                    'cash_balance_after': cash_after,
                                    'relative_strength': {
                                        'victor': s1 if victor is n1_obj else s2,
                                        'vanquished': s2 if vanquished is n2_obj else s1},
                                    'reparations_decision_event_id':
                                    reparation_gate_id}
                                flow_event_id = None
                                if context is not None:
                                    flow_event_id = _emit_diplomacy_trace(
                                        context, kind=flow_kind,
                                        record_class='transfer',
                                        subject={'type': 'nation',
                                                 'id': side_nation.name},
                                        metric_id='finance.treasury_flow',
                                        unit=side_nation.currency, after=delta,
                                        inputs=flow_inputs,
                                        cause_event_ids=([reparation_gate_id]
                                                         if reparation_gate_id
                                                         else None))
                                elif side_nation.tiles:
                                    flow_event_id = emit(
                                        side_nation.tiles[0], kind=flow_kind,
                                        record_class='transfer', phase='strategy',
                                        subject={'type': 'nation',
                                                 'id': side_nation.name},
                                        metric_id='finance.treasury_flow',
                                        unit=side_nation.currency, after=delta,
                                        inputs=flow_inputs)
                                if flow_event_id:
                                    reparation_event_ids.append(flow_event_id)
                    else:
                        reparation_details['reason_code'] = 'treasury_agent_unavailable'
                        reparation_details['treasury_agents_available'] = False
            else:
                reparation_details = {
                    'evaluated': False,
                    'reason_code': 'nation_state_missing_from_world',
                    'nation_one_found': n1_obj is not None,
                    'nation_two_found': n2_obj is not None,
                }
        elif world is not None:
            reparation_details = {
                'evaluated': False,
                'reason_code': 'nations_missing_from_mechanic_world'}
        peace_event = {
            't': t,
            'event': 'PEACE_SIGNED',
            'parties': [n1, n2],
            'message': f"Peace treaty signed between {n1} and {n2} at T={t}.{indemnity_note}"
        }
        self.diplomacy_log.append(peace_event)
        _emit_diplomacy_trace(
            context, kind='diplomacy_peace_signed',
            subject={'type': 'nation_pair', 'id': n1, 'other': n2},
            metric_id='diplomacy.peace_state', unit='state',
            before='at_war', after='at_peace',
            inputs={'parties': [n1, n2], 'turn': int(t),
                    'relation_before': float(relation_before),
                    'relation_after': float(relation_after),
                    'relation_target': -0.2,
                    'indemnity_note': indemnity_note,
                    'reparations': reparation_details},
            cause_event_ids=([decision_event_id]
                             + reparation_decision_event_ids
                             + reparation_event_ids
                             if decision_event_id else
                             reparation_decision_event_ids
                             + reparation_event_ids or None))
        return {'success': True, 'message': peace_event['message']}

    def get_allies(self, nation_name: str) -> list[str]:
        """Return list of allied nation names with an active defensive alliance."""
        allies = []
        for tr in self.get_active_treaties(nation_name):
            if tr.treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value:
                partner = tr.partner_of(nation_name)
                if partner:
                    allies.append(partner)
        return allies

    # ------------------------------------------------------------------
    # Per-Turn Relations Drift & Ideology Updates
    # ------------------------------------------------------------------

    def update_relations(self, tiles: list, nations: list, t: int = 0) -> None:
        """Per-turn drift of bilateral relations based on ideology, trade, threats, and memory."""
        n_list = [n.name for n in nations]
        for i, n1 in enumerate(n_list):
            for n2 in n_list[i + 1:]:
                if self.are_at_war(n1, n2):
                    prior = self.get_relation(n1, n2)
                    self.set_relation(n1, n2, -1.0)
                    nation_obj1 = next((n for n in nations if n.name == n1), None)
                    if nation_obj1 and nation_obj1.tiles:
                        from run_trace import emit
                        emit(nation_obj1.tiles[0], kind='diplomacy_war_relation_lock',
                             record_class='calculation', phase='strategy',
                             subject={'type': 'nation_pair', 'id': n1, 'other': n2},
                             metric_id='diplomacy.relation', unit='ratio',
                             before=prior, after=-1.0,
                             formula_id='diplomacy.active_war_lock.v1',
                             inputs={'active_war': True})
                    continue

                cur_rel = self.get_relation(n1, n2)
                drift = 0.0
                ideology_drift = 0.0

                # 1. Ideological distance
                nation_obj1 = next((n for n in nations if n.name == n1), None)
                nation_obj2 = next((n for n in nations if n.name == n2), None)
                if nation_obj1 and nation_obj2:
                    # Match regime types & ruling factions
                    if nation_obj1.regime_type == nation_obj2.regime_type:
                        ideology_drift = 0.005
                    else:
                        ideology_drift = -0.005
                    drift += ideology_drift

                # 2. Trade intimacy
                trade_volume = 0.0
                for r in tiles:
                    if getattr(r, 'owner_nation', None) is nation_obj1:
                        for other in r.neighbors.values():
                            if getattr(other, 'owner_nation', None) is nation_obj2:
                                trade_volume += abs(getattr(r, 'cumulative_trade_balance', 0.0))
                if trade_volume > 50.0:
                    drift += 0.01

                # 3. Active treaties positive pull
                if self.has_treaty(n1, n2, TreatyType.DEFENSIVE_ALLIANCE.value):
                    drift += 0.02
                elif self.has_treaty(n1, n2, TreatyType.TRADE_PACT.value):
                    drift += 0.01

                # 4. Betrayal memory decay drag
                b1 = self.betrayal_memory.get((n1, n2), [])
                b2 = self.betrayal_memory.get((n2, n1), [])
                total_betrayals = len(b1) + len(b2)
                if total_betrayals > 0:
                    drift -= 0.01 * total_betrayals

                # Apply gradual drift towards target
                after = self.adjust_relation(n1, n2, drift)
                if nation_obj1 and nation_obj1.tiles:
                    from run_trace import emit
                    emit(nation_obj1.tiles[0], kind='diplomacy_relation_drift',
                         record_class='calculation', phase='strategy',
                         subject={'type': 'nation_pair', 'id': n1, 'other': n2},
                         metric_id='diplomacy.relation', unit='ratio',
                         before=cur_rel, after=after,
                         formula_id='diplomacy.ideology_trade_treaty_memory.v1',
                         inputs={'ideology_drift': ideology_drift,
                                 'trade_volume': trade_volume,
                                 'trade_drift': 0.01 if trade_volume > 50.0 else 0.0,
                                 'defensive_alliance': self.has_treaty(n1, n2,
                                     TreatyType.DEFENSIVE_ALLIANCE.value),
                                 'trade_pact': self.has_treaty(n1, n2,
                                     TreatyType.TRADE_PACT.value),
                                 'active_treaty_drift': 0.02 if self.has_treaty(n1, n2,
                                     TreatyType.DEFENSIVE_ALLIANCE.value) else
                                     (0.01 if self.has_treaty(n1, n2, TreatyType.TRADE_PACT.value) else 0.0),
                                 'betrayals': total_betrayals,
                                 'betrayal_drift': -0.01 * total_betrayals,
                                 'requested_drift': drift},
                         constraints={'lower_bound': -1.0, 'upper_bound': 1.0})


# Global singleton instance for shared simulation access
diplomacy_instance = DiplomacySystem()

def get_diplomacy() -> DiplomacySystem:
    return diplomacy_instance
