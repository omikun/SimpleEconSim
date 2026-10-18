# Causal run trace: implementation status

The live server writes one compact `.ctr` file per world generation to
`tmp/traces/`. A bounded recent ring supports live inspection. Every completed
turn has a hash checkpoint. The old collective report remains available
separately.

Remaining work is specified in the [completion plan](causal_trace_completion_plan.md).
Entries below describe installed probes, not uniformly verified end-to-end
causal coverage.

## Inspect a run

```bash
venv/bin/python trace_report.py --run tmp/traces/RUN.ctr --turn 12 --entity tile:Delta --good food --metric goods.price --verify
venv/bin/python trace_coverage.py --run tmp/traces/RUN.ctr
```

The web client queries `/api/trace?turn=12&entity=tile:Delta&metric=goods.price`
with `offset` and `limit` for paging. `/api/trace/download` exports the live
JSONL. In the Comparison view, the tile Goods tab has a **Why?** button for
food prices; the national Macro tab has **Why AI?** and **Why $** buttons;
the FX matrix has a **Why?** button for each quoted currency pair.

## Recorded with exact calculation or operation inputs

- Tile market demand, supply, price reference and decay, transport price,
  private/public paid sales, producer inventory, production, nominal GDP,
  population count, and cost of living.
- Local cost-of-living calculations record fixed basket goods and weights,
  component reference prices, regional/climate multipliers, local currency, and
  a replayable total. National cost-of-living means link member baskets and
  include coverage, territory membership, currencies, and arithmetic
  continuing-member versus territorial-composition changes.
- National reference prices are recorded per priced good with tile-level price
  links, territory membership, coverage, and currency context. The legacy
  national food-price history is separately replayed with its original
  denominator, missing-recipe-as-zero rule, and empty-nation fallback. National
  prices are intentionally unconverted means of local-currency values, with
  mixed currency flagged.
- Live market order chains record positive buyer quantities with current stock,
  household or input-need branch, cash availability and recipe context; local
  seller offers record available stock and reserves. Same-turn production,
  seller asks, accepted demand/supply totals, replayable market pressure, price
  updates, and paid sales link through event IDs where those events exist.
  Charter restrictions retain submitted and permitted quantities. Imported
  sales now trace source acquisitions through route departure and arrival,
  imported supply totals, delivered quotes, and settlement. Each shipment ID
  keeps its owner, quantity, route history, and parked state; legacy unlinked
  cargo is labeled separately. Route loading records queue depth and
  congestion-based delay; countdown and hold events identify strike, blockade,
  and quarantine pauses. Food retention, freight affordability limits, and
  freight payments are also recorded. Zero bids and local offers are grouped
  by reason per good, retain affected agent IDs and decision inputs, and link
  to demand/supply totals.
- The standalone `econsim.py --trace PATH.ctr` option writes price mutations,
  final snapshots and reconciled per-turn bridges. Its decay and market update
  formulas replay from captured inputs; trace-on/off one-turn checks matched
  final stats and RNG state.
- Corporate and independent production rolls use the existing RNG draws.
  Price updates link the prior clearing summaries used as market samples.
- Collective bargaining and authority events enter the run trace and preserve
  within-strike event order. Pre-production workforce records show scheduled,
  capped, and available worker-hours by employee and firm. Corporate output,
  including zero output caused by withheld labor, links to workforce evidence;
  independent production links to commons activity when foraging took time
  from the main occupation. Labor or subsistence production records link to
  zero-offer summaries, market supply, demand/supply pressure, and price updates.
- Faction grievance sources, protest energy, unrest roll and takeover/garrison
  result, and legitimacy drift. National population, GDP, cost of living, and
  protest energy have member tile values and aggregation rules.
- Bilateral FX mid changes record reserve ratio, pressure, PPP, regime, and
  band; bank conversions, funded turn-zero trader floats, bilateral order
  matches, and same-currency cash/wallet conversions record actual transfers.
- Soil fertility and food nutrition updates record farming intensity, crop
  practices, enclosure, fertilizer, regeneration, and bounds. Air, water, and
  soil pollution updates record emissions, controls, dispersion, runoff, and
  downstream river advection; ecological metrics are sampled at turn end.
- Migration pressure gates record wage memory, food price differentials, risk,
  threshold results, eligible pool sizes, and each resident's departure or
  arrival, including destination and carried wealth.
