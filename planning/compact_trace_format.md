# Compact causal trace

Simulation runs write `tmp/traces/<run-id>.ctr`. The event schema, IDs,
sequence, formulas, and turn checkpoints are unchanged when decoded.

The current compact file starts with `COCTRACE3\n` and stores checksummed
frames in independently decodable raw DEFLATE blocks. Payloads are still UTF-8
JSON records. Writers publish at block, query and checkpoint boundaries. The
reader rejects corrupt frames and torn tails. Checkpoints hash decoded canonical
JSON payloads. This format uses only Python's standard library. JSONL is an
export format; the reader accepts only `.ctr` input.

## Read or decode

```bash
venv/bin/python trace_report.py --run tmp/traces/RUN_ID.ctr --turn 12 --entity tile:Delta --good cloth --metric goods.price
venv/bin/python trace_report.py --run tmp/traces/RUN_ID.ctr --verify
venv/bin/python trace_report.py --run tmp/traces/RUN_ID.ctr --storage-stats
venv/bin/python trace_report.py --run tmp/traces/RUN_ID.ctr --decode-jsonl tmp/decoded-run.jsonl
```

`--decode-jsonl -` writes the complete decoded JSONL to standard output.
The web API `/api/trace` reads compact traces directly. `/api/trace/download`
exports decoded JSONL for existing tools; add `?format=compact` to download
the smaller `.ctr` file. Both links are available in the web client.

In a generated one-turn test run on 2026-10-16, the compact file was 677,011
bytes versus 10,481,917 decoded JSONL bytes (6.5% of the original size).
Actual ratios depend on how many repeated events a scenario emits. This
storage change does not remove events or reduce their recorded detail.

## Redesign plan — 2026-10-24

Status: pending implementation. Preserve simulation rules and RNG consumption.
Store the facts needed to reconstruct what happened; let a versioned decoder
supply repeated context, defaults, rules and explanatory scaffolding.

### Baseline and targets

A fresh default SimServer run, seed 4242, completed 20 turns at source commit
`beea33f4b174f4721029ecd860e7c206378fb4b3`: 884,682 records,
1,059,032,055 decoded bytes and 75,299,815 compact bytes. Local analysis is in
`tmp/trace-fat-analysis/report.md`, `stats.json`, `details.json` and `sample.md`;
run metadata is in `tmp/trace-fat-20-run.json`. This measures one scenario.

| First candidate | Records | Decoded MB | Treatment |
|---|---:|---:|---|
| Unchanged metric snapshots | 264,216 | 144.0 | Baseline, changes and explicit unchanged coverage |
| Empty price bridges | 28,947 | 16.5 | Compact coverage when there are no writes, change or gaps |
| Separate sale-price observations | 23,276 | 14.1 | Project transaction price from sale events |
| Separate forage receipts | 22,142 | 10.8 | Merge receipt identity into foraging events |

These are 38.3% of records and 17.5% of decoded bytes before replacement
overhead. Five bulky kinds add 317.2 MB: labor member counts, zero-order
summaries, trader route decisions, temporary-work means and elite capital
allocation evaluations. Combining the first candidates with substantial payload
normalization suggests a 33–40% decoded-size reduction as a planning estimate.
This is not a measured rewrite or compressed-size forecast. Compression already
removes 92.9% of decoded size; measure disk and CPU effects separately.

Initial binary proof-of-concept completed against a fresh 20-turn default
trace. It retained every event and field, encoded generic typed values, and used
one compressed string table followed by independently compressed 256-record
blocks. The source was 75,285,550 bytes; the prototype was 32,005,118 bytes
(42.51% of source, 57.49% smaller). It decoded all 884,682 records and matched
the source's chained logical SHA-256 exactly:
`d5a1cdf83b32ead1b7199925c3ad63afca7527d7c5f8de4da82e0df3b9d62d27`.
The table held 944,760 distinct strings and compressed to 2,886,410 bytes.
Offline scan, encode and decode took 19.26, 28.56 and 24.04 seconds. This proves
size and round-trip feasibility, not production performance: it scans twice
before writing and performs a full decode check. It does not yet measure a
streaming writer, indexed lookup or memory, and these timings are not directly
comparable with current reader timings. Artifacts are
`tmp/trace-fat-analysis/prototype.py`, `prototype.source.ctr` and
`prototype.bin`. An initial draft exposed serialized map ordering for objects
whose original keys were numeric; the corrected encoding preserves map order
and the exact logical digest. Production encoding must keep this property.

