# Candidates for substantially fewer generated trace events

Analysis: 2026-10-27. Current recording implementation: `5148212`.
This is a candidate breakdown; no production recording policy changes here.

## Current count and scope

The measured default native world has 1,000 tiles, seed 777. Turn 2 contains
**262,026 logical records** in **2,217 packed packets containing that turn**.
The latest optimizations deliberately preserve event count and original
evidence while reducing construction, copying and serialization costs.

The next step must change event granularity: record actual changes/actions and
group checked state coverage, rather than create an event ID, emitter call,
known-event cache entry and SQLite row for every unchanged stat each turn.
Packing more rows into a packet alone does not accomplish this.

Counts below come from the latest retained optimized trace in
`national_causal_trace_optimization.json`. Its original event rows were verified
equal to the previous recorder apart from additional summary fields. The
turn/epoch-gap guard added afterward does not change this consecutive-turn
sample. This mostly-wilderness early world is not a representative benchmark
for every populated or crisis scenario.

## Disjoint replacement pools

| Candidate | Current records, turn 2 | Share of all records | Replacement and evidence to preserve |
| --- | ---: | ---: | --- |
| Unchanged stat snapshots | 179,316 | 68.4% | Checked state coverage by tile/nation and metric domain. Preserve baseline, current source, dimensions, units, rule/coverage status and exact effective turn/epoch. Keep changes and missing baselines explicit. |
| No-write unchanged price bridges | 18,925 | 7.2% | Record a checked no-price-write flag in coverage instead of a separate bridge per good. Keep full ordered reconciliation for any writes, gaps, or mismatch, including offsetting writes. |
| Fixed/retained Gini calculations | 19,012 | 7.3% | Fixed-zero rule coverage (18,772) and original-sample references between refreshes (240). Keep actual refresh inputs, fixed-to-active transitions and effective dates. Resolve existing source chains through anchors instead of dangling IDs. |
| Empty active-disease closing censuses | 4,998 | 1.9% | A checked disease-domain zero set per tile. Preserve earlier exposure, onset, treatment, mortality, nonempty censuses, and transitions to zero. A zero closing count does not imply no disease activity during the turn. |
| Empty tax-distribution calculations | 3,952 | 1.5% | Checked empty allocation coverage. This pool has no recorded receipts and all opening distribution components zero. Keep actual tax receipts, payments, account writes, nonempty receipt allocations, source links and reconciliation. |
| Empty labor rollups and zero person counts | 4,964 | 1.9% | Group empty labor cohorts (1,976), zero birth/death counts (2,000), and zero living-person counts (988). Preserve eligibility rules, births/deaths/migration/conversions, source gaps and category entry/exit. |
| Other quiet derived samples | 7,952 | 3.0% | Use state/rule references where valid; derive simple outputs from retained inputs when queried. Check dependencies and statuses first—zero does not establish inactivity. |

The first five rows total **226,203 records (86.328%)**. They are already
unchanged-state or exact inactivity/template candidates, making them the first
implementation pool. The last two rows total **12,916 (4.929%)** and require
additional rule/dependency review. All seven rows are disjoint by event kind
and condition: **239,119 records (91.258%)** in the combined investigation pool.
These are replacement pools, not an authorization or proof of safe deletion.

The 843 remaining snapshots have changed values or lack an opening baseline.
Keep these explicit initially: removing their individual events adds little
count benefit and complicates the most useful change explanations.

## Details of the secondary derived pool

| Kind / condition | Count |
| --- | ---: |
| Unchanged effective workday cap samples | 1,000 |
| Zero in-transit pipeline depth | 1,000 |
| Zero population growth rate | 1,000 |
| Zero wilderness food production with no source causes | 988 |
| Empty wilderness resident census | 988 |
| Zero trader cash sum with no source causes | 988 |
| Zero export-value calculations with no source causes | 1,000 |
| Zero import-value calculations with no source causes | 988 |
| Total | 7,952 |

Inspect inputs rather than values alone. For example, the sampled population
growth formula returns zero with only two observations because it requires ten;
the record also shows a current population of 99. Replace that event with an
explicit insufficient-history rule/status, not an assertion of no population
change. Likewise zero in-transit stock does not rule out shipments that arrived
during the turn or goods on parked/pending routes.

Zero wilderness GDP and net-trade records are deliberately excluded from this
particular secondary count when they have linked causes. Some could eventually
be represented as exact derived views, but their upstream references must be
preserved rather than treating them as unreferenced empty events. No blanket
wilderness trace exclusion is proposed.

