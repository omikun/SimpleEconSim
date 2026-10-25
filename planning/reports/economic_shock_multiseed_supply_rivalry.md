# 5-seed supply-rivalry shock screen

Matched 20-turn runs at seeds 812, 813, 814, 815, 816. The two interventions are analyzed separately; turns 8–11 are the shock window and later differences are not draw-aligned after RNG paths diverge. Per-seed ranges are descriptive, not confidence intervals or empirical calibration.

Simulation provenance by seed: 812: `569b723ca954c20869f89d4d70097994446a054a` (4 arms; dirty 0); 813: `569b723ca954c20869f89d4d70097994446a054a` (4 arms; dirty 0); 814: `569b723ca954c20869f89d4d70097994446a054a` (4 arms; dirty 0); 815: `569b723ca954c20869f89d4d70097994446a054a` (4 arms; dirty 0); 816: `569b723ca954c20869f89d4d70097994446a054a` (4 arms; dirty 0).

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
