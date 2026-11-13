# Multi-step elite planning: detailed implementation plan

Status: implemented as an experimental, default-off production/supply planner.
Branch: `feature/elite-operator-runner`; main remains unchanged.
The responsibility split, generic input correction, pure projections, bounded
search, central configuration, shadow mode, real-order execution and persisted
recovery are implemented. See the [acceptance report](reports/elite_planner_acceptance/README.md)
and its twenty varied, complete-turn decisions for evidence and supported-scope
limits. The economic review finds no net-asset advantage over ordinary policy;
the experiment remains off by default.
The sections below retain the approved implementation contracts and sequence.

## 1. First delivery and boundaries

Support one corporate firm, its current non-food production recipe, its existing
employees/machinery, and its local market/currency. The first chain is:

1. Choose an affordable quantity/price limit for the firm's production input.
2. Buy through the existing auction and observe the actual fill.
3. Wait for normal production and payroll; observe actual consumption/output.
4. Observe a funded output sale through the next ordinary auction.

The planner controls input purchase intent and when to wait/review. It does not
create a new crafting action or market. Output sale initially uses ordinary ask
rules; a projected sale is never credited as real cash. Compare the entire chain
with existing policy, including its automatic purchasing, production and sales.

Exclude recipe switching, hiring, new machinery, household spending, overseas
trade, borrowing/FX, crop advances, leases, water rights and charters from search
v1. Existing policies continue handling them. Add a supply alternative later only
when its timing, counterparties and effects have an explicit pure projection.
Workshop/engineering/food routes that bypass the supported corporate production
path report `unsupported` and retain existing policy. Do not approximate them
using the wrong production formula.

Initially admit only firms whose projected commitments can be funded from their
own realized cash. Existing loans/dues still constrain them. If automatic bank or
owner-financing behavior materially changes the comparison and has no pure model,
report that limitation and retain baseline rather than invent future financing.

One firm owns one plan. An owner and company must not create competing plans for
the company or combine their cash. Keep the existing stage order: luxury,
voyage/spatial/political actions, lord transformations and machinery still precede
supply planning. Earlier actions can invalidate a plan; recheck real resources
at order submission. A plan is not a reservation of another actor's property.

## 2. Actual timing and an executable example

Relevant normal phase order:

| Phase | Existing owner | Planning consequence |
| --- | --- | --- |
| Opening | `micro/region/opening_phase.py`, elite supply stage | Review/search; publish data-only input intent |
| Business auction | `micro/region_market.py` | Buy inputs and sell previously held output; observe actual fills |
| Work/production | `micro/region/production_phase.py`, `micro/region_production.py` | Normal work allocation, random production and input consumption |
| Payroll/obligations | Existing production-phase handlers | Pay real liabilities; projected sales cannot fund earlier dues |
| Next turn's auction | Existing market | Newly produced output can first sell here |

Never collapse input purchase, production and output sale into one opening-phase
transaction. Automatic phase advancement is not another paid operator action.

Build a controlled integration fixture with firm cash 20, two available wood
units priced at 3, payroll 4, a recipe producing one furniture from two wood, and
a buyer funding a furniture purchase at 15. Configure production to succeed
deterministically and hold irrelevant mechanisms explicitly disabled. Assert:

| Receipt | Firm cash | Firm inventory |
| --- | ---: | --- |
| Initial | 20 | No input/output |
| T input auction: actual purchase 6 | 14 | 2 wood |
| T normal production | 14 | 0 wood, 1 furniture |
| T payroll: actual payment 4 | 10 | 1 furniture |
| T+1 auction: actual sale 15 | 25 | No input/output |

The supplier receives 6, workers receive 4 and the buyer pays 15. Aggregate cash
is conserved. Use controlled actual clearing prices, not reference-price credits.
This fixture proves phase/accounting correctness, not improvement over ordinary
policy. Add a separate scarce-cash fixture where choosing a smaller input buffer
preserves payroll and improves the stated goal/value over the actual baseline.
If the baseline is equally good, select it rather than claim automatic production
as a planning gain.

## 3. Correct generic material settlement first

`economy/elite_transformation.py::execute_lord_transformation` currently charges
the generic operator fee and adds outputs without removing inputs. Correct this
in its own commit and establish a new baseline before planner comparisons.

