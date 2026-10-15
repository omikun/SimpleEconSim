# Corporate collective action: implementation and run evidence

Status: general bargaining and evidence slice implemented, 2026-10-14; broader coalition and constitutional outcomes remain planned. This generalizes the [railway strike design](railway_strikes_and_independence.md) to workers at **every corporation**. Railway work can be one important sector, but the rules use firm IDs, actual workers, output, inputs, transport, cash, food, and authority rather than a railway special case. The [earlier railway implementation plan](railway_strikes_implementation_plan.md) remains background; this document is the active plan.

## Game rule

Every living corporation can face collective demands. Workers vote, individually decide whether they can withhold labor, and may receive finite support from others. Withholding reduces that firm's *actual* productive labor. Downstream effects follow existing production, trade, tax, and military-supply paths. A firm can make a funded offer, maintain its position, seek replacements through normal hiring, or contract. Government can use only laws and personnel it actually controls.

Successful settlements improve workers' confidence and leave organizations in place. A fulfilled promise can reduce grievances. Broken promises and repression can increase support for broader political change where the responsible authority is identifiable. In a colonial jurisdiction, that political change may include federation or independence; in a sovereign country it can mean reform, elections, or a new governing coalition. A workplace victory never automatically creates independence.

## What is implemented now

1. `collective_action.py` holds a persistent organization per voting corporation, strike IDs, member and participant IDs, demands, organization O, confidence E, and settlement review data. The record lives on the region and survives pickle save/load.
2. `micro/region/stepper.py` calls the collective rules before production and logs the observed output change, actual cash payroll, and later food sufficiency. `labor_resistance.py` delegates strikes to this general rule while retaining sabotage/repair.
3. Other willing workers can transfer existing food or cash to participants. `transfer_support` provides an explicit conserved transfer and log event. Firm AI compares a limited lost-output forecast to affordable extra payroll, offers terms, and waits for two observed payrolls before scoring fulfillment.
4. Each event has a stable ID, turn, firm ID, strike ID, explanatory message, and numeric facts. `collective_report.py` exports the complete sequence to JSON Lines, with scenario market sales, input purchases, and policy records where available.
5. `sim_server/sim_server.py` exposes organization state and recent events per territory. The common labor scenario projection includes them. `client/web/static` is a symlink to `web_client`, so the served web UI uses the same files.
6. `collective_politics.py` applies distinct government incidents once to named residents. Only a scenario with an explicit `region.colonial_authority` receives independence preferences; sovereign domestic disputes retain organization without separatism. Armed strikebreaking and an observed reduction in actual corporate shifts emit incidents. Political coverage deduplicates people in multiple corporations. The agenda index is not an independence chance and changes no border.

The run-log format and replay commands are in [collective_run_log.md](collective_run_log.md).

## Phase A — Stabilize the general strike loop

- Verify that every corporation type can create an organization without making every employee a member. A person joins the organization by a recorded affirmative vote or later consent; a strike's participant list includes only people who actually withhold labor.
- Preserve employer and employee pointers. Evaluate participation after hiring and before production. Count withheld labor for a turn only if it was withheld during that turn's production. An accepted offer after the economy tick takes effect at the next turn.
- Separate worker choice, owner forecast, offer, agreement, payroll, and review events. Forecast output value is a decision input and never entered as a monetary loss.
- Test full run, no-strike run, low-food withdrawal, funded agreement, missed payroll, second strike after cooldown, dead/migrated worker, and pickle round trip. Check cash and goods audits.

**Gate:** the real production and payroll paths drive the outcome for a mill, a farm corporation, and one other sector. Repeat calls in one turn do not create a second vote, transfer, or settlement review. Commit.

## Phase B — Explainability and player control

- Export each full run with `collective_report.py --scenario labor-frontier-rivalry --seed 612 --turns 20 --output tmp/collective_run.jsonl`. Each JSON row identifies its source; record both forecast and observed outcome when they differ. Keep event ordering and IDs stable after save/load.
- Add scenario actions to support a specific organization from existing public food reserves, propose funded terms to the relevant firm, or refuse a petition. The same action handlers serve desktop and web and honor one major decision per turn. The player does not directly spend private firm cash.
- Keep the default UI short: active workers, food runway, affected production and sales, the next deadline, and two or three viable choices. Make the full event sequence inspectable per territory. Use clear reason text when an action is unavailable.
- Add a test that server serialization is JSON-safe and matches the desktop projection. Inspect the iPad-sized web view and desktop panel.

