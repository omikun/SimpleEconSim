"""
worldview_tooltips_charts.py — Comprehensive Tooltip Providers for Charts, Citizen Status, Labor & Comparison.

Provides rich contextual explanations, formulas, strategic utility for the player, and live stat breakdowns for:
- 10-Chart Macroeconomic & Market Sidebar (Prices, Pop/Hunger, Production, Trade, Gov Income, Gini, Inventory, Protest/Commons, GDP, Demand Ratio)
- Citizen Status Visualizers & Tabs (Social Classes, Subsistence Mode, Commons vs Rent, Disparity & Unrest, Wealth Pyramid, Lorenz Curve)
- Labor & Workplace Alienation Dashboard (Workday Caps, Exploitation s/v, Alienation, Health Hazards, Consciousness vs Spectacle, Strikes & Sabotage)
- Cross-Nation Comparison Modal Tabs & Filters (Leaderboard, Provincial Goods, Forex & Banking, Surplus Extraction, Grievance Analysis)
"""

from __future__ import annotations
from goods import Goods
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN


# =============================================================================
# 1. 10-CHART SIDEBAR TOOLTIPS
# =============================================================================

def build_sidebar_chart_tooltip(btn_id: str, world: dict, region=None, nation=None) -> dict | None:
    """Detailed tooltips for the 10 sidebar time-series charts."""
    pinned = region or world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    owner = nation or (getattr(pinned, 'owner_nation', None) if pinned else None)
    if owner is None and world.get('nations'):
        owner = world['nations'][0]

    gov = getattr(pinned, 'gov', None) if pinned else None

    # Live stats helpers
    pf = pinned.price_log.get(Goods.food, [1.0])[-1] if pinned and pinned.price_log.get(Goods.food) else 1.0
    pw = pinned.price_log.get(Goods.wood, [1.0])[-1] if pinned and pinned.price_log.get(Goods.wood) else 1.0
    pfurn = pinned.price_log.get(Goods.furniture, [1.0])[-1] if pinned and pinned.price_log.get(Goods.furniture) else 1.0

    pop_c = len(getattr(pinned, 'agents', [])) if pinned else 0
    hungry_c = sum(1 for a in getattr(pinned, 'agents', []) if not a.is_corporation and not a.is_government and getattr(a, 'hungry_steps', 0) > 0) if pinned else 0

    prodf = pinned.production_log.get(Goods.food, [0])[-1] if pinned and pinned.production_log.get(Goods.food) else 0
    prodw = pinned.production_log.get(Goods.wood, [0])[-1] if pinned and pinned.production_log.get(Goods.wood) else 0
    prodfurn = pinned.production_log.get(Goods.furniture, [0])[-1] if pinned and pinned.production_log.get(Goods.furniture) else 0

    exp_val = sum(pinned.export_val.get(g, [0])[-1] if pinned.export_val.get(g) else 0 for g in (Goods.food, Goods.wood, Goods.furniture)) if pinned else 0.0
    imp_val = sum(pinned.import_val.get(g, [0])[-1] if pinned.import_val.get(g) else 0 for g in (Goods.food, Goods.wood, Goods.furniture)) if pinned else 0.0

    protest_e = pinned.protest_energy_log[-1] if pinned and pinned.protest_energy_log else 0.0
    commons_pct = (pinned.tenure_log[-1] * 100.0) if pinned and getattr(pinned, 'tenure_log', None) else 100.0

    gdp_val = (pinned.gdp_log[-1]) if pinned and getattr(pinned, 'gdp_log', None) else 0.0
    gini_val = (pinned.gini_log.get(Goods.food, [0.0])[-1]) if pinned and pinned.gini_log.get(Goods.food) else 0.0
    migr_val = (pinned.migration_intent_log[-1]) if pinned and getattr(pinned, 'migration_intent_log', None) else 0.0

    inv_f = pinned.inventory_log.get(Goods.food, [0])[-1] if pinned and pinned.inventory_log.get(Goods.food) else 0
    inv_w = pinned.inventory_log.get(Goods.wood, [0])[-1] if pinned and pinned.inventory_log.get(Goods.wood) else 0
    inv_furn = pinned.inventory_log.get(Goods.furniture, [0])[-1] if pinned and pinned.inventory_log.get(Goods.furniture) else 0

    dem_f = pinned.demand_ratio_log.get(Goods.food, [1.0])[-1] if pinned and pinned.demand_ratio_log.get(Goods.food) else 1.0
    dem_w = pinned.demand_ratio_log.get(Goods.wood, [1.0])[-1] if pinned and pinned.demand_ratio_log.get(Goods.wood) else 1.0
    dem_furn = pinned.demand_ratio_log.get(Goods.furniture, [1.0])[-1] if pinned and pinned.demand_ratio_log.get(Goods.furniture) else 1.0

    # 1. Prices
    if btn_id in ('chart_1', 'chart_1_prices'):
        return {
            'title': "Chart 1: Market Commodity Prices",
            'badge': "PRICE STABILITY",
            'badge_col': ACCENT,
            'category': "Market Dynamics & Inflation",
            'cost': "Click chart cell to zoom in; Esc/Tab to restore grid",
            'desc': [
                "Tracks the real-time market-clearing equilibrium prices for staple Food (green), raw Wood (amber), and manufactured Furniture (blue) across trading turns.",
                "Why Useful: Spot inflationary spikes indicating severe local shortages or bottlenecks. When food prices rise faster than wages, workers starve and protest energy surges. If manufactured wares collapse in price, factory profit margins vanish, triggering wage cuts and layoffs."
            ],
            'stats': [
                ("Food Price (Grain)", f"${pf:.2f}", (120, 200, 80)),
                ("Wood Price (Timber)", f"${pw:.2f}", (190, 150, 70)),
                ("Furniture Price (Wares)", f"${pfurn:.2f}", (90, 140, 230)),
            ],
            'icon': 'chart',
            'btn_id': btn_id
        }

    # 2. Pop / Hunger
    if btn_id in ('chart_2', 'chart_2_pop_hunger'):
        return {
            'title': "Chart 2: Demographics & Hunger Attrition",
            'badge': "CIVIL SURVIVAL",
            'badge_col': (235, 90, 90),
            'category': "Demographics & Human Welfare",
            'cost': "Critical Warning: Malnutrition escalates unrest and causes population decline",
            'desc': [
                "Compares total living citizen population (white) against the count of undernourished, hungry citizens (red) unable to secure daily subsistence rations.",
                "Why Useful: The primary early-warning bellwether for humanitarian crises and bread riots. A rising red curve means wages cannot cover cost of living or open markets are bare, requiring emergency grain relief ($50), agricultural subsidies, or Universal Basic Income."
            ],
            'stats': [
                ("Living Population", f"{pop_c} Citizens", (230, 230, 230)),
                ("Hungry Citizens", f"{hungry_c} Starving", RED if hungry_c > 0 else GREEN),
                ("Hunger Rate", f"{(hungry_c / max(1, pop_c))*100:.1f}%", RED if hungry_c > 0 else GREEN),
            ],
            'icon': 'pop',
            'btn_id': btn_id
        }

    # 3. Production
    if btn_id in ('chart_3', 'chart_3_production'):
        return {
            'title': "Chart 3: Physical Output & Production",
            'badge': "INDUSTRIAL OUTPUT",
            'badge_col': (110, 210, 120),
            'category': "Macroeconomic Supply",
            'cost': "Shows raw volume of physical units produced per turn",
            'desc': [
                "Plots the volume of physical goods produced each turn across agrarian farming (food), forestry logging (timber), and artisan workshops (furniture).",
                "Why Useful: Monitors real productive capacity. Reveals whether capital investments, technological discoveries (e.g. 4-field crop rotation, steam automation), or labor shift regulations are expanding physical wealth or contracting output."
            ],
            'stats': [
                ("Food Harvested", f"{prodf:.1f} units/t", (120, 200, 80)),
                ("Timber Logged", f"{prodw:.1f} units/t", (190, 150, 70)),
                ("Furniture Manufactured", f"{prodfurn:.1f} units/t", (90, 140, 230)),
            ],
            'icon': 'industry',
            'btn_id': btn_id
        }

    # 4. Trade Flow
    if btn_id in ('chart_4', 'chart_4_trade_flow'):
        net_trade = exp_val - imp_val
        return {
            'title': "Chart 4: Trade Flow (Exports vs Imports)",
            'badge': "CURRENT ACCOUNT",
            'badge_col': (100, 180, 240),
            'category': "Commercial Balance of Payments",
            'cost': "Paired bars per turn: Green = Exports, Red = Imports",
            'desc': [
                "Compares total monetary value of commodities exported to neighboring territories against imports flowing into local consumer and industrial markets.",
                "Why Useful: Chronic import deficits drain regional banking cash reserves and currency strength, while export surpluses build wealth, stimulate hiring, and expand national treasury foreign reserves."
            ],
            'stats': [
                ("Export Value", f"${exp_val:,.1f}/t", (110, 210, 120)),
                ("Import Value", f"${imp_val:,.1f}/t", (230, 110, 100)),
                ("Net Trade Balance", f"{'+' if net_trade >= 0 else ''}${net_trade:,.1f}/t", GREEN if net_trade >= 0 else RED),
            ],
            'icon': 'ex',
            'btn_id': btn_id
        }

    # 5. Gov Income
    if btn_id in ('chart_5', 'chart_5_gov_income'):
        return {
            'title': "Chart 5: Government Fiscal Revenue Inflows",
            'badge': "PUBLIC FINANCES",
            'badge_col': (240, 200, 90),
            'category': "Fiscal Structure (10-Turn Moving Avg)",
            'cost': "Stacked bars: Income Tax (amber) + Tariffs (blue) + Death Duties (purple)",
            'desc': [
                "Decomposes public treasury revenues into direct citizen income taxes, cross-border customs tariffs, and aristocratic estate inheritance levies.",
                "Why Useful: Assesses fiscal resilience. If the state depends heavily on volatile customs tariffs, trade wars or embargoes will crater revenues; direct income taxes provide steady cash but squeeze worker living margins if raised too high."
            ],
            'stats': [
                ("Income Tax Share", "Direct levy on citizen earnings", (240, 200, 90)),
                ("Customs Tariff Share", "Border levy on foreign imports", (110, 150, 235)),
                ("Inheritance Duty Share", "Levy on deceased wealth estates", (200, 120, 230)),
            ],
            'icon': 'treasury',
            'btn_id': btn_id
        }

    # 6. Gini / Migr
    if btn_id in ('chart_6', 'chart_6_gini_migr'):
        return {
            'title': "Chart 6: Inequality (Gini) & Migration Outflow",
            'badge': "WEALTH DISPARITY",
            'badge_col': (200, 120, 230),
            'category': "Social Stratification & Brain Drain",
            'cost': "Gini index (0..1) vs Net citizen migration intent",
            'desc': [
                "Tracks the wealth Gini inequality coefficient (purple) alongside citizen migration intent and demographic flight (cyan).",
                "Why Useful: Extreme inequality (Gini > 0.45) breeds class resentment, crime, and strikes. Persistent negative migration indicates workers are abandoning your province for neighboring lands with higher wages, lower taxes, or better public welfare safety nets."
            ],
            'stats': [
                ("Gini Inequality Index", f"{gini_val:.3f}", (200, 120, 230)),
                ("Migration Intent", f"{'+' if migr_val >= 0 else ''}{migr_val:.2f}", (120, 200, 220)),
            ],
            'icon': 'lorenz',
            'btn_id': btn_id
        }

    # 7. Inventories
    if btn_id in ('chart_7', 'chart_7_inventories'):
        return {
            'title': "Chart 7: Commodity Inventories & Stockpiles",
            'badge': "MARKET RESERVES",
            'badge_col': (190, 150, 70),
            'category': "Storehouse Stockpiles & Buffers",
            'cost': "Physical units stored in commercial warehouses",
            'desc': [
                "Displays unsold commodity stockpiles (Food, Wood, Furniture) stored in regional warehouses and merchant granaries.",
                "Why Useful: Warehouse inventories buffer against bad harvests and trade blockades. Zero inventory warns of imminent price spikes; excessive unsold inventory reveals overproduction, lack of consumer purchasing power, or high transportation friction."
            ],
            'stats': [
                ("Stored Food (Granary)", f"{inv_f:.1f} units", (120, 200, 80)),
                ("Stored Wood (Lumber)", f"{inv_w:.1f} units", (190, 150, 70)),
                ("Stored Furniture (Wares)", f"{inv_furn:.1f} units", (90, 140, 230)),
            ],
            'icon': 'granary',
            'btn_id': btn_id
        }

    # 8. Protest / Commons
    if btn_id in ('chart_8', 'chart_8_protest_commons'):
        return {
            'title': "Chart 8: Civil Protest Energy vs Feudal Commons",
            'badge': "AGRARIAN CONFLICT",
            'badge_col': (245, 140, 40),
            'category': "Class Struggle & Enclosure Dynamics",
            'cost': "Protest Energy (0..10) vs Remaining Unenclosed Commons Area (x5)",
            'desc': [
                "Visualizes the causal link between landlord enclosure of customary feudal commons and popular civil discontent.",
                "Why Useful: When customary commons are privatized by landlords, dispossessed serfs lose free foraging rights, forcing them into precarious wage labor and driving up protest energy. When protest crosses 6.5, riots and armed insurrections erupt."
            ],
            'stats': [
                ("Protest Energy", f"{protest_e:.2f} / 10.00", RED if protest_e > 4.0 else (245, 140, 40)),
                ("Customary Commons", f"{commons_pct:.1f}% remaining", (120, 205, 140)),
            ],
            'icon': 'protest',
            'btn_id': btn_id
        }

    # 9. GDP Output
    if btn_id in ('chart_9', 'chart_9_gdp_output'):
        return {
            'title': "Chart 9: Gross Domestic Economic Output (GDP)",
            'badge': "MACRO EXPANSION",
            'badge_col': (100, 225, 150),
            'category': "Aggregate Economy (10-Turn Moving Avg)",
            'cost': "Gross market value of all finished goods produced ($/turn)",
            'desc': [
                "Plots the 10-turn moving average of total gross domestic economic output (GDP) produced across the territory.",
                "Why Useful: The master headline indicator of overall economic growth and industrial scale. Use it to measure whether technological investments, paved roads, and workforce expansion are compounding aggregate sovereign wealth."
            ],
            'stats': [
                ("Current GDP / Turn", f"${gdp_val:,.1f}", (100, 225, 150)),
                ("Growth Trend", "10-Turn Smoothed Moving Average", TEXT),
            ],
            'icon': 'gdp',
            'btn_id': btn_id
        }

    # 10. Demand Ratio
    if btn_id in ('chart_10', 'chart_10_demand_ratio'):
        return {
            'title': "Chart 10: Market Demand / Supply Ratios",
            'badge': "SHORTAGE DETECTOR",
            'badge_col': (245, 180, 70),
            'category': "Market Equilibrium & Bottlenecks",
            'cost': "Ratio = (Consumer Purchase Orders) / (Available Supply). Baseline = 1.0",
            'desc': [
                "Tracks the ratio of consumer purchase orders to market available inventory for Food (orange), Wood (green), and Furniture (blue).",
                "Why Useful: Ratios > 1.0 indicate structural shortages and unsatisfied consumer demand, predicting imminent price inflation and worker hunger. Ratios < 1.0 indicate oversupply and gluts, signaling that production should be reallocated."
            ],
            'stats': [
                ("Food Demand Ratio", f"{dem_f:.2f}x ({'Deficit' if dem_f > 1.05 else ('Glut' if dem_f < 0.95 else 'Balanced')})", (245, 180, 70)),
                ("Wood Demand Ratio", f"{dem_w:.2f}x ({'Deficit' if dem_w > 1.05 else ('Glut' if dem_w < 0.95 else 'Balanced')})", (180, 220, 90)),
                ("Furniture Demand Ratio", f"{dem_furn:.2f}x ({'Deficit' if dem_furn > 1.05 else ('Glut' if dem_furn < 0.95 else 'Balanced')})", (130, 175, 245)),
            ],
            'icon': 'chart',
            'btn_id': btn_id
        }

    return None


