# Plunder of Labor: profit driven AI and visible consequences

## Goal and scope

Give firms, landlords, creditors, households, and governments distinct decisions. A household with a workable livelihood should usually prefer to keep it unless a job offers a better *reliable* life. An employer wants the lowest **feasible total cost per saleable unit**, which can mean better pay, a machine, a lease, a political petition, or contraction. When profits are squeezed, owners may try to change households' alternatives or their bargaining power. They must pay for the attempt, can fail, and cannot enact law themselves. The player should be able to follow a decision from motive through target, legal stage, household response, and realized outcome.

This extends [the mechanism design](plunder_of_labor.md) and [the implementation playbook](plunder_of_labor_implementation_playbook.md). The existing playbook calls the implemented work a **first causal slice**. Do not assume every mechanism in the design catalog has an executable operation. In particular, a narrative event must never claim a destroyed farm, pass arrest, document seizure, or restored right unless the simulation actually changed the named asset, case, or right.

## What exists today, and what the AI lacks

| Path | Existing engine seam | AI / UI work needed |
| --- | --- | --- |
| Wage offers and hiring | `region_labor.py`, `economy/labor_mobility.py`, `labor_choice.evaluate_offer` and `attach_worker` | Have the owner select a wage against expected output and payroll; preserve `evaluate_offer` as the one acceptance gate. Show rejected offers and the outside option. |
| Commons, enclosure, rent, cash tax | `livelihood_access.py`, `enclosure.py`, `land_rent.py`, `economy/transformation_graph.py`, `micro/region/stepper.py` | Choose named parcels and households, price survey/enforcement and food/output losses, show legal and usable access separately. Cash tax is a **government** policy, never a private owner command. |
| Harvest advances, liens, tenancy | `crop_credit.offer_advance`, `create_tenancy_agreement`, lien/share settlement | Add owner/creditor candidate builders, an actual household acceptance path, default/collection risk, and named creditor receipts. Existing elite planner does not call these APIs. |
| Public labor laws | `labor_laws.submit_law_petition`, `decide_labor_laws`, `labor_cases.py`, `workhouse.py` | Replace the planner's first-feasible petition behavior with a priced petition candidate. Replace the current government approval threshold with a separate political decision. Show petition → vote/decision → funded case → outcome. Player law commands already exist in `sim_server/sim_server.py`. |
| Work terms and scrip | `labor_contract.py`, `region_finance.py`, `labor_resistance.py` | Model hours/pace, cash versus scrip, deductions, fatigue, injuries, strikes, and effective pay in the same comparison. Never count an unpaid wage as a cost saving without recording the worker's claim. |
| Machinery, trade, captive regimes | `economy/transformation_graph.py`, `economy/capitalist_planner.py` | Compare investment and trade on the same horizon as labor strategies. Captive/conquest operators must retain their existing scenario, legal, and capacity prerequisites; they are not a generic firm option. |
| Accounting and player inspection | `economy/true_cost_ledger.py`, `sim_server/sim_server.py`, `web_client/client.js`, `client/desktop/inspect/labor_ui.py` | Build complete recent operating statements, strategy records, and causal UI. Current web view shows laws, cases, worker claims/access, and recent offers, but not owner motive, alternatives, or observed return. Desktop labor panel chiefly shows aggregate charts. |

The current `EliteCapitalistPlanner.plan_and_execute_elite` returns after the first successful action (luxury purchase, trade, law petition, lord operation, machinery, then investment). `evaluate_class_legislation` may submit an affordable petition without measuring the firm's profit shortfall. Existing `region_labor.adjust_wages` changes pay using tightness/cash heuristics, and elite expansion raises a company's wage and workforce cap without a realized P&L comparison. A new strategy planner must own deliberate employer wage/contract changes; the existing wage adjustment may remain a safety backstop only if it cannot overwrite the chosen strategy in the same turn.

`TrueCostLedger` reports nominal and social cost estimates, but its production stage values are not by themselves a settled cash operating statement. Verify every sales and payroll posting before using them to trigger decisions. Surplus value, inventory valuation, owner equity injections, and dividends are not spendable profit. Record the distinction in the UI.

