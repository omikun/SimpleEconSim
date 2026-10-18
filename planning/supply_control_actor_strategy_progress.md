# Supply control implementation progress

Updated 2026-10-18. This file tracks implementation against
[`supply_control_actor_strategy_plan.md`](supply_control_actor_strategy_plan.md).
Simulation checks are evidence about mechanics, not a claim that the scenario is
already fun or balanced; that still needs player feedback.

## Phase 0 — fixture and operation audit: complete

- The normal engine fixture has two named cotton growers, two mills, a route,
  and government. A poor-rainfall variant checks named water allocation. The
  first seasonal tick passes currency conservation.
- Verified turn order: policy and rent before local production; crop claims and
  contract settlement before the spot auction; route posting afterward. Cargo
  arriving after local settlement is eligible for the destination's next
  auction.
- Found and addressed two operational gaps: route freight was not charged to a
  public carrier, and an unstaffed corporation could produce through the
  independent-producer path. Bare leases retain tenant cultivation, so the AI
  treats them as no guaranteed input supply.

## Phase 1 — actor accounts: tested cash bridge reconciles, broader coverage pending

- `economy/actor_accounts.py` creates stable local settlement IDs, opening
  snapshots, bounded event history, and sealed actor-turn statements. It records
  paid spot and contract values, production/input consumption, wages, owner
  finance and distributions, taxes/claims, rights, charter fees, freight, and
  now company scrip wages, store redemption, food-credit debt, and store stock
  purchases. Scrip changes are kept separate from cash wages and cash movement.
- The event journal is independent of compact causal tracing; serialization and
  save/load tests verify they do not create new settlements. Both clients show
  named cash, crop receipts, food, debt, supply offers, and relevant rights.
  Statements label cost coverage as incomplete. Web additionally shows scrip
  balances and cash movement not yet matched to journal postings.
- The benchmark seeds both world generation and Python's global simulation RNG.
  Before the cash-adapter work, two fresh-process 50-turn runs for seed 4242
  matched at $15,700.70 in final-turn unmatched actor cash. The audit now checks
  every actor-turn as well as reporting the largest current and historical gaps.
- The cash bridge now includes company formation and planning transfers, strike
  support and machinery repair, workhouse food purchases, medical care, charity
  donations, inheritance, welfare, UBI, parental leave, baby bonuses, birth
  endowments, provincial food-haulage wages, and alienation spending and fees.
  Shared province actors read cash postings from every member tile, with tile
  and event references retained in their statements.
- In fresh 50-turn default runs, seeds 4242, 4243, and 4244 each completed with
  zero currency violations and zero unmatched cash across all actor-turn
  statements. This verifies the current default scenario sample; broader
  scenario coverage and long-run statement-history checks remain outstanding.
- Cash statements describe observed transfers, not complete profit. Estate
  foreign-wallet inheritance and escheat now have separate currency records and
  opening/closing wallet balances. Domestic-bank losses on sovereign defaults
  now have named bond write-off events and before/after capital and equity
  evidence; non-estate credit losses and other noncash asset changes still need
  coverage.
- Cash rent, enclosure charter fees, and bailiff services now post named actor
  transfers. The bailiff's $10 cost is tracked as its own enforcement expense.
- Estate cash distributed to heirs, government, or charity now posts as named
  inheritance transfers with source currency and destination details. This
  reduced the deterministic seed's final-turn unmatched sum from $15,700.70 to
  $15,606.81; the largest remaining gaps are unchanged, so inheritance was a
  real but secondary source.
- Bank deposits/withdrawals, loan issuance/repayment, deposit interest, and
  deposit haircuts now post named events. Turn accounts expose bank savings,
  outstanding bank principal, company-store debt, and distinct repayment and
  haircut totals. Estate settlement now records repayment from cash/deposits,
  repayment from foreign-currency wallets, principal transferred to heirs, and
  heirless principal write-offs. The write-off event names how much was absorbed
  by bank capital, depositors, and treasury recapitalization; actor summaries
  keep debt amounts grouped by currency.
- The Anti-Truck Act's company-store debt cancellation is recorded as a paired
  noncash event: workers see the liability discharged, the employer sees its
  store receivable written off, and neither side gets a false cash movement.
