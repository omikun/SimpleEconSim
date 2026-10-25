# Economic response to supply and demand shocks

Date: 2026-10-24. Status: baseline and five-seed default-game paired screens
complete; initial mechanical/formula audits applied. Treasury-flow writer
gaps have been traced and instrumented; a fresh single-arm audit now closes.
The refreshed four-arm audit, cross-scenario robustness, full stock/welfare
accounting and empirical calibration remain.
Preserve game rules during diagnosis; put any eventual economic fixes in
separate changes.

## Implementation progress

| Phase | Status | Evidence / remaining work |
|---|---|---|
| 1. Baseline evidence and case studies | Complete for the selected 20-turn trace | Added streaming panel extraction and a baseline report. It identifies the furniture-input and local-food cases below; the trace does not cover every household, balance or in-transit stock. |
| 2. Controlled shock experiments | Five paired 20-turn default-game seeds complete | Seeds 4242–4246 match complete canonical state at turn 7 for both shock pairs; original seed-4243 no-op attempts are excluded. Active role targets are selected and recorded per seed. The paired report gives per-seed effects and coverage. |
| 3. Criteria and interpretation | Market gates pass in all ten valid seed-pairs; treasury source legs instrumented and one fresh arm audited | Supported structural/formula and account-closure checks pass on the original four seed-4242 traces. A fresh seed-4242 wood control passes 60/60 account closes and 60/60 treasury-flow reconciliations after the source-flow updates. Rerun the other three arms before closing this phase. No recovery-time or empirical-realism claim is made. |

The old `market_price_stabilization_plan.md` describes an earlier price rule.
Current `region_market.update_price_ref` already demand-gates positive scarcity
and discounts negative inventory scarcity only when demand is slack. Treat the
older diagnosis as historical; do not implement its proposed formula changes
without reproducing a current-source failure.

### Implemented paired screens

`economic_shock_experiment.py` starts each control and treatment in a fresh
process, fixes Python/NumPy/hash seeds, records a complete canonical state digest
after turn 7, and uses the same default-game seed in both arms. It writes audit
events when the shock is applied and removed, retains compressed traces, and
compares market panels and end-of-turn state metrics.

- `wood_supply_reduction`: at c50, multiply the wood recipe output by 0.5 for
  turns 8–11 and restore it before turn 12 when c50 has active wood producers.
  Otherwise select the active tile with the most wood producers (ties use
  downstream furniture producers, household count, then stable tile name). This
  is a temporary productivity/physical-supply intervention. It destroys no
  stock and its result must be measured from realized wood production and offers.
- `furniture_demand_increase`: raise desired furniture inventory by a factor of
  1.5 for every other eligible resident in c50 on turns 8–11 when c50 has an
  eligible cohort. Otherwise select the tile with the largest eligible cohort
  (ties use furniture-producer count, then stable tile name). Assignment is
  deterministic by agent ID. Unit orders are integral and rounded up, so at the
  baseline one-unit target the treated cohort target is two units; it creates no
  transfer or money. Household budgets, credit and purchases of other goods
  remain endogenous and are measured as spillovers.

The private market hook is absent by default and only reads explicit
`_analysis_demand_target_overrides`. Submitted buyer-order events record the
adjusted target and its unshocked value when a treatment override applies.
The first valid run was a diagnostic screen at default seed 4242. Tile names
are not stable economic roles across seeds: the initial seed-4243 attempt found
no wood producers and no eligible households on c50, making both interventions
no-ops despite a matched turn-7 state. Those original attempts are excluded
from effect summaries. The selector now prefers c50 only when that shock has
an active target, otherwise it deterministically chooses a relevant active
tile; every corrected arm records its tile and selection evidence, and paired
arms must select the same tile. The seed-4242 run predates the selection
metadata, but its intervention event records 11 affected wood producers and
67 of 134 eligible furniture-demand residents, and the corresponding market
panels show realized treatment responses.

### Results from the default-seed paired screen

The runner and interventions were committed at `dd850255bea13d107733a859fd13b0a8ac315448`.
All four 20-turn runs use seed 4242 and have exactly matching control/treatment
canonical state at turn 7 (`94febc162853ef19d951d6720b4a58ea9be4543944e2675f31fbc8ce7c318cd9`).
The trace-backed comparison and audit summary are in
`planning/reports/economic_shock_screen_seed4242.md`; full compressed traces
remain under ignored `tmp/traces/`.

