# Packed causal traces and checked unchanged-state coverage

Completed 2026-10-27, implementing both options authorized after the
[trace-volume analysis](trace_volume_breakdown_and_reduction_options.md). Implementation base:
`d37f1e9`. No gameplay model or economic rule changes, and no paid model calls.

## Result

New runs use independently seekable `COCTRACE4` batches, with shared metadata,
column schemas and reconstructable event identities. Each batch contains at
most 128 logical records and targets at most 512 KiB; large single events keep
the prior 64 MiB limit. Inputs are frozen when accepted so later mutation cannot
rewrite queued evidence. A versioned SHA-256 packet chain binds the preceding
digest and logical count. Checkpoints occupy separate frames. All trace
verification, audits, indexing, publication, save/restore and recovery paths use
the matching version's integrity semantics. V3 traces remain readable and
resumable with their original hash scope.

Unchanged scalar observations use `checked_unchanged_snapshot.v1`. A compact
entry explicitly records its checked value, subject/metric/unit, turn/epoch,
and current source identity. Readers reconstruct the original logical event,
including before/after, zero delta, confidence, source/gap status and stable
event ID. Missing evidence never implies unchanged or zero. Initial samples,
changed-to-zero values, missing baselines, different scalar types/signed zeros,
and nonstandard shapes stay explicit. No cross-turn continuity assumption or
unbounded history replay is needed to seek a batch.

Transactions, decisions, no-op price writes, random draws, calculation chains,
Gini refresh/sample evidence, and gap audits remain. The inspector, explainer,
formula replay and expanded JSONL export consume the same logical view.
Packing changes physical storage rather than pretending that hundreds of
thousands of observations have disappeared from that view. Logical SQLite index
entries remain for direct source-ID and stat lookups.

The native fast snapshot path avoids generic emitter dispatch for closing
tile/nation observations while preserving event identities and source caches.
Derived indexes consume decoded packed rows directly instead of serializing
and reparsing each full event. F11 and web queries publish a complete packet
before freezing their evidence boundary. AI generation stays on demand.

## Additional cause of slow later turns

The 12-turn run exposed a comparison error in native turn/save prechecks.
Empty profession and labor categories disappear from a fresh sample but their
zero baselines intentionally remain in the recorder. A dictionary inequality
therefore invented between-turn changes. Six quiet boundaries in the legacy
run recorded another full snapshot/calculation closure, nearly doubling some
turns' work.

The precheck now allows absence only for the recorder's retained zero census
categories. A real action event, changed value, missing nonzero category or
returning category still closes the pending boundary. This removes redundant
observations and calculations; all actual gameplay turns/actions remain traced.
Save preparation uses the same comparison.

## Measurements

Local Python 3.13, default native 1,000-tile world, seed/terrain/nation seed 777,
NumPy seed 777, `PYTHONHASHSEED=0`. Each configuration used a separate sequential
process. Timings cover `step_world`, excluding generation, UI, evidence hashing,
and queries. These are single local measurements, not latency guarantees.

The isolated three-turn comparison holds the logical evidence constant:

| Measure | Legacy V3 | Packed, dense | Packed + coverage |
| --- | ---: | ---: | ---: |
| Stored bytes | 36,987,350 | 16,743,058 | 15,780,108 |
| Physical data frames | 785,108 | 6,889 | 6,889 |
| Logical records | 785,108 | 785,108 | 785,108 |
| Explicit snapshots | 540,539 | 540,539 | 144,828 |
| Checked covered snapshots | 0 | 0 | 395,711 |
| Three turns total | 14.943 s | 12.955 s | 12.994 s |
| Cold stat catalog | 13.632 s | 10.164 s | 10.017 s |
| Warm stat catalog | 0.069 s | 0.068 s | 0.070 s |

Packing plus coverage uses **57.3% less storage**, takes **13.0% less turn time**,
and builds the cold catalog **26.5% faster**. All modes expose the same 973
selected-tile catalog variants. Expanded evidence matches across every row
after identity and format-specific checkpoint normalization; sampled economic
values and both gameplay RNG states also match. Checkpoint integrity passes in
each format. Coverage adds a further 5.8% saving over dense packing here.
An additional row-by-row comparison preserves every numeric scalar during
normalization and confirms all 785,107 nonmetadata records match exactly.
Its digest is retained separately in the benchmark data.

The longer comparison includes the retained-zero precheck correction:

| Measure after 12 turns | Previous precheck + legacy | Corrected precheck + coverage |
| --- | ---: | ---: |
| Stored bytes | 212,083,387 | 67,212,180 |
| Logical records | 4,517,212 | 3,150,830 |
| Actual turn checkpoints plus redundant closures | 18 | 12 |
| Turn 12 | 9.303 s | 4.876 s |
| Covered snapshots | 0 | 2,009,483 |

The combined changes use **68.3% less storage**, take **36.3% less total turn
time**, and make turn 12 **47.6% faster**. The simulation metric digest, Python
RNG digest, NumPy RNG digest and 1,020 catalog variants match. Expanded record
hashes intentionally differ because the six unnecessary closures are gone;
the three-format comparison above is the lossless-storage equivalence check.

Historical Gini observations for turns 2, 10, 11 and 12 resolve to the respective
turn's `gini_series_calculation`, including retained values after a refresh.
Those source lookups are recorded in the
[machine-readable benchmark](packed_trace_storage_benchmarks.json).

The old long-run benchmark accepted `labor-frontier-rivalry`, which the native
builder silently ignored. Trace metadata confirms these are **default native
worlds**, not the authored server scenario. The committed benchmark now rejects
unsupported native scenarios. Long-run cold catalog timings overlapped other
validation and are retained as diagnostics, not used for the isolated speed
claim. Raw trace files and sidecars are local diagnostics under `tmp/traces`;
the durable report contains measurements, digests and integrity results.

## Validation and limits

- Final 37-test storage/packing, native-session, desktop AI and semantic-state
  regression group passed. New cases include exact legacy/dense/coverage
  equivalence, current sources, historical catalogs, command epochs, zero
  closings, signed zeros, Unicode, mutable input isolation, invalid JSON,
  independent seeks, fixed prefixes, index rebuilds, fresh-process append,
  V3 continuation, torn/corrupt tails, repaired-CRC chain tampering, partial
  writes, raw-to-packed mixed-format seeking, and real-action versus
  retained-zero boundary handling.
- The broader inspector, audit, command, explanation, service, integration,
  chart, census and web group ran 144 tests: 143 passed. The existing web Gini
  expectation at `tests/test_web_server.py:312` requests a missing
  `replay_matches` input; the same failure was reproduced in legacy mode.
- All 39 recorder tests passed. The separate fresh-process server checkpoint
  suite passed all four tests, including both authored scenarios, complete
  economic/RNG state, graph aliases, pending cargo/loan/technology causes,
  recovery and failed publication. Checkpoint tests should run in their own
  process: prior recorder fixtures in a combined invocation pollute shared
  journal globals and can cause a canonical-state mismatch.
- The native Egypt full-economy continuation test passed after the final
  precheck change, including a fresh child process, same-process restore,
  prefix retention, aliases, and rejection of unrecognized runtime resources.

Full-state acceptance exposed old comparison issues: pollution assessment
receipt IDs differ on forks and NumPy/native float scalars could encode
inconsistently. Only the receipt identity is excluded; rates, affected counts
and actual economic values remain compared, with regression tests detecting
their changes. Multiprocessing's `__mp_main__` alias is excluded from captured
gameplay module globals, just like `__main__`.

Recording and cold indexing still take seconds on large worlds. This work does
not remove real causal events, change gameplay, compact the derived SQLite
index, or migrate existing trace files in place. Old checkpoint manifests still
enforce their source-fingerprint compatibility rules. Use a new run for the new
storage default; diagnostic legacy/dense modes and storage counters are
documented in [the storage guide](../../docs/trace_storage.md).

## Reproduction

```sh
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode legacy --output tmp/legacy.json
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode packed --output tmp/packed.json
env PYTHONHASHSEED=0 venv/bin/python -m benchmarks.benchmark_trace_storage --mode coverage --output tmp/coverage.json
env MPLCONFIGDIR=/private/tmp/coc-ai-mpl PYTHONPATH=tests:. venv/bin/python -m unittest test_trace_packing test_trace_codec test_trace_blocks test_desktop_trace_session test_ai_explainer_desktop test_simulation_semantics
env MPLCONFIGDIR=/private/tmp/coc-ai-mpl PYTHONPATH=tests:. venv/bin/python -m unittest test_simulation_checkpoint
env MPLCONFIGDIR=/private/tmp/coc-ai-mpl PYTHONPATH=tests:. venv/bin/python -m unittest test_native_simulation_checkpoint
```

The final implementation's legacy mode also has the quiet-boundary fix, so a
new 12-turn legacy run will not reproduce the old duplicate closures. The
checked-in comparison preserves that earlier baseline explicitly.
