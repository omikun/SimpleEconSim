# Network Laboratory: The Broken Crossing

For contracts, hiring patrons, private toll bargains and audits, use the separate [Patronage guide and winning routes](people_network_patronage.md): `venv/bin/python -m client.desktop.network_lab --ruleset patronage`. This page describes the classic coalition ruleset.

Rules version 2: the isolated implementation of the [people-network manifesto](gdd.md#manifesto-a-nation-is-a-network-of-people). Run it from the repository root:

```bash
venv/bin/python -m client.desktop.network_lab
venv/bin/python -m client.desktop.network_lab --start displaced --seed 4243
```

This opens a separate Pygame client. It reads exported terrain geometry and an authored society of 32 people; it does not construct or advance the economy. The ordinary game launchers retain their existing behavior. Switch between the two laboratory starts with **Other start**, or restart the same seed with **Restart**. There is no live conversion of an existing campaign into laboratory mode.

## Your job

**Keep enough people behind you to govern, and get the broken bridge repaired.** Farmers want the repairs to help them reach their fields first. Traders want market access first. You need cooperation from both groups, while your rival Sen is trying to win your councillors away from you.

Start with **Start**, the overview that opens automatically. **Groups** shows what people want and what you have promised. You do not need to inspect all 32 people. It tells you how many of the nine council votes you hold, explains the bridge decision, and suggests useful people with direct action buttons. Numbered markers on the map match those suggestions. They now compare the consequences of a move with waiting, rather than simply picking the least opposed or most connected person.

| Action | What you are asking |
|---|---|
| **Ask for support** | “Will you back me?” Talk to this one person. The request arrives next round and may fail. |
| **Ask to rally** | “Will you recruit people you know?” An ally spends time spreading your chosen goal; they cannot also repair the bridge while doing this. |
| **Stop rallying** | Free that person's time so they can work again. |
| **Give one share** | Move a recurring public service share from the selected donor group to this group. |
| **Agree to conditions** | Promise a group its listed terms; members consider your program, then judge delivery. |
| **Help farmers first / Help traders first** | Choose the repair plan as the current government. |

Use the goal selector to ask for political support or rally people for one of the repair plans. A person can back Sen politically and still help repair the bridge. You have two political actions each round; **End round** or Space lets people respond, speak to their contacts, work and reconsider their commitments.

Holding five council supporters for two completed rounds lets an opposition leader request a vote. The vote happens the following round, allowing a response. Five actual votes transfer office. If you lose office, you keep playing as the same person: rebuild a coalition and try to return. Your promises survive the change.

Clicking a person opens optional detail, and Tab cycles everyone. **Introduce selected to…** connects two existing contacts who both support you. It creates one low-trust channel, not instant cooperation. Escape cancels the introduction.

## Groups, budgets and conditional backing

The council now includes people from all four communities. A coalition cannot be built solely by concentrating on councillors in the capital.

| Group | What it wants |
|---|---|
| Cultivators | Two service-budget shares; prefers field access first. |
| Traders | Two shares; prefers market access first. |
| Craft mutual-aid society | One share and no more than two members rallying for the same leader at once. |
| Civic service association | One share and a liaison from its membership. |

You have **four recurring service-budget shares**, while these minimum funding requests total six. In **Groups**, choose a donor with the top button, then **Give one share** to a different group. This uses one political action and conserves the total of four. The allocation persists each round and across office changes. These are an explicit laboratory service-budget abstraction, not cash from the full economic game.

An agreement makes the listed funding, representation or workload conditions binding for that candidate's relationship with the group. It can make a credible program more attractive; it does not instantly pledge everyone's votes. Broken agreements and promises lower credibility, and promising more shares than exist weakens belief in the offer.

A new agreement gives an incumbent two governing rounds to begin delivery. An opposition leader's clock waits until they take office. **Two consecutive delivered rounds honor the agreement; delivery must then continue.** Breach can make individual members withhold support even when personal influence remains high. Restoring delivery takes two rounds again. Existing agreements cannot be erased by signing the same offer again.

Losing office suspends obligations you cannot enforce, but retains your delivery record, breach history and elapsed governing time. Returning does not provide another fresh grace period. The new ruler inherits the public allocation and must decide how to change it. Honoring an agreement remains compatible with members individually preferring another candidate.

Actual service delivery and representation alter group opinions, which feed each person's interests and travel through relationships. Overlapping memberships can create competing obligations. Past governing records fade slowly in opposition. The **Groups** panel compares your record with Sen's; map cards show current funding against requests.

## Keeping people organized costs time

Volunteers—including the player and Sen—can rally for **three active rounds**, then automatically step back for **two rounds away from campaigning**. This cost exists even when the bridge has no work underway. Weariness weakens their reinforcement before the break. Releasing someone early lets them recover; at high strain they cannot immediately be assigned again. A break from rallying does not prevent ordinary repair work or governing decisions.

Green rings mark rallying people; gold outer rings warn that a break is approaching. Hover or inspect a person to see their strain. Craft members also judge how many of their peers you keep away from ordinary work. Durable relationships and organizations remain when an organizer steps back, so planning relief is part of coalition maintenance.

## Governing and obligations

The incumbent can adopt a repair package and appoint up to two supporting liaisons. Liaisons can reach an extra contact while sharing the same total organizing budget. A liaison appointment or a choice of repair package can be promised to a contact. Incompatible package promises and overbooked posts are rejected. Office-contingent promises become due two rounds after gaining office. Honor or breach changes the beneficiary's trust in the promisor. Use **Promises** to inspect and renounce pending obligations.

Repair requires six work contributions and four hauling contributions from at least two locations in each of three consecutive rounds. Everyone counts once, regardless of overlapping memberships. Task pressure and an available effort slot are needed; newly committed people start work next round. Political opponents can cooperate on the crossing. Organizers cannot also supply work. The player can use **Work personally** when not organizing.

A missed work round resets the consecutive streak. A package change also resets it. A missed deadline is recorded, damages trust in the incumbent, and does not forbid later completion. Completion changes trust and leads to maintenance: two contributors per round after a two-round grace period. Two consecutive shortfalls create a service failure. The prototype uses abstract effort, not cash, goods or the existing construction system.

## Read the map without opening every person

- **Terrain** puts people on the actual river catchment. Flow arrows follow the river from mountain springs to the sea. Upstream Village is on inland high ground; Market Landing is at the coastal mouth. The bridge spans an actual river segment.
- **Network** is a large, stable relationship diagram with every person named, grouped by community. Its spacing is schematic; it does not pretend to be geography.
- Bigger markers mean more trusted outgoing reach. Thicker arrows mean stronger directional relationships: trust multiplied by communication capacity in the selected political or repair context. A diamond means that person holds a council vote. A green ring means they are already rallying contacts.
- Blue means they back you, coral means they back Sen, and gold means they have not committed. Community cards summarize support and show whether the group prefers fields or market access first.
- Numbered markers correspond to **Overview** suggestions: ask for support, rally allies, or release someone to work. The advisor checks whether the move preserves votes or improves repair cooperation after allowing the network to evolve; it does not simply count contacts.
- **All links** reveals the complete diagram; **Useful links** emphasizes the selected person and suggested intermediaries. Hovering reveals reach and council status without selecting anyone.
- **Council** lists all nine votes, whether the preferences are close, the officeholder and challenge timing.
- **Why?** shows pressure accumulation, signed incoming contributions, appeals, interests, decay, opposing resistance and saturation. The strongest incoming contacts appear by name.
- **History** buttons and left/right arrows inspect recorded rounds; **Live** returns to current decisions. Inspection cannot advance the simulation. Actions are disabled while viewing history.
- **Causes** expands the latest relevant semantic event into its causal parents. **Export** writes complete checkpoints, accepted actions, structural changes, transitions and their IDs to a `.trace.json` file beside the save.

### What the suggestions mean

For each legal request, rallying assignment or release, the advisor runs a separate copy of the real game for five rounds. It compares that branch with waiting, keeping already accepted actions in both branches and letting Sen follow the current rival policy. It evaluates council majorities, support sustained across the final rounds, time in office, actual repair staffing and progress, missed deadlines and existing promises. Someone with many contacts can be a poor choice if they cannot reach useful people or if rallying removes a needed worker.

Each card states its estimated result and cost. These are alternatives, not additive promises of success: after you choose one, the other suggestions are recalculated. Forecasts assume you take no additional actions during the five rounds. Making further moves changes the outcome. The advisor does not compare every possible sequence, repair policy, concession or long-term alliance; it is not an optimal strategy guide. Historical inspection shows actual history rather than speculative advice.

The advisor also considers public allocations, group agreements and volunteer breaks through the same five-round engine. It still does not plan every future sequence; an agreement may require follow-up moves beyond the one being compared. The terms are authored group demands, not a free-form negotiation system.

The trace records significant changes rather than one narrative event per edge/channel update. Full local contributions can be reconstructed from checkpoints using `people_network.events.explain`. Contributions explain the executed path; the application makes no automatic claim that one intervention was a necessary cause.

Use Space or N to end a round; right-drag pans and the wheel zooms. F1 opens the briefing. Escape closes the briefing, cancels an introduction, or leaves history. The minimum window is 1100×800.

## Saves and headless verification

Save/load defaults to `outputs/people_network/laboratory.json`; `--save-path` changes it. Saves include pending decisions, pressures, group records, agreements, budget allocations, volunteer strain, graph/source state, timers and the action journal. Version-1 saves are rejected explicitly; start a fresh run for the coalition rules. They validate content/rules and terrain digests. A failed load leaves the current session intact. Existing game saves and terrain slots are separate. Exported JSON is intended for local analysis; saves are not signed or authenticated.

```bash
venv/bin/python -m people_network.cli --start displaced --autoplay --rounds 24
venv/bin/python -m people_network.cli --rounds 32 \
  --commands scenarios/people_network/playthroughs/govern_restore.json
venv/bin/python -m scripts.playtest_people_network
venv/bin/python -m unittest tests.test_people_network tests.test_people_network_map tests.test_people_network_advice tests.test_people_network_coalitions tests.test_people_network_ui -v
```

The checked 32-round version-2 fixture uses legal player commands with an active rival: displacement in round 11, restoration in round 23, renewed governing obligations, and another loss of office in round 30. The last change is a real outcome of the new rules, not a scripted transition. Separate acceptance paths show that retaining office, restoring office and failing to restore are all possible. CLI runs replay their journals and check state digests. The acceptance runner writes local summaries and full traces under `outputs/people_network/`.

The corrected catchment uses 350 terrain cells and verified downhill drainage. Saves from the original terrain require a fresh run because the authored geography and terrain digests changed.

The static terrain fixture was exported by `venv/bin/python -m scripts.build_people_network_terrain` from the game's polygon map generator. Regenerating it changes terrain provenance and invalidates old laboratory saves; it does not write map-editor slots.

## Current limits

This is a small full-information laboratory with a simple council and public rival heuristic. It has no death/succession, military removal, hidden intelligence, full economic integration or browser client. Organization succession on a person's unavailability exists as a journaled scenario/debug input, not as a normal player coercion action. Affiliation and geography are authored; the seed supplies a small initial pressure perturbation. After round 24, play can continue.

Automated checks establish reproducibility and the existence of different political paths. Enjoyment, balance across players, and usability with actual human testers remain to be evaluated before integrating this layer with the wider game. See the [verification report](../planning/reports/people_network_coalition_mechanics.md).
