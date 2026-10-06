"""
economy/map_generator.py — Procedural Capitalism Map Generator & Balanced Geological Gating.

Generates and tunes balanced geological and ecological world configurations for the
Capitalist Propagation Engine:
1. Gated Mineral Deposits:
   - Iron ore deposits: strictly highland/mountainous bedrock (elevation >= 0.40 or biome in hills/mountains). Rarity ~12-15%.
   - Coal seams: strictly sedimentary hill/forest biomes (0.20 <= elevation <= 0.65). Rarity ~10-12%.
   - Nitrate deposits: coastal islands and arid basins. Rarity ~8%.
2. Climate & Ecological Zoning:
   - Subtropical / Mediterranean river corridors and southern zones for cash crops (cotton, sugar, tobacco).
   - Temperate central plains for food grain farming, sheep pasture grazing, and textile weaving.
   - Cold northern highland ridges for timber and iron mining.
3. Peripheral Wilderness & Colonial Frontier:
   - Preserves unclaimed frontier tiles with native populations (wilderness_pop > 0)
     bordering claimed nations, guaranteeing that War Capitalism chartered expeditions
     and plantation complexes can always operate.
4. Deterministic Map Regeneration:
   - Ensures that when a player regenerates the world map (using any random or chosen seed),
     all gameplay elements, geological deposits, and economic institutions are reliably re-created.
"""

from __future__ import annotations
import random
from typing import List, Dict, Any, Tuple, Optional
from goods import Goods
from agent import Agent, initialize_agent, seed_traits
from land_tenure import LandPlot, TenureStatus
from province import Province


def apply_geological_and_economic_distribution(
    tiles: List[Any],
    grid: List[List[Any]],
    seed: int = 42,
    grid_rows: int = 9,
    grid_cols: int = 9,
) -> Dict[str, Any]:
    """Distributes geological deposits, climates, and economic setups across world tiles with balanced rarity."""
    rng = random.Random(seed)

    land_tiles = [t for t in tiles if not getattr(t, 'is_ocean', False) and getattr(t, 'elevation', 0.0) >= 0.0]
    total_land = len(land_tiles)
    if total_land == 0:
        return {'iron_count': 0, 'coal_count': 0, 'nitrate_count': 0}

    # 1. Climate Zoning by Geography
    # South/East river valleys -> Subtropical (cotton, sugar, tobacco)
    # North/Highland -> Cold (timber, mining)
    # Central/West -> Temperate (grains, wool)
    for tile in tiles:
        if getattr(tile, 'is_ocean', False):
            continue
        r = getattr(tile, 'grid_r', 0)
        c = getattr(tile, 'grid_c', 0)
        elev = getattr(tile, 'elevation', 0.20)

        if elev >= 0.70 or r <= 1:
            tile.climate = 'cold'
        elif (r >= 5 and c >= 3) or getattr(tile, 'is_river_corridor', False):
            tile.climate = 'subtropical'
        elif r >= 6 and c <= 3:
            tile.climate = 'mediterranean'
        else:
            tile.climate = 'temperate'

    # 2. Geological Mineral Deposit Distribution (Balanced Rarity)
    # A. Iron Ore Deposits (~12-14% of land tiles)
    iron_candidates = [
        t for t in land_tiles
        if getattr(t, 'elevation', 0.0) >= 0.38 or getattr(t, 'biome', '') in ('hills', 'mountains', 'snow_peaks')
    ]
    target_iron_count = max(2, min(len(iron_candidates), int(total_land * 0.13)))
    selected_iron = rng.sample(iron_candidates, min(len(iron_candidates), target_iron_count)) if iron_candidates else []

    for t in land_tiles:
        t.has_iron_deposit = False
        t.mineral_richness = 0.0
        if not hasattr(t, 'terrain') or t.terrain is None:
            t.terrain = {}

    for t in selected_iron:
        t.has_iron_deposit = True
        t.mineral_richness = round(0.40 + 0.60 * rng.random(), 2)
        t.terrain['iron_deposit'] = True
        t.terrain['has_iron_deposit'] = True

    # B. Coal Veins (~10-12% of land tiles, non-overlapping with high snow peaks)
    coal_candidates = [
        t for t in land_tiles
        if not getattr(t, 'has_iron_deposit', False)
        and (getattr(t, 'biome', '') in ('hills', 'forest', 'plains'))
        and (0.15 <= getattr(t, 'elevation', 0.0) <= 0.65)
    ]
    target_coal_count = max(2, min(len(coal_candidates), int(total_land * 0.11)))
    selected_coal = rng.sample(coal_candidates, min(len(coal_candidates), target_coal_count)) if coal_candidates else []

    for t in land_tiles:
        t.has_coal_vein = False

    for t in selected_coal:
        t.has_coal_vein = True
        t.terrain['coal_vein'] = True
        t.terrain['has_coal_vein'] = True

    # C. Nitrate / Saltpeter Deposits (~8% of land tiles, coastal / arid)
    nitrate_candidates = [
        t for t in land_tiles
        if not getattr(t, 'has_iron_deposit', False) and not getattr(t, 'has_coal_vein', False)
        and (getattr(t, 'is_coast', False) or getattr(t, 'climate', '') in ('mediterranean', 'subtropical'))
    ]
    target_nitrate_count = max(1, min(len(nitrate_candidates), int(total_land * 0.08)))
    selected_nitrate = rng.sample(nitrate_candidates, min(len(nitrate_candidates), target_nitrate_count)) if nitrate_candidates else []

    for t in land_tiles:
        t.has_nitrate_deposit = False

    for t in selected_nitrate:
        t.has_nitrate_deposit = True
        t.terrain['nitrate_deposit'] = True
        t.terrain['has_nitrate_deposit'] = True

    return {
        'total_land_tiles': total_land,
        'iron_count': len(selected_iron),
        'coal_count': len(selected_coal),
        'nitrate_count': len(selected_nitrate),
        'subtropical_count': sum(1 for t in land_tiles if getattr(t, 'climate', '') == 'subtropical'),
        'temperate_count': sum(1 for t in land_tiles if getattr(t, 'climate', '') == 'temperate'),
        'cold_count': sum(1 for t in land_tiles if getattr(t, 'climate', '') == 'cold'),
    }


