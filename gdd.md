# Call of Capital: Modern Economic Warfare — Game Design Document

**Working Title Candidates (with Strategy & Economic Warfare Twists):**
- **WAR BY OTHER MEANS: Economic Total War** *(Clausewitzian inversion: capital and financial markets as supreme instruments of conquest)*
- **HEARTS OF CAPITAL: Sovereign Debt & The Extractive State** *(Subversion of 'Hearts of Iron'—industrial mobilization directed at extracting living labor rather than frontlines)*
- **TOTAL COMMODITY: The Great Separation** *(Subversion of 'Total War'—every aspect of human life, land, and time subordinated to market discipline)*
- **SHOCK DOCTRINE: Grand Economic Warfare** *(The weaponization of financial crises, sovereign debt traps, and forced privatization)*
- **COMMAND & COMMODIFY** *(Subversion of 'Command & Conquer'—compelling populations into market dependency)*
- **THE ART OF DEBT: Sovereign Warfare** *(Subversion of 'The Art of War'—conquering sovereign nations via 100-turn bonds, central bank reserves, and currency crises)*
- **FINANCIAL BLITZKRIEG: The Enclosure of Nations** *(Modern economic warfare: structural adjustment, capital flight, and resource extraction)*
- **ENCLOSURE: A Grand Strategy of Capital** *(The foundational historical crime: fencing off the commons to force people into wage labor)*
- **MUTUALLY ASSURED ACCUMULATION** *(Cold War doctrine inverted: infinite compound growth colliding with planetary ecological limits)*

**Engine Basis:** SimpleEconSim (`sim_world.py`, `region.py`, `forex.py`, `sovereign_bonds.py`, `unrest.py`, `buildings.py`, `wealth_lineage.py`, `transporter.py`).
Each region is a living simulation of individual human agents who possess cash, debts, skills, kin lineage, memory, and physical needs. Every transfer of money, resource, or labor is strictly conserved down to the penny. The accounting audit is not just an invariant—it is an indictment.

---

## 1. Executive Concept & Philosophical Thesis

### 1.0 First Playable Scenario: Egypt's Grain and Debt Crisis, 1877

The first campaign is grounded in **Khedivate of Egypt under Khedive Ismail Pasha**, during the overlap of a low Nile flood and the country's debt emergency. In 1876, Egypt suspended payments on treasury bonds and established the Caisse de la Dette Publique, whose foreign commissioners directly received revenues assigned to debt service. In 1877, a very low Nile left farmland unirrigated and threatened the *doura* (maize) staple. The scenario brings these documented pressures into one playable crisis in **Cairo**, the **Nile Delta**, and **Upper Egypt**, with **Alexandria** as the export and port connection. It uses a deterministic setup and a 20-turn base horizon that extends for late sovereignty crises.

This is a historically grounded scenario, not a claim that the exact game sequence occurred. The one-release public grain reserve, the first payment deadline on turn 6, and the particular choices and outcomes are game abstractions. Turns compress decision windows; they do not represent a literal bond calendar. The player governs Ismail's administration with the Caisse already in operation and must decide how much grain relief and fiscal autonomy to defend while meeting or renegotiating each scheduled debt instalment.

**Opening situation (turn 1):** Cairo holds 440 public maize units, enough for one release of up to 110 full four-unit meals. One quarter of households begin without food access: their former stocks and most of their purchasing power are held by more affluent private households, so the shock changes distribution without minting or deleting cash or food. The low Nile reduces food yields along the Egyptian corridor through turn 12, most severely in Upper Egypt and the Delta. Egypt has 235 spendable sovereign treasury units against 600 units of Caisse bonds held by Britain and France. A 200-unit instalment first falls due on turn 6, with later windows five turns after each completed payment. Historically, cotton exports and customs receipts were central to Egypt's debt crisis; this first playable slice abstracts that fiscal dependence through treasury, creditor-confidence, and autonomy state rather than adding a cotton commodity. It uses the existing food good for maize and models the effect of retaining food exports on local granaries and creditor confidence. The three political constituencies are large landowners, merchants and exporters, and *fellahin* (rural cultivators). The generated map is schematic rather than a literal outline of Egypt, but its scenario geography follows a real river corridor: Upper Egypt and Cairo lie upstream, the Nile Delta sits on the northern coast where the river splits into two outlets, and Alexandria lies farther west on that coast.

