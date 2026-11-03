# Why starvation persists in the engineering campaigns

Investigation date: 2026-10-29. Seed: 4243. Current expanded productivity and
slower soil degradation rules. This investigation changes no gameplay.

## Finding

The campaigns have both intermittent supply shortages and severe food-access
failures. More output helps, but food is held in private inventories and a public
granary, while market ordering can prevent even solvent hungry people from
buying a meal. The results should not be interpreted as a clean technology
balance test until the purchasing defect and fixture restrictions are addressed.

Three deterministic 100-turn replays were observed: commercial engineering,
commercial engineering with the regional public steam installation, and the
control. Every complete acceptance result matched its saved baseline exactly.
Observers capture submitted quantities, actual auction limits and receipts,
settled food transfers, daily calorie intake, ownership of stocks, public aid,
and each death before inheritance changes the victim's estate.

## How much food exists?

One food unit supplies 500 kcal. An ordinary adult needs four units before
starvation adaptation; children have age-dependent needs. Foraging is a major
food source and is recorded separately from the production chart.

| Entire 100-turn campaign | Commercial | Regional steam pilot | Control |
| --- | ---: | ---: | ---: |
| Farm production | 11,115 | 9,976 | 8,817 |
| Commons foraging | 30,348 | 29,212 | 27,576 |
| Combined new food | 41,463 | 39,188 | 36,393 |
| Effective minimum meal need, food equivalents | 35,661.9 | 33,347.3 | 31,401.9 |
| Baseline meal need before starvation adaptation | 35,863 | 33,525 | 31,596 |
| Actual civilian meal consumption | 42,161 | 39,761 | 37,079 |
| Turns aggregate consumption meets effective minimum | 88 | 93 | 94 |
| Starvation deaths | 8 | 6 | 7 |
| People with a calorie deficit on turn 100 | 22 | 5 | 4 |

Food units are daily-equivalent nutrition in the simulation, not tonnes or
literal calendar-day output. These campaigns have different population paths,
so their total outputs or death counts do not isolate the causal effect of
steam. Initial food stocks and public stocks also contribute to consumption.
Minimum meal need here is the sum of actual civilian meal assessments; it is
not a full accounting of every possible use of food.

In the commercial run, combined new supply exceeds effective minimum need by
about 16% over the campaign. Nevertheless, supply is below minimum need in 28
individual turns. Storage and distribution therefore matter even when the
campaign-wide sum is sufficient. Richer people also eat above their minimum,
and consumption above need is not automatically transferable to someone else.

On turn 49, the region consumes 421 units against 383.4 units of effective
minimum need, but 15 people have deficits and two factory workers die of
starvation. At the end of the turn, actor inventories still hold 1,457 units,
including 297 in nonfood corporations, and the granary holds another 116.
All 22 units sold in that turn's private food auction go to buyers who already
hold at least four units at auction entry. This is direct allocation evidence;
the campaign does not have an aggregate lack of food on that turn.

## 1. Oversized orders can prevent an affordable meal

The general household food bid starts from an affordable quantity and then
multiplies that quantity by the consumption multiplier. This can make the
submitted quantity unaffordable. The auction then caps the unit bid by
`cash / requested_quantity` instead of reducing the requested quantity.

On turn 65, worker 77 has 196.99 cash before trading and no food. The order asks
for 36 units, giving a maximum unit bid of 5.472. Every seller asks at least
8.058. The worker receives zero units and later dies of starvation, although
four units at the lowest ask cost only about 32.23. Competition could still
affect allocation after a correction, but this particular submitted order
cannot cross any seller's price at all.

The same defect appears for worker 76 on turn 17: cash 19.03, requested
quantity 35, unit bid 0.544, minimum seller ask 0.955, zero private purchases,
and a starvation death that turn. This is a mechanical purchasing defect,
not simply a low-wage economic outcome.

Sources: `micro/region_market.py:187` (quantity), `:356` (unit limit), `:606`
(price-priority clearing). See the replay's `auctions`, `orders`, and `meals`.

## 2. Stockpiling demand competes with meals

