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

At plan start, a three-turn default probe verified nine treasury account closures and
144 changed bank-stock snapshots. It does not exercise war, default, coups,
annexation, many scenario actions, save/resume or long-run performance.

## Starting source findings (2026-10-22)

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

## Current completion gates (2026-10-23)

| Phase | Implemented evidence | Remaining gate |
|---|---|---|
| 0 | Writer/metric/history inventory; 31 source reviews of 507 financial candidates | 476 reviews, active-path and complete history/UI classifications |
| 1–2 | Military/medical/sovereign/rescue/subsidy fixtures; 127 further public probes; command boundaries | Rare branches and complete semantic payment-to-write contracts |
| 3 | Timed native ownership/institution setters with shared-account fixtures | Additional nation creation/direct edits and scenario acceptance |
| 4 | Independent economic replay, stock/source contracts and linked snapshots | Unsupported AI/scenario formulas and complete per-metric provenance |
| 5 | Atomic full SimServer saves, branches, recovery; full economic graph/RNG/action equality in fresh-process default continuation | All-scenario continuation acceptance |
| 6 | Block index/rebuild, stable queries/export, bounded identity cache and streamed CLI comparisons | Measured memory/query/runtime budgets and retired-reference audit |
| 7 | Shared web/desktop/CLI explanations, native recording, F11 inspector, historical membership and iPad browser checks | Full scenario/history acceptance and physical-device follow-up if available |
| 8 | Short probes and deterministic negative fixtures | Multi-seed 30/100-turn acceptance, off/on state/actions and published budgets/report |

Latest short acceptance: `ce15dcf`, four canonical scenarios × on/off, three
steps each, all checks pass. Matrix: `tmp/acceptance-smoke3-2026-10-23/matrix.json`.
The release matrix finished from a pinned archive of that commit and failed its
long-run gates. Its results
do not certify later edits until affected gates are rerun.

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


### Provenance audit progress (2026-10-23)

Added a streaming, disk-backed audit for event identity, sequence/checkpoints,
declared cause links and supported formula replay. Unsupported formulas and
calculations without formula contracts are reported independently; the report
never labels those as complete causality. Price snapshots now require a verified
ordered price bridge, preventing a coincidentally matching last calculation
from concealing a broken stock chain. Audit/recorder/codec checks passed 43 tests.
The per-metric required-input/source contract inventory remains open; this slice
is a structural validator, not a declaration that all metrics are complete.


### Native command correction (2026-10-23)

Command-boundary review found the bond rating lobbying command passed a string
and an unsupported keyword to the native rating API after charging the fee. It
now passes the Nation and turn and lets the native API settle the fee once. A
command fixture verifies the $200 debit and unchanged game turn. This gameplay
correction is committed separately from trace storage and lifecycle changes.


### Trace boundaries and indexed storage progress (2026-10-23)

New `.ctr` files use checksummed record frames in independent 256-record
compression blocks. Complete published byte boundaries support indexed seeks,
stable pages and export while autoplay continues. SQLite indexes rebuild after
deletion or database corruption; source corruption fails decoding. Recent event
identity memory is bounded to 4,096 entries with indexed cold lookup. Export
releases the simulation lock before scanning or network streaming.

Mutating server commands now close a separate trace epoch without advancing
game time. Optional client/command IDs return the persisted original response
on retry and reject conflicting reuse. A native economic command fixture
verifies a single debit, command-to-write causes and verified treasury closures
through the next turn. Storage/recorder/web/bond checks passed 69 tests; focused
retry/index checks passed two more. Existing trace input is intentionally not
supported. Full simulation checkpoint publication/restore, recovery, browser
retry IDs, memory/performance budgets and the remaining global gates are open.


### Full simulation checkpoint progress (2026-10-23)

Implemented trusted local checkpoints containing the live world, shared object
graph, discovered gameplay module/class registries and imported mutable aliases,
Python/NumPy/cached random state, pending causal maps and account books. Source
and runtime fingerprints fail closed across incompatible rules. Native ontology
callbacks are resolved against validated code; no gameplay registry is omitted
when serialization fails. Immutable state and trace files are fsynced before an
atomic manifest is published. Restore always forks; inherited event/account
identities remain stable, new branch identities are distinct, address-based bank
and public-account keys are rebuilt, and retry responses survive restore.