For callback-free inventory transformations:

- Prepare a complete effect before writes: canonical goods, aggregated input
  quantities, available stock, cash, valid fee recipient and output quantities.
  Enum/string aliases such as `Goods.wood` and `"wood"` share one stock check.
- Share canonical inventory requirements with generic operator feasibility in
  `economy/transformation_graph.py`; use `Agent.inv_get/inv_add`, including custom
  goods. Do not create a second inventory representation.
- Reject negative/non-finite requirements and unsupported output quantities
  before charging. Inputs must exist before the action; its own outputs cannot
  satisfy its prerequisites. A missing `gov.agent` also fails before writes.
- Preserve the existing generic integer-output conversion explicitly in this
  correction; test/document fractional declared outputs being truncated. Do not
  silently change yields while fixing consumption. Input quantities and edible
  thousandth-unit storage use existing precision; reject an unrepresentable debit
  rather than journal a different quantity from storage.
- Apply each validated input debit and output credit exactly once; retain the
  source-owned fee transfer. Journal actual `input_consumed`, `production` and
  `operator_fee` effects; preserve `unclaimed_production` retirement semantics.
- Leave callback-owned transformations to their callbacks. Do not apply generic
  inputs/outputs in addition to a callback's existing effects.

Tests cover insufficient stock/cash/recipient with no partial effects, aliased
requirements, custom goods, fractional inputs/output conversion, food precision,
same-good input/output, and repeated invocation after inputs are exhausted.
Recipes can intentionally transform goods; do not assume every recipe conserves
unit count or mass. Search cycle rejection must prevent unbounded repetition
without changing legitimate recipe semantics.

## 4. Small data contracts, shared calculations

Use immutable records containing values and stable IDs, never live actors,
closures or a deep-copied world. Names below are proposed interfaces, not a new
general-purpose workflow framework.

| Record | Required contents |
| --- | --- |
| `PlanningState` | Firm/region/currency IDs; absolute turn and phase; canonical inventory quantities; cash and due obligations; productive/work capacity; pending commitments; observed prices/fills; assumption/version data |
| `PlanningGoal` | Kind (`input_stock` or `cash_buffer`), good/currency, minimum quantity/balance, deadline phase; cash-reserve constraints through that deadline |
| `CandidateStep` | Action ID, quantity, limit price/max spend, earliest phase/deadline, expected effects and assumptions; no executable callback |
| `SearchResult` | `found`, `no_improvement`, `unsupported` or `budget_exhausted`; best feasible candidate if any, baseline/candidate values, expansion counts and rejection reasons |
| Active-plan record | Schema version, stable plan/firm IDs, goal/steps/cursor, status, review turn, pending order/proposal, receipt totals, processed receipt cursor, assumptions and bounded retry count |

Proposed function boundaries:

```python
capture_planning_state(firm, region, turn, settings) -> PlanningState
derive_goal(snapshot) -> PlanningGoal | None
project_step(state, step, observations) -> ProjectionResult
score_terminal(state, goal, baseline) -> Evaluation
plan_goal(snapshot, goal, limits) -> SearchResult
revalidate_step(plan, firm, region, turn) -> ValidationResult
input_order_intent(plan, firm, region, turn) -> OrderIntent | None
observe_plan_receipt(plan, receipt) -> None
```

`capture_planning_state` reads only. Existing supply evaluation can seed water
rights, and production's `ensure_labor_agreement` can create agreements; neither
is safe to call as a hypothetical probe. Extract a shared pure agreement/default
builder if necessary. Test that capture/search do not change fatigue, agreements,
rights, inventory, gameplay caches, journals or any simulation RNG.

Extract only reusable deterministic production arithmetic from
`produce_corporation`: capacity/input limits, effort/modifiers, production chance
and realized output rounding. Keep actual random draws, fatigue updates, stock
writes and receipts in the production owner with the same draw order. Projection
uses that shared arithmetic and observed estimates; it never runs real production
on a clone or peeks at future random values. Preserve accelerated/Python paths.

Start with exact deterministic fixtures, then bounded expected-yield forecasts.
Fractional expected output is a forecast and cannot authorize spending real
inventory/cash. Unmodeled future work/strikes/engineering effects must be explicit
unsupported conditions or recorded uncertainty, not secretly initialized state.

