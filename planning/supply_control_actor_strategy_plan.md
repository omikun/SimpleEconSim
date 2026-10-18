# Supply control: grower choice, actor accounts, and strategic play

## Purpose and player test

This follows the completed mechanics in [auction_market_and_input_power_plan.md](auction_market_and_input_power_plan.md). The core question is whether a nation should help its mills secure cheap inputs when that may reduce grower livelihoods, food security, and future supply, while a rival nation competes for the same crops and military resources. A useful decision must have plausible winners, losers, and alternatives. Neither a charter nor a competitive market should be the automatic best answer.

**Playable target:** In a small district with two named growers, two mills, and a route to another market, the player can explain a mill's input problem, the grower's reason for accepting or refusing its offer, the government's reason for approving or rejecting a charter, and the actual result several turns later. The player can recover from an initially poor choice. Show the rival's response and a national consequence, such as exports, tax revenue, food supply, or military procurement. Keep seasonal production at ten turns per year and individual career reconsideration at one turn per year.

## Current state and gaps verified in code

- `region_market.py` records settled spot fills with buyer, seller, quantity, unit price, and paid total. `crop_credit.py` records contract delivery and debt credit. `supply_rights.py` records land and water transfers. These records are separate, and the spot event buffer keeps only the last 500 fills. A buyer's delivered cost and a grower's realized crop return cannot be read from one coherent account.
- `crop_credit.offer_advance` transfers money and creates an obligation immediately when basic eligibility passes. `supply_rights.transfer_plot_title` and `acquire_water_right` also settle immediately. The word “voluntary” in their events currently means that the caller used that API; it does not prove the seller or borrower agreed. The server's direct land and water commands use the same paths.
- `economy/capitalist_planner.py` gives input control candidates urgency-based scores and usually selects one. It does not compare expected incremental cash return against a spot bid, a route purchase, or reduced output. Its `_active_plans` field is unused. Candidate prices and crop supply are largely inferred from reference quotes and an immediate shortage.
- `sim_server.serialize_tile` exposes current actor cash and market fills; `web_client/client.js` lists contracts, leases, charters, and water rights. It does not show an actor's income statement, an offer's acceptance reason, or forecast versus realized result. The existing labor-strategy plan also calls for firm operating statements; use one shared account/event layer rather than parallel notions of profit.
- A lease changes `controlled_by_id`, while existing tenants remain. Before valuing a lease as a cotton source, verify that control changes actual crop choice, delivery, or rent in the current production path. If it only changes a title field, its projected input benefit must be zero until an operative right is added.

## Accounting and decision contracts

Use a **single authoritative transaction journal** (or adapters over existing settlement records) with stable IDs independent of whether the optional compact trace is enabled. Append once at the operation that moves money, goods, debt, or a right. Keep the journal bounded in the live world and allow detailed history through the existing compact trace. Each record needs turn, tile, kind, good/asset, quantity, local currency, payer/recipient, seller/buyer, gross amount, deductions, linked proposal/contract/right IDs, and cause event ID where one exists. A transfer has exactly one source and destination; an FX leg names both currencies and the conversion actually paid. Do not infer paid amounts from a recipe reference.

For each named actor and turn, derive and seal:

| Measure | Rule |
| --- | --- |
| Firm sales and input cost | Sales are actual paid output fills; purchased crop enters inventory at actual acquisition cost and becomes an expense when consumed. Freight, tariff, finance, rent, payroll, petition, maintenance, and enforcement are distinct charges to their actual payer. Unsold output is inventory, not sales. |
| Firm result | Show operating profit, cash movement, stock, debt, and cash runway separately. An owner's investment or an advance recovered through crop is not sales revenue. Do not count the same transfer in `TrueCostLedger` and the cash account twice. |
| Grower crop result | Show spot receipts, contracted crop value, cash received at delivery, debt principal/interest extinguished, production/input/rent costs, food retained or purchased, and ending debt separately. Receiving an advance raises cash and debt; it is not crop income. |
| Rights and livelihood | Snapshot usable plot/commons access, title/control, water allocation, food stock and intake, due claims, and feasible outlets before a proposal and after settlement. Attribute observed changes to named transactions; label other changes as contemporaneous rather than proven effects. |

