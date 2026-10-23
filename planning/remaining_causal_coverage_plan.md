# Close the remaining causal trace gaps

Date: 2026-10-22. Execution started; see Progress for completed slices and open gates.
This is the next execution plan after `b4dfe05`, supplementing
[the overall plan](causal_trace_completion_plan.md) and
[ordered treasury closure](treasury_account_closure_plan.md).
Commit each coherent implementation slice and update this document with evidence.
Do not push. Keep gameplay/accounting changes in separate documented commits.

## Goal

For a supported game statistic, explain the selected turn through recorded
operations, formulas and decisions, with a verifiable path from opening to close.
A player should understand what changed, what the actors did, and the tradeoff.
An analyst should be able to reproduce the arithmetic and locate missing evidence.

Do not equate these different checks:

1. A writer was instrumented.
2. A formula reproduces its recorded output.
3. Referenced upstream records exist and cover the required inputs.
4. Ordered writes reconcile the opening and closing stock.
5. The selected UI value uses that same metric, timing, membership and units.

A three-turn default probe currently verifies nine treasury account closures and
144 changed bank-stock snapshots. It does not exercise war, default, coups,
annexation, many scenario actions, save/resume or long-run performance.

## Source findings affecting implementation

- `begin_public_change()` / `finish_public_change()` provide explicit account
  probes. Many older transfer records still lack these stock probes. Extend
  actual mutation sites; do not infer before balances as closing minus payment.
- `TreasuryTraceBook.close()` deliberately rejects membership changes. It needs
  actual transition records before these can become verified composition bridges.
- `trace_coverage.py` counts matching changed snapshots plus treasury checks.
  It does not yet prove complete upstream provenance or all UI/history coverage.
- `RunTrace.query()` scans the complete `.ctr` file even for one event ID.
- `trace_codec.py` uses one live raw DEFLATE stream with sync flushes. A compressed
  byte offset is not an independently decodable starting point. Resume/index work
  must address compressor state, not simply reopen the file in append mode.
- `_known_event_ids` grows with the run despite the bounded recent ring. Public
  account inventory also includes government × referenced-bank combinations.
  Measure both before claiming bounded memory.
- `test_save_slots.py` exercises map/preset JSON slots. That does not establish
  full simulation checkpoint/resume. Preserve that existing feature separately.
- The earlier plan's references to indexing source JSONL and old trace
  compatibility are superseded: `.ctr` is authoritative. No legacy JSONL input
  or backward trace compatibility is required. JSONL remains a decoded export.

## Execution order and gates

Proceed in the order below. Phase 4 may start after the writer inventory, but
final acceptance depends on all phases. Avoid one large implementation commit.
Each slice records files changed, fixture exercised, tests run, remaining gaps,
and its commit. Failures remain visible; never add a synthetic balancing entry.

### Phase 0 — Establish an authoritative gap register

**Deliverables:** a machine-readable inventory and a short generated report.

1. Enumerate active public cash, deposit, liability and bank-capital writers,
   including aliases such as `treasury.cash`, `payer.capital` and dictionary
   updates. Record file/function, account types, current probes, semantic transfer
   record, calling path, and deterministic fixture. A text search is a starting
   point, not proof of completeness.
2. Enumerate serialized statistics, web/desktop chart series, scalar histories
   and event journals using `metric_catalog.py`, serializers and chart bindings.
   Classify canonical active paths, legacy standalone entry points, and unused
   histories. Audit `cash_log`, `bought_log`, `gdp_by_profession_log`, `forage_log`,
   `labor_decision_log`, `settlement_log`, `exchange_rate_log`,
   `foreign_reserves_log`, `price_spread_log` and `trade_balance_log`; do not assume
   every unmapped journal needs a new scalar metric.
3. Give each entry independent writer/formula/link/closure/UI coverage fields,
   units, sampling time and a precise missing-work description.
4. Generate scenario-specific gap reports rather than a single global percentage.
   Record reasons for unavailable metrics and distinguish a disabled feature
   from a branch that the fixture simply failed to exercise.

**Gate:** every declared supported surface and active public writer has an owner,
a fixture, a coverage classification and a tracked closure task. Production
writers newly added later require an inventory entry through a regression check.

