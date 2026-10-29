# Graph dynamics and minimal causal trace

Date: October 28, 2026.
Status: technical specification for the [first implementation](people_network_first_implementation_plan.md). The standalone laboratory is implemented; see the [guide](../docs/people_network_lab.md) and [verification report](reports/people_network_coalition_mechanics.md) for delivered behavior and limits.

The requested model is a graph simulation with local influence propagation, competing pressures, persistent communities, and explainable inflection points. Explicit invitations remain player actions; they are not the sole mechanism by which influence spreads. This specification replaces the earlier invitation-only scoring proposal.

## 1. Graph as authoritative data

Use one directed, weighted, sparse graph spanning all locations:

- Nodes are people, with stable IDs, location, interests, commitments, and dynamic pressure state.
- Directed edges are channels through which a person's expressed position can influence another. An edge `j → i` stores how receptive recipient `i` is to sender `j`, by context, plus communication capacity and availability.
- Organizations are persistent membership sets with authored peer edges and a coordinator. Membership supplies context and continuity; it does not implicitly create a clique or a single aggregate voting node.
- Terrain adjacency is a separate geographic graph. It constrains contact availability where configured; political influence follows social edges, including long-distance ones.

Store node/edge dictionaries and incoming/outgoing adjacency indexes. A membership index supports organization queries. Keep each edge stored once; indexes reference its ID. No NetworkX or graph database is required for the first scale. A graph library can later supply offline diagnostics without owning simulation state.

Use graph operations directly: iterate incoming edges for pressure updates, traverse reachable contacts for previews, find paths to explain recruitment, detect disconnected components after structural changes, and inspect cut/bridge edges between communities. Directed reachability matters; a weakly connected graph need not allow influence in both directions. Local edge creation, removal, availability, and weight changes alter future propagation. Centrality and community detection are diagnostics, not mandatory per-round calculations or persuasion multipliers.

An introduction adds a low-trust channel only after agreement. Fulfilling/breaking a promise changes declared trust weights. A temporary disruption can close a channel without deleting its history. Arbitrary edge editing remains a developer tool. Any derived boundary/component cache is invalidated by relevant node/edge changes; it is never a second authority over allegiance.

## 2. Physics-inspired, with a specific meaning for pressure

Treat a political pressure as a **bounded disposition toward a candidate or goal**, not as physical energy. Local sources push it, relationships transmit it, resistance attenuates it, and continued organization can sustain it. Opposing candidates compete for relative support; costly tasks compete for effort. Material interests can resist or reinforce incoming pressure.

Use first-order damped dynamics initially. Do not add physical positions, collision forces, inertia/velocity, or oscillatory springs just to make the metaphor literal. Graph-drawing forces are presentation only and never determine political outcomes. Social influence has sources, opposing resistance and decay; do not impose money-style conservation on it.

### Channels and node state

For each person `i` and active channel `k`, maintain a pressure `x[i,k]` in `[0,1]`. Channels initially cover the player candidacy, rival candidacy, and a small bounded set of public task/package goals. Keep candidate pressure separate from project pressure: a rival supporter may cooperate with a useful repair.

A person can have high player and rival pressure simultaneously, representing competing attractions. Record both values and the difference. Low/low means weak engagement; high/high means strong competing pulls. Collapsing both into a single signed value would erase that distinction.

Store issue alignment `b[i,k]`, decay, response rate, entry/exit thresholds, and current expressed commitments separately. Continuous pressure is not a ballot, promise, or delivered work. Discrete decisions read the fields and actual constraints.

### Minimal stable update

For edge `j → i`, compute effective conductance:

`c[j,i,k] = trust[i←j,context(k)] * channel_capacity[j→i] * availability[j→i]`

All factors are bounded and nonnegative. Negative trust blocks or weakens a channel; this version does not silently turn distrust into support for an opposite cause.

Let `B[i]` be the person's declared receiving budget, shared across all active channels. With all coefficients taken from the frozen round snapshot:

`d[i] = max(1, sum(c[j,i,k] for incoming j and active k) / B[i])`

`w[j,i,k] = c[j,i,k] / d[i]`

Then sum directed edge pressure contributions:

`F[j→i,k] = w[j,i,k] * (x[j,k] - x[i,k])`

and advance synchronously:

`opposition[i,k] = competition * x[i,k] * x[i,opponent(k)]` for the two candidate channels; zero for public tasks.

`raw[i,k] = x[i,k] + h * (sum(F[j→i,k]) + s[i,k] + a[i,k]*(b[i,k] - x[i,k]) - decay[i,k]*x[i,k] - opposition[i,k])`

`x_next[i,k] = clamp(raw[i,k], 0, 1)`

Here `s` is a bounded direct source from an action, delivered appeal, or ongoing organizer; `a*(b-x)` anchors response to material interests; `decay*x` represents fading pressure without reinforcement. The signed edge term is a contribution to the recipient's disposition. It is not an equal-and-opposite conserved flow subtracted from the sender on a directed graph. Label it “transmitted pressure” in the UI rather than asserting physical conservation.

