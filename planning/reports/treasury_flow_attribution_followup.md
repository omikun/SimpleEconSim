# Treasury-flow attribution follow-up

The clean-source seed-4242 paired shock audit now reconciles every traced
treasury turn after three classes of missing source legs were instrumented:
public welfare/benefit payments, medical/estate/haulage flows, and income-tax
debits paid by a government account.

| Arm | Public-account closes | Treasury-attributed turns | Absolute residual total |
|---|---:|---:|---:|
| Wood supply control | 60/60 | 60/60 | 6.291148e-12 |
| Wood supply treatment | 60/60 | 60/60 | 5.419623e-12 |
| Furniture demand control | 60/60 | 60/60 | 6.291148e-12 |
| Furniture demand treatment | 60/60 | 60/60 | 5.728681e-12 |

The remaining values are floating-point residuals. All four runs also pass
the bounded structural/supported-formula audit with zero reported issues;
complete causal coverage remains false. These results establish source
attribution for these traces and the currently instrumented mutation sites.
They do not prove complete goods-stock conservation or cover every possible
writer in every scenario.

## Refreshed supply-rivalry audit after charity inventory fix

After the charity distribution guard prevented one-unit transfers from
fractional balances, the saved seed-812–816 scenario traces were replayed
again with the corrected whole-unit charity formula. The fresh simulations
were generated from clean source commit
`3056a95d62c96a2b50e5eb0030d97f1c94d868b4`; the replay uses the subsequent
audit fix that floors the fractional balance rather than rounding it up.
All 20 arm traces pass bounded formula/structural checks, all 800/800
public-account closes and 800/800 treasury turns reconcile, and the maximum
absolute residual is 1.727632e-12. The replay reports zero issues. The stock
census contains zero negative holdings in all 400 arm-turn observations.
These checks still leave `complete_causal_coverage` false and do not establish
physical goods-flow conservation.

The follow-up also audited all four arms of the clean-source seed-812
`supply_rivalry` experiment after tracing and instrumenting the government-paid
machinery-repair receipt:

| Arm | Public-account closes | Treasury-attributed turns | Absolute residual total |
|---|---:|---:|---:|
| Cotton supply control | 40/40 | 40/40 | 1.264974e-12 |
| Cotton supply treatment | 40/40 | 40/40 | 9.968553e-13 |
| Mill cotton-demand control | 40/40 | 40/40 | 1.264974e-12 |
| Mill cotton-demand treatment | 40/40 | 40/40 | 1.264974e-12 |

Each scenario arm also passed the settlement-bound gate. The bounded
structural/supported-formula audit reports zero issues in every arm. The
seed-812 machine-readable results and paired report are in
`tmp/economic-shocks/supply-rivalry/seed-812/paired-results.json` (ignored)
and `economic_shock_supply_rivalry_seed812.md`, respectively. The audited
simulation source is commit `569b723ca954c20869f89d4d70097994446a054a`.

Deep audits of the other four paired seeds found one new gap in seed 814. Each
arm still closed all 40 public accounts, but only 39/40 treasury turns were
fully attributed. At turn 20 the Cotton Fields government bought four units of
cloth from Meridian Mill in the ordinary local auction. The trace contained a
government cash-account write and a settled sale, but no nation expenditure:
the residual was `-46.3124698646` in supply control, demand control and demand
treatment, and `-56.9059067482` in supply treatment. `region_market.py` now
emits a negative `government_market_purchase` leg linked to both the account
write and settled sale. A focused regression test checks its signed amount and
causal links. A fresh seed-814 run on the fix commit passes the same 40/40 gates
in all four arms. The complete seed-812–816 sample was then rerun from clean
source commit `569b723ca954c20869f89d4d70097994446a054a` with deep audits:

| Seed | Deep-audited arm traces | Public-account closes | Treasury turns | Maximum arm residual |
|---:|---:|---:|---:|---:|
| 812 | 4/4 | 160/160 | 160/160 | 1.264974e-12 |
| 813 | 4/4 | 160/160 | 160/160 | 1.225783e-12 |
| 814 | 4/4 | 160/160 | 160/160 | 1.727632e-12 |
| 815 | 4/4 | 160/160 | 160/160 | 1.067091e-12 |
| 816 | 4/4 | 160/160 | 160/160 | 1.500217e-12 |

Across the 20 control/treatment arm traces, all 800/800 account closes and
800/800 treasury-flow turns reconcile. Every bounded structural/formula audit
reports zero issues, and every market settlement-bound gate passes. Residuals
are floating-point noise. `complete_causal_coverage` remains false; this
sampled source closure does not prove complete money-writer coverage or goods
stock conservation.

## Diagnosed source legs

The original US T4 control residual of -231.007765 matched the cash outflow
from `government_distribute_welfare_cash`. Benefit methods now pass the active
region when recording baby-bonus, UBI, parental-leave and welfare legs, so
public-account lookup no longer depends on an empty `government.regions` list.

Further intermediate traces exposed government-paid medical care, estate cash
and probate-deposit receipts, and provincial food haulage. These now emit
signed nation-level flows at their mutation sites and link to account-write or
transfer evidence.

The final remaining treatment residual was Japan T16 -5.00. The aggregate
`income_tax_collected` receipt included tax paid by a counted government
account, while the payer debit existed only in the public-account ledger.
`collect_tax` now emits `government_income_tax_payment` for the actual debit
and links it to the account-write evidence.

The final four-arm audit was run on clean source commit
`b4da81d64dd7a72f73f7b8fd9e4b9f591a5b4149`. It preserved paired turn-7 state
matching. Market mechanical gates passed in each arm; source-level and
formula-level gates report zero audit issues. The report and machine-readable
run data are in `economic_shock_screen_seed4242.md` and ignored
`tmp/economic-shocks/seed-4242/paired-results.json`.

## Remaining audit work

- Extend source-flow coverage to new scenarios and intervention writers; the
  current 20-arm scenario sample is now reconciled.
- Reconcile physical goods across household, producer, trader, public and
  in-transit stocks; treasury closure does not establish goods conservation.
- Keep `complete_causal_coverage` marked false until unsupported mutation and
  source-contract coverage is addressed.