### Phase 1 — Finish financial and military account probes

**Files:** `treasury_trace.py`, `finance_trace.py`, `army.py`,
`banking_policy.py`, `sovereign_bonds.py`, `construction_politics.py`,
`disease.py`, and remaining direct economic writers identified in Phase 0.

1. Make `finish_public_change()` return emitted IDs. Where one action changes
   multiple accounts, give all legs the semantic operation ID and explicit
   actor/account identities. Link existing payment/decision records to those
   writes without creating a second signed treasury flow.
2. Add actual stock probes for military payroll, partial payroll, procurement,
   military hospital payments, bank rescues, construction progress/overruns,
   and public medical payments/refunds. Capture before images after any nested
   withdrawal and immediately before the cash debit.
3. Cover sovereign issuance, domestic underwriting, foreign purchase, coupons,
   resident coupon contributions, redemption, maturity, fees and default.
   Record the public cash legs and the bank asset/capital legs according to the
   existing rules; do not silently repair questionable allocation rules.
4. Check already instrumented bank/estate paths for missing public deposit
   reassignment, loss or rescue legs. Keep bank equity, debt principal,
   deposit ownership and public cash as distinct balances.
5. Record zero-payment and rejection gates where meaningful; blocked actions
   must not invent cash movement. Preserve frozen withdrawal and overdraft rules.

**Fixtures:** full/partial military funding; private versus public hospital;
foreign and domestic bonds; insufficient cash; default and rescue; shared-bank
aliases; frozen deposits; construction failure/refund.

**Gate:** each fixture closes its account chains and agrees with the existing
signed-flow audit where applicable. Tracing on/off gives identical semantic
state and RNG state. Deliberately missing/offsetting writes still fail closure.

Suggested commits: military/medical; bank rescue; bond cash settlements;
construction and remaining estate paths.

### Phase 2 — Finish political, manual and scenario account probes

**Files:** `coup.py`, `election.py`, `intents.py`, `worldview_policies.py`,
`client/desktop/panels/transfer_dialog.py`, active legacy adapters,
`agents/resistance/manager.py`, `scenario_projects.py`, `scenario_district.py`,
`scenario_politics.py`, `scenario_gunboat.py`, `scenarios/modules/debt.py`,
and active frontier/supply scenario modules.

1. Probe treasury seizure, election spending, repression/covert operations,
   grants, manual transfers, policy costs/refunds and national/provincial pools.
   An internal grant changes two public accounts while leaving their combined
   national treasury unchanged; both legs are required.
2. Probe scenario wages, arrears relief, reserve recalls, transport fees,
   creditor remittances and public action costs. Capture both sides of foreign
   transfers using their own nation/currency contexts.
3. Preserve initialization as starting conditions. Actions before tracing starts
   need explicit initialization observations, not fabricated historical writes.
4. Route shared web/desktop commands through existing common execution paths
   where available. Avoid independent financial implementations in the clients.
   Any active duplicate adapter must either delegate or receive the same probes.
5. Connect action → account writes → transfer → effect records. Unsupported or
   missing trace context gets a diagnostic rather than a claim of complete coverage.

**Fixtures:** funded/rejected/refunded actions, zero-net internal grants,
cross-nation transfers, coup seizure, frontier actions, and representative Egypt
public projects/crisis payments. Assert web/desktop command parity.

**Gate:** all inventoried active political/manual/scenario public writers have
verified positive and relevant failure fixtures; no duplicate flow counting.

### Phase 3 — Verify ownership and account-composition transitions

**Files:** `nation.py`, `province.py`, `claims.py`, territory/control writers,
`treasury_trace.py`, `bank_trace.py`, `trace_snapshots.py` and replay helpers.

1. Emit explicit transition records at claims, annexation, secession, occupation
   where it actually changes the accounting boundary, institution replacement,
   bank reassignment and government creation/removal. Identify the real mutation
   sites from Phase 0; a changed flag alone does not imply ownership changed.
2. Capture old/new nation, province, territory and government/bank aliases,
   physical account IDs, balances at transition, cause/action ID and sequence.
