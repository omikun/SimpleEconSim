# Twenty-turn economic policy comparison

Fresh processes use the same world, terrain, nation and hash seeds. All arms must match the initial economy/RNG digest before policy assignment. This is a current-source comparison, not an exact replay of the old trace. Paths diverge after intervention, including their random draws.

The all-AI arm isolates sovereign autonomy against rivals-only. Artisan-input and national-relief arms each change one mechanism against all-AI. The combined arm tests their interaction.

| Arm | Nation | Resident-turns | Underfed resident-turns | Deaths |
|---|---|---:|---:|---:|
| rivals_only | China | 10403 | 913 | 1 |
| rivals_only | Japan | 11132 | 807 | 4 |
| rivals_only | United States | 8692 | 1963 | 7 |
| all_ai | China | 10315 | 199 | 0 |
| all_ai | Japan | 11176 | 599 | 1 |
| all_ai | United States | 9185 | 23 | 1 |
| artisan_inputs | China | 10315 | 199 | 0 |
| artisan_inputs | Japan | 11176 | 599 | 1 |
| artisan_inputs | United States | 9185 | 23 | 1 |
| national_relief | China | 10335 | 199 | 0 |
| national_relief | Japan | 11204 | 555 | 2 |
| national_relief | United States | 9209 | 31 | 1 |
| combined | China | 10335 | 199 | 0 |
| combined | Japan | 11204 | 555 | 2 |
| combined | United States | 9209 | 31 | 1 |

Resident-turns use each turn's current population; these are not fixed-cohort welfare estimates.

| Arm | Tile | Food shortfall units | Food intake records | Wood input failures in furniture |
|---|---|---:|---:|---:|
| rivals_only | c10 | 1079 | 1385 | 159 |
| rivals_only | c46 | 3938 | 2117 | 92 |
| rivals_only | c59 | 1494 | 1970 | 102 |
| rivals_only | c50 | 2247 | 1612 | 112 |
| all_ai | c10 | 1272 | 1431 | 185 |
| all_ai | c46 | 8 | 1434 | 147 |
| all_ai | c59 | 88 | 1397 | 175 |
| all_ai | c50 | 789 | 1549 | 165 |
| artisan_inputs | c10 | 1272 | 1431 | 185 |
| artisan_inputs | c46 | 8 | 1434 | 147 |
| artisan_inputs | c59 | 88 | 1397 | 175 |
| artisan_inputs | c50 | 789 | 1549 | 165 |
| national_relief | c10 | 1020 | 1425 | 188 |
| national_relief | c46 | 8 | 1439 | 148 |
| national_relief | c59 | 111 | 1402 | 174 |
| national_relief | c50 | 794 | 1555 | 165 |
| combined | c10 | 1020 | 1425 | 188 |
| combined | c46 | 8 | 1439 | 148 |
| combined | c59 | 111 | 1402 | 174 |
| combined | c50 | 794 | 1555 | 165 |

| Arm | Trace checkpoints | Food balanced intervals | Wood balanced intervals | Furniture balanced intervals |
|---|---:|---:|---:|---:|
| rivals_only | 20 | 9/20 | 20/20 | 15/20 |
| all_ai | 20 | 15/20 | 20/20 | 19/20 |
| artisan_inputs | 20 | 15/20 | 20/20 | 19/20 |
| national_relief | 20 | 15/20 | 20/20 | 19/20 |
| combined | 20 | 15/20 | 20/20 | 19/20 |

Nonzero stock residuals remain accounting/coverage limitations; trace verification alone does not prove physical conservation. The JSON files retain complete interval audits, compact trace paths, policy decisions and selected city panels. One seed and twenty turns do not establish general resilience.

## Findings and implementation decision

The refactored source was inspected before changes. The existing
`SimServer.autoplay_nations` switch supplies the autonomy treatment; interactive
player control is unchanged. The original twenty-turn trace is not replayed
exactly: these runs use source `8591bd8` with the implementation fingerprints in
the JSON sidecar. All five seed-4242 runs match initial economy/RNG digest
`4c87d6ada03ada` (prefix), and each uses identical implementation bytes. The two
seed-4243 runs also match one another before intervention. The accepted file
manifest in the sidecar selects the rerun controls rather than the earlier
in-progress artifacts rejected by the runner's source-change guard.

- Enabling the existing U.S. national AI is the large response: underfed
  resident-turns fall from 1,963 to 23, while Georgetown's observed food
  shortfalls fall from 3,938 to 8 units. These are realized path comparisons,
  not estimates for identical surviving household cohorts.
- Independent artisan demand is now visible to traders, with eligibility and
  next-meal cash protection. It changes no measured outcomes in this seed.
  Beijing still has 165 missing-wood furniture-production records and produces
  31 furniture units over the twenty turns; its wood imports are zero.