## Additional smaller candidates

- A paid sale, its unit-price observation and seller receipt occur 1,303 times
  each in this turn. A canonical settlement containing the complete quantity,
  price, payment, receipt, tax/fee and account-leg evidence could replace three
  records with one. The ceiling is about **2,606 fewer records (1.0%)** if all
  groups can be safely matched. Equal counts alone do not prove that matching;
  partial/failed settlements retain their distinct evidence.
- Buyer order submission and bid-price calculation each occur 2,285 times.
  A complete order record with funding, requested quantity, price limit and
  the limit's formula could save up to **2,285 (0.9%)**, subject to matching and
  lifecycle review. Keep rejected, unfunded and unfilled orders and reasons.
- Duplicate aggregate representations can become derived query views when
  their exact membership, currency, timing and reducer semantics match. Do not
  assume similarly named tile/national/chart series are interchangeable.
- Routine repeated AI evaluations are possible later targets with explicit
  unchanged-decision coverage. Keep binding constraints and failed actions:
  these can explain why relief, imports or employment did not respond.

Transaction representation work is a smaller opportunity than removing the
per-stat observation fan-out. All actual economic legs and gross directions
must remain available even if several projections share one canonical event.

## Count projections, not measured speedups

Replacing the primary pool with roughly 1,000–6,000 bounded grouped coverage
records would yield approximately **37,000–42,000 records per turn**, versus
262,026: **84–86% fewer**. The overhead range is an illustrative assumption,
not a measured certificate design. Arrays, source diversity, byte limits,
membership changes and active rules determine the actual group count.

If the secondary pool also qualifies, sharing coverage across those categories
could bring this sample toward **24,000–30,000 records**: about **89–91% fewer**.
Treat this as a sizing target for this world, not a universal promise. Actual
market activity, many populated regions, disease and policy crises can increase
the irreducible evidence substantially. First-turn baselines differ from this
steady-turn comparison.

Fewer event objects and index rows should reduce overhead, but these percentages
are not turn-speed predictions. The simulation must still compute economic
outcomes and check coverage. A giant record containing the same fully built
per-stat events would change the counter without removing much CPU work.

## Required representation and query changes

1. Separate event records from checked state coverage. Emit coverage arrays or
   bounded domain certificates directly; keep genuine changes/actions explicit.
2. Store a baseline plus checked intervals/rule coverage, with explicit invalidation
   for subject/dimension, unit, membership, source, rule and epoch transitions.
   Missing intervals remain unknown. A new source at the same value remains a
   new explanation even if it does not need another full observation event.
3. Index coverage groups/ranges, not one expanded SQLite row per virtual sample.
   Historical F12 metric discovery and exact tile/stat/turn selection must read
   both real events and covered state, including known zeros.
4. Resolve source references through baseline/coverage anchors or reserved ID
   ranges without eagerly materializing one logical event per stat. Preserve
   old-file reads and provide an explicit virtual observation view where needed.
   Current consumers assume numeric event sequence ordering, so ordering and
   fixed-prefix semantics need a versioned compatibility design.
5. Report actual event count, coverage-group count, and virtual sampled-value
   count separately. Do not claim a logical count reduction while indexing every
   reconstructed sample as another event.
6. Validate source links, gross-flow reconciliation, offsetting activity,
   historical queries, first baselines, rule transitions, incomplete coverage,
   formula replay, corruption, checkpoint forks, complete economic/RNG parity
   and populated/crisis scenarios. Measure emission, cold/warm queries and
   whole-turn time separately.

Actual taxation, government spending, cash and goods transfers, debt/default,
production shocks, disease/mortality, migration, policy changes, failed actions
and unexplained residuals stay available. A flat national total can hide large
opposing regional or cohort changes; national-only totals are insufficient.

The recommendation is to implement the primary state-coverage/index redesign
first, keep detailed action/flow events, and assess the secondary derived pool
afterward. This is a materially larger count reduction than another packing
optimization. Detailed measured counters and illustrative input records are in
[the JSON analysis](trace_count_reduction_candidates.json).

Implementation follow-up: the primary grouped-state/index redesign is complete.
Default turn 2 now emits 40,263 actual events/groups instead of 262,026, with
identical expanded evidence and preserved gross financial flows. Initial
readings use a separate unknown-opening rule. The secondary pool was assessed
and remains explicit pending category-specific rules. See
[the implementation measurements and validation](state_coverage_event_reduction.md).