3. Reconcile national opening total plus account operations while included,
   plus balances entering at their transition time, minus balances leaving at
   their transition time. A final-balance membership adjustment is insufficient:
   a departing account may continue changing after departure.
4. Attribute each physical account once per national report. Moving a tile that
   shares a government with retained tiles need not move the whole public account.
   Track association reference counts and tier changes; handle multiple moves,
   a move out and back, and account closure/founding within the same turn.
5. Record currency changes separately. Preserve current unconverted aggregation
   semantics and label them; use recorded rates only when a real conversion
   occurs. Do not introduce FX translation through an explanation formula.
6. Promote a composition bridge only when its transitions and timed balances
   are complete. Incomplete transitions retain the current audit behavior.

**Gate:** replay works for new accounts, shared institutions, replacement banks,
partial province transfer, repeated same-turn moves, zero-balance associations
and currency changes. Aggregate accounting agrees with the live game, including
cases where the game's ownership rules are economically unusual.

### Phase 4 — Verify provenance and close remaining displayed metrics

**Files:** `metric_catalog.py`, `trace_coverage.py`, `run_trace.py`,
`trace_snapshots.py`, replay modules and writers identified by the inventory.

1. Extend coverage validation to missing/duplicate IDs, unresolved required
   causes, incorrect turn/sampling time, formula mismatch, chain discontinuity,
   membership gaps and UI binding mismatch. Validate required links according
   to each metric's contract; not every observation needs a fabricated cause.
2. Verify inactive/unchanged branches as well as changed values. Missing inputs
   must stay missing instead of becoming zero or falling out of the denominator.
3. Close active history/statistic gaps from Phase 0. Respect matrix histories,
   trailing samples, event journals and post-turn empty bucket appends. Link a
   chart point to the value actually plotted, including display transforms.
4. Recheck goods prices, unrest and FX in scenario fixtures: reference versus
   ask versus paid price; no-trade turns; market restrictions; currency direction;
   actual actor choices and whether their effects were realized.
5. Distinguish arithmetic explanation from interpretation. Do not claim that
   an observed correlation or forecast proves the reason for an outcome.

**Gate:** every supported displayed metric has a verified contract and fixture.
A matching recorded value cannot hide a missing required formula or source link.
The report names unsupported legacy paths separately from failures of active paths.

### Phase 5 — Durable checkpoints, resume, branches and recovery

**Files:** `run_trace.py`, `trace_codec.py`, simulation checkpoint integration,
new trace-manifest/resume tests; keep map preset slots separate.

1. Define a versioned run manifest and checkpoint contract before implementing
   resume. Store run/branch ancestry, schema/rule versions, last durable sequence,
   digest, turn, operation/command identities, RNG state and pending causal links.
2. Implement or locate a full simulation checkpoint boundary; do not mistake a
   serialized UI world or map seed for restorable simulation state. Persist the
   required economic/AI state and rebind physical bank/public account IDs after
   restore. Python object addresses cannot serve as saved identities.
3. Use independently decodable compressed segments/blocks for new traces,
   retaining `.ctr` as the source format. Resume into a fresh segment with an
   explicit predecessor digest; never serialize an in-memory compressor or
   append a new raw stream without framing it.
4. Publish the simulation checkpoint and trace boundary with a crash-consistent
   manifest protocol. A save or restore must identify one consistent pair.
   Restoring an older save forks a branch; it cannot rewrite committed history.
5. Deduplicate retried commands using durable command/operation IDs. Distinguish
   retry from a legitimate repeat action; never undo already settled money.
6. Recover to the last verified committed boundary on a torn tail. Preserve the
   damaged artifact and describe discarded/uncommitted records. Detect interior
   corruption; never silently skip it or certify it as a valid run.
7. Test write failures and interrupted saves, sequence/digest continuity, pending
   shipments/loans/technology causes across resume, and branch ancestry.

**Gate:** uninterrupted and checkpoint/resumed runs have equal semantic state
and RNG outcomes after identity normalization. No orphan cause links or duplicate
settlements; damaged data cannot produce a successful completion checkpoint.
No legacy JSONL input or backward trace-format compatibility is added. Preserve
existing map/preset slot migrations; a new full-simulation checkpoint format
does not require invented legacy migrations.

