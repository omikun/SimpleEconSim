# Gameplay streamlining audit

Branch: `feature/streamline-gameplay`, based on squashed `main` (`c2a1472`).
Worktree: `/private/tmp/coc-streamline`.

Status: all 46 gates reviewed and refactored, with one commit per gate.
The existing central GameplayFlags configuration remains authoritative.

## Purpose and method

Reduce the amount of code and the number of implementations needed to express
one game rule. Moving a large function into another file is not a reduction by
itself. DRY means one authoritative rule; many wrappers, generic frameworks, or
parallel implementations can still make that rule harder to find.

For each gate, in the order below:

1. Follow production entry points, commands, direct callers, and scenario paths.
2. Identify the state owner and all writers, including accounting and tracing.
3. Compare repeated calculations by behavior, not just similar names or syntax.
4. Classify each candidate as shared rule, separate policy, compatibility entry
   point, disconnected implementation, or observation-only code.
5. Consolidate one confirmed duplicate at a time. Preserve random call order,
   amounts, rounding, event causes, and disabled-state contracts.
6. Check relevant existing tests and old/new outputs. Record baseline failures.
7. Commit the feature slice and its evidence before starting the next gate.

Do not merge separate simulation models merely because they use the same words.
Do not delete disconnected code until its intended public behavior is resolved.
Avoid adding a framework to replace two small, readable pieces of code.

## Initial evidence

Counts below are tracked Python files and physical lines at `c2a1472`, not
executable statements or a claim that all these files are active:

| Area | Files | Lines |
| --- | ---: | ---: |
| Tests | 234 | 49,587 |
| Clients | 98 | 43,077 |
| Micro simulation | 64 | 21,589 |
| Economy | 36 | 16,998 |
| Scenarios | 34 | 14,809 |
| Macro simulation | 25 | 14,658 |
| Terrain | 34 | 11,097 |
| Tracked tmp experiments | 109 | 9,498 |
| Trace | 35 | 8,164 |
| Tracked scratch experiments | 25 | 3,928 |

An AST comparison of function bodies, excluding docstrings and functions shorter
than 16 lines, confirms exact copies across desktop and worldview clients:

| Function | Locations | Lines per copy |
| --- | --- | ---: |
| `_get_stat_breakdown` | `client/desktop/hud/ui.py`, `client/worldview/worldview_ui.py` | 336 |
| `draw_help` | same two files | 278 |
| `_draw_city_policies` | `client/desktop/panels/policies.py`, `client/worldview/worldview_policies.py` | 209 |
| `draw_innovation_tab` | desktop/worldview actions | 150 |
| `draw_transfer_dialog` | desktop/worldview transfer dialogs | 135 |
| `_draw_nation_policies` | desktop/worldview policies | 132 |
| `transfer_dialog_hit` | desktop/worldview transfer dialogs | 110 |
| `draw_diplomacy_tab` | desktop/worldview actions | 109 |
| `draw_construction_tab` | desktop/worldview actions | 106 |

These are confirmed copies, but which entry points remain supported and how
module state is shared still need investigation. Do not assume the older client
is unused. Audit the relevant UI alongside each owning mechanism below.

## Gate inventory and audit queue

These are all 46 fields of `GameplayFlags`, in central-config order. The questions
are investigation targets, not findings. Progress and evidence for completed rows are recorded below.

