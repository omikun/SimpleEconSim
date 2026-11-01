# Governing network: first integration contract and ownership register

Updated: November 1, 2026.

This records the observation and first active governing slices of the [governing plan](governing_network_implementation_plan.md). `Observe` retains the read-only contract below. `Governing` replaces scenario recruitment with autonomous network coordination, executed through existing labor and scenario handlers. It introduces no separate economic ledger, action currency or government-transition resolver. Human usability and balance remain milestone-4 gates; opposition remains later.

## Active governing contract

| Responsibility | Owner and boundary |
|---|---|
| Frozen material facts and graph | `governing_network` retains current actor references and a bounded 24-observation journal. Version-1 observe is unchanged; version-2 governing adds participation state. |
| Autonomous household coordination | `governing_collectives` evaluates individual food/arrears grievances, shared pressure, contacts, cohesion, delivery trust, risk, repression memory and survival resources. Stable personal differences consume no economic RNG. Petitions are demands now; strikes are intentions for the following turn. |
| Next-turn execution | Both native engines call `prepare_turn` before `sim_engine.step_turn`. Live location, need, actual rations/stocks, work availability, survival capacity and settlement conditions are rechecked. Each intent is consumed once. Existing production and payroll read the resulting Boolean; no extra output penalty is applied. |
| Strike ownership | `agents/strike_status.py` holds namespaced sources for enrolled actors. Workplace and enclosure settlements remove their own source. Network bargains remove only consenting participants' network source. Explicit whole-person repression clears all affected sources. Off/observe actors keep the legacy Boolean and gain no registry. |
| Generic escalation | Network-only withholding does not also count toward the generic route-wide general-strike freeze. Independent workplace/resistance sources can still cause it. |
| Existing scenario recruitment and mutual aid | In governing mode `_organize` uses actual network participants rather than legacy hunger-only recruits. The same handler still transfers real automatic mutual-aid food. Off/observe use `_legacy_recruit`. |
| Funded local bargaining | Existing owners fund cash grants and wage offers through existing transfers. Zero-funded terms fail before wages or political rewards change. Actual recipients decide individually whether to accept a three-turn ceasefire; worsening needs can break it. Existing campaign unrest/legitimacy consequences occur once. No representative binds all followers. |
| Material policy and authority | `governing_actions` previews read-only real costs and routes to the existing action dispatcher. Foreign map inspection does not change the player's Egyptian treasury authority. One existing major decision per turn remains. |
| Causal chain | Native plan → consumed participation → actual firm workforce hours → production events are linked. The network journal records pressure sources, contact/opposition terms and individual thresholds. UI explanations use observed participation reasons and actual payment receipts. |
| Player interface | The shared governing view exposes grain routes, up to two common demand cards, local terms/arrears responses and all four due debt choices. All policies/back and scrolling retain the fuller existing campaign decisions. Urgent scenario dialogs retain their existing choices and input priority in the primary client; inline debt responses clear the resolved warning instead of stalling later phases. Ordinary option announcements stay suppressed. No recurring rally action is added. |

The active graph adds the authored Nile Valley–Cairo contact and local household/holder counteredges. Friendly pressure diffuses synchronously; opposing pressure reduces the other side's field within a bounded budget. Owner property pressure follows actual seizures with decaying memory. Owner influence is currently counterpressure rather than an independent economic veto; merchants do not yet have autonomous bargaining. These authored group contacts are a coarse first integration, not a complete personal relationship network.

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

## Original strike-writer audit and its resolution

`is_striking` is one shared Boolean with several independent writers:

- `agents/collective_action.py` starts workplace action, accepts agreements, ends closed-firm action and reviews delivery. Agreement code can clear employees' flags.
- `agents/resistance/manager.py` sets and clears flags for enclosure revolts and charismatic movements, among other resistance paths. Its general-strike escalation also reads the combined flag and can block routes.
- `scenarios/scenario_political_economy.py` recruits a scenario cohort, clears emigrants from that cohort, and settles or represses local strikes. Its `_organize` also transfers actual mutual-aid food.
- `micro/labor_politics.py` can clear strikes through national armed strikebreaking.
- `agents/agent.py` initializes the flag. `micro/region_production.py` uses it to exclude workers from actual production, including independent producers.

