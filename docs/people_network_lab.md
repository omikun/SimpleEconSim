# Network Laboratory: The Broken Crossing

The first isolated implementation of the [people-network manifesto](gdd.md#manifesto-a-nation-is-a-network-of-people). Run it from the repository root:

```bash
venv/bin/python -m client.desktop.network_lab
venv/bin/python -m client.desktop.network_lab --start displaced --seed 4243
```

This opens a separate Pygame client. It reads exported terrain geometry and an authored society of 32 people; it does not construct or advance the economy. The ordinary game launchers retain their existing behavior. Switch between the two laboratory starts with **Other start**, or restart the same seed with **Restart**. There is no live conversion of an existing campaign into laboratory mode.

## What to do

You begin in office with five of nine councillors, or in opposition after an authored displacement with four supporters. You have two political actions per round. Select people on the map, in the contact diagram, or from the council list. Tab cycles every person.

Choose a goal: your candidacy, Sen's candidacy, upstream repair, or market repair. **Appeal** sends a delayed message along an existing contact. **Organize** reserves your or a supporting person's effort to sustain that goal and contact others. It becomes active the next round. **Release effort** lets that person work again. Ordinary pressure also travels through existing relationships without new messages.

A high degree of connectivity does not guarantee influence. Relationships have directional trust in governing and organizing. People have their own issue interests, and attention/output budgets limit transmission. Separate pressure fields retain attraction to both candidates. Opposing pressure resists growth; a contested person can withdraw before joining another coalition. Commitments have review delays and entry/exit thresholds to prevent constant flipping.

**Introduce selected to…** connects two existing contacts who both support you; select the second person to complete the introduction. This creates one directed low-trust channel. It does not grant instant cooperation. Cancel with Escape.

Holding five council commitments for two completed rounds permits **Call council vote**. The vote is scheduled for the following round, giving the incumbent a response. Five actual ballots transfer office. The player remains the same person after displacement and can keep organizing to return. Neither gaining nor losing office erases relationships or promises.

## Governing and obligations

The incumbent can adopt a repair package and appoint up to two supporting liaisons. Liaisons can reach an extra contact while sharing the same total organizing budget. A liaison appointment or a choice of repair package can be promised to a contact. Incompatible package promises and overbooked posts are rejected. Office-contingent promises become due two rounds after gaining office. Honor or breach changes the beneficiary's trust in the promisor. Use **Promises** to inspect and renounce pending obligations.

Repair requires six work contributions and four hauling contributions from at least two locations in each of three consecutive rounds. Everyone counts once, regardless of overlapping memberships. Task pressure and an available effort slot are needed; newly committed people start work next round. Political opponents can cooperate on the crossing. Organizers cannot also supply work. The player can use **Work personally** when not organizing.

A missed work round resets the consecutive streak. A package change also resets it. A missed deadline is recorded, damages trust in the incumbent, and does not forbid later completion. Completion changes trust and leads to maintenance: two contributors per round after a two-round grace period. Two consecutive shortfalls create a service failure. The prototype uses abstract effort, not cash, goods or the existing construction system.

## Read the network and its history

- Blue/coral marks dominant player/rival pressure. Gold marks contested people and, with **Links**, boundaries across opposing commitments. White rings identify councillors.
- **Focus only** shows connections around the selected person. **Links** reveals the broader network. Click a contact in the stable relationship diagram to inspect them.
- **Council** shows all nine individual commitments, both pressure values, the officeholder and challenge timing.
- **Why?** shows pressure accumulation, signed incoming contributions, appeals, interests, decay, opposing resistance and saturation. The strongest incoming contacts appear by name.
- **History** buttons and left/right arrows inspect recorded rounds; **Live** returns to current decisions. Inspection cannot advance the simulation. Actions are disabled while viewing history.
- **Causes** expands the latest relevant semantic event into its causal parents. **Export** writes complete checkpoints, accepted actions, structural changes, transitions and their IDs to a `.trace.json` file beside the save.

The trace records significant changes rather than one narrative event per edge/channel update. Full local contributions can be reconstructed from checkpoints using `people_network.events.explain`. Contributions explain the executed path; the application makes no automatic claim that one intervention was a necessary cause.

Use Space or N to end a round; right-drag pans and the wheel zooms. F1 opens the briefing. Escape closes the briefing, cancels an introduction, or leaves history. The minimum window is 1100×800.

## Saves and headless verification

Save/load defaults to `outputs/people_network/laboratory.json`; `--save-path` changes it. Saves include pending decisions, pressures, graph/source state, timers and the action journal. They validate content/rules and terrain digests. A failed load leaves the current session intact. Existing game saves and terrain slots are separate. Exported JSON is intended for local analysis; saves are not signed or authenticated.

```bash
venv/bin/python -m people_network.cli --start displaced --autoplay --rounds 24
venv/bin/python -m people_network.cli --rounds 30 \
  --commands scenarios/people_network/playthroughs/govern_restore.json
venv/bin/python -m scripts.playtest_people_network
venv/bin/python -m unittest tests.test_people_network tests.test_people_network_ui -v
```

The checked 30-round fixture uses legal player commands with an active rival: displacement in round 11, restoration in round 24, and fulfillment of a liaison promise after restoration. It is a regression trace, not a walkthrough guaranteeing victory for arbitrary seeds or choices. CLI runs replay their journals and check state digests. The acceptance runner writes local summaries and full traces under `outputs/people_network/`.

The static terrain fixture was exported by `venv/bin/python -m scripts.build_people_network_terrain` from the game's polygon map generator. Regenerating it changes terrain provenance and invalidates old laboratory saves; it does not write map-editor slots.

## Current limits

This is a small full-information laboratory with a simple council and public rival heuristic. It has no death/succession, military removal, hidden intelligence, full economic integration or browser client. Organization succession on a person's unavailability exists as a journaled scenario/debug input, not as a normal player coercion action. Affiliation and geography are authored; the seed supplies a small initial pressure perturbation. After round 24, play can continue.

Automated checks establish reproducibility and the existence of different political paths. Enjoyment, balance across players, and usability with actual human testers remain to be evaluated before integrating this layer with the wider game. See the [verification report](../planning/reports/people_network_first_playtest.md).
