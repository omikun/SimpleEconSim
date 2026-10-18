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

## Phase 1 — actor accounts: core implemented, full reconciliation pending

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
- Recent 50-turn default runs created 145 firm and 294 grower account rows,
  10–13 supply proposals, and no active contracts/charters at the end. Across
  seeds 4242–4244, final-turn sums of absolute unmatched actor cash movements
  ranged from $21,015 to $31,338, showing that a full per-actor cash bridge is
  not complete. Some
  unmatched movement is from legacy systems that have not been connected to this
  journal; do not read the displayed recorded result as complete profit. The
  benchmark now names the eight largest unmatched actors; the top absolute gap
  was $1,713.25 for a grower and $1,463.82 for a corporation, giving the next
  instrumentation pass concrete targets.
- Bank deposit/withdrawal, loan issuance, and deposit interest now post named
  cash events; turn accounts separately expose bank deposits and outstanding
  bank principal. Loan repayment, default, and write-down adapters remain open.
- Remaining gate work: complete loan repayment/default and
  farmgate-to-route-to-import accounting for every cargo source. The latest
  default runs also expose large unposted actor cash changes; scrip, FX, and
  shipment postings cover some paths, but the full cash bridge is still open.

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

- Local FX desk conversions now record their home-currency cash leg and the
  foreign amount/rate in the same economic event; a focused account test checks
  that this leg reconciles. Bank deposit/withdrawal adapters remain open.
- Route shipments now carry a stable shipment ID plus the trader's source cost
  basis, freight per unit, and source currency. Arrival makes a matching
  import-lot record; destination auction fills decrement that lot and link the
  paid destination price back to it. The actor account and both clients show
  actual imported input unit prices; the account also exposes shipment IDs,
  source cost, and freight as separate values.
- The source cost is the trader's weighted acquisition cost at posting. It is
  not yet a complete named farmgate receipt ledger for every way cargo can be
  gathered, and parked/re-routed legacy cargo does not retain the same link.
  FX and tariff conversions also remain separate cash legs rather than a fully
  normalized per-shipment delivered-cost calculation.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python -m unittest test_supply_control_actor_strategy test_supply_rights test_market_auction test_market_routes test_web_client_parity` — 63 tests passed after bank account, campaign-currency, and linked shipment-lot additions.
- `node --check web_client/client.js` — passed.
- `git diff --check` — passed.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_rivalry.py` — 12 matched runs, zero reported currency violations.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_rivalry.py 812 813 814` — repeated after shipment linking; all 12 branches still report zero currency violations.
- `MPLCONFIGDIR=/private/tmp/codex-mpl venv/bin/python benchmark_supply_default.py 50 <seed>` — 50 turns completed with zero currency violations for seeds 4242, 4243, and 4244 after the campaign-transfer fix.
- Full `unittest discover` was attempted but this environment's native pygame/OpenGL tests crashed the Python process (exit 139) before a summary could be produced; the focused simulation, rights, auction, route, and web parity suite remains green.
