# 5-seed default-game shock screen

Paired 20-turn screens at seeds 4242, 4243, 4244, 4245, 4246; turns 8–11 are the shock window. Per-seed differences are matched treatment minus control; displayed ranges are descriptive, not confidence intervals or empirical calibration.

Each seed uses an independent world initialization. Within each seed, the control and treatment must match at turn 7. Later RNG streams can diverge after the intervention, so recovery-path differences are not draw-aligned.

Simulation source provenance by seed: 4242 `cc4275f9149135c01953444d2fa836cbdcb3627a` (dirty arms: 4/4); 4243 `cc4275f9149135c01953444d2fa836cbdcb3627a` (dirty arms: 4/4); 4244 `cc4275f9149135c01953444d2fa836cbdcb3627a` (dirty arms: 4/4); 4245 `cc4275f9149135c01953444d2fa836cbdcb3627a` (dirty arms: 4/4); 4246 `cc4275f9149135c01953444d2fa836cbdcb3627a` (dirty arms: 4/4).

The recorded simulation commit is consistent across arms, but the tracked worktree was dirty for these runs because the prior preliminary default-summary Markdown/JSON outputs were modified; the simulation source files themselves matched the recorded commit. Treat this as commit-pinned rather than pristine-tree provenance.

## Deep trace and ledger audits

Audited 20/20 arms. Bounded structural/supported-formula checks pass in 20/20 arms with 0 reported issues; public-account closes verify 1200/1200; treasury flows are attributed in 1064/1200 turns, with 4/20 arms fully attributed. Complete causal coverage is present in 0/20 arms.

| Seed | Audited arms | Formula pass | Issues | Account closes | Treasury attributed turns | Fully attributed arms |
|---:|---:|---:|---:|---:|---:|---:|
| 4242 | 4/4 | 4/4 | 0 | 240/240 | 240/240 | 4/4 |
| 4243 | 4/4 | 4/4 | 0 | 240/240 | 206/240 | 0/4 |
| 4244 | 4/4 | 4/4 | 0 | 240/240 | 220/240 | 0/4 |
| 4245 | 4/4 | 4/4 | 0 | 240/240 | 179/240 | 0/4 |
| 4246 | 4/4 | 4/4 | 0 | 240/240 | 219/240 | 0/4 |

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

## Fixed default-game resident cohort

Each default-game arm freezes the same eligible resident IDs after turn 7 and records compact aggregate observations through turn 20. The table covers turns 8–11. Need-met rates use present, living roster members with positive measured calorie need; missing people are not assigned zero intake. Cash and debt changes are each person's change from turn 7 divided by their own positive baseline cash, and only residents whose recorded home currency still matches are covered. Wage measures count residents with a recorded cash or scrip wage receipt per living person-turn; they are incidence rates, not pooled amounts. Raw cash amounts are not pooled across local currencies. Differences are treatment minus control; rate and balance-ratio differences are percentage points.