def setup_capitalism_institutions(region: Any, t: int = 0) -> None:
    """Configures feudal land tenure, open plots, lord agent, and corporate firm vacancies."""
    if getattr(region, 'wilderness', False) or getattr(region, 'is_ocean', False):
        return

    # Initialize universal recipes
    if hasattr(region, 'recipes'):
        region.recipes.setdefault(Goods.wool, {'price': 3.5, 'production': 10, 'numInput': 0})
        region.recipes.setdefault(Goods.cloth, {'price': 6.0, 'production': 8, 'numInput': 2, 'input': Goods.wool})
        region.recipes.setdefault(Goods.cotton, {'price': 4.0, 'production': 12, 'numInput': 0})
        region.recipes.setdefault(Goods.iron_ore, {'price': 3.0, 'production': 6, 'numInput': 0})
        region.recipes.setdefault(Goods.iron, {'price': 7.5, 'production': 5, 'numInput': 2, 'input': Goods.iron_ore})
        region.recipes.setdefault(Goods.coal, {'price': 4.0, 'production': 8, 'numInput': 0})
        region.recipes.setdefault(Goods.sugar, {'price': 4.5, 'production': 10, 'numInput': 0})
        region.recipes.setdefault(Goods.rum, {'price': 9.0, 'production': 4, 'numInput': 2, 'input': Goods.sugar})
        region.recipes.setdefault(Goods.fine_textiles, {'price': 15.0, 'production': 3, 'numInput': 2, 'input': Goods.cloth, 'is_luxury': True})

    # Ensure tenure system has plots
    if hasattr(region, 'tenure') and region.tenure:
        tenure = region.tenure
        if len(tenure.plots) == 0:
            agents = getattr(region, 'agents', [])
            lord = next((a for a in agents if getattr(a, 'is_lord', False)), None)
            if not lord and agents:
                lord = agents[0]
                lord.is_lord = True
                lord.cash = max(100.0, getattr(lord, 'cash', 0.0))

            lord_id = lord.id if lord else 1
            # Add 6 customary serf plots and 2 manorial demesne plots
            for p_idx in range(8):
                plot = LandPlot(
                    plot_id=f"plot_{region.name}_{p_idx+1}",
                    tile_name=region.name,
                    lord_id=lord_id,
                    fraction=0.125,
                    tenure=TenureStatus.FEUDAL if p_idx < 6 else TenureStatus.ENCLOSED,
                    rent_rate=1.50 if p_idx >= 6 else 0.0,
                    tenant_ids=[agents[min(len(agents)-1, p_idx+1)].id] if len(agents) > p_idx+1 else [],
                )
                tenure.plots.append(plot)


def generate_capitalism_map(
    seed: int = 42,
    terrain_seed: Optional[int] = None,
    nation_seed: Optional[int] = None,
    scenario_id: Optional[str] = None
) -> Tuple[List[Any], List[Any], List[List[Any]]]:
    """Builds a complete, procedurally generated capitalist simulation map.

    Returns:
        (tiles, nations, grid)
    Guarantees:
        - Gated geological ore deposits (iron, coal, nitrates) with tuned rarity.
        - Geographic climate diversity (subtropical, temperate, cold).
        - Feudal estates, manorial tenure, and capitalist investment structures.
        - Bordering peripheral wilderness territories for War Capitalism conquest.
    """
    from sim_world import build_world_hex

    tiles, nations, grid = build_world_hex(
        seed=seed,
        terrain_seed=terrain_seed,
        nation_seed=nation_seed,
        scenario_id=scenario_id
    )

    # Apply geological and climate distribution
    t_seed = terrain_seed if terrain_seed is not None else seed
    apply_geological_and_economic_distribution(tiles, grid, seed=t_seed)

    # Initialize institutions on all claimed regions
    for tile in tiles:
        setup_capitalism_institutions(tile, t=0)

    return tiles, nations, grid
