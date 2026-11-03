# Slower soil loss and expanded production technology — 2026-10-29

Negative net soil-fertility changes now advance at 0.1 times the previous rate. Positive recovery keeps its existing speed and bounds. The ecological trace uses a new replayable v2 formula; old v1 evidence remains replayable. Attributed production depletion estimates use the same slowdown factor.

Steam applications now cover all production goods through installed machinery, with a maximum +50% output at tier 4. Tier 1 gives +25.625%, tier 2 +33.75%, and tier 3 +41.875%. Ownership, construction costs, actual usage and paid upgrades remain part of deployment. Legacy steam installations acquire the broad application list while retaining their installed generation. Imported-only foreign luxuries do not become domestically manufacturable; government and none are not productive goods.

The catalog grew from 29 to 45 technologies. Sixteen new technologies use the ordinary discovery, prototype, engineering, construction, operation and retrofit mechanisms. Existing steam looms now target cloth/fine textiles instead of furniture, and coke-fired smelting targets iron instead of wood. Watermills, freight infrastructure, electrification and process automation have explicit productive applications. Every one of the 17 domestic production professions has a sector-specific productivity path in addition to general-purpose machinery.

Agricultural experience now includes fiber/cash crops and wool. Manufacturing experience includes extraction, metallurgy, ceramics, textiles, distilling and crop processing. Transport output also contributes civil-engineering experience. Existing food/wood/furniture coefficients are retained. The displayed percentages are gameplay calibration, not measured historical estimates.

## Profession coverage

| Profession / commodity | Specific production technologies |
|---|---|
| food | Four-Field Crop Rotation; Fluvial Watermills & Gristmills; Synthetic Chemical Pesticides; Haber-Bosch Synthetic Fertilizers; Seed Drills & Row Cultivation; Tractors & Crop-Specific Harvesters |
| wood | Bloomery Iron Smelting; Fluvial Watermills & Gristmills; Chainsaws, Cable Logging & Skidders |
| furniture | Standardized Guild Workshops; Precision Lathes, Planers & Interchangeable Parts |
| transport | Caravel Galleons & Deep Harbors; Turnpike Trusts & Macadamized Roads; Contour Barge Canals & Pound Locks; Petroleum Refining & Diesel |
| wool | Selective Sheep Breeding & Flock Husbandry; Mechanical Sheep Shearing |
| cloth | Fly Shuttle & Mechanized Wool Carding; Mechanized Steam Loom Mills; Jacquard Pattern Weaving |
| nitrates | Gunpowder Rock Blasting; Steam Mine Pumps & Winding Engines; Powered Drills, Cutters & Mine Conveyors |
| cotton | Tractors & Crop-Specific Harvesters; Roller & Saw Cotton Gins |
| iron ore | Gunpowder Rock Blasting; Steam Mine Pumps & Winding Engines; Powered Drills, Cutters & Mine Conveyors |
| iron | Bloomery Iron Smelting; Coal Coking & Blast Furnaces; Bessemer Structural Steel & Rail; Precision Lathes, Planers & Interchangeable Parts |
| coal | Gunpowder Rock Blasting; Steam Mine Pumps & Winding Engines; Powered Drills, Cutters & Mine Conveyors |
| tobacco | Tractors & Crop-Specific Harvesters; Controlled Tobacco Curing & Leaf Handling |
| sugar | Tractors & Crop-Specific Harvesters; Roller Sugar Mills & Juice Processing |
| tea | Tractors & Crop-Specific Harvesters; Mechanical Tea Rolling & Drying |
| fine textiles | Fly Shuttle & Mechanized Wool Carding; Mechanized Steam Loom Mills; Jacquard Pattern Weaving |
| porcelain | Pottery Wheels & Controlled-Draft Kilns; Continuous Ceramic Kilns & Process Control |
| rum | Continuous Column Distillation |

## Historical/engineering references

These primary sources establish the real production methods represented by the technology families; they do not establish the chosen game multipliers.