## Decision model

### Household outside option

For each real person, forecast one turn ahead using current **usable** plot/commons yield, stored food, crop sale proceeds, craft/informal work where executable, tenancy terms, cash due, food prices, care/rest time, and the chance of a harvest or wage payment. Compare this with each funded vacancy's expected *cash equivalent* after deductions, hours, food/transport cost, injury/quit risk, and payment reliability. Secure subsistence raises the value of declining a poor offer; it does not ban high wage work. Hunger or debt changes the feasible options and urgency, not the person's innate willingness to be deceived. Literacy can affect contract information or dispute success only through an explicit rule with a remedy.

Use `labor_choice.evaluate_offer` for final employment acceptance. Extend its input/decision record rather than creating another hiring gate. For tenancy/advance, add separate proposal and acceptance results before calling the existing creation/transfer APIs; do not silently enroll a tenant or borrower. Only include migration, relief, trade, or resistance as candidate choices where a real simulation operation is reachable. If no funded job exists, pressure can produce unemployment, tenancy, flight, protest, or hunger; it cannot create an employee.

### Owner pressure, alternatives, and objective

At the end of each settled turn, keep a rolling 3–5 turn record per company: sold revenue, output, unsold stock, actual wage cash/scrip liability, inputs, rent, tax, interest, repairs, petitions, advances and recoveries, guards/case contributions, and cash runway in payrolls. A firm is under pressure if its rolling operating margin is below its required return, cash runway is short, or funded vacancies constrain profitable output. Falling commodity prices and unsold inventory are distinct from labor scarcity. Compare price against **probable sales**, not production alone.

At the next owner planning window, enumerate feasible strategies and a no-action baseline. Over a bounded 2–4 turn horizon, estimate for candidate `a`:

`Δ owner value(a) = discounted[Δ expected sales receipts + Δ rents/credit receipts − Δ wages − Δ inputs/capital − Δ petition/survey/enforcement − Δ defaults/turnover/disruption] − failure risk − liquidity cost`.

Use company cash profit for a company's payroll strategy; use the landlord's rent/land value and the creditor's actual recovery for their choices. When the same owner controls two entities, an internal transfer is not new wealth. Use net output per hour and likely fill rate: the smallest posted wage may cost more through vacancies, fatigue, illness, quality loss, and strike. Report assumptions as forecasts and later compare them with actual results; do not call a forecast an observed saving.

Candidate families, all run through existing legal/action entry points:

1. **Market response:** raise or lower the wage within law and worker acceptance, improve terms, change staffing or shift/pace, maintain or buy machinery, import inputs/recruit through an actual route, sell stock, contract, close, or wait. If there is no saleable demand, contraction may win.
2. **Control the independent option:** as a qualified lord/holder, seek enclosure of a named plot, use an existing rent claim, or offer a lease/share agreement. Count lost food production, survey cost, enforcement chance, and worker migration. A firm with no land rights cannot perform this itself.
3. **Creditor path:** make a funded harvest advance to an eligible cultivator on a real plot, possibly with a crop lien. Price repayment and default, not face value; a loan disbursement is a cash outflow. A borrower can decline, repay, dispute, or default under the implemented rules.
4. **Political path:** pay to petition for wage cap, gathering restriction, quit penalty, or vagrancy; wait for an independent state decision. Value the chance of enactment **and** the chance of funded enforcement. A petition by itself changes neither law nor physical access.
5. **Legally gated force/captive regimes:** only expose an existing transformation operator when its historical/scenario/authority and target preconditions hold. Estimate military/upkeep, mortality, resistance, output disruption, and diplomatic/political cost. New mechanisms from the design catalog require their own engine ticket before the planner may select them.

For each candidate, record `feasible`, a specific rejection reason, expected incremental value, target IDs, cash required now, expected horizon, and main uncertainty. Pick the greatest positive risk-adjusted incremental value, with deterministic ID tie breaking. Execute at most one **major** institutional/land action per owner per planning interval. Ordinary production and payroll continue. Add a cooldown for repeated failed petitions/cases and hysteresis around the margin trigger. If every candidate is negative, wait or contract. A profitable firm may still prefer an opportunistic action if its expected gain is positive, but a low margin alone is never a license to use force.

