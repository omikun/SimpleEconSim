# People network: first implementation plan

Date: October 28, 2026.
Status: first standalone implementation delivered October 28, 2026. This plan records the intended design; the [guide](../docs/people_network_lab.md) and [verification report](reports/people_network_coalition_mechanics.md) describe implemented behavior, adaptations, and remaining human playtests. Full-game integration remains deferred.

Rules version 2 adds [coalition maintenance mechanics](people_network_coalition_mechanics.md): competing group demands, conserved public allocations, conditional agreements and volunteer strain.

Related: [manifesto](../docs/gdd.md#manifesto-a-nation-is-a-network-of-people), [initial design discussion](people_network_layer.md), [existing rebellion design](../docs/rebellion.md).

Revision, October 28: [graph dynamics and minimal causal trace](people_network_graph_dynamics.md) specifies the pressure-propagation model requested for this layer. It replaces the initial invitation-only recruitment proposal and governs pressure updates, competing spheres of influence, and trace attribution.

## 1. Outcome and design contract

Build a small, playable **Network Laboratory** over the terrain map. The player assembles cooperation through relationships, governs through a coalition, can lose office, and can organize a return with the same people and organizations. Demonstrate meaningful network effects before connecting them to the economy.

The first release is complete when a tester can play an uninterrupted govern → displacement → organize → restoration → govern sequence, understand why cooperation spread or failed, and identify consequences of promises made earlier. Displacement is contingent during ordinary play; a second start makes recovery immediately testable. A successful player must be able to avoid displacement.

The following choices are proposed defaults for the first implementation. They resolve scope questions without claiming a final design for the full game:

| Decision | First implementation |
|---|---|
| Client | Local Pygame desktop laboratory with headless runner |
| World | One small terrain scenario, four named locations |
| People | 32 individually simulated adults, including player and rival |
| Communities | Four persistent, overlapping organizations |
| Political institution | A nine-person council choosing the officeholder |
| Main task | Restore a flood-damaged shared crossing through cooperation |
| Run length | 24 decision rounds, with optional continuation |
| Player identity | One living individual, persisting after loss of office |
| Rules | One social engine for player, rival, governing, and opposition |
| Time | Laboratory decision rounds; no aging or seasonal clock |
| Integration | No economic, military, demographic, or existing rebellion updates |

The council is a bounded test institution. It is not a universal model of government, revolution, or nineteenth-century politics. The crossing is a coordination task with abstract effort requirements, not a second construction or goods simulation.

## 2. Scope boundaries

Include an explicit directed weighted graph, continuous pressure propagation through contacts, opposing influence fields, contextual trust, group membership, issue preferences, limited attention, persistent organizations, negotiated promises, rival organizing, council support, task delivery, save/resume, and minimal causal tracing of interventions and inflection points.

Defer household simulation, money and goods, taxation, production, warfare, violent coups, assassination, secret networks, death and succession, migration, arbitrary graph editing, procedural relationship generation, multiplayer, browser parity, and live switching of simulation modes. Do not add economic integration to make an uninteresting network loop appear busy.

Keep all prototype abstractions visible in the briefing. A person represents one person in this scenario; do not silently multiply an organizer into hundreds of invisible followers. Every participant is counted once even when belonging to several organizations.

## 3. First scenario: The Broken Crossing

### Geography and communities

Four sites occupy a connected patch of terrain: the council town, an upstream farming village, a riverside workshop settlement, and a market landing. The damaged crossing links communities politically and is drawn on the map. Its repair does not modify real trade routes in this version.

Four organizations provide overlapping relationships: cultivators' association, craft mutual-aid society, traders' circle, and civic service association. Membership, not geography alone, defines each group. Include cross-region contacts, members with more than one affiliation, a highly connected but distrusted figure, a locally trusted organizer, and at least two different bridges between communities. The player and rival are members of this society rather than external controllers.

Author these people and links in data with stable IDs. Names and descriptions should make motives readable without relying on stereotypes. Initially use one authored graph with several starting-state variants; randomize only explicitly declared setup choices. Do not confuse variation in starting trust with testing different topologies.

### Task and political conflict

The crossing needs cooperative effort from at least two locations and two skill categories. For the first tuning pass, require six work contributions and four hauling contributions in each of three consecutive work rounds, with participants from at least two locations each round. A shortfall resets the consecutive-round counter, with an explicit explanation. A person provides at most one contribution per round; skill eligibility and willingness are separate. One well-connected individual cannot supply the task personally.

Choose between two repair packages: prioritize upstream access or market access. Both repair the crossing, but groups value the distribution of access differently. Each package has the same visible total effort requirement initially, making coalition choice—not hidden arithmetic—the experiment. One active package exists at a time; switching it cancels pending invitations and clearly warns that work progress and incompatible promises will be affected. Initial rule: reset project progress on a package switch to avoid ambiguous partial work.

Each accepted package has a public deadline, initially six rounds after adoption. The incumbent controls adoption and scheduling. An opposition leader can recruit, negotiate and propose an alternative, but cannot spend public authority. Supporters of an opposition repair proposal remain available for organizing rather than producing an unauthorized second crossing. Restoration allows that proposal to be adopted with its existing commitments, subject to revalidation.

At least one promise concerns a real choice the incumbent can honor: appointing one liaison from a partner organization to one of two liaison posts within two rounds of taking office. At least one concerns the repair package. Posts provide a bounded organizing benefit, such as one extra outgoing invitation for the appointed liaison, rather than guaranteed votes. Limited posts and incompatible package preferences create real bargaining costs.

Completion, missed deadlines, appointments, and broken promises change contextual trust and issue satisfaction through declared rules. No invisible legitimacy bonus automatically recruits the whole map. A completed crossing becomes a maintenance task with a lower recurring contribution requirement, keeping governing relevant after success. Initial maintenance: two eligible contributors per round after a two-round grace period; two consecutive shortfalls trigger a visible service failure. Exact counts are tuning data.

### Two starts, one rule set

- **Fragile government:** the player holds office with five of nine councillors behind them. A rival has a credible alternative coalition. There is enough time to deliver or negotiate; removal is not scripted.
- **After displacement:** the rival holds office and the player retains some contacts and unfulfilled commitments. The briefing describes the authored initial displacement; subsequent events use normal rules. This is an alternative scenario start, not a claim that its history was simulated.

Keep the same people, institution, relationships, and action rules in both. A diagnostic fixture may remove an organizer temporarily to test organizational resilience, but this is not a normal player action in the first release.

## 4. Data model and ownership

Use a dedicated `people_network/` package with explicit imports. Proposed records:

| Record | Minimum fields and meaning |
|---|---|
| `NetworkSession` | Schema/rules version, mode, scenario ID and content digest, seed, round, phase, player ID, network state, queued commands, action journal |
| `Person` | Stable ID, name, location, skills, issue preferences, participation threshold, memberships, available effort, council eligibility |
| `Relationship` | Directed source/target IDs, contextual trust values, descriptive relationship type; sparse adjacency |
| `PressureState` | Per-person/per-channel bounded pressure, interest anchor, decay, response rate, entry/exit thresholds; candidate margins are derived |
| `PressureSource` | Person/channel, signed bounded forcing, origin event, start/stop rounds, effort requirement and shared output budget |
| `Organization` | ID, members, peer links, current coordinator, shared purpose, meeting capacity; survives coordinator departure |
| `Goal` | ID, sponsor, kind, package, eligibility, deadlines, effort requirements, progress, status |
| `Invitation` | Sender, recipient, goal, originating action/event, send round, delivery round, expiry |
| `Commitment` | Person, goal or candidate, state, next review, effort allocation, explanatory event |
| `Promise` | Promisor, beneficiary, exact condition, deadline or activation condition, status, fulfillment evidence |
| `Government` | Officeholder, councillor IDs, ballots, challenge state, liaison posts, last transition round |
| `NetworkEvent` | Stable event ID, round/phase, kind, actors, goal, parents, inputs, result, reason codes |
| `RoundCheckpoint` | Pressure arrays, commitments, active sources, graph revision, replay cursor and canonical digest; reconstructs omitted edge detail |
| `TerrainContext` | Geometry, bounds, stable location IDs, anchors, adjacency and map provenance; presentation/geography only |

Trust is directed: a recipient's trust in a sender determines receptiveness. Distinguish trust in organizing from trust in governing. Membership supplies contacts and continuity, not automatic obedience. A coordinator has limited meeting capacity; every member can refuse a task. In this version a meeting is a narrated use of the coordinator's invitation capacity through existing member contacts, not an unlimited broadcast or a separate influence bonus.

The authoritative structure is one sparse directed weighted graph, with node/edge dictionaries and incoming/outgoing adjacency indexes. Organizations are membership sets with actual peer links; terrain adjacency is separate. Graph operations compute local pressure updates, reachable contacts, causal paths, connected components and bridges/cuts. Avoid building complete organizational cliques or calculating global centrality as a persuasion rule. Sources and graph drawing are distinct: force-directed visual layouts cannot determine influence.

All rules mutate session-owned state through the engine. Renderers and inspectors read snapshots. Network `Person` records are laboratory identities; a later adapter can map them to existing agents without modifying `Agent` now. Never write laboratory office changes into real `Nation` or `Region` objects.

## 5. Recruitment and network effects

### Pressure propagation is the underlying simulation

Use a deterministic, synchronous, damped graph update, with seeded initial conditions. People carry bounded pressure fields for each candidate and active task. Directed contextual trust determines channel conductance; influence propagates through existing contacts every round, including rounds without a new invitation. Actions and ongoing organizing introduce bounded local sources. Interests anchor a person's response; decay, limited attention and competing obligations resist pressure. Commitment feedback can reinforce a movement, within explicit effort and source budgets.

The [technical specification](people_network_graph_dynamics.md) defines the starting equation, stability constraint, capacity normalization, graph operations, boundaries and exact trace requirements. Validate those rules before balancing. This is a physics-inspired social model, not a claim that political influence obeys physical conservation or that force-directed graph layout simulates politics.

Track player and rival pressures separately, then derive a margin. High pressure from both sides is contested; weak pressure from both sides is disengagement. Sphere boundaries emerge along graph cuts and contested nodes, can span regions, and can move as opposing sources strengthen, decay, or lose bridges. They are not hard territorial borders or a second ownership system.

An explicit invitation delivers a bounded source to a contact, sharing receiving capacity with other appeals. It does not bypass graph evolution with an independent success score. Do not also apply the former committed-peer scoring bonus: peer reinforcement is already represented by transmitted pressure and declared commitment-backed sources. Candidate and project channels remain separate so opponents can cooperate on a useful task.

Actual allegiance and work commitments require sufficient pressure plus eligibility, capacity, and thresholds with hysteresis. The model must permit stalled cascades, persistent communities, competing fronts, and shifts after source/bridge changes. A large number of contacts cannot supply unlimited transmitted pressure or guarantee cooperation.

### States and attention

Use `unaware → aware → willing → committed → acted`, with `declined`, `withdrawn`, `completed`, and `expired` outcomes. Awareness may arise through ordinary network transmission or a direct appeal. Awareness persists; pressure continues evolving during a two-round decision-review cooldown. Willingness is an evaluated disposition, not effort delivered. A committed person must still be available when execution occurs.

Each person has one effort slot per round. Allocating it to organizing prevents contributing labor that round. A council ballot is a separate institutional action; it does not create extra effort. A committed organizer can send at most two invitations to existing contacts per round; a liaison may send one additional invitation, sharing the same total source budget. Newly recruited people can organize starting the following round. Limit each recipient to two targeted appeal evaluations per round and one combined appeal per goal; allocate excess requests with declared stable rules. Continuous pressure evolution is not suspended by that appeal cap.

Multiple appeals share bounded receiver/source budgets; repeated messages cannot multiply influence without limit. All transmission traverses existing channels. A two-party introduction action can create a low-trust edge when a mutual contact agrees; it does not create trust or commitment for free. This is the only normal edge-creation action in the first version. Relationship/availability changes are explicit graph mutations that affect later propagation.

Committed participants review their involvement after package changes, broken promises, capacity conflicts, or declining support, while continuous pressure evolves each round. Use a lower continuation threshold than entry threshold to provide staying power without permanent loyalty. Initially require a two-round minimum commitment unless its goal changes incompatibly. Record withdrawals and their causes. Clamp trust, use bounded event-specific updates, and never let raw centrality become a universal persuasion statistic.

Organizations persist through their membership and peer links. If a coordinator becomes unavailable, eligible members select a replacement using declared willingness and internal trust. Meetings pause for one round; member contacts and commitments remain. A fragile star network should lose more reach than a mature group, without making either result inevitable.

## 6. Player commands and government continuity

The player receives two political action points per round. Approach, introduce, propose/withdraw a promise, organize, adopt a repair package, appoint a liaison, and request a council challenge each cost one point. End round costs none. Personal work costs one point and uses the player's effort slot. A pass is legal. The rival has the same action budget and command validation.

Action previews show eligibility, cost, timing, affected commitments, and likely reasons for acceptance/refusal. Start with full information; fog of war is deferred. Every action that cannot be taken has a specific reason. Reject invalid commands without spending action points or changing state. Accepted commitments do not retroactively give back spent actions. Prevent incompatible promises from being simultaneously accepted; allow explicit renegotiation or renunciation with shown consequences. An approach sends an invitation through an existing contact; organizing reserves one's effort to forward invitations toward a specified goal on the next round. Both use the delivery, attention and capacity rules above.

### Council and office rules

Every councillor can commit to one candidate at a time. Council allegiance reads candidate pressure, relative margin, program alignment, review timing and commitments under the same graph rules used for everyone else. Councillors assess player and rival from the same snapshot; ties retain the existing allegiance or remain undecided. A large competing pressure can cause withdrawal without an immediate switch. There is no automatic delivery of an organization's council votes by its coordinator.

A challenger can request a confidence vote after holding at least five declared council commitments for two completed rounds. The next round displays a pending vote and allows a response. At resolution, each councillor casts one ballot according to current valid support. Five of nine votes transfer office; otherwise the incumbent remains. Apply a two-round challenge cooldown after any vote. Prevent simultaneous and repeated challenges from consuming the same round. With only two candidates, only the non-incumbent can initiate one.

Transition changes officeholder, institutional command permissions, and vacant liaison appointments. It does not change player ID, erase relationships, clear promises, or grant control of the victor. Office-dependent promises activate on gaining office; their activation rules and deadlines are shown when making them. Existing public project progress remains under the new administration, while conflicting commitments are reviewed. Neither removal nor restoration instantly changes everyone else's allegiance.

An incumbent who honors commitments gains practical cooperation. An opposition player loses appointment/adoption powers but retains approaches, introductions, movement organizing, promises contingent on office, and challenges. The screen immediately explains the new options. There is no death, imprisonment, or exile lockout in this slice. At round 24 provide a debrief and optional continuation rather than declaring all opposition runs lost.

## 7. Authoritative round order

1. Player submits validated commands within the action budget; accepted commands have stable IDs and are journaled. No hidden round advance occurs on inspection.
2. Rival selects commands using only the same public start-of-round information, then validates them through the same API. It cannot inspect the player's uncommitted command queue.
3. Freeze the resolution snapshot. Resolve mutually conflicting proposals with documented stable ordering; do not let dictionary iteration choose winners. Apply exclusive post appointments only for the incumbent.
4. Deliver appeals due this round and construct bounded sources. Advance pressure fields synchronously over the frozen graph, retaining both opposing fields and recording compact checkpoints. New node pressure reaches downstream contacts on a later update. Evaluate pressure thresholds, margins and review constraints; enqueue commitment/allegiance/boundary transitions with local decompositions.
5. Apply commitment updates, allocate available effort using explicit person preferences and stable tie breaks, and deliver project/maintenance contributions. A newly committed person begins work next round. Current organizers sustain sources within their effort/output budgets; changes take effect in the next pressure update.
6. Resolve appointments, goal results, deadlines, promise fulfillment/breach, and bounded trust updates. End-of-round fulfillment counts before declaring a same-round deadline breached.
7. Record council commitments, update sustained-support counters, and resolve any vote scheduled for this round using current valid ballots. Process office transition once; new office powers become usable next round.
8. Queue forwarding/meetings for next round, record graph/source changes and semantic inflections with causal links, checkpoint the state, run numerical and game invariants, increment the round, and refill budgets.

Document the exact snapshot boundary for each rule in the engine and tests. Trust changes from this round affect conductance next round. Pending invitations deliver one round after sending; no same-round recursive cascade. Preserve the phase's graph revision in causal reconstruction rather than using later weights. An engine call advances exactly one decision round. Display the round label rather than importing the game's lifecycle-year clock.

## 8. Rival behavior

Use a small inspectable heuristic, not an LLM or search over secret state. Each round consider: protect existing pivotal commitments; repair a promise at risk; recruit a bridge or councillor; advance the public task if incumbent; call a valid challenge if opposition. Estimate gain with the same public scoring helpers, subtract action and promise costs, and prefer coalition diversity when gains are close. Resolve ties by stable IDs.

Keep candidates considered and the chosen reason in optional developer diagnostics; the minimal authoritative trace journals the accepted command and its source. The rival may fail and may keep governing successfully; do not secretly force a reversal to showcase the feature. Scripted pressure events may change public issue priorities in both starts but cannot directly assign votes or office.

## 9. Terrain and interface

The initial screen contains terrain, four location labels, selected markers, an office/round/action strip, the active task, and a short event feed. Avoid showing all 32 people and all edges simultaneously.

Selecting a location opens its people and organization summaries. Selecting a person shows their role, memberships, current commitments, trust context, and a one-hop contact diagram with at most eight visible contacts plus an expandable list. Overlapping markers use a selection list. Contact layout is stable while selected and separate from terrain coordinates.

Selecting a goal highlights relevant locations and recent recruitment paths. Arrows distinguish pending invitation, accepted commitment, and delivered cooperation using labels or patterns as well as colors. Terrain anchors and lines transform with the same camera; hit-testing must match zoom and pan. Cross-region links remain visible when relevant; no regional graph screens are required.

Add a pressure overlay with dominant candidate, absolute engagement, contested nodes, and transmitting edges. Boundary inspection shows both camps' pressure, change since the previous round, key incoming contributions and resistance. Use graph boundaries even when they form geographically scattered pockets; do not draw continuous territorial fronts unsupported by actual connections. A history scrubber reads checkpoints without advancing play and highlights recorded inflection points.

The council view shows nine distinct councillors, declared allegiance, pending vote timing, and the reasons a pivotal member may change. The promises view shows who expects what, when it becomes due, and conflicting obligations. A displacement banner explains lost institutional actions and available organizing actions; the player portrait and identity remain the same.

Example explanation: “Mara agreed to haul: pressure arriving through Ilyas and her workshop contacts overcame her reluctance, the upstream package benefits her village, and she has an effort slot available. She starts next round.” Selecting it reveals the pressure history, signed contributions, relevant threshold and capacity check. Highlight enough of the chain to inspect how mobilization radiated beyond the initial organizer.

Provide explicit End Round, Save, Load, Restart Same Setup, Change Start, and Exit controls. Debrief includes office changes, coalition composition, delivery, broken promises, and a few decisive recruitment chains. Keep the full graph, raw scores, alternate scores, and all rival decisions in a developer inspector/export.

## 10. Architecture and repository touchpoints

### Findings from current source

- `client/worldview/worldview_engine.py:build_world_view` calls `core/sim_world.py:build_world`, then builds a view around economic tiles and nations. It is not a terrain-only constructor.
- `core/sim_world_voronoi.py` imports `Region`, `Nation`, finance and trade modules while adapting `PolygonMapGenerator` geography into a world. Reusing this full builder would instantiate unwanted systems.
- `core/sim_engine.py:step_turn` advances AI intents, local economies, trade, and other systems. It must not run in laboratory mode.
- `client/worldview/worldview_map.py` and camera modules expose compatibility facades over `client/desktop/`. Prefer canonical desktop components for new rendering work.
- `client/desktop/app.py` imports many economic panels. Do not add a large laboratory branch throughout its event loop. Use a dedicated entry point and small reusable rendering helpers.
- `client/web/mapgen_server.py` contains geometry/rendering helpers alongside HTTP, GPU workers, and writable saved-slot behavior. Extract or reuse lower-level pure terrain helpers after checking their dependencies; do not import/start the server to obtain a map.
- `sim_server/sim_server.py` and `core/simulation_checkpoint.py` are built around the full simulation. First-version network persistence should not require constructing a `SimServer`.

### Proposed files

All paths below are relative to the repository root and proposed unless explicitly identified as existing.

| Path | Responsibility |
|---|---|
| `people_network/model.py` | Records, enums, version identifiers, canonical serialization |
| `people_network/scenario.py` | Data loading, validation, authored initial states |
| `people_network/rules.py` | Pressure-to-decision thresholds, invitations, capacities, commitments and promises |
| `people_network/graph.py` | Sparse adjacency, validated graph mutations, reachability and bridge/cut queries |
| `people_network/dynamics.py` | Bounded synchronous pressure update, source budgets, conductance, margin/boundary derivation |
| `people_network/government.py` | Council/challenge/transition rules |
| `people_network/engine.py` | Authoritative commands and round phases |
| `people_network/rival.py` | Bounded opponent policy using public state |
| `people_network/events.py` | Minimal action/change/transition trace, checkpoints, causal reconstruction and inflection queries |
| `people_network/persistence.py` | Atomic versioned save/load and replay validation |
| `people_network/terrain.py` | Terrain-only adapter and stable location anchors |
| `people_network/cli.py` | Headless play, scripted commands, exports and sweeps |
| `scenarios/people_network/broken_crossing.json` | People, directed links, groups, goals, starts and tuning |
| `client/desktop/network_lab.py` | Dedicated desktop launcher, event loop and session controller |
| `client/desktop/panels/network_panel.py` | People, goal, council and promise views |
| `client/desktop/map/network_overlay.py` | Markers, arrows, selection, focused graph view |
| `tests/test_people_network_*.py` | Rules, continuity, persistence and isolation checks |
| `scripts/playtest_people_network.py` | Reproducible acceptance runs and summary reports |

Suggested future launch commands: `venv/bin/python -m client.desktop.network_lab --start governing --seed 4243` and `venv/bin/python -m people_network.cli --start displaced --seed 4243`. They are planned interfaces, not commands that work today.

### Terrain reuse spike

Before UI implementation, identify the lowest-level `PolygonMapGenerator` geometry and projection helpers that can load a fixed terrain configuration without constructing economic agents or modifying active saved slots. Export a minimal terrain context and select four stable land anchors. Store map provenance and anchors in the scenario/save.

First target is a static polygon terrain rendering with elevation, water, location labels, pan, and zoom. Reuse existing visual assets/helpers where they are sufficiently independent. Full 3D micropolygon rendering and map-editor controls are optional later presentation work. If existing camera helpers require economic objects, extract a small geometry-only helper; do not invent dummy nations, mutable bank accounts, or empty economies to satisfy a renderer.

Do not refactor the entire terrain stack. If the spike reveals expensive coupling, use an authored terrain fixture generated from the same terrain tooling, and document how it was produced. It must still provide actual terrain and geographic anchors rather than replacing the requested map with a force-directed graph.

### Mode behavior and baseline protection

The dedicated launcher selects `network_lab`; ordinary launchers retain existing behavior and do not import/init the network layer. Save mode is explicit and cannot be changed mid-session. A future integrated mode should return an explanatory unsupported-mode error in the laboratory until adapters exist. A display checkbox changes visibility only.

Use a network-owned random generator for setup, persist its state if consumed later, and avoid the global random stream. No importing the layer into the canonical turn loop for this release. A launcher link from the existing menu may be added last if it can start a clean session without sharing mutable globals.

## 11. Persistence, validation, and replay

Use versioned JSON with an atomic temporary-file/replace write. Save the complete canonical session, graph and revision, per-channel pressure, active source budgets/timers, pending deliveries, commitment state, promise timers, council challenge counters, project progress, content digest, action/event sequence, checkpoint cursor and any RNG state. Store saves in a laboratory-specific directory selected by the launcher, separate from terrain slots and existing checkpoints.

Validate IDs, references, ranges, unique council membership, capacity, phase boundaries, and mode on load. Reject incompatible schema/rules versions and mismatched scenario content with an actionable message; migration is deferred. Do not partially replace the current session on failed load. Save at decision boundaries only in this version.

Replay the accepted command journal from a version-matched initial setup; journal rival commands too and verify them against the engine. Compare canonical state digests after every round, excluding view state and wall-clock times. Loading/saving/inspection must not consume randomness, advance deadlines, or alter commitments. Cap the on-screen feed while keeping the complete run export for this short scenario.

### Minimal trace and causal explanations

Persist accepted actions/external inputs, structural/source changes, and consequential transitions, plus compact pressure/state checkpoints. Do not emit a narrative event for every edge update. At a threshold crossing, preserve before/after fields, opposing contributions, threshold/capacity constraints, strongest contributors plus exact remainder, and the checkpoint/graph revision needed to reconstruct all inputs. Cumulative explanations cover gradual build-up since the last decision; the last small push is not automatically the only cause.

Inflections include commitment/allegiance changes, contested-boundary entry/exit, bridge/source changes, majority shifts, task outcomes and office transfers. Use hysteresis to suppress trivial jitter. Connect office changes to ballots, ballots to allegiance shifts, and those shifts to pressure contributions and originating actions. Graph feedback loops become time-ordered causal history. Arithmetic attribution explains the executed path; claims that a cause was necessary require a labeled counterfactual replay. The [trace specification](people_network_graph_dynamics.md#4-minimal-causal-trace) defines records, reconciliation and compactness checks.

## 12. Verification and acceptance

### Automated behavior tests

- Directed and contextual trust affect conductance correctly; a refusal explains its actual pressure/margin/capacity constraint.
- A chain recruits at most one hop per round. Simultaneous updates are independent of person insertion order.
- Repeated invitations, overlapping memberships and multiple senders cannot multiply a person, ballot, or effort slot.
- A high-degree distrusted person underperforms a trusted local organizer in a declared fixture; a bridge changes reach across regions.
- Committed peers can tip an undecided contact, but do not inevitably recruit a strongly opposed one.
- Effort allocated to organizing cannot also complete work. Ineligible workers cannot fill required skill slots.
- Broken and fulfilled promises update the right trust context once; office-contingent deadlines activate once; an invalid command changes nothing.
- Leader unavailability leaves organizational membership/peer links intact and permits succession; a star loses reach when its center is absent.
- A challenge requires sustained support, provides a response round, counts unique ballots, observes cooldown and transfers office at most once.
- Displacement preserves player identity and connections, changes command permissions, and leaves a legal recovery path. Restoration retains obligations.
- Project change, deadline, completion, maintenance failure and office transfer have unambiguous ordering.
- Same setup and journal reproduce the same events and final digest; save/resume matches uninterrupted play.
- Invalid/corrupt saves do not replace a live session. Cross-mode saves are rejected.
- Advancing the laboratory never calls the canonical economic step or existing rebellion/regime updates. Normal launch behavior does not initialize network state or alter global random state.
- Opposing local sources produce contested high/high pressure distinct from weak low/low engagement; boundaries can advance or retreat after forcing/channel changes.
- Stable updates remain bounded, disconnected components cannot transmit across missing edges, and source-free fixtures decay under declared anchors.
- Semantic crossing decompositions and cumulative totals reconcile; checkpoint-based reconstruction matches optional full edge diagnostics. Tracing does not change state or require per-edge narrative events.

Use small rule fixtures and a few end-to-end authored traces. Do not assert that every seed must yield player victory or displacement. At least one legal trace must preserve office, one must recover it, one must fail to recover, and one must govern after restoration with a promise conflict.

### UI verification

Manually play both starts on the real desktop client. Inspect at a small supported window size and a larger size. Check text wrapping, map selection after zoom/pan, overlapping markers, focused relationship expansion, keyboard access to End Round/close inspector, colors plus labels, save/load errors, and the displacement transition. Capture screenshots of governing, recruitment explanation, opposition, and restoration. Do not rely on headless tests for readability.

### Playtest questions and gates

Run an initial formative pass with at least three testers, aiming at 15–25 minutes per run. These are proposed targets, not statistical proof. Record their decisions and explanations with consent; no external telemetry service is needed.

1. Can the tester explain a two-hop recruitment chain and one refusal without opening the raw graph?
2. Do they consider both recruiting new contacts and maintaining existing promises?
3. Can they find useful actions within two rounds of displacement?
4. Does restoration create an interesting governing problem from earlier obligations?
5. Do different coalition routes feel distinct, and can they identify why they would replay?

Gate integration on understandable causality and repeated consequential choices. Winning, a large cascade, or a visually attractive graph alone is insufficient. If every tester approaches the same hub, reduce its universal reach/context fit and improve alternatives. If players mostly wait, shorten delivery delays or improve active choices before adding systems. If restoration is impossible or automatic, revise council thresholds and coalition starting conditions before expanding scale.

### Diagnostics and performance

Export unique reach, invitations, acceptance/refusal reasons, propagation depth, opposing pressure/margins, contested boundary changes, source/decay balance, duplicate suppression, work contribution, promise fulfillment, council allegiance changes, office changes, actions used, trace bytes and time per engine/UI operation. Keep centrality metrics diagnostic only. Store only the minimal authoritative records by default; enable full edge dumps and rival candidate evaluations explicitly for debugging.

At 32 people, target engine resolution below 50 ms per round on the development machine, excluding terrain generation and rendering. Profile a synthetic 200-person sparse graph to expose accidental all-pairs work; do not increase the release population because that benchmark passes. Record hardware, scenario digest, and version with measurements. After terrain initialization, drawing should remain responsive while inspecting relationships; only optimize observed stalls.

## 13. Delivery sequence and reviewable milestones

| Milestone | Deliverable | Exit gate |
|---|---|---|
| 1. Contracts and fixture | Model/schema, scenario data, command/event vocabulary, exact round rules | Data validates; both starts inspectable headlessly; no economic dependencies |
| 2. Social loop | Sparse graph, stable pressure dynamics, competing sources, capacities, promises, organizations, compact trace | Cascade/stall/competing-front/stability/context/duplicate/persistence-of-group fixtures pass; explanations reconcile |
| 3. Political loop | Project, appointments, rival, council challenge and role transitions | Headless hold-office and displacement/recovery traces; governing after restoration |
| 4. Persistence and isolation | Save/load, journal replay, state digests, baseline checks | Interrupted and uninterrupted runs match; forbidden simulation calls absent |
| 5. Terrain interface | Terrain spike, map overlay, focused relationships, actions and explanations | Both starts playable visually; selection and causal paths readable |
| 6. Playtest and tune | Tester sessions, bounded parameter revisions, results report, instructions | Causality and choice gates assessed; defects fixed or explicitly recorded |

The terrain dependency spike may run during milestone 1 to retire risk early; building the full interface waits until a headless political loop works. Each milestone should be a small reviewable change, with tests relevant to its rules. Do not merge unrelated ongoing engineering/technology work into this feature.

After milestone 6, write `planning/reports/people_network_coalition_mechanics.md` with scenario/rules digests, reproduced runs, tester findings, balance changes and a recommendation: iterate, expand standalone play, or attempt one integration experiment. Update the README and scenario guide to distinguish working features from remaining proposals.

## 14. Risks and explicit responses

| Risk | Response in this slice |
|---|---|
| Highest-degree contact solves everything | Contextual trust, limited attention, role diversity, alternative bridges |
| Network becomes a static influence bar | Actual invitation paths, commitment review, tasks, rivals and obligations |
| Groups are permanent voting blocs | Individual decisions, overlapping membership, conditional cooperation |
| Society collapses whenever a leader leaves | Persistent peer links, coordinator succession and contrasting topology fixtures |
| Opposition is a waiting room | Same organizing actions, rival vulnerability, visible route to a council challenge |
| Council feels like the whole nation | Explicit test abstraction; no claim to model all regimes yet |
| Promises become unlimited free persuasion | Exact fulfillable terms, exclusive posts, conflict checks and breach consequences |
| Terrain reuse drags in the full simulation | Geometry-only adapter, fixed fixture fallback, forbidden-call tests |
| Too many hidden variables obscure decisions | Full-information first release, component explanations, few trust contexts |
| Prototype becomes a parallel economy | Abstract effort only, no cash/goods or real agent mutations |
| Physics metaphor creates unstable or unexplained pressure | First-order bounded update, validated step size/budgets, hysteresis, decomposed sources and decay |
| Trace volume obscures causes | Semantic inflections plus compact checkpoints; reconstruct edge detail on demand |

## 15. First integration experiment, after approval based on playtests

Keep integrated mode unavailable in the first release. If the laboratory works, select one read-only material input, such as a local grievance from an existing scenario, and one mediated output, such as cooperation with a project. Specify ownership of authority and collective action before enabling output effects. Replace laboratory abstractions rather than adding a second cash ledger, population, government or takeover engine.

Before integrating, separately resolve population representation, relationship initialization for existing agents, interaction with rebellion/regime rules, time-scale mapping, save compatibility, and disabled-mode equivalence. Death/succession, richer forms of removal, fog of war, additional clients and national scale require subsequent plans. The first implementation succeeds by proving that organizing and governing through relationships is worth playing.
