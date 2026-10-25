# Paired 20-turn economic shock screen

Scenario `supply_rivalry`, seed `812`, simulation source commit(s) `3d2105acfd9ddfcceb6559614750cc655f5a1331`. Turns 1-7 are pre-shock; the shock is active on turns 8-11 and removed before turn 12. Recovery is observed through turn 20.
One paired seed per intervention is an exploratory screen, not a robustness or empirical-calibration claim.

## 50% temporary cotton recipe-output reduction

Target tile `Cotton Fields`. Turn-7 complete canonical states match: **True**. Control trace: `tmp/traces/7a5e60fa3c3b4ede8c6adf0970848517-1.ctr`; treatment trace: `tmp/traces/e9d7ed0e683b4dd983547756237083f1-1.ctr`.

Treatment minus control in cotton markets at selected turns:

| Turn | Tile | Good | Ref. delta | Paid VWAP delta | Bids | Offers | Imports | Supply | Sold | Output | Inventory |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 7 | Cotton Fields | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 7 | Rival Port | cloth | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 7 | Rival Port | cotton | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 8 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 8 | Cotton Fields | cotton | 0.00 | — | 0 | — | — | -1 | — | -1 | -1.00 |
| 8 | Rival Port | cloth | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 8 | Rival Port | cotton | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 9 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 9 | Cotton Fields | cotton | 0.01 | 0.02 | 0 | -1 | 0 | -1 | 0 | 0 | -1.00 |
| 9 | Rival Port | cloth | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 9 | Rival Port | cotton | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 10 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 10 | Cotton Fields | cotton | 0.03 | 0.47 | 0 | -2 | 0 | -2 | -2 | -1 | 0.00 |
| 10 | Rival Port | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 10 | Rival Port | cotton | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 11 | Cotton Fields | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 11 | Cotton Fields | cotton | 0.06 | 0.09 | 2 | -2 | 0 | -2 | -2 | -2 | 0.00 |
| 11 | Rival Port | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 11 | Rival Port | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 12 | Cotton Fields | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 12 | Cotton Fields | cotton | 0.07 | 0.12 | 1 | -1 | 0 | -1 | -1 | 0 | 0.00 |
| 12 | Rival Port | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 12 | Rival Port | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 15 | Cotton Fields | cloth | 0.39 | — | 1 | — | — | -2 | — | 0 | 0.00 |
| 15 | Cotton Fields | cotton | 0.01 | — | 7 | — | — | 0 | — | 0 | 0.00 |
| 15 | Rival Port | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 15 | Rival Port | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 20 | Cotton Fields | cloth | -0.04 | — | -7 | — | — | 0 | — | 0 | 0.00 |
| 20 | Cotton Fields | cotton | -0.08 | — | -2 | — | — | 0 | — | 0 | 0.00 |
| 20 | Rival Port | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 20 | Rival Port | cotton | 0.00 | — | -3 | — | — | 0 | — | 0 | 0.00 |

Shock-window totals on turns 8-11 at `Cotton Fields`:

| Cotton Fields measure | Control total | Treatment total | Delta | Paired turns |
|---|---:|---:|---:|---:|
| Units sold | 20 | 16 | -4 | 3/4 |
| Submitted bids | 55 | 57 | 2 | 4/4 |
| Recorded offered supply | 37 | 31 | -6 | 4/4 |
| Production | 8 | 4 | -4 | 4/4 |
| Food shortfall units | 77.00 | 77.00 | 0.00 | 4/4 |
| Mean reference-price delta | - | - | 0.02 | 4/4 |
| Mean paid-VWAP delta | - | - | 0.19 | 3/4 |

Totals use only paired observations; denominators show coverage, and missing values remain unavailable.

### Audit gates

- `control`: settlement bounds **PASS** (85/200 rows had clearing summaries); structural/supported-formula checks **PASS**; nation-account closes **40/40** verified; treasury fully attributed **40/40 turns** (complete).
- `treatment`: settlement bounds **PASS** (80/200 rows had clearing summaries); structural/supported-formula checks **PASS**; nation-account closes **40/40** verified; treasury fully attributed **40/40 turns** (complete).

Structural and supported-formula checks cover only audited rules; complete causal coverage is not established. Nation account closes and treasury attribution are reported above; neither gate establishes complete goods-stock conservation or causal coverage. See the plan for remaining limits.

### Named actors and cotton logistics

