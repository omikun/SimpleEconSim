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
unweighted recent-sample mean. Web chart points open the trace inspector for
national food price, nominal GDP, treasury, population and protest energy, plus
selected-tile food price, GDP, population, protest energy, food production,
food producer inventory, food-cash Gini, soil fertility, nutrition density,
air and water pollution, disease fatalities, individual
malnutrition/waterborne/respiratory/chemical case counts, and combined
healthcare outlays. Other chart series still need explicit source mappings;
desktop charts do not yet open the trace inspector.

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
applies when no prestige goods are consumed. Open finance work includes
imperial claims outside the active named-obligation flow, household support
channels beyond the documented aid, policy subsidies outside the traced set,
other police enforcement transfers, and scenario-specific military and
diplomatic costs. The core army wage and ration mutations are already traced.
There is no recurring police payroll transfer in the production turn path; the
one-shot safety-patrol payment is covered below. Egypt's
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
The UI shows unavailable comparison placeholders as such. Web charts show an
empty-state message when a series has no data instead of drawing a sample
curve. Desktop charts do not yet have a trace drilldown, and save/rebranch and
a persistent query index are not implemented. The compact source trace is
queried by scanning events.

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
trace volume down, except when local inventory consumption has a recent private
grain purchase candidate to follow. Starvation deaths link to the same-turn
intake event when present. Five fixtures cover shortage, trader stock,
routine-noise suppression, death linkage, and trace-on/off parity; 69 food,
nutrition, life-cycle, district, and trace tests passed. Compilation and
`git diff --check` passed.

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

Egypt's one-time officer-arrears action now records its treasury affordability
and recipient-availability gates, the exact source debit, and a receipt for
each household paid under the existing Alexandria-first rule. Receipt rows
expose recipient wallet balances and any unconverted currency mismatch. The
linked political outcome records army loyalty and garrison morale changes.
Repeat-payment, underfunded, and no-recipient attempts record no-op outcomes
without inventing a cash transfer. These metrics are registered in the trace
catalog, with morale and loyalty emitted as separate before/after outcomes.

Verification: four dedicated arrears-transfer fixtures, four existing Egypt
politics tests, and all 30 run-trace tests passed (38 total). Compilation and
`git diff --check` passed. Other scenario decisions and cash transfers remain
open.

Guided Egypt's recurring political-support calculation now records its actual
formula inputs and intermediates: mean household hunger, territorial unrest
summary, garrison morale, officer access, fiscal autonomy, extraction, naval
pressure, ruler/cabinet conditions, and the resulting loyalty, support,
grievance, movement, and authority values. Changed political metrics emit
before/after outcomes linked to that calculation. Dynastic-succession and
officer-movement gates record their measured thresholds and whether they
triggered, with links back to the turn calculation. The trace catalog includes
the added scenario and political metrics.

Verification: six dedicated arrears/dynamics fixtures, four existing Egypt
politics tests, and all 30 run-trace tests passed (40 total). Compilation and
`git diff --check` passed. Political response actions and remaining scenario
cash transfers still need audit.

Guided Egypt's dynastic and officer-movement response choices now record the
selected option, crisis context, available options, and political state before
and after the response. Changed ruler, coalition, legitimacy, autonomy,
creditor confidence, support, loyalty, authority, and nationalist-movement
metrics link back to the selected response. The palace-response path records
the exact unrest change by territory and its army-loyalty formula. Attempts
without a pending crisis or with an unavailable option record a no-op gate.

Verification: nine dedicated arrears, dynamics, and response fixtures, four
existing Egypt politics tests, and all 30 run-trace tests passed (43 total).
Compilation and `git diff --check` passed. Other scenario actions and non-Guided
policy transfers remain open.

The province policy panel now traces equalization-grant funding and the
province's least-liquid tile selection, including the balance score used for
each candidate. Successful grants record the matched provincial cash debit and
municipal treasury receipt; insufficient funds and empty provinces record
no-op outcomes. Soil-conservation spending records its provincial cash debit
as a public-service expenditure with no modeled cash recipient, then records
each changed tile's fertility. The existing funded-empty-province case remains
visible as spending without a land effect. Funding and outcome metrics are in
the metric catalog.

Verification: four dedicated policy-transfer fixtures, the existing provincial
grant conservation test, and the UI policy-action execution test passed (6
total). Compilation and `git diff --check` passed. City food aid, guano subsidy,
and other world-policy cash mutations remain open.

City emergency food aid now logs the existing source priority across municipal
government cash, tile-bank capital, and the owner nation's treasury. The funding
decision records every tested source, the selected account and balance, or the
shortfall when none can cover the $50 cost. Funded aid records the exact debit
as a public-service expense without a cash payee. Each selected household has
an outcome for food inventory and hunger before and after the action. The trace
explicitly identifies food creation without a stock debit. It also preserves
and exposes two current behaviors: aid still creates food if no source can
fund it, and a funded action spends the full cost even when no hungry household
qualifies.

Verification: five dedicated source-priority, fallback, unfunded-aid,
zero-recipient, and trace-on/off parity tests plus four provincial policy trace
tests and the existing policy-action UI test passed (10 total). Compilation and
`git diff --check` passed. The national guano subsidy and other world-policy
cash mutations remain open.

The national guano blockade-runner subsidy now records its $100 treasury gate
and coastal-port availability as separate decisions. The treasury debit links
to every selected trader or local-agent receipt, with a separate treasury
refund for any coastal tile that has no agents. The action outcome reconciles
the cash shares to the gross cost. For each port it records fertilizer stock
before and after, the requested 20 units, the actual delivery after the 80-unit
storage cap, and recovery from nitrate depletion. Insufficient treasury and no
coastal ports remain no-charge no-ops, with the existing gate order preserved.

Verification: four dedicated guano tracing tests, all seven fertilizer supply
and blockade tests, five emergency-food trace tests, four provincial policy
trace tests, and the existing policy-action UI test passed (21 total). Coverage
includes trace-on/off parity, insufficient funds, no ports, capped delivery,
recipient priority, and an unoccupied-port treasury refund. Compilation and
`git diff --check` passed. Other world-policy cash mutations remain open.

