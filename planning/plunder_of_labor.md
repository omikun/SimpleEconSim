# Plunder of Labor: from subsistence to controlled labor

## Purpose

Model how employers and states turn people who can live partly outside the cash economy into reliable, cheap, intensive labor. The player should see **who loses a livelihood, who gains control, where the value goes, and what people do in response**. Losing a plot must not automatically make someone a factory worker: the same pressure can produce seasonal wage work, tenancy, sharecropping, migration, informal trade, debt bondage, workhouse confinement, or resistance.

This is a design plan, not a claim that every place followed the same path. The strongest historical anchor is Sven **Beckert's** *Empire of Cotton*: cotton production linked land seizure, slavery, credit, imperial power, peasant cultivation, and factory wage labor. Beckert's account of the post emancipation cotton system stresses that capitalists needed a dependable supply of **labor**, not merely suitable land. Colonial and post emancipation systems used different combinations of coercion rather than one universal transition to wages. [Beckert, Harvard](https://www.wcfia.harvard.edu/publications/empire-cotton-0); [Beckert, *Emancipation and Empire*](https://dash.harvard.edu/bitstream/handle/1/3207344/Beckert_EmancipationEmpire.pdf); [National Archives on postwar labor arrangements](https://www.archives.gov/publications/prologue/1997/summer/slave-emancipation).

### Design rule

People allocate time among own cultivation, commons use, household craft, care, mutual aid, wage work, and rest. A household with secure access to land and shared resources can reject a bad wage. A wage job may still attract them if its **real, reliable benefit** exceeds what they give up. Coercion works by shrinking alternatives, increasing cash obligations, restricting exit, or applying direct force. Model these as distinct changes, never as an unexplained `wage_dependency` bonus.

## What already exists

The main simulation has `land_tenure.py` parcel tenure and a derived commons access share; `enclosure.py` charters, survey fees, debt deadlines, eviction memory, and a force check; `land_rent.py` rent; `region_labor.py` wage bids and a reservation wage; `economy/labor_mobility.py` an emergency route into vacancies; `labor_contract.py` hours and surplus accounting; `region_finance.py` scrip and company store debt; `workhouse.py` vagrancy arrests; `labor_politics.py` wage caps and workday law; and resistance/unrest systems. The transformation graph and elite planner already offer enclosure, wage cap, vagrancy, conquest, and captive labor actions. The [existing capitalism roadmap](capitalism_simulation_limitations_and_roadmap.md) marks these as implemented.

The smaller `commonweal/` simulation is a useful comparison: household work stops around a food target; harvest shocks, borrowing, foreclosure, cash taxes, and employers' competition ratchet create landlessness and wage seeking. Its own README says this is a small valley experiment, separate from the main hex simulation. This plan targets the main simulation and can later inform a smaller Commonweal policy experiment; do not silently couple their models.

**Integration gaps to address first:** `economy/labor_mobility.py` can attach any unemployed person to the highest wage vacancy before `region_labor.py` evaluates their reservation wage. The workhouse currently arrests eligible unemployed people automatically if the building exists, rather than following a law, enforcement budget, and hearing outcome. A plot's aggregate commons fraction does not tell us which households actually retain access. `workhouse.py` credits compulsory labor revenue directly to the treasury and purchases gruel without a corresponding seller/food transfer in one path; that needs a conservation audit before expanding it.

## Core simulation: the household choice each turn

Track **real livelihood options**, not a single free/forced binary:

| State | Meaning | Needed data |
| --- | --- | --- |
| Subsistence access | Food, fuel, grazing, gleaning, fishing, water, and household plots actually available to this household | Rights by household and parcel/resource; local yield and travel time |
| Cash obligations | Rent, tax, debt service, fees, and essential market purchases due this turn | Creditor, due date, amount, legal priority |
| Labor offer | Real wage after food prices, deductions, commute, injury risk, and unpaid care | Employer, hours, location, pay form, reliability |
| Exit power | Ability to change jobs, move, own/lease land, use commons, or contest a debt | Law, papers, travel cost, local force, allies |
| Labor condition | Hours, pace, nutrition, injury, fatigue, skills, and bargaining strength | Person and workplace records |

At the beginning of each turn, each household calculates its food and cash gaps **after** available own production and mutual aid. It compares feasible paths: farm/forage, sell crops or craft goods, take seasonal or regular wage work, rent/sharecrop, borrow, migrate, seek relief, or resist. The comparison uses expected food security, future debt, time, and risk, not cash wage alone. Rights and law determine which paths are feasible; coercion changes those constraints. A parent with dependents or a scarce skill may have a different reservation wage from another worker. Employers hire only if expected sale revenue covers all labor, inputs, security, and finance costs. Hence some dispossessed people remain unemployed even when desperate.

The commodity chain should settle at every handoff: cultivator or worker output → local buyer → transporter/merchant → mill → final buyer. A merchant's gain from a lower farm gate price is matched by a lower producer receipt; a factory owner's gain from lower wages is matched by lower worker income. Taxes, interest, store markups, guard wages, and transport fees have named recipients. Track profit **after** these costs and after any inventory loss, so a cheap labor policy can lose money when it disrupts production or demand.

Keep **tenancy/sharecropping** distinct from wage labor. A cultivator may control daily work while surrendering rent or a crop share; creditors can still control inputs, buyer, and crop choice. This intermediary outcome is essential to the cotton story and should not be mislabeled as a payroll job. [National Archives](https://www.archives.gov/publications/prologue/1997/summer/slave-emancipation); [National Park Service sharecropping case](https://home.nps.gov/teachers/classrooms/145shields.htm).

## Mechanism catalog

Each row is an optional policy or tactic with a distinct causal path. **Private actors can petition, finance, collude, hire, or act illegally.** They cannot instantaneously change public law; state authorization, capacity, and enforcement determine whether a law takes effect. The alternatives column is just as important as the pressure column.

### A. Remove independent livelihood

| Mechanism | Initiator and prerequisite | Immediate change | Response and cost |
| --- | --- | --- | --- |
| Enclosure and legal title conversion | Owners petition; state surveys and adjudicates | Common use rights become exclusive parcels; some holders receive land, others lose access | Claims, compensation fights, fence removal, migration; survey and policing cost |
| Individual title and alienable collateral | State registry, lenders, land buyers | Communal/customary claims become saleable and foreclosable individual titles | Households may sell voluntarily, litigate, pool titles, or lose land after shocks |
| Rent conversion | Landlord with enforceable lease | In kind/customary dues become cash rent with deadlines | Tenants sell produce, seek wages, negotiate, move, or default |
| Restrictions on gathering | State forest/fish/game authority or titled owner | Gleaning, hunting, fishing, fuelwood, grazing, and water become licensed, fined, or prohibited | Illegal gathering, courts, smuggling, or flight; patrol cost |
| Irrigation, drainage, or water control | Estate, canal company, or state with upstream control | Small plots lose water or face new fees while export plots gain priority | Water petitions, local engineering, sabotage, crop switching |
| Crop and food displacement | Estate owner, concession, or export policy | Food acreage becomes cotton/sugar/pasture; local food supply and fallback employment change | Crop price boom can help some growers; food price reversal and soil loss can trap others |
| Destruction and eviction | Landlord militia, army, or illegal private force | Burned homes/crops or armed clearance remove actual subsistence stock | High casualties, flight, legitimacy loss, rebuilding cost, organized resistance |
| Conquest and reservation of land | State/chartered company with military reach | Indigenous communities lose territory and legal standing | Supply and garrison expense, insurgency, international conflict |

English enclosure reorganized collective rights through surveys and claims rather than simply flipping a terrain flag; the division of rights and eligibility matters. [Historical study of enclosure acts](https://tile.loc.gov/storage-services/master/gdc/gdcebookspublic/20/08/61/24/17/2008612417/2008612417.pdf). The armed conquest and slavery axis comes directly from Beckert's cotton history. [Harvard](https://studyofcapitalism.harvard.edu/publications/empire-cotton-global-history).

### B. Create a need for money or a creditor

| Mechanism | Initiator and prerequisite | Immediate change | Response and cost |
| --- | --- | --- | --- |
| Cash only poll, hut, or land tax | State with tax collectors | Household must earn currency even if food secure | Crop sales, wage work, migration, evasion; collection cost and revolt risk |
| Registration/survey/license fees | State or licensed surveyor | Upfront bill for title, residence, trade, or tools | Disputes and arrears; can dispossess households despite sufficient food |
| Advance against harvest | Merchant/lender with scarce seasonal liquidity | Food, seed, or cash now for future crop/labor claim | May smooth shocks; crop failure rolls debt forward |
| Crop lien and tied sale | Merchant, landlord, or bank with enforceable lien | Harvest pledged to a creditor; restricted buyer and net price | Grower may seek cooperative buyers, contest accounts, or switch crop |
| Company housing/store/scrip | Employer controls local food and housing | Nominal wage returns through marked up essentials, deductions, and debt | Exit possible if outside housing/shops and transport exist |
| Monopoly procurement/transport | Merchant cartel or chartered company | Farm gate price falls relative to export price; cultivator must grow more to meet cash dues | Smuggling, cooperatives, alternative routes; cartel enforcement cost |
| Essential goods made purchasable only | Owner/state restricts home craft, seed saving, milling, or access to water | Household must buy goods previously produced or shared | Local substitutes, barter, political challenge |
| Relief conditional on work | State/parish with funded relief or stores | Food assistance requires a work test, settlement papers, or assigned labor | People may comply, rely on mutual aid, migrate, or contest eligibility |

Cash taxes and land expropriation were explicitly connected to wage labor recruitment in some colonial settings, but effects varied by local land and labor regimes. [Research on colonial Mozambique](https://www.cambridge.org/core/journals/international-review-of-social-history/article/colonial-state-formation-without-integration-tax-capacity-and-labour-regimes-in-portuguese-mozambique-1890s1970s/D10934ACA671BFEC0E15240A728A6401). Debt tied to recruitment fees, wage deductions, and control of documents remains a recognized coercion pathway. [ILO](https://www.ilo.org/resource/statement/preventing-and-responding-abusive-and-fraudulent-labour-recruitment-call-0).

### C. Restrict the ability to refuse, leave, or bargain

| Mechanism | Initiator and prerequisite | Immediate change | Response and cost |
| --- | --- | --- | --- |
| Debt secured by service | Creditor and enforcing court/force | Debt balance and exit restriction tied to an employer | Repayment, flight, court defense, collective debt refusal |
| Quit penalty or contract enforcement | State law after employer petition | Leaving before term costs withheld wages, fine, arrest, or transport expense | Absconding, strike, employer switching if exceptions exist |
| Vagrancy/pass/settlement rules | State police and local courts | Unemployed or mobile people face checks, fines, workhouse or assigned work | Hiding, migration through informal routes, civil rights challenge |
| No poaching and employer collusion | Employer group with market concentration | Fewer competing bids; wage offers and job mobility fall | Worker combinations, migration, rival entrants |
| Wage ceiling and anti combination law | State at employer request | Wage competition constrained, organizing criminalized | Vacancies may remain unfilled; secret association and strikes rise |
| Recruitment fraud/fees/document seizure | Agent, employer, or broker | Worker arrives indebted or cannot leave | Escape, legal help, worker networks; expose agent and employer |
| Selective property, schooling, or occupation exclusion | State/custom enforced by courts | Some groups cannot own/lease land or enter skilled work; bargaining options shrink | Legal and political challenge, informal work, emigration |
| Workhouse, corvée, penal leasing, enslavement | State/owner with explicit force and legal regime | Labor directly compelled outside an ordinary wage contract | Fiscal upkeep, guard costs, mortality, flight, rebellion, legitimacy collapse |
| Compulsory cultivation or labor quota | Colonial/state authority or concession backed by force | Households must plant an export crop or supply days of work regardless of their own food plan | Hidden acreage, evasion, black markets, food shortages, local resistance |

Postwar U.S. Black Codes provide a concrete example of vagrancy and contract rules coupled to racial land restrictions; the National Park Service also records federal opposition to those laws. Do not present these as neutral labor market rules. [NPS Reconstruction study](https://www.nps.gov/subjects/reconstruction/upload/Reconstruction-NHL_Theme_Study_508.pdf); [National Archives on Alabama vagrancy laws](https://www.archives.gov/files/research/microfilm/m1900.pdf).

### D. Extract more output from those already employed

| Mechanism | Employer or state action | Benefit sought | Countervailing effect |
| --- | --- | --- | --- |
| Longer day, shorter breaks, piece rates and quotas | Employer sets hours and intensity | More output per worker or pay tied to yield | Fatigue, mistakes, injury, lower reproduction/health, strikes |
| Surveillance, overseers, fines, withheld pay | Employer pays supervisors; state may enforce fines | Reduce pace variation and absences | Supervision cost, concealment/sabotage, grievance |
| Machinery and deskilling | Owner invests in real tools and inputs | Higher throughput; weaker skilled bargaining | Capital cost, maintenance, displacement, resistance |
| Child/family labor and gender wage segmentation | Employer recruits household members under local law | More labor supply at lower posted rates | Care and schooling losses, injury, public opposition |
| Imported or migrant labor and strikebreakers | Recruiter/employer finances travel and housing | Weaken local labor shortage or strike | Recruitment cost; migrants may organize too; intergroup conflict |
| Scrip, deductions, and false accounting | Employer/store/creditor controls ledger | Lower effective wage without lowering posted wage | Audit disputes, flight, collective claims, reform pressure |

Output per hour should depend on **nutrition, skill, soil, tools, fatigue, and coercion**, with diminishing or negative returns at extreme hours. Intimidation may get attendance and a short output jump, while worsening injuries, quality, soil, and future labor supply. Raising output must also require buyers, transport, and commodity demand; a glut can make an extraction campaign unprofitable.

## Rules for force and law

1. **Separate proposal, enactment, and execution.** An elite petition changes the political agenda. Passage needs a regime or coalition. Enforcement needs funded officers, courts, information, and physical reach. Owners can attempt illegal violence, but it is recorded as such and contestable.
2. **Require a target and a claim.** Enforcement applies to named parcels, households, debts, contracts, or people. For every eviction or arrest, record legal basis, officer, cost, resistance, and destination. This prevents a tile wide percentage from instantly converting everyone.
3. **Let enforcement fail.** Local solidarity, distance, terrain, unions, counsel, rival officials, or military refusal can block it. Failed enforcement may leave de facto commons access even if a title changed.
4. **Count the full bill.** Owners pay recruiters, guards, advances, compensation, and lost harvests; the state pays police, courts, prisons, and garrisons. Public revenue must come from a payer or actual sale of produced goods, never appear because a person was confined.
5. **Preserve legal differences.** Chattel slavery, convict labor, corvée, debt bondage, tenancy, and wage work are different regimes with different rights and pay flows. Avoid representing them all as `employee=True`.
6. **Make reform enforceable too.** Abolishing a rule on paper does not instantly erase debts or open occupied land. Compensation, document return, title restoration, arrears cancellation, transport, inspection, and legal aid take capacity.

## Data and turn flow

**Minimum new state:** `HouseholdAccess` (person/household, parcel/resource, right type, seasonal yield, recognized/de facto status); `Obligation` (principal, creditor, origin, interest, due date, collateral, dispute status); `LaborAgreement` (regime, employer, hours, pay form, deductions, term, exit clause); `EnforcementCase` (target, law/claim, officer, funding, stage, outcome). Use IDs and existing person/parcel objects, not parallel population counters. Record the **origin** of each debt so a high rate or fraudulent charge is visible and contestable. Keep education/literacy as a factor in contract comprehension and access to legal defense, not as a deterministic propensity to be fooled.

**Order each turn:** (1) weather, yields, prices, land/resource access; (2) tax/rent/debt and employer offers; (3) household plan and labor matching; (4) work, production, injuries, sales and actual wage payment; (5) debt settlement and foreclosure cases; (6) petitions, adjudication, enforcement, flight and resistance; (7) update memories, welfare, class and political support. Cases created today should normally resolve after a visible delay, with emergency actions explicitly marked. Choose one authoritative labor matching path: the mobility scheduler can select candidates, but the reservation/exit logic must decide acceptance before employer attachment.

**Key metrics:** households with independent food access; food days and cash gap; share of labor hours in own production / tenancy / wage work / compulsory regimes; real wage after deductions; worker ability to quit; debt by origin and creditor; land by tenure and de facto access; injuries, fatigue and care time; output per hour; owners' **net** profit after enforcement; state enforcement cost; arrests, evictions, flight, disputes, strikes, and restored rights. Break totals down by region and affected group. An aggregate wage labor share alone cannot show why anyone took the job.

## Player and AI decisions

For an employer, the choice is an investment comparison: **offer better pay/terms; fund productivity; finance credit and stores; lobby for legal exclusion; pay for coercion; recruit elsewhere; or abandon the project**. Each requires cash, time, authority, and a viable market. They may bundle strategies, but they should not always choose maximal violence: guard cost, crop loss, resistance, political backlash, and labor flight can make a less coercive offer more profitable.

For government, the choice is an enforceable institutional package: recognize commons and customary title; tax in kind or cash; permit or prohibit forest/resource use; regulate liens and stores; protect the right to quit and move; fund courts and inspectors; protect organizing; finance relief or public employment; or back owners with police and military force. State revenue, ruling coalition, legitimacy, and coercive capacity shape what it can sustain. Distinguish a law's stated rationale from its measured distributional result.

For households and movements, choices include negotiating a lease, selling a seasonal labor stint, forming a buying/credit cooperative, collective harvest, remitting migrant earnings, contesting title, hiding goods, flight, strike, reclaiming commons, and accepting relief. Coordination and access to records/courts determine which responses are feasible; hunger alone need not create an organized uprising.

## A legible example chain

1. A village household gathers fuelwood and food, cultivates its plot, and owes in kind dues. A cotton merchant offers an advance; the household may accept to smooth a poor harvest.
2. A landlord seeks enclosure. The state must survey claims, decide whose rights count, and fund enforcement. Some villagers retain titled plots; others lose grazing and gathering rights. This is visible by household.
3. A cash tax and survey fee come due. The household compares selling cotton, a seasonal mill/estate job, tenancy, migration, and borrowing. A viable wage can be chosen voluntarily; a poor wage can be refused while food access remains.
4. A crop shortfall makes the advance hard to repay. If a lien is enforceable, the merchant claims the harvest at the agreed price. The player sees the original advance, interest, crop transfer, remaining balance, and any disputed accounting.
5. If the landlord and state also close the commons and penalize movement, exit options shrink. The household may accept a bad wage, sign a sharecropping contract, flee, or organize. Arrest or eviction requires a funded, contestable case.
6. The owner initially gains cheap cotton. The ledger later shows guard expense, lower local food, injury, soil wear, unrest, and possible export price collapse. Reform can restore rights or reduce debt and can also change investment incentives.

## Delivery order and acceptance

1. **First, repair the seam.** Route every candidate through one household acceptance/contract decision; make workhouse arrests law and capacity dependent; audit its food/cash flows. Acceptance: a food secure household rejects a wage below its real reservation value, while a landless household with a funded offer can accept; neither is silently attached or arrested.
2. **Model access and obligations.** Add household rights to named parcels and commons resources, and one ledger for cash rent, taxes, advances, fees, and arrears. Acceptance: enclosure changes only affected households; a cash obligation can increase wage seeking without destroying a plot; all payments have a recipient.
3. **Add debt and tenure paths.** Add harvest advances, liens, tenancy/sharecropping, foreclosure hearings, and creditor-controlled sales. Acceptance: bad harvest can lead to repayment, renegotiation, eviction, or continued tenancy depending on assets and law; no automatic conversion to wage work.
4. **Add law and enforcement.** Add petition/passage/execution stages for gathering bans, exit penalties, vagrancy, and movement restrictions; give each budget, target, delay, and resistance. Acceptance: a legal decree without officers or local reach changes no person's physical access; costs and outcomes appear in the ledger.
5. **Add workplace discipline.** Extend labor agreements with hours, pace, piece rates, deductions, injury and exit. Acceptance: hours and output can diverge; extreme intensity harms health and future productivity; the firm sees net rather than gross return.
6. **Integrate AI, UI, and scenarios.** Expose an inspectable household timeline and a regional "why people work" panel. Start with a bounded cotton district experiment, then use the Egypt scenario only where chronology and existing gameplay support it. Compare secure commons, cash tax, enclosure, and debt/lien treatments under the same weather and prices. Acceptance: each path produces a readable causal history and conserved money/food; outcomes include thriving smallholders, mixed livelihoods, tenant dependency, wage work, flight, and failed coercion.

### Balance tests that matter

- A high wage attracts some secure cultivators without dispossession; a low wage cannot magically fill vacancies when households have viable alternatives.
- Enclosure plus a cash tax increases cash seeking, but can also depress food and produce migration or resistance rather than employment if there are no jobs.
- A bad harvest and legitimate advance may raise welfare in the short run; usurious interest and tied sale can create persistent debt. Debt can be paid off, disputed, or forgiven.
- Wage caps and armed arrests require capacity and can fail; effective enforcement is costly enough to alter owners' and the state's choices.
- A cotton boom can reward cultivators, while a later price fall reveals the risk of monoculture and liens. Revenue, wages, and food stocks remain conserved and traceable.
- Legal reform plus weak enforcement differs visibly from restoration of de facto access.

**Scope note:** Historical references motivate mechanisms and plausible relationships. All coefficients, dates, and event frequencies are game parameters to calibrate; they should not be presented as measured historical constants.
