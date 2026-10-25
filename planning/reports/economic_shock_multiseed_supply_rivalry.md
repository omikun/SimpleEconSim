# 5-seed supply-rivalry shock screen

Matched 20-turn runs at seeds 812, 813, 814, 815, 816. The two interventions are analyzed separately; turns 8–11 are the shock window and later differences are not draw-aligned after RNG paths diverge. Per-seed ranges are descriptive, not confidence intervals or empirical calibration.

Simulation provenance by seed: 812: `38d7a4413196ac5c27e17b5746ff9d78c91c7bf0` (4 arms; dirty 0); 813: `38d7a4413196ac5c27e17b5746ff9d78c91c7bf0` (4 arms; dirty 0); 814: `38d7a4413196ac5c27e17b5746ff9d78c91c7bf0` (4 arms; dirty 0); 815: `38d7a4413196ac5c27e17b5746ff9d78c91c7bf0` (4 arms; dirty 0); 816: `38d7a4413196ac5c27e17b5746ff9d78c91c7bf0` (4 arms; dirty 0).

## Deep trace audits

Deep audits cover 20/20 arm traces. The audited arms pass 800/800 public-account closes and attribute 800/800 treasury turns. Bounded structural/formula issues: 0; maximum absolute residual total within any arm: 1.73e-12. Complete causal coverage is reported in 0/20 audited arms.

| Seed | Deep-audited arms | Account closes | Treasury turns | Largest arm residual | Formula issues |
|---:|---:|---:|---:|---:|---:|
| 812 | 4/4 | 160/160 | 160/160 | 1.26e-12 | 0 |
| 813 | 4/4 | 160/160 | 160/160 | 1.23e-12 | 0 |
| 814 | 4/4 | 160/160 | 160/160 | 1.73e-12 | 0 |
| 815 | 4/4 | 160/160 | 160/160 | 1.07e-12 | 0 |
| 816 | 4/4 | 160/160 | 160/160 | 1.50e-12 | 0 |

## Temporary cotton supply reduction

Turn-7 complete-state match: 5/5; scenario hook passes: 5/5; market gates pass in both arms: 5/5.

Shock-window paired effects in Cotton Fields and connected markets. Flow quantities sum observed turn deltas; producer inventory is the point-in-time turn-11 difference; price rows average per-turn percent changes from that seed's control.

| Measure | 812 | 813 | 814 | 815 | 816 | Mean | Range | Seeds observed | Turn coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cotton production | -4.00 | -8.00 | -9.00 | -3.00 | -4.00 | -5.60 | -9.00 to -3.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cotton offered supply | -6.00 | -8.00 | -9.00 | -4.00 | -4.00 | -6.20 | -9.00 to -4.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cotton units sold | -4.00 | -8.00 | -9.00 | -3.00 | -4.00 | -5.60 | -9.00 to -3.00 | 5/5 | 812:3/4, 813:4/4, 814:4/4, 815:3/4, 816:3/4 |
| Cotton submitted bids | 2.00 | 8.00 | 6.00 | 2.00 | 2.00 | 4.00 | 2.00 to 8.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cotton producer inventory at T11 | 0.00 | 0.00 | -1.00 | 0.00 | -1.00 | -0.40 | -1.00 to 0.00 | 5/5 | 812:1/1, 813:1/1, 814:1/1, 815:1/1, 816:1/1 |
| Cotton reference-price change (%) | 0.54 | 0.36 | 0.11 | 0.15 | 0.01 | 0.23 | 0.01 to 0.54 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cotton paid-VWAP change (%) | 4.20 | 2.52 | 2.48 | 0.68 | 0.54 | 2.09 | 0.54 to 4.20 | 5/5 | 812:3/4, 813:4/4, 814:4/4, 815:3/4, 816:3/4 |
| Cloth production | 0.00 | -8.00 | -4.00 | 0.00 | 0.00 | -2.40 | -8.00 to 0.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cloth units sold | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:1/4, 813:1/4, 814:1/4, 815:1/4, 816:1/4 |
| Cloth paid-VWAP change (%) | 0.00 | 0.00 | 0.17 | 0.00 | 0.00 | 0.03 | 0.00 to 0.17 | 5/5 | 812:1/4, 813:1/4, 814:1/4, 815:1/4, 816:1/4 |
| Rival Port cotton units sold | 0.00 | -2.00 | -2.00 | 0.00 | 0.00 | -0.80 | -2.00 to 0.00 | 5/5 | 812:3/4, 813:3/4, 814:2/4, 815:3/4, 816:1/4 |
| Rival Port cotton paid-VWAP change (%) | 0.00 | 0.61 | 3.80 | 0.00 | 0.00 | 0.88 | 0.00 to 3.80 | 5/5 | 812:2/4, 813:3/4, 814:2/4, 815:2/4, 816:1/4 |
| Rival Port cloth units sold | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Rival Port cloth paid-VWAP change (%) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:2/4, 813:2/4, 814:1/4, 815:2/4, 816:2/4 |

