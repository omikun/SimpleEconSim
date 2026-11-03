# Production, abundance, and new uses

The regional base economy now shares a demand system across food, heating,
clothing, furnishings, and luxury goods. Spoilage and storage losses are deferred.

## Household decisions

Each household submits one basket whose total maximum auction payments fit its
cash budget. Savings can fund that basket through a recorded bank withdrawal.
Meals, dependent children, working inputs, and workshop equipment take priority.
The remaining budget compares comfort and variety across goods using diminishing
marginal benefits and finite stock targets. Lower staple prices release spending
for other uses; lower cloth or furniture prices bring those goods within reach.
Raw ore and other industrial inputs have no invented direct household demand.

Recurring use and fractional durable wear create replacement demand. Production
inputs and workshop equipment are reserved from household use. Post-payroll food
purchases use the household's new cash rather than an earlier basket's limits.

## Production and processing

Successful productive work earns proficiency separately for each worker and good.
The practice multiplier is `1 + 0.6 * (1 - exp(-completed_work / 30))`: it starts at
one and approaches 1.6. Full inventories, missing inputs, strikes, and failed
production do not earn practice. Installed technologies remain a separate source
of productivity. Existing initial grain production is five units per successful
batch against an ordinary adult meal of four units; actual output also depends
on seasons, land access, work allocation, fertility, and institutions.

Prepared meals are the first new processing use. A workshop needs one unit of
owned furniture as equipment, physical grain inputs, and labor. Every unit of
grain becomes one meal unit with exactly the same calories. Better practice or
machinery raises throughput and the required grain together. Equipment remains
in owned inventory and is protected from household use and resale.

The processing engine accepts ordinary recipe input/output ratios and equipment
requirements, and is tested with nonfood cloth processing too. Existing wood to
furniture, wool to cloth, cloth to fine textiles, and sugar to spirits chains also
benefit from cheaper inputs and the common household demand system.

One independent workshop entrant per region per turn may respond to funded
orders. Entry checks equipment costs, working capital, meal costs, existing
stocks and capacity, and foregone sales in the person's current occupation. The
entrant changes occupation and receives an eight-turn trial before ordinary
career evaluation resumes; serious hunger permits earlier departure. Equipment
and inputs must actually be acquired. Firms can buy equipment through the same
auction. Existing employment and investment mechanisms handle firm growth.

Commercial investment forecasts require recent funded orders or settled sales.
A posted wool or luxury price alone does not establish profitable demand or
justify converting all food land. Consuming a luxury can yield prestige;
producing one for sale requires buyers. Pending capacity still dampens expected
prices through the existing transformation graph.

## Prices, population, and trade

Base-economy reference prices and idle prices can fall to the existing numerical
minimum of 0.1. Input costs guide investment and bids, rather than imposing a
guaranteed selling price. Distressed manufacturers may offer stock below its
recorded cost. Auction settlement still controls actual prices and cash flows.

Prepared meals count toward nutritional intake and meal-access checks. Existing
nutrition-dependent fertility, childhood, mortality, and household transfers
remain active. Population responses are delayed and need not be monotonic across
random seeds. Existing multi-good routes include prepared meals, with their
normal freight, currency, tariff, and capacity constraints.

`Region.abundance_enabled` defaults to true. Author-controlled economies using
`scenario_owner_policy` and wilderness tiles retain their prior rules. Existing
commodity IDs are unchanged; prepared food is appended to the enum. Save loading
extends old wallets and migrates old regional commodity tables while preserving
current checkpoint graph identities.

## Validation

Run the behavior and accounting tests with:

```sh
MPLCONFIGDIR=/private/tmp/abundance-mpl venv/bin/python -m unittest tests.test_abundance -q
```

Run each real-turn comparison in a fresh process, because the simulation owns
global registries:

```sh
MPLCONFIGDIR=/private/tmp/abundance-mpl venv/bin/python scripts/audit_abundance.py --seed 4243 --turns 60 --output /private/tmp/abundance-control.json
MPLCONFIGDIR=/private/tmp/abundance-mpl venv/bin/python scripts/audit_abundance.py --seed 4243 --turns 60 --productivity 2 --output /private/tmp/abundance-treatment.json
```

The treatment changes farm yield at turn 16 as an explicit experiment. It does
not inject purchases, processing output, births, or recurring income. The report
records prices, production, population, hunger, inventories, practice, workshop
entry, and cash-conservation violations. This is a mechanism acceptance check;
long-run balance, richer recipes, and future spoilage remain separate tuning work.
