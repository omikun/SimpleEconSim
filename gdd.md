# ENCLOSURE: The Cost of Capital — Game Design Document

**Working Titles:**
- **ENCLOSURE: The Cost of Capital** *(Primary Working Title)*
- **PRIMITIVE ACCUMULATION**
- **DEAD LABOR** *(Marxian allusion: "Capital is dead labor, which, vampire-like, lives only by sucking living labor...")*
- **THE EXTERNALITY ENGINE**
- **COMMODIFIED: The Great Separation**
- **METABOLIC RIFT**
- **SURPLUS & RUIN**
- **THE IRON CAGE**

**Engine Basis:** SimpleEconSim (`sim_world.py`, `region.py`, `forex.py`, `sovereign_bonds.py`, `unrest.py`, `buildings.py`, `wealth_lineage.py`, `transporter.py`).
Each region is a living simulation of individual human agents who possess cash, debts, skills, kin lineage, memory, and physical needs. Every transfer of money, resource, or labor is strictly conserved down to the penny. The accounting audit is not just an invariant—it is an indictment.

---

## 1. Executive Concept & Philosophical Thesis

### 1.1 The Core Proposition
Most strategy games celebrate growth as an unalloyed good. You build a sawmill, line goes up; you discover the steam engine, green numbers pop; you conquer a territory, it becomes your passive resource fountain.

**ENCLOSURE** turns this paradigm inside out:
It is a grand strategy simulation of political economy, finance, and ecological metabolism. It simulates how capitalism actually emerged and how it reproduces itself:
1. **The Starting Harmony of Reciprocity:** The world does not begin as empty terra nullius waiting for flags. Every tile is already inhabited by indigenous peoples, customary peasantries, and tribes living within customary tenure, reciprocal communal obligations, and localized rivalries.
2. **The Enclosure Shock (Primitive Accumulation):** Capital cannot exist without a propertyless working class. To create wage labor, elites violently and legally enclose the commons—fencing off shared pastures, forests, and fisheries, destroying self-sufficient subsistence.
3. **The Great Commodification:** Stripped of the land, human beings are severed from direct access to food and shelter. They have only one thing left to sell: their living labor power. Society transforms into a universal commodity market where land, nature, time, and human beings themselves are priced, leased, and consumed.
4. **The Exploitation Treadmill:** As competition intensifies, capitalists must reinvest or perish. To maintain the rate of profit, they compel workers to toil longer, faster, and harder just to secure enough money to buy back the subsistence they once gathered freely.
5. **The Immiseration-Productivity Paradox:** Technology and labor productivity skyrocket by 1,000%. Industrial factories produce mountains of goods. Yet the humans producing this wealth are more exhausted, alienated, insecure, and indebted than their ancestors.
6. **Externalized Ruin:** The true costs of capital accumulation are never paid by capital. They are externalized onto the human body (child labor, lung rot, stress, shortened lifespans) and onto Nature (clear-cut forests, exhausted soils, toxic runoff, metabolic rift).
7. **The Financial Apex:** As physical production suffers diminishing profit margins, the system financializes. Central banks, fractional reserve lenders, and 20/50/100-turn sovereign bond markets take center stage—funneling imperial tribute, funding resource wars, and enforcing austerity on debtor regions.

### 1.2 The Signature Promise
**Every macroscopic strategy outcome—a financial panic, a sovereign default, a general strike, a peasant jacquerie, a colonial war, an ecological collapse—is traceable all the way down to the exact tile, the exact agent, the ledger balance, the calories withheld, and the uncompensated labor extracted.**

---

## 2. Design Pillars

### Pillar 1: Conserved Value as the Indictment of Capital
Nothing comes from nothing. The game engine enforces absolute conservation of currency, matter, and labor. When an industrialist amasses a fortune of 100,000 ducats, the game's ledger proves exactly who didn't receive it. Profit is revealed not as magic creation, but as uncompensated surplus value extracted from living labor and free gifts stolen from exhausted nature.

### Pillar 2: The Enclosure Vector (From Subsistence to Debt Peonage)
Land begins as a common heritage governed by usufruct and custom. The central strategic vector of statecraft and elite accumulation is *Enclosure*: privatizing the commons, criminalizing customary foraging and gleaning, and imposing monetary head taxes that force autonomous humans into the wage-labor market.