Paid prices are only compared when both arms recorded a positive control transaction price. Missing clearings are excluded and shown in turn coverage, never treated as zero.

### Meridian Mill cotton orders

Control and treatment order totals use observed order rows; the treatment's unshocked target is recorded alongside the override so desired demand is separated from submitted bids.

| Seed | Control rows | Treatment rows | Control target | Treated target | Treatment unshocked target | Target uplift | Control bids | Treatment bids | Override rows |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 812 | 3 | 3 | 7.00 | 7.00 | 7.00 | 0.00 | 26.00 | 28.00 | 0 |
| 813 | 3 | 3 | 6.00 | 6.00 | 6.00 | 0.00 | 25.00 | 26.00 | 0 |
| 814 | 3 | 3 | 6.00 | 6.00 | 6.00 | 0.00 | 25.00 | 25.00 | 0 |
| 815 | 3 | 3 | 9.00 | 9.00 | 9.00 | 0.00 | 20.00 | 22.00 | 0 |
| 816 | 3 | 3 | 7.00 | 7.00 | 7.00 | 0.00 | 26.00 | 28.00 | 0 |

A missing mill order row means no order event was observed for that turn; the table reports row counts rather than imputing a zero target.

### Stable named actors

Effects on stocks are treatment-minus-control differences in the actor's turn-7-to-11 change. Flow effects sum paired observed turns 8–11. These are actor-level accounting indicators, not a complete welfare index.

| Seed | Actor | Cash change | Food stock change | Cotton stock change | Cloth stock change | Food intake | Output | Sales cash | Input costs | Wages | Debt / bank debt change | Flow coverage |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 812 | Amina, secure grower | -8.02 | 0.00 | 0.00 | 0.00 | 0.00 | -2.00 | -9.34 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 812 | Binta, cash-poor grower | -9.71 | 0.00 | 0.00 | 0.00 | 0.00 | -2.00 | -9.72 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 812 | Meridian Mill | -1.48 | 0.00 | -2.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.27 | 0.00 | 0.00 / -7.25 | 4, 4, 4, 4, 4 |
| 812 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 813 | Amina, secure grower | -17.64 | 3.00 | 0.00 | 0.00 | -2.00 | -5.00 | -22.72 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 813 | Binta, cash-poor grower | -18.62 | 0.00 | 0.00 | 0.00 | 0.00 | -4.00 | -21.97 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 813 | Meridian Mill | -0.16 | 1.00 | 1.00 | -8.00 | 0.00 | -8.00 | 0.00 | -35.14 | 0.00 | 0.00 / -17.96 | 4, 4, 4, 4, 4 |
| 813 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 814 | Amina, secure grower | -16.95 | -4.00 | 0.00 | 0.00 | 0.00 | -4.00 | -22.26 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 814 | Binta, cash-poor grower | -23.58 | -3.00 | 0.00 | 0.00 | -2.00 | -5.00 | -28.90 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 814 | Meridian Mill | -0.90 | 0.00 | 0.00 | -4.00 | 0.00 | -4.00 | 0.28 | -23.63 | 0.00 | 0.00 / -19.61 | 4, 4, 4, 4, 4 |
| 814 | Vesper Mill | -0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.09 | 0.00 | 0.00 / 0.13 | 4, 4, 4, 4, 4 |
| 815 | Amina, secure grower | 1.30 | -1.00 | 0.00 | 0.00 | -2.00 | -1.00 | -3.12 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 815 | Binta, cash-poor grower | -8.56 | 0.00 | 0.00 | 0.00 | -2.00 | -2.00 | -9.84 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 815 | Meridian Mill | -8.30 | 6.00 | -2.00 | 0.00 | 0.00 | 0.00 | 0.00 | -0.08 | 0.00 | 0.00 / -8.15 | 4, 4, 4, 4, 4 |
| 815 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 816 | Amina, secure grower | -9.44 | 0.00 | 0.00 | 0.00 | -2.00 | -2.00 | -10.59 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 816 | Binta, cash-poor grower | -9.45 | 0.00 | 0.00 | 0.00 | -2.00 | -2.00 | -10.59 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 816 | Meridian Mill | -5.22 | 3.00 | -2.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / -10.20 | 4, 4, 4, 4, 4 |
| 816 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |

Flow coverage columns list observed turns, in order for food intake, output, sales cash, input costs and wages; each denominator is four. These are observed transactions, not a complete profit calculation. A stock value is unavailable when either arm lacks the same actor at turn 7 or 11.

### Turn-7 household cohort

The roster freezes all living non-company, non-government, non-trader residents in both scenario regions at turn 7. Effects compare matched baseline members; turn-8–11 flow metrics are per observed person-turn. Employer linkage is a status proxy, and calorie intake is compared with each person's recorded calorie need. This is the complete resident cohort for this small scenario, not a general population welfare index.

| Seed | Baseline members C/T | Matched | Alive T11 (pp) | Need met (pp) | Food shortfall (pp) | Employer-linked (pp) | Calories (kcal/person-turn) | Cash change/person | Debt change/person | Wages/person-turn | Sales/person-turn | Purchases/person-turn | Input cost/person-turn |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 812 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | -0.17 (34/34) | +0.00 (34/34) | +0.00 (136/136) | -0.14 (136/136) | -0.08 (136/136) | +0.00 (136/136) |
| 813 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | -7.35 (136/136) | -0.27 (34/34) | +0.00 (34/34) | +0.00 (136/136) | -0.26 (136/136) | -0.14 (136/136) | +0.00 (136/136) |
| 814 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +3.68 (136/136) | -0.43 (34/34) | +0.00 (34/34) | +0.00 (136/136) | -0.37 (136/136) | -0.23 (136/136) | +0.00 (136/136) |
| 815 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | -14.71 (136/136) | +0.03 (34/34) | +0.00 (34/34) | +0.00 (136/136) | -0.08 (136/136) | -0.07 (136/136) | +0.00 (136/136) |
| 816 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | -14.71 (136/136) | -0.15 (34/34) | +0.00 (34/34) | +0.00 (136/136) | -0.14 (136/136) | -0.09 (136/136) | +0.00 (136/136) |

Percentage entries are treatment-minus-control percentage point effects. Parentheses show matched members or observed person-turns over expected coverage; missing or migrated-out members are not silently imputed as zero.

### Physical holdings census

The census sums every agent's ordinary inventory and the trader export, foreign, parked and legacy-pipeline pools; it also counts distinct government/charity food stores and pending/in-transit route cargo. It is a complete point-in-time census of these enumerated supply-rivalry stores, not a goods-flow conservation proof. The JSON sidecar retains all goods and turns; this table shows food, cotton and cloth at T7, T11 and T20.