| # | Gate | Owning path to start from | Investigation target |
| ---: | --- | --- | --- |
| 1 | `nation_ai` | `core/sim_engine.py`, `macro/ai_nation.py` | Repeated score rules, disconnected planners, decision vs trace bulk; first reduction complete |
| 2 | `construction_projects` | `macro/intents.py`, construction/buildings | Public/private/scenario execution and repeated project lifecycle rules |
| 3 | `private_technology_adoption` | `economy/technology_adoption.py` | Shared construction commissioning vs separate investment policy |
| 4 | `wage_quotes` | `micro/region_labor.py` | Quote adjustment vs payroll and duplicated labor calculations |
| 5 | `trade_epidemic_spread` | `micro/disease.py`, engine | Shared exposure/infection rules vs local transmission policy |
| 6 | `migration` | `meso/migration.py` | Planning, arrival, agent transfer and household accounting |
| 7 | `frontier_claims` | `micro/claims.py` | Province founding, membership and ownership transfer copies |
| 8 | `regime` | `macro/regime.py` | Repeated political state and legitimacy calculations |
| 9 | `military` | `macro/army.py` | Recruitment, upkeep and direct client command implementations |
| 10 | `wars` | `macro/war_logic.py` | Combat/occupation lifecycle overlap with scenarios |
| 11 | `diplomacy` | `macro/diplomacy.py` | Direct client actions vs authoritative server commands |
| 12 | `innovation` | `macro/innovation.py` | Discovery, refinement, project effects, duplicated UI |
| 13 | `popular_resistance` | engine, political resistance | Overlap with factions, unrest and collective action |
| 14 | `imperialism` | engine, imperialism | Ownership/control mutations vs war and scenario systems |
| 15 | `sovereign_bonds` | bonds, server turn pipeline | Repeated treasury transfers, issuance and UI handlers |
| 16 | `scenario_progression` | server hooks, scenarios | Shared scenario transitions vs authored content |
| 17 | `workhouse` | `micro/workhouse.py`, health phase | Inmate state, labor allocation and household meals |
| 18 | `elite_planning` | capitalist planner, opening phase | Overlap with private adoption, production policy and nation AI |
| 19 | `career_mobility` | career transitions, demographics | Multiple hiring/switching entry points and legacy schedulers |
| 20 | `workplace_resistance` | labor resistance, collective action | Strike membership, withheld work and review duplication |
| 21 | `foraging` | foraging, work allocation | Regional/wilderness resource and work calculations |
| 22 | `wilderness` | terrain wilderness | Separate turn loop vs shared household and food rules |
| 23 | `feudal_tribute` | tribute, harvest claims | In-kind transfers vs tenancy and crop liens |
| 24 | `abundance` | `economy/abundance.py` | Alternate production rules and duplicate skill accumulation |
| 25 | `national_food_logistics` | food logistics | National targeting vs provincial transfer implementation |
| 26 | `food_spoilage` | food economy, food storage | Stock pools, fractional losses and storage ownership |
| 27 | `food_relief` | province, food logistics | Delivery/levy/dispatch vs emergency and scenario release |
| 28 | `household_food` | households, consumption | Repeated meal demand/allocation/consumption calculations |
| 29 | `taxation` | region finance, government | Fixed/income taxes, assessment, transfer and trace copies |
| 30 | `profits` | region finance | Dividends, salaries, debt repayment and bailout ownership |
| 31 | `household_lifecycle` | lifecycle, demographics | Birth/death/estate cleanup across local and wilderness turns |
| 32 | `local_market` | region market, auction | Separate clearing flows and repeated food purchase logic |
| 33 | `labor_market` | region labor | Hiring, firm emergence and existing career wrappers |
| 34 | `wages` | region finance, labor contracts | Payroll, arrears, scrip and duplicated settlement paths |
| 35 | `production` | agriculture, region production | Independent/corporate/workshop paths sharing the same rules |
| 36 | `independent_input_requests` | region logistics | Corporate vs artisan demand calculations |
| 37 | `forex` | forex modules | Quotes, conversion, reserve and wallet accounting |
| 38 | `regional_trade` | trade flow, routes, settlement | Bilateral/wilderness trade and duplicate inventory transfers |
| 39 | `land_rent` | land rent, livelihood access | Shared obligations vs separate rent assessment logic |
| 40 | `crop_credit` | crop credit, harvest claims | Advances, liens, offtake and common settlement rules |
| 41 | `crop_share_tenancy` | crop credit, harvest claims | Harvest entitlement calculation vs credit-specific policy |
| 42 | `alienation` | agents, alienation | Shared health/wear attributes and duplicate updates |
| 43 | `pollution` | externalities, pollution response | Exposure, emission and collective response ownership |
| 44 | `disease` | disease, medical care, demographics | Disease progression, treatment and cause-of-death calculations |
| 45 | `factions` | region factions, collective politics | Parallel organization/membership/loyalty state |
| 46 | `unrest` | agents unrest, political shocks | Overlapping grievance, protest and revolt transitions |

## Feature 1: nation AI

Production path: `step_turn` checks `nation_ai`, invokes `ai.decide_turn`, then
`production_policy.decide_nation`. The latter funds bounded production programs;
it is a separate policy from strategic intents, not a duplicate implementation.
AI assignment in `SimServer._configure_nation_ai` chooses which nations are
controlled; it does not execute a second turn.

Findings:

- `_bottleneck_relief_breakdown` repeated the same price/productivity gate and
  trace-field construction for food and wood, with different constants. It now
  uses one explicit two-row rule loop. Formula, strict thresholds, absent-value
  behavior and all trace field values are preserved. This removes 27 lines.
- `evaluate_expansion` is about 197 lines, plus its terrain/valuation helpers.
  Repository call-site search found callers only in tests. `decide_turn` does
  not call it, and no production caller of its public scoring APIs was found.
  This is a disconnected implementation candidate, not evidence that frontier
  claims are duplicated: claims use settler majority, a different rule.
  Keep this visible pending a decision about whether expansion planning is a
  supported future feature or obsolete API; silently wiring it in changes play.
- Much of the class constructs explanatory trace dictionaries. Those fields
  have formula/causality consumers and tests. Replacing them with a generic
  event framework or deleting them would need evidence beyond line counts.
- The desktop/worldview copies are a larger confirmed duplication source than
  this first simulation calculation. Inspect caller ownership per mechanism.