### Government is a separate actor

The state receives petitions and can originate tax, enforcement funding, or reform policy. It ranks public revenue, governing coalition support, legitimacy, food security/unrest, court capacity, and treasury cost according to its regime/traits. A fee may influence access or corruption only through a recorded rule; it must not mechanically guarantee approval. The state may reject a rich sponsor, pass a law that later lacks officers, fund a particular case, or repeal/reform in response to harm. A government-controlled player command remains authoritative and should use the same validation and event schema as an AI decision.

Keep these stages separate: `proposed → decided → in force on paper → case funded → case resolved → physical access/worker state changed`. Rejection, delay, appeal, weak enforcement, and de facto access are valid outcomes. Tying owner pressure directly to `set_labor_law` or direct arrest would bypass the simulation's political conflict.

### Order, observation, and feedback

Keep the existing beginning-of-turn law decision, rent/tax assessment, labor match, work, sales, and settlement order in `micro/region/stepper.py`. Read **last turn's sealed** financial record when planning; never use current unsettled production as realized profit. After a new strategy executes, schedule its first material effect at a defined stage: wage offers can reach the later mobility pass this turn, but the earlier `run_labour` pass has already happened; a petition is considered next turn; debt/liens settle at their normal due/harvest stage. Record this lag in the decision. Observe realized effects for 2–4 turns and update simple local success estimates (fill rate, petition acceptance, lien recovery, enforcement success) with bounded smoothing. Do not use an opaque global reinforcement learner. Evaluation can be deterministic and cheap at tile scale.

## Data contract and UI narrative

Use stable IDs and plain JSON projections of authoritative simulation records, not a second mutable economy. Proposed records:

| Record | Minimum fields |
| --- | --- |
| `FirmOperatingStatement` | turn, firm/owner/tile IDs, sold revenue, units sold, produced/unsold units, wages paid and owed, inputs, rent/tax/interest, strategy/enforcement expense, cash profit, margin, runway; link to social cost audit separately |
| `LaborStrategyDecision` | ID, turn, actor role/ID, target firm/plot/person/case IDs, pressure trigger, baseline and chosen forecast, runner-up, rejected alternatives with reasons, legal preconditions, cash budget, expected effect turn, status |
| `HouseholdLivelihoodDecision` | person ID/turn, feasible real paths, usable food estimate, cash due, offer/net pay, reservation/outside estimate, chosen path and reason, linked strategy/rights/claim IDs |
| `GovernmentLawDecision` | petition/law/sponsor IDs, turn, coalition/legitimacy/treasury/capacity inputs, decision and reason, enforcement funding status |
| `MechanismOutcome` | source decision ID, turn, actual state change and transfers, target IDs, appeal/resistance result, observed profit/worker welfare delta; `pending` if too early to measure |

Use a bounded recent event log per tile plus stable references to existing obligation, case, access, and petition IDs. Save/load must preserve pending decisions and outcome windows. The UI reads one server view model so labels and statuses agree across web and desktop. Avoid N×M household-by-candidate simulation: aggregate forecasts for ranking, then a bounded named target set for the selected action. Return a selection count and an explicit `sampled` label when the UI lists only part of a population.

### Player view, with concrete examples

