# Grouped state coverage and packed causal traces

New runs record `COCTRACE5` files. Actual actions, account writes, changes and
audits remain individual events. Consecutive checked state samples share one
bounded coverage event and one group index entry instead of an event and index
row per sample. The inspector, API, formula replay and default JSONL export
resolve the original sample identities and reconstruct the same evidence.
`COCTRACE3` and `COCTRACE4` remain readable and resume in their original format
when restored by a compatible checkpoint build. Older application builds cannot
read V5. Checkpoint source fingerprints still require compatible application
sources; this change does not migrate old simulation pickles across builds.

## Quiet wilderness capture

New V5 runs use capture policy `minimal-wilderness.v1`. Quiet, unclaimed tiles
without resident agents, institutions, active cargo, faction members, military
or projects no longer generate padded economic observations. An empty faction
system or empty route object alone does not make a tile active. Background
native population is preserved separately from resident agents.

At setup, bounded batches record six frontier fields: native population, soil
fertility, nutrition density, and air/water/soil pollution. Each completed
turn/command epoch records checked domain coverage in cohorts of at most 512
tiles, with references to their recorded state. Actual field changes retain
ordinary changed snapshots and a new state anchor. Missing coverage never means
inactivity or an unchanged value; gaps require a fresh baseline. The index adds
one row per cohort, without manufacturing per-stat observations for omitted
chart defaults.

Wilderness reference prices are captured when a real calculation consumes
them. Sources identify recipe references without an operating market; they are
not clearing prices or paid trades. A quote is reused only while its current
value, units and regime remain valid. Route decisions and migration pressure
retain actual numerical inputs and reference links. UI previews and F12 reads
do not create observations.

Pollution, migration, foraging, claims, shipments, financial legs and other
actual activity remain recorded. Resident homesteaders and other active frontier
tiles retain full capture. Regime changes invalidate cached reference sources;
newly active economies retain unknown openings where no baseline was observed.
Existing claim/ticker logs remain intact; sparse coverage does not create
missing upstream causal evidence for those mechanisms.

`COC_TRACE_WILDERNESS=full` selects diagnostic full capture for new runs.
V3/V4 runs and saved runs without the new policy retain full capture on resume.
New minimal-policy checkpoints preserve state anchors and consumed-price
sources across forks. This is a capture reduction: expanded record counts also
fall, and omitted padded facts are intentionally not reconstructed. V5 framing,
digest scopes and checkpoint count meanings are unchanged.

## Unchanged stats

A normal snapshot records the metric, subject dimensions, opening and closing
values, unit, turn/command epoch, confidence, gap status, and source link.
When the opening and closing scalar values are exactly equal, the writer can
encode a `checked_unchanged_snapshot.v1` coverage entry instead. It records the
checked value and **the current observation's source**, not a previous turn's
source. Reading it reconstructs the original snapshot and its stable event ID.

Coverage is explicit for each observed turn and self-contained in a bounded
batch. Missing recording never means zero or unchanged. A changed-to-zero
value, differing scalar types or signed zeros, and nonstandard
observation shapes remain explicit snapshots. Initial scalar readings can share
a group under the separate `checked_initial_snapshot.v1` rule. Their opening
value and delta remain absent; they never assert that the value was unchanged.
Underlying trades, transfers, price writes, decisions, disease/migration events,
Gini calculation chains, and gap audits are retained even when a stat is flat.

This keeps historical F12 selections and later source references valid without
requiring an unbounded walk through earlier turns. It also preserves the
difference between a known zero, an unknown baseline, and an observation whose
calculation source is missing. Coverage does not upgrade explanatory certainty.

The emitter captures standard observations directly into compact checked cells,
with turn/phase metadata frozen once and full rows expanded on demand.
Verified no-write price bridges, unchanged fixed/retained Gini samples, empty
closing disease censuses, and empty tax-distribution calculations also use
explicit rule certificates. Actual price writes, Gini refreshes, nonempty
disease lists and tax receipts retain their full evidence. A zero net change
with offsetting activity does not qualify as inactivity.