**Core loop:**
1. Read the crisis briefing and choose an immediate response: release public maize reserves, keep more food in domestic supply, or preserve treasury funds for debt service.
2. Choose a fiscal response: reduce local tax rates to ease pressure on cultivators, raise them to protect revenue at a political cost, or preserve the existing rate. At each payment window, pay the instalment, defer once, default, or pay half and conditionally write down the other half in exchange for Caisse oversight. Unpaid principal remains for later windows. Deferral moves the current payment three turns later and adds a 10% surcharge to that instalment and the bond claim; it does not erase the obligation.
3. Watch staple prices, household food access, treasury capacity, creditor confidence, and political support respond over the next few turns. Households eating fewer than four food units count as underfed. Public maize releases reserve a full meal for those reached; they eat it during the next consumption step, so the next turn’s hunger and ending account for the ration exactly once. Local tax rates can be raised or lowered on later turns until they reach the zero or 60% limit; each change still uses the turn’s major decision. Newly available decision groups pause play and explain the event that unlocked them. The Guided bar shows changes since the previous turn and names the measured action or simulation phase responsible. Egyptian district protest pressure feeds the scenario's unrest measure. Separate Britain and France reports show their own protest trend, main grievance, hunger, legitimacy, and treasury position.
4. React to consequences: the Caisse answers Egypt's decisions on the next turn. Routine acknowledgement is reported; demands pause the scenario and offer explicit replies with costs and effects. Default can create a collection levy and a customs claim; an arrears plan creates a new due date. Major domestic choices and creditor replies are tracked separately so a diplomatic answer does not consume the turn's domestic decision. The reusable decision/reaction tree and implementation plan live in `situation_scenario_template.json`.
5. If Cairo contests a customs claim or rejects a revised guarantee, Britain considers naval enforcement. A squadron needs a coastal Alexandria, a funded expedition, manageable unrest at home, and enough force to overmatch the local batteries and any Egyptian garrison. Cairo can spend a major decision and treasury funds to prepare the batteries before the squadron arrives. Egypt may request French mediation, propose a joint guarantee, or seek French opposition to unilateral force. France can endorse, abstain, oppose, mediate, or fund a separate squadron; Britain assesses the offer and its own intervention cost. A French squadron needs supply, and a naval demonstration does not authorize bombardment. The resulting ultimatum lets Cairo settle, concede customs control, disarm, or defend. Defending against a credible squadron brings bombardment and a blockade that closes Alexandria's shared trade routes; continued blockade costs Britain each turn, so holding out can work if the expedition becomes unsustainable. No customs collection starts solely because a claim was asserted.
6. Reach the campaign horizon (normally turn 20) with food access and government capacity maintained, or face default, unrest, a continuing collection levy, invasion, or deeper loss of fiscal control. The outcome is a debrief, not a binary score screen.

**District and nutrition loop:** Clicking an Egyptian tile opens a District decision view with that district’s underfed households, mean calorie deficit, body-fat energy reserve, protest pressure, and tax rate. Cairo may reserve full meals for the worst-fed local households, suspend that district’s taxes, transfer a negotiated settlement directly to poorer households, or disperse protesters where police or a garrison exist. A riot warning focuses the affected tile. Each district intervention uses the same one-major-decision-per-turn budget as national policy. One food unit provides 500 daily-equivalent calories; adults need 2,000. Wealth raises desired consumption smoothly, and surplus calories add to body energy reserves. A shortfall reduces reserves and produces proportional hunger and grievance immediately. Starvation death risk rises continuously as reserves run out, so a well-fed person can endure deprivation longer without being immune to its social effects. Protest, mob, compromise, and takeover chances and mob size now rise on smooth pressure curves; public food-aid coverage, fertility, the chance of changing work, and emergency food borrowing also respond continuously to food stress. The realized riot, birth, job change, or takeover is still discrete. Food and money transfers remain conserved. Physical events such as a riot, death, and a bond payment remain discrete.

The campaign has two linked decision chapters within one campaign run, normally 20 turns: Nile flood and Caisse debt, then the contingent crisis of sovereignty, officers, and intervention. The shared engine supplies trade blockades and army battles; strategic sites, fleets, forts, and occupation institutions are bounded scenario systems. The generated terrain is a schematic Nile corridor with a strategic Tel el Kebir defense point, not a literal historical battlefield or a month-by-month 1876–82 calendar. Historically, the 1882 intervention followed years of fiscal and political conflict; it was not an automatic punishment for one missed remittance.

The 600-unit Caisse claim is an existing pair of zero-coupon sovereign bonds held by Britain and France. The scenario schedules 200-unit service windows, so the sandbox bond market does not automatically pay or default the same claims. Payments reduce principal; a half-payment concession conditionally writes down only that instalment's unpaid half. Later principal remains due. Revisions, concessions, and defaults update both bond records and a readable debt ledger. An accepted customs assignment intercepts up to five units per turn from actual Egyptian tax and customs receipts (25% and 50% of eligible receipts, respectively), and stops when the claim is paid. Rail and port claims are named in the ledger but have no independent receipt source yet.

Egyptian political authority is now tracked separately from aggregate legitimacy. A paid garrison at Alexandria anchors military morale; promotion access, loyalty to the palace, cabinet authority, civilian backing, and nationalist strength respond to fiscal policy, welfare, foreign oversight, and naval coercion. The player can pay officer arrears, open promotions, invite a representative cabinet, or dismiss foreign controllers. Dismissing controllers produces a creditor demand that can weaken Ismail's authority. If authority and foreign control cross the relevant thresholds, the succession can shift to Tawfiq; if the officer-civilian movement gains enough support while palace army loyalty weakens, a constitutional or ‘Urabi-led cabinet can take power. The player remains responsible for Egypt's governing coalition after either transition. These are conditional game outcomes rather than a scripted replay of 1879 or 1881.