The desktop policy dispatcher had separate, untraced copies of city emergency
food aid, provincial equalization and soil conservation, and national guano
subsidies. It now delegates those actions to the same instrumented implementation
used by the web client; the duplicate desktop mutations were removed. This keeps
the trace semantics and action effects consistent across client entry points.

Verification: six city-food trace tests, five provincial-policy trace tests,
five guano trace tests, and the existing policy-action UI test passed (17
total). The desktop-specific cases confirm traces are emitted for each shared
action family. Compilation and `git diff --check` passed.

The frontier pioneer aid action now records the eligible homesteaders, each
recipient's food inventory before and after the two-unit grant, and the
aggregate food created. It explicitly records that the current action debits
neither treasury cash nor an inventory stockpile, even though the panel labels
the action "$40". A frontier target can carry its own trace context outside
`world['tiles']`; the policy trace lookup now checks that target directly.
Desktop and web dispatchers share this action implementation. A frontier with
no homesteaders logs the no-recipient result while preserving the current
feedback text.

Verification: two dedicated pioneer-aid tests, two existing frontier-expedition
tests, six city-food tests, five provincial-policy tests, and five guano tests
passed (20 total). Coverage includes desktop/web parity, trace-on/off parity,
zero eligible recipients, and the absence of cash and stock debits. Compilation
and `git diff --check` passed.

National emergency granary relief now records each tile's living hungry
candidate set, selected households, hunger-step resets, granary stock change,
and famine-progression reset. It records the existing cumulative draw rule:
each tile's requested draw uses the total households fed so far across the
current nation-wide pass. The trace also shows that the government's separate
food inventory is only observed, not consumed, and that household food
inventories remain unchanged when hunger is reset. No-eligible-household
actions still reset famine progression and are now visible as zero-recipient
outcomes.

Verification: two granary trace tests and the existing relief-prevents-genesis
test passed (3 total), covering multi-tile cumulative draw, trace-on/off parity,
zero recipients, famine reset, and the unconsumed government food balance.
Compilation and `git diff --check` passed.

Mass entertainment subsidies now log the selected government account and
affordability gate, exact treasury debit, and per-tile entertainment increase
and unrest reduction. The trace records the uniform per-tile boost, the
entertainment cap at 1.0, the unrest floor at zero, and the public-service
expense without a modeled cash payee. Underfunded attempts record the shortfall
and leave treasury and tile state unchanged.

Verification: two dedicated entertainment-trace tests, two granary-trace tests,
and all five existing trade-route epidemic tests passed (9 total). Coverage
includes trace-on/off parity, affordability rejection, and capped effects.
Compilation and `git diff --check` passed. Other labor-law state changes remain
open for causal tracing.

Statutory workday changes now log the requested delta, bounded target, legal
8-to-16-hour range, and no-op attempts at a boundary. Applied changes record
each tile's legal cap and Ten-Hour Act state, corporate shifts immediately
clamped to the new cap, faction support changes, and the protest-energy
increase when the workday expands. The action outcome links those results to
the decision gate.

Verification: all three dedicated workday-trace tests passed, including
trace-on/off parity, a lower-cap reform, a longer-workday protest increase, and
a boundary no-op. The existing wage-cap test passed when rerun by itself.
A combined run of the workday, statute-of-laborers, and plunder-labor suites
had one wage-cap assertion failure (31 of 32 passed); the same assertion passed
in isolation, so the broader order-sensitive failure remains to diagnose.
Compilation and `git diff --check` passed.

The Statute of Laborers now traces the selected cap, every corporate wage cut,
and the resulting Gentry, Bourgeoisie, Labor, Peasant, and other faction-support
changes. Repeal logs the legal-state reversal and support shifts, while showing
that the existing code leaves the stored cap value and reduced wages untouched.
Factory-safety enactment records each tile's mandate state. These shared
`labor_politics` actions emit the same records regardless of which client called
them.

Verification: two dedicated law-trace tests, three workday-trace tests, and the
existing wage-cap enactment regression passed (6 total). The repeal test checks
that reduced wages remain reduced and the cap value remains stored after repeal.
Compilation and `git diff --check` passed.

Trade quarantine enactment and repeal now trace nation and tile flags, every
route's quarantine state, and the faction-support changes. The records show
which routes were closed or reopened and link them to the policy transition.
This action has no cash leg.

Verification: the dedicated quarantine parity test, all five trade-route
epidemic tests, and both labor-law trace tests passed (8 total). Compilation
and `git diff --check` passed. Anti-truck policy effects and remaining labor-law
transitions remain open for tracing.

The Anti-Truck Act now records the decree decision, tile law states, corporate
scrip-to-cash switches, company-debt writeoffs, debtor despair relief, and
faction-support changes. It also records that the requested truck-system
grievance reduction currently has no effect because `Faction.add_grievance`
ignores negative amounts; this documents current behavior without changing it.

Verification: the dedicated trace-on/off parity test, the existing scrip and
debt-peonage regression, labor enforcement, quarantine, and labor-law trace
tests passed (12 total). Trace metrics are catalogued and instrumented.
Compilation and `git diff --check` passed.

National uprising handling now records the strike-rate and unrest threshold
calculation, the military and police strength comparison, the ruling faction,
and the selected repression or concession branch. Effects record strikers
cleared, memory seeds, authority-incident coverage, unrest reductions, and
legitimacy gains. The trace also explains when thresholds are missed or both
labor concessions have already been enacted. Class consciousness is measured
by the legacy calculation but does not currently affect this decision.

Verification: five dedicated uprising trace tests and the existing coercion
regression suite passed (13 total), covering trace-on/off parity, armed
strikebreaking, both concession tiers, no-crisis, and no-further-concession
outcomes. Compilation and `git diff --check` passed.

