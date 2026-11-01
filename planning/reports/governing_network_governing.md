# First active governing slice: delivery and verification

Date: November 1, 2026.

The optional `governing` mode now implements milestone 3's first loop in Egypt's existing grain crisis. Players make food, tax and debt decisions while real residents autonomously petition, bargain or withhold work. The [plain-language guide](../../docs/governing_campaign.md) explains the choices. Milestone 4 has the automated and rendered evidence below; human understanding, enjoyment and balancing remain open gates. Opposition and return remain milestone 5.

## Implemented boundaries

- One sparse organization graph references the existing population. Synchronous friendly diffusion, local household/holder counterpressure and durable organization memory affect actual individual participation. Contacts are authored experimental content.
- Household petitions are demands now. Strike intentions are revalidated before the following economic turn against actual food, funded rations, arrears, location, work availability, survival resources and settlements. Existing labor/production consumes the projected flag once.
- Namespaced workplace, enclosure and network causes coexist. Settling one removes only its own source. Explicit whole-person repression clears affected sources. Network-only withholding does not also trigger a generic route-wide strike freeze.
- Existing public/private grain transfers, cash, tax relief, wages, mutual aid, debt and government transitions retain their existing authorities. No second treasury, action currency, council or output multiplier is introduced.
- Existing owner-funded terms reach actual petitioners. Zero-funded terms fail before wage/support changes. Individuals can refuse paid terms; accepted ceasefires expire or break on worsening conditions. Existing campaign action consequences occur once.
- The primary and legacy clients share grain-policy controls with actual current cost quotes, two common demand cards, focused local responses and due debt choices. All policies/back and scrolling expose the fuller campaign controls. Urgent crisis dialogs retain input priority, and inline debt payment/default clears the resolved warning so later phases can run. Foreign inspection does not change Egyptian governing authority.
- Native plan, participation, available firm hours and production events are causally linked. A bounded observation journal retains material/contact/opposition terms; the map panel explains recent participation changes with actual reasons or receipts.

Observe mode remains version 1 and read-only. Governing is version 2. Off remains the default. Neither live conversion nor implicit save migration is permitted. Native checkpoints preserve pending intentions, organization memory and strike sources. Restored trace branches intentionally have different future event identities; tests exclude only new `trace_event_id` references when comparing continued network state and separately compare material samples.

## Automated evidence

**The focused 40 governing/observation/UI/native tests passed.** They cover real overlapping workplace offers and enclosure dissolution, explicit repression, connected versus fragmented organizations under equal hardship, quiet cooperation without rallies, actual queued meals preventing participation, bounded/reconstructible opposing pressure, paid and rejected terms, unfunded failure, actual withheld firm hours linked to zero output, policy-cost conservation, decision limits, authority and checkpoint continuation. Coverage includes clearing an actual due-payment warning and preventing clicks through urgent dialogs.

The broader selected run attempted **80 tests: 79 passed, one failed**. `test_private_grain_purchase_is_candidate_source_for_later_meal` expects a prior purchase in the food-intake candidate list. The same assertion fails in isolation in both the active snapshot and a copy with these governing changes reverted. Earlier workplace tests also encountered ten setup errors selecting a firm with employees, reproduced in the pre-change baseline. These are limits of the shared economic baseline, not green checks; no unrelated fixtures were changed to hide them.

```sh
MPLCONFIGDIR=/private/tmp/regnum-mpl SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  venv/bin/python -m unittest \
  tests.test_governing_collectives tests.test_governing_campaign_ui \
  tests.test_governing_network tests.test_governing_network_ui \
  tests.test_governing_network_native -q
```

**All six active recording-parity comparisons passed**: three grain routes in both native engines through turn 8, with recording enabled and disabled. Each compares every turn's sampled economic metrics, full player-facing community/demand results, network diagnostic digest and policy results. A thirteenth fresh-process buy run matched the initial unrecorded run's full canonical economic graph, samples, network digest, decisions and presentation. The three routes ended in distinct canonical economic states in both engines.

```sh
venv/bin/python -m scripts.verify_governing_campaign --steps 7
```

A separate primary-engine buy route requested 19 economic steps and ended naturally in **breakdown at turn 17**. Its actual urgent dialog offered tax relief; the scripted first legal response attempted it, conditions remained beyond the existing breakdown threshold, and the next dialog accepted the declared outcome. No warning remained pending. At that point treasury was 113.11, 471 household-view residents were underfed, and 281 were in network walkouts. This is a legal failed campaign, not a winning-strategy claim. The final buy route now reaches existing late political phases instead of being held behind a hidden debt warning.