Default-world tests compare every sampled metric and RNG state after the next
turn, including a fresh-process continuation, command deduplication, source
preservation, failed manifest publication, damaged state and torn-tail recovery.
Interior corruption is rejected. Three integration fixtures also verify pending
cargo delivery, shared loan references/repayment and retained technology causes.
Checkpoint/inventory/codec/recorder/web checks passed 72 tests. Multi-scenario
and long-run acceptance remain open.
The bond command correction removed one obsolete direct debit; its reviewed
removal is reflected in the financial-write baseline (507 candidates, 31 source
reviews, 476 pending).

Local usage: `venv/bin/python simulation_checkpoint.py --turns 3 --directory
tmp/checkpoints` prints the committed manifest. Continue with `--restore
<manifest> --turns 3`. The web server accepts `--restore-checkpoint <manifest>`
and resumes paused on a new branch. These saves are separate from map presets.


### Checkpoint acceptance refinement (2026-10-23)

Broader test ordering loaded the scenario evaluator's static lambda dispatch,
which standard serialization cannot reference by name. Replaced its two logical
callbacks with equivalent module functions so the registry is retained. Another
continuation fixture created new UUID-based projects; sampled-metric comparison
now normalizes project identity by tile and native creation order while retaining
all values and references. This is explicitly a metric comparison, not a digest
of every internal model field. The combined recorder/checkpoint/source-audit
checks passed 51 tests after these findings were corrected.


### Independent formula and required-source progress (2026-10-23)

Added independent replay for cash/deposit and FX transitions, production and
tribute, GDP/inventory/population aggregations, wages/work hours, nutrition,
mortality/treatment, ecology, legitimacy and trade values. Captured missing
primitive FX adjustment speed/caloric conversion inputs and exact production
receipts; retained full tenure precision. Disease case counts now include the
actual counted patient IDs. Construction funding priority is a decision record.

Stock closures, production totals, ordered price bridges and explained snapshots
now have explicit required-source checks. Snapshots link their actual producing
record. Matching arithmetic cannot conceal an omitted required cause, a different
physical account or a contradictory source value. A negative fixture removes a
required link while keeping the number correct and verifies that the audit fails.
Six independent replay fixtures perturb primitive inputs and retain unsupported
formulas as unsupported. Combined recorder/financial/checkpoint/flow checks passed
58 tests. Fresh default seed-4242 three-turn evidence has 114,376 rows, 35,949
formula matches, 17,030 required-source contract matches, three checkpoints and
no unexplained changed snapshots or structural failures. It still contains 6,583
unsupported replay records and 41,764 formula records outside required-source
contracts; these remain explicitly unverified. Report:
`tmp/replay_source_contracts_default_2026_10_23.json`. AI/scenario formulas and
full per-metric provenance contracts remain open.


### Bounded inspection and durable retry progress (2026-10-23)

CLI reports and paired-run snapshot comparisons stream with bounded buffers;
comparison joins use temporary SQLite storage. Live queries release the simulation
lock before indexing/decoding. Per-file index locks serialize concurrent cache
updates; deleted/corrupt/incompatible sidecars rebuild without treating lock
contention as corruption. Fixed-boundary concurrent queries agree with sequential
results while source appends. Decoded frame limits are checked before publishing.

Browser transport assigns a fresh action ID for each deliberate command and
reuses it after a lost response. The HTTP endpoint preserves those IDs. Step,
world reload and exceptions after partial account writes have durable receipts;
retries return their recorded outcome without repeating the action. Partial
failures close their observed state, and a recorder failure prevents another
mutating command from being mistaken for a retry. Existing moving-average
comparison assertions now use the chart's actual two-decimal demand-ratio
precision, and compact-download tests use the current codec magic. The recorder,
index, command, reader and web regressions passed 71 tests; focused reader/index/
historical membership checks passed 23. The JavaScript transport check verifies
identical retry bodies and a new ID for a new action. Memory/runtime budgets and
full long-run acceptance remain open.


