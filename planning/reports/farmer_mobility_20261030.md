# Why the responsive campaign loses its farmers

Read-only investigation, 2026-10-30. Seed 4243, commercial engineering,
responsive wages and labor mobility, authored owner strategies, ordinary relief.

The observed 100-turn run reproduces the complete saved acceptance result
exactly, including the source fingerprint:

`fdf616204664b019db4e2eda124f91b87ff32b43962a013cbaea4557f61631f0`

No gameplay changes were made for this investigation. Observers recorded
occupational scores, job offers, job exits, eligibility, market quotes and
volumes, and the original farmers' subsequent occupations.

## Why they leave

The authored economy gives industrial work much stronger early returns. It
starts households with cash and food, seeds an operating furniture firm, and
gives forestry unusually high output. Early food is cheap and ample in household
stocks; there is real demand for furniture.

On turn 4, original farmer 18 compares the following decision scores:

| Occupation | Expected-return score |
| --- | ---: |
| Food | 4.805 |
| Wood | 5.831 |
| Furniture | 63.716 |

The scores combine estimated reachable cash sales, costs, and food retained
for the household; they are not receipts already paid. Farmer 18 changes to
furniture. On turn 8, farmer 37 sees furniture at 80.477 against food at 5.003
and makes the same change.

Across the campaign, 24 observed independent switches by the original farmers
leave food: 16 for furniture and eight for wood. Hiring removes additional
farmers from independent production. On turn 15 there are 52 accepted furniture
job offers and 11 wood offers across all residents; 72 of 86 residents end the
turn employed. Accepted offers are recorded evaluations, not a count of unique
people employed over the entire campaign.

The original 44 independent farmers decline as follows:

| Turn | Original farmers still personally farming independently |
| --- | ---: |
| 1 | 44 |
| 8 | 42 |
| 12 | 21 |
| 14 | 18 |
| 15 | 0 |
| 20 | 0 |
| 38 | 1 |
| 50 | 0 |
| 100 | 0 |

This table follows the founding farmer IDs. New children often carry the food
occupation label despite being too young to produce; counting every such label
as an active farmer would obscure the collapse.

## Why the recovery fails

### 1. Wealth excludes hungry people from occupational reconsideration

`LaborMobilityScheduler.get_non_elites` requires cash below 150, in addition to
its role and childhood restrictions. This cash threshold is applied before the
emergency hunger path is selected. Therefore hunger cannot rescue an excluded
cash-rich worker.

On turn 60, six of the original farmers are explicitly skipped while hungry
with cash above that threshold: IDs 34, 32, 22, 47, 36 and 11. Their cash ranges
from about 175 to 408. Food in their inventories is insufficient, but their cash
keeps them out of the career-recovery calculation.

The old demographic career mechanism also returns immediately when
`region.labor_scheduler_last_turn == turn`. That flag describes the whole
district, including people the scheduler did not select. Those people do not
receive a fallback career assessment.

Sources: `economy/labor_mobility.py:174–187`,
`agents/demographics_career.py:147–148`.

### 2. Quitting to forage skips the farming decision

For eligible workers with at least two hunger steps and usable commons, the
scheduler can call `quit_job`. It then immediately executes `continue`, skipping
the independent-career comparison for that person. Quitting preserves the
current occupation, so a furniture worker becomes an independent furniture
worker who can forage; they do not automatically resume farming.

The observed run contains 593 hunger-driven job exits. None is followed by a
food-career comparison for the same person on the same turn. These are repeated
exits by a much smaller population, not 593 distinct workers.

Hiring is evaluated before independent occupational choices. A later job offer
can therefore pull the person into another industrial job before farming is
considered. The daily demographic job-seeking mechanism is another hiring path.
Offer acceptance checks the wage against a reservation wage and verifies current
payroll/input funding. It does not establish that the resulting cash can obtain
a meal from a market with no grain offered.

The occupational scheduler records no food-return comparisons after turn 52,
even though famine continues for the remainder of the campaign.

Sources: `economy/labor_mobility.py:300–320` and `:329–391`,
`micro/labor_choice.py:40–114`, `agents/demographics_career.py:102`.

### 3. The food-price signal is anchored to obsolete trades

The reference-price rule responds to funded demand and scarcity, but repeatedly
blends its result toward the last twelve transaction-price samples. Samples are
not discounted by elapsed time. When trading stops, the same historical prices
continue to restrain the quote.

| Turn | Food units bid | Units offered | Food quote | Furniture quote |
| --- | ---: | ---: | ---: | ---: |
| 20 | 1,069 | 0 | 1.334 | 37.715 |
| 30 | 1,058 | 0 | 1.648 | 25.743 |
| 40 | 1,023 | 0 | 1.757 | 17.671 |
| 50 | 936 | 0 | 1.777 | 12.459 |
| 80 | 600 | 0 | 5.617 | 4.980 |
| 100 | 297 | 0 | 5.757 | 2.897 |

The food transaction-price sample list is identical on turns 30, 40 and 50.
That is sustained funded excess demand against no offers, while the quoted
price barely changes. Late in the campaign food finally looks relatively more
valuable, but the occupational eligibility and quit/re-hire problems remain.

Source: `micro/region_market.py:530–564`.

### 4. Some farmers return, but the recovery does not persist

Two people independently switch into food on turn 38. Farmer 43's comparison
values food at 7.191 and furniture at 1.407 after industrial competition has
reduced expected sales per producer. This confirms that the return calculation
can favor farming when the person actually reaches it.

Farmer 43 farms for several turns, then accepts a furniture wage offer of about
96.07 on turn 49. By turn 50 this person has about 187.74 cash, no food, and
2.50 hunger steps—already above the scheduler's cash threshold. By turn 53 cash
is about 505.13 and hunger has risen to 5.50 steps.

Land loss is not the dominant observed gate in this replay: 133 of 134 recorded
food-return assessments passed the usable-field check. The sole recorded
rejection on that basis involved another person without a field. Many of the
original farmers retain their named plot while working in industry.

## Implication

Leaving farming for a well-paid opportunity is understandable early in this
fixture. The subsequent failure to recover is substantially a decision-system
problem. Having cash is treated as evidence that survival reconsideration is
unnecessary; hunger-driven quitting bypasses the farming comparison; new job
offers precede that comparison; and old transaction prices weaken the scarcity
signal.

The next repair should let acute hunger bypass wealth/cohort exclusions,
assess food-secure independent work before re-hiring a hungry worker, permit a
person quitting for subsistence to evaluate farming immediately, and reduce the
weight of old price evidence as it ages. These require separate regression and
campaign checks; this investigation does not claim an exact number of deaths
each change would prevent.

Machine-readable evidence:
`farmer_mobility_diagnostics_20261030.json.gz`. The observer script used for the
replay is `/private/tmp/inspect_farmer_mobility.py`.
