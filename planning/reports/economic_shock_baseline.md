# 20-turn economic baseline trace review

Trace run `a6dde09ee33543629148c2f619351ec4-1`; scenario `None`; seed `4242`; 884,681 events over turns 0–20.
Source commit: `b523f5f939453f9de09f3fbba874ea99ecd76616`. The trace is an observational startup run with no controlled shock or counterfactual.
All prices below distinguish actual transaction VWAP from the posted reference; each market quantity uses the trace's recorded unit basis.

## Furniture market: c50 (CNY)

The local wood-to-furniture chain shows tight furniture supply and a persistent price cap. The counts below are recorded production-zero reasons; they are not additive lost units. Missing market records stay blank rather than being interpreted as zero.

| Turn | Furniture ref. | Paid VWAP | Demand ratio | Bids | Offers | Sold | Furniture output | Missing-wood zeroes | Wood ref. | Wood sold |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 28.12 | 30.50 | 15.75 | 126.00 | 8.00 | 8.00 | 8.00 | 0.00 | 1.12 | 15.00 |
| 2 | 31.30 | 34.23 | 17.43 | 122.00 | 7.00 | 7.00 | 6.00 | 0.00 | 1.26 | 44.00 |
| 3 | 34.36 | 38.18 | 59.50 | 119.00 | 2.00 | 2.00 | 2.00 | 4.00 | 1.38 | 21.00 |
| 4 | 37.35 | 41.23 | 16 | 112.00 | 7.00 | 7.00 | 0.00 | 8.00 | 1.50 | 109.00 |
| 5 | 40.22 | 45.00 | 24.75 | 99.00 | 4.00 | 4.00 | 1.00 | 7.00 | 1.61 | 72.00 |
| 6 | 43.02 | 48.54 | 15.17 | 91.00 | 6.00 | 6.00 | 2.00 | 14.00 | 1.71 | 56.00 |
| 7 | 45.77 | 51.84 | 20 | 80.00 | 4.00 | 4.00 | 1.00 | 16.00 | 1.82 | 50.00 |
| 8 | 48.45 | 55.10 | 14.40 | 72.00 | 5.00 | 5.00 | 1.00 | 16.00 | 1.93 | 48.00 |
| 9 | 50 | 58.14 | 20 | 60.00 | 3.00 | 3.00 | 0.00 | 17.00 | 2.03 | 48.00 |
| 10 | 50 | 60.50 | 25 | 50.00 | 2.00 | 2.00 | 1.00 | 17.00 | 2.13 | 41.00 |
| 11 | 50 | — | 5 | 96.00 | — | — | 0.00 | 16.00 | 2.24 | 39.00 |
| 12 | 50 | 61 | 47 | 94.00 | 2.00 | 2.00 | 2.00 | 11.00 | 2.34 | 35.00 |
| 13 | 50 | 61 | 92 | 92.00 | 1.00 | 1.00 | 1.00 | 7.00 | 2.43 | 39.00 |
| 14 | 50 | 60.67 | 30.67 | 92.00 | 3.00 | 3.00 | 2.00 | 5.00 | 2.55 | 44.00 |
| 15 | 50 | 61 | 90 | 90.00 | 1.00 | 1.00 | 1.00 | 3.00 | 2.68 | 52.00 |
| 16 | 50 | 60.50 | 46.50 | 93.00 | 2.00 | 2.00 | 1.00 | 2.00 | 2.83 | 45.00 |
| 17 | 50 | 61 | 44 | 88.00 | 2.00 | 2.00 | 2.00 | 0.00 | 2.98 | 46.00 |
| 18 | 50 | 60.67 | 28.67 | 86.00 | 3.00 | 3.00 | 2.00 | 0.00 | 3.14 | 45.00 |
| 19 | 50 | 61 | 75 | 75.00 | 1.00 | 1.00 | 1.00 | 0.00 | 3.31 | 47.00 |
| 20 | 50 | 60.50 | 31.50 | 63.00 | 2.00 | 2.00 | 1.00 | 1.00 | 3.49 | 51.00 |

