# National outcomes across twenty turns

Scope: seed 4242, combined arm (all national AIs, independent artisan requests, domestic relief). This describes the saved run, not a new run of the subsequently changed code. Trace: `/Users/sli/Code/tmp/traces/3a5a39c221d04258b9d7653ac43c02c3-1.ctr`. Source commit before implementation: `8591bd80f485df22efbc699f869b4a4235e26cca`; implementation fingerprints are retained in the run JSON.

Comparisons below use the end of turn 1 and end of turn 20, not pre-game state. National membership in every recorded chart aggregation matches the initial ownership map. Currency amounts are local nominal units and cannot be compared as purchasing power across countries.

## Assessment

Food relief did not establish national stability. China and Japan suffered repeated successful local takeovers affecting their national regimes on turns 19–20. The United States avoided a successful takeover but experienced mobs, strikes, falling legitimacy, rising living costs and a shrinking public cash/deposit cushion. Furniture supply was severely constrained across all three nations; many other goods had no active production sector. Japan had the most severe recorded disease burden.

## National indicators

| Metric | China | Japan | United States |
|---|---:|---:|---:|
| Residents | 483 → 574 | 524 → 619 | 423 → 517 |
| Treasury cash + deposits | 1.25e+03 → 401 | 1.23e+03 → 238 | 1.15e+03 → 385 |
| Nominal output per turn | 2.1e+03 → 1.45e+03 | 2.43e+03 → 1.78e+03 | 1.71e+03 → 1.5e+03 |
| Cost-of-living basket | 11.2 → 18.6 | 11.2 → 18.6 | 11.2 → 18.8 |
| Legitimacy (0–1) | 0.578 → 0.000621 | 0.578 → 0.000468 | 0.578 → 0.259 |
| Mean protest energy | 3.14 → 8.69 | 3.08 → 9.23 | 3.25 → 9.42 |
| Mean commons access | 1 → 0.25 | 1 → 0.6 | 1 → 0.417 |
| Recorded strikers | 0 → 28 | 0 → 20 | 0 → 6 |
| Untreated disease cases | 0 → 35 | 0 → 212 | 0 → 49 |
| Mean air pollution | 0 → 3.22 | 0 → 22.8 | 0 → 15.3 |
| Mean water pollution | 2.11 → 18.5 | 1.66 → 25.1 | 2.25 → 21.4 |
| Underfed share of resident-turns | 1.93% | 4.95% | 0.34% |
| Underfed residents at turn 20 | 160/574 (27.9%) | 198/619 (32.0%) | 25/517 (4.8%) |
| Recorded deaths over 20 turns | 0 | 2 | 1 |

Treasury is gross cash plus deposits across government tiers, not net assets after debt. GDP is nominal and has strong within-run swings; the endpoints are not a real-growth estimate. National averages can hide local distress. Hunger here uses resident calorie deficits from the experiment, not the separate legacy hungry-count chart. Disease figures count cases, not necessarily distinct people.

## Every commodity

Each cell is **production / funded bid units / sold units**, summed across the twenty turns. Bids can recur for the same unsatisfied demand; sales can include existing stock and resale. These are market activity measures, not unique household needs or a material balance.

| Good | China | Japan | United States |
|---|---:|---:|---:|
| cloth | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| coal | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| cotton | 0 / 5110 / 646 | 0 / 6171 / 646 | 0 / 4717 / 152 |
| fine_textiles | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| food | 28895 / 19857 / 15109 | 26691 / 21495 / 14899 | 49123 / 19697 / 17649 |
| foreign_luxuries | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| furniture | 143 / 5886 / 205 | 214 / 5335 / 298 | 125 / 5459 / 186 |
| iron | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| iron_ore | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| nitrates | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| porcelain | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| rum | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| sugar | 0 / 3668 / 373 | 0 / 3403 / 277 | 0 / 2921 / 367 |
| tea | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| tobacco | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| wood | 2100 / 24182 / 4017 | 2488 / 26025 / 4964 | 1516 / 20432 / 2772 |
| wool | 24 / 1153 / 26 | 24 / 864 / 26 | 22 / 1585 / 22 |

Transport is accounted for separately as a service market; the general commodity panel records only 3 / 2 / 3 units of transport production respectively. Its separate market records contain 98 offered unit-turns, one bid unit and zero sales across the run; this service market barely operated. These records do not include all direct construction or relief-haulage payments. Its missing general-panel bid fields must not be interpreted as zero transport demand.

