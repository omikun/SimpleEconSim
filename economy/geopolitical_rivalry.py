"""
economy/geopolitical_rivalry.py — AI Nation Capitalist Propagation & Geopolitical Rivalry Engine.

Theoretical Grounding (Alexander Gerschenkron / Friedrich List / Sven Beckert):
1. The Industrial Dilemma of Rival States: As the metropolitan core (Lancashire) industrializes and
   dominates global manufactured export markets, rival foreign states observe this shift and adopt
   one of three strategic economic postures:
   - Mercantilist Protective Tariffs (Listian Protectionism): Erects high tariff barriers (35%-50%)
     on imported manufactures to protect domestic artisans and infant industries.
   - Subsidized Industrial Emulation (Gerschenkron Catch-Up): State subsidizes domestic steam mills
     and blast furnaces with state treasury funds to break foreign monopoly.
   - Coercive Agrarian Dependency (Peripheral Specialization): Adapts to colonial raw material export
     monoculture (cotton, sugar, tobacco), exchanging agricultural goods for manufactured imports.
2. Dynamic Trade Impact: High rival tariffs increase trade friction on metropolitan merchant voyages,
   reducing arbitrage ROI and redirecting oceanic trade circuits.
"""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from goods import Goods


class StrategicPosture:
    LAISSEZ_FAIRE = "LAISSEZ_FAIRE"                 # Standard trade, open borders (~12% tariff)
    MERCANTILIST_TARIFF = "MERCANTILIST_TARIFF"     # High protective tariff wall (35%-50%)
    INDUSTRIAL_EMULATION = "INDUSTRIAL_EMULATION"   # State-subsidized factories & infant industries
    AGRARIAN_DEPENDENCY = "AGRARIAN_DEPENDENCY"     # Peripheral raw commodity monoculture export


@dataclass
class RivalNationState:
    """Tracks strategic economic posture and industrial development of a rival foreign nation."""
    nation_name: str
    posture: str = StrategicPosture.LAISSEZ_FAIRE
    tariff_rate: float = 0.12             # Import duty on foreign manufactured goods
    emulated_mills_count: int = 0
    dependency_crop: Optional[str] = None
    geopolitical_tension: float = 0.0     # 0.0 to 100.0 (Trade friction with metropole)
    turns_in_posture: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nation_name': self.nation_name,
            'posture': self.posture,
            'tariff_rate': self.tariff_rate,
            'emulated_mills_count': self.emulated_mills_count,
            'dependency_crop': self.dependency_crop,
            'geopolitical_tension': self.geopolitical_tension,
            'turns_in_posture': self.turns_in_posture,
        }


