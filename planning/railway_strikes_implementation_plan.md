# Implementation plan: collective strikes to independence politics

Status: ready for sequential implementation, 2026-10-14. Follow the rules in [`agent.md`](../agent.md) and the equations and historical limits in [Railway strikes, collective power, and independence](railway_strikes_and_independence.md). This plan targets the main simulation. Each numbered phase ends in one reviewable commit. Do not push.

## Outcome and scope

First deliver a playable factory strike in the existing `labor_frontier_rivalry` scenario: workers may organize and withhold labor, survive through real support, settle funded demands, and retain organization afterward. Then add a separate, longer colonial railway scenario in which transport disruption, cross-sector alliances, constitutional reform, and independence can emerge. The existing four-district scenario lasts 20 turns and has no staffed railway or colonial authority, so it must not pretend to reproduce 1947–60 Senegal.

The complete player loop is:

`workers form a demand → vote and join a strike → household food/cash determine endurance → actual output or transport falls → employer/state makes a funded response → delivery is checked → organization and political preferences change → a coalition may put constitutional change on the agenda → actors negotiate or contest it`.

No score directly creates sales, goods, money, law, territory, or sovereignty. Every major consequence must pass through an existing or newly implemented operation. Existing labor, military, and market rules remain available to every side under the same constraints.

## Repository map and mandatory seams

| Concern | Current seam | Instruction |
| --- | --- | --- |
| Regional order | `micro/region/stepper.py` runs labor, forage, `step_workplace_resistance`, production, trade, and wages. | Strike participation must be set before production. Review delivered wages after payroll. Ensure the worker makes only one labor/forage choice. |
| Existing workplace strike | `labor_resistance.py:evaluate_strikes` sets every employee striking after a majority vote and can grant an immediate hours concession from a cash check. | Opt the new scenario into the new lifecycle; leave legacy worlds intact until they can be migrated deliberately. Retain sabotage and repair behavior. |
| National strike reaction | `regime.py:step_regime` calls `labor_politics.py:evaluate_uprising_pressure`. | A strike under the new lifecycle may create a response proposal, but must not simultaneously receive a free law/concession from this path. |
| General strike | `agents/resistance/manager.py` sets `Route.is_blocked_by_strike` and can freeze routes. | Specify precedence between the new staffed rail capacity and this broader general strike. An existing full general strike still takes effect. One dispute must not be scored as two unrelated victories. |
| Cargo | `transporter.py:Route` owns pending and in-transit cargo; `sim_engine.py` advances routes after each tile economy. | Never remove cargo to represent delay. `capacity_per_unit` currently affects congestion delay, not units shipped per turn. Add a separate quantitative throughput limit for rail. |
| Scenario state | `scenario_labor_frontier_rivalry.py`, `labor_frontier_labor.py`, `labor_frontier_projection.py`. | Use a feature flag and an authoritative registry reachable by the regional step. Keep the one-major-decision budget for player actions. |
| Desktop and web | `client/desktop/panels/scenario_ui.py`, `client/web/static/client.js`, `web_client/client.js`, `sim_server/sim_server.py:serialize_world`. | Project from one read-only Python function. The served web bundle is `client/web/static/client.js`; update both JS copies if both remain in use. Avoid independent JS estimates of the political score. |
| Political jurisdiction | `nation.py:Nation.transfer_tile` reparents citizenship and tile ownership. | Audit currency, region government, taxes, claims, army, treaties, and existing obligations before reusing it for independence. |

Before editing any phase, inspect `git status --short`. Do not stage unrelated work or generated saved slots. For a new persistent `Agent` attribute, check its `__slots__` and `_extra_attrs`; prefer storing organization and event records in the scenario registry with stable person/firm IDs. Keep a single physical cash or food balance in its existing owner account. Use only seeded choices and stable ID ordering. Write a commit-message file under `tmp/`, then `git commit -F <file>`.

## Shared data contract, established in Phase 1

Use one authoritative `CollectiveRegistry` in the scenario state. Each participating region holds a reference to that registry so the regional step can read it before production. The registry survives pickle round trips. It contains serializable primitives and records keyed by stable IDs; it does not duplicate `Agent` objects or their cash/inventory. The registry must tolerate a dead, migrated, or captured member by resolving IDs against current world state on each turn.

Minimum records:

