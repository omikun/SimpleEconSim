# Governing network: first integration contract and ownership register

Date: October 30, 2026.

This records milestones 1–2 of the [governing plan](governing_network_implementation_plan.md). The implemented slice observes Egypt's existing economy and shows its three civilian communities. It runs a small experimental pressure graph alongside the campaign. It does **not** change recruitment, legitimacy, unrest, production, government replacement or victory conditions. Milestones 3–4 remain the next governing delivery; the opposition phase remains later.

## One authority per material effect

| Effect | Existing authority | Observation boundary |
|---|---|---|
| Public/private money and grain | `scenario_egypt_1877.apply_action`, `scenario_political_economy.apply_action`, ordinary market/accounting handlers | Copy cash, inventories and actual transaction records. Never debit accounts or use an observer budget. |
| National relief | Existing `release_maize` action queues four-unit next-meal rations for eligible underfed households | A queued ration is not evidence of a consumed meal. Read resolved calorie deficit on the next turn. |
| Private warehouse stock | Existing owner inventory plus `private_reserve_by_tile` | Calculate a bounded view without calling `stock`, `_reserved` or `district_snapshot`: those helpers can write reserve state. |
| Arrears, payment and foreclosure | `scenario_political_economy._assess_arrears`, `_foreclose` and existing relief actions | Read actual balances and current actor location; refresh membership after death/migration. |
| Mutual aid | Existing `_organize` and `district_support_mutual_aid` transfers | Observe actual participants/outcomes; create no food and preserve automatic aid. |
| Jobs, payroll and production | Existing hiring, labor contracts, `region_production` and construction/project systems | No second job list, work allocation, project progress or payroll. |
| Petitions and scenario strike cohort | Existing `scenario_political_economy._organize` | Observe counts only in this slice. All existing recruitment remains enabled exactly as before. |
| Workplace strike organization | `agents/collective_action.py` | Observe actual flags; do not issue parallel instructions to employees. |
| Other resistance and repression | `agents/resistance/manager.py`, `micro/labor_politics.py` and existing scenario actions | Preserve their current authority; no extra productivity/unrest penalty. |
| Political support and civilian/officer coalition | `scenario_politics`, national regime code and existing action effects | No new support gauge, election/council rule or additive policy bonus. |
| Succession/deposition | Existing core regime and scenario political transition paths | No displaced-player identity or second transition executor yet. |
| Experiment state | `scenarios/governing_network.py` | Versioned, serializable observation sidecar only; authoritative state remains outside it. |

## Strike-writer audit and the next mutation gate

`is_striking` is one shared Boolean with several independent writers:

- `agents/collective_action.py` starts workplace action, accepts agreements, ends closed-firm action and reviews delivery. Agreement code can clear employees' flags.
- `agents/resistance/manager.py` sets and clears flags for enclosure revolts and charismatic movements, among other resistance paths. Its general-strike escalation also reads the combined flag and can block routes.
- `scenarios/scenario_political_economy.py` recruits a scenario cohort, clears emigrants from that cohort, and settles or represses local strikes. Its `_organize` also transfers actual mutual-aid food.
- `micro/labor_politics.py` can clear strikes through national armed strikebreaking.
- `agents/agent.py` initializes the flag. `micro/region_production.py` uses it to exclude workers from actual production, including independent producers.

Simply replacing `_organize` recruitment would leave overlapping sources vulnerable to clearing each other's flags. Simply adding new network recruits could also trigger generic escalation in addition to their actual withheld work. The observation implementation changes **none** of these writers.

Before enabling the `governing` mode, implement an explicit source/participant contract: ending one organization must not end another's continuing strike, national repression must deliberately settle the sources it affects, and a network petition must not trigger a production penalty. Prove overlapping-source tests and the actual labor consumption boundary before shipping network-driven recruitment. This is an engineering exit gate, not a request for additional user permission.

## Turn order

1. The native engine resolves the economic turn, including hiring, production, consumption and generic regimes/resistance. `core/sim_engine.py` evaluates national regime transitions before the scenario advance.
2. `scenario_egypt_1877.advance_scenario` advances strategic projects and existing political economy. The latter processes standing private sales, tax assessments, existing organization and mutual aid.
3. The existing grain entitlement handler runs.
4. **The new observer freezes material observations here, once per turn.** It updates only its sidecar and separate diagnostic journal.
5. Existing scenario debt deadlines, unrest translation, politics, foreign reactions and campaign resolution continue.

Consequently the UI labels its data “after turn N food and taxes,” not a final forecast of the later political phases. Between-turn policy selections do not rewrite this completed observation. Opening conditions are recorded at campaign creation without pretending an economic turn has already run.

Both `client.desktop.engine` and the legacy `worldview_engine` use this shared scenario boundary. A future governing cohort should be prepared from a frozen observation and consumed before the **next** turn's relevant labor step. It must not retroactively remove completed work or run a second leadership check.

## Three views of the same population

- Cultivators and workers are living, nongovernment, noncorporate residents who are neither traders nor landowners/warehouse holders.
- Grainholders and landowners are living landowners and the actual warehouse owners named by the scenario.
- Merchants and exporters are current trader agents. The label is a broad player-facing view; it does not infer a complete export industry or new political faction from these roles.

A trader can also hold a warehouse. That person appears once in each relevant view and remains one economic actor. Repeated references in location lists do not duplicate a person. The observer does not invent a representative, binding mandate, vote, member subscription or class-wide agreement.