### Small event schemas and explicit defaults

Define a typed payload per event kind with required fields, optional fields,
explicit defaults and semantic validation, rather than an unrestricted generic
`inputs` map. Inventory explanation, replay, query, source-contract and
reconciliation consumers before removing fields.

- Hoist run ID, branch ID and schema version into file context. Hoist turn,
  epoch and phase where invariant within a block, with explicit changes.
- Define record class, metric, unit and formula in the event schema where
  invariant; encode overrides only for variable cases.
- Store actor, tile, good and operation identities once. Reconstruct public
  event IDs from run/branch and sequence; use compact internal references.
  Preserve the distinction between journal IDs and trace IDs.
- Derive `delta` from before/after. Compute successful `formula_replay` results
  when inspected or in a separate versioned validation report. Retain actual
  discrepancies and missing/unsupported evidence; absence must not mean success.
- Omit false flags, zero values, empty lists and nulls only where the specific
  event schema defines that exact default. Unknown, absent, not applicable,
  empty and zero must stay distinct wherever interpretation depends on them.
- Move constant rule prose, formula descriptions, eligibility rules and sample
  point descriptions into schema/template definitions.
- Replace copied values with source references only when the source captures
  the same value at the same boundary. Preserve local observations where timing,
  rounding or semantics differ.

Lack of incoming links does not establish that a terminal record is unused:
charts and queries consume evidence too.

### Replace generic confidence

The current writer generally assigns `exact` to calculations, transfers and
outcomes, `unknown` to other classes, and downgrades failed formula replay.
Emitters can override it. This is not verified provenance.

Remove stored generic `confidence` from the new schema. Present specific checks
instead: arithmetic replay, source resolution, balance reconciliation,
unsupported checks and missing evidence. Preserve the distinction between
observations, forecasts, recorded decisions and mechanically captured effects.

### Shared evidence and reduced event counts

1. Store one census per tile/boundary shared by labor counts and temporary-work
   means. Reference previous censuses and encode membership, age eligibility and
   status changes; retain person-event links.
2. Compact zero-order reasons through shared inputs, memberships and exceptions.
   Keep the ability to explain why an identified agent did not place an order.
3. Share route/sector evaluation inputs. Preserve choices, thresholds,
   constraints and rejection reasons. Do not silently drop alternatives needed
   for exact decision replay. Lossy diagnostic tiers are a separate scope decision.
4. Merge sale-price and forage-receipt duplicates. Update metric projections,
   IDs/source links and queries; preserve currency and receipt identity. Keep
   distinct seller settlement/journal provenance and both transfer legs.
5. Encode unchanged samples with explicit coverage intervals and boundaries.
   Distinguish unchanged, absent and missing-source samples. Equal closing
   values do not imply no intervening production, consumption or transfers.
6. Replace empty routine bridges with coverage semantics; retain actual writes,
   gaps, residuals and discrepancies.

Keep zero-production causes and random draws. All 8,683 zero-production records
and all 4,320 explicitly marked Gini carry-forward records were referenced in
this run. Gini carry-forward chains can become sample validity intervals with
redirected consumers; do not simply delete them.

### String tables and reasoning templates

Use numeric IDs for field names, kinds, enums, goods and fixed rules/templates.
Dynamic reasoning uses a template/reason ID plus typed parameters, for example
`INPUT_UNAVAILABLE(good_id, required, available)`. Render prose in the viewer.
Preserve actual free text verbatim; intern repetitions where worthwhile. Do not
use lossy summarization.

Embed the schema/template dictionary or a complete immutable definition bundle
in the file so historical explanations cannot drift with application text.
Definitions do not replace variable inputs, random draws or causal evidence.

### Binary container and version dispatcher

