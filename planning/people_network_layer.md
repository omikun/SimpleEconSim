# People network layer: design discussion and isolated playtest

Date: October 27, 2026.
Status: original design discussion retained below. The first standalone laboratory has since been implemented; see the [guide](../docs/people_network_lab.md) and [verification report](reports/people_network_first_playtest.md). Wider integration remains deferred.

The [first implementation plan](people_network_first_implementation_plan.md) expands this discussion into a proposed scenario, rule set, architecture, delivery sequence, and playtest gates. Its initial scope choices are proposed defaults, not implemented capabilities.

The October 28 [graph dynamics and minimal causal trace specification](people_network_graph_dynamics.md) refines the simulation direction: use a directed weighted graph with local pressure propagation, competing influence fields and persistent communities. Invitations introduce pressure; the network continues evolving between actions. Trace a small set of interventions and consequential transitions, with checkpoints for reconstructing the accumulation and causes of inflection points.

## Agreed direction

The [game manifesto](../docs/gdd.md#manifesto-a-nation-is-a-network-of-people) establishes that national capacity depends on relationships among people. Influence travels through those relationships to mobilize concrete tasks and goals. Durable subnetworks sustain collective action, and connections between groups shape coalitions and government behavior.

The player can govern while in office and continue after being overthrown, building a movement to regain power. The player retains their political identity across that transition. The network should be tested for enjoyment before being integrated with the wider simulation. A separately enabled layer and an isolated terrain-map playtest are the proposed means, not existing capabilities.

## Smallest useful experiment

Use a small terrain scenario with a handful of locations, a few dozen named people, and three or four overlapping communities. These are tentative scope limits. Every simulated person should have a readable role, interests, relationships, and reasons to cooperate or refuse. Avoid requiring the full economic population in the first experiment. Prototype characters are not claimed to be a complete representation of the existing population.

Begin the player in office with a fragile coalition and a concrete task, such as obtaining cooperation for a public project. A rival recruits from the same society. The player makes limited choices each turn: approach an organizer, negotiate a commitment, support a community, or ask an ally to mobilize contacts. An organizer's agreement creates an attempt to recruit others, rather than instantly delivering everyone connected to them.

Show the chain: who asked whom, what each person committed to, who declined, and why. Distinguish sympathy from willingness to act. Delivering an agreed task should have a visible consequence; broken commitments should affect future cooperation. A simple fixed effort budget can constrain the prototype without importing production, finance, or household subsistence. Label it as a prototype abstraction.

Run a companion setup starting just after displacement so recovery can be tested without requiring every tester to lose first. Both setups should use the same people and relationship rules. Regaining office must then require governing with the coalition assembled to return, including its competing obligations.

The first loop should test at least one persistent organization that survives a leader's removal and one bridge between groups whose loss changes coalition options. Rivals must act and react under comparable constraints; a passive population would not establish that coalition play works.

## One network, geographic locations, focused views

A separate graph for every region is unnecessary. Model one sparse relationship network whose people have geographic locations and overlapping group memberships. Relationships can cross regional boundaries. Geography shapes access, travel, and contact where useful; graph layout does not need to reproduce terrain coordinates.

Use the terrain map as the default view. Mark important people and organizations in their locations, and summarize local mobilization and commitments. Selecting someone opens a compact relationship view with their immediate contacts and relevant bridges. Selecting a goal highlights only the active recruitment paths and affected locations. Show a few consequential intermediaries before exposing individual followers through inspection.

These are different views of the same state. Do not maintain an independent social graph per region or ask the player to manage every edge. A full network view can be a development inspector if useful, but need not be the primary game screen. Group summaries must distinguish overlapping membership from unique participating people to avoid double counting.

## Proposed development modes

Separate whether the rules run from whether the network overlay is visible. Hiding a map layer must not disable its simulation.

| Proposed mode | Network rules | Wider simulation | Purpose |
|---|---|---|---|
| Existing game | Disabled | Existing behavior | Preserve a baseline for comparison |
| Network laboratory | Enabled | Disabled; explicit fixed or scripted scenario inputs | Find and tune the social play loop |
| Integrated experiment, later | Enabled | Enabled through defined connections | Test interactions after the laboratory works |

Prefer choosing the mode at scenario creation and recording it in saves. Do not promise a live mid-run toggle: initializing relationships in an old world or removing a network during a campaign needs explicit migration and continuity rules. A development restart with the same seed is sufficient for the first comparison.

The laboratory must actually skip unrelated simulation updates. Merely hiding economy panels or freezing displayed values would leave the experiment hard to interpret. Reuse terrain and presentation components where practical, without assuming the existing world loop can already run this mode.

## Conceptual boundary for a future implementation

Keep relationship, organization, commitment, mobilization, and coalition state together behind a clear layer boundary. Give people stable identifiers so later integration can associate network participants with existing agents. Use a small explicit set of inputs such as grievances, locations, institutional roles, and available resources; produce recruitment attempts, commitments, cooperation, and coalition changes with causal explanations.

In the laboratory, scenario data supplies those inputs. Later adapters could read economic conditions and apply authorized effects to the existing game. Avoid a second source of truth for cash, population, officeholders, or military control. Any later resource transfers must use the existing conservation rules. Define which system owns overlapping rebellion and political outcomes before integrating; running two independent takeover calculations would be ambiguous.

Disabled mode should not generate relationships, consume additional random draws, or apply network effects. This is a future acceptance requirement, not a verified property. Seeded runs, recorded mode settings, and concise recruitment explanations should make playtest outcomes reproducible.

## Evidence needed before integration

- A tester can explain why an influential person's appeal spread in one group and failed in another.
- Recruiting a bridge, organizing locally, and maintaining an existing coalition produce meaningfully different choices; recruiting the most connected person is not always best.
- An organization can survive the loss of its central figure without becoming indestructible.
- An overthrown player has understandable actions and a plausible, uncertain path back to office.
- Governing after restoration presents consequences from promises made while organizing.
- Terrain and focused relationship views communicate the situation without requiring a full graph for every region.
- Repeated short playtests reveal decisions players want to revisit, rather than passive waiting for influence numbers to rise.

These are proposed qualitative gates. No schedule or balance thresholds are fixed yet. Only after the loop works should an integrated experiment connect one material pressure and one institutional consequence at a time.

## Questions still open

- Does the player persist as one individual, a household or lineage, or a movement after death? Displacement continuity is agreed; succession is not.
- Which first task best exposes competing commitments: a public project, a strike, an election, or another local contest?
- How much information should normal play reveal about trust and recruitment, compared with the development inspector?
- Which relationship distinctions are necessary for fun? Start with very few; contextual trust, obligation, and organizational membership are candidates, not a committed schema.
- What determines loss and recovery of office in the laboratory, and how can both happen without letting one connected person decide every outcome?
- What minimum connection to geography creates meaningful choices without adding travel micromanagement?

The next step is to discuss this experiment and its core task. Runtime work remains outside this documentation change.