- **Wood supply screen:** halving c50 wood recipe output for turns 8–11 reduced
  realized c50 wood production by 39 units and recorded wood offers/sales by
  60 units cumulatively over the four shock turns. Submitted wood bids rose by
  73 units in the matched panel. Traced nonfood wood consumption was 112 units
  in control and 96 in treatment over all four turns. The c50 furniture
  reference was already at its cap, and furniture sales did not fall during
  the intervention window; this seed therefore demonstrates the physical-
  supply first-order response but not a clean downstream price/welfare
  response. Furniture and food shortfall indicators are reported separately.
- **Furniture demand screen:** desired inventory rose for 67 of 134 eligible
  c50 residents (one to two units at the start). Submitted furniture bids
  rose by 8 units over turns 8–11, but cumulative fills were unchanged. The
  posted reference remained capped at 50; paid-VWAP changes were small and
  mixed in sign (mean treatment-minus-control paid VWAP -0.02 across four
  paired turns). Traced furniture consumption was 24 control versus 29
  treatment units, but only 3/4 turns had paired consumption records. This is
  evidence that a stated preference/stock-target shock does not automatically
  become extra fills or a clear price response when cash, stocks and the supply
  cap bind; realized-consumption coverage is incomplete.
- In both screens the c50 household food-shortfall units showed no net change
  in the four-turn shock window. This does not establish no welfare spillover:
  intake events are not a complete census, and the single seed is noisy.
- The supply treatment changes later event/RNG paths. Turn-7 pairing proves
  identical pre-intervention starts, but turn 12–20 differences combine the
  lasting treatment state with divergent random draws. Do not label that path
  a seed-aligned recovery effect.

The report now includes import and total-offer deltas, nonfood consumption,
shock-window totals with observed-turn denominators, and per-run audit gates.
`--reuse-existing --audit` reanalyzes the saved traces without rerunning the
simulation or creating another decoded export.

### Five-seed default-game screen

The corrected paired sample for seeds 4242–4246 is summarized in
`planning/reports/economic_shock_multiseed_default.md`, with machine-readable
paired effects in `planning/reports/economic_shock_multiseed_default.json`.
Each control/treatment pair has the same complete turn-7 state; both shock
pairs pass the market-mechanics gates in all five seeds (10/10 pairs). The
screen uses active local targets selected for the relevant economic role:
wood targets are c50, c59, c76, c56 and c78; furniture-demand targets are c50,
c74, c74, c78 and c71. Currency is preserved per seed and paid-price effects
are summarized as within-seed percent changes.

- The temporary wood-output reduction lowered target-tile production in all
  five seeds (−9 to −54 units over turns 8–11; mean −35.8) and lowered offered
  supply/sales in all five (−10 to −87; mean −52.4). Submitted bids increased
  in all five (+10 to +73; mean +38.6), target-tile wood consumption fell in
  all five (−6 to −34; mean −20.6), and paid VWAP increased in observed rows
  (+0.104% to +4.362%; mean +1.348%). Price coverage is 19/20 shock-window
  seed-turns and selected downstream measures have lower coverage, as detailed
  in the report.
- The furniture inventory-target increase raised submitted bids in all five
  seeds (+7 to +12; mean +8.6), but offered supply (mean +0.6), sales (mean
  +0.4) and production (mean +0.2) changed little. Paid VWAP changes were
  small and non-positive in this sample (−0.461% to 0%; mean −0.099%).
  Furniture-consumption coverage is 14/20 shock-window seed-turns and its
  observed effects vary from −3 to +5 units.
- Observed food-shortfall deltas are zero in both screens, but the wood-screen
  food measure is missing for some seed-turns. This is not a welfare finding.
  The five-seed sample is descriptive, has no confidence interval, and does
  not establish historical realism. We do not infer recovery time from the
  post-shock traces: the intervention can change later random-number paths,
  and a recovery tolerance was not operationalized for this screen.

This is evidence for the immediate local mechanisms tested: reduced physical
wood output tightens offers/sales and raises bids/prices; extra furniture
desired inventory creates bids more reliably than it creates supply or fills
under the current cash, stock and reference-price constraints. It does not
establish a general equilibrium response or a welfare improvement/loss.

## Questions and standards

Assess three things separately: mechanical correctness (settlement, accounting,
formula and source consistency), plausible economic behavior under stated
institutions/constraints, and calibration against empirical evidence. A formula
replaying correctly does not establish realism. A plausible price sign alone
does not establish successful allocation, household survival or recovery.

