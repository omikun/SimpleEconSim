# Engineering Republic: first 60 turns

This examines the first 60 turns of the responsive-labor commercial campaign, seed 4243. The saved parent campaign is 100 turns long. An instrumented replay ran all 100 turns and matched the complete saved acceptance result exactly, including its snapshots, daily career history, investments, settings and currency audit. No gameplay source or campaign settings changed for this analysis.

Source fingerprint: `864b77683f8b21eee3c152fdd90db087afd0f4c2b3bcb19b46ba1a968637db05`.

[Overview figure](first_60_turns.png) · [Vector figure](first_60_turns.svg) · [Full read-only diagnostics](responsive_4243_diagnostics.json.gz) · [Saved parent campaign](../career_recovery_release_20261031/responsive_4243.json).

The story is an early furniture boom, a food-access crisis, a substantial return to farming, and failure of the original industrial employer. Pollution and political instability become major constraints. The career mechanism preserves and restores farm labor, while household access, physical inputs and institutions continue to fail.

## Scope and opening state

This is one nation, Engineering Republic, and one isolated region, Works. It has no neighbors, traders, imports, exports, foreign wars or autonomous national policy AI. Owner strategic planning is authored/disabled; ordinary firm incorporation, financing, wage response, career choice, markets, nutrition, health, politics and innovation still run. Food relief remains the ordinary policy. There is no public steam pilot or publicly funded engineering program.

The reported opening population is 75 residents, with 73 eligible working adults. Actual work includes 44 in food, 11 in wood, five in furniture, four each in iron, ore and coal, and one in porcelain. Employees are counted by their employer's output. The original furniture company starts with four workers, 2,500 Crowns, 60 wood units and a wage of 2.5.

There are 1,610 food units in resident inventories, one engineering workshop, and generous authored stocks of wood, iron, ore and coal. Forestry is deliberately unusually productive: its base recipe produces 30 units. This is a stress scenario, not a balanced historical starting economy. Steam knowledge starts at prototype capability, but no steam machine is installed.

## Timeline

| End of turn | Reported residents | Farm adults | Furniture adults | Food reference price | Underfed after turn | Recorded starvation deaths, cumulative |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 75 | 44 | 5 | 1.00 | — | 0 |
| 10 | 81 | 22 | 29 | 1.00 | 0 | 0 |
| 20 | 87 | 15 | 33 | 1.46 | 19 | 0 |
| 30 | 92 | 17 | 43 | 2.76 | 15 | 0 |
| 40 | 93 | 40 | 27 | 4.90 | 10 | 4 |
| 50 | 97 | 41 | 25 | 8.71 | 12 | 7 |
| 60 | 90 | 48 | 25 | 17.25 | 4 | 11 |

Population and death counters contain an entity-conversion artifact explained below. Food prices here are reference quotes, not the price of every paid transaction. Meal observations can include a person who dies later in the same turn, so their underfed count can be one higher than the end-of-turn count.

**Turns 1–10: an attractive furniture market draws workers away from food.** Furniture begins at a reference price of 25 and reaches 31.63 by turn 10, while grain remains at one. The comparison uses reachable sales and retained food, not the quote alone. On turn two, the food source has 44 workers, a strongest relative gain of about 1.36 and a departure rate of 13.6%; five departures commit and 38 workers are held back. On turn three, the rate reaches 25%, permitting nine departures. By turn 10, farm adults have fallen to 22, while furniture has 29.

Opening stocks and foraging conceal the strain. There is no underfeeding through turn 11. Wealth also increases appetite: by turn 10, most adults desire eight or nine food units, compared with a normal four-unit adult calorie requirement. Actual intake that turn is 656 units against an effective requirement of about 308. Surplus intake goes into modeled body reserves; it does not protect a different household from later hunger.

**Turns 11–30: food reserves thin, households diverge, and the sectoral shift overshoots.** First underfeeding appears on turn 12. Farm employment bottoms at 11 on turn 18; underfeeding peaks at 23 residents on turn 19. At turn 20, 87 residents have only 24 units left in household food stocks after consumption. The observed post-payroll auction has 353 bid units and zero offered units. The government has 62 units in the separate granary, but emergency release is disabled. Ordinary food aid delivers four units that turn.

