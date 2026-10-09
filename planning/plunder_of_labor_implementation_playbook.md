# Plunder of Labor: implementation playbook

This is the execution companion to [the mechanics design](plunder_of_labor.md). It is written for an implementation agent that needs explicit, small tasks. Finish phases in order. Each phase should be a separate reviewable commit, or split at the numbered substeps where noted. Do not implement the whole catalog of historical mechanisms in one pass. The first complete vertical slice is **commons access → cash obligation → household labor choice → paid work or tenancy → enforceable debt → visible consequences**.

## Scope and non-negotiable rules

- Work in the **main** simulation (`Region`, `Agent`, `micro/region/stepper.py`). `commonweal/` is a separate prototype; leave it untouched.
- Read `agent.md`, this file, and `planning/plunder_of_labor.md` before editing. The repository requires conserved money and goods, file-based commit messages, commits without pushes, and no scripts run from inline strings.
- At the start of each phase, inspect `git status --short`. Do not stage or modify unrelated user work. The `saved_slots/active_slot.json` file often changes during runs; never commit it accidentally. Prefer in-memory test fixtures to a live saved game.
- Use `Agent.id` and `LandPlot.plot_id` as references. Store no second copy of cash, food inventory, employer, or plot ownership. `Agent` uses `__slots__` with `_extra_attrs`; add stable, frequently used fields to slots and initialize them in `Agent.__init__`.
- Use **one** authoritative labor acceptance function and **one** employment mutation function. Existing lists and pointers (`worker.employer`, `firm.employees`) must always agree.
- A new rule is **off by default** unless it is replacing an already active rule. All old worlds and unrelated scenarios should load with sane defaults. If a pickle or slot schema changes, add a migration/default path and a round-trip check.
- Tests should verify behavior and conservation, not merely restate a formula. If an old test expects a mint or automatic arrest, update its assertion and explain the change in the test name/comment.
- Use deterministic tie-breaking (`Agent.id`, `plot_id`) and seeded simulation randomness. No unseeded random choice in law, credit, or enforcement.

## Known call sites and hazards

| Area | Current file and call | Required treatment |
| --- | --- | --- |
| Regional turn | `micro/region/stepper.py:step_economy` | Main ordering authority. It currently forages **before** hiring, then calls `run_labour` and `LaborMobilityScheduler`. |
| Other labor call | `scenarios/modules/capitalism.py:advance_turn` | Also calls the scheduler. Prevent a second decision in the same turn. |
| Firm hiring | `region_labor.py:hire_workers` | Has a reservation wage check but immediately writes employment state. |
| Scheduler hiring | `economy/labor_mobility.py:step_labor_cohort` | Currently hires into the highest wage vacancy without that check. |
| Commons | `foraging.py:forage_tile` | Uses a tile-wide `commons_access` and creates food before labor allocation. |
| Rent and surveys | `land_rent.py:collect_rents`; `enclosure.py:step_enclosure_survey_debts` | Keep one charge per person and turn; do not charge through both legacy and new paths. |
| Workhouse | `workhouse.py:step_workhouse` | Building alone now causes arrest; gruel purchase and credited revenue need conserved counterparties. |
| Law operators | `economy/transformation_graph.py` | `petition_statute_of_laborers` enacts directly; `enforce_vagrancy_decree` runs arrests directly. Later phases must separate petition, law, and execution. |
| Output and snapshots | `region_production.py`, `region_market.py`, `sim_server/sim_server.py:serialize_tile` | Record actual harvest/sale transfers and expose new state as JSON-safe data. |

### Target turn order

Use `micro/region/stepper.py` as the one place that orders these calls. Preserve unrelated trade, ecology, disease, and lifecycle calls in their existing relative order unless a test shows a dependency. Add a comment beside each new insertion:

1. Reset per-turn receipts and compute current prices/yields. Resolve any law proposal whose earliest decision turn has arrived.
2. Assess **this turn's** cash rent and fixed cash tax, and read older debt balances. This must happen **before** labor choice so due cash affects offers. Enclosure during elite planning may add a one-time survey obligation before the scheduler considers newly displaced people.
3. Run existing firm setup/hiring, elite planning, and the scheduler through the shared `evaluate_offer`/`attach_worker` pair. The scheduler executes at most once per region/turn.
4. Forage for people who did not allocate the turn to full wage work. Then produce goods, collect tribute, transfer any valid crop share/lien from **current harvest**, and open market trade.
5. Pay wages and profit distributions. Settle named cash obligations from actual debtor balances, then run the existing percentage tax path. Update rent/arrears logs from the settlement result.
6. Process default petitions and enforcement cases, then lifecycle, workhouse feeding/confinement, health, factions, and telemetry. A newly created case cannot resolve before its `earliest_turn`.

### Shared data vocabulary

Introduce these records only in the phase that first uses them. Put definitions in a small leaf module such as `labor_institutions.py` with no imports from `Region`, `Nation`, `Government`, or server/UI modules. Do not use magic string values scattered across files; define constants or enums there.

| Record | Introduced | Required fields |
| --- | --- | --- |
| `LaborDecision` | 1 | `worker_id`, `firm_id`, `turn`, `accepted`, `reason`, `reservation_wage`, `offered_wage`, `outside_food_estimate`, `cash_due_estimate` |
| `AccessRight` | 2 | `person_id`, `plot_id`, `resource` (`field` or `commons_food` initially), `legal_share`, `usable_share`, `source` |
| `CashObligation` | 2 | `id`, `debtor_id`, `creditor_id`, `origin` (`rent`, `survey`, `cash_tax`, later `advance`), `original_principal`, `balance`, `interest_rate`, `due_turn`, `collateral_plot_id`, `status`, `last_accrued_turn`, `last_settled_turn` |
| `TenancyAgreement` | 3 | `tenant_id`, `landlord_id`, `plot_id`, `type` (`cash_rent` or `crop_share`), `cash_rent`, `crop_share`, `active` |
| `LaborAgreement` | 5 | `worker_id`, `firm_id`, `regime` (`wage` initially), `start_turn`, `term_turns`, `hours`, `pay_mode`, `pay_rate`, `deduction_rule`, `exit_rule`, `active` |
| `EnforcementCase` | 4 | `id`, `kind`, `target_person_id`, `target_plot_id`, `claim_id`, `requested_turn`, `earliest_turn`, `state`, `officer_cost`, `outcome` |

Use a monotonically increasing ID counter per region for obligations and cases. Make only references to `Agent`/`LandPlot` in these records so serialization is straightforward. A `CashObligation` is **not** a second bank loan: existing `Agent.loans` and bank ledgers remain authoritative for bank debt. The new record handles named rent, survey, tax, and crop-advance claims. Existing `company_debt` remains authoritative until a dedicated migration is implemented; show it in the later UI as a separate category rather than duplicating it.

### Minimal acceptance scenario for the whole feature

Construct one deterministic region with a landlord, two cultivators, one employer, one merchant, a customary plot, a food market, and a small government treasury. Run the same weather/price path under four configurations: customary rights; cash tax only; enclosure plus tax; enclosure plus advance/lien. By the final phase, reports must show who kept access, who took paid work or tenancy, each money/food transfer, any enforcement attempt, and what happened to food, debt, output, wages, and unrest. A path with no employer vacancies must be allowed to end in unemployment, migration, or resistance instead of invented jobs.

## Phase 0 — Establish a safe baseline

This is a preparation gate, not a mechanics change.

1. Record the current branch, status, and exact commands that work in this environment. Use the project `venv/bin/python` if system Python lacks dependencies. Do not run a command that writes tracked PNGs or saved slots without checking its effects.
2. Read these functions in order: `step_economy`, `can_forage`, `forage_tile`, `run_labour`, `hire_workers`, `evaluate_worker_reservation_wage`, `step_labor_cohort`, `step_workhouse`, `collect_rents`, `step_enclosure_survey_debts`.
3. Run the existing focused suites: `test_capitalist_propagation.py`, `test_phase1_enclosure_expansions.py`, `test_truck_system_and_scrip.py`, `test_statute_of_laborers.py`, `test_cadastre_shift_serialization.py`. Record existing failures in the commit/report before changing behavior.
4. Create `test_plunder_labor.py` with a reusable small fixture, but add no test that merely checks class construction. First test should reproduce the scheduler bypass of reservation wage and the forage-then-hire double allocation.

**Exit gate:** baseline failures and the two reproducible bugs are documented. Only the new test file is changed.

