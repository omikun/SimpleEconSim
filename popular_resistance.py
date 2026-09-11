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


class PopularResistanceManager:
    """Orchestrates anti-enclosure revolts, general strikes, barricades, and commune transitions."""

    def __init__(self):
        self.tile_states: Dict[str, ResistanceState] = {}
        self.resistance_log: List[Dict[str, Any]] = []

    def get_state(self, tile_name: str) -> ResistanceState:
        if tile_name not in self.tile_states:
            self.tile_states[tile_name] = ResistanceState(tile_name=tile_name)
        return self.tile_states[tile_name]

    # ------------------------------------------------------------------
    # Level 1-2: Anti-Enclosure Revolts
    # ------------------------------------------------------------------

    def evaluate_anti_enclosure_revolt(self, tile: Region, t: int, world: dict | None = None) -> List[Dict[str, Any]]:
        """Check if dispossessed / hungry peasants tear down enclosure fences on *tile*."""
        events = []
        tenure = getattr(tile, 'tenure', None)
        if not tenure or not tenure.plots:
            return events

        enclosed = tenure.enclosed_plots()
        if not enclosed:
            return events

        # Count hungry non-corp, non-gov citizens (especially dispossessed and tenants)
        hungry_peasants = [
            a for a in getattr(tile, 'agents', [])
            if not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_trader', False)
            and getattr(a, 'alive', True)
            and (getattr(a, 'hungry_steps', 0) > 0 or getattr(a, 'social_class', '') in ('dispossessed', 'tenant', 'serf'))
        ]

        unrest = getattr(tile, 'unrest_level', 0.0)
        state = self.get_state(tile.name)

        # Trigger revolt if multiple hungry peasants and positive unrest
        if len(hungry_peasants) >= 2 and (unrest >= 0.8 or any(getattr(a, 'hungry_steps', 0) >= 2 for a in hungry_peasants)):
            # Revolt fires: peasants tear down the fence of the largest enclosed plot
            target_plot = max(enclosed, key=lambda p: p.fraction)
            tenure.revert_plot_to_commons(target_plot.plot_id, turn=t)
            state.fences_torn += 1
            state.revolt_intensity = min(1.0, state.revolt_intensity + 0.3)

            # Enrage landlord / lord
            lord = next((a for a in getattr(tile, 'agents', []) if a.id == target_plot.lord_id), None)
            if lord:
                lord.mem_push('mem_broken_fences', 1.0)
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            if 'Gentry' in factions:
                factions['Gentry'].add_grievance('agrarian_revolt', 3.0)
            if 'Bourgeoisie' in factions:
                factions['Bourgeoisie'].add_grievance('agrarian_revolt', 2.0)

            # Peasant hunger and unrest cools slightly now that commons foraging is restored
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
                'msg': f"FENCE TEARING! Dispossessed peasants tore down fences on plot {target_plot.plot_id} in {tile.name}, restoring commons foraging access to {tenure.commons_access*100:.0f}%!"
            }
            events.append(ev)
            self.resistance_log.append(ev)

            if world:
                from worldview_engine import ticker_push
                ticker_push(world, t, 'ALERT', f"🌾 {ev['msg']}", (220, 190, 70))

        return events

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
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'ALERT', f"✊ {ev['msg']}", (240, 80, 80))
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
                from worldview_engine import ticker_push
                ticker_push(world, t, 'ALERT', f"🚧 {ev['msg']}", (240, 110, 50))
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
                from worldview_engine import ticker_push
                ticker_push(world, t, 'WAR', f"⚔️ {ev['msg']}", (250, 50, 50))

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
                        from worldview_engine import ticker_push
                        ticker_push(world, t, 'MILITARY', f"⚔️ {ev['msg']}", (240, 80, 80))
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

            from worldview_engine import ticker_push
            ticker_push(world, t, 'ALERT', f"🚩 {ev['msg']}", (255, 30, 30))

        return events

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
