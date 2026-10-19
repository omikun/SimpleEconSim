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
- A cash wage shortfall creates a paired noncash employer payable and worker
  claim. Actor statements report opening and closing arrears and new accruals;
  compact traces explain the nominal wage, cash paid, employer cash, tender
  rule, and claimants. Aggregate balances preserve claims beyond the 500 recent
  detail rows. After current payroll review, firms now repay old claims from
  cash above a one-payroll reserve, oldest claim first. Cash and wallet
  settlements link the employer debit to the worker receipt, update the
  liability balance, and trace the before/after claim. Both clients show new
  arrears and repayments. Migrating workers retain creditor references and
  can collect into a currency wallet. Worker death passes claims to living
  heirs or to government/charity probate shares; firms that dissolve use their
  remaining cash first and write off any unpaid balance. The payroll
  insolvency, construction bankruptcy, corporation-death, and owner-estate
  dissolution paths use this settlement. Claim relationships survive save/load.
- The frontier expedition now debits its advertised 100-unit cost from the
  sponsor treasury and funds five 20-unit pioneer wallets in the sponsor
  currency. Linked treasury-spend and wallet-grant events plus compact traces
  show the source and destination balances. This also fixes the old policy
  handler's invalid agent initialization and duplicate arrival insertion.
- Owner-funded payroll rescues and firm-to-owner salary, dividend, and loan
  repayment flows now distinguish hand cash from a currency-wallet leg.
  Linked events preserve the firm cash bridge while showing the owner's wallet
  movement and the firm's opening/closing owner loan. Election campaign
  spending similarly records treasury outflow and the candidate's cash or
  wallet receipt, with the payment route and balances in the compact trace.
- Wilderness trader settlements now record the trader's cash debit and each
  homesteader's wallet receipt as linked transfer legs. Goods advanced to
  homesteaders and harvested food/wood collected by traders have separate
  quantity records with their reference prices. Actor statements reconcile the
  trader's cash movement and each resident's wallet movement. This records the
  current settlement rules without adding debt: despite older comments calling
  the goods an advance or loan, this code path does not create a homesteader
  liability or trader receivable.
- Imported auction sales now keep the seller's total proceeds while splitting
  actual cash receipts from destination-currency wallet receipts. FX proceeds
  post a linked noncash wallet event, and the actor cash bridge counts only the
  seller's hand-cash portion. The buyer-side sale stays on the destination
  ledger, while the seller receipt posts to the trader's home tile; the trace
  links both ledgers to the same sale.
- Away traders who spend foreign wallet balances on destination food now post
  the wallet debit on their home tile and the seller's cash receipt on the
  destination tile. The trace links both journal legs and records the food,
  quantity, price, and before/after balances. The generalized and legacy
  two-region trade drivers use the same settlement recorder.
- Bilateral FX order-book matches now journal the bidder's home-currency cash
  payment and the seller-to-buyer foreign-wallet transfer as linked legs. The
  trace records both traders' before/after cash and wallet balances, matched
  quantity, rate, and journal references; actor statements reconcile both
  traders' changes.
- Initial trader float is now recorded as a funded setup conversion: the cash
  and deposit contributions, bank FX pool/reserve changes, and foreign-wallet
  receipt share one transfer ID. Since world generation seeds this before the
  live trace attaches, the server flushes those records into the turn-zero
  trace; actor statements count only the hand-cash portion as cash outflow.
- Wilderness entry, settlement on claimed land, migration, and treasury
  conversion of same-currency wallets now record linked cash and wallet legs.
  Both current and compatibility wilderness APIs pass tile and turn context;
  actor statements reconcile the cash side and show per-currency wallet flows.
- Crop liens and share-tenancy rent now record in-kind harvest quantity and
  reference value. Lien records show the actual debt credit separately from
  any crop value transferred beyond the remaining balance; share-rent records
  name the tenant, landlord, plot, crop share, and valuation basis. These flows
  are excluded from cash reconciliation and appear in actor statements and the
  web market summary.