Capitalist electoral backlash now traces the pro-labor-law and candidate
availability gates, opposition filtering and charisma-based candidate choice,
each capitalist or corporate donor's liquidity calculation, and every cash or
foreign-currency-wallet donation. Paired account balances record the source
debit and candidate receipt; later receipts link to earlier deposits into the
same candidate account. Separate records explain the charisma-adjusted
popularity increase and aggregate campaign result.

Verification: the dedicated backlash trace tests and full supply-control actor
strategy suite passed (47 total), including trace-on/off parity, domestic cash
and FX-wallet conservation, candidate selection, donor thresholds, and closed
gates. Compilation and `git diff --check` passed.

Regime-driven labor-law repeal now records its gates and tile/workplace
outcomes. This trace exposed a state mismatch in the existing mechanic: the
nation cap returns to 16 hours, but tile `workday_cap` and `ten_hour_act` flags
can remain at 10 hours, and firms keep their current shifts. The general
repeal path also leaves the Statute of Laborers wage cap and Anti-Truck Act
active; the trace lists those laws as present but untouched. This is documented
as a gameplay consistency issue for a follow-up, separately from the completed
observability change.

Verification: two dedicated repeal tests, both existing labor-law trace tests,
and all three statutory workday trace tests passed (7 total), including
trace-on/off parity, stale tile and firm state, and laws outside this repeal
path. Compilation and `git diff --check` passed.

Phase 4 follow-up, 2026-10-18: national elections now trace candidate-pool
formation, faction-leader evaluations, independent fill, candidate ranking,
each eligible voter's faction-weighted choice and broken-promise defection,
per-candidate vote totals, campaign-budget gates and allocations, campaign
cash transfers, and the winner/incumbent transition. The final election record
links to its candidate pool and vote tallies; transfer rows link to each
candidate's budget decision. Empty candidate pools also record why there was
no winner. Campaign spending's charisma-diluted popularity formula is recorded
separately. The trace distinguishes base popularity, which ranks and limits the
candidate pool and supplies the existing first-in-order vote tie-break, from
campaign/backlash popularity changes, which happen after pool ordering and do
not enter faction vote weights.

Verification: four dedicated election tests and all 45 supply-control actor
strategy tests passed. Coverage includes trace-on/off result parity, campaign
cash conservation, transfer-to-allocation links, candidate selection, voter
fallbacks, broken-promise defection, and empty elections. Compilation and
`git diff --check` passed.

Phase 4 follow-up, 2026-10-18: bilateral treaty and war actions now record
acceptance gates and reason codes, treaty relation thresholds and betrayal
penalties, signing/breaking/cancellation state, relations and betrayal-memory
changes, war aims, treaties broken by war, and each defensive-alliance call.
Peace offers record whether a war exists and an offer is already pending;
responses record the next-turn timing rule, acceptance or rejection, and final
war state. Peace signing records the fixed relation reset and the reparations
strength threshold. When the mechanic receives the nation world, reparations
record the 2.5-to-1 strength test, 20-strength minimum, 40% treasury share,
$50 cap, and paired payer/recipient cash balances under one operation ID.

Tracing is passed from AI intents, web actions, desktop actions, and the
labor-frontier rivalry. Trace-only world context does not activate the existing
alliance military gate or peace reparations mechanic when the gameplay caller
did not supply that world; those unevaluated conditions are labeled in the
trace. This preserves existing outcomes while making path differences visible.

Verification: four dedicated diplomacy-action tests and 47 diplomacy, war,
AI, scenario, and web-client parity tests passed. Tests cover accepted and
rejected treaty gates, betrayal versus cancellation, defensive ally calls,
duplicate wars, peace timing, no-world reparations behavior, actual reparations
cash legs, trace-on/off state parity, and registered metrics. Treaty signing
still uses an automatic threshold check rather than a recipient AI response;
the trace records that current acceptance model explicitly. Compilation and
`git diff --check` passed.

Phase 4 follow-up, 2026-10-18: active-war AI decisions now expose why a nation
waits after war is declared, waits for the other side's peace response, proposes
peace after securing its aim or culminating, or selects an attack. Attack
records include a bounded list of forecasts and the progress-minus-cost margin
against the existing 0.15 threshold. Peace evaluations expose the territory,
supply, strength, recent-loss, and regime-change terms; the final response links
to that calculation. Tracing leaves the current AI rules unchanged.

Verification: six dedicated war-intent trace tests, six existing war-logic
tests, and four diplomacy-action tests passed. Coverage includes trace-on/off
intent parity, peace calculation causal links, regime-change rejection, attack
forecast selection, peace proposal gates, metric registration, compilation,
and `git diff --check`.

Phase 4 follow-up, 2026-10-18: the expansion evaluator now records each
frontier-tile gate, settlement or conquest score, terrain and population
components, food/wood bottleneck bonuses, diplomatic fallout, military balance,
and the strict score/tie-order reason for selecting or rejecting a plan.
Spatial exclusions identify owned, ocean, and below-sea-level tiles.

Audit finding: `evaluate_expansion` currently has no production caller; the
active `decide_turn` path does not use this M5.3 plan. The new trace appears
when the evaluator is called, but this work does not activate expansion or
change AI behavior. That integration remains a gameplay/AI follow-up.

Verification: six dedicated expansion trace tests, nine existing M5 AI and
diplomacy tests, and two diplomacy-AI trace tests passed. Trace-on/off plan
parity, settlement valuation, conquest and alliance gates, spatial exclusions,
registered metrics, compilation, and `git diff --check` were checked.

Phase 4 follow-up, 2026-10-18: active nation-turn policy records now include
explicit failure codes and threshold inputs for defensive recruitment,
contractor subsidies, public works, and enclosure. Project status/cash gates,
per-tile infrastructure readiness, commons tenure, protest, market/schedule
triggers, landlord affordability, and pasture selection are retained in the
existing nation decision record. The final nation decision directly links to
war-intent evaluation events as well as diplomacy evaluation.