# =============================================================================
# 2. CITIZEN STATUS DASHBOARD & VISUALIZATIONS
# =============================================================================

def build_citizen_tooltip(btn_id: str, world: dict, region=None, nation=None) -> dict | None:
    """Tooltips for Citizen status tabs, scope buttons, charts, and inequality pyramids."""
    pinned = region or world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    owner = nation or (getattr(pinned, 'owner_nation', None) if pinned else None)
    if owner is None and world.get('nations'):
        owner = world['nations'][0]

    # Tabs
    if btn_id == 'tab_charts':
        return {
            'title': "Macroeconomic Charts & Markets Tab",
            'badge': "TIME-SERIES SUITE",
            'badge_col': ACCENT,
            'category': "Right Sidebar Navigation",
            'cost': "Hotkey: Click or press Tab to view 10-chart grid",
            'desc': [
                "Switches the sidebar to the 10-chart macroeconomic and commodity market dashboard.",
                "Why Useful: Provides real-time and historical trend lines for commodity prices, production volumes, trade flows, fiscal budgets, inventory stockpiles, and GDP output."
            ],
            'stats': [("Active View", "10 Macro Charts", ACCENT)],
            'icon': 'chart',
            'btn_id': btn_id
        }

    if btn_id == 'tab_citizens':
        return {
            'title': "Citizen Status & Labor Dynamics Tab",
            'badge': "CLASS STRUCTURE",
            'badge_col': (110, 205, 130),
            'category': "Right Sidebar Navigation",
            'cost': "Hotkey: Click to view social classes and workplace alienation",
            'desc': [
                "Switches the sidebar to the Changing Status of Citizens dashboard, tracking social class transitions (serfs, tenants, wage workers, dispossessed, gentry), subsistence modes, labor alienation, strikes, and wealth pyramids.",
                "Why Useful: Understand the human cost of economic development, monitor poverty and dispossession, and balance corporate capital extraction against social stability."
            ],
            'stats': [("Active View", "Citizen & Labor Dynamics", (110, 205, 130))],
            'icon': 'pop',
            'btn_id': btn_id
        }

    # Scopes
    if btn_id == 'citizen_scope_tile':
        return {
            'title': "Filter Scope: Selected City / Tile",
            'badge': "MUNICIPAL LEVEL",
            'badge_col': (100, 180, 240),
            'category': "Data Filter Scope",
            'cost': "Click to inspect the currently pinned territory",
            'desc': [
                "Restricts all citizen status graphs, class breakdowns, and labor metrics to the currently selected city or tile.",
                "Why Useful: Pinpoint localized poverty, acute labor strikes, or rapid landlord enclosures in specific urban centers."
            ],
            'stats': [("Pinned Tile", getattr(pinned, 'display_name', getattr(pinned, 'name', 'None')), TEXT)],
            'icon': 'municipal',
            'btn_id': btn_id
        }

    if btn_id == 'citizen_scope_nation':
        return {
            'title': "Filter Scope: Sovereign Nation",
            'badge': "NATIONAL AGGREGATE",
            'badge_col': (245, 205, 60),
            'category': "Data Filter Scope",
            'cost': "Click to aggregate data across all constituent cities",
            'desc': [
                "Aggregates citizen status logs, class headcounts, and labor dynamics across all constituent territories of the sovereign nation.",
                "Why Useful: Formulate nationwide macroeconomic policies, evaluate overall social class composition, and benchmark national labor standards."
            ],
            'stats': [("Nation", getattr(owner, 'name', 'None'), (245, 205, 60))],
            'icon': 'crown',
            'btn_id': btn_id
        }

    # Sub-tabs
    if btn_id == 'citizen_subtab_class':
        return {
            'title': "Sub-Tab: Social Class Stratification",
            'badge': "CLASS EVOLUTION",
            'badge_col': (165, 115, 230),
            'category': "Citizen Subsystem",
            'cost': "Click to analyze social classes, food subsistence, and rent",
            'desc': [
                "Displays the historical transformation of citizens across 6 socioeconomic tiers: Feudal Serfs, Agrarian Tenants, Industrial Wage Laborers, Dispossessed Paupers, Aristocratic Gentry, and Commercial Bourgeoisie.",
                "Why Useful: Tracks the transition from customary feudal agrarianism to industrial wage labor and monitors the growth of landless poverty."
            ],
            'stats': [("Active Subsystem", "Social Classes & Subsistence", (165, 115, 230))],
            'icon': 'pyramid',
            'btn_id': btn_id
        }

    if btn_id == 'citizen_subtab_labor':
        return {
            'title': "Sub-Tab: Labor Commodification & Alienation",
            'badge': "WORKPLACE STRUGGLE",
            'badge_col': (220, 95, 95),
            'category': "Citizen Subsystem",
            'cost': "Click to analyze shift lengths, exploitation s/v, and strikes",
            'desc': [
                "Displays factory labor dynamics: actual daily shift hours, legal workday caps, surplus value exploitation rates (s/v), 4D Marxian alienation, physiological health hazards, strikes, and Luddite machinery sabotage.",
                "Why Useful: Manage workplace productivity vs unrest; enact workday limits or subsidize public spectacles to maintain factory output."
            ],
            'stats': [("Active Subsystem", "Labor Alienation & Resistance", (220, 95, 95))],
            'icon': 'labor',
            'btn_id': btn_id
        }

    # Modes
    if btn_id == 'citizen_mode_charts':
        return {
            'title': "View Mode: Time-Series Trend Charts",
            'badge': "HISTORICAL LOGS",
            'badge_col': ACCENT,
            'category': "Visualization Mode",
            'cost': "Click to view historical 4-chart trend lines",
            'desc': [
                "Renders 4 interactive time-series charts tracing the historical progression of citizen classes, food sources, rent burdens, and inequality across turns.",
                "Why Useful: Observe long-term social trajectories, evaluate the lasting effects of land reforms, and anticipate future civil unrest."
            ],
            'stats': [("Display Mode", "4 Time-Series Charts", ACCENT)],
            'icon': 'chart',
            'btn_id': btn_id
        }

    if btn_id == 'citizen_mode_pyramid':
        return {
            'title': "View Mode: Wealth Pyramid & Lorenz Curve",
            'badge': "CROSS-SECTIONAL",
            'badge_col': (215, 175, 70),
            'category': "Visualization Mode",
            'cost': "Click to view wealth pyramid and Lorenz inequality curve",
            'desc': [
                "Displays the instantaneous cross-sectional Social Class Wealth Pyramid and the Lorenz Inequality Distribution Curve.",
                "Why Useful: Directly inspect the concentration of private wealth held by the upper classes versus the population mass of working citizens."
            ],
            'stats': [("Display Mode", "Wealth Pyramid & Lorenz Curve", (215, 175, 70))],
            'icon': 'pyramid',
            'btn_id': btn_id
        }

    # 4 Citizen Charts
    if btn_id in ('citizen_chart_1', 'citizen_chart_1_classes'):
        return {
            'title': "Citizen Chart 1: Social Class Composition",
            'badge': "DEMOGRAPHIC STRATA",
            'badge_col': (110, 205, 130),
            'category': "Class Transformation",
            'cost': "Plots headcount across 6 socioeconomic classes",
            'desc': [
                "Tracks the population breakdown across 6 social classes: Serfs (customary feudal commons), Tenants (rent-paying agrarian farmers), Wage Workers (proletarians), Dispossessed (landless paupers), Gentry (lords/landlords), and Bourgeoisie (artisans/industrialists).",
                "Why Useful: Reveals the structural shift from agrarian feudalism to capitalist industrialization. A surge in Dispossessed paupers warns of extreme poverty and impending civil unrest."
            ],
            'stats': [
                ("Serfs (Customary)", "Subsist on feudal commons", (110, 205, 130)),
                ("Tenants (Agrarian)", "Pay cash rent to landlords", (235, 195, 75)),
                ("Workers (Proletariat)", "Earn cash wages in workshops", (220, 85, 85)),
                ("Dispossessed (Paupers)", "Landless, unemployed citizens", (145, 145, 155)),
            ],
            'icon': 'pyramid',
            'btn_id': btn_id
        }

    if btn_id in ('citizen_chart_2', 'citizen_chart_2_subsistence'):
        return {
            'title': "Citizen Chart 2: Subsistence & Food Sourcing",
            'badge': "FOOD SECURITY",
            'badge_col': (240, 165, 60),
            'category': "Nutritional Dependency",
            'cost': "Green = Foraged Commons, Amber = Market Purchases, Red = Hungry",
            'desc': [
                "Quantifies how citizens secure daily sustenance: free subsistence foraging on customary feudal commons (green), cash purchases on open commodity markets (amber), or unfulfilled hunger/malnutrition (red).",
                "Why Useful: Highlights the transition to market dependency. If commons foraging drops due to enclosures while market food purchases stall, workers lack cash to survive, causing immediate spikes in hunger."
            ],
            'stats': [
                ("Foraged Commons Food", "Zero monetary cost", (120, 215, 140)),
                ("Purchased Market Food", "Requires disposable cash wages", (240, 165, 60)),
                ("Unfed Hungry Citizens", "Leads to starvation attrition", (240, 70, 70)),
            ],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id in ('citizen_chart_3', 'citizen_chart_3_commons_rent'):
        return {
            'title': "Citizen Chart 3: Commons Access & Rent Extraction",
            'badge': "LANDLORD TENURE",
            'badge_col': (230, 120, 50),
            'category': "Agrarian Land Economics",
            'cost': "Commons % (green) vs Cash Rent Extracted ($) vs Rent Arrears ($)",
            'desc': [
                "Plots remaining unenclosed customary feudal commons area percentage against total cash rent extracted by aristocratic landlords and unpaid rent debt arrears.",
                "Why Useful: Monitors landlord rent burdens. When rent arrears spike, evictions follow, swelling urban slums with dispossessed paupers and fueling violent anti-landlord resistance."
            ],
            'stats': [
                ("Commons Land Share", "Remaining customary feudal parcel", (90, 215, 130)),
                ("Cash Rent Collected", "Extracted by landlords into private wealth", (230, 120, 50)),
                ("Unpaid Rent Arrears", "Accrued peasant debt burden", (230, 70, 115)),
            ],
            'icon': 'gentry',
            'btn_id': btn_id
        }

    if btn_id in ('citizen_chart_4', 'citizen_chart_4_disparity_unrest'):
        return {
            'title': "Citizen Chart 4: Wealth Disparity (Gini) & Protest",
            'badge': "CLASS RESENTMENT",
            'badge_col': (240, 75, 75),
            'category': "Political Stability Index",
            'cost': "Gini Inequality (x100) vs Civil Protest Energy (0..10)",
            'desc': [
                "Tracks the wealth Gini inequality coefficient (amber, scaled x100) alongside popular civil protest energy (red, scale 0..10).",
                "Why Useful: Demonstrates how economic disparity directly translates into political unrest and revolutionary pressure. Use fiscal equalization, UBI, or tax reforms to reduce Gini before protest reaches crisis levels."
            ],
            'stats': [
                ("Gini Inequality Index", "0.00 = Equality, 1.00 = Max Disparity", (230, 185, 70)),
                ("Civil Protest Energy", "0..10 Scale (Riots at 6.5, Revolution at 9.5)", (240, 75, 75)),
            ],
            'icon': 'protest',
            'btn_id': btn_id
        }

    # Visualizations
    if btn_id == 'citizen_viz_pyramid':
        return {
            'title': "Social Class Wealth Pyramid",
            'badge': "WEALTH STRATIFICATION",
            'badge_col': (215, 175, 70),
            'category': "Cross-Sectional Distribution",
            'cost': "Visualizes population share vs wealth share by class tier",
            'desc': [
                "Displays the hierarchical distribution of society: Gentry (nobles/landlords) and Bourgeoisie (industrialists) at the apex, followed by Tenants, Wage Workers, Serfs, and Dispossessed paupers at the base.",
                "Why Useful: Instantly reveals the concentration of private wealth. A top-heavy pyramid with an impoverished base indicates severe structural instability and high strike vulnerability."
            ],
            'stats': [("Pyramid Tiers", "6 Socioeconomic Classes", (215, 175, 70))],
            'icon': 'pyramid',
            'btn_id': btn_id
        }

    if btn_id == 'citizen_viz_lorenz':
        return {
            'title': "Lorenz Inequality Curve",
            'badge': "GINI METRIC",
            'badge_col': (230, 185, 70),
            'category': "Economic Inequality Analysis",
            'cost': "Area between curve & 45-degree line represents Gini Index",
            'desc': [
                "Plots cumulative share of population against cumulative share of private wealth against the 45-degree line of perfect equality.",
                "Why Useful: The definitive economic benchmark for inequality. The further the curved line bows away from the diagonal, the higher the Gini coefficient and the greater the concentration of wealth in elite hands."
            ],
            'stats': [("Line of Equality", "45-Degree Reference Diagonal", DIM)],
            'icon': 'lorenz',
            'btn_id': btn_id
        }

    return None


# =============================================================================
# 3. LABOR & WORKPLACE ALIENATION DASHBOARD
# =============================================================================

def build_labor_tooltip(btn_id: str, world: dict, region=None, nation=None) -> dict | None:
    """Tooltips for labor regulations, workday limits, spectacle funding, and labor charts."""
    pinned = region or world.get('selected_region')
    if pinned is None and world.get('nations') and world['nations'][0].tiles:
        pinned = world['nations'][0].tiles[0]

    owner = nation or (getattr(pinned, 'owner_nation', None) if pinned else None)
    if owner is None and world.get('nations'):
        owner = world['nations'][0]

    cap_h = getattr(pinned, 'max_workday_hours', 16.0) if pinned else 16.0
    sv_rate = (getattr(pinned, 'labor_sv_log', [0.0])[-1] * 100.0) if pinned and getattr(pinned, 'labor_sv_log', None) else 0.0
    alien_val = (getattr(pinned, 'alienation_log', [0.0])[-1] * 100.0) if pinned and getattr(pinned, 'alienation_log', None) else 0.0
    consc_val = (getattr(pinned, 'class_consciousness_log', [0.0])[-1] * 100.0) if pinned and getattr(pinned, 'class_consciousness_log', None) else 0.0
    protest_e = pinned.protest_energy_log[-1] if pinned and pinned.protest_energy_log else 0.0

    if btn_id == 'labor_workday_down':
        return {
            'title': "Statutory Workday Cap [-1 Hour]",
            'badge': "LABOR PROTECTION",
            'badge_col': (100, 185, 245),
            'category': "Workplace Labor Regulation",
            'cost': "Lowers statutory workday ceiling (Min: 6.0 Hours)",
            'desc': [
                "Enacts statutory labor regulations shortening the maximum permitted daily factory shift by 1.0 hour.",
                "Why Useful: Reduces worker exhaustion, lowers physiological health attrition, alleviates alienation, and pleases the Proletarian faction. Trade-off: Slightly lowers maximum daily industrial output per worker."
            ],
            'stats': [
                ("Statutory Workday Cap", f"{cap_h:.1f}h -> {max(6.0, cap_h - 1.0):.1f}h", (100, 185, 245)),
                ("Exploitation Rate (s/v)", f"{sv_rate:.1f}%", ACCENT),
                ("Alienation Index", f"{alien_val:.1f} / 100", (180, 120, 220)),
            ],
            'icon': 'clock',
            'btn_id': btn_id
        }

    if btn_id == 'labor_workday_up':
        return {
            'title': "Statutory Workday Cap [+1 Hour]",
            'badge': "CAPITAL PRODUCTION",
            'badge_col': (240, 100, 100),
            'category': "Workplace Labor Regulation",
            'cost': "Raises statutory workday ceiling (Max: 16.0 Hours)",
            'desc': [
                "Permits industrial workshops to operate longer shifts, extending the statutory workday cap by 1.0 hour.",
                "Why Useful: Boosts aggregate factory production and corporate profit margins. Severe trade-off: Escalates worker exhaustion, accelerates health attrition and workplace mortality, and increases strike risk."
            ],
            'stats': [
                ("Statutory Workday Cap", f"{cap_h:.1f}h -> {min(16.0, cap_h + 1.0):.1f}h", (240, 100, 100)),
                ("Exploitation Rate (s/v)", f"{sv_rate:.1f}%", ACCENT),
                ("Proletarian Consciousness", f"{consc_val:.1f}%", (240, 75, 75)),
            ],
            'icon': 'clock',
            'btn_id': btn_id
        }

    if btn_id == 'labor_subsidize_spectacle':
        return {
            'title': "Subsidize Mass Public Spectacle ($50)",
            'badge': "POPULAR PACIFICATION",
            'badge_col': (235, 140, 245),
            'category': "Cultural Pacification Decrees",
            'cost': "Cost: $50 grant from municipal / sovereign treasury",
            'desc': [
                "Disburses public funds to sponsor mass commercial entertainment, theatrical carnivals, and public circuses.",
                "Why Useful: Pacifies civil discontent and dulls revolutionary mobilization. Instantly reduces worker class consciousness by 20% and lowers popular protest energy by 0.20 points."
            ],
            'stats': [
                ("Class Consciousness", f"{consc_val:.1f}% -> {max(0.0, consc_val * 0.8):.1f}%", (235, 140, 245)),
                ("Protest Energy Impact", "-0.20 Points", GREEN),
                ("Treasury Cost", "$50 Cash", (240, 200, 90)),
            ],
            'icon': 'theatre',
            'btn_id': btn_id
        }

    # 4 Labor Charts
    if btn_id in ('labor_chart_1', 'labor_chart_1_exploitation'):
        return {
            'title': "Labor Chart 1: Workday Shifts & Exploitation (s/v)",
            'badge': "SURPLUS VALUE",
            'badge_col': (240, 190, 60),
            'category': "Marxian Labor Exploitation",
            'cost': "Shift Hours (red), Legal Cap (blue), Surplus Value Rate s/v (amber)",
            'desc': [
                "Tracks average actual daily work shift hours against the statutory legal workday cap, alongside the surplus value rate s/v = (Surplus Product / Wages) x 100%.",
                "Why Useful: Directly measures the extraction of surplus value by capital owners. A soaring s/v rate indicates high capital profits achieved by keeping worker wages low relative to their output."
            ],
            'stats': [
                ("Statutory Workday Cap", f"{cap_h:.1f} Hours", (100, 180, 240)),
                ("Surplus Value Rate (s/v)", f"{sv_rate:.1f}%", (240, 190, 60)),
            ],
            'icon': 'labor',
            'btn_id': btn_id
        }

    if btn_id in ('labor_chart_2', 'labor_chart_2_alienation_health'):
        return {
            'title': "Labor Chart 2: Alienation & Health Hazards",
            'badge': "WORKER ATTRITION",
            'badge_col': (180, 120, 220),
            'category': "Occupational Health & Psychology",
            'cost': "4D Alienation (purple) vs Health Hazard (red) vs Vice Spend (teal)",
            'desc': [
                "Tracks the 4-dimensional Marxian alienation index (from product, labor process, human nature, fellow workers), physiological health attrition rate (x1000), and despair vice spending ($).",
                "Why Useful: Warns of workplace burnout, moral despair, and early mortality caused by repetitive mechanized assembly line shifts. High alienation triggers compensatory spending on alcohol and vice."
            ],
            'stats': [
                ("Alienation Index", f"{alien_val:.1f} / 100", (180, 120, 220)),
                ("Health Hazard Attrition", "Workplace injury & toxic fatigue", (220, 70, 70)),
                ("Despair Vice Spending", "Tavern & escapism outlays", (100, 210, 180)),
            ],
            'icon': 'labor',
            'btn_id': btn_id
        }

    if btn_id in ('labor_chart_3', 'labor_chart_3_consciousness_entertain'):
        return {
            'title': "Labor Chart 3: Consciousness vs Entertainment",
            'badge': "POLITICAL MOBILIZATION",
            'badge_col': (240, 75, 75),
            'category': "Working Class Organization",
            'cost': "Consciousness (red) vs Spectacle Pacification (blue) vs Protest (orange)",
            'desc': [
                "Plots Proletarian Class Consciousness against State Entertainment Pacification and popular Civil Protest Energy.",
                "Why Useful: Tracks the political mobilization of industrial workers. When consciousness outstrips entertainment pacification, workers organize labor unions, launch wildcat strikes, and demand political suffrage."
            ],
            'stats': [
                ("Class Consciousness", f"{consc_val:.1f}%", (240, 75, 75)),
                ("Protest Energy", f"{protest_e:.2f} / 10.00", (240, 150, 50)),
            ],
            'icon': 'theatre',
            'btn_id': btn_id
        }

    if btn_id in ('labor_chart_4', 'labor_chart_4_strikes_sabotage'):
        return {
            'title': "Labor Chart 4: Strikes & Machine Sabotage",
            'badge': "WORKPLACE RESISTANCE",
            'badge_col': (235, 60, 60),
            'category': "Industrial Resistance Dynamics",
            'cost': "Strikers (bright red), Sabotaged Machines (amber), Active Machines (green)",
            'desc': [
                "Displays the number of striking factory workers (wildcat walkouts), industrial machinery destroyed by Luddite sabotage, and active operational machines.",
                "Why Useful: Measures the direct physical and economic cost of labor unrest. Strikes halt assembly lines, while Luddite sabotage destroys valuable mechanical capital stock."
            ],
            'stats': [
                ("Active Strikes", "Workers on wildcat walkouts", (235, 60, 60)),
                ("Sabotaged Machinery", "Physical equipment wrecked", (220, 140, 40)),
                ("Operational Capital Stock", "Active mechanized machinery", (110, 215, 130)),
            ],
            'icon': 'sabotage',
            'btn_id': btn_id
        }

    return None


# =============================================================================
# 4. CROSS-NATION COMPARISON MODAL TABS & FILTERS
# =============================================================================

def build_compare_tooltip(btn_id: str, world: dict) -> dict | None:
    """Tooltips for the 5 comparative accounts tabs and commodity filters."""
    if btn_id == 'compare_tab_1':
        return {
            'title': "Comparison Tab 1: Macro Accounts & Leaderboard",
            'badge': "GLOBAL SCOREBOARD",
            'badge_col': ACCENT,
            'category': "Cross-Nation Analytics",
            'cost': "Hotkey: Click tab or press C to open Comparison Suite",
            'desc': [
                "Multi-nation executive scoreboard comparing Population, GDP Output ($/turn), Treasury Vaults, Standing Military Units, and Current Account Trade Balances with turn-over-turn deltas.",
                "Why Useful: Provides a high-level strategic overview to benchmark your sovereign power against global rivals and identify which nations are economically expanding or declining."
            ],
            'stats': [("Tab Scope", "All Sovereign Nations", ACCENT)],
            'icon': 'crown',
            'btn_id': btn_id
        }

    if btn_id == 'compare_tab_2':
        return {
            'title': "Comparison Tab 2: Goods & Provincial Economy",
            'badge': "COMMODITY MARKETS",
            'badge_col': (120, 200, 80),
            'category': "Cross-Nation Analytics",
            'cost': "Inspects Food, Wood, and Furniture markets across all provinces",
            'desc': [
                "Detailed provincial commodity ledger showing market prices, physical output, warehouse inventories, and shortages for Food, Wood, and Furniture.",
                "Why Useful: Identifies high-margin regional trade arbitrage opportunities, acute commodity deficits, and lucrative export markets for your domestic industries."
            ],
            'stats': [("Tab Scope", "All Provincial Commodity Markets", (120, 200, 80))],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id == 'compare_tab_3':
        return {
            'title': "Comparison Tab 3: External, FX & Banking",
            'badge': "MONETARY & CREDIT",
            'badge_col': (100, 180, 240),
            'category': "Cross-Nation Analytics",
            'cost': "Tracks Foreign Exchange Rates (NEER) & Commercial Banking Sheets",
            'desc': [
                "Analyzes sovereign foreign exchange strength (Nominal Effective Exchange Rate), bilateral currency exchange matrix, and provincial commercial bank balance sheets (deposits, loans, equity).",
                "Why Useful: Monitors currency appreciation/depreciation and evaluates commercial banking liquidity to detect regional credit crunches before banks fail."
            ],
            'stats': [("Tab Scope", "Monetary FX & Banking Systems", (100, 180, 240))],
            'icon': 'bank',
            'btn_id': btn_id
        }

    if btn_id == 'compare_tab_4':
        return {
            'title': "Comparison Tab 4: Class Wealth Extraction & Attrition",
            'badge': "SURPLUS EXTRACTION",
            'badge_col': (200, 120, 230),
            'category': "Cross-Nation Analytics",
            'cost': "Ledger of Landlord Rent, Capital Profits, Wages & Health Attrition",
            'desc': [
                "Cross-nation comparative ledger tracking landlord rent extraction, corporate capital profits, wage share of GDP, and workplace health attrition rates.",
                "Why Useful: Directly compares the economic efficiency and human exploitation of different sovereign regimes, contrasting feudal agrarianism with industrial capitalism."
            ],
            'stats': [("Tab Scope", "Class Surplus Extraction & Health", (200, 120, 230))],
            'icon': 'pyramid',
            'btn_id': btn_id
        }

    if btn_id == 'compare_tab_5':
        return {
            'title': "Comparison Tab 5: Protest Energy & Grievance Sources",
            'badge': "UNREST ANALYSIS",
            'badge_col': (245, 80, 80),
            'category': "Cross-Nation Analytics",
            'cost': "Pinpoints root grievance drivers for every city across the world",
            'desc': [
                "Analyzes the exact underlying grievance drivers (unemployment, food hunger, tax burden, casualties, inequality) driving civil unrest in each city.",
                "Why Useful: Pinpoint the root causes of revolutionary instability in any territory and apply targeted policy remedies (tax cuts, famine aid, security patrols) before uprisings occur."
            ],
            'stats': [("Tab Scope", "Civil Grievances & Revolution Risk", (245, 80, 80))],
            'icon': 'protest',
            'btn_id': btn_id
        }

    if btn_id == 'compare_filter_food':
        return {
            'title': "Commodity Filter: Staple Food (Grain)",
            'badge': "AGRARIAN SECTOR",
            'badge_col': (120, 200, 80),
            'category': "Provincial Economy Filter",
            'cost': "Click to filter Tab 2 ledger to Food markets",
            'desc': [
                "Filters the Tab 2 provincial market ledger to staple agricultural Food and grain production.",
                "Why Useful: Inspect regional grain prices and discover which cities suffer from food deficits or boast massive export surpluses."
            ],
            'stats': [("Filtered Good", "Food (Grain)", (120, 200, 80))],
            'icon': 'grain',
            'btn_id': btn_id
        }

    if btn_id == 'compare_filter_wood':
        return {
            'title': "Commodity Filter: Raw Wood (Timber)",
            'badge': "FORESTRY SECTOR",
            'badge_col': (190, 150, 70),
            'category': "Provincial Economy Filter",
            'cost': "Click to filter Tab 2 ledger to Timber markets",
            'desc': [
                "Filters the Tab 2 provincial market ledger to raw timber and forestry production.",
                "Why Useful: Monitor lumber supplies needed for workshop manufacturing, construction, and charcoal smelting."
            ],
            'stats': [("Filtered Good", "Wood (Timber)", (190, 150, 70))],
            'icon': 'wood',
            'btn_id': btn_id
        }

    if btn_id in ('compare_filter_furniture', 'compare_filter_furn'):
        return {
            'title': "Commodity Filter: Manufactured Furniture (Wares)",
            'badge': "WORKSHOP SECTOR",
            'badge_col': (90, 140, 230),
            'category': "Provincial Economy Filter",
            'cost': "Click to filter Tab 2 ledger to Manufactured Furniture",
            'desc': [
                "Filters the Tab 2 provincial market ledger to manufactured consumer furniture and artisan wares.",
                "Why Useful: Track industrial workshop profitability and find high-price urban markets to sell finished goods."
            ],
            'stats': [("Filtered Good", "Furniture (Wares)", (90, 140, 230))],
            'icon': 'industry',
            'btn_id': btn_id
        }

    return None
