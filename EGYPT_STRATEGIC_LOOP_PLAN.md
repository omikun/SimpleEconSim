# Egypt strategic loop plan

## Goal

Make Guided Egypt compelling at the scale of a state. Each major decision should advance a visible plan, change a district or strategic route, invite a rival response, and create a new decision. The player should be able to say what kind of Egypt they tried to build and what that cost households, districts, and creditors. Personal accounts may clarify consequences later; they are not the primary game loop in this plan.

The campaign remains a historical crisis game, not a territorial expansion game. Its scarce territory is the Nile corridor, its contested assets are food access, revenue, customs, canal passage, political authority, and armed control. The existing 20-turn base horizon, late-crisis extension, 15 outcome IDs, shared simulation, and Guided/Advanced modes remain the starting constraints.

## Playable loop

1. **Choose a national priority and a place.** Fund a food, fiscal, or sovereignty project in a named district or strategic site. The project consumes a major decision and real cash, goods, and labor where appropriate.
2. **See work and effects on the map.** A project has construction or negotiation progress, a completion condition, upkeep, and a visible footprint. It changes actual production, storage, receipts, supply, or control; it never creates a separate shadow economy.
3. **Meet opposition.** Owners, workers, officers, the Caisse, Britain, and France respond according to their existing interests and resources. Responses have costs and can be countered. A project is an opening move in a contest, not a permanent bonus purchased once.
4. **Replan at a short deadline.** The next harvest, 200-unit instalment, creditor reply, naval approach, or district protest tests the chosen plan. The player may reinforce it, change course, or accept a loss. The map and a short turn report explain what changed and why.

### Three project fronts

| Front | First playable project | Visible strategic gain | Opportunity cost and counterplay |
| --- | --- | --- | --- |
| Food security | Repair irrigation or public storage in the Delta or Upper Egypt | A named district produces or retains more actual maize; households' calorie deficits and local unrest respond | Cash and workers are unavailable for the next remittance or defenses; owners may warehouse the extra harvest or merchants may seek export rights |
| Fiscal autonomy | Build an Egyptian customs and tax administration at Alexandria/Cairo, or renegotiate an assigned receipt stream | More of an actual receipt stays under Egyptian control; the Caisse ledger and institutional control show the change | Staffing and oversight cost money; creditors may demand disclosure, collateral, or enforcement; extraction from cultivators must not be presented as a costless alternative |
| Sovereignty | Improve the Alexandria–Tel el Kebir defense line and its paid supply, or secure a canal/diplomatic guarantee | Fortification, troop readiness, route access, and opponent plans change on the strategic map | Arms and upkeep compete with food and debt service; Britain/France react to access and expected intervention cost; civilian risk remains visible |

Projects are investments, not exclusive victory classes. A player may combine them, but the first payment and harvest arrive before all three can be completed. Their effects should be legible even when the final outcome label is unchanged.

## Current seams and constraints

- `scenario_egypt_1877.py` owns the one-major-decision budget, scenario setup, turn phases, and ending evidence. Project actions should enter through its action handler and the same status provenance used by existing actions.
- `scenario_geography.py` already maps Alexandria, the Delta, Cairo, Upper Egypt, Port Said, Ismailia, and Tel el Kebir to a small strategic graph. Some strategic sites share a generated tile; project markers must use their authored site coordinates without pretending they are separate provinces.
- `buildings.py` already has irrigated-farm and granary recipes with physical construction, staffing, and materials. Each currently costs 250, more than Egypt's 235 opening treasury and more than the available cash after reserving the first 200-unit remittance. Audit whether a smaller repair, staged financing, or reuse of an existing building is needed before exposing these recipes as opening choices. Do not grant free output or add an untracked construction currency.
- `scenario_political_economy.py`, `scenario_debt.py`, `scenario_occupation.py`, and `scenario_campaign.py` already own food access, real receipt interception, garrison supply, and battles. Projects must change those systems through explicit hooks and conserved transfers, not copy their totals into a parallel score.
- `worldview_scenario_ui.py` already has three Guided pressure cards and a long scrolling decision list. The project view should be a small selected-plan strip and map overlay; detailed arithmetic stays in tooltips and Analysis. Advanced mode reads the same state.
- The full campaign does not yet have a general mid-run save/load command. Keep project state serializable and avoid making this feature depend on a new save system.

