# Causal run trace: implementation status

The live server writes one JSONL file per world generation to `tmp/traces/`. A
bounded recent ring supports live inspection. Every completed turn has a hash
checkpoint. The old collective report remains available separately.

## Inspect a run

```bash
venv/bin/python trace_report.py --run tmp/traces/RUN.jsonl --turn 12 --entity tile:Delta --metric goods.price --verify
venv/bin/python trace_coverage.py --run tmp/traces/RUN.jsonl
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
- Corporate and independent production rolls use the existing RNG draws.
  Price updates link the prior clearing summaries used as market samples.
- Faction grievance sources, protest energy, unrest roll and takeover/garrison
  result, and legitimacy drift. National population, GDP, cost of living, and
  protest energy have member tile values and aggregation rules.
- Bilateral FX mid changes record reserve ratio, pressure, PPP, regime, and
  band; bank conversions and trader order matches record actual transfers.
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
- Treasury phase boundaries, tax receipts, tariffs, government borrowing and
  loan service, food spending, army payroll, and scenario sales taxes are
  recorded as signed flows. End-of-turn reconciliation shows any unattributed
  residual rather than assigning it to a plausible source.
- Nation AI records evaluated gates and submitted intents; intent outcomes
  link back to the decision. Elite planning records selected action and cash
  outcome. Candidate details for elite plans are still partial.

## Known gaps

The coverage checker reports a changed snapshot as unexplained when its final
value does not match a recorded calculation. Treasury snapshots show cash and
deposit components, but treasury transfers are not yet comprehensively
instrumented. Bank lending outside government deficit loans, bonds, rent flows,
migration, non-disease health attrition and mortality attribution,
trade-transmitted infection, war, construction, and several scenario
operations still need mutation-point records. The current metric
catalog does not yet cover every displayed field;
`inventory_region_histories()` labels legacy series as instrumented or
untraced so a missing probe is visible during development.
The UI shows unavailable comparison placeholders as such. Desktop charts do
not yet have a trace drilldown, and save/rebranch and a persistent query index
are not implemented. The file is queried by scanning JSONL.

The first 20-turn labor scenario coverage run recorded 9,043 rows in 5.3 MB,
with 20 valid checkpoints and no currency-audit violations. Tracing on and off
produced the same sampled state SHA-256. This run predates the later treasury
and ecology probes, so its row count and coverage are a baseline rather than a
current measurement. A calculation match establishes the displayed value and
its immediate inputs; it does not by itself establish every upstream cause.
