# Egypt campaign: diplomacy and outcome completion plan

## Goal and boundary

Finish the 20-turn Guided Egypt campaign without adding another dashboard of player-facing numbers. Every ending must describe a durable state caused by decisions and simulation: food access, debt, revenue control, government authority, territorial control, and enforceable foreign commitments. Britain, France, and the Ottoman government may disagree. A French statement of support must not silently become a French fleet, bombardment, occupation, or veto over Britain.

The current implementation has ten reachable endings, but a solvent, stable government with poor food access can fall through to `breakdown`; disarming Alexandria can be called `successful_repudiation`; France's stance is mostly a report; and revenue oversight after `concede_revenue` has little continuing play. This plan keeps the existing short campaign and uses the existing strategic order layer, sovereign bonds, conserved transfers, fleets, occupation system, warnings, Guided panels, and Advanced UI.

The historical calibration is *joint diplomatic and naval pressure followed by a British-only bombardment and expedition*, not a required sequence. A [UK parliamentary account of the July 1882 crisis](https://hansard.parliament.uk/Commons/1882-07-25/debates/cbf550ed-9305-4bff-a87d-cfdc22e615da/Supply%E2%80%94ForcesInTheMediterranean%28VoteOfCredit%29) records that France declined to join the bombardment. A [later UK parliamentary account](https://hansard.parliament.uk/Commons/1883-03-02/debates/b4fd568c-89cb-4466-af05-9f7f8c1f563c/CommonsChamber) reports the French Chamber's rejection of naval credits and subsequent withdrawal. These are historical guardrails for possible branches, not fixed event triggers or game balance values.

## State and outcome contract

Add one inspectable `scenario_state['diplomatic_crisis']` record. Its public fields should be: Egyptian proposal, British policy, French policy, French authorization, French commitment, Ottoman offer, treaty terms, treaty signatories, and reasons for each actor's decision. Commitments are `none`, `endorsement`, `mediator`, `joint_guarantor`, or `joint_enforcement`; actual fleet presence and expenditures live in `geography['fleets']` and the ledgers. Save a snapshot of the decisions at each crisis step so later AI changes do not rewrite history.

Treat an ending as a **primary outcome plus factual descriptors**. The primary outcome answers who governs and controls debt or territory; descriptors report food hardship, payment state, who backed intervention, casualties, and whether a treaty remains enforceable. Preserve existing outcome IDs where possible for old saves. Rename only player-facing titles when an old ID overstates what happened. Do not create separate endings merely because France issued a statement or because one extra flag changed.

| Primary ending | Required durable state at campaign end | Change |
| --- | --- | --- |
| Relief and payment / creditor settlement | Claim paid or written down, food protected, no overriding territorial control | Keep existing IDs |
| Fiscal hardship | Claim paid or settled, government above breakdown thresholds, but food access still poor | New `fiscal_hardship`; debt descriptor says paid or settled |
| Coercive extraction / breakdown | Extraction while government survives / actual low legitimacy or high unrest | Keep existing IDs; no generic fallback to breakdown |
| Creditor financial control | Active, enforceable assignment of receipts with unpaid claim | Keep `imposed_financial_control` ID for saves; display consent/coercion and creditor identity |
| Joint creditor control | Britain and France both sign, fund, and receive an active assigned-revenue agreement | New `joint_financial_control` |
| Sovereign compromise | Ottoman-mediated settlement actually paid and accepted | Keep existing ID |
| French-brokered compromise | France offers terms, Egypt and Britain accept, claim is revised or paid, no foreign revenue/territorial control | New `french_brokered_settlement` |
| Coerced disarmament | Egypt disarms or yields a military guarantee, claim remains, no foreign territorial/revenue control | New `coerced_disarmament`; never call this repudiation |
| Unresolved crisis | Claim remains and no enforceable settlement, foreign control, victory, or breakdown is established | New `unresolved_crisis`; debrief states next obligation and the threat |
| Successful repudiation / nationalist victory | Default survives without disarmament, levy, or foreign control / nationalist cabinet also repels or outlasts intervention | Tighten existing predicates; record source of British withdrawal |
| Stalled intervention / occupation | Britain still holds a foothold / Cairo | Keep existing IDs; record whether France materially participated |

Priority: actual Cairo control, then other occupied sites; actual breakdown; active joint or unilateral control; accepted settlements; coerced disarmament; defended sovereignty; surviving extraction; paid/settled food result; otherwise unresolved crisis. A nationalist victory can be promoted ahead of nonterritorial debt outcomes only when the cabinet governs and the foreign expedition was defeated or forced out, not simply because a fleet left after Egypt conceded. Keep food hardship as a descriptor on every ending as well as the `fiscal_hardship` primary ending when debt was resolved but food was not.

## Phase 1 — Correct ending evidence before adding diplomacy

1. Introduce a normalized `outcome_evidence` or equivalent projection from the actual bond balance, ledger, fleet and occupation state, welfare metrics, and recorded concessions. `classify_outcome` must consume it. Do not infer a victory from `naval_crisis.stage == 'withdrawn'` alone.
2. Record why each squadron withdrew: paid settlement, failed supply, political restraint, deterrence, disarmament, or defeat. Record whether disarmament and other guarantees survive at turn 20. A withdrawal due to Egyptian payment is a settlement; a withdrawal after disarmament is a concession; a withdrawal forced by cost or military defeat may support repudiation.
3. Add the `fiscal_hardship`, `coerced_disarmament`, and `unresolved_crisis` endings and debrief text. Replace the final unconditional `breakdown` fallback. Keep the early breakdown warning and rescue choices.
4. Show the exact ending evidence in the debrief: hunger rate, legitimacy/unrest threshold, outstanding claim, active assignment, concessions, control of Alexandria/Cairo, and source of withdrawal.

**Done when:** Complete campaigns reach each new ending through UI-valid decisions. No stable government is labeled collapsed solely because food is poor; disarmament cannot become repudiation; no active claim silently disappears at turn 20. Existing ten paths remain reachable. Candidate files: `scenario_egypt_1877.py`, `scenario_gunboat.py`, `scenario_debt.py`, `scenario_status.py`, `worldview_scenario_ui.py`, `test_scenario_playthroughs.py`.

## Phase 2 — Make concessions and guarantees enforceable

1. Represent `concede_revenue` as a signed, bounded oversight agreement: inspected revenue streams, inspection cost, information disclosed, expiration or review condition, and a breach response. Mere inspection should not seize cash. A collection assignment must name eligible receipt streams, cap, remaining claim, creditor shares, and who can enforce it.
2. Give Egypt at least one follow-up decision: comply and preserve terms, seek a narrower assignment with a real offer, or revoke oversight at a predictable diplomatic cost. The Caisse responds by accepting, demanding collateral, or escalating depending on actual collection, claim exposure, and credibility.
3. Use the existing debt and occupation ledgers for every payment, levy, military upkeep payment, and negotiated transfer. Neither a treaty nor a new French branch may mint or destroy cash. Joint collection pays Britain and France according to claims or signed shares and ends when the claim is settled.
4. At turn 20, record whether an agreement remains binding rather than treating a temporary promise as permanent control.

**Done when:** Each concession changes future choices or receipts; revocation creates a visible response; ledger totals and bond principal reconcile; expired or discharged assignments cannot produce a control ending. Candidate files: `scenario_situation.py`, `situation_scenario_template.json`, `scenario_debt.py`, `scenario_occupation.py`.

## Phase 3 — Give France an independent, costly choice

1. Evaluate French policy from its **own** bond exposure, expected recovery, treasury and domestic protest, the cost of a British monopoly in Egypt, canal access, and any Egyptian offer. Expose the top two reasons in the foreign report. Freeze a policy commitment for the current ultimatum, then permit withdrawal only through a recorded event such as lost authorization, unpaid supply, or a broken treaty.
2. Separate four French reactions: **endorse collection** (diplomatic signal), **offer mediation** (terms both Cairo and London can accept or reject), **join enforcement** (requires funded authorization and a supplied French squadron), and **oppose unilateral action** (raises Britain's diplomatic and domestic cost but does not veto it). Abstention remains possible. Require authorization for a French bombardment or landing separately from a naval demonstration.
3. Give Egypt contextual offers that consume its normal major decision: request French mediation, offer a transparent joint revenue guarantee, or seek French opposition to unilateral enforcement. Each offer states its price in money, autonomy, intelligence, or future rights. France answers next turn with reasons. Britain then chooses whether to accept the bargain, proceed alone, or withdraw based on expected claim recovery and intervention cost.
4. If France joins enforcement, create and supply a **real French fleet** through existing fleet rules. Do not fold French guns into the British fleet. Blockade and damage calculations use each present fleet's authorized contribution; participation costs France cash and raises its domestic exposure. British command may still proceed alone after a French refusal or withdrawal. A French ship without bombardment authorization can demonstrate but cannot fire.
5. Give Ottoman mediation a genuine proposal and British/Caisse acceptance rule, rather than an Egyptian cash check alone. Rejecting mediation has a visible political and fiscal consequence; the historical path remains possible.

**Done when:** Under different measured conditions France can endorse, abstain, oppose, mediate, or join at least naval enforcement; each choice alters British or Egyptian options and has an observable cost. Britain can still intervene alone after France declines. A French commitment never grants free ships or an automatic victory. Candidate files: `scenario_geography.py`, `scenario_gunboat.py`, `scenario_campaign.py`, `scenario_situation.py`, `scenario_debt.py`, `situation_scenario_template.json`.

## Phase 4 — Resolve French branches into distinct states

1. A French-brokered treaty requires an offer, separate Egyptian and British acceptance, an actual claim revision or payment, and named future rights. Only then may it end as `french_brokered_settlement`.
2. Joint creditor control requires both governments to sign and fund collection, a live assignment, and ledger transfers to both. Only then may it end as `joint_financial_control`. If France merely endorses Britain, retain the ordinary financial-control or occupation ending with a French-support descriptor.
3. French opposition raises the British cost or reduces legitimacy of unilateral force; it can cause withdrawal, but Britain may pay the cost and fight alone. If a binding nonintervention guarantee is later added, it needs a breach rule and could merit its own ending; mere opposition is an ending descriptor.
4. If France joins a fleet but Britain alone takes Cairo, the primary ending stays British occupation. A truly joint occupation requires separately supplied French land units and shared institutional control; defer that larger mechanic until there is a player decision loop for it.
5. Prevent modal deadlocks when French, Ottoman, creditor, naval, and debt decisions become due on the same turn. Apply deterministic priority, queue the remainder, and allow the player to answer each consequential demand before the next simulation step.

**Done when:** A full decision-path campaign reaches every new diplomatic ending and can still reach every old one. The same recorded state always classifies the same way, even after saving and loading. No branch claims French military or financial control without the corresponding fleet, contract, and ledger evidence. Candidate files: `scenario_egypt_1877.py`, `scenario_gunboat.py`, `scenario_occupation.py`, `worldview_engine.py`, `test_scenario_playthroughs.py`.

## Phase 5 — Present the diplomatic loop without crowding Guided mode

1. Keep three headline pressure cards. Promote a temporary **Foreign decision** card only when a French or British response is pending; show the actor, commitment, cost, deadline, and one likely next move. Put bond shares, votes, fleet supply, treaty clauses, and causal history in Analysis and tooltips.
2. On each offer or ultimatum, show enabled choices and their projected changes. Separate `France endorses`, `French fleet present`, and `France authorized to fire` in plain language. Never use a single “France supports” flag for all three.
3. Show a short chain in the log and debrief: Egypt's offer → French decision and reason → British decision and reason → payment or military action → final control. Mark historical parallels as such, and mark alternate outcomes as simulation results.
4. Keep Guided and Advanced on the same scenario state and action handlers. Update the reusable situation template with actor decisions and enforcement prerequisites rather than hard-coding France's branch in rendering.

**Done when:** A player can explain why France joined, declined, or opposed; what Britain did in response; who actually controls revenue and territory; and why the ending was awarded. The full choice list remains visible and every choice has a consequence tooltip. Candidate files: `worldview_scenario_ui.py`, `client/desktop/panels/scenario_ui.py`, `scenario_status.py`, `scenario_history.py`, `gdd.md`.

## Verification and commit sequence

After **each phase**, verify its state invariants and run the relevant scenario tests before committing that phase. At the end, run all scenario suites, a deterministic complete campaign for **every primary ending**, and multi-turn diplomacy cases covering every French policy and British reply. Include one save/load continuation and one Guided modal-click path per new consequential decision. Recheck ledger conservation, bond balances, one-major-action-per-turn, modal priority, and the existing historical British-only route. Commit each phase separately, as with the preceding Egypt mechanics plan.

## Decisions to lock before implementation

1. **French armed scope:** Recommended: independent French naval demonstration and optional blockade/bombardment; no French land campaign in this pass. A joint occupation requires a separate phase.
2. **Diplomatic victory:** Recommended: French opposition alone modifies an outcome; only an enforceable treaty creates a new primary ending.
3. **Campaign horizon:** Recommended: keep 20 turns and report outstanding treaties and debt honestly in the debrief. A later chapter can continue those states.
4. **Outcome count:** Recommended: add only the five primary outcomes named above, and use descriptors for smaller variations. Keep the existing ten IDs reachable and avoid multiplying endings for every France stance.

## Implementation record

| Phase | Commit | Result |
| --- | --- | --- |
| 1 | `c5742af` | Ending evidence, withdrawal causes, disarmament, and three missing endings. |
| 2 | `521a3dd` | Bounded Caisse oversight and receipt collection with follow-up decisions and ledger transfers. |
| 3 | `9104196` | Independent French policy, Egyptian offers, British replies, funded French fleet, and separate fire authorization. |
| 4 | `25e02d2` | Campaign paths for the two treaty endings and all other endings; final-turn diplomatic replies resolve before debrief. |
| 5 | Final phase commit | Guided pressure and modal presentation, scrollable evidence debrief, updated situation template and GDD. |

The outcome classifier is checked against recorded scenario state after a pickle roundtrip. The application currently uses pickle only for generated map caching; it has no full campaign save/load command. A full `world` pickle fails with a recursion error in the simulation object graph, so a resumable campaign save is still a separate persistence task. The Phase 4 save/load continuation criterion is limited to the scenario record until that task is implemented.
