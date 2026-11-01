# Governing through society: simplification and implementation plan

Date: October 30, 2026.
Status, November 1, 2026: milestone 3's first governing slice is implemented behind the creation-time `governing` mode. It adds autonomous household petitions, next-turn walkouts, source-owned strikes, opposing pressure and funded local bargaining to Egypt's existing economy. See the [guide](../docs/governing_campaign.md), [ownership register](governing_network_ownership_register.md) and [verification report](reports/governing_network_governing.md). Milestone 4 has automated and rendered-playthrough evidence; human usability and balance remain open gates. Opposition remains milestone 5. The classic and Patronage laboratories remain implemented experiments. This plan supersedes importing their complete player-facing systems into the main game.

## 1. Player experience

**The player governs a country. Society cooperates, bargains or resists in response to those decisions.**

The normal loop is: see a material problem → choose a policy → let the existing economy carry it out → see who benefited and who was harmed → address an organized demand when it matters. Ordinary administration and political communication continue without assigning individual recruiters every few turns.

Keep the original ambition that power depends on people's relationships. The network determines whether dissatisfaction remains scattered, becomes a credible petition, or develops into coordinated obstruction. It also explains why an influential representative can gain privately while their constituents suffer. The player usually engages with organizations and issues; a particular person becomes important when they control something specific.