- Wider relief reduces Tokyo's observed appetite shortfall from 1,272 to 1,020
  units. Japan's underfed resident-turns fall from 599 to 555, while the U.S.
  rises from 23 to 31. Total deaths are 2 in all-AI and 3 in the combined arm;
  different subsequent random paths prevent attributing that one-death
  difference specifically to a transport effect. The policy is a bounded
  capability, not a universally improving balancing rule.
- All-AI dispatches 900 food units and receives 448 before the horizon. The
  combined arm dispatches 2,346 and receives 744. Cargo still in transit at
  turn 20 remains in provincial stock censuses; dispatch is not delivery or
  consumption. Source provinces pay existing haulage wages, reserves and levy
  caps remain in force, and unrelated/foreign territories cannot be used as
  domestic transit shortcuts. No national treasury grant to source haulers or
  new procurement contract is introduced.
- Seller orders explicitly distinguish landlords, corporations, public
  governments and other people. The `gov` occupation must not be interpreted as
  evidence of public ownership. This corrects the earlier conversational
  description of Tokyo's private estate holdings as a government reserve.

## Remaining timber bottleneck

The artisan arm records 265 evaluated wood-route candidates toward Beijing:
185 fail the profitability threshold and 80 pass. All 80 passing candidates
see independent producer requests, and 72 finish with wood toward Beijing as
the selected route. Nevertheless there are no physical wood shipments. This
rules out the inference that merely exposing artisan requests will create
usable timber supply.

A concrete acquisition check is turn 12 in source tile c48. Eight selected
traders submit ten-unit wood bids each, but none receives wood. That source
market itself has 429 funded bid units against only 32 offered units, all of
which sell; local output is 18 and the paid VWAP is about 2.21. The traders'
bid limits are about 1.90, capped by their net destination value. The source is
also scarce. A requested route is not a purchase, and a purchase is not a
shipment. Follow timber investment/occupation returns and acquisition bid
limits before introducing a funded procurement or production incentive.
Representative route events, the source clearing panel and complete compact
trace paths are retained in the sidecar and raw arm JSON files.

## Second-seed check

Seed 4243 compares all-AI with the combined changes on the same initial state:

| Nation | All-AI underfed resident-turns | Combined underfed resident-turns | Deaths, both arms |
|---|---:|---:|---:|
| China | 900 | 900 | 0 |
| Japan | 194 | 194 | 2 |
| United States | 59 | 59 | 0 |

Dispatch rises from 482 to 503 units and arrivals from 482 to 485, without a
measured underfeeding or mortality change. This check supports the limited
claim that the new capability functions across another generated world; it
does not establish robust welfare improvement.

## Validation and next work

The combined seed-4242 trace contains 872,509 rows and 20 verified checkpoints.
All 125 focused tests pass, including the nine new policy-response tests.
An additional native Egypt checkpoint integration batch timed out at its
150-second bound while waiting for the fresh-process restore subprocess
(`tests/test_native_simulation_checkpoint.py:63`). It is not counted as passing;
the captured parent traceback is in `tmp/economic-policy-bounded-tests.log`.
Investigate that restore test separately before claiming the broader checkpoint
integration suite passes.
The supported structural/formula audit reports zero issues, 60/60 attributed
nation treasury turns and 60/60 verified public account closes. Market checks
pass for 4,320 rows and 885 settlements. Complete causal coverage remains
false. The five comparison arms and two holdout arms verify 140 checkpoints.
No negative stock rows are observed in the bounded stock censuses.

Wood balances in all twenty intervals in the five seed-4242 arms. Food and
furniture still have residuals; for example the combined arm balances food in
15/20 intervals with a maximum five-unit residual, and furniture in 19/20 with
a maximum one-unit residual. Isolated transport tests conserve goods and cash,
but those checks do not resolve every whole-world lifecycle/storage writer.
Keep the open stock-accounting work ahead of claims of fully reconciled
welfare or resilience.

Next: reconcile the remaining food/furniture residuals; measure fixed initial
household cohorts; trace source timber sellers and the traders' failed fills;
then test a budgeted timber supply/procurement intervention. Consider national
funding of source-province haulage only when the new skipped-dispatch evidence
shows a funding bottleneck. International relief contracts and replacing the
territorial expansion scorer's nominal price thresholds remain separate work.

Reproduce without exporting a full decoded trace:

```sh
MPLCONFIGDIR=/private/tmp/regnum-mpl venv/bin/python -m economy.economic_policy_experiment --seed 4242 --out-dir tmp/economic-policy-reproduction-4242
MPLCONFIGDIR=/private/tmp/regnum-mpl venv/bin/python -m economy.economic_policy_experiment --seed 4243 --arms all_ai combined --out-dir tmp/economic-policy-reproduction-4243
```
