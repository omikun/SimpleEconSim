# Patronage: play guide and tested winning routes

Launch from the repository root:

```bash
venv/bin/python -m client.desktop.network_lab --ruleset patronage
```

The normal launcher still opens the classic coalition laboratory. Patronage uses the same 32 people and terrain, with a separate version-3 save. The broader economic simulation stays off.

## What you are doing

A flood broke the bridge. You have a fragile five-vote government, a public repair fund of 36 credits, four recurring service shares, and two political actions each round. The credits and service shares are separate resources.

You can pay a public board to manage repairs, or bargain with Yara for a private contract. Delegating jobs can give Quinn a following of people who depend on him. A toll concession can enrich a broker while excluding people without money. Giving Inez an exemption helps her personally; her village still pays. These people also hold council votes, but a job or favor does not automatically deliver anyone's ballot.

**Win from completed round 12 onward: hold office, have at least five council commitments, and keep the repaired bridge working.** The result separately reports your political power, bridge delivery and access. You can continue after the debrief, lose office, organize a movement and return. A late repair can satisfy the round-12 condition, but the missed deadline and lost journeys remain in the history.

## Which screens help

| Screen or mark | What it tells you | Decision it supports |
|---|---|---|
| Start | Council count, delivery, access, fund, escrow, your wallet and current blockers | Whether your next action needs to address construction or the coalition |
| Deals → Repair | Public and private offers, reserved margin, actual wages and the remaining affordable work | Whether the speed/control bargain is worth the cost; whether a bonus can still help |
| Deals → Access | Toll terms you know, known exemptions, expiry, buyout and access outcomes | Who receives rents, who pays, and whether to end a concession |
| Deals → Records | Public free-access promise, independent audit and evidence you can disclose | Whether your promises conflict, and who could learn that |
| Council | Nine named commitments, quick Ask/Rally buttons, work commitments and rest status | Protecting the fifth vote and rotating people without double-booking workers |
| Brokers | Each major actor's own demands and known paid dependents | Distinguishing an influential representative from their constituents |
| Jobs | Actual acceptances/refusals, wages, outside options, worker/hauler counts and paging | Checking whether a broker delivered the advertised crew |
| Network / Terrain | Same state, different layouts; every person is named in Network | Locating intermediaries and seeing whether a relation crosses communities |
| Gold outer ring and gate arrows | Who controls repair management, the job queue or access | Identifying a particular bottleneck and a possible replacement |
| Teal dashed links | Paid dependence you know about; thicker means stronger dependence | Seeing who gains a following from public spending; this is separate from trust |
| Solid ties, larger people, council diamonds | Known communication strength, known outgoing reach and council seats | Comparing observed social influence with legal authority and the votes you need |
| Green rally ring; Person rest message | Who is spending effort recruiting, and who needs a break | Keeping political pressure going while preserving repair labor |
| Why? | Records you possess and their timing | Following a change without revealing opponents' undiscovered deals |

Inspecting and changing views is free. Taking a political action costs one action. **End round** or Space runs the rival, work, payments, evidence and pressure simulation. Map markers open Person; Council also has direct Ask/Rally buttons. Click Iskra on Network or use Start's **Rally your own contacts** to organize personally.

## The cynical winning route I played

This is a reproducible seed-4243 route, played through the actual Pygame button and map-marker hit testing with Sen active. It is an example, not a claim of optimal play. The public alternative below also wins.

The first column matches the **completed round counter in the header**. Make those choices, then click End round. Thus the row labeled 0 produces completed round 1. “Rally” means the political goal **my coalition**, not repair work.

| Completed rounds before the move | Actions | Why these actions | Where to decide |
|---|---|---|---|
| 0 | Award Yara the contract; appoint Quinn to hiring | Get a crew operating immediately. The fund reserves 30 for work and six for the management margin. Quinn gains control over jobs, which creates a future problem as well as cooperation. | Deals → Repair: compare costs, startup delay and broker motives. |
| 1 | Reserve Quinn's two-credit completion bonus; rally Iskra's own contacts | Quinn can prefer preserving his temporary office to finishing. A completion reward changes that incentive. It comes from Yara's margin, with both brokers accepting the variation. Iskra begins political recruitment while the paid crew works. | Repair's bonus card; Start's own-rally button. |
| 2 | Grant Yara a two-credit toll concession; exempt Inez personally | This is the cynical bargain: Yara gets an income right and Inez gets private protection. It does not secure their followers. The crew completes the bridge at the end of this round. These favors are optional political choices, not prerequisites for all winning strategies. | Access: fee, duration, individual exemption warning; Jobs confirms the crew. |
| 3 | Rally Quinn; appoint Amal as a public-service liaison | The hiring office has expired, but Quinn's paid relationships remain. Get his political network working with you. Amal's liaison satisfies the civic demand. **Liaison is a different action from appointing her independent auditor.** | Council quick Rally; Person's Appoint public-service liaison. Gold job-office control disappears; teal dependence remains. |
| 4 | Move one service share from trade to growers; agree to growers' conditions | Inez's private exemption has not met the village's public-service demand. Funding becomes civic 1, growers 2, craft 1, trade 0. This sacrifices traders' services despite Yara's private gains. | Start → Groups: donor selector, funding/need and agreement terms. |
| 5 | Agree to civic conditions; rally Yara | Civic funding and Amal's liaison make this promise deliverable. Profit alone does not keep Yara in your coalition indefinitely; political recruitment still matters. | Groups; Council's Yara row. |
| 6 | Agree to craft conditions; rally Amal | Craft has its share and a manageable campaign workload. Amal spreads support through the civic network. | Groups; Council. |
| 7 | Rally Basil and Iskra | Rotate effort as earlier organizers tire. Recruiting through the town helps preserve its two allied council seats. | Council rest messages; Start's own-rally button. |
| 8 | Rally Inez | Mobilize the farmer network while others recover. Her own support and the village's needs remain separate considerations. | Council and Brokers. |
| 9 | Rally Quinn again after his break | His remaining following can support either candidate. Keep the former job patron politically engaged. | Council's readiness message and Network's remaining teal ties. |
| 10 | Inspect; no action needed in this recorded route | Check that five commitments and a working bridge remain. Free inspection does not consume actions. | Start, Council and Access. |
| 11 | Rally Yara after her break; end the round | Sustain the fifth-seat coalition through the debrief. | Council and the round-12 result. |