## Phase 1 — One labor decision and a conserved workhouse

**Goal:** A worker is attached only after an explicit, consistent choice. A workhouse building is capacity, not an arrest order. This phase repairs seams before adding economic features.

### 1.1 Centralize labor choice

1. Add `labor_choice.py` with `evaluate_offer(worker, firm, region, turn) -> LaborDecision` and `attach_worker(worker, firm, turn, decision)`. `evaluate_offer` must be pure: no cash, inventory, employer, or list mutation.
2. Reject offers when the worker is dead, a trader/government/firm/lord, already employed elsewhere, confined, the firm is dead/full, wage is nonpositive, or the firm cannot fund at least one wage. Use the existing `evaluate_worker_reservation_wage` as the starting floor. Until Phase 2, estimate outside food from a valid `assigned_plot_id` and current tenure. Set `reservation = max(0.75 * food_price, base_reservation + 0.5 * food_price * access - min(0.4 * base_reservation, 0.05 * cash_due))`, where `access` is in `[0,1]` and `cash_due` is zero until Phase 2. This is a **tuned game rule**, not a historical estimate. Hunger may affect `cash_due`/outside food estimates but must never cause automatic attachment. Return a reason string from a fixed set (`accepted`, `insufficient_wage`, `no_vacancy`, `unfunded`, `unavailable`).
3. Have `attach_worker` alone update both sides, `hired_at`, `wage`, `shift_hours`, and output. Make it idempotent if the same accepted decision is submitted twice. A worker may reject a low offer and consider a higher one in the same turn; stop evaluating only after attachment.
4. Replace direct hiring mutations in `region_labor.hire_workers` and `LaborMobilityScheduler.step_labor_cohort` with this pair. Preserve the scheduler's cohort and emergency ordering, but **not** its unconditional acceptance. Count rejected offers in a small turn log for UI/testing.
5. Add `region.labor_scheduler_last_turn`, set **at the end of the scheduler call**, and make a second scheduler call on that region/turn a no-op. Keep `scenarios/modules/capitalism.py` as a fallback for stand-alone scenario use, guarded by this marker. `run_labour` still runs once in the region step and may evaluate offers before the scheduler; it must call the same acceptance function. Neither candidate finder owns a separate acceptance rule.

### 1.2 Allocate foraging and paid work once

1. In `micro/region/stepper.py`, move `forage_tile` to after all labor matching and before `region_production.produce`. For Phase 1, use a simple whole-turn choice: employed workers cannot also forage; unemployed eligible workers can. The later work-hours model may permit a measured partial day.
2. Check whether any other path adds forage before or after this point. Preserve the wilderness homesteader branch in `foraging.py`.
3. Add a test with a valid commons worker who accepts a job: one turn must not award both full forage and full wage work. A rejected worker should still forage when eligible.

### 1.3 Repair workhouse activation and conservation

1. Add `region.vagrancy_law_active = False` and `region.workhouse_last_step_turn = -1` in `micro/region/core.py`. `step_workhouse` may feed existing inmates, but it may arrest a new person only if the law is active **and** a police/constable capacity exists. Use current `police_employed` or garrison data; do not invent officers. Cap new arrests to funded capacity. A lawless region or a workhouse with no enforcement capacity arrests nobody.
2. Change `enforce_vagrancy_decree` in `economy/transformation_graph.py` to request/set the law, then let the regional workhouse step process arrests once. Do not call `step_workhouse` a second time from the operator. Phase 4 replaces direct elite activation with a petition, so keep this interim change small.
3. When gruel comes from government inventory, transfer the exact food units to inmates. If government buys food, find a seller who actually holds `Goods.food`, transfer seller food to government/inmate, and transfer government cash to that seller. If nobody can sell, inmates remain unfed. Never reduce government cash while creating food from nowhere.
4. Do not credit treasury cash merely because confined people worked. For now, record `forced_labor_hours`/output as a noncash metric with **zero sale revenue**. A later real buyer/sale can create revenue by cash transfer. Preserve starvation/riot behavior.
5. Change the existing workhouse tests to set a law and officers when expecting arrest, and assert cash/food sums across government, sellers, and inmates. Replace the old `3 × 1.50` minted revenue expectation with zero cash revenue until a buyer pays. Add a no-law/no-police test and a same-turn idempotence test.