| Seed | T7 agents / routes / public stores | Negative stock observations C/T | Good | Holder / pool | T7 C/T | T11 C/T | T7-to-T11 change effect | T20 C/T |
|---:|---|---:|---|---|---:|---:|---:|---:|
| 812 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/4 | cloth | household / inventory | 3.0/3.0 | 8.0/8.0 | 0.00 | 2.0/2.0 |
|  |  |  | cotton | household / inventory | 12.0/12.0 | 1.0/0.0 | -1.00 | 0.0/0.0 |
|  |  |  | food | household / inventory | 210.0/210.0 | 241.0/242.0 | 1.00 | 349.0/367.0 |
|  |  |  | cloth | producer / inventory | 19.0/19.0 | 8.0/8.0 | 0.00 | 0.0/0.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 10.0/8.0 | -2.00 | 0.0/0.0 |
|  |  |  | food | producer / inventory | 35.0/35.0 | 40.0/40.0 | 0.00 | 36.0/33.0 |
|  |  |  | food | public / charity_food | 0.0/0.0 | 0.0/0.0 | 0.00 | 0.0/-0.5 |
|  |  |  | food | public / government_food | 102.0/102.0 | 121.0/121.0 | 0.00 | 110.0/108.5 |
|  |  |  | cotton | trader / foreign_inventory | 4.0/4.0 | 0.0/0.0 | 0.00 | 0.0/0.0 |
|  |  |  | food | trader / inventory | 8.0/8.0 | 1.0/0.0 | -1.00 | 1.0/0.0 |
| 813 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | household / inventory | 3.0/3.0 | 7.0/7.0 | 0.00 | 6.0/3.0 |
|  |  |  | cotton | household / inventory | 0.0/0.0 | 3.0/1.0 | -2.00 | 2.0/0.0 |
|  |  |  | food | household / inventory | 187.0/187.0 | 198.0/202.0 | 4.00 | 355.0/251.0 |
|  |  |  | cotton | in_transit / route_in_transit | 18.0/18.0 | 0.0/0.0 | 0.00 | 0.0/0.0 |
|  |  |  | cloth | producer / inventory | 18.0/18.0 | 21.0/13.0 | -8.00 | 0.0/0.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 2.0/3.0 | 1.00 | 6.0/1.0 |
|  |  |  | food | producer / inventory | 42.0/42.0 | 43.0/44.0 | 1.00 | 28.0/48.0 |
|  |  |  | food | public / government_food | 101.0/101.0 | 91.0/91.0 | 0.00 | 48.0/55.0 |
|  |  |  | food | trader / inventory | 3.0/3.0 | 3.0/2.0 | -1.00 | 0.0/0.0 |
| 814 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | government_agent / inventory | 0.0/0.0 | 0.0/0.0 | 0.00 | 4.0/3.0 |
|  |  |  | cloth | household / inventory | 3.0/3.0 | 6.0/6.0 | 0.00 | 6.0/0.0 |
|  |  |  | cotton | household / inventory | 10.0/10.0 | 4.0/3.0 | -1.00 | 2.0/1.0 |
|  |  |  | food | household / inventory | 266.0/266.0 | 271.0/271.0 | 0.00 | 475.0/467.0 |
|  |  |  | cloth | producer / inventory | 18.0/18.0 | 4.0/0.0 | -4.00 | 0.0/0.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 5.0/5.0 | 0.00 | 7.0/8.0 |
|  |  |  | food | producer / inventory | 42.0/42.0 | 46.0/46.0 | 0.00 | 36.0/38.0 |
|  |  |  | food | public / government_food | 73.0/73.0 | 78.0/79.0 | 1.00 | 22.0/21.0 |
|  |  |  | food | trader / inventory | 2.0/2.0 | 3.0/4.0 | 1.00 | 0.0/0.0 |
| 815 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | household / inventory | 3.0/3.0 | 7.0/7.0 | 0.00 | 5.0/5.0 |
|  |  |  | cotton | household / inventory | 14.0/14.0 | 0.0/0.0 | 0.00 | 3.0/3.0 |
|  |  |  | food | household / inventory | 214.0/214.0 | 263.0/262.0 | -1.00 | 333.0/378.0 |
|  |  |  | cloth | producer / inventory | 18.0/18.0 | 2.0/2.0 | 0.00 | 8.0/1.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 14.0/12.0 | -2.00 | 5.0/1.0 |
|  |  |  | food | producer / inventory | 34.0/34.0 | 50.0/56.0 | 6.00 | 24.0/28.0 |
|  |  |  | food | public / government_food | 110.0/110.0 | 119.0/119.0 | 0.00 | 103.0/108.0 |
|  |  |  | cotton | trader / foreign_inventory | 4.0/4.0 | 0.0/0.0 | 0.00 | 0.0/0.0 |
|  |  |  | food | trader / inventory | 4.0/4.0 | 3.0/2.0 | -1.00 | 1.0/1.0 |
| 816 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | household / inventory | 3.0/3.0 | 4.0/4.0 | 0.00 | 2.0/2.0 |
|  |  |  | cotton | household / inventory | 12.0/12.0 | 1.0/0.0 | -1.00 | 0.0/3.0 |
|  |  |  | food | household / inventory | 256.0/256.0 | 227.0/228.0 | 1.00 | 490.0/610.0 |
|  |  |  | cloth | producer / inventory | 18.0/18.0 | 3.0/3.0 | 0.00 | 0.0/0.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 10.0/8.0 | -2.00 | 7.0/0.0 |
|  |  |  | food | producer / inventory | 36.0/36.0 | 45.0/48.0 | 3.00 | 32.0/31.0 |
|  |  |  | food | public / government_food | 99.0/99.0 | 112.0/112.0 | 0.00 | 69.0/96.0 |
|  |  |  | food | trader / inventory | 3.0/3.0 | 4.0/4.0 | 0.00 | 2.0/0.0 |

Negative-stock counts are negative category/pool/good holdings observed over all 20 turns in each arm. They are preserved as findings for follow-up, not clamped during census or report aggregation.

### Post-shock return to control bands