```text
Organization:
  id, name, jurisdiction_id, member_person_ids, representative_person_ids,
  linked_organization_ids, treasury_agent_id, O, E, founded_turn, status

Demand:
  id, metric, beneficiary_person_ids, baseline, target, weight,
  responsible_party_id, due_turn, accepted_turn, delivered_fraction

Strike:
  id, organization_id, employer_id, region_id, authorized_turn,
  effective_turn, participant_person_ids, status, demand_ids,
  support_periods, hardship_periods, eligible_hours, withheld_hours,
  ended_turn, review_turn, review_applied_event_id

PoliticalIncident (later phase):
  id, event_kind, responsible_authority_id, affected_person_ids,
  evidence, occurred_turn, applied_organization_ids
```

The `treasury_agent_id` points to an existing account holder or a newly registered union account holder whose cash and inventory are included in the usual audits. Do not store a second spendable fund balance in `Organization`. Resolve missing IDs explicitly and close or transfer unserviceable obligations; never silently drop money. IDs must be unique across save/load and independent of Python object identity. Bound historical logs without deleting live claims or IDs needed for idempotence.

Public projection schema, added only as each feature becomes real:

```text
collective_info: {
  organizations: [{id, name, members, O, E}],
  active_strikes: [{id, demands, participants, people_short_of_essentials,
                    endurance_range, affected_output_or_routes, review_turn}],
  settlements: [{strike_id, promised, delivered, review_turn}],
  political_options: [{id, support, coalition_members, status}],
  timeline: [{event_id, turn, cause, observed_effect}]
}
```

Keep numeric internals behind an expandable inspection view. The default card leads with concrete people, food, output, transport, and deadlines.

## Phase 0 — Baseline and turn-order contract

**Deliverable:** a small architecture note in this plan or test comments plus focused regression fixtures; no behavior change.

1. Trace `micro/region/stepper.py`, `sim_engine.py`, `regime.py`, and `agents/resistance/manager.py` for one normal turn. Record when participation can affect production, wage payment, transport posting, general-strike blocking, and the next player decision. Choose this ordering: a vote or accepted offer at turn `t` becomes effective at `t+1`; participation is prepared before that turn's labor/production; settlement review occurs after actual payroll, and political consequences apply once afterward.
2. Run baseline `test_labor_frontier_rivalry.py`, `test_plunder_labor.py`, `test_phase4.py`, and `test_web_client_parity.py`. Keep their results in the commit note. Check `test_coercion_gdd_adherence.py` for national-strike assumptions.
3. Add a fixed-seed fixture that exposes the actual source of the scenario's player/owner cash, food, employment, route state, and tax receipts. It should support later tests without creating stocks during assertions.
4. Document exactly how both `scenario_labor_frontier_rivalry.step_world` and `SimServer.step` invoke the same regional step and scenario-after-engine hook. Keep them behaviorally identical.

**Gate:** fixture produces the same starting IDs and balances through desktop-world and `SimServer` construction. Existing tests pass. Commit only fixture/note changes.

## Phase 1 — Persistent organization and strike lifecycle

**Deliverable:** a feature-gated, authoritative strike record that survives turns and saves. The first visible result is a live organization and a correctly recorded walkout.

1. Add `collective_action.py` for registry, organization, demand, vote, and strike state transitions. Seed one mill-worker organization in `scenario_labor_frontier_rivalry.create_world`; attach the registry reference to the applicable regions. Leave all other scenarios with this feature off.
2. Give the organization named members and representatives from existing people. Authorize a demand package with real baseline, target, weights summing to one, payer, and due date. Record actual votes by eligible member ID. A majority authorizes a strike but does not automatically enroll every employee.
3. Provide `prepare_collective_turn(region, t)` before the regular labor/forage/production decision. At the announced effective turn, set `is_striking` only for participants who choose withholding. Ensure employer lists and worker pointers stay consistent. A person cannot simultaneously work, forage a full shift, and strike.
4. In `labor_resistance.step_workplace_resistance`, skip `evaluate_strikes` only for a region with the new registry enabled; continue sabotage/repair and logging. Avoid rewriting the entire legacy strike system in this phase.
5. In `labor_politics.evaluate_uprising_pressure`, suppress automatic concessions for strikes governed by this registry; preserve other triggers through an explicit branch. Likewise audit `agents/resistance/manager.py` so a new strike is not automatically treated as a second, separately scored organization. Record the reason for any general-strike escalation.
6. End a strike only through an explicit state transition: accepted settlement, participant withdrawal, closure/layoff, or a separately resolved enforcement action. Keep its historical record and event ID after it ends.