**Phase 1 gate:** focused tests pass; the two hiring paths agree; no worker has both full forage and wage work in one turn; workhouse cash and food are conserved. Run at least one short `SimServer` turn path with a firm and one with a workhouse. Do not move on if the existing `test_capitalist_propagation` fixture must be weakened to allow below-reservation hiring; adjust its wage/food setup instead.

## Phase 2 — Household access and named cash obligations

**Goal:** The game knows *which* person can use *which* resource, and *why* they need cash. Treat each `Agent` as one household decision unit for this first slice; dependents can affect its need later. Do not create a separate household population.

### 2.1 Named access rights

1. Add `Region.access_rights: dict[int, list[AccessRight]]` and an initializer in a new `livelihood_access.py`. At world creation, run it **after** `micro/region/core.py` assigns `tenant_ids` and `assigned_plot_id`. Give each named tenant a `field` and `commons_food` right on the assigned plot. Do not infer a right merely from being present on the tile or from lacking an eviction memory. `LandPlot.tenant_ids` remains the occupancy list. Access records are the right to use a resource, not title. Check both lists for consistency after every change.
2. Add `effective_access(person, region, resource) -> float` in that module. For `commons_food`, sum `plot.fraction × tenure_weight × usable_share` over the person's rights, then clamp to `[0,1]`; tenure weights are FEUDAL/COMMONS `1`, LEASEHOLD `0.5`, ENCLOSED `0`. Use `legal_share` instead of `usable_share` for an official-claim query. If a legacy loaded region has no new records, lazily seed from existing `tenant_ids` and `assigned_plot_id` once; do not repeatedly recreate lost rights. Wilderness foraging retains its existing separate rules.
3. Change `foraging.can_forage`/`forage_tile` to use that helper. In this phase, `commons_food` is the only new gatherable good; keep fuelwood, water, and fishing as named future resource types without pretending they have physical inventories yet.
4. Change `execute_enclosure` so it modifies rights only for holders of the target plot; it must not select the first `N` arbitrary serfs. Make loss of legal right and loss of usable access separate fields. Apply memory/grievance to the affected IDs, and record a small event with old/new access.
5. Check birth, death, move, and plot reassignment paths. Add a right on a valid assignment; remove/deactivate rights on death or eviction; do not let an unrelated person inherit a right solely because they live on the same tile. At this phase, support a deterministic explicit transfer helper rather than a broad inheritance rewrite.

### 2.2 Cash obligations without duplicate billing

1. Add `Region.cash_obligations: list[CashObligation]` and an ID counter. Add helpers `assess_obligation`, `due_cash_for(person_id, turn)`, `settle_obligations(region, turn)`, and `cancel_obligation`. `assess` cannot move cash. Accrue interest at most once per turn by `last_accrued_turn`; `settle` may move cash only debtor → named creditor, bounded by actual debtor cash and the outstanding balance. Set `last_settled_turn` to prevent a second collection in the same turn. A partial payment reduces `balance`; it does not create a fresh obligation.
2. In `land_rent.py`, split the current `collect_rents` work into `assess_rents(region, turn)` **before labor choice** and a log/summary after `settle_obligations` **after wages**. Assess this turn's rent for `plot.tenant_ids` only. Do not also run the old direct deduction. Keep the existing pastoral conversion trigger separate. Keep arrears attached to the tenant's obligation, not only a plot-wide number.
3. In `enclosure.py`, issue one survey obligation per named tenant at enclosure. Migrate the old `enclosure_survey_debts` list into the new ledger on load or keep a read-only adapter; never charge from both. Do not create a foreclosure in this phase merely because the due date passed; Phase 3 will process it through a case.
4. Add an optional fixed `cash_tax_per_person` policy, default `0`. Assess it once per turn for eligible adults with government as creditor. This is separate from the existing percentage income tax in `region_finance.py`; make that distinction explicit in names, UI, and tests.
5. In `labor_choice.evaluate_offer`, read `effective_access` and `due_cash_for` to estimate the outside livelihood. Use the bounded reservation formula from Phase 1 with actual access and cash due. The obligation changes the worker's choice; it is **not** a command to take a job. Keep the choice pure. Test four cases at the same wage/food price: secure/no debt, secure/high debt, landless/no debt, landless/high debt. Confirm that higher access never lowers reservation and higher due cash never raises it.
6. Add JSON-safe summaries to `SimServer.serialize_tile`: affected household count, active obligations by origin, due this turn, paid, and arrears. Correct the existing `survey_debts` serializer key mismatch (`agent_id` versus actual `tenant_id`) while changing this seam.