Keep responsibilities compact: proposed `elite_planning_state.py` for records,
snapshot/goals; `elite_planning_projection.py` for pure successors and scoring;
`elite_plan_search.py` for search; `elite_plan_execution.py` for lifecycle/order
intent. These are ownership boundaries, not a requirement to split every helper
into a file. Existing production, market, journals and supply modules keep their
execution responsibilities. Review size and remove replaced helpers per commit.

## 5. Forecast, baseline and selection rules

Generate input goals from a supported next production batch and real available
work, not another hardcoded two-turn stocking formula. Cash goals have a specific
phase deadline; enough cash at the root does not satisfy a goal that includes
upcoming payroll/dues. Obligations due before the next confirmed receipt constrain
purchase affordability.

Project a small set of meaningful purchase quantities: no purchase, the next
batch shortage, supported additional batches within capacity/horizon, and the
ordinary-policy target. Include ordinary policy as a candidate. Share its pure
bid/ask calculations where safe, while recording uncertain future assumptions.
Do not call live borrowing, settlement or supply callbacks to build the baseline.

Limit projected purchases by observed supply and affordability; limit projected
sales by observed funded demand and normal asking rules. Quotes alone do not
prove a fill. The same observed market envelope applies to baseline and candidate;
forecasts cannot reserve counterparties or count demand twice. Replan on actual
partial/failed fills.

Rank feasible goal satisfaction first, then incremental terminal value relative
to baseline, then lower commitment/shorter completion and stable action IDs.
Terminal value includes cash plus conservatively realizable remaining inventory
minus outstanding liabilities, valued once. Paid inputs/wages/fees are already
reflected in balances; never subtract them again. Separate expected value from
cash available to commit. Require an explainable improvement before active
selection; equality retains baseline. Unsupported options retain existing policy.

## 6. Bounded deterministic search

Replace unused `TransformationGraph.find_conversion_paths` with resource-aware
search after its tests pass; repository search currently finds no Python callers.
Retain the commodity/operator registry and update its overstated multi-step
discovery documentation. `TradeCircuitGraphSearch` remains a separate route-
topology algorithm; it is not an executable firm-plan search.

Use deterministic best-first search over supported purchase decisions and normal
phase advances. Prefer this small explicit algorithm to a generic graph framework.
Allow repeated productive batches when resources/time permit them.

Initial experimental limits in central config: 3 commitment decisions, 4 elapsed
turns, 200 expanded states per firm, and 2,000 per world turn. Phase waits do not
consume commitment depth; they do consume horizon/work budget. These starting
values require measurement, not an optimality claim. Use deterministic counters,
not a wall-clock cutoff, to decide results. Measure elapsed time separately.

Start with exact equivalent-state deduplication and no-progress cycle pruning.
State identity includes phase, resources, liabilities, commitments and conditions;
retain cost basis if valuation depends on it. Do not round quantities merely to
merge states. Add dominance pruning only with tests proving equivalent future
options. Legitimate repeat IDs are not cycles by themselves.

Stable action ordering/ties must reproduce results. A world-level deterministic
round-robin cursor prevents low-ID firms monopolizing the global budget; persist
the active scheduler cursor. Shadow scheduling remains diagnostic-only and cannot
alter the active cursor or ordinary policy cadence. Due-plan validation has its
own bounded cheap path and must not wait
behind fresh searches. Budget exhaustion reports best-known feasible results and
reasons; it never spends unbounded work or claims an optimum.

## 7. Central configuration and shadow integration

Add a frozen per-run `ElitePlanningConfig` beside `GameplayFlags` in
`core/world_config.py`. Keep `GameplayFlags` boolean-only; do not add a mode string
to its 46 mechanism flags. Proposed fields: `mode = off|shadow|active`, search
limits above and a bounded replan limit. Defaults are off with validated positive
limits. Use one resolver for programmatic, CLI, web startup and restored settings.

Thread this value through `SimServer`, region attachment, CLI/web launch settings,
checkpoint manifest validation and reproducibility metadata. Do not add a new
configuration file or mutable process-global switch. Older checkpoint compatibility
must be explicit: missing experiment settings mean off.

