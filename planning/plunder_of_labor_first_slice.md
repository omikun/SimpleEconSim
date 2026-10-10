# First slice: Labor, Territory, and Rivalry

Status: implementation plan, 2026-10-10. This specializes [the AI and UI plan](plunder_of_labor_ai_and_ui_plan.md) around the player's stated strategic tension. Proposed numbers are tuning inputs, not historical estimates. Implement S0–S6 in order and commit after each gate. The deliverable is a complete small scenario playable in web and desktop.

## 1. Player promise and completion target

**Expand production, labor control, and territory enough to compete with a neighboring state, while deciding what costs your citizens will bear.** Private owners seek profitable labor arrangements; the player needs actual public receipts, supplies, and people to maintain a capable state. The rival pursues the same opportunities with its own finite resources. Livelihood protection, industrial investment, coercion, military spending, territorial expansion, and diplomacy compete for money, goods, time, and political support.

The 20-turn prototype must let the player experience this chain in either direction:

`labor/access policy → staffing, food and production → paid sales and owner profit → actual tax receipts → funded military readiness → border leverage or territorial change → new resources, residents and costs`.

Every arrow needs an actual operation or measured flow. Firm wealth does not become treasury money automatically, and possession of a district does not immediately create tax receipts. The player may also break the chain through negotiation, productivity investment, restraint, or a successful defensive posture.

Completion requires one playable run with a real domestic choice, a rival economic response, a credible military opportunity/threat, and an observable consequence for livelihoods. Multiple branches must be possible, but no specific run is forced to contain a war or an eviction. A successful policy can remain successful.

## 2. Bounded world

Create a distinct `labor_frontier_rivalry` scenario using the existing Empire of Cotton setup patterns and shared scenario interpreter. Use fictional country/district names. Keep the existing Egypt and Empire of Cotton scenarios selectable and unchanged in purpose.

| Element | Initial scope |
| --- | --- |
| Countries | Player state and one AI neighbor, both with governments, private owners, ordinary citizens, and real tax/payroll accounts. |
| Map | Four adjacent land districts in a line: player capital → player cotton/food borderland → rival cotton/food borderland → rival capital. Borders and routes are visible. |
| Territory | Each borderland is inhabited, productive, owned, and defended or defendable. It can change control through the actual war/settlement path. No empty frontier windfall. Capitals cannot be conquered in this slice. |
| People | Start around 40 adult citizens per country plus existing organizational actors; initialize a small unit from those people. Keep living person IDs through enlistment, discharge, capture outcomes, and migration. Tune the count only if the fixture requires it. |
| Production | Food and cotton in borderlands; cloth in capitals. Reuse inputs required by the selected machinery recipe. No new goods or technology tree. |
| Money | One common fixture currency to isolate production, fiscal, and military effects. Both nations' balances remain independent. No FX or credit expansion feature in this slice. |
| Markets | Existing funded buyers and trader routes in the two capital markets buy delivered cloth from either nation. Measured market share is actual paid cloth receipts/units by origin. |
| Labor conflict | One targeted gathering-restriction petition affecting named commons-food rights in the player's borderland; the rival may use the same operation. No new catalog of force regimes. |
| Productive alternative | One available machinery improvement or repair with its actual inputs, owner contribution, cash recipient, and completion time. |
| Military | Small paid and fed land units, one-step adjacent movement, existing battle resolution, and a narrow occupation/control rule for border districts. Equipment quality initially fixed; no arms industry or fleet. |
| Diplomacy | One bilateral border standstill/non-aggression proposal with acceptance based on interest and credible force. Trade continues only where route and treaty rules allow it. |
| Horizon | 20 turns for the playable scenario; 30 turns for the engineering sanity run. Endings include future upkeep and outstanding commitments. |

The player starts with more protected commons and a slightly higher delivered cloth cost; the rival begins with a modest industrial advantage and finite fiscal/military reserves. Neither can initially afford every investment, full relief, and an expedition at once. Set the initial lead and reserves using measured baseline turns: target enough reserves for roughly four existing-unit payrolls plus one meaningful intervention, with recurring revenue capable of changing that runway. The player must have a viable opening before the rival could attack. These are tuning conditions, not a guarantee of equal outcomes.

Buyers have actual cash, desired quantities/inventory limits, and maximum prices. Their budgets are part of the initialized money stock; never replenish them for free. Delivered offers compete in the existing market clearing process. If cloth use is absent, add explicit documented consumption or allow inventory saturation to reduce demand. A sale transfers real cloth and money; transport and taxes have recipients. Use foreign-origin sales receipts, rather than cloth inventory on a tile, to measure import competition.

