# Distribution changes: matched abundance rerun

The rerun shows **no improvement in the recorded outcomes of this particular
benchmark**. Every saved per-turn field matches the previous 60-turn result,
both with doubled farm yield and in the unchanged-yield control. This establishes
matching recorded outcomes, not identity of every unrecorded internal state.

Both cases ran in fresh processes with seed 4243, 70 initial residents, the same
profession distribution, no traders, and the same 60-turn horizon. The higher
productivity case doubles farm yield at turn 16. Spoilage remains absent. Game
rules and policy settings were not changed for the comparison.

The current source fingerprint was unchanged across both reruns:
`642fa60b2fcd071b3239c886e627718e4a112cdc8869637c48460d2184c2e6aa`.

## Matched higher-productivity outcome

| Measure | Previous run | Current rerun |
|---|---:|---:|
| Residents at turn 60 | 304 | 304 |
| Underfed at turn 60 | 45 (14.8%) | 45 (14.8%) |
| Mean underfed share, final 20 turns | 12.23% | 12.23% |
| Raw grain in agent inventories at turn 60 | 4,125 | 4,125 |
| Grain reference price at turn 60 | 0.4956 | 0.4956 |
| Prepared food produced over 60 turns | 673 | 673 |
| Underfed person-turns over 60 turns | 907 | 907 |
| Currency-audit violations | 0 | 0 |

The control also matches its archived observations: 231 residents, 57 underfed,
and 33 grain units in agent inventories at turn 60. Its final-twenty-turn mean
underfed share remains 34.04%.

## Distribution mechanisms are running

Separate read-only observation runs reproduce the current acceptance result
exactly. Across the higher-productivity case they record:

- 60 post-payroll purchase opportunities, transferring 810 food units.
- 60 public-aid calls, delivering 949 units.
- 60 charity-distribution calls, delivering 382 units.
- 60 emergency-release evaluations, but zero emergency-enabled turns and zero
  emergency granary releases.

These figures describe current-source activity. No equivalent mechanism-level
archive was captured for the earlier run, so they do not measure changes in those
individual flows. Identical aggregate outcomes can mean an earlier run already
contained a repair, or that a changed path did not alter this fixture's outcomes.
They do not establish that the distribution repairs have no value in other cases.

This local fixture does not add nations or a sovereign policy AI to its turn
loop. It therefore does not exercise the adaptive national-relief settings of
the separate food-access campaign matrix. Emergency policy stayed off here.

## The current remaining problem is concentrated among poor adults

At the actual meal boundary of turn 60:

- All 45 underfed residents are age 14 or older; 23 are employed.
- The 45 residents collectively have 5.2104 in cash and no bank deposits.
- Nineteen have less than 0.01 in combined cash and deposits.

At the close of the same turn, two landlords hold 2,507 and 1,193 grain units:
3,700 of the region's 4,125 units, or 89.7%. Applying the existing ordinary
reserve rules leaves 3,664 units saleable, all held by those two landlords.
Corporations hold 15 grain units; those units are below their operating reserve.
The granary separately holds 112 units while emergency release remains disabled.

These observations point to adult purchasing power and concentration of grain
ownership as the immediate issue to investigate in this fixture. They do not
show that children are the residual underfed group, or that most surplus is
trapped in company stocks. Having grain available for sale does not fund a hungry
household's purchase, and ordinary aid does not guarantee a complete meal.

## Evidence

- [Current higher-productivity run](higher_productivity_4243.json)
- [Current control](control_4243.json)
- [Source and execution manifest](manifest.json)
- [Machine-readable comparison](comparison.json)
- [Distribution activity, verified to preserve the result](distribution_activity_4243.json)
- [Meal-boundary cash, savings, and ownership diagnostics](final_household_access_4243.json)
- [Archived comparison source](../abundance_acceptance_20261030.json)
