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
- Sovereign bond purchases, proceeds, domestic underwriting, coupons,
  maturities, defaults, and early redemptions record signed nation treasury
  flows and the bond terms; municipal sewer underwriting records its project.
- Campaign Caisse debt records principal revisions, concessions, defaults,
  creditor collection assignments, payments, and signed Egypt/creditor treasury
  flows for assigned revenue interception.
- Public baby bonuses, scaled UBI, parental leave, and welfare record the
  treasury outflow, recipients, policy rate, and any funding shortfall.
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
quotes, settlements, and optional standalone `econsim.py --trace` run have
separate price records with replay checks for supported formulas. Remaining
price work is linking production, inventories, needs, accepted orders, and
settlements through time without implying a trade caused an earlier quote.
Imported shipment IDs now resolve across purchase, departure, arrival, supply,
quote, and paid sale when those source records exist. The strike-to-output
chain remains partial. The main market's `vwap` input is an unweighted
recent-sample mean. The web inspector can filter a tile and selected good;
historical chart points do not yet open that inspector directly.

The coverage checker reports a changed snapshot as unexplained when its final
value does not match a recorded calculation. Per-profession headcount snapshots
are sparse: unchanged counts, including zero categories, are omitted while the
membership-change calculation records retain before/after counts and agent IDs.
Treasury snapshots show cash and
deposit components, but treasury transfers are not yet comprehensively
instrumented. Several scenario operations still need mutation-point records.
Some secondary and elite AI candidate details remain partial. The current metric
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
