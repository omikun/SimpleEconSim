# National causal trace optimization

Implemented 2026-10-27 following `053201b`. See the
[plan](../national_causal_trace_optimization.md) and
[benchmark data](national_causal_trace_optimization.json).

## Financial evidence is preserved

Tax receipts, spending, transfers, paid transactions, rejected/blocked actions,
and ordered public/bank account writes remain recorded. Unchanged balances do
not imply inactivity. A regression exercises a real +100 public account write
and tax flow followed by a -100 relief write and flow: all four events remain,
reconciliation retains both source IDs and zero residual, and gross inflows and
outflows are each 100.

Treasury reconciliation now adds both gross directions and per-kind counts and
totals alongside existing signed flows and unattributed residuals. These totals
describe the recorded national fiscal flows, not an assumption that every
unobserved transaction has been recovered. Internal cash/deposit movements and
membership changes retain their existing distinct reconciliation semantics.

Financial tests found an existing healthcare double count, reproduced with all
new options disabled: a -20 medical payment and its -20 regional summary were
both counted against an actual treasury loss of 20. Preserve both records, but
classify the summary as a `finance.public_healthcare_spending` observation.
The individual medical payment/receipt treasury legs and public account writes
remain. Public/private care, self-refunds, unfunded treatment, closure and
traced/untraced economic/RNG parity tests cover this correction. This changes
trace classification, not treatment or money movement.

## Less work before serialization

Standard unchanged snapshots are prepared directly as compact observations.
Turn/epoch/phase context is frozen once and shared; individual fields are
captured without constructing and copying a full logical event first. The
bounded writer packs these alongside ordinary events. Recent-event consumers
and disk readers reconstruct the original dictionaries, identities, before/
after values, sources, confidence and missing-source status when needed.

Rule certificates cover exactly checked no-write price bridges, unchanged
wilderness/retained Gini calculations, empty closing disease censuses and empty
tax-distribution calculations. Nonempty price writes, nonempty receipts, Gini
refresh samples, changed-to-zero observations, absent opening values and scalar
type/signed-zero differences keep their original evidence. An offsetting pair
of price writes is tested to retain both ordered steps even at zero net change.
An empty disease closing census does not remove any earlier onset, treatment,
exposure or mortality events.

Labor rollups now share a captured census rather than repeatedly deep-copying
its current/previous person arrays. Packet schema version 2 includes its own
shared-input table; all original inputs expand before replay or queries. A
private append-side capture prevents caller/recent-view mutations from changing
queued history. Every bounded packet is self-contained for seeks and forks.
Old packet schema version 1 and V3 traces remain readable. Old builds cannot
decode schema version 2; checkpoint source compatibility checks still apply.

## National contributions

Existing national aggregate records receive exact regional arithmetic ledgers
without adding event IDs or altering causal event ordering. Covered statistics
include stock aggregates, national reference prices, the national food-price
history, profession populations and chart reducers. Coverage follows the
recorded reducer: a missing recipe's zero contribution to the legacy food mean
stays explicitly distinct from a price observed to be zero. Partial reference-
price coverage is aligned by tile ID, not by zipping a shorter covered array
against the entire territory list.

Ledgers retain positive and negative regional contributions, opening/closing
boundaries, entry/exit, coverage changes, mean-weight effects, observed coverage,
currency/unit warnings and unexplained residuals. The initial missing baseline
stays unknown. An uncovered turn/epoch interval invalidates a cached opening
baseline instead of implying continuity. For example, a fixed regional value can change its contribution
when a new region changes a mean's denominator; the ledger separates that weight
effect from a local value change. Reconciled arithmetic does not establish the
upstream economic mechanism.

The on-demand AI packet includes exact summary totals plus at most twelve
regional changes per summary, selects material changes from both directions,
and prioritizes their current/opening sources before territorial list order.
At most four series summaries from the selected turn/command epoch enter a packet; omissions are
explicit. Full ledgers remain in the aggregate trace records. The prompt version
changes so old cached narratives are not reused under the new instructions.
No background model generation or paid provider call was introduced.

## Verification and reproduction

