# Egypt strategic loop: integration audit

Date: 2026-10-04. Scope: Phase 6 of [the strategic loop plan](EGYPT_STRATEGIC_LOOP_PLAN.md).

## Reproduction

```sh
PYTHONHASHSEED=0 MPLCONFIGDIR=/private/tmp/regnum-mpl venv/bin/python audit_egypt_strategic_integration.py --suite --output /private/tmp/egypt_strategic_integration_verified_final.json
PYTHONHASHSEED=0 MPLCONFIGDIR=/private/tmp/regnum-mpl venv/bin/python -m unittest test_scenario_playthroughs -q
MPLCONFIGDIR=/private/tmp/regnum-mpl venv/bin/python -m unittest test_scenario_projects test_scenario_presentation test_scenario_debt test_scenario_diplomacy -q
```

The audit runs each campaign in a separate process. The replay helper resets the bond market, imperialism manager, agent IDs, and campaign random stream. Its fiscal variants transfer up to 40 units between Cairo and a real private household without creating cash. The two Nile variants set the Delta and Upper Egypt yield modifiers to 0.25 or 0.55 through turn 12. The matrix covers 35 complete paths: 16 ending routes, a food-access continuation, 16 opening-project and political routes under paired Nile/fiscal conditions, and two favorable payment routes. Both Python hash seeds 0 and 1 occur in the matrix.

## Results

The isolated matrix reached **15 of 15 declared outcome IDs**, with no replay errors, and the full playthrough test passed all ten tests including an independently rerun reachability matrix. The baseline historical route went through succession, a debt warning, a naval ultimatum, landing, capital conflict, officer movement, and occupation. Organized resistance reached nationalist victory; mediation reached sovereign compromise; a funded sovereignty project could still produce successful repudiation. The first chapter can therefore feed materially different second-chapter conflicts.

| Route | Observed result | Strategic and social reading |
| --- | --- | --- |
| Pay and protect food | Relief and payment; no claim outstanding; 1.6% hungry at finish in one sampled run | A treasury-first plan is possible with later district cash recall and grain access, but that run still accumulated 3,957 household hunger turns. |
| Settle with creditors, ordinary low Nile | Creditor settlement or fiscal hardship in sampled replays; claim cleared | Clearing bonds does not establish food security; borderline final hunger changes the category. |
| Settle with favorable Nile and +40 central cash | Creditor settlement; claim cleared; below 1% hungry at finish in one sampled run | The protected ending is conditional on real food access and fiscal room. |
| Delta repair with access follow-up | Creditor settlement in one sampled baseline; 1,513 private food units delivered and 75.65 paid to carriers | Repair plus grain retention, requisition, bargaining, and a standing entitlement can reach households. The 3,660 cumulative hunger turns remain visible in the debrief. |
| Delta repair alone under paired shocks | Fiscal hardship or breakdown; high final hunger | Extra harvest does not automatically defeat warehousing and unequal access. |
| Alexandria revenue office under paired shocks | Fiscal hardship in sampled variants; claim cleared | The office moves actual receipts and causes a Caisse reply; collection does not feed households. |
| Canal defense under paired shocks | Successful repudiation in sampled variants; high final hunger and 600 claim outstanding | Defensive sovereignty can coexist with debt and severe hunger. |
| Historical occupation / resistance | Occupation / nationalist victory | Military and political responses both remain reachable; neither is a welfare victory by itself. |

The ending labels are evidence categories, not scores. A favorable final hunger count can follow many hungry turns, so the debrief reports cumulative hunger, calorie deficits, private grain holdings, creditor transfers, and casualties. No opening project dominates all tested conditions: each front changes a distinct physical or institutional state, and pursuing only the project leaves other pressures exposed.

## Conservation and interface checks

- Project tests verify cash moves to named workers, grain leaves owner inventory before emergency meals, carrier wages come from Cairo, and district reserve recall preserves aggregate government cash with a protected local floor. Tax tests verify that the Alexandria office divides collected receipts and that Caisse interception reduces the outstanding claim by the amount actually received.
- A generic revolutionary commune can no longer silently repudiate the authored Caisse bonds. The historical debt/creditor and naval loop remains intact because Britain and France's local grievance growth is scaled to reflect their larger off-map administrative capacity; the 0.20 factor is a gameplay abstraction.
- The Guided project strip, map markers, action previews, and debrief were exercised in focused tests. A 1400 × 900 Guided frame was rendered with the full desktop GPU terrain renderer on an Apple M3 Pro using the cached 40,064-face mesh (120,192 vertices), saved as `/private/tmp/egypt_phase6_guided.png`, and visually inspected. The full renderer remained active.
- The audit tracks material events, chosen actions, and thresholded national-stat changes by turn. A mediation route with a three-turn quiet streak was updated to respond to cultivator tax pressure at turn 14. The subsequent 35-path matrix had a maximum quiet streak of two turns. This heuristic detects stalled feedback, but cannot establish whether a new player understands or enjoys the decisions.

## Remaining design limits

1. **Late relief can clean up a final snapshot.** The food-access route can end with very low hunger after substantial cumulative deprivation. That social cost is disclosed, but outcome classification still uses the GDD's final 20% hunger threshold. A future balance pass should decide whether the protected ending should also require a cumulative welfare condition; changing it now would require new route tuning and explicit GDD approval of that design change.
2. **Early standing relief is expensive.** A separate turn-4 entitlement trial transferred 7,406 food units and paid 370.3 cash to carriers, exhausting Cairo's ability to service later debt; it ended in occupation with 63% hungry. This is a real fiscal tradeoff, but the 0.05 fee and private-reserve rules need human playtest for legibility and plausibility.
3. **No blind player was available.** The automated matrix proves mechanical reachability, conservation checks, and visible status change. It does not prove that the loop feels fun or that players can infer who benefits and who pays without prior knowledge. The next playtest should ask what plan the player formed, what changed on the map, how the rival reacted, and who bore the cost, then revise tooltips and timing from those answers.
4. **Fixed seeds do not yet make every aggregate replay identical.** Fresh processes with the same authored map and random seed have shown small changes in household outcomes, and a borderline route can cross an ending threshold. The isolated matrix checks existence of decision paths across conditions; its exact welfare figures are samples. A later engine pass should identify the remaining iteration-order or global-state source before using single-seed results as balance guarantees.
