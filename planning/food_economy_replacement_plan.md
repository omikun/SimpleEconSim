# Replace the food economy: farms, household provisioning, and seasonal supply

Date: 2026-10-31. Implemented: 2026-11-01. Gameplay now uses the replacement food economy.
Implementation, validation evidence, and remaining balance limits: [implementation report](reports/food_economy_replacement_20261101.md).
Revised to incorporate livelihood inertia, commons migration, profession support
metrics, and government responses. Universal steam productivity was a temporary
experiment and is not part of the replacement design.

## 1. Outcome and scope

Replace the current food-production and provisioning rules with one coherent
model. A farm is a persistent operation on land, a household needs meals and a
buffer, and a market connects producers and consumers. A person's career label
is neither a farm nor a food inventory.

The intended result is an economy where households can live on stored harvests,
farms keep working while people have food in their pantries, and productivity
can allow fewer farmers to feed more people. Scarcity can still occur through a
bad harvest, loss of land, low wages, blocked trade, institutional failure, or
poor policy. The simulation should identify which of these is happening.

This is a replacement of the governing food rules, not another collection of
emergency exceptions. Reuse existing infrastructure where appropriate—land
titles, cash transfers, auctions, transport, installed machinery, and traces—but
replace the decisions those systems currently receive from the food model.

Preserve the user-approved profession departure cap, including its configurable
four-person minimum. Add a livelihood-viability gate before proposing a move;
greater returns elsewhere alone do not trigger departure. The cap controls
permanent career changes; it is not the food supply target. Preserve the
deliberate separate clocks: one agent year per turn
and ten turns per seasonal cycle. Express food, work, and forecasts consistently
in game turns rather than interpreting a turn as a literal agricultural year or
day. No change to aging or reproduction timing is part of this project.

The first complete implementation includes seasonal farming, shared household
provisioning, livelihood inertia, bounded subsistence work and migration,
storage, local sales, existing delayed trade, nutrition, a cross-profession
needs view, bounded policy responses, initialization, and explanations. Defer new
crop species, livestock nutrition, detailed diets, a futures exchange, and a
general replacement of every industry's production function.

## 2. Evidence to explain

Use the [verified first-60-turn campaign](reports/campaign_60turn_deep_dive_20261031/deep_dive.md)
as a diagnostic baseline, not a balance specification:

- The opening 1,610 food units cover about 5.4 basic consumption turns. Many
  growers start with 22 units, above the generic food-production inventory
  limit of 20. Their reserves directly suppress production.
- Actual adult farm membership falls from 44 to 11, then recovers to 48 by turn
  60. Recovery in headcount does not restore dependable food output.
- Nearly 90% of newly supplied food comes from the activity called foraging.
  That category currently mixes subsistence access with a very generous food
  allowance, rather than measuring a finite local resource and allocated work.
- Wealth raises desired staple consumption from four units to eight or nine.
  Early excess consumption and later household shortages coexist.
- The granary contains 103 units at turn 60 while some residents remain hungry.
  Physical presence, legal ownership, market offers, and household access differ.
- Dissolved corporations enter the resident population. Three of the eleven
  recorded starvation deaths in these 60 turns belong to those entities; eight
  belong to original or born human residents.

Current code also contains crop-cycle forecasts and food-security responses.
These are useful prior work, but the replacement forecast must derive from
actual crop commitments, stock accounts, and deliveries rather than perpetuate
the current rolling-production estimate as a second authority.

## 3. Model contracts

### 3.1 Food units and nutrition

Retain the existing food-unit convention: one standard unit represents 500
game-calories, and a reference adult's basic requirement is four units per turn.
This is an economic accounting scale. Age-specific requirements remain explicit.

Use fixed-point quantities at one-thousandth of a food unit in the new accounts;
existing whole-unit goods enter as exact multiples. Round only at defined
transaction boundaries. Carry remainders for losses and allocation; rounding
must never repeatedly create or destroy unrecorded food. Compatibility views
must not discard the underlying fractional balance.

Separate three quantities:

1. **Basic nutrition:** the household's ordinary calorie requirements.
2. **Recovery nutrition:** a bounded temporary addition for depleted people.
3. **Food preference:** willingness to pay for preparation and quality.

Wealth changes the third quantity. It does not double baseline staple calories.
For the initial implementation, cap recovery intake at 25% above normal need,
falling continuously to zero as body reserves recover. Treat this as a tunable
game parameter. Do not count reduced metabolic need during starvation as proof
that the region's ordinary nutritional requirement has been met.

Use existing raw and prepared food for the first quality distinction. Prepared
food buys convenience/satisfaction at a premium and substitutes for raw food
calories. It is not an additional compulsory meal. Its recipe consumes raw
food, work, and any specified fuel; conversion cannot create calories. Do not
introduce a full nutrition or cuisine system to fix demand.

Body reserves remain personal, separate from physical food stocks. Audit the
current reserve, deficit, recovery, and mortality calculations for agreement
with the new single consumption event. Retain a continuous deprivation risk;
do not add an arbitrary immunity period or promise immediate recovery after
one adequate meal.

### 3.2 Explicit state

Introduce a small set of authoritative records:

| Record | Essential state | What it replaces |
| --- | --- | --- |
| Household | Members, dependents/guardian, food accounts, authorized purchasing funds, reserve target | Repeated per-person guesses about family demand |
| Farm operation | Stable ID, plot allocation, operator, tools, storage, operating stock, employment/claims | Food production inferred from a person's current output label |
| Crop cycle | Planted area, seed used, stage, completed work, weather history, remaining harvest | Independent random food-production attempts each turn |
| Food account | Owner, physical location, raw/prepared quantity, storage capacity and losses, reservations | Food split between normal inventory, emergency counters, and implicit reserves |
| Work allocation | Person, activity/operation, fraction of available turn, delivered effective work | Separate work deductions and free activity allowances |
| Food outlook | Time-indexed supply, demand, deliveries, confidence, household access gaps | Multiple incompatible meal and cycle shortage estimates |

