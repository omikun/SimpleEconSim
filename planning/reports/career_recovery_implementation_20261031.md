# Career recovery implementation and acceptance

Date: 2026-10-31. Status: implemented; career rules accepted, food balance remains open.

The regional economy now makes career choices once, before production. Every eligible adult is considered regardless of savings. Hiring, independent work, workshop entry and demographic entry points share the same departure ledger.

## Implemented rules

- Protect four living adult workers per profession per region. Count actual work: employer output for employees, current production occupation for independents. Children, firms and service roles do not inflate the protected workforce.
- Freeze headcounts before hiring. Departures use `min(25%, 10% × relative feasible-return gain)` applied to workers above four. The strongest feasible proposed move sets the source rate; stronger moves receive slots first.
- Carry fractions below one between qualifying turns. Unused whole slots expire; idle professions reset the fraction. Arrivals cannot refill capacity, and commitment rechecks the living workforce after forced losses.
- Trader admission also consumes the existing source profession’s departure budget, preventing an alternate route around the floor. Coming of age records the household trade without granting a second departure decision.
- Same-profession employer moves and exits to independent work in the same profession need no departure slot. Death, compulsory reassignment and displacement can take a profession below four.
- Compare current work against independent output, retained household food, commons food, input costs, actual sales and funded vacancies. Existing equipment, skill, land and financing gates still apply. Jobs and independent choices compete in one pass, replacing the old emergency quit/rehire loop and random demographic fallback.
- New processing workshops can use real funded unfilled household orders as evidence before their first sale. A posted price alone does not establish a market.
- Record return comparisons and feasibility evidence, plus each profession’s population, floor, quota, used slots and blocked workers. The web Citizens → Labor panel shows the full table; desktop government cards show the farmer summary.

## Price evidence

Actual paid transactions have dated observations. Food’s two auctions merge paid quantities into one per-turn VWAP. Observation influence decays with a configurable three-turn half-life and twelve-turn window. Idle quotes do not refresh evidence. Old undated save histories are retained but cannot be treated as newly paid transactions. Historical v1 formula replay is preserved; new calculations use v2. Moves remain bounded, with existing input-cost floors and price ceiling retained.

Zero buyers and zero sellers are neutral in the demand/supply record. Positive funded demand with no sellers still produces scarcity pressure. This fixes an idle/emergency-stock corner without manufacturing demand.

## Final campaign matrix

All eighteen 100-turn cases ran at source fingerprint `864b77683f8b21eee3c152fdd90db087afd0f4c2b3bcb19b46ba1a968637db05`. Every run reported unchanged source and zero currency-accounting violations. Full results and daily adult-workforce/food/departure histories are in [the release directory](career_recovery_release_20261031/summary.json).

Starvation deaths over the complete campaign:

| Case | Seed 4243 | Seed 4242 | Seed 4244 |
| --- | ---: | ---: | ---: |
| commercial | 23 | 22 | 21 |
| regional | 18 | 20 | 18 |
| control | 25 | 21 | 17 |
| responsive | 14 | 15 | 13 |
| responsive_relief | 5 | 8 | 10 |
| frozen_relief | 12 | 5 | 13 |

Actual adult farm workforce, including employees doing farm work:

| Case | Seed | Turn 20 | Turn 50 | Turn 100 | Minimum across 100 turns |
| --- | ---: | ---: | ---: | ---: | ---: |
| responsive | 4243 | 15 | 41 | 45 | 11 |
| responsive | 4242 | 8 | 47 | 62 | 8 |
| responsive | 4244 | 11 | 50 | 73 | 11 |
| responsive_relief | 4243 | 11 | 37 | 21 | 11 |
| responsive_relief | 4242 | 11 | 42 | 35 | 11 |
| responsive_relief | 4244 | 12 | 42 | 36 | 10 |

Farm work no longer disappears in these responsive cases: the workforce bottoms at 8–11 adults, then recovers. In seed 4243 it grows from 15 at turn 20 to 45 at turn 100; the final turn produces 34 farm-food units and 280 foraged units. All 12,025 recorded profession-turn budgets satisfy used ≤ quota ≤ starting workforce above the floor, with carry below one.

The archived pre-rewrite responsive runs recorded 82/82/71 starvation deaths, compared with 14/15/13 here. This is context rather than a controlled attribution: prices and other shared-workspace simulation changes differ between source versions. Frozen-labor cases are not uniformly better; the old frozen commercial cases had 13/12/7 starvation deaths, versus 23/22/21 here. The new mechanism is not accepted as a general cure for starvation.

Remaining limits: four workers do not guarantee enough food, especially as population grows. Underfeeding persists in most cases; the food reference often reaches its existing price ceiling. Some households still cannot obtain enough food despite aggregate output. Those are food production, access and balance questions beyond the career-budget rule. No food, money or immortal workers were added to hide them.

## Verification

- 127 targeted career, price, food, market, lifecycle and causal-trace checks passed.
- 109 integration checks for capitalist planning, labor institutions, engineering, productivity, adoption and web parity passed; these include the standard 30-turn world check.
- Four server checkpoint tests passed, covering ordinary and authored scenarios and fresh-process continuation. The ledger and dated price evidence survive save/restore.
- Native Egypt checkpoint continuation passed, including the final release recheck.
- Browser checks passed at 1440×1000 and 390×844, including numeric table fields and no document overflow. Browser test loads the exact local UI scripts directly to avoid intermittent static-file connection resets in the disposable preview server.
- Tests that assumed immediate automatic recruitment now explicitly seed operating mills and a real paid cargo purchase, so their price, workforce and transport trace assertions remain meaningful under gradual career changes.