### Phase 6 — Rebuildable indexes and bounded inspection cost

**Files:** compressed-block codec/manifest, a new rebuildable query index,
`run_trace.py`, `trace_report.py`, `client/web/server.py`.

1. Index event ID, turn, entity, metric, kind and good with block/record locations.
   Use independently decodable blocks from Phase 5; raw offsets into today's
   single DEFLATE stream cannot provide arbitrary record access.
2. Treat the index as disposable derived data. Store its source boundary/digest,
   validate freshness and rebuild from committed `.ctr` blocks after deletion,
   corruption or restart. An index must not change event identities or game state.
3. Use stable pagination tied to a committed boundary so autoplay cannot make
   pages skip/duplicate records. Resolve cross-turn causes independently of the
   currently selected entity/metric filters, including ancestor branches.
4. Stream CLI reports and exports with bounded buffers. Capture a consistent
   export boundary and release the simulation lock before network streaming;
   handle slow/disconnected clients without stalling the game.
5. Replace unbounded known-ID/history caches with indexed lookup plus bounded
   caches where safe. Measure account-inventory combinations and retired strong
   references before optimizing; preserve explicit zero-opening evidence.

**Gate:** indexed and sequential queries agree for every supported filter and
page. Cold event lookup does not scan the whole run. Rebuilds are state-neutral,
exports verify, memory stays within the measured budget, and concurrent autoplay
and inspection remain consistent.

### Phase 7 — Finish the shared player explanation experience

**Files:** common explanation data builder, web/iPad trace inspector, desktop
trace panels, `trace_report.py`, chart bindings and parity tests.

1. Show treasury opening, actual receipts/spending, internal public transfers,
   membership effects and closing value separately. Expand into account writes
   and their decisions/transfer records. Shared accounts must not appear as
   duplicate money.
2. Use the same verified explanation model for price, unrest, FX and AI records.
   Label observation, forecast, verified formula, verified chain and missing
   evidence explicitly; summarize the largest recorded contributors first.
3. Ensure account and cross-turn cause navigation works from historical nation
   charts, including former ownership and renamed/replaced institutions.
4. Preserve touch-sized controls, loading/empty/error states and paging on iPad.
   A missing upstream record should identify the exact gap, not show a spinner
   indefinitely or invent a narrative.

**Gate:** web, desktop and CLI reproduce the selected source values, units,
status and membership. Exercise historical points, multiple goods, no-trade
turns, treasury transfers and a deliberately incomplete explanation. Retain
existing working chart bindings instead of rebuilding the inspector wholesale.

### Phase 8 — Scenario acceptance, performance budgets and release evidence

1. Use deterministic fixtures to force rare branches: war, sovereign default,
   bank rescue, political seizure, manual refund, frontier claim, annexation and
   scenario crisis. Autoplay alone is not branch coverage.
2. Run fixed default three-nation, `labor_frontier_rivalry`, `supply_rivalry` and
   Egypt acceptance scenarios. Verify the actual canonical runner for each.
   Include multiple documented seeds; record commands, commits and settings.
3. First run short checks to find failures, then the 30/100-turn acceptance and
   benchmark matrix from the overall plan. Reuse a run for coverage and timing
   where valid instead of repeating it without a concrete reason.
4. Compare tracing off/on semantic state, RNG and actions. Normalize UUID and
   allocation-dependent identity differences explicitly, without excluding
   economic state. Measure runtime, peak RSS, compact/decoded bytes per turn,
   cold/warm query latency, recovery/index rebuild time and export consistency.
5. Publish measured baselines before fixing budgets. Set concrete regression
   limits in the benchmark configuration; optimize only diagnosed bottlenecks
   and rerun the affected correctness/performance gates afterward.
6. Publish a final coverage matrix and release report: fixtures exercised,
   provenance/closure failures, unsupported surfaces, reproducible measurements
   and the exact commit. If a gate fails, leave it open with a follow-up task.