Food concern uses actual calorie deficit, with a 5% deficit threshold for the displayed underfed count. Tax concern uses existing unpaid balances. Owner property pressure uses actual requisition transactions. A merchant trade-pressure source is currently limited to merchants who themselves hold reserved warehouse stock under the existing hold policy. Other merchant grievances remain unmodeled rather than being fabricated from unrelated national sales.

## The small graph

Each district has up to three organization nodes, referencing the real membership above. Empty nodes cannot transmit. Same-community contacts along a small authored Upper Egypt–Cairo–Delta–Alexandria–canal chain supply directed weighted links where those locations exist. This is an explicit experimental setup, **not** a historical claim, inferred personal trust or a connection copied automatically from every river/trade route.

The observer computes directed reachability and weak components. A synchronous diffusion step carries old pressure one contact at a time and retains memory. Its receive budget bounds the sum of contact weights, so high degree cannot make pressure explode. For each channel it records old pressure, the material contribution, individual contact contributions, empty-membership adjustment and the result. Those terms reconstruct the update.

Food, arrears, property and trade remain separate diagnostic channels. This first slice does not yet model opposing-channel competition, actual organizing capacity, autonomous political bargaining or collective-action thresholds. A connected-versus-fragmented graph changes the **diagnostic propagation**, not mobilization in the real economy. Do not describe that as a completed network-effects gameplay test.

## Minimal grain-crisis storyboard

| Player sees | Existing policy choice | What really changes | What the observer may explain |
|---|---|---|---|
| Households lack food; public stores are finite | Release public maize | Available public stock becomes household next-meal entitlements | Underfed counts change only after actual food delivery/consumption. Clicking the label grants no abstract popularity reward here. |
| Private owners hold reserved maize | Buy private maize, then release available public stores on a later decision | Treasury pays actual owners; their grain moves into public inventory; release follows the existing decision cadence | Purchase and feeding are distinguishable. The treasury can lose money while households are still hungry. |
| The treasury cannot comfortably pay for cooperation | Requisition private maize, then distribute available relief | Actual owner grain moves to public stores without a purchase payment; existing unrest effects still occur once | Owner property pressure can increase even if households later benefit. |
| Private supply is held back | Open private grain sales | Existing sellers offer available grain and eligible households pay actual prices; standing sales continue | Sales can increase while people without purchasing power remain underfed. |
| Food provision improves but unpaid taxes persist | Existing district arrears relief or worker settlement | Existing handlers write off actual liabilities or negotiate real owner-funded terms | Food and tax concerns remain distinguishable; no generic “all demands solved” state. |

The rendered community panel is the milestone-1 UI mock made concrete: three concerns visible over the existing terrain, beside the unchanged campaign decisions. Hiding it changes presentation only. No individual inspector or graph lesson is required to read those concerns.

The audit also found two different existing scenario interfaces: the primary desktop has a shorter decision panel, while the legacy worldview panel exposes the private-grain routes and more campaign responses. This slice shares the observation overlay across both; it does not silently merge those clients. The three-policy verification uses the real scenario action dispatcher. The rendered primary-client playthrough exercises its existing reserve-release button. Milestone 3 must expose the grain routes and relevant dispute responses coherently in the primary client's normal decisions before claiming a playable integrated governing loop.

## Modes, persistence and journal

At scenario creation, `off` preserves prior behavior and `observe` enables this slice. `governing` is deliberately rejected until the recruitment gate above is passed. The desktop option is `--scenario egypt-1877 --ui-mode guided --governing-network observe`; the programmatic creation argument is `governing_network_mode='observe'` on either native builder. Restart preserves the selected creation option.

An otherwise compatible save with no sidecar remains off; the existing native checkpoint's source-version checks still apply. Version 1 stores the selected mode, scenario identity, frozen actor IDs and material inputs, graph, diagnostics and a bounded 24-observation journal. It fits the existing native checkpoint graph. Mode/version/reference validation rejects unsupported or inconsistent state instead of silently converting it. There is no live mode switch in Settings.

The diagnostic journal has its own deterministic observation IDs. It deliberately does not emit new events into the authoritative trace clock: some existing business-operation IDs include that clock's sequence. Actual grain transaction receipts remain available in the frozen input snapshot. This boundary lets observing remain observational even for trace identity. The journal does not claim that every concurrent change was caused by the most recent policy.

## Verification and remaining work

The focused tests cover read-only behavior, RNG preservation, real/overlapping membership, delivery versus a policy label, property seizure, frozen turns, death/migration, bounded diffusion, contact counterfactuals, source reconstruction, journal limits, JSON state and native checkpoint continuation. UI tests cover all three visible communities, hide/reopen in both clients and preventing clicks through the panel to an obscured district.

`scripts.verify_governing_network` compares three real grain-policy routes with observations off/on, tracing off/on and both native engines, in fresh processes with fixed Python, NumPy and hash seeds. It compares all sampled economic metrics each turn and the complete canonical economic graph, including RNG and gameplay globals, at the end. In addition to the repository's existing canonical normalization, it removes the documented observation sidecar and relabels the exact native recorder run UUID, retaining event sequence suffixes and all quantities. The [verification report](reports/governing_network_observation.md) records the executed results.

Milestone 3 still requires the strike-source contract, opposing pressure and actual autonomous participation, next-turn intent consumption, and a small number of integrated dispute responses. Milestone 4 still requires materially different full policy routes and human usability evidence. Neither a diagnostic graph nor deterministic replay establishes that governing is fun. Loss-and-return remains milestone 5.