The earlier 20-turn matrix was superseded after final review found that primary-client debt decisions left an unresolved hidden warning. Final evidence uses the corrected warning lifecycle, answers urgent dialogs through their actual enabled controls and records their decisions. Temporary headless button rectangles are removed before canonical economic serialization.

**All 12 off/observe comparisons and six recording-parity diagnostic checks still passed**, covering three routes, both engines and recording on/off through turn 8. They compare sampled values, decisions and the complete canonical economic graph, excluding only the observation sidecar and relabeling the exact recorder run UUID while retaining event suffixes, money and RNG state.

```sh
venv/bin/python -m scripts.verify_governing_network --steps 7
```

Simulation comparisons used a frozen 707-file shared-source copy, SHA-256 `af701038c5068f4e0b41123850d9dbe87f840b42731d3064b739bb1c4ed5c1bc`, archived locally at `outputs/governing_network/governing-final-sources.zip`. This avoids concurrent source drift during paired runs. It includes other ongoing economic work and is not a clean-branch release certification. The [JSON report](governing_network_governing.json) records the compact evidence, route samples, UI commands and limitations.

## Actual primary-client playthroughs

All three routes were rendered at 1400×900 from that same frozen source, with fixed Python, NumPy and hash seeds. The replay clicks actual registered controls and advances real economic turns. It never forces actors, resources, strike flags, policies' success or victory. Screenshots were visually inspected for readable costs, district names, bargain uncertainty, debt consequences and accessible targets.

| Turn | Decision | Rationale and visible cue |
|---|---|---|
| 1 | Distribute public maize | The button quotes 110 household meals costing 440 public maize. Fund meals before the next work decision. |
| 2 | Buy, requisition or open private sales | Compare the visible treasury quote and owner losses with cash-dependent household access. The buy route quoted 80 maize for 89.3 treasury; requisition moved 80 without payment. |
| 3 | Distribute acquired grain on the buy/seizure routes | Acquisition is not consumption. The button quotes 20 household meals from 80 maize. Private sales instead continue automatically. |
| 6 | Pay the available 200 debt service | The due card shows the treasury, payment cost and alternatives. These runs had enough cash; later debt obligations persist. |

The player made four policy decisions on the buy/seizure routes and three on the market route through turn 8. **Zero political upkeep or individual recruitment actions** were needed. All policies and Back were exercised. The two-demand-plus-debt layout is also covered by a presentation test. Pending/current walkout counts and a concrete recent explanation remain visible without selecting a person.

At turn 8, the buy/seizure/market routes respectively had treasury 136.16/225.50/231.72, underfed household-view residents 459/459/456, and current network walkouts 297/284/300. The market UI route takes no turn-3 tax action; the longer simulation matrix does, so these are distinct documented command sequences. All UI routes still had substantial hunger and no terminal outcome at turn 8.

```sh
venv/bin/python -m scripts.playtest_governing_campaign --route buy
venv/bin/python -m scripts.playtest_governing_campaign --route requisition
venv/bin/python -m scripts.playtest_governing_campaign --route market
```

The verified short render artifacts are under `outputs/governing_network/governing-ui-final/`. Voronoi rendering required graphics access in this environment. The ordinary script defaults to `outputs/governing_network/governing-ui/` and supports `--output-dir`.

A long rendered buy playthrough also reached the same natural **turn-17 breakdown** through the primary client's actual urgent-dialog controls. It made six main-panel policy decisions: release, purchase, release and debt payments on turns 6, 11 and 16. The existing breakdown dialog then attempted tax relief and, when that did not restore viable conditions, accepted the declared outcome. The debrief was rendered and visually inspected: debt service paid, outstanding claim zero, government legitimacy 4%, and widespread hunger. No recruitment upkeep was added. The complete UI command/notice sequence and snapshots are in the JSON report; images are under `outputs/governing_network/governing-ui-long/buy/`.

## Open gates

The first slice demonstrates actual network effects and policy trade-offs without requiring a recruiter-management loop. It does not prove a balanced or enjoyable campaign. Persistent high hunger needs human playtesting alongside the concurrent food-economy changes. The next review should ask whether players understand petitions versus walkouts, whether funded food changes feel clear, whether refusal and owner opposition matter, and whether any recurring response feels like upkeep.

The network remains a coarse organization graph. Owner opposition is counterpressure rather than an independent economic veto; merchants are a material view rather than autonomous negotiators. Broader representation, personal mandates, opposition resources and return-to-power institutions remain future work. Existing government transitions and the current campaign's end conditions still apply.
