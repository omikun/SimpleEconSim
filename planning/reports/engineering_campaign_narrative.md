# What happened in the engineering campaigns

This account uses a read-only replay of the four original seed-4243, 100-turn
runs. Every original acceptance snapshot matches. The extra telemetry is in the
four `engineering_*_diagnostics.json` files beside this report; replay with
`scripts/inspect_engineering_campaigns.py --variant NAME --output PATH` in a fresh
process for each variant. No gameplay rules were changed for this diagnosis.

## What these worlds were

Four separate versions of one nation, each named Engineering Republic, each
controlling a single region called Works. The actual starting regime is
autocracy. There are no neighboring regions, foreign rivals, trade routes or
starting armies. There is consequently no international war, expansion or trade
competition to narrate. Normal domestic economy, ecology, demographics, politics,
banking and innovation all run.

Commercial, public and control begin with 75 resident agents and 250 cash per
ordinary resident; weak demand begins with 18 and 40. Each has a 10,000 national
treasury, a testing workshop, commons tenure, generous forestry output, finite
supplier stock and a furniture firm with 2,500 capital and four employees. All
know coal coking at high capability. Public begins without steam knowledge; the
others begin with a tier-1 blueprint. The control disables autonomous deployment.

This is an engineering acceptance fixture. Its owner policy disables ordinary
wage adjustment and elite planning; no general national AI responds to crises.
The tracked factory's wage remains 2.5. Public research renewal is the only
scripted strategic response. These limits matter when interpreting the collapse.

## Commercial pioneer

The named furniture factory invests 800 in a tier-1 installation on turn 11,
estimating 92.18 extra receipts per turn and 8.68 turns to pay back. A second
furniture company installs the same generation on turn 16 for 770.50. Both pay
without investment loans. National private installation spending is 1,570.50;
the earlier acceptance table recorded only the named factory's 800.

On turn 20 the tracked firm has four employees and 5,809 cash. Its average
receipts over the latest eight turns are 724 per turn. It has spent 98.93 on
private steam engineering. The national blueprint is still tier 1; manufacturing
maturity is 25.50%. Later total private steam engineering spending is 116.66.

The tracked factory's workers become subject to pollution-related withholding
from turn 38. Production then becomes zero while wages and living costs persist.
All four original employees die of starvation, on turns 54, 58, 61 and 66. No
replacement is hired. The log records 2,963 insufficient-wage rejections, plus
unavailable candidates; these are repeated offers, not distinct people.

The second steam user continues operating intermittently and still has one
worker at turn 100. National capability reaches tier 2 on turn 55 and ends at
38.24 XP. Both installed machines remain tier 1. Generation-1 maturity reaches
47.77%; tier-2 blueprints inherit 16.72%. Knowledge has progressed without free
upgrades to existing equipment.

Resident-agent counts at turns 0/20/50/100 are 75/80/104/104. The engine records
79 births, 29 age-or-health deaths, 15 disease-attributed deaths and seven
starvation deaths. These flows need not reconcile directly with resident counts
because corporation creation and role conversion affect the agent census.
At turn 100, 71 resident agents carry the native-child flag. There are 44
corporate entities, but only one employs anybody. The count of companies is not
a measure of productive industrial capacity.

Organic discoveries continue: crop rotation on turn 43, bloomery iron on 48,
guild standardization on 53 and mechanized textiles on 73. There are 23 recorded
coup events, between turns 21 and 87, repeatedly led by the same agent. The final
regime remains autocracy. The repeated-coup pattern is a model pathology to
investigate, not 23 distinct historical regimes.

## Public engineering challenger

Paid experiments demonstrate steam on turn 10, reach tier 2 on 15, and tier 3
on 64. Public steam engineering costs 1,146.11 over the run. Most is early:
968.19 has been spent by turn 20, when iron shortages constrain further work.
The 100-per-turn authorization is a ceiling, not automatic spending or progress.

Private industry deploys the results. The tracked factory commissions tier 1 on
turn 11, another company commissions tier 2 on 16 for 792.83, and the original
factory pays 316.82 for a retrofit on 17. National private capital spending is
1,909.65. Both final installations are tier 2; national knowledge is tier 3.

On turn 20 the tracked firm has 6,443 cash, four workers, and recent average
receipts of 815 per turn. Its engineering advantage does not avert the domestic
crisis. Pollution-related withholding includes three workers from turn 25 and
all four by turn 33. Its employees die of starvation on turns 49, 53, 56 and 57.
It ends with 3,860 cash and 2,757 deposits but no workers. The other firm also
ends without employees.

