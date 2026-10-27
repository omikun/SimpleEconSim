# Further event-reduction candidates after V5 grouping

Analysis 2026-10-27, implementation `f1da6c8`. This report changes no simulation
or recording policy. Counts are from retained native seed-777 benchmark traces:
default turn 2 and Egypt turn 3, both 1,000 tiles. These remain early worlds with
988 mostly empty wilderness tiles; counts are not universal active-world targets.

## Current denominator

Default turn 2 stores **40,263 actual events/groups**, including 4,442 coverage
anchors; Egypt turn 3 stores **42,475**, including 4,461 anchors. The old
262,026-expanded-event default denominator is no longer the right measure of
remaining opportunities. Financial movements and active causes are still explicit.

## Ranked candidates

| Family | Default candidate records | Share of remaining actual records | Proposed representation and causal requirements |
| --- | ---: | ---: | --- |
| Empty labor and demographic counts | 4,964 | 12.3% | Checked empty adult rollups/temporary-work means (1,976), zero registered birth/death counters (2,000), empty living-person counts (988). Preserve census eligibility, previous/current membership, age rule, counter inputs, source and lifecycle ordering; zero closing population does not mean no migration/death. |
| Empty exports, imports and pipeline | 2,988 | 7.4% | Empty exports (1,000), empty imports (988), zero in-transit samples (1,000). Require empty settlements/shipments and retain route/state/currency scope; pending/parked cargo remains outside this pipeline formula. Keep actual movements and receipts. |
| Empty wilderness production, population and trader cash | 2,964 | 7.4% | Three groups of 988. Checked no producer receipts, no resident IDs and no trader wallets, retaining the exact writer rule, sample point and dimensions. Nonempty membership with zero output/cash is a different condition. |
| Growth-rule outputs | 1,000 | 2.5% | Preserve fixed wilderness-zero versus insufficient-history/zero-baseline/full-window formulas. A zero growth output is not proof of unchanged population. |
| Unchanged effective workday samples | 1,000 | 2.5% | Retain effective and displayed statutory caps, production sample point and applicable policy source. Preserve changes and decisions even if the final statutory value is flat. |
| Further derived GDP/net-trade views | 1,988 | 4.9% | Zero wilderness GDP with zero food units (988), and net trade with both exports and imports zero (1,000). Preserve production/price and export/import source chains. A zero net with opposing flows does not qualify. |
| Transaction-price projection | 1,303 | 3.2% | Resolve the separate unit-price observation from its canonical paid sale, retaining its original ID, quantity, price, buyer/seller, total, currency, import flag and observation point. |
| Buyer order plus price-limit formula | 2,285 potential fewer records | 5.7% | A canonical order with quantity/funding and bid formula projections. Preserve distinct decision/calculation timing, original source IDs, repricing and failed/unfilled submissions. |
| Seller-receipt projection | Up to another 1,303 | 3.2% | A richer settlement could contain the receipt leg, but must preserve actual cash/wallet splits, journal references, recipient identity/location/currency and posting time. Higher risk than deriving unit price. |

The first five rows are the **same disjoint 12,916-record secondary pool**
identified earlier. It is now 32.08% of the remaining records, rather than 4.93%
of the old expanded count. Empty temporary-work means are already inside the
1,976 labor total; counting their 988 records again would inflate savings.

Egypt has 12,913 secondary candidates (30.40% of its remaining records): three
birth/death counters are nonzero and stay outside the pool. Its GDP/net-trade
pool is also 1,988. This is a candidate membership count, not authorization or
proof that every record can safely move to coverage.

## Account for new group overhead

Replacing 12,916 records does **not** remove 12,916 stored events. New coverage
needs additional anchors at phase/entity boundaries. A count-only replay of the
actual stored order, retaining exact turn/epoch/phase/base-entity keys and a
512-cell cap, gives:

| Hypothetical replacement | Default actual records | Reduction | Egypt actual records | Reduction |
| --- | ---: | ---: | ---: | ---: |
| Existing V5 | 40,263 | — | 42,475 | — |
| Secondary pool only | 31,347 | 22.14% | 33,562 | 20.98% |
| Secondary plus eligible GDP/net-trade | 28,383 | 29.51% | 30,598 | 27.96% |

The secondary-only default projection has 8,442 anchors instead of 4,442, so
the net saving is **8,916**, not 12,916. Adding GDP/net-trade avoids some of that
fragmentation, leaving 7,466 anchors. Replaying only the existing groups produces
exactly the existing 40,263/42,475 totals; these projections do not assume free
merging of the current groups.

This projection is not an implementation benchmark. It ignores encoded byte
limits, new rule validation costs and explicit intermediate publication points;
real groups can split further. No speedup is implied by these percentages.
Direct checked-rule capture must replace original emitter/row construction,
rather than wrapping fully built events in another container.

## Transaction matching evidence and limits

Checked parent links rather than assuming equal counts establish pairing:

- Default: 2,285 bids each link to one distinct submitted quantity order.
  Egypt: 2,862 such pairs. No repeated child per parent appears in these samples.
- Default: 1,303 paid sales each have one linked price observation and one linked
  seller-receipt record. Egypt: 1,337 such three-record sets. No repeated child
  per parent appears in these samples.

These prove linked matching in the sampled turns, not complete settlement
equivalence. Funding/public account writes, inventory provenance, tariffs and
FX operations can occur between projections. Retain their ordered evidence and
original references. A future canonical settlement must not present a later
receipt as known when the earlier sale was emitted. Partial failures and later
repricing need explicit handling. The seller receipt cannot simply be deleted
because the sale also contains a payment amount.

## Lower-priority candidates and events to retain

There are 480 elite operator evaluations in the default sample, 675 in Egypt.
Their count alone does not show redundancy. Only identical evaluation inputs,
constraints and outcomes could share checked decision coverage. Failed or
unaffordable relief/import/employment actions can explain a national crisis and
remain valuable. Likewise, 841 remaining default snapshots include actual
changes and baseline gaps; these are useful explanations, not the next target.

The 4,442 existing coverage anchors are already bundled, not another pool of
per-stat events. Relaxing phase/entity boundaries to merge them would complicate
historical indexing, ordering and fixed prefixes. The replay found no savings
from simply merging adjacent existing groups under the current rules.

Keep actual taxes, public spending, tribute, transfers, paid settlements, account
writes, debt/default, production shocks, disease/mortality, migration, policy
changes, failed actions and unexplained residuals. Preserve regional/cohort
sources and gross opposing directions even when national net totals are zero.

## Recommendation

Implement exact checked rules for the secondary pool and eligible GDP/net-trade
views first, with source/lifecycle/transition tests and sparse virtual-ID queries.
The count-only target is roughly **28–31 thousand** default events per turn,
about **22–30% fewer than the current 40,263**. Then assess the duplicate
transaction-price projection; combine buyer order/bid or receipt legs only with
a complete lifecycle design. Profile real turns before deciding which work
will improve latency most; count savings and CPU savings differ.

The subsequent [first-ten-turn profile](default_first_ten_turn_profile.md)
finds that fixed-schema capture and snapshot fan-out deserve priority over
further count reduction alone. Recursive `freeze` runs 22.3 million times in ten
turns; existing covered cells still incur substantial CPU work. Ordinary ten
turns take 33.62 seconds with tracing and 3.91 without, with matching economic
metric/RNG digests in this sample. No additional event culling is implemented by
this analysis.

[Raw counts, matching results, projections and illustrative excerpts](remaining_trace_event_candidates.json)
were generated by `tmp/analyze_remaining_trace_candidates.py` using only
`iter_storage_records`; no world simulation or model calls were required.