## 3. The first decisions

Expose choices contextually in the existing one-major-decision-per-turn scenario budget. Inspection and normal payroll/standing policy execution are free of click costs. Rejecting a pending proposal uses the same budget rule as approving it; its deadline must allow a response. A physical movement, investment, recruitment order, law decision, or relief operation consumes the budget even if issued through Advanced UI. Waiting is available and does not secretly grant the AI extra resources.

| Action | Required operation | Strategic consequence visible to the player |
| --- | --- | --- |
| Approve targeted gathering restriction | Employer pays petition fee; player authorizes named target rights; a funded officer closes usable access after a visible implementation window. | May increase wage seeking and reduce labor cost, but can reduce food access and increase public enforcement expense. Hiring still requires a funded offer and worker acceptance. |
| Protect access / reject petition | Deny the proposal or suspend/repeal its operation; physically restore only the rights this restriction changed when enforcement is withdrawn. | Keeps a livelihood option and may leave vacancies or higher required wages. Does not give a free production bonus. |
| Back a productive labor agreement | Owner and workers accept funded wage/terms; optionally co-fund the one machinery project through a named supplier. The contract and project are distinct commitments even if presented together. | Costs more now and takes time; may lower cost per unit through productivity/retention while preserving access. Either side can refuse terms. |
| Release food relief | Transfer a finite reserve to eligible people and consume it once through existing nutrition logic. | Protects livelihoods and bargaining power but reduces the reserve available for troop supply and later shortages. |
| Recruit or reposition | Enlist eligible willing citizens at a funded offer, or move existing units along a valid edge; update civilian availability. | Improves deterrence or enables expansion while consuming cash/food and reducing civilian labor supply. No free recruitment-based reduction in protest. |
| Declare limited war / take a border district | Announced war and legal movement/battle through existing intents, followed by actual control and administration. | Gains or loses a productive district with its people and liabilities; casualties, interrupted trade, and garrison supply may outweigh receipts. |
| Propose border standstill | Existing diplomacy entry point with an explicit acceptance/rejection result; record duration/review terms supported by the engine. | Can release funds for industry or livelihoods, but the neighbor accepts only if its alternative is less attractive. |

Keep factory wages and routine private investment under owner AI. The player can propose/co-fund terms and choose public policy, but does not freely dictate every private offer. No separate tax slider is added for this first slice: use a visible fixed scenario tax rule and real collection, reducing the number of new controls. The broader plan can later introduce more fiscal bargaining.

## 4. Three AI decisions, connected by evidence

**Owner:** compare better wages/terms, machinery, petitioning for the targeted restriction, and contraction/waiting. Use settled cash records, expected saleable output, finite buyer demand, and observed hiring results. Read the rival's competition through lost sales/delivered prices. Use one persistent goal such as retaining a buyer or restoring payroll runway. Pay private costs from private balances; a public enforcement subsidy remains visible in the public ledger. Record failed petitions and new terms instead of resubmitting identical requests every turn.

**Household:** compare usable food access, stocks, actual cash obligations, and funded wage offers. Someone can refuse, accept, leave under actual contract rules, or qualify for relief. Enlistment is another funded occupation with its own eligibility; it cannot coexist with a full civilian workday. The first slice represents people and existing work/food decisions; do not claim a complete family/care model.

**Rival state:** maintain one plan—industrial investment, hold/fortify the border, limited expansion, or a standstill. Choose using its own treasury and food runway, measured market position, domestic food/unrest, and the local deployable force balance. Reconsider on project completion, lost sales, supply failure, or a changed border. It can use the same permitted domestic labor policy, with costs and affected citizens. One government strategic action per turn plus ordinary operations, matching the player's decision bandwidth.

Economic strength influences military opportunity only through actual funds, people, and provisions. Expansion assessment compares expected district receipts/resource access with recruitment, supply, likely losses, occupation, and domestic instability. National army totals are insufficient: forces must be able to reach the target and remain supplied. A rival can decline war despite numerical superiority, or abandon an expedition it cannot sustain. Announcements should expose visible preparation and provide at least one full player response opportunity before first hostile entry in this prototype. This is a declared operational rule for mobilization, not a scripted invasion countdown.

## 5. Territorial control and military conservation

