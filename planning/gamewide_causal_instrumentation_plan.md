# Game-wide causal instrumentation and run replay

Status: implementation plan, 2026-10-15. This extends the [collective run log](collective_run_log.md) to the entire simulation. The goal is to answer, for any displayed statistic and turn: **what changed, which operation changed it, what inputs and constraints were used, who decided, and what actually happened afterward?** This is a plan, not a claim that those probes already exist.

## Current seams and findings

- `sim_engine.step_turn` is the shared turn pipeline for the main simulation and the labor frontier scenario. It runs sovereign AI/intents, local economies, transport, trade, FX conversions, migration, claims, regimes, armies, diplomacy, innovation/resistance/imperialism, FX desk updates, and audits. Scenario code runs an additional settlement hook afterward. The existing shared `collective_trace_clock` stamps selected events across these paths.
- `Region` already keeps many time series: price, demand, supply, production, inventories, cash, population, hunger, GDP, extraction, rent, wages, strikes, grievances, protest energy, unrest events, ecology, disease, routes, FX, and trade. Most series contain **results**, not their calculation inputs or actors. `SimServer._record_history` retains only 50 national chart points; a replay must not depend on those UI buffers.
- `region_market.update_price_ref` changes reference prices from bid/ask ratio, producer stock scarcity, recent realized prices, and an input-cost floor. `price_decay` and `set_price` are other writers; the plan must instrument **every** writer, including transport prices and scenario market quotes. Logging only `price_log` cannot establish why a price moved.
- `region_factions.accumulate_grievances` has a source breakdown, but faction-specific additions, decay, policy satisfaction, protest-energy calculation, random unrest roll, repression, and national legitimacy drift are spread across `region_factions.py`, `faction.py`, `unrest.py`, and `regime.py`. “Unrest” can mean protest energy, an event stage, or a displayed aggregate; these need separate metric IDs.
- `forex.ForexDesk.update` uses reserve pressure, a PPP pull, a regime rule, and a band clamp. Its existing history stores rate and reserves. `sim_engine.py` currently calls `desk.update(0, ...)`, so the desk history does not have the actual turn. Conversion transactions in `forex.py` and the quoted rate update need distinct records. Define the quote direction and units before presenting an appreciation/depreciation explanation.
- `ai_nation.py` has `decision_log` but its main turn method submits intents without a comparable record of considered and rejected choices. `economy/capitalist_planner.py` returns early from many branches; `labor_frontier_labor.py` logs one owner choice but not all alternatives or the eventual result. A decision and the later intent execution are different events.
- `sim_server/sim_server.py` calculates nation and comparison panels independently. In the comparison suite, protest-share percentages are currently constants, several `treasury_delta`/`gini_delta` values are zero placeholders, the tile unrest stage reads a different field from `protest_energy_log`, and the banking panel can show fallback NEER/reserve values. A trace must mark such fields **unverified/placeholder** until they derive from authoritative state. The nation macro uses average tile protest energy while comparison panels sum it; both cannot share one unlabeled “unrest” definition.

## Data contract

Create one `RunTrace` owned by the world/server, attached to every region, nation, and scenario hook. Migrate the shared sequence from `collective_trace_clock` without renumbering old collective IDs. Keep the original state histories for charts; the trace is an append-only record of *how* the next state was reached. An event has:

```text
schema_version, run_id, branch_id, event_id, sequence, turn, phase, source
kind, actor {type,id}, subject {type,id}, location {tile,nation}
cause_event_ids, decision_id, operation_id, related_event_ids
metric_id, unit, currency, value_before, value_after, delta
inputs, formula_id, rule_version, constraints, active_floor_or_cap
record_class: observation | calculation | forecast | decision | attempt | transfer | outcome | audit
confidence: exact | approximate | unknown
```

Only include fields relevant to an event. IDs are stable strings; enum/good/currency names are explicit. Amounts use full simulation precision in the evidence file; the UI rounds only for display. JSON serialization is typed and fails on unsupported values instead of silently using `default=str`. A decision record contains observed inputs, feasible candidates and rejection reasons, scores with units/horizon, selected action, and expected result. Its execution record contains preconditions rechecked, exact paid costs/transfers, success/failure, and outcome. A forecast never becomes booked revenue or loss. Stochastic choices record the RNG stream/key, threshold/probability, and draw **without making an extra draw**.