Verification: six dedicated nation-policy trace tests, six expansion trace
tests, six war-intent trace tests, two diplomacy-AI trace tests, and nine M5
AI regression tests passed (29 total). Coverage includes food-emergency
blocks, action parity for enclosure, empty and unaffordable gates, project and
infrastructure screening, and final-decision causal links. Per-neighbor threat
weights behind border vulnerability remain a spatial tracing gap. Compilation
and `git diff --check` passed.

Phase 4 follow-up, 2026-10-18: border-vulnerability calculation now records
each adjacent tile's ownership, relations, defensive alliance/non-aggression
exclusion, troops present, hostility floor, and weighted threat. The local
garrison, denominator floor, total weighted force, and final vulnerability
formula are included. The nation-turn result links its defense candidate back
to each tile calculation.

Verification: two dedicated border-vulnerability tests, six nation-policy
trace tests, and nine M5 AI regression tests passed (17 total). Trace-on/off
scores and reason text match; treaty exclusions, weighted threat calculation,
metric registration, final-decision linkage, compilation, and `git diff --check`
were checked.

Phase 4 follow-up, 2026-10-18: elite corporate planning now emits a compact
market novelty scan, a per-region planner-phase gate, and a per-eligible-elite
planning gate. The phase gate records when scenario owner-policy mode disables
the standard planner. The scan reports new and removed goods; the agent gate
names the first trigger that allowed planning (new item, same-turn supply
proposal, same-turn concession, or five-turn cadence), or records `not_due`,
and links novelty-triggered runs to the scan.
The previously emitted `market.supply_strategy` metric is now present in the
metric catalog alongside these new gate metrics. Non-elites remain outside the
planning candidate trace to avoid logging ordinary households as skipped firms.

Verification: five dedicated planner-gate tests and 63 existing capitalist
propagation and supply-control tests passed (68 total). Tests cover each gate,
scenario suppression, novelty event linkage, trace-on/off cadence parity,
JSON-safe records, metric registration, compilation, and `git diff --check`.
Planner return values and the existing five-turn/trigger cadence are unchanged.

Catalog audit follow-up, 2026-10-18: a production-source AST audit found 27
emitted metric IDs without decoder descriptions and 71 direct metric IDs missing
the catalog's instrumented-coverage marker. All 27 descriptions have been added
for crop contracts, bids, market charters and offers, land and water rights,
routes, scenario creditor/naval outcomes, resistance capacity, and related
events; all literal production emissions are now marked as instrumented. A
repository test scans production Python call sites and fails if an emitted
literal `metric_id` is absent from either registry.

Verification: the catalog audit covers all 266 production literal metric IDs;
the registry test plus the market, supply-rights, route, creditor, occupation,
resistance, and naval trace suites passed (98 tests). `metric_catalog.py` and
the audit test compile, and `git diff --check` passed. This closes registry
metadata gaps without changing simulation behavior.

AI queryability follow-up, 2026-10-18: the final nation decision, final
corporation plan, and intent execution outcome now carry dedicated `ai.*`
metric IDs. This makes the candidate selection records filterable alongside
their existing calculation and cash-outcome links. An audit of event-only
records also found further candidates for review, including FX conversion,
route freight/shipment lifecycle, coup checks, and takeover attempts; these
remain readable by event kind while their metric-label coverage is evaluated.

Verification: the catalog audit, nation and corporate decision trace tests,
M5 AI regressions, capitalist propagation, and supply-control suites passed
(86 tests). The intent execution record retains its decision link; compilation
and `git diff --check` passed.

Trace-reader follow-up, 2026-10-18: metricless events can now be queried by
their `kind` through `RunTrace.query`, `trace_report.py --kind`, and the web
`/api/trace?kind=...` endpoint. This makes shipment lifecycle, FX conversion,
coup-check, and unrest events directly filterable without assigning numeric
metrics to categorical records.

Verification: compact round-trip and CLI filtering, trace queries, and web API
tests passed (65 tests). A metricless shipment-departure record was selected
through all reader layers; Python compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: direct bank FX conversions now carry the
`trade.fx_conversion` metric and record the trader's foreign-wallet balance
before and after the exchange. Both directions retain the executed foreign
amount, conversion rate, home-currency payment, and bank FX-pool and reserve
balances, complementing the existing bilateral-rate and order-book traces.

Verification: the FX accounting and trace-registry suites passed (35 tests).
Tests cover sell-foreign and buy-foreign wallet deltas, home settlement, bank
pool/reserve movements, and metric registration; compilation and
`git diff --check` passed.

Phase 3 follow-up, 2026-10-18: route departures and arrivals now expose shipped
quantity as `trade.shipment_quantity`, while carrier payments expose
`trade.route_freight_settlement` with the exact currency amount and a causal
link to the departure. The existing shipment source-purchase and arrival links
remain intact, so the route trace now presents cargo volume and freight cost
as queryable metrics through the shipment lifecycle.

Verification: the metric registry, market-route, and run-trace suites passed
(45 tests). The integration run exercises both departure and arrival quantities
and confirms freight rows link to their shipment. Compilation and
`git diff --check` passed.

Phase 4 follow-up, 2026-10-18: coup checks now use a shared assessment result
for gameplay and tracing. The registered `politics.coup_decision` record shows
whether low legitimacy allowed candidate screening, the ranked eligible
generals and trait weights, the leader's cash, mutinous and loyal unit details,
government guard mobilization, legitimacy defense, optional RNG margin, both
force totals, and the strict comparison reason. The public `coup_chance()`
two-value return contract and coup outcome rules remain unchanged.

Verification: three focused coup trace tests cover trace-on/off outcome parity,
force reconstruction, legitimacy and candidate gates, and successful coup
execution. The existing coercion/GDD tests and the full metric-catalog callsite
audit also passed (12 tests); compilation and `git diff --check` passed.

Phase 4 follow-up, 2026-10-18: popular-front takeover checks now emit the
registered `politics.takeover_decision` metric for ownerless, gated, repelled,
and successful outcomes. Inputs include legitimacy and mob-share pressure,
both random draws, the per-unit garrison contributions and morale factors,
casualty memory seeds, protest reduction, and the regime outcome. Existing
protest-energy and legitimacy records are retained, with the latter now
including its opening value.