- Disease onset records exposure inputs and RNG draws; treatment records
  provider, payer, cure chance, outcome, and unaffordable cases. Post-treatment
  case counts, spending, untreated cases, and fatalities are sampled. Public
  treatment payments that leave government cash enter treasury reconciliation.
- Non-fatal health attrition records each agent's air, water, pesticide, soil,
  and nutrition contributions, alongside their pollution and food exposures.
- Birth outcomes record the fertility gate, existing random draw, parent food,
  and newborn endowment. Water-contamination infant deaths record the water
  level, sewer condition, survival probability, mortality draw, and turn total.
- Demographic, battlefield, state-violence, political-clash, and assassination
  deaths share one registered-person counter and tile/national totals. Infant
  losses remain a separate event because they were never living residents.
  Disease presence is recorded as a risk factor; a demographic death is counted
  as disease-attributable only when the actual draw exceeds pre-disease risk but
  falls within disease-adjusted risk. The counter is recorded on the source tile
  consumed by the disease summary. Population bridges that reconcile opening
  residents with births, external entries, departures/arrivals, deaths, role
  conversions, and territory membership changes are emitted per tile and nation.
  The profession-count population series is separately defined as the sum of
  output-coded agents and traders. Per-profession count changes record entering
  and leaving agent IDs and link deaths, career switches, migration, and role
  changes where their events exist. These counts are recorded in the local
  metrics phase before that turn's migration phase; the resident census is the
  end-of-turn measure. National profession counts use territory membership at
  snapshot time. Military people remain resident-counted while their status and
  transfers are traced separately.
- Trade-borne plague records route contagion loading probability and draw,
  quarantine blocks, cargo availability, vulnerable population, and the
  selected newly infected person.
- Named cash obligations record assessment basis, due date, debtor and creditor,
  interest, payment, balance remaining, and rent collected or outstanding.
- Wage arrears record the original shortfall, oldest-first repayments, worker
  cash or wallet receipts, and the firm payroll reserve. Migrating claimants
  keep the receivable; worker death transfers it to heirs or probate recipients.
  Firm exit uses remaining cash first and records any limited-liability
  write-off. Actor statements and both clients expose accrual, collection,
  inheritance, and loss.
- Bank credit records requested and approved amounts, reserve capacity, frozen
  status, rates, borrower type, and repayments split into principal and interest.
- Deposit interest, sovereign default write-downs, recapitalization, and bail-ins
  record capital changes, affected depositors, freeze state, and funding source.
- Sovereign bank recaps now pair each treasury debit with its bank-capital
  increase under a shared operation ID and link the cash record to the capital
  change. The transfer is split per bank for accurate reconciliation.
- Deposit bail-ins record each depositor's balance loss and matching bank-equity
  gain as a non-cash conversion. The aggregate bank event links to affected
  depositors, and faction loyalty and legitimacy changes link back to the
  resolution.
- Sovereign bond purchases, proceeds, domestic underwriting, coupons,
  maturities, defaults, and early redemptions record signed nation treasury
  flows and the bond terms. These and campaign Caisse payments use the shared
  `treasury_transfer.v1` contract, with operation IDs, payer/payee identities,
  and government cash balances before/after. Cross-currency numeric transfers
  flag that no conversion took place. Domestic underwriting states when bank
  cash is not debited. Municipal sewer bond funding records the contractor
  credit as `finance.cash_creation` and flags its missing source-side cash
  mutation. Caisse payer and creditor legs pair under one operation ID.
- Campaign Caisse debt records principal revisions, concessions, defaults,
  creditor collection assignments, payments, and signed Egypt/creditor treasury
  flows for assigned revenue interception.
- Egypt project construction, upkeep, and repair wages include treasury and
  worker cash balances. District reserve recalls and revenue-office remittances
  record paired operation IDs whose signed treasury legs net to zero. Grain
  entitlement links each carrier wage to the owner's food inventory reduction
  and the recipient's calorie/deficit change.
- Public baby bonuses, scaled UBI, parental leave, welfare, and legacy tax
  receipts use `treasury_transfer.v1`, including treasury cash before/after,
  recipient IDs, and scale/funding details. Group-benefit recipient balances
  are marked as not individually captured.
- Tariff receipts record separate national and local-port treasury credits under
  one operation ID, including allocation and balance evidence. Emergency food
  levies record donor food inventories, protected reserves, and the matching
  government food-stock increase.
