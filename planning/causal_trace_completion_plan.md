# Complete causal coverage, with goods price fluctuations first

Date: 2026-10-16. This is the next implementation plan, based on a source review
of the existing recorder and probes. It supplements
[the original plan](gamewide_causal_instrumentation_plan.md) and
[the implementation status](gamewide_causal_instrumentation_status.md).
Tasks below are pending unless explicitly marked otherwise. Commit each phase;
do not push. Preserve simulation rules while adding instrumentation. Any needed
gameplay/accounting correction gets its own documented change and tests.

## Outcome and completion rule

For every displayed statistic, a player or analyst can select a turn and see
the opening value, ordered operations, closing value, formula inputs, units,
constraints, and relevant decisions. The explanation must distinguish exact
mechanical evidence, recorded observations, forecasts, and missing evidence.
Do not report a metric as fully explained just because a recorded number
matches its final snapshot.

Goods price fluctuations are the first player-facing deliverable: cover every
available good, price increases, decreases, and unchanged prices. Explain the
reference quote separately from what buyers actually paid.

## Findings that change the work order

- `region_market.py` already traces reference updates, decay, and transport
  pricing. `trace_snapshots.sample()` samples only food, wood, furniture, and
  transport. The web comparison trace button requests food-price records.
- `econsim_trade_money._price_default_decay()` and `set_market_price()` have
  separate legacy price mutations. Scenario cotton and cloth use
  `labor_frontier_market._cotton_ask()` and `_cloth_ask()`; those quotes can
  change while the recipe price stays fixed. Initialization constants are
  starting conditions, not market fluctuations.
- The main price formula calls `sum(recent) / len(recent)` a `vwap`. It is an
  unweighted mean of recent stored samples. Preserve that algorithm and label
  it accurately. A new transaction VWAP must use quantities and its own ID.
- Decay writes `recipes[good]['price']` without synchronizing `_price_ref`.
  Record both values and their roles; do not silently change the pricing rule.
- The latest elite candidate snapshot runs checks and estimates a second time
  before the real planner. It also truncates sectors to eight. Its feasibility
  labels omit some later cash/return gates. These are prospective alternatives,
  not proof that the real planner evaluated every one of them.
- The first death probe counted only `demographics_estate.handle_death()`;
  subsequent work added the shared registered-person path for combat,
  repression, and assassination. Infant losses stay separate from resident
  deaths. Disease presence remains risk evidence unless its modifier crosses
  the actual death-draw threshold.
  Death counters now reset at the simulation turn boundary, so repeated
  snapshots do not mutate them.
- `RunTrace.snapshot()` checks only the latest recorded value. It does not
  validate the formula, preceding mutations, or component provenance. Events
  marked `outcome` are automatically described as exact even where the supplied
  cause is only an interpretation (for example, dying while diseased).
- A misindented domestic coupon payment in `sovereign_bonds.py` was discovered
  during this review and corrected immediately. This does not validate the other
  recent instrumentation changes; Phase 0 remains required.

## Phase 0 — Establish trustworthy existing coverage

Files: `run_trace.py`, `trace_snapshots.py`, `trace_coverage.py`,
`metric_catalog.py`, `economy/capitalist_planner.py`, mortality producers,
and the recent bond/government/scenario probes.

1. Run focused recorder, bond, banking, debt, epidemic, and elite-planner tests;
   repair regressions before extending the schema. Then run short seeded
   default, labor-frontier, and Egypt scenarios with tracing on and off.
2. Compare semantic state, RNG state, actions, money, and goods. Exclude trace
   counters/files from the state digest and normalize nondeterministic identity
   generation explicitly; a seed alone does not stabilize UUIDs or process hashes.
3. Move trace counters/reset boundaries to the simulation turn boundary, or
   derive counts from events; calling a report twice must not mutate world state.
   Distinguish demographic deaths, violent deaths, and infant losses. Record
   disease presence as a risk factor unless the actual rule identifies a cause.
4. Capture decision evidence during the real evaluation. Prove any retained
   preflight helper pure and RNG-neutral; label skipped later stages as
   `not_evaluated_after_selection`, not rejected alternatives.
5. Define consistent entity IDs/location fields, metric units, count versus
   stock semantics, event/operation IDs, actual phase/turn, and schema versions.
   Separate data persistence failures from explanation completeness; a dropped
   row must not yield a falsely complete audit/checkpoint.
6. Extend the metric inventory to every serialized/charted field, including
   scenario panels and dynamic goods. For each: writer, formula, unit, timing,
   aggregation, UI location, coverage state, and explicit missing work.

Gate: focused tests pass, trace-on/off fixtures agree, reporting is read-only,
and inventory labels distinguish recorded, formula-replayable, linked,
reconciled, and missing. Commit correctness repairs and inventory.

## Phase 1 — Complete goods price fluctuation records

Files: `region_market.py`, `econsim_trade_money.py`,
`labor_frontier_market.py`, `scenario_political_economy.py`,
`trace_snapshots.py`, `metric_catalog.py`, shared price-trace helpers.

1. Inventory all price writers and quote calculators, including dictionary
   updates and scenario schedules. Tag each as initial endowment, reference
   quote, seller ask, import/delivered quote, paid transaction, or derived index.
   Register all goods dynamically; unavailable markets have null observations
   and a reason. Do not manufacture a zero paid price when nothing traded.
2. Retain `goods.price` as the documented reference-price ID for compatibility.
   Add distinct IDs for seller ask, delivered quote, transaction price,
   quantity-weighted transaction average, and any displayed price index.
   Identify market/tile, good, currency, price basis, and unit on every record.