Verification: four takeover trace tests cover no-owner and zero-chance gates,
force and casualty details, success/regime changes, and trace-on/off parity.
Those tests plus collective-action, coercion/GDD, and catalog-coverage suites
passed (23 tests); compilation and `git diff --check` passed.

Phase 4 follow-up, 2026-10-18: dynamic collective-action observations now
share the registered `labor.collective_action` metric, with the precise event
kind as its categorical value and the existing event facts, message, firm,
strike, and causal links preserved. This makes organization votes, strike
lifecycle, firm offers, production observations, support transfers, payroll,
and settlement reviews queryable under one metric without changing their
event-specific kinds.

Verification: trace queries select the collective-action metric and retain
the strike-to-workforce causal link. The run-trace, collective-action, and
metric-catalog coverage suites passed (41 tests); compilation and
`git diff --check` passed.

Phase 3 follow-up, 2026-10-18: the reusable scenario coercion module now
records blockade operating costs as `military.fleet_upkeep`, including the
aggressor treasury balance, requested and paid amounts, currency, insolvency
shortfall, and explicit expense-sink accounting treatment because no upkeep
recipient is modeled. Insolvency withdrawal links to that cost record, and the
mobilization-to-ultimatum transition records the fleet-to-battery force ratio.
Tracing does not persist event IDs into scenario state.

Verification: three dedicated scenarios cover funded upkeep, insolvency and
withdrawal linkage, and a due ultimatum; each compares traced and untraced
state. Those tests, scenario interpreter/diplomacy regressions, and catalog
coverage passed (16 tests); compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: charity food allocations now record each exact
charity-stock debit and household food credit with the recipient's age/hunger
group and tile. An aggregate `goods.charity_food_aid` outcome links to the
individual distribution rows and records the selected hungry recipients,
young-recipient pass, and remaining charity stock. Empty-stock turns stay
quiet to limit routine trace volume.

Verification: two focused fixtures cover exact recipient and charity balances,
the linked aggregate, empty-stock noise suppression, and trace-on/off state
parity. The charity trace, supply-control actor, run-trace, and metric-catalog
coverage suites passed (78 tests); compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: charity donations now emit `finance.cash_transfer`
records for corporate and wealthy individual gifts. Each transfer includes
donor and charity wallet balances, corporate retained earnings where relevant,
the actor-account journal event, and the charity's funding need. Donations
funded from bank deposits link to the exact withdrawal and preserve requested
versus settled amounts.

Verification: a dedicated traced/untraced fixture checks corporate and
individual balances, retained earnings, bank deposits, transfer contracts,
withdrawal causality, and final charity reserves. Donation regressions and the
metric-catalog callsite audit passed (3 tests); compilation and
`git diff --check` passed.

Phase 3 follow-up, 2026-10-18: national food-security funding now records both
the sovereign treasury debit and municipal receipt under one operation ID and
`treasury_transfer.v1` contract. Each side includes exact account balances and
currency; the receipt links to the debit, and the food-security assessment
links to the receipt. The paired amounts net to zero within the nation.

Verification: the traced/untraced food-security fixtures retain identical
balances and policy results. The focused response, paired-leg, and metric
catalog tests passed (3 tests); compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: private and public medical-care payments now
emit exact `finance.cash_transfer` contracts with patient/government and
provider wallet balances. Treatment outcomes link to their payment records;
the public spending aggregate links to its actual provider transfers. The
medical spending summary separates treatment costs from cash that actually
changed accounts, identifying self-administered care without creating a
fictitious transfer.

Verification: three tests cover private payment, public payment, and public
self-administration, each checking trace-on/off state parity and event links.
Those tests and the metric-catalog audit passed (4 tests); compilation and
`git diff --check` passed.

Phase 3 follow-up, 2026-10-18: baby bonuses, scaled or full UBI, parental leave,
and starvation welfare now emit one `finance.cash_transfer` receipt per
household. Each receipt records the exact recipient wallet before and after,
the amount actually paid, the actor-account journal ID, and a link to the
aggregate treasury leg. The contract marks payer balances as aggregate evidence
instead of inventing per-recipient treasury snapshots.

Verification: three traced/untraced fixtures cover all four benefit paths,
including a partially funded UBI and parental-leave shortfall. Existing
government transfer and provincial policy tests plus metric-catalog coverage
passed (12 tests); compilation and `git diff --check` passed.

Phase 3/4 follow-up, 2026-10-18: successful coups now record each tile's exact
treasury-to-general cash seizure as `finance.cash_transfer`, linked to the
force-comparison decision. A registered `politics.coup_execution` outcome
records the regime and legitimacy result, amount seized, purge count, and links
to the decision and seizure rows. Trace IDs remain local to the trace.

Verification: the successful-coup fixture checks per-account balances, actor
journal linkage, decision/seizure/outcome causality, and trace-on/off state
parity. Coup decision and metric-catalog tests passed (4 tests); compilation
and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: enclosure enforcement and charter settlements now
record exact bailiff and landlord-to-government wallet transfers, including
actor-account journal IDs and currency. The bailiff affordability decision
records protest, existing force, cash requirement, and recipient; successful
enclosure outcomes link the force decision and both payments. Defied attempts
record the unaffordable-force gate without inventing a transfer.

The legacy `enclosure_survey_debts` loop migrates old saves into named
obligations and returns before its historical payment/auction branch. This
change instruments the active charter-payment path only; later obligation
settlement remains owned by the named-obligation/case trace.

Verification: traced and untraced enclosure outcomes and balances match for
funded enforcement, defied enclosure, and government fallback receipt. The
enclosure, coercion, cadastre, and metric-catalog tests passed (28 tests);
compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: active named-obligation payments now emit exact
`finance.cash_transfer` contracts for debtor and creditor wallets, preserving
the operation ID in the actor-account journal. Payment rows link to the
interest-and-balance settlement; the existing `finance.obligation_payment`
row links to the exact transfer. The production rent and arrears summaries
receive local-only event-ID lists and link to their claim settlements without
persisting trace IDs in simulation state.