- Routine government food purchases record per-seller cash and food inventory
  balances. The treasury payment event links to the matching goods-sale event;
  the previous aggregate spending record no longer double-counts the flow.
- Egypt scenario harvest purchases, private warehouse sales, public purchases,
  and requisitions have linked cash and goods events with exact actor inventories.
  Unpaid requisitions also link the resulting unrest and legitimacy changes.
- Construction steps record material purchases, required and available inputs,
  navvy hiring and pay, progress multipliers, stall causes, and completion.
- Battles record initial strengths, casualties, winner, and conquest. War-side
  cohesion and posture updates expose supply runway, territorial losses, and
  political shocks; peace reparations enter treasury reconciliation.
- Bilateral diplomacy changes show ideology, trade volume, treaty pull, and
  betrayal memory; active wars explain relation locks.
- Treasury phase boundaries, tax receipts, tariffs, government borrowing and
  loan service, food spending, army payroll, and scenario sales taxes are
  recorded as signed flows. End-of-turn reconciliation shows any unattributed
  residual rather than assigning it to a plausible source.
- Nation AI records evaluated gates and submitted intents; intent outcomes
  link back to the decision. Firm decisions record worker offers and refusals,
  wage adjustments, payroll borrowing and layoffs, and incorporation finance.
  Elite planning records selected action, luxury prices and sellers, sector
  margins, voyage ROIs, legislative/operator feasibility, return estimates,
  and cash outcome. Spatial exports, inventory liquidation, and some
  investment alternatives remain partial.
  The candidate snapshot is a separate preflight evaluation; it must be replaced
  or validated before describing those alternatives as the planner's actual
  evaluated choices.

## Known gaps

Reference snapshots cover priced recipe goods, and the live market, scenario
quotes, settlements, optional standalone `econsim.py --trace` runs, local
baskets, and national price aggregates have separate records with replay checks
for supported formulas. National and basket calculations retain their current
unconverted currency semantics and flag mixed currency. Imported shipment IDs
resolve across purchase, departure, arrival, supply, quote, and paid sale when
those source records exist. The core local strike/workforce/output/offer/price
path is linked. Remaining price work includes scenario history series and
their membership/currency decomposition. The main market's `vwap` input is an
unweighted recent-sample mean. Historical chart points do not yet open the web
inspector directly.

The coverage checker reports a changed snapshot as unexplained when its final
value does not match a recorded calculation. Per-profession headcount snapshots
are sparse: unchanged counts, including zero categories, are omitted while the
membership-change calculation records retain before/after counts and agent IDs.
Treasury snapshots show cash and deposit components. Bond, Caisse, public
benefit, Egypt project payroll/recall/remittance, tariff transfers, and
cadastral tax recovery now have operation IDs and balance evidence. Emergency
food levies expose exact in-kind stock changes, and routine public grain
purchases reconcile seller and treasury balances. Guided canal transit tolls,
customs-receivership tariff interception, Caisse toll debits, and granary stock
seizures are traced with no-conversion currency mismatches and missing source
legs exposed. Government food aid and household mutual aid now record exact food
inventory movements. Provincial emergency relief now traces the donor levy,
in-transit shipment inventory, haulage cash transfer and recipients or public
stock on arrival. National Egypt maize release traces each public-stock debit
against an individual household's queued meal ration, with allocation outcomes
and no-op reasons. Parent-to-child food sharing now reconciles both household
inventory legs and links each transfer to its aggregate outcome. Household
intake records source amounts and health-state changes for food shortages,
reserve use, trader stocks, and changing reserves; starvation deaths link to
same-turn intake evidence. Household market bids record cash-affordable units,
the wallet basis and formula, and bank funding causes; actual wood and furniture
consumption records distinguish wealth use, stockpile drawdown, and stochastic
wear. Elite luxury consumption records inventory drawdown, per-good prestige
ratings and saturation gains, status-tier changes, and the capped decay that
applies when no prestige goods are consumed. Other untraced imperial claim
paths, additional household support channels, other subsidies, remaining
police enforcement transfers and any recurring police upkeep mechanic,
remaining military service costs, and many scenario costs still need complete
transfer contracts. Egypt's
district relief, tax relief, settlement, and repression actions now record
success/failure reasons and measured effects. National
treasury, bank, household, firm, and goods-by-currency reconciliations remain
incomplete. Several scenario operations still need mutation-point records.
Nation and capitalist AI decisions record most evaluated candidates, selections,
and outcomes. The labor scheduler exposes its cohort gate, and nation diplomacy
records candidate thresholds and rejection reasons. Egypt's French, British,
and Ottoman scenario policies now expose their candidate gates and offer
valuation. Other scenario and spatial AI candidate details remain partial. The current metric
catalog does not yet cover every displayed field;
`inventory_region_histories()` labels legacy series as instrumented or
untraced so a missing probe is visible during development.
The UI shows unavailable comparison placeholders as such. Desktop charts do
not yet have a trace drilldown, and save/rebranch and a persistent query index
are not implemented. The compact source trace is queried by scanning events.

