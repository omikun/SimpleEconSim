# Paired 20-turn economic shock screen

Scenario `default`, seed `4242`, simulation source commit(s) `b4da81d64dd7a72f73f7b8fd9e4b9f591a5b4149`. Turns 1-7 are pre-shock; the shock is active on turns 8-11 and removed before turn 12. Recovery is observed through turn 20.
One paired seed per intervention is an exploratory screen, not a robustness or empirical-calibration claim.

## 50% temporary wood recipe-output reduction

Target tile `c50`. Turn-7 complete canonical states match: **True**. Control trace: `tmp/traces/eaf7e00cd14348f3b03897af36140348-1.ctr`; treatment trace: `tmp/traces/a57dbd77d15c414f8746eeb4262b975a-1.ctr`.

Treatment minus control on `c50` at selected turns:

| Turn | Good | Ref. delta | Paid VWAP delta | Bids | Offers | Imports | Supply | Sold | Output | Inventory | Food shortfall | Nonfood consumed |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | furniture | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | — |
| 7 | wood | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | 0 |
| 8 | furniture | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | 0 |
| 8 | wood | 0.00 | -0.00 | 8 | -10 | 0 | -10 | -10 | -10 | 0.00 | — | -4 |
| 9 | furniture | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | 0 |
| 9 | wood | -0.00 | 0.00 | 14 | -16 | 0 | -16 | -16 | -11 | 0.00 | — | -7 |
| 10 | furniture | 0.00 | 0.00 | 1 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | 0 |
| 10 | wood | 0.00 | 0.01 | 14 | -16 | 0 | -16 | -16 | -7 | 0.00 | — | 2 |
| 11 | furniture | 0.00 | 0.00 | -1 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | 0 |
| 11 | wood | 0.00 | 0.00 | 37 | -18 | 0 | -18 | -18 | -11 | 0.00 | — | -7 |
| 12 | furniture | 0.00 | — | 1 | — | — | -1 | — | -1 | 0.00 | — | — |
| 12 | wood | 0.00 | 0.01 | 57 | -16 | 0 | -16 | -16 | -8 | 0.00 | — | -10 |
| 15 | furniture | 0.00 | — | -14 | — | — | -2 | — | -2 | 0.00 | — | — |
| 15 | wood | 0.00 | 0.01 | 82 | -23 | 0 | -23 | -23 | -10 | 0.00 | — | -21 |
| 20 | furniture | 0.00 | — | -14 | — | — | -2 | — | -2 | 0.00 | — | — |
| 20 | wood | 0.00 | -0.07 | 77 | 26 | 0 | 26 | 26 | 12 | 0.00 | — | -1 |

Shock-window totals on turns 8-11:

| c50 measure | Control total | Treatment total | Delta | Paired turns |
|---|---:|---:|---:|---:|
| Units sold | 143 | 83 | -60 | 4/4 |
| Submitted bids | 1360 | 1433 | 73 | 4/4 |
| Recorded offered supply | 143 | 83 | -60 | 4/4 |
| Production | 58 | 19 | -39 | 4/4 |
| Food shortfall units | 0.00 | 0.00 | 0.00 | 4/4 |
| Nonfood units consumed | 112 | 96 | -16 | 4/4 |
| Mean reference-price delta | - | - | 0.00 | 4/4 |
| Mean paid-VWAP delta | - | - | 0.00 | 4/4 |

Totals use only paired observations; denominators show coverage, and missing values remain unavailable.

### Audit gates

- `control`: settlement bounds **PASS** (655/720 rows had clearing summaries); structural/supported-formula checks **PASS**; nation-account closes **60/60** verified; treasury fully attributed **60/60 turns** (complete).
- `treatment`: settlement bounds **PASS** (646/720 rows had clearing summaries); structural/supported-formula checks **PASS**; nation-account closes **60/60** verified; treasury fully attributed **60/60 turns** (complete).