### Pillar 3: Worker Alienation & The Commodification of Human Life
Agents are not mindless worker drones with passive output statistics. They experience deep psychological alienation:
- Alienation from the product: They make luxury furniture they can never afford.
- Alienation from the act of production: Forced cadence, repetitive injury, punitive shifts.
- Alienation from nature: Removal from rural ecology into squalid, smoke-choked tenement blocks.
- Alienation from fellow workers: Pitched against each other in competitive labor auctions and reserve armies of the unemployed.

### Pillar 4: Externalized Ruin & The Metabolic Rift
Firms and state projects show record returns on paper because they externalize their true costs. Smelters boost GDP while blackening skies and sickening adjacent populations; monoculture grain exports generate foreign exchange while depleting soil nutrients. The game calculates an explicit **Externalities Ledger**: unhealed biological damage, pollution accumulation, and societal trauma that inevitably return to trigger systemic collapse.

### Pillar 5: Deep Generational Memory & Class Struggle
Agents remember. A family whose ancestral grazing pasture was seized carries a generational grudge against the enclosing landlord family. Workers remember broken wage promises, strike massacres, and foreclosures. Class struggle is not a random disaster event card; it is the fundamental thermodynamic pressure of the economic engine.

---

## 3. The World: Tiles, Ecology, and the Commons

### 3.1 Customary Commons vs. Enclosed Private Property
Each region tile is an active socio-ecological biome with distinct characteristics:

| Land Status | Usufruct Rights | Survival Autonomy | Capital Extraction | Taxation Potential |
|---|---|---|---|---|
| **Customary Commons** | Open to clan/village; communal grazing, foraging, gathering | High; agents produce subsistence food & firewood without money | Zero; no cash surplus for outside elites | Low; tribute in kind, high resistance to cash taxes |
| **Transitional Leasehold** | Tenancy under customary rents; common rights partially restricted | Moderate; vulnerable to rent spikes and evictions | Moderate; landlords capture grain margins | Moderate; tithes, land levies |
| **Enclosed Private Property** | Strictly privatized; trespassing and poaching criminalized | Zero; agents must pay cash rent or work for wages | Maximum; fully optimized for cash crop / industrial extraction | High; formalized land taxes, stamp duties, corporate yields |

### 3.2 Biome Depletion & The Metabolic Rift
Tiles have natural resource stocks and biological carrying capacity:
- **Fertility & Soil Depletion:** Intensive monoculture cash-cropping (cotton, wheat, tobacco) produces enormous short-term yields but degrades soil organic matter. Without costly restorative inputs (guano, bone meal, chemical nitrates), crop yields collapse into Dust Bowl famine cycles.
- **Forestry & Clear-Cutting:** Forests provide wild game, berries, building timber, and fuel. Enclosing landlords clear-cut forests for charcoal and lumber exports, destroying the local thermal buffer and subsistence safety nets.
- **Hydrology & Effluent:** Upstream textile mills and tanneries dump toxic chemical effluent into rivers. Downstream tiles suffer tainted drinking water, infant mortality spikes, and collapse of river fisheries.
- **Mineral Extraction:** Mines require timber shoring and cheap human bodies. Shaft cave-ins, black lung, and toxic tailings leave permanent scars on local demographics.

### 3.3 The Starting Balance: Reciprocity and Tension
At game start (Year 0):
- The world is fully inhabited. Indigenous nations, autonomous tribes, and peasant communes hold customary rights over nearly all habitable tiles.
- A delicate balance prevails: reciprocal gift-economies, customary tribute, seasonal nomadic migration routes, and local rivalries.
- Trade exists, but it is primarily luxury exchange and ritual diplomacy—not yet a totalizing global market where food, housing, and life itself are bought and sold as financialized commodities.
- The emergent imperial states (e.g. Britain, France, US, Japan, China) control initial core administrative capitals, but their hinterlands are still un-enclosed or held under customary feudal/communal obligations.

---

## 4. Class Structure & Social Agents

