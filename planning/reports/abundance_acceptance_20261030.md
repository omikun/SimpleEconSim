# Abundance system acceptance — 2026-10-30

Implemented for the regional base economy, with spoilage deferred. See
[the mechanism guide](../../docs/abundance.md) and
[all acceptance observations](abundance_acceptance_20261030.json).

The shared household budget covers meals and dependents, working inputs,
equipment, and diminishing-benefit comfort and variety. Successful work earns
bounded proficiency. Prepared meals provide a new physical grain-processing
chain, with real equipment, labor, input purchases, and buyers. The same
processing engine also supports nonfood recipe ratios. Existing processing
chains and multi-good trade use the new demand signals.

Commercial forecasts now require funded orders or realized sales. This fixes a
failure exposed by the initial acceptance run: quoted wool prices alone caused
all farmland to become pasture before food productivity could develop. Producers
can sell distressed inventories below cost, and market references can fall
below the old starting-price and input-cost floors.

## Real-turn experiment

Five separate processes ran 60 actual turns each, starting with 70 residents.
The treatment doubles farm yield at turn 16; other behavior remains endogenous.
No purchases, processing output, births, or recurring income are injected.

| Seed / treatment | Mean food price, final 20 turns | Mean population, final 20 turns | Mean hungry residents, final 20 turns | Total prepared meals produced |
|---|---:|---:|---:|---:|
| 4243 / control | 0.9017 | 233.35 | 80.20 | 321 |
| 4243 / higher yield | 0.5520 | 267.85 | 33.25 | 673 |
| 4242 / control | 0.5954 | 263.60 | 36.85 | 749 |
| 4242 / higher yield | 0.5555 | 244.25 | 24.30 | 799 |
| 4244 / higher yield | 0.5560 | 280.15 | 36.50 | 656 |

Both paired seeds produce cheaper staples, more processing, and fewer hungry
residents under higher yield. Seed 4243 has roughly 39% cheaper food and twice as
much processing. Population responds differently across seeds; increased yield
does not mechanically force faster population growth. Every run reports zero
cash-conservation violations and rejects negative goods inventories.

## Verification

138 behavior and regression tests pass across household demand, production,
technology adoption, engineering, market settlement, international trade,
nutrition, dependent transfers, causal replay, capitalist investment, and trace
catalog coverage. Tests include a nonfood workshop, input/calorie conservation,
funded equipment orders, blocked-production practice, price saturation, savings
withdrawals, and old-wallet migration.

Checkpoint continuation is checked for the base server, labor-frontier and
supply-rivalry scenarios, plus native Egypt across a fresh process. Current saves
preserve lazy dictionaries and graph identities; old serialized agent wallets
extend for the appended commodity.

An additional geography suite reported two failing assertions: a coastal farmer
share of 0.7926 against an expected minimum of 0.8, and a shrubland biome at an
elevation where that test expects hills or mountains. Those terrain and initial
occupation rules were not changed in this implementation.

## Remaining tuning

This establishes the mechanism rather than long-run balance. The first new food
type is prepared meals; additional recipes can use the common processing engine.
Household spending weights, proficiency speed, startup amortization, storage
targets, and demographic outcomes remain balance parameters. Existing regional
inequality and food access can still produce hunger alongside aggregate stocks.
No spoilage, storage loss, transit loss, or waste sink was introduced.