3. At each real price mutation record old displayed price, old internal
   reference, new values, writer, operation ID, and ordered formula stages:
   bids/asks ratio (including the zero-supply rule), inventory scarcity,
   demand term, scarcity term, influence clamp, target, smoothing,
   recent-sample mean/blend, input-cost floor, final floor/cap, rounding.
   Store constants, input-good prices and quantities, production denominator,
   sample turns/IDs, and reason for an inactive/unchanged branch.
4. For decay, record the no-orders trigger, the 1.05 threshold, 0.95 factor,
   and cost floor. For transport and legacy prices, record the actual branch,
   multiplier, living-cost floor, and producer constraints used there.
5. Trace cotton wage-based asks; cloth wage, cotton cost, machinery and output
   capacity terms; freight, tariff/drawback, FX quote direction, margin,
   delivered-price ceiling, buyer affordability, and rounding. Record asks at
   their real evaluation point and paid prices at settlement. Do not reevaluate
   a quote after purchases have changed its inputs.
6. Emit a per-turn price bridge with *all* ordered mutations and intermediate
   values. Compute ordered stage differences whose sum equals the change;
   label them formula-stage contributions, not independent causal shares.
   Include a reference-reset term if displayed price and internal reference
   differ. Provide absolute and percent change (percent unavailable at zero).
7. Create a pure formula replay registry keyed by version. Recompute recorded
   prices solely from evidence. Never change existing prices to make a trace fit.

Gate: fixtures cover rising/falling/unchanged reference prices, no orders,
zero supply, active floors/caps, input-price shocks, transport, legacy paths,
cotton and cloth quotes, FX/freight, mixed-quantity sales, and multiple writes
within one turn. All final prices replay, ordered differences reconcile, and
trace-on/off market results remain identical.

## Phase 2 — Connect prices to their upstream causes

Files: production, foraging/consumption, `region_market.py`,
`region_logistics.py`, `transporter.py`, `world_trade.py`, `forex.py`, scenario markets.

1. Link local asks to available producer stocks and production/consumption;
   imported asks to actual available deliveries and their owning trader;
   bids to needs, inventories, cash/credit, and purchasing limits.
2. Record shipment posting, route capacity, delay, blockade/quarantine,
   arrivals, parked/rejected goods, tariff and freight settlements with stable
   operation IDs. Explain absent supply without counting cargo twice.
3. Link reference price updates to the prior samples actually used, and paid
   sales to the current order/quote records. Preserve lags: the current sale
   cannot explain a price update that already happened earlier in the turn.
4. Support chains such as strike → fewer worker-hours → lower output → fewer
   offers → price update. Display a broken link as missing evidence. Wages,
   taxes, and FX affect only the formulas that actually consume them; do not
   infer automatic cost pass-through or a macro inflation explanation.
5. For national/basket prices, record component prices, weights, currencies,
   coverage and territorial membership at that turn. Separate genuine price
   changes from changing product/territory mix or currency conversion.

Gate: seeded harvest, strike, route delay, and input-price shock cases resolve
from source events through quotes to paid trades; all arrows are supported.
Money, inventories and cargo ownership reconcile.

## Phase 3 — Close fiscal and scenario operation gaps

Files: `scenario_projects.py`, `scenario_occupation.py`, `scenario_geography.py`,
`scenario_political_economy.py`, `scenario_district.py`, `scenario_gunboat.py`,
`scenario_politics.py`, `scenario_oversight.py`, `scenario_situation.py`,
`scenarios/effects.py`, `scenarios/modules/debt.py`, imperialism/resistance,
estate transfers, government/bank helpers.

1. Use one transfer contract: operation ID, payer/payee accounts, currencies,
   amount, opening/closing balances, reason, and state mutation references.
   Enumerate project payroll, carrier fees, reserve recalls, central remittances,
   tariff receipts, emergency in-kind levies, canal tolls, occupation seizures,
   tribute, tax recovery, grain purchases, subsidies, repression spending,
   inheritance, and scenario action costs.
2. Internal municipal/provincial/sovereign transfers change account components
   but net to zero for the same national treasury. Cross-border receipts and
   payments have linked sides. Preserve operation IDs to prevent duplicates.
3. Audit default/underwriting/municipal bond paths against actual counterparties.
   Log explicit creation/destruction rules only where the simulation authorizes
   them. Separate coupons, principal, write-downs, deposits and spendable cash.
4. Reconcile national treasury, banks, households, firms and goods by currency
   and operation, retaining explicit unexplained residuals. Account for changes
   in territorial membership separately from cash transactions.

Gate: each enumerated flow has a targeted fixture; same-nation transfers net
to zero; source/recipient balances and national totals reconcile. No invented
balancing entry may erase a simulation accounting defect.

## Phase 4 — Finish AI and remaining metric coverage

1. Complete nation/corporation/scenario decisions at the real evaluation gates:
   spatial input imports/exports, liquidation, expansion/incorporation, rivals,
   labor mobility, diplomacy and coercive choices. Record thresholds, scores,
   actual tie-break order/draw, liquidity, borrowing limits, expected horizon,
   selected action, no-op reason, and execution success/failure.
2. Link later consequences to executed decisions and retain the distinction
   between predictions and realized profit, labor cost, citizen welfare,
   resistance, and economic/military competitiveness.
3. Close inventoried gaps in hunger/nutrition, real wages, employment, wealth
   distribution, GDP/trade, innovation, tenure/enforcement, climate, army supply,
   elections/coups/claims, and scenario sovereignty/institutional control.
   Derived statistics need membership, weights, refresh cadence and components.
