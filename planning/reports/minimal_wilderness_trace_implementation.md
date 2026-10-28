# Minimal wilderness tracing: implementation and acceptance

Implemented 2026-10-27 from base `5246fe9`. The
[plan](../minimal_wilderness_trace_plan.md) and
[raw measurements](minimal_wilderness_trace_implementation.json) describe the
capture contract and acceptance evidence.

## Measured result

Native default map, 1,000 tiles, seed 777, first ten turns. Same-source full and
minimal policies ran in fresh sequential processes with `PYTHONHASHSEED=0` and
all V5 grouping optimizations enabled. No concurrent heavy tests ran during
timings. Construction, state hashing, index queries and profiling are outside
the measured step intervals. These are single local observations per policy.

| Measure | Full wilderness capture | Minimal wilderness capture | Reduction |
| --- | ---: | ---: | ---: |
| Ten turn steps | 33.199 s | 12.174 s | 63.3% |
| Average step | 3.320 s | 1.217 s | 63.3% |
| Stored events/groups, including setup | 418,081 | 213,118 | 49.0% |
| Expanded records, including setup | 2,617,864 | 227,565 | 91.3% |
| Trace bytes | 47,113,174 | 18,531,272 | 60.7% |
| Cold active-tile F12 catalog | 12.103 s | 4.093 s | 66.2% |
| Warm active-tile F12 catalog | 2.624 ms | 2.713 ms | Similar |

The active tile has the same 958 catalog options. Ordinary step speedup is
**2.73×** in this sample. Turn 2 falls from 40,263 to 21,526 stored records and
262,026 to 22,977 expanded records. Most omitted facts cease to exist, rather
than becoming virtual entries reconstructed by the reader.

Egypt's two native steps (turns 2 and 3, because setup starts at turn 1) fall from
7.026 to 2.669 seconds total: **62.0% less step time**. Stored records fall from
101,722 to 46,678 and expanded records from 527,764 to 49,860. Its selected quiet
tile has eight meaningful frontier choices, versus 181 padded/full choices.

## What quiet wilderness records now

For the default map's 988 eligible wilderness tiles:

- Setup: two initial-state batches and two domain-coverage cohorts.
- Each completed turn: two exact-turn/epoch cohorts, covering no operating
  economy, no resident agents and the checked frontier fields.
- First actual price consumption: 187 reference-price observations across 11
  tiles, reused through the measured ten turns. Egypt uses 204 across 12 tiles.
- Real environmental effects: seven downstream pollution events, six changed
  water snapshots and six refreshed state anchors per default turn.
- Cause-bearing trade detail: 33 export/import/net summaries across 11 tiles
  per turn. These survive even where a net or gross total is zero; empty totals
  alone do not prove that the underlying evidence is unnecessary.

That is **54 quiet-wilderness/policy records per steady default turn**, plus
newly needed observations if values or activity change, instead of 18,791
directly scoped records in the original turn-2 analysis. The additional first
turn quotes and initial batches are separate from that steady count.

The six frontier fields are background native population, soil fertility,
nutrition density and air/water/soil pollution. Native inhabitants are not
misreported as resident agents or as an operating market. Fixed cohorts contain
at most 512 tile IDs and refer to bounded initial state or changed state anchors.
The disposable index has one wilderness row per cohort, without per-tile/stat
padding. A missing turn/epoch remains unavailable.

## Implementation boundaries

`WildernessTrace` owns eligibility, baseline/state references, consumed quotes
and transitions. Empty faction and route scaffolding is eligible; actual cargo,
members, institutions, residents, military, construction or nation membership
select full capture. Nonzero birth/death counters also prevent a falsely quiet
ending census. Regime changes invalidate quote caches; reentry or a recording
gap establishes a fresh frontier baseline.

The sampler bypasses economic history/goods collection before its large
per-metric dictionaries and identities are built. The wilderness writer skips
routine production/GDP/census/Gini/labor/tax trace construction while preserving
the original histories and foraging behavior. Generic closing snapshots, labor
censuses and empty trade trace emission are skipped for eligible tiles. History
scaffolding and the short three-good flow check remain.

On-use price sources cover existing route, investment, labor, innovation and
national-aggregation lookups. Migration's direct neighbor-price read also gains
links at the real pressure gate. UI score previews remain read-only. Quotes
freeze the actual current recipe value and explicitly identify their non-market
basis. They do not become clearing prices, transactions or invented price deltas.

F12 and chart requests on padded quiet stats receive a deterministic local
applicability answer, including without an API key. Watched frontier fields
resolve their recorded historical value; real changed snapshots retain the
ordinary causal/AI path. F11 also explains an empty quiet price selection.
Loading and on-demand generation behavior remain intact; there are no background
provider calls.

