# Call of Capital: Modern Economic Warfare (`SimpleEconSim`)

**Call of Capital: Modern Economic Warfare** (built on the **SimpleEconSim** engine) is a multi-scale political economy, historical crisis, and grand strategy simulator. Unlike traditional strategy games where resources materialize from abstract modifiers, every unit of grain, ore, textile, land parcel, bond, and currency in the world is produced, owned, traded, taxed, or seized by living, aging, and reproducing human agents (`Person`) under **strict penny-exact conservation**.

---

## Table of Contents

1. [Goals of the Game & Core Philosophy](#1-goals-of-the-game--core-philosophy)
2. [Ways to Run the Game & Utilities](#2-ways-to-run-the-game--utilities)
3. [Available Simulation Mechanisms](#3-available-simulation-mechanisms)
4. [What to Expect Next (Roadmap)](#4-what-to-expect-next-roadmap)
5. [Repository Architecture](#5-repository-architecture)

---

## 1. Goals of the Game & Core Philosophy

### The Player's Role
You act as the **Sovereign State** (and its regional/provincial apparatus) governing an interconnected multi-region economy, or as a historical ruler navigating an authored crisis campaign. You do not telepathically command citizens to work or eat; instead, you shape their material incentives, property laws, infrastructure, fiscal/monetary rules, and diplomatic/military posture—and then Deal with the emergent class, fiscal, and geopolitical consequences.

### Manifesto Direction: A Nation Depends on Its People's Networks
The intended direction extends the current state-centered role: **power emerges from relationships among people**. Trusted organizers mobilize others toward concrete goals; durable communities sustain collective action; bridges between groups make coalitions possible. Governments depend on these networks to act, and their decisions reshape the networks in return. Material conditions create interests and grievances, while relationships shape whether people can act on them together.

The player should be able to govern while in power and, after being overthrown, continue as a displaced leader organizing a movement to regain power. Supporters, obligations, rivals, and persistent organizations should connect those phases of play. The standalone laboratory implements the first version of this continuity; extending it to the existing campaigns remains a design commitment.

The first experiment is an isolated network playtest over the terrain map, selected through a separate launcher, with the broader simulation replaced by explicit scenario inputs. Its balance and interface remain open to playtest revision; integration follows evidence that the loop is enjoyable. See the [manifesto](docs/gdd.md#manifesto-a-nation-is-a-network-of-people) and [prototype discussion](planning/people_network_layer.md).

The [first implementation plan](planning/people_network_first_implementation_plan.md) records the design of the desktop Network Laboratory, including recruitment, coalition bargaining, displacement and restoration, terrain views, isolation boundaries, and playtest acceptance gates.

### Play the Network Laboratory

The standalone network prototype opens with a plain-language overview, suggested actions, a terrain map with support markers, and a named network diagram. Launch: `venv/bin/python -m client.desktop.network_lab`. It runs pressure propagation and competing coalitions over terrain, with governing, displacement, restoration, conditional group agreements, scarce public allocations, volunteer breaks, and causal history. Open Groups to see the demands and budget. Use `--start displaced` to begin in opposition. The existing economic simulation does not run in this client. See the [laboratory guide](docs/people_network_lab.md) for controls, saves and verification, and the [implementation report](planning/reports/people_network_coalition_mechanics.md) for current limits.

The separate **Patronage** ruleset adds brokers, repair contracts, hiring control, finite payments, personal toll exemptions, job dependence, public/private promises and evidence. Launch with `venv/bin/python -m client.desktop.network_lab --ruleset patronage`. Win by governing with five council commitments and a working bridge from round 12 onward; public access, private gains and survival are reported separately. See the [play guide and tested winning routes](docs/people_network_patronage.md), [implementation plan](planning/people_network_patronage_implementation_plan.md), and [verification report](planning/reports/people_network_patronage.md). The classic laboratory remains available.

The integrated experiment is [Governing through society](planning/governing_network_implementation_plan.md), starting with Egypt's grain crisis. Launch `venv/bin/python -m client.desktop.app --scenario egypt-1877 --ui-mode guided --governing-network governing`. Govern through food, tax and debt decisions while people autonomously petition, bargain or withhold work through the existing economy. Three community summaries, current and planned walkouts, policy costs and at most two demand cards appear over the terrain without individual recruitment. See the [plain-language guide](docs/governing_campaign.md), [ownership register](planning/governing_network_ownership_register.md) and [verification report](planning/reports/governing_network_governing.md). The read-only `observe` mode remains available; `off` is the default. Opposition and return remain a later phase, and human playtesting still needs to establish whether the integrated loop is enjoyable.

### Core Strategic Tensions
Every decision pulls against competing structural constraints:
- **Domestic Subsistence vs. Cash-Crop Export & Debt Service**: Diverting fertile river basins and peasant labor toward export cash crops (like cotton) raises foreign exchange for bond coupons, but hollows out local grain supply, triggering famine, hoarding, and food riots.
- **Sovereignty vs. Foreign Creditors & Gunboat Diplomacy**: Defaulting on or restructuring sovereign debt (`ISRB` / foreign bonds) frees domestic revenue for public granaries and clinics, but risks triggering foreign receivership (such as the *Caisse de la Dette Publique*), naval blockades, and military occupation of strategic corridors (`Alexandria`, `Suez Canal`, `Tel el Kebir`, `Cairo`).
- **Capital Accumulation vs. Class Struggle**: Enclosing the commons, depressing wages, or allowing industrialists to pay workers in company scrip accelerates factory profits and tax revenue, but drives up 4-dimensional worker alienation, unionization, general strikes, Luddite machine-breaking, and revolutionary communes.
- **Industrial Growth vs. Ecological & Metabolic Rift**: Intensive monoculture and coal-powered factories deplete soil fertility, exhaust mines, and pollute river systems unless balanced with crop rotation, fallowing, and pollution controls.

### Dual Game-Time Clock
The simulation runs on a dual timescale:
- **Demographic & Institutional Time**: `1 turn = 1 agent lifecycle year` (aging, career mobility, reproduction, bond coupon schedules, election cycles).
- **Agricultural & Weather Cycle**: A `10-turn` seasonal cycle (`turn % 10`) drives planting, flood/drought shocks, harvest yields, and winter heating/subsistence pressure.

### Authored Historical Campaigns & Sandbox Play
1. **Egypt 1877: Grain & Debt Crisis (`egypt_1877`)** — Step into the role of Khedive Ismail Pasha's government in 1877 (Chapters I & II). Balance peasant subsistence along the Nile against the Anglo-French *Caisse de la Dette Publique*, cotton export dependence, merchant crop-credit traps, and British naval pressure at Alexandria and the Suez Canal.
2. **Empire of Cotton (`empire_of_cotton`)** — Navigate the global triangular trade linking industrial textile mills, raw cotton frontiers, merchant shipping lanes, and coerced vs. wage labor regimes.
3. **Labor Frontier Rivalry (`labor_frontier_rivalry`)** — Compete for scarce mobile labor across industrializing provinces using frontier pioneer grants, homesteading, wage competition, and social welfare.
4. **Strategic Supply Rivalry (`supply_rivalry`)** — Secure critical industrial inputs (iron, coal, timber, grain) across contested mountain passes and maritime chokepoints.
5. **Procedural Multi-Nation Geopolitical Sandbox** — Generate custom 3D Voronoi/hex island or continental worlds with competing sovereign nations, dynamic regimes, floating exchange rates, and full policy toolkits.

---

## 2. Ways to Run the Game & Utilities

All commands below assume the local virtual environment at `./venv/bin/python`. A top-level [`sitecustomize.py`](file:///Users/sli/Code/sitecustomize.py) automatically registers all domain folders (`core/`, `agents/`, `micro/`, `meso/`, `macro/`, `economy/`, `terrain/`, `scenarios/`, `trace/`, `client/worldview/`) on `sys.path`.

### A. Primary Desktop Graphical Client (`Worldview`)
Launch the full Pygame + 3D Voronoi/Hex desktop game with campaign selection, Guided Mode, and Sandbox Mode:

```bash
./runworldview.sh
# or directly:
./venv/bin/python -m client.desktop.app
```

- **Guided Mode vs. Advanced Sandbox Mode**:
  - **Guided Mode** presents a streamlined historical crisis HUD: a top ribbon with cash, grain reserves, sovereignty status, and turn controls; a curated action dock (`Subsidize Bread`, `Release Grain`, `Ration Grain`, `Pay Coupon`, `Negotiate Debt`, `Capital Controls`, `Guard Corridor`, `Modernize Ports`); narrative crisis cards; and an end-of-chapter multi-pillar debrief (`Food Security`, `Fiscal Health`, `Sovereignty`, `Social Stability`).
  - **Advanced Mode** unlocks all **9 thematic map layers**, **6 left sovereign drawers** (`Fiscal`, `Monetary`, `Land`, `Social`, `Trade`, `Politics`), the **10-chart right telemetry sidebar**, and deep-dive modal inspectors (`Cadastre`, `Citizens`, `Compare`, `Causal Trace Evidence`).
- **Key Desktop Controls**:
  - `Space`: Pause / Resume simulation
  - `N` or `.`: Step forward 1 turn while paused
  - `[` / `]`: Decrease / Increase simulation speed (`1x` to `20x`)
  - `1`–`9`: Switch thematic map overlays (`Terrain`, `Wealth`, `Population`, `Food`, `Unrest`, `Trade`, `Pollution`, `Land Ownership`, `Geopolitics`)
  - `Tab`: Toggle between Guided Mode and Advanced/Sandbox Mode
  - `C`: Open Region Comparison Matrix
  - `P`: Open Citizen Roster & Biography Inspector
  - `L`: Open Land Cadastre & Parcel Map

### B. Browser / Mobile Web Client, Server Control Center & Tech Simulator

#### 1. Unified Server Control Center (`:8000`) — Remote Start / Stop / Restart
Launch the standalone **Server Control Center** to remotely monitor, turn on/off, restart, and inspect live logs for **Call of Capital (`:8081`)**, **Mapgen2 Terrain Explorer (`:8080`)**, and the **Tech Tree & Leapfrog Simulator (`:8082`)** from any desktop or mobile browser:

```bash
./venv/bin/python client/web/manager_server.py --port 8000 --host 0.0.0.0
```
- Open `http://localhost:8000` (or `http://<your-lan-or-tailscale-ip>:8000` remotely).
- Each service card (`👑 Call of Capital`, `🗺️ Mapgen2 Terrain Explorer`, `🔬 Tech Tree & Leapfrog Simulator`) provides **Launch**, **Stop**, **Restart**, **Reload Log**, and **Open in Browser** controls.

#### 2. Standalone Tech Tree & Leapfrog Simulator (`tech_sim_web.py` on `:8082`)
Launch the interactive **Emergent Multi-Avenue Discovery, Refinement & Guild Leapfrog Simulator** directly from the command line (or toggle it remotely via the `:8000` Control Center):

```bash
./venv/bin/python tech_sim_web.py --port 8082 --host 0.0.0.0
# or via module:
./venv/bin/python -m client.web.tech_sim_server --port 8082
```
- **How to Operate the Tech Simulator (`http://localhost:8082`)**:
  1. **Select an Empire Archetype Preset**: Choose **Maritime Pioneer** (high wages, cheap fuel, ghost acres, high late-era incumbent guilds), **Agrarian Hegemon** (cheap labor, distant fuel, rich treasury for state subsidies), or **Latecomer Challenger** (0% legacy guild blockades, primed to steal Tier 1–2 and leapfrog).
  2. **Pick a Target Technology**: Choose from the 4 flagship multi-avenue deep dives (**Gunpowder [Class I]**, **Steam Power [Class II]**, **Combustion [Class III]**, **Microchips [Class IV]**) or use the dropdown to select **any technology dynamically synced from [`macro/innovation.py`](file:///Users/sli/Code/macro/innovation.py) (`TECH_CATALOG`)**.
  3. **Configure Discovery Avenues & Factor Prices**: Select the active local catalyst (e.g., *Flooded Pit Mine*, *Blast Furnace Bellows*, *Dutch Polder Drainage*, *Brine Pressure Boilers*, or *Upstream River Barge*), adjust **Resource Proximity ($G_{\text{prox}}$)**, toggle the **Local Bottleneck Crisis ($C_{\text{crisis}}$)**, and tune **Wage-to-Fuel Ratio ($E_{\text{ratio}}$)**, **Ghost Acres ($S_{\text{supply}}$)**, and **Scholar-Artisan Networks ($M_{\text{net}}$)**.
  4. **Choose Prototype Operating & State Subsidy Mode**:
     - **Commercially Competitive (`+Tax`, `1.0x XP`)**: Self-sustaining when wages are high and fuel is cheap; stalls if labor is too cheap.
     - **Standard State Subsidy (`-25g/t`, `0.5x XP`)**: State arsenal funding that progresses at half speed regardless of low wages.
     - **Crash State Mandate (`-100g/t`, `1.0x XP`)**: Pays `4x` upkeep to replicate the `4.0x` adjacency/commercial bonus out of the State Treasury.
  5. **Test `+1 Tier` Espionage & Local Refinement**: Click **Launch Spy Mission (+1 Tier)** to steal blueprints one tier at a time up to the Era's **Complexity Ceiling** (`85%` Class I, `65%` Class II, `50%` Class III, `30%` Class IV), gated by physical input resources and prerequisite sibling techs. Once at the theft ceiling, click **+1 Turn / +5 Turns** to refine the stolen tier domestically all the way to **Tier 4**!
  6. **Resolve Incumbent Guild Legislation**: When entrenched guilds enact protectionist laws (e.g., *The Locomotive 'Red Flag' Act of 1865*, throttling Refinement XP to `25%`), test **Parliamentary Repeal** (`-40 Pol`, `-15% Stability`), **Eminent Domain Buyout** (`-400g`), or **Greenfield / Colonial Bypass** (`Free`, `0.75x Artisan Net`).
- **Programmatic REST API**:
  - `GET /api/health` — Server status and live `TECH_CATALOG` sync count.
  - `GET /api/catalog` — Full JSON specification of all multi-avenue and `macro/innovation.py` technologies.
  - `POST /api/simulate` — Run headless multi-turn simulations via JSON payload (`{"tech_id": "steam_engines", "turns": 25, "subsidy_mode": "crash"}`).

#### 3. Call of Capital Simulation Web Server (`sim_server` / `client/web/server.py`)
Run the simulation server with a browser/mobile front-end (automatically prints a terminal QR code for LAN mobile/tablet connection):

```bash
./venv/bin/python -m sim_server.web_server
# or via the Voronoi Web Server on port 8081:
./venv/bin/python client/web/server.py --port 8081
```
- Open `http://localhost:8080` (or `:8081`) in any desktop or mobile browser.
- Supports scenario selection, turn stepping, policy enactment, map inspection, and causal trace querying via JSON API endpoints.

### C. Standalone & Experimental Economic Runners
Run focused economic simulations and terminal/live-chart experiments without the full 3D geopolitical desktop UI:

```bash
# Classic single-region terminal / chart simulation
./venv/bin/python econsim.py

# Live animated matplotlib dashboard of prices, wealth, and classes
./venv/bin/python economy/econsim_live.py

# Two-region trade, migration, and arbitrage laboratory
./venv/bin/python economy/econsim_two_region.py

# Monetary velocity, inflation, and trade balance laboratory
./venv/bin/python economy/econsim_trade_money.py

# Automated macroeconomic shock & policy response experiments
./venv/bin/python economy/economic_shock_experiment.py
```

### D. Terrain, 3D Micropolygon & Map Generation Tools
Explore and tune the procedural tectonic, hydrological, Voronoi, and 3D software-rasterized terrain pipelines:

```bash
# Interactive GUI for tectonic plates, rainfall, rivers, and biomes
./venv/bin/python terrain/mapgen_gui.py

# Web-based map generator preview
./venv/bin/python terrain/mapgen_web.py

# High-resolution 3D micropolygon island renderer
./venv/bin/python terrain/render_island_micropolys.py

# Voronoi geopolitical border & province renderer
./venv/bin/python terrain/render_voronoi_geopolitics.py

# Classic hex-grid terrain viewer
./venv/bin/python terrain/hexview.py
```

### E. Causal Trace, Checkpoint & Diagnostic CLI Utilities
Every simulation run records a binary/indexed **Causal Trace (`TraceIndex` / `.ctr`)** linking metric shifts to exact code causes (`StockDelta`, `DecisionEvent`, `BlockedAction`, `FinancialTransfer`):

```bash
# Inspect, audit, or export a saved causal trace (.ctr) file
./venv/bin/python trace/trace_report.py --run outputs/<run_file>.ctr --audit
./venv/bin/python trace/trace_report.py --run outputs/<run_file>.ctr --coverage
./venv/bin/python trace/trace_report.py --run outputs/<run_file>.ctr --kind stock_delta
./venv/bin/python trace/trace_report.py --run outputs/<run_file>.ctr --decode-jsonl outputs/trace.jsonl

# Audit codebase financial/stock writers against causal trace instrumentation
./venv/bin/python trace/causal_gap_inventory.py --check
./venv/bin/python trace/causal_gap_inventory.py --markdown outputs/causal_gaps.md

# Verify deterministic simulation checkpoint save/restore
./venv/bin/python core/simulation_checkpoint.py
```

### F. Historical Campaign Audits, Benchmarks & Test Suite
```bash
# Run the full unit and integration test suite (200 test modules)
./venv/bin/python -m unittest discover -s tests

# Run specific core verification suites
./venv/bin/python -m unittest discover -s tests -p "test_state_handler.py"
./venv/bin/python -m unittest discover -s tests -p "test_trace_*.py"
./venv/bin/python -m unittest discover -s tests -p "test_scenario_campaign.py"

# Run Egypt 1877 campaign balance & historical fidelity audits
./venv/bin/python scripts/audit_egypt_strategic_integration.py
./venv/bin/python scripts/audit_egypt_chapter_two.py
./venv/bin/python scripts/audit_egypt_political_economy.py
./venv/bin/python scripts/audit_egypt_food_project.py
./venv/bin/python scripts/audit_egypt_fiscal_project.py
./venv/bin/python scripts/audit_egypt_sovereignty_project.py

# Run performance & scenario benchmarks
./venv/bin/python benchmarks/benchmark_career_mobility.py
./venv/bin/python benchmarks/benchmark_labor_strategy.py
./venv/bin/python benchmarks/benchmark_supply_default.py
./venv/bin/python benchmarks/benchmark_supply_rivalry.py
```

---

## 3. Available Simulation Mechanisms

### I. Microeconomic Engine (`micro/`, `agents/`)
- **Penny-Exact Order Book Markets (`micro/market.py`)**: Double-auction and posted-price markets for food, grain, cotton, timber, iron ore, coal, tools, textiles, weapons, and luxury goods. Every trade transfers exact cash and inventory between buyer and seller.
- **Multi-Stage Production & Transformation Graph (`micro/buildings.py`, `micro/transformation_graph.py`)**:
  - **Extractive**: Farms (subsistence grain vs. export cotton), Timber Camps, Iron Mines, Coal Mines, Pasture/Livestock.
  - **Manufacturing**: Tool Workshops, Textile Mills, Weapon Foundries, Luxury Artisans, Breweries/Bakehouses.
  - **Civic & Infrastructure**: Granaries, Clinics, Schools, Workhouses, Ports, Rail/Canal Corridors, Fortifications.
- **Agent Lifecycle, Nutrition & Disease (`agents/person.py`, `micro/disease.py`)**:
  - Citizens age, form households, consume food/luxuries, contract contagious or malnutrition-linked diseases (`Cholera`, `Typhus`, `Rickets`), and pass down estates via configurable inheritance laws (`Partible` vs. `Primogeniture`).
- **Labor Market, Career Mobility & Company Scrip (`micro/career_mobility.py`)**:
  - Workers evaluate net utility across wage employment, peasant cultivation, sharecropping, artisanal self-employment, soldiering, or migration.
  - Factory owners can issue **Company Scrip** redeemable only at high-markup **Tommy Shops**, trapping workers in debt peonage unless outlawed by the state (`Outlaw Scrip` policy).
- **Land Cadastre, Tenure & Enclosures (`micro/land_tenure.py`)**:
  - Individual land parcels tracked by fertility, irrigation, improvement level, and legal tenure (`Commons`, `Peasant Smallholding`, `State Domain`, `Private Estate`, `Waqf / Religious Trust`).
  - Supports **Enclosure Acts**, **Homestead Grants**, **Crop Credit & Merchant Offtake Traps** (where moneylenders lock peasants into undervalued harvest pledges), and **Land Redistribution**.

### II. Class Consciousness, Alienation & Resistance (`micro/factions.py`, `micro/class_consciousness.py`)
- **4-Dimensional Worker Alienation (`agents/person.py`)**: Tracks *Product Alienation* (wage vs. output value), *Process Alienation* (factory discipline/deskilling), *Species-Being Alienation* (exhaustion/subsistence misery), and *Social Alienation* (inequality/enclosure displacement).
- **Labor Unions & Strikes**: Workers pool union strike funds, negotiate collective wage floors, and launch wildcat or general strikes that halt factory output.
- **Direct Action & Insurrection**:
  - **Luddite Machine-Breaking**: Displaced artisans sabotage automated mills and capital equipment.
  - **Anti-Enclosure Revolts**: Dispossessed peasants tear down estate fences to reclaim commons.
  - **Bread Riots & Granary Seizures**: Starving urban crowds storm merchant warehouses when grain prices spike.
  - **Urban Barricades, Revolutionary Communes & Assassination Plots**: High unrest and regime illegitimacy trigger street barricades, autonomous regional communes, or plots against oligarchs and state officials.

### III. Meso-Level Geography, Logistics & Arbitrage (`meso/`, `terrain/`)
- **Topographic Edge Barriers & Corridors (`core/world_topology.py`, `terrain/`)**: Regions are connected by physical edges with distance, mountain passes, navigable rivers, canals, or maritime lanes. Transport costs scale with terrain friction, banditry, and infrastructure level.
- **Inter-Regional Merchant Arbitrage (`meso/trader.py`)**: Private merchant caravans and shipping fleets buy surplus commodities in low-price regions and haul them across borders to high-price markets, taking transport losses and paying border tariffs.
- **Floating Foreign Exchange (`meso/forex.py`)**: Cross-currency trade clears through dynamic FX pools where exchange rates float in response to trade imbalances, capital flight, and specie reserves.
- **Internal & Cross-Border Migration (`meso/migration.py`)**: Starving or landless citizens migrate along transport corridors toward regions with higher wages, open frontier land, or public relief.

### IV. Macroeconomic Fiscal, Monetary & Financial Systems (`macro/`)
- **Taxation & Public Finance (`macro/government.py`)**: Progressive or flat income taxes, corporate profit taxes, land value taxes (`Kharaj` / `Ushri`), wealth taxes, sales/excise taxes, and import tariffs.
- **Sovereign Debt & International Sovereign Bond Market (`macro/bonds.py`)**:
  - Domestic treasury bonds held by wealthy citizens and banks, plus foreign-denominated sovereign bonds (`ISRB`).
  - Coupon payments transfer treasury cash directly to bondholders; missed coupons trigger sovereign default penalties, credit spread spikes, and foreign intervention.
- **Fractional-Reserve Banking & Contagion (`macro/banking.py`, `macro/contagion.py`)**:
  - Commercial banks accept household deposits and extend industrial/crop loans.
  - Loan defaults or depositor panics trigger bank runs, interbank contagion cascades, credit crunches, and state choices between **Taxpayer Bailouts**, **Depositor Bail-Ins**, or **Bank Nationalization**.
- **Monetary Regimes (`macro/monetary.py`)**: Switch between **Gold/Silver Specie Standard** (hard constraint on money creation) and **Fiat Currency** (enabling central bank seigniorage, quantitative easing, and inflation risks).
- **Induced Innovation & Royal Bounties (`macro/tech.py`, `macro/royal_bounty.py`)**: Factor scarcity (high wages or expensive coal/land) induces private R&D into labor-saving or land-saving technologies, which the state can accelerate via targeted **Royal Bounties** and public universities.

### V. Geopolitics, Imperialism & Warfare (`macro/geopolitics.py`, `macro/foreign_influence.py`)
- **Regime Types & Political Transitions (`macro/politics.py`)**: `Absolute Monarchy / Khedivate`, `Census Oligarchy`, `Parliamentary Democracy`, `Military Junta`, and `Socialist Republic`, with elections, parliamentary coalitions, and military coups.
- **Imperialist Coercion & Receivership (`macro/foreign_influence.py`, `scenarios/egypt_1877.py`)**:
  - **Unequal Treaties & Capitulations**: Foreign powers demand tariff caps and extraterritorial tax exemptions.
  - **Foreign Debt Receivership (*Caisse de la Dette*)**: Creditor committees garnish railway and customs revenues at the source before the domestic treasury can spend them.
  - **Naval Blockades & Gunboat Diplomacy**: Foreign fleets blockade ports (`Alexandria`), sever maritime trade, and land expeditionary forces along strategic corridors (`Suez Canal` $\rightarrow$ `Tel el Kebir` $\rightarrow$ `Cairo`).
- **Military Logistics & Garrison Defense (`macro/military.py`)**: Standing armies require weapons, rations, and regular pay; unpaid soldiers mutiny or defect during foreign invasions or domestic uprisings.

### VI. Engine Infrastructure & Auditability (`core/`, `trace/`)
- **Centralized State Mutation Handler (`core/state_handler.py`)**: Guarded, zero-Allocation-when-disabled handler (`StateMutationHandler`) for agent/building/treasury cash and inventory mutations, supporting conservation assertions, NaN/Inf guards, watchpoints, and audit logs.
- **Indexed Causal Trace (`trace/trace_index.py`, `trace/trace_codec.py`)**: Records causal chains linking policy actions, market clearings, and stock deltas into compact `.ctr` trace files so every chart movement in the UI can answer *"Why did this change?"* with concrete evidence.
- **Deterministic Simulation Checkpoints (`core/simulation_checkpoint.py`)**: Full deep-state and RNG serialization allowing exact mid-campaign save/restore and counterfactual branching.

---

## 4. What to Expect Next (Roadmap)

Based on active architectural and design roadmaps in [`planning/ARCHITECTURE_AND_PERFORMANCE_PLAN.md`](file:///Users/sli/Code/planning/ARCHITECTURE_AND_PERFORMANCE_PLAN.md) and [`planning/capitalism_simulation_limitations_and_roadmap.md`](file:///Users/sli/Code/planning/capitalism_simulation_limitations_and_roadmap.md):

1. **100% Causal Trace & `StateMutationHandler` Coverage Across All Financial Writers**:
   - Complete the migration of the remaining legacy direct `.cash` and `.inventory` mutations into [`StateMutationHandler`](file:///Users/sli/Code/core/state_handler.py) and finish causal review of all 507 cataloged financial writers tracked by [`trace/causal_gap_inventory.py`](file:///Users/sli/Code/trace/causal_gap_inventory.py).
2. **Multi-Chapter Historical Campaigns & Post-Horizon Sandbox Continuation**:
   - Expand **Egypt 1877** beyond Chapter II (the Urabi Revolt, 1882 British Bombardment of Alexandria, and Battle of Tel el Kebir) with seamless post-campaign continuation and richer counterfactual branches (e.g., successful constitutional nationalist coalition vs. Anglo-French dual control).
   - Expand **Empire of Cotton** and **Supply Rivalry** into multi-chapter guided narratives with dedicated crisis cards and debrief pillars.
3. **Full Desktop $\leftrightarrow$ Web/Mobile Client Parity**:
   - Bring the newly added Desktop Guided Mode crisis cards, causal trace evidence modals, and 3D/Voronoi thematic map overlays to complete visual and functional parity in [`sim_server/`](file:///Users/sli/Code/sim_server) and [`web_client/`](file:///Users/sli/Code/web_client).
4. **Deeper Multi-Tier Industrial & Financial Realism**:
   - **Joint-Stock Corporations & Equity Markets**: Allow multiple capitalist agents and banks to hold tradable shares in large infrastructure (canals, railways) and factory conglomerates.
   - **Endogenous Business Cycles & Inventory Overproduction**: Sharpen credit-driven fixed-capital overinvestment and inventory glut dynamics so classic 19th-century commercial panics emerge endogenously across connected trade networks.
   - **Multi-Nation Diplomatic AI & Alliances**: Enable rival great powers to compete for spheres of influence, sovereign debt tranches, and canal concessions simultaneously.
5. **Continued Hot-Loop & Vectorized Performance Scaling**:
   - Build on the recent **2.0x engine speedup** by batching household consumption and demographic updates across 5,000+ agent worlds while preserving penny-exact determinism.

---

## 5. Repository Architecture

```text
.
├── client/desktop/app.py     # Primary 3D/Voronoi Desktop Game Client entrypoint
├── econsim.py                # Standalone single-region economic simulator entrypoint
├── tech_sim_web.py           # Standalone Emergent Tech Tree & Leapfrog Simulator server (:8082)
├── runworldview.sh           # Convenience launcher for Desktop Worldview
├── sitecustomize.py          # Automatic sys.path registration for all domain packages
├── core/                     # World loop, StateMutationHandler, WorldTopology, checkpoints, config
├── agents/                   # Person lifecycle, household, skills, alienation, decision logic
├── micro/                    # Markets, buildings, land tenure, labor mobility, factions, disease
├── meso/                     # Multi-region trade, merchant arbitrage, migration, floating FX
├── macro/                    # Government, taxes, sovereign bonds, banking contagion, geopolitics
├── economy/                  # Standalone economic runners & shock/monetary laboratory scripts
├── terrain/                  # Tectonic, hydrological, Voronoi, hex, and 3D micropolygon renderers
├── scenarios/                # Authored campaigns (Egypt 1877, Empire of Cotton, Supply Rivalry)
├── trace/                    # Causal trace engine, binary .ctr codec, audit & gap CLI tools
├── client/                   # Desktop UI packages (client/desktop/) & worldview UI modules (client/worldview/)
├── sim_server/               # HTTP/REST & WebSocket simulation server + LAN QR launcher
├── web_client/               # Browser & mobile HTML5/JS client
├── tests/                    # 200 unit, integration, causal trace, and campaign test suites
├── scripts/                  # Historical campaign audits & terrain generator comparison scripts
├── benchmarks/               # Simulation performance & scenario balance benchmarks
├── docs/                     # Game Design Document (gdd.md), feature matrix, and mechanics guides
└── planning/                 # Architectural plans, causal trace roadmaps, and milestone specs
```
