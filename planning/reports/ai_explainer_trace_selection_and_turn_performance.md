# Desktop explainer selection and turn performance correction

Date: 2026-10-26. Baseline: `f73bd97`, before this correction.

## Player-visible result

F12 now lists recorded metric/subject variants for the selected entity and
turn. Good, profession, livelihood, disease, class, and other scalar subject
dimensions accompany the request automatically. Searching filters these
recorded choices rather than the entire metric registry. Empty results and
turns without a completed sample have a visible empty state and cannot submit
an invented selection.

The drawer follows clicks on uncovered map tiles. **Change tile / nation**
opens a searchable entity list; Tab/Shift+Tab also cycle entities. Turn buttons
and Left/Right select a turn, and Refresh reads new published evidence.
Switching map tiles while viewing a narrative returns to the new tile's stat
picker without generating another narrative. A **Choose another stat / tile**
button offers the same path from a result or error.

F12 replaces an open F11 panel, whose input handler otherwise consumes map
clicks. Both native map-selection functions clear stale chart selections so
the AI launcher cannot keep using a chart from a previously selected tile.

## Root causes

1. The old F12 picker listed all 388 registered metrics for every entity. Most
   agent, AI, nation, FX, and dimensional metrics do not exist for an arbitrary
   tile selection. Choosing a price also omitted its good unless the player
   manually typed a dimension. Valid trace data existed on turn 2, but the
   offered query often did not match it.
2. The picker captured its entity once when opened and never followed later
   map selection. An open F11 inspector could also swallow those map clicks.
3. `record_labor_censuses` scanned the whole previous metric inventory for
   every tile and both categorical census dimensions. The default 1,000-region
   map therefore performed repeated scans over roughly 180,000 sampled stats.
4. Gini snapshot recording searched the entire tile list for each tile/good
   sample. Common subject identities were repeatedly serialized as JSON.
5. Recording remains intrinsically substantial: this map writes about 261,000
   causal records per turn. Event construction, JSON serialization, compression,
   hashing, and publication account for much of the remaining cost.

No provider call was involved in the measured turn latency. Generation remains
explicitly requested per stat.

## Implementation

- Add `TraceIndex.available_metrics` to group exact recorded metric/subject
  variants at a fixed published boundary without decoding their event bodies.
- Add a disposable SQLite entity/turn expression index and let normal evidence
  queries use the same literal JSON paths. Existing sidecars upgrade in place;
  the authoritative compact trace format is unchanged.
- Freeze the boundary on the UI thread, then perform local catalog indexing on
  a lazy, single-worker executor. Display **Reading recorded stats…** while it
  runs. Only user requests create this local indexing work; opening the picker
  never invokes the provider.
- Cancel pending superseded lookups, ignore running stale results, clear stale
  buttons, and reject stale/empty metric choices. Workers retain paths and
  immutable query arguments, not the live world graph.
- Validate bounded scalar dimension maps, disallow entity overrides and
  nonfinite floats, and retain compatibility with existing dimension fields.
- Group previous labor categories once per recording pass, preserving removed
  categories and zero-closing evidence. Build one tile lookup per snapshot
  pass. Bound caches for the two common immutable subject shapes, retaining
  exact JSON keys and the general path for arbitrary subjects.
- Exclude the drawer's live Future from native checkpoint serialization and
  restore the drawer in the running world after the save attempt.

## Controlled performance comparison

Local Python 3.13 virtual environment, saved default 1,000-region topology,
seed/terrain seed/nation seed 777, initially 1,197 agents, three native turns,
`PYTHONHASHSEED=0`. Runs were sequential without another test workload during
the timed steps. Baseline functions were loaded from `f73bd97`; the optimized
run used the working source. These are elapsed simulation-step times, excluding
map generation, evidence queries, UI rendering, and profiler overhead.

| Turn | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| 1 | 6.275s | 4.690s | 25.3% |
| 2 | 10.257s | 5.147s | 49.8% |
| 3 | 10.427s | 5.219s | 49.9% |
| Total | 26.959s | 15.057s | 44.2% |

Both runs produced 785,108 records, including setup and checkpoint records.
The normalized sampled metric digest was identical:
`0981a125fae60b7f427388f785f0556895577628689e7e14a822955ce4e9da15`.
The decoded evidence digest was also identical after normalizing random run
and operation identities and omitting the identity-dependent checkpoint hash:
`4f8b084c4a9a959f220a4001314908ca3da1c1ed19bddf011ec078746a4d0634`.
The change does not obtain speed by removing trace records or changing rules.

Separate two-turn profiles explain the improvement: labor census recording
dropped from 5.112s to 0.285s cumulative profiler time; subject-key handling
dropped from 2.567s to 1.329s despite the added shared Gini lookups. Total
profiled step time fell from 24.377s to 17.758s. These profiles characterize
the hotspots; the unprofiled table is the player-latency comparison.

Raw local diagnostics: `/private/tmp/coc-perf-v2-before.json`,
`/private/tmp/coc-perf-v2-after.json`, `/private/tmp/coc-native-before.prof`, and
`/private/tmp/coc-native-final.prof`.

## Validation

116 targeted tests passed:

```sh
env MPLCONFIGDIR=/private/tmp/coc-ai-mpl PYTHONPATH=tests:. \
  venv/bin/python -m unittest \
  test_ai_explainer_desktop test_ai_explainer_service \
  test_ai_explainer_integration test_labor_census_trace test_trace_index \
  test_run_trace test_desktop_chart_trace test_trace_audit test_trace_blocks \
  test_trace_codec test_trace_commands test_trace_explanation \
  test_desktop_trace_session
```

Coverage includes demand-only behavior, typed dimensional selection, exact
entity/turn/boundary matching, missing records, map and search selection,
switching while loading, stale results/buttons, switching away from an existing
narrative, transient Future handling during saves, single-pass census inventory
scanning, removed census categories, exact cached subject keys, trace integrity,
chart evidence, treasury closure, and shared web-service compatibility.

A real seeded native turn-2 smoke check opened F12 on `c0`, obtained recorded
choices, generated population, GDP, and food-price packets with a fixture
provider, switched to `c17`, and drew the resulting picker. Opening the drawer
took 0.000304s before asynchronous indexing. Picker discovery and tile switching
made zero provider calls; exactly three explicit requests called the fixture.
All 909 offered turn-2 `c0` variants passed dimension validation and matched
recorded evidence. The recorded metrics, trace count/digest, and Python gameplay
RNG remained unchanged.
All 523,173 records and both turn checkpoints passed trace integrity checking.
Results are in `tmp/ai-explainer-native-turn2-fix.json`; the visually inspected
drawer render is `tmp/ai-explainer-picker-fixed.png`. These checks use a fixture
provider and do not spend API credits.

`test_native_simulation_checkpoint` still fails its existing fresh-process
canonical-state comparison, showing `total_light` entries with equal displayed
values among its first reported differences. The same failure was reproduced
using the original test and original trace/checkpoint sources from `f73bd97`
in a temporary module overlay, including its fresh subprocess. This pre-existing
continuation failure is separate from the corrected picker and optimizations;
the focused native save test verifies that an in-flight picker Future is never
serialized and the live drawer is restored after saving.

## Remaining limits

The first lookup on a large, unindexed trace can take several seconds; the UI
now stays available and shows local evidence loading. Full causal recording on
1,000 regions still costs several seconds per turn. Larger trace-format or
storage changes would require separate compatibility and evidence-retention
work. Historical content, model settings, and gameplay mechanisms are unchanged
by this correction.