The general food purchase capacity uses the recipe inventory limit of the
buyer's output profession, rather than a food-specific household reserve.
Wealth multipliers expand that limit further. Nonfood firms use the same
household branch and multiply capacity by one plus their employee count.
Corporations do not eat meals.

The private auction sorts buyers by descending unit bid, with actor ID as the
tie-breaker. Hunger can raise a bid limit, but there is no distinct meal-first
order. A hungry person's low cash divided across their order can leave their
bid below a stocked household's bid. On turn 40, 50 of 53 auctioned units go
to buyers already holding at least four food units; worker 10 bids for four,
has 15.74 cash before the auction, and receives none.

In ordinary market selling, a nonfood producer's surplus food is excluded from
resale. Employees also offer none of their inventory. Food can therefore move
into inventories that do not offer it back when prices or hunger rise.
Emergency public procurement has a separate ability to reach surplus stocks,
but the emergency policy is off in these fixtures.

Commercial turn 100 ends with 398 food units in nonfood corporations; the
regional steam pilot ends with 530. These are private stocks, not public
reserves or food automatically available to households.

Sources: `micro/region_market.py:187`, `:230`, `:252`, `:606`.

## 3. Factory workers cannot reliably access their employer's food

Employed people cannot forage. The authored furniture firm keeps its opening
wage of 2.5 because `scenario_owner_policy=True` disables normal wage adjustment
and owner planning. On turn 49, one food unit is quoted at 4.27 before auction
premiums; an ordinary four-unit meal is already about 17.09 at that quote.

The company store supports scrip purchases. Its emergency credit path supplies
only one unit, only when the worker has under two food units and cash below
one food unit's price, among other conditions. There is no general cash
purchase path for employees to buy a whole meal from these firm stocks.

The original firm's four workers die of starvation on turns 49, 49, 55, and
58, while their employer holds 58, 58, 54, and 54 food units respectively.
It ends with 54 units, zero employees, and 3,473.29 cash.

Trading occurs before wages. Worker 10 on turn 49 has 3.84 cash at bidding,
below the 4.27 quote, so submits no bid. After payday and tax, cash is 6.24,
but trading has finished. This also puts cash above the company emergency
credit threshold. The worker eats nothing and dies that turn.

Another fixture issue: these directly attached workers retain `output=food`
despite working in a furniture factory. Emergency food borrowing excludes
food-output agents, so they are excluded from that route even though they
are not independently growing food. Changing that gate alone would not
resolve insufficient wages, auction competition, or one-unit loan sizing.

Sources: `micro/foraging.py:25`, `micro/region_labor.py:320`,
`micro/region/stepper.py:232`, `micro/region_finance.py:354`,
`micro/region_market.py:12`, `scripts/audit_engineering_campaigns.py:65`.

## 4. The public granary releases food by calendar, not distress

The granary can store 120 units. It normally releases at most four units,
only in seasonal phases 9, 0, and 1 of the ten-phase cycle. Its release does
not scale with population, current meal deficits, or starvation risk.

On commercial turn 49 it ends with 116 units and delivers four units into
public aid. On turns 58 and 65 it has 120 units but releases none, while
starvation deaths occur. On turn 100 it still has 112 units, while the sum
of individual calorie deficits is equivalent to 59.19 food units. Four
public aid units are delivered that turn.

Public aid does occur: 325 units over the commercial campaign, 222 in the
steam pilot, and 285 in the control. Ordinary aid gives one unit per selected
recipient and caps coverage. The emergency policy, which can cover larger
meal gaps and reach private surpluses, is disabled. Public stores are therefore
an allocation bottleneck, not proof that there is no welfare system.

Sources: `micro/region_production.py:638`, `:673`, `:801`,
`macro/government.py:837`.

## 5. Charity has limited procurement access and late delivery

Charity buys after the private auction and normally only from food producers
with stock above their own meal reserves. Its cash cannot purchase food
locked in a nonfood firm's inventory through this ordinary path. A small food
target also constrains purchases. Distribution gives one unit to roughly a
third of hungry survivors, then young people if food remains.

