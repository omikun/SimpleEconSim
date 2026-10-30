# Patronage laboratory: implementation and verification

Date: October 29, 2026. Ruleset: `patronage`, save version 3. The classic version-2 laboratory remains the default. This implements the bounded six-stage [plan](../people_network_patronage_implementation_plan.md); see the [player walkthrough](../../docs/people_network_patronage.md) and [recorded results](people_network_patronage.json).

## Implemented behavior

- Public versus merchant repair management; exclusive contract, hiring and access rights with limited scope and expiry. A private hiring queue does not veto independent volunteers.
- A conserved 164-credit laboratory ledger: 36 public credits plus four per person. Escrow, earned wages, the management margin, completion bonus, tolls, maintenance and compensation are actual transfers. Four service shares remain separate.
- Voluntary jobs with individual skill/availability/outside-option decisions and a unique effort set. Rafi can refuse Quinn's exclusive queue. Thirty repair wages cover three successful work rounds; broken streaks can exhaust funding.
- Quinn can prefer continuing job control to finishing. A mutually accepted two-credit variation pays him from Yara's six-credit margin on completion. Public hiring and compensated replacement provide alternatives.
- Earned dependence, benefit attribution, different personal/constituency interests, private exemptions, changing broker power, and individual political decisions. Employment never assigns a ballot. Group agreements bind explicit signatories rather than every member.
- Public free-access claims, private terms, actual journeys, evidence, independent audit and one-hop-per-round disclosure. Reactions require knowledge and respect promise/receipt timing. Known relationship thickness reconstructs observed jobs rather than exposing hidden renewals; the normal map projects known social edges rather than revealing private changes as line widths or marker rankings.
- Persistent money, rights, evidence, ties and obligations across government changes. Sen uses the same legal commands, including contracts, delegated hiring, completion rewards, concessions, exemptions, audits, disclosure and political organizing.
- Deal cards, job/refusal records, evidence paging, council quick actions and rest/work status, a broker overview, typed map overlays, blocker explanations and a round-12 debrief separating political power, delivery and access.
- Version-2 and version-3 readers with distinct scenario digests; atomic save, resume and exact journal replay. Launchers reject cross-ruleset UI loads without replacing the current session. There is no automatic conversion.

The pressure graph remains the social authority. Directed breadth-first reachability selects a patron's reachable recruitment pool; disclosures traverse directed contacts; local weighted pressure and opposing fields still resolve political preferences. A separate small control graph projects holder → right → operation. No graph per region is introduced.

## Legal playthroughs through the interface

The SDL dummy display ran the actual Pygame drawing and mouse hit testing. The runner clicked rendered buttons and named map markers, checked accepted actions, kept Sen active, and compared each final state with the headless command route. These are automated interface playthroughs, not human enjoyment tests. The runner used no forced ballots, office transfers, balance changes or hidden availability inputs.

| Route, seed 4243 | Repair completes | Final votes / office | Access | Public repair fund |
|---|---|---|---|---|
| Public management, 12 rounds | Round 4 | 5 / player | 36 crossings; 12 journeys delayed before repair; no post-repair denials or tolls | 6 |
| Brokers, 12 rounds | Round 3 | 5 / player | 37 crossings; 8 delayed before repair; 3 post-repair denials; 30 credits actually collected in tolls | 0 |
| Displacement and restoration, 28 rounds | Round 3 | 6 / player | 85 crossings; 8 delayed; 19 post-repair denials; 35 toll credits | 0 |

All three end with a working bridge, meet the stated win condition, conserve 164 credits and pass save/load/replay. The restoration run loses office in round 11 and returns in round 19. Sen appoints an auditor in round 13 and grants a new concession in round 15. That concession is still binding when the player returns. Grower obligations breach in round 20, then recover through actual funding in round 22; civic and craft agreements are honored again in round 21.

The private route's two-credit bonus and four-credit contractor margin sum to the six reserved credits. The 30 toll credits are gross receipts, not net profit: the concession holder pays some maintenance from their wallet to preserve the income stream. A denied or unmade journey creates no toll income.

The full-information JSON saves were about 2.33 MB for public management, 2.53 MB for the broker route and 7.40 MB for the 28-round restoration. This includes checkpoints and exact reconstruction data. The latest complete UI playthroughs, replay and comparison took about 0.8, 0.9 and 2.6 seconds respectively on this host; these are whole-run timings, not engine-step benchmarks.

## Causal comparisons

Using the same broker-route commands with a specified intervention omitted:

- **No completion bonus:** Quinn withholds the paid queue. Later voluntary work rescues the bridge only in round 11, after the deadline. The government still wins with five votes, but 40 journeys wait for repair and only eight complete by round 12. The bonus improves delivery; it is not claimed to be necessary for every possible win.
- **No Quinn political rallies:** the bridge still completes in round 3. Quinn joins Sen, office changes in round 11, and the player finishes with four votes. Work incentives and political mobilization are distinct.

These are actual replay branches, not necessity claims inferred from event ordering. Separate behavioral tests show successful public delivery without political survival, paid workers voting for the opponent, unknown terms producing no evidence reaction, a bonus changing withholding, and the paid queue being bypassed by independent volunteers.

## Verification

**75 targeted tests passed**, covering the original laboratory and the new mechanics/UI. Coverage includes conservation and escrow reconciliation, permission checks and read-only previews, unique effort, motive refusal, explicit signatories, finite tolls, individual exemptions, evidence audiences and timing, audit/disclosure, no normal-play leaks, dependence reconstruction, legal displacement/restoration, exact pressure components, traced/untraced equivalence, pending-decision save/resume, replay and cross-ruleset loads.

Every panel and all deal pages were drawn at 1100×800 and 1440×960; controls stayed within the window. The opening modal blocks background input. Minimum-size council, records and help screens, plus the route screenshots, were visually inspected. The five original classic acceptance cases also passed, including its exact round-11 displacement, round-23 restoration and round-30 second displacement fixture.

Reproduce:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m unittest \
  tests.test_people_network tests.test_people_network_map \
  tests.test_people_network_advice tests.test_people_network_coalitions \
  tests.test_people_network_ui tests.test_people_network_patronage \
  tests.test_people_network_patronage_ui -q
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m \
  scripts.playtest_people_network_patronage --ui
venv/bin/python -m scripts.playtest_people_network
```

Screenshots, exact saves, per-round commands/outcomes and replay reports are in `outputs/people_network/patronage_playtests/`. Portable command fixtures are committed under `scenarios/people_network/playthroughs/patronage_*.json`. No generated terrain or full-game saves were changed.

## Scope and remaining limits

This is an authored one-project experiment: a few named brokers, fixed bounded offers, integer credits, one job wage, a limited travel schedule, a deterministic rival policy and a narrow evidence system. It does not implement open-ended price bargaining, a national economy, arbitrary institutions, parties, policing or generalized hidden intelligence. Initial motives and response coefficients are game rules, not empirical estimates.

Classic full-information five-round forecasts stay in classic mode. Patronage uses known offer/control/evidence cards instead of forecasting opponents' private state. Full truth remains available in explicitly labeled developer exports. A later belief-based forecast would require a separate design.

The winning walkthroughs establish legal, understandable routes for the default seed; they do not establish optimal play, broad balance across all seeds, a guaranteed fresh-opposition recovery path, or human enjoyment. The continuous loss-and-return path is verified. Wider campaign integration remains deferred, and laboratory accounts must be replaced by existing financial adapters before any integration.