4. Instrument violent deaths and consolidate mortality accounting without
   relabeling risk factors as proven causes. A resident census bridge now
   distinguishes births, entries, deaths, migration, person/entity role changes,
   and territorial membership changes by tile and nation. The profession-count
   population series now records per-profession member changes and their local
   phase; its total is the recorded sum of those counts. The snapshot explicitly
   distinguishes that pre-migration count from the end-of-turn resident census.
   Soldiers remain included in resident counts while their military status and
   movement are traced separately.
5. Upgrade coverage checks to validate mutation chains, versioned formulas,
   referenced causes, covered components, missing writers and conservation.
   Report counts by scenario, subsystem and metric, not one misleading percent.

Gate: every displayed field has an explicit coverage classification and tested
definition. Every supported deterministic fixture has zero unexplained changes;
unsupported paths remain visibly unavailable, with an itemized remaining list.

## Phase 5 — Deliver explanations in web, desktop and CLI

Files: `web_client/client.js`, `web_client/chart_renderer.js`,
`client/web/server.py`, `sim_server/sim_server.py`, desktop charts/panels,
`trace_report.py`, shared explanation renderer.

1. Add good, price-kind, turn/range and event-ID filters. Resolve upstream IDs
   across turns even when they are outside the current metric filter. Paginate
   rather than silently truncating explanations at 100 events.
2. Every goods row and historical chart point opens the exact selected good,
   tile and turn. Offer reference, posted/delivered, and paid-price views where
   those values exist. Web/iPad, desktop and CLI use the same explanation data.
3. Present old/new price, percent change, currency/unit, ordered formula terms,
   active constraints, supply/demand evidence and relevant decisions. Expand
   into exact records; mark no trade, stale samples, partial causes, and missing
   evidence. Long lists have paging and touch-sized controls.
4. Extend the same inspector to unrest, FX, treasury, AI, and the remaining
   registered charts. Preserve historical nation membership and field semantics.

Illustrative target (not measured): “Cloth ask rose from 10 to 11 per unit.
The recorded wage term increased by 0.7 and the cotton-cost term by 0.3.
Freight stayed at 0.3. No buyer purchased at the new delivered quote.”
Only show those numbers when the recorded formula and outcomes establish them.

Gate: the same selected point yields identical numbers in web, desktop and CLI;
iPad interaction selects non-food goods and earlier turns correctly. A no-trade
turn cannot show an invented transaction price or treat an ask as a paid sale.

## Phase 6 — Persistence, performance and release closure

1. Persist/resume event sequence, run/branch ancestry, schema/rule version,
   pending cause links and operation IDs. Test save/resume, branching, retried
   commands, crash/truncated-tail recovery and old-save compatibility.
2. Add a rebuildable index for turn/entity/good/metric/event ID over the source
   JSONL. Keep full evidence, bounded recent memory, and streaming exports;
   an index rebuild must not alter simulation state or event identity.
3. Benchmark fixed default, frontier and Egypt runs for 30 and 100 turns:
   runtime, peak memory, bytes/turn, query latency, full-run completeness and
   trace-on/off state equality. Set budgets from measured baselines before
   optimizing writes/indexes; document the accepted budget and actual results.
4. Publish the completed coverage matrix, remaining unsupported paths (if any),
   test evidence and performance figures. Replace the old 20-turn baseline
   claims with current measurements, explicitly dated and scenario-specific.

Gate: restart/branch correctness, bounded query memory, complete exports,
agreed performance budgets and all prior gates pass. Completion means verified
coverage of the declared supported game surfaces, not merely added probes.

## First implementation slice

After Phase 0, implement Phase 1 price replay plus the minimum Phase 5 selector:
one food rise, one food fall, one furniture input-floor event, and one scenario
cloth quote change, each inspectable at a historical turn. Include all goods
in the catalog/snapshot enumeration now; follow with the full upstream chains.
This delivers useful price explanations early while the remaining fiscal,
scenario, AI and persistence work proceeds in the listed order.

### Progress recorded 2026-10-16

- All priced recipe goods now receive end-of-turn reference snapshots, including
  cotton and cloth. An ordered bridge lists the observed reference writes and
  reports a gap when opening or closing values do not reconcile.
- Main market reference, decay, cotton asks, cloth asks, delivered scenario
  quotes and paid transaction averages have pure replay checks. Scenario asks
  and delivered quotes are captured during evaluation; paid prices are emitted
  only after settlement. The main market keeps its existing unweighted recent
  sample algorithm and labels it as a mean.
- The web tile panel and CLI can select a good and earlier turn. The web panel
  separates reference, seller ask, delivered quote, paid price and paid average.
  The API accepts a good filter. Death counters now reset at the engine turn
  boundary, so taking a snapshot does not clear them.
- This is the first slice, not completion of Phases 0–6. Source-to-order chains,
  comprehensive mortality,
  treasury reconciliation, AI evaluation evidence, chart-point/desktop parity,
  persistence and performance gates remain open. Current price bridges check
  ordered writes; they do not yet prove every upstream cause.

Follow-up in the same slice: transport price changes and the live market's
local seller asks and import quotes now record replayable formulas. The import
quote records the FX buy rate, tariff, drawback, margin and destination price
ceiling used at evaluation. Targeted tests cover no-order decay and a furniture
input-cost floor. The standalone `econsim.py` runner can now write an opt-in
compact price trace with `--trace`; its no-order decay and demand/producer-floor
formulas replay from captured inputs, and each turn includes price snapshots
and bridges. Tracing does not change standalone price results.
Supported price formulas now carry an in-record replay result. A mismatch
downgrades confidence and makes its turn bridge incomplete; it cannot be shown
as a verified explanation merely because the final price was recorded.

