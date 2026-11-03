# Food access implementation and acceptance

Implemented 2026-10-30 from [the approved plan](../engineering_food_access_plan.md).
Original evidence remains in [the diagnosis](engineering_food_access_20261029.md).

## Delivered behavior

- Household food orders use a meal requirement and a configurable reserve
  (two future turns by default). Requested quantities fit a unit-price budget;
  increasing a desired basket cannot recreate the oversized-order rejection.
  Dependent children order through the local parent, and queued meals and
  prepared food already owned reduce new grain demand.
- Corporations procure food against recipe inputs or explicit company-store
  requirements. Their employee count no longer creates a household appetite.
  Firms and employees can offer excess grain while protecting meals, dependent
  requirements, and operating stocks. Public procurement and provincial levies
  also protect genuine operating commitments.
- Employees can buy a meal from company inventory with cash. Scrip still
  redeems existing credit; emergency company advances have a cumulative ceiling
  and configurable unit allowance. Ordinary store purchases do not create cash
  or credit.
- After payroll and company-store settlement there is one additional local
  food purchase opportunity covering remaining meals. It uses actual paid cash,
  refreshes savings availability, and does not reuse a stale household basket's
  zero unit limit. It does not rerun interest, borrowing, payroll, tax, or other
  goods markets. The food price is published once, using combined sales evidence;
  sales histories and imported-sale attribution are preserved.
- Public grain delivery and charity distribution happen before consumption
  and mortality. A shared province charity distributes through each district's
  pre-meal boundary; the former end-of-province distribution is removed.
  A per-district turn guard prevents repeated aid. Ordinary charitable portions
  remain limited; this is not a guarantee of full meals for everyone.
- Authorized emergency granary release can occur outside the seasonal release
  window. It is limited by actual grain, remaining meal gaps, explicit reserve
  policy, and handling capacity. Seasonal releases count toward that turn's
  handling capacity. The final stored unit can be used in an emergency.
- Employed workers retaining food-growing skills can seek emergency food credit;
  the old profession-only exclusion no longer treats them as self-feeding.
- Campaign settings independently expose responsive wages/labor mobility,
  authored or autonomous owner strategies, relief policy, and private/regional
  installed steam. Existing authored stress tests remain available. Default
  game behavior is unchanged by the new opt-in fixture switches.
- The nation comparison shows an expandable food-access explanation: supply,
  meal needs, household/company/public/charity stocks, saleable food, cargo in
  transit, meal prices, wage quotes, and policy constraints. Desktop municipal
  cards show the same diagnosis. Gross foraging is captured before deaths so
  the supply measure does not silently lose a deceased resident's contribution.
- Food auction traces record filled quantities and reasons for remaining
  unfilled demand. The new formula replays; existing market, food-transfer,
  granary, and price formulas remain supported.

## Validation

151 focused and regression tests pass across food access, local/international
markets, company scrip, food recovery, charity timing, nutrition, granary stock
flows, installed productivity, engineering/adoption, web projections, and the
concurrent abundance system. New regression cases include the solvent buyer
with an oversized basket, cash company-store purchases, payday cash against a
previous empty basket, policy-off/emergency granary rules, dependent ordering,
aid before intake, one price publication, and preserved import attribution.

Save/restore validation covers the default server, authored labor-frontier and
supply-rivalry scenarios, pending cargo/loans/technology, failed publication
recovery, and the native Egypt world. These checks compare full continued
economic graphs in fresh processes.

Chrome desktop (1440px) and mobile (390px) checks pass without page errors or
page-width overflow. The native municipal card was rendered and inspected.
The temporary browser server is not part of the shipped gameplay.

## Eighteen 100-turn campaigns

All cases use `PYTHONHASHSEED=0`, seeds 4243/4242/4244, and independent processes.
All 18 have zero currency-audit violations and an unchanged simulation-source
fingerprint from start to finish:

`fdf616204664b019db4e2eda124f91b87ff32b43962a013cbaea4557f61631f0`

Every case ends with zero food units in corporations. Read-only food observers
reproduce the full saved acceptance results for seed-4243 commercial,
responsive, and frozen-relief cases exactly.