The `elite_planning` parent gate wins. Also require relevant market/production
mechanisms; report why unsupported combinations cannot execute. Never silently
enable disabled flags. Rivalry scenarios currently disable elite planning: retain
their overrides and use explicit dedicated fixtures for coverage.

In shadow mode, snapshot and search at the existing supply-stage decision point;
ordinary policy still executes. Do not write active plans, alter order targets,
allocate operational plan/order IDs or change cadence. Trace proposed steps,
baseline/candidate values, assumptions and search limits. Compare full economic
state/accounting and RNG against off, excluding only deliberate observational
telemetry and experiment metadata. Trace enablement must not affect decisions.

## 8. Active execution through existing market orders

At the supply stage, an eligible active plan supplies an input-order intent. If
there is no useful supported plan, use existing supply policy. Unresolved legacy
proposals block competing plans for that firm. A submitted commitment uses the
existing stage's action handling; do not create a new top-level loop.

Apply the intent only to the firm's current recipe input inside the ordinary bid
path (`calculate_bid`, bid-limit handling and `trade`). Replace its corresponding
ordinary demand target; do not append a second bid. Preserve all other household,
food, setup-good and trader rules. Bound quantity AND limit price by actual cash
after shared order reservations and due-payroll/obligation allowance. Revalidate
immediately before submission because other policy actions can change the opening
snapshot. Planner allowances are not new ledger balances.

Use the existing market for matching, cash/inventory/cost-basis writes and journal
entries. Output asks remain normal in v1. The planner observes their actual fills;
it never pays itself at a quote or inserts a synthetic sale.

Introduce stable trace-independent `order_id` plus optional `plan_id`/`step_id`
provenance through order rows and settlement receipts. Diagnostic event IDs are
unsuitable command identities. Use a checkpointed per-owner sequence; submission
key `(plan_id, step_index, submission_epoch)` prevents duplicate bids. Production
and payroll receipts also need stable source identities and relevant firm/turn/
phase data; add only missing provenance to existing source events.

Advance progress at the source settlement/production path, including partial-fill
totals. Do not infer completion by repeatedly scanning bounded history: market
events retain only 500 rows and economic journals 2,000. Persist counters and a
receipt cursor/identity check sufficient to reject replay. Correlate ordinary
production/sale receipts to the one active firm plan without attributing opening
stock sales to newly planned output; retain opening-stock and quantity accounting.

## 9. Plan lifecycle, interruption and save/restore

Extend existing `EliteCapitalistPlanner._active_plans[firm_id]` as the single
owner. Use a versioned discriminated record for legacy supply proposals versus
production chains. Normalize old records once, preserving pending IDs/status and
budget; never resubmit a proposal just because its schema changed.

Transitions: `ready -> submitted -> waiting -> ready/completed`, with explicit
`blocked` and `cancelled` reasons. Submission is not a fill; prediction is not
completion. Wait on receipt quantities until the next step is actually feasible.
Failed/partial fills and deadlines trigger bounded replanning from real state,
including spent cash and existing stock. Cancellation follows existing order
lifetime rules; never invent a refund for an unfilled intent.

Extend `should_run_planning` with due-plan/receipt triggers. Fresh search retains
normal cadence; an input receipt or T+1 sale must not wait five turns to advance
the cursor. Validate active plans cheaply before deciding whether search is due.

Revalidate firm existence/aliveness, owner/region/recipe identity, workers,
mechanism gates, actual inputs/cash/obligations, order status, price limits and
deadline. Earlier priority actions and other decisions can invalidate an
assumption. Cancel/revise instructions; do not undo settled effects. Explicitly
test firm exit, ownership change and a worker strike after planning.

Switching off/shadow stops new commitments and clears future order overrides.
Already-created contracts/obligations settle normally. Passive receipt tracking
stays consistent while disabled so re-enabling cannot replay an old step.
Restore IDs, cursors, intent lifetime, budget scheduling and config; continuation
must neither submit twice nor skip a partial receipt.