Standalone verification: the one-turn `econsim.py --trace` run produced three
price mutations, three price snapshots, three reconciled bridges, and zero
formula replay failures; the compact trace passed checkpoint verification. A
seeded trace-on/off comparison matched final stats and the final RNG state.
The run also exposed stale plot initialization for the full Goods enum; price
histories and chart labels now cover the configured goods, and the purchase
subplot limits its four panels to its four intended professions.

Phase 2 first slice: live-market positive buyer and seller orders now retain
the stock, need, cash, recipe, and rule context used to submit them. Producer
offers link to same-turn production records where available; seller asks link
to the offer, paid sales link to both submitted sides, and market totals and
demand/supply ratios replay from their recorded inputs. The price update or
no-order decay links to that ratio. Charter reductions record submitted and
permitted quantities and the governing rule. This traces submitted positive
orders; reasons why agents submitted zero orders and full route/arrival evidence
remain open. Imported shipment provenance now links a source acquisition
purchase to route departure when its trace ID exists, departure to arrival,
and arrival to the market's
import supply total and delivered quote; the paid sale links to its buyer order
and the quote actually evaluated. Shipment ownership, quantity, parked status,
route history, and explicit legacy-unlinked status stay on the records. Route
loading records queue depth, capacity-per-unit, and congestion delay; progress
and held records explain countdowns and strike, blockade, or quarantine pauses.
Food retention, freight affordability limits, and freight settlements are
recorded. Zero bids and local offers now appear in one compact per-good summary,
grouped by exact reason code and retaining the affected agent IDs and relevant
decision inputs; market demand and supply totals link to that summary. The
same-turn strike, available-hours, corporate-output, zero-offer summary, market
pressure, and price-update chain is now recorded.

Verification: the focused trace, auction, route, food-security, and trade-route
suites passed 65 tests. A seeded six-turn labor-frontier run verified that
recorded purchase event IDs resolve through departure, arrival, imported
supply, delivered quote, and at least one paid imported sale. A route fixture
verified congestion delays, blockade holds, and quarantine rejection. The
six-turn trace contained 13,663 rows in 863,399 bytes, six valid checkpoints,
zero unresolved cause IDs, and zero formula replay failures. It contained 144
zero-order summaries covering 2,448 zero bids and 3,213 zero local offers. One
turn of the same seeded labor-frontier scenario wrote 2,449 rows in 135,332
bytes, up from the 2,426-row pre-summary baseline. Compilation and
`git diff --check` passed. These are initial scenario samples, not the
30/100-turn performance gate.

Phase 0 follow-up, 2026-10-18: demographic deaths now distinguish disease
presence from disease-attributable mortality. A disease fatality is counted
only when the actual death draw is above the pre-disease risk and at or below
the disease-adjusted risk. The summary counter is updated on the source tile
read by the disease summary. This adds evidence and corrects a counter wiring
gap without changing mortality probabilities or random draws. Population
bridges across living residents now reconcile births, external entries,
cross-tile migration, deaths, role conversion, and nation membership changes;
the profession-count series records its exact output/trader scope, local update
phase, changing member IDs, and links to related death, occupation, migration,
and role events when available. Its recorded total remains the sum of the
profession counts, with national aggregation using current tile membership.
The profession metric is stored sparsely: stable counts and zero-valued
categories are omitted from snapshots, while the change calculations remain
available. In a seeded five-turn default-world run, 182 profession events
included 113 changed snapshots, no unexplained profession changes, and no
mismatch between the summed profession histories and the legacy population
series. The trace-volume check exposed and removed repeated unchanged rows.

The storage portion of Phase 6 now has a compact `.ctr` event stream and a
streaming reader; see [the format and decode commands](compact_trace_format.md).
Legacy JSONL traces were removed and their input path was retired. Resume/branch
state, a rebuildable query index, and longer performance gates are still pending.

Phase 2 follow-up, 2026-10-18: collective bargaining and authority events now
enter the run trace, with successive events in a strike linked together.
Workforce availability records scheduled and capped hours, unavailable hours,
employee status, wage, and machinery before production. Corporate production
and labor-constrained zero output link back to that record; independently
produced goods link to same-turn commons-foraging activity, including failed
production rolls when subsistence work lowered the chance. Zero output rows are
limited to labor or subsistence explanations, keeping routine full inventories
and missing inputs in the compact market reason summaries. Those zero-output
events are indexed like successful production, allowing no-offer summaries,
market supply, pressure, and price updates to retain the existing cause chain.

Verification: targeted strike/worker-hours/production and commons-work tests
passed, as did the live market/price integration test. The collective-action
suite passed after its fixture was updated to provide a second worker instead
of assuming the scenario hires two during its first turn. A one-turn seeded
frontier trace recorded 1,840 events (115,432 compressed bytes), including four
workforce records, two corporate zero-output events, 34 subsistence-linked
independent zero rolls, and 24 market zero-order summaries. All cause IDs
resolved, the checkpoint verified, and a trace-on/off run matched semantic
state and Python RNG state. This direct scenario runner omits the server setup
snapshot, so its size is not directly comparable to the earlier server sample.

Phase 2 follow-up, 2026-10-18: local cost-of-living calculations now record the
food, wood, and furniture prices, fixed basket weights, regional and climate
multipliers, currency, and a replayable total. Each basket links to the latest
prior reference-price event for each component, making the time ordering
explicit. National cost-of-living means link to their member-tile calculations
and record territory membership, coverage, currencies, basket definition, and
the fact that no currency conversion occurs. Their continuing-tile price
change and territory residual are reported separately; the residual is only an
arithmetic decomposition and is omitted when the currency basis changes.