Validation: 1,946 old/new result dictionaries matched exactly in a differential
check covering prices, exact price/productivity thresholds, multi-tile means and absent
recipe/owned-tile cases.
Seventeen of eighteen existing focused expansion, decision-gate, diplomacy
trace and M5 scoring/defense tests passed. The failing diplomacy trace assertion
expects only the diplomacy cause ID, while the result also includes a border
vulnerability ID; reproduced identically on clean `main`. No change to that
unrelated assertion or causal behavior is included.

The remaining completed reviews follow in central-config order.

## Feature 2: construction projects

Public builds and private adoption already share `ConstructionProject.step`;
scenario strategic projects also encode authored political effects, so they are
not interchangeable with physical construction. `Intent.step` duplicated the
execution/result event path for already-approved and newly-approved commands.
Those paths now converge after the approval transition. The pending countdown
still waits until the following call after reaching zero; approval/result event
order and execution trace remain intact.

Validation: engineering, contractor subsidy trace, and nation AI intent-gate
tests. See commit for exact scope; project funding and completion rules unchanged.

## Feature 3: private technology adoption

Investment estimates and public construction approval are distinct policies;
private financing still delegates physical completion to ConstructionProject.
Both the decision loop and commissioning guard independently encoded the same
owner/status test. `_has_active_private_project` is now the single rule, retaining
the commissioning recheck because callers can commission directly. Observation
windows, credit terms, recipe quotations, and project ownership are preserved.
Validation: complete technology adoption and engineering suites (34 tests).

## Feature 4: wage quotes

Wage quotes are price-setting, distinct from payroll/arrears settlement. Every
firm recalculated the identical regional reservation wage, and scarcity firms
calculated it again for tracing. Compute it once per wage-adjustment phase and
reuse that value for decisions and evidence. Firm-specific cash, MRPL and legal
caps remain per firm. No RNG or settlement behavior changed.
Validation: 24 old/new wage-policy scenarios matched wages and full trace
dictionaries; all 27 gate contracts pass. The full-world wage regression was
stopped during its second 15-turn setup; its first pastoral-conversion case
passed. The complete slow module is not claimed as passing.

## Feature 5: trade epidemic spread

Cargo contagion and clinical disease onset are separate mechanisms. Loading
probability depends only on source prevalence, but was recomputed per route.
Compute it once per infected source and reuse the source population in tracing;
route iteration, quarantine effects, random draws and infection writes retain
their order. Patient selection still uses the existing global random stream;
changing it to the injected stream would be a behavior change, not deduplication.
Validation: trade-route epidemic tests.

## Feature 6: migration

`run_migrations` plans household travel; `arrive_subsistence_moves` resolves it
and `migrate_one` performs the conserved currency/residency transition. They
are stages, not three competing movers. Removed dynamic Goods imports and an
unused household import; look up the terrain edge manager once per household
candidate search rather than once per neighbor. Destination ordering, legal
checks, household capacity reservations and arrival delays remain intact.
The compatibility `_pick_destination` query is not the full planning algorithm;
no production callers found, so do not silently replace the planner with it.
Validation: food economy v2 household migration and movement-law contracts.

## Feature 7: frontier claims

Claims preserve the majority and force/consent rules; war annexation and AI
expansion scoring are different policies. The same displaced-resident creation
block occurred for the initial local population and refugees unable to leave.
One helper now owns role, currency, memory and agent creation for both. Calls
stay at the same points so seeded trait/ID order and refugee allocation remain
unchanged. Wilderness population reset is now unconditional once after claim.
Validation: coercion/GDD adherence and central frontier gate checks.

## Feature 8: regime

Elections, coups and commune legitimacy use deliberately different eligibility
and support rules; no duplicate regime transition executor was found. Removed
a single-use clamp wrapper and simplified faction support collection, preserving
the same addition order and empty-population default. Retain the early-return
coup/commune paths because they prevent elections after a regime change.
Validation: coup/election decision trace suites.

## Feature 9: military

Concrete personnel and abstract units have distinct recipient accounting and
must retain that distinction. Their wage funding had two identical treasury
debit/trace blocks for sufficient cash versus deposit-assisted payment. Bank
withdrawal is now the optional funding stage followed by one payout/debit path.
Partial payroll, event causes, soldier receipts and abstract-service ledger
sinks are preserved. Validation: military upkeep, medical account, and abstract
military currency audit suites.

## Feature 10: wars

Attack forecasting is a read-only policy input; battle resolution writes real
casualties and territory. They cannot share an executor without changing play.
Forecasts repeatedly scanned war aims and recalculated a fixed supply multiplier
inside target/force loops. Resolve the defensive posture, desired tile set and
supply multiplier once per forecast. Attack order, thresholds and scores stay
unchanged. Validation: war logic and war intent causal trace suites.

## Feature 11: diplomacy