**Gate:** one vote produces one strike ID; only joining workers withhold output; unrelated firms keep producing; legacy worlds retain current behavior; save/load and repeated preparation of the same turn cannot create a second strike or score a settlement. Add `test_collective_action.py`; include the existing focused suites. Commit.

## Phase 2 — Household endurance and conserved mutual aid

**Deliverable:** strike duration emerges from household resources and finite support.

1. Add an explicit support transfer from a donor person, union account, or public reserve to a named recipient. Reuse wallet/inventory transfer helpers where possible. Commit the transfer only after the sender has the cash/food. If the recipient is absent or has died, leave resources with the sender and record the failure.
2. At the same point as ordinary subsistence/food consumption, record for each participating person whether essential needs were met. The current `Agent.parent` link is not a shared household budget; do not invent pooled food or count inferred relatives as one household. In this first slice, S/H use participant-person-periods. A later scenario may use participant-household-periods only after implementing actual shared accounts, consumption, and a stable household ID. Worker cash or food received through aid must use the normal consumption path.
3. Record one adult's time spent gathering, provisioning, or caring if that activity is modeled in the scenario; it cannot also fill a mill or rail shift. Do not award community support through an uncosted morale bonus.
4. At strike end calculate observed `P`, `S`, and `H` from real hours and person-periods, with zero-denominator handling. Provide an endurance forecast as a range with the first participant shortfall and number short already. Mark forecasts as estimates because prices, gifts, and future supply may change.
5. Add worker AI choice among continuing, accepting an offer, returning to work, and an available livelihood alternative. It should consider expected real pay, current hunger, mutual aid, access rights, and household dependents. Use the existing labor acceptance logic where feasible; a strike vote does not override household choice forever.

**Gate:** a funded strike lasts longer than an otherwise identical unfunded strike; aid decreases donor stock and increases recipient stock by equal amounts; a shortfall can cause withdrawal without automatically erasing grievance; no participant works and forages a full shift in the same turn; cash and goods audits pass. Commit.

## Phase 3 — Funded settlement, verified delivery, and organization memory

**Deliverable:** a strike can win or lose, and the outcome leaves durable O/E state.

1. Give the employer AI explicit offers: wage, hours, job security, or a supported rights proposal where its authority permits. Extend `labor_frontier_labor._fair_terms` or share its funded-offer helper so direct player support and owner negotiation use the same transfers and worker acceptance. The employer cannot enact a government right. Put public subsidies through the existing one-major-decision rule.
2. A signed offer records payer, beneficiary, due date, real-pay basket, baseline, and target. Continue using actual payroll and legal enforcement paths. Assess the promised terms after two payroll periods, or the demand's declared due date if later. An announced rate that was never paid yields no wage fulfillment.
3. Implement demand fulfillment, V, then the O/E equations from the design document. Compute updates from the same pre-review values. Apply exactly once per `review_applied_event_id`; a later breach is a new incident with its own ID. Track actual loss of representatives/operating resources as X instead of equating X with a crackdown order.
4. Reduce the corresponding grievance only for delivered beneficiaries. Preserve organization, members, and unrelated claims. A failed strike may leave organization growth from actual participation and support but lower confidence.
5. Have owner AI forecast the next several production/sales/payroll turns under settle, wait, replace, and reduce-output options. It sees plausible current information, not future shocks. Score only feasible actions. A low-wage demand is allowed to fail if another employer or subsistence option exists.

**Gate:** the design document's O/E example reproduces `.4436` and `.4780`; delivered and undelivered offers diverge; a successful settlement restores actual work and output; reviewing a saved state twice gives one change; firm/treasury money and goods conserve. Commit.

## Phase 4 — First playable strike and shared UI

**Deliverable:** the existing 20-turn scenario contains a complete, understandable strike decision and aftermath on both desktop and iPad web.