These are components and records, not a new inheritance hierarchy for every
agent. Use aggregate commodity balances and reservations, not a lot object for
every grain unit.

Every physical unit has exactly one account and location. A reservation is a
claim on that account's stock, not a second inventory. A shipment is an account
in transit. Compatibility reads such as `inv_get(food)` may expose a derived
view; they must not become independently writable shadow balances.

An operating business and its owner remain distinct entities. Dissolution
settles or transfers assets and closes the business; it never turns a company
into a person. Fix this before interpreting mortality or labor results.

### 3.3 Households and ownership

Build explicit households from the existing parent/dependent relationships.
Unlinked adults start as single-adult households; do not invent family links.
Handle parent death, guardianship, adulthood, migration, and household splitting
through named membership transfers. A dependent appears in exactly one meal
plan. A change of profession does not split a household.

Pooling food does not silently merge personal cash or property. The household
buyer may spend only funds authorized by its members. Keep payer identities
and budget reservations so two orders cannot spend the same money.

Farm operating stock belongs to the operation's lawful owner or owners. Moving
grain to a household pantry, paying a worker in kind, repaying a crop lien, and
selling grain are explicit transfers. Seed is reserved from owned grain and
actually consumed at sowing. Eating the seed reserve is possible by releasing
that reservation, with the lost planting opportunity made visible.

## 4. Persistent farms and seasonal production

### 4.1 Land and continuity

Create operations on existing arable plots. A plot may contain several
operations, but their allocated areas cannot exceed its actual arable area.
Customary rights determine who may operate land; they do not give every new
household member another copy of that land's productive capacity.

Farm ownership, operation, and labor are distinct. The operator needs lawful
access. A hired harvest worker does not need a personal field right. Farms
persist through a worker changing career, the operator's death, succession,
and temporary labor shortages. Unworked crops deteriorate through missing
work; they do not disappear merely because an agent changed its label.

Enclosure, eviction, and land conversion update the same operations and rights.
Specify the lawful recipient of standing crops and stored grain. Record any
destruction rather than losing stock through object deletion.

### 4.2 One ten-phase crop calendar

Use a single configurable crop calendar, aligned with the game's ten-phase
seasonal clock. First candidate: sowing in phases 0–1, tending in 2–5, harvest
in 6–7, and storage/fallow in 8–9. Finalize the calendar before integration and
update tribute timing and seasonal UI together; do not leave incompatible
definitions of harvest in different modules.

Keep the ten-phase seasonal curve as a seasonal input. Assign its effect once
to the relevant crop stage; do not multiply a seasonal harvest by the old
per-turn food-production curve again. Existing authored climate and Nile
shocks enter the crop's growth/yield inputs explicitly.

Each operation chooses planted area using land, seed, tools, expected work,
working funds, expected household needs, sale prospects, and storage. This is a
bounded rule-based plan, not a multi-period optimization solver.

Conceptually:

```text
potential harvest = planted area × yield per area
                    × soil/water/weather factors × applicable technology

realized harvest = potential harvest × establishment factor
                   × tending factor × harvested fraction
```

Establishment requires actual seed and sowing work. Tending records delivered
work during its window. Harvesting requires actual harvest work and leaves
uncollected crop at risk until the harvest window closes. Use bounded,
diminishing-return work factors; additional workers cannot exceed the land's
potential. Missing an expired work window cannot be repaired by retrospective
labor. Weather may change prospects, but does not redraw the whole crop on
every production call.

Household pantry fullness never enters this yield equation. Storage constraints
can change the next planting plan, selling decisions, or spoilage. They cannot
retroactively stop a standing crop growing because its owner has dinner.

### 4.3 Technology

Attach the applicable machinery and productive assets to the operation. Apply
each benefit to its actual channel: work required, yield potential, processing,
or storage losses. Fuel, repairs, and construction materials remain real costs.
Avoid applying one productivity bonus independently to both work and yield
unless the technology explicitly provides both effects.

Remove the universal steam-production modifier when the replacement is
integrated. Steam is a power source for applicable machinery, not a direct
bonus to every profession. A farm benefits only from an implemented compatible
application, such as powered pumping or threshing, with its own equipment,
inputs, installation, operating costs, and scope. If an application is absent,
steam knowledge or an unrelated installed engine gives that activity no bonus.
Other professions likewise receive applicable tools/processes rather than a
universal multiplier. Engineering progress receives actual operation/use and
funded engineering work, not farmer headcount or forecast output. Preserve
historical experimental results as records, not as the new technology baseline.

Preserve the slower soil degradation setting. Soil, pollution, illness, and
work refusal affect named inputs. The farm explanation should show their
separate contributions, including the case where many nominal farmers deliver
little effective work.

## 5. Work, careers, and subsistence

Give each eligible person one available-work budget per turn. Allocate it
among their paid or independent main work, seasonal farm work, commons
subsistence, and engineering activity. Health and participation determine
delivered work. Total committed time cannot exceed availability, and the
existing workday law remains binding.

Extend ordinary production to accept effective labor supplied by this ledger.
Retain non-food recipe behavior where possible, but remove competing deductions
for foraging or engineering. A half-time factory employee must contribute
half-time work through the same adapter, not a full worker plus a second food
activity. Do not rewrite unrelated industrial recipes in this project.