Result: **five council votes, office retained, bridge completed in round 3, 37 completed journeys, three post-repair access denials and eight journeys delayed before repair**. Yara collected 30 credits in actual tolls; some of her earnings paid maintenance. Quinn earned the two-credit completion reward, Yara earned the remaining four-credit contract margin, and workers earned 30 repair credits. The public fund ended at zero. No money was created: all accounts still total 164 credits.

Not every step above is necessary for every win. In a replay branch, omitting the bonus delayed completion from round 3 to round 11; later voluntary work eventually rescued the task, after the deadline. Omitting Quinn's political rallies instead lost his vote, and Sen took office in round 11. These are comparisons of the recorded route, not universal rules about all possible sequences.

## A public-management route also wins

It completes in round 4, retains five votes, leaves six public credits, charges no tolls and denies no post-repair journeys. Twelve journeys wait for repair, compared with eight in the faster private route. The two routes therefore trade speed, public funds, private power and access rather than awarding a simple morality bonus.

| Completed round | Actions before ending the round |
|---|---|
| 0 | Public management; rally Yara. |
| 1 | Appoint Amal as liaison; rally Quinn. |
| 2 | Rally Amal and Iskra. |
| 3 | Transfer a service share from trade to growers; agree with growers. |
| 4 | Agree with civic and craft. |
| 5 | Rally Basil and Inez. |
| 6 | Rally Yara. |
| 7 | Rally Quinn. |
| 8 | Rally Amal and Iskra. |
| 9–10 | Inspect; no additional actions in this route. |
| 11 | Rally Basil and Inez. |

Public hiring takes an initial round to gather applicants. It spreads jobs beyond the council and attributes more of the benefit to the government. It still needs consent, available skills and political maintenance. Repairing the bridge and then neglecting the coalition loses office in a separate legal run.

## Promises, evidence and removal

Publicly promising free access does not prevent you from granting a toll concession. It creates an obligation. A person who pays or sees a relevant receipt can identify a contradiction. A promise made after an earlier toll does not retroactively make that toll a breach.

Private exemptions are known to the parties. Amal's independent audit grants real record access on the next round; she publishes findings herself, including deals that hurt the appointing ruler. Disclosures spread one directed relationship hop per round. A person reacts only after receiving the evidence. Private beneficiaries and excluded members can respond differently. Normal offer cards, advice and tooltips do not read opponents' undiscovered clauses. Full truth remains in the explicitly labeled developer export.

Replacing a private hiring officer costs two personal credits in compensation; public recruitment takes a round. Buying out a concession costs two personal credits. Earned wages, profits and relationships remain. Cancelling an active merchant contract compensates its holder and returns unused escrow; it does not refund work already paid for. If the work streak breaks, the original fund may no longer cover three new consecutive rounds. The blocker card explains that shortage.

## Reproduce the playtests

The third committed route, `patronage_restore.json`, deliberately omits Quinn's political rallies, loses office in round 11 and returns in round 19 through ordinary appeals, organizing and a confidence vote. Sen audits the old deals and grants a new concession while governing. Returning does not erase that concession or the grower agreement. Reappointing Amal and restoring the growers' two service shares recovers the governing coalition by round 22. It ends round 28 with six votes. This route is also clicked through the interface by the runner below.

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  venv/bin/python -m scripts.playtest_people_network_patronage --ui
venv/bin/python -m people_network.cli --ruleset patronage --rounds 12 \
  --commands scenarios/people_network/playthroughs/patronage_brokers.json
```

The UI runner clicks the same rendered controls used by native mouse input, keeps Sen active, checks each accepted command and compares the resulting state with the headless route. It saves screenshots, reports, saves and exact replay checks under `outputs/people_network/patronage_playtests/`. This verifies the interface and legal simulation path; human playtesting is still needed to judge enjoyment and difficulty. See the [verification report](../planning/reports/people_network_patronage.md) for coverage and current limits.

Patronage saves default to `outputs/people_network/patronage.json`. Classic version-2 saves remain supported by the classic launcher. There is no automatic conversion or live ruleset toggle. Restart in the desired mode for comparison.
