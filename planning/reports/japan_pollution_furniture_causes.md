# Japan: pollution and furniture causes

Scope: saved seed-4242 combined twenty-turn run, trace `3a5a39c221d04258b9d7653ac43c02c3-1`. This is trace analysis and inspection of the current implementation, not a new intervention experiment.

## Pollution

Tokyo (c10) dominates the national air average. Its industrial-corporation count is zero through turn 8, four at turn 9, five at turn 10, and ten from turn 17 through turn 20. The ecology rule counts wood/furniture corporations, regardless of actual production or labor activity. Each adds 1.8 air-index units per turn; the accumulated index retains 85% of the previous turn. No coal intensifier or scrubber was active. At turn 20: 82.2743 × 0.85 + 18 = 87.9331. Air update event: `3a5a39c221d04258b9d7653ac43c02c3-1:849969`.

This is an important realism limitation: incorporation can increase emissions while output stagnates. Only one Japanese corporate furniture-production event appears in the entire run (one unit at turn 14); ordinary artisans produce most furniture. The number of corporations is not evidence of a production boom.

Tokyo's water pollution reaches the cap of 100 by turn 15. At turn 20, its own new emissions are 2.98125 urban waste plus 12 industrial waste, with zero fertilizer runoff. It has no sewer, filtration, or clean-water flag. Its river graph has no downstream outlet. It receives upstream pollution from Japanese c38 and c6 and U.S. c35. At turn 20 their modeled transfers are 5.4122, 1.6018, and 7.0271 index units respectively; the received stock increments are zero at that point because Tokyo is already capped. These figures are pollution-index transfers, not physical pollutant mass. Water update event: `3a5a39c221d04258b9d7653ac43c02c3-1:849970`.

Current mitigation mechanisms:

- Smoke scrubber: reduces new air emissions 70%, but converts part of the captured amount to soil pollution. With ten counted corporations, ongoing emissions fall from 18 to 5.4 and the uncapped steady-state air index is 36. Thus a scrubber reverses the increase from 88 but does not eliminate the problem.
- Water filtration: multiplies locally generated water emissions by 0.3. It does not directly treat the incoming upstream term or remove a fraction of existing stock. Upstream controls are therefore necessary for Tokyo.
- Trunk sewer: multiplies local emissions by 0.3 and changes downstream transport. Its exact code should be used rather than interpreting the building description as guaranteed disease eradication.
- Natural dispersion removes 15% of air and 12% of water stock per ecology update, before ongoing sources and river transfers. Reducing emissions below removal allows recovery; the water result depends on the whole river network and update ordering.

The national AI's observed public-works decision selects a Tokyo road at turn 1, then records `food_emergency` as the public-works exclusion on turns 2–20. The inspected construction selector chooses roads and canals, not sewers, filtration, scrubbers or sawmills. Mitigation recipes exist, but there is no pollution-responsive choice in this selector. At turn 20 Japan's public cash/deposit total is about 238, below listed scrubber (300), filtration (450), and sewer (1,000) costs. Materials and labor also have to be supplied. The clean_water_act flag is read by ecology, but a usable policy setter was not found in the inspected Python sources.

## Furniture

| Turn | Japan furniture production | Furniture market sales | Japan wood production |
|---|---:|---:|---:|
| 1 | 54 | 54 | 168 |
| 2 | 51 | 56 | 150 |
| 3 | 20 | 30 | 168 |
| 4 | 2 | 12 | 174 |
| 5 | 5 | 16 | 172 |
| 10 | 3 | 9 | 98 |
| 15 | 3 | 5 | 108 |
| 20 | 5 | 5 | 150 |

The collapse precedes Tokyo's industrial air emissions, which start at turn 9. It is primarily an input-supply problem. An initial Tokyo artisan event starts with 10 wood units, consumes two and produces one furniture unit (event `3a5a39c221d04258b9d7653ac43c02c3-1:12325`). By turn 4 there are explicit missing-wood production failures. Japan records 904 missing-input furniture-production failures across the run, compared with 29 corporate furniture stops explicitly attributed to withheld/revolting workers. These are event counts, not estimates of lost output, and corporate input-shortage early returns have incomplete zero-event coverage.

Japan produces 2,488 wood units over twenty turns. Recorded household nonfood wood consumption is 2,495: 1,396 stockpile drawdown and 1,099 wealth-multiplier consumption. This already uses roughly the entire new timber output before furniture and construction inputs. Initial stocks can temporarily cover the excess; repeated market sales are not new timber production. Wood imports remain zero.

There is a specific input-protection inconsistency: the ordinary stockpile drawdown exempts wood-input producers, but wealth-multiplier consumption does not. Furniture-occupation agents lose 145 wood units to household consumption over the run. At turn 10, Tokyo artisan 966 consumes its last one wood unit through this wealth rule despite `input_good=wood` (event `3a5a39c221d04258b9d7653ac43c02c3-1:375114`). This is a later aggravating mechanism, not an explanation of the entire initial collapse.

Demand persists: 5,335 funded furniture bid units versus 298 sold over the run, with the national mean reference price reaching 50 at turn 20. Bids can repeat across turns, so they are not unique household needs. Sales temporarily exceed production as existing goods circulate. No furniture import flow restores supply.

## Recommended sequence, not yet implemented or tested

1. Base industrial emissions on actual production/activity, with explicit residual emissions if warranted, instead of corporation count alone.
2. Protect a bounded next-production-batch input reserve from discretionary household consumption.
3. Add environmental health and input-supply investment candidates to national AI decisions; avoid excluding every such project throughout a prolonged food emergency.
4. Target Tokyo and upstream districts for controls together. Budget cash, construction inputs and operational needs; account for scrubber sludge rather than shifting pollution invisibly.
5. Increase sustainable timber supply and establish funded acquisition/delivery. A sawmill exists; its intended timber bonus is 30%, subject to staffing and production integration. Furniture workshops help only after wood can reach producers.
6. Use matched runs to test output, input availability, household welfare, pollution in every affected medium/district, public finances and disease. The formulas above are explanatory calculations, not measured intervention outcomes.