The comparison script requires identical original logical events after
normalizing only identity strings/checkpoint hash metadata and removing newly
added summary fields. It preserves all numeric scalars. The benchmark JSON
retains the resulting digest, original event counts by kind, state/RNG digests,
rule counts, packet counts, shared-input counts, integrity checks and timings.

Use separate sequential processes with `PYTHONHASHSEED=0` and the same seed.
The baseline disables `COC_TRACE_TEMPLATES`, `COC_TRACE_SHARED_INPUTS`, and
`COC_TRACE_NATIONAL_SUMMARIES`; defaults enable all three. These switches never
disable actual financial-flow instrumentation. Timings cover native
`step_world`, excluding map generation, hashing, queries and UI. Single local
measurements are diagnostic rather than latency guarantees.

Logical index rows remain: this work reduces event construction, copying and
encoded repetition. It does not implement a sparse SQLite index or eliminate
all per-metric iteration. Cold catalog building can remain several seconds and
must be measured independently. Larger/active worlds can have different costs.

Focused regressions cover reconstructed template equivalence, immutable inputs,
unknown/literal codec markers, independent shared-input seeks, invalid shared
references, zero-net flows/writes, regional offsets, mean membership changes,
missing coverage, missing baselines, residuals, historical/epoch boundaries,
pickle continuity, source prioritization and medical spending classification.
Broader financial, recorder, inspector, formula/audit and explainer suites and
separate fresh-process server/native checkpoint suites provide integration
coverage.

The final broad targeted group passed **201 tests**. All **four server checkpoint
tests** passed in a separate process. The **native Egypt continuation test**
passed, including fresh-process restore, full economic state, original-prefix
retention and graph aliases. A further **50-test** focused explainer/command regression run
checks the final selected-epoch filtering. No external model calls were needed.
Checkpoint suites remain isolated from the broad fixture process as required
by the existing shared-global fixture behavior. This is targeted acceptance,
not a claim that every unrelated project test passes; the previously documented
web Gini `replay_matches` expectation is outside this change.

## Measured result

Default native 1,000-tile map, seed/terrain/nation/NumPy seed 777, three turns:

| Measure | Previous packed path | Optimized, with national summaries |
| --- | ---: | ---: |
| Turn 1 | 4.010 s | 3.803 s |
| Turn 2 | 4.611 s | 3.688 s |
| Turn 3 | 4.459 s | 3.590 s |
| Total turn time | 13.080 s | 11.081 s |
| Trace bytes | 15,779,190 | 14,093,196 |
| Physical packets | 6,889 | 6,588 |
| Logical records | 785,108 | 785,108 |
| Cold F12 catalog | 9.641 s | 10.010 s |
| Warm F12 catalog | 0.068 s | 0.071 s |

The added optimization takes **15.3% less total turn time** and **10.7% less
storage**, including the new national summary evidence. Cold catalog construction
was **3.8% slower** in this sample; the change does not claim an inspector speed
gain. All 973 selected-tile catalog variants remain available.

All 785,107 original nonmetadata events match row by row after removing only
new summary fields and normalizing run/operation identity strings and checkpoint
hash/scope. Event counts by kind, sampled economic values and both Python/NumPy
RNG states match. The preserved original evidence digest is
`9e0d97e49201e5e0cabdec6eb9f920f9d789a128ac8f2c9f6c4046289aa63eb2`.
Both traces pass all three turn checkpoints. The healthcare classification
correction is covered separately by actual medical settlement/closure tests;
the default benchmark does not exercise public medical spending.

The optimized file contains 395,711 direct covered observations, 56,775 no-write
price certificates, 37,544 fixed-zero Gini certificates, 480 retained-Gini
certificates, 14,996 empty disease censuses and 11,856 empty tax-distribution
certificates. There are 6,224 shared census input uses across 3,025 self-contained
packet entries. These are representations of the original logical events, not
claims that those observations were deleted.

Benchmark samples were taken before the final uncovered-interval guard was
added. That guard leaves consecutive sampled turns unchanged and is covered by
explicit turn/epoch-gap regressions. The raw trace files remain local under
`tmp/traces`; the durable JSON retains the measurements and checks.