Identify whether a problem is physical scarcity, insufficient purchasing power,
market access, labor/capacity, input bottlenecks, credit or price-setting rules.
Distinguish needs and desired inventory from submitted funded demand, offers
from physical supply, and posted reference prices from actual paid prices.

## Existing coverage inspected

| Source | What it checks | What remains unproven |
|---|---|---|
| `test_market_auction.py` | Exact offers, bid/ask crossing, midpoint settlement, household food reserve, higher bids/paid price under excess demand, no corporate auction bypass | Whole-economy adjustment and recovery |
| `test_run_trace.py` | Reference replay, rise/fall, no-order decay, input floors, oversupply deflation, productive input priority, career/production links | Multi-turn matched shock effects and stable feedback |
| `test_market_affordability_trace.py` | Liquidity/bank draws and zero/positive order evidence | Distribution of unmet need after income shocks |
| `test_supply_control_actor_strategy.py` | Lower water allocation under drought, real public crop purchases, negative-margin output pause/workforce release, actor accounts | Full drought-to-harvest-to-price-to-welfare response |
| `test_fertilizer_supply_and_blockade.py` | Fertilizer stock/production multiplier, depleted-soil harvest penalty, blocked inflows, synthesis and subsidy transfers | Dynamic price/import/labor adaptation; career test only checks an allowed choice |
| `test_capitalist_propagation.py` | Luxury demand/shadow cash valuation, investment, pending-capacity expectations and an alternative investment choice | Actual damping of repeated boom/bust cycles; test name alone is not long-run evidence |
| `test_food_security_recovery.py` | Meal reserves, relief conservation, funding, household access, one-turn haulage delay | Robust aggregate welfare recovery across shocks/seeds |
| `test_market_routes.py`, `test_supply_rights.py` | Route decisions and rights/charter restrictions on real goods | Spatial adjustment speed and failure under disruption |
| `benchmark_supply_rivalry.py` | Matched scenario starts and 20-turn policy outcomes for growers, mills and trade | Formal causal shock/recovery assertions and a measured no-action counterfactual in the reported default loop |
| `benchmark_supply_default.py` | Longer-run supply/control accounting and sector diagnostics | Designed symmetric supply/demand shock matrix |

These are source-inspection findings, not a claim that the tests currently pass.
No comprehensive controlled shock/recovery suite was identified in this review.
Before implementation, run the focused relevant tests and record current results.
Review `market_price_stabilization_plan.md` as historical hypotheses; check current
code rather than assuming its earlier diagnosis or parameter proposals still apply.

## Initial 20-turn trace screen

Source: `tmp/trace-fat-analysis/prototype.source.ctr`, default seed 4242,
scenario `None`, run ID `a6dde09ee33543629148c2f619351ec4-1`, generated from
source commit `b523f5f939453f9de09f3fbba874ea99ecd76616`. The compact trace has
884,682 records including its metadata header (884,681 event rows), over turns
0–20. The reusable streaming extractor is `economic_shock_analysis.py`; the
curated report is `planning/reports/economic_shock_baseline.md`. The command
also writes a compact tile/good/turn panel to ignored `tmp/` storage. No full
decoded export was created. This is an observational startup run without a
designed shock or counterfactual. It cannot establish a causal impulse response.

- All 12 recorded furniture reference markets are at the hard price cap of 50
  by turn 10 and remain at 50 on turn 20. Reference caps do not cap actual paid
  prices: individual settlements can exceed 50. Diagnose supply/input access,
  bid funding, selection rules, production and entry before changing the cap.
- Wood references rise strongly within each currency area. Turn-1 to turn-20
  market means are CNY 1.073 to 3.127, JPY 1.044 to 2.900, and USD 1.125 to
  3.388. Do not average prices across currencies without explicit FX conversion.
- Turn-10 food offers exceed submitted bids substantially in the CNY markets
  (6,591 versus 564 units) and JPY markets (6,960 versus 555), while USD markets
  show the opposite (318 versus 681). CNY/JPY reference prices are floor-bound
  at 1. These aggregates motivate local access/affordability and trade diagnosis;
  they do not prove every tile has a surplus or that unmet household needs vanish.
- Zero-output evidence includes 1,831 independent-production missing-input
  outcomes, 5,837 failed independent-production draws, 1,015 independent strike
  outcomes, 61 firm outcomes with all employees withholding/revolting and 10
  with no employees. These are event counts, not production-loss quantities.