### Shared player explanations and native recording (2026-10-23)

Added one explanation model for web/iPad, desktop and CLI, including local source
validation, explicit observation/forecast/formula/chain/gap labels and the largest
recorded contributors. Treasury separates known receipts/spending, confirmed
internal cash/deposit moves, timed membership effects and flow residuals. Numeric
reconciliation never certifies complete payment classification. Raw values and
IDs remain available through disclosures and source links.

Both native world builders now attach a recorder; pending player actions close
before a new gameplay turn can reset their evidence. F11 opens a paged native
inspector for treasury, prices, unrest, FX and nation AI, including historical
turns, source paging and Back. Native chart aggregation uses recorded former
membership when available. The web inspector retains stable boundaries across
pages and cause navigation and uses touch-sized, named account buttons.

Reader/native/checkpoint/inventory checks passed 31 tests, reader/index/historical
membership checks passed 23 and recorder/index/command/web regression checks
passed 71. Targeted HTTP/model parity passed; browser transport checks passed.
An isolated Chrome iPad-sized touch check passed treasury values, 44-pixel targets,
account-source navigation, empty and request-error states. Native and iPad
renderings were visually checked (`tmp/desktop-causal-evidence.png`,
`tmp/ipad-causal-evidence.png`). No physical iPad test is claimed. Reproduction
commands and evidence labels: [inspection guide](trace_inspection_guide.md).
The gate table above remains authoritative; full scenario/provenance/performance
acceptance is still pending.


### Stable contractor names before semantic acceptance (2026-10-23)

The acceptance review found contractor names interpolated a bound `Agent.name`
method, embedding a process address in company names and logs. The founder's
name method is now called; string-name fixtures remain supported. This display
correction is isolated from instrumentation. Ten construction/treasury-flow
checks and a native founder-name assertion passed.


### Epoch-aware labor/faction source correction (2026-10-23)

The broader acceptance review found two source-link guards still comparing the
recorder's `(turn, epoch)` boundary with a plain integer turn. Final labor census
and faction histories now compare the full boundary, retaining current career,
status, food-intake, grievance and tax source links. The existing labor census,
faction history and recorder suites passed 45 tests, including assertions on the
actual upstream event IDs. This is a trace-only lifecycle correction.


### Deterministic geography tie breaks for acceptance (2026-10-23)

Fresh-process comparison exposed an existing world-generation instability:
province BFS chose equally distant remaining nodes from a Python set, so object
allocation addresses could change district assignment and initial agent locations
under the same seeds. Equal-distance choices now use native input order; Voronoi
adjacency is installed in center-index order. The source correction is separate
from instrumentation. A hash-layout fixture verifies equal partitions under
three object hash arrangements; existing generation, clustering/connectivity and
degree-cap checks passed (four tests). No current live world's territory is
rewritten by this change. Acceptance proceeds against the deterministic rules.


### Full economic state acceptance tooling (2026-10-23)

Added a real recorder-off option for both canonical runners and a fresh-process
acceptance harness. The comparison retains economic quantities, native ordering,
shared aliases, pending objects, callback closures, gameplay globals and Python/
NumPy RNG. Registered domain UUIDs are renamed consistently; explicit observation
fields are counted separately. Unknown native state objects fail serialization.
A one-dollar change, changed policy ordering, changed alias and changed callback
closure all produce differences in negative fixtures.

Default seed 4242, three turns, now produces the same full state digest with
recording on and off. A marshal-based code fingerprint initially produced a false
callback difference; stable bytecode/constants fingerprints now retain rule
identity without marshal interning artifacts, also protecting checkpoint callback
validation. Seven semantic/checkpoint tests passed; the first test invocation
also named a nonexistent command test module, which is rerun under its real name.
These preliminary timing measurements were concurrent with tests and are not
benchmark baselines.

The sequential matrix runner pins a committed Git source archive so later edits
cannot mix rules within a run. Smoke coverage uses all four canonical scenarios.
Release coverage uses two seeds, 30/100 default sandbox turns and the authored
20-turn scenario horizons (or earlier native endings). Completed turns are
reported honestly; terminal campaigns are not forced to continue to 100 turns.
Full scenario equality, measured budgets and remaining provenance gates stay open.