The first 20-turn labor scenario coverage run recorded 9,043 rows in 5.3 MB,
with 20 valid checkpoints and no currency-audit violations. Tracing on and off
produced the same sampled state SHA-256. This run predates the later treasury
and ecology probes, so its row count and coverage are a baseline rather than a
current measurement. A calculation match establishes the displayed value and
its immediate inputs; it does not by itself establish every upstream cause.

The Phase 3 bond and campaign-debt slice passed 32 bond, banking-contagion,
campaign-debt, and sewer/ecology tests. Paired foreign purchases and Caisse
receipts reconciled payer/payee cash balances and zero-sum same-currency
treasury movement. Municipal sewer funding exposed a recorded contractor cash
increase without a source-account debit; this remains a traced accounting
defect or explicit creation rule to resolve, not an inferred conserved
transfer.

The Phase 3 transfer tests now cover 46 public, project, Caisse, bond, and live
trace cases. Isolated Egypt fixtures verify worker pay balances, paired
district-to-Cairo movements, and grain stock/calorie changes. The broad Egypt
project integration fixture stopped during deterministic world generation at
that point in the work; a later world-generation follow-up below resolves this
default-seed case.

Tariff and emergency levy follow-up passed 26 government-transfer,
tariff-sharing, emergency-food, scenario-project, and fiscal-federalism tests.
Tariff payer allocation reconciles to the two treasury credits, while the levy
fixture balances donor stock losses against the government stock gain.

Routine public grain-purchase follow-up passed 33 food-security, market-auction,
and market-route tests. The trace now reconciles each treasury debit and seller
credit with matching stock movement and links the cash and goods records.

Egypt scenario grain tracing passed four deterministic transaction fixtures;
with the four project-transfer fixtures, nine focused tests passed. Private
harvest purchases, household sales, government purchases, and requisitions now
link cash and goods legs. Trace-on and trace-off harvest transactions preserve
the same balances, stock, history row, and operation ID.

Sovereign bank recapitalization passed seven banking tests and 21 combined
banking, debt-enforcement, and bond tests. The two-bank fixture confirms that
per-bank cash debits sum to the sovereign expense and link to capital increases.

Deposit bail-in tracing passed all seven banking-contagion tests. The fixture
verified depositor balances, matching equity, no cash movement, and the policy's
class and legitimacy consequences.

Estate bank-default tracing now covers the full loss waterfall: shareholder
capital, each depositor's non-cash haircut, local treasury funding, and any
unabsorbed loss that drives bank capital negative. Treasury funding records
both the government cash debit and bank capital credit, with the writeoff
linking its component events. The heirless-default fixture reconciles a $25
writeoff as $4 shareholder loss, $10 depositor loss, $3 treasury recap, and $8
residual loss. The 45 supply-control/actor-account, seven banking, 12 debt and
coercion, seven bond, and 29 live trace tests passed. Compilation and
`git diff --check` passed. Occupation and tribute flows, general wealth and
inheritance transfers, broad household/firm transfers, and some scenario costs
remain open.

Guided Egypt occupation receipts and negotiated withdrawal settlements now
record paired payer and recipient treasury balances under a shared operation
ID. Receipt calculations include institutional control, resistance, boycott,
strike, port damage, the per-turn cap, and the government's available cash.
Feudal tribute records each serf-to-lord inventory transfer by good, the
subsistence reserve and enforcement context, and the reference valuation used
by `tribute_collected_log`. Trace-on/off fixtures produced matching inventory
balances and operation IDs. Six focused occupation/tribute tests, 16
coercion/grain/government transfer tests, and 79 actor-account, fiscal, and live
trace tests passed; compilation and `git diff --check` passed. The existing
full Egypt occupation tests still fail during world generation because
`shape_nile_delta` cannot find a second coastal outlet; they do not reach the
changed occupation code. Imperial revenue claims outside this bounded scenario,
household transfers, and general inheritance remain open.