- Five update examples move against a simple contemporaneous demand-ratio sign
  rule. Inspect recent-price blending, old references and floors before labeling
  these errors. Example: turn 7, c35 food event ending `:249526`, excess-demand
  ratio 1.2065 but reference delta -0.000266; past-price blending is recorded.
- Intake-record counts vary greatly by turn (50 at turn 1, 1,314 at turn 10,
  1,021 at turn 20). Verify census and emission-path coverage before using their
  shortfall fraction as a population hunger rate. Missing clearing records are
  explicitly counted in the extraction and must not be interpreted as zero trade.

First investigation: wood-to-furniture bottleneck and persistent furniture cap.
Second: food abundance versus purchasing power/access across locations. Identify
whether these are startup transients, constraints with credible causes, or
self-reinforcing failures before designing large scenario sweeps.

### Phase 1 findings and coverage gaps

The trace-backed case studies refine those investigations:

- In CNY tile `c50`, the furniture reference reaches its 50 cap at turn 9 and
  remains there through turn 20. Paid VWAP reaches 61, showing that the
  reference cap does not cap transaction prices. At turn 10, bids are 50,
  offers and sales are 2, output is 1, and 17 zero-output records cite missing
  wood. This is evidence for an input bottleneck alongside tight supply, not
  proof that the price trajectory is caused only by wood scarcity. The paired
  experiment must also report labor, producer inventory, funding and entry.
- Food access is location-specific. At turn 10 in JPY tile `c10`, offers are
  957 against 166 bids and the recorded intake cohort has no shortfall. At USD
  tiles `c46` and `c59`, offers are 59/126 against 249/191 bids, while
  119/135 and 104/126 recorded intake rows show shortfalls of 303/214 units.
  Their production totals are 260/313, which do not equal saleable or accessible
  stocks. This comparison rejects a global-surplus inference; it does not yet
  distinguish local physical supply, purchasing power, household stocks,
  trader allocation, transport or relief.
- The report distinguishes actual paid VWAP from reference prices, and demand,
  offers, sales, production and producer stock. The panel records absent
  clearing/VWAP observations explicitly. The analyzer records 1,413
  reference-price update/decay events (1,213 price updates plus 200 no-order
  decay events); 456 have no paired clearing summary. This is a coverage
  difference, not a finding of 456 zero-trade markets.
- Household intake is not a stable census denominator: trace records are
  heterogeneous by tile and turn. The existing trace also does not provide a
  complete cohort panel or complete wage, profit, credit and in-transit stock
  histories. Matched experiments must add state snapshots for those outcomes
  and label trace coverage separately.

The focused existing suite passed: 77 tests across auction, affordability,
fertilizer/blockade, food-recovery and supply-control behavior; a second set of
81 trace, routes, rights and capitalist-propagation tests also passed. These
confirm mechanisms and trace contracts, not the economy-wide shock response.

## Phase 1 — Baseline evidence and causal case studies

1. Freeze commit, scenario/engine, seeds, configuration and trace boundaries.
   Reconcile samples with live histories/censuses and audit needed formulas,
   source links, zero-trade paths and actual transfer legs. Document gaps.
2. Build tile/good/turn panels with explicit currency and coverage flags. Track
   quantity-weighted transaction price, reference/ask/bid distributions, bids,
   offers, fills, unsold stock, unfilled funded orders, zero-order reasons,
   production, input inventories, capacity, employment, wages, profit/cash,
   shipments/departures/arrivals, consumption, hunger, mortality and entry/exit.
   Keep producer/household/trader/in-transit inventories separate; distinguish
   stock from turnover and production from offers. Do not treat no trade as a
   zero price or use reference substitutes as actual transactions.
3. Trace named furniture firms/artisans backward from low output and reference
   caps to inputs, wood fills, available funds, labor, skill/tenure and producer
   entry. Trace forward to profits, wage payments and household purchases.
4. Trace food-shortfall households against local offers, their own stocks/cash,
   funded bids, access/rights, allocation priority, transport, relief and meals.
   Separate local scarcity from aggregate abundance and effective demand failure.
5. Produce plots of levels and changes with event IDs for representative causal
   chains. Report unexplained residuals separately from behavioral hypotheses.

## Phase 2 — Controlled shock design

Use three levels: a small auction with fixed actors/stocks/cash for mechanism
isolation; `supply_rivalry` or labor-frontier for cotton-to-cloth and trade;
the default game for heterogeneous households and wood-to-furniture. Preserve
the scenario's native stepping path. Identify intervention hooks before resets,
production, bidding or allocation, so a scenario does not overwrite the shock.