### Authored-scenario acceptance findings (2026-10-23)

The first pinned smoke matrix (`9c6dbf5`) passes default, but correctly leaves
frontier, supply and Egypt failing. Frontier/supply expose missing public-account
probes in named obligation settlements, public taxpayers and labor-law petition
fees. Added actual before/after probes and linked obligation and petition records;
public creditor, debtor and internal-transfer fixtures pass alongside existing
closure and state-normalization regressions (17 tests). No money rule changed.

Native journals share the recorder clock: inserted trace rows change sequence
numbers, while append order is the same. Acceptance now ranks recorded journal
sequences globally, preserving order and ties across journals; a reversed-order
negative fixture still fails. The labor-surplus source ID is observational and
explicitly omitted; all surplus amounts remain. Egypt starts at turn 1, so the
harness now reports starting/final turns separately from completed steps.

Egypt also exposes late public receipts, disease counts changing after treatment,
and a legitimacy record whose extra subject dimension prevents snapshot matching.
These remain active repairs, not accepted coverage. Currency-audit violations in
Egypt also require investigation against the recorder-off run. The release
matrix will follow the corrected short gates.


### Egypt sampling and geography corrections (2026-10-23)

The native disease chart stores pre-treatment case counts, while snapshots had
used closing live counts. These are now separate metrics: `health.disease_cases`
uses the actual chart history, and `health.active_disease_cases` records the
closing live census. A cured-patient fixture verifies history 1 versus live 0;
no treatment or gameplay timing changed. The foreclosure legitimacy record now
uses the national scalar subject and retains the affected person in its inputs.

The full Egypt graph also exposed nondeterministic equal-flux river decomposition
from set iteration. Stable corner-index tie breaks are committed separately as
`d063a73`; three hash-layout fixtures plus polygon/geography tests passed (20
tests). River paths remain part of acceptance state because scenario generation
uses them to select the Nile. They were not hidden by the comparator. The one
Egypt currency violation (-5 EGP at turn 2) is identical with tracing on/off,
so it remains a separate accounting investigation, not a recorder divergence.


### Native scenario rerun and abstract military sink (2026-10-23)

Pinned smoke rerun `d58e81d`: all four scenarios have identical complete economic
state/RNG/actions with recorder on/off. Default and frontier also pass all short
closure/snapshot/structural checks. Egypt now has no unexplained changed snapshots
or public-account gaps; its remaining -5 EGP warning was located at the existing
abstract Alexandria garrison payroll: treasury cash is debited, but abstract units
have no soldier wallets. That real sink was absent from the destruction ledger.

The military correction records only the actual abstract-service expense in the
existing destruction ledger and emits a linked cash-destruction record. It does
not alter pay, treasury balances, morale or personnel. Four full/partial/unpaid/
concrete-personnel accounting cases plus existing military/treasury regressions
passed (14 tests). Concrete soldier payments never receive a sink exemption.
This accounting correction is committed separately from instrumentation repairs.

Supply's remaining 1.6-unit account gap was located at government freight-carrier
receipts; freight and concession fee probes are installed and the native three-
turn frontier/supply account regression passes. Including market-route, supply-
rights and cadastral source tests, 31 tests passed. A new pinned smoke run and
the release matrix are next; long-run gates remain open.

### Full continuation and additional replay evidence (2026-10-23)

The default checkpoint regression now compares the complete canonical economic
graph, shared references, pending state, native journal order, histories and RNG
after uninterrupted versus fresh-process restore/continue. Both that fresh
process and same-process restore match exactly; sampled metrics and retry checks
also remain in the fixture. This closes the default full-state gate, while other
scenario continuation cases remain pending.

Added independent arithmetic for water capacity/weather, construction materials/
labor progress, wage cash/tightness/cap gates, nonfood consumption draws, rent
rollups, workplace accidents, sabotage/broken stock and zero-order counts.
Market sold-unit summaries now retain each settled sale quantity and require
matching upstream sale identity, good, tile, amount and declared links. Negative
fixtures change primitive inputs or remove/misdirect a source while leaving the
claimed result unchanged. Initial Gini and collective journal observations no
longer carry misleading formula identifiers. Eleven replay tests and 33 market/
labor/catalog regressions passed. Existing default trace records produce no new
unexpected replay mismatches under the expanded independent replay.