Verification: a partial-payment fixture checks interest accrual, both wallet
balances, remaining claim balance, journal linkage, causal links, and
trace-on/off state parity. Obligation, enforcement, enclosure, labor, cadastre,
and metric-catalog suites passed (45 tests); compilation and `git diff --check`
passed. Production assesses rent as named claims; the standalone direct rent
collector is not called by the production stepper.

Phase 3/4 follow-up, 2026-10-18: assassination contracts now trace the leader,
active-plot, and treasury funding gates; the exact treasury-to-constable or
treasury-to-charity payment; and the commissioned plot. If the existing logic
debits funds without a recipient, the trace records a policy expenditure with
an explicit missing cash payee instead of inventing a credit. The active plot
keeps a stable operation key (not an event ID) for cross-turn lookup. Each
detection check records its actual random draw, risk, and remaining duration;
the blown, target-missing, decapitation, or martyrdom outcome is recorded. The
final outcome links to the registered death row, whose optional trace-ID return
path keeps event IDs local to the trace.

Verification: traced and untraced commissioning, decapitation, martyrdom, and
detection fixtures match for game state and RNG state. The assassination,
rebellion, metric-catalog, person-death, food-intake, and run-trace suites
passed (53 tests); the medical/disease regression script, compilation, and
`git diff --check` passed.

Phase 3 follow-up, 2026-10-18: six cash-bearing governance-panel actions now
share one traced implementation across web and desktop: city UBI, agricultural
subsidy, safety patrol, provincial highway and healthcare spending, and the
national science grant. Funding decisions expose the exact treasury gate;
debits record balances and local actor-account journals. Safety patrol records
the actual wallet chosen by the existing first-living-non-government-agent
rule, or shows the debit as an expense if there is no recipient. Its outcome
records police capacity and protest change. UBI enactment uses the cost-bearing
mandate path in both panel dispatchers, and repeal resets its mandate counter.
Farm subsidy, road maintenance, healthcare, and science spending currently
have no modeled recipient or corresponding farm, route, health, or research
state effect; their traces explicitly show the treasury debit and the absent
effect.

Verification: 27 policy trace, public-aid, provincial, guano, frontier, and
metric-catalog tests passed. The focused City/Province/Nation policy UI action
test also passed; the broader GUI module could not complete because its renderer
failed to create an OpenGL context. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: public construction now traces its ordered
government cash and bank-deposit source legs, target-bank capital fallback,
shortfall rollback, contractor payment, and project commissioning under the
BuildIntent operation ID. Each bank-deposit leg records the amount requested,
the amount the bank settled, resulting wallet/deposit balances, and the linked
withdrawal event. The payment contract itemizes contributors and marks the
composite payer as a virtual pool without a captured wallet balance. A frozen
bank fixture exposes the current behavior where a $300 request settles only
$5, the wallet is debited by $300 and falls to -$295, and the project still
receives its full contractor payment. This is recorded as existing behavior;
the mechanics were not changed.

Verification: traced/untraced cash and deposit construction fixtures match,
including game and RNG state. The frozen-deposit trace checks requested versus
settled funds, wallet deficit, and payment. A shortfall fixture verifies cash
rollback, the remaining settled bank withdrawal, and that no contractor payment
occurs. BuildIntent, trace-catalog, and run-trace suites passed (34 tests).
Construction regressions passed except the existing textile staffing test,
which fails its `operational_efficiency > 0.2` assertion at exactly 0.2 even
when run alone. The focused multi-tier grant and construction UI test did not
complete: its Python process aborted with exit 134 during the pygame test.
Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: imperial receivership enforcement now records
the initial $50 agent-contract gate and payment, recurring retainer affordability
and payment, and the $50 replacement-agent contract when military enforcement
loses its force. Exact creditor and agent wallet balances share stable operation
IDs with the receivership state. An unaffordable payment links to suspension.
If the current recipient search finds no agent, the creditor debit is recorded
as an explicit uncredited policy expense instead of a fabricated transfer.
Cross-currency payments flag that no conversion occurred.