National reference-price means now cover each priced recipe good and link to
the tile reference-price snapshots used. They record covered and uncovered
territories, price basis, local currencies, territory ownership, and changes in
membership or price coverage. The legacy national food-price history has its
own metric and replay record matching the existing formula exactly: total
member-territory denominator, missing recipe contributes zero, and an empty
nation falls back to 1.0. This preserves the meaning of the existing chart while
distinguishing it from the better-covered-territory mean. Neither national
price measure converts local currencies. Arithmetic territorial decomposition
is only offered when currency context is stable and is not labeled as causal
attribution.

Verification: 60 focused trace, auction, route, collective-action, and codec
tests passed; compilation and `git diff --check` passed. A two-turn seeded
frontier server trace contained 4,917 events (301,179 compressed bytes), two
checkpoints, 76 national reference-price aggregates, four cost-of-living and
four legacy food-history aggregates, 1,124 replayable formulas with zero
mismatches, and zero unresolved cause IDs. This is a compact two-turn audit,
not the 30/100-turn performance gate.

Phase 3 first slice, 2026-10-18: a shared `treasury_transfer.v1` contract now
records operation ID/type, side, amount and denomination, payer/payee accounts,
local cash leg, conversion status, and counterparty-leg coverage. Sovereign bond
principal purchases, proceeds,
early redemptions, maturities, and coupons now share a stable operation ID
across recorded nation treasury legs. Each leg records the payer and payee
accounts, the changed government-cash balance before and after, local and bond
currencies, the local-currency leg, and whether currency conversion occurred.
Mixed-currency operations are flagged because the current settlement code
moves the same numeric amount without an FX conversion. Coupon records retain
the gross amount and resident contribution separately from the government's
remaining cash outflow. Domestic bank underwriting identifies that the current
simulation adds proceeds to government cash without a recorded bank cash
debit.

Campaign Caisse payments and assigned-revenue interceptions use the same
contract, with matching IDs for payer and creditor legs and before/after
government cash balances. The trace writer tolerates scenario nation objects
without an explicit currency by using tile, bond, then USD fallback context.

The municipal sewer bond path now records the contractor cash credit as
`finance.cash_creation`, linked by operation ID to the bond/project. This
exposes an accounting gap: the simulation increases contractor cash by the bond
principal but does not mutate or record a funding-source cash account. The
existing game behavior is unchanged; the trace makes the source-side residual
reviewable instead of describing the movement as conserved.

Verification: 32 bond-announcement, sovereign-bond, campaign-debt,
bank-contagion, and sewer/ecology tests passed. Foreign-purchase and Caisse
fixtures verified paired operation IDs, account balance changes, and zero net
treasury movement for same-currency flows; a separate fixture confirmed
unconverted currency mismatch is flagged. The municipal fixture verified the
cash-creation record and its bond link. Compilation and `git diff --check`
passed. Other project, tax, subsidy, inheritance, occupation, and cross-system
transfer paths remain to be audited against the same contract.

Phase 3 follow-up, 2026-10-18: the shared transfer contract now covers
government baby bonuses, UBI, parental leave, welfare, and legacy tax receipts.
Each event records a stable operation ID, payer/payee account roles, currency,
the government cash balance before and after, and recipient IDs where available.
For group benefits the individual recipient balances are explicitly marked as
not captured; actor-level cash events remain separate evidence. Transfer IDs
are deterministic from the government, turn, amount, recipients, and decision
inputs, so tracing adds no random draws or economic state changes.

Verification: 80 focused government-transfer, supply-control, live trace, and
campaign-debt tests passed. The fixture checked outgoing and incoming balance
direction and the shared contract version. Compilation and `git diff --check`
passed. Other grain purchases, bank recapitalization, occupation/tribute flows,
inheritance, and household/firm transfers still need the contract or a
documented non-cash explanation.

Phase 3 follow-up, 2026-10-18: a shared treasury-leg emitter now keeps the
versioned transfer contract consistent across bonds, Caisse receipts, public
benefits, and Egypt scenario projects. Project construction, upkeep, and repair
wages link the Egyptian treasury balance to each worker's before/after cash.
District reserve recalls and central revenue remittances record both sides of
the same-nation movement; paired `finance.treasury_flow` legs net to zero in
national reconciliation. Grain entitlement records each carrier payment and
the paired in-kind food transfer from the owner's inventory to recipient
calories/deficit, with the carrier payment linked as supporting evidence.

Verification: 46 government-transfer, scenario-project transfer, Caisse,
sovereign-bond, and live trace tests passed. Focused fixtures verified exact
worker balances, paired recall/remittance legs, and food inventory/calorie
changes; compilation and `git diff --check` passed. The existing broad
`test_scenario_projects` integration fixture could not initialize its Egypt
world because `shape_nile_delta` raised “Egypt's river needs a second coastal
outlet for its delta”; this occurs during map generation before the changed
transfer code runs. Project transfer checks therefore use small deterministic
fixtures until that separate generation failure is resolved.

Phase 3 follow-up, 2026-10-18: import tariff receipts now record separate
national and port-government treasury credits under one operation ID, with
exact recipient balances and the gross, intercepted, and allocated amounts.
Emergency food levies now record a `goods_transfer.v1` contract, the public
food-stock change, each donor's inventory change and protected reserve, and the
remaining meal gap after collection.

Verification: 26 government-transfer, tariff-sharing, emergency-food, scenario
project, and fiscal-federalism tests passed. Tariff fixtures confirmed the
80/20 allocation nets to the actual receipts and uses distinct government
account identities; the levy fixture confirmed donor inventory loss equals
the government's food-stock gain. Compilation and `git diff --check` passed.
Bank recapitalization, occupation/tribute flows, inheritance, and broader
household/firm transfers remain open.

