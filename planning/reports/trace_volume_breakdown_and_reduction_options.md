# Trace volume breakdown and reduction options

Analysis date: 2026-10-26. Recording implementation: `ee8d8a9`.

The largest opportunity is representing repetitive observations more compactly.
The trace contains useful causal events, but most entries in this particular
early-game world are repeated readings from wilderness bookkeeping. A lossless
packing experiment preserves every logical event and its evidence links while
substantially reducing physical frames and storage. A subsequent sparse-state
scheme could reduce logical observations, but requires explicit coverage and
provenance rules rather than deleting every unchanged value.

This document and its diagnostic data are an analysis and proposed follow-up.
No game recording policy or production trace format is changed here.

## Dataset and measurement

Use turn 2 of the immutable native trace captured during the previous fix:

`tmp/traces/desktop-fe540ef3f39846748a2e197d55558ddc.ctr`

The default map has 1,000 tiles, seed/terrain/nation seed 777. The trace contains
three completed turns. Turn 2 has **262,026 entries**, **177.51 MB of decoded
JSONL**, and **12.60 MB of stored frames**. MB here means decimal megabytes.
Stored-frame sizes are exact frame extents, including frame/block headers;
shared compression dictionaries mean they are not predicted deletion savings.

The recording has 988 wilderness tiles and 12 other tiles in this turn, inferred
from the actual `gini.wilderness_zero.v1` rule. Wilderness accounts for
**239,103 entries (91.3%)**, and 177,840 of the 180,159 stat snapshots.
Wilderness is a simulation mode, not a universal assertion that a tile is empty
or incapable of foraging, migration, or later settlement. It must not become a
blanket trace exclusion rule.

## Entries by purpose

| Entry kind | Count | Share | Purpose |
| --- | ---: | ---: | --- |
| `metric_snapshot` | 180,159 | 68.8% | Stat opening/closing readings, units, and calculation-source status |
| `gini_series_calculation` | 19,012 | 7.3% | Gini refresh, retain-previous, or wilderness-fixed-zero rule |
| `price_bridge` | 19,000 | 7.3% | Reconcile the ordered price writes against the displayed closing price |
| `closing_active_disease_census` | 5,000 | 1.9% | Five disease counts per tile, with the affected-person IDs |
| `tax_revenue_distribution_calculation` | 4,000 | 1.5% | Four tax-distribution series per tile, usually zero here |
| Everything else | 34,855 | 13.3% | Orders, paid sales, receipts, transfers, decisions, population/labor calculations, and other evidence |

Rounded percentages need not sum to exactly 100%. These kinds are disjoint.

The main causal layers serve different jobs. A paid sale records what moved;
a price calculation explains an updated reference price; a price bridge checks
that all ordered writes reconcile; a snapshot records the closing chart value.
Those layers are useful when activity occurs. Generating the same shape for
every inactive tile/good pair is what makes the volume disproportionate.

The `snapshot` phase alone contains **209,665 entries (80.0%)**, including
closing calculations and audits as well as snapshots. It is not 209,665
distinct gameplay actions.

## What is inside the snapshots?

| Snapshot family | Count |
| --- | ---: |
| Goods reference prices | 19,000 |
| Gini series | 18,012 |
| Production | 18,000 |
| Producer inventories | 18,000 |
| Demand | 17,847 |
| Supply | 17,847 |
| Units sold | 17,843 |
| Active disease counts | 5,000 |
| Historical disease-count series | 5,000 |
| Tax distribution | 4,000 |
| Other stats | 39,610 |

The seven commodity/Gini families account for 126,549 snapshots. In
`terrain/wilderness/wilderness.py`, `_align_logs` appends zero production,
inventory, demand, supply, sold, and Gini readings, plus unchanged reference
prices, so downstream chart readers can safely access aligned histories. The
trace snapshot sampler then records those readings separately by tile/good.
These are distinct subjects and metrics, not duplicate event identities.
There are **zero duplicate subject/metric snapshot rows within this turn**.

Of all 180,159 snapshots:

- **154,190** are unchanged zero values.
- **25,126** are unchanged nonzero values.
- **833** have changed opening/closing values.
- **10** lack an opening baseline.

Thus **179,316 snapshots (99.5%) have unchanged values**. They account for
68.4% of the entire turn's entries. This is a value-based investigation pool,
not a count of records that can safely be deleted: evidence sources, coverage,
or offsetting underlying events may still differ.

