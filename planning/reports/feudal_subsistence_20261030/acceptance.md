# Seasonal tribute and landlord feeding — acceptance

Implemented the clarified instruction: collect feudal tribute once per
ten-turn agricultural cycle and tax each new harvest once. Stored reserves are
not repeatedly assessed. Landlords supply basic meals to hungry people residing
on their own estates before consumption and starvation mortality.

[Mechanism details](../../../docs/feudal_subsistence.md).

## Matched 60-turn results

The same abundance fixture was rerun in fresh processes, with its initial
population, professions, seed, productivity treatment, and policy settings
preserved. Spoilage remains absent. The changes to tribute and private relief
operate together; these comparisons do not isolate their individual effects.
Population and random-event paths differ after the new rules begin operating.

| Case | Final population, before → after | Final underfed, before → after | Mean underfed share in last 20 turns, before → after |
|---|---:|---:|---:|
| Seed 4243, higher farm yield | 304 → 282 | 45 → 18 | 12.23% → 2.43% |
| Seed 4243, no yield treatment | 231 → 245 | 57 → 29 | 34.04% → 12.22% |
| Seed 4242, higher farm yield | 281 → 254 | 31 → 16 | 9.87% → 5.94% |

In the higher-yield seed-4243 case, underfed person-turns fell from 907 to 210.
The remaining grain no longer concentrates in the original landlords' stocks:
they hold zero grain at the close of turn 60, versus 3,700 previously. Closing
grain elsewhere totals 848 units, compared with 4,125 total previously. The grain
reference quote is higher, 1.2814 versus 0.4956: improved nutrition did not depend
on preserving the old low-price/high-landlord-stock outcome. Prepared-food output
remains similar over the full run, 669 versus 673 units.

All three runs have zero currency-audit violations and reject negative goods
inventories. The simulation source fingerprint remained unchanged across runs:
`cf8b8b06a08abd899170371e2664770df8154242cd44501788a428d47200b59c`.

Final-source confirmation reproduces all three saved economic runs exactly
after a checkpoint-comparison repair, with source fingerprint
`523424bd1fc495b8e49a789025008bba4dfc4e4b9bfad5e1082b1e10def4902e`.

## Directly observed tax and relief

Read-only observers reproduce each saved seed-4243 reference result exactly.
Collections occur on turns **7, 17, 27, 37, 47, and 57**. The higher-yield case
records 1,691 grain units collected as tribute and 1,343 units supplied through
566 landlord-to-resident food transfers. The control records 366 grain units
collected and 517 units of private estate relief. Relief can also use the
owner's initial stock or market purchases; it is not limited to tribute receipts.

In the higher-yield case, 18 residents are underfed at turn 60: 11 are estate
residents and 7 are outside the resolved estate-residence groups. Owners supplied
26 units that turn and have zero grain remaining after their own meals. This is
a finite-resource limit, rather than an unused landlord stock of thousands of
units. One underfed resident is a child under 14. The full run still records two
starvation deaths, so the new rule is not an unconditional survival guarantee.
The control records three starvation deaths. Comparable old death totals were
not captured by the earlier abundance archive.

## Validation and evidence

186 focused and regression tests pass, including receipt accumulation, once-per-
cycle collection, reserves excluded from the base, dependent food protection,
estate-specific residence, live consumption before mortality, limited grain,
prepared/public meal offsets, exact inventory transfers, replay, and unfinished
harvest assessments surviving save/restore. Broader checks cover nutrition,
charity, markets, technology, household transfers, inheritance, coercion, and
trace coverage. Four full server checkpoint tests and one native Egypt checkpoint
test also pass, for **191 passing tests** in total. These include fresh-process
continuation of the base world, labor-frontier and supply-rivalry scenarios.

The expanded traces exposed an existing comparison issue when scenarios were run
back-to-back: retained prior-world journal clocks interleaved with current-world
sequence ranks. Acceptance normalization now separates those independent clock
domains, preserving current-world order and ties, all economic values, and shared
references. A regression test verifies both equivalent trace gaps and detection
of changed event order or amounts. This repair does not change gameplay results.

- [Source and run manifest](manifest.json)
- [Final-source confirmation](manifest_final.json)
- [Higher-productivity seed 4243](higher_productivity_4243.json)
- [Control seed 4243](control_4243.json)
- [Higher-productivity seed 4242](higher_productivity_4242.json)
- [Higher-productivity collection/relief journal](higher_productivity_4243_diagnostics.json)
- [Control collection/relief journal](control_4243_diagnostics.json)
- [Previous benchmark](../abundance_acceptance_20261030.json)

This changes the feudal institutional mechanism; it does not establish long-run
equilibrium or remove hunger among every landless or underfunded household.