The strategic canal map now connects the Mediterranean, Alexandria, Port Said, Ismailia, Tel el Kebir, Cairo, and Upper Egypt as named sites anchored to the generated Nile corridor. Fleet movement consumes coal; canal passage requires transit rights and transfers tolls to Egypt. A supplied British fleet must be present off Alexandria to maintain a blockade. Britain weighs its claim, expedition funding, and domestic protest. France separately weighs its bonds, treasury, protests, canal access, and Egyptian offers before endorsing, abstaining, opposing, mediating, or funding a squadron. Ottoman mediation can delay an ultimatum and succeed only when Egypt can pay and Britain accepts the terms. Cairo may close foreign canal transit at a diplomatic cost.

If Cairo fights the ultimatum, bombardment spends Egyptian battery ammunition, damages the fort and British fleet, injures civilians, and impairs Alexandria's port. A landing warning pauses play before Britain commits troops. Egypt can defend the port, move its garrison to Tel el Kebir west of Ismailia, withdraw to Cairo, or negotiate. The canal approach takes several turns and can fail for lack of access or supply. The shared army battle model decides losses and whether Britain obtains a foothold; naval fire alone does not transfer territorial control.

A British foothold now needs a funded land garrison. Holding Alexandria controls customs; holding Cairo controls the tax administration while Egypt remains formally sovereign. Occupied receipts are taken from actual government income and entered in a conserved ledger, capped at 20 units per turn, with boycott, strikes, and resistance reducing collection. Egyptian decisions can organize noncooperation, accept local collaboration, or conduct armed resistance at a civilian cost. Cairo can offer 30 units for withdrawal; Britain replies the next turn after comparing resistance, collectible receipts, and garrison supply. Cash moves only if Britain accepts, and the unpaid Caisse claim remains. A Cairo assault pauses for a defense choice. Endings distinguish occupation, stalled intervention, nationalist victory, successful repudiation, debt settlement, and government breakdown according to measured territory and institutions.

The second chapter begins when succession, an officer movement, or naval mobilization makes sovereignty the central decision. A briefing modal summarizes the actual ruler, coalition, army loyalty, claim, fleets, canal, and held territory. Guided mode then leads with Egyptian authority, foreign demands, and coastal defense or occupation; it moves relevant decisions to the top without hiding the others. A late transition receives at least eight chapter turns, and a new British foothold receives at least five turns for resistance, collaboration, collection, and negotiation before the ending. The 20-turn horizon remains the base case. The final modal leads with civilian and battlefield injuries and actual occupation receipts and supply costs, while all other social statistics remain available by scrolling.

The seeded [chapter-two path audit](EGYPT_CHAPTER_TWO_AUDIT.md) contrasts occupation, organized resistance and negotiated withdrawal, a rejected premature offer, canal defense, mediation, disarmament, and imposed control. These endings depend on recorded territory, contracts, debt, and withdrawal causes. A nationalist withdrawal can leave the Caisse claim unpaid; military sovereignty and debt settlement are separate facts.

**Strategic loop:** Guided play lets Cairo fund three competing plans: Nile food security, Egyptian control of actual fiscal receipts, and defense of the Alexandria–canal route. Repairs, the Alexandria revenue office, and the supplied Tel el Kebir line pay real local crews and show progress on the map. The office moves a share of actual district receipts to Cairo after lawful creditor claims; the line changes British route costs and battle strength; the Nile repair changes actual harvests, which private holders may still withhold. A standing grain entitlement can take surplus from landowners and well-stocked households and feed underfed households, paying carriers from the treasury while reducing legitimacy and increasing unrest. It can run out of grain or funds. Cairo may once call up to 80 units of already-collected district reserves to meet a national bill, leaving local governments at least 20 each and raising local unrest. The debrief keeps cumulative hunger and calorie deficit visible even if late relief improves the final hunger count. Britain and France remain separate actors with measured domestic protest; the scenario scales their local grievance growth to represent administrative depth outside the five playable Egyptian districts. The [implementation plan](EGYPT_STRATEGIC_LOOP_PLAN.md) and [baseline](EGYPT_STRATEGIC_BASELINE.md) record the work and its initial bottlenecks. Project costs, the 0.20 foreign grievance scale, and the 20-turn calendar are gameplay abstractions, not documented 1877 quantities.

