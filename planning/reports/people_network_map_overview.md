# Network laboratory: readable overview and river geography

Date: October 28, 2026.

## Problems addressed

The original settlement exporter chose land near arbitrary target coordinates. It never checked which direction a river flowed or whether a place called Upstream Village was inland. The original interface required opening individual people to find useful relationships. Its focus diagram and all-links view did not explain whom to ask, what to ask for, or how the bridge and political goals differed.

## Geography

The corrected fixture exports 350 polygon terrain cells. It selects one actual generated river by following downslope corner pointers from elevated headwaters to the coastal mouth. Settlements are placed relative to this chain, not arbitrary screen coordinates. Upstream Village is inland at approximately 0.74 normalized elevation, below the headwaters at approximately 0.82 and above the coastal landing at approximately zero. The town and workshop are inland on opposite sides of the river corridor. The bridge spans a real river segment, replacing the arbitrary village-to-town line.

The fixture records cell IDs, elevations, coastal flags, river stations, main-river corner IDs, crossing banks and framing bounds. Authored scenario location coordinates now agree with the exported map. Tests verify a non-increasing downhill chain, matching actual river segments, inland/coastal placement and aligned scenario/terrain coordinates. Existing saves from the old authored geography are rejected by the existing content/terrain digest checks; restart the laboratory to use the corrected map.

## In-game understanding

The default **Overview** states the two purposes: hold five council votes and repair the bridge. It explains farmers' field access versus traders' market access, offers the repair choices, shows current vote/work availability, and presents up to two explained opportunities with direct action buttons. Recommendations are read-only observations of the current public state. They do not give the player free support, alter AI decisions or predict guaranteed success.

**Ask for support** means speak to one person. **Ask to rally** means ask an ally to spend their work time recruiting contacts for the selected goal. These definitions appear in the briefing and person view. The selected goal can be council votes, farmers' repair or traders' repair. Newly available office challenges can also be requested from Overview.

The terrain and **Network** views show the same graph. Network lays everyone out in stable community groups with all 32 names visible at both supported window sizes. Node size reflects trusted weighted outgoing reach; diamonds are council votes; green rings indicate rallying; colors indicate actual commitments. Community cards show support counts and repair preferences. Suggested people have numbered badges matching the cards. Useful links emphasize those intermediaries and the selection; All links is available for full inspection. Hovering reveals contact reach and council role without opening the inspector.

Reach counts only active outgoing channels with contextual trust at least 0.45, weighted by trust and capacity. It is a readable opportunity measure, not a new persuasion bonus. Advice combines it with available allied organizers, current commitments, cross-community contacts and councillors reachable by the player. A popular person who does not trust you is not treated as an automatically controllable organizer. Duplicate suggested people are removed so badges remain unambiguous.

## Verification

- 51 targeted tests pass: 18 graph/game rules, three geography/advice contracts, three Pygame controller/layout checks, and 27 existing desktop chart/explainer checks.
- Advice is tested for read-only behavior, legal previewable actions, unique badges and the ability to rally directly from Overview without opening Person.
- Both map modes render at 1100×800 and 1440×960; every person is labeled in Network. Screenshots of terrain, network and in-game briefing are visually reviewed.
- All five political acceptance paths still replay exactly, including displacement in round 11 and restoration in round 24 of the continuous case. [Acceptance summary](people_network_acceptance.json) is refreshed for the new geographic content and terrain digests.
- No pressure dynamics, council thresholds or economic integration were changed in this revision. Human playtesting of the clearer presentation remains the next evaluation step.

## Subsequent advice revision

The initial overview heuristics described above were too shallow: political targets were ranked mostly by current opposition and organizers mostly by reachable contacts. The [strategy advice revision](people_network_strategy_advice.md) replaces these suggestions with bounded forward comparisons through the actual rules, exposes assumptions and opportunity costs, and maps relationship strength to line thickness. It leaves the political simulation unchanged.