Start with paired 20-turn response windows: seven pre-shock observations,
shock turns 8–11, removal at turn 12, recovery through turn 20. This is a screen.
If startup dominates, create a settled prehistory/checkpoint first and observe
20 further turns. Define settled history from measured trends/variability rather
than assuming seven startup turns imply equilibrium. Extend recovery to 50/100
turns only for persistent gaps, slow capacity or cycles the short screen cannot resolve.

| Experiment | Intervention | Main response to measure |
|---|---|---|
| Negative/positive physical supply | Output/productivity or available water +/-25%, then +/-50%; temporary and persistent variants | Output, stocks, paid price, fill rate, consumption and recovery |
| Intermediate input shortage | Wood or cotton supply reduction at the production source | Upstream prices, input rationing, downstream output and margins |
| Demand increase/decrease | Change durable-good inventory targets/spending preferences +/-25%, then +/-50%, with actual budget limits | Funded bids, fills, stocks, prices and crowding out of other spending |
| Income/credit disruption | Explicit funded transfers or credit restriction, separately identified from preference changes | Affordability, arrears, consumption, solvency and distribution |
| Trade interruption/restoration | Route capacity/cost/blockade with physical shipments and timing | Local price dispersion, diversion, substitute supply and arrival lag |
| Compounded stress | Supply loss plus income/credit/trade constraint after individual cases work | Propagation, insolvency, relief capacity and irreversibility |

Never implement a supply/demand shock by editing the price to get the expected
answer. Inventory destruction must record a physical loss. Transfers/procurement
must identify a payer and conserve cash unless an explicit monetary injection
is the experiment. Preference changes reallocate budgets and may affect other
goods; report spillovers rather than calling the change economically isolated.

For each checkpoint, branch into unchanged control and shocked treatment with
identical starting state and RNG. Restore into fresh processes because domain
registries are process-global. Fix Python/NumPy/hash seeds and intervention
timing. Shared initial RNG does not guarantee draw-by-draw alignment after
branches take different paths; use multiple paired seeds and report variation.
Record exact interventions, affected IDs, before/after values, duration and units
as audit evidence, including removal. Check that no unintended budgets, actors,
rules or policies changed. Analyze endogenous policy/AI responses as part of
the full experiment; disable them only in explicitly isolated mechanism fixtures.

## Phase 3 — Criteria and interpretation

- Mechanical gates: finite/nonnegative physical stocks where required, no
  overselling/double settlement, reconciled monetary flows including authorized
  creation/loss, conserved goods net of production/consumption/loss, and no
  missing required sources. Do not require a debt-financed economy's money
  stock to remain constant when its rules permit creation/destruction.
- In isolated unconstrained fixtures, supply loss should reduce available units;
  excess funded demand should pressure paid prices/fills in the expected
  direction; gluts should clear through lower prices or visible unsold stocks.
  Integrated outcomes may differ because income, composition, floors, credit
  and policy move too. Explain those channels rather than imposing universal signs.
- Measure treatment-minus-control response paths, peaks, cumulative consumption
  and output losses, inventory buffer duration, unmet funded demand and unmet
  need, price dispersion, cap/floor occupancy, entry/career changes, defaults,
  layoffs and recovery time. Define recovery as a predeclared tolerance around
  the paired control for several consecutive turns, using absolute tolerances
  for near-zero quantities. No recovery within the window is censored, not zero.
- Examine quantities alongside prices: floor/cap pinning can hide pressure;
  demand collapse from hunger/death is not successful recovery. Track original
  cohorts and population/territory changes; report per-survivor and total welfare.
- Look for persistent one-way inflation, vanished inventories, profitable sectors
  unable to obtain inputs, unexplained zero orders, zero-activity market lockup,
  synchronized over-entry, growing oscillations and premature instantaneous
  trade/labor/capacity adjustment. Diagnose with source events before fixes.
- Predeclare comparisons and tolerances before intervention runs, report seeds
  and uncertainty, and separate exploratory discovery from regression assertions.
  Start at seeds 4242–4246 for default and 812–816 for supply rivalry; five pairs
  are a diagnostic sample, not precise calibration. Expand if conclusions vary.
- For claims of empirical realism, select the relevant historical setting and
  primary evidence for elasticities, inventory buffers, response delays and
  consumption effects. Nominal price levels and a cap of 50 have no standalone
  empirical meaning. Mark calibration as pending until that comparison exists.

### Applied gates and treasury residual diagnosis

