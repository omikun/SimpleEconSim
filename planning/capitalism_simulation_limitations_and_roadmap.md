# Capitalist Simulation Engine: Limitations, Backlog & Roadmap

This document outlines the theoretical, algorithmic, economic, and technical limitations of the capitalist propagation engine (inspired by Sven Beckert's *Capitalism / Empire of Cotton*), structured as actionable engineering and modeling issues.

---

## Issue Backlog & Work Items

### Tier 1: Core Priority Enhancements (Completed)

- [x] **ISSUE-01: Macro & Spatial Inter-Regional Planning** (Implemented & Verified in test_08)
  - **Limitation:** Elite agents currently plan and optimize primarily within their local region/tile market. They cannot formulate geographic supply chain triangles (e.g., importing raw cotton from an agricultural region, spinning it in an urban industrial region, and exporting finished textiles to foreign markets for luxury trade).
  - **Implemented Solution:** Added `evaluate_spatial_trade` in `EliteCapitalistPlanner` with `SPATIAL_LUXURY_IMPORT`, `SPATIAL_INPUT_IMPORT`, and `SPATIAL_EXPORT` across neighboring tiles. Verified strictly conserved inter-regional currency transfers.

- [x] **ISSUE-02: Ecological, Biome & Geological Gating** (Implemented & Verified in test_06)
  - **Limitation:** Currently, any lord on any tile can mandate cotton cultivation or open an iron mine regardless of geography. In reality, cotton/sugar/tobacco require specific climates (tropical/subtropical frost-free days, alluvial soil), and coal/iron require specific geological deposits.
  - **Implemented Solution:** Added `allowed_climates`, `disallowed_climates`, `allowed_biomes`, `disallowed_biomes`, and `required_terrain_tags` to `TransformationOperator`. Bounded cotton/sugar to warm/temperate/subtropical zones, and mining away from oceanic biomes.

- [x] **ISSUE-03: Class Legislation & State Power as an Economic Weapon** (Implemented & Verified in test_07)
  - **Limitation:** When labor shortages occur and wages spike ($LTR > 1.2$), capitalists and lords in the current model simply absorb high wages. Historically, as Beckert and Polanyi emphasize, elites weaponized the state to pass wage-capping statutes (e.g., *Statute of Laborers*), criminalize vagrancy, ban worker combinations, or enforce parish workhouses.
  - **Implemented Solution:** Introduced `petition_statute_of_laborers` and `enforce_vagrancy_decree` operators into `TransformationGraph`. When acute wage squeezes threaten employer profit margins, elites cartelize and petition the state to legally cap wages and enforce vagrancy workhouse labor.

---

### Tier 2: Economic & Algorithmic Sophistication

- [x] **ISSUE-04: Rational Price Expectations & Agricultural Cobweb Damping** (Implemented & Verified in test_09)
  - **Limitation:** Agents plan using myopic spot prices. If multiple lords simultaneously enclose land for sheep grazing, they do not anticipate future market gluts that crash wool prices.
  - **Implemented Solution:** Added `compute_expected_price(region, good)` in `TransformationGraph` using EMA price trends ($P_{\text{trend}}$) and pending capacity damping ($\mathbb{E}[P] = P_{\text{trend}} \times (1 + Q_{\text{pending}} / \bar{Q}_{\text{sales}})^{-1.10}$). When the first lord commits land to wool pasture, `pending_capacity` drops expected wool prices, redirecting subsequent lords to alternative sectors (cotton, sugar, grain, war capitalism) and damping the Ezekiel cobweb cycle.

- [x] **ISSUE-05: Continuous Multi-Asset Portfolio Optimization (Linear Programming)** (Implemented & Verified in test_14)
  - **Limitation:** The planner previously picked a single discrete operator rather than optimizing continuous land allocation across multiple crops and risk profiles.
  - **Implemented Solution:** Added `EstatePortfolioOptimizer` in `economy/portfolio_optimizer.py`. Solves bounded continuous land allocation across food security (wheat/grain to feed domestic serfs), customary peasant stability floors (preventing immediate revolt), and discretionary commercial cash crops (wool pastures, cotton/sugar plantations).

- [x] **ISSUE-06: Capital Goods Supply Chains & Machinery Depreciation** (Implemented & Verified in test_10)
  - **Limitation:** Factory machinery was previously an abstract integer without physical industrial inputs or wear-and-tear depreciation.
  - **Implemented Solution:** Added `apply_machinery_depreciation` (operational wear-and-tear breaking machinery every 12 turns or under heavy shifts) and registered two Department I capital goods operators:
    1. `maintain_repair_machinery`: Consumes $1\times\text{iron}$ + cash to restore broken machines and eliminate the 50% productivity penalty.
    2. `construct_machinery`: Consumes $2\times\text{iron} + 1\times\text{coal}$ + cash to increase `machinery_level` and employment capacity. All cash is strictly conserved to metalworkers/artisans or the Crown.

---

### Tier 3: Historical "War Capitalism" & Coercive Imperialism

- [x] **ISSUE-07: Sovereign Colonial Conquest & Armed Land Expropriation** (Implemented & Verified in test_11)
  - **Limitation:** Land acquisition was restricted to domestic legal enclosure of customary tenant plots. Historical war capitalism relied on military conquest of foreign indigenous territories and armed frontier violence.
  - **Implemented Solution:** Registered `chartered_frontier_conquest` operator. Elite agents with liquid capital ($C \ge 50$) dispatch an armed expeditionary force to uncolonized frontier/wilderness territories (`wilderness = True` or `wilderness_pop > 0`). Conserves money down to the penny: \$35 distributed as mercenary soldier pay to commoners, \$15 paid to the Crown as charter fee. Dispossesses frontier native populations and establishes primary export enclaves (cotton, sugar, tobacco, iron ore) delivering raw materials to metropolitan investors.

- [x] **ISSUE-08: Coerced & Enslaved Labor Regimes Beyond Domestic Serfdom** (Implemented & Verified in test_13)
  - **Limitation:** Only domestic serfs with customary usufruct rights were modeled. The historical transatlantic plantation complex (Beckert's War Capitalism) commodified human beings as transferable property.
  - **Implemented Solution:** Registered `procure_captive_labor` and `mandate_plantation_labor_gang` operators in `TransformationGraph` and wired them to `EliteCapitalistPlanner`. Elites procure captive labor ($+5$ per shipment) via triangular trade of manufactured goods (`rum`, `cloth`) or merchant coin (\$25 conserved to commoners). Plantation gang labor forces unfree labor into intensive primary extraction (15 units of cotton/sugar/tobacco per cycle) with zero wage cost, armed overseer supervision costs (\$10 paid to commoner guards), and mortal physical attrition ($-1$ captive labor per cycle).

- [x] **ISSUE-09: Financial Leverage, Bills of Exchange & Credit Bubbles** (Implemented & Verified in test_15)
  - **Limitation:** Agents only borrowed static bank loans. Merchant banking historically created elastic paper money, trade bills of exchange, and speculative asset bubbles.
  - **Implemented Solution:** Implemented `BillOfExchange` and `CreditMarketManager` in `economy/finance_bills.py`. Supports negotiable trade credit instruments, commercial bill discounting with present-value haircuts, maturity settlements, debt default mechanics, and systemic leverage monitoring.

---

### Tier 4: Technical & Performance Infrastructure

- [x] **ISSUE-10: Event-Driven Fast-Path for Starving Commoners** (Implemented & Verified in test_12)
  - **Limitation:** Non-elites are split across $n$ cohorts, meaning a starving dispossessed serf could wait several turns before their cohort ran, leading to preventable starvation deaths.
  - **Implemented Solution:** Added an emergency fast-path in `LaborMobilityScheduler.step_labor_cohort`. Agents experiencing acute hunger (`hungry_steps > 0`), dispossession, or eviction memory bypass the cohort round-robin cycle and are prepended to the execution queue, prioritizing them for open corporate factory vacancies and immediate wage income while maintaining sub-second total execution.

- [x] **ISSUE-11: Full Fast Slot Acceleration & UI Symbol/Texture Mapping for Dynamic Commodities** (Implemented & Verified in test_16, test_17, test_18)
  - **Limitation:** Dynamically registered string goods previously lacked pre-allocated array slots and visual render metadata.
  - **Implemented Solution:** Implemented `economy/commodity_visuals.py` providing fast contiguous integer slot index lookups, category classification, emoji/unicode symbols, profession badges, and procedural texture styling for both core and dynamic goods. Built `economy/map_generator.py` with balanced geological gating for ore deposits (iron, coal, nitrates), climate zoning (subtropical, temperate, cold), and deterministic map regeneration.

---

### Tier 5: Worldview UI, Geopolitics & Macro Circulation (Current Backlog)

- [x] **ISSUE-12: Map Overlays, Badges & Estate/Financial HUD Inspector** (Implemented & Verified in test_capitalism_ui_overlays)
  - **Requirement:** Render commodity glyphs (⛏️ iron, ⬛ coal, ☁️ cotton, 🧵 cloth, 💎 luxuries) and geological deposit icons on hex tiles using `commodity_visuals.py` metadata. Add an inspector panel for selected tiles displaying land tenure plot allocations (wheat vs. pasture vs. cotton), active bills of exchange and yield curves, machinery levels and breakdown warnings, and frontier colonial estates with captive labor cohorts.
  - **Implemented Solution:** Added procedural vector icons in `ui_icons.py` (`cotton`, `cloth`, `luxuries`, `steam_mill`). Updated `worldview_map.py` with geological deposit beacons (`iron_ore`, `coal_seam`, `guano`) and capitalist badges (`M1`/`!BRK`, `WOL`, `COT`, `LUX`, `CAP`). Added subtabs (`[Parcels & Land]` vs `[Capital & Credit]`) and 3 financial inspector cards in `worldview_cadastre.py` with interactive repair action. Verified with full regression and unit test suite.

- [x] **ISSUE-13: Transatlantic Trade Triangle & Foreign Luxury Import Cycle** (Implemented & Verified in test_triangular_trade_and_luxuries)
  - **Requirement:** Multi-region commodity cycle between metropolis, agrarian countryside, and overseas colonial outposts. Finished cloth exported overseas to purchase fine foreign luxuries (silk, porcelain, tea, rum) returning to metropole elites, boosting prestige and driving further land conversions.
  - **Implemented Solution:** Built `economy/trade_circuit_discovery.py` featuring startup topological cycle discovery (finding 60 candidate triangular and bilateral loops) auto-serialized to `scenarios/discovered_trade_circuits.json`. Implemented `CircuitGatingEvaluator` checking geological deposits (`has_iron_deposit`), biomes, and workshop recipes with progressive route activation (`RESOURCE_LOCKED`, `TECH_LOCKED`, `DORMANT_UNEXPLORED`, `ACTIVATED_ROUTE`). Implemented `TradeTriangleManager` and `MerchantVoyage` in `economy/triangular_trade.py` with dynamic arbitrage evaluation ($-\ln(\text{Margin}) < 0$), multi-turn voyage state machine, freight cash conservation, and Crown customs tariffs. Implemented `ConspicuousConsumptionManager` in `economy/conspicuous_consumption.py` tracking prestige scores, status tiers (*Gentry* $\to$ *Burgher* $\to$ *Lord of the Manor* $\to$ *Magnate*), and status decay. Integrated into `EliteCapitalistPlanner`, `worldview_cadastre.py` Card 4 with interactive `[Charter Voyage]` button, and `worldview_map.py` `TRG` badges.

- [x] **ISSUE-14: Luddite Machine-Breaking & Class Resistance Events** (Implemented & Verified in test_luddites_and_rivalry)
  - **Requirement:** When statutory wage caps and enclosures push worker restiveness above threshold, secret worker combinations form nocturnal machine-breaking raids, destroying factory machinery levels unless suppressed by constabulary or pacified by relief.
  - **Implemented Solution:** Implemented `LudditeMovementManager` and `LudditeState` in `economy/luddite_resistance.py`. Tracks secret combination strength driven by statutory wage caps, starvation wages, mechanization, and unemployed cottagers. Triggers clandestine nocturnal raids when combination strength $\ge 50.0$, breaking factory machinery (`machinery_broken = True`, reducing `machinery_level`). Supported player/elite countermeasures: hiring armed factory guards (`hire_factory_guards`) to contest and repel raids, granting Speenhamland bread relief (`grant_parish_bread_relief`) to pacify workers, and raising firm wages. Integrated into `worldview_cadastre.py` Card 1 with live threat indicators and interactive defense buttons, plus map `LUD` badges in `worldview_map.py`.

- [x] **ISSUE-15: AI Nation Capitalist Propagation & Geopolitical Rivalry** (Implemented & Verified in test_luddites_and_rivalry)
  - **Requirement:** Enable rival AI nations to observe metropolitan industrialization and either copy industrial reforms, entrench coercive agrarian commodity dependency, or impose protective mercantilist tariffs.
  - **Implemented Solution:** Implemented `GeopoliticalRivalryManager` and `RivalNationState` in `economy/geopolitical_rivalry.py`. Evaluates metropolitan manufactured export volume across non-player rival nations, dynamically triggering one of three strategic postures:
    1. `MERCANTILIST_TARIFF`: Rival government erects high protective tariff walls (40%) to shield domestic handloom artisans against cheap imported cloth.
    2. `INDUSTRIAL_EMULATION`: Rival government with mineral deposits (coal/iron) and treasury state-subsidizes competing mechanized steam mills on its capital tile to break British monopoly.
    3. `AGRARIAN_DEPENDENCY`: Warm-climate rivals lacking minerals peripheralize by converting estate plots to raw cotton monoculture for metropolitan export.
    Wired into `scenario_empire_of_cotton.py` and regression tested.