Replace the unconditional foraging allowance with two named paths:

- Subsistence cultivation belongs to a farm operation and uses the crop model.
- Gathering, fishing, and gleaning use a finite seasonal commons resource pool,
  lawful access, work time, and diminishing returns under crowding.

Commons capacity belongs to the land, not to each resident independently.
Enclosure affects access. Population growth does not multiply available wild
food. The first version can aggregate these activities as **commons food**;
it must distinguish them from field cultivation in accounting and UI.

### 5.1 Stay while the present livelihood works

Use a small rule-based state machine, not continuous global profit ranking:

1. **Stable:** retain the current livelihood when it covers ordinary household
   necessities and has a credible path through the seasonal cycle. Do not
   propose a permanent move merely because another profession pays more.
2. **Under pressure:** record a viability failure when ordinary recurring
   income plus accessible subsistence cannot cover necessities and liquid
   reserves are projected to run out before a credible replenishment. Use a
   two-turn cash runway and two consecutive adverse observations as initial
   tunable thresholds. Exclude optional luxury purchases and one-time voluntary
   investment spending from this test.
3. **Seeking a replacement:** persistent pressure permits searching. Actual
   meal failure or loss of the current livelihood—closure, eviction, or loss
   of usable inputs—permits searching immediately. People need not exhaust
   their body reserves or die before recognizing failure.

For growers, test the full crop-cycle budget, stored food, crop prospects, and
necessary costs. A non-harvest turn with no grain-sale revenue is not itself
bankruptcy. A farmer who can feed the household and meet necessities stays
even if furniture has a higher quoted return. Conversely, being labeled a
farmer does not prove subsistence is secure.

Before committing a permanent change, try feasible ways to retain the
livelihood: local commons food, a temporary paid shift, or a funded job in the
same trade. Choose an alternative that restores household viability with the
least executable disruption: usable existing skills, low entry costs, and
local access. Use net returns as a tie-breaker among comparable viable choices,
not a command to select the richest profession in the region. Destination
vacancies, inputs, startup costs, and funds remain binding.

Only these eligible proposals enter the existing profession departure budget;
their feasible gain still determines its rate. A high sector price cannot draw
every comfortable worker into that proposal pool. Successful recovery clears
pressure. There is no extra personality distribution, elaborate belief model,
or second career scheduler.

New working-age entrants and genuinely displaced people may choose among
feasible entry opportunities without an established trade to abandon. Record
first entry separately. Company ownership is not an exemption from livelihood
assessment: an insolvent owner with hungry dependents must also have choices.

### 5.2 Commons are a continuing subsistence avenue

People facing a meal gap attempt to use accessible local commons while those
commons exist and can yield food. Employment or a non-farming profession does
not automatically disqualify them. Reserve required gathering time in the work
plan before discretionary work. Honor contracted hours where possible; if
survival requires absence from a paid shift, record the lost production/pay
and any contractual consequence rather than granting a second free workday.

Foraging does not imply a new primary profession. A household adequately fed
by its current work and commons does not switch merely because cash earnings
are low. Retain travel/work costs and finite seasonal yields: open commons
create an avenue for subsistence, not an unlimited guaranteed meal under any
crowding or ecological conditions. Show denied access, exhausted capacity, and
insufficient work time as separate causes of an unsuccessful attempt.

### 5.3 Subsistence migration and future movement laws

When local subsistence fails, consider both feasible local livelihoods and
nearby regions reachable by existing routes. Closure of commons is an explicit
reason to look elsewhere. A nearby usable commons can be a destination without
a factory vacancy or a private plot purchase. Prefer a viable local solution
when it exists; do not require someone to wait for starvation before planning
a move after losing their subsistence avenue.

Check destination rights, available commons capacity after crowding, journey
time, food for the journey, household/dependent movement, and known conditions.
Commit arriving households against remaining capacity in deterministic order
so all migrants cannot assume they alone will use the same spare resource.
Transit is a real location/time interval, with residents and food accounted
for once. Temporary foraging across a reachable nearby boundary may be a work
trip rather than a residential move if the round trip fits the work budget.

Expose one movement-policy evaluation shared by migration and subsistence
travel. Defaults permit movement. A future vagrancy or settlement law can add
permit requirements, expected penalties, or enforced barriers. Declared law and
actual enforcement are separate inputs; deterrence can discourage movement
without magically closing destination commons. Lawful move, deterred move,
denied passage, and any explicitly modeled evasion have distinct reasons.
Do not implement a full new policing/legal system in this food rewrite, but
make the policy interface and acceptance fixtures work now. Restricting
movement can strand people and worsen deprivation; it does not create jobs or
food, and it must never be disguised as a voluntary profession change.

The profession departure floor is not a residence restriction. Moving while
retaining a trade is a migration event, not a permanent profession change;
recompute live local membership accordingly. Do not prevent a subsistence move
by treating the last four members of a profession as legally bound residents.

Commit one work plan from these decisions. Seasonal farm vacancies specify
required work, pay or in-kind terms, and available funding.

The profession cap continues to govern changes in primary profession. A
temporary harvest shift does not relabel a carpenter as a farmer and back next
turn. Record both profession headcount and actual farm labor. Revise livelihood
return estimates to use seasonal net returns per unit of committed work,
retained household food, costs, and opportunity costs—not gross harvest value
compared with a single turn's wage.

Returning to farming requires available land as an operator or a real farm job
as a worker. The former can require seed and waiting until sowing; the latter
can supply useful work immediately when a crop needs it. The profession floor
does not create land, inputs, or vacancies.