The design reference is Frostpunk's connection between governing decisions and social consequences, including the sequel's group bargaining. The useful lesson is to make political trade-offs part of managing society. We are not adding its council structure, ideological axes or approval meters wholesale. [Developer discussion](https://store.epicgames.com/news/frostpunk-2-exclusive-interview-leave-your-fingerprint-on-a-frozen-world?lang=en-US).

## 2. What changes from the current prototype

| Current laboratory behavior | Proposed main-game behavior |
|---|---|
| Repeatedly rally named supporters and rotate them through campaign breaks | Cooperation persists through interests, delivery, agreements and organizational memory; routine mobilization is autonomous |
| Two political actions per laboratory round | Use the campaign's existing decision cadence and action limits; introduce no second attention currency |
| Manage a nine-person council to retain five votes | Use the country's existing governing institutions; Egypt does not acquire the laboratory council |
| A 32-person cast with individual council and support controls | See three relevant communities, their material concerns and organized capacity; inspect a representative only when useful |
| Separate laboratory job, wage, hiring and project rules | Existing labor, production and project systems resolve routine execution |
| A separate 164-credit laboratory ledger and four service shares | Existing inventories, wallets, treasury, tax and debt authorities supply all material effects |
| Several tabs for deals, jobs, brokers, evidence and votes | Existing crisis view presents the problem, choices, affected groups and current dispute |
| General access to private bargains, audits and disclosures | Retain a bounded promise record; introduce investigations only when a scenario needs them |
| Construction and political campaigning compete through a laboratory effort slot | Use actual availability, employment and strike rules; do not add a second labor-allocation system |
| Automatic broad trust rewards for project success in classic mode | Attribute actual benefits, losses and broken commitments to affected people and organizations |

This changes rules as well as presentation. Hiding the graph while keeping the recruitment schedule would preserve the problem.

Patronage already resolves individual job acceptance and wages automatically. The remaining workload comes from separate political scheduling, institutions and resource models. Preserve useful automation while reducing those obligations.

Keep graph propagation, heterogeneous interests, durable organizations, costly concessions, explicit authority and causal explanations. Remove routine individual campaigning from the governing interface. Defer generic contract negotiation, private exemptions, intelligence systems and institutional expansion from the first integration.

## 3. First playable slice: Egypt's existing grain crisis

Work inside the existing `egypt_1877` campaign and its main client. Do not create another mandatory bridge game or a new standalone political sandbox. The existing laboratories remain development comparisons and regression evidence.

Use the existing food shortage, public maize reserves, privately held maize, cultivator arrears and impending debt payment. Project three visible civilian communities from existing actors and roles:

- **Cultivators and working households:** food access, arrears, wages and security of livelihood.
- **Grainholders and landowners:** control over stocks, payment, property and tax exposure.
- **Merchants and exporters:** actual trading opportunities, market access and predictable rules.

These are proposed political views over existing agents, not three already-complete faction models. A person may have overlapping interests. Population, participation and costs must deduplicate actual agent IDs. Existing officer, foreign-creditor and cabinet systems remain relevant but do not become additional new faction simulations in this slice.

Use three existing policy routes as the initial comparison:

| Policy route | Material resolution | Political question |
|---|---|---|
| Buy private maize, then distribute available relief | Existing purchase and relief handlers transfer actual money and grain | Can the treasury afford cooperation with owners while meeting debt obligations? |
| Requisition available private grain | Existing requisition rules determine availability, compensation and enforcement | Does helping hungry households justify alienating those with control and influence? |
| Open private grain markets | The existing standing market policy offers available grain; actual household purchasing power determines access | Does increasing supply help the people who cannot afford it, and who captures the income? |

Show costs from the real handlers rather than inventing fixed laboratory prices. Buying stock alone does not improve food access until households actually receive or can purchase food. A selected standing policy continues automatically within its real limits; running out of grain, money or authority produces a specific report.

The first consequential collective responses are **petitions and strikes**, using existing affected people and existing settlement actions. A petition signals a demand; it does not directly reduce production. A strike affects only its actual participants through the existing labor path. Do not add another general productivity or unrest penalty for the same action.

A representative might offer settlement in exchange for arrears relief or an existing worker bargain. The player chooses a governing response. They do not schedule speeches to preserve each household's support.

## 4. Politics that continues without maintenance clicks

Keep material satisfaction, trust in a promise and capacity to coordinate distinguishable. Public presentation can use clear descriptions such as “households are hungry; their associations are well connected; a tax petition is spreading.” There is no single corruption or universal loyalty score.

Each political update should:

1. Observe resolved food access, payments, arrears, employment, enforcement and fulfilled commitments.
2. Attribute changes to affected members and responsible institutions. Record mixed outcomes within a community instead of assigning everyone the same reaction.
3. Update remembered cooperation and grievances gradually. Sustained delivery supports stable cooperation; material deterioration, broken commitments, hostile decisions and organized opponents can change it.
4. Propagate bounded pressure through the relationship network and evaluate actual available participants.
5. Produce a petition or recruitment/settlement proposal when there is sufficient organization and a concrete demand.

**There is no penalty for failing to press a rally button.** Time can matter because livelihoods, obligations and alternatives change. Existing participation constraints still apply, but their routine management belongs to people and organizations. Stable cooperation should survive several quiet turns without political maintenance actions.

Opposing influence remains autonomous. A rival can exploit a genuine unresolved grievance or offer an alternative coalition. Their effectiveness depends on contacts, credibility, available participants and resources. Avoid scripted betrayal, a fixed recruitment pulse, or a predetermined overthrow turn.

Representatives cannot bind an entire class by signing an agreement. Display the demand, who is represented, what the representative can deliver and what participating members actually do. Benefits credited to an organization can strengthen its independence from the government.

## 5. A small network behind the governing view

Use one sparse network spanning locations. The first integration uses regional organization nodes and a few relevant existing coordinators or holders of material power. Membership refers to existing agents; it does not create a second population or import the laboratory's 32-person cast.

Links need an explainable basis: an established association, shared participating members, a coordinator's contacts or a supported trade/communication connection. Do not assume every trade route is automatically political trust. A small authored initial topology is acceptable if labeled as scenario setup rather than inferred history.

Reuse weighted propagation, reachability and component reasoning where useful. Generalize algorithms separately from the laboratory's fixed `player/rival/upstream/market` channels and `Session` schema. Keep opposing pressures, lag and persistence. Do not introduce a full all-pairs graph over the economic population in the first slice.

Group summaries are a presentation and scale choice, not proof that members agree. Aggregated organization links must not duplicate people, invent votes or grant vetoes. An actor can block only an activity they actually control; disconnected workers and alternative suppliers remain possible substitutes.

The main map shows relevant locations and active collective action. A focused relationship overlay is optional. It should explain why a dispute spreads or stalls; it is not a required screen for routine policy decisions.

## 6. One authority for each existing effect

Before implementation, write a short ownership register for the affected paths:

| State or effect | Authority and boundary |
|---|---|
| Money, inventories, taxes and debt | Existing economic handlers; network observes results and requests authorized actions |
| Employment, wages and project progress | Existing labor/construction systems; no political copy of completion or staffing |
| Strike participants | One existing execution path, selected by mode; replace the relevant recruitment decision rather than running both versions |
| Household mutual aid | Existing transfers and inventories; no food generated by organization strength |
| Civilian support, legitimacy and unrest | Explicit mapping to existing political state; audit overlapping old/new responses before enabling mutation |
| Government replacement | Existing regime/scenario authority until a unified transition contract is ready; no parallel council or takeover resolver |
| Player identity | Separate from the nation's government when the later opposition phase is enabled |

The first integration point to audit is `scenario_political_economy._organize`: it currently derives petitioners and striker recruitment largely from hunger and arrears, and also performs mutual-aid transfers. Replace only the selected recruitment/coordination logic under the experiment. Preserve actual transfers and unrelated processing. Inventory other writers of `is_striking` before enabling the replacement.

Existing actions also directly affect civilian support, legitimacy and unrest. A delivery event must not receive an old support bonus plus an equivalent new network bonus without a deliberate distinct causal meaning. Derived summaries should reuse existing political fields or replace their source under the flag, rather than adding competing victory gauges.

Use immutable turn observations and one network update per economic turn. The current core regime phase precedes parts of the scenario advance, so implementation must explicitly locate observation and effect boundaries. Prefer next-turn recruitment intents consumed by the existing labor path. Do not silently retroactively change work already delivered or resolve leadership twice.

Retain the game's existing time abstraction. The political graph does not add a separate round clock or consume authoritative economic random draws merely by being observed.

## 7. Interface and attention budget

Extend the current food, treasury/debt and political-support pressure cards. The normal screen should answer:

- What is failing materially?
- Which communities are affected, and what do they want?
- Can their organization actually obstruct something?
- What are the real costs and consequences of the available responses?

An expanded political card shows the three communities, a concrete concern, a plain description of organization and the most relevant change. Exact weights and full graph inspection stay in developer tools. Named representatives appear on a dispute card with their role and limited authority.

For the first authored crisis, allow at most two disputes requiring a new decision at the same time. Repeated notices about the same unmet demand should update one card. Preserve all material effects and pending obligations; do not discard problems to achieve a tidy display. Ordinary messages stay in the activity history instead of opening blocking dialogs.

Each dispute offers a small number of real responses, normally two or three, plus continuing the current policy when legal. Preview direct resource costs, likely beneficiaries, institutional concessions and uncertainty. Do not promise exact future loyalty or use hidden information in advice.

After resolution, show a short chain: “arrears relief delivered → petition participation fell → the threatened strike did not form.” A failed response should say whether it lacked money, authority, willing participants or credibility. Existing causal IDs support inspection without requiring a separate player-facing evidence game.

## 8. Opposition is a later, distinct phase

Preserve the commitment that overthrow need not end play. Build it after the governing slice passes the usability gates below. The first integrated slice must not claim that this continuation already exists in the main campaign.

When enabled, one authoritative transition changes the player's role from incumbent to displaced leader. The economy, population and new government continue. Earlier agreements, remembered benefits, institutions and enforceable rights persist. The player does not gain control of the successor's treasury simply because the UI still follows Egypt.

Opposition play should offer a few consequential choices: negotiate a governing alliance, back a specific organized demand, or pursue a lawful/institutionally available challenge. Day-to-day recruitment remains autonomous. Access to funds and supporters must be real; there is no free campaign resource pool.

Return to office uses the country's institutions. Egypt does not inherit the laboratory's five-of-nine vote rule. Existing succession, deposition and generic regime transitions need a single transition executor and stable player identity before this phase ships. Character death/succession remains outside the first implementation.

On restoration, inherited obligations and existing conditions resume. Return is neither automatic nor equivalent to a successful governing coalition.

## 9. Delivery sequence

| Milestone | Deliverable | Exit gate |
|---|---|---|
| 1. Freeze the simpler contract | Ownership register, three-community projection, one grain-crisis storyboard and a compact UI mockup | Every normal choice addresses the existing economy; no individual campaign schedule or new political currency |
| 2. Observe the existing campaign | Read-only material observations and organization/network diagnostics in Egypt | Existing authoritative outcomes and random sequence match disabled mode; traces explain membership and material inputs |
| 3. Ship one governing loop | Group response, automatic coordination and gated petition/strike recruitment through existing handlers; integrated cards | The player can complete a short crisis using policy/dispute decisions without opening a person inspector or rallying anyone |
| 4. Validate and simplify | Multiple policy routes, network counterfactuals, longer-run stability, ordinary UI playthroughs and human feedback | Organization changes outcomes; routine political upkeep stays absent; trade-offs are legible and the economic ledger reconciles |
| 5. Add loss and return | Stable player identity, unified transition ownership and a small opposition action set | A legal loss/return path preserves obligations and resources, and the player governs after returning without managing recruiters |

Milestones 1–4 are the first delivery target. Stop adding political features if milestone 4 fails; remove or revise the source of workload. Milestone 5 is a separately gated continuation of the same direction, not a prerequisite for proving the governing loop.

Candidate code boundaries: existing scenario actions and accounting remain in `scenario_egypt_1877.py`, `scenario_political_economy.py` and `government.py`; a small proposed `scenarios/governing_network.py` owns organization/coordination state and adapters; `scenario_ui.py` presents the projection. Any later transition changes are coordinated with `scenario_politics.py` and the core regime path. Confirm these boundaries during milestone 1 rather than distributing ownership across new parallel systems.

## 10. Modes, compatibility and verification

Introduce a scenario-creation experiment setting with proposed values **off**, **observe** and **governing**. Off retains current campaign behavior. Observe computes diagnostics without political/material mutations or extra authoritative RNG consumption. Governing enables only the explicitly replaced paths. Hiding an overlay does not disable simulation.

Record the mode and versioned state in saves; validate actor references and source ownership. Preserve old campaign saves in their original mode. Refuse implicit conversion or live toggles that would discard institutions, recruitment state or obligations. Keep the old laboratories and their version-2/version-3 fixtures available as development evidence, without adding their screens to the main client.

Required behavioral checks:

- Equal material hardship with connected versus fragmented organizations produces different mobilization, with real participating agents and a reconstructible cause.
- Quiet, adequately served society does not require rallying or artificial periodic support refreshes.
- A policy's actual delivery matters more than clicking its label; a failed or unfunded order does not grant success rewards.
- Groups can disagree internally; overlapping members are not counted twice; a representative can lose followers.
- A petition and a strike have different effects; strike participation affects work once through the existing authority.
- Alternative grain policies produce materially and politically different outcomes. Neither private favors nor a single virtuous choice guarantees victory.
- Cash, grain, labor and debt reconcile; relevant legacy effects and new effects do not double count.
- Mode-off regressions, observe-mode equivalence, save/resume, deterministic replay and traced/untraced results remain valid.
- A player can understand the first crisis from the existing pressure cards, choose a response and explain the affected groups without a graph tutorial.
- The eventual opposition test uses actual institutional conditions, preserves past obligations and offers an uncertain return without forced transfers.

Use existing Egypt scenario, grain-transfer, bargain, politics, campaign and presentation tests as the baseline. Add only tests that distinguish the new behavior, then run short integrated UI playthroughs comparing the three policy routes. Record the number and purpose of required political interventions, not merely whether a script can win.

Human playtesting should specifically look for needless clicks, recurring maintenance choices and situations where inspecting individuals becomes compulsory. Automated replay proves consistency; the first delivery is successful only if governing is understandable and political decisions arise from the society being governed.

## 11. Immediate next implementation step

Start with the ownership register and a read-only Egypt observation adapter. Produce one visible explanation linking actual food/arrears outcomes to a community's concern. Audit the strike writers and political turn order before enabling effects. Do not begin by porting laboratory contracts, replacing the whole political system, or adding a new graph screen.

Implementation update: `off`, version-1 `observe` and version-2 `governing` are available at campaign creation. The strike-source contract now keeps workplace, enclosure and network participation independent while projecting the existing production Boolean. Petitions are immediate demands; network work-withholding intentions are revalidated and consumed before the next economic turn. Existing mutual aid, transfers, labor execution and government transitions retain their owners. The shared main view exposes private grain routes, local dispute responses and due debt choices. The [ownership register](governing_network_ownership_register.md) records the implemented boundaries. The next gate is human playtesting and simplification, including whether organization and policy trade-offs are clear without using the graph or inspecting people. Do not add the opposition layer before that review.
