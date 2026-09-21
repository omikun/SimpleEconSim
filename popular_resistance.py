"""
popular_resistance.py — Escalation Ladder of Popular Resistance and the Revolutionary Commune.

Implements the class struggle dynamics from gdd.md (§7.3, §8, §12):
  1. Anti-Enclosure Revolts (Level 1–2):
     Dispossessed peasants physically tear down enclosure fences, reverting
     privatized plots back to customary COMMONS, restoring foraging access,
     and destroying landlord improvements.
  2. General Strike (Level 3):
     When regional labor militancy crosses critical mass, a General Strike paralyzes
     the tile: shuts down production, freezes transport routes, and starves markets.
  3. Armed Insurrection & Barricades (Level 4):
     Workers and peasants erect street barricades, raid state armories for weapons
     (strictly conserved transfers), and clash with army garrisons.
  4. The Revolutionary Commune (Level 5):
     When legitimacy collapses to 0 and insurrection triumphs, the state is overthrown
     and reconstituted as a Worker-Peasant Council Commune:
       - All land tenure across the nation is declared COMMONS (0 rent, 100% foraging).
       - Foreign imperial sovereign debt is unilaterally repudiated.
       - Ruling faction switches to Worker-Peasant Council.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any, TYPE_CHECKING
from land_tenure import TenureStatus, TileTenure
from goods import Goods

if TYPE_CHECKING:
    from nation import Nation
    from region import Region


def _safe_ticker_push(world: dict | None, t: int, category: str, msg: str, color: tuple):
    if world is None:
        return
    try:
        from worldview_engine import ticker_push
        ticker_push(world, t, category, msg, color)
    except (ImportError, Exception):
        pass


@dataclass
class AssassinationPlot:
    """Active covert plot against a charismatic rebellion leader."""
    target_leader_id: int
    target_leader_name: str
    tile_name: str
    turns_remaining: int
    total_turns: int
    funding_allocated: float
    detection_risk_per_turn: float = 0.12
    status: str = "in_progress"  # 'in_progress' | 'struck_decapitation' | 'struck_martyrdom' | 'blown' | 'aborted'


@dataclass
class RebellionConfig:
    """Configurable knobs for tailoring fermentation duration and criticality thresholds."""
    fermentation_pace: float = 1.0       # Global pace multiplier [0.2 = slow burn, 2.0 = powder keg]
    alpha_broadcast: float = 0.08        # Leader manifesto / soapbox recruitment rate
    beta_contagion: float = 0.12         # Peer-to-peer social diffusion rate
    deterrence_factor: float = 0.05      # Police presence slowdown factor
    f_crit_ratio: float = 0.35           # Fraction of sympathizers needed for Martyrdom (below = Decapitation)
    eruption_ratio: float = 0.70         # Fraction of sympathizers needed for open street action


@dataclass
class ResistanceState:
    """Per-tile popular resistance status."""
    tile_name: str
    revolt_intensity: float = 0.0      # 0.0 to 1.0
    fences_torn: int = 0               # cumulative plots de-enclosed by revolt
    is_general_strike: bool = False    # halts production and transport routes
    strike_turns_active: int = 0
    has_barricades: bool = False       # barricades erected by worker militias
    barricade_hp: float = 0.0          # structural integrity of street barricades (requires military to breach)
    armory_raided: bool = False        # state armory weapons seized
    militia_strength: int = 0          # armed citizen insurgents

    # ---- Multi-turn Stepped Anti-Enclosure Escalation ----
    enclosure_stage: str = "dormant"   # 'dormant' | 'organizing' | 'announced' | 'marching' | 'protest' | 'leveling'
    target_plot_id: Optional[str] = None
    target_plot_fraction: float = 0.0
    revolt_participants: List[int] = field(default_factory=list)  # Agent IDs actively mobilizing
    stage_turn: int = 0                # turn index of current stage
    martyrdom_multiplier: float = 1.0  # multiplier to future turnout from police killings
    terror_cooldown: int = 0           # chilling effect: turns where terror prevents organizing
    sympathizer_food_donated: int = 0  # food provided to marchers
    police_employed: int = 0           # employed police officers on payroll

    # ---- Charismatic Agitators & Fermentation Dynamics ----
    leader_id: Optional[int] = None
    leader_name: str = ""
    leader_charisma: float = 0.0
    followers: List[int] = field(default_factory=list)
    fermentation_turns: int = 0
    martyrs: List[str] = field(default_factory=list)
    active_plot: Optional[AssassinationPlot] = None


class PopularResistanceManager:
    """Orchestrates anti-enclosure revolts, general strikes, barricades, and commune transitions."""

    def __init__(self, config: Optional[RebellionConfig] = None):
        self.tile_states: Dict[str, ResistanceState] = {}
        self.resistance_log: List[Dict[str, Any]] = []
        self.config: RebellionConfig = config or RebellionConfig()

    def get_state(self, tile_name: str) -> ResistanceState:
        if tile_name not in self.tile_states:
            self.tile_states[tile_name] = ResistanceState(tile_name=tile_name)
        return self.tile_states[tile_name]

    def inject_anti_imperial_unrest(self, tile: Region, amount: float = 2.5, t: int = 0):
        """Urabi nationalist resistance: foreign fiscal intervention sparks unrest, strikes, and barricades."""
        st = self.get_state(tile.name)
        st.revolt_intensity = min(1.0, st.revolt_intensity + 0.05 * (amount / 2.5))
        tile.unrest_level = getattr(tile, 'unrest_level', 0.0) + (amount * 0.1)

        # If intensity high, escalate to barricades or citizen mobilization
        if st.revolt_intensity >= 0.65 and not st.has_barricades:
            st.has_barricades = True
            st.barricade_hp = 100.0
            st.militia_strength = max(st.militia_strength, 15)
            self.resistance_log.append({
                'turn': t,
                'tile': tile.name,
                'kind': 'URABI_BARRICADES',
                'msg': f"URABI REVOLT: Citizens of {tile.name} erected street barricades against foreign debt collectors!"
            })

    # ------------------------------------------------------------------
    # Level 1-2: Multi-Turn Anti-Enclosure Revolts
    # ------------------------------------------------------------------

    def _feed_revolt_participants(self, tile: Region, participants: List[Any], t: int, world: dict | None = None) -> int:
        """Feed marching peasants from local charity or sympathetic citizens; return total food distributed.
        
        Strictly 100% money and goods conserved.
        """
        food_distributed = 0
        charity = getattr(tile, 'charity', None)

        for a in participants:
            if not getattr(a, 'alive', True):
                continue
            # If agent already has food in inventory, consume it
            if a.inv_get(Goods.food, 0) > 0:
                a.inv_add(Goods.food, -1)
                a.hungry_steps = 0
                continue

            fed = False
            # 1. Check local parish charity
            if charity and getattr(charity, 'food_inventory', 0) > 0:
                charity.food_inventory -= 1
                a.inv_add(Goods.food, 1)
                a.inv_add(Goods.food, -1)
                a.hungry_steps = 0
                food_distributed += 1
                fed = True

            # 2. Check sympathetic citizens (non-gentry, non-gov, non-corp with surplus food)
            if not fed:
                for s in getattr(tile, 'agents', []):
                    if s.id == a.id or getattr(s, 'is_corporation', False) or getattr(s, 'is_government', False):
                        continue
                    if getattr(s, 'social_class', '') in ('proletarian', 'artisan', 'cottar', 'serf') and s.inv_get(Goods.food, 0) > 1:
                        s.inv_add(Goods.food, -1)
                        a.hungry_steps = 0
                        food_distributed += 1
                        fed = True
                        break

            # 3. Unfed marcher accumulates hunger
            if not fed:
                a.hungry_steps += 1

        # Desperation Looting: if participants are starving (hungry_steps >= 2), they raid municipal or landlord stores
        starving = [a for a in participants if getattr(a, 'alive', True) and getattr(a, 'hungry_steps', 0) >= 2]
        if len(starving) >= 2:
            rgov = getattr(tile, 'gov', None)
            food_available = getattr(rgov, 'food_inventory', 0) if rgov else 0
            if food_available > 2:
                looted = min(food_available, len(starving), 10)
                rgov.food_inventory -= looted
                for i in range(looted):
                    starving[i].hungry_steps = 0
                    food_distributed += 1
                if world:
                    _safe_ticker_push(world, t, 'ALERT', f"🥖 BREAD RIOT: Starving peasant marchers raided municipal granaries in {tile.name} ({looted} food seized)!", (240, 140, 50))

        return food_distributed

    def evaluate_anti_enclosure_revolt(self, tile: Region, t: int, world: dict | None = None) -> List[Dict[str, Any]]:
        """Multi-turn stepped anti-enclosure escalation: Organizing -> Announced -> Marching -> Protest -> Leveling."""
        events = []
        state = self.get_state(tile.name)
        tenure = getattr(tile, 'tenure', None)
        if not tenure or not tenure.plots:
            return events

        # Handle Terror Cooldown (Chilling Effect from overwhelming state violence)
        if state.terror_cooldown > 0:
            state.terror_cooldown -= 1
            if state.enclosure_stage != "dormant":
                # Clear active marchers if terror was just imposed
                for a in getattr(tile, 'agents', []):
                    if a.id in state.revolt_participants:
                        setattr(a, 'in_revolt', False)
                        setattr(a, 'is_striking', False)
                state.enclosure_stage = "dormant"
                state.revolt_participants.clear()
            return events

        enclosed = tenure.enclosed_plots()

        # If revolt is active but targeted plot was already restored to commons (e.g. by gov decree), dissolve peacefully!
        if state.enclosure_stage != "dormant":
            target_plot = tenure.find_plot(state.target_plot_id) if state.target_plot_id else None
            if not target_plot or target_plot.tenure != TenureStatus.ENCLOSED:
                for a in getattr(tile, 'agents', []):
                    if a.id in state.revolt_participants:
                        setattr(a, 'in_revolt', False)
                        setattr(a, 'is_striking', False)
                state.enclosure_stage = "dormant"
                state.revolt_participants.clear()
                state.target_plot_id = None
                ev = {
                    'turn': t,
                    'kind': 'ENCLOSURE_REVOLT_DISSOLVED_PEACEFUL',
                    'tile': tile.name,
                    'msg': f"🕊️ Peasant march in {tile.name} dissolved peacefully after enclosure grievances were resolved."
                }
                events.append(ev)
                self.resistance_log.append(ev)
                if world:
                    _safe_ticker_push(world, t, 'POLICY', f"🕊️ {ev['msg']}", (120, 240, 150))
                return events

        # Check active covert assassination plot if movement is already mobilized (dormant movements advance plot in step_rebellion_fermentation)
        if state.enclosure_stage != "dormant" and state.active_plot and state.active_plot.status == "in_progress":
            plot = state.active_plot
            plot.turns_remaining -= 1

            if random.random() < plot.detection_risk_per_turn and plot.turns_remaining > 0:
                plot.status = "blown"
                state.active_plot = None
                leader = next((a for a in getattr(tile, 'agents', []) if a.id == state.leader_id and getattr(a, 'alive', True)), None)
                if leader:
                    leader.charisma = min(1.0, getattr(leader, 'charisma', 0.5) + 0.15)
                    state.leader_charisma = leader.charisma
                ev = {
                    'turn': t,
                    'kind': 'ASSASSINATION_PLOT_BLOWN',
                    'tile': tile.name,
                    'leader_id': state.leader_id,
                    'leader_name': state.leader_name,
                    'msg': f"PLOT BLOWN: Infiltrator targeting {state.leader_name} was uncovered in {tile.name}! Public fury swells the agitator's ranks."
                }
                events.append(ev)
                self.resistance_log.append(ev)
                if world:
                    _safe_ticker_push(world, t, 'ALERT', f"⚠️ {ev['msg']}", (240, 80, 80))
            elif plot.turns_remaining <= 0:
                ok, msg, data = self.resolve_assassination_strike(tile, t, world)
                ev = {
                    'turn': t,
                    'kind': 'ASSASSINATION_STRIKE_RESOLVED',
                    'tile': tile.name,
                    'outcome': data.get('outcome', 'unknown'),
                    'msg': msg
                }
                events.append(ev)
                self.resistance_log.append(ev)
                if data.get('outcome') == 'decapitation':
                    return events

        # --------------------------------------------------------------
        # STAGE 0 -> 1: DORMANT to ORGANIZING
        # --------------------------------------------------------------
        if state.enclosure_stage == "dormant":
            if not enclosed:
                return events

            # Step covert fermentation dynamics
            ferment_evs = self.step_rebellion_fermentation(tile, t, world)
            events.extend(ferment_evs)
            if state.enclosure_stage != "dormant":
                return events

            hungry_peasants = [
                a for a in getattr(tile, 'agents', [])
                if not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)
                and not getattr(a, 'is_trader', False)
                and getattr(a, 'alive', True)
                and (getattr(a, 'hungry_steps', 0) > 0 or getattr(a, 'social_class', '') in ('dispossessed', 'tenant', 'serf', 'cottar'))
            ]
            unrest = getattr(tile, 'unrest_level', 0.0)

            # Trigger condition: 2+ hungry/dispossessed peasants and high unrest or 2+ turns starvation
            if len(hungry_peasants) >= 2 and (unrest >= 0.8 or any(getattr(a, 'hungry_steps', 0) >= 2 for a in hungry_peasants)):
                target_plot = max(enclosed, key=lambda p: p.fraction)
                
                # Base participants scaled by martyrdom multiplier from past massacres
                base_count = max(2, int(len(hungry_peasants) * 0.6 * state.martyrdom_multiplier))
                
                # Ensure leader is identified and included
                leader = self._find_or_emerge_leader(tile)
                if leader and leader in hungry_peasants:
                    other_peasants = [a for a in hungry_peasants if a.id != leader.id]
                    selected = [leader] + other_peasants[:max(1, base_count - 1)]
                else:
                    selected = hungry_peasants[:base_count]
                    if not leader and selected:
                        best_leader = max(selected, key=lambda a: getattr(a, 'charisma', 0.5) * 0.5 + getattr(a, 'ambition', 0.5) * 0.5)
                        state.leader_id = best_leader.id
                        name_attr = getattr(best_leader, 'name', None)
                        if callable(name_attr):
                            state.leader_name = name_attr()
                        elif isinstance(name_attr, str):
                            state.leader_name = name_attr
                        else:
                            state.leader_name = f"Agitator-{best_leader.id}"
                        state.leader_charisma = getattr(best_leader, 'charisma', 0.5)

                for a in selected:
                    setattr(a, 'in_revolt', True)
                    setattr(a, 'is_striking', True)

                state.revolt_participants = [a.id for a in selected]
                state.followers = list(state.revolt_participants)
                state.target_plot_id = target_plot.plot_id
                state.target_plot_fraction = target_plot.fraction
                state.enclosure_stage = "organizing"
                state.stage_turn = t

                ev = {
                    'turn': t,
                    'kind': 'ENCLOSURE_REVOLT_ORGANIZING',
                    'tile': tile.name,
                    'plot_id': target_plot.plot_id,
                    'participants': len(selected),
                    'msg': f"ORGANIZING: Clandestine peasant assemblies reported in {tile.name}. Secret oaths sworn to resist enclosures on {target_plot.plot_id}!"
                }
                events.append(ev)
                self.resistance_log.append(ev)
                if world:
                    _safe_ticker_push(world, t, 'ALERT', f"🌾 {ev['msg']}", (230, 180, 50))
                return events

        # --------------------------------------------------------------
        # ACTIVE STAGES: Sustain marchers, check logistics & advance
        # --------------------------------------------------------------
        participants = [a for a in getattr(tile, 'agents', []) if a.id in state.revolt_participants and getattr(a, 'alive', True)]
        if not participants:
            state.enclosure_stage = "dormant"
            state.revolt_participants.clear()
            return events

        # Maintain labor withholding
        for a in participants:
            setattr(a, 'in_revolt', True)
            setattr(a, 'is_striking', True)

        # Feed marchers via charity or sympathizers
        state.sympathizer_food_donated = self._feed_revolt_participants(tile, participants, t, world)

        # Advance stage ladder
        if state.enclosure_stage == "organizing":
            state.enclosure_stage = "announced"
            state.stage_turn = t
            ev = {
                'turn': t,
                'kind': 'ENCLOSURE_REVOLT_ANNOUNCED',
                'tile': tile.name,
                'plot_id': state.target_plot_id,
                'participants': len(participants),
                'msg': f"PROCLAMATION: Peasant manifestos nailed to church doors in {tile.name}, demanding fences on {state.target_plot_id} be opened!"
            }
            events.append(ev)
            self.resistance_log.append(ev)
            if world:
                _safe_ticker_push(world, t, 'ALERT', f"📜 {ev['msg']}", (240, 150, 40))

        elif state.enclosure_stage == "announced":
            state.enclosure_stage = "marching"
            state.stage_turn = t
            # Additional sympathizers join the march column
            more_peasants = [
                a for a in getattr(tile, 'agents', [])
                if a.id not in state.revolt_participants
                and not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)
                and getattr(a, 'alive', True)
                and getattr(a, 'social_class', '') in ('dispossessed', 'tenant', 'serf', 'cottar')
            ]
            if more_peasants:
                joined = more_peasants[:max(1, int(len(more_peasants) * 0.3))]
                for a in joined:
                    setattr(a, 'in_revolt', True)
                    setattr(a, 'is_striking', True)
                    state.revolt_participants.append(a.id)
                    participants.append(a)

            ev = {
                'turn': t,
                'kind': 'ENCLOSURE_REVOLT_MARCHING',
                'tile': tile.name,
                'plot_id': state.target_plot_id,
                'participants': len(participants),
                'msg': f"PEASANT MARCH: Column of {len(participants)} peasants armed with scythes and spades is marching toward {state.target_plot_id} in {tile.name}!"
            }
            events.append(ev)
            self.resistance_log.append(ev)
            if world:
                _safe_ticker_push(world, t, 'ALERT', f"🚶 {ev['msg']}", (240, 90, 40))

        elif state.enclosure_stage == "marching":
            state.enclosure_stage = "protest"
            state.stage_turn = t
            ev = {
                'turn': t,
                'kind': 'ENCLOSURE_REVOLT_PROTEST',
                'tile': tile.name,
                'plot_id': state.target_plot_id,
                'participants': len(participants),
                'msg': f"PERIMETER STANDOFF: Peasant demonstrators massed at the boundary ditches of {state.target_plot_id} in {tile.name}!"
            }
            events.append(ev)
            self.resistance_log.append(ev)
            if world:
                _safe_ticker_push(world, t, 'ALERT', f"⚠️ {ev['msg']}", (240, 40, 40))

        elif state.enclosure_stage == "protest":
            # ----------------------------------------------------------
            # STAGE 5: LEVELING (Fence Tearing & Restoring Commons)
            # ----------------------------------------------------------
            state.enclosure_stage = "leveling"
            target_plot = tenure.find_plot(state.target_plot_id)
            if target_plot and target_plot.tenure == TenureStatus.ENCLOSED:
                tenure.revert_plot_to_commons(target_plot.plot_id, turn=t)
                state.fences_torn += 1
                state.revolt_intensity = min(1.0, state.revolt_intensity + 0.3)

                # Lord memory push
                lord = next((a for a in getattr(tile, 'agents', []) if a.id == target_plot.lord_id), None)
                if lord:
                    lord.mem_push('mem_broken_fences', 1.0)
                factions = getattr(getattr(tile, 'factions', None), 'factions', {})
                if 'Gentry' in factions:
                    factions['Gentry'].add_grievance('agrarian_revolt', 3.0)
                if 'Bourgeoisie' in factions:
                    factions['Bourgeoisie'].add_grievance('agrarian_revolt', 2.0)

                # Cool unrest
                tile.unrest_level = max(0.0, tile.unrest_level - 0.2)

                owner_name = tile.owner_nation.name if getattr(tile, 'owner_nation', None) else "Neutral"
                ev = {
                    'turn': t,
                    'kind': 'ANTI_ENCLOSURE_REVOLT',
                    'tile': tile.name,
                    'nation': owner_name,
                    'plot_id': target_plot.plot_id,
                    'fraction': target_plot.fraction,
                    'new_commons_access': tenure.commons_access,
                    'msg': f"FENCE TEARING! Peasants leveled fences on {target_plot.plot_id} in {tile.name}, restoring commons foraging to {tenure.commons_access*100:.0f}%!"
                }
                events.append(ev)
                self.resistance_log.append(ev)
                if world:
                    _safe_ticker_push(world, t, 'ALERT', f"🌾 {ev['msg']}", (220, 190, 70))

            # Disperse marchers back to normal life
            for a in participants:
                setattr(a, 'in_revolt', False)
                setattr(a, 'is_striking', False)
            state.enclosure_stage = "dormant"
            state.revolt_participants.clear()
            state.target_plot_id = None

        return events

    # ------------------------------------------------------------------
    # Police / Military Interdiction of Anti-Enclosure Revolts
    # ------------------------------------------------------------------

    def interdict_enclosure_revolt(self, tile: Region, t: int, world: dict,
                                  force_level: str = "auto") -> Tuple[bool, str, Dict[str, Any]]:
        """Deploy employed police or military garrison to stop an active enclosure march/protest."""
        state = self.get_state(tile.name)
        if state.enclosure_stage in ("dormant", "leveling"):
            return False, f"No active peasant march in {tile.name} to interdict.", {}

        # 1. Verify police or military capacity (cannot conjure police from thin air)
        rgov = getattr(tile, 'gov', None)
        gov_cash = rgov.agent.cash if (rgov and hasattr(rgov, 'agent')) else 0.0
        police_count = getattr(tile, 'police_officers', getattr(rgov, 'police_officers', 0))
        garrison_soldiers = sum(getattr(u, 'soldiers', 0) for u in getattr(tile, 'military_units', []))

        if police_count <= 0 and garrison_soldiers <= 0:
            # Check if municipality can fund emergency constables ($60 required)
            if gov_cash >= 60.0:
                rgov.agent.cash -= 60.0
                police_count = 5
                setattr(tile, 'police_officers', 5)
                from imperialism import _disburse_agent_funds
                _disburse_agent_funds(world, getattr(tile, 'owner_nation', None), 60.0)
            else:
                return False, f"Cannot mobilize police: {tile.name} has no constables on payroll and municipal treasury has insufficient funds ($60 required)!", {}

        participants = [a for a in getattr(tile, 'agents', []) if a.id in state.revolt_participants and getattr(a, 'alive', True)]
        if not participants:
            state.enclosure_stage = "dormant"
            state.revolt_participants.clear()
            return True, f"Peasant march in {tile.name} had already disbanded.", {}

        # 2. Analyze crowd violence propensity
        veteran_rioters = sum(1 for a in participants if getattr(a, 'military_xp', 0.0) > 0.1)
        desperate_rioters = sum(1 for a in participants if getattr(a, 'hungry_steps', 0) >= 2 or getattr(a, 'despair', 0.0) > 0.6)
        outlaw_rioters = sum(1 for a in participants if getattr(a, 'risk_tolerance', 0.5) > 0.75)
        trauma_rioters = sum(1 for a in participants if sum(getattr(a, 'memory', {}).get('mem_casualties', [])) > 0)
        rioter_violence = (veteran_rioters * 2.0 + desperate_rioters * 1.5 + outlaw_rioters * 1.0 + trauma_rioters * 2.0) / max(1, len(participants))

        total_enforcers = police_count + garrison_soldiers * 2

        # 3. Determine clash outcome
        # Case A: Peaceful Dispersal (Enforcers heavily outnumber crowd, low rioter violence, no army)
        if total_enforcers >= len(participants) * 2 and rioter_violence < 0.4 and garrison_soldiers == 0:
            for a in participants:
                setattr(a, 'in_revolt', False)
                setattr(a, 'is_striking', False)
            state.enclosure_stage = "dormant"
            state.revolt_participants.clear()
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            for f in factions.values():
                f.add_grievance('police_intervention', 0.5)
            msg = f"🛡️ Constables cordoned off the march in {tile.name}. Peasants dispersed peacefully without casualties."
            if world:
                _safe_ticker_push(world, t, 'POLICY', msg, (120, 240, 150))
            return True, msg, {'casualties': 0, 'outcome': 'peaceful'}

        # Case B: Overwhelming Slaughter / State Terror (The Chilling Effect)
        # Triggered by standing army intervention or overwhelming police force
        if garrison_soldiers >= 5 or total_enforcers >= len(participants) * 3 or force_level == "brutal":
            kill_count = max(2, min(len(participants), int(len(participants) * 0.5)))
            victims = participants[:kill_count]
            survivors = participants[kill_count:]

            # Conserve any wealth of victims into heirs or charity
            charity = getattr(tile, 'charity', None)
            for v in victims:
                v.alive = False
                if v.cash > 0 and charity and hasattr(charity, 'agent'):
                    charity.agent.cash += v.cash
                    v.cash = 0.0
                setattr(v, 'in_revolt', False)
                setattr(v, 'is_striking', False)

            # Chilling effect state terror
            state.terror_cooldown = 10
            state.enclosure_stage = "dormant"
            state.revolt_participants.clear()
            state.followers.clear()
            state.leader_id = None
            state.martyrdom_multiplier = 1.0  # Momentum shattered

            for s in survivors:
                setattr(s, 'in_revolt', False)
                setattr(s, 'is_striking', False)
                s.mem_push('mem_casualties', 2.0)

            owner = getattr(tile, 'owner_nation', None)
            if owner:
                owner.legitimacy = max(0.05, getattr(owner, 'legitimacy', 0.6) - 0.20)

            msg = f"🩸 STATE TERROR: Armed state forces ruthlessly crushed the peasant march in {tile.name} ({kill_count} killed). A 10-turn terrorized peace smothers revolt organizing."
            if world:
                _safe_ticker_push(world, t, 'MILITARY', msg, (240, 60, 60))
            return True, msg, {'casualties': kill_count, 'outcome': 'terror'}

        # Case C: Violent Clash & Martyrdom (Backfire Effect)
        # Moderate casualties create martyrs and escalate future participation
        kill_count = max(1, min(len(participants), int(len(participants) * 0.2) or 1))
        victims = participants[:kill_count]
        survivors = participants[kill_count:]

        charity = getattr(tile, 'charity', None)
        for v in victims:
            v.alive = False
            if v.cash > 0 and charity and hasattr(charity, 'agent'):
                charity.agent.cash += v.cash
                v.cash = 0.0
            setattr(v, 'in_revolt', False)
            setattr(v, 'is_striking', False)

        for s in survivors:
            setattr(s, 'in_revolt', False)
            setattr(s, 'is_striking', False)
            s.mem_push('mem_casualties', 1.0)
            s.mem_push('mem_promises', 1.0)

        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        for fname in ('Labor', 'Peasant', 'Commoners'):
            if fname in factions:
                factions[fname].add_grievance('police_brutality', 3.0 * kill_count)

        if state.leader_id in [v.id for v in victims]:
            state.martyrs.append(state.leader_name)
            state.leader_id = None
        state.followers.clear()
        state.martyrdom_multiplier = min(3.5, state.martyrdom_multiplier + 0.6)
        state.enclosure_stage = "dormant"
        state.revolt_participants.clear()

        msg = f"⚔️ BLOODY POLICE CLASH: Constables broke up the peasant march in {tile.name} ({kill_count} killed). Public outrage erupts over fallen martyrs (+60% future turnout)!"
        if world:
            _safe_ticker_push(world, t, 'ALERT', msg, (240, 80, 80))
        return True, msg, {'casualties': kill_count, 'outcome': 'martyrdom'}

    # ------------------------------------------------------------------
    # Level 3: General Strike
    # ------------------------------------------------------------------

    def evaluate_general_strike(self, tile: Region, t: int, world: dict | None = None) -> List[Dict[str, Any]]:
        """Check if regional labor militancy crosses critical threshold to spark a General Strike."""
        events = []
        workers = [
            a for a in getattr(tile, 'agents', [])
            if getattr(a, 'social_class', '') in ('proletarian', 'serf', 'tenant', 'dispossessed')
            and getattr(a, 'alive', True)
        ]
        if not workers:
            return events

        strikers = [a for a in workers if getattr(a, 'is_striking', False)]
        strike_rate = len(strikers) / len(workers)
        unrest = getattr(tile, 'unrest_level', 0.0)
        state = self.get_state(tile.name)

        # Trigger General Strike if strike rate >= 35% or unrest >= 4.0
        if not state.is_general_strike:
            if strike_rate >= 0.35 or (strike_rate >= 0.25 and unrest >= 3.0):
                state.is_general_strike = True
                state.strike_turns_active = 1

                # Freeze local transport routes
                for r_name, r in getattr(tile, 'routes', {}).items():
                    setattr(r, 'is_blocked_by_strike', True)

                ev = {
                    'turn': t,
                    'kind': 'GENERAL_STRIKE_DECLARED',
                    'tile': tile.name,
                    'strike_rate': strike_rate,
                    'msg': f"GENERAL STRIKE! {strike_rate*100:.0f}% of workers walked out in {tile.name}. Production and transport routes frozen!"
                }
                events.append(ev)
                self.resistance_log.append(ev)

                if world:
                    _safe_ticker_push(world, t, 'ALERT', f"✊ {ev['msg']}", (240, 80, 80))
        else:
            state.strike_turns_active += 1
            # Check if general strike cools down
            if strike_rate < 0.15 and unrest < 1.5:
                state.is_general_strike = False
                state.strike_turns_active = 0
                for r in getattr(tile, 'routes', {}).values():
                    setattr(r, 'is_blocked_by_strike', False)
                ev = {
                    'turn': t,
                    'kind': 'GENERAL_STRIKE_ENDED',
                    'tile': tile.name,
                    'msg': f"General strike in {tile.name} concluded. Work and transport resumed."
                }
                events.append(ev)
                self.resistance_log.append(ev)

        return events

    # ------------------------------------------------------------------
    # Level 4: Armed Insurrection & Barricades
    # ------------------------------------------------------------------

    def evaluate_armed_insurrection(self, tile: Region, t: int, world: dict | None = None) -> List[Dict[str, Any]]:
        """Workers and dispossessed erect barricades and raid armories if unrest reaches critical fever."""
        events = []
        state = self.get_state(tile.name)
        unrest = getattr(tile, 'unrest_level', 0.0)

        # Barricades erection
        if unrest >= 4.5 and not state.has_barricades:
            state.has_barricades = True
            state.barricade_hp = 100.0
            ev = {
                'turn': t,
                'kind': 'BARRICADES_ERECTED',
                'tile': tile.name,
                'msg': f"TO THE BARRICADES! Workers and students erected street barricades across {tile.name}!"
            }
            events.append(ev)
            self.resistance_log.append(ev)
            if world:
                _safe_ticker_push(world, t, 'ALERT', f"🚧 {ev['msg']}", (240, 110, 50))
        elif state.has_barricades and state.barricade_hp <= 0.0:
            state.barricade_hp = 100.0

        # Armory raid (strictly conserved resource transfer)
        if unrest >= 6.0 and not state.armory_raided:
            # Check if tile has local government or army garrison with supplies
            state.armory_raided = True
            state.militia_strength = max(5, int(unrest * 2))

            # Conserved transfer: take food and cash from municipal government only if strikers exist
            rgov = getattr(tile, 'gov', None)
            food_looted = 0
            cash_looted = 0.0

            strikers = [
                a for a in getattr(tile, 'agents', [])
                if not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)
                and getattr(a, 'alive', True)
                and (getattr(a, 'is_striking', False) or getattr(a, 'hungry_steps', 0) > 0)
            ]

            if strikers and rgov:
                if getattr(rgov, 'food_inventory', 0) > 5:
                    food_looted = min(15, int(rgov.food_inventory * 0.5), len(strikers))
                    rgov.food_inventory -= food_looted
                    for idx in range(food_looted):
                        strikers[idx].inv_add(Goods.food, 1)

                if rgov.agent.cash > 20.0:
                    desired_cash = min(50.0, rgov.agent.cash * 0.4)
                    per_striker = round(desired_cash / len(strikers), 2)
                    if per_striker > 0:
                        total_given = per_striker * len(strikers)
                        rgov.agent.cash -= total_given
                        cash_looted = total_given
                        for s in strikers:
                            s.cash += per_striker

            ev = {
                'turn': t,
                'kind': 'ARMORY_RAIDED',
                'tile': tile.name,
                'food_looted': food_looted,
                'cash_looted': cash_looted,
                'militia_strength': state.militia_strength,
                'msg': f"ARMORY RAID! Insurgents seized the armory in {tile.name}, mobilizing {state.militia_strength} citizen militia!"
            }
            events.append(ev)
            self.resistance_log.append(ev)
            if world:
                _safe_ticker_push(world, t, 'WAR', f"⚔️ {ev['msg']}", (250, 50, 50))

        # Barricade Military Enforcement & Attrition
        if state.has_barricades:
            # Active military garrisons or stationed state units engage the barricades
            garrison_units = [u for u in getattr(tile, 'military_units', []) if getattr(u, 'soldiers', 0) > 0]
            if garrison_units:
                total_soldiers = sum(u.soldiers for u in garrison_units)
                suppression_power = max(50.0, total_soldiers * 2.0)
                state.barricade_hp -= suppression_power
                if state.barricade_hp <= 0.0:
                    state.has_barricades = False
                    state.barricade_hp = 0.0
                    state.militia_strength = max(0, state.militia_strength - 10)
                    ev = {
                        'turn': t,
                        'kind': 'BARRICADE_BREACHED',
                        'tile': tile.name,
                        'msg': f"MILITARY SUPPRESSION: State military forces stormed and dismantled street barricades in {tile.name}!"
                    }
                    events.append(ev)
                    self.resistance_log.append(ev)
                    if world:
                        _safe_ticker_push(world, t, 'MILITARY', f"⚔️ {ev['msg']}", (240, 80, 80))
            elif unrest < 1.5 and state.militia_strength == 0:
                # Unattended barricades crumble naturally without military clash if unrest has cooled
                state.has_barricades = False
                state.barricade_hp = 0.0
                ev = {
                    'turn': t,
                    'kind': 'BARRICADES_DISSOLVED',
                    'tile': tile.name,
                    'msg': f"Barricades in {tile.name} dissolved as civil unrest subsided."
                }
                events.append(ev)
                self.resistance_log.append(ev)

        return events

    # ------------------------------------------------------------------
    # Level 5: The Revolutionary Commune
    # ------------------------------------------------------------------

    def evaluate_revolutionary_commune(self, nation: Nation, t: int, world: dict) -> List[Dict[str, Any]]:
        """If legitimacy hits 0 and barricades/general strikes dominate, declare the Revolutionary Commune!"""
        events = []
        if getattr(nation, 'regime_type', '') == 'commune':
            return events

        tiles = getattr(nation, 'tiles', [])
        if not tiles:
            return events

        legitimacy = getattr(nation, 'legitimacy', 0.6)
        barricaded_count = sum(1 for tile in tiles if self.get_state(tile.name).has_barricades)
        strike_count = sum(1 for tile in tiles if self.get_state(tile.name).is_general_strike)

        # Trigger criteria: legitimacy collapsed to <= 0.05 and majority of tiles barricaded or striking
        if legitimacy <= 0.08 and (barricaded_count >= len(tiles) / 2 or strike_count >= len(tiles) / 2):
            # TRANSITION TO REVOLUTIONARY COMMUNE!
            nation.regime_type = 'commune'
            nation.ruling_faction = 'Worker-Peasant Council'
            nation.legitimacy = 0.85  # revolutionary enthusiasm

            # 1. Abolish all private land tenure across the nation -> restore to COMMONS
            total_plots_reverted = 0
            for tile in tiles:
                tenure = getattr(tile, 'tenure', None)
                if tenure:
                    total_plots_reverted += tenure.revert_all_to_commons(turn=t)
                # Lower unrest now that revolution succeeded
                tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 1.5)
                st = self.get_state(tile.name)
                st.has_barricades = False
                st.is_general_strike = False

            # 2. Unilaterally repudiate all foreign imperial sovereign debt
            from imperialism import get_imperialism_manager
            imp_mgr = get_imperialism_manager()
            repudiation_results = imp_mgr.repudiate_all_imperial_obligations(nation, t, world)

            ev = {
                'turn': t,
                'kind': 'REVOLUTIONARY_COMMUNE_DECLARED',
                'nation': nation.name,
                'plots_reverted_to_commons': total_plots_reverted,
                'repudiated_debt': repudiation_results.get('repudiated_debt', 0.0),
                'msg': f"🚩 REVOLUTIONARY COMMUNE PROCLAIMED in {nation.name}! Private land titles abolished ({total_plots_reverted} plots restored to Commons). Sovereign foreign debt repudiated!"
            }
            events.append(ev)
            self.resistance_log.append(ev)

            _safe_ticker_push(world, t, 'ALERT', f"🚩 {ev['msg']}", (255, 30, 30))

        return events

    # ------------------------------------------------------------------
    # Charismatic Rebellion Leaders, Fermentation & Covert Plots
    # ------------------------------------------------------------------

    def _find_or_emerge_leader(self, tile: Region) -> Optional[Any]:
        """Find the existing living leader or emerge a charismatic working-class agitator."""
        state = self.get_state(tile.name)
        if state.leader_id is not None:
            leader = next((a for a in getattr(tile, 'agents', []) if a.id == state.leader_id and getattr(a, 'alive', True)), None)
            if leader:
                return leader
            state.leader_id = None
            state.leader_name = ""
            state.leader_charisma = 0.0

        if state.terror_cooldown > 0:
            return None

        candidates = [
            a for a in getattr(tile, 'agents', [])
            if not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_trader', False)
            and getattr(a, 'alive', True)
            and getattr(a, 'social_class', '') in ('dispossessed', 'tenant', 'serf', 'cottar', 'proletarian')
        ]
        if not candidates:
            # Fallback for generic agents without explicit class tags
            candidates = [
                a for a in getattr(tile, 'agents', [])
                if not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)
                and not getattr(a, 'is_trader', False)
                and getattr(a, 'alive', True)
            ]
        if not candidates:
            return None

        def _score(a):
            ch = getattr(a, 'charisma', 0.5)
            amb = getattr(a, 'ambition', 0.5)
            cc = getattr(a, 'class_consciousness', 0.5)
            rt = getattr(a, 'risk_tolerance', 0.5)
            return 0.45 * ch + 0.35 * amb + 0.10 * cc + 0.10 * rt

        best = max(candidates, key=_score)
        state.leader_id = best.id
        name_attr = getattr(best, 'name', None)
        if callable(name_attr):
            state.leader_name = name_attr()
        elif isinstance(name_attr, str):
            state.leader_name = name_attr
        else:
            state.leader_name = f"Agitator-{best.id}"
        state.leader_charisma = getattr(best, 'charisma', 0.5)
        if best.id not in state.followers:
            state.followers.append(best.id)
        return best

    def step_rebellion_fermentation(self, tile: Region, t: int, world: dict | None = None) -> List[Dict[str, Any]]:
        """Advance covert fermentation, follower recruitment diffusion, and critical eruption."""
        events = []
        state = self.get_state(tile.name)
        if state.terror_cooldown > 0:
            return events

        tenure = getattr(tile, 'tenure', None)
        enclosed_plots = tenure.enclosed_plots() if tenure else []
        if not enclosed_plots:
            return events

        # Check active covert assassination plot
        if state.active_plot and state.active_plot.status == "in_progress":
            plot = state.active_plot
            plot.turns_remaining -= 1

            if random.random() < plot.detection_risk_per_turn and plot.turns_remaining > 0:
                plot.status = "blown"
                state.active_plot = None
                leader = next((a for a in getattr(tile, 'agents', []) if a.id == state.leader_id and getattr(a, 'alive', True)), None)
                if leader:
                    leader.charisma = min(1.0, getattr(leader, 'charisma', 0.5) + 0.15)
                    state.leader_charisma = leader.charisma
                ev = {
                    'turn': t,
                    'kind': 'ASSASSINATION_PLOT_BLOWN',
                    'tile': tile.name,
                    'leader_id': state.leader_id,
                    'leader_name': state.leader_name,
                    'msg': f"PLOT BLOWN: Infiltrator targeting {state.leader_name} was uncovered in {tile.name}! Public fury swells the agitator's ranks."
                }
                events.append(ev)
                self.resistance_log.append(ev)
                if world:
                    _safe_ticker_push(world, t, 'ALERT', f"⚠️ {ev['msg']}", (240, 80, 80))
            elif plot.turns_remaining <= 0:
                ok, msg, data = self.resolve_assassination_strike(tile, t, world)
                ev = {
                    'turn': t,
                    'kind': 'ASSASSINATION_STRIKE_RESOLVED',
                    'tile': tile.name,
                    'outcome': data.get('outcome', 'unknown'),
                    'msg': msg
                }
                events.append(ev)
                self.resistance_log.append(ev)
                if data.get('outcome') == 'decapitation':
                    return events

        leader = self._find_or_emerge_leader(tile)
        if not leader:
            return events

        sympathizers = [
            a for a in getattr(tile, 'agents', [])
            if not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_trader', False)
            and getattr(a, 'alive', True)
            and getattr(a, 'social_class', '') in ('dispossessed', 'tenant', 'serf', 'cottar', 'proletarian')
        ]
        if not sympathizers:
            sympathizers = [
                a for a in getattr(tile, 'agents', [])
                if not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)
                and not getattr(a, 'is_trader', False)
                and getattr(a, 'alive', True)
            ]
        K = len(sympathizers)
        if K == 0:
            return events

        # Sync living followers
        alive_ids = {a.id for a in sympathizers}
        state.followers = [fid for fid in state.followers if fid in alive_ids]
        if leader.id not in state.followers:
            state.followers.append(leader.id)
        F = len(state.followers)

        # Grievance G in [0, 1]
        unrest = getattr(tile, 'unrest_level', 0.0)
        enclosed_count = len(enclosed_plots)
        hungry_count = sum(1 for a in sympathizers if getattr(a, 'hungry_steps', 0) > 0)
        grievance = min(1.0, (unrest * 0.15) + (enclosed_count * 0.20) + (hungry_count / max(1, K) * 0.40))

        # Deterrence P
        rgov = getattr(tile, 'gov', None)
        police_count = getattr(tile, 'police_officers', getattr(rgov, 'police_officers', 0))
        garrison_soldiers = sum(getattr(u, 'soldiers', 0) for u in getattr(tile, 'military_units', []))
        P = police_count + garrison_soldiers

        # Diffusion equation: dF/dt
        cfg = self.config
        C_L = getattr(leader, 'charisma', 0.5)
        unmobilized = max(0, K - F)

        broadcast = cfg.alpha_broadcast * C_L * grievance * unmobilized
        contagion = cfg.beta_contagion * (F / max(1, K)) * grievance * unmobilized
        deterrence = cfg.deterrence_factor * P * (F / max(1, K))
        net_growth = (broadcast + contagion - deterrence) * cfg.fermentation_pace
        recruits = max(0, int(round(net_growth)))

        if recruits > 0 and unmobilized > 0:
            uncommitted = [a for a in sympathizers if a.id not in state.followers]
            for a in uncommitted[:recruits]:
                state.followers.append(a.id)

        state.fermentation_turns += 1

        # Check natural critical mass eruption
        F_curr = len(state.followers)
        T_rebel = max(2, int(K * cfg.eruption_ratio))
        if F_curr >= T_rebel and state.enclosure_stage == "dormant" and enclosed_plots:
            target_plot = max(enclosed_plots, key=lambda p: p.fraction)
            state.target_plot_id = target_plot.plot_id
            state.target_plot_fraction = target_plot.fraction
            state.revolt_participants = list(state.followers)
            for a in sympathizers:
                if a.id in state.followers:
                    setattr(a, 'in_revolt', True)
                    setattr(a, 'is_striking', True)
            state.enclosure_stage = "organizing"
            state.stage_turn = t
            ev = {
                'turn': t,
                'kind': 'ENCLOSURE_REVOLT_ORGANIZING',
                'tile': tile.name,
                'plot_id': target_plot.plot_id,
                'participants': len(state.revolt_participants),
                'leader_name': state.leader_name,
                'msg': f"ORGANIZING: {state.leader_name} mobilized clandestine assemblies ({len(state.revolt_participants)} followers) in {tile.name} to resist enclosures on {target_plot.plot_id}!"
            }
            events.append(ev)
            self.resistance_log.append(ev)
            if world:
                _safe_ticker_push(world, t, 'ALERT', f"🌾 {ev['msg']}", (230, 180, 50))

        return events

    def initiate_assassination_plot(self, tile: Region, t: int, world: dict | None = None,
                                    operative_funds: float = 75.0,
                                    target_leader_id: Optional[int] = None,
                                    turns_delay: Optional[int] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """Commission a covert assassination contract against a charismatic rebellion leader.
        
        Conserves money: funds are transferred from local government treasury to operatives/charity.
        """
        state = self.get_state(tile.name)
        leader = self._find_or_emerge_leader(tile)
        if not leader:
            return False, f"No active rebellion leader identified in {tile.name}.", {}

        if state.active_plot and state.active_plot.status == "in_progress":
            return False, f"An assassination operation is already underway against {state.leader_name} in {tile.name}.", {}

        rgov = getattr(tile, 'gov', None)
        gov_cash = rgov.agent.cash if (rgov and hasattr(rgov, 'agent')) else 0.0
        if gov_cash < operative_funds:
            return False, f"Insufficient municipal treasury funds (${gov_cash:.2f} < ${operative_funds:.2f}) to finance an assassination contract.", {}

        # Conserved funds transfer
        rgov.agent.cash -= operative_funds
        police_agents = [a for a in getattr(tile, 'agents', []) if getattr(a, 'is_police', False) or getattr(a, 'social_class', '') == 'constable']
        if police_agents:
            police_agents[0].cash += operative_funds
        elif getattr(tile, 'charity', None) and hasattr(tile.charity, 'agent'):
            tile.charity.agent.cash += operative_funds

        if turns_delay is None:
            turns_delay = random.randint(2, 4)
            if getattr(leader, 'charisma', 0.5) > 0.75:
                turns_delay += 1

        plot = AssassinationPlot(
            target_leader_id=leader.id,
            target_leader_name=state.leader_name,
            tile_name=tile.name,
            turns_remaining=turns_delay,
            total_turns=turns_delay,
            funding_allocated=operative_funds,
            detection_risk_per_turn=0.10,
            status="in_progress"
        )
        state.active_plot = plot

        msg = f"Covert assassination contract commissioned against {state.leader_name} in {tile.name} (${operative_funds:.2f} disbursed, striking in ~{turns_delay} turns)."
        if world:
            _safe_ticker_push(world, t, 'POLICY', f"🗡️ {msg}", (200, 100, 100))

        return True, msg, {'turns_delay': turns_delay, 'funding': operative_funds, 'target_id': leader.id}

    def resolve_assassination_strike(self, tile: Region, t: int, world: dict | None = None) -> Tuple[bool, str, Dict[str, Any]]:
        """Resolve an assassination strike on the leader: Decapitation vs. Martyrdom Cascade."""
        state = self.get_state(tile.name)
        leader = next((a for a in getattr(tile, 'agents', []) if a.id == state.leader_id and getattr(a, 'alive', True)), None)
        if not leader:
            state.active_plot = None
            state.leader_id = None
            return False, "Target leader was already dead or missing.", {}

        # Conserve leader's personal wealth
        leader.alive = False
        setattr(leader, 'in_revolt', False)
        setattr(leader, 'is_striking', False)
        charity = getattr(tile, 'charity', None)
        if getattr(leader, 'cash', 0.0) > 0 and charity and hasattr(charity, 'agent'):
            charity.agent.cash += leader.cash
            leader.cash = 0.0

        sympathizers = [
            a for a in getattr(tile, 'agents', [])
            if not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_trader', False)
            and getattr(a, 'alive', True)
            and getattr(a, 'social_class', '') in ('dispossessed', 'tenant', 'serf', 'cottar', 'proletarian')
        ]
        if not sympathizers:
            sympathizers = [
                a for a in getattr(tile, 'agents', [])
                if not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)
                and not getattr(a, 'is_trader', False)
                and getattr(a, 'alive', True)
            ]
        K = max(1, len(sympathizers))
        F = len([fid for fid in state.followers if fid != leader.id])
        F_crit = max(2, int(K * self.config.f_crit_ratio))

        if state.active_plot:
            state.active_plot.turns_remaining = 0

        # Case 1: Decapitation (F < F_crit)
        if F < F_crit:
            if state.active_plot:
                state.active_plot.status = "struck_decapitation"
            state.active_plot = None
            state.followers.clear()
            state.revolt_participants.clear()
            state.enclosure_stage = "dormant"
            state.terror_cooldown = 8
            state.leader_id = None

            for a in sympathizers:
                setattr(a, 'in_revolt', False)
                setattr(a, 'is_striking', False)

            msg = f"SHADOW STRIKE: Rebel leader {state.leader_name} was assassinated in {tile.name}! Without organizational roots, the movement shatters and followers scatter."
            if world:
                _safe_ticker_push(world, t, 'MILITARY', f"🗡️ {msg}", (180, 120, 120))
            return True, msg, {'outcome': 'decapitation', 'leader_name': state.leader_name, 'followers_before': F, 'f_crit': F_crit}

        # Case 2: Martyrdom Cascade (F >= F_crit)
        if state.active_plot:
            state.active_plot.status = "struck_martyrdom"
        state.active_plot = None
        state.martyrs.append(state.leader_name)
        leader_charisma = getattr(leader, 'charisma', 0.5)
        martyr_boost = 0.8 + (leader_charisma * 0.5)
        state.martyrdom_multiplier = min(4.0, state.martyrdom_multiplier + martyr_boost)

        # Discontinuous surge of uncommitted sympathizers into followers
        uncommitted = [a for a in sympathizers if a.id not in state.followers]
        surge_count = max(2, int(len(uncommitted) * 0.70))
        for a in uncommitted[:surge_count]:
            state.followers.append(a.id)

        # Trauma and betrayal memory pushed to all followers
        for a in sympathizers:
            if a.id in state.followers:
                setattr(a, 'in_revolt', True)
                setattr(a, 'is_striking', True)
                a.mem_push('mem_casualties', 2.0)
                a.mem_push('mem_promises', 2.0)

        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        for fname in ('Labor', 'Peasant', 'Commoners'):
            if fname in factions:
                factions[fname].add_grievance('martyrdom_outrage', 5.0)

        # Immediate escalation to Protest stage
        state.enclosure_stage = "protest"
        state.revolt_participants = list(state.followers)
        tile.unrest_level = min(10.0, getattr(tile, 'unrest_level', 0.0) + 3.0)
        state.leader_id = None

        msg = f"🔥 BLOOD OF THE MARTYR! {state.martyrs[-1]} was assassinated in {tile.name}! Public outrage explodes, surging {len(state.followers)} followers into immediate open revolt!"
        if world:
            _safe_ticker_push(world, t, 'ALERT', f"⚔️ {msg}", (255, 40, 40))

        return True, msg, {'outcome': 'martyrdom', 'leader_name': state.martyrs[-1], 'followers_now': len(state.followers), 'f_crit': F_crit, 'multiplier': state.martyrdom_multiplier}

    def get_rebellion_debug_info(self, tile: Region) -> Dict[str, Any]:
        """Developer and balancing telemetry monitor displaying raw underlying parameters."""
        state = self.get_state(tile.name)
        leader = next((a for a in getattr(tile, 'agents', []) if a.id == state.leader_id and getattr(a, 'alive', True)), None) if state.leader_id else None

        sympathizers = [
            a for a in getattr(tile, 'agents', [])
            if not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_trader', False)
            and getattr(a, 'alive', True)
            and getattr(a, 'social_class', '') in ('dispossessed', 'tenant', 'serf', 'cottar', 'proletarian')
        ]
        if not sympathizers:
            sympathizers = [
                a for a in getattr(tile, 'agents', [])
                if not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)
                and not getattr(a, 'is_trader', False)
                and getattr(a, 'alive', True)
            ]
        K = len(sympathizers)
        F = len(state.followers)
        F_crit = max(2, int(K * self.config.f_crit_ratio))
        T_rebel = max(2, int(K * self.config.eruption_ratio))

        plot_info = None
        if state.active_plot:
            p = state.active_plot
            plot_info = {
                'status': p.status,
                'turns_remaining': p.turns_remaining,
                'total_turns': p.total_turns,
                'funding': p.funding_allocated,
                'detection_risk': p.detection_risk_per_turn,
                'projected_outcome': 'MARTYRDOM' if F >= F_crit else 'DECAPITATION'
            }

        return {
            'tile_name': tile.name,
            'stage': state.enclosure_stage,
            'leader_id': state.leader_id,
            'leader_name': state.leader_name,
            'leader_alive': leader is not None,
            'leader_charisma': getattr(leader, 'charisma', 0.0) if leader else 0.0,
            'leader_ambition': getattr(leader, 'ambition', 0.0) if leader else 0.0,
            'followers_count': F,
            'sympathizers_capacity_k': K,
            'f_crit_threshold': F_crit,
            't_rebel_threshold': T_rebel,
            'current_regime_zone': 'MARTYRDOM_ZONE' if F >= F_crit else 'DECAPITATION_ZONE',
            'fermentation_turns': state.fermentation_turns,
            'martyrdom_multiplier': state.martyrdom_multiplier,
            'martyrs_history': list(state.martyrs),
            'terror_cooldown': state.terror_cooldown,
            'active_plot': plot_info
        }

    def get_player_intelligence_report(self, tile: Region) -> Dict[str, Any]:
        """Fog-of-war intelligence dossier for player UI with qualitative indicators."""
        state = self.get_state(tile.name)
        sympathizers = [
            a for a in getattr(tile, 'agents', [])
            if not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_trader', False)
            and getattr(a, 'alive', True)
            and getattr(a, 'social_class', '') in ('dispossessed', 'tenant', 'serf', 'cottar', 'proletarian')
        ]
        if not sympathizers:
            sympathizers = [
                a for a in getattr(tile, 'agents', [])
                if not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)
                and not getattr(a, 'is_trader', False)
                and getattr(a, 'alive', True)
            ]
        K = max(1, len(sympathizers))
        F = len(state.followers)
        ratio = F / K

        if ratio < 0.15:
            atmosphere = "Quiet grumbling in local alehouses."
            notoriety = "Faint Rumors (Obscure)"
            risk = "Minimal / Fractured (Decapitation likely)"
        elif ratio < 0.35:
            atmosphere = "Clandestine assemblies and radical pamphlets."
            notoriety = "Rising Local Firebrand"
            risk = "Moderate / Unstable"
        elif ratio < 0.60:
            atmosphere = "Widespread secret oaths across parish cottages."
            notoriety = "Household Name / Rebel Organizer"
            risk = "HIGH MARTYRDOM RISK (Liquidation will ignite fury)"
        else:
            atmosphere = "Imminent mass mobilization at the perimeter ditches!"
            notoriety = "Revered Folk Hero & Deliverer"
            risk = "CATASTROPHIC MARTYRDOM GUARANTEED"

        plot_desc = "No covert contracts active."
        if state.active_plot:
            p = state.active_plot
            plot_desc = f"Shadow warrant in progress (~{p.turns_remaining} turns remaining)."

        return {
            'tile_name': tile.name,
            'leader_known': state.leader_id is not None,
            'leader_alias': state.leader_name or "Unknown Agitator",
            'public_atmosphere': atmosphere,
            'leader_notoriety': notoriety,
            'martyrdom_risk_assessment': risk,
            'covert_plot_status': plot_desc
        }

    # ------------------------------------------------------------------
    # Step Popular Resistance Turn Loop
    # ------------------------------------------------------------------

    def step_popular_resistance(self, world: dict, t: int) -> List[Dict[str, Any]]:
        """Run popular resistance evaluation across all tiles and nations."""
        all_events = []
        tiles = world.get('tiles', [])
        nations = world.get('nations', [])

        for tile in tiles:
            if getattr(tile, 'wilderness', False):
                continue
            e1 = self.evaluate_anti_enclosure_revolt(tile, t, world)
            e2 = self.evaluate_general_strike(tile, t, world)
            e3 = self.evaluate_armed_insurrection(tile, t, world)
            all_events.extend(e1 + e2 + e3)

        for nation in nations:
            e4 = self.evaluate_revolutionary_commune(nation, t, world)
            all_events.extend(e4)

        return all_events


_GLOBAL_POPULAR_RESISTANCE: PopularResistanceManager | None = None


def get_popular_resistance_manager() -> PopularResistanceManager:
    """Return singleton PopularResistanceManager instance."""
    global _GLOBAL_POPULAR_RESISTANCE
    if _GLOBAL_POPULAR_RESISTANCE is None:
        _GLOBAL_POPULAR_RESISTANCE = PopularResistanceManager()
    return _GLOBAL_POPULAR_RESISTANCE


def reset_popular_resistance_manager() -> None:
    """Reset the singleton instance (useful for test isolation)."""
    global _GLOBAL_POPULAR_RESISTANCE
    _GLOBAL_POPULAR_RESISTANCE = None