| Case | Seed | Final residents | Final underfed | Starvation deaths, all 100 turns |
| --- | ---: | ---: | ---: | ---: |
| Commercial, authored owners/frozen wages | 4243 | 109 | 7 | 13 |
| Regional public steam pilot, frozen wages | 4243 | 83 | 6 | 10 |
| Technology-adoption control, frozen wages | 4243 | 86 | 8 | 9 |
| Responsive wages and labor mobility | 4243 | 19 | 12 | 82 |
| Responsive wages/mobility plus adaptive relief | 4243 | 8 | 8 | 97 |
| Frozen wages plus adaptive relief | 4243 | 62 | 5 | 4 |
| Commercial, authored owners/frozen wages | 4242 | 93 | 6 | 12 |
| Regional public steam pilot, frozen wages | 4242 | 95 | 9 | 8 |
| Technology-adoption control, frozen wages | 4242 | 86 | 11 | 9 |
| Responsive wages and labor mobility | 4242 | 11 | 11 | 82 |
| Responsive wages/mobility plus adaptive relief | 4242 | 3 | 3 | 96 |
| Frozen wages plus adaptive relief | 4242 | 70 | 6 | 3 |
| Commercial, authored owners/frozen wages | 4244 | 84 | 7 | 7 |
| Regional public steam pilot, frozen wages | 4244 | 94 | 6 | 10 |
| Technology-adoption control, frozen wages | 4244 | 89 | 6 | 9 |
| Responsive wages and labor mobility | 4244 | 22 | 9 | 71 |
| Responsive wages/mobility plus adaptive relief | 4244 | 9 | 9 | 97 |
| Frozen wages plus adaptive relief | 4244 | 79 | 9 | 1 |

Adaptive relief invokes the existing food-security controller each turn: it
funds/enables emergency response when its assessment calls for it. It does not
hold emergency policy on permanently. Responsive labor enables wage adjustment
and the existing career/job mobility scheduler while leaving the authored
owners' investment strategy separate.

These are complete simulation outcomes with different population and random
event paths. The archived October-29 runs also predate concurrent production,
demand, and prepared-food changes. Their old-to-new death counts do not isolate
the food-access repairs. The within-current-source cases expose policy effects
and remaining failure modes, rather than proving universal famine recovery.

## Remaining failure is visible, not resolved by these repairs

The frozen-wage commercial fixture still produces poverty and starvation. On
seed 4243 its original firm's workers die while their employer holds zero food,
instead of dying beside the employer's formerly inaccessible 54–58 units.
Some solvent people still fail to obtain food because no surplus is offered
or other buyers win the auction. Correct order sizing does not guarantee a
market fill.

Adaptive relief reduces starvation deaths in the frozen fixture from 13 to 4,
12 to 3, and 7 to 1 across the three seeds, with different population outcomes.
Ordinary limited charity and a fixed low wage still do not guarantee a meal.

The responsive one-region fixture exposes a severe additional feedback:
workers move into the highly profitable furniture/wood economy and paid jobs;
the farming workforce and commons foraging decline, then grain production
reaches zero. At seed 4243, the responsive case ends producing no grain and
gathering only 28 food units per turn. Relief cannot procure food that no one
produces once reserves are exhausted. The adaptive controller can alter
population and labor paths further, so it is not uniformly beneficial.

This is an unresolved labor-allocation/production stability problem in the
authored boom scenario. The implementation does not force farmers to stay,
fabricate grain, guarantee profitable wages, or suppress deaths to make the
acceptance table look favorable. Before treating this fixture as a general
technology balance benchmark, its occupational-return expectations, paid-job
sustainability, and recovery into farming need their own causal investigation.

A separate current-source default-world smoke run with all three nations under
their policy AI completes ten real turns. At turn ten the United States,
China, and Japan have 401, 596, and 592 residents respectively, with zero
underfed residents in each nation. This checks the integrated multi-region path;
ten turns are not evidence of long-run stability. Its stored currency field is
the final turn's audit result, not an accumulated ten-turn audit.

## Evidence and reproduction

- [Matrix summary](food_access_final_20261030/summary.json) and individual
  case files in that directory preserve settings, milestones, source hashes,
  deaths, final food access, technology activity, and per-turn currency audits.
- `commercial_4243_food.json.gz`, `responsive_4243_food.json.gz`, and
  `frozen_relief_4243_food.json.gz` preserve orders, auction limits and fills,
  daily meals, stocks at death, and matching acceptance metadata.
- [Default-world smoke run](food_access_final_20261030/default_world_10_turns.json).
- Intermediate experiments are retained separately in
  `food_access_intermediate_20261030/`; they are not final acceptance evidence.

```sh
env MPLCONFIGDIR=/private/tmp/engineering-mpl venv/bin/python scripts/audit_food_access_matrix.py
env MPLCONFIGDIR=/private/tmp/engineering-mpl venv/bin/python -m unittest tests.test_food_access
```

The matrix reruns all 18 cases and rejects changing simulation sources or any
currency-audit violations. Run each individual campaign in a fresh process.