Descriptive recovery rule: after the shock is removed, a measure is within band when quantity differences are no more than max(1 unit, 5% of the control) or paid-price differences are within 5% of control for three consecutive observed turns. Missing observations break a candidate run. Post-shock RNG streams can diverge, so these are path summaries rather than draw-aligned causal recovery estimates.

| Measure | 812 | 813 | 814 | 815 | 816 | Rule |
|---|---:|---:|---:|---:|---:|---|
| Cotton production | within_tolerance (T12; 9/9 observed) | not_recovered_by_window_end (—; 9/9 observed) | within_tolerance (T12; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | not_recovered_by_window_end (—; 9/9 observed) | 3 consecutive; quantity ±max(1, 5%), price ±5% |
| Cotton offered supply | within_tolerance (T14; 9/9 observed) | not_recovered_by_window_end (—; 9/9 observed) | within_tolerance (T12; 9/9 observed) | within_tolerance (T12; 9/9 observed) | not_recovered_by_window_end (—; 9/9 observed) | 3 consecutive; quantity ±max(1, 5%), price ±5% |
| Cotton units sold | not_established_missing_observations (—; 1/9 observed) | not_recovered_by_window_end (—; 9/9 observed) | within_tolerance (T12; 9/9 observed) | within_tolerance (T12; 9/9 observed) | not_recovered_by_window_end (—; 9/9 observed) | 3 consecutive; quantity ±max(1, 5%), price ±5% |
| Cotton paid VWAP | not_established_missing_observations (—; 1/9 observed) | within_tolerance (T12; 9/9 observed) | within_tolerance (T12; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | 3 consecutive; quantity ±max(1, 5%), price ±5% |

A result of no detectable shock-window response means the metric never moved outside its tolerance in observed turns; it is not evidence of rapid recovery.

### Cotton route events

| Seed | Period | Control departures | Treatment departures | Departure delta | Control arrivals | Treatment arrivals | Arrival delta |
|---:|---|---:|---:|---:|---:|---:|---:|
| 812 | Shock window | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 812 | Full 20 turns | 4.0 | 4.0 | 0.0 | 4.0 | 4.0 | 0.0 |
| 813 | Shock window | 2.0 | 0.0 | -2.0 | 20.0 | 18.0 | -2.0 |
| 813 | Full 20 turns | 20.0 | 18.0 | -2.0 | 20.0 | 18.0 | -2.0 |
| 814 | Shock window | 14.0 | 12.0 | -2.0 | 14.0 | 12.0 | -2.0 |
| 814 | Full 20 turns | 14.0 | 12.0 | -2.0 | 14.0 | 12.0 | -2.0 |
| 815 | Shock window | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 815 | Full 20 turns | 4.0 | 4.0 | 0.0 | 4.0 | 4.0 | 0.0 |
| 816 | Shock window | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 816 | Full 20 turns | 2.0 | 2.0 | 0.0 | 2.0 | 2.0 | 0.0 |

## Temporary Meridian Mill cotton-input target increase

Turn-7 complete-state match: 5/5; scenario hook passes: 5/5; market gates pass in both arms: 5/5.

Shock-window paired effects in Cotton Fields and connected markets. Flow quantities sum observed turn deltas; producer inventory is the point-in-time turn-11 difference; price rows average per-turn percent changes from that seed's control.

| Measure | 812 | 813 | 814 | 815 | 816 | Mean | Range | Seeds observed | Turn coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cotton production | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cotton offered supply | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cotton units sold | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:3/4, 813:4/4, 814:4/4, 815:3/4, 816:3/4 |
| Cotton submitted bids | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cotton producer inventory at T11 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:1/1, 813:1/1, 814:1/1, 815:1/1, 816:1/1 |
| Cotton reference-price change (%) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cotton paid-VWAP change (%) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:3/4, 813:4/4, 814:4/4, 815:3/4, 816:3/4 |
| Cloth production | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Cloth units sold | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:1/4, 813:1/4, 814:1/4, 815:1/4, 816:1/4 |
| Cloth paid-VWAP change (%) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:1/4, 813:1/4, 814:1/4, 815:1/4, 816:1/4 |
| Rival Port cotton units sold | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:3/4, 813:3/4, 814:2/4, 815:3/4, 816:1/4 |
| Rival Port cotton paid-VWAP change (%) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:2/4, 813:3/4, 814:2/4, 815:2/4, 816:1/4 |
| Rival Port cloth units sold | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:4/4, 813:4/4, 814:4/4, 815:4/4, 816:4/4 |
| Rival Port cloth paid-VWAP change (%) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 to 0.00 | 5/5 | 812:2/4, 813:2/4, 814:1/4, 815:2/4, 816:2/4 |

Paid prices are only compared when both arms recorded a positive control transaction price. Missing clearings are excluded and shown in turn coverage, never treated as zero.

### Meridian Mill cotton orders

Control and treatment order totals use observed order rows; the treatment's unshocked target is recorded alongside the override so desired demand is separated from submitted bids.

| Seed | Control rows | Treatment rows | Control target | Treated target | Treatment unshocked target | Target uplift | Control bids | Treatment bids | Override rows |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 812 | 3 | 3 | 7.00 | 11.00 | 7.00 | 4.00 | 26.00 | 26.00 | 3 |
| 813 | 3 | 3 | 6.00 | 9.00 | 6.00 | 3.00 | 25.00 | 25.00 | 3 |
| 814 | 3 | 3 | 6.00 | 9.00 | 6.00 | 3.00 | 25.00 | 25.00 | 3 |
| 815 | 3 | 3 | 9.00 | 15.00 | 9.00 | 6.00 | 20.00 | 20.00 | 3 |
| 816 | 3 | 3 | 7.00 | 11.00 | 7.00 | 4.00 | 26.00 | 26.00 | 3 |

A missing mill order row means no order event was observed for that turn; the table reports row counts rather than imputing a zero target.

### Stable named actors

Effects on stocks are treatment-minus-control differences in the actor's turn-7-to-11 change. Flow effects sum paired observed turns 8–11. These are actor-level accounting indicators, not a complete welfare index.

| Seed | Actor | Cash change | Food stock change | Cotton stock change | Cloth stock change | Food intake | Output | Sales cash | Input costs | Wages | Debt / bank debt change | Flow coverage |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 812 | Amina, secure grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 812 | Binta, cash-poor grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 812 | Meridian Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 812 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 813 | Amina, secure grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 813 | Binta, cash-poor grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 813 | Meridian Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 813 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 814 | Amina, secure grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 814 | Binta, cash-poor grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 814 | Meridian Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 814 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 815 | Amina, secure grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 815 | Binta, cash-poor grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 815 | Meridian Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 815 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 816 | Amina, secure grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 816 | Binta, cash-poor grower | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 816 | Meridian Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |
| 816 | Vesper Mill | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 / 0.00 | 4, 4, 4, 4, 4 |

Flow coverage columns list observed turns, in order for food intake, output, sales cash, input costs and wages; each denominator is four. These are observed transactions, not a complete profit calculation. A stock value is unavailable when either arm lacks the same actor at turn 7 or 11.

### Turn-7 household cohort

The roster freezes all living non-company, non-government, non-trader residents in both scenario regions at turn 7. Effects compare matched baseline members; turn-8–11 flow metrics are per observed person-turn. Employer linkage is a status proxy, and calorie intake is compared with each person's recorded calorie need. This is the complete resident cohort for this small scenario, not a general population welfare index.

| Seed | Baseline members C/T | Matched | Alive T11 (pp) | Need met (pp) | Food shortfall (pp) | Employer-linked (pp) | Calories (kcal/person-turn) | Cash change/person | Debt change/person | Wages/person-turn | Sales/person-turn | Purchases/person-turn | Input cost/person-turn |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 812 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (34/34) | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) |
| 813 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (34/34) | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) |
| 814 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (34/34) | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) |
| 815 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (34/34) | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) |
| 816 | 34/34 | 34 | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (34/34) | +0.00 (34/34) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) | +0.00 (136/136) |