Simply replacing `_organize` recruitment would leave overlapping sources vulnerable to clearing each other's flags. Simply adding new network recruits could also trigger generic escalation in addition to their actual withheld work. The source registry and escalation boundary above address these problems only for enrolled governing actors. The migrated writers retain their legacy behavior outside governing mode.

Focused tests now exercise actual workplace offers, enclosure dissolution, overlapping sources, deliberate repression and native withheld-hours/zero-output causal links. A connected-versus-fragmented fixture changes actual participation under equal hardship. Quiet society, funded next meals, individually rejected bargains and unfunded failure paths are covered. See the [active-phase report](reports/governing_network_governing.md) for executed results and baseline limitations.

## Turn order

1. The native engine resolves the economic turn, including hiring, production, consumption and generic regimes/resistance. `core/sim_engine.py` evaluates national regime transitions before the scenario advance.
2. `scenario_egypt_1877.advance_scenario` advances strategic projects and existing political economy. The latter processes standing private sales, tax assessments, existing organization and mutual aid.
3. The existing grain entitlement handler runs.
4. **The new observer freezes material observations here, once per turn.** It updates only its sidecar and separate diagnostic journal.
5. Existing scenario debt deadlines, unrest translation, politics, foreign reactions and campaign resolution continue.

Consequently the UI labels its data “after turn N food and taxes,” not a final forecast of the later political phases. Between-turn policy selections do not rewrite this completed observation. Opening conditions are recorded at campaign creation without pretending an economic turn has already run.

Both `client.desktop.engine` and the legacy `worldview_engine` use this shared scenario boundary. Governing mode consumes the previous frozen intent immediately before step 1, then plans the next cohort after step 4. It does not retroactively remove completed work or run a second leadership check.

## Three views of the same population

- Cultivators and workers are living, nongovernment, noncorporate residents who are neither traders nor landowners/warehouse holders.
- Grainholders and landowners are living landowners and the actual warehouse owners named by the scenario.
- Merchants and exporters are current trader agents. The label is a broad player-facing view; it does not infer a complete export industry or new political faction from these roles.

A trader can also hold a warehouse. That person appears once in each relevant view and remains one economic actor. Repeated references in location lists do not duplicate a person. The observer does not invent a representative, binding mandate, vote, member subscription or class-wide agreement.

Food concern uses actual calorie deficit, with a 5% deficit threshold for the displayed underfed count. Tax concern uses existing unpaid balances. Owner property pressure uses actual requisition transactions. A merchant trade-pressure source is currently limited to merchants who themselves hold reserved warehouse stock under the existing hold policy. Other merchant grievances remain unmodeled rather than being fabricated from unrelated national sales.

## The small graph

Each district has up to three organization nodes, referencing the real membership above. Empty nodes cannot transmit. Same-community contacts along a small authored Upper Egypt–Cairo–Delta–Alexandria–canal chain supply directed weighted links where those locations exist. This is an explicit experimental setup, **not** a historical claim, inferred personal trust or a connection copied automatically from every river/trade route.

The observer computes directed reachability and weak components. A synchronous diffusion step carries old pressure one contact at a time and retains memory. Its receive budget bounds the sum of contact weights, so high degree cannot make pressure explode. For each channel it records old pressure, the material contribution, individual contact contributions, empty-membership adjustment and the result. Those terms reconstruct the update.

Food, arrears, property and trade remain separate channels. In observe mode they are diagnostics only. Governing mode adds the opposing terms, organization memory and actual participation described above; it retains exact pressure contributions for reconstruction. The observation report's connected/fragmented test establishes propagation; the governing test separately establishes a change in actual work-withholding participants.

## Minimal grain-crisis storyboard