The active model already has one DiplomacySystem; the duplicate is its client
command/view implementation. Compared complete desktop/worldview actions source:
only import routes and a legacy labor-campaign click guard differed. Camera/map
imports already forward to desktop; imported `ticker_push` and `get_font` helper
bodies also match. Replaced the copied worldview actions module with a facade
sharing desktop functions and retaining the scenario guard before dispatch.
This also removes duplicate military/construction/innovation/debt action views,
whose mechanisms remain individually audited in their own rows. No model treaty
rules, selected-nation state, or campaign feedback changed.
Validation: legacy forwarding/guard contracts and diplomacy action trace suite.

## Feature 12: innovation

Discovery/refinement and deployment remain distinct: a discovered technology
does not conjure machinery. Production-based agronomy/manufacturing learning
duplicated the same weighted-sample update and trace sequence. One explicit
domain/weights loop now owns that rule, keeping domain order and floating-point
summation intact. Freight, finance and military learning retain their different
inputs. The copied innovation UI was removed with the actions facade in row 11.
Validation: innovation trace, engineering, and private adoption suites.

## Feature 13: popular resistance

The facade forwards to one manager; factions, collective organizations and
rebellion state describe different stages. Found 18 identical pairs appending
an event to both the turn result and retained history. A small `_record_event`
method now owns that dual publication, keeping the exact event objects, order
and history lifetime. Rebellion stages and their thresholds remain explicit.
Validation: charismatic rebellion, assassination, commune legitimacy and
coercion/GDD adherence suites.

## Feature 14: imperialism

Facade and package share one manager. Reserves duplicated the bond market's
active-holder query; use that authoritative query and retain the foreign-issuer
filter. Debt owed deliberately includes defaults, so it cannot use the market's
active-only liability query. Fused the two-pass unresolved-default filter while
preserving optional-creditor semantics. Enforcement, seizure and revenue
interception are different stages with separate accounting evidence.
Validation: imperial enforcement funding, asset seizure and revenue trace suites.

## Feature 15: sovereign bonds

Public offerings and immediate underwriting have different timing; coupons,
redemption and default also require distinct cash legs. Direct issuance had
identical issuer-credit blocks in foreign-holder and domestic branches. Keep
the holder debit conditional and issue the issuer credit once afterward, with
the same public account trace and causal IDs. Coupon properties are only two
lines each; a new inheritance hierarchy would add more machinery than it saves.
Validation: sovereign bond and bond announcement suites.

## Feature 16: scenario progression

Scenario hooks are authored transitions, not substitutes for the normal engine.
The server duplicated hook invocation and post-hook currency totals for its two
authored rivalry scenarios. Select the hook, invoke once, retain the labor-only
treasury trace boundary, then audit currency once. Disabled and unknown scenario
paths still perform no hook or extra audit. Validation: focused branch/order
checks plus the central gameplay gate suite.

## Feature 17: workhouse

Confinement and meals intentionally differ from ordinary voluntary employment.
Government food purchases repeatedly sorted the same agent list per inmate;
sort once, keeping inventory/eligibility checks live each purchase. Build fed
and starving ID lists once and share them between result and trace. Physical
food transfers, seller order, hearing/release timing and forced labor accounting
remain unchanged. Validation: labor enforcement and coercion/debt suites.

## Feature 18: elite planning

Elite ownership/investment choices and household career moves are different
actors/policies; retained their separate evaluators. Novelty state assignment
was identical in both branches, as was recording the market-novelty gate.
Collapsed those duplicate branches and used the existing defaulted cache pop
directly. The trace still lists exactly the gates actually considered, in order,
and novelty cache invalidation remains turn scoped.
Validation: elite planning gate/novelty trace suite.

## Feature 19: career mobility

The old LaborMobilityScheduler already delegates to step_careers and its
turn guard; it is not a second hiring engine. Preserve that compatibility API.
Removed repeated profession evaluation per adult, duplicate quota rounding,
and two identical post-transition adult scans in the scheduler trace. Frozen
counts, carry, departure quotas and per-person commitments remain owned by
the same ledger. Validation: career transitions and elite gate trace suites.

## Feature 20: workplace resistance

Strike participation delegates to collective action; sabotage/repair are distinct
physical consequences. The workforce trace separately reimplemented its own
availability predicate for the working count. Derive that count from its worker
status rows, preserving strike/revolt precedence. The tile rollup also computed
strikers twice; count the existing live striker ID list once. No sabotage draws,
machinery costs or withholding rules changed. Validation: collective action suite.

## Feature 21: foraging

Wilderness already delegates gathering to the same forage_tile function; there
is one finite-stock/work-budget algorithm. Capacity was calculated for stock
replenishment and again for every gathering receipt. Compute it once for this
turn and reuse it in receipts; harvest order, stock rounding, eligibility and
household work assignment stay the same. Potential subsistence forecasts remain
read-only estimates rather than a second goods-creation path.
Validation: food economy v2 and household food transfer trace suites.

## Feature 22: wilderness

Wilderness already shares food preparation, gathering, household allocation and
mortality functions; its separate loop omits institutions and local markets.
Forcing it through the claimed economy would add fake government/bank objects.
Neutral history alignment duplicated the same eight series for goods and trader
cohorts. Use one ordered cohort pass, retaining good-only price/demand series
and all original integer/float zeros. Validation: wilderness telemetry and
food economy v2 suites.

