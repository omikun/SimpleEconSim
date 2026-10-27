# Hot loops in the first ten default-map turns

Measured 2026-10-27 on simulation implementation `f1da6c8`. The game/recorder
implementation is unchanged by this profiling work. Added a reusable profiling
driver and retained measurements; no event-culling policy is implemented here.

## Method and observed gameplay time

Native default map, 1,000 tiles, world/terrain/nation/NumPy seed 777,
`PYTHONHASHSEED=0`. All current V5 trace optimizations enabled. Measured turn
stepping in fresh sequential processes:

1. Ordinary tracing-enabled timing of turns 1–10.
2. cProfile around each of the same ten steps, with per-turn and combined stats.
3. Diagnostic ordinary timing of the same ten steps with `trace_enabled=False`.

Map generation is outside the step timing (0.522 seconds in the ordinary traced
run). No rendering, F12 queries, AI generation or full offline trace audit occurs
inside the measured steps. Profile serialization and report generation are also
outside the measured regions. This is one local sample per configuration.

| Turn | Ordinary seconds with tracing | Actual events/groups produced |
| --- | ---: | ---: |
| 1 | 2.988 | 56,623 |
| 2 | 3.255 | 40,263 |
| 3 | 3.172 | 40,108 |
| 4 | 3.196 | 40,060 |
| 5 | 3.293 | 41,270 |
| 6 | 3.202 | 39,339 |
| 7 | 3.476 | 38,666 |
| 8 | 3.374 | 38,345 |
| 9 | 3.667 | 39,802 |
| 10 | 3.995 | 43,468 |

**33.618 seconds total, 3.362 seconds/turn average.** Actual records include
group anchors; the expanded evidence view still has roughly 260–265 thousand
facts per turn. Whole-run totals including setup are 418,081 actual records and
2,617,864 expanded records, in a 47,136,532-byte trace.

The recorder-disabled diagnostic took **3.908 seconds total, 0.391/turn**.
Turning the recorder off removed 29.711 seconds, **88.38% of elapsed time** in
these paired samples. Its normalized economic metric digest and Python/NumPy
RNG states match the traced run. This validates those measured outputs; it is
not a full economic-object-graph equivalence test. The intended optimization
retains causal recording while removing its CPU overhead.

The cProfile run took **96.272 seconds** around the steps, versus 33.618 ordinary
seconds: about **2.86× instrumentation overhead**. It recorded **397,925,253
calls**, including recursion. Profiler timings rank execution paths; they are
not gameplay latency estimates. Heavy call instrumentation can exaggerate the
relative cost of Python loops. The profiled/unprofiled traced runs match in
economic metric/RNG digests, total counts and every per-turn actual event count.

## Largest paths

Times below are totals across all ten profiled turns. **Cumulative times
overlap**: `record` calls `snapshot`, which calls coverage capture and `freeze`.
Do not sum these rows.

| Path | Calls | Cumulative profile seconds | Self seconds | Interpretation |
| --- | ---: | ---: | ---: | --- |
| `trace_snapshots.record` | 10 | 51.788 | 1.588 | Closing trace passes consume 53.8% of profiled turn time, including all child work. |
| `RunTrace.snapshot` | 1,802,153 | 33.464 | 4.359 | Around 180,000 metric observations per turn still perform lookup, identity and capture work. |
| `trace_packing.freeze` | 22,320,135 including recursion; 2,627,747 nonrecursive calls | 31.515 | 22.564 | Largest individual CPU loop: recursively copying/validating event/cell inputs and estimating capture budgets. |
| `RunTrace._prepare` | 2,242,973 | 31.659 | 1.647 | Shared-context setup and dispatch for covered facts. |
| `CompactTraceWriter.append_coverage` | 2,242,973 | 29.362 | 2.618 | Per-cell capture, group matching, locking and flush decisions. |
| `RunTrace.emit` | 629,705 | 32.409 | 2.323 | Remaining calculations/actions/certificates still traverse the general emission path. |
| `CompactTraceWriter.append` | 417,944 | 24.653 | 0.794 | Captures ordinary events and stores groups/packets; includes freezing and batch work. |
| `capture_cell` | 2,242,973 | 18.176 | 1.211 | Builds/freeze-validates each checked seven-field cell. |
| `flush_pending` / `_batch` | 10,276 / 10,246 | 9.251 / 9.029 | 0.217 / 0.086 | Packet construction, serialization, compression and writing. |
| `price_bridge` | 190,000 | 6.845 | 0.202 | No-write bridges are grouped on disk but still checked/captured per good/tile. |
| Gini `record_sample` | 190,120 | 5.521 | 0.326 | Quiet/fixed Gini rules still create checked samples. |
| `json.dumps` | 465,175 | 4.863 | 0.324 | JSON serialization beneath batches and other trace paths. |
| `CoverageBuffer.accepts` | 2,218,455 | 4.488 | 1.250 | Repeated context/base-subject comparison and generator-based type/value checks. |
| `trace_snapshots.sample` | 20 | 4.486 | 3.342 | One pre-turn command-change check and one closing collection per turn. |
| `_subject_key` | 2,857,844 | 4.167 | 2.272 | Repeated rebuilding of metric subject identities. |
| zlib `compress` | 10,246 | 2.665 | 2.665 | About 2.8% of profiled total; not the leading cost. |
| `KnownEventIds.add_virtual` | 2,242,973 | 2.339 | 1.449 | Per-sample numeric ID parsing/range bookkeeping. |