Cadastral tax recovery now records household payments, arrears and missed
assessment changes, the foreclosure hazard inputs and draw, and the auction
settlement split between district tax revenue and cultivator refund. Use-right
changes and linked unrest, legitimacy, and migration results are recorded; local
treasury receipts are attributed to the district rather than folded into the
national balance. Ninety-eight focused tests passed, including trace-on/off
state equivalence. Full Egypt integration is still blocked before this path by
the existing Nile delta generation error. Caisse toll and granary seizures,
imperial revenue claims outside the guided occupation, household aid and
subsistence transfers,
subsidies, repression costs, inheritance, and other scenario transfers remain.

Guided Suez transit tolls now pair the payer and recipient treasury balances,
record cumulative toll receipts, and link the toll to the fleet's passage into
Ismailia. Current GBP-to-EGP nominal amounts are explicitly marked as
unconverted. Two focused tests passed, including trace-on/off state equivalence.
The existing full geography tests remain blocked during world generation by
the Nile delta outlet error.

Customs-receivership tariff interception now records the creditor cash increase,
receivership debt balance change, requested and actual share, and currency
context. The remaining national and local tariff receipts link to the claim
events. A missing creditor treasury appears as an uncredited balance change
without an invented cash leg. Three focused fixtures and 57 customs,
imperial-debt, scenario-debt, public-transfer, and run-trace tests passed,
including trace-on/off state equivalence. Caisse transit-toll and granary
seizures, other imperial claims, household aid and subsistence transfers,
subsidies, repression, inheritance, and other scenario transfers remain.

Public food aid now emits one exact goods transfer per recipient, pairing the
government stock decrease with the resident's food inventory increase. The
aggregate aid record links those transfers. Automatic mutual aid and the
player-supported mutual-aid action record donor/receiver inventories and total
meals moved; the supported action also links its legitimacy gain. Five focused
fixtures and 56 food-security, grain, government-transfer, and live-trace tests
passed, including trace-on/off equivalence. The Egypt world-generation error
still blocks full scenario integration. Broader subsistence flows, additional
household aid channels, subsidies, repression, inheritance, and other scenario
transfers remain.

Caisse transit-toll seizures now trace actual debtor cash debits and creditor
credits. The legacy fallback can credit up to $5 without a debtor debit when
the requested toll is unaffordable; the trace exposes the unbacked receipt and
does not invent a source-side cash loss. Granary seizures trace exact food-stock
loss, the $2-per-unit cash valuation, and the creditor's cash receipt while
showing that no food inventory is transferred to the creditor. Four focused
fixtures and 61 customs, coercion, debt, transfer, and live-trace tests passed,
including trace-on/off equivalence. The manager's comment mentions royalty
seizures, but this step has no royalty seizure implementation. Other imperial
claims, household aid and subsistence transfers, subsidies, repression,
inheritance, and other scenario transfers remain.

Provincial emergency relief now reconciles donor food inventories with in-transit
cargo, pairs the government haulage debit with every hauler's cash increase, and
traces arrival into resident inventories or destination public stock. Stable
shipment operation IDs connect the dispatch and later arrival; trace event IDs
are not stored in simulation state. Outcome events explain when a candidate
shipment is skipped because no route exists or haulage is unaffordable. Four
dedicated fixtures and 52 focused food-security, aid and trace tests passed,
including cloned-state equivalence with tracing enabled and disabled. Broader
household subsistence, other aid channels, subsidies, repression, inheritance,
and other scenario transfers remain.

Egypt's district action outcomes now record the four player responses and their
no-op reasons. Public relief traces Cairo's stock debit against queued household
meal entitlements; local negotiation traces the treasury debit and individual
recipient cash balances; tax relief records fiscal and unrest changes; repression
records forces, memory seeds, protest and legitimacy. Seven focused fixtures and
15 district, aid, and government-transfer tests passed.

The Nile delta blocker is resolved for the authored default seed. Delta shaping
first searches for a clean river branch, then falls back to the cheapest
connected existing channel when generated rivers block the fork. The default
campaign now builds 1,000 regions with two distinct coastal outlets. Closed-canal
defense reroutes to Alexandria, matching the campaign behavior and tooltip; its
stale test expectation was updated. Sixteen campaign, geography, and
district-action tests passed, along with a 70-turn historical campaign path. The
12 scenario-project tests also pass. The full ending-matrix audit, which starts
fifteen separate 70-turn campaigns, was stopped after several minutes without
output; complete ending coverage remains unverified.

