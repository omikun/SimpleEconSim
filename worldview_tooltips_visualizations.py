"""
worldview_tooltips_visualizations.py — Tooltips for Phase 1, 2, & 3 Specialized Visualizations.
Provides rich floating tooltips explaining mechanics, strategic utility, and stats.
"""

from __future__ import annotations
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN


def build_visualization_tooltip(btn_id: str, world: dict, region=None, nation=None, province=None) -> dict | None:
    """Resolve tooltip descriptor for visualization controls, modes, and column headers."""
    pinned = region or world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    owner = nation or (getattr(pinned, 'owner_nation', None) if pinned else None)
    if owner is None and world.get('nations'):
        owner = world['nations'][0]

    # Live metric extraction helpers
    pop_count = len(getattr(pinned, 'agents', [])) if pinned else 0
    shifts = getattr(pinned, 'avg_shift_hours_log', []) if pinned else []
    avg_shift = shifts[-1] if shifts else 8.0
    sv_log = getattr(pinned, 'rate_of_exploitation_log', []) if pinned else []
    sv_rate = sv_log[-1] if sv_log else 0.5
    strikers = getattr(pinned, 'strikers_log', [0])[-1] if pinned and getattr(pinned, 'strikers_log', None) else 0
    broken = getattr(pinned, 'broken_machinery_log', [0])[-1] if pinned and getattr(pinned, 'broken_machinery_log', None) else 0
    protest_e = getattr(pinned, 'protest_energy_log', [0.0])[-1] if pinned and getattr(pinned, 'protest_energy_log', None) else 0.0
    tenure = getattr(pinned, 'tenure', None)
    commons_pct = (tenure.commons_access * 100.0) if tenure else 100.0
    rent_collected = getattr(pinned, 'rent_collected_log', [0.0])[-1] if pinned and getattr(pinned, 'rent_collected_log', None) else 0.0
    prov = province or (getattr(pinned, 'province', None) if pinned else None)
    prov_gov = getattr(prov, 'gov', None) if prov else None
    prov_cash = (prov_gov.agent.cash if prov_gov and hasattr(prov_gov, 'agent') else 0.0)

    # -------------------------------------------------------------------------
    # 1. COMPARISON MODAL TAB 4: EXTRACTION & CIRCUIT OF CAPITAL
    # -------------------------------------------------------------------------
    if btn_id == 'compare_ext_scope_country':
        return {
            'title': "Extraction Scope: Sovereign Nations",
            'badge': "SOVEREIGN LEVEL",
            'badge_col': ACCENT,
            'category': "Territorial Aggregation",
            'cost': "Aggregates total tribute, rent, surplus value, and taxes per nation",
            'desc': [
                "Summarizes all extractive flows across all constituent provinces and cities into sovereign national totals.",
                "Why Useful to Player: Compare total national wealth extraction, overall rate of exploitation (s/v), and national health degradation between sovereign powers."
            ],
            'stats': [("Aggregation Scope", "Sovereign Nations", ACCENT)],
            'icon': 'globe',
            'btn_id': btn_id
        }

    if btn_id == 'compare_ext_scope_province':
        return {
            'title': "Extraction Scope: Regional Provinces",
            'badge': "PROVINCIAL LEVEL",
            'badge_col': (100, 180, 240),
            'category': "Territorial Aggregation",
            'cost': "Aggregates extractive transfers and taxes per province",
            'desc': [
                "Breaks down wealth extraction across distinct geographic provinces, showing provincial tax retention and local surplus accumulation.",
                "Why Useful to Player: Identify uneven regional development, pinpointing provinces where heavy tribute or landlord rent is choking economic dynamism."
            ],
            'stats': [("Aggregation Scope", "Regional Provinces", (100, 180, 240))],
            'icon': 'province',
            'btn_id': btn_id
        }

    if btn_id == 'compare_ext_scope_city':
        return {
            'title': "Extraction Scope: Cities & Hex Tiles",
            'badge': "MUNICIPAL LEVEL",
            'badge_col': (245, 210, 85),
            'category': "Territorial Aggregation",
            'cost': "Displays individual granular data for every settlement and rural tile",
            'desc': [
                "Displays granular extraction line-items for each individual tile: local municipal revenue, specific landlord rent, and factory surplus value.",
                "Why Useful to Player: Pinpoint the exact cities suffering acute physical wear or high worker alienation before local labor strikes break out."
            ],
            'stats': [("Aggregation Scope", "Cities / Individual Tiles", (245, 210, 85))],
            'icon': 'city',
            'btn_id': btn_id
        }

    if btn_id == 'compare_ext_mode_table':
        return {
            'title': "View Mode: Data Table Ledger",
            'badge': "COMPARATIVE TABULAR",
            'badge_col': (220, 185, 65),
            'category': "Accounts View Mode",
            'cost': "Displays line-item extraction metrics across all territories",
            'desc': [
                "Presents an exhaustive comparative tabular breakdown of all wealth extraction channels: Feudal Tribute, Ground Rent, Surplus Value, and Multi-Tier Government Taxes.",
                "Why Useful to Player: Allows exact numeric comparisons between regions. Easily identify which provinces generate the highest surplus profits or where rent extraction is causing catastrophic health attrition."
            ],
            'stats': [("Active Mode", "Tabular Extraction Ledger", (220, 185, 65))],
            'icon': 'scale',
            'btn_id': btn_id
        }

    if btn_id == 'compare_ext_mode_circuit':
        return {
            'title': "View Mode: Marxian Circuit of Capital & TRPF",
            'badge': "CIRCULAR FLOW SANKEY",
            'badge_col': (245, 210, 85),
            'category': "Analytical Visualizer",
            'cost': "Displays 5-stage Sankey diagram (M->C->P->C'->M') and TRPF curve",
            'desc': [
                "Visualizes the complete macro-circuit of capital accumulation: Money Capital (M) purchasing Constant Inputs (C) and Variable Labor (V), entering Production (P) to extract Surplus Value, and realizing Commodities (C') on the market.",
                "Why Useful to Player: Reveals the class split of realized surplus (machinery reinvestment vs luxury vs anti-labor PAC funds) against worker wage outlays (subsistence, rent, despair vices, spectacle). In the bottom curve, monitor the Tendency of the Rate of Profit to Fall (TRPF) as constant capital (c/v) accumulates."
            ],
            'stats': [
                ("Circuit Stages", "M -> C & V -> P -> C' -> Splits", (245, 210, 85)),
                ("TRPF Plot", "Organic Composition (c/v) vs Profit %", (100, 180, 240)),
            ],
            'icon': 'bank',
            'btn_id': btn_id
        }

    if btn_id == 'circuit_nation_btn':
        return {
            'title': "Nation Circuit Switcher",
            'badge': "SOVEREIGN SELECTION",
            'badge_col': ACCENT,
            'category': "Circuit Visualizer Control",
            'cost': "Click to switch the active nation displayed in the Sankey diagram",
            'desc': [
                "Switches the Marxian Circuit of Capital Sankey diagram and TRPF curve to another sovereign nation in the world.",
                "Why Useful to Player: Directly compare how rival empires allocate capital: discover whether foreign competitors are reinvesting in heavy machinery or squandering surplus on luxury and political lobbying."
            ],
            'stats': [("Selected Nation", owner.name if owner else "Imperial Realm", ACCENT)],
            'icon': 'crown',
            'btn_id': btn_id
        }

    if btn_id == 'trpf_curve_plot':
        return {
            'title': "TRPF & Organic Composition of Capital (c/v)",
            'badge': "HISTORICAL DYNAMICS",
            'badge_col': (100, 180, 240),
            'category': "Macroeconomic Theory",
            'cost': "Plots c/v ratio (blue), profit rate % (gold), and shift hours (red)",
            'desc': [
                "Demonstrates the Tendency of the Rate of Profit to Fall (TRPF). As capitalists compete by accumulating more machinery relative to living labor (higher c/v), the rate of profit tendentially declines because only living labor yields surplus value.",
                "Why Useful to Player: Explains why capitalists aggressively lengthen shift hours (red line) to counteract falling profit rates. When profit rates drop, expect corporations to push for longer shifts or slash wages."
            ],
            'stats': [
                ("Organic Comp (c/v)", "Constant capital over wage bill", (100, 180, 240)),
                ("Rate of Profit", "Surplus value over (C + V)", (245, 210, 80)),
                ("Shift Pressure", "Offsetting mechanism via longer shifts", RED),
            ],
            'icon': 'machinery',
            'btn_id': btn_id
        }

    # Tab 4 Column Headers
    if btn_id == 'hdr_ext_tribute':
        return {
            'title': "Column: Feudal Tribute (Serfs)",
            'badge': "IN-KIND CORVEE",
            'badge_col': (220, 185, 65),
            'category': "Feudal Extraction",
            'cost': "Value of agrarian produce transferred directly from serfs to lords",
            'desc': [
                "Quantifies customary feudal dues and in-kind food tribute delivered by customary serfs to regional lords and gentry.",
                "Why Useful to Player: Measures feudal lord enrichment. High tribute enriches the aristocracy but limits peasant purchasing power on open consumer markets."
            ],
            'stats': [("Extraction Channel", "Customary Feudal Tenure", (220, 185, 65))],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id == 'hdr_ext_rent':
        return {
            'title': "Column: Ground Rent (Tenants)",
            'badge': "CASH RENT EXTRACTED",
            'badge_col': (235, 125, 55),
            'category': "Agrarian Capital",
            'cost': "Cash rental fees charged by landlords on enclosed plots",
            'desc': [
                "Measures total monetary ground rent collected from agricultural tenant farmers cultivating enclosed private land.",
                "Why Useful to Player: Direct indicator of peasant dispossession. High rents drive tenants into debt arrears, leading to evictions and rural rebellions."
            ],
            'stats': [("Extraction Channel", "Enclosed Landed Property", (235, 125, 55))],
            'icon': 'gentry',
            'btn_id': btn_id
        }

    if btn_id == 'hdr_ext_surplus':
        return {
            'title': "Column: Surplus Value (s/v)",
            'badge': "UNPAID LIVING LABOR",
            'badge_col': (225, 65, 75),
            'category': "Industrial Capital",
            'cost': "Value created by wage laborers in excess of their wages paid",
            'desc': [
                "Measures the total monetary surplus value extracted from industrial workers by workshops and corporations.",
                "Why Useful to Player: The primary engine of capitalist accumulation. High surplus value boosts industrial profits and state tax revenues, but fuels workplace alienation and strike risks."
            ],
            'stats': [("Extraction Channel", "Wage Labor Exploitation", (225, 65, 75))],
            'icon': 'labor',
            'btn_id': btn_id
        }

    if btn_id == 'hdr_ext_exploit':
        return {
            'title': "Column: Rate of Exploitation (s/v %)",
            'badge': "EXPLOITATION INTENSITY",
            'badge_col': RED,
            'category': "Marxian Ratio",
            'cost': "Ratio of Surplus Value to Variable Capital: s / v",
            'desc': [
                "The percentage ratio of surplus labor time to necessary subsistence labor time. A rate of 100% means the worker spends half the day working for their own wage and half the day creating pure capitalist profit.",
                "Why Useful to Player: Gauges the intensity of labor exploitation. Rates above 100% trigger rapid worker health attrition, high class consciousness, and severe strike vulnerability."
            ],
            'stats': [("Current Tile s/v", f"{sv_rate*100:.0f}%", RED if sv_rate > 1.0 else (240, 180, 80))],
            'icon': 'labor',
            'btn_id': btn_id
        }

    if btn_id in ('hdr_ext_tax_muni', 'hdr_ext_tax_prov', 'hdr_ext_tax_nat', 'hdr_ext_tax_sov'):
        tier_name = "Municipal (City)" if 'muni' in btn_id else ("Provincial" if 'prov' in btn_id else "Sovereign (Imperial)")
        return {
            'title': f"Column: {tier_name} Statutory Tax",
            'badge': "FISCAL FEDERALISM",
            'badge_col': (75, 155, 235),
            'category': "Public Revenue Capture",
            'cost': "Taxes legally captured by each governing administrative tier",
            'desc': [
                f"Measures the statutory revenue share automatically distributed to the {tier_name} government.",
                "Why Useful to Player: Under fiscal federalism, public funds are split between local cities (policing, relief), provinces (regional equalization), and the national sovereign (army, tech, UBI). Check this to ensure lower tiers are not starving for budget."
            ],
            'stats': [("Administrative Tier", tier_name, (75, 155, 235))],
            'icon': 'scale',
            'btn_id': btn_id
        }

    if btn_id in ('hdr_ext_total', 'hdr_ext_total_ext'):
        return {
            'title': "Column: Total Class Wealth Extraction",
            'badge': "AGGREGATE EXTRACTION",
            'badge_col': (255, 220, 120),
            'category': "Cumulative Transfer",
            'cost': "Sum of Feudal Tribute + Ground Rent + Surplus Value",
            'desc': [
                "The total volume of economic wealth siphoned away from working producers (serfs, tenants, wage laborers) into the hands of non-working property owners (lords, landlords, capitalists).",
                "Why Useful to Player: Unveils which territories act as the primary extractive hubs of the empire, and where the economic surplus is concentrated."
            ],
            'stats': [("Aggregate Total", "Tribute + Rent + Surplus Value", (255, 220, 120))],
            'icon': 'pyramid',
            'btn_id': btn_id
        }

    if btn_id in ('hdr_ext_attrition', 'hdr_ext_wear'):
        return {
            'title': "Column: Physical Health Wear & Workplace Casualties",
            'badge': "BODILY DEGRADATION",
            'badge_col': (235, 80, 90),
            'category': "Public Health Index",
            'cost': "Physiological wear-and-tear score plus recorded workplace injuries",
            'desc': [
                "Quantifies bodily damage inflicted upon the labor force through long shift hours, dangerous unshielded machinery, and toxic workshop air.",
                "Why Useful to Player: Direct predictor of premature mortality. Passing the Factory Safety Mandate or shortening workdays immediately reduces this attrition rate."
            ],
            'stats': [("Health Wear", f"{avg_shift:.1f}h shift impact", (235, 80, 90))],
            'icon': 'hazard',
            'btn_id': btn_id
        }

    if btn_id in ('hdr_ext_alienation', 'hdr_ext_alien'):
        return {
            'title': "Column: 4D Alienation Spectrum %",
            'badge': "PSYCHIC SEVERANCE",
            'badge_col': (175, 105, 235),
            'category': "Social Psychology",
            'cost': "Composite index across Product, Process, Nature, and Species",
            'desc': [
                "Measures the psychological estrangement of citizens: disconnected from what they produce, alienated from the monotonous labor process, separated from nature, and stripped of creative agency.",
                "Why Useful to Player: Highly alienated citizens resort to escapist despair spending (taverns/vice) and are prone to sudden revolutionary mobilization unless pacified by state spectacles."
            ],
            'stats': [("4D Index", "Product + Process + Nature + Species", (175, 105, 235))],
            'icon': 'alienation',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 2. COMPARISON MODAL TAB 5: PROTEST & REBELLION ATTRACTOR
    # -------------------------------------------------------------------------
    if btn_id == 'compare_protest_scope_country':
        return {
            'title': "Protest Scope: Sovereign Nations",
            'badge': "SOVEREIGN AGGREGATE",
            'badge_col': (235, 75, 75),
            'category': "Grievance Aggregation",
            'cost': "Aggregates national civil protest energy and macro grievance drivers",
            'desc': [
                "Summarizes total civil unrest, riot risks, and percentage breakdown of grievance sources at the sovereign state level.",
                "Why Useful to Player: Compare stability across nations and determine which countries face systemic collapse from class conflict or famine."
            ],
            'stats': [("Aggregation Scope", "Sovereign Nations", (235, 75, 75))],
            'icon': 'protest',
            'btn_id': btn_id
        }

    if btn_id == 'compare_protest_scope_province':
        return {
            'title': "Protest Scope: Regional Provinces",
            'badge': "PROVINCIAL SUITE",
            'badge_col': (245, 140, 60),
            'category': "Grievance Aggregation",
            'cost': "Breaks down civil protest scores and drivers by province",
            'desc': [
                "Analyzes protest energy across individual provinces, highlighting regional hotbeds of agrarian or industrial resentment.",
                "Why Useful to Player: Direct provincial garrison troops or targeted infrastructure investments to quell unrest in specific agitated provinces."
            ],
            'stats': [("Aggregation Scope", "Regional Provinces", (245, 140, 60))],
            'icon': 'province',
            'btn_id': btn_id
        }

    if btn_id == 'compare_protest_scope_city':
        return {
            'title': "Protest Scope: Cities & Hex Tiles",
            'badge': "MUNICIPAL SUITE",
            'badge_col': (235, 90, 90),
            'category': "Grievance Aggregation",
            'cost': "Granular protest scores and primary grievance driver per settlement",
            'desc': [
                "Displays exact protest scores, strike casualties, food deprivation levels, and the dominant grievance driver for each settlement.",
                "Why Useful to Player: Pinpoint the exact city on the verge of open insurrection and diagnose its specific cause (e.g. bread starvation vs brutal 14h factory shifts)."
            ],
            'stats': [("Aggregation Scope", "Cities / Individual Tiles", (235, 90, 90))],
            'icon': 'city',
            'btn_id': btn_id
        }

    if btn_id == 'compare_protest_mode_table':
        return {
            'title': "View Mode: Grievance Sources Table",
            'badge': "ROOT CAUSE BREAKDOWN",
            'badge_col': (235, 70, 70),
            'category': "Unrest Analysis View",
            'cost': "Displays percentage breakdown across 8 distinct grievance drivers",
            'desc': [
                "Presents an exact accounting of why citizens are protesting in each territory: Overworked Shifts, Rent Extraction, Food Deprivation, Workplace Casualties, or State Taxes.",
                "Why Useful to Player: Never guess why riots are spreading. Check the table to apply the exact legislative remedy needed (e.g. food subsidies for hunger, workday caps for overwork, curfew for riots)."
            ],
            'stats': [("Active Mode", "Grievance Breakdown Table", (235, 70, 70))],
            'icon': 'protest',
            'btn_id': btn_id
        }

    if btn_id == 'compare_protest_mode_attractor':
        return {
            'title': "View Mode: The Rebellion Attractor (Phase-Space)",
            'badge': "2D DYNAMIC DYNAMICAL SYSTEM",
            'badge_col': (220, 60, 60),
            'category': "Non-Linear Stability Plot",
            'cost': "Plots Shift Hours (X) vs Class Consciousness (Y) with strike hazard zone",
            'desc': [
                "Maps every city and province onto a 2-dimensional phase-space plot: X-axis is Workday Shift Length (8h to 16h), Y-axis is Proletarian Class Consciousness (0.0 to 1.0).",
                "Why Useful to Player: Directly reveals territories drifting toward the crimson Hazard Attractor Zone (>10h shift, >0.40 consciousness), where workers initiate wildcat strikes and smash machinery. Downward blue vectors show the dampening effect of mass public entertainment."
            ],
            'stats': [
                ("Hazard Threshold", "Shifts > 10h & Consc > 0.40", RED),
                ("Bubble Size", "Proportional to population", TEXT),
                ("Bubble Color", "Green (<2), Amber (2-4), Red (>4 Unrest)", ACCENT),
            ],
            'icon': 'sabotage',
            'btn_id': btn_id
        }

    if btn_id == 'attractor_hazard_zone':
        return {
            'title': "Wildcat Strike & Luddite Sabotage Hazard Zone",
            'badge': "CRITICAL THRESHOLD",
            'badge_col': RED,
            'category': "Phase-Space Hazard Region",
            'cost': "Active when Shift Length > 10.0h and Class Consciousness > 0.40",
            'desc': [
                "The crimson cross-hatched region in the top-right of the phase-space plot. When a city's conditions cross into this zone, industrial discipline collapses into spontaneous factory walkouts and physical machinery smashing.",
                "Why Useful to Player: Pull territories out of this hazard zone by passing the Ten-Hour Act (shifting left) or funding mass entertainment spectacles (shifting downward)."
            ],
            'stats': [
                ("Trigger X", "Shift Hours > 10.0h", (240, 100, 100)),
                ("Trigger Y", "Class Consciousness > 40%", (240, 75, 75)),
                ("Consequences", "Factory work halts, machines smashed", RED),
            ],
            'icon': 'sabotage',
            'btn_id': btn_id
        }

    if btn_id == 'attractor_pacification_vector':
        return {
            'title': "Mass Entertainment Pacification Vector",
            'badge': "CULTURAL HEGEMONY",
            'badge_col': (70, 195, 235),
            'category': "Downward Damping Force",
            'cost': "Generated by state subsidies to theatres, circuses, and carnivals",
            'desc': [
                "The cyan arrows pointing downward from phase-space bubbles. Represents the pacifying force of mass commercial spectacle, dulling revolutionary consciousness.",
                "Why Useful to Player: Demonstrates how bread and circuses keep overworked populations docile. Use spectacle subsidies ($50) to push restless territories away from the strike threshold."
            ],
            'stats': [("Vector Direction", "Pulls Consciousness Downwards", (70, 195, 235))],
            'icon': 'theatre',
            'btn_id': btn_id
        }

    if btn_id == 'hdr_protest_score':
        return {
            'title': "Column: Civil Protest Score",
            'badge': "MASS MOBILIZATION",
            'badge_col': (235, 75, 75),
            'category': "Unrest Accounting",
            'cost': "Dynamic index combining all unresolved grievances and class friction",
            'desc': [
                "Composite index of civil unrest and insurgent tension in this territory. Computed dynamically from the sum of unresolved grievances: brutal workday overwork, enclosure dispossession, hunger starvation, workplace casualties, and tax burdens.",
                "Why Useful to Player: Monitor this value closely. Scores above 3.0 trigger localized riots and barricades; scores above 6.0 spark nationwide revolution."
            ],
            'stats': [("Danger Level", ">3.0 Riots / >6.0 Insurrection", (235, 75, 75))],
            'icon': 'protest',
            'btn_id': btn_id
        }

    if btn_id in ('hdr_protest_overwork', 'hdr_protest_shifts'):
        return {
            'title': "Column: Overworked Shifts Grievance (%)",
            'badge': "EXHAUSTION PROTEST",
            'badge_col': (240, 140, 50),
            'category': "Labor Grievance",
            'cost': "Percentage of local unrest driven by grueling 10h-16h shifts",
            'desc': [
                "Percentage of total local civil grievance stemming from excessive shift hours and exhaustion under grueling industrial workdays.",
                "Why Useful to Player: If high, placate workers immediately by reducing statutory shift hours [-1 Hour] or passing the Ten-Hour Act."
            ],
            'stats': [("Remedy", "Pass Workday Cap [-1 Hour]", (240, 140, 50))],
            'icon': 'clock',
            'btn_id': btn_id
        }

    if btn_id in ('hdr_protest_enclosure', 'hdr_protest_rent'):
        return {
            'title': "Column: Rent & Enclosure Grievance (%)",
            'badge': "LANDLORD RESENTMENT",
            'badge_col': (215, 175, 75),
            'category': "Agrarian Grievance",
            'cost': "Percentage of unrest caused by lost commons and landlord rent",
            'desc': [
                "Percentage of local grievance generated by customary commons privatization and burdensome tenant cash rents paid to aristocrats and landlords.",
                "Why Useful to Player: If this dominates, peasants are on the verge of rebellion. Lower land taxes, freeze rents, or halt further enclosure policies."
            ],
            'stats': [("Remedy", "Commons Preservation / Rent Relief", (215, 175, 75))],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id in ('hdr_protest_hunger', 'hdr_protest_food'):
        return {
            'title': "Column: Food Deprivation Grievance (%)",
            'badge': "SUBSISTENCE THREAT",
            'badge_col': (225, 70, 70),
            'category': "Biological Survival",
            'cost': "Percentage of unrest driven by food shortages and starvation",
            'desc': [
                "Percentage of grievance caused by food shortages, elevated grain prices, and outright calorie starvation.",
                "Why Useful to Player: Hunger unrest triggers rapid urban bread riots. Release emergency grain reserves or subsidize food imports to drop market prices."
            ],
            'stats': [("Remedy", "Release Grain Reserves / Food Subsidies", (225, 70, 70))],
            'icon': 'food',
            'btn_id': btn_id
        }

    if btn_id == 'hdr_protest_strikes':
        return {
            'title': "Column: Strikes & Casualties Grievance (%)",
            'badge': "WORKPLACE RADICALISM",
            'badge_col': (235, 90, 90),
            'category': "Industrial Grievance",
            'cost': "Percentage of unrest from factory walkouts and machinery accidents",
            'desc': [
                "Percentage of grievance fueled by machine accidents, workplace deaths, and spontaneous wildcat strike crackdowns.",
                "Why Useful to Player: Reflects active labor strife. Indicates whether factories need workplace safety reforms or pacification spectacles."
            ],
            'stats': [("Remedy", "Factory Acts / Safety Regulations", (235, 90, 90))],
            'icon': 'sabotage',
            'btn_id': btn_id
        }

    if btn_id in ('hdr_protest_state', 'hdr_protest_taxes'):
        return {
            'title': "Column: Taxes & State Repression Grievance (%)",
            'badge': "STATE BACKLASH",
            'badge_col': (190, 100, 220),
            'category': "Fiscal Resistance",
            'cost': "Percentage of unrest driven by multi-tier taxes and police coercion",
            'desc': [
                "Percentage of grievance driven by burdensome multi-tier government taxation (municipal, provincial, sovereign) and heavy-handed gendarmerie policing.",
                "Why Useful to Player: High state grievances indicate the population feels squeezed by the state treasury. Lower taxes or offer public services to reduce friction."
            ],
            'stats': [("Remedy", "Lower Tax Rates / De-escalate Policing", (190, 100, 220))],
            'icon': 'treasury',
            'btn_id': btn_id
        }

    if btn_id == 'hdr_protest_driver':
        return {
            'title': "Column: Primary Grievance Driver",
            'badge': "ROOT CAUSE DIAGNOSTIC",
            'badge_col': ACCENT,
            'category': "Diagnostic Summary",
            'cost': "Identifies the single largest contributor to unrest in this territory",
            'desc': [
                "Identifies the single largest contributor to unrest in this territory (e.g. Overworked Shifts, Food Deprivation, Rent & Enclosure, Strikes, Taxation).",
                "Why Useful to Player: Instantly reveals the exact systemic failure destabilizing the region so you can apply the targeted legislative or economic solution."
            ],
            'stats': [("Diagnostic", "Dominant Restlessness Factor", ACCENT)],
            'icon': 'scale',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 3. RIGHT-HAND PANEL: CITIZENS & WEALTH STRATIFICATION
    # -------------------------------------------------------------------------
    if btn_id == 'citizen_mode_charts':
        return {
            'title': "View Mode: Historical Class Time-Series",
            'badge': "LONGITUDINAL TRENDS",
            'badge_col': ACCENT,
            'category': "Citizen Status View",
            'cost': "Displays 4 time-series charts of class transformation",
            'desc': [
                "Renders 4 longitudinal charts tracking Social Classes headcount, Food Sourcing (commons vs market), Enclosure & Rent burdens, and Gini vs Protest over historical turns.",
                "Why Useful to Player: Analyze long-term structural trends in your society, tracking how customary feudal peasants transform into market-dependent urban wage laborers."
            ],
            'stats': [("Active Mode", "4-Chart Longitudinal Grid", ACCENT)],
            'icon': 'pyramid',
            'btn_id': btn_id
        }

    if btn_id == 'citizen_mode_pyramid':
        return {
            'title': "View Mode: Class Stratification Pyramid & Lorenz Curve",
            'badge': "CROSS-SECTIONAL WEALTH",
            'badge_col': (245, 210, 80),
            'category': "Inequality Suite",
            'cost': "Displays 4-tier demographic wealth pyramid and live Lorenz curve",
            'desc': [
                "Presents an instantaneous cross-sectional analysis of society: a 4-tier demographic wealth pyramid (Bourgeoisie/Gentry, Artisans, Wage Workers, Dispossessed) alongside a live Lorenz inequality curve with computed Gini index.",
                "Why Useful to Player: Instantly evaluate the concentration of private wealth. Detect oligarchic inequality before popular revolution erupts."
            ],
            'stats': [
                ("Top Tier", "Bourgeoisie & High Gentry", (245, 210, 80)),
                ("Base Tier", "Wage Workers, Serfs & Dispossessed", (235, 90, 90)),
                ("Lorenz Gini", "Live inequality coefficient", (230, 185, 70)),
            ],
            'icon': 'pyramid',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 4. RIGHT-HAND PANEL: LABOR & 4D ALIENATION RADAR
    # -------------------------------------------------------------------------
    if btn_id == 'labor_mode_charts':
        return {
            'title': "View Mode: Labor Historical Time-Series",
            'badge': "WORKPLACE TRENDS",
            'badge_col': (230, 90, 90),
            'category': "Labor Analytics View",
            'cost': "Displays 4 historical charts of workplace struggle",
            'desc': [
                "Tracks the evolution of the workday over time: Workday Shifts vs Legal Caps vs Surplus Value (s/v), Alienation & Health Hazards, Consciousness vs Spectacle, and Wildcat Strikes vs Machine Sabotage.",
                "Why Useful to Player: Monitor whether recent labor policies (such as the Ten-Hour Act) are successfully dampening strikes and stabilizing workplace output."
            ],
            'stats': [("Active Mode", "4 Labor Trend Charts", (230, 90, 90))],
            'icon': 'labor',
            'btn_id': btn_id
        }

    if btn_id == 'labor_mode_radar':
        return {
            'title': "View Mode: 4D Alienation Spider / Radar Chart",
            'badge': "POLAR SPECTRUM",
            'badge_col': (180, 120, 220),
            'category': "Philosophical Labor Metric",
            'cost': "Displays 4-axis polar radar plot comparing classes",
            'desc': [
                "Renders a 4-spoke polar radar plot measuring alienation across Product (output ownership), Process (monotonous assembly shifts), Nature (severed customary land relationship), and Species-Being (degradation of creative human faculties).",
                "Why Useful to Player: Contrasts the psychic state of wage workers against customary feudal serfs and the ruling bourgeoisie. Highlights which dimension of estrangement is most acute."
            ],
            'stats': [
                ("North Spoke", "Product Alienation (Surplus Extraction)", (235, 90, 90)),
                ("East Spoke", "Process Alienation (Shift Length & Hazards)", (240, 140, 50)),
                ("South Spoke", "Nature Alienation (Commons Enclosure)", (110, 205, 130)),
                ("West Spoke", "Species-Being Alienation (Agency & Despair)", (180, 120, 220)),
            ],
            'icon': 'alienation',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 5. LEFT GOVERNANCE PANEL: ELECTORAL STRUGGLE BAROMETER
    # -------------------------------------------------------------------------
    if btn_id == 'gov_electoral_barometer':
        has_ten = getattr(owner, 'ten_hour_act', False) if owner else False
        has_safe = getattr(owner, 'factory_safety_act', False) if owner else False
        return {
            'title': "The Electoral Struggle & Capitalist Backlash Barometer",
            'badge': "POLITICAL EQUILIBRIUM",
            'badge_col': (235, 90, 90),
            'category': "Sovereign Democratic Dynamics",
            'cost': "Balances Popular Reform Pressure vs Capitalist PAC Campaign War Chest",
            'desc': [
                "Displays the dynamic political tug-of-war deciding your incumbent regime's survival: Popular Pressure on the left (driven by exhausted shifts, strikes, and UBI demands) versus the Capitalist Opposition War Chest on the right.",
                "Why Useful to Player: Passing pro-labor reforms (Ten-Hour Act, Safety Mandate) wins massive popular favor, but provokes severe capitalist backlash. Outraged corporate owners donate up to 30% of their profits to challenger parties to fund your electoral defeat! Subsidizing mass entertainment pacifies workers but tilts the needle toward capitalist dominance."
            ],
            'stats': [
                ("Ten-Hour Act Passed", "YES (Capitalist backlash active)" if has_ten else "NO (Popular strike pressure building)", (220, 100, 100) if has_ten else GREEN),
                ("Safety Mandate Passed", "YES (Capitalist backlash active)" if has_safe else "NO (High workplace casualties)", (220, 100, 100) if has_safe else (240, 180, 80)),
                ("Political Stake", "Incumbent Re-Election vs Challenger Ouster", ACCENT),
            ],
            'icon': 'scale',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 6. MAP DOCK LAYERS 1 TO 8
    # -------------------------------------------------------------------------
    if btn_id == 'layer_overview':
        return {
            'title': "Map Layer 1: Realm Overview",
            'badge': "GENERAL COMPASS",
            'badge_col': ACCENT,
            'category': "Hex Map Choropleth Mode",
            'cost': "Hotkey: Press 1 or click dock button",
            'desc': [
                "Default political and geographic overview displaying national capital stars, provincial seats, city populations, food market prices, and active trade routes.",
                "Why Useful to Player: Your primary tactical view for empire navigation, identifying provincial boundaries, and tracking basic settlement sizes."
            ],
            'stats': [("Active Layer", "1. Overview", ACCENT)],
            'icon': 'crown',
            'btn_id': btn_id
        }

    if btn_id == 'layer_physical':
        return {
            'title': "Map Layer 2: Physical & Height Elevation",
            'badge': "TOPOGRAPHY & BIOMES",
            'badge_col': (140, 225, 255),
            'category': "Hex Map Choropleth Mode",
            'cost': "Hotkey: Press 2 or click dock button",
            'desc': [
                "Displays 3D raymarched elevation in meters, natural biomes, and terrain yield bonuses for agricultural food and forestry timber.",
                "Why Useful to Player: Discover high-altitude mountain passes, defensible chokepoints, and fertile river valleys boasting agricultural multipliers."
            ],
            'stats': [("Active Layer", "2. Physical & Height", (140, 225, 255))],
            'icon': 'mountain',
            'btn_id': btn_id
        }

    if btn_id == 'layer_population':
        return {
            'title': "Map Layer 3: Population & Social Unrest",
            'badge': "CIVIL STABILITY",
            'badge_col': (245, 140, 60),
            'category': "Hex Map Choropleth Mode",
            'cost': "Hotkey: Press 3 or click dock button",
            'desc': [
                "Highlights demographic density, unfulfilled hunger counts, and civic order stages across all territories.",
                "Why Useful to Player: Pinpoint starving cities and monitor developing civil unrest before riots break out."
            ],
            'stats': [("Active Layer", "3. Population & Unrest", (245, 140, 60))],
            'icon': 'protest',
            'btn_id': btn_id
        }

    if btn_id == 'layer_economy':
        return {
            'title': "Map Layer 4: Economy & Wealth",
            'badge': "REGIONAL GDP & BANKING",
            'badge_col': (120, 225, 130),
            'category': "Hex Map Choropleth Mode",
            'cost': "Hotkey: Press 4 or click dock button",
            'desc': [
                "Displays nominal GDP output, local tax rates, and commercial bank equity reserves for each municipality.",
                "Why Useful to Player: Identify your wealthiest economic engines and assess regional commercial banking solvency."
            ],
            'stats': [("Active Layer", "4. Economy & Wealth", (120, 225, 130))],
            'icon': 'bank',
            'btn_id': btn_id
        }

    if btn_id == 'layer_production':
        return {
            'title': "Map Layer 5: Production & Industrial Output",
            'badge': "OUTPUT & FACTORIES",
            'badge_col': (245, 210, 90),
            'category': "Hex Map Choropleth Mode",
            'cost': "Hotkey: Press 5 or click dock button",
            'desc': [
                "Displays commodity outputs (Food, Wood, Furniture) and count of operational industrial workshops and farms.",
                "Why Useful to Player: Survey physical commodity supply chains and target capital subsidies to lagging sectors."
            ],
            'stats': [("Active Layer", "5. Production & Output", (245, 210, 90))],
            'icon': 'industry',
            'btn_id': btn_id
        }

    if btn_id == 'layer_military':
        return {
            'title': "Map Layer 6: Military & Border Defense",
            'badge': "GARRISONS & COMBAT",
            'badge_col': (235, 80, 80),
            'category': "Hex Map Choropleth Mode",
            'cost': "Hotkey: Press 6 or click dock button",
            'desc': [
                "Displays garrisoned soldiers, unit combat readiness, morale %, and exposed border vulnerabilities.",
                "Why Useful to Player: Detect undefended border sectors vulnerable to foreign invasion and monitor garrison troop morale."
            ],
            'stats': [("Active Layer", "6. Military & Defense", (235, 80, 80))],
            'icon': 'sword',
            'btn_id': btn_id
        }

    if btn_id == 'layer_enclosure':
        return {
            'title': "Map Layer 7: Land Tenure & Commons Enclosure",
            'badge': "AGRARIAN CHOROPLETH",
            'badge_col': (215, 175, 75),
            'category': "Hex Map Choropleth Mode",
            'cost': "Hotkey: Press 7 or click dock button",
            'desc': [
                "Shades the entire game world based on Land Tenure: Customary Feudal Commons appear as lush meadow green, transitional mixed tenure as yellow-ochre, and fully enclosed capitalist parcels as parched amber-brown.",
                "Why Useful to Player: Visually survey the progress of parliamentary enclosure across your empire. Spot remaining customary foraging commons and predict where peasant resistance and eviction riots will erupt next."
            ],
            'stats': [
                ("Meadow Green", "High Commons Access (Free Foraging)", (60, 190, 90)),
                ("Parched Brown", "Fully Enclosed (High Cash Rents)", (195, 95, 40)),
                ("Selected Tile Commons", f"{commons_pct:.0f}%", (215, 175, 75)),
            ],
            'icon': 'gentry',
            'btn_id': btn_id
        }

    if btn_id == 'layer_exploitation':
        return {
            'title': "Map Layer 8: Exploitation Rate (s/v) & Strikes",
            'badge': "WORKPLACE HAZARD CHOROPLETH",
            'badge_col': (235, 75, 75),
            'category': "Hex Map Choropleth Mode",
            'cost': "Hotkey: Press 8 or click dock button",
            'desc': [
                "Renders a live industrial exploitation heatmap: territories with low surplus extraction appear in cool blue, rising to blazing crimson as the surplus value rate (s/v) and shift hours escalate.",
                "Why Useful to Player: Animated pulsating crimson warning borders immediately flag territories suffering from active wildcat strikes or Luddite machinery sabotage, enabling rapid political intervention."
            ],
            'stats': [
                ("Cool Blue", "Low Exploitation (Equitable Wages)", (50, 120, 220)),
                ("Blazing Crimson", "Extreme Exploitation (High s/v)", (235, 50, 60)),
                ("Pulsating Border", "Active Wildcat Strike or Sabotage", RED),
            ],
            'icon': 'sabotage',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 7. RADAR SPOKE AXES & VISUALIZATION INSETS
    # -------------------------------------------------------------------------
    if btn_id in ('radar_product_axis', 'radar_axis_0'):
        return {
            'title': "4D Radar Axis: Product Alienation (Surplus)",
            'badge': "OUTPUT EXPROPRIATION",
            'badge_col': (235, 90, 90),
            'category': "Alienation Dimension",
            'cost': "North Spoke: Measures loss of worker control over their output",
            'desc': [
                "Represents estrangement from the commodity produced. Under capitalist wage labor, workers own nothing of what they manufacture; products are appropriated by capitalists to realize surplus value on markets.",
                "Why Useful to Player: High product alienation drives class consciousness and demands for worker co-ownership or higher wages."
            ],
            'stats': [("Axis Metric", "Rate of Exploitation (s/v)", (235, 90, 90))],
            'icon': 'labor',
            'btn_id': btn_id
        }

    if btn_id in ('radar_process_axis', 'radar_axis_1'):
        return {
            'title': "4D Radar Axis: Process Alienation (Shifts & Hazards)",
            'badge': "DISCIPLINARY ASSEMBLY",
            'badge_col': (240, 140, 50),
            'category': "Alienation Dimension",
            'cost': "East Spoke: Measures monotony, shift length, and assembly speedup",
            'desc': [
                "Measures alienation from the labor activity itself. Industrial machinery dictates the pace, reducing the human artisan into a mere mechanical appendage under grueling 10h-16h shifts.",
                "Why Useful to Player: Shortening workdays directly pulls this spoke inward, restoring worker morale and reducing workplace accidents."
            ],
            'stats': [("Axis Metric", f"Shift Hours: {avg_shift:.1f}h", (240, 140, 50))],
            'icon': 'clock',
            'btn_id': btn_id
        }

    if btn_id in ('radar_nature_axis', 'radar_axis_2'):
        return {
            'title': "4D Radar Axis: Nature Alienation (Enclosure)",
            'badge': "SEVERED FROM EARTH",
            'badge_col': (110, 205, 130),
            'category': "Alienation Dimension",
            'cost': "South Spoke: Measures loss of commons access and wilderness relation",
            'desc': [
                "Measures alienation from the natural world. Enclosures strip customary foraging rights, confining dispossessed peasants to dark urban factories severed from open land.",
                "Why Useful to Player: High nature alienation creates acute market food dependency, making populations vulnerable to price shocks and famine."
            ],
            'stats': [("Axis Metric", f"Enclosure Fraction: {100-commons_pct:.0f}%", (110, 205, 130))],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id in ('radar_species_axis', 'radar_axis_3'):
        return {
            'title': "4D Radar Axis: Species-Being Alienation (Gattungswesen)",
            'badge': "STIFLED POTENTIAL",
            'badge_col': (180, 120, 220),
            'category': "Alienation Dimension",
            'cost': "West Spoke: Measures exhaustion of creative agency and despair vices",
            'desc': [
                "Measures the loss of human species-essence (Gattungswesen). Exhausted workers lose time for culture, intellect, and community, turning to tavern vice spending to endure existence.",
                "Why Useful to Player: Reducing this axis unlocks higher worker innovation, civic participation, and lower crime rates."
            ],
            'stats': [("Axis Metric", "Despair Vice Outlays & Burnout", (180, 120, 220))],
            'icon': 'alienation',
            'btn_id': btn_id
        }

    # -------------------------------------------------------------------------
    # 8. PHASE 3: EXTERNALITIES, BUILDINGS & ECOLOGICAL POLICIES
    # -------------------------------------------------------------------------
    if btn_id == 'layer_externalities':
        return {
            'title': "Map Layer 9: Ecological Rift & Pollution",
            'badge': "METABOLIC RIFT",
            'badge_col': (100, 215, 140),
            'category': "Map Overlay",
            'cost': "Hotkey [9]: Toggles environmental metabolic rift choropleth",
            'desc': [
                "Visualizes physical metabolic rift across every territory: soil fertility exhaustion from continuous cropping vs natural regeneration, atmospheric coal smog, and river/aquifer chemical runoff.",
                "Why Useful to Player: Identify degrading farmlands before famine strikes, locate industrial smog clusters, and plan trunk sewers, scrubbers, and fallow reserves."
            ],
            'stats': [
                ("Soil Fertility", f"{getattr(pinned, 'soil_fertility', 1.0)*100:.0f}%", (120, 220, 140)),
                ("Nutrition Density", f"{getattr(pinned, 'nutrition_density', 1.0)*100:.0f}%", (240, 200, 80)),
                ("Smog / Water P.", f"{getattr(pinned, 'pollution_air', 0.0):.0f} / {getattr(pinned, 'pollution_water', 0.0):.0f}", (240, 120, 120)),
            ],
            'icon': 'externalities',
            'btn_id': btn_id
        }

    if btn_id == 'city_mandate_fertilizer':
        fert_on = getattr(pinned, 'use_fertilizer', False)
        return {
            'title': f"Synthetic Fertilizers: {'Mandated' if fert_on else 'Natural/Banned'}",
            'badge': "AGRONOMIC SHIFT",
            'badge_col': (240, 190, 80) if fert_on else GREEN,
            'category': "Municipal Agronomy Decree",
            'cost': "Boosts crop yields (+75%), but dilutes food nutrition (1.0 -> 0.70)",
            'desc': [
                "Mandates heavy application of synthetic nitrogen fertilizers on arable fields. Massively inflates gross food tonnage (+75%), but causes nutrition density dilution and nitrate river runoff.",
                "Why Useful to Player: Quells immediate urban grain deficits at the cost of long-term biological health wear and downstream water pollution."
            ],
            'stats': [
                ("Yield Bonus", "+75% Food Output", GREEN),
                ("Nutrition Density", "1.0 -> 0.70", (240, 140, 50)),
                ("Downstream Runoff", "+1.2 Water Pollution/t", RED),
            ],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id == 'city_mandate_pesticides':
        pest_on = getattr(pinned, 'use_pesticides', False)
        return {
            'title': f"Chemical Pesticides: {'Mandated' if pest_on else 'Organic/Banned'}",
            'badge': "TOXIC CONTROL",
            'badge_col': RED if pest_on else GREEN,
            'category': "Municipal Agronomy Decree",
            'cost': "Protects crop yield (+40%), but causes acute farmworker toxicity",
            'desc': [
                "Mandates chemical spraying to eradicate crop pests. Raises baseline agricultural yields (+40%), but exposes farmworkers to toxic biological wear (+0.04/t) and leaves soil chemical residue.",
                "Why Useful to Player: Maximizes farm production during critical shortages while trading off farmworker health and longevity."
            ],
            'stats': [
                ("Yield Protection", "+40% Food Output", GREEN),
                ("Worker Toxicity", "+0.040 Health Attrition/t", RED),
                ("Soil Residue", "+0.5 Soil Pollution/t", (240, 140, 50)),
            ],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id == 'prov_soil_conservation':
        return {
            'title': "Provincial Soil Conservation & Fallow Subsidies ($150)",
            'badge': "REGENERATION",
            'badge_col': (130, 220, 160),
            'category': "Provincial Environmental Accord",
            'cost': "$150 from provincial treasury",
            'desc': [
                "Funds legume cover cropping and mandatory fallow rest across all member territories, permanently restoring +10% soil fertility.",
                "Why Useful to Player: Halts metabolic rift soil depletion without requiring expensive chemical inputs."
            ],
            'stats': [
                ("Fertility Boost", "+10% Across Province", GREEN),
                ("Provincial Cash", f"${prov_cash:,.0f}", (120, 240, 150) if prov_cash >= 150 else RED),
            ],
            'icon': 'province',
            'btn_id': btn_id
        }

    if btn_id == 'build_trunk_sewer':
        return {
            'title': "Construct Municipal Trunk Sewer ($350)",
            'badge': "SANITATION",
            'badge_col': (100, 200, 240),
            'category': "Municipal Infrastructure",
            'cost': "Cost: $350 (Takes 2 turns)",
            'desc': [
                "Builds an underground brick sewer network, eliminating 70% of urban cholera and waterborne epidemics.",
                "Why Useful to Player: Drastically cuts urban biological health attrition and stabilizes labor productivity in dense cities."
            ],
            'stats': [
                ("Epidemic Defense", "-70% Water Contamination", GREEN),
                ("Construction Time", "2 Turns", TEXT),
            ],
            'icon': 'civil_engineering',
            'btn_id': btn_id
        }

    if btn_id == 'build_smoke_scrubber':
        return {
            'title': "Construct Smokestack Wet Scrubber ($300)",
            'badge': "AIR CLEANING",
            'badge_col': (160, 210, 255),
            'category': "Municipal Infrastructure",
            'cost': "Cost: $300 (Takes 2 turns)",
            'desc': [
                "Installs water-condensation filtration towers on industrial smokestacks, filtering out 70% of atmospheric soot and sulfur dioxide into toxic chemical sludge.",
                "Why Useful to Player: Protects urban populations from respiratory smog wear, though sludge must be managed."
            ],
            'stats': [
                ("Smog Reduction", "-70% Air Pollution", GREEN),
                ("Side-Effect", "+0.4 Soil Sludge/t", (240, 140, 50)),
            ],
            'icon': 'manufacturing',
            'btn_id': btn_id
        }

    if btn_id == 'build_soil_conservation_reserve':
        return {
            'title': "Construct Agroecological Conservation Reserve ($200)",
            'badge': "ECOLOGICAL RESTORATION",
            'badge_col': (130, 220, 160),
            'category': "Municipal Infrastructure",
            'cost': "Cost: $200 (Takes 2 turns)",
            'desc': [
                "Sets aside protected acreage for agroecological rotation, bio-diverse windbreaks, and nitrogen fixation, boosting annual soil regeneration by +25%.",
                "Why Useful to Player: Permanently counteracts industrial soil exhaustion and guarantees sustainable food yields."
            ],
            'stats': [
                ("Soil Regen Rate", "+25% Natural Regeneration", GREEN),
                ("Construction Time", "2 Turns", TEXT),
            ],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id == 'build_water_filtration_plant':
        return {
            'title': "Construct Provincial Water Filtration Plant ($450)",
            'badge': "WATER SECURITY",
            'badge_col': (80, 200, 255),
            'category': "Provincial Public Works",
            'cost': "Cost: $450 (Takes 3 turns)",
            'desc': [
                "Constructs slow sand-bed gravity filters and aeration cascades, eliminating chemical runoff and municipal effluent across the regional watershed.",
                "Why Useful to Player: Restores water purity across all downstream settlements and prevents waterborne disease mortality."
            ],
            'stats': [
                ("Water Purity", "-80% Watershed Pollution", GREEN),
                ("Construction Time", "3 Turns", TEXT),
            ],
            'icon': 'municipal',
            'btn_id': btn_id
        }

    return None