Phase 3 follow-up, 2026-10-18: routine government food purchases from local
markets now record one payer/payee contract per seller, with exact government
cash, seller cash, seller stock, and public food inventory balances. The
treasury flow itself is the cause of the paired goods-sale record, and both
records share the same operation ID; the former aggregate treasury deduction
was removed to avoid counting purchases twice.

Verification: the food-security, market-auction, and market-route suites passed
33 tests. The emergency market-purchase fixture confirmed that individual
treasury legs sum to the government's cash loss, seller receipts match those
legs, food stocks move by the purchased quantity, and the goods event links to
the cash event. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Egyptian private harvest purchases, warehouse
sales to households, public purchases from private stores, and unpaid
requisitions now emit linked cash and goods transfer contracts. Cash and stock
events share a deterministic operation ID derived from the transaction parties,
tile, turn, and type, so enabling trace does not change scenario state or IDs.
Requisitions identify the absent payment, record household stock seizure, and
link the added district unrest and national legitimacy loss to the requisition.
Aggregate grain-debrief rows keep their existing totals and list operation IDs.

Verification: nine focused grain/project transfer tests passed. Five scenario
grain tests checked both sides of private purchases and sales, public treasury
purchases, unpaid seizure, linked unrest/legitimacy changes, and equal
simulation outcomes with tracing enabled or disabled. Compilation and
`git diff --check` passed.

Phase 3 follow-up, 2026-10-18: sovereign bank rescues now emit one transfer per
bank, pairing each treasury debit with the bank-capital increase. Bank-capital
outcomes and treasury flows share an operation ID, and the treasury record
links directly to its capital-change cause. The previous total-only treasury
debit was removed so reconciliation counts each rescue exactly once.

Verification: 21 banking-contagion, debt-enforcement, and bond-announcement
tests passed. The two-bank rescue fixture reconciled its $1,050 total debit to
the individual $650 and $400 capital increases, with both account balances and
cause links checked. Compilation and `git diff --check` passed. Estate-driven
bank recapitalization, occupation/tribute flows, inheritance, broader
household/firm transfers, and other scenario costs remain.

Phase 3 follow-up, 2026-10-18: deposit bail-ins now record each depositor's
reduced bank claim against the matching bank-capital increase as a non-cash
conversion. Aggregate bank changes link the individual conversions; faction
loyalty and national legitimacy outcomes link back to the bank resolution.

Verification: 50 banking-contagion, debt-enforcement, bond-announcement, and
live trace tests passed. The bail-in fixture checked a $112.50 depositor
haircut, equal bank-equity gain, explicit no-cash status, and the downstream
bourgeoisie, labor, and legitimacy changes. Compilation and `git diff --check`
passed. Estate-driven bank recapitalization,
occupation/tribute flows, inheritance, broader household/firm transfers, and
other scenario costs remain.

Phase 3 follow-up, 2026-10-18: estate-driven bank debt writeoffs now show the
full seniority waterfall. Shareholder capital losses and each depositor's
non-cash loss are recorded separately; any local treasury recapitalization is
paired with the bank capital gain under a treasury transfer contract; any
remaining loss explains the negative bank equity. The writeoff outcome links
the component events and shares a stable operation ID with the economic
ledger.

Verification: the 45 supply-control and actor-account tests, seven banking
contagion tests, 12 scenario-debt and coercion tests, seven bond-announcement
tests, and 29 live trace tests passed. The heirless-default fixture reconciled
the $25 loss as $4 capital, $10 depositor haircut, $3 treasury funding, and $8
residual loss, with exact account balances and cause links. Compilation and
`git diff --check` passed. Occupation/tribute flows, general inheritance,
broader household/firm transfers, and other scenario costs remain.

Phase 3 follow-up, 2026-10-18: bounded Guided Egypt occupation receipts and
withdrawal settlements now pair payer and recipient treasury balances under
one operation ID. The receipt explanation records institutional control,
resistance, boycott, strike, port damage, the per-turn cap, and available cash.
Feudal in-kind tribute records each serf/lord inventory leg, subsistence
protection, force and protest conditions, and a linked valuation using the
legacy log's food and recipe prices.

Verification: six occupation/tribute trace tests, 16 coercion, grain transfer,
and government transfer tests, and 79 actor-account, fiscal, and live trace
tests passed. Trace-on/off occupation and tribute fixtures preserved balances
and stable operation IDs. Compilation and `git diff --check` passed. The six
existing full Egypt occupation tests still fail before the changed code runs:
world generation raises because `shape_nile_delta` cannot find a second coastal
outlet. Imperial revenue claims outside this bounded occupation, tax recovery,
general inheritance, broader household/firm transfers, and other scenario costs
remain.

Phase 3 follow-up, 2026-10-18: cadastral tax assessments now record household
cash payments, exact national and municipal allocations, arrears changes,
missed-assessment counts, and the deterministic foreclosure-risk roll. A
foreclosure records the buyer's auction payment, its split into public tax
recovery and cultivator refund, arrears recovery, use-right transfer, and linked
unrest, legitimacy, and migration consequences. Municipal receipts are
attributed to their district treasury, separately from national receipts. The
existing migration path also now reads the current turn before withdrawing and
redepositing bank funds.

Verification: the assessment and auction fixtures reconcile all cash and
arrears balances and check cause links; trace-on/off fixtures produced identical
simulation state. The 98 focused coercion, banking, grain, occupation/tribute,
government transfer, supply-control, and live-trace tests passed. Compilation
and `git diff --check` passed. Full Egypt integration remains blocked earlier
in world generation by the existing missing Nile delta outlet. Guided Suez
transit tolls, imperial revenue claims outside the guided occupation, household
aid and subsistence flows, subsidies, repression costs, inheritance, and other
scenario costs remain.