National maize release now records per-household ration entitlements as exact
public-stock transfers and links them to a national outcome with recipient
count and reserve before/after. A skipped release records whether its ration
limit is zero, stock cannot fund a full ration, or nobody is underfed. Three
focused fixtures cover allocation, all three no-op reasons, and trace-on/off
state parity. Thirty-two national and
district relief, household-aid, food-security, and government-transfer tests
passed; compilation and `git diff --check` passed.

The shared repression mechanic now emits a force-use outcome for successful and
blocked attempts. Records include police/garrison strength, legitimacy and
protest changes, grievance reduction, and the people who receive casualty and
broken-promise memories. Three fixtures cover forced repression, the no-force
gate, and trace-on/off state parity; 18 repression, district-action, and coercion
tests passed. Military and police payroll/maintenance transfers remain open.

Emergency construction overrun grants now reconcile the national treasury debit
with the contractor credit and link the cash transfer to the project outcome,
including rejected-grant reasons and stalled-project resumption. Four dedicated
fixtures and the existing overrun-subsidy regression passed. The full 12-test
construction module had one unrelated staffing threshold failure at exactly
0.2 efficiency; the other 11 tests passed. Other policy subsidies and military
and police payroll/maintenance transfers remain open.

Dependent children now receive per-transfer food inventory records paired with
the parent's food debit. The household-level result links to those transfers.
Three focused fixtures cover exact reconciliation, trace-on/off state parity,
and lifecycle-summary linkage; 23 dependent-food, lifecycle, nutrition, and
relief tests passed. Compilation and `git diff --check` passed. Household cash
affordability, non-food consumption, and other household support channels remain.

Household intake now records source quantities from ration queues, local food,
and trader foreign/export stocks, together with deficit, energy reserve, and
hunger changes. Routine full meals with stable health state are omitted to keep
trace volume down. Starvation deaths link to the same-turn intake event when
present. Five fixtures cover shortage, trader stock, routine-noise suppression,
death linkage, and trace-on/off parity; 69 food, nutrition, life-cycle, district,
and trace tests passed. Compilation and `git diff --check` passed.

Household cash affordability now records the units affordable from `remainingCash`
at each market bid, its formula and basis, and any bank-withdrawal event that
funded the attempt. Both positive orders and zero-order summaries link to those
withdrawals. Zero bids report the specific `cash_at_or_below_unit_price` reason
when a non-employee household's remaining wallet cannot cover one unit. Actual
wood and furniture consumption records before/after inventory and separates
wealth-multiplier use, wood stockpile drawdown, and furniture wear, including
the existing random draw and threshold. No bid quantity or consumption rule was
changed; the new reason only makes an existing zero-bid condition explicit.
Two dedicated affordability fixtures and three non-food consumption fixtures
passed; 13 dependent-food, food-intake, and auction-market tests passed, as did
all 30 run-trace tests. Compilation and `git diff --check` passed. Additional
household aid channels remain open.

The labor scheduler now records round-robin cohort selection, deferred workers,
and the hunger, unemployment, dispossession, or eviction reasons for emergency
bypass. Worker wage and livelihood decisions link to the schedule event. Three
focused fixtures and 29 scheduler, capitalist-planner, and rivalry tests passed.
Compilation and `git diff --check` passed.

Nation diplomacy evaluation now traces candidate-level gates for dominant
military threats, counterbalancing alliances, trade pacts, treaty betrayal, and
ideological war declarations. Each row records the relevant relation and
military thresholds, eligibility, selection, and a stable reason code. The
final nation-AI decision links back to that diplomacy evaluation, so the
proposed intents can be compared with what the full turn submitted.

Two focused fixtures verify candidate reasons, intent agreement, final-decision
linkage, and trace-on/off behavior parity. Seventeen diplomacy-AI, war-logic,
and multi-nation sandbox tests passed. Compilation and `git diff --check`
passed. Scenario diplomacy policies and the remaining spatial, expansion, and
other AI candidate gates still need detailed records.