Generate an `ActorTurnAccount` from the journal after the local and route settlement phases, then seal it for next-turn planning. Give both the web and desktop clients the same JSON view model, with compact summaries in normal play and exact postings in Analysis. Maintain per-currency conservation and quantity reconciliation; do not add book value to cash profit. For cross-region goods, acquisition price and later freight/tariff need a named shipment link. A delivered unit cost must use **actual** arrival and purchase, not an estimate of the destination quote.

An offer has `proposal_id`, parties, target plot/right/harvest, quantity, price or formula, due and expiry turns, cash required, rights conveyed, legal basis, status, and linked decision. Statuses: `proposed → accepted/countered/rejected/expired → settled/defaulted/disputed`. No money, goods, debt, or rights move until acceptance and final revalidation. A counteroffer is a new priced term linked to the original; cap negotiation rounds and use deterministic tie breaking. A forced legal transfer must use a separate named authority and process, never the voluntary transaction path. Player commands require the same checks as AI actions.

## Implementation phases

Each phase is a reviewable commit after its gate passes. Keep the next phase from relying on an unimplemented choice. Update this document when a discovered settlement path changes the sequence. Follow `agent.md`: put the commit message in `tmp/commit_msgN.txt`, commit, and do not push.

### Phase 0 — Small deterministic economic fixture and operation audit

**Files:** new focused test fixture, `region_production.py`, `region_market.py`, `crop_credit.py`, `supply_rights.py`, route settlement helpers, `sim_engine.py` or the local stepper.

1. Build two growers on named plots, two cotton-consuming mills with different liquidity, one route, and a government. Fix starting cash, stocks, water, rights, obligations, and expected production. Include a normal and a poor-harvest variant.
2. Trace the exact per-turn order: owner planning, offer decision, production, contract delivery, spot clearing, route delivery, debt/rent/payroll/tax, and account seal. Specify what can use this turn's crop and what waits a turn. Record the existing lease effect on actual cultivation and the source of freight/tariff/FX charges.
3. Capture opening/closing per-currency cash and per-good stock, including cargo in transit, bank/treasury, and claims. Add fixture assertions for a simple spot sale, contract delivery, and route shipment before altering behavior.

**Gate:** the fixture runs the normal engine path, balances its transfers, and gives an unambiguous before/after state for every named actor. List any missing operation required to make a lease or right economically effective; do not give it an artificial benefit in later forecasts.

### Phase 1 — Actor-level accounts and outcome links

**Files:** a small account/journal module under `economy/`, settlement adapters in `region_market.py`, `crop_credit.py`, `supply_rights.py`, route/payroll/rent/tax paths needed by the fixture, `sim_server/sim_server.py`, focused tests.

1. Assign stable transaction IDs at settlement. Adapt existing spot, contract, land, water, route and relevant cost events into the common record without moving money a second time. Preserve contract `cash_paid` and `advance_credit` separately. Add actual freight/tariff/FX legs where settled, then link them to the delivered crop lot.
2. Compute per-actor sealed turn accounts and a bounded rolling 3–5 turn view. Define profit and cash flow as above; record unsold inventory and unresolved liabilities at the period end. Keep both corporation and grower accounts, including food intake and rights/access snapshots. Mark incomplete cost coverage explicitly until its posting is connected.
3. Expose selected actors' accounts and a short transaction/outcome timeline through `serialize_tile`. Keep ordinary world payload small; use compact trace or an actor-specific retrieval path for older detail. Verify save/load and that repeated serialization never changes balances or creates duplicate postings.

**Gate:** in the fixture, named spot and contract receipts reconcile to payer cash, seller cash, goods, and debt; a prepaid crop does not become a second cash receipt; a firm with unsold cloth has no cloth sales; an equity contribution changes cash runway but not operating profit. A route purchase has a delivered cost that differs from its farmgate receipt for an explained reason.