Furniture reaches 43 workers by turn 30. Farm work has started recovering, but only to 17. Food's reference rises to 2.76 while furniture falls to 24.73. Prices are beginning to change the incentive, but land rights, source budgets, household hunger and the availability of funded jobs determine who can actually move.

**Turns 31–40: labor returns to farming, but the original company fails.** Food workers rise from 17 at turn 30 to 40 at turn 40. Across the first 60 turns, there are 39 recorded food-to-furniture transitions and 31 furniture-to-food transitions, plus additional entries to farming from wood and adulthood. These are transitions, not unique people.

The original firm loses most of its staff early, recovers four workers around turns 18–21, and then spends down its capital. Its wage rises from 2.5 to 40.37 at turn 20 and 57.68 at turn 30. Cash falls from 2,500 initially to 449.66 at turn 30 and 8.33 at turn 33. It dissolves on turn 34.

Before dissolution it produces only 62 furniture units and collects about 1,423.80 Crowns in sales, against 2,566.58 in wages, 360 in machinery repairs, and other operating costs. It also pays approximately 710.78 in owner salary and 252.23 in dividends. These figures describe its actual cash flows, not a counterfactual claim that any one payment caused failure. Strikes and pollution-related refusal to work accompany weak production. The company can have employees on the books and produce nothing.

The first recorded starvation deaths occur on turn 38. A recovery in the number of farmers does not instantly repair depleted body reserves or guarantee food to every worker.

**Turns 41–60: the workforce recovers more than the food system.** Farm adults reach 48, but grain output on turn 60 is only 17 units. Foraging supplies another 332. Actual meals total 351 units, close to the region's effective requirement that turn; four survivors remain underfed. In the ten-turn period 51–60, farm output is only 156 units, versus 394 in turns 41–50. Seasonality, illness, hunger, work allocated to foraging, inventories and pollution-related withholding all matter. Headcount is not a harvest guarantee.

## Food access and distribution

Over turns 1–60, farms produce 2,067 food units and foraging supplies 17,720: almost 90% of this new food comes from foraging. The economy is heavily dependent on subsistence access rather than a productive commercial grain market.

Total recorded intake is 21,270 units versus approximately 20,639 units of effective metabolic need. That cumulative surplus coexists with starvation because food is consumed by different people at different times. Earlier wealthy households eat more; later workers without grain, field access or commons time cannot eat money.

By turn 60, the separate granary contains 103 units, while ordinary government food inventory is zero and the charity has no food. Ordinary public aid has delivered 167 units over 60 turns. Emergency release never activates in this variant. The granary could cover some immediate deficits, but 103 units cannot replace the entire region's ongoing food requirement.

Two individual cases reveal different constraints:

- **Ironworker 64:** At turn 37, his current wage return is 1.5, while the feasible farming livelihood score is about 73.11. This includes food utility and is not a promised cash wage. Iron has reached its protected minimum of four, so he cannot use a voluntary departure. He dies on turn 38 after eating nothing that turn. The minimum is working as specified, with a real cost to workers in a protected occupation.
- **Ore worker 77:** He has no usable field right, so farming is not feasible even as food becomes valuable. On turn 47 he has 97.17 Crowns and eats one food unit, or 500 modeled calories, against an effective need of about 1,362. He dies with depleted body reserves. Cash alone does not guarantee an offered meal or a field to cultivate.

A later ironworker, 15, dies with 219.70 Crowns and no food. His late-career situation also includes company ownership, which excludes him from ordinary non-owner career decisions. The old blanket cash gate has been removed; other eligibility and access constraints remain.

## Industry, finance and prices

The region has 29 surviving corporate entities at turn 60 but only two wage-employed residents, both in iron. Incorporation is a poor proxy for an operating factory. Many company entities have no workforce.

The bank's outstanding loans rise from zero to about 7,411 at turn 40 and end at 6,895. Deposits end at 4,974, while bank capital falls from 2,000 to 1,791. The bank remains unfrozen. Credit supports transactions and firms while repayment, distress and writeoffs proceed; it does not create physical food or iron.