## Phases

### Phase 0 — Set the decision contract and baseline

Write one-page design cards for the three fronts: place, investment, delay, operating cost, actual engine effect, who benefits, who pays, opponent response, and failure mode. Audit a turn-by-turn baseline for food-first, payment-first, historical occupation, and resistance paths. Identify turns with no compelling decision or material feedback. Record opening cash, construction inputs, existing building availability, district food flows, and AI resources. Update `gdd.md` with the strategic loop and mark the campaign's tuned quantities as abstractions.

**Done when:** Each project has a specific causal hook and can plausibly reach its first milestone before a relevant deadline. The audit shows where the current loop stalls. No implementation proceeds on a project whose food, money, or labor source is undefined.

### Phase 1 — Reusable project and map state

Add a small scenario project registry and per-project state: ID, front, target tile/site, sponsor, status, paid inputs, remaining work, staffing/upkeep, effect source, damage/suspension, and event history. Reuse the shared construction model where its materials and costs fit; add only a narrow scenario adapter for repairs or institutions it cannot represent. Commit project costs immediately through real owners and ledgers. Advance progress once per completed turn in a deterministic phase, and apply an effect once on completion. Define repair, cancellation, and occupation handling before a project can be built.

Add a map overlay for planned, active, interrupted, and lost projects; show the affected route or district. Do not change the GPU terrain pipeline or replace the map renderer.

**Done when:** A project can be started, delayed by missing resources, completed, damaged, and inspected from Guided and Advanced without duplicate cash, goods, or effects. The map shows its state, and restart produces the same opening setup.

### Phase 2 — Food-security vertical slice

Implement one affordable, localized irrigation or storage project first. It must alter actual harvest or retained food, then flow through warehouse buying, market access, rations, calorie deficit, arrears, and protest. Give owners or merchants a measured response to increased local supply: offer more, reserve more, export, or bargain, according to price and their holdings. Provide at least one subsequent player response using the existing major-decision budget, such as public purchase, export retention, or a district agreement.

Show the project's effect on the named district and on the route to Cairo. The turn report should separate increased food produced, food privately held, food reaching households, and food used for public relief. More production alone is not a claim that hunger fell.

**Done when:** In a complete opening playthrough, the project can change household food access before or during the low-Nile shock. A contrasting path can conserve cash for the first instalment and show the food cost. The map and report explain why extra grain did or did not reach hungry households.

### Phase 3 — Fiscal autonomy contest

Implement one Alexandria/Cairo revenue project through actual tax/customs records and Caisse assignment rules. Separate building collection capacity from raising tax rates: a better administration may reduce leakage or shift institutional control, but it must not create receipts beyond underlying taxable activity. Give the Caisse a visible, delayed reply tied to the unpaid claim, enforceable agreement, and measured receipts. Let Egypt defend the project, offer terms, or redirect effort; Britain and France use their distinct existing claims and diplomatic constraints.

**Done when:** A payment-first and an autonomy-first route make materially different choices by the first two service windows. Every disputed receipt has a payer, collector, and recipient; the Caisse cannot collect after its claim is cleared or authority expires. A player can explain why a creditor accepted, escalated, or conceded.

### Phase 4 — Sovereignty and route contest

Make one defense or canal-access project affect the existing Alexandria–Port Said–Ismailia–Tel el Kebir–Cairo route and the funded British expedition. Readiness requires upkeep and supply, and damaged works can be repaired. Britain should choose an affordable response from the route and force balance: bargain, blockade, change approach, attack, or withdraw. French support remains a separately funded and authorized choice. Avoid a scripted invasion triggered merely by project completion or default.