Agents in the simulation belong to dynamic social classes shaped by their relation to property, land, and capital:

```
┌─────────────────────────────────────────────────────────────┐
│                 FINANCIAL & INDUSTRIAL OLIGARCHS             │
│    Owns banks, factories, sovereign debt, joint-stock shares │
│    Accumulates unspent financial capital & extracts interest │
└──────────────────────────────┬──────────────────────────────┘
                               │ Private Property / Debt
┌──────────────────────────────▼──────────────────────────────┐
│                    LANDOWNING ARISTOCRACY                   │
│    Controls enclosed estates, timber forests, mineral rights│
│    Collects land rent and evicts non-paying tenants         │
└──────────────────────────────┬──────────────────────────────┘
                               │ Dispossession / Enclosure
┌──────────────────────────────▼──────────────────────────────┐
│                     PETTY BOURGEOISIE                       │
│    Artisans, small shopkeepers, independent craft masters    │
│    Slowly crushed by industrial competition & debt          │
└──────────────────────────────┬──────────────────────────────┘
                               │ Proletarianization
┌──────────────────────────────▼──────────────────────────────┐
│                 WAGE PROLETARIAT (Living Labor)             │
│    Owns no land or capital; sells hours of life for cash    │
│    Trapped on the survival treadmill; alienable & fired      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Criminalization / Vagrancy
┌──────────────────────────────▼──────────────────────────────┐
│              RESERVE ARMY & DISPOSSESSED NATIVES             │
│    Unemployed, vagrants, landless refugees, colonial subjects│
│    Drives wages down; mobilized as strike-breakers or cannon│
└─────────────────────────────────────────────────────────────┘
```

### 4.1 The Alienation Index
Every working agent possesses a psychological and physiological vector:
- `alienation` (0.0 to 1.0): Scales with hours worked, separation from the end-product, workplace danger, and lack of leisure.
- `health_attrition`: Accumulated physical wear and tear (toxic fumes, machinery accidents, malnutrition).
- `despair` & `numbing`: High alienation and low wages drive spending toward escapist commodities (gin, opium, gambling) which transfer the worker's remaining wages directly to merchant capitalists.
- `class_consciousness`: An agent's understanding of systemic exploitation, boosted by workplace solidarity, literate union organizers, shared strikes, and state repression memory.

---

## 5. The Conserved Financial & Economic Machinery

### 5.1 Conserved Money as Absolute Audit
The engine rejects the standard video game fiction of abstract "mana" or spawned money:
- Every currency unit (Dollar, Pound, Yen, Franc, Silver) is numbered and tracked.
- The per-turn audit verifies: `Total_Currency = Agents_Cash + Bank_Deposits + Sovereign_Treasuries + FX_Desks`.
- Profit made by a factory is mathematically identical to: `Revenue_From_Sales - (Wages_Paid + Raw_Material_Costs + Wear_Tear)`.
- When wages are suppressed below the cost of caloric reproduction, the surplus flows directly into the capitalist's vault or bank deposit.

### 5.2 The Commodification of Labor
Before enclosure, an agent worked until subsistence needs were met, then rested, socialized, or engaged in ritual. Under capitalism:
- The agent must pay cash rent and buy food in the market.
- Capitalists set the working day (e.g., 10, 12, 14, 16 hours).
- **The Rate of Surplus Value ($s/v$):** If an 8-hour shift produces the value needed to feed the worker, any additional hours worked represent pure uncompensated surplus value pocketed by the owner.
- When machines speed up production, the worker does not work fewer hours; rather, the output quota increases, raising physical exhaustion while keeping wages anchored to bare biological survival.

### 5.3 The Banking & Credit System
- **Deposit Hoarding:** Capitalists do not keep cash under mattresses; they deposit surplus in commercial banks (`bank.py`).
- **Credit Creation & Usury:** Banks lend accumulated capital to other capitalists (for factory expansion) or to desperate workers and indebted peasants (at compound interest).
- **Foreclosure:** When crops fail or factories lay off staff, borrowers cannot service debt. The bank forecloses, seizing collateral (the last ancestral family plots, tools, homes), directly accelerating land concentration.

