# How the economy performed: seed 4243, higher productivity

The productivity-to-cheaper-food mechanism worked, and a new processing use
emerged. The economy nevertheless ended with growing nutritional stress and a
weak processing sector. This run demonstrates a response to abundance; it does
not yet demonstrate a stable transition to broad prosperity.

[Charts](abundance_4243_analysis_20261030.png) ·
[Calculated phase statistics](abundance_4243_analysis_20261030.json) ·
[Original observations](abundance_acceptance_20261030.json)

## What was simulated

One region began with 70 residents, predominantly farmers, plus woodworkers and
furniture makers. Farm yield was doubled externally at turn 16. There were no
traders, so exports did not contribute to this outcome. Spoilage was disabled.
Production, consumption, prices, births, career changes, and workshop entry then
followed the ordinary turn loop. The yield intervention tests the response to
higher productivity; it does not establish that technology investment itself
would have delivered that doubling.

## The economic trajectory

The following are ten-turn averages, which reduce distortion from the existing
ten-phase agricultural cycle. Hunger means a resident had a positive calorie
deficit that turn. The hunger percentage averages each turn's population share.
Prices are reference quotes, not realized transaction prices or real wages.

| Turns | Residents | Grain produced / turn | Grain reference price | Raw grain inventory | Residents with calorie deficit | Prepared meals produced / turn |
|---|---:|---:|---:|---:|---:|---:|
| 1–10 | 72.4 | 153.0 | 0.967 | 747 | 0.43% | 0.9 |
| 21–30 | 133.3 | 505.3 | 0.758 | 3,647 | 5.68% | 12.3 |
| 31–40 | 182.4 | 437.1 | 0.656 | 6,086 | 7.25% | 24.4 |
| 41–50 | 246.3 | 380.4 | 0.583 | 6,342 | 10.51% | 17.4 |
| 51–60 | 289.4 | 221.5 | 0.521 | 4,914 | 13.94% | 7.5 |

Early on, the economy supplied almost everyone sufficiently, built inventories,
and began processing meals at turn 8. Both the initial recovery of soil fertility
and productive practice were active; the records do not isolate their respective
contributions. Soil fertility reached 1.25 by turn 13 and remained there.

The yield increase then supported a substantial harvest expansion. Grain output
averaged 505 units per turn in turns 21–30. Prices continued down and stocks
accumulated. This is the intended supply response: more physical output supported
both additional residents and a lower staple quote.

The late period is more concerning. Average grain output fell 56% between turns
21–30 and 51–60, while population more than doubled between those windows. Stocks
peaked at 6,834 units in turn 45 and fell to 4,125 by turn 60. This cannot be
explained by spoilage, which was absent. It shows net drawdown of the recorded
agent stocks, although the snapshot does not provide a complete stock-flow bridge.
Output decline alone also cannot establish an overall calorie shortage: foraging
and public grain stocks are not included in the recorded harvest or agent-stock
series.

## Cheap grain did not guarantee food access

Population increased from 70 to 304. The reference price of grain fell from
1.042 at turn 1 to 0.496 at turn 60, approximately 52%.

Yet 45 of the final 304 residents had a calorie deficit, approximately 14.8%.
At that same point, 4,125 grain units remained in agent inventories. At four units
per ordinary adult meal, that is roughly 3.4 turns of adult-sized meals per
resident, before ownership and access constraints. Many residents are children
with different needs, so this is an illustrative comparison, not a precise
reserve-duration estimate.

The combination supports an access or purchasing-power interpretation, alongside
emerging pressure from population and declining output. It does not identify
which owners held the grain or why particular residents went hungry. Low cash,
protected household or business reserves, allocation among dependents, and
production curtailment are mechanisms to investigate, not measured findings here.

The code does reduce production as a producer's own inventory fills, and stops
it at its storage limit. Consequently, declining output could partly be a normal
response to inventories that cannot be sold profitably or to buyers without
spendable cash. The aggregates cannot separate that response from work allocation,
land access, illness, or other production constraints.

## A new food market emerged, but remained small and expensive

Prepared-meal production began at turn 8 and totaled 673 units over the run.
Output averaged 24.4 per turn in turns 31–40, then fell to 7.5 in turns 51–60,
a 69% decline. Prepared-food inventories ended at zero.

The prepared-meal reference price rose from 1.97 to 15.92. At turn 60, a prepared
meal's quote was about 32 times the raw grain quote despite equal calorie content.
This is consistent with a premium convenience/variety product whose processing
capacity or accessibility remained constrained. Cheap grain inputs did not make
the finished product cheap. Wages, equipment costs, realized sales prices, and
firm accounts were not saved, so these quotes do not establish processor profits.

The recorded `workshops` variable is a count of residents whose output profession
is prepared food. It includes children and does not require installed equipment
or positive output. Likewise, the `farmers` variable is not an adult-worker count.
Those series must not be interpreted as operating firms, employment, or capacity.
The run recorded zero farm corporations throughout.

## How much did the productivity increase help?

The same-seed control provides a useful benchmark for the final twenty turns:

| Measure | Higher productivity | Control |
|---|---:|---:|
| Mean grain reference price | 0.552 | 0.902 |
| Mean grain output / turn | 301.0 | 91.4 |
| Mean residents | 267.9 | 233.4 |
| Mean share with calorie deficits | 12.2% | 34.0% |
| Total prepared output over all 60 turns | 673 | 321 |

The higher-yield economy was materially better fed than its control, despite
supporting more people. It was also becoming less secure over its own final
twenty turns. Both statements are true: improvement relative to the counterfactual
does not establish a stable endpoint.

## Assessment and next measurements

This was an agrarian expansion with a small premium-food market, rather than a
demonstrated broad industrial transition. The observed mechanisms support cheaper
staples and new uses, but do not yet establish sustained diversification, rising
real wages, profitable firms, or a demographic equilibrium. Nonfood observations
cover only combined cloth and furniture stocks, not production, spending, or use.
Cash-conservation checks reported no violations; this verifies that audit, not
the economy's welfare or profitability.

Before adding spoilage or retuning demand, the most useful next diagnostics are:

1. Stocks, spendable cash, food bids, fills, and protected reserves for hungry
   households versus adequately fed households.
2. A complete food bridge: harvest, foraging, public stocks, processing inputs,
   transfers, and consumption, with prepared meals avoiding double counting.
3. Production withheld because of full inventories, work allocation, illness,
   insufficient inputs, or lack of land access.
4. Equipped adult processors, actual labor, sales, costs, and profit; adult
   workforce and dependent population counted separately.
5. Nonfood output and consumption, household budget shares, and wage purchasing
   power, to determine whether staple abundance creates broader prosperity.

No game rules were changed for this analysis.