The campaign defines ten original endings and five additional endings. The additional endings are fiscal hardship after debt resolution, coerced disarmament with an outstanding claim, an unresolved claim at the campaign horizon, joint British-French collection, and a French-brokered paid settlement. Continued requisitions after a tax increase can raise receipts but accumulate enough political damage to break the government. A live customs assignment produces a financial-control ending while the claim remains unpaid. French endorsement alone remains a diplomatic fact in the debrief; joint control requires a signed agreement and actual collection paid to both creditors. Full-campaign audits must verify reachability from player decisions across more than one map and fiscal condition; the 20% final hunger threshold remains unchanged. The debrief separately reports cumulative household hunger so one late ration does not erase earlier suffering.

Guided mode keeps three headline pressures and shows the canal sites, fleet location, and control changes on the map. The opening briefing pauses play in a modal. The ending opens a scrollable modal with cumulative household hunger, calorie deficit and surplus, mean body energy reserves, peak shortage alongside private food holdings, cash concentration, taxes collected, actual creditor transfers, civilian injuries, and the political debrief. The national bar shows current spendable treasury, current-turn tax receipts, total outstanding Caisse principal, and deltas; the tax tooltip divides receipts by district and government tier. Its decision list scrolls in the panel when needed; each visible choice retains a consequence tooltip. Analysis draws its own inspector and tooltips above the map without hidden Guided-panel hover targets. The campaign log separates documented historical context, tuned game quantities, and contingent play outcomes. The Advanced composition remains available over the same scenario state.

**Political economy mechanics in the current campaign:**
1. Named landowners or traders buy maize from actual cultivator inventories after harvest and before market trading, up to 60 units per district warehouse. They offer only a price-sensitive share to the food auction, comparing local prices with a reservation price and neighboring export prices. Holdings rise in response to household deficit and fall when owners run out of cash or local prices become attractive. Guided mode shows the private stock next to public reserves and hunger. Cairo can buy held grain at a premium for later public relief, requisition it with a legitimacy and unrest cost, or open direct private sales to households who can afford the district price. A purchase transfers cash to the owner; a requisition does not. Private buying gives producers a current sale, while withdrawing supply can raise later market prices through the existing auction.
2. Cultivators with plot access owe a small scenario cadastral assessment tied continuously to the local tax rate. One quarter of actual cash receipts goes to Cairo and three quarters to the district; both appear in tax records. Unpaid balances age into a smooth foreclosure risk; foreclosure removes the cultivator's use right and can auction it to a named buyer. Auction proceeds pay the arrears first and any remainder goes to the cultivator. The existing landlord keeps title to the larger shared plot. A dispossessed cultivator loses foraging rights and secure field output, faces pressure to take wage work, and may move to a less hungry or better employed Egyptian district. The ledger records the cultivator, title holder, buyer, arrears before and after sale, auction price, and destination. Local arrears forgiveness cancels balances and lowers future assessments; general or district tax cuts lower subsequent assessments.
3. Household calorie gaps and arrears generate petitions; a smooth pressure response recruits some petitioners to withhold work. Existing production rules reduce output when those agents strike. Households can redistribute their own food through mutual aid. Cairo can support that exchange, broker a settlement funded by owners that raises offered wages, or use local forces to break a strike and incur recorded injury memories and political costs. The Guided district view shows petitions and offers all local choices with tooltips.
4. The Caisse report lists actual assigned receipts by source and creditor and estimates the cash required to feed hungry households beyond public stores. It identifies the part of a relief purchasing shortfall that coincides with diverted receipts; this is an accounting comparison, not a claim that every transfer would otherwise have funded relief. Cairo may offer a lower per-turn collection cap for eight additional turns of inspection beyond the campaign horizon. Creditors answer on the next turn based on confidence; acceptance changes the cap and reduces fiscal autonomy while leaving the principal outstanding.

The seeded path comparison and balance decisions are recorded in `EGYPT_POLITICAL_ECONOMY_AUDIT.md`. The ending debrief now counts land loss, migration, grain purchased or seized, mutual-aid food, strikebreaking injuries, and assigned receipts against relief shortfalls. These are tracked through real household, land, goods, and cash state. Remaining depth work includes more varied owner strategies, explicit wage-work placement after eviction, and a fully modeled post-horizon inspection period.

**Outcome bands:** Debt resolution may end in relief and payment, creditor settlement, Ottoman or French mediated compromise, fiscal hardship after settlement, unilateral or joint creditor control, coerced disarmament, unresolved crisis, or successful repudiation. Escalation may end in stalled intervention, nationalist victory, or British occupation. Domestic extraction may end in coercive extraction or government breakdown. The ending is a debrief category determined by debt status, signed obligations, actual receipts, territorial control, and political and welfare measures; it is not a moral judgment.

For the ordinary first playable implementation, “protected food access” means no more than 20% of households are hungry at the ending; breakdown triggers if legitimacy falls to 10% or average regional unrest reaches 0.85. Territorial control, actual breakdown, enforceable creditor control, and accepted treaties take precedence in the ending classifier. Surviving high-tax extraction is then classified as coercive extraction; settled debt with food above the configured target is fiscal hardship. These are tuning thresholds, not historical measures. Scenario variants can use a stricter food-access target.

