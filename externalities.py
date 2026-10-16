"""
externalities.py — Ecological Metabolic Rift, Soil Depletion, Fertilizer/Pesticide Tradeoffs,
and Industrial Pollution for Call of Capital.

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
    if not hasattr(region, 'fertilizer_stock'):
        region.fertilizer_stock = 12.0
    if not hasattr(region, 'fertilizer_consumed_last_turn'):
        region.fertilizer_consumed_last_turn = 0.0
    if not hasattr(region, 'fertilizer_inflow_last_turn'):
        region.fertilizer_inflow_last_turn = 0.0
    if not hasattr(region, 'is_nitrate_depleted'):
        region.is_nitrate_depleted = False

    before_ecology = {
        'soil_fertility': region.soil_fertility,
        'nutrition_density': region.nutrition_density,
        'pollution_air': region.pollution_air,
        'pollution_water': region.pollution_water,
        'pollution_soil': region.pollution_soil,
    }

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

    regime = getattr(region, 'farming_regime', 'rotation')
    use_fert = (regime == 'intensive' or getattr(region, 'use_fertilizer', False) or
                getattr(region, 'mandate_fertilizer', False))
    use_pest = getattr(region, 'use_pesticides', False) or getattr(region, 'mandate_pesticides', False)

    # -------------------------------------------------------------------------
    # 0. Global Fertilizer Inflow & Maritime Blockade Mechanics
    # -------------------------------------------------------------------------
    is_coastal = getattr(region, 'is_coast', False) or any(getattr(n, 'is_water', False) for n in getattr(region, 'neighbors', {}).values())
    is_blockaded = False
    try:
        from imperialism import get_imperialism_manager
        is_blockaded = get_imperialism_manager().is_tile_blockaded(region.name)
    except Exception:
        pass

    fert_inflow = 0.0
    # Maritime Guano & Nitrate Shipments
    if is_coastal and not is_blockaded:
        if 'mineral_nitrates' in unlocked_techs or not unlocked_techs:
            fert_inflow += 3.0

    # Domestic Haber-Bosch Synthetic Nitrogen Fixation
    if 'synthetic_fertilizers' in unlocked_techs:
        industrial_count = sum(1 for a in getattr(region, 'agents', [])
                               if getattr(a, 'output', None) in (Goods.wood, Goods.furniture)
                               and getattr(a, 'is_corporation', False))
        if industrial_count > 0:
            fert_inflow += 4.0  # Domestic synthesis immune to naval blockade

    region.fertilizer_stock = max(0.0, min(60.0, getattr(region, 'fertilizer_stock', 12.0) + fert_inflow))
    region.fertilizer_inflow_last_turn = fert_inflow

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

    # Soil extraction: intensive monoculture extracts nutrients faster
    extraction_rate = 0.003 * min(10, food_producers) + 0.012 * farm_corps
    enclosed = getattr(getattr(region, 'tenure', None), 'enclosed_fraction', 0.0)
    extraction_rate *= (1.0 + enclosed * 0.5)
    if use_fert or regime == 'intensive':
        extraction_rate *= 1.5

    # Natural and agroecological regeneration
    regen_rate = 0.015  # Baseline natural microbial recovery
    if regime == 'rotation' or has_rotation:
        regen_rate += 0.035  # Four-field rotation with legumes & animal manure
    if has_agroecology:
        regen_rate += 0.030  # Advanced agroecology & compost digestion
    if has_conservation:
        regen_rate += 0.025  # Soil conservation reserve buffer plots
    if getattr(region, 'soil_conservation_subsidy', False):
        regen_rate += 0.020  # Subsidized fallow periods

    # If chemical fertilizer is used, natural soil regeneration is suppressed (microbiome death)
    if use_fert:
        regen_rate *= 0.30

    max_fertility = 1.35 if (regime == 'rotation' and 'arable_silt' in getattr(region, 'terrain', {})) else (1.25 if regime == 'rotation' else 1.10)
    region.soil_fertility = max(0.20, min(max_fertility, region.soil_fertility - extraction_rate + regen_rate))

    # -------------------------------------------------------------------------
    # 2. Food Nutritional Density Dynamics
    # -------------------------------------------------------------------------
    if use_fert:
        # Synthetic nitrogen forces rapid water uptake, diluting protein and micronutrients
        target_nutrition = 0.70
    elif regime == 'rotation' or has_agroecology or has_rotation:
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
    # 4. Water Effluent & Hydrological Downstream River Advection
    # -------------------------------------------------------------------------
    pop_count = len([a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)])
    urban_waste = (pop_count / 80.0) * 1.5
    ind_water_waste = industrial_producers * 1.2
    fert_runoff = 3.5 if use_fert else 0.0

    raw_water_emission = urban_waste + ind_water_waste + fert_runoff

    # Trunk sewer channels wastewater away from city center
    if has_sewer:
        raw_water_emission *= 0.30  # Local water protected, flushes downstream
    if has_filtration or getattr(region, 'clean_water_act', False):
        raw_water_emission *= 0.30  # Filtration plants purify supply

    # Downstream Hydrological Advection along River Corridors
    advected_downstream = 0.0
    downstream_tiles = []
    try:
        from terrain_edges import get_edge_manager
        em = get_edge_manager()
        if em is not None:
            downstream_tiles = em.get_downstream_neighbors(region.name)
            if downstream_tiles:
                # 35% of waterborne pollution flows downstream into neighboring tiles
                advection_frac = 0.35
                if has_sewer:
                    # Bazalgette intercepting sewer cuts downstream effluent discharge by 80%
                    advection_frac *= 0.20
                advected_downstream = (region.pollution_water + raw_water_emission) * advection_frac
                per_tile_advection = advected_downstream / len(downstream_tiles)
                for dt in downstream_tiles:
                    water_before = getattr(dt, 'pollution_water', 0.0)
                    dt.pollution_water = min(100.0, water_before + per_tile_advection)
                    from run_trace import emit
                    emit(dt, kind='pollution_downstream_advection', record_class='calculation',
                         subject={'type': 'tile', 'id': dt.name},
                         metric_id='ecology.pollution_water', unit='index',
                         before=water_before, after=dt.pollution_water,
                         formula_id='ecology.downstream_advection.v1',
                         inputs={'source_tile': region.name,
                                 'source_pollution_before_emission': before_ecology['pollution_water'],
                                 'source_emission': raw_water_emission,
                                 'source_total_advection': advected_downstream,
                                 'downstream_tile_count': len(downstream_tiles),
                                 'advection_fraction': advection_frac,
                                 'tile_share': per_tile_advection},
                         constraints={'upper_cap': 100.0,
                                      'active_cap': dt.pollution_water >= 100.0})

                    # Riparian Diplomatic Grievance & Casus Belli
                    owner_dt = getattr(dt, 'owner_nation', None)
                    owner_self = getattr(region, 'owner_nation', None)
                    if owner_dt and owner_self and owner_dt.name != owner_self.name and per_tile_advection > 1.2:
                        from diplomacy import get_diplomacy
                        dip = get_diplomacy()
                        if dip:
                            dip.adjust_relation(owner_dt.name, owner_self.name, -0.06)
                            factions = getattr(getattr(dt, 'factions', None), 'factions', {})
                            for f in factions.values():
                                f.add_grievance('river_poisoning', 1.5)
                            if dip.get_relation(owner_dt.name, owner_self.name) <= -0.50:
                                cb_set = getattr(owner_dt, 'active_casus_belli', set())
                                cb_set.add((owner_self.name, 'riparian_poisoning'))
                                owner_dt.active_casus_belli = cb_set
    except Exception:
        pass

    # Residual water pollution after downstream flow and dispersion
    region.pollution_water = max(0.0, min(100.0, (region.pollution_water * 0.88 + raw_water_emission) - advected_downstream))

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

    from run_trace import emit
    subject = {'type': 'tile', 'id': region.name}
    emit(region, kind='soil_fertility_update', record_class='calculation',
         subject=subject, metric_id='ecology.soil_fertility', unit='ratio',
         before=before_ecology['soil_fertility'], after=region.soil_fertility,
         formula_id='ecology.soil_balance.v1',
         inputs={'extraction_rate': extraction_rate, 'regeneration_rate': regen_rate,
                 'farming_regime': regime, 'enclosed_fraction': enclosed,
                 'food_producers': food_producers, 'farm_corporations': farm_corps,
                 'fertilizer_used': use_fert, 'rotation': has_rotation,
                 'agroecology': has_agroecology, 'conservation_reserve': has_conservation,
                 'conservation_subsidy': bool(getattr(region, 'soil_conservation_subsidy', False))},
         constraints={'lower_bound': 0.20, 'upper_bound': max_fertility})
    emit(region, kind='nutrition_density_update', record_class='calculation',
         subject=subject, metric_id='ecology.nutrition_density', unit='ratio',
         before=before_ecology['nutrition_density'], after=region.nutrition_density,
         formula_id='ecology.nutrition_transition.v1',
         inputs={'target_density': target_nutrition, 'blend_fraction': 0.25,
                 'fertilizer_used': use_fert, 'farming_regime': regime,
                 'soil_fertility': region.soil_fertility})
    emit(region, kind='pollution_air_update', record_class='calculation',
         subject=subject, metric_id='ecology.pollution_air', unit='index',
         before=before_ecology['pollution_air'], after=region.pollution_air,
         formula_id='ecology.air_emissions_dispersion.v1',
         inputs={'industrial_producers': industrial_producers,
                 'raw_emission_after_controls': raw_air_emission,
                 'smoke_scrubber': has_scrubber, 'coal_intensifier':
                 ('coal_coking' in unlocked_techs or 'steam_engines' in unlocked_techs),
                 'dispersion_fraction': 0.15},
         constraints={'lower_bound': 0.0, 'upper_bound': 100.0})
    emit(region, kind='pollution_water_update', record_class='calculation',
         subject=subject, metric_id='ecology.pollution_water', unit='index',
         before=before_ecology['pollution_water'], after=region.pollution_water,
         formula_id='ecology.water_emissions_advection.v1',
         inputs={'urban_emission': urban_waste, 'industrial_emission': ind_water_waste,
                 'fertilizer_runoff': fert_runoff, 'raw_emission': raw_water_emission,
                 'downstream_advection': advected_downstream,
                 'dispersion_fraction': 0.12, 'sewer': has_sewer,
                 'filtration_or_clean_water_act': has_filtration or getattr(region, 'clean_water_act', False),
                 'downstream_tiles': [dt.name for dt in downstream_tiles]},
         constraints={'lower_bound': 0.0, 'upper_bound': 100.0})
    emit(region, kind='pollution_soil_update', record_class='calculation',
         subject=subject, metric_id='ecology.pollution_soil', unit='index',
         before=before_ecology['pollution_soil'], after=region.pollution_soil,
         formula_id='ecology.soil_toxins_biodegradation.v1',
         inputs={'pesticide_runoff': pesticide_runoff,
                 'scrubber_sludge': sludge_generated,
                 'raw_soil_emission': raw_soil_emission,
                 'biodegradation_fraction': 0.08},
         constraints={'lower_bound': 0.0, 'upper_bound': 100.0})

    return get_tile_metabolic_state(region)


def apply_environmental_health_wear(region):
    """Inflict physiological wear-and-tear from smog, bad water, toxic spray, and depleted food."""
    use_pest = region.use_pesticides or getattr(region, 'mandate_pesticides', False)
    nation = getattr(region, 'owner_nation', None)
    has_clean_pest = 'biological_pest_control' in getattr(nation, 'unlocked_techs', set()) if nation else False

    for a in getattr(region, 'agents', []):
        if not getattr(a, 'alive', True) or getattr(a, 'is_corporation', False) or getattr(a, 'is_government', False):
            continue

        attrition_sources = {'air_pollution': 0.0, 'water_pollution': 0.0,
                             'direct_pesticide_exposure': 0.0, 'soil_toxicity': 0.0,
                             'low_nutrition': 0.0}

        # 1. Smog inhalation (particulate matter & sulfur)
        if region.pollution_air > 15.0:
            attrition_sources['air_pollution'] = 0.0015 * (region.pollution_air - 15.0)

        # 2. Contaminated drinking water (cholera, heavy metals)
        if region.pollution_water > 20.0:
            attrition_sources['water_pollution'] = 0.0020 * (region.pollution_water - 20.0)

        # 3. Direct pesticide exposure (agricultural laborers handle toxic spray)
        if use_pest and not has_clean_pest and getattr(a, 'output', None) == Goods.food:
            attrition_sources['direct_pesticide_exposure'] = 0.040
        elif region.pollution_soil > 25.0:
            attrition_sources['soil_toxicity'] = 0.0015 * (region.pollution_soil - 25.0)

        # 4. Poor food nutritional density (micronutrient deficiency)
        if region.nutrition_density < 0.85:
            attrition_sources['low_nutrition'] = 0.025 * (1.0 - region.nutrition_density)

        attrition_delta = sum(attrition_sources.values())
        if attrition_delta > 0.0:
            attrition_before = float(getattr(a, 'health_attrition', 0.0))
            a.health_attrition = attrition_before + attrition_delta
            from run_trace import emit
            emit(region, kind='environmental_health_attrition', record_class='calculation',
                 subject={'type': 'tile', 'id': region.name,
                          'agent_id': getattr(a, 'id', None)},
                 metric_id='health.attrition', unit='attrition_points',
                 before=attrition_before, after=a.health_attrition,
                 formula_id='health.environmental_exposure_wear.v1',
                 inputs={'attrition_delta': attrition_delta,
                         'source_components': attrition_sources,
                         'air_pollution': region.pollution_air,
                         'water_pollution': region.pollution_water,
                         'soil_toxicity': region.pollution_soil,
                         'nutrition_density': region.nutrition_density,
                         'pesticide_use': use_pest,
                         'biological_pest_control': has_clean_pest,
                         'agent_output': getattr(getattr(a, 'output', None), 'name', None)})


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
        'fertilizer_stock': getattr(region, 'fertilizer_stock', 12.0),
        'fertilizer_consumed': getattr(region, 'fertilizer_consumed_last_turn', 0.0),
        'fertilizer_inflow': getattr(region, 'fertilizer_inflow_last_turn', 0.0),
        'is_nitrate_depleted': getattr(region, 'is_nitrate_depleted', False),
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
            'total_fertilizer_stock': 0.0,
            'composite_toxicity': 0.0,
            'any_nitrate_depleted': False,
        }
    n = len(tiles)
    avg_fert = sum(getattr(t, 'soil_fertility', 1.0) for t in tiles) / n
    avg_nutr = sum(getattr(t, 'nutrition_density', 1.0) for t in tiles) / n
    avg_air = sum(getattr(t, 'pollution_air', 0.0) for t in tiles) / n
    avg_water = sum(getattr(t, 'pollution_water', 0.0) for t in tiles) / n
    avg_soil = sum(getattr(t, 'pollution_soil', 0.0) for t in tiles) / n
    tot_fert = sum(getattr(t, 'fertilizer_stock', 0.0) for t in tiles)
    any_depleted = any(getattr(t, 'is_nitrate_depleted', False) for t in tiles)
    return {
        'avg_soil_fertility': avg_fert,
        'avg_nutrition_density': avg_nutr,
        'avg_pollution_air': avg_air,
        'avg_pollution_water': avg_water,
        'avg_pollution_soil': avg_soil,
        'total_fertilizer_stock': tot_fert,
        'any_nitrate_depleted': any_depleted,
        'composite_toxicity': avg_air * 0.35 + avg_water * 0.40 + avg_soil * 0.25,
    }
