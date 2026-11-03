# Farmer recovery: simplified career-transition plan

Date: 2026-10-31. Status: implemented. See the [acceptance report](reports/career_recovery_implementation_20261031.md).

The user has chosen a simple profession-level transition cap in place of the
previous heterogeneous-beliefs and detailed transition-frictions design.

Evidence: [matched mobility replay](reports/farmer_mobility_20261030.md).
Existing foundations: [food-access implementation](reports/food_access_implementation_20261030.md).

## 1. One career-decision path and one departure budget

Use [the simplified transition design](livelihood_decision_redesign.md).

Each profession in each region receives a per-turn departure allowance based
on the attractiveness of feasible alternatives and the number of adult workers
remaining above a protected minimum. Start with minimum four, gain sensitivity
0.10 and maximum transition rate 0.25; these are configurable tuning parameters.

Rank beneficial feasible moves and commit them through one ledger shared by
hiring, independent career changes and demographic career decisions. Remove
cash-based exclusion and competing fallback mutations. Preserve the physical,
financial and legal checks already needed to carry out a move.

Carry fractional allowances so small professions can shrink gradually to four.
Unused whole slots expire. A same-profession employer change does not use an
exit slot; an arrival cannot refill that turn's budget. Children and companies
are not adult workers. Forced events and deaths are accounted separately.

## 2. Repair stale price evidence separately

Timestamp actual paid transactions and reduce their influence as they age.
Use a configurable decay rate and observation window. Idle quotes must not
be relabeled as fresh transactions. Sustained funded demand with no offers
should influence quotes, and returning supply should permit prices to fall.

Preserve one coherent price update per turn, bounded movements, affordability,
historical formula replay and save compatibility.

## 3. Validate and explain

Show the profession's population, protected minimum, permitted departures,
used slots and blocked moves. Record the return comparison and feasibility
checks that produced each proposed move.

Test rate scaling, the protected minimum, fractional carry, expired unused
slots, all hiring paths, failed commitments and save/restore. Rerun the existing
eighteen 100-turn cases across seeds 4243, 4242 and 4244 at one source version.
Measure actual adult farm labor, completed harvests, foraging, food prices,
meal intake and deaths alongside the transition counts.
