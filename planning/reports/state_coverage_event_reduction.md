# Grouped state coverage: implementation and measurements

Implemented 2026-10-27, following the primary recommendation in
[the candidate analysis](trace_count_reduction_candidates.md). The baseline is
the recording behavior at `3c73b2f`: V4 with templates, checked certificates,
shared census inputs and national/fiscal contribution summaries enabled.

## Result

The default world's second turn now emits **40,263 actual events/groups instead
of 262,026 events: 84.63% fewer**. The third turn emits 40,108 instead of 261,935.
The saved checked facts and their original source IDs remain available through
the expanded compatibility view. Actual cash movements are unchanged.

The whole-run measurements below include initialization, initial readings and
metadata, so their reductions differ from a steady turn. Egypt begins at turn 1;
two calls to step produce completed turns 2 and 3. Both maps have 1,000 tiles.

| Measurement | Default V4 | Default V5 | Egypt V4 | Egypt V5 |
| --- | ---: | ---: | ---: | ---: |
| Calls to step | 3 | 3 | 2 | 2 |
| Actual events/groups | 785,108 | 137,131 | 527,764 | 101,722 |
| Coverage group anchors | 0 | 12,043 | 0 | 7,628 |
| Virtual checked samples | 0 | 660,020 | 0 | 433,670 |
| Expanded compatibility records | 785,108 | 785,108 | 527,764 | 527,764 |
| SQLite `events` rows | 785,108 | 137,131 | 527,764 | 101,722 |
| SQLite total event + coverage rows | 785,108 | 149,174 | 527,764 | 109,350 |
| SQLite file bytes | 370,393,088 | 173,285,376 | 248,840,192 | 118,018,048 |
| Trace bytes | 14,099,198 | 13,374,288 | 10,175,386 | 9,605,098 |
| Total seconds in step | 10.883 | 9.792 | 7.910 | 7.005 |
| Cold current-turn c0 catalog, seconds | 9.513 | 3.600 | 6.622 | 2.595 |
| Warm current-turn c0 catalog, milliseconds | 2.46 | 2.53 | 0.94 | 1.06 |

Across the full runs, actual event counts fell **82.53% / 80.73%**, total index
data rows **81.00% / 79.28%**, turn time **10.03% / 11.44%**, and cold catalog
time **62.16% / 60.82%** for default/Egypt respectively. Warm catalogs remain
around 1–3 ms; the small differences do not establish an improvement.

These are single local samples, measured in separate sequential processes with
`PYTHONHASHSEED=0`, Python/world seed 777 and NumPy seed 777. Map generation,
evidence hashing and queries are outside step timing. Cold catalog timing
includes initial index construction; warm timing reuses it. Heavy acceptance
tests ran only after all timed configurations finished. This is not a long-run
or all-crisis performance guarantee. Egypt includes its authored grain/debt
pressures, but these two steps do not reach every later debt/default event.

## What changed

V5 captures checked cells directly, before full event dictionaries exist. Each
cell retains original sequence, rule, metric, unit, dimensions, value and rule
details such as the current source. Consecutive cells for one exact
turn/epoch/phase and base entity share a bounded group. Groups close before an
ordinary event, context/entity change, size limit, publication, query,
checkpoint or close. No global reorder or historical carry-forward is needed.

The primary covered categories are unchanged scalar snapshots, checked no-write
price bridges, fixed/retained Gini calculations, empty active-disease closing
censuses and empty tax-distribution calculations. A zero closing disease census
does not delete earlier onset/treatment/mortality events. Empty allocation
requires no receipts and zero opening components, not merely a zero net sum.

Initial scalar readings use a separate checked-initial rule. This adjustment
avoids first-turn baselines fragmenting otherwise adjacent checks into thousands
of small groups. Their opening and delta remain absent, and their current
source/confidence/gap status remain exact. Default V5 retains 142,671 initial
samples this way; Egypt retains 142,674. Changed values and changes to zero are
still ordinary events. There is no blanket wilderness or quiet-nation filter.

Group anchors have distinct `:coverage:` identities. Numeric sample IDs remain
reserved for historical references. Source caches keep bounded numeric ranges
instead of adding each virtual ID to the ordinary recent-event cache. Identity
matching remains exact: alternate numeric spellings do not become valid IDs.

The index stores one actual event row per group plus a separate group-domain
row with checked cells. It stores **no individual virtual-sample rows**. Entity,
turn, boundary and source-ID ranges prune groups before cell selection. Metric
catalog construction does not instantiate virtual event dictionaries; a test
forbids expansion during cold catalog building. Selected query results alone
expand to their original event shapes and source IDs.

V5 uses its own packet-chain digest scope, validates group structure and numeric
sequence ordering, and checks actual and expanded checkpoint counts. V3/V4
readers and resumed writers retain their formats. Save/restore, fork, recovery,
fixed published boundaries, indexes rebuilt from source, and failure after a
short write preserve their existing guarantees. Simulation checkpoint source
fingerprints still apply; old pickles are not migrated between application
builds. Older application builds cannot read V5.

The pre-existing causal coverage-report module remains separate from the new
storage helper, `trace/trace_state_coverage.py`.

## Counts and exports

`event_records` / recorder `event_count` mean actual ordinary events plus group
anchors. `virtual_samples` counts checked cells. `expanded_records` is ordinary
events plus reconstructed original samples. Metadata is included in whole-run
counts. Legacy `logical_records`, recorder `count`, checkpoint `count_before`
and verification `rows` retain expanded meanings for existing consumers. New
`event_count_before` and manifest `trace_event_records` expose actual counts.