## 6. Provisioning, storage, and markets

### 6.1 Household reserve planning

Compute one meal plan per household. Prioritize members' basic requirements,
then bounded recovery nutrition, then optional food quality. Allocate scarce
household food proportionally to requirements, with explicitly recorded
medical/recovery priority if enabled. Do not let iteration order decide which
child eats.

The reserve target is a replenishment plan:

```text
target stock = basic needs until the next credible replenishment
               + explicit safety buffer
               - committed accessible deliveries in that interval
```

For a farm household, replenishment may be its next harvest. For a wage
household it may be the next regular purchasing opportunity, provided local
offers and wages make that credible. Use a one-turn safety buffer as the first
candidate parameter, then test it. Do not make every urban household hoard a
full crop cycle simply because the region farms seasonally.

Separate today's meal bid, reserve-restocking bid, and quality bid. Their
urgency and willingness to pay differ. Budget them together, with actual
liquid funds or explicitly approved credit. Desired but unfunded food remains
an access gap; it cannot count as funded market demand. Do not multiply a large
quantity by a total budget mistakenly treated as a unit price.

### 6.2 Storage and sales

Provide ordinary household pantry capacity, farm storage, merchant storage,
and public granaries. Capacity and losses are physical properties, separate
from a household's desired reserve. Use a simple aggregate storage-loss rule
per account/storage class, with carried fractional loss and explicit events.
Overflow is offered, moved, or recorded as loss; it is never silently removed.

Operators reserve seed and planned household withdrawals, then offer commercial
surplus. They can revise these reservations as prices and risks change. There
is no permanent blanket prohibition on selling stocked food, and no rule
requiring farmers to sell their next meal to make the market liquid.

Use existing merchant/trader actors and transport infrastructure for storage
and distribution. Make storage trading a funded activity with carrying costs,
capacity, purchase risk, and actual sale revenue. Do not create a buyer of last
resort with unlimited money or an automatic guaranteed markup. The replacement
must work in a balanced local economy without requiring an artificial merchant
subsidy. Explicitly isolated scenarios cannot assume imports.

### 6.3 Prices and settlement

Reuse the auction/settlement machinery and dated paid-price observations.
Replace its food-order generation. Reference quotes are estimates; actual
funded orders and reachable sellers determine meals and realized farm returns.

Use one household food-purchasing phase after payroll and currently due cash
settlements. Earlier production-input orders may include grain for processors
or firms, but cannot consume a second copy of household demand. Reserve stock
and cash across all order phases. Update the food reference once from the
combined dated transaction evidence, not once per phase.

Keep local sales and interregional delivery distinct. Food sold to a distant
buyer moves into transit and becomes available only on arrival. Harvest,
processing, taxes, liens, in-kind wages, and aid each debit and credit named
accounts. Set the priority of competing crop claims once, in the contract/
tenure rules; forbid each subsystem from claiming the same harvest separately.

## 7. One outlook, two distinct problems

Project a turn-by-turn regional food balance through the next main harvest and
one subsequent full crop cycle. A positive end-of-cycle total must not hide an
earlier lean-season deficit.

```text
closing stock[t] = opening stock[t] + expected local receipts[t]
                   + committed arrivals[t] - normal meal requirements[t]
                   - seed/processing uses[t] - losses[t]
                   - committed departures[t]
```

Processing transfers calories between raw/prepared forms; count net losses,
not gross input and output as separate additions to food supply. Run the
projection in calorie-equivalent units while retaining physical commodity
balances for settlement. Crop prospects reflect work completed, remaining
feasible work, and weather uncertainty. Show central and adverse cases; never
count merely hoped-for imports as committed arrivals.

Alongside the physical balance, assess each household's **access**: owned food,
accessible deliveries, purchasing funds versus actual offers, legal access,
and expected delivery timing. Public grain is part of regional physical stock
but not a household entitlement until the governing policy releases it.

Classify shortages as supply, purchasing power, restricted/withheld stock,
transport delay, or a combination. Include crop labor, seed, storage, and
pollution constraints as explanations for supply risk. Feed this same outlook
to household planners, farm planners, government policy, trace output, and UI,
with visibility appropriate to each actor. Decisions use information available
at the planning boundary, not future random outcomes.

Existing ordinary and emergency policies become explicit rule configurations:
eligibility, reserve floor, release/procurement limit, budget, and transport
capacity. Relief buys or transfers real food. Government may fund farm work,
storage, transport, or engineering, but public spending does not automatically
make an immature machine commercially efficient. Keep player policy choices
and rival AI distinct; do not silently enable emergency government in every
test to conceal a broken private economy.

## 8. A coherent initial economy

Replace uniform profession-based food grants with an opening-state builder.
Inputs include population/households, crop phase, land and operations, standing
crops if any, tools, seed, stored harvest, public/private ownership, cash,
merchant capacity, and any committed shipments.

Default balanced scenarios should start at a declared post-harvest phase with
stored output from a documented synthetic preceding harvest. Support other
phases by explicitly authoring standing crops and earlier work. Introduce a
scenario seasonal-phase offset rather than altering birth turns to move the
calendar. Display and persist that offset consistently across climate, tribute,
forecasts, and UI.

The builder must:

1. Allocate land without duplicating area or customary capacity.
2. Construct household and operating accounts, then distribute the authored
   harvest among seed, pantries, commercial storage, and public stocks.
3. Check that the preceding harvest is feasible for its declared land, work,
   technology, and weather assumptions. Initialization may endow assets, but
   every endowment is listed; it must not masquerade as a live simulated sale.
4. Set cash/working-capital endowments and opening quotes independently from
   physical food; no fabricated paid-price observations.