Every chart field gets a manifest entry in `metric_catalog.py` (or a data file checked by it): metric ID, owner entity, unit/currency, turn phase, exact calculation/aggregation rule, authoritative writer, source events, null behavior, and UI fields that display it. Classify entries as authoritative, derived, scenario-specific, placeholder, or deprecated. One metric ID must not stand for both tile protest energy and actual unrest stage. National aggregates retain numerator, denominator, member tile IDs, and weights. Moving a tile between nations must not silently rewrite historical membership. If a displayed value lacks provenance, the UI says “Explanation unavailable” and identifies the missing source.

Use `cause_event_ids` only for recorded operations that actually feed the calculation or decision. A policy passed earlier may be an input; a contemporaneous correlated trend is not automatically a cause. For nonlinear formulas, record named terms and the active floor/cap, then recompute the final value. Do not invent additive percentages for a clamp or a minimum. Deltas of cash and goods must reconcile to named senders, recipients, creation/destruction rules, or an audit violation.

### Example: why food price rose

The numbers below illustrate the target record shape; they are not from a measured run.

```text
market_price_update: tile=Delta, good=food, turn=12
before=1.20, local_asks=60, imported_asks=20, bids=120,
demand_ratio=1.50, producer_stock=14, scarcity=..., recent_realized_prices=[...],
inflation_term=..., unclamped_target=..., VWAP_blend=..., input_cost_floor=...,
active_constraint=none, after=1.27
linked_events=[harvest_receipt_ids, import_delivery_ids, paid_sale_ids]
```

The linked events explain where supply and demand came from. The price calculation proves the reference-price change. Sales and food purchased are observed effects, not assumed consequences of the quoted reference.

## Implementation phases

Each phase ends with a focused test and a separate commit. Do not push. Follow `agent.md`: preserve money/goods, write scripts to files rather than inline shell code, and write commit messages to `tmp/commit_msgN.txt` before `git commit -F`.

### Phase 0 — Inventory and definitions

1. Generate a reviewed inventory of `Region` histories, `Nation`/bank/route state, scenario ledgers, and every field in `SimServer.serialize_world`, `serialize_tile`, `_calc_nation_macro`, and the six comparison tabs. Include desktop and web labels. For each, identify the current writer and its phase. Do not infer the formula from the label.
2. Resolve ambiguous metrics: nominal output value versus `real_gdp_output_log`; cash versus bank equity/deposits; tile protest energy versus `unrest_log` stage; a nation's mean versus sum; bilateral FX mid versus NEER; treasury cash versus deposits and debt. Replace hardcoded comparison percentages and zero deltas with real derivations or show them as unavailable. Correct the tile unrest field and display labels where necessary.
3. Establish fixed-seed baseline files for a normal world and labor frontier scenario: end-state digest, event count, cash/goods audit, representative price, unrest, FX, GDP, treasury, and AI decisions. Record existing unrelated failing tests separately. Decide exact metric IDs and unit conventions before adding probes.

**Gate:** every displayed stat is inventoried and either has an authoritative formula or is visibly unavailable. The same named metric has the same definition in desktop, web, tile, province, nation, and comparison views. Commit the catalog and corrected projections.

### Phase 1 — Shared recorder, snapshots, and replay contract

1. Add `run_trace.py` with a monotonic, append-only recorder and typed event helpers. Give `sim_engine.step_turn` and scenario after-hooks the same recorder. Add explicit phase markers and end-of-turn metric snapshots. Do not add an extra simulation pass that mutates agents.
2. Preserve run ID, seed, scenario, code/rule version, configuration, and branch ancestry. On save/load, continue sequence and event IDs; on restart from a save into a new branch, start a branch ID referencing the parent snapshot. Deduplicate retried commands by operation ID. A trace segment includes a checksum and count so a truncated file is detectable.
3. Write JSONL incrementally or in durable chunks, with a small in-memory recent-event ring for UI. Do not retain a second unbounded copy of every transaction in the world object. Keep complete forensic files for a run and an index by `(turn, entity, metric, event_id)` for queries. Make retention/export explicit and ensure a failed file write does not alter simulation results.
4. Adapt `collective_action.py`, `collective_trace_clock.py`, and `collective_report.py` through a compatibility adapter. Old saves with no sequence use the existing approximate-order flag; never present their order as exact.

