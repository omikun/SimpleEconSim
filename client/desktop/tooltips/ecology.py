"""
worldview_tooltips_ecology.py — Tooltips for Phase 3 Ecological Rift, Epidemics, & Medical Economics.

Provides rich floating tooltips explaining mechanisms, strategic utility, and live stats
for Tab 6, chart mode switchers, ecological time-series charts, medical decrees, and clinic buildings.
"""

from __future__ import annotations
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN


def build_ecology_tooltip(btn_id: str, world: dict, region=None, nation=None, province=None) -> dict | None:
    """Resolve tooltip descriptor for ecological, epidemiological, and medical controls."""
    pinned = region or world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    owner = nation or (getattr(pinned, 'owner_nation', None) if pinned else None)
    if owner is None and world.get('nations'):
        owner = world['nations'][0]

    prov = province or (getattr(pinned, 'province', None) if pinned else None)

    # Live stats helpers
    fert = getattr(pinned, 'soil_fertility', 1.0) if pinned else 1.0
    nutr = getattr(pinned, 'nutrition_density', 1.0) if pinned else 1.0
    smog = getattr(pinned, 'pollution_air', 0.0) if pinned else 0.0
    water = getattr(pinned, 'pollution_water', 0.0) if pinned else 0.0
    soil_tox = getattr(pinned, 'pollution_soil', 0.0) if pinned else 0.0

    d_cases = getattr(pinned, 'disease_cases_log', [{}])[-1] if pinned and getattr(pinned, 'disease_cases_log', None) else {}
    if not isinstance(d_cases, dict):
        d_cases = {}
    tot_sick = d_cases.get('total', 0)
    untr = getattr(pinned, 'untreated_cases_log', [0])[-1] if pinned and getattr(pinned, 'untreated_cases_log', None) else 0

    # -------------------------------------------------------------------------
    # 1. COMPARISON MODAL TAB 6: ECOLOGY & PUBLIC HEALTH
    # -------------------------------------------------------------------------
    if btn_id in ('compare_tab_6', 'compare_tab_ecology'):
        return {
            'title': "Comparison Suite: Ecology & Public Health",
            'badge': "METABOLIC RIFT & EPIDEMICS",
            'badge_col': (120, 220, 140),
            'category': "Comparative Geopolitics",
            'cost': "Displays cross-nation, cross-province, and municipal ecological degradation and disease data",
            'desc': [
                "Examines environmental metabolic rift: soil fertility exhaustion, synthetic fertilizer nutrition dilution, coal smog, contaminated river effluent, and chemical pesticide sludge.",
                "Tracks epidemic outbreaks (malnutrition, cholera, smog bronchitis, pesticide poisoning) and healthcare financing (private patient bills vs public treasury subsidies).",
                "Why Useful to Player: Identify regions suffering severe ecological breakdown or infectious collapse, and evaluate whether to subsidize public clinics or mandate environmental remediation."
            ],
            'stats': [
                ("Realm Total Sick", f"{tot_sick:,} active cases", (240, 100, 100) if tot_sick > 0 else GREEN),
                ("Current Selected Tile Fert", f"{fert*100:.0f}%", (130, 215, 120)),
                ("Current Selected Tile Smog", f"{smog:.1f}", (235, 90, 90) if smog > 15 else DIM),
            ],
            'icon': 'chart',
            'btn_id': btn_id
        }

    if btn_id == 'compare_eco_scope_country':
        return {
            'title': "Ecological Scope: Sovereign Nations",
            'badge': "SOVEREIGN AGGREGATION",
            'badge_col': ACCENT,
            'category': "Territorial Aggregation",
            'cost': "Rolls up environmental metrics, infection cases, and healthcare spending per nation",
            'desc': [
                "Aggregates national agricultural depletion, industrial smokestack pollution, and epidemic infection prevalence across all constituent provinces and settlements.",
                "Why Useful to Player: Compare which rival powers are running unsustainable extractive economies that degrade their national workforce's physiological vitality."
            ],
            'stats': [("Aggregation Scope", "Sovereign Nations", ACCENT)],
            'icon': 'globe',
            'btn_id': btn_id
        }

    if btn_id == 'compare_eco_scope_province':
        return {
            'title': "Ecological Scope: Regional Provinces",
            'badge': "PROVINCIAL AGGREGATION",
            'badge_col': (100, 180, 240),
            'category': "Territorial Aggregation",
            'cost': "Rolls up environmental metrics and health data across provincial boundaries",
            'desc': [
                "Groups tiles by province to reveal regional watersheds, soil basins, and regional sanatorium / hospital coverage.",
                "Why Useful to Player: Direct provincial infrastructure funding (e.g. water filtration plants or sanatoriums) to the provinces with the heaviest waterborne and airborne disease burdens."
            ],
            'stats': [("Aggregation Scope", "Regional Provinces", (100, 180, 240))],
            'icon': 'province',
            'btn_id': btn_id
        }

    if btn_id == 'compare_eco_scope_city':
        return {
            'title': "Ecological Scope: Municipal Settlements",
            'badge': "MUNICIPAL SETTLEMENTS",
            'badge_col': (130, 215, 160),
            'category': "Territorial Aggregation",
            'cost': "Displays raw granular stats for every individual city and settlement tile",
            'desc': [
                "Examines localized smokestacks, polluted urban drainage, localized fertilizer runoffs, and specific epidemic caseloads per city tile.",
                "Why Useful to Player: Pinpoint the exact cities requiring immediate brick trunk sewers, wet coal smoke scrubbers, or municipal clinic construction."
            ],
            'stats': [("Aggregation Scope", "Municipal Settlements", (130, 215, 160))],
            'icon': 'city',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 2. SIDEBAR DASHBOARD CHART MODE SWITCHERS
    # -------------------------------------------------------------------------
    if btn_id == 'btn_chart_mode_econ':
        return {
            'title': "Sidebar Dashboard: Macroeconomic Accounts",
            'badge': "MACRO ECONOMY",
            'badge_col': ACCENT,
            'category': "Sidebar View Toggle",
            'cost': "Switches right sidebar to the standard 10-chart economic time-series dashboard",
            'desc': [
                "Displays commodity prices, population & hunger, industrial production, import/export flows, government revenues, Gini inequality & migration, inventories, protest & commons, GDP, and demand ratios.",
                "Why Useful to Player: Monitor commercial liquidity, commodity balances, and market clearing across the local settlement."
            ],
            'stats': [("Dashboard Mode", "Macroeconomic Accounts", ACCENT)],
            'icon': 'chart',
            'btn_id': btn_id
        }

    if btn_id == 'btn_chart_mode_eco':
        return {
            'title': "Sidebar Dashboard: Ecology & Public Health",
            'badge': "ECOLOGY & EPIDEMICS",
            'badge_col': (120, 220, 140),
            'category': "Sidebar View Toggle",
            'cost': "Switches right sidebar to the 6-chart ecological and epidemiological dashboard",
            'desc': [
                "Displays soil fertility vs food nutrition density, atmospheric smog & water pollution & pesticide sludge rifts, active disease caseloads, private medical bills vs public subsidies, untreated sick counts, and physiological bodily wear.",
                "Why Useful to Player: Continuously monitor environmental deterioration and prevent cascading epidemic fatalities."
            ],
            'stats': [
                ("Soil Fertility", f"{fert*100:.0f}%", (130, 215, 120)),
                ("Food Nutrition", f"{nutr*100:.0f}%", (225, 195, 70)),
                ("Active Infections", f"{tot_sick:,} cases", (240, 90, 90) if tot_sick > 0 else GREEN),
            ],
            'icon': 'chart',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 3. PUBLIC HEALTH POLICY DECREES & CLINIC BUILDINGS
    # -------------------------------------------------------------------------
    if btn_id == 'city_toggle_public_healthcare':
        cur_status = getattr(pinned, 'public_healthcare_decree', False) if pinned else False
        return {
            'title': "Municipal Decree: Public Healthcare & Subsidized Clinics",
            'badge': "PUBLIC HEALTH POLICY",
            'badge_col': GREEN if cur_status else (240, 180, 80),
            'category': "Public Health & Social Welfare",
            'cost': "$15–$30 per patient treatment disbursed directly from the Municipal Treasury",
            'desc': [
                "Authorizes the municipal treasury to fully subsidize medical diagnoses, medicines, and clinical treatments for all afflicted citizens.",
                "Mechanism: When enabled, sick workers receive free cures paid by government funds (0 LEAK). If disabled, patients must pay private out-of-pocket bills ($20); impoverished workers who cannot afford medicine remain sick, suffer accelerated bodily wear, despair, and death.",
                "Why Useful to Player: Curtails worker mortality, stops epidemic contagion, and eliminates healthcare bankruptcies among working families."
            ],
            'stats': [
                ("Policy Status", "ENACTED (Subsidized)" if cur_status else "REPEALED (Private Out-of-Pocket)", GREEN if cur_status else (240, 180, 80)),
                ("Untreated Sick (Can't Pay)", f"{untr:,} workers", (235, 80, 80) if untr > 0 else GREEN),
            ],
            'icon': 'policy',
            'btn_id': btn_id
        }

    if btn_id in ('build_municipal_clinic', 'building_municipal_clinic'):
        return {
            'title': "Municipal Apothecary & Clinic",
            'badge': "CIVIC HEALTHCARE",
            'badge_col': (120, 220, 140),
            'category': "Municipal Public Health Infrastructure",
            'cost': "$250.00 | 2 Turns | 3 Wood, 1 Furniture",
            'desc': [
                "Constructs a permanent municipal clinic and apothecary staffed by trained physicians and herbalists.",
                "Increases regional medical cure success rate to 95% and provides subsidized clinical treatments.",
                "Why Useful to Player: Vital for industrial and farming settlements to treat pesticide poisoning, black lung smog, and waterborne epidemics before they decimate the labor force."
            ],
            'stats': [
                ("Cure Rate Bonus", "+15% (Up to 95% success)", GREEN),
                ("Tier", "Tile / City", (140, 190, 240)),
            ],
            'icon': 'hammer',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 4. MEDICAL TECHNOLOGIES
    # -------------------------------------------------------------------------
    if btn_id in ('tech_germ_theory_antisepsis', 'germ_theory_antisepsis'):
        return {
            'title': "Germ Theory & Antiseptic Sanitation",
            'badge': "ERA II MEDICAL SCIENCE",
            'badge_col': (100, 200, 255),
            'category': "Civil Engineering & Epidemiology",
            'cost': "720 Science XP",
            'desc': [
                "Replaces miasma theories with microbiological pathogen identification and antiseptic carbolic acid treatments.",
                "Reduces waterborne cholera transmission by 65% and cuts medical treatment costs by 20%.",
                "Unlocks the Municipal Apothecary & Clinic building recipe."
            ],
            'stats': [("Transmission Reduction", "-65% Waterborne Cholera", GREEN)],
            'icon': 'science',
            'btn_id': btn_id
        }

    if btn_id in ('tech_pharmaceutical_chemistry', 'pharmaceutical_chemistry'):
        return {
            'title': "Synthetic Pharmacology & Chemotherapy",
            'badge': "ERA III INDUSTRIAL MEDICINE",
            'badge_col': (180, 120, 240),
            'category': "Manufacturing & Pharmacology",
            'cost': "1,250 Science XP",
            'desc': [
                "Chemical synthesis of targeted antidotes, antitoxins, and early antibiotics from coal tar derivatives.",
                "Raises clinical cure success rate to 95% and neutralizes chemical pesticide toxicity among farmworkers.",
                "Why Useful to Player: Protects the agrarian workforce when deploying aggressive chemical pesticide mandates."
            ],
            'stats': [("Cure Success Rate", "95% Success", GREEN)],
            'icon': 'science',
            'btn_id': btn_id
        }

    if btn_id in ('tech_universal_healthcare_system', 'universal_healthcare_system'):
        return {
            'title': "Universal Public Healthcare Coverage",
            'badge': "ERA IV SOCIAL WELFARE",
            'badge_col': (240, 200, 80),
            'category': "Finance & Public Welfare",
            'cost': "1,700 Science XP",
            'desc': [
                "State-administered healthcare system guaranteeing free clinical treatment of all epidemic diseases for every citizen.",
                "Reduces government treatment procurement costs by 30% and permanently eliminates out-of-pocket medical bankruptcies.",
                "Why Useful to Player: Maximizes life expectancy, lowers worker despair, and eliminates health-induced protest energy."
            ],
            'stats': [("Healthcare Coverage", "100% Universal Public Coverage", GREEN)],
            'icon': 'science',
            'btn_id': btn_id
        }

    return None