Household cash rises from 19,633 to 23,329.77, with another 4,076.77 in household deposits at turn 60. These nominal balances do not indicate improved food security. Food's reference price has risen more than seventeenfold. Furniture falls from 25 to 9.53, so its quoted purchasing power in food falls from 25 units per furniture unit to about 0.55. Wood remains at its old one-Crown floor. Iron, ore and coal references reach the existing 50-Crown ceiling.

Reference-valued production peaks at about 2,083.71 on turn 18 and is 912.75 at turn 60. This is the simulation's nominal production-value series, not real GDP or a welfare measure.

## Technology and physical bottlenecks

No steam installation is commissioned. Capability remains at XP 1, commercial maturity remains zero, and public engineering, private engineering and installation spending remain zero. There is no operating steam work to generate refinement.

The original company considers installing the prototype. At turn 20, the recorded quote is 800 Crowns, with an estimated gain of 12.28 per turn and a payback of about 65 turns. The immature design requires five units each of wood, iron and coal. Wood is plentiful, but region-wide iron is only three units at the end of turn 20 and often zero nearby. The adoption record reports `construction_supplies_unavailable`. Other early decisions report no operating workforce; later the company cannot sustain operations at all.

Knowledge still advances: Bloomery Iron Smelting and Standardized Guild Workshops are discovered at turn 29; Pottery Wheels & Controlled-Draft Kilns at turn 35. Discovery does not itself put the corresponding installation into production. The expanded steam productivity scope therefore never produces a steam-driven food boost in this run.

## Environment, health and politics

Soil is not collapsing: fertility rises from 1.0 to its rotation cap of 1.25, while nutrition density remains 1.0. Industrial pollution is much more consequential. Air pollution peaks at 54.10 and water pollution at 55.25, both on turn 22. They remain elevated at 33.78 and 37.80 respectively on turn 60.

The disease caseload rises to 110 simultaneous recorded conditions at turn 60, including 50 waterborne, 41 respiratory and 19 malnutrition conditions. Individuals can have multiple conditions; this is not 110 distinct patients. The untreated-condition count is 105. Private medical payments total 14,680 Crowns over 60 turns; recorded public medical spending is zero. Pollution-related unrest reports 49 participants at turn 60 and can directly withhold production.

The country starts and remains an autocracy. Legitimacy falls from 0.6 to zero by turn 20 and resets to 0.3 on turn 21. Forty successful-coup treasury-seizure entries occur during turns 21–60, transferring 1,541.62 Crowns of local public money to the coup leader. The post-coup baseline of 0.3 is still below the coup eligibility threshold of 0.4, which is consistent with the repeated-coup loop rather than institutional recovery.

The municipal treasury ends at zero while the national treasury grows to 10,989.53 through its tax receipts. There is no autonomous national AI in this scenario to turn that national balance into an expanded relief or engineering program.

## Population and mortality accounting caveat

The engine reports 75 → 90 residents, 33 births and 23 deaths: 11 starvation, seven age/health, five disease. Those figures do not form a clean biological population account.

Five dissolved company entities—79, 107, 119, 125 and 126—are reclassified as noncorporate people. Three subsequently appear as starvation deaths: 107 at turn 50, 119 at turn 58 and 126 at turn 59. Two remain in the reported resident population at turn 60. Their owners are separate agents, so these are entity-conversion artifacts.

Separating those entities leaves 88 surviving original/born human agents and 20 human-agent deaths, including eight starvation deaths. The exact reported identity is `75 + 33 births + 5 company-to-person entries − 23 recorded deaths = 90 residents`. Balanced currency audits do not detect this identity/accounting problem.

## What this run establishes

The career rule prevents a complete farm exodus and permits a substantial return when food becomes more attractive. It also reveals the costs of a hard profession floor, land-access constraints and owner eligibility. It does not make agricultural output, household food access, public relief, industrial inputs or political institutions automatically recover. The most important remaining problems in this run are those concrete mechanisms, together with the company/person identity artifact and repeated-coup feedback.