**Phase 2 gate:** an enclosure affects only target plot holders; two residents on different plots can have different forage outcomes on the same tile; rent/tax/survey produce named receivables and actual paired cash transfers; a high cash due can change wage acceptance without creating money or a job. Test legacy world loading/round-trip with absent new fields.

## Phase 3 — Advances, liens, and tenancy/sharecropping

**Goal:** A distressed cultivator can stay on the land under new terms, sell a crop under a lien, repay, renegotiate, or face a delayed foreclosure. Do not collapse these into `employer != None`.

### 3.1 Harvest advances and crop receipts

1. Add `offer_advance(lender, cultivator, amount, due_turn, collateral_plot_id)` in `crop_credit.py`. Validate both agents and plot; transfer **actual** cash or named goods immediately from lender to borrower; create exactly one `CashObligation(origin='advance')`. Refuse if lender lacks cash/goods. Record lender, principal, interest rate, and crop/plot collateral.
2. In `region_production.py`, record per-turn production receipts (`person_id`, `good`, `quantity`) when independent cultivators actually produce. Clear receipts at turn start. Do not infer harvest from total inventory; old food in a household's store is not automatically a pledged harvest.
3. Add `settle_crop_lien` between production/tribute and open-market sale in `micro/region/stepper.py`. Transfer at most the pledged share of **this turn's** crop to the creditor, apply the agreed farm gate price to the obligation, and record the cash/goods counterparties. If the contract is a creditor purchase, merchant cash pays cultivator; if it is in-kind debt repayment, reduce debt by the agreed value without minting cash. Choose one contract type explicitly in the record.
4. If there is no harvest, there is no seized crop. Accrue debt once, then handle a missed payment in the next case step. Reject negative balances, duplicate lien settlement, or taking more goods than produced.

### 3.2 Tenancy as its own regime

1. Add `TenancyAgreement` to a plot or region registry. The first two types are `cash_rent` and `crop_share`; use one active agreement per tenant/plot. Tenancy keeps `worker.employer is None` and the tenant in `plot.tenant_ids`.
2. For `cash_rent`, use the Phase 2 obligation path. For `crop_share`, transfer a documented fraction of current harvest to the landlord **before market sale**; do not charge cash rent as well unless the agreement explicitly contains both terms.
3. Update `social_class.py` and region summaries to count tenants/sharecroppers separately from wage workers. A person who takes occasional wage work while retaining a tenancy can have both a current job and an underlying tenure status; report hours by activity rather than overwriting their land relationship.

### 3.3 Default and foreclosure as cases

1. Replace the survey-fee deadline's immediate eviction with a pending `EnforcementCase(kind='foreclosure')`. Minimum delay: case is created on/after default turn, can resolve no earlier than the next turn. Reuse the same case flow for advance defaults. No duplicate case for the same live claim.
2. Resolve a case through these ordered checks: debt paid/canceled → case closed; debtor and creditor still exist → proceed; eligible defense/renegotiation → update terms; valid authority and funded enforcement → transfer the named claim/rights; otherwise pending or failed. Until Phase 4, use existing police/garrison fields for the capacity check.
3. On a successful eviction, update `plot.tenant_ids`, `assigned_plot_id`, `AccessRight`, social class, memories, and event log together. An auction moves title only if an actual buyer pays the actual recipient. A failed auction does not pretend to transfer cash. Preserve the tenant's or lender's remaining debt rights explicitly.
4. Add tests for full repayment, partial repayment, zero crop, good harvest, failed enforcement, successful eviction, and a valid sharecropping path. Assert balance of every cash/good transfer.

**Phase 3 gate:** the same bad harvest can yield different outcomes under different credit terms; a sharecropper is never counted solely as a wage employee; lien transfer never exceeds the pledged current crop; a default does not evict someone on the same turn it arises.

## Phase 4 — Petition, law, adjudication, and enforcement