- Remaining gate work: audit other non-estate credit losses; decide whether
  wilderness inventory advances should create a repayable debt claim.
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
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_forex_accounting test_world_trade_accounting test_market_routes test_market_auction test_run_trace test_supply_control_actor_strategy` — 82 tests passed after bilateral FX order-book settlement accounting.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — repeated after bilateral FX journal coverage; the default three-nation run completed with zero currency violations and zero unmatched actor cash on turn 50 or across actor-turn statements.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_forex_accounting test_frontier_policies test_run_trace test_supply_control_actor_strategy test_phase1_enclosure_expansions test_wilderness_trade_accounting` — 79 tests passed after cash-to-wallet conversion accounting.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — repeated after wallet conversion journaling; zero currency violations, zero unmatched actor cash on turn 50, and zero unmatched actor-turn cash across the run.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_crop_credit_accounting test_forex_accounting test_supply_control_actor_strategy test_supply_rights test_web_client_parity test_phase1_enclosure_expansions test_run_trace` — 108 tests passed after crop-lien and share-rent accounting.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed for crop-credit actor accounts and the web summary.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — repeated after in-kind crop accounting; zero currency violations, zero unmatched actor cash on turn 50, and zero unmatched actor-turn cash across the run.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_forex_accounting test_world_trade_accounting test_web_client_parity test_run_trace test_supply_control_actor_strategy test_market_routes` — 102 tests passed after initial trader-float accounting; a focused live-server test confirms float records appear in the turn-zero compact trace.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — repeated after initial float accounting; zero currency violations, zero unmatched actor cash on turn 50, and zero unmatched actor-turn cash across the run.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec test_banking_contagion test_plunder_labor` — 139 tests passed, including paired wage-arrears statements, causal shortfall inputs, and balance retention after the 500-row detail window.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed for the wage-arrears trace, account, and client changes.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — the default three-nation run completed with zero currency violations, zero unmatched actor cash on turn 50, and zero unmatched actor-turn cash across the run.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_frontier_policies` — 2 tests passed for treasury-funded grants, source/destination wallet journal legs, web/desktop parity, and insufficient-funds rejection.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed for frontier action and trace changes.
- Owner wallet bailout, salary, repayment, and election campaign cash/wallet legs now have focused account tests; web serialization exposes the resulting owner-loan and wallet-transfer totals.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity test_truck_system_and_scrip test_run_trace test_trace_codec test_banking_contagion test_plunder_labor test_frontier_policies test_owner_currency_transfers` — 143 tests passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — 50 turns completed with zero currency violations and zero unmatched actor cash at the end or across actor-turn statements.
- `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` — passed for the owner and election transfer changes.
- Wilderness trader settlement now posts linked trader-cash and homesteader-wallet
  legs, plus valued goods-advance and output-collection records. The actor-account
  test checks both cash closure and wallet receipts; compact traces point back to
  tile-qualified journal rows.
- `venv/bin/python -m unittest test_wilderness_trade_accounting` — 1 test passed
  for frontier goods movement, trader cash reconciliation, homesteader wallet
  receipts, and trace-to-journal references.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_wilderness_trade_accounting test_owner_currency_transfers test_frontier_policies test_supply_control_actor_strategy test_market_routes test_market_auction test_run_trace test_trace_codec` — 85 tests passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — the default three-nation 50-turn run completed with zero currency violations and zero unmatched actor cash on the final turn or across actor-turn statements.