Verification: three focused fixtures cover establishment and retainer transfers,
missing payees, and unaffordable suspension; trace-on/off balances and RNG state
match. The metric-catalog audit and imperialism, coercion, phase-4, and
hired-agent conservation tests passed (13 distinct tests). Compilation and
`git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Egypt district worker bargaining now records its
strike/petition and employer eligibility gates; each employer's 0.5 wage offer,
20.0 cap, exact cash contribution, and resulting balances; and the equal split
to each selected worker. The transfer uses an explicitly virtual employer pool
with itemized source legs, not a fabricated pooled wallet. The linked outcome
records recipient selection, zero-funding settlements, strike and petition
state, settlement duration, unrest, and legitimacy. Rejected gates are visible
as well. No bargaining rule or simulation state transition changed.
If a stale petition resolves with no eligible household members, the existing
employer debit is recorded as uncredited with an explicit missing-recipient
status rather than shown as a worker transfer.

Verification: seven focused tests cover compact-trace serialization and
verification, transfer-leg reconciliation, zero-contribution and both
rejection gates, missing household receipts, and traced/untraced state parity.
The bargaining, district, metric-catalog, and run-trace suites passed (45
tests); the Egypt food-repair campaign playthrough also passed and reaches this
bargaining action. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Egypt district arrears relief now links each
debtor's exact tax writeoff to the action result, including municipal and
national shares, total forgiveness, local tax-rate reduction, and legitimacy
gain. The no-arrears gate is recorded. District strike-breaking records the
existing repression force gate, memory and grievance event, strike-flag
clearing, and collective injury-memory count in one operation chain. The
repression helper accepts an optional operation ID and event-ID collector;
existing callers and its default return value are unchanged.

Verification: arrears, district-effect, repression, bargaining, generic
district-action, catalog, and actor-account writeoff probes passed (23 tests).
They cover traced/untraced repression parity, unavailable force, missing
arrears, exact public writeoff shares, and links from repression/writeoff
records to the scenario action. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: district reserve recall now records used/empty
reserve gates, each paired district-to-Cairo cash transfer, per-district unrest,
and the national legitimacy loss in a linked action summary. Grain-entitlement
policy activation, deactivation and repeated requests are traced; each active
turn records its donor/recipient feasibility, conserved food and carrier
payments, remaining hunger, and the delivery-linked legitimacy and unrest
changes. Zero-delivery turns identify the unmet eligibility condition. The
trace event IDs remain local to the recorder and are not stored in campaign
state.

Verification: project-transfer, strategic-project, catalog, district-effect,
and bargaining suites passed (33 tests), including compact contract legs,
delivery and no-delivery cases, reserve gates, and trace-on/off parity for
recall and food entitlement. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Guided Egypt occupation actions now explain
boycott, general strike, insurgency, collaboration and withdrawal offers with
before/after state, effect duration, clamp formulas and rejection reasons.
Insurgency reports the actual garrison loss and civilian-casualty counter; a
withdrawal offer is recorded as a proposal with no immediate payment. Repeated
same-turn decisions receive distinct operation IDs. No occupation rule changed.

Verification: occupation action, occupation regression, metric-catalog,
district-effect and geography tests passed (18 tests), covering all player
actions, rejection gates, unique operation IDs and trace-on/off state parity.
Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Guided Egypt landing responses now trace warning
and funding gates, canal-route calculations, garrison relocations, deployed
occupation troops, settlement cash/debt/autonomy changes, and the final campaign
state. Landing summaries link to their battle and territory-control outcomes;
partial debt-settlement failure preserves the observed state delta. No campaign
rules or response results changed.

Verification: campaign, occupation, metric-catalog and geography suites passed
(25 tests), covering evacuation, linked battle causes, rejected responses,
canal funding and rerouting choices, trace-on/off state parity, and compact
trace decoding. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Alexandria bombardment now explains its supplied
fleet gate, battery ammunition and fleet damage, British and French gun power,
strike formula, fort and port damage, selected civilian injuries and exact
health-attrition changes, unrest and next landing turn. Trace records distinguish
missing fleet, wrong location, depleted ships/coal, and unsupplied fleet. No
bombardment or injury rules changed.

Verification: campaign, occupation, metric-catalog and geography suites passed
(27 tests), including bombardment gate, casualty/attrition caps, trace-on/off
parity, and compact trace decoding. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Egyptian expedition steps now record landing
readiness, the 10-transport minimum, recurring British supply costs, each fleet
route move and canal toll, the Tel el Kebir battle result, and withdrawal.
Summary events link to their household funding/payment, fleet movement/toll,
battle, territory-control, and withdrawal causes. Failure records distinguish
missing or unready fleets, inadequate transports, supply failure, unavailable
routes, denied canal access, and unaffordable tolls. No campaign rules changed.

Verification: campaign, geography, occupation, metric-catalog, and scenario
project suites passed (49 tests); three focused campaign playthroughs passed.
They cover readiness and route failures, successful movement, upkeep and toll
gates, battle-to-withdrawal causality, compact trace verification, and
trace-on/off state parity. Compilation and `git diff --check` passed. The
separate all-endings audit was stopped inside its long integration subprocess
and is not counted as a pass.

Phase 3 follow-up, 2026-10-18: Guided Egypt's naval responses now record the
pending-demand and response-stage gates, settlement affordability, unreliable
palace command, debt settlement, customs levy, disarmament, mediation timing,
hold-out timing, and naval defense result. Defense traces include the force
ratio and threshold, missing or deterred fleet outcomes, blockade state,
bombardment and its civilian/infrastructure effects. Each response summary
links to the debt, withdrawal, and bombardment events emitted during that
action. No response rules changed.

Verification: nine dedicated naval-response tests passed, covering gates,
all player choices, defense exits, exact transfer and withdrawal links,
trace-on/off parity, and compact `.ctr` serialization. Campaign, diplomacy,
coercion, geography and metric-catalog regression suites passed (37 tests), as
did the payment-path playthrough. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Egyptian autonomous naval-crisis turns now trace
coastal-access, payment, and domestic-protest gates; British intervention and
coastal-force decisions; squadron funding and arrival; French support funding
and fleet movement; recurring upkeep, French supply failure, resupply and
withdrawal; and Ottoman mediation timing, acceptance, and reason-specific
rejection. Blockade turns link to the expedition summary, and mediated
settlements link to their debt and withdrawal events. Warning-modal and idle
crisis pauses remain silent. No naval-crisis behavior changed.

Verification: ten dedicated naval-crisis tests passed, including compact
`.ctr` serialization; geography, diplomacy and naval-response suites passed
(20 tests). Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: naval escalation entry now records the trigger
reason, active-crisis rejection, stage transition, due turn and chapter-two
transition. A crisis can reopen after withdrawal under the current rule without
restarting chapter two. Creditor response effect events are passed through to
the escalation summary as direct causes. No trigger or chapter behavior
changed.

Verification: 15 naval-crisis and escalation tests passed, including
creditor-response causal linkage, trace-on/off parity and compact `.ctr`
verification. The combined naval, geography, diplomacy, creditor-situation
and metric-catalog regression set passed (41 tests), as did the funded-canal
campaign playthrough. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Alexandria revenue-inspection answers now trace
the pending-demand gate, publication or refusal, creditor-confidence change,
defaulted bond IDs and escalation attempt. A pre-escalation decision record
links the refusal and default condition into naval crisis entry; the final
response record links the decision and escalation. An already-active crisis
records the rejected repeat trigger. No response rules changed.

Verification: six dedicated fiscal-challenge tests passed, including compact
`.ctr` verification and trace-on/off parity. Project, metric-catalog,
creditor-situation and naval-crisis tests passed (31 tests). The fiscal-project
campaign playthrough passed. Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Alexandria revenue-office reviews now record
settled-claim and active-collection-assignment gates, or inspection-challenge
creation. Review records include claim size, assignment provenance, creditor
confidence delta, project site/timing, and recent revenue-report inputs. New
challenges retain their source project and review turn, and the later player
response links to that review before any refusal/default escalation. No
gameplay rules changed.

Verification: eight dedicated tests passed, including all review outcomes,
causal linkage into refusal/escalation, trace-on/off parity and compact `.ctr`
verification. Project and metric-catalog suites passed (13 tests). The Egypt
fiscal-project campaign playthrough passed. Compilation and `git diff --check`
passed.

Phase 3 follow-up, 2026-10-18: strategic-project starts, turn advances,
damage, repairs, and cancellation now emit lifecycle outcomes and rejection
reasons. The trace identifies selected crews, work progress, occupation,
integrity, staffing, public-food and upkeep gates. Wage summaries link to the
exact worker payments; canal crew meals link each public-store debit to queued
worker entitlements. Battle damage to the canal line links to its battle
outcome. No project rules or return values changed.

Verification: eight dedicated lifecycle tests passed, including action gates,
social/food blockers, wage and meal transfer linkage, battle damage, parity,
and compact `.ctr` validation. Strategic-project, metric-catalog, and two
focused playthroughs passed (15 tests). Campaign and campaign-trace suites
passed (18 tests). Compilation and `git diff --check` passed.

Phase 3 follow-up, 2026-10-18: Nile repair food reports now connect the
post-production harvest snapshot to a turn-scoped tile/good production event,
the repaired project's advance, and recent private harvest purchases. The
report labels the yield factor as realized and marks its sampling stage before
political-economy releases; it also records reserves, strikers, and underfed
households. Owner purchase-response events link to the transaction's cash and
food legs. Missing recent purchase events remain visible alongside their
operation IDs. Repeated same-turn reporting does not duplicate outcomes or
state records; no trace IDs were added to scenario state.

Verification: project, catalog, food-outcome, and current-turn production-index
regressions passed (15 tests). The Nile-repair debt-tradeoff playthrough passed.
The compact trace verified successfully. Compilation and `git diff --check`
passed.

Phase 2 follow-up, 2026-10-18: private warehouse releases now trace every
household's food need and cash affordability at the posted price, actual
purchase, and no-sale reason. District release outcomes link to the exact cash
and food legs. Opening the private grain market records the policy transition,
stock and release totals by district, and links to those outcomes; repeat
requests show the already-open gate. Automatic open-market releases have their
own trigger label. Trading behavior is unchanged.

Verification: grain-transfer, private-release, project, and metric-catalog
regressions passed (20 tests), including trace-on/off parity and compact `.ctr`
verification. Compilation and `git diff --check` passed.

Phase 2 follow-up, 2026-10-18: a bounded, trace-only index now carries private
household grain-sale events forward by buyer. When that household consumes
local inventory on a later turn, the intake record includes actual local food
units consumed and the recent sale events as candidate sources, alongside the
calorie deficit, reserve, and hunger changes. Because household food inventory
is fungible, source allocation remains explicitly unknown and purchase events
are not claimed as direct causes. Trace IDs stay outside simulation state.

Verification: the private-release integration test validates a paid sale,
later inventory consumption, candidate event IDs, unknown source allocation,
and compact `.ctr` verification. The private-release, grain-transfer, intake,
nutrition, metric-catalog, run-trace, Nile food-outcome, and food-security
regressions passed in focused suites (65 tests). A combined test invocation
failed only when the Nile food-outcome fixture ran after the run-trace module;
that fixture and the run-trace tests pass separately. Compilation and
`git diff --check` passed.

Phase 2 follow-up, 2026-10-18: each labor-frontier cotton and cloth delivered
quote now links to the seller ask used to construct it. Each paid scenario
transaction links to the exact delivered quote selected before settlement and
records its quote turn, currency, and delivered-price basis. This distinguishes
buyer cost from seller receipt and makes quote-to-settlement ordering explicit.
No market rule changed.

Verification: two scenario quote tests pass, covering quote replay and
seller-ask → delivered-quote → selected-transaction links with matching good,
buyer, seller, turn, currency, and price. Two focused labor-frontier market
tests and four market-affordability/codec tests passed. The complete
labor-frontier behavior suite still reports six failures in petition/protection
action state and timing tests; the quote-focused tests pass. Compilation and
`git diff --check` passed.

Phase 2 follow-up, 2026-10-18: labor-frontier quote and settlement records now
capture origin/destination tiles, seller/buyer nations, seller/buyer currencies,
currency mismatch, and an explicit no-conversion flag at evaluation time.
Paid-price records carry the selected quote's same membership and currency
context, preserving the state that existed before any later border change.
National reference-price and food-history aggregates already retain their
turn-specific territory membership and unconverted currency semantics.

Verification: scenario quote replay and ownership/currency assertions, the
historical cloth quote test, and the focused cloth market test passed. The full
labor-frontier behavior suite still has six petition/protection action timing
and state failures recorded above. Compilation and `git diff --check` passed.

Phase 5 follow-up, 2026-10-18: the trace query API and CLI reader accept exact
event IDs. The web price inspector can enter an event ID, show the selected
record and its market basis/currency/territory fields, and open any linked
upstream event by clicking its ID. A player can follow the scenario market
chain from paid transaction to chosen delivered quote to seller ask.

Verification: all 31 run-trace tests passed, including exact event-ID filters
in `RunTrace.query` and the CLI report. The web trace-query/download endpoint
and static JavaScript endpoint tests passed (2); `node --check web_client/client.js`
passed. Long trace result lists still need pagination.

Phase 5 follow-up, 2026-10-18: selecting a food-price chart point opens the
shared trace inspector for that exact turn. Nation-wide history points query
`goods.national_food_price`; selected-tile points query local `goods.price` for
food. The inspector retains exact-event input and clickable upstream IDs for
following quote, transaction, and formula evidence. Other chart metrics still
need source mappings and remain outside this slice.

Verification: the chart renderer's point-selection test confirms index, value,
turn, and hit-area behavior. UI utility/geometry/API transport tests passed;
web JavaScript serving and trace-query tests passed (2); JavaScript syntax
checks passed.