Use the existing `RecruitArmyIntent`, `MoveArmyIntent`, `DeclareWarIntent`, `army.resolve_battle`, and `Nation.transfer_tile` seams after the focused repairs below. A unit tracks enlisted person IDs; recruitment changes availability, payment reaches those people, and desertion restores surviving people to civilian life rather than creating new agents. Keep casualties and estates consistent with the existing death/probate system. Count rations and personal consumption once.

A supplied attacker can take a border district only after the actual battle or accepted territorial settlement. Record control and sovereignty/administration status separately if a provisional occupation is used. For this slice, direct transfer may occur on secured conquest under an explicit scenario rule; the UI must say which status actually changed. Reconcile nation/tile membership, tax recipient, units, citizenship, treasury references, and claims through one authoritative transition. Protect existing cash/inventory balances; the common currency removes conversion ambiguity.

Acquisition preserves the district's residents, stocks, obligations, and rights until a separate supported action changes them. It does not automatically evict everyone, hand the occupier all private wealth, or fill factories. Record grievances from actual battle, dispossession, and disrupted supply through existing mechanisms. Require recurrent garrison pay and food from a reachable friendly/treaty supply path; withdrawal can expose the district to recapture. Both sides can seek peace. Losing a border district continues play with fewer resources and a visible recovery/settlement opportunity.

## 6. Reuse and prerequisite audit

These are findings from reading the current code, not claims that a new scenario already works.

| Current seam | Reuse | Required check/repair for this slice |
| --- | --- | --- |
| `scenario_empire_of_cotton.py`, its JSON template | World construction patterns, interpreter binding, actor naming. | Its frontier reaction announces conquest after a delay and its outcome can declare hegemony from mill/cotton totals. New scenario uses actual contests and relative outcomes. Keep a separate template/ID. |
| `scenarios/modules/capitalism.py`, `micro/region/stepper.py` | Existing production/labor operations and metrics. | Both contain planner/mobility/machinery stepping. The new scenario must use one authoritative world economy tick and never run either subsystem twice. Do not treat aggregate reserve fields as independent goods. |
| `economy/geopolitical_rivalry.py` | Rival posture labels and decision visibility. | Existing emulation creates a firm with cash without a matched debit, and cloth holdings proxy imports. Replace the invoked path with funded investment and actual sales data; do not copy these shortcuts into the new scenario. |
| `ai_nation.py` | Terrain valuation, vulnerability and sovereign intent generation. | Add a bounded scenario policy profile so the rival has one decision owner. Use local reachable supplied strength, fiscal runway, and shared market evidence. Disable competing autonomous planners for these same decisions. |
| `army.py` | Unit strength, morale, upkeep, battle model. | Recruitment currently adds unit counts without binding/removing civilian availability; desertion creates new people. Trace payroll debits to real payees; complete enlistment, pay, supply, death/discharge handling for this scenario's units. |
| `intents.py`, `diplomacy.py`, `nation.py` | Validated actions, treaty/war state, territory transfer. | Enforce the shared action budget and once-only execution. Check transfer updates the tile's active government/tax recipient as well as its lists and ownership fields. |
| `region_market.py`, `world_trade.py`, `region_finance.py`, `sim_engine.py` | Real settlement, trade, tax and world audit. | Attribute delivered sales by origin and reconcile private revenue → tax payment → treasury. Same buyers cannot pay twice through a scenario overlay. |
| `labor_laws.py`, `labor_cases.py`, `livelihood_access.py` | Petition, law, rights, and claims. | Target the restriction to named rights, add a response/implementation delay and real officer budget, preserve baseline rights for repeal, and close invalid pending operations. |
| Server/client scenario integration | Existing command protocol, Guided cards, map/inspection and debrief. | Current desktop setup contains Egypt-specific routing. Register the new scenario on both clients explicitly; a passing headless runner does not establish that it is playable. |

Use a scenario-scoped adapter for a bounded new rule where appropriate. Fix shared conservation/identity bugs in the authoritative helper when needed, with regression checks for its existing callers. Do not duplicate an economy or military ledger to avoid a broken integration.

## 7. UI: three pressures and a connected map

The default screen shows the mandate and turn, then three expandable cards:

1. **Livelihoods:** adequately fed residents, usable commons access, paid hours/real pay, and the most affected group. Include affected people across acquired territory; pin the starting citizen cohort to expose losses hidden by changing denominators.
2. **Economic position:** player/rival delivered cloth price and paid market share, firm margin, public receipts, treasury runway, and committed projects. Explain whether the current disadvantage is labor, inputs, transport, productivity, or buyer demand.
3. **Border power:** reachable supplied forces, food/payroll runway, treaty/war status, territory, and the rival's visible preparation. Show force estimates and supply limits rather than a single unexplained threat meter.