43,635 snapshots carry `calculation_recorded`; 136,524 carry `source_missing`.
All 833 changed snapshots in this sample are labeled `calculation_recorded`.
That label does not establish complete upstream attribution. Unchanged
`source_missing` observations still need to retain their explicit limitation;
packing or carry-forward must not upgrade them into verified explanations.

## Concrete reduction candidates and their dependencies

Inbound links were checked across all three recorded turns, including event-ID
strings nested in inputs, not only `cause_event_ids`. Future turns outside this
sample are not covered by that check. A currently unreferenced record may also
be an explanation root, a chart query target, or a future source.

| Investigation pool | Count | Referenced by later recorded turns | Implication |
| --- | ---: | ---: | --- |
| Unchanged zero snapshots | 154,190 | 0 | Strong sparse-state candidate after preserving coverage, status, and current causal roots |
| Unchanged nonzero snapshots | 25,126 | 354 | Source identity and historical query behavior must survive compaction |
| Unchanged price bridges with no steps, gaps, or causes | 18,925 | 0 | Bundle their explicit no-write reconciliation rather than emit one standalone audit per good |
| Wilderness fixed-zero Gini calculations | 18,772 | 18,772 | Every one is a source for the next turn; simple deletion breaks the chain |
| Other retain-previous Gini calculations | 240 | 240 | Preserve the actual sampled source and refresh rule |
| Zero-valued population/labor/disease closing records | 9,965 | 0 | All 9,965 have inbound links within the run; some are changes **to** zero |

Candidate pools can overlap; in particular, zero-valued closing records must
not be added to other pools as an independent saving. The first five rows are
disjoint by event kind/condition and total 217,253 entries (82.9%), but that is
the repetitive investigation pool, not an authorized 82.9% deletion.

There are also **26 unchanged price bridges with recorded price writes**.
Those writes happen to have zero individual differences in this turn. They
still demonstrate why testing only the net delta is insufficient. Other turns
can have positive and negative movements that cancel, such as tax receipts
and relief spending leaving the treasury unchanged.

Market order/price/receipt records should not be called duplicates just because
their counts match. Here, 2,285 submitted buyer orders record **quantity and
funding**, while 2,285 `local_buyer_bid` records explain the **unit-price limit**.
A paid sale, its unit-price observation, and the seller's receipt likewise
serve quantity, price, and settlement queries. Packing or shared source
references may help; dropping the underlying order or settlement can lose
affordability, unmet-need, and conservation explanations.

## First recommendation: lossless packed batches

Represent many logical events in one independently seekable physical batch.
Store shared run/turn/epoch/phase fields once, dictionary-encode repeated row
schemas, and derive event IDs from their recorded sequence and run/branch
identity. Keep all event-specific values, inputs, dimensions, rules, source
links, confidence, and gap statuses. Expand the original logical events for
the inspector, API, causal audit, and JSONL export.

This can reduce physical records and repeated encoding without choosing which
causes are important in advance. In the measured data, shared context and
identity fields alone occupy roughly 52 MB of decoded top-level fields.
Actual packed results are in `trace_packing_experiment_turn2.json`.

The offline prototype groups at most 128 logical events or 512 KiB of source
JSON per batch. The seekable variant starts a fresh compression block for each
batch, avoiding a misleading gain from huge blocks that would make individual
evidence queries expensive. It verifies that expanding the packed output gives
all **262,026 original logical events**, with this identical canonical digest:

`d21735cf8d02984b5e0a9bde9519713af44ce065618b5fcf798eae8cf37833b4`

The baseline uses 262,026 physical data frames. Packed output uses 2,054,
with 87.73 MB of encoded payload rather than 177.51 MB. The independently
seekable packed file occupies 5.26 MB rather than 12.60 MB, about 58% less.
These are representation experiments on a temporary copy, not a production
format, gameplay speed benchmark, or proof that current readers support it.

The same temporary experiment measured encoding, compression/append, and a
rolling hash, excluding source decoding and live simulation/index/cache work:

| Representation / integrity scope | Encode, append, and hash time | Stored size |
| --- | ---: | ---: |
| Current rows / canonical logical-row digest | 3.003s | 12.60 MB |
| Packed batches / same logical-row digest | 2.668s | 5.26 MB |
| Packed batches / digest over encoded packed payloads | 1.310s | 5.26 MB |