| Shock-window observation | Control | Treatment | Treatment minus control |
|---|---:|---:|---:|
| Cotton market fills (units) | 26.00 | 22.00 | -4.00 |
| Meridian Mill submitted bids (units) | 26.00 | 28.00 | 2.00 |
| Meridian Mill desired target on observed orders | 7.00 | 7.00 | 0.00 |
| Unshocked target on observed mill orders | 7.00 | 7.00 | 0.00 |
| Cotton route departures (units) | 0 | 0 | 0 |
| Cotton route arrivals (units) | 0 | 0 | 0 |
| Named growers' food intake (units) | 34.00 | 34.00 | 0.00 |

Route event coverage: control 0 departures and 0 arrivals; treatment 0 departures and 0 arrivals. Mill cotton order events observed: control 3 and treatment 3; the target override appears on 0 treatment order rows. Across all 20 turns, cotton route events were 1 departures / 1 arrivals in control and 1 / 1 in treatment. Named-actor turn rows observed during the shock: 16 control and 16 treatment.

The table below reports the named growers and mills at the end of the shock window. Cash and inventories are state observations; they are not by themselves a complete welfare or goods-conservation measure.

| Actor | Turn | Control cash | Treatment cash | Delta | Control food | Treatment food | Control cotton | Treatment cotton | Control cloth | Treatment cloth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Amina, secure grower | 7 | 1.07 | 1.07 | 0.00 | 3 | 3 | 6 | 6 | 0 | 0 |
| Amina, secure grower | 11 | 17.33 | 9.31 | -8.02 | 14 | 14 | 0 | 0 | 0 | 0 |
| Binta, cash-poor grower | 7 | 0.57 | 0.57 | 0.00 | 1 | 1 | 4 | 4 | 0 | 0 |
| Binta, cash-poor grower | 11 | 24.90 | 15.19 | -9.71 | 3 | 3 | 0 | 0 | 0 | 0 |
| Meridian Mill | 7 | 6.00 | 6.00 | 0.00 | 14 | 14 | 0 | 0 | 16 | 16 |
| Meridian Mill | 11 | 265.45 | 263.96 | -1.48 | 6 | 6 | 10 | 8 | 8 | 8 |
| Vesper Mill | 7 | 6.00 | 6.00 | 0.00 | 21 | 21 | 0 | 0 | 3 | 3 |
| Vesper Mill | 11 | 172.70 | 172.70 | 0.00 | 34 | 34 | 0 | 0 | 0 | 0 |

Scenario-hook integrity: control `not applicable`; treatment `True`. The treatment hook checks that native scenario stepping preserves the cotton intervention through turn 11 and restores it before turn 12.

The route events link physical cotton departures to arrivals; market fills are reported separately because arrival does not guarantee sale to the target mill. Post-shock draws can diverge after turn 7, so later arm differences are not draw-aligned.

## 50% increase in Meridian Mill's cotton inventory target

Target tile `Cotton Fields`. Turn-7 complete canonical states match: **True**. Control trace: `tmp/traces/ae1e7cd35f4b4aac9d7f83223ca3d124-1.ctr`; treatment trace: `tmp/traces/d93655b0a1214b65a5114795cedff7de-1.ctr`.

Treatment minus control in cotton markets at selected turns:

| Turn | Tile | Good | Ref. delta | Paid VWAP delta | Bids | Offers | Imports | Supply | Sold | Output | Inventory |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 7 | Cotton Fields | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 7 | Rival Port | cloth | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 7 | Rival Port | cotton | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 8 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 8 | Cotton Fields | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 8 | Rival Port | cloth | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 8 | Rival Port | cotton | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 9 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 9 | Cotton Fields | cotton | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 9 | Rival Port | cloth | 0.00 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 9 | Rival Port | cotton | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 10 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 10 | Cotton Fields | cotton | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 10 | Rival Port | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 10 | Rival Port | cotton | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 11 | Cotton Fields | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 11 | Cotton Fields | cotton | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 11 | Rival Port | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 11 | Rival Port | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 12 | Cotton Fields | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 12 | Cotton Fields | cotton | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 12 | Rival Port | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 12 | Rival Port | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 15 | Cotton Fields | cloth | 0.00 | 0.00 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 |
| 15 | Cotton Fields | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 15 | Rival Port | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 15 | Rival Port | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 20 | Cotton Fields | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 20 | Cotton Fields | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 20 | Rival Port | cloth | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |
| 20 | Rival Port | cotton | 0.00 | — | 0 | — | — | 0 | — | 0 | 0.00 |

Shock-window totals on turns 8-11 at `Cotton Fields`:

| Cotton Fields measure | Control total | Treatment total | Delta | Paired turns |
|---|---:|---:|---:|---:|
| Units sold | 20 | 20 | 0 | 3/4 |
| Submitted bids | 55 | 55 | 0 | 4/4 |
| Recorded offered supply | 37 | 37 | 0 | 4/4 |
| Production | 8 | 8 | 0 | 4/4 |
| Food shortfall units | 77.00 | 77.00 | 0.00 | 4/4 |
| Mean reference-price delta | - | - | 0.00 | 4/4 |
| Mean paid-VWAP delta | - | - | 0.00 | 3/4 |

Totals use only paired observations; denominators show coverage, and missing values remain unavailable.

### Audit gates

- `control`: settlement bounds **PASS** (85/200 rows had clearing summaries); structural/supported-formula checks **PASS**; nation-account closes **40/40** verified; treasury fully attributed **40/40 turns** (complete).
- `treatment`: settlement bounds **PASS** (85/200 rows had clearing summaries); structural/supported-formula checks **PASS**; nation-account closes **40/40** verified; treasury fully attributed **40/40 turns** (complete).

Structural and supported-formula checks cover only audited rules; complete causal coverage is not established. Nation account closes and treasury attribution are reported above; neither gate establishes complete goods-stock conservation or causal coverage. See the plan for remaining limits.

### Named actors and cotton logistics

| Shock-window observation | Control | Treatment | Treatment minus control |
|---|---:|---:|---:|
| Cotton market fills (units) | 26.00 | 26.00 | 0.00 |
| Meridian Mill submitted bids (units) | 26.00 | 26.00 | 0.00 |
| Meridian Mill desired target on observed orders | 7.00 | 11.00 | 4.00 |
| Unshocked target on observed mill orders | 7.00 | 7.00 | 0.00 |
| Cotton route departures (units) | 0 | 0 | 0 |
| Cotton route arrivals (units) | 0 | 0 | 0 |
| Named growers' food intake (units) | 34.00 | 34.00 | 0.00 |

Route event coverage: control 0 departures and 0 arrivals; treatment 0 departures and 0 arrivals. Mill cotton order events observed: control 3 and treatment 3; the target override appears on 3 treatment order rows. Across all 20 turns, cotton route events were 1 departures / 1 arrivals in control and 1 / 1 in treatment. Named-actor turn rows observed during the shock: 16 control and 16 treatment.

The table below reports the named growers and mills at the end of the shock window. Cash and inventories are state observations; they are not by themselves a complete welfare or goods-conservation measure.

| Actor | Turn | Control cash | Treatment cash | Delta | Control food | Treatment food | Control cotton | Treatment cotton | Control cloth | Treatment cloth |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Amina, secure grower | 7 | 1.07 | 1.07 | 0.00 | 3 | 3 | 6 | 6 | 0 | 0 |
| Amina, secure grower | 11 | 17.33 | 17.33 | 0.00 | 14 | 14 | 0 | 0 | 0 | 0 |
| Binta, cash-poor grower | 7 | 0.57 | 0.57 | 0.00 | 1 | 1 | 4 | 4 | 0 | 0 |
| Binta, cash-poor grower | 11 | 24.90 | 24.90 | 0.00 | 3 | 3 | 0 | 0 | 0 | 0 |
| Meridian Mill | 7 | 6.00 | 6.00 | 0.00 | 14 | 14 | 0 | 0 | 16 | 16 |
| Meridian Mill | 11 | 265.45 | 265.45 | 0.00 | 6 | 6 | 10 | 10 | 8 | 8 |
| Vesper Mill | 7 | 6.00 | 6.00 | 0.00 | 21 | 21 | 0 | 0 | 3 | 3 |
| Vesper Mill | 11 | 172.70 | 172.70 | 0.00 | 34 | 34 | 0 | 0 | 0 | 0 |

Scenario-hook integrity: control `not applicable`; treatment `True`. The treatment hook checks that native scenario stepping preserves the cotton intervention through turn 11 and restores it before turn 12.

The route events link physical cotton departures to arrivals; market fills are reported separately because arrival does not guarantee sale to the target mill. Post-shock draws can diverge after turn 7, so later arm differences are not draw-aligned.

## Reproduction

```sh
venv/bin/python economic_shock_experiment.py --seed 812 \
  --scenario supply_rivalry --out-dir tmp/economic-shocks/supply-rivalry/seed-812 --reuse-existing --audit
```

The JSON retains full turn panels, state snapshots, intervention IDs, pre-shock digests, audit gates and trace paths. Compressed traces are generated under `tmp/traces/` and are not checked into Git.
