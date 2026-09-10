"""
externalities.py — Ecological Metabolic Rift, Soil Depletion, Fertilizer/Pesticide Tradeoffs,
and Industrial Pollution for REGNUM.

Models:
1. Metabolic Rift & Soil Fertility:
   - Intensive monoculture farming extracts soil nitrogen/minerals, causing soil_fertility to decay.
   - Restored naturally through customary fallow, Four-Field Crop Rotation, and soil conservation reserves.
2. Synthetic Fertilizers:
   - Drastically boosts crop yield (+75%), but degrades food nutrition_density (1.0 -> 0.70)
   - Generates nitrate runoff into local water bodies (+pollution_water).
3. Chemical Pesticides:
   - Shields crops (+40% output), but leaves persistent chemical toxins in soil and water
   - Direct toxic chemical exposure spikes health_attrition on farmworkers and local pops.
4. Industrial Pollution:
   - Smelting, coal coking, and steam mills generate atmospheric smog (pollution_air) and industrial effluent (pollution_water).
   - Smoke scrubbers reduce smog by 70% at the cost of toxic chemical sludge (pollution_soil).
   - Municipal trunk sewers clean urban drinking water, flushing effluent downstream.
5. Public Health Consequences:
   - Smog inhalation, contaminated water, and depleted food nutrition accelerate agent health_attrition.
"""

from __future__ import annotations
from goods import Goods
from random_cache import rand