**Gate:** instrumented and uninstrumented 30-turn runs have identical state digests and RNG results; save/load/rebranch is ordered, idempotent, and checkable; trace re-export is byte-stable for a fixed seed and version. Commit.

### Phase 2 — Production, livelihood, market prices, and trade

1. In `region_production.py`, record per-firm inputs removed, available worker hours, strike/forage exclusions, productivity, terrain/climate/machinery modifiers, actual units created, and final inventory. Name any explicit creation/destruction rule. Capture subsistence gather, consumption, purchases, hunger, wages, scrip redemption, and charity support as actual flows where they affect a charted metric.
2. In `region_market.py`, instrument `update_price_ref`, `price_decay`, `set_price`, and transport pricing at the point of mutation. Record bids, local/import asks, prior reference, producer inventories, scarcity, realized transaction prices, cost floor, clamp, and final reference. In `clear_discriminatory`, record matched buyer/seller/quantity, paid price, tax, rebate, and unsold stock. Tag a no-trade turn explicitly.
3. In `region_logistics.py`, `transporter.py`, `world_trade.py`, and scenario market hooks, record posting, queueing, route capacity/delay, arrival, rejection, paid settlement, and tariff/freight transfers. A shipment remains owned in every state. Link price updates to actual delivered supply where applicable, and distinguish a price quote from a paid sale.
4. Add derived snapshots for cost of living, real wages, GDP, inventory, output, employment, and trade balance using catalog formulas. Do not convert a scenario-specific cloth sale into the generic market's sale twice.

**Gate:** for a seeded price rise/fall, an analyst can recompute the final reference and identify supply, demand, VWAP, and floor effects. A strike/harvest/route delay leads through observed output, inventory, delivery, paid trade, and price without an invented damage charge. Money and goods reconcile. Commit.

### Phase 3 — Treasury, banking, debt, and FX

1. Record each tax, tariff, rent/tribute, payroll, subsidy, bond issue/coupon/default, bank deposit/loan/interest, and public reserve transfer at its authoritative operation. Include currency, account IDs, opening/closing balances, and the matching counterparty. Reconcile treasury changes by source and use the exact treasury definition displayed in the UI.
2. In `forex.py`, log conversion orders and actual executions separately from `ForexDesk.update`. For each bilateral desk update record quote direction, opening mid, domestic FX pool, partner reserves, target reserves, reserve ratio, pressure term/clamp, PPP target/gap, band clamp, regime, and closing mid. Pass the actual turn from `sim_engine.py` instead of `0`. Log why fixed regimes did not move. Record the inputs to any displayed NEER; remove a fallback NEER that is not computed.
3. Include currency-audit opening total, transfers, authorized creation/destruction, closing total, and residual. A nonzero residual remains an explicit violation, never a “cause” assigned to a plausible transaction. Treat different currencies separately and show conversion rates when comparing purchasing power.

**Gate:** reserve drain, PPP movement, a band cap, fixed parity, and a booked conversion each yield distinct explanations; multi-currency totals reconcile before and after save/load. Commit.

### Phase 4 — Grievance, unrest, regime, and political outcomes

1. In `region_factions.py` and `faction.py`, record raw hunger/inequality/tax/unemployment/eviction/labor/trauma inputs, scenario scales, faction-specific additions, previous grievance, decay, resulting support, and protest-energy formula. Use the exact source breakdown for comparison panels; do not display fixed percentages.
2. In `unrest.py`, record energy, calculated intensities, eligible mob/force, the one RNG draw, selected stage, loot/compromise/takeover operation, and its real material and legitimacy effects. Log a calm result when a meaningful roll occurred. In `regime.py`, record legitimacy target, drift, coup/election thresholds, candidates, and actual outcome. Link repression incidents and later grievance memory without counting the same action twice.
3. Connect labor/collective and constitutional incidents through stable event IDs. A workplace promise, enacted law, delivered right, and political preference change remain separate records. Do not turn a strike into an automatic state change.

**Gate:** a reader can distinguish “protest energy rose” from “a riot occurred,” recompute both the grievance change and event threshold, and see exactly why a government gained or lost legitimacy. Commit.

### Phase 5 — Nation, corporation, and scenario AI