**Done when:** The same debt crisis can yield a defended canal, a costly occupation, a negotiated withdrawal, or a concession because of prior investments and opponent resources. The player sees the route consequence before issuing the order. Civilian and military costs remain in the debrief.

### Phase 5 — Guided pacing and strategic presentation

Replace the generic "choose one decision" emphasis with a compact **current plan / next threat / recent consequence** strip. Preserve the three pressure cards and every legal option in the scrolling list. Put project status and control directly on the map; hover or select for inputs, beneficiaries, harmed groups, uncertainty, and the likely opponent response. Use approximate or directional projections where the simulation or AI can vary; do not promise exact future deltas.

Give the player a short turn report only when a material event occurred: project progress or stall, district access change, creditor move, troop movement, or missed obligation. Group routine data in Analysis. No sequence of passive turns should require opening repeated explanatory modals, and no modal should hide a warning or deadline.

The debrief should compare intended plan with built projects, lost works, remaining obligations, territorial and revenue control, household food access, tax burden, dispossession, creditor transfers, and casualties. Existing outcome IDs remain evidence based.

**Done when:** Without opening Analysis, a new player can identify their current project, its next milestone, the next deadline, the strongest rival move, and the main social cost. Switching Guided/Advanced changes presentation only.

### Phase 6 — Balance, playtest, and integration

Replay at least food-first, payment-first, sovereignty-first, historical occupation, organized resistance, and diplomatic compromise paths. Vary at least the low-Nile severity and one initial fiscal condition; a single seed is insufficient to judge balance. Check that each front can create a viable path and that no opening project dominates all conditions. Audit cash/goods conservation, staffing, effect application, claim balances, AI funding, action budget, modal priority, late horizon extension, and all existing endings. Check map overlays with the full renderer.

Conduct a short blind playtest if a player is available. Ask what plan they formed, what changed on the map, what the rival did, and who bore the cost; record the answers rather than assuming the UI communicates them. Track turns with no new opportunity or material feedback. Aim for no more than two consecutive such turns in the curated Guided paths; fix the cause rather than adding arbitrary popups.

**Done when:** The first ten turns have at least two viable plans with different visible effects, the second chapter responds to those investments, and the debrief explains both strategic and social outcomes. All existing scenario paths remain reachable or have an intentional documented replacement.

## Decisions and recommended defaults

1. **Player identity:** Govern Egypt through its current ruling coalition, even after succession. Britain, France, creditors, owners, workers, and officers remain independent actors. This preserves the current campaign and creates opponents without a second playable faction.
2. **Map scope:** Use the five named Egyptian districts and existing strategic sites. Do not add territorial expansion or a literal map of Egypt in this pass.
3. **Project count:** Deliver one complete project per front before adding variants. Competing sites and counterplay are more valuable than a large build menu.
4. **Materials:** Reuse existing food, cash, wood, labor, and buildings where feasible. Add no commodity solely to make a project recipe look historical. If the shared 250-cost recipes cannot serve the opening, author a smaller repair with actual costs and production effects.
5. **Pacing:** Keep one major decision per turn and the current base horizon. Construction advances between decisions; opponent replies and deadlines can interrupt. Avoid mandatory decisions every turn.
6. **Success:** Keep evidence-based endings; show project achievements and social costs as additional outcome evidence, not a new victory-point score. A solvent but extractive state and a sovereign but indebted state should remain distinct.
7. **Theme:** Every gain must identify who owns the resulting output or right, who paid for it, and who can be excluded. A higher harvest, tax receipt, or military strength is not automatically a social good.

## Implementation discipline

Implement and verify one phase at a time, then make a separate commit for that phase after reviewing the diff. Preserve unrelated working-tree changes. The Phase 2 food slice is the first playability checkpoint: if it is not engaging in a short playtest, revise the loop before implementing the other two projects. The plan defines targets, not proof that the finished game will be fun.