Each card leads to feasible decisions with costs, timing, uncertainty, and competing uses of the same reserve. For example: `Relief can feed 8 residents; it uses food currently sufficient for two turns of the border unit's rations` only when derived from the actual quantities and ration rules. A petition card might say `The mill seeks cheaper labor after losing cloth orders. The state would pay patrol costs; the owner retains the wage saving.`

The four-district map shows ownership, meaningful trade routes, units, the targeted commons, and threatened/acquired borderland. Selecting a district explains what it supplies, who lives there, and what changes if control is lost. A short linked timeline connects a player's choice to a household, firm, fiscal receipt, rival response, or border event. Separate forecasts from transfers and observed changes; do not attribute an entire military outcome to a single wage decision.

Web and desktop use the same action IDs, deadlines, state/status vocabulary, and server/domain validations. Analysis holds detailed actor plans and books. The debrief compares both countries and reports territorial/economic gains, human costs, sustainable readiness, and unresolved commitments. It may describe secure prosperity, costly dominance, protected but dependent livelihoods, overextension, or territorial retreat only when metrics support those descriptions.

## 8. Implementation sequence and commit gates

### S0 — Register a deterministic scenario and prove one turn path

- Add proposed `scenarios/templates/labor_frontier_rivalry.scenario.json` and a thin `scenario_labor_frontier_rivalry.py` adapter. Seed the four districts, both governments, rights, firms, buyers, real citizens, reserves, and connections once. Use existing setup/registry entry points; add missing routing for both clients.
- Trace the actual desktop, server, and headless tick and choose a single owner for economy, trade, AI, army, and scenario presentation. The interpreter schedules decisions/reads results; it does not repeat production or labor. Start with rivalry disabled until accounts are wired.
- Gate: scenario is selectable and renders in both clients; one step runs each subsystem once; baseline cash/goods/person IDs are recorded; no legacy free frontier event or early cotton-hegemony ending is inherited.
- Commit: `Add bounded labor and frontier rivalry scenario`.

### S1 — Connect markets, private profit, and public capacity

- Instrument actual cloth deliveries and payments in existing market/trade settlement; add per-firm settled statements and per-nation real receipts. Configure funded buyers and demand bounds. Snapshot public commitments and food/payroll runway.
- Route the selected investment through actual owner/public funding and supplier/building operations. Reuse available production recipes; if a machinery operation produces goods or capacity without proper inputs, repair that invoked path before enabling it.
- Gate: a rival's cheaper available delivered cloth can win an order; unavailable cheap cloth cannot; unsold output is not revenue; private profit does not increase treasury before a tax/transfer; buyer balances and received lots reconcile. No AI action grants a free mill.
- Commit: `Link export competition to firm and treasury receipts`.

### S2 — Deliver the domestic labor choice and its counterplay

- Extend the shared owner planner with the limited candidate set and a persistent retain-buyers/payroll goal. Read last settled statements. Ensure wage changes cannot be overwritten by legacy adjustment in the same turn and that workers compare offers on the same effective date.
- Implement the targeted gathering petition, player/rival-government decision, paid patrol and reversible effect on the named rights. Provide funded better terms, the selected machinery alternative, and actual grain relief. Preserve worker acceptance and no-vacancy behavior.
- Gate: the same owner can choose higher pay, investment, petition or contraction in different cases; refusing/undoing pressure has a real effect; target households may still refuse bad offers; loss of access and any resulting pay/food changes appear in records; public and private costs reconcile.
- Commit: `Add competing labor strategies and funded player responses`.

### S3 — Make military strength use real people, pay, and food

- Add enlisted IDs/occupation exclusion to the active unit path. Update recruitment, wages, rations, desertion/discharge and casualty identity handling in `army.py` and callers. Reuse existing alive/person and probate bookkeeping; prevent simultaneous civilian production, foraging and troop service.
- Support adjacent movement and simple reachable supply through owned/treaty districts. Keep equipment fixed and use existing battle strengths. Ensure a unit is counted consistently in nation/tile lists and paid once per turn.
- Gate: recruiting reduces available civilian workers; payroll credits real recipients; rations consume real stock once; unpaid/unfed units weaken; desertion creates no people; casualties do not erase cash or inventory outside the documented death/estate path.
- Commit: `Conserve military manpower payroll and supply`.