The Egypt foreign-diplomacy evaluator now records France's ordered policy
gates, Britain's treasury and protest constraints, and the Ottoman Empire's
mediation trigger. Britain's response to a French offer records the capped
recovery, canal-access value, expedition costs, protest cost, prepared-line
penalty, and treaty-versus-military comparison; it links to the prior British
policy evaluation. Two dedicated fixtures verify the candidate rows, cause
links, serialization, and trace-on/off state parity. Ten scenario-diplomacy
and geography tests passed. The broader playthrough suite was interrupted
inside its separate-process ending-reachability matrix, so it has no complete
result. Other scenario candidate gates and actions remain open.

Military upkeep now records reachable seller ration purchases as exact cash
and food transfers, links bank withdrawals to payroll, and records the
government ration stock consumed, wage/food shortfalls, morale changes, and
desertion. Scenario personnel cash credits link to the aggregate payroll debit;
abstract units explicitly identify the lack of individual soldier wallets.
Two dedicated fixtures cover procurement reconciliation, bank funding,
shortfall effects, and trace-on/off parity. Twenty-four military, banking,
AI, and Phase 4 tests passed, as did the focused enlisted-personnel upkeep
regression. The broader labor-frontier module still has four failing action
assertions and two errors in petition/protection fixtures; its enlisted upkeep
test passes. Per-case police enforcement fees and outcomes are now traced, but
recurring police patrol payroll/maintenance and other military cost categories
remain open.

Labor debt and vagrancy enforcement now records case creation and the rule
that made each case eligible. Hearing outcomes expose settled or missing
claims, absent debtors, lost collateral occupancy, missing force, and treasury
or constable funding failures. A funded foreclosure or penalty hearing records
the exact government-to-constable cash transfer; foreclosure records the
tenant and access-right changes. Vagrancy records the active-law/workhouse
gate, whether poverty or dispossession qualified the person, the constable
payment, and the resulting workhouse status change with links back to the gate,
eligibility decision, and transfer. Garrison-backed actions are distinguished
from paid constable actions.

Four dedicated fixtures verify cash-account reconciliation, candidate and
gate reasons, case-to-payment-to-status cause links, and trace-on/off parity.
Sixty-six labor-mechanics, enclosure/workhouse, and causal-trace regression
tests passed, along with compilation and `git diff --check`. Recurring commons
patrol payroll is now instrumented; broader police maintenance remains open.

Recurring commons patrol enforcement now records the treasury funding check,
bank deposits requested and actually withdrawn, the selected constable, the
balanced $3 treasury-to-officer payment, and whether restricted access became
active or was suspended. Bank withdrawal rows cause-link to the funding
decision; the decision links to appointment and payment; the outcome includes
the access-share change and resulting restriction state. Partial bank funding
is visible as a failed gate, so a suspension is not misreported as no policy
attempt.

Three dedicated fixtures cover successful bank funding, partial funding and
suspension, missing constables, and trace-on/off parity. They pass along with
the two frontier-policy tests, compilation, and `git diff --check`. The older
end-to-end petition test still errors with `KeyError: Meridian` while looking
up a restriction record after the scenario step; it fails before reaching the
patrol handler. Broader police maintenance remains uninstrumented.

Elite conspicuous consumption now records each prestige-good inventory draw
and links those draws to the agent's prestige change. The outcome exposes each
good's prestige rating, saturation multiplier, sequential gain, and inventory
before/after; no-luxury decay records the eligible holdings checked, the
0.40-point decay cap, and the before/after status tier. An agent with no
prestige and no luxury stock emits no event. Four focused trace fixtures and
six existing triangular-trade/luxury tests passed (10 total), along with
compilation and `git diff --check`. Other household support channels remain
open.

Estate cash, deposit, and goods allocations now record their beneficiaries,
account balances, probate share rules, bank withdrawal causes, and terminal
cash/deposit/wallet closeouts. Foreign wallet detail rows link to the estate
closeout, and company ownership succession records whether the highest-cash
descendant or oldest employee received the firm. Goods rows include each
beneficiary's actual inventory change and also preserve the unchanged deceased
source inventory, making the current non-conserving rule visible.

Verification: six focused probate-trace fixtures, 23 actor-account tests, and
all 30 run-trace tests passed; compilation and `git diff --check` passed. The
new evidence exposes two separate accounting defects for follow-up: heir cash
allocations use the requested estate deposit even when a frozen bank settles a
smaller withdrawal, and the resulting residual deposit is removed from the
account map without reducing the bank's aggregate deposit liability. Probate
also credits goods to heirs or institutions without debiting the deceased
inventory. These behaviors were left unchanged in this instrumentation commit.