Validate `B > 0`, `h > 0`, and `h*(sum_j w[j,i,k] + a[i,k] + decay[i,k] + competition) <= 1` for every node/channel. Require `sum_k abs(s[i,k]) <= source_budget[i]`, and cap organizer output across recipients too. Define clamp correction as `x_next - raw` in the trace, so contributions reconcile exactly even at bounds. The conservative stability bound includes the maximum opposing field. Candidate opposition prevents sustained competing sources from merely saturating both independent fields at one; the two values remain separately inspectable. Source budgets and normalization prevent duplicate appeals, extra memberships, and arbitrary channel creation from providing unlimited force.

Initially use one synchronous propagation step per decision round. Sources introduced at a node can affect its contacts on the next update; there is no recursive within-round flood. When source and propagation phases are displayed, label that one-hop delay consistently. A round with no player action still evolves under existing fields, sources, decay, and rival behavior.

A constant input should settle or approach a stable state under these first-order rules. Numerical flicker is not political turbulence. Validate boundedness and decay/equilibrium fixtures before tuning cascades. Initial automated playtests added the bounded mutual opposition term after independent fields could saturate together and stall boundary movement. This equation is a starting model to test, not a scientific claim or a promise of fun.

### Sources, attention, and commitment feedback

An approach sends a one-round delayed appeal to an existing contact. Delivery applies a bounded local source, with magnitude based on contextual trust and relevance. Multiple appeals share the receiver's source budget and are allocated proportionally with stable rounding, never by incidental iteration order.

Organizing uses the organizer's effort slot to sustain an expressed channel and send up to two targeted appeals per round. A liaison can send one additional appeal, but keeps the same total output budget; the post adds reach, not free unlimited pressure. An organized commitment may supply a small ongoing self-source while effort is allocated to organizing. Merely sympathizing supplies no extra source beyond the node's existing pressure. All source rules are declared, bounded, and explainable.

Ordinary conversation is represented by continuous edge coupling whether or not a formal invitation was sent. Avoid applying an invitation score, an independent committed-peer bonus, and graph diffusion for the same peer effect. There is one authoritative pressure update. Sources and commitment feedback enter that update explicitly. Keep the number of active channels bounded and reject duplicate equivalent goals at scenario validation/action validation.

## 3. Opposing forces and spheres of influence

For candidates A and B, define the local margin `m[i] = x[i,A] - x[i,B]`. A new public allegiance requires a minimum absolute candidate pressure and margin above an entry threshold. Switching candidates requires the opposite margin threshold plus a minimum review/dwell period. Withdrawal can occur before joining the other side; high conflict can leave a person undecided. Exact thresholds are tuning data.

Sphere membership is derived from current margins and declared commitments. An influence boundary is a social edge joining nodes with different dominant candidates, or a node whose margin is within a configurable contested band while both pressures are substantial. Distinguish a dormant neutral from a contested person. No hard territorial ownership changes merely because a margin changes sign.

Boundary inspection shows both opposing channels, their strongest upstream sources, local resistance and net trend. Blocking a bridge can halt propagation; another route may bypass it. Recruiting a trusted intermediary can shift a boundary outward over several rounds. A broken promise can weaken a local source or channel and let a rival advance through existing paths. Boundaries are graph cuts, not necessarily continuous lines across terrain; scattered organizations can exert influence in distant places.

Task commitments require enough goal pressure, affordable cost, eligibility, and an available effort slot. Competing task goals use a declared capacity allocation rule; candidate allegiance does not consume work effort. Use pressure thresholds with hysteresis and capacity review to give organizations staying power. Group persistence comes from durable contacts, aligned interests, effort-backed reinforcement and commitments, rather than an automatic loyalty aura. Test removal of a central figure in both star and redundant community topologies.

## 4. Minimal causal trace

The trace must explain both gradual accumulation and discrete transitions. It should not log a separate narrative event for every edge/channel update. Use three authoritative record families and a compact checkpoint stream:

| Record family | Persisted content | Why it is needed |
|---|---|---|
| `Action` | Accepted player/rival command, parameters, budgets, round, stable ID; declared external input | Reproduce deliberate interventions and scenario pressures |
| `StructuralChange` | Before/after trust or edge availability, introductions, source start/stop, promise/organization/goal changes; parent action/outcome IDs | Explain changes in graph topology, coupling and ongoing forcing |
| `Transition` | Commitment/allegiance/withdrawal, goal success/failure, promise result, council vote/office change; before/after, thresholds and causal parents | Identify consequential changes and inflection points |
| `RoundCheckpoint` | Compact pressure arrays, commitments, active sources, boundary summary, state digest and replay cursor | Recover evolving continuous state and reconstruct detailed contributions on demand |