Packet schema version 2 supports these certificates and shared labor-census inputs.
Each bounded packet includes its own census table; independent seeks do not
need an earlier packet. Full original census inputs are reconstructed before
formula replay or inspection. Packet schema version 1 and V3 files
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

Each coverage group has one exact turn, command epoch, phase and base entity.
It holds at most 512 checked cells and targets a 512 KiB capture budget; unusually
large individual values remain subject to the frame hard limit. Groups close
before ordinary events, entity/context changes, capacity limits, publication,
queries, checkpoints and close. Each stores complete dimensions, values, rule
parameters and current source IDs. Numeric sample sequences are reserved as
before. Group anchors use separate `:coverage:` IDs, and expansion preserves the
original causal sequence without sorting or walking older turns.

Each new packed batch is an independent compression/seek block, holds at most
128 stored events/groups, and targets at most 512 KiB of captured content.
Individual large events retain the 64 MiB hard limit. Mutable event inputs
are frozen when the event is accepted, before deferred batch serialization.

CRC checks detect frame corruption. A SHA-256 packet chain includes each
packet's predecessor digest and prior stored-event count. V5 checkpoints use
`state-coverage-packet-chain-sha256.v1`, V4 uses
`packed-payload-chain-sha256.v1`, and V3 retains
`canonical-json-chain-sha256.v1`. Checkpoints occupy separate frames. Digests
from different scopes are not interchangeable. Save/restore and recovery verify
the format's digest and both expanded and stored counts. A complete prefix
remains inspectable after a torn later tail.

Queries and checkpoints publish complete batches. Each stored event has a
batch offset and internal position; derived indexes may be deleted and rebuilt.
The index holds one `events` row per actual event/group and one `coverage` row
per group. It does not persist rows for individual virtual samples. Historical
catalogs inspect only matching entity/turn groups. Source-ID queries first find
matching identity/sequence ranges, then resolve the requested cell and verify
the original source block. Paging expands only selected results. Broad full-run
exports/audits deliberately still enumerate all original facts and can be costly.

Native turn/save prechecks also distinguish retained empty census categories
from actual between-turn changes. Removing a category's retained zero does not
create a duplicate closure; changed values and recorded player actions still do.

## Inspect storage and compare modes

```sh
venv/bin/python trace/trace_report.py --run tmp/traces/RUN.ctr --storage-stats
venv/bin/python trace/trace_report.py --run tmp/traces/RUN.ctr --verify
venv/bin/python trace/trace_report.py --run tmp/traces/RUN.ctr --decode-jsonl tmp/RUN.jsonl
venv/bin/python trace/trace_report.py --run tmp/traces/RUN.ctr --stored-records --decode-jsonl tmp/RUN-stored.jsonl
```

Storage stats distinguish `event_records` (actual ordinary events plus group
anchors), `coverage_groups`, `virtual_samples`, `initial_samples`, and
`expanded_records` (ordinary events plus reconstructed samples). `logical_records`
and recorder `count` retain their historical expanded-view meaning. Recorder
`event_count` counts actual events/groups, including accepted pending data.
`verify.rows` is expanded; `verify.event_records` is actual. V5 checkpoints retain
expanded `count_before` and add actual `event_count_before`. A default export
expands checked observations; `--stored-records` exposes the grouped format.
Count reductions do not mean deleting the checked values or causal references.

For controlled comparison, use separate sequential processes with the same
seed and hash seed:

```sh
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode legacy --output tmp/trace-legacy.json
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode packed --output tmp/trace-packed.json
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode coverage --output tmp/trace-coverage.json
env PYTHONHASHSEED=0 COC_TRACE_COVERAGE=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode coverage --output tmp/trace-v4.json
```

The default is V5 packed storage with grouped coverage. For diagnostics on **new runs**,
`COC_TRACE_STORAGE=legacy` selects V3; `COC_TRACE_COVERAGE=0` selects V4 while
retaining the previous optimizations. `COC_TRACE_SPARSE=0` disables checked
snapshot coverage, while separate calculation certificates can still apply.
Existing restored files retain their
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
The subsequent event-count reduction, exact-evidence checks and measured limits
are tracked in [its plan](../planning/state_coverage_event_reduction.md) and
[its report](../planning/reports/state_coverage_event_reduction.md).