## Verification

- **277 regression tests passed**, including 18 new policy-focused tests,
  national contributions, fiscal/medical/treasury flows, codecs, fixed prefixes,
  corrupt records, index rebuilding, command epochs, quote reuse/value changes,
  migration-price links, homesteader foraging, real cargo/factions, unknown
  openings, native-population gaps and local answers without a provider.
- **Four server checkpoint tests passed**, covering same/fresh-process forks,
  RNG/shared accounts/retries and damaged-save gates.
- **One native Egypt checkpoint test passed**, checking the complete economic
  graph in same/fresh-process continuations and preservation of the parent.
- Default ten-turn and Egypt two-step **complete economic graphs, sampled
  metrics, Python RNG and NumPy RNG match** between full and minimal policies.
  Canonical comparison preserves financial quantities, inventories, populations,
  histories, rules, shared references and gameplay ordering; observational IDs,
  registered domain UUIDs and inserted journal-clock gaps are normalized.
- Both minimal traces pass integrity, checkpoint, source-link and supported
  formula audits with no issues. Unsupported formulas/source contracts and
  preexisting explicit source gaps remain limitations, not inferred proof.

Protected-event comparison remaps event identities by turn/epoch/phase,
subject/metric/kind and occurrence. Quiet price sources map by tile/good/value;
observation date intentionally changes to the consumption point. Clock-derived
operation IDs are consistently renamed while preserving their associations.
First-read quote links can improve formerly absent source links; each such
addition is checked against the decision's frozen tile/good/price input. All
economic values, constraints, results and preexisting protected source edges
remain part of the comparison. Detailed results are in the raw report.

**227,283 protected default records and 49,643 protected Egypt records match**,
with no missing, added or changed protected events after the stated identity and
new-source handling. Default validation checks 1,428 newly available route-input
quote references across 54 decisions, plus 14 new migration food-source edges.
Egypt checks 1,326 route-input references across 60 decisions, plus 13 migration
food-source edges. These counts include repeated references to reused quote
observations; they are not unique prices or provider calls.

V3/V4 remain readable and full-policy runs keep full capture. Pre-policy saved
recorders without a wilderness-policy field rebind as full. New minimal saves
retain state anchors and quote sources across forks. V5 framing, hash scopes
and expanded/stored count meanings are unchanged; normal checkpoint source
compatibility still applies. `COC_TRACE_WILDERNESS=full` selects diagnostic full
capture for a new run.

## Remaining hot loops and limits

The separate minimal cProfile run has 138.6 million calls and 32.321 profiled
seconds, versus 397.9 million and 96.272 seconds in the earlier full profile.
Profiler overhead means these are rankings, not gameplay latency estimates.
Minimal profiled counts, metrics and RNG match its ordinary timing run.

Closing `trace_snapshots.record` falls from 51.788 to **3.191 cumulative profile
seconds**; recursive input `freeze` falls from 31.515 to **10.412 seconds**.
The remaining costs center on retained event capture/serialization, populated
markets and ordinary world loops. Actual market trade takes 9.035 cumulative
profile seconds; wilderness stepping no longer creates the large economic
per-stat trace fanout. Cumulative parent/child times overlap and must not be
summed. Full detail is retained in the raw profile summary.

This optimization does not fill missing claim/displacement source contracts;
existing claim/ticker logs and conservation behavior remain, with their existing
regression coverage. It does not remove chart padding or promise a particular
latency on other maps. No live model requests were used for implementation or
validation, and no API key is required for local applicability explanations.

## Reproducing the timing comparison

Run these sequentially from the repository, with the configured virtualenv:

```sh
COC_TRACE_WILDERNESS=full PYTHONHASHSEED=0 venv/bin/python -m benchmarks.profile_default_turns --turns 10 --capture-state --worker timing --output tmp/minimal-wilderness-default-full
COC_TRACE_WILDERNESS=minimal PYTHONHASHSEED=0 venv/bin/python -m benchmarks.profile_default_turns --turns 10 --capture-state --worker timing --output tmp/minimal-wilderness-default-minimal
COC_TRACE_WILDERNESS=minimal PYTHONHASHSEED=0 venv/bin/python -m benchmarks.profile_default_turns --turns 10 --worker profile --output tmp/minimal-wilderness-default-minimal
```

Add `--scenario egypt_1877 --turns 2` and use separate output directories for
the authored-scenario comparison. `--capture-state` writes a canonical graph
outside timing; reports include state, metrics and RNG hashes. The local
acceptance drivers are `tmp/run_minimal_wilderness_benchmarks.py`,
`tmp/compare_minimal_wilderness_evidence.py` and
`tmp/audit_minimal_wilderness_runs.py`. Raw comparisons explicitly state their
normalization rules and limits.
