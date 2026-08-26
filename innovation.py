"""
innovation.py — Induced Innovation, Learning-by-Doing & Technology Diffusion Engine for REGNUM.

Implements real-world technological evolution:
1. Learning-by-Doing: Practical economic output accumulates domain experience:
   - Agronomy: Cumulative food harvests and famine survival.
   - Manufacturing: Cumulative timber cutting and furniture production.
   - Civil Engineering: Cumulative trade flow across rugged terrain and water corridors.
   - Finance: Cumulative market trade settlements, forex volumes, and debt management.
   - Military: Cumulative soldier-turns, border defense, and battle experience.
2. Induced Innovation (Bottlenecks Drive Breakthroughs):
   - High food price / hunger -> accelerates agricultural breakthroughs.
   - High mountain friction / sheer cliffs -> accelerates alpine blasting & tunneling.
   - High wages / labor shortages -> accelerates mechanization.
   - Active wars -> accelerates metallurgy, logistics, and siegecraft.
3. Royal Innovation Bounties:
   - Sovereigns can pledge a cash purse from the national treasury (e.g. $400) for a specific
     bottleneck. When local inventors/corporations discover it, the prize is disbursed (conserved money).
4. Trade Diffusion & Reverse-Engineering:
   - Innovations spread organically along active trade routes and bilateral trade pacts.
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

from goods import Goods
from random_cache import rand

if TYPE_CHECKING:
    from nation import Nation
    from region import Region


class TechDomain(str, Enum):
    AGRONOMY = "agronomy"
    MANUFACTURING = "manufacturing"
    CIVIL_ENGINEERING = "civil_engineering"
    FINANCE = "finance"
    MILITARY = "military"


@dataclass
class Technology:
    tech_id: str
    name: str
    domain: TechDomain
    description: str
    base_xp_required: float
    era: int = 1
    unlocked_buildings: list[str] = field(default_factory=list)
    production_modifiers: dict[str, float] = field(default_factory=dict)
    bottleneck_evaluator: Callable[[Nation, list[Region]], float] | None = None


# -----------------------------------------------------------------------------
# Bottleneck Pressure Calculators (Real-World Economic Incentives)
# -----------------------------------------------------------------------------

def _eval_food_bottleneck(nation: Nation, tiles: list[Region]) -> float:
    """High food price inflation & hunger accelerate agricultural breakthroughs."""
    if not tiles:
        return 1.0
    avg_food_price = sum(r.recipes.get(Goods.food, {}).get('price', 1.0) for r in tiles) / len(tiles)
    hungry_count = sum(sum(1 for a in r.agents if getattr(a, 'hungry_steps', 0) > 0) for r in tiles)
    multiplier = 1.0
    if avg_food_price > 1.8:
        multiplier += (avg_food_price - 1.8) * 1.5
    if hungry_count > 10:
        multiplier += min(3.0, hungry_count * 0.10)
    return min(4.0, multiplier)


def _eval_mountain_bottleneck(nation: Nation, tiles: list[Region]) -> float:
    """High elevation, impassable cliffs, and mountain borders accelerate blasting & tunneling."""
    if not tiles:
        return 1.0
    high_tiles = sum(1 for r in tiles if getattr(r, 'elevation', 0.0) >= 0.50)
    blocked_edges = 0
    from terrain_edges import get_edge_manager
    em = get_edge_manager()
    if em:
        for r in tiles:
            for other_name in getattr(r, 'all_adjacent_names', []):
                edge = em.get_edge(r.name, other_name)
                if edge and not edge.passable:
                    blocked_edges += 1
    multiplier = 1.0 + (high_tiles * 0.4) + (blocked_edges * 0.3)
    return min(4.5, multiplier)


def _eval_wage_labor_bottleneck(nation: Nation, tiles: list[Region]) -> float:
    """High worker wages and labor shortages accelerate mechanization & labor-saving tools."""
    if not tiles:
        return 1.0
    wages = [a.wage for r in tiles for a in getattr(r, 'agents', []) if hasattr(a, 'wage') and a.wage > 0]
    avg_wage = (sum(wages) / len(wages)) if wages else 1.0
    multiplier = 1.0
    if avg_wage > 2.0:
        multiplier += (avg_wage - 2.0) * 1.2
    return min(3.5, multiplier)


def _eval_war_bottleneck(nation: Nation, tiles: list[Region]) -> float:
    """Active wars and military threats accelerate military doctrine & supply logistics."""
    from diplomacy import get_diplomacy
    dip = get_diplomacy()
    active_wars = len([w for w in dip.active_wars if nation.name in w])
    if active_wars > 0:
        return 2.5 + active_wars * 1.0
    return 1.0


# -----------------------------------------------------------------------------
# Technology Catalog
# -----------------------------------------------------------------------------

TECH_CATALOG: dict[str, Technology] = {
    # 1. Agronomy & Demographics
    'crop_rotation': Technology(
        tech_id='crop_rotation',
        name='Four-Field Crop Rotation',
        domain=TechDomain.AGRONOMY,
        description='Restores soil fertility naturally, granting +25% baseline food productivity.',
        base_xp_required=350.0,
        era=1,
        production_modifiers={Goods.food.value: 1.25},
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'granary_silos': Technology(
        tech_id='granary_silos',
        name='State Granary Silos',
        domain=TechDomain.AGRONOMY,
        description='Hermetically sealed food storage; unlocks State Granary construction.',
        base_xp_required=600.0,
        era=1,
        unlocked_buildings=['granary'],
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'mechanized_reaping': Technology(
        tech_id='mechanized_reaping',
        name='Horse-Drawn Mechanical Reapers',
        domain=TechDomain.AGRONOMY,
        description='Drastically reduces farm labor requirement while raising harvest volume by +40%.',
        base_xp_required=1200.0,
        era=2,
        production_modifiers={Goods.food.value: 1.40},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),

    # 2. Manufacturing & Metallurgy
    'hydraulic_sawmills': Technology(
        tech_id='hydraulic_sawmills',
        name='Water-Powered Sawmills',
        domain=TechDomain.MANUFACTURING,
        description='Harnesses fluvial water flow to saw lumber; unlocks Mechanized Sawmill.',
        base_xp_required=380.0,
        era=1,
        unlocked_buildings=['sawmill'],
        production_modifiers={Goods.wood.value: 1.30},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),
    'guild_standardization': Technology(
        tech_id='guild_standardization',
        name='Standardized Workshop Guilds',
        domain=TechDomain.MANUFACTURING,
        description='Specialized artisan tools and templates; unlocks Artisan Workshop & Guildhall.',
        base_xp_required=650.0,
        era=1,
        unlocked_buildings=['workshop'],
        production_modifiers={Goods.furniture.value: 1.30},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),

    # 3. Civil Engineering & Geography
    'engineered_roadbeds': Technology(
        tech_id='engineered_roadbeds',
        name='Engineered Macadam Roadbeds',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Crushed stone foundation networks; unlocks Paved Highway Networks (-40% friction).',
        base_xp_required=400.0,
        era=1,
        unlocked_buildings=['paved_road'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'fluvial_locks': Technology(
        tech_id='fluvial_locks',
        name='Fluvial River Locks & Bridges',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Pioneers permanent river crossings; unlocks Fluvial River Bridges & Ports.',
        base_xp_required=550.0,
        era=1,
        unlocked_buildings=['river_bridge'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'gunpowder_blasting': Technology(
        tech_id='gunpowder_blasting',
        name='Gunpowder Rock Blasting & Tunneling',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Blasts through sheer granite cliffs; unlocks Alpine Mountain Pass Roads.',
        base_xp_required=950.0,
        era=2,
        unlocked_buildings=['mountain_pass'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),

    # 4. Finance & Institutions
    'double_entry_bookkeeping': Technology(
        tech_id='double_entry_bookkeeping',
        name='Double-Entry Ledger Auditing',
        domain=TechDomain.FINANCE,
        description='Improves commercial transparency, reducing bank loan defaults and liquidity panics.',
        base_xp_required=420.0,
        era=1,
    ),
    'public_sanatoriums': Technology(
        tech_id='public_sanatoriums',
        name='Public Sanatoriums & Hygiene',
        domain=TechDomain.FINANCE,
        description='Institutional medical care; unlocks Public Sanatorium (-50% citizen mortality).',
        base_xp_required=1100.0,
        era=2,
        unlocked_buildings=['sanatorium']
    ),

    # 5. Military Doctrine & Logistics
    'standardized_drills': Technology(
        tech_id='standardized_drills',
        name='Standardized Barracks Drills',
        domain=TechDomain.MILITARY,
        description='Professional training regimen; newly recruited armies start with +1.5x base veteran XP.',
        base_xp_required=450.0,
        era=1,
        bottleneck_evaluator=_eval_war_bottleneck
    ),
    'siege_artillery': Technology(
        tech_id='siege_artillery',
        name='Blackpowder Siege Batteries',
        domain=TechDomain.MILITARY,
        description='Heavy ordnance casting; armies gain +50% combat effectiveness in siege conquest.',
        base_xp_required=1300.0,
        era=2,
        bottleneck_evaluator=_eval_war_bottleneck
    ),
}


# -----------------------------------------------------------------------------
# Innovation Manager (Global Simulation State)
# -----------------------------------------------------------------------------

@dataclass
class RoyalBounty:
    tech_id: str
    nation_name: str
    bounty_amount: float
    offered_turn: int


class InnovationSystem:
    """Orchestrator for domain practice, induced bottlenecks, bounties, and trade diffusion."""

    def __init__(self):
        # nation_name -> dict of domain -> cumulative float XP
        self.domain_experience: dict[str, dict[str, float]] = {}
        # nation_name -> set of unlocked tech_ids
        self.discovered_techs: dict[str, set[str]] = {}
        # nation_name -> dict of tech_id -> diffusion progress [0.0, 1.0]
        self.diffusion_progress: dict[str, dict[str, float]] = {}
        # list of active RoyalBounties
        self.active_bounties: list[RoyalBounty] = []
        # Event log for UI ticker and historical records
        self.discovery_log: list[dict] = []

    def get_discovered_techs(self, nation_name: str) -> set[str]:
        return self.discovered_techs.setdefault(nation_name, set())

    def has_tech(self, nation_name: str, tech_id: str) -> bool:
        return tech_id in self.get_discovered_techs(nation_name)

    def get_domain_xp(self, nation_name: str, domain: TechDomain) -> float:
        nat_xp = self.domain_experience.setdefault(nation_name, {d.value: 0.0 for d in TechDomain})
        return nat_xp.get(domain.value, 0.0)

    def post_royal_bounty(self, nation: Nation, tech_id: str, bounty_amount: float, t: int) -> bool:
        """Sovereign posts a cash prize from treasury to incentivize a breakthrough."""
        if tech_id not in TECH_CATALOG:
            return False
        if self.has_tech(nation.name, tech_id):
            return False
        treasury = nation.treasury()
        if treasury['total'] < bounty_amount:
            return False

        # Deduct bounty cash from government (held in escrow until awarded)
        nation.government.agent.cash -= bounty_amount
        bounty = RoyalBounty(tech_id=tech_id, nation_name=nation.name,
                             bounty_amount=bounty_amount, offered_turn=t)
        self.active_bounties.append(bounty)
        tech_name = TECH_CATALOG[tech_id].name
        self.discovery_log.append({
            't': t, 'event': 'BOUNTY_OFFERED',
            'message': f"{nation.name} posted a ${bounty_amount:,.0f} Royal Prize for '{tech_name}'."
        })
        return True

    def accumulate_learning_by_doing(self, tiles: list[Region], nations: list[Nation], t: int):
        """Accumulate domain practice from actual economic production and activity."""
        for n in nations:
            nat_tiles = n.tiles
            if not nat_tiles:
                continue
            nat_xp = self.domain_experience.setdefault(n.name, {d.value: 0.0 for d in TechDomain})

            # 1. Agronomy: Calibrated so ~200 food/turn yields ~3.0 XP/turn
            food_produced = sum(r.production_log.get(Goods.food, [0])[-1] if getattr(r, 'production_log', {}).get(Goods.food) else 0 for r in nat_tiles)
            nat_xp[TechDomain.AGRONOMY.value] += food_produced * 0.015

            # 2. Manufacturing: Timber and Furniture production (~2.5 XP/turn)
            wood_p = sum(r.production_log.get(Goods.wood, [0])[-1] if getattr(r, 'production_log', {}).get(Goods.wood) else 0 for r in nat_tiles)
            furn_p = sum(r.production_log.get(Goods.furniture, [0])[-1] if getattr(r, 'production_log', {}).get(Goods.furniture) else 0 for r in nat_tiles)
            nat_xp[TechDomain.MANUFACTURING.value] += (wood_p * 0.02 + furn_p * 0.035)

            # 3. Civil Engineering: Freight volume across terrain (~2.0 XP/turn)
            trade_vol = sum(sum(r.export_vol[g][-1] for g in r.export_vol if r.export_vol[g]) for r in nat_tiles)
            nat_xp[TechDomain.CIVIL_ENGINEERING.value] += trade_vol * 0.02

            # 4. Finance: Commercial transactions & tax collections (~1.5 XP/turn)
            taxes = sum(getattr(r.gov, 'tax_revenue_log', [0.0])[-1] if getattr(r.gov, 'tax_revenue_log', None) else 0.0 for r in nat_tiles)
            nat_xp[TechDomain.FINANCE.value] += (taxes * 0.01 + len(n.provinces) * 0.25)

            # 5. Military: Active soldiers & garrisons (~1.5 XP/turn)
            soldiers = sum(len(getattr(r, 'military_units', [])) * 10 for r in nat_tiles)
            nat_xp[TechDomain.MILITARY.value] += (soldiers * 0.02 + 0.2)

    def evaluate_breakthroughs(self, nations: list[Nation], t: int) -> list[dict]:
        """Check if cumulative experience and economic bottleneck pressure trigger a breakthrough."""
        events = []
        for n in nations:
            discovered = self.get_discovered_techs(n.name)
            nat_tiles = n.tiles
            if not nat_tiles:
                continue

            for tech_id, tech in TECH_CATALOG.items():
                if tech_id in discovered:
                    continue

                xp = self.get_domain_xp(n.name, tech.domain)
                # Calculate bottleneck pressure multiplier (e.g. 1.0x to 3.5x)
                pressure = tech.bottleneck_evaluator(n, nat_tiles) if tech.bottleneck_evaluator else 1.0

                # Check if a royal bounty exists for this tech (adds massive 3.5x focused acceleration)
                bounty_obj = next((b for b in self.active_bounties if b.nation_name == n.name and b.tech_id == tech_id), None)
                if bounty_obj:
                    pressure *= 3.5

                effective_xp = xp * pressure

                # Threshold check & probabilistic breakthrough
                if effective_xp >= tech.base_xp_required:
                    # Measured chance per turn: 6% baseline once threshold reached, boosted up to 35% with bounty
                    base_chance = 0.06 + 0.12 * min(1.0, (effective_xp - tech.base_xp_required) / tech.base_xp_required)
                    if bounty_obj:
                        base_chance = min(0.40, base_chance + 0.20)

                    if rand.random() < base_chance:
                        # Breakthrough achieved!
                        discovered.add(tech_id)
                        msg = f"BREAKTHROUGH: {n.name} discovered '{tech.name}' via {tech.domain.value} practice (Pressure: {pressure:.1f}x)!"
                        event = {'t': t, 'nation': n.name, 'tech_id': tech_id, 'tech_name': tech.name, 'event': 'DISCOVERY', 'message': msg}
                        events.append(event)
                        self.discovery_log.append(event)

                        # Award royal bounty if active (conserve money by paying inventing citizens)
                        if bounty_obj:
                            self.active_bounties.remove(bounty_obj)
                            # Disburse cash to the citizens of the capital tile
                            cap_tile = nat_tiles[0]
                            if cap_tile.agents:
                                share = bounty_obj.bounty_amount / len(cap_tile.agents)
                                for a in cap_tile.agents:
                                    a.cash += share
                            self.discovery_log.append({
                                't': t, 'event': 'BOUNTY_AWARDED',
                                'message': f"Royal Bounty of ${bounty_obj.bounty_amount:,.0f} awarded to {cap_tile.name} inventors for '{tech.name}'!"
                            })

        return events

    def diffuse_technologies_along_trade(self, pair_orders: list, nations: list[Nation], t: int) -> list[dict]:
        """Diffuse unlocked innovations to trading partners based on trade intimacy and bilateral treaties."""
        events = []
        from diplomacy import get_diplomacy, TreatyType
        dip = get_diplomacy()

        nations_by_name = {n.name: n for n in nations}

        for r, other in pair_orders:
            n_src = getattr(r, 'owner_nation', None)
            n_dst = getattr(other, 'owner_nation', None)
            if n_src is None or n_dst is None or n_src.name == n_dst.name:
                continue

            src_techs = self.get_discovered_techs(n_src.name)
            dst_techs = self.get_discovered_techs(n_dst.name)

            # Technologies that src has but dst does not
            diffusable = src_techs - dst_techs
            if not diffusable:
                continue

            # Trade intimacy calculation (~25-35 turns to fully diffuse)
            turn_trade = sum(r.export_val[g][-1] for g in r.export_val if r.export_vol[g])
            base_diffusion = 0.008
            if turn_trade > 25.0:
                base_diffusion += 0.012
            if dip.has_treaty(n_src.name, n_dst.name, TreatyType.TRADE_PACT.value):
                base_diffusion += 0.015

            dst_prog = self.diffusion_progress.setdefault(n_dst.name, {})

            for tech_id in diffusable:
                cur = dst_prog.get(tech_id, 0.0)
                cur += base_diffusion
                dst_prog[tech_id] = cur

                if cur >= 1.0:
                    # Fully adopted via trade diffusion!
                    dst_techs.add(tech_id)
                    dst_prog.pop(tech_id, None)
                    tech_name = TECH_CATALOG[tech_id].name
                    msg = f"TRADE DIFFUSION: {n_dst.name} adopted '{tech_name}' via trade with {n_src.name}!"
                    event = {'t': t, 'nation': n_dst.name, 'tech_id': tech_id, 'tech_name': tech_name, 'event': 'DIFFUSION', 'message': msg}
                    events.append(event)
                    self.discovery_log.append(event)

        return events

    def step(self, tiles: list[Region], nations: list[Nation], pair_orders: list, t: int) -> list[dict]:
        """Advance one turn of learning-by-doing, induced breakthroughs, and trade diffusion."""
        self.accumulate_learning_by_doing(tiles, nations, t)
        discovery_events = self.evaluate_breakthroughs(nations, t)
        diffusion_events = self.diffuse_technologies_along_trade(pair_orders, nations, t)
        return discovery_events + diffusion_events


_INNOVATION_SYSTEM: InnovationSystem | None = None

def get_innovation_system() -> InnovationSystem:
    global _INNOVATION_SYSTEM
    if _INNOVATION_SYSTEM is None:
        _INNOVATION_SYSTEM = InnovationSystem()
    return _INNOVATION_SYSTEM

def step_innovation(tiles: list[Region], nations: list[Nation], pair_orders: list, t: int) -> list[dict]:
    return get_innovation_system().step(tiles, nations, pair_orders, t)