| Experiment | Seed | Baseline N C/T | Roster matched | T11 present C/T | T11 alive C/T | Need met C/T (Δ pp) | kcal/need-person-turn C/T (Δ) | Employer-linked C/T (Δ pp) | Median cash Δ/T7 cash C/T (Δ pp; coverage) | Median debt Δ/T7 cash C/T (Δ pp; coverage) | Cash-wage recipients C/T (Δ pp) | Scrip-wage recipients C/T (Δ pp) | Need/living person-turn coverage C/T |
|---|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Temporary local wood supply reduction | 4242 | 1356/1356 | yes | 100.0%/100.0% | 100.0%/100.0% | 94.4%/94.5% (+0.1 pp) | 2225.018/2226.770 (+1.75) | 2.2%/2.3% (+0.0 pp) | -8.05% [1349/1356]/-7.97% [1349/1356] (+0.08 pp) | +0.00% [1349/1356]/+0.00% [1349/1356] (+0.00 pp) | 1.6%/1.7% (+0.0 pp) | 0.0%/0.0% (+0.0 pp) | need 5424/5424, live 5424/5424; need 5424/5424, live 5424/5424 |
| Temporary local wood supply reduction | 4243 | 1314/1314 | yes | 99.8%/99.8% | 99.8%/99.8% | 81.4%/81.4% (-0.0 pp) | 1949.353/1951.152 (+1.80) | 6.6%/6.7% (+0.1 pp) | -16.65% [1262/1314]/-13.93% [1262/1314] (+2.71 pp) | +0.00% [1262/1314]/+0.00% [1262/1314] (+0.00 pp) | 3.6%/3.7% (+0.1 pp) | 0.0%/0.0% (+0.0 pp) | need 5252/5256, live 5252/5256; need 5251/5256, live 5251/5256 |
| Temporary local wood supply reduction | 4244 | 1497/1497 | yes | 100.0%/100.0% | 100.0%/100.0% | 94.1%/94.1% (+0.0 pp) | 2248.914/2249.582 (+0.67) | 1.7%/1.7% (+0.0 pp) | -7.31% [1491/1497]/-7.07% [1491/1497] (+0.24 pp) | +0.00% [1491/1497]/+0.00% [1491/1497] (+0.00 pp) | 0.7%/0.7% (+0.0 pp) | 0.0%/0.0% (+0.0 pp) | need 5988/5988, live 5988/5988; need 5988/5988, live 5988/5988 |
| Temporary local wood supply reduction | 4245 | 1315/1315 | yes | 99.7%/99.7% | 99.7%/99.7% | 80.0%/80.0% (+0.0 pp) | 1922.235/1922.235 (+0.00) | 2.9%/2.9% (+0.0 pp) | -14.09% [1286/1315]/-14.09% [1286/1315] (+0.00 pp) | +0.00% [1286/1315]/+0.00% [1286/1315] (+0.00 pp) | 1.1%/1.1% (+0.0 pp) | 0.0%/0.0% (+0.0 pp) | need 5253/5260, live 5253/5260; need 5253/5260, live 5253/5260 |
| Temporary local wood supply reduction | 4246 | 1495/1495 | yes | 99.9%/99.9% | 99.9%/99.9% | 89.2%/89.2% (+0.0 pp) | 2140.408/2140.492 (+0.08) | 3.3%/3.3% (+0.0 pp) | -9.34% [1463/1495]/-9.31% [1463/1495] (+0.03 pp) | +0.00% [1463/1495]/+0.00% [1463/1495] (+0.00 pp) | 2.2%/2.2% (+0.0 pp) | 0.0%/0.0% (+0.0 pp) | need 5979/5980, live 5979/5980; need 5979/5980, live 5979/5980 |
| Temporary local furniture inventory-target increase | 4242 | 1356/1356 | yes | 100.0%/100.0% | 100.0%/100.0% | 94.4%/94.3% (-0.1 pp) | 2225.018/2225.387 (+0.37) | 2.2%/2.1% (-0.2 pp) | -8.05% [1349/1356]/-7.74% [1349/1356] (+0.31 pp) | +0.00% [1349/1356]/+0.00% [1349/1356] (+0.00 pp) | 1.6%/1.5% (-0.1 pp) | 0.0%/0.0% (+0.0 pp) | need 5424/5424, live 5424/5424; need 5424/5424, live 5424/5424 |
| Temporary local furniture inventory-target increase | 4243 | 1314/1314 | yes | 99.8%/99.8% | 99.8%/99.8% | 81.4%/81.5% (+0.1 pp) | 1949.353/1950.486 (+1.13) | 6.6%/6.5% (-0.1 pp) | -16.65% [1262/1314]/-15.69% [1263/1314] (+0.96 pp) | +0.00% [1262/1314]/+0.00% [1263/1314] (+0.00 pp) | 3.6%/3.6% (+0.1 pp) | 0.0%/0.0% (+0.0 pp) | need 5252/5256, live 5252/5256; need 5251/5256, live 5251/5256 |
| Temporary local furniture inventory-target increase | 4244 | 1497/1497 | yes | 100.0%/100.0% | 100.0%/100.0% | 94.1%/94.1% (+0.0 pp) | 2248.914/2249.499 (+0.58) | 1.7%/1.7% (+0.0 pp) | -7.31% [1491/1497]/-7.39% [1491/1497] (-0.08 pp) | +0.00% [1491/1497]/+0.00% [1491/1497] (+0.00 pp) | 0.7%/0.7% (+0.0 pp) | 0.0%/0.0% (+0.0 pp) | need 5988/5988, live 5988/5988; need 5988/5988, live 5988/5988 |
| Temporary local furniture inventory-target increase | 4245 | 1315/1315 | yes | 99.7%/99.9% | 99.7%/99.9% | 80.0%/80.0% (-0.1 pp) | 1922.235/1917.950 (-4.28) | 2.9%/2.9% (-0.0 pp) | -14.09% [1286/1315]/-15.35% [1289/1315] (-1.26 pp) | +0.00% [1286/1315]/+0.00% [1289/1315] (+0.00 pp) | 1.1%/1.1% (-0.0 pp) | 0.0%/0.0% (+0.0 pp) | need 5253/5260, live 5253/5260; need 5259/5260, live 5259/5260 |
| Temporary local furniture inventory-target increase | 4246 | 1495/1495 | yes | 99.9%/99.9% | 99.9%/99.9% | 89.2%/89.1% (-0.2 pp) | 2140.408/2140.181 (-0.23) | 3.3%/3.5% (+0.2 pp) | -9.34% [1463/1495]/-9.26% [1463/1495] (+0.08 pp) | +0.00% [1463/1495]/+0.00% [1463/1495] (+0.00 pp) | 2.2%/2.3% (+0.2 pp) | 0.0%/0.0% (+0.0 pp) | need 5979/5980, live 5979/5980; need 5978/5980, live 5978/5980 |

Across seeds, cohort survival stayed between 99.7% and 100% at turn 11, with no consistent treatment direction. Need-met changes were very small and mixed: −0.02 to +0.07 percentage points for the wood cut and −0.15 to +0.09 points for the furniture-demand shock. Calories eaten per need-person-turn changed from 0 to +1.80 kcal in the wood screen and −4.28 to +1.13 kcal in the furniture screen. Median cash effects ranged from −1.26 to +2.71 percentage points of baseline cash; median debt changes were zero in every seed. Cash-wage receipt incidence changed by −0.13 to +0.18 points, and no scrip-wage receipts were recorded. This short sample shows no consistent population-wide welfare response, while control-arm need-met rates in the shock window were 80%–94% across seeds; subgroup losses can be hidden by these cohort aggregates.

An absent roster member can have migrated or otherwise left the observed actor set; absence is not treated as death. Alive coverage and presence coverage are shown separately. This is a fixed-cohort shock-window comparison, not an estimate of long-run recovery or a historically calibrated welfare effect.

## Limits

Five seeds are a diagnostic sample, not a precise uncertainty estimate. Deep audits cover all 20 arms: the bounded structural/formula checks and public-account closes pass, but only 1,064/1,200 treasury turns are fully attributed and complete causal coverage remains false. Full goods-stock conservation, broader welfare accounting, prospective recovery evidence, and primary-source calibration remain open in the analysis plan.

Reproduce the paired runs with `economic_shock_experiment.py` for each seed, then summarize their saved JSON without re-decoding traces:

```sh
venv/bin/python economic_shock_multiseed.py --root tmp/economic-shocks/default-resident-cohort --seeds 4242 4243 4244 4245 4246
```
