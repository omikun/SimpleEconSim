# Food security recovery after the 50-turn mortality audit

## Evidence and objective

The seed-777 default three-nation run recorded 1,000 deaths, including 974 from
starvation. Food producers fell from 644 on turn 1 to 120 on turn 5. The labor
mobility scheduler compared recipe price times output, so an unsold $100 imported
luxury looked better than farming. Later, large household food stocks coexisted
with hunger. Existing public purchases were capped at 16 food units per tile and
aid arrived after that turn's death assessment. No default nation had an AI.

The objective is a recoverable food crisis whose response consumes actual goods
and money. Food security must constrain, rather than erase, the game's choice
between export growth, labor control, and citizens' livelihoods.

## Implementation sequence

1. **Repair independent work choices.** Rank only sectors with a reachable
   local market and usable inputs by realized sales per producer. Value food
   retained for one's own meal. Treat foreign luxuries as imports, not a free
   domestic occupation. Preserve acceptance of funded wage offers. Record
   career switches and rejected candidates in the compact trace.
   Calibrate the usual shared commons right to provide a full meal when intact
   and require a funded wage offer to replace the food the worker gives up.
2. **Repair the food entitlement path.** A grower reserves at least the food
   needed for the next meal, while retaining the option to sell surplus and
   buy food when short. Government and charity purchases respect that reserve.
   Move existing conserved public food to eligible residents before they eat
   and before mortality. Emergency aid can cover the actual meal gap, subject
   to inventory; ordinary aid keeps its existing limits. If a local treasury
   cannot buy enough, levy at most one quarter of a holder's surplus above the
   next meal. Record who gives and receives each unit and the grievance caused
   by compulsory collection.
3. **Add a nation food-security policy.** At the strategy boundary, forecast
   local calorie gaps from residents, accessible food, customary foraging,
   recent production,
   and prior deficits. Distinguish scarce supply from poor access. Set bounded
   local emergency procurement and meal relief, fund it by transfers from
   the sovereign treasury when available, and require three adequate harvests
   before permitting enclosure. Allow employed people who are repeatedly
   hungry to leave for usable commons, retaining any lawful quit penalty.
   Preserve player control: attach this AI only to
   non-player nations in the default world; standalone headless runs can opt
   into autonomous control of all nations.
   New children inherit usable household rights. Provinces can send taxed
   surplus grain to hungry districts with a travel delay and paid local
   haulers; dispatch capacity and cash bound the response.
4. **Make the response inspectable.** Trace each tile's diagnosis, funding,
   procurement, meal transfers, and the nation AI's considered decisions.
   Surface the live diagnosis and response in the existing nation projection.
5. **Validate.** Use focused tests for meal timing and conservation, reserve
   logic, market-based career choice, and AI budgets. Re-run the same seeded
   default game, verify its compact trace, and compare deaths, food producers,
   and resident calorie intake against the original audit. Keep results for
   other seeds as tuning evidence rather than claiming universal balance.

## Scope and balance guardrails

- Food and cash move from named holders. No free grain, instant cross-tile
  transfers, or uncosted relief. Provincial shipments arrive after at least
  one turn and cost haulage wages.
- A crop producer may still choose a credible, better-paid job. The fix removes
  fictitious returns, not the economic pressure to work for wages.
- A nation can prioritize war or capital spending, but the AI records the
  expected food cost and suppresses discretionary exploitation when deaths
  are imminent.
- The player may choose a harsher policy. The autonomous emergency response
  runs for rival nations; private surplus levies carry a visible political cost.

## Implementation and validation

The implementation now covers every step above. The compact trace includes
food diagnoses, nation choices, paid purchases, grain levies, delayed provincial
shipments, meal transfers, customary inheritance, and exits from hungry jobs.
The web nation comparison shows underfed residents, emergency districts,
protected commons, food delivered, and grain levied; its AI explanation lists
the district diagnoses and funding.

In the original seed-777, 50-turn default-world audit, 1,000 residents died,
including 974 from starvation. In a repeated 50-turn run with the changes,
the same world seeds and autonomous control of all three nations, 45 residents
died, including 1 from starvation; the currency audit had no violations.
The run fixed `PYTHONHASHSEED` for repeatability. The original audit did not
fix that setting, so this is a benchmark comparison rather than a controlled
paired estimate. It also had no default nation AI, while the new run enables
all three; the number measures the complete policy and mechanic change, not
any one intervention in isolation. The 78 focused and integration tests pass.
A traced 10-turn run decoded and verified 1,528,548 rows across 10 checkpoints,
including food diagnoses, purchases, levies, career decisions, inherited
rights, job exits, and nation decisions.

Turn 50 still had 134 underfed residents. Average unrest was above 9 in all
three nations, reflecting the political cost of repeated emergency measures.
Those remain balance targets: the reforms prevent mass mortality, while a
larger population can still outgrow local food access and force a choice
between land, wages, transport, and public relief.