1. **Tile labor pressure card** (web Citizens → Labor & Alienation; desktop selected tile): independent/tenant/wage/compulsory counts; funded vacancies; median offer and reservation; households with cash due; legal versus usable commons access; a small trend for wage hours, food access, firm cash margin, and enforcement spend. A compact status could read: `Cotton price fell 18%; 2 firms below required margin; 6 funded vacancies; 11 households retain usable commons`.
2. **Owner decision card** under each firm/estate: `Mill 17: cash margin −4% over 3 turns; 9/15 jobs filled. Chose petition for wage cap (fee $8; expected +$12 over 3 turns, approval estimate 40%). Higher wage forecast +$9; machine +$5. Petition awaiting government decision.` Show the **cash cost now**, forecast and uncertainty, actual return once observable, and an affordance to inspect the affected owner/plot. If estimates are rough, use ranges or `estimate`, never spurious precision.
3. **Law and case pipeline:** proposed/rejected/enacted labels, sponsor, turn, fee, government's stated reason, number of funded officers, target case, appeal, outcome. A law badge alone must not imply the commons were physically closed. Give `legal access 0%, usable access 60%` a plain explanation such as `ban enacted; no funded patrol reached this plot`.
4. **Household “why this work?” card:** actual food and cash outside option, named bills and creditors, job offer after deductions, hours/pace, accepted/rejected reason, lease/advance status, ability to quit, food/access change, and subsequent response. Example: `T23: survey removed 1/2 gathering access → $3 rent due → refused $2 wage (outside food sufficient) → accepted $4 seasonal offer at T24` only if each linked event occurred.
5. **Outcome timeline:** cards link decision → petition/claim → legal action → enforcement → household choice → output/pay/owner profit. Show short and long effects: immediate wage saving can coexist with later injury, flight, or sales decline. Filters by actor, type, target, and turn; map markers for actual enclosure/case outcomes only. News ticker can announce a significant *verified* event, not a forecast as though completed.

`sim_server.serialize_tile` already exposes worker rights, due cash, claims, recent offers, law status, and case summaries. Add the strategy/operating/outcome projections there, with full selected entity details fetched or included only for that tile. Web updates belong in `web_client/index.html`, `client.js`, and styles; desktop updates belong in `client/desktop/inspect/labor_ui.py` and its active inspect route. Both surfaces should derive wording from the same statuses. Keep player controls beside decisions only for commands the authoritative server can execute, such as existing law enact/repeal. Future accept/reject petition, funding, restitution, or appeals controls require validated server commands and real simulation effects first.

## Implementation phases for a lower skilled coding agent

Each phase is a separate commit after its gate passes. Keep changes in the listed files unless a direct caller requires more. Update this plan when a discovered engine limitation changes the intended behavior. For each commit, report one named example with before/after cash, rights, work, and outcome, plus tests and any remaining coverage gap. Follow `agent.md`: commit message in `tmp/commit_msgN.txt`, commit but do not push.

### Phase 0 — Audit and baseline fixtures

- Read the paths in the table above and map every owner operation to its `can_agent_execute`/real mutation. Classify the design catalog as implemented, partial, or future ticket in one test fixture or small registry; never create a generic “coercion strength” action.
- Add a deterministic small cotton-district fixture with owner, firm, titled/commons households, tenant, creditor, government, and officer; known prices, stocks, wages, and claims. Capture initial cash/goods totals and the existing planner's decisions.
- Gate: fixture loads without new AI, money/goods audit is clean, and the mechanism registry includes the actions the planner will actually invoke.

### Phase 1 — Settled profit and pressure signals

- Add a per-firm, per-turn operating statement near `region_finance.py` / market settlement and seal it after sales and pay. Reconcile it with `TrueCostLedger` nominal fields while preserving their different purpose. Track paid versus owed wages, inventory, actual units sold, owner loans, and enforcement/petition expense without double counting transfers.
- Add a rolling margin, payroll runway, vacancy, and saleability snapshot. Save/load and JSON-serialize only plain values. No strategic behavior changes yet.
- Gate: a wage payment lowers firm cash and raises worker cash exactly once; a cash injection changes runway but not profit; unsold output does not count as sales; scrip and unpaid wages remain liabilities; price crash produces pressure even with abundant workers.

### Phase 2 — Household and proposal forecasts

- Extend `labor_choice.py` with a pure livelihood comparison and explanatory breakdown; make `region_labor.py` and `economy/labor_mobility.py` call the same final offer gate. Add explicit proposal/acceptance helpers for `crop_credit.py` tenancy and advances; only call transfer/contract APIs after acceptance.
- Keep current available alternatives only. Store bounded `HouseholdLivelihoodDecision` records and links to rights/obligations/offer IDs.
- Gate: secure cultivator can reject low pay and take attractive pay; debt/food loss can make a funded offer attractive; no vacancy means no job; a refused advance moves no money and creates no claim.

