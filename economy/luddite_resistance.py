"""
economy/luddite_resistance.py — Luddite Machine-Breaking & Worker Resistance Engine.

Theoretical Grounding (E.P. Thompson / Eric Hobsbawm / Sven Beckert):
1. Machine-Breaking as Collective Bargaining by Riot: When statutory wage caps (Statute of Laborers),
   commons enclosures, and anti-combination laws block legal unions, skilled artisans and displaced
   workers organize secret oath-based combinations under the folkloric banner of "General Ned Ludd".
2. Nocturnal Machine-Breaking Raids: Target mechanized manufacturing mills, breaking machinery
   (machinery_broken = True, decrementing machinery_level) and setting back capitalist throughput.
3. Repression vs. Pacification vs. Concession:
   - Armed Constabulary / Factory Guards: Station guards to contest nocturnal raids (strictly conserved pay).
   - Poor Relief / Speenhamland Bread Doles: Parish food/cash doles pacify worker hunger and abate tension.
   - Wage Concessions: Raising wages above starvation thresholds naturally dissolves secret combinations.
"""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from goods import Goods


@dataclass
class LudditeState:
    """Tracks secret combination strength and machine-breaking tensions on a specific parish/region."""
    region_name: str
    combination_strength: float = 0.0   # 0.0 to 100.0 (50+ triggers raids)
    factory_guards: int = 0             # Hired constables / armed mill guards
    raids_conducted: int = 0
    machines_broken: int = 0
    relief_doles_paid: float = 0.0
    active_threat_level: str = "QUIET"   # "QUIET", "FERMENTING", "ACUTE_COMBINATION", "ACTIVE_RAIDS"

    def update_threat_level(self) -> str:
        if self.combination_strength >= 75.0:
            self.active_threat_level = "ACTIVE_RAIDS"
        elif self.combination_strength >= 50.0:
            self.active_threat_level = "ACUTE_COMBINATION"
        elif self.combination_strength >= 25.0:
            self.active_threat_level = "FERMENTING"
        else:
            self.active_threat_level = "QUIET"
        return self.active_threat_level