The four seed-4242 traces were checked with `economic_shock_experiment.py`
market gates and the existing `trace_audit`/`trace_coverage` tools.

- All four runs pass finite-value and observed settlement-bound checks across
  their core-good market panels: no negative sales, sales above funded demand
  or recorded supply, negative production/inventory, or contradictory
  `no_paid_sale` flags were found. Missing clearings remain missing, not
  synthetic zero trades.
- All four runs pass the structural and supported-formula audit with zero
  reported audit issues. This is a bounded supported-formula check, not full
  causal coverage; the audit reports complete causal coverage as false.
- Nation-account closure passes in all runs: 60 of 60 closes verified, zero
  account-closure gaps.
- The original four seed-4242 traces predate the latest instrumentation fix and
  do not pass treasury flow attribution: they fully attribute 46/60 turns in
  wood control and demand control, 50/60 in wood treatment, and 53/60 in demand
  treatment. Their absolute residual totals are 719.8684, 719.8684, 660.9925
  and 667.0668 in mixed account currencies/units. These are gap indicators,
  not a converted national total.
- The repeated US T4 control residual was exactly identified. The nation
  treasury moved from 1141.705923 to 1353.742656 (+212.036732); recorded
  flows summed to +443.044498, leaving -231.007765. The government cash
  account close shows a `government_distribute_welfare_cash` write from
  442.867715 to 211.859949, also -231.007765. The 31 positive
  `government_cash_obligation_payment` receipts and +0.176783 deposit interest
  were correctly recorded; the outgoing welfare transfer was missing from
  the nation-flow list. `_trace_public_transfer` had not received the active
  region and could not find a traced entry in that local government's
  `regions`. The benefit methods now pass their active region when recording
  baby-bonus, UBI, parental-leave and welfare summary legs. A regression test
  exercises all four with an empty `government.regions` list.
- An intermediate control trace after the welfare fix resolved the US T4
  residual and showed `welfare_distributed: -231.007765`, but left 13 residual
  turns. Those turns exposed government-account medical-patient debits, estate
  cash/probate-deposit receipts and provincial food-haulage spending. These
  are now emitted as nation-level signed flows at their mutation sites, linked
  to account-write or transfer evidence. A second fresh seed-4242 wood-control
  trace passes all 60/60 public-account closes and all 60/60 treasury-flow
  reconciliations; the absolute residual total is 6.3e-12 (floating-point
  noise). Structural and supported-formula checks report zero issues, with
  complete causal coverage still false. Rerun the other three seed-4242 arms
  with the same audit before replacing the historical paired counts or
  claiming this gate for all four.

The paired report distinguishes market mechanics from ledger attribution. The
current mechanical gate does not prove goods conservation across household,
producer, trader and in-transit stocks; those stock boundaries remain a separate
accounting follow-up.

## Deliverables and next action

The compact baseline report, the seed-4242 case studies, and the corrected
five-seed default-game summary are complete in
`planning/reports/economic_shock_baseline.md`,
`planning/reports/economic_shock_screen_seed4242.md`, and
`planning/reports/economic_shock_multiseed_default.md`. Continue in this order:

1. Rerun the other three seed-4242 arms with deep audit after the treasury-flow
   source updates. Verify 60/60 account closes and treasury-flow reconciliation
   in every arm; investigate and report any remaining residuals.
2. Add a scenario-aware intervention adapter and test supply rivalry on seeds
   812–816. Confirm that native scenario stepping does not overwrite the shock;
   compare local production, shipment, arrival, price and welfare response.
3. Add stable-cohort household outcomes, wages/profit/credit and separate
   producer, trader, household and in-transit stock measures before concluding
   on welfare or goods conservation.
4. Define and calculate an explicit, coverage-aware recovery measure for
   future paired runs; post-shock RNG divergence limits causal interpretation.
5. Select historical primary evidence for the relevant setting before making
   empirical-realism claims; until then this is a code-behavior study.

Use streaming extraction and compressed traces; full decoded exports are
unnecessary. Indexed module/window access (including SQLite versus compressed
trace plus sidecar tradeoffs) remains a trace-format follow-up in
`compact_trace_format.md` and does not block the current paired analysis.

The current screens do not establish a broken economic rule: the wood shock
reduces physical output and offers, while the furniture-demand shock raises
orders without reliably raising fills or paid price under a binding cap. Add
focused economic regression assertions only after multi-seed or scenario tests
confirm a repeatable failure. Keep any eventual rule fix separate, rerun the
paired cases and unaffected controls, and do not tune thresholds merely to pass.