5. Produce a full time-indexed first-cycle outlook and report any deficit.
   A balanced scenario fails validation if its stated assumptions cannot feed
   residents. A deliberately distressed scenario may start short, labeled so.

Do not solve initialization by merely changing 22 to 19, setting stocks to
zero, or increasing the food inventory cutoff. The pantry no longer controls
crop growth at any stock level. Opening reserves buy time; they are not proof
of a sustainable food economy.

For a deliberately simple calibration example, 75 adult-equivalent residents
need 300 units per turn, or 3,000 per cycle. Suppose seed use is 180 and storage
losses are 120 per cycle. A renewable harvest must supply 3,300, not just replace
the visible household pantry. With a 300-unit carryover buffer, post-harvest
stocks of 3,600 fall to 300 before the next 3,300-unit harvest and return to
3,600. The 300-unit buffer is a stock maintained across cycles, not another
300 units of recurring consumption. These are illustrative accounting values,
not prescribed yields or a claim that the actual scenario has 75 equivalent
adults. The real builder computes age-specific demand and physical losses.

Use optional deterministic prehistory later as a scenario-authoring tool, not
as a hidden runtime rescue. Do not discard or reroll failed starts until a
healthy seed appears.

## 9. Turn order and implementation boundaries

The canonical order is:

1. Apply scheduled arrivals and opening storage losses; update membership and
   known rights changes; snapshot stocks, budgets, and observations.
2. Build household requirements and the shared food outlook. Plan crop work,
   funded vacancies, primary career moves, and each person's work allocation.
3. Settle production-input purchases and any explicit working-capital finance.
   Confirm funds and inputs before committing work. Adjust failed plans once
   within the same work budget; do not add a second career-decision pass.
4. Deliver work and produce: crop stages, harvest, commons food, processing,
   and other industries. Record actual labor and receipts.
5. Settle harvest claims and ordinary goods/business sales; pay wages, redeem
   due in-kind/scrip claims, and settle due cash obligations in a declared order.
6. Clear household food purchases using available funds. Perform authorized
   public/charity/estate transfers and bounded same-turn redistribution of
   already local stocks. Schedule new distant shipments for future turns.
7. Allocate meals, consume once, update nutrition/health, then assess mortality.
   Apply births, deaths, succession, and household changes for the next plan.
8. Record closing balances, access failures, outlook error, prices, and audits.

Orders or work needing funds cannot spend anticipated sales proceeds without
real financing. Wage arrears and failure remain possible and visible. Military
and institutional food requirements must enter the balance even if they use
different supply accounts from civilian households.

World/province orchestration must apply arrivals and common planning snapshots
before regional iteration. A later-stepped region cannot send food backwards
in time to a region that has already eaten. Give standalone, desktop, and web
engines the same phase coordinator. Persist phase markers and reservations so
checkpoint restore cannot repeat a harvest, payment, or meal.

Suggested ownership of new code:

| Area | Replacement responsibility | Main existing integrations |
| --- | --- | --- |
| `micro/food_accounts.py` | Accounts, reservations, transfers, conversions, losses | Agent inventories, granary, emergency food, processing |
| `micro/households.py` | Membership, purchasing authority, meal allocation | Demographics, inheritance, migration |
| `micro/agriculture.py` | Operations, crop calendar, work requirements, harvest | Land tenure, water, soil, productivity, crop claims |
| `micro/work_allocation.py` | Shared work budget and effective work | Labor choice, career transitions, firms, engineering |
| `micro/livelihood_viability.py` | Stay/pressure/search decisions before the departure cap | Household budget, career proposals, seasonal returns |
| Existing migration coordinator | Subsistence destinations, household travel, policy evaluation | Commons access, routes, transit, future movement laws |
| `micro/food_provisioning.py` | Meal/reserve/quality orders and funded offers | Market, payroll, scrip, relief |
| `micro/food_outlook.py` | Physical projection and household access diagnosis | Policy AI, private planning, server, traces |
| `economy/production_needs.py` | Commodity requirements, constraints, intervention estimates | Recipes, productive orders, repair needs, stocks, food outlook |
| Existing government policy layer | Funded procurement, advances, hiring, relief, review/expiry | Treasury, contracts, private delivery/work, needs view |
| Scenario initialization | Opening-state builder and validation | Default world, authored scenarios, audit campaigns |

Names are proposed; responsibility boundaries are the design contract. Keep
orchestration in a coordinator rather than spreading state mutations across
diagnostic helpers. Observers and UI projections remain read-only.

## 10. Delivery sequence and removal of old rules

### A. Establish trustworthy accounting

Archive the current seeded baseline with a source fingerprint and corrected
human/company classification. Fix company dissolution identity. Add food
balance and population-identity audits alongside the existing currency audit.
Inventory every food writer and consumer, including armies, traders, children,
crop credit, taxation, aid, prepared food, pillage, inheritance, and transit.

**Exit condition:** every source/sink has an identified owner and meaning; an
inactive company cannot eat, age, reproduce, or die of starvation.

### B. Build the replacement domain in isolation

Implement records, account operations, household membership, crop stages, and
work allocation as independently executable domain rules. Build tiny authored
economies against those rules before connecting the live stepper. Implement
the outlook from those exact states. No legacy food-production fallback.

**Exit condition:** a household and farm can complete two crop cycles with
conserved food/work and predictable meals, including seed renewal.

### C. Build provisioning and the opening-state builder

Implement saturated calorie demand, bounded recovery, quality substitution,
reserve targets, funded household orders, farm offers, storage, and initialized
crop/stock positions. Connect existing cash settlement and auction primitives.

