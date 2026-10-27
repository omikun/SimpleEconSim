# Packed traces and checked unchanged-state coverage

Authorized: 2026-10-26, implement both reduction options from the trace-volume
analysis. Preserve causal evidence and historical explainer behavior, and
commit the completed implementation without pushing.

Completed: 2026-10-27. Results and limits are recorded in the
[implementation report](reports/packed_trace_storage_implementation.md), with
[benchmark data](reports/packed_trace_storage_benchmarks.json).

## Storage design

New runs use `COCTRACE4` with independently compressed, checksummed batches.
A batch contains up to 128 logical records and targets at most 512 KiB of
decoded encoded content. An oversized individual event retains the previous
64 MiB hard limit. Shared metadata and schema dictionaries avoid repeated
field names; ordinary run/branch/sequence event identities reconstruct exactly.

The append path freezes mutable inputs immediately. It does not wrap previously
serialized full JSON rows in another JSON layer. A rolling SHA-256 chain binds
each encoded packet to its predecessor and logical count. Checkpoints explicitly
declare the new digest scope and occupy separate frames. V3 files remain
readable and resumable with their original canonical-JSON digest scope.

Unchanged snapshots use `checked_unchanged_snapshot.v1` coverage: each compact
entry carries the checked baseline value, metric, subject dimensions, unit,
current source identity and turn/epoch context. The reader reconstructs its
original before/after values, zero delta, confidence, source links, and gap
status. Coverage is self-contained per bounded batch, so random access never
requires replaying an unbounded chain of prior turns. It attests the value
again at each turn rather than inferring continuity from absent records.

Initial baselines, changed values, changed-to-zero values, differing scalar
types or signed zeros, missing opening samples, and nonstandard observation
shapes stay explicit. All underlying transactions, decisions, computations,
no-op price audits, Gini source chains, and gap audits remain available.

The longer acceptance run also exposed unnecessary native command boundaries.
The sampler omits empty profession/labor categories while the recorder retains
their zero baselines for a possible later return. Comparing those dictionaries
directly incorrectly treated quiet turns as player actions. Compare current
samples while allowing only those specifically retained zero categories to be
absent. Any other changed value, a missing nonzero category, a returning
category, or an emitted player-action event still forces its boundary. This
removes duplicate full observation/calculation closures without dropping an
actual turn or command boundary. Apply the same rule when saving native games.

The logical query/export view retains stable event identities and historical
samples. Physical frame count, covered snapshots, and explicit snapshots are
reported separately; an expanded logical event count is not a storage-size
claim. Keeping logical index entries preserves direct source-ID lookup and
the existing F12 metric catalog contract.

## Work checklist

- [x] Versioned bounded batches, mutable-input freezing, packet digest scope.
- [x] V3 read/resume compatibility and independently seekable batch coordinates.
- [x] Checked unchanged-snapshot coverage with stable virtual observations.
- [x] Checkpoints, trace verification/audits, recovery-prefix hashes, and F11/web
  publication boundaries use the appropriate format's integrity semantics.
- [x] Index metadata and event reads consume expanded rows without full-row
  serialization/parsing solely to build the derived index.
- [x] Exact fixture equivalence across legacy, packed, and coverage modes,
  current source identities, command epochs, zero closings, signed zeros,
  mutation isolation, unsupported JSON values, corruption/torn tails, and
  fresh-process append continuation.
- [x] Complete live save/restore, inspector/service and seeded equivalence checks.
- [x] Record isolated whole-turn/storage/catalog benchmarks for all three modes.
- [x] Final documentation, diagnostic artifacts, review and detailed commit.

## Acceptance details

Compare all expanded gameplay records after normalizing random run/operation
identities and format-specific checkpoint metadata. Require matching sampled
economic values and gameplay RNG states, valid source links and supported
formula audits, queryable unchanged stats for historical tile/turn selections,
and correct fixed-boundary behavior after subsequent appends and save forks.

Full-state continuation comparison exposed existing pollution assessment
receipt IDs being treated as economic state. Exclude only that observational
receipt ID; retain the assessment's rate, affected counts and policy outcomes.
Normalize NumPy float scalars to JSON floats for type-stable graph comparison,
and keep multiprocessing's `__mp_main__` alias out of captured gameplay globals.
Tests must continue detecting changes to the actual economic/risk values.