1. Extend `labor_frontier_projection.project` with read-only `collective_info` and contextual actions: inspect worker demands, support a funded settlement, release existing food, protect commons, or refuse a requested coercive measure. Only actions with implemented handlers may be enabled. All player actions still use `labor_frontier_labor.apply_action` and one major decision per turn.
2. Show a single strike situation card with participants, people short of food, affected production/orders, who pays for each offer, and the response deadline. At review show promised versus delivered terms and resulting organization/confidence change. Link event text to observed output and receipts without asserting a precise counterfactual profit.
3. Use that projection in `client/desktop/panels/scenario_ui.py` and server `scenario_info`. Update the served `client/web/static/client.js` and the parallel `web_client/client.js`; update styles in the matching served stylesheets. Both surfaces must show the same action availability and reasons, including the disabled reason after a decision.
4. Adjust pacing so at least one fixed seed exposes a strike early enough to negotiate and review before turn 20. Avoid a forced strike every run. A player who prevents the grievance should see the resulting stable workplace.

**Gate:** test a complete 20-turn scripted run with settlement and one with prolonged conflict; verify iPad-sized layout and desktop display; test shared projection parity, web command budget, event wording, and no hidden enabled action. Existing 30-turn scenario audit passes. Commit. This is the first release milestone.

## Phase 5 — Staffed railway and longer colonial scenario

**Deliverable:** a dedicated railway strike can delay real shipments without creating or deleting cargo.

1. Create a separate scenario ID/template in `scenarios/templates/` and a scenario module parallel to `scenario_labor_frontier_rivalry.py`. Use a fictional federation inspired by French West Africa. Make the time unit explicit (recommended one month per turn) and the campaign long enough for settlement and later political choices. Keep all territories inhabited and all initial cash, food, rolling stock, and jobs explicit.
2. Add a railway workplace with named qualified occupations and hours, an employer/payer, normal capacity, and an account for wages. For each role calculate `min(1, available qualified hours / required hours)`; the minimum required role bounds rail service. Replacements must be recruited, trained if required, arrive, and be paid. A static label such as “replacement crew” creates no capacity.
3. Add a separate per-turn unit throughput limit to the railway `Route`. Do not reinterpret `capacity_per_unit` as that limit. Leave unposted goods with their owner or queue accepted goods under the existing route owner; in-transit cargo keeps its owner and delivery clock. Preserve the current full-freeze behavior when a genuinely separate general strike, blockade, or quarantine applies. Use a reason set or equivalent so lifting one block does not lift another.
4. Make sellers' offers reach buyers only through delivered rail cargo or an explicit slower road route. The current frontier scenario's `settle_markets` can trade directly, so merely drawing a rail line there would not connect strike to sales. Verify the whole chain: staffing → units delivered → paid sales → actual taxes → funded public/military supply. Show inventories and rerouting to avoid claiming every exposed order was lost.
5. Register the new scenario with desktop startup, `SimServer`, and web startup/selection, and add a shared projection. Start with the labor and transport outcome; constitutional politics are introduced later.

**Gate:** 0%, partial, and 100% rail staffing produce distinct delivered quantities; a road route limits loss; queued cargo remains owned across a strike and resumes afterward; no abstract damage charge or ghost tax; save/load, per-currency and physical-goods audits, and both clients pass. Commit.

## Phase 6 — Cross-sector coalitions and colonial preferences

**Deliverable:** organization can become political power, while reform, federation, and independence remain competing choices.

1. Add an explicit colonial authority/jurisdiction relation to the new scenario. Keep a local administration, railway employer, and imperial authority as separate actors and budgets. A domestic private wage dispute has no independence variable by default.
2. Give eligible people or weighted cohorts preferences that sum to one across reform within empire, autonomous federation, and independence. Initialize them from scenario circumstances, not ethnicity. Keep each organization's O/E separate from its members' constitutional preferences.
3. Add invitations/joint committees/party alliances between organizations. An organizer spends time or cash; target members consent or decline. Compute coalition coverage from unique person IDs. Never add faction memberships to get a supporter total, because memberships overlap.
4. Add one-time, attributable political incidents with IDs: a missed accepted commitment, a delivered imperial reform, and a verified repression event. Apply the design document's I equation once to each affected cohort. Attribute private conduct to colonial authority only when a recorded state action or enforceable responsibility connects them.
5. Calculate the mobilization index from deduplicated represented people, O/E, and I. Use it as political agenda strength. The number is not a probability of independence and cannot flip a flag. Provide a full preference breakdown and actual supporters in the UI.