The opening should present **one recommended action and at most three live pressures** at a time: household access to maize, the next debt-service window, and political support. A short causal explanation connects each pressure to a choice (for example, “Keeping more food at home improves local reserves, while lower export receipts weaken creditor confidence”). Deep agent, class, ecology, and ledger detail remains available by inspection. The scenario is a playable slice and tutorial; later sandbox play exposes the wider world and more systems.

**Scenario success criteria:** Players can explain how the low Nile's harvest loss, public food supply, and debt control interact; identify who benefits from the current policy; make at least two consequential decisions; and understand how those choices changed the ending. The scenario supports distinct approaches—protect household access, preserve creditor confidence, or raise revenue at a political cost—without requiring the player to monitor every simulation variable. Scenario content must be authored as data/configuration (map setup, briefing, pressure definitions, action choices, and outcome predicates) rather than embedded in rendering code, so additional scenarios can reuse the same presentation components.

### 1.0.1 Interface Configurations

The UI has two swappable configurations backed by reusable components:

- **Guided (default for Egypt's Grain and Debt Crisis):** objective and turn horizon, crisis briefing, up to three priority pressures, recommended action, focused map overlays, and a small number of contextual decisions. Diagnostic charts, all system drawers, and detailed accounting are available from an explicit “Analysis” view.
- **Advanced (existing interface):** retains the full current map controls, system drawers, charts, comparison tools, and diagnostic panels for players familiar with grand strategy and simulation games.

`ui_mode` is an application/system preference (`guided` or `advanced`), independent of the active scenario and map topology. Both configurations use the same simulation state, actions, and domain components; presentation modules decide which components are prominent, collapsed, or available through analysis. Switching modes must not reset the world or discard user state. Persist the preference in application settings, with an environment/command-line override for development and automation.

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

### 1.3 The Twin Core Imperatives: Absolute Accounting & Organic Emergence
Along with accounting for every penny in the economy down to the cent, the supreme technical and design goal of this game is the simulation of underlying mechanisms such that events occur organically and emergently rather than via scripted event trees or arbitrary countdown timers.
1. **No Scripted Crises or Arbitrary Timers:** Famines (e.g. Turnip Winter), urban epidemics (The Great Stink), debt crises, and insurrections are never arbitrary timers or pre-scripted narrative flags. They emerge organically from the thermodynamic realities of the world: nutrient depletion in the soil, microbial concentration in the river, insolvent balance sheets, and withheld calories.
2. **Violence as the Foundation of Political and Economic Action:** Political and economic actions are never self-enforcing moral abstractions. They are always and everywhere enforced by violence or the credible threat of violence. Property rights exist only because bailiffs and constables shoot trespassers; debt collection across borders occurs only because imperial gunboats can pulverize coastal forts or occupy the debtor's capital. When the balance of coercive power collapses, contracts dissolve into revolution or debt repudiation.

---

### 1.4 The Player's Strategic Conflict: Livelihoods, Expansion, and Rival Power

The player trades expansion in the exploitation of labor and territory against the livelihoods of citizens while neighboring nations compete economically and militarily. Protecting access to land or improving work terms affects the cost and availability of labor; industrial output affects paid sales and real fiscal receipts; military power requires people, pay, food, and reachable supply. Rivals face the same constraints and may invest, negotiate, defend, or exploit an opportunity to expand. Private profits support national power only through actual investment, taxation, or other transfers.

Territorial expansion can secure productive land, resources, markets, and revenue, while adding residents, recurrent military costs, disrupted livelihoods, and political resistance. A domestic settlement must be sustainable under external competition. The player can pursue conquest and extraction, productive compromise, defense and diplomacy, or another feasible combination; consequences follow the underlying flows rather than a guaranteed punishment for any one policy. Evaluate relative economic and military position alongside household security, effective rights, sovereignty, and future commitments.

The next labor-system playable slice is [Labor, Territory, and Rivalry](planning/plunder_of_labor_first_slice.md): a separate, bounded two-nation scenario with one domestic labor pressure mechanism, a productive alternative, paid export competition, and a contestable inhabited border. Its implementation order and acceptance gates specialize the [labor AI and UI plan](planning/plunder_of_labor_ai_and_ui_plan.md). Egypt retains its existing introductory campaign and outcome rules.

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

### Pillar 6: The Monopoly of Violence (The Iron Fist Behind Property & Contracts)
Law, debt contracts, border tariffs, and property titles do not enforce themselves. Every economic decree is backed by the state's organized violence or the credible threat of armed force. Contracts hold only so long as the enforcer possesses the military or police capacity to inflict catastrophic costs upon the defiant. When coercive power falters—or when enforcement costs exceed the prize—contracts collapse, debts are repudiated, and enclosure fences are torn down.

### Pillar 7: Emergent Mechanics Over Scripted Story Trees
The simulation models deep causal roots, not narrative triggers. If an indebted nation defaults, an imperial power cannot simply press a button or wait for a countdown timer to take over the debtor's state. The escalation occurs only because the creditor calculates the balance of armed forces, naval projection logistics, and occupation costs against the debtor's military defense and popular resistance. Every macroscopic phenomenon is an emergent equilibrium of underlying mechanical pressures.

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

### 5.0 Commodity Scope: Few Goods, Distinct Decisions

The game does not need a long commodity catalog for its own sake. More goods are useful only when they create a strategic bottleneck, a meaningful substitution, or a legible distributional conflict. The opening scenario should foreground three commodity groups:

- **Staple food:** survival, household security, reserve policy, and export-versus-domestic allocation.
- **Industrial inputs:** timber and transport capacity, abstracted together in the opening interface as the cost of expanding production and moving goods.
- **Manufactures:** cloth and tools/furniture as visible outputs of industrialization, useful for trade and revenue but not substitutes for food.

Existing goods include food, wood, furniture, transport, wool, cloth, and nitrates. Keep these in the simulation where their production chains already matter, but do not require players to manage each as an equally important market. Wool and cloth can support a simple pastoral-to-manufacturing chain; nitrates can remain a later ecological/industrial input. Treat government as an institution or service, not as a tradable commodity in player-facing terminology.

Before adding a commodity, require a clear answer to: who produces it, who needs it, what player decision changes its flow, and what visible consequence follows if it is scarce or abundant? If those answers are weak, represent it as an input, capacity, or aggregate rather than a new player-facing good. Prefer commodity groups and contextual detail panels over adding more top-level meters.

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

### 8.3 The Coercion Calculus: Sovereign Debt Enforcement, Relative Might, and Credible Takeover

A core trap of inferior strategy games is reducing imperialism and debt enforcement to arbitrary countdown timers (e.g. "if the debtor is unable to pay for 3 turns, or clearance is under 15%, an imperial receivership is automatically declared"). In this simulation, such mechanics are strictly emergent and conditional on the **monopoly and balance of violence**.

#### 1. The Coercive Prerequisite for Fiscal Escalation
An imperial creditor cannot simply decree a *Caisse de la Dette Publique* or seize domestic railway tolls, canal revenues, granary buffers, or mining royalties by administrative fiat. Escalation to direct fiscal and asset takeover is **only possible if the creditor possesses the military force or a credible threat of military force capable of invading and taking over the debtor country by force**.
- Without credible military power backing the creditor, the debtor sovereign will simply ignore the demand, tear up the bond contracts, or repudiate the debt with zero consequences.
- If the creditor attempts an administrative receivership without garrison force, local officials and armed populations will physically expel foreign bailiffs.

#### 2. What "Credible Threat of Armed Takeover" Means in Concrete Simulation Terms
Whether a threat of takeover is credible is evaluated through a continuous thermodynamic calculus between creditor and debtor:
- **Relative Military Might & Mobilization Ratio:** The ratio of the creditor's deployed and deployable forces (standing army divisions, naval gunboats, mobilized constabulary, hired mercenary bailiffs) compared to the debtor's territorial defense forces (standing army, fortified bastions, regional garrisons, armed citizen militias).
- **Power Projection & Logistics Costs:** Violence is not free. Moving an expeditionary naval fleet or army corps across sea corridors or borders drains substantial sovereign cash every turn (fuel, ammunition, rations, transport upkeep). If the expeditionary cost to conquer the debtor exceeds the present value of the defaulted debt, the creditor's threat is an empty bluff.
- **Asymmetric Deterrence & Urabi Insurgency Risk:** An armed takeover is not a clean spreadsheet operation; it unleashes intense popular resistance. When foreign powers attempt to seize domestic revenues or food supplies, the debtor population mobilizes along the resistance ladder (Urabi-style nationalist revolts, peasant barricades, general strikes, anti-imperial mutinies). If the debtor has high population density, armed militancy, or defensible terrain, the anticipated pacification cost turns an invasion into an imperial quagmire.
- **Creditor Domestic Constraints:** A creditor government facing internal unrest, high domestic debt, or war with peer imperial rivals cannot credibly commit forces abroad without risking revolution or financial panic at home.

#### 3. Dynamically Negotiated Terms (The Bargaining Frontier)
All numbers governing debt enforcement—the turn horizons before escalation, clearance thresholds, haircut percentages (30% to 60%), Brady bond maturities, and concession scopes—are **not hardcoded constants**. They are emergent bargaining positions determined dynamically by relative military might and the credibility of takeover:
- **Overwhelming Imperial Superiority (Credible Total Takeover):** When the creditor commands overwhelming naval and ground superiority within striking distance, the creditor dictates draconian terms: maximum revenue diversion (65%+), direct seizure of transit tolls and granaries (*Caisse de la Dette*), or perpetual unequal treaties.
- **Strategic Parity or High Asymmetric Deterrence (The Credible Resistance):** When the debtor possesses significant defense forces, difficult terrain, or a highly militant population capable of bloody insurgency, the creditor cannot credibly invade. The creditor is forced to the negotiating table, accepting deep principal haircuts (e.g. 50–60% Brady Bond restructuring) and forgiving penalties to salvage whatever pennies can be recovered peacefully.
- **Creditor Impotence (The Hollow Bluff):** When the creditor lacks power projection or faces internal crisis, the debtor repudiates foreign bonds completely, expels foreign bankers, and abolishes imperial concessions without firing a shot.

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

### 10.0 Decision-First Presentation

The opening scenario should not ask the player to treat every measured quantity as a control variable. The default view leads with a concise crisis briefing, the player's current objective, up to three pressures that threaten it, and the consequential actions available now. Each pressure should show direction, cause, affected groups, and one or more response options. Detailed values (alienation, health attrition, separate pollution channels, faction grievances, individual balance sheets, and similar measures) are supporting evidence shown when the player inspects a place, group, firm, or policy.

Use a small number of readable headline indicators—household security, state capacity, economic power, social stability, and ecological viability—only where each one helps the player choose. Avoid duplicating the same underlying condition across multiple always-visible meters. The UI should explain causal relationships in plain language and reveal specific metrics on demand. The player should usually be deciding what to do about a pressure, rather than deciding which of dozens of indicators to watch.

### 10.0.1 Modular UI and System Preference

Keep the existing full interface as the **Advanced** configuration. Add a separate **Guided** composition for Egypt's Grain and Debt Crisis using reusable UI components rather than deleting, duplicating, or simplifying the underlying simulation panels. The configuration is selected in System/Settings and stored as `ui_mode`; it is not tied to map topology, save data, or difficulty. A developer may override it with `COC_UI_MODE=guided|advanced` (or the equivalent CLI option).

UI composition is a thin layer over shared components: scenario briefing, objective/turn tracker, priority-pressure cards, contextual action chooser, analysis drawer, map overlays, and existing detail panels. Guided mode presents its scenario components first and groups specialist panels under **Analysis**. Advanced mode keeps the current navigation and panel layout. Both modes must expose the same legal actions and simulation detail, preserve selection and turn state when switched, and remain compatible with mouse, keyboard, and save/load. Scenario-specific content belongs in scenario data; reusable rendering and interaction logic belongs in UI modules.

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

Egypt's Grain and Debt Crisis is a bounded introductory scenario with its own turn-20 outcome bands; it does not replace the long-form sandbox horizons above. Its result should summarize food access, debt outcome, regime stability, and fiscal autonomy, with a short causal account of the player's pivotal choices.

---

## 12. Phased Development Roadmap

- **Phase 0: Focused Playable Slice — Egypt's Grain and Debt Crisis (priority)**
  - Create a deterministic Egypt 1877 scenario with fixed turn-1 conditions, an abstracted turn-6 debt-service window, and a turn-20 horizon. Scenario setup, pressures, actions, and outcome predicates are data-driven; document which values compress or fictionalize the historical timeline.
  - Define the opening briefing, up to three priority pressures, contextual decisions, and a debrief that traces pivotal actions to consequences.
  - Build Guided UI components as a modular composition; retain current UI as Advanced. Add a System/Settings `ui_mode` preference and development override. Switching mode must preserve simulation state.
  - Use existing economy, enclosure, unrest, and bond mechanics where they produce understandable choices; defer systems that do not support this loop.
  - Tune commodity presentation around staple food, industrial inputs, and manufactures. Add no new commodity until it creates a distinct decision and consequence.
  - Review readability with new players: can they explain the crisis, make a meaningful choice, and understand the result without interpreting the full dashboard?

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
- **Phase 4: Sovereign Debt, Financial Imperialism & Popular Resistance**
  - Integrate multi-turn sovereign bonds (20/50/100 turns) into foreign policy, domestic bank capitalization, and debt-enforcement crises.
  - Implement *Caisse de la Dette Publique* and receivership escalation governed strictly by **relative military might and the credible threat of armed takeover** rather than arbitrary timers.
  - Model asset seizures: tile transit tolls (rail/canals), granary buffer food reserves, and mining royalties under foreign receivership.
  - Model domestic banking contagion (*Corralito* freezes, commercial credit halt, deflationary price collapse, panic bank runs).
  - Implement emergent, dynamically negotiated debt restructuring (Brady Bonds, principal haircuts, unequal trade treaties).
  - Implement the popular resistance ladder: anti-enclosure fence-leveling, Luddite machine sabotage, general strikes, armed Urabi-style anti-imperial insurgencies, and revolutionary communes.
- **Phase 5: The "Money Trail" Audit UI**
  - Build interactive state archive visualization tracing accumulated wealth directly back to the labor and environmental costs extracted to produce it.

---

## 13. Genre Positioning & Comparisons to Strategy Classics

This game occupies a distinct, disruptive position within the grand strategy, 4X, and political economy genres. It borrows structural systems from classic titles while radically subverting their core ideological assumptions.

### 13.1 Comparison with Major Strategy Benchmarks

#### 1. Victoria 3 & Victoria 2 (Paradox Interactive)
- **Shared DNA:** Pop-driven demographics (Pops), multi-step production pipelines, domestic and international market access, interest groups (Landowners, Industrialists, Trade Unions), and legislative reforms.
- **The Twist / Subversion:**
  - *Subverting the Liberal Growth Fantasy:* In *Victoria 3*, Standard of Living (SoL) rises almost monotonically with GDP; industrialization is depicted as an engine that inevitably raises human welfare. In our game, industrialization triggers the **Immiseration Paradox**: aggregate output explodes, yet workers are more exhausted, alienated, biologically depleted, and indebted as costs are offloaded onto their bodies.
  - *Conserved Money vs. Minting Magic:* *Victoria* spawns money via arbitrary "minting" formulas and soft debt pools. Our simulation runs on an ironclad **conserved-money invariant**—every dollar hoarded by an oligarch is a dollar removed from the circulation of wages.
  - *Primitive Accumulation:* Shifting away from customary land in *Victoria* is a sterile legislative vote; in our game, **enclosure is an active, coercive, and violent dispossession** of living human communities.

#### 2. Civilization VI & Old World (Firaxis / Mohawk Games)
- **Shared DNA:** 2D tile-based territory, regional biomes, resource deposits, borders, infrastructure, and national treasuries.
- **The Twist / Subversion:**
  - *The Myth of Terra Nullius:* *Civilization* begins with a settler stepping onto an "empty" wilderness waiting for a flag. In our game, **every tile begins fully inhabited** by indigenous peoples and customary peasant communes in ecological and reciprocal balance. Territorial expansion is never "settling the empty wild"—it is always **expropriation, unequal treaty, or military eviction**.
  - *Bottom-Up Class Resistance:* In *Civ*, rulers click a button and workers instantly erect wonders. In our game, workers hold strikes, sabotage machinery, and mount armed insurrections when pushed past their biological limits.

#### 3. Frostpunk (11 bit studios)
- **Shared DNA:** The visceral, moral weight of labor exploitation: extended 14-hour shifts, child labor, perilous mine shafts, bodily attrition, and escalating popular discontent.
- **The Twist / Subversion:**
  - In *Frostpunk*, labor brutality is rationalized by an external, existential crisis (apocalyptic winter). In our game, the brutality is **internally generated by the market mechanism itself**: capital demands 16-hour shifts and child labor not to survive an ice age, but to out-compete rivals, service 50-turn bond coupons, and maximize quarterly surplus value.

#### 4. Suzerain (Torpor Games)
- **Shared DNA:** Political-economic tightropes: balancing budgets against oligarchs and socialist unions, national debt rating pressures, and the ever-present threat of a military coup.
- **The Twist / Subversion:**
  - *Suzerain* relies on narrative decision trees with scripted event flags. Our game achieves these same political crises organically through a **continuous, bottom-up agent-based economic and financial simulation**.

#### 5. Hearts of Iron IV (Paradox Interactive) & Modern Economic Warfare
- **Shared DNA:** Grand wartime mobilization, resource bottlenecks, and the geopolitical struggle for hegemony.
- **The Twist / Subversion:**
  - While *Hearts of Iron* simulates total military war on the battlefield, our game simulates **Economic Total War**: weaponizing sovereign bond markets (20/50/100-turn auctions), orchestrating currency runs through central bank FX desks, foreclosing on sovereign collateral, and extracting raw resources from indebted vassals without firing a shot.

---

### 13.2 Structural Comparison Matrix

| System Dimension | Traditional 4X (*Civilization*, *Old World*) | Paradox Grand Strategy (*Victoria 3*) | **WAR BY OTHER MEANS / ENCLOSURE** |
|---|---|---|---|
| **World Map at Start** | Empty wilderness to claim | Pre-set nations, passive subsistence | **Fully inhabited customary commons & reciprocity** |
| **Growth Arc** | Infinite upward progress | Industrialization raises living standards | **Immiseration paradox: tech explodes, human life degrades** |
| **Money Simulation** | Abstract treasury counter | Floating currency with minting magic | **Strictly conserved-money ledger audit down to the cent** |
| **Environmental Cost** | Static hex yields | Infinite resource exploitation | **Metabolic rift: soil exhaustion, river poisoning, collapse** |
| **Sovereign Finance** | Simple loans / flat interest | National debt pool | **20/50/100-turn bonds, foreign auctions, debt vassalage** |
| **The Working Class** | Passive production multiplier | Demographic Pops with SoL wants | **Alienated living labor fighting on an escalation ladder** |
| **Warfare Doctrine** | Military units clashing on tiles | Frontlines & colonial expeditions | **Economic warfare: debt traps, enclosure, monetary embargoes** |