The compatibility export still enumerates every fact. Use `--stored-records`
with `--decode-jsonl` to export actual grouped records. Broad decoded exports
and offline full causal audits still expand all facts and remain expensive.
The new format does not imply an 85% reduction in every kind of trace work.

The trace file shrank only another 5–6% because V4 already compressed repeated
facts well and V5 preserves the cells, dimensions and sources. Simulation work,
checking each observed value, source-cache updates and capturing each cell also
remain. This explains why the event/index reduction is much larger than the
10–11% turn-speed improvement.

## Evidence and acceptance

Compared **785,107 default and 527,763 Egypt nonmetadata rows** in order against
V4. All original fields, numeric economic values, kinds, formula inputs,
constraints, sources, national contribution ledgers and fiscal gross-flow
reconciliations match. Normalization changes only run/operation identity strings
and format-specific checkpoint hash/scope/actual-count metadata. Both Python and
NumPy RNG states and the normalized economic metric digests also match.

Preserved evidence digests:

- Default: `e7a15d27dd1e9d84eeec49ea84bf6cdb344e82b98319d7961ac4867418151a60`
- Egypt: `2d86d69e9fe8748a385bdd94f677603bf809582bb0bbf7de84434240b21d9293`

Actual tax receipts, government spending, transfers, paid sales, account writes,
debt operations, failed actions, offsetting movements and unexplained residuals
are not filtered or consolidated. Identical ordered expanded rows verify that
all previously recorded financial legs and gross directions survive, including
activity hidden by a flat balance. Existing source gaps remain gaps.

Historical c0, c500 and nation metric catalogs match. **32 historical explainer
packets** match in values, source traversal, formulas, confidence and limitations:
11 default, 11 initial Egypt-scenario selections, and 10 direct Egypt nation
requests across turns 2/3 for treasury, population, food price, legitimacy and
protest energy. They cover active price/sales changes, quiet zeros, retained Gini,
non-c0 selection and unavailable initial openings. These are evidence-packet
checks with no provider calls; existing bounded source limits remain visible.

Acceptance tests:

- 212 targeted storage, index, recorder, formula/source audit, F12/AI integration,
  national contribution, labor, disease, public/private account and fiscal tests
  pass (`tmp/state-coverage-final-tests.log`).
- Four server checkpoint tests pass, covering fresh-process continuation for
  default and both authored rivalry scenarios, full shared economic graphs,
  RNG/cached RNG, pending cargo/loans/technology, duplicate commands, corrupt
  manifests, damaged tails and publication failure
  (`tmp/state-coverage-final-server-checkpoints.log`).
- One full native Egypt checkpoint test passes across fresh/same-process forks,
  with complete economic graph comparison, source prefix preservation and
  rejection of unknown runtime resources
  (`tmp/state-coverage-final-native-checkpoint.log`).
- Coverage tests additionally check sparse row counts, independent bounded
  groups, paging, null dimensions, command epochs, missing baselines, current
  sources, mutation isolation, old-format resume, malformed groups and failed
  writes. Exact-ID validation received a targeted recorder/index retest.

No API credits were used. The on-demand generation, loading/cancel UI and future
mechanic planning behavior are unchanged; turns do not trigger model work.

## Secondary candidate assessment

Leave the additional **12,916 records / 4.93%** candidate pool explicit for now.
Empty labor cohorts need membership/eligibility and current shared-census source
checks; births/deaths need lifecycle ordering, and an empty final population
does not establish that no migration or death occurred. Derived zeros also need
specific rule semantics. The observed zero growth rate can mean insufficient
ten-observation history despite a nonzero population, and an empty in-transit
pipeline does not mean there were no shipments during the turn. Flat workday
caps can still represent binding policy decisions.

These need separately versioned checked rules with transition tests before
joining coverage. They are not necessary to meet the implemented primary
84–86% steady-turn target. Likewise, combining paid sale/receipt/price records
or orders with bids is a smaller future opportunity and requires settlement
matching and complete leg/lifecycle retention. This implementation intentionally
keeps those actual actions individual.

## Reproduction and artifacts

Run the two configurations in separate sequential processes; repeat with
`--scenario egypt_1877 --turns 2` for the second workload:

```sh
env PYTHONHASHSEED=0 COC_TRACE_COVERAGE=0 MPLCONFIGDIR=/private/tmp/coc-ai-mpl venv/bin/python -m benchmarks.benchmark_trace_storage --mode coverage --output tmp/state-coverage-default-baseline.json
env PYTHONHASHSEED=0 COC_TRACE_COVERAGE=1 MPLCONFIGDIR=/private/tmp/coc-ai-mpl venv/bin/python -m benchmarks.benchmark_trace_storage --mode coverage --output tmp/state-coverage-default-optimized.json
```

[The machine-readable report](state_coverage_event_reduction.json) contains raw
benchmark reports, per-turn stored/expanded counts, rule totals, SQLite counts
and bytes, all event-kind counts, digests, catalog counts and sampled packet
values. Local QA drivers and logs are retained under `tmp/`:
`run_state_coverage_benchmarks.py`, `compare_state_coverage.py` and
`check_egypt_coverage_packets.py`. The implementation checklist is
[in the completed plan](../state_coverage_event_reduction.md).