- `venv/bin/python -m py_compile trade_settle.py sim_engine.py economy/actor_accounts.py metric_catalog.py test_wilderness_trade_accounting.py` and `git diff --check` — passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_market_routes test_market_auction test_supply_control_actor_strategy test_wilderness_trade_accounting` — 63 tests passed, including a foreign-currency auction receipt that now changes the trader wallet without falsely posting cash.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — the default three-nation 50-turn run completed with zero currency violations and zero unmatched actor cash on the final turn or across actor-turn statements.
- `venv/bin/python -m py_compile region_market.py economy/actor_accounts.py benchmark_supply_default.py test_market_routes.py` and `git diff --check` — passed.
- Cross-tile imported sales now post the seller's cash or wallet receipt on the source tile, linked to the destination purchase. The 63-test trade/accounting suite and the 50-turn default benchmark were repeated after this change; the benchmark still reports zero currency violations and zero unmatched actor cash.
- `venv/bin/python -m py_compile world_trade.py region_market.py economy/actor_accounts.py benchmark_supply_default.py metric_catalog.py test_market_routes.py` and `git diff --check` — passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_world_trade_accounting test_market_routes test_market_auction test_triangular_trade_and_luxuries test_supply_control_actor_strategy test_wilderness_trade_accounting` — 70 tests passed. Away-trader wallet purchases reconcile the home-tile wallet debit and destination seller cash receipt.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 4242` — 50 turns completed with zero currency violations and zero unmatched actor cash on the final turn or across actor-turn statements.
- `venv/bin/python -m py_compile world_trade.py econsim_two_region.py metric_catalog.py test_world_trade_accounting.py` and `git diff --check` — passed.
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
- `MPLCONFIGDIR=/private/tmp/wage-arrears-mpl venv/bin/python -m unittest test_plunder_labor test_web_client_parity` — 43 tests passed after wage-arrears repayment and UI account updates. `node --check web_client/client.js`, targeted Python compilation, and `git diff --check` passed.
- `MPLCONFIGDIR=/private/tmp/wage-arrears-mpl venv/bin/python benchmark_supply_default.py 50 4242` — default three-nation run reached turn 50 on 80 tiles with zero currency violations and zero unmatched actor cash on turn 50 or across all actor-turn statements.
- `MPLCONFIGDIR=/private/tmp/wage-exit-mpl venv/bin/python -m unittest test_plunder_labor test_run_trace test_web_client_parity test_supply_control_actor_strategy test_labor_shortage_wage_spike test_forex_accounting test_person_flows test_war_logic test_trade_route_epidemic_transmission` — 133 tests passed after wage-claim repayment, inheritance, remote settlement, and exit write-offs. Node syntax, targeted Python compilation, and `git diff --check` passed.
- `MPLCONFIGDIR=/private/tmp/wage-exit-mpl venv/bin/python benchmark_supply_default.py 50 4242` — default three-nation run reached turn 50 on 80 tiles with zero currency violations and zero unmatched actor cash on turn 50 or across all actor-turn statements.
- An adjacent construction-suite run found one separate failure: `test_07_operational_building_staffing_and_efficiency` remains at the 0.2 efficiency floor, including when run alone. The other tests in that suite passed.
- Full `unittest discover` was attempted but this environment's native pygame/OpenGL tests crashed the Python process (exit 139) before a summary could be produced; the focused simulation, rights, auction, route, and web parity suite remains green.
- Disease mortality attribution now records active illness as risk evidence and
  counts a death as disease-attributable only when the death draw crosses the
  pre-disease threshold because of the disease modifier. The fatality counter
  is written on the tile that the medical summary reads; the previous context
  lookup could leave it at zero. Probabilities and draws are unchanged.
- `MPLCONFIGDIR=/private/tmp/mortality-trace-mpl venv/bin/python -m unittest test_run_trace test_trade_route_epidemic_transmission test_person_flows test_war_logic test_metabolic_rift_and_riparian_ecology` — 43 tests passed. Targeted compilation and `git diff --check` passed.
- Resident census bridges now reconcile end-of-turn living residents by tile
  and nation: births, external entries, movement, deaths and causes, entity-role
  conversions, and changes in territorial membership are separate terms.
  Bridge rows link to retained birth/death/movement/role-conversion event IDs;
  unclassified exits are listed separately and downgrade confidence even when
  the arithmetic still reconciles. The metric inventory now
  marks resident counts and role changes as instrumented.
- `MPLCONFIGDIR=/private/tmp/population-bridge-tests venv/bin/python -m unittest test_run_trace test_person_flows test_web_server test_trade_route_epidemic_transmission` — 66 tests passed. A five-turn default three-nation trace emitted 20 resident bridges; all 20 reconciled and linked to source events. Targeted compilation and `git diff --check` passed.
- Legacy population instrumentation now records profession membership changes
  separately from the end-of-turn resident census. The trace identifies added
  and removed agent IDs and links available career, death, migration, and role
  events. Snapshots omit unchanged and zero-count categories to keep the new
  series compact.
- `MPLCONFIGDIR=/private/tmp/profession-population-tests venv/bin/python -m unittest test_run_trace test_person_flows test_web_server test_trade_route_epidemic_transmission` — 68 tests passed. In a seeded five-turn default-world run, the profession series emitted 182 events (113 changed snapshots), had no unexplained changes, and matched each tile's `total_population` history exactly. Targeted compilation and `git diff --check` passed.
- Corporate supply-control traces now link the ranked strategy to its advance,
  land, water, or charter submission and to the later negotiation or public
  decision. Failed submissions and output pauses produce explicit outcomes;
  pause evidence names released workers and the workforce-cap change.
- The supply-control actor suite passed 48 tests, trace/catalog tests passed
  37, and planner-gate/supply-rights tests passed 24. Python compilation and
  `git diff --check` passed.