Percentage entries are treatment-minus-control percentage point effects. Parentheses show matched members or observed person-turns over expected coverage; missing or migrated-out members are not silently imputed as zero.

### Physical holdings census

The census sums every agent's ordinary inventory and the trader export, foreign, parked and legacy-pipeline pools; it also counts distinct government/charity food stores and pending/in-transit route cargo. It is a complete point-in-time census of these enumerated supply-rivalry stores, not a goods-flow conservation proof. The JSON sidecar retains all goods and turns; this table shows food, cotton and cloth at T7, T11 and T20.

| Seed | T7 agents / routes / public stores | Negative stock observations C/T | Good | Holder / pool | T7 C/T | T11 C/T | T7-to-T11 change effect | T20 C/T |
|---:|---|---:|---|---|---:|---:|---:|---:|
| 812 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | household / inventory | 3.0/3.0 | 8.0/8.0 | 0.00 | 2.0/2.0 |
|  |  |  | cotton | household / inventory | 12.0/12.0 | 1.0/1.0 | 0.00 | 0.0/0.0 |
|  |  |  | food | household / inventory | 210.0/210.0 | 241.0/241.0 | 0.00 | 349.0/349.0 |
|  |  |  | cloth | producer / inventory | 19.0/19.0 | 8.0/8.0 | 0.00 | 0.0/0.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 10.0/10.0 | 0.00 | 0.0/0.0 |
|  |  |  | food | producer / inventory | 35.0/35.0 | 40.0/40.0 | 0.00 | 36.0/36.0 |
|  |  |  | food | public / government_food | 102.0/102.0 | 121.0/121.0 | 0.00 | 110.0/110.0 |
|  |  |  | cotton | trader / foreign_inventory | 4.0/4.0 | 0.0/0.0 | 0.00 | 0.0/0.0 |
|  |  |  | food | trader / inventory | 8.0/8.0 | 1.0/1.0 | 0.00 | 1.0/1.0 |
| 813 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | household / inventory | 3.0/3.0 | 7.0/7.0 | 0.00 | 6.0/6.0 |
|  |  |  | cotton | household / inventory | 0.0/0.0 | 3.0/3.0 | 0.00 | 2.0/2.0 |
|  |  |  | food | household / inventory | 187.0/187.0 | 198.0/198.0 | 0.00 | 355.0/355.0 |
|  |  |  | cotton | in_transit / route_in_transit | 18.0/18.0 | 0.0/0.0 | 0.00 | 0.0/0.0 |
|  |  |  | cloth | producer / inventory | 18.0/18.0 | 21.0/21.0 | 0.00 | 0.0/0.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 2.0/2.0 | 0.00 | 6.0/6.0 |
|  |  |  | food | producer / inventory | 42.0/42.0 | 43.0/43.0 | 0.00 | 28.0/28.0 |
|  |  |  | food | public / government_food | 101.0/101.0 | 91.0/91.0 | 0.00 | 48.0/48.0 |
|  |  |  | food | trader / inventory | 3.0/3.0 | 3.0/3.0 | 0.00 | 0.0/0.0 |
| 814 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | government_agent / inventory | 0.0/0.0 | 0.0/0.0 | 0.00 | 4.0/4.0 |
|  |  |  | cloth | household / inventory | 3.0/3.0 | 6.0/6.0 | 0.00 | 6.0/6.0 |
|  |  |  | cotton | household / inventory | 10.0/10.0 | 4.0/4.0 | 0.00 | 2.0/2.0 |
|  |  |  | food | household / inventory | 266.0/266.0 | 271.0/271.0 | 0.00 | 475.0/475.0 |
|  |  |  | cloth | producer / inventory | 18.0/18.0 | 4.0/4.0 | 0.00 | 0.0/0.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 5.0/5.0 | 0.00 | 7.0/7.0 |
|  |  |  | food | producer / inventory | 42.0/42.0 | 46.0/46.0 | 0.00 | 36.0/36.0 |
|  |  |  | food | public / government_food | 73.0/73.0 | 78.0/78.0 | 0.00 | 22.0/22.0 |
|  |  |  | food | trader / inventory | 2.0/2.0 | 3.0/3.0 | 0.00 | 0.0/0.0 |
| 815 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | household / inventory | 3.0/3.0 | 7.0/7.0 | 0.00 | 5.0/5.0 |
|  |  |  | cotton | household / inventory | 14.0/14.0 | 0.0/0.0 | 0.00 | 3.0/3.0 |
|  |  |  | food | household / inventory | 214.0/214.0 | 263.0/263.0 | 0.00 | 333.0/333.0 |
|  |  |  | cloth | producer / inventory | 18.0/18.0 | 2.0/2.0 | 0.00 | 8.0/8.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 14.0/14.0 | 0.00 | 5.0/5.0 |
|  |  |  | food | producer / inventory | 34.0/34.0 | 50.0/50.0 | 0.00 | 24.0/24.0 |
|  |  |  | food | public / government_food | 110.0/110.0 | 119.0/119.0 | 0.00 | 103.0/103.0 |
|  |  |  | cotton | trader / foreign_inventory | 4.0/4.0 | 0.0/0.0 | 0.00 | 0.0/0.0 |
|  |  |  | food | trader / inventory | 4.0/4.0 | 3.0/3.0 | 0.00 | 1.0/1.0 |
| 816 | 44/44 agents; 2/2 routes; 2+2 public stores | 0/0 | cloth | household / inventory | 3.0/3.0 | 4.0/4.0 | 0.00 | 2.0/2.0 |
|  |  |  | cotton | household / inventory | 12.0/12.0 | 1.0/1.0 | 0.00 | 0.0/0.0 |
|  |  |  | food | household / inventory | 256.0/256.0 | 227.0/227.0 | 0.00 | 490.0/490.0 |
|  |  |  | cloth | producer / inventory | 18.0/18.0 | 3.0/3.0 | 0.00 | 0.0/0.0 |
|  |  |  | cotton | producer / inventory | 0.0/0.0 | 10.0/10.0 | 0.00 | 7.0/7.0 |
|  |  |  | food | producer / inventory | 36.0/36.0 | 45.0/45.0 | 0.00 | 32.0/32.0 |
|  |  |  | food | public / government_food | 99.0/99.0 | 112.0/112.0 | 0.00 | 69.0/69.0 |
|  |  |  | food | trader / inventory | 3.0/3.0 | 4.0/4.0 | 0.00 | 2.0/2.0 |