Structural and supported-formula checks cover only audited rules; complete causal coverage is not established. Nation account closes and treasury attribution are reported above; neither gate establishes complete goods-stock conservation or causal coverage. See the plan for remaining limits.

Read the intervention first against realized wood output, offers and sales, then against downstream furniture. The posted furniture reference is capped, so paid VWAP and quantities are needed to assess price pressure. Turn-7 states match, but later random streams are not draw-aligned after paths diverge.

## 50% increase in household furniture inventory targets

Target tile `c50`. Turn-7 complete canonical states match: **True**. Control trace: `tmp/traces/af2a8a6ba9c44292a738fbd39d74d17d-1.ctr`; treatment trace: `tmp/traces/dfc05380bc0640049c776f86152ef400-1.ctr`.

Treatment minus control on `c50` at selected turns:

| Turn | Good | Ref. delta | Paid VWAP delta | Bids | Offers | Imports | Supply | Sold | Output | Inventory | Food shortfall | Nonfood consumed |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | furniture | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | — |
| 8 | furniture | 0.00 | 0.00 | 3 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | -1 |
| 9 | furniture | 0.00 | -0.24 | 3 | 1 | 0 | 1 | 1 | 0 | 0.00 | — | — |
| 10 | furniture | 0.00 | -0.17 | 1 | -1 | 0 | -1 | -1 | 0 | 0.00 | — | 6 |
| 11 | furniture | 0.00 | 0.33 | 1 | 0 | 0 | 0 | 0 | 1 | 0.00 | — | 0 |
| 12 | furniture | 0.00 | 0.00 | 4 | 0 | 0 | 0 | 0 | 0 | 0.00 | — | 0 |
| 15 | furniture | 0.00 | 0.00 | 2 | -1 | 0 | -1 | -1 | -1 | 0.00 | — | -1 |
| 20 | furniture | 0.00 | — | -8 | — | — | -2 | — | -2 | 0.00 | — | — |

Shock-window totals on turns 8-11:

| c50 measure | Control total | Treatment total | Delta | Paired turns |
|---|---:|---:|---:|---:|
| Units sold | 15 | 15 | 0 | 4/4 |
| Submitted bids | 310 | 318 | 8 | 4/4 |
| Recorded offered supply | 15 | 15 | 0 | 4/4 |
| Production | 7 | 8 | 1 | 4/4 |
| Food shortfall units | 0.00 | 0.00 | 0.00 | 4/4 |
| Nonfood units consumed | 24 | 29 | 5 | 3/4 |
| Mean reference-price delta | - | - | 0.00 | 4/4 |
| Mean paid-VWAP delta | - | - | -0.02 | 4/4 |

Totals use only paired observations; denominators show coverage, and missing values remain unavailable.

### Audit gates

- `control`: settlement bounds **PASS** (655/720 rows had clearing summaries); structural/supported-formula checks **PASS**; nation-account closes **60/60** verified; treasury fully attributed **60/60 turns** (complete).
- `treatment`: settlement bounds **PASS** (660/720 rows had clearing summaries); structural/supported-formula checks **PASS**; nation-account closes **60/60** verified; treasury fully attributed **60/60 turns** (complete).

Structural and supported-formula checks cover only audited rules; complete causal coverage is not established. Nation account closes and treasury attribution are reported above; neither gate establishes complete goods-stock conservation or causal coverage. See the plan for remaining limits.

The intervention increases desired furniture stocks for half of eligible residents. Submitted bids show demand; price, fills, household consumption, food intake and budgets show whether it became realized welfare or displaced other spending.

## Reproduction

```sh
venv/bin/python economic_shock_experiment.py --seed 4242 \
  --out-dir tmp/economic-shocks/seed-4242 --reuse-existing --audit
```

The JSON retains full turn panels, state snapshots, intervention IDs, pre-shock digests, audit gates and trace paths. Compressed traces are generated under `tmp/traces/` and are not checked into Git.