Store a full initial state and versioned rules/scenario digest. For this 32-person laboratory, full pressure arrays per round are inexpensive; keep them, rather than making rounded deltas or a top-N cause list the only evidence. Journal scripted inputs and any sampled values if randomness is later introduced. Discrete records can be exported as JSONL; checkpoints can be packed arrays. Avoid general financial trace integration until the laboratory's schema is proven.

Each semantic event stores its local decomposition: previous value, signed incoming total per channel, local source, interest anchoring, decay, opposing resistance, clamp correction, resulting value, competing-channel margin, and the exact decision threshold/capacity constraint. Keep the strongest few incoming contributors inline for readability, plus the exact signed remainder and a pointer to the round snapshot/graph revision. Reconstruct all edge contributions from those snapshots and versioned coefficients when requested. Never discard losing-side pressure just because the final transition favored the player.

Every change record has its own before/after values; multiple changes to the same edge in one round remain distinguishable and replayable. Resolve propagation using the effective graph revision frozen for that phase, then apply later changes to next-round coefficients. Save both pre/post-phase checkpoints when an intermediate state cannot be reconstructed from the preceding checkpoint plus ordered changes. Do not use a final-round graph to explain an earlier propagation step.

### Inflection points and attribution

Emit semantic transitions for entry/exit threshold crossings, changes in allegiance, meaningful boundary moves, source exhaustion, bridge closure/opening, coalition majority gained/lost, project success/failure, and office transfer. A boundary entering the contested band is meaningful; small jitter within the band is not a new event. Use entry/exit bands to avoid trace floods. Group related changes into a round summary while retaining individual IDs.

For a node that crosses a threshold after several rounds, offer a local explanation of the crossing round and a cumulative view since its last allegiance/commitment decision (or run start). Store the interval's start/end values and reconstruct the signed contribution totals across that interval. This avoids attributing a slow accumulation entirely to the final small push. Distinguish “largest contribution” from “decisive”: arithmetic attribution describes the executed path, not proof that removing a source would have prevented the outcome.

An inflection is a named game transition or configured diagnostic, not every mathematical second-derivative sign change. Office transfer points to individual ballots; ballots point to allegiance changes; changes point to contributing fields/edges, source changes and originating actions. Recurrent reinforcement creates loops in the social graph, but causal links advance in phase/time and form an acyclic history. Expand history only as far as requested.

Present a short chain such as:

`promise broken → organizer trust/channel weakens → rival pressure overtakes local support → councillor withdraws → council majority lost → office changes`

Every link must be backed by actual records. Do not manufacture a single root cause if several accumulated effects mattered. Numerical illustration only: a candidate margin can move from `+0.08` to `-0.14` with net edge contributions `-0.16`, local source changes `-0.04` and anchor/decay effects `-0.02`; crossing a configured `-0.12` switch threshold then produces a transition. The real trace must also show both absolute pressure values, eligibility and review constraints. These numbers are not measured game results.

For claims such as “this bridge was pivotal,” run an explicit replay branch with that change removed, preserving other accepted commands and declaring any commands made invalid by the branch. Label this a fixed-command counterfactual; it does not model how the player or rival might have chosen differently. Do not run expensive counterfactuals automatically for every ordinary explanation.

## 5. Verification additions

- Two-hop chain: a pulse cannot affect a second-hop node in the same propagation update.
- Disconnect a component: no edge pressure crosses the cut, regardless of terrain proximity.
- Unequal directional trust: A influencing B need not imply equal reverse influence.
- Two opposing sources: expose high/high contest separately from low/low neutrality; stronger forcing can move a boundary gradually.
- Remove a source: pressure decays or settles under the declared remaining sources and anchors; it does not disappear globally in one round.
- Strongly connected community: reinforcement can outlast an individual organizer under bounded rules; a star has different resilience.
- Stability: pressures remain finite/bounded; normalization, source saturation and clamp corrections reconcile. A passive source-free zero-anchor fixture decays without spontaneous recruitment.
- Shared budgets: duplicate channels, repeated appeals and duplicated membership do not increase capacity.
- Hysteresis: small margin fluctuations cannot cause repeated allegiance flips or boundary-event spam.
- Insertion-order permutation leaves pressure results and causal summaries unchanged within the documented numerical tolerance; event ordering uses stable IDs.
- Every crossing explanation reconciles old value plus contributions to new value, and cumulative interval totals reconcile too. The losing channel is inspectable.
- Reconstructing a requested edge breakdown from a checkpoint matches full diagnostic mode; source/graph revisions and phase ordering match replay.
- Traced/untraced runs produce identical authoritative state. Compact-trace size grows with checkpoints and consequential changes, not mandatory per-edge narrative events.

Measure step time and trace bytes per round with the plan's 32-person scenario and a sparse 200-person stress fixture. The pressure step is `O(K*(V+E))` for bounded channels, plus changed-state bookkeeping. Keep full edge diagnostics optional. Numerical model changes require a rules-version bump and revised replay fixtures.