## Feature 23: feudal tribute

Tribute, crop liens and share tenancy use common harvest availability, but their
claim bases and recipients are different. Collection already builds the live
person ID map for serfs yet linearly searched the same population per landlord.
Reuse that map and remove the single-use lookup implementation. Estate food
relief remains a physical gift before meals, not an inverse tribute transaction.
Validation: tribute trace, feudal subsistence and coercion adherence suites.

## Feature 24: abundance

Abundance workshops transform physical inputs/equipment and household budgets
fund real uses; they are not interchangeable with crop production or elite
capital planning. Workshop work aggregation queried each allocation twice to
implement the legacy missing-budget fallback. main_work now accepts an explicit
keyword default (existing callers still receive None); abundance queries once.
This keeps zero assigned work distinct from an absent turn budget. The shared
API will also remove the duplicate conventional-production fallback in row 35.
Validation: abundance and food economy v2 suites.

## Feature 25: national food logistics

National coordination extends the existing provincial shipment engine rather
than running a second transport simulation. Delivery rebuilt the same national
tile list for every shipment; build one name index per delivery phase. Dispatch
also rebuilt the unchanged province list per hungry destination; hoist that
list while continuing to recompute incoming cargo after each dispatch. Ownership
and currency eligibility are still checked against current turn state.
Validation: economic policy response and provincial relief transfer trace suites.

## Feature 26: food spoilage

Natural decay already has one turn-guarded owner in begin_turn. Raw/prepared
food and farm stores intentionally have different rates and remainder storage.
The repeated-looking rounding truncates losses and carries the remainder; the
shared inventory milli() rounds half-even, so substituting it would change
losses. Retain the explicit small loops instead of introducing account adapters.
Only simplified dependency loading by importing seed reserve once rather than
inside every farm iteration. Capacity overflow remains a separate physical
storage rule. Validation: spoilage stock/remainder gate contract passes.

## Feature 27: food relief

The donor reserve formula was written once when admitting donors and again
when summing collectible levy capacity. Accumulate capacity using that same
reserve during donor selection, retaining donor order, protected household and
corporate inputs, and levy limits. Emergency granary release and shipment relief
have distinct timing/stock owners, so keep their executors separate.
Validation: economic policy response, provincial relief transfer and granary
relief trace suites.

## Feature 28: household food

One household module owns grouping, buyers and proportional meal allocation.
Demand calculated buyer status twice, and allocation reread the same inventory
for totals, donors and recipients before any transfer. Resolve buyer status
once and snapshot each good once per family allocation; transfer ordering and
proportional targets are unchanged. Avoid an unused member set on indexed
queries. Household cash stays individual; no generic pooled-account model added.
Validation: household food transfer, dependent food and food economy v2 suites.

## Feature 29: taxation

Fixed obligations and deficit-driven income taxation are separate assessments;
their shared tax gate must not suppress debt service. Debt service duplicated
loan removal from both borrower and bank ledgers for already-paid versus newly
paid loans. One cleanup path now follows optional service, preserving short
circuiting for already-cleared principal and all debit/trace ordering.
The apparent duplicate policy drawing functions also register hitboxes in their
module's state; importing those functions alone would break legacy clicks, so
that shortcut was rejected. Validation: fiscal policy trace/federalism suites.

## Feature 30: profits

Salary/dividends, owner loan repayment and bailouts already use shared owner
tender settlement. The bailout branches duplicated firm credit, owner-loan
mutation and funding evidence after different owner debits. Keep cash-vs-wallet
debit rules explicit, then converge on one firm funding path. Local meal reserve,
foreign currency eligibility, amounts and original treasury source-writer tags
are preserved. Validation: owner currency transfer and treasury flow trace suites.

## Feature 31: household lifecycle

Claimed and wilderness loops already share consumption/death handlers; the
claimed lifecycle additionally owns welfare, reproduction and estate cleanup.
Resolve the per-run flags once at Live entry instead of interpreting missing
context separately for tribute and then lifecycle/food sharing. Per-agent random
shuffle, mortality/reproduction order and compatibility career calls remain
unchanged. Those calls have a turn guard; moving them before consumption would
change direct Live callers and was rejected. Validation: food intake, dependent
food, estate wealth, and feudal subsistence suites.
Result: 28/29 pass. The heirless-estate fixture's Charity.receive_food signature
mismatch reproduces unchanged on clean main; no estate API changes included.

## Feature 32: local market

Input/business clearing and post-payroll household purchases deliberately use
different timing and budgets. Found an unreachable duplicate household-food
bid branch: the earlier food/noncorporation/nongovernment guard always returns
first. The later food/nongovernment branch can only be a corporation, so remove
its redundant role test and unreachable second household calculation. Kept the
trader path because unusual combined role flags can still reach it.
Validation: market auction, affordability and household food transfer suites.