class LudditeMovementManager:
    """Manages Luddite tension accumulation, nocturnal raids, guard defenses, and bread relief."""

    def __init__(self):
        self.states: Dict[str, LudditeState] = {}
        self.events_log: List[Dict[str, Any]] = []

    def get_state(self, region_name: str) -> LudditeState:
        if region_name not in self.states:
            self.states[region_name] = LudditeState(region_name=region_name)
        return self.states[region_name]

    def evaluate_tensions(self, region: Any, t: int) -> float:
        """Computes per-turn changes in combination strength based on objective economic conditions."""
        state = self.get_state(region.name)
        agents = getattr(region, 'agents', [])
        corps = [a for a in agents if getattr(a, 'is_corporation', False) and getattr(a, 'alive', True)]
        commoners = [a for a in agents if getattr(a, 'alive', True) and not getattr(a, 'is_lord', False) and not getattr(a, 'is_corporation', False)]

        if not corps or not commoners:
            # No factories or no workers -> tension fades
            state.combination_strength = max(0.0, state.combination_strength - 5.0)
            state.update_threat_level()
            return state.combination_strength

        delta = 0.0

        # 1. Statutory Wage Suppression Grievance
        if getattr(region, 'statute_of_laborers', False):
            delta += 12.0

        # 2. Wage Squeeze vs. Food Cost
        food_p = float(region.recipes.get(Goods.food, {}).get('price', 1.0)) if hasattr(region, 'recipes') else 1.0
        for c in corps:
            wage = getattr(c, 'wage', 2.0)
            if wage < food_p * 1.5:
                delta += 8.0  # Starvation wage
            elif wage > food_p * 3.0:
                delta -= 6.0  # Generous wage pacifies

        # 3. Displaced / Unemployed Worker Pressure
        hungry_count = sum(1 for a in commoners if getattr(a, 'hungry_steps', 0) > 0)
        unemployed_count = sum(1 for a in commoners if getattr(a, 'employer', None) is None and getattr(a, 'output', None) == Goods.none)
        delta += min(15.0, hungry_count * 2.5 + unemployed_count * 1.5)

        # 4. Mechanization Threat Factor
        max_machinery = max(getattr(c, 'machinery_level', 1) for c in corps)
        if max_machinery >= 2:
            delta += 5.0

        # 5. Deterrence from Factory Guards
        if state.factory_guards > 0:
            delta -= (state.factory_guards * 4.0)

        # Apply net delta bounded between 0 and 100
        state.combination_strength = max(0.0, min(100.0, state.combination_strength + delta))
        state.update_threat_level()
        return state.combination_strength

    def execute_nocturnal_raid(self, region: Any, t: int) -> Optional[Dict[str, Any]]:
        """Executes a clandestine machine-breaking raid if combination strength crosses threshold."""
        state = self.get_state(region.name)
        if state.combination_strength < 50.0:
            return None

        agents = getattr(region, 'agents', [])
        corps = [a for a in agents if getattr(a, 'is_corporation', False) and getattr(a, 'alive', True)
                 and (getattr(a, 'machinery_level', 0) > 0 or not getattr(a, 'machinery_broken', False))]

        if not corps:
            return None

        # Target the firm with the highest machinery level
        target_firm = max(corps, key=lambda c: getattr(c, 'machinery_level', 1))

        # Check guard defense
        if state.factory_guards > 0:
            # Armed clash: guards contest the Luddite raid
            if state.factory_guards >= 3:
                # Guards repel raid successfully!
                state.factory_guards -= 1  # 1 guard injured/fatigued
                state.combination_strength = max(0.0, state.combination_strength - 25.0)
                state.update_threat_level()
                rep = {
                    'type': 'LUDDITE_RAID_REPELLED',
                    'region': region.name,
                    'firm_id': target_firm.id,
                    'guards_remaining': state.factory_guards,
                    'message': f"Luddite raid on Firm #{target_firm.id} repelled by armed factory guards!"
                }
                self.events_log.append(rep)
                return rep
            else:
                # Guards overwhelmed: guards routed, machines broken anyway
                state.factory_guards = 0

        # Successful Machine-Breaking!
        old_level = getattr(target_firm, 'machinery_level', 1)
        target_firm.machinery_broken = True
        target_firm.broken_machinery = 1
        target_firm.machinery_level = max(0, old_level - 1)

        state.raids_conducted += 1
        state.machines_broken += 1
        state.combination_strength = max(20.0, state.combination_strength - 20.0)  # Partially vented
        state.update_threat_level()

        rep = {
            'type': 'LUDDITE_MACHINE_BROKEN',
            'region': region.name,
            'firm_id': target_firm.id,
            'old_level': old_level,
            'new_level': target_firm.machinery_level,
            'message': f"⚠️ GENERAL NED LUDD: Secret combination broke mechanical frames at Firm #{target_firm.id}!"
        }
        self.events_log.append(rep)
        return rep

    def hire_factory_guards(self, employer: Any, region: Any, count: int = 1) -> Dict[str, Any]:
        """Hire armed factory guards to protect mills against Luddites. Conserves money strictly."""
        cost_per_guard = 15.0
        total_cost = count * cost_per_guard

        if getattr(employer, 'cash', 0.0) < total_cost:
            return {'success': False, 'message': f"Insufficient funds for guards (need ${total_cost:.1f})"}

        _trace_cash_write = _trace_public_begin(None, employer)
        employer.cash -= total_cost
        _trace_public_finish(_trace_cash_write, 'economy/luddite_resistance:LudditeMovementManager.hire_factory_guards',
                             inputs={"source_writer": 'economy/luddite_resistance.py:LudditeMovementManager.hire_factory_guards:4950de5b1c06ab6f:1'})
        state = self.get_state(region.name)
        state.factory_guards += count

        # Distribute guard pay strictly to commoners/veterans in the region
        recipients = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                      and not getattr(a, 'is_lord', False) and not getattr(a, 'is_corporation', False)
                      and a.id != employer.id]
        if recipients:
            split = total_cost / len(recipients)
            for r in recipients:
                _trace_cash_write = _trace_public_begin(None, r)
                r.cash += split
                _trace_public_finish(_trace_cash_write, 'economy/luddite_resistance:LudditeMovementManager.hire_factory_guards',
                                     inputs={"source_writer": 'economy/luddite_resistance.py:LudditeMovementManager.hire_factory_guards:c136949c0a7d5fb3:1'})
        elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
            _trace_cash_write = _trace_public_begin(None, region.gov.agent)
            region.gov.agent.cash += total_cost
            _trace_public_finish(_trace_cash_write, 'economy/luddite_resistance:LudditeMovementManager.hire_factory_guards',
                                 inputs={"source_writer": 'economy/luddite_resistance.py:LudditeMovementManager.hire_factory_guards:fa32d937bd14276e:1'})
        else:
            _trace_cash_write = _trace_public_begin(None, employer)
            employer.cash += total_cost  # refund if no recipient
            _trace_public_finish(_trace_cash_write, 'economy/luddite_resistance:LudditeMovementManager.hire_factory_guards',
                                 inputs={"source_writer": 'economy/luddite_resistance.py:LudditeMovementManager.hire_factory_guards:7f15454ab8dccbc0:1'})

        state.update_threat_level()
        return {
            'success': True,
            'guards_hired': count,
            'total_guards': state.factory_guards,
            'cost': total_cost,
            'message': f"Hired {count} armed factory guard(s) to secure manufacturing mills."
        }

    def grant_parish_bread_relief(self, benefactor: Any, region: Any, amount: float = 20.0) -> Dict[str, Any]:
        """Grant emergency Speenhamland bread dole / poor relief, calming Luddite combinations."""
        if getattr(benefactor, 'cash', 0.0) < amount:
            return {'success': False, 'message': f"Insufficient funds for relief (need ${amount:.1f})"}

        _trace_cash_write = _trace_public_begin(None, benefactor)
        benefactor.cash -= amount
        _trace_public_finish(_trace_cash_write, 'economy/luddite_resistance:LudditeMovementManager.grant_parish_bread_relief',
                             inputs={"source_writer": 'economy/luddite_resistance.py:LudditeMovementManager.grant_parish_bread_relief:2146fd071cecb239:1'})
        state = self.get_state(region.name)
        state.relief_doles_paid += amount

        # Distribute relief cash or food strictly to commoners
        hungry = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                  and a.id != benefactor.id
                  and not getattr(a, 'is_lord', False) and not getattr(a, 'is_corporation', False)]
        if hungry:
            split = amount / len(hungry)
            for h in hungry:
                _trace_cash_write = _trace_public_begin(None, h)
                h.cash += split
                _trace_public_finish(_trace_cash_write, 'economy/luddite_resistance:LudditeMovementManager.grant_parish_bread_relief',
                                     inputs={"source_writer": 'economy/luddite_resistance.py:LudditeMovementManager.grant_parish_bread_relief:0f415bd425af4732:1'})
                # Clear hunger step
                if hasattr(h, 'hungry_steps'):
                    h.hungry_steps = max(0, h.hungry_steps - 1)

        # Drastically drop combination strength
        tension_drop = min(state.combination_strength, amount * 2.0)
        state.combination_strength -= tension_drop
        state.update_threat_level()

        return {
            'success': True,
            'amount_paid': amount,
            'tension_reduced': tension_drop,
            'new_strength': state.combination_strength,
            'message': f"Granted ${amount:.1f} parish poor relief; pacified secret combinations (-{tension_drop:.1f} tension)."
        }

    def step_region_luddites(self, region: Any, t: int) -> List[Dict[str, Any]]:
        """Advance Luddite movement cycle for the region."""
        self.evaluate_tensions(region, t)
        events = []
        raid_res = self.execute_nocturnal_raid(region, t)
        if raid_res:
            events.append(raid_res)
        return events