The c50 furniture reference is at the hard cap on 12 of 20 turns. Its actual paid VWAP reaches 61, exceeding the reference cap. At turn 10, the reference is 50, recorded demand ratio 25, bids 50, offers 2, sales 2 and output 1; 17 zero-output events cite unavailable wood. The cap applies to the reference, not the paid VWAP. This supports a local intermediate-input bottleneck hypothesis, but does not prove that wood scarcity alone explains the price path: labor, input purchasing and producer entry also need to be separated.

## Food: local supply versus household intake at turn 10

| Tile | Currency | Ref. | Paid VWAP | Demand ratio | Bids | Offers | Sold | Production | Intake shortfalls | Shortfall units / desired |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| c10 | JPY | 1 | 1 | 0.17 | 166.00 | 957 | 158.00 | 160.00 | 0.00 / 115.00 records | 0 / 653 |
| c46 | USD | 1.46 | 1.70 | 4.22 | 249.00 | 59 | 59.00 | 260.00 | 119.00 / 135.00 records | 303 / 737 |
| c59 | USD | 1.39 | 1.43 | 1.52 | 191.00 | 126.00 | 126.00 | 313.00 | 104.00 / 126.00 records | 214 / 681 |

c10 is the abundant-market comparison: offers substantially exceed funded bids, and the recorded intake cohort has no shortfall. At c46 and c59, local offers are below bids and many observed households still report shortfalls, despite positive local production. Production is not the same as food offered for sale or accessible to a household; inventory carryover, meal reserves, trader stocks, allocation and relief remain relevant. c46 is USD while c10 is JPY, so nominal prices cannot be compared across those tiles without an exchange-rate basis.

Representative source events:

- **c50 furniture, turn 10:** price update: `a6dde09ee33543629148c2f619351ec4-1:373126`; clearing: `a6dde09ee33543629148c2f619351ec4-1:373125`; paid-price VWAP: `a6dde09ee33543629148c2f619351ec4-1:373124`; production total: `a6dde09ee33543629148c2f619351ec4-1:372020`; missing-wood zero: `a6dde09ee33543629148c2f619351ec4-1:371911`
- **c50 wood, turn 10:** price update: `a6dde09ee33543629148c2f619351ec4-1:373063`; clearing: `a6dde09ee33543629148c2f619351ec4-1:373062`; production total: `a6dde09ee33543629148c2f619351ec4-1:372019`
- **c46 food, turn 10:** price update: `a6dde09ee33543629148c2f619351ec4-1:367751`; clearing: `a6dde09ee33543629148c2f619351ec4-1:367750`; paid-price VWAP: `a6dde09ee33543629148c2f619351ec4-1:367749`; production total: `a6dde09ee33543629148c2f619351ec4-1:367043`; shortfall intake: `a6dde09ee33543629148c2f619351ec4-1:368091`

## Coverage and limits

The analyzer found 456 of 1413 market reference-price observations without a corresponding clearing summary. Its panel retains coverage flags and missing values. Food intake records are a trace-observed cohort, not a census denominator guaranteed to cover every resident or every turn.
The current trace is strong for posted-price formulas, order totals, sales, production totals, producer inventories and recorded food intake. It does not by itself provide a complete household-cohort panel, all wage/profit/credit balances, or complete physical inventories in transit. Phase 2 must combine trace events with canonical state snapshots for matched comparisons, and must preserve coverage and missingness rather than filling gaps with zeros.

## Reproduction

```sh
venv/bin/python economic_shock_analysis.py \
  tmp/trace-fat-analysis/prototype.source.ctr \
  --source-commit b523f5f939453f9de09f3fbba874ea99ecd76616 \
  --json-out tmp/economic-shock-baseline-panel.json \
  --report-out planning/reports/economic_shock_baseline.md
```
