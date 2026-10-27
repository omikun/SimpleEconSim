# Packed causal traces and unchanged-stat coverage

New runs record `COCTRACE4` files. They keep the same logical events and source
identities exposed by the trace inspector, API, formula replay, and decoded
JSONL export, while storing bounded batches with shared context and schemas.
`COCTRACE3` traces remain readable and can continue on their original format
when restored by a compatible checkpoint build.

## Unchanged stats

A normal snapshot records the metric, subject dimensions, opening and closing
values, unit, turn/command epoch, confidence, gap status, and source link.
When the opening and closing scalar values are exactly equal, the writer can
encode a `checked_unchanged_snapshot.v1` coverage entry instead. It records the
checked value and **the current observation's source**, not a previous turn's
source. Reading it reconstructs the original snapshot and its stable event ID.

Coverage is explicit for each observed turn and self-contained in a bounded
batch. Missing recording never means zero or unchanged. An initial baseline,
a changed-to-zero value, a missing opening sample, differing scalar types or
signed zeros, and nonstandard observation shapes remain explicit snapshots.
Underlying trades, transfers, price writes, decisions, disease/migration events,
Gini calculation chains, and gap audits are retained even when a stat is flat.

This keeps historical F12 selections and later source references valid without
requiring an unbounded walk through earlier turns. It also preserves the
difference between a known zero, an unknown baseline, and an observation whose
calculation source is missing. Coverage does not upgrade explanatory certainty.

The emitter now captures standard unchanged observations directly into compact
templates, with turn/phase metadata frozen once and full rows expanded on read.
Verified no-write price bridges, unchanged fixed/retained Gini samples, empty
closing disease censuses, and empty tax-distribution calculations also use
explicit rule certificates. Actual price writes, Gini refreshes, nonempty
disease lists and tax receipts retain their full evidence. A zero net change
with offsetting activity does not qualify as inactivity.

Packet schema version 2 adds these certificates and shared labor-census inputs.
Each bounded packet includes its own census table; independent seeks do not
need an earlier packet. Full original census inputs are reconstructed before
formula replay, indexing or inspection. Packet schema version 1 and V3 files
remain readable. Old builds cannot read the new packet schema.

Taxation, government spending, paid trades, transfers and all other previously
recorded inflows/outflows remain individual events with their original IDs and
ordered account writes. Treasury reconciliations additionally show gross
inflows, gross outflows and both directions by kind. These describe recorded
national fiscal flows; existing unattributed residuals still expose gaps.
The regional `public_healthcare_spending` summary uses its own
`finance.public_healthcare_spending` observation metric. Individual medical
payment/receipt legs carry the treasury flows; adding the summary again would
double-count the spending. The summary and its cash-transfer links remain.

National stock and chart aggregates now carry regional contribution ledgers.
They reconcile sums/means with territory entry/exit, missing-value coverage and
changing mean weights. Opposing regional contributions remain visible at a
zero national net change. These are arithmetic decompositions, not proof of
upstream mechanisms; units, currency composition, absent baselines and residuals
remain explicit. The AI packet keeps exact totals and bounded material changes
from both directions, prioritizes their source links, and leaves the complete
ledger in the aggregate event.

## Integrity and publication

Each new packed batch is an independent compression/seek block, holds at most
128 logical rows, and targets at most 512 KiB of encoded decoded content.
Individual large events retain the 64 MiB hard limit. Mutable event inputs
are frozen when the event is accepted, before deferred batch serialization.

CRC checks detect frame corruption. A SHA-256 packet chain includes each
packet's predecessor digest and prior logical count. Turn checkpoints use
`packed-payload-chain-sha256.v1` and occupy separate frames. V3 checkpoints
retain `canonical-json-chain-sha256.v1`; digests from different scopes are not
interchangeable. Save/restore and recovery verify the format's own digest and
logical count. A complete prefix remains inspectable after a torn later tail.

Queries and checkpoints publish complete batches. Each logical event has a
batch offset and internal position; derived indexes may be deleted and rebuilt.
The index still retains logical entries for direct event-ID and stat queries.
Storage reduction is measured separately from expanded logical event count.

Native turn/save prechecks also distinguish retained empty census categories
from actual between-turn changes. Removing a category's retained zero does not
create a duplicate closure; changed values and recorded player actions still do.

## Inspect storage and compare modes

```sh
venv/bin/python trace/trace_report.py --run tmp/traces/RUN.ctr --storage-stats
venv/bin/python trace/trace_report.py --run tmp/traces/RUN.ctr --verify
venv/bin/python trace/trace_report.py --run tmp/traces/RUN.ctr --decode-jsonl tmp/RUN.jsonl
```

Storage stats report physical frames, logical records, explicit snapshots,
and covered snapshots. An export expands checked observations, so its logical
row count deliberately stays compatible with the original evidence view.

For controlled comparison, use separate sequential processes with the same
seed and hash seed:

```sh
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode legacy --output tmp/trace-legacy.json
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode packed --output tmp/trace-packed.json
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode coverage --output tmp/trace-coverage.json
```

The default is packed storage with coverage. For diagnostics on **new runs**,
`COC_TRACE_STORAGE=legacy` selects V3; `COC_TRACE_SPARSE=0` keeps packed storage
but disables checked-observation coverage. Existing restored files retain their
storage version. These settings do not enable or request AI generation.

For controlled comparisons, `COC_TRACE_TEMPLATES=0` disables direct template and
certificate emission, `COC_TRACE_SHARED_INPUTS=0` disables shared labor inputs,
and `COC_TRACE_NATIONAL_SUMMARIES=0` disables the added national/fiscal summaries.
All default to enabled. They never disable underlying financial flow recording.

The implementation checklist and acceptance requirements are in
[the implementation plan](../planning/trace_storage_reduction_implementation.md).
Measured savings and validation limits are in
[the implementation report](../planning/reports/packed_trace_storage_implementation.md).
The subsequent national trace optimization is tracked in
[its plan](../planning/national_causal_trace_optimization.md).