### 5.4 The Apex: The Sovereign Bond Market (20 / 50 / 100-Turn Instruments)
The sovereign state is bound to capital through the sovereign bond mechanism (`sovereign_bonds.py`):
- **Imperial Financing:** States issue 20, 50, and 100-turn bonds to fund military expeditions, naval expansion, colonial conquest, and infrastructure built for resource extraction.
- **The Coupon Treadmill:** Governments must pay periodic coupon interest every turn to bondholders (the financial oligarchy).
- **Austerity & Repossession:** If the state runs a deficit, bond rating crashes. Foreign and domestic financiers demand structural adjustment: slashing public grain reserves, privatizing municipal water, cutting worker welfare, and directing tax revenue solely to bond debt service.
- **Announced Bond Auctions:** Bond issues are announced 1 turn in advance, allowing allied and rival nations to bid, buy up another nation's sovereign debt, and weaponize financial leverage for diplomatic vassalage.

### 5.5 Global Currency & FX Desks (`forex.py`)
- Exchange rates are anchored by central bank gold/silver reserves and bilateral trade imbalances.
- Dominant imperial currencies (e.g. Pound Sterling, US Dollar) operate as global reserve currencies, enabling imperial powers to import raw resources from the periphery while exporting financial inflation.

---

## 6. The Great Contradiction: Exploding Tech vs. Immiseration

### 6.1 The Innovation Tree: Subsumption of Labor
Technological progress in the game is not a neutral civic tree; it is an instrument of labor discipline and output acceleration:

1. **Agrarian Enclosure & Drainage (Era 1):** Eliminates strip-farming; converts common fields into private sheep pastures and commercial grain estates.
2. **Manufactory & Division of Labor (Era 1–2):** Strips artisans of specialized craft knowledge; decomposes tasks into mind-numbing repetitive motions.
3. **Steam Power & The Mechanical Loom (Era 2):** Decouples production from river geography; forces workers into 24-hour shift cycles governed by clock-time.
4. **Chemical Fertilizers & Smelting (Era 2–3):** Exponentially increases yield while poisoning local aquifers and sickening smelter workers.
5. **Joint-Stock Corporations & Financialization (Era 3):** Shields capital owners behind corporate veil; legal mandate to maximize quarterly shareholder extraction regardless of human or environmental cost.

### 6.2 The Jevons Paradox & Overproduction Crises
- **The Efficiency Trap:** Increasing energy or resource efficiency does not decrease total consumption; it makes extraction cheaper, accelerating the depletion of forests, coal, and ore.
- **Crisis of Realization (Underconsumption):** Because capitalists depress wages to maximize profit, the working masses lack the purchasing power to buy the exploding volume of consumer goods.
- **The Gluts:** Unsold grain rots in warehouses while starving families protest outside; textile stocks pile up while unclothed children freeze in tenements. The market solves this crisis not through redistribution, but through violent price collapses, bankruptcies, factory closures, and imperial wars to force open foreign markets.

---

## 7. Politics: The State, Regimes, and Class Struggle

### 7.1 The State as the Shield of Property
The state is not an impartial referee. Its primary structural role is enforcing property titles and contracts:
- Laws against vagrancy and trespassing force landless peasants into factory workhouses.
- Police and military units suppress strikes, protect scabs, and break up land occupation movements.
- Tax systems disproportionately tax consumption (tariffs, excises on salt, grain, beer) while exempting capital gains and foreign bond holdings.

### 7.2 Regimes and the Democratic Illusion
The player does not play as a single human immortal; they control the state apparatus.

#### Path A: The Bourgeois Republic / Oligarchic Democracy
- **Elections & Campaign Cash:** Candidates with charisma and elite backing receive massive treasury and industrial donations (`campaign_finance`).
- **Gerrymandering & Property Qualifications:** Voting rights can be restricted by property ownership, race/ethnicity, or literacy tests.
- **The Reformist Trap:** Concessions (the 10-hour workday, public hygiene, child labor laws) reduce immediate revolt risks, but reduce profit margins, prompting capital flight and investment strikes.