- Egypt scenario cadastral arrears relief and the generic cash-obligation
  cancellation helper now record noncash debtor/creditor write-offs. Arrears
  forgiveness splits the public claim between municipal and national
  treasuries, matching the tax-allocation rule. Actor statements and web tile
  inspection show these write-offs without treating them as cash movement.
- Imported asks now use each shipment lot's source cost and paid freight,
  converted to destination currency with the source desk's current buy quote
  (or the destination desk's bilateral quote). The quote trace records the
  selected cost basis, FX method, tariff and drawback, break-even, margin, and
  whether the reference-price cap binds. A low reference cap cannot force an
  ask below landed break-even after the effective tariff. Trader routing and
  input bid estimates apply that tariff once, matching settlement's statutory
  duty and drawback rules.
- Each paid imported sale records the actual destination price, source and
  freight cost in both currencies, FX rate and valuation basis, tariff assessed,
  drawback returned, tariff paid, seller receipt, and estimated landed margin.
  Delivered-input account lots expose those fields through the server API; the
  web and desktop clients summarize landed cost, duty, and trader margin beside
  the actual delivered unit price.
- Stock created by old direct-buy paths, initial scenario setup, liquidation,
  or other flows without a settled market event remains explicitly unlinked.
  If a legacy lot lacks a bilateral FX quote, the ask trace records the parity
  fallback used for pricing; if its acquisition cost is unknown, it remains
  explicitly estimated or unlinked instead of being presented as a settled
  purchase cost.
- Bank deposits and withdrawals now carry a named institution, depositor,
  reason, requested and settled amounts, cash and savings balances before and
  after, and bank-wide deposit totals. Frozen withdrawals show the cap and any
  blocked amount. Actor accounts and both clients report per-turn deposits and
  withdrawals separately from the closing savings balance. Explicit tile
  context now captures internal charity operations that were previously
  omitted because the charity agent is not a resident.
- A cash wage shortfall now creates a paired noncash employer payable and
  worker claim. Actor statements report opening and closing arrears and new
  accruals; compact traces explain the nominal wage, cash paid, employer cash,
  tender rule, and claimants. Aggregate balances preserve outstanding claims
  beyond the 500 recent detail rows. This instruments accrual only: the game
  still has no wage-arrears repayment, write-off, or estate-settlement path.
- The frontier expedition now debits its advertised 100-unit cost from the
  sponsor treasury and funds five 20-unit pioneer wallets in the sponsor
  currency. Linked treasury-spend and wallet-grant events plus compact traces
  show the source and destination balances. This also fixes the old policy
  handler's invalid agent initialization and duplicate arrival insertion.
- Remaining gate work: audit other non-estate credit losses and non-probate
  cash-to-wallet legs, including owner bailouts and election campaign transfers;
  decide how unpaid wage claims behave when the firm or worker exits.
  Scenario-seeded or legacy cargo can still lack a settled source cost. The
  tested default runs close the actor cash bridge, but they do not prove
  complete balance-sheet or operating-profit coverage.

## Phase 2 — grower and title-holder agency: implemented, deeper law/remedy work out of scope

- Advances/offtake, crop advances, land leases/sales, and water rights now use
  proposals that wait for seller response. Rejection and countering do not move
  money or rights; settlement rechecks funds, title, water, harvest pledges,
  and protected food/water reserves. Low-level settlement APIs require an
  accepted proposal token. Player land/water commands create offers instead of
  bypassing consent. Pending offers survive save/load.
- Proposal events carry named parties, reservation basis, decision reason, and
  outcome. Tests cover refusal by a secure grower, acceptance when liquidity is
  useful, title counteroffer, water refusal, duplicate offer, buyer insolvency,
  and protected reserves.
- Coercive state action remains represented by existing named concession and
  labor-law systems; this slice does not add a new expropriation or violence
  operation. Any new forced transfer needs its own authority, enforcement cost,
  target response, and remedy.

## Phase 3 — corporate choice: implemented, outcome calibration pending

- `economy/supply_strategy.py` scores corporate input actions against a funded
  spot/route baseline using recent sales, saleability, fill rates, seller
  reservation value, estimated acceptance/delivery/default, cash runway, and
  direct cost. It does not use future harvest draws or private rival cash.
- The planner records its candidate set, selected action, runner-up, key
  assumptions, proposal result, and replan triggers. It cools down after a
  rejection, avoids duplicate active proposals, and pauses unprofitable output
  for five turns while releasing workers and later restoring hiring capacity.
  A lease with no production effect scores as infeasible; water only scores when
  a contract can direct the crop.
- Tests show a secure grower makes a discounted advance unattractive, a
  cash-poor grower can make a useful advance attractive, and a negative-margin
  mill releases workers. Corporate forecasts are still estimates, not calibrated
  forecasts; multi-seed realized-vs-expected accuracy remains to be measured.

## Phase 4 — playable scenario and clients: implemented, playability validation pending

- Added `scenario_supply_rivalry.py` with two named districts/nations, two
  growers, domestic and rival mills, a route, and a timed exclusive-buying
  petition. Player actions include approve/reject/repeal, public crop purchase,
  and funded canal repair. The scenario runs through the normal engine and is
  available to CLI, web, and desktop guided flows.
- Both clients project the same scenario pressures and accept the same funded
  actions. Tests exercise server actions and desktop projection. The player can
  inspect corporate proposals and outcomes through the existing supply panel.
- The scenario's agency paths and mechanical effects are test-covered. No human
  playtest has yet verified that a new player can understand the forecast or
  that either path is enjoyable; this remains an explicit product gate.

## Phase 5 — balance and audits: initial benchmarks complete, unresolved audit and tuning remain

- Added `benchmark_supply_rivalry.py` for matched policy runs (reject/approve
  charter, public crop purchase, canal investment) across seeds 812–814, and
  `benchmark_supply_default.py` for the requested 50-turn, three-nation default
  run. The scenario branches produce different fill, sales, grower cash/food,
  and canal outcomes. Branches diverge stochastically after actions, so these
  results are descriptive, not clean causal estimates.
- Each of the 12 rivalry benchmark runs reported zero currency violations. The
  phase-level default audit found the prior currency leak in
  `capitalist_electoral_backlash`: a donation was debited/credited in cash and
  also changed wallets, sometimes below zero or double-counting. It now moves
  exactly one balance; election campaign spending credits a candidate's
  nation-currency wallet when their home currency differs. Regression tests
  cover same-currency wallets and cross-currency donors/recipients.
- After that fix, 50-turn default runs for seeds 4242, 4243, and 4244 reported
  zero currency violations. Earlier runs of seed 4243 showed -$112.61 and
  -$786.98 USD gaps in the regime phase. Keep the phase audit in the benchmark
  and continue testing more seeds before closing the gate.
- No option has been shown to dominate across these three starts, but the
  benchmark currently reports branch outcomes rather than proving an optimal
  strategy or enjoyable balance. Outstanding checks from the plan include
  complete multi-seed corporate decision quality, more exploit cases, and
  human playtest feedback.

## Verification run

- Imported shipment asks now use lot cost plus paid freight in destination
  currency; quote traces include FX valuation, tariff terms, break-even, margin,
  and reference-cap behavior. Paid sales and firm account lots carry tariff,
  drawback, seller receipt, FX, landed-cost, and trader-margin details. Both
  clients show the destination-currency landed cost, duty, and margin beside
  the actual imported input price.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_market_routes test_market_auction test_supply_control_actor_strategy.ActorAccountTests` — 39 tests passed, including a USD-to-EUR shipment with freight, tariff, drawback, settlement, and account-summary checks, plus a reference-cap break-even check.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec test_banking_contagion` — 120 tests passed.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — default three-nation 50-turn run completed with zero currency violations, zero unmatched actor cash on turn 50, and zero unmatched actor-turn cash across the run.
- Bank deposit and withdrawal journal events now link to the bank institution
  and carry caller reason, requested/settled amount, and before/after cash and
  savings balances. The compact trace shows frozen-withdrawal caps. Actor
  statements include total deposits and withdrawals; charity's internal bank
  operations now have an explicit region and are journaled too.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec test_banking_contagion` — 121 tests passed, including charity cash sweeps, actor deposit/withdrawal totals, and a frozen-withdrawal trace.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — the default three-nation 50-turn run completed with zero currency violations and zero unmatched actor cash on turn 50 or across actor-turn statements.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec test_banking_contagion test_plunder_labor` — 139 tests passed, including paired wage-arrears statements, causal shortfall inputs, and balance retention after the 500-row detail window.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed for the wage-arrears trace, account, and client changes.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — the default three-nation run completed with zero currency violations, zero unmatched actor cash on turn 50, and zero unmatched actor-turn cash across the run.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_frontier_policies` — 2 tests passed for treasury-funded grants, source/destination wallet journal legs, web/desktop parity, and insufficient-funds rejection.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed for frontier action and trace changes.
- Domestic-bank sovereign bond principal and coupon defaults now create one
  economic journal event per affected tile bank, linked to the bond ID and
  issuer. Compact trace records the default kind, missed payment amount, actual
  bank asset loss, capital/equity before and after, deposits, liabilities,
  cumulative write-downs, and deposit-freeze transition. End-turn snapshots
  capture bank capital, equity, deposits, liabilities, and cumulative write-
  downs; tile inspection exposes the institution balance sheet and held
  sovereign tranches. Existing behavior is preserved: coupon default still
  writes down the held bond's allocated principal, which the new records make
  explicit for later tuning.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec test_banking_contagion` — 116 tests passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — default three-nation run completed 50 turns with zero currency violations, zero unposted actor cash on turn 50, and zero unposted actor-turn cash across the run.
- `git diff --check` and targeted Python compilation passed for the bank, bond, snapshot, serializer, and test changes.
- The Anti-Truck Act now links a debt write-off event to worker and employer
  statements, records the law and currency in the causal trace, and shows the
  worker relief or firm receivable loss in the web actor-account summary.
- District arrears relief now writes down the household liability and the
  matching municipal/national tax claims; direct cancellation of a named cash
  obligation records the debtor and creditor losses. Both are noncash journal
  events with causal trace entries and actor-account totals.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec test_banking_contagion` — 116 tests passed after the Anti-Truck Act ledger addition.
- `node --check web_client/client.js`, targeted Python compilation, and
  `git diff --check` passed for the Anti-Truck Act ledger and display changes.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec test_banking_contagion` — 118 tests passed after cadastral arrears and obligation-cancellation coverage.
- `node --check web_client/client.js`, targeted Python compilation, and
  `git diff --check` passed for the new debt-writeoff paths.

- Local FX desk conversions now record their home-currency cash leg and the
  foreign amount/rate in the same economic event; a focused account test checks
  that this leg reconciles. Bank deposit and withdrawal traces now record why
  cash moved between a named actor and savings; frozen-bank traces distinguish
  requested and settled amounts and expose the subsistence cap. Internal
  charity deposits/withdrawals use explicit tile context so they appear even
  though the charity agent is not in the resident list.
- Route shipments now carry a stable shipment ID plus the trader's source cost
  basis, freight per unit, and source currency. Arrival makes a matching
  import-lot record; destination auction fills decrement that lot and link the
  paid destination price back to it. The actor account and both clients show
  actual imported input unit prices; the account also exposes shipment IDs,
  source cost, and freight as separate values.
- Parked arrivals now receive import-lot records too. A parked sale retains the
  same cost and shipment link, and re-routing creates a new route-leg ID while
  keeping the original source shipment, source region, cost status, and full
  route history. Legacy parked quantities without a lot are tagged
  `unlinked_legacy_cargo` instead of being assigned invented costs. Shipment
  departure, arrival, and sale records carry the same provenance in the
  economic journal and compact causal trace. Reclaiming a trader also returns
  cargo still waiting in a route's pending queue to export stock.
- Paid market purchases by traders now create quantity-backed acquisition
  records that point to the purchase journal and trace events, named seller,
  actual paid unit price, currency, and any parent shipment. Route posting
  consumes those records; a fully linked shipment's source unit cost is the
  quantity-weighted actual paid price. Mixed shipments carry their linked and
  unlinked portions separately, through rerouting, arrival, sale, and the
  firm's delivered-input account. This links market-sourced crop to the
  destination fill without treating the displayed reference price as a cost.
- Stock created by old direct-buy paths, initial scenario setup, liquidation,
  or other flows without a settled market event remains explicitly unlinked.
  FX and tariff conversions remain separate cash legs rather than a fully
  normalized per-shipment delivered-cost calculation.
- Deaths that distribute foreign wallets now record one event per currency and
  beneficiary. Cash inherited directly into a wallet has a linked cash debit
  and noncash wallet receipt, so the actor cash bridge does not count it twice.
  Accounts show opening/closing wallet balances and currency changes; province
  event aggregation makes cross-tile heirs visible. Heirless government
  receipts and no-government escheats are recorded separately.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip` — 67 tests passed after bank debt, company-store debt, campaign-currency, and linked shipment additions.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_run_trace test_market_auction test_supply_control_actor_strategy test_phase1_enclosure_expansions` — 34 tests passed after inheritance, cash-rent, enclosure-fee, and public food-purchase postings.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy.ActorAccountTests test_supply_control_actor_strategy.SupplyControlActorFixtureTests test_phase1_enclosure_expansions` — 29 tests passed after shared-province cash postings and alienation-flow instrumentation.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy.ActorAccountTests.test_estate_debt_settlement_records_foreign_payment_and_inherited_principal test_supply_control_actor_strategy.ActorAccountTests.test_heirless_default_records_loss_waterfall_and_treasury_funding` — estate repayments, multi-currency inherited debt, deposit bail-in, and treasury recapitalization postings passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy.ActorAccountTests test_supply_control_actor_strategy.SupplyControlActorFixtureTests test_phase1_enclosure_expansions` — 31 tests passed after the estate-debt journal additions. `test_run_trace` passed all 17 tests; `test_true_cost_externalities` passed all 10 when run alone.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_market_routes test_market_auction test_phase4 test_supply_control_actor_strategy.ActorAccountTests test_run_trace` — 52 tests passed after parked and re-routed shipment provenance, trace linkage, and pending-cargo reclaim.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace` — 100 tests passed across the actor-account, rights, market, route, web-parity, truck/scrip, and trace suites.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_market_routes test_market_auction test_supply_control_actor_strategy.ActorAccountTests test_run_trace` — passed after purchase-to-seller acquisition links and route cost weighting.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace` — 103 tests passed after acquisition links; focused compile and diff checks passed.
- Repeating `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` after acquisition-link tracking again completed 50 turns with zero currency violations and zero unmatched actor cash across actor-turn statements.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec` — 109 tests passed after foreign-wallet inheritance and escheat coverage; `git diff --check` and targeted compile checks passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — repeated after foreign-wallet accounting; the 50-turn run reported zero currency violations and zero unmatched actor cash across actor-turn statements.
- `git diff --check` and `venv/bin/python -m compileall -q transporter.py world_trade.py region_market.py region_logistics.py economy/actor_accounts.py` — passed for the shipment-provenance slice.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — default three-nation 50-turn run completed with zero currency violations, zero unmatched cash on turn 50, and zero unmatched cash across actor-turn statements.
- `node --check web_client/client.js` and `git diff --check` — passed after the same changes.
- `node --check web_client/client.js` — passed.
- `git diff --check` — passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_rivalry.py` — 12 matched runs, zero reported currency violations.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_rivalry.py 812 813 814` — repeated after shipment linking; all 12 branches still report zero currency violations.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 <seed>` — 50 turns completed with zero currency violations for seeds 4242, 4243, and 4244 after the campaign-transfer fix.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — two fresh-process runs after seeding the global RNG matched across counts, proposals, prices, cash audit, and unmatched accounts; both reported zero currency violations and $15,700.70 unmatched actor cash. After estate-transfer postings, the deterministic run still had zero violations and $15,606.81 unmatched actor cash. The benchmark also shows the largest unmatched actor-turn rows for targeted tracing.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — seed 4242 completed 50 turns with zero currency violations, zero unmatched cash on turn 50, zero unmatched cash across all actor-turn statements, and zero actor-turn statements above the 1-cent threshold. Seeds 4243 and 4244 also completed with zero currency violations and zero unmatched cash on turn 50.
- Full `unittest discover` was attempted but this environment's native pygame/OpenGL tests crashed the Python process (exit 139) before a summary could be produced; the focused simulation, rights, auction, route, and web parity suite remains green.