`freeze` causes most of the repeated primitive operations: 47.96 million
`isinstance`, 52.23 million `len` and 36.48 million `isascii` calls in the
profile. Its immediate coverage-cell callers account for **16.777 cumulative
seconds** inside `freeze`; ordinary-event capture accounts for **14.072**.
This confirms that both checked cells and remaining full records matter.

The on-disk event reduction did not eliminate per-fact work: **2.243 million
coverage captures** and **1.802 million closing snapshot calls** still occur
over ten turns. Grouping removed individual stored events and index rows while
preserving their checked values and source IDs. These preserved checks now
dominate the CPU profile.

## Economic paths and world loops

The engine body (`sim_engine.step_turn`) takes 41.528 cumulative profile seconds,
but it includes trace emissions inside the simulation. Province/local economy
stepping takes 24.006/22.811 seconds for 50 province/120 populated-tile calls.
The largest narrower paths are:

| Path | Calls | Cumulative profile seconds | Self seconds |
| --- | ---: | ---: | ---: |
| Wilderness stepping | 9,880 | 12.241 | 0.216 |
| Local market `trade` | 120 | 9.086 | 0.597 |
| Elite planning | 738 | 2.740 | 0.060 at outer function |
| Discriminatory market clearing | 449 | 2.036 | 0.192 |
| Consumption `Live` | 120 | 1.690 | 0.028 |
| Trader route repointing | 120 | 1.678 | 0.110 |
| Production | 120 | 1.126 | 0.031 |
| Actor account sealing | 120 | 1.119 | 0.637 |
| Feudal tribute collection | 120 | 0.989 | 0.015 |
| World parked-goods resolution | 10 | 0.706 | 0.594 |

These timings also include child instrumentation and overlap. Wilderness's
12.241 cumulative seconds versus 0.216 self seconds show why merely skipping
wilderness economics is not the right inference: its child checked-history
emissions are expensive. The diagnostic trace-disabled total corroborates that
the sampled economy itself is much cheaper than traced stepping.

The pending-import gather in `sim_engine.step_turn` scans every other tile for
each tile and then checks adjacency. It is a concrete quadratic world loop
(roughly one million pair visits per turn on this map) that could iterate
neighbors directly. However, the entire engine function's self time is only
1.195 profile seconds across ten turns. This loop is a smaller next priority
than trace capture; include it after the dominant costs are addressed.

## Optimization priority informed by the profile

1. **Specialize capture for the fixed checked-cell schema.** Validate scalar
   values/sources precisely, freeze mutable dimensions/rule details once, and
   reuse validated metadata, subjects and unit/metric descriptors. Avoid
   recursively revalidating/copying the same small structures and strings for
   every scalar. Keep the generic fallback, finite-number/type guards, mutation
   isolation, byte bounds and write-failure behavior.
2. **Batch the snapshot/coverage path at tile/domain scope.** Reuse stable
   subject identities and context within a bounded group, simplify the per-cell
   group compatibility checks, and pass reserved numeric sequences directly
   into range bookkeeping. Preserve exact observation timing, source changes,
   command epochs and historical source resolution.
3. **Then move the measured secondary quiet calculations into checked rules.**
   That reduces remaining general `emit` and ordinary-event `freeze` work. The
   [candidate analysis](remaining_trace_event_candidates.md) projects roughly
   28–31k actual default records versus 40,263, depending on derived views and
   group overhead. This does not remove most of the existing 224k checked cells
   per turn, so culling alone will leave the largest capture path active.
4. **Reuse pre-turn snapshots only with reliable mutation invalidation.** The
   native wrapper currently samples once to detect between-turn commands and
   again when closing. A valid dirty/epoch mechanism might remove a redundant
   full collection, but direct player/scenario mutations must still be detected.
5. **Optimize smaller engine/market loops afterward.** Iterate actual neighbors
   for pending imports and profile market/route/account-book loops independently
   once trace overhead is lower. Compression-level tuning and transaction-row
   consolidation are lower priorities for the measured CPU problem.

This is a proposed order, not an implemented optimization or speedup promise.
Retain actual taxation/spending/inflows/outflows, failed decisions and regional
source chains. Validate state/RNG, exact expanded evidence, F12 and checkpoints
for any subsequent capture change, and compare ordinary ten-turn timings again.

## Reproduce and inspect

```sh
env MPLCONFIGDIR=/private/tmp/coc-ai-mpl PYTHONHASHSEED=0 venv/bin/python -m benchmarks.profile_default_turns --seed 777 --turns 10 --output tmp/default-ten-turn-profile
```

The driver runs ordinary/profiled processes sequentially, produces per-turn
`.prof` files and a combined `.prof`, and verifies digests/count parity. Open a
raw profile with standard `pstats` tooling. The optional recorder-disabled
diagnostic was run separately using `tmp/time_default_without_trace.py` with
the same seeds and `trace_enabled=False`.

[The retained JSON summary](default_first_ten_turn_profile.json) contains all
ordinary timings, top cumulative/self functions with callers, per-turn
hotspots, trace paths/counts and metric/RNG digests, including the separate
recorder-disabled diagnostic. Full binary profiles and detailed JSON remain
under `tmp/default-ten-turn-profile/`. The profiling runner itself successfully
completed all twenty traced steps, and the separate diagnostic completed ten.