**Gate:** all declared active surfaces have passing evidence, supported fixtures
have no unexpected unexplained required changes or unresolved required links
(deliberately injected gaps must produce the expected audit), resume/branch
and UI parity checks pass, and agreed performance budgets are met. Any remaining
unsupported surface must be explicitly scoped and visible; it cannot silently
count as complete.

## First implementation slice

Start Phase 0 with the writer/metric gap register, then implement Phase 1's
military/medical account probes. Exercise full and partial payroll, procurement,
public/private treatment and self-payment/refund. Run public-account, bank,
existing military/medical and trace-on/off parity tests, update the register and
commit. Follow with bank rescue and sovereign cash settlements. No new player
mechanic or general rewrite of money settlement is required for this slice.

## Progress

- Planning source review complete. Gap-register discovery and the first military/medical runtime slice are implemented.
- Current baseline: `b4dfe05`; the latest short default probe is
  `tmp/trace_coverage_default_treasury_chains_2026_10_22.json`.
- Phase 0: in progress. The register discovers 508 financial-write candidates,
  381 metric declarations and 89 history fields. Eleven military/medical writes
  have explicit source reviews; 497 financial candidates still require review.
  Active scenario paths and UI bindings are not yet fully classified.
- Phase 1: military/medical slice implemented. Public account writes link to
  existing payroll, procurement and treatment records; full/partial/unfunded
  cases and self-refunds have deterministic fixtures. Added the missing ration
  treasury outflow and public medical-provider receipt without changing money
  settlement. Bank rescue, bond cash, construction and other writers remain.
- Verification: 47 focused tests and 63 recorder/web parity tests passed. The
  three-turn default probe still verifies nine treasury closures and all 144
  changed bank stocks, with three valid compact checkpoints.
- Registry details, regeneration commands and limitations:
  [coverage README](coverage/README.md). The Phase 0 global classification gate
  remains open while source-reviewed subsets receive runtime probes.
- Phases 2–8 and the remaining Phase 0/1 gates are pending.


### Financial slice progress

Bank rescue debits, sovereign issue/purchase/coupon/maturity/redemption cash
legs, rating-agency fees and construction subsidy debits now have stock probes.
Existing semantic settlement records link to those writes; rating fees have
signed flow records. Domestic cash creation and rescue alias behavior are
preserved. Four new financial fixtures plus banking, subsidy, treasury, recorder
and inventory regression suites passed 63 tests. Source reviews now cover 31
of 508 candidates (some with explicitly partial branch evidence); 477 remain.
Live-offering and unusual counterparty acceptance remains open. Next: political,
manual and scenario writers, then timed composition transitions.


### Political/manual/scenario writer progress (2026-10-23)

Installed 127 explicit conditional public-account probes in political actions,
manual transfers, frontier/supply/Egypt payments, diplomacy, innovation funding,
workhouse and market public receipts. Registered public agents can resolve their
trace source without a region argument; private wallets do not acquire public
entries. Existing scenario/political/payment regressions passed 81 tests. Native
equalization and seizure fixtures verify zero-net internal transfers and actual
seizure account closure. Source reviews and complete semantic payment-to-write
link contracts for these new paths remain pending; installed probes do not by
themselves finish Phase 0 or Phase 2 acceptance. Timed composition is next.


### Timed composition progress (2026-10-23)

Native nation add/remove/transfer, province institution assignment, and regional
bank/government setters record timed accounting-boundary transitions. Treasury
replay interleaves owned-interval account writes with entry/exit balances at the
actual transition; it does not substitute final balances. Nested setters are
recorded once. Direct uninstrumented pointer/list edits still produce audits.
Five new fixtures cover post-departure spending, out-and-back transfers, shared
accounts with retained aliases, new bank association and missing transitions.
Composition/public/fiscal checks passed 25 tests; recorder/catalog/inventory/web
checks passed 71. A fresh default probe verifies three compact checkpoints and
keeps all treasury and bank changes explained (114,757 rows). Report:
`tmp/trace_coverage_default_composition_2026_10_23.json`. Creation/removal of
nations outside native setters and arbitrary direct edits remain unsupported
composition paths; provenance and complete scenario gates are still open.