**Exit condition:** a farm household and a wage household can exchange food
and goods over two cycles; opening pantry size never disables a standing crop.

### D. Integrate the full live economy through one coordinator

Connect land institutions, crop claims, effective labor in all production,
livelihood viability, commons access, subsistence migration, technology,
engineering, payroll, transport, policy, nutrition, and lifecycle events.
Route all food mutation through the new accounts. Connect the same
coordinator to every supported engine and scenario entry point.

At cutover, remove or retire the old generic food recipe production path,
unconditional foraging grants, wealth-driven staple appetite, overlapping
reserve calculations, independently spendable emergency counters, and rolling
harvest guesses used as authoritative forecasts. Replace existing food-policy
and UI projections with views of the new state. Retain historical trace formula
decoders for old reports; they do not execute old gameplay.

Development can retain a version-selected old runner for baseline comparison,
but a running world uses exactly one food model. Do not mix old and new
behavior per agent, stock threshold, starvation flag, or scenario name.

**Exit condition:** a live run has one crop producer, one work allocator, one
household meal planner, and one physical food balance; no legacy writer remains.

### E. Explanations and tuning

Deliver the food-support and cross-profession needs UI below, the bounded
government response set, and scenario migrations. Run controlled acceptance
and calibrate only after conservation and causal tests pass. Record which
parameters changed, with matching seed/scenario configurations. Do not claim
all mortality improvement is caused by agriculture when demand, identity, and
institutions also changed.

## 11. Player presentation

Use ordinary terms and answer three questions at each level:

- **Region:** “Will food last until harvest?”, “Can households obtain it?”, and
  “What is limiting the next harvest?” Show stock coverage, the earliest
  projected gap, expected/adverse harvests, imports arriving in time, and
  households lacking meals. Split household, commercial, public, seed, and
  transit stocks without summing reservations twice.
- **Farm:** show land, crop stage, seed, work needed/supplied, expected harvest,
  retained food, offered food, machinery, and the largest constraint. Example:
  “Harvest expected in 3 turns; tending work is 60% staffed.”
- **Household:** show meals covered, reserves, next credible income/delivery,
  food cost versus spendable funds, and a concrete unmet need. Example:
  “Can afford 3 of 4 units; local grain is available.”

Distinguish primary farmers from effective farm work. Show labor supplied by
farmers, seasonal hires, and household subsistence. Explain a career decision
with its viability/pressure reason, considered alternatives, and departure
quota. Include “Stayed: household needs covered” even when another trade has
higher returns. A lack of switches can then be understood as inertia rather
than a broken comparison.

### 11.1 Farmers' support capacity and the realized food balance

Add a compact **Food support** card with three views, all using the same
accounts and outlook:

1. **Latest completed turn:** farm food, commons food, net imports/exports,
   meal requirements and actual meals, seed use, losses, and stock drawdown or
   accumulation. During an uncompleted turn label values “so far”; never compare
   partial output with a completed population's whole-turn needs as a final
   result. Include current projected closing balance separately.
2. **Completed crop cycle / rolling ten turns:** sustainable domestic support
   from agriculture, with subsistence cultivation included and commons shown
   separately. Compare with average ordinary nutritional requirements over the
   same interval. Show how much of support came from imports or drawing down
   inherited stocks. Neither can be mislabeled as domestic farm productivity.
3. **Next crop cycle:** expected and adverse support, remaining work/inputs
   needed to achieve it, stock coverage until harvest, and projected shortfall.

Convert food into adult-equivalent meals for comparison: one adult-equivalent
needs four standard food units per turn. Display actual people alongside
age-adjusted equivalents; children are not silently counted as four-unit adults.

```text
net farm calories per cycle, before trade = harvested edible calories
    - seed use - attributable losses

farm support capacity = net farm calories per cycle, before trade
    / (reference adult calories per turn × cycle length)

farm contribution margin = net farm calories per cycle, before trade
    - ordinary resident calorie requirements over the same cycle
```

This is production by local farms, not the final regional food balance. Show
exports separately as allocation of food away from local residents. Add commons
and net accessible imports (imports minus exports, deducted exactly once) for
total support. Count processing once: turning grain into prepared food changes
its form and may lose calories; it does not add another harvest. For incomplete crop cycles,
use the outlook rather than treating an early harvest as a completed annual
yield. Clearly label rolling observations versus completed cycles.

Illustrative presentation, not observed campaign data:

> 30 primary farmers / 18 full-time-equivalent farm workers.
> Farms support 105 adult-equivalents; residents require 120.
> Farmers themselves require 30; other residents require 90.
> Farm surplus after farmers' meals supports 75 of those 90: gap 15.
> Commons supply 10 equivalents, leaving a local production gap of 5.
> Stored food covers that remaining gap for 4 turns; next harvest is in 6.

In this example primary farmers happen to have 30 adult-equivalents of need;
calculate their actual requirements in a real run. Non-farming dependents count
among other residents. Display gathering work that reduced farm time as well,
so the two food sources cannot appear to use the same labor twice.

Name the distinction explicitly: **production deficit**, **reserve drawdown**,
and **unmet meals** are different measurements. A seasonal production deficit
can be intentional while stored harvest covers meals. Report a stockout risk
only when the time-indexed stock path goes negative or a household cannot
access its share. Do not recommend adding farmers solely because this turn's
harvest was zero.

### 11.2 Extend the view across professions

Add an **Economic needs** table, organized by commodity/production chain with
profession links rather than assuming one profession per final good:

