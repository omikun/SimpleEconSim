# Egypt 1876–82: mechanics plan

## Goal and historical boundary

Make the Guided Egypt campaign capable of producing the historical path **and plausible alternatives** from the same causal rules. Financial control, army grievances, domestic support, naval pressure, and strategic access should interact. A missed payment alone must never guarantee bombardment or occupation.

The historical spine is: the 1876 Caisse and later Anglo-French financial control; Ismail's deposition in 1879; the broad ‘Urabi movement in 1881–82; the Alexandria crisis and British bombardment in July 1882; a British expedition through the Suez Canal and defeat of ‘Urabi at Tel el Kebir in September. Britain's canal and financial interests mattered together. France did not take part in the July bombardment. Sources: [National Army Museum](https://www.nam.ac.uk/explore/egypt-and-sudan), [Cambridge History of Egypt](https://www.cambridge.org/core/books/abs/cambridge-history-of-egypt/urabi-revolution-and-the-british-conquest-18791882/BD8A4DFB05CC2C5695074E1A9B44524F), [Cambridge account of the intervention](https://www.cambridge.org/core/books/imperial-incarceration/egypt-and-sudan-18821887/CC2378753E9E3317864D2A32E1E1DA1F).

Calibration check: [the July 14, 1882 Hansard debate](https://hansard.parliament.uk/Commons/1882-07-14/debates/aef5d070-48f2-475b-9087-5fc392b7f2a8/Egypt) discusses the absence of a simultaneous landing during Alexandria's bombardment, supporting separate bombardment and landing decisions. The National Army Museum places Tel el Kebir southwest of Ismailia, so the canal expedition now sails to Ismailia and then marches to an inland Tel el Kebir defense point. Sources guide order and geography; combat strengths and costs remain tuned values.

The 20-turn campaign compresses years into decisions, so turns are not literal calendar months. Named historical events should be *possible outcomes*, never mandatory timers. Keep each rule visible as a cause, cost, and likely consequence before the player chooses.

## Delivered first slice: customs claim to naval blockade

- Egypt may refuse a creditor customs claim or a guarantee without paying an automatic levy. A creditor response queues a naval assessment for the following turn.
- A consensual customs levy has a remaining balance and stops when the remittance is collected.
- Britain must have enough treasury cash, tolerable domestic protest, access to coastal Alexandria, and a force advantage over the battery and local garrison. Mobilization and continuing supply payments transfer money to British households.
- France's domestic condition determines whether it supports the demand. The British squadron and its ultimatum are visible; Cairo can settle, accept customs control, disarm, or defend.
- Defending against a credible squadron produces a bombardment consequence and uses the shared imperialism manager to blockade Alexandria's routes. Cairo can settle or hold out; an unsustainable British expedition withdraws.
- The Guided debt card, interrupting modal, hover consequences, ticker, and debrief expose the escalation. This is still an abstract squadron and battery, not a complete naval or invasion model.

## Phase 1 — One debt and revenue ledger

**Status:** Complete. Guided claims are recorded as pre-existing sovereign bonds held by Britain and France. Scenario payment decisions settle or revise those bonds. Consensual collection now intercepts a capped share of actual tax and customs receipts, with each transfer in the debt ledger.

**Original problem:** The Guided remittance and the sandbox sovereign bonds were separate accounts; the Guided levy was a flat transfer rather than interception of specific receipts.

**Mechanics:** Represent the Caisse's assigned revenues as named claims on customs, rail, port, and tax receipts. Link scenario maturities and default to sovereign bonds. Require each creditor's actual claim and record interest, principal, arrears, concessions, and settlements. Collect from the claimed revenue stream, limited by what it yields, with a ledger showing who paid and who received it. A consensual assignment works without ships; an imposed assignment requires a currently enforceable agreement or occupation.

**Player loop:** Relief and tax choices alter food, receipts, and the forecast payment. A debt screen shows the next obligation, restricted revenues, and who controls them.

**Completion:** Paying or restructuring one obligation updates both the Guided campaign and sandbox bond book; no duplicate or phantom collection occurs; transfers conserve cash. Candidate seams: `scenario_egypt_1877.py`, `scenario_situation.py`, `sovereign_bonds.py`, `macro/imperialism/manager.py`.

## Phase 2 — Egyptian political authority and the army

**Status:** Complete for the bounded campaign. Alexandria has a paid garrison whose morale contributes to loyalty to the palace. Officer access, army loyalty, palace and cabinet authority, civilian backing, and nationalist strength now move with welfare, austerity, foreign supervision, and naval coercion. The player can fund arrears, open promotions, invite a cabinet, or dismiss controllers. Conditional decisions can replace Ismail with Tawfiq or bring an officer-civilian coalition under ‘Urabi to power; the player continues governing Egypt. Controller dismissal draws an explicit creditor response.

**Original problem:** A single legitimacy and unrest number could not reproduce the conflict among Ismail, Tawfiq, army officers, landed notables, cultivators, and foreign controllers.

**Mechanics:** Track army pay, officer promotion access, loyalty to the ruler, and willingness to follow a civilian cabinet. Let austerity, foreign appointments, and repression produce grievances. Link existing factions and resistance to civilian support for an officers' movement. Allow a constitutional cabinet, a palace coalition, or a nationalist coalition to gain authority. A deposition or change of khedive requires a political actor with the power to carry it out; it is not a timed event.

**Player loop:** Decide whose support to buy, reform, or risk. The interface shows the two or three factions most likely to determine the next crisis, with reasons for movement.

**Completion:** Financial austerity can weaken army loyalty, a broad ‘Urabi-style coalition can form or fail, and the state can split over who may order Alexandria's defense. Candidate seams: `army.py`, `nation.py`, `coup.py`, `agents/resistance/manager.py`.

## Phase 3 — Canal geography, real fleets, and separate foreign decisions

**Status:** Complete for strategic Guided play. Alexandria, Port Said, Ismailia, Tel el Kebir, Cairo, and Upper Egypt are connected by a route graph anchored to generated Nile tiles. Canal transit rights and conserved toll transfers affect passage. The British squadron has a position, ships, guns, transports, coal, damage, and supply; only a supplied squadron off Alexandria can enforce its blockade. Britain and France decide independently, and Ottoman mediation can delay or settle an ultimatum. Cairo can close foreign canal transit.

**Problem:** Alexandria is a generated coastal tile, but the map lacks a playable Suez Canal, Port Said, Ismailia, Egyptian coastal batteries, and ship movement. The current squadron's force and travel are scenario abstractions. French support is diplomatic information only.

**Mechanics:** Give the campaign a connected Mediterranean–Alexandria–Port Said–Ismailia–Cairo route, canal transit rights and tolls, and defensible landing sites. Model fleet units with ships, guns, coal, supply, range, movement, and attrition. Use the existing blockade effect only when ships are present and supplied. Britain and France independently weigh bond exposure, canal access, domestic politics, cost, and diplomatic risk. Include Ottoman suzerainty and possible mediation or authorization as political constraints.

**Player loop:** See where fleets are and what they can reach, reinforce a fort or canal approach, offer terms, seek mediation, or accept a known risk.

**Completion:** A fleet can arrive, blockade, withdraw, or be deterred for physical and political reasons; France can join, abstain, or oppose; canal control changes Britain's strategic calculation. Candidate seams: map generation, `army.py`, `macro/imperialism/manager.py`, diplomacy, trade routes.

## Phase 4 — Ultimatums, bombardment, landings, and campaign resolution

**Status:** Complete for the Guided strategic layer. Fighting an ultimatum now spends battery ammunition, damages fort integrity and the British fleet, injures civilians, and records port infrastructure damage. A supplied fleet with transports warns the player before landing. The player can defend Alexandria, move the garrison to Tel el Kebir via Ismailia, evacuate, or settle. Britain must travel the canal route over turns and pay upkeep and tolls. Land battles use the shared army resolver, record losses, and change territorial control only when troops win or Egypt evacuates.

**Problem:** The first slice resolves bombardment as a scenario consequence. It has no destructible batteries, civilian harm, landing logistics, or land campaign.

**Mechanics:** An ultimatum names observable demands and a deadline. Forts can disarm, fight, run short of ammunition, or be destroyed. Fire damages buildings, supplies, trade, and civilians; it can harden or fracture Egyptian political support. A naval victory permits a landing only where transport and troops can be supplied. Use shared battle resolution for an Alexandria route or the canal route, with terrain, morale, officer loyalty, and local support deciding outcomes. Avoid a single scripted battle or automatic Cairo capture.

**Player loop:** Choose defense, evacuation, negotiation, canal denial, or a withdrawal to a stronger line; see immediate costs and the next likely British move.

**Completion:** A Britain that can bombard may still fail to occupy; a defended canal may redirect or defeat the expedition; an Egyptian collapse can restore a compliant ruler without erasing local opposition. Candidate seams: `army.py`, `diplomacy.py`, `macro/imperialism/manager.py`, regional damage and population systems.

## Phase 5 — Occupation, resistance, and alternate endings

**Status:** Complete for the bounded campaign. British land units must remain supplied to hold territory. Port and capital control determine who controls customs and tax offices; occupied receipts are drawn from actual income and transferred to Britain with a per-turn cap. Resistance rises with unrest, nationalist strength, and civilian harm. Egypt can organize a boycott, strike, insurgency, collaboration, or conditional withdrawal terms. A separate warning precedes a Cairo assault. The turn-20 debrief distinguishes formal sovereignty from effective institutional control and includes occupation, stalled intervention, nationalist victory, and successful repudiation outcomes.

**Reachability audit:** The outcome catalog now names all ten endings produced by the classifier. Complete decision-path tests reach relief and payment, creditor settlement, sovereign compromise through Ottoman mediation, continuing creditor financial control (by accepted demand or naval ultimatum), successful repudiation, stalled intervention, nationalist victory, occupation, coercive extraction, and government breakdown. Repeated emergency requisitions provide a player-caused breakdown path; sustained customs collection is classified as financial control rather than breakdown.

**Problem:** The current campaign ends at turn 20 with debt and government outcome bands. It cannot portray prolonged occupation or renewed Egyptian bargaining power.

**Mechanics:** If foreign forces hold administrative centers and routes, occupation must consume garrison supply and generate locally contested revenue. Permit collaboration, boycott, strikes, insurgency, negotiated withdrawal, and postwar debt terms. Distinguish formal Egyptian sovereignty from effective fiscal or military control. Continue to track civilian welfare and casualties. Include outcomes such as sovereign compromise, successful repudiation, stalled intervention, imposed financial control, occupation, and nationalist victory.

**Completion:** Each ending follows measured control of territory, institutions, resources, and support. The debrief explains why Britain and France did or did not intervene and who controls revenues and force at the end.

## Phase 6 — Guided presentation and historical calibration

**Status:** Complete for the bounded 20-turn campaign. Guided mode retains three pressure cards, promotes occupation and canal status when decisive, draws Port Said, Ismailia, and Tel el Kebir on the generated terrain, and scrolls the full decision list without a More menu. Every landing and capital assault has an interrupting decision with consequence tooltips. The campaign log labels documented context, tuned values, and outcomes generated by play. Deterministic 20-turn checks reach a peaceful payment outcome, the historical order of succession → officer coalition → naval crisis → occupation, and an alternate canal defense that blocks Cairo. The desktop GPU pipeline rendered both Guided and Advanced before the final presentation edits; the final macOS GUI retry stalled inside `pygame.init`, so the final layout was verified with surface-based UI tests rather than a new desktop screenshot.

Preserve three headline pressures. Reveal army allegiance, naval threat, or canal access as one of those pressures when it becomes decisive; keep deeper tables in Analysis. Every ultimatum and major military decision needs a consequence tooltip and a pause before resolution. The campaign log must distinguish documented history, plausible alternatives, and tuned game values. Calibrate the historical path against primary records and historians, then play alternate paths to ensure they are mechanically possible. The Advanced UI and sandbox systems should remain usable with the same domain rules.

## Design decisions still open

1. **Campaign scope:** Extend this campaign through 1882, or keep 1877 as the introductory chapter and create a second 1881–82 chapter. Recommended: two linked chapters, so one Guided run stays readable.
2. **Player role:** Continue as the incumbent khedive after a possible deposition, or switch to the governing Egyptian coalition. Recommended: control the governing coalition and clearly show when authority changes hands.
3. **War detail:** Simulate ship and land unit maneuvers directly, or use strategic orders with the shared battle model under the hood. Recommended: strategic orders in Guided, detailed unit control in Advanced.
4. **Historical names:** Use documented actors and places, but never guarantee their historical decisions. Recommended: fixed identities and starting positions, contingent choices and outcomes.