**Gate:** a new player can identify why a strike started, how participants survived, what the owner offered, what was actually paid, and why the conflict ended. Commit.

## Phase C — General economic propagation and owner strategy

- For any firm, let employee withholding change actual produced units. Let shortage reach dependent firms through their owned inventory and existing purchases. Log observed input inventory, delivered purchases, sales receipts, taxes, and orders not filled. Do not double-charge a lost-sale penalty. Goods remain with their owner until sold, consumed, or explicitly spoiled.
- Replace a one-turn owner cash threshold with a bounded forecast using cash runway, current paid sales, inventory buffers, expected extra payroll, and feasible normal hiring. Distinct owners may offer better wages, maintain current terms, close, or seek an existing government remedy. Only executable operations can be selected.
- Give donors and workers budget and livelihood choices. Mutual aid must not create food or money; public relief competes with other uses of the same reserves.
- Test input bottleneck vs stocked buffer vs alternate supplier, two firms bidding for workers, and a successful productive settlement vs coercion. Record costs and recipients.

**Gate:** strikes at different corporations have different economic reach because their output and customers differ; the UI explains the measured dependency. Commit.

## Phase D — Coalitions and political preference

- Create persistent links among actual organizations and other constituency groups. A worker can belong to overlapping groups but counts once in political coverage. Invitations and joint campaigns require organizer effort and consent.
- Track O and E for organizations and constitutional preferences for represented people separately. In sovereign states, include reform/representation options; in a jurisdiction with an explicit colonial authority, include reform within empire, federation/autonomy, and independence.
- Record accepted government commitments, actual delivery, breaches, coercive incidents, and attribution as distinct event IDs. Apply the design document's political-preference equation only once per incident and only to affected people. A private wage increase is not automatically a colonial reform.
- Show party/coalition composition, members, delivered promises, and support for alternatives. Use the mobilization index only to put proposals on an agenda, not as an independence probability.

**Gate:** honest reform can lower independence support while unions remain strong; a later breach can change preference; normal domestic strikes do not raise separatism. Commit.

## Phase E — Political resolution and playtesting

- A constitutional proposal names its sponsors, voters/delegates, territorial scope, deadline, and terms. Reform, federation, and independence require explicit votes and acceptance under the scenario's constitutional rules. Sovereignty changes only through an accepted settlement or the existing real conflict path.
- Use `Nation.transfer_tile` only after auditing currencies, governments, citizens, soldiers, claims, debts, contracts, and taxes. A new state has real institutions and liabilities. Employees and unions remain after a flag changes.
- Give government AI feasible responses with public budgets, security constraints, and uncertain forecasts. Different industries can act as chokepoints when their goods are necessary for consumers, tax revenue, or force supply; none gets automatic railway-like transport power.
- Balance with matched seeds and playtests. Compare protection, settlement, replacement, and coercion across money, food, sales, political support, and military supply. Keep at least two viable approaches and a route to recovery.

**Gate:** a strike can help build a later coalition, but cannot by itself decide sovereignty. Players can inspect the event sequence and understand who gained, who paid, and which promises were honored. Commit.

## Evidence and conservation rules for every phase

- Use stable firm/person/strike/event IDs. Retain original demands, payer, beneficiaries, signed date, review date, and delivered amounts. Do not overwrite historical facts with a newer offer.
- Preserve one authoritative cash and goods account for every actor. A support event names its donor and recipient. Scrip counts as fulfilled real wages only when it buys delivered goods at a measured value; a cash promise requires cash paid.
- Count production and sales only from actual inventory and paid transactions. A forecast or exposure estimate is labeled as such. Trace rows should let an analyst follow a candidate cause through decision, physical change, sale, tax, and later policy.
- The historical Senegal/French West Africa case motivates the organizational and political design. Tuning coefficients are game values, not a numerical estimate of the strike's role in independence.