| Column | Meaning |
| --- | --- |
| Workers / effective work | Primary profession count and delivered labor |
| Output / requirements | Actual output against household necessities, productive input use, repairs, and funded orders |
| Stocks / trade | Usable stock, committed arrivals/departures, and coverage |
| Pressure | Sustained shortage/surplus, unmet essential need, paid prices and unsold offers |
| Binding constraint | Labor, skill, inputs, land, equipment, finance, access, or transport |
| Possible response | A feasible intervention and the conditions/costs needed |

Count intermediate requirements once along each production chain. Distinguish
funded commercial demand from unmet necessities that currently have no buyer
budget. A luxury stockpile and an iron shortage preventing food-tool repairs
have different urgency. Do not invent a universal “correct” worker share or
claim that all goods support people in the same way calories do.

Where labor is actually binding, estimate extra effective work needed under
current productivity, land, and input constraints. Show “about 5 additional
full-time workers, provided seed is funded,” not “need 5 farmers” from a fixed
population ratio. If land, iron, or water binds instead, say that more labor
alone will not close the gap. Equipment improvements can make an already small
profession sufficient; that is a successful outcome.

### 11.3 Government tools for profession balance

Government changes the conditions under which production and livelihoods are
viable. It does not continuously assign everyone to the most profitable trade.
Use the common needs table to choose a funded intervention:

| Mechanism | What the government does | Principal limit or cost |
| --- | --- | --- |
| Procurement contracts | Place time-limited orders for grain, timber, iron, cloth, or other needed goods, with quantity and price/ceiling stated | Treasury must reserve funds; only delivered goods are paid unless an explicit advance is contracted |
| Crop/enterprise working-capital advances | Fund seed, tools, raw materials, or payroll against a real production plan | Public credit exposure and repayment/default; cannot fix absent land or inputs |
| Seasonal hiring support / paid public work | Fund an actual harvest shift, irrigation repair, hauling job, or other productive task | Real payroll, available workers, competing work time, and potential private-worker displacement |
| Training and entry grants | Finance a bounded apprenticeship/tool package for entrants, unemployed, or already livelihood-insecure workers | Training delay, real trainers/tools, limited places; no instant skilled profession conversion |
| Rights and access policy | Preserve/open commons, lease usable plots, or remove a demonstrated entry barrier | Finite capacity, property/political consequences, and possible loss of another land use |
| Public storage and logistics | Buy/store a reserve, improve a route, or contract delayed delivery from surplus areas | Construction/operating costs, food losses, physical delivery limits |
| Targeted relief / essential purchasing support | Transfer food or money to households with an access failure | Cash cannot feed people when supply is absent; demand can increase prices |
| Sector investment / engineering | Fund relevant machinery, maintenance, or engineering where productivity is the bottleneck | Capital, materials, skilled work, operating costs, and development delay |

Procurement creates a visible credible buyer, not a raised reference quote or
free producer income. Advances are loans or explicitly declared grants, never
silent money creation. Avoid paying both a broad output subsidy and a full
procurement premium for the same delivery without an explicit policy choice.

Launch the first playable policy set with bounded procurement, productive
working-capital advances, seasonal hiring support, and targeted relief, reusing
existing policy/finance actions where available. Connect existing access,
logistics, and investment actions to the needs explanations. Add the training
program as a subsequent capability using the same funding/eligibility interface.
Movement restrictions remain a future legal capability through section 5.3,
not an automatic remedy selected by the food AI.

Make the choice depend on the diagnosis:

- Farm work is short but seed/land exist: offer funded seasonal jobs and recruit
  new entrants or livelihood seekers, preserving viable workers' inertia.
- Farmers are present but tools/seed/working capital are missing: finance the
  missing input; do not recruit another cohort to idle on the same land.
- Grain exists but households cannot obtain it: release/buy relief or improve
  purchasing power and delivery; adding farmers has a delayed effect.
- Iron constrains tool replacement: place a bounded iron order or finance its
  inputs, not a grain subsidy that leaves the tool bottleneck unchanged.
- Output is persistently unsold: let time-limited support expire; avoid funding
  additional permanent capacity without demand. New entrants seek other viable
  needs; established workers reconsider when their livelihood ceases to work.

Government AI uses the same information available to the player. Check a full
crop-cycle outlook before classifying food pressure; use two consecutive
adverse observations for non-seasonal discretionary intervention as an initial
tuning rule. Urgent meal failures permit immediate relief. Prioritize essential
needs and binding inputs, respect a declared overall budget, and preview the
next upstream constraint before committing a contract. Limit each program by
quantity, funding, and expiry, then reassess actual deliveries before renewal.

Show cost, delay, expected benefit, and assumptions in the order preview—for
example, “Fund 5 harvest shifts for 2 turns; expected +80 grain, if the crop
remains viable.” Actual work and output determine the result. The AI cannot
teleport workers, change their profession flags, override land constraints, or
spend anticipated fiscal revenue without credit. Report why an otherwise useful
action is unaffordable or politically unavailable.

Do not expose accounting implementation choices as player decisions.

## 12. Acceptance criteria

### Accounting and causal checks

- Each commodity balance closes: opening stock plus harvest/gathering,
  processing outputs, and imports equals closing stock plus consumption,
  exports, seed use, processing inputs, and spoilage. In the combined calorie
  balance, processing inputs/outputs cancel except their recorded conversion
  losses. Internal transfers cancel in both balances.
- Work allocations do not exceed availability; health/strike deductions are
  applied once. Land and commons productive capacity cannot be duplicated.
- Population reconciles births, deaths, and migration for human entities only.
- Fixed crop/work/weather inputs give the same harvest with empty or full
  household pantries. Insufficient storage produces a recorded storage/sale
  consequence, not a skipped crop-growth call.
