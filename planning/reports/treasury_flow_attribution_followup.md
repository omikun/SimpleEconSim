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

- Extend source-flow coverage beyond the audited default-game arms, especially
  to the supply-rivalry scenario and any new intervention writers.
- Reconcile physical goods across household, producer, trader, public and
  in-transit stocks; treasury closure does not establish goods conservation.
- Keep `complete_causal_coverage` marked false until unsupported mutation and
  source-contract coverage is addressed.