### Diagnosed append overhead (2026-10-23)

The short baseline writes 8.97 MB / 114k rows in three default steps (8.25s with
recording versus 1.33s without). Egypt writes 37.89 MB / 780k rows (53.09s versus
1.91s). These establish a performance problem; they are not accepted budgets.
Writer source review found a file open/close and stat for every record. One owned,
unbuffered append handle now writes the same framed bytes and publishes its byte
boundary only after a complete successful write. A forced short write leaves the
published boundary intact and the damaged tail detectable. A 20,000-record
comparison with the pinned old codec produced identical 508,637-byte files:
0.668s before versus 0.091s after on this host (about 7.4× for append alone).
This microbenchmark does not establish total-turn speedup. Full native run/query/
recovery correctness and measured final runtime budgets remain required.

### Long-run acceptance findings and repair queue (2026-10-23)

The frozen `ce15dcf` release matrix completed: nine simulation pairs produced
reports, and Egypt seed 1878 failed map construction in both recorder modes.
None of the nine pairs passed all gates. Reports are in
`tmp/acceptance-release-2026-10-23/matrix.json`; this is failure evidence, not
release acceptance. Two supply-scenario pairs already preserve the full economic
graph; other differences include trace-only proposal/petition source identities.

The longer runs exposed public actors entering nominally private contractor,
payroll, trading and policy paths. Conditional probes now surround 236 additional
cash mutations in 48 modules: they activate only for actual government actors,
capture before/after at the mutation, and retain the inventoried writer identity.
These probes do not constitute completed source reviews or balanced-transfer
contracts. A government-contractor fixture checks material purchases and actual
navvy payments against public-account closure.

Additional repairs in progress: sample Gini inputs at the native history writer;
capture shared-government tax writes and coup legitimacy resets; distinguish the
existing emergency forage and fractional charity issue rules in replay; link
wilderness production/GDP/population and the lagged disease-fatality series to
their actual contributors. Preserve native economic behavior while repairing
observations. The default seed 4242 CNY audit loss (first turn 30, -10.56) still
needs an actual accounting explanation; no balancing exemption is accepted.
Egypt's second-outlet map failure needs a separate geography correction.

After these repairs, commit the source and rerun affected native pairs from that
immutable revision. All-scenario checkpoint continuation, complete writer and
history classification, unsupported formula/source contracts, retained object
lifetimes and final measured performance budgets remain open.

Native sampling repairs are now implemented. Wilderness production uses actual
forage receipts; GDP uses those units and the contemporaneous reference price;
population uses the resident IDs at the history write. Disease-fatality samples
retain threshold-crossing mortality contributors across the native counter's
one-turn sampling lag, including required mortality-source identity/value
contracts. A missing positive contributor fails replay. Four new fixtures cover
late cash/membership changes after Gini sampling, held Gini provenance, lagged
fatality/reset/source tampering, missing fatality contributors and forage output.
Verification: 102 focused trace, account, scenario, replay and inventory tests
pass together. The separate campaign suite exposes one existing funding-source
fixture failure; running it after hex-world tests also exposes a topology-global
fixture dependency. Both remain in the follow-up queue rather than being counted
as passing verification.

### Acceptance fixture and alternate delta repair (2026-10-23)

The campaign fixture now selects/restores its required Voronoi topology and
attaches its test recorder to every native tile/nation. Funding sampled on a
different tile is therefore visible to the action's source checks. The combined
coup/campaign suite passes 17 tests, including the previously missing funding
record. The Egypt delta keeps its existing preferred-coast searches, then tries
a bounded nearby northern outlet on either side only when both fail. A geography
regression verifies distinct coastal outlets, a continuous connected branch and
idempotence for release seeds 1877/1878. Full seed-1878 simulation acceptance
still requires a rerun. This map correction is separate from trace allocation.