- Leaving a farm, returning, hiring a landless worker, operator death, and
  enclosure affect the correct crop/rights state without creating harvests.
- Basic calorie demand is invariant to wealth; recovery is bounded; prepared
  food substitutes for raw food and consumes real inputs.
- Payroll precedes household purchasing; every person consumes once; every
  delivery has one arrival. Repeated phases and save/restore cannot duplicate
  transactions, reservations, work, or meals.
- The outlook detects an intermediate lean-season deficit even if the next
  harvest is large. Unfunded bids and speculative imports do not close gaps.
- Diagnostics do not mutate outcomes. A fresh-process checkpoint replay matches
  an uninterrupted seeded run, including pending crops and shipments.

### Small controlled economies

1. **Renewable subsistence:** two complete cycles with sufficient land, seed,
   work, storage, and no shock produce zero basic-meal deficits, zero human
   starvation deaths, and enough seed for the next cycle without recurring gifts.
2. **Opening-stock sensitivity:** run identical committed crops with 0.5×, 1×,
   and 2× pantry endowments. Harvest does not change merely because pantries
   differ. Low reserves may cause a real early gap; high reserves cannot conceal
   a structural deficit in the outlook.
3. **Productivity and specialization:** with land, weather, and inputs held
   fixed, installed labor-saving equipment allows less farm work to achieve
   the same harvest; a yield technology increases its specified potential.
   Subsequent labor reallocation must be feasible and still feed households.
4. **Livelihood inertia and recovery:** comfortable farmers stay despite much
   higher industrial returns. Persistent deficits/short runway trigger search,
   and meal failure or lost livelihood triggers immediate consideration, still
   subject to career budgets and real destinations. Non-harvest cash-flow gaps
   do not wrongly classify a viable grower as bankrupt. A temporary harvest
   shift preserves the primary trade. Missing planting windows delays new
   crops; existing crops can hire harvest help.
5. **Access failure:** adequate local food plus unaffordable prices causes an
   access warning. Funded wages or targeted transfers repair access if sellers
   and delivery capacity exist; printing a purchase order cannot fix no supply.
6. **Distribution failure:** distant surplus cannot feed a blocked destination
   immediately. A funded, traversable shipment improves access only on arrival.
7. **Policy choice:** withheld public grain remains physically present but
   inaccessible; an authorized release transfers stock and improves meals.
   An empty treasury or granary constrains the response.
8. **Real crop failure:** drought, lost seed, missing work, or destroyed storage
   can cause scarcity and deprivation. Relief succeeds only with sufficient
   reachable food and resources; there is no guaranteed crisis rescue.
9. **Commons and movement:** an employed household with a meal gap can gather
   locally using actual work time. Commons-fed households retain viable trades.
   Closure with no local alternative prompts nearby subsistence migration;
   destination crowding and travel costs bind. The same scenario with a
   restrictive enforced movement policy shows deterred/blocked moves and their
   deprivation consequences, with no invented food or disappearance of people.
10. **Specific technology:** an unrelated steam engine does not raise crop or
    artisan output. An implemented compatible machine improves its specified
    task and consumes its specified operating inputs. No universal multiplier
    survives cutover.
11. **Actionable support metrics:** farm capacity includes farmers' own meals;
    subtract those requirements before displaying support for other residents.
    Counts are age-adjusted and season-matched. Food processing, seed, losses,
    and exports are counted once. A non-harvest turn with adequate carryover
    does not trigger an erroneous farmer-recruitment recommendation.
12. **Cross-profession response:** identical food gaps caused by missing labor,
    iron tools, or purchasing power produce different diagnoses/actions. A
    funded iron contract consumes treasury funds only under its declared terms,
    requires physical deliveries, and does not relabel comfortable workers.
    Unaffordable programs cannot run; quantity caps and expiry prevent support
    accumulating indefinitely after a shortage ends.

### Campaign validation

Rerun the established 18-case, three-seed 100-turn matrix at one source version.
Update opening states explicitly and archive them, so comparisons distinguish
the opening endowment change from the new dynamics. Also run the default
multi-nation world and the authored Egypt scenario to exercise institutions,
cross-region ordering, seasonal claims, and transit. Extend selected balanced
and stressed cases to 300 turns to expose depletion, debt, and population effects.

Report each ten-turn cycle: ordinary calorie needs and actual intake, deficits
by household, human starvation deaths, production by source, stocks by owner,
spoilage, planted/harvested area, seed renewal, effective farm work, primary
professions, paid food prices, real food purchasing power, trade, relief,
technology operation, pollution, and all accounting residuals.

Release gates are zero unexplained accounting/identity residuals, all controlled
causal checks passing, replay parity, and working desktop/web explanations.
Balanced fixtures must replenish themselves. Stress campaigns need honest
causal diagnoses, not a universal zero-death target. Keep the old campaign
results as historical evidence; do not retune the new model merely to reproduce
their farmer counts or prices.

## 13. Save and scenario migration

Version the food schema and require explicit opening declarations for updated
scenarios. Preserve stable commodity IDs and historical trace readers.

For old saves, migrate only facts that exist: physical stocks and locations,
households, rights, debts, known assets, and queued shipments. Do not invent a
free standing crop or retrospectively earned harvest to make the conversion
comfortable. Produce a migration outlook and warn in the loading UI if missing
crop/work history makes the converted world distressed. Preserve the original
save, and offer a new campaign as the supported balanced starting point.

Any compatibility adapter must translate data at load or a primitive API
boundary. It must not restore the old behavioral rules. The finished system
has one authoritative food economy.