Furniture production fell from 41 to 3 units per turn in China, 54 to 5 in Japan, and 25 to 2 in the U.S. Missing-input production failures numbered 850, 904 and 475 respectively. Timber output persisted but was inadequate relative to bids; the earlier acquisition investigation found export traders losing to local buyers. Cotton and sugar traded despite no recorded new production, so this run does not demonstrate replenishing supply chains for them. The eleven entirely inactive goods are not evidence that demand was successfully satisfied. All recorded market import units were zero. One private route shipment departed at turn 20, carrying two wool units within Japan; food relief used a separate shipment mechanism.

## Politics, labor, construction and health

### China

Local unrest outcomes (district-turn counts): unrest: 46, protest: 18, calm: 4, mob: 10, takeover: 2.

Strike starts: 2.
- Turn 19, c50: successful takeover; resulting national regime democracy; reason `no_garrison_defense`; event `3a5a39c221d04258b9d7653ac43c02c3-1:791666`.
- Turn 20, c50: successful takeover; resulting national regime autocracy; reason `no_garrison_defense`; event `3a5a39c221d04258b9d7653ac43c02c3-1:840504`.
- Turn 3, c50: completed turnpike_road; event `3a5a39c221d04258b9d7653ac43c02c3-1:81273`.
- Turn 9, c50: completed barge_canal; event `3a5a39c221d04258b9d7653ac43c02c3-1:318561`.

Turn-20 disease counts: waterborne: 36, respiratory: 0, malnutrition: 10.

### Japan

Local unrest outcomes (district-turn counts): protest: 30, calm: 2, unrest: 46, mob: 14, compromise: 4, takeover: 4.

Strike starts: 17.
- Turn 19, c10: successful takeover; resulting national regime autocracy; reason `no_garrison_defense`; event `3a5a39c221d04258b9d7653ac43c02c3-1:800556`.
- Turn 19, c6: successful takeover; resulting national regime autocracy; reason `no_garrison_defense`; event `3a5a39c221d04258b9d7653ac43c02c3-1:804506`.
- Turn 20, c10: successful takeover; resulting national regime autocracy; reason `no_garrison_defense`; event `3a5a39c221d04258b9d7653ac43c02c3-1:850570`.
- Turn 20, c6: successful takeover; resulting national regime autocracy; reason `no_garrison_defense`; event `3a5a39c221d04258b9d7653ac43c02c3-1:854963`.
- Turn 4, c10: completed turnpike_road; event `3a5a39c221d04258b9d7653ac43c02c3-1:121471`.

Turn-20 disease counts: waterborne: 108, respiratory: 99, malnutrition: 32.

### United States

Local unrest outcomes (district-turn counts): unrest: 29, protest: 13, calm: 2, mob: 16.

Strike starts: 6.
- Turn 5, c59: completed turnpike_road; event `3a5a39c221d04258b9d7653ac43c02c3-1:160751`.
- Turn 11, c59: completed barge_canal; event `3a5a39c221d04258b9d7653ac43c02c3-1:402343`.

Turn-20 disease counts: waterborne: 56, respiratory: 8, malnutrition: 2.

## Causal interpretation and limitations

- The grievance records explicitly include rent/enclosure, inequality, hunger, levies, wages and labor resistance. At turn 20, rent/enclosure contributes 3.75 grievance points in Beijing and Washington; grain-levy pressure reaches 3 in several donor districts. Relief can therefore coexist with political costs. These are recorded model inputs, not independently estimated real-world causal effects.
- China changes to democracy after Beijing’s turn-19 takeover, attempts an election with no candidates, then changes back to autocracy after another takeover at turn 20. Japan records four successful takeovers across Tokyo (c10) and c6 at turns 19 and 20. Repeated takeovers in consecutive turns deserve a separate model review.
- Every successful takeover records zero garrison force. No military coup fired. The separate uprising-response mechanism records no_action for all sixty nation-turns; this does not mean that every policy mechanism was inactive.
- All three nations have zero military strength in diplomacy assessments. Relations between Japan and the U.S. reach -1, but the military advantage gate blocks ideological war. No national territorial membership changes were observed.
- The United States unlocks crop rotation at turn 17; the event declares a 1.25 food-production modifier, but does not by itself establish a measured 25% aggregate harvest gain.
- Population growth is not a welfare score. Endpoints use the living resident census; births, deaths and role changes have separate definitions.
- Financial solvency, debt service sustainability, real GDP, a validated unemployment rate, and causal attribution of the full disease increase are not established by this summary.
- Existing food and furniture stock-flow residuals remain. These results describe one seed and twenty turns and do not establish general resilience.
