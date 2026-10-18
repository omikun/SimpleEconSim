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
- New death totals count `demographics_estate.handle_death()` only. Combat and
  repression/assassination paths also set `alive = False`. Infant losses are
  separate events and must not be subtracted from an already living population.
  The death counters currently reset in trace reporting, which also needs repair.
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
   canal tolls, occupation seizures, tribute, tax recovery, grain purchases,
   subsidies, repression spending, inheritance, and scenario action costs.
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
   relabeling risk factors as proven causes. Population bridges distinguish
   births, deaths, migration, soldiers, corporate agents and ownership changes.
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
- This is the first slice, not completion of Phases 0–6. Legacy standalone
  pricing, source-to-order chains, comprehensive mortality,
  treasury reconciliation, AI evaluation evidence, chart-point/desktop parity,
  persistence and performance gates remain open. Current price bridges check
  ordered writes; they do not yet prove every upstream cause.

Follow-up in the same slice: transport price changes and the live market's
local seller asks and import quotes now record replayable formulas. The import
quote records the FX buy rate, tariff, drawback, margin and destination price
ceiling used at evaluation. Targeted tests cover no-order decay and a furniture
input-cost floor. Legacy standalone pricing remains outside the live recorder.
Supported price formulas now carry an in-record replay result. A mismatch
downgrades confidence and makes its turn bridge incomplete; it cannot be shown
as a verified explanation merely because the final price was recorded.

Phase 0 follow-up, 2026-10-18: demographic deaths now distinguish disease
presence from disease-attributable mortality. A disease fatality is counted
only when the actual death draw is above the pre-disease risk and at or below
the disease-adjusted risk. The summary counter is updated on the source tile
read by the disease summary. This adds evidence and corrects a counter wiring
gap without changing mortality probabilities or random draws. Population
bridges across births, migration, deaths, and role changes are still pending.

The storage portion of Phase 6 now has a compact `.ctr` event stream and a
streaming reader; see [the format and decode commands](compact_trace_format.md).
Legacy JSONL traces were removed and their input path was retired. Resume/branch
state, a rebuildable query index, and longer performance gates are still pending.