## Feature 33: labor market

Solvency layoffs, incorporation and career hiring have separate ownership.
Standard incorporation and elite transformation have different funding and
selection policies; merging them without resolving those differences would
change gameplay. Hoist invariant regional food/startup reserve inputs from the
founder loop; keep trait RNG, inventory transfer, financing and founder order
unchanged. The shared career engine remains the only hiring commitment path.
Validation: labor-market gate plus career transition contracts.

## Feature 34: wages

Cash wages, scrip and arrear claims are distinct tenders/obligations and retain
their own accounting. Farm payroll scanned every work-budget person row once
per farm to locate a known employee ID. Read that employee's activity map once
and sum the same employer farms in order. Ordinary payroll now uses the shared
explicit missing-budget fallback added in row 24. Nominal rates, partial cash,
scrip and arrear settlement ordering are unchanged.
Validation: truck/scrip suite and wage-specific plunder-labor contracts.
Result: truck/scrip 3/4 and wage contracts 6/9 pass. All four errors are
fixtures missing region.bank, before the edited payroll logic; each reproduces
on clean main. No bank or scrip behavior changes included.

## Feature 35: production

Corporate shifts, independent work and farm harvests have different capacity,
input and accounting rules. Keep those paths explicit. Corporate effort queried
the same work budget twice per employee; use the canonical missing-budget
fallback from row 24, preserving a current-turn zero allocation versus an absent
budget. RNG draws, fatigue changes and output/input settlement are unchanged.
Validation: collective action, abundance and food economy v2 suites.

## Feature 36: independent input requests

Extracted funded producer demand from the large route-choice routine into
trade_input_demand.input_requests. This gate now has a small, named owner;
route choice retains margin/scoring and evidence publication. Both corporate
and independent requests share input shortage and affordability calculation,
with the independent meal reserve and child/employment exclusions explicit.
No alternate request model or new configuration was introduced.
Validation: economic policy response and trade quarantine trace suites.

## Feature 37: forex

The helper claimed to serve both market-cycle entry points, but the legacy
entry point still copied bidding, matching, reserve filling and stale-order
cleanup. Both now use _cycle_one_desk. Its explicit legacy_repatriation option
preserves the sole difference: legacy converts all listed traders through the
primary desk, multi-neighbor converts locally based traders through that desk.
Also removed one-element-generator sums in sovereign currency audits.
Validation: FX accounting plus both cycle APIs' repatriation/conservation checks.

## Feature 38: regional trade

Active and parked cargo had copied provenance-tuple construction and unlinked
remainder accounting. One _cargo_offers helper now offers a single cargo pool;
pending_imports controls which pools are eligible. Active-before-parked order,
good order, lot order, all provenance fields and legacy inventory fallback are
preserved. Wilderness barter remains separate from currency market settlement.
Validation: market routes, bilateral accounting and wilderness accounting suites.

## Feature 39: land rent

Live turns assess named obligations; the legacy direct collection API still
owns demographic pastoral conversion and remains in use by compatibility tests.
These are not interchangeable rent implementations. Assessment now indexes
live residents once instead of rescanning all residents per named tenant;
legacy collection calculates phase-invariant scarcity and corporate wage inputs
once. Plot/tenant order, rent amounts and conversion/eviction rules are retained.
Validation: obligation payment, enclosure expansion and rent gate contracts.

## Feature 40: crop credit

Advance authorization, fixed-price offtake and fallback liens intentionally
remain distinct. They already share claimable-harvest accounting. Normalize an
advance's lien share once for both claim and fallback contract; resolve contract
unit price once for valuation, affordability and evidence. Remove the unused
local receipt list from lien settlement. Delivery still retires actual harvest
at the inventory boundary, and credit never creates additional crop or cash.
Validation: crop credit accounting and advance/offtake actor contracts.
Result: valid advance and mixed cash/debt-credit delivery contracts pass (2/2).
Both older crop-credit accounting fixtures omit receipt.turn and fail to create
a current harvest; both StopIteration errors reproduce on clean main.

## Feature 41: crop share tenancy

Tenancy grants access and collects in-kind rent; it does not extend credit.
Moved agreement creation and crop-share settlement to the small tenancy module,
with compatibility exports from crop_credit so current clients and gate patches
keep working. The two gates still share harvest_claims, not copied crop-supply
logic. Removed the unused receipt local; evidence, ordering and inventories are
unchanged. Validation: real-harvest share transfer and independent gate contracts;
the two untimed-receipt baseline errors noted in row 40 remain unchanged.

## Feature 42: alienation

Despair's merchant-recipient and treasury-fallback branches copied the entire
cash transfer and journal record. Select the recipient and its original source
writer first, then use one settlement call. Random selection still occurs only
when merchants exist; missing-recipient handling and transfer evidence retain
their prior behavior. Psychological alienation and medical disease remain
separate models. Validation: actor cash reconciliation, entertainment trace and
collective-action suites, plus direct fallback/no-recipient differential checks.