- [steam](https://collection.sciencemuseumgroup.org.uk/objects/co50985)
- [farms](https://www.fao.org/interactive/agricultural-mechanization/en/)
- [breeding](https://www.fao.org/animal-genetics/background/why-is-ag-important/en/)
- [shearing](https://www.worksafe.govt.nz/topic-and-industry/agriculture/working-with-animals/working-with-sheep/safe-sheep-shearing-gpg/)
- [distilling](https://www.scotchwhiskyexperience.co.uk/about/about-whisky/whisky-making/)
- [forestry](https://www.iso.org/cms/%20render/live/en/sites/isoorg/contents/data/standard/05/08/50880.html)
- [mining](https://www.cdc.gov/niosh/mining/topics/machinery-struck-by-injuries.html)
- [industry](https://www.energy.gov/cmei/ito/industrial-efficiency-technologies)
- [cotton](https://www.ars.usda.gov/southeast-area/stoneville-ms/cotton-ginning-research/docs/what-is-a-cotton-gin/)
- [weaving](https://www.si.edu/spotlight/punch-cards)
- [pottery](https://collection.sciencemuseumgroup.org.uk/objects/co24090)
- [sugar](https://www.cirad.fr/en/our-activities-our-impact/tropical-value-chains/sugarcane/plant-and-uses)
- [tea](https://agritech.tnau.ac.in/postharvest/pht_plantationcrop_tea.html)
- [tobacco](https://craven.ces.ncsu.edu/flue-cured-tobacco-curing-practices/)

## Repeat campaign comparison

All cases retain the original seed 4243, 100 turns, opening endowments, fixed-wage owner policy and absence of general sovereign AI. These runs combine the slower soil rule, broad steam applications and expanded catalog/learning; differences cannot be attributed to steam alone. The original reports remain alongside the new files.

| Case | Fertility: original → revised | Recorded food output at turn 100 | Food price at turn 100 | Residents at turn 100 |
|---|---:|---:|---:|---:|
| commercial | 0.20 → 1.05 | 13 → 58 | 32.65 → 26.21 | 104 → 104 |
| public | 0.20 → 1.12 | 14 → 63 | 33.31 → 27.77 | 71 → 104 |
| low demand | 1.25 → 1.25 | 30 → 30 | 21.35 → 21.35 | 35 → 35 |
| control | 0.20 → 1.10 | 13 → 59 | 44.77 → 34.00 | 55 → 68 |

The three larger cases no longer exhaust soil to its 0.20 floor by turn 100. Their recorded food output is more than four times the original final sample. This is not a complete welfare improvement: hunger and workforce deaths persist, and the commercial case has more hungry residents at the final sample. Fixed wages, health, unrest and distribution remain separate constraints.

Broad steam applicability did not cause private farm adoption in these runs: the paid steam investments were still in furniture firms. A separate regional-pilot experiment commissions a public steam installation with real treasury funds, inputs and construction workers so that the new application scope actually benefits other producers.

### Paid regional steam pilot

The additional commercial-strategy run used `--public-steam-pilot`. Its regional
installation cost the treasury 800 and consumed five units each of wood, iron
and coal through normal construction. It completed successfully and benefited
all applicable regional producers. Private installations remained separately
owned and funded.

At turn 100, this run had soil fertility 1.026, recorded food output 65, food
price 30.74, 79 resident agents and five hungry residents. Steam capability was
51.43 (tier 2), and generation-1 manufacturing maturity reached 100%. The run
reported zero currency-audit violations and its independent diagnostic replay
matched its acceptance data. This demonstrates broad productive use and rapid
manufacturing learning, not a cure for the fixed-wage, health or political
problems: the original factory still lost its workforce and repeated coups
continued. Its trajectory also differs from the private-adoption case, so a
single final food-price or hunger comparison is not an isolated causal estimate.

Saved evidence:
[acceptance](engineering_regional_steam_pilot_20261029.json) and
[diagnostics](engineering_regional_steam_pilot_20261029_diagnostics.json).

```sh
venv/bin/python scripts/audit_engineering_campaigns.py --variant commercial --public-steam-pilot --output /tmp/regional-steam.json
venv/bin/python scripts/inspect_engineering_campaigns.py --variant commercial --public-steam-pilot --baseline /tmp/regional-steam.json --output /tmp/regional-steam-diagnostics.json
```

Validation: 124 focused/regression tests passed, including all 17 actual production paths, ownership isolation, legacy steam application, acyclic prerequisites, sector discovery experience, exact soil timing and trace replay. Four checkpoint tests passed (the source-signature case was rerun after editing ceased). Desktop/mobile browser checks verify the long productivity list and existing program controls. Each revised four-case diagnostic replay matches its independently saved acceptance snapshots.