**Gate:** the worked example yields I `.3360` after credible reform and `.5352` after a separate later breach/repression incident; double-processing incidents or overlapping memberships cannot inflate support; a noncolonial strike has no separatist effect; a union can become stronger while independence support falls. Commit.

## Phase 7 — Constitutional bargaining and state response

**Deliverable:** a coalition can make a formal political proposal, and the authority can choose meaningful, funded responses. Independence occurs only through an accepted constitutional settlement or an existing actual conflict path.

1. Add proposal records with sponsors, represented people, option, territorial scope, deadline, negotiation terms, and rule for ratification. Include reform, federation, and independence. Require consent under the scenario's explicit voting/delegate rule and approval of all negotiating authorities where appropriate. Make scope contestable; a railway network spanning multiple territories does not imply one nation-state.
2. Give the authority AI feasible choices: enforce promised rights, negotiate labor terms, fund modernization, reject, seek legal replacement crews, offer autonomy/federation, or negotiate independence. Forecast public cash/runway, trade interruption, security, and mandate support with uncertainty. Charge only actual operations; avoid subtracting losses twice if sales receipts already fell.
3. If sovereignty changes, use `Nation.transfer_tile` only after auditing its currency and government effects. For the first constitutional scenario, use a common currency to limit the migration seam. Transfer jurisdiction with people, organizations, claims, property, existing contracts, debts, and military obligations intact unless the negotiated terms explicitly reassign them. Ensure new state institutions have a funded government account and coherent tax/food rules. Register every new nation in world, scenario, server, and diplomacy state.
4. Create a readable political timeline: what workers asked, what was delivered, which groups joined, what each side proposed, who accepted, and what changed on the map and in the budget. Desktop/web use the same projection and available actions. A proposal can fail and return later under changed conditions.

**Gate:** a victorious workplace strike alone never changes sovereignty; credible reform can hold; an organized cross-sector coalition can secure federation or independence if accepted; a failed negotiation leaves ownership and obligations intact; after independence, wages, hunger, debts, parties, and the union still exist. Audit money/goods and test save/load before/after transfer. Commit. This is the political release milestone.

## Phase 8 — Balance, AI quality, and playtest

**Deliverable:** two or more viable strategic approaches and a player-readable explanation of why each actor changed course.

1. Run matched seeds with organization learning enabled/disabled. Vary one factor at a time: subsistence access, donated support, rail dependence, offered equality, settlement breach, coalition reach, and authority coercive resources. Record household shortfalls, real pay, sales receipts, tax, army supply, O/E, constitutional preferences, and outcomes. The result is in-game attribution only.
2. Identify dominant policies. If suppression always wins, inspect its real personnel, supply, legitimacy, and later-organization costs. If every victory forces independence, inspect reform credibility and preference updates. If players can never afford a settlement, adjust initial stocks or market returns through explicit scenario configuration.
3. Playtest the factory and railway scenarios on desktop and iPad. Before the decision, ask players what they expect to gain and whom it costs. Afterward, ask whether they can explain the observed result. Remove repeated alerts and obscure actions; keep a detailed inspection view for experts.
4. Add a concise debrief with direct transfers, observed follow-on changes, and uncertainty about broader causation. Do not claim that the historical strike caused a measurable percentage of Senegal's independence.

**Gate:** deterministic tests and audits pass, both UIs work at their target sizes, and playtesters can identify at least two coherent strategies with costs and a recovery route. Record balance settings and observed limits. Commit.

## Checks to run at every behavior phase

- Focused new tests and the relevant existing suites, especially `test_labor_frontier_rivalry.py`, `test_plunder_labor.py`, `test_phase4.py`, `test_coercion_gdd_adherence.py`, and `test_web_client_parity.py`. Run only the broad suite needed to resolve remaining integration risk.
- `git diff --check` and `git status --short` before staging. Confirm no generated PNG, saved slot, or unrelated file is in the commit.
- At least one deterministic branch test that advances through the actual turn loop, plus a pickle round trip when persistent state changes.
- Currency and physical-goods conservation across support, wages, markets, route queues, force payroll, and constitutional transfer. Use the current audit functions and inspect each abnormal ledger event rather than increasing its tolerance.
- One desktop/`SimServer` parity case whenever scenario actions or projections change; one web parity case when the web bundle changes.

At the end of each phase, report the changed files, one gameplay example, tests run, the commit hash, and any remaining limitation. Do not claim a later phase is implemented because its card or formula exists in a design document.