## Feature 43: pollution

Air/water exposure and nutrition-density wear are tile-wide; compute those
components once, then copy the component map for each eligible person. Direct
pesticide exposure versus soil toxicity retains its existing exclusive branch
and component summation order. Production emissions and environmental wear
remain separate from disease onset. Nutrition-related wear also exists in
alienation with different coefficients: that is an existing model overlap,
not a safe behavior-neutral deletion in this refactor.
Validation: pollution output/response suite and threshold/role differential checks.
Result: 324 ecology combinations match main across five actor roles. The
pollution suite passes 8/9; its furniture input-reserve expectation (4 versus 6)
fails identically on clean main in unchanged consumption code.

## Feature 44: disease

Public and private care copied cure rolling, treatment counting, outcome evidence
and attrition recovery. Funding remains explicit in each tender path, followed
by one treatment outcome path with the original payer metadata and public/private
recovery amount. Unfunded diseases still skip cure RNG and retain untreated
consequences. Removed repeated identical payment operation-ID assignments.
Onset, treatment, epidemic routes and pre/post-treatment case counts retain
their separate responsibilities. Validation: medical, untreated disease,
military medical and trade epidemic suites, plus exact state/trace differentials.

## Feature 45: factions

Demand satisfaction repeated assignments across a long name-dispatch chain.
Use one local demand-to-value table, preserving unknown demands and applying
compromise concessions afterward. Grievance calculations reuse their existing
noncorporate/nongovernment cohort instead of repeating that filter in five
scans. Membership's live-person filter and grievance timing remain distinct;
no population eligibility or class/political weighting changes included.
Validation: faction history/replay and gameplay gate suites.

## Feature 46: unrest

Failed takeovers and ordinary mob outcomes copied looting dispatch. Resolve the
stage first, then dispatch mob looting once before the pollution-stage override;
that override still does not invent a second looting event. Repression now
indexes residents once rather than scanning all agents for every faction
membership. setdefault preserves first-match behavior and overlapping factions
still seed memories once per membership. Grievance and protest reductions,
legitimacy loss, RNG order and trace links are unchanged.
Validation: repression/takeover/coercion trace suites and stage-dispatch checks.
Result: 10 repression/takeover/coercion tests pass. All 140 sampled stage
combinations match main, including looting arguments, trace rows and RNG calls.

## Final result

All 46 feature slices are complete. This is a behavior-preserving streamlining
pass, not a claim that the entire codebase is now small. Against c2a1472:

- Runtime Python: 44 changed files, 612 lines added, 2,068 removed; net 1,456
  physical lines removed. This includes new extracted modules.
- The legacy action facade accounts for 1,249 net removed lines; the other
  runtime changes remove 207 net lines. Repeated work and branches are also
  reduced where the physical line count is nearly unchanged.
- Five new regression tests occupy 84 lines in two test modules.
- All 46 central-config fields have matching ordered review sections above.
  Gate defaults, profiles and the central flag registry are unchanged.

The strongest duplication finding was copied legacy client code. Within the
simulation, repeated scans, branch-local settlement copies, and recomputation
were more common than interchangeable whole mechanisms. Genericizing those
mechanisms further would hide their differences in timing, tender, ownership,
and evidence. No generic framework was introduced.

## Final validation

The final focused regression run passed **362 tests in 51 modules**, each in a
separate Python process. The modules were:

- `tests.test_gameplay_flags`: 27 passed
- `tests.test_engineering`: 21 passed
- `tests.test_technology_adoption`: 13 passed
- `tests.test_trade_route_epidemic_transmission`: 5 passed
- `tests.test_food_economy_v2`: 32 passed
- `tests.test_coercion_gdd_adherence`: 8 passed
- `tests.test_coup_decision_trace`: 3 passed
- `tests.test_election_decision_trace`: 4 passed
- `tests.test_military_upkeep_trace`: 2 passed
- `tests.test_military_medical_account_trace`: 5 passed
- `tests.test_abstract_military_currency_audit`: 1 passed
- `tests.test_war_logic`: 6 passed
- `tests.test_war_intent_trace`: 6 passed
- `tests.test_worldview_actions_compatibility`: 3 passed
- `tests.test_diplomacy_action_trace`: 4 passed
- `tests.test_innovation_trace`: 10 passed
- `tests.test_imperial_enforcement_funding_trace`: 3 passed
- `tests.test_imperial_asset_seizure_trace`: 4 passed
- `tests.test_imperial_revenue_trace`: 3 passed
- `tests.test_sovereign_bonds`: 5 passed
- `tests.test_bond_announcements`: 7 passed
- `tests.test_elite_planning_gate_trace`: 17 passed
- `tests.test_career_transitions`: 13 passed
- `tests.test_collective_action`: 10 passed
- `tests.test_household_food_transfer_trace`: 5 passed
- `tests.test_feudal_subsistence`: 14 passed
- `tests.test_abundance`: 15 passed
- `tests.test_economic_policy_response`: 9 passed
- `tests.test_provincial_relief_transfer_trace`: 4 passed
- `tests.test_fiscal_policy_trace`: 7 passed
- `tests.test_fiscal_federalism`: 5 passed
- `tests.test_owner_currency_transfers`: 1 passed
- `tests.test_treasury_flow_trace`: 14 passed
- `tests.test_food_intake_trace`: 5 passed
- `tests.test_dependent_food_trace`: 3 passed
- `tests.test_market_auction`: 6 passed
- `tests.test_market_affordability_trace`: 2 passed
- `tests.test_forex_cycles`: 2 passed
- `tests.test_forex_accounting`: 4 passed
- `tests.test_world_trade_accounting`: 1 passed
- `tests.test_wilderness_trade_accounting`: 1 passed
- `tests.test_market_routes`: 18 passed
- `tests.test_obligation_payment_trace`: 2 passed
- `tests.test_phase1_enclosure_expansions`: 11 passed
- `tests.test_mass_entertainment_trace`: 2 passed
- `tests.test_medical_care_trace`: 4 passed
- `tests.test_disease_untreated_trace`: 2 passed
- `tests.test_faction_history_trace`: 3 passed
- `tests.test_repression_trace`: 3 passed
- `tests.test_takeover_decision_trace`: 4 passed
- `tests.test_scenario_coercion_trace`: 3 passed