Introduce a new format version; do not reinterpret COCTRACE3. Backward
compatibility is not required. The initial outer dispatcher may support only
the new decoder. Reject unknown versions clearly, without guessing or fallback.

| Identifier | Purpose |
|---|---|
| Container version | Framing, compression and typed encoding |
| Event schema version | Fields, defaults, meanings, formulas and templates |
| Source/build ID | Exact simulation implementation |

Proposed layout:

1. Magic, versions, build identity, run metadata and schema dictionary.
2. Independent blocks with explicit context, local string/entity dictionaries,
   typed records, boundaries and checksums.

Use native numeric values and compact integer references with explicit numeric
encoding rules. Select the binary codec through a measured prototype and
dependency/cost comparison; no codec is selected yet.

Indexed reads must decode a block without replaying earlier dictionary updates.
Use header definitions plus block-local dictionaries or dictionary checkpoints.
Preserve bounded memory, live publication/query behavior, seek/resume and
torn-tail recovery.

`open_trace()` inspects the header and dispatches to a version-specific decoder
that returns standard event objects directly. JSON/JSONL remains an export and
verbose inspection view, not an intermediate serialization immediately parsed
again. Expanded records may reconstruct defaults/context but not missing evidence.

Version checkpoint hashing and resume state deliberately. Define canonical
logical-record hashing independently of physical dictionary IDs/compression,
including ordering, omitted defaults and numeric encoding. Update checkpoint
compatibility checks and rebuild incompatible indexes. Preserve causal targets
or deterministic projection mappings for merged events. Keep original historical
files immutable; any conversion is explicit and separate from normal decoding.

### Work order and acceptance

1. Inventory schemas and consumer dependencies. Capture small fixtures covering
   defaults, currencies, source links, boundaries and failures.
2. Prototype binary encoding/string tables against the 20-turn trace without
   event reduction. Require exact logical-record round trips. Measure compressed
   bytes, write CPU, sequential decoding, indexed lookup and peak memory.
3. Implement version dispatch, reader/writer and JSON export. Migrate index,
   audit, CLI, UI, checkpoint and recovery consumers to decoded event objects.
4. Reduce redundant fields/defaults and normalize shared census/decision inputs.
   Require equivalent reconstructed evidence and replay results; redundant
   serialized fields need not remain byte-identical.
5. Merge events and encode unchanged coverage. Verify equivalent metric queries,
   historical charts, source resolution, balances and diagnostic explanations.
6. Run relevant codec, corruption/truncation, random-access, publication,
   checkpoint/resume, causal-contract and UI checks. Unsupported or missing
   evidence remains explicit.
7. Repeat the default benchmark and representative labor-frontier, supply-rivalry
   and Egypt runs. Compare simulation state/RNG with tracing on/off. Report
   measured record, disk, CPU and memory changes separately.

Completion requires working inspection/export, preserved required evidence,
no dangling causal references, reproducible logical hashes, safe recovery and
measured performance results. Do not present estimated savings as achieved.

### Future tasks — indexed module and turn-window inspection

- Extend the existing `TraceIndex` SQLite sidecar with stable subsystem IDs,
  inclusive turn ranges, phase/entity/good filters and keyset pagination.
  Maintain the index incrementally as published trace blocks are written so
  normal first queries do not require a whole-game scan. Preserve rebuildability.
- Query metadata first, group results by block and decompress each selected
  block once. Keep dictionaries independently accessible. Bound block sizes and
  prefer turn boundaries; decoding a window may include small edge blocks.
- Route CLI and web/desktop filtered inspection through the index. Stream
  filtered JSON exports; never require a full decoded trace on disk.
- Offer explicit expansion to causes outside the selected module/turn window.
  Distinguish complete window results from unavailable evidence.
- Benchmark combined payload plus index size, write overhead, peak memory and
  cold/warm filtered-query latency on long games. Compact index identifiers and
  avoid duplicating verbose JSON or text IDs unnecessarily.
- Compare the current compressed-file/sidecar layout with a single SQLite
  container holding compressed block BLOBs and event metadata in one transaction.
  Storing full decoded JSON per row is not the default proposal. Choose after
  measuring storage, publication, recovery and query costs.
