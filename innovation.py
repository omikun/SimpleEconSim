"""
innovation.py — Induced Innovation, Learning-by-Doing & Technology Diffusion Engine for Call of Capital.

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


from tile_resources import TileResource, get_nation_resources

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
    required_resources: list[TileResource] = field(default_factory=list)
    required_techs: list[str] = field(default_factory=list)
    unlocked_buildings: list[str] = field(default_factory=list)
    production_modifiers: dict[str, float] = field(default_factory=dict)
    bottleneck_evaluator: Callable[[Nation, list[Region]], float] | None = None


# -----------------------------------------------------------------------------
# Bottleneck Pressure Calculators (Real-World Economic Incentives)
# -----------------------------------------------------------------------------

def _eval_food_bottleneck(nation: Nation, tiles: list[Region], *, evidence=None) -> float:
    """High food price inflation & hunger accelerate agricultural breakthroughs."""
    if not tiles:
        if evidence is not None:
            evidence.update(model='food', no_tiles=True)
        return 1.0
    prices = [{'tile': getattr(r, 'name', 'unknown'),
               'price': r.recipes.get(Goods.food, {}).get('price', 1.0)} for r in tiles]
    avg_food_price = sum(row['price'] for row in prices) / len(tiles)
    hungry_agents = [{'tile': getattr(r, 'name', 'unknown'), 'agent_id': getattr(a, 'id', None)}
                     for r in tiles for a in r.agents
                     if getattr(a, 'hungry_steps', 0) > 0]
    hungry_count = len(hungry_agents)
    if evidence is not None:
        evidence.update(model='food', tile_food_prices=prices,
                        hungry_agents=hungry_agents)
    multiplier = 1.0
    if avg_food_price > 1.8:
        multiplier += (avg_food_price - 1.8) * 1.5
    if hungry_count > 10:
        multiplier += min(3.0, hungry_count * 0.10)
    return min(4.0, multiplier)


def _eval_mountain_bottleneck(nation: Nation, tiles: list[Region], *, evidence=None) -> float:
    """High elevation, impassable cliffs, and mountain borders accelerate blasting & tunneling."""
    if not tiles:
        if evidence is not None:
            evidence.update(model='mountain', no_tiles=True)
        return 1.0
    high_tile_names = [getattr(r, 'name', 'unknown') for r in tiles
                       if getattr(r, 'elevation', 0.0) >= 0.50]
    high_tiles = len(high_tile_names)
    blocked_edges = 0
    blocked_adjacencies = []
    from terrain_edges import get_edge_manager
    em = get_edge_manager()
    if em:
        for r in tiles:
            for other_name in getattr(r, 'all_adjacent_names', []):
                edge = em.get_edge(r.name, other_name)
                if edge and not edge.passable:
                    blocked_edges += 1
                    blocked_adjacencies.append([r.name, other_name])
    if evidence is not None:
        evidence.update(model='mountain', high_tiles=high_tile_names,
                        blocked_adjacencies=blocked_adjacencies,
                        counting_rule='each blocked tile adjacency, including repeated undirected edges')
    multiplier = 1.0 + (high_tiles * 0.4) + (blocked_edges * 0.3)
    return min(4.5, multiplier)


def _eval_wage_labor_bottleneck(nation: Nation, tiles: list[Region], *, evidence=None) -> float:
    """High worker wages and labor shortages accelerate mechanization & labor-saving tools."""
    if not tiles:
        if evidence is not None:
            evidence.update(model='wages', no_tiles=True)
        return 1.0
    wage_rows = [{'tile': getattr(r, 'name', 'unknown'),
                 'agent_id': getattr(a, 'id', None), 'wage': a.wage}
                 for r in tiles for a in getattr(r, 'agents', [])
                 if hasattr(a, 'wage') and a.wage > 0]
    wages = [row['wage'] for row in wage_rows]
    avg_wage = (sum(wages) / len(wages)) if wages else 1.0
    if evidence is not None:
        evidence.update(model='wages', positive_wages=wage_rows,
                        eligibility_rule='all agents with a positive wage field')
    multiplier = 1.0
    if avg_wage > 2.0:
        multiplier += (avg_wage - 2.0) * 1.2
    return min(3.5, multiplier)


def _eval_war_bottleneck(nation: Nation, tiles: list[Region], *, evidence=None) -> float:
    """Active wars and military threats accelerate military doctrine & supply logistics."""
    from diplomacy import get_diplomacy
    dip = get_diplomacy()
    wars = [w for w in dip.active_wars if nation.name in w]
    active_wars = len(wars)
    if evidence is not None:
        evidence.update(model='war', active_wars=[list(w) for w in wars])
    if active_wars > 0:
        return 2.5 + active_wars * 1.0
    return 1.0


# -----------------------------------------------------------------------------
# 16-Technology Multi-Era Catalog (Medieval -> Modern)
# -----------------------------------------------------------------------------

TECH_CATALOG: dict[str, Technology] = {
    # =========================================================================
    # ERA I: MEDIEVAL & FEUDAL (Era 1)
    # =========================================================================
    'crop_rotation': Technology(
        tech_id='crop_rotation',
        name='Four-Field Crop Rotation',
        domain=TechDomain.AGRONOMY,
        description='Restores soil fertility naturally, granting +25% baseline food productivity.',
        base_xp_required=350.0,
        era=1,
        required_resources=[TileResource.ARABLE_SILT],
        production_modifiers={Goods.food.value: 1.25},
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'bloomery_iron': Technology(
        tech_id='bloomery_iron',
        name='Bloomery Iron Smelting',
        domain=TechDomain.MANUFACTURING,
        description='Smelts mountain iron with hardwood charcoal; unlocks durable tools (+25% labor output).',
        base_xp_required=380.0,
        era=1,
        required_resources=[TileResource.IRON_ORE, TileResource.TIMBER],
        production_modifiers={Goods.wood.value: 1.25},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),
    'fluvial_watermills': Technology(
        tech_id='fluvial_watermills',
        name='Fluvial Watermills & Gristmills',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Harnesses river kinetic flow; unlocks Mechanized Sawmills & Fluvial River Bridges.',
        base_xp_required=400.0,
        era=1,
        required_resources=[TileResource.TIMBER],
        unlocked_buildings=['sawmill', 'river_bridge'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'guild_standardization': Technology(
        tech_id='guild_standardization',
        name='Standardized Guild Workshops',
        domain=TechDomain.MANUFACTURING,
        description='Specialized artisan joinery; unlocks Artisan Workshop & Guildhall (+30% furniture).',
        base_xp_required=450.0,
        era=1,
        required_resources=[TileResource.TIMBER],
        unlocked_buildings=['workshop'],
        production_modifiers={Goods.furniture.value: 1.30},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),

    # =========================================================================
    # ERA II: RENAISSANCE & COMMERCIAL (Era 2)
    # =========================================================================
    'gunpowder_blasting': Technology(
        tech_id='gunpowder_blasting',
        name='Gunpowder Rock Blasting',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Blasts through sheer granite cliffs; unlocks Alpine Mountain Pass Roads.',
        base_xp_required=650.0,
        era=2,
        required_resources=[TileResource.IRON_ORE],
        required_techs=['bloomery_iron'],
        unlocked_buildings=['mountain_pass'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'deep_navigation': Technology(
        tech_id='deep_navigation',
        name='Caravel Galleons & Deep Harbors',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Oceanic navigation and heavy timbers; unlocks Paved Highways & Maritime Harbors.',
        base_xp_required=700.0,
        era=2,
        required_resources=[TileResource.TIMBER, TileResource.PASTURE_FLAX],
        unlocked_buildings=['paved_road'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'turnpike_trusts': Technology(
        tech_id='turnpike_trusts',
        name='Turnpike Trusts & Macadamized Roads',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Toll-funded crushed stone highways reducing overland transport friction by 50% and boosting farm rent collection.',
        base_xp_required=620.0,
        era=2,
        required_resources=[TileResource.TIMBER],
        unlocked_buildings=['turnpike_road'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'barge_canals': Technology(
        tech_id='barge_canals',
        name='Contour Barge Canals & Pound Locks',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Inland water navigation networks linking coal, wool, and grain basins to urban ports with 75% freight cost reduction.',
        base_xp_required=720.0,
        era=2,
        required_resources=[TileResource.TIMBER],
        unlocked_buildings=['barge_canal'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'mechanized_textiles': Technology(
        tech_id='mechanized_textiles',
        name='Fly Shuttle & Mechanized Wool Carding',
        domain=TechDomain.MANUFACTURING,
        description='Centralizes spinning and weaving into textile manufactories, sparking soaring commercial demand for wool.',
        base_xp_required=680.0,
        era=2,
        required_resources=[TileResource.TIMBER, TileResource.PASTURE_FLAX],
        unlocked_buildings=['textile_mill'],
        production_modifiers={Goods.cloth.value: 1.40},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),
    'siege_artillery': Technology(
        tech_id='siege_artillery',
        name='Blackpowder Siege Batteries',
        domain=TechDomain.MILITARY,
        description='Standardized cannon casting; armies gain +50% combat power in siege conquest.',
        base_xp_required=750.0,
        era=2,
        required_resources=[TileResource.IRON_ORE],
        required_techs=['gunpowder_blasting'],
        bottleneck_evaluator=_eval_war_bottleneck
    ),
    'double_entry_bookkeeping': Technology(
        tech_id='double_entry_bookkeeping',
        name='Double-Entry Ledger Banking',
        domain=TechDomain.FINANCE,
        description='Improves commercial transparency, reducing bank loan defaults and liquidity panics.',
        base_xp_required=600.0,
        era=2,
    ),
    'municipal_trunk_sewers': Technology(
        tech_id='municipal_trunk_sewers',
        name='Brick Underground Trunk Sewers',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Underground brick drainage that flushes urban sewage away from drinking wells, reducing epidemics.',
        base_xp_required=680.0,
        era=2,
        unlocked_buildings=['trunk_sewer'],
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'germ_theory_antisepsis': Technology(
        tech_id='germ_theory_antisepsis',
        name='Germ Theory & Antiseptic Sanitation',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Microbial disease identification and carbolic antisepsis; cuts waterborne cholera transmission by 65% and reduces medical treatment costs.',
        base_xp_required=720.0,
        era=2,
        unlocked_buildings=['municipal_clinic'],
        bottleneck_evaluator=_eval_food_bottleneck
    ),

    # =========================================================================
    # ERA III: STEAM & INDUSTRIAL REVOLUTION (Era 3)
    # =========================================================================
    'coal_coking': Technology(
        tech_id='coal_coking',
        name='Coal Coking & Blast Furnaces',
        domain=TechDomain.MANUFACTURING,
        description='Replaces scarce charcoal with coal; multiplies metal smelting output by 3x.',
        base_xp_required=950.0,
        era=3,
        required_resources=[TileResource.COAL_SEAM, TileResource.IRON_ORE],
        required_techs=['bloomery_iron'],
        production_modifiers={Goods.wood.value: 1.40},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),
    'steam_engines': Technology(
        tech_id='steam_engines',
        name='Watt Piston Steam Engines',
        domain=TechDomain.MANUFACTURING,
        description='Harnesses pressurized coal steam; unlocks Steam Factories (+50% factory output).',
        base_xp_required=1100.0,
        era=3,
        required_resources=[TileResource.COAL_SEAM, TileResource.IRON_ORE],
        required_techs=['coal_coking'],
        production_modifiers={Goods.furniture.value: 1.50},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),
    'bessemer_steel': Technology(
        tech_id='bessemer_steel',
        name='Bessemer Structural Steel & Rail',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Mass steel decarbonization; slashes land trade friction across all routes by 70%.',
        base_xp_required=1250.0,
        era=3,
        required_resources=[TileResource.COAL_SEAM, TileResource.IRON_ORE],
        required_techs=['steam_engines'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'mechanized_looms': Technology(
        tech_id='mechanized_looms',
        name='Mechanized Steam Loom Mills',
        domain=TechDomain.MANUFACTURING,
        description='Continuous steam-powered weaving; multiplies textile and garment output by 4x.',
        base_xp_required=1050.0,
        era=3,
        required_resources=[TileResource.PASTURE_FLAX, TileResource.COAL_SEAM],
        required_techs=['steam_engines'],
        production_modifiers={Goods.furniture.value: 1.40},
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),
    'chemical_pesticides': Technology(
        tech_id='chemical_pesticides',
        name='Synthetic Chemical Pesticides',
        domain=TechDomain.AGRONOMY,
        description='Synthetic arsenical and organophosphate sprays protecting monoculture crops (+40% harvest), but poisoning soil and workers.',
        base_xp_required=1000.0,
        era=3,
        required_resources=[TileResource.ARABLE_SILT],
        production_modifiers={Goods.food.value: 1.40},
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'coal_scrubbers': Technology(
        tech_id='coal_scrubbers',
        name='Wet Coal Smoke Scrubbers',
        domain=TechDomain.MANUFACTURING,
        description='Water-spray condensation towers scrubbing 70% of sulfur dioxide and soot from smokestacks into concentrated chemical sludge.',
        base_xp_required=1150.0,
        era=3,
        required_resources=[TileResource.COAL_SEAM, TileResource.IRON_ORE],
        required_techs=['steam_engines'],
        unlocked_buildings=['smoke_scrubber'],
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),
    'water_filtration': Technology(
        tech_id='water_filtration',
        name='Slow Sand Municipal Water Filtration',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Sand and gravel biological filtration beds purifying provincial municipal water supplies from typhoid and industrial waste.',
        base_xp_required=1100.0,
        era=3,
        unlocked_buildings=['water_filtration_plant'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'agroecology_rotation': Technology(
        tech_id='agroecology_rotation',
        name='Agroecological Fallow & Composting',
        domain=TechDomain.AGRONOMY,
        description='Complex multi-field legume composting that fully regenerates depleted soil fertility without synthetic nitrate runoff.',
        base_xp_required=1200.0,
        era=3,
        required_resources=[TileResource.ARABLE_SILT],
        required_techs=['crop_rotation'],
        unlocked_buildings=['soil_conservation_reserve'],
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'pharmaceutical_chemistry': Technology(
        tech_id='pharmaceutical_chemistry',
        name='Synthetic Pharmacology & Chemotherapy',
        domain=TechDomain.MANUFACTURING,
        description='Chemical synthesis of antidotes and antibiotics; raises medical cure success rate to 95% and neutralizes chemical pesticide toxicity.',
        base_xp_required=1250.0,
        era=3,
        required_resources=[TileResource.COAL_SEAM],
        required_techs=['germ_theory_antisepsis'],
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'mineral_nitrates': Technology(
        tech_id='mineral_nitrates',
        name='Guano & Mineral Nitrate Logistics',
        domain=TechDomain.AGRONOMY,
        description='Extraction and bulk maritime transshipment of Peruvian guano and Atacama sodium nitrate, unlocking +75% crop yields but creating vulnerability to naval blockades.',
        base_xp_required=1150.0,
        era=3,
        required_techs=['crop_rotation'],
        bottleneck_evaluator=_eval_food_bottleneck
    ),

    # =========================================================================
    # ERA IV: PETROLEUM, ELECTRIC & MODERN AGE (Era 4)
    # =========================================================================
    'petroleum_refining': Technology(
        tech_id='petroleum_refining',
        name='Petroleum Refining & Diesel',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='Hydrocarbon cracking into diesel & asphalt; enables motorized freight transport.',
        base_xp_required=1500.0,
        era=4,
        required_resources=[TileResource.CRUDE_PETROLEUM],
        required_techs=['bessemer_steel'],
        bottleneck_evaluator=_eval_mountain_bottleneck
    ),
    'dynamo_electrification': Technology(
        tech_id='dynamo_electrification',
        name='Dynamo Power Grids',
        domain=TechDomain.CIVIL_ENGINEERING,
        description='High-voltage regional transmission; unlocks 24/7 factory shifts (+35% national GDP).',
        base_xp_required=1650.0,
        era=4,
        required_resources=[TileResource.RARE_MINERALS, TileResource.COAL_SEAM],
        required_techs=['bessemer_steel'],
        bottleneck_evaluator=_eval_wage_labor_bottleneck
    ),
    'synthetic_fertilizers': Technology(
        tech_id='synthetic_fertilizers',
        name='Haber-Bosch Synthetic Fertilizers',
        domain=TechDomain.AGRONOMY,
        description='Fixes atmospheric nitrogen using hydrocarbons; doubles food harvests (+100%), but dilutes food nutritional density and triggers river nitrate runoff.',
        base_xp_required=1400.0,
        era=4,
        required_resources=[TileResource.CRUDE_PETROLEUM, TileResource.ARABLE_SILT],
        required_techs=['petroleum_refining'],
        production_modifiers={Goods.food.value: 2.00},
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'biological_pest_control': Technology(
        tech_id='biological_pest_control',
        name='Integrated Biological Pest Management',
        domain=TechDomain.AGRONOMY,
        description='Beneficial insect ecology and pheromone disruption replacing toxic chemical insecticides, eliminating farmworker toxicity.',
        base_xp_required=1550.0,
        era=4,
        required_resources=[TileResource.ARABLE_SILT],
        required_techs=['chemical_pesticides'],
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'universal_healthcare_system': Technology(
        tech_id='universal_healthcare_system',
        name='Universal Public Healthcare Coverage',
        domain=TechDomain.FINANCE,
        description='State-administered health system guaranteeing public treatment of all epidemics, reducing treatment cost by 30% and eliminating out-of-pocket bankruptcies.',
        base_xp_required=1700.0,
        era=4,
        required_techs=['pharmaceutical_chemistry'],
        bottleneck_evaluator=_eval_food_bottleneck
    ),
    'microelectronics': Technology(
        tech_id='microelectronics',
        name='Silicon Microelectronics & Computing',
        domain=TechDomain.FINANCE,
        description='Semiconductor transistor logic; automated market clearing and zero administrative drag.',
        base_xp_required=1800.0,
        era=4,
        required_resources=[TileResource.RARE_MINERALS],
        required_techs=['dynamo_electrification'],
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


def _learning_sample(tile, field_name, good=None, *, owner=...):
    owner = tile if owner is ... else owner
    series = getattr(owner, field_name, {} if good is not None else ())
    history = series.get(good, ()) if good is not None else series
    return {'tile': tile.name, 'source_field': field_name,
            'good': getattr(good, 'name', str(good)) if good is not None else None,
            'quantity': history[-1] if history else 0,
            'sample_index': len(history) - 1 if history else None,
            'source_available': bool(history),
            'source_metric_id': 'goods.production' if field_name == 'production_log' else None}


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
        from innovation_trace import record_learning

        for n in nations:
            nat_tiles = n.tiles
            if not nat_tiles:
                continue
            nat_xp = self.domain_experience.setdefault(n.name, {})
            for d in TechDomain:
                nat_xp.setdefault(d.value, 0.0)
            opening_xp = dict(nat_xp)

            # 1. Agronomy: Calibrated so ~200 food/turn yields ~3.0 XP/turn
            food_samples = [_learning_sample(r, 'production_log', Goods.food) for r in nat_tiles]
            food_produced = sum(row['quantity'] for row in food_samples)
            nat_xp[TechDomain.AGRONOMY.value] += food_produced * 0.015
            record_learning(n, TechDomain.AGRONOMY.value,
                            opening_xp[TechDomain.AGRONOMY.value],
                            nat_xp[TechDomain.AGRONOMY.value],
                            [{'quantity': food_produced, 'coefficient': 0.015,
                              'source': 'food_output', 'tile_samples': food_samples}], turn=t)

            # 2. Manufacturing: Timber and Furniture production (~2.5 XP/turn)
            wood_samples = [_learning_sample(r, 'production_log', Goods.wood) for r in nat_tiles]
            furniture_samples = [_learning_sample(r, 'production_log', Goods.furniture) for r in nat_tiles]
            wood_p = sum(row['quantity'] for row in wood_samples)
            furn_p = sum(row['quantity'] for row in furniture_samples)
            nat_xp[TechDomain.MANUFACTURING.value] += (wood_p * 0.02 + furn_p * 0.035)
            record_learning(n, TechDomain.MANUFACTURING.value,
                            opening_xp[TechDomain.MANUFACTURING.value],
                            nat_xp[TechDomain.MANUFACTURING.value],
                            [{'quantity': wood_p, 'coefficient': 0.02,
                              'source': 'wood_output', 'tile_samples': wood_samples},
                             {'quantity': furn_p, 'coefficient': 0.035,
                              'source': 'furniture_output', 'tile_samples': furniture_samples}], turn=t)

            # 3. Civil Engineering: Freight volume across terrain (~2.0 XP/turn)
            exports_by_tile = [[_learning_sample(r, 'export_vol', good)
                                for good in r.export_vol if r.export_vol[good]] for r in nat_tiles]
            export_samples = [row for rows in exports_by_tile for row in rows]
            trade_vol = sum(sum(row['quantity'] for row in rows) for rows in exports_by_tile)
            nat_xp[TechDomain.CIVIL_ENGINEERING.value] += trade_vol * 0.02
            record_learning(n, TechDomain.CIVIL_ENGINEERING.value,
                            opening_xp[TechDomain.CIVIL_ENGINEERING.value],
                            nat_xp[TechDomain.CIVIL_ENGINEERING.value],
                            [{'quantity': trade_vol, 'coefficient': 0.02,
                              'source': 'export_units', 'tile_samples': export_samples}], turn=t)

            # 4. Finance: Commercial transactions & tax collections (~1.5 XP/turn)
            tax_samples = [_learning_sample(r, 'tax_revenue_log', owner=r.gov) for r in nat_tiles]
            taxes = sum(row['quantity'] for row in tax_samples)
            nat_xp[TechDomain.FINANCE.value] += (taxes * 0.01 + len(n.provinces) * 0.25)
            record_learning(n, TechDomain.FINANCE.value,
                            opening_xp[TechDomain.FINANCE.value], nat_xp[TechDomain.FINANCE.value],
                            [{'quantity': taxes, 'coefficient': 0.01,
                              'source': 'legacy_tax_revenue_log', 'tile_samples': tax_samples},
                             {'quantity': len(n.provinces), 'coefficient': 0.25,
                              'source': 'province_count'}], turn=t)

            # 5. Military: Active soldiers & garrisons (~1.5 XP/turn)
            military_samples = [
                {'tile': r.name, 'quantity': len(getattr(r, 'military_units', [])) * 10,
                 'unit_ids': [getattr(unit, 'id', None) for unit in getattr(r, 'military_units', [])],
                 'counting_rule': 'ten soldier-equivalents per unit object; ignores unit strength'}
                for r in nat_tiles]
            soldiers = sum(row['quantity'] for row in military_samples)
            nat_xp[TechDomain.MILITARY.value] += (soldiers * 0.02 + 0.2)
            record_learning(n, TechDomain.MILITARY.value,
                            opening_xp[TechDomain.MILITARY.value], nat_xp[TechDomain.MILITARY.value],
                            [{'quantity': soldiers, 'coefficient': 0.02,
                              'source': 'soldier_equivalents', 'tile_samples': military_samples}],
                            turn=t, fixed_increment=0.2)

    def evaluate_breakthroughs(self, nations: list[Nation], t: int) -> list[dict]:
        """Check if cumulative experience and economic bottleneck pressure trigger a breakthrough."""
        from innovation_trace import (emit_innovation, latest_innovation_event,
                                      record_pressure, record_research_gate,
                                      record_technology, trace_region)

        events = []
        for n in nations:
            discovered = self.get_discovered_techs(n.name)
            nat_tiles = n.tiles
            if not nat_tiles:
                fallback = next((trace_region(other) for other in nations
                                 if trace_region(other) is not None), None)
                record_research_gate(n, '*', t, 'no_territory', region_override=fallback)
                continue

            for tech_id, tech in TECH_CATALOG.items():
                if tech_id in discovered:
                    record_research_gate(n, tech_id, t, 'already_known')
                    continue

                # 1. Technology prerequisites check
                missing_techs = [req for req in tech.required_techs if req not in discovered]
                if missing_techs:
                    record_research_gate(n, tech_id, t, 'missing_prerequisites',
                                         missing_technologies=missing_techs,
                                         resource_gate='not_evaluated_after_prerequisite_gate')
                    continue

                # 2. Natural resource prerequisites check (domestic ownership or trade imports)
                nat_res = get_nation_resources(n, nat_tiles)
                missing_resources = [res for res in tech.required_resources if res not in nat_res]
                if missing_resources:
                    record_research_gate(
                        n, tech_id, t, 'missing_resources',
                        available_resources=sorted(getattr(res, 'value', str(res)) for res in nat_res),
                        missing_resources=[getattr(res, 'value', str(res)) for res in missing_resources])
                    continue

                xp = self.get_domain_xp(n.name, tech.domain)
                # Calculate bottleneck pressure multiplier (e.g. 1.0x to 3.5x)
                evaluator = tech.bottleneck_evaluator
                pressure_inputs = {}
                known_formula = evaluator is None or evaluator in (
                    _eval_food_bottleneck, _eval_mountain_bottleneck,
                    _eval_wage_labor_bottleneck, _eval_war_bottleneck)
                if evaluator is None:
                    pressure = 1.0
                    pressure_inputs['model'] = 'none'
                elif known_formula:
                    pressure = evaluator(n, nat_tiles, evidence=pressure_inputs)
                else:
                    pressure = evaluator(n, nat_tiles)
                    pressure_inputs.update(model='custom',
                                           evaluator=getattr(evaluator, '__name__', 'custom'),
                                           evidence_status='callback_result_only')
                raw_pressure = pressure
                pressure_trace_id = record_pressure(
                    n, tech_id, t, raw_pressure, pressure_inputs, known_formula=known_formula)

                # Check if a royal bounty exists for this tech (adds massive 3.5x focused acceleration)
                bounty_obj = next((b for b in self.active_bounties if b.nation_name == n.name and b.tech_id == tech_id), None)
                if bounty_obj:
                    pressure *= 3.5

                effective_xp = xp * pressure

                # Threshold check & probabilistic breakthrough
                base_chance = None
                draw = None
                success = False
                if effective_xp >= tech.base_xp_required:
                    # Measured chance per turn: 6% baseline once threshold reached, boosted up to 35% with bounty
                    base_chance = 0.06 + 0.12 * min(1.0, (effective_xp - tech.base_xp_required) / tech.base_xp_required)
                    if bounty_obj:
                        base_chance = min(0.40, base_chance + 0.20)

                    draw = rand.random()
                    success = draw < base_chance
                learning_id = latest_innovation_event(
                    n, 'innovation.domain_experience', domain=tech.domain.value)
                evaluation_id = emit_innovation(
                    n, kind='innovation_breakthrough_evaluation', record_class='calculation',
                    subject_fields={'tech_id': tech_id}, metric_id='innovation.breakthrough',
                    unit='boolean', after=int(success),
                    formula_id='innovation.breakthrough_draw.v1',
                    inputs={'turn': int(t), 'domain': tech.domain.value,
                            'domain_experience': xp, 'bottleneck_multiplier': raw_pressure,
                            'bounty_active': bounty_obj is not None,
                            'bounty_amount': bounty_obj.bounty_amount if bounty_obj else None,
                            'effective_experience': effective_xp,
                            'required_experience': tech.base_xp_required,
                            'threshold_met': effective_xp >= tech.base_xp_required,
                            'chance': base_chance, 'random_draw': draw,
                            'available_resources': sorted(getattr(res, 'value', str(res)) for res in nat_res),
                            'required_technologies': list(tech.required_techs),
                            'reason': ('discovered' if success else 'breakthrough_roll_failed'
                                       if draw is not None else 'experience_below_threshold')},
                    cause_event_ids=[event_id for event_id in (learning_id, pressure_trace_id)
                                     if event_id is not None] or None)
                if success:
                    discovered.add(tech_id)
                    record_technology(
                        n, tech_id, t, 'domestic_breakthrough',
                        unlocked_buildings=list(tech.unlocked_buildings),
                        production_modifiers={str(good): value for good, value in tech.production_modifiers.items()},
                        cause_event_ids=([evaluation_id] if evaluation_id else None))
                    msg = f"BREAKTHROUGH: {n.name} discovered '{tech.name}' via {tech.domain.value} practice (Pressure: {pressure:.1f}x)!"
                    event = {'t': t, 'nation': n.name, 'tech_id': tech_id, 'tech_name': tech.name, 'event': 'DISCOVERY', 'message': msg}
                    events.append(event)
                    self.discovery_log.append(event)

                    if bounty_obj:
                        self.active_bounties.remove(bounty_obj)
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
        from innovation_trace import (emit_innovation, latest_innovation_event,
                                      record_diffusion_gate, record_technology)
        dip = get_diplomacy()

        nations_by_name = {n.name: n for n in nations}

        for r, other in pair_orders:
            n_src = getattr(r, 'owner_nation', None)
            n_dst = getattr(other, 'owner_nation', None)
            if n_src is None or n_dst is None or n_src.name == n_dst.name:
                anchor = n_dst if n_dst is not None else n_src
                if anchor is not None:
                    record_diffusion_gate(
                        anchor, t, 'missing_owner' if n_src is None or n_dst is None else 'same_nation',
                        r.name, other.name)
                continue

            src_techs = self.get_discovered_techs(n_src.name)
            dst_techs = self.get_discovered_techs(n_dst.name)

            # Technologies that src has but dst does not
            diffusable = src_techs - dst_techs
            if not diffusable:
                record_diffusion_gate(n_dst, t, 'no_unknown_source_technologies', r.name, other.name)
                continue

            # Trade intimacy calculation (~25-35 turns to fully diffuse)
            trade_samples = [{'good': getattr(g, 'name', str(g)),
                              'value': r.export_val[g][-1],
                              'sample_index': len(r.export_val[g]) - 1}
                             for g in r.export_val if r.export_vol[g]]
            turn_trade = sum(sample['value'] for sample in trade_samples)
            base_diffusion = 0.008
            if turn_trade > 25.0:
                base_diffusion += 0.012
            trade_pact = dip.has_treaty(n_src.name, n_dst.name, TreatyType.TRADE_PACT.value)
            if trade_pact:
                base_diffusion += 0.015

            dst_prog = self.diffusion_progress.setdefault(n_dst.name, {})

            for tech_id in diffusable:
                cur = dst_prog.get(tech_id, 0.0)
                prior_progress = cur
                cur += base_diffusion
                dst_prog[tech_id] = cur
                previous_id = latest_innovation_event(n_dst, 'innovation.diffusion_progress', tech_id=tech_id)
                progress_id = emit_innovation(
                    n_dst, kind='innovation_trade_diffusion_update', record_class='calculation',
                    subject_fields={'tech_id': tech_id}, metric_id='innovation.diffusion_progress',
                    unit='progress_fraction', before=prior_progress, after=cur,
                    formula_id='innovation.trade_diffusion.v1',
                    inputs={'turn': int(t), 'prior_progress': prior_progress,
                            'source_nation': n_src.name, 'source_tile': r.name,
                            'destination_tile': other.name, 'source_trade_value': turn_trade,
                            'source_trade_samples': trade_samples, 'trade_pact': trade_pact,
                            'progress_increment': base_diffusion, 'adoption_threshold': 1.0,
                            'source_knows_technology': tech_id in src_techs,
                            'prerequisite_resource_checks': 'not_applied_to_trade_diffusion',
                            'zero_trade_rule': 'positive baseline diffusion remains active'},
                    cause_event_ids=([previous_id] if previous_id else None))

                if cur >= 1.0:
                    # Fully adopted via trade diffusion!
                    dst_techs.add(tech_id)
                    dst_prog.pop(tech_id, None)
                    adoption_id = record_technology(
                        n_dst, tech_id, t, 'trade_diffusion', source_nation=n_src.name,
                        source_tile=r.name, destination_tile=other.name,
                        cause_event_ids=([progress_id] if progress_id else None))
                    emit_innovation(
                        n_dst, kind='innovation_diffusion_progress_removed', record_class='calculation',
                        subject_fields={'tech_id': tech_id}, metric_id='innovation.diffusion_progress',
                        unit='progress_fraction', before=cur, after=0.0,
                        formula_id='innovation.diffusion_adoption_reset.v1',
                        inputs={'turn': int(t), 'adopted': True,
                                'removed_progress': cur, 'reason': 'technology_now_known'},
                        cause_event_ids=[event_id for event_id in (progress_id, adoption_id)
                                         if event_id is not None] or None)
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