### Phase 2 — Grower and title-holder agency

**Files:** proposal/decision module, `crop_credit.py`, `supply_rights.py`, existing grower livelihood helpers, server commands, focused tests.

1. Change advances/offtake, title sale/lease, and water acquisition to **propose → decide → settle** for AI callers. The direct player commands must propose or resolve on valid authority; they cannot silently create agreement. Preserve existing lower-level settlement functions as guarded internal operations or require an accepted proposal token. Revalidate stock, title, water units, cash, tenant status, and duplicate claims just before settlement.
2. Give the receiving actor a bounded, explainable reservation value based on observed spot receipts, expected harvest/food kept, actual outstanding debt, next due payments, water/plot productivity, accessible rival buyers/routes, and risk of waiting. Food security and usable rights affect the outside option. Hunger can make a poor offer attractive; it does not force an acceptance flag. A title holder values future rent and control; a water holder values forgone yield and any minimum domestic allocation.
3. Permit accept, reject, or one counteroffer with a deadline. Keep personality or imperfect information as bounded variation around real constraints. Prevent overlapping pledges of the same harvest or sale of a protected/occupied right. Use existing lawful coercive institutions, where available, as distinct contested procedures with enforcement and remedy; never report them as voluntary consent.
4. Emit a decision record with offered terms, named outside option, acceptance threshold, reason, and subsequent status. Rejection moves no cash/right/debt. When an advance is accepted, link disbursement to its future crop and liability; when a grower defaults, preserve the actual shortfall rather than pretending the forecast was realized.

**Gate:** a secure grower can refuse a low fixed price, a liquidity-constrained grower can accept a useful advance, a rival bid changes the choice, a title holder can refuse a lease, and a water holder can refuse a diversion. Countered terms reprice the buyer's project; expiry, death, lost title, or insufficient funds cannot create a transfer. All paths conserve money, crop, water, and obligations.

### Phase 3 — Corporate choice among real alternatives

**Files:** `economy/capitalist_planner.py`, market/route quote helpers, `market_concessions.py` only where needed, strategy tests.

1. Replace the urgency score with a common **incremental expected owner value** over the next harvest or 2–4 turns, whichever is longer. Baseline is the best feasible ordinary response: spot bid, route supply, smaller output, or wait. Compare advances, leases/title purchases, water, and eligible charter petitions against that baseline. Use observed fills and stale-aware quotes, visible rights/routes, estimated acceptance and delivery probabilities, direct costs, and residual asset/liability value. Do not read future random harvests or private rival cash.
2. Rank candidates by expected added profit subject to cash runway, capacity, rights, and uncertainty. Record expected crop units, net delivered cost, acceptance probability, charter approval/enforcement probability, expected grower exit or yield loss, cost now, horizon, main uncertainty, and reason infeasible. Do not subtract a risk twice when it is already inside an expected cash flow.
3. Persist a small actor plan with target, budget, proposal/charter ID, next review, and stop conditions. Replan on rejection, default, changed quotes, route disruption, policy change, or a worse realized result. Add a cooldown for repeated rejected offers and duplicate petitions. Execute at most one major right or charter action per owner per planning window; ordinary market bids continue.
4. Keep state authority independent. The nation AI should evaluate a charter's fiscal and strategic benefit against food access, grower income, legitimacy, enforcement capacity, and rival response; the player's pending petition still waits for a real decision. Neither a petition nor a positive corporate forecast guarantees a charter.

**Gate:** controlled fixtures select spot bidding when rivals compete and growers have good outlets; an advance when a grower wants liquidity and delivery is credible; a lease or water deal only when it improves actual harvest/input cost enough to pay; a petition only when expected approval and enforcement justify its fee; and contraction when output cannot be sold profitably. Rejection or default changes the following plan. The AI trace includes the baseline, chosen candidate, runner-up, assumptions, and realized comparison.

### Phase 4 — Playable scenario and matched web/desktop presentation