**Goal:** A capitalist can seek state power but cannot personally toggle public law. A government can legislate, yet actual access changes only where it has enforceable reach.

### 4.1 Separate political stages

1. Add a small `LaborLawState` on nation/region with statuses `absent`, `proposed`, `enacted`, `suspended`, `repealed`. Implement only three new or migrated rules first: `vagrancy`, `gathering_restriction`, `quit_penalty`. Existing wage cap can use the same petition queue, but preserve the government player's direct policy command as an explicit enactment action.
2. Add `submit_law_petition(sponsor, target, law, fee, turn)`. Transfer the fee to the named government account only if the petition is valid and can be filed; failed prerequisites transfer nothing. The call creates a proposal, not a law or an arrest.
3. Change the elite transformation operators `petition_statute_of_laborers` and `enforce_vagrancy_decree` to submit petitions. Rename UI text where necessary so it does not promise immediate effect. The sovereign/player action may enact or reject at the next decision window. AI governments should use one deterministic, testable decision function based on ruling faction/legitimacy and cost; never have a petition automatically succeed merely because the sponsor can pay.
4. Create a dedicated `step_labor_laws(region, turn)` call **once** in the regional turn. Law passage updates legal flags; it does not directly mutate household rights, employment, or confinement.

### 4.2 Fund and resolve specific cases

1. Use `EnforcementCase` for gathering fines, contract/quit penalties, vagrancy hearings, and foreclosure. Cases name one target and one claim. Add precondition, creation turn, earliest resolution turn, officer cost, and outcome. Existing workhouse confinement must be initiated by a resolved vagrancy case; the Phase 1 direct arrest path should become a case creator.
2. An officer action requires a real police/garrison capacity and budget. For civilian enforcement, choose a deterministic set of eligible living local agents as paid constables (exclude the target and creditor), capped by `police_employed`; transfer the case cost from the government to these agents before resolution. A paid garrison may use its existing military payroll instead of a second payment, but the case must point to that funded unit. If no named payee or funded unit exists, do not enforce. One officer cannot resolve unlimited cases in a turn. A case may fail due to absent target, weak reach, local resistance, or repeal.
3. Check `legal_share` separately from `usable_share`: enactment may remove a legal right; a failed fence/patrol may leave actual gathering available. Conversely, illegal private destruction can remove actual access while legal right survives and creates a remedy claim. Record both states.
4. A worker with a quit penalty may still try to leave. Resolve their exit into one of: lawful exit, employer settlement, unpaid fine/claim, escape, or failed exit. Never set `employer` to the old firm solely because a law exists; the outcome must follow a case and physical reach.
5. Add remedies: repeal/rights restoration stops future cases; paid legal aid may contest pending cases; debt cancellation closes linked cases. Reopening de facto access may require a later enforcement action. Keep the first version deterministic and transparent in the event log.

**Phase 4 gate:** employer petition alone changes no law; enacted but unfunded gathering restriction changes legal status but can fail to stop actual forage; workhouse confinement and quit penalties have a named case, cost/capacity, and outcome; one case resolves at most once. Include tests for repeal during a pending case and no officers available.

## Phase 5 — Workplace terms, discipline, and real productivity

**Goal:** Once a person accepts wage work, the employer can alter terms and intensity, but hours, output, health, pay, and net profit remain separate observable quantities.