### S4 — Connect rival strategy to limited territorial competition

- Add the bounded rivalry policy to `ai_nation.py` or a scenario-specific policy adapter, feeding existing intents. It reviews investment, defense, expansion, domestic labor policy, and standstill using the same budgets as the player. Retire competing rivalry behavior for this scenario.
- Implement visible mobilization, war/movement, border-only contest, validated control transfer, recurrent supply, and peace/standstill. Both player and rival can initiate expansion. The opportunity is conditional on resources and the defender's reaction.
- Gate: richer private owners alone do not spawn armies; an insolvent/unsupplied rival can postpone expansion; a costly expedition can reduce industrial capacity; funded deterrence or mutually useful diplomacy can avert attack; territory transfer preserves residents/assets and changes actual fiscal control once.
- Commit: `Connect national rivalry to funded border expansion`.

### S5 — Complete the player loop on web and desktop

- Add authoritative scenario commands/projections in `sim_server/` and the shared scenario action layer. Enforce one action budget across the interpreter, intents, legacy controls, and both clients. Disabled actions explain the unmet resource, jurisdiction, timing, or target condition.
- Build the three pressure cards, contextual actions, map markers, limited warning pauses, actor/household drilldown, and comparative debrief in `web_client/` and `client/desktop/panels/scenario_ui.py` with existing inspect panels. Save pending proposals, plans, treaties, and response windows.
- Gate: the player can follow the complete domestic → economic → fiscal → border chain and take every authorized response on either client; numbers are consistent, targets outside sampled citizen lists remain inspectable, and no sidebar bypass gives an extra action.
- Commit: `Expose labor livelihood and border tradeoffs in both clients`.

### S6 — Verify strategies and run the playable slice

- Add proposed focused tests in `test_labor_frontier_rivalry.py` using the production tick. Cover protected investment, owner-backed restriction/expansion, defense/diplomacy, and passive decline/failed expansion. Use the same seed and buyers for comparative runs; confirm different outcomes follow actual decisions.
- Exercise the causal chain in both directions: domestic policy affects saleable production and public capacity; rival competition changes owner incentives; mobilization changes labor/food availability; acquisition adds receipts and costs. Also test enough demand for humane investment to succeed, and a case where coercion benefits its sponsor while public/household losses remain visible.
- Run the focused existing labor, scenario, trade, diplomacy and military regressions identified by changed callers, then a 30-turn conservation/person/contract/supply audit and one save/load round trip. Smoke-test both UIs; test mobile/keyboard essentials and response deadline preservation. Broaden testing only for remaining concrete risks.
- Conduct a short formative playtest when people are available: can they explain the objective, the rival's advantage, the public/private distinction, two feasible responses, and one tradeoff they would replay differently? Record missing human feedback as unvalidated; do not substitute a successful automated run for enjoyment.
- Gate: no free cash/goods/people, duplicate tick, automatic conquest, fixed-date invasion, or forced welfare collapse; both nations can pursue and pay for credible strategies; at least two context-dependent player approaches work in tested starts; player feedback supports continuing or identifies a specific redesign.
- Commit: `Validate the labor and frontier rivalry playable slice`.

## 9. Acceptance examples and scope stop

The first release must demonstrate these **fixture outcomes**, not force all of them into one playthrough:

- **Protect and compete:** a funded productivity/terms path preserves usable access while retaining enough sales and defense capacity to hold the border.
- **Exploit and expand:** restricting access can improve an owner's margin and permit greater production; only actual public receipts finance further strength. Expansion can gain a district, with tracked human and recurrent costs.
- **Overextend:** recruitment draws too many workers or reserves from production/food; an initially stronger force becomes unsustainable and must withdraw or accept terms.
- **Fall behind and adapt:** lost orders reduce receipts, producing a visible defense problem; investment, a defensible position, or accepted diplomacy offers a response before loss becomes unavoidable in that fixture.
- **Rival restraint:** the neighbor sees insufficient gain or supply, chooses industry or a standstill, and does not invade merely because the scenario reached a particular turn.

Stop scope at two countries, one cross-border market competition, one pressure mechanism, one productive alternative, one land front, and one treaty family. Leave new debt traps, cartels, navies, multiple alliances, arms industries, covert action, and other historical labor mechanisms for later slices. Preserve the wider mechanism registry as future work. The first milestone succeeds when protecting livelihoods, expanding extraction, and keeping pace with a rival are connected choices the player understands and wants to explore again.
