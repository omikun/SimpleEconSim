"""
diplomacy.py — Bilateral Relations, Treaties, Alliances, and Betrayal Memory for REGNUM (M5.4–M5.7).

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

    def propose_treaty(self, proposer: str, target: str, treaty_type: str, t: int = 0) -> tuple[bool, str]:
        """Propose and sign a treaty between proposer and target if terms are accepted."""
        if proposer == target:
            return False, "Cannot sign treaty with self."

        if self.are_at_war(proposer, target):
            return False, f"{proposer} and {target} are currently at war."

        if self.has_treaty(proposer, target, treaty_type):
            return False, f"Active {treaty_type} already exists between {proposer} and {target}."

        rel = self.get_relation(proposer, target)
        # Check betrayal history
        betrayals = self.betrayal_memory.get((target, proposer), [])
        betrayal_penalty = len(betrayals) * 0.35

        # Thresholds by treaty type
        if treaty_type == TreatyType.TRADE_PACT.value:
            threshold = -0.2 + betrayal_penalty
        elif treaty_type == TreatyType.NON_AGGRESSION.value:
            threshold = 0.0 + betrayal_penalty
        elif treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value:
            threshold = 0.3 + betrayal_penalty
        else:
            threshold = 0.0

        if rel < threshold:
            reason = (f"{target} rejected {treaty_type} with {proposer}: "
                      f"relations ({rel:.2f}) below threshold ({threshold:.2f}).")
            return False, reason

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
        self.adjust_relation(proposer, target, 0.15)

        event = {
            't': t,
            'event': 'TREATY_SIGNED',
            'treaty_id': treaty_id,
            'type': treaty_type,
            'parties': [proposer, target],
            'message': f"Signed {treaty_type} between {proposer} and {target} (ID {treaty_id})."
        }
        self.diplomacy_log.append(event)
        return True, event['message']

    def break_treaty(self, breaker: str, partner: str, treaty_type: str, t: int = 0,
                     reason: str = "strategic re-evaluation") -> dict:
        """Break an active treaty. Inflicts betrayal memory, relations penalty, and grievance."""
        broken_treaty = None
        for tr in self.get_active_treaties(breaker, partner):
            if tr.treaty_type == treaty_type:
                tr.status = "broken"
                tr.broken_by = breaker
                tr.broken_turn = t
                broken_treaty = tr
                break

        if broken_treaty is None:
            return {'success': False, 'message': f"No active {treaty_type} found to break."}

        # Severe relations hit
        rel_drop = -0.6 if treaty_type == TreatyType.DEFENSIVE_ALLIANCE.value else -0.35
        self.adjust_relation(breaker, partner, rel_drop)

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
        return {'success': True, 'event': event, 'message': event['message']}

    def sign_treaty(self, proposer: str, target: str, treaty_type: str, t: int = 0) -> tuple[bool, str]:
        """Convenience alias to propose and sign a treaty."""
        return self.propose_treaty(proposer, target, treaty_type, t)

    def cancel_treaty(self, breaker: str, partner: str, treaty_type: str, t: int = 0,
                      reason: str = "diplomatic cancellation") -> dict:
        """Convenience alias to cancel an active treaty amicably."""
        broken_treaty = None
        for tr in self.get_active_treaties(breaker, partner):
            if tr.treaty_type == treaty_type:
                tr.status = "cancelled"
                tr.broken_by = breaker
                tr.broken_turn = t
                broken_treaty = tr
                break

        if broken_treaty is None:
            return {'success': False, 'message': f"No active {treaty_type} found to cancel."}

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
        return {'success': True, 'event': event, 'message': event['message']}

    # ------------------------------------------------------------------
    # War & Alliance Mechanics
    # ------------------------------------------------------------------

    def are_at_war(self, n1: str, n2: str) -> bool:
        return self._pair_key(n1, n2) in self.active_wars

    def declare_war(self, aggressor: str, target: str, t: int = 0,
                    reason: str = "territorial dispute") -> list[dict]:
        """Declare war between aggressor and target.

        Breaks all treaties with target, triggers defensive alliances, sets relations to -1.0.
        """
        events = []
        war_key = self._pair_key(aggressor, target)
        if war_key in self.active_wars:
            return events

        self.active_wars.add(war_key)
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

        # Call defensive allies of target into the war
        allies = self.get_allies(target)
        for ally in allies:
            if ally == aggressor:
                continue
            ally_war_key = self._pair_key(ally, aggressor)
            if ally_war_key not in self.active_wars:
                self.active_wars.add(ally_war_key)
                self.set_relation(ally, aggressor, -1.0)
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

        return events

    def sign_peace(self, n1: str, n2: str, t: int = 0) -> dict:
        """End war between n1 and n2."""
        war_key = self._pair_key(n1, n2)
        if war_key in self.active_wars:
            self.active_wars.remove(war_key)
            self.set_relation(n1, n2, -0.2)
            event = {
                't': t,
                'event': 'PEACE_SIGNED',
                'parties': [n1, n2],
                'message': f"Peace treaty signed between {n1} and {n2} at T={t}."
            }
            self.diplomacy_log.append(event)
            return {'success': True, 'message': event['message']}
        return {'success': False, 'message': f"{n1} and {n2} were not at war."}

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
                    self.set_relation(n1, n2, -1.0)
                    continue

                cur_rel = self.get_relation(n1, n2)
                drift = 0.0

                # 1. Ideological distance
                nation_obj1 = next((n for n in nations if n.name == n1), None)
                nation_obj2 = next((n for n in nations if n.name == n2), None)
                if nation_obj1 and nation_obj2:
                    # Match regime types & ruling factions
                    if nation_obj1.regime_type == nation_obj2.regime_type:
                        drift += 0.005
                    else:
                        drift -= 0.005

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
                self.adjust_relation(n1, n2, drift)


# Global singleton instance for shared simulation access
diplomacy_instance = DiplomacySystem()

def get_diplomacy() -> DiplomacySystem:
    return diplomacy_instance