Checkpoint hashing needs a deliberate choice. Today's recorder computes a
rolling digest over every canonical logical JSON row. Keeping that exact
scheme still requires serializing those full rows to hash them, even when the
writer stores a compact representation. A versioned digest over encoded packed payloads
can protect the full encoded content without reconstructing every JSON row on
the simulation thread. The experiment measures both integrity scopes; they
must never be silently treated as equivalent formats.

The packed variant retaining the current digest also reproduces the identical
rolling hash in the experiment. Its write-path reduction is about 11%, whereas
the versioned packed-payload digest variant reduces that measured path by
about 56%. Neither number is a measured whole-turn speedup. Both representations
reconstruct exactly the same logical source records.

## Subsequent option: fewer logical observations

After the packed format is stable, introduce explicit state coverage if
logical index size and per-stat emission remain material costs:

1. Record a complete baseline and its metric/dimension/unit domain.
2. Record changes and newly appearing stats. Keep changed-to-zero and missing
   baseline cases explicit.
3. At each completed turn/command epoch, attest which unchanged values were
   checked and carried forward. Preserve current calculation sources, coverage
   status, membership, units, and rule versions. A matching value with new
   causal activity is not an unchanged causal explanation.
4. Let readers reconstruct the observed stat for any covered tile/stat/turn.
   Resolve carried observations as evidence-backed virtual samples, retaining
   valid source identities and actual effective turns. An uncovered interval
   remains unknown, never an assumed zero or unchanged value.
5. For fixed wilderness rules and non-refresh Gini turns, use bounded rule
   coverage or source ranges with explicit start/end and state transitions.
   Settlement, population changes, foraging, trade, or a Gini refresh must
   invalidate the applicable range immediately.

Do not implement this by removing arbitrary zero rows or reconstructing an old
turn from the current live world. The F12 metric catalog must understand the
same coverage model, or the original 'no trace found' problem will return.

## Evidence that must remain available

- Actual production, paid trades, inventory changes, transfers, tax/relief
  flows, imports/exports, treasury and bank reconciliation, and state changes.
- Failed or blocked actions, no-trade and affordability reasons, disease risks
  and random draws, mortality, migration, policy effects, and relevant AI
  decisions. These explain absences and constraints as well as positive events.
- Intermediate inputs and ordered mutations when an unchanged total hides
  activity or changing composition.
- Historical territory membership, currency basis, cohort/disease/good
  dimensions, command epochs, rule versions, and explicit provenance gaps.
- The evidence for a recorded zero, an unavailable baseline, and a verified
  no-op. These must remain distinguishable from missing recording.

## Implementation and acceptance work before changing production

1. Give packed traces an explicit format/version and preserve old-trace
   reading. Define logical versus physical counts and checkpoint hash scope.
2. Put packing ahead of avoidable full-row JSON serialization. Wrapping already
   serialized JSON in a second JSON packet could add work instead of saving it.
3. Bound seek/decode work by bytes and logical row counts, preserve ordering,
   and define coordinates for an event within a packed batch.
4. Keep the index, generic metric catalog, direct event lookup, formula replay,
   and explanation packets correct for every stat and subject dimension.
   Packing alone does not reduce the number of logical SQLite index rows.
5. Compare fully expanded logical records, source links, units, limits, and
   replay results against the unmodified recording. If the checkpoint format
   changes, test its new integrity contract separately rather than equating
   incomparable digest values.
6. Test truncated/corrupt batches, fixed historical boundaries, command epochs,
   cancellation, save/restore forks, and random source lookup. Benchmark
   cold/warm F12 catalog latency as well as whole-turn time and memory.
7. Exercise later, more populated worlds and food crises, debt/default, disease,
   migration, and offsetting flows. This mostly-wilderness early-game sample
   is not a universal workload or a demonstrated full-game speedup.

The detailed counters are in `trace_volume_turn2.json`. The temporary diagnostic
scripts used for this analysis are `/private/tmp/analyze_native_trace_volume.py`,
`/private/tmp/check_offsetting_price_traces.py`, and
`/private/tmp/experiment_packed_trace_frames.py`. Source traces were read only;
the packing experiment wrote and removed separate temporary files.