Negative-stock counts are negative category/pool/good holdings observed over all 20 turns in each arm. They are preserved as findings for follow-up, not clamped during census or report aggregation.

### Post-shock return to control bands

Descriptive recovery rule: after the shock is removed, a measure is within band when quantity differences are no more than max(1 unit, 5% of the control) or paid-price differences are within 5% of control for three consecutive observed turns. Missing observations break a candidate run. Post-shock RNG streams can diverge, so these are path summaries rather than draw-aligned causal recovery estimates.

| Measure | 812 | 813 | 814 | 815 | 816 | Rule |
|---|---:|---:|---:|---:|---:|---|
| Cotton submitted bids | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | 3 consecutive; quantity ±max(1, 5%), price ±5% |
| Cotton units sold | no_detectable_shock_response (—; 2/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | 3 consecutive; quantity ±max(1, 5%), price ±5% |
| Cotton paid VWAP | no_detectable_shock_response (—; 2/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | no_detectable_shock_response (—; 9/9 observed) | 3 consecutive; quantity ±max(1, 5%), price ±5% |

A result of no detectable shock-window response means the metric never moved outside its tolerance in observed turns; it is not evidence of rapid recovery.

### Cotton route events

| Seed | Period | Control departures | Treatment departures | Departure delta | Control arrivals | Treatment arrivals | Arrival delta |
|---:|---|---:|---:|---:|---:|---:|---:|
| 812 | Shock window | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 812 | Full 20 turns | 4.0 | 4.0 | 0.0 | 4.0 | 4.0 | 0.0 |
| 813 | Shock window | 2.0 | 2.0 | 0.0 | 20.0 | 20.0 | 0.0 |
| 813 | Full 20 turns | 20.0 | 20.0 | 0.0 | 20.0 | 20.0 | 0.0 |
| 814 | Shock window | 14.0 | 14.0 | 0.0 | 14.0 | 14.0 | 0.0 |
| 814 | Full 20 turns | 14.0 | 14.0 | 0.0 | 14.0 | 14.0 | 0.0 |
| 815 | Shock window | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 815 | Full 20 turns | 4.0 | 4.0 | 0.0 | 4.0 | 4.0 | 0.0 |
| 816 | Shock window | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 816 | Full 20 turns | 2.0 | 2.0 | 0.0 | 2.0 | 2.0 | 0.0 |

## Audit scope and interpretation

All seed pairs share complete canonical state at turn 7, and all treatment hooks pass through the shock and restore before turn 12. Both arms pass the market settlement-bound checks in every seed pair. The table above reports the deep-accounting and structural checks for each retained arm trace. See `economic_shock_supply_rivalry_seed812.md` and the treasury follow-up for residuals and limitations.

The five-seed sample describes local mechanism response in this fixed scenario. It does not establish general supply-chain resilience, population welfare, goods-stock conservation, causal recovery, or historical realism. Complete causal coverage remains false. No route event in a shock window means that seed did not exercise a new shipping response; it does not establish that trade is generally unresponsive. Stable named-actor snapshots improve cohort comparability but omit households outside the scenario instrumentation.

Reproduce each clean-source pair with `economic_shock_experiment.py --scenario supply_rivalry`, then summarize the saved JSON without re-decoding traces:

```sh
venv/bin/python economic_shock_scenario_multiseed.py --root tmp/economic-shocks/supply-rivalry --seeds 812 813 814 815 816
```
