# Egypt strategic-loop baseline and design cards

Run `MPLCONFIGDIR=/private/tmp/coc-mpl venv/bin/python audit_egypt_strategy_baseline.py output.json` to reproduce this snapshot of the current working tree. The four scripts use one seeded opening and UI-valid actions. They show reachable outcomes and pacing, not a balance guarantee across seeds or a human playtest.

| Path | Last action | Unused major-decision turns | Final underfed households | Treasury | Caisse claim | Ending |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Grain retention, sales, late release, payments | 19 | 13 | 314/527 | 139 | 0 | Fiscal hardship |
| Grain retention and payments | 16 | 14 | 391/513 | 143 | 0 | Fiscal hardship |
| Succession, default, naval defense, port/Cairo evacuation | 11 | 9 | 392/510 | 706 | 600 | Occupation |
| Same crisis, boycott, strike, insurgency, withdrawal offer | 13 | 6 | 419/505 | 707 | 600 | Nationalist victory |

All four begin with 235 treasury units and 138 underfed households. The payment-first path has only seven underfed households on turn 10 but 391 at the end; the late hunger rise needs a causal explanation in Guided mode and a strategic response. The occupation path has no new player choice after turn 11. "Unused" means no major action was taken, not that a turn had no simulation event. The late social cost is much larger than the civilian injury count, so the debrief must not let battlefield injuries crowd out household hunger.

## Food-security card — Nile repair

- **Place and action:** Repair a district's existing irrigation and storage channel in the Nile Delta or Upper Egypt. Select the district on the map and commit a small project before the first remittance. This is a repair, not a new 250-unit farm or granary.
- **Who pays and works:** Cairo transfers a bounded construction budget to local workers over two or three turns. Track the hired households, wages paid, and any stalled turn; no work or cash appears from an abstract progress meter.
- **Engine effect:** On completion, alter actual district food yield or retained grain through `region_production.py`/`region_logistics.py`. Follow the food into household consumption, public granaries, private warehouses, and exports. Upkeep must be paid for the effect to persist.
- **Opposition and response:** Owners may buy and reserve a share of the larger harvest when they have cash and a price incentive. Egypt can buy the held grain, retain exports, negotiate local access, or leave the market in place using the existing action budget.
- **Failure:** Missing labor or upkeep suspends work or the benefit. Increased production can coexist with hunger when access remains unequal. The map must show the repair and the food-access result separately.

## Fiscal-autonomy card — Egyptian revenue office

- **Place and action:** Staff a customs/revenue office tied to Alexandria's actual customs stream and Cairo's fiscal administration. The first milestone must be affordable before the second service window.
- **Who pays and works:** Cairo funds named local administrative staff; their wages leave the treasury and reach households. Collection must stay bounded by underlying trade/tax receipts.
- **Engine effect:** A staffed Egyptian office improves the retained Egyptian share only where Egypt holds the institution and no enforceable Caisse or occupation claim overrides it. Ledger entries show gross receipt, assigned/occupied portion, and Egyptian remainder.
- **Opposition and response:** The Caisse measures the recovered receipts and claim exposure, then accepts inspection, asks for revised terms, or pays to enforce the old claim. Egypt can negotiate, comply, or revoke under existing oversight rules.
- **Failure:** Unstaffed, occupied, or contractually subordinated offices cannot silently collect for Egypt. Stronger revenue extraction can worsen cultivator access; show incidence by district rather than labeling all revenue as a social gain.

## Sovereignty card — canal defense line

- **Place and action:** Prepare the Alexandria–Tel el Kebir line at a selected strategic site. Existing sites may share generated tiles; the project marks the site, not a fictional new province.
- **Who pays and works:** Cairo funds local labor and the paid garrison. Fort repairs consume real funds, and readiness decays if the garrison cannot be supplied.
- **Engine effect:** Completed works change the existing fort or trench strength used by the landing/battle calculation and the route's supply cost. They do not give Egypt a free fleet or automatically prevent an attack.
- **Opposition and response:** Britain compares the Caisse claim, route access, fleet coal, expedition cost, domestic pressure, and Egyptian force. It may bargain, change approach, blockade, attack, or withdraw; France chooses separately under its existing authorization and funding rules.
- **Failure:** Bombardment damages works, supply can fail, and civilians may be harmed even if the line holds. Egypt can repair, seek terms, or shift its defense with another major decision.

## Readiness issues before Phase 1

The shared `buildings.py` farm and granary recipes cost 250 each, exceeding the opening treasury. Its current material-procurement code deducts contractor cash without transferring a corresponding good from a seller, so directly using it would violate this scenario's conserved-transfer requirement. Use a narrow repair adapter with actual paid labor first; reconsider shared construction once its material trade is audited. The project system must also use the existing one-major-action guard and be visible in both UI modes.