1. Introduce a shared decision-trace helper that wraps an AI decision without changing selection order or consuming randomness. Log the information actually available at decision time, candidate IDs, feasibility checks, scores/forecast horizons, chosen candidate, and concise reasons for the strongest rejected candidates. A “do nothing” choice is a real candidate. Avoid dumping private future state into an AI rationale.
2. Instrument `ai_nation.py` defense, expansion, diplomacy, peace/war, subsidies, public works, and enclosure. Link each submitted intent to `intents.py` execution, rechecked preconditions, payment, and outcome. Record when an intended action fails or is superseded.
3. Instrument `economy/capitalist_planner.py`, `region_labor.py`, labor-mobility/owner wage bidding, and other corporation strategy paths. Because the planner returns early, log at the point of each gate/return or refactor into a side-effect-free candidate pass before choosing. Keep corporate revenue, liquidity, obligations, expected labor/input costs, and actual later profit separate. Include coercive operators and why a cheaper alternative won or lost.
4. Instrument scenario-specific owner and rival strategies through the same schema. Keep scenario narrative text as a rendering of structured inputs and results rather than the only evidence. Include player commands with authorization, chosen target, cost, handler result, and rejected/no-op reason.

**Gate:** for a nation and a corporation in one seeded turn, the trace identifies why an action was chosen over feasible alternatives and whether the submitted operation executed. Adding probes does not change chosen actions or the end state. Commit.

### Phase 6 — Remaining systems and coverage closure

1. Add source events and snapshots for population/birth/death/migration; disease/medical care; soil, pollution, fertilizer and climate; construction/innovation; armies/supply/war; elections/diplomacy/claims; land tenure, law enforcement, workhouse, and obligations. Use the catalog to assign the authoritative writer and expected cause type for every displayed field.
2. Add a coverage checker: for every metric snapshot change, require a same-turn calculation record and its input/operation links, or an explicit `unexplained_change` diagnostic. For a derived aggregate, require covered component snapshots. An unchanged metric needs its definition and snapshot, not a verbose non-event every turn.
3. Where a stochastic or external system cannot yet explain a value, report the gap explicitly with source file and phase. Remove metric-specific ad hoc loggers only after their users migrate; keep legacy chart histories as projections if needed.

**Gate:** the catalog reports 100% coverage for displayed metrics, no silent placeholder values, and no unexplained changes in deterministic fixture runs. Commit.

### Phase 7 — Analysis tools, UI, and performance

1. Add a CLI such as `trace_report.py --run <path> --turn 12 --entity tile:Delta --metric goods.food.price` that prints a concise causal path with before/after, formula terms, linked operations, forecasts versus realized outcomes, and audit status. Add a run-diff mode for matched seeds/configurations; label those comparisons as in-game counterfactuals, not proof of a historical cause.
2. Add paged/filterable `/api/trace` queries and a streaming full-run download. In desktop and iPad web charts, tapping a point opens a “Why did this change?” panel: a short explanation, top contributing operations, AI choice and rejected alternative where relevant, and a link to exact records. Show units, currency, territory, turn, source, uncertainty, and active floor/cap. Virtualize long event lists; do not send a full forensic log in every state poll.
3. Benchmark 30- and 100-turn default and scenario runs. Compare wall time, resident memory, trace bytes/turn, and state hash against no-trace mode. Set and document an acceptable budget from measurements, then batch writes/compress chunks as needed. The UI recent ring may be bounded; the forensic file and its index must retain the full run.

**Gate:** a player can explain a price change, unrest change, currency move, treasury delta, and AI action from both desktop and iPad; the CLI gives the same numbers; tests verify exact formula replay, conservation, deterministic behavior, save/load, query pagination, and practical run overhead. Commit.

## Priority and first implementation slice

Start with Phases 0–2, then FX and AI. A vertical slice should make one tile's food-price chart clickable and explain one fixed-seed rise and one fall using actual market inputs, while the full run records the same events. Include a corporation's response to the price change and verify whether its action executed. This validates schema, ordering, provenance, UI query, and performance before instrumenting dozens of remaining systems.

The acceptance test for that slice is a user-readable path such as: `harvest reduced → local asks fell → imports partly filled the gap → demand/available supply rose → reference price increased despite the cost floor staying inactive → buyers purchased fewer units → corporation considered raising its wage but lacked cash → no offer executed`. Every arrow must name the event or formula that supports it; if the source does not establish an arrow, show the two observations without claiming causation.