### Phase 3 — Owner candidate selection

- Create a small strategy module under `economy/` with pure candidate builders and a single scorer. Start with wage/terms, machinery, no action/contraction, tenancy/advance, enclosure/rent, and law petition. Wrap existing operators and APIs; do not copy their mutation logic.
- Call it from `economy/capitalist_planner.py` before the old first-success institutional branches; remove/disable duplicate auto petitions. Keep luxury and merchant activity independent only if their shared cash budget is checked before committing a strategy. Coordinate with `region_labor.adjust_wages` so it cannot immediately reverse chosen pay.
- Add cooldowns, liquidity reserve, target selection, horizon, deterministic tie breaks, and execution result/failed precondition status.
- Gate: low margin does not always choose coercion; profitable wage increase can win; petition loses to a better machine; price collapse can lead to contraction; unaffordable or illegal action is rejected; no owner takes two major actions at once.

### Phase 4 — Government, cases, and learning

- Replace the fixed approval rule in `labor_laws.decide_labor_laws` with a deterministic government choice using treasury, faction support/legitimacy, food/unrest, and expected enforcement budget. Keep `submit_law_petition` and `set_labor_law` as the state transition APIs. Record government reasons and petition outcomes.
- Join existing `labor_cases.py`, `workhouse.py`, access events, and claim settlement to a strategy ID. Add bounded outcome observation to update forecast success rates. Do not generate a success event for an unfunded or failed case.
- Gate: rich sponsor can lose; enacted ban without officer leaves usable access; funded case can fail/appeal; revenue and force costs are paid by named actors; owner learns from repeated failed petitions and tries a different path.

### Phase 5 — Player facing web and desktop UI

- Extend `sim_server/sim_server.py` tile JSON with bounded statements, decisions, government stages, and linked outcomes. Add selected person/firm drilldown without truncating the only relevant target to the first 25 citizen records. Validate missing/dead entity references and old saves.
- Build the tile pressure, owner choice, petition/case pipeline, household reason, and outcome timeline in `web_client/index.html` / `client.js`; then add the same status and drilldown to the active desktop labor inspect UI. Use common wording/status identifiers and sanitized web content. Existing player law controls continue to use server commands.
- Gate: web and desktop show the same real IDs, costs, statuses, and affected people; pending is never shown as completed; forecast versus realized values are visually distinct; a household with no actual offer is not described as having rejected one.

### Phase 6 — Counterfactual balance and stability

- Under the same seed/weather/market path, compare secure commons, cash tax, enclosure, and advance/lien. Then run a boom followed by a cotton price decline. Report wages/hours, independent food, tenancy, funded vacancies, actual cash profit, creditor recovery, government spend, forced cases, movement, and protest, by group and region.
- Tune explicit coefficients in one config: required return, forecast horizon, approval/support thresholds, risk weights, and cooldown. Prefer plausible alternate outcomes over a guaranteed wage labor conversion. Validate save/load, 30-turn sanity run, representative cohort performance, and all money/goods/contract invariants.
- Gate: each mechanism leaves a readable causal trail; profitable voluntary hiring, stable smallholding, indebted tenancy, failed coercion, state refusal, and firm exit all occur in appropriate fixtures; existing scenarios and web/desktop smoke checks pass. Stop testing once these concrete risks are resolved.

## Out of scope until engine operations exist

Separate follow-up tickets are required for burned farms/illegal violence, water/fuelwood/fish restrictions, new title registry and compensation, recruiter fraud and seized papers, pass borders, no-poach cartels, labor quotas, penal leasing, child/family labor, and false books. For each, first implement a named asset/person/claim change, payer and recipient, legal basis, resistance/remedy, and test. Only then add it to the owner candidate registry and UI. The planner may inspect the catalog for future work; it must not select a prose-only mechanism.
