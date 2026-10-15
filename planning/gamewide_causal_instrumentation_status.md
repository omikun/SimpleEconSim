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
food prices; the national Macro tab has a **Why AI?** button.

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
- Nation AI records evaluated gates and submitted intents; intent outcomes
  link back to the decision. Elite planning records selected action and cash
  outcome. Candidate details for elite plans are still partial.

## Known gaps

The coverage checker reports a changed snapshot as unexplained when its final
value does not match a recorded calculation. Treasury snapshots show cash and
deposit components, but treasury transfers are not yet comprehensively
instrumented. Bank lending, bonds, rents, migration, disease, ecology, war,
construction, and several scenario operations still need mutation-point
records. The current metric catalog does not yet cover every displayed field;
the UI shows unavailable comparison placeholders as such. Desktop charts do
not yet have a trace drilldown, and save/rebranch and a persistent query index
are not implemented. The file is queried by scanning JSONL.

The 20-turn labor scenario run used for the first coverage gate recorded
9,043 rows in 5.3 MB, with 20 valid checkpoints and no currency-audit
violations. Tracing on and off produced the same sampled state SHA-256.
All changed snapshots in that run matched calculation records except treasury
(40 changes). A calculation match establishes the displayed value and its
immediate inputs; it does not by itself establish every upstream cause.
