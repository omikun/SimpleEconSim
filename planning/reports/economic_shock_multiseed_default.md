# 5-seed default-game shock screen

Paired 20-turn screens at seeds 4242, 4243, 4244, 4245, 4246; turns 8–11 are the shock window. Per-seed differences are matched treatment minus control; displayed ranges are descriptive, not confidence intervals or empirical calibration.

Each seed uses an independent world initialization. Within each seed, the control and treatment must match at turn 7. Later RNG streams can diverge after the intervention, so recovery-path differences are not draw-aligned.

Simulation source provenance by seed: 4242 `b4da81d64dd7a72f73f7b8fd9e4b9f591a5b4149` (dirty arms: 0/4); 4243 `18c88875446fcc541f2ba4461e8948aef2c1376a` (dirty arms: 0/2), `21d3c6bc39567eb9b7834d0d62cc3b859fa910a4` (dirty arms: 0/2); 4244 `21d3c6bc39567eb9b7834d0d62cc3b859fa910a4` (dirty arms: 0/4); 4245 `21d3c6bc39567eb9b7834d0d62cc3b859fa910a4` (dirty arms: 0/4); 4246 `21d3c6bc39567eb9b7834d0d62cc3b859fa910a4` (dirty arms: 0/4).

## Temporary local wood supply reduction

Selected active target tiles by seed: 4242:c50 (CNY), 4243:c59 (JPY), 4244:c76 (JPY), 4245:c56 (USD), 4246:c78 (USD).
Turn-7 states match: 5/5; market mechanical gates pass: 5/5 seed pairs in both arms.

| Measure | 4242 | 4243 | 4244 | 4245 | 4246 | Mean | Median | Range | Seeds observed | Seed coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Wood production | -39.000 | -54.000 | -54.000 | -9.000 | -23.000 | -35.800 | -39.000 | -54.000 to -9.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:4/4, 4246:4/4 |
| Wood offered supply | -60.000 | -87.000 | -82.000 | -10.000 | -23.000 | -52.400 | -60.000 | -87.000 to -10.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:4/4, 4246:4/4 |
| Wood units sold | -60.000 | -87.000 | -82.000 | -10.000 | -23.000 | -52.400 | -60.000 | -87.000 to -10.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:3/4, 4246:4/4 |
| Wood submitted bids | 73.000 | 60.000 | 40.000 | 10.000 | 10.000 | 38.600 | 40.000 | 10.000 to 73.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:4/4, 4246:4/4 |
| Wood paid VWAP change (%) | 0.104 | 0.246 | 0.325 | 1.702 | 4.362 | 1.348 | 0.325 | 0.104 to 4.362 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:3/4, 4246:4/4 |
| Furniture units sold | 0.000 | 0.000 | -1.000 | 0.000 | 0.000 | -0.200 | 0.000 | -1.000 to 0.000 | 5 | 4242:4/4, 4243:4/4, 4244:2/4, 4245:3/4, 4246:3/4 |
| Furniture paid VWAP change (%) | 0.000 | 0.207 | -0.276 | 0.000 | 0.000 | -0.014 | 0.000 | -0.276 to 0.207 | 5 | 4242:4/4, 4243:4/4, 4244:2/4, 4245:3/4, 4246:3/4 |
| Food shortfall units | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 to 0.000 | 5 | 4242:4/4, 4243:4/4, 4244:2/4, 4245:4/4, 4246:4/4 |
| Wood consumed | -16.000 | -34.000 | -34.000 | -6.000 | -13.000 | -20.600 | -16.000 | -34.000 to -6.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:4/4, 4246:4/4 |

A seed-level sum is cumulative over observed shock-window turns for quantities and consumption; price rows show mean per-turn percent changes from that seed's control so currencies remain comparable. Coverage cells prevent a missing record from being silently counted as zero.

## Temporary local furniture inventory-target increase

Selected active target tiles by seed: 4242:c50 (CNY), 4243:c74 (CNY), 4244:c74 (USD), 4245:c78 (JPY), 4246:c71 (JPY).
Turn-7 states match: 5/5; market mechanical gates pass: 5/5 seed pairs in both arms.

| Measure | 4242 | 4243 | 4244 | 4245 | 4246 | Mean | Median | Range | Seeds observed | Seed coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Furniture submitted bids | 8.000 | 7.000 | 12.000 | 9.000 | 7.000 | 8.600 | 8.000 | 7.000 to 12.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:4/4, 4246:4/4 |
| Furniture offered supply | 0.000 | 2.000 | 0.000 | 0.000 | 1.000 | 0.600 | 0.000 | 0.000 to 2.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:4/4, 4246:4/4 |
| Furniture units sold | 0.000 | 2.000 | 0.000 | 0.000 | 0.000 | 0.400 | 0.000 | 0.000 to 2.000 | 5 | 4242:4/4, 4243:4/4, 4244:3/4, 4245:3/4, 4246:3/4 |
| Furniture production | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.200 | 0.000 | 0.000 to 1.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:4/4, 4246:4/4 |
| Furniture paid VWAP change (%) | -0.034 | -0.461 | 0.000 | 0.000 | 0.000 | -0.099 | 0.000 | -0.461 to 0.000 | 5 | 4242:4/4, 4243:4/4, 4244:3/4, 4245:3/4, 4246:3/4 |
| Food shortfall units | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 to 0.000 | 5 | 4242:4/4, 4243:4/4, 4244:4/4, 4245:4/4, 4246:4/4 |
| Furniture consumed | 5.000 | -1.000 | -2.000 | -3.000 | 0.000 | -0.200 | -1.000 | -3.000 to 5.000 | 5 | 4242:3/4, 4243:3/4, 4244:2/4, 4245:2/4, 4246:4/4 |

A seed-level sum is cumulative over observed shock-window turns for quantities and consumption; price rows show mean per-turn percent changes from that seed's control so currencies remain comparable. Coverage cells prevent a missing record from being silently counted as zero.

## Limits

Five seeds are a diagnostic sample, not a precise uncertainty estimate. Deep structural/formula and treasury audits were run on the seed-4242 traces; the other seed pairs carry the market mechanical gates only. Treasury residual attribution, full goods-stock conservation, stable household cohorts, a supply-rivalry cross-scenario sample, and primary-source calibration remain open in the analysis plan.

Reproduce the paired runs with `economic_shock_experiment.py` for each seed, then summarize their saved JSON without re-decoding traces:

```sh
venv/bin/python economic_shock_multiseed.py --root tmp/economic-shocks --seeds 4242 4243 4244 4245 4246
```