def step_tile_externalities(region, t: int) -> dict:
    """Execute per-turn ecological update for a region: soil, nutrition, air, water, and soil toxicity."""
    if not hasattr(region, 'soil_fertility'):
        region.soil_fertility = 1.0
    if not hasattr(region, 'nutrition_density'):
        region.nutrition_density = 1.0
    if not hasattr(region, 'pollution_air'):
        region.pollution_air = 0.0
    if not hasattr(region, 'pollution_water'):
        region.pollution_water = 0.0
    if not hasattr(region, 'pollution_soil'):
        region.pollution_soil = 0.0
    if not hasattr(region, 'use_fertilizer'):
        region.use_fertilizer = False
    if not hasattr(region, 'use_pesticides'):
        region.use_pesticides = False

    # Check installed buildings and nation techs for ecological modifiers
    b_names = [getattr(b, 'name', '') for b in getattr(region, 'buildings', [])]
    has_sewer = 'trunk_sewer' in b_names
    has_scrubber = 'smoke_scrubber' in b_names
    has_filtration = 'water_filtration_plant' in b_names
    has_conservation = 'soil_conservation_reserve' in b_names

    nation = getattr(region, 'owner_nation', None)
    unlocked_techs = getattr(nation, 'unlocked_techs', set()) if nation else set()
    has_rotation = 'crop_rotation' in unlocked_techs
    has_agroecology = 'agroecology_rotation' in unlocked_techs
    has_clean_pest = 'biological_pest_control' in unlocked_techs

    # Auto-enable fertilizer/pesticides if mandated or if unlocked & active
    use_fert = region.use_fertilizer or getattr(region, 'mandate_fertilizer', False)
    use_pest = region.use_pesticides or getattr(region, 'mandate_pesticides', False)

    # -------------------------------------------------------------------------
    # 1. Agricultural Intensity & Metabolic Soil Depletion
    # -------------------------------------------------------------------------
    food_producers = sum(1 for a in getattr(region, 'agents', [])
                         if getattr(a, 'output', None) == Goods.food
                         and not getattr(a, 'is_corporation', False)
                         and getattr(a, 'employer', None) is None)
    farm_corps = sum(1 for a in getattr(region, 'agents', [])
                     if getattr(a, 'is_corporation', False)
                     and getattr(a, 'output', None) == Goods.food)

    # Soil extraction from monoculture harvest
    # Extensive corporate farms extract nutrients faster than small customary yeomen
    extraction_rate = 0.003 * min(10, food_producers) + 0.012 * farm_corps
    enclosed = getattr(getattr(region, 'tenure', None), 'enclosed_fraction', 0.0)
    extraction_rate *= (1.0 + enclosed * 0.5)

    # Natural and agroecological regeneration
    regen_rate = 0.015  # Baseline natural microbial recovery
    if has_rotation:
        regen_rate += 0.015  # Four-field rotation with legumes
    if has_agroecology:
        regen_rate += 0.030  # Advanced agroecology & compost digestion
    if has_conservation:
        regen_rate += 0.025  # Soil conservation reserve buffer plots
    if getattr(region, 'soil_conservation_subsidy', False):
        regen_rate += 0.020  # Subsidized fallow periods

    # If chemical fertilizer is used, natural soil regeneration is suppressed (microbiome death)
    if use_fert:
        regen_rate *= 0.30

    max_fertility = 1.25 if 'arable_silt' in getattr(region, 'terrain', {}) else 1.10
    region.soil_fertility = max(0.25, min(max_fertility, region.soil_fertility - extraction_rate + regen_rate))

    # -------------------------------------------------------------------------
    # 2. Food Nutritional Density Dynamics
    # -------------------------------------------------------------------------
    if use_fert:
        # Synthetic nitrogen forces rapid water uptake, diluting protein and micronutrients
        target_nutrition = 0.70
    elif has_agroecology or has_rotation:
        # Diverse soil biology maximizes micronutrient density
        target_nutrition = 1.00
    else:
        # Depleted soil slightly lowers nutrition
        target_nutrition = max(0.80, min(1.0, region.soil_fertility))

    # Nutrition density shifts smoothly towards target
    region.nutrition_density += (target_nutrition - region.nutrition_density) * 0.25
    region.nutrition_density = max(0.50, min(1.0, region.nutrition_density))

    # -------------------------------------------------------------------------
    # 3. Atmospheric Smog & Air Pollution (Coal, Smelters, Mills)
    # -------------------------------------------------------------------------
    industrial_producers = sum(1 for a in getattr(region, 'agents', [])
                               if getattr(a, 'output', None) in (Goods.wood, Goods.furniture)
                               and getattr(a, 'is_corporation', False))
    raw_air_emission = industrial_producers * 1.8
    if 'coal_coking' in unlocked_techs or 'steam_engines' in unlocked_techs:
        raw_air_emission *= 1.6  # Coal burning generates intense sulfur smog

    # Wet smoke scrubber cuts smog by 70%, but generates toxic sludge
    sludge_generated = 0.0
    if has_scrubber:
        scrubbed = raw_air_emission * 0.70
        raw_air_emission -= scrubbed
        sludge_generated = scrubbed * 0.50

    # Atmospheric wind dispersion (15% per turn)
    region.pollution_air = max(0.0, min(100.0, region.pollution_air * 0.85 + raw_air_emission))

    # -------------------------------------------------------------------------
    # 4. Water Effluent & Aquifer Pollution
    # -------------------------------------------------------------------------
    pop_count = len([a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)])
    urban_waste = (pop_count / 80.0) * 1.5
    ind_water_waste = industrial_producers * 1.2
    fert_runoff = 3.5 if use_fert else 0.0

    raw_water_emission = urban_waste + ind_water_waste + fert_runoff

    # Trunk sewer channels wastewater away from city center
    if has_sewer:
        raw_water_emission *= 0.40  # Local water protected, flushes downstream
    if has_filtration or getattr(region, 'clean_water_act', False):
        raw_water_emission *= 0.30  # Filtration plants purify supply

    # River flow dispersion (12% per turn)
    region.pollution_water = max(0.0, min(100.0, region.pollution_water * 0.88 + raw_water_emission))

    # -------------------------------------------------------------------------
    # 5. Soil Toxicity & Chemical Sludge
    # -------------------------------------------------------------------------
    pesticide_runoff = 4.0 if (use_pest and not has_clean_pest) else 0.0
    raw_soil_emission = pesticide_runoff + sludge_generated

    # Biodegradation of soil toxins (8% per turn)
    region.pollution_soil = max(0.0, min(100.0, region.pollution_soil * 0.92 + raw_soil_emission))

    # -------------------------------------------------------------------------
    # 6. Public Health Attrition Impact
    # -------------------------------------------------------------------------
    apply_environmental_health_wear(region)

    # -------------------------------------------------------------------------
    # 7. Archive Time-Series Logs
    # -------------------------------------------------------------------------
    if not hasattr(region, 'soil_fertility_log'):
        region.soil_fertility_log = []
    if not hasattr(region, 'nutrition_density_log'):
        region.nutrition_density_log = []
    if not hasattr(region, 'pollution_air_log'):
        region.pollution_air_log = []
    if not hasattr(region, 'pollution_water_log'):
        region.pollution_water_log = []
    if not hasattr(region, 'pollution_soil_log'):
        region.pollution_soil_log = []

    region.soil_fertility_log.append(region.soil_fertility)
    region.nutrition_density_log.append(region.nutrition_density)
    region.pollution_air_log.append(region.pollution_air)
    region.pollution_water_log.append(region.pollution_water)
    region.pollution_soil_log.append(region.pollution_soil)

    return get_tile_metabolic_state(region)


