# Egypt campaign balance audit

This is a seeded, 20-turn comparison of three decision paths through the same opening world. Run it with `venv/bin/python audit_egypt_political_economy.py output.json`. The audit records the treasury, Caisse principal, public and deliberately reserved private maize, hunger, tax arrears, land loss, migration, petitions, strikes, legitimacy, and unrest after each turn. The script resets both random streams before each path.

| Path | Pivotal decisions | Ending | Treasury | Caisse claim | Hungry households | Land loss | Legitimacy |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Protect households | Release rations, cut taxes, buy warehouse grain; concede, defer, then contest default | Successful repudiation | 75 | 420 | 171/663 (26%) | 0 | 43% |
| Pay creditors | Raise taxes twice; pay 200 on turns 6, 11, and 16 | Coercive extraction | 640 | 0 | 201/625 (32%) | 15 | 33% |
| Leave grain to market | Open private sales; pay all three instalments | Fiscal hardship | 213 | 0 | 218/599 (36%) | 2 | 44% |

All paths begin with 235 spendable treasury units, 600 in Caisse bonds, 440 public maize units, 20 units deliberately held in warehouses, and 138 underfed households out of 555. The low Nile and unequal food access still create cumulative harm in the paths that resolve debt. The creditor path ends cash rich because its higher taxes transfer more money from districts; it also has the most foreclosures and migrations. The market path preserves the public reserve but leaves the most households hungry. The relief path spends its reserve repeatedly after buying actual warehouse food, preserves tenure, and cannot keep paying the Caisse. Its 420-unit outstanding claim is the price of this route, not an erased debt.

The worst single-turn hunger count was 324, 326, and 311 respectively. By turn 20 the creditor path had 24.48 units of cultivator arrears, 225 petitioners, and 10 strikers; the market path had 5.93 arrears, 228 petitioners, and 30 strikers. Deliberately reserved private grain reached 260 and 285 units in the protection and creditor paths, while opening sales cleared the market path's reserve. Private food in the ending debrief includes ordinary household and owner pantries; the warehouse figure here measures only grain deliberately withheld from the auction.

Two further scripted routes prove that a protected-food ending is attainable through active policy: retaining grain, opening private sales, and using the late public release yields **relief and payment**; conceding half of the first instalment yields **creditor settlement**. Two early cultivator tax cuts made the latter route short of cash at the last payment, so that test route no longer cuts taxes. A full-campaign test covers each of the 15 declared endings. The 20% final hunger threshold is unchanged. The results are seeded examples rather than a claim that every random seed or reasonable player path is balanced.

## Balance decisions

- Public stores cover one release of up to 110 next meals. The ration is physically reserved at the action and consumed exactly once on the next consumption step, when the ending measures hunger.
- Cadastral taxes send 25% of collected cash to Cairo and 75% to districts. Unpaid assessments can age into foreclosure, so high revenue has a visible household cost. A successful payment route needs receipts, while several tax cuts can make the final instalment unaffordable.
- Private warehouses start small and grow only by buying actual food from producers. Owners offer reserved grain as local prices approach their reservation or export price. Cairo can buy or seize those units, or let holders sell to households able to pay.
- Petitioners and strikers respond continuously to food deficit and arrears. A negotiated settlement lasts three turns; the same grievance is not automatically conceded again each turn. The Guided political card leads with unrest and legitimacy, while its details retain military and collective-action measures.

## Remaining work

The owner strategy is a single reservation-price rule, the path audit samples one seed, and most displaced cultivators only face a chance to find wage work through existing job changes. Future balance checks should vary the Nile shock and initial distribution, record whether each district action offers a distinct successful route, and model the inspection period beyond turn 20 if the campaign horizon is extended.