Before accepting these tests, fix the checkpoint comparison oracle separately.
Main and this branch already reproduce a `pathlib` lazy-cache graph mismatch in
`test_live_state_rng_shared_accounts_and_retry_continue_on_new_branch`.
Canonicalize supported standard path values by concrete type and path text
without traversing lazy caches; keep application mutable fields and references
strict. Test warmed/unwarmed equal paths and genuinely different paths. Do not
ignore all private fields or weaken plan/RNG comparison to aggregate totals.

## 10. Commit sequence and acceptance gates

Each row was implemented in reviewable commits, with follow-up corrections from
final review. Evidence is recorded in the acceptance report. Work remains on the
feature branch; merge requires a later explicit decision.

| # | Change and primary files | Evidence / exit condition |
| ---: | --- | --- |
| 1 | Fix callback-free input settlement: `elite_transformation.py`, shared inventory requirements in `transformation_graph.py` | No partial writes on rejection; exact consumed/output/fee receipts; alias/custom/fraction tests; document intentional corrected baseline |
| 2 | Correct checkpoint oracle: `core/simulation_semantics.py`, checkpoint tests | Warm/cold paths equivalent, distinct paths differ, existing full continuation passes without hiding economic/RNG state |
| 3 | Add quantitative records/goals and hand-solvable fixtures: planning-state module and focused tests | Deadline/cash-reserve semantics; immutable snapshot; separate owner/firm cash; normal-phase 20 -> 14 -> 10 -> 25 chain |
| 4 | Extract shared pure production/market evaluation; add projection module | Deterministic projected/live effects agree; old live outcomes/draw order unchanged; no search-side agreement/fatigue/RNG mutation |
| 5 | Add baseline, funded demand forecasts and terminal evaluation | Partial/no demand, payroll-before-sale, inventory/liability value counted once; equal baseline wins; unsupported routes explained |
| 6 | Implement bounded search; remove unused DFS and correct registry documentation | Repeated batches, intermediate resources, deadlines, unaffordable steps, cycles, stable ties, firm/world budget exhaustion and fair scheduling |
| 7 | Wire central config and read-only shadow mode: `world_config.py`, server/CLI/web, checkpoint metadata, supply-stage trace | Default off; parent/scenario gates respected; off/shadow full state, journals and RNG equivalent apart from declared telemetry/settings |
| 8 | Add stable order/receipt provenance and one input-intent override: `region_market.py`, existing receipt owners | Exactly one ordinary/planned input bid; actual price/cash bounds; normal settlement conservation; trace-off IDs still work |
| 9 | Add active-plan lifecycle using `_active_plans`, supply and activation owners | One next commitment; due-plan wake; ordinary production/sale advance from real receipts; unresolved legacy proposals protected |
| 10 | Complete recovery and interruption behavior | Partial fill/expiry/rejection, replayed receipts, history eviction, changed workers/owner/firm exit, gate toggles; uninterrupted vs fresh-process checkpoint continuation matches |
| 11 | Fixed-seed active evaluation, cleanup and review | Explain forecast vs actual and baseline improvement; measure nodes/time, no starvation/duplicate orders; delete replaced logic and update docs |

## 11. Validation and completion criteria

Use focused modules alongside existing elite runner, valuation, cash,
planning-gate, treasury, supply, labor-law, checkpoint and gameplay-flag suites.
Production-kernel extraction also needs production and accelerated-path coverage.
Avoid tests that simply mirror helpers; assert actual resources, phase outcomes,
receipts, deterministic choices and continuation.

After pure tests, run a dedicated production/supply scenario across off, shadow
and active for several fixed seeds and enough turns for repeated chains. Include
adverse price/demand shocks and many competing eligible firms. Compare off/shadow
strictly. Compare active deliberately: source-accounted cash, input/output,
payroll coverage, failures, baseline/candidate forecasts, realized receipts and
bounded work. Active need not improve every stochastic run; the deterministic
beneficial fixture must improve and adverse cases remain feasible. Choose rollout
lengths/seeds in the implementation fixture and record results rather than
promising unmeasured speed.

Complete when the supported real chain works across turns and restore, the
planner never spends forecast assets, all mode/gate semantics hold, work limits
are enforced, and each calculation/effect has one owner. Keep active experimental
and off by default until this evidence is reviewed. Future supply projections are
separate extensions with the same contracts, not prerequisites to finishing v1.