1. Create a `LaborAgreement` when `attach_worker` succeeds. For legacy workers already attached at load, create a default wage agreement with existing `firm.wage` and `firm.shift_hours` once. Keep `firm.employees` and `worker.employer` as the operational relationship; the agreement explains its terms and exit rule.
2. In `labor_contract.py`, add explicit `pace`, `piece_rate`, `quota`, and `deduction_rule` fields to the agreement or its terms object. Start with wage per turn and one optional piece-rate mode. Do not let a firm switch a worker's contract without an event and an acceptance, law, or enforceable penalty.
3. Route output through one bounded work-effort calculation using actual attendance, hours, pace, nutrition, machinery, and fatigue. Keep `calculate_shift_multiplier` as the baseline at pace `1.0`. Above a threshold, extra hours/pace have diminishing output while fatigue/injury rise. Avoid adding output from an accounting-only `surplus_value` function.
4. In `region_finance.pay_wages`, pay the cash/scrip amount promised by the active agreement and record actual payment, withheld amount, and authorized deductions separately. Scrip and `company_debt` are existing systems; integrate their balances without treating scrip as sovereign cash. Enforce the Truck Act before a pay mode is selected.
5. Employer guard/overseer spending must transfer cash to named workers or suppliers. Record `gross_sales`, `cash_wages`, `input_cost`, `safety_cost`, `guard_cost`, `credit_cost`, and `net_profit`. `record_surplus_value` may remain a separate analytical measure; label it differently from realized cash profit.
6. Tie fatigue/injury to existing `alienation.py`, `labor_resistance.py`, and health logs, and let a severe workplace lower next-turn capacity or trigger absence/strike. No blanket productivity multiplier with only a positive side.
7. Add tests showing: 12-hour output exceeds 8-hour output under healthy conditions but not proportionally; extreme pace can lower future output; an unpaid wage remains an employer liability; piece-rate pay follows actual units; legal workday and Truck Act bind; guard payment has a recipient; profit falls when enforcement costs exceed extra output.

**Phase 5 gate:** all pay and goods paths conserve; the UI can separately report hours, units, injury, nominal pay, realized pay, deductions, and net firm profit. Existing wage cap, strike, and scrip tests still pass after updating their fixture terms.

## Phase 6 — AI, UI, scenario, and balance integration

**Goal:** The entire causal chain is visible and used by owners/governments only when it makes sense economically and politically.

### 6.1 AI choices

1. Extend `economy/capitalist_planner.py` with options in this order: raise wage/shorten terms, buy machinery, offer an advance or tenancy, petition for legal pressure, fund permitted enforcement, recruit elsewhere, do nothing. Estimate **net** return after credit risk, guards, unrest, flight, and output disruption. Use existing expected commodity prices and pending capacity to avoid assuming every cotton expansion is profitable.
2. Add a simple AI government decision helper for petition approval and enforcement funding. It must check treasury, governing coalition/legitimacy, and law status. It must be possible for a wealthy employer to lose a petition or for the state to enact a law it cannot enforce.
3. Add household alternatives to the decision log: accept wage, remain on land, tenancy, borrow, seek relief, migrate, or dispute. Implement only alternatives for which the existing sim has an actual operation. Never show an option in the UI that has no simulation effect.

### 6.2 Inspectable output and commands

1. Add a bounded per-person timeline of events: access change, obligation assessed/paid, job offer accepted/rejected, contract change, harvest/lien, case result, injury, migration. Each event has IDs and turn. Keep at most a documented recent window in live memory; long archive can be handled separately.
2. Extend `SimServer.serialize_tile` and its citizen entries with: legal/usable food access, current obligation totals by origin, labor regime, real wage after deductions, ability-to-quit state, and recent reasons. Include regional counts for subsistence, tenant/sharecropper, wage, unemployed, and compulsory labor, plus enforcement costs and outcomes. Use plain JSON values, no class instances.
3. Update `web_client/client.js` citizen and cadastre views first. Show a compact "why this household works" breakdown, the named rights/creditors, and a one-turn causal change. Then update desktop `client/desktop/inspect/labor_ui.py` and corresponding legacy panel only if it is actually still used. Keep desktop/web labels consistent.
4. Add authoritative policy commands in `sim_server/protocol.py` and `sim_server/sim_server.py` for the laws the player can enact/repeal, and case/rights actions that the UI exposes. Validate target nation/tile/person ownership and prerequisites server-side. Do not mutate law state directly in JavaScript.

### 6.3 Bounded experiment and performance

1. Add a small deterministic cotton-district scenario/test fixture. Run the same seed and weather under the four configurations in the shared acceptance scenario. Report wage hours, tenant hours, independent food, cotton output, creditor receipts, firm net profit, government costs, evictions, and protest.
2. Exercise a boom followed by a price decline. Make sure owners can stop expanding, lenders can lose money, and households can exit or reorganize where law/force allow. Keep Egypt integration as a separate follow-up after the generic system passes; do not overwrite the bounded 1877 campaign rules during this phase.
3. Add an audit function for the new mechanics: total cash before/after transfers, physical goods before/after transfers plus explicit production/consumption, no negative inventories, no duplicate settlements/cases, `worker.employer` ↔ `firm.employees` consistency, access share bounds, and one active tenancy per tenant/plot. Check JSON serialization and one pickled world round-trip.
4. Run focused suites, then a 30-turn simulation sanity run. Only run a longer run if a concrete stability risk remains. Confirm the scheduler still meets its existing subsecond cohort target at representative population size.