#### Path B: Authoritarian Oligarchy & Military Dictatorship
- **The Gun-Barrel Exit:** When popular unrest crosses critical thresholds and elections threaten socialist/indigenous victory, the military leadership (`generals`) and financial elites stage a coup (`coup.py`).
- **Purges and Martial Law:** Disbands unions, mass-arrests faction organizers, privatizes remaining state lands, and forcibly suppresses wages.
- **The Fragility of the Sword:** The army requires massive upkeep. Unpaid soldiers mutiny or join the revolutionary mob.

### 7.3 The Escalation Ladder of Popular Resistance
Built on `unrest.py` and `Region.step()`:

```
[Level 0: Quiet Grinding]
  Workers endure exhaustion; alcoholism, suicide, and interpersonal crime rise.
      │
      ▼
[Level 1: Industrial Sabotage & Luddism]
  Machinery smashed in night raids; grain stores burned; clandestine union organizing.
      │
      ▼
[Level 2: The Strike Wave]
  Labor withheld across key sectors (rail, coal, docks); export pipelines freeze.
      │
      ▼
[Level 3: General Strike & Land Occupations]
  Peasants tear down enclosure fences and re-occupy ancestral commons; citywide shutdowns.
      │
      ▼
[Level 4: Armed Insurrection & Barricades]
  Workers seize state armories; pitched street battles against police and private militia.
      │
      ▼
[Level 5: Revolutionary Dual Power / Popular Commune]
  Old regime deposed; abolition of private land titles; restoration of the commons under democratic worker-council control.
```

---

## 8. Geopolitics, Imperialism, and Unequal Exchange

### 8.1 Core vs. Periphery Dynamics
The global map (`sim_world.py`) connects nations through trade routes (`transporter.py`):
- **Core Industrial Nations:** Import raw timber, raw cotton, unprocessed ores, and cheap grain from peripheral and colonized regions; export manufactured goods, machines, and sovereign debt.
- **The Periphery:** Locked into monoculture debt traps. Local food sovereignty is crushed to make way for export crops (sugar, rubber, tea) demanded by foreign credit markets.

### 8.2 The Imperial Sequence
1. **The Merchant Phase:** Unequal trade treaties negotiated through naval presence; cheap manufactured textiles flood indigenous markets, bankrupting traditional village weavers.
2. **The Debt Entrapment Phase:** Peripheral monarchs and leaders are granted high-interest loans (20/50-turn bonds) to buy arms or build luxury palaces.
3. **The Gunboat Enforcement Phase:** When the peripheral government defaults, the imperial fleet blockades ports, seizes customs houses, and assumes direct administrative control over tax collection.
4. **Colonial Annexation & Primitive Accumulation:** Ancestral indigenous lands are declared "crown land" or "waste land" and auctioned off to imperial concession corporations.

---

## 9. Existing Codebase → Structural Mechanics Mapping

The existing architecture directly supports this vision:

| Game Mechanic | Codebase Module | Implementation State & Additions |
|---|---|---|
| **Conserved Value Audit** | `forex.py`, `region.py` (`audit_currency_total`) | Active. Enforces that no money is created or vanished during exploitation, debt payments, or expropriation. |
| **Sovereign Debt & Imperial Leverage** | `sovereign_bonds.py` | Active. Multi-turn bonds (20/50/100 turns), coupon interest payouts, default penalties, and AI bond auctions with 1-turn announcements. |
| **Class Struggle & Unrest Escalation** | `unrest.py` | Active. 5-tier escalation from low-morale drag to strikes, riots, and full regime collapse. |
| **Resource Extraction & Factories** | `buildings.py`, `region.py` | Active. Production buildings, input-output commodity chains, labor demands, and industrial upgrades. |
| **Dynasty & Generational Memory** | `wealth_lineage.py`, `agent.py` | Active. Family trees, heritable wealth, ancestral memory of eviction, starvation, and betrayal. |
| **Global Trade & Geography** | `sim_world.py`, `world_names.py`, `transporter.py` | Active. Fully connected trade graph, real historic capitals and provinces, bilateral transport routes and tariffs. |
| **Common vs. Enclosed Land Status** | `region.py`, `tile.py` | **Target Expansion:** Introduce `land_tenure` (Commons, Leasehold, Enclosed) modifying subsistence food availability and wage dependency. |
| **The Externalities Ledger** | `region.py` | **Target Expansion:** Track accumulated biome pollution, soil fertility decay, and agent health attrition metrics. |