class GeopoliticalRivalryManager:
    """Evaluates rival foreign nations, adopts strategic postures, and adjusts trade barriers."""

    def __init__(self):
        self.rival_states: Dict[str, RivalNationState] = {}
        self.events_log: List[Dict[str, Any]] = []

    def get_state(self, nation_name: str) -> RivalNationState:
        if nation_name not in self.rival_states:
            self.rival_states[nation_name] = RivalNationState(nation_name=nation_name)
        return self.rival_states[nation_name]

    def evaluate_and_step_rivals(self, world: dict, t: int) -> List[Dict[str, Any]]:
        """Evaluates geopolitical postures for all non-player rival nations."""
        events = []
        player_nation_name = world.get('player_nation_name', 'Lancashire_Metropole')
        nations = world.get('nations', [])

        for nat in nations:
            if getattr(nat, 'name', '') == player_nation_name:
                continue

            state = self.get_state(nat.name)
            state.turns_in_posture += 1

            # Assess nation capabilities
            tiles = getattr(nat, 'tiles', [])
            if not tiles:
                continue

            treasury = getattr(getattr(nat, 'gov', None), 'treasury', 50.0)
            if hasattr(treasury, 'cash'):
                treasury = treasury.cash

            has_minerals = any(getattr(tl, 'has_iron_deposit', False) or getattr(tl, 'has_coal_vein', False) for tl in tiles)
            has_warm_climate = any(getattr(tl, 'climate', '') in ('subtropical', 'tropical') for tl in tiles)

            # Check metropolitan trade penetration (how much foreign cloth is on rival tiles)
            cloth_imported = sum(sum(a.inv_get(Goods.cloth, 0) for a in getattr(tl, 'agents', [])) for tl in tiles)

            # Decision Logic:
            # 1. If rival has high cloth penetration and artisans are threatened -> Mercantilist Tariff
            if cloth_imported >= 10 and state.posture != StrategicPosture.MERCANTILIST_TARIFF:
                state.posture = StrategicPosture.MERCANTILIST_TARIFF
                state.tariff_rate = 0.40  # 40% protective tariff wall
                state.geopolitical_tension = min(100.0, state.geopolitical_tension + 25.0)
                msg = f"PROTECTIONISM: {nat.name} enacted a 40% mercantilist tariff on foreign textiles to protect domestic weavers!"
                rep = {'type': 'MERCANTILIST_TARIFF_ENACTED', 'nation': nat.name, 'tariff_rate': 0.40, 'message': msg}
                events.append(rep)
                self.events_log.append(rep)

            # 2. If rival has mineral resources and treasury -> Subsidized Industrial Emulation
            elif has_minerals and treasury >= 60.0 and state.emulated_mills_count == 0:
                state.posture = StrategicPosture.INDUSTRIAL_EMULATION
                state.emulated_mills_count += 1
                state.tariff_rate = 0.25  # Infant industry tariff

                # Incorporate state-subsidized mill on rival capital tile
                cap_tile = tiles[0]
                from agent import Agent, seed_traits
                comp = Agent(t + 500)
                comp.is_corporation = True
                seed_traits(comp)
                comp.output = Goods.cloth
                comp.machinery_level = 1
                comp.wage = 2.50
                _trace_cash_write = _trace_public_begin(None, comp)
                comp.cash = 40.0
                _trace_public_finish(_trace_cash_write, 'economy/geopolitical_rivalry:GeopoliticalRivalryManager.evaluate_and_step_rivals',
                                     inputs={"source_writer": 'economy/geopolitical_rivalry.py:GeopoliticalRivalryManager.evaluate_and_step_rivals:086df6c3b277e354:1'})
                comp.region = cap_tile.name
                cap_tile.agents.append(comp)

                msg = f"INDUSTRIAL EMULATION: {nat.name} state-subsidized mechanized steam mill #{comp.id} to break British textile monopoly!"
                rep = {'type': 'INDUSTRIAL_EMULATION_STARTED', 'nation': nat.name, 'firm_id': comp.id, 'message': msg}
                events.append(rep)
                self.events_log.append(rep)

            # 3. If warm climate but no industrial mineral base -> Agrarian Dependency
            elif has_warm_climate and not has_minerals and state.posture != StrategicPosture.AGRARIAN_DEPENDENCY:
                state.posture = StrategicPosture.AGRARIAN_DEPENDENCY
                state.dependency_crop = "cotton"
                state.tariff_rate = 0.08  # Low duty to encourage manufactured imports

                # Convert rival plots to cotton monoculture
                for tl in tiles:
                    tenure = getattr(tl, 'tenure', None)
                    if tenure and hasattr(tenure, 'plots'):
                        for p in tenure.plots:
                            if getattr(p, 'production_type', '') == 'arable':
                                p.production_type = 'cotton'
                                break

                msg = f"PERIPHERAL DEPENDENCY: {nat.name} converted estate lands to raw cotton monoculture for metropolitan export."
                rep = {'type': 'AGRARIAN_DEPENDENCY_ADOPTED', 'nation': nat.name, 'crop': 'cotton', 'message': msg}
                events.append(rep)
                self.events_log.append(rep)

        return events
