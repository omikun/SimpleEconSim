# People network laboratory: first implementation verification

Date: October 28, 2026. Scope: standalone Network Laboratory, not full-game integration.

## Delivered

The [laboratory](../../docs/people_network_lab.md) runs a sparse directed relationship graph with four pressure channels, contextual trust, bounded sources, shared attention, damped propagation and explicit opposing-candidate resistance. It includes authored overlapping organizations, introductions, promises, task cooperation, an active rival, council challenges, continuous player identity across office changes, save/load/replay, time inspection and causal reconstruction.

A separate desktop entry point reads a terrain fixture (initially 180 cells; corrected to a verified 350-cell river catchment in the [overview revision](people_network_map_overview.md)) exported from the existing polygon generator. It does not construct economic agents or advance the existing world. `client.desktop` now resolves its public exports lazily so importing the laboratory does not initialize the full client. Tests assert the absence of economic engine imports and preservation of global RNG state.

## Reproducible political paths

All cases use seed 4243, an active rival, and legal commands. The [machine-readable acceptance summary](people_network_acceptance.json) includes state digests and measurements, refreshed after the geography correction; the political paths are unchanged. Reproduce with:

```bash
venv/bin/python -m scripts.playtest_people_network
```

| Start / policy | Rounds | Result |
|---|---:|---|
| Governing / public heuristic | 24 | Retains office, completes the upstream crossing |
| Governing / pass | 24 | Loses office in round 8; rival completes a project |
| Displaced / maintained organizers and a targeted pledge | 24 | Regains office in round 16 |
| Displaced / pass | 24 | Remains in opposition |
| Governing / checked continuous cycle | 30 | Loses office in round 11, regains it in round 24, honors the restoration pledge and completes a project afterward |

The continuous case is stored as [accepted player commands](../../scenarios/people_network/playthroughs/govern_restore.json). No fixture directly changes ballots or office. Each acceptance case replays both sides' journal and checks authoritative state digests. Controlled unit fixtures separately test institutional thresholds and response timing.

## Checks and measured limits

- 18 graph/game tests pass: propagation latency, cuts/directionality, opposing fields, stability, ordering, attribution, budgets, no double-counted effort, promise costs, hysteresis, restoration, succession, save/resume, replay and import/RNG isolation.
- Two Pygame controller/layout tests pass at 1100×800 and 1440×960. They exercise action previews, the decision loop, read-only historical inspection, save/load error handling, selectable contact markers, button bounds, and modal blocking.
- 27 existing desktop chart/explainer tests pass after the lazy-export change.
- A broader legacy world/action/trace test invocation aborted with exit 134 while initializing an OpenGL context (`cannot choose pixel format`). That invocation is not counted as a pass. It was not used as evidence for laboratory behavior; the laboratory initializes neither ModernGL nor the economic world.
- Rendered frames were visually inspected at the initial state, displacement/council view, restored government/obligations, and small-window causal view. These captures use SDL's dummy driver; they are not a claim of live human usability testing.
- On this arm64 development host with Python 3.13.1, acceptance rounds average roughly 3.8–4.4 ms, maximum approximately 5.1 ms, including checkpoint/trace bookkeeping and the rival. A separate 200-node/600-edge pressure fixture averages approximately 2.0 ms per pressure update over 100 updates, excluding rendering and checkpoint serialization.
- Complete uncompressed JSON exports are approximately 1.9–2.5 MB for 24–30 rounds, or 78–85 KB per round. The first implementation stores complete before/after state checkpoints for reliable reconstruction, rather than packed pressure arrays. It emits 95–253 semantic records per acceptance run; no mandatory edge-by-edge narrative stream exists. Compression/checkpoint deduplication can follow measured need.

## Changes made during implementation

Independent fields could saturate both candidates at one, trapping contested nodes. Candidate updates now include bounded mutual opposition, with the stability check and causal decomposition extended to include it. Organizer reinforcement was tuned to 0.20 and the round step to 0.60. Both strong competing attraction and weak engagement remain representable. These are gameplay tuning values, not empirical social measurements.

Equivalent appeals in transit are rejected; receiver and sender budgets are shared, and target channel evaluations are capped. An organizer that withdraws releases their reserved source/effort. Deadline failure is a historical consequence rather than a prohibition on late completion. State, sources and edge contributions reconcile including clipping, opposing resistance and gradual accumulation.

The implementation consolidates commitments, government and command handling in `people_network/engine.py` rather than splitting every proposed plan file immediately. The dedicated desktop interface likewise keeps its small panels together. Graph operations, dynamics, scenario ownership, events, persistence, terrain and the public rival policy remain separate modules.

Coordinator unavailability is a journaled scenario/debug operation: membership and peer links survive, and a deterministic available member succeeds the coordinator. Rich internal elections, coordinator-specific meeting bonuses and a one-round meeting interruption are deferred; this version's actual influence comes from people and edges, not the coordinator title alone.

## Remaining playtest gate

No human tester study has been performed. The proposed three-person formative test, enjoyment/replayability assessment, cross-player balance and real desktop input review remain open. Full graph diagnostics expose small-scenario structure; normal views focus on the selected person, council and active pressures. Counterfactual necessity is not asserted by the contribution trace; a dedicated counterfactual branching interface is deferred.

Recommendation: play and iterate in the standalone laboratory. Do not integrate with economic state, existing rebellion/regime outcomes, or national-scale population until human playtests show the loop is understandable and worth replaying. The 24-round debrief remains a concise event/status view with optional continuation, rather than a separately authored campaign ending screen.

## Follow-up: geography and readable overview

The [map/overview revision](people_network_map_overview.md) corrects the upstream/coastal placement and adds a large named graph, map-based reach and vote markers, community support summaries, explained next-action cards and plain-language in-game objectives. The expanded targeted suite passes 51 tests. The refreshed acceptance summary records current hashes and timings; initial timing figures above describe the original implementation run.

The later [strategy advice revision](people_network_strategy_advice.md) replaces the overview's initial ranking shortcuts with five-round branch comparisons and makes relationship lines thicker according to trust and capacity. The targeted suite now passes 55 tests; all five political path digests remain identical.