Phase 3 follow-up, 2026-10-18: guided canal transit now records paired payer and
recipient treasury balances, a cumulative toll event, and the resulting fleet
movement. It retains the simulation's nominal transfer across GBP and EGP and
marks that no currency conversion occurred, so the mismatch is visible in the
trace. The event uses a deterministic operation ID derived from the turn,
crossing, payer, and prior toll total.

Verification: two focused toll-trace tests passed. They checked both account
balances, shared operation IDs, the cross-currency no-conversion flag, movement
cause links, and trace-on/off state equality. Compilation and `git diff --check`
passed. The four existing end-to-end geography tests remain blocked by
the previously documented Egypt delta-generation error. Caisse transit-toll
and granary seizures, general imperial revenue interception, household aid and
subsistence flows, subsidies, repression costs, inheritance, and other scenario
costs remain.

Phase 3 follow-up, 2026-10-18: customs-receivership tariff interception now
records the exact creditor treasury credit and receivership debt reduction.
The revenue source is labeled as an aggregate with no identified source account,
and the creditor-side no-FX behavior is visible for currency mismatches. The
remaining national and port tariff receipts link back to the interception and
debt events. When no creditor treasury can be found, the trace records the debt
change and missing credit without fabricating a cash leg.

Verification: three focused fixtures cover exact balances, tariff allocation,
trace-on/off state equality, and the missing-creditor path. The 57 customs,
imperial-debt, scenario-debt, public-transfer, and run-trace tests passed.
Compilation and `git diff --check` passed. Caisse transit-toll and granary
seizures, other imperial claims, household aid and subsistence flows, subsidies,
repression costs, inheritance, and other scenario costs remain.

Phase 3 follow-up, 2026-10-18: public food-aid distributions now record each
government food-stock debit and recipient inventory increase under a
`goods_transfer.v1` contract; the aggregate distribution links to its recipient
events. Automatic and government-supported household mutual aid record the
donor and recipient food balances, total meals moved, and the supported
program's legitimacy change.

Verification: five focused fixtures cover ordinary and emergency public food
aid, automatic and supported mutual aid, exact inventory balances, outcome
cause links, and trace-on/off state equality. Fifty-six food-security, scenario
grain, government-transfer, and live-trace tests passed. Compilation and
`git diff --check` passed. Full Egypt integration remains blocked during world
generation by the existing Nile delta outlet error. Broader subsistence flows,
other household aid channels, subsidies, repression costs, inheritance, and
other scenario costs remain.

Phase 3 follow-up, 2026-10-18: Caisse transit-toll seizures now trace the
debtor treasury debit when it occurs, the creditor treasury credit, and the
receivership balance change. Granary seizure records the district stock loss,
the legacy $2-per-food-unit valuation, and the resulting creditor cash receipt;
it explicitly says the creditor receives no food inventory. Missing payer or
creditor legs remain visible instead of being filled with balancing records.

Verification: four focused fixtures cover funded toll seizure, the legacy
unfunded fallback, granary valuation, and trace-on/off state equality. The 61
customs, coercion, scenario-debt, government-transfer, and live-trace tests
passed. Compilation and `git diff --check` passed. The existing fallback rule
credits up to $5 when the debtor cannot afford the full requested toll and does
not debit the debtor treasury; the trace exposes this accounting defect, which
is left as a separate gameplay correction. The manager comment mentions royalty
seizures, but no royalty-seizure mutation exists in this path. Other imperial
claims, household aid and subsistence flows, subsidies, repression costs,
inheritance, and other scenario costs remain.

Phase 3 follow-up, 2026-10-18: provincial emergency relief now records each
surplus-food donor debit into the shipment's in-transit cargo balance, the
government-funded haulage payment with the government's cash debit and every
hauler's cash increase, and each arrival transfer from cargo to residents or
the destination's public food inventory. Dispatch events link donor and payment
legs; arrival events link the recipient and public-stock legs back to the stable
shipment operation ID. Shipments retain that deterministic ID so the later
arrival can be matched to dispatch without storing a trace event ID in game
state. Explicit outcome events record when an eligible transfer is skipped
because there is no route or the government cannot afford the haulage request.
A cash leg is emitted only for actual hauler payments.

Verification: four dedicated fixtures reconcile donor food, cargo, wage cash,
resident food and fallback public stock, and check the unaffordable dispatch
outcome. A cloned-state check confirms tracing does not change dispatch or
arrival results. Fifty-two focused food-security, provincial-relief, public-aid,
and run-trace tests passed. Compilation and `git diff --check` passed. More
general household subsistence, other aid channels, subsidies, repression
spending, inheritance, and other scenario costs remain.

Phase 3 follow-up, 2026-10-18: all four player district responses now emit a
success or failure outcome with the reason and measured effects. Public relief
records each transfer from Cairo's maize inventory into a household's queued
next-meal entitlement. Local negotiation pairs Cairo's treasury debit with each
recipient's cash balance and links the payment to the resulting unrest, protest,
and grievance reductions. Tax relief records the local rate change, unrest and
protest multiplier, legitimacy gain, and reduced extraction level. Repression
records available forces, seeded casualty and broken-promise memories, protest
change, and legitimacy cost. Rejected relief, unaffordable settlement, and
repression without force record their no-op reason.

Verification: seven district-action fixtures and 15 district-action,
household-aid, and public-transfer tests passed, including cloned-state
trace-on/off equivalence. Compilation and `git diff --check` passed. The broader
Egypt campaign and playthrough suites remain unable to initialize because
`shape_nile_delta` raises the existing missing-second-coastal-outlet error
during world generation, before these action paths run.

