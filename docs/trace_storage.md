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

The implementation checklist and acceptance requirements are in
[the implementation plan](../planning/trace_storage_reduction_implementation.md).
Measured savings and validation limits are in
[the implementation report](../planning/reports/packed_trace_storage_implementation.md).