Resident counts are 75/77/103/71 at turns 0/20/50/100. The engine records 56
births and 64 deaths: 42 age-or-health, 12 disease and ten starvation. There are
100 active disease cases at turn 50, of which 85 are untreated; diagnoses can
overlap in the same person. The peak is 115 cases on turn 65. Public medical
spending is zero throughout this fixture, despite the separate engineering
budget. There are 65 recorded coup events, turns 36–100, all with the same
recorded leader. The national treasury finishes at 10,006 despite research
spending because other fiscal and estate flows also operate.

Other discoveries are crop rotation on turn 53, bloomery iron on 70 and guild
standardization on 83. Tier-3 steam manufacturing maturity ends at only 7.96%.
The run shows high technical capability coexisting with costly, immature designs
and poor living conditions; it does not show that public research caused those
living conditions.

## Weak demand

The firm has the same initial capital as its richer counterparts, but fewer,
poorer customers. On turn 20 recent sales average 122 per turn. An 800 steam
installation has an estimated 34.65-turn payback and negative discounted value.
No company deploys steam, no dedicated steam engineering is funded, and the
blueprint remains at tier 1 with zero maturity. No additional technology is
discovered during this run.

The factory loses one employee to age-or-health mortality on turn 23 and three
to starvation on turns 39 and 43. It ends with 1,098 cash and 1,124 deposits,
but no workforce. Hiring remains unsuccessful; 1,089 offers are rejected as
insufficient, plus unavailable candidates.

Resident counts are 18/19/17/35. There are 23 recorded births and six recorded
deaths. Pollution is much lower than in the larger economies and the tracked
workers never enter pollution-related withholding. Final active disease cases
number only one. Soil fertility remains 1.25. Nevertheless, food-price inflation,
hunger and political instability persist: the engine records 56 coup events
between turns 35 and 100. Final national cash is 10,255. This is technological
stagnation with a surviving but distressed local economy, not an empty world.

## Control without autonomous deployment

The control starts with the richer commercial conditions but never installs
steam equipment. Its factory initially sells well and holds 6,373 cash on turn
20. Pollution-related withholding begins on turn 23, affecting all four workers
by turn 24. Employees die on turns 33, 46, 52 and 54: one age-or-health death and
three starvation deaths. The original corporate entity eventually dissolves.

Resident counts are 75/81/90/55. The engine records 32 births and 63 deaths:
37 age-or-health, 18 disease and eight starvation. Disease peaks at 92 concurrent
cases on turn 63. Soil fertility reaches 0.20 by the end. The control records
two coups, on turns 89 and 90. Organic discoveries still produce bloomery iron
(50), guild standardization (55), crop rotation (59) and mechanized textiles
(95), while the unused steam blueprint stays at tier 1.

This run establishes that the original factory's demise also occurs without
the new adoption behavior. It does not isolate every cause of the differences
between runs: interventions change subsequent actions and random-draw paths.

## Shared macroeconomic failures

Food prices begin at 1. By turn 100 they are 32.65 commercial, 33.31 public,
21.35 weak-demand and 44.77 control. Tracked factory wages remain 2.5 throughout.
Food inventories still exist, including stock held by the firms, while workers
starve. This is an access/distribution and real-income problem as well as a
production problem. Fixed wages and disabled adaptive management in the test
fixture materially amplify it.

Recorded food output falls from turn 20 to 100: 135→13 commercial, 138→14 public
and 110→13 control. Soil fertility reaches its 0.20 floor in those three larger
economies. Weak demand retains 1.25 fertility and food output rises from 10 to
30. Foraging, inventories and allocation must also be considered when assessing
nutrition; reference-price-valued GDP alone is not a food-access measure.

Bank loans outstanding at turn 100 are 8,584 commercial, 8,079 public, 2,997
weak-demand and 8,590 control. No bank freezes, but lending capacity is almost
fully used. The reported technology investments themselves use no loans.
National treasuries remain near or above their initial 10,000. Neither those
cash balances nor zero currency-audit violations establish prosperity.

Nominal GDP is physical production multiplied by current reference prices,
including unsold output. High food prices can increase that number during
material hardship. The poverty/health and productive-capacity data give a much
less favorable picture than nominal balances do.

The technology mechanism's distinctions remain visible: knowledge versus
installed machinery; capability versus manufacturing maturity; investment
versus demand; and engineering budgets versus actual staff/material capacity.
The next representative balance run should restore adaptive wage/management
responses and include public-health/food policy, while separately investigating
repeated coups and the proliferation of empty companies. No such fixes were
made during this read-only diagnosis.