World-generation follow-up, 2026-10-18: the Egypt delta builder now prefers an
unclaimed channel for its second outlet and, when the selected fork is blocked
by generated rivers, reuses the cheapest connected side channel. The default
seed now builds a 1,000-region map with two distinct coastal outlets. The
campaign's closed-canal response remains the authored Alexandria reroute; an
outdated test that expected no landing was corrected to assert that route and
battle location.

Verification: 16 campaign, geography, and district-action tests passed, as did
12 scenario-project tests, the 70-turn historical campaign path, and the default
world-build check. The full ending-matrix audit launched 15 separate 70-turn
campaigns and was stopped after several minutes without output; its complete
matrix result is still unverified. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: the nationwide `release_maize` action now records
each public-stock debit against an individual household's next-meal ration
queue. A national outcome links those transfers to the number of recipients and
the before/after reserve. Skipped releases record whether the reserve cannot
fund a full ration or no household is underfed. These queue transfers are
distinguished from food already in a household's inventory.

Verification: three focused fixtures cover allocation, all three no-op reasons, and
trace-on/off state equivalence. Thirty-two national and district relief,
household-aid, food-security, and government-transfer tests passed. Compilation
and `git diff --check` passed. Other public assistance and household subsistence
flows, subsidies, repression spending, inheritance, and scenario action costs
remain.

Phase 3 follow-up, 2026-10-18: the shared repression mechanic now records when
force is missing or used, the police/garrison present, legitimacy and protest
changes, grievance reduction, and the people receiving casualty and broken
promise memories. The event is emitted at the mechanic so district and other
callers share one causal record. Military and police payroll/maintenance
transfers remain separate fiscal gaps.

Verification: three dedicated fixtures cover forced repression, the no-force
gate, and trace-on/off state parity. Eighteen repression, district-action, and
coercion tests passed. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: emergency construction overrun grants now pair
the national treasury debit with the contractor credit, link that transfer to
the project outcome, and record why grants are rejected. The record includes
the project resume and cumulative subsidy amount. Other policy subsidies still
need their own modeled payee or explicit unmodeled-service treatment.

Verification: four focused fixtures plus the existing overrun-subsidy regression
passed. In the full 12-test construction module, 11 passed and an unrelated
staffing assertion failed because efficiency was exactly 0.2 rather than above
0.2. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: dependent children now receive per-transfer food
inventory records paired with the parent's inventory debit. The aggregate
household transfer links to those records. Existing callers can keep the
two-value return; the lifecycle requests transfer IDs only when it needs to
connect the aggregate event.

Verification: three dedicated fixtures cover exact inventory reconciliation,
trace-on/off state parity, and linkage from the lifecycle summary. Twenty-three
dependent-food, game-time, nutrition, national/district relief, and household-
action tests passed. Compilation and `git diff --check` passed. Household cash
affordability, non-food consumption, and other support channels remain.

Phase 3 follow-up, 2026-10-18: household intake now records food source quantities
from reserved public rations, household inventory, and traders' foreign/export
stock, alongside caloric deficit, energy reserve, and hunger-step changes.
Routine full meals with no changing health state are omitted to control trace
volume. Starvation deaths link to the same-turn intake record when one exists.

Verification: five dedicated fixtures cover shortage, trader stock, routine-noise
suppression, starvation-death linkage, and trace-on/off parity. Sixty-nine food,
nutrition, life-cycle, district, and run-trace tests passed. Compilation and
`git diff --check` passed. Household cash affordability, non-food consumption,
and other support channels remain.

Phase 4 follow-up, 2026-10-18: the labor scheduler now records the round-robin
cohort selected, who was deferred, and which hunger, unemployment,
dispossession, or eviction conditions caused an emergency bypass. Per-worker
wage and livelihood decisions link back to the schedule record, making the
evaluation cadence visible alongside the already traced candidate scores.

Verification: three dedicated fixtures cover ordinary deferral, emergency
bypass and its causes, repeated-call gating, and trace-on/off state parity.
Twenty-nine scheduler, capitalist-planner, and rivalry tests passed. Compilation
and `git diff --check` passed.

Phase 4 follow-up, 2026-10-18: nation diplomacy evaluation now records each
candidate gate and decision for dominant threats, counterbalancing alliances,
trade pacts, treaty betrayal, and ideological war. The records expose
relations, military strengths, threshold checks, eligibility, selection, and
stable reasons. The final nation-AI decision links to the detailed diplomacy
evaluation.

Verification: two dedicated fixtures check candidate reasons, the proposed
intent list, final-decision cause linkage, and trace-on/off behavior parity.
Seventeen diplomacy-AI, war-logic, and multi-nation sandbox tests passed.
Compilation and `git diff --check` passed. Scenario diplomacy policies and
other spatial, expansion, and AI candidate gates remain incomplete.

Phase 4 follow-up, 2026-10-18: the Egypt scenario foreign-policy evaluator now
records France's ordered policy gates, Britain's funding and protest gates,
and the Ottoman Empire's mediation trigger. The British offer reply records
the recovery cap, canal-access value, expedition costs, protest and canal-line
penalties, and the treaty-versus-military comparison. The reply links to the
British funding evaluation that informed it.

Verification: two dedicated fixtures cover policy candidate rows, serialized
trace data, cause links, offer valuation, and trace-on/off state parity. Ten
scenario-diplomacy and geography tests passed. The broader playthrough suite
was interrupted inside its separate-process ending-reachability matrix and has
no complete result. Other scenario candidate gates and action outcomes remain
incomplete.