| Player sees | Existing policy choice | What really changes | What the observer may explain |
|---|---|---|---|
| Households lack food; public stores are finite | Release public maize | Available public stock becomes household next-meal entitlements | Underfed counts change only after actual food delivery/consumption. Clicking the label grants no abstract popularity reward here. |
| Private owners hold reserved maize | Buy private maize, then release available public stores on a later decision | Treasury pays actual owners; their grain moves into public inventory; release follows the existing decision cadence | Purchase and feeding are distinguishable. The treasury can lose money while households are still hungry. |
| The treasury cannot comfortably pay for cooperation | Requisition private maize, then distribute available relief | Actual owner grain moves to public stores without a purchase payment; existing unrest effects still occur once | Owner property pressure can increase even if households later benefit. |
| Private supply is held back | Open private grain sales | Existing sellers offer available grain and eligible households pay actual prices; standing sales continue | Sales can increase while people without purchasing power remain underfed. |
| Food provision improves but unpaid taxes persist | Existing district arrears relief or worker settlement | Existing handlers write off actual liabilities or negotiate real owner-funded terms | Food and tax concerns remain distinguishable; no generic “all demands solved” state. |

The rendered community panel is the milestone-1 UI mock made concrete: three concerns visible over the existing terrain, beside the unchanged campaign decisions. Hiding it changes presentation only. No individual inspector or graph lesson is required to read those concerns.

The audit found two different existing scenario interfaces: the primary desktop had a shorter decision panel, while the legacy worldview panel exposed more policies. Governing mode now shares a compact policy/dispute view between both and exposes the full existing policy panel through All policies. Rendered primary-client playthroughs exercise the real purchase, seizure and private-sales buttons alongside reserve distribution and debt responses.

## Modes, persistence and journal

At scenario creation, `off` preserves prior behavior, `observe` enables read-only diagnostics and `governing` enables the active slice. The desktop option is `--scenario egypt-1877 --ui-mode guided --governing-network governing`; use `observe` for comparison. Either native builder accepts the corresponding `governing_network_mode`. Restart preserves the selected creation option.

An otherwise compatible save with no sidecar remains off; the existing native checkpoint's source-version checks still apply. Version 1 stores the selected mode, scenario identity, frozen actor IDs and material inputs, graph, diagnostics and a bounded 24-observation journal. It fits the existing native checkpoint graph. Mode/version/reference validation rejects unsupported or inconsistent state instead of silently converting it. There is no live mode switch in Settings.

The diagnostic journal has its own deterministic observation IDs. Observe mode emits no extra authoritative trace events: some business-operation IDs include that clock's sequence. Governing mode additionally emits actual plan/participation decisions into the native trace, linking real food-intake causes when available and actual workforce outcomes. Native checkpoint restore deliberately forks recording identity; continuation tests retain all material/decision values while excluding only new native `trace_event_id` references. The journal does not claim every concurrent change was caused by the most recent policy.

## Verification and remaining work

The focused tests cover read-only behavior, RNG preservation, real/overlapping membership, delivery versus a policy label, property seizure, frozen turns, death/migration, bounded diffusion, contact counterfactuals, source reconstruction, journal limits, JSON state and native checkpoint continuation. UI tests cover all three visible communities, hide/reopen in both clients and preventing clicks through the panel to an obscured district.

`scripts.verify_governing_network` compares three real grain-policy routes with observations off/on, tracing off/on and both native engines, in fresh processes with fixed Python, NumPy and hash seeds. It compares all sampled economic metrics each turn and the complete canonical economic graph, including RNG and gameplay globals, at the end. In addition to the repository's existing canonical normalization, it removes the documented observation sidecar and relabels the exact native recorder run UUID, retaining event sequence suffixes and all quantities. The [verification report](reports/governing_network_observation.md) records the executed results.

The first milestone-3 governing loop is implemented. Milestone 4 has automated route, counterfactual and rendered-control evidence, with results and scope in the [active report](reports/governing_network_governing.md). Human usability and balancing remain open. Neither deterministic replay nor a rendered script establishes that governing is fun. Loss-and-return remains milestone 5.
