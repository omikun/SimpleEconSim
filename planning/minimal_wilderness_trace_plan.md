# Minimal wilderness trace policy

Design and feasibility analysis: 2026-10-27, game implementation `1cbb5fa`.
User request: remove most wilderness tracing while preserving explanations of
meaningful events. The analysis below informed the implemented policy, validated
2026-10-27 against base commit `5246fe9`. See the
[implementation report](reports/minimal_wilderness_trace_implementation.md).

## Proposed change

Stop treating quiet, unclaimed wilderness as a fully instrumented economy.
Record a small initial frontier state, bounded per-turn coverage of checked
inactive domains, and actual changes/interactions. Do not construct hundreds
of per-stat facts and compress them afterward.

Simulation/chart histories may retain their existing padded defaults. A chart
history slot no longer requires an economic trace observation. New runs use an
explicit capture-policy version; existing traces retain their original evidence.

## What the investigation found

Default seed-777 turn 2 contains **40,263 stored events/groups**. Its 988
wilderness tiles directly account for **18,791 stored records** and **239,103
expanded facts**. One ordinary quiet tile produces 180 closing snapshots,
47 other checked facts and 15 standalone calculations, packed into 19 records.
Of the snapshots, 127 concern goods, largely because of zero-filled histories.

Two real exceptions occur among those directly scoped wilderness rows:

- Seven downstream-pollution events with actual source-tile/value arithmetic.
- Six changed water-pollution snapshots. One tile receives multiple events.

Preserve these thirteen records. Six additional group anchors are fragmentation
around the exceptions, not separate mechanisms.

A fresh native run inspected turns 0, 1 and 2. All 988 wilderness tiles have no
resident agents/entities, owner/nation membership, bank, government, charity,
currency, active faction members, active cargo, military units or active projects.
They qualify for a quiet economic-domain policy, with environmental changes
retained separately.

Object presence is not a valid activity test: all 988 have a FactionSystem
object, and 281 have route objects. Check real membership/cargo rather than
rejecting empty scaffolding. Existing comments about no wilderness factions or
routes are too broad for implementation guards.

Also, **281 tiles have background native population, totaling 23,028**. This
`wilderness_pop` scalar affects claims/resistance and differs from resident
agents and the current population history. No agent residents does not mean
uninhabited land. Preserve its initial values and changes.

### Trader reference prices are a genuine dependency

A three-turn scan inspected 81,785 retained stored records, including nested
inputs and checked cells, for references to candidate routine wilderness IDs:

- 698,498 candidate source IDs across the sample.
- **5,712 reference occurrences**, all in `trader_route_decision` records.
- **108 distinct referring decisions**, **374 distinct price observations**,
  **11 wilderness tiles**, and **187 distinct tile/good/value combinations**.
- All referenced metrics are `goods.price`. Repeated input/cause references
  contribute to the occurrence total; 5,712 is not a unique quote count.

Removing every wilderness price source would break real route explanations.
Capture prices when decisions actually read them, instead of capturing every
good on every wilderness tile every turn. The scan establishes the sampled
dependency; future consumers and transitions still require tests.

## Minimal record model

### Initial frontier state

Capture bounded batches of tile identities and meaningful initial state:
background native population, resident/ownership regime, watched ecological
values and necessary frontier fields. Reference existing geographic identity
where available. Do not copy whole regions or create 180 metric baselines and
numeric observation IDs per tile.

### Small exact-turn domain coverage

Check eligibility and meaningful state once per tile. Emit bounded cohort
records, for example at most 512 tile IDs per record: about **two records for
988 tiles per completed turn/epoch**. Include policy/rule version, exact boundary,
tile membership and the checked domains.

Coverage can certify no operating market and no resident agents while pollution
events coexist on those tiles. It must not assert that nothing happened.
Missing/incomplete coverage means unavailable, never inferred inactivity.

Watch a few meaningful fields, including native population and ecology, and
record actual changes with available sources. Preserve a gap if no source is
known. Do not scan all goods/recipe/labor histories to verify chart padding.

### Reference-price observations on actual use

Use the current number already read by a real decision/calculation. An
observation identifies tile, good, value, units/regime and observation point,
with basis **recipe/reference value on a tile without an operating market**.
It is not a paid transaction or a clearing price.

Capture the first consumed value and reuse the observation while its value,
identity, units and regime remain valid. Each consuming decision still freezes
the actual number used in its own inputs. Compare the actual value on use;
changes without a recorded writer create a new observation with its upstream
cause explicitly unknown. First-turn reads need truthful observations too.

No per-good capture is needed where nobody reads the prices. Audit all price
consumers: `meso/region_logistics.py`, `economy/capitalist_planner.py`,
`trace/innovation_trace.py`, `micro/labor_contract.py`, and national aggregation
in `trace/trace_snapshots.py`. Prefer an explicit observe-on-use API, preserving
ordinary market lookup behavior. The sample's 187 combinations are a sizing
observation, not a hard limit on required quotes.

Audit direct recipe-price reads too. For example, migration intent uses local
food price versus neighboring reference prices in `meso/region_logistics.py`.
Some consumers freeze numeric inputs without an explicit per-price source ID;
they do not appear in the source-ID dependency scan. Preserve their actual
inputs and add bounded quote references where necessary. Source-ID scanning
alone is not proof that nobody else reads wilderness prices.

### Actual events and conservative fallback

Always preserve pollution/advection, foraging/food creation, migration,
walletization/decashing, financial transfers, shipments, claims/resistance,
construction, military activity and other real events. Never suppress agent,
bank, public-account, FX or global events because a related tile is wilderness.