**Files:** authored scenario and CLI registration, `sim_server/sim_server.py`, `web_client/`, desktop market/Guided panels, scenario and UI tests.

1. Build the small scenario from Phase 0 as an actual playable world. Give the player a government objective and a timed input-supply problem: a domestic mill, a rival buyer, two growers with different food/debt positions, a route, and an enforceable but contestable petition. Let the player decide a charter or a named protection/investment response through an existing funded operation. Give the rival a visible economic or military consequence, not a detached score bonus.
2. Put one compact card on the normal screen: `crop paid price / local supply and funded demand / mill input fill / grower food and cash / petition deadline`. Show a forecast before a response and an observed outcome afterward, with winners and losers by name. Add an actor drilldown for receipts, costs, rights, decision reasons, and the linked sequence offer → response → crop → sale → account. Mark estimates, stale quotes, and unresolved contracts clearly. Keep the same commands and wording on web (including iPad layout) and desktop.
3. Include at least two viable paths under different starts: open competition may preserve growers and later supply, while a time-limited controlled supply arrangement may protect a strategic industry under a temporary shock but cost legitimacy or food access. Use actual transactions and strategic reactions for every consequence. Provide a recovery move after refusal, charter repeal, or a bad harvest.

**Gate:** on both clients a player can identify why the price moved, why each grower accepted/refused, why the mill chose its action, and what it gained or lost after settlement. Every visible button passes server validation and has a real funded effect. The route and petition deadlines remain meaningful on touch devices. A new player can finish the scenario without opening the full trace; if human feedback is unavailable, report gameplay clarity as unvalidated rather than claiming fun is proven.

### Phase 5 — Balance, audits, and game-quality checks

**Files:** deterministic benchmark script under `tmp/` or tests, trace analysis tooling, parameter configuration, scenario copy if needed.

1. Compare same-start runs across open buying, an accepted advance, refused advance, lease/water rights, and a charter. Use multiple seeds and a short 20-turn scenario plus a 50-turn default three-nation run. Record per-mill realized input unit cost/fill/profit, per-grower crop net/cash/food/debt, title/water concentration, public revenue/enforcement cost, unrest, and rival trade/military supply. Pair seeds, but label branch divergence and external shocks; do not call an aggregate difference a causal effect on an individual.
2. Test exploits: duplicate advances against one harvest, over-pledged water, contracts that take household reserves, buyer insolvency at delivery, lease without production benefit, offer spam, end-of-horizon asset purchase, free public enforcement, and UI commands bypassing acceptance or jurisdiction. Verify save/load with pending proposals and contracts, trace replay, and per-currency/good conservation.
3. Tune observable parameters so choices depend on scarcity, outside outlets, liquidity, state capacity, and rival strength. Avoid guaranteeing that every control is profitable or that every grower refuses it. Playtest whether choices produce understandable tension, varied strategies, and useful recovery; revise pacing or presentation based on what players actually do.

**Gate:** no dominant option across all controlled starts; both market and controlled-supply paths can win under stated conditions, each can fail for an understandable reason, and actor accounts explain the result. Technical tests and conservation pass. Record gameplay feedback separately from simulation correctness.

## First coding slice

Start with Phases 0–1. The first demonstration is one grower selling cotton locally and another delivering two pledged units to a mill, while a rival buys through the route. Print or inspect each actor's opening/closing cash, stock, debt, food, paid prices, and rights. The mill's delivered input cost and each grower's cash and crop result must reconcile to the same settled events. Only then add acceptance logic: without that evidence, a proposed deal cannot be priced or explained reliably.

## Explicit boundaries

- These phases improve decisions around mechanisms already implemented. New violence, expropriation, or labor-law operations require their own named legal authority, physical state change, cost, target response, and remedy before the planner can choose them.
- Forecasts express actor beliefs and uncertainty; realized accounts express paid transfers. Rights and food effects stay visible even when the firm does not price them directly.
- Aggregate national totals supplement named actor accounts. The player's strategic choice remains expansion and competitive strength against citizens' livelihoods, not maximizing one undifferentiated score.