Charity distributes only 153 units across the entire commercial campaign.
On turn 49 it has about 632.25 in deposits and no food. On turn 100 deposits
are 805.43 and food stock is only 0.5 units. These observations do not imply
that funds are always immediately withdrawable, but they establish that
charity has not exhausted all nominal wealth while securing adequate meals.

Charity distribution also occurs after demographic consumption and mortality.
Food it gives survivors is available for a later meal; it cannot prevent an
earlier death in that same turn. Government food aid, in contrast, is delivered
before consumption and mortality.

Sources: `micro/region_market.py:2114`, `agents/charity.py:276`, `:334`,
`micro/region/stepper.py:375`, `:462`, `economy/econsim_live.py:109`.

## What the technology change does and does not establish

The earlier expanded-rules campaign increased turn-100 commercial farm output
from 13 to 58 units. That comparison includes slower soil loss and several
technology changes; it does not isolate steam's contribution.

Steam is now eligible to benefit food, but private installed machines still
benefit their owners. Both adopted steam installations in the commercial case
belong to furniture firms. Discovery or adding a catalog technology does not
automatically equip farms. The public regional steam pilot does cover farming,
yet still has six starvation deaths and ends with 530 food units in nonfood
firms. Output improvement does not bypass the access failures above.

There are real production constraints too: seasonality, available farm labor,
water rights, inventory limits, hunger reducing work, and pollution-associated
work withholding. Commercial independent food-output people fall from 44 at
opening to 27 on turn 40 before recovering later. Soil fertility remains 1.25
during the original workers' starvation deaths, so rapid soil collapse is not
the explanation for those deaths under the revised rules.

This is one isolated region with no traders or neighboring regions. There is
no evidence here for food being delayed on roads or exported abroad. National
coordinated relief is not running: the fixture has no nation AI and no
provinces. The national treasury's money is separate from local procurement;
the commercial treasury ends with 10,633.84 cash.

Sources: `economy/technology_adoption.py:39`, `micro/region_production.py:30`,
`:418`, `meso/food_logistics.py:46`, and the saved campaign diagnostics.

## Suggested next changes, not implemented here

1. Correct food-order affordability so a larger desired basket cannot make a
   person unable to buy an affordable smaller meal. Use a food-specific reserve
   target rather than the recipe limit of the buyer's profession.
2. Give corporate food procurement an explicit purpose and distribution path:
   contracted worker meals, a functioning store, or genuine trading inventory.
   Permit surplus resale; do not treat an immortal firm as a hungry household.
3. Let emergency granary release respond to actual meal deficits. Deliver
   charitable aid before consumption and mortality, and make procurement access
   and funding visible rather than assuming treasury cash feeds people.
4. Correct the fixture's employed-food-grower classification and restore
   economically responsive wages, or explicitly label the frozen-wage case as
   a stress test. Preserve the possibility of real low-wage hunger.
5. Rerun paired campaigns and show production, foraging, public/private stocks,
   prices, household meal affordability, unmet calories, and death causes
   separately. More output should not be the only measure of food security.

The first issue is a clear ordering defect. Price competition, private
ownership, wage outcomes, and welfare coverage also involve intended game
rules and policy choices. No counterfactual fix has been run in this report,
so it does not assign a number of preventable deaths to each proposed change.

## Reproduction and evidence

Use `scripts/inspect_engineering_food.py` in a fresh process per case. Example:

```sh
env MPLCONFIGDIR=/private/tmp/engineering-mpl venv/bin/python scripts/inspect_engineering_food.py \
  --variant commercial \
  --baseline planning/reports/engineering_commercial_expanded_20261029.json \
  --output /private/tmp/commercial-food.json.gz
```

For the regional pilot, add `--public-steam-pilot` and use its acceptance
baseline. For control, use `--variant control` and the control baseline.

Saved compressed JSON observations:

- `engineering_commercial_food_20261029.json.gz`
- `engineering_regional_steam_pilot_food_20261029.json.gz`
- `engineering_control_food_20261029.json.gz`

The `rows` summarize each turn; `auctions` preserve price limits and actual
receipts; `meals` preserve individual nutrition; `deaths` preserve food access
at death. Every file records `acceptance_matches=true`.
