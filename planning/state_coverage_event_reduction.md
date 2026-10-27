# Grouped state coverage and fewer emitted events

Authorized 2026-10-27 after the measured candidate breakdown. Implement the
primary replacement pool first; assess the secondary empty/derived pool once
the primary design is validated. Preserve actual actions and gross flows.
Commit completed work without pushing.

## Representation

- New runs use versioned V5 event-count semantics, with old V3/V4 read/resume
  support. Store bounded checked coverage groups instead of per-stat events.
- Capture consecutive checks sharing turn/epoch/phase and base entity. Flush
  before an actual event, context/entity transition, byte/cell limit, query,
  checkpoint or close. This retains causal sequence and fixed-prefix order.
- Preserve original numeric sequence references as virtual checked samples.
  Group anchors have distinct identities; queries resolve covered IDs without
  indexing every virtual observation. New coverage is explicitly checked, not
  inferred from absent turns or from a currently live game object.
- Keep missing baselines, changed values/zero transitions, nonempty price writes,
  tax receipts, Gini refreshes and all actual inflows/outflows explicit. Standard
  unchanged observations and verified inactivity certificates enter coverage.
  Initial readings use a distinct checked-initial-sample rule, preserving an
  absent opening value and delta; grouping them never asserts continuity.
- Keep expanded event exports/replay compatible. Expose actual stored events,
  coverage groups, virtual samples and expanded compatibility counts separately.

## Work

- [x] Bounded coverage representation, direct capture, publication and failure
  semantics, versioned integrity and old-format compatibility.
- [x] Sparse group index, historical metric catalog, dimensions/epochs, virtual
  ID resolution, ordering, paging, fixed prefixes and rebuild behavior.
- [x] Recorder source caches/recent view, verification/audits, checkpoints,
  restore/forks and reporting preserve evidence and count distinctions.
- [x] Validate primary candidates and assess secondary candidates conservatively.
- [x] Exact expanded-evidence comparison, gross flow preservation, source-link
  and formula checks, missing/zero/rule transitions, corrupt/torn-tail tests,
  historical F12 requests, fresh continuation and state/RNG parity.
- [x] Isolated benchmark of events, index rows, storage, turn time and cold/warm
  F12 latency; document measured reductions and limits; detailed commit.

Avoid simply moving prebuilt events into a giant record or recreating one
SQLite row for every virtual sample. Keep independent seek/decode work bounded.
The 84–86% primary count target is a projection for the measured mostly-empty
1,000-tile world, not a latency guarantee or a universal crisis-workload target.

## Completion

Implemented the primary pool in V5, with one additional distinct rule for
initial scalar samples. Initial samples preserve unknown openings and deltas;
they are never treated as unchanged. Assessed the secondary pool and retained
it explicitly pending category-specific lifecycle/dependency rules. Actual
transactions and all original financial legs remain individual events.

Default turn 2 emits 40,263 instead of 262,026 records (84.63% fewer).
Default/Egypt whole-run actual event counts fall 82.53%/80.73%, and step time
falls 10.03%/11.44% in isolated single-sample benchmarks. Expanded evidence,
economic metric digests and both RNG states match. Historical F12 packets match
for c0, c500 and nations, including Egypt's crisis metrics. All 217 integration
and checkpoint tests pass, with additional exact-ID regression checks.

See [the implementation and validation report](reports/state_coverage_event_reduction.md)
and [raw measurements](reports/state_coverage_event_reduction.json).
Commit this implementation with its completed plan, docs and measurements;
do not push.