Environment: repository venv Python 3.13, PYTHONPATH=., PYTHONHASHSEED=0,
MPLCONFIGDIR=/private/tmp/engineering-mpl, SDL_AUDIODRIVER=dummy and
SDL_VIDEODRIVER=dummy. Run each named module with `python -m unittest MODULE`.
The single-process combined run exited in native Pygame code. A smaller
sovereign_bonds + bond_announcements + fiscal_federalism combination also
crashes on clean main at build_panel drawing after Pygame shutdown/reinit.
Separate-process execution passed all listed modules; this existing native
lifecycle issue is not represented as a passing combined run.

Additional old/new comparisons included 1,946 AI score cases, 24 wage-quote
cases, 36 payroll cases (cash/scrip, farm/nonfarm and absent/stale/current work
budgets), three despair payment branches, 324 ecology combinations over five
actor roles, 64 medical cases with identical full traces and RNG state, and
140 unrest stage combinations with matching looting, traces and RNG calls.
All 46 changed Python modules parse, and git diff --check passes.

A deterministic aggregate digest comparison used seed 4243, three turns and
trace disabled on both clean main c2a1472 and the completed feature source.
The digest covers per-tile population, GDP, cash, bank equity, aggregate goods,
prices, exports/imports, foraging and unrest, plus nation population/treasury
and currency violations. Monetary/stock/price fields are rounded to eight
decimal places; this is not a proof of every internal state being identical.

| World | Tiles | Both versions' SHA-256 | Currency violations |
| --- | ---: | --- | ---: |
| Hex | 81 | `0380e973163ce2b47b1c5426235a84068a667d9fd58f5de7ed7564c7449e6ac8` | 0 |
| Voronoi | 80 | `43d8db34df3cf2507df0cdce1d5d709e002dc814d2102461ec025aaad7c738ce` | 0 |
| Hex, labor-frontier-rivalry | 81 | `a4656ac926c9803f495f892a661d616ff13a871d79539543f480f110ef855d38` | 0 |

The comparison helper and raw logs are session artifacts under /private/tmp
(gameplay-aggregate-check.py and streamline-*.log). The report above records
the evidence independently of those temporary files.

## Existing failures and remaining findings

The complete repository test suite is not claimed green. These failures were
observed during this review and reproduced on unchanged clean main:

- Diplomacy AI decision trace: an extra border vulnerability cause ID differs
  from the fixture's expected sole diplomacy cause.
- Heirless estate test: Charity.receive_food fixture signature mismatch.
- Four payroll tests: one truck/scrip fixture and three plunder-labor wage
  fixtures omit region.bank and error before the changed payroll calculation.
- Both old crop-credit accounting tests omit receipt.turn, so no current harvest
  is registered and their settlement-event lookups raise StopIteration.
- Furniture consumption in pollution_output_response expects six wood units
  but receives four in unchanged input-reserve behavior.

The slow two-case labor-shortage suite was not completed as a full suite; the
pastoral conversion case passed, but the second 15-turn setup was interrupted.
Older run_trace failures previously found in the base (malformed work budget
and stale production-event expectations) are also outside this pass's passing
regression list.

Known candidates retained for a subsequent behavior/ownership decision:
legacy policy renderers register mutable hitbox state and cannot simply be
aliased; legacy HUD/help/transfer views still contain copies; the old expansion
planner has no production callers; nutrition wear has distinct coefficients in
two models; direct rent collection differs from the live obligation pipeline.
These findings are recorded rather than hidden behind adapters or silently
deleted. The refactor branch retains every per-gate commit; main receives one
squashed change above c2a1472.