def apply_environmental_health_wear(region):
    """Inflict physiological wear-and-tear from smog, bad water, toxic spray, and depleted food."""
    use_pest = region.use_pesticides or getattr(region, 'mandate_pesticides', False)
    nation = getattr(region, 'owner_nation', None)
    has_clean_pest = 'biological_pest_control' in getattr(nation, 'unlocked_techs', set()) if nation else False

    for a in getattr(region, 'agents', []):
        if not getattr(a, 'alive', True) or getattr(a, 'is_corporation', False) or getattr(a, 'is_government', False):
            continue

        attrition_delta = 0.0

        # 1. Smog inhalation (particulate matter & sulfur)
        if region.pollution_air > 15.0:
            attrition_delta += 0.0015 * (region.pollution_air - 15.0)

        # 2. Contaminated drinking water (cholera, heavy metals)
        if region.pollution_water > 20.0:
            attrition_delta += 0.0020 * (region.pollution_water - 20.0)

        # 3. Direct pesticide exposure (agricultural laborers handle toxic spray)
        if use_pest and not has_clean_pest and getattr(a, 'output', None) == Goods.food:
            attrition_delta += 0.040  # Acute chemical toxicity on farmworkers
        elif region.pollution_soil > 25.0:
            attrition_delta += 0.0015 * (region.pollution_soil - 25.0)

        # 4. Poor food nutritional density (micronutrient deficiency)
        if region.nutrition_density < 0.85:
            attrition_delta += 0.025 * (1.0 - region.nutrition_density)

        if attrition_delta > 0.0:
            a.health_attrition = getattr(a, 'health_attrition', 0.0) + attrition_delta


def get_tile_metabolic_state(region) -> dict:
    """Return structured dictionary of Phase 3 metabolic and pollution indices for a region."""
    return {
        'soil_fertility': getattr(region, 'soil_fertility', 1.0),
        'nutrition_density': getattr(region, 'nutrition_density', 1.0),
        'pollution_air': getattr(region, 'pollution_air', 0.0),
        'pollution_water': getattr(region, 'pollution_water', 0.0),
        'pollution_soil': getattr(region, 'pollution_soil', 0.0),
        'use_fertilizer': getattr(region, 'use_fertilizer', False),
        'use_pesticides': getattr(region, 'use_pesticides', False),
        'total_toxicity': (
            getattr(region, 'pollution_air', 0.0) * 0.35 +
            getattr(region, 'pollution_water', 0.0) * 0.40 +
            getattr(region, 'pollution_soil', 0.0) * 0.25
        ),
    }


def aggregate_nation_externalities(nation) -> dict:
    """Compute aggregate national averages for ecological and environmental health."""
    tiles = getattr(nation, 'tiles', [])
    if not tiles:
        return {
            'avg_soil_fertility': 1.0,
            'avg_nutrition_density': 1.0,
            'avg_pollution_air': 0.0,
            'avg_pollution_water': 0.0,
            'avg_pollution_soil': 0.0,
            'composite_toxicity': 0.0,
        }
    n = len(tiles)
    avg_fert = sum(getattr(t, 'soil_fertility', 1.0) for t in tiles) / n
    avg_nutr = sum(getattr(t, 'nutrition_density', 1.0) for t in tiles) / n
    avg_air = sum(getattr(t, 'pollution_air', 0.0) for t in tiles) / n
    avg_water = sum(getattr(t, 'pollution_water', 0.0) for t in tiles) / n
    avg_soil = sum(getattr(t, 'pollution_soil', 0.0) for t in tiles) / n
    return {
        'avg_soil_fertility': avg_fert,
        'avg_nutrition_density': avg_nutr,
        'avg_pollution_air': avg_air,
        'avg_pollution_water': avg_water,
        'avg_pollution_soil': avg_soil,
        'composite_toxicity': avg_air * 0.35 + avg_water * 0.40 + avg_soil * 0.25,
    }