---

## 10. The Player Experience & User Interface

### 10.1 The Dual Face of the Dashboard
The UI contrasts the cold triumphalism of capital with the grim ground-level reality:
- **The "High Minister's View" (Top Bar & Ticker):**
  - Gleaming neoclassical aesthetic: "GDP Growth: +8.4%", "Industrial Output: +14.2%", "Bond Rating: AAA", "Imperial Conquests: 3 Provinces".
- **The "Ground Truth Archive" (The State Ledger & Deep Zoom):**
  - Click on any tile to see:
    - *Common Land Remaining:* 12% (down from 88%).
    - *Average Caloric Intake:* 1,620 kcal (down from 2,300 kcal under customary tenure).
    - *Average Working Hours:* 14.2 hrs/day (up from 6.5 hrs/day).
    - *Child Labor Participation:* 38%.
    - *Top 1% Wealth Share:* 79.4%.
    - *Externalized Ecological Debt:* 42,000 tons of sulfur/effluent; soil exhaustion in 18 turns.

### 10.2 The Audit of Blood and Coin (The Money Trail)
At any point, the player can inspect any fortune, palace, or battleship:
> *"The Royal Dreadnought was financed by 50,000 ducats from the 50-Turn Sovereign War Bond. The interest coupons are serviced by the 12% Salt Excise Tax collected from the Northern Mining District. Over the last 15 turns, 420 miners died of lung rot and 810 children suffered chronic rickets to pay these coupons. The bondholders earned 14,200 ducats in net yield, deposited in the Bank of the Metropolis."*

---

## 11. Victory, Defeat, and Alternative Horizons

The game does not mandate a singular teleology; it challenges the player to navigate the contradictions of history:

1. **The Hegemon of Capital (Imperial Triumph):** You build an unchallengeable global empire, privatize every acre of the planet, command astronomical financial wealth, and suppress all dissent with an iron fist—leaving a scarred, blackened, depleted world teetering on systemic ecological collapse.
2. **The Gilded Collapse (Historical Defeat):** You maximize short-term profits, externalize all costs, ignore soil exhaustion and worker health, until an uncontainable confluence of crop failure, sovereign bond default, and general strike tears your regime to pieces.
3. **The Social Democratic Truce (Reformism):** You manage the contradictions through aggressive progressive taxation, labor laws, public health, and environmental conservation—constantly fighting off capital strikes, elite tax flight, and conservative military coups.
4. **The Reclamation of the Commons (Revolutionary Alternative):** Popular movements overthrow the dictatorship of property, re-institute customary and democratic stewardship over the land, abolish debt peonage, and redirect productive capacity toward human well-being and ecological equilibrium.

---

## 12. Phased Development Roadmap

- **Phase 1: Enclosure & Subsistence Mechanics**
  - Implement `land_tenure` on regions (`COMMONS`, `LEASEHOLD`, `ENCLOSED`).
  - Common lands allow agents to gather subsistence food directly without money.
  - Enclosing land converts commons into private agricultural/resource slots, driving dispossessed agents into the urban wage labor market.
- **Phase 2: Labor Commodification & Alienation**
  - Model wage-labor contracts: hours per shift, workplace safety, and surplus value extraction ($s/v$).
  - Introduce `alienation`, `health_attrition`, and `despair` tracking on agents.
- **Phase 3: The Externalities Engine & Metabolic Rift**
  - Add soil depletion from intensive monoculture farming and pollution from factories/smelters.
  - Model health consequences and fishery/forest depletion.
- **Phase 4: Financial Imperialism & Resistance**
  - Integrate multi-turn sovereign bonds into foreign policy and debt-enforcement wars.
  - Implement anti-enclosure revolts, Luddite sabotage, general strikes, and revolutionary communes.
- **Phase 5: The "Money Trail" Audit UI**
  - Build interactive state archive visualization tracing accumulated wealth directly back to the labor and environmental costs extracted to produce it.