**Phase 6 gate:** each policy pathway has a readable person-level explanation and conserved transfers; the four treatments produce meaningfully different outcomes; no AI action bypasses state law or a household's labor decision; both web and desktop show the same causal status; no unrelated scenario or save regression.

## Coverage of the full mechanism catalog

The six phases above deliver a **complete first causal slice**, not every row of the mechanics catalog. After Phase 6 passes, implement the remaining rows as small follow-up tickets in this order. Each ticket must state: initiating actor, prerequisite, named target, exact transfer or state change, enforcement path, counteraction, UI explanation, and a conservation test. Do not add several untested policies behind one generic "coercion" number.

| Mechanisms from the design | First implementation location | Follow-up after the core slice |
| --- | --- | --- |
| Enclosure, individual title, rent conversion, gathering restrictions | Phases 2–4 | Title registry and compensation; distinct rights for wood, water, grazing and fish |
| Irrigation/water control, export crop conversion, destruction/eviction, conquest | Existing land/conquest systems plus Phase 6 ledger | One project/case per changed canal, crop plot, burned stock, or seized territory; record supplies, casualties, and restoration |
| Cash tax, survey/license fees, harvest advance, crop lien | Phases 2–3 | Add license-specific rules and differentiated tax exemptions only after the common obligation ledger is stable |
| Company housing/store/scrip, monopoly procurement, essential-goods dependency, work-conditioned relief | Existing scrip plus Phase 5 accounting | Add housing as a named asset; price cartels and alternate buyers; model each newly purchased essential as a real good; gate relief with actual food stock |
| Debt secured by service, quit penalties, vagrancy/pass rules, wage ceiling | Phases 1, 3–4 | Add pass and settlement boundaries across tiles; ensure a debt judgment does not silently reattach an escaped worker |
| Employer no-poaching, recruitment fraud/fees/document seizure, property/school/occupation exclusion | After Phase 6 | Separate tickets: cartel agreement and rival bids; recruiter contract and disputed charge; group-specific legal eligibility with a court remedy |
| Workhouse, corvée, penal leasing, enslavement, compulsory cultivation/quotas | Existing operators plus Phases 1 and 4 workhouse/case rules | Give every regime its own custody, legal status, food, output, exit, mortality, and recipient ledger; add one regime at a time |
| Hours, pace, piece rates, quotas, surveillance, fines, withheld pay, machinery | Phase 5 | Add specialized workplace practices only when actual production and pay flows support them |
| Child/family labor and gender wage segmentation, migrant labor/strikebreakers, false accounting | After Phase 6 | Separate tickets for dependent care/schooling, funded travel and recruitment, and contestable employer books |

**Historical and balancing guard:** these tickets are possible mechanisms, not a universal sequence or a claim that every capitalist prefers coercion. Add a mechanism only when the player can see its benefit, cost, affected people, and an alternative response. Refer to the source links in the design document for historical grounding; keep numerical coefficients labeled as game tuning.

## Repeatable verification commands

Run from `/Users/sli/Code`; use the project interpreter. These commands are examples for the agent to record in its phase report, not permission to skip a failing gate:

```bash
venv/bin/python -m unittest test_plunder_labor
venv/bin/python -m unittest test_capitalist_propagation test_phase1_enclosure_expansions test_truck_system_and_scrip test_statute_of_laborers test_cadastre_shift_serialization
git diff --check
git status --short
```

For a short economy run, use the project's existing 30-turn driver only after checking whether it writes images or save files. Compare `git status --short` before and after, and stage only files intentionally changed for the phase. Do not discard user changes to make the status look clean.

## Definition of done for every phase

The implementation agent's report for a phase must include: changed files; the exact causal rule added or replaced; tests run and results; a one-turn example with before/after rights, cash, food, work, or case status; remaining limitations; and the commit ID. If a gate fails, fix it before starting the next phase. Do not hide an unmodeled mechanism behind a generic percentage or a narrative event.