Frozen-bank probate now allocates cash only from the amount actually withdrawn.
Any residual deposit is transferred to heirs as a non-cash bank deposit, with
per-heir source/payee balances and a no-cash-movement journal row. The transfer
preserves the bank's liability-to-account-sum difference, and heirs without a
bank reference adopt the source bank for the inherited account. The ordinary
unfrozen withdrawal-and-cash distribution remains unchanged.

Verification: the frozen-withdrawal fixture now checks requested versus
settled cash, deposit reassignment, account-sum conservation, and trace-on/off
state parity. Six probate fixtures, 23 actor-account tests, and all 30 run-trace
tests passed; compilation and `git diff --check` passed. The separate probate
inventory source-debit correction remains open.

Probate now clears each deceased agent's remaining goods inventory after the
distribution decision. Per-good source-debit outcomes link back to the
allocation record; if the government, charity, or heirs receive nothing, the
closeout still records the unallocated goods being removed from the deceased
estate. This prevents inherited goods from remaining duplicated in the dead
agent's inaccessible inventory.

Verification: seven focused probate-trace fixtures, 23 actor-account tests,
all 30 run-trace tests, and all 25 plunder-labor tests passed. Compilation and
`git diff --check` passed. Remaining household/public aid, imperial claims,
police and military maintenance, and scenario transfers are still open.

Emergency constable mobilization during enclosure interdiction now records the
$60 municipal affordability gate, exact municipal cash debit, and the actual
recipient wallet credit selected by the existing disbursement helper. The
trace makes clear that this helper credits the first living non-government
agent, not a named constable, while the interdiction sets capacity to five
officers. The final outcome links the funding decision and payment to peaceful
dispersal, a bloody clash, or state terror, including casualties, terror
cooldown, and legitimacy changes. Insufficient funds and existing-force paths
record their gate and do not invent an emergency payment.

Verification: four focused emergency-constable fixtures and thirteen existing
multi-turn enclosure, commons-patrol, and labor-enforcement tests passed.
Compilation and `git diff --check` passed. Code search found no separate
recurring police payroll or maintenance transfer behind the police-capacity
fields; that recurring cost is a missing mechanic, while other military costs,
household aid, imperial claims, and scenario transfers remain open.

The core army cash and food mutation audit found no additional untraced
military upkeep path: `pay_and_feed` wages and ration drawdown plus
`_procure_rations` seller payments and food receipts are already instrumented.
`recruit_unit` changes labor assignment and unit state without charging cash or
goods. Naval crisis, campaign recruitment, and other scenario-specific force
costs remain in the scenario audit.

Creditor situation effects now record the treasury affordability decision,
Egypt's exact cash debit, each Britain/France receipt, and the applied policy
effects and resulting scenario-state changes. All legs share an operation ID;
recipient contracts expose the existing no-FX numeric transfer when currencies
differ. A response that is unaffordable records no transfer. If no eligible
creditor exists, the existing Egypt debit remains unchanged but is explicitly
recorded as having no receipt leg.

Verification: three focused situation-transfer fixtures plus twelve
supporting scenario-politics, occupation-settlement, occupation-transfer, and
fiscal-project creditor-reply tests passed (15 total), including trace-on/off
parity. Compilation and `git diff --check` passed. Other scenario actions, household
support channels, imperial claim paths, and cross-system reconciliations remain
open.

Guided Egypt naval and occupation force-supply costs now share a household
transfer trace. Battery preparation, British and French squadron mobilization
and upkeep, canal expedition supply, occupation garrison supply, and Caisse
inspection preparation record the funding decision, shortfall or missing
recipient, exact treasury debit and resident wallet credit, and linked outcome.
The trace names the actual first eligible resident selected by the existing
rule; it does not imply that the payment went to a soldier or sailor. Failed
occupation supply links its morale and strength losses to the funding failure,
and the resulting withdrawal or fleet outcome links to that same cause. The
narrower-oversight action now also records Egypt's $20 payer debit and split
British/French receipts, including the unaffordable offer gate. Cash contracts
flag resident-wallet currency mismatches when the existing numeric transfer
does not apply FX.

Verification: five household-cost and oversight fixtures, nine existing naval
crisis/occupation/politics fixtures, and two longer canal/occupation playthrough
tests passed (16 total). Compilation and `git diff --check` passed. Other
scenario transfers, household support, imperial claims, and cross-system
reconciliations remain open. The shared currency-contract change also passed 34
existing geography, occupation-transfer, and run-trace tests.