Initially keep full capture for wilderness with resident agents/entities,
active cargo, institutions, military units, active projects or unusual nation
membership. That protects homesteaders and authored scenarios while removing
the large quiet-tile workload. Environmental-only changes remain sparse events
and watched-state deltas; they do not require all goods/labor snapshots.

Preserve native-population changes and successful/repelled claims, including
origin counts, denominator, force/resistance and resulting membership. Some
claim details currently live in claim/ticker logs rather than uniform causal
events. Keep those logs and assess whether a concise structured transition is
needed; do not imply missing causal links are already complete.

## F12 and historical behavior

Resolve the tile's policy/domain record for the requested turn, epoch and fixed
published boundary. Index bounded cohorts/baselines/changes, not omitted metrics
or hundreds of virtual default observations.

- Padded market/labor/tax statistics say **not applicable** or **display default,
  not an observed economic statistic**. Avoid the generic "no trace found" error.
- A checked no-agent census can answer resident count zero from the cohort;
  background native population remains a separate concept.
- Ecology uses a recorded initial value/change and explicit watched-field
  coverage. Missing coverage remains a gap.
- Reference quotes retain their date/basis and do not manufacture market-price
  deltas. Real frontier/environmental events keep ordinary source traversal.

Applicability messages are deterministic and need no paid model request. The
loading UI remains for meaningful on-demand explanations. Existing chart
defaults remain visibly distinguishable from recorded observations.

## Remove CPU work at its origin

Filtering after `emit`, `snapshot` or `freeze` would miss the main benefit.
Apply the policy before constructing unused dictionaries, arrays and IDs:

1. `step_wilderness`: skip routine profession/Gini and synthetic economic trace
   emission for eligible tiles; preserve game/history updates.
2. `trace_snapshots.sample`: use the compact branch before per-good/per-history
   collection, including setup, pre-turn checks and closing.
3. `trace_snapshots.record` and labor census capture: bypass generic quiet-tile
   disease/labor/person-count, price-bridge and snapshot loops. Keep real census
   changes and meaningful watched fields.
4. `core/sim_engine.py`: skip empty wilderness export/import/net trace builders;
   preserve history updates and actual settlement events.
5. `desktop_trace_session`: compare compact state for between-turn changes.
   Do not rebuild the old broad sample merely to test whether something changed.
6. Price consumers: use on-use observations instead of periodic padded sources.

Invalidate stale metric/reference caches on regime changes. Prevent the generic
retained-zero profession/labor baseline loop from reintroducing omitted quiet
tile keys. A newly claimed market needs a valid new baseline; unknown openings
must not inherit an artificial padded economic baseline.

## Size target and limits

From actual turn-2 records:

- Outside directly scoped wilderness: **21,472**.
- Preserve thirteen nonroutine wilderness events/snapshots: **+13**.
- Two bounded cohort records: **+2**.
- Structural estimate: **21,487 records**, plus needed quotes/state/transition
  records, versus **40,263** now. A one-record-per-tile approach would instead
  total 22,460 before handling exceptions and quotes.

Aim to eliminate almost all routine per-stat wilderness emissions and roughly
**45–47% of whole-turn stored records** in this sample after small overlays.
Most of the 239k expanded wilderness facts should cease to be generated. They
are intentionally not reconstructed as hundreds of fake virtual observations.
This is a count/design projection; runtime improvement must be measured.

## Compatibility and implementation checklist

Version the capture policy in new-run metadata. V5 framing can carry the new
ordinary record kinds without silently changing digest/count meaning. Old files
remain readable; old-policy resumes retain their policy unless an explicit
transition is supported. Normal checkpoint source compatibility still applies.

Minimal runs intentionally have fewer expanded facts. Compare economic state,
RNG and all protected event values/constraints/source relationships, allowing
explicit source-ID remapping and truthful new quote observations. Do not require
equality to the padded observations deliberately removed.

- [x] Add policy metadata, eligibility, sparse initial state and bounded
  exact-boundary coverage; retain a full diagnostic policy.
- [x] Add on-use price observations at the audited consumers; test accepted/rejected
  decisions, current values, changed values and valid source IDs.
- [x] Add early sampler/emitter branches without per-good construction or
  ID allocation for omitted defaults.
- [x] Add historical applicability/default handling and sparse lookup, with
  no unnecessary provider calls.
- [x] Test empty scaffolding versus real faction/cargo activity; homesteaders;
  enter/leave/re-enter and same-turn migration; native population/displacement;
  successful/repelled claims; pollution; institutions and nation membership.
- [x] Preserve fiscal/financial legs, source links, gaps, unknown baselines,
  changed-to-zero cases and effects into later active turns.
- [x] Test command epochs, fixed prefixes, missing coverage, index rebuild,
  corrupt/torn data, old formats, checkpoints and fresh-process forks.
- [x] Compare isolated full/minimal first-ten-turn default runs and profiles,
  full economic state/RNG, protected evidence, authored Egypt and focused
  frontier transitions. Report measured CPU, counts and query behavior.
- [x] Document results and commit the completed implementation without pushing.

Design, implementation and acceptance are complete and included in the delivery commit.
Claim/displacement and wallet behavior retain their existing logs and regression
coverage. This optimization does not add missing structured claim-source
contracts. History scaffolding and the short three-good trade-flow check remain;
the large per-stat economic sampler/emitter paths are bypassed. Nonempty or
cause-bearing trade summaries remain even when their numeric total is zero.

[Raw analysis](reports/minimal_wilderness_trace_analysis.json)
contains the captured exceptions, fresh eligibility census and dependency scan.
Local drivers: `tmp/analyze_minimal_wilderness_policy.py` and
`tmp/check_wilderness_external_dependencies.py`. No model calls were used.
