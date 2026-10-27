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
from treasury_trace import begin_public_change, finish_public_change
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


class ComplexityClass(int, Enum):
    CLASS_I_LOW = 1       # Medieval / Early Modern: Steal up to Tier 3 (85 XP)
    CLASS_II_MEDIUM = 2   # 1st Industrial Rev: Steal up to Tier 3 (65 XP)
    CLASS_III_HIGH = 3    # 2nd Industrial / Machine Age: Steal up to Tier 2 (50 XP)
    CLASS_IV_EXTREME = 4  # Information / Atomic Age: Steal up to Tier 2 (30 XP)


# Complexity Class -> (max_steal_tier, max_steal_xp_cap)
COMPLEXITY_STEAL_CAPS: dict[int, tuple[int, float]] = {
    1: (3, 85.0),
    2: (3, 65.0),
    3: (2, 50.0),
    4: (2, 30.0),
}

TIER_XP_THRESHOLDS: dict[int, float] = {
    1: 1.0,
    2: 25.0,
    3: 60.0,
    4: 90.0,
}


@dataclass
class DiscoveryAvenue:
    avenue_id: str
    name: str
    crisis_label: str
    prototype_building: str
    required_resources: list[TileResource] = field(default_factory=list)


_HISTORICAL_AVENUE_OVERRIDES: dict[str, dict] = {
    'gunpowder_blasting': {
        'complexity_class': 1,
        'incumbent_guild': 'Feudal Knight & Crossbow Guilds',
        'protectionist_law': 'Chivalric Arms Monopoly Edict',
        'avenues': [
            DiscoveryAvenue('alchemy', 'Daoist Elixir & Kiln Alchemy', 'Court Mineral Calcination Patronage', 'alchemical_kiln', [TileResource.IRON_ORE]),
            DiscoveryAvenue('siege', 'Frontier Siege Warfare', 'Stone Castle Fortification Stalemate', 'bronze_mortar', [TileResource.IRON_ORE]),
            DiscoveryAvenue('mining', 'Hard-Rock Mining & Canal Blasting', 'Granite Mountain Pass Bottleneck', 'mountain_pass', [TileResource.IRON_ORE]),
        ],
    },
    'steam_engines': {
        'complexity_class': 2,
        'incumbent_guild': 'Waterwheel Millers & Hand-Loom Guilds',
        'protectionist_law': 'Guild Charter Urban Steam Ban',
        'avenues': [
            DiscoveryAvenue('pit', 'Deep Pit Mine Drainage (Newcomen Path)', 'Flooded Deep Coal/Iron Mine Shafts', 'pithead_pump', [TileResource.COAL_SEAM, TileResource.IRON_ORE]),
            DiscoveryAvenue('bellows', 'Blast Furnace Bellows (Song/Ironworks Path)', 'Frozen / Low-Flow Rivers Halt Iron Smelting', 'steam_blast_furnace', [TileResource.COAL_SEAM, TileResource.IRON_ORE]),
            DiscoveryAvenue('polder', 'Civic Polder & Drydock Pumping (Dutch Path)', 'Coastal Marsh Flooding & Drydock Sluicing', 'hydraulic_sluice_pump', [TileResource.COAL_SEAM]),
            DiscoveryAvenue('brine', 'Brine & Sugar Pressure Boilers (Sichuan Path)', 'Evaporation Fuel Crisis in Salt/Sugar Vats', 'condensing_boiler', [TileResource.COAL_SEAM]),
            DiscoveryAvenue('river', 'Upstream River Barge Hauling', 'Strong Downstream Current Blocks Heavy Freight', 'paddle_winch_barge', [TileResource.COAL_SEAM]),
        ],
    },
    'petroleum_refining': {
        'complexity_class': 3,
        'incumbent_guild': 'Coal-Steam Railway & Turnpike Barons',
        'protectionist_law': "The Locomotive 'Red Flag' Act of 1865",
        'avenues': [
            DiscoveryAvenue('kerosene', 'Kerosene Lighting Byproduct (US/Baku Path)', 'Whale-Oil Scarcity & Volatile Gasoline Surplus', 'stationary_petrol_engine', [TileResource.CRUDE_PETROLEUM]),
            DiscoveryAvenue('tractor', 'Continental Steppe Farm Mechanization', 'Heavy Steam Tractors Sink in Farmland Mud', 'farm_tractor_works', [TileResource.CRUDE_PETROLEUM]),
            DiscoveryAvenue('towngas', 'Municipal Town-Gas Workshop Engine (Otto Path)', 'Small Workshops Cannot Afford Steam Boilermen', 'four_stroke_workshop', [TileResource.CRUDE_PETROLEUM]),
        ],
    },
    'microelectronics': {
        'complexity_class': 4,
        'incumbent_guild': 'Vacuum-Tube & Electromechanical Telecom Cartel',
        'protectionist_law': 'Telecom Monopoly Procurement Mandate',
        'avenues': [
            DiscoveryAvenue('aerospace', 'Aerospace & Missile Guidance Miniaturization', 'Vacuum Tubes Too Heavy for High-Speed Guidance', 'planar_transistor_lab', [TileResource.RARE_MINERALS]),
            DiscoveryAvenue('consumer', 'Precision Optics & Consumer Export Hub', 'Resource-Poor State Needs High-Margin Exports', 'solid_state_memory_fab', [TileResource.RARE_MINERALS]),
            DiscoveryAvenue('robotics', 'Demographic Aging & Factory Robotics', 'Shrinking Workforce & Sky-High Factory Wages', 'nc_logic_fab', [TileResource.RARE_MINERALS]),
        ],
    },
}


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
    complexity_class: int = 0
    discovery_avenues: list[DiscoveryAvenue] = field(default_factory=list)
    tier_dependencies: dict[int, list[str]] = field(default_factory=dict)
    incumbent_guild: str = ""
    protectionist_law: str = ""

    def __post_init__(self):
        override = _HISTORICAL_AVENUE_OVERRIDES.get(self.tech_id, {})
        if self.complexity_class <= 0:
            self.complexity_class = int(override.get('complexity_class', min(4, max(1, int(self.era)))))
        if not self.incumbent_guild:
            self.incumbent_guild = str(override.get(
                'incumbent_guild',
                f"Legacy {self.domain.value.replace('_', ' ').title()} Guilds"
            ))
        if not self.protectionist_law:
            self.protectionist_law = str(override.get(
                'protectionist_law',
                f"Incumbent {self.domain.value.replace('_', ' ').title()} Charter Restriction"
            ))
        if not self.discovery_avenues:
            if 'avenues' in override:
                self.discovery_avenues = list(override['avenues'])
            else:
                res_names = ", ".join(getattr(r, 'value', str(r)) for r in self.required_resources) or "Civic Inputs"
                proto = self.unlocked_buildings[0] if self.unlocked_buildings else f"{self.tech_id}_prototype"
                self.discovery_avenues = [
                    DiscoveryAvenue(f"{self.tech_id}_primary", f"Local {res_names} Hub (Primary Path)",
                                    f"Acute {self.domain.value.replace('_', ' ').title()} Bottleneck", proto, list(self.required_resources)),
                    DiscoveryAvenue(f"{self.tech_id}_arsenal", "Sovereign Arsenal & Public Works Mandate",
                                    "Strategic Fiscal / Military Modernization Pressure", f"state_{proto}", list(self.required_resources)),
                    DiscoveryAvenue(f"{self.tech_id}_syndicate", "Merchant & Artisan Syndicate Venture",
                                    "High Wage / Commercial Arbitrage Opportunity", f"commercial_{proto}", list(self.required_resources)),
                ]
        if self.required_techs and 3 not in self.tier_dependencies:
            self.tier_dependencies[3] = list(self.required_techs)


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
    _trace_operation_id: str | None = field(default=None, compare=False, repr=False)
    _trace_escrow_event_id: str | None = field(default=None, compare=False, repr=False)


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
        # nation_name -> dict of tech_id -> refinement XP [0.0, 100.0] (Tiers 1..4)
        self.tech_refinement_xp: dict[str, dict[str, float]] = {}
        # nation_name -> dict of tech_id -> 'commercial' | 'standard' | 'crash'
        self.tech_subsidy_mode: dict[str, dict[str, str]] = {}
        # nation_name -> dict of tech_id -> {'active': bool, 'clout': float, 'frontier_bypass': bool, 'law_name': str}
        self.guild_blockades: dict[str, dict[str, dict]] = {}
        # nation_name -> dict of tech_id -> selected avenue_id
        self.selected_avenues: dict[str, dict[str, str]] = {}

    def get_discovered_techs(self, nation_name: str) -> set[str]:
        return self.discovered_techs.setdefault(nation_name, set())

    def has_tech(self, nation_name: str, tech_id: str) -> bool:
        return tech_id in self.get_discovered_techs(nation_name)

    def get_domain_xp(self, nation_name: str, domain: TechDomain) -> float:
        nat_xp = self.domain_experience.setdefault(nation_name, {d.value: 0.0 for d in TechDomain})
        return nat_xp.get(domain.value, 0.0)

    def get_refinement_xp(self, nation_name: str, tech_id: str) -> float:
        nat_ref = self.tech_refinement_xp.get(nation_name, {})
        if tech_id in nat_ref:
            return float(nat_ref[tech_id])
        if self.has_tech(nation_name, tech_id):
            return 1.0
        return 0.0

    def get_tech_tier(self, nation_name: str, tech_id: str) -> int:
        xp = self.get_refinement_xp(nation_name, tech_id)
        if not self.has_tech(nation_name, tech_id) and xp <= 0.0:
            return 0
        if xp < TIER_XP_THRESHOLDS[2]:
            return 1
        if xp < TIER_XP_THRESHOLDS[3]:
            return 2
        if xp < TIER_XP_THRESHOLDS[4]:
            return 3
        return 4

    def get_subsidy_mode(self, nation_name: str, tech_id: str) -> str:
        return self.tech_subsidy_mode.get(nation_name, {}).get(tech_id, 'commercial')

    def get_guild_blockade(self, nation_or_name: Nation | str, tech_id: str) -> dict:
        nat_name = nation_or_name if isinstance(nation_or_name, str) else getattr(nation_or_name, 'name', str(nation_or_name))
        nat_blocks = self.guild_blockades.setdefault(nat_name, {})
        if tech_id not in nat_blocks:
            tech = TECH_CATALOG.get(tech_id)
            era = getattr(tech, 'era', 1) if tech else 1
            # Incumbent guilds from earlier eras exert parliamentary clout against Era 3-4 paradigm shifts
            prior_era_mastered = sum(
                1 for tid in self.get_discovered_techs(nat_name)
                if tid in TECH_CATALOG and TECH_CATALOG[tid].era < era
            )
            clout = min(85.0, 20.0 + prior_era_mastered * 15.0) if era >= 3 else 15.0
            nat_blocks[tech_id] = {
                'active': bool(clout >= 50.0 and era >= 3),
                'clout': float(clout),
                'frontier_bypass': False,
                'law_name': tech.protectionist_law if tech else 'Guild Charter Restriction',
                'guild_name': tech.incumbent_guild if tech else 'Legacy Guilds',
            }
        return nat_blocks[tech_id]

    def evaluate_avenue_factors(self, nation: Nation, tech_id: str) -> dict:
        """Compute multi-avenue emergence and refinement multipliers from live tile conditions."""
        tech = TECH_CATALOG.get(tech_id)
        tiles = list(getattr(nation, 'tiles', ()))
        if not tech or not tiles:
            return {
                'prox_mult': 1.0, 'crisis_mult': 1.0, 'wage_ratio': 1.0,
                'supply_mult': 1.0, 'net_mult': 1.0, 'active_avenue': None,
            }

        nat_res = get_nation_resources(nation, tiles)
        req_res = list(tech.required_resources)
        if not req_res:
            prox_mult = 2.5
        elif all(r in nat_res for r in req_res):
            # Check if any single tile or adjacent pair co-locates the required inputs
            single_tile_match = any(
                all(r in getattr(tile, 'natural_resources', ()) for r in req_res)
                for tile in tiles
            )
            prox_mult = 4.0 if (single_tile_match or len(tiles) <= 2) else 1.5
        else:
            prox_mult = 0.2

        raw_pressure = tech.bottleneck_evaluator(nation, tiles) if tech.bottleneck_evaluator else 1.0
        crisis_mult = 2.5 if raw_pressure >= 1.8 else (1.4 if raw_pressure > 1.1 else 0.8)

        wages = [a.wage for r in tiles for a in getattr(r, 'agents', ()) if getattr(a, 'wage', 0.0) > 0.0]
        avg_wage = (sum(wages) / len(wages)) if wages else 1.0
        fuel_prices = [
            r.recipes.get(Goods.wood, {}).get('price', r.recipes.get(Goods.food, {}).get('price', 1.0))
            for r in tiles if hasattr(r, 'recipes')
        ]
        avg_fuel = (sum(fuel_prices) / len(fuel_prices)) if fuel_prices else 1.0
        wage_ratio = max(0.2, min(4.0, avg_wage / max(0.5, avg_fuel)))

        trade_vol = sum(
             (r.export_vol[g][-1] if r.export_vol.get(g) else 0)
            for r in tiles for g in getattr(r, 'export_vol', {})
        )
        supply_mult = max(0.8, min(3.0, 1.0 + trade_vol * 0.02))

        blockade = self.get_guild_blockade(nation, tech_id)
        net_mult = 1.5 * (0.75 if blockade.get('frontier_bypass') else 1.0)

        sel_id = self.selected_avenues.get(nation.name, {}).get(tech_id)
        active_av = next((av for av in tech.discovery_avenues if av.avenue_id == sel_id), None)
        if active_av is None and tech.discovery_avenues:
            active_av = tech.discovery_avenues[0]

        return {
            'prox_mult': prox_mult,
            'crisis_mult': crisis_mult,
            'wage_ratio': wage_ratio,
            'supply_mult': supply_mult,
            'net_mult': net_mult,
            'active_avenue': active_av.avenue_id if active_av else None,
            'avenue_name': active_av.name if active_av else tech.name,
            'prototype_building': active_av.prototype_building if active_av else '',
        }

    def set_subsidy_mode(self, nation: Nation, tech_id: str, mode: str, t: int = 0) -> tuple[bool, str]:
        """Switch prototype operating mode between 'commercial' (0x cost), 'standard' (1x -> 0.5x XP), and 'crash' (4x -> 1.0x XP)."""
        if tech_id not in TECH_CATALOG or mode not in ('commercial', 'standard', 'crash'):
            return False, f"Invalid tech '{tech_id}' or subsidy mode '{mode}'."
        tech = TECH_CATALOG[tech_id]
        if mode in ('standard', 'crash') and not self.has_tech(nation.name, tech_id):
            bounty_amt = 75.0 if mode == 'standard' else 300.0
            has_bounty = any(b.nation_name == nation.name and b.tech_id == tech_id for b in self.active_bounties)
            if not has_bounty and hasattr(nation, 'treasury'):
                self.post_royal_bounty(nation, tech_id, bounty_amt, t)
        self.tech_subsidy_mode.setdefault(nation.name, {})[tech_id] = mode
        label = {'commercial': 'Commercial (1.0x ROI)', 'standard': 'Standard 1x Subsidy (0.5x XP)', 'crash': 'Crash 4x Mandate (1.0x XP)'}[mode]
        return True, f"{nation.name} set '{tech.name}' operating mode to {label}."

    def attempt_tech_espionage(self, stealer: Nation, tech_id: str, t: int = 0,
                               target_nation: Nation | None = None,
                               nations: list[Nation] | None = None) -> tuple[bool, str]:
        """
        Incremental +1 Tier espionage action:
          - Requires physical input resources and dependent prerequisite sibling techs.
          - Capped by ComplexityClass (I: 85 XP, II: 65 XP, III: 50 XP, IV: 30 XP) and strictly below source tier.
          - Once stolen up to the ceiling, the nation can refine the technology locally all the way to Tier 4.
        """
        from innovation_trace import record_espionage_attempt, record_technology

        if tech_id not in TECH_CATALOG:
            return False, f"Unknown technology '{tech_id}'."
        tech = TECH_CATALOG[tech_id]
        before_xp = self.get_refinement_xp(stealer.name, tech_id)
        current_tier = self.get_tech_tier(stealer.name, tech_id)

        # 1. Input resource check
        nat_res = get_nation_resources(stealer, getattr(stealer, 'tiles', ()))
        missing_res = [r for r in tech.required_resources if r not in nat_res]
        if missing_res:
            record_espionage_attempt(
                stealer, tech_id, t, False, 'missing_input_resources', before_xp, before_xp,
                missing_resources=[getattr(r, 'value', str(r)) for r in missing_res])
            return False, f"Espionage blocked: {stealer.name} lacks physical input resources for '{tech.name}'."

        # 2. Determine source leader tier/XP
        source_tier = 4
        source_xp = 100.0
        source_name = target_nation.name if target_nation else 'Foreign Tech Leader'
        if target_nation is not None:
            source_tier = self.get_tech_tier(target_nation.name, tech_id)
            source_xp = self.get_refinement_xp(target_nation.name, tech_id)
        elif nations:
            peers = [other for other in nations if other.name != stealer.name and self.has_tech(other.name, tech_id)]
            if peers:
                best_peer = max(peers, key=lambda o: self.get_refinement_xp(o.name, tech_id))
                source_name = best_peer.name
                source_tier = max(2, self.get_tech_tier(best_peer.name, tech_id))
                source_xp = max(50.0, self.get_refinement_xp(best_peer.name, tech_id))

        max_steal_tier, max_steal_xp = COMPLEXITY_STEAL_CAPS.get(tech.complexity_class, (3, 65.0))
        effective_tier_cap = min(max_steal_tier, max(1, source_tier - 1) if source_tier < 4 else max_steal_tier)
        effective_xp_cap = min(max_steal_xp, source_xp * (max_steal_xp / 100.0))

        if current_tier >= effective_tier_cap or before_xp >= effective_xp_cap:
            record_espionage_attempt(
                stealer, tech_id, t, False, 'espionage_ceiling_reached', before_xp, before_xp,
                current_tier=current_tier, max_steal_tier=effective_tier_cap, max_steal_xp=effective_xp_cap)
            return (
                False,
                f"Espionage Ceiling reached for '{tech.name}' (Max Stolen: Tier {effective_tier_cap} / {effective_xp_cap:.0f} XP). "
                f"Refine your Tier {current_tier} prototypes domestically to reach Tier 4!"
            )

        target_tier = current_tier + 1
        # 3. Prerequisite sibling tech check
        discovered = self.get_discovered_techs(stealer.name)
        missing_prereqs = [req for req in tech.required_techs if req not in discovered]
        tier_deps = tech.tier_dependencies.get(target_tier, [])
        missing_tier_deps = [dep for dep in tier_deps if self.get_tech_tier(stealer.name, dep) < 2 and dep not in discovered]
        all_missing = list(dict.fromkeys(missing_prereqs + missing_tier_deps))
        if all_missing and (target_tier >= 2 or missing_prereqs):
            record_espionage_attempt(
                stealer, tech_id, t, False, 'missing_dependent_technology', before_xp, before_xp,
                target_tier=target_tier, missing_dependencies=all_missing)
            return False, f"Dependency Lock: Must steal or develop prerequisite {all_missing} before stealing Tier {target_tier} '{tech.name}'!"

        # 4. Advance by +1 Tier up to ceiling
        tier_floor_xp = {1: 5.0, 2: 28.0, 3: 62.0}
        after_xp = min(effective_xp_cap, max(before_xp + 15.0, tier_floor_xp.get(target_tier, 28.0)))
        self.tech_refinement_xp.setdefault(stealer.name, {})[tech_id] = after_xp

        was_known = tech_id in discovered
        if not was_known:
            discovered.add(tech_id)
            record_technology(
                stealer, tech_id, t, 'espionage_theft', source_nation=source_name,
                declared_unlocked_buildings=list(tech.unlocked_buildings),
                declared_production_modifiers={
                    getattr(Goods._value2member_map_.get(good), 'name', str(good)): value
                    for good, value in tech.production_modifiers.items()},
                modifier_basis='technology_catalog_declaration')

        new_tier = self.get_tech_tier(stealer.name, tech_id)
        record_espionage_attempt(
            stealer, tech_id, t, True, 'stolen_plus_one_tier', before_xp, after_xp,
            source_nation=source_name, tier_before=current_tier, tier_after=new_tier,
            max_steal_xp=effective_xp_cap)
        msg = f"ESPIONAGE (+1 Tier): {stealer.name} stole Tier {new_tier} '{tech.name}' blueprints ({after_xp:.0f} XP) from {source_name}!"
        self.discovery_log.append({'t': t, 'nation': stealer.name, 'tech_id': tech_id, 'tech_name': tech.name, 'event': 'ESPIONAGE', 'message': msg})
        return True, msg

    def resolve_guild_blockade(self, nation: Nation, tech_id: str, action: str, t: int = 0) -> tuple[bool, str]:
        """Resolve an incumbent guild legislative blockade via 'repeal', 'buyout', or 'frontier' bypass."""
        from innovation_trace import record_guild_legislation

        if tech_id not in TECH_CATALOG or action not in ('repeal', 'buyout', 'frontier'):
            return False, f"Unknown technology '{tech_id}' or guild action '{action}'."
        blockade = self.get_guild_blockade(nation, tech_id)
        tech = TECH_CATALOG[tech_id]

        if action == 'repeal':
            if hasattr(nation, 'legitimacy'):
                nation.legitimacy = max(0.05, float(nation.legitimacy) - 0.08)
            blockade['active'] = False
            msg = f"PARLIAMENTARY REPEAL: {nation.name} repealed '{blockade['law_name']}', unblocking '{tech.name}' refinement!"
        elif action == 'buyout':
            if hasattr(nation, 'treasury') and not self.has_tech(nation.name, tech_id):
                self.post_royal_bounty(nation, tech_id, 300.0, t)
            blockade['active'] = False
            blockade['clout'] = 10.0
            msg = f"EMINENT DOMAIN BUYOUT: {nation.name} bought out {blockade['guild_name']} charters, unblocking '{tech.name}'!"
        else:  # frontier
            blockade['active'] = False
            blockade['frontier_bypass'] = True
            msg = f"GREENFIELD BYPASS: {nation.name} deployed '{tech.name}' prototypes in frontier districts outside guild jurisdiction!"

        record_guild_legislation(
            nation, tech_id, t, action, blockade['active'],
            guild_name=blockade['guild_name'], law_name=blockade['law_name'],
            frontier_bypass=blockade['frontier_bypass'])
        self.discovery_log.append({'t': t, 'nation': nation.name, 'tech_id': tech_id, 'tech_name': tech.name, 'event': 'GUILD_RESOLVED', 'message': msg})
        return True, msg

    def step_refinement(self, nations: list[Nation], t: int) -> list[dict]:
        """Advance domestic Tinkering/Refinement XP (0..100, Tiers 1..4) for discovered technologies."""
        from innovation_trace import record_refinement_progress

        events = []
        for n in nations:
            discovered = self.get_discovered_techs(n.name)
            if not discovered or not getattr(n, 'tiles', ()):
                continue
            nat_ref = self.tech_refinement_xp.setdefault(n.name, {})
            for tech_id in sorted(discovered):
                tech = TECH_CATALOG.get(tech_id)
                if not tech:
                    continue
                before_xp = float(nat_ref.get(tech_id, 1.0))
                if before_xp >= 100.0:
                    continue
                prev_tier = self.get_tech_tier(n.name, tech_id)
                factors = self.evaluate_avenue_factors(n, tech_id)
                mode = self.get_subsidy_mode(n.name, tech_id)

                if mode == 'commercial':
                    roi = factors['wage_ratio'] * (factors['prox_mult'] / 2.0)
                    base_ref = 0.8 if roi < 1.2 else 2.5 * (factors['wage_ratio'] / 2.0) * (factors['prox_mult'] / 2.0)
                elif mode == 'standard':
                    base_ref = 3.2 * 0.5
                else:  # crash (4x cost -> full 1.0x adjacency speed)
                    base_ref = 3.2 * 1.35

                increment = base_ref * (factors['supply_mult'] / 1.5) * (factors['net_mult'] / 1.2)
                blockade = self.get_guild_blockade(n, tech_id)
                if blockade.get('active'):
                    increment *= 0.25

                # Check Tier 3 prerequisite sibling tech gate (60 XP threshold)
                tier3_deps = tech.tier_dependencies.get(3, [])
                missing_tier3 = [dep for dep in tier3_deps if dep not in discovered]
                cap_xp = 59.0 if missing_tier3 else 100.0

                after_xp = min(cap_xp, before_xp + max(0.0, increment))
                nat_ref[tech_id] = after_xp
                record_refinement_progress(
                    n, tech_id, t, before_xp, after_xp, increment, cap_xp=cap_xp,
                    subsidy_mode=mode, guild_blockade_active=bool(blockade.get('active')),
                    avenue_id=factors.get('active_avenue'))

                new_tier = self.get_tech_tier(n.name, tech_id)
                if new_tier > prev_tier:
                    msg = f"REFINEMENT TIER {new_tier}: {n.name} refined '{tech.name}' to Tier {new_tier} ({after_xp:.0f} XP)!"
                    ev = {'t': t, 'nation': n.name, 'tech_id': tech_id, 'tech_name': tech.name, 'tier': new_tier, 'event': 'REFINEMENT', 'message': msg}
                    events.append(ev)
        return events

    def post_royal_bounty(self, nation: Nation, tech_id: str, bounty_amount: float, t: int) -> bool:
        """Sovereign posts a cash prize from treasury to incentivize a breakthrough."""
        from innovation_trace import record_bounty_gate, record_bounty_funding

        if tech_id not in TECH_CATALOG:
            record_bounty_gate(nation, tech_id, t, bounty_amount, False, 'unknown_technology')
            return False
        if self.has_tech(nation.name, tech_id):
            record_bounty_gate(nation, tech_id, t, bounty_amount, False, 'technology_already_known')
            return False
        treasury = nation.treasury()
        if treasury['total'] < bounty_amount:
            record_bounty_gate(nation, tech_id, t, bounty_amount, False,
                               'insufficient_total_treasury', treasury=dict(treasury))
            return False

        # Deduct bounty cash from government (held in escrow until awarded)
        gate_id = record_bounty_gate(nation, tech_id, t, bounty_amount, True,
                                    'affordable_from_total_treasury', treasury=dict(treasury))
        cash_before = float(nation.government.agent.cash)
        _public_write = begin_public_change(None, nation.government.agent)
        nation.government.agent.cash -= bounty_amount
        finish_public_change(_public_write, 'innovation:InnovationSystem.post_royal_bounty',
                             inputs={'source_writer': 'innovation.py:InnovationSystem.post_royal_bounty:0f57323c95457acc:1', 'semantic_operation_id': locals().get('operation_id')})
        bounty = RoyalBounty(tech_id=tech_id, nation_name=nation.name,
                             bounty_amount=bounty_amount, offered_turn=t)
        self.active_bounties.append(bounty)
        record_bounty_funding(nation, bounty, cash_before,
                              float(nation.government.agent.cash), treasury, gate_id)
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
                                      known_technology_event,
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
                prerequisite_trace_ids = [known_technology_event(n, req)
                                          for req in tech.required_techs]
                evaluation_id = emit_innovation(
                    n, kind='innovation_breakthrough_evaluation', record_class='calculation',
                    subject_fields={'tech_id': tech_id}, metric_id='innovation.breakthrough',
                    unit='boolean', after=int(success),
                    formula_id='innovation.breakthrough_draw.v1',
                    inputs={'turn': int(t), 'domain': tech.domain.value,
                            'domain_experience': xp, 'bottleneck_multiplier': raw_pressure,
                            'bounty_active': bounty_obj is not None,
                            'bounty_amount': bounty_obj.bounty_amount if bounty_obj else None,
                            'bounty_id': bounty_obj._trace_operation_id if bounty_obj else None,
                            'effective_experience': effective_xp,
                            'required_experience': tech.base_xp_required,
                            'threshold_met': effective_xp >= tech.base_xp_required,
                            'chance': base_chance, 'random_draw': draw,
                            'available_resources': sorted(getattr(res, 'value', str(res)) for res in nat_res),
                            'required_technologies': list(tech.required_techs),
                            'reason': ('discovered' if success else 'breakthrough_roll_failed'
                                       if draw is not None else 'experience_below_threshold')},
                    cause_event_ids=[event_id for event_id in (
                        learning_id, pressure_trace_id,
                        bounty_obj._trace_escrow_event_id if bounty_obj else None,
                        *prerequisite_trace_ids)
                                     if event_id is not None] or None)
                if success:
                    discovered.add(tech_id)
                    discovery_id = record_technology(
                        n, tech_id, t, 'domestic_breakthrough',
                        declared_unlocked_buildings=list(tech.unlocked_buildings),
                        declared_production_modifiers={
                            getattr(Goods._value2member_map_.get(good), 'name', str(good)): value
                            for good, value in tech.production_modifiers.items()},
                        modifier_basis='technology_catalog_declaration',
                        cause_event_ids=([evaluation_id] if evaluation_id else None))
                    msg = f"BREAKTHROUGH: {n.name} discovered '{tech.name}' via {tech.domain.value} practice (Pressure: {pressure:.1f}x)!"
                    event = {'t': t, 'nation': n.name, 'tech_id': tech_id, 'tech_name': tech.name, 'event': 'DISCOVERY', 'message': msg}
                    events.append(event)
                    self.discovery_log.append(event)

                    if bounty_obj:
                        self.active_bounties.remove(bounty_obj)
                        cap_tile = nat_tiles[0]
                        payments = []
                        if cap_tile.agents:
                            share = bounty_obj.bounty_amount / len(cap_tile.agents)
                            for a in cap_tile.agents:
                                recipient_before = float(a.cash)
                                _public_write = begin_public_change(None, a)
                                a.cash += share
                                finish_public_change(_public_write, 'innovation:InnovationSystem.evaluate_breakthroughs',
                                                     inputs={'source_writer': 'innovation.py:InnovationSystem.evaluate_breakthroughs:a9bdf8381733dec4:1', 'semantic_operation_id': locals().get('operation_id')})
                                payments.append({'agent_id': getattr(a, 'id', None), 'amount': float(share),
                                                 'cash_before': recipient_before,
                                                 'cash_after': float(a.cash)})
                        from innovation_trace import record_bounty_award
                        record_bounty_award(n, bounty_obj, t, cap_tile.name, payments, discovery_id)
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
                                      known_technology_event,
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
                source_knowledge_id = known_technology_event(n_src, tech_id)
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
                            'source_knowledge_event_id': source_knowledge_id,
                            'source_knowledge_trace_status': ('linked' if source_knowledge_id
                                                              else 'no_knowledge_mutation_record'),
                            'prerequisite_resource_checks': 'not_applied_to_trade_diffusion',
                            'zero_trade_rule': 'positive baseline diffusion remains active'},
                    cause_event_ids=[event_id for event_id in (previous_id, source_knowledge_id)
                                     if event_id is not None] or None)

                if cur >= 1.0:
                    # Fully adopted via trade diffusion!
                    dst_techs.add(tech_id)
                    dst_prog.pop(tech_id, None)
                    adoption_id = record_technology(
                        n_dst, tech_id, t, 'trade_diffusion', source_nation=n_src.name,
                        source_tile=r.name, destination_tile=other.name,
                        declared_unlocked_buildings=list(TECH_CATALOG[tech_id].unlocked_buildings),
                        declared_production_modifiers={
                            getattr(Goods._value2member_map_.get(good), 'name', str(good)): value
                            for good, value in TECH_CATALOG[tech_id].production_modifiers.items()},
                        modifier_basis='technology_catalog_declaration',
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
        """Advance one turn of learning-by-doing, induced breakthroughs, trade diffusion, and domestic refinement."""
        self.accumulate_learning_by_doing(tiles, nations, t)
        discovery_events = self.evaluate_breakthroughs(nations, t)
        diffusion_events = self.diffuse_technologies_along_trade(pair_orders, nations, t)
        refinement_events = self.step_refinement(nations, t)
        return discovery_events + diffusion_events + refinement_events


_INNOVATION_SYSTEM: InnovationSystem | None = None

def get_innovation_system() -> InnovationSystem:
    global _INNOVATION_SYSTEM
    if _INNOVATION_SYSTEM is None:
        _INNOVATION_SYSTEM = InnovationSystem()
    return _INNOVATION_SYSTEM

def step_innovation(tiles: list[Region], nations: list[Nation], pair_orders: list, t: int) -> list[dict]:
    return get_innovation_system().step(tiles, nations, pair_orders, t)